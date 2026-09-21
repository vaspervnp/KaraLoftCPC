#!/usr/bin/env python3
"""The X clip: a sprite cut off at the left and right edges. (Module 6d)

WHAT WAS WRONG, MEASURED OFF THE ERASE SCRIPT. The script is the draw's
own record of which screen words it wrote, so reading it back asks
where she was put with no model of the blitter in it at all. Before
this module:

    KARA_X  74   three of her nine occupied columns folded onto column
                 0 of the NEXT character row, 8 lines down
    KARA_X  -6   she was drawn WHOLE, at columns 10..18 and 24 lines
                 below where she is: a second heroine in the middle of
                 the picture

CLAUDE.md 8.10 said the blitter culled her off the left edge. It did
not - there was no cull and no clip, and the camera's own clamps were
the only thing keeping level 1 out of it.

WHAT IS CHECKED HERE is spanblit.asm's CX lane, against the same
independent v-model tools/test_spanblit.py runs on the fast one - the
per-LINE picture of the frame, not the group encoding, so a grouping
bug shows up rather than cancelling. The sweep is every column from
-BOX_W to the width of the screen, at addresses chosen to put spans on
every awkward boundary there is.

And the two lanes are each other's control at the one place they
overlap: a sprite that needs no clipping must come out of the slow lane
as the SAME SCRIPT, byte for byte, that the fast one writes.
"""
import os
import random
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import symbols, boot, sync, STUB                     # noqa: E402
from test_spanblit import (make_frame, split, join, next_line,   # noqa: E402
                           FRAME, BOX_W)

SCR_BYTES = 80                  # SCR_CHARS * 2
SCRIPT = 0x8200
fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def touched_x(de, rec, x, clip=True):
    """[(address, line, byte)] the draw must write, in order.

    The same walk test_spanblit.py's `touched` makes, with the one
    thing this module adds: a byte is drawn only if the screen COLUMN
    it would land in is on the display. The column is the box's own
    plus the span's skip plus the byte - it is never derived from the
    address, because in a 1024-word ring "off the right edge" and "the
    next character row" are the same place.
    """
    out, addr = [], de
    for i, (skip, pairs) in enumerate(rec):
        r, v = split(addr)
        v = (v + skip) & 0x7FF
        for b in range(len(pairs)):
            if not clip or 0 <= x + skip + b < SCR_BYTES:
                out.append((join(r, v), i, b))
            v = (v + 1) & 0x7FF
        addr = next_line(addr)
    return out


def callx(m, sym, routine, hl, de, bc, a, x, skip=0):
    m.poke(sym["SPAN_SKIP"], skip)
    m.poke(sym["SPAN_X"], x & 0xFF)
    code = bytes([0xF3,
                  0x21, hl & 0xFF, hl >> 8,
                  0x11, de & 0xFF, de >> 8,
                  0x01, bc & 0xFF, bc >> 8,
                  0x3E, a,
                  0xCD, sym[routine] & 0xFF, sym[routine] >> 8,
                  0x18, 0xFE])
    m.write_ram(STUB, code)
    m.set_pc(STUB)
    for _ in range(400000):
        m.run_us(1)
        if m.pc == STUB + len(code) - 2:
            return True
    return False


def script_of(m, sym):
    p, out = SCRIPT, []
    for _ in range(4000):
        n = m.peek(p)
        if n == 255:
            return out
        out.append((m.peek(p + 1) | m.peek(p + 2) << 8, n,
                    bytes(m.read_ram(p + 3, n))))
        p += 3 + n
    return None


def where(addr, scroll):
    """A screen address back to (line, byte column), through the ring.

    CLAUDE.md 6.4's model read the other way round. It is the only
    honest way to ask this question: in a 1024-word circular space
    "off the right edge" and "the start of the next character row" are
    the same address, so a column can never be recovered from the
    address alone - it takes the start address the CRTC is showing.
    """
    ra = (addr >> 11) & 7
    ma = ((addr & 0xC000) >> 2) | ((addr & 0x7FF) >> 1)
    idx = (ma - scroll) & 0x3FF
    return idx // 40 * 8 + ra, (idx % 40) * 2 + (addr & 1)


def game_runs(m, sym):
    """The erase script as the LOOP wrote it - address and length."""
    p, out = sym["SPAN_SCRIPT"], []
    for _ in range(6000):
        n = m.peek(p)
        if n == 255:
            return out
        out.append((m.peek(p + 1) | m.peek(p + 2) << 8, n))
        p += 3 + n
    return None


