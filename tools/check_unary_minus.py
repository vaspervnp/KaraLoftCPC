#!/usr/bin/env python3
"""Refuse a unary minus on an equ the assembler has not seen yet.

RASM 3.2.5 DROPS THE SIGN: `ld bc,-TILE_H` with TILE_H defined in a later
include assembles as `ld bc,16`, `and -TILE_H AND 255` as `and &10`, and
`-X-1` as X-1 - no error, no warning, and the build is clean. Measured on
a scratch file, every form below with X an equ defined after it:

    ld a,-X   cp -X   db -X   ld bc,-X-1   ld bc,-X*2      wrong
    ld de,-(X)   ld bc,0-X   and 256-X   dw -LABEL         right

so it is the sign directly in front of a FORWARD equ and nothing else.
Write `0 - X` (or `-(X)`). CLAUDE.md 10 has the incident.

This walks src/main.asm with its includes expanded where they stand,
which is the order RASM sees, and exits 1 naming every site.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC, BUILD = os.path.join(ROOT, "src"), os.path.join(ROOT, "build")
OPS = set(",(+-*/%<>=&|^!~")
WORDOPS = {"AND", "OR", "XOR", "MOD", "SHL", "SHR", "EQU"}


def find(name, here):
    for base in (os.path.dirname(here), SRC, BUILD):
        p = os.path.join(base, name)
        if os.path.exists(p):
            return p
    return None


def expand(p, out):
    for n, raw in enumerate(open(p, errors="replace"), 1):
        code = raw.split(";")[0]
        m = re.match(r'\s*include\s+"([^"]+)"', code, re.I)
        if m:
            q = find(m.group(1), p)
            if q is None:
                sys.exit(f"check_unary_minus: cannot find {m.group(1)} ({p}:{n})")
            expand(q, out)
        else:
            out.append((p, n, code))
    return out


def sites(main):
    lines = expand(main, [])
    equ_at = {}
    for i, (_, _, code) in enumerate(lines):
        m = re.match(r'\s*([A-Za-z_][A-Za-z0-9_.]*)\s*:?\s+equ\s', code, re.I)
        if m:
            equ_at.setdefault(m.group(1).upper(), i)
    for i, (p, n, code) in enumerate(lines):
        m = re.match(r'\s*(?:[A-Za-z_][A-Za-z0-9_.]*:?\s+)?(equ|[A-Za-z]+)\s+(.*)$',
                     code, re.I) if code.strip() else None
        if not m:
            continue
        toks = re.findall(r'[A-Za-z_][A-Za-z0-9_.]*|&[0-9A-Fa-f]+|#[0-9A-Fa-f]+|\$|\d+|\S',
                          m.group(2))
        prev = None
        for k, t in enumerate(toks):
            if (t == "-" and (prev is None or prev in OPS or prev.upper() in WORDOPS)
                    and k + 1 < len(toks) and re.match(r'[A-Za-z_]', toks[k + 1])):
                d = equ_at.get(toks[k + 1].upper())
                if d is not None and d > i:
                    q, qn, _ = lines[d]
                    yield (f"{os.path.relpath(p, ROOT)}:{n}: -{toks[k + 1]} before its equ at "
                           f"{os.path.relpath(q, ROOT)}:{qn}   {code.strip()}")
            prev = t


if __name__ == "__main__":
    main = sys.argv[1] if len(sys.argv) > 1 else os.path.join(SRC, "main.asm")
    bad = list(sites(main))
    for b in bad:
        print(b)
    if bad:
        print(f"check_unary_minus: {len(bad)} unary minus on a forward equ - RASM drops the "
              f"sign; write 0 - X")
        sys.exit(1)
