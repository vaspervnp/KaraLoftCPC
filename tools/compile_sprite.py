#!/usr/bin/env python3
"""A span cel -> Z80 that draws it: a COMPILED sprite (CLAUDE.md 8.27).

The span blitter (src/spanblit.asm) is at its floor for its format - 72 T
a byte composited and saved - and what a 24x64 character costs on top of
that is the per-line and per-group bookkeeping of READING the format. A
compiled cel reads nothing: every byte's mask and data are immediates in
the instruction that writes it, and every line's skip and count are
where the code jumps to. What it writes is EXACTLY what SPAN_DRAW writes,
the composite and the erase script both, so SPAN_ERASE_AT lifts it off
unchanged and the two can be compared byte for byte.

WHAT IT ASSUMES, AND WHY THE ENGINE CAN PROMISE IT:

  * the box's TOP LINE is the first line of a character row, so which
    line of a character row each box line is on is known here. A
    sentry stands on a floor, a floor is a tile row and a tile is two
    character rows, and her box is 64 lines - so its top is too.
  * no line of the box crosses a 256-byte page of video RAM, so a byte
    step is INC E. Where a box sits in video RAM is a property of the
    WORLD and not of the view: SCROLL starts as WORLD_CR * 40 + WORLD_X
    and every scroll step moves the three together (8.1), so a world
    character (X, R) is always at word 40R + X of the 1024-word ring. A
    sentry does not move, so the tool that places it checks its box
    against that once, at build time (page_safe(), below) - and a page
    boundary is also where the 2 KB fold is, so it never meets that
    either.

TWO CELS, AND THE SECOND IS NOT A REDRAW (CLAUDE.md 8.27). A sentry shows
its aim and, for the art's four frames after a shot, its recoil. Drawn
afresh - when it comes on, when it turns, while it flashes - the blob
draws the AIM and saves under it the background of every byte EITHER cel
writes, so the erase script lifts both off. Changing cel is then a
TOGGLE: the screen holds exactly the other cel's composite, and a byte
written (bg AND m) OR d is (bg AND m') XOR d with m' = m AND NOT d, so

    aim XOR recoil = (bg AND (m'a XOR m'r)) XOR (da XOR dr)

and XORing that over the screen turns either cel into the other. The
background it needs is in the erase script, at an address this tool
knows (ENEMY_SCRIPT and the script's own layout), so one routine serves
both directions and touches only the 60 to 87 bytes that differ:

    aim, saved             16,000 to 20,000 T, as one cel was
    the toggle             3,000 to 4,000 T

THE BLOB:   ex de,hl : the script's first byte &FF? -> FRESH, otherwise
            jump to TOGGLE through BC, the blob's own address (the
            engine passes it: the code has no other way to find itself)
    FRESH:  the aim and the save; then the recoil's toggle if that is
            the cel ES_CEL asks for
    TOGGLE: ... and RET, which is BANK_RESTORE's (src/sentry.asm)

REGISTERS:  HL  the screen, walking right along the line
            DE  the erase script, as SPAN_ERASE_AT reads it
            C   the line's x = 0, as L - restored at every line
            A   the work            IX the enemy's slot (its ES_CEL)
   IN:  DE = the box's top-left byte, HL = the script, BC = the blob
   OUT: destroys AF, BC, DE, HL
"""
import os
import sys

# CPC timings, in NOPs (one NOP is 4 T, the gate array's microsecond),
# and sizes, of the instructions this tool emits that take no operand
NOPS = {"ld a,h": 1, "ld h,a": 1, "ld l,c": 1, "ld c,l": 1, "ld a,c": 1,
        "ld l,a": 1, "ld c,a": 1, "inc l": 1, "inc a": 1, "ex de,hl": 1,
        "inc hl": 2, "inc de": 2, "ld (hl),e": 2, "ld (hl),d": 2,
        "ld (hl),a": 2, "ld a,(hl)": 2, "xor (hl)": 2, "ld a,(de)": 2,
        "ld (de),a": 2, "add hl,bc": 3, "pop hl": 3, "ret": 3, "ret z": 4,
        "push hl": 4, "ex (sp),hl": 6}
