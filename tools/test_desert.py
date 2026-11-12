#!/usr/bin/env python3
"""Levels 17 to 20 on a 6128: the desert - its quicksand, its NPCs who
sell the code to the next door, and the shuttle at the end of it.
CLAUDE.md 8.22.

QUICKSAND IS A TILE THAT HOLDS HER. The format's Quicksand bit (32) is
TA_SINK, and src/player.asm's SINK_STEP is the first thing that has ever
read it: standing in it she is held, and let down a line on every other
game frame; past 28 lines her jump cannot lift her over the lip, and
when the sand reaches her chest it has her. Every number here is
measured off her own KARA_WY, and each half has its control - the same
pit with LEVEL_SINK cleared is a hole she falls to the bottom of and
cannot leave.

AN NPC IS A RECORD THAT TAKES COINS AND GIVES A KEY (TALK_NPC_COIN):
what he sells is the code to the next door. The NPCs and the shuttle
are composites, baked by tools/make_desert_map.py - checked here pixel
for pixel against the artist's own sheets - and the route is driven from
the joystick through all four levels with every on-screen character cell
checked against the map on every game frame.
"""
import json
import os
import re
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import symbols, sync                                # noqa: E402
from make_level import read                                    # noqa: E402
import test_forest7 as F                                       # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BUILD = os.path.join(ROOT, "build")
ART = os.path.join(ROOT, "assets", "sprites", "level5_desert")
EDITOR = os.path.join(ROOT, "editor", "src", "CpcLevelEditor.Domain")

JOY_UP, JOY_RIGHT = 0x01, 0x08
GS_PLAY, GS_DEAD, GS_CLEAR = 0, 1, 2
EK_NPC, EK_PICKUP, EK_DOOR = 3, 4, 6
EF_TAKEN = 2
MAP_W, ROW_GROUND = 128, 9
STAND_WY = ROW_GROUND * 16 - 64         # her box's top, standing on sand
FIRST, LAST = 17, 20

sym = symbols()
TILES = open(os.path.join(BUILD, "levels", "level5_desert",
                          "deserttiles.bin"), "rb").read()
fails = []
check = F.check
F.fails = fails


def lvl(n):
    return read(open(os.path.join(BUILD, f"level_{n}.lvl"), "rb").read())


def recs(n):
    e = lvl(n)["entity_bytes"]
    return [e[i:i + 8] for i in range(0, len(e), 8)]


def names():
    man = json.load(open(os.path.join(ART, "manifest.json")))
    s = next(s for s in man["sheets"] if s["name"] == "desert_tiles")
    return {n: i for i, n in enumerate(s["tile_names"])}


T = names()
QS = T["quicksand"]


def w(m, a):
    return F.word(m, sym[a])


def b(m, a):
    return m.peek(sym[a])


def cell(m, x, r):
    return m.peek(sym["MAP_ADDR"] + r * MAP_W + x)


def put(m, wx, wy):
    """Her box at (wx bytes, wy lines), on her feet, nothing moving."""
    m.poke(sym["KARA_WX"], wx & 255)
    m.poke(sym["KARA_WX"] + 1, wx >> 8)
    m.poke(sym["KARA_WY"], wy & 255)
    m.poke(sym["KARA_WY"] + 1, wy >> 8)
    for a in ("KARA_VY", "KARA_FELL", "KARA_COYOTE"):
        m.poke(sym[a], 0)
    m.poke(sym["KARA_GROUND"], 1)


