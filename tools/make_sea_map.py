#!/usr/bin/env python3
"""The undersea's maps - level 13 first - and the cables baked into its
tileset. CLAUDE.md 8.18.

THE ARTIST COMPOSED THIS ENVIRONMENT AND THIS TOOL ONLY LAYS IT OUT.
`assets/sprites/level4_underwater/manifest.json` describes every piece,
and two mockups compose them. Read back cell by cell - they are 160-pixel
screens at 6x3, exactly as the forest's was (8.11) - every cell of both
matches a tile of the sheet, and what the reading says is the grammar
below:

    row 0       sky between the walls, rock_2 in them
    row 1       the surface, rock_1 in the walls
    then        bg_light, bg_mid, bg_deep - FLAT bands, changing on
                whole tile rows, with the wall's inner face in the
                band's own colour: wall_light / wall_mid / wall_deep
    a ledge     two rows growing out of a wall: rock_top along the top
                and ledge_tr at its end, rock_under and ledge_br below
                (mirrored for the right wall: ledge_tl / ledge_bl),
                rock_fill in the wall's face column at those rows
    the floor   sand_top over sand_fill, props standing on it
    the siphon  rim_l, throat_top x4, rim_r in the floor row, and
                rock_fill | throat x4 | rock_fill under it
    a cable     anchor_top under a ledge, anchor_bot on the one below,
                the cable itself between - "stack between anchor_top /
                anchor_bot tiles"

IT IS 32x64, VERTICAL, AND IT GOES DOWN: "Vertical scroll top to
bottom, 20 tiles wide" is the manifest's own note, and 32x64 is the
shape the cave already proved on a 6128 (8.13). 20 tiles is a screen;
this is 26 of water between two walls, so the camera pans a little.

THE CABLE IS A TRAP, the forest's machinery with a second kind
(src/hazard.asm, 8.17): a map cell whose tile changes, four cels at
consecutive indexes composited over the water at build time, and the
bite is the TILE's - TA_HAZARD on the live cel, read by HAZARD_HURT.
The artist's cycle is "1.5 s off, 1 s live; flash one spark frame as
warning 250 ms before going live", and a trap has four cels, so:

    cel 0   off                      the safe one
    cel 1   spark frame 1            the warning flash - NO hazard
    cel 2   off                      ... a beat before
    cel 3   spark frame 3            live, and TA_HAZARD

and the durations are HZ_DUR's second row, in game frames.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
BUILD = os.path.join(ROOT, "build")
sys.path.insert(0, HERE)
from make_level import pack, read, UNDERWATER, SCROLL_V          # noqa: E402
from tilebake import box_pens, encode_tile, sheet_frames         # noqa: E402

ART = os.path.join(ROOT, "assets", "sprites", "level4_underwater")
TILES_SHEET = "sea_tiles_cpc_mode0_sheet"
CABLE_SHEET = "sea_cable_cpc_mode0_sheet"

MAP_W, MAP_H = 32, 64           # 1.6 screens across, 5.3 DOWN
TILESET_ID = 4                  # environment 4, levels 13-16

SOLID, PLATFORM, HAZARD = 1, 2, 4

# THE WALLS. Two columns of rock and a face, each side: 26 of water.
WALL_L, WALL_R = 2, 29          # the face columns
WATER = range(WALL_L + 1, WALL_R)

# THE BANDS, in rows. Row 0 is sky and row 1 the surface; the floor is
# the last two. Ledges round off only in the MID band - ledge_tr/br/
# tl/bl are drawn over bg_mid ("wall/ledge/prop tiles carry the band in
# their name and must sit in that band") - so the ledges live there.
ROW_SKY, ROW_SURFACE = 0, 1
LIGHT = range(2, 16)
MID = range(16, 48)
DEEP = range(48, 62)
ROW_SAND, ROW_FILL = 62, 63

# HER BOX IN THE WATER is 16 bytes by 24 lines (src/swim.asm): four
# tiles across and a tile and a half down. So a gap she swims through is
# at least five tiles wide, and a passage at least two rows tall.
GAP_MIN, PASS_MIN = 5, 2

TILE_FLAGS = {
    # What stops her: the rock, the walls, the ledges, the floor and
    # everything standing on it that is not a plant. And the SKY and the
    # SURFACE, which is the top of the water - she swims up to it and
    # no further.
    "sky_1": SOLID, "surface_1": SOLID, "surface_2": SOLID,
    "rock_1": SOLID, "rock_2": SOLID, "rock_3": SOLID,
    "wall_light_1": SOLID, "wall_light_2": SOLID,
    "wall_mid_1": SOLID, "wall_mid_2": SOLID,
    "wall_deep_1": SOLID, "wall_deep_2": SOLID,
    "wall_deep_3": SOLID, "wall_deep_4": SOLID,
    "ledge_mid_1": SOLID, "ledge_mid_2": SOLID,
    "ledge_mid_3": SOLID, "ledge_mid_4": SOLID,
    "sand_1": SOLID, "sand_2": SOLID,
    "ruins_1": SOLID, "ruins_2": SOLID, "ruins_3": SOLID,
    "pipe_1": SOLID, "pipe_2": SOLID,
    "cable_anchor_1": SOLID, "cable_anchor_2": SOLID,
    "vent_1": SOLID, "vent_2": SOLID, "vent_3": SOLID,
    "siphon_rim_1": SOLID, "siphon_rim_2": SOLID,
    "siphon_rim_3": SOLID, "siphon_rim_4": SOLID,
    # The water, the light shaft, the coral and the weed carry nothing.
}

# What the manifest calls the tiles, against what the table calls them.
# tile_table.json numbers each tag's tiles in the order the manifest's
# description lists them, so this is a reading of that sentence.
ALIAS = {
    "bg_light": "bg_1", "bg_mid": "bg_2", "bg_deep": "bg_3",
    "bg_ray": "bg_ray_1", "sky": "sky_1",
    "rock_fill": "rock_1", "rock_top": "rock_2", "rock_under": "rock_3",
    "wall_l_light": "wall_light_1", "wall_r_light": "wall_light_2",
    "wall_l_mid": "wall_mid_1", "wall_r_mid": "wall_mid_2",
    "ledge_tr": "ledge_mid_1", "ledge_br": "ledge_mid_2",
    "ledge_tl": "ledge_mid_3", "ledge_bl": "ledge_mid_4",
    "wall_l_deep": "wall_deep_1", "wall_r_deep": "wall_deep_2",
    "wall_l_weed": "wall_deep_3", "wall_r_weed": "wall_deep_4",
    "sand_top": "sand_1", "sand_fill": "sand_2",
    "coral_a": "coral_1", "coral_b": "coral_2",
    "weed_0": "weed_1", "weed_1": "weed_2",
    "ruin_block": "ruins_1", "ruin_col": "ruins_2", "ruin_cap": "ruins_3",
    "pipe_h": "pipe_1", "pipe_v": "pipe_2",
    "anchor_top": "cable_anchor_1", "anchor_bot": "cable_anchor_2",
    "vent_0": "vent_1", "vent_1": "vent_2", "vent_2": "vent_3",
    "rim_l": "siphon_rim_1", "rim_r": "siphon_rim_2",
    "throat_top": "siphon_rim_3", "throat": "siphon_rim_4",
}

EK_PLAYER_START, EK_PICKUP, EK_HAZARD, EK_DOOR = 0, 4, 5, 6
EF_ACTIVE, EF_TOUCH, EF_SOLID = 1, 8, 4
PU_KEY, PU_AMMO, PU_MEDKIT, PU_OXYGEN = 0, 1, 2, 6
HZ_CABLE = 1                    # p0 of a hazard: WHICH hazard (8.6)
HZ_MAX = 8
ENT_MAX = 24
BAKE_LIMIT = 240                # ENT_BAKE's scratch tiles start here (8.6)

# THE CABLE'S FOUR CELS, out of the sheet's `off` and `spark` tags.
CABLE_CELS = ((0, False), (1, False), (0, False), (3, True))

# RG_OXYGEN is docs/editor.md 5.5's OxygenVent - the format's region
# kind 2, which nothing read until the sea (src/swim.asm).
RG_OXYGEN = 2


def tile_names():
    d = json.load(open(os.path.join(ART, "tile_table.json")))
    s = d["sheets"][0]
    assert s["sheet"] == "sea_tiles" and s["count"] == 42, s["sheet"]
    names = [t["name"] for t in s["tiles"]]
    t = {n: i for i, n in enumerate(names)}
    for a, n in ALIAS.items():
        t[a] = t[n]
    return names, t


class Bake:
    """The cables' composites, numbered from the end of the tileset in
    the order they are first placed - so every level of the sea SHARES
    them, because a tileset is the environment's (8.13)."""

    def __init__(self, names):
        self.names = names
        self.n = len(names)
        self.tiles, self.tile_boxes = sheet_frames(ART, TILES_SHEET)
        self.cable_sheet, self.cable_boxes = sheet_frames(ART, CABLE_SHEET)
        self.blob = bytearray()
        self.extra = []                     # (name, flags) per composite
        self.cables = {}                    # background -> its cel 0

    def _add(self, name, over, bg, flags):
        b = self.tile_boxes[bg]
        under = box_pens(self.tiles, b["x"], b["y"], b["w"], b["h"])
        pens = [[o if o is not None else u for o, u in zip(ro, ru)]
                for ro, ru in zip(over, under)]
        i = self.n + len(self.extra)
        assert i < BAKE_LIMIT, "the bake reached ENT_BAKE's scratch tiles"
        self.blob += encode_tile(pens)
        self.extra.append((name, flags))
        return i

    def cable(self, bg):
        """A cable segment over `bg`: cel 0's index, the other three
        after it."""
        if bg not in self.cables:
            first = None
            for c, (frame, live) in enumerate(CABLE_CELS):
                b = self.cable_boxes[frame]
                over = box_pens(self.cable_sheet, b["x"], b["y"], b["w"],
                                b["h"], alpha=True)
                i = self._add(f"cable_{c}_on_{self.names[bg]}", over, bg,
                              TILE_FLAGS.get(self.names[bg], 0)
                              | (HAZARD if live else 0))
                first = i if first is None else first
            self.cables[bg] = first
        return self.cables[bg]


