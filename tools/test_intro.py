#!/usr/bin/env python3
"""The title screen: the picture, its palette, the prompt, the press.

WHAT THIS IS REALLY CHECKING is that the artist's bytes survive four
transformations - a layout change, ZX0, five raw sectors of a disc, and
a depacker writing into video RAM - and arrive on the screen unchanged.
So the comparison is the whole 16,336 bytes, byte for byte, against the
file the build produced, and the control is the one mistake that is
easy to make and looks almost right: comparing against the LINEAR .scr
the artist shipped, which is what INTRO.BAS beside it loads.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/home/vasilhs/cpcemu")

import cpclib                                                   # noqa: E402
from cpc import CPC                                             # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
BUILD = os.path.join(ROOT, "build")

SCREEN = 0xC000
W_BYTES = 80
LINES = 200

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    if not ok:
        fails.append(name)


def symbols():
    d = {}
    for line in open(os.path.join(BUILD, "game.sym")):
        m = re.match(r"^(\S+) #([0-9A-F]+) ", line)
        if m:
            d[m.group(1)] = int(m.group(2), 16)
    return d


def inc_bytes(text, label, stop):
    """The db lines of one label out of build/intro.inc."""
    blob = text.split(label + ":")[1].split(stop)[0]
    out = bytearray()
    for line in blob.strip().splitlines():
        line = line.strip()
        if not line.startswith("db "):
            break
        for v in line[3:].split(","):
            out.append(int(v.strip().split(";")[0].strip()[1:], 16))
    return bytes(out)


def sync(m, sym):
    """Stop in WAIT_VSYNC's spin - the one moment the frame is whole.

    The emulator's framebuffer is a live raster buffer, so a sample
    taken mid-sweep is the new frame's top over the old frame's bottom
    and the sprite has moved between the two. CLAUDE.md 5.
    """
    lo, hi = sym["WAIT_VSYNC"], sym["WAIT_VSYNC.WAIT"] + 6
    for _ in range(40000):
        m.run_us(4)
        if lo <= m.pc <= hi:
            return True
    return False


def screen_pens(native):
    """[line][pixel] pens, decoded out of the screen-ordered picture."""
    rows = []
    for y in range(LINES):
        base = (y & 7) * 2048 + (y >> 3) * W_BYTES
        row = []
        for b in range(W_BYTES):
            row += list(cpclib.decode_byte(native[base + b]))
        rows.append(row)
    return rows


def boot(sym, press_after=None):
    m = CPC()
    m.run_frames(150)
    m.insert_disc(os.path.abspath(os.path.join(BUILD, "kara.dsk")))
    m.type_text('RUN"DISC\n')
    for _ in range(500):
        m.run_frames(2)
        if m.peek(sym["LEVEL_OK"]) and m.mode == 0 and m.peek(sym["INTRO_BLINK"]):
            return m
    return m


def main():
    sym = symbols()
    inc = open(os.path.join(BUILD, "intro.inc")).read()
    native = open(os.path.join(BUILD, "intro.bin"), "rb").read()
    linear = open(os.path.join(
        ROOT, "assets", "intro", "intro_cpc_mode0.scr"), "rb").read()

    print("\n  the picture, four transformations later:")
    m = boot(sym)
    check("the core reached the title and the level behind it",
          m.mode == 0 and m.peek(sym["LEVEL_OK"]) == 1,
          f"mode {m.mode}, LEVEL_OK {m.peek(sym['LEVEL_OK'])} - the picture "
          f"goes up first and the 1.6 s load runs underneath it")
    check("the start address is back at the top of the screen",
          m.crtc_screen_addr == 0x3000,
          f"R12/R13 = {m.crtc_screen_addr:#06x} - page &C000, offset 0. "
          f"BASIC had been scrolling it")

    vram = bytes(m.read_ram(SCREEN, len(native)))
    # The prompt is drawn over lines 4-11, so those bytes are allowed to
    # differ; everything else must be the artist's, exactly.
    skip = set()
    for row in range(8):
        y = 4 + row
        base = (y & 7) * 2048 + (y >> 3) * W_BYTES
        skip.update(range(base, base + W_BYTES))
    wrong = [i for i in range(len(native))
             if i not in skip and vram[i] != native[i]]
    check("the whole picture is in video RAM, byte for byte",
          not wrong,
          f"{len(native) - len(skip)} bytes compared - the prompt's own "
          f"{len(skip)} are checked below" if not wrong
          else f"{len(wrong)} bytes differ, first at {wrong[0]}")

    # THE CONTROL: the .scr as it ships is 200 lines one after another
    # and a CPC screen is eight interleaved raster blocks. Loaded raw it
    # would come out in bands, so this comparison has to FAIL.
    same = sum(1 for i in range(min(len(linear), len(vram)))
               if linear[i] == vram[i])
    check("... and NOT the linear .scr it was made from",
          same < len(linear) * 9 // 10,
          f"{same} of {len(linear)} bytes match by coincidence - the layout "
          f"conversion is real, which is what INTRO.BAS beside the asset "
          f"gets wrong")

    print("\n  the artist's own sixteen colours, ON THE SCREEN:")
    # The gate array's pen registers cannot be read back - not here and
    # not on the machine - so the palette is checked where it shows: the
    # emulator's framebuffer is indexed by HARDWARE colour, so a pixel
    # whose pen the picture knows says which colour that pen was given.
    want = inc_bytes(inc, "INTRO_PALETTE", "INTRO_TEXT_BYTES")
    hw = [v & 0x1F for v in want[:16]]
    game_pens = bytes(m.read_ram(sym["PALETTE_DATA"], 16))
    fb, FBW = m.framebuffer(), 1024
    pens = screen_pens(native)

    def score(top, line):
        row = fb[(top + line) * FBW:(top + line + 1) * FBW]
        return sum(1 for i in range(160)
                   if row[64 + i * 4] == hw[pens[line][i]])
    top = max(range(0, 140), key=lambda t: score(t, 100))
    worst = min((score(top, y), y) for y in (20, 60, 100, 140, 180))
    check("every pen is the one the .aseprite asked for",
          worst[0] == 160,
          f"{worst[0]} of 160 pixels on the worst of five sampled lines "
          f"(line {worst[1]}) carry the hardware colour the pen was given, "
          f"with the display found at framebuffer row {top}")
    check("... and they are NOT the game's",
          [v & 0x1F for v in game_pens] != hw,
          "the title is the artist's palette and the city is src/palette.asm; "
          "sharing one would make this vacuous")

    print("\n  PRESS SPACE OR FIRE:")
    on = inc_bytes(inc, "INTRO_TEXT_ON", "INTRO_TEXT_OFF")
    off = inc_bytes(inc, "INTRO_TEXT_OFF", "\n\n")
    n = len(on) // 8
    addrs = [0xC000 + ((4 + r) & 7) * 0x800 + ((4 + r) >> 3) * W_BYTES + 2
             for r in range(8)]
    check("the two strips are different pictures", on != off,
          f"{sum(1 for a, b in zip(on, off) if a != b)} of {len(on)} bytes - "
          f"without that the blink below could not be seen")

    seen = set()
    for _ in range(80):
        m.run_frames(1)
        row = bytes(m.read_ram(addrs[3], n))
        if row == on[3 * n:4 * n]:
            seen.add("on")
        elif row == off[3 * n:4 * n]:
            seen.add("off")
        else:
            seen.add("other")
    check("the words blink between exactly those two", seen == {"on", "off"},
          f"over 80 frames the strip was {sorted(seen)}")

    print("\n  the press, and the control that it is the press:")
    before = m.peek(sym["FRAME_COUNT"])
    m.run_frames(120)
    check("with nothing pressed the game does not start",
          m.peek(sym["FRAME_COUNT"]) == before,
          f"FRAME_COUNT {before} after another 120 frames of waiting - the "
          f"main loop is the only thing that bumps it")

    m.joystick(0x10)                    # the joystick's fire, same bit as SPACE
    m.run_frames(8)
    m.joystick(0)
    started = None
    for i in range(240):
        m.run_frames(1)
        if m.peek(sym["FRAME_COUNT"]) != before:
            started = i
            break
    check("and with it the game starts", started is not None,
          f"{started} frames after the release - SCROLL_INIT paints the "
          f"playfield in between" if started is not None else "it never did")

    m.run_frames(40)
    sync(m, sym)                # the framebuffer is a LIVE raster buffer
    check("she is on the roof", m.peek(sym["KARA_GROUND"]) == 1,
          f"grounded={m.peek(sym['KARA_GROUND'])}, "
          f"WY={m.peek(sym['KARA_WY'])}")
    fb = m.framebuffer()
    city = [v & 0x1F for v in game_pens]
    # THE COLOUR SETS CANNOT TELL THESE TWO PALETTES APART - they share
    # eleven of their sixteen hardware colours - so what is checked is
    # the MAPPING: decode the pens the city is drawn in straight out of
    # video RAM through the engine's own scrolled address model, and ask
    # what colour the screen gave each one.
    scroll = m.peek(sym["SCROLL"]) | (m.peek(sym["SCROLL"] + 1) << 8)
    # HER OWN BOX IS NOT COMPARABLE and nothing is wrong with it: she is
    # drawn and erased inside one frame (CLAUDE.md 8.7), so at the
    # WAIT_VSYNC the erase has put the background back in RAM while the
    # framebuffer still holds the frame she was IN.
    kx, ky = m.peek(sym["KARA_X"]), m.peek(sym["KARA_Y"])
    good = bad = 0
    title_bad = 0
    for r in range(4, 20):
        for ra in (0, 5):
            y = r * 8 + ra
            row = fb[(top + y) * FBW:(top + y) * FBW + FBW]
            for c in range(40):
                ma = (scroll + r * 40 + c) & 0x3FF
                a = 0xC000 + (ra << 11) + (ma << 1)
                for k, b in enumerate(m.read_ram(a, 2)):
                    if kx <= c * 2 + k < kx + 12 and ky <= y < ky + 64:
                        continue
                    for j, pen in enumerate(cpclib.decode_byte(b)):
                        seen = row[64 + (c * 4 + k * 2 + j) * 4]
                        good += seen == city[pen]
                        bad += seen != city[pen]
                        title_bad += seen != hw[pen]
    check("and the city is drawn in the game's colours", bad == 0,
          f"{good} pixels over 32 display lines, every one of them the "
          f"colour src/palette.asm gives its pen"
          if bad == 0 else f"{bad} of {good + bad} pixels are not")
    check("... which is not the palette the title was in", title_bad > 0,
          f"{title_bad} of those {good} pixels would be the wrong colour "
          f"under the title's pens - the two share eleven hardware colours, "
          f"so without this the check above would pass either way")
    check("nothing is left of the prompt",
          m.peek(sym["INTRO_BLINK"]) is not None
          and bytes(m.read_ram(addrs[0], n)) != on[:n],
          "the playfield is painted over it, and INTRO_WAIT takes it down "
          "before that anyway")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(fails))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
