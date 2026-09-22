#!/usr/bin/env python3
"""The entity table, the AABB and the five handlers of CLAUDE.md 8.6.

Two things are being checked and they are different questions.

THE RECORD IS THE LEVEL FILE'S RECORD - docs/editor.md 9.2 fixes an
entity at eight bytes, kind/x/y/flags/p0/p1, and module 6's loader is
meant to be an LDIR. So the test builds records the way a file would
and pokes them straight into the table; if the engine needed a
conversion, that would fail here rather than in a web application
written against the format later.

THE HANDLERS SPEND THINGS. A key opens one door, an altar takes one
idol, an informant is paid once. Every one of those is a state change
that has to happen exactly once, so each is driven twice.
"""
import os
import re
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import boot, symbols, sync                        # noqa: E402

STUB = 0xA000
EK_PLAYER_START, EK_CHECKPOINT, EK_ENEMY, EK_NPC = 0, 1, 2, 3
EK_PICKUP, EK_HAZARD, EK_DOOR, EK_RECEPTACLE = 4, 5, 6, 7
EF_ACTIVE, EF_TAKEN, EF_SOLID, EF_TOUCH = 1, 2, 4, 8
PU_KEY, PU_AMMO, PU_MEDKIT, PU_COIN, PU_IDOL, PU_BOOK = range(6)
(ER_NOTHING, ER_TOOK, ER_HEALED, ER_OPENED, ER_LOCKED, ER_PLACED,
 ER_WRONG, ER_EMPTY, ER_TOLD, ER_POOR, ER_FULL) = range(11)
ER_NAME = "nothing took healed opened locked placed wrong empty told poor full".split()
IN_UP = 1
ENT_STRIDE, ENT_MAX = 8, 24
# kind -> (width in bytes, height in lines), from ENT_HITBOX
HITBOX = {EK_PICKUP: (4, 16), EK_DOOR: (16, 80), EK_RECEPTACLE: (4, 16),
          EK_NPC: (6, 64), EK_ENEMY: (6, 64), EK_CHECKPOINT: (4, 16),
          EK_PLAYER_START: (6, 64), EK_HAZARD: (4, 16)}
# Her collision box. KARA_WX / KARA_WY ARE THIS BOX, not her sprite -
# the sprite is 12 bytes wide, the box is centred in it, and the drawer
# takes the difference off (src/collide.asm). So the model below needs
# no offset at all; what it needs is the right height, and 64 is it.
KARA_W, KARA_H = 6, 64

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def record(kind, x_px, y_px, flags, p0=0, p1=0):
    """The eight bytes a level file holds, little-endian like the file."""
    return bytes([kind, x_px & 255, x_px >> 8, y_px & 255, y_px >> 8,
                  flags, p0, p1])


class World:
    def __init__(self, m, sym):
        self.m, self.sym = m, sym

    def load(self, *records):
        """Write a table, AND say how long it is.

        ENT_COUNT is the level header's entity count (editor.md 9.2) and
        the scan stops there - walking all 24 slots cost 4,004 T a frame
        with six in use. A test that writes the table by hand has to
        write the count too, exactly as module 6's loader will.
        """
        blob = b"".join(records)
        blob += bytes(ENT_MAX * ENT_STRIDE - len(blob))
        self.m.write_ram(self.sym["ENT_TABLE"], blob)
        self.m.poke(self.sym["ENT_COUNT"], ENT_MAX)
        self.m.poke(self.sym["ENT_BAKED"], 0)   # no scenery to put back

    def place(self, wx, wy):
        self.m.poke(self.sym["KARA_WX"], wx & 255)
        self.m.poke(self.sym["KARA_WX"] + 1, wx >> 8)
        self.m.poke(self.sym["KARA_WY"], wy)

    def run(self, routine, up=False, mask=0, frame=3):
        """Call one routine from a DI stub.

        `mask` goes into A, which ENTITY_COLLISION_CHECK reads as the
        EF_ bits an entity must have. Leaving it to whatever was in the
        register made the sweep below miss everything it should have
        hit - the test's own bug, and the first place to look when a
        register-argument routine disagrees with a model.
        """
        s, m = self.sym, self.m
        # THE DEFAULT IS THE SWEEP'S OWN FRAME AND IT HAS MOVED ONCE:
        # the sweep is one frame in FOUR now (FRAME_COUNT AND 3 == 3),
        # so a default of 1 stopped sweeping and eleven checks below
        # reported that no pickup goes into any counter. The default has
        # to travel with the gate.
        # ENT_UPDATE's TOUCH sweep runs on ODD frames only - it shares
        # the frame budget with the enemy redraw, which takes the even
        # ones (src/enemy.asm). A test that did not say which it wanted
        # would pass or fail on the parity of whatever ran before it.
        #
        # IT WAS THE EVEN ONES AND THE PHASE IS NOT ARBITRARY ANY MORE:
        # she steps on the even frames and CAMERA_DECIDE asks for the
        # scroll there, so H_HEAD paints fourteen rows of the incoming
        # column on that frame and H_TAIL's six land on the odd one.
        # 13,872 T against 4,920, and the sweep belongs with the
        # cheaper half - measured, it is 3 loop iterations in 200
        # walking and 7 running (CLAUDE.md 9).
        m.poke(s["FRAME_COUNT"], frame)
        m.poke(s["INPUT_PRESSED"], IN_UP if up else 0)
        m.poke(s["INPUT_NOW"], IN_UP if up else 0)
        a = s[routine]
        code = bytes([0xF3, 0x3E, mask, 0xCD, a & 0xFF, a >> 8, 0x18, 0xFE])
        m.write_ram(STUB, code)
        m.set_pc(STUB)
        for _ in range(60000):
            m.run_us(1)
            if m.pc == STUB + 6:
                return
        raise SystemExit(f"{routine} ran away")

    def st(self, name):
        return self.m.peek(self.sym[name])

    def flags(self, i):
        return self.m.peek(self.sym["ENT_TABLE"] + i * ENT_STRIDE + 5)

    def result(self):
        return self.m.peek(self.sym["ENT_RESULT"])

    def give(self, **kw):
        for k, v in kw.items():
            self.m.poke(self.sym[k], v)


