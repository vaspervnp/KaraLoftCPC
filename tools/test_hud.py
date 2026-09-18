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
AMMO_CELLS = 7                           # ... and the rounds straight after
AMMO_COL = CELLS                         # character 6
AMMO_X0 = AMMO_COL * 4                   # Mode 0 pixel 24 of 160
ROUNDS = AMMO_CELLS * 2                  # 14, both magazines
BUL_MAX = ROUNDS                         # ... and what one reload is worth
CLIPS_COL = AMMO_COL + AMMO_CELLS        # character 13: the spare magazines
CLIPS_X0 = CLIPS_COL * 4

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    if not ok:
        fails.append(name)


def digits_from_inc():
    """HUD_DIGITS is one label and ten cels, with a comment before each."""
    text = open(os.path.join(BUILD, "hud_art.inc")).read()
    body = [ln for ln in text.split("HUD_DIGITS:")[1].splitlines()
            if ln.strip().startswith("db ")]
    out = {}
    for d in range(10):
        rows = []
        for ln in body[d * LINES:(d + 1) * LINES]:
            row = []
            for v in ln.strip()[3:].split(","):
                row += list(cpclib.decode_byte(int(v.strip()[1:], 16)))
            rows.append(row)
        out[f"HUD_DIGIT_{d}"] = rows
    return out


def cells_from_inc(names=("HUD_CELL_FULL", "HUD_CELL_EMPTY")):
    """The 4x8 cells the build exported, as pen rows."""
    text = open(os.path.join(BUILD, "hud_art.inc")).read()
    out = {}
    for name in names:
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


INV_BYTES = 12                  # six cells: icon, count, icon, count


def inv_from_inc():
    """The item icons and the digits as RAW BYTES, out of the build.

    Bytes and not pens, because this run is copied into video RAM whole
    - twelve consecutive bytes on each of eight lines - so the thing to
    compare is the thing that is copied.
    """
    text = open(os.path.join(BUILD, "hud_art.inc")).read()

    def block(label, lines):
        body = [ln for ln in text.split(label + ":")[1].splitlines()
                if ln.strip().startswith("db ")]
        out = []
        for ln in body[:lines]:
            out += [int(v.strip()[1:], 16) for v in ln.strip()[3:].split(",")]
        return out

    art = {n: block("HUD_ICON_" + n, LINES)
           for n in ("KEY", "KEY_DARK", "COIN", "COIN_DARK")}
    art["DIGITS"] = block("HUD_DIGITS", LINES * 10)
    return art


def inv_expect(art, keys, coins):
    """What the six cells must hold: an icon a kind and a count beside
    it, lit while she has one and the same silhouette in the dark while
    she has not - capped at nine, which is what one character holds."""
    out = []
    for y in range(LINES):
        for count, name in ((keys, "KEY"), (coins, "COIN")):
            lit = art[name if count else name + "_DARK"]
            out += lit[y * 4:y * 4 + 4]
            d = min(count, 9) * 16 + y * 2
            out += art["DIGITS"][d:d + 2]
    return out


def inv_on_screen(m, sym):
    """The six cells as they stand in video RAM, through the engine's
    own circular address model (CLAUDE.md 6.4)."""
    sc = m.peek(sym["SCROLL"]) | (m.peek(sym["SCROLL"] + 1) << 8)
    base = (sc + sym["HUD_INV_BASE"]) & 0x3FF
    out = []
    for r in range(LINES):
        for b in range(INV_BYTES):
            w = (base + (b >> 1)) & 0x3FF
            out.append(m.peek(0xC000 + ((r & 7) << 11) + w * 2 + (b & 1)))
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


def ammo_expect(spent, pips):
    """The 28x8 pen grid the rounds should be showing.

    THE ROUNDS GO OUT FROM THE LEFT, so the row is spent//2 empty cells,
    a half-spent one when the count is odd, and full cells after it -
    which is the engine's own rule stated a second time, from the count
    rather than from the seam it keeps.
    """
    grid = []
    for y in range(LINES):
        row = []
        for c in range(AMMO_CELLS):
            lo, hi = 2 * c, 2 * c + 1
            if hi < spent:
                name = "HUD_PIP_EMPTY"
            elif lo < spent:
                name = "HUD_PIP_HALF"
            else:
                name = "HUD_PIP_FULL"
            row += pips[name][y]
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


def on_screen(m, top, want, hwpen, x0=0):
    """How many of a run's pixels are wrong in the rendered frame."""
    fb = m.framebuffer()
    bad = 0
    for y in range(LINES):
        row = fb[(top + TOP_LINE + y) * FBW:(top + TOP_LINE + y + 1) * FBW]
        for x in range(len(want[y])):
            if row[64 + (x0 + x) * 4] != hwpen[want[y][x]]:
                bad += 1
    return bad