# ---------------------------------------------------------------------
# THE COMPOSITION. Everything above is the artist's; everything in a
# LAYOUT is a designer's.
#
# `ledges` is (top row, side, length in tiles): two rows of rock out of
# the left wall ("L") or the right ("R"). `cables` is (column, the upper
# ledge's top row, the cel it starts on): anchor_top under that ledge,
# anchor_bot on the next, and the live segments between - so a cable
# stands in a CORRIDOR and cannot be swum round, only timed.
# ---------------------------------------------------------------------
LEVEL_13 = dict(
    level=13,
    about="the dive",
    # A LEDGE EVERY SEVEN ROWS, ALTERNATING SIDES: a corridor five rows
    # tall between each pair, entered by the gap at one end and left by
    # the gap at the other, so every one of them has to be CROSSED.
    # Five and not four, because a cable stands between two anchors and
    # her box is 24 lines: with four the gap past it was two rows - 32
    # lines - and the water lifting her a line every other frame put
    # her back into the anchor whenever she let go of DOWN. Three rows
    # is 48, and that is a cable a player times rather than threads.
    ledges=((16, "L", 18), (23, "R", 18), (30, "L", 18), (37, "R", 18),
            (44, "L", 18)),
    # (column, the upper ledge's row, the cel it starts on, how far
    # into it in quarters). Four phases chosen so that no two cables
    # ever change within two game frames of each other: a phase that is
    # only a starting cel gives every cable a boundary at the same
    # instant, and twelve cells changing at once is more than the
    # painter has room for (src/hazard.asm, 8.18).
    cables=((15, 16, 0, 0), (18, 23, 0, 2), (17, 30, 2, 3), (14, 37, 3, 2)),
    vents=((7, 29),),                       # (column, the row it stands in)
    rays=((5, 3), (14, 2), (22, 4), (9, 7), (26, 9)),
    floor_props=((4, "coral_a"), (9, "weed_0"), (14, "coral_b"),
                 (17, "weed_1")),
    ruins=(27, 5),                          # (left column, height) on the floor
    siphon=20,                              # rim_l's column
    start=(6, 2),                           # column, row of her box's top
    pickups=((24, 22, "ammo"), (5, 36, "oxygen"), (24, 43, "medkit"),
             (6, 61, "key"), (12, 61, "oxygen")),
    # THE SURFACE IS AIR, and so is the column of bubbles over a vent.
    # (left, top, width, height) in tiles.
    regions=((3, 2, 26, 1), (6, 27, 3, 2)),
)
LAYOUTS = (LEVEL_13,)


