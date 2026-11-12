#!/usr/bin/env python3
"""The space station's maps: levels 21 to 24, the last environment.
CLAUDE.md 8.23.

THE ARTIST COMPOSED IT AND THIS TOOL ONLY LAYS IT OUT. The sheet's own
description names every tile by tag ("Frame order per tag: bg_far =
space_a, space_b, ...") and tile_table.json gives the same tags in the
same order, so the names are read out of the one and checked against the
other. Rows, as the mockups have them:

    row  0     the ceiling, with its lights
    rows 1-7   the back wall: blue panels, pillars, and windows on space
    row  8     the wall's foot
    row  9     THE FLOOR - the forest's row, for the camera's reason
    rows 10+   the hull

PLAN.MD'S STATION IS LASER TRAPS AND KEYCARDS, and both are machinery
the engine already has:

* A LASER IS A TRAP (8.17): a column of cells from an emitter in a
  bulkhead's ceiling to one in the floor, whose tile goes round off,
  on, on, on - HZ_LASER, the fourth kind, 20 game frames off and 30 on,
  the artist's 0.8 s and 1.2 s. The on cels carry TA_HAZARD, so the
  bite is HAZARD_HURT's as it is the spikes'; it cannot be jumped, only
  timed.
* A KEYCARD DOOR IS AN ALTAR (8.17): the reader beside it is a
  receptacle that takes a key, and every cell around it whose tile
  carries TA_ADVANCE moves on to the next index - the reader to its lit
  picture and the door's four shut tiles to its open ones, which carry
  no TA_SOLID. So an inner door opens without the level ending; the
  door at the END is an EK_DOOR, as every level's way out is.
* A KEYCARD IS A KEY. PU_KEY, drawn out of the station's own pickup
  sheet (src/entity.asm's ENT_ART_OVER).

THE COMPUTER AT THE END IS A PICTURE, like the shuttle (8.22): one cel
baked over the wall, and the way out of level 24 is its EK_DOOR - the
last door in the game.

THE CYBER-ILLUMINATI GUARD IS NOT HERE: 24x64, agent class (CLAUDE.md 9).
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
BUILD = os.path.join(ROOT, "build")
sys.path.insert(0, HERE)
from make_level import pack, read                              # noqa: E402
from tilebake import box_pens, encode_tile, sheet_frames       # noqa: E402

ART = os.path.join(ROOT, "assets", "sprites", "level6_station")
TILES_SHEET = "station_tiles_cpc_mode0_sheet"
LASER_SHEET = "station_laser_cpc_mode0_sheet"
COMPUTER_SHEET = "station_computer_cpc_mode0_sheet"

MAP_W, MAP_H = 128, 16
TILESET_ID = 6                  # environment 6, levels 21-24
ROW_CEIL, ROW_FLOOR = 0, 9
BULK = 4                        # a bulkhead's ceiling comes down to here

SOLID, PLATFORM, HAZARD, ADVANCE = 1, 2, 4, 128
EK_PLAYER_START, EK_PICKUP, EK_HAZARD, EK_DOOR, EK_RECEPTACLE = 0, 4, 5, 6, 7
EF_ACTIVE, EF_SOLID, EF_TOUCH = 1, 4, 8
PU_KEY, PU_MEDKIT = 0, 2
HZ_LASER = 3
ENT_MAX, HZ_MAX = 24, 16
BAKE_LIMIT = 240

TILE_FLAGS = {
    "ceiling": SOLID, "ceiling_light": SOLID, "emit_ceiling": SOLID,
    "hull": SOLID,
    # THE FLOOR IS A PLATFORM, and so is a catwalk: one tile, one flag
    # set, and a platform is a floor from above (CLAUDE.md 8.8).
    "floor_l": PLATFORM, "floor_m": PLATFORM, "floor_r": PLATFORM,
    "emit_floor": PLATFORM,
    # the exit's door is an EK_DOOR and carries nothing (8.8); the inner
    # doors' tiles are the pairs baked below
}


def tile_names():
    """The sheet's description names the frames tag by tag; the tile
    table carries the same tags in the same order. Both are read."""
    man = json.load(open(os.path.join(ART, "manifest.json")))
    sheet = next(s for s in man["sheets"] if s["name"] == "station_tiles")
    order = sheet["description"].split("Frame order per tag:", 1)[1]
    order = order.split(". ", 1)[0]
    table = json.load(open(os.path.join(ART, "tile_table.json")))
    rows = next(s for s in table["sheets"] if s["sheet"] == "station_tiles")
    names = {}
    by_tag = {}
    for part in order.split(";"):
        tag, members = part.split("=")
        by_tag[tag.strip()] = [m.strip() for m in members.split(",")]
    seen = {}
    for t in rows["tiles"]:
        k = seen.get(t["tag"], 0)
        seen[t["tag"]] = k + 1
        names[by_tag[t["tag"]][k]] = t["index"]
    assert all(len(v) == seen[k] for k, v in by_tag.items()), \
        "the description and the table disagree on a tag's count"
    return names


class Bake:
    """What the station's levels composite, numbered after its tileset:
    the laser's four cels over the wall, the inner doors' shut and open
    tiles in PAIRS at consecutive indexes, and the computer."""

    def __init__(self, t):
        self.t = t
        self.n = len(t)
        self.tiles, self.boxes = sheet_frames(ART, TILES_SHEET)
        self.blob = bytearray()
        self.extra = []

    def pens(self, name):
        b = self.boxes[self.t[name]]
        return box_pens(self.tiles, b["x"], b["y"], b["w"], b["h"])

    def add(self, label, pens, flags):
        i = self.n + len(self.extra)
        assert i < BAKE_LIMIT, "the bake reached ENT_BAKE's scratch tiles"
        self.blob += encode_tile(pens)
        self.extra.append((label, flags))
        return i

    def laser(self):
        """Cel 0 off, 1 on, 2 the flicker, 3 on again - the column's own
        tile is 'wall', so one set serves every laser in the game. The
        sheet is a TILE sheet, so pen 0 is its transparency (7.3)."""
        sheet, boxes = sheet_frames(ART, LASER_SHEET)
        under = self.pens("wall")
        base = None
        for cel, frame, flags in ((0, 5, 0), (1, 3, HAZARD), (2, 4, HAZARD),
                                  (3, 3, HAZARD)):
            b = boxes[frame]
            over = box_pens(sheet, b["x"], b["y"], 8, 16)
            pens = [[o if o else u for o, u in zip(ro, ru)]
                    for ro, ru in zip(over, under)]
            i = self.add(f"laser_{cel}", pens, flags)
            base = i if base is None else base
        return base

    def door(self):
        """Four pairs, (shut, open): the shut one carries TA_ADVANCE and
        TA_SOLID, its open one is the next index and carries nothing - the
        head excepted, which is a lintel either way."""
        out = {}
        for part, shut, open_, after in (
                ("head", "door_head_shut", "door_head_open", SOLID),
                ("top", "door_shut_top", "door_open_mid", 0),
                ("mid", "door_shut_mid", "door_open_mid", 0),
                ("bot", "door_shut_bot", "door_open_bot", 0)):
            out[part] = self.add(f"{shut}_pair", self.pens(shut),
                                 SOLID | ADVANCE)
            self.add(f"{open_}_pair", self.pens(open_), after)
        return out

    def computer(self):
        """The computer's idle cel, 4 x 3 tiles, over the wall."""
        sheet, boxes = sheet_frames(ART, COMPUTER_SHEET)
        b = boxes[0]
        under = self.pens("wall")
        out = {}
        for r in range(3):
            for c in range(4):
                over = box_pens(sheet, b["x"] + c * 8, b["y"] + r * 16, 8, 16,
                                alpha=True)
                pens = [[o if o is not None else u for o, u in zip(ro, ru)]
                        for ro, ru in zip(over, under)]
                out[(c, r)] = self.add(f"computer_{c}{r}", pens, 0)
        return out


