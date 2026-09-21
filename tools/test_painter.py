#!/usr/bin/env python3
"""The EDITOR's own level, on the emulator.

Every other check on the level editor is a comparison between two pieces
of software: C# against Python, one reader against one writer. This one
puts the editor's output on a disc and boots a 6128 with it, which is the
only witness this project treats as final (CLAUDE.md 5).

AND THE THING IT HAS TO PROVE IS NOT BYTE EQUALITY, because the editor
does not produce the generator's bytes and is not supposed to. A baked
overlay pair takes its tile index the first time it is placed, so the
numbering follows the order the placements arrive in: make_city_map.py
sweeps prop by prop and the painter lays cells down row by row, and
CLAUDE.md 8.3 has already written that the numbering is not part of the
contract. What IS the contract is the PICTURE - and a picture is what the
hardware can be asked about:

  * the map in RAM, cell by cell, resolved through the tile blob that
    was depacked into bank C4 - 2,048 cells of 64 bytes - must be the
    same 131,072 bytes as the shipped build's
  * the attribute under every one of those cells must be the same, which
    is the flags file lining up with the editor's own numbering
  * the entity table and ENT_COUNT must be the same records
  * and video RAM at the same game frame must be the same picture

  ... while the map BYTES differ, which is the numbering, and is the
  point rather than a tolerance.

AND THE LOADER'S OWN THREE CONTROLS COME WITH IT, because
tools/test_format.py cannot be pointed at this file: its first two checks
compare the .lvl against build/city_map.bin and build/city_entities.bin,
which are make_city_map.py's intermediates and not anything the editor
produces - and comparing the editor's file against the editor's own
statement of it would prove nothing at all. So the half that IS about the
engine is re-run here on the editor's bytes: break the magic and the
loader refuses, give it a map of another shape and it refuses, and zero
the ladder's flags in the file and the table in RAM loses TA_CLIMB.

THE CONTROLS FOR THE PICTURE, and both are the mistake that looks almost
right:

  * the editor's level with the SHIPPED tile blob under it. Every file is
    a real file and the level loads; the composited cells simply name
    tiles that hold something else. If the picture check cannot see that,
    it cannot see anything.
  * the same export with one cell PAINTED. The picture must differ, and
    at exactly the cells that were painted - which says the editor's edit
    reaches the glass and not only the file.

AND THE TILES ARE READ WITH peek AND NOT WITH read_ram, which is the one
thing here that would have made the whole comparison vacuous: read_ram is
documented as "base 64K RAM (banks 0-3), ignoring ROM paging", so at
&4000 it hands back bank 1 whatever the gate array has selected - the
same wrong bytes on both machines. It was written that way first, and
the check that caught it stays in: the blob in bank C4 has to be the
blob on the disc.

It costs four discs and four boots, so it is the last suite in
tools/run_tests.sh. It restores build/ with a full ./build.sh whatever
happens, and checks the disc comes back byte for byte.
"""
import hashlib
import os
import shutil
import subprocess
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import symbols, boot, sync, raw                     # noqa: E402
from build_levels import zx0                                   # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BUILD = os.path.join(ROOT, "build")
TILES = os.path.join(BUILD, "levels", "level1_city", "citytiles.bin")
DOTNET = "/home/vasilhs/.dotnet/dotnet"
CLI = os.path.join(ROOT, "editor", "src", "CpcLevelEditor.Cli")
SCRATCH = os.environ.get("KARA_SCRATCH") or os.path.join(
    "/tmp", f"kara-painter-{os.getuid()}")

# The four files an export is, and where each of them belongs in build/.
EXPORTED = {
    "level_1.lvl": BUILD,
    "tileflags_level1_city.bin": BUILD,
    "city_baked.json": BUILD,
    "citytiles.bin": os.path.dirname(TILES),
}
TILE_BYTES = 64                         # 4 bytes x 16 lines (CLAUDE.md 8.3)
CELLS = 128 * 16
SETTLE = 60                             # game frames after the level lands

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def run(*args, **kw):
    r = subprocess.run(args, capture_output=True, text=True, cwd=ROOT, **kw)
    if r.returncode:
        raise SystemExit(f"{' '.join(args)}:\n{r.stdout}{r.stderr}")
    return r.stdout


