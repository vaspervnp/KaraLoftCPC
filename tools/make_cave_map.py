#!/usr/bin/env python3
"""Level 9's map: the cave, and the first level that is TALL.

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
tools/test_shape.py proved on a 6128 - this is the first SHIPPED level
to ask for it.

AND IT IS THE FIRST MAP WITH LADDERS SINCE THE CITY, which is not a
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

WHAT IS NOT HERE IS THE PUZZLE. The artist drew a four-slot gate and
two panels that hint the order sun-moon / eye-star, and CLAUDE.md 8.1
calls the cave's signature a "3-symbol book/lever puzzle";
READ_BOOK_PUZZLE and CURRENT_BOOK_ID exist in the engine and nothing
has ever driven them. The gate here is an EK_DOOR that a key opens, and
the slots are drawn unfilled. Wiring the books to the slots is a
mechanic and not a map, and inventing its contract quietly would be the
worse of the two ways to be wrong.
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
SHEET = "cave_tiles_cpc_mode0_sheet"

MAP_W, MAP_H = 32, 64           # 1.6 screens across, 5.3 DOWN
LEVEL_ID, TILESET_ID = 9, 3     # level 9 of 24, environment 3

SOLID, PLATFORM, HAZARD, LADDER = 1, 2, 4, 8

# The walls are the map's edges and she is three tiles wide, so the
# inner faces go here and everything outside them is fill.
WALL_L, WALL_R = 3, 28

# FLOORS EIGHT ROWS APART, which is 128 world lines - the City's own
# roof-to-street drop, and what CLAUDE.md 11 step 7's table fixed for
# the editor's generator. She starts on the bottom one and climbs.
FLOORS = (6, 14, 22, 30, 38, 46, 54, 62)

# (the floor she leaves, the column the ladder is in). THE COLUMN MOVES
# EVERY FLOOR, so each one has to be WALKED before it can be left -
# which is the generator's rule (11 step 7) and the only thing that
# makes eight floors a level rather than one floor eight times.
LADDERS = ((62, 24), (54, 8), (46, 20), (38, 6), (30, 22), (22, 10),
           (14, 25))

GATE_COL = 12                   # 4 wide, its base standing on the top floor
TOP_FLOOR = FLOORS[0]
START_COL = 6                   # on the bottom floor, away from its ladder

# The overlays, as (row, column, tile) - each one composited onto
# whatever the map already holds there. Crystals stand on a surface and
# lamps hang from a beam, which is the artist's own description.
DECOR = [(r - 1, c, n) for r, c, n in (
    (54, 14, "crystal_0"), (54, 15, "crystal_1"),
    (38, 18, "crystal_0"), (22, 11, "crystal_1"),
)] + [(r, c, n) for r, c, n in (
    (50, 12, "beam_top"), (51, 12, "beam_post"), (52, 12, "beam_post"),
    (34, 20, "lamp_0"), (18, 8, "lamp_1"),
)]

TILE_FLAGS = {
    # The rock she stands on. A floating ledge is a PLATFORM - a floor
    # from above and nothing from below - so a jump can carry her up
    # through one; the floors are eight rows apart and her jump reaches
    # two, so that never skips a ladder.
    "ground": SOLID,
    "ledge_l": PLATFORM, "ledge_m": PLATFORM, "ledge_r": PLATFORM,
    "wall_l_ledge": PLATFORM, "wall_r_ledge": PLATFORM,
    "pillar_top": PLATFORM,
    # The walls, which are the edges of the map and have to stop her.
    "wall_fill": SOLID, "wall_l": SOLID, "wall_l_b": SOLID,
    "wall_r": SOLID, "wall_r_b": SOLID,
    "ceil": SOLID, "ceil_stalactites": SOLID,
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
ENT_MAX = 24

BAKED = {}                      # (overlay tile, tile under it) -> new index


def tile_names():
    """The cave's tile_table.json names every tile, which the forest's
    does not - there the table carries tags and the manifest's prose
    carries the names (8.11). So this is the table, read straight."""
    d = json.load(open(os.path.join(ART, "tile_table.json")))
    sheet = next(s for s in d["sheets"] if s["sheet"] == "cave_tiles")
    names = [t["name"] for t in sheet["tiles"]]
    assert len(names) == sheet["count"] == 47, names
    return names


def put_overlay(g, names, y, x, name):
    """Place an overlay, baking it onto whatever it covers."""
    over, under = names.index(name), g[y][x]
    key = (over, under)
    if key not in BAKED:
        BAKED[key] = len(names) + len(BAKED)
    g[y][x] = BAKED[key]


def build_map(names):
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

    # ---- the floors: a ledge from wall to wall ---------------------
    for r in FLOORS:
        g[r][WALL_L + 1] = t["wall_l_ledge"]
        g[r][WALL_R - 1] = t["wall_r_ledge"]
        for x in range(WALL_L + 2, WALL_R - 1):
            g[r][x] = t["ledge_m"]

    # ---- and the ladders between them ------------------------------
    # The top rung is IN the upper floor's row, which is what lets her
    # walk over it and step onto the shaft with DOWN (8.8). The rest
    # run down to just above the floor she is leaving.
    for lower, col in LADDERS:
        for r in range(lower - 8, lower):
            put_overlay(g, names, r, col, "ladder")

    # ---- the gate at the top, standing on the last floor ------------
    # 4 wide x 5 tall: the slots across the top, then four rows of
    # pillar / door / door / pillar.
    for i, n in enumerate(("gate_slot_sun", "gate_slot_moon",
                           "gate_slot_eye", "gate_slot_star")):
        g[TOP_FLOOR - 5][GATE_COL + i] = t[n]
    for r in range(TOP_FLOOR - 4, TOP_FLOOR):
        for i, n in enumerate(("gate_pillar_l", "gate_door_l",
                               "gate_door_r", "gate_pillar_r")):
            g[r][GATE_COL + i] = t[n]

    # ---- the panels that hint its order, set into the walls ---------
    g[TOP_FLOOR - 2][WALL_L] = t["panel_sun_moon"]
    g[TOP_FLOOR - 2][WALL_R] = t["panel_eye_star"]

    # ---- and the crystals, the beams and the lamps ------------------
    for r, c, n in DECOR:
        put_overlay(g, names, r, c, n)
    return g


def entity(kind, tile_x, base_row, flags, p0=0, p1=0):
    """One record, given in TILES. The format stores world pixels with
    y at the BASE of the hitbox (CLAUDE.md 8.6)."""
    x, y = tile_x * 8, base_row * 16
    return bytes([kind, x & 255, x >> 8, y & 255, y >> 8, flags, p0, p1])


def build_entities():
    return b"".join([
        # She starts a row high and falls the last 16 pixels, which is
        # free against FALL_FREE of 96 and keeps a 64-line box out of
        # the tiles (8.11).
        entity(EK_PLAYER_START, START_COL, FLOORS[-1] - 1, EF_ACTIVE),
        entity(EK_PICKUP, 20, FLOORS[-2], EF_ACTIVE | EF_TOUCH, PU_AMMO, 14),
        entity(EK_PICKUP, 12, FLOORS[-4], EF_ACTIVE | EF_TOUCH, PU_MEDKIT),
        # THE KEY IS ON THE SECOND FLOOR FROM THE TOP, so the climb is
        # done before the gate can be opened and the last ladder is not
        # a shortcut past it.
        entity(EK_PICKUP, 22, FLOORS[1], EF_ACTIVE | EF_TOUCH, PU_KEY),
        entity(EK_DOOR, GATE_COL + 1, TOP_FLOOR,
               EF_ACTIVE | EF_SOLID, 0, PU_KEY),
    ])


def reachable(m, names):
    """Every place she can stand - AND THIS ONE CLIMBS.

    The forest's fill models a walk, a fall and a two-row jump
    (make_forest_map.py). A cave is none of those: its floors are eight
    rows apart and the only way up is a ladder, so a fill without one
    says the level is eight separate rooms - which is exactly what a
    cave with a misplaced ladder IS, and the reason this is worth
    writing rather than assuming.
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

    start = under(START_COL, FLOORS[-1] - 1)
    seen, queue = set(), [(START_COL, start)]
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
    return seen