def sweep_in_game(m, sym):
    """Put her at every column either edge can reach and read back the
    columns her draw wrote. Returns (columns tried, the ones that
    strayed).

    HALF 1 IS THE SWEEP THAT HAS THE WHOLE SCRIPT IN IT. half=0 is the
    top of the game frame, where she has been erased; her draw finishes
    on the second sweep, and a script sampled before then is one that is
    still being written - which reads as 3,572 runs.
    """
    tried, stray = 0, []
    for xs in list(range(-BOX_W, 0)) + list(range(SCR_BYTES - 20,
                                                  SCR_BYTES + 1)):
        sync(m, sym, half=0)
        m.poke(sym["KARA_X"], xs & 0xFF)
        sync(m, sym, half=1)
        scroll = m.peek(sym["SCROLL"]) | m.peek(sym["SCROLL"] + 1) << 8
        runs = game_runs(m, sym)
        if runs is None:
            stray.append((xs, "the script never terminated"))
            continue
        tried += 1
        lo, hi = max(xs, 0), min(xs + BOX_W, SCR_BYTES)
        for a, n in runs:
            for k in range(n):
                _, c = where((a & 0xF800) | ((a + k) & 0x7FF), scroll)
                if not lo <= c < hi:
                    stray.append((xs, c))
                    break
            else:
                continue
            break
    return tried, stray