OPS = {"ld a,h": 0x7C, "ld h,a": 0x67, "ld l,c": 0x69, "ld c,l": 0x4D,
       "ld a,c": 0x79, "ld l,a": 0x6F, "ld c,a": 0x4F, "inc l": 0x2C,
       "inc a": 0x3C, "ex de,hl": 0xEB, "inc hl": 0x23, "inc de": 0x13,
       "ld (hl),e": 0x73, "ld (hl),d": 0x72, "ld (hl),a": 0x77,
       "ld a,(hl)": 0x7E, "xor (hl)": 0xAE, "ld a,(de)": 0x1A,
       "ld (de),a": 0x12, "add hl,bc": 0x09, "pop hl": 0xE1, "ret": 0xC9,
       "ret z": 0xC8, "push hl": 0xE5, "ex (sp),hl": 0xE3}
IMM = {"add a,": 0xC6, "adc a,": 0xCE, "and ": 0xE6, "xor ": 0xEE,
       "or ": 0xF6, "cp ": 0xFE, "ld (hl),": 0x36, "ld a,": 0x3E,
       "jr z,": 0x28}


def cost(ins):
    """(NOPs, bytes) of one instruction in the forms this tool emits."""
    if ins in NOPS:
        return NOPS[ins], 1
    if ins.startswith("ld a,(&"):
        return 4, 3                         # ld a,(nn)
    if ins.startswith("ld a,(ix+"):
        return 5, 3
    if ins.startswith("ld hl,"):
        return 3, 3
    if ins.startswith("ld (hl),"):
        return 3, 2                         # ld (hl),n
    if ins.startswith("jr z,"):
        return 3, 2                         # taken
    if any(ins.startswith(p) for p in IMM):
        return 2, 2                         # ALU / load with an immediate
    raise ValueError(ins)


def frame_lines(blob, f):
    """Span blob frame f -> (y0, [(skip, [(mask, data), ...]), ...]) with
    one entry per stored line - the exporter's own format read back."""
    off = blob[2 * f] | blob[2 * f + 1] << 8
    y0, n = blob[off], blob[off + 1]
    p, skip, lines = off + 2, 0, []
    while True:
        nl = blob[p]
        if nl == 0:
            break
        count = blob[p + 1]
        d = blob[p + 2] | blob[p + 3] << 8
        p += 4
        if count:
            skip += d - 65536 if d > 32767 else d
        for _ in range(nl):
            pairs = [(blob[p + 2 * b], blob[p + 2 * b + 1])
                     for b in range(count)]
            p += 2 * count
            lines.append((skip if count else 0, pairs))
    assert len(lines) == n, (len(lines), n)
    return y0, lines


def cel_bytes(blob, f):
    """Span blob frame f -> {(line, x): (mask, data)} for every byte the
    cel WRITES - a byte of mask &FF and data 0 inside a span is none."""
    y0, lines = frame_lines(blob, f)
    out = {}
    for i, (skip, pairs) in enumerate(lines):
        for k, (mask, data) in enumerate(pairs):
            assert data & mask == 0, "a data bit under a mask bit"
            if mask != 0xFF or data:
                out[(y0 + i, skip + k)] = (mask, data)
    return out


def segments(cels, gap=3):
    """The erase script's layout: one entry a run of the bytes ANY of the
    cels writes, a line split where it has more than `gap` bytes of
    nothing (an entry is 3 bytes and 15 NOPs; a byte saved is 1 and 5).
    -> [(line, x0, count, offset of the entry in the script)], length"""
    xs = {}
    for c in cels:
        for (y, x) in c:
            xs.setdefault(y, set()).add(x)
    segs, o = [], 0
    for y in sorted(xs):
        row = sorted(xs[y])
        lo = prev = row[0]
        for x in row[1:] + [None]:
            if x is None or x - prev > gap:
                n = prev - lo + 1
                segs.append((y, lo, n, o))
                o += 3 + n
                lo = x
            prev = x
    return segs, o + 1


