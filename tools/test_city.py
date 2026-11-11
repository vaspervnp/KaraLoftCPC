#!/usr/bin/env python3
"""Level 2 on a 6128: the City's second map, across the rooftops.

Level 1's garage is where its key goes and LEVEL_GOTO goes to
LEVEL_CUR + 1 (CLAUDE.md 8.1), so level 2 is the map that door has
pointed at since it was placed. It opens on that garage drawn OPEN, and
it is the City's own mechanic - plan.md's rooftop jumps - made into the
level: five roofs, four gaps, and the key on the last roof.

WHAT MAKES IT A CHECK AND NOT A SCREENSHOT is that nothing here knows
where the generator put anything. The roofs, the gaps, the ladders and
the barricades that cut the street are read back out of the level's OWN
map through the engine's own TILE_ATTR, and she is driven across them
from the joystick. The jump is pressed at one rule for every gap - the
byte column one before the gap's first - and the rule is inside every
window only because the windows were measured, which the last section
of this suite does again on the level itself.

THE JUMP IS 28 LINES - P_JUMP's own comment used to say 36 when it
was 21 - and that is the number this level is shaped by: every roof
here is SOLID and a solid step of two rows is a wall (CLAUDE.md 8.14,
and the comment by P_GRAVITY). Forty-three is what she reaches onto a
PLATFORM, which is every branch and ledge the forest and the cave were
measured against - and still short of three rows.

AND A THREE-TILE GAP DOWNHILL CAN BE CROSSED WITHOUT A PRESS: running
off its edge lands her on the far roof at one stride phase in two. That
was a reason to make the downhill gaps four wide, and a play-test said
four was too wide to make at all - so they are three, every gap is one
a WALK can make - the one UP on a single frame, which makes it a run's -
and the run-off check below says which gaps a run off
the edge crosses rather than that none does.
"""
import os
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import boot, symbols, sync                          # noqa: E402
import make_city_map as city                                   # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BUILD = os.path.join(ROOT, "build")
JOY = {"right": 0x08, "left": 0x04, "up": 0x01, "down": 0x02, "fire": 0x10}
GS_CLEAR = 2
TA_SOLID, TA_PLATFORM, TA_CLIMB = 0x01, 0x02, 0x08
LEVEL = 2
PAVEMENT = city.ROW_PAVEMENT * 16       # 224, the street's surface
V_CR_MAX = (16 * 16 - 192) // 8         # 8 - the deepest a 16-row view goes
EK_PICKUP, EK_DOOR, EK_ENEMY = 4, 6, 2
EF_TAKEN = 2

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


