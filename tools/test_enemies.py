#!/usr/bin/env python3
"""The level's characters: src/enemy.asm.

Three different questions, and they need different kinds of evidence.

THE TABLE IS DATA. ENEMY_TYPES is read back out of the machine and
compared with the exporter's own .inc constants, because the bug that
cost the most here was not in any routine: `align 32` put a 64-byte
table across a page boundary and ENEMY_TYPE_AT's ADD A,low silently
wrapped, so a drone came out 135 lines tall with 23 hit points.

THE BEHAVIOUR IS A LOOP. Patrol, facing, sight, fire rate and damage
are all "over N frames", so they are driven in the running game and
watched, not poked and called.

THE DRAWING IS A BUDGET. One enemy on screen costs 17,968 T against a
scrolling frame's 420, so it is a PERSISTENT sprite: drawn once, left
on the screen between refreshes, and refreshed only on a frame that can
pay. The two things worth checking are that its pixels really do
survive a skipped frame, and that the loop still locks 25 Hz - 100 game
frames in 200 hardware ones.

AND A COUNT OF GAME FRAMES IS A SAMPLER BEFORE IT IS A MEASUREMENT.
The window has to start on a game frame, the tap has to be driven on
the game's clock rather than the hardware's, and what is left still
moves with where in the LEVEL the two hundred frames fall - so the loop
is asserted exactly with the drones off and as a floor with them on.
The three measurements are beside the checks.
"""
import os
import re
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import boot, symbols, sync                        # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LEV = os.path.join(ROOT, "build", "levels")
EK_ENEMY, EF_ACTIVE, EF_TAKEN = 2, 1, 2
# THE SLOT'S SHAPE COMES OFF THE BUILD, not out of this file. ES_Y went
# from a byte to a word and the stride from 16 to 17 when the map stopped
# being 16 rows tall (src/enemy.asm), and every offset after it moved;
# a copy written down here is a second statement of the layout that is
# right on the day it is typed and silently wrong afterwards - it would
# have read ES_TYPE out of the high byte of ES_Y and reported a drone
# with no type at all.
ES_FIELDS = ("REC", "X", "Y", "TYPE", "FACE", "CEL", "TIMER", "FIRE", "HP",
             "HOME", "SPAN", "DIR", "DIE")
ES, ES_STRIDE = {}, 0
EN_T = dict(BANK=0, RIGHT=1, BANK_L=3, LEFT=4, MOVE_F=6, MOVE_N=7,
            FIRE_F=8, FIRE_N=9, W=10, H=11, SPEED=12, PERIOD=13, HP=14,
            DUR=15, SPAWNS=17)
EN_T_STRIDE = 32
JOY_RIGHT, JOY_LEFT, JOY_FIRE, JOY_UP = 0x08, 0x04, 0x10, 0x01

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def inc_values(path):
    out = {}
    for line in open(os.path.join(LEV, path)):
        p = line.split()
        if len(p) >= 3 and p[1] == "equ":
            try:
                out[p[0]] = int(p[2])
            except ValueError:
                pass
    return out


def es_layout(sym):
    global ES, ES_STRIDE
    ES = {k: sym["ES_" + k] for k in ES_FIELDS}
    ES_STRIDE = sym["ES_STRIDE"]


def slot(m, sym, i, field):
    return m.peek(sym["ENEMIES"] + i * ES_STRIDE + ES[field])


def word(m, addr):
    return m.peek(addr) | (m.peek(addr + 1) << 8)


# The window is EN_XL .. 80 - w - EN_XL byte columns (ENEMY_PLACE), so
# these stop her with the drone a good margin inside it rather than
# balanced on its edge.
DRONE_IN_LO, DRONE_IN_HI = 12, 56


def game_frame(m, sym):
    """ONE game frame, top of the loop to top of the loop (CLAUDE.md 10:
    a count of game frames is phase-sensitive and has to be anchored)."""
    f0 = m.peek(sym["FRAME_COUNT"])
    while m.peek(sym["FRAME_COUNT"]) == f0:
        m.run_us(64)
    sync(m, sym, half=0)


def to_drone(sym, frames=400):
    """Walk her right until the first drone is drawable AND WELL INSIDE
    the window.

    Stopping the instant ENEMY_VIS goes up stops her with the drone one
    byte inside the right-hand edge of the cull window, and half of its
    patrol then takes it straight back out. Every check after this one
    would depend on which way it happened to be flying when she arrived,
    which is a phase accident of how many frames the level took to load.
    Walk until it is a margin in, and it stays in."""
    m = boot(sym, scroll=True)
    m.joystick(JOY_RIGHT)
    for _ in range(frames):
        m.run_frames(1)
        if m.peek(sym["ENEMY_VIS"]) and \
                DRONE_IN_LO <= m.peek(sym["ENEMY_SX"]) <= DRONE_IN_HI:
            break
    m.joystick(0)
    return m


