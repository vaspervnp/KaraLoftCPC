#!/usr/bin/env python3
"""The desert's maps: levels 17 to 20. CLAUDE.md 8.22.

THE ARTIST COMPOSED IT AND THIS TOOL ONLY LAYS IT OUT. The manifest's
notes give the bands the tiles are painted for, and the three mockups
are a screen of each part composed:

    rows 0-3   sky_deep
    row  4     sky_pale             ... a bunker's roof
    row  5     sky_haze             ... a palm's crown
    row  6     far_plain / mesas    ... a palm's horizon trunk
    rows 7-8   far_sand             ... the deco, the tents, the pillars
    row  9     THE GROUND           ... sand_top, quicksand, the pool
    rows 10+   sand_fill

THE GROUND IS ROW 9, the forest's row and for the forest's reason: the
vertical camera keeps her middle at 112 standing there, and the view
stays put until something takes her down (CLAUDE.md 8.11).

PLAN.MD'S DESERT IS QUICKSAND AND NPCS WHO SELL WHAT THEY KNOW FOR
COINS, and both are in it:

* QUICKSAND IS A PIT FOUR ROWS DEEP of the artist's quicksand tile,
  flagged TA_SINK - the format's Quicksand bit, which nothing read
  until now (src/player.asm SINK_STEP). She is held in it and let down
  a line on every other game frame; past 28 lines her jump cannot lift
  her over its lip, and at 40 it has her. So a pit is crossed by
  hopping, or by the pillars and ledges over it.
* AN NPC IS PAID IN COINS AND GIVES THE CODE TO THE NEXT DOOR, as the
  key that door asks for (src/entity.asm TALK_NPC_COIN). There is no
  key lying about in the desert: the way out is bought. Every level
  carries at least the price in coins, so a player who arrives with
  none can still pay.

THE NPCS AND THE SHUTTLE ARE TILES, BAKED HERE. None of them moves: the
nomad and the informant are 24x64 - agent class, which the frame cannot
draw (CLAUDE.md 9) - and a picture that does not move is scenery
(8.17). Each is composited over the bands behind it, ONE cel, and their
span blobs stop going into the banks (tools/level_banks.py's BAKED),
which is what pays for the composites.

THE MERCENARY IS NOT HERE, AND THAT IS THE SAME MEASUREMENT: 24x64,
agent class. The desert has no enemy, like the forest.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
BUILD = os.path.join(ROOT, "build")
sys.path.insert(0, HERE)
from make_level import pack, read                              # noqa: E402
from tilebake import box_pens, encode_tile, sheet_frames       # noqa: E402
import sentries                                                 # noqa: E402

ART = os.path.join(ROOT, "assets", "sprites", "level5_desert")
TILES_SHEET = "desert_tiles_cpc_mode0_sheet"

MAP_W, MAP_H = 128, 16
TILESET_ID = 5                  # environment 5, levels 17-20
ROW_HAZE, ROW_HORIZON, ROW_GROUND = 5, 6, 9
SINK_ROWS = 4                   # a quicksand pit: the ground row and three
                                # under it - 64 lines, past the 40 that
                                # swallow her (SINK_CHEST)

SOLID, PLATFORM, HAZARD, SINK = 1, 2, 4, 32
TILE_FLAGS = {
    "sand_top": SOLID, "sand_fill": SOLID, "rock_fill": SOLID,
    # THE SANDSTONE LEDGE AND THE PILLAR'S TOP ARE PLATFORMS, not solid.
    # A pillar is two tiles and its top is 32 lines over the ground, and
    # her jump rises 28: solid, it is a wall (CLAUDE.md 8.14). As a
    # platform her reach is 43, and the shaft under it is scenery.
    "rock_l": PLATFORM, "rock_m": PLATFORM, "rock_r": PLATFORM,
    "pillar_top": PLATFORM,
    "quicksand": SINK,
    # The oasis: the pool's surface is water she stands in, the deep
    # under it is the bed; the outlet's rock is rock.
    "pool_deep": SOLID, "siphon_top": SOLID, "siphon": SOLID,
    # AND THE REST IS SCENERY, against two of the artist's suggestions.
    # The saguaro is deco in the manifest and stays deco: a one-tile
    # hazard in the row her last line is in bites on every walk past,
    # and a running jump spends five game frames over it. And the
    # bunker's walls are a FACADE, the City's brick again (CLAUDE.md
    # 8.8): solid, the wall at its left edge stops her box four bytes
    # short of the door's, so UP there meets nothing.
}

EK_PLAYER_START, EK_ENEMY, EK_NPC, EK_PICKUP, EK_DOOR = 0, 2, 3, 4, 6
EN_MERC = 7                     # the mercenary, a sentry (CLAUDE.md 8.27)
EF_ACTIVE, EF_TAKEN, EF_SOLID, EF_TOUCH = 1, 2, 4, 8
PU_KEY, PU_AMMO, PU_MEDKIT, PU_COIN = 0, 1, 2, 3
ENT_MAX = 24
BAKE_LIMIT = 240                # ENT_BAKE's scratch tiles start here

# THE FIGURES: (sheet, its frame, width and height in tiles). One cel,
# the first of each sheet's own idle - a tile does not animate here.
FIGURES = {
    "nomad": ("desert_nomad_cpc_mode0_sheet", 0, 3, 4),
    "informant": ("desert_informant_cpc_mode0_sheet", 0, 3, 4),
    "shuttle": ("desert_shuttle_cpc_mode0_sheet", 0, 6, 6),
}


def tile_names():
    """The manifest's own `tile_names`, checked against tile_table.json -
    two statements of one order, which have to agree."""
    man = json.load(open(os.path.join(ART, "manifest.json")))
    sheet = next(s for s in man["sheets"] if s["name"] == "desert_tiles")
    names = {n: i for i, n in enumerate(sheet["tile_names"])}
    table = json.load(open(os.path.join(ART, "tile_table.json")))
    rows = next(s for s in table["sheets"] if s["sheet"] == "desert_tiles")
    assert [x["name"] for x in rows["tiles"]] == sheet["tile_names"], \
        "the manifest and the tile table disagree on the order"
    return names


class Bake:
    """Every composite the desert's levels place, numbered from the end
    of the tileset in the order they are first placed - shared, because
    a tileset is the environment's (8.13)."""

    def __init__(self, t):
        self.t = t
        self.name = {i: n for n, i in t.items()}
        self.n = len(t)
        self.tiles, self.tile_boxes = sheet_frames(ART, TILES_SHEET)
        self.sheets = {}
        self.blob = bytearray()
        self.extra = []
        self.done = {}

    def piece(self, fig, col, row, bg):
        """Tile (col, row) of figure `fig` over background tile `bg`."""
        key = (fig, col, row, bg)
        if key not in self.done:
            stem, frame, _, _ = FIGURES[fig]
            if stem not in self.sheets:
                self.sheets[stem] = sheet_frames(ART, stem)
            sheet, boxes = self.sheets[stem]
            b = boxes[frame]
            over = box_pens(sheet, b["x"] + col * 8, b["y"] + row * 16, 8, 16,
                            alpha=True)
            ub = self.tile_boxes[bg]
            under = box_pens(self.tiles, ub["x"], ub["y"], ub["w"], ub["h"])
            pens = [[o if o is not None else u for o, u in zip(ro, ru)]
                    for ro, ru in zip(over, under)]
            i = self.n + len(self.extra)
            assert i < BAKE_LIMIT, "the bake reached ENT_BAKE's scratch tiles"
            self.blob += encode_tile(pens)
            self.extra.append((f"{fig}_{col}{row}_on_{self.name[bg]}",
                               TILE_FLAGS.get(self.name[bg], 0)))
            self.done[key] = i
        return self.done[key]


