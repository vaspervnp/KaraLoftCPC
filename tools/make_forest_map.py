#!/usr/bin/env python3
"""Level 5's map: the forest, and the first level nobody hand-wrote twice.

THE ARTIST COMPOSED THIS LEVEL AND THIS TOOL ONLY LAYS IT OUT.
`assets/sprites/level2_forest/manifest.json` carries the frame order in
prose and a description of every piece - the bands top to bottom, the
two-tile tree, the branch platforms, the pit in the ground row, the
mountain and the cave mouth - and `mockup_forest.png` is one screen of
it composed. CLAUDE.md 8.9: reading the mockup back tile by tile is the
fastest way to settle a question the tiles alone cannot answer, and it
is where the row of every band below comes from:

    row  0   canopy_fill
    row  1   canopy_edge_a / _b
    row  2   far_crowns
    rows 3-7 far_trunks_a / _b      ... and the branch platforms
    row  8   far_base               ... and the deco
    row  9   THE GROUND
    rows 10+ dirt

THE GROUND IS ROW 9 BECAUSE THE CAMERA SAYS SO. CAMERA_V keeps her
middle between CAM_TOP 64 and CAM_BOT 112 (CLAUDE.md 8.8), and a floor
at row 9 puts it at exactly 112 - the mirror of the City's roof, which
sits at exactly 64. So the view stays at WORLD_CR 0 and what is on the
screen is the artist's own twelve rows; a jump takes her middle to 76,
which is still inside the band, and falling into a pit is the one thing
that scrolls it.

THE LEVEL NUMBER IS 5 AND NOT 2. An ENVIRONMENT is a bank set and a
LEVEL is a map (CLAUDE.md 8.1); the forest is environment 2 and its
block is levels 5-8, so this is level_5.lvl with tileset 2 in its
header. Walking out of level 1's garage goes to level 2, which is a
City map nobody has painted - so this is reachable by LEVEL_GOTO and
not yet by playing.

AND THE SPIKE PIT CANNOT HURT HER, WHICH IS WORTH SAYING RATHER THAN
HIDING. `TA_HAZARD` is defined in src/collide.asm and **nothing reads
it** - grep says 0 uses outside the definition. So the pits are flagged
the way the level means them and, until something reads the bit, what
they actually are is a dip she falls 16 pixels into and jumps out of.
The data is right in advance; the engine is what owes.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
BUILD = os.path.join(ROOT, "build")
sys.path.insert(0, HERE)
from make_level import pack, read                              # noqa: E402
from tilebake import box_pens, encode_tile, sheet_frames       # noqa: E402
import sentries                                              # noqa: E402

ART = os.path.join(ROOT, "assets", "sprites", "level2_forest")

MAP_W, MAP_H = 128, 16          # 6.4 screens across, one down - the City's
LEVEL_ID, TILESET_ID = 5, 2     # level 5 of 24, environment 2

ROW_CANOPY, ROW_EDGE, ROW_CROWNS = 0, 1, 2
ROW_TRUNKS = range(3, 8)
ROW_BASE, ROW_GROUND = 8, 9

SOLID, PLATFORM, HAZARD, LADDER = 1, 2, 4, 8
# THE ONE NEW BIT, and the tile flag byte's last free one: "a satisfied
# receptacle over this cell moves it on to the next tile". The altar's
# empty cells carry it and its lit cells do not, so PLACE_STATUE can
# light an altar without knowing its shape - and a cell that is not an
# altar's is left alone whatever stands on it (CLAUDE.md 8.17).
ADVANCES = 128

# WHAT A TILE DOES, and there is no file in the package to import it
# from (CLAUDE.md 11 step 7): tile_table.json says how a tile is DRAWN
# and carries no collision at all. So this is the designer's statement,
# and the editor's LevelFlagSeeds.Forest is the same one.
#
# THE FACE OF THE FOREST IS BACKGROUND, NOT A WALL - the lesson the
# City's brick already paid for (CLAUDE.md 8.8). Trunks, crowns, the
# canopy and the whole mountain are scenery she walks in front of: made
# solid, a tree would be a wall across the level and the mountain would
# be the end of it.
TILE_FLAGS = {
    "grass": SOLID, "grass_edge_l": SOLID, "grass_edge_r": SOLID,
    "dirt": SOLID,
    # In the ground row with the grass, so they hold her up like it.
    "trunk_base_l": SOLID, "trunk_base_r": SOLID,
    "root_l": SOLID, "root_r": SOLID,
    # THE SIGNATURE MECHANIC. A platform is a floor from above and
    # nothing from below, so she jumps up through a branch and stands
    # on it - which is what "walkable surface = tile top" means.
    "branch_l": PLATFORM, "branch_m": PLATFORM, "branch_r": PLATFORM,
    # Flagged, and nothing reads the bit yet - see the header.
    "spike_pit": HAZARD,
    # The cave's floor is the ground row where the mouth is.
    "cave_floor_l": SOLID, "cave_floor": SOLID, "cave_floor_r": SOLID,
}

EK_PLAYER_START, EK_ENEMY, EK_NPC, EK_PICKUP = 0, 2, 3, 4
EK_HAZARD, EK_DOOR, EK_RECEPTACLE = 5, 6, 7
HZ_SPIKETRAP = 0                # p0 of a hazard: WHICH hazard (8.6)
LK_DISABLES = 1                 # docs/editor.md 5.4's own order
EF_ACTIVE, EF_TAKEN, EF_SOLID, EF_TOUCH = 1, 2, 4, 8
PU_KEY, PU_AMMO, PU_MEDKIT, PU_COIN, PU_IDOL, PU_BOOK = range(6)
EN_AGENT, EN_DRONE, EN_SNIPER = 0, 1, 2
EN_WOLF, EN_BOAR = 5, 6         # they bite, on the ground (CLAUDE.md 8.24)
ENT_MAX = 24
SCREEN_TILES = 20               # 160 pixels of play area, 8 to a tile
PATROL = 3                      # half-width in tiles


def tile_names():
    """Frame order, straight out of the manifest's own description.

    The forest's states it as "Frame index: 0 far_crowns, 1 ..." where
    the City's says "frame order: a, b, c" - and tile_table.json names
    these tiles bg_1..cave_10 by TAG and index, which is not what the
    artist calls them. The two agree on the ORDER, which is what makes
    this readable rather than a second numbering.
    """
    man = json.load(open(os.path.join(
        ROOT, "assets", "sprites", "level2_forest", "manifest.json")))
    sheet = next(s for s in man["sheets"] if s["name"] == "forest_tiles")
    order = sheet["description"].split("Frame index:", 1)[1].strip().rstrip(".")
    names = {}
    for part in order.split(","):
        i, name = part.strip().split(None, 1)
        names[name.strip()] = int(i)
    table = json.load(open(os.path.join(
        ROOT, "assets", "sprites", "level2_forest", "tile_table.json")))
    count = next(s for s in table["sheets"]
                 if s["sheet"] == "forest_tiles")["count"]
    assert len(names) == count, f"{len(names)} names against {count} tiles"
    assert sorted(names.values()) == list(range(count)), "the order has a hole"
    return names


# ---------------------------------------------------------------------
# THE ALTAR AND THE SPIKE TRAP ARE TILES, BAKED HERE - NOT SPRITES.
#
# Both stand still. The altar is 24x32 - three tiles by two - and the
# trap is 8x16, exactly one tile, and neither moves across the screen:
# what changes is WHICH picture is in the cell, the altar's twice (empty,
# then lit) and the trap's four times a cycle. That is the pickup's
# argument (CLAUDE.md 8.6) and the overlays' (7.3) one step further: a
# picture that does not move is scenery, scenery is a map cell, and a
# map cell costs nothing until it changes. So every cel of both is
# composited over the tile it stands on, here, and appended to the
# forest's tileset - and the engine moves a cell from one to the next by
# writing one byte of the map and repainting it.
#
# THE CELS OF A THING ARE CONSECUTIVE INDEXES, and that is the whole
# contract with the engine. A trap's four cels are base..base+3, so the
# animator needs the base and nothing else (src/hazard.asm); an altar
# piece's lit cel is its empty cel + 1, and only the empty one carries
# ADVANCES, so PLACE_STATUE can light whatever is around it without
# being told its shape.
#
# AND THE TWO SPRITE BLOBS STOP GOING INTO THE BANKS, which is what pays
# for this. forestaltar is 1,868 bytes and forestspiketrap 346, in a
# bank set with 671 to spare (CLAUDE.md 6.2); the composites are 64
# bytes a tile. tools/level_banks.py's BAKED says so.
# ---------------------------------------------------------------------
TRAP_SHEET = "forest_spiketrap_cpc_mode0_sheet"
ALTAR_SHEET = "forest_altar_cpc_mode0_sheet"
TILES_SHEET = "forest_tiles_cpc_mode0_sheet"
TRAP_CELS = 4                           # retracted, half, full, half
TRAP_BITES = (False, True, True, True)  # "Damage on frames 1-3"
ALTAR_EMPTY, ALTAR_LIT = 0, 3           # `empty`, and the last of
                                        # `idol_placed`'s three - the eye
                                        # at its middle brightness, since
                                        # a tile cannot pulse
ALTAR_W, ALTAR_H = 3, 2                 # tiles: 24 x 32 pixels
# What an altar or a trap may be composited over: the bands, and nothing
# a designer put there. A prop over a tree trunk would be a pair nothing
# else places, and a bank set with 671 bytes spare cannot afford pairs
# for their own sake.
PROP_GROUND = {"far_trunks_a", "far_trunks_b", "far_base"}
BAKE_LIMIT = 240                        # ENT_BAKE's scratch tiles start
                                        # here (CLAUDE.md 8.6)


class Bake:
    """Every composite the forest's levels place, numbered from the end
    of the tileset in the order they are first placed - so the levels
    SHARE them, because a tileset is the environment's (8.13)."""

    def __init__(self, t):
        self.t = t
        self.name = {i: n for n, i in t.items()}
        self.n = len(t)
        self.tiles, self.tile_boxes = sheet_frames(ART, TILES_SHEET)
        self.trap_sheet, self.trap_boxes = sheet_frames(ART, TRAP_SHEET)
        self.altar_sheet, self.altar_boxes = sheet_frames(ART, ALTAR_SHEET)
        assert len(self.trap_boxes) == TRAP_CELS, "the trap's cycle moved"
        self.blob = bytearray()
        self.extra = []                     # (name, flags) per composite
        self.traps = {}                     # background -> its first cel
        self.altars = {}                    # (piece, background) -> empty

    def _under(self, bg):
        b = self.tile_boxes[bg]
        return box_pens(self.tiles, b["x"], b["y"], b["w"], b["h"])

    def _add(self, name, over, bg, flags):
        under = self._under(bg)
        pens = [[o if o is not None else u for o, u in zip(ro, ru)]
                for ro, ru in zip(over, under)]
        i = self.n + len(self.extra)
        assert i < BAKE_LIMIT, "the bake reached ENT_BAKE's scratch tiles"
        self.blob += encode_tile(pens)
        self.extra.append((name, flags))
        return i

    def trap(self, bg):
        """A trap over `bg`: its cel 0's index, the other three after it."""
        if bg not in self.traps:
            ground = TILE_FLAGS.get(self.name[bg], 0)
            first = None
            for c, b in enumerate(self.trap_boxes):
                over = box_pens(self.trap_sheet, b["x"], b["y"], b["w"],
                                b["h"], alpha=True)
                i = self._add(f"spiketrap_{c}_on_{self.name[bg]}", over, bg,
                              ground | (HAZARD if TRAP_BITES[c] else 0))
                first = i if first is None else first
            self.traps[bg] = first
        return self.traps[bg]

    def altar(self, col, row, bg):
        """One piece of an altar - column 0-2 and row 0-1 of its 3x2 -
        over `bg`. Returns the EMPTY piece's index; the lit one is the
        next."""
        key = ((col, row), bg)
        if key not in self.altars:
            ground = TILE_FLAGS.get(self.name[bg], 0)
            got = []
            for cel, extra in ((ALTAR_EMPTY, ADVANCES), (ALTAR_LIT, 0)):
                b = self.altar_boxes[cel]
                over = box_pens(self.altar_sheet, b["x"] + col * 8,
                                b["y"] + row * 16, 8, 16, alpha=True)
                state = "empty" if cel == ALTAR_EMPTY else "lit"
                got.append(self._add(
                    f"altar_{state}_{col}{row}_on_{self.name[bg]}", over, bg,
                    ground | extra))
            assert got[1] == got[0] + 1
            self.altars[key] = got[0]
        return self.altars[key]


