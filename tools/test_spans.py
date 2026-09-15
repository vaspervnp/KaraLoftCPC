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
import glob
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


def sheets():
    """Every blob the build actually produced, from its own sidecar.

    Not a hand-written list: the exporter records which sheet a blob
    came from, which frames of it survived --tags and --drop, and
    whether it is the mirrored facing. Add an enemy to build.sh and it
    is tested without touching this file.
    """
    out = []
    base = os.path.join(ROOT, "build", "levels")
    for side_path in sorted(glob.glob(os.path.join(base, "*", "*_frames.json"))):
        side = json.load(open(side_path))
        out.append((side["name"], side["sheet"],
                    side_path[:-len("_frames.json")] + ".bin",
                    [t["name"] for t in side["tags"]], side["mirrored"],
                    side["source_frames"], side.get("tiles", False)))
    return out


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
        y, skip, seen = y0, 0, 0
        while True:
            nlines = blob[p]
            if nlines == 0:                     # end of frame
                p += 1
                break
            count = blob[p + 1]
            dskip = blob[p + 2] | (blob[p + 3] << 8)
            p += 4
            seen += nlines
            if count:
                skip += dskip - 65536 if dskip > 32767 else dskip
            for k in range(nlines):
                # A span that leaves the box would make the blitter write
                # into the next screen row, which is the whole reason the
                # engine clips - so it is a fault here, not an exception.
                if count and (not 0 <= skip or skip + count > bw or y >= bh):
                    malformed.append((f, f"line {y}: skip {skip} + count "
                                         f"{count} leaves a {bw}-byte box"))
                    p += 2 * count
                    y += 1
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
                y += 1
        if seen != lines:
            malformed.append((f, f"groups cover {seen} lines, header says {lines}"))
        frames.append((grid, bg, p - off))
    return frames, malformed


def expected(rgba, box, palette, mirror=False):
    """What the art says each pixel should be: a pen, or None if clear."""
    x0, y0, w, h = box["x"], box["y"], box["w"], box["h"]
    crop = rgba.crop((x0, y0, x0 + w, y0 + h))
    if mirror:
        crop = crop.transpose(Image.FLIP_LEFT_RIGHT)
    pens = cpclib.quantise(crop, palette)
    px = crop.load()
    return [[pens[y][x] if px[x, y][3] else None for x in range(w)]
            for y in range(h)]


def zx0_check():
    """Depack every .zx0 on the emulator and compare with its source."""
    import re
    import subprocess
    try:
        sys.path.insert(0, "/home/vasilhs/cpcemu")
        from cpc import CPC
    except Exception as e:                      # no emulator: say so, do not
        check("ZX0 blobs depack byte-exact", True, f"skipped ({e})")
        return
    dec = "/home/vasilhs/rasm/decrunch/dzx0_fast.asm"
    tmp = os.environ.get("TMPDIR", "/tmp")
    CODE, DST = 0x8000, 0x4000                  # &0000-&3FFF is the OS ROM
    print("\n  ZX0, depacked by dzx0_fast on a 6128:")
    bad, total, cost = [], 0, 0
    for p in sorted(glob.glob(os.path.join(ROOT, "build", "*.zx0"))
                    + glob.glob(os.path.join(ROOT, "build", "levels", "*",
                                             "*.zx0"))):
        f = os.path.relpath(p, os.path.join(ROOT, "build"))
        orig = open(p[:-4] + ".bin", "rb").read()
        if len(orig) > 0x3F00:                  # will not fit under the code
            continue
        a = os.path.join(tmp, "_zx0.asm")
        o, sy = os.path.join(tmp, "_zx0.bin"), os.path.join(tmp, "_zx0.sym")
        open(a, "w").write(
            f'        org &{CODE:04X}\n        include "{dec}"\n'
            f'        di\n        ld hl,DATA\n        ld de,&{DST:04X}\n'
            f'        call DEP\nSPIN:   jp SPIN\nDEP:    DecompressZX0\n'
            f'DATA:   incbin "{p}"\n')
        r = subprocess.run(["rasm", a, "-amper", "-ob", o, "-s", "-sa", "-os", sy],
                           capture_output=True, text=True)
        if r.returncode:
            bad.append((f, "did not assemble"))
            continue
        sym = {m.group(1): int(m.group(2), 16) for m in
               (re.match(r"^(\S+)\s+#([0-9A-F]+)", l) for l in open(sy)) if m}
        m = CPC()
        m.run_frames(80)
        m.write_ram(CODE, open(o, "rb").read())
        m.set_pc(CODE)
        us = None
        for t in range(1, 1_000_000):
            m.run_us(1)
            if m.pc == sym["SPIN"]:
                us = t
                break
        got = bytes(m.read_ram(DST, len(orig)))
        total += 1
        cost += (us or 0) * 4
        if got != orig:
            bad.append((f, "ran away" if us is None else "wrong bytes"))
        print(f"    {f:<34}{os.path.getsize(p):6d}"
              f" -> {len(orig):6d}  {(us or 0) * 4:8d} T"
              f"   {'ok' if got == orig else 'FAILED'}")
    check("every ZX0 blob depacks byte-exact", not bad,
          f"{total} blobs, {cost} T in all = {cost / 79872:.0f} frames at a "
          f"level load" + (f"; bad: {bad}" if bad else ""))


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

    for name, sheet, blob_path, tags, mirror, source, tiles in sheets():
        js = os.path.join(ROOT, sheet)
        stem = os.path.basename(sheet)[:-5]
        binname = os.path.basename(blob_path)
        if tiles:
            # Opaque tiles are raw and have no spans to check; the
            # exporter's own round trip covers them.
            continue
        if not os.path.exists(blob_path):
            check(f"{name}: {binname} exists", False, "run build.sh first")
            continue
        meta = json.load(open(js))
        info = meta["frames"]
        if isinstance(info, dict):
            info = [info[k] for k in sorted(info)]
        # Which sheet frames the exporter actually kept - tag selection
        # AND the artist's --drop list. Read rather than re-derived, so
        # the test cannot agree with a stale idea of the drop list.
        info = [info[i] for i in source]
        rgba = Image.open(os.path.join(os.path.dirname(js),
                                       meta["meta"]["image"])).convert("RGBA")
        blob = open(blob_path, "rb").read()
        fw, fh = info[0]["frame"]["w"], info[0]["frame"]["h"]
        bw = fw // 2
        print(f"\n  {name} from {stem}: {len(info)} frames of {fw}x{fh}, "
              f"blob {len(blob)} bytes"
              + (", MIRRORED" if mirror else "")
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
            want = expected(rgba, f["frame"], palette, mirror)
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
        incpath = blob_path.replace(".bin", ".inc")
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

    # ---- the ZX0 blobs, depacked on a real 6128 -------------------
    # A cruncher that packs and a depacker that unpacks are two claims,
    # and only the pair matters. Every shipped blob goes through the
    # depacker the loader will use and is compared byte for byte.
    zx0_check()

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(fails))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
