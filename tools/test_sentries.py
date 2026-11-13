#!/usr/bin/env python3
"""The SENTRIES (CLAUDE.md 8.27): the City's agent, the forest's sniper,
the desert's mercenary and the station's guard - 24x64 characters drawn
by a COMPILED cel - and the station's wall turret, which the span blitter
draws. What is checked here, on a 6128:

  * the compiled cels against the span blitter, for all four and both
    facings: the aim, the toggle to the recoil and back, and the recoil
    drawn fresh, each the same video RAM byte for byte, a lift that puts
    the screen back, the encoder against RASM's, and what each costs -
    with a position whose line crosses a page and the toggle run over
    the background as the controls;
  * that rule in the tools, and every sentry the shipped levels place on
    a column that keeps it;
  * a mercenary in play: it keeps its post and is never engaged, it is
    drawn when it comes on and redrawn when it turns and not between -
    with EN_STILL answering "redraw" as the control - it fires and hits,
    every shot its recoil TOGGLED in and out with the picture the cel it
    says on every frame - with ENEMY_KEEP off, a lift and a fresh draw
    each, as the control - and it goes down where it stands, flashing,
    and stays down;
  * every level with a sentry in it, driven with them ON: the station's
    four, whose lasers are the one place a sentry and the trap painter
    share a frame, with every on-screen cell the map's on every game
    frame - and HZ_PEND_ADD's off-screen reject, which is what paid for
    it, as the control; the forest's two snipers; the City's agent;
  * and the lock beside each kind.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_forest7 as F                                        # noqa: E402
from bench import boot, sync                                    # noqa: E402
import compile_sprite as cs                                     # noqa: E402
import sentries                                                 # noqa: E402

ROOT = os.path.join(HERE, "..")
LEV = os.path.join(ROOT, "build", "levels")
BUILD = os.path.join(ROOT, "build")
JOY_UP, JOY_DOWN, JOY_LEFT, JOY_RIGHT, JOY_FIRE = 0x01, 0x02, 0x04, 0x08, 0x10
EK_ENEMY, EF_TAKEN = 2, 2
GS_PLAY, GS_CLEAR = 0, 2
SENTRY = {0: ("level1_city", "cityagent"), 2: ("level2_forest", "forestsniper"),
          7: ("level5_desert", "desertmercenary"),
          8: ("level6_station", "stationcyber")}
TURRET = 9
STUB, HOOK, COUNT = 0x9000, 0x9300, 0x93F0

fails = []
sym = F.symbols()
REAL_WRONG = F.wrong_cells


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        fails.append(name)


def w(m, a):
    return m.peek(a) | m.peek(a + 1) << 8


def inc_value(env, name, key):
    return cs.inc_value(os.path.join(LEV, env, name + ".inc"), key)


def records(n):
    blob = open(os.path.join(BUILD, f"level_{n}.lvl"), "rb").read()
    off, cnt = blob[15] | blob[16] << 8, blob[10]
    return [blob[off + 8 * i:off + 8 * i + 8] for i in range(cnt)]


# =====================================================================
# 1. THE COMPILED CEL AGAINST THE SPAN BLITTER
# =====================================================================
def run(m, code):
    m.write_ram(STUB, bytes(code))
    m.set_pc(STUB)
    spin = STUB + len(code) - 2
    for us in range(1, 400000):
        m.run_us(1)
        if m.pc == spin:
            return us * 4
    raise SystemExit("a stub never returned")


def stub(pre, target):
    return [0xF3] + pre + [0xCD, target & 0xFF, target >> 8, 0x18, 0xFE]


def ld16(op, v):
    return [op, v & 0xFF, v >> 8]


def rasm_bytes(ins):
    """The same instruction list through RASM, which is what says the
    compiler's own encoder is right."""
    tmp = os.path.join(BUILD, "test_sentries_enc")
    with open(tmp + ".asm", "w") as f:
        f.write("        org &6000\n")
        for i in ins:
            if i.startswith("jr z,"):
                i = f"jr z,$+{int(i[5:]) + 2}"
            f.write(f"        {i}\n")
    r = subprocess.run(["rasm", tmp + ".asm", "-amper", "-ob", tmp + ".bin"],
                       capture_output=True, text=True)
    out = open(tmp + ".bin", "rb").read() if r.returncode == 0 else b""
    for x in (".asm", ".bin"):
        if os.path.exists(tmp + x):
            os.remove(tmp + x)
    return out


