#!/usr/bin/env python3
"""Acceptance test for the level loader.

A level arrives as four or five ZX0 streams, one per bank, each of them
a 16 KB image with the level's blobs laid out at fixed addresses. Three
things have to hold:

1. Every stream unpacks byte for byte into its bank, ON THE HARDWARE and
   through the depacker the engine actually uses. A cruncher that packs
   and a depacker that unpacks are two separate claims.
2. Every stream fits the staging buffer, because the loader reads one
   file at a time into base RAM and a stream that overran would land in
   the save-under buffers.
3. build/levels/banks.inc agrees with where the blobs really are - that
   file is what the engine will index the art by, and nothing else
   checks it.

It also reports what a level change costs, which is the number that
decides whether it needs a loading screen.
"""
import json
import os
import re
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import level_banks                                            # noqa: E402
from bench import boot, symbols, sync, STUB          # noqa: E402

# read_ram() reads the base 64 KB and ignores the RAM configuration, so
# it returns bank 1 - still holding the bootstrap - however the window
# is paged. peek() is the CPU-visible read and is the only one that
# sees a bank. It is a call per byte, which is why this reads the
# unpacked image once and compares in Python rather than sampling.
def read_bank(m, addr, n):
    return bytes(m.peek(addr + i) for i in range(n))

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LEV = os.path.join(ROOT, "build", "levels")
STAGE = 0x8000
# bench.py's stub sits at &9000 and the biggest packed bank is 4,695
# bytes, which reaches &925F - so this suite needs its own stub out of
# the staging buffer's way. &A000-&A6FF is free; AMSDOS starts at &A700.
MYSTUB = 0xA000

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def unpack(m, sym, cfg, packed):
    """Poke a stream at STAGE, run UNPACK_BANK, return the T-states."""
    m.write_ram(STAGE, packed)
    code = bytes([0xF3,                                 # di
                  0x21, STAGE & 0xFF, STAGE >> 8,       # ld hl,STAGE
                  0x3E, cfg,                            # ld a,cfg
                  0xCD, sym["UNPACK_BANK"] & 0xFF, sym["UNPACK_BANK"] >> 8,
                  0x18, 0xFE])                          # jr $
    m.write_ram(MYSTUB, code)
    m.set_pc(MYSTUB)
    end = MYSTUB + len(code) - 2
    for us in range(1, 2_000_000):
        m.run_us(1)
        if m.pc == end:
            return us * 4
    return None


def disc_check(m, sym):
    """LEVEL_LOAD end to end: off the floppy, through ZX0, into the bank.

    The streams are raw sectors past AMSDOS's files, read by the
    engine's own uPD765 driver, because the firmware went out with the
    ROMs at boot. This is the only check that exercises the driver, the
    layout tool and the unpacker together - and the layout tool writes
    the disc image from the same sizes it wrote the include from, so a
    disagreement between them shows up here as a wrong byte.
    """
    if "LEVEL_LOAD" not in sym:
        check("LEVEL_LOAD is linked", False, "rebuild first")
        return
    print("\n  LEVEL_LOAD, off the disc:")
    names = sorted(x for x in os.listdir(LEV)
                   if x.startswith("level") and os.path.isdir(os.path.join(LEV, x)))
    bad = missing = 0
    for i, lvl in enumerate(names):
        for k, kind in enumerate(("lvl", "set")):
            d = os.path.join(LEV, lvl)
            streams = sorted(f for f in os.listdir(d)
                             if f.startswith(kind + "_") and f.endswith(".zx0"))
            if not streams:
                continue
            code = bytes([0xF3, 0x3E, i * 2 + k,
                          0xCD, sym["LEVEL_LOAD"] & 0xFF, sym["LEVEL_LOAD"] >> 8,
                          0x30, 0x01,               # jr nc,+1  - carry = ok
                          0x00,
                          0x18, 0xFE])
            m.write_ram(MYSTUB, code)
            m.set_pc(MYSTUB)
            end, us = MYSTUB + len(code) - 2, None
            for t in range(1, 8_000_000):
                m.run_us(1)
                if m.pc == end:
                    us = t
                    break
            if us is None:
                check(f"{lvl} {kind} loads", False, "ran away")
                continue
            wrong = 0
            for f in streams:
                cfg = int(f.split("_")[1].split(".")[0], 16)
                raw = open(os.path.join(d, f[:-4] + ".bin"), "rb").read()
                m.write_ram(MYSTUB + 0x40,
                            bytes([0xF3, 0x01, cfg, 0x7F, 0xED, 0x49, 0x18, 0xFE]))
                m.set_pc(MYSTUB + 0x40)
                for _ in range(80):
                    m.run_us(1)
                got = read_bank(m, 0x4000, len(raw))
                wrong += sum(1 for a, b in zip(got, raw) if a != b)
            bad += wrong
            print(f"    {lvl:<20}{kind}  {len(streams)} banks"
                  f"   {us * 4:9d} T = {us / 1e6:.2f} s"
                  f"   {'ok' if not wrong else str(wrong) + ' WRONG'}")
    check("LEVEL_LOAD brings every bank off the disc byte-exact",
          bad == 0 and not missing, f"{bad} wrong bytes")