# ---------------------------------------------------------------------
# THE COMPOSITION, one entry a level. Every number is a TILE column.
#
#   windows   (left, width): a window on space, rows 1-7
#   pillars   columns of a pillar, rows 1-8
#   catwalks  (left, length, row) of floor - a platform
#   consoles  left columns of a 2x2 console standing on the floor
#   lasers    (column, head start in quarters of its cycle): a bulkhead
#             over rows 0-4, the emitter at row 4, the beam rows 5-8
#   doors     columns of an inner keycard door; its reader is the column
#             to its left
#   keys      (column, the row it stands ON) of a keycard
#   medkits   the same, of a medkit
#   exit      the column of the door the level leaves by
# ---------------------------------------------------------------------
LEVEL_21 = dict(
    level=21, about="the airlock",
    start=4, windows=((10, 6), (40, 8), (86, 6)), pillars=(8, 18, 38, 50, 84),
    catwalks=(), consoles=(26, 72),
    lasers=((32, 0), (60, 1)), doors=(80,),
    keys=((46, 9), (100, 9)), medkits=(), exit=120, computer=None,
)
LEVEL_22 = dict(
    level=22, about="the labs",
    start=4, windows=((14, 10), (84, 10)), pillars=(12, 26, 66, 82, 104),
    catwalks=((36, 6, 7), (90, 6, 7)), consoles=(24, 56, 96),
    lasers=((30, 0), (50, 1), (76, 0), (110, 1)), doors=(62, 116),
    keys=((38, 7), (92, 7), (120, 9)), medkits=(70,), exit=124,
    computer=None,
)
LEVEL_23 = dict(
    level=23, about="the reactor",
    start=4, windows=((6, 10), (26, 8), (66, 6), (88, 10)),
    pillars=(8, 24, 58, 68, 94),
    catwalks=((28, 4, 7), (34, 4, 5), (70, 5, 7), (76, 5, 5)),
    consoles=(46, 100),
    lasers=((20, 0), (42, 1), (52, 0), (86, 1), (108, 0)), doors=(64, 114),
    keys=((36, 5), (80, 5), (119, 9)), medkits=(48,), exit=124,
    computer=None,
)
LEVEL_24 = dict(
    level=24, about="the computer",
    start=4, windows=((4, 10), (40, 10), (70, 12), (92, 6)),
    pillars=(10, 22, 46, 58, 82),
    catwalks=((26, 6, 7), (66, 6, 7)), consoles=(22, 84),
    lasers=((18, 0), (36, 1), (54, 0), (90, 1), (100, 0)), doors=(62, 104),
    keys=((30, 7), (68, 7), (96, 9)), medkits=(44,), exit=None,
    computer=114,
)
LAYOUTS = (LEVEL_21, LEVEL_22, LEVEL_23, LEVEL_24)