def main():
    sym = symbols()
    for n in ("HUD_SERVICE", "HUD_ALL", "HUD_PUT", "HUD_LEVEL", "HUD_HP",
              "HUD_LAST", "HUD_LIT", "HUD_STEPS", "HUD_CELL_FULL",
              "HUD_CELL_EMPTY", "HUD_AMMO", "HUD_AMMO_PUT",
              "HUD_AMMO_SPENT", "MAG_LEFT", "MAG_RIGHT", "HUD_CLIPS",
              "HUD_CLIPS_N", "HUD_DIGITS", "AMMO_RESERVE"):
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

    # -----------------------------------------------------------------
    # THE ROUNDS, AT THE OTHER END OF THE SAME ROW.
    #
    # Fourteen pips, two to a character, going out from the LEFT as she
    # fires - which is the mirror of the bar and NOT free in the same
    # places: a run leaves the word just past its left end whichever way
    # the view goes, so the bar is free stepping right and this is free
    # stepping left (CLAUDE.md 7.8).
    # -----------------------------------------------------------------
    pips = cells_from_inc(("HUD_PIP_FULL", "HUD_PIP_HALF", "HUD_PIP_EMPTY"))
    print("\n  fourteen rounds, straight after the bar:")
    m.poke(sym["MAG_LEFT"], 7)
    m.poke(sym["MAG_RIGHT"], 7)
    m.run_frames(3)
    sync(m, sym)
    bad = on_screen(m, top, ammo_expect(0, pips), hwpen, AMMO_X0)
    check("the rounds are on the screen, next to the bar, both magazines "
          "full",
          bad == 0, f"{ROUNDS * 2 * LINES - bad} of {ROUNDS * 2 * LINES} "
          f"pixels are the artist's own bullet")

    print("\n  and they go out from the LEFT as she fires:")
    for left, right in ((7, 7), (6, 7), (4, 4), (2, 1), (0, 1), (0, 0)):
        m.poke(sym["MAG_LEFT"], left)
        m.poke(sym["MAG_RIGHT"], right)
        m.run_frames(3)
        sync(m, sym)
        spent = ROUNDS - left - right
        bad = on_screen(m, top, ammo_expect(spent, pips), hwpen, AMMO_X0)
        check(f"{left}+{right} rounds leaves {ROUNDS - spent} pips lit, "
              f"the rightmost ones", bad == 0,
              f"{bad} wrong pixels" if bad else "exactly, on the screen")

    # AND THEY STAY, which is the same property the bar has and a
    # different arithmetic: this run's vacated word is off the row
    # going LEFT and inside the picture going RIGHT.
    print("\n  and they STAY, walking both ways:")
    m.poke(sym["MAG_LEFT"], 5)
    m.poke(sym["MAG_RIGHT"], 4)
    m.run_frames(3)
    want_ammo = ammo_expect(ROUNDS - 9, pips)
    for mask, name in ((JOY_RIGHT, "RIGHT"), (JOY_LEFT, "LEFT")):
        worst, seen = 0, set()
        m.joystick(mask)
        for _ in range(90):
            m.run_frames(1)
            sync(m, sym)
            seen.add(m.peek(sym["SCROLL"]) | (m.peek(sym["SCROLL"] + 1) << 8))
            m.poke(sym["MAG_LEFT"], 5)          # the drones shoot back and
            m.poke(sym["MAG_RIGHT"], 4)         # she is not what is measured
            worst = max(worst, on_screen(m, top, want_ammo, hwpen, AMMO_X0))
        m.joystick(0)
        check(f"... walking {name}, with nine rounds left", worst == 0,
              f"{len(seen)} start addresses, worst frame {worst} wrong pixels "
              f"of {ROUNDS * 2 * LINES}")

    # THE NEGATIVE CONTROL IS THE SAME ONE THE BAR HAS: with HUD_AMMO
    # returning at once the rounds are still DRAWN - the first frame
    # draws them - and the CRTC then carries them off with the world.
    print("\n  the negative control - the rounds must be REWRITTEN:")
    m2 = boot(sym, scroll=True)
    m2.run_frames(20)
    m2.poke(sym["MAG_LEFT"], 5)
    m2.poke(sym["MAG_RIGHT"], 4)
    m2.run_frames(3)
    sync(m2, sym)
    top2 = find_top(m2, sym, expect(m2.peek(sym["PLAYER_HP"]), art, steps), hwpen)
    before = on_screen(m2, top2, want_ammo, hwpen, AMMO_X0)
    m2.poke(sym["HUD_AMMO"], 0xC9)          # RET
    worst2 = 0
    m2.joystick(JOY_RIGHT)
    for _ in range(90):
        m2.run_frames(1)
        sync(m2, sym)
        m2.poke(sym["MAG_LEFT"], 5)
        m2.poke(sym["MAG_RIGHT"], 4)
        worst2 = max(worst2, on_screen(m2, top2, want_ammo, hwpen, AMMO_X0))
    m2.joystick(0)
    check("without it the rounds slide off with the world",
          before == 0 and worst2 > 0,
          f"{before} wrong pixels with the redraw, {worst2} of "
          f"{ROUNDS * 2 * LINES} without it")

    # -----------------------------------------------------------------
    # AND ONE DIGIT AFTER THEM: HOW MANY MAGAZINES THE RESERVE IS WORTH.
    #
    # A reload takes BUL_MAX rounds out of AMMO_RESERVE (bullets.asm),
    # so the reserve IS a number of magazines. The expectation is
    # computed here from the reserve rather than read out of
    # HUD_CLIPS_N, which is the engine's own answer.
    # -----------------------------------------------------------------
    print("\n  and the spare magazines, as a digit:")
    digits = digits_from_inc()
    reserve0 = m.peek(sym["AMMO_RESERVE"])
    for reserve in (28, 14, 13, 0, 42, 140):
        m.poke(sym["AMMO_RESERVE"], reserve)
        m.run_frames(3)
        sync(m, sym)
        want_d = min(reserve // BUL_MAX, 9)
        bad = on_screen(m, top, digits[f"HUD_DIGIT_{want_d}"], hwpen,
                        CLIPS_X0)
        check(f"a reserve of {reserve:3d} rounds shows {want_d}", bad == 0,
              f"{bad} wrong pixels" if bad else
              f"the artist's own digit, and the engine agrees "
              f"({m.peek(sym['HUD_CLIPS_N'])})")
    m.poke(sym["AMMO_RESERVE"], reserve0)
    m.run_frames(3)

    # AND A REPAINT UNDER THE BOTTOM ROW IS PUT BACK. ENT_SETTLE queues
    # the four cells a taken pickup leaves (entity.asm) and they can
    # land on row 23; the repaint runs after the beam has passed it, and
    # what makes the next frame write the row again is HUD_LIT and
    # HUD_AMMO_SPENT being set to a layout neither owns.
    # -----------------------------------------------------------------
    # AND THEN WHAT SHE IS CARRYING: an icon a kind and a count beside
    # it, at columns 14-19 (CLAUDE.md 7.8). The expectation is built
    # from the build's own art rather than from the engine's buffer,
    # which would be the engine checking itself.
    print("\n  and what she is carrying, at the end of the strip:")
    inv = inv_from_inc()
    for keys, coins in ((0, 0), (1, 0), (0, 3), (2, 7), (5, 14)):
        m.poke(sym["KEYS_COUNT"], keys)
        m.poke(sym["COINS_COUNT"], coins)
        m.run_frames(4)
        sync(m, sym)
        got = inv_on_screen(m, sym)
        want = inv_expect(inv, keys, coins)
        wrong = sum(a != b for a, b in zip(got, want))
        check(f"{keys} key(s) and {coins:2d} coin(s)", wrong == 0,
              f"{wrong} wrong bytes of {INV_BYTES * LINES}"
              + ("  - fourteen coins still show 9" if coins > 9 else ""))

    m.poke(sym["KEYS_COUNT"], 0)
    m.poke(sym["COINS_COUNT"], 0)

    # THE WALK GETS ITS OWN MACHINE, and that is not tidiness. 180
    # frames of walking carries her up the roof into a drone's fire,
    # and the bench at the bottom of this file measures HUD_LEVEL from
    # a full bar - so a walk left in the shared machine is a check
    # failing three screens away from what changed.
    print("\n  and they STAY, walking both ways:")
    m4 = boot(sym, scroll=True)
    m4.run_frames(20)
    m4.poke(sym["KEYS_COUNT"], 1)           # ... and BEFORE the first
    m4.poke(sym["COINS_COUNT"], 3)          # sample, or it is compared
    m4.run_frames(3)                        # against the layout it had
    # AND THE EXPECTATION IS BUILT FROM THE COUNTS AT THE SAMPLE, not
    # from the two poked in above. She walks over the roof's key on the
    # way, so KEYS_COUNT becomes 2 for the rest of the walk - and a
    # fixed expectation then reports the digit as ten wrong bytes when
    # the strip is showing exactly what she is carrying, which is the
    # property this is about.
    want_inv = inv_expect(inv, 1, 3)
    for mask, name in ((JOY_RIGHT, "RIGHT"), (JOY_LEFT, "LEFT")):
        worst, seen = 0, set()
        m4.joystick(mask)
        for _ in range(90):
            m4.run_frames(1)
            sync(m4, sym)
            seen.add(m4.peek(sym["SCROLL"]) | (m4.peek(sym["SCROLL"] + 1) << 8))
            want_inv = inv_expect(inv, m4.peek(sym["KEYS_COUNT"]),
                                  m4.peek(sym["COINS_COUNT"]))
            worst = max(worst, sum(a != b for a, b in
                                   zip(inv_on_screen(m4, sym), want_inv)))
        m4.joystick(0)
        check(f"... walking {name}", worst == 0,
              f"{len(seen)} start addresses, worst frame {worst} wrong "
              f"bytes of {INV_BYTES * LINES}")

    # THE SAME NEGATIVE CONTROL THE BAR AND THE ROUNDS HAVE: an icon has
    # no neighbour's content to inherit, so with HUD_INV returning at
    # once the CRTC carries the whole run off with the world.
    print("\n  the negative control - the items must be REWRITTEN:")
    m3 = boot(sym, scroll=True)
    m3.run_frames(20)
    m3.poke(sym["KEYS_COUNT"], 1)
    m3.poke(sym["COINS_COUNT"], 3)
    m3.run_frames(4)
    sync(m3, sym)
    before = sum(a != b for a, b in zip(inv_on_screen(m3, sym),
                                        inv_expect(inv, 1, 3)))
    m3.poke(sym["HUD_INV"], 0xC9)           # RET
    worst3 = 0
    m3.joystick(JOY_RIGHT)
    for _ in range(90):
        m3.run_frames(1)
        sync(m3, sym)
        want3 = inv_expect(inv, m3.peek(sym["KEYS_COUNT"]),
                           m3.peek(sym["COINS_COUNT"]))
        worst3 = max(worst3, sum(a != b for a, b in
                                 zip(inv_on_screen(m3, sym), want3)))
    m3.joystick(0)
    check("without it the items slide off with the world",
          before == 0 and worst3 > 0,
          f"{before} wrong bytes with the redraw, {worst3} of "
          f"{INV_BYTES * LINES} without it")

    print("\n  and a repaint under the bottom row is put back:")
    m.run_frames(3)
    sync(m, sym)
    scroll = m.peek(sym["SCROLL"]) | (m.peek(sym["SCROLL"] + 1) << 8)
    for w in range(CELLS + AMMO_CELLS + 1):   # ... and the digit
        for line in range(LINES):
            addr = 0xC000 + 2 * ((scroll + BASE + w) & 0x3FF) + 0x800 * line
            m.poke(addr, 0x55)
            m.poke(addr + 1, 0x55)
    # ONE FRAME BEFORE READING IT: the framebuffer is what the beam
    # last drew, not what is in RAM, so a scribble poked after the
    # sweep is invisible until the next one - and that frame also
    # proves the engine does NOT repair it on its own.
    m.run_frames(1)
    sync(m, sym)
    damaged = (on_screen(m, top, expect(m.peek(sym["PLAYER_HP"]), art, steps),
                         hwpen)
               + on_screen(m, top, want_ammo, hwpen, AMMO_X0))
    for n in ("HUD_HP", "HUD_LIT", "HUD_AMMO_SPENT"):
        m.poke(sym[n], 0xFF)
    m.run_frames(1)
    sync(m, sym)
    healed = (on_screen(m, top, expect(m.peek(sym["PLAYER_HP"]), art, steps),
                        hwpen)
              + on_screen(m, top, want_ammo, hwpen, AMMO_X0))
    check("both runs come back on the next frame", damaged > 0 and healed == 0,
          f"{damaged} pixels wrong after the scribble, {healed} after one "
          f"frame - and a bar that only checked HUD_HP would leave them, "
          f"because HUD_LEVEL finds the same cells lit and says so")

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
    # THE LOCK IS 25 Hz AND 100 OF 200 (CLAUDE.md 9): a game frame is
    # two hardware frames, so that the heroine is on the screen for both
    # sweeps and a frame the loop cannot pay for is not a hole where she
    # was. The strip is drawn once a game frame like everything else.
    check("walking and scrolling with the strip on holds 25 Hz",
          loops >= 99,
          f"{loops} game frames in 200 hardware frames")

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
