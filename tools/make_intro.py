#!/usr/bin/env python3
"""The intro screen, its palette, and the PRESS SPACE OR FIRE prompt.

WHAT THE ARTIST SHIPPED AND WHAT THE HARDWARE WANTS ARE NOT THE SAME
BYTES. assets/intro/intro_cpc_mode0.scr is 16,000 bytes - 200 lines of
80, LINE AFTER LINE - and a CPC screen is not laid out that way: line L
lives at (L AND 7) * &800 + (L >> 3) * 80, so 200 lines of it span
16,336 bytes with the eight raster blocks interleaved. Loaded straight
to &C000 (which is what the INTRO.BAS beside it does) the picture comes
out shuffled into eight bands. The conversion is here, checked against
the .png the same export produced.

It is then ZX0-packed like everything else that goes on the disc
(CLAUDE.md 7.4): 16,336 bytes down to ~2,500, which is five sectors and
one read. The engine unpacks it STRAIGHT INTO VIDEO RAM - there is no
bank to stage it through and no reason for one, because nothing else is
on screen while the title is up.

THE PROMPT IS TWO PRE-RENDERED STRIPS, NOT A FONT AND A SAVE-UNDER. It
blinks, so the engine needs the picture with the words on it and the
picture without; both are known at build time, so both are built here
and the blink is one LDIR either way. 19 characters at 8 pixels is 152
of the 160 the screen is wide, centred on the black sky at the top -
measured, not assumed: lines 0-15 of this image are 1,259 pixels of pen
1 out of 1,280.
"""
import json
import os
import re
import subprocess
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cpclib                                                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
ART = os.path.join(ROOT, "assets", "intro")
BUILD = os.path.join(ROOT, "build")

W_BYTES = 80                    # 160 Mode 0 pixels
LINES = 200
TEXT = "PRESS SPACE OR FIRE"
TEXT_Y = 4                      # the sky, and clear of her head at y=20
TEXT_PEN = 11                   # the intro palette's white

# An 8x8 glyph for each letter the prompt uses, and nothing else - a
# full font would be 96 glyphs to draw ten of them.
FONT = {
    "P": ".####.. .#...#. .#...#. .####.. .#..... .#..... .#..... .......",
    "R": ".####.. .#...#. .#...#. .####.. .#..#.. .#...#. .#...#. .......",
    "E": ".#####. .#..... .#..... .####.. .#..... .#..... .#####. .......",
    "S": "..###.. .#...#. .#..... ..###.. .....#. .#...#. ..###.. .......",
    "A": "..###.. .#...#. .#...#. .#####. .#...#. .#...#. .#...#. .......",
    "C": "..###.. .#...#. .#..... .#..... .#..... .#...#. ..###.. .......",
    "O": "..###.. .#...#. .#...#. .#...#. .#...#. .#...#. ..###.. .......",
    "F": ".#####. .#..... .#..... .####.. .#..... .#..... .#..... .......",
    "I": "..###.. ...#... ...#... ...#... ...#... ...#... ..###.. .......",
    " ": "....... ....... ....... ....... ....... ....... ....... .......",
}
GLYPH_W = 8


def glyph_rows(ch):
    rows = FONT[ch].split()
    assert len(rows) == 8, ch
    return [r.ljust(GLYPH_W, ".") for r in rows]


def to_screen(linear):
    """The artist's line-after-line bytes, in the CRTC's own order."""
    out = bytearray((LINES - 1 & 7) * 2048 + ((LINES - 1) >> 3) * W_BYTES
                    + W_BYTES)
    for y in range(LINES):
        base = (y & 7) * 2048 + (y >> 3) * W_BYTES
        out[base:base + W_BYTES] = linear[y * W_BYTES:(y + 1) * W_BYTES]
    return bytes(out)


def ink_to_hw():
    """Firmware ink -> hardware colour, off docs/cpc_palette.md."""
    table = {}
    for line in open(os.path.join(ROOT, "docs", "cpc_palette.md")):
        m = re.match(r"^\|\s*(\d+)\s*\|[^|]+\|\s*(\d+)\s*\|", line)
        if m:
            table[int(m.group(1))] = int(m.group(2))
    assert len(table) == 27, len(table)
    return table


def zx0(path):
    asm = path + ".pack.asm"
    out = os.path.splitext(path)[0] + ".zx0"
    open(asm, "w").write(f'        org 0\n        LZX0\n'
                         f'        incbin "{path}"\n        LZCLOSE\n')
    r = subprocess.run(["rasm", asm, "-amper", "-ob", out],
                       capture_output=True, text=True)
    os.remove(asm)
    if r.returncode:
        raise SystemExit(f"packing {path}:\n{r.stdout}{r.stderr}")
    return os.path.getsize(out)


