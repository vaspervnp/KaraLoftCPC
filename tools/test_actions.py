#!/usr/bin/env python3
"""The action state machine of CLAUDE.md 8.4, driven one transition at a
time.

ACT_UPDATE is called from a stub with the input bytes and the ground
flag poked directly, rather than through the keyboard: the emulator has
no code for SHIFT, and a test that cannot press SHIFT cannot check the
RUN state at all. What the KEYBOARD does is a separate question and the
last section here asks it for the keys it can press.

Every state's frames are checked against the blob the exporter actually
shipped - nine cels of the drawn sheet are not in it (CLAUDE.md 7.1) -
so a re-export with a different frame count fails here rather than
drawing somebody's elbow.
"""
import os
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import boot, symbols, sync                        # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
STUB = 0xA000

IN_UP, IN_DOWN, IN_LEFT, IN_RIGHT = 1, 2, 4, 8
IN_FIRE, IN_SPARE, IN_PAUSE, IN_RUN = 16, 32, 64, 128
# THE ROLL IS DOWN AND A DIRECTION, not Z. It is a PRESS of either half
# while the other is held (src/action.asm), which is what stops a
# committed 8-cel roll re-triggering on the frame it ends.
ROLL_NOW = IN_DOWN | IN_RIGHT
ROLL_PRESS = IN_RIGHT
KARA_W = 12          # her box, in screen bytes

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def incs():
    """The FIRST/COUNT constants and the duration tables, from the art."""
    out = {}
    for blob in ("kcore", "kextra"):
        p = os.path.join(ROOT, "build", "levels", "_shared", blob + ".inc")
        dur = []
        for line in open(p):
            line = line.split(";")[0].strip()
            if " equ " in line:
                k, v = line.split(" equ ")
                out[k.strip()] = int(v.strip())
            elif line.startswith("db "):
                dur += [int(n) for n in line[3:].split(",")]
        out[blob.upper() + "_DURATION"] = dur
    return out


class Sim:
    def __init__(self, m, sym):
        self.m, self.sym = m, sym
        a = sym["ACT_UPDATE"]
        self.code = bytes([0xF3, 0xCD, a & 0xFF, a >> 8, 0x18, 0xFE])

    def poke(self, now=0, pressed=0, ground=1):
        s, m = self.sym, self.m
        m.poke(s["INPUT_NOW"], now)
        m.poke(s["INPUT_PRESSED"], pressed)
        m.poke(s["KARA_GROUND"], ground)

    def step(self, now=0, pressed=0, ground=1):
        self.poke(now, pressed, ground)
        self.m.write_ram(STUB, self.code)
        self.m.set_pc(STUB)
        for _ in range(20000):
            self.m.run_us(1)
            if self.m.pc == STUB + 4:
                break
        else:
            raise SystemExit("ACT_UPDATE ran away")
        return self.state()

    def state(self):
        s, m = self.sym, self.m
        return dict(st=m.peek(s["KARA_STATE"]), anim=m.peek(s["KARA_ANIM"]),
                    frame=m.peek(s["KARA_FRAME"]), set=m.peek(s["KARA_SET"]),
                    timer=m.peek(s["KARA_TIMER"]), done=m.peek(s["KARA_DONE"]))

    def force(self, st):
        """Drop her into a state as if ACT_UPDATE had just entered it.

        ANIM = 255 and not 0: entering a state leaves the cel index one
        BEFORE the first, because the animator runs the timer down and
        steps in the same call. Poking 0 here would skip cel 0 and the
        test would be measuring its own setup.
        """
        self.m.poke(self.sym["KARA_STATE"], st)
        self.m.poke(self.sym["KARA_DONE"], 0)
        self.m.poke(self.sym["KARA_ANIM"], 255)
        self.m.poke(self.sym["KARA_TIMER"], 1)


