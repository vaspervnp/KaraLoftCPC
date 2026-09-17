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


def name_of(names, extra, index):
    """A tile's name, baked or not, for the report and the flags."""
    return names[index] if index < len(names) else extra[index - len(names)]


def bake_overlays(names):
    """Composite every (overlay, background) pair into a new tile.

    Returns (extra tile bytes, extra names). The pixels come from the
    artist's own sheet, quantised against src/palette.asm exactly as
    tools/aseprite2spans.py does it, and go out in the same
    COLUMN-MAJOR order the tile blitters read (see encode_tiles there).
    An overlay's pen 0 is the transparent one (CLAUDE.md 7.3); every
    other pen wins over what is underneath.
    """
    import cpclib
    from aseprite2spans import game_palette
    art = os.path.join(ROOT, "assets", "sprites", "level1_city")
    sheet = Image.open(os.path.join(
        art, "city_tiles_cpc_mode0_sheet.png")).convert("RGBA")
    js = json.load(open(os.path.join(art, "city_tiles_cpc_mode0_sheet.json")))
    frames = js["frames"]
    if isinstance(frames, dict):
        frames = [frames[k] for k in frames]
    palette = game_palette(os.path.join(ROOT, "src", "palette.asm"))

    w, h = frames[0]["frame"]["w"], frames[0]["frame"]["h"]
    cache = {}

    def pens_of(i):
        """An original tile's pens, or a baked one's - AND A BAKED ONE
        CAN BE UNDER ANOTHER. The lamp's pole hangs under its head and
        the tank's cells sit on top of the roof props, so a pair can
        name a tile that is itself a pair. Every baked index is higher
        than the two it was made from, so resolving in index order
        terminates."""
        if i in cache:
            return cache[i]
        if i < len(names):
            b = frames[i]["frame"]
            crop = sheet.crop((b["x"], b["y"],
                               b["x"] + b["w"], b["y"] + b["h"]))
            cache[i] = cpclib.quantise(crop, palette)
        else:
            over, under = next(k for k, v in BAKED.items() if v == i)
            top, bottom = pens_of(over), pens_of(under)
            cache[i] = [[top[y][x] or bottom[y][x] for x in range(w)]
                        for y in range(h)]
        return cache[i]

    def encode(pens):
        out = bytearray()
        for col in range(w // 4):               # 4 pixels a character
            for y in range(h):
                for x in (col * 4, col * 4 + 2):
                    out.append(cpclib.encode_pixels(pens[y][x], pens[y][x + 1]))
        return bytes(out)

    # AND A PAIR THAT COMPOSITES TO THE OVERLAY ITSELF IS NOT BAKED.
    # Where the background is black in every pixel the overlay's
    # transparent pen 0 already comes out black, so the composite is
    # byte for byte the tile the artist drew and a copy of it would be
    # 64 bytes of bank for nothing. This is the one place that question
    # is ANSWERED rather than assumed, and the answer was a surprise:
    # `far_fill` is not all black (4 lit pixels of 128), so the three
    # roof props on it are baked like everything else and only
    # `tank_10` is dropped.
    blob, extra, remap, same = bytearray(), [], {}, {}
    for (over, under), index in sorted(BAKED.items(), key=lambda kv: kv[1]):
        bytes_ = encode(pens_of(index))
        if bytes_ == encode(pens_of(over)):
            remap[index] = over
            same[index] = name_of(names, extra, under)
            continue
        remap[index] = len(names) + len(extra)
        extra.append(f"{names[over]}_on_{name_of(names, extra, under)}")
        blob += bytes_
    return bytes(blob), extra, remap, same


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

    # ---- the overlays, composited onto what they cover --------------
    # The map holds the BAKED tile, so every blitter stays a plain copy
    # and the frame pays nothing. See the note by put_overlay().
    extra_bytes, extra_names, remap, flat = bake_overlays(names)
    for row in g:                       # the provisional ids become the
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


if __name__ == "__main__":
    main()