# ---------------------------------------------------------------------
# THE LEVEL, left to right. Every number here is a TILE column, and the
# sections are written in the order she meets them.
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# THE COMPOSITION, ONE ENTRY A LEVEL. Everything above this line is the
# artist's - the bands, the names, the flags - and everything in a
# LAYOUT is a designer's: where the trees stand, where the ground is cut
# and where the branches are. Two levels share the machinery below
# because they share an environment; what makes them different levels
# is entirely in here.
#
# Level 5 is unchanged to the byte, which is the control on this being a
# refactor rather than a rewrite: tools/test_forest.py plays it.
# ---------------------------------------------------------------------
LEVEL_5 = dict(
    level_id=5,
    start_x=3,
    trees=(9, 24, 47, 66, 96, 110),     # the two-tile trunk's LEFT column
    pits=((14, 2), (30, 3), (72, 3), (102, 3)),     # (left column, width)
    # (left column, length, row). THE ROWS ARE 5 AND 7 AND THAT IS HER
    # JUMP: 43 pixels onto a platform against a 16-pixel row is two rows, so a row-5
    # branch with no row-7 branch under it is scenery - see reachable().
    branches=((18, 4, 7), (34, 4, 7), (36, 5, 5),
              (78, 4, 7), (84, 4, 7), (86, 5, 5), (114, 4, 7)),
    mountain=(52, 62),                  # left and right columns, inclusive
    caves=(120,),                       # each mouth's left column, 4 wide;
                                        # the DOOR goes in the last one
    deco={6: "bush_l", 7: "bush_r", 21: "rock", 28: "flowers",
          34: "mushrooms", 44: "bush_l", 45: "bush_r", 69: "rock",
          75: "flowers", 84: "mushrooms", 93: "rock", 105: "flowers"},
    snipers=(),
    # A WOLF ON THE GRASS BEFORE THE MOUNTAIN AND A BOAR PAST THE THIRD
    # PIT: two encounters, fifty tiles apart, and each one with a branch
    # in reach - (34, 4, 7) and (84, 4, 7) - to get above its charge.
    beasts=((42, EN_WOLF), (92, EN_BOAR)),
    entities=[
        # kind, tile x, the row it STANDS on, flags, p0, p1
        ("start", 3, None, 0, 0),
        # THE KEY IS ON A BRANCH, which is what makes the platforms the
        # level rather than scenery: the way out is behind a jump.
        ("key", 38, 5, 0, 0),
        ("ammo", 20, None, 14, 0),
        ("medkit", 64, None, 0, 0),
        # ... and the IDOL is the one pickup drawn out of the forest's
        # OWN sheet - forestpickups carries nothing else (CLAUDE.md 8.6).
        ("idol", 100, None, 0, 0),
        # The altar takes it: level 2's signature, and PLACE_STATUE is
        # the handler that has been waiting for a level with one in it.
        # IT WAS AT 117, under the end of the row-7 branch at 114, and
        # nothing could see that while a receptacle was not drawn. It is
        # drawn now (the bake above), so it stands where the art has
        # room for it: on the grass the far side of the last pit, the
        # flowers moved two along to make the space, and at an ODD
        # column like every altar - the trunks behind its top row
        # alternate a/b by column, so an odd column is one set of six
        # composites for every altar in the forest.
        ("altar", 107, None, 0, 0),
        ("door", None, None, 0, 0),     # in the last cave mouth
    ],
)