def overlaps(kx, ky, kind, ex_px, ey_px):
    """The model: her box against the entity's, base-anchored."""
    ew, eh = HITBOX[kind]
    ex = ex_px >> 1
    etop = (ey_px - eh) & 0xFF
    return (kx < ex + ew and ex < kx + KARA_W
            and ky < etop + eh and etop < ky + KARA_H)


ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LEV = os.path.join(ROOT, "build", "levels")
MAP_ADDR, MAP_W = 0xA000, 128
TILE_BYTES, TILE_W, TILE_H = 64, 4, 16
BAKE_ADDR, BAKE_TILE0, BAKE_STRIDE = 0x7C00, 240, 5
# ENT_ART, the same table src/entity.asm holds: PU_* -> blob and cel.
ART = {PU_KEY:    ("level1_city/citypickups", "KEY"),
       PU_AMMO:   ("level1_city/citypickups", "AMMO"),
       PU_MEDKIT: ("_shared/hudicon", "HEART"),
       PU_COIN:   ("_shared/hudicon", "COIN"),
       PU_IDOL:   ("_shared/hudicon", "IDOL"),
       PU_BOOK:   ("_shared/hudicon", "BOOK")}


def blob_cel(path, tag):
    """(blob bytes, the cel index its FIRST frame has) for one tag."""
    data = open(os.path.join(LEV, path + ".bin"), "rb").read()
    name = os.path.basename(path).upper()
    first = None
    for line in open(os.path.join(LEV, path + ".inc")):
        if line.startswith(f"{name}_{tag}_FIRST"):
            first = int(line.split()[-1])
    if first is None:
        raise SystemExit(f"{path}.inc has no {tag} tag")
    return data, first


def stamp(blob, cel, tile):
    """The model: one span frame composited into a column-major tile.

    Deliberately NOT a copy of ENT_STAMP - it indexes the tile the way
    CLAUDE.md 9 writes the layout down, char_column * 32 + line * 2 +
    byte, and walks the span format the way test_spans.py does. If the
    Z80 and this agree, two independent readings of the format agree.
    """
    out = bytearray(tile)
    off = blob[2 * cel] | (blob[2 * cel + 1] << 8)
    y, p = blob[off], off + 2
    skip = 0
    while True:
        nlines = blob[p]
        if nlines == 0:
            break
        count = blob[p + 1]
        dskip = blob[p + 2] | (blob[p + 3] << 8)
        p += 4
        if count:
            skip += dskip - 65536 if dskip > 32767 else dskip
        for _ in range(nlines):
            for b in range(count):
                mask, data = blob[p], blob[p + 1]
                p += 2
                x = skip + b
                i = (x >> 1) * 32 + y * 2 + (x & 1)
                out[i] = (out[i] & mask) | data
            y += 1
    return bytes(out)


def peek_c4(m, sym, addr, n):
    """n bytes of bank C4 - read_ram() ignores banking, so the machine
    has to move them into base RAM itself. &9300 is inside the level
    staging buffer, free once the level has loaded."""
    m.run_code(0x8000, bytes([
        0x01, 0xC4, 0x7F, 0xED, 0x49,
        0x21, addr & 0xFF, addr >> 8, 0x11, 0x00, 0x93,
        0x01, n & 0xFF, n >> 8, 0xED, 0xB0,
        0x01, 0xC0, 0x7F, 0xED, 0x49, 0x18, 0xFE]))
    out = bytes(m.read_ram(0x9300, n))
    m.set_pc(sym["WAIT_VSYNC"])
    return out


def screen_cell(m, sym, col, row):
    """The 64 bytes of one map cell, read back off the DISPLAY.

    Same masked-word model as CLAUDE.md 6.4 - the point is to check
    what the CRTC is actually showing, not what the map says.
    """
    wx, wcr = m.peek(sym["WORLD_X"]), m.peek(sym["WORLD_CR"])
    scroll = m.peek(sym["SCROLL"]) | (m.peek(sym["SCROLL"] + 1) << 8)
    out = bytearray(TILE_BYTES)
    for cc in range(2):
        sc = (col * 2 + cc - wx) & 0xFF
        for line in range(TILE_H):
            sr = (row * 2 + (line >> 3) - wcr) & 0xFF
            if sc >= 40 or sr >= 24:
                return None
            word = (scroll + sr * 40 + sc) & 0x3FF
            a = 0xC000 + word * 2 + (line & 7) * 0x800
            out[cc * 32 + line * 2] = m.peek(a)
            out[cc * 32 + line * 2 + 1] = m.peek(a + 1)
    return bytes(out)


def quiet_the_enemies(m, sym):
    """Take the level's drones off the screen and leave them off.

    They are a PERSISTENT sprite - drawn once and left there between
    refreshes (src/enemy.asm) - so anything comparing video RAM against
    the tilemap has to either model them or remove them, and these
    checks are about pickups. Clearing ENEMY_LIVE makes ENEMY_PICK find
    nobody; the refresh that follows lifts the last one off.
    """
    m.poke(sym["ENEMY_LIVE"], 0)
    m.run_frames(3)