def main():
    sym = symbols()
    m = boot(sym)
    sync(m, sym)
    rng = random.Random(6040)

    # The same awkward boundaries the fast lane's suite uses - the 2 KB
    # fold, the character-row step, the ends of a raster block - because
    # CX_RUN is a SECOND copy of that arithmetic and the copy is the
    # thing to be afraid of (spanblit.asm's header, CLAUDE.md 9).
    starts = [0xC000, 0xC7F0, 0xC7F8, 0xC7FC, 0xCFF4, 0xD7F6,
              0xC050, 0xE3C2, 0xF7FA, 0xDFF9]
    starts += [0xC000 + rng.randrange(0x4000) for _ in range(6)]
    columns = list(range(-BOX_W, 1)) + list(range(SCR_BYTES - BOX_W,
                                                  SCR_BYTES + 1))
    columns += [rng.randrange(0, SCR_BYTES - BOX_W) for _ in range(4)]

    print("\n  the clipped lane against the v-model:")
    bad_draw = bad_bystander = bad_erase = cases = drawn = folds = 0
    hangs = []
    for de in starts:
        for x in columns:
            lines = rng.choice([1, 7, 8, 9, 64])
            forced = {0: (0, 12), 1: (11, 1), 2: (0, 0)} if lines > 3 else None
            blob, rec = make_frame(rng, lines, forced)
            m.write_ram(FRAME, blob)
            before = bytes(m.read_ram(0xC000, 0x4000))

            want = {}
            for (addr, i, b) in touched_x(de, rec, x):
                mask, data = rec[i][1][b]
                want[addr] = (want.get(addr, before[addr - 0xC000])
                              & mask) | data
            if not callx(m, sym, "SPAN_DRAW_CX", FRAME, de, SCRIPT, lines, x):
                hangs.append((de, x))
                continue
            cases += 1
            drawn += len(want)
            after = bytes(m.read_ram(0xC000, 0x4000))
            for addr, v in want.items():
                bad_draw += after[addr - 0xC000] != v
            for off in range(0x4000):
                if 0xC000 + off not in want and after[off] != before[off]:
                    bad_bystander += 1

            runs = script_of(m, sym)
            if runs is None:
                hangs.append((de, x))
                continue
            folds += len(runs) - sum(
                1 for i, (s, p) in enumerate(rec)
                if any(0 <= x + s + b < SCR_BYTES for b in range(len(p))))

            callx(m, sym, "SPAN_ERASE", 0, 0, 0, 0, x)
            back = bytes(m.read_ram(0xC000, 0x4000))
            bad_erase += sum(1 for i in range(0x4000) if back[i] != before[i])

    check("it always returns", not hangs,
          f"{len(hangs)} of {cases + len(hangs)} ran away: {hangs[:3]}")
    check("every composited byte lands where the v-model says",
          bad_draw == 0,
          f"{bad_draw} wrong of {drawn} bytes over {cases} placements")
    check("nothing outside the visible part of the span is touched",
          bad_bystander == 0, f"{bad_bystander} bytes")
    check("the erase restores the screen exactly", bad_erase == 0,
          f"{bad_erase} bytes still wrong")
    check("... and wrapped spans really were split in THIS lane too",
          folds > 0, f"{folds} extra runs across {cases} placements")

    # -----------------------------------------------------------------
    # The two lanes, where they overlap.
    # -----------------------------------------------------------------
    print("\n  the two lanes against each other:")
    same = differ = 0
    for de in starts[:6]:
        for x in (0, 3, 20, SCR_BYTES - BOX_W):
            lines = 64
            blob, rec = make_frame(rng, lines,
                                   {0: (0, 12), 1: (11, 1), 2: (0, 0)})
            m.write_ram(FRAME, blob)
            before = bytes(m.read_ram(0xC000, 0x4000))
            callx(m, sym, "SPAN_DRAW", FRAME, de, SCRIPT, lines, x)
            fast = script_of(m, sym)
            callx(m, sym, "SPAN_ERASE", 0, 0, 0, 0, x)
            callx(m, sym, "SPAN_DRAW_CX", FRAME, de, SCRIPT, lines, x)
            slow = script_of(m, sym)
            callx(m, sym, "SPAN_ERASE", 0, 0, 0, 0, x)
            m.write_ram(0xC000, before)
            same += fast == slow
            differ += fast != slow
    check("a sprite that needs no clip comes out of both the same",
          differ == 0, f"{same} scripts identical, {differ} differ - "
                       f"two implementations of one format, and the fold "
                       f"is in both")

    # -----------------------------------------------------------------
    # The controls. Neither check above says anything until something
    # shows it would have noticed.
    # -----------------------------------------------------------------
    print("\n  and the controls:")
    de, x, lines = 0xC050, -5, 64
    blob, rec = make_frame(rng, lines, {0: (0, 12), 1: (11, 1)})
    m.write_ram(FRAME, blob)
    before = bytes(m.read_ram(0xC000, 0x4000))
    callx(m, sym, "SPAN_DRAW_CX", FRAME, de, SCRIPT, lines, x)
    after = bytes(m.read_ram(0xC000, 0x4000))
    # ... the model with the clip taken out of it: if the engine were
    # NOT clipping, this is what the screen would hold.
    unclipped = {}
    for (addr, i, b) in touched_x(de, rec, x, clip=False):
        mask, data = rec[i][1][b]
        unclipped[addr] = (unclipped.get(addr, before[addr - 0xC000])
                           & mask) | data
    wrong = sum(1 for a, v in unclipped.items() if after[a - 0xC000] != v)
    check("an UNCLIPPED model disagrees with the machine",
          wrong > 0, f"{wrong} of {len(unclipped)} bytes - so the check "
                     f"above is not passing on a clip that does nothing")
    callx(m, sym, "SPAN_ERASE", 0, 0, 0, 0, x)

    # ... and the fast lane on the same placement, which is the defect
    # this module is about.
    m.write_ram(0xC000, before)
    from test_spanblit import call as call_fast
    call_fast(m, sym, "SPAN_DRAW", hl=FRAME, de=de, bc=SCRIPT, a=lines)
    after = bytes(m.read_ram(0xC000, 0x4000))
    want = {}
    for (addr, i, b) in touched_x(de, rec, x):
        mask, data = rec[i][1][b]
        want[addr] = (want.get(addr, before[addr - 0xC000]) & mask) | data
    stray = sum(1 for off in range(0x4000)
                if 0xC000 + off not in want and after[off] != before[off])
    check("the FAST lane on the same placement writes outside the display",
          stray > 0, f"{stray} bytes, which is what 6d is for")
    call_fast(m, sym, "SPAN_ERASE")

    # -----------------------------------------------------------------
    # AND THE SAME QUESTION IN THE RUNNING GAME. Everything above drives
    # the lane from a DI stub with a synthetic frame; this drives
    # KARA_SPAN_DRAW - her real cels, the real scroll, and the one
    # comparison that picks the lane - and reads the answer off the
    # erase script, which is the draw's own record of the words it wrote
    # and has no model of the blitter in it at all.
    # -----------------------------------------------------------------
    print("\n  and in the running game, at every column either edge reaches:")
    g = boot(sym, scroll=True)
    g.run_frames(20)
    tried, stray = sweep_in_game(g, sym)
    check("every column she is put at writes only inside the visible box",
          not stray, f"{tried - len(stray)} of {tried} columns"
                     + (f", stray at {stray[:3]}" if stray else ""))

    # ... and the control is the defect itself: the lane chooser NOPed
    # out, so the fast lane draws every one of those columns.
    img = bytes(g.read_ram(sym["KARA_SPAN_DRAW"], 240))
    at = sym["KARA_SPAN_DRAW"] + img.index(bytes([0xFE, 69, 0x79, 0x01])) + 6
    was = g.peek(at), g.peek(at + 1)
    g.poke(at, 0x00); g.poke(at + 1, 0x00)      # jr nc,.clipped -> nop nop
    tried2, stray2 = sweep_in_game(g, sym)
    g.poke(at, was[0]); g.poke(at + 1, was[1])
    check("... and with the lane chooser NOPed out they do not",
          len(stray2) > 0, f"{len(stray2)} of {tried2} columns stray into "
                           f"the wrong character row, which is what 6d is "
                           f"for")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
