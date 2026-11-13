#!/usr/bin/env python3
"""Level 4 on a 6128: the City's last map, and the way out of it.

Level 3's garage leads here and level 4 opens on it drawn OPEN. It is
the two maps before it end to end - level 2's rooftop jumps, one of
every shape that level measured, and level 3's plaza, down off the
tallest roof by the ledge and up the next building's ladder past a
barricade - and its way out is the garage plan.md ends the City at,
which leads to level 5: the forest, an ENVIRONMENT away, so the door
reads the forest's art and not one sector (CLAUDE.md 8.1).

As in tools/test_city.py and tools/test_city3.py, nothing here knows
where the generator put anything: the roofs, the gaps, the plaza, the
barricades and the ladders are read back out of the level's own map
through the engine's own TILE_ATTR, and she is driven from the
joystick.
"""
import os
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import symbols, sync                                # noqa: E402
import make_city_map as city                                   # noqa: E402
import test_city as tc                                         # noqa: E402
from test_city import (JOY, PAVEMENT, V_CR_MAX, EK_PICKUP,     # noqa: E402
                       GS_CLEAR, EF_TAKEN, walk_to, run_east, fall, window)
from test_city3 import (City3, walk_east, to_lip, hang_and_drop,  # noqa: E402
                        walk_off, walk_off_west, climb_at)
import test_module4 as t4                                      # noqa: E402

BUILD = tc.BUILD
LEVEL = 4
FOREST = 1                  # LEVEL_ENV, 0 based: the City is 0
fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def city4(sym, names, drones=False):
    return City3(sym, names, drones=drones, level=LEVEL)


def tileset(c):
    """Every tile a map byte can name: the City's blob as the build wrote
    it, and the bake's sixteen scratch tiles out of bank C4 (8.6)."""
    blob = open(os.path.join(BUILD, "levels", "level1_city",
                             "citytiles.bin"), "rb").read()
    t = bytearray(256 * 64)
    t[:len(blob)] = blob
    t[240 * 64:] = t4.read_tile_bank(c.m, c.sym, 1024, 0x7C00)
    return t


def wrong_cells(c, tiles):
    """The character cells of the playfield that are not the map, at a
    half=0 sync - she is erased and the background is finished, so
    there is nothing else on it with the drones off. Columns 0 and 39
    are left out because a pending column's head is painted there a
    frame before its latch (8.2), and so is the strip, which is not
    the map."""
    m = c.m
    lm = t4.live_map(m)
    scroll, wx, wcr = c.word("SCROLL"), c.byte("WORLD_X"), c.byte("WORLD_CR")
    out = []
    for cr in range(24):
        for x in range(1, 39):
            if cr == 23 and x < c.sym["HUD_STRIP_CELLS"]:
                continue
            want = {}
            t4.paint_cell(want, tiles, lm, scroll, wx, wcr, cr, x)
            if any(m.peek(a) != v for a, v in want.items()):
                out.append((cr, x))
    return out


