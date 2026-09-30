#!/usr/bin/env python3
"""Levels 9 to 12 on a 6128: the cave, and the first SHIPPED levels that
are tall - up by ladder, down by ladder or by a hole, up again by the
rock, jump after jump, and down to the water on ladders the earthquake
broke.

Every other map in this game is 128x16. The cave is 32x64 - 1.6 screens
across and 5.3 DOWN - so it is the first level to ask MAP_INSTALL to
patch the engine's thirty-six shape immediates for real rather than in
a suite's own hand-built map (CLAUDE.md 8.3). And it is the first map
since the City with a LADDER in it, which is what its bank set was
given the `climb` cels for (6.2).

WHAT MAKES IT A CHECK AND NOT A SCREENSHOT is that nothing here knows
where the generator put anything. The floors and the seven ladders are
read back out of the level's OWN map through the engine's own
TILE_ATTR, and she is driven up them from the joystick.

CLIMBING UP READS THE ROW ABOVE HER FEET AND CLIMBING DOWN READS THE
ONE UNDER THEM, which is not symmetry and is worth knowing before
writing a driver for either. The ladder's top rung is in the upper
floor's own row, because a rung she could only fall onto is not a way
up (8.8); so from a floor, DOWN finds the ladder in that floor's row
and UP finds it in the row above. Asking the down question on the way
up says "no ladder here" on every floor in the level.

AND THE CLIMB IS WHAT FOUND THE `kact` BUG, which is why the second
half of this suite is about the heroine and not about the cave. The
action blob is allocated per level and is NOT pinned, and KARA_SETS
named level 1's symbols for all six environments - so `climb`, which
is a back view stored once at the end of the RIGHT-facing blob, was
read out of the City's address inside the cave's banks. The machine
died on the first rung. Six of the twelve addresses were wrong and
only the City's were right, because the City is level 1.
"""
import json
import os
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import boot, symbols, sync                          # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BUILD = os.path.join(ROOT, "build")
ART = os.path.join(ROOT, "assets", "sprites", "level3_cave")
TA_SOLID, TA_PLATFORM, TA_CLIMB = 1, 2, 8
JOY = {"right": 0x08, "left": 0x04, "up": 0x01, "down": 0x02}
GS_CLEAR = 2
LEVEL, ENV = 9, 3                       # level 9 of 24, environment 3
NEXT = 10                               # ... and where its gate points
THIRD = 11                              # ... and where THAT one does
FOURTH = 12                             # ... and the cave's last
MAP_W, MAP_H = 32, 64
V_CR_MAX = (MAP_H * 16 - 192) // 8      # 104 - the deepest the view goes
ENVS = ("city", "forest", "cave", "undersea", "desert", "station")
STUB = 0x8E00

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