def main():
    sym = symbols()
    for n in ("ACT_UPDATE", "KARA_STATE", "KARA_SET", "KARA_ANIM",
              "KARA_TIMER", "KARA_DONE", "INPUT_NOW", "INPUT_PRESSED"):
        if n not in sym:
            check(f"{n} is linked", False, "rebuild first")
            return 1
    K = incs()
    m = boot(sym)
    sync(m, sym)
    sim = Sim(m, sym)

    ST = dict(IDLE=0, WALK=1, RUN=2, JUMP=3, ROLL=4, AIM=5, FIRE=6)
    CORE, EXTRA = 0, 1
    # state -> (set, first, count, loops)
    SPEC = {
        "IDLE": (CORE,  K["KCORE_IDLE_FIRST"],       K["KCORE_IDLE_COUNT"], True),
        "WALK": (CORE,  K["KCORE_WALK_FIRST"],       K["KCORE_WALK_COUNT"], True),
        "RUN":  (EXTRA, K["KEXTRA_RUN_FIRST"],       K["KEXTRA_RUN_COUNT"], True),
        "JUMP": (CORE,  K["KCORE_JUMP_FIRST"],       K["KCORE_JUMP_COUNT"], False),
        "ROLL": (EXTRA, K["KEXTRA_ROLL_FIRST"],      K["KEXTRA_ROLL_COUNT"], False),
        "AIM":  (CORE,  K["KCORE_SHOOT_DRAW_FIRST"], K["KCORE_SHOOT_DRAW_COUNT"], False),
        "FIRE": (CORE,  K["KCORE_SHOOT_FIRST"],      K["KCORE_SHOOT_COUNT"], False),
    }
    print("\n  the states, as CLAUDE.md 8.4 tabulates them:")
    for n, (s, f, c, lp) in SPEC.items():
        print(f"    {n:<5} {'kextra' if s else 'kcore ' }  frames {f}-{f + c - 1}"
              f"  {'loops' if lp else 'holds'}")

    # -----------------------------------------------------------------
    # 1. Every transition in the table.
    # -----------------------------------------------------------------
    print("\n  transitions:")
    cases = [
        ("nothing held, on the ground",      "IDLE", dict()),
        ("right held",                       "WALK", dict(now=IN_RIGHT)),
        ("left held",                        "WALK", dict(now=IN_LEFT)),
        ("SHIFT and right",                  "RUN",  dict(now=IN_RIGHT | IN_RUN)),
        ("SHIFT with no direction",          "IDLE", dict(now=IN_RUN)),
        ("off the ground",                   "JUMP", dict(ground=0)),
        ("off the ground, still holding right", "JUMP",
         dict(now=IN_RIGHT, ground=0)),
        ("DOWN held, a direction pressed",   "ROLL", dict(pressed=ROLL_PRESS,
                                                          now=ROLL_NOW)),
        ("SPACE held",                       "AIM",  dict(now=IN_FIRE)),
        ("SPACE held while walking",         "AIM",  dict(now=IN_FIRE | IN_RIGHT)),
    ]
    wrong = 0
    for name, want, kw in cases:
        sim.force(ST["IDLE"])
        got = sim.step(**kw)
        ok = got["st"] == ST[want]
        wrong += not ok
        print(f"    {'ok ' if ok else 'NO '} {name:<38} -> "
              f"{[k for k, v in ST.items() if v == got['st']][0]}")
    check("every entry condition reaches its state", wrong == 0, f"{wrong} wrong")

    # ENTERING a state must show its FIRST cel, and this has to be driven
    # through the transition rather than by poking KARA_ANIM - the whole
    # bug was in what entry leaves behind, so a test that sets that up
    # itself is testing its own setup. Every state is entered from
    # somewhere else and the very next frame is inspected.
    print("\n  the first frame of a state is its FIRST cel:")
    entry = dict(IDLE=dict(), WALK=dict(now=IN_RIGHT),
                 RUN=dict(now=IN_RIGHT | IN_RUN), JUMP=dict(ground=0),
                 ROLL=dict(now=ROLL_NOW, pressed=ROLL_PRESS),
                 AIM=dict(now=IN_FIRE))
    wrong = 0
    for name, kw in entry.items():
        # come from somewhere that is NOT it, and is not committed
        sim.force(ST["WALK"] if name != "WALK" else ST["IDLE"])
        sim.step(**(dict(now=IN_RIGHT) if name != "WALK" else dict()))
        g = sim.step(**kw)
        want = SPEC[name][1]
        ok = g["st"] == ST[name] and g["frame"] == want
        wrong += not ok
        print(f"    {'ok ' if ok else 'NO '} {name:<5} opens on frame "
              f"{g['frame']}, want {want}")
    # ... and FIRE, which can only be entered by releasing from AIM
    sim.force(ST["IDLE"])
    sim.step(now=IN_FIRE)
    g = sim.step(now=0)
    ok = g["st"] == ST["FIRE"] and g["frame"] == SPEC["FIRE"][1]
    wrong += not ok
    print(f"    {'ok ' if ok else 'NO '} FIRE  opens on frame {g['frame']}, "
          f"want {SPEC['FIRE'][1]}")
    check("no state opens a cel late", wrong == 0,
          f"{wrong} of 7 skipped their first cel")

    # a roll in the air must NOT start
    sim.force(ST["IDLE"])
    got = sim.step(pressed=ROLL_PRESS, now=ROLL_NOW, ground=0)
    check("a roll cannot start in the air", got["st"] == ST["JUMP"],
          "it is a dodge, not a glide")

    # the gun: draw, hold, release
    sim.force(ST["IDLE"])
    a = sim.step(now=IN_FIRE)
    b = sim.step(now=IN_FIRE)
    c = sim.step(now=0)
    check("SPACE down aims, and keeps aiming while it is held",
          a["st"] == ST["AIM"] and b["st"] == ST["AIM"])
    check("SPACE up FIRES, and only from a draw", c["st"] == ST["FIRE"])
    sim.force(ST["IDLE"])
    d = sim.step(now=0)
    check("...and not from standing still", d["st"] == ST["IDLE"],
          "a release that never drew must not fire")

    # -----------------------------------------------------------------
    # 2. The committed states: nothing interrupts them.
    # -----------------------------------------------------------------
    print("\n  a roll and a shot run to the end whatever the input does:")
    for name in ("ROLL", "FIRE"):
        s, first, count, _ = SPEC[name]
        sim.force(ST[name])
        seen, frames, n = [], [], 0
        while n < 400:
            # every input EXCEPT a fresh roll press: INPUT_PRESSED is
            # edge-detected, so re-asserting the roll every frame is a
            # key being pressed again, which is allowed to start a
            # second roll and would be testing nothing.
            g = sim.step(now=IN_LEFT | IN_RIGHT | IN_FIRE | IN_RUN,
                         pressed=IN_UP)
            n += 1
            seen.append(g["st"])
            frames.append(g["frame"])
            if g["st"] != ST[name]:
                break
        held = sum(1 for x in seen if x == ST[name])
        cels = sorted(set(frames[:held]))
        want = list(range(first, first + count))
        print(f"    {name:<5} held for {held} frames, cels {cels}")
        check(f"{name} plays every one of its {count} cels, in order",
              cels == want, f"saw {cels}, want {want}")
        check(f"{name} is not interrupted by any input",
              held > count, f"{held} frames for {count} cels")
        check(f"{name} ends by itself", seen[-1] != ST[name])

    # -----------------------------------------------------------------
    # 3. The cel rate is the ART's, not a constant.
    # -----------------------------------------------------------------
    print("\n  cel timing against the durations Aseprite recorded:")
    bad = 0
    for name in ("IDLE", "WALK", "RUN"):
        s, first, count, _ = SPEC[name]
        dur = K[("KCORE", "KEXTRA")[s] + "_DURATION"]
        sim.force(ST[name])
        inp = dict(IDLE=dict(), WALK=dict(now=IN_RIGHT),
                   RUN=dict(now=IN_RIGHT | IN_RUN))[name]
        held = {}
        for _ in range(sum(dur[first:first + count]) * 2):
            g = sim.step(**inp)
            held[g["frame"]] = held.get(g["frame"], 0) + 1
        want = {first + i: dur[first + i] * 2 for i in range(count)}
        got = {k: v for k, v in sorted(held.items())}
        same = got == want
        bad += not same
        print(f"    {name:<5} frames held {list(got.values())}, "
              f"art says {[dur[first + i] for i in range(count)]} x2")
        if not same:
            print(f"          want {want}")
    check("each cel is held for exactly the frames the art asks", bad == 0,
          f"{bad} of 3 states wrong")

    # a state that loops comes back to its first cel
    s, first, count, _ = SPEC["WALK"]
    dur = K["KCORE_DURATION"]
    sim.force(ST["WALK"])
    seq = []
    for _ in range(sum(dur[first:first + count]) + 2):
        seq.append(sim.step(now=IN_RIGHT)["frame"])
    check("a looping state wraps to its first cel",
          seq[0] == first and seq[-1] == first and len(set(seq)) == count,
          f"{sorted(set(seq))}")

    # a holding state stops on its last
    s, first, count, _ = SPEC["JUMP"]
    sim.force(ST["JUMP"])
    for _ in range(200):
        g = sim.step(ground=0)
    check("a holding state stops on its last cel and stays there",
          g["frame"] == first + count - 1 and g["done"] == 1,
          f"frame {g['frame']}, want {first + count - 1}")

    # -----------------------------------------------------------------
    # 4. The set comes with the state, because run and roll are a
    #    different blob in a different bank.
    # -----------------------------------------------------------------
    print("\n  the blob each state draws from:")
    bad = 0
    for name, (want_set, first, count, _) in SPEC.items():
        sim.force(ST[name])
        g = sim.step(**dict(IDLE=dict(), WALK=dict(now=IN_RIGHT),
                            RUN=dict(now=IN_RIGHT | IN_RUN),
                            JUMP=dict(ground=0), ROLL=dict(),
                            AIM=dict(now=IN_FIRE), FIRE=dict())[name])
        ok = g["set"] == want_set and first <= g["frame"] < first + count
        bad += not ok
        print(f"    {'ok ' if ok else 'NO '} {name:<5} set "
              f"{'kextra' if g['set'] else 'kcore '} frame {g['frame']}")
    check("run and roll draw from kextra, the rest from kcore", bad == 0,
          f"{bad} wrong")

    # -----------------------------------------------------------------
    # 4b. RUN is two bytes a frame, which is the CRTC's scroll step.
    #
    # Driven through PLAYER_UPDATE with the input poked, for the same
    # reason as everything above: there is no key code for SHIFT here,
    # so the only way to exercise IN_RUN at all is to set the bit.
    # -----------------------------------------------------------------
    print("\n  how far a frame carries her:")

    def travel(now, frames=8, wx=40):
        """Bytes she covers in `frames` calls of PLAYER_UPDATE.

        FRAME_COUNT is stepped by hand: inside the camera's push zone
        the walk moves only on the frames the camera does, and the loop
        is what normally advances the counter they agree on. Leaving it
        still made a walk in the push zone read as zero - which is the
        engine being right and the harness being wrong, and worth the
        two lines to get right rather than testing only the free zone.
        """
        s = sym
        m.poke(s["KARA_WX"], wx)
        m.poke(s["KARA_WX"] + 1, 0)
        m.poke(s["WORLD_X"], 0)
        m.poke(s["KARA_GROUND"], 1)
        a = s["PLAYER_UPDATE"]
        code = bytes([0xF3, 0xCD, a & 0xFF, a >> 8, 0x18, 0xFE])
        for i in range(frames):
            m.poke(s["INPUT_NOW"], now)
            m.poke(s["INPUT_PRESSED"], 0)
            m.poke(s["FRAME_COUNT"], i)
            m.write_ram(STUB, code)
            m.set_pc(STUB)
            for _ in range(40000):
                m.run_us(1)
                if m.pc == STUB + 4:
                    break
        return (m.peek(s["KARA_WX"]) | m.peek(s["KARA_WX"] + 1) << 8) - wx

    walked = travel(IN_RIGHT)
    ran = travel(IN_RIGHT | IN_RUN)
    still = travel(0)
    left = travel(IN_LEFT)
    print(f"    free zone, 8 frames: walking {walked} bytes, running "
          f"{ran}, still {still}, left {left}")
    check("a walk is one byte a frame", walked == 8, f"{walked} in 8 frames")
    check("SHIFT doubles it to the CRTC's scroll step", ran == 16,
          f"{ran} in 8 frames, want 16")
    check("no direction, no movement", still == 0, f"{still}")
    check("left goes left", left == -8, f"{left}")

    # In the PUSH zone she moves the way the camera does, or the picture
    # doubles (CLAUDE.md 8.2): two bytes on the camera's frame and none
    # between. A run is two bytes EVERY frame, which is the camera's own
    # step, so it scrolls every frame and a walk every other one.
    pwalk = travel(IN_RIGHT, wx=140)
    prun = travel(IN_RIGHT | IN_RUN, wx=140)
    print(f"    push zone, 8 frames: walking {pwalk} bytes, running {prun}")
    check("in the push zone a walk keeps the camera's pace, not its own",
          pwalk == 8, f"{pwalk} in 8 frames, want 8 - two bytes every other")
    check("...and a run moves every frame, because the camera can", prun == 16,
          f"{prun} in 8 frames, want 16")

    # -----------------------------------------------------------------
    # 4c. A round leaves the muzzle the way she is facing.
    #
    # bullets.asm read KARA_FACING with the opposite convention to
    # player.asm, and for two modules nothing noticed: the Module 1-3
    # screen never writes the flag, so it sat at its initialiser and
    # both readings agreed by accident. The first shot fired from the
    # scrolling demo went backwards out of her own muzzle.
    # -----------------------------------------------------------------
    print("\n  which way a round goes:")
    B, STRIDE = sym["BULLETS"], 5

    def shoot(facing):
        for i in range(14):                 # empty the pool
            m.poke(B + i * STRIDE, 0)
        m.poke(sym["KARA_FACING"], facing)
        m.poke(sym["KARA_X"], 40)
        m.poke(sym["KARA_Y"], 40)
        m.poke(sym["MAG_LEFT"], 7)
        m.poke(sym["MAG_RIGHT"], 7)
        m.poke(sym["RELOAD_TIMER"], 0)
        for r in (sym["FIRE_BULLET"], sym["UPDATE_BULLETS"],
                  sym["UPDATE_BULLETS"]):
            code = bytes([0xF3, 0xCD, r & 0xFF, r >> 8, 0x18, 0xFE])
            m.write_ram(STUB, code)
            m.set_pc(STUB)
            for _ in range(40000):
                m.run_us(1)
                if m.pc == STUB + 4:
                    break
            if r == sym["FIRE_BULLET"]:
                x0 = next(m.peek(B + i * STRIDE + 1) for i in range(14)
                          if m.peek(B + i * STRIDE))
        x1 = next(m.peek(B + i * STRIDE + 1) for i in range(14)
                  if m.peek(B + i * STRIDE))
        return x0, x1

    rx0, rx1 = shoot(0)
    lx0, lx1 = shoot(1)
    print(f"    facing right (0): spawned at byte {rx0}, two frames on {rx1}")
    print(f"    facing left  (1): spawned at byte {lx0}, two frames on {lx1}")
    check("facing right, the round travels right", rx1 > rx0,
          f"{rx0} -> {rx1}")
    check("facing left, the round travels left", lx1 < lx0, f"{lx0} -> {lx1}")
    check("the muzzle is mirrored with her, not left on one side",
          rx0 > 40 and lx0 < 40 + KARA_W // 2,
          f"right spawns at {rx0}, left at {lx0}, her box is 40..{40 + KARA_W - 1}")

    # -----------------------------------------------------------------
    # 5. The keys the emulator can actually press.
    # -----------------------------------------------------------------
    print("\n  what the keyboard scan makes of the keys it can be sent:")
    from cpc import CPC
    m2 = CPC()
    m2.run_frames(150)
    m2.insert_disc(os.path.abspath(os.path.join(ROOT, "build", "kara.dsk")))
    m2.type_text('RUN"DISC\n')
    m2.run_frames(400)
    m2.poke(sym["DEMO_TIMER"], 2)
    m2.poke(sym["DEMO_TIMER"] + 1, 0)
    m2.run_frames(150)

    def held(key, frames=8):
        m2.key_down(key)
        m2.run_frames(frames)
        v = m2.peek(sym["INPUT_NOW"])
        m2.key_up(key)
        m2.run_frames(4)
        return v

    got_z = held("z")
    check("Z is not bound to anything any more", got_z == 0,
          f"INPUT_NOW = &{got_z:02X} - the roll is DOWN + a direction")
    got_sp = held(" ")
    check("SPACE reads as IN_FIRE", got_sp == IN_FIRE,
          f"INPUT_NOW = &{got_sp:02X}")
    idle = m2.peek(sym["INPUT_NOW"])
    check("nothing held reads as nothing", idle == 0, f"INPUT_NOW = &{idle:02X}")
    print("    NOTE: SHIFT has no key code in this emulator, so IN_RUN's\n"
          "    BINDING is unproven here - its behaviour is section 1.")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(fails))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
