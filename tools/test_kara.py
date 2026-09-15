#!/usr/bin/env python3
"""KARA_SPAN_DRAW: the heroine's real art, on the real screen model.

This is the join between three things that were each tested alone - the
exporter's blobs, the span blitter, and the level loader that puts the
blobs in a bank - plus the one piece that exists only here: working out
how much of a 64-line sprite is on a 192-line display when the camera
has carried her off an edge.

The model reads the blob from disc, decodes its groups independently of
the blitter, and computes every address from the v-model in CLAUDE.md
6.4 rather than by stepping the way the engine steps.
"""
import os
import random
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import boot, symbols, sync, STUB          # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SCR_LINES = 192
SCR_CHARS = 40
MYSTUB = 0xA000

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def decode(blob, f):
    """Frame f -> (y0, [(skip, [(mask, data), ...]) per stored line])."""
    off = blob[2 * f] | (blob[2 * f + 1] << 8)
    y0, lines = blob[off], blob[off + 1]
    p, skip, rows = off + 2, 0, []
    while blob[p]:
        nl, count = blob[p], blob[p + 1]
        d = blob[p + 2] | (blob[p + 3] << 8)
        p += 4
        if count:
            skip += d - 65536 if d > 32767 else d
        for _ in range(nl):
            pairs = [(blob[p + 2 * k], blob[p + 2 * k + 1]) for k in range(count)]
            p += 2 * count
            rows.append((skip, pairs))
    assert len(rows) == lines, (len(rows), lines)
    return y0, rows


def addr_of(scroll, line, col):
    """CLAUDE.md 6.4, written out rather than stepped."""
    v = (2 * scroll + 80 * (line >> 3) + col) & 0x7FF
    return 0xC000 + ((line & 7) << 11) + v


def step(a, n):
    """n bytes on, folding at the end of the 2 KB raster block."""
    r, v = (a - 0xC000) >> 11, (a - 0xC000) & 0x7FF
    return 0xC000 + (r << 11) + ((v + n) & 0x7FF)


def main():
    sym = symbols()
    for n in ("KARA_SPAN_DRAW", "LEVEL_LOAD", "SPAN_ERASE"):
        if n not in sym:
            check(f"{n} is linked", False, "rebuild first")
            return 1
    m = boot(sym)
    sync(m, sym)

    # level 1's gameplay set puts kcore in &C5 and kcore_l in &C6
    code = bytes([0xF3, 0x3E, 0, 0xCD, sym["LEVEL_LOAD"] & 0xFF,
                  sym["LEVEL_LOAD"] >> 8, 0x18, 0xFE])
    m.write_ram(MYSTUB, code)
    m.set_pc(MYSTUB)
    for _ in range(8_000_000):
        m.run_us(1)
        if m.pc == MYSTUB + len(code) - 2:
            break
    blobs = {0: open(os.path.join(ROOT, "build", "levels", "_shared",
                                  "kcore.bin"), "rb").read(),
             1: open(os.path.join(ROOT, "build", "levels", "_shared",
                                  "kcore_l.bin"), "rb").read()}
    frames = (blobs[0][0] | (blobs[0][1] << 8)) // 2
    print(f"\n  kcore loaded into &C5 and &C6: {frames} frames of "
          f"{sym.get('KARA_W_BYTES', 0)}x{sym.get('KARA_H', 0)}")

    def draw(x, y, frame, facing, scroll):
        m.poke(sym["KARA_X"], x)
        m.poke(sym["KARA_Y"], y)
        m.poke(sym["KARA_FRAME"], frame)
        m.poke(sym["KARA_FACING"], facing)
        m.poke(sym["SCROLL"], scroll & 0xFF)
        m.poke(sym["SCROLL"] + 1, scroll >> 8)
        c = bytes([0xF3, 0xCD, sym["KARA_SPAN_DRAW"] & 0xFF,
                   sym["KARA_SPAN_DRAW"] >> 8, 0x18, 0xFE])
        m.write_ram(MYSTUB, c)
        m.set_pc(MYSTUB)
        for _ in range(400000):
            m.run_us(1)
            if m.pc == MYSTUB + len(c) - 2:
                return True
        return False

    def erase():
        c = bytes([0xF3, 0xCD, sym["SPAN_ERASE"] & 0xFF,
                   sym["SPAN_ERASE"] >> 8, 0x18, 0xFE])
        m.write_ram(MYSTUB, c)
        m.set_pc(MYSTUB)
        for _ in range(400000):
            m.run_us(1)
            if m.pc == MYSTUB + len(c) - 2:
                return

    rng = random.Random(4242)
    bad = stray = bad_erase = cases = culls = clips = 0
    cases_list = [(x, y, f, fa, sc)
                  for x, y in ((0, 0), (68, 0), (20, 128), (40, 145),
                               (40, 191), (40, 192), (40, 200), (40, 250),
                               (40, 255), (0, 96), (68, 96))
                  for f, fa in ((0, 0), (5, 1), (16, 0), (16, 1))
                  for sc in (0, 1, 500, 1023)]
    cases_list += [(rng.randrange(0, 69), rng.randrange(0, 256),
                    rng.randrange(frames), rng.randrange(2),
                    rng.randrange(1024)) for _ in range(120)]

    for x, y, f, facing, scroll in cases_list:
        y0, rows = decode(blobs[facing], f)
        top = (y + y0) & 0xFF
        if top < SCR_LINES:
            first, nskip = top, 0
            ndraw = min(len(rows), SCR_LINES - top)
        else:
            above = 256 - top
            if above >= len(rows):
                ndraw, nskip, first = 0, 0, 0
            else:
                nskip, ndraw, first = above, len(rows) - above, 0
        if ndraw == 0:
            culls += 1
        elif ndraw < len(rows) or nskip:
            clips += 1

        before = bytes(m.read_ram(0xC000, 0x4000))
        want = {}
        for j in range(ndraw):
            skip, pairs = rows[nskip + j]
            a = step(addr_of(scroll, first + j, x), skip)
            for b, (mask, data) in enumerate(pairs):
                aa = step(a, b)
                want[aa] = (want.get(aa, before[aa - 0xC000]) & mask) | data
        if not draw(x, y, f, facing, scroll):
            check(f"draw at x={x} y={y} f={f} returns", False, "ran away")
            continue
        cases += 1
        after = bytes(m.read_ram(0xC000, 0x4000))
        for a, v in want.items():
            if after[a - 0xC000] != v:
                bad += 1
        for i in range(0x4000):
            if after[i] != before[i] and 0xC000 + i not in want:
                stray += 1
        erase()
        back = bytes(m.read_ram(0xC000, 0x4000))
        bad_erase += sum(1 for i in range(0x4000) if back[i] != before[i])

    print(f"  {cases} placements: {culls} entirely off the display, "
          f"{clips} clipped at an edge")
    check("every pixel of her lands where the v-model says", bad == 0,
          f"{bad} wrong bytes")
    check("nothing outside her spans is touched", stray == 0, f"{stray} bytes")
    check("the erase restores the screen exactly", bad_erase == 0,
          f"{bad_erase} bytes still wrong")
    check("a sprite off the display is culled, not folded", culls > 0,
          f"{culls} of {cases} placements")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(fails))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