# ---------------------------------------------------------------------
# LEVEL 6 - through the cave mouth level 5 ends at, and out the other
# side of it. Level 5's door is an EK_DOOR in its cave at tile 120 and
# LEVEL_GOTO goes to LEVEL_CUR + 1 (CLAUDE.md 8.1), so this is the map
# that door has been leading to since the day it was placed. Same
# environment - levels 5-8 are the forest - so the transition is one
# sector and no art at all.
#
# IT OPENS ON A CAVE MOUTH INSTEAD OF ENDING ON ONE, which is the whole
# of what says the two are consecutive: she walks out of the dark at
# the left edge and the forest is in front of her again.
#
# AND IT IS THE FIRST MAP DESIGNED WITH THE SPIKES AS A MECHANIC. When
# level 5 was drawn, TA_HAZARD had no reader and its pits were a dip
# (8.12); they bite for 16 now. So level 6 has THREE pits and not four,
# every one of them at most 3 tiles - which a RUN clears in its 15-frame
# arc and a walk does not (8.8) - and a medkit between the second and
# the third. What that comes to end to end is measured rather than
# hoped: see tools/test_forest.py.
#
# THE KEY IS TWO BRANCHES UP, which is level 5's idea taken one step:
# there the key sat on a row-5 branch with a row-7 branch under it, and
# here the climb is the point - ground to row 7, row 7 to row 5, each
# inside the two rows her jump reaches.
LEVEL_6 = dict(
    level_id=6,
    start_x=3,                          # on the cave floor she came out of
    trees=(12, 30, 58, 76, 104),
    pits=((18, 2), (52, 3), (88, 3)),
    branches=((22, 4, 7), (62, 5, 7), (65, 5, 5), (94, 4, 7), (110, 5, 7)),
    mountain=(36, 46),
    caves=(1, 120),                     # ... in at the left, out at the right
    deco={8: "bush_l", 9: "bush_r", 25: "rock", 48: "flowers",
          68: "mushrooms", 96: "rock", 112: "flowers"},
    snipers=(),
    beasts=((30, EN_WOLF), (80, EN_BOAR)),
    entities=[
        ("start", 3, None, 0, 0),
        ("ammo", 26, None, 14, 0),
        ("key", 67, 5, 0, 0),           # the top of the climb
        ("medkit", 72, None, 0, 0),
        ("idol", 98, None, 0, 0),
        ("altar", 117, None, 0, 0),     # odd, like every altar - see 5
        ("door", None, None, 0, 0),
    ],
)

