#!/usr/bin/env python3
"""Build every level's sprite and tile blobs from the artist's manifests.

The art arrives as one directory per level with a manifest.json listing
its sheets and what each one is for, plus a handful of shared sheets at
the top (the heroine, the projectiles) and in common/ (the HUD). This
walks all of that and produces, per sheet:

    build/levels/<level>/<sheet>.bin       right-facing, or the only facing
    build/levels/<level>/<sheet>_l.bin     left-facing, where it is needed
    ... and the .inc and _frames.json the exporter always writes

Tiles go out raw (opaque, no mask); everything else is span-compressed.

WHICH SHEETS GET A SECOND FACING is a judgement the manifests do not
record, so it is written down here: anything that turns to face Kara or
travels in a direction. A pickup, a tile, a wall-mounted machine or a
thing bolted to the scenery does not, and each of those saved is
2-20 KB of bank.
"""
import json
import glob
import os
import re
import subprocess
import sys

def ident(name):
    return re.sub(r"[^A-Za-z0-9]", "", name).upper()


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
A = os.path.join(ROOT, "assets", "sprites")
OUT = os.path.join(ROOT, "build", "levels")

# Turns to face her, or travels: needs both facings.
MIRRORED = {
    # the heroine and what she throws
    "heroine", "heroine_actions", "heroine_swim", "bullet", "spear",
    # the seven people
    "city_agent", "forest_sniper", "cave_excavator", "desert_mercenary",
    "desert_nomad", "desert_informant", "station_cyber",
    # animals
    "forest_wolf", "forest_boar", "cave_bats",
    # machines that aim or travel
    "city_drone", "sea_drone", "station_turret",
    # and what those throw
    "city_drone_shot", "station_turret_shot", "station_plasma",
    "sea_torpedo",
}
# Bolted down, symmetrical, or only ever seen one way round: one facing.
#   city_car        the escape drives right and only right
#   desert_shuttle, desert_basedoor, station_pod, station_computer,
#   forest_altar, sea_siphon, sea_mine, sea_cable, sea_explosion
#   cave_books, cave_symbols, cave_quake_*, every pickup, every tile

# Kara's own frames, which no manifest lists because she is in every level.
SHARED = [
    # (directory, sheet stem, symbol, tiles?, extra args)
    (A, "heroine_cpc_mode0_sheet", "KCORE", False,
     ["--tags", "idle,walk,jump,shoot_draw,shoot",
      "--drop", "idle=3", "--drop", "walk=2,4,6",
      "--drop", "run=2,4,6", "--drop", "jump=3,5"]),
    (A, "heroine_cpc_mode0_sheet", "KEXTRA", False,
     ["--tags", "run,roll",
      "--drop", "idle=3", "--drop", "walk=2,4,6",
      "--drop", "run=2,4,6", "--drop", "jump=3,5"]),
    (A, "heroine_actions_cpc_mode0_sheet", "KACT", False, []),
    (A, "heroine_cpc_mode0_swim_sheet", "KSWIM", False, []),
    (A, "bullet_cpc_mode0_sheet", "BULLET", False, []),
    (A, "spear_cpc_mode0_sheet", "SPEAR", False, []),
    (os.path.join(A, "common"), "hud_icons_cpc_mode0_sheet", "HUDICON", False, []),
    (os.path.join(A, "common"), "hud_digits_cpc_mode0_sheet", "HUDDIGIT", False, []),
    (os.path.join(A, "common"), "hud_bars_cpc_mode0_sheet", "HUDBAR", False, []),
]
# The shared blobs keyed by the name MIRRORED uses
SHARED_MIRROR_KEY = {"KCORE": "heroine", "KEXTRA": "heroine",
                     "KACT": "heroine_actions", "KSWIM": "heroine_swim",
                     "BULLET": "bullet", "SPEAR": "spear"}


def export(js, out, inc, name, tiles=False, mirror=False, extra=()):
    cmd = [sys.executable, os.path.join(HERE, "aseprite2spans.py"), js,
           "-o", out, "--inc", inc, "--name", name, *extra]
    if tiles:
        cmd.append("--tiles")
    if mirror:
        cmd.append("--mirror")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"{js}:\n{r.stdout}{r.stderr}")
    return os.path.getsize(out)


