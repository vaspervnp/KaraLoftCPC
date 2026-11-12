#!/usr/bin/env python3
"""test_sound.py - the AY, read back out of the chip (CLAUDE.md 11 step 9).

Nobody here can listen, so nothing in this suite asks whether the music
is good. It asks whether the player plays what was written, and whether
the game around it is the game it was:

  * the bytes in memory are the bytes the compiler laid out;
  * the chip's eleven registers, tick for tick, are what
    tools/make_music.py's own model of the player says - on the title,
    and in the City - with the model a tick out as the control;
  * every event the watch reads asks for its effect on channel C, the
    effect is the descriptor, tick for tick, and C then comes back to
    the music IN STEP, which is the music having been counted the whole
    time it was not heard;
  * the important effect wins, a request keeps the flags it was given
    (ENEMY_WOUND's carry is its answer), and the drones ask for theirs;
  * the keyboard still reads through the chip the music is writing,
    R7 bit 6 is never set, a disc read is silent, and a fade takes the
    music down with the palette;
  * and the frame did not pay for it: a tick is benched, and the loop
    is counted with the player and with SOUND_TICK poked to RET.
"""
import os
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cpc import CPC                                     # noqa: E402
import bench                                            # noqa: E402
import make_music as MM                                 # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DSK = os.path.abspath(os.path.join(ROOT, "build", "kara.dsk"))
STUB = 0x9000
JOY_RIGHT, JOY_FIRE = 0x08, 0x10
IN_RIGHT = 0x08
FAIL = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def word(m, a):
    return m.peek(a) | m.peek(a + 1) << 8


def regs(m):
    return list(m.psg_regs()[:11])


def after_tick(m, sym, prev, limit=12):
    """Run until SND_TICKS moves off `prev`, then a little more so the
    tick's flush is finished. Returns the new count."""
    for _ in range(limit):
        m.run_frames(1)
        t = m.peek(sym["SND_TICKS"])
        if t != prev:
            m.run_us(3000)          # ... and the tick's own flush
            return t
    return None


class Clock:
    """Ticks since a tune was started, counted across SND_TICKS' wrap.

    SND_TICKS is one byte and the effects below run for many hundred
    ticks, so the model's index is this and not that."""

    def __init__(self, m, sym):
        self.m, self.sym = m, sym
        self.raw = m.peek(sym["SND_TICKS"])
        self.n = 0

    def catch_up(self):
        t = self.m.peek(self.sym["SND_TICKS"])
        self.n += (t - self.raw) & 0xFF
        self.raw = t
        return self.n

    def next(self):
        """Run to the next tick, with its flush done: the tick's number."""
        self.catch_up()
        t = after_tick(self.m, self.sym, self.raw)
        self.n += (t - self.raw) & 0xFF
        self.raw = t
        return self.n


def stub(m, sym, code, ok_off):
    """Run `code` at STUB from the top of the loop and put the loop back.
    `code` ends in spins; returns the offset the PC was found spinning
    at, or None."""
    bench.sync(m, sym, 0)
    m.write_ram(STUB, bytes(code))
    m.set_pc(STUB)
    spins = {o for o in ok_off}
    for _ in range(400000):
        m.run_us(1)
        if m.pc - STUB in spins:
            break
    at = m.pc - STUB
    m.set_pc(sym["WAIT_VSYNC"])
    return at if at in spins else None


def call_a(m, sym, routine, a):
    """di : ld a,n : call routine : ei : jr $"""
    r = sym[routine]
    return stub(m, sym, [0xF3, 0x3E, a, 0xCD, r & 0xFF, r >> 8, 0xFB,
                         0x18, 0xFE], {7})


def title_machine(sym):
    """A machine sitting on the title, its tune playing, nothing pressed."""
    m = CPC()
    m.run_frames(150)
    m.insert_disc(DSK)
    m.type_text('RUN"DISC\n')
    prev = None
    for _ in range(1500):
        m.run_frames(1)
        v = m.peek(sym["INTRO_BLINK"])
        if prev is not None and (v - prev) & 0xFF == 1:
            return m
        prev = v
    raise SystemExit("the title never came up")


