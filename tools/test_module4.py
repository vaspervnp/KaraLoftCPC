#!/usr/bin/env python3
"""Module 4 acceptance test: CRTC hardware scrolling over a banked tilemap.

Two comparisons, and the second one is the point.

The first reconstructs the whole playfield from the game's own state --
the map and tile sheet as they sit in bank C4, plus SCROLL, WORLD_X and
WORLD_CR -- and checks all 15,360 bytes against what the Z80 wrote into
video RAM. Address arithmetic that ignores the 1024-word wrap, a tile
lookup off by a row, a scroll step that moves the CRTC without moving
the map cursor: none of those survive it.

The second repeats it against the RENDERED FRAMEBUFFER, which is a
different claim. RAM being right only says the engine eventually wrote
the correct bytes. The framebuffer says the beam found them already
there. That is what tests the ordering in tilemap.asm -- apply before
painting on one axis, after it on the other -- and the failure it
catches is a 4-pixel column of the wrong tile down one edge, which
leaves video RAM perfectly correct.
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
FB_X0 = 64                      # first displayed column; 1 Mode 0 pixel = 4
T_PER_LINE = 256
FRAME_T = 79872

SCR_CHARS = 40
SCR_CHAR_ROWS = 24
SCR_LINES = SCR_CHAR_ROWS * 8
MAP_W, MAP_H = 64, 16
SCREEN_WIDTH_BYTES = 80
SPR_WIDTH, SPR_HEIGHT, SPR_FRAME_SIZE = 8, 48, 768
TILE_BYTES = 128
TILES_LEN = 16 * TILE_BYTES
BLOB_LEN = TILES_LEN + MAP_W * MAP_H

fails = []
def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def symbols():
    out = {}
    for line in open(os.path.join(ROOT, "build", "game.sym")):
        m = re.match(r"^(\S+) #([0-9A-F]+) ", line)
        if m:
            out[m.group(1)] = int(m.group(2), 16)
    return out


def in_vsync(machine, sym):
    return sym["WAIT_VSYNC"] <= machine.pc <= sym["WAIT_VSYNC.WAIT"] + 6


def settle(machine, sym):
    """Advance to a frame with no vertical step in flight.

    A vertical step paints its incoming row in two halves on consecutive
    frames and only then latches the new start address, so between the
    two SCROLL has moved but the picture has not. That is the design -
    the row is hidden until it is whole - but it means SCROLL and the
    screen only agree while V_PHASE is clear.
    """
    for _ in range(40):
        sync_to_frame_top(machine, sym)
        if machine.peek(sym["V_PHASE"]) == 0:
            return True
        next_frame_top(machine, sym)
    return False


def sync_to_frame_top(machine, sym):
    """Stop between frames, in the WAIT_VSYNC spin."""
    for _ in range(40000):
        machine.run_us(4)
        if in_vsync(machine, sym):
            return True
    return False


def next_frame_top(machine, sym):
    """Run exactly one iteration of the demo loop and stop between frames.

    It watches the demo's own frame counter rather than the PC leaving
    WAIT_VSYNC. The 300 Hz interrupt pulls the PC out of that spin six
    times a frame, so "not in the spin any more" means "an interrupt
    fired", and an earlier version of this advanced a quarter of a frame
    per call.
    """
    start = machine.peek(sym["FRAME_COUNT"])
    for _ in range(40000):
        machine.run_us(4)
        if machine.peek(sym["FRAME_COUNT"]) != start:
            break
    return sync_to_frame_top(machine, sym)


def sync_to_vsync(machine, sym):
    """Stop in the instant after VSYNC, before the frame's step runs.

    The emulator's framebuffer is a live raster buffer, not a finished
    frame. Sample it while the beam is halfway down and the top of the
    capture is the new sweep while the bottom is still the old one --
    which looks exactly like tearing and is not. Just after VSYNC the
    whole display area belongs to one sweep, and the next one has 72
    scanlines of border to cross before it touches anything.
    """
    lo = sym["SCROLL_DEMO.LOOP"] + 3        # past "call WAIT_VSYNC"
    start = machine.peek(sym["FRAME_COUNT"])
    for _ in range(40000):                  # coarse: to the end of this step
        machine.run_us(8)
        if machine.peek(sym["FRAME_COUNT"]) != start:
            break
    for _ in range(30000):                  # fine: the window is ~1 us wide
        machine.run_us(1)
        if lo <= machine.pc <= lo + 8:
            return True
    return False


def state(machine, sym):
    scroll = machine.peek(sym["SCROLL"]) | (machine.peek(sym["SCROLL"] + 1) << 8)
    return (scroll, machine.peek(sym["WORLD_X"]), machine.peek(sym["WORLD_CR"]),
            machine.peek(sym["KARA_X"]), machine.peek(sym["KARA_Y"]),
            machine.peek(sym["KARA_FRAME"]))


def overlay_kara(want, sprites, scroll, kara_x, kara_y, frame):
    """Composite Kara over the tilemap, in the blitter's own address model.

        v    = (2*SCROLL + 80*char_row + byte_column) AND &07FF
        addr = &C000 + ((line AND 7) << 11) + v

    Same formula the Z80 uses, so a sprite drawn with the Module 3 flat
    model (or one that mishandles the 2047 seam) will not match.
    """
    base = frame * SPR_FRAME_SIZE
    cr, raster = divmod(kara_y, 8)
    v = (2 * scroll + 80 * (cr & 0x1F) + kara_x) & 0x7FF
    for line in range(SPR_HEIGHT):
        for b in range(SPR_WIDTH):
            addr = 0xC000 + (raster << 11) + ((v + b) & 0x7FF)
            mask = sprites[base + line * 16 + b * 2]
            data = sprites[base + line * 16 + b * 2 + 1]
            if addr in want:
                want[addr] = (want[addr] & mask) | data
        raster += 1
        if raster == 8:
            raster = 0
            v = (v + 80) & 0x7FF
    return want


def expected_screen(tiles, level_map, scroll, world_x, world_cr):
    """Every byte the playfield should hold, as {vram address: value}.

    The address model from CLAUDE.md 6.4 written out in full: MA masked
    to 10 bits, raster in bits 11-13, word times two.
    """
    want = {}
    for cr in range(SCR_CHAR_ROWS):
        wr = (world_cr + cr) & 0xFF
        map_row = (wr >> 1) & (MAP_H - 1)
        line_off = (wr & 1) * 64
        for x in range(SCR_CHARS):
            wc = (world_x + x) & 0xFF
            tile = level_map[map_row * MAP_W + ((wc >> 2) & (MAP_W - 1))]
            src = tile * TILE_BYTES + line_off + (wc & 3) * 2
            word = (scroll + cr * SCR_CHARS + x) & 0x3FF
            for raster in range(8):
                addr = 0xC000 + (raster << 11) + word * 2
                want[addr] = tiles[src + raster * 8]
                want[addr + 1] = tiles[src + raster * 8 + 1]
    return want


def expected_pens(want, scroll):
    """A 192 x 160 grid of pen numbers, read back out of the byte model.

    Derived from `want` rather than from the tiles directly, so whatever
    is composited into it - Kara included - is carried through.
    """
    rows = []
    for line in range(SCR_LINES):
        cr, raster = divmod(line, 8)
        v = (2 * scroll + 80 * cr) & 0x7FF
        row = []
        for x in range(SCREEN_WIDTH_BYTES):
            row.extend(cpclib.decode_byte(want[0xC000 + (raster << 11) + ((v + x) & 0x7FF)]))
        rows.append(row)
    return rows


def model(tiles, level_map, sprites, st, with_kara):
    """Expected video RAM for one sampled state.

    Two models, deliberately. The loop draws Kara and then erases her
    again in the same frame - ahead of the raster, then behind it - so
    at the VSYNC sample point video RAM holds pure tilemap and no Kara,
    while the frame the beam actually painted holds her. Comparing RAM
    against the Kara-free model and the framebuffer against the Kara
    model tests both halves of that arrangement.
    """
    scroll, wx, wcr, kx, ky, kf = st
    want = expected_screen(tiles, level_map, scroll, wx, wcr)
    return overlay_kara(want, sprites, scroll, kx, ky, kf) if with_kara else want


def step_deltas(machine, sym, frames):
    """Signed (scroll, world_x, world_cr) change for each frame that moved.

    Watching frame by frame is the only honest way to size a step: the
    demo's vertical phases only move every 4th frame, and poking its
    counters to force the cadence just races whatever it was doing.
    """
    out = []
    prev = state(machine, sym)[:3]
    for _ in range(frames):
        next_frame_top(machine, sym)
        cur = state(machine, sym)[:3]
        d = tuple(((c - p) & m) - (m + 1 if ((c - p) & m) > m // 2 else 0)
                  for c, p, m in zip(cur, prev, (0x3FF, 0xFF, 0xFF)))
        if any(d):
            out.append(d)
        prev = cur
    return out


def render_mismatch(machine, pen_rows, pen_to_hw, y0):
    fb = machine.framebuffer()
    bad = 0
    for y, row in enumerate(pen_rows):
        base = (y0 + y) * FB_W + FB_X0
        for x, pen in enumerate(row):
            if fb[base + x * 4] != pen_to_hw[pen]:
                bad += 1
    return bad


def find_display_top(machine, candidates, pen_to_hw):
    """Search for the first displayed scanline instead of assuming it.

    R6 = 24 shortens the picture, so the offset is not the one the other
    suites use. Searching for it means a wrong guess shows up as a poor
    score rather than as a silent pass.
    """
    fb = machine.framebuffer()
    best, best_hit = 0, -1
    for pen_rows in candidates:
        for y0 in range(0, 140):
            hit = 0
            for y in range(0, 24, 3):
                base = (y0 + y) * FB_W + FB_X0
                for x in range(0, 160, 5):
                    if fb[base + x * 4] == pen_to_hw[pen_rows[y][x]]:
                        hit += 1
            if hit > best_hit:
                best, best_hit = y0, hit
    return best, best_hit, 8 * 32


def read_bank(machine, sym):
    """Copy bank C4's first 3K out through the window and read it back.

    run_code() only sets PC -- it does not save one -- so the blob ends
    in a spin rather than a RET and the caller's PC is put back by hand.

    It goes back to the TOP of WAIT_VSYNC, not to the address that was
    interrupted. The spin is "in a,(c)" with BC preloaded by the
    instruction above it, and the blob leaves BC pointing at the gate
    array; resuming mid-spin polls the wrong chip and hangs forever.
    """
    machine.run_code(0x8000, bytes([
        0x01, 0xC4, 0x7F, 0xED, 0x49,           # ld bc,&7FC4 : out (c),c
        0x21, 0x00, 0x40, 0x11, 0x00, 0xA0,     # ld hl,&4000 : ld de,&A000
        0x01, 0x00, 0x0C, 0xED, 0xB0,           # ld bc,3072  : ldir
        0x01, 0xC0, 0x7F, 0xED, 0x49,           # ld bc,&7FC0 : out (c),c
        0x18, 0xFE]))                           # jr $
    out = machine.read_ram(0xA000, BLOB_LEN)
    machine.set_pc(sym["WAIT_VSYNC"])
    return out


def main():
    sym = symbols()
    machine = CPC()
    machine.run_frames(150)
    machine.insert_disc(os.path.abspath(os.path.join(ROOT, "build", "kara.dsk")))
    machine.type_text('RUN"DISC\n')
    machine.run_frames(400)
    check("Module 1-3 screen is running", machine.mode == 0, f"mode={machine.mode}")

    # Cut the Module 1-3 phase short rather than waiting out DEMO_TIMER,
    # then give DRAW_PLAYFIELD its ~18 frames to paint all 40 columns.
    machine.poke(sym["DEMO_TIMER"], 2)
    machine.poke(sym["DEMO_TIMER"] + 1, 0)
    machine.run_frames(30)
    check("handed over to the scrolling demo",
          state(machine, sym)[0] > 0, f"scroll={state(machine, sym)[0]}")

    sprites = machine.read_ram(sym["KARA_SPRITES"], 4 * SPR_FRAME_SIZE)
    tiles = machine.read_ram(sym["CITY_TILES"], TILES_LEN)
    level_map = machine.read_ram(sym["CITY_MAP"], MAP_W * MAP_H)
    check("level blob is intact in base RAM",
          len(set(level_map)) > 1 and max(level_map) < 16,
          f"{len(set(level_map))} distinct tiles, max index {max(level_map)}")

    pal = machine.read_ram(sym["PALETTE_DATA"], 16)
    pen_to_hw = [b & 0x1F for b in pal]

    # ---------------------------------------------------------------
    # frame cost, measured before any run_us stepping skews the bands
    # ---------------------------------------------------------------
    machine.run_frames(2)
    fb = machine.framebuffer()
    work = sum(1 for y in range(272) if fb[y * FB_W + 5] == 12)
    print(f"\n  horizontal step: {work} scanlines = {work * T_PER_LINE} T "
          f"= {100 * work * T_PER_LINE / FRAME_T:.1f}% of a frame")
    check("a scroll step fits in a frame", 0 < work * T_PER_LINE < FRAME_T,
          f"{work * T_PER_LINE} of {FRAME_T} T")

    check("test can sync to the top of a frame", sync_to_frame_top(machine, sym))
    check("tiles and map reached bank C4",
          bytes(read_bank(machine, sym)) == bytes(tiles) + bytes(level_map),
          "3072 bytes compared")

    # ---------------------------------------------------------------
    # 1. video RAM vs the map, across all three scroll phases
    # ---------------------------------------------------------------
    print("\n  video RAM vs map, Kara already erased (15,360 bytes per sample):")
    scrolls, worst = [], 0
    for label, advance in [("horizontal", 0), ("horizontal", 90),
                           ("vertical down", 130), ("vertical down", 90),
                           ("vertical up", 100), ("vertical up", 90)]:
        if advance:
            machine.run_frames(advance)
        settle(machine, sym)
        st = state(machine, sym)
        scroll, wx, wcr = st[0], st[1], st[2]
        scrolls.append(scroll)
        want = model(tiles, level_map, sprites, st, with_kara=False)
        vram = machine.read_ram(0xC000, 0x4000)
        bad = sum(1 for a, v in want.items() if vram[a - 0xC000] != v)
        worst = max(worst, bad)
        raw = machine.crtc_screen_addr
        ok_crtc = raw == (0x3000 | scroll)
        print(f"    {label:<14} scroll={scroll:>4} world=({wx:>3},{wcr:>3}) "
              f"kara=({st[3]:>2},{st[4]:>3},f{st[5]})  "
              f"{bad:>5} wrong  CRTC=&{raw:04X} {'ok' if ok_crtc else 'MISMATCH'}")
        if not ok_crtc:
            fails.append(f"CRTC start address at scroll {scroll}")

    check("playfield always matches the map", worst == 0, f"worst sample: {worst} bytes")
    check("scrolling crossed the 1024-word wrap",
          max(scrolls) + SCR_CHARS * SCR_CHAR_ROWS > 1024,
          f"max scroll {max(scrolls)} + 960 words")

    # ---------------------------------------------------------------
    # 2. step sizes
    # ---------------------------------------------------------------
    print("\n  step sizes:")
    for phase, name, frames, want, n in [
            (0, "horizontal",    6,  (1, 1, 0),    6),
            (1, "vertical down", 12, (40, 0, 1),   3),
            (2, "vertical up",   12, (-40, 0, -1), 3)]:
        machine.poke(sym["DEMO_PHASE"], phase)
        machine.poke(sym["DEMO_PHASE_T"], 0)
        sync_to_frame_top(machine, sym)
        deltas = step_deltas(machine, sym, frames)
        uniform = deltas and all(d == want for d in deltas)
        check(f"{name} step", uniform and len(deltas) == n,
              f"{len(deltas)} steps in {frames} frames, "
              + (f"each {deltas[0]}" if uniform else f"deltas {sorted(set(deltas))}"))

    # ---------------------------------------------------------------
    # 3. what the beam actually displayed
    #
    # The completed frame lags the scroll state by an iteration, and by
    # how much depends on the axis: horizontal and downward steps latch
    # the new start address at the top of their own frame, an upward one
    # latches it at the end. Rather than model that, the check asks for
    # something stronger and simpler - the frame must be pixel-exact for
    # ONE consistent view. A torn frame is a mix of two and matches
    # neither.
    # ---------------------------------------------------------------
    print("\n  rendered frame vs map (30,720 pixels per sample):")
    machine.poke(sym["DEMO_PHASE"], 0)
    machine.poke(sym["DEMO_PHASE_T"], 0)
    check("test can sync to the instant after VSYNC", sync_to_vsync(machine, sym))
    settle(machine, sym)
    st = state(machine, sym)
    y0, hits, probes = find_display_top(
        machine, [expected_pens(model(tiles, level_map, sprites, st, True), st[0])],
        pen_to_hw)
    check("found the displayed area in the framebuffer", hits >= probes * 0.9,
          f"top scanline {y0}, {hits} of {probes} probes matched")

    for phase, name in [(0, "horizontal"), (1, "vertical down"), (2, "vertical up")]:
        machine.poke(sym["DEMO_PHASE"], phase)
        machine.poke(sym["DEMO_PHASE_T"], 0)
        history = []
        for _ in range(6):
            sync_to_vsync(machine, sym)
            if machine.peek(sym["V_PHASE"]) == 0:
                history.append(state(machine, sym))
        scores = [(render_mismatch(machine,
                                   expected_pens(model(tiles, level_map, sprites, h, True), h[0]),
                                   pen_to_hw, y0), h)
                  for h in history[-3:]]
        bad, st = min(scores)
        print(f"    {name:<14} scroll={st[0]:>4} world=({st[1]:>3},{st[2]:>3}) "
              f"kara=({st[3]:>2},{st[4]:>3},f{st[5]})  "
              f"{bad:>6} wrong pixels  (best of {len(scores)} candidate views)")
        check(f"{name} scrolling is tear-free on screen", bad == 0, f"{bad} pixels")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(fails))
        return 1
    print("Module 4 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
