#!/usr/bin/env python3
"""Module 5's own checks: rounds, and what firing costs the frame.

The pool holds SCREEN coordinates and the map is in WORLD ones, so the
whole of this is a coordinate conversion with a tile probe on the end,
and the way to test a conversion is to drive it from both sides: put a
solid tile under the round and it must die, put sky under it and it
must not. The map cell is chosen from the round's position by the test's
own arithmetic, not by the engine's, so the two have to agree.

And then: SHE HAS TO KEEP WALKING WHILE SHE FIRES. In the camera's push
zone her screen column never moves - the walk IS the scroll - so a frame
the loop drops while she is firing does not look like a dropped frame,
it looks like a character who has stopped. That is exactly how it was
reported, and it is the reason this suite counts her TRAVEL against the
loop rather than trusting a T-state model.
"""
import os
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import boot, symbols, sync, Bench                   # noqa: E402

STUB = 0x9400
MAP_ADDR, MAP_W = 0xA000, 128
BUL_STRIDE, EBUL_STRIDE = 5, 5
BUL_MAX = 14
# Attributes 0 and TA_SOLID. NOT `brick` (8) for the solid one any more:
# the building's facade is scenery now and only the roof and the pavement
# hold anything up (src/collide.asm), so a brick poked into a cell stops
# nothing and the check would pass for the wrong reason.
TILE_SKY, TILE_BRICK = 0, 26    # sky, sidewalk

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def cell_of(m, sym, sx, sy):
    """The map cell a round at screen (sx, sy) is over - the test's own
    reading of CLAUDE.md 8.3, not the engine's."""
    wx = sx + m.peek(sym["WORLD_X"]) * 2            # world bytes
    wy = (sy + m.peek(sym["WORLD_CR"]) * 8) & 0xFF  # world pixel row
    return MAP_ADDR + (wy >> 4) * MAP_W + ((wx >> 2) & (MAP_W - 1))


def run(m, sym, routine):
    a = sym[routine]
    m.write_ram(STUB, bytes([0xF3, 0xCD, a & 0xFF, a >> 8, 0x18, 0xFE]))
    m.set_pc(STUB)
    for _ in range(80000):
        m.run_us(1)
        if m.pc == STUB + 4:
            return
    raise SystemExit(f"{routine} ran away")


def fire(m, sym, pool, live, sx, sy, direction=0):
    """One round in slot 0 and nothing else in the pool.

    AND HOW DEEP THE POOL IS, for hers. BUL_TOP bounds every walk of it
    (src/bullets.asm) exactly as ENT_COUNT bounds the entity sweep, so a
    test that writes the table by hand has to write the bound too -
    left at 0 the engine correctly walks nothing and the round sits
    there for ever.
    """
    base = sym[pool]
    m.write_ram(base, bytes([1, sx, sy, direction, 60])
                + bytes(3 * BUL_STRIDE))
    m.poke(sym[live], 1)
    if "BUL_TOP" in sym and pool == "BULLETS":
        m.poke(sym["BUL_TOP"], 1)
    # AND WHICH FRAME OF THE THREE IT IS. Rounds hold still one frame in
    # BUL_SLOW (CLAUDE.md 8.5) and the counter belongs to the main loop,
    # which is not running under a DI stub - left where it was parked
    # the round correctly does not move and every check below reads as a
    # dead engine.
    m.poke(sym["BUL_PHASE"], sym["BUL_SLOW"])