def compiled():
    print("\nTHE COMPILED CELS: against the span blitter, byte for byte")
    m = boot(sym, scroll=True)
    m.poke(sym["ENEMY_LIVE"], 0)
    sync(m, sym, 0)
    scroll = w(m, sym["SCROLL"])
    script, slot, es_cel = sym["ENEMY_SCRIPT"], 0x9200, 8

    def addr(x, y):
        ma = (scroll + (y >> 3) * 40 + (x >> 1)) & 1023
        return 0xC000 | ((y & 7) << 11) | (ma << 1) | (x & 1)

    def safe(x, y):
        return all(((addr(x, y + 8 * r) & 0xFF) + 12) <= 256 for r in range(8))

    base = run(m, stub([], sym["BANK_RESTORE"]))
    vram0 = m.read_ram(0xC000, 0x4000)
    page = [0x01, 0xC0, 0x7F, 0xED, 0x49]
    times = []
    for kind, (env, name) in sorted(SENTRY.items()):
        aim = inc_value(env, name, "_FIRE_FIRST")
        for face in ("", "_l"):
            span = open(os.path.join(LEV, env, name + face + ".bin"), "rb").read()
            code = open(os.path.join(LEV, env, name + "c" + face + ".bin"), "rb").read()
            ins = cs.sentry(env, name, face)[0]
            same_tool = code == cs.assemble(ins)
            same_rasm = code == rasm_bytes(ins)
            m.write_ram(0x4000, span)           # bank 1, the &C0 config's
            m.write_ram(0x6000, code)

            def span_draw(x, y, cel):
                """The span blitter's picture of a cel over the background."""
                m.write_ram(0xC000, vram0)
                off = span[2 * cel] | span[2 * cel + 1] << 8
                pre = [0x3E, 0, 0x32] + ld16(0, sym["SPAN_SKIP"])[1:] + page \
                    + ld16(0x21, 0x4000 + off + 2) \
                    + ld16(0x11, addr(x, y + span[off])) + ld16(0x01, 0x8000) \
                    + [0x3E, span[off + 1]]
                t = run(m, stub(pre, sym["SPAN_DRAW"]))
                return m.read_ram(0xC000, 0x4000), t - base

            def blob(x, y, cel, fresh):
                """The blob, as EN_DRAW_C enters it."""
                m.poke(slot + es_cel, cel)
                if fresh:
                    m.poke(script, 0xFF)
                pre = page + [0xDD] + ld16(0x21, slot) + ld16(0x11, addr(x, y)) \
                    + ld16(0x21, script) + ld16(0x01, 0x6000)
                t = run(m, stub(pre, 0x6000))
                return m.read_ram(0xC000, 0x4000), t - base

            def lift():
                run(m, stub(ld16(0x21, script), sym["SPAN_ERASE_AT"]))
                return m.read_ram(0xC000, 0x4000) == vram0

            def diff(a, b):
                return sum(p != q for p, q in zip(a, b))

            res = []
            for y in (64, 96):
                x = next(x for x in range(4, 60, 2) if safe(x, y))
                pic_a, t_span = span_draw(x, y, aim)
                pic_r, _ = span_draw(x, y, aim + 1)
                m.write_ram(0xC000, vram0)
                v1, t_fresh = blob(x, y, aim, True)
                v2, t_tog = blob(x, y, aim + 1, False)
                v3, _ = blob(x, y, aim, False)
                back1 = lift()
                v4, _ = blob(x, y, aim + 1, True)        # fresh, on the recoil
                back2 = lift()
                res.append((x, y, diff(v1, pic_a), diff(v2, pic_r), diff(v3, pic_a),
                            diff(v4, pic_r), back1 and back2, t_span, t_fresh, t_tog))
            check(f"{name}{face}: the aim, the toggle to the recoil and back, and "
                  f"the recoil drawn fresh, are the span blitter's pictures",
                  same_tool and same_rasm and all(r[2:6] == (0, 0, 0, 0) and r[6] for r in res),
                  f"{len(code)} bytes, {'' if same_rasm else 'NOT '}RASM's encoding; " + ", ".join(
                      f"at {x},{y}: {a}/{t}/{b}/{f} bytes differ, "
                      f"{'lifted clean' if k else 'NOT lifted clean'}"
                      for x, y, a, t, b, f, k, _, _, _ in res))
            times.append((name + face, res[0][7], res[0][8], res[0][9]))
            tried, d = 0, 0
            for x in (x for x in range(4, 60, 2) if not safe(x, 64)):
                tried += 1
                pic_a, _ = span_draw(x, 64, aim)
                m.write_ram(0xC000, vram0)
                v, _ = blob(x, 64, aim, True)
                d = diff(v, pic_a)
                if d:
                    break
            check("... and where a line of it crosses a page, it does not",
                  d > 0, f"at {x},64: {d} bytes differ, the first of {tried} such "
                  f"columns whose art meets the page - the rule tools/sentries.py keeps")
    for name, ts, tf, tt in times[::2]:
        print(f"      {name}: the span blitter's aim {ts:,} T; compiled, the aim "
              f"and its save {tf:,} T and the toggle to the recoil {tt:,} T")

    # THE CONTROL: the toggle assumes the screen holds the OTHER cel. Run it
    # over the background instead - which is what a toggle without the
    # lift's guarantee would meet - and it is not the recoil.
    env, name = SENTRY[8]
    aim = inc_value(env, name, "_FIRE_FIRST")
    span = open(os.path.join(LEV, env, name + ".bin"), "rb").read()
    m.write_ram(0x4000, span)
    m.write_ram(0x6000, open(os.path.join(LEV, env, name + "c.bin"), "rb").read())
    x = next(x for x in range(4, 60, 2) if safe(x, 64))
    pic_r, _ = span_draw(x, 64, aim + 1)
    m.write_ram(0xC000, vram0)
    blob(x, 64, aim, True)
    m.write_ram(0xC000, vram0)                  # the aim gone, its save kept
    v, _ = blob(x, 64, aim + 1, False)
    check("... and the toggle run over the background is NOT the recoil",
          diff(v, pic_r) > 0, f"{diff(v, pic_r)} bytes differ")