def build_map(t, L, bake):
    g = [[0] * MAP_W for _ in range(MAP_H)]
    for r in range(MAP_H):
        band = ("light" if r in LIGHT else "mid" if r in MID else "deep")
        for x in range(MAP_W):
            if x < WALL_L or x > WALL_R:
                g[r][x] = t["rock_fill"]
            elif x == WALL_L or x == WALL_R:
                side = "l" if x == WALL_L else "r"
                if band == "deep":
                    # the weed variant every third row, so the face is
                    # not one tile repeated down a whole screen
                    g[r][x] = t[f"wall_{side}_{'weed' if r % 3 == 0 else 'deep'}"]
                else:
                    g[r][x] = t[f"wall_{side}_{band}"]
            else:
                g[r][x] = t[f"bg_{band}"]
    for x in range(MAP_W):
        g[ROW_SKY][x] = t["rock_top"] if x <= WALL_L or x >= WALL_R else t["sky"]
        g[ROW_SURFACE][x] = (t["rock_fill"] if x <= WALL_L or x >= WALL_R
                             else t["surface_1"])
    for x, r in L["rays"]:
        g[r][WALL_L + 1 + x] = t["bg_ray"]

    # ---- the ledges ------------------------------------------------
    for r, side, n in L["ledges"]:
        assert r in MID and r + 1 in MID, f"a ledge at row {r} is not mid band"
        assert len(WATER) - n >= GAP_MIN, f"the gap past row {r}'s ledge"
        if side == "L":
            cols = range(WALL_L + 1, WALL_L + 1 + n)
            g[r][WALL_L] = g[r + 1][WALL_L] = t["rock_fill"]
            for x in cols:
                g[r][x], g[r + 1][x] = t["rock_top"], t["rock_under"]
            g[r][cols[-1]], g[r + 1][cols[-1]] = t["ledge_tr"], t["ledge_br"]
        else:
            cols = range(WALL_R - n, WALL_R)
            g[r][WALL_R] = g[r + 1][WALL_R] = t["rock_fill"]
            for x in cols:
                g[r][x], g[r + 1][x] = t["rock_top"], t["rock_under"]
            g[r][cols[0]], g[r + 1][cols[0]] = t["ledge_tl"], t["ledge_bl"]

    # ---- the floor, its props, the ruins and the siphon --------------
    for x in range(WALL_L, WALL_R + 1):
        g[ROW_SAND][x], g[ROW_FILL][x] = t["sand_top"], t["sand_fill"]
    for x, name in L["floor_props"]:
        g[ROW_SAND - 1][x] = t[name]
    left, h = L["ruins"]
    for r in range(ROW_SAND - h, ROW_SAND + 2):
        for x in range(left, left + 2):
            g[r][x] = t["ruin_block"]
    g[ROW_SAND - h - 1][left] = t["ruin_col"]
    g[ROW_SAND - h - 2][left] = t["ruin_cap"]
    s = L["siphon"]
    g[ROW_SAND][s], g[ROW_SAND][s + 5] = t["rim_l"], t["rim_r"]
    g[ROW_FILL][s], g[ROW_FILL][s + 5] = t["rock_fill"], t["rock_fill"]
    for x in range(s + 1, s + 5):
        g[ROW_SAND][x], g[ROW_FILL][x] = t["throat_top"], t["throat"]

    # ---- the vents, standing on a ledge or the floor -----------------
    for x, r in L["vents"]:
        assert g[r + 1][x] in (t["rock_top"], t["sand_top"]), \
            f"the vent at {x},{r} stands on nothing"
        g[r][x] = t["vent_0"]

    # ---- the cables, between two ledges -------------------------------
    # ONE RECORD A CABLE, and its length in p1's top nibble: the cells
    # BELOW its first (src/hazard.asm's HZ_WRITE). Every cell of the run
    # is the same composite, because a cable hangs in one band.
    hz = []
    for x, r, cel, quarter in L["cables"]:
        phase = cel | quarter << 2
        below = next(rr for rr, _, _ in L["ledges"] if rr > r)
        assert g[r + 1][x] == t["rock_under"], f"no ledge over the cable at {x}"
        assert g[below][x] == t["rock_top"], f"no ledge under the cable at {x}"
        g[r + 2][x] = t["anchor_top"]
        g[below - 1][x] = t["anchor_bot"]
        cells = range(r + 3, below - 1)
        assert 1 <= len(cells) <= 16
        assert len({g[rr][x] for rr in cells}) == 1, "a cable across two bands"
        cel0 = bake.cable(g[r + 3][x])
        for rr in cells:
            g[rr][x] = cel0
        hz.append((x, r + 3, phase | (len(cells) - 1) << 4, len(cells)))
    assert len(hz) <= HZ_MAX, f"{len(hz)} cables, HZ_MAX is {HZ_MAX}"
    return g, hz


