#!/usr/bin/env python3
"""The FDC decisions cpcemu cannot disagree with.

The headless emulator resolves the controller synchronously and never
runs out of patience, so a driver can be wrong in four ways and still
pass every other suite here - which is what happened, and what showed
up on Retro Virtual Machine as a black screen.

None of that can be reproduced here. What CAN be checked is the code's
own logic in isolation: call the verdict routine with result bytes a
real controller produces and see what it says, time the transfer loop
against the controller's deadline, and prove the waits are counted out
rather than infinite. See docs/AmstradDskReadHowTo.md.
"""
import os
import re
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import boot, symbols, sync                       # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
STUB = 0xA000
DEADLINE_T = 128            # 32 us at 4 MHz - the uPD765's byte budget

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def call(m, sym, addr, timeout=400000):
    code = bytes([0xF3, 0xCD, addr & 0xFF, addr >> 8, 0x18, 0xFE])
    m.write_ram(STUB, code)
    m.set_pc(STUB)
    t = 0
    for _ in range(timeout):
        m.run_us(1)
        t += 4
        if m.pc == STUB + 4:
            return t
    return None


def verdict(m, sym, st0, st1, st2):
    """FDC_XFER_OK with those result bytes. True = the data is good."""
    m.poke(sym["DISC_ST0"], st0)
    m.poke(sym["DISC_ST1"], st1)
    m.poke(sym["DISC_ST2"], st2)
    # di : call FDC_XFER_OK : ld a,0 : adc a,a : ld (spill),a : jr $
    a = sym["FDC_XFER_OK"]
    spill = sym["DISC_SPILL"]
    code = bytes([0xF3, 0xCD, a & 0xFF, a >> 8, 0x3E, 0x00, 0x8F,
                  0x32, spill & 0xFF, spill >> 8, 0x18, 0xFE])
    m.write_ram(STUB, code)
    m.set_pc(STUB)
    for _ in range(4000):
        m.run_us(1)
        if m.pc == STUB + len(code) - 2:
            return m.peek(spill) == 1
    return None


def loop_cost():
    """T-states of FDC_READ_ONE's inner transfer loop, from the source.

    Counted rather than measured: the loop only runs while a real
    controller is feeding it, and the emulator's is instantaneous.
    Every instruction on the CPC is padded to a multiple of 4 T by the
    gate array, which is what the round-up below is.
    """
    src = open(os.path.join(ROOT, "src", "disc.asm")).read()
    body = src[src.index("\n.byte:"):src.index("\n                ld   (DISC_PTR),hl")]
    cost = {"in a,(c)": 12, "and": 8, "cp": 8, "jr": 12, "inc c": 4,
            "dec c": 4, "ld (hl),a": 8, "inc hl": 8, "dec de": 8,
            "ld a,d": 4, "or e": 4, "bit": 8}
    total, seen = 0, []
    for line in body.splitlines():
        line = re.sub(r"\s+", " ", line.split(";")[0].strip().lower())
        if not line or line.endswith(":"):
            continue
        if line.startswith(".") and ":" in line:
            line = line.split(":", 1)[1].strip()
        if not line:
            continue
        # the fast path is the one that takes the jr z and skips the bits
        if line.startswith("bit") or line.startswith("jr nz") or \
           line.startswith("jr .result"):
            continue
        for k, v in cost.items():
            if line.startswith(k):
                total += v
                seen.append((line, v))
                break
        else:
            raise SystemExit(f"unknown instruction in the transfer loop: {line}")
    return total, seen


