#!/usr/bin/env python3
"""Level 3 on a 6128: the City's third map, down to the street and up.

Level 2's garage leads here and level 3 opens on it drawn OPEN. Level 2
was the rooftops, where every way on was a jump; this is the street,
where every way on is a CLIMB and a way DOWN. The pavement is cut by a
barricade under every roof but the last, so the only way past one is
that building's ladder and its roof; and between the buildings are
plazas no jump crosses, so the way off a roof is down - walked off,
which costs the height, or hung off the ledge and let go, which is free
(CLAUDE.md 8.8). The key is on the last roof and the way out is a garage
under it.

NOTHING HERE KNOWS WHERE THE GENERATOR PUT ANYTHING. The roofs, the
plazas, the barricades and the ladders are read back out of the level's
own map through the engine's own TILE_ATTR, and she is driven from the
joystick. The two ways down are each other's control: the same edge is
paid for walked off and free hung off, so a rule that charged for
everything fails one and a rule that charged for nothing fails the
other.
"""
import os
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import symbols, sync                                # noqa: E402
import make_city_map as city                                   # noqa: E402
import test_city as tc                                         # noqa: E402
from test_city import (City, JOY, PAVEMENT, V_CR_MAX, EK_PICKUP,  # noqa: E402
                       GS_CLEAR, EF_TAKEN, walk_to, walk_until_stuck,
                       climb_up, window, TA_SOLID, TA_PLATFORM)

BUILD = tc.BUILD
LEVEL = 3
fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


class City3(City):
    """Level 3, in the units the level is written in. A ROOF is the top
    of a building: a crate standing on one is something on the roof, not
    the roof, so it is told apart by the tile's name."""

    def __init__(self, sym, names, drones=False):
        super().__init__(sym, drones=drones, level=LEVEL)
        self.names = names

    def name(self, x, y):
        t = self.map[y * self.w + x]
        return self.names[t] if t < len(self.names) else f"#{t}"

    def building(self, x):
        for y in range(city.ROW_PAVEMENT - 4):
            if (self.a(x, y) & (TA_SOLID | TA_PLATFORM)
                    and self.name(x, y) != "crate"):
                return y
        return None

    def buildings(self):
        """(first column, last column, roof row), west to east."""
        out, x = [], 0
        while x < self.w:
            r = self.building(x)
            if r is None:
                x += 1
                continue
            x0 = x
            while x < self.w and self.building(x) is not None:
                x += 1
            out.append((x0, x - 1, r))
        return out

    def hp(self):
        return self.byte("PLAYER_HP")


def walk_east(c, until, frames=900, jump_stuck=True):
    """Hold RIGHT; when she stops against something one row high, jump.
    Stops when the predicate holds or she stops for good."""
    was, still = c.wx(), 0
    for _ in range(frames):
        if until():
            break
        # FOUR FRAMES STILL, NOT TWO: a dropped game frame with a drone
        # in view is two frames she does not move, and a jump taken for
        # it arrives at a lip in the air, where DOWN is not a ledge.
        press = jump_stuck and still >= 4 and c.byte("KARA_GROUND")
        c.m.joystick(JOY["right"] | (JOY["up"] if press else 0))
        c.step()
        still = still + 1 if c.wx() == was else 0
        was = c.wx()
        if still > 30:
            break
    c.m.joystick(0)
    for _ in range(3):
        c.step()


def to_lip(c, x1):
    """Walk east along a roof to its last column, x1, and stop with her
    box at the lip - test_climb's own place for it."""
    walk_east(c, lambda: c.wx() >= (x1 + 1) * 4 - 7)


def hang_and_drop(c):
    """DOWN at the lip, hold it until she hangs, let it up, press it again
    inside the window - she lets go. Returns (hung, fell, hp0, hp1)."""
    sym = c.sym
    hp0 = c.hp()
    c.m.joystick(JOY["down"])
    for _ in range(sym["HANG_BEAT"] + 4):
        c.step()
    hung = (c.byte("KARA_STATE") == sym["KST_HANG"], c.feet())
    c.m.joystick(0)
    for _ in range(2):
        c.step()
    c.m.joystick(JOY["down"])
    c.step()
    c.m.joystick(0)
    top = None
    for _ in range(200):
        c.step()
        vy = c.byte("KARA_VY")
        if top is None and 0 < vy < 128:
            top = c.word("FALL_TOP")
        if c.byte("KARA_GROUND"):
            break
    for _ in range(3):
        c.step()
    fell = None if top is None else c.feet() - 64 - top
    return hung, fell, hp0, c.hp()


