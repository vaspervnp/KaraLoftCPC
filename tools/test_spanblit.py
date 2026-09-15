#!/usr/bin/env python3
"""Acceptance test for the span blitter (src/spanblit.asm).

Three things have to hold and none of them is obvious from the code:

1. The composite lands on exactly the bytes the span says and nothing
   else. A span is addressed as line start + skip, and the line start
   walks the SCROLLED screen, so a span can run off the end of the 2 KB
   raster block in the middle of itself. The blitter splits those into
   two runs; if it ever fails to, the tail lands 2 KB away - in another
   raster of the same screen, which looks like a stray stripe and not
   like a crash.

2. The erase restores the screen EXACTLY, from a script it has to
   re-read correctly, including those split runs and including empty
   lines (LDIR with BC = 0 would move 65536 bytes).

3. Both are fast enough to sit in the frame. The whole reason for the
   format is that a 24x64 sprite has to cost less than the 16x48 one it
   replaces.

The model here recomputes the addresses independently from the v-model
in CLAUDE.md 6.4 rather than from the blitter's own stepping, so the
two can disagree.
"""
import os
import random
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import Bench, boot, symbols, sync, raw, STUB          # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FRAME = 0x9200                  # where the test puts a synthetic frame
BOX_W = 12

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


# ---------------------------------------------------------------- model
def split(addr):
    off = addr - 0xC000
    return off >> 11, off & 0x7FF           # raster, offset in the block


def join(raster, v):
    return 0xC000 + (raster << 11) + v


def next_line(addr):
    """One scanline down, the way the CRTC lays the screen out."""
    r, v = split(addr)
    r += 1
    if r == 8:
        r, v = 0, (v + 80) & 0x7FF          # next character row, 40 words on
    return join(r, v)


def touched(de, rec):
    """[(address, line, byte-in-span)] the draw must write, in order.

    Derived from the per-LINE picture, not from the group encoding, so
    a grouping bug in the exporter or the blitter shows up here.
    """
    out, addr = [], de
    for i, (skip, pairs) in enumerate(rec):
        r, v = split(addr)
        v = (v + skip) & 0x7FF              # the skip folds too
        for b in range(len(pairs)):
            out.append((join(r, v), i, b))
            v = (v + 1) & 0x7FF             # ... and so does every byte
        addr = next_line(addr)
    return out


def make_frame(rng, lines, forced=None):
    """A synthetic frame in the grouped format, and its per-line truth.

    Runs of equal (skip, count) are deliberately common - that is what
    the format is for - but not universal, so both the group setup and
    the within-group line loop get exercised.
    """
    rec = []
    while len(rec) < lines:
        i = len(rec)
        if forced and i in forced:
            skip, count, run = forced[i][0], forced[i][1], 1
        elif rng.random() < 0.15:
            skip, count = 0, 0              # interior empty lines
            run = rng.randrange(1, 4)
        else:
            skip = rng.randrange(0, BOX_W)
            count = rng.randrange(1, BOX_W - skip + 1)
            run = rng.choice([1, 1, 2, 3, 5])
        for _ in range(min(run, lines - len(rec))):
            rec.append((skip, [(rng.randrange(256), rng.randrange(256))
                               for _ in range(count)]))

    blob = bytearray()
    prev_skip = i = 0
    while i < len(rec):
        skip, pairs = rec[i]
        count = len(pairs)
        j = i + 1
        while (j < len(rec) and len(rec[j][1]) == count
               and (count == 0 or rec[j][0] == skip)):
            j += 1
        if count == 0:
            blob += bytes([j - i, 0, 0, 0])
        else:
            d = skip - prev_skip
            blob += bytes([j - i, count, d & 0xFF, 0xFF if d < 0 else 0])
            prev_skip = skip
            for k in range(i, j):
                for m, dd in rec[k][1]:
                    blob += bytes([m, dd])
        i = j
    blob.append(0)
    return bytes(blob), rec