class Walk:
    """Where HL is: the box line it is on, and its x on the line."""
    def __init__(self):
        self.out, self.line, self.x = ["ld c,l"], 0, 0

    def go(self, y, x, fresh_line):
        while self.line < y:
            if self.line % 8 == 7:          # the next character row: +80
                self.out.extend(["ld a,c", "add a,80", "ld c,a", "ld a,h",
                                 "adc a,&C8", "and &C7", "ld h,a"])
                self.line += 1              # (line 7 is &F8 + the page,
            else:                           #  &C8 + the carry takes it to
                k = min(y - self.line, 7 - self.line % 8)  # line 0 of the
                self.out.extend(["ld a,h", f"add a,{8 * k}", "ld h,a"])
                self.line += k              #  next, and &C7 is the fold)
            fresh_line = True
        if fresh_line:
            self.out.extend(["ld l,c"] if x == 0 else
                            ["ld a,c", f"add a,{x}", "ld l,a"])
        elif x == self.x + 1:
            self.out.append("inc l")
        elif x == self.x + 2:
            self.out.extend(["inc l", "inc l"])
        elif x != self.x:
            self.out.extend(["ld a,c", f"add a,{x}", "ld l,a"])
        self.x = x


def compile_fresh(aim, segs):
    """The aim, composited, with the background of every byte in segs
    saved under it in the erase script's own format."""
    w = Walk()
    last = None
    for (y, lo, n, _) in segs:
        w.go(y, lo, y != last)
        last = y
        w.out.extend(["ex de,hl", f"ld (hl),{n}", "inc hl", "ld (hl),e",
                      "inc hl", "ld (hl),d", "inc hl", "ex de,hl"])
        for x in range(lo, lo + n):
            if x != lo:
                w.out.append("inc l")
                w.x = x
            w.out.extend(["ld a,(hl)", "ld (de),a", "inc de"])   # the save
            if (y, x) in aim:
                mask, data = aim[(y, x)]
                if mask == 0:
                    w.out.append(f"ld (hl),&{data:02X}")
                else:
                    if mask != 0xFF:
                        w.out.append(f"and &{mask:02X}")
                    if data:
                        w.out.append(f"or &{data:02X}")
                    w.out.append("ld (hl),a")
    w.out.extend(["ld a,&FF", "ld (de),a"])
    return w.out


def effective(v):
    """(mask, data) -> (m', data): written = (bg AND m') XOR data."""
    if v is None:
        return 0xFF, 0
    mask, data = v
    return mask & ~data & 0xFF, data


def compile_toggle(a, b, segs, script):
    """Either cel into the other, over the background in the script."""
    where = {}
    for (y, lo, n, o) in segs:
        for x in range(lo, lo + n):
            where[(y, x)] = script + o + 3 + x - lo
    w = Walk()
    last = None
    for (y, x) in sorted(set(a) | set(b)):
        ma, da = effective(a.get((y, x)))
        mb, db = effective(b.get((y, x)))
        k1, k2 = ma ^ mb, da ^ db
        if not k1 and not k2:
            continue
        w.go(y, x, y != last)
        last = y
        if not k1:                          # opaque in both, or the same
            w.out.extend(["ld a,(hl)", f"xor &{k2:02X}", "ld (hl),a"])
            continue
        w.out.append(f"ld a,(&{where[(y, x)]:04X})")
        if k1 != 0xFF:
            w.out.append(f"and &{k1:02X}")
        if k2:
            w.out.append(f"xor &{k2:02X}")
        w.out.extend(["xor (hl)", "ld (hl),a"])
    w.out.append("ret")
    return w.out


def sentry_code(aim, recoil, aim_cel, es_cel, script):
    """The whole blob for one facing, as one instruction list."""
    segs, length = segments([aim, recoil])
    fresh = compile_fresh(aim, segs)
    toggle = compile_toggle(aim, recoil, segs, script)
    entry_len = 12                          # the six below and these five
    tail = ["pop hl", f"ld a,(ix+{es_cel})", f"cp {aim_cel}", "ret z"]
    at_toggle = entry_len + 1 + sum(cost(i)[1] for i in fresh) \
        + sum(cost(i)[1] for i in tail)
    head = ["ex de,hl", "ld a,(de)", "inc a", "jr z,7",
            "push hl", f"ld hl,{at_toggle}", "add hl,bc", "ex (sp),hl", "ret"]
    assert sum(cost(i)[1] for i in head) == entry_len
    return head + ["push hl"] + fresh + tail + toggle, fresh, toggle, length


def number(s):
    return int(s[1:], 16) if s.startswith("&") else int(s)


