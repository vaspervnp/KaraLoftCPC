#!/usr/bin/env python3
"""The cave's gate and its books (CLAUDE.md 8.25), on a 6128.

plan.md's cave is a gate the covers of ancient books open, and the
artist drew all of it: a gate four slots wide - sun, moon, eye, star -
a book of each symbol, each slot with its book in, and two tablets, one
carved sun-and-moon and one eye-and-star. A gate wants the pair ONE
tablet shows, that tablet is on the wall where she comes in, and the
level has all four books: the two the gate does not want are CURSED.

What is checked here, each with the fault that would pass it as its
control:

  * the tablet she reads is the pair her gate wants, in all four levels,
    and the gate she came through has the last level's books in it;
  * every book is drawn as ITS symbol - its cel of cave_books composited
    over the tile under it, against an independent reading of the span
    format - with BOOK_CEL poked to RET as the control, which draws all
    four as the sun;
  * a good book goes into her set and a cursed one costs her a cell and
    is gone - with the curse taken off the record as the control;
  * the lock: nothing in hand, half the pair, and the pair with a book
    over, which it takes and leaves the other; the key it gives; its
    wanted slots moving on to the slot with the book in, on the map and
    on the screen; and TA_ADVANCE taken off them as the control;
  * the second UP is the door, and the lock BEFORE the door is what
    makes that so: swapped, the gate never opens;
  * and a death puts all of it back.

The route - up level 9 for its two books past the cursed ones, and the
same in levels 10 to 12 - is tools/test_cave.py's, which drives every
cave level from the joystick.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_forest7 as F                                        # noqa: E402
from bench import boot                                          # noqa: E402
from test_entities import blob_cel, stamp, peek_c4, screen_cell  # noqa: E402

ROOT = os.path.join(HERE, "..")
BUILD = os.path.join(ROOT, "build")
sys.path.insert(0, HERE)
from make_level import read                                     # noqa: E402
import make_cave_map as CM                                      # noqa: E402

JOY_UP = 0x01
EK_PICKUP, EK_DOOR, EK_RECEPTACLE = 4, 6, 7
EF_TAKEN = 2
PU_BOOK = 5
CURSED = 0x80
SYMBOLS = ("sun", "moon", "eye", "star")
ER_PLACED, ER_WRONG, ER_EMPTY, ER_OPENED = 5, 6, 7, 3
TA_ADVANCE = 128

fails = []
sym = F.symbols()
names = CM.tile_names()
T = {n: i for i, n in enumerate(names)}


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        fails.append(name)


def w(m, a):
    return m.peek(a) | m.peek(a + 1) << 8


def recs(m):
    n = m.peek(sym["ENT_COUNT"])
    raw = m.read_ram(sym["ENT_TABLE"], n * 8)
    return [bytes(raw[i * 8:i * 8 + 8]) for i in range(n)]


def at(r):
    """A record's tile column and the floor row it stands on."""
    return (r[1] | r[2] << 8) // 8, (r[3] | r[4] << 8) // 16


def books(m):
    return [(i, r) for i, r in enumerate(recs(m))
            if r[0] == EK_PICKUP and r[6] == PU_BOOK]


def lock(m):
    return next((i, r) for i, r in enumerate(recs(m)) if r[0] == EK_RECEPTACLE)


def cell(m, col, row):
    return m.peek(sym["MAP_ADDR"] + row * 32 + col)


def pristine(m, col, row):
    """The level image's own byte, which nothing in play writes."""
    return m.peek(sym["LEVEL_LVL"] + 21 + row * 32 + col)


def enter(level, pokes=()):
    """Into `level` through the door of the one before it - with `pokes`
    made BEFORE the install, which is where a bake is decided."""
    m = boot(sym, scroll=True)
    for a, v in pokes:
        m.poke(a, v)
    m.poke(sym["LEVEL_CUR"], level - 2)
    m, took = F.to_level(sym, level, frm=m)
    assert took, f"level {level} never came up"
    m.poke(sym["ENEMY_LIVE"], 0)        # the bats are tools/test_beasts.py's
    return m


def up(m, frames=3):
    """UP for a game frame and let go: the lowest ENT_RESULT seen is
    what the press did (it is cleared every frame, 0 = nothing)."""
    seen = 0
    for k in range(frames):
        F.gframe(m, sym, JOY_UP if k == 0 else 0)
        seen = seen or m.peek(sym["ENT_RESULT"])
    return seen