def every_kind_checks(sym):
    """Every PU_*, and not only the four this level happens to carry.

    The City places a key, an ammo clip, a medkit and a coin, and their
    art is cels 0 and 1 of citypickups and cels 0 and 4 of hudicon -
    all near the FRONT of their blobs. A designer can drop any of the
    six anywhere, so the other two had never been baked by anything,
    and one of them hung the machine.

    PU_BOOK is hudicon's cel 7, second from LAST in a nine-cel blob.
    ENT_FRAME_COPY kept both its counters in BC and copied with LDI,
    which decrements BC: it over-copied every frame it was ever given,
    ran off the end of the blob on the last two, and never met a
    terminator. One book pickup in a level therefore hung MAP_INSTALL
    before the first frame - and NOTHING in this suite could see it,
    because the check above walks the level's own pickups.

    Measured on the shipped build with the record poked into the table,
    ENT_BAKE called from a DI stub:

        before        key 129,742 us, idol 129,230, BOOK NEVER RETURNED
        after          key  36,769 us, idol  36,085, book  35,419

    The three-and-a-half times is the over-copy: 83 bytes of frame,
    2,545 bytes written.
    """
    print("\n  ... and every kind of pickup, not just the level's four:")
    m = boot(sym, scroll=True)
    quiet_the_enemies(m, sym)
    tiles = open(os.path.join(LEV, "level1_city", "citytiles.bin"), "rb").read()

    # A cell no pickup of the level's own was baked into, so what it
    # holds is a real tile index and not a scratch one.
    col, row = 100, 5
    cell = MAP_ADDR + row * MAP_W + col
    was = m.peek(cell)
    if was >= BAKE_TILE0:
        check("the probe cell is a plain tile", False, f"({col},{row}) is {was}")
        return

    def bake(pu, flags=EF_ACTIVE | EF_TOUCH):
        """One pickup, alone in the table, through the real ENT_BAKE."""
        m.poke(cell, was)                       # whatever the last one left
        blob = record(EK_PICKUP, col * 8, (row + 1) * 16, flags, pu, 0)
        blob += bytes(ENT_MAX * ENT_STRIDE - len(blob))
        m.write_ram(sym["ENT_TABLE"], blob)
        m.poke(sym["ENT_COUNT"], ENT_MAX)
        a = sym["ENT_BAKE"]
        code = bytes([0xF3, 0xCD, a & 0xFF, a >> 8, 0x18, 0xFE])
        m.write_ram(STUB, code)
        m.set_pc(STUB)
        for us in range(1, 200000):
            m.run_us(1)
            if m.pc == STUB + 4:
                m.set_pc(sym["WAIT_VSYNC"])
                return us
        m.set_pc(sym["WAIT_VSYNC"])
        return None                             # it ran away

    plain = tiles[was * TILE_BYTES:(was + 1) * TILE_BYTES]
    hung, wrong, agreed, slowest = [], [], 0, 0
    for pu in range(6):
        us = bake(pu)
        if us is None:
            hung.append(pu)
            continue
        slowest = max(slowest, us)
        blob, cel = blob_cel(*ART[pu])
        want = stamp(blob, cel, plain)
        got = peek_c4(m, sym, BAKE_ADDR, TILE_BYTES)
        if got == want and m.peek(cell) == BAKE_TILE0:
            agreed += 1
        else:
            wrong.append(pu)

    check("ENT_BAKE comes back for all six kinds", not hung,
          f"PU_{'/'.join(str(p) for p in hung)} never returned - the frame "
          "copy walked off the end of the blob"
          if hung else f"slowest {slowest:,} us")
    check("... and every one of them composites to the model",
          agreed == 6, f"{agreed} of 6 tiles"
          + (f", wrong: {wrong}" if wrong else ""))

    # THE CONTROLS. Six comparisons that all passed would also pass if
    # every kind drew the same thing, or if the stamp wrote nothing.
    bake(PU_BOOK)
    book = peek_c4(m, sym, BAKE_ADDR, TILE_BYTES)
    blob, cel = blob_cel(*ART[PU_IDOL])
    check("a book is not an idol", book != stamp(blob, cel, plain),
          "the model would agree with anything if every cel drew the same")
    check("... and neither of them is the tile underneath",
          book != plain, "a stamp that wrote nothing would pass the model")

    us = bake(PU_BOOK, flags=0)                 # not EF_ACTIVE
    check("a record that is not EF_ACTIVE is not baked at all",
          us is not None and m.peek(sym["ENT_BAKED"]) == 0
          and m.peek(cell) == was,
          f"ENT_BAKED {m.peek(sym['ENT_BAKED'])}, cell {m.peek(cell)} "
          f"against {was}")
    m.poke(cell, was)


def ceiling_checks(sym):
    """ENT_BAKE_MAX pickups get a tile. What happens to the rest is the
    reason the level editor refuses them.

    A pickup is not a sprite - it is composited once into a private copy
    of the tile it stands on - and there are sixteen of those copies at
    the top of bank C4 (CLAUDE.md 8.6). ENT_MAX is 24, so a level can
    hold eight pickups the engine will not draw, and entity.asm says
    what it does about it in its own words: "the rest stay invisible
    rather than overwrite someone else's art".

    INVISIBLE IS NOT ABSENT, and that is the half a designer cannot
    guess. The AABB never consults the bake, so the seventeenth pickup
    is still there to walk into - it goes into her inventory out of a
    cell that is drawing plain roof.

    The editor's EngineLimits.BakedPickups is this number, and this is
    where the two are tied together: raise ENT_BAKE_MAX and the check
    below moves with it, which is what should then move the editor's.
    """
    print("\n  the bake's ceiling, and what is past it:")
    m = boot(sym, scroll=True)
    quiet_the_enemies(m, sym)
    w = World(m, sym)
    ceiling = sym["ENT_BAKE_MAX"]

    # Clear of the level's own five, which are at columns 24, 44 and 64
    # of row 5 and 26 and 62 of row 13.
    first_col, row = 70, 5
    n = ceiling + 3
    cells = [MAP_ADDR + row * MAP_W + first_col + i for i in range(n)]
    plain = [m.peek(c) for c in cells]
    if any(p >= BAKE_TILE0 for p in plain):
        check("the probe cells are plain tiles", False, f"{plain}")
        return

    w.load(*[record(EK_PICKUP, (first_col + i) * 8, (row + 1) * 16,
                    EF_ACTIVE | EF_TOUCH, PU_KEY, 0) for i in range(n)])
    a = sym["ENT_BAKE"]
    m.write_ram(STUB, bytes([0xF3, 0xCD, a & 0xFF, a >> 8, 0x18, 0xFE]))
    m.set_pc(STUB)
    for _ in range(400000):
        m.run_us(1)
        if m.pc == STUB + 4:
            break
    m.set_pc(sym["WAIT_VSYNC"])

    drawn = [i for i, c in enumerate(cells) if m.peek(c) >= BAKE_TILE0]
    check(f"exactly ENT_BAKE_MAX = {ceiling} pickups get a scratch tile",
          m.peek(sym["ENT_BAKED"]) == ceiling and len(drawn) == ceiling,
          f"{len(drawn)} of {n} drawn, ENT_BAKED {m.peek(sym['ENT_BAKED'])}")
    check("... and the ones past it draw whatever was under them",
          all(m.peek(cells[i]) == plain[i] for i in range(ceiling, n)),
          f"cells {list(range(ceiling, n))} still hold {plain[ceiling:]}")

    # ... AND THE ENGINE WILL STILL HAND HER ONE. Her box is 6 bytes and
    # a pickup 4, and x is in PIXELS in the record and BYTES in the box
    # (CLAUDE.md 8.10), so this stands her across the last one.
    over = first_col + n - 1
    m.poke(sym["KEYS_COUNT"], 0)
    w.place(over * 4 - 1, (row + 1) * 16 - KARA_H)
    w.run("ENT_UPDATE")
    check("... and one of THOSE is still there to walk into",
          m.peek(sym["KEYS_COUNT"]) == 1,
          f"KEYS_COUNT {m.peek(sym['KEYS_COUNT'])} off a pickup at tile "
          f"({over},{row}), whose cell is drawing tile {m.peek(cells[-1])} "
          "- which is why the editor refuses the level rather than "
          "warning about it")


