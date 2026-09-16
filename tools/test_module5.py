#!/usr/bin/env python3
"""Module 5's own checks: a round that meets a wall stops there.

The pool holds SCREEN coordinates and the map is in WORLD ones, so the
whole of this is a coordinate conversion with a tile probe on the end,
and the way to test a conversion is to drive it from both sides: put a
solid tile under the round and it must die, put sky under it and it
must not. The map cell is chosen from the round's position by the test's
own arithmetic, not by the engine's, so the two have to agree.
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
    """One round in slot 0 and nothing else in the pool."""
    base = sym[pool]
    m.write_ram(base, bytes([1, sx, sy, direction, 60])
                + bytes(3 * BUL_STRIDE))
    m.poke(sym[live], 1)


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

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
