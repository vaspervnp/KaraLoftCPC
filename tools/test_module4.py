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
    screen only agree while V_PHASE is clear. A horizontal step spans two
    frames the same way (H_HEAD then H_COMMIT / H_TAIL), so wait that out
    too, or a sample catches the incoming column with 18 of its 24 rows
    painted.
    """
    for _ in range(60):
        sync_to_frame_top(machine, sym)
        if (machine.peek(sym["V_PHASE"]) == 0
                and machine.peek(sym["H_PENDING"]) == 0
                and machine.peek(sym["H_TAIL_DUE"]) == 0):
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


VSTEP_STUB = 0x9200

def drive(machine, sym, phase):
    """Put the engine into one of the three scroll motions.

    The demo is player-driven now, so horizontal scrolling comes from
    holding the joystick and letting CAMERA_UPDATE follow Kara. The
    vertical engine has no in-game driver yet - levels 3 and 4 are
    Module 6 - so a step is started directly and the main loop's
    SCROLL_SERVICE / SCROLL_VBLANK carry it through.
    """
    if phase == 0:
        drive.want = 0
        machine.joystick(0x08)               # walk her to the camera's edge,
        machine.run_frames(20)               # so every later frame scrolls
        return
    machine.joystick(0)                      # the camera must not also step
    machine.poke(sym["V_REQUEST"], 0)        # while a vertical step is measured.
    drive.want = 1 if phase == 1 else 2      # And clear any request the last
                                             # phase left: the engine now defers
                                             # a vertical step while a
                                             # horizontal one is in flight, so a
                                             # request can outlive its phase and
                                             # fire as the wrong direction here.


def pump_h(machine, sym):
    """Hold the joystick right; CAMERA_DECIDE follows her.

    It used to poke KARA_WX by +2 a frame instead, to avoid depending on
    what is in front of her. That is no longer safe to do: two bytes a
    frame is the CAMERA's step, and inside the push zone the player code
    deliberately moves her in step with the camera so her SCREEN column
    never changes. Poking the world position drives her at a speed the
    camera cannot match, KARA_X alternates by one byte every frame, and
    the test then measures a fault it created itself. If she walks into
    a wall the camera stops and the test goes vacuous rather than failing,
    which is why the placeholder city now has one continuous rooftop -
    see tools/make_placeholder_level.py.
    """
    machine.joystick(0x08)


def vstep(machine, sym):
    """Ask the engine for a vertical step. No PC hijacking: SCROLL_SERVICE
    picks the request up on its own, exactly as levels 3 and 4 will."""
    if machine.peek(sym["V_PHASE"]):
        return False
    machine.poke(sym["V_REQUEST"], getattr(drive, "want", 1))
    return True


def state(machine, sym):
    """(scroll, world_x, world_cr, kara_x, kara_y, kara_frame, pending)

    pending is None, or (h_scroll, h_wx, h_col) when a horizontal step
    has been requested and its column head is already in video RAM.
    """
    scroll = machine.peek(sym["SCROLL"]) | (machine.peek(sym["SCROLL"] + 1) << 8)
    pending = None
    if machine.peek(sym["H_PENDING"]):
        pending = (machine.peek(sym["H_SCROLL"]) | (machine.peek(sym["H_SCROLL"] + 1) << 8),
                   machine.peek(sym["H_WX"]), machine.peek(sym["H_COL"]))
    return (scroll, machine.peek(sym["WORLD_X"]), machine.peek(sym["WORLD_CR"]),
            machine.peek(sym["KARA_X"]), machine.peek(sym["KARA_Y"]),
            machine.peek(sym["KARA_FRAME"]), pending)


def overlay_kara(want, sprites, scroll, kara_x, kara_y, frame):
    """Composite Kara over the tilemap, in the blitter's own address model.

        v    = (2*SCROLL + 80*char_row + byte_column) AND &07FF
        addr = &C000 + ((line AND 7) << 11) + v

    Same formula the Z80 uses, so a sprite drawn with the Module 3 flat
    model (or one that mishandles the 2047 seam) will not match.
    """
    rect = clip_rect(kara_x, kara_y)
    if rect is None:
        return want                 # culled: entirely off the display
    sy0, height, sline, sx0, width, scol = rect
    base = frame * SPR_FRAME_SIZE
    cr, raster = divmod(sline, 8)
    v = (2 * scroll + 80 * (cr & 0x1F) + scol) & 0x7FF
    for i in range(height):
        for j in range(width):
            addr = 0xC000 + (raster << 11) + ((v + j) & 0x7FF)
            off = base + (sy0 + i) * 16 + (sx0 + j) * 2
            if addr in want:
                want[addr] = (want[addr] & sprites[off]) | sprites[off + 1]
        raster += 1
        if raster == 8:
            raster = 0
            v = (v + 80) & 0x7FF
    return want


def first_opaque(sprites, frame, rect):
    """Screen line of her first line that actually puts pixels down.

    Not the top of her box: lines 0 and 1 of every frame are entirely
    transparent, so unclipped she first shows two lines down. Clip two
    or more lines off her top and she shows from the very first one -
    which is a correct difference, not a drift, and the check would
    otherwise read it as one.
    """
    sy0, height, sline, sx0, width, _ = rect
    for i in range(height):
        row = sprites[frame * SPR_FRAME_SIZE + (sy0 + i) * 16:][:16]
        if any(row[(sx0 + j) * 2] != 0xFF for j in range(width)):
            return sline + i
    return sline


def clip_rect(kara_x, kara_y):
    """What KARA_DRAW will actually draw: (sy0, h, screen line, sx0, w, col).

    The same four cases per axis the blitter uses, and the model has to
    agree with it exactly or the render checks below measure the model.
    Vertically the world wraps at 256 while the display shows 192, so a
    screen line of 192-255 is the hidden band - below the bottom and
    above the top at once. Horizontally nothing wraps: byte 80 of a
    character row is byte 0 of the next one down, so it is clipped.
    """
    if kara_y <= SCR_LINES - SPR_HEIGHT:
        sy0, height, sline = 0, SPR_HEIGHT, kara_y
    elif kara_y < SCR_LINES:
        sy0, height, sline = 0, SCR_LINES - kara_y, kara_y
    else:
        skip = (256 - kara_y) & 0xFF
        if skip >= SPR_HEIGHT:
            return None
        sy0, height, sline = skip, SPR_HEIGHT - skip, 0
    if kara_x <= SCREEN_WIDTH_BYTES - SPR_WIDTH:
        sx0, width, scol = 0, SPR_WIDTH, kara_x
    elif kara_x < SCREEN_WIDTH_BYTES:
        sx0, width, scol = 0, SCREEN_WIDTH_BYTES - kara_x, kara_x
    else:
        skip = (256 - kara_x) & 0xFF
        if skip >= SPR_WIDTH:
            return None
        sx0, width, scol = skip, SPR_WIDTH - skip, 0
    return sy0, height, sline, sx0, width, scol


def paint_cell(want, tiles, level_map, scroll, world_x, world_cr, cr, x):
    """One character cell of the view (scroll, world_x, world_cr) into `want`.

    The address model from CLAUDE.md 6.4 written out in full: MA masked
    to 10 bits, raster in bits 11-13, word times two.
    """
    wr = (world_cr + cr) & 0xFF
    map_row = (wr >> 1) & (MAP_H - 1)
    line_off = (wr & 1) * 64
    wc = (world_x + x) & 0xFF
    tile = level_map[map_row * MAP_W + ((wc >> 2) & (MAP_W - 1))]
    src = tile * TILE_BYTES + line_off + (wc & 3) * 2
    word = (scroll + cr * SCR_CHARS + x) & 0x3FF
    for raster in range(8):
        addr = 0xC000 + (raster << 11) + word * 2
        want[addr] = tiles[src + raster * 8]
        want[addr + 1] = tiles[src + raster * 8 + 1]


def expected_screen(tiles, level_map, scroll, world_x, world_cr):
    """Every byte the playfield should hold, as {vram address: value}."""
    want = {}
    for cr in range(SCR_CHAR_ROWS):
        for x in range(SCR_CHARS):
            paint_cell(want, tiles, level_map, scroll, world_x, world_cr, cr, x)
    return want


COL_HEAD = 18

def overlay_head(want, tiles, level_map, world_cr, pending):
    """The top COL_HEAD rows of a pending step's column, painted a frame
    early under the PENDING view. In the current view those words are
    the left (or right) edge of the row below (above) - they sit in RAM
    ahead of the latch, and the beam has already swept them."""
    if pending is None:
        return want
    h_scroll, h_wx, h_col = pending
    for cr in range(COL_HEAD):
        paint_cell(want, tiles, level_map, h_scroll, h_wx, world_cr, cr, h_col)
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


def model(tiles, level_map, sprites, st, with_kara, kara_st=None):
    """Expected video RAM for one sampled state.

    Two models, deliberately. The loop draws Kara and then erases her
    again in the same frame - ahead of the raster, then behind it - so
    at the VSYNC sample point video RAM holds pure tilemap and no Kara,
    while the frame the beam actually painted holds her. Comparing RAM
    against the Kara-free model and the framebuffer against the Kara
    model tests both halves of that arrangement.

    Kara is drawn at the TOP of a frame from the position the previous
    frame worked out, so the frame that ends at sample k showed the view
    of sample k with Kara from sample k-1: pass that as kara_st. And the
    Kara-free RAM at a sample already holds the head of the pending
    column, painted behind the beam during the frame just finished.
    """
    scroll, wx, wcr, kx, ky, kf, pending = st
    want = expected_screen(tiles, level_map, scroll, wx, wcr)
    if not with_kara:
        return overlay_head(want, tiles, level_map, wcr, pending)
    if kara_st is not None:
        kx, ky, kf = kara_st[3], kara_st[4], kara_st[5]
    return overlay_kara(want, sprites, scroll, kx, ky, kf)


def step_deltas(machine, sym, frames, pump=None):
    """Signed (scroll, world_x, world_cr) change for each frame that moved.

    Watching frame by frame is the only honest way to size a step: the
    demo's vertical phases only move every 4th frame, and poking its
    counters to force the cadence just races whatever it was doing.
    """
    out = []
    prev = state(machine, sym)[:3]
    for _ in range(frames):
        if pump:
            pump(machine, sym)
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
    check("handed over to the scrolling demo, and Kara has landed",
          machine.peek(sym["KARA_GROUND"]) == 1,
          f"grounded={machine.peek(sym['KARA_GROUND'])}, "
          f"WY={machine.peek(sym['KARA_WY'])}")

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
    # 0. Kara's screen column while the camera follows her
    #
    # The CRTC scrolls 2 bytes a step and she walks 1 byte a frame, so
    # the camera can only fire every other frame. Every one of those
    # frames is drawn and erased correctly and passes every check above
    # - but let her keep walking 1 byte a frame inside the push zone and
    # the column the blitter draws her at goes 54, 55, 54, 55 at 25 Hz,
    # which on a monitor is two Karas a character apart for as long as
    # the screen moves. Driven by the joystick, not pump_h: pump_h moves
    # her 2 bytes a frame and can never show it. It runs FIRST, from her
    # landing spot, because the joystick respects walls and pump_h does
    # not: after the other phases she can be standing against one, and a
    # walk that never moves is a camera that never steps.
    # ---------------------------------------------------------------
    print("\n  Kara's screen column while the camera follows her:")
    for mask, name, frames in [(0x08, "right", 40), (0x04, "left", 70)]:
        if mask == 0x04:                # walk her well clear of the map's left
            machine.joystick(0x08)      # edge first: the camera stops there and
            machine.run_frames(70)      # she resumes walking a byte a frame,
        machine.joystick(mask)          # which is correct and not what is tested
        log = []
        for _ in range(frames):
            next_frame_top(machine, sym)
            log.append(state(machine, sym))
        machine.joystick(0)
        moved = [i for i in range(1, len(log)) if log[i][0] != log[i - 1][0]]
        # On a frame where the view moved, the column the blitter drew her
        # at must not have moved. Checked per step, not over the whole
        # span: at the map's edge the camera stops and she walks on
        # normally, one byte a frame, which is correct and would otherwise
        # read as a failure.
        jumped = [(log[i - 1][3], log[i][3]) for i in moved
                  if log[i][3] != log[i - 1][3]]
        print(f"    {name:<6} camera stepped {len(moved)} times; "
              f"KARA_X changed on {len(jumped)} of them {jumped[:4]}")
        check(f"camera follows her {name} without moving her on screen",
              len(moved) >= 4 and not jumped,
              f"{len(moved)} camera steps, {len(jumped)} moved her")

    # ---------------------------------------------------------------
    # 1. video RAM vs the map, across all three scroll phases
    # ---------------------------------------------------------------
    print("\n  video RAM vs map, Kara already erased (15,360 bytes per sample):")
    scrolls, worst = [], 0
    for label, advance in [("horizontal", 0), ("horizontal", 90),
                           ("vertical down", 130), ("vertical down", 90),
                           ("vertical up", 100), ("vertical up", 90)]:
        drive(machine, sym, {"horizontal": 0, "vertical down": 1, "vertical up": 2}[label])
        pump = vstep if label != "horizontal" else pump_h
        for _ in range(advance // 10):
            pump(machine, sym)
            machine.run_frames(10)
        settle(machine, sym)            # never mid vertical step: the incoming
                                        # row is painted in two halves on
                                        # consecutive frames and is off-screen
                                        # until both are down, so RAM really
                                        # does disagree with the map between
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
    for phase, name, frames, want, least in [
            # Three steps in six frames, not six: the CRTC scrolls a whole
            # character (2 bytes) and she walks 1 byte a frame, so the
            # camera can only step every other frame. See PLAYER_X.
            (0, "horizontal",    6,  (1, 1, 0),    3),
            (1, "vertical down", 16, (40, 0, 1),   3),
            (2, "vertical up",   16, (-40, 0, -1), 3)]:
        drive(machine, sym, phase)
        settle(machine, sym)
        deltas = step_deltas(machine, sym, frames, pump_h if phase == 0 else vstep)
        uniform = deltas and all(d == want for d in deltas)
        # The COUNT in a fixed window is demo cadence - a vertical step now
        # commits two frames after it starts, so a window catches 3 or 4.
        # What must hold is that every step that happens is exactly one
        # character row and moves nothing else.
        check(f"{name} step", uniform and len(deltas) >= least,
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
    drive(machine, sym, 0)
    check("test can sync to the instant after VSYNC", sync_to_vsync(machine, sym))
    prev = state(machine, sym)
    sync_to_vsync(machine, sym)
    st = state(machine, sym)
    y0, hits, probes = find_display_top(
        machine, [expected_pens(model(tiles, level_map, sprites, st, True, kara_st=prev), st[0])],
        pen_to_hw)
    check("found the displayed area in the framebuffer", hits >= probes * 0.9,
          f"top scanline {y0}, {hits} of {probes} probes matched")

    for phase, name in [(0, "horizontal"), (1, "vertical down"), (2, "vertical up")]:
        drive(machine, sym, phase)
        history = []
        for _ in range(6):
            (vstep if phase else pump_h)(machine, sym)
            sync_to_vsync(machine, sym)
            history.append(state(machine, sym))   # mid-step frames included
        # Kara is drawn at the top of a frame from the position the frame
        # before worked out, so the frame that ended at sample i showed
        # sample i's view with sample i-1's Kara. i-2 is allowed as well:
        # sync_to_vsync searches coarsely and then finely for the instant
        # after VSYNC and can land a frame further on, which shifts the
        # whole pairing and has nothing to do with the engine.
        scores = [(render_mismatch(machine,
                                   expected_pens(model(tiles, level_map, sprites, history[i], True,
                                                       kara_st=history[k]), history[i][0]),
                                   pen_to_hw, y0), history[i])
                  for i in range(max(1, len(history) - 3), len(history))
                  for k in (i - 1, i - 2) if k >= 0]
        bad, st = min(scores, key=lambda t: t[0])   # states carry None fields
        print(f"    {name:<14} scroll={st[0]:>4} world=({st[1]:>3},{st[2]:>3}) "
              f"kara=({st[3]:>2},{st[4]:>3},f{st[5]})  "
              f"{bad:>6} wrong pixels  (best of {len(scores)} candidate views)")
        check(f"{name} scrolling is tear-free on screen", bad == 0, f"{bad} pixels")

    # ---------------------------------------------------------------
    # 3b. Kara does not move on screen while the world scrolls under her
    #
    # KARA_Y is a SCREEN line, so her rendered box must start at exactly
    # that line on every single frame. When SCROLL ran ahead of the CRTC
    # latch she was drawn at line 112 of a view that was not on screen
    # yet - 8 scanlines out, for the two frames before the latch caught
    # up - which looks like two Karas flickering. Every other check here
    # passed through that, because they only compared frames where the
    # two agreed.
    # ---------------------------------------------------------------
    print("\n  Kara's screen position through a vertical scroll:")
    for phase, name in [(1, "vertical down"), (2, "vertical up")]:
        drive(machine, sym, phase)
        tops = set()
        prev = None
        for _ in range(14):
            vstep(machine, sym)
            sync_to_vsync(machine, sym)
            st = state(machine, sym)
            if prev is None:
                prev = st
                continue
            bare = expected_pens(expected_screen(tiles, level_map, st[0], st[1], st[2]), st[0])
            fb = machine.framebuffer()
            rows = [y for y, row in enumerate(bare)
                    if any(fb[(y0 + y) * FB_W + 64 + x * 4] != pen_to_hw[p]
                           for x, p in enumerate(row))]
            rect = clip_rect(prev[3], prev[4])   # the Y she was DRAWN from
            if rect is None:                     # culled: nothing to find
                prev = st
                continue
            tops.add(rows[0] - first_opaque(sprites, prev[5], rect) if rows else None)
            prev = st
        seen = sorted(o for o in tops if o is not None)
        print(f"    {name:<14} rendered top minus KARA_Y: {seen}")
        # Her screen line MOVES during a vertical scroll - she holds a world
        # position and the camera travels under her. What must not move is
        # the offset between where the engine says she is and where she is
        # actually drawn. When SCROLL ran ahead of the CRTC latch this took
        # two values 8 apart: the "two Karas".
        check(f"Kara is drawn where the engine says she is, through a {name} step",
              len(seen) == 1 and 0 <= seen[0] < 8,
              f"offsets seen {seen}, want a single value in 0..7")

    # ---------------------------------------------------------------
    # 4. R12/R13 are only ever written during vertical blanking
    #
    # This one cannot be caught by looking at the picture HERE. The
    # headless emulator reloads its address latch from R12/R13 only at
    # vertical-total rollover, so a mid-frame write defers harmlessly to
    # the next frame and renders perfectly. A real 6845 takes it from the
    # next character row and splits the screen - which is what happened
    # on RetroVirtualMachine while every check above passed. So assert
    # the RULE, not the appearance: the write must land inside the 72
    # scanlines of border between the VSYNC exit and the first displayed
    # line.
    # ---------------------------------------------------------------
    print("\n  CRTC start-address writes (must be inside vertical blanking):")
    lo = sym["SCROLL_APPLY"]
    hi = lo + 30
    top = sym["SCROLL_DEMO.LOOP"] + 3
    worst = 0
    seen = 0
    for phase, name in [(0, "horizontal"), (1, "vertical down"), (2, "vertical up")]:
        drive(machine, sym, phase)
        latest = None
        for _ in range(12):
            (vstep if phase else pump_h)(machine, sym)
            sync_to_vsync(machine, sym)          # stops just past the VSYNC exit
            us = 0
            for _ in range(4800):                # stay inside ONE frame, or the
                machine.run_us(4)                # search runs on into the next
                us += 4                          # frame's legitimate vblank write
                if lo <= machine.pc <= hi:
                    latest = us if latest is None else max(latest, us)
                    seen += 1
                    break
        if latest is None:
            print(f"    {name:<14} no start-address write in any sampled frame")
            continue
        worst = max(worst, latest)
        print(f"    {name:<14} latest write {latest:>6} us after VSYNC "
              f"= scanline {latest / 64:5.1f}")
    check("R12/R13 written only in the border above the display",
          seen > 0 and worst < 4608,           # 72 scanlines x 64 us
          f"worst {worst} us (limit 4608 = 72 scanlines); {seen} writes seen")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(fails))
        return 1
    print("Module 4 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