# =====================================================================
def bytes_in_memory(m, sym):
    print("\n  the bytes:")
    bad, total = [], 0
    table = sym["TUNE_TABLE"]
    for ti, t in enumerate(MM.TUNES):
        hdr = word(m, table + 2 * ti)
        for ci, ch in enumerate("ABC"):
            at = word(m, hdr + 2 * ci)
            want = MM.Stream(t, ch).at(at)
            got = bytes(m.read_ram(at, len(want)))
            total += len(want)
            if got != want:
                bad.append((t["name"], ch))
    check("every channel of every tune is the bytes the compiler laid out",
          not bad, f"{total} bytes over {len(MM.TUNES)} tunes, relocated to "
          f"where RASM put them" + (f"; wrong: {bad}" if bad else ""))
    want = [MM.TUNE_ID[n] for n in MM.ENV_TUNE]
    got = list(m.read_ram(sym["ENV_TUNE"], len(want)))
    check("... and ENV_TUNE is the environments' tunes", got == want,
          f"{dict(zip(range(len(got)), (MM.TUNES[i]['name'] for i in got)))}")


def against_model(samples, model, shift=0):
    """(tick, regs) samples against the model's frames: wrong registers."""
    bad, first = 0, None
    for k, r in samples:
        i = k - 1 + shift
        if not 0 <= i < len(model):
            continue
        for j in range(11):
            if r[j] != model[i][j]:
                bad += 1
                if first is None:
                    first = (k, j, r[j], model[i][j])
    return bad, first


def title_tune(sym):
    print("\n  the title, on the chip:")
    m = title_machine(sym)
    tune = m.peek(sym["SND_TUNE"])
    check("the title plays the title's tune", tune == MM.TUNE_ID["title"],
          f"SND_TUNE {tune}")
    t, samples, bit6, hw = m.peek(sym["SND_TICKS"]), [], 0, 0
    t0 = t
    for _ in range(240):
        f0 = m.peek(sym["IRQ_TICKS"])
        t = after_tick(m, sym, t)
        if t is None:
            break
        r = regs(m)
        samples.append(((t - t0) & 0xFF if t >= t0 else t + 256 - t0, r))
        bit6 += (r[7] >> 6) & 1
    # the ticks are counted from the tune's first, which SOUND_TUNE at
    # INTRO_WAIT's entry started: SND_TICKS was 0 from SOUND_INIT until
    # then, and the title is the first thing that ticks at all
    samples = [(k + t0, r) for k, r in samples]
    model = MM.simulate(MM.TUNE_ID["title"], 600)
    bad, first = against_model(samples, model)
    check("eleven registers a tick, tick for tick, are the model's",
          bad == 0 and len(samples) >= 200,
          f"{len(samples)} ticks, {bad} registers wrong"
          + (f"; first at tick {first[0]}: R{first[1]} {first[2]} "
             f"against {first[3]}" if first else ""))
    sbad, _ = against_model(samples, model, shift=1)
    check("... and a model one tick out is not", sbad > len(samples),
          f"{sbad} registers wrong a tick out - what says the comparison "
          f"would have noticed")
    check("R7 bit 6 is never set - the keyboard's port stays an input",
          bit6 == 0, f"{bit6} of {len(samples)} samples")
    # half rate: SOUND_HALF ticks on every other 50 Hz frame
    t1 = m.peek(sym["SND_TICKS"])
    m.run_frames(100)
    n = (m.peek(sym["SND_TICKS"]) - t1) & 0xFF
    check("the title's 50 Hz loop ticks every other frame", n == 50,
          f"{n} ticks in 100 hardware frames - 25 Hz, the game's rate")