# ---------------------------------------------------------------------
# THE COMPOSITION, one entry a level. Every number is a TILE column.
#
#   pits      (left, width) of quicksand, SINK_ROWS deep
#   ledges    (left, length, row) of sandstone ledge - a platform
#   pillars   columns of a broken pillar: top at row 7, shaft at row 8
#   cacti     columns of a saguaro - its foot bites
#   npc       (which, left column, price in coins): stands on the
#             ground, three tiles wide; his tent is to his left
#   coins     (column, the row it stands ON)
#   bunker    the left column of the bunker the level ends at; its door
#             is the four after it
#   entry     the left column of a bunker she came OUT of, if any
#   mercs     (column, the row it stands ON) of a mercenary: a SENTRY,
#             24x64 and drawn compiled, which keeps its post and shoots
#             at her (src/sentry.asm). Two a level, GAP tiles apart, on
#             a column tools/sentries.py says its cel can be drawn on
# ---------------------------------------------------------------------
# LEVEL 17 IS THE OASIS. She comes out of the siphon's outlet into the
# pool at the left - level 16's way out leads here - and walks east. Two
# small pits teach the sand: three wide, which a running jump clears and
# a walk drops into; the informant by his tent, at the end, sells the
# code to the bunker beside him for three coins, and she has passed five.
#
# EVERY NPC STANDS AFTER HIS PRICE, so a player who picks up what is in
# her way can pay him without going back - and none of them is between
# two coins she would have to fetch from beyond him.
LEVEL_17 = dict(
    level=17, about="the oasis",
    start=11, outlet=True,
    mesas=(26, 58, 96), palms=(14, 44, 74),
    pits=((50, 3), (84, 3)),
    ledges=((60, 4, 7),),
    pillars=(),
    cacti=(38, 88),
    bones=(56, 92), signs=(), fences=(),
    tents=(100,), npc=("informant", 103, 3),
    mercs=((32, 9), (72, 9)),
    coins=((22, 9), (46, 9), (62, 7), (79, 9), (98, 9)),
    medkits=(), ammo=(),
    bunker=116, entry=None, shuttle=None,
)
# LEVEL 18 IS THE DUNES: the sand is the level. Three fields of it, each
# wider than any jump, crossed by what stands out of them - pillars a
# jump apart, and a sandstone ledge - or by hopping, which the sand lets
# her do as long as she does not stop. The nomad wants four coins and
# two of them are over the sand.
LEVEL_18 = dict(
    level=18, about="the dunes",
    start=8, outlet=False,
    mesas=(18, 50, 88), palms=(),
    pits=((22, 8), (52, 10), (90, 8)),
    ledges=((54, 3, 7), (58, 3, 5), (63, 3, 7)),
    pillars=(25, 29, 93, 97),
    cacti=(42, 80),
    bones=(16, 70, 112), signs=(), fences=(),
    tents=(104,), npc=("nomad", 107, 4),
    mercs=((44, 9), (84, 9)),
    coins=((14, 9), (29, 7), (59, 5), (73, 9), (97, 7), (113, 9)),
    medkits=(), ammo=(),
    bunker=116, entry=4, shuttle=None,
)
# LEVEL 19 IS THE FENCE: the restricted area - signs, chain link, the
# cacti thicker, and the sand deeper into it. Ledges two high over the
# widest field, so the way across is up and along; the informant again,
# for five.
LEVEL_19 = dict(
    level=19, about="the fence",
    start=8, outlet=False,
    mesas=(30, 66, 102), palms=(),
    pits=((26, 6), (58, 12), (96, 6)),
    ledges=((56, 3, 7), (60, 4, 5), (66, 3, 7), (70, 3, 5)),
    pillars=(29, 99),
    cacti=(20, 46, 84, 110),
    bones=(), signs=(16, 48, 88), fences=(17, 18, 49, 50, 89, 90),
    tents=(102,), npc=("informant", 105, 5),
    mercs=((40, 9), (86, 9)),
    coins=((12, 9), (29, 7), (36, 9), (62, 5), (72, 5), (80, 9), (99, 7)),
    medkits=(77,), ammo=(),
    bunker=116, entry=4, shuttle=None,
)
# LEVEL 20 IS THE LAUNCH PAD, the desert's last and plan.md's "secret
# launch base and boarding the craft": out of a bunker, across the last
# of the sand, the nomad for the boarding code, and the shuttle on its
# pad at the far end - the way out is its door, and it leads to the
# station.
LEVEL_20 = dict(
    level=20, about="the launch pad",
    start=8, outlet=False,
    mesas=(28, 64), palms=(),
    pits=((24, 5), (50, 8), (82, 6)),
    ledges=((52, 3, 7), (57, 3, 7)),
    pillars=(85,),
    cacti=(40, 72, 100),
    bones=(), signs=(96,), fences=(97, 98, 99),
    tents=(64,), npc=("nomad", 67, 5),
    mercs=((32, 9), (92, 9)),
    coins=((18, 9), (27, 9), (44, 9), (53, 7), (58, 7), (78, 9), (85, 7)),
    medkits=(46,), ammo=(),
    bunker=None, entry=4, shuttle=110,
)
LAYOUTS = (LEVEL_17, LEVEL_18, LEVEL_19, LEVEL_20)


