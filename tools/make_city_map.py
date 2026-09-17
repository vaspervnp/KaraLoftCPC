#!/usr/bin/env python3
"""The City map, over the DRAWN 8x16 tiles.

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


def tile_flags(names):
    """One byte a tile, in the artist's frame order."""
    return bytes(TILE_FLAGS.get(n, 0) for n in names)


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


def entity(kind, tile_x, base_row, flags, p0=0, p1=0):
    """One record. Positions are given in TILES and converted here, so
    the numbers above stay readable against the map."""
    x = tile_x * 8                      # 8 pixels a tile
    y = base_row * 16                   # the row's TOP is the base it sits on
    return bytes([kind, x & 255, x >> 8, y & 255, y >> 8, flags, p0, p1])


def build_entities(path):
    e = [
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
            g[ROW_ROOFLINE][x] = T["ac_unit"]
    for x in range(9, MAP_W, 16):
        if free(x):
            g[ROW_ROOFLINE][x] = T["chimney"]
    for x in range(13, MAP_W, 32):
        if free(x):
            g[ROW_ROOFLINE][x] = T["antenna"]

    # ---- the water tank: a 2 wide x 3 tall group, tank_RC row-major --
    for x0 in range(20, MAP_W, 48):
        for r in range(3):
            for c in range(2):
                y = ROW_ROOFLINE - 2 + r
                if free(x0 + c):
                    g[y][x0 + c] = T[f"tank_{r}{c}"]

    # ---- a lamp, hung on the wall above the pavement -----------------
    # NOT standing IN the pavement row, which is where it used to be:
    # lamp_pole has no attributes, so a pole in the sidewalk row was a
    # hole she fell through on her way along the street.
    for x in range(6, MAP_W, 24):
        if free(x):
            g[ROW_PAVEMENT - 2][x] = T["lamp_top"]
            g[ROW_PAVEMENT - 1][x] = T["lamp_pole"]

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

    blob = bytes(b for row in g for b in row)
    assert len(blob) == MAP_W * MAP_H
    assert max(blob) < len(names), "a tile index ran past the sheet"
    out = os.path.join(ROOT, "build", "city_map.bin")
    open(out, "wb").write(blob)
    flags = tile_flags(names)
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


if __name__ == "__main__":
    main()
