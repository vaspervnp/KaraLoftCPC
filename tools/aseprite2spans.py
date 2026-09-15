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

and one frame is a header and then GROUPS of lines:

    db  y0                       first line of the box with any pixels
    db  lines                    lines stored; empty ones off the ends dropped
    then groups, until nlines = 0:
        db  nlines               consecutive lines that share this span
        db  count                bytes in the span, 0 for blank lines
        dw  dskip                this group's skip minus the last one's,
                                 SIGNED and sign-extended to 16 bits so the
                                 blitter can add it to a screen address with
                                 ADD/ADC and no branch on the sign. The first
                                 group's "last one" is 0; a blank group's is
                                 0 too, since it moves no skip.
        db  mask, data           ... nlines x count times, interleaved so
                                     the blitter walks both with one pointer
    db  0                        end of frame

**Lines are grouped because the per-line bookkeeping, not the
composite, is what the blitter spends its time on.** Measured on the
real art: 58 lines of a heaviest frame carry 329 span bytes, so 5.7
bytes a line against ~300 T of reading (skip, count), computing the
entry into the unrolled run, and testing for the 2 KB seam. Consecutive
lines share a span 3.5 times out of 4, so saying it once per group and
not once per line takes that off ~60% of the lines.

The interleave is the same convention as the old full-box format:
mask bits SET where the background shows through, so the blitter does
SCREEN = (SCREEN AND MASK) OR DATA.

BOTH FACINGS ARE STORED, and `--mirror` is how the second one is made.
Mirroring a Mode 0 byte is the fixed permutation 7<->6, 5<->4, 3<->2,
1<->0, so doing it at DRAW time is one table lookup - except that the
lookup needs an index register and the blitter has none spare: HL has
to hold the mask/data because only (HL) works with AND/OR, DE the
screen, BC the save. Every way round it measured 96-136 T a byte
against 72, or about +7,900 T a frame, which the frame does not have.
Mirroring at export time costs a bank instead, and after the --drop
list there is a bank. See CLAUDE.md 7.1.

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


def encode_frame(rgba, box, palette, mirror=False):
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

    if mirror:
        # The box flips, so a span at [skip, skip+count) lands at
        # [bw-skip-count, bw-skip), its bytes reversed and each one's
        # two pixels swapped.
        lines = [(bw - skip - len(span), [(mirror_byte(m), mirror_byte(d))
                                          for m, d in reversed(span)])
                 if span else (0, [])
                 for skip, span in lines]

    # Drop empty lines off the top and the bottom. Interior ones stay,
    # as count = 0: a gap between her arm and her boot is one byte, and
    # a second index to skip it would cost more than it saves.
    top = next((i for i, (_, s) in enumerate(lines) if s), None)
    if top is None:
        raise SystemExit("frame is entirely transparent")
    bottom = max(i for i, (_, s) in enumerate(lines) if s)
    lines = lines[top:bottom + 1]

    out = bytearray([top, len(lines)])
    span_bytes = 0
    prev_skip = i = 0
    while i < len(lines):
        skip, span = lines[i]
        count = len(span)
        j = i + 1                       # how far the same span runs
        while (j < len(lines) and len(lines[j][1]) == count
               and (count == 0 or lines[j][0] == skip)):
            j += 1
        if count == 0:
            out += bytes([j - i, 0, 0, 0])      # blank lines: just step past
        else:
            d = skip - prev_skip
            out += bytes([j - i, count, d & 0xFF, 0xFF if d < 0 else 0])
            prev_skip = skip
            for k in range(i, j):
                span_bytes += count
                for mask, data in lines[k][1]:
                    out.append(mask)
                    out.append(data)
        i = j
    out.append(0)                               # end of frame
    return bytes(out), span_bytes, bw * h