# ----------------------------------------------------------------- run
def call(m, sym, routine, hl=0, de=0, bc=0, a=0):
    code = bytes([0xF3,                                 # di
                  0x21, hl & 0xFF, hl >> 8,             # ld hl,nn
                  0x11, de & 0xFF, de >> 8,             # ld de,nn
                  0x01, bc & 0xFF, bc >> 8,             # ld bc,nn
                  0x3E, a,                              # ld a,n
                  0xCD, sym[routine] & 0xFF, sym[routine] >> 8,
                  0x18, 0xFE])                          # jr $
    m.write_ram(STUB, code)
    m.set_pc(STUB)
    end = STUB + len(code) - 2
    for _ in range(400000):
        m.run_us(1)
        if m.pc == end:
            return True
    return False


def main():
    sym = symbols()
    m = boot(sym)
    sync(m, sym)
    print(f"\n  SPAN_RUN at &{sym['SPAN_RUN']:04X}, "
          f"SPAN_ENTRY at &{sym['SPAN_ENTRY']:04X}, "
          f"script at &{sym['SPAN_SCRIPT'] if 'SPAN_SCRIPT' in sym else 0x8200:04X}")
    script = 0x8200

    rng = random.Random(1234)
    bad_draw = bad_erase = bad_bystander = 0
    cases = 0
    folds = rows = 0

    # Positions chosen to put spans on every awkward boundary there is:
    # the 2 KB fold, the character-row step, the top and bottom of a
    # raster block - and then a spread of ordinary ones.
    starts = [0xC000, 0xC7F0, 0xC7F8, 0xC7FC, 0xCFF4, 0xD7F6,
              0xC050, 0xC7A0, 0xE3C2, 0xF7FA, 0xC004, 0xDFF9]
    starts += [0xC000 + rng.randrange(0x4000) for _ in range(8)]

    for de in starts:
        lines = rng.choice([1, 7, 8, 9, 64])
        # force a full-width span onto the line most likely to straddle
        forced = {0: (0, 12), 1: (11, 1), 2: (0, 0)} if lines > 3 else None
        blob, rec = make_frame(rng, lines, forced)
        m.write_ram(FRAME, blob)
        before = bytes(m.read_ram(0xC000, 0x4000))

        # Replay in order, so that where a sprite overlaps itself the
        # model resolves it the way the Z80 does.
        want = dict()
        for (addr, i, b) in touched(de, rec):
            mask, data = rec[i][1][b]
            under = want.get(addr, before[addr - 0xC000])
            want[addr] = (under & mask) | data

        if not call(m, sym, "SPAN_DRAW", hl=FRAME, de=de, bc=script,
                    a=lines):
            check(f"draw at &{de:04X} returns", False, "ran away")
            continue
        cases += 1
        after = bytes(m.read_ram(0xC000, 0x4000))
        for addr, v in want.items():
            if after[addr - 0xC000] != v:
                bad_draw += 1
        # nothing outside the span may move
        for off in range(0x4000):
            if 0xC000 + off not in want and after[off] != before[off]:
                bad_bystander += 1

        # how many runs did the split actually produce?
        n_runs = 0
        q = script
        while m.peek(q) != 255:
            n_runs += 1
            q += 3 + m.peek(q)
        folds += n_runs - sum(1 for _, p in rec if p)
        rows += 1

        if not call(m, sym, "SPAN_ERASE"):
            check(f"erase at &{de:04X} returns", False, "ran away")
            continue
        back = bytes(m.read_ram(0xC000, 0x4000))
        bad_erase += sum(1 for i in range(0x4000) if back[i] != before[i])

    check("every composited byte lands where the v-model says",
          bad_draw == 0, f"{bad_draw} wrong bytes over {cases} placements")
    check("nothing outside the spans is touched", bad_bystander == 0,
          f"{bad_bystander} bytes")
    check("the erase restores the screen exactly", bad_erase == 0,
          f"{bad_erase} bytes still wrong")
    check("wrapped spans really were split", folds > 0,
          f"{folds} extra runs across {rows} placements")

    # ------------------------------------------------------------ cost
    # Real frames, not synthetic ones: the whole point of the format is
    # what it does to the REAL occupancy, and the answer differs by a
    # third between her lightest frame and her heaviest.
    path = os.path.join(ROOT, "build", "levels", "_shared", "kcore.bin")
    if os.path.exists(path):
        blob = open(path, "rb").read()
        n = (blob[0] | (blob[1] << 8)) // 2
        frames = []
        for f in range(n):
            off = blob[2 * f] | (blob[2 * f + 1] << 8)
            lines, p, span = blob[off + 1], off + 2, 0
            while blob[p]:
                nl, count = blob[p], blob[p + 1]
                p += 4 + 2 * count * nl
                span += count * nl
            frames.append((f, lines, span, blob[off + 2:p + 1]))

        sync(m, sym)
        b = Bench(m, sym)
        sym["_DRAW"] = STUB + 0x100
        costs = []
        for f, lines, span, data in frames:
            m.write_ram(FRAME, data)
            m.write_ram(STUB + 0x100, bytes([0x21, FRAME & 0xFF, FRAME >> 8,
                                             0x11, 0x00, 0xC4,
                                             0x01, 0x00, 0x82,
                                             0x3E, lines,
                                             0xC3, sym["SPAN_DRAW"] & 0xFF,
                                             sym["SPAN_DRAW"] >> 8]))
            costs.append((f, span, b.T("_DRAW"), b.T("SPAN_ERASE")))

        worst = max(costs, key=lambda c: c[2] + c[3])
        light = min(costs, key=lambda c: c[2] + c[3])
        mean = sum(c[2] + c[3] for c in costs) // len(costs)
        print(f"\n  cost over all {n} frames of kara_core, draw + erase:")
        for tag, c in (("lightest", light), ("heaviest", worst)):
            print(f"    {tag:<9} frame {c[0]:2d}, {c[1]:3d} span bytes: "
                  f"{c[2]:6d} + {c[3]:5d} = {c[2] + c[3]:6d} T"
                  f"   ({c[2] / c[1]:.0f} a byte drawn)")
        print(f"    mean                                        {mean:6d} T")
        print(f"    the 16x48 pair it replaces was              41,664 T")

        # The composite itself is 72 T a byte and cannot be less: nine
        # instructions, all of them 8 T after the gate array's padding.
        check("the composite is at its floor", worst[2] / worst[1] < 125,
              f"{worst[2] / worst[1]:.0f} T a byte against a 72 T floor, "
              f"the rest being per-line")

        # And the real question: does the frame still close? Measure the
        # rest of a SCROLLING loop rather than trusting a table.
        rest = 0
        for name in ("INPUT_SCAN", "PLAYER_UPDATE", "CAMERA_DECIDE",
                     "SCROLL_SERVICE", "PLAYER_TO_SCREEN", "GAME_LOGIC",
                     "BUL_DRAW", "BUL_ERASE"):
            if name in sym:
                rest += b.T(name) or 0
        col = 0
        if "DRAW_COLUMN" in sym:
            m.write_ram(STUB + 0x100, bytes([0x3E, 20, 0xC3,
                                             sym["DRAW_COLUMN"] & 0xFF,
                                             sym["DRAW_COLUMN"] >> 8]))
            for first, rows in ((0, 18), (18, 6)):       # H_HEAD + H_TAIL
                def setup(mm, first=first, rows=rows):
                    mm.poke(sym["COL_FIRST"], first)
                    mm.poke(sym["COL_N"], rows)
                col += b.T("_DRAW", setup=setup) or 0
        print(f"\n  a scrolling frame, of 79,872 T:")
        print(f"    the incoming column, head + tail          {col:6d} T"
              f"   ({col / 384:.0f} a byte)")
        print(f"    input, player, camera, bullets, logic     {rest:6d} T")
        for tag, c in (("lightest", light), ("heaviest", worst)):
            tot = col + rest + c[2] + c[3]
            print(f"    + Kara, {tag:<9}                      {tot:6d} T"
                  f"   {'fits' if tot <= 79872 else 'OVER by %d' % (tot - 79872)}")
        tot = col + rest + worst[2] + worst[3]
        check("the frame closes on her heaviest frame while scrolling",
              tot <= 79872,
              f"{tot} T, {79872 - tot} to spare; the column is "
              f"{col / 384:.0f} T a byte and the next lever on it is a "
              f"column-major tile layout, worth ~2,300 T")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(fails))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