SPACE = ("space_a", "space_b", "space_c")


def build_map(t, L, bake, laser0, door, comp):
    g = [[t["hull"]] * MAP_W for _ in range(MAP_H)]
    for x in range(MAP_W):
        g[ROW_CEIL][x] = t["ceiling_light" if x % 8 == 3 else "ceiling"]
        for r in range(1, 8):
            g[r][x] = t["wall_seam" if x % 6 == 0 else "wall"]
        g[3][x] = t["wall_pipe"] if x % 6 else g[3][x]
        g[8][x] = t["wall_stripe"]
        g[ROW_FLOOR][x] = t["floor_m"]
    # an irregular mix of stars, so the windows are not a grid (the notes)
    for left, w in L["windows"]:
        for x in range(left, left + w):
            col = [t["win_top"]]
            for r in range(3):
                col.append(t[SPACE[(x * 7 + r * 3 + left) % 3]])
            col += [t["space_rim"], t["space_planet"], t["win_bot"]]
            for r, tile in enumerate(col):
                g[1 + r][x] = tile
    for x in L["pillars"]:
        g[1][x] = t["pillar_top"]
        for r in range(2, 8):
            g[r][x] = t["pillar_mid"]
        g[8][x] = t["pillar_base"]
    for x in L["consoles"]:
        g[7][x], g[7][x + 1] = t["console_tl"], t["console_tr"]
        g[8][x], g[8][x + 1] = t["console_bl"], t["console_br"]
    for x, n, row in L["catwalks"]:
        for i in range(n):
            g[row][x + i] = t["floor_l" if i == 0 else
                              "floor_r" if i == n - 1 else "floor_m"]

    def bulkhead(c, w):
        for x in range(c, c + w):
            for r in range(1, BULK + 1):
                g[r][x] = t["ceiling"]

    # ---- the lasers: a bulkhead, its emitters, the beam over the wall --
    for c, _ in L["lasers"]:
        bulkhead(c - 1, 3)
        g[BULK][c] = t["emit_ceiling"]
        for r in range(BULK + 1, ROW_FLOOR):
            g[r][c] = laser0                # cel 0, off: the pristine image
        g[ROW_FLOOR][c] = t["emit_floor"]
    # ---- the inner doors: the reader on the wall beside each ----------
    for c in L["doors"]:
        bulkhead(c, 1)
        g[BULK][c] = door["head"]
        g[5][c] = door["top"]
        g[6][c] = g[7][c] = door["mid"]
        g[8][c] = door["bot"]
        for r in range(BULK, 9):
            g[r][c - 1] = t["wall"]
        g[7][c - 1] = t["reader_locked"]
    # ---- the way out: the door, or the computer -----------------------
    if L["exit"] is not None:
        c = L["exit"]
        bulkhead(c, 1)
        g[BULK][c] = t["door_head_shut"]
        g[5][c] = t["door_shut_top"]
        g[6][c] = g[7][c] = t["door_shut_mid"]
        g[8][c] = t["door_shut_bot"]
    if L["computer"] is not None:
        c = L["computer"]
        for r in range(3):
            for i in range(4):
                g[6 + r][c + i] = comp[(i, r)]
    return g