class City:
    """The running game on level 2, in the units the level is written in."""

    def __init__(self, sym, drones=False, level=LEVEL):
        self.sym = sym
        self.m = m = boot(sym, scroll=True)
        # One garage a level: level 1's opens onto level 2, level 2's onto
        # level 3. `frames` is the LAST door's.
        for lv in range(2, level + 1):
            m.poke(sym["GAME_STATE"], GS_CLEAR)
            self.frames = None
            for f in range(900):
                m.run_frames(1)
                # THE SYNC IS THE FSM COMING BACK TO PLAY, not LEVEL_OK -
                # that is still 1 from the level being left (8.1).
                if (m.peek(sym["GAME_STATE"]) == 0
                        and m.peek(sym["LEVEL_CUR"]) == lv - 1):
                    self.frames = f
                    m.run_frames(10)
                    break
        hdr = m.read_ram(sym["LEVEL_LVL"], 21)
        self.hdr = hdr
        self.w, self.h = hdr[5] | hdr[6] << 8, hdr[7] | hdr[8] << 8
        self.map = bytes(m.read_ram(sym["LEVEL_LVL"] + 21, self.w * self.h))
        self.attr = bytes(m.read_ram(sym["TILE_ATTR"], sym["TILE_ATTR_N"]))
        self.spawned = m.peek(sym["ENEMY_LIVE"])
        if not drones:
            m.poke(sym["ENEMY_LIVE"], 0)         # ENEMY_PICK finds nobody
        self.hw = self.game = 0

    # ---- the level, as the ENGINE reads it -------------------------
    def a(self, x, y):
        return self.attr[self.map[y * self.w + x]]

    def roof(self, x):
        """The highest row of column x she can stand on above the street,
        or None: a gap. Crates under a roof are under the roof."""
        for y in range(city.ROW_PAVEMENT):
            if self.a(x, y) & (TA_SOLID | TA_PLATFORM):
                return y
        return None

    def gaps(self):
        """(first column, width, near roof, far roof), west to east."""
        out, x = [], 0
        while x < self.w:
            if self.roof(x) is None:
                x0 = x
                while x < self.w and self.roof(x) is None:
                    x += 1
                out.append((x0, x - x0, self.roof(x0 - 1), self.roof(x)))
            x += 1
        return out

    def barricades(self):
        """Columns three crates high at street level, under a roof."""
        return [x for x in range(self.w)
                if all(self.a(x, y) & TA_SOLID
                       for y in range(city.ROW_PAVEMENT - 3, city.ROW_PAVEMENT))
                and self.roof(x) < city.ROW_PAVEMENT - 3]

    def ladders(self):
        return [x for x in range(self.w)
                if self.a(x, city.ROW_PAVEMENT - 1) & TA_CLIMB]

    def pit(self, x):
        return sum(1 for b in self.barricades() if b < x)

    def records(self, kind):
        n = self.byte("ENT_COUNT")
        t = self.m.read_ram(self.sym["ENT_TABLE"], n * 8)
        return [t[i:i + 8] for i in range(0, n * 8, 8) if t[i] == kind]

    # ---- her, in the same units -------------------------------------
    def word(self, name):
        a = self.sym[name]
        return self.m.peek(a) | self.m.peek(a + 1) << 8

    def byte(self, name):
        return self.m.peek(self.sym[name])

    def wx(self):
        return self.word("KARA_WX")

    def feet(self):
        return self.word("KARA_WY") + 64

    def col(self):
        """The tile column CLIMB_AT probes - the middle of her box."""
        return (self.wx() + 3) // 4

    def step(self):
        """One GAME frame, counting the hardware ones it took."""
        f0 = self.byte("FRAME_COUNT")
        for _ in range(8):
            self.m.run_frames(1)
            self.hw += 1
            if self.byte("FRAME_COUNT") != f0:
                self.game += (self.byte("FRAME_COUNT") - f0) & 255
                return

    def _settle(self):
        last, still = None, 0
        for _ in range(600):
            self.step()
            v = (self.byte("WORLD_X"), self.byte("WORLD_CR"), self.wx(),
                 self.feet())
            still = still + 1 if v == last else 0
            last = v
            if still > 6:
                break

    def _poke(self, wx, feet, facing):
        m, sym = self.m, self.sym
        m.poke(sym["KARA_WX"], wx & 255)
        m.poke(sym["KARA_WX"] + 1, wx >> 8)
        wy = feet - 64
        m.poke(sym["KARA_WY"], wy & 255)
        m.poke(sym["KARA_WY"] + 1, wy >> 8)
        m.poke(sym["KARA_VY"], 0)
        m.poke(sym["KARA_GROUND"], 1)
        m.poke(sym["PLAYER_HP"], 100)
        m.poke(sym["KARA_FACING"], facing)

    def put(self, wx, feet):
        """Stand her somewhere, facing right, with the camera where play
        would have it. A poke is a fair question for the windows: what is
        asked is the JUMP, and how she got to the run-up is the drive's,
        which is driven.

        BUT THE CAMERA IS PART OF THE QUESTION, AND IT WAS NOT WHERE PLAY
        PUTS IT. Poked straight to her run-up she was hundreds of bytes
        off the screen; PLAYER_SCREEN_X takes the difference modulo 256
        (CLAUDE.md 8.10), so the camera read her as far to the RIGHT,
        chased the map's right-hand end and parked there - WORLD_X 216 at
        every try of level 4's windows, her KARA_X 141 and 217. That is a
        state no player can reach, and it is not the same walk: in the
        push zone a walk is two bytes on one game frame in two (8.2).
        So the view is walked to her with the camera's own pan, never
        more than a screen away so its arithmetic is always the game's,
        and she is stood facing right, where it settles her at its trail
        mark - the camera of a heroine who has been walking this way.
        """
        for _ in range(30):
            vl = self.byte("WORLD_X") * 2
            if vl <= max(0, wx - 30) and wx - vl <= 60:
                break
            if wx - vl < 30:        # left of the view: from its left edge,
                self._poke(max(wx, vl + 4) if vl else wx, feet, 1)
            else:                   # facing left, which pans it left
                self._poke(min(wx, vl + 70), feet, 0)
            self._settle()
        self._poke(wx, feet, 0)
        self._settle()


