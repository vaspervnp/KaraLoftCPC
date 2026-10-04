#!/usr/bin/env python3
"""The City's maps, over the DRAWN 8x16 tiles: levels 1, 2 and 3.

Everything below down to LEVEL 2's own header is level 1, and it comes
out byte for byte what it was before level 2 existed - that is the
check that the second map did not disturb the first. The two SHARE the
bake, because a tileset belongs to the environment (CLAUDE.md 8.13), and
level 2 is drawn to need no composite level 1 does not already have.

This replaces make_placeholder_level.py's stand-in sheet: the tiles are
now the artist's, exported by build_levels.py into the level's own bank,
and only the MAP is generated here. It is still scaffolding - a designed
level comes from the editor (docs/editor.md) once the format is read by
the engine - but it is scaffolding built out of the real art, so what is
on screen is what the game will look like.

TILE NUMBERS ARE THE SHEET'S FRAME ORDER, which the manifest spells out
and build/levels/level1_city/citytiles_frames.json confirms. They are
read from that sidecar rather than hard-coded, so a re-export with a
different frame count cannot quietly shift the map by one tile.

THE COLUMN COMES FROM THE ARTIST'S OWN MOCKUPS, not from guesswork.
assets/sprites/level1_city/mockup_city.png and mockup_city_street.png
are two screens of this level composed by hand, and reading them back
tile by tile gives the row order below:

    sky_stars / sky_mid / sky_low          the night
    far_tower|far_block|far_step           the skyline's tops
    far_fill ...                           its black mass, and the props
    roof_l roof_m ... roof_r               THE ROOF - she walks on its top
    brick / brick_win_lit / brick_win_dark the wall, all the way down
    sidewalk                               THE STREET - and its top too

Two things fall out of that and both were wrong here before:

  * `brick_top` IS NOT USED. It appears in neither mockup. It draws a
    black band and then a pale ledge five lines in, and put directly
    under the roof it reads as a SECOND floor 16 pixels below the one
    she is standing on - which is exactly the place a play-test report
    (errors/wrongwalkplace.png) circled as "she walks in the wrong
    spot". She was always on the roof; the picture had two roofs. The
    wall under a roof you walk on is plain brick and windows.
  * The walkable surface is the TOP LINE of its tile, and in this art
    that line is the bright pen-1 cap - roof_m's and sidewalk's alike.
    The mockup stands her on it with a one-line gap under her boots.

THE ROOFTOP IS ONE CONTINUOUS RUN AT ONE HEIGHT. A tile is 16 pixels
tall and she walks 2 a frame, so any step up in the roof line is a wall
that stops her dead - and a player who cannot walk is a camera that
cannot scroll, which makes every scrolling test vacuous WITHOUT failing
it. The variety is in the skyline above, the windows below and the props
on the roof, none of which is in her way.

EXCEPT FOR ONE GAP, AND IT IS PUT WHERE THE WALKING TESTS CANNOT REACH
IT. She has a `drop` animation - a fall she did not choose, as against
the `jump` arc she asked for (CLAUDE.md 8.4) - and nothing in a level
with an unbroken roof can ever play it. So two buildings stand apart:
ROOF_GAP is three tiles of open air from the roof's row down to the
pavement, and walking off its edge is a 128-pixel fall to the street.

Three tiles, because BOX_SOLID_V ORs the attributes of every tile under
her box and her box is 6 bytes against a 4-byte tile - it spans two of
them, three when it is not aligned - so a two-tile gap has positions she
would stand across. Three has seven byte positions where every tile
under her is open, and she walks into one of them whether she is moving
1 byte a frame or 2.

And it is at tile 95 because the longest walk any suite makes along this
roof reaches tile 83 - measured, not estimated, and asserted below. A
gap in front of those walks would turn every one of them from a test of
the scroll into a test of the fall, silently.

AND NOW THERE IS A WAY DOWN. The ladders run from the roof's own row to
the last wall row, so their top tile is one she can stand on (it is
TA_CLIMB + TA_PLATFORM in collide.asm) and pressing DOWN on it takes
her onto the ladder. The street is 128 pixels below the roof and the
display is 192 lines of a 256-line world, so it cannot be on screen at
the same time as the roof: reaching it IS a vertical scroll.
"""
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")

MAP_W, MAP_H = 128, 16          # both powers of two: the map wraps with AND
                                # 128 tiles of 8 pixels = 1024 world pixels,
                                # the same world the 64x16 map of 16x16 tiles
                                # covered, at twice the horizontal resolution

ROW_SKY_TOP  = 0
ROW_SKY_MID  = 1
ROW_SKY_LOW  = 2
ROW_FAR_TOP  = 3                # the far skyline's tops
ROW_DRONE    = 4                # a drone hovers here: its box is 44..64 and
                                # her muzzle is at world y 54, so she can hit
                                # it and it can hit her
ROW_ROOFLINE = 5                # props stand here, on top of the roof
ROW_ROOF     = 6                # <- the walkable surface, world y = 96
ROW_WALL_TOP = 7                # the wall: brick and windows, no ledge
ROW_PAVEMENT = 14               # <- the street surface, world y = 224
ROW_STREET   = 15               # the road itself, under the kerb

# The drop, in pixels, and what the display can show of it at once.
ROOF_Y   = ROW_ROOF * 16        # 96
STREET_Y = ROW_PAVEMENT * 16    # 224
SCREEN_LINES = 192              # R6 = 24 character rows (CLAUDE.md 8.2)
WORLD_LINES  = 16 * 16          # the map's own height, and Y wraps in a byte


# ---------------------------------------------------------------------
# WHAT EACH TILE DOES, which is not what it looks like and not how it is
# drawn. docs/editor.md 9.1 ships this as tileflags_<level>.bin, one
# byte a tile, and src/collide.asm takes the format's own bit order -
# so this dict IS the engine's table and there is no translation
# anywhere between them. Anything not named here is scenery.
#
# The three rules that are load-bearing and were each paid for once:
#
#   * THE BUILDING'S FACE IS NOT A WALL. brick, its windows and the
#     garage in the middle of it have nothing: her box is three tiles
#     wide and the ladder's shaft is one, so a solid facade is a place
#     she arrives inside and can never walk out of (CLAUDE.md 8.8).
#   * A LADDER IS A FLOOR AS WELL AS A SHAFT. Its top tile is in the
#     roof's own row, so she has to be able to stand on it before she
#     can step onto it: Platform is what a one-way floor is.
#   * THE ROOF PROPS ARE SCENERY. A solid prop on the rooftop is a wall
#     she cannot walk past, which stops the camera and makes every
#     scrolling test vacuous WITHOUT failing it.
SOLID, PLATFORM, HAZARD, LADDER, WATER, QUICKSAND, DEADLY = (
    1, 2, 4, 8, 16, 32, 64)

TILE_FLAGS = {
    "concrete": SOLID,
    "roof_l": SOLID, "roof_m": SOLID, "roof_r": SOLID,
    "ladder": LADDER | PLATFORM,
    "sidewalk": SOLID, "curb": SOLID, "street": SOLID, "street_line": SOLID,
    "crate": SOLID,
}


# ---------------------------------------------------------------------
# AN OVERLAY TILE IS BAKED ONTO WHAT IT COVERS, at build time, and the
# map gets the composited tile. CLAUDE.md 7.3 has the problem: 34 tiles
# across three levels are drawn with pen 0 meaning TRANSPARENT, and
# every blitter in tilemap.asm is a plain copy - so a lamp on a brick
# wall paints an 8x32 black rectangle out of it.
#
# THE ALTERNATIVE WAS MEASURED AND IT IS THE FRAME THAT REFUSES IT. A
# masked cell is 2-3x a copy (7.3) and DRAW_COLUMN spends 669 T on each
# of the 24 it paints every character step, so a column with two
# overlays in it is +1,300 to +2,700 T against the 3,548 the frame has
# spare (9) - and level 3's cave has overlay tiles running down a whole
# wall. Baking costs 64 bytes of bank per distinct PAIR and nothing per
# frame, which is the same trade ENT_BAKE already makes for the pickups
# (8.6).
#
# Only the pairs that need it are baked, and which those are is
# MEASURED rather than reasoned: a pair whose composite comes out byte
# for byte the overlay is dropped, because there was nothing under it
# to lose. Of level 1's eleven, exactly one is - and 7.3's old claim
# that the roof props over `far_fill` were "correct by accident" was
# wrong: far_fill carries 4 lit pixels of its 128 and the props were
# painting them black.
BAKED = {}                      # (overlay tile, tile under it) -> new index