def entity(kind, x_px, y_base, flags, p0=0, p1=0):
    return bytes([kind, x_px & 255, x_px >> 8, y_base & 255, y_base >> 8,
                  flags, p0, p1])


def build_entities(L):
    floor = ROW_FLOOR * 16
    recs = [entity(EK_PLAYER_START, L["start"] * 8, floor - 16, EF_ACTIVE)]
    for x, row in L["keys"]:
        recs.append(entity(EK_PICKUP, x * 8, row * 16, EF_ACTIVE | EF_TOUCH,
                           PU_KEY, 1))
    for x in L["medkits"]:
        recs.append(entity(EK_PICKUP, x * 8, floor, EF_ACTIVE | EF_TOUCH,
                           PU_MEDKIT))
    for c in L["doors"]:                    # the reader: wants one key
        recs.append(entity(EK_RECEPTACLE, (c - 1) * 8, floor, EF_ACTIVE,
                           PU_KEY, 1))
    for i, (c, head) in enumerate(L["lasers"]):
        # three cells below its own: the beam is four tiles, her height
        recs.append(entity(EK_HAZARD, c * 8, (BULK + 2) * 16, EF_ACTIVE,
                           HZ_LASER, 3 << 4 | (head & 3) << 2))
    if L["exit"] is not None:
        recs.append(entity(EK_DOOR, (L["exit"] - 1) * 8, floor,
                           EF_ACTIVE | EF_SOLID, 0, PU_KEY))
    else:
        recs.append(entity(EK_DOOR, L["computer"] * 8, floor,
                           EF_ACTIVE | EF_SOLID, 0, PU_KEY))
    assert len(recs) <= ENT_MAX
    assert len(L["lasers"]) <= HZ_MAX
    return b"".join(recs)