def stand_at_lock(m):
    """Her box over the lock's tile, standing on its floor - and the
    camera brought to her, which a poke does not do (CLAUDE.md 10)."""
    _, r = lock(m)
    col, row = at(r)
    m.poke(sym["KARA_WX"], (col * 4 - 1) & 255)
    m.poke(sym["KARA_WX"] + 1, (col * 4 - 1) >> 8)
    wy = row * 16 - 64
    m.poke(sym["KARA_WY"], wy & 255)
    m.poke(sym["KARA_WY"] + 1, wy >> 8)
    for _ in range(400):
        F.gframe(m, sym, 0)
        if m.peek(sym["WORLD_CR"]) <= max(0, row - 14):
            break
    for _ in range(10):
        F.gframe(m, sym, 0)
    return col, row


def slots(m, gate_col, gate_row):
    return [cell(m, gate_col + i, gate_row - 5) for i in range(4)]


# ---------------------------------------------------------------------
def tablets():
    print("\n  the tablets and the gates, in the files:")
    ok, seen = True, []
    for L in CM.LAYOUTS:
        lvl = read(open(os.path.join(BUILD, f"level_{L['level']}.lvl"), "rb").read())
        mp = lvl["map"]
        want = CM.TABLETS[tuple(L["wants"])]
        other = [n for n in CM.TABLETS.values() if n != want][0]
        col, floor = L["start"]
        side = CM.WALL_L if col - CM.WALL_L < CM.WALL_R - col else CM.WALL_R
        gc, gr = L["gate"]
        here = [mp[(floor - 2) * 32 + side], mp[(gr - 2) * 32 + CM.WALL_L],
                mp[(gr - 2) * 32 + CM.WALL_R]]
        good = all(x == T[want] for x in here) and T[other] not in mp
        seen.append(f"{L['level']}: {want[6:]}")
        ok = ok and good
    check("each level shows ONE tablet, the pair its gate wants - where she "
          "comes in and beside the gate - and never the other", ok,
          ", ".join(seen))

    ok, seen = True, []
    for prev, L in zip(CM.LAYOUTS, CM.LAYOUTS[1:]):
        mp = read(open(os.path.join(BUILD, f"level_{L['level']}.lvl"), "rb").read())["map"]
        ic, ir = L["entrance"]
        got = [mp[(ir - 5) * 32 + ic + i] for i in range(4)]
        want = [T[f"gate_book_{s}" if s in prev["wants"] else f"gate_slot_{s}"]
                for s in SYMBOLS]
        ok = ok and got == want
        seen.append(f"{L['level']}: {'+'.join(prev['wants'])}")
    check("the gate she came through has the last level's books in it", ok,
          ", ".join(seen))


# ---------------------------------------------------------------------
def pictures():
    print("\n  every book is drawn as its own symbol:")
    blob, sun = blob_cel("level3_cave/cavebooks", "BOOK_SUN")

    def measure(m):
        wrong, n = [], 0
        for i, r in books(m):
            col, row = at(r)
            k = (r[7] & 15).bit_length() - 1
            under = pristine(m, col, row - 1)
            base = peek_c4(m, sym, 0x4000 + 64 * under, 64)
            want = stamp(blob, sun + 2 * k, base)
            got = peek_c4(m, sym, 0x4000 + 64 * cell(m, col, row - 1), 64)
            n += 1
            if got != want:
                wrong.append(SYMBOLS[k])
        return n, wrong

    m = enter(9)
    n, wrong = measure(m)
    check("all four, their own cel of cave_books over the tile under them",
          n == 4 and not wrong,
          f"{n} books, wrong: {wrong or 'none'} - against an independent "
          f"reading of the span format (test_entities.stamp)")

    m = enter(9, pokes=[(sym["BOOK_CEL"], 0xC9)])
    n, wrong = measure(m)
    check("... and with BOOK_CEL poked to RET they are all the sun",
          sorted(wrong) == ["eye", "moon", "star"],
          f"wrong: {sorted(wrong)} - one book picture for four symbols, "
          f"and a tablet that tells her nothing")


