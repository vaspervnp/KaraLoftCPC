#!/usr/bin/env python3
"""Module 1 acceptance test: the boot, the banks, and the interrupt.

IT NO LONGER HAS A SCREEN TO READ. The Module 1-3 acceptance screen -
colour bars for the Mode 0 encoding, five green blocks for the banks, a
heartbeat lamp for the loop - has been deleted along with the 16x48
blitter that drew the placeholder heroine over it. What it proved is
still true and still worth checking; it is just no longer painted:

  1. the disc loads, the bootstrap relocates the core and the game runs
     from &0040 with both ROMs out (screen mode 0, LEVEL_OK set)
  2. BANK_TEST's own verdict bytes - one per configuration - are PASS.
     It writes to each bank through the &4000 window and reads back
     through the next one, which is the check the green blocks showed
  3. IRQ_TICKS advances: the IM 1 handler at &0038 is ours and firing
  4. FRAME_COUNT advances: the main loop is going round
  5. and it is going round at 50 Hz - six interrupt ticks to the frame

The Mode 0 encoding the colour bars proved is checked by
tools/test_cpclib.py against the hardware palette, and on the screen by
every suite that reconstructs what the blitter should have written.
"""
import os
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cpc import CPC                                            # noqa: E402
from bench import symbols                                      # noqa: E402

sym = symbols()
DSK = os.path.join(os.path.dirname(__file__), "..", "build", "kara.dsk")
PEN_GREEN, PEN_RED = 0xFC, 0xCC          # palette.asm - a solid pen byte

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


c = CPC()
c.run_frames(200)
c.insert_disc(os.path.abspath(DSK))
c.type_text('RUN"DISC\n')
c.run_frames(400)
for _ in range(200):                     # LEVEL_LOAD is 1.4 s with DI
    c.run_frames(2)
    if c.peek(sym["LEVEL_OK"]):
        break
# ... and then the title screen waits for a key, not for a timer
from cpcboot import past_intro           # noqa: E402
past_intro(c, sym)
c.run_frames(6)

print("boot:")
check("screen mode is 0", c.mode == 0, f"mode={c.mode}")
check("the level came off the disc", c.peek(sym["LEVEL_OK"]) != 0,
      "LEVEL_OK - the FDC driver read every bank and unpacked it")
check("the core is running from &0040, not &4000",
      0x40 <= c.pc < 0x4000, f"PC = &{c.pc:04X}")

print("\nthe banks, by BANK_TEST's own verdict:")
names = ["&C0", "&C4", "&C5", "&C6", "&C7"]
verdict = c.read_ram(sym["BANK_RESULT"], 5)
for i, nm in enumerate(names):
    check(f"bank {nm} holds what was written to it", verdict[i] == PEN_GREEN,
          f"&{verdict[i]:02X} - " + ("pass" if verdict[i] == PEN_GREEN
                                     else "FAIL" if verdict[i] == PEN_RED
                                     else "never written"))

print("\nthe interrupt and the loop:")
# LET HER LAND FIRST. She spawns above the roof and falls onto it, and a
# fall is the vertical camera: every row step repaints the bottom row's
# fourteen HUD characters from the tilemap on the frame the CRTC latches
# - 13,200 T, more than that frame has (CLAUDE.md 7.8). Measured from
# the boot frame this reads 48 of 50 and what it is measuring is the
# spawn, not the loop; tools/test_climb.py is where the cost of a climb
# is asserted, with the number in it.
c.run_frames(90)
t0 = c.peek(sym["IRQ_TICKS"])
f0 = c.peek(sym["FRAME_COUNT"])
c.run_frames(50)
t1 = c.peek(sym["IRQ_TICKS"])
f1 = c.peek(sym["FRAME_COUNT"])
ticks = (t1 - t0) & 255
frames = (f1 - f0) & 255
# 6 ticks a frame, in a byte that wraps, and the sample can start and
# end anywhere inside a frame - so it is 300 mod 256 give or take one.
check("IM 1 handler is firing", abs(ticks - ((50 * 6) & 255)) <= 2,
      f"{ticks} ticks in 50 frames, which is 300 in a byte - the firmware's "
      f"handler went out with the lower ROM, so this one is ours")
check("the main loop is going round", frames > 0,
      f"{frames} iterations in 50 frames")
# AND IT HOLDS 25 Hz, WHICH IS WHAT THE LOOP IS FOR. A game frame is two
# hardware frames (CLAUDE.md 9): the loop draws her on the first and
# erases her on the second, so she is on the screen for both sweeps and
# a frame it cannot pay for is not a hole where she was. 50 hardware
# frames is 25 iterations, and the gate array's 6 ticks a hardware frame
# is the clock that says the hardware frames really went by.
check("... and it holds 25 Hz", frames >= 24,
      f"{frames} of 50 hardware frames, against {ticks} ticks - the gate "
      f"array delivers exactly 6 a hardware frame, so 25 iterations is "
      f"two VSYNCs apiece with nothing dropped")

print("\n" + ("ALL CHECKS PASSED" if not fails
              else f"{len(fails)} FAILED: {fails}"))
sys.exit(1 if fails else 0)