def main():
    sym = symbols()
    es_layout(sym)
    m = boot(sym, scroll=True)

    # ---- the type table -------------------------------------------
    print("  ENEMY_TYPES, against the exporter's own constants:")
    agent = inc_values("level1_city/cityagent.inc")
    drone = inc_values("level1_city/citydrone.inc")
    sniper = inc_values("level2_forest/forestsniper.inc")
    seadrone = inc_values("level4_underwater/seadrone.inc")
    T = sym["ENEMY_TYPES"]
    # EN_KINDS OFF THE BUILD AND NOT OFF THIS LIST. Counting the rows
    # the suite happens to know about made the page check pass on a
    # table that had grown past it - a third character went in and this
    # said "&1C80 + 64 bytes" about 96 of them. A row nobody looks at
    # is the other half: `want` has to name every kind the engine has,
    # and the count below is what says so.
    kinds = sym["EN_KINDS"]
    check("the whole table is inside one page - ADD A,low cannot carry",
          (T & 0xFF) + kinds * EN_T_STRIDE <= 256,
          f"&{T:04X} + {kinds * EN_T_STRIDE} bytes, {kinds} kinds")
    want = [("cityagent", 0, agent, "WALK", "FIRE"),
            ("citydrone", 1, drone, "FLY", "FIRE"),
            # THE FOREST'S, AND THE FIRST ROW HERE THAT IS NOT THE
            # CITY'S - so it is also the check that a character's art
            # is named out of its OWN level's bank symbols.
            ("forestsniper", 2, sniper, "WALK", "FIRE"),
            # THE SEA'S, which SWIMS - the tag is the sheet's, so a row
            # that took the City's FLY would point at no cels at all.
            ("seadrone", 3, seadrone, "SWIM", "FIRE")]
    check("every kind the engine has is checked below", len(want) == kinds,
          f"{len(want)} rows against EN_KINDS {kinds}")

    # ... AND THE EDITOR'S COPY OF THE SAME TABLE. Its validator refuses
    # a p0 at or past the end, so an enum that has not caught up refuses
    # a level the engine plays - and nothing on the hardware says so.
    enum = editor_enum("EnemyKind")
    check("the editor's EnemyKind is the engine's table", 
          sorted(enum.values()) == list(range(kinds)),
          f"{', '.join(f'{k}={v}' for k, v in sorted(enum.items(), key=lambda kv: kv[1]))} "
          f"against EN_KINDS {kinds}")
    for name, t, v, move, fire in want:
        base = T + t * EN_T_STRIDE
        got = {k: m.peek(base + o) for k, o in EN_T.items()}
        key = name.upper()
        ok = (got["W"] == v[f"{key}_BOX_W"] and got["H"] == v[f"{key}_BOX_H"]
              and got["MOVE_F"] == v[f"{key}_{move}_FIRST"]
              and got["MOVE_N"] == v[f"{key}_{move}_COUNT"]
              and got["FIRE_F"] == v[f"{key}_{fire}_FIRST"]
              and got["FIRE_N"] == v[f"{key}_{fire}_COUNT"])
        check(f"{name}'s row is the sheet's own numbers", ok,
              f"{got['W']}x{got['H']} bytes, move {got['MOVE_F']}+"
              f"{got['MOVE_N']}, fire {got['FIRE_F']}+{got['FIRE_N']}")
        check(f"{name}'s two facings are in DIFFERENT banks",
              got["BANK"] != got["BANK_L"],
              f"&{got['BANK']:02X} right, &{got['BANK_L']:02X} left - "
              f"same address &{word(m, base + EN_T['RIGHT']):04X} in each")

    # ---- the spawn -------------------------------------------------
    print("\n  spawned from the level's own records:")
    m.run_frames(5)                     # ENEMY_SPAWN runs inside SCROLL_INIT
    blob = open(os.path.join(ROOT, "build", "city_entities.bin"), "rb").read()
    recs = [blob[i * 8:i * 8 + 8] for i in range(24)]
    live = [r for r in recs if r[0] == EK_ENEMY and r[5] & EF_ACTIVE]
    n = m.peek(sym["ENEMY_LIVE"])
    check("every enemy record became a live slot", n == len(live),
          f"{n} live, {len(live)} in the level")
    ok = True
    for i, r in enumerate(live):
        x, y = r[1] | r[2] << 8, r[3] | r[4] << 8
        h = m.peek(T + r[6] * EN_T_STRIDE + EN_T["H"])
        hp = m.peek(T + r[6] * EN_T_STRIDE + EN_T["HP"])
        # HOME, not X: it has been patrolling since the level installed.
        if (word(m, sym["ENEMIES"] + i * ES_STRIDE + ES["HOME"]) != x
                or word(m, sym["ENEMIES"] + i * ES_STRIDE
                        + ES["Y"]) != (y - h) & 0xFFFF
                or slot(m, sym, i, "HP") != hp
                or slot(m, sym, i, "SPAN") != r[7] * 8):
            ok = False
    check("each one is placed on its feet, with the type's hit points", ok,
          "y = base - height, span = p1 tiles in pixels")

    # THE LEVEL'S HALF OF "ONE ENEMY ON SCREEN". tools/make_city_map.py
    # asserts the spacing; this is the same fact from the engine's side.
    xs = sorted((r[1] | r[2] << 8) // 8 for r in live)
    gaps = [b - a for a, b in zip(xs, xs[1:])]
    check("no two of them can share a screen", all(g > 20 for g in gaps),
          f"tile gaps {gaps}, the screen is 20 tiles")

    # ---- before anybody has seen it: a beat ---------------------------
    # She stands at the start of level 1; the first drone is inside
    # EN_NEAR of the view and well outside the window, so it is the one
    # awake and nobody can see it. That is the only time a beat means
    # anything now (ENEMY_PICK).
    print("\n  before it has been seen, it patrols a beat:")
    m = boot(sym, scroll=True)
    sync(m, sym, half=0)
    home = word(m, sym["ENEMIES"] + ES["HOME"])
    span = slot(m, sym, 0, "SPAN")
    xs, dirs, drew, curs = set(), set(), set(), set()
    for _ in range(100):
        game_frame(m, sym)
        xs.add(word(m, sym["ENEMIES"] + ES["X"]))
        dirs.add(slot(m, sym, 0, "DIR"))
        drew.add(m.peek(sym["ENEMY_DREW"]) != 0)
        curs.add(word(m, sym["ENEMY_CUR"]))
    lo, hi = min(xs), max(xs)
    check("standing at the start, the first drone is the one awake - and "
          "off the screen", curs == {sym["ENEMIES"]} and drew == {False},
          f"ENEMY_CUR {sorted(hex(c) for c in curs)}, drawn {sorted(drew)}")
    check("it patrols, and stays inside its beat",
          home - span - 2 <= lo and hi <= home + span + 2,
          f"{lo}..{hi} around home {home} +/- {span}")
    check("it turns at both ends", dirs == {0, 1},
          f"directions seen {sorted(dirs)}")

    # ---- AND FROM THE MOMENT IT IS ON THE SCREEN, IT FOLLOWS HER --------
    # A play-test: "the drones jump from one place to another, disappear
    # and come back. From the moment they appear they should move fast but
    # not abruptly, and not leave the screen until you kill them or they
    # kill you." What it was is in CLAUDE.md 8.7: drawn on one game frame
    # in two and not at all while the picture moved, so a walk froze it
    # for up to 34 bytes of its patrol and then showed all of them at
    # once; and culled at a hard edge the camera walked it across. So:
    # drawn once, it is ENGAGED - it keeps to her, on its side, at her
    # chest, inside the window - and it is redrawn on every game frame.
    print("\n  and from the moment it is on the screen, it follows her:")

    def follow(quiet=None):
        mm = to_drone(sym)
        if quiet:
            mm.poke(sym[quiet], 0xC9)        # RET
        w = mm.peek(sym["ENEMY_W"])
        h = mm.peek(sym["ENEMY_H"])
        out = []
        for joy, n in ((JOY_RIGHT, 150), (JOY_LEFT, 150), (0, 60)):
            mm.joystick(joy)
            for _ in range(n):
                mm.poke(sym["PLAYER_HP"], 100)
                game_frame(mm, sym)
                out.append(dict(
                    joy=joy, drew=mm.peek(sym["ENEMY_DREW"]) != 0,
                    sx=mm.peek(sym["ENEMY_SX"]), sy=word(mm, sym["ENEMY_SY"]),
                    dwx=word(mm, sym["ENEMY_DREW_WX"]),
                    kmid=word(mm, sym["KARA_WX"]) + sym["KARA_BOX_W"] // 2,
                    ey=word(mm, sym["ENEMIES"] + ES["Y"]),
                    ky=word(mm, sym["KARA_WY"])))
        mm.joystick(0)
        return mm, out, w, h

    m, run, w, h = follow()
    eng = word(m, sym["ENEMY_ENG"])
    check("drawn once, it is the one following her",
          eng == sym["ENEMIES"] and word(m, sym["ENEMY_CUR"]) == eng,
          f"ENEMY_ENG &{eng:04X}, the first slot &{sym['ENEMIES']:04X}")
    xl, yb = sym["EN_XL"], sym["EN_YB"]
    off = [i for i, r in enumerate(run) if not r["drew"]]
    check("it is on the screen on every game frame of a walk away from it, "
          "back past it and standing", not off,
          f"{len(run)} frames, {len(off)} without it"
          + (f", the first {off[:6]}" if off else ""))
    out_w = [i for i, r in enumerate(run)
             if r["drew"] and not (xl <= r["sx"] <= 80 - xl - w
                                   and r["sy"] + h <= yb)]
    check("... always inside its window: two characters clear of both "
          "edges and above the strip's rows", not out_w,
          f"columns {xl}..{80 - xl - w}, its box ending by line {yb}"
          + (f"; outside at {out_w[:6]}" if out_w else ""))
    steps = [r2["dwx"] - r1["dwx"] for r1, r2 in zip(run, run[1:])]
    check("... moving a byte or two a game frame and never more",
          max(abs(d) for d in steps) <= 2,
          f"steps seen {sorted(set(steps))} - EN_CHASE is two bytes, her run")
    # A HOLD IS A TURN OR IT IS A FRAME IT WAS NOT REDRAWN ON. Standing,
    # it sways, and it holds one frame at each end - which end is where
    # its sway runs out or where the window's clamp turns it round, so the
    # NUMBER of holds is the sway's width and not a property: measured,
    # with her at CAM_LEAD it sways four bytes against the right-hand
    # clamp and holds one frame in five. What a drawing that skipped
    # frames leaves is a hold BETWEEN two steps the same way.
    still = [r["dwx"] for r in run if r["joy"] == 0][10:]
    def sign(v): return (v > 0) - (v < 0)
    holds = [i for i in range(1, len(still) - 2) if still[i] == still[i + 1]]
    mid_run = [i for i in holds
               if not (sign(still[i] - still[i - 1]) and
                       sign(still[i] - still[i - 1]) == -sign(still[i + 2] - still[i + 1]))]
    check("... and redrawn on every one: standing, it holds only where it "
          "turns round", holds and not mid_run,
          f"{len(holds)} holds in {len(still) - 1} frames, {len(mid_run)} of "
          f"them between two steps the same way"
          + (f" at {mid_run[:6]}" if mid_run else "")
          + " - redrawn on one frame in two, as it was, is every other frame")
    gaps = sorted(abs(r["dwx"] + w // 2 - r["kmid"]) for r in run[10:])
    med = gaps[len(gaps) // 2]
    check("it keeps to her, EN_DIST off, give or take its sway",
          gaps[0] >= sym["EN_MIN"] and abs(med - sym["EN_DIST"]) <= 6,
          f"middle to middle {gaps[0]}..{gaps[-1]} bytes, {med} typically; "
          f"EN_DIST {sym['EN_DIST']}, never under EN_MIN {sym['EN_MIN']}")
    chest = [r["ey"] - r["ky"] for r in run[10:]]
    check("... at her chest", all(abs(d - sym["EN_DY"]) <= sym["EN_VY"]
                                  for d in chest),
          f"its top {min(chest)}..{max(chest)} lines below hers, "
          f"EN_DY {sym['EN_DY']}")
    _, run_q, w, _ = follow("ENEMY_MOVE")
    off_q = sum(1 for r in run_q if not r["drew"])
    check("CONTROL: ENEMY_MOVE = RET, and the walk away leaves it behind",
          off_q > 50,
          f"{off_q} of {len(run_q)} frames without it - the following is "
          f"what keeps it on the screen, not the window")

    # ---- its cels, and its fire ---------------------------------------
    m = to_drone(sym)
    cels, faces = set(), set()
    for _ in range(200):
        m.run_frames(1)
        m.poke(sym["PLAYER_HP"], 100)
        cels.add(slot(m, sym, 0, "CEL"))
        faces.add(slot(m, sym, 0, "FACE"))
    mv_f = m.peek(T + EN_T_STRIDE + EN_T["MOVE_F"])
    mv_n = m.peek(T + EN_T_STRIDE + EN_T["MOVE_N"])
    fr_f = m.peek(T + EN_T_STRIDE + EN_T["FIRE_F"])
    check("it animates through the whole move loop at the art's own rate",
          set(range(mv_f, mv_f + mv_n)) <= cels,
          f"cels seen {sorted(cels)}, move loop {mv_f}..{mv_f + mv_n - 1}")
    check("it plays its recoil when it fires", fr_f in cels,
          f"fire cel {fr_f} {'seen' if fr_f in cels else 'never seen'}")

    # ---- its fire, and hers ----------------------------------------
    print("\n  the exchange:")
    m = to_drone(sym)
    hp0 = m.peek(sym["PLAYER_HP"])
    for _ in range(250):
        m.run_frames(1)
        if m.peek(sym["PLAYER_HP"]) != hp0:
            break
    hurt = hp0 - m.peek(sym["PLAYER_HP"])
    check("its shots take health off her", hurt > 0, f"{hp0} -> "
          f"{m.peek(sym['PLAYER_HP'])}, {hurt} a hit")
    # THE BORDER IS THE HUD FOR NOW (CLAUDE.md 9). A static one over a
    # scrolling screen needs a raster split the frame cannot pay for, so
    # until module 6 the player is told by four frames of red.
    check("... and the border says so", m.peek(sym["HURT_FLASH"]) > 0,
          f"HURT_FLASH {m.peek(sym['HURT_FLASH'])} of "
          f"{sym['HURT_FRAMES']} frames")
    for _ in range(sym["HURT_FRAMES"] + 2):
        m.run_frames(1)
        m.poke(sym["PLAYER_HP"], 100)       # not hit again
    check("... and it goes out again", m.peek(sym["HURT_FLASH"]) == 0,
          "black once the frames are up, so it is the hit and not a "
          "border that is red from now on")

    # ---- IT HAS TO BE ON THE SCREEN BEFORE IT CAN SHOOT ------------
    # Live and drawn are a few frames apart: it has to clear the
    # drawable edge by EN_HYST and then wait for a frame with room for
    # its draw (CLAUDE.md 8.7). Rounds out of an empty screen are not a
    # difficulty setting.
    print("\n  and it shoots only once the player can see it:")
    m = to_drone(sym)
    m.poke(sym["PLAYER_HP"], 100)
    # ITS PIXELS ARE HELD OFF BY HOLDING THE REFRESH OFF, not by poking
    # ENEMY_DREW alone: its sight and its gun run in the second sweep now,
    # AFTER the refresh (ENEMY_THINK, CLAUDE.md 8.7), so a poke between
    # frames is written over by the refresh before the gun ever reads it.
    held = {n: m.peek(sym[n]) for n in ("ENEMY_REFRESH_EARLY",
                                        "ENEMY_REFRESH_LATE")}
    for n in held:
        m.poke(sym[n], 0xC9)            # RET
    for _ in range(260):                # its pixels held off the screen
        m.poke(sym["ENEMY_DREW"], 0)
        m.run_frames(1)
        m.poke(sym["PLAYER_HP"], 100)
    for n, v in held.items():
        m.poke(sym[n], v)
    check("nothing leaves its gun while its pixels are not up",
          m.peek(sym["EBUL_LIVE"]) == 0 and m.peek(sym["PLAYER_HP"]) == 100,
          f"EBUL_LIVE {m.peek(sym['EBUL_LIVE'])}, her HP "
          f"{m.peek(sym['PLAYER_HP'])} over 260 frames in its sights")
    fired = 0
    for _ in range(260):                # ... and now let it be drawn
        m.run_frames(1)
        m.poke(sym["PLAYER_HP"], 100)
        fired = max(fired, m.peek(sym["EBUL_LIVE"]))
    check("... and it does the moment they are", fired > 0,
          f"{fired} of its rounds in the air once the refresh is let go - "
          f"so the check above is the gate and not a dead gun")

    m = to_drone(sym)
    hp_want = m.peek(T + EN_T_STRIDE + EN_T["HP"])
    hits, t = [], 0
    last = slot(m, sym, 0, "HP")
    for t in range(300):
        # THE GUN IS DRAW-HOLD-RELEASE (CLAUDE.md 8.4): a held trigger
        # aims and never fires, which is how the first version of this
        # test managed 300 frames without a single round leaving.
        m.joystick(JOY_FIRE if (t % 12) < 4 else 0)
        m.run_frames(1)
        hp = slot(m, sym, 0, "HP")
        if hp != last:
            hits.append(t)
            last = hp
        if hp == 0:
            break
    m.joystick(0)
    check(f"her rounds kill it in {hp_want} hits", len(hits) == hp_want
          and last == 0, f"hits at frames {hits}")
    m.run_frames(4)
    rec = word(m, sym["ENEMIES"] + ES["REC"])
    check("the RECORD is marked killed, not just the slot",
          m.peek(rec + 5) & EF_TAKEN != 0, f"flags &{m.peek(rec + 5):02X}")

    # ---- and it falls out of the sky before it goes ----------------
    # A drone that vanished on the frame the last round landed read as
    # a bug: the shot and the disappearance are the same frame, so
    # nothing on screen says one caused the other. It keeps its slot
    # for ES_DIE more frames, falling and flashing (CLAUDE.md 8.7).
    # ES_Y IS A WORD (CLAUDE.md 8.7), so the fall is read as one: on the
    # City every value of it fits in a byte and the two readings agree,
    # which is exactly why a byte read here would never say so.
    def slot_y(mm):
        return word(mm, sym["ENEMIES"] + ES["Y"])

    y0 = slot_y(m)
    seen, ys = set(), []
    # EN_DIE_FRAMES COUNTS GAME FRAMES AND THIS LOOP COUNTS HARDWARE
    # ONES, and a game frame is two of them (CLAUDE.md 9).
    for _ in range(2 * sym["EN_DIE_FRAMES"] + 24):
        m.run_frames(1)
        seen.add(m.peek(sym["ENEMY_DREW"]) != 0)
        ys.append(slot_y(m))
    check("it falls", ys[-1] > y0 + 40, f"world y {y0} -> {ys[-1]}")
    check("... and flashes on the way down", seen == {True, False},
          "drawn on some of those frames and not on others, which is what "
          "the refresh's erase already costs it")
    check("... and then it is gone for good",
          slot(m, sym, 0, "DIE") == 0 and word(m, sym["ENEMY_CUR"]) == 0
          and m.peek(sym["ENEMY_DREW"]) == 0,
          f"ES_DIE {slot(m, sym, 0, 'DIE')}, ENEMY_CUR "
          f"&{word(m, sym['ENEMY_CUR']):04X}, its pixels lifted off")

    # ---- the persistent sprite -------------------------------------
    # Its pixels stay on the screen from one refresh to the next and the
    # refresh is the only thing that lifts them off (ENEMY_REFRESH). What
    # used to be checked here was that they SURVIVED a frame the refresh
    # was put off on - and putting it off was the bug. What is left to
    # check is the other half: one refresh, one image, nothing left of
    # the last one. The picture outside its box is checked against the
    # map in tools/test_city4.py, on the street drone, all the way along.
    print("\n  it is a PERSISTENT sprite, lifted off by its own refresh:")
    m = to_drone(sym)
    for _ in range(6):
        game_frame(m, sym)
    script = bytes(m.read_ram(sym["ENEMY_SCRIPT"], 3))
    game_frame(m, sym)
    check("it was drawn, and its erase script is a real one",
          m.peek(sym["ENEMY_DREW"]) != 0 and script[0] != 0xFF,
          f"ENEMY_DREW {m.peek(sym['ENEMY_DREW'])}, script starts "
          f"{script.hex()}")
    check("... and it is the top of the second sweep that redraws it, "
          "in the border", m.peek(sym["ENEMY_EARLY"]) == 1,
          "ENEMY_SLOT found nothing it could meet")

    # ---- and the frame still closes --------------------------------
    # WHAT THE FRAMES THAT ARE ALLOWED TO OVERRUN ARE, AND WHY. Two per
    # encounter pay whatever the enemy costs: the one it comes into view
    # on and the one it leaves on (ENEMY_REFRESH). And turning round
    # makes the camera pan (CAM_TRAIL/CAM_LEAD in player.asm), which is a
    # whole column every frame for about 26 frames instead of every
    # other one. Both are transients and both are named here rather than
    # hidden behind a loose threshold.
    print("\n  the loop, and it is 25 Hz now:")
    # THE GAME RUNS AT 25 Hz AND THE LOCK IS 100 OF 200 (CLAUDE.md 9).
    # A frame this loop drops is not a stutter, it is a frame with no
    # heroine in it - she is drawn in the top border and erased at her
    # raster gate - and at 50 Hz the heavy paths could not make the
    # budget. A play-test reported the last of it as flicker while she
    # RAN. The loop waits for two VSYNCs, her erase moved to the second
    # hardware frame so she is on the screen for both sweeps, and every
    # path below reaches the lock exactly.
    #
    # WHAT THESE PATHS USED TO MEASURE IS KEPT HERE, because it is the
    # record of what each thing cost while the frame was the budget and
    # it is the first place to look when something has to come back out.
    # The columns are the same build with one thing changed: the energy
    # bar, the artist's redrawn land sheet, the half-speed walk, the
    # fourteen ammo pips, the magazine digit, and the touch sweep moved
    # to one frame in four.
    #
    #   standing         201 199 198 201 201 201 201
    #   walking right    199 199 198 199 198 198 198
    #   walking left     194 190 186 193 192 191 191
    #   + firing         196 195 173 194 184 183 191
    #   jumping + firing 195 193 158 191  -  174 189
    #   running           -   -   -  172 161 151 160
    #   running + firing  -   -   -  185  -  151 164
    #
    # and of those, the two run rows are what 25 Hz was for.
    def loop_count(joy, tap, shift, quiet=None, drones=True, pre=90):
        mm = boot(sym, scroll=True)
        if quiet:
            mm.poke(sym[quiet], 0xC9)       # RET
        mm.joystick(JOY_RIGHT)
        for _ in range(pre):
            mm.run_frames(1)
        if shift:
            # THERE IS NO KEYCODE FOR SHIFT ON ITS OWN HERE, so what is
            # pressed is an UPPERCASE letter: the emulator puts row 2
            # bit 5 down for the shift and row 8 bit 2 for the A, and
            # the engine binds the first and nothing at all to the
            # second (src/input.asm).
            mm.key_down('A')
        mm.joystick(joy)
        mm.run_frames(5)
        # ANCHOR THE WINDOW TO THE TOP OF A GAME FRAME, or the count
        # below is the sampler's phase as much as the loop's. A game
        # frame is two hardware ones, so 200 of them hold exactly 100
        # boundaries - but only if the window STARTS on one. Measured on
        # an unchanged build, the same path over ten unanchored windows
        # reads 99, 100 and 101 by turns; anchored it reads 100 forty
        # times out of forty.
        sync(mm, sym, half=0)
        f0 = mm.peek(sym["FRAME_COUNT"])
        for t in range(200):
            if not drones:
                mm.poke(sym["ENEMY_LIVE"], 0)   # ENEMY_PICK finds nobody
            if tap:
                # AND THE TAP IS COUNTED IN GAME FRAMES, NOT HARDWARE
                # ONES. It was "four hardware frames down in every
                # twelve", which at 25 Hz is two game frames down in six
                # - but only when the twelve happen to start on a game
                # frame. Straddling one, the same pattern holds the
                # trigger down for THREE game frames in some of its
                # windows and two in the rest, so how hard it drives the
                # loop is a property of where the sampler started.
                # Measured over the twelve hardware alignments of the
                # old pattern, anchored, game frames per 200: walking
                # right + firing 99 ten times and 100 twice, jumping +
                # firing 99 eight and 100 four, running + firing 97
                # three times, 98 eight and 99 once.
                g = (mm.peek(sym["FRAME_COUNT"]) - f0) % 256
                mm.joystick(joy | (JOY_FIRE if (g % 6) < 2 else 0))
            mm.run_frames(1)
        got = (mm.peek(sym["FRAME_COUNT"]) - f0) % 256
        mm.joystick(0)
        if shift:
            mm.key_up('A')
        return got

    # AND EVERY PATH REACHES THE LOCK WITH THE LEVEL'S DRONES OFF -
    # EVERY ONE, INCLUDING THE RUN WITH THE GUN. That is not what this
    # suite used to say: it carried 98 for the run-and-fire path and
    # named the run's own cels as the reason, "351 span bytes against
    # the 324 of her heaviest kcore one". The cels are not the reason
    # and CLAUDE.md 7.8 and 9 are corrected with it.
    #
    # What found it was making the sampler honest. Two things in it were
    # deciding the number: the window was not anchored to a game frame,
    # and the tap was written in hardware frames (both above). With both
    # fixed the count still moved when nothing but the PRE-ROLL did -
    # the same build, the same window, started one frame further along
    # the roof - which is a count that is about WHERE IN THE LEVEL the
    # two hundred frames fall. Measured over ten starting points, 86 to
    # 95 frames of walking in:
    #
    #                            with the drones      with them off
    #   standing / walking /     100 x 10             100 x 10
    #     walking left / running
    #   walking right + firing   99, 100              100 x 10
    #   jumping + firing         99, 100              100 x 10
    #   running right + firing   96 .. 99             100 x 10
    #
    #   running right + firing   95 .. 99  <- 16-bit world Y
    #   running right + firing   95 .. 98  <- ... and 16-bit ES_Y
    #
    # AND THE LAST ROW MOVED BY ONE WHEN WORLD Y BECAME SIXTEEN BITS
    # (CLAUDE.md 8.1), WHICH IS THE COST OF IT AND THE WHOLE OF THE
    # COST. Re-measured over the same ten starting points on the
    # widened build, the drone-free count is still exactly 100 on all
    # seven paths - so the LOOP did not lose a frame anywhere - and
    # every band above is the one it was except the run with the gun,
    # which went from 96..99 to 95..99.
    #
    # What says where the frame went is the strip's own column below:
    # with HUD_SERVICE returning at once the widened build measures
    # 99 99 99 98 98 99 99 99 99 97, which is the 8-bit build's ten
    # numbers EXACTLY. So the ~380 T of 16-bit Y costs nothing on a
    # frame that is not also paying for the bottom row, and on the one
    # path that steps the camera every game frame - a run's step IS one
    # CRTC character (CLAUDE.md 8.2) - it pushes one or two more of
    # those 3,568 T frames over the edge.
    #
    # So the drone-free count is the LOOP and it is exact; the in-game
    # one is the loop plus an ENCOUNTER whose phase the pre-roll moves,
    # and what can honestly be asserted about it is a floor with the
    # sweep above beside it. Both are checked, because either alone
    # would hide something: the exact one cannot see a frame the
    # encounter costs, and the floor cannot see a frame the loop lost.
    #
    # WHAT THESE PATHS USED TO MEASURE IS KEPT, because it is the record
    # of what each thing cost while the frame was the budget and it is
    # the first place to look when something has to come back out. The
    # columns are the same build with one thing changed: the energy bar,
    # the artist's redrawn land sheet, the half-speed walk, the fourteen
    # ammo pips, the magazine digit, and the touch sweep moved to one
    # frame in four - all of them 50 Hz numbers, 200 of 200 being the
    # lock.
    #
    #   standing         201 199 198 201 201 201 201
    #   walking right    199 199 198 199 198 198 198
    #   walking left     194 190 186 193 192 191 191
    #   + firing         196 195 173 194 184 183 191
    #   jumping + firing 195 193 158 191  -  174 189
    #   running           -   -   -  172 161 151 160
    #   running + firing  -   -   -  185  -  151 164
    #
    # and of those, the two run rows are what 25 Hz was for.
    seen = {}
    for label, joy, tap, shift, floor in (
            ("standing still", 0, False, False, 100),
            ("walking right, scrolling", JOY_RIGHT, False, False, 100),
            ("walking left, into it", JOY_LEFT, False, False, 100),
            ("walking right + firing", JOY_RIGHT, True, False, 99),
            ("jumping + firing, scrolling",
             JOY_RIGHT | JOY_UP, True, False, 99),
            ("running right, scrolling", JOY_RIGHT, False, True, 100),
            ("running right + firing", JOY_RIGHT, True, True, 95)):
        # EXACTLY THE LOCK, NOT "AT LEAST" AND NOT "AT MOST". A game
        # frame that took three hardware frames reads one under and one
        # that took a single frame reads one over, and both are faults:
        # the first is a dropped game frame - a sweep with no heroine in
        # it - and the second is the erase landing on the frame of the
        # draw, which is a blank sweep.
        bare = loop_count(joy, tap, shift, drones=False)
        check(f"25 Hz: {label}, the level's drones off", bare == 100,
              f"{bare} game frames in 200 hardware frames, want 100")
        got = seen[label] = loop_count(joy, tap, shift)
        check(f"... and the encounter costs {label} no more than "
              f"{100 - floor}", floor <= got <= 100,
              f"{got} in the game against {bare} with nothing to shoot at, "
              f"and {floor} is the worst of ten starting points")

    # AND MOST OF WHAT THE RUN'S ENCOUNTER COSTS IS THE BOTTOM ROW.
    # This check used to claim the opposite - "what it drops is not the
    # strip" - on the strength of the two counts being equal at one
    # starting point. Over the ten it is worth one game frame at eight
    # of them and nothing at the other two, so it was a part of the
    # encounter's cost and not the whole of it; sixteen-bit world Y then
    # took it to two and three:
    #
    #                      8-bit world Y                   16-bit world Y
    #   with the strip     98 99 99 97 97 98 98 98 98 96   97 99 99 95 95 96 97 97 97 95
    #   HUD_SERVICE = RET  99 99 99 98 98 99 99 99 99 97   99 99 99 98 98 99 99 99 99 97
    #   the strip's share   1  0  0  1  1  1  1  1  1  1    2  0  0  3  3  3  2  2  2  2
    #
    #                                                      ... and 16-bit ES_Y
    #   with the strip                                     98 98 98 95 95 96 97 97 97 95
    #   HUD_SERVICE = RET                                  99 99 99 97 97 99 99 99 99 97
    #   the strip's share                                   1  1  1  2  2  3  2  2  2  2
    #
    # THE MIDDLE ROW WAS THE SAME TEN NUMBERS ON THE FIRST TWO BUILDS,
    # and that is the measurement rather than a coincidence: what the
    # WORLD Y widening cost is only frames that were already paying
    # 3,568 T for a step right, which on a run is every game frame.
    # THE ENEMY SLOT'S OWN Y IS DIFFERENT AND SMALLER: two of the ten
    # lose a frame with the strip silent as well - ENEMY_PICK is
    # 924 T -> 1,024 and ENEMY_SHOT_CHECK 224 -> 252, benched from a DI
    # stub with a drone in view - and the worst of the ten, which is
    # what the floor below asserts, does not move at all. With the
    # drones off all three columns are 100.
    # AND THE BOUND HERE IS FOUR AND WAS THREE, on a build whose floor
    # did not move at all. The number this subtracts is sensitive to
    # the encounter's PHASE - which the paragraph above says is not the
    # loop - and something moved the phase.
    #
    # (Both arms are single points at the same pre-roll of 90 - the
    # 95 asserted as the floor above is a number written down from a
    # past sweep, not a worst-of-ten measured in this run.)
    #
    # WHAT MOVED IT WAS 10,292 T INSIDE MAP_INSTALL. HAZARD_SCAN ORs
    # the whole of TILE_ATTR once a level (collide.asm); boot() polls
    # LEVEL_OK every two frames, so a level that installs an eighth of
    # a frame later can be found a frame later, and the whole sweep
    # starts one frame further along the roof. Measured, the same ten
    # pre-rolls, HUD_SERVICE silent:
    #
    #   before HAZARD_SCAN existed   99 99 99 97 97 99 99 99 99 97
    #   after it                     99 99 97 97 99 99 99 99 97 97
    #   ... with HAZARD_HURT = RET   99 99 97 97 99 99 99 99 97 97
    #
    # The last two rows are the SAME TEN NUMBERS, so the shift is the
    # build's phase and not the routine's 24 T a frame - and the floor
    # asserted above is 95 on all three.
    #
    # The two arms are at the SAME pre-roll and always were, so this is
    # the strip's share and not a spread; what the phase moved is the
    # share itself, and over the ten it now reads 1 1 2 2 4 4 2 2 2 2.
    label = "running right + firing"
    quiet = loop_count(JOY_RIGHT, True, True, quiet="HUD_SERVICE")
    check("... and the strip is at most four frames of what it costs",
          0 <= quiet - seen[label] <= 4,
          f"{quiet} of 200 with the WHOLE of HUD_SERVICE returning at once, "
          f"against {seen[label]} with it")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


def editor_enum(name):
    """The editor's copy of an engine table, read out of its source.

    A COPY OF A TABLE IS RIGHT ON THE DAY IT IS TYPED. The editor holds
    EnemyKind and PickupKind because `p0` is always "which thing this
    is" (CLAUDE.md 8.6) and the inspector needs a list behind the
    number - and its validator refuses a `p0` at or past the end,
    which is the engine's own rule. The moment the engine grows a row
    and the enum does not, the editor refuses a level the engine
    plays; the moment it shrinks, the editor offers one the engine
    skips. Neither says anything on the hardware.
    """
    path = os.path.join(ROOT, "editor", "src", "CpcLevelEditor.Domain",
                        f"{name}.cs")
    out = {}
    for line in open(path, encoding="utf-8"):
        mm = re.match(r"^\s{4}(\w+)\s*=\s*(\d+),", line)
        if mm:
            out[mm.group(1)] = int(mm.group(2))
    return out

if __name__ == "__main__":
    sys.exit(main())