def entity(kind, x_px, y_base, flags, p0=0, p1=0):
    return bytes([kind, x_px & 255, x_px >> 8, y_base & 255, y_base >> 8,
                  flags, p0, p1])


PICKUPS = {"key": (PU_KEY, 0), "ammo": (PU_AMMO, 14),
           "medkit": (PU_MEDKIT, 0), "oxygen": (PU_OXYGEN, 0)}


def build_entities(L, hz):
    """The records, in file order. Her start is given as the row of her
    box's TOP - she is 24 lines tall in the water and the record's y is
    the BASE (8.6) - and everything else is on the tile grid."""
    col, row = L["start"]
    recs = [entity(EK_PLAYER_START, col * 8, row * 16 + 24, EF_ACTIVE)]
    for x, row, kind in L["pickups"]:
        p0, p1 = PICKUPS[kind]
        recs.append(entity(EK_PICKUP, x * 8, (row + 1) * 16,
                           EF_ACTIVE | EF_TOUCH, p0, p1))
    # THE WAY OUT IS THE SIPHON, and it is a door with a lock like every
    # other way out of a level: the key opens it (8.6's CHECK_KEY_DOOR).
    s = L["siphon"]
    recs.append(entity(EK_DOOR, (s + 1) * 8, ROW_SAND * 16,
                       EF_ACTIVE | EF_SOLID, 0, PU_KEY))
    for x, r, p1, _ in hz:
        recs.append(entity(EK_HAZARD, x * 8, (r + 1) * 16, EF_ACTIVE,
                           HZ_CABLE, p1))
    assert len(recs) <= ENT_MAX, f"{len(recs)} records, ENT_MAX is {ENT_MAX}"
    return b"".join(recs)