def export(out, paint=()):
    """The editor's four files, through the CLI the build would call."""
    shutil.rmtree(out, ignore_errors=True)
    args = [DOTNET, "run", "--project", CLI, "-v", "q",
            "--", "export", "--out", out]
    for cell in paint:
        args += ["--paint", cell]
    run(*args)
    return out


def install(src):
    """... into build/, where the assembler and the banker read them."""
    for name, dest in EXPORTED.items():
        shutil.copy(os.path.join(src, name), os.path.join(dest, name))
    zx0(TILES)                          # test_spans.py depacks this one


def relink():
    run(os.path.join(ROOT, "build.sh"), "--relink")


def witness(sym):
    """What the machine made of whatever is on the disc."""
    m = boot(sym, scroll=True)
    # THE SAME GAME FRAME ON BOTH MACHINES, not the same wall clock. The
    # tile blob packs to a different size, so the disc read is a
    # different length and the two boots reach SCROLL_INIT at different
    # moments; FRAME_COUNT is the loop's own count and is what makes the
    # two pictures comparable.
    target = (m.peek(sym["FRAME_COUNT"]) + SETTLE) & 255
    for _ in range(SETTLE * 4):
        m.run_frames(1)
        if m.peek(sym["FRAME_COUNT"]) == target:
            break
    sync(m, sym, 0)
    out = {
        "vram": bytes(m.read_ram(0xC000, 0x4000)),
        "map": bytes(m.read_ram(sym["MAP_ADDR"], CELLS)),
        "attr": bytes(m.read_ram(sym["TILE_ATTR"], sym["TILE_ATTR_N"])),
        "ents": bytes(m.read_ram(sym["ENT_TABLE"], 24 * 8)),
        "count": m.peek(sym["ENT_COUNT"]),
        "scroll": m.peek(sym["SCROLL"]) | (m.peek(sym["SCROLL"] + 1) << 8),
    }
    # ... and the WHOLE of bank C4's window as the depacker left it,
    # because a tile index is an address in it: the blob starts at
    # &4000 and the bake's sixteen scratch tiles are at &7C00, which is
    # exactly &4000 + 240 * 64 (CLAUDE.md 8.6). So every index 0-255
    # resolves at the same stride and the pickups Kara has not picked up
    # are in the picture too.
    #
    # PEEK AND NOT read_ram. read_ram is documented as "base 64K RAM
    # (banks 0-3), ignoring ROM paging", so at &4000 it hands back bank
    # 1 whatever the gate array has selected - the same wrong bytes on
    # every machine, which is a picture check that passes without
    # looking at the tiles. peek is the CPU-visible read and follows the
    # configuration; the check below is what says which one this is.
    raw(m, sym["BANK_SET_C4"])
    out["tiles"] = bytes(m.peek(0x4000 + i) for i in range(0x4000))
    out["m"] = m                        # ... for the loader controls below
    return out


def picture(w):
    """Every map cell resolved to the 64 bytes it actually draws."""
    tiles, out = w["tiles"], bytearray()
    for cell in w["map"]:
        out += tiles[cell * TILE_BYTES:(cell + 1) * TILE_BYTES]
    assert len(out) == CELLS * TILE_BYTES, "a cell did not resolve to a tile"
    return bytes(out)


def attributes(w):
    return bytes(w["attr"][cell] for cell in w["map"])


def differing_cells(a, b):
    pa, pb = picture(a), picture(b)
    return [i for i in range(CELLS)
            if pa[i * TILE_BYTES:(i + 1) * TILE_BYTES]
            != pb[i * TILE_BYTES:(i + 1) * TILE_BYTES]]