def main():
    sym = symbols()
    m = boot(sym, scroll=True)
    m.run_frames(5)
    SY = m.peek(sym["KARA_WY"]) + 17 - m.peek(sym["WORLD_CR"]) * 8
    print(f"  her muzzle line is screen {SY}; WORLD_X={m.peek(sym['WORLD_X'])}")

    for pool, live, upd, name, speed in (
            ("BULLETS", "BUL_LIVE", "UPDATE_BULLETS", "her rounds", "BUL_SPEED"),
            ("EBULLETS", "EBUL_LIVE", "EBUL_UPDATE", "their rounds",
             "EBUL_SPEED")):
        print(f"\n  {name}:")
        # ---- over sky, it flies on --------------------------------
        # THE STEP IS THE ENGINE'S OWN CONSTANT AND NOT THE NUMBER 2.
        # At 50 Hz a round moved two bytes on two frames in three; a
        # game frame is two hardware frames now, so it moves FOUR and
        # takes every frame, and both pools say so themselves
        # (CLAUDE.md 9's table of what 25 Hz cost). Read off the build,
        # the next re-timing re-derives this instead of failing it.
        step = sym[speed]
        sx = 40
        cell = cell_of(m, sym, sx + step, SY)
        was = m.peek(cell)
        m.poke(cell, TILE_SKY)
        fire(m, sym, pool, live, sx, SY)
        run(m, sym, upd)
        alive_sky = m.peek(sym[pool])
        moved = m.peek(sym[pool] + 1)

        # ---- over a brick, it stops -------------------------------
        m.poke(cell, TILE_BRICK)
        fire(m, sym, pool, live, sx, SY)
        run(m, sym, upd)
        alive_wall = m.peek(sym[pool])
        m.poke(cell, was)

        check(f"{name}: a round over sky flies on",
              alive_sky == 1 and moved == sx + step,
              f"active={alive_sky}, x {sx} -> {moved}, and {speed} is {step}")
        check(f"{name}: a round that reaches a solid tile dies",
              alive_wall == 0, f"active={alive_wall}")
        check(f"{name}: and the pool's live count comes down with it",
              m.peek(sym[live]) == 0, f"{live}={m.peek(sym[live])}")

        # ---- the negative control ---------------------------------
        # A probe that ignored WORLD_X would read the map 2*WORLD_X
        # bytes to the left, which at this position is a different
        # cell: put a brick THERE and the round must NOT die.
        wrong = cell_of(m, sym, sx + step, SY) - (m.peek(sym["WORLD_X"]) * 2 >> 2)
        if wrong != cell:
            wwas = m.peek(wrong)
            m.poke(wrong, TILE_BRICK)
            fire(m, sym, pool, live, sx, SY)
            run(m, sym, upd)
            survived = m.peek(sym[pool])
            m.poke(wrong, wwas)
            check(f"{name}: a brick at the UNCONVERTED cell does not stop it",
                  survived == 1,
                  "the probe really is in world coordinates")

    firing_costs_her_nothing(sym)

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


JOY_RIGHT, JOY_FIRE = 0x08, 0x10
IN_FIRE = 0x10          # input.asm bit 4 - the same bit AIM_ROOTS_HER reads
FRAMES = 200