def put_overlay(g, names, y, x, name):
    """Place an overlay tile, baking it onto whatever it covers."""
    over, under = names.index(name), g[y][x]
    key = (over, under)
    if key not in BAKED:
        BAKED[key] = len(names) + len(BAKED)
    g[y][x] = BAKED[key]


def tile_flags(names):
    """One byte a tile, in the artist's frame order."""
    return bytes(TILE_FLAGS.get(n, 0) for n in names)


# THE BAKE MOVED TO tools/tilebake.py, because the City stopped being
# the only level with overlays in it. It is the same code and the same
# bytes - citytiles.bin, city_baked.json and the tile flags all come
# out byte for byte what they were, which is what says the lift was a
# lift. `name_of` goes with it, since the report below reads a baked
# tile's name out of the same two lists the baker builds.
from tilebake import bake_overlays, name_of          # noqa: E402

CITY_ART = os.path.join(ROOT, "assets", "sprites", "level1_city")
CITY_SHEET = "city_tiles_cpc_mode0_sheet"


def tile_names():
    """Frame order, straight out of the manifest's description field."""
    man = json.load(open(os.path.join(
        ROOT, "assets", "sprites", "level1_city", "manifest.json")))
    sheet = next(s for s in man["sheets"] if s["name"] == "city_tiles")
    order = sheet["description"].split("frame order:", 1)[1]
    order = order.split(".", 1)[0]
    names = [n.strip() for n in order.split(",")]
    return {n: i for i, n in enumerate(names)}, names


# ---------------------------------------------------------------------
# The level's entities, in the EIGHT-BYTE record docs/editor.md 9.2
# fixes and src/entity.asm reads: kind, x u16, y u16, flags, p0, p1.
#
# Scaffolding again - the editor will write these - but written in the
# final format, against the map above, so the engine's half of the
# agreement is exercised before a web application is built against it.
# ---------------------------------------------------------------------
EK_ENEMY, EK_PICKUP, EK_DOOR, EK_NPC, EK_RECEPTACLE = 2, 4, 6, 3, 7
EN_AGENT, EN_DRONE = 0, 1
SCREEN_TILES = 20               # 160 pixels of play area, 8 to a tile
EF_ACTIVE, EF_TAKEN, EF_SOLID, EF_TOUCH = 1, 2, 4, 8
PU_KEY, PU_AMMO, PU_MEDKIT, PU_COIN, PU_IDOL, PU_BOOK = range(6)
ENT_MAX = 24


def entity_px(kind, x, y, flags, p0=0, p1=0):
    """One record, in the world pixels the FORMAT stores."""
    return bytes([kind, x & 255, x >> 8, y & 255, y >> 8, flags, p0, p1])


def entity(kind, tile_x, base_row, flags, p0=0, p1=0):
    """One record. Positions are given in TILES and converted here, so
    the numbers above stay readable against the map."""
    return entity_px(kind, tile_x * 8, base_row * 16, flags, p0, p1)


EK_PLAYER_START = 0
# WHERE SHE STARTS, AND IT IS EXACTLY WHERE SHE ALREADY DID. KARA_WX and
# KARA_WY were assembler initialisers - 43 and 16 - applied once, when
# the bootstrap relocates the core image, and never again; PLAYER_SPAWN
# reads this record instead, so a second level can start her somewhere
# else and a death has somewhere to put her back to.
#
# The record is in the units the FORMAT uses and hers are not: x is
# world PIXELS against her byte column, and y is the BASE of the hitbox
# against her box's top. 43 * 2 = 86, and 16 + KARA_BOX_H = 80.
#
# NOT ON THE TILE GRID, AND IT DOES NOT HAVE TO BE. Only a pickup does,
# because ENT_BAKE stamps it into the cell its top-left falls in; she is
# drawn by the span blitter at a byte column. 86 is ten tiles and six
# pixels, and moving her to a whole tile would be moving her.
#
# AND SHE IS IN THE AIR ON PURPOSE. Base 80 is one line short of the
# roof at 96, so she falls the last 16 pixels onto it - free, against
# FALL_FREE of 96 - which is what the initialisers did and what stops a
# 64-line box starting INSIDE the tiles, where the landing snaps her a
# whole row too low and BOX_SOLID_H then refuses every step.
KARA_START_X, KARA_START_BASE = 86, 80


def build_entities(path):
    e = [
        entity_px(EK_PLAYER_START, KARA_START_X, KARA_START_BASE, EF_ACTIVE),
        # Pickups stand ON the roof, so their base is the roof's top edge.
        entity(EK_PICKUP, 24, ROW_ROOF, EF_ACTIVE | EF_TOUCH, PU_KEY, 0),
        entity(EK_PICKUP, 44, ROW_ROOF, EF_ACTIVE | EF_TOUCH, PU_AMMO, 14),
        entity(EK_PICKUP, 64, ROW_ROOF, EF_ACTIVE | EF_TOUCH, PU_MEDKIT, 0),
        # ... and two more DOWN ON THE STREET, which is the only reason to
        # go and look at it: a demo you can reach and need not is a demo
        # nobody scrolls to.
        entity(EK_PICKUP, 26, ROW_PAVEMENT, EF_ACTIVE | EF_TOUCH, PU_COIN, 5),
        entity(EK_PICKUP, 62, ROW_PAVEMENT, EF_ACTIVE | EF_TOUCH, PU_AMMO, 14),
        # The garage, down at street level: 4 tiles wide, 5 tall, and its
        # base is the pavement. Solid until the key opens it.
        entity(EK_DOOR, 30, ROW_PAVEMENT, EF_ACTIVE | EF_SOLID, 0, PU_KEY),
        # An informant on the roof, three coins for a hint.
        entity(EK_NPC, 104, ROW_ROOF, EF_ACTIVE, 3, 1),
        # Drones, hovering a row above the roof. p0 is WHICH character
        # and p1 the patrol half-width in tiles - see src/enemy.asm.
        #
        # THEY ARE FORTY TILES APART AND THE SCREEN IS TWENTY, which is
        # the level's half of "one enemy on screen at a time": the
        # engine draws only the first it finds in view, so two that
        # could be seen together would mean one of them silently
        # vanishing. The assert below is what keeps that honest as the
        # map is edited.
        #
        # THE ROW IS HER MUZZLE'S, not a guess: she stands with her
        # feet on row 6, so KARA_WY is 36 and the firing cel's own
        # spawn point puts the shot on world y 54. A drone has to be
        # drawn across that line or every round goes under it.
        entity(EK_ENEMY, 36, ROW_DRONE, EF_ACTIVE, EN_DRONE, 4),
        entity(EK_ENEMY, 76, ROW_DRONE, EF_ACTIVE, EN_DRONE, 4),
        entity(EK_ENEMY, 116, ROW_DRONE, EF_ACTIVE, EN_DRONE, 6),
    ]
    # No two enemies, at either end of their beats, can share a screen.
    beats = []
    for r in e:
        if r[0] != EK_ENEMY:
            continue
        x = (r[1] | r[2] << 8) // 8         # tiles
        beats.append((x - r[7], x + r[7]))
    beats.sort()
    for (_, a_hi), (b_lo, _) in zip(beats, beats[1:]):
        assert b_lo - a_hi > SCREEN_TILES, (
            f"two enemies can be on screen at once: one reaches tile {a_hi}, "
            f"the next starts at {b_lo}, and the screen is {SCREEN_TILES} "
            f"tiles wide")
    blob = b"".join(e) + bytes(8 * (ENT_MAX - len(e)))
    assert len(blob) == ENT_MAX * 8
    open(path, "wb").write(blob)
    return len(e)