def walk_to(c, col, frames=900):
    for _ in range(frames):
        if c.col() == col:
            break
        c.m.joystick(JOY["right"] if c.col() < col else JOY["left"])
        c.step()
    c.m.joystick(0)
    for _ in range(3):
        c.step()
    return c.col() == col


def walk_until_stuck(c, direction, frames=400):
    """Hold one way until she stops moving, and say where."""
    was, still = c.wx(), 0
    c.m.joystick(JOY[direction])
    for _ in range(frames):
        c.step()
        still = still + 1 if c.wx() == was else 0
        was = c.wx()
        if still >= 8:
            break
    c.m.joystick(0)
    return c.wx()


def climb_up(c, frames=900):
    was, still, start = c.feet(), 0, c.feet()
    c.m.joystick(JOY["up"])
    for _ in range(frames):
        c.step()
        now = c.feet()
        still = still + 1 if now == was else 0
        was = now
        if still >= 12 and now < start:
            break
    c.m.joystick(0)
    for _ in range(4):
        c.step()
    return c.feet()


def run_east(c, until_col, frames=900, press_at=-1):
    """Hold RIGHT and SHIFT and take every gap and every step the map
    has. A gap is pressed for on the first frame her box is at
    `press_at` bytes from its first byte column - one rule for all four
    - and a step the frame she is up against it. Stops on the ground at
    `until_col`, or on the street."""
    c.m.key_down('A')               # SHIFT, which an uppercase letter is
    pressed, events = set(), []
    for _ in range(frames):
        wx, feet, press = c.wx(), c.feet(), False
        if c.byte("KARA_GROUND"):
            if c.col() >= until_col or feet >= PAVEMENT:
                break
            ahead = (wx + 6) // 4               # the column past her box
            touch = (wx + 7) // 4               # ... and past her stride
            if ahead < c.w and c.roof(ahead) is None:
                gap = ahead
                while c.roof(gap - 1) is None:
                    gap -= 1
                if gap not in pressed and wx >= gap * 4 + press_at:
                    press = True
                    pressed.add(gap)
                    events.append(("gap", gap, wx, feet))
            elif (touch < c.w and c.roof(touch) is not None
                  and c.roof(touch) * 16 < feet and ("step", touch) not in pressed):
                press = True
                pressed.add(("step", touch))
                events.append(("step", touch, wx, feet))
        c.m.joystick(JOY["right"] | (JOY["up"] if press else 0))
        c.step()
        if events and events[-1][0] == "gap" and c.byte("KARA_GROUND"):
            if len(events[-1]) == 4:
                events[-1] += (c.feet(), c.wx())     # where it landed
    c.m.joystick(0)
    c.m.key_up('A')
    for _ in range(3):
        c.step()
    return events


def fall(c, direction, frames=400, joy_extra=0):
    """Walk one way until she has left the ground and landed. `fell` is
    the machine's own FALL_TOP, read the instant she starts down (8.4)."""
    top, air, hp0 = None, False, c.byte("PLAYER_HP")
    c.m.joystick(JOY[direction] | joy_extra)
    for i in range(frames):
        c.step()
        if i == 0 and joy_extra:
            c.m.joystick(JOY[direction])
        vy = c.byte("KARA_VY")
        if not c.byte("KARA_GROUND"):
            air = True
            if top is None and 0 < vy < 128:
                top = c.word("FALL_TOP")
        elif air:
            break
    c.m.joystick(0)
    for _ in range(3):
        c.step()
    fell = None if top is None else c.feet() - 64 - top
    return fell, hp0, c.byte("PLAYER_HP")