# ---------------------------------------------------------------------
# LEVEL 7 - THE FOREST'S OWN MECHANIC, which is where level 6's cave
# leads: plan.md's "placing the statuette on the altar to disable the
# trap", and the first level in which the altar does something.
#
# THE IDOL IS TWO BRANCHES UP and the altar is on the ground past the
# mountain; past the altar is a FIELD OF EIGHT SPIKE TRAPS, one every
# other tile, and past the field is the key and the way out. The traps
# all start on cel 0, so they come up together and go down together -
# a field that breathes - and a field whose traps are all down at once
# is one she is bitten in once a cycle, where a rippling one would hold
# HAZARD_IN up and bite her once for the lot (src/player.asm, 8.12).
#
# SO THE ALTAR IS A CHOICE AND ITS PRICE IS MEASURED, not hoped: carry
# the idol to it and the whole field goes down and stays down; walk on
# without it and the field is paid for in bites. Her box is six bytes
# against a trap every eight, so wherever she stands in the field she is
# in at least one; what crossing it costs at a walk and at a run is
# tools/test_forest7.py's to say, with the altar as its control.
#
# A medkit at the start and none after: she comes in from level 6 with
# whatever its pits left her, and a medkit past the field would make the
# field a toll she could pay twice.
LEVEL_7 = dict(
    level_id=7,
    start_x=3,                          # out of the cave she came in by
    trees=(12, 34, 82, 108),
    pits=((18, 2), (88, 3)),
    branches=((22, 5, 7), (25, 5, 5),  # the idol's climb, level 6's shape
              (96, 4, 7)),              # ... and the key's one step
    mountain=(40, 50),
    caves=(1, 120),
    deco={8: "flowers", 30: "rock", 52: "bush_l", 53: "bush_r",
          78: "mushrooms", 92: "rock", 104: "flowers", 114: "rock"},
    # NO SNIPER, AND THAT IS A MEASUREMENT TOO (CLAUDE.md 8.27). One stood
    # at 104, past the key, and was never on the screen with the field -
    # and walked from the start, the field's eighth trap was a cel behind
    # the map on 7 game frames against 2 without him: ENEMY_PICK's walk
    # of the table, a thousand T for a sentry nowhere near, is all the
    # eight cells breathing together had to spare. Level 8's fields are
    # four cells, and its sniper costs them nothing.
    snipers=(),
    entities=[
        ("start", 3, None, 0, 0),
        ("medkit", 7, None, 0, 0),
        ("idol", 27, 5, 0, 0),          # the top of the climb
        ("ammo", 46, None, 14, 0),
        ("altar", 57, None, 0, 0),      # odd, like every altar
        ("key", 98, 7, 0, 0),
        ("door", None, None, 0, 0),
    ],
    # (column, the cel it starts on, which altar stops it)
    traps=tuple((x, 0, 0) for x in range(62, 78, 2)),
    # NO BEAST, AND THAT IS A MEASUREMENT (CLAUDE.md 8.26): a field of
    # eight cells breathing together and a wolf's refresh do not fit one
    # second sweep. With the refresh first the field was a cel behind the
    # map on 214 game frames of 454; with the field's paint first the
    # sweep ran to 85,892 T and the loop was 87 of 200 standing.
)

