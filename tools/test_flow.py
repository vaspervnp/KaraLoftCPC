#!/usr/bin/env python3
"""The level FSM: where she starts, the fade, and what a restart means.

CLAUDE.md 11 step 8. Four things that did not exist:

  1. PLAYER_SPAWN. KARA_WX and KARA_WY were assembler initialisers,
     applied once when the bootstrap relocates the core image and never
     again - so a second level would start her on the first one's roof
     and a death had nowhere to put her back to. The City carries an
     EK_PLAYER_START record now and she is read out of it.
  2. The fade. The palette is a 3x3x3 cube (6.6), so one step darker is
     each non-zero channel down one level and a fade to black is
     exactly two steps. It is measured WHERE IT SHOWS, because the gate
     array cannot be read back - here or on the machine (7.7).
  3. GAME_STATE, FLOW_CHECK and FLOW_STEP. She dies, the screen fades,
     and the level comes back; the garage opens, the title comes up,
     and it starts again.
  4. LEVEL_RESET, and it is the dangerous one. A restart is SCROLL_INIT
     - the map, the entity table, the tile flags, the bake and the
     enemies all come back out of the pristine LEVEL_IMAGE at &B000 -
     plus the state that belongs to HER and to the FRAME. A byte
     forgotten there is a level that plays slightly wrong in a way
     nobody can see.

So the instrument for (4) has no model in it: PLAY the level, kill her,
and compare EVERY BYTE of the engine's RAM against a machine that has
just booted and run the same number of game frames. Its control is a
line of LEVEL_RESET knocked out - the sweep has to report it, or its
silence about the rest means nothing.
"""
import os
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import symbols, boot, sync                          # noqa: E402
import make_fade                                               # noqa: E402
from cpc import CPC                                            # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DSK = os.path.abspath(os.path.join(ROOT, "build", "kara.dsk"))
STUB, SCRATCH = 0x9000, 0x9200
JOY_RIGHT, JOY_FIRE = 0x08, 0x10
GS_PLAY, GS_DEAD, GS_CLEAR = 0, 1, 2
KST_DIE, ER_OPENED = 10, 3
SETTLE = 35                     # game frames each machine runs after its
                                # level is installed, before it is read

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