def walk_off(c, x1):
    """Walk east off a roof's last column and land. (fell, hp0, hp1)."""
    hp0, top = c.hp(), None
    c.m.joystick(JOY["right"])
    for _ in range(300):
        c.step()
        vy = c.byte("KARA_VY")
        if not c.byte("KARA_GROUND") and top is None and 0 < vy < 128:
            top = c.word("FALL_TOP")
        if top is not None and c.byte("KARA_GROUND"):
            break
    c.m.joystick(0)
    for _ in range(3):
        c.step()
    fell = None if top is None else c.feet() - 64 - top
    return fell, hp0, c.hp()


def climb_at(c, col):
    """Walk to a ladder's column - jumping what is one row high on the
    way, which walk_to does not - and climb it to the top."""
    if c.col() < col:
        walk_east(c, lambda: c.col() >= col)
    ok = walk_to(c, col)
    return ok, climb_up(c)


def walk_off_west(c, frames=600):
    """Hold LEFT until she has left the ground and landed. (fell, hp0)."""
    hp0, top, air = c.hp(), None, False
    c.m.joystick(JOY["left"])
    for _ in range(frames):
        c.step()
        vy = c.byte("KARA_VY")
        if not c.byte("KARA_GROUND"):
            air = True
            if top is None and 0 < vy < 128:
                top = c.word("FALL_TOP")
        elif air:
            break
    c.m.joystick(0)
    for _ in range(3):
        c.step()
    return (None if top is None else c.feet() - 64 - top), hp0