def in_sand(m):
    return cell(m, (w(m, "KARA_WX") + 3) // 4, ROW_GROUND) == QS


# =====================================================================
# 1. THE BAKE AND THE FLAGS - before any machine
# =====================================================================
def offline():
    print("\nTHE BAKE AND THE FLAGS, out of the artist's own sheets")
    import cpclib
    from PIL import Image
    from aseprite2spans import game_palette
    pal = game_palette(os.path.join(ROOT, "src", "palette.asm"))

    def sheet(stem):
        img = Image.open(os.path.join(ART, stem + ".png")).convert("RGBA")
        fr = json.load(open(os.path.join(ART, stem + ".json")))["frames"]
        fr = fr if isinstance(fr, list) else list(fr.values())
        return img, [f["frame"] for f in fr]

    def decode(i):                       # a tile out of the blob, as pens
        t = TILES[i * 64:(i + 1) * 64]
        p = [[0] * 8 for _ in range(16)]
        for col in range(2):
            for y in range(16):
                for k in range(2):
                    l, r = cpclib.decode_byte(t[col * 32 + y * 2 + k])
                    p[y][col * 4 + k * 2], p[y][col * 4 + k * 2 + 1] = l, r
        return p

    flags = open(os.path.join(BUILD, "tileflags_level5_desert.bin"),
                 "rb").read()
    check("quicksand carries TA_SINK and nothing else, and the sand around "
          "it is solid", flags[QS] == sym["TA_SINK"]
          and flags[T["sand_top"]] & 1 and flags[T["sand_fill"]] & 1,
          f"quicksand {flags[QS]}, TA_SINK {sym['TA_SINK']}")
    check("... and nothing in the desert's tileset carries TA_HAZARD, so no "
          "desert level pays for the spike probe",
          not any(f & 4 for f in flags), f"{sum(1 for f in flags if f & 4)}")

    # Every figure cell of every level against the art: the sheet's pens
    # where it is opaque, the band tile's where it is not.
    figs = {"desert_nomad_cpc_mode0_sheet": (3, 4),
            "desert_informant_cpc_mode0_sheet": (3, 4),
            "desert_shuttle_cpc_mode0_sheet": (6, 6)}
    base = len(T)
    opaque = wrong = cells = 0
    seen = set()
    for n in range(FIRST, LAST + 1):
        mp = lvl(n)["map"]
        npc = next(r for r in recs(n) if r[0] == EK_NPC)
        col = (npc[1] | npc[2] << 8) // 8
        which = []
        # the NPC is three tiles over four rows standing on the ground;
        # which sheet is told by trying both, which is the point - a
        # composite of the wrong one fails every opaque pixel
        for stem in ("desert_nomad_cpc_mode0_sheet",
                     "desert_informant_cpc_mode0_sheet"):
            which.append((stem, col, ROW_GROUND - 4))
        if mp[(ROW_GROUND - 6) * MAP_W + 110] >= base:
            which.append(("desert_shuttle_cpc_mode0_sheet", 110,
                          ROW_GROUND - 6))
        best = []
        for stem, c0, r0 in which:
            img, fr = sheet(stem)
            fw, fh = figs[stem]
            crop = img.crop((fr[0]["x"], fr[0]["y"],
                             fr[0]["x"] + fw * 8, fr[0]["y"] + fh * 16))
            pens = cpclib.quantise(crop, pal)
            a = crop.getchannel("A").load()
            o = bad = 0
            for tr in range(fh):
                for tc in range(fw):
                    i = mp[(r0 + tr) * MAP_W + c0 + tc]
                    got = decode(i)
                    for y in range(16):
                        for x in range(8):
                            px, py = tc * 8 + x, tr * 16 + y
                            if a[px, py]:
                                o += 1
                                bad += got[y][x] != pens[py][px]
            best.append((bad, o, stem, c0, r0, fw * fh))
        # the NPC is whichever of the two sheets matches
        npcs = sorted(best[:2])
        for bad, o, stem, c0, r0, nc in [npcs[0]] + best[2:]:
            opaque += o
            wrong += bad
            cells += nc
            seen.add(stem.split("_")[1])
            print(f"  level {n}: {stem.split('_')[1]} at tile {c0}: "
                  f"{bad} of {o} opaque pixels wrong")
        check(f"level {n}'s NPC is one sheet, not the other",
              npcs[0][0] == 0 and npcs[1][0] > npcs[1][1] // 4,
              f"{npcs[0][2].split('_')[1]} {npcs[0][0]} wrong, "
              f"{npcs[1][2].split('_')[1]} {npcs[1][0]} of {npcs[1][1]}")
    check("every NPC and the shuttle is the artist's own picture, composited "
          "over the band behind it", wrong == 0 and opaque > 0
          and seen == {"nomad", "informant", "shuttle"},
          f"{wrong} of {opaque} opaque pixels in {cells} cells wrong")

    # And what is behind a figure is the BAND: every transparent pixel of
    # a composite is the band tile's own. One check, on the shuttle,
    # whose top rows are over three different bands.
    l20 = lvl(20)["map"]
    img, fr = sheet("desert_shuttle_cpc_mode0_sheet")
    a = img.crop((fr[0]["x"], fr[0]["y"], fr[0]["x"] + 48,
                  fr[0]["y"] + 96)).getchannel("A").load()
    band = {3: "sky_deep", 4: "sky_pale", 5: "sky_haze", 6: "far_plain",
            7: "far_sand", 8: "far_sand"}
    clear = bad = 0
    for tr in range(6):
        under = decode(T[band[3 + tr]])
        for tc in range(6):
            got = decode(l20[(3 + tr) * MAP_W + 110 + tc])
            for y in range(16):
                for x in range(8):
                    if not a[tc * 8 + x, tr * 16 + y]:
                        clear += 1
                        bad += got[y][x] != under[y][x]
    check("... and behind it, the band: the shuttle's transparent pixels are "
          "the sky and the sand", bad == 0 and clear > 0,
          f"{bad} of {clear}")

    for n in range(FIRST, LAST + 1):
        rs = recs(n)
        npc = next(r for r in rs if r[0] == EK_NPC)
        price = npc[6]
        coins = [r for r in rs if r[0] == EK_PICKUP and r[6] == 3]
        before = sum(r[7] for r in coins
                     if (r[1] | r[2] << 8) < (npc[1] | npc[2] << 8))
        check(f"level {n}: {before} coins lie before an NPC who wants "
              f"{price}", before >= price and all(r[7] == 1 for r in coins),
              f"{len(coins)} coin records, each worth "
              f"{sorted({r[7] for r in coins})}")

    src = open(os.path.join(EDITOR, "TileFlags.cs")).read()
    q = re.search(r"Quicksand\s*=\s*(\d+)", src)
    check("the editor's TileFlags.Quicksand is the engine's TA_SINK",
          q and int(q.group(1)) == sym["TA_SINK"],
          f"{q.group(1) if q else None} against {sym['TA_SINK']}")


# =====================================================================
# 2. THE SAND
# =====================================================================
def to_pit(level=17):
    """Into `level` and walked to the lip of its first pit."""
    m, took = F.to_level(sym, level)
    x0 = next(x for x in range(MAP_W) if cell(m, x, ROW_GROUND) == QS)
    F.walk(m, sym, x0 - 3)
    return m, took, x0


def sand():
    print("\nTHE SAND: held, and let down")
    m, took, x0 = to_pit()
    check("into the desert out of the sea's siphon: an environment away",
          took is not None and b(m, "LEVEL_ENV") == 4 and b(m, "LEVEL_OK")
          and m.peek(sym["TILE_ATTR"] + QS) == sym["TA_SINK"]
          and b(m, "LEVEL_SWIM") == 0 and b(m, "LEVEL_HAZARD") == 0,
          f"{took} hardware frames, LEVEL_ENV {b(m, 'LEVEL_ENV')}, the "
          f"quicksand's attribute {m.peek(sym['TILE_ATTR'] + QS)}, "
          f"LEVEL_HAZARD {b(m, 'LEVEL_HAZARD')}")
    mid = (x0 + 1) * 4 - 1                # her box inside the 3-wide pit
    put(m, mid, STAND_WY)
    F.gframe(m, sym, 0)
    y0 = w(m, "KARA_WY")
    for _ in range(40):
        F.gframe(m, sym, 0)
    sunk = w(m, "KARA_WY") - y0
    check("standing in it she goes down a line every other game frame",
          sunk == 20 and b(m, "KARA_GROUND") and b(m, "PLAYER_HP") == 100,
          f"{sunk} lines in 40 game frames, GROUND {b(m, 'KARA_GROUND')}")

    # THE ESCAPE: from each depth, RIGHT and one press of UP.
    out = {}
    for d in range(18, 36, 2):
        put(m, mid, STAND_WY + d)
        for f in range(40):
            F.gframe(m, sym, JOY_RIGHT | (JOY_UP if f == 0 else 0))
            if w(m, "KARA_WY") == STAND_WY and not in_sand(m):
                break
        out[d] = w(m, "KARA_WY") == STAND_WY and not in_sand(m)
    deepest = max((d for d, ok in out.items() if ok), default=None)
    check("one jump lifts her out from as deep as 28 lines and not from 30",
          deepest == 28 and all(out[d] for d in out if d <= 28)
          and not any(out[d] for d in out if d > 28),
          f"out from {sorted(d for d in out if out[d])}, held at "
          f"{sorted(d for d in out if not out[d])}")

    # SWALLOWED: from the surface, nothing held.
    put(m, mid, STAND_WY)
    died = None
    for f in range(140):
        F.gframe(m, sym, 0)
        if b(m, "PLAYER_HP") == 0:
            died = (f, w(m, "KARA_WY") - STAND_WY)
            break
    check("left standing, the sand reaches her chest at 40 lines and has "
          "her", died is not None and died[1] == 40,
          f"HP 0 on game frame {died and died[0]}, "
          f"{died and died[1]} lines down")
    for _ in range(300):
        m.run_frames(1)
        if b(m, "GAME_STATE") == GS_PLAY and b(m, "PLAYER_HP") == 100:
            break
    m.run_frames(10)
    check("... and the level comes back, with her at its start",
          b(m, "PLAYER_HP") == 100 and b(m, "GAME_STATE") == GS_PLAY
          and b(m, "LEVEL_CUR") == 16 and not in_sand(m),
          f"HP {b(m, 'PLAYER_HP')}, WX {w(m, 'KARA_WX')}")

    # THE CONTROL: the same pit with TA_SINK taken off the quicksand's
    # attribute in TILE_ATTR is a hole.
    c, _, x0 = to_pit()
    c.poke(sym["TILE_ATTR"] + QS, 0)
    put(c, (x0 + 1) * 4 - 1, STAND_WY)
    for _ in range(20):
        F.gframe(c, sym, 0)
    deep = w(c, "KARA_WY") - STAND_WY
    for f in range(60):
        F.gframe(c, sym, JOY_RIGHT | (JOY_UP if f % 8 == 0 else 0))
    for _ in range(20):                 # ... and landed from the last one
        F.gframe(c, sym, 0)
    check("... and with TA_SINK taken off the tile the pit is a hole she falls to "
          "the bottom of and cannot leave", deep == 64
          and w(c, "KARA_WY") - STAND_WY == 64,
          f"{deep} lines down, and {w(c, 'KARA_WY') - STAND_WY} after 60 "
          f"frames of RIGHT and UP")


# =====================================================================
# 3. THE NPC AND THE DOOR
# =====================================================================
def npc():
    print("\nTHE NPC: coins for the code, and the door it opens")
    m, _ = F.to_level(sym, 17)
    rs = recs(17)
    i = next(k for k, r in enumerate(rs) if r[0] == EK_NPC)
    r = rs[i]
    price, at = r[6], (r[1] | r[2] << 8) // 2
    rec = sym["ENT_TABLE"] + 8 * i
    door = next(r for r in rs if r[0] == EK_DOOR)
    dat = (door[1] | door[2] << 8) // 2
    put(m, at, STAND_WY)
    for _ in range(30):
        F.gframe(m, sym, 0)
    m.poke(sym["COINS_COUNT"], price - 1)
    F.interact(m, sym)
    check("one coin short, he says nothing and takes nothing",
          b(m, "COINS_COUNT") == price - 1 and b(m, "KEYS_COUNT") == 0
          and not m.peek(rec + 5) & EF_TAKEN,
          f"coins {b(m, 'COINS_COUNT')}, keys {b(m, 'KEYS_COUNT')}")
    m.poke(sym["COINS_COUNT"], price + 2)
    F.interact(m, sym)
    paid = b(m, "COINS_COUNT"), b(m, "KEYS_COUNT")
    F.interact(m, sym)
    check("with his price he takes it and she has the code, once",
          paid == (2, 1) and b(m, "COINS_COUNT") == 2
          and b(m, "KEYS_COUNT") == 1 and m.peek(rec + 5) & EF_TAKEN,
          f"after paying coins {paid[0]} keys {paid[1]}; after asking "
          f"again {b(m, 'COINS_COUNT')} and {b(m, 'KEYS_COUNT')}")

    # the door: without the code, and with it
    c, _ = F.to_level(sym, 17)
    put(c, dat + 4, STAND_WY)
    for _ in range(40):
        F.gframe(c, sym, 0)
    F.interact(c, sym)
    shut = b(c, "GAME_STATE")
    put(m, dat + 4, STAND_WY)
    for _ in range(40):
        F.gframe(m, sym, 0)
    F.interact(m, sym)
    check("the bunker's door stays shut to her without the code and opens "
          "with it", shut == GS_PLAY and b(m, "GAME_STATE") == GS_CLEAR,
          f"without {shut}, with {b(m, 'GAME_STATE')}")


# =====================================================================
# 4. THE ROUTE - from the joystick, 17 to 20
# =====================================================================
def drive(m, n, log):
    """One level from its start to its door: RIGHT, a jump at the lip of
    every pit, a hop whenever the sand has her eight lines down, UP to
    the NPC and UP at the door. Returns (game frames, wrong frames)."""
    rs = recs(n)
    npc_r = next(r for r in rs if r[0] == EK_NPC)
    door = next(r for r in rs if r[0] == EK_DOOR)
    ncol = (npc_r[1] | npc_r[2] << 8) // 8
    dcol = (door[1] | door[2] << 8) // 8
    stuck, was, prev_up, wrong = 0, -1, False, 0
    for f in range(2500):
        if b(m, "GAME_STATE") != GS_PLAY:
            break
        wx, wy = w(m, "KARA_WX"), w(m, "KARA_WY")
        stuck = stuck + 1 if wx == was else 0
        was = wx
        t = (wx + 3) // 4
        want_up = False
        joy = JOY_RIGHT
        ahead = [cell(m, (wx + 6 + k) // 4, ROW_GROUND) for k in (0, 2, 4)]
        if wy == STAND_WY and QS in ahead:
            want_up = True
        if in_sand(m) and wy - STAND_WY >= 8:
            want_up = True
        if stuck >= 6:
            want_up, stuck = True, 0
        if t >= ncol and not b(m, "KEYS_COUNT") and wy == STAND_WY:
            joy, want_up = 0, True
        if t >= dcol + 1 and b(m, "KEYS_COUNT"):
            joy, want_up = 0, True
        up = want_up and not prev_up
        prev_up = up
        F.gframe(m, sym, joy | (JOY_UP if up else 0))
        if in_sand(m):
            log["depth"] = max(log["depth"], w(m, "KARA_WY") - STAND_WY)
        log["hp"] = min(log["hp"], b(m, "PLAYER_HP"))
        if b(m, "GAME_STATE") == GS_PLAY and F.wrong_cells(m, sym, TILES):
            wrong += 1
    m.joystick(0)
    return f, wrong


def route():
    print("\nTHE ROUTE: from the oasis to the shuttle, from the joystick")
    m, _ = F.to_level(sym, FIRST)
    painted = [n for n in range(FIRST, 25)
               if os.path.exists(os.path.join(BUILD, f"level_{n}.lvl"))]
    for n in range(FIRST, LAST + 1):
        log = {"depth": 0, "hp": 100}
        c0 = b(m, "COINS_COUNT")
        frames, wrong = drive(m, n, log)
        check(f"level {n}: through its door, the NPC paid, never hurt",
              b(m, "GAME_STATE") == GS_CLEAR and log["hp"] == 100,
              f"{frames} game frames, coins {c0} -> {b(m, 'COINS_COUNT')}, "
              f"deepest in the sand {log['depth']} lines, HP at least "
              f"{log['hp']}")
        check(f"level {n}: every on-screen cell is the map's on every game "
              f"frame", wrong == 0, f"{wrong} frames")
        took = None
        for f in range(600):
            m.run_frames(1)
            if (b(m, "GAME_STATE") == GS_PLAY and b(m, "LEVEL_CUR") == n
                    and b(m, "LEVEL_OK")):
                took = f + 1
                break
        if n < LAST:
            check(f"... into level {n + 1}, one sector and no art",
                  took is not None and took < 100 and b(m, "LEVEL_ENV") == 4,
                  f"{took} hardware frames")
            m.run_frames(10)
        elif LAST + 1 in painted:
            check("... and the shuttle leads to level 21, the station: an "
                  "environment away", took is not None
                  and b(m, "LEVEL_ENV") == 5, f"{took} hardware frames")
        else:
            m.run_frames(300)
            lo, hi = sym["INTRO_WAIT"], sym["INTRO_WAIT"] + 0x80
            title = False
            for _ in range(2 * 19968 // 8):
                m.run_us(8)
                if lo <= m.pc < hi:
                    title = True
                    break
            check("... and level 21 is the station, unpainted, so the "
                  "shuttle goes back to the title", title)


# =====================================================================
# 5. THE LOCK, AND WHAT IT COSTS
# =====================================================================
def lock():
    print("\nTHE LOCK: game frames in 200 hardware frames")
    m, _, x0 = to_pit(18)
    put(m, (x0 - 2) * 4, STAND_WY)
    for _ in range(10):
        F.gframe(m, sym, 0)
    n, _ = F.stand_count(m, sym)
    check(f"standing on the sand: 100", n == 100, f"{n}")
    put(m, (x0 + 1) * 4, STAND_WY)
    n, _ = F.stand_count(m, sym, pattern=lambda g: JOY_UP if g % 12 == 0
                         else 0)
    check("hopping in the quicksand: 100", n == 100 and in_sand(m),
          f"{n}, {w(m, 'KARA_WY') - STAND_WY} lines down at the end")
    # THE CONTROL: SCROLL_SERVICE's tick gate taken away, so the first
    # sweep begins a piece of the incoming row however late it reaches
    # it - the engine as it was. Sinking steps the camera down a row, and
    # the piece lands on a take-off's or a landing's sweep.
    c, _, x0 = to_pit(18)
    c.poke(sym["V_A_LIMIT"], 255)
    put(c, (x0 + 1) * 4, STAND_WY)
    for _ in range(4):
        F.gframe(c, sym, 0)
    n2, _ = F.stand_count(c, sym, pattern=lambda g: JOY_UP if g % 12 == 0
                          else 0)
    check("... and with the row's tick gate taken away, the same hop drops "
          "a game frame", n2 < 100, f"{n2}")
    m2, _, x0 = to_pit(18)
    put(m2, 4 * 4, STAND_WY)
    for _ in range(10):
        F.gframe(m2, sym, 0)
    n, _ = F.stand_count(m2, sym, pattern=lambda g: JOY_RIGHT
                         | (JOY_UP if g % 10 == 0 else 0))
    check("walking and jumping across the dunes: 100", n == 100, f"{n}")
    m2.key_down('A')
    n, _ = F.stand_count(m2, sym, pattern=lambda g: JOY_RIGHT
                         | (JOY_UP if g % 10 == 0 else 0))
    m2.key_up('A')
    check("running and jumping: 100", n == 100, f"{n}")
    # THE DESERT'S TIGHTEST PATH: running through the sand with the gun
    # going. The sand is 892 T a game frame while she is in it, which is
    # more than the 800 the run with the gun has on a level with a drone
    # (CLAUDE.md 9) - and the desert has no drone, which is the forest's
    # argument for its spikes (8.12) one hazard along.
    m3, _, x0 = to_pit(18)
    put(m3, (x0 - 3) * 4, STAND_WY)
    for _ in range(10):
        F.gframe(m3, sym, 0)
    m3.key_down('A')
    sand = []
    n, _ = F.stand_count(m3, sym, pattern=lambda g: (
        sand.append(in_sand(m3)) or JOY_RIGHT | (0x10 if g % 6 < 2 else 0)
        | (JOY_UP if g % 14 == 0 else 0)))
    m3.key_up('A')
    check("running and firing through the quicksand: 100", n == 100
          and sum(sand) > 20, f"{n}, in the sand on {sum(sand)} of "
          f"{len(sand)} samples")


def cost():
    print("\nWHAT IT COSTS: SINK_STEP, from a DI stub")
    import bench
    from bench import boot
    m, _, x0 = to_pit()
    put(m, (x0 + 1) * 4 - 1, STAND_WY + 8)
    F.gframe(m, sym, 0)

    def acc(v, fc=None):
        def setup(mm):
            mm.poke(sym["PROBE_ACC"], v)
            if fc is not None:
                mm.poke(sym["FRAME_COUNT"], fc)
        return setup
    bm = bench.Bench(m, sym)
    sinks = bm.T("SINK_STEP", acc(sym["TA_SINK"], 0))
    holds = bm.T("SINK_STEP", acc(sym["TA_SINK"], 1))
    city = boot(sym, scroll=True)
    for _ in range(40):
        city.run_frames(1)
    none = bench.Bench(city, sym).T("SINK_STEP", acc(sym["TA_SOLID"]))
    print(f"  no sand under her {none} T; in it, the frame she goes down "
          f"{sinks} T and the frame she does not {holds} T")
    check("nothing under her but air costs the AND of a byte the floor's "
          "probe has just written", none is not None and none < 60,
          f"{none} T on level 1")
    check("... and in the sand, a column's probe on one frame in two",
          sinks is not None and holds is not None and sinks < 600
          and holds < 100, f"{sinks} T and {holds} T")


def main():
    offline()
    sand()
    npc()
    route()
    lock()
    cost()
    print()
    print("ALL CHECKS PASSED" if not fails else
          f"{len(fails)} FAILED: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