# ---------------------------------------------------------------------
# LEVEL 8 - THE FOREST'S LAST, which is where level 7's cave leads, and
# the way out of the forest: plan.md ends it at "a dark cave opening at
# the root of a mountain", and mockup_forest_cave.png draws exactly
# that - the mountain's face, and the arch IN the rock. The cave mouths
# of levels 5-7 stand in the trees; this one is cut into the mountain,
# and its door leads to level 9, the cave - an environment away.
#
# TWO ALTARS AND TWO FIELDS, AND EACH ALTAR STOPS ONLY ITS OWN. That is
# what the LINKS are for: a Disables link names its source and its
# target, so the first idol on the first altar puts the first field down
# and leaves the second one breathing. Two idols, either one on either
# altar - an idol is an idol - and the key past the second field.
LEVEL_8 = dict(
    level_id=8,
    start_x=3,
    trees=(8, 50, 102),
    pits=((44, 3), (96, 3)),
    branches=((14, 5, 7), (17, 5, 5),   # the first idol's climb
              (60, 5, 7), (63, 5, 5),   # ... and the second's
              (89, 4, 7)),              # and the key's step
    mountain=(108, 127),                # the mountain to the end of the
    caves=(1, 118),                     # map, and the way out IN it
    deco={5: "rock", 22: "flowers", 41: "mushrooms", 55: "bush_l",
          56: "bush_r", 69: "rock", 93: "flowers", 105: "mushrooms"},
    snipers=(56,),                      # under the second idol's climb
    entities=[
        ("start", 3, None, 0, 0),
        ("idol", 19, 5, 0, 0),
        ("altar", 27, None, 0, 0),      # the first altar, entity 2
        ("ammo", 48, None, 14, 0),
        ("idol", 65, 5, 0, 0),
        ("medkit", 70, None, 0, 0),
        ("altar", 73, None, 0, 0),      # the second, entity 6
        ("key", 91, 7, 0, 0),
        ("door", None, None, 0, 0),
    ],
    traps=tuple((x, 0, 0) for x in range(32, 40, 2))
          + tuple((x, 0, 1) for x in range(78, 86, 2)),
)

LAYOUTS = (LEVEL_5, LEVEL_6, LEVEL_7, LEVEL_8)


def build_map(t, L, bake):
    """The 128x16 grid, as the artist's bands with the level cut into it."""
    g = [[t["far_trunks_a"]] * MAP_W for _ in range(MAP_H)]
    for x in range(MAP_W):
        g[ROW_CANOPY][x] = t["canopy_fill"]
        g[ROW_EDGE][x] = t["canopy_edge_a" if x % 2 == 0 else "canopy_edge_b"]
        g[ROW_CROWNS][x] = t["far_crowns"]
        for r in ROW_TRUNKS:
            g[r][x] = t["far_trunks_a" if (x + r) % 2 == 0 else "far_trunks_b"]
        g[ROW_BASE][x] = t["far_base"]
        g[ROW_GROUND][x] = t["grass"]
        for r in range(ROW_GROUND + 1, MAP_H):
            g[r][x] = t["dirt"]

    # ---- the mountain, over the far_trunks rows -------------------
    # "mtn_slope (45-degree left edge) over far_trunks rows,
    #  mtn_slope_base in the far_base row" - so the slope walks in one
    # column a row as it comes down, and the rock fills behind it.
    left, right = L["mountain"]
    for i, r in enumerate(ROW_TRUNKS):
        g[r][left + i] = t["mtn_slope"]
        for x in range(left + i + 1, right + 1):
            g[r][x] = t["mtn_rock_moss" if (x + r) % 3 == 0 else "mtn_rock"]
    for x in range(left + len(ROW_TRUNKS), right + 1):
        g[ROW_BASE][x] = t["mtn_slope_base"]

    # ---- the big trees, two tiles wide ----------------------------
    for x in L["trees"]:
        for r in ROW_TRUNKS:
            g[r][x], g[r][x + 1] = t["trunk_l"], t["trunk_r"]
        g[ROW_BASE][x], g[ROW_BASE][x + 1] = t["trunk_l"], t["trunk_r"]
        g[ROW_GROUND][x] = t["trunk_base_l"]
        g[ROW_GROUND][x + 1] = t["trunk_base_r"]
        if x - 1 >= 0:
            g[ROW_GROUND][x - 1] = t["root_l"]
        if x + 2 < MAP_W:
            g[ROW_GROUND][x + 2] = t["root_r"]

    # ---- the branch platforms -------------------------------------
    # A branch that leaves a trunk gets the knot cel, which is what the
    # artist drew it for; one in mid-air simply starts with branch_l.
    for x, n, row in L["branches"]:
        for i in range(n):
            g[row][x + i] = t["branch_l" if i == 0 else
                              "branch_r" if i == n - 1 else "branch_m"]
        for tx in L["trees"]:
            if tx == x + n:                     # it meets a trunk's left side
                g[row][tx] = t["trunk_knot_l"]
            if tx + 1 == x - 1:                 # ... or its right
                g[row][tx + 1] = t["trunk_knot_r"]

    # ---- the pits in the ground row -------------------------------
    # "grass_edge_r, spike_pit x N, grass_edge_l" - the edges face IN,
    # which is the artist's naming and not a mistake here: the tile on
    # the pit's left is the RIGHT-hand edge of the grass before it.
    for x, n in L["pits"]:
        g[ROW_GROUND][x - 1] = t["grass_edge_r"]
        for i in range(n):
            g[ROW_GROUND][x + i] = t["spike_pit"]
        g[ROW_GROUND][x + n] = t["grass_edge_l"]

    # ---- the deco on the undergrowth row --------------------------
    for x, name in L["deco"].items():
        g[ROW_BASE][x] = t[name]

    # ---- the altar, standing on the grass ------------------------
    # The record is its BOTTOM-CENTRE cell, so the 3x2 is one column
    # either side of it and the two rows above the ground.
    solid = {t[n] for n, f in TILE_FLAGS.items() if f & SOLID}
    names = {i: n for n, i in t.items()}
    for x in altar_columns(L):
        for row in range(ALTAR_H):
            r = ROW_GROUND - ALTAR_H + row
            for col in range(ALTAR_W):
                c = x - 1 + col
                assert names[g[r][c]] in PROP_GROUND, (
                    f"the altar at {x} stands over {names[g[r][c]]}")
                g[r][c] = bake.altar(col, row, g[r][c])
        assert all(g[ROW_GROUND][x - 1 + col] in solid
                   for col in range(ALTAR_W)), f"the altar at {x} is on air"

    # ---- and the spike traps, one tile each, on the grass --------
    for x, _, _ in L.get("traps", ()):
        assert names[g[ROW_BASE][x]] == "far_base", (
            f"the trap at {x} stands over {names[g[ROW_BASE][x]]}")
        assert g[ROW_GROUND][x] in solid, f"the trap at {x} is over a pit"
        g[ROW_BASE][x] = bake.trap(g[ROW_BASE][x])

    # ---- and the cave mouths --------------------------------------
    # 4 wide x 6 high, ending IN the ground row: arch, four rows of
    # sides, floor. Level 5 has one and it is the way OUT; level 6 has
    # two and the first is the way IN - the same six rows of tiles read
    # as an entrance or an exit depending only on which end of the map
    # they are at, which is why there is no second set of art for it.
    arch = ROW_GROUND - 5
    for cave in L["caves"]:
        for i in range(4):
            g[arch][cave + i] = t[f"cave_arch_{i}"]
        for r in range(arch + 1, ROW_GROUND):
            g[r][cave] = t["cave_side_l"]
            g[r][cave + 1] = t["cave_dark"]
            g[r][cave + 2] = t["cave_dark"]
            g[r][cave + 3] = t["cave_side_r"]
        for i, name in enumerate(("cave_floor_l", "cave_floor",
                                  "cave_floor", "cave_floor_r")):
            g[ROW_GROUND][cave + i] = t[name]
    return bytes(b for row in g for b in row)