def build_regions(L):
    out = bytearray()
    for x, y, w, h in L["regions"]:
        out += bytes([RG_OXYGEN, x & 255, x >> 8, y & 255, y >> 8, w, h])
    return bytes(out)


def reachable(g, t, flags):
    """Every cell her 4x2-tile box can occupy, flood-filled from where
    she starts, by whole tiles. She swims, so every direction is the
    same move - this is the sea's whole difference from the forest's
    reachable(): there is no gravity to model."""
    def free(c, r):
        return all(0 <= r + j < MAP_H and 0 <= c + i < MAP_W
                   and not flags[g[r + j][c + i]] & SOLID
                   for j in range(2) for i in range(4))
    return free


def checks(g, t, flags, L, hz):
    free = reachable(g, t, flags)
    col, row = L["start"]
    assert free(col, row), "she starts inside rock"
    seen, todo = {(col, row)}, [(col, row)]
    while todo:
        c, r = todo.pop()
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c + dc, r + dr)
            if n not in seen and free(*n):
                seen.add(n)
                todo.append(n)

    def touches(x, row):
        # a box of 4x2 tiles overlaps tile (x, row)
        return any((c, r) in seen for c in range(x - 3, x + 1)
                   for r in range(row - 1, row + 1))
    for x, prow, kind in L["pickups"]:
        assert touches(x, prow), f"the {kind} at {x},{prow} cannot be reached"
    s = L["siphon"]
    assert any(touches(x, ROW_SAND - 1) for x in range(s + 1, s + 5)), \
        "the siphon cannot be reached"
    # AND EVERY CABLE IS IN THE WAY. A cable a player can swim round is
    # scenery, so the fill is run again with each one's cells taken as
    # rock: the key must then be out of reach. One cable at a time, so
    # a cable that is bypassed is caught even when the others are not.
    key = next((x, row) for x, row, kind in L["pickups"] if kind == "key")
    for x, r, _, n in hz:
        wall = {(x, rr) for rr in range(r, r + n)}

        def free2(c, rr):
            return free(c, rr) and not any(
                (c + i, rr + j) in wall for j in range(2) for i in range(4))
        seen2, todo = {(col, row)}, [(col, row)]
        while todo:
            c, rr = todo.pop()
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (c + dc, rr + dr)
                if nb not in seen2 and free2(*nb):
                    seen2.add(nb)
                    todo.append(nb)
        kx, kr = key
        assert not any((c, rr) in seen2 for c in range(kx - 3, kx + 1)
                       for rr in range(kr - 1, kr + 1)), \
            f"the cable at column {x}, row {r} can be swum round"
    return len(seen)