def encode_tiles(rgba, frames, palette):
    """Tiles are opaque, so they are not spans and carry no mask.

    A level's tiles fill their own frame - pen 0 is black, not
    transparent - so the span format would store a full-width run on
    every line plus an all-zero mask beside it: twice the bytes and
    twice the work for nothing. They go out raw instead, row-major,
    which is the order the tile renderer walks them in.

    Returns (bytes, bytes_per_tile).
    """
    w, h = frames[0]["frame"]["w"], frames[0]["frame"]["h"]
    if w % 2:
        raise SystemExit("tile width must be even: Mode 0 packs 2 pixels a byte")
    out = bytearray()
    for f in frames:
        b = f["frame"]
        if (b["w"], b["h"]) != (w, h):
            raise SystemExit("tiles are not all one size")
        crop = rgba.crop((b["x"], b["y"], b["x"] + w, b["y"] + h))
        pens = cpclib.quantise(crop, palette)
        for y in range(h):
            for x in range(0, w, 2):
                out.append(cpclib.encode_pixels(pens[y][x], pens[y][x + 1]))
    return bytes(out), (w // 2) * h


def ident(name):
    return re.sub(r"[^A-Za-z0-9]", "_", name).upper()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json", help="the sheet's Aseprite JSON")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--inc", required=True)
    ap.add_argument("--name", required=True, help="symbol prefix, e.g. KARA")
    ap.add_argument("--palette", default=None)
    ap.add_argument("--tiles", action="store_true",
                    help="opaque tile sheet: emit raw row-major frames with "
                         "no mask and no frame table, all one size")
    ap.add_argument("--mirror", action="store_true",
                    help="emit the LEFT-facing blob: every frame flipped in "
                         "its box. See the header for why this is done here "
                         "and not in the blitter.")
    ap.add_argument("--mirror-table", default=None,
                    help="also write the 256-byte Mode 0 pixel-swap table")
    ap.add_argument("--drop", action="append", default=[], metavar="TAG=N,N",
                    help="drop these frames of a tag, NUMBERED FROM 1 as the "
                         "artist counts them in the sheet row. The dropped "
                         "frame's hold time is added to the one before it, so "
                         "thinning a cycle makes it coarser and not faster - "
                         "which matters for a walk, where the feet have to "
                         "keep up with the distance travelled.")
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

    # ---- thin the tags the artist asked to thin -------------------
    drops, keep_dur = {}, {}
    for spec in args.drop:
        if "=" not in spec:
            raise SystemExit(f"--drop wants TAG=N,N, got {spec!r}")
        tag, nums = spec.split("=", 1)
        drops[tag.strip()] = {int(n) for n in nums.split(",") if n.strip()}
    known = {t["name"] for t in tags}
    unknown = [t for t in drops if t not in known]
    if unknown:
        raise SystemExit(f"{args.json}: no such tag to drop from: "
                         f"{', '.join(unknown)}")
    if drops:
        keep, newtags = [], []
        for t in tags:
            gone = drops.get(t["name"], set())
            bad = [n for n in gone if not 1 <= n <= t["to"] - t["from"] + 1]
            if bad:
                raise SystemExit(f"{t['name']} has {t['to'] - t['from'] + 1} "
                                 f"frames; cannot drop {bad}")
            first = len(keep)
            for n in range(1, t["to"] - t["from"] + 2):
                i = t["from"] + n - 1
                if n in gone:
                    # Give its time to the frame before it - or after, if
                    # it WAS the first - so the cycle still lasts as long
                    # as it did and only gets coarser.
                    host = keep[-1] if keep and len(keep) > first else None
                    if host is None:
                        nxt = next((t["from"] + k - 1
                                    for k in range(n + 1, t["to"] - t["from"] + 2)
                                    if k not in gone), None)
                        host = nxt
                        if host is not None:
                            keep_dur[host] = keep_dur.get(
                                host, frames[host].get("duration", FRAME_MS))
                    if host is not None:
                        keep_dur[host] = (keep_dur.get(
                            host, frames[host].get("duration", FRAME_MS))
                            + frames[i].get("duration", FRAME_MS))
                    continue
                keep.append(i)
            newtags.append({**t, "from": first, "to": len(keep) - 1})
            if len(keep) == first:
                raise SystemExit(f"{t['name']}: every frame dropped")
        frames = [dict(frames[i], duration=keep_dur.get(i,
                       frames[i].get("duration", FRAME_MS))) for i in keep]
        tags = newtags
        kept_source = keep
        print(f"  dropped {sum(len(v) for v in drops.values())} frames: "
              + "; ".join(f"{k} {sorted(v)}" for k, v in drops.items()))
    else:
        kept_source = list(range(len(frames)))

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
        kept_source = [kept_source[i] for i in keep]

    boxes = {(f["frame"]["w"], f["frame"]["h"]) for f in frames}
    if len(boxes) != 1:
        raise SystemExit(f"frames are not all one size: {sorted(boxes)}")
    fw, fh = boxes.pop()

    if args.tiles:
        if args.mirror:
            raise SystemExit("--tiles and --mirror make no sense together")
        out, per = encode_tiles(rgba, frames, palette)
        open(args.out, "wb").write(out)
        name = args.name.upper()
        inc = [f"; Generated by tools/aseprite2spans.py from "
               f"{os.path.basename(args.json)}",
               "; Opaque tiles, row-major, no mask - see encode_tiles().",
               "",
               f"{name}_TILES".ljust(23) + f" equ {len(frames)}",
               f"{name}_TILE_W".ljust(23) + f" equ {fw // 2}        ; bytes",
               f"{name}_TILE_H".ljust(23) + f" equ {fh}",
               f"{name}_TILE_SIZE".ljust(23) + f" equ {per}",
               f"{name}_BLOB_SIZE".ljust(23) + f" equ {len(out)}",
               ""]
        for t in tags:
            tag = ident(t["name"])
            inc.append(f"{name}_{tag}_FIRST".ljust(23) + f" equ {t['from']}")
            inc.append(f"{name}_{tag}_COUNT".ljust(23)
                       + f" equ {t['to'] - t['from'] + 1}")
        open(args.inc, "w").write("\n".join(inc) + "\n")
        json.dump({"sheet": os.path.relpath(os.path.abspath(args.json),
                                            os.path.join(here, "..")),
                   "name": name, "mirrored": False, "tiles": True,
                   "box": [fw // 2, fh],
                   "source_frames": kept_source,
                   "tags": [{"name": t["name"], "from": t["from"], "to": t["to"]}
                            for t in tags]},
                  open(os.path.splitext(args.out)[0] + "_frames.json", "w"),
                  indent=1)
        print(f"{os.path.basename(args.json)}: {len(frames)} tiles of "
              f"{fw}x{fh} = {per} bytes each")
        print(f"  -> {args.out}  {len(out)} bytes")
        return 0

    blobs, span_total, box_total = [], 0, 0
    for f in frames:
        blob, span, box = encode_frame(rgba, f["frame"], palette, args.mirror)
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

    # Which sheet frames actually made it in, so the acceptance test
    # checks the blob against the SAME frames rather than re-deriving
    # the --drop list and drifting from it.
    side = os.path.splitext(args.out)[0] + "_frames.json"
    json.dump({"sheet": os.path.relpath(os.path.abspath(args.json),
                                       os.path.join(here, "..")),
               "name": name,
               "mirrored": bool(args.mirror),
               "box": [fw // 2, fh],
               "source_frames": kept_source,
               "tags": [{"name": t["name"], "from": t["from"], "to": t["to"]}
                        for t in tags]},
              open(side, "w"), indent=1)

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
    print(f"  -> {side}")
    if args.mirror_table:
        print(f"  -> {args.mirror_table}  256 bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