# ---------------------------------------------------------------------
def touch():
    print("\n  picking them up:")
    m = enter(9)
    bs = books(m)
    good = [(i, r) for i, r in bs if not r[7] & CURSED]
    bad = [(i, r) for i, r in bs if r[7] & CURSED]

    def take(m, i, r):
        """Her box onto the book, a game frame, and what it did."""
        col, row = at(r)
        m.poke(sym["PLAYER_HP"], 100)
        m.poke(sym["KARA_WX"], (col * 4 - 1) & 255)
        m.poke(sym["KARA_WX"] + 1, (col * 4 - 1) >> 8)
        wy = row * 16 - 64
        m.poke(sym["KARA_WY"], wy & 255)
        m.poke(sym["KARA_WY"] + 1, wy >> 8)
        for _ in range(3):
            F.gframe(m, sym, 0)
        flags = recs(m)[i][5]
        return m.peek(sym["CURRENT_BOOK_ID"]), m.peek(sym["PLAYER_HP"]), bool(flags & EF_TAKEN)

    m.poke(sym["CURRENT_BOOK_ID"], 0)
    a = take(m, *good[0])
    b = take(m, *good[1])
    want = good[0][1][7] | good[1][1][7]
    check("a good book goes into her SET: two books, two bits",
          a[0] == good[0][1][7] and b[0] == want and a[2] and b[2]
          and a[1] == b[1] == 100,
          f"{a[0]} then {b[0]}, HP {b[1]}, both taken")
    c = take(m, *bad[0])
    check("a cursed one costs her a cell, goes into no set, and is gone",
          c[0] == want and c[1] == 100 - sym["BOOK_HURT"] and c[2],
          f"books {c[0]}, HP 100 -> {c[1]}, taken {c[2]}")

    # THE CONTROL: the curse taken off the record. The same book is then
    # a good one, which is what says the cost was the bit and not the
    # walk onto it.
    i, r = bad[1]
    m.poke(sym["ENT_TABLE"] + i * 8 + 7, r[7] & ~CURSED & 255)
    d = take(m, i, r)
    check("... and with its curse taken off, the same book is a good one",
          d[1] == 100 and d[0] == want | (r[7] & 15),
          f"books {d[0]}, HP {d[1]}")


