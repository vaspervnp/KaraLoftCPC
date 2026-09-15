#!/usr/bin/env python3
"""Acceptance test for the span exporter.

The exporter throws away two thirds of every frame - the transparent
two thirds - so the only thing worth asserting is that the third it
keeps, put back through the blitter's own arithmetic, reproduces the
artwork pixel for pixel. That is what this does: it composites each
frame over a RANDOM background the way the Z80 will,

    SCREEN = (SCREEN AND MASK) OR DATA

and checks that every opaque pixel came out the pen the art asked for
and every transparent one came out exactly the background it was over.
A mask convention inverted, a skip off by one, a span a byte short, an
interleave the wrong way round: none of those survive it.
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cpclib
from aseprite2spans import game_palette, mirror_byte

from PIL import Image

ROOT = os.path.join(HERE, "..")
# What the build actually ships, splits and all: the sheet is bigger
# than a 16 KB bank, so it is exported twice with different tags.
SHEETS = [("KCORE",  "heroine_cpc_mode0_sheet",      "kara_core.bin",
           ["idle", "walk", "jump", "shoot_draw", "shoot"]),
          ("KEXTRA", "heroine_cpc_mode0_sheet",      "kara_extra.bin",
           ["run", "roll"]),
          ("KSWIM",  "heroine_cpc_mode0_swim_sheet", "kara_swim.bin", None)]

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def decode_blob(blob, n_frames, bw, bh):
    """Span blob -> one (pen or None) grid per frame, the blitter's way.

    Mirrors what the Z80 will do rather than what the exporter did, so
    the two can disagree: walk the frame table, then each line's
    (skip, count) and its interleaved pairs, compositing over a
    background chosen so that every transparent pixel is recognisable.
    """
    frames = []
    malformed = []
    for f in range(n_frames):
        off = blob[2 * f] | (blob[2 * f + 1] << 8)
        y0, lines = blob[off], blob[off + 1]
        p = off + 2
        if y0 + lines > bh:
            malformed.append((f, "runs past the bottom of the box"))
        grid = [[None] * (2 * bw) for _ in range(bh)]
        # A different background pen under every pixel, so a transparent
        # one that came out right proves the mask let THAT pen through
        # and not just some pen.
        rng = random.Random(f)
        bg = [[rng.randrange(16) for _ in range(2 * bw)] for _ in range(bh)]
        for i in range(lines):
            skip, count = blob[p], blob[p + 1]
            p += 2
            y = y0 + i
            # A span that leaves the box would make the blitter write
            # into the next screen row, which is the whole reason the
            # engine clips - so it is a fault here, not an exception.
            if skip + count > bw or y >= bh:
                malformed.append((f, f"line {y}: skip {skip} + count {count} "
                                     f"leaves a {bw}-byte box"))
                p += 2 * count
                continue
            for b in range(count):
                mask, data = blob[p], blob[p + 1]
                p += 2
                x = 2 * (skip + b)
                under = cpclib.encode_pixels(bg[y][x], bg[y][x + 1])
                out = (under & mask) | data
                lo, hi = cpclib.decode_byte(out)
                grid[y][x] = (lo, bg[y][x])
                grid[y][x + 1] = (hi, bg[y][x + 1])
        frames.append((grid, bg, p - off))
    return frames, malformed


def expected(rgba, box, palette):
    """What the art says each pixel should be: a pen, or None if clear."""
    x0, y0, w, h = box["x"], box["y"], box["w"], box["h"]
    crop = rgba.crop((x0, y0, x0 + w, y0 + h))
    pens = cpclib.quantise(crop, palette)
    px = crop.load()
    return [[pens[y][x] if px[x, y][3] else None for x in range(w)]
            for y in range(h)]


def main():
    palette = game_palette(os.path.join(ROOT, "src", "palette.asm"))
    print(f"\n  palette from src/palette.asm: {palette}")

    print("\n  Mode 0 pixel-swap table:")
    tbl = [mirror_byte(b) for b in range(256)]
    check("mirroring is its own inverse", all(tbl[tbl[b]] == b for b in range(256)))
    swapped = all(cpclib.decode_byte(tbl[cpclib.encode_pixels(a, b)]) == (b, a)
                  for a in range(16) for b in range(16))
    check("mirroring swaps the two pixels and keeps their pens", swapped,
          "all 256 pen pairs")
    path = os.path.join(ROOT, "build", "mode0_mirror.bin")
    if os.path.exists(path):
        check("the emitted table matches", open(path, "rb").read() == bytes(tbl))

    for name, stem, binname, tags in SHEETS:
        js = os.path.join(ROOT, "assets", "sprites", stem + ".json")
        blob_path = os.path.join(ROOT, "build", binname)
        if not os.path.exists(blob_path):
            check(f"{name}: {binname} exists", False, "run build.sh first")
            continue
        meta = json.load(open(js))
        info = meta["frames"]
        if isinstance(info, dict):
            info = [info[k] for k in sorted(info)]
        if tags:                        # the same subset, in the same order
            by_name = {t["name"]: t for t in meta["meta"]["frameTags"]}
            info = [info[i] for w in tags
                    for i in range(by_name[w]["from"], by_name[w]["to"] + 1)]
        rgba = Image.open(os.path.join(os.path.dirname(js),
                                       meta["meta"]["image"])).convert("RGBA")
        blob = open(blob_path, "rb").read()
        fw, fh = info[0]["frame"]["w"], info[0]["frame"]["h"]
        bw = fw // 2
        print(f"\n  {name} from {stem}: {len(info)} frames of {fw}x{fh}, "
              f"blob {len(blob)} bytes"
              + (f", tags {','.join(tags)}" if tags else ""))
        check(f"{name}: fits a 16 KB bank", len(blob) <= 16384,
              f"{len(blob)} bytes, {16384 - len(blob)} spare")

        # the frame table has to cover the blob exactly, in order
        offs = [blob[2 * i] | (blob[2 * i + 1] << 8) for i in range(len(info))]
        ordered = offs == sorted(offs) and offs[0] == 2 * len(info)
        check(f"{name}: frame table is ordered and starts past itself", ordered,
              f"first offset {offs[0]}, table {2 * len(info)} bytes")

        decoded, malformed = decode_blob(blob, len(info), bw, fh)
        check(f"{name}: every span stays inside its frame box", not malformed,
              f"{len(malformed)} bad: {malformed[:3]}")
        end = offs[-1] + decoded[-1][2]
        check(f"{name}: frames tile the blob with nothing left over",
              end == len(blob), f"frames end at {end}, blob is {len(blob)}")

        wrong = bad_frames = 0
        opaque = 0
        for i, f in enumerate(info):
            want = expected(rgba, f["frame"], palette)
            grid, bg, _ = decoded[i]
            n = 0
            for y in range(fh):
                for x in range(fw):
                    got = grid[y][x]
                    if want[y][x] is None:
                        # transparent: the mask must have let the
                        # background through untouched
                        ok = got is None or got[0] == bg[y][x]
                    else:
                        opaque += 1
                        ok = got is not None and got[0] == want[y][x]
                    if not ok:
                        n += 1
            wrong += n
            bad_frames += bool(n)
        check(f"{name}: every frame composites back to the art", wrong == 0,
              f"{wrong} wrong pixels in {bad_frames} of {len(info)} frames, "
              f"{opaque} opaque pixels checked")

        # the .inc the assembler reads has to agree with the blob
        incpath = os.path.join(ROOT, "build", binname.replace(".bin", ".inc"))
        if os.path.exists(incpath):
            inc = open(incpath).read()
            def eq(sym):
                for line in inc.splitlines():
                    if line.split(" ")[0] == sym:
                        return int(line.split("equ")[1].strip().split()[0])
                return None
            check(f"{name}: .inc agrees with the blob",
                  eq(f"{name}_FRAMES") == len(info)
                  and eq(f"{name}_BLOB_SIZE") == len(blob)
                  and eq(f"{name}_BOX_W") == bw and eq(f"{name}_BOX_H") == fh,
                  f"FRAMES={eq(name + '_FRAMES')} SIZE={eq(name + '_BLOB_SIZE')} "
                  f"BOX={eq(name + '_BOX_W')}x{eq(name + '_BOX_H')}")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(fails))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
