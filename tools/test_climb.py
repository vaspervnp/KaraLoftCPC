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
  6. stopping on the ladder: no direction held holds her still AND
     holds the CLIMB cel she stopped on - there is no `hang` state any
     more, because two side-on cels in the middle of a back-view climb
     read as her turning round without moving
  7. the loop still holds 50 Hz on every one of those
  8. THE NEGATIVE CONTROL: take TA_CLIMB off the ladder tile and none of
     it happens. Without this the suite would pass on a build where
     DOWN simply dropped her through a hole in the roof.
  9. and the other way off the roof: the gap between two buildings, the
     `drop` cels it exists to play, and the landing. Its own negative
     control fills the gap in with roof and walks her across it.
 10. AND SHE CAN JUMP IT. The window is counted in frames either side of
     the lip, including the P_COYOTE frames after it, and it has a
     control at each end: too early lands her in the hole, too late is
     past the coyote and she falls.
 11. the street runs PAST the garage. It is four tiles wide and it used
     to be solid, which is a wall across a pavement she is three tiles
     wide on. The control puts TA_SOLID back and watches her stop dead.
"""
import os
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import symbols, boot                                  # noqa: E402
import make_city_map as city                                     # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

JOY_UP, JOY_DOWN, JOY_LEFT, JOY_RIGHT = 0x01, 0x02, 0x04, 0x08
# The FORMAT's bit order, which the engine took as its own when the
# flags moved into tileflags_<level>.bin (docs/editor.md 9.2).
TA_SOLID, TA_PLATFORM, TA_CLIMB = 0x01, 0x02, 0x08
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
        frame=m.peek(sym["KARA_FRAME"]), ky=m.peek(sym["KARA_Y"]),
        facing=m.peek(sym["KARA_FACING"]))


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
              "CLIMB_AT", "CAMERA_V", "KST_CLIMB", "KACT_CLIMB_COUNT",
              "KSET_ACT", "KST_JUMP", "KARA_COYOTE", "P_COYOTE",
              "KST_HANG", "KST_CROUCH", "KARA_HANG", "HANG_BEAT",
              "HANG_HOLD", "HANG_DROP", "KACT_HANG_FIRST", "KACT_HANG_COUNT",
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

    # ---- 6. stopping on the ladder ----------------------------------
    # SHE HOLDS THE CEL SHE STOPPED ON, and there is no `hang` state any
    # more. The art has the tag and this used to play it, which put two
    # SIDE-ON cels in the middle of a back-view climb: she stopped and
    # turned to face the player without moving a pixel. Stopping is the
    # same pose not moving, so the state stays CLIMB and the animator is
    # simply not called (src/action.asm).
    print("\n  stopping on it:")
    m.joystick(JOY_DOWN)
    m.run_frames(30)
    m.joystick(0)
    m.run_frames(6)
    hang = st(m, sym)
    y0, cel0 = hang["wy"], hang["frame"]
    seen = set()
    for _ in range(40):
        m.run_frames(1)
        seen.add(st(m, sym)["frame"])
    still = st(m, sym)
    check("nothing held holds her where she is",
          still["climb"] == 1 and still["wy"] == y0,
          f"world y {y0} -> {still['wy']} over 40 frames")
    check("... on the CLIMB cel she stopped on, frozen there",
          still["state"] == sym["KST_CLIMB"] and still["kset"] == sym["KSET_ACT"]
          and seen == {cel0}
          and sym["KACT_CLIMB_FIRST"] <= cel0
          < sym["KACT_CLIMB_FIRST"] + sym["KACT_CLIMB_COUNT"],
          f"cel {cel0} held for 40 frames (the climb run is "
          f"{sym['KACT_CLIMB_FIRST']}.."
          f"{sym['KACT_CLIMB_FIRST'] + sym['KACT_CLIMB_COUNT'] - 1}), cels "
          f"seen: {sorted(seen)}")
    # ... and the animator is not merely dead: hold DOWN and it runs.
    m.joystick(JOY_DOWN)
    moving = set()
    for _ in range(40):
        m.run_frames(1)
        moving.add(st(m, sym)["frame"])
    m.joystick(0)
    m.run_frames(4)
    check("and it is the INPUT that froze it, not a stopped animator",
          len(moving) > 1 and moving <= set(range(
              sym["KACT_CLIMB_FIRST"],
              sym["KACT_CLIMB_FIRST"] + sym["KACT_CLIMB_COUNT"])),
          f"climbing again she plays {sorted(moving)}")
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

    # ---- 10. and she can JUMP the gap -------------------------------
    # A GAP YOU CAN ONLY FALL INTO IS A WALL WITH A LONGER ANIMATION.
    # Her arc is 15 frames and she covers about a byte a frame; the hole
    # is 12 bytes and she has to be 7 past its far lip to land, so the
    # take-off window is the ten bytes before the edge - a fifth of a
    # second, after which the press did nothing at all and she fell 128
    # pixels. P_COYOTE frames of edge after the ground goes away is what
    # makes that a jump a player can actually make, and the two controls
    # below are what keep it from becoming a jump she cannot miss.
    print("\n  jumping it:")

    def jump_at(offset, frames=800):
        """Walk right and tap UP `offset` frames from the lip.

        THE LIP IS THE ONE SECTION 9 MEASURED, not one found in this
        run: the press has to be scheduled before she gets there, and
        a walk that starts the same way reaches it on the same frame.
        A jump changes what happens after it and nothing before it.
        """
        mm = boot(sym, scroll=True)
        mm.joystick(JOY_RIGHT)
        airborne, took_off = None, None
        for i in range(frames):
            if i == where_lip + offset:
                mm.joystick(JOY_RIGHT | JOY_UP)
                mm.run_frames(1)
                mm.joystick(JOY_RIGHT)
            else:
                mm.run_frames(1)
            mm.poke(sym["PLAYER_HP"], 100)
            s = st(mm, sym)
            if i == where_lip + offset:
                took_off = s["state"]       # what the press made of her
            if airborne is None and not s["ground"]:
                airborne = i
            if airborne is not None and s["ground"]:
                mm.joystick(0)
                return s, took_off
        mm.joystick(0)
        return st(mm, sym), took_off

    where_lip = off[0] if off else 0
    over, flew = jump_at(0)
    check("a press on the frame the roof runs out clears the gap",
          over["wy"] + KARA_BOX_H == ROOF_Y
          and over["wx"] // 4 > city.ROOF_GAP[-1],
          f"she lands on tile {over['wx'] // 4} with her feet at "
          f"{over['wy'] + KARA_BOX_H} (the roof is {ROOF_Y}, the gap "
          f"{city.ROOF_GAP[0]}..{city.ROOF_GAP[-1]})")
    late, flew_late = jump_at(sym["P_COYOTE"] - 1)
    check(f"... and so does one {sym['P_COYOTE'] - 1} frames after it, which is "
          f"the last of the coyote",
          late["wy"] + KARA_BOX_H == ROOF_Y
          and late["wx"] // 4 > city.ROOF_GAP[-1],
          f"tile {late['wx'] // 4}, feet {late['wy'] + KARA_BOX_H}")
    check("and a coyote take-off turns the fall she was in into a JUMP",
          flew == sym["KST_JUMP"] and flew_late == sym["KST_JUMP"],
          f"KARA_STATE {flew} on the press at the lip and {flew_late} on the "
          f"one {sym['P_COYOTE'] - 1} frames into the fall (JUMP is "
          f"{sym['KST_JUMP']}, DROP is {sym['KST_DROP']}) - .jump clears "
          f"KARA_FELL, which is what the cels are chosen from")

    print("\n  the two controls - the window has both ends:")
    spent, _ = jump_at(sym["P_COYOTE"] + 2)
    check("past the coyote the press does nothing and she falls",
          spent["wy"] + KARA_BOX_H >= STREET_Y,
          f"she ends on the street at {spent['wy'] + KARA_BOX_H}, not the "
          f"roof at {ROOF_Y} - the counter runs out whether she uses it or "
          f"not, so a long fall cannot be rescued halfway down")
    early, _ = jump_at(-12)
    check("and a jump twelve frames early lands her in the hole",
          early["wy"] + KARA_BOX_H >= STREET_Y,
          f"she ends at {early['wy'] + KARA_BOX_H} on tile "
          f"{early['wx'] // 4} - the gap is still a gap, and the check "
          f"above is not passing because everything clears it")

    # ---- 11. the street, past the garage ----------------------------
    # IT IS PART OF THE BUILDING'S FACE, like the brick around it. Solid,
    # its four tiles were a wall across the pavement - her box is three
    # tiles wide, so BOX_SOLID_H refused every step into it and the
    # street was cut in two at each garage. A shut door is something she
    # opens with the key; it is not something the physics stops her at.
    print("\n  the street runs past the garage:")
    T2, _ = city.tile_names()
    GARAGE = ("jamb_l", "sign_p", "jamb_r", "shutter", "shutter_bottom")
    garage_x = 30                       # make_city_map.py puts one here
    for n in GARAGE:
        a = m.peek(sym["TILE_ATTR"] + T2[n])
        if a & TA_SOLID:
            check(f"the garage tile `{n}` is not a wall", False,
                  f"TILE_ATTR[{T2[n]}] = &{a:02X}")
            break
    else:
        check("none of the garage's five tiles is solid",
              True, f"tiles {[T2[n] for n in GARAGE]}")

    def street_from(tile, solid=False, frames=420):
        """Climb down the ladder at `tile` and walk LEFT along the road."""
        mm = boot(sym, scroll=True)
        if solid:
            for n in GARAGE:
                mm.poke(sym["TILE_ATTR"] + T2[n], TA_SOLID)
        onto_ladder(mm, sym, tile)
        mm.joystick(JOY_DOWN)
        for _ in range(400):
            mm.run_frames(1)
            mm.poke(sym["PLAYER_HP"], 100)
            s = st(mm, sym)
            if s["ground"] and s["wy"] + KARA_BOX_H >= STREET_Y:
                break
        start = st(mm, sym)["wx"]
        mm.joystick(JOY_LEFT)
        least = start
        for _ in range(frames):
            mm.run_frames(1)
            mm.poke(sym["PLAYER_HP"], 100)
            least = min(least, st(mm, sym)["wx"])
        mm.joystick(0)
        return start, least

    down_at = city.LADDER_X[1]          # tile 34, just past the garage
    start, least = street_from(down_at)
    check("she walks the pavement straight past it",
          least // 4 < garage_x,
          f"from tile {start // 4} she reaches tile {least // 4}, and the "
          f"garage is tiles {garage_x}..{garage_x + 3}")
    print("\n  the negative control - it is the TILES, not the walk:")
    start2, least2 = street_from(down_at, solid=True)
    check("with TA_SOLID back on them she stops dead at the jamb",
          garage_x <= least2 // 4 <= garage_x + 3,
          f"from tile {start2 // 4} she gets no further left than tile "
          f"{least2 // 4}, which is inside the garage's own four "
          f"({garage_x}..{garage_x + 3}) - so the walk above is the tiles "
          f"and not the walk")

    # ---- 12. the OTHER way down: the ledge --------------------------
    # A ladder is the way down the level gives you. This is the one the
    # floor gives you: DOWN at the lip and she crouches, takes hold and
    # hangs off it on the `hang` cels the artist redrew for it. Let the
    # key up and she waits HANG_HOLD frames and climbs back; press it
    # again inside them and she lets go, which is a drop.
    print("\n  the ledge at the gap:")

    def to_lip(mm=None):
        mm = mm or boot(sym, scroll=True)
        mm.joystick(JOY_RIGHT)
        for _ in range(700):
            mm.run_frames(1)
            mm.poke(sym["PLAYER_HP"], 100)
            if wx_of(mm) >= city.ROOF_GAP[0] * 4 - 7:
                break
        mm.joystick(0)
        mm.run_frames(2)
        return mm

    def wx_of(mm):
        return mm.peek(sym["KARA_WX"]) | (mm.peek(sym["KARA_WX"] + 1) << 8)

    mm = to_lip()
    stood = st(mm, sym)
    mm.joystick(JOY_DOWN)
    mm.run_frames(4)
    ducked = st(mm, sym)
    check("DOWN at the lip crouches her first",
          ducked["state"] == sym["KST_CROUCH"]
          and mm.peek(sym["KARA_HANG"]) == 1
          and ducked["wy"] == stood["wy"],
          f"KARA_STATE {ducked['state']} (CROUCH is {sym['KST_CROUCH']}), "
          f"still on the roof at {ducked['wy'] + KARA_BOX_H}")
    check("... and turns her back on the drop",
          ducked["facing"] == 1 and stood["facing"] == 0,
          f"KARA_FACING {stood['facing']} -> {ducked['facing']} - the art is "
          f"drawn with the building to her RIGHT, so a right-hand lip is the "
          f"mirrored cel")
    mm.run_frames(sym["HANG_BEAT"] + 2)
    hung = st(mm, sym)
    check("... and then she takes hold of it",
          hung["state"] == sym["KST_HANG"] and hung["kset"] == sym["KSET_ACT"]
          and sym["KACT_HANG_FIRST"] <= hung["frame"]
          < sym["KACT_HANG_FIRST"] + sym["KACT_HANG_COUNT"]
          and hung["ground"] == 0,
          f"KARA_STATE {hung['state']} (HANG is {sym['KST_HANG']}), cel "
          f"{hung['frame']} of the kact blob's hang run")
    check("... hanging exactly the art's own drop below the floor",
          hung["wy"] == stood["wy"] + sym["HANG_DROP"],
          f"world y {stood['wy']} -> {hung['wy']}: the cel puts the ledge's "
          f"top surface on line 6 of a box whose last line is 63")
    mm.run_frames(60)
    still = st(mm, sym)
    check("... and the key held down holds her there",
          still["state"] == sym["KST_HANG"] and still["wy"] == hung["wy"],
          f"60 frames later she is still at {still['wy']} - the count only "
          f"starts when DOWN comes up")

    mm.joystick(0)
    mm.run_frames(sym["HANG_HOLD"] - 6)
    waiting = st(mm, sym)
    mm.run_frames(12)
    back = st(mm, sym)
    check("letting the key up and NOT pressing it again climbs her back",
          waiting["state"] == sym["KST_HANG"] and back["ground"] == 1
          and back["wy"] + KARA_BOX_H == ROOF_Y,
          f"still hanging {sym['HANG_HOLD'] - 6} frames after the key, back on "
          f"the roof at {back['wy'] + KARA_BOX_H} after "
          f"{sym['HANG_HOLD']}")

    print("\n  ... and the other answer:")
    mm = to_lip()
    mm.joystick(JOY_DOWN)
    mm.run_frames(sym["HANG_BEAT"] + 6)
    mm.joystick(0)
    mm.run_frames(6)
    mm.joystick(JOY_DOWN)                   # asked again, inside the window
    mm.run_frames(2)
    mm.joystick(0)
    let_go = st(mm, sym)
    check("pressing DOWN again inside the window lets go",
          let_go["state"] == sym["KST_DROP"] and let_go["ground"] == 0,
          f"KARA_STATE {let_go['state']} (DROP is {sym['KST_DROP']}) - letting "
          f"go is a fall she did not choose, not a jump")
    for _ in range(120):
        mm.run_frames(1)
        mm.poke(sym["PLAYER_HP"], 100)
        if mm.peek(sym["KARA_GROUND"]):
            break
    down = st(mm, sym)
    check("... and she falls to the street",
          down["wy"] + KARA_BOX_H == STREET_Y,
          f"feet at {down['wy'] + KARA_BOX_H}, pavement at {STREET_Y}")

    print("\n  the negative control - it is the LIP, not the key:")
    mm = boot(sym, scroll=True)
    mm.joystick(JOY_RIGHT)
    mm.run_frames(60)                       # out in the middle of the roof
    mm.joystick(0)
    mm.run_frames(2)
    mid = st(mm, sym)
    mm.joystick(JOY_DOWN)
    mm.run_frames(sym["HANG_BEAT"] + 20)
    ctl = st(mm, sym)
    check("DOWN in the middle of a floor is a crouch and nothing more",
          ctl["state"] == sym["KST_CROUCH"] and mm.peek(sym["KARA_HANG"]) == 0
          and ctl["wy"] == mid["wy"] and ctl["ground"] == 1,
          f"KARA_STATE {ctl['state']}, KARA_HANG {mm.peek(sym['KARA_HANG'])}, "
          f"still standing at {ctl['wy'] + KARA_BOX_H} - so the hang is the "
          f"floor running out and not the key")
    mm.joystick(0)

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