def main():
    sym = symbols()
    for n in ("FDC_XFER_OK", "DISC_ST0", "DISC_ST1", "DISC_ST2", "DISC_SPILL",
              "FDC_OUT", "FDC_DRAIN", "DISC_READ"):
        if n not in sym:
            check(f"{n} is linked", False, "rebuild first")
            return 1
    m = boot(sym)
    sync(m, sym)

    # -----------------------------------------------------------------
    # 1. The verdict. This is the bug that shipped: a single-sector read
    #    sends EOT = R, so a real controller ends the transfer at the end
    #    of the cylinder and says so. cpcemu returns IC = 00 instead, so
    #    a test that only ever sees cpcemu's bytes cannot catch it.
    # -----------------------------------------------------------------
    print("\n  what the driver makes of result bytes a real uPD765 returns:")
    cases = [
        ("a plain normal read",              0x00, 0x00, 0x00, True),
        ("END OF CYLINDER - what RVM returns for every single-sector "
         "read", 0x40, 0x80, 0x00, True),
        ("EN together with OVERRUN",         0x40, 0x90, 0x00, False),
        ("sector not found",                 0x40, 0x04, 0x00, False),
        ("a CRC error in the data field",    0x40, 0xA0, 0x00, False),
        ("missing address mark",             0x40, 0x81, 0x00, False),
        ("NOT READY - no disc in the drive", 0x48, 0x00, 0x00, False),
        ("the cylinder byte disagreed",      0x40, 0x80, 0x10, False),
        ("invalid command",                  0x80, 0x00, 0x00, False),
        ("abnormal termination, polling",    0xC0, 0x00, 0x00, False),
    ]
    wrong = 0
    for name, st0, st1, st2, want in cases:
        got = verdict(m, sym, st0, st1, st2)
        mark = "ok " if got == want else "NO "
        if got != want:
            wrong += 1
        print(f"    {mark} ST0={st0:02X} ST1={st1:02X} ST2={st2:02X}  "
              f"{'good' if got else 'fault':<5}  {name}")
    check("the verdict matches a real controller on all ten", wrong == 0,
          f"{wrong} wrong")
    check("END OF CYLINDER alone is NOT a failure",
          verdict(m, sym, 0x40, 0x80, 0x00) is True,
          "this is the one that black-screened RVM")
    check("...but NOT READY is, even with an empty ST1",
          verdict(m, sym, 0x48, 0x00, 0x00) is False,
          "an empty drive must not read as a good sector")

    # -----------------------------------------------------------------
    # 2. The transfer loop against the controller's 32 us a byte.
    # -----------------------------------------------------------------
    total, seen = loop_cost()
    print(f"\n  transfer loop, counted from the source: {total} T "
          f"= {total / 4:.0f} us a byte, deadline {DEADLINE_T} T")
    check("the transfer loop fits the controller's byte budget",
          total <= DEADLINE_T,
          f"{total} T of {DEADLINE_T}; an overrun here is invisible to cpcemu")
    src = open(os.path.join(ROOT, "src", "disc.asm")).read()
    body = src[src.index("\n.byte:"):src.index("\n                ld   (DISC_PTR),hl")]
    check("...and it holds the port in BC rather than reloading it",
          "ld   bc,FDC_STATUS" not in body and "ld   bc,FDC_DATA" not in body,
          "reloading both twice a byte is the 20 T that overran on RVM")
    check("...and it tests RQM, DIO and EXM in ONE read of the status",
          len(re.findall(r"in\s+a,\(c\)", body)) == 2 and
          "FDC_ST_RQM+FDC_ST_DIO+FDC_ST_EXM" in body,
          "a separate EXM read before RQM is the race that hung RVM")

    # -----------------------------------------------------------------
    # 3. Nothing may hang. With no controller answering, every wait has
    #    to come back - a failed load is recoverable, a dead machine is
    #    not.
    # -----------------------------------------------------------------
    print("\n  the waits are counted out, not infinite:")
    src_ok = True
    for name in ("FDC_OUT", "FDC_IN"):
        blk = src[src.index(f"\n{name}:"):]
        blk = blk[:blk.index("\n; ---")]
        if "dec  d" not in blk:
            src_ok = False
    check("FDC_OUT and FDC_IN count their polls", src_ok,
          "an uncounted spin here is the black screen with no way out")
    seekblk = src[src.index("\nFDC_SEEK:"):]
    seekblk = seekblk[:seekblk.index("\n; ---")]
    check("the seek gives up rather than spinning",
          "dec  d" in seekblk and "jr   nz,.wait" in seekblk)
    check("the seek is collected with SENSE INTERRUPT STATUS, not CB",
          "FDC_SENSE_INT" in seekblk and "and  &10" not in seekblk,
          "polling CB either falls through the seek or waits on itself")
    drain = src[src.index("\nFDC_DRAIN:"):]
    drain = drain[:drain.index("\n; ---")]
    check("the result is drained by status, not by a count",
          "bit  4,a" in drain and "djnz" not in drain,
          "SENSE with nothing pending returns ONE byte, not two")
    check("the drain runs before the first command too",
          "call FDC_DRAIN" in src[src.index("\nDISC_READ:"):],
          "AMSDOS ran before us and the chip keeps its state")

    # -----------------------------------------------------------------
    # 4. It still works end to end on the emulator we do have.
    # -----------------------------------------------------------------
    # di : ld a,0 : call LEVEL_LOAD : jr nc,fail : jr $ / fail: jr $
    code = bytes([0xF3, 0x3E, 0, 0xCD, sym["LEVEL_LOAD"] & 0xFF,
                  sym["LEVEL_LOAD"] >> 8, 0x30, 0x02, 0x18, 0xFE, 0x18, 0xFE])
    m.write_ram(STUB, code)
    m.set_pc(STUB)
    done = None
    for _ in range(8_000_000):
        m.run_us(1)
        if m.pc == STUB + 8:        # carry set: fell through the JR NC
            done = True
            break
        if m.pc == STUB + 10:       # the JR NC was taken
            done = False
            break
    check("a level still loads off the disc here", done is True,
          "carry clear" if done is False else "" if done else "ran away")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(fails))
        return 1
    print("ALL CHECKS PASSED")
    print("  NOTE: passing here is necessary and NOT sufficient. cpcemu\n"
          "  models the controller synchronously; confirm on Retro Virtual\n"
          "  Machine before believing the FDC works.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
