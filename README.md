# Kara Loft and the Illuminati

An action platformer for the **Amstrad CPC 6128**, written in pure Z80
assembly. Six levels, each with its own scroll axis, in Mode 0 at 50 Hz.

> The Illuminati are trying to stop Kara Loft from reaching their
> orbital headquarters and recovering the star map that holds the
> coordinates where her father is held.

It starts on the rooftops of a night city and ends in orbit.

| # | Level | Scroll | Mechanic | Transition |
|---|---|---|---|---|
| 1 | City | horizontal | rooftops, a key for the underground garage, drones | escape by muscle car |
| 2 | Forest | horizontal | branch platforms, spike traps, an idol on an altar | into a cave mouth |
| 3 | Cave | vertical ↑ | climbing, a four-book gate puzzle | an earthquake, and a flood |
| 4 | Undersea | vertical ↓ | oxygen and buoyancy, mines, live cables | a siphon out to the oasis |
| 5 | Desert | horizontal | sinking sand, NPCs who talk for coins | a shuttle launch |
| 6 | Space station | horizontal | timed lasers, turrets, keycards | the map, and the escape pod |

Armament is two pistols with independent seven-round magazines. She
walks, runs (SHIFT), jumps, rolls (Z), climbs and swims, and the gun is
draw-hold-release on SPACE.

---

## Technical

The target is a real 6128, and every number below is **measured on an
emulator running a 6128 ROM set**, not estimated. [CLAUDE.md](CLAUDE.md)
is the technical contract; everything in it came from a measurement, and
most of its entries correct something that looked obvious and was not.

### The frame

A frame is **79,872 T-states**. The worst frame while scrolling:

| | T |
|---|---:|
| the incoming tile column, in two pieces | 16,504 |
| input, player, camera, bullets, logic | 7,080 |
| the heroine: composite + erase | 52,996 |
| **total** | **76,580 of 79,872** |

The order of work inside a frame is not a dependency order, it is a
**beam chase**. She is drawn in the top border where she is ahead of the
raster; the incoming column goes down behind the beam across two frames;
her erase is gated on an interrupt count, because the 6845 exposes no
scanline register.

### Scrolling

Hardware scrolling through the CRTC start address, horizontally and both
ways vertically. **R6 = 24, not 25**: 24 character rows display 960 of
the 1,024 words the CRTC can address, and the 64 that stay off-screen
are what makes vertical scrolling tear-free. The screen is a window into
a circular space of 1,024 words, not a linear buffer, so every address
calculation goes through the mask.

### Sprites

The heroine is **24×64** and her frames are stored as **spans**: per
line, only the bytes that are actually drawn. Just 34% of her box is
occupied, so the 61,440 bytes of land frames become 18,065 — the
difference between four banks and one.

**Both facings are stored.** Mirroring a Mode 0 byte is one bit
permutation and one 256-byte lookup, but the lookup needs an index
register the inner loop has not got: `HL` holds the mask and data, `DE`
the screen, `BC` the save. Measured at 96-136 T a byte against 72, about
7,900 T a frame. Mirroring at export time costs a bank instead of time.

### Tiles

8×16 pixels, stored **column-major**: for each character column of the
tile, that column's two bytes for all sixteen lines, consecutively.
Every blitter paints a character column at a time, so this turns the
step between lines into one `INC L` instead of three instructions —
64 T a raster instead of 76, at no cost in space.

### Compression and loading

Everything ships through **ZX0** (`dzx0_fast`), measured on a 6128
against the nine crunchers RASM bundles. It wins on **both ratio and
speed**: 19.5% at 49 T a byte, where Exomizer manages 19.3% for three
times the depack time.

A level's art is 57-77 KB unpacked, more than the five banks the window
can reach, so it loads per level as **one ZX0 stream per bank**: read,
page, unpack. The whole game's art is 223,975 bytes raw, 44,332 packed,
and a level change takes **1.38-1.74 s**.

The engine reads the floppy itself, driving the uPD765 through its
ports. There is no firmware left to call — the boot sequence disables
both ROMs, and the engine sits where the lower ROM would be — and the
level streams are raw sectors past the filesystem rather than AMSDOS
files, so there is no directory to parse either.

| | |
|---|---|
| Machine | Amstrad CPC 6128, 128 KB (the extra 64 is required, not optional) |
| Language | Z80 assembly, no runtime |
| Display | Mode 0, 160×200, 16 pens of 27 · title in overscan, 192×272 |
| Audio | AY-3-8912, three channels, SFX on C |
| Media | 3" floppy, a `.dsk` image with a BASIC loader |

---

## Building

```bash
./build.sh
```

produces `build/kara.dsk`. Needs `rasm`, `iDSK`, and Python with Pillow.

```bash
./tools/run_tests.sh
```

Nine acceptance suites, all of them against an emulator running a real
ROM: Mode 0 encoding, the sprite blobs against the artwork, the span
blitter against an independent address model, every bank of every level
unpacked byte for byte off a real disc image, the overscan layout, and
scrolling compared
against the **rendered framebuffer** rather than only against RAM.

**No module is considered done on a clean assemble.** Several of the
hardest bugs here passed every RAM check and showed up only on screen —
or passed a test that read the address the model says and found correct
bytes there, left by an earlier repaint.

## Layout

```
src/          the engine: bootstrap, blitters, scrolling, input, physics
tools/        Aseprite/Blender exporters, packers, the acceptance suites
assets/       the art: one directory per level with the artist's manifest
docs/         hardware palette, the level editor's design
plan.md       the original production plan (Greek)
CLAUDE.md     the technical contract - measurements, traps, module order
```

## Status

Modules 1-4 are done and module 5 is in progress. What runs today:
bootstrap and relocation, banking, the city scrolling both ways with
Kara over it, driven by input, colliding with tiles, jumping, and a
camera that follows her — at a locked 50 Hz. The span blitter and the
level loader are written and measured but not yet wired into the loop;
what is missing is the mid-game disc read, because the firmware went out
with the ROMs at boot. The order of work is in [CLAUDE.md](CLAUDE.md)
§11.
