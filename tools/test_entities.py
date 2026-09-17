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

    def run(self, routine, up=False, mask=0, frame=1):
        """Call one routine from a DI stub.

        `mask` goes into A, which ENTITY_COLLISION_CHECK reads as the
        EF_ bits an entity must have. Leaving it to whatever was in the
        register made the sweep below miss everything it should have
        hit - the test's own bug, and the first place to look when a
        register-argument routine disagrees with a model.
        """
        s, m = self.sym, self.m
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
    print("\n  the touch sweep's frame parity:")
    w = World(boot(sym), sym)
    w.load(record(EK_PICKUP, 100, 100, EF_ACTIVE | EF_TOUCH, PU_KEY, 0))
    w.place(50, 40)
    w.give(KEYS_COUNT=0)
    w.run("ENT_UPDATE", mask=EF_TOUCH, frame=0)   # even: the redraw's frame,
    even = w.st("KEYS_COUNT")                    # and the column's head
    w.run("ENT_UPDATE", mask=EF_TOUCH, frame=1)  # odd: the sweep's own
    odd = w.st("KEYS_COUNT")
    check("the touch sweep runs on odd frames and not even ones",
          even == 0 and odd == 1, f"even {even}, odd {odd}")

    check("the level's table is the eight-byte record, ENT_MAX long",
          len(blob) == ENT_MAX * 8 and used > 0, f"{len(blob)} bytes")

    bake_checks(sym)

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