class Play:
    """The running game, in the units the level is written in."""

    def __init__(self, sym, climbable=True, level=LEVEL):
        self.sym, self.level = sym, level
        self.m = m = boot(sym, scroll=True)
        m.poke(sym["LEVEL_CUR"], level - 2)     # ... so the next one is ours
        m.poke(sym["GAME_STATE"], GS_CLEAR)
        self.frames = None
        for f in range(900):
            m.run_frames(1)
            # THE SYNC IS THE FSM COMING BACK TO PLAY. LEVEL_ENV is
            # claimed BEFORE the read and LEVEL_OK is still 1 from the
            # level being left (8.1), so a driver that waits on either
            # is reading the LAST level's map.
            if (m.peek(sym["GAME_STATE"]) == 0
                    and m.peek(sym["LEVEL_CUR"]) == level - 1):
                self.frames = f
                m.run_frames(10)
                break
        self.reread()
        if not climbable:
            self.unclimb()
        self.attr = bytes(m.read_ram(sym["TILE_ATTR"], sym["TILE_ATTR_N"]))

    def reread(self):
        """The level in RAM, after a transition has replaced it."""
        sym, m = self.sym, self.m
        hdr = m.read_ram(sym["LEVEL_LVL"], 21)
        self.w = hdr[5] | hdr[6] << 8
        self.h = hdr[7] | hdr[8] << 8
        self.tileset = hdr[9]
        self.map = bytes(m.read_ram(sym["LEVEL_LVL"] + 21, self.w * self.h))
        self.attr = bytes(m.read_ram(sym["TILE_ATTR"], sym["TILE_ATTR_N"]))

    def unclimb(self):
        """The control: take TA_CLIMB off every tile that has it, in the
        table the ENGINE reads, leaving the map and the picture alone."""
        base, n = self.sym["TILE_ATTR"], self.sym["TILE_ATTR_N"]
        for i in range(n):
            a = self.m.peek(base + i)
            if a & TA_CLIMB:
                self.m.poke(base + i, a & ~TA_CLIMB)

    def word(self, name):
        a = self.sym[name]
        return self.m.peek(a) | self.m.peek(a + 1) << 8

    def byte(self, name):
        return self.m.peek(self.sym[name])

    def standable(self, row):
        return [x for x in range(self.w)
                if self.attr[self.map[row * self.w + x]] & (TA_SOLID | TA_PLATFORM)]

    def floors(self):
        """A row that is a FLOOR: standable nearly all the way across -
        which leaves room for the walls' own columns either side - AND
        with open space above it. Without that second half the map's
        own CEILING and the rock under the bottom floor are both
        floors, which is true of the attributes and useless to a walk."""
        return [r for r in range(1, self.h)
                if len(self.standable(r)) > self.w - 4
                and len(self.standable(r - 1)) <= self.w - 4]

    def shafts(self, row):
        """The columns on `row` the ENGINE would call a ladder."""
        return [x for x in range(self.w)
                if self.attr[self.map[row * self.w + x]] & TA_CLIMB]

    def platforms(self, row):
        """The runs of cells on `row` that are a floor from above and
        nothing from below - every step and every floor in this
        environment, and never the walls, which are SOLID."""
        out, run = [], []
        for x in range(self.w):
            if self.attr[self.map[row * self.w + x]] & TA_PLATFORM:
                run.append(x)
            else:
                if run:
                    out.append((run[0], run[-1]))
                run = []
        if run:
            out.append((run[0], run[-1]))
        return out

    def row(self):
        """The map row her feet are on: KARA_WY is the TOP of a 64-line box."""
        return (self.word("KARA_WY") + 64) // 16

    def column(self):
        """The tile column CLIMB_AT probes - the middle of her six-byte box."""
        return (self.word("KARA_WX") + 3) // 4

    def walk_to(self, column, frames=700):
        for _ in range(frames):
            if self.column() == column:
                break
            self.m.joystick(JOY["right"] if self.column() < column
                            else JOY["left"])
            self.m.run_frames(1)
        self.m.joystick(0)
        self.m.run_frames(2)
        return self.column() == column

    def holes(self, row):
        """The runs of three or more cells a floor is MISSING - what she
        can fall through.

        It names no wall column, because it does not have to: on a floor
        row every cell is either the rock she stands on, the wall, or a
        hole, and only the hole has NO attribute at all. Three is
        BOX_SOLID_V's number (8.8) and the reason a two-cell gap is not
        one she can fall through."""
        out, run = [], []
        for x in range(self.w):
            if self.attr[self.map[row * self.w + x]]:
                if len(run) >= 3:
                    out.append(run[0])
                run = []
            else:
                run.append(x)
        if len(run) >= 3:
            out.append(run[0])
        return out

    def settle(self, frames=300, still_for=20):
        was, still = self.word("KARA_WY"), 0
        for _ in range(frames):
            self.m.run_frames(1)
            now = self.word("KARA_WY")
            still = still + 1 if now == was else 0
            was = now
            if still >= still_for:
                break
        return self.row()

    def climb_down(self, frames=900):
        """DOWN until the floor below catches her - which is when she
        STOPS MOVING, and not when her row changes. A ladder is eight
        rows and her row ticks over on every one of them, so a driver
        that watched the row descended one tile and called it a floor."""
        was, still, start = self.word("KARA_WY"), 0, self.row()
        self.m.joystick(JOY["down"])
        for _ in range(frames):
            self.m.run_frames(1)
            now = self.word("KARA_WY")
            still = still + 1 if now == was else 0
            was = now
            if still >= 25 and self.row() > start:
                break
        self.m.joystick(0)
        self.m.run_frames(6)
        return self.row()

    def down_and_measure(self, frames=900):
        """climb_down, and what the machine made of any fall on the way:
        FALL_TOP read while she is falling, which is the instant it is
        frozen (8.4) - so a ladder that ends in mid-air says where it
        let her go, in the engine's own number and not the map's."""
        began, start = None, self.row()
        was, still = self.word("KARA_WY"), 0
        self.m.joystick(JOY["down"])
        for _ in range(frames):
            self.m.run_frames(1)
            vy = self.byte("KARA_VY")
            if 0 < vy < 128 and began is None:
                began = self.word("FALL_TOP")
            now = self.word("KARA_WY")
            still = still + 1 if now == was else 0
            was = now
            if still >= 25 and self.row() > start:
                break
        self.m.joystick(0)
        self.m.run_frames(6)
        fell = None if began is None else self.word("KARA_WY") - began
        return self.row(), fell

    def walk_off(self, column, frames=700):
        """Walk toward `column` until the floor stops being under her -
        which is what a HOLE is, and the only thing in this environment
        that costs her anything."""
        start = self.row()
        for _ in range(frames):
            if self.row() > start:
                break
            self.m.joystick(JOY["right"] if self.column() < column
                            else JOY["left"])
            self.m.run_frames(1)
        self.m.joystick(0)
        return self.settle()

    def climb_up(self, frames=900):
        """UP until the floor above catches her, or she is not moving."""
        was, still, start = self.word("KARA_WY"), 0, self.row()
        self.m.joystick(JOY["up"])
        for _ in range(frames):
            self.m.run_frames(1)
            now = self.word("KARA_WY")
            still = still + 1 if now == was else 0
            was = now
            if still >= 25 and self.row() < start:
                break
        self.m.joystick(0)
        self.m.run_frames(6)
        return self.row()


