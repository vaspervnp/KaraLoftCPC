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

MAP_W, MAP_H = 128, 16          # 6.4 screens across, one down - the City's
LEVEL_ID, TILESET_ID = 5, 2     # level 5 of 24, environment 2

ROW_CANOPY, ROW_EDGE, ROW_CROWNS = 0, 1, 2
ROW_TRUNKS = range(3, 8)
ROW_BASE, ROW_GROUND = 8, 9

SOLID, PLATFORM, HAZARD, LADDER = 1, 2, 4, 8

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
EK_DOOR, EK_RECEPTACLE = 6, 7
EF_ACTIVE, EF_TAKEN, EF_SOLID, EF_TOUCH = 1, 2, 4, 8
PU_KEY, PU_AMMO, PU_MEDKIT, PU_COIN, PU_IDOL, PU_BOOK = range(6)
EN_AGENT, EN_DRONE, EN_SNIPER = 0, 1, 2
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
# THE LEVEL, left to right. Every number here is a TILE column, and the
# sections are written in the order she meets them.
# ---------------------------------------------------------------------
TREES = (9, 24, 47, 66, 96, 110)        # the two-tile trunk's LEFT column
PITS = ((14, 2), (30, 3), (72, 3), (102, 3))    # (left column, width)
# HER JUMP IS 36 PIXELS AND A ROW IS 16, so a branch two rows above
# whatever she is standing on is the most she can reach: row 7 from the
# ground, row 5 from row 7. A row-5 branch with no row-7 branch under
# it is scenery, and the key on it is a level that cannot be finished -
# which is what `reachable` below is for, and what it caught here.
BRANCHES = ((18, 4, 7), (34, 4, 7), (36, 5, 5),
            (78, 4, 7), (84, 4, 7), (86, 5, 5), (114, 4, 7))
MOUNTAIN = (52, 62)                     # left and right columns, inclusive
CAVE = 120                              # the mouth's left column, 4 wide
DECO = {6: "bush_l", 7: "bush_r", 21: "rock", 28: "flowers",
        34: "mushrooms", 44: "bush_l", 45: "bush_r", 69: "rock",
        75: "flowers", 84: "mushrooms", 93: "rock", 107: "flowers"}


def build_map(t):
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
    left, right = MOUNTAIN
    for i, r in enumerate(ROW_TRUNKS):
        g[r][left + i] = t["mtn_slope"]
        for x in range(left + i + 1, right + 1):
            g[r][x] = t["mtn_rock_moss" if (x + r) % 3 == 0 else "mtn_rock"]
    for x in range(left + len(ROW_TRUNKS), right + 1):
        g[ROW_BASE][x] = t["mtn_slope_base"]

    # ---- the big trees, two tiles wide ----------------------------
    for x in TREES:
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
    for x, n, row in BRANCHES:
        for i in range(n):
            g[row][x + i] = t["branch_l" if i == 0 else
                              "branch_r" if i == n - 1 else "branch_m"]
        for tx in TREES:
            if tx == x + n:                     # it meets a trunk's left side
                g[row][tx] = t["trunk_knot_l"]
            if tx + 1 == x - 1:                 # ... or its right
                g[row][tx + 1] = t["trunk_knot_r"]

    # ---- the pits in the ground row -------------------------------
    # "grass_edge_r, spike_pit x N, grass_edge_l" - the edges face IN,
    # which is the artist's naming and not a mistake here: the tile on
    # the pit's left is the RIGHT-hand edge of the grass before it.
    for x, n in PITS:
        g[ROW_GROUND][x - 1] = t["grass_edge_r"]
        for i in range(n):
            g[ROW_GROUND][x + i] = t["spike_pit"]
        g[ROW_GROUND][x + n] = t["grass_edge_l"]

    # ---- the deco on the undergrowth row --------------------------
    for x, name in DECO.items():
        g[ROW_BASE][x] = t[name]

    # ---- and the cave mouth, which is the way out -----------------
    # 4 wide x 6 high, ending IN the ground row: arch, four rows of
    # sides, floor.
    arch = ROW_GROUND - 5
    for i in range(4):
        g[arch][CAVE + i] = t[f"cave_arch_{i}"]
    for r in range(arch + 1, ROW_GROUND):
        g[r][CAVE] = t["cave_side_l"]
        g[r][CAVE + 1] = t["cave_dark"]
        g[r][CAVE + 2] = t["cave_dark"]
        g[r][CAVE + 3] = t["cave_side_r"]
    for i, name in enumerate(("cave_floor_l", "cave_floor",
                              "cave_floor", "cave_floor_r")):
        g[ROW_GROUND][CAVE + i] = t[name]
    return bytes(b for row in g for b in row)


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
START_X = 3