def disown_checks(sym):
    """A repaint disowns the strip's layout ONLY when it can reach it.

    ENT_REPAINT_DUE puts the tilemap back where a taken pickup was, and
    that cell may be under the HUD's bottom row - so the layout is
    stamped &FF and HUD_SERVICE writes the whole strip again before the
    beam gets there (CLAUDE.md 7.8). Unconditionally, that costs a whole
    game frame on the two paths that have none to give: the strip laid
    out again is ~17,000 T on a first sweep with under 484 to spare.

    A level-1 pickup is never over the strip - the roof is world
    character row 12 and the view's own row is 0 to 8 - so what is
    checked here is the guard itself, driven at a cell chosen to land
    where the strip is and at two that do not. Both halves matter: a
    guard that never fires would pass the second and third alone.
    """
    print("\n  the repaint disowns the strip only when it is under it:")
    m = boot(sym, scroll=True)
    quiet_the_enemies(m, sym)
    sync(m, sym)
    wx, wcr = m.peek(sym["WORLD_X"]), m.peek(sym["WORLD_CR"])
    if wcr & 1:
        # ENT_RP_WR is a map row doubled and so always even; with an odd
        # view row the repaint's rows are odd, row 23 is refused for
        # having its partner off the display, and row 21 stops at 22.
        check("the view's row is even, so row 22 is reachable at all",
              False, f"WORLD_CR {wcr}")
        return

    def cell(screen_col, screen_row):
        row = (wcr + screen_row) // 2
        col = (wx + screen_col) // 2
        return MAP_ADDR + row * MAP_W + col

    def repaint(addr):
        m.poke(sym["HUD_HP"], 100)
        m.write_ram(STUB, bytes([
            0xF3, 0x21, addr & 0xFF, addr >> 8,
            0xCD, sym["ENT_CELL_REPAINT"] & 0xFF,
            sym["ENT_CELL_REPAINT"] >> 8, 0x18, 0xFE]))
        m.set_pc(STUB)
        for _ in range(40000):
            m.run_us(1)
            if m.pc == STUB + 7:
                break
        return m.peek(sym["HUD_HP"])

    # THE COLUMNS HAVE TO BE EVEN with an even view, for the same reason
    # the rows do: ENT_RP_WC is a map column doubled.
    hud_row, strip = sym["HUD_ROW"], sym["HUD_STRIP_CELLS"]
    inside = wx & 1
    outside = strip + ((wx ^ strip) & 1)
    got = repaint(cell(inside, hud_row - 1))
    check("a cell whose lower half IS the strip's row disowns the layout",
          got == 0xFF,
          f"HUD_HP &{got:02X} after a repaint at screen ({inside}, "
          f"{hud_row - 1}), which covers rows {hud_row - 1} and {hud_row}")

    got = repaint(cell(inside, hud_row - 3))
    check("... and two rows higher does not", got == 100,
          f"HUD_HP {got} after the same repaint at screen row "
          f"{hud_row - 3} - so the guard is the ROW and not the call")

    got = repaint(cell(outside, hud_row - 1))
    check("... nor does the same row past the strip's last cell",
          got == 100,
          f"HUD_HP {got} at screen column {outside}, the strip being "
          f"columns 0 to {strip - 1}")

    m.set_pc(sym["WAIT_VSYNC"])


def bake_checks(sym):
    """A pickup is drawn by being composited into the tile it stands on.

    Not by a sprite: measured, one pickup through SPAN_DRAW cost
    12,116 T a frame against the 1,324 a scrolling frame has spare
    (CLAUDE.md 9). So the three things worth testing are that the
    composite is right, that it reaches the screen, and that taking it
    puts the original tile back.
    """
    print("\n  baked into the tilemap:")
    m = boot(sym, scroll=True)
    quiet_the_enemies(m, sym)
    baked = m.peek(sym["ENT_BAKED"])
    ents = bytes(m.read_ram(sym["ENT_TABLE"], ENT_MAX * ENT_STRIDE))
    n_pick = sum(1 for i in range(ENT_MAX)
                 if ents[i * 8] == EK_PICKUP and ents[i * 8 + 5] & EF_ACTIVE)
    check("every pickup in the level got a scratch tile",
          baked == n_pick, f"{baked} baked, {n_pick} pickups")

    tiles = open(os.path.join(LEV, "level1_city", "citytiles.bin"), "rb").read()
    agreed = wrong = 0
    first_cell = None
    for slot in range(baked):
        L = sym["ENT_BAKE_LIST"] + slot * BAKE_STRIDE
        rec = m.peek(L) | (m.peek(L + 1) << 8)
        cell = m.peek(L + 2) | (m.peek(L + 3) << 8)
        was = m.peek(L + 4)
        i = (rec - sym["ENT_TABLE"]) // ENT_STRIDE
        pu = ents[i * 8 + 6]
        blob, cel = blob_cel(*ART[pu])
        want = stamp(blob, cel, tiles[was * TILE_BYTES:(was + 1) * TILE_BYTES])
        got = peek_c4(m, sym, BAKE_ADDR + slot * TILE_BYTES, TILE_BYTES)
        if got == want:
            agreed += 1
        else:
            wrong += 1
        if m.peek(cell) != BAKE_TILE0 + slot:
            wrong += 1
        if first_cell is None:
            first_cell = (cell, was, got, pu)
    check("the composite agrees with an independent model of the format",
          wrong == 0 and agreed == baked, f"{agreed} of {baked} tiles")
    check("a baked pickup is NOT the tile it was baked over",
          all(peek_c4(m, sym, BAKE_ADDR + s * TILE_BYTES, TILE_BYTES)
              != tiles[m.peek(sym["ENT_BAKE_LIST"] + s * BAKE_STRIDE + 4)
                       * TILE_BYTES:][:TILE_BYTES] for s in range(baked)),
          "the negative control: a stamp that wrote nothing would pass "
          "the model too")

    # ---- and it has to reach the CRTC ------------------------------
    cell, was, want, _ = first_cell
    col, row = (cell - MAP_ADDR) & (MAP_W - 1), (cell - MAP_ADDR) >> 7
    plain = tiles[was * TILE_BYTES:(was + 1) * TILE_BYTES]
    m.joystick(0x08)                                  # walk her at it
    seen_before = None
    for _ in range(400):
        m.run_frames(1)
        if m.peek(sym["WORLD_X"]) >= col * 2 - 36 and not m.peek(cell) == was:
            break
    sync(m, sym)
    seen_before = screen_cell(m, sym, col, row)
    check("the baked tile is what the CRTC shows before she takes it",
          seen_before == want,
          f"cell ({col},{row}), WORLD_X {m.peek(sym['WORLD_X'])}")
    check("... and it is not the plain tile", seen_before != plain)

    for _ in range(400):
        m.run_frames(1)
        if m.peek(cell) == was:
            break
    m.run_frames(3)
    sync(m, sym)
    m.joystick(0)
    after = screen_cell(m, sym, col, row)
    check("taking it puts the original tile back on the screen",
          after == plain, f"map cell is {m.peek(cell)} again")



