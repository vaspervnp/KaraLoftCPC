#!/usr/bin/env python3
"""Round-trip the sprite exporter: PNG -> binary -> PNG.

Decodes kara_sprites.bin back into pens and transparency and compares it
against the source sheet quantised to the game palette. Anything the
exporter gets wrong -- interleaving, mask polarity, frame order, row order
-- shows up as a pixel mismatch here.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cpclib
from png2sprite import game_palette

from PIL import Image

FW, FH = 16, 48
ROOT = os.path.join(HERE, "..")

fails = []
def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


sheet = Image.open(os.path.join(ROOT, "assets", "placeholder", "kara_sheet.png")).convert("RGBA")
blob = open(os.path.join(ROOT, "build", "kara_sprites.bin"), "rb").read()
palette = game_palette(os.path.join(ROOT, "src", "palette.asm"))

frames = sheet.width // FW
frame_bytes = (FW // 2) * FH * 2

check("frame is 768 bytes, as plan.md 3.1 specifies", frame_bytes == 768, f"{frame_bytes}")
check("binary size matches frame count",
      len(blob) == frames * frame_bytes, f"{len(blob)} for {frames} frames")

bad_pen = bad_mask = 0
for n in range(frames):
    src = sheet.crop((n * FW, 0, (n + 1) * FW, FH))
    pens = cpclib.quantise(src, palette)
    px = src.load()
    off = n * frame_bytes
    for y in range(FH):
        for xb in range(FW // 2):
            mask = blob[off]
            data = blob[off + 1]
            off += 2
            got = cpclib.decode_byte(data)
            for i, x in enumerate((xb * 2, xb * 2 + 1)):
                opaque_src = px[x, y][3] >= 128
                bit = cpclib.MASK_LEFT if i == 0 else cpclib.MASK_RIGHT
                opaque_got = (mask & bit) == 0
                if opaque_got != opaque_src:
                    bad_mask += 1
                elif opaque_src and got[i] != pens[y][x]:
                    bad_pen += 1

check("transparency round-trips", bad_mask == 0, f"{bad_mask} wrong")
check("opaque pens round-trip", bad_pen == 0, f"{bad_pen} wrong")

# a sprite that is entirely transparent must leave the screen untouched
mask = cpclib.encode_mask(False, False)
data = cpclib.encode_pixels(0, 0)
under = cpclib.encode_pixels(11, 4)
check("fully transparent byte is a no-op", (under & mask) | data == under)

# the sheet must actually contain transparency, or the test proves nothing
alpha = sheet.getchannel("A")
check("source sheet has transparent and opaque pixels",
      alpha.getextrema() == (0, 255), str(alpha.getextrema()))

print("\n" + ("ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILED: {fails}"))
sys.exit(1 if fails else 0)
