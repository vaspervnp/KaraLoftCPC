#!/usr/bin/env python3
"""Level 15 on a 6128: the patrol - the sea's drones. CLAUDE.md 8.20.

THE CITY'S DRONE, IN THE WATER. EN_SEADRONE is the fourth row of
ENEMY_TYPES and nothing about its behaviour is new: once it has been on
the screen it is ENGAGED (8.7), follows her on its own side and is
redrawn on every game frame until one of them is dead. What the water
changes is HOW FAR it keeps, and that is four immediates of the follow
patched by BOX_SET with the rest of the swimmer's box (8.18): a 32-byte
swimmer and a 16-byte drone are not a 12-byte heroine and an 8-byte
drone, and the land's 22 bytes would put it inside her.

Every expectation is read out of something other than the code under
test, and every one has a control:

    the way in     out of level 14's siphon, four slots out of the
                   level's own records, the type's hit points, and the
                   follow's four sites holding the water's values here
                   and the land's on the City
    the follow     engaged, drawn on every game frame, at the swimmer's
                   distance from her middle and level with her - and
                   with ENEMY_MOVE poked to RET it is left behind
    the kill       three of her rounds, the fall, and the next drone
                   engaged only when she reaches it
    the torpedo    EBUL_DAMAGE off her a hit while it follows - and with
                   EBUL_SPAWN poked to RET, nothing
    the reload     an empty gun tapped every eight game frames gets its
                   magazines back - and with START_RELOAD's guard taken
                   out, which is the engine as it was, it never does
    the route      from the surface to the siphon from the joystick,
                   every drone shot down on the way, a vent breathed on
                   two ledges, every on-screen cell the map's on every
                   game frame except under the drone's own drawn box
    the lock       game frames per 200 hardware frames, anchored, with a
                   drone following her
    the strip      the second sweep's strip down before row 22 with the
                   drone's refresh in front of it
"""
import os
import re
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import sync                                          # noqa: E402
from make_level import read                                     # noqa: E402
import test_sea as TS                                           # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
BUILD = os.path.join(ROOT, "build")
sym = TS.sym
U, D, L, R, FIRE = TS.U, TS.D, TS.L, TS.R, TS.FIRE
GS_PLAY, GS_DEAD, GS_CLEAR = TS.GS_PLAY, TS.GS_DEAD, TS.GS_CLEAR
LEVEL = 15
LVL = read(open(os.path.join(BUILD, f"level_{LEVEL}.lvl"), "rb").read())
EK_ENEMY = sym["EK_ENEMY"]
# THE SLOT'S LAYOUT IS READ OFF THE BUILD, not written down: it was
# 17 here, and ES_CHARGE made the stride 18 (CLAUDE.md 8.24) - and a suite
# reading every slot one byte short reported a fifth drone (CLAUDE.md 10).
ES = sym["ES_STRIDE"]
ES_X, ES_Y, ES_TYPE, ES_HP, ES_DIE = (sym[n] for n in
                                      ("ES_X", "ES_Y", "ES_TYPE", "ES_HP", "ES_DIE"))

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


W = TS.word


def drone_records():
    """(x, base y, p0, p1) of every EK_ENEMY record, out of the FILE."""
    e = LVL["entity_bytes"]
    recs = [e[i:i + 8] for i in range(0, len(e), 8)]
    return [(r[1] | r[2] << 8, r[3] | r[4] << 8, r[6], r[7]) for r in recs
            if r[0] == EK_ENEMY]


def excused_wrong(m):
    """test_sea's picture model, with the drone's own DRAWN box excused:
    it is a persistent sprite (8.7), so between its refreshes its pixels
    are on the screen at the top of the loop, where her and her rounds'
    have been lifted off. Only the box the engine says it drew is
    excused - a stray copy anywhere else is still a wrong cell."""
    bad = TS.wrong_cells(m)
    if m.peek(sym["ENEMY_DREW"]):
        dx, dw = W(m, sym["ENEMY_DREW_WX"]), m.peek(sym["ENEMY_DREW_W"])
        dy, dh = W(m, sym["ENEMY_DREW_WY"]), m.peek(sym["ENEMY_DREW_H"])
        bad = [(c, r) for c, r in bad
               if not (4 * c < dx + dw and dx < 4 * c + 4
                       and 16 * r < dy + dh and dy < 16 * r + 16)]
    return bad



