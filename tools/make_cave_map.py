#!/usr/bin/env python3
"""The cave's maps - levels 9 TO 12, all four, and the first levels that are TALL.

THE ARTIST COMPOSED THIS ENVIRONMENT AND THIS TOOL ONLY LAYS IT OUT.
`assets/sprites/level3_cave/manifest.json` describes every piece and
the description is the specification:

    bg = dark blue/black rock (3 variants, identical borders so they
    mix freely). wall: wall_fill + inner edges for left (wall_l,
    wall_l_b) and right walls (wall_r, wall_r_b); the a/b edges stack
    in any order. platform: ground (top of a rock mass), floating
    ledge_l/m/r (1 tile thick, walkable top row 0), wall_l_ledge /
    wall_r_ledge (ledge growing out of a wall edge, joins ledge_m).
    ... ladder: climbable rope ladder (repeats vertically).
    gate (4x5 tiles): row 0 = gate_slot_sun, _moon, _eye, _star;
    rows 1-4 = gate_pillar_l, gate_door_l, gate_door_r, gate_pillar_r.

IT IS 32x64 AND EVERY OTHER MAP IN THIS GAME IS 128x16. W * H is always
2,048 (CLAUDE.md 8.3) and the cave is the shape that stands the City on
its end: 1.6 screens across and 5.3 DOWN. MAP_INSTALL patches the
engine's own thirty-six immediates out of the header, which
tools/test_shape.py proved on a 6128 - these are the first SHIPPED
levels to ask for it.

AND THEY ARE THE FIRST MAPS WITH LADDERS SINCE THE CITY, which is not a
coincidence: only levels 1 and 3 have a `ladder` tile in their tilesets
and tools/level_banks.py reads that off tile_table.json to decide which
levels carry the `climb` cels at all (CLAUDE.md 6.2). The other four
take an action blob 2,722 bytes shorter. So a cave without ladders
would waste the one thing its bank set was given.

THE LADDER IS AN OVERLAY HERE AND AN OPAQUE TILE IN THE CITY, which is
CLAUDE.md 8.3's own example of the two tables being independent: what a
tile DOES and how it is DRAWN are different questions. The engine has
no masked tile path (7.3), so every overlay placed here is composited
at build time by tools/tilebake.py - the City's own baker, lifted.
Measured, what the bake recovers over drawing the ladder plain: 20
pixels of 128 over the background and 61 over wall_fill, because the
cave's background is 88-94 pixels of black out of 128.

ONE TOOL, FOUR COMPOSITIONS - AND UNLIKE THE FOREST'S, THEY SHARE A
BAKE. A tileset belongs to the ENVIRONMENT and not to the level, so
levels 9 to 12 point into ONE cavetiles.bin and one
tileflags_level3_cave.bin: every (overlay, background) pair any of them
places has to take the same index in all of them, and the blob is
appended to ONCE. make_forest_map.py never had to say this because the
forest has no overlays at all (7.3). So the maps are built first, all
of them, into one BAKED; the composite happens after.

AND THE TILESET IS BOTH OF THE ENVIRONMENT'S SHEETS: the cave's
forty-seven and then the earthquake's thirteen (build_levels.
one_tileset), with the composites after all sixty. That renumbered
every composite by thirteen, so levels 9-11 are no longer the files
that shipped byte for byte - and what says nothing moved is the
PICTURE: every one of their 2,048 cells draws the same 64 bytes and
carries the same attribute, which is CLAUDE.md 8.3's own statement that
the numbering is not part of the contract.

    level 9   THE WAY UP. She enters at the bottom and climbs eight
              floors to a gate. The ladder's column moves every floor,
              so each one has to be WALKED before it can be left -
              the editor generator's own rule (11 step 7), and the
              only thing that makes eight floors a level rather than
              one floor eight times.

    level 10  THE WAY DOWN, which is where level 9's gate has always
              pointed. It OPENS on that gate - gate_open_l/gate_open_r,
              the two door leaves folded back, which nothing in this
              game had ever placed - and the way out is at the bottom.
              And every floor she leaves has a HOLE in it three tiles
              wide, so going down is the first thing in this
              environment that is a CHOICE: the ladder is free and the
              hole is 128 world lines, which is 32 of her 100 points
              against FALL_FREE of 96 (8.4). It is the City's
              ledge-against-gap one environment along.

    level 11  THE WAY UP AGAIN, BY THE ROCK - which is where level 10's
              gate at the bottom leads, and what plan.md names as the
              cave's mechanic: a climb on platforms and stalagmites.
              There is NO LADDER in it. Between every pair of floors is
              a staircase - a two-tile stalagmite and two ledges, each
              two rows above the last and starting the column after it
              ends - so the way up is twenty-eight jumps of 32 lines
              against a reach of 36. The highest step is six rows above
              the floor below it, 96 lines, which is FALL_FREE exactly:
              a miss costs her the height and never a point.

    level 12  DOWN TO THE WATER, the cave's last - where level 11's gate
              at the top leads, and after the earthquake plan.md ends
              the environment with. The eighth floor is under the flood,
              the walls are cracked and pouring, and three of the six
              ladders are broken: she climbs down to the end and lets
              go, and the fall is measured from where the ladder ENDS
              (FALL_MARK, 8.4) - two, three and four rungs short are 96,
              80 and 64 lines, and all of them free. The gate out stands
              on the last dry floor, and past it is the undersea.

WHAT IS NOT HERE IS THE PUZZLE. The artist drew a four-slot gate and
two panels that hint the order sun-moon / eye-star, and CLAUDE.md 8.1
calls the cave's signature a "3-symbol book/lever puzzle";
READ_BOOK_PUZZLE and CURRENT_BOOK_ID exist in the engine and nothing
has ever driven them. The gates here are EK_DOORs that a key opens, and
the slots are drawn UNFILLED at both ends - including level 10's, which
she has already come through. gate_book_sun/_moon/_eye/_star are in the
sheet and stay unplaced, because a gate drawn with its books in would
be this file claiming a mechanic that is not written.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
BUILD = os.path.join(ROOT, "build")
sys.path.insert(0, HERE)
from make_level import pack, read                              # noqa: E402
from tilebake import bake_overlays, name_of                    # noqa: E402

ART = os.path.join(ROOT, "assets", "sprites", "level3_cave")
# THE TILESET IS BOTH SHEETS, in the manifest's order: the cave's own
# forty-seven and then the earthquake's thirteen - the cracks, the
# waterfall, the flood's surface and its body. build_levels.one_tileset
# appends the second blob to the first, so a tile of either sheet is an
# index a map can name (CLAUDE.md 8.13).
SHEETS = ("cave_tiles_cpc_mode0_sheet", "cave_quake_cpc_mode0_sheet")
TILE_SHEETS = (("cave_tiles", 47), ("cave_quake", 13))

MAP_W, MAP_H = 32, 64           # 1.6 screens across, 5.3 DOWN
TILESET_ID = 3                  # environment 3, levels 9-12

SOLID, PLATFORM, HAZARD, LADDER = 1, 2, 4, 8

# The walls are the map's edges and she is three tiles wide, so the
# inner faces go here and everything outside them is fill.
WALL_L, WALL_R = 3, 28

# FLOORS EIGHT ROWS APART, which is 128 world lines - the City's own
# roof-to-street drop, and what CLAUDE.md 11 step 7's table fixed for
# the editor's generator. It is SHARED by both levels and not a
# layout's own, because neither number is a composition: the first
# floor is row 6 because her box is 64 lines and a floor above it
# starts her at a negative Y, and eight rows is the drop the fall
# damage is scaled against.
FLOORS = (6, 14, 22, 30, 38, 46, 54, 62)

# A HOLE IS THREE TILES AND THE NUMBER IS BOX_SOLID_V'S. It ORs the
# attributes of every tile under her six-byte box - two of them, three
# when she is not aligned - so a two-tile gap has positions where she
# is still standing across solid floor (8.8). Three gives her byte
# positions where everything under her is open.
HOLE_W = 3

# ---------------------------------------------------------------------
# The two compositions.
#
# `ladders` is (the floor the ladder HANGS FROM, its column): it
# occupies that floor's own row and the seven below it, so ONE tuple is
# the way up from the floor beneath and the way down from this one. The
# top rung being in the upper floor's row is what lets her walk over it
# and step onto the shaft with DOWN (8.8) - a rung she could only fall
# onto is not a way up.
# ---------------------------------------------------------------------
LEVEL_9 = dict(
    level=9,
    about="the way up",
    ladders=((54, 24), (46, 8), (38, 20), (30, 6), (22, 22), (14, 10),
             (6, 25)),
    holes=(),
    start=(6, FLOORS[-1]),              # column, the floor she stands on
    gate=(12, FLOORS[0]),               # the way out, shut
    entrance=None,
    # THE KEY IS ON THE SECOND FLOOR FROM THE TOP, so the climb is done
    # before the gate can be opened and the last ladder is not a
    # shortcut past it.
    pickups=((20, FLOORS[-2], "ammo"), (12, FLOORS[-4], "medkit"),
             (22, FLOORS[1], "key")),
    crystals=((54, 14, "crystal_0"), (54, 15, "crystal_1"),
              (38, 18, "crystal_0"), (22, 11, "crystal_1")),
    fixtures=((50, 12, "beam_top"), (51, 12, "beam_post"),
              (52, 12, "beam_post"), (34, 20, "lamp_0"),
              (18, 8, "lamp_1")),
    pillars=(),
    pools=(),
)

LEVEL_10 = dict(
    level=10,
    about="the way down",
    # The sides alternate, so every floor is crossed; and the hole is
    # always PAST the ladder from where she lands, never between her
    # and it. A hole in the way would make the ladder reachable only by
    # a run-jump across three tiles - which she can do (8.8) and which
    # reachable() deliberately does not credit her with.
    ladders=((6, 22), (14, 9), (22, 21), (30, 11), (38, 19), (46, 13),
             (54, 24)),
    # (the floor, the first of its three columns). They sit against the
    # wall she is walking toward, so the floor simply breaks away there
    # and ledge_l / ledge_r cap the edge it leaves - the two tiles the
    # artist drew for exactly that and level 9 never places.
    holes=((6, 25), (14, 4), (22, 25), (30, 4), (38, 25), (46, 4),
           (54, 25)),
    start=(17, FLOORS[0]),              # in the doorway she came through
    gate=(16, FLOORS[-1]),              # the way out, shut, at the bottom
    entrance=(16, FLOORS[0]),           # ... and the way in, open
    # THE KEY IS ON THE SECOND FLOOR FROM THE BOTTOM, which is level
    # 9's rule read the other way up: the descent is done before the
    # gate can be opened.
    pickups=((15, FLOORS[1], "ammo"), (16, FLOORS[3], "medkit"),
             (18, FLOORS[-2], "key")),
    crystals=((30, 26, "crystal_1"), (46, 6, "crystal_0"),
              (62, 21, "crystal_0"), (62, 22, "crystal_1")),
    fixtures=((11, 14, "lamp_0"), (27, 8, "lamp_1"), (43, 17, "lamp_0"),
              (57, 7, "beam_top"), (58, 7, "beam_post"),
              (59, 7, "beam_post")),
    # A pillar is TWO tiles and not three, because its top is a
    # PLATFORM and a jump reaches 36 pixels: two rows up is 32 and
    # three is 48, which would be scenery pretending to be a perch.
    # Its BASE carries nothing - a solid tile in the middle of a floor
    # is a wall to a heroine three tiles wide (8.8's garage).
    pillars=((22, 16), (46, 20)),
    # Water lies at the bottom of a shaft. pool_0/pool_1 are PLATFORM
    # and not TA_WATER: that flag exists and NOTHING READS IT, the same
    # state TA_HAZARD was in before 8.12, so setting it would be this
    # file describing a mechanic the engine has not got.
    pools=((62, 8), (62, 9)),
)

LEVEL_11 = dict(
    level=11,
    about="the way up, by the rock",
    ladders=(),
    holes=(),
    # THE CLIMB WITHOUT A LADDER, which is what plan.md names as the
    # cave's own mechanic - "ανάβαση σε πλατφόρμες/stalagmites" - and
    # level 9 did not use. A staircase is (the floor it rises FROM, the
    # column of its foot, which way it goes): a two-tile stalagmite on
    # that floor, then a three-tile ledge, then another, every one TWO
    # ROWS above the last, and then the floor above - which is a
    # platform, so she jumps up through it. Two rows is 32 lines against
    # a jump of 36 (8.4), which is the forest's branch step exactly.
    #
    # EACH STEP STARTS IN THE COLUMN AFTER THE LAST ONE ENDS, and that
    # is BOX_SOLID_V's number again: it ORs every tile under her
    # six-byte box, so standing at the end of a step she already
    # overhangs the next one's first column, and a jump STRAIGHT UP
    # lands on it. A gap would ask for a jump with a run-up; a step
    # directly overhead would put the ledge through her head, which the
    # artist's own note ("leave 4 free tiles above a surface") rules
    # out.
    #
    # AND THE HIGHEST STEP IS EXACTLY FALL_FREE ABOVE THE FLOOR BELOW
    # IT: six rows is 96 lines, and a fall costs only the EXCESS (8.4).
    # So nothing she can miss in this level costs her a point - a miss
    # costs the height, and the climb is the skill.
    stairs=((62, 16, 1), (54, 10, -1), (46, 14, 1), (38, 6, 1),
            (30, 24, -1), (22, 8, 1), (14, 21, 1)),
    start=(6, FLOORS[-1]),              # in the doorway she came through
    gate=(8, FLOORS[0]),                # the way out, shut, at the top
    entrance=(5, FLOORS[-1]),           # ... and the way in, open
    # THE KEY IS ON THE SECOND FLOOR FROM THE TOP, level 9's rule: the
    # climb is done before the gate can be opened.
    pickups=((15, FLOORS[-2], "ammo"), (17, FLOORS[3], "medkit"),
             (18, FLOORS[1], "key")),
    crystals=((62, 25, "crystal_0"), (62, 26, "crystal_1"),
              (46, 23, "crystal_1"), (22, 5, "crystal_0")),
    fixtures=((35, 22, "lamp_0"), (19, 24, "lamp_1"),
              (43, 7, "beam_top"), (44, 7, "beam_post"),
              (45, 7, "beam_post")),
    pillars=(),
    # A drip is a stalactite with a drop forming on it, and the artist
    # drew it to land "in a pool 3-5 tiles below". Two of the three
    # cels of one drop, placed as two drops caught at different moments
    # - one over the pool on the top floor - because a tile does not
    # animate here (7.3).
    drips=((14, "drip_2"), (22, "drip_1")),
    pools=((6, 22), (6, 23)),
)

LEVEL_12 = dict(
    level=12,
    about="down to the water",
    # THE EIGHTH FLOOR IS UNDER THE WATER. The earthquake plan.md ends
    # the cave with has happened: the springs have broken, the bottom
    # of the shaft is flooded, and the gate out stands on the last dry
    # floor. So the way is DOWN again - she comes in through level
    # 11's gate at the TOP - toward the water and not away from it,
    # which is where the undersea level beyond it begins.
    floors=FLOORS[:-1],
    flood=FLOORS[-2] + 1,               # the surface, right under it
    # AND THE EARTHQUAKE BROKE THE LADDERS. Three of the six stop short
    # - three rungs, two, four - and she lets go at the end. Two rungs
    # is six rows above the floor below, 96 lines, which is FALL_FREE
    # exactly, so none of them costs a point; what they cost is that
    # the fall is measured from where the ladder ENDS, which is
    # FALL_MARK's whole rule, now with a player on it.
    ladders=((6, 23), (14, 6, 3), (22, 20), (30, 9, 2), (38, 22, 4),
             (46, 12)),
    # ... and some floors broke too: the hole beside a ladder is level
    # 10's choice, 32 points against the rungs.
    holes=((6, 25), (22, 24), (30, 4), (38, 25), (46, 4)),
    start=(9, FLOORS[0]),               # in the doorway she came through
    gate=(18, FLOORS[-2]),              # the way out, on the last dry floor
    entrance=(8, FLOORS[0]),            # ... and the way in, open
    # THE KEY IS ON THE SECOND FLOOR FROM THE BOTTOM, level 10's rule:
    # the descent is done before the gate can be opened.
    pickups=((14, FLOORS[1], "ammo"), (14, FLOORS[3], "medkit"),
             (17, FLOORS[-3], "key")),
    # The walls are cracked and water pours out of them - two falls
    # down the left wall, the lower one through the broken floor at
    # row 46, and two down the right.
    cracks=((17, 2, "crack_3"), (18, 2, "crack_4"), (41, 2, "crack_4"),
            (26, 29, "crack_3"), (27, 29, "crack_4"), (50, 29, "crack_4")),
    falls=((4, 18, 21), (4, 42, 53), (27, 27, 29), (27, 51, 53)),
    crystals=((14, 16, "crystal_0"), (38, 14, "crystal_1")),
    fixtures=((33, 16, "lamp_1"), (9, 17, "lamp_0")),
    pillars=(),
    pools=(),
)

LAYOUTS = (LEVEL_9, LEVEL_10, LEVEL_11, LEVEL_12)

TILE_FLAGS = {
    # The rock she stands on. A floating ledge is a PLATFORM - a floor
    # from above and nothing from below - so a jump can carry her up
    # through one; the floors are eight rows apart and her jump reaches
    # two, so that never skips a ladder.
    "ground": SOLID,
    "ledge_l": PLATFORM, "ledge_m": PLATFORM, "ledge_r": PLATFORM,
    "wall_l_ledge": PLATFORM, "wall_r_ledge": PLATFORM,
    "pillar_top": PLATFORM,
    "pool_0": PLATFORM, "pool_1": PLATFORM,
    # The walls, which are the edges of the map and have to stop her.
    "wall_fill": SOLID, "wall_l": SOLID, "wall_l_b": SOLID,
    "wall_r": SOLID, "wall_r_b": SOLID,
    "ceil": SOLID, "ceil_stalactites": SOLID,
    # The earthquake's cracks are wall_fill breaking open, so they are
    # wall; the waterfall, the flood's surface and the flood itself
    # carry NOTHING, because TA_WATER has no reader (the pools' note
    # above) and a flag with no reader is this file describing a
    # mechanic the engine has not got.
    "crack_1": SOLID, "crack_2": SOLID, "crack_3": SOLID, "crack_4": SOLID,
    # THE SIGNATURE. Ladder AND platform, exactly as the City's is: a
    # platform so she walks over the top rung like any other floor
    # tile, a ladder so DOWN on it steps her onto the shaft (8.8).
    "ladder": LADDER | PLATFORM,
    # AND THE GATE'S OWN TILES CARRY NOTHING, which is CLAUDE.md 8.8's
    # lesson the City already paid for: its garage was four solid tiles
    # across a pavement she is three tiles wide on, and it cut the
    # street in two. A shut door is an EK_DOOR record with EF_SOLID -
    # something she OPENS with the key - and not something the physics
    # refuses to let her stand in front of. What stops her walking
    # through it is that there is nothing behind it to walk to.
}

EK_PLAYER_START, EK_ENEMY, EK_NPC, EK_PICKUP = 0, 2, 3, 4
EK_DOOR, EK_RECEPTACLE = 6, 7
EF_ACTIVE, EF_TAKEN, EF_SOLID, EF_TOUCH = 1, 2, 4, 8
PU_KEY, PU_AMMO, PU_MEDKIT, PU_COIN, PU_IDOL, PU_BOOK = range(6)
PICKUPS = {"key": (PU_KEY, 0), "ammo": (PU_AMMO, 14), "medkit": (PU_MEDKIT, 0),
           "coin": (PU_COIN, 0), "idol": (PU_IDOL, 0), "book": (PU_BOOK, 0)}
ENT_MAX = 24

BAKED = {}                      # (overlay tile, tile under it) -> new index


def tile_names():
    """The cave's tile_table.json names every tile, which the forest's
    does not - there the table carries tags and the manifest's prose
    carries the names (8.11). So this is the table, read straight - both
    of its sheets, in the order the blob has them."""
    d = json.load(open(os.path.join(ART, "tile_table.json")))
    names = []
    for sheet, count in TILE_SHEETS:
        s = next(x for x in d["sheets"] if x["sheet"] == sheet)
        got = [t["name"] for t in s["tiles"]]
        assert len(got) == s["count"] == count, (sheet, got)
        names += got
    return names


def put_overlay(g, names, y, x, name):
    """Place an overlay, baking it onto whatever it covers."""
    over, under = names.index(name), g[y][x]
    key = (over, under)
    if key not in BAKED:
        BAKED[key] = len(names) + len(BAKED)
    g[y][x] = BAKED[key]


def build_map(names, L):
    t = {n: i for i, n in enumerate(names)}
    g = [[t["bg_a"]] * MAP_W for _ in range(MAP_H)]
    for r in range(MAP_H):
        for x in range(MAP_W):
            g[r][x] = t[("bg_a", "bg_b", "bg_c")[(r + x) % 3]]

    # ---- the walls, and their inner faces --------------------------
    for r in range(MAP_H):
        for x in range(0, WALL_L):
            g[r][x] = t["wall_fill"]
        for x in range(WALL_R + 1, MAP_W):
            g[r][x] = t["wall_fill"]
        g[r][WALL_L] = t["wall_l" if r % 2 == 0 else "wall_l_b"]
        g[r][WALL_R] = t["wall_r" if r % 2 == 0 else "wall_r_b"]

    # ---- the roof of the cave, and the rock it stands on ------------
    for x in range(WALL_L + 1, WALL_R):
        g[0][x] = t["ceil_stalactites" if x % 4 == 0 else "ceil"]
    for x in range(WALL_L + 1, WALL_R):
        g[MAP_H - 1][x] = t["ground"]

    # ---- ... or the water that has come up over it ------------------
    # The flood's body under its surface, wall to wall; the surface is
    # an overlay, placed with the other overlays below.
    if L.get("flood"):
        for r in range(L["flood"] + 1, MAP_H):
            for x in range(WALL_L + 1, WALL_R):
                g[r][x] = t["flood_1"]

    # ---- the floors: a ledge from wall to wall ---------------------
    for r in L.get("floors", FLOORS):
        g[r][WALL_L + 1] = t["wall_l_ledge"]
        g[r][WALL_R - 1] = t["wall_r_ledge"]
        for x in range(WALL_L + 2, WALL_R - 1):
            g[r][x] = t["ledge_m"]

    # ---- ... and then the holes are cut back out of them ------------
    # The cap goes on the side the floor SURVIVES: ledge_r ends a run
    # that stops at the hole and ledge_l starts the one that resumes
    # after it, which is what those two tiles are drawn for.
    for r, x0 in L["holes"]:
        for x in range(x0, x0 + HOLE_W):
            g[r][x] = t[("bg_a", "bg_b", "bg_c")[(r + x) % 3]]
        if WALL_L + 1 <= x0 - 1:
            g[r][x0 - 1] = t["ledge_r"]
        if x0 + HOLE_W <= WALL_R - 1:
            g[r][x0 + HOLE_W] = t["ledge_l"]

    # ---- the pillars, which are scenery with a perch on top ---------
    for r, x in L["pillars"]:
        g[r - 1][x] = t["pillar_base"]
        g[r - 2][x] = t["pillar_top"]

    # ---- the staircases: a stalagmite and two ledges ---------------
    # A ledge that reaches a wall grows OUT of it - wall_l_ledge and
    # wall_r_ledge are drawn for that - and the floors already end in
    # the same two tiles.
    for r, c, d in L.get("stairs", ()):
        g[r - 1][c] = t["pillar_base"]
        g[r - 2][c] = t["pillar_top"]
        for k, row in ((1, r - 4), (4, r - 6)):
            cols = sorted(c + d * (k + i) for i in range(3))
            for x in cols:
                g[row][x] = t["ledge_m"]
            g[row][cols[0]] = t["wall_l_ledge" if cols[0] == WALL_L + 1
                                else "ledge_l"]
            g[row][cols[-1]] = t["wall_r_ledge" if cols[-1] == WALL_R - 1
                                 else "ledge_r"]

    # ---- the ceiling's drips ---------------------------------------
    for x, n in L.get("drips", ()):
        g[0][x] = t[n]

    # ---- and the water that collects at the bottom ------------------
    for i, (r, x) in enumerate(L["pools"]):
        g[r][x] = t["pool_0" if i % 2 == 0 else "pool_1"]

    # ---- the walls the earthquake has cracked ------------------------
    for r, x, n in L.get("cracks", ()):
        g[r][x] = t[n]

    # ---- and the ladders between the floors -------------------------
    # A THIRD NUMBER IS A LADDER THE EARTHQUAKE BROKE: that many rungs
    # from the top and then nothing. She climbs down to the end and lets
    # go - CLIMB_LEAVE, which nothing shipped has ever reached - and the
    # fall is measured from where the ladder ENDS, because FALL_MARK
    # follows her down the rungs (8.4).
    for top, col, *rest in L["ladders"]:
        for r in range(top, top + (rest[0] if rest else 8)):
            put_overlay(g, names, r, col, "ladder")

    # ---- the water pouring out of the cracks -------------------------
    # The frame down the column is the ROCK's variant, so a waterfall
    # over bg_a is always waterfall_1, over bg_b waterfall_2: three
    # composites for every waterfall in the level rather than twelve.
    # The same for the flood's surface along its row. A tile does not
    # animate here (7.3), so which frame is where is a choice of
    # picture, and this one costs 192 bytes of bank instead of 768.
    for x, r0, r1 in L.get("falls", ()):
        for r in range(r0, r1 + 1):
            here = g[r][x]
            if here >= len(names) or TILE_FLAGS.get(names[here], 0):
                continue                        # a floor, or drawn on already
            put_overlay(g, names, r, x, f"waterfall_{(r + x) % 3 + 1}")
    if L.get("flood"):
        r = L["flood"]
        for x in range(WALL_L + 1, WALL_R):
            put_overlay(g, names, r, x, f"flood_top_{(r + x) % 3 + 1}")

    # ---- the gate, standing on its floor ----------------------------
    # 4 wide x 5 tall: the slots across the top, then four rows of
    # pillar / door / door / pillar.
    gate_col, gate_row = L["gate"]
    gate_slots(g, t, gate_col, gate_row)
    for r in range(gate_row - 4, gate_row):
        for i, n in enumerate(("gate_pillar_l", "gate_door_l",
                               "gate_door_r", "gate_pillar_r")):
            g[r][gate_col + i] = t[n]

    # ---- the panels that hint its order, set into the walls ---------
    g[gate_row - 2][WALL_L] = t["panel_sun_moon"]
    g[gate_row - 2][WALL_R] = t["panel_eye_star"]

    # ---- and the gate she came THROUGH, which is the same gate open --
    # Its two door leaves are folded back against the pillars, drawn as
    # OVERLAYS over the cave behind them: gate_open_l is 5 pixels of
    # 8 and gate_open_r 8 of 8 with 88 of 128 transparent, which is a
    # doorway you can see through and not a door.
    if L["entrance"]:
        in_col, in_row = L["entrance"]
        gate_slots(g, t, in_col, in_row)
        for r in range(in_row - 4, in_row):
            g[r][in_col] = t["gate_pillar_l"]
            g[r][in_col + 3] = t["gate_pillar_r"]
            put_overlay(g, names, r, in_col + 1, "gate_open_l")
            put_overlay(g, names, r, in_col + 2, "gate_open_r")

    # ---- and the crystals, the beams and the lamps ------------------
    for r, c, n in L["crystals"]:
        put_overlay(g, names, r - 1, c, n)      # standing ON the floor
    for r, c, n in L["fixtures"]:
        put_overlay(g, names, r, c, n)
    return g


def gate_slots(g, t, col, row):
    """The four unfilled slots across the head of a gate."""
    for i, n in enumerate(("gate_slot_sun", "gate_slot_moon",
                           "gate_slot_eye", "gate_slot_star")):
        g[row - 5][col + i] = t[n]


def entity(kind, tile_x, base_row, flags, p0=0, p1=0):
    """One record, given in TILES. The format stores world pixels with
    y at the BASE of the hitbox (CLAUDE.md 8.6)."""
    x, y = tile_x * 8, base_row * 16
    return bytes([kind, x & 255, x >> 8, y & 255, y >> 8, flags, p0, p1])


def build_entities(L):
    col, floor = L["start"]
    out = [
        # She starts a row high and falls the last 16 pixels, which is
        # free against FALL_FREE of 96 and keeps a 64-line box out of
        # the tiles (8.11).
        entity(EK_PLAYER_START, col, floor - 1, EF_ACTIVE),
    ]
    for x, row, kind in L["pickups"]:
        p0, p1 = PICKUPS[kind]
        out.append(entity(EK_PICKUP, x, row, EF_ACTIVE | EF_TOUCH, p0, p1))
    gate_col, gate_row = L["gate"]
    out.append(entity(EK_DOOR, gate_col + 1, gate_row,
                      EF_ACTIVE | EF_SOLID, 0, PU_KEY))
    return b"".join(out)


def reachable(m, names, L):
    """Every place she can stand - AND THIS ONE CLIMBS, BOTH WAYS.

    The forest's fill models a walk, a fall and a two-row jump
    (make_forest_map.py). A cave is none of those: its floors are eight
    rows apart and the only free way between them is a ladder, so a
    fill without one says the level is eight separate rooms - which is
    exactly what a cave with a misplaced ladder IS, and the reason this
    is worth writing rather than assuming.

    AND DOWN IS NOT UP RUN BACKWARDS. Level 10 descends, so the fill
    has to step off the foot of a ladder as well as onto its head; a
    model that only climbed would reach level 10's bottom through its
    HOLES and never check that a single ladder in it works.

    It stays deliberately conservative in the other direction: it
    credits her with a two-row jump and no horizontal one at all, so a
    gap she could clear at a run (8.8) is a gap this refuses.
    """
    t = {n: i for i, n in enumerate(names)}
    flag = {}
    for n, f in TILE_FLAGS.items():
        flag[t[n]] = f
    for (over, under), i in BAKED.items():
        flag[i] = flag.get(under, 0) | TILE_FLAGS.get(names[over], 0)

    def at(x, row):
        return flag.get(m[row][x], 0) if 0 <= row < MAP_H and 0 <= x < MAP_W else 0

    def on(x, row):
        return bool(at(x, row) & (SOLID | PLATFORM)) and not at(x, row - 1) & SOLID

    def under(x, row):
        for r in range(row, MAP_H):
            if on(x, r):
                return r
        return None

    col, floor = L["start"]
    seen, queue = set(), [(col, under(col, floor - 1))]
    while queue:
        x, row = queue.pop()
        if row is None or (x, row) in seen:
            continue
        seen.add((x, row))
        for nx in (x - 1, x + 1):                   # walk, or off an edge
            if on(nx, row):
                queue.append((nx, row))
            elif 0 <= nx < MAP_W and not at(nx, row) & SOLID:
                queue.append((nx, under(nx, row)))
        for nx in range(x - 3, x + 4):              # jump, at most two rows
            for nr in (row - 1, row - 2):
                if on(nx, nr):
                    queue.append((nx, nr))
        if at(x, row) & LADDER or at(x, row - 1) & LADDER:
            r = row                                 # ... and CLIMB one
            while r > 0 and at(x, r - 1) & LADDER:
                r -= 1
                if on(x, r):
                    queue.append((x, r))
            for nx in (x - 1, x + 1):               # step off at the top
                if on(nx, r):
                    queue.append((nx, r))
        if at(x, row) & LADDER:
            r = row                                 # ... or go DOWN it
            while r + 1 < MAP_H and at(x, r + 1) & LADDER:
                r += 1
            queue.append((x, under(x, r + 1)))
    return seen


def checks(m, names, ents, L):
    """What the engine would read a byte of, do nothing about and carry
    on past - refused here instead (CLAUDE.md 11 step 7)."""
    assert len(ents) // 8 <= ENT_MAX, f"{len(ents) // 8} records"
    pickups = [i for i in range(0, len(ents), 8) if ents[i] == EK_PICKUP]
    assert len(pickups) <= 16, "more pickups than ENT_BAKE has scratch tiles"
    for i in pickups:
        assert ents[i + 5] & EF_TOUCH, "a pickup with no EF_TOUCH"
        x = ents[i + 1] | ents[i + 2] << 8
        y = ents[i + 3] | ents[i + 4] << 8
        assert x % 8 == 0 and y % 16 == 0, f"a pickup off the grid at {x},{y}"

    # ONE LADDER A FLOOR, AND A COLUMN THAT MOVES. The first is what
    # makes the level survivable without spending a point on a hole;
    # the second is what makes eight floors a level rather than one
    # floor eight times.
    floors = L.get("floors", FLOORS)
    cols = [lad[1] for lad in L["ladders"]]
    assert len(set(cols)) == len(cols), f"two floors share a ladder: {cols}"
    # A ladder is keyed by the floor it hangs FROM and a staircase by
    # the floor it rises FROM, so both come down to "the upper floor of
    # the pair", and every pair has to have one.
    stairs = L.get("stairs", ())
    ways = [lad[0] for lad in L["ladders"]] + [r - 8 for r, _, _ in stairs]
    assert sorted(ways) == sorted(floors[:-1]), (
        f"a pair of floors with no way between them: {sorted(ways)}")

    # THE STAIRCASES: inside the walls, the highest step no further
    # above its floor than a fall she can take for free, and the foot
    # of each one well away from where the last one put her down.
    free = 64 + 64 // 2                 # FALL_FREE: her box and a half
    for r, c, d in stairs:
        for x in (c, c + 6 * d):
            assert WALL_L < x < WALL_R, f"a staircase through the wall at {x}"
        assert 6 * 16 <= free, "the top step is a fall that costs"
    # A BROKEN LADDER IS A FALL FROM WHERE IT ENDS, and it has to be one
    # she can take: the earthquake broke the ladders and not the level.
    for top, col, *rest in L["ladders"]:
        if rest:
            assert (8 - rest[0]) * 16 <= free, (
                f"the ladder at {col} ends {8 - rest[0]} rows above the "
                f"floor - a fall that costs")
    # ... AND WHERE THE WATER HAS COME UP, THE FLOOR ABOVE IT IS WHOLE:
    # the flood carries no attribute, so a hole in that floor would be a
    # fall out of the bottom of the map.
    if L.get("flood"):
        assert not [h for h in L["holes"] if h[0] == floors[-1]], (
            "a hole in the floor over the water")
        assert floors[-1] < L["flood"], "the water is over the last floor"
    for (_, c0, d0), (_, c1, _) in zip(stairs, stairs[1:]):
        landed = c0 + 5 * d0            # the middle of the top ledge
        assert abs(c1 - landed) >= 6, (
            f"the staircase at {c1} starts where the one at {c0} ends - "
            f"a floor she does not have to walk")

    where = reachable(m, names, L)
    for i in range(0, len(ents), 8):
        if ents[i] not in (EK_PICKUP, EK_DOOR, EK_RECEPTACLE):
            continue
        x = (ents[i + 1] | ents[i + 2] << 8) // 8
        row = (ents[i + 3] | ents[i + 4] << 8) // 16
        assert (x, row) in where, (
            f"a kind-{ents[i]} record at tile {x}, row {row} is somewhere "
            f"she cannot stand - the ladders are the only way up")

    # ... AND EVERY FLOOR HAS TO BE REACHED, which is the cave's own
    # version of the same question: a ladder in the wrong column is a
    # level that stops at the floor below it and looks perfectly fine.
    for r in floors:
        assert any(row == r for _, row in where), f"floor at row {r} is cut off"

    # ... AND EVERY LADDER HAS TO BE STOOD ON. A hole between where she
    # lands and the ladder is a floor she can only leave by falling -
    # which plays, and costs 32 points a floor, and is not what the map
    # says. reachable() credits no horizontal jump, so this is exactly
    # the question "could she walk to it".
    for r, c, *_ in L["ladders"]:
        assert (c, r) in where, (
            f"the ladder at tile {c}, row {r} is somewhere she cannot "
            f"walk to - a hole is between her and it")

    # ... AND EVERY STEP HAS TO BE STOOD ON, which is the same question
    # a staircase asks: a step she cannot reach is scenery, and the one
    # above it is then a step nobody can reach either.
    for r, c, d in stairs:
        steps = [(c, r - 2)] + [(c + d * (k + i), row)
                                for k, row in ((1, r - 4), (4, r - 6))
                                for i in range(3)]
        for x, row in steps:
            assert (x, row) in where, (
                f"the step at tile {x}, row {row} is out of her reach")
    return len(pickups), len(where)


def main():
    names = tile_names()

    # ALL THE MAPS FIRST, INTO ONE BAKED. The blob and the flag table
    # are the ENVIRONMENT's, so a pair placed by any level has to come
    # out at one index - and they are built in level order so that each
    # level added appends its new pairs after everybody else's.
    built = []
    for L in LAYOUTS:
        g = build_map(names, L)
        ents = build_entities(L)
        pickups, standable = checks(g, names, ents, L)
        built.append((L, g, ents, pickups, standable))

    extra_bytes, extra_names, remap, flat = bake_overlays(
        ART, SHEETS, names, BAKED)
    for _, g, _, _, _ in built:
        for r in range(MAP_H):
            for x in range(MAP_W):
                g[r][x] = remap.get(g[r][x], g[r][x])

    full = names + extra_names
    flags = bytes(TILE_FLAGS.get(n, 0) for n in full)
    # A BAKED TILE INHERITS WHAT IS UNDERNEATH IT, because what the cell
    # DOES is what it did before something was drawn on it (7.3) - and
    # the ladder is the exception that proves it, since the ladder is
    # the overlay and the climb is its own.
    flags = bytearray(flags)
    for (over, under), i in BAKED.items():
        j = remap.get(i, i)
        if j >= len(names):
            flags[j] = (TILE_FLAGS.get(names[under], 0)
                        | TILE_FLAGS.get(names[over], 0))
    flags = bytes(flags) + bytes(256 - len(flags))

    # THE BLOB IS TRUNCATED TO THE TILESET'S OWN TILES FIRST, so running
    # this twice bakes the same pairs rather than stacking a second
    # copy on the first - make_city_map.py's own rule, and the same
    # reason: build.sh runs this AFTER build_levels.py exported the
    # blob and BEFORE level_banks.py lays it into a bank.
    tiles = os.path.join(BUILD, "levels", "level3_cave", "cavetiles.bin")
    base = open(tiles, "rb").read()[:64 * len(names)]
    assert len(base) == 64 * len(names), "the tile blob is short"
    assert len(extra_bytes) == 64 * len(extra_names)
    open(tiles, "wb").write(base + extra_bytes)
    # AND ITS ZX0 GOES WITH IT. build_levels.py packed the blob as it
    # exported it, which was before this appended anything; the stale
    # stream is what tools/test_spans.py depacks on the emulator, and
    # for the City it reported "wrong bytes" rather than "stale".
    from build_levels import zx0
    zx0(tiles)
    print(f"-> cavetiles.bin   {len(names)} tiles + {len(extra_names)} baked "
          f"= {len(base) + len(extra_bytes)} bytes, shared by "
          f"{len(LAYOUTS)} levels")

    out = os.path.join(BUILD, "tileflags_level3_cave.bin")
    open(out, "wb").write(flags[:256])
    print(f"-> tileflags_level3_cave.bin  {len(full)} tiles, "
          f"{sum(1 for f in flags[:len(full)] if f)} with anything on")

    for L, g, ents, pickups, standable in built:
        m = bytes(b for row in g for b in row)
        lvl = pack(level_id=L["level"], tileset_id=TILESET_ID,
                   width=MAP_W, height=MAP_H, map_bytes=m, entities=ents)
        out = os.path.join(BUILD, f"level_{L['level']}.lvl")
        open(out, "wb").write(lvl)
        back = read(lvl)
        assert back["map"] == m and back["entities"] == len(ents) // 8
        print(f"-> level_{L['level']}.lvl    {len(lvl)} bytes: "
              f"{back['width']}x{back['height']}, {back['entities']} entities "
              f"({pickups} pickups), tileset {TILESET_ID} - {L['about']}")
        print(f"   {len(L.get('floors', FLOORS))} floors 8 rows apart, "
              f"{len(L['ladders'])} "
              f"ladders, {len(L.get('stairs', ()))} staircases, "
              f"{len(L['holes'])} holes, a 4x5 gate, "
              f"{standable} standable cells")
    return 0


if __name__ == "__main__":
    sys.exit(main())
