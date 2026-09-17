#!/usr/bin/env python3
"""The energy bar: is it drawn, does it track her health, does it STAY.

THE PROPERTY THAT MATTERS IS THE LAST ONE. On a hardware-scrolled
display the address a thing lives at is the one the CRTC is about to
show somewhere else, so anything screen-fixed has to be rewritten every
time the start address changes (CLAUDE.md 7.8). A bar that is merely
drawn once looks right for one frame and then slides off with the
world - so it is checked ON THE SCREEN, in the emulator's framebuffer,
on every frame of a walk that scrolls, and the negative control is the
engine with the redraw taken out.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/home/vasilhs/cpcemu")

import cpclib                                                   # noqa: E402
from bench import Bench, boot, symbols, sync                    # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BUILD = os.path.join(ROOT, "build")
FBW = 1024
JOY_RIGHT, JOY_LEFT = 0x08, 0x04
CELLS, LINES, CELL_W = 6, 8, 2           # bytes across a cell
ROW = 23                                 # THE BOTTOM character row
BASE = ROW * 40                          # ... 920 words into the view
TOP_LINE = ROW * 8                       # display line 184

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    if not ok:
        fails.append(name)


def cells_from_inc():
    """The two 4x8 cells the build exported, as pen rows."""
    text = open(os.path.join(BUILD, "hud_art.inc")).read()
    out = {}
    for name in ("HUD_CELL_FULL", "HUD_CELL_EMPTY"):
        body = text.split(name + ":")[1].splitlines()[1:]
        rows = []
        for line in body[:LINES]:
            vals = [int(v.strip()[1:], 16) for v in line.strip()[3:].split(",")]
            row = []
            for v in vals:
                row += list(cpclib.decode_byte(v))
            rows.append(row)
        out[name] = rows
    return out


def lit_cells(hp, steps):
    return sum(1 for s in steps if hp >= s)


def expect(hp, art, steps):
    """The 24x8 pen grid the bar should be showing for this health."""
    n = lit_cells(hp, steps)
    grid = []
    for y in range(LINES):
        row = []
        for c in range(CELLS):
            row += art["HUD_CELL_FULL" if c < n else "HUD_CELL_EMPTY"][y]
        grid.append(row)
    return grid


def find_top(m, sym, want, hwpen):
    """Which framebuffer row the display starts on, from the bar itself."""
    fb = m.framebuffer()

    def score(t):
        n = 0
        for y in range(LINES):
            row = fb[(t + TOP_LINE + y) * FBW:(t + TOP_LINE + y + 1) * FBW]
            n += sum(1 for x in range(CELLS * 4)
                     if row[64 + x * 4] == hwpen[want[y][x]])
        return n
    return max(range(0, 312 - TOP_LINE - LINES), key=score)


def on_screen(m, top, want, hwpen):
    """How many of the bar's 192 pixels are wrong in the rendered frame."""
    fb = m.framebuffer()
    bad = 0
    for y in range(LINES):
        row = fb[(top + TOP_LINE + y) * FBW:(top + TOP_LINE + y + 1) * FBW]
        for x in range(CELLS * 4):
            if row[64 + x * 4] != hwpen[want[y][x]]:
                bad += 1
    return bad


