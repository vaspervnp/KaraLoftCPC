#!/usr/bin/env python3
"""Module 1 acceptance test: boot kara.dsk and verify what it draws.

Checks, in order:
  1. the disc loads and the game takes over (screen mode becomes 0)
  2. the 16 colour bars read back as pens 0..15  -> Mode 0 encoding + VRAM map
  3. the five bank blocks are green              -> banking works
  4. IRQ_TICKS advances                          -> IM 1 handler installed
  5. the heartbeat block toggles                 -> main loop is alive

Screen positions come from the demo layout documented at the top of
src/main.asm; they move when that layout does.
"""
import sys, os
sys.path.insert(0, "/home/vasilhs/cpcemu")
from cpc import CPC
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import symbols                                      # noqa: E402

sym = symbols()

DSK = os.path.join(os.path.dirname(__file__), "..", "build", "kara.dsk")
SHOTS = sys.argv[1] if len(sys.argv) > 1 else "build"

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

# THE GAME BOOTS STRAIGHT ONTO THE ROOFTOP NOW. The colour bars, the bank
# self-test's verdict and the stripes belong to the Module 1-3 acceptance
# screen, which the core keeps an entry point to - so wait out the level
# load the boot does first, then jump into it.
for _ in range(200):
    c.run_frames(2)
    if c.peek(sym["LEVEL_OK"]):
        break
c.run_frames(6)
c.poke(sym["DEMO_TIMER"], 0xFF)
c.poke(sym["DEMO_TIMER"] + 1, 0xFF)
c.set_pc(sym["INTRO_SCREEN"])
c.run_frames(30)
# ... and stop between frames before sampling. The screen below is
# painted once, on the way in, and reading it while that is still
# happening loses whichever blocks had not been drawn yet.
lo, hi = sym["WAIT_VSYNC"], sym["WAIT_VSYNC.WAIT"] + 6
for _ in range(40000):
    c.run_us(4)
    if lo <= c.pc <= hi:
        break

print("boot:")
check("screen mode is 0", c.mode == 0, f"mode={c.mode}")
c.screenshot(os.path.join(SHOTS, "module1.png"), aspect=True)

# --- colour bars: line 20, bar N occupies bytes N*5 .. N*5+4 ---
scr = c.decode_screen_ram()          # list of rows of pen indices
row = scr[20]
bars = [row[bar * 10 + 2] for bar in range(16)]   # 5 bytes = 10 pixels per bar
check("colour bars read back as pens 0-15", bars == list(range(16)), str(bars))

# --- bank result blocks: line 44, block i at byte 4+i*14, 10 bytes wide ---
row = scr[44]
PEN_GREEN, PEN_RED = 7, 3
names = ["&C0", "C4", "C5", "C6", "C7"]
for i, nm in enumerate(names):
    pen = row[(4 + i * 14) * 2 + 4]
    check(f"bank {nm} marker survived", pen == PEN_GREEN,
          f"pen={pen} ({'green' if pen == PEN_GREEN else 'red' if pen == PEN_RED else '?'})")

# --- interrupt liveness lamp: line 60, byte 16..23 ---
# IT FLASHES, so a single sample tests the phase the machine happens to
# be in and not whether the handler runs. Watch it for a while instead:
# the boot no longer passes through this screen, so which frame the test
# arrives on is not something it can count on.
pens = set()
for _ in range(40):
    pens.add(c.decode_screen_ram()[60][16 * 2 + 4])
    c.run_frames(1)
check("IM 1 handler is firing", PEN_GREEN in pens,
      f"pens seen over 40 frames: {sorted(pens)}")

# --- heartbeat toggles across 25 frames ---
def beat():
    return c.decode_screen_ram()[60][4 * 2 + 4]
b0 = beat()
c.run_frames(26)
b1 = beat()
check("heartbeat toggles", b0 != b1, f"{b0} -> {b1}")
c.screenshot(os.path.join(SHOTS, "module1_beat.png"), aspect=True)

print("\n" + ("ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILED: {fails}"))
sys.exit(1 if fails else 0)