def tick(c):
    """ONE game frame, from the top of the loop to the top of the next -
    which is where INPUT_SCAN has not yet read the joystick.

    step() runs whole hardware frames until FRAME_COUNT moves, so where
    it stops is wherever the emulator's frame happens to end - measured,
    PCs 10,108 to 14,546, which is inside the next game frame's own work
    and past its INPUT_SCAN. An UP held for one step() was then read on
    some frames and never on others, and a press window came out with a
    frame of miss in its middle; and a sync after a step() runs a whole
    game frame more, which made a walk read as two bytes a frame.
    """
    f0 = c.byte("FRAME_COUNT")
    while c.byte("FRAME_COUNT") == f0:
        c.m.run_us(64)
    sync(c.m, c.sym, half=0)


def window(c, gap, w, near, far, start, run=True):
    """The GAME FRAMES, counted from the start of the run-up, on which
    UP starts a jump that comes down past `gap` - and whether running
    off its edge with no press at all crosses it. One machine, put back
    at the same run-up before each try, so the stride's phase is the
    start's.

    IT IS FRAMES AND IT USED TO BE BYTE COLUMNS, which is the same
    number only while she steps a byte a frame. The press went in on the
    first frame her box reached column X and the count was the distinct
    columns pressed at - and in the camera's push zone a walk is two
    bytes on one frame in two (8.2), so half the frames a player can
    press on were never asked about. Frames are what a player's timing
    is made of.

    AND A PRESS COUNTS ONLY IF IT STARTED A JUMP AND THAT JUMP LANDED
    ACROSS: the coyote frames past the lip are presses in the air that
    do start one (8.4), and a run off a downhill edge crosses with no
    jump at all (RUN_OFF), so "she ended up on the far roof" would count
    a late press that did nothing. Its first landing is the verdict -
    a press that clears the far roof and comes down on the step beyond
    it is a jump made, not one missed.
    """
    far_edge = (gap + w) * 4

    def attempt(t):
        c.put(start, near * 16)
        if run:
            c.m.key_down('A')
        jumped, landed = None, None
        sync(c.m, c.sym, half=0)
        for i in range(90):
            press = i == t
            # ... AND FROM THE ROOF SHE STARTED ON: a press after she has
            # come down somewhere else is a jump from the street, and off
            # a plaza's pavement one lands on the crate past its edge
            if (press and c.byte("KARA_GROUND")
                    and c.feet() != near * 16):
                break
            c.m.joystick(JOY["right"] | (JOY["up"] if press else 0))
            near_side = c.wx() + 5 < far_edge
            tick(c)
            if press:               # ... and from THIS side of the gap: a
                jumped = (near_side  # run that went off its edge is on
                          and c.byte("KARA_VY") >= 128)   # the far roof
            if t is not None and i > t and jumped is not None \
                    and c.byte("KARA_GROUND"):
                landed = (c.feet(), c.wx())
                break
            if t is None and c.byte("KARA_GROUND") and i > 2 \
                    and (c.feet() != near * 16 or c.wx() + 5 >= far_edge):
                landed = (c.feet(), c.wx())
                break
        c.m.joystick(0)
        if run:
            c.m.key_up('A')
        for _ in range(3):
            c.step()
        # ACROSS IS THE FAR ROOF'S LINE OR HIGHER, not merely off the
        # pavement: a plaza has a crate in it, and a take-off that comes
        # down on its top near the far side has not crossed anything
        over = (landed is not None and landed[0] <= far * 16
                and landed[1] + 5 >= far_edge)
        return over, jumped

    good, misses = [], 0
    for t in range(48):
        over, jumped = attempt(t)
        if over and jumped:
            good.append(t)
            misses = 0
        elif good:
            misses += 1
            if misses > 4:          # past the coyote frames: it is over
                break
    ran_off, _ = attempt(None)
    return good, ran_off