# Where the ladders are. Each one runs from the ROOF's own row - so its
# top tile is the one she stands on and DOWN takes her onto it - to the
# last row of wall above the pavement.
LADDER_X = list(range(11, MAP_W, 23))

# The gap between two buildings, and the ONE place `drop` can be played.
# See the header for why it is three tiles and why it is this far along.
ROOF_GAP = list(range(95, 98))
# The furthest along this roof any suite walks her, measured by holding
# the joystick right for the 290 frames tools/test_enemies.py holds it
# and reading KARA_WX back: byte 332, which is tile 83. The margin below
# is what stops a gap being put in front of a test that is measuring
# something else.
ROOF_WALK_REACH = 83


def build_level_1(T, names):
    """Level 1's map, its overlays recorded in BAKED and not yet
    composited - the bake is done once, for both maps, in main()."""
    g = [[T["void"]] * MAP_W for _ in range(MAP_H)]

    for x in range(MAP_W):
        # ---- sky, three bands, stars thinning out near the horizon ----
        g[ROW_SKY_TOP][x] = T["sky_stars"] if (x * 7) % 11 == 0 else T["void"]
        g[ROW_SKY_MID][x] = T["sky_mid"]
        g[ROW_SKY_LOW][x] = T["sky_low"]

        # ---- the far skyline: tops over fill ------------------------
        g[ROW_FAR_TOP][x] = (T["far_tower"], T["far_block"], T["far_step"],
                             T["far_block"])[(x // 3) % 4]
        for y in range(ROW_FAR_TOP + 1, ROW_ROOF):
            g[y][x] = T["far_fill"]

        # ---- the roof she walks on, one height, all the way ---------
        # roof_l / roof_m... / roof_r reads as a row of separate
        # buildings standing shoulder to shoulder, which is variety that
        # costs her nothing: the SURFACE is flat whatever tile draws it.
        p = x % 16
        g[ROW_ROOF][x] = (T["roof_l"] if p == 0 else
                          T["roof_r"] if p == 15 else T["roof_m"])

        # ---- the wall below, with lit and dark windows --------------
        # NO brick_top. See the header: its pale ledge five lines down
        # is a second roof line, and it is the one the play-test report
        # pointed at.
        for y in range(ROW_WALL_TOP, ROW_PAVEMENT):
            lit = ((x // 2 + y) % 3 == 0)
            g[y][x] = (T["brick_win_lit"] if lit and (x + y) % 2 == 0 else
                       T["brick_win_dark"] if lit else T["brick"])

        # ---- street level ------------------------------------------
        g[ROW_PAVEMENT][x] = T["sidewalk"]
        g[ROW_STREET][x] = T["street_line"] if (x % 8) < 2 else T["street"]

    # ---- ladders: roof row down to the last row of wall -------------
    # THE TOP TILE IS IN THE ROOF'S OWN ROW, which is what makes the
    # ladder reachable: collide.asm gives it TA_CLIMB + TA_PLATFORM, so
    # she walks over it like any other roof tile and DOWN steps onto it.
    # A ladder that started one row lower would be a thing she could
    # only fall onto.
    for x in LADDER_X:
        for y in range(ROW_ROOF, ROW_PAVEMENT):
            g[y][x] = T["ladder"]

    # ---- the gap between two buildings ------------------------------
    # Open air from the roof's own row to the row above the pavement, so
    # what you see through it is the black the skyline stands in and what
    # is under it is the street. far_fill has no attributes, which is the
    # whole point: BOX_SOLID_V finds nothing to stand on and she falls.
    # The buildings either side get their proper end tiles, because the
    # x % 16 run above knows nothing about the hole.
    for y in range(ROW_ROOF, ROW_PAVEMENT):
        for x in ROOF_GAP:
            g[y][x] = T["far_fill"]
    g[ROW_ROOF][ROOF_GAP[0] - 1] = T["roof_r"]
    g[ROW_ROOF][ROOF_GAP[-1] + 1] = T["roof_l"]

    # ---- props on the roof, standing on ROW_ROOFLINE ----------------
    # Decoration only: TILE_ATTR gives them no attributes, so she walks
    # straight through them. A solid prop on the runway is the step that
    # stops the camera.
    def free(x):
        return x < MAP_W and x not in LADDER_X and x not in ROOF_GAP

    for x in range(5, MAP_W, 16):
        if free(x):
            put_overlay(g, names, ROW_ROOFLINE, x, "ac_unit")
    for x in range(9, MAP_W, 16):
        if free(x):
            put_overlay(g, names, ROW_ROOFLINE, x, "chimney")
    for x in range(13, MAP_W, 32):
        if free(x):
            put_overlay(g, names, ROW_ROOFLINE, x, "antenna")

    # ---- the water tank: a 2 wide x 3 tall group, tank_RC row-major --
    # ITS TOP ROW IS THE ONE THAT SHOWED. The tank stands two rows into
    # the skyline, so tank_00 and tank_01 are over far_tower and
    # far_block rather than over the black fill, and their transparent
    # pixels used to punch a hole in the towers behind them.
    for x0 in range(20, MAP_W, 48):
        for r in range(3):
            for c in range(2):
                y = ROW_ROOFLINE - 2 + r
                if free(x0 + c):
                    put_overlay(g, names, y, x0 + c, f"tank_{r}{c}")

    # ---- a lamp, hung on the wall above the pavement -----------------
    # NOT standing IN the pavement row, which is where it used to be:
    # lamp_pole has no attributes, so a pole in the sidewalk row was a
    # hole she fell through on her way along the street.
    for x in range(6, MAP_W, 24):
        if free(x):
            put_overlay(g, names, ROW_PAVEMENT - 2, x, "lamp_top")
            put_overlay(g, names, ROW_PAVEMENT - 1, x, "lamp_pole")

    # ---- the garage: 4 wide x 5 tall, closed, down at street level ---
    # manifest: row0 jamb_l sign_p lock_(red|green) jamb_r; rows 1-3 two
    # shutters between the jambs; row4 shutter_bottom.
    for i, x0 in enumerate(range(30, MAP_W - 4, 60)):
        top = ROW_PAVEMENT - 5
        lock = T["lock_red"] if i == 0 else T["lock_green"]
        g[top][x0:x0 + 4] = [T["jamb_l"], T["sign_p"], lock, T["jamb_r"]]
        for r in range(1, 4):
            g[top + r][x0:x0 + 4] = [T["jamb_l"], T["shutter"],
                                     T["shutter"], T["jamb_r"]]
        g[top + 4][x0:x0 + 4] = [T["jamb_l"], T["shutter_bottom"],
                                 T["shutter_bottom"], T["jamb_r"]]
        assert not any(x in LADDER_X for x in range(x0, x0 + 4)), \
            f"a ladder runs through the garage at tile {x0}"

    # ---- a crate or two on the pavement ------------------------------
    for x in range(18, MAP_W, 29):
        if free(x) and g[ROW_PAVEMENT - 1][x] == T["brick"]:
            g[ROW_PAVEMENT - 1][x] = T["crate"]

    # ---- the gap is a level decision and these are its terms ---------
    assert len(ROOF_GAP) >= 3, (
        "a gap of two tiles has positions where her 6-byte box still "
        "straddles solid roof - see BOX_SOLID_V in src/collide.asm")
    assert ROOF_GAP[0] > ROOF_WALK_REACH + 8, (
        f"the gap starts at tile {ROOF_GAP[0]} and the longest walk along "
        f"this roof reaches tile {ROOF_WALK_REACH}: a hole in front of "
        f"those walks turns a scroll test into a fall test without failing")
    assert not set(ROOF_GAP) & set(LADDER_X), "a ladder runs into the gap"
    assert all(g[ROW_ROOFLINE][x] == T["far_fill"] for x in ROOF_GAP), \
        "a roof prop is standing over the gap"   # far_fill is the bare row
    assert all(g[ROW_PAVEMENT][x] == T["sidewalk"] for x in ROOF_GAP), \
        "there is no pavement under the gap to land on"
    for x in ROOF_GAP:
        for y in range(ROW_ROOF, ROW_PAVEMENT):
            assert g[y][x] == T["far_fill"], (
                f"tile ({x},{y}) is in the gap and is not open air")

    return g


from make_level import pack, read                    # noqa: E402

# =====================================================================
# LEVEL 2: ACROSS THE ROOFTOPS
#
# Level 1 ends at a garage its key opens, and LEVEL_GOTO goes to
# LEVEL_CUR + 1 (CLAUDE.md 8.1) - so level 2 is the map that door has
# pointed at since the day it was placed. Same environment: one sector
# and no art. AND IT OPENS ON A GARAGE DRAWN OPEN, which is the
# manifest's own recipe - "open rows 1-3 void x2, row 4 open_ramp x2" -
# for two tiles nothing had ever placed. It is the cave's open gate
# (8.13) one environment back: she comes out of the door she went in by.
#
# AND IT IS THE CITY'S OWN MECHANIC, WHICH LEVEL 1 SHOWED ONCE. plan.md
# names it - "άλματα σε ταράτσες" - and level 1 has one gap, out of the
# way of everything it asks her to do. Here the key is on the last of
# five roofs and every gap between them is a jump she HAS to make:
#
#   * THE STREET IS CUT INTO PITS. A building's face is background
#     (8.8), so the street runs under every roof and a player who fell
#     into the first gap could walk to the last building's ladder. Three
#     crates high is 48 lines against a jump that clears 21 - and that
#     would reach 36 if a crate were a platform - so a barricade of
#     them is a wall, and each pit has ONE ladder, on the building she
#     jumped FROM. A miss costs the fall and the climb back - never the
#     jump itself.
#   * THE KEY'S ROOF HAS NO LADDER AT ALL, so the last jump is the only
#     way onto it - and its roof is FALL_FREE above the street, so the
#     way back down costs nothing.
#
# WHAT A JUMP CAN BE IS MEASURED, NOT CHOSEN. RUN_JUMPS is the take-off
# window in game frames, by the gap's width and the far roof's row less
# the near one's, at each of the two phases a run's two-byte stride can
# meet the lip in - measured on this level, on the machine, by pressing
# UP at every byte column from sixteen before each gap to ten past it
# (tools/test_city.py does it again). Four things fell out of that, and
# the first two are why the level is the shape it is:
#
#   * EVERY GAP IS THREE WIDE, AND A WALK MAKES EVERY ONE OF THEM. It
#     was not so the day the level was drawn: the jump was -15 and 21
#     lines, the downhill gaps were four wide, and a walk made the first
#     gap and no other. A play-test on Caprice32 could not make the
#     second or the third at all, and the answer was both halves - a
#     jump one game frame longer (P_JUMP -17, 28 lines, CLAUDE.md 8.14)
#     and the downhill gaps a tile narrower. Measured, the same gaps on
#     the old jump were 6/7, 5/6, 3/4 and 5/6 frames at a run and 3, 0,
#     0 and 0 at a walk.
#   * A THREE-TILE GAP DOWNHILL CAN BE CROSSED WITHOUT A PRESS: running
#     off its edge lands her on the far roof at one stride phase in two.
#     That is why it was four wide, and it is now a thing the level
#     gives away - RUN_OFF says so and the suite measures it.
#   * The window depends on the stride's phase by one frame: an odd byte
#     column meets the lip a byte earlier.
#   * The jump UP is still the tightest, by a frame at a run.
#
# The five roofs use three of them, and in an order:
#
#   G1   7 -> 7, three wide    level: level 1's own gap, 7 or 8 frames
#   G2   7 -> 8, three wide    downhill: 8 or 9, and 5 at a walk
#   ...  two steps up a row each to the tallest roof, and a drop off it
#   G3   8 -> 7, three wide    UP a row: 6 or 7, and 3 at a walk
#   G4   7 -> 8, three wide    as G2, onto the key's roof
#
# EVERY NUMBER ON THIS LEVEL IS A COMPOSITE LEVEL 1 ALREADY BAKED. The
# props stand on far_fill, the lamps go on columns whose wall is the
# same brick and window as level 1's lamps, and the one water tank
# stands where the skyline behind it and the air-conditioner under it
# are the pairs level 1's three tanks were baked from. So the City's
# tile blob, its flag table and its bake record do not change by a
# byte - which is what the editor's golden suite and test_painter.py
# hold them to - and main() asserts it rather than hoping.
# =====================================================================
RUN_JUMPS = {(3, 0): (7, 8), (3, 1): (8, 9), (3, -1): (6, 7)}
# ... and walking, AT LEAST: a walk's window measured a frame wider on a
# machine that had driven to the gap than on one that had just arrived,
# where a run's did not move at all, so for a walk the table is a floor.
WALK_JUMPS = {(3, 0): 3, (3, 1): 5, (3, -1): 3}
RUN_OFF = {(3, 1)}          # the shapes a run off the edge crosses at one
                            # stride phase of the two, with no press
# HOW HIGH SHE GOES IS 28 LINES, and every roof here is SOLID, so that
# is the number. .jump stores P_JUMP and falls into .airborne, which
# adds P_GRAVITY BEFORE it moves her: the -17 is never a step and the
# arc is 13 + 9 + 5 + 1, measured on the machine as 128 -> 115 -> 106 ->
# 101 -> 100. Forty-three is what she reaches onto a PLATFORM, because
# feet that fall INTO a platform's row are snapped onto its top
# (28 + 15); a solid roof she cannot move over until her box has
# cleared it, so a step of two rows is a wall - which is what the first
# version of this level found, standing under a tall roof it had put
# in her way, when the jump was 21.
JUMP_RISE = 28
FALL_FREE = 96              # KARA_BOX_H * 1.5, and inclusive (8.4)

L2_BUILDINGS = (            # (first column, last column, roof row)
    (0, 21, 7),             # the one she comes out of
    (25, 47, 7),
    (51, 53, 8),            # four that stand shoulder to shoulder: two
    (54, 55, 7),            # steps of a row each up to the tallest -
    (56, 61, 6),            # which is as much as a solid roof allows -
    (62, 73, 8),            # and a drop of two rows off its far side
    (77, 100, 7),           # the way out is at its foot
    (104, 127, 8),          # the key's - and not a ladder on it
)
L2_LADDERS = (19, 44, 71, 97)       # one on each building before a gap
L2_BARRICADES = (30, 56, 83)        # three crates high, at street level
L2_GARAGE_IN = 6                    # the one she came out of, drawn OPEN
L2_GARAGE_OUT = 88                  # the way out, shut, under roof four
L2_CRATES = ((2, 2), (3, 1))        # (column, crates high): the coin's
L2_LAMPS = (12, 36, 54, 66, 78, 96, 108, 120)
L2_PROPS = ((4, "ac_unit"), (13, "chimney"), (16, "antenna"),
            (28, "chimney"), (33, "ac_unit"), (40, "antenna"),
            (52, "chimney"), (57, "ac_unit"),
            (65, "ac_unit"), (68, "antenna"),
            (80, "chimney"), (86, "ac_unit"), (93, "chimney"),
            (107, "antenna"), (116, "ac_unit"), (122, "chimney"))
L2_TANKS = (56,)                    # on the tall roof, over (57)'s ac_unit

# WHERE SHE STARTS: just out of the garage, a row above the pavement so
# she falls the last 16 lines onto it - level 1's own reason (above).
L2_START = (84, 208)                # world pixels: x, and the box's base
L2_PICKUPS = (                      # (column, base row, PU_*, p1)
    (2, 12, PU_COIN, 5),            # on the crates, by the garage
    (60, 6, PU_AMMO, 14),           # on the tall roof, which is on the way
    (76, 14, PU_MEDKIT, 0),         # in the pit under the hardest jump
    (112, 8, PU_KEY, 0),            # on the last roof
)
L2_DRONES = ((36, 4), (88, 3), (117, 3))   # (column, patrol half-width)


def l2_roof(x):
    """The roof row over column x, or None where there is no building."""
    for x0, x1, r in L2_BUILDINGS:
        if x0 <= x <= x1:
            return r
    return None


def l2_building(x):
    for i, (x0, x1, _) in enumerate(L2_BUILDINGS):
        if x0 <= x <= x1:
            return i
    return None


def l2_gaps():
    """(first column, width, near roof, far roof), west to east."""
    out = []
    for (_, a1, ra), (b0, _, rb) in zip(L2_BUILDINGS, L2_BUILDINGS[1:]):
        if b0 > a1 + 1:
            out.append((a1 + 1, b0 - a1 - 1, ra, rb))
    return out


def l2_pit(x):
    """Which stretch of street column x is in: the barricades cut it."""
    return sum(1 for b in L2_BARRICADES if b < x)


def miss_cost(near):
    """What a missed jump off a roof at row `near` costs her: the fall
    is measured from the APEX (FALL_MARK, 8.4) down to the pavement."""
    return max(0, (ROW_PAVEMENT - near) * 16 + JUMP_RISE - FALL_FREE)


def build_city(L, T, names):
    """A City map out of one LAYOUT - level 2's or level 3's - with its
    overlays recorded in the SAME BAKED as level 1's. Everything here is
    the City's and nothing is a level's: which buildings, at what height,
    with their ladders, barricades, garages, crates and props, is L."""
    def roof_of(x):
        for x0, x1, r in L["buildings"]:
            if x0 <= x <= x1:
                return r
        return None

    g = [[T["void"]] * MAP_W for _ in range(MAP_H)]
    for x in range(MAP_W):
        g[ROW_SKY_TOP][x] = T["sky_stars"] if (x * 7) % 11 == 0 else T["void"]
        g[ROW_SKY_MID][x] = T["sky_mid"]
        g[ROW_SKY_LOW][x] = T["sky_low"]
        g[ROW_FAR_TOP][x] = (T["far_tower"], T["far_block"], T["far_step"],
                             T["far_block"])[(x // 3) % 4]
        roof = roof_of(x)
        # The skyline's black down to the roof - or, in a gap, all the
        # way to the pavement, which is level 1's own gap exactly.
        for y in range(ROW_FAR_TOP + 1,
                       ROW_PAVEMENT if roof is None else roof):
            g[y][x] = T["far_fill"]
        if roof is not None:
            g[roof][x] = T["roof_m"]
            # THE SAME WALL AS LEVEL 1'S, cell for cell, because it is
            # the same function of the column and the row - which is
            # what lets a lamp here be a composite level 1 already has.
            for y in range(roof + 1, ROW_PAVEMENT):
                lit = ((x // 2 + y) % 3 == 0)
                g[y][x] = (T["brick_win_lit"] if lit and (x + y) % 2 == 0
                           else T["brick_win_dark"] if lit else T["brick"])
        g[ROW_PAVEMENT][x] = T["sidewalk"]
        g[ROW_STREET][x] = T["street_line"] if (x % 8) < 2 else T["street"]
    for x0, x1, r in L["buildings"]:
        g[r][x0], g[r][x1] = T["roof_l"], T["roof_r"]

    for x in L["ladders"]:
        for y in range(roof_of(x), ROW_PAVEMENT):
            g[y][x] = T["ladder"]

    # ---- the garages: 4 wide x 5 tall, on the pavement ---------------
    for x0, shut in L["garages"]:
        top = ROW_PAVEMENT - 5
        mid = T["shutter"] if shut else T["void"]
        low = T["shutter_bottom"] if shut else T["open_ramp"]
        g[top][x0:x0 + 4] = [T["jamb_l"], T["sign_p"],
                             T["lock_red"] if shut else T["lock_green"],
                             T["jamb_r"]]
        for r in range(1, 4):
            g[top + r][x0:x0 + 4] = [T["jamb_l"], mid, mid, T["jamb_r"]]
        g[top + 4][x0:x0 + 4] = [T["jamb_l"], low, low, T["jamb_r"]]

    # ---- crates: the barricades, the street's steps, the roofs' -----
    for x in L["barricades"]:
        for y in range(ROW_PAVEMENT - 3, ROW_PAVEMENT):
            g[y][x] = T["crate"]
    for x, high in L["crates"]:
        for y in range(ROW_PAVEMENT - high, ROW_PAVEMENT):
            g[y][x] = T["crate"]
    for x in L.get("roof_crates", ()):
        g[roof_of(x) - 1][x] = T["crate"]   # opaque: no pair to bake

    # ---- the overlays: props, the tank over its ac_unit, the lamps ---
    for x, name in L["props"]:
        put_overlay(g, names, roof_of(x) - 1, x, name)
    for x0 in L["tanks"]:
        r = roof_of(x0)
        for rr in range(3):
            for c in range(2):
                put_overlay(g, names, r - 3 + rr, x0 + c, f"tank_{rr}{c}")
    for x in L["lamps"]:
        put_overlay(g, names, ROW_PAVEMENT - 2, x, "lamp_top")
        put_overlay(g, names, ROW_PAVEMENT - 1, x, "lamp_pole")
    return g


L2 = dict(buildings=L2_BUILDINGS, ladders=L2_LADDERS,
          barricades=L2_BARRICADES,
          garages=((L2_GARAGE_IN, False), (L2_GARAGE_OUT, True)),
          crates=L2_CRATES, props=L2_PROPS, tanks=L2_TANKS, lamps=L2_LAMPS)


def build_level_2(T, names):
    """Level 2's map, its overlays recorded in the SAME BAKED as level 1's."""
    return build_city(L2, T, names)


def build_entities_2():
    e = [entity_px(EK_PLAYER_START, *L2_START, EF_ACTIVE)]
    for x, row, kind, amount in L2_PICKUPS:
        e.append(entity(EK_PICKUP, x, row, EF_ACTIVE | EF_TOUCH, kind, amount))
    # THE DOOR, which is level 1's garage record: p1 is the pickup that
    # opens it, and EF_SOLID is what the format calls a shut door.
    e.append(entity(EK_DOOR, L2_GARAGE_OUT, ROW_PAVEMENT,
                    EF_ACTIVE | EF_SOLID, 0, PU_KEY))
    # Drones two rows above the roof under them, which is where level 1
    # puts its own for the reason written there: her muzzle's line.
    for x, half in L2_DRONES:
        e.append(entity(EK_ENEMY, x, l2_roof(x) - 2, EF_ACTIVE, EN_DRONE, half))
    return b"".join(e)


def l2_checks(g, T, ents):
    """The level's terms, each one a way it could load, look right and
    be impossible - or be possible the wrong way."""
    gaps = l2_gaps()
    for x0, x1, r in L2_BUILDINGS:
        # Six is level 1's roof, and a jump's apex 28 lines above it is
        # as high as anything in this game takes her; nine keeps her
        # middle inside CAM_BOT, so every roof is framed at WORLD_CR 0.
        assert 6 <= r <= 9, f"the roof at {x0}..{x1} is on row {r}"
    for (_, a1, ra), (b0, _, rb) in zip(L2_BUILDINGS, L2_BUILDINGS[1:]):
        if b0 == a1 + 1:                # shoulder to shoulder
            assert (ra - rb) * 16 < JUMP_RISE, (
                f"the roof at {b0} is {ra - rb} rows above the one before "
                f"it, and a jump clears {JUMP_RISE} lines of SOLID roof")
            assert (rb - ra) * 16 <= FALL_FREE, f"the drop at {b0} costs"
    for x, w, near, far in gaps:
        assert (w, far - near) in RUN_JUMPS, (
            f"the gap at {x} is {w} wide from row {near} to row {far}, "
            f"which no measured run-jump reaches")
        # A BARRICADE SHE CAN LAND ON IS ONE SHE CAN WALK OVER. Under a
        # roof she can drift while she falls - measured over every
        # take-off at every gap, a missed jump comes down no further
        # than the far roof's first column - so they stand well clear
        # of every gap's two edges.
        for b in L2_BARRICADES:
            assert b <= x - 6 or b >= x + w + 5, (
                f"the barricade at {b} is within six tiles of the gap at {x}")
    for b in L2_BARRICADES:
        assert l2_roof(b) is not None, f"the barricade at {b} is in a gap"
        assert all(g[y][b] == T["crate"]
                   for y in range(ROW_PAVEMENT - 3, ROW_PAVEMENT))
        assert 3 * 16 > JUMP_RISE + 15  # a wall even if crates were platforms
    # EVERY PIT HAS ONE WAY OUT, AND IT IS BACK UP TO WHERE SHE JUMPED.
    for x, w, near, far in gaps:
        pit = l2_pit(x)
        assert all(l2_pit(c) == pit for c in range(x, x + w)), \
            f"a barricade stands in the gap at {x}"
        ups = [c for c in L2_LADDERS if l2_pit(c) == pit]
        near_b = l2_building(x - 1)
        assert any(l2_building(c) == near_b for c in ups), (
            f"nothing in the pit under the gap at {x} leads back up to "
            f"the roof she jumped from")
        assert all(l2_building(c) <= near_b for c in ups), (
            f"the pit under the gap at {x} has a ladder onto a roof PAST "
            f"it, so the jump is one she never has to make")
    last = len(L2_BUILDINGS) - 1
    assert not any(l2_building(c) == last for c in L2_LADDERS), \
        "the key's roof has a ladder, so the last jump is optional"
    for c in L2_LADDERS:
        assert l2_roof(c) is not None and g[l2_roof(c)][c] == T["ladder"]
        assert all(g[y][c] == T["ladder"]
                   for y in range(l2_roof(c), ROW_PAVEMENT))
    # The coin's crates: a step of one and then of two, each a row up.
    hs = sorted(h for _, h in L2_CRATES)
    assert hs[0] * 16 < JUMP_RISE and all(
        (b - a) * 16 < JUMP_RISE for a, b in zip(hs, hs[1:]))
    # Where things are, and which stretch of street they are on.
    key = next(p for p in L2_PICKUPS if p[2] == PU_KEY)
    assert l2_building(key[0]) == last and key[1] == l2_roof(key[0])
    assert l2_pit(L2_START[0] // 8) == 0 and l2_pit(L2_LADDERS[0]) == 0
    assert l2_pit(L2_GARAGE_OUT) == l2_pit(gaps[-1][0]), (
        "the way out is not in the pit she lands in off the key's roof")
    assert (ROW_PAVEMENT - L2_BUILDINGS[-1][2]) * 16 <= FALL_FREE, (
        "walking off the key's roof costs her something")
    for x, row, kind, _ in L2_PICKUPS:
        assert row in (ROW_PAVEMENT, l2_roof(x),
                       ROW_PAVEMENT - dict(L2_CRATES).get(x, 0)), \
            f"pickup {kind} at {x} is standing on nothing"
        assert x not in L2_LADDERS and x not in dict(L2_PROPS), \
            f"pickup {kind} at {x} shares its cell with a ladder or a prop"
    for x, name in L2_PROPS:
        assert l2_roof(x) is not None and x not in L2_LADDERS, \
            f"{name} at {x} is over a gap or a ladder"
    for x in L2_LAMPS:
        assert l2_roof(x) is not None and x not in L2_LADDERS
        assert not any(b == x for b in L2_BARRICADES)
        assert not any(x0 <= x < x0 + 4
                       for x0 in (L2_GARAGE_IN, L2_GARAGE_OUT))
    # One enemy a screen - level 1's own rule, the same assert.
    beats = sorted((x - h, x + h) for x, h in L2_DRONES)
    for (_, a_hi), (b_lo, _) in zip(beats, beats[1:]):
        assert b_lo - a_hi > SCREEN_TILES, (
            f"two drones can be on screen at once: {a_hi} and {b_lo}")
    assert len(ents) % 8 == 0 and len(ents) // 8 <= ENT_MAX
    return gaps


# =====================================================================
# LEVEL 3: DOWN TO THE STREET AND UP AGAIN
#
# Level 2's garage leads here, and level 3 opens on it drawn OPEN, as
# level 2 opened on level 1's. Level 2 was the rooftops and every way on
# was a jump; this one is the street, and every way on is a CLIMB and a
# way DOWN, which is the other half of what the City's art and the
# engine already carry:
#
#   * THE STREET IS CUT UNDER EVERY BUILDING. A barricade three crates
#     high stands on the pavement under each roof but the last - 48
#     lines against a jump of 28, a wall even to a reach of 43 - so the
#     only way past one is the building's ladder, on its near side, and
#     the roof over the top of it.
#   * BETWEEN THE BUILDINGS IS OPEN STREET, EIGHT TILES OF IT, which no
#     jump crosses (measured in tools/test_city3.py: every take-off at
#     either phase of a run comes down in the plaza). So the way off a
#     roof is DOWN, and there are two: walk off the edge, which is the
#     roof's height against FALL_FREE at a point a pixel - 16 off a
#     row-7 roof, 32 off a row-6 one - or DOWN AT THE LIP, hang off the
#     ledge and let go, which is 70 lines at the most and free (8.8).
#     The ledge has been in the game since a play-test asked for it and
#     no level has needed it; here every roof is a choice between the
#     two, the City's version of the cave's ladder-or-hole (8.13).
#   * WALKING OFF EVERY EDGE IS SURVIVABLE: 16 + 32 + 32 = 80 of her 100,
#     with a medkit in the second plaza, so a player who never finds the
#     ledge is punished and not stopped.
#   * THE KEY IS ON THE LAST ROOF AND THE LAST ROOF HAS A LADDER, and the
#     way out is a garage under it, past the last barricade. Every
#     barricade is one-way - nothing leads back over one - so the key
#     goes where a miss can always be walked back to; a key on a roof
#     she has left behind would be a level she cannot finish.
#
# And not one composite level 1 did not already bake: props over
# far_fill, lamps on columns 0 mod 6 under a roof, the tank where level
# 2's stands, and the roof crates are opaque. main() asserts it.
# =====================================================================
L3_BUILDINGS = (            # (first column, last column, roof row)
    (0, 25, 7),             # the one she comes out of
    (34, 59, 6),
    (68, 93, 6),
    (102, 127, 8),          # the key's, with the way out under it
)
L3_LADDERS = (19, 37, 71, 105)      # each on the side she arrives from
L3_BARRICADES = (23, 44, 78)        # under every roof but the last
L3_GARAGE_IN = 6                    # level 2's way out, drawn OPEN
L3_GARAGE_OUT = 112                 # past the last barricade, shut
L3_CRATES = ((2, 2), (3, 1), (30, 1))   # the coin's two steps; one in
                                        # the first plaza, with the clip
L3_ROOF_CRATES = (41, 76)           # one to jump on each tall roof
L3_LAMPS = (12, 48, 84, 108, 120)
L3_PROPS = ((4, "ac_unit"), (13, "chimney"), (16, "antenna"),
            (39, "chimney"), (47, "ac_unit"), (53, "antenna"),
            (57, "ac_unit"),
            (73, "antenna"), (82, "chimney"), (88, "ac_unit"),
            (110, "chimney"), (116, "antenna"), (121, "ac_unit"))
L3_TANKS = (56,)                    # on the first tall roof, as level 2's
L3_START = (84, 208)                # out of the garage, a row up
L3_PICKUPS = (                      # (column, base row, PU_*, p1)
    (2, 12, PU_COIN, 5),            # on the crates, by the garage
    (30, 13, PU_AMMO, 14),          # on the first plaza's crate
    (64, 14, PU_MEDKIT, 0),         # in the second plaza
    (98, 14, PU_COIN, 5),           # in the third
    (124, 8, PU_KEY, 0),            # at the far end of the last roof
)
L3_DRONES = ((50, 4), (84, 4), (118, 3))    # (column, patrol half-width)
L3 = dict(buildings=L3_BUILDINGS, ladders=L3_LADDERS,
          barricades=L3_BARRICADES,
          garages=((L3_GARAGE_IN, False), (L3_GARAGE_OUT, True)),
          crates=L3_CRATES, roof_crates=L3_ROOF_CRATES, props=L3_PROPS,
          tanks=L3_TANKS, lamps=L3_LAMPS)


def l3_roof(x):
    for x0, x1, r in L3_BUILDINGS:
        if x0 <= x <= x1:
            return r
    return None


def l3_building(x):
    for i, (x0, x1, _) in enumerate(L3_BUILDINGS):
        if x0 <= x <= x1:
            return i
    return None


def l3_pit(x):
    """Which stretch of street column x is in: the barricades cut it."""
    return sum(1 for b in L3_BARRICADES if b < x)


def walk_off_cost(roof):
    """Walking off a roof at row `roof` onto the pavement: no apex, just
    the drop, against FALL_FREE at a point a pixel (8.4)."""
    return max(0, (ROW_PAVEMENT - roof) * 16 - FALL_FREE)


def build_level_3(T, names):
    return build_city(L3, T, names)


def build_entities_3():
    e = [entity_px(EK_PLAYER_START, *L3_START, EF_ACTIVE)]
    for x, row, kind, amount in L3_PICKUPS:
        e.append(entity(EK_PICKUP, x, row, EF_ACTIVE | EF_TOUCH, kind, amount))
    e.append(entity(EK_DOOR, L3_GARAGE_OUT, ROW_PAVEMENT,
                    EF_ACTIVE | EF_SOLID, 0, PU_KEY))
    for x, half in L3_DRONES:
        e.append(entity(EK_ENEMY, x, l3_roof(x) - 2, EF_ACTIVE, EN_DRONE, half))
    return b"".join(e)


def l3_checks(g, T, ents):
    """Level 3's terms - each one a way it could load, look right and be
    impossible, or be possible without the climb it is made of."""
    B = L3_BUILDINGS
    for x0, x1, r in B:
        assert 6 <= r <= 9, f"the roof at {x0}..{x1} is on row {r}"
    plazas = []
    for (_, a1, _), (b0, _, _) in zip(B, B[1:]):
        # Eight is twice the four-tile gap no press cleared on the old
        # jump; the suite measures that nothing clears it on this one.
        assert b0 - a1 - 1 >= 8, f"the plaza after {a1} is a jump"
        plazas.append((a1 + 1, b0 - a1 - 1))
    last = len(B) - 1
    # ONE LADDER A BUILDING, ON THE SIDE SHE ARRIVES FROM, AND EVERY
    # BARRICADE BETWEEN ITS BUILDING'S LADDER AND ITS FAR EDGE.
    for i, (x0, x1, r) in enumerate(B):
        ups = [c for c in L3_LADDERS if l3_building(c) == i]
        assert len(ups) == 1, f"building {i} has ladders at {ups}"
        bars = [b for b in L3_BARRICADES if l3_building(b) == i]
        if i == last:
            assert not bars, "the way out is behind a barricade"
            continue
        assert len(bars) == 1 and ups[0] < bars[0] < x1, (
            f"building {i}: ladder {ups} and barricade {bars} - the street "
            f"under it is not cut between the two")
        assert all(g[y][bars[0]] == T["crate"]
                   for y in range(ROW_PAVEMENT - 3, ROW_PAVEMENT))
        assert r < ROW_PAVEMENT - 3 - 3, "the roof is down on the crates"
        assert l3_pit(ups[0]) == l3_pit(x0 - 1 if i else 0), (
            f"building {i}'s ladder is not on the street she arrives by")
    assert 3 * 16 > JUMP_RISE + 15         # a wall even to a platform's reach
    for c in L3_LADDERS:
        assert all(g[y][c] == T["ladder"]
                   for y in range(l3_roof(c), ROW_PAVEMENT))
    # WALKING OFF EVERY EDGE IS SURVIVABLE, and the ledge is the point.
    costs = [walk_off_cost(r) for _, _, r in B[:-1]]
    assert sum(costs) < 100, f"walking off every roof costs {costs}"
    # The start, the doors and the key.
    assert l3_pit(L3_START[0] // 8) == 0 and l3_pit(L3_GARAGE_IN) == 0
    assert l3_building(L3_GARAGE_OUT) == last
    assert l3_pit(L3_GARAGE_OUT) == len(L3_BARRICADES)
    assert l3_pit(L3_LADDERS[-1]) == len(L3_BARRICADES)
    key = next(p for p in L3_PICKUPS if p[2] == PU_KEY)
    assert l3_building(key[0]) == last and key[1] == l3_roof(key[0])
    # The coin's crates: a step of one and then of two, each a row up;
    # and every crate on the street or a roof is ONE she can jump.
    hs = sorted(h for x, h in L3_CRATES if x < L3_GARAGE_IN)
    assert hs[0] * 16 < JUMP_RISE and all(
        (b - a) * 16 < JUMP_RISE for a, b in zip(hs, hs[1:]))
    assert all(h * 16 < JUMP_RISE for x, h in L3_CRATES if x > L3_GARAGE_IN)
    for x in L3_ROOF_CRATES:
        assert l3_roof(x) is not None and x not in L3_LADDERS
    for x, row, kind, _ in L3_PICKUPS:
        assert row in (ROW_PAVEMENT, l3_roof(x),
                       ROW_PAVEMENT - dict(L3_CRATES).get(x, 0)), \
            f"pickup {kind} at {x} is standing on nothing"
        assert x not in L3_LADDERS and x not in dict(L3_PROPS) \
            and x not in L3_ROOF_CRATES and x not in L3_BARRICADES, \
            f"pickup {kind} at {x} shares its cell"
    for x, name in L3_PROPS:
        assert l3_roof(x) is not None and x not in L3_LADDERS \
            and x not in L3_ROOF_CRATES, f"{name} at {x}"
        assert all(x not in (x0, x1) for x0, x1, _ in B), \
            f"{name} at {x} is on a roof's lip"
    for x in L3_LAMPS:
        assert l3_roof(x) is not None and x % 6 == 0
        assert x not in L3_LADDERS and x not in L3_BARRICADES
        assert not any(x0 <= x < x0 + 4
                       for x0 in (L3_GARAGE_IN, L3_GARAGE_OUT))
    beats = sorted((x - h, x + h) for x, h in L3_DRONES)
    for (_, a_hi), (b_lo, _) in zip(beats, beats[1:]):
        assert b_lo - a_hi > SCREEN_TILES, (
            f"two drones can be on screen at once: {a_hi} and {b_lo}")
    assert len(ents) % 8 == 0 and len(ents) // 8 <= ENT_MAX
    return plazas, costs


def main():
    T, names = tile_names()
    side = os.path.join(ROOT, "build", "levels", "level1_city",
                        "citytiles_frames.json")
    exported = json.load(open(side))
    assert exported["tiles"] and exported["box"] == [4, 16], exported["box"]
    n_exported = 1 + max(t["to"] for t in exported["tags"])
    if n_exported != len(names):
        raise SystemExit(f"the sheet exports {n_exported} tiles but the "
                         f"manifest names {len(names)} - one of them moved")

    g = build_level_1(T, names)
    # ... AND LEVEL 2, INTO THE SAME BAKED. A tileset is the
    # environment's (CLAUDE.md 8.13): a pair either level places has to
    # take one index in both, so both maps are built before anything is
    # composited - and level 2 is drawn to add no pair at all.
    level_1_pairs = dict(BAKED)
    g2 = build_level_2(T, names)
    ents2 = build_entities_2()
    gaps2 = l2_checks(g2, T, ents2)
    g3 = build_level_3(T, names)
    ents3 = build_entities_3()
    plazas3, costs3 = l3_checks(g3, T, ents3)
    assert BAKED == level_1_pairs, (
        f"level 2 or 3 placed overlay pairs level 1 never baked: "
        f"{sorted(set(BAKED) - set(level_1_pairs))}. They would bake after "
        f"level 1's and level 1 would not move - but citytiles.bin, its flag "
        f"table and city_baked.json would, and the editor's golden suite and "
        f"tools/test_painter.py hold all three to level 1's bake byte for "
        f"byte. Move the prop, or change those with it.")
    # ---- the overlays, composited onto what they cover --------------
    # The map holds the BAKED tile, so every blitter stays a plain copy
    # and the frame pays nothing. See the note by put_overlay().
    extra_bytes, extra_names, remap, flat = bake_overlays(
        CITY_ART, CITY_SHEET, names, BAKED)
    for row in g + g2 + g3:             # the provisional ids become the
        for x in range(MAP_W):          # real ones, or the overlay again
            if row[x] in remap:
                row[x] = remap[row[x]]
    tiles_bin = os.path.join(ROOT, "build", "levels", "level1_city",
                             "citytiles.bin")
    # A TILE'S SIZE COMES FROM THE SIDECAR AND THE BLOB IS TRUNCATED TO
    # THE SHEET'S OWN TILES FIRST, so running this twice bakes the same
    # eleven pairs rather than stacking a second copy on the first.
    per = exported["box"][0] * exported["box"][1]
    base = open(tiles_bin, "rb").read()[:per * len(names)]
    assert len(base) == per * len(names), "the tile blob is short"
    if len(extra_names):
        assert len(extra_bytes) == per * len(extra_names)
        open(tiles_bin, "wb").write(base + extra_bytes)
    # AND ITS ZX0 GOES WITH IT. build_levels.py packed the blob as it
    # exported it, which was before this appended anything; the stale
    # stream is what tools/test_spans.py depacks on the emulator, and
    # it reported "wrong bytes" rather than "stale".
    from build_levels import zx0
    zx0(tiles_bin)
    names = names + extra_names
    # WHAT EACH BAKED TILE STANDS ON, AFTER THE REMAP. The `under` a
    # pair was recorded with may itself be a provisional id - the water
    # tank's top corner sits on an air-conditioning unit that is a bake
    # of its own - so it has to be resolved the same way the map cells
    # were, or the flags are read out of a tile index that no longer
    # exists. Sorted, because resolving a chain needs the tile under a
    # tile to have been resolved first, and a bake's index is always
    # higher than both of the tiles it was made from.
    under_of = {remap[index]: remap.get(under, under)
                for (_, under), index in sorted(BAKED.items(),
                                                key=lambda kv: kv[1])
                if remap[index] >= len(names) - len(extra_names)}
    print(f"-> citytiles.bin   {len(base)} + {len(extra_bytes)} bytes: "
          f"{len(extra_names)} baked of {len(BAKED)} pairs placed, "
          f"{len(flat)} of them already right over black")
    for i in range(len(names) - len(extra_names), len(names)):
        print(f"     {i:3d}  {names[i]}")
    # WHAT WAS BAKED, WRITTEN DOWN. tools/test_format.py composites each
    # pair again from the artist's sheet and compares - which it cannot
    # do from an empty dict, and a test that iterates nothing passes.
    json.dump([{"index": remap[i], "over": o, "under": remap.get(u, u),
                "name": names[remap[i]], "baked": remap[i] != o}
               for (o, u), i in sorted(BAKED.items(), key=lambda kv: kv[1])],
              open(os.path.join(ROOT, "build", "city_baked.json"), "w"),
              indent=1)

    blob = bytes(b for row in g for b in row)
    assert len(blob) == MAP_W * MAP_H
    assert max(blob) < len(names), "a tile index ran past the sheet"
    out = os.path.join(ROOT, "build", "city_map.bin")
    open(out, "wb").write(blob)
    # A BAKED TILE DOES WHAT THE ONE UNDERNEATH DOES. What she stands
    # on, walks into or climbs is the background; the overlay is the
    # decoration that was drawn over it.
    flags = bytearray(tile_flags(names))
    for index, under in under_of.items():
        flags[index] = flags[under]
    flags = bytes(flags)
    open(os.path.join(ROOT, "build", "tileflags_level1_city.bin"),
         "wb").write(flags)   # one byte a tile, and the loader clears
                              # the rest of the 256 the engine indexes
    print(f"-> tileflags_level1_city.bin  {len(flags)} tiles, "
          f"{sum(1 for f in flags if f)} of them with anything on")
    n = build_entities(os.path.join(ROOT, "build", "city_entities.bin"))
    print(f"-> city_entities.bin  {n} of {ENT_MAX} slots used, "
          f"{ENT_MAX * 8} bytes")
    print(f"-> city_map.bin    {MAP_W}x{MAP_H} = {len(blob)} bytes, "
          f"{len(set(blob))} distinct tiles of {len(names)}")
    print(f"   roof at map row {ROW_ROOF} = world y {ROOF_Y}, one height "
          f"across all {MAP_W} columns and open at {len(ROOF_GAP)} of them")
    print(f"   street at map row {ROW_PAVEMENT} = world y {STREET_Y}, "
          f"{STREET_Y - ROOF_Y} pixels below it")
    print(f"   ladders at tiles {LADDER_X}, rows {ROW_ROOF}-{ROW_PAVEMENT - 1}")
    print(f"   a {len(ROOF_GAP)}-tile gap in the roof at tiles {ROOF_GAP} - "
          f"{ROOF_GAP[0] - ROOF_WALK_REACH} tiles past the longest walk")
    # THE WHOLE POINT OF PUTTING THE STREET DOWN THERE. The view is 192
    # lines of a 256-line world, so its top can only sit in 0..64. With
    # it at 0 the roof is framed - she stands on screen line 96, inside
    # the camera's band - and the street's surface at 224 is off the
    # bottom of the display. So the street cannot be seen, never mind
    # stood on, until the view scrolls, and putting her on it drives the
    # view the whole 64 pixels it has.
    assert STREET_Y >= SCREEN_LINES, (
        f"the street's surface is at world y {STREET_Y}, which the "
        f"{SCREEN_LINES}-line display shows without scrolling at all")
    assert STREET_Y + 16 <= WORLD_LINES, "the street falls out of the world"
    assert ROOF_Y + 96 <= STREET_Y, "the climb is too short to be worth a ladder"

    # ---- level 2, straight into the format: there is no second
    # city_map.bin, because make_level.py's two inputs are level 1's
    # golden intermediates (tools/test_format.py reads them) and level 2
    # has no reason to grow a pair of its own.
    blob2 = bytes(b for row in g2 for b in row)
    assert len(blob2) == MAP_W * MAP_H and max(blob2) < len(names)
    lvl2 = pack(level_id=2, tileset_id=1, width=MAP_W, height=MAP_H,
                map_bytes=blob2, entities=ents2)
    open(os.path.join(ROOT, "build", "level_2.lvl"), "wb").write(lvl2)
    back = read(lvl2)
    assert back["map"] == blob2 and back["entities"] == len(ents2) // 8
    print(f"-> level_2.lvl     {len(lvl2)} bytes: {MAP_W}x{MAP_H}, "
          f"{back['entities']} entities, tileset 1, and not one overlay "
          f"pair level 1 had not already baked")
    print(f"   {len(L2_BUILDINGS)} roofs at rows "
          f"{', '.join(str(r) for _, _, r in L2_BUILDINGS)}; ladders at "
          f"{list(L2_LADDERS)}; the street cut at {list(L2_BARRICADES)}")
    for x, w, near, far in gaps2:
        print(f"   gap at {x:3d}, {w} wide, row {near} -> {far}: a run-jump "
              f"with {'/'.join(map(str, RUN_JUMPS[w, far - near]))} game "
              f"frames to take off in, "
              f"and a miss costs {miss_cost(near)}")

    # ---- level 3, the same way ---------------------------------------
    blob3 = bytes(b for row in g3 for b in row)
    assert len(blob3) == MAP_W * MAP_H and max(blob3) < len(names)
    lvl3 = pack(level_id=3, tileset_id=1, width=MAP_W, height=MAP_H,
                map_bytes=blob3, entities=ents3)
    open(os.path.join(ROOT, "build", "level_3.lvl"), "wb").write(lvl3)
    back = read(lvl3)
    assert back["map"] == blob3 and back["entities"] == len(ents3) // 8
    print(f"-> level_3.lvl     {len(lvl3)} bytes: {MAP_W}x{MAP_H}, "
          f"{back['entities']} entities, tileset 1, and not one new pair")
    print(f"   {len(L3_BUILDINGS)} roofs at rows "
          f"{', '.join(str(r) for _, _, r in L3_BUILDINGS)}; ladders at "
          f"{list(L3_LADDERS)}; the street cut at {list(L3_BARRICADES)}")
    for (x, w), c in zip(plazas3, costs3):
        print(f"   plaza at {x:3d}, {w} wide: walking off the roof before it "
              f"costs {c}, the ledge nothing")


if __name__ == "__main__":
    main()