def walk(sym, pattern, frames=FRAMES, top=None, kill_enemies=False,
         no_hud=False):
    """Hold a joystick pattern and report (loop iterations, bytes travelled).

    `top` pokes BUL_TOP every frame, which is the negative control: it
    puts the pool walk back to the full BUL_MAX depth it used to run at.

    `no_hud` puts a RET at the top of HUD_SERVICE, which is the other
    control: the bottom row is fourteen characters now and a camera step
    leaves a word of them on the screen to be fetched back off the
    tilemap (CLAUDE.md 7.8), so it is what decides whether this walk's
    loop holds 50 Hz - and whether her travel can be compared against an
    expectation counted in HARDWARE frames.
    """
    m = boot(sym, scroll=True)
    if no_hud:
        m.poke(sym["HUD_SERVICE"], 0xC9)
    m.run_frames(5)
    # ANCHOR THE WINDOW TO THE TOP OF A GAME FRAME. A game frame is two
    # hardware ones, so `frames` of them hold exactly half that many
    # boundaries - but only if the window STARTS on one, and an
    # unanchored one reads a frame under or over by turns on a build
    # that has not changed. tools/test_enemies.py carries the sweep.
    sync(m, sym, half=0)
    f0 = m.peek(sym["FRAME_COUNT"])
    x0 = m.peek(sym["KARA_WX"]) | (m.peek(sym["KARA_WX"] + 1) << 8)
    peak, aim_frames, last_fc = 0, 0, m.peek(sym["FRAME_COUNT"])
    aim_taps, was_aiming = 0, False
    for t in range(frames):
        # THE PATTERN IS HANDED A GAME FRAME AND NOT A HARDWARE ONE, and
        # the two comments below are what that is for: everything this
        # routine reports - the frames she was planted on, the bytes she
        # covered, the step she takes on one game frame in two - is on
        # the game's clock, and a trigger written on the hardware's held
        # it down for three game frames in some of its windows and two
        # in the rest. AIM_ROOTS_HER refuses her step on a GAME frame,
        # so a window of three covers two of her step frames and a
        # window of two covers one: the same tap then cost her 34 bytes
        # where the count of aiming frames predicted 28, and the check
        # below failed for the sampler's arithmetic rather than the
        # engine's.
        m.joystick(pattern((m.peek(sym["FRAME_COUNT"]) - f0) % 256))
        if kill_enemies:
            m.poke(sym["ENEMY_LIVE"], 0)    # ENEMY_PICK then finds nobody
        if top is not None:
            m.poke(sym["BUL_TOP"], top)
        m.run_frames(1)
        # SAMPLED EVERY FRAME, not read at the end: UPDATE_BULLETS puts
        # the mark back to 0 the moment the pool empties, so the last
        # frame of a burst reports a pool that never existed.
        peak = max(peak, m.peek(sym["BUL_TOP"]))
        # ... AND THE FRAMES SHE SPENT PLANTED ARE COUNTED OFF THE
        # ENGINE AND NOT OFF THE PATTERN. The tap is written in HARDWARE
        # frames and AIM_ROOTS_HER refuses her step on a GAME frame,
        # which is two of them (CLAUDE.md 9) - so "half the aiming
        # frames" is only right when the tap's windows happen to line up
        # with the game's clock, and it was two bytes out when they did
        # not.
        #
        # IT IS THE INPUT BYTE AND NOT KARA_STATE, because the input
        # byte is what AIM_ROOTS_HER reads: `ld a,c / and IN_FIRE`
        # (player.asm). KARA_STATE spends fewer frames in KST_AIM than
        # the trigger spends down - the release runs four cels of KST_FIRE
        # and she walks through those - so counting the STATE came out
        # eleven bytes short of what she actually lost.
        #
        # AND WHAT IS COUNTED IS THE TAPS, NOT ONLY THE FRAMES. She
        # steps on one game frame in two inside the camera's push zone
        # (CLAUDE.md 8.2), and a tap holds the trigger down across one
        # or two consecutive game frames - so what a tap costs her is
        # ONE step, whichever of the two it covers, and a count of
        # aiming FRAMES is a count of 1s and 2s that does not divide by
        # anything. Measured frame by frame on this walk: three taps in
        # a row were seen as two aiming frames, one and two, and every
        # one of them cost her exactly one step of P_PUSH.
        fc = m.peek(sym["FRAME_COUNT"])
        if fc != last_fc:
            last_fc = fc
            if m.peek(sym["INPUT_NOW"]) & IN_FIRE:
                aim_frames += 1
                if not was_aiming:
                    aim_taps += 1
                was_aiming = True
            else:
                was_aiming = False
    loops = (m.peek(sym["FRAME_COUNT"]) - f0) % 256
    x1 = m.peek(sym["KARA_WX"]) | (m.peek(sym["KARA_WX"] + 1) << 8)
    m.joystick(0)
    return loops, x1 - x0, peak, (aim_frames, aim_taps)


