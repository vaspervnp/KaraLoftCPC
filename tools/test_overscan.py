#!/usr/bin/env python3
"""Verify the overscan layout against real CRTC emulation.

cpclib claims a 192x272 overscan screen must be two independent halves of
17 character rows, because the CRTC only drives MA0-MA9 and so cannot
address more than 1024 words per raster block. That is a claim about
hardware, so it gets tested on hardware rather than argued about: each
half is programmed into the CRTC as a 192x136 screen, displayed, and the
rendered pixels are compared against the source image.

If the halving were wrong -- if 34 rows really did fit -- this test would
still pass for half 0 but the picture would tear or repeat. So it also
checks the negative: 34 rows programmed as one screen DOES wrap.
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/home/vasilhs/cpcemu")

import cpclib
from cpc import CPC

BORDER_HW = 26          # Lime - deliberately not in the title palette
FB_W = 1024             # the framebuffer is wider than the rendered picture
VISIBLE_W, VISIBLE_H = 768, 272

fails = []
def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def setup_code(palette, rows):
    """Z80 that puts the gate array in Mode 0 and the CRTC in overscan width."""
    pens = "\n".join(f"                db &{cpclib.gate_array_value(hw):02X}"
                     for hw in palette)
    crtc = [(0, 63), (1, 48), (2, 50), (3, 0x8E), (4, 38), (5, 0),
            (6, rows), (7, 30), (8, 0), (9, 7), (12, 0x30), (13, 0)]
    writes = "\n".join(
        f"                ld   bc,&BC00 + {r}\n"
        f"                out  (c),c\n"
        f"                ld   bc,&BD00 + &{v:02X}\n"
        f"                out  (c),c" for r, v in crtc)
    return f"""
                org  &8000
                di
                ld   sp,&BFFF
                ld   bc,&7F8C           ; mode 0, both ROMs disabled
                out  (c),c
                ld   hl,PENS            ; 16 pens
                ld   bc,&7F00
.pen:           out  (c),c
                ld   a,(hl)
                inc  hl
                out  (c),a
                inc  c
                ld   a,c
                cp   16
                jr   c,.pen
                ld   c,&10              ; border
                out  (c),c
                ld   a,&{cpclib.gate_array_value(BORDER_HW):02X}
                out  (c),a
{writes}
.halt:          jr   .halt
PENS:
{pens}
"""


def assemble(source):
    with tempfile.TemporaryDirectory() as tmp:
        asm = os.path.join(tmp, "probe.asm")
        binf = os.path.join(tmp, "probe.bin")
        open(asm, "w").write(source)
        r = subprocess.run(["rasm", asm, "-amper", "-ob", binf],
                           capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(r.stdout + r.stderr)
        return open(binf, "rb").read()


def display(machine, code, page):
    machine.write_ram(0xC000, bytes(page))
    machine.run_code(0x8000, code, frames=4)
    return machine.framebuffer()


def find_display(fb, border_index):
    """Bounding box of the picture inside the border.

    Only the 768x272 rendered area counts; the rest of the 1024x312
    framebuffer is padding the emulator never draws into.
    """
    xs, ys = [], []
    for y in range(VISIBLE_H):
        row = fb[y * FB_W:(y + 1) * FB_W]
        for x in range(VISIBLE_W):
            if row[x] != border_index:
                xs.append(x)
                ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def main():
    blob = open(os.path.join(HERE, "..", "build", "overscan.bin"), "rb").read()
    check("overscan.bin is 26,112 bytes", len(blob) == cpclib.OVERSCAN_BYTES,
          f"{len(blob)}")

    expected = cpclib.unpack_overscan(blob)
    palette = [int(v, 16) & 0x1F for v in __import__("re").findall(
        r"db &([0-9A-F]{2})",
        open(os.path.join(HERE, "..", "build", "title_palette.asm")).read())]
    check("palette include has 16 pens", len(palette) == 16, f"{len(palette)}")

    code = assemble(setup_code(palette, rows=17))
    hw_to_pen = {}
    for pen, hw in enumerate(palette):
        hw_to_pen.setdefault(hw, pen)

    machine = CPC()
    machine.run_frames(120)

    for half in (0, 1):
        page = cpclib.overscan_half_page(blob, half)
        fb = display(machine, code, page)
        bbox = find_display(fb, BORDER_HW)
        if bbox is None:
            check(f"half {half} displays anything", False)
            continue
        x0, y0, x1, y1 = bbox
        width_px = (x1 - x0 + 1) // 4          # 4 framebuffer units per Mode 0 pixel
        height = y1 - y0 + 1
        check(f"half {half} displays 192x136",
              width_px == 192 and height == 136,
              f"got {width_px}x{height} at ({x0},{y0})")

        mismatches = 0
        sampled = 0
        for line in range(min(136, height)):
            src = expected[half * 136 + line]
            row = fb[(y0 + line) * FB_W:(y0 + line + 1) * FB_W]
            for px in range(0, 192, 3):        # every third pixel is plenty
                got = hw_to_pen.get(row[x0 + px * 4 + 1])
                sampled += 1
                if got != src[px]:
                    mismatches += 1
        check(f"half {half} pixels match the source image",
              mismatches == 0, f"{mismatches}/{sampled} wrong")

    # Negative control. If 34 rows fitted in one buffer the split would be
    # pointless, so prove they do not. The page holds only half 0 (136 lines
    # of picture, rest zeroes), and MA advances 48 per row, so:
    #
    #   rows 17-20  (lines 136-167)  MA 816-1007, still linear -> blank
    #   row 21      (line 168)       MA crosses 1024 mid-line  -> wraps
    #
    # Blank where the buffer ran out, then picture data reappearing out of
    # nowhere, is the address counter folding back on itself.
    code34 = assemble(setup_code(palette, rows=34))
    fb = display(machine, code34, cpclib.overscan_half_page(blob, 0))
    bbox = find_display(fb, BORDER_HW)
    x0, y0, _, y1 = bbox
    lines = [bytes(fb[(y0 + n) * FB_W + x0:(y0 + n) * FB_W + x0 + 768])
             for n in range(y1 - y0 + 1)]
    uniform = lambda ln: len(set(ln)) == 1

    blank = [n for n in range(136, 168) if uniform(lines[n])]
    check("34 rows: the unfilled rows 17-20 draw blank",
          len(blank) == 32, f"{len(blank)}/32 blank")

    recycled = [n for n in range(168, len(lines)) if not uniform(lines[n])]
    check("34 rows: address counter wraps at row 21, so the split is required",
          len(recycled) > 0,
          f"{len(recycled)} lines of recycled picture from line 168 on")

    machine.screenshot(os.path.join(HERE, "..", "build", "overscan_half0.png"))
    print("\n" + ("ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
