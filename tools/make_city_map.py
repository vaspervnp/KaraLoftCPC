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

THE ROOFTOP IS ONE CONTINUOUS RUN AT ONE HEIGHT. A tile is 16 pixels
tall and she walks 2 a frame, so any step up in the roof line is a wall
that stops her dead - and a player who cannot walk is a camera that
cannot scroll, which makes every scrolling test vacuous WITHOUT failing
it. The variety is in the skyline above, the windows below and the props
on the roof, none of which is in her way.
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
ROW_FAR_TOP  = 3
ROW_ROOFLINE = 4                # props stand here, on top of the roof
ROW_ROOF     = 5                # <- the walkable surface, world y = 80
ROW_WALL_TOP = 6
ROW_PAVEMENT = 12
ROW_CURB     = 13
ROW_STREET   = 14


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
    ROOF = ROW_ROOF * 16                # world y of the rooftop surface
    e = [
        # Pickups stand ON the roof, so their base is the roof's top edge.
        entity(EK_PICKUP, 24, ROW_ROOF, EF_ACTIVE | EF_TOUCH, PU_KEY, 0),
        entity(EK_PICKUP, 44, ROW_ROOF, EF_ACTIVE | EF_TOUCH, PU_AMMO, 14),
        entity(EK_PICKUP, 64, ROW_ROOF, EF_ACTIVE | EF_TOUCH, PU_MEDKIT, 0),
        entity(EK_PICKUP, 84, ROW_ROOF, EF_ACTIVE | EF_TOUCH, PU_COIN, 5),
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
        # ROW_FAR_TOP AND NOT ROW_ROOFLINE, because a drone a row higher
        # hovers above her gun: her muzzle is at world y 37 (KARA_WY 20
        # plus the firing cel's own spawn point) and a drone based on
        # row 4 spans 44-64, so every round she fired went under it.
        # Based on row 3 it spans 28-48, which is her head height - she
        # can hit it and it can hit her.
        entity(EK_ENEMY, 36, ROW_FAR_TOP, EF_ACTIVE, EN_DRONE, 4),
        entity(EK_ENEMY, 76, ROW_FAR_TOP, EF_ACTIVE, EN_DRONE, 4),
        entity(EK_ENEMY, 116, ROW_FAR_TOP, EF_ACTIVE, EN_DRONE, 6),
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
        g[ROW_ROOFLINE][x] = T["far_fill"]

        # ---- the roof she walks on, one height, all the way ---------
        # roof_l / roof_m... / roof_r reads as a row of separate
        # buildings standing shoulder to shoulder, which is variety that
        # costs her nothing: the SURFACE is flat whatever tile draws it.
        p = x % 16
        g[ROW_ROOF][x] = (T["roof_l"] if p == 0 else
                          T["roof_r"] if p == 15 else T["roof_m"])

        # ---- the wall below, with lit and dark windows --------------
        g[ROW_WALL_TOP][x] = T["brick_top"]
        for y in range(ROW_WALL_TOP + 1, ROW_PAVEMENT):
            lit = ((x // 2 + y) % 3 == 0)
            g[y][x] = (T["brick_win_lit"] if lit and (x + y) % 2 == 0 else
                       T["brick_win_dark"] if lit else T["brick"])

        # ---- street level ------------------------------------------
        g[ROW_PAVEMENT][x] = T["sidewalk"]
        g[ROW_CURB][x] = T["curb"]
        for y in range(ROW_STREET, MAP_H):
            g[y][x] = T["street_line"] if (x % 8) < 2 and y == ROW_STREET \
                else T["street"]

    # ---- ladders down the face of a building every so often ---------
    for x in range(11, MAP_W, 23):
        for y in range(ROW_WALL_TOP, ROW_PAVEMENT):
            g[y][x] = T["ladder"]

    # ---- props on the roof, standing on ROW_ROOFLINE ----------------
    # Decoration only: TILE_ATTR gives them no attributes, so she walks
    # straight through them. A solid prop on the runway is the step that
    # stops the camera.
    for x in range(5, MAP_W, 16):
        g[ROW_ROOFLINE][x] = T["ac_unit"]
    for x in range(9, MAP_W, 16):
        g[ROW_ROOFLINE][x] = T["chimney"]
    for x in range(13, MAP_W, 32):
        g[ROW_ROOFLINE][x] = T["antenna"]

    # ---- the water tank: a 2 wide x 3 tall group, tank_RC row-major --
    for x0 in range(20, MAP_W, 48):
        for r in range(3):
            for c in range(2):
                y = ROW_ROOFLINE - 2 + r
                if x0 + c < MAP_W:
                    g[y][x0 + c] = T[f"tank_{r}{c}"]

    # ---- a lamp on the pavement -------------------------------------
    for x in range(6, MAP_W, 24):
        g[ROW_PAVEMENT - 1][x] = T["lamp_top"]
        g[ROW_PAVEMENT][x] = T["lamp_pole"]

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

    # ---- a crate or two on the pavement ------------------------------
    for x in range(17, MAP_W, 37):
        g[ROW_PAVEMENT - 1][x] = T["crate"]

    blob = bytes(b for row in g for b in row)
    assert len(blob) == MAP_W * MAP_H
    assert max(blob) < len(names), "a tile index ran past the sheet"
    out = os.path.join(ROOT, "build", "city_map.bin")
    open(out, "wb").write(blob)
    n = build_entities(os.path.join(ROOT, "build", "city_entities.bin"))
    print(f"-> city_entities.bin  {n} of {ENT_MAX} slots used, "
          f"{ENT_MAX * 8} bytes")
    print(f"-> city_map.bin    {MAP_W}x{MAP_H} = {len(blob)} bytes, "
          f"{len(set(blob))} distinct tiles of {len(names)}")
    print(f"   roof at map row {ROW_ROOF} = world y {ROW_ROOF * 16}, "
          f"continuous across all {MAP_W} columns")


if __name__ == "__main__":
    main()