def main():
    names, t = tile_names()
    bake = Bake(names)
    built = []
    for L in LAYOUTS:
        g, hz = build_map(t, L, bake)
        built.append((L, g, hz))

    flags = bytes(TILE_FLAGS.get(n, 0) for n in names)
    flags += bytes(f for _, f in bake.extra)
    out = os.path.join(BUILD, "tileflags_level4_underwater.bin")
    open(out, "wb").write(flags)
    print(f"-> tileflags_level4_underwater.bin  {len(flags)} tiles, "
          f"{sum(1 for f in flags if f)} with anything on")

    # THE BLOB IS TRUNCATED TO THE TILESET'S OWN TILES FIRST, so running
    # this twice bakes the same cels rather than stacking a second copy
    # - the rule every map tool here keeps, for the same reason.
    tiles = os.path.join(BUILD, "levels", "level4_underwater", "seatiles.bin")
    base = open(tiles, "rb").read()[:64 * len(names)]
    assert len(base) == 64 * len(names), "the tile blob is short"
    open(tiles, "wb").write(base + bytes(bake.blob))
    from build_levels import zx0
    zx0(tiles)
    print(f"-> seatiles.bin  {len(names)} tiles + {len(bake.extra)} baked "
          f"({len(bake.cables)} cable set(s) of {len(CABLE_CELS)}) = "
          f"{len(base) + len(bake.blob)} bytes")

    for L, g, hz in built:
        reach = checks(g, t, flags, L, hz)
        ents = build_entities(L, hz)
        regions = build_regions(L)
        m = bytes(b for row in g for b in row)
        lvl = pack(level_id=L["level"], tileset_id=TILESET_ID,
                   width=MAP_W, height=MAP_H, map_bytes=m, entities=ents,
                   flags=SCROLL_V | UNDERWATER, regions=regions)
        out = os.path.join(BUILD, f"level_{L['level']}.lvl")
        open(out, "wb").write(lvl)
        back = read(lvl)
        assert back["map"] == m and back["entities"] == len(ents) // 8
        assert back["regions"] == len(L["regions"])
        print(f"-> level_{L['level']}.lvl    {len(lvl)} bytes: {MAP_W}x"
              f"{MAP_H}, underwater, {back['entities']} entities, "
              f"{len(hz)} cables of {sum(h[3] for h in hz)} cells, {back['regions']} air regions, "
              f"tileset {TILESET_ID} - {L['about']}; {reach} places her "
              f"box can be")
    return 0


if __name__ == "__main__":
    sys.exit(main())
