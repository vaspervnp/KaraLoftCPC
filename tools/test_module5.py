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
from bench import boot, symbols                                # noqa: E402

STUB = 0x9400
MAP_ADDR, MAP_W = 0xA000, 128
BUL_STRIDE, EBUL_STRIDE = 5, 5
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


def main():
    sym = symbols()
    m = boot(sym, scroll=True)
    m.run_frames(5)
    SY = m.peek(sym["KARA_WY"]) + 17 - m.peek(sym["WORLD_CR"]) * 8
    print(f"  her muzzle line is screen {SY}; WORLD_X={m.peek(sym['WORLD_X'])}")

    for pool, live, upd, name in (("BULLETS", "BUL_LIVE", "UPDATE_BULLETS",
                                   "her rounds"),
                                  ("EBULLETS", "EBUL_LIVE", "EBUL_UPDATE",
                                   "their rounds")):
        print(f"\n  {name}:")
        # ---- over sky, it flies on --------------------------------
        sx = 40
        cell = cell_of(m, sym, sx + 2, SY)
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
              alive_sky == 1 and moved == sx + 2,
              f"active={alive_sky}, x {sx} -> {moved}")
        check(f"{name}: a round that reaches a solid tile dies",
              alive_wall == 0, f"active={alive_wall}")
        check(f"{name}: and the pool's live count comes down with it",
              m.peek(sym[live]) == 0, f"{live}={m.peek(sym[live])}")

        # ---- the negative control ---------------------------------
        # A probe that ignored WORLD_X would read the map 2*WORLD_X
        # bytes to the left, which at this position is a different
        # cell: put a brick THERE and the round must NOT die.
        wrong = cell_of(m, sym, sx + 2, SY) - (m.peek(sym["WORLD_X"]) * 2 >> 2)
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
FRAMES = 200


def walk(sym, pattern, frames=FRAMES, top=None):
    """Hold a joystick pattern and report (loop iterations, bytes travelled).

    `top` pokes BUL_TOP every frame, which is the negative control: it
    puts the pool walk back to the full BUL_MAX depth it used to run at.
    """
    m = boot(sym, scroll=True)
    m.run_frames(5)
    f0 = m.peek(sym["FRAME_COUNT"])
    x0 = m.peek(sym["KARA_WX"]) | (m.peek(sym["KARA_WX"] + 1) << 8)
    peak = 0
    for t in range(frames):
        m.joystick(pattern(t))
        if top is not None:
            m.poke(sym["BUL_TOP"], top)
        m.run_frames(1)
        # SAMPLED EVERY FRAME, not read at the end: UPDATE_BULLETS puts
        # the mark back to 0 the moment the pool empties, so the last
        # frame of a burst reports a pool that never existed.
        peak = max(peak, m.peek(sym["BUL_TOP"]))
    loops = (m.peek(sym["FRAME_COUNT"]) - f0) % 256
    x1 = m.peek(sym["KARA_WX"]) | (m.peek(sym["KARA_WX"] + 1) << 8)
    m.joystick(0)
    return loops, x1 - x0, peak


def firing_costs_her_nothing(sym):
    """Walking and firing must cost her no ground against walking.

    THE TEST THAT MISSED THIS HELD THE TRIGGER. tools/test_enemies.py's
    "walking right + firing" holds FIRE down, and FIRE held is AIM
    (CLAUDE.md 8.4) - the gun is draw-hold-RELEASE, so a held trigger
    never puts a round in the air and the pool stays idle. Every check
    of "firing" was measuring a frame with an empty pool.
    """
    print("\n  firing while she walks:")
    for n in ("BUL_TOP", "BUL_DREW_TOP"):
        if n not in sym:
            check(f"the engine has {n}", False, "rebuild first")
            return

    plain, plain_x, _ = walk(sym, lambda t: JOY_RIGHT)
    held, held_x, held_top = walk(sym, lambda t: JOY_RIGHT | JOY_FIRE)
    tap = (lambda t: JOY_RIGHT | (JOY_FIRE if (t % 12) < 4 else 0))
    fired, fired_x, peak = walk(sym, tap)

    print(f"    walking            {plain} loops, {plain_x} bytes")
    print(f"    walking + AIM      {held} loops, {held_x} bytes "
          f"(BUL_TOP {held_top} - a HELD trigger never fires)")
    print(f"    walking + firing   {fired} loops, {fired_x} bytes "
          f"(BUL_TOP peaked at {peak})")

    check("a held trigger really is only AIM, and fires nothing",
          held_top == 0, "BUL_TOP stayed 0, so the pool never had a round in it")
    check("tapping it really does put rounds in the air",
          peak > 0, f"BUL_TOP reached {peak}")
    check("she keeps her ground while firing",
          fired_x >= plain_x - 4,
          f"{fired_x} bytes against {plain_x} walking - at most 4 behind")
    check("and the loop still holds 50 Hz",
          fired >= 197, f"{fired} loop iterations in {FRAMES} hardware frames")

    # THE NEGATIVE CONTROL: put the walk back to its old depth.
    #
    # BUL_TOP is what stops all four pool walks at the deepest slot ever
    # taken instead of at BUL_MAX. Holding it at BUL_MAX re-creates the
    # fault from outside the engine: 6,228 T a frame of dead slots, the
    # loop drops frames, and because her screen column is fixed in the
    # camera's push zone what the player sees is a character who has
    # stopped walking.
    stuck, stuck_x, _ = walk(sym, tap, top=14)
    print(f"    ... with BUL_TOP forced to BUL_MAX: {stuck} loops, {stuck_x} bytes")
    check("without the high-water mark she loses ground, which is the bug",
          stuck_x < plain_x - 20 and stuck < 190,
          f"{stuck_x} bytes and {stuck} loops - the dead slots are what cost her")


if __name__ == "__main__":
    sys.exit(main())
