#!/usr/bin/env python3
"""The ladder, the street, and the camera that follows her between them.

The City is not a rooftop any more: there are ladders down the face of
the building and a street at the bottom, and the street is far enough
down that it CANNOT be on screen at the same time as the roof. So this
suite is as much about the vertical scroll as about the climb - reaching
the pavement is the only way to exercise the axis from the game rather
than by poking V_REQUEST, which is what tools/test_module4.py does.

What it checks, in order:

  1. the map really has a shaft: TA_CLIMB from the roof's own row down
     to the last row of wall, and a solid pavement under it
  2. the geometry: the roof's surface, the street's, and the fact that
     the display cannot show both
  3. DOWN on the ladder tile puts her on it, and the cels come out of
     the `kact` blob rather than kcore
  4. she arrives on the pavement at exactly the street's surface line,
     grounded and off the ladder, and the view travelled to get there
  5. UP brings her back to exactly the roof's surface, and the view with
     her
  6. hanging: no direction held holds her still, on the hang cels
  7. the loop still holds 50 Hz on every one of those
  8. THE NEGATIVE CONTROL: take TA_CLIMB off the ladder tile and none of
     it happens. Without this the suite would pass on a build where
     DOWN simply dropped her through a hole in the roof.
"""
import os
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import symbols, boot                                  # noqa: E402
import make_city_map as city                                     # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

JOY_UP, JOY_DOWN, JOY_LEFT, JOY_RIGHT = 0x01, 0x02, 0x04, 0x08
TA_SOLID, TA_PLATFORM, TA_CLIMB = 0x80, 0x40, 0x08
TILE_LADDER = 25
KARA_BOX_H = 64
SCREEN_LINES = 192

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def st(m, sym):
    return dict(
        wx=m.peek(sym["KARA_WX"]) | (m.peek(sym["KARA_WX"] + 1) << 8),
        wy=m.peek(sym["KARA_WY"]), ground=m.peek(sym["KARA_GROUND"]),
        climb=m.peek(sym["KARA_CLIMB"]), cr=m.peek(sym["WORLD_CR"]),
        state=m.peek(sym["KARA_STATE"]), kset=m.peek(sym["KARA_SET"]),
        frame=m.peek(sym["KARA_FRAME"]), ky=m.peek(sym["KARA_Y"]))


def onto_ladder(m, sym, tile):
    """Walk her right until her box straddles the ladder at map tile
    `tile`, which is where DOWN can find it under her feet."""
    want = tile * 4 - 1              # CLIMB_GRAB's own answer, see player.asm
    m.joystick(JOY_RIGHT)
    for _ in range(300):
        m.run_frames(1)
        if m.peek(sym["KARA_WX"]) | (m.peek(sym["KARA_WX"] + 1) << 8) >= want:
            break
    m.joystick(0)
    m.run_frames(2)


def climb(m, sym, joy, frames=400, until=None):
    """Hold a direction on the ladder until `until` says stop."""
    m.joystick(joy)
    for i in range(frames):
        m.run_frames(1)
        if until and until(st(m, sym)):
            break
    m.joystick(0)
    m.run_frames(2)
    return i