class Patrol(TS.Sea):
    """The running game in level 15, logging the drone every game frame."""

    def __init__(self, before=None):
        TS.LEVEL = LEVEL
        super().__init__(before=before)
        self.log = []
        self.wrong = []
        self.shoot = False          # go() shoots back at whatever engages
        self.fought = []            # ... and how long each one took

    def eng(self):
        a = W(self.m, sym["ENEMY_ENG"])
        return None if a == 0 else (a - sym["ENEMIES"]) // ES

    def slot(self, k, f):
        a = sym["ENEMIES"] + ES * k + f
        return W(self.m, a) if f in (ES_X, ES_Y) else self.m.peek(a)

    def frame(self, joy=0, picture=False):
        TS.Sea.frame(self, joy, False)
        m = self.m
        e = self.eng()
        drew = m.peek(sym["ENEMY_DREW"])
        self.log.append(dict(
            wx=self.w("KARA_WX"), wy=self.w("KARA_WY"),
            hp=self.b("PLAYER_HP"), eng=e,
            alive=e is not None and self.slot(e, ES_HP) > 0,
            drew=drew, dx=W(m, sym["ENEMY_DREW_WX"]),
            dw=m.peek(sym["ENEMY_DREW_W"]), dy=W(m, sym["ENEMY_DREW_WY"]),
            hps=[self.slot(k, ES_HP) for k in range(4)],
            o2=self.b("OXYGEN"), rounds=self.b("MAG_LEFT") + self.b("MAG_RIGHT"),
            joy=joy))
        if picture:
            bad = excused_wrong(m)
            if bad:
                self.wrong.append((len(self.log), bad[:3]))

    def go(self, tx, ty, limit=600, picture=True):
        """test_sea's go(), and with `shoot` set it stops to shoot down
        any drone that engages her on the way - a drone engages when IT
        is ready, which is not a place on the route."""
        for _ in range(limit):
            e = self.eng()
            if self.shoot and e is not None and self.slot(e, ES_HP):
                self.fought.append((e, self.fight(picture=picture),
                                    self.w("KARA_WY")))
                continue
            x, y = self.w("KARA_WX"), self.w("KARA_WY")
            if abs(x - tx) <= 1 and abs(y - ty) <= 2:
                break
            j = 0
            if x < tx - 1:
                j |= R
            elif x > tx + 1:
                j |= L
            if y < ty - 2:
                j |= D
            elif y > ty + 2:
                j |= U
            self.frame(j, picture)
        return self.w("KARA_WX"), self.w("KARA_WY")

    def gx(self, x, picture=True):
        self.go(x, self.w("KARA_WY"), picture=picture)

    def gy(self, y, picture=True):
        self.go(self.w("KARA_WX"), y, picture=picture)

    def fight(self, limit=200, picture=True):
        """Face the drone that is following her and tap the trigger -
        draw, hold, release - until it is down. Returns the frames it
        took, or None if it never went down."""
        for i in range(limit):
            e = self.eng()
            if e is None or self.slot(e, ES_HP) == 0:
                return i
            mid = (W(self.m, sym["ENEMY_DREW_WX"])
                   + self.m.peek(sym["ENEMY_DREW_W"]) // 2)
            face = R if mid > self.w("KARA_WX") + sym["SWIM_BOX_W"] // 2 else L
            k = i % 8
            self.frame((face if k == 0 else 0) | (FIRE if 1 <= k <= 3 else 0),
                       picture)
        return None


def at_title(m, frames=400):
    """INTRO_WAIT's loop is reached on every frame the title is up - and
    spends nearly all of it in WAIT_VSYNC, which is in the core, so a PC
    sampled once a frame almost never lands in it. Stepped a few
    microseconds at a time for two frames, it cannot miss."""
    m.run_frames(frames)
    lo, hi = sym["INTRO_WAIT"], sym["INTRO_WAIT"] + 0x80
    for _ in range(2 * 19968 // 8):
        m.run_us(8)
        if lo <= m.pc < hi:
            return True
    return False


# =====================================================================
def way_in():
    print("\nTHE WAY IN: out of level 14's siphon, and the four drones")
    p = Patrol()
    m = p.m
    check("level 15 is the sea's second map after the minefield, one "
          "sector and no art",
          p.took is not None and p.took < 200 and p.b("LEVEL_OK") == 1
          and p.b("LEVEL_ENV") == 3 and p.b("LEVEL_CUR") == LEVEL - 1
          and p.b("LEVEL_SWIM") == 1,
          f"{p.took} hardware frames, LEVEL_ENV {p.b('LEVEL_ENV')}, "
          f"LEVEL_CUR {p.b('LEVEL_CUR')}, LEVEL_SWIM {p.b('LEVEL_SWIM')}")
    recs = drone_records()
    T = sym["ENEMY_TYPES"] + sym["EN_SEADRONE"] * sym["EN_T_STRIDE"]
    h, hp = m.peek(T + sym["EN_T_H"]), m.peek(T + sym["EN_T_HP"])
    ok = len(recs) == 4 and all(r[2] == sym["EN_SEADRONE"] for r in recs)
    for k, (x, y, p0, p1) in enumerate(recs):
        ok = ok and (p.slot(k, ES_TYPE) == sym["EN_SEADRONE"]
                     and p.slot(k, ES_HP) == hp
                     and p.slot(k, ES_Y) == y - h)
    check("four sea drones out of the level's own records, each with the "
          "type's hit points, on its feet", ok,
          f"{len(recs)} records, EN_SEADRONE {sym['EN_SEADRONE']}, "
          f"{hp} HP, y = base - {h}")

    # THE FOLLOW'S FOUR SITES. test_sea's box check reads every site of
    # BOX_SITES against the byte the ASSEMBLER put there; this is the
    # same four read as what they MEAN: the water's distance, its
    # negative, the nearest it may come and how far below her top.
    def site(n, wide=True):
        return W(m, sym[n]) if wide else m.peek(sym[n])
    water = {"BX_EN_DIST": sym["SWIM_EN_DIST"],
             "BX_EN_DISTN": (0 - sym["SWIM_EN_DIST"]) & 0xFFFF,
             "BX_EN_MIN": sym["SWIM_EN_MIN"], "BX_EN_DY": sym["SWIM_EN_DY"]}
    got = {n: site(n) for n in water}
    check("the follow's four immediates hold the water's distances",
          got == water, f"{got}")
    land = TS.boot(sym, scroll=True)
    lgot = {n: W(land, sym[n]) for n in water}
    lwant = {"BX_EN_DIST": sym["EN_DIST"],
             "BX_EN_DISTN": (0 - sym["EN_DIST"]) & 0xFFFF,
             "BX_EN_MIN": sym["EN_MIN"], "BX_EN_DY": sym["EN_DY"]}
    check("... and on the City, the land's", lgot == lwant, f"{lgot}")
    return p


def follow():
    print("\nTHE FOLLOW: engaged, drawn on every game frame, at the "
          "swimmer's distance")
    p = Patrol()
    p.gx(16, picture=False)
    p.gy(100, picture=False)                # into the first one's sight
    n0 = len(p.log)
    for _ in range(40):
        p.frame(0)
    p.gy(300, picture=False)                # and down, 200 lines, with it
    seg = [r for r in p.log[n0:] if r["eng"] is not None and r["alive"]]
    drawn = sum(1 for r in seg if r["drew"])
    half = sym["SWIM_BOX_W"] // 2
    dist = [abs(r["dx"] + r["dw"] // 2 - (r["wx"] + half)) for r in seg]
    dys = [r["dy"] - r["wy"] for r in seg]
    lo = sym["SWIM_EN_MIN"]
    hi = sym["SWIM_EN_DIST"] + sym["EN_SWAY"] // 2 + sym["EN_CHASE"]
    check("the first drone is engaged and drawn on every game frame of it",
          seg and drawn == len(seg),
          f"{drawn} of {len(seg)} game frames, {len(p.log) - n0} logged")
    check("... between the nearest it may come and the swimmer's distance "
          "and its sway, from her middle",
          dist and lo <= min(dist) and max(dist) <= hi,
          f"{min(dist) if dist else '-'}..{max(dist) if dist else '-'} bytes, "
          f"typically {sorted(dist)[len(dist) // 2] if dist else '-'}, "
          f"against {lo}..{hi}")
    check("... and level with her while she swims 200 lines down",
          dys and max(abs(d) for d in dys) <= 12,
          f"its top minus hers {min(dys) if dys else '-'}..{max(dys) if dys else '-'} "
          f"lines, SWIM_EN_DY {sym['SWIM_EN_DY']}")

    q = Patrol(before=lambda m: m.poke(sym["ENEMY_MOVE"], 0xC9))
    q.gx(16, picture=False)
    q.gy(100, picture=False)
    n0 = len(q.log)
    q.gy(300, picture=False)
    left = sum(1 for r in q.log[n0:]
               if r["eng"] is None or not r["drew"]
               or abs(r["dy"] - r["wy"]) > 24)
    check("... and with ENEMY_MOVE poked to RET she leaves it behind",
          left > len(q.log[n0:]) // 2,
          f"{left} of {len(q.log) - n0} game frames with it not beside her - "
          f"so it is the follow that keeps it there")
    return p


def kill(p):
    print("\nTHE KILL: three of her rounds, the fall, and the next")
    e = p.eng()
    hp0 = p.slot(e, ES_HP) if e is not None else None
    hits = []
    was = hp0
    for i in range(200):
        e2 = p.eng()
        if e2 != e or p.slot(e, ES_HP) == 0:
            break
        mid = W(p.m, sym["ENEMY_DREW_WX"]) + p.m.peek(sym["ENEMY_DREW_W"]) // 2
        face = R if mid > p.w("KARA_WX") + 8 else L
        k = i % 8
        p.frame((face if k == 0 else 0) | (FIRE if 1 <= k <= 3 else 0))
        now = p.slot(e, ES_HP)
        if now != was:
            hits.append(was - now)
            was = now
    check("it goes down to three of her rounds, one hit point each",
          hp0 == 3 and hits == [1, 1, 1] and p.slot(e, ES_HP) == 0,
          f"{hp0} HP, hits {hits}, in {i} game frames")
    die = p.slot(e, ES_DIE)
    y0 = p.slot(e, ES_Y)
    for _ in range(4):
        p.frame(0)
    check("... and falls, dying", die > 0 and p.slot(e, ES_Y) > y0,
          f"ES_DIE {die}, ES_Y {y0} -> {p.slot(e, ES_Y)}")
    for _ in range(sym["EN_DIE_FRAMES"] + 4):
        p.frame(0)
    check("... and is gone, and nobody follows her until she reaches the "
          "next", p.eng() is None and not p.b("ENEMY_DREW"),
          f"ENEMY_ENG {p.eng()}, ENEMY_DREW {p.b('ENEMY_DREW')}")
    p.gy(340, picture=False)
    check("the next one engages when she reaches it, in table order",
          p.eng() == 1, f"ENEMY_ENG slot {p.eng()} at WY {p.w('KARA_WY')}")


def torpedo():
    print("\nTHE TORPEDO: EBUL_DAMAGE a hit while it follows")

    def run(before=None):
        p = Patrol(before=before)
        p.gx(16, picture=False)
        p.gy(100, picture=False)
        hp0 = p.b("PLAYER_HP")
        for _ in range(160):
            p.frame(0)
        drops = [a["hp"] - b["hp"] for a, b in zip(p.log, p.log[1:])
                 if b["hp"] < a["hp"]]
        return hp0, p.b("PLAYER_HP"), drops
    hp0, hp1, drops = run()
    check("treading water beside it, its rounds land, EBUL_DAMAGE each",
          drops and all(d == sym["EBUL_DAMAGE"] for d in drops),
          f"HP {hp0} -> {hp1} in 160 game frames, hits {drops}")
    c0, c1, cd = run(lambda m: m.poke(sym["EBUL_SPAWN"], 0xC9))
    check("... and with EBUL_SPAWN poked to RET, nothing touches her",
          c1 == c0 and not cd, f"HP {c0} -> {c1}")


def reload():
    print("\nTHE RELOAD: an empty gun, tapped")

    def run(before=None):
        p = Patrol(before=before)
        p.m.poke(sym["MAG_LEFT"], 0)
        p.m.poke(sym["MAG_RIGHT"], 0)
        res = p.b("AMMO_RESERVE")
        back = None
        for i in range(150):
            p.frame(FIRE if 1 <= i % 8 <= 3 else 0)
            if back is None and p.b("MAG_LEFT") + p.b("MAG_RIGHT"):
                back = i
        return res, back, p.b("MAG_LEFT") + p.b("MAG_RIGHT")
    res, back, n = run()
    check("tapping the trigger every eight game frames, the magazines come "
          "back after RELOAD_FRAMES",
          back is not None and back <= sym["RELOAD_FRAMES"] + 8 and n > 0,
          f"reserve {res}, back on game frame {back}, {n} rounds")
    # THE ENGINE AS IT WAS: START_RELOAD's guard is `ld a,(RELOAD_TIMER)
    # : or a : ret nz`, and the RET NZ is its fifth byte. NOPed, every
    # dry release starts the count again.
    guard = sym["START_RELOAD"] + 4
    res, back, n = run(lambda m: m.poke(guard, 0x00))
    check("... and with the guard taken out - the engine as it was - they "
          "never do", back is None and n == 0,
          f"{n} rounds after 150 game frames of tapping - every dry "
          f"release restarted the count")


def route(p):
    """From the surface to the siphon, shooting down every drone when it
    engages her. The heights are the level's own: under a ledge is its
    row and the one under it, cleared by her 24 lines; a vent's region
    is two rows over the ledge it stands on."""
    p.shoot = True
    p.gx(16)
    p.gy(340)                               # through ledge 18's gap
    p.gx(60)
    p.gy(440)                               # onto ledge 30 ...
    p.gx(28)                                # ... and its vent
    for _ in range(25):
        p.frame(0, True)
    p.gx(92)
    p.gy(636)                               # through ledge 30's gap, onto 42
    p.gx(96)                                # ... and its vent
    for _ in range(25):
        p.frame(0, True)
    p.gx(16)
    p.gy(966)                               # through 42's gap: medkit, key
    p.gx(44)                                # the tank
    p.gy(880)                               # over the ruins
    p.gx(86)
    p.gy(966)                               # the siphon
    p.shoot = False


def the_route():
    print("\nTHE ROUTE: down past four drones, from the joystick")
    p = Patrol()
    route(p)
    o2 = [r["o2"] for r in p.log]
    check("every drone is shot down where it engages her, in table order",
          [f[0] for f in p.fought] == [0, 1, 2, 3]
          and all(f[1] is not None for f in p.fought)
          and all(p.slot(k, ES_HP) == 0 for k in range(4)),
          f"(slot, game frames, her WY): {p.fought}")
    eng = [r for r in p.log if r["eng"] is not None and r["alive"]]
    check("... and every game frame one was following her, it was drawn",
          eng and all(r["drew"] for r in eng),
          f"{sum(1 for r in eng if r['drew'])} of {len(eng)}")
    check("she reaches the siphon with the key, alive",
          p.b("KEYS_COUNT") == 1 and p.b("PLAYER_HP") > 0
          and p.b("GAME_STATE") == GS_PLAY,
          f"WX {p.w('KARA_WX')} WY {p.w('KARA_WY')}, HP {p.b('PLAYER_HP')} "
          f"at least {min(r['hp'] for r in p.log)}, air at least {min(o2)}, "
          f"{len(p.log)} game frames")
    check("every on-screen cell is the map's on every game frame of it, "
          "but the drone's own box",
          not p.wrong, f"{len(p.wrong)} frames: {p.wrong[:3]}")
    p.frame(U)
    p.frame(0)
    check("UP at the siphon opens the way out",
          p.b("GAME_STATE") == GS_CLEAR)
    took = None
    for f in range(400):
        p.m.run_frames(1)
        if p.b("GAME_STATE") == GS_PLAY and p.b("LEVEL_CUR") == LEVEL:
            took = f + 1
            break
    check("... and it leads to level 16, the siphon, inside one "
          "environment", took is not None and p.b("LEVEL_ENV") == 3
          and took < 100,
          f"{took} hardware frames - one sector, no art - LEVEL_ENV "
          f"{p.b('LEVEL_ENV')}, LEVEL_CUR {p.b('LEVEL_CUR')}")


def lock():
    print("\nTHE LOCK: game frames in 200 hardware frames, a drone with her")
    p = Patrol()
    p.gx(16, picture=False)
    p.gy(100, picture=False)

    def count(joy, tap=False):
        sync(p.m, sym, 0)
        f0 = p.b("FRAME_COUNT")
        for i in range(100):                # game frames, on the game's clock
            j = joy | (FIRE if tap and i % 6 < 2 else 0)
            p.m.joystick(j)
            p.m.run_frames(2)
        p.m.joystick(0)
        return (p.b("FRAME_COUNT") - f0) % 256
    def with_her():
        e = p.eng()
        return e is not None and p.slot(e, ES_HP) > 0
    got, there = {}, []
    for name, joy, tap in (("treading water, it following", 0, False),
                           ("swimming down, it following", D, False),
                           ("firing at it", 0, True)):
        there.append(with_her())
        got[name] = count(joy, tap)
    for k, v in got.items():
        check(f"{k}: 100", v == 100, f"{v}")
    check("... and a live drone was following her at the start of each",
          all(there), f"{there}, and at the end slot {p.eng()} with "
          f"{p.slot(p.eng(), ES_HP) if p.eng() is not None else '-'} HP")


def strip():
    print("\nTHE STRIP: down before row 22 with the drone's refresh in "
          "front of it")
    p = Patrol()
    p.gx(16, picture=False)
    p.gy(90, picture=False)
    m = p.m
    a0, a1 = sym["ENEMY_SLOT"], sym["ENEMY_THINK"]
    rows = []
    for joy, n in ((0, 20), (D, 120)):
        for _ in range(n):
            m.joystick(joy)
            sync(m, sym, 1)
            cr0 = m.peek(sym["WORLD_CR"])
            while m.pc != a0:
                m.run_us(1)
            t = 0
            while m.pc != a1 and t < 40000:
                m.run_us(1)
                t += 1
            rows.append((t * 4, m.peek(sym["WORLD_CR"]) != cr0,
                         m.peek(sym["ENEMY_EARLY"]),
                         W(m, sym["ENEMY_ENG"]) != 0))
    m.joystick(0)
    worst = max(r[0] for r in rows)
    steps = [r[0] for r in rows if r[1]]
    early = [r[0] for r in rows if r[2] and r[3]]
    check("the second sweep's strip is down before row 22 on every game "
          "frame, the drone's refresh and the row steps among them",
          worst < 63488 and steps and early,
          f"worst {worst} T of 63,488 over {len(rows)} game frames; "
          f"{len(steps)} row steps, worst {max(steps) if steps else '-'}; "
          f"{len(early)} with the refresh at the top of the sweep")


def main():
    way_in()
    p = follow()
    kill(p)
    torpedo()
    reload()
    the_route()
    lock()
    strip()
    print()
    if fails:
        print(f"{len(fails)} CHECK(S) FAILED")
        for f in fails:
            print("  -", f)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