def city_tune(m, sym):
    print("\n  the City, on the chip:")
    tune = m.peek(sym["SND_TUNE"])
    check("level 1 plays the City's", tune == MM.TUNE_ID["city"],
          f"SND_TUNE {tune}")
    m.poke(sym["SND_TUNE"], 0xFF)            # so SOUND_TUNE starts it again
    call_a(m, sym, "SOUND_TUNE", MM.TUNE_ID["city"])
    clock = Clock(m, sym)
    model = MM.simulate(MM.TUNE_ID["city"], 4000)
    samples, sfx = [], 0
    for _ in range(220):
        m.poke(sym["ENEMY_LIVE"], 0)
        n = clock.next()
        sfx += m.peek(sym["SX_PRIO"]) != 0
        samples.append((n, regs(m)))
    bad, first = against_model(samples, model)
    check("standing on the roof, the chip is the model",
          bad == 0 and len(samples) >= 200 and sfx == 0,
          f"{len(samples)} ticks, {bad} registers wrong, {sfx} with an effect"
          + (f"; first at tick {first[0]}: R{first[1]} {first[2]} against "
             f"{first[3]}" if first else ""))
    return clock, model


SFX_REGS = (4, 5, 6, 10)


def sfx_want(name):
    """What the chip's channel C should hold on each tick of an effect."""
    flags, noise, nd, per, sweep, vols = MM.SFX[MM.SFX_ID[name] - 1][1:]
    out = []
    for k, v in enumerate(vols):
        p = per + sweep * k
        out.append((p & 0xFF, (p >> 8) & 0xF, (noise + nd * k) & 0x1F, v,
                    0 if flags & MM.TONE else 1, 0 if flags & MM.NOISE else 1))
    return out


def c_of(r):
    return (r[4], r[5], r[6], r[10], (r[7] >> 2) & 1, (r[7] >> 5) & 1)


def effects(m, sym, clock, model):
    print("\n  what the game does, and what it sounds like:")
    events = [
        ("a hit takes health", "hurt", lambda: m.poke(sym["PLAYER_HP"],
                                                     m.peek(sym["PLAYER_HP"]) - 8)),
        ("a medkit gives it back", "medkit", lambda: m.poke(
            sym["PLAYER_HP"], m.peek(sym["PLAYER_HP"]) + 8)),
        ("a round leaves her gun", "shot", lambda: m.poke(
            sym["MAG_LEFT"], m.peek(sym["MAG_LEFT"]) - 1)),
        ("a reload begins", "reload", lambda: m.poke(sym["RELOAD_TIMER"], 30)),
        ("a clip goes into the reserve", "clip", lambda: m.poke(
            sym["AMMO_RESERVE"], m.peek(sym["AMMO_RESERVE"]) + 14)),
        ("a key", "key", lambda: m.poke(sym["KEYS_COUNT"],
                                         m.peek(sym["KEYS_COUNT"]) + 1)),
        ("a coin", "coin", lambda: m.poke(sym["COINS_COUNT"],
                                           m.peek(sym["COINS_COUNT"]) + 1)),
        ("the idol picked up", "key", lambda: m.poke(sym["STATUES_HELD"], 1)),
        ("... and put on the altar", "altar",
         lambda: m.poke(sym["STATUES_HELD"], 0)),
    ]
    handback = []
    for what, name, act in events:
        m.poke(sym["RELOAD_TIMER"], 0)
        # wait for the effect before to be over, and the watch to settle
        for _ in range(60):
            m.poke(sym["ENEMY_LIVE"], 0)
            m.run_frames(2)
            if m.peek(sym["SX_PRIO"]) == 0:
                break
        bench.sync(m, sym, 0)
        act()
        want = sfx_want(name)
        got, ok = [], True
        for k in range(len(want) + 1):
            m.poke(sym["ENEMY_LIVE"], 0)
            n = clock.next()
            r = regs(m)
            if k < len(want):
                got.append(c_of(r))
            else:
                # THE TICK AFTER: C is the music's again, and IN STEP
                handback.append(c_of(r) == c_of(model[n - 1]))
        prio = MM.SFX_ID[name]
        check(f"{what}: {name} on C, tick for tick", got == want,
              f"{len(want)} ticks" + ("" if got == want else
                                      f"; got {got[:3]} against {want[:3]}"))
    check("... and after every one, C is the music again, in step",
          all(handback),
          f"{sum(handback)} of {len(handback)} - the music on C was counted "
          f"the whole time, so it comes back on the tick and the envelope it "
          f"had reached rather than re-struck")

    # THE IMPORTANT ONE WINS: a hit and a shot in one frame is the hit
    for _ in range(60):
        m.run_frames(2)
        if m.peek(sym["SX_PRIO"]) == 0:
            break
    bench.sync(m, sym, 0)
    m.poke(sym["MAG_LEFT"], m.peek(sym["MAG_LEFT"]) - 1)
    m.poke(sym["PLAYER_HP"], m.peek(sym["PLAYER_HP"]) - 8)
    clock.next()
    c = c_of(regs(m))
    check("a hit and a shot in the same frame: the hit is heard",
          c == sfx_want("hurt")[0], f"C {c}")
    # ... and a shot while the hit plays is dropped, not queued
    m.poke(sym["MAG_LEFT"], m.peek(sym["MAG_LEFT"]) - 1)
    clock.next()
    c = c_of(regs(m))
    check("... and a shot while it plays does not cut it off",
          c == sfx_want("hurt")[1], f"C {c} - the hit's second tick")