def firing_costs_her_nothing(sym):
    """Firing must cost her no ground BEYOND the frames she spent aiming.

    THE TEST THAT MISSED THIS HELD THE TRIGGER. tools/test_enemies.py's
    "walking right + firing" holds FIRE down, and FIRE held is AIM
    (CLAUDE.md 8.4) - the gun is draw-hold-RELEASE, so a held trigger
    never puts a round in the air and the pool stays idle. Every check
    of "firing" was measuring a frame with an empty pool.

    AND "THE SAME GROUND AS A WALK" IS NO LONGER THE PROPERTY, because
    AIMING PLANTS HER NOW (CLAUDE.md 8.4): SPACE held is a stance and she
    does not walk out of it. So a tapped trigger costs her exactly the
    frames the trigger was down and not one more, which is a sharper
    statement than the old one and catches the same fault - dropped
    frames are ground lost on frames she was NOT aiming. The aiming
    frames are counted off the pattern itself, so re-timing the tap
    re-derives the expectation instead of invalidating it.
    """
    print("\n  firing while she walks:")
    for n in ("BUL_TOP", "BUL_DREW_TOP"):
        if n not in sym:
            check(f"the engine has {n}", False, "rebuild first")
            return

    plain, plain_x, _, _ = walk(sym, lambda t: JOY_RIGHT)
    held, held_x, held_top, _ = walk(sym, lambda t: JOY_RIGHT | JOY_FIRE)
    # TWO GAME FRAMES DOWN IN EVERY SIX - the same third of the time the
    # old four-in-twelve hardware pattern asked for, said on the clock
    # the engine reads the trigger on (walk() above).
    tap = (lambda g: JOY_RIGHT | (JOY_FIRE if (g % 6) < 2 else 0))
    fired, fired_x, peak, _ = walk(sym, tap)

    aiming = sum(1 for g in range(FRAMES // 2) if tap(g) & JOY_FIRE)

    print(f"    walking            {plain} loops, {plain_x} bytes")
    print(f"    walking + AIM      {held} loops, {held_x} bytes "
          f"(BUL_TOP {held_top} - a HELD trigger never fires)")
    print(f"    walking + firing   {fired} loops, {fired_x} bytes "
          f"(BUL_TOP peaked at {peak}, {aiming} of {FRAMES // 2} game "
          f"frames aiming)")

    check("a held trigger really is only AIM, and fires nothing",
          held_top == 0, "BUL_TOP stayed 0, so the pool never had a round in it")
    check("tapping it really does put rounds in the air",
          peak > 0, f"BUL_TOP reached {peak}")
    # AIMING IS A STANCE: SPACE down and she plants. Held for the whole
    # run she must not travel at all, and tapped she must lose exactly
    # the frames she held it for.
    check("holding SPACE plants her: she does not walk while she aims",
          held_x == 0, f"{held_x} bytes travelled with the trigger held down")
    # WHAT IT COSTS TO FIRE PAST A DRONE, with the encounter measured
    # rather than assumed. Tap-firing on a scrolling frame is 200 of 200
    # with nothing else on the screen; the drone's two unmissable frames
    # - the one it comes into view on and the one it leaves on (8.7) -
    # land on frames already carrying the heaviest cel in the game (9).
    alone, alone_x, _, _ = walk(sym, tap, kill_enemies=True)
    steady, steady_x, _, (aim_game, aim_taps) = walk(
        sym, tap, kill_enemies=True, no_hud=True)
    base, base_x, _, _ = walk(sym, lambda t: JOY_RIGHT,
                              kill_enemies=True, no_hud=True)
    print(f"    ... and with no drone   {alone} loops, {alone_x} bytes")
    print(f"    ... and no HUD either   {steady} loops, {steady_x} bytes")
    print(f"    ... the same, not firing {base} loops, {base_x} bytes")
    # AND THE FOUR FRAMES IT DOES COST ARE THE BOTTOM ROW, NOT THE GUN.
    # Measured on the same walk with HUD_SERVICE poked to RET: 201 loops
    # against 196, so the whole of the difference is the strip. Firing
    # spends a round, a spent round darkens a pip and the ammo cells are
    # written again - and on a frame that also stepped the camera, the
    # word the strip left behind has to come back off the TILEMAP at
    # ~59 T a byte (CLAUDE.md 7.8).
    # IT IS A COMPARISON AND NOT A FLOOR, and that is what 25 Hz changed
    # about it. "196 of 200" was a 50 Hz number - the lock was one loop
    # iteration per hardware frame - and the lock is 100 of 200 now
    # (CLAUDE.md 9), so the threshold measured nothing except the
    # migration it had not had. What the paragraph above actually claims
    # is a difference: the gun costs nothing, and the few frames that do
    # go are the strip. Measured that way it is sharper than the floor
    # ever was - with the strip silent, firing costs EXACTLY nothing.
    check("firing costs her nothing on its own",
          steady == base and alone >= steady - 2,
          f"{steady} loop iterations tap-firing against {base} walking, on "
          f"the same drone-free screen with the HUD silent - so the gun is "
          f"free; with the strip back it is {alone}, and that difference is "
          f"the strip (CLAUDE.md 7.8)")

    # AND THE PROPERTY IS MEASURED WITHOUT THE DRONE, which is the whole
    # point of having the drone-free run. "She loses exactly the frames
    # the trigger was down" is a statement about AIMING (8.4), and a
    # frame the loop drops is ground lost for a different reason
    # entirely. Against the drone-free walk the property is exact; with
    # the drone in it she covers fewer bytes still, and that difference
    # is the encounter, reported below rather than folded into a
    # tolerance. It was folded in until the land sheet was redrawn: the
    # drone then cost 12 bytes instead of 2 and a check about the gun
    # failed for something that is not the gun.
    # HALF THE AIMING FRAMES, AND THE ARITHMETIC SURVIVED 25 Hz FOR A
    # DIFFERENT REASON THAN IT WAS WRITTEN FOR. It used to be "she steps
    # on one frame in two, so half the aiming frames land on a step".
    # She steps on EVERY game frame now (PLAYER_STEP, CLAUDE.md 8.2) and
    # every aiming frame costs her one - but `aiming` is counted in the
    # tap pattern's own HARDWARE frames, and a game frame is two of them
    # (CLAUDE.md 9). Half of 68 hardware frames is 34 game frames, each
    # costing a byte. Same number, different derivation, and it still
    # re-derives from the pattern rather than being written down.
    # AND IT IS MEASURED ON THE RUN WHOSE LOOP HOLDS, which is the one
    # with the HUD off as well. The tap pattern is counted in HARDWARE
    # frames and her beat runs on the GAME's clock, so a frame the loop
    # drops slides the two against each other: in the push zone she
    # steps every fourth game frame and the trigger is down for four, so
    # a window that covered one step can come to cover none - two bytes,
    # per dropped frame. Measured, that is the whole of the difference:
    # 67 bytes with the strip off, which is exactly the expectation, and
    # 71 with it over four dropped frames.
    # AND IT IS COMPARED AGAINST A WALK THAT DIFFERS ONLY IN THE
    # TRIGGER - same drone-free screen, same silent HUD - because a
    # walk measured under a different load is a different number of
    # game frames and the difference would then be two things at once.
    # AND THE COUNT IS THE ENGINE'S. "Half the aiming frames" was the
    # right arithmetic for a tap written in hardware frames against a
    # 50 Hz loop; against a 25 Hz one it is right only when the tap's
    # windows happen to line up with the game's clock, and when they do
    # not it is two bytes out - one game frame she was planted on that
    # the halving did not count. walk() reads KARA_STATE on each game
    # frame instead, so what is subtracted is the frames the engine
    # actually refused her step on.
    # AND A FRAME COSTS 0 OR P_PUSH, NOT ALWAYS ONE BYTE. In the camera's
    # push zone she moves P_PUSH = 2 bytes on the camera's frame and
    # nothing on the frames between (CLAUDE.md 8.2), so a trigger-down
    # frame that lands on an off-frame costs her nothing and one that
    # lands on an on-frame costs two. One byte apiece is the AVERAGE,
    # and the sum was asserted to within a single push step.
    #
    # AND THAT AVERAGE IS NOT GOOD ENOUGH, WHICH ONLY SHOWED ONCE THE
    # SAMPLER STOPPED WOBBLING. A TAP is what costs her a step, not a
    # FRAME: the trigger is down across one or two consecutive game
    # frames and she steps on every other one, so each tap takes
    # exactly one step of P_PUSH whichever frames it covers. Counting
    # frames instead, the same walk came out 34 bytes lost against 29
    # frames seen aiming - five over a tolerance of two, and neither
    # number wrong. Counted in taps it is 17 of them, 34 bytes, exact.
    #
    # THE FRAME COUNT IS STILL WORTH HAVING and it is printed: a tap
    # seen as ONE aiming frame rather than two is the engine scanning
    # the joystick before the sampler moved it, which is a hardware
    # frame of slack in the driver and not something the engine did.
    push = sym["P_PUSH"]
    costs = push * aim_taps
    check("and tapping costs her the aiming frames and nothing else",
          steady == FRAMES // 2 and abs((base_x - steady_x) - costs) <= push,
          f"{steady_x} bytes against {base_x} walking - she lost "
          f"{base_x - steady_x} to {aim_taps} taps at {push} bytes the tap, "
          f"which is within one push step of {costs}; {aim_game} game frames "
          f"were seen with the trigger down; the loop held {steady} of "
          f"{FRAMES // 2} game frames, so none of it is a dropped frame")
    check("... and the strip's dropped frames move it by no more than they can",
          abs(alone_x - steady_x) <= 2 * abs(steady - alone) + 2,
          f"{alone_x} bytes in play against {steady_x} with the HUD off, over "
          f"{steady - alone} dropped frames - a dropped frame can move the tap "
          f"off one of her step frames and a push step is {2} bytes")
    # THE ENCOUNTER'S OWN COST, and it is the art's now. Her heaviest
    # `kcore` cel went from 284 span bytes to 323 in the redraw - 2,808 T
    # of composite at the blitter's 72 T floor - so a firing frame that
    # also carries a drone no longer fits. It was 4 frames of the 200;
    # measured after the redraw it is 16, and 14 bytes of ground with
    # them. tools/test_enemies.py carries the same move on its own five
    # paths.
    check("and a drone encounter costs at most sixteen frames of it",
          fired >= alone - 16,
          f"{fired} loop iterations against {alone} without the drone, "
          f"and {fired_x} bytes against {alone_x}")

    # THE NEGATIVE CONTROL: put the walk back to its old depth.
    #
    # BUL_TOP is what stops all four pool walks at the deepest slot ever
    # taken instead of at BUL_MAX. Holding it at BUL_MAX re-creates the
    # fault from outside the engine.
    #
    # AND IT IS MEASURED IN T-STATES, NOT IN DROPPED FRAMES. It used to
    # be a frame count with a threshold under it, and that made the
    # control a hostage to the frame's headroom: the day ENEMY_PICK gave
    # 2,200 T back the same fault dropped 9 frames in 200 instead of 32
    # and the threshold failed. What the mark actually does is take work
    # off the frame, so time the work.
    depth = {}
    for top in (1, BUL_MAX):
        mm = boot(sym, scroll=True)
        mm.run_frames(5)
        b = Bench(mm, sym)

        def setup(m2, top=top):
            m2.write_ram(sym["BULLETS"],
                         bytes([1, 40, 60, 0, 60]) + bytes(13 * BUL_STRIDE))
            m2.poke(sym["BUL_LIVE"], 1)
            m2.poke(sym["BUL_TOP"], top)
            m2.poke(sym["BUL_DREW_TOP"], top)
        depth[top] = {n: (b.T(n, setup) or 0) for n in
                      ("UPDATE_BULLETS", "BUL_DRAW", "BUL_ERASE",
                       "ENEMY_SHOT_CHECK")}
    print(f"\n  the four pool walks, ONE round in the air:")
    for n in depth[1]:
        print(f"    {n:<18} {depth[1][n]:6d} T at BUL_TOP 1, "
              f"{depth[BUL_MAX][n]:6d} at {BUL_MAX}")
    lean, fat = sum(depth[1].values()), sum(depth[BUL_MAX].values())
    print(f"    {'TOTAL':<18} {lean:6d} T          {fat:6d}"
          f"   -> {fat - lean} T of dead slots")
    check("the high-water mark is worth thousands of T a firing frame",
          fat - lean > 4000,
          f"{fat - lean} T between a walk bounded at the deepest slot taken "
          f"and one bounded at BUL_MAX")

    stuck, stuck_x, _, _ = walk(sym, tap, top=BUL_MAX)
    print(f"    ... and in play, with BUL_TOP forced to BUL_MAX: "
          f"{stuck} loops, {stuck_x} bytes")
    # AND IN PLAY IT COSTS FRAMES AND NO LONGER COSTS GROUND, which is
    # the entry in CLAUDE.md 8.5 arriving: "the in-play numbers are not
    # the negative control any more". With 160 T of headroom the dead
    # slots dropped 43 frames in 200 and 40 bytes of ground with them;
    # with a 159,744 T game frame the same 5,408 T of overrun mostly
    # fits, so it costs frames and she still covers her full distance.
    # The T-state bench above is the control now - that is why it was
    # written - and this stays as the in-play corroboration it can
    # honestly be.
    check("... and in play it still costs her frames",
          stuck < fired,
          f"{stuck} loops against {fired} on the SAME tap pattern, and "
          f"{stuck_x} bytes against {fired_x} - the ground no longer moves, "
          f"because 5,408 T of overrun fits in a 25 Hz frame where it did "
          f"not fit in a 50 Hz one")


if __name__ == "__main__":
    sys.exit(main())