def main():
    sym = symbols()
    print("Level 2: the City, across the rooftops\n")
    names = city.tile_names()[1]
    shipped = open(os.path.join(BUILD, f"level_{LEVEL}.lvl"), "rb").read()

    c = City(sym)
    print("  out of level 1's garage:")
    check("the garage leads here", c.frames is not None,
          f"{c.frames} hardware frames, fade and all")
    check("... and it is one sector, not an environment",
          c.byte("LEVEL_ENV") == 0 and c.byte("LEVEL_CUR") == LEVEL - 1,
          f"LEVEL_ENV {c.byte('LEVEL_ENV')} - no art came with it")
    check("the level is the file on the disc",
          bytes(c.hdr) + c.map == shipped[:21 + 2048]
          and (c.w, c.h, c.hdr[3], c.hdr[9]) == (128, 16, LEVEL, 1)
          and c.byte("LEVEL_OK") == 1,
          f"{c.w}x{c.h}, level {c.hdr[3]}, tileset {c.hdr[9]}")
    check("the drones are in it", c.spawned == 3,
          f"{c.spawned} spawned, held off for the drive and back on below")

    # ---- the door she came out of, drawn OPEN ----------------------
    def name(x, y):
        t = c.map[y * c.w + x]
        return names[t] if t < len(names) else f"#{t}"
    opening = [x for x in range(c.w - 3)
               if name(x + 1, city.ROW_PAVEMENT - 1) == "open_ramp"
               and name(x + 2, city.ROW_PAVEMENT - 1) == "open_ramp"]
    g0 = opening[0] if opening else None
    check("it opens on a garage drawn OPEN",
          g0 is not None
          and all(name(g0 + k, y) == "void"
                  for k in (1, 2) for y in range(10, 13))
          and name(g0 + 2, 9) == "lock_green",
          f"columns {g0}..{g0 + 3}: open_ramp under three rows of void and a "
          f"green lock - two tiles nothing had ever placed" if g0 is not None
          else "no open_ramp anywhere")
    check("... and she comes out of it onto the street",
          c.feet() == PAVEMENT and g0 is not None and c.col() > g0 + 3
          and c.byte("WORLD_CR") == V_CR_MAX,
          f"feet {c.feet()}, column {c.col()}, WORLD_CR "
          f"{c.byte('WORLD_CR')} of {V_CR_MAX}")

    # ---- the level as the engine reads it --------------------------
    gaps, bars, ups = c.gaps(), c.barricades(), c.ladders()
    print(f"    gaps {[(g, w, n, f) for g, w, n, f in gaps]}")
    print(f"    barricades {bars}, ladders {ups}")
    check("four gaps between five roofs", len(gaps) == 4,
          "each one a run-jump of a kind measured below")
    check("no gap is two rows up, or four tiles on the level",
          all((w, f - n) in city.RUN_JUMPS for _, w, n, f in gaps),
          "the two shapes no press of UP clears")
    lastroof = gaps[-1][0] + gaps[-1][1]
    check("every pit has one ladder out, onto the roof she jumped FROM",
          all(any(c.pit(u) == c.pit(g) and u < g for u in ups)
              and not any(c.pit(u) == c.pit(g) and u > g for u in ups)
              for g, _, _, _ in gaps),
          "so a miss costs the fall and the climb, never the jump")
    check("... and the key's roof has no ladder at all",
          not any(u >= lastroof for u in ups),
          f"nothing at or past column {lastroof} - the last jump is the "
          f"only way on")

    # ---- the street is cut ------------------------------------------
    print("\n  the street is cut, so the roofs are the only way along:")
    stopped = walk_until_stuck(c, "right")
    check("walking the street from the garage, she stops at the first "
          "barricade", bars and stopped + 6 <= bars[0] * 4,
          f"stopped with her box at bytes {stopped}..{stopped + 5}, the "
          f"crates at {bars[0] * 4 if bars else '-'}")
    cc = City(sym)
    crate = names.index("crate")
    cc.m.poke(sym["TILE_ATTR"] + crate, 0)
    gone = walk_until_stuck(cc, "right", frames=200)
    check("... and with the crate's TA_SOLID taken off she walks on past it",
          bars and gone > bars[0] * 4 + 8,
          f"to byte {gone} - so it is the barricade, and not the drive, "
          f"that stopped her")
    del cc

    # ---- the drive ---------------------------------------------------
    print("\n  across the rooftops, from the joystick:")
    ok = walk_to(c, ups[0])
    top = climb_up(c)
    check("up the ladder from the street", ok and top == c.roof(ups[0]) * 16,
          f"feet {top}, the roof line {c.roof(ups[0]) * 16}; "
          f"WORLD_CR {c.byte('WORLD_CR')}")
    sync(c.m, sym, half=0)          # anchored: CLAUDE.md 10
    c.hw = c.game = 0
    keyx = next((r[1] | r[2] << 8) // 8 for r in c.records(EK_PICKUP)
                if r[6] == city.PU_KEY)
    ev = run_east(c, keyx)
    jumps = [e for e in ev if e[0] == "gap"]
    steps = [e for e in ev if e[0] == "step"]
    for e in ev:
        print(f"      {e[0]:4s} at {e[1]:3d}: pressed at byte {e[2]}, feet "
              f"{e[3]}" + (f" -> landed {e[4]} at byte {e[5]}"
                           if len(e) > 4 else ""))
    want = {g: f * 16 for g, _, _, f in gaps}
    check("all four gaps jumped, each onto the far roof",
          len(jumps) == 4 and all(len(e) > 4 and e[4] == want[e[1]]
                                  for e in jumps),
          "pressed at one rule: the byte column before the gap's first")
    check("... and the two steps up to the tall roof",
          len(steps) == 2, f"{[s[1] for s in steps]}, a row each")
    check("the clip on the tall roof and the key on the last",
          c.byte("AMMO_RESERVE") == 42 and c.byte("KEYS_COUNT") == 1,
          f"reserve {c.byte('AMMO_RESERVE')}, keys {c.byte('KEYS_COUNT')}, "
          f"HP {c.byte('PLAYER_HP')}")
    # ONE FRAME OF IT IS DROPPED, AND IT IS NOT THE ANCHOR. This read
    # "the loop held" with a frame of slack; measured frame by frame, the
    # extra hardware frame is a game frame that took three - the first
    # jump's TAKE-OFF at a run (CLAUDE.md 8.16).
    check("... and the loop dropped one frame at most, at a take-off",
          c.hw <= 2 * c.game + 1,
          f"{c.game} game frames in {c.hw} hardware ones: "
          f"{c.hw - 2 * c.game} dropped")

    # ---- the way out -------------------------------------------------
    print("\n  and the way out:")
    fell, hp0, hp1 = fall(c, "left")
    check("walking off the key's roof is free",
          fell == city.FALL_FREE and hp1 == hp0 and c.feet() == PAVEMENT,
          f"{fell} lines by the machine's own FALL_TOP - FALL_FREE exactly "
          f"- and HP {hp0} -> {hp1}")
    door = next((r[1] | r[2] << 8) // 8 for r in c.records(EK_DOOR))
    check("... into the pit the way out is in",
          c.pit(c.col()) == c.pit(door),
          f"she is at column {c.col()}, the garage at {door}")
    walk_to(c, door + 2)
    c.m.joystick(JOY["up"])
    c.step()
    c.m.joystick(0)
    for _ in range(10):
        c.step()
        if c.byte("GAME_STATE"):
            break
    check("UP at the garage with the key opens it",
          c.byte("GAME_STATE") == GS_CLEAR,
          f"GAME_STATE {c.byte('GAME_STATE')}")
    hp, res = c.byte("PLAYER_HP"), c.byte("AMMO_RESERVE")
    on = None
    for f in range(900):
        c.m.run_frames(1)
        if c.byte("LEVEL_CUR") == LEVEL and c.byte("GAME_STATE") == 0:
            on = f
            break
    check("... and it leads to level 3, which is the next door along",
          on is not None and c.byte("LEVEL_ENV") == 0
          and c.byte("PLAYER_HP") == hp and c.byte("AMMO_RESERVE") == res
          and c.byte("KEYS_COUNT") == 0,
          f"after {on} hardware frames: HP {c.byte('PLAYER_HP')} and reserve "
          f"{c.byte('AMMO_RESERVE')} came with her, the key did not "
          f"(keys {c.byte('KEYS_COUNT')})")
    del c

    # ---- under fire --------------------------------------------------
    print("\n  the same drive with the drones in it:")
    d = City(sym, drones=True)
    walk_to(d, ups[0])
    climb_up(d)
    sync(d.m, sym, half=0)
    d.hw = d.game = 0
    ev = run_east(d, keyx)
    check("she crosses the rooftops under fire",
          d.byte("KEYS_COUNT") == 1 and d.byte("PLAYER_HP") > 0
          and len([e for e in ev if e[0] == "gap"]) == 4,
          f"HP 100 -> {d.byte('PLAYER_HP')}, keys {d.byte('KEYS_COUNT')}, "
          f"{d.game} game frames in {d.hw} hardware ones")
    del d

    # ---- a miss -----------------------------------------------------
    print("\n  a miss, and what it costs:")
    mi = City(sym)
    walk_to(mi, ups[0])
    climb_up(mi)
    g2, w2, n2, f2 = gaps[1]
    run_east(mi, g2 - 3)
    # A WALKING press five bytes before the gap. The arc carries a walk
    # eight, so it comes down where the near roof has already run out:
    # a jump that falls short - measured from its APEX, which is what a
    # miss is.
    mi.m.joystick(JOY["right"])
    for _ in range(200):
        if mi.wx() >= g2 * 4 - 5:
            break
        mi.step()
    fell, hp0, hp1 = fall(mi, "right", joy_extra=JOY["up"])
    cost = city.miss_cost(n2)
    check("a walking jump pressed too early falls into the pit",
          mi.feet() == PAVEMENT and mi.pit(mi.col()) == mi.pit(g2),
          f"feet {mi.feet()}, column {mi.col()}")
    check("... and it costs what the tool says, measured from the apex",
          fell is not None and hp0 - hp1 == fell - city.FALL_FREE == cost,
          f"fell {fell} lines, HP {hp0} -> {hp1}: {cost} predicted")
    out = [u for u in ups if mi.pit(u) == mi.pit(g2)]
    walk_to(mi, out[0])
    top = climb_up(mi)
    check("the pit's one ladder puts her back where she jumped from",
          top == n2 * 16 and mi.col() < g2,
          f"feet {top}, column {mi.col()} - the near roof, so the jump is "
          f"still ahead of her")
    ev = run_east(mi, g2 + w2 + 2)
    check("... and the jump at a run makes it",
          mi.feet() == f2 * 16 and mi.col() >= g2 + w2,
          f"feet {mi.feet()}, column {mi.col()}")

    # ---- how high she goes, which is what the level is shaped by ----
    print("\n  the jump is 28 lines, and a solid roof two rows up is a wall:")
    for _ in range(6):
        mi.step()
    floor, low = mi.feet(), mi.feet()
    mi.m.joystick(JOY["up"])
    mi.step()
    mi.m.joystick(0)
    for _ in range(12):
        mi.step()
        low = min(low, mi.feet())
    check("a jump rises 28 lines, under the 32 of two rows",
          floor - low == city.JUMP_RISE,
          f"feet {floor} -> {low}: gravity is added before the first move, "
          f"so -17 is never a step - 13+9+5+1")
    # THE CONTROL IS THE STEP. Take the middle roof out of the WORKING
    # map - what collision reads - and the tall roof is two rows of
    # solid straight up from where she stands.
    roofs = [mi.roof(x) for x in range(mi.w)]
    top = min(r for r in roofs if r is not None)
    tall = roofs.index(top)
    base = sym["MAP_ADDR"]
    fill, roof_m = names.index("far_fill"), names.index("roof_m")
    low_row = mi.roof(tall - 3)
    mi.map = bytearray(mi.map)          # ... and the driver's copy with it
    for x in range(tall - 2, tall):
        for y, t in ((low_row - 1, fill), (low_row, roof_m)):
            mi.m.poke(base + y * mi.w + x, t)
            mi.map[y * mi.w + x] = t
    run_east(mi, tall + 3, frames=80)
    check("... and with the middle step taken out, she cannot get up",
          mi.col() < tall and mi.feet() == low_row * 16,
          f"stuck at column {mi.col()} on row {mi.feet() // 16}, the tall "
          f"roof at {tall} two rows above her")
    del mi

    # ---- the medkit is under the jump that needs it -----------------
    print("\n  and the medkit, under the jump that goes up:")
    mk = City(sym)
    g3, w3, n3, f3 = gaps[2]
    medx = next((r[1] | r[2] << 8) // 8 for r in mk.records(EK_PICKUP)
                if r[6] == city.PU_MEDKIT)
    check("the medkit is in the pit under the hardest jump",
          g3 <= medx < g3 + w3 and f3 < n3,
          f"column {medx}, under the gap at {g3} - the one that goes UP")
    mk.put(g3 * 4 - 20, n3 * 16)
    mk.m.joystick(JOY["right"])
    for _ in range(200):                # the same early walking press
        if mk.wx() >= g3 * 4 - 5:
            break
        mk.step()
    fell, hp0, hp1 = fall(mk, "right", joy_extra=JOY["up"])
    taken = [r for r in mk.records(EK_PICKUP) if r[6] == city.PU_MEDKIT]
    check("a walk pressed early misses, and the medkit pays for it",
          mk.feet() == PAVEMENT and fell is not None
          and fell - city.FALL_FREE == city.miss_cost(n3)
          and hp1 == 100 and taken and taken[0][5] & EF_TAKEN,
          f"fell {fell}, {fell - city.FALL_FREE if fell else '-'} points, "
          f"and HP is {hp1} again with the medkit taken")
    del mk

    # ---- the windows, measured on the level itself -------------------
    print("\n  every gap's take-off window, at both stride phases:")
    wm = City(sym)
    walk_to(wm, ups[0])
    climb_up(wm)
    all_match, runoff_match = True, True
    for g, w, n, f in gaps:
        got, offs = [], 0
        for phase in (0, 1):
            start = g * 4 - 24 + phase
            good, ran_off = window(wm, g, w, n, f, start)
            got.append(len(good))
            offs += ran_off
        runoff_match = runoff_match and offs == (
            1 if (w, f - n) in city.RUN_OFF else 0)
        walks = [len(window(wm, g, w, n, f, g * 4 - 24 + phase,
                            run=False)[0]) for phase in (0, 1)]
        want = city.RUN_JUMPS[w, f - n]
        wwant = city.WALK_JUMPS.get((w, f - n), 0)
        # A RUN'S WINDOW IS THE SHAPE'S AND A WALK'S IS A FLOOR. With the
        # camera where play has it and the press at the top of a game
        # frame (put(), tick()), a run comes out the same on every level
        # for every gap of a shape; a walk steps two bytes on one frame
        # in two in the push zone, so where the lip falls in that rhythm
        # is the gap's, and the same shape measures 1 here and 2 on
        # level 4 (make_city_map.py).
        ok = tuple(got) == want and min(walks) >= wwant
        all_match = all_match and ok
        print(f"      gap at {g:3d}, {w} wide, row {n} -> {f}: running "
              f"{got[0]}/{got[1]} frames, walking {walks[0]}/{walks[1]}"
              f"{'' if ok else '  <- the tool says ' + str(want) + ', walking at least ' + str(wwant)}")
    check("they are the windows make_city_map.py was built against",
          all_match, "a run's exactly, at both stride phases, and a walk's "
          "at least")
    check("... and a run off the edge crosses the downhill ones only",
          runoff_match, "at one stride phase of the two, and the level "
          "and the uphill gap never")
    wins = [city.RUN_JUMPS[w, f - n] for _, w, n, f in gaps]
    hard = wins[2]
    check("the jump UP is still the tightest",
          all(sum(hard) < sum(o) for i, o in enumerate(wins) if i != 2),
          f"{hard} frames against {[o for i, o in enumerate(wins) if i != 2]}")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