def art_checks(sym):
    """WHERE A PICKUP'S PICTURE COMES FROM, IN EVERY ENVIRONMENT.

    ENT_ART used to be six rows of L1_* symbols, and `hudicon` is
    allocated at a different bank AND address in every one of the six
    levels - so a medkit or a coin placed anywhere but the City baked
    its picture out of whatever sat at the City's address in that
    level's banks. The level loads, the map is right, and one tile is
    noise: CLAUDE.md 11 step 7's own class of fault, and one nothing
    here could see, because every suite measures the City.

    What is checked is ENT_ART_FOR's answer for all six environments x
    six kinds against build/levels/banks.inc and the artist's own .inc
    files - the same sources the assembler read, taken apart by
    different code. The control is the fault itself: how many of the 36
    the OLD table would have got wrong.
    """
    print("\n  a pickup's art, in every environment:")
    banks, cels = inc_values()
    m = boot(sym, scroll=True)

    def ask(env, kind):
        """ENT_ART_FOR, from a DI stub, with LEVEL_ENV poked."""
        m.poke(sym["LEVEL_ENV"], env)
        m.write_ram(0x9000, bytes([0xF3, 0x3E, kind, 0xCD,
                                   sym["ENT_ART_FOR"] & 0xFF,
                                   sym["ENT_ART_FOR"] >> 8, 0x18, 0xFE]))
        m.set_pc(0x9000)
        # di(1) + ld a,n(2) + call nn(3) = the `jr $` sits at +6, where
        # bench.raw's own stub has it at +4. Waiting at +5 reads back
        # whatever the last real bake left in the scratch, which is a
        # constant answer for every question - the shape of a test whose
        # argument changes nothing (CLAUDE.md 10).
        for _ in range(200000):
            m.run_us(1)
            if m.pc == 0x9006:
                break
        else:
            raise SystemExit("ENT_ART_FOR never returned")
        return (m.peek(sym["ENT_ART_BANK"]),
                m.peek(sym["ENT_ART_ADDR"]) | m.peek(sym["ENT_ART_ADDR"] + 1) << 8,
                m.peek(sym["ENT_ART_CELN"]))

    # What each environment draws SPECIALLY, off the shipped sheets.
    over = {(0, PU_KEY):    ("CITYPICKUPS", "KEY", 1),
            (0, PU_AMMO):   ("CITYPICKUPS", "AMMO", 1),
            (1, PU_IDOL):   ("FORESTPICKUPS", "IDOL", 2),
            (3, PU_MEDKIT): ("SEAPICKUPS", "MEDKIT", 4)}
    HUD_CEL = {PU_KEY: "KEY", PU_AMMO: "AMMO", PU_MEDKIT: "HEART",
               PU_COIN: "COIN", PU_IDOL: "IDOL", PU_BOOK: "BOOK"}

    wrong, moved, seen = [], 0, {}
    for env in range(6):
        for kind in range(6):
            if (env, kind) in over:
                sheet, cel, lvl = over[(env, kind)]
                want = banks[f"L{lvl}_{sheet}"] + (cels[f"{sheet}_{cel}_FIRST"],)
            else:
                want = banks[f"L{env + 1}_HUDICON"] + (cels[f"HUDICON_{HUD_CEL[kind]}_FIRST"],)
            got = ask(env, kind)
            seen[(env, kind)] = got
            if got != want:
                wrong.append((env, kind, got, want))
            # ... and what the OLD table would have said: level 1's, always
            old = (banks["L1_CITYPICKUPS"] + (cels[f"CITYPICKUPS_{HUD_CEL[kind]}_FIRST"],)
                   if kind in (PU_KEY, PU_AMMO)
                   else banks["L1_HUDICON"] + (cels[f"HUDICON_{HUD_CEL[kind]}_FIRST"],))
            if old != want:
                moved += 1

    check("every environment gets its OWN art", not wrong,
          f"36 of 36 - 6 environments x 6 kinds, against banks.inc and the "
          f"artist's .inc files" if not wrong else f"{wrong[:3]}")
    check("... and that is not what the old table said", moved > 0,
          f"{moved} of the 36 move - which is how many pickups were baking "
          f"out of level 1's address in somebody else's banks")

    # THE SHARPEST HALF: the fallback must be a DIFFERENT blob in each
    # environment, because that is the fact the old table denied.
    addrs = {seen[(env, PU_BOOK)] for env in range(6)}
    check("the fallback is six different places, not one", len(addrs) == 6,
          ", ".join(f"env {e}: &{seen[(e, PU_BOOK)][0]:02X}:"
                    f"{seen[(e, PU_BOOK)][1]:04X}" for e in range(6)))

    # ... and the City still answers exactly what it always did, which
    # is what the bake checks above are measured against.
    check("the City is untouched", seen[(0, PU_KEY)] ==
          banks["L1_CITYPICKUPS"] + (cels["CITYPICKUPS_KEY_FIRST"],),
          "its key is still citypickups cel 0")

    # ... AND THE EDITOR'S COPY OF THE SAME LIST. Its validator refuses a
    # pickup whose p0 is past ENT_ART_KINDS, which is the engine's own
    # rule - so an enum that has not caught up refuses a level the engine
    # bakes, and nothing on the hardware says which record was skipped.
    enum = editor_enum("PickupKind")
    check("the editor's PickupKind is the engine's list",
          sorted(enum.values()) == list(range(sym["ENT_ART_KINDS"])),
          f"{', '.join(f'{k}={v}' for k, v in sorted(enum.items(), key=lambda kv: kv[1]))} "
          f"against ENT_ART_KINDS {sym['ENT_ART_KINDS']}")