def build_map(t, L, bake):
    g = [[t["sand_fill"]] * MAP_W for _ in range(MAP_H)]
    for x in range(MAP_W):
        for r in range(0, 4):
            g[r][x] = t["sky_deep"]
        g[4][x] = t["sky_pale"]
        g[ROW_HAZE][x] = t["sky_haze"]
        g[ROW_HORIZON][x] = t["far_plain"]
        g[7][x] = g[8][x] = t["far_sand"]
        g[ROW_GROUND][x] = t["sand_top"]
    for x in L["mesas"]:
        g[ROW_HORIZON][x], g[ROW_HORIZON][x + 1] = t["far_mesa_l"], t["far_mesa_r"]

    def figure(fig, left, top):
        _, _, w, h = FIGURES[fig]
        for row in range(h):
            for col in range(w):
                bg = g[top + row][left + col]
                assert bake.name[bg] in ("sky_deep", "sky_pale", "sky_haze",
                                         "far_plain", "far_sand"), \
                    f"the {fig} at {left} stands over {bake.name[bg]}"
                g[top + row][left + col] = bake.piece(fig, col, row, bg)

    # ---- the oasis and the siphon's outlet, at the left --------------
    # "rock_l rock_m rock_r cap (row 7), rock_fill rock_fill siphon_top
    # (row 8), rock_fill rock_fill siphon (row 9)"; the pool after it.
    if L["outlet"]:
        g[7][0], g[7][1], g[7][2] = t["rock_l"], t["rock_m"], t["rock_r"]
        g[8][0], g[8][1], g[8][2] = t["rock_fill"], t["rock_fill"], t["siphon_top"]
        g[9][0], g[9][1], g[9][2] = t["rock_fill"], t["rock_fill"], t["siphon"]
        g[9][3] = t["pool_l"]
        for x in range(4, 8):
            g[9][x] = t["pool_m"]
        g[9][8] = t["pool_r"]
        for x in range(3, 9):
            g[10][x] = t["pool_deep"]

    for x in L["palms"]:                    # crown, horizon trunk, trunk
        g[5][x - 1], g[5][x], g[5][x + 1] = t["palm_l"], t["palm_m"], t["palm_r"]
        g[6][x] = t["palm_trunk_hz"]
        g[7][x] = g[8][x] = t["palm_trunk"]
    for x in L["tents"]:
        g[7][x + 1] = t["tent_top"]
        g[8][x], g[8][x + 1], g[8][x + 2] = t["tent_l"], t["tent_m"], t["tent_r"]
    for x in L["bones"]:
        g[8][x] = t["bones"]
    for x in L["signs"]:
        g[8][x] = t["sign"]
    for x in L["fences"]:
        g[8][x] = t["fence"]
    for x in L["cacti"]:
        g[7][x], g[8][x] = t["cactus_top"], t["cactus_bot"]
    for x in L["pillars"]:
        g[7][x], g[8][x] = t["pillar_top"], t["pillar_shaft"]
    for x, n, row in L["ledges"]:
        for i in range(n):
            g[row][x + i] = t["rock_l" if i == 0 else
                              "rock_r" if i == n - 1 else "rock_m"]

    # ---- the quicksand ---------------------------------------------
    for x, n in L["pits"]:
        for i in range(n):
            for r in range(ROW_GROUND, ROW_GROUND + SINK_ROWS):
                g[r][x + i] = t["quicksand"]

    # ---- the bunkers -------------------------------------------------
    # "roof_l roof_m x4 roof_r (row 4) over base_wall | door x4 |
    # base_wall (rows 5-8)" - the door block is 32x64, her height.
    for b in (L["bunker"], L["entry"]):
        if b is None:
            continue
        g[4][b] = t["roof_l"]
        for i in range(1, 5):
            g[4][b + i] = t["roof_m"]
        g[4][b + 5] = t["roof_r"]
        for r in range(5, 9):
            g[r][b], g[r][b + 5] = t["base_wall"], t["base_wall"]
            for i in range(1, 5):
                g[r][b + i] = t["door"]

    # ---- the figures, last, over the bands ---------------------------
    which, left, _ = L["npc"]
    figure(which, left, ROW_GROUND - 4)
    if L["shuttle"] is not None:
        figure("shuttle", L["shuttle"], ROW_GROUND - 6)
    return g