def watch_control(m, sym, clock, model):
    print("\n  and with the watch taken away:")
    for _ in range(60):
        m.run_frames(2)
        if m.peek(sym["SX_PRIO"]) == 0:
            break
    w = sym["SND_WATCH"]
    old = m.peek(w)
    m.poke(w, 0xC9)
    bench.sync(m, sym, 0)
    m.poke(sym["PLAYER_HP"], m.peek(sym["PLAYER_HP"]) - 8)
    ok = True
    for _ in range(8):
        m.poke(sym["ENEMY_LIVE"], 0)
        n = clock.next()
        ok &= m.peek(sym["SX_PRIO"]) == 0 and c_of(regs(m)) == c_of(model[n - 1])
    m.poke(w, old)
    check("SND_WATCH poked to RET: the same hit is silent", ok,
          "C stays the music's - so it is the watch that asked, and not "
          "something else that happened to sound like it")


def requests(m, sym):
    print("\n  the requests that are not the watch's:")
    req = sym["SFX_REQ"]
    for carry, name in ((1, "set"), (0, "clear")):
        code = [0xF3, 0x37 if carry else 0xB7,      # di ; scf / or a
                0x3E, 5,                            # ld a,5
                0xCD, req & 0xFF, req >> 8,         # call SFX_REQ
                0x38, 0x02,                         # jr c,+2
                0x18, 0xFE,                         # clear: spin at 9
                0x18, 0xFE]                         # set: spin at 11
        if not carry:
            code[1] = 0xB7
        m.poke(sym["SFX_REQ_ID"], 0)
        at = stub(m, sym, code, {9, 11})
        want = 11 if carry else 9
        check(f"SFX_REQ hands back the carry it was given ({name})",
              at == want, f"spun at +{at}, request {m.peek(sym['SFX_REQ_ID'])}")
    # ENEMY_WOUND: a hit, and a kill, on a slot built here
    slot, rec = 0x9100, 0x9180
    es_hp, es_rec, es_die = sym["ES_HP"], sym["ES_REC"], sym["ES_DIE"]
    ef = sym["ENT_FLAGS"]
    for hp, sfx, dies in ((3, "ehit", False), (1, "ekill", True)):
        m.write_ram(slot, bytes(32))
        m.write_ram(rec, bytes(8))
        m.poke(slot + es_hp, hp)
        m.poke(slot + es_rec, rec & 0xFF)
        m.poke(slot + es_rec + 1, rec >> 8)
        m.poke(sym["SFX_REQ_ID"], 0)
        w = sym["ENEMY_WOUND"]
        code = [0xF3, 0xDD, 0x21, slot & 0xFF, slot >> 8,   # ld ix,slot
                0xB7,                                       # or a: carry clear
                0xCD, w & 0xFF, w >> 8,
                0x38, 0x02, 0x18, 0xFE, 0x18, 0xFE]         # 11 alive, 13 dead
        at = stub(m, sym, code, {11, 13})
        got = m.peek(sym["SFX_REQ_ID"])
        check(f"a drone {'killed' if dies else 'hit'}: {sfx} asked for, and "
              f"ENEMY_WOUND's carry is still its answer",
              got == MM.SFX_ID[sfx] and at == (13 if dies else 11)
              and bool(m.peek(rec + ef) & sym["EF_TAKEN"]) == dies,
              f"request {got}, carry {'set' if at == 13 else 'clear'}")
    e = sym["EBUL_SPAWN"]
    m.poke(sym["SFX_REQ_ID"], 0)
    lv = m.peek(sym["EBUL_LIVE"])
    at = stub(m, sym, [0xF3, 0x01, 100, 20, 0x3E, 0,          # ld bc ; ld a,0
                       0xCD, e & 0xFF, e >> 8, 0x18, 0xFE], {9})
    got = m.peek(sym["SFX_REQ_ID"])
    check("a drone's round in the air asks for its shot",
          got == MM.SFX_ID["eshot"] and m.peek(sym["EBUL_LIVE"]) == lv + 1,
          f"request {got}")
    m.run_frames(20)


