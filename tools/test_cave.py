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
import os
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import boot, symbols                                # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BUILD = os.path.join(ROOT, "build")
TA_SOLID, TA_PLATFORM, TA_CLIMB = 1, 2, 8
JOY = {"right": 0x08, "left": 0x04, "up": 0x01, "down": 0x02}
GS_CLEAR = 2
LEVEL, ENV = 9, 3                       # level 9 of 24, environment 3
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

    def __init__(self, sym, climbable=True):
        self.sym = sym
        self.m = m = boot(sym, scroll=True)
        m.poke(sym["LEVEL_CUR"], LEVEL - 2)     # ... so the next one is ours
        m.poke(sym["GAME_STATE"], GS_CLEAR)
        self.frames = None
        for f in range(900):
            m.run_frames(1)
            # THE SYNC IS THE FSM COMING BACK TO PLAY. LEVEL_ENV is
            # claimed BEFORE the read and LEVEL_OK is still 1 from the
            # level being left (8.1), so a driver that waits on either
            # is reading the LAST level's map.
            if (m.peek(sym["GAME_STATE"]) == 0
                    and m.peek(sym["LEVEL_CUR"]) == LEVEL - 1):
                self.frames = f
                m.run_frames(10)
                break
        hdr = m.read_ram(sym["LEVEL_LVL"], 21)
        self.w = hdr[5] | hdr[6] << 8
        self.h = hdr[7] | hdr[8] << 8
        self.tileset = hdr[9]
        self.map = bytes(m.read_ram(sym["LEVEL_LVL"] + 21, self.w * self.h))
        if not climbable:
            self.unclimb()
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
    print("\n  her action cels, per environment:")
    b = banks_inc()
    live = Play(sym)
    got = [kact_row(live.m, sym, i) for i in range(6)]
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
    old = Play(sym)
    old.m.poke(sym["KACT_FOR_ENV"], 0xC9)               # RET
    was = [kact_row(old.m, sym, i) for i in range(6)]
    wrong = sum(1 for i, r in enumerate(was)
                for k in (0, 3) if r[k:k + 3] != want[i][k:k + 3])
    check("... and the old engine had ONE answer to the six",
          len(set(was)) == 1 and wrong == 6,
          f"{len(set(was))} distinct answer(s), {wrong} of 12 addresses "
          f"wrong - the forest got NEITHER facing right and the cave, "
          f"undersea, desert and station only their left one")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