def main():
    sym = symbols()
    print("Level 3: the City, down to the street and up again\n")
    names = city.tile_names()[1]
    names = names + [f"baked_{i}" for i in range(256 - len(names))]
    shipped = open(os.path.join(BUILD, f"level_{LEVEL}.lvl"), "rb").read()

    c = City3(sym, names)
    print("  out of level 2's garage:")
    check("the garage leads here", c.frames is not None,
          f"{c.frames} hardware frames, fade and all")
    check("... and it is one sector, not an environment",
          c.byte("LEVEL_ENV") == 0 and c.byte("LEVEL_CUR") == LEVEL - 1,
          f"LEVEL_ENV {c.byte('LEVEL_ENV')} - no art came with it")
    check("the level is the file on the disc",
          bytes(c.hdr) + c.map == shipped[:21 + 2048]
          and (c.w, c.h, c.hdr[3], c.hdr[9]) == (128, 16, LEVEL, 1)
          and c.byte("LEVEL_OK") == 1,
          f"{c.w}x{c.h}, level {c.hdr[3]}, tileset {c.hdr[9]}")
    check("the drones are in it", c.spawned == 3,
          f"{c.spawned} spawned, held off for the drive and back on below")
    opening = [x for x in range(c.w - 3)
               if c.name(x + 1, city.ROW_PAVEMENT - 1) == "open_ramp"
               and c.name(x + 2, city.ROW_PAVEMENT - 1) == "open_ramp"]
    g0 = opening[0] if opening else None
    check("it opens on level 2's garage drawn OPEN, and she is out of it",
          g0 is not None and c.feet() == PAVEMENT and c.col() > g0 + 3
          and c.byte("WORLD_CR") == V_CR_MAX,
          f"the open door at {g0}, her feet {c.feet()} at column {c.col()}")

    # ---- the level as the engine reads it --------------------------
    B, bars, ups = c.buildings(), c.barricades(), c.ladders()
    plazas = [(a1 + 1, b0 - a1 - 1) for (_, a1, _), (b0, _, _)
              in zip(B, B[1:])]
    print(f"    roofs {B}")
    print(f"    plazas {plazas}, barricades {bars}, ladders {ups}")
    check("four roofs with an open plaza between each two",
          len(B) == 4 and all(w >= 8 for _, w in plazas),
          f"plazas {[w for _, w in plazas]} tiles wide")
    owns = lambda x: next(i for i, (a, b, _) in enumerate(B) if a <= x <= b)
    check("one ladder a building, on the side she comes from",
          sorted(owns(u) for u in ups) == list(range(len(B))))
    check("... and under every roof but the last, a barricade past it",
          len(bars) == len(B) - 1
          and all(owns(b) == i and ups[i] < b < B[i][1]
                  for i, b in enumerate(bars)),
          "so the street under a roof cannot be walked: the roof is the "
          "way past")

    # ---- the street is cut ------------------------------------------
    print("\n  the street is cut, so the roofs are the only way along:")
    stopped = walk_until_stuck(c, "right")
    check("walking on from the garage, she stops at the first barricade",
          stopped + 6 <= bars[0] * 4,
          f"her box at bytes {stopped}..{stopped + 5}, the crates at "
          f"{bars[0] * 4}")
    cc = City3(sym, names)
    cc.m.poke(sym["TILE_ATTR"] + names.index("crate"), 0)
    gone = walk_until_stuck(cc, "right", frames=200)
    check("... and with the crate's TA_SOLID taken off she walks past it",
          gone > bars[0] * 4 + 8,
          f"to byte {gone} - the barricade stopped her, not the drive")
    del cc

    # ---- the drive, by the ledge ------------------------------------
    print("\n  over every barricade, and down every ledge:")
    sync(c.m, sym, half=0)          # anchored: CLAUDE.md 10
    c.hw = c.game = 0
    keyx = next((r[1] | r[2] << 8) // 8 for r in c.records(EK_PICKUP)
                if r[6] == city.PU_KEY)
    ledges, climbs = [], []
    for i, (x0, x1, r) in enumerate(B):
        ok, top = climb_at(c, ups[i])
        climbs.append(ok and top == r * 16)
        print(f"      up the ladder at {ups[i]:3d} onto row {r}: feet {top}")
        if i == len(B) - 1:
            break
        to_lip(c, x1)
        hung, fell, hp0, hp1 = hang_and_drop(c)
        ledges.append((x1, r, hung, fell, hp0, hp1, c.feet(), c.col()))
        print(f"      off the ledge at {x1:3d}: hung {hung[0]} at feet "
              f"{hung[1]}, fell {fell}, HP {hp0} -> {hp1}, landed feet "
              f"{c.feet()} at column {c.col()}")
    check("up every ladder onto its roof", all(climbs) and len(climbs) == 4,
          f"{climbs}")
    check("off every roof but the last by the ledge",
          len(ledges) == len(B) - 1
          and all(h[0] and h[1] == r * 16 + sym["HANG_DROP"]
                  for _, r, h, *_ in ledges),
          f"hanging with her feet HANG_DROP = {sym['HANG_DROP']} lines below "
          f"each roof: {[l[2][1] for l in ledges]}")
    check("... each one free, and each into the plaza past it",
          all(fell is not None and fell <= city.FALL_FREE and hp0 == hp1
              and feet == PAVEMENT and x1 < col <= x1 + 8
              for x1, _, _, fell, hp0, hp1, feet, col in ledges),
          f"fell {[l[3] for l in ledges]} lines against FALL_FREE "
          f"{city.FALL_FREE}, HP {[l[5] for l in ledges]}")
    walk_east(c, lambda: c.col() >= keyx)
    check("the key at the far end of the last roof",
          c.byte("KEYS_COUNT") == 1, f"keys {c.byte('KEYS_COUNT')}, "
          f"HP {c.hp()}, reserve {c.byte('AMMO_RESERVE')}")
    check("... and the loop held, climbs, drops and columns alike",
          c.hw <= 2 * c.game + 1,
          f"{c.game} game frames in {c.hw} hardware ones")

    # ---- the way out -------------------------------------------------
    print("\n  and the way out:")
    fell, hp0 = walk_off_west(c)
    check("walking off the last roof's near edge is free",
          c.feet() == PAVEMENT and fell is not None
          and fell <= city.FALL_FREE and c.hp() == hp0,
          f"{fell} lines, HP {hp0} -> {c.hp()}, at column {c.col()} - the "
          f"street the way out is on")
    door = next((r[1] | r[2] << 8) // 8 for r in c.records(6))
    walk_to(c, door + 2)
    c.m.joystick(JOY["up"])
    c.step()
    c.m.joystick(0)
    for _ in range(10):
        c.step()
        if c.byte("GAME_STATE"):
            break
    check("UP at the garage with the key opens it",
          c.byte("GAME_STATE") == GS_CLEAR, f"GAME_STATE {c.byte('GAME_STATE')}")
    back = None
    for f in range(1500):
        c.m.run_frames(1)
        if c.byte("LEVEL_CUR") == 0 and c.byte("GAME_STATE") == 0:
            back = f
            break
        if f > 200 and f % 30 == 0:             # the title waits for a press
            c.m.joystick(JOY["fire"])
            c.m.run_frames(2)
            c.m.joystick(0)
    check("... and level 4 is not painted, so the game starts over",
          back is not None and c.hp() == 100
          and c.byte("AMMO_RESERVE") == 28 and c.byte("KEYS_COUNT") == 0,
          f"after {back} hardware frames and a title: HP {c.hp()}, reserve "
          f"{c.byte('AMMO_RESERVE')}")
    del c

    # ---- the other way down: walked off, and what it costs -----------
    print("\n  the other way down - walked off the edge:")
    w = City3(sym, names)
    costs = []
    for i, (x0, x1, r) in enumerate(B[:-1]):
        climb_at(w, ups[i])
        to_lip(w, x1)
        fell, hp0, hp1 = walk_off(w, x1)
        costs.append((x1, r, fell, hp0, hp1))
        print(f"      off the roof at {x1:3d}, row {r}: fell {fell}, HP "
              f"{hp0} -> {hp1}")
    check("every walk off an edge costs the drop past FALL_FREE, by the "
          "machine's own FALL_TOP",
          len(costs) == len(B) - 1
          and all(fell == (city.ROW_PAVEMENT - r) * 16
                  and hp0 - hp1 == city.walk_off_cost(r)
                  for _, r, fell, hp0, hp1 in costs),
          f"{[(c_[2], c_[3] - c_[4]) for c_ in costs]} - (lines, points), "
          f"which is walk_off_cost()'s {[city.walk_off_cost(c_[1]) for c_ in costs]}")
    check("... off the same three lips the ledge was free from",
          [c_[0] for c_ in costs] == [l[0] for l in ledges]
          and all(c_[3] > c_[4] for c_ in costs)
          and all(l[4] == l[5] for l in ledges),
          "the two ways down are each other's control: a rule that charged "
          "for everything fails the ledge, one that charged for nothing "
          "fails this")
    med = [r for r in w.records(EK_PICKUP) if r[6] == city.PU_MEDKIT]
    check("... and walking off all three is survivable, with the medkit",
          w.hp() > 0 and med and med[0][5] & EF_TAKEN,
          f"HP {w.hp()} at the last ladder, the medkit "
          f"{'taken' if med and med[0][5] & EF_TAKEN else 'still there'}")
    del w

    # ---- no jump crosses a plaza -------------------------------------
    print("\n  no jump crosses a plaza, at either stride phase:")
    jm = City3(sym, names)
    across = []
    for (p0, pw), (_, x1, rn), (b0, _, rf) in zip(plazas, B, B[1:]):
        hits = []
        for phase in (0, 1):
            good, ran_off = window(jm, p0, pw, rn, rf, p0 * 4 - 24 + phase)
            hits.append((len(good), ran_off))
        across.append(hits)
        print(f"      plaza at {p0:3d}, {pw} wide, row {rn} -> {rf}: "
              f"{hits[0][0]}/{hits[1][0]} take-offs land past it")
    check("every take-off from every roof comes down in the plaza",
          all(h == (0, False) for hits in across for h in hits),
          "so the way off a roof is down, and the climb is the way on")
    del jm

    # ---- under fire --------------------------------------------------
    print("\n  the same drive with the drones in it:")
    d = City3(sym, names, drones=True)
    for i, (x0, x1, r) in enumerate(B):
        climb_at(d, ups[i])
        if i == len(B) - 1:
            break
        to_lip(d, x1)
        hang_and_drop(d)
    walk_east(d, lambda: d.col() >= keyx)
    check("she crosses the level under fire",
          d.byte("KEYS_COUNT") == 1 and d.hp() > 0,
          f"HP 100 -> {d.hp()}, keys {d.byte('KEYS_COUNT')}")
    del d

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
