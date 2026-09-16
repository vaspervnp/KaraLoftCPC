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
  3. DOWN on the ladder tile puts her on it, she plays the one cel of
     turning to it before she plays any of the climb, and the cels come
     out of the `kact` blob rather than kcore
  3b. THE CLIMB IS A BACK VIEW AND HAS ONE FACING: the same cel comes
     out whichever way KARA_FACING says she is turned, while the side-on
     turn cel does not. Its negative control tells KARA_SETS the set has
     two facings and watches the left-hand blob draw something else
  4. she arrives on the pavement at exactly the street's surface line,
     grounded and off the ladder, and the view travelled to get there
  5. UP brings her back to exactly the roof's surface, and the view with
     her
  6. hanging: no direction held holds her still, on the hang cels
  7. the loop still holds 50 Hz on every one of those
  8. THE NEGATIVE CONTROL: take TA_CLIMB off the ladder tile and none of
     it happens. Without this the suite would pass on a build where
     DOWN simply dropped her through a hole in the roof.
  9. and the other way off the roof: the gap between two buildings, the
     `drop` cels it exists to play, and the landing. Its own negative
     control fills the gap in with roof and walks her across it.
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
              "V_CR_MAX", "CAM_TOP", "CAM_BOT", "TILE_ATTR",
              "KST_CLIMB_TURN", "CLIMB_TURN_START", "CLIMB_TURN_OFF",
              "KACT_CLIMB_FIRST", "KACT_CLIMB_TURN_FIRST", "KACT_DURATION",
              "KARA_SETS", "KSET_BYTES", "KARA_SPAN_DRAW", "SPAN_ERASE"):
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
    for _ in range(4):
        m.run_frames(1)
        if m.peek(sym["KARA_CLIMB"]):
            break
    on = st(m, sym)
    check("DOWN puts her on the ladder", on["climb"] == 1 and on["ground"] == 0,
          f"KARA_CLIMB {on['climb']}, KARA_GROUND {on['ground']}")
    check("and centres her box - and so her figure - on the shaft",
          on["wx"] == ladder * 4 - 1,
          f"KARA_WX {on['wx']} - her box's middle, byte {on['wx'] + 3}, "
          f"is inside the shaft's tile ({ladder * 4}..{ladder * 4 + 3})")

    # SHE TURNS BEFORE SHE CLIMBS. `climb` is a back view and walk is
    # side on, so there is one cel between them; it is drawn standing on
    # the ground, which is why the engine holds her still while it is up.
    check("the first thing she plays is the turn, not the climb",
          on["state"] == sym["KST_CLIMB_TURN"]
          and on["kset"] == sym["KSET_ACT"]
          and on["frame"] == sym["KACT_CLIMB_TURN_FIRST"],
          f"KARA_STATE {on['state']} (TURN is {sym['KST_CLIMB_TURN']}), "
          f"cel {on['frame']} of the action blob")
    dur = m.peek(sym["KACT_DURATION"] + sym["KACT_CLIMB_TURN_FIRST"])
    turn = 0
    while turn < 30 and m.peek(sym["KARA_STATE"]) == sym["KST_CLIMB_TURN"]:
        m.run_frames(1)
        turn += 1
    turned = st(m, sym)
    m.joystick(0)
    check("and it holds her where she is, for the art's own beat",
          turned["wy"] == on["wy"] and abs(turn - dur) <= 1,
          f"{turn} frames, and the artist drew the cel for {dur}; "
          f"world y {on['wy']} -> {turned['wy']}")
    check("then the climb cels come up, out of the ACTION blob",
          turned["kset"] == sym["KSET_ACT"]
          and turned["state"] == sym["KST_CLIMB"]
          and turned["frame"] >= sym["KACT_CLIMB_FIRST"],
          f"KARA_SET {turned['kset']}, KARA_STATE {turned['state']} "
          f"(CLIMB is {sym['KST_CLIMB']}), cel {turned['frame']}")

    # ---- 3b. the back view has ONE facing --------------------------
    # The four climb cels are stored once, at the END of the right-facing
    # blob, and kact_l stops before them (CLAUDE.md 7.1). So the drawer
    # has to ignore KARA_FACING from KACT_CLIMB_FIRST on - and this is
    # the check that it does, on the screen and not on the table.
    print("\n  the back view, which has no left and right:")
    STUB = 0x9000
    mm = boot(sym, scroll=True)

    def call(machine, addr):
        c = bytes([0xF3, 0xCD, addr & 0xFF, addr >> 8, 0x18, 0xFE])
        machine.write_ram(STUB, c)
        machine.set_pc(STUB)
        for _ in range(400000):
            machine.run_us(1)
            if machine.pc == STUB + 4:
                return True
        return False

    def shot(machine, facing, frame):
        """Draw one cel straight through KARA_SPAN_DRAW and read the
        screen back, then put the screen the way it was."""
        machine.poke(sym["KARA_SET"], sym["KSET_ACT"])
        machine.poke(sym["KARA_FRAME"], frame)
        machine.poke(sym["KARA_FACING"], facing)
        machine.poke(sym["KARA_X"], 30)
        machine.poke(sym["KARA_Y"], 60)
        if not call(machine, sym["KARA_SPAN_DRAW"]):
            return None
        out = bytes(machine.read_ram(0xC000, 0x4000))
        call(machine, sym["SPAN_ERASE"])
        return out

    back = sym["KACT_CLIMB_FIRST"]
    side = sym["KACT_CLIMB_TURN_FIRST"]
    br, bl = shot(mm, 0, back), shot(mm, 1, back)
    check("a climb cel draws the same pixels whichever way she faces",
          br is not None and br == bl,
          f"cel {back} - she is on a ladder with her back to the player, "
          f"so there is nothing to mirror")
    sr, sl = shot(mm, 0, side), shot(mm, 1, side)
    check("... and the turn cel, which is side on, does not",
          sr is not None and sl is not None and sr != sl,
          f"cel {side} - drawn facing right, mirrored facing left")

    # THE NEGATIVE CONTROL. Tell KARA_SETS the action set has two facings
    # all the way up and the left-hand draw indexes kact_l past the end
    # of its frame table, which has only the cels that HAVE two facings.
    thresh = sym["KARA_SETS"] + sym["KSET_ACT"] * sym["KSET_BYTES"]
    was = mm.peek(thresh)
    check("the engine really is bounding it at the first back-view cel",
          was == back, f"KARA_SETS row {sym['KSET_ACT']} says {was}")
    mm.poke(thresh, 255)
    wild = shot(mm, 1, back)
    check("the negative control: told it has two facings, the left blob "
          "draws something else", wild != br,
          "kact_l holds only the cels with two facings, so frame "
          f"{back} is past the end of its table")

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
    landed = st(m, sym)
    m.joystick(0)
    m.run_frames(3)
    bot = st(m, sym)
    check("stepping off onto the pavement plays the turn again",
          landed["state"] == sym["KST_CLIMB_TURN"],
          f"KARA_STATE {landed['state']} on the frame she let go "
          f"(TURN is {sym['KST_CLIMB_TURN']})")
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

    # ---- 9. the gap in the roof, and the fall -----------------------
    # A DROP IS NOT A JUMP. She has an animation for the ground going
    # away under her and nothing in a level with an unbroken roof can
    # ever play it, so the City has one gap - three tiles of open air
    # between two buildings, put where no other suite's walk reaches it
    # (tools/make_city_map.py). Walking off its edge is a 128-pixel fall
    # to the street, and it is the only thing in the level that drives
    # the vertical camera faster than it can follow.
    print("\n  walking off the roof:")
    T, _ = city.tile_names()
    MAP_ADDR = sym["MAP_ADDR"] if "MAP_ADDR" in sym else 0xA000

    def to_the_gap(mm, frames=700):
        """Hold right until the ground goes away, and keep her alive.

        The drones shoot at her on the way past and what is being
        measured here is the fall, not her hit points; a death would
        take the state machine (KST_DIE beats everything) and the run
        would be measuring that instead.
        """
        mm.joystick(JOY_RIGHT)
        first = None
        for i in range(frames):
            mm.run_frames(1)
            mm.poke(sym["PLAYER_HP"], 100)
            s = st(mm, sym)
            if first is None and not s["ground"]:
                first = (i, s)
            if first and s["ground"] and s["wy"] + KARA_BOX_H >= STREET_Y:
                mm.joystick(0)
                return first, i, st(mm, sym)
        mm.joystick(0)
        return first, None, st(mm, sym)

    mm = boot(sym, scroll=True)
    off, landed_at, down = to_the_gap(mm)
    check("she walks off the roof's edge and the ground goes away",
          off is not None and off[1]["wy"] + KARA_BOX_H == ROOF_Y,
          f"airborne on frame {off[0] if off else '-'} with her feet still on "
          f"the roof line {ROOF_Y}" if off else "she never left the ground")
    if off:
        check("... and it is a DROP, not a jump: she did not ask for it",
              off[1]["state"] == sym["KST_DROP"]
              and off[1]["kset"] == sym["KSET_ACT"]
              and off[1]["frame"] >= sym["KACT_DROP_FIRST"],
              f"KARA_STATE {off[1]['state']} (DROP is {sym['KST_DROP']}, "
              f"JUMP is {sym['KST_JUMP']}), cel {off[1]['frame']}")
    check("she lands on the pavement, exactly on its surface",
          landed_at is not None and down["wy"] + KARA_BOX_H == STREET_Y,
          f"feet at world y {down['wy'] + KARA_BOX_H}, pavement at {STREET_Y}"
          + (f", {landed_at - off[0]} frames in the air" if landed_at and off
             else ""))
    mm.run_frames(60)
    settled = st(mm, sym)
    check("and the camera catches up with her on the street",
          settled["cr"] == cr_max and 0 <= settled["ky"] <= SCREEN_LINES - 1,
          f"WORLD_CR {settled['cr']} of {cr_max}, KARA_Y {settled['ky']} - the "
          f"fall outruns the camera, which then has to follow her down")

    # THE NEGATIVE CONTROL: fill the hole in and she walks across it.
    # Without it this section would pass on a build where she fell
    # through the roof anywhere, which is the failure it is there to
    # tell the gap apart from.
    print("\n  the negative control - it is the HOLE, not the walk:")
    mm = boot(sym, scroll=True)
    for x in city.ROOF_GAP:
        mm.poke(MAP_ADDR + city.ROW_ROOF * city.MAP_W + x, T["roof_m"])
    off2, landed2, ctl = to_the_gap(mm, frames=700)
    check("with the gap filled in she walks straight over it",
          off2 is None and ctl["ground"] == 1
          and ctl["wy"] + KARA_BOX_H == ROOF_Y
          and ctl["wx"] // 4 > city.ROOF_GAP[-1],
          f"she is at tile {ctl['wx'] // 4}, past the gap at "
          f"{city.ROOF_GAP}, still on the roof at {ctl['wy'] + KARA_BOX_H}")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