def inc_values():
    """banks.inc and the art .inc files, read independently."""
    banks, cels = {}, {}
    for line in open(os.path.join(LEV, "banks.inc")):
        mm = re.match(r"^(L\d_\w+?)_(BANK|ADDR)\s+equ\s+&([0-9A-F]+)", line)
        if mm:
            name, which, v = mm.group(1), mm.group(2), int(mm.group(3), 16)
            b, a = banks.get(name, (0, 0))
            banks[name] = (v, a) if which == "BANK" else (b, v)
    for root, _, files in os.walk(LEV):
        for f in files:
            if not f.endswith(".inc"):
                continue
            for line in open(os.path.join(root, f)):
                mm = re.match(r"^(\w+_FIRST)\s+equ\s+(\d+)", line)
                if mm:
                    cels[mm.group(1)] = int(mm.group(2))
    return banks, cels


def main():
    sym = symbols()
    for n in ("ENT_UPDATE", "ENT_TABLE", "ENTITY_COLLISION_CHECK",
              "CHECK_KEY_DOOR", "PLACE_STATUE", "READ_BOOK_PUZZLE",
              "TALK_NPC_COIN", "USE_MEDKIT", "PLAYER_HP", "KEYS_COUNT",
              "COINS_COUNT", "STATUES_HELD", "CURRENT_BOOK_ID"):
        if n not in sym:
            check(f"{n} is linked", False, "rebuild first")
            return 1
    m = boot(sym)
    sync(m, sym)
    w = World(m, sym)

    # -----------------------------------------------------------------
    # 1. The AABB, swept against an independent model.
    # -----------------------------------------------------------------
    print("\n  the overlap test, swept against the separating-axis model:")
    # Swept around the EDGES rather than uniformly: an overlap test is
    # only ever wrong by one, so the interesting positions are the ones
    # where her box just touches or just misses. A uniform grid spends
    # its time far away from the answer.
    bad = cases = hits = 0
    for kind in (EK_PICKUP, EK_DOOR, EK_NPC):
        ew, eh = HITBOX[kind]
        for ex_px, ey in ((80, 80), (81, 96), (160, 192)):
            w.load(record(kind, ex_px, ey, EF_ACTIVE))
            ex = ex_px >> 1
            etop = (ey - eh) & 0xFF
            for kx in range(max(0, ex - KARA_W - 2), ex + ew + 3):
                for ky in list(range(max(0, etop - KARA_H - 2),
                                     min(255, etop - KARA_H + 3))) + \
                          list(range(max(0, etop + eh - 2),
                                     min(255, etop + eh + 3))) + \
                          [etop, etop + eh // 2]:
                    w.place(kx, ky)
                    m.poke(sym["ENT_HIT"], 0)
                    m.poke(sym["ENT_HIT"] + 1, 0)
                    w.run("ENTITY_COLLISION_CHECK")
                    hit = (m.peek(sym["ENT_HIT"])
                           | m.peek(sym["ENT_HIT"] + 1) << 8) != 0
                    want = overlaps(kx, ky, kind, ex_px, ey)
                    cases += 1
                    hits += want
                    if hit != want:
                        bad += 1
                        if bad < 5:
                            print(f"    kind {kind} at ({ex_px},{ey}) vs "
                                  f"kara ({kx},{ky}): engine "
                                  f"{'hit' if hit else 'miss'}, model "
                                  f"{'hit' if want else 'miss'}")
    print(f"    {cases} placements around the edges, "
          f"{hits} of them overlapping")
    check("the AABB agrees with the model everywhere", bad == 0,
          f"{bad} of {cases} disagree")
    check("...and the sweep actually produced overlaps", hits > cases // 20,
          f"{hits} hits: a sweep that never touches proves nothing")

    # -----------------------------------------------------------------
    # 2. Pickups act on contact, once.
    # -----------------------------------------------------------------
    print("\n  pickups, on touch:")
    ROOF = 80
    cases = [
        ("a key",     PU_KEY,    0,  "KEYS_COUNT",   1, ER_TOOK),
        ("an ammo box", PU_AMMO, 14, "AMMO_RESERVE", None, ER_TOOK),
        ("a coin",    PU_COIN,   5,  "COINS_COUNT",  5, ER_TOOK),
        ("an idol",   PU_IDOL,   0,  "STATUES_HELD", 1, ER_TOOK),
        ("a book",    PU_BOOK,   3,  "CURRENT_BOOK_ID", 3, ER_TOOK),
    ]
    for name, pu, p1, counter, want, res in cases:
        w.load(record(EK_PICKUP, 80, ROOF, EF_ACTIVE | EF_TOUCH, pu, p1))
        w.give(KEYS_COUNT=0, COINS_COUNT=0, STATUES_HELD=0,
               CURRENT_BOOK_ID=0, AMMO_RESERVE=0)
        w.place(40, ROOF - KARA_H)
        w.run("ENT_UPDATE")
        got = w.st(counter)
        taken = bool(w.flags(0) & EF_TAKEN)
        exp = p1 if want is None else want
        ok = got == exp and taken and w.result() == res
        print(f"    {'ok ' if ok else 'NO '} {name:<12} {counter} = {got}"
              f" (want {exp}), {'taken' if taken else 'STILL THERE'}, "
              f"{ER_NAME[w.result()]}")
        if not ok:
            fails.append(f"pickup: {name}")
        # ... and a second pass must change nothing
        before = w.st(counter)
        w.run("ENT_UPDATE")
        if w.st(counter) != before:
            fails.append(f"pickup taken twice: {name}")
    check("every pickup type goes into the right counter", True
          if not [f for f in fails if f.startswith("pickup:")] else False,
          "see above")
    check("a pickup is taken once, not once a frame",
          not [f for f in fails if f.startswith("pickup taken twice")])

    # -----------------------------------------------------------------
    # 3. The medkit is the one that can be refused.
    # -----------------------------------------------------------------
    print("\n  the medkit:")
    for hp, want_hp, want_res, want_taken in ((40, 75, ER_HEALED, True),
                                              (80, 100, ER_HEALED, True),
                                              (100, 100, ER_FULL, False)):
        w.load(record(EK_PICKUP, 80, ROOF, EF_ACTIVE | EF_TOUCH, PU_MEDKIT))
        w.give(PLAYER_HP=hp)
        w.place(40, ROOF - KARA_H)
        w.run("ENT_UPDATE")
        got, taken = w.st("PLAYER_HP"), bool(w.flags(0) & EF_TAKEN)
        ok = got == want_hp and taken == want_taken and w.result() == want_res
        print(f"    {'ok ' if ok else 'NO '} at {hp} HP -> {got}, "
              f"{'consumed' if taken else 'left on the ground'}, "
              f"{ER_NAME[w.result()]}")
        if not ok:
            fails.append(f"medkit at {hp}")
    check("35 points, capped at 100, and refused when full",
          not [f for f in fails if f.startswith("medkit")])

    # -----------------------------------------------------------------
    # 4. The four asked-for handlers. UP, and only UP.
    # -----------------------------------------------------------------
    print("\n  the door, and the key it spends:")
    door = record(EK_DOOR, 160, 192, EF_ACTIVE | EF_SOLID, 0, PU_KEY)
    w.load(door)
    w.give(KEYS_COUNT=0)
    w.place(78, 132)
    w.run("ENT_UPDATE", up=True)
    check("no key, no door", w.result() == ER_LOCKED and
          not w.flags(0) & EF_TAKEN, ER_NAME[w.result()])
    w.give(KEYS_COUNT=1)
    w.run("ENT_UPDATE", up=True)
    opened = bool(w.flags(0) & EF_TAKEN)
    check("a key opens it and is spent",
          w.result() == ER_OPENED and opened and w.st("KEYS_COUNT") == 0,
          f"{ER_NAME[w.result()]}, keys now {w.st('KEYS_COUNT')}")
    check("...and an open door is no longer solid",
          not w.flags(0) & EF_SOLID, f"flags &{w.flags(0):02X}")
    w.give(KEYS_COUNT=1)
    w.run("ENT_UPDATE", up=True)
    check("an open door does not eat a second key", w.st("KEYS_COUNT") == 1,
          f"keys {w.st('KEYS_COUNT')}")

    w.load(door)
    w.give(KEYS_COUNT=1)
    w.place(78, 132)
    w.run("ENT_UPDATE", up=False)
    check("standing on a door does nothing until UP is pressed",
          w.result() == ER_NOTHING and not w.flags(0) & EF_TAKEN,
          ER_NAME[w.result()])

    print("\n  the altar, which wants two idols:")
    w.load(record(EK_RECEPTACLE, 80, ROOF, EF_ACTIVE, PU_IDOL, 2))
    w.give(STATUES_HELD=0)
    w.place(40, ROOF - KARA_H)
    w.run("ENT_UPDATE", up=True)
    check("empty-handed, it says so", w.result() == ER_EMPTY,
          ER_NAME[w.result()])
    w.give(STATUES_HELD=2)
    w.run("ENT_UPDATE", up=True)
    check("one idol goes in and it still wants another",
          w.result() == ER_PLACED and w.st("STATUES_HELD") == 1
          and not w.flags(0) & EF_TAKEN,
          f"{ER_NAME[w.result()]}, held {w.st('STATUES_HELD')}")
    w.run("ENT_UPDATE", up=True)
    check("the second satisfies it", w.flags(0) & EF_TAKEN
          and w.st("STATUES_HELD") == 0,
          f"flags &{w.flags(0):02X}, held {w.st('STATUES_HELD')}")

    print("\n  the gate slot, which wants ONE symbol:")
    w.load(record(EK_RECEPTACLE, 80, ROOF, EF_ACTIVE, PU_BOOK, 3))
    w.give(CURRENT_BOOK_ID=0)
    w.place(40, ROOF - KARA_H)
    w.run("ENT_UPDATE", up=True)
    check("no book, nothing to read", w.result() == ER_EMPTY,
          ER_NAME[w.result()])
    w.give(CURRENT_BOOK_ID=2)
    w.run("ENT_UPDATE", up=True)
    check("the wrong symbol is refused AND kept",
          w.result() == ER_WRONG and w.st("CURRENT_BOOK_ID") == 2
          and not w.flags(0) & EF_TAKEN,
          f"{ER_NAME[w.result()]}, still holding {w.st('CURRENT_BOOK_ID')}")
    w.give(CURRENT_BOOK_ID=3)
    w.run("ENT_UPDATE", up=True)
    check("the right one lights it and leaves her empty-handed",
          w.result() == ER_PLACED and w.st("CURRENT_BOOK_ID") == 0
          and w.flags(0) & EF_TAKEN,
          f"{ER_NAME[w.result()]}, holding {w.st('CURRENT_BOOK_ID')}")

    print("\n  the informant, three coins:")
    w.load(record(EK_NPC, 80, ROOF, EF_ACTIVE, 3, 7))
    w.give(COINS_COUNT=2, NPC_LINE=0)
    w.place(40, ROOF - KARA_H)
    w.run("ENT_UPDATE", up=True)
    check("two coins is not enough, and buys nothing",
          w.result() == ER_POOR and w.st("COINS_COUNT") == 2,
          f"{ER_NAME[w.result()]}, coins {w.st('COINS_COUNT')}")
    w.give(COINS_COUNT=5)
    w.run("ENT_UPDATE", up=True)
    check("five buys it, three are taken, and he names his line",
          w.result() == ER_TOLD and w.st("COINS_COUNT") == 2
          and w.st("NPC_LINE") == 7,
          f"{ER_NAME[w.result()]}, coins {w.st('COINS_COUNT')}, "
          f"line {w.st('NPC_LINE')}")
    w.run("ENT_UPDATE", up=True)
    check("he does not charge twice for the same hint",
          w.st("COINS_COUNT") == 2, f"coins {w.st('COINS_COUNT')}")

    # -----------------------------------------------------------------
    # 5. The table's own rules.
    # -----------------------------------------------------------------
    print("\n  the table:")
    w.load(bytes(8), record(EK_PICKUP, 80, ROOF, EF_ACTIVE | EF_TOUCH,
                            PU_KEY))
    w.give(KEYS_COUNT=0)
    w.place(40, ROOF - KARA_H)
    w.run("ENT_UPDATE")
    check("an all-zero slot is empty, not a PlayerStart at (0,0)",
          w.st("KEYS_COUNT") == 1,
          "kind 0 is a real kind, so a slot is told by its FLAGS")
    w.load(record(EK_PICKUP, 80, ROOF, EF_TOUCH, PU_KEY))   # no EF_ACTIVE
    w.give(KEYS_COUNT=0)
    w.run("ENT_UPDATE")
    check("an inactive entity is not there at all", w.st("KEYS_COUNT") == 0)
    w.load(record(EK_PICKUP, 80, ROOF, EF_ACTIVE | EF_TAKEN | EF_TOUCH,
                  PU_KEY))
    w.run("ENT_UPDATE")
    check("a taken one stays taken", w.st("KEYS_COUNT") == 0)

    # the level's own table, as build/city_entities.bin wrote it
    blob = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "build", "city_entities.bin"), "rb").read()
    used = sum(1 for i in range(ENT_MAX) if blob[i * 8 + 5] & EF_ACTIVE)
    print(f"\n  the City ships {used} entities in {len(blob)} bytes:")
    for i in range(used):
        r = blob[i * 8:i * 8 + 8]
        print(f"    kind {r[0]}  x {r[1] | r[2] << 8:4d}  "
              f"y {r[3] | r[4] << 8:3d}  flags &{r[5]:02X}  "
              f"p0 {r[6]}  p1 {r[7]}")
    print("\n  the touch sweep's place in the beat:")
    # IT IS ONE FRAME IN FOUR NOW, NOT ONE IN TWO, AND THE RUN IS WHY.
    # A run is a byte a frame and the camera steps every other one, so
    # the stepping frame carries the incoming column AND the heaviest
    # cel in the game; the sweep on top of that is what tipped it over.
    # Measured, quartering it is worth 11 loop iterations in 200
    # running (151 -> 162) and nothing at all walking, which is the
    # shape of a cost that only lands on the tight frames.
    #
    # ALL FOUR PHASES ARE DRIVEN, because a check that only knew about
    # odd and even would still pass on the old gate and say nothing
    # about the new one - and WHICH odd phase it is was worth more than
    # the quartering: 182 -> 191 firing and 173 -> 189 jumping and
    # firing, for two off the plain run (src/entity.asm).
    w = World(boot(sym), sym)
    seen = []
    for phase in range(4):
        w.load(record(EK_PICKUP, 100, 100, EF_ACTIVE | EF_TOUCH, PU_KEY, 0))
        w.place(50, 40)
        w.give(KEYS_COUNT=0)
        w.run("ENT_UPDATE", mask=EF_TOUCH, frame=phase)
        seen.append(w.st("KEYS_COUNT"))
    check("the touch sweep runs on every game frame",
          seen == [1, 1, 1, 1],
          f"phases 0..3 picked up {seen} - it shared the 50 Hz frame with "
          f"the enemy redraw and took one frame in two, then one in four; "
          f"a game frame is two hardware frames now and the pair of them "
          f"is 376 T of 159,744 (CLAUDE.md 9)")

    # ---- AND SHE STILL PICKS IT UP AT A RUN, WHICH IS THE WORST CASE
    # A run is a byte a frame, so four frames between sweeps is four
    # bytes of travel - against her 6-byte box plus a 4-byte pickup,
    # which is ten bytes of overlap, so at least two sweeps land inside
    # it. That is the argument; this is the measurement, in the running
    # game rather than through the harness above.
    print("\n  and she still picks it up at a RUN:")
    # A RUN IS THE WORST CASE FOR A SWEEP: she covers two bytes a game
    # frame, against the ten bytes her 6-byte box and a 4-byte pickup
    # overlap for. This is that, in the running game rather than through
    # the harness above.
    JOY_RIGHT = 0x08

    def running_pass(untouchable=False, frames=200):
        mm = boot(sym, scroll=True)
        if untouchable:
            # THE NEGATIVE CONTROL IS THE FLAG, not the beat: take
            # EF_TOUCH off the key's own record and the same run must
            # walk straight past it. Without this the check below would
            # pass on a game that handed her a key for any reason.
            for i in range(ENT_MAX):
                r = sym["ENT_TABLE"] + i * ENT_STRIDE
                if (mm.peek(r) == EK_PICKUP and mm.peek(r + 6) == PU_KEY):
                    mm.poke(r + 5, mm.peek(r + 5) & ~EF_TOUCH)
        mm.joystick(JOY_RIGHT)
        mm.key_down('A')                    # SHIFT: row 2 bit 5 (input.asm)
        took = None
        for t in range(frames):
            mm.run_frames(1)
            if took is None and mm.peek(sym["KEYS_COUNT"]):
                took = t
        mm.joystick(0)
        mm.key_up('A')
        return took

    took = running_pass()
    check("running right over the roof's key, she takes it",
          took is not None,
          f"KEYS_COUNT went up on hardware frame {took}" if took is not None
          else "she ran straight past it")
    missed = running_pass(untouchable=True)
    check("... and with EF_TOUCH off that record she runs straight past",
          missed is None,
          f"she still took it on frame {missed} - so the check above is "
          f"not measuring the touch sweep" if missed is not None
          else "so what the check above measures really is the sweep")

    check("the level's table is the eight-byte record, ENT_MAX long",
          len(blob) == ENT_MAX * 8 and used > 0, f"{len(blob)} bytes")

    bake_checks(sym)
    art_checks(sym)
    every_kind_checks(sym)
    ceiling_checks(sym)
    disown_checks(sym)

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