def altar_columns(L):
    """Where a LAYOUT puts its altars - each one's bottom-centre column."""
    return [x for name, x, *_ in L["entities"] if name == "altar"]


def entity(kind, tile_x, base_row, flags, p0=0, p1=0):
    """One record. Given in TILES and converted here, so the numbers
    above stay readable against the map; the FORMAT stores world pixels
    with y at the BASE of the hitbox (CLAUDE.md 8.6)."""
    x, y = tile_x * 8, base_row * 16
    return bytes([kind, x & 255, x >> 8, y & 255, y >> 8, flags, p0, p1])


# SHE STARTS IN THE AIR ON PURPOSE, one row above the grass, so she
# falls the last 16 pixels onto it - free against FALL_FREE of 96. A
# 64-line box placed level with the tiles starts INSIDE them and the
# landing snaps her a whole row low.
#
# AND NEITHER LEVEL HAS A SNIPER, WHICH IS A MEASUREMENT AND NOT AN
# OVERSIGHT. The forest's only ranged character is 12x64 - agent class,
# which CLAUDE.md 8.7 measured as unaffordable at 50 Hz and 9 called
# affordable at 25 Hz ON PAPER, with nothing having measured it. Two of
# them went in level 5 and the measurement is what took them out:
# standing beside one, the loop is
#
#     80 game frames in 200 hardware, against 100 with ENEMY_LIVE at 0
#
# - the same level, the same spot, one thing changed. Twenty holes in
# two hundred frames, where the City's drones cost nought to five.
# EN_SNIPER stays in the type table the way EN_AGENT has.
#
# WHAT THEY HAVE IS THE FOREST'S OWN CREATURES: a wolf and a boar each,
# on the ground (`beasts`). Their tags are RUN and ATTACK - melee - and
# a row of ENEMY_TYPES whose EN_T_KIND says so charges and bites where a
# drone would fire, and keeps to the line it was placed on (CLAUDE.md
# 8.24). They hold the lock at 100 of 200.

# What each name in a LAYOUT's `entities` means, in the engine's terms:
# the kind, the flag bits, and which of p0/p1 the two numbers are. `p0
# is always "which thing this is"' (CLAUDE.md 8.6).
ENTITY_KINDS = {
    "start":  (EK_PLAYER_START, EF_ACTIVE, 0),
    "key":    (EK_PICKUP, EF_ACTIVE | EF_TOUCH, PU_KEY),
    "ammo":   (EK_PICKUP, EF_ACTIVE | EF_TOUCH, PU_AMMO),
    "medkit": (EK_PICKUP, EF_ACTIVE | EF_TOUCH, PU_MEDKIT),
    "idol":   (EK_PICKUP, EF_ACTIVE | EF_TOUCH, PU_IDOL),
    "altar":  (EK_RECEPTACLE, EF_ACTIVE, PU_IDOL),
    "door":   (EK_DOOR, EF_ACTIVE | EF_SOLID, 0),
    # NOT EF_TOUCH: a trap is not something she takes, and the touch
    # sweep publishes the first box it meets - a trap there would hide
    # the idol lying next to it (CLAUDE.md 8.6). What it does to her is
    # the TILE's: cels 1-3 carry HAZARD and HAZARD_HURT reads the flag.
    "trap":   (EK_HAZARD, EF_ACTIVE, HZ_SPIKETRAP),
}


