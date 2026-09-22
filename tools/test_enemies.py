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


# The cull window is 2 .. 80 - w - 2 byte columns (ENEMY_PICK), so these
# stop her with the drone a good margin inside it rather than balanced on
# its edge.
DRONE_IN_LO, DRONE_IN_HI = 12, 56


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
            ("forestsniper", 2, sniper, "WALK", "FIRE")]
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

    # ---- patrol, facing, sight -------------------------------------
    print("\n  one of them, driven in the running game:")
    m = to_drone(sym)
    check("the first drone came into view and is drawable",
          m.peek(sym["ENEMY_VIS"]) == 1 and word(m, sym["ENEMY_CUR"]) != 0,
          f"sx={m.peek(sym['ENEMY_SX'])} sy={word(m, sym['ENEMY_SY'])}")
    home = word(m, sym["ENEMIES"] + ES["HOME"])
    span = slot(m, sym, 0, "SPAN")
    xs, cels, faces, dirs = set(), set(), set(), set()
    for _ in range(200):
        m.run_frames(1)
        xs.add(word(m, sym["ENEMIES"] + ES["X"]))
        cels.add(slot(m, sym, 0, "CEL"))
        faces.add(slot(m, sym, 0, "FACE"))
        dirs.add(slot(m, sym, 0, "DIR"))
    lo, hi = min(xs), max(xs)
    check("it patrols, and stays inside its beat",
          home - span - 2 <= lo and hi <= home + span + 2,
          f"{lo}..{hi} around home {home} +/- {span}")
    check("it turns at both ends", dirs == {0, 1}, f"directions seen {sorted(dirs)}")
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
    for _ in range(260):                # its pixels held off the screen
        m.poke(sym["ENEMY_DREW"], 0)
        m.run_frames(1)
        m.poke(sym["PLAYER_HP"], 100)
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
          f"{fired} of its rounds in the air once ENEMY_DREW is left alone - "
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
    print("\n  it is a PERSISTENT sprite, not a per-frame one:")
    m = to_drone(sym)
    for _ in range(6):                  # settle, so it is definitely drawn
        m.run_frames(1)
    sync(m, sym)
    drew = m.peek(sym["ENEMY_DREW"])
    script = bytes(m.read_ram(sym["ENEMY_SCRIPT"], 8))
    before = bytes(m.read_ram(0xC000, 0x4000))
    # A frame the redraw cannot afford: hold VIEW_STEP up, which is what
    # a scrolling frame does.
    m.poke(sym["VIEW_STEP"], 8)
    m.run_frames(1)
    sync(m, sym)
    after = bytes(m.read_ram(0xC000, 0x4000))
    check("its pixels are still on the screen after a skipped frame",
          drew != 0 and m.peek(sym["ENEMY_DREW"]) == drew
          and bytes(m.read_ram(sym["ENEMY_SCRIPT"], 8)) == script,
          f"ENEMY_DREW {drew}, the script is untouched")
    check("... and the screen under it did not move either",
          sum(1 for a, b in zip(before, after) if a != b) < 400,
          "a skipped frame redraws nothing, so only Kara's own box changes")

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