def levels_tunes(m, sym):
    print("\n  a tune an environment:")
    env0 = m.peek(sym["LEVEL_ENV"])
    got = []
    for env in range(7):
        m.poke(sym["LEVEL_ENV"], env)
        m.poke(sym["SND_TUNE"], 0xFF)
        stub(m, sym, [0xF3, 0xCD, sym["SOUND_LEVEL"] & 0xFF,
                      sym["SOUND_LEVEL"] >> 8, 0xFB, 0x18, 0xFE], {5})
        got.append(m.peek(sym["SND_TUNE"]))
    m.poke(sym["LEVEL_ENV"], env0)
    want = [MM.TUNE_ID[n] for n in MM.ENV_TUNE] + [MM.TUNE_ID["title"]]
    check("SOUND_LEVEL plays each environment's, and the title's past them",
          got == want, f"{got}")
    # the same tune goes on: a death or a door inside an environment
    m.poke(sym["LEVEL_ENV"], 0)
    sl = [0xF3, 0xCD, sym["SOUND_LEVEL"] & 0xFF, sym["SOUND_LEVEL"] >> 8,
          0xFB, 0x18, 0xFE]
    stub(m, sym, sl, {5})                     # the City's, from its start
    start = word(m, sym["SND_VA"])
    m.run_frames(30)                          # ... some way into it
    stub(m, sym, sl, {5})
    p = word(m, sym["SND_VA"])
    check("... and the one already playing is not started again",
          p != start,
          f"channel A at &{p:04X} after a second SOUND_LEVEL, its start "
          f"&{start:04X} - a level is a map and the tune is the "
          f"environment's (8.1)")