def main():
    sym = symbols()
    for n in ("KARA_CLIMB", "PLAYER_CLIMB", "CLIMB_ENTER", "CLIMB_GRAB",
              "CLIMB_AT", "CAMERA_V", "KST_CLIMB", "KST_HANG", "KSET_ACT",
              "V_CR_MAX", "CAM_TOP", "CAM_BOT", "TILE_ATTR"):
        if n not in sym:
            print(f"  [FAIL] the engine has no {n}")
            fails.append(n)
    if fails:
        print(f"\nFAILED: {len(fails)} check(s): " + ", ".join(fails))
        return 1

    ROOF_Y = city.ROW_ROOF * 16
    STREET_Y = city.ROW_PAVEMENT * 16
    ladder = city.LADDER_X[0]

    # ---- 1. the map, as the generator wrote it ---------------------
    print("\n  the shaft, in build/city_map.bin:")
    blob = open(os.path.join(ROOT, "build", "city_map.bin"), "rb").read()
    col = [blob[row * city.MAP_W + ladder] for row in range(city.MAP_H)]
    rungs = list(range(city.ROW_ROOF, city.ROW_PAVEMENT))
    check("the ladder runs from the roof's row to the last row of wall",
          all(col[r] == TILE_LADDER for r in rungs)
          and col[city.ROW_ROOF - 1] != TILE_LADDER
          and col[city.ROW_PAVEMENT] != TILE_LADDER,
          f"tile {ladder}, rows {rungs[0]}-{rungs[-1]}")

    # TILE_ATTR is a literal in collide.asm; read the one the engine has.
    m = boot(sym, scroll=True)
    attr = m.peek(sym["TILE_ATTR"] + TILE_LADDER)
    check("the ladder tile is a climb AND a one-way floor",
          attr == TA_CLIMB + TA_PLATFORM,
          f"TILE_ATTR[{TILE_LADDER}] = &{attr:02X} - TA_PLATFORM is what lets "
          f"her stand on its top rung before she steps onto it")

    # ---- 2. the geometry -------------------------------------------
    print("\n  the drop:")
    check("the street is below what the display can show from the roof",
          STREET_Y >= SCREEN_LINES,
          f"roof surface y {ROOF_Y}, street surface y {STREET_Y}, "
          f"display {SCREEN_LINES} lines - she cannot see it until it scrolls")
    cr_max = sym["V_CR_MAX"]
    check("the view has exactly the range the drop needs",
          cr_max * 8 + SCREEN_LINES == city.MAP_H * 16,
          f"V_CR_MAX = {cr_max} character rows = {cr_max * 8} lines")

    # ---- 3. getting on it ------------------------------------------
    print("\n  stepping onto it:")
    s0 = st(m, sym)
    check("she starts on the roof", s0["ground"] and s0["wy"] + KARA_BOX_H == ROOF_Y,
          f"feet at world y {s0['wy'] + KARA_BOX_H}, roof at {ROOF_Y}")
    onto_ladder(m, sym, ladder)
    before = st(m, sym)
    check("walking over the top rung does not drop her through it",
          before["ground"] == 1 and before["climb"] == 0
          and before["wy"] + KARA_BOX_H == ROOF_Y,
          f"feet at {before['wy'] + KARA_BOX_H}, still grounded")
    m.joystick(JOY_DOWN)
    m.run_frames(2)
    on = st(m, sym)
    m.joystick(0)
    check("DOWN puts her on the ladder", on["climb"] == 1 and on["ground"] == 0,
          f"KARA_CLIMB {on['climb']}, KARA_GROUND {on['ground']}")
    check("and centres her box - and so her figure - on the shaft",
          on["wx"] == ladder * 4 - 1,
          f"KARA_WX {on['wx']} - her box's middle, byte {on['wx'] + 3}, "
          f"is inside the shaft's tile ({ladder * 4}..{ladder * 4 + 3})")
    check("the cels come out of the ACTION blob, not kcore",
          on["kset"] == sym["KSET_ACT"] and on["state"] == sym["KST_CLIMB"],
          f"KARA_SET {on['kset']}, KARA_STATE {on['state']} "
          f"(CLIMB is {sym['KST_CLIMB']})")

    # ---- 4. all the way down ---------------------------------------
    print("\n  down to the street:")
    cr_seen = set()
    m.joystick(JOY_DOWN)
    for _ in range(400):
        m.run_frames(1)
        s = st(m, sym)
        cr_seen.add(s["cr"])
        if s["ground"] and not s["climb"] and s["wy"] + KARA_BOX_H >= STREET_Y:
            break
    m.joystick(0)
    m.run_frames(3)
    bot = st(m, sym)
    check("she lands on the pavement, exactly on its surface",
          bot["ground"] == 1 and bot["climb"] == 0
          and bot["wy"] + KARA_BOX_H == STREET_Y,
          f"feet at world y {bot['wy'] + KARA_BOX_H}, pavement at {STREET_Y}")
    check("the view had to scroll the whole way to follow her",
          bot["cr"] == cr_max and 0 in cr_seen,
          f"WORLD_CR {min(cr_seen)} -> {bot['cr']} of a maximum {cr_max}")
    check("and it put her on the display, not past the bottom of it",
          0 <= bot["ky"] <= SCREEN_LINES - 1,
          f"KARA_Y {bot['ky']}")
    check("the street is on screen with her",
          bot["cr"] * 8 + SCREEN_LINES >= city.MAP_H * 16,
          f"the view shows world lines {bot['cr'] * 8}.."
          f"{bot['cr'] * 8 + SCREEN_LINES - 1}")

    # ---- 5. she can walk there, and climb back ---------------------
    print("\n  the street, and back up:")
    m.joystick(JOY_RIGHT)
    m.run_frames(20)
    m.joystick(0)
    m.run_frames(2)
    walked = st(m, sym)
    check("the pavement carries her: she walks without falling",
          walked["ground"] == 1 and walked["wy"] == bot["wy"]
          and walked["wx"] > bot["wx"],
          f"world x {bot['wx']} -> {walked['wx']}, feet still at "
          f"{walked['wy'] + KARA_BOX_H}")

    # walk back to the shaft, whichever side of it she is on
    m.joystick(JOY_LEFT)
    for _ in range(300):
        m.run_frames(1)
        if (m.peek(sym["KARA_WX"]) | (m.peek(sym["KARA_WX"] + 1) << 8)) \
                <= ladder * 4 - 1:
            break
    m.joystick(0)
    m.run_frames(2)
    m.joystick(JOY_UP)
    for _ in range(400):
        m.run_frames(1)
        s = st(m, sym)
        if s["ground"] and not s["climb"] and s["wy"] + KARA_BOX_H <= ROOF_Y:
            break
    m.joystick(0)
    m.run_frames(3)
    top = st(m, sym)
    check("UP brings her back to exactly the roof's surface",
          top["ground"] == 1 and top["climb"] == 0
          and top["wy"] + KARA_BOX_H == ROOF_Y,
          f"feet at world y {top['wy'] + KARA_BOX_H}, roof at {ROOF_Y}")
    check("and the view came back to the top of the world",
          top["cr"] == 0, f"WORLD_CR {top['cr']}")

    # ---- 6. hanging -------------------------------------------------
    print("\n  hanging on:")
    m.joystick(JOY_DOWN)
    m.run_frames(30)
    m.joystick(0)
    m.run_frames(6)
    hang = st(m, sym)
    y0 = hang["wy"]
    m.run_frames(40)
    still = st(m, sym)
    check("nothing held holds her where she is",
          still["climb"] == 1 and still["wy"] == y0,
          f"world y {y0} -> {still['wy']} over 40 frames")
    check("... on the hang cels, not the climb ones",
          still["state"] == sym["KST_HANG"] and still["kset"] == sym["KSET_ACT"],
          f"KARA_STATE {still['state']} (HANG is {sym['KST_HANG']})")
    m.joystick(JOY_LEFT)
    m.run_frames(20)
    m.joystick(0)
    m.run_frames(2)
    side = st(m, sym)
    check("LEFT and RIGHT cannot walk her out of the shaft",
          side["climb"] == 1 and side["wx"] == hang["wx"],
          f"KARA_WX {hang['wx']} -> {side['wx']}")

    # ---- 7. and the loop still closes -------------------------------
    print("\n  the loop, on the new ground:")
    for label, setup in (
            ("climbing down", lambda mm: (onto_ladder(mm, sym, ladder),
                                          mm.joystick(JOY_DOWN))),
            ("standing on the street", lambda mm: (
                onto_ladder(mm, sym, ladder), mm.joystick(JOY_DOWN),
                mm.run_frames(200), mm.joystick(0))),
            ("walking the street", lambda mm: (
                onto_ladder(mm, sym, ladder), mm.joystick(JOY_DOWN),
                mm.run_frames(200), mm.joystick(JOY_RIGHT)))):
        mm = boot(sym, scroll=True)
        setup(mm)
        mm.run_frames(5)
        f0 = mm.peek(sym["FRAME_COUNT"])
        mm.run_frames(200)
        got = (mm.peek(sym["FRAME_COUNT"]) - f0) % 256
        mm.joystick(0)
        # The floor is the one tools/test_enemies.py sets and for the same
        # reason: an enemy coming into or going out of view costs a frame,
        # and the vertical camera's own step is a whole character row of
        # DRAW_ROW split over two frames.
        check(f"50 Hz: {label}", got >= 198,
              f"{got} loop iterations in 200 hardware frames")

    # ---- 8. the negative control ------------------------------------
    print("\n  the negative control - TA_CLIMB is what does it:")
    mm = boot(sym, scroll=True)
    mm.poke(sym["TILE_ATTR"] + TILE_LADDER, TA_SOLID)    # a plain floor
    onto_ladder(mm, sym, ladder)
    grounded = st(mm, sym)
    mm.joystick(JOY_DOWN)
    mm.run_frames(20)
    mm.joystick(0)
    mm.run_frames(2)
    ctl = st(mm, sym)
    check("without it DOWN does nothing at all",
          ctl["climb"] == 0 and ctl["ground"] == 1
          and ctl["wy"] == grounded["wy"] and ctl["cr"] == 0,
          f"KARA_CLIMB {ctl['climb']}, world y {ctl['wy']}, WORLD_CR {ctl['cr']}"
          f" - she stays on the roof, so the climb really is driven by the "
          f"tile's attribute and not by where she is standing")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