# =====================================================================
# 2. THE RULE, IN THE TOOLS AND IN THE SHIPPED LEVELS
# =====================================================================
def rule():
    print("\nTHE RULE: where a sentry may stand")
    placed = []
    for n in range(1, 25):
        if not os.path.exists(os.path.join(BUILD, f"level_{n}.lvl")):
            continue
        for r in records(n):
            if r[0] == EK_ENEMY and r[6] in SENTRY:
                x, base = (r[1] | r[2] << 8) // 8, (r[3] | r[4] << 8) // 16
                placed.append((n, r[6], x, base,
                               cs.page_safe(sentries.word(x, base), 8, 6)))
    check("every sentry a shipped level places keeps every line in a page",
          placed and all(ok for *_, ok in placed),
          f"{len(placed)} placed: " + ", ".join(
              f"L{n} {SENTRY[k][1]}@{x}" for n, k, x, _, _ in placed))
    bad = next(x for x in range(0, 120) if not cs.page_safe(sentries.word(x, 9), 8, 6))
    try:
        sentries.check(0, [(bad, 9)], b"")
        refused = False
    except AssertionError as e:
        refused = "page" in str(e)
    check("... and the tool refuses a column that does not", refused,
          f"row 9, tile {bad}")
    good = next(x for x in range(0, 120) if cs.page_safe(sentries.word(x, 9), 8, 6))
    pickup = bytes([4, (good + 1) * 8 & 255, (good + 1) * 8 >> 8, 8 * 16 & 255,
                    8 * 16 >> 8, 1 | 8, 0, 0])
    try:
        sentries.check(0, [(good, 9)], pickup)
        refused = False
    except AssertionError as e:
        refused = "under the sentry" in str(e)
    check("... and a pickup under one, whose repaint it would not see", refused,
          f"a pickup at tile {good + 1} under a sentry at {good}")


