#!/usr/bin/env python3
"""ZX0-pack the asset blobs, through RASM's own cruncher.

Why ZX0, measured on kara_core.bin (10,910 bytes) with every cruncher
RASM ships and every depacker in /home/vasilhs/rasm/decrunch, each one
run on a 6128 and checked byte for byte against the original:

    algorithm      packed  ratio  depacker   T a byte   frames
    ZX0 fast         2129  19.5%    189 B       49.0      6.7
    ZX0 standard     2129  19.5%     70 B       62.4      8.5
    Exomizer         2101  19.3%    332 B      153.7     21.0
    aPLib fast       2153  19.7%    238 B       64.9      8.9
    ZX7 turbo        2284  20.9%     90 B       67.4      9.2
    LZ48             4583  42.0%     72 B       49.6      6.8

Exomizer packs 28 bytes tighter and costs three times the depack time
and 143 more bytes of depacker; LZ48 is as fast and packs half as well.
ZX0 is best on both axes at once, which is unusual and is why there is
no trade-off to argue about here.

**This buys disc and load time, not frame time.** The blitter composites
from uncompressed bytes in a bank, so every blob is depacked once at the
level transition and drawn from RAM after that. It does not move the
in-frame budget in CLAUDE.md 9 by one T-state.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "..", "build")


def pack(name):
    src = os.path.join(BUILD, name)
    out = os.path.join(BUILD, name.replace(".bin", ".zx0"))
    asm = os.path.join(BUILD, "_pack.asm")
    with open(asm, "w") as f:
        f.write(f'        org 0\n        LZX0\n        incbin "{src}"\n'
                f'        LZCLOSE\n')
    r = subprocess.run(["rasm", asm, "-amper", "-ob", out],
                       capture_output=True, text=True)
    os.remove(asm)
    if r.returncode or not os.path.exists(out):
        raise SystemExit(f"packing {name} failed:\n{r.stdout}{r.stderr}")
    return os.path.getsize(src), os.path.getsize(out)


def main():
    names = sys.argv[1:]
    raw = pk = 0
    for n in names:
        if not os.path.exists(os.path.join(BUILD, n)):
            continue
        a, b = pack(n)
        raw += a
        pk += b
        print(f"  {n:<20}{a:7d} -> {b:6d}  {100 * b / a:5.1f}%")
    if raw:
        print(f"  {'ZX0 total':<20}{raw:7d} -> {pk:6d}  {100 * pk / raw:5.1f}%"
              f"   ({raw - pk} bytes off the disc)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