def ascend(p, report=True):
    """Up every ladder the level has, and where she got to."""
    landings, alive = [p.row()], True
    for _ in range(p.h // 4):
        r0 = p.row()
        s = p.shafts(r0 - 1)            # the rungs ABOVE her feet
        if not s:
            break                       # the top floor: no way up
        if not p.walk_to(s[0]):
            if report:
                print(f"      could not reach the ladder at tile {s[0]} on "
                      f"row {r0}, stopped at {p.column()}")
            break
        was = p.byte("FRAME_COUNT")
        r1 = p.climb_up()
        alive = p.byte("FRAME_COUNT") != was
        if report:
            print(f"      floor {r0:2d} -> {r1:2d}   WY {p.word('KARA_WY'):4d}  "
                  f"view ({p.byte('WORLD_X')},{p.byte('WORLD_CR')})  "
                  f"HP {p.byte('PLAYER_HP')}  keys {p.byte('KEYS_COUNT')}  "
                  f"ammo {p.byte('AMMO_RESERVE')}")
        if not alive:
            if report:
                print(f"      *** the machine stopped: PC &{p.m.pc:04X}")
            break
        if r1 == r0:
            break
        landings.append(r1)
    return landings, alive


class Clock:
    """Hardware frames and game frames counted side by side, which is the
    loop's own lock (CLAUDE.md 9) - and the highest screen line her box
    reached while they were counted."""

    def __init__(self, p):
        self.p, self.hw, self.game, self.top = p, 0, 0, 255
        sync(p.m, p.sym, half=0)        # anchored: CLAUDE.md 10
        self.last = p.byte("FRAME_COUNT")

    def run(self, n=1):
        for _ in range(n):
            self.p.m.run_frames(1)
            self.hw += 1
            now = self.p.byte("FRAME_COUNT")
            self.game += (now - self.last) & 255
            self.last = now
            y = self.p.byte("KARA_Y")               # 192-255 is ABOVE it
            self.top = min(self.top, y - 256 if y >= 192 else y)


def climb_rock(p, clock, steps=None, floors=(), report=True):
    """Up the level by JUMPING, which is the only way level 11 has.

    Nothing here knows where a step is: the one to go for is the run of
    platform two rows above her feet, read out of the level's own map
    through TILE_ATTR. She walks until her six-byte box OVERHANGS it and
    jumps straight up - which is the geometry the level is built on,
    each step starting in the column after the last one ends."""
    landings = [p.row()]
    for _ in range(steps or p.h):
        r0 = p.row()
        runs = p.platforms(r0 - 2)
        if not runs:
            break                       # the top floor: nothing above
        x = p.word("KARA_WX")
        a, b = min(runs, key=lambda r: min(abs(r[0] * 4 - x),
                                           abs(r[1] * 4 - x)))
        for _ in range(900):
            x = p.word("KARA_WX")
            if (x + 5) // 4 >= a and x // 4 <= b:
                break
            p.m.joystick(JOY["right"] if (x + 5) // 4 < a else JOY["left"])
            clock.run()
        p.m.joystick(0)
        clock.run(2)
        p.m.joystick(JOY["up"])         # a PRESS: a held UP does not re-jump
        clock.run(4)
        p.m.joystick(0)
        was, still = p.word("KARA_WY"), 0
        for _ in range(300):
            clock.run()
            now = p.word("KARA_WY")
            still = still + 1 if now == was else 0
            was = now
            if still >= 20:
                break
        r1 = p.row()
        if report and (r1 in floors or r1 == r0):
            print(f"      row {r0:2d} -> {r1:2d}   WY {p.word('KARA_WY'):4d}  "
                  f"view ({p.byte('WORLD_X')},{p.byte('WORLD_CR')})  "
                  f"HP {p.byte('PLAYER_HP')}  keys {p.byte('KEYS_COUNT')}  "
                  f"ammo {p.byte('AMMO_RESERVE')}")
        if r1 == r0:
            break
        landings.append(r1)
    return landings


def off_the_step(p):
    """Walk off the end of the step she is on - the end AWAY from the
    step below, so nothing catches her before the floor - and what the
    machine measured the fall as: FALL_TOP is where it began, frozen
    the instant she started down (8.4)."""
    x = p.word("KARA_WX")               # her box, not her middle: she
    here = [r for r in p.platforms(p.row())         # may be standing
            if r[0] <= (x + 5) // 4 and x // 4 <= r[1]]  # on the overhang
    below = p.platforms(p.row() + 2)
    go = JOY["right"] if below and below[0][1] < here[0][0] else JOY["left"]
    start, hp, began = p.row(), p.byte("PLAYER_HP"), None
    for _ in range(400):
        if p.row() > start:
            began = p.word("FALL_TOP")
            break
        p.m.joystick(go)
        p.m.run_frames(1)
    p.m.joystick(0)
    landed = p.settle()
    return start, landed, p.word("KARA_WY") - began, hp - p.byte("PLAYER_HP")


def fall_free_sites(p):
    """The two immediates FALL_FREE is written into in FALL_DAMAGE -
    `cp FALL_FREE + 1` and `sub FALL_FREE` - found by their bytes."""
    a, free = p.sym["FALL_DAMAGE"], p.sym["FALL_FREE"]
    code = bytes(p.m.read_ram(a, 48))
    i = code.find(bytes([0xFE, free + 1, 0xD8, 0xD6, free]))
    return (a + i + 1, a + i + 4) if i >= 0 else None


# ---------------------------------------------------------------------
# The action set, per environment - the bug the climb found.
# ---------------------------------------------------------------------
def banks_inc():
    out = {}
    path = os.path.join(BUILD, "levels", "banks.inc")
    for line in open(path):
        parts = line.split()
        if len(parts) >= 3 and parts[1] == "equ" and parts[2].startswith("&"):
            out[parts[0]] = int(parts[2][1:], 16)
    return out


def kact_row(m, sym, env):
    """What KARA_SETS' action row holds after KACT_FOR_ENV has run."""
    m.poke(sym["LEVEL_ENV"], env)
    a = sym["KACT_FOR_ENV"]
    m.write_ram(STUB, bytes([0xF3, 0xCD, a & 255, a >> 8, 0x18, 0xFE]))
    m.set_pc(STUB)
    for _ in range(40000):
        if m.pc == STUB + 4:
            break
        m.run_us(1)
    else:
        raise SystemExit(f"KACT_FOR_ENV never returned for environment {env}")
    return tuple(m.peek(sym["KACT_ROW"] + i) for i in range(6))


def kact_want(b, n):
    """What the level's own allocation put there, out of banks.inc."""
    return (b[f"L{n}_KACT_BANK"], b[f"L{n}_KACT_ADDR"] & 255,
            b[f"L{n}_KACT_ADDR"] >> 8,
            b[f"L{n}_KACT_L_BANK"], b[f"L{n}_KACT_L_ADDR"] & 255,
            b[f"L{n}_KACT_L_ADDR"] >> 8)


def descend(p, report=True):
    """Down every ladder the level has, and what it cost her."""
    landings, alive = [p.row()], True
    for _ in range(p.h // 4):
        r0 = p.row()
        s = p.shafts(r0)                # descending: the rungs in HER row
        if not s:
            break                       # the bottom floor: no way down
        if not p.walk_to(s[0]):
            if report:
                print(f"      could not reach the ladder at tile {s[0]} on "
                      f"row {r0}, stopped at {p.column()}")
            break
        was = p.byte("FRAME_COUNT")
        r1 = p.climb_down()
        alive = p.byte("FRAME_COUNT") != was
        if report:
            print(f"      floor {r0:2d} -> {r1:2d}   WY {p.word('KARA_WY'):4d}  "
                  f"view ({p.byte('WORLD_X')},{p.byte('WORLD_CR')})  "
                  f"HP {p.byte('PLAYER_HP')}  keys {p.byte('KEYS_COUNT')}  "
                  f"ammo {p.byte('AMMO_RESERVE')}")
        if not alive or r1 == r0:
            break
        landings.append(r1)
    return landings, alive


def main():
    sym = symbols()
    print("Level 9: the cave\n")

    p = Play(sym)
    check("the transition installs it", p.frames is not None,
          f"{p.frames} hardware frames - an environment change, so 1.6 s "
          f"of art came with it")
    check("and it is the shape the header asks for",
          (p.w, p.h, p.tileset) == (MAP_W, MAP_H, ENV)
          and p.byte("LEVEL_OK") == 1,
          f"{p.w}x{p.h}, tileset {p.tileset}, LEVEL_OK {p.byte('LEVEL_OK')}, "
          f"LEVEL_ENV {p.byte('LEVEL_ENV')}")

    floors = p.floors()
    ladders = {r: p.shafts(r) for r in floors if p.shafts(r)}
    check("the engine reads eight floors", len(floors) == 8,
          f"rows {floors}")
    check("... and a ladder on every one but the bottom",
          len(ladders) == 7 and all(len(c) == 1 for c in ladders.values()),
          f"{ {r: c[0] for r, c in ladders.items()} }")
    check("... and the column moves, so every floor has to be WALKED",
          len({c[0] for c in ladders.values()}) == 7,
          "seven floors, seven different columns")

    check("she starts on the bottom floor",
          p.row() == floors[-1] and p.byte("WORLD_CR") == V_CR_MAX,
          f"row {p.row()}, WORLD_CR {p.byte('WORLD_CR')} of {V_CR_MAX} - "
          f"the deepest a 64-row map's view goes")

    print("    the climb:")
    landings, alive = ascend(p)
    check("the machine survives the climb", alive,
          "the `climb` cels come out of THIS environment's own kact blob")
    check("she climbs every floor to the top",
          landings == sorted(floors, reverse=True),
          f"{landings}")
    check("... and the view goes the whole way with her",
          p.byte("WORLD_CR") == 0,
          f"WORLD_CR {V_CR_MAX} -> {p.byte('WORLD_CR')}, which is the "
          f"whole map")
    check("... picking up the clip and the key on the way",
          p.byte("KEYS_COUNT") == 1 and p.byte("AMMO_RESERVE") == 42,
          f"keys {p.byte('KEYS_COUNT')}, reserve {p.byte('AMMO_RESERVE')}")

    door = None
    ents = p.m.read_ram(sym["ENT_TABLE"], p.byte("ENT_COUNT") * 8)
    for i in range(p.byte("ENT_COUNT")):
        r = ents[i * 8:i * 8 + 8]
        if r[0] == 6:                   # EK_DOOR
            door = (r[1] | r[2] << 8) // 8
    check("the gate is a record and not a wall", door is not None,
          f"EK_DOOR at tile {door} - its own tiles carry no attributes, "
          f"which is 8.8's garage lesson")
    p.walk_to(door)
    before = p.byte("GAME_STATE")
    p.m.joystick(JOY["up"])
    p.m.run_frames(4)
    p.m.joystick(0)
    p.m.run_frames(20)
    check("... and the key opens it",
          before == 0 and p.byte("GAME_STATE") == GS_CLEAR,
          f"GAME_STATE {before} -> {p.byte('GAME_STATE')}, "
          f"ENT_RESULT {p.byte('ENT_RESULT')}")

    # -----------------------------------------------------------------
    # AND THROUGH IT IS LEVEL 10, which is where that gate has pointed
    # since the day it was placed: LEVEL_GOTO goes to LEVEL_CUR + 1 and
    # levels 9-12 are one environment, so it is a map read of one
    # sector and no art at all.
    # -----------------------------------------------------------------
    print("\n  ... and through the gate:")
    env_before = p.byte("LEVEL_ENV")
    moved = None
    for f in range(900):
        p.m.run_frames(1)
        if (p.byte("GAME_STATE") == 0 and p.byte("LEVEL_CUR") == NEXT - 1):
            moved = f
            p.m.run_frames(10)
            break
    check("level 9's gate leads to level 10", moved is not None,
          f"{moved} hardware frames")
    check("... and no art came with it",
          p.byte("LEVEL_ENV") == env_before,
          f"LEVEL_ENV {env_before} either side - one sector, not 1.6 s")

    p.reread()
    p.level = NEXT
    floors10 = p.floors()
    ladders10 = {r: p.shafts(r) for r in floors10 if p.shafts(r)}
    holes10 = {r: p.holes(r) for r in floors10 if p.holes(r)}
    check("it is the same shape and the same tileset",
          (p.w, p.h, p.tileset) == (MAP_W, MAP_H, ENV),
          f"{p.w}x{p.h}, tileset {p.tileset}")
    check("she is on the TOP floor this time",
          p.row() == floors10[0] and p.byte("WORLD_CR") == 0,
          f"row {p.row()}, WORLD_CR {p.byte('WORLD_CR')} - level 9 started "
          f"at row {MAP_H - 2} with the view at {V_CR_MAX}")
    check("a ladder off every floor but the bottom",
          len(ladders10) == 7 and all(len(c) == 1 for c in ladders10.values())
          and len({c[0] for c in ladders10.values()}) == 7,
          f"{ {r: c[0] for r, c in ladders10.items()} }")
    check("... and a HOLE in every one of them too",
          len(holes10) == 7 and set(holes10) == set(ladders10),
          f"{ {r: c[0] for r, c in holes10.items()} } - three tiles, "
          f"which is BOX_SOLID_V's number (8.8)")

    # THE DOORWAY SHE CAME THROUGH IS OPEN AND THE ONE SHE IS GOING TO
    # IS SHUT, and that is in the bytes: the open one's two door cells
    # are COMPOSITES - gate_open_l/gate_open_r baked over the cave
    # behind them - and the shut one's are the artist's own plain
    # tiles. Neither carries an attribute, because a door is a record.
    sheet_tiles = len(json.load(open(os.path.join(
        ART, "tile_table.json")))["sheets"][0]["tiles"])
    door10 = None
    ents10 = p.m.read_ram(sym["ENT_TABLE"], p.byte("ENT_COUNT") * 8)
    for i in range(p.byte("ENT_COUNT")):
        r = ents10[i * 8:i * 8 + 8]
        if r[0] == 6:
            door10 = (r[1] | r[2] << 8) // 8
    gate_col = door10 - 1
    shut = [p.map[(floors10[-1] - 1) * p.w + gate_col + i] for i in (1, 2)]
    openx = [p.map[(floors10[0] - 1) * p.w + gate_col + i] for i in (1, 2)]
    check("the gate she came through is drawn OPEN",
          all(x >= sheet_tiles for x in openx)
          and all(x < sheet_tiles for x in shut) and openx != shut,
          f"the doorway at the top is {openx} - composited, past the "
          f"sheet's {sheet_tiles} - against {shut} at the bottom")
    check("... and neither is something the physics stops her at",
          all(p.attr[x] == 0 for x in openx + shut),
          "a shut door is an EK_DOOR with EF_SOLID, not a wall (8.8)")

    print("    the descent, by ladder:")
    hp0 = p.byte("PLAYER_HP")
    landings10, alive10 = descend(p)
    check("the machine survives the descent", alive10)
    check("she goes down every floor to the bottom",
          landings10 == floors10, f"{landings10}")
    check("... and the ladders cost her nothing",
          p.byte("PLAYER_HP") == hp0,
          f"HP {hp0} -> {p.byte('PLAYER_HP')} - the free way down")
    check("... picking up the clip and the key on the way",
          p.byte("KEYS_COUNT") == 1 and p.byte("AMMO_RESERVE") == 56,
          f"keys {p.byte('KEYS_COUNT')}, reserve {p.byte('AMMO_RESERVE')} - "
          f"42 crossed the door from level 9 and this level's clip is the "
          f"third; the KEY did not cross, which is why there is one here")

    p.walk_to(door10)
    before = p.byte("GAME_STATE")
    p.m.joystick(JOY["up"])
    p.m.run_frames(4)
    p.m.joystick(0)
    p.m.run_frames(20)
    check("the key opens the gate at the bottom",
          before == 0 and p.byte("GAME_STATE") == GS_CLEAR,
          f"GAME_STATE {before} -> {p.byte('GAME_STATE')}")

    # -----------------------------------------------------------------
    # AND THROUGH THAT ONE IS LEVEL 11: UP AGAIN, BY THE ROCK. plan.md
    # names the cave's mechanic as a climb on platforms and stalagmites
    # and level 9 climbed ladders; this one has none at all. Between
    # every pair of floors is a stalagmite and two ledges, each two rows
    # above the last - 32 lines against a jump of 36 - so the way up is
    # twenty-eight jumps, and the vertical camera follows JUMPS for the
    # first time rather than a ladder or a fall.
    # -----------------------------------------------------------------
    print("\n  ... and through it, level 11:")
    env_before, moved = p.byte("LEVEL_ENV"), None
    for f in range(900):
        p.m.run_frames(1)
        if p.byte("GAME_STATE") == 0 and p.byte("LEVEL_CUR") == THIRD - 1:
            moved = f
            p.m.run_frames(10)
            break
    check("level 10's gate leads to level 11", moved is not None,
          f"{moved} hardware frames")
    check("... and no art came with it", p.byte("LEVEL_ENV") == env_before,
          f"LEVEL_ENV {env_before} either side")

    p.reread()
    p.level = THIRD
    floors11 = p.floors()
    check("she is on the BOTTOM floor again",
          len(floors11) == 8 and p.row() == floors11[-1]
          and p.byte("WORLD_CR") == V_CR_MAX,
          f"row {p.row()} of floors {floors11}, WORLD_CR "
          f"{p.byte('WORLD_CR')} - she came through level 10's gate at "
          f"the bottom")
    check("... and there is no ladder in it at all",
          not any(p.shafts(r) for r in range(p.h)),
          "TA_CLIMB on none of its 2,048 cells - the rock is the way up")

    # A STAIRCASE, READ OFF THE MAP: between each pair of floors, one
    # run of platform two, four and six rows above the lower one - a
    # single tile and then two of three - each starting in the column
    # after the last ends, which is what lets a jump straight up reach
    # it (make_cave_map.py's own argument, BOX_SOLID_V's number).
    stairs, shaped = {}, True
    for upper, lower in zip(floors11, floors11[1:]):
        runs = [p.platforms(lower - k) for k in (2, 4, 6)]
        stairs[lower] = runs
        if any(len(r) != 1 for r in runs):
            shaped = False
            continue
        (s0, s1, s2) = (r[0] for r in runs)
        widths = [b - a + 1 for a, b in (s0, s1, s2)]
        touch = all(n[0] == o[1] + 1 or n[1] == o[0] - 1
                    for o, n in ((s0, s1), (s1, s2)))
        shaped &= widths == [1, 3, 3] and touch
    check("... and a staircase between every pair of floors", shaped
          and len(stairs) == 7,
          f"{ {r: [s[0] for s in st if s] for r, st in stairs.items()} } - "
          f"a stalagmite and two ledges, each two rows up and one column on")
    feet = [st[0][0][0] for st in stairs.values() if st[0]]
    check("... with its foot somewhere else on every floor",
          len(set(feet)) == 7, f"stalagmites at columns {feet}")

    # THE DOORWAYS: the pillars are the artist's own tiles, so they are
    # found by name and what is BETWEEN them is compared.
    names = [t["name"] for t in json.load(open(os.path.join(
        ART, "tile_table.json")))["sheets"][0]["tiles"]]
    pl, pr = names.index("gate_pillar_l"), names.index("gate_pillar_r")

    def doorway(row):
        for x in range(p.w - 3):
            if (p.map[row * p.w + x] == pl
                    and p.map[row * p.w + x + 3] == pr):
                return [p.map[row * p.w + x + i] for i in (1, 2)]
        return None
    bottom, top = doorway(floors11[-1] - 1), doorway(floors11[0] - 1)
    check("the gate she came through is OPEN, at the bottom this time",
          bottom and top and all(x >= sheet_tiles for x in bottom)
          and all(x < sheet_tiles for x in top),
          f"{bottom} between the pillars at the bottom - composited, past "
          f"the sheet's {sheet_tiles} - against {top} at the top")

    print("    the climb, by jumping:")
    hp0, ammo0 = p.byte("PLAYER_HP"), p.byte("AMMO_RESERVE")
    clock = Clock(p)
    landings11 = climb_rock(p, clock, floors=floors11)
    check("she jumps every step to the top",
          landings11 == list(range(floors11[-1], floors11[0] - 1, -2)),
          f"{len(landings11) - 1} jumps, row {landings11[0]} -> "
          f"{landings11[-1]}, every one exactly two rows")
    check("... and the view goes the whole way with her",
          p.byte("WORLD_CR") == 0,
          f"WORLD_CR {V_CR_MAX} -> {p.byte('WORLD_CR')}")
    # A JUMP IS THE FASTEST THING SHE DOES UPWARD - 36 lines in four
    # game frames, where a ladder is two lines a frame - so it is the
    # first thing that could carry her off the top of the picture
    # before CAMERA_V's row steps (three game frames each) catch up.
    check("... and the camera keeps her on the screen",
          0 <= clock.top < 192,
          f"the highest her box went was screen line {clock.top} - a "
          f"negative number would be her head clipped off the top")
    check("... without the loop dropping a frame",
          abs(clock.hw // 2 - clock.game) <= 1,
          f"{clock.game} game frames in {clock.hw} hardware ones - a jump "
          f"cel and the incoming ROW on the same frames, which nothing "
          f"before this level put together")
    ents11 = p.m.read_ram(sym["ENT_TABLE"], p.byte("ENT_COUNT") * 8)
    kit = [r for r in (ents11[i * 8:i * 8 + 8]
                       for i in range(p.byte("ENT_COUNT")))
           if r[0] == 4 and r[6] == 2]              # EK_PICKUP, PU_MEDKIT
    check("... picking up the clip and the key on the way",
          p.byte("KEYS_COUNT") == 1
          and p.byte("AMMO_RESERVE") == ammo0 + 14,
          f"keys {p.byte('KEYS_COUNT')}, reserve {ammo0} -> "
          f"{p.byte('AMMO_RESERVE')}")
    check("... and nothing she did cost her a point",
          p.byte("PLAYER_HP") == hp0 and kit and not kit[0][5] & 2,
          f"HP {hp0} -> {p.byte('PLAYER_HP')}, and the medkit she walked "
          f"past is still on the floor: at full health it is refused (8.6)")

    door11 = None
    for i in range(p.byte("ENT_COUNT")):
        r = ents11[i * 8:i * 8 + 8]
        if r[0] == 6:
            door11 = (r[1] | r[2] << 8) // 8
    p.walk_to(door11)
    before = p.byte("GAME_STATE")
    p.m.joystick(JOY["up"])
    p.m.run_frames(4)
    p.m.joystick(0)
    p.m.run_frames(20)
    check("the key opens the gate at the top",
          before == 0 and p.byte("GAME_STATE") == GS_CLEAR,
          f"GAME_STATE {before} -> {p.byte('GAME_STATE')}")

    # -----------------------------------------------------------------
    # AND THROUGH THAT ONE IS LEVEL 12, THE CAVE'S LAST: after the
    # earthquake plan.md ends the environment with. The bottom of the
    # shaft is under water, the walls are cracked and pouring, three of
    # the six ladders are broken - and she comes in at the TOP, through
    # level 11's gate, and goes DOWN to the last dry floor.
    # -----------------------------------------------------------------
    print("\n  ... and through it, level 12:")
    env_before, moved = p.byte("LEVEL_ENV"), None
    for f in range(900):
        p.m.run_frames(1)
        if p.byte("GAME_STATE") == 0 and p.byte("LEVEL_CUR") == FOURTH - 1:
            moved = f
            p.m.run_frames(10)
            break
    check("level 11's gate leads to level 12", moved is not None
          and p.byte("LEVEL_ENV") == env_before,
          f"{moved} hardware frames, LEVEL_ENV {env_before} either side")
    p.reread()
    p.level = FOURTH
    floors12 = p.floors()
    check("she is on the TOP floor, and there are SEVEN",
          len(floors12) == 7 and p.row() == floors12[0]
          and p.byte("WORLD_CR") == 0,
          f"floors {floors12}, row {p.row()}, WORLD_CR {p.byte('WORLD_CR')}")

    # THE EARTHQUAKE'S TILES ARE THE CAVE'S TILESET NOW. They were a
    # blob of their own at an address no map could name; the tileset is
    # both sheets (build_levels.one_tileset), so a cell holds one. Found
    # by name - the table is the artist's - and checked for what the
    # ENGINE reads under them.
    both = [t["name"] for sh in json.load(open(os.path.join(
        ART, "tile_table.json")))["sheets"][:2] for t in sh["tiles"]]
    flood, cracks = both.index("flood_1"), [both.index(f"crack_{k}")
                                            for k in (1, 2, 3, 4)]
    below = [p.map[r * p.w + x] for r in range(floors12[-1] + 2, p.h)
             for x in range(p.w) if not p.attr[p.map[r * p.w + x]]]
    surface = [p.map[(floors12[-1] + 1) * p.w + x] for x in range(p.w)
               if not p.attr[p.map[(floors12[-1] + 1) * p.w + x]]]
    check("the eighth floor is under water",
          below and set(below) == {flood} and len(surface) >= 20
          and all(c >= len(both) for c in surface),
          f"{len(below)} cells of flood_1 (tile {flood}) under a row of "
          f"{len(surface)} composited surface cells, and none of them "
          f"carries an attribute")
    cracked = [(r, x) for r in range(p.h) for x in range(p.w)
               if p.map[r * p.w + x] in cracks]
    check("the walls are cracked, and a crack is still wall",
          cracked and all(p.attr[p.map[r * p.w + x]] & TA_SOLID
                          for r, x in cracked),
          f"{len(cracked)} cracked cells, every one TA_SOLID")
    bottom, top = doorway(floors12[-1] - 1), doorway(floors12[0] - 1)
    check("the gate she came through is OPEN, at the top",
          bottom and top and all(x >= sheet_tiles for x in top)
          and all(x < sheet_tiles for x in bottom),
          f"{top} at the top against {bottom} at the bottom")

    # THE LADDERS, AND HOW MUCH OF EACH IS LEFT - read off the map: the
    # rungs from a floor's own row down to the first cell that is not
    # one. Eight is a whole ladder; fewer is one the earthquake broke.
    lengths = {}
    for r in floors12[:-1]:
        s = p.shafts(r)
        n = 0
        while s and p.attr[p.map[(r + n) * p.w + s[0]]] & TA_CLIMB:
            n += 1
        lengths[r] = n
    broken = {r: n for r, n in lengths.items() if n < 8}
    check("a ladder off every floor, and the earthquake broke three",
          len(lengths) == 6 and len(broken) == 3,
          f"rungs per floor {lengths}")

    print("    the descent:")
    hp0, falls12, landings12 = p.byte("PLAYER_HP"), {}, [p.row()]
    ammo12 = p.byte("AMMO_RESERVE")
    for _ in range(8):
        r0, s = p.row(), p.shafts(p.row())
        if not s or not p.walk_to(s[0]):
            break
        r1, fell = p.down_and_measure()
        print(f"      floor {r0:2d} -> {r1:2d}   ladder of {lengths.get(r0)} "
              f"rungs   fell {fell}   HP {p.byte('PLAYER_HP')}   "
              f"keys {p.byte('KEYS_COUNT')}   ammo {p.byte('AMMO_RESERVE')}")
        if r1 == r0:
            break
        falls12[r0] = fell
        landings12.append(r1)
    check("she goes down every floor to the last dry one",
          landings12 == floors12, f"{landings12}")
    check("a broken ladder is a fall from where it ENDS",
          all(falls12.get(r) == (8 - n) * 16 for r, n in broken.items())
          and all(falls12.get(r) is None for r in lengths if r not in broken),
          f"{ {r: falls12.get(r) for r in broken} } lines, against "
          f"{ {r: (8 - n) * 16 for r, n in broken.items()} } read off the "
          f"map - FALL_TOP froze at the last rung, and the whole ladders "
          f"were no fall at all")
    check("... and none of them costs her a point",
          p.byte("PLAYER_HP") == hp0,
          f"HP {hp0} -> {p.byte('PLAYER_HP')} - the shortest stub is two "
          f"rungs, 96 lines, which is FALL_FREE")
    check("... and the clip and the key are on the way",
          p.byte("KEYS_COUNT") == 1
          and p.byte("AMMO_RESERVE") == ammo12 + 14,
          f"keys {p.byte('KEYS_COUNT')}, reserve {ammo12} -> "
          f"{p.byte('AMMO_RESERVE')}")

    door12 = None
    ents12 = p.m.read_ram(sym["ENT_TABLE"], p.byte("ENT_COUNT") * 8)
    for i in range(p.byte("ENT_COUNT")):
        r = ents12[i * 8:i * 8 + 8]
        if r[0] == 6:
            door12 = (r[1] | r[2] << 8) // 8
    p.walk_to(door12)
    before = p.byte("GAME_STATE")
    p.m.joystick(JOY["up"])
    p.m.run_frames(4)
    p.m.joystick(0)
    p.m.run_frames(20)
    check("the key opens the last gate, over the water",
          before == 0 and p.byte("GAME_STATE") == GS_CLEAR,
          f"GAME_STATE {before} -> {p.byte('GAME_STATE')}")

    # AND THAT IS THE END OF THE CAVE: level 13 is the undersea's first
    # and nobody has painted it, so LEVEL_GOTO refuses and the game
    # starts again from the title (8.1) - a full reset, not a door.
    back = None
    for f in range(1400):
        p.m.run_frames(1)
        if p.byte("LEVEL_CUR") == 0 and p.byte("GAME_STATE") == 0:
            back = f
            break
        if f > 200:
            p.m.joystick(0x10)
            p.m.run_frames(2)
            p.m.joystick(0)
    check("... and past it is the title, because level 13 is not painted",
          back is not None and p.byte("PLAYER_HP") == 100,
          f"back on level 1 after {back} hardware frames, HP "
          f"{p.byte('PLAYER_HP')}")

    # -----------------------------------------------------------------
    # A MISS COSTS THE HEIGHT AND NOT A POINT, and that is a number and
    # not a hope: the highest step of a staircase is six rows above the
    # floor below it, 96 lines, which is FALL_FREE exactly - and a fall
    # costs only the excess (8.4). The machine's own FALL_TOP says how
    # far she fell, so the check is on the measurement and not on the
    # map. Its control is the threshold one line lower in FALL_DAMAGE's
    # own two immediates: the same walk off the same step then costs
    # exactly one point, which is what says the fall was 96 and not
    # something shorter that would be free anyway.
    # -----------------------------------------------------------------
    print("\n  off the top step of a staircase:")
    falls = []
    for lower in (False, True):
        q = Play(sym, level=THIRD)
        sites = fall_free_sites(q)
        if lower and sites:
            q.m.poke(sites[0], sym["FALL_FREE"])
            q.m.poke(sites[1], sym["FALL_FREE"] - 1)
        climb_rock(q, Clock(q), steps=3, report=False)
        falls.append(off_the_step(q))
        a, b, d, cost = falls[-1]
        print(f"      {'FALL_FREE - 1' if lower else 'as shipped   '}  "
              f"row {a} -> {b}, {d} lines, {cost} points")
    check("the top step is FALL_FREE above the floor, and falling off "
          "it is free",
          falls[0][2] == sym["FALL_FREE"] and falls[0][3] == 0
          and falls[0][1] - falls[0][0] == 6,
          f"{falls[0][2]} lines measured by FALL_TOP, against FALL_FREE "
          f"{sym['FALL_FREE']}: {falls[0][3]} points")
    check("... and with the threshold one line lower it costs one",
          sites is not None and falls[1][2] == falls[0][2]
          and falls[1][3] == 1,
          f"{falls[1][3]} point(s) for the same {falls[1][2]} lines - the "
          f"fall is AT the boundary, not under it")

    # -----------------------------------------------------------------
    # And the control for the climb: TA_PLATFORM taken off the
    # stalagmite's top in the table the engine reads. The driver keeps
    # its OWN copy, so it still walks her to the stalagmite and still
    # jumps - and the ledge above that is four rows up, 64 lines, where
    # her jump reaches 36.
    # -----------------------------------------------------------------
    # -----------------------------------------------------------------
    # The control for level 12's broken ladders: FALL_MARK poked to RET,
    # so the mark no longer follows her down the rungs. The same stub
    # is then measured from wherever FALL_TOP was last set - her start,
    # at the top of the level - and a fall that was free is not.
    # -----------------------------------------------------------------
    print("\n  control - FALL_MARK poked to RET, on level 12:")
    k = Play(sym, level=FOURTH)
    k.m.poke(sym["FALL_MARK"], 0xC9)
    fell_k = hp_k = None
    entered = k.word("KARA_WY")
    for _ in range(4):
        s = k.shafts(k.row())
        if not s or not k.walk_to(s[0]):
            break
        r0 = k.row()
        r1, fell_k = k.down_and_measure()
        hp_k = k.byte("PLAYER_HP")
        print(f"      floor {r0:2d} -> {r1:2d}   fell {fell_k}   HP {hp_k}")
        if fell_k is not None:
            break
    check("... without it, the first broken ladder is a fall from the "
          "top of the level",
          fell_k == k.word("KARA_WY") - entered and hp_k < 100,
          f"{fell_k} lines - exactly from where she entered the level to "
          f"where she landed - and HP {hp_k}, where as shipped it was "
          f"{(8 - broken[min(broken)]) * 16} and nothing")

    print("\n  control - TA_PLATFORM off the stalagmite's top in TILE_ATTR:")
    c11 = Play(sym, level=THIRD)
    foot = c11.platforms(c11.row() - 2)[0][0]
    tip = c11.map[(c11.row() - 2) * c11.w + foot]
    c11.m.poke(sym["TILE_ATTR"] + tip, c11.attr[tip] & ~TA_PLATFORM)
    stuck = climb_rock(c11, Clock(c11), steps=2)
    check("she cannot leave the bottom floor",
          stuck == [floors11[-1]],
          f"{stuck} - the map is the same map; a stalagmite whose top is "
          f"not a floor is scenery")

    # -----------------------------------------------------------------
    # AND THE HOLE IS THE OTHER WAY DOWN, WHICH COSTS. 128 world lines
    # against FALL_FREE of 96 is 32 of her 100 points, at a point a
    # pixel (8.4) - the same arithmetic as the City's roof gap, and
    # the first CHOICE this environment has ever offered.
    # -----------------------------------------------------------------
    print("\n  the other way down - the holes:")
    h = Play(sym, level=NEXT)
    floors_h = h.floors()
    drops, hp = [], h.byte("PLAYER_HP")
    for r in floors_h[:3]:
        col = h.holes(r)[0] + 1
        before = h.byte("PLAYER_HP")
        landed = h.walk_off(col)
        drops.append((r, landed, before - h.byte("PLAYER_HP")))
        print(f"      floor {r:2d} -> {landed:2d}  through the hole at tile "
              f"{col - 1}   HP {before} -> {h.byte('PLAYER_HP')}")
    check("a hole drops her exactly one floor",
          all(b - a == 8 for a, b, _ in drops), f"{[(a, b) for a, b, _ in drops]}")
    check("... and each one costs her 32 points",
          all(c == 32 for _, _, c in drops),
          f"{[c for _, _, c in drops]} - 128 world lines less FALL_FREE's "
          f"96, at a point a pixel, which is the City's roof gap exactly")
    check("... so three of them is what a medkit is for",
          h.byte("PLAYER_HP") == hp - 96 and h.byte("PLAYER_HP") > 0,
          f"HP {hp} -> {h.byte('PLAYER_HP')} - a fourth would kill her, "
          f"and the ladders are free")

    # -----------------------------------------------------------------
    # The control: the same level with TA_CLIMB taken out of the table
    # the engine reads. The map does not move and the picture does not
    # change - the ladders simply stop being ladders.
    # -----------------------------------------------------------------
    print("\n  control - TA_CLIMB off every ladder tile in TILE_ATTR:")
    c = Play(sym, climbable=False)
    print("    the climb:")
    landings2, alive2 = ascend(c)
    check("she cannot leave the bottom floor",
          landings2 == [c.floors()[-1]],
          f"{landings2} - and the map is byte for byte the same map")

    # -----------------------------------------------------------------
    # And her action set, which is what the climb was drawn out of.
    # -----------------------------------------------------------------
    # A PLAIN BOOT AND NOT A TRANSITION, which is the difference
    # between measuring the old engine and measuring a leftover.
    # KACT_ROW is written by MAP_INSTALL, so a machine that has been
    # into the cave holds the CAVE's row - and the control below, which
    # pokes the routine out, would then be reading that rather than the
    # L1_KACT_* literals the source shipped. It read 6 of 12 either way
    # until level 10 moved the cave's allocation and the two answers
    # parted company.
    print("\n  her action cels, per environment:")
    b = banks_inc()
    live = boot(sym, scroll=True)
    got = [kact_row(live, sym, i) for i in range(6)]
    want = [kact_want(b, i + 1) for i in range(6)]
    for i, name in enumerate(ENVS):
        g = got[i]
        print(f"    {name:<10} right &{g[0]:02X}:{g[2]:02X}{g[1]:02X}   "
              f"left &{g[3]:02X}:{g[5]:02X}{g[4]:02X}   "
              f"{'ok' if g == want[i] else 'WRONG'}")
    check("every environment's kact is its own", got == want,
          "12 of 12 addresses agree with banks.inc")

    # ... and the control is the engine as it shipped: one answer to six
    # questions, because KARA_SETS held L1_KACT_* literals.
    old = boot(sym, scroll=True)                        # level 1, and only it
    old.poke(sym["KACT_FOR_ENV"], 0xC9)                 # RET
    was = [kact_row(old, sym, i) for i in range(6)]
    wrong = sum(1 for i, r in enumerate(was)
                for k in (0, 3) if r[k:k + 3] != want[i][k:k + 3])
    # HOW MANY IT GOT WRONG IS DERIVED AND NOT WRITTEN DOWN, because the
    # number MOVES: kact is allocated per level, so anything that
    # changes the size of anything in an environment's bank set moves
    # it. Adding level 10's baked tiles to cavetiles.bin - 768 bytes -
    # took this from 6 of 12 to 9. A suite with the old number in it
    # would have reported the engine breaking when nothing had.
    expect = sum(1 for i in range(6)
                 for k in (0, 3) if want[i][k:k + 3] != want[0][k:k + 3])
    check("... and the old engine had ONE answer to the six",
          len(set(was)) == 1 and set(was) == {want[0]} and wrong == expect,
          f"{len(set(was))} distinct answer(s) - level 1's - and it is "
          f"wrong for {wrong} of the 12 addresses, which is what "
          f"banks.inc says it must be")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