# =====================================================================
# 3. A MERCENARY IN PLAY
# =====================================================================
def hook(m):
    """Count EN_DRAW_C's entries by jumping its first instruction through a
    stub in the staging buffer's free tail: a FRESH draw - the script
    emptied by the lift, so the blob saves and draws the aim - in COUNT,
    and a TOGGLE - the script kept, the other cel on the screen - in
    COUNT + 2."""
    a = sym["EN_DRAW_C"]
    first = bytes(m.peek(a + i) for i in range(3))
    code = ([0xE5, 0xF5] + ld16(0x3A, sym["ENEMY_SCRIPT"]) + [0x3C, 0x20, 9]
            + ld16(0x2A, COUNT) + [0x23] + ld16(0x22, COUNT) + [0x18, 7]
            + ld16(0x2A, COUNT + 2) + [0x23] + ld16(0x22, COUNT + 2)
            + [0xF1, 0xE1] + list(first) + ld16(0xC3, a + 3))
    m.write_ram(HOOK, bytes(code))
    for i in range(4):
        m.poke(COUNT + i, 0)
    for i, b in enumerate(ld16(0xC3, HOOK)):
        m.poke(a + i, b)


def draws(m):
    return w(m, COUNT)


def toggles(m):
    return w(m, COUNT + 2)


def picture(m, ix):
    """What is on the screen in the sentry's box against what should be:
    the cel EN_DREW_CEL says it drew, composited over the background its
    erase script holds - read back through that script's own addresses.
    -> (the cel, bytes wrong, bytes looked at)"""
    kind = m.peek(ix + sym["ES_TYPE"])
    env, name = SENTRY[kind]
    face = "_l" if m.peek(sym["EN_DREW_FACE"]) else ""
    span = open(os.path.join(LEV, env, name + face + ".bin"), "rb").read()
    aim = inc_value(env, name, "_FIRE_FIRST")
    cel = m.peek(sym["EN_DREW_CEL"])
    want = cs.cel_bytes(span, cel)
    segs = cs.segments([cs.cel_bytes(span, aim), cs.cel_bytes(span, aim + 1)])[0]
    p, wrong, seen = sym["ENEMY_SCRIPT"], 0, 0
    for (y, lo, n, _) in segs:
        cnt, at = m.peek(p), w(m, p + 1)
        if cnt != n:
            return cel, -1, seen
        for k in range(n):
            bg = m.peek(p + 3 + k)
            mask, data = want.get((y, lo + k), (0xFF, 0))
            wrong += m.peek(at + k) != (bg & mask) | data
            seen += 1
        p += 3 + n
    return cel, wrong, seen


