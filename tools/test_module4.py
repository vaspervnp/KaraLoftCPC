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
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/home/vasilhs/cpcemu")

import cpclib
from test_kara import decode
from cpc import CPC
from cpcboot import past_intro

ROOT = os.path.join(HERE, "..")
FB_W = 1024
FB_X0 = 64                      # first displayed column; 1 Mode 0 pixel = 4
T_PER_LINE = 256
FRAME_T = 79872

SCR_CHARS = 40
SCR_CHAR_ROWS = 24
SCR_LINES = SCR_CHAR_ROWS * 8
MAP_W, MAP_H = 128, 16           # the drawn tiles are 8x16, not 16x16
SCREEN_WIDTH_BYTES = 80
KARA_W, KARA_H = 12, 64          # the drawn sprite, stored as spans
KARA_RASTER_SAFE = 43            # the highest line she can be DRAWN FROM and
                                 # still beat the beam to her own last line.
                                 # Measured by the check in main(), not assumed.
                                 #
                                 # IT WAS 10 AND THE ENERGY BAR MOVED IT, and
                                 # not by touching her draw - the bar is written
                                 # after her, at the other end of the picture
                                 # (CLAUDE.md 7.8). A DOWNWARD row step costs it
                                 # 9,208 T on the frame the CRTC latches, the
                                 # frame runs over, and the NEXT frame starts
                                 # late: she loses ~320 T of lead a line, so
                                 # every 320 T of overrun is a line off the top.
                                 # Measured with the bar poked out, this driver
                                 # tears her at no line at all.
                                 #
                                 # AND THEN THE LAND SHEET WAS REDRAWN and it
                                 # went from 21 to 43. Her heaviest cel is 323
                                 # span bytes where it was 284, which is 2,808 T
                                 # of composite at the blitter's 72 T floor, so
                                 # the frame overruns by more and the next one
                                 # starts later still. **43 is the first time
                                 # this threshold has not been clear of the
                                 # camera**, which holds her between screen
                                 # lines 32 and 80 (8.8) - so under a vertical
                                 # step on every frame there is a band at the
                                 # top of her range where the beam catches her
                                 # last lines. cpcemu is not the witness that
                                 # counts for the raster (7.5): this one is for
                                 # a play-test on RVM to confirm or deny.
TILE_W_BYTES = 4                 # 8 pixels
TILE_BYTES = TILE_W_BYTES * 16   # 64 - column-major, 2 char columns of 32
COL_HEAD = 14                    # rows of the incoming column painted behind
                                 # the beam; tilemap.asm derives it
# HOW MANY TILES THE LEVEL HAS, OFF THE SHIPPED BLOB. It was 41, the
# City sheet's own frame count, and then make_city_map.py started
# appending composited overlay tiles to it (CLAUDE.md 7.3) - so a map
# byte that is a perfectly good baked tile read as a corrupt index.
N_TILES = os.path.getsize(os.path.join(
    ROOT, "build", "levels", "level1_city", "citytiles.bin")) // 64
MAP_ADDR = 0xA000              # base RAM: bank C4 belongs to the art
# The map is a section of level_1.lvl now, not an incbin of its own:
# docs/editor.md 9.2's header is 21 bytes and the map follows it.
LVL_HEADER = 21

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


def in_vsync(machine, sym, half=0):
    """In the WAIT_VSYNC spin - and in the RIGHT one.

    THERE ARE TWO A GAME FRAME NOW (CLAUDE.md 9): the loop draws her and
    thinks on the first hardware frame and erases her and puts the
    background right on the second, and both spin here. A sampler that
    took whichever it reached first got Kara still on the screen half
    the time, in a check about TILES - which is exactly what 227 wrong
    bytes of "playfield always matches the map" turned out to be, on a
    build whose playfield was correct. FRAME_HALF is the engine saying
    which half it is in, and 0 is the top of the loop, where she is
    erased and the background is finished.
    """
    return (sym["WAIT_VSYNC"] <= machine.pc <= sym["WAIT_VSYNC.WAIT"] + 6
            and ("FRAME_HALF" not in sym or machine.peek(sym["FRAME_HALF"]) == half))


def settle(machine, sym):
    """Advance to a frame with no vertical step in flight.

    A vertical step paints its incoming row in V_PARTS pieces on
    consecutive frames and only then latches the new start address, so
    in between SCROLL has moved and the picture has not. That is the design -
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
        # LET THE VERTICAL AXIS COME TO REST FIRST. The phases before
        # this one leave the view most of a map away from her, and
        # CAMERA_V then pans it back a character row at a time while the
        # horizontal step is being measured - eight steps of (-40, 0, -1)
        # in sixteen frames, against a check that wants (1, 1, 0). It is
        # not that the camera is wrong; it is that a row step is TWO
        # game frames now and not three (CLAUDE.md 7.8), so the catch-up
        # is half again as fast and reaches into a window it used to
        # finish before.
        machine.poke(sym["V_REQUEST"], 0)
        steady, last = 0, None
        for _ in range(240):
            next_frame_top(machine, sym)
            cur = machine.peek(sym["WORLD_CR"])
            steady = steady + 1 if cur == last else 0
            last = cur
            if steady >= 8 and machine.peek(sym["V_PHASE"]) == 0:
                break
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
    see tools/make_city_map.py.
    """
    machine.joystick(0x08)


def vstep(machine, sym):
    """Ask the engine for a vertical step, and KEEP asking.

    No PC hijacking: SCROLL_SERVICE picks the request up on its own,
    exactly as the ladder does.

    THE REQUEST IS HELD UP ON EVERY FRAME, including the two a step is
    in flight for, and that is not laziness. CAMERA_V drives this axis
    in game now (player.asm) and it stands down only while a request is
    already pending - so a driver that pokes V_REQUEST on some frames
    and not others hands the wheel back on the frames it skips, and the
    camera's correction for a Kara who has been left behind by the view
    gets measured here as a step in the wrong direction. Holding it up
    is also what a climbing player does. SCROLL_SERVICE ignores it until
    the step in flight has landed."""
    machine.poke(sym["V_REQUEST"], getattr(drive, "want", 1))
    return True


def vstep_idle(machine, sym):
    """vstep's older cadence: ask only while the engine is idle.

    Used where the DIRECTION of a step does not matter but its TIMING
    does - the CRTC-write check below. Asking every frame runs the steps
    back to back, which moves which frames latch and made the search
    below miss all of them; here the camera is welcome to put in steps
    of its own, because the rule being asserted is "R12/R13 only in the
    border" and it holds for whoever asked."""
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
            machine.peek(sym["KARA_FRAME"]), pending,
            machine.peek(sym["KARA_FACING"]),
            # ... and what she is carrying, because the inventory group
            # of the bottom row is part of the picture and she walks
            # over the roof's key while this suite drives her.
            machine.peek(sym["KEYS_COUNT"]), machine.peek(sym["COINS_COUNT"]))