def sea_tune(sym):
    """The sea's tune is the first whose bars are NOT in the SOUND image -
    they are in the HIGH image, past the table (tools/make_music.py's
    FAR_TUNES) - so it is held to the model on the chip, in the sea."""
    print("\n  the sea, on the chip - out of the HIGH image:")
    import test_sea
    test_sea.LEVEL = 13
    p = test_sea.Sea()
    m = p.m
    tune = m.peek(sym["SND_TUNE"])
    ti = MM.TUNE_ID["sea"]
    hdr = word(m, sym["TUNE_TABLE"] + 2 * ti)
    check("level 13 plays the sea's, and its bars are past the SOUND image",
          tune == ti and hdr >= sym["HIGH_START"] and hdr < sym["HIGH_END"],
          f"SND_TUNE {tune}, its header at &{hdr:04X}, the HIGH image "
          f"&{sym['HIGH_START']:04X}-&{sym['HIGH_END']:04X}")
    m.poke(sym["SND_TUNE"], 0xFF)
    call_a(m, sym, "SOUND_TUNE", ti)
    clock = Clock(m, sym)
    model = MM.simulate(ti, 4000)
    samples, sfx = [], 0
    for _ in range(220):
        n = clock.next()
        sfx += m.peek(sym["SX_PRIO"]) != 0
        samples.append((n, regs(m)))
    bad, first = against_model(samples, model)
    out, _ = against_model(samples, model, shift=1)
    check("treading water, the chip is the model - and a tick out it is not",
          bad == 0 and len(samples) >= 200 and sfx == 0 and out > 0,
          f"{len(samples)} ticks, {bad} registers wrong, {out} with the "
          f"model a tick out, {sfx} with an effect"
          + (f"; first at tick {first[0]}: R{first[1]} {first[2]} against "
             f"{first[3]}" if first else ""))


def keyboard(m, sym):
    print("\n  the keyboard, through the chip the music is writing:")
    t0 = m.peek(sym["SND_TICKS"])
    m.joystick(JOY_RIGHT)
    held, frames, bit6 = 0, 0, 0
    for _ in range(200):
        m.poke(sym["ENEMY_LIVE"], 0)
        m.run_frames(1)
        frames += 1
        held += bool(m.peek(sym["INPUT_NOW"]) & IN_RIGHT)
        bit6 += (m.psg_reg(7) >> 6) & 1
    m.joystick(0)
    ticks = (m.peek(sym["SND_TICKS"]) - t0) & 0xFF
    check("RIGHT held: INPUT_NOW has it on every frame the music plays",
          held >= frames - 1 and ticks >= 90,
          f"{held} of {frames} frames, {ticks} ticks of music under them, "
          f"R7 bit 6 set on {bit6}")


def disc_and_fade(m, sym):
    print("\n  a door, its fade and its disc read:")
    lo, hi = sym["DISC_MOTOR_ON"], sym["DISC_MOTOR_STATE"]
    for _ in range(40):
        m.run_frames(2)
        if m.peek(sym["SX_PRIO"]) == 0:
            break
    bench.sync(m, sym, 0)
    m.poke(sym["GAME_STATE"], sym["GS_CLEAR"])
    loud, quiet, atten, fade_ticks = 0, 0, set(), 0
    t = m.peek(sym["SND_TICKS"])
    door = False
    # THE CALL THAT MUTES IT IS NOT INSIDE THE READ. DISC_READ's first
    # instruction is `call SOUND_MUTE`, and a sample that lands on it -
    # one in 7,775 at a 20 us stride, depending on where the stride
    # meets the code - finds the note still sounding, because the mute
    # has not run yet. It did the day the station's levels moved the
    # code under it: DISC_READ+2, with the City's tune on all three voices.
    mute = sym["DISC_READ"]
    for _ in range(140000):
        m.run_us(20)
        pc = m.pc
        atten.add(m.peek(sym["SND_ATTEN"]))
        if m.peek(sym["SX_PRIO"]) == MM.SFX_ID["door"]:
            door = True
        if lo <= pc < hi and not mute <= pc < mute + 3:
            v = m.psg_regs()[8:11]
            if any(v):
                loud += 1
            else:
                quiet += 1
        if m.peek(sym["LEVEL_CUR"]) == 1 and m.peek(sym["GAME_STATE"]) == 0:
            break
    check("the way out opening plays the door", door)
    check("the disc read is silent", quiet > 100 and loud == 0,
          f"{quiet} samples inside the read with all three levels at 0, "
          f"{loud} with any up")
    check("the fade takes the music down with the palette",
          {0, 4, 8} <= atten, f"SND_ATTEN {sorted(atten)} - four levels a "
          f"step of the palette's two")
    check("... and level 2 goes on with the City's tune",
          m.peek(sym["SND_TUNE"]) == MM.TUNE_ID["city"]
          and m.peek(sym["LEVEL_CUR"]) == 1,
          f"LEVEL_CUR {m.peek(sym['LEVEL_CUR'])}, SND_TUNE "
          f"{m.peek(sym['SND_TUNE'])}")
    return m