def main():
    os.makedirs(SCRATCH, exist_ok=True)
    saved = os.path.join(SCRATCH, "shipped")
    os.makedirs(saved, exist_ok=True)
    for name, src in EXPORTED.items():
        shutil.copy(os.path.join(src, name), os.path.join(saved, name))
    shipped_dsk = hashlib.md5(
        open(os.path.join(BUILD, "kara.dsk"), "rb").read()).hexdigest()

    print("\n  the build the game ships:")
    sym = symbols()
    blob = os.path.getsize(TILES)
    ship = witness(sym)
    check("it is the City, and the level is in RAM",
          ship["count"] and len(set(ship["map"])) > 20,
          f"{ship['count']} entities, {len(set(ship['map']))} distinct tiles "
          f"of {blob // TILE_BYTES} in the blob")
    # AND THE TILES REALLY ARE READ OUT OF BANK C4. Everything below
    # resolves a map cell through this blob, so a read that came back
    # with the same wrong bytes on both machines would make the picture
    # check pass without looking at anything.
    check("the blob in bank C4 is the one on the disc",
          ship["tiles"][:blob] == open(TILES, "rb").read(),
          f"{blob:,} bytes, through ZX0 and the disc into the window")

    try:
        print("\n  the editor's own export:")
        made = export(os.path.join(SCRATCH, "export"))
        check("the four files came out",
              all(os.path.exists(os.path.join(made, n)) for n in EXPORTED),
              ", ".join(f"{n} {os.path.getsize(os.path.join(made, n))}B"
                        for n in EXPORTED))
        editor_lvl = open(os.path.join(made, "level_1.lvl"), "rb").read()
        shipped_lvl = open(os.path.join(saved, "level_1.lvl"), "rb").read()
        differ = sum(1 for a, b in zip(editor_lvl, shipped_lvl) if a != b)
        check("... and it is NOT the generator's file, byte for byte",
              len(editor_lvl) == len(shipped_lvl) and differ > 0,
              f"{differ} of {len(editor_lvl)} bytes differ - the numbering "
              f"follows the placement order, which CLAUDE.md 8.3 says is "
              f"not part of the contract")

        install(made)
        relink()
        paint = witness(sym)

        print("\n  and the machine, booted off a disc made of them:")
        check("the editor's blob is in the bank, depacked",
              paint["tiles"][:blob] == open(os.path.join(made, "citytiles.bin"), "rb").read()
              and paint["tiles"][:blob] != ship["tiles"][:blob],
              "and it is not the shipped one - the baked tiles are in the "
              "painter's order")
        check("the level loaded at all",
              paint["count"] == ship["count"] and len(set(paint["map"])) > 20,
              f"{paint['count']} entities, {len(set(paint['map']))} distinct "
              f"tiles - a refused header would leave the map at zero")
        check("THE PICTURE IS THE SAME PICTURE",
              picture(paint) == picture(ship),
              f"{CELLS} cells of {TILE_BYTES} bytes = "
              f"{CELLS * TILE_BYTES:,} bytes, resolved through the blob the "
              f"depacker put in bank C4")
        check("... and so is what every cell DOES",
              attributes(paint) == attributes(ship),
              f"{len(set(attributes(ship)))} distinct attributes over the "
              f"map - the flags file lining up with the editor's numbering")
        check("... and the entity table is the same records",
              paint["ents"] == ship["ents"],
              "8 bytes a slot, 24 slots, in RAM's own layout")
        check("... and the screen is the same screen",
              paint["vram"] == ship["vram"],
              f"all {len(ship['vram']):,} bytes of video RAM at game frame "
              f"{SETTLE}, which is the beam's own answer")
        check("while the MAP BYTES are the editor's, not the generator's",
              paint["map"] != ship["map"],
              f"{sum(1 for a, b in zip(paint['map'], ship['map']) if a != b)} "
              f"of {CELLS} cells name a different tile index for the same "
              f"picture")

        # ---- and the loader's own controls, on the editor's bytes ----
        # tools/test_format.py's three, re-run against a file it cannot
        # itself be pointed at: its first two checks compare the .lvl
        # against build/city_map.bin and build/city_entities.bin, which
        # are make_city_map.py's own intermediates and not something the
        # editor produces - and comparing the editor's file with the
        # editor's own statement of it would prove nothing.
        print("\n  the loader, on the editor's own bytes:")
        machine = paint["m"]
        flags_file = open(os.path.join(made, "tileflags_level1_city.bin"), "rb").read()
        check("TILE_ATTR is the editor's flags file",
              paint["attr"][:len(flags_file)] == flags_file
              and set(paint["attr"][len(flags_file):]) == {0},
              f"{len(flags_file)} tiles, {sum(1 for f in flags_file if f)} "
              f"with anything on, and all {len(paint['attr'])} indices there")

        def reinstall():
            machine.write_ram(sym["MAP_ADDR"], bytes(CELLS))
            raw(machine, sym["MAP_INSTALL"])
            return bytes(machine.read_ram(sym["MAP_ADDR"], CELLS))

        check("re-running the loader puts the map back",
              reinstall()[:16] == paint["map"][:16],
              "which is what the three below are measured against")

        machine.poke(sym["LEVEL_LVL"], ord("X"))        # "XV" is not a level
        check("a broken magic is refused, and the map is left alone",
              set(reinstall()) == {0})
        machine.poke(sym["LEVEL_LVL"], ord("L"))

        machine.poke(sym["LEVEL_LVL"] + 5, 64)          # a 64-tile-wide map
        check("a map of another shape is refused too", set(reinstall()) == {0})
        machine.poke(sym["LEVEL_LVL"] + 5, 128)

        # THE LADDER, FOUND IN THE FILE AND NOT LOOKED UP ANYWHERE: it is
        # the one tile the editor marked Ladder|Platform, which is the
        # pairing that lets her walk over the top rung and step down onto
        # the shaft (CLAUDE.md 8.8).
        rungs = [i for i, f in enumerate(flags_file) if f == 8 | 2]
        check("exactly one tile is a ladder AND a platform", len(rungs) == 1,
              f"tile {rungs} of {len(flags_file)}")
        machine.poke(sym["LEVEL_TILEFLAGS"] + rungs[0], 0)
        reinstall()
        check("and the flags come from the file, not from the engine",
              machine.peek(sym["TILE_ATTR"] + rungs[0]) == 0,
              "zero the ladder in the editor's own file and the table in "
              "RAM loses TA_CLIMB with it")

        # ---- control 1: the editor's level over the shipped blob ------
        print("\n  the control - the same level with the wrong tile blob:")
        shutil.copy(os.path.join(saved, "citytiles.bin"), TILES)
        zx0(TILES)
        relink()
        wrong = witness(sym)
        bad = differing_cells(wrong, ship)
        check("the picture comes out WRONG, and the check says so",
              len(bad) > 0,
              f"{len(bad)} of {CELLS} cells draw something else - every file "
              f"is real and the level loads, so this is what the picture "
              f"check is for")
        check("... and the screen is wrong with it", wrong["vram"] != ship["vram"])

        # ---- control 2: one cell painted ------------------------------
        print("\n  the other control - one cell painted in the editor:")
        # A roof tile in the middle of the street's own row, far from the
        # walks the other suites make and from the roof's gap.
        cells = ["40,14=crate", "41,14=crate"]
        made = export(os.path.join(SCRATCH, "export-painted"), paint=cells)
        install(made)
        relink()
        after = witness(sym)
        moved = differing_cells(after, ship)
        want = sorted(int(c.split(",")[1].split("=")[0]) * 128
                      + int(c.split(",")[0]) for c in cells)
        check("the painted cells are the ones that changed",
              moved == want,
              f"cells {moved} changed against {want} painted - "
              f"{', '.join(cells)}")
        check("... and the rest of the picture did not move",
              len(moved) == len(cells),
              "which is what says the edit reached the glass and nothing "
              "else did")
    finally:
        print("\n  putting build/ back:")
        for name, dest in EXPORTED.items():
            shutil.copy(os.path.join(saved, name), os.path.join(dest, name))
        run(os.path.join(ROOT, "build.sh"))
        back = hashlib.md5(
            open(os.path.join(BUILD, "kara.dsk"), "rb").read()).hexdigest()
        check("the shipped disc is back, byte for byte", back == shipped_dsk,
              f"md5 {back[:12]}")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