def build_entities(t, L):
    """A LAYOUT's records, in the order it lists them, then its traps -
    and the LINKS that say which altar stops which trap.

    The order is the FILE's order and it matters: the engine clears its
    24 slots and LDIRs count * 8 bytes over the front, so the records
    have to be contiguous from zero (CLAUDE.md 8.3). A link names its
    source and target by that position, so the traps go LAST and every
    index before them is the one the layout wrote.
    """
    recs = []
    for name, x, row, p1, _ in L["entities"]:
        kind, flags, p0 = ENTITY_KINDS[name]
        if name == "door":
            # THE DOOR IS IN THE LAST CAVE MOUTH, whichever that is -
            # level 5 has one and level 6 has two, and the way OUT is
            # the one furthest along. Its p1 is the PU_* that opens it.
            x, p0, p1 = L["caves"][-1] + 1, 0, PU_KEY
        if name == "altar":
            p1 = 1                       # how many it still wants
        if name == "start":
            row = ROW_GROUND - 1         # a row high, so she falls onto it
        recs.append(entity(kind, x, ROW_GROUND if row is None else row,
                           flags, p0, p1))
    for x in L["snipers"]:
        recs.append(entity(EK_ENEMY, x, ROW_GROUND, EF_ACTIVE,
                           EN_SNIPER, 0))
    # THE BEASTS: the forest's own wolf and boar, which bite where the
    # sniper would shoot (CLAUDE.md 8.24). They stand on the ground row
    # and keep to it, so a branch is where she is out of their reach.
    for x, kind in L.get("beasts", ()):
        recs.append(entity(EK_ENEMY, x, ROW_GROUND, EF_ACTIVE,
                           kind, PATROL))

    # THE TRAPS, AND WHAT STOPS EACH ONE. `traps` is (column, phase,
    # which altar): the phase is the cel it starts on, so a field can be
    # set to breathe together or to ripple, and the altar is the LINK -
    # docs/editor.md 5.4's `Disables`, receptacle -> hazard, read by
    # PLACE_STATUE (src/hazard.asm).
    altars = [i for i, (name, *_) in enumerate(L["entities"])
              if name == "altar"]
    links = bytearray()
    for x, phase, which in L.get("traps", ()):
        assert 0 <= phase < TRAP_CELS
        links += bytes([LK_DISABLES, altars[which], len(recs), 0])
        recs.append(entity(EK_HAZARD, x, ROW_GROUND, EF_ACTIVE,
                           HZ_SPIKETRAP, phase))
    return b"".join(recs), bytes(links)


def reachable(m, t, L):
    """Every place she can stand, from the start, and how she gets there.

    THE EDITOR'S GENERATOR HAS THIS AND A HAND-MADE LEVEL NEEDS IT MORE:
    a flood fill over the floors is the only thing that says the key is
    somewhere she can get to. It is deliberately CONSERVATIVE - it
    credits her with a 2-row jump and 3 tiles of carry, where the arc is
    15 frames and a run covers more - so a level that passes here passes
    on the machine.
    """
    solid = {t[n] for n, f in TILE_FLAGS.items() if f & SOLID}
    stand = {t[n] for n, f in TILE_FLAGS.items() if f & (SOLID | PLATFORM)}

    def on(x, row):
        """Can she stand at (x, row)? - something under her, air at her feet."""
        if not 0 <= x < MAP_W or not 0 <= row < MAP_H:
            return False
        return (m[row * MAP_W + x] in stand
                and m[(row - 1) * MAP_W + x] not in solid)

    def under(x, row):
        """Where she lands falling from just above (x, row)."""
        for r in range(row, MAP_H):
            if on(x, r):
                return r
        return None

    sx = L["start_x"]
    start = under(sx, ROW_GROUND - 1)
    seen, queue = set(), [(sx, start)]
    while queue:
        x, row = queue.pop()
        if (x, row) in seen or row is None:
            continue
        seen.add((x, row))
        for nx in (x - 1, x + 1):               # walk, or walk off an edge
            if on(nx, row):
                queue.append((nx, row))
            elif 0 <= nx < MAP_W and m[row * MAP_W + nx] not in solid:
                queue.append((nx, under(nx, row)))
        for nx in range(x - 3, x + 4):          # jump, at most two rows
            for nr in (row - 1, row - 2):
                if on(nx, nr):
                    queue.append((nx, nr))
    return seen