# =====================================================================
# 1. Where she starts.
# =====================================================================
def spawn_checks(sym):
    print("\n  where she starts, and it is the LEVEL that says:")

    def start(poke=()):
        m = CPC(); m.run_frames(150)
        m.insert_disc(DSK); m.type_text('RUN"DISC\n'); m.run_frames(300)
        # ... into the RELOCATED core. The bootstrap LDIRed the image to
        # &0040 within a frame of the CALL, so these ARE the assembler's
        # initialisers, and the title is still up: nothing has run
        # SCROLL_INIT yet.
        for a, v in poke:
            m.poke(a, v)
        m.run_frames(100)
        from bench import past_intro
        past_intro(m, sym)
        for _ in range(200):
            m.run_frames(2)
            if m.peek(sym["LEVEL_OK"]):
                m.run_frames(6)
                break
        return (m.peek(sym["KARA_WX"]) | m.peek(sym["KARA_WX"] + 1) << 8,
                m.peek(sym["KARA_WY"]), m)

    wx, wy, m = start()
    t = sym["ENT_TABLE"]
    kind = m.peek(t)
    rx = m.peek(t + 1) | m.peek(t + 2) << 8
    ry = m.peek(t + 3) | m.peek(t + 4) << 8
    check("the City carries an EK_PLAYER_START, first in the table",
          kind == 0 and m.peek(t + 5) & 1,
          f"kind {kind}, flags {m.peek(t + 5)}, at ({rx},{ry})")
    # THE RECORD IS IN THE FORMAT'S UNITS AND SHE IS NOT. x is world
    # PIXELS against her byte column and y is the BASE of the hitbox
    # against her box's top (8.6), which is the conversion PLAYER_SPAWN
    # exists to do.
    box_h = ry - (rx and 0) - 0
    check("... and she is standing on the ground under it",
          wx == rx // 2, f"record x {rx} px -> wx {rx // 2}, she is at {wx}")
    check("... having fallen the last few pixels onto the roof",
          wy == 32, f"KARA_WY {wy}; the record puts her box top at "
                    f"{ry - 64} and the roof is at world y 96")

    # THE CONTROL. Poke the initialisers somewhere impossible: if
    # PLAYER_SPAWN is doing anything at all she lands in the same place.
    off = sym["KARA_WX"]
    wx2, wy2, _ = start([(off, 0), (off + 1, 1), (off + 2, 200)])
    check("the assembler's initialisers no longer decide",
          (wx2, wy2) == (wx, wy),
          f"poked to (256,200) and she is still at ({wx2},{wy2})")
    # ... AND THE CONTROL ON THE CONTROL. A poke that landed in the
    # wrong place would agree for no reason at all. The first version of
    # this check poked the IMAGE at &4027, which the bootstrap had
    # copied down and abandoned, and passed while proving nothing.
    wx3, wy3, _ = start([(off, 0), (off + 1, 1), (off + 2, 200),
                         (sym["PLAYER_SPAWN"], 0xC9)])
    check("... and with PLAYER_SPAWN as a RET they decide again",
          (wx3, wy3) != (wx, wy), f"she starts at ({wx3},{wy3})")


# =====================================================================
# 2. The fade.
# =====================================================================
def fade_checks(sym, m):
    print("\n  the fade, read off the gate array:")
    rgb = make_fade.hardware_colours()
    lev = make_fade.level
    by = {(lev(r), lev(g), lev(b)): hw for hw, (r, g, b, _) in rgb.items()}
    name = {hw: v[3] for hw, v in rgb.items()}
    black = by[(0, 0, 0)]

    def darker(hw):
        r, g, b, _ = rgb[hw]
        return by[(max(lev(r) - 1, 0), max(lev(g) - 1, 0), max(lev(b) - 1, 0))]

    def border(hw, k):
        """FADE_LEVEL k steps on a palette whose BORDER is `hw`.

        The pen registers cannot be read back, so the fade is measured
        where it shows - and the border is the one palette entry that is
        also half the picture, so no tile has to be found to sample.
        """
        m.write_ram(SCRATCH, bytes([0x40 | black] * 16 + [0x40 | hw]))
        f = sym["FADE_LEVEL"]
        m.write_ram(STUB, bytes([0xF3, 0x21, SCRATCH & 255, SCRATCH >> 8,
                                 0x3E, k, 0xCD, f & 255, f >> 8, 0x18, 0xFE]))
        m.set_pc(STUB)
        for _ in range(200000):
            m.run_us(1)
            if m.pc == STUB + 9:
                break
        m.run_frames(2)
        return m.framebuffer()[150 * 1024 + 8]

    bad = []
    for hw in sorted(rgb):
        want, x = [], hw
        for _ in range(3):
            want.append(x)
            x = darker(x)
        got = [border(hw, k) for k in range(3)]
        if got != want:
            bad.append(f"{name[hw]}: {[name.get(g, g) for g in got]} "
                       f"against {[name[w] for w in want]}")
    check("every ramp is the cube's, all 27 colours x 3 levels",
          not bad, bad[0] if bad else "81 readings")
    ends = [(border(hw, 0), border(hw, 2)) for hw in sorted(rgb)]
    check("k = 0 leaves every colour alone",
          all(a == hw for (a, _), hw in zip(ends, sorted(rgb))))
    check("k = FADE_STEPS is black for every one of them",
          all(b == black for _, b in ends))
    check("... and 26 of the 27 changed on the way",
          sum(a != b for a, b in ends) == 26,
          f"{sum(a != b for a, b in ends)}; black cannot")


# =====================================================================
# 3. What ends a level.
# =====================================================================
def trigger_checks(sym, m):
    print("\n  what ends a level, driven from a stub:")

    def flow(state, result, kstate, done):
        for n, v in (("GAME_STATE", state), ("ENT_RESULT", result),
                     ("KARA_STATE", kstate), ("KARA_DONE", done)):
            m.poke(sym[n], v)
        f = sym["FLOW_CHECK"]
        m.write_ram(STUB, bytes([0xF3, 0xCD, f & 255, f >> 8, 0x18, 0xFE]))
        m.set_pc(STUB)
        for _ in range(100000):
            m.run_us(1)
            if m.pc == STUB + 4:
                break
        return m.peek(sym["GAME_STATE"])

    check("a door that gave way clears the level",
          flow(GS_PLAY, ER_OPENED, 0, 0) == GS_CLEAR)
    check("her `die` run, played through, is a death",
          flow(GS_PLAY, 0, KST_DIE, 1) == GS_DEAD)
    # DEATH IS KARA_DONE AND NOT PLAYER_HP. Zero hit points is the
    # instant she is hit; what the player has to see is six cels and the
    # 600 ms the artist holds the last one for (7.1).
    check("... and the same run still playing is not",
          flow(GS_PLAY, 0, KST_DIE, 0) == GS_PLAY,
          "PLAYER_HP would have taken the screen away on the frame the "
          "round landed")
    check("nothing else ends it", flow(GS_PLAY, 1, 4, 1) == GS_PLAY)
    check("and a level already leaving is not asked twice",
          flow(GS_CLEAR, 0, KST_DIE, 1) == GS_CLEAR,
          "a death during the fade would take the clear's exit away")


# =====================================================================
# 4. The restart, against a machine that has just booted.
# =====================================================================
def gframes(m, sym, n):
    for _ in range(n):
        sync(m, sym, half=0)
        m.run_frames(1)


def play_and_die(sym, nobble=None):
    """Dirty everything a level can dirty, then kill her."""
    m = boot(sym, scroll=True)
    if nobble:
        m.write_ram(nobble, bytes([0, 0, 0]))
    for t in range(90):
        m.joystick(JOY_RIGHT | (JOY_FIRE if (t % 14) < 5 else 0))
        m.run_frames(2)
    m.joystick(0); m.run_frames(4)
    # ... and a few the walk cannot reach in ninety frames. A poke is a
    # fair question here: what is asked is whether the restart puts the
    # world back, not whether she can get it into that state.
    for n, v in (("COINS_COUNT", 4), ("STATUES_HELD", 2),
                 ("CURRENT_BOOK_ID", 3), ("AMMO_RESERVE", 5),
                 ("HURT_FLASH", 2), ("RELOAD_TIMER", 9)):
        m.poke(sym[n], v)
    dirt = dict(keys=m.peek(sym["KEYS_COUNT"]),
                wx=m.peek(sym["KARA_WX"]) | m.peek(sym["KARA_WX"] + 1) << 8,
                view=m.peek(sym["WORLD_X"]))
    m.poke(sym["PLAYER_HP"], 0)
    for _ in range(400):
        m.run_frames(2)
        if (m.peek(sym["GAME_STATE"]) == GS_PLAY
                and m.peek(sym["KARA_STATE"]) != KST_DIE):
            break
    else:
        raise SystemExit("the restart never finished")
    return m, dirt


def restart_checks(sym):
    print("\n  she dies and the level comes back:")
    m, dirt = play_and_die(sym)
    check("the play dirtied something to put back",
          dirt["keys"] and dirt["view"],
          f"she took {dirt['keys']} key(s), walked to wx {dirt['wx']} and "
          f"scrolled the view to character {dirt['view']}")
    gframes(m, sym, SETTLE)

    fresh = boot(sym, scroll=True)
    gframes(fresh, sym, SETTLE)

    for n, size in (("MAP_ADDR", 2048), ("ENT_TABLE", 24 * 8),
                    ("TILE_ATTR", 256)):
        a = sym[n]
        bad = sum(fresh.peek(a + k) != m.peek(a + k) for k in range(size))
        check(f"{n} is the level's again, all {size} bytes", bad == 0,
              f"{bad} differ" if bad else
              "the cells she emptied, the records she took, the flags")
    a, n = sym["LEVEL_IMAGE"], 2405
    bad = sum(fresh.peek(a + k) != m.peek(a + k) for k in range(n))
    check("... out of a LEVEL_IMAGE nothing ever wrote on", bad == 0,
          "which is the whole reason a restart needs no disc read")

    for n in ("PLAYER_HP", "KEYS_COUNT", "COINS_COUNT", "STATUES_HELD",
              "CURRENT_BOOK_ID", "AMMO_RESERVE", "MAG_LEFT", "MAG_RIGHT",
              "RELOAD_TIMER", "HURT_FLASH", "BUL_LIVE", "BUL_TOP",
              "ENT_RESULT", "V_REQUEST", "VIEW_STEP", "H_PENDING"):
        if fresh.peek(sym[n]) != m.peek(sym[n]):
            check(f"{n} came back", False,
                  f"fresh {fresh.peek(sym[n])}, restarted {m.peek(sym[n])}")
            break
    else:
        check("and every byte of what she carries, her guns and the "
              "frame's pending work", True, "16 of them, named")
    return m


# =====================================================================
# 5. ... and the sweep that finds what nobody thought of.
# =====================================================================
FREE = {"FRAME_COUNT", "IRQ_TICKS", "IRQ_LAST", "FRAME_TICK0",
        "HEAD_ANCHOR", "BUL_PHASE", "HEARTBEAT"}
# Scratch a routine writes before it reads: the span blitter's
# self-modified immediates, the save-unders and erase scripts, the
# repaint's and DRAW_CELL's working cell, the record the AABB last
# found, and the fade's own. Each is named rather than a range, and the
# control below is what says the list is not just long enough to pass.
DEAD = ("SPAN_", "CX_", "HUD_STEP", "HUD_V_", "HUD_BANK", "FADE_PAL",
        "FADE_STEP", "ENT_HIT", "ENT_RP_WC", "ENT_RP_WR", "ENT_RP_WORD",
        "CELL_WORD", "CELL_WC", "CELL_WR", "CELL_COUNT")


def sweep(sym, ra, rb):
    """Every byte of engine RAM, with the dead ones named."""
    by_addr = sorted((v, k) for k, v in sym.items() if "." not in k)

    def where(x):
        lo, nm = by_addr[0]
        for v, n in by_addr:
            if v > x:
                break
            lo, nm = v, n
        return f"{nm}+{x - lo}" if x != lo else nm

    out = []
    for i in list(range(0x0040, 0x4000)) + list(range(0x8000, 0xBF00)):
        if ra[i] == rb[i]:
            continue
        if 0x8100 <= i < 0xA000:        # save-unders and erase scripts
            continue
        w = where(i)
        if w.split("+")[0] in FREE or w.startswith(DEAD):
            continue
        out.append((i, w, ra[i], rb[i]))
    return out


def sweep_checks(sym, restarted):
    """... and the alignment is SEARCHED, because it has to be.

    Both machines are found by POLLING - run two frames, look - so each
    marker is up to two game frames late and the pair up to four apart.
    Four game frames is four pixels of drone and a cel of her idle, and
    neither is a fault. So the fresh machine is stepped one game frame
    at a time and the difference counted at each: what "a restart is a
    level start" means is that there EXISTS an alignment at which the
    two machines are the same machine, and a restart that forgot a byte
    has no such alignment - which is what the control shows.
    """
    print("\n  and the sweep, which has no model in it:")
    # BOTH MACHINES AT THE SAME HALF OF THE GAME FRAME. The loop waits
    # for two VSYNCs and FRAME_HALF is the engine saying which it is in
    # (src/main.asm) - so a snapshot taken without asking compares a
    # frame that has drawn her against one that has erased her.
    sync(restarted, sym, half=0)
    rb = bytes(restarted.read_ram(0, 0x10000))
    fresh = boot(sym, scroll=True)
    gframes(fresh, sym, SETTLE - 6)

    best, at, worst = None, None, 0
    for off in range(14):
        sync(fresh, sym, half=0)
        d = sweep(sym, bytes(fresh.read_ram(0, 0x10000)), rb)
        worst = max(worst, len(d))
        if best is None or len(d) < len(best):
            best, at = d, SETTLE - 6 + off
        fresh.run_frames(1)
    check("nothing the restart forgot", not best,
          f"32,448 bytes of engine RAM, aligned at +{at} game frames "
          f"(the worst alignment in the window differs in {worst})"
          if not best else
          "; ".join(f"{w} {x}/{y}" for _, w, x, y in best[:6]))

    # THE CONTROL. Knock the line that clears KEYS_COUNT out of
    # LEVEL_RESET - three NOPs over `ld (KEYS_COUNT),a` - and the key
    # she took has to still be in her hand AT EVERY ALIGNMENT, because
    # no amount of waiting puts a key back on a roof. A sweep that
    # cannot see one forgotten byte has nothing to say about the rest.
    key = bytes([0x32, sym["KEYS_COUNT"] & 255, sym["KEYS_COUNT"] >> 8])
    base = sym["LEVEL_RESET"]
    img = bytes(restarted.read_ram(base, 64))
    k = img.find(key)
    if k < 0:
        check("the control could be armed", False,
              "no `ld (KEYS_COUNT),a` in LEVEL_RESET's first 64 bytes")
        return
    nobbled, _ = play_and_die(sym, nobble=base + k)
    gframes(nobbled, sym, SETTLE)
    sync(nobbled, sym, half=0)
    rn = bytes(nobbled.read_ram(0, 0x10000))
    seen = 0
    for off in range(14):
        sync(fresh, sym, half=0)
        d = sweep(sym, bytes(fresh.read_ram(0, 0x10000)), rn)
        seen += any(w.startswith("KEYS_COUNT") for _, w, _, _ in d)
        fresh.run_frames(1)
    check("... and with one line of LEVEL_RESET knocked out it says so",
          seen == 14, f"the key is still in her hand at {seen} of 14 "
                      f"alignments")


def clear_checks(sym):
    print("\n  the way out opens, and the game starts again:")
    m = boot(sym, scroll=True)
    m.joystick(JOY_RIGHT)
    for _ in range(60):
        m.run_frames(2)
    m.joystick(0)
    m.poke(sym["COINS_COUNT"], 7)
    away = m.peek(sym["WORLD_X"])
    # FLOW_CHECK's own reading of ER_OPENED is checked from the stub
    # above; ENT_UPDATE clears ENT_RESULT at the top of every frame, so
    # a poke made between frames is gone before FLOW_CHECK sees it.
    # What is driven here is the STEP, which is the half with a disc
    # read in it.
    m.poke(sym["GAME_STATE"], GS_CLEAR)
    titled = False
    for _ in range(60):
        m.run_frames(4)
        if m.peek(sym["GAME_STATE"]) == GS_CLEAR and m.peek(sym["WORLD_X"]) == 0:
            titled = True
    m.run_frames(60)
    check("it holds on the title, waiting to be answered",
          m.peek(sym["GAME_STATE"]) == GS_CLEAR,
          "INTRO_WAIT, the same prompt the game opens on")
    m.joystick(JOY_FIRE); m.run_frames(6); m.joystick(0)
    for _ in range(300):
        m.run_frames(2)
        if m.peek(sym["GAME_STATE"]) == GS_PLAY:
            break
    m.run_frames(40)
    wx = m.peek(sym["KARA_WX"]) | m.peek(sym["KARA_WX"] + 1) << 8
    check("the press starts the level again", m.peek(sym["GAME_STATE"]) == GS_PLAY)
    check("... at the start record, with an empty pocket",
          wx == 43 and m.peek(sym["COINS_COUNT"]) == 0,
          f"wx {wx}, coins {m.peek(sym['COINS_COUNT'])}, view was at "
          f"character {away}")
    check("... and the level is a level", m.peek(sym["LEVEL_OK"]) == 1,
          "LEVEL_OK is what says MAP_INSTALL took it; 0 here means the "
          "loop runs on with no heroine in the picture")


def main():
    sym = symbols()
    print("The level FSM - where she starts, the fade, and what a "
          "restart means")
    spawn_checks(sym)
    m = boot(sym, scroll=True)
    fade_checks(sym, m)
    trigger_checks(sym, m)
    restarted = restart_checks(sym)
    sweep_checks(sym, restarted)
    clear_checks(sym)

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