def merc():
    print("\nA MERCENARY IN PLAY: level 17")
    m, took = F.to_level(sym, 17)
    live = m.peek(sym["ENEMY_LIVE"])
    check("level 17's two mercenaries are spawned", live == 2,
          f"ENEMY_LIVE {live}, {took} hardware frames in")
    hook(m)
    first, eng, xs = None, set(), set()
    for g in range(400):
        F.gframe(m, sym, JOY_RIGHT)
        m.poke(sym["PLAYER_HP"], 100)
        if w(m, sym["ENEMY_ENG"]):
            eng.add(g)
        cur = w(m, sym["ENEMY_CUR"])
        if cur:
            xs.add(w(m, cur + sym["ES_X"]))
        if m.peek(sym["ENEMY_DREW"]):
            first = g
            break
    ix = w(m, sym["ENEMY_CUR"])
    check("it is drawn when it comes on, and never engaged",
          first is not None and not eng and draws(m) == 1,
          f"drawn at game frame {first}, {draws(m)} fresh draw(s), "
          f"ENEMY_ENG never set")
    for _ in range(4):
        F.gframe(m, sym, 0)
    for i in range(4):
        m.poke(COUNT + i, 0)
    hits, changes, recoil, wrong, seen, blind = 0, 0, 0, 0, 0, None
    aim = m.peek(ix + sym["ES_CEL"])
    x0, y0 = w(m, ix + sym["ES_X"]), w(m, ix + sym["ES_Y"])
    for g in range(150):
        shown = m.peek(sym["EN_DREW_CEL"])
        F.gframe(m, sym, 0)
        changes += m.peek(sym["EN_DREW_CEL"]) != shown
        if m.peek(sym["PLAYER_HP"]) < 100:
            hits += 1
            m.poke(sym["PLAYER_HP"], 100)
        cel, bad, n = picture(m, ix)
        recoil += cel != aim
        wrong, seen = wrong + (bad if bad >= 0 else 9999), seen + n
        if cel != aim and blind is None:        # read as the aim instead
            m.poke(sym["EN_DREW_CEL"], aim)
            blind = picture(m, ix)[1]
            m.poke(sym["EN_DREW_CEL"], cel)
    fresh, tog = draws(m), toggles(m)
    check("standing in its sight: it fires and hits, and is not redrawn",
          hits > 0 and fresh == 0
          and (w(m, ix + sym["ES_X"]), w(m, ix + sym["ES_Y"])) == (x0, y0),
          f"{hits} hits in 150 game frames, {fresh} fresh draws, at its post")
    check("... and it is SEEN to fire: every shot is the recoil, toggled on and "
          "off over the aim, and the picture is the cel it says on every frame",
          recoil > 0 and changes > 0 and tog == changes and wrong == 0,
          f"the recoil up on {recoil} frames, {changes} changes of cel, "
          f"{tog} toggles; {wrong} bytes wrong of {seen}")
    check("... and the check sees the difference: a recoil's frame read as the aim",
          blind is not None and blind > 0, f"{blind} bytes wrong")
    # THE CONTROL: the toggle is what spares it the lift. Send EN_STILL's
    # compiled answer to "redraw" and every change of cel is a fresh draw
    st, top = sym["EN_STILL"], sym["EN_DRAW_C"]
    jump = next(a for a in range(st, top) if m.peek(a) == 0xE1
                and m.peek(a + 1) == 0xC3 and w(m, a + 2) == sym["ENEMY_KEEP"])
    m.poke(jump, 0xB7)                          # or a
    m.poke(jump + 1, 0xC9)                      # ret
    for i in range(4):
        m.poke(COUNT + i, 0)
    changes = 0
    for _ in range(150):
        shown = m.peek(sym["EN_DREW_CEL"])
        F.gframe(m, sym, 0)
        changes += m.peek(sym["EN_DREW_CEL"]) != shown
        m.poke(sym["PLAYER_HP"], 100)
    m.poke(jump, 0xE1)
    m.poke(jump + 1, 0xC3)
    check("... and without ENEMY_KEEP every change of cel is a lift and a fresh draw",
          changes > 0 and draws(m) == changes and toggles(m) == 0,
          f"{changes} changes of cel, {draws(m)} fresh draws, {toggles(m)} toggles")
    # THE CONTROL: EN_STILL answering "redraw" every time
    keep = [m.peek(sym["EN_STILL"] + i) for i in range(2)]
    m.poke(sym["EN_STILL"], 0xB7)               # or a
    m.poke(sym["EN_STILL"] + 1, 0xC9)           # ret
    n0 = draws(m)
    for _ in range(50):
        F.gframe(m, sym, 0)
        m.poke(sym["PLAYER_HP"], 100)
    every = draws(m) - n0
    for i, b in enumerate(keep):
        m.poke(sym["EN_STILL"] + i, b)
    check("... and with EN_STILL answering 'redraw', it is redrawn every frame",
          every >= 45, f"{every} compiled draws in 50 game frames")
    # ITS TURN: walk past it, and it is redrawn when it faces the other way
    n0, face0, turned = draws(m), m.peek(ix + sym["ES_FACE"]), None
    hx = w(m, ix + sym["ES_X"]) // 2 + 20
    for g in range(300):
        F.gframe(m, sym, JOY_RIGHT)
        m.poke(sym["PLAYER_HP"], 100)
        if m.peek(ix + sym["ES_FACE"]) != face0 and turned is None:
            turned = g
        if w(m, sym["KARA_WX"]) > hx:
            break
    check("walked past, it turns round and is redrawn for it",
          turned is not None and 1 <= draws(m) - n0 <= 3,
          f"turned at game frame {turned}, {draws(m) - n0} compiled draw(s)")
    # THE KILL: back to it, turned to it, and three rounds
    m2, _ = F.to_level(sym, 17)
    for g in range(400):
        F.gframe(m2, sym, JOY_RIGHT)
        m2.poke(sym["PLAYER_HP"], 100)
        if m2.peek(sym["ENEMY_DREW"]):
            break
    ix = w(m2, sym["ENEMY_CUR"])
    rec = w(m2, ix + sym["ES_REC"])
    x0, y0 = w(m2, ix + sym["ES_X"]), w(m2, ix + sym["ES_Y"])
    shots = 0
    for g in range(300):
        F.gframe(m2, sym, JOY_FIRE if g % 6 < 2 else 0)
        m2.poke(sym["PLAYER_HP"], 100)
        if g % 6 == 2:
            shots += 1
        if m2.peek(ix + sym["ES_HP"]) == 0:
            break
    down = m2.peek(ix + sym["ES_HP"]) == 0
    drawn, still, gone = [], True, None
    for g in range(60):
        F.gframe(m2, sym, 0)
        m2.poke(sym["PLAYER_HP"], 100)
        drawn.append(m2.peek(sym["ENEMY_DREW"]) and 1 or 0)
        if m2.peek(ix + sym["ES_DIE"]):
            still = still and (w(m2, ix + sym["ES_X"]), w(m2, ix + sym["ES_Y"])) == (x0, y0)
        elif gone is None:
            gone = g
    check("her rounds bring it down, and it goes down where it stands",
          down and still, f"{shots} releases, ES_X/ES_Y unchanged while it flashes")
    check("... flashing, and then it is gone and its record taken",
          0 < sum(drawn) < len(drawn) and gone is not None
          and m2.peek(rec + 5) & EF_TAKEN and not drawn[-1],
          f"drawn on {sum(drawn)} of 60 frames, gone after {gone}")


