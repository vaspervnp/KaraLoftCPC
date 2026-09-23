#!/usr/bin/env python3
"""The cave's maps - levels 9 AND 10, and the first levels that are TALL.

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

ONE TOOL, TWO COMPOSITIONS - AND UNLIKE THE FOREST'S, THEY SHARE A
BAKE. A tileset belongs to the ENVIRONMENT and not to the level, so
levels 9 and 10 point into ONE cavetiles.bin and one
tileflags_level3_cave.bin: every (overlay, background) pair either
level places has to take the same index in both, and the blob is
appended to ONCE. make_forest_map.py never had to say this because the
forest has no overlays at all (7.3). So the maps are built first, both
of them, into one BAKED; the composite happens after.

That level 9 is byte for byte the file that shipped is what says the
second composition did not disturb the first.

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
SHEET = "cave_tiles_cpc_mode0_sheet"

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

LAYOUTS = (LEVEL_9, LEVEL_10)

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

    # ---- the floors: a ledge from wall to wall ---------------------
    for r in FLOORS:
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

    # ---- and the water that collects at the bottom ------------------
    for i, (r, x) in enumerate(L["pools"]):
        g[r][x] = t["pool_0" if i % 2 == 0 else "pool_1"]

    # ---- and the ladders between the floors -------------------------
    for top, col in L["ladders"]:
        for r in range(top, top + 8):
            put_overlay(g, names, r, col, "ladder")

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
    cols = [c for _, c in L["ladders"]]
    assert len(set(cols)) == len(cols), f"two floors share a ladder: {cols}"
    hung = {r for r, _ in L["ladders"]}
    assert hung == set(FLOORS[:-1]) or hung == set(FLOORS[1:]), (
        f"a floor with no ladder off it: {sorted(hung)}")

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
    for r in FLOORS:
        assert any(row == r for _, row in where), f"floor at row {r} is cut off"

    # ... AND EVERY LADDER HAS TO BE STOOD ON. A hole between where she
    # lands and the ladder is a floor she can only leave by falling -
    # which plays, and costs 32 points a floor, and is not what the map
    # says. reachable() credits no horizontal jump, so this is exactly
    # the question "could she walk to it".
    for r, c in L["ladders"]:
        assert (c, r) in where, (
            f"the ladder at tile {c}, row {r} is somewhere she cannot "
            f"walk to - a hole is between her and it")
    return len(pickups), len(where)


def main():
    names = tile_names()

    # BOTH MAPS FIRST, INTO ONE BAKED. The blob and the flag table are
    # the ENVIRONMENT's, so a pair placed by either level has to come
    # out at one index - and level 9 is built first so that its own
    # eleven keep the indices they shipped with.
    built = []
    for L in LAYOUTS:
        g = build_map(names, L)
        ents = build_entities(L)
        pickups, standable = checks(g, names, ents, L)
        built.append((L, g, ents, pickups, standable))

    extra_bytes, extra_names, remap, flat = bake_overlays(
        ART, SHEET, names, BAKED)
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
        print(f"   {len(FLOORS)} floors 8 rows apart, {len(L['ladders'])} "
              f"ladders, {len(L['holes'])} holes, a 4x5 gate, "
              f"{standable} standable cells")
    return 0


if __name__ == "__main__":
    sys.exit(main())