def drone_cells(c):
    """The character cells round the drone's drawn box, which is the one
    thing on the playfield at a sync that is not the map.

    THE BOX AS IT WAS DRAWN, NOT ENEMY_SX. At a half=0 sync ENEMY_SX is
    already the NEXT frame's - ENEMY_PICK_NEXT works it out at the end
    of the second sweep, after the drone has moved and in the view
    H_COMMIT is about to latch (CLAUDE.md 8.7) - so it can be two
    characters from the pixels on the screen. ENEMY_DREW_WX is where the
    refresh put them, and WORLD_X is still the view they are in."""
    if not c.byte("ENEMY_DREW"):
        return set()
    sx = (c.word("ENEMY_DREW_WX") - 2 * c.byte("WORLD_X")) & 0xFFFF
    if sx >= 0x8000:
        sx -= 0x10000
    w = c.byte("ENEMY_DREW_W")
    bot, cnt = c.byte("ENEMY_LAST_BOT"), c.byte("ENEMY_LAST_CNT")
    top = bot - cnt + 1
    return {(r, x) for r in range(max(0, top // 8 - 1), min(23, bot // 8 + 1) + 1)
            for x in range(max(0, sx // 2 - 1), min(39, (sx + w) // 2 + 1) + 1)}


def fight(c, frames=400):
    """Turn to the drone that is following her and shoot it down.

    A DRIVE UNDER FIRE IS A DRIVE THAT FIRES BACK NOW. A drone that has
    been on the screen follows her until one of them is dead (CLAUDE.md
    8.7), at her chest and in its own sights, so a player who never
    shoots back is shot down - 8 points every 35 game frames, which is
    the level 4 drive's length three times over. The gun is draw-hold-
    release (8.4): FIRE with a direction turns her without walking her,
    letting go fires. True once nothing is following her."""
    es_hp = c.sym["ES_HP"]
    for t in range(frames):
        eng = c.word("ENEMY_ENG")
        if not eng:
            c.m.joystick(0)
            return True
        aim = 0
        if c.m.peek(eng + es_hp):           # alive: falling ones are done
            ex = c.m.peek(eng + c.sym["ES_X"]) | c.m.peek(eng + c.sym["ES_X"] + 1) << 8
            her = c.word("KARA_WX") + c.sym["KARA_BOX_W"] // 2
            side = JOY["right"] if (ex >> 1) + 4 > her else JOY["left"]
            aim = side | JOY["fire"] if t % 6 < 3 else 0
        c.m.joystick(aim)
        c.step()
    c.m.joystick(0)
    return False


def fall_watch(c, tiles, x1, frames=80):
    """Walk east off the roof that ends at column x1 and land, sampling
    the playfield every game frame. [(frame, wrong cells)], and only
    the samples that had any."""
    to_lip(c, x1)
    c.m.joystick(JOY["right"])
    seen, air = [], False
    for f in range(frames):
        c.step()
        sync(c.m, c.sym, half=0)
        ground = c.byte("KARA_GROUND")
        air = air or not ground
        w = wrong_cells(c, tiles)
        if w:
            seen.append((f, w))
        if air and ground:
            c.m.joystick(0)
    return seen


def openings(c):
    """(first column, width, near roof, far roof) between buildings."""
    B = c.buildings()
    return [(a1 + 1, b0 - a1 - 1, ra, rb)
            for (_, a1, ra), (b0, _, rb) in zip(B, B[1:])]


def main():
    sym = symbols()
    print("Level 4: the City's last, and the way out of it\n")
    names = city.tile_names()[1]
    names = names + [f"baked_{i}" for i in range(256 - len(names))]
    shipped = open(os.path.join(BUILD, f"level_{LEVEL}.lvl"), "rb").read()

    c = city4(sym, names)
    print("  out of level 3's garage:")
    check("the garage leads here", c.frames is not None,
          f"{c.frames} hardware frames, fade and all")
    check("... and it is one sector, not an environment",
          c.byte("LEVEL_ENV") == 0 and c.byte("LEVEL_CUR") == LEVEL - 1,
          f"LEVEL_ENV {c.byte('LEVEL_ENV')} - no art came with it")
    check("the level is the file on the disc",
          bytes(c.hdr) + c.map == shipped[:21 + 2048]
          and (c.w, c.h, c.hdr[3], c.hdr[9]) == (128, 16, LEVEL, 1)
          and c.byte("LEVEL_OK") == 1,
          f"{c.w}x{c.h}, level {c.hdr[3]}, tileset {c.hdr[9]}")
    check("the drones are in it", c.spawned == 3,
          f"{c.spawned} spawned, held off for the drive and back on below")
    opening = [x for x in range(c.w - 3)
               if c.name(x + 1, city.ROW_PAVEMENT - 1) == "open_ramp"
               and c.name(x + 2, city.ROW_PAVEMENT - 1) == "open_ramp"]
    g0 = opening[0] if opening else None
    check("it opens on level 3's garage drawn OPEN, and she is out of it",
          g0 is not None and c.feet() == PAVEMENT and c.col() > g0 + 3
          and c.byte("WORLD_CR") == V_CR_MAX,
          f"the open door at {g0}, her feet {c.feet()} at column {c.col()}")

    # ---- the level as the engine reads it --------------------------
    B, bars, ups = c.buildings(), c.barricades(), c.ladders()
    ops = openings(c)
    gaps = [o for o in ops if o[1] < city.PLAZA_MIN]
    plazas = [o for o in ops if o[1] >= city.PLAZA_MIN]
    print(f"    roofs {B}")
    print(f"    gaps {gaps}, plazas {plazas}")
    print(f"    barricades {bars}, ladders {ups}")
    owns = lambda x: next((i for i, (a, b, _) in enumerate(B)
                           if a <= x <= b), None)
    check("three gaps, one of every shape level 2 measured, and a plaza",
          len(gaps) == 3 and len(plazas) == 1
          and sorted(f - n for _, _, n, f in gaps) == [-1, 0, 1]
          and all((w, f - n) in city.RUN_JUMPS for _, w, n, f in gaps),
          f"{[(w, f - n) for _, w, n, f in gaps]} - level, up and down")
    check("every gap's pit has one ladder out, onto the roof she jumped FROM",
          all(any(c.pit(u) == c.pit(g) and owns(u) == owns(g - 1) for u in ups)
              and not any(c.pit(u) == c.pit(g) and owns(u) > owns(g - 1)
                          for u in ups)
              for g, _, _, _ in gaps),
          "so a miss costs the fall and the climb, never the jump")
    p0, pw = plazas[0][:2]
    check("the plaza's ladder is on the building past it, behind a barricade",
          [owns(u) for u in ups if c.pit(u) == c.pit(p0)] == [owns(p0 + pw)]
          and any(owns(b) == owns(p0 + pw) and b > p0 + pw for b in bars),
          "level 3's rule: down off one roof, up the next")
    check("... and the key's roof has no ladder at all",
          not any(owns(u) == len(B) - 1 for u in ups),
          f"nothing on {B[-1][0]}..{B[-1][1]} - the last jump is the only "
          f"way on")

    # ---- the drive ---------------------------------------------------
    print("\n  across the roofs, down the ledge, up and across again:")
    ok, top = climb_at(c, ups[0])
    check("up the first ladder", ok and top == B[0][2] * 16,
          f"feet {top}, the roof line {B[0][2] * 16}")
    sync(c.m, sym, half=0)          # anchored: CLAUDE.md 10
    c.hw = c.game = 0
    tall = next(i for i, b in enumerate(B) if b[1] + 1 == p0)
    ev = run_east(c, B[tall][1] - 2)
    for e in ev:
        print(f"      {e[0]:4s} at {e[1]:3d}: pressed at byte {e[2]}, feet "
              f"{e[3]}" + (f" -> landed {e[4]} at byte {e[5]}"
                           if len(e) > 4 else ""))
    jumped = [e for e in ev if e[0] == "gap"]
    check("the level gap and the one UP onto the tallest roof, jumped",
          len(jumped) == 2 and c.feet() == B[tall][2] * 16
          and all(len(e) > 4 and e[4] < PAVEMENT for e in jumped),
          f"feet {c.feet()}, the tallest roof {B[tall][2] * 16}; "
          f"reserve {c.byte('AMMO_RESERVE')} - the clip is up there")
    to_lip(c, B[tall][1])
    hung, fell, hp0, hp1 = hang_and_drop(c)
    check("off the tallest roof by the ledge, free, into the plaza",
          hung[0] and fell is not None and fell <= city.FALL_FREE
          and hp0 == hp1 and c.feet() == PAVEMENT
          and p0 <= c.col() < p0 + pw,
          f"hanging at feet {hung[1]}, fell {fell}, HP {hp0} -> {hp1}, "
          f"column {c.col()}")
    up = next(u for u in ups if c.pit(u) == c.pit(p0))
    ok, top = climb_at(c, up)
    check("up the next building's ladder, past its barricade",
          ok and top == B[tall + 1][2] * 16,
          f"feet {top}; coins {c.byte('COINS_COUNT')} - the plaza's coin "
          f"is on the way")
    keyx = next((r[1] | r[2] << 8) // 8 for r in c.records(EK_PICKUP)
                if r[6] == city.PU_KEY)
    ev = run_east(c, keyx)
    last = [e for e in ev if e[0] == "gap"]
    check("the jump DOWN onto the key's roof, and the key",
          len(last) == 1 and len(last[0]) > 4
          and last[0][4] == B[-1][2] * 16 and c.byte("KEYS_COUNT") == 1,
          f"keys {c.byte('KEYS_COUNT')}, HP {c.hp()}")
    # NOT THE LOCK, AND SAID SO. A game frame that takes three hardware
    # frames is a frame with no heroine in it (9). This drive drops one
    # at a run's take-off, one on a run's first step and one in the fall
    # off the ledge - measured frame by frame, and written into CLAUDE.md
    # 8.16 - so what is asserted is that it does not get worse.
    check("... and the loop dropped no more than three frames on the way",
          c.hw - 2 * c.game <= 3,
          f"{c.game} game frames in {c.hw} hardware ones: "
          f"{c.hw - 2 * c.game} dropped")

    # ---- the way out, and where it goes -------------------------------
    print("\n  and the way out of the City:")
    fell, hp0 = walk_off_west(c)
    check("walking off the key's roof is free, into the pit the way out "
          "is in",
          c.feet() == PAVEMENT and fell is not None
          and fell <= city.FALL_FREE and c.hp() == hp0,
          f"{fell} lines, HP {hp0} -> {c.hp()}, column {c.col()}")
    door = next((r[1] | r[2] << 8) // 8 for r in c.records(6))
    walk_to(c, door + 2)
    c.m.joystick(JOY["up"])
    c.step()
    c.m.joystick(0)
    for _ in range(10):
        c.step()
        if c.byte("GAME_STATE"):
            break
    check("UP at the garage with the key opens it",
          c.byte("GAME_STATE") == GS_CLEAR, f"GAME_STATE {c.byte('GAME_STATE')}")
    hp, res, coins = c.hp(), c.byte("AMMO_RESERVE"), c.byte("COINS_COUNT")
    on = None
    for f in range(1500):
        c.m.run_frames(1)
        if c.byte("LEVEL_CUR") == 4 and c.byte("GAME_STATE") == 0:
            on = f
            break
    check("... and it leads OUT of the City: level 5, the forest",
          on is not None and c.byte("LEVEL_ENV") == FOREST
          and c.byte("LEVEL_OK") == 1,
          f"after {on} hardware frames - an environment, so the forest's art "
          f"came with it: LEVEL_ENV {c.byte('LEVEL_ENV')}")
    check("... with her health, her reserve and her coins, and not the key",
          c.hp() == hp and c.byte("AMMO_RESERVE") == res
          and c.byte("COINS_COUNT") == coins and c.byte("KEYS_COUNT") == 0,
          f"HP {c.hp()}, reserve {c.byte('AMMO_RESERVE')}, coins "
          f"{c.byte('COINS_COUNT')}, keys {c.byte('KEYS_COUNT')}")
    del c

    # ---- the windows, measured on the level itself -------------------
    print("\n  every gap's take-off window, at both stride phases:")
    wm = city4(sym, names)
    all_match, runoff_match = True, True
    for g, w, n, f in gaps:
        got, offs = [], 0
        for phase in (0, 1):
            good, ran_off = window(wm, g, w, n, f, g * 4 - 24 + phase)
            got.append(len(good))
            offs += ran_off
        # ... at both push beats too: a walk's window is a frame earlier
        # or later with the beat, and the same length (test_city.py)
        walks = [len(window(wm, g, w, n, f, g * 4 - 24 + phase,
                            run=False, beat=beat)[0])
                 for phase in (0, 1) for beat in (0, 1)]
        want = city.RUN_JUMPS[w, f - n]
        wwant = city.WALK_JUMPS[w, f - n]
        ok = tuple(got) == want and all(x == wwant for x in walks)
        all_match = all_match and ok
        runoff_match = runoff_match and offs == (
            1 if (w, f - n) in city.RUN_OFF else 0)
        print(f"      gap at {g:3d}, {w} wide, row {n} -> {f}: running "
              f"{got[0]}/{got[1]} frames, walking "
              + "/".join(map(str, walks))
              + f"{'' if ok else '  <- the tool says ' + str(want) + ', walking ' + str(wwant)}")
    check("they are level 2's windows, shape for shape",
          all_match, "a run's and a walk's exactly, at both stride phases "
          "and both push beats (8.14)")
    check("... and a run off the edge crosses the downhill one only",
          runoff_match)
    across = []
    for phase in (0, 1):
        good, ran_off = window(wm, p0, pw, plazas[0][2], plazas[0][3],
                               p0 * 4 - 24 + phase)
        across.append((len(good), ran_off))
    check("no take-off from the tallest roof lands across the plaza",
          across == [(0, False), (0, False)], f"{across}")
    del wm

    # ---- a miss at the hard one, and what pays for it ----------------
    print("\n  a miss at the jump UP, and the medkit under it:")
    mk = city4(sym, names)
    g2, w2, n2, f2 = next(o for o in gaps if o[3] < o[2])
    medx = next((r[1] | r[2] << 8) // 8 for r in mk.records(EK_PICKUP)
                if r[6] == city.PU_MEDKIT)
    check("the medkit is in the pit under the jump that goes UP",
          g2 <= medx < g2 + w2, f"column {medx}, the gap {g2}..{g2 + w2 - 1}")
    mk.put(g2 * 4 - 20, n2 * 16)
    mk.m.joystick(JOY["right"])
    for _ in range(200):
        if mk.wx() >= g2 * 4 - 5:
            break
        mk.step()
    fell, hp0, hp1 = fall(mk, "right", joy_extra=JOY["up"])
    taken = [r for r in mk.records(EK_PICKUP) if r[6] == city.PU_MEDKIT]
    # The miss is off a row-7 roof, so it costs 44 and the medkit is
    # worth 35 (8.6): it pays most of it back, not all.
    check("a walk pressed early misses, costs what the tool says, and the "
          "medkit is under it",
          mk.feet() == PAVEMENT and fell is not None
          and fell - city.FALL_FREE == city.miss_cost(n2)
          and hp1 == min(100, 100 - city.miss_cost(n2) + 35)
          and taken and taken[0][5] & EF_TAKEN,
          f"fell {fell}, {fell - city.FALL_FREE if fell else '-'} points, "
          f"and the medkit takes HP back to {hp1}")
    out = [u for u in mk.ladders() if mk.pit(u) == mk.pit(g2)]
    walk_to(mk, out[0])
    from test_city import climb_up
    top = climb_up(mk)
    check("... and the pit's ladder puts her back where she jumped from",
          top == n2 * 16 and mk.col() < g2, f"feet {top}, column {mk.col()}")
    del mk

    # ---- the other way down the plaza --------------------------------
    print("\n  walked off the tallest roof instead:")
    wo = city4(sym, names)
    wo.put(B[tall][0] * 4 + 8, B[tall][2] * 16)
    to_lip(wo, B[tall][1])
    fell, hp0, hp1 = walk_off(wo, B[tall][1])
    check("it costs the drop past FALL_FREE, where the ledge was free",
          fell == (city.ROW_PAVEMENT - B[tall][2]) * 16
          and hp0 - hp1 == city.walk_off_cost(B[tall][2]),
          f"fell {fell}, HP {hp0} -> {hp1}: walk_off_cost() says "
          f"{city.walk_off_cost(B[tall][2])}")
    del wo

    # ---- and the strip stays where it is -----------------------------
    # A PLAY-TEST ON CAPRICE32: "when I fall into a gap between buildings
    # I leave a copy of the hud behind". A fall outruns the camera, so
    # her last lines went down over the strip and her save-under held
    # its pixels; the vertical latch then moved the view a row, the
    # strip was repainted where it belongs, and her erase put the old
    # strip back on row 22 by its absolute addresses (CLAUDE.md 7.8).
    # HUD_CLIP stops her at the strip's top line, and the control
    # is that routine poked to RET: the copy comes back, in the same
    # cells, and scrolls up the picture with the wall it is painted on.
    print("\n  and a fall into the gap leaves nothing of the HUD behind:")
    # EVERY ROOF'S FALL, NOT THE FIRST ONE'S. Which falls put her save-
    # under over the strip on the frame the view steps is a matter of
    # phase: the first roof's did, until the incoming row's paint moved
    # (CLAUDE.md 8.22), and then it did not - the control found nothing
    # there and the rule was no less needed. So both halves walk off all
    # four roofs: with HUD_CLIP not one sample of any of them has a wrong
    # cell, and with it poked to RET the copy comes back in some.
    for control in (False, True):
        falls = []
        for k in range(len(B) - 1):
            hg = city4(sym, names)
            if control:
                hg.m.poke(sym["HUD_CLIP"], 0xC9)
            tiles = tileset(hg)
            hg.put(B[k][0] * 4 + 8, B[k][2] * 16)
            seen = fall_watch(hg, tiles, B[k][1])
            falls.append((k, hg.feet() == PAVEMENT, seen))
            del hg
        landed = all(f[1] for f in falls)
        if not control:
            check("walked off every roof into the gap after it, the "
                  "playfield is the map at every frame",
                  landed and not any(f[2] for f in falls),
                  ", ".join(f"roof {k}: {len(sn)}" for k, _, sn in falls)
                  + " samples with a wrong cell")
        else:
            hit = [(k, sn[0]) for k, _, sn in falls if sn]
            check("... and with HUD_CLIP = RET the strip is left on "
                  "the wall", landed and hit
                  and all(r in (21, 22) for _, (_, cells) in hit
                          for r, _ in cells[:1]),
                  f"{len(hit)} of {len(falls)} falls, the first at roof "
                  f"{hit[0][0]}, frame {hit[0][1][0]}: {hit[0][1][1]}"
                  if hit else "nothing on any roof")

    # AND THE STREET DRONE COMES DOWN WITH HER. It used to patrol a beat
    # in the plaza, two rows above the pavement, and the camera walked it
    # out of the picture and back - "they jump from one place to another,
    # disappear and come back", a play-test said, and asked for them to
    # stay on the screen until she kills them or they kill her. Drawn
    # once it is ENGAGED (src/enemy.asm): it keeps to her side, at her
    # chest, inside a window that ends above the strip's rows (EN_YB) -
    # which is why it no longer calls HUD_CLIP: its refresh runs before
    # the strip's vacate now, and a box on row 22 would save the old
    # strip as its background. So she hangs off the tallest roof with it
    # following her, drops into the plaza, and on every game frame of
    # that the drone is on the screen, its box ends above row 22, and
    # the playfield is the map everywhere but that box. The control is
    # the following itself: ENEMY_MOVE = RET, and the drop leaves it on
    # the roof and out of the picture.
    for control in (False, True):
        dg = city4(sym, names, drones=True)
        if control:
            dg.m.poke(sym["ENEMY_MOVE"], 0xC9)
        tiles = tileset(dg)
        dg.put(B[tall][1] * 4 - 8, B[tall][2] * 16)
        to_lip(dg, B[tall][1])
        for _ in range(300):                    # until one is following her
            dg.step()
            dg.m.poke(sym["PLAYER_HP"], 100)
            if dg.word("ENEMY_ENG"):
                break
        engaged = dg.word("ENEMY_ENG") != 0
        seen = dict(frames=0, off=0, low=0, wrong=[])

        def watched(c=dg, seen=seen):
            c.m.poke(sym["PLAYER_HP"], 100)
            tc.tick(c)
            seen["frames"] += 1
            if not c.byte("ENEMY_DREW"):
                seen["off"] += 1
            elif c.byte("ENEMY_LAST_BOT") >= sym["EN_YB"]:
                seen["low"] += 1
            seen["wrong"] += [(seen["frames"], x) for x in wrong_cells(c, tiles)
                              if x not in drone_cells(c)]
        dg.step = watched
        hang_and_drop(dg)
        for _ in range(30):
            dg.step()
        landed = dg.feet() == PAVEMENT
        del dg
        if not control:
            check("the street drone follows her off the tallest roof: on the "
                  "screen every frame, above the strip's rows",
                  engaged and landed and seen["off"] == 0 and seen["low"] == 0,
                  f"{seen['frames']} game frames, {seen['off']} without it, "
                  f"{seen['low']} with its box below line {sym['EN_YB'] - 1}")
            check("... and the playfield is the map everywhere but its box",
                  not seen["wrong"],
                  f"{len(seen['wrong'])} wrong cells"
                  + (f", the first {seen['wrong'][:4]}" if seen["wrong"] else ""))
        else:
            check("... and with ENEMY_MOVE = RET the drop leaves it behind",
                  engaged and landed and seen["off"] > 10,
                  f"{seen['off']} of {seen['frames']} frames without it")

    # ---- under fire --------------------------------------------------
    # AND SHE FIRES BACK, because a drone that has seen her does not let
    # go (CLAUDE.md 8.7): between the drive's legs, whatever is following
    # her is turned to and shot down. Without that the same drive is
    # shot down itself, which is the control - and the design: "until
    # you kill them or they kill you".
    print("\n  the same drive with the drones in it:")
    for back in (True, False):
        d = city4(sym, names, drones=True)
        kills = 0
        for leg in (lambda: climb_at(d, ups[0]),
                    lambda: run_east(d, B[tall][1] - 2),
                    lambda: to_lip(d, B[tall][1]),
                    lambda: hang_and_drop(d),
                    lambda: climb_at(d, up),
                    lambda: run_east(d, keyx)):
            if back and d.word("ENEMY_ENG"):
                kills += fight(d)
            leg()
        eng = d.word("ENEMY_ENG")
        on_her = eng and d.m.peek(eng + sym["ES_HP"]) > 0
        if back:
            check("she crosses the City's last level under fire, shooting "
                  "back", d.byte("KEYS_COUNT") == 1 and d.hp() > 0 and kills,
                  f"HP 100 -> {d.hp()}, keys {d.byte('KEYS_COUNT')}, "
                  f"{kills} drone(s) shot down on the way")
            hp_back = d.hp()
        else:
            # WHETHER SHE DIES OF IT IS THE BALANCE AND NOT THE PROPERTY:
            # 8 points a hit against a drive whose length moves with every
            # change to the frame. What does not move is that one of them
            # has to die - so either she is back at the start, or a live
            # drone is still following her at the key.
            check("... and NOT shooting back, one of them is not finished",
                  d.byte("KEYS_COUNT") == 0 or on_her,
                  f"keys {d.byte('KEYS_COUNT')}, HP {d.hp()} against "
                  f"{hp_back} shooting back, and "
                  + ("a live drone still on her" if on_her else
                     "nothing following her"))
        del d

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