def assemble(ins):
    """The instructions this tool emits, as bytes - checked against RASM's
    own encoding by tools/test_sentries.py."""
    out = bytearray()
    for i in ins:
        if i in OPS:
            out.append(OPS[i])
        elif i.startswith("ld a,(&"):
            v = number(i[6:-1])
            out += bytes([0x3A, v & 0xFF, v >> 8])
        elif i.startswith("ld a,(ix+"):
            out += bytes([0xDD, 0x7E, number(i[9:-1])])
        elif i.startswith("ld hl,"):
            v = number(i[6:])
            out += bytes([0x21, v & 0xFF, v >> 8])
        else:
            for pre, op in IMM.items():
                if i.startswith(pre):
                    out += bytes([op, number(i[len(pre):]) & 0xFF])
                    break
            else:
                raise ValueError(i)
    return bytes(out)


def measure(ins):
    n = b = 0
    for i in ins:
        c, s = cost(i)
        n, b = n + c, b + s
    return n * 4, b


def page_safe(word, rows, box_words):
    """Whether a box whose top-left is world word `word` (40R + X) keeps
    every one of its `rows` character rows inside one 256-byte page."""
    for r in range(rows):
        w = (word + 40 * r) & 1023
        if (w & 127) + box_words > 128:
            return False
    return True


# THE SENTRIES: which characters are compiled. TWO CELS EACH, both
# facings: the AIM - the first of the art's FIRE cels, arm out and the gun
# level - and the RECOIL after it, which is what a shot looks like. A
# sentry does not walk (src/sentry.asm), so its four walk cels are not
# here. What decided two and not six is the BANKS: outside &C0 no bank
# has a hole over 4,094 bytes, because kcore, kextra and the tileset are
# pinned, and a facing is one blob in one bank. Two cels compiled whole
# were 5,200 to 6,500 bytes; the aim and the toggle are 3,200 to 3,900.
SENTRIES = (
    ("level1_city", "cityagent"),
    ("level2_forest", "forestsniper"),
    ("level5_desert", "desertmercenary"),
    ("level6_station", "stationcyber"),
)
LEV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                   "build", "levels")


def inc_value(path, key):
    for line in open(path):
        parts = line.split()
        if len(parts) >= 3 and parts[0].endswith(key) and parts[1] == "equ":
            return int(parts[2])
    raise SystemExit(f"{path}: no {key}")


ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def src_equ(path, key):
    """A literal `KEY equ &nnnn` out of the engine's own source, so the
    blob and the engine agree without the blob waiting for the assembly."""
    for line in open(os.path.join(ROOT, "src", path)):
        parts = line.split()
        if len(parts) >= 3 and parts[0] == key and parts[1] == "equ":
            return number(parts[2])
    raise SystemExit(f"src/{path}: no {key}")


def sentry(env, name, face):
    """-> (instructions, fresh, toggle, script length) for one facing."""
    inc = os.path.join(LEV, env, name + ".inc")
    aim = inc_value(inc, "_FIRE_FIRST")
    if inc_value(inc, "_BOX_W") != 12 or inc_value(inc, "_BOX_H") != 64:
        raise SystemExit(f"{name}: a sentry is 12 bytes by 64 lines")
    if inc_value(inc, "_FIRE_COUNT") < 2:
        raise SystemExit(f"{name}: a sentry's FIRE tag is an aim and a recoil")
    span = open(os.path.join(LEV, env, name + face + ".bin"), "rb").read()
    return sentry_code(cel_bytes(span, aim), cel_bytes(span, aim + 1), aim,
                       src_equ("enemy.asm", "ES_CEL"),
                       src_equ("main.asm", "ENEMY_SCRIPT"))


def build():
    """Every sentry's two compiled cels, beside its span blobs in
    build/levels: <name>c.bin facing right and <name>c_l.bin facing left,
    each nothing but the code - the engine jumps to the blob's own
    address, with that address in BC."""
    for env, name in SENTRIES:
        for f in ("", "_l"):
            ins, fresh, toggle, length = sentry(env, name, f)
            out = assemble(ins)
            open(os.path.join(LEV, env, name + "c" + f + ".bin"), "wb").write(out)
            if len(out) > 4094:
                raise SystemExit(f"{name}c{f}: {len(out)} bytes, and the hole "
                                 f"kcore leaves in a bank is 4,094")
            print(f"  {name}c{f}.bin  {len(out)} bytes: the aim "
                  f"{measure(fresh)[0]} T fresh, the toggle "
                  f"{measure(toggle)[0]} T; a script of {length}")


def main():
    if sys.argv[1:] == ["--build"]:
        return build()
    raise SystemExit("usage: compile_sprite.py --build")


if __name__ == "__main__":
    main()
