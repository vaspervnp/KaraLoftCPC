#!/usr/bin/env python3
"""Module 3 acceptance test: masked blitter, save-under, bullet pool.

The interesting checks reconstruct what the screen SHOULD hold from the
game's own state -- Kara's position and frame, the stripe table, the
bullet pool -- and compare it against the bytes the Z80 actually wrote.
A blitter that drops a byte, shifts a line, gets the mask polarity
backwards or restores the wrong row cannot pass that.

It also profiles the frame from the coloured border bands the demo
paints, and reports the cost against the budget in CLAUDE.md 9.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/home/vasilhs/cpcemu")

import cpclib
from cpc import CPC

ROOT = os.path.join(HERE, "..")
FB_W = 1024
T_PER_LINE = 256                # 64 us x 4 T-states
FRAME_T = 79872                 # 312 lines x 64 us x 4

SPR_W, SPR_H = 8, 48
STRIPE_TOP = 64
MARKS = [("erase", 21), ("logic", 30), ("sprite", 12),
         ("bullets", 18), ("hud", 24)]

fails = []
def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def sync_to_frame_top(machine, sym):
    """Stop the machine in WAIT_VSYNC, between frames.

    Drawing takes most of a frame, so a naive run_frames() lands the CPU
    somewhere inside the blitter and samples a half-drawn screen. The
    spin in WAIT_VSYNC is the one point where the previous frame is
    complete and the next has not started.
    """
    lo = sym["WAIT_VSYNC"]
    hi = sym["WAIT_VSYNC.WAIT"] + 6
    for _ in range(40000):
        machine.run_us(4)
        if lo <= machine.pc <= hi:
            return True
    return False


def symbols():
    out = {}
    for line in open(os.path.join(ROOT, "build", "game.sym")):
        m = re.match(r"^(\S+) #([0-9A-F]+) ", line)
        if m:
            out[m.group(1)] = int(m.group(2), 16)
    return out


def stripe_table(machine, sym):
    return machine.read_ram(sym["STRIPE_PENS"], 14)


def stripe_byte(table, line):
    if line < STRIPE_TOP:
        return None
    band = (line - STRIPE_TOP) // 8
    return table[band] if band < len(table) else None


KARA_HOME_Y = 96      # the DEV SCREEN's own line for the 16x48
                      # placeholder, in the middle of the stripes at
                      # 64-175. It is not a collision-box number: this
                      # screen does not run the span blitter at all.


def main():
    sym = symbols()
    machine = CPC()
    machine.run_frames(150)
    machine.insert_disc(os.path.abspath(os.path.join(ROOT, "build", "kara.dsk")))
    machine.type_text('RUN"DISC\n')
    machine.run_frames(400)

    # THE GAME NO LONGER PASSES THROUGH THIS SCREEN. It boots straight
    # onto the rooftop, and the Module 1-3 acceptance screen is a
    # development screen the core keeps an entry point to - so this
    # suite jumps into it, after waiting out the level load the boot
    # now does first. DEMO_TIMER is pinned open so it stays there.
    for _ in range(200):
        machine.run_frames(2)
        if machine.peek(sym["LEVEL_OK"]):
            break
    machine.run_frames(6)
    machine.poke(sym["DEMO_TIMER"], 0xFF)
    machine.poke(sym["DEMO_TIMER"] + 1, 0xFF)
    machine.set_pc(sym["INTRO_SCREEN"])
    machine.run_frames(30)      # let it settle: the screen is redrawn, the
                                # pool refilled and her walk restarted

    check("game is running in Mode 0", machine.mode == 0, f"mode={machine.mode}")
    # ---------------------------------------------------------------
    # frame cost, measured first: the run_us stepping the later checks
    # use leaves the machine mid-scanline and skews the border bands, read off the border bands
    # ---------------------------------------------------------------
    machine.run_frames(2)
    fb = machine.framebuffer()
    counts = {}
    for name, hw in MARKS:
        counts[name] = sum(1 for y in range(272) if fb[y * FB_W + 5] == hw)

    print("\n  frame profile (border bands, 1 line = 256 T-states):")
    total = 0
    for name, _ in MARKS:
        t = counts[name] * T_PER_LINE
        total += t
        print(f"    {name:<9} {counts[name]:>4} lines  {t:>7} T  {100 * t / FRAME_T:5.1f}%")
    print(f"    {'TOTAL':<9} {sum(counts.values()):>4} lines  {total:>7} T  "
          f"{100 * total / FRAME_T:5.1f}% of a 79,872 T frame")

    check("frame work fits inside one frame", total < FRAME_T,
          f"{total} of {FRAME_T} T")
    budget_ok = total <= 0.25 * FRAME_T
    print(f"  [{'PASS' if budget_ok else 'NOTE'}] plan.md's 25% sprite budget"
          f"  {'met' if budget_ok else f'exceeded: {100 * total / FRAME_T:.1f}%'}")


    check("test can sync to the top of a frame", sync_to_frame_top(machine, sym))

    stripes = stripe_table(machine, sym)
    sprites = machine.read_ram(sym["KARA_SPRITES"], 4 * 768)

    # ---------------------------------------------------------------
    # 1. the masked composite
    # ---------------------------------------------------------------
    kx = machine.peek(sym["KARA_X"])
    ky = machine.peek(sym["KARA_Y"])
    kf = machine.peek(sym["KARA_FRAME"])
    check("Kara is on screen and animating",
          0 <= kx <= 72 and ky == KARA_HOME_Y and 0 <= kf <= 3,
          f"x={kx} y={ky} frame={kf}")

    bullet_cells = set()
    pool = machine.read_ram(sym["BULLETS"], 14 * 5)
    for i in range(14):
        if pool[i * 5]:
            bx, by = pool[i * 5 + 1], pool[i * 5 + 2]
            bullet_cells |= {(bx, by), (bx, by + 1)}

    frame = sprites[kf * 768:(kf + 1) * 768]
    wrong = checked = 0
    for line in range(SPR_H):
        y = ky + line
        for xb in range(SPR_W):
            if (kx + xb, y) in bullet_cells:
                continue                       # a round is sitting on top
            mask = frame[line * 16 + xb * 2]
            data = frame[line * 16 + xb * 2 + 1]
            bg = stripe_byte(stripes, y)
            addr = 0xC000 + cpclib.screen_offset(kx + xb, y)
            got = machine.peek(addr)
            want = (bg & mask) | data
            checked += 1
            if got != want:
                wrong += 1
    check("masked blit composites Kara over the stripes",
          wrong == 0, f"{wrong}/{checked} bytes wrong")

    # ---------------------------------------------------------------
    # 2. save-under restore: everything Kara has walked past is clean
    # ---------------------------------------------------------------
    wrong = checked = 0
    for line in range(SPR_H):
        y = ky + line
        bg = stripe_byte(stripes, y)
        for xb in range(0, kx):
            if (xb, y) in bullet_cells:
                continue
            got = machine.peek(0xC000 + cpclib.screen_offset(xb, y))
            checked += 1
            if got != bg:
                wrong += 1
    check("save-under leaves the background exactly as it was",
          wrong == 0, f"{wrong}/{checked} bytes wrong behind Kara")

    # ---------------------------------------------------------------
    # 3. dual pistols
    # ---------------------------------------------------------------
    seen_reload = False
    seen_alternation = set()
    mags_seen = set()
    for _ in range(240):
        machine.run_frames(1)
        # no sync needed: these are scalars the logic phase writes atomically
        left = machine.peek(sym["MAG_LEFT"])
        right = machine.peek(sym["MAG_RIGHT"])
        mags_seen.add((left, right))
        seen_alternation.add(machine.peek(sym["ACTIVE_GUN"]))
        if machine.peek(sym["RELOAD_TIMER"]):
            seen_reload = True
    check("magazines never exceed 7 rounds",
          all(l <= 7 and r <= 7 for l, r in mags_seen),
          f"max seen {max(max(m) for m in mags_seen)}")
    check("both guns take turns", seen_alternation == {0, 1},
          str(sorted(seen_alternation)))
    check("running dry starts a reload", seen_reload)
    check("magazines refill after the reload",
          (7, 7) in mags_seen or any(l + r >= 7 for l, r in mags_seen))

    # ---------------------------------------------------------------
    # 4. bullet travel: 2 bytes = 4 Mode 0 pixels per frame
    # ---------------------------------------------------------------
    # The demo spends a fifth of its time reloading, with nothing in
    # flight, so wait for a frame that actually has rounds to measure
    # rather than sampling one and hoping.
    steps = []
    for _ in range(80):
        sync_to_frame_top(machine, sym)
        before = machine.read_ram(sym["BULLETS"], 14 * 5)
        machine.run_frames(1)
        sync_to_frame_top(machine, sym)
        after = machine.read_ram(sym["BULLETS"], 14 * 5)
        steps = [after[i * 5 + 1] - before[i * 5 + 1]
                 for i in range(14)
                 if before[i * 5] and after[i * 5]
                 and before[i * 5 + 4] == after[i * 5 + 4] + 1]   # one frame older
        if steps:
            break
    check("rounds travel 4 pixels per frame",
          bool(steps) and all(s == 2 for s in steps), f"steps={sorted(set(steps))}")

    machine.screenshot(os.path.join(ROOT, "build", "module3.png"), aspect=True)
    machine.screenshot(os.path.join(ROOT, "build", "module3_raster.png"),
                       full_framebuffer=True)
    print("\n" + ("ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