def entity(kind, x_px, y_base, flags, p0=0, p1=0):
    return bytes([kind, x_px & 255, x_px >> 8, y_base & 255, y_base >> 8,
                  flags, p0, p1])


def build_entities(L):
    """The records, in file order. She starts a row high and falls onto
    the sand (CLAUDE.md 8.11); a pickup stands on the tile grid; the NPC's
    box is the middle of his three tiles."""
    ground = ROW_GROUND * 16
    recs = [entity(EK_PLAYER_START, L["start"] * 8, ground - 16, EF_ACTIVE)]
    for x, row in L["coins"]:
        # p1 IS THE AMOUNT (8.6): a coin record with p1 0 is taken, drawn
        # off the map and worth nothing, which is how the first build of
        # this level played.
        recs.append(entity(EK_PICKUP, x * 8, row * 16,
                           EF_ACTIVE | EF_TOUCH, PU_COIN, 1))
    for x in L["medkits"]:
        recs.append(entity(EK_PICKUP, x * 8, ground,
                           EF_ACTIVE | EF_TOUCH, PU_MEDKIT))
    which, left, price = L["npc"]
    # His box is 6 bytes - 12 pixels - so it starts 6 pixels into his 24.
    recs.append(entity(EK_NPC, left * 8 + 6, ground, EF_ACTIVE, price, 0))
    if L["bunker"] is not None:
        door = L["bunker"] + 1
    else:
        door = L["shuttle"] + 1             # the boarding door, on the pad
    recs.append(entity(EK_DOOR, door * 8, ground, EF_ACTIVE | EF_SOLID,
                       0, PU_KEY))
    for x, row in L.get("mercs", ()):
        recs.append(entity(EK_ENEMY, x * 8, row * 16, EF_ACTIVE, EN_MERC, 0))
    assert len(recs) <= ENT_MAX
    return b"".join(recs)


