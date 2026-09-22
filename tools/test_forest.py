#!/usr/bin/env python3
"""Level 5 on a 6128: the forest, and the first map that is not the City's.

WHAT MAKES IT A CHECK AND NOT A SCREENSHOT is that nothing here knows
where the generator put anything. The bands, the branch platforms, the
pits and the cave are read back out of the level's OWN map through the
engine's own TILE_ATTR, and she is driven across it from the joystick.

THE TRANSITION IS THE WAY IN, not a DI stub. Calling LEVEL_GOTO from
one installs the level and leaves the PC in the stub's own `jr $`, so
run_frames() afterwards spins there and the game never takes another
step - she sat at her start position through 1,200 frames of RIGHT and
it read like a level she could not walk. FLOW_STEP goes to
LEVEL_CUR + 1, so the way in is the way the game does it.

AND A PLAYER JUMPS WHEN SHE STOPS. The pits are a step DOWN into and
not a gap across: she falls the 16 pixels onto the dirt and the grass
on the far side is then a wall to a walk. Holding RIGHT alone she stops
at the first one - the level working, and a driver that only walks
measuring a level it cannot play.

ITS CONTROL IS THE BRANCHES. Take TA_PLATFORM off them and the level
still loads, still walks and still looks right - and the key, which is
on one, is somewhere she can no longer stand.
"""
import os
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import boot, symbols, sync                          # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TA_SOLID, TA_PLATFORM, TA_HAZARD = 1, 2, 4
JOY_RIGHT, JOY_UP = 0x08, 0x01
GS_CLEAR = 2
LEVEL, ENV = 5, 2                       # level 5 of 24, environment 2
MAP_W, MAP_H = 128, 16
ROW_BRANCH = (5, 7)
ROW_GROUND = 9

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def word(m, a):
    return m.peek(a) | m.peek(a + 1) << 8


def to_forest(sym):
    """Boot on the City and walk out of it into level 5."""
    m = boot(sym, scroll=True)
    m.poke(sym["LEVEL_CUR"], LEVEL - 2)         # ... so the next one is ours
    m.poke(sym["GAME_STATE"], GS_CLEAR)
    for f in range(900):
        m.run_frames(1)
        if (m.peek(sym["GAME_STATE"]) == 0
                and m.peek(sym["LEVEL_CUR"]) == LEVEL - 1):
            m.run_frames(10)
            return m, f
    return m, None


def drive(m, sym, tile, limit=4000):
    """Right, and UP whenever she has not moved for eight frames."""
    stuck = was = 0
    for _ in range(limit):
        wx = word(m, sym["KARA_WX"])
        if (wx + 3) // 4 >= tile:
            break
        stuck = stuck + 1 if wx == was else 0
        was = wx
        m.joystick(JOY_RIGHT | (JOY_UP if stuck >= 8 else 0))
        if stuck >= 8:
            stuck = 0
        m.run_frames(1)
    m.joystick(0)
    m.run_frames(4)
    return (word(m, sym["KARA_WX"]) + 3) // 4


def bands(m, sym):
    """What the ENGINE thinks each row of the level is."""
    g = bytes(m.read_ram(sym["MAP_ADDR"], MAP_W * MAP_H))
    attr = bytes(m.read_ram(sym["TILE_ATTR"], 256))
    out = {}
    for r in range(MAP_H):
        k = [attr[g[r * MAP_W + x]] for x in range(MAP_W)]
        out[r] = (sum(1 for a in k if a & TA_SOLID),
                  sum(1 for a in k if a & TA_PLATFORM),
                  sum(1 for a in k if a & TA_HAZARD))
    return out, g, attr