# =====================================================================
# 4. EVERY LEVEL WITH A SENTRY IN IT, WITH THE SENTRIES ON
# =====================================================================
def wrong_but_it(m, tiles):
    """F.wrong_cells, less the tiles round the enemy's drawn box - the
    one thing on the playfield at a sync that is not the map."""
    bad = REAL_WRONG(m, sym, tiles)
    if not m.peek(sym["ENEMY_DREW"]):
        return bad
    x0 = w(m, sym["ENEMY_DREW_WX"])
    x1 = x0 + m.peek(sym["ENEMY_DREW_W"])
    y0 = w(m, sym["ENEMY_DREW_WY"])
    y1 = y0 + m.peek(sym["ENEMY_DREW_H"])
    return [b for b in bad if not (x0 // 4 - 1 <= b[0] <= (x1 - 1) // 4 + 1
                                   and y0 // 16 - 1 <= b[1] <= (y1 - 1) // 16 + 1)]


class Arrived(Exception):
    pass


GFRAME = F.gframe


def station():
    print("\nTHE STATION WITH ITS GUARDS AND TURRETS ON: levels 21 to 24")
    import test_station as S

    def counted(m, sym_, t, excuse="her"):
        return wrong_but_it(m, t)
    F.wrong_cells = counted
    try:
        m, _ = F.to_level(sym, 21)
        hook(m)
        tog = []
        for n in range(21, 25):
            log = {"hp": 100}
            f0, t0 = draws(m), toggles(m)
            frames, wrong = S.drive(m, n, log)
            check(f"level {n}: through it with the sentries shooting, and "
                  f"every cell the map's on every game frame",
                  m.peek(sym["GAME_STATE"]) == GS_CLEAR and wrong == 0,
                  f"{frames} game frames, HP at least {log['hp']}, {wrong} "
                  f"frames with a wrong cell outside a sentry's box; "
                  f"{draws(m) - f0} fresh draws, {toggles(m) - t0} toggles")
            tog.append(toggles(m) - t0)
            if n < 24:
                m.poke(sym["PLAYER_HP"], 100)
                for f in range(600):
                    m.run_frames(1)
                    if (m.peek(sym["GAME_STATE"]) == GS_PLAY
                            and m.peek(sym["LEVEL_CUR"]) == n and m.peek(sym["LEVEL_OK"])):
                        break
                m.run_frames(10)
        check("... and a guard fired on the screen, so its recoil was toggled "
              "in among the lasers", sum(tog) > 0, f"toggles by level: {tog}")
        # STANDING IN A GUARD'S SIGHT BETWEEN TWO LASERS, where its shots
        # and its toggles meet the laser's cels for as long as she stays:
        # the picture against the engine as it was before the recoil was
        # drawn (EN_STILL's toggle answered "nothing to draw"). They must
        # be the SAME frames, because what is wrong there is not the
        # toggle: a guard's ROUND crossing a beam has the painter put a
        # new cel under it, and the round's erase puts the old one back
        # (CLAUDE.md 8.27) - with its fire held off, it is 0.
        def spot(old):
            mm, _ = F.to_level(sym, 23)

            def gf(m_, s_, joy):
                GFRAME(m_, s_, joy)
                m_.poke(sym["PLAYER_HP"], 100)
                if w(m_, sym["KARA_WX"]) >= 188 and not m_.peek(sym["HAZARD_IN"]):
                    raise Arrived()
            F.gframe = gf
            try:
                S.drive(mm, 23, {"hp": 100})
            except Arrived:
                pass
            finally:
                F.gframe = GFRAME
            hook(mm)
            if old:
                j = next(a for a in range(sym["EN_STILL"], sym["EN_DRAW_C"])
                         if mm.peek(a) == 0xE1 and mm.peek(a + 1) == 0xC3
                         and w(mm, a + 2) == sym["ENEMY_KEEP"])
                mm.poke(j, 0x37)                # scf
                mm.poke(j + 1, 0xC9)            # ret
            bad = []
            for g in range(400):
                F.gframe(mm, sym, 0)
                mm.poke(sym["PLAYER_HP"], 100)
                bad.append(sorted(set(wrong_but_it(mm, S.TILES))))
            n, _ = F.stand_count(mm, sym, pattern=lambda g: (
                mm.poke(sym["PLAYER_HP"], 100), 0)[1])
            return bad, toggles(mm), n
        now, t_now, n_now = spot(False)
        was, t_was, n_was = spot(True)
        check("level 23, in a guard's sight between two lasers: its toggles "
              "leave the picture exactly as the engine without them, and the lock",
              t_now > 0 and t_was == 0 and now == was and n_now == 100,
              f"{t_now} toggles; {sum(1 for b in now if b)} frames with a stale "
              f"cell against {sum(1 for b in was if b)} without them, the same "
              f"frames: {now == was}; {n_now} of 200")
        # THE CONTROL: the cells off the screen kept at the door, as they
        # were before the sentries came - a laser off the screen is six
        # cells on the list and a tick of twice the time
        m, _ = F.to_level(sym, 23)
        m.poke(sym["HZ_OFF_ADD"], 255)
        frames, wrong = S.drive(m, 23, {"hp": 100})
        check("... and with HZ_PEND_ADD keeping the cells off the screen, "
              "level 23 shows a beam a cel behind", wrong > 0, f"{wrong} frames")
    finally:
        F.wrong_cells = REAL_WRONG


def walk_both(n, upto, tiles):
    """Level n walked RIGHT to tile `upto` the way test_forest7.py walks
    it - UP only when she is stuck - twice: with its sentry, and with
    the enemies held off (F.QUIET), which is the walk that suite asserts.
    Her health is topped up so that the walk is the same walk. Returns
    {quiet: (frames with a wrong cell, compiled draws, ever drawn, m)}."""
    out = {}
    for quiet in (False, True):
        m, _ = F.to_level(sym, n)
        F.QUIET = quiet
        hook(m)
        seen = [False]

        def stop(m_):
            m_.poke(sym["PLAYER_HP"], 100)
            seen[0] = seen[0] or bool(m_.peek(sym["ENEMY_DREW"]))
            return False
        F.wrong_cells = lambda m_, s_, t, excuse="her": wrong_but_it(m_, t)
        try:
            _, wrong = F.walk(m, sym, upto, tiles, stop=stop)
        finally:
            F.wrong_cells = REAL_WRONG
            F.QUIET = False
        out[quiet] = (len(wrong), draws(m), seen[0], m)
    return out


def others():
    print("\nTHE FOREST'S SNIPERS AND THE CITY'S AGENT")
    ftiles = open(os.path.join(LEV, "level2_forest", "foresttiles.bin"), "rb").read()
    for n, upto in ((8, 52),):          # the sniper at 56, ahead of her
        r = walk_both(n, upto, ftiles)
        (won, d, seen, m), (woff, _, _, _) = r[False], r[True]
        check(f"level {n}: the sniper is drawn compiled, and every cell but "
              f"its own is the map's, as on the walk without it",
              seen and d >= 1 and won == 0 and woff == 0,
              f"{d} compiled draw(s); {won} frames with a wrong cell, {woff} "
              f"with the enemies held off")
        sync(m, sym, 0)
        n_, _ = F.stand_count(m, sym)
        check(f"... and standing in its sight, the lock", n_ == 100,
              f"{n_} of 200, drawn {m.peek(sym['ENEMY_DREW'])}")
    import make_city_map as city
    import test_city3 as c3
    names = city.tile_names()[1]
    names = names + [f"baked_{i}" for i in range(256 - len(names))]
    c = c3.City3(sym, names, drones=True, level=4)
    agents = [r for r in records(4) if r[0] == EK_ENEMY and r[6] == 0]
    check("level 4 places the City's agent on the key's roof",
          len(agents) == 1 and c.spawned == 3,
          f"at tile {(agents[0][1] | agents[0][2] << 8) // 8}, {c.spawned} enemies")
    m = c.m
    hook(m)
    # THE AGENT ALONE: the street drone ENGAGES while the view is walked
    # to the key's roof, and an engaged drone holds the pick until it is
    # dead (8.7) - which is the drive under fire's, in test_city4.py. So
    # the agent's slot is copied to the first and the table cut to one.
    es, live = sym["ES_STRIDE"], m.peek(sym["ENEMY_LIVE"])
    slots = [sym["ENEMIES"] + i * es for i in range(live)]
    agent = next(a for a in slots
                 if m.peek(a + sym["ES_TYPE"]) == 0)
    m.write_ram(slots[0], bytes(m.peek(agent + i) for i in range(es)))
    m.poke(sym["ENEMY_LIVE"], 1)
    # straight onto the key's roof, at its lip: the agent is ahead of her
    c.put(91 * 4 + 2, 8 * 16)
    seen, n0 = False, draws(m)
    for g in range(200):                # on towards it until it is drawn
        F.gframe(m, sym, 0 if seen else JOY_RIGHT)
        m.poke(sym["PLAYER_HP"], 100)
        seen = seen or bool(m.peek(sym["ENEMY_DREW"])
                            and m.peek(w(m, sym["ENEMY_TYP"]) + sym["EN_T_KIND"]) & 8)
    check("... and on her roof it is drawn compiled",
          seen and draws(m) - n0 >= 1, f"{draws(m) - n0} compiled draw(s)")
    n_, _ = F.stand_count(m, sym)
    check("... and the lock beside it", n_ == 100, f"{n_} of 200")


# =====================================================================
# 5. THE LOCK, ON THE DESERT
# =====================================================================
def lock():
    print("\nTHE LOCK, a mercenary on the screen: game frames in 200")
    m, _ = F.to_level(sym, 17)
    for g in range(400):
        F.gframe(m, sym, JOY_RIGHT)
        m.poke(sym["PLAYER_HP"], 100)
        if m.peek(sym["ENEMY_DREW"]):
            break
    ix = w(m, sym["ENEMY_CUR"])

    def alive(joy):                     # her rounds must not take it away
        m.poke(ix + sym["ES_HP"], 3)
        return joy
    for name, pat in (("standing in its sight", None),
                      ("firing at it", lambda g: alive(JOY_FIRE if g % 6 < 2 else 0)),
                      ("walking past it, so that it turns",
                       lambda g: alive(JOY_RIGHT | (JOY_UP if g % 12 == 0 else 0)))):
        n, _ = F.stand_count(m, sym, pattern=pat)
        check(f"{name}: 100", n == 100,
              f"{n}, drawn {m.peek(sym['ENEMY_DREW'])}")


def main():
    print("The sentries (CLAUDE.md 8.27)")
    compiled()
    rule()
    merc()
    lock()
    others()
    station()
    print()
    print("ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILED: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