def reachable(g, t, L):
    """Every place she can stand, from the start - the forest's model,
    walking, falling off an edge and jumping at most two rows and three
    tiles, with QUICKSAND counted as somewhere she can jump FROM: she is
    held in it, grounded, for as long as it has not got her."""
    flags = {i: TILE_FLAGS.get(n, 0) for n, i in t.items()}

    def fl(x, row):
        b = g[row][x]
        return flags.get(b, 0) if b < len(t) else bake_flags.get(b, 0)
    solid = lambda x, r: fl(x, r) & SOLID
    stand = lambda x, r: fl(x, r) & (SOLID | PLATFORM | SINK)

    def on(x, row):
        if not 0 <= x < MAP_W or not 1 <= row < MAP_H:
            return False
        return stand(x, row) and not solid(x, row - 1) \
            and not (fl(x, row - 1) & SINK)

    def under(x, row):
        for r in range(row, MAP_H):
            if on(x, r):
                return r
        return None

    start = (L["start"], under(L["start"], ROW_GROUND - 1))
    seen, todo = set(), [start]
    while todo:
        x, row = todo.pop()
        if (x, row) in seen or row is None:
            continue
        seen.add((x, row))
        for nx in (x - 1, x + 1):
            if on(nx, row):
                todo.append((nx, row))
            elif 0 <= nx < MAP_W and not solid(nx, row):
                todo.append((nx, under(nx, row)))
        for nx in range(x - 3, x + 4):
            for nr in (row - 1, row - 2):
                if on(nx, nr):
                    todo.append((nx, nr))
    return seen


