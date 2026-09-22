#!/usr/bin/env python3
"""The map's shape is the LEVEL's, and this is what says so.

MAP_W was 128 and MAP_H 16 in the source and the City is the only level
that has ever existed, so every mask, every shift run and every bound in
the engine held a number nobody had ever changed. The shape comes out of
`level_<n>.lvl` now and is patched into those immediates at
MAP_INSTALL (src/mapshape.asm), which raises exactly the question
CLAUDE.md 10 raises about a raster gate: NOT "is the number right" but
"DOES CHANGING IT CHANGE ANYTHING".

So the order here is the order of how much each step could be fooled by:

  1. the bytes         - every patched immediate against an independent
                         computation from W and H, for all three shapes
  2. the refusals      - the shapes that are not shapes, and the one that
                         IS 2,048 bytes and is still refused
  3. THE ADDRESSING    - MAP_CELL and ENT_CELL_OF called from a DI stub
                         over a swept world, against MAP_ADDR + row*W +
                         col, which is the format and not the engine
  4. THE PICTURE       - a 32x64 level built here, installed on the
                         machine, and 15,360 bytes of video RAM against
                         a model that knows only W, H and the tiles

and the negative control is the whole of it with MAP_SHAPE_SET poked to
RET: the engine then keeps the City's shape, every check above 1 still
passes on the City, and the vertical level draws the wrong cells.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/home/vasilhs/cpcemu")

from bench import boot, symbols                             # noqa: E402
import test_module4 as M4                                   # noqa: E402

ROOT = os.path.join(HERE, "..")
MAP_ADDR = 0xA000
MAP_BYTES = 2048
SCR_CHARS, SCR_CHAR_ROWS = 40, 24
KARA_W_BYTES, KARA_ART_X = 12, 3
STUB = 0x9200
LVL_HEADER = 21
TILE_BYTES = 64

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


# ---------------------------------------------------------------------
# What every site should hold, worked out here from W and H alone. This
# is the independent half: src/mapshape.asm's own table is three rows of
# `db` and comparing the engine against it would be comparing the engine
# with itself.
# ---------------------------------------------------------------------
def shape_of(w, h):
    log_w = w.bit_length() - 1
    return {
        "PM_MC_COLM": bytes([w - 1]),
        "PM_TS_COLM": bytes([w - 1]),
        "PM_DC_COLM": bytes([w - 1]),
        "PM_DR_COLM": bytes([w - 1]),
        "PM_RN_COLM": bytes([w - 1]),
        "PM_CR_COLM": bytes([w - 1]),
        "PM_EC_COLM": bytes([w - 1]),
        "PM_RP_COLM": bytes([w - 1]),
        "PM_TS_COMP": bytes([(256 - w) & 255]),
        "PM_DC_COMP": bytes([(256 - w) & 255]),
        "PM_DR_COMP": bytes([(256 - w) & 255]),
        "PM_RN_COMP": bytes([(256 - w) & 255]),
        "PM_EC_COMP": bytes([(256 - w) & 255]),
        "PM_TS_ROWM": bytes([h - 1]),
        "PM_DC_ROWM": bytes([h - 1]),
        "PM_DR_ROWM": bytes([h - 1]),
        "PM_EC_ROWM": bytes([h - 1]),
        "PM_MC_ROWHI": bytes([(h - 1) >> 4]),
        "PM_DC_STEP": bytes([w & 255]),
        "PM_MD_STEP": bytes([w & 255]),
        "PM_RP_PAGE": bytes([256 // w - 1]),
        "PM_PX_VIEW": bytes([w * 2 - SCR_CHARS]),
        "PM_CD_VIEW": bytes([w * 2 - SCR_CHARS]),
        "PM_VT_VIEW": bytes([w * 2 - SCR_CHARS]),
        "PM_VT_VIEW1": bytes([w * 2 - SCR_CHARS + 1]),
        "PM_CV_VCR": bytes([(h * 16 - SCR_CHAR_ROWS * 8) // 8]),
        "PM_VT_VCR": bytes([(h * 16 - SCR_CHAR_ROWS * 8) // 8]),
        "PM_VT_VCR1": bytes([(h * 16 - SCR_CHAR_ROWS * 8) // 8 + 1]),
        "PM_KARA_XMAX": (w * 4 - KARA_W_BYTES + KARA_ART_X).to_bytes(2, "little"),
        # THE RUNS, AND THEY ARE A FIXED LENGTH WHATEVER THE SHAPE. A
        # rotation this shape does not want is a NOP, and a NOP is one
        # byte and 4 T exactly like the `rrca` it stands in for - so the
        # slot costs the same for every shape and there is no branch.
        "PM_TS_ROT": run(0x0F, 8 - log_w, 4),
        "PM_DC_ROT": run(0x0F, 8 - log_w, 4),
        "PM_DR_ROT": run(0x0F, 8 - log_w, 4),
        "PM_EC_ROT": run(0x0F, 8 - log_w, 4),
        "PM_RP_ADD": run(0x87, 8 - log_w, 4),
        "PM_RP_ROT": run(0x07, 8 - log_w, 4),
        "PM_SCALE": (b"\0\0\0\0" * (3 - (log_w - 4))
                     + b"\xcb\x23\xcb\x12" * (log_w - 4)),
    }


def run(op, n, slots):
    return bytes([0] * (slots - n) + [op] * n)


SITES = sorted(shape_of(128, 16))


def snap(m, sym):
    want = shape_of(128, 16)
    return {k: bytes(m.peek(sym[k] + i) for i in range(len(want[k])))
            for k in SITES}


def call(m, sym, target, setup=b""):
    """di : <setup> : call target : jr $ - and stop on the spin."""
    code = b"\xf3" + setup + bytes([0xCD, target & 255, target >> 8, 0x18, 0xFE])
    m.write_ram(STUB, code)
    m.set_pc(STUB)
    end = STUB + len(code) - 2
    for _ in range(600000):
        m.run_us(1)
        if m.pc == end:
            return True
    return False


def install(m, sym, w, h):
    """Put a shape in the header and re-run the loader."""
    m.poke(sym["LEVEL_LVL"] + 5, w & 255)
    m.poke(sym["LEVEL_LVL"] + 6, w >> 8)
    m.poke(sym["LEVEL_LVL"] + 7, h & 255)
    m.poke(sym["LEVEL_LVL"] + 8, h >> 8)
    call(m, sym, sym["MAP_INSTALL"])


FLOOR_ROW = 20                  # ... of a 64-row map
FLOOR_TILE = 1                  # and the only tile this level calls solid


def pattern(w, h, floor=False):
    """A map with no repeat along either axis in a screen's window.

    A level of one tile says nothing: every addressing fault in the
    engine resolves to SOME cell, and if its neighbours look the same
    the picture is right by accident. Stepping by 7 along the row and
    by 13 down means a cell mistaken for the one beside it or the one
    above it is a different tile.

    `floor` lays one row of FLOOR_TILE across it, which is the only
    thing in this level she can stand on - see tile_flags(). One
    uniform row of sixty-four is what it costs to have a walk that is
    not a walk into a wall.
    """
    n = os.path.getsize(os.path.join(
        ROOT, "build", "levels", "level1_city", "citytiles.bin")) // TILE_BYTES
    m = bytearray((row * 13 + col * 7) % n
                  for row in range(h) for col in range(w))
    if floor:
        for col in range(w):
            m[FLOOR_ROW * w + col] = FLOOR_TILE
    return bytes(m)


def tile_flags():
    """Nothing is solid but the floor, so the walk is a walk."""
    f = bytearray(256)
    f[FLOOR_TILE] = 1                       # TA_SOLID
    return bytes(f)


def level_file(w, h, level_map, y=320):
    """docs/editor.md 9.2's bytes, written by hand.

    Written here and not imported from tools/make_level.py, because a
    level built by the generator and read by the engine is one writer
    against one reader; this is a second writer, and the City's own
    file is what says the two agree (tools/test_format.py).
    """
    ents = bytes([0,                        # EK_PLAYER_START
                  80 & 255, 80 >> 8,        # x, world pixels
                  y & 255, y >> 8,          # y, the BASE of the hitbox
                  1,                        # EF_ACTIVE
                  0, 0])
    off_map = LVL_HEADER
    off_ent = off_map + MAP_BYTES
    end = off_ent + len(ents)
    return (b"LV" + bytes([1, 1, 0])
            + w.to_bytes(2, "little") + h.to_bytes(2, "little")
            + bytes([1, 1, 0, 0])
            + off_map.to_bytes(2, "little") + off_ent.to_bytes(2, "little")
            + end.to_bytes(2, "little") + end.to_bytes(2, "little")
            + level_map + ents)


def tile_bank(m, sym):
    """The level's tiles as they really sit in bank C4, scratch and all."""
    shipped = open(os.path.join(ROOT, "build", "levels", "level1_city",
                                "citytiles.bin"), "rb").read()
    scratch = M4.read_tile_bank(m, sym, 1024, 0x7C00)
    return shipped + bytes(0x7C00 - 0x4000 - len(shipped)) + scratch