def main():
    sym = symbols()
    if "UNPACK_BANK" not in sym:
        check("UNPACK_BANK is linked", False, "rebuild first")
        return 1
    m = boot(sym)
    sync(m, sym)

    inc = open(os.path.join(LEV, "banks.inc")).read()
    equ = {mm.group(1): int(mm.group(2), 16) for mm in
           re.finditer(r"^(\S+)\s+equ\s+&([0-9A-F]+)", inc, re.M)}

    levels = sorted(x for x in os.listdir(LEV)
                    if x.startswith("level") and os.path.isdir(os.path.join(LEV, x)))
    bad_bytes = over_stage = 0
    total_cost = {}
    print()
    for lvl in levels:
        d = os.path.join(LEV, lvl)
        for kind in ("lvl", "set"):
            streams = sorted(f for f in os.listdir(d)
                             if f.startswith(kind + "_") and f.endswith(".zx0"))
            if not streams:
                continue
            cost = 0
            for f in streams:
                cfg = int(f.split("_")[1].split(".")[0], 16)
                packed = open(os.path.join(d, f), "rb").read()
                raw = open(os.path.join(d, f[:-4] + ".bin"), "rb").read()
                if len(packed) > 0x2000:
                    over_stage += 1
                t = unpack(m, sym, cfg, packed)
                got = read_bank(m, 0x4000, len(raw))
                if got != raw:
                    bad_bytes += sum(1 for a, b in zip(got, raw) if a != b)
                cost += t or 0
            total_cost[f"{lvl} {kind}"] = cost
            print(f"  {lvl:<20}{kind}  {len(streams)} banks, "
                  f"{sum(os.path.getsize(os.path.join(d, f)) for f in streams):6d}"
                  f" packed   {cost:8d} T = {cost / 79872:4.1f} frames"
                  f" = {cost / 79872 / 50:.2f} s")
    # leave the machine as the game expects it
    m.write_ram(MYSTUB, bytes([0xF3, 0x01, 0xC0, 0x7F, 0xED, 0x49, 0x18, 0xFE]))
    m.set_pc(MYSTUB)
    for _ in range(200):
        m.run_us(1)

    check("every bank unpacks byte-exact on the hardware", bad_bytes == 0,
          f"{bad_bytes} wrong bytes")
    check("every stream fits the staging buffer", over_stage == 0,
          f"{over_stage} streams over {0x2000} bytes")

    # ---- banks.inc has to describe the images it was built from ------
    wrong = []
    for lvl in levels:
        d = os.path.join(LEV, lvl)
        pre = "L" + lvl[5] + "_"
        for sym_name, addr in equ.items():
            if not sym_name.startswith(pre) or not sym_name.endswith("_ADDR"):
                continue
            blob = sym_name[len(pre):-5].lower()
            bank = equ.get(sym_name[:-5] + "_BANK")
            src = os.path.join(d, blob + ".bin")
            if not os.path.exists(src):
                # KACT is one symbol and two files: a level with no
                # ladder tile in its tileset carries the action blob
                # that stops before `climb` (CLAUDE.md 7.1). Resolved
                # the way the allocator resolves it, so a level that got
                # the wrong one fails here.
                if blob == "kact" and not level_banks.has_ladder(lvl):
                    blob = "kactnoclimb"
                src = os.path.join(LEV, "_shared", blob + ".bin")
            if not os.path.exists(src) or bank is None:
                wrong.append((sym_name, "no such blob"))
                continue
            want = open(src, "rb").read()
            for kind in ("lvl", "set"):
                img = os.path.join(d, f"{kind}_C{bank & 15:X}.bin")
                if bank == 0xC0:
                    img = os.path.join(d, f"{kind}_C0.bin")
                if not os.path.exists(img):
                    continue
                data = open(img, "rb").read()
                o = addr - 0x4000
                if data[o:o + len(want)] == want:
                    break
            else:
                wrong.append((sym_name, f"not at &{addr:04X} of bank &{bank:02X}"))
    check("banks.inc points at the blob it says", not wrong,
          f"{len(wrong)} bad" + (f": {wrong[:3]}" if wrong else ""))

    disc_check(m, sym)

    worst = max(total_cost.items(), key=lambda kv: kv[1])
    print(f"\n  worst level change: {worst[0]} at {worst[1]} T "
          f"= {worst[1] / 79872 / 50:.2f} s of unpacking, before the disc read")
    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(fails))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