# AND IT SHIPS WITH NO ENEMIES, WHICH IS A MEASUREMENT AND NOT AN
# OVERSIGHT. The forest's only ranged character is the sniper, and it is
# 12x64 - agent class, which CLAUDE.md 8.7 measured as unaffordable at
# 50 Hz and 9 called affordable at 25 Hz ON PAPER, with nothing having
# measured it. Two of them went in this map and the measurement is
# what took them out: standing beside one, the loop is
#
#     80 game frames in 200 hardware, against 100 with ENEMY_LIVE at 0
#
# - the same level, the same spot, one thing changed. Twenty holes in
# two hundred frames, where the City's drones cost nought to five.
#
# The forest's OWN creatures are a wolf and a boar, and both are 16x24
# and would very likely fit - but their tags are RUN and ATTACK. They
# are melee, and the engine has no melee: driven through EN_T_FIRE they
# would shoot invisible bullets. That is the work level 2's enemies are
# waiting on, and EN_SNIPER stays in the type table the way EN_AGENT
# has - correct data that the frame cannot spend yet.
SNIPERS = ()


def build_entities(t):
    recs = [
        entity(EK_PLAYER_START, START_X, ROW_GROUND - 1, EF_ACTIVE),
        # THE KEY IS ON A BRANCH, which is what makes the platforms the
        # level rather than scenery: the way out is behind a jump.
        entity(EK_PICKUP, 38, 5, EF_ACTIVE | EF_TOUCH, PU_KEY),
        entity(EK_PICKUP, 20, ROW_GROUND, EF_ACTIVE | EF_TOUCH, PU_AMMO, 14),
        entity(EK_PICKUP, 64, ROW_GROUND, EF_ACTIVE | EF_TOUCH, PU_MEDKIT),
        # ... and the IDOL is the one pickup drawn out of the forest's
        # OWN sheet - forestpickups carries nothing else (CLAUDE.md 8.6).
        entity(EK_PICKUP, 100, ROW_GROUND, EF_ACTIVE | EF_TOUCH, PU_IDOL),
        # The altar takes it: level 2's signature, and PLACE_STATUE is
        # the handler that has been waiting for a level with one in it.
        entity(EK_RECEPTACLE, 117, ROW_GROUND, EF_ACTIVE, PU_IDOL, 1),
        entity(EK_DOOR, CAVE + 1, ROW_GROUND, EF_ACTIVE | EF_SOLID, 0, PU_KEY),
    ]
    for x in SNIPERS:
        recs.append(entity(EK_ENEMY, x, ROW_GROUND, EF_ACTIVE,
                           EN_SNIPER, PATROL))
    return b"".join(recs)


def reachable(m, t):
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

    start = under(START_X, ROW_GROUND - 1)
    seen, queue = set(), [(START_X, start)]
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


def checks(m, t, ents):
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

    # ... AND EVERY THING SHE HAS TO TOUCH MUST BE SOMEWHERE SHE CAN
    # STAND. A record's row is the floor it stands on and not the cell
    # it is in: y is the BASE of the hitbox (CLAUDE.md 8.6).
    where = reachable(m, t)
    for i in range(0, len(ents), 8):
        if ents[i] not in (EK_PICKUP, EK_DOOR, EK_RECEPTACLE):
            continue
        x = (ents[i + 1] | ents[i + 2] << 8) // 8
        row = (ents[i + 3] | ents[i + 4] << 8) // 16
        assert (x, row) in where, (
            f"a kind-{ents[i]} record at tile {x}, row {row} is somewhere "
            f"she cannot stand - her jump is 36 pixels and a row is 16")

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
    m = build_map(t)
    ents = build_entities(t)
    pickups, enemies, pit_tiles = checks(m, t, ents)

    flags = bytes(TILE_FLAGS.get(n, 0)
                  for n, _ in sorted(t.items(), key=lambda kv: kv[1]))
    out = os.path.join(BUILD, "tileflags_level2_forest.bin")
    open(out, "wb").write(flags)
    print(f"-> tileflags_level2_forest.bin  {len(flags)} tiles, "
          f"{sum(1 for f in flags if f)} with anything on")

    blob = pack(level_id=LEVEL_ID, tileset_id=TILESET_ID,
                width=MAP_W, height=MAP_H, map_bytes=m, entities=ents)
    out = os.path.join(BUILD, f"level_{LEVEL_ID}.lvl")
    open(out, "wb").write(blob)
    back = read(blob)
    assert back["map"] == m and back["entities"] == len(ents) // 8
    print(f"-> level_{LEVEL_ID}.lvl     {len(blob)} bytes: {back['width']}x"
          f"{back['height']}, {back['entities']} entities "
          f"({pickups} pickups, {enemies} snipers), tileset {TILESET_ID}")
    print(f"   {len(TREES)} trees, {len(BRANCHES)} branch platforms, "
          f"{len(PITS)} pits ({pit_tiles} tiles of spike), a mountain and "
          f"a cave mouth at tile {CAVE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