def enter_level(m, sym):
    """Install the level and go BACK INTO THE LOOP, not into a spin.

    A level installed from a DI stub is a still picture, and a still
    picture only exercises DRAW_PLAYFIELD. The incoming column, the
    incoming row and the map steps that walk between cells are the
    scrolling engine, and the only way to drive them is to let the game
    run on the level.
    """
    loop = sym["SCROLL_DEMO.LOOP"]
    m.write_ram(STUB, bytes([0xF3,
                             0xCD, sym["SCROLL_INIT"] & 255,
                             sym["SCROLL_INIT"] >> 8,
                             0xFB,
                             0xC3, loop & 255, loop >> 8]))
    m.set_pc(STUB)
    m.run_frames(8)


def main():
    sym = symbols()
    m = boot(sym, scroll=True)

    # -----------------------------------------------------------------
    print("\n  the shape the City installed:")
    city = snap(m, sym)
    want = shape_of(128, 16)
    wrong = [k for k in SITES if city[k] != want[k]]
    check("every patched site holds the City's own shape", not wrong,
          f"{len(SITES)} sites, {len(wrong)} disagreeing"
          + (": " + ", ".join(wrong) if wrong else ""))
    now = bytes(m.peek(sym["SHAPE_NOW"] + i) for i in range(12))
    check("... and SHAPE_NOW says which shape that was",
          now[0] == 127 and now[2] == 15,
          f"col mask &{now[0]:02X}, row mask &{now[2]:02X}")

    # -----------------------------------------------------------------
    print("\n  the shapes it takes:")
    for w, h in ((32, 64), (64, 32), (128, 16)):
        install(m, sym, w, h)
        got, want = snap(m, sym), shape_of(w, h)
        wrong = [k for k in SITES if got[k] != want[k]]
        check(f"{w}x{h} patches every site", not wrong,
              f"{len(SITES)} sites"
              + ("" if not wrong else ", wrong: "
                 + ", ".join(f"{k} {got[k].hex()} want {want[k].hex()}"
                             for k in wrong[:4])))

    # -----------------------------------------------------------------
    # AND THE REFUSALS, WHICH ARE THREE DIFFERENT REFUSALS. A width that
    # is not a power of two, a product that is not 2,048, and a shape
    # that is BOTH and is still refused because 16 tiles is 128 pixels
    # against a 160-pixel display.
    print("\n  ... and the ones it refuses:")
    for w, h, why in ((64, 16, "64 x 16 is 1,024 bytes, not 2,048"),
                      (96, 32, "96 is not a power of two, and 96 x 32 "
                               "is 3,072"),
                      (16, 128, "2,048 bytes, and 128 pixels of map "
                                "against a 160-pixel display")):
        install(m, sym, 128, 16)
        before = snap(m, sym)
        install(m, sym, w, h)
        after = snap(m, sym)
        check(f"{w}x{h} is refused", before == after, why)
    install(m, sym, 128, 16)

    # -----------------------------------------------------------------
    # THE ADDRESSING, AND THIS ONE HAS NO ENGINE IN IT. MAP_CELL is
    # called from a DI stub with a world position in HL and DE, and what
    # it returns is compared against the format's own statement of where
    # a cell is: MAP_ADDR + row * W + col.
    print("\n  MAP_CELL over a swept world, against MAP_ADDR + row*W + col:")
    for w, h in ((128, 16), (64, 32), (32, 64)):
        install(m, sym, w, h)
        bad, n, first = 0, 0, None
        for bx in range(0, w * 4, 7):           # world byte column
            for wy in range(0, h * 16, 23):     # world pixel row
                setup = bytes([0x21, bx & 255, bx >> 8,     # ld hl,bx
                               0x11, wy & 255, wy >> 8])    # ld de,wy
                code = (b"\xf3" + setup
                        + bytes([0xCD, sym["MAP_CELL"] & 255,
                                 sym["MAP_CELL"] >> 8,
                                 0x22, 0x80, 0x93,          # ld (&9380),hl
                                 0x18, 0xFE]))
                m.write_ram(STUB, code)
                m.set_pc(STUB)
                end = STUB + len(code) - 2
                for _ in range(200000):
                    m.run_us(1)
                    if m.pc == end:
                        break
                got = m.peek(0x9380) | (m.peek(0x9381) << 8)
                row = (wy >> 4) & (h - 1)
                col = (bx >> 2) & (w - 1)
                exp = MAP_ADDR + row * w + col
                n += 1
                if got != exp:
                    bad += 1
                    if first is None:
                        first = (bx, wy, got, exp)
        check(f"{w}x{h}: MAP_CELL lands on the right cell", bad == 0,
              f"{n} placements, {bad} wrong"
              + ("" if not bad else f"; first at byte {first[0]}, line "
                                    f"{first[1]}: &{first[2]:04X} want "
                                    f"&{first[3]:04X}"))
    # -----------------------------------------------------------------
    # AND THEN THE PICTURE, WHICH IS THE ONE THAT CANNOT BE FOOLED BY
    # ARITHMETIC. A 32x64 level is built here - the format's own bytes,
    # written by hand, which makes this a second writer as well as a
    # second reader - installed through SCROLL_INIT on the machine, and
    # every byte of the playfield compared against a model that knows
    # the tiles, W and H and nothing else about the engine.
    print("\n  a 32x64 level, drawn on the machine:")
    for w, h in ((32, 64), (128, 16)):
        m = boot(sym, scroll=True)
        tiles = tile_bank(m, sym)
        level_map = pattern(w, h)
        m.write_ram(sym["LEVEL_LVL"], level_file(w, h, level_map))
        ok = call(m, sym, sym["SCROLL_INIT"])
        st = (m.peek(sym["SCROLL"]) | (m.peek(sym["SCROLL"] + 1) << 8),
              m.peek(sym["WORLD_X"]), m.peek(sym["WORLD_CR"]))
        got = bytes(m.read_ram(MAP_ADDR, MAP_BYTES))
        check(f"{w}x{h}: the map is installed", ok and got == level_map,
              f"{sum(1 for a, b in zip(got, level_map) if a != b)} of "
              f"{MAP_BYTES} cells differ")
        M4.MAP_W, M4.MAP_H = w, h
        want = M4.expected_screen(tiles, level_map, *st)
        vram = m.read_ram(0xC000, 0x4000)
        bad = sum(1 for a, v in want.items() if vram[a - 0xC000] != v)
        check(f"{w}x{h}: the playfield is the map",
              bad == 0,
              f"{bad} of {len(want)} bytes wrong, view scroll={st[0]} "
              f"world=({st[1]},{st[2]})")
        M4.MAP_W, M4.MAP_H = 128, 16

    # -----------------------------------------------------------------
    # AND THEN IT HAS TO SCROLL, which is a different half of the
    # engine: DRAW_PLAYFIELD paints cells and the scroll paints an
    # incoming COLUMN and an incoming ROW, and walks between cells with
    # MAP_ROW_DOWN and ROW_NEXT_TILE rather than by looking each one up.
    print("\n  ... and it scrolls, on all three axes:")
    m = boot(sym, scroll=True)
    tiles = tile_bank(m, sym)
    blobs = M4.load_blobs()
    level_map = pattern(32, 64, floor=True)
    m.write_ram(sym["LEVEL_TILEFLAGS"], tile_flags())
    m.write_ram(sym["LEVEL_LVL"], level_file(32, 64, level_map,
                                             y=FLOOR_ROW * 16))
    enter_level(m, sym)
    m.poke(sym["ENEMY_LIVE"], 0)                # no drones in this level
    M4.MAP_W, M4.MAP_H = 32, 64
    start = m.peek(sym["WORLD_X"]), m.peek(sym["WORLD_CR"])
    seen = [start]
    for label, joy, req, frames in (("standing still", 0, 0, 16),
                                    ("walking right", 0x08, 0, 60),
                                    ("scrolling down", 0, 1, 16),
                                    ("scrolling back up", 0, 2, 16)):
        for _ in range(frames):
            m.joystick(joy)
            if req:
                m.poke(sym["V_REQUEST"], req)
            M4.next_frame_top(m, sym)
        m.joystick(0)
        m.poke(sym["V_REQUEST"], 0)
        M4.settle(m, sym)
        st = M4.state(m, sym)
        want = M4.model(tiles, level_map, blobs, st, with_kara=False)
        vram = m.read_ram(0xC000, 0x4000)
        bad = sum(1 for a, v in want.items() if vram[a - 0xC000] != v)
        seen.append((st[1], st[2]))
        check(f"32x64: the playfield is the map, {label}", bad == 0,
              f"{bad} of {len(want)} bytes wrong, view scroll={st[0]} "
              f"world=({st[1]},{st[2]})")
    # AND THE AXES HAVE TO HAVE MOVED, or three of those four checks
    # are the still one measured again - and the EXTREMES are what says
    # so, not the last sample, because the last phase deliberately puts
    # the view back where it started.
    #
    # ACROSS, WHAT IT REACHES IS THE SHAPE'S OWN BOUND: the camera stops
    # at W * 2 - SCR_CHARS, which is 24 on a 32-wide map and 216 on the
    # City's - so a walk that ran to 24 and stopped is PM_PX_VIEW
    # holding the patched number, measured rather than read back.
    across = [x for x, _ in seen]
    down = [y for _, y in seen]
    limit = 32 * 2 - SCR_CHARS
    check("... and both axes moved under it, across to the shape's own bound",
          max(across) == limit and max(down) - min(down) >= 8,
          f"the view went from {seen[0]} across to {max(across)} of a bound "
          f"of {limit}, and down {min(down)}..{max(down)} of 104")
    M4.MAP_W, M4.MAP_H = 128, 16

    # -----------------------------------------------------------------
    # THE NEGATIVE CONTROL, AND IT IS THE WHOLE POINT. With
    # MAP_SHAPE_SET returning at once the engine keeps whatever shape
    # its immediates were last patched to - the City's, out of the
    # build - and every check above that is about the City still
    # passes. What must NOT pass is the vertical level: a 32-wide map
    # read with a 128-wide map's masks is a picture of the wrong cells.
    print("\n  ... and with MAP_SHAPE_SET returning at once:")
    m = boot(sym, scroll=True)
    m.poke(sym["MAP_SHAPE_SET"], 0xC9)          # RET
    tiles = tile_bank(m, sym)
    level_map = pattern(32, 64)
    m.write_ram(sym["LEVEL_LVL"], level_file(32, 64, level_map))
    call(m, sym, sym["SCROLL_INIT"])
    st = (m.peek(sym["SCROLL"]) | (m.peek(sym["SCROLL"] + 1) << 8),
          m.peek(sym["WORLD_X"]), m.peek(sym["WORLD_CR"]))
    M4.MAP_W, M4.MAP_H = 32, 64
    want = M4.expected_screen(tiles, level_map, *st)
    vram = m.read_ram(0xC000, 0x4000)
    bad = sum(1 for a, v in want.items() if vram[a - 0xC000] != v)
    M4.MAP_W, M4.MAP_H = 128, 16
    check("the unpatched engine draws the wrong cells", bad > 1000,
          f"{bad} of {len(want)} bytes wrong - the same level, read "
          f"with the City's masks")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
