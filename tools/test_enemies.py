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
survive a skipped frame, and that the loop still locks 50 Hz.
"""
import os
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import boot, symbols, sync                        # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LEV = os.path.join(ROOT, "build", "levels")
EK_ENEMY, EF_ACTIVE, EF_TAKEN = 2, 1, 2
ES = dict(REC=0, X=2, Y=4, TYPE=5, FACE=6, CEL=7, TIMER=8, FIRE=9, HP=10,
          HOME=11, SPAN=13, DIR=14, DIE=15)
ES_STRIDE = 16
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
    m = boot(sym, scroll=True)

    # ---- the type table -------------------------------------------
    print("  ENEMY_TYPES, against the exporter's own constants:")
    agent = inc_values("level1_city/cityagent.inc")
    drone = inc_values("level1_city/citydrone.inc")
    T = sym["ENEMY_TYPES"]
    check("the whole table is inside one page - ADD A,low cannot carry",
          (T & 0xFF) + 2 * EN_T_STRIDE <= 256,
          f"&{T:04X} + {2 * EN_T_STRIDE} bytes")
    want = [("cityagent", 0, agent, "WALK", "FIRE"),
            ("citydrone", 1, drone, "FLY", "FIRE")]
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
                or slot(m, sym, i, "Y") != (y - h) & 0xFF
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
          f"sx={m.peek(sym['ENEMY_SX'])} sy={m.peek(sym['ENEMY_SY'])}")
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
    y0 = slot(m, sym, 0, "Y")
    seen, ys = set(), []
    for _ in range(sym["EN_DIE_FRAMES"] + 12):
        m.run_frames(1)
        seen.add(m.peek(sym["ENEMY_DREW"]) != 0)
        ys.append(slot(m, sym, 0, "Y"))
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
    print("\n  the loop, with a drone on screen:")
    for label, joy, floor, why, tap in (
            # A HIT COSTS A FRAME AND ONLY WHEN IT CROSSES A CELL.
            # The drone shoots her while she stands there - 100 down to
            # 76 over these 200 frames - and six cells over 100 points
            # is 16.67 apiece, so one of those hits takes the bar from
            # six lit to five and HUD_LEVEL lays the buffer out again:
            # 5,732 + 2,348 T, landing on a frame that is already
            # carrying ENEMY_REFRESH's 17,968. Measured against the same
            # run with PLAYER_HP frozen at 100: 201 with the bar and 201
            # without, against 199 and 201 when it is allowed to fall.
            ("standing still", 0, 198,
             "a hit that crosses a cell redraws the bar", False),
            ("walking right, scrolling", JOY_RIGHT, 198,
             "two frames an encounter pay for the enemy coming and going",
             False),
            ("walking left, into it", JOY_LEFT, 186,
             "... turning round pans the camera for 20 frames, and a pan "
             "is where the bar is dearest", False),
            # HELD IS AIM, NOT FIRE. The gun is draw-hold-RELEASE
            # (CLAUDE.md 8.4), so a trigger held down for 200 frames
            # never puts a round in the air and these two used to
            # measure a frame with an idle pool - which is how a pool
            # walk that cost 6,228 T a firing frame went unseen. `tap`
            # says fire the way a player does; what it costs her is
            # tools/test_module5.py's business.
            # AND THE ENERGY BAR IS THE THIRD NAMED COST. It is six
            # cells at the BOTTOM left and it has to be rewritten every
            # time the start address moves (CLAUDE.md 7.8). A step RIGHT
            # costs 1,188 T - two cells, and nothing at all to erase,
            # because the word the bar leaves behind is the last column
            # of row 22 and that is the incoming column H_TAIL has just
            # painted. A step LEFT is 2,688: its incoming column is 0,
            # so the leftover word is inside the bar's own row and has
            # to come back off the tilemap.
            #
            # Measured against the same run with HUD_SERVICE poked to
            # RET: 201/199/194/196/195 without the bar and
            # 199/199/190/195/193 with it. The whole of it is the pan -
            # walking right, where the camera steps every OTHER frame,
            # is 199 either way.
            # AND THE FOURTH NAMED COST IS THE ART ITSELF, which is the
            # one nothing in the engine can be tuned to give back. The
            # artist redrew the land sheet and her heaviest `kcore` cel
            # went from 284 span bytes to 323: 39 bytes at the
            # composite's 72 T floor is 2,808 T, and drawn plus erased
            # the cel went 54,820 -> 57,524. The frame did not have it.
            # Measured over the same five paths, same build, only the
            # sheet changed:
            #
            #   still 199 -> 198   right 199 -> 198   left 190 -> 186
            #   right+firing 195 -> 173   jumping+firing 193 -> 158
            #
            # The two firing paths are where it lands because a firing
            # frame carries the heaviest cel in the game AND a round in
            # the air AND the drone. What it looks like in play is
            # ground she does not cover, and tools/test_module5.py
            # measures it in bytes rather than in frames: 119 where the
            # aiming alone accounts for 131.
            #
            # These floors are the measurement, not a target. They were
            # accepted deliberately - the alternative was dropping the
            # mask on the 74% of her span bytes that are fully opaque,
            # which is 56 T a byte against 72 and ~3,950 T on this cel,
            # and that is a format, an exporter and a blitter (CLAUDE.md
            # 9, "what did not work").
            ("walking right + firing", JOY_RIGHT, 173,
             "... and the redrawn land sheet is 2,808 T of composite on "
             "her heaviest cel", True),
            ("jumping + firing, scrolling",
             JOY_RIGHT | JOY_UP, 158,
             "... and the redrawn land sheet is 2,808 T of composite on "
             "her heaviest cel", True)):
        mm = boot(sym, scroll=True)
        mm.joystick(JOY_RIGHT)
        for _ in range(90):
            mm.run_frames(1)
        mm.joystick(joy)
        mm.run_frames(5)
        f0 = mm.peek(sym["FRAME_COUNT"])
        for t in range(200):
            if tap:
                mm.joystick(joy | (JOY_FIRE if (t % 12) < 4 else 0))
            mm.run_frames(1)
        got = (mm.peek(sym["FRAME_COUNT"]) - f0) % 256
        mm.joystick(0)
        check(f"50 Hz: {label}", got >= floor,
              f"{got} loop iterations in 200 hardware frames"
              + (f" (floor {floor}: {why})" if why else ""))

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