def main():
    sym = symbols()
    print("\n  out of the City and into the forest:")
    m, frames = to_forest(sym)
    check("the transition finished", frames is not None,
          f"{frames} hardware frames - an ENVIRONMENT change, so the art "
          f"was reloaded too" if frames else "GAME_STATE never came back")
    if frames is None:
        return 1

    lvl = m.read_ram(sym["LEVEL_LVL"], 21)
    w, h = lvl[5] | lvl[6] << 8, lvl[7] | lvl[8] << 8
    check("it is level 5's map, in the forest's art",
          m.peek(sym["LEVEL_OK"]) == 1 and (w, h) == (MAP_W, MAP_H)
          and lvl[9] == ENV and m.peek(sym["LEVEL_ENV"]) == ENV - 1,
          f"LEVEL_OK {m.peek(sym['LEVEL_OK'])}, {w}x{h}, tileset {lvl[9]}, "
          f"LEVEL_ENV {m.peek(sym['LEVEL_ENV'])}, "
          f"ENT_COUNT {m.peek(sym['ENT_COUNT'])}")

    print("\n  the bands, as the engine reads them:")
    rows, g, attr = bands(m, sym)
    for r in range(MAP_H):
        if any(rows[r]):
            print(f"    row {r:2d}: {rows[r][0]:3d} solid, {rows[r][1]:2d} "
                  f"platform, {rows[r][2]:2d} hazard")
    check("the ground is a floor with pits cut in it",
          rows[ROW_GROUND][0] > MAP_W - 20 and rows[ROW_GROUND][2] > 0,
          f"{rows[ROW_GROUND][0]} solid and {rows[ROW_GROUND][2]} hazard "
          f"of {MAP_W} - and TA_HAZARD has no reader, so a pit is a dip")
    check("the branches are PLATFORM and nothing else is",
          all(rows[r][1] > 0 and rows[r][0] == 0 for r in ROW_BRANCH)
          and sum(rows[r][1] for r in range(MAP_H)
                  if r not in ROW_BRANCH) == 0,
          f"rows {list(ROW_BRANCH)}: "
          f"{[rows[r][1] for r in ROW_BRANCH]} tiles, no solid among them")
    check("the canopy and the trunks are BACKGROUND",
          all(rows[r] == (0, 0, 0) for r in range(0, 5)),
          "rows 0-4 carry nothing - made solid, a tree is a wall across "
          "the level and the mountain is the end of it (CLAUDE.md 8.8)")

    print("\n  and she walks it:")
    start = (word(m, sym["KARA_WX"]) + 3) // 4
    check("she landed on the grass", word(m, sym["KARA_WY"]) == ROW_GROUND * 16 - 64,
          f"WY {word(m, sym['KARA_WY'])}, at tile {start} - the record is a "
          f"row high on purpose and she falls the last 16 pixels")
    ammo0 = m.peek(sym["AMMO_RESERVE"])
    got = drive(m, sym, MAP_W - 4)
    check("she reached the far end of the level", got >= MAP_W - 4,
          f"tile {start} -> {got} of {MAP_W}, "
          f"view ({m.peek(sym['WORLD_X'])},{m.peek(sym['WORLD_CR'])})")
    check("... and picked the clip up on the way",
          m.peek(sym["AMMO_RESERVE"]) > ammo0,
          f"AMMO_RESERVE {ammo0} -> {m.peek(sym['AMMO_RESERVE'])}")
    check("... and nothing hurt her", m.peek(sym["PLAYER_HP"]) == 100,
          f"HP {m.peek(sym['PLAYER_HP'])} - the pits are 16 pixels, free "
          f"against FALL_FREE of 96, and the level carries no enemy")

    print("\n  the loop, in a level with no enemy in it:")
    sync(m, sym, half=0)
    a = m.peek(sym["FRAME_COUNT"])
    for _ in range(200):
        m.run_frames(1)
    games = (m.peek(sym["FRAME_COUNT"]) - a) & 255
    check("it holds the 25 Hz lock", games == 100,
          f"{games} game frames in 200 hardware - and a 12x64 sniper "
          f"standing here measured 80, which is why level 5 carries none")

    # ---- the control: the branches -------------------------------
    print("\n  and with TA_PLATFORM taken off the branches:")
    m2, _ = to_forest(sym)
    rows2, g2, attr2 = bands(m2, sym)
    branch_tiles = {g2[r * MAP_W + x] for r in ROW_BRANCH
                    for x in range(MAP_W) if attr2[g2[r * MAP_W + x]] & TA_PLATFORM}
    for t in branch_tiles:
        m2.poke(sym["TILE_ATTR"] + t, attr2[t] & ~TA_PLATFORM)
    rows3, _, _ = bands(m2, sym)
    check("the level still loads and the map is untouched",
          rows3[ROW_GROUND][0] == rows[ROW_GROUND][0],
          f"{len(branch_tiles)} tile indices changed their ATTRIBUTE and no "
          f"map byte moved - which is what makes the next line about the "
          f"flag and not about the picture")
    check("... and the branches stop being a floor",
          all(rows3[r][1] == 0 for r in ROW_BRANCH),
          "so the key, which sits on one, is somewhere she cannot stand")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