def main():
    scr = open(os.path.join(ART, "intro_cpc_mode0.scr"), "rb").read()
    assert len(scr) == W_BYTES * LINES, len(scr)

    # ---- the picture, checked against the export's own .png ----------
    png = Image.open(os.path.join(ART, "intro_cpc_mode0.png"))
    pens = [[png.getpixel((x, y)) for x in range(W_BYTES * 2)]
            for y in range(LINES)]
    wrong = sum(1 for y in range(LINES) for xb in range(W_BYTES)
                if scr[y * W_BYTES + xb] != cpclib.encode_pixels(
                    pens[y][xb * 2], pens[y][xb * 2 + 1]))
    if wrong:
        raise SystemExit(f"intro .scr disagrees with its .png in {wrong} "
                         f"bytes - is it line-major after all?")

    native = to_screen(scr)
    raw = os.path.join(BUILD, "intro.bin")
    open(raw, "wb").write(native)
    packed = zx0(raw)

    # ---- the palette -------------------------------------------------
    js = json.load(open(os.path.join(ART, "intro_cpc_mode0_palette.json")))
    ink = ink_to_hw()
    lines = ["; generated by tools/make_intro.py - do not edit",
             "INTRO_PALETTE:"]
    for p in js["pens"]:
        hw = ink[p["firmware_ink"]]
        near = cpclib.nearest_hw(tuple(int(p["hex"][i:i + 2], 16)
                                       for i in (0, 2, 4)))
        # The artist names an INK and also gives the RGB it stands for;
        # they have to be the same colour or one of the two is a typo.
        if hw != near:
            raise SystemExit(f"pen {p['pen']}: ink {p['firmware_ink']} is "
                             f"hw {hw} but #{p['hex']} is nearest hw {near}")
        lines.append(f"                db &{0x40 | hw:02X}"
                     f"      ; pen {p['pen']:2d}  ink {p['firmware_ink']:2d}"
                     f"  #{p['hex']}")
    lines.append(f"                db &{0x40 | ink[0]:02X}      ; border")

    # ---- the prompt, with and without the words ----------------------
    x0 = (W_BYTES * 2 - len(TEXT) * GLYPH_W) // 2
    assert x0 % 2 == 0 and x0 >= 0, x0
    n_bytes = len(TEXT) * GLYPH_W // 2
    on, off = bytearray(), bytearray()
    for row in range(8):
        y = TEXT_Y + row
        lit = [False] * (len(TEXT) * GLYPH_W)
        for i, ch in enumerate(TEXT):
            for x, c in enumerate(glyph_rows(ch)[row]):
                lit[i * GLYPH_W + x] = c == "#"
        for b in range(n_bytes):
            p = [pens[y][x0 + b * 2 + k] for k in (0, 1)]
            off.append(cpclib.encode_pixels(p[0], p[1]))
            q = [TEXT_PEN if lit[b * 2 + k] else p[k] for k in (0, 1)]
            on.append(cpclib.encode_pixels(q[0], q[1]))
    lines += ["", f"INTRO_TEXT_BYTES equ {n_bytes}",
              f"INTRO_TEXT_LINES equ 8", "INTRO_TEXT_ADDR:"]
    for row in range(8):
        y = TEXT_Y + row
        addr = 0xC000 + (y & 7) * 0x800 + (y >> 3) * W_BYTES + x0 // 2
        lines.append(f"                dw &{addr:04X}          ; line {y}")
    for name, blob in (("INTRO_TEXT_ON", on), ("INTRO_TEXT_OFF", off)):
        lines.append(f"{name}:")
        for row in range(8):
            r = blob[row * n_bytes:(row + 1) * n_bytes]
            lines.append("                db " +
                         ",".join(f"&{v:02X}" for v in r))
    open(os.path.join(BUILD, "intro.inc"), "w").write("\n".join(lines) + "\n")

    print(f"-> intro.bin          {len(native)} bytes -> {packed} packed "
          f"({100 * packed // len(native)}%), "
          f"{(packed + 511) // 512} sectors")
    print(f"   intro.inc         palette 17 bytes, prompt "
          f"\"{TEXT}\" {len(TEXT) * GLYPH_W}x8 at ({x0},{TEXT_Y}), "
          f"2 x {n_bytes * 8} bytes")


if __name__ == "__main__":
    main()
