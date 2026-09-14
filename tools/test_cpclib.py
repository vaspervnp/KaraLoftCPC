#!/usr/bin/env python3
"""Round-trip and cross-check tests for the Mode 0 encoder.

CLAUDE.md requires every exporter to prove its encoding. This checks the
library against three independent references: itself (round trip), the
emulator's own decoder, and the hand-written table in src/palette.asm.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/home/vasilhs/cpcemu")

import cpclib
from cpc import _decode_byte

fails = []
def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)

# 1. every pen pair survives encode -> decode
bad = [(l, r) for l in range(16) for r in range(16)
       if cpclib.decode_byte(cpclib.encode_pixels(l, r)) != (l, r)]
check("all 256 pen pairs round-trip", not bad, str(bad[:4]))

# 2. every byte survives decode -> encode
bad = [b for b in range(256) if cpclib.encode_pixels(*cpclib.decode_byte(b)) != b]
check("all 256 bytes round-trip", not bad, str(bad[:4]))

# 3. agrees with the emulator's decoder, which is the hardware reference
bad = [b for b in range(256) if list(cpclib.decode_byte(b)) != _decode_byte(b, 0)]
check("agrees with the emulator decoder", not bad, str(bad[:4]))

# 4. agrees with the PEN_SOLID table hand-written in the assembly source
src = open(os.path.join(HERE, "..", "src", "palette.asm")).read()
block = src.split("PEN_SOLID:")[1].split("PEN_GREEN")[0]
asm = [int(v, 16) for v in re.findall(r"&([0-9A-Fa-f]{2})", block)]
lib = [cpclib.solid_pen_byte(p) for p in range(16)]
check("PEN_SOLID in palette.asm matches", asm == lib, f"{[hex(v) for v in asm]}")

# 5. mask semantics: emulate the blitter and check both cases
def blit(screen, mask, data):
    return (screen & mask) | data

ok = True
for under_l, under_r in ((5, 9), (0, 15), (12, 3)):
    screen = cpclib.encode_pixels(under_l, under_r)
    for spr_l, spr_r in ((7, 2), (1, 14)):
        for opaque_l in (True, False):
            for opaque_r in (True, False):
                data = cpclib.encode_pixels(spr_l if opaque_l else 0,
                                            spr_r if opaque_r else 0)
                mask = cpclib.encode_mask(opaque_l, opaque_r)
                got = cpclib.decode_byte(blit(screen, mask, data))
                want = (spr_l if opaque_l else under_l,
                        spr_r if opaque_r else under_r)
                if got != want:
                    ok = False
check("masked blit keeps background under transparent pixels", ok)

# 6. screen_offset matches the formula the Z80 uses
bad = [ln for ln in range(200)
       if cpclib.screen_offset(0, ln) != (ln & 7) * 0x800 + (ln >> 3) * 80]
check("screen_offset matches the Z80 addressing", not bad)
check("screen fits in 16K", max(cpclib.screen_offset(79, ln) for ln in range(200)) < 0x4000)

# 7. palette table agrees with docs/cpc_palette.md
doc = open(os.path.join(HERE, "..", "docs", "cpc_palette.md")).read()
rows = re.findall(r"^\| *\d+ \| *([^|]+?) *\| *(\d+) \| *`&([0-9A-F]{2})` \| *(\d+),(\d+),(\d+) *\|$",
                  doc, re.M)
check("docs list all 27 colours", len(rows) == 27, f"found {len(rows)}")
bad = [r[0] for r in rows
       if cpclib.HW_COLOURS.get(int(r[1])) != (int(r[3]), int(r[4]), int(r[5]))
       or cpclib.gate_array_value(int(r[1])) != int(r[2], 16)]
check("library palette matches docs/cpc_palette.md", not bad, str(bad))

print("\n" + ("ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILED: {fails}"))
sys.exit(1 if fails else 0)
