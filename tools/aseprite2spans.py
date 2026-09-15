#!/usr/bin/env python3
"""Aseprite sheet + JSON -> CPC Mode 0 SPAN-COMPRESSED sprite bank.

Why spans and not boxes
-----------------------
The drawn heroine is 24x64, which is 12 bytes by 64 lines: 768 bytes of
data and as much mask, so 1,536 a frame and 61,440 for the 40 land
frames. That is four 16 KB banks, and the machine has four in total. It
would also cost 49,152 T-states to composite, 62% of a frame.

But only about a third of the box has anything in it. Storing each line
as (skip, count) and then only the count bytes that are actually drawn
takes both numbers down by two thirds, and makes the 24x64 sprite
CHEAPER to draw than the 16x48 one it replaces. See CLAUDE.md 7.1.

Blob layout
-----------
Everything is relative to the blob's base, so the loader can put it at
whatever address the bank window happens to be:

    dw  offset of frame 0        <- FRAMES entries, 2 bytes each
    dw  offset of frame 1
    ...
    <frame 0>
    <frame 1>
    ...

and one frame is

    db  y0                       first line of the box with any pixels
    db  lines                    lines stored; trailing empty ones dropped
    then `lines` records, top to bottom:
        db  skip                 bytes from the box's left edge to the span
        db  count                bytes in the span, 0 for an empty line
        db  mask, data           ... count times, interleaved so the
                                     blitter walks both with one pointer

The interleave is the same convention as the old full-box format:
mask bits SET where the background shows through, so the blitter does
SCREEN = (SCREEN AND MASK) OR DATA.

ONE FACING IS STORED. Mirroring a Mode 0 byte is the fixed bit
permutation 7<->6, 5<->4, 3<->2, 1<->0, so the engine mirrors a span at
draw time through a 256-byte table rather than doubling the data.
`--mirror-table` writes that table out.

Usage:
    aseprite2spans.py sheet.json -o out.bin --inc out.inc --name KARA
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpclib

from PIL import Image

FRAME_MS = 20                       # 50 Hz


def game_palette(path):
    """The 16 pens the engine programs, read from src/palette.asm.

    Sprites MUST be quantised against the same pens the level uses, so
    the palette comes from the assembly source and not from the image.
    """
    src = open(path).read()
    block = src.split("PALETTE_DATA:")[1].split("PEN_SOLID")[0]
    values = [int(v, 16) for v in re.findall(r"db +&([0-9A-Fa-f]{2})", block)]
    if len(values) < 16:
        raise SystemExit(f"{path}: expected 16 pens + border, found {len(values)}")
    return [v & 0x1F for v in values[:16]]      # strip the &40 colour-select prefix


def mirror_byte(b):
    """Swap the two pixels a Mode 0 byte holds.

    Their bits interleave as p0 = 7,5,3,1 and p1 = 6,4,2,0, so exchanging
    the pixels is exchanging each of those pairs - a fixed permutation,
    which is why the engine can do it with one lookup.
    """
    out = 0
    for hi in (7, 5, 3, 1):
        if b & (1 << hi):
            out |= 1 << (hi - 1)
        if b & (1 << (hi - 1)):
            out |= 1 << hi
    return out


def encode_frame(rgba, box, palette):
    """One frame of the sheet -> its span record, and some statistics.

    Returns (bytes, span_bytes, box_bytes). A pixel is transparent where
    the art's alpha is 0; everything else is quantised against `palette`,
    which is why a sprite never introduces a colour the level cannot show.
    """
    x0, y0, w, h = box["x"], box["y"], box["w"], box["h"]
    if w % 2:
        raise SystemExit("frame width must be even: Mode 0 packs 2 pixels per byte")
    bw = w // 2
    px = rgba.load()

    crop = rgba.crop((x0, y0, x0 + w, y0 + h))
    pens = cpclib.quantise(crop, palette)
    cpx = crop.load()

    lines = []                                  # (skip, [(mask, data), ...])
    for y in range(h):
        run = []
        for b in range(bw):
            lo, hi = cpx[2 * b, y], cpx[2 * b + 1, y]
            left, right = lo[3] != 0, hi[3] != 0
            data = cpclib.encode_pixels(pens[y][2 * b] if left else 0,
                                        pens[y][2 * b + 1] if right else 0)
            run.append((cpclib.encode_mask(left, right), data, left or right))
        first = next((i for i, r in enumerate(run) if r[2]), None)
        if first is None:
            lines.append((0, []))
            continue
        last = max(i for i, r in enumerate(run) if r[2])
        lines.append((first, [(m, d) for m, d, _ in run[first:last + 1]]))

    # Drop empty lines off the top and the bottom. Interior ones stay,
    # as count = 0: a gap between her arm and her boot is one byte, and
    # a second index to skip it would cost more than it saves.
    top = next((i for i, (_, s) in enumerate(lines) if s), None)
    if top is None:
        raise SystemExit("frame is entirely transparent")
    bottom = max(i for i, (_, s) in enumerate(lines) if s)

    out = bytearray([top, bottom - top + 1])
    span_bytes = 0
    for skip, span in lines[top:bottom + 1]:
        out.append(skip)
        out.append(len(span))
        span_bytes += len(span)
        for mask, data in span:
            out.append(mask)
            out.append(data)
    return bytes(out), span_bytes, bw * h


def ident(name):
    return re.sub(r"[^A-Za-z0-9]", "_", name).upper()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json", help="the sheet's Aseprite JSON")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--inc", required=True)
    ap.add_argument("--name", required=True, help="symbol prefix, e.g. KARA")
    ap.add_argument("--palette", default=None)
    ap.add_argument("--mirror-table", default=None,
                    help="also write the 256-byte Mode 0 pixel-swap table")
    ap.add_argument("--tags", default=None,
                    help="comma-separated tags to emit, in this order. The "
                         "sheet is bigger than a 16 KB bank, so it is split "
                         "at export time and each blob numbers its own frames "
                         "from zero.")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    palette = game_palette(args.palette or os.path.join(here, "..", "src", "palette.asm"))

    meta = json.load(open(args.json))
    frames = meta["frames"]
    if isinstance(frames, dict):                # Aseprite's "hash" export
        frames = [frames[k] for k in sorted(frames)]
    sheet = os.path.join(os.path.dirname(os.path.abspath(args.json)),
                         meta["meta"]["image"])
    rgba = Image.open(sheet).convert("RGBA")

    tags = meta["meta"].get("frameTags", [])
    if args.tags:
        wanted = [t.strip() for t in args.tags.split(",")]
        by_name = {t["name"]: t for t in tags}
        missing = [w for w in wanted if w not in by_name]
        if missing:
            raise SystemExit(f"{args.json}: no such tag: {', '.join(missing)}")
        keep, tags, first = [], [], 0
        for w in wanted:
            t = by_name[w]
            n = t["to"] - t["from"] + 1
            keep += list(range(t["from"], t["to"] + 1))
            tags.append({**t, "from": first, "to": first + n - 1})
            first += n
        frames = [frames[i] for i in keep]

    boxes = {(f["frame"]["w"], f["frame"]["h"]) for f in frames}
    if len(boxes) != 1:
        raise SystemExit(f"frames are not all one size: {sorted(boxes)}")
    fw, fh = boxes.pop()

    blobs, span_total, box_total = [], 0, 0
    for f in frames:
        blob, span, box = encode_frame(rgba, f["frame"], palette)
        blobs.append(blob)
        span_total += span
        box_total += box

    table = 2 * len(blobs)
    offsets, cur = [], table
    for b in blobs:
        offsets.append(cur)
        cur += len(b)
    out = bytearray()
    for o in offsets:
        out += bytes([o & 0xFF, o >> 8])
    for b in blobs:
        out += b
    open(args.out, "wb").write(out)

    name = args.name.upper()
    inc = [f"; Generated by tools/aseprite2spans.py from {os.path.basename(args.json)}",
           "; Span-compressed Mode 0 frames - see the tool's header for the layout.",
           "",
           f"{name}_FRAMES".ljust(23) + f" equ {len(blobs)}",
           f"{name}_BOX_W".ljust(23) + f" equ {fw // 2}        ; bytes",
           f"{name}_BOX_H".ljust(23) + f" equ {fh}",
           f"{name}_BLOB_SIZE".ljust(23) + f" equ {len(out)}",
           ""]
    def equate(sym, value):
        inc.append(sym.ljust(23) + f" equ {value}")   # ljust alone runs a long
                                                      # name straight into "equ"
    for t in tags:
        tag = ident(t["name"])
        equate(f"{name}_{tag}_FIRST", t["from"])
        equate(f"{name}_{tag}_COUNT", t["to"] - t["from"] + 1)
        for kv in (t.get("data") or "").split(","):
            if "=" in kv:
                k, v = kv.split("=", 1)
                equate(f"{name}_{tag}_{ident(k)}", v.strip())
    inc.append("")
    inc.append("; How many 50 Hz frames each cel is held for, rounded from the")
    inc.append("; milliseconds Aseprite stores. One byte per frame.")
    inc.append(f"{name}_DURATION:")
    durs = [max(1, round(f.get("duration", FRAME_MS) / FRAME_MS)) for f in frames]
    for i in range(0, len(durs), 16):
        inc.append("                db " + ", ".join(str(d) for d in durs[i:i + 16]))
    open(args.inc, "w").write("\n".join(inc) + "\n")

    if args.mirror_table:
        open(args.mirror_table, "wb").write(bytes(mirror_byte(b) for b in range(256)))

    for t in tags:
        n = sum(len(blobs[i]) for i in range(t["from"], t["to"] + 1))
        print(f"    {t['name']:<12} {t['to'] - t['from'] + 1:2d} frames  {n:6d} bytes")
    pct = 100 * span_total / box_total
    print(f"{os.path.basename(args.json)}: {len(blobs)} frames of {fw}x{fh} "
          f"= {fw // 2} bytes x {fh} lines")
    print(f"  span {span_total} of {box_total} box bytes ({pct:.0f}%)")
    bank = 16384
    fit = "fits a bank" if len(out) <= bank else f"OVER a bank by {len(out) - bank}"
    print(f"  -> {args.out}  {len(out)} bytes, {bank - len(out)} spare - {fit} "
          f"(a full-box build would be {2 * box_total})")
    print(f"  -> {args.inc}")
    if args.mirror_table:
        print(f"  -> {args.mirror_table}  256 bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