def checks(m, t, ents, L):
    """What the engine would read a byte of, do nothing about, and carry
    on past - so it is refused here instead (CLAUDE.md 11 step 7)."""
    assert len(ents) // 8 <= ENT_MAX, f"{len(ents) // 8} records"
    pickups = [i for i in range(0, len(ents), 8) if ents[i] == EK_PICKUP]
    assert len(pickups) <= 16, "more pickups than ENT_BAKE has scratch tiles"
    for i in pickups:
        assert ents[i + 5] & EF_TOUCH, "a pickup with no EF_TOUCH"
        x = ents[i + 1] | ents[i + 2] << 8
        y = ents[i + 3] | ents[i + 4] << 8
        assert x % 8 == 0 and y % 16 == 0, f"a pickup off the grid at {x},{y}"

    # NO TWO ENEMIES MAY SHARE A SCREEN. ENEMY_PICK takes the first it
    # finds near the view, so the second is not a second enemy - it is
    # no enemy (CLAUDE.md 8.7). p1 is the patrol half-width, so what
    # has to clear a screen is the gap between the PATROLS.
    spans = sorted((ents[i + 1] | ents[i + 2] << 8) // 8
                   for i in range(0, len(ents), 8) if ents[i] == EK_ENEMY)
    for a, b in zip(spans, spans[1:]):
        gap = (b - PATROL) - (a + PATROL)
        assert gap > SCREEN_TILES, f"two enemies {gap} tiles apart"
    # ... and a SNIPER is a sentry (CLAUDE.md 8.27): drawn compiled, so
    # his column must keep every line of his box inside a page of video
    # RAM, and redrawn only when he turns, so no pickup, trap or altar
    # may be under him - tools/sentries.py, the desert's and the
    # station's own rule.
    sentries.check(L["level_id"], [(x, ROW_GROUND) for x in L["snipers"]],
                   ents)

    # ... AND EVERY THING SHE HAS TO TOUCH MUST BE SOMEWHERE SHE CAN
    # STAND. A record's row is the floor it stands on and not the cell
    # it is in: y is the BASE of the hitbox (CLAUDE.md 8.6).
    where = reachable(m, t, L)
    for i in range(0, len(ents), 8):
        if ents[i] not in (EK_PICKUP, EK_DOOR, EK_RECEPTACLE):
            continue
        x = (ents[i + 1] | ents[i + 2] << 8) // 8
        row = (ents[i + 3] | ents[i + 4] << 8) // 16
        assert (x, row) in where, (
            f"a kind-{ents[i]} record at tile {x}, row {row} is somewhere "
            f"she cannot stand - her jump reaches 43 pixels and a row is 16")

    # ... and she has to be able to WALK to the door, which on this
    # level means the ground is not cut in two by anything solid.
    solid = {t[n] for n, f in TILE_FLAGS.items() if f & SOLID}
    row = m[ROW_GROUND * MAP_W:(ROW_GROUND + 1) * MAP_W]
    open_run = [x for x, b in enumerate(row) if b not in solid]
    assert all(b in solid or t["spike_pit"] == b for b in row), \
        "the ground row has something on it that is neither floor nor pit"
    return len(pickups), len(spans), len(open_run)


def main():
    t = tile_names()

    # THE MAPS FIRST AND THE BAKE AFTER, because the levels share it: a
    # composite takes its index the first time ANY of them places it, so
    # the tileset is only known once every map is built - the cave's own
    # order (tools/make_cave_map.py), for the cave's own reason.
    bake = Bake(t)
    built = []
    for L in LAYOUTS:
        m = build_map(t, L, bake)
        ents, links = build_entities(t, L)
        counts = checks(m, t, ents, L)
        built.append((L, m, ents, links, counts))

    # ONE FLAG TABLE FOR THE ENVIRONMENT, NOT ONE PER LEVEL. What a tile
    # DOES is a property of the tileset and the tileset is the forest's;
    # MAP_INSTALL LDIRs it over all 256 entries of TILE_ATTR whichever
    # of the environment's levels is loading (CLAUDE.md 8.3). The baked
    # tiles' flags are the bake's: what is under them, plus HAZARD on a
    # trap's biting cels and ADVANCES on an altar's empty ones.
    flags = bytes(TILE_FLAGS.get(n, 0)
                  for n, _ in sorted(t.items(), key=lambda kv: kv[1]))
    flags += bytes(f for _, f in bake.extra)
    out = os.path.join(BUILD, "tileflags_level2_forest.bin")
    open(out, "wb").write(flags)
    print(f"-> tileflags_level2_forest.bin  {len(flags)} tiles, "
          f"{sum(1 for f in flags if f)} with anything on")

    # THE BLOB IS TRUNCATED TO THE TILESET'S OWN TILES FIRST, so running
    # this twice bakes the same pieces rather than stacking a second copy
    # - make_city_map.py's rule and the cave's. build.sh runs this AFTER
    # build_levels.py exported the blob and BEFORE level_banks.py lays it
    # into a bank, and the ZX0 goes with it: build_levels packed the
    # blob before anything was appended, and tools/test_spans.py depacks
    # the stream on the emulator.
    tiles = os.path.join(BUILD, "levels", "level2_forest", "foresttiles.bin")
    base = open(tiles, "rb").read()[:64 * len(t)]
    assert len(base) == 64 * len(t), "the tile blob is short"
    open(tiles, "wb").write(base + bytes(bake.blob))
    from build_levels import zx0
    zx0(tiles)
    print(f"-> foresttiles.bin  {len(t)} tiles + {len(bake.extra)} baked "
          f"({len(bake.traps)} trap set{'s' if len(bake.traps) != 1 else ''}"
          f" of {TRAP_CELS}, {len(bake.altars)} altar pieces x 2) = "
          f"{len(base) + len(bake.blob)} bytes")

    for L, m, ents, links, (pickups, enemies, pit_tiles) in built:
        n = L["level_id"]
        blob = pack(level_id=n, tileset_id=TILESET_ID,
                    width=MAP_W, height=MAP_H, map_bytes=m, entities=ents,
                    links=links)
        out = os.path.join(BUILD, f"level_{n}.lvl")
        open(out, "wb").write(blob)
        back = read(blob)
        assert back["map"] == m and back["entities"] == len(ents) // 8
        traps = len(L.get("traps", ()))
        print(f"-> level_{n}.lvl     {len(blob)} bytes: {back['width']}x"
              f"{back['height']}, {back['entities']} entities "
              f"({pickups} pickups, {enemies} enemies, {traps} traps), "
              f"{len(links) // 4} links, tileset {TILESET_ID}")
        print(f"   {len(L['trees'])} trees, {len(L['branches'])} branch "
              f"platforms, {len(L['pits'])} pits ({pit_tiles} tiles of "
              f"spike), a mountain and {len(L['caves'])} cave "
              f"mouth{'s' if len(L['caves']) > 1 else ''} at "
              f"{', '.join(str(c) for c in L['caves'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