def main():
    sym = symbols()
    for n in ("HUD_SERVICE", "HUD_ALL", "HUD_PUT", "HUD_LEVEL", "HUD_HP",
              "HUD_LAST", "HUD_LIT", "HUD_STEPS", "HUD_CELL_FULL",
              "HUD_CELL_EMPTY"):
        if n not in sym:
            check(f"the engine has {n}", False, "rebuild first")
    if fails:
        print(f"\nFAILED: {len(fails)} check(s)")
        return 1

    art = cells_from_inc()
    m = boot(sym, scroll=True)
    m.run_frames(20)
    steps = list(m.read_ram(sym["HUD_STEPS"], CELLS))
    hwpen = [v & 0x1F for v in m.read_ram(sym["PALETTE_DATA"], 16)]
    print(f"\n  six cells of the artist's hud_bars, lit at HP {steps}:")

    hp = m.peek(sym["PLAYER_HP"])
    want = expect(hp, art, steps)
    sync(m, sym)
    top = find_top(m, sym, want, hwpen)
    bad = on_screen(m, top, want, hwpen)
    check("the bar is on the screen, bottom left, at full health", bad == 0,
          f"{CELLS * 4 * LINES - bad} of {CELLS * 4 * LINES} pixels are the "
          f"artist's own cells, with the display at framebuffer row {top}")

    print("\n  and it follows her health:")
    for hp in (100, 84, 50, 17, 1, 0):
        m.poke(sym["PLAYER_HP"], hp)
        m.run_frames(3)
        sync(m, sym)
        want = expect(hp, art, steps)
        bad = on_screen(m, top, want, hwpen)
        check(f"HP {hp:3d} lights {lit_cells(hp, steps)} of {CELLS}", bad == 0,
              f"{bad} wrong pixels" if bad else "exactly, on the screen")
    m.poke(sym["PLAYER_HP"], 100)
    m.run_frames(3)

    print("\n  and it STAYS, which is the whole difficulty:")
    want = expect(100, art, steps)
    worst, steps_seen = 0, set()
    scroll0 = m.peek(sym["SCROLL"]) | (m.peek(sym["SCROLL"] + 1) << 8)
    m.joystick(JOY_RIGHT)
    for _ in range(90):
        m.run_frames(1)
        sync(m, sym)
        steps_seen.add(m.peek(sym["SCROLL"]) | (m.peek(sym["SCROLL"] + 1) << 8))
        worst = max(worst, on_screen(m, top, want, hwpen))
    m.joystick(0)
    check("the view really did scroll under it", len(steps_seen) > 20,
          f"{len(steps_seen)} distinct start addresses over 90 frames, from "
          f"{scroll0} - without that the check below is vacuous")
    check("... and the bar never moved with it, walking RIGHT", worst == 0,
          f"worst frame of the 90 had {worst} wrong pixels of "
          f"{CELLS * 4 * LINES}")

    # LEFT AND UP ARE THE DIRECTIONS THAT LEAVE SOMETHING BEHIND, and
    # they are the ones a right-hand walk would never have shown: the
    # new draw covers five of the bar's six old words and the sixth is
    # off the screen going right and ON it going left (src/hud.asm).
    worst, steps_seen = 0, set()
    m.joystick(JOY_LEFT)
    for _ in range(90):
        m.run_frames(1)
        sync(m, sym)
        steps_seen.add(m.peek(sym["SCROLL"]) | (m.peek(sym["SCROLL"] + 1) << 8))
        worst = max(worst, on_screen(m, top, want, hwpen))
    m.joystick(0)
    check("... and walking LEFT, which leaves a cell behind", worst == 0,
          f"{len(steps_seen)} start addresses, worst frame {worst} wrong "
          f"pixels - the vacated cell comes back from the tilemap")

    # ... and UP, where the whole bar vacates a visible row. She starts
    # ON the first ladder (world x 43, LADDER_X[0] is bytes 44-47), so
    # DOWN climbs her off the roof and the camera follows her down,
    # which walks the start address 40 words at a time.
    worst, rows = 0, set()
    m5 = boot(sym, scroll=True)             # a fresh one: the walk above
    m5.run_frames(20)                       # has carried her off the ladder
    m5.joystick(0x02)                       # DOWN
    for _ in range(240):
        m5.run_frames(1)
        sync(m5, sym)
        rows.add(m5.peek(sym["WORLD_CR"]))
        worst = max(worst, on_screen(m5, top, want, hwpen))
    m5.joystick(0)
    check("the view scrolled VERTICALLY under it too", len(rows) > 4,
          f"{len(rows)} character rows of view travelled while she climbed")
    check("... and the bar stayed where it was", worst == 0,
          f"worst frame of the 200 had {worst} wrong pixels - a vertical "
          f"step vacates all six cells, one row down")

    print("\n  the negative control - take the redraw out:")
    m2 = boot(sym, scroll=True)
    m2.run_frames(20)
    m2.poke(sym["HUD_SERVICE"], 0xC9)       # RET: drawn once and left there
    m2.joystick(JOY_RIGHT)
    worst2 = 0
    for _ in range(90):
        m2.run_frames(1)
        sync(m2, sym)
        worst2 = max(worst2, on_screen(m2, top, want, hwpen))
    m2.joystick(0)
    check("without it the bar slides off with the world", worst2 > 0,
          f"{worst2} wrong pixels of {CELLS * 4 * LINES} - the same 90 frames "
          f"with HUD_SERVICE returning at once")

    print("\n  the six start positions in 1024 that cross the seam:")
    # The bar is six characters wide and the ring is 1024 words, so at
    # words 1019-1023 its last cells fold back to the top of their own
    # 2 KB block (CLAUDE.md 6.4). LEVEL 1 NEVER REACHES THEM - its
    # scroll is WORLD_X + 40 * WORLD_CR, at most 216 + 320 - so this is
    # driven, and driven as a UNIT: poking SCROLL and letting the game
    # run makes the camera fight the nonsense position, which is how
    # this check used to pass without ever reaching the fold.
    m3 = boot(sym, scroll=True)
    m3.run_frames(20)
    art_full = art["HUD_CELL_FULL"]
    stub, bad3 = 0xB000, []
    for w in (1018, 1019, 1020, 1021, 1022, 1023):
        m3.poke(sym["SCROLL"], w & 0xFF)
        m3.poke(sym["SCROLL"] + 1, w >> 8)
        a = sym["HUD_SERVICE"]
        m3.write_ram(stub, bytes([0xF3, 0xCD, a & 0xFF, a >> 8, 0x18, 0xFE]))
        m3.set_pc(stub)
        for _ in range(40000):
            m3.run_us(1)
            if m3.pc == stub + 4:
                break
        wrong = 0
        for c in range(CELLS):
            word = (w + BASE + c) & 0x3FF
            for line in range(LINES):
                addr = 0xC000 + (line << 11) + (word << 1)
                got = list(m3.read_ram(addr, 2))
                want2 = [cpclib.encode_pixels(art_full[line][0], art_full[line][1]),
                         cpclib.encode_pixels(art_full[line][2], art_full[line][3])]
                wrong += sum(1 for x, y in zip(got, want2) if x != y)
        bad3.append(wrong)
    check("the bar survives the fold, at every one of them", not any(bad3),
          f"words 1018-1023, wrong bytes {bad3} - 1018 is the last one that "
          f"does NOT fold, so it is the control on the other five")

    print("\n  and the frame still closes:")
    m4 = boot(sym, scroll=True)
    m4.run_frames(20)
    m4.poke(sym["ENEMY_LIVE"], 0)           # the encounter is test_module5's
    f0 = m4.peek(sym["FRAME_COUNT"])
    m4.joystick(JOY_RIGHT)
    for _ in range(200):
        m4.poke(sym["ENEMY_LIVE"], 0)
        m4.run_frames(1)
    m4.joystick(0)
    loops = (m4.peek(sym["FRAME_COUNT"]) - f0) % 256
    check("walking and scrolling with the bar on holds 50 Hz", loops >= 199,
          f"{loops} loop iterations in 200 hardware frames")

    print("\n  what it costs:")
    b = Bench(m, sym)
    cost = {}
    for name in ("HUD_ALL", "HUD_PUT", "HUD_LEVEL"):
        cost[name] = b.T(name)
        print(f"    {name:12s} {cost[name]} T")

    # AND WHAT IT COSTS WHEN THE PICTURE HAS NOT MOVED. Six cells over
    # 100 points is 16.67 apiece, so most hits change PLAYER_HP without
    # changing which cells are lit - and HUD_LEVEL says so with the Z
    # flag rather than laying the buffer out again for the same picture.
    # Driven from the machine, not asserted from the source: the poke
    # below is a health she has not got, so the count is recomputed
    # either way and only the layout is skipped.
    def hp(v):
        return lambda mm: mm.poke(sym["PLAYER_HP"], v)

    m.poke(sym["PLAYER_HP"], 100)
    m.run_frames(3)
    same = b.T("HUD_LEVEL", hp(99))          # still six cells lit
    moved = b.T("HUD_LEVEL", hp(40))         # ... and now two
    print(f"    {'HUD_LEVEL':12s} {same} T when the same cells stay lit, "
          f"{moved} T when they do not")
    check("a hit that does not cross a cell does not redraw the bar",
          same * 4 < moved,
          f"{same} T against {moved} - HP 99 lights the same six as 100, "
          f"HP 40 lights two")
    m.poke(sym["PLAYER_HP"], 100)
    m.run_frames(3)
    check("one character of pan writes two cells, not six",
          cost["HUD_PUT"] * 2 < cost["HUD_ALL"],
          f"{cost['HUD_PUT'] * 2} T against {cost['HUD_ALL']} for all six - "
          f"a pan moves the view every frame for about twenty of them")
    check("and the pan's own redraw fits the frame's headroom",
          cost["HUD_PUT"] * 2 < 3548,
          f"{cost['HUD_PUT'] * 2} T against the 3,548 a scrolling frame has "
          f"spare (CLAUDE.md 9)")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(fails))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
