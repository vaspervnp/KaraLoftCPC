#!/usr/bin/env python3
"""Level 9 on a 6128: the cave, and the first SHIPPED level that is tall.

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
from bench import boot, symbols                                # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BUILD = os.path.join(ROOT, "build")
ART = os.path.join(ROOT, "assets", "sprites", "level3_cave")
TA_SOLID, TA_PLATFORM, TA_CLIMB = 1, 2, 8
JOY = {"right": 0x08, "left": 0x04, "up": 0x01, "down": 0x02}
GS_CLEAR = 2
LEVEL, ENV = 9, 3                       # level 9 of 24, environment 3
NEXT = 10                               # ... and where its gate points
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