def mute_control(sym):
    print("\n  ... and with SOUND_MUTE poked to RET:")
    m = bench.boot(sym, scroll=True)
    m.run_frames(40)
    mu = sym["SOUND_MUTE"]
    m.poke(mu, 0xC9)
    bench.sync(m, sym, 0)
    m.poke(sym["GAME_STATE"], sym["GS_CLEAR"])
    loud, quiet = 0, 0
    lo, hi = sym["DISC_MOTOR_ON"], sym["DISC_MOTOR_STATE"]
    for _ in range(140000):
        m.run_us(20)
        pc = m.pc
        if lo <= pc < hi:
            if any(m.psg_regs()[8:11]):
                loud += 1
            else:
                quiet += 1
        if m.peek(sym["LEVEL_CUR"]) == 1 and m.peek(sym["GAME_STATE"]) == 0:
            break
    check("the read holds whatever note was sounding", loud > 100,
          f"{loud} samples with a level up, {quiet} without - a note held "
          f"for the whole read, which is what the mute is for")


def cost(sym):
    print("\n  what it costs:")
    m = bench.boot(sym, scroll=True)
    m.run_frames(20)
    b = bench.Bench(m, sym)
    ts = []
    for _ in range(60):
        m.poke(sym["ENEMY_LIVE"], 0)
        t = b.T("SOUND_TICK")
        if t is not None:
            ts.append(t)
        m.run_frames(2)
    ts.sort()
    # THE BOUND IS A QUARTER OF THE WAIT IT LIVES IN, and it is not what
    # says the frame can pay: the loop count below is, and so are the
    # floors of tools/test_enemies.py and test_climb.py, which run with
    # the player in every path. A bar line - all three voices striking at
    # once, and an effect starting on the same tick - is the dear case.
    check("a tick, benched from a DI stub", ts and ts[-1] < 40468 // 4,
          f"{len(ts)} ticks: {ts[0]} T at least, {ts[len(ts) // 2]} typical, "
          f"{ts[-1]} at worst - in the second sweep's wait for its head "
          f"gate, which is 40,468 T of nothing")

    def loops(m, joy, quiet):
        bench.sync(m, sym, 0)
        if quiet:
            m.poke(sym["SOUND_TICK"], 0xC9)
        f0 = m.peek(sym["FRAME_COUNT"])
        m.joystick(joy)
        for _ in range(200):
            m.poke(sym["ENEMY_LIVE"], 0)
            m.run_frames(1)
        m.joystick(0)
        return (m.peek(sym["FRAME_COUNT"]) - f0) & 0xFF

    with_ = loops(bench.boot(sym, scroll=True), JOY_RIGHT, False)
    without = loops(bench.boot(sym, scroll=True), JOY_RIGHT, True)
    check("walking right, scrolling: the 25 Hz lock with the player in it",
          with_ == 100 and without == 100,
          f"{with_} game frames in 200 hardware, {without} with SOUND_TICK "
          f"poked to RET")


def main():
    sym = bench.symbols()
    title_tune(sym)
    m = bench.boot(sym, scroll=True)
    m.run_frames(20)
    bytes_in_memory(m, sym)
    clock, model = city_tune(m, sym)
    effects(m, sym, clock, model)
    watch_control(m, sym, clock, model)
    requests(m, sym)
    levels_tunes(m, sym)
    sea_tune(sym)
    keyboard(m, sym)
    disc_and_fade(bench.boot(sym, scroll=True), sym)
    mute_control(sym)
    cost(sym)
    print()
    if FAIL:
        print(f"{len(FAIL)} CHECK(S) FAILED")
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