# ---------------------------------------------------------------------
def the_lock():
    print("\n  the lock, and the door after it:")
    m = enter(9)
    i, r = lock(m)
    gate_col = at(recs(m)[i + 1])[0] - 1
    col, row = stand_at_lock(m)
    want = r[7]
    before = slots(m, gate_col, row)
    check("the lock is the record before the door, and wants the sun and "
          "the moon", recs(m)[i + 1][0] == EK_DOOR and want == 3,
          f"record {i} wants {want}, at tile {col}")

    m.poke(sym["CURRENT_BOOK_ID"], 0)
    e = up(m)
    m.poke(sym["CURRENT_BOOK_ID"], 1)
    h = up(m)
    check("nothing in hand is nothing, and half the pair is refused - and "
          "she keeps the half", e == ER_EMPTY and h == ER_WRONG
          and m.peek(sym["CURRENT_BOOK_ID"]) == 1
          and not recs(m)[i][5] & EF_TAKEN and m.peek(sym["KEYS_COUNT"]) == 0,
          f"ENT_RESULT {e}, then {h}, holding {m.peek(sym['CURRENT_BOOK_ID'])}")

    m.poke(sym["CURRENT_BOOK_ID"], want | 8)
    p = up(m)
    after = slots(m, gate_col, row)
    lit = [a - b for a, b in zip(after, before)]
    check("the pair goes in, and what it does not want stays in her hand",
          p == ER_PLACED and m.peek(sym["CURRENT_BOOK_ID"]) == 8
          and recs(m)[i][5] & EF_TAKEN and m.peek(sym["KEYS_COUNT"]) == 1,
          f"ENT_RESULT {p}, holding {m.peek(sym['CURRENT_BOOK_ID'])}, "
          f"the gate's key {m.peek(sym['KEYS_COUNT'])}")
    check("... and its two slots move on, and only those two",
          lit == [1, 1, 0, 0]
          and after[:2] == [before[0] + 1, before[1] + 1],
          f"slots {before} -> {after}")
    for _ in range(6):
        F.gframe(m, sym, 0)
    shown = [screen_cell(m, sym, gate_col + k, row - 5) for k in range(2)]

    d = up(m)
    check("and the next UP is the door", d == ER_OPENED
          and m.peek(sym["GAME_STATE"]) == F.GS_CLEAR,
          f"ENT_RESULT {d}, GAME_STATE {m.peek(sym['GAME_STATE'])}")

    # (bank C4 is read last: peek_c4 runs a stub of its own on the machine)
    tiles = [peek_c4(m, sym, 0x4000 + 64 * after[k], 64) for k in range(2)]
    books_in = [peek_c4(m, sym, 0x4000 + 64 * T[f"gate_book_{s}"], 64)
                for s in ("sun", "moon")]
    check("... and the slots were on the screen as the artist's slot with "
          "its book in", shown == tiles and tiles == books_in,
          "both cells, byte for byte, read back off the display")

    # THE CONTROL FOR THE PICTURE: TA_ADVANCE off the wanted slots, in
    # the table the engine reads. The lock still takes the books and
    # still gives the key - so it is the FLAG that lights them.
    m = enter(9)
    i, r = lock(m)
    col, row = stand_at_lock(m)
    before = slots(m, gate_col, row)
    for x in before[:2]:
        m.poke(sym["TILE_ATTR"] + x, m.peek(sym["TILE_ATTR"] + x) & ~TA_ADVANCE)
    m.poke(sym["CURRENT_BOOK_ID"], 3)
    p = up(m)
    check("... and with TA_ADVANCE off them the books go in and nothing lights",
          p == ER_PLACED and slots(m, gate_col, row) == before
          and m.peek(sym["KEYS_COUNT"]) == 1,
          f"slots {before} -> {slots(m, gate_col, row)}, key "
          f"{m.peek(sym['KEYS_COUNT'])}")

    # THE CONTROL FOR THE ORDER: the door before the lock. UP finds the
    # door first, and with no key the door is all it ever finds.
    m = enter(9)
    i, r = lock(m)
    col, row = stand_at_lock(m)
    door = recs(m)[i + 1]
    m.write_ram(sym["ENT_TABLE"] + i * 8, door + r)
    m.poke(sym["CURRENT_BOOK_ID"], 3)
    res = [up(m) for _ in range(3)]
    check("... and with the door first, the gate never opens",
          all(x == 4 for x in res) and m.peek(sym["GAME_STATE"]) == 0
          and m.peek(sym["CURRENT_BOOK_ID"]) == 3,
          f"ENT_RESULT {res} - ER_LOCKED every time, her books still in "
          f"her hand")


# ---------------------------------------------------------------------
def restart():
    print("\n  a death puts it back:")
    m = enter(9)
    i, r = lock(m)
    gate_col = at(recs(m)[i + 1])[0] - 1
    col, row = stand_at_lock(m)
    before = slots(m, gate_col, row)
    bs = [r[5] for _, r in books(m)]
    m.poke(sym["CURRENT_BOOK_ID"], 3)
    up(m)
    for k, (j, b) in enumerate(books(m)):
        m.poke(sym["ENT_TABLE"] + j * 8 + 5, b[5] | EF_TAKEN)
    m.poke(sym["PLAYER_HP"], 0)
    back = False
    for _ in range(2000):
        m.run_frames(1)
        if m.peek(sym["GAME_STATE"]) == F.GS_DEAD:
            back = True
        if back and m.peek(sym["GAME_STATE"]) == 0:
            break
    m.run_frames(10)
    check("the slots dark, the books back, her hands and the key empty",
          back and slots(m, gate_col, row) == before
          and [r[5] for _, r in books(m)] == bs
          and not lock(m)[1][5] & EF_TAKEN
          and m.peek(sym["CURRENT_BOOK_ID"]) == 0
          and m.peek(sym["KEYS_COUNT"]) == 0,
          f"slots {slots(m, gate_col, row)}, books' flags "
          f"{[r[5] for _, r in books(m)]}")


def main():
    print("The cave's gate and its books (CLAUDE.md 8.25)")
    tablets()
    pictures()
    touch()
    the_lock()
    restart()
    if fails:
        print(f"FAILED: {len(fails)} check(s): {', '.join(fails)}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