def zx0(path):
    """Pack with RASM's ZX0 and return the packed size."""
    asm = path + ".pack.asm"
    out = os.path.splitext(path)[0] + ".zx0"
    open(asm, "w").write(f'        org 0\n        LZX0\n'
                         f'        incbin "{path}"\n        LZCLOSE\n')
    r = subprocess.run(["rasm", asm, "-amper", "-ob", out],
                       capture_output=True, text=True)
    os.remove(asm)
    if r.returncode:
        raise SystemExit(f"packing {path}:\n{r.stdout}{r.stderr}")
    return os.path.getsize(out)


# A blob has to fit one bank whole: its frame table is at its start and
# its offsets are relative to that, so it cannot straddle the window.
# The only sheets anywhere near the limit are the set pieces - the
# shuttle at 48x96 is 20 KB on its own - and they all have tags, so the
# split is by tag and the engine just refers to a smaller blob.
BANK_LIMIT = 12288


def do_sheet(dirn, stem, name, tiles, mirror, extra, dest):
    js = os.path.join(dirn, stem + ".json")
    if not os.path.exists(js):
        return []
    rows = []
    for suffix, mir in ((("", False),) if not mirror
                        else (("", False), ("_l", True))):
        base = os.path.join(dest, name.lower() + suffix)
        n = export(js, base + ".bin", base + ".inc",
                   name + ("L" if mir else ""), tiles, mir, extra)
        if n > BANK_LIMIT and not tiles:
            tags = [t["name"] for t in
                    json.load(open(js))["meta"].get("frameTags", [])]
            if len(tags) > 1:
                for ext in (".bin", ".inc", "_frames.json"):
                    if os.path.exists(base + ext):
                        os.remove(base + ext)
                for t in tags:
                    b2 = os.path.join(dest, f"{name.lower()}_{t}{suffix}")
                    n2 = export(js, b2 + ".bin", b2 + ".inc",
                                f"{name}{ident(t)}" + ("L" if mir else ""),
                                tiles, mir, list(extra) + ["--tags", t])
                    rows.append((os.path.basename(b2) + ".bin", n2,
                                 zx0(b2 + ".bin")))
                print(f"    {name}{suffix} was {n} bytes - split into "
                      f"{len(tags)} blobs by tag")
                continue
        rows.append((os.path.basename(base) + ".bin", n, zx0(base + ".bin")))
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)
    grand_raw = grand_pk = 0
    report = {}

    # ---- the shared set, loaded once and never swapped ----------------
    dest = os.path.join(OUT, "_shared")
    os.makedirs(dest, exist_ok=True)
    rows = []
    for dirn, stem, name, tiles, extra in SHARED:
        key = SHARED_MIRROR_KEY.get(name, name.lower())
        rows += do_sheet(dirn, stem, name, tiles, key in MIRRORED, extra, dest)
    report["_shared"] = rows

    # ---- one directory per level -------------------------------------
    for man in sorted(glob.glob(os.path.join(A, "level*", "manifest.json"))):
        d = os.path.dirname(man)
        lvl = os.path.basename(d)
        dest = os.path.join(OUT, lvl)
        os.makedirs(dest, exist_ok=True)
        kinds = {s["name"]: s["kind"] for s in json.load(open(man))["sheets"]}
        rows = []
        for js in sorted(glob.glob(os.path.join(d, "*_sheet.json"))):
            stem = os.path.basename(js)[:-5]
            sheet = stem[:-len("_cpc_mode0_sheet")]
            kind = kinds.get(sheet)
            if kind is None:
                kind = "sprites"        # a character the manifest omits
            rows += do_sheet(d, stem, sheet.upper().replace("_", ""),
                             kind == "tiles", sheet in MIRRORED, (), dest)
        report[lvl] = rows

    w = max(len(r[0]) for rs in report.values() for r in rs)
    for lvl, rows in report.items():
        raw = sum(r[1] for r in rows)
        pk = sum(r[2] for r in rows)
        grand_raw += raw
        grand_pk += pk
        print(f"\n  {lvl}   {raw} bytes, {pk} packed "
              f"({100 * pk / raw:.0f}%), {raw / 16384:.2f} banks unpacked")
        for n, a, b in sorted(rows):
            print(f"    {n:<{w}}{a:7d} -> {b:6d}")
    print(f"\n  everything: {grand_raw} raw, {grand_pk} packed "
          f"({100 * grand_pk / grand_raw:.0f}%)")
    json.dump({k: [{"file": n, "raw": a, "packed": b} for n, a, b in v]
               for k, v in report.items()},
              open(os.path.join(OUT, "sizes.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
