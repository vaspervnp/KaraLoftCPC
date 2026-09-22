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


CITY_HAZARD = None      # what LEVEL_HAZARD says in level 1, read while the
                        # machine is still standing in it - see the control


def to_forest(sym, level=LEVEL):
    """Boot on the City and walk out of it into one of the forest's levels.

    THE WAY IN IS THE WAY THE GAME GOES and not a DI stub: FLOW_STEP
    goes to LEVEL_CUR + 1, so LEVEL_CUR is set to one before the one
    wanted and GS_CLEAR does the rest.

    AND IT WAITS FOR THE FSM TO COME BACK TO PLAY, not for LEVEL_ENV.
    The environment is claimed BEFORE the read (CLAUDE.md 8.1) and
    LEVEL_OK is still 1 from the level being left, so a driver that
    waits on either of those is reading the LAST level's map: measured,
    27 frames in, TILE_ATTR still held the City's.
    """
    global CITY_HAZARD
    m = boot(sym, scroll=True)
    CITY_HAZARD = m.peek(sym["LEVEL_HAZARD"])
    m.poke(sym["LEVEL_CUR"], level - 2)         # ... so the next one is ours
    m.poke(sym["GAME_STATE"], GS_CLEAR)
    for f in range(900):
        m.run_frames(1)
        if (m.peek(sym["GAME_STATE"]) == 0
                and m.peek(sym["LEVEL_CUR"]) == level - 1):
            m.run_frames(10)
            return m, f
    return m, None