def checks(g, t, L, flags):
    """THE KEYS COME BEFORE THE DOORS. Walking left to right, every door
    she meets - each reader, and the way out last - must find a key in
    her pocket that no earlier door took; and every key must stand
    somewhere she can stand, which on this floor is the floor or a
    catwalk reachable from it."""
    held = 0
    events = sorted([(x, "key") for x, _ in L["keys"]]
                    + [(c, "door") for c in L["doors"]]
                    + [(L["exit"] if L["exit"] is not None
                        else L["computer"], "door")])
    for x, what in events:
        held += 1 if what == "key" else -1
        assert held >= 0, f"level {L['level']}: a door at {x} with no key"
    # NOTHING IS BUILT THROUGH A BULKHEAD, a door or the way out: a
    # window behind a beam would put the beam over space, and its
    # composite is over the wall; a catwalk through one would be cut by
    # the beam's cells.
    fixed = set()
    for c, _ in L["lasers"]:
        fixed |= {c - 1, c, c + 1}
    for c in L["doors"]:
        fixed |= {c - 2, c - 1, c}
    for c in (L["exit"], L["computer"]):
        if c is not None:
            fixed |= set(range(c - 1, c + 5))
    for left, wd in L["windows"]:
        assert not fixed & set(range(left, left + wd)), \
            f"level {L['level']}: a window at {left} meets a bulkhead"
    for cx, cn, _ in L["catwalks"]:
        # ... AND NONE ENDS AGAINST ONE. A bulkhead's ceiling comes down
        # to row 4, so at a catwalk's height it is a wall: a catwalk that
        # stops a tile short of one leaves her standing on its end, her
        # box still over it, unable to walk on or to fall off - level
        # 24's first draft, which the suite's drive found.
        near = set(range(cx - 3, cx + cn + 3))
        assert not fixed & near, \
            f"level {L['level']}: a catwalk at {cx} meets a bulkhead"
    # TWO LASERS THAT CAN BE ON THE SCREEN TOGETHER DO NOT CHANGE
    # TOGETHER. A laser changes cel every ten game frames from the start
    # of its cycle, and a head start moves that by quarters of its first
    # cel - five frames - so an odd difference never meets and an even one
    # always does. Two beams changing at once are eight cells, against the
    # seven the passes before the strip and in the head gate's wait have
    # room for: the eighth was a cel behind the map for a frame, level 23's
    # first draft, which the suite's picture check found. Two screens and
    # not one, because the beams OFF the screen were on the painter's
    # list as well; since they are not (hazard.asm's .off, CLAUDE.md
    # 8.23) one screen would do, and the margin costs no level anything.
    lz = L["lasers"]
    for (c1, h1), (c2, h2) in zip(lz, lz[1:]):
        assert c2 - c1 >= 40 or (h1 - h2) % 2, \
            f"level {L['level']}: the lasers at {c1} and {c2} change together"
    for x, row in L["keys"]:
        if row == ROW_FLOOR:
            assert x not in fixed, f"level {L['level']}: a key at {x}"
            continue
        on = [(cx, cn, cr) for cx, cn, cr in L["catwalks"]
              if cr == row and cx <= x < cx + cn]
        assert on, f"level {L['level']}: a key at {x}, row {row}, on air"
        # two rows above the floor, or two above a catwalk she can reach
        # from it within three tiles - her jump (CLAUDE.md 8.11)
        cx, cn, cr = on[0]
        assert cr == ROW_FLOOR - 2 or any(
            r2 == cr + 2 and c2 - 3 <= cx + cn and cx - 3 <= c2 + n2
            for c2, n2, r2 in L["catwalks"]), \
            f"level {L['level']}: a key at {x}, row {row}, out of reach"
    for c, _ in L["lasers"]:
        assert all(g[r][c] == g[BULK + 1][c] for r in range(BULK + 1, 9))
    return held


def main():
    t = tile_names()
    bake = Bake(t)
    laser0 = bake.laser()
    door = bake.door()
    comp = bake.computer()
    built = [(L, build_map(t, L, bake, laser0, door, comp)) for L in LAYOUTS]

    names = sorted(t.items(), key=lambda kv: kv[1])
    TILE_FLAGS["reader_locked"] = ADVANCE   # ... and reader_ok is next
    flags = bytes(TILE_FLAGS.get(n, 0) for n, _ in names)
    flags += bytes(f for _, f in bake.extra)
    open(os.path.join(BUILD, "tileflags_level6_station.bin"), "wb").write(flags)
    print(f"-> tileflags_level6_station.bin  {len(flags)} tiles, "
          f"{sum(1 for f in flags if f)} with anything on")

    tiles = os.path.join(BUILD, "levels", "level6_station", "stationtiles.bin")
    base = open(tiles, "rb").read()[:64 * len(t)]
    assert len(base) == 64 * len(t), "the tile blob is short"
    open(tiles, "wb").write(base + bytes(bake.blob))
    from build_levels import zx0
    zx0(tiles)
    print(f"-> stationtiles.bin  {len(t)} tiles + {len(bake.extra)} baked "
          f"= {len(base) + len(bake.blob)} bytes")

    for L, g in built:
        ents = build_entities(L)
        left = checks(g, t, L, flags)
        m = bytes(b for row in g for b in row)
        lvl = pack(level_id=L["level"], tileset_id=TILESET_ID,
                   width=MAP_W, height=MAP_H, map_bytes=m, entities=ents)
        open(os.path.join(BUILD, f"level_{L['level']}.lvl"), "wb").write(lvl)
        back = read(lvl)
        assert back["map"] == m and back["entities"] == len(ents) // 8
        print(f"-> level_{L['level']}.lvl    {len(lvl)} bytes: {MAP_W}x"
              f"{MAP_H}, {back['entities']} entities, {len(L['lasers'])} "
              f"lasers, {len(L['doors'])} keycard doors, "
              f"{len(L['keys'])} keycards ({left} spare), tileset "
              f"{TILESET_ID} - {L['about']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