def checks(m, names, ents):
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

    where = reachable(m, names)
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
    for r in FLOORS:
        assert any(row == r for _, row in where), f"floor at row {r} is cut off"
    return len(pickups), len(where)


def main():
    names = tile_names()
    g = build_map(names)
    ents = build_entities()
    pickups, standable = checks(g, names, ents)

    extra_bytes, extra_names, remap, flat = bake_overlays(
        ART, SHEET, names, BAKED)
    for r in range(MAP_H):
        for x in range(MAP_W):
            g[r][x] = remap.get(g[r][x], g[r][x])
    m = bytes(b for row in g for b in row)

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

    # THE BLOB IS TRUNCATED TO THE SHEET'S OWN TILES FIRST, so running
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
          f"= {len(base) + len(extra_bytes)} bytes")

    out = os.path.join(BUILD, "tileflags_level3_cave.bin")
    open(out, "wb").write(flags[:256])
    print(f"-> tileflags_level3_cave.bin  {len(full)} tiles, "
          f"{sum(1 for f in flags[:len(full)] if f)} with anything on")

    lvl = pack(level_id=LEVEL_ID, tileset_id=TILESET_ID,
               width=MAP_W, height=MAP_H, map_bytes=m, entities=ents)
    out = os.path.join(BUILD, f"level_{LEVEL_ID}.lvl")
    open(out, "wb").write(lvl)
    back = read(lvl)
    assert back["map"] == m and back["entities"] == len(ents) // 8
    print(f"-> level_{LEVEL_ID}.lvl     {len(lvl)} bytes: {back['width']}x"
          f"{back['height']}, {back['entities']} entities "
          f"({pickups} pickups), tileset {TILESET_ID}")
    print(f"   {len(FLOORS)} floors 8 rows apart, {len(LADDERS)} ladders, "
          f"a 4x5 gate at the top, {standable} standable cells")
    return 0


if __name__ == "__main__":
    sys.exit(main())