def drive(m, sym, tile, limit=4000, hurts=None):
    """Right, and UP whenever she has not moved for eight frames.

    `hurts`, when a list is passed, collects (tile, points) for every
    frame PLAYER_HP went DOWN - which is what says a pit bit her, and
    where. It has to be sampled per frame rather than read at the end:
    the level carries a medkit, USE_MEDKIT caps at HP_MAX, and a net
    figure across the walk cannot tell four bites and a cap from three.
    """
    stuck = was = 0
    hp = m.peek(sym["PLAYER_HP"])
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
        now = m.peek(sym["PLAYER_HP"])
        if hurts is not None and now < hp:
            hurts.append(((wx + 3) // 4, hp - now))
        hp = now
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
          f"of {MAP_W} - and the hazard bit has a reader now, below")
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
    hurts = []
    got = drive(m, sym, MAP_W - 4, hurts=hurts)
    check("she reached the far end of the level", got >= MAP_W - 4,
          f"tile {start} -> {got} of {MAP_W}, "
          f"view ({m.peek(sym['WORLD_X'])},{m.peek(sym['WORLD_CR'])})")
    check("... and picked the clip up on the way",
          m.peek(sym["AMMO_RESERVE"]) > ammo0,
          f"AMMO_RESERVE {ammo0} -> {m.peek(sym['AMMO_RESERVE'])}")
    # ---- AND THE PITS TOOK THEIR BITE, which they did not until
    # TA_HAZARD got its first reader (CLAUDE.md 8.11). This check used
    # to be "nothing hurt her, HP 100" and it was true for the wrong
    # reason: the level carries no enemy and a 16-pixel pit is free
    # against FALL_FREE of 96, so the ONLY thing that could hurt her
    # here was the spikes, and nothing read them.
    pits = sum(1 for r in range(MAP_H) for x in range(MAP_W)
               if attr[g[r * MAP_W + x]] & TA_HAZARD
               and (x == 0 or not attr[g[r * MAP_W + x - 1]] & TA_HAZARD))
    bite = sym["TILE_HURT"]          # off the build, not written down here
    check("... and the spikes bit her, once for each pit",
          len(hurts) == pits and all(c == bite for _, c in hurts),
          f"{len(hurts)} bites of {bite} at tiles "
          f"{[t for t, _ in hurts]}, against {pits} pits - one an ENTRY, "
          f"because twelve frames of contact at any damage worth the "
          f"name is instant death")
    check("... and she was still alive at the end of it",
          0 < m.peek(sym["PLAYER_HP"]) < 100,
          f"HP {m.peek(sym['PLAYER_HP'])} - the medkit at tile 62 is "
          f"why this is not 100 - {pits} * {bite}")

    print("\n  the loop, in a level with no enemy in it:")
    sync(m, sym, half=0)
    a = m.peek(sym["FRAME_COUNT"])
    for _ in range(200):
        m.run_frames(1)
    games = (m.peek(sym["FRAME_COUNT"]) - a) & 255
    check("it holds the 25 Hz lock", games == 100,
          f"{games} game frames in 200 hardware - and a 12x64 sniper "
          f"standing here measured 80, which is why level 5 carries none")

    # ---- LEVEL 6, which is where level 5's door has always led ----
    # LEVEL_GOTO goes to LEVEL_CUR + 1 (CLAUDE.md 8.1) and level 5 ends
    # at an EK_DOOR in its cave mouth, so this is not a second map that
    # happens to exist - it is the one that door has been pointing at
    # since the day it was placed.
    print("\n  and level 6, through the cave mouth level 5 ends at:")
    m6, f6 = to_forest(sym, 6)
    check("she arrives in level 6", m6.peek(sym["LEVEL_CUR"]) == 5,
          f"{f6} hardware frames, LEVEL_CUR {m6.peek(sym['LEVEL_CUR'])} - "
          f"and LEVEL_ENV did NOT move, because levels 5-8 are one "
          f"environment and one bank set")
    check("... and it is the forest's art, not a second load of it",
          m6.peek(sym["LEVEL_ENV"]) == ENV - 1,
          f"LEVEL_ENV {m6.peek(sym['LEVEL_ENV'])}, ENT_COUNT "
          f"{m6.peek(sym['ENT_COUNT'])}")

    rows6, g6, attr6 = bands(m6, sym)
    check("it opens ON the cave floor she came out of",
          attr6[g6[ROW_GROUND * MAP_W + 3]] & TA_SOLID
          and not any(attr6[g6[r * MAP_W + 3]] for r in range(5, ROW_GROUND)),
          f"tile 3 of the ground row holds her up and the six rows above "
          f"it carry nothing - which is a cave mouth read as an ENTRANCE, "
          f"the same tiles level 5 uses as an exit")
    check("its ground is cut in three and not four",
          rows6[ROW_GROUND][2] == 8,
          f"{rows6[ROW_GROUND][2]} tiles of spike against level 5's "
          f"{rows[ROW_GROUND][2]} - three pits, every one at most 3 tiles, "
          f"which a RUN clears and a walk does not (CLAUDE.md 8.8)")

    # THE CLIMB IS THE LEVEL AND THE FLOOD FILL ONLY MODELS IT. The key
    # sits two branches up - ground to row 7, row 7 to row 5, each
    # inside the two rows her 36-pixel jump reaches - and
    # make_forest_map.py refuses a level whose key it cannot reach. That
    # is a conservative model of a walk; this is the walk.
    GROUND_WY, B7_WY, B5_WY = ROW_GROUND * 16 - 64, 7 * 16 - 64, 5 * 16 - 64
    stood, last, stuck = set(), -1, 0
    for _ in range(3000):
        x, y = word(m6, sym["KARA_WX"]), word(m6, sym["KARA_WY"])
        stood.add(y)
        stuck = stuck + 1 if x == last else 0
        last = x
        joy = JOY_RIGHT
        if y == GROUND_WY and 60 <= x // 4 <= 64:
            joy |= JOY_UP                       # under the low branch
        elif y == B7_WY and 63 <= x // 4 <= 66:
            joy |= JOY_UP                       # ... and up again
        elif stuck > 8:
            joy |= JOY_UP
        m6.joystick(joy)
        m6.run_frames(1)
        if m6.peek(sym["KEYS_COUNT"]) or x // 4 > 80:
            break
    m6.joystick(0)
    check("she climbs two branches and takes the key",
          m6.peek(sym["KEYS_COUNT"]) == 1,
          f"KEYS_COUNT {m6.peek(sym['KEYS_COUNT'])}, and she stood at "
          f"KARA_WY {sorted(y for y in stood if y in (GROUND_WY, B7_WY, B5_WY))}"
          f" - the ground, the row-7 branch and the row-5 one")

    # ---- AND WHAT SHE CARRIES FROM ONE INTO THE OTHER --------------
    # Her health crosses a door and this level's key does not (8.1), so
    # two levels of spikes in a row is a question neither of them can
    # answer alone - and it only became a question when TA_HAZARD got a
    # reader (8.12).
    print("\n  and the two of them in sequence:")
    ms, _ = to_forest(sym, 5)
    h5 = []
    drive(ms, sym, MAP_W - 4, hurts=h5)
    carried = ms.peek(sym["PLAYER_HP"])
    ms.poke(sym["LEVEL_CUR"], 4)
    ms.poke(sym["GAME_STATE"], GS_CLEAR)
    for _ in range(900):
        ms.run_frames(1)
        if (ms.peek(sym["GAME_STATE"]) == 0
                and ms.peek(sym["LEVEL_CUR"]) == 5):
            ms.run_frames(10)
            break
    check("her health crossed the door", ms.peek(sym["PLAYER_HP"]) == carried,
          f"{carried} out of level 5 and {ms.peek(sym['PLAYER_HP'])} into "
          f"level 6 - a door is not a medkit")
    h6 = []
    drive(ms, sym, MAP_W - 4, hurts=h6)
    end = ms.peek(sym["PLAYER_HP"])
    check("... and she is alive at the end of both", 0 < end,
          f"100 -> {carried} -> {end}, {len(h5)} bites in level 5 and "
          f"{len(h6)} in level 6 against a medkit in each")

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

    # ---- the control: the hazard's reader -------------------------
    # THE BITE ABOVE PROVES NOTHING WITHOUT THIS. Every other thing in
    # the level that could take a point off her is absent by design -
    # no enemy, and a 16-pixel pit is free against FALL_FREE - so a
    # check that merely watched HP fall would pass on a build where
    # something else entirely was hurting her. HAZARD_HURT returning
    # at once is the engine as it was before it had a reader.
    print("\n  and with HAZARD_HURT taken back out:")
    m4, _ = to_forest(sym)
    m4.poke(sym["HAZARD_HURT"], 0xC9)                   # RET
    hurts4 = []
    got4 = drive(m4, sym, MAP_W - 4, hurts=hurts4)
    check("she still walks the whole level", got4 >= MAP_W - 4,
          f"tile -> {got4} of {MAP_W} - the pits are still a dip she "
          f"falls into and jumps out of, which is what they always were")
    check("... and the spikes cost her nothing at all",
          not hurts4 and m4.peek(sym["PLAYER_HP"]) == 100,
          f"{len(hurts4)} bites, HP {m4.peek(sym['PLAYER_HP'])}")

    # ... and the City, which has no hazard tile in it, must not pay
    # for the probe or notice it is there.
    check("and the City claims no hazard at all",
          CITY_HAZARD == 0 and m.peek(sym["LEVEL_HAZARD"]) == TA_HAZARD,
          f"LEVEL_HAZARD: city {CITY_HAZARD}, forest "
          f"{m.peek(sym['LEVEL_HAZARD'])} - so HAZARD_HURT is three "
          f"instructions and a RET in four of the six environments")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