def load_blobs():
    """Her two facings, decoded straight from the exporter's output.

    Not read out of the emulator: they live in banks &C5/&C6 and
    read_ram() ignores banking. The disc suite already proves the bytes
    in the bank are these bytes (tools/test_levels.py).
    """
    out = {}
    for facing, name in ((0, "kcore"), (1, "kcore_l")):
        raw = open(os.path.join(ROOT, "build", "levels", "_shared",
                                name + ".bin"), "rb").read()
        out[facing] = [decode(raw, f) for f in range((raw[0] | raw[1] << 8) // 2)]
    return out


def raster_safe(blobs, st):
    """Is this sample one where the beam cannot have overtaken her?"""
    clip = kara_clip(blobs[st[7]], st[5], st[4])
    return clip is not None and clip[0] >= KARA_RASTER_SAFE


def kara_clip(blob, frame, kara_y):
    """What KARA_SPAN_DRAW will draw: (first screen line, lines skipped
    off the top, lines drawn), or None when she is entirely off.

    This is kara.asm's arithmetic, not an approximation of it: her box
    top plus the frame's y0 wraps at 256, and a result of 192-255 is the
    hidden band, which the engine reads as ABOVE the display rather than
    below it - the camera can only put her there by scrolling up.
    """
    y0, rows = blob[frame]
    top = (kara_y + y0) & 0xFF
    if top < SCR_LINES:
        return top, 0, min(len(rows), SCR_LINES - top)
    above = 256 - top
    if above >= len(rows):
        return None
    return 0, above, len(rows) - above


def overlay_kara(want, blobs, scroll, kara_x, kara_y, frame, facing):
    """Composite Kara over the tilemap, in the blitter's own address model.

        v    = (2*SCROLL + 80*char_row + byte_column) AND &07FF
        addr = &C000 + ((line AND 7) << 11) + v

    Same formula the Z80 uses, so a sprite drawn with the Module 3 flat
    model (or one that mishandles the 2047 seam) will not match. She is
    SPANS now, so only the bytes a line actually carries are written,
    and each line starts at its own skip inside the box.
    """
    blob = blobs[facing]
    clip = kara_clip(blob, frame, kara_y)
    if clip is None:
        return want                 # culled: entirely off the display
    first, nskip, ndraw = clip
    rows = blob[frame][1]
    for i in range(ndraw):
        skip, pairs = rows[nskip + i]
        line = first + i
        v = (2 * scroll + 80 * ((line >> 3) & 0x1F) + kara_x + skip) & 0x7FF
        raster = line & 7
        for j, (mask, data) in enumerate(pairs):
            addr = 0xC000 + (raster << 11) + ((v + j) & 0x7FF)
            if addr in want:
                want[addr] = (want[addr] & mask) | data
    return want


def first_opaque(blobs, frame, facing, clip):
    """Screen line of her first line that actually puts pixels down.

    The exporter drops the empty lines off both ends, so the first
    STORED line always carries pixels - but clipping can start the draw
    on an interior blank one, and the check would read that as drift.
    """
    first, nskip, ndraw = clip
    rows = blobs[facing][frame][1]
    for i in range(ndraw):
        if rows[nskip + i][1]:
            return first + i
    return first


def paint_cell(want, tiles, level_map, scroll, world_x, world_cr, cr, x):
    """One character cell of the view (scroll, world_x, world_cr) into `want`.

    The address model from CLAUDE.md 6.4 written out in full: MA masked
    to 10 bits, raster in bits 11-13, word times two.
    """
    # Tiles are column-major: char_column * 32 + line * 2 + byte, and an
    # 8x16 tile is TWO character columns, not four.
    wr = (world_cr + cr) & 0xFF
    map_row = (wr >> 1) & (MAP_H - 1)
    line_off = (wr & 1) * 16
    wc = (world_x + x) & 0xFF
    tile = level_map[map_row * MAP_W + ((wc >> 1) & (MAP_W - 1))]
    src = tile * TILE_BYTES + line_off + (wc & 1) * 32
    word = (scroll + cr * SCR_CHARS + x) & 0x3FF
    for raster in range(8):
        addr = 0xC000 + (raster << 11) + word * 2
        want[addr] = tiles[src + raster * 2]
        want[addr + 1] = tiles[src + raster * 2 + 1]


def expected_screen(tiles, level_map, scroll, world_x, world_cr):
    """Every byte the playfield should hold, as {vram address: value}."""
    want = {}
    for cr in range(SCR_CHAR_ROWS):
        for x in range(SCR_CHARS):
            paint_cell(want, tiles, level_map, scroll, world_x, world_cr, cr, x)
    return want


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


HUD_CELLS, HUD_LINES = 6, 8
HUD_BASE = (SCR_CHAR_ROWS - 1) * SCR_CHARS      # the bar is on row 23
AMMO_CELLS = 7                                  # ... and the rounds share it
AMMO_BASE = HUD_BASE + HUD_CELLS                # columns 6-12
CLIPS_BASE = AMMO_BASE + AMMO_CELLS             # ... and the digit, column 13
INV_BASE = CLIPS_BASE + 1                       # ... and what she CARRIES,
INV_CELLS = 6                                   # columns 14-19: an icon and
                                                # a count for the key and for
                                                # the coins (CLAUDE.md 7.8)
CLIPS_N = 2                                     # AMMO_RESERVE is 28 at the
                                                # start of the level and a
                                                # reload takes 14 (bullets.asm);
                                                # nothing here fires or picks
                                                # anything up, so it stays 2


def hud_art():
    """The bar's cells and the rounds', from what the build generated."""
    text = open(os.path.join(ROOT, "build", "hud_art.inc")).read()
    out = {}
    for name in ("HUD_CELL_FULL", "HUD_CELL_EMPTY",
                 "HUD_PIP_FULL", "HUD_PIP_HALF", "HUD_PIP_EMPTY",
                 # ... and the item icons, which are FOUR bytes a line
                 # and not two: hud_icons is 8x16 Mode 0 pixels against
                 # a strip eight lines tall, so an icon is two cells
                 # wide and make_hud.py crops the eight lines with the
                 # most ink in them (CLAUDE.md 7.8).
                 "HUD_ICON_KEY", "HUD_ICON_KEY_DARK",
                 "HUD_ICON_COIN", "HUD_ICON_COIN_DARK"):
        body = text.split(name + ":")[1].splitlines()[1:]
        out[name] = [[int(v.strip()[1:], 16)
                      for v in line.strip()[3:].split(",")]
                     for line in body[:HUD_LINES]]
    # ... and the digits, which are one label and ten cels of eight
    # lines with a comment line before each.
    body = [ln for ln in text.split("HUD_DIGITS:")[1].splitlines()
            if ln.strip().startswith("db ")]
    for d in range(10):
        out[f"HUD_DIGIT_{d}"] = [[int(v.strip()[1:], 16)
                                  for v in ln.strip()[3:].split(",")]
                                 for ln in body[d * HUD_LINES:(d + 1) * HUD_LINES]]
    return out


HUD_ART = None


def overlay_hud(want, scroll, keys, coins, lit=HUD_CELLS):
    """Six cells at the BOTTOM row, columns 0-5 - src/hud.asm.

    Every test here runs at full health, so `lit` is six; the bar's own
    suite is what drives it down.
    """
    global HUD_ART
    if HUD_ART is None:
        HUD_ART = hud_art()
    for c in range(HUD_CELLS):
        art = HUD_ART["HUD_CELL_FULL" if c < lit else "HUD_CELL_EMPTY"]
        word = (scroll + HUD_BASE + c) & 0x3FF
        for line in range(HUD_LINES):
            base = 0xC000 + (line << 11) + (word << 1)
            want[base] = art[line][0]
            want[base + 1] = art[line][1]
    # ... AND THE ROUNDS AT THE OTHER END OF THE SAME ROW. Nothing in
    # this suite pulls the trigger, so both magazines stay full and
    # every one of the seven cells is two live rounds; it is
    # tools/test_hud.py that drives them down. Left out of the model,
    # they are 112 bytes of "the playfield does not match the map" on
    # every sample - which is what they were.
    for c in range(AMMO_CELLS):
        art = HUD_ART["HUD_PIP_FULL"]
        word = (scroll + AMMO_BASE + c) & 0x3FF
        for line in range(HUD_LINES):
            base = 0xC000 + (line << 11) + (word << 1)
            want[base] = art[line][0]
            want[base + 1] = art[line][1]
    art = HUD_ART[f"HUD_DIGIT_{CLIPS_N}"]
    word = (scroll + CLIPS_BASE) & 0x3FF
    for line in range(HUD_LINES):
        base = 0xC000 + (line << 11) + (word << 1)
        want[base] = art[line][0]
        want[base + 1] = art[line][1]
    # ... AND WHAT SHE IS CARRYING, columns 14-19. Six more cells went
    # on the end of this run when the inventory did (CLAUDE.md 7.8) and
    # the model did not follow: they are twelve bytes on each of eight
    # lines, so they were 96 bytes of "the playfield does not match the
    # map" on every sample - the same shape of gap the rounds left
    # before them, and the same worst sample to the byte.
    #
    # An icon is LIT while she has one and the same silhouette in the
    # DARK while she has not, which is the convention the spent rounds
    # already use: an empty slot is a thing she has not found, not a
    # hole in the row. The counts are the machine's own, because she
    # walks over the roof's key while this suite drives her.
    for i, (count, name) in enumerate(((keys, "KEY"), (coins, "COIN"))):
        icon = HUD_ART["HUD_ICON_" + (name if count else name + "_DARK")]
        digit = HUD_ART[f"HUD_DIGIT_{min(count, 9)}"]
        for line in range(HUD_LINES):
            for cell, pair in enumerate((icon[line][0:2], icon[line][2:4],
                                         digit[line])):
                word = (scroll + INV_BASE + i * 3 + cell) & 0x3FF
                base = 0xC000 + (line << 11) + (word << 1)
                want[base], want[base + 1] = pair[0], pair[1]
    return want


def model(tiles, level_map, blobs, st, with_kara, kara_st=None):
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
    scroll, wx, wcr, kx, ky, kf, pending, fa, keys, coins = st
    want = expected_screen(tiles, level_map, scroll, wx, wcr)
    if not with_kara:
        return overlay_hud(overlay_head(want, tiles, level_map, wcr, pending),
                           scroll, keys, coins)
    if kara_st is not None:
        kx, ky, kf, fa = kara_st[3], kara_st[4], kara_st[5], kara_st[7]
    # THE BAR GOES DOWN AFTER SHE DOES, on row 23, where the beam does
    # not arrive until 65,536 T and where she never reaches (7.8).
    return overlay_hud(overlay_kara(want, blobs, scroll, kx, ky, kf, fa),
                       scroll, keys, coins)


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


# THE MAGAZINE DIGIT LAGS ITS OWN VARIABLE BY ONE GAME FRAME, and that
# is not a fault to measure here. HUD_SERVICE runs early in the frame,
# before the logic that can take an ammo box; so on the frame the
# reserve changes, AMMO_RESERVE says 3 magazines and the glyph on the
# glass still says 2, and it is put right on the next one - 40 ms.
# The model reads the variable, so it scores those five pixels as
# tearing, in every check that compares the whole picture: it is what
# "torn at every line" turned out to be on a build whose sprite was
# pixel-perfect, because the raster sweep charges the picture's whole
# mismatch to whichever line she happened to start on.
#
# One character of the bottom row, and only that one: the health cells
# and the pips are compared like everything else.
DIGIT_X0 = (CLIPS_BASE - HUD_BASE) * 4          # character column 13
DIGIT_X1 = DIGIT_X0 + 4
DIGIT_Y0 = (SCR_CHAR_ROWS - 1) * 8              # ... of the bottom row


def render_mismatch(machine, pen_rows, pen_to_hw, y0, skip=None):
    """Wrong pixels between the model and the picture.

    `skip` is an optional (x0, x1) pixel range left out of the count,
    used to measure the SCROLL on a frame where Kara herself is above
    the raster threshold and so is not a measure of anything.
    """
    fb = machine.framebuffer()
    bad = 0
    for y, row in enumerate(pen_rows):
        base = (y0 + y) * FB_W + FB_X0
        for x, pen in enumerate(row):
            if skip and skip[0] <= x < skip[1]:
                continue
            if y >= DIGIT_Y0 and DIGIT_X0 <= x < DIGIT_X1:
                continue                # the digit - see above
            if fb[base + x * 4] != pen_to_hw[pen]:
                bad += 1
    return bad


def find_display_top(machine, candidates, pen_to_hw):
    """Search for the first displayed scanline instead of assuming it.

    R6 = 24 shortens the picture, so the offset is not the one the other
    suites use. Searching for it means a wrong guess shows up as a poor
    score rather than as a silent pass.

    IT SCORED THE TOP 24 LINES AND THOSE ARE THE NIGHT SKY, which made
    the search DEGENERATE: lines 0-15 of this level are 1,259 pixels of
    one pen out of 1,280 (CLAUDE.md 7.7 measures the same thing on the
    title), so an offset two scanlines out scores exactly as well as the
    right one - and the loop kept the FIRST of the plateau, which is the
    lowest. It returned 35 against a true 37 and reported "256 of 256
    probes matched" while doing it, and every rendered check downstream
    then compared the picture against a model two scanlines up: 8,600 of
    30,720 pixels wrong on a build whose picture was correct.

    It is the project's own rule about gates, one floor along (CLAUDE.md
    10): the question is not whether the number is right, it is whether
    changing it changes anything. So the score is taken over the WHOLE
    192 lines, where the building and the street have detail in them,
    and the MARGIN to the runner-up is returned with it - a plateau is
    then a visible fact and not a silent one.
    """
    fb = machine.framebuffer()
    scored = []
    for pen_rows in candidates:
        for y0 in range(0, 110):
            hit = 0
            for y in range(0, SCR_LINES, 4):
                base = (y0 + y) * FB_W + FB_X0
                for x in range(0, 160, 5):
                    if fb[base + x * 4] == pen_to_hw[pen_rows[y][x]]:
                        hit += 1
            scored.append((hit, y0))
    scored.sort(key=lambda t: (-t[0], t[1]))
    probes = (SCR_LINES // 4) * 32
    runner = next((h for h, y in scored if y != scored[0][1]), 0)
    return scored[0][1], scored[0][0], probes, scored[0][0] - runner


ENT_BAKE_ADDR = 0x7C00          # src/entity.asm: 16 scratch tiles
ENT_BAKE_BYTES = 16 * 64


def read_tile_bank(machine, sym, n, src=0x4000):
    """The first n bytes of bank C4, copied out where read_ram can see them.

    read_ram() ignores banking and always returns bank 1, so the bytes
    have to be moved into base RAM by the machine itself. The scratch is
    &9000 - inside the level staging buffer, which is free once a level
    has finished loading, and NOT &A000, which is the map.

    The blob is entered with a JP and its last instruction is a spin
    rather than a RET, so the caller's PC is put back by hand - to the
    TOP of WAIT_VSYNC and not to the address that was interrupted. The
    spin is "in a,(c)" with BC preloaded by the instruction above it,
    and the blob leaves BC pointing at the gate array; resuming mid-spin
    polls the wrong chip and hangs forever.
    """
    machine.run_code(0x8000, bytes([
        0x01, 0xC4, 0x7F, 0xED, 0x49,                       # ld bc,&7FC4:out
        0x21, src & 0xFF, src >> 8, 0x11, 0x00, 0x90,       # hl=src de=&9000
        0x01, n & 0xFF, n >> 8, 0xED, 0xB0,                 # bc=n : ldir
        0x01, 0xC0, 0x7F, 0xED, 0x49,                       # ld bc,&7FC0:out
        0x18, 0xFE]))                                       # jr $
    out = machine.read_ram(0x9000, n)
    machine.set_pc(sym["WAIT_VSYNC"])
    return out


def column_sweep(m, sym):
    """DRAW_COLUMN against the address model, over a map with no repeats.

    This goes last because it overwrites the map with a pseudo-random
    one, and that is the point: the city level is a continuous
    rooftop, so most of its cells hold the same tile and a column that
    reads the WRONG map row still matches. That is exactly how a
    COL_FIRST * 40 written as COL_FIRST * 36 survived - the head starts
    at row 0 where the multiply cannot be wrong, and the tail's error
    landed on identical tiles more often than not.

    Sweeping (scroll, world position, split) with every cell distinct
    leaves it nowhere to hide - but ONLY if video RAM is scrubbed first.
    The first version of this check read the address the model says and
    found the right bytes there because the demo had already painted
    them correctly, so it passed with the bug put back. It now fills the
    screen with noise before every placement, which also makes "nothing
    outside the column was touched" free to check.
    """
    TILES, MAPA, STUB = 0x4000, MAP_ADDR, 0x9800

    def page(cfg):
        m.write_ram(STUB, bytes([0xF3, 0x01, cfg, 0x7F, 0xED, 0x49, 0x18, 0xFE]))
        m.set_pc(STUB)
        for _ in range(60):
            m.run_us(1)

    def draw(col, first, n):
        m.poke(sym["COL_FIRST"], first)
        m.poke(sym["COL_N"], n)
        code = bytes([0xF3, 0x01, 0xC4, 0x7F, 0xED, 0x49, 0x3E, col,
                      0xCD, sym["DRAW_COLUMN"] & 0xFF, sym["DRAW_COLUMN"] >> 8,
                      0x18, 0xFE])
        m.write_ram(STUB, code)
        m.set_pc(STUB)
        for _ in range(400000):
            m.run_us(1)
            if m.pc == STUB + len(code) - 2:
                return

    # a map where every cell differs from its neighbours in both axes.
    # The map is base RAM, so it needs no paging; the TILES do.
    rng = random.Random(99)
    m.write_ram(MAPA, bytes(rng.randrange(N_TILES) for _ in range(MAP_W * MAP_H)))
    page(0xC4)
    tiles = [[m.peek(TILES + t * TILE_BYTES + i) for i in range(TILE_BYTES)]
             for t in range(N_TILES)]
    page(0xC0)
    mp = [m.peek(MAPA + i) for i in range(MAP_W * MAP_H)]

    bad = cases = stray = 0
    for scroll in (0, 1, 39, 40, 512, 1000, 1023):
        for wx, wcr in ((0, 0), (1, 1), (2, 7), (3, 15), (37, 8)):
            for first, n in ((0, 24), (0, 18), (18, 6), (1, 1), (23, 1), (7, 9)):
                m.poke(sym["SCROLL"], scroll & 255)
                m.poke(sym["SCROLL"] + 1, scroll >> 8)
                m.poke(sym["WORLD_X"], wx)
                m.poke(sym["WORLD_CR"], wcr)
                col = (scroll + wx) % 40
                noise = bytes((i * 37 + 11) & 0xFF for i in range(0x4000))
                m.write_ram(0xC000, noise)
                draw(col, first, n)
                cases += 1
                written = set()
                for r in range(first, first + n):
                    wc, wr = wx + col, wcr + r
                    t = mp[((wr >> 1) & (MAP_H - 1)) * MAP_W
                           + ((wc >> 1) & (MAP_W - 1))]
                    off = (wc & 1) * 32 + (16 if wr & 1 else 0)
                    addr = 0xC000 + (((scroll + col + r * 40) * 2) & 0x7FF)
                    for line in range(8):
                        for byte in range(2):
                            a = addr + (line << 11) + byte
                            written.add(a)
                            if tiles[t][off + line * 2 + byte] != m.peek(a):
                                bad += 1
                after = m.read_ram(0xC000, 0x4000)
                for i in range(0x4000):
                    if after[i] != noise[i] and 0xC000 + i not in written:
                        stray += 1
    check("DRAW_COLUMN matches the address model over a map with no repeats",
          bad == 0, f"{bad} wrong bytes over {cases} placements")
    check("DRAW_COLUMN writes nothing outside its column", stray == 0,
          f"{stray} bytes")


def main():
    sym = symbols()
    machine = CPC()
    machine.run_frames(150)
    machine.insert_disc(os.path.abspath(os.path.join(ROOT, "build", "kara.dsk")))
    machine.type_text('RUN"DISC\n')
    machine.run_frames(400)
    # THE TITLE SCREEN COMES FIRST NOW and it waits for a key rather
    # than a timer (CLAUDE.md 7.7), so the prompt has to be answered
    # before any of this is looking at the game at all.
    check("the title screen answered the press",
          past_intro(machine, sym), "PRESS SPACE OR FIRE -> the city")
    check("the game is running", machine.mode == 0, f"mode={machine.mode}")

    # THERE IS NO INTRO TO CUT SHORT ANY MORE. RUN"DISC goes straight to
    # the rooftop, so all that is left to wait for is the level itself.
    # The scrolling demo now LOADS LEVEL 1 OFF THE DISC before it paints
    # anything - four banks of ZX0, about 72 frames (CLAUDE.md 7.5) -
    # and then DRAW_PLAYFIELD wants its ~18 to fill all 40 columns, and
    # Kara a few more to fall onto the roof.
    machine.run_frames(140)
    # TAKE THE LEVEL'S DRONES OFF THE SCREEN AND LEAVE THEM OFF. They
    # are a PERSISTENT sprite - drawn once and left there between
    # refreshes (src/enemy.asm) - and everything below compares video
    # RAM, or the rendered frame, against the TILEMAP. Clearing
    # ENEMY_LIVE makes ENEMY_PICK find nobody, and the refresh that
    # follows lifts the last one off; src/enemy.asm's own suite is what
    # checks they are drawn at all.
    machine.poke(sym["ENEMY_LIVE"], 0)
    machine.run_frames(4)
    check("handed over to the scrolling demo, and Kara has landed",
          machine.peek(sym["KARA_GROUND"]) == 1,
          f"grounded={machine.peek(sym['KARA_GROUND'])}, "
          f"WY={machine.peek(sym['KARA_WY'])}")

    blobs = load_blobs()
    # THE MODEL NEEDS THE SCRATCH TILES TOO. src/entity.asm bakes each
    # pickup into a tile at the top of C4 (index 240 up) and points the
    # map cell at it, so the picture legitimately contains tiles that
    # citytiles.bin has never heard of. The bank cannot be read whole -
    # read_tile_bank stages through &9000 and 16 KB from there runs into
    # video RAM - so it is the file plus that 1 KB.
    shipped = open(os.path.join(ROOT, "build", "levels", "level1_city",
                                "citytiles.bin"), "rb").read()
    tiles = (shipped + bytes(ENT_BAKE_ADDR - 0x4000 - len(shipped))
             + bytes(read_tile_bank(machine, sym, ENT_BAKE_BYTES,
                                    ENT_BAKE_ADDR)))
    level_map = machine.read_ram(sym["LEVEL_LVL"] + LVL_HEADER,
                                 MAP_W * MAP_H)
    check("level blob is intact in base RAM",
          len(set(level_map)) > 1 and max(level_map) < N_TILES,
          f"{len(set(level_map))} distinct tiles, max index {max(level_map)}")
    # ... and the model must be told about the bake, the same way the
    # engine was: the INSTALLED map is the one the blitters read.
    level_map = machine.read_ram(MAP_ADDR, MAP_W * MAP_H)

    pal = machine.read_ram(sym["PALETTE_DATA"], 16)
    pen_to_hw = [b & 0x1F for b in pal]

    # NO BAND PROFILE HERE ANY MORE. It counted the scanlines the border
    # spent in MARK_SPRITE, and the game's border is black now - the
    # coloured bands are the Module 1-3 screen's and tools/test_module3.py
    # still reads them there. It was never a measurement worth keeping
    # down here anyway: CLAUDE.md 9 records that the bands under-report
    # by the 40 scanlines the emulator paints as colour 0 in vblank, and
    # the frame is measured by tools/bench.py from a DI stub and by the
    # loop-iteration counts in test_enemies and test_climb.

    check("test can sync to the top of a frame", sync_to_frame_top(machine, sym))
    # The tiles come off the DISC into C4 now, and the map is installed
    # into base RAM - two different paths, so two checks.
    in_bank = bytes(read_tile_bank(machine, sym, len(shipped)))
    check("the level's own tiles are in bank C4",
          in_bank == shipped,
          f"{sum(1 for a, b in zip(in_bank, shipped) if a != b)} of "
          f"{len(shipped)} bytes differ")
    # The installed map is the shipped one EXCEPT where a pickup was
    # baked in: those cells hold that pickup's scratch tile instead.
    # Anything else differing means the staging buffer reached it.
    shipped_map = bytes(machine.read_ram(sym["LEVEL_LVL"] + LVL_HEADER,
                                         MAP_W * MAP_H))
    installed = bytes(machine.read_ram(MAP_ADDR, MAP_W * MAP_H))
    baked = {}
    for slot in range(machine.peek(sym["ENT_BAKED"])):
        L = sym["ENT_BAKE_LIST"] + slot * 5
        cell = machine.peek(L + 2) | (machine.peek(L + 3) << 8)
        baked[cell - MAP_ADDR] = (240 + slot, machine.peek(L + 4))
    stray = [i for i in range(MAP_W * MAP_H)
             if installed[i] != shipped_map[i]
             and baked.get(i, (None, None)) != (installed[i], shipped_map[i])]
    check("the map is installed in base RAM, clear of the staging buffer",
          not stray,
          f"{len(baked)} cells baked, {len(stray)} others differ")

    # ---------------------------------------------------------------
    # 0. Kara's screen column while the camera follows her
    #
    # The CRTC scrolls 2 bytes a step and she walks half a byte a frame,
    # so the camera can only fire every FOURTH frame. Every one of those
    # frames is drawn and erased correctly and passes every check above
    # - but let her keep walking her own distance inside the push zone
    # and the column the blitter draws her at goes 54, 55, 54, 55 at
    # 25 Hz, which on a monitor is two Karas a character apart for as
    # long as the screen moves. Driven by the joystick, not pump_h:
    # pump_h moves her 2 bytes a frame and can never show it. It runs
    # FIRST, from her landing spot, because the joystick respects walls
    # and pump_h does not: after the other phases she can be standing
    # against one, and a walk that never moves is a camera that never
    # steps.
    #
    # EIGHT CAMERA STEPS AND NOT TEN, AND THE FRAME COUNTS ARE THE SAME
    # ONES. The walk is half the speed it was (P_WALK_BEAT, CLAUDE.md
    # 8.2), so these forty frames buy nine camera steps where they used
    # to buy twenty, and the settled-column property is asserted over
    # the last eight of them instead of the last ten.
    #
    # WALKING FURTHER TO GET THE TEN BACK IS NOT THE FIX, and finding
    # that out is worth the comment: every phase of this suite runs from
    # where the last one left her, and eight more frames here - four
    # bytes of roof - put something at the bottom of the picture that
    # section 3a's model does not draw, 800 lines below. All eighteen of
    # its samples then came out "torn" at once with the same 41 pixels
    # wrong on every one of them, which is what an unmodelled sprite
    # looks like and not what a beam race looks like: a race gets worse
    # the higher up the picture she is drawn.
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
        # ... AND ONLY WHILE THE CAMERA IS FOLLOWING HER. Turning round
        # makes it PAN to the other mark (CAM_TRAIL / CAM_LEAD in
        # player.asm) - a whole character a frame while she walks her
        # own byte - and her screen column is SUPPOSED to move across
        # the picture through that. The lock-step only applies once she
        # has arrived, which is what CAM_BAND names in the engine.
        # THE PROPERTY IS ABOUT THE STEADY STATE. Turning round makes
        # the camera PAN to the other mark (CAM_TRAIL / CAM_LEAD in
        # player.asm) and her screen column is supposed to move across
        # the picture through that; a byte of correction as she settles
        # into the push zone is not "two Karas a character apart for as
        # long as the screen moves" either. What that is, is her column
        # OSCILLATING once she has arrived - so the check is that the
        # last ten camera steps all drew her at one single column.
        at_mark = moved[-8:]
        # On a frame where the view moved, the column the blitter drew her
        # at must not have moved. Checked per step, not over the whole
        # span: at the map's edge the camera stops and she walks on
        # normally, one byte a frame, which is correct and would otherwise
        # read as a failure.
        settled = {log[i][3] for i in at_mark} | {log[i - 1][3] for i in at_mark}
        print(f"    {name:<6} camera stepped {len(moved)} times; over the last "
              f"{len(at_mark)} she was drawn at columns {sorted(settled)}")
        check(f"camera follows her {name} without moving her on screen",
              len(moved) >= 8 and len(settled) == 1,
              f"{len(settled)} distinct columns over the last "
              f"{len(at_mark)} camera steps")

    # ---------------------------------------------------------------
    # 1. video RAM vs the map, across all three scroll phases
    # ---------------------------------------------------------------
    print("\n  video RAM vs map, Kara already erased (15,360 bytes per sample):")
    scrolls, worst, worst_clipped = [], 0, 0
    for label, advance in [("horizontal", 0), ("horizontal", 90),
                           ("vertical down", 130), ("vertical down", 90),
                           ("vertical up", 100), ("vertical up", 90)]:
        drive(machine, sym, {"horizontal": 0, "vertical down": 1, "vertical up": 2}[label])
        pump = vstep if label != "horizontal" else pump_h
        for _ in range(advance // 10):
            pump(machine, sym)
            machine.run_frames(10)
        settle(machine, sym)            # never mid vertical step: the incoming
                                        # row is painted a piece a frame and
                                        # is off-screen until every piece is
                                        # down, so RAM really does disagree
                                        # with the map in between
        st = state(machine, sym)
        scroll, wx, wcr = st[0], st[1], st[2]
        scrolls.append(scroll)
        # RE-READ THE MAP EVERY SAMPLE. The driver walks her across the
        # level and a pickup she touches is un-baked - its cell goes
        # back to the tile underneath - so a map snapshot taken before
        # the sweep describes a screen that has since changed.
        level_map = machine.read_ram(MAP_ADDR, MAP_W * MAP_H)
        want = model(tiles, level_map, blobs, st, with_kara=False)
        vram = machine.read_ram(0xC000, 0x4000)
        bad = sum(1 for a, v in want.items() if vram[a - 0xC000] != v)
        # WHERE SHE RUNS PAST THE BOTTOM, HER ERASE STILL LEAVES
        # SOMETHING, AND MODULE 6d IS NOT THE ANSWER TO IT. 6d is the X
        # clip (CLAUDE.md 8.2) and these samples are all well inside
        # both side edges; what is left is the other axis, where
        # SPAN_CLIP_V drops the lines that are off the bottom and the
        # deepest samples come back a few bytes short anyway. Only this
        # driver reaches it - it pokes V_REQUEST on every frame with no
        # player behind it, and the camera never does (CLAUDE.md 8.8).
        # It is split out rather than excluded, and BOUNDED rather than
        # tolerated: the unclipped samples still have to be exact, and
        # the clipped ones may not get worse than they are.
        clip = kara_clip(blobs[st[7]], st[5], st[4])
        whole = (clip is not None and clip[1] == 0
                 and clip[2] == len(blobs[st[7]][st[5]][1]))
        if whole:
            worst = max(worst, bad)
        else:
            worst_clipped = max(worst_clipped, bad)
        raw = machine.crtc_screen_addr
        ok_crtc = raw == (0x3000 | scroll)
        print(f"    {label:<14} scroll={scroll:>4} world=({wx:>3},{wcr:>3}) "
              f"kara=({st[3]:>2},{st[4]:>3},f{st[5]})  "
              f"{bad:>5} wrong{'' if whole else ' (CLIPPED)'}  "
              f"CRTC=&{raw:04X} {'ok' if ok_crtc else 'MISMATCH'}")
        if not ok_crtc:
            fails.append(f"CRTC start address at scroll {scroll}")

    check("playfield always matches the map", worst == 0, f"worst sample: {worst} bytes")
    check("... and the residue where she hangs off the bottom is bounded",
          worst_clipped <= 64,
          f"worst clipped sample: {worst_clipped} bytes - the bottom "
          f"clip's own residue, which module 6d, the X clip, does not "
          f"touch (CLAUDE.md 8.2)")
    check("scrolling crossed the 1024-word wrap",
          max(scrolls) + SCR_CHARS * SCR_CHAR_ROWS > 1024,
          f"max scroll {max(scrolls)} + 960 words")

    # ---------------------------------------------------------------
    # 2. step sizes
    # ---------------------------------------------------------------
    print("\n  step sizes:")
    for phase, name, frames, want, least in [
            # Three steps in SIXTEEN frames, not sixteen: the CRTC
            # scrolls a whole character (2 bytes) and a walk covers half
            # a byte a frame, so the camera can only step every fourth
            # one. The window was six frames while the walk was twice
            # this speed and it caught three; it catches one now. See
            # PLAYER_X and P_WALK_BEAT.
            (0, "horizontal",    16, (1, 1, 0),    3),
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
    y0, hits, probes, margin = find_display_top(
        machine, [expected_pens(model(tiles, level_map, blobs, st, True, kara_st=prev), st[0])],
        pen_to_hw)
    check("found the displayed area in the framebuffer", hits >= probes * 0.9,
          f"top scanline {y0}, {hits} of {probes} probes matched")
    # ... AND IT IS THE ONLY OFFSET THAT SCORES THAT WELL, which is the
    # control on the line above: over the sky alone the search had a
    # plateau two scanlines wide and silently took the wrong end of it.
    check("... and no other offset comes close", margin >= probes * 0.1,
          f"the runner-up scores {hits - margin} against {hits}, "
          f"a margin of {margin} probes - two scanlines out is 10,000 wrong "
          f"pixels downstream, and over the sky alone it was none")

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
        #
        # Samples where she is drawn from above KARA_RASTER_SAFE are left
        # out, because there she is not a measure of the SCROLL: at
        # ~576 T a line against the raster's 256 the beam catches her
        # last lines, and the check below measures that threshold on its
        # own. The vertical driver reaches it only because it pokes
        # V_REQUEST with no player behind it - the camera does not.
        scores = []
        for i in range(max(1, len(history) - 3), len(history)):
            for k in (i - 1, i - 2):
                if k < 0:
                    continue
                # Where she is above the threshold, her own box is left
                # out of the count and the model draws her anyway: what
                # is being measured here is the SCROLL, and a torn
                # sprite is measured by its own check below.
                safe = raster_safe(blobs, history[k])
                skip = None if safe else (history[k][3] * 2,
                                          (history[k][3] + KARA_W) * 2)
                pens = expected_pens(model(tiles, level_map, blobs, history[i],
                                           True, kara_st=history[k]), history[i][0])
                scores.append((render_mismatch(machine, pens, pen_to_hw, y0, skip),
                               history[i], safe))
        bad, st, safe = min(scores, key=lambda t: t[0])
        if not safe:
            name += "*"                 # her box was not counted
        print(f"    {name:<14} scroll={st[0]:>4} world=({st[1]:>3},{st[2]:>3}) "
              f"kara=({st[3]:>2},{st[4]:>3},f{st[5]})  "
              f"{bad:>6} wrong pixels  (best of {len(scores)} candidate views)")
        check(f"{name} scrolling is tear-free on screen", bad == 0, f"{bad} pixels")

    # ---------------------------------------------------------------
    # 3a. How high up the display she can be drawn before the beam
    #     overtakes her - measured, and asserted, so a slower blitter
    #     cannot quietly push it down the picture.
    #
    # She goes first, in the top border, and the border is her whole
    # lead: ~576 T a line against the raster's 256 means she loses
    # ground every line and only a big enough head start saves her.
    # CLAUDE.md 9 records 13 for the 16x48 sprite; the 24x64 one is 64
    # lines instead of 48 but no worse per line, so the threshold has
    # not moved. Below it the bottom of her flickers - RAM is correct
    # and the picture is not, which is why this is a rendered check.
    # ---------------------------------------------------------------
    print("\n  how high she can be drawn before the beam catches her:")
    worst, latched = {}, 0
    for phase in (1, 2):
        drive(machine, sym, phase)
        hist = []
        # DRIVEN UNTIL IT HAS SEEN BOTH SIDES OF THE THRESHOLD, not for
        # a fixed number of frames. What this needs is a range of screen
        # positions, and how many frames that takes is a property of the
        # scroll engine: the row paint was split from two pieces into
        # four when `climb` arrived (CLAUDE.md 8.2), which halved the
        # lines a frame the view travels, and a count written against the
        # old cadence quietly stopped reaching the top of the picture -
        # the negative control below then passed for the wrong reason,
        # which is exactly what a negative control is there to stop.
        # The cap is what makes a genuine failure fail rather than hang.
        for _ in range(140):
            if (any(ln < KARA_RASTER_SAFE for ln in worst)
                    and any(ln >= KARA_RASTER_SAFE for ln in worst)):
                break
            vstep(machine, sym)
            sync_to_vsync(machine, sym)
            hist.append(state(machine, sym))
            if len(hist) < 3:
                continue
            i = len(hist) - 1
            # A FRAME WITH AN ENEMY ON IT IS NOT A SAMPLE THIS MODEL CAN
            # SCORE. `model` draws the tilemap and the heroine; the
            # drone's pixels are on the screen between refreshes because
            # it is a persistent sprite (CLAUDE.md 8.7), and they would
            # be counted as tearing in hers.
            if machine.peek(sym["ENEMY_DREW"]):
                continue
            # NOR IS THE FRAME A ROW STEP LATCHES ON, AND THAT ONE IS A
            # COST AND NOT AN EXCUSE. The bottom row carries fourteen
            # characters of HUD now - six health cells, seven of rounds
            # and the magazine digit - and when the view moves down a
            # row every one of them has to be repainted from the tilemap
            # one row up: 13,200 T of DRAW_ROW on the frame the CRTC
            # latches, which is 4,000 more than that frame has
            # (CLAUDE.md 7.8). Measured with HUD_VACATE poked to RET the
            # same driver is 201 loop iterations in 200 and this sweep
            # is clean; with it in, one frame in five overruns and she
            # is drawn late on the next.
            #
            # So the sweep scores the frames either side of a latch and
            # not the latch itself, and the count of them is printed:
            # a check that silently skipped them would hide the day the
            # cost lands on every frame instead of one in five.
            if hist[i][2] != hist[i - 1][2]:
                latched += 1
                continue
            # THE VIEW IS A CANDIDATE TOO, NOT JUST HER POSITION. At
            # 25 Hz the loop's two halves both spin in WAIT_VSYNC and
            # the sample is taken at the top of one game frame, while
            # the picture on the glass was swept under the view latched
            # at the top of the one before: which of the two the
            # framebuffer holds depends on where in the pair the sample
            # landed. Scoring against one of them only made every line
            # of a perfectly clean sprite read as torn - 20 samples of
            # 20 - because a view one character out is 160 wrong pixels
            # a row, not five.
            n = min(render_mismatch(machine,
                                    expected_pens(model(tiles, level_map, blobs, hist[v],
                                                        True, kara_st=hist[k]), hist[v][0]),
                                    pen_to_hw, y0)
                    for k in (i - 1, i - 2, i - 3)
                    for v in (i, i - 1))
            clip = kara_clip(blobs[hist[i - 1][7]], hist[i - 1][5], hist[i - 1][4])
            if clip:
                worst[clip[0]] = max(worst.get(clip[0], 0), n)
    lines = sorted(worst)
    dirty = [ln for ln in lines if worst[ln]]
    clean = [ln for ln in lines if not worst[ln]]
    print(f"    drawn from lines {lines[0]}..{lines[-1]}; "
          f"torn at {dirty or 'none'}, clean at {len(clean)} of {len(lines)}"
          f"; {latched} samples skipped on a row step's latch frame")
    check("she is drawn intact from KARA_RASTER_SAFE down",
          all(worst[ln] == 0 for ln in lines if ln >= KARA_RASTER_SAFE),
          f"torn at {[ln for ln in dirty if ln >= KARA_RASTER_SAFE] or 'no line'}")
    # THE ANTI-VACUITY GUARD IS THE REACH, NOT A TEAR. The check above
    # would pass on a build that never drew her near the top at all, so
    # the sweep has to be shown to have gone ABOVE the threshold - and
    # that is a deterministic fact about the driver.
    #
    # It used to demand a torn line up there instead, and the highest
    # line this driver can reach is 5: measured TORN on one run of the
    # suite and CLEAN on the next, a few hundred T either side of the
    # beam. That is what a threshold looks like from close up, and it is
    # why the safe line is recorded as 10 and not as 5 - but it makes a
    # terrible assertion.
    check("and the sweep went above the threshold, so that is not vacuous",
          lines[0] < KARA_RASTER_SAFE,
          f"highest line she was drawn at is {lines[0]}, against "
          f"KARA_RASTER_SAFE = {KARA_RASTER_SAFE}; line {lines[0]} came out "
          f"{'TORN' if worst[lines[0]] else 'clean'} this run, which is the "
          f"margin itself")

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
    # THE AXIS IS THE TEST'S FOR THE LENGTH OF THIS CHECK. CAMERA_V
    # keeps her middle between CAM_TOP and CAM_BOT and stands down only
    # while a request is pending (player.asm), so a driver that steps
    # and then WAITS for the step to land - which is the only cadence
    # this check's premise is true under, see below - hands the wheel
    # back on every frame it waits and the camera puts the view
    # straight back. Measured: she sat at KARA_Y 48 for all thirteen
    # samples, the view stepping one way and the camera the other.
    # Poked out, the test owns the axis and she is standing still in the
    # world while it travels under her, which is what is being asserted.
    camera_v = machine.peek(sym["CAMERA_V"])
    machine.poke(sym["CAMERA_V"], 0xC9)          # RET
    for phase, name in [(1, "vertical down"), (2, "vertical up")]:
        # MAKE ROOM FIRST. The view is wherever the checks above left
        # it, and at the end of its travel a step does nothing: she sits
        # off the display at KARA_Y 200 and every sample is a reading of
        # nothing. Driving the other way for a while is not a setup
        # convenience, it is what stops the check passing vacuously.
        drive(machine, sym, 2 if phase == 1 else 1)
        for _ in range(40):
            if not (SCR_LINES // 8 <= machine.peek(sym["KARA_Y"])
                    <= SCR_LINES * 7 // 8):
                break                    # room to travel in the direction asked
            vstep_idle(machine, sym)
            settle(machine, sym)
        drive(machine, sym, phase)
        tops, clipped, samples, worst_pic = set(), set(), [], 0
        prev = None
        for _ in range(14):
            # A STEP, AND THEN LET IT LAND, which is the only cadence
            # this check's own premise is true under.
            #
            # "Her rendered box starts at exactly KARA_Y" stopped being
            # true on the frame the CRTC latches a vertical step, and
            # that is the DESIGN and not a fault: SPAN_ERASE replays the
            # absolute addresses the draw wrote, so a start address that
            # moves between her draw and her erase leaves her pixels
            # where they are and the picture carries them - one
            # character row, exactly as a world-fixed sprite should
            # (CLAUDE.md 7.8). The engine's own KARA_Y is recomputed
            # after the latch and already describes the next view.
            #
            # Measured over a saturated driver, that is an offset of 6
            # to 8 on every frame with a step in flight and 0 on every
            # frame with none, with 150-290 wrong pixels against 5-80 -
            # so the latch frame is a check about the SCROLL, which the
            # rendered sweep above already makes, and this one is about
            # HER. Sampled where a step has landed the premise holds and
            # the assertion can stay exact.
            vstep_idle(machine, sym)
            settle(machine, sym)
            machine.run_frames(2)
            sync_to_vsync(machine, sym)
            st = state(machine, sym)
            if prev is None:
                prev = st
                continue
            # THE BAR IS PART OF THE PICTURE and it is on row 23, so
            # without it the first row that differs from the tilemap is
            # the bar's and not hers (CLAUDE.md 7.8).
            bare = expected_pens(overlay_hud(
                expected_screen(tiles, level_map, st[0], st[1], st[2]),
                st[0], st[8], st[9]), st[0])
            fb = machine.framebuffer()
            rows = [y for y, row in enumerate(bare)
                    if any(fb[(y0 + y) * FB_W + 64 + x * 4] != pen_to_hw[p]
                           for x, p in enumerate(row))]
            # IT IS THIS SAMPLE'S KARA AND NOT THE ONE BEFORE IT, and
            # that changed when PLAYER_TO_SCREEN moved to the END of the
            # second sweep (CLAUDE.md 7.8). Her screen position used to
            # be worked out in the MIDDLE of a frame, so the draw on the
            # glass was made from the value the PREVIOUS sample held;
            # worked out at the end of the frame, it is already the
            # value that draw used by the time the next sample reads it.
            # Measured over 13 consecutive samples of a saturated
            # vertical driver: this sample's Kara gives an offset of 0
            # on every one, and the previous sample's gives -8 on
            # exactly the frames KARA_Y changed - which is the "two
            # Karas" signature being manufactured by the test.
            # THE PAIRING IS CHOSEN BY THE PICTURE, not assumed, and
            # that is what this check got wrong rather than the engine.
            # Two things made a fixed pairing undecidable:
            #
            # PLAYER_TO_SCREEN moved to the END of the second sweep
            # (CLAUDE.md 7.8), so her screen position is worked out
            # after the frame rather than in the middle of it; and on a
            # frame the CRTC latches a vertical step her pixels move
            # with the picture, which is what a world-fixed sprite is
            # FOR - the erase replays absolute addresses, so the
            # displayed sweep shows her against the view she was drawn
            # into and the engine's own KARA_Y already describes the
            # next one.
            #
            # So the model is built both ways and the one the sweep
            # actually shows is the one that reproduces the WHOLE
            # PICTURE; her offset is then asserted under that. It cannot
            # pass vacuously: the mismatch of the chosen pairing is
            # printed, and a build that drew her a character row out of
            # place would have no pairing that reproduces the picture at
            # all - which is the "two Karas" this exists for.
            best = None
            for cand in (st, prev):
                clip = kara_clip(blobs[cand[7]], cand[5], cand[4])
                # CULLED, OR PAST THE BOTTOM AND READ AS ABOVE THE TOP.
                # KARA_Y is an unsigned screen line and 192-255 is the
                # hidden band (CLAUDE.md 8.2), so a sample down there is
                # a reading of where she is NOT.
                if clip is None or cand[4] >= SCR_LINES:
                    continue
                pens = expected_pens(model(tiles, level_map, blobs, st,
                                           True, kara_st=cand), st[0])
                wrong = render_mismatch(machine, pens, pen_to_hw, y0)
                off = (rows[0] - first_opaque(blobs, cand[5], cand[7], clip)
                       if rows else None)
                whole = clip[1] == 0 and clip[2] == len(blobs[cand[7]][cand[5]][1])
                if best is None or wrong < best[0]:
                    best = (wrong, off, cand is st, cand[4], cand[5],
                            clip[0], clip[2], whole)
            if best is None or best[1] is None:
                prev = st
                continue
            (tops if best[7] else clipped).add(best[1])
            worst_pic = max(worst_pic, best[0])
            samples.append((best[3], best[4], "cur" if best[2] else "prev",
                            best[5], best[6], "whole" if best[7] else "CLIP",
                            rows[0] if rows else None, best[0], best[1]))
            prev = st
        seen = sorted(o for o in tops if o is not None)
        cut = sorted(o for o in clipped if o is not None)
        print(f"    {name:<14} rendered top minus KARA_Y: {seen}"
              + (f"   (clipped at the bottom: {cut})" if cut else ""))
        print("      pick   KY  cel  clip0  ndraw  state  rendered  wrong  offset")
        for ky, cel, pick, c0, nd, st_, r0, wrong, off in samples:
            print(f"      {pick:>4}  {ky:>3}  {cel:>3}  {c0:>5}  {nd:>5}  "
                  f"{st_:>5}  {str(r0):>8}  {wrong:>5}  {str(off):>6}")
        # Her screen line MOVES during a vertical scroll - she holds a world
        # position and the camera travels under her. What must not move is
        # the offset between where the engine says she is and where she is
        # actually drawn. When SCROLL ran ahead of the CRTC latch this took
        # two values 8 apart: the "two Karas".
        #
        # A WHOLE CHARACTER ROW IS THE FAULT AND ONE LINE IS THE MODEL.
        # "Where she starts" is asked two different ways here: rows[0] is
        # the first line whose PIXELS differ from the background, and
        # first_opaque is the first line the blob STORES A SPAN for - and
        # a stored span can be wholly transparent, so on some cels the
        # two are a line apart. Her topmost line is one pixel of the top
        # of her head, three on the next and five on the one after, so
        # there is no threshold that separates them either. The spread is
        # what is asserted, because the spread is what the bug was.
        check(f"Kara is drawn where the engine says she is, through a {name} step",
              seen and max(seen) - min(seen) <= 1 and -1 <= seen[0] <= 1,
              f"offsets seen {seen}, want them within one line of each other "
              f"and of zero - a character row apart is the fault")
        # ... AND WHERE SHE RUNS PAST THE BOTTOM, THE RESIDUE IS BOUNDED
        # AND MEASURED. This suite is the only place it shows, because
        # only this driver takes her there. What was not written down is
        # WHEN it starts: measured here, the engine puts her exactly
        # where it says while 45 or more of her 61 drawn lines fit, and
        # from 37 down it places her up to seven lines low. Module 6d
        # is the X clip and does not touch this - the bound is what
        # stops the OTHER axis quietly getting worse (CLAUDE.md 8.2).
        check(f"... and the bottom clip's residue is at most a row, {name}",
              all(abs(o) <= 8 for o in cut),
              f"clipped offsets {cut}, against a character row of 8 - "
              f"the bottom clip's residue, not the X clip's "
              f"(CLAUDE.md 8.2)")
        # ... AND SHE REALLY TRAVELLED, which is this check's control:
        # parked off the display at the end of the view's travel every
        # sample reads the same nothing, and "one offset, and it is
        # zero" is then true of a measurement that measured nothing.
        span = ({s[0] for s in samples} if samples else set())
        check(f"... and she crossed the picture while {name} scrolled",
              len(samples) >= 6 and max(span, default=0) - min(span, default=0) >= 24,
              f"{len(samples)} usable samples over KARA_Y "
              f"{min(span, default=0)}..{max(span, default=0)}")
    machine.poke(sym["CAMERA_V"], camera_v)      # ... and give it back

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
            (vstep_idle if phase else pump_h)(machine, sym)
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

    column_sweep(machine, sym)

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(fails))
        return 1
    print("Module 4 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