bake_flags = {}


def checks(g, t, ents, L):
    assert len(ents) // 8 <= ENT_MAX
    recs = [ents[i:i + 8] for i in range(0, len(ents), 8)]
    pickups = [r for r in recs if r[0] == EK_PICKUP]
    assert len(pickups) <= 16
    coins = sum(r[7] for r in pickups if r[6] == PU_COIN)
    price = L["npc"][2]
    assert coins >= price, f"level {L['level']}: {coins} coins for {price}"
    before = sum(1 for x, _ in L["coins"] if x < L["npc"][1])
    assert before >= price, \
        f"level {L['level']}: {before} coins before the NPC, who wants {price}"
    where = reachable(g, t, L)
    for r in recs:
        if r[0] not in (EK_PICKUP, EK_NPC, EK_DOOR):
            continue
        x = (r[1] | r[2] << 8) // 8
        row = (r[3] | r[4] << 8) // 16
        assert (x, row) in where, \
            f"level {L['level']}: a kind-{r[0]} at tile {x}, row {row} " \
            f"is somewhere she cannot stand"
    # A SENTRY STANDS ON SAND - every column of its box over solid
    # ground, not a pit - where its cel can be drawn and nothing is
    # painted under it (tools/sentries.py).
    for x, row in L.get("mercs", ()):
        assert all(g[row][c] == t["sand_top"] for c in range(x, x + 3)), \
            f"level {L['level']}: the mercenary at {x} is not on sand"
    sentries.check(L["level"], L.get("mercs", ()), ents)
    # A PIT MUST BE ONE SHE CAN GET OUT OF: sand on both sides of it, so
    # there is a lip to jump to.
    for x, n in L["pits"]:
        assert g[ROW_GROUND][x - 1] == t["sand_top"]
        assert g[ROW_GROUND][x + n] == t["sand_top"]
    return coins, len(where)


def main():
    t = tile_names()
    bake = Bake(t)
    built = []
    for L in LAYOUTS:
        g = build_map(t, L, bake)
        built.append((L, g))
    bake_flags.update({t_i: f for t_i, (_, f) in
                       enumerate(bake.extra, start=len(t))})

    flags = bytes(TILE_FLAGS.get(n, 0)
                  for n, _ in sorted(t.items(), key=lambda kv: kv[1]))
    flags += bytes(f for _, f in bake.extra)
    open(os.path.join(BUILD, "tileflags_level5_desert.bin"), "wb").write(flags)
    print(f"-> tileflags_level5_desert.bin  {len(flags)} tiles, "
          f"{sum(1 for f in flags if f)} with anything on")

    tiles = os.path.join(BUILD, "levels", "level5_desert", "deserttiles.bin")
    base = open(tiles, "rb").read()[:64 * len(t)]
    assert len(base) == 64 * len(t), "the tile blob is short"
    open(tiles, "wb").write(base + bytes(bake.blob))
    from build_levels import zx0
    zx0(tiles)
    print(f"-> deserttiles.bin  {len(t)} tiles + {len(bake.extra)} baked "
          f"= {len(base) + len(bake.blob)} bytes")

    for L, g in built:
        ents = build_entities(L)
        coins, reach = checks(g, t, ents, L)
        m = bytes(b for row in g for b in row)
        lvl = pack(level_id=L["level"], tileset_id=TILESET_ID,
                   width=MAP_W, height=MAP_H, map_bytes=m, entities=ents)
        out = os.path.join(BUILD, f"level_{L['level']}.lvl")
        open(out, "wb").write(lvl)
        back = read(lvl)
        assert back["map"] == m and back["entities"] == len(ents) // 8
        print(f"-> level_{L['level']}.lvl    {len(lvl)} bytes: {MAP_W}x"
              f"{MAP_H}, {back['entities']} entities, {len(L['pits'])} "
              f"quicksand pits, {coins} coins for a price of "
              f"{L['npc'][2]}, tileset {TILESET_ID} - {L['about']}; "
              f"{reach} places she can stand")
    return 0


if __name__ == "__main__":
    sys.exit(main())
