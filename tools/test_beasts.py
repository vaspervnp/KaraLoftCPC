#!/usr/bin/env python3
"""The enemies that BITE (CLAUDE.md 8.24): the forest's wolf and boar on
levels 5 and 6, and the cave's bats on levels 9 to 12.

They are the engaged drone of 8.7 with two bits of its type row changed
(src/melee.asm): EN_MELEE, which turns its shot into a CHARGE to her
side and a bite when its box reaches hers, and EN_GROUND, which keeps a
beast on the line it was placed on. What is checked here, on a 6128:

  * the type rows, against the editor's enum;
  * the wolf: it engages, keeps to its ground, sees her on it and not
    from a branch, charges to a byte short of her and never overlaps
    her, bites for its row's points once a charge, plays its attack
    cels, and dies to her rounds - with the three bits that make it a
    beast each knocked out as a control;
  * the boar's bite, which is twice the wolf's;
  * the bat: it engages as she climbs, keeps to her chest, bites, and
    one round brings it down, after which the next one in the table is
    the one that comes;
  * and the lock with each of them following her.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_forest7 as F                                        # noqa: E402
from bench import sync                                          # noqa: E402
import test_cave as C                                           # noqa: E402

ROOT = os.path.join(HERE, "..")
JOY_UP, JOY_DOWN, JOY_LEFT, JOY_RIGHT, JOY_FIRE = 0x01, 0x02, 0x04, 0x08, 0x10

fails = []
sym = F.symbols()


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        fails.append(name)


def w(m, a):
    return m.peek(a) | m.peek(a + 1) << 8


def es(m, ix, field):
    return m.peek(ix + sym[field])


def es_w(m, ix, field):
    return w(m, ix + sym[field])


def engaged(m):
    return w(m, sym["ENEMY_ENG"])


def row_of(kind):
    return sym["ENEMY_TYPES"] + kind * sym["EN_T_STRIDE"]


def sample(m):
    """The one following her and her, at the top of a game frame."""
    ix = engaged(m)
    if not ix:
        return None
    t = es(m, ix, "ES_TYPE")
    width = m.peek(row_of(t) + sym["EN_T_W"])
    ex = es_w(m, ix, "ES_X") // 2
    # HER SPRITE'S box and not her body's: it is the box ENEMY_SLOT
    # tests the refresh against, and two that meet are a refresh at the
    # end of the second sweep (src/melee.asm)
    art = (sym["KARA_W_BYTES"] - sym["KARA_BOX_W"]) // 2
    hx = w(m, sym["KARA_WX"]) - art
    hw = sym["KARA_W_BYTES"]
    if ex >= hx:
        gap = ex - (hx + hw)
    else:
        gap = hx - (ex + width)
    return dict(ix=ix, type=t, x=ex, y=es_w(m, ix, "ES_Y"), hp=es(m, ix, "ES_HP"),
                charge=es(m, ix, "ES_CHARGE"), cel=es(m, ix, "ES_CEL"),
                gap=gap, early=m.peek(sym["ENEMY_EARLY"]),
                her_y=w(m, sym["KARA_WY"]), drew=m.peek(sym["ENEMY_DREW"]))


def stand(m, frames, joy=0, top_up=True):
    """`frames` game frames with `joy` held: every sample, and every bite
    as the points it cost - her health topped back up after each, so
    that she lives through it."""
    log, bites = [], []
    for _ in range(frames):
        F.gframe(m, sym, joy)
        hp = m.peek(sym["PLAYER_HP"])
        if hp < 100:
            bites.append(100 - hp)
            if top_up:
                m.poke(sym["PLAYER_HP"], 100)
        log.append(sample(m))
    m.joystick(0)
    return log, bites


def shoot(m, side):
    """One round toward `side` (0 right, 1 left): the trigger drawn with
    the direction held, which turns her and plants her (8.4), and let go.
    """
    d = JOY_RIGHT if side == 0 else JOY_LEFT
    F.gframe(m, sym, JOY_FIRE | d)
    F.gframe(m, sym, JOY_FIRE | d)
    F.gframe(m, sym, 0)
    for _ in range(5):
        F.gframe(m, sym, 0)
        if m.peek(sym["PLAYER_HP"]) < 100:
            m.poke(sym["PLAYER_HP"], 100)


def kill(m, limit=24):
    """Releases of the trigger into the one following her until it is
    down, and its hit points then. A release is TWO rounds: the shoot
    cels carry both pistols (8.5)."""
    ix = engaged(m)
    n = 0
    while ix and es(m, ix, "ES_HP") and n < limit:
        side = m.peek(sym["ENEMY_SIDE"])
        shoot(m, side)
        n += 1
    return n, (es(m, ix, "ES_HP") if ix else None)


def to_wolf():
    m, _ = F.to_level(sym, 5)
    F.walk(m, sym, 34)
    m.poke(sym["PLAYER_HP"], 100)
    for _ in range(10):
        F.gframe(m, sym, 0)
    return m


# =====================================================================
# 1. THE ROWS
# =====================================================================
def rows():
    print("\nTHE ROWS: three characters that bite")
    m, _ = F.to_level(sym, 5)
    got = {}
    for name in ("EN_BAT", "EN_WOLF", "EN_BOAR", "EN_DRONE", "EN_SEADRONE"):
        r = row_of(sym[name])
        got[name] = (m.peek(r + sym["EN_T_KIND"]), m.peek(r + sym["EN_T_BITE"]))
    want = {"EN_BAT": (sym["EN_MELEE"], 8),
            "EN_WOLF": (sym["EN_MELEE"] | sym["EN_GROUND"], 8),
            "EN_BOAR": (sym["EN_MELEE"] | sym["EN_GROUND"], 16),
            "EN_DRONE": (0, 0), "EN_SEADRONE": (0, 0)}
    check("the bat bites, the wolf and the boar bite on the ground, and "
          "the two drones are kind 0 as they were", got == want, f"{got}")
    cs = open(os.path.join(ROOT, "editor", "src", "CpcLevelEditor.Domain",
                           "EnemyKind.cs")).read()
    enum = dict((k, int(v)) for k, v in re.findall(r"(\w+) = (\d+),", cs))
    check("the editor's EnemyKind has them at the engine's numbers",
          enum.get("Bat") == sym["EN_BAT"] and enum.get("Wolf") == sym["EN_WOLF"]
          and enum.get("Boar") == sym["EN_BOAR"]
          and len(enum) == sym["EN_KINDS"],
          f"{enum} against EN_KINDS {sym['EN_KINDS']}")


# =====================================================================
# 2. THE WOLF
# =====================================================================
def wolf():
    print("\nTHE WOLF: level 5, on the grass before the mountain")
    m = to_wolf()
    log, bites = stand(m, 200)
    s = [x for x in log if x]
    check("it is the one following her, drawn on every game frame",
          len(s) == 200 and all(x["type"] == sym["EN_WOLF"] and x["drew"] for x in s),
          f"{len(s)} of 200 frames, types {sorted({x['type'] for x in s})}")
    ys = {x["y"] for x in s}
    check("... and it keeps to its ground: its top never leaves the line",
          ys == {120}, f"ES_Y {sorted(ys)} - the ground row's surface, 144, "
          f"less its 24 lines")
    check("it bites for its row's 8 points, once a charge",
          len(bites) >= 4 and set(bites) == {8},
          f"{len(bites)} bites in 200 game frames: {bites}")
    gaps = [x["gap"] for x in s]
    check("... and the charge stops short of her: its box never meets her "
          "SPRITE's", min(gaps) >= 1, f"the gap between them {min(gaps)} to "
          f"{max(gaps)} bytes - EN_AIR {sym['EN_AIR']} at the end of a charge, "
          f"EN_REACH {sym['EN_REACH']} across it to her body")
    early = sum(1 for x in s if x["early"] != 1)
    check("... so it is redrawn at the top of the second sweep on every frame",
          early == 0, f"{early} frames refreshed anywhere else")
    attack = sym["FORESTWOLF_ATTACK_FIRST"]
    cels = {x["cel"] for x in s if x["charge"]}
    check("a charge plays the attack cels",
          any(attack <= c < attack + 2 for c in cels),
          f"cels while charging {sorted(cels)}, attack {attack}..{attack + 1}")

    # ---- the controls: each bit that makes it a beast, knocked out
    m = to_wolf()
    m.poke(sym["EN_BITE_STEP"], 0xC9)
    _, b2 = stand(m, 200)
    check("... with EN_BITE_STEP poked to RET it charges and never bites",
          not b2, f"{len(b2)} bites")
    m = to_wolf()
    # EN_SIGHT_Y as it was: its own TOP. `ld a,(ix + ES_Y) : ret`
    m.write_ram(sym["EN_SIGHT_Y"], bytes([0xDD, 0x7E, sym["ES_Y"], 0xC9]))
    l3, b3 = stand(m, 200)
    check("... with its sight comparing its TOP with hers, it never sees "
          "her on its own ground and never charges",
          not b3 and not any(x and x["charge"] for x in l3),
          f"{len(b3)} bites, {sum(1 for x in l3 if x and x['charge'])} frames "
          f"charging - a 24-line wolf's top is EN_H_SIGHT below a 64-line "
          f"heroine's")
    m = to_wolf()
    k = row_of(sym["EN_WOLF"]) + sym["EN_T_KIND"]
    m.poke(k, sym["EN_MELEE"])
    l4, _ = stand(m, 60)
    y4 = sorted({x["y"] for x in l4 if x})
    check("... and with EN_GROUND off it climbs to her chest like a drone",
          y4[0] < 120, f"ES_Y {y4[0]}..{y4[-1]}, her top "
          f"{l4[-1]['her_y'] if l4[-1] else '?'} + EN_DY")

    # ---- from a branch she is out of its reach and its sight
    m, _ = F.to_level(sym, 5)
    F.walk(m, sym, 30)
    F.climb(m, sym, (32, 36), (35, 38), lambda mm: mm.peek(sym["KEYS_COUNT"]))
    m.poke(sym["PLAYER_HP"], 100)
    wy = w(m, sym["KARA_WY"])
    l5, b5 = stand(m, 150)
    check("on the row-5 branch it does not see her and does not bite",
          wy == 16 and not b5 and not any(x and x["charge"] for x in l5),
          f"KARA_WY {wy}, {len(b5)} bites, "
          f"{sum(1 for x in l5 if x and x['charge'])} frames charging")

    # ---- her rounds, over its back
    m = to_wolf()
    n, hp = kill(m)
    check("her rounds bring it down, fired standing over its back "
          "(EN_HIT_BAND)", hp == 0 and n <= 4,
          f"{n} releases of the trigger, ES_HP {hp}")
    m = to_wolf()
    # RET where the band is widened: its own box, as the drone's is
    m.write_ram(sym["EN_HIT_BAND"] + 12, bytes([0xC9]))
    n2, hp2 = kill(m, limit=8)
    check("... and with the band its own box, every round goes over it",
          hp2 and hp2 > 0, f"{n2} releases, ES_HP {hp2}")
    return m


# =====================================================================
# 3. THE BOAR
# =====================================================================
def boar():
    print("\nTHE BOAR: past the third pit")
    m = to_wolf()
    kill(m)
    for _ in range(40):
        F.gframe(m, sym, 0)
    F.walk(m, sym, 84)
    m.poke(sym["PLAYER_HP"], 100)
    for _ in range(10):
        F.gframe(m, sym, 0)
    log, bites = stand(m, 200)
    s = [x for x in log if x]
    check("the boar is the next one to follow her",
          s and all(x["type"] == sym["EN_BOAR"] for x in s),
          f"types {sorted({x['type'] for x in s})}")
    check("... and its bite is 16", bites and set(bites) == {16},
          f"{len(bites)} bites: {bites}")
    n, hp = kill(m)
    check("... and its three hit points come down", hp == 0 and n <= 6,
          f"{n} releases, ES_HP {hp}")
    return m


# =====================================================================
# 4. THE BATS
# =====================================================================
def bats():
    print("\nTHE BATS: level 9, up the first ladder")
    p = C.Play(sym, level=9, calm=False)
    m = p.m
    s = p.shafts(p.row() - 1)
    p.walk_to(s[0])
    p.climb_up()
    m.poke(sym["PLAYER_HP"], 100)
    for _ in range(20):
        F.gframe(m, sym, 0)
    log, bites = stand(m, 200)
    s = [x for x in log if x]
    check("the first bat is following her once she is up the ladder",
          len(s) == 200 and all(x["type"] == sym["EN_BAT"] for x in s),
          f"{len(s)} of 200 frames")
    off = {x["y"] - x["her_y"] for x in s if not x["charge"]}
    check("... at her chest", off and max(abs(o - 12) for o in off) <= 8,
          f"its top less hers {sorted(off)} - EN_DY is 12")
    check("... and it swoops and bites for 8", bites and set(bites) == {8},
          f"{len(bites)} bites in 200 game frames: {bites}")
    check("... and never meets her sprite", min(x["gap"] for x in s) >= 1,
          f"gap {min(x['gap'] for x in s)} to {max(x['gap'] for x in s)}")
    swoop = sym["CAVEBATS_SWOOP_FIRST"]
    check("... playing its swoop cels when it does",
          any(swoop <= x["cel"] < swoop + 2 for x in s if x["charge"]),
          f"cels while swooping {sorted({x['cel'] for x in s if x['charge']})}")
    first = engaged(m)
    n, hp = kill(m)
    check("one hit brings it down", hp == 0 and n <= 3,
          f"{n} releases, ES_HP {hp}")
    for _ in range(60):
        F.gframe(m, sym, 0)
    nxt = w(m, sym["ENEMY_CUR"])
    check("... and the one ENEMY_PICK has next is the second in the table",
          nxt and nxt == first + sym["ES_STRIDE"],
          f"slot {(nxt - sym['ENEMIES']) // sym['ES_STRIDE'] if nxt else None}")
    return p


# =====================================================================
# 5. THE LOCK
# =====================================================================
def count(m, pattern):
    n, _ = F.stand_count(m, sym, pattern=pattern)
    return n


def lock():
    print("\nTHE LOCK: game frames in 200 hardware frames, one following her")
    m = to_wolf()
    n = count(m, None)
    check("the wolf: standing", n == 100, f"{n}")
    m = to_wolf()
    n = count(m, lambda g: (JOY_FIRE if g % 6 < 2 else 0))
    check("... firing at it", n == 100, f"{n}")
    for pre in (0, 4, 8):
        m = to_wolf()
        for _ in range(pre):
            F.gframe(m, sym, 0)
        n = count(m, lambda g: JOY_RIGHT | (JOY_UP if g % 12 == 0 else 0))
        check(f"... walking and jumping on with it, {pre} frames in", n == 100,
              f"{n}")
    m = to_wolf()
    m.key_down('A')
    n = count(m, lambda g: JOY_RIGHT)
    m.key_up('A')
    check("... running on with it", n == 100, f"{n}")
    p = C.Play(sym, level=9, calm=False)
    s = p.shafts(p.row() - 1)
    p.walk_to(s[0])
    p.climb_up()
    for _ in range(20):
        F.gframe(p.m, sym, 0)
    n = count(p.m, None)
    check("the bat: standing", n == 100, f"{n}")
    n = count(p.m, lambda g: (JOY_FIRE if g % 6 < 2 else 0))
    check("... firing at it", n == 100, f"{n}")


def main():
    rows()
    wolf()
    boar()
    bats()
    lock()
    print()
    print("ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILED: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
