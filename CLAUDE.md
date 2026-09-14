# CLAUDE.md — Kara Loft and the Illuminati (Amstrad CPC 6128)

Z80 assembly game for the Amstrad CPC 6128. The design document is [plan.md](plan.md)
(written in Greek); this file holds the technical contract that code must satisfy.
**Where this file and plan.md disagree, this file wins** — see §11 for the specific
corrections and why.

## 1. Status

**Modules 1-4 done.** `./build.sh` regenerates the assets, assembles, and
produces `build/kara.dsk`. It boots, relocates, passes its bank self-test, runs
Kara walking and firing over a striped background with full save-under restore,
and then hands over to the scrolling city: a tilemap in bank C4 moved by the
CRTC start address, horizontally and both ways vertically. `./tools/run_tests.sh`
runs every acceptance suite; all six pass. Modules 5-7 (§11) are not started.

```
src/main.asm      bootstrap at &4000 + core engine at &0040
src/config.asm    ports and memory map constants
src/bank.asm      bank switching (must stay outside &4000-&7FFF)
src/screen.asm    Mode 0 addressing, block fill, palette, vsync
src/palette.asm   the 16 pens + solid-pen byte table
src/sprite.asm    masked blitter, save-under restore, scanline stepping
src/bullets.asm   dual pistols, 14-round pool, reloading
src/tilemap.asm   CRTC hardware scrolling, tile rendering out of bank C4
disc/disc.bas     ASCII BASIC loader

tools/cpclib.py            Mode 0 encoding, palette, screen layout - the one
                           place the bit interleaving is written down
tools/png2sprite.py        sprite sheet  -> data+mask binary
tools/png2screen.py        image         -> overscan.bin / 16K screen
tools/png2tiles.py         16x16 tile sheet -> 128 bytes/tile + .inc
tools/make_placeholder_level.py  the stand-in city tiles and 64x16 map
tools/blender_title.py     the title scene and its CPC render settings
tools/make_placeholder_sprites.py
tools/test_*.py            acceptance suites
tools/run_tests.sh         all of them, in order

assets/placeholder/        stand-in sprite art, to be replaced
assets/title/              the title render
docs/                      hardware reference tables
```

Nothing INCBINs the asset binaries yet: Module 3 links the sprites, Module 6
the title screen. `build.sh` regenerates them anyway so they cannot drift.

## 2. Target platform (hard constraints)

| Property | Value |
|---|---|
| Machine | Amstrad CPC 6128, 128 KB RAM (the extra 64 KB is required, not optional) |
| CPU | Z80 @ 4 MHz nominal; gate array wait states make every instruction a multiple of 1 µs |
| Video | Mode 0 in-game (160×200, 16 pens from 27 hardware colours) |
| Title screen | Overscan Mode 0, 192×272 pixels, 26,112 bytes of VRAM |
| Audio | AY-3-8912, 3 channels + 1 noise generator |
| Media | 3" floppy `.dsk` image, loaded by a BASIC loader |
| Frame | 312 scanlines × 64 µs = 19,968 µs = 79,872 T-states @ 50 Hz |

## 3. Toolchain (verified present on this machine)

| Tool | Location | Version |
|---|---|---|
| RASM (assembler) | `/usr/local/bin/rasm`, source in `/home/vasilhs/rasm` | v3.2.5 (Atlas) |
| iDSK (disk imager) | `/usr/local/bin/iDSK`, source in `/home/vasilhs/idsk` | 0.20 |
| Headless emulator | `/home/vasilhs/cpcemu/cpc.py` (+ `libcpcheadless.so`) | floooh/chips |
| Python | system `python3` 3.14 with Pillow 12.3 | — |
| ffmpeg | `/home/vasilhs/bin/ffmpeg` | for the audio pipeline |
| Blender | MCP tools (`mcp__Blender__*`) — no CLI binary on PATH | render pipeline |
| Aseprite | **not available** — no CLI and no MCP server is connected | see §7.2 |

RASM can emit the DSK itself via a `SAVE "GAME.BIN",start,length,AMSDOS,"kara.dsk"`
directive, which is usually simpler than post-processing with iDSK. Use iDSK when you
need to inspect or patch an existing image:

```bash
iDSK kara.dsk -l
```

The project uses the two-step route, wrapped in `build.sh`:

```bash
./build.sh
```

`-t 1` = binary, `-c` = load address, `-e` = execution address, `-f` = overwrite.

**`rasm` needs `-amper`.** Without it `&` is the bitwise AND operator and every
hex literal in this codebase fails to parse. `build.sh` passes it; any ad-hoc
`rasm` invocation must too.

## 4. Boot sequence

AMSDOS can only land the binary somewhere BASIC is not, and BASIC occupies
`&0170` upward — so the load address is `&4000`, which is exactly the banked
window nothing may live in. The code at `&4000` is therefore a **bootstrap, not
the engine**:

1. `DI`, `LD SP,&BFFF`.
2. Write `&8C` to the gate array: Mode 0, **both ROMs disabled**. The lower ROM
   must go before any execution at `&0040`, or reads from `&0000-&3FFF` come
   from the OS ROM instead of the relocated code.
3. Select RAM config `&C0` so the window is in a known state.
4. `LDIR` the core engine image down to `&0040` (source and destination do not
   overlap) and `JP` into it. There is no way back to BASIC after this.
5. The core rewrites `&0038` with `JP IRQ_HANDLER` before the first `EI`, since
   the firmware's handler went out with the lower ROM.

`ORG code,output` in RASM is what lets the core be assembled for `&0040` while
being stored in the file after the bootstrap.

## 5. Test loop — always verify in the emulator

Never declare a module working on a clean assemble alone. The headless emulator boots a
real 6128 ROM set, accepts a `.dsk`, and renders to a framebuffer, so every visual claim
is checkable. Run from `/home/vasilhs/cpcemu` (or add it to `sys.path`):

```python
from cpc import CPC
c = CPC()                      # boots a 6128
c.run_frames(200)              # reach the BASIC prompt
c.insert_disc("kara.dsk")
c.type_text('RUN"DISC\n')
c.run_frames(500)
c.screenshot("shot.png", aspect=True)
```

Useful members: `peek/poke`, `read_ram/write_ram`, `run_code(addr, code)`, `pc`,
`mode`, `crtc_screen_addr`, `palette()`, `framebuffer()` (1024×312, 8-bit indices into
the 32-entry hardware palette), `decode_screen_ram()`, `joystick(mask)`, `quickload()`.

Two gotchas learned from probing it:

* The framebuffer is **hardware-colour indexed**, not pen indexed. To recover pen
  numbers, either set a known ink mapping first or use `decode_screen_ram()`.
* `crtc_screen_addr` returns the raw R12/R13 value. Convert to a RAM address with
  `base = ((raw & 0x3000) << 2) | ((raw & 0x0300) << 1) | ((raw & 0xFF) << 1)`.
  Do not assume `&C000` — BASIC scrolling moves it.

One Mode 0 pixel spans 4 framebuffer columns; the visible area starts at x=64.

**Sampling the screen needs a sync point.** Drawing takes most of a frame, so a bare
`run_frames()` leaves the CPU inside the blitter and a test reads a half-drawn
screen. Step with `run_us(4)` until `pc` is in the `WAIT_VSYNC` spin — the one
moment when the last frame is finished and the next has not begun. Do any
border-band profiling *before* that stepping, though: leaving the machine
mid-scanline skews the bands.

## 6. CPC 6128 hardware reference

### 6.1 Memory map (base 64 KB)

```
&0000-&003F  Z80 restart vectors + IM 1 interrupt handler
&0040-&3FFF  Core engine, scrolling engine, sound driver      (never banked out)
&4000-&7FFF  Level logic, collision data, entity management   (BANKED WINDOW)
&8000-&BFFF  Sprite buffers, background restore buffers, temp (never banked out)
&C000-&FFFF  Primary video RAM
```

### 6.2 Banking (gate array port `&7Fxx`)

Writing `&C0`–`&FF` to port `&7F` selects a RAM configuration. Only the `&4000-&7FFF`
window changes in the configurations this project uses:

| Config | `&0000` | `&4000` | `&8000` | `&C000` | Project use |
|---|---|---|---|---|---|
| `&C0` | 0 | 1 | 2 | 3 | default / `BANK_RESTORE` |
| `&C4` | 0 | 4 | 2 | 3 | Levels 1–2 tiles, tilemaps, palette animation |
| `&C5` | 0 | 5 | 2 | 3 | Levels 3–4 tiles, subsea physics tables |
| `&C6` | 0 | 6 | 2 | 3 | Levels 5–6 tiles, space station assets |
| `&C7` | 0 | 7 | 2 | 3 | Overscan title buffer + NPC dialogue tables |

```asm
BANK_SET_C4:    ld   bc,&7FC4
                out  (c),c
                ret
```

**Three rules, all of them crash-class:**

1. The bank-switching routine itself must live outside `&4000-&7FFF` — put it in
   `&0040-&3FFF` or `&8000-&BFFF`.
2. The stack must never be inside the banked window, and never inside VRAM.
   `LD SP,&BFFF` at startup.
3. Any data structure read across a bank switch must be copied to base RAM first.

The overscan title screen is 26,112 bytes and does not fit one 16 KB bank; it is split
across two banks and assembled into VRAM in two passes.

### 6.3 Mode 0 pixel encoding — VERIFIED

Each byte holds 2 pixels, bits interleaved. Bit numbers on the right are the **pen
number's** bit weights (bit 0 = value 1, bit 3 = value 8):

```
byte bit 7 -> left  pixel (pixel 0), pen bit 0
byte bit 6 -> right pixel (pixel 1), pen bit 0
byte bit 5 -> left  pixel (pixel 0), pen bit 2
byte bit 4 -> right pixel (pixel 1), pen bit 2
byte bit 3 -> left  pixel (pixel 0), pen bit 1
byte bit 2 -> right pixel (pixel 1), pen bit 1
byte bit 1 -> left  pixel (pixel 0), pen bit 3
byte bit 0 -> right pixel (pixel 1), pen bit 3
```

Encode (`p0`, `p1` are pen numbers 0-15):

```python
byte = (((p0 >> 0) & 1) << 7) | (((p1 >> 0) & 1) << 6) \
     | (((p0 >> 2) & 1) << 5) | (((p1 >> 2) & 1) << 4) \
     | (((p0 >> 1) & 1) << 3) | (((p1 >> 1) & 1) << 2) \
     | (((p0 >> 3) & 1) << 1) | (((p1 >> 3) & 1) << 0)
```

Confirmed on the emulator by poking single bits into screen RAM and reading back the
rendered colour, and it matches `_decode_byte()` in `cpc.py`. **plan.md §4.2 states this
table with bits 0↔3 and 1↔2 swapped and is wrong** — an exporter built from the plan's
table produces scrambled palette indices. Every asset exporter must use the table above,
and every exporter needs a round-trip unit test (encode → decode → original pens).

### 6.4 Screen addressing

Standard (non-overscan) layout, 80 bytes per line, base `&C000`:

```
addr = base + (line & 7) * &0800 + (line >> 3) * 80 + x_byte
```

That form assumes the CRTC start address is zero. Once anything scrolls it no
longer holds, and the general model — verified against the emulator at six
start addresses, 2,400 sampled bytes each, wrap-crossing ones included, with
zero mismatches — is:

```
addr = ((MA & &3000) << 2) | ((RA & 7) << 11) | ((MA & &3FF) << 1)

MA = start + char_row * R1 + char_column        RA = raster 0-7 within the row
```

The `& &3FF` is the part that bites. **The screen is a window into a circular
space of 1024 words, not a linear buffer**, because the gate array only drives
MA0-MA9 onto the address bus. Everything that computes a screen address —
tiles, sprites, HUD — has to apply that mask, and code that walks the screen by
adding a constant is only correct while it stays inside one character row.

Advancing one scanline inside the blitter:

```asm
                ld   bc,&0800
                add  hl,bc          ; next scanline within the char row
                jr   nc,.same_row   ; crossed the 8-line boundary?
                ld   bc,&C050       ; +&C050 wraps to the next char row
                add  hl,bc
.same_row:
```

### 6.5 Overscan title screen (192×272)

CRTC registers. **One CRTC character = 2 bytes**, so R1=48 gives 96 bytes/line:

| Reg | Value | Meaning |
|---|---|---|
| R0 | 63 | horizontal total (64 chars) |
| R1 | 48 | horizontal displayed → 96 bytes/line → 192 Mode 0 pixels |
| R2 | 50 | horizontal sync position |
| R6 | 34 | vertical displayed → 34 × 8 = 272 scanlines |
| R7 | 35 | vertical sync position |

96 bytes × 272 lines = **26,112 bytes**. plan.md's "48 chars × 4 bytes = 192 bytes"
is arithmetically wrong but arrives at the correct 192-pixel width and the correct
total; use 96 bytes/line.

**The screen cannot be one buffer.** The CRTC only drives MA0-MA9 onto the address
bus, so one raster block reaches 1024 words = 2048 bytes. At 48 chars per line that
is 21 character rows, and overscan needs 34. So the screen is **two halves of 17
rows** (136 lines, 13,056 bytes each), each laid out exactly like a normal CPC
screen, with the display code re-pointing R12/R13 at the second half partway down
the frame:

```
offset within a half = (line AND 7) * &0800 + (line >> 3) * 96 + x   ; peaks at 15,967
```

Verified on the emulator, including the failure mode: programmed as 34 rows in one
buffer, rows 17-20 draw blank and the address counter folds back mid-row-21, redrawing
the top of the picture. `tools/test_overscan.py` asserts both directions.

`overscan.bin` is stored in **copy order** — half 0 raster blocks 0-7, then half 1 —
each block 17 rows × 96 bytes = 1,632 bytes, so the loader is eight LDIRs per half
rather than a scatter.

### 6.6 Palette and fades

Gate array port `&7F00`: write `&00-&0F` to select a pen (`&10` for border), then the
hardware colour value; the verified ink/hardware/port table is in
[docs/cpc_palette.md](docs/cpc_palette.md) and the game's 16 pens are in
`src/palette.asm`. Fades walk each pen through a luminance-ordered ramp toward
black and back; keep the ramp as a table, not as arithmetic on colour codes.

### 6.7 AY-3-8912

Accessed through PPI port A (`&F4`) with control on `&F6`. Register set: R0-R5 tone
periods, R6 noise period, R7 mixer, R8-R10 channel volumes, R11-R13 hardware envelope.
The music player runs from the 50 Hz interrupt. Channel C is the SFX carrier: gunshots
and hurt sounds steal it via the noise generator and volume envelope, then hand it back
to the music without a re-trigger click.

## 7. Asset pipeline

### 7.1 Sprites

Kara Loft is 16×48 pixels → 8 bytes wide × 48 lines.

```
data frame : 8 × 48 = 384 bytes
AND mask   : 8 × 48 = 384 bytes
total      : 768 bytes per frame
```

Mask convention: mask bits **set where the background shows through**, clear where the
sprite pixel is opaque, so the blitter does:

```
SCREEN = (SCREEN AND MASK) OR DATA
```

Because Mode 0 interleaves, a pixel's four mask bits are not adjacent: the left pixel
owns the odd bits (`&AA`) and the right pixel the even ones (`&55`). A transparent left
pixel therefore contributes `&AA`, not `&F0`.

**Mask and data are interleaved per byte**, so the blitter walks both with one pointer:

```
line 0:  mask0 data0 mask1 data1 ... mask7 data7
line 1:  ...

ld a,(de) : and (hl) : inc hl : or (hl) : inc hl : ld (de),a : inc de
```

Produced by `tools/png2sprite.py`, emitted for `INCBIN`, with a generated `.inc` of
frame count and sizes. Sprites are quantised against the pens in `src/palette.asm`,
not against their own image, so they match the level they are drawn over.

### 7.2 Aseprite is not available

plan.md assumes an Aseprite MCP server. Nothing on this machine provides Aseprite, so
the sprite front end reads PNG sheets via Pillow instead. Swapping in Aseprite later
changes nothing downstream — the output format is unaffected.

### 7.3 Blender

**Blender runs on Windows (5.2.1 LTS), not inside WSL.** Consequences:

* Render paths passed to `bpy` must be Windows paths (`C:\Users\vasilhs\...`); read
  the result back from WSL under `/mnt/c/...`.
* Blender cannot see this repository, so scripts are injected as source through
  `execute_blender_code` rather than imported by path.
* The EEVEE enum name differs between versions — this build has `BLENDER_EEVEE`, not
  `BLENDER_EEVEE_NEXT`. Pick from `render.bl_rna.properties["engine"].enum_items`.

**The open Blender session contains unrelated unsaved work** (a scene of ~200 objects).
`tools/blender_title.py` therefore builds into its own scene, `KaraTitle`, never clears
anything, and restores the active scene when it finishes. Keep it that way.

Render settings that matter: 192×272 at 100%, and **pixel aspect 2:1**, because Mode 0
pixels are twice as wide as they are tall — without it the art is framed for a shape
the hardware never shows. Camera is orthographic, per plan.md.

`tools/png2screen.py` then picks 16 of the 27 hardware colours by usage, optionally
Floyd-Steinberg dithers (worth it — a render banded to 16 colours looks poor without
it), and writes `overscan.bin` plus a palette include and a preview.

## 8. Game architecture

### 8.1 Level flow

Six levels, each with its own scroll axis:

| # | Level | Scroll | Bank | Signature mechanic |
|---|---|---|---|---|
| 1 | City | horizontal L→R | C4 | rooftop jumps, key → garage |
| 2 | Forest | horizontal L→R | C4 | branch platforms, spikes, statue-on-altar |
| 3 | Cave | vertical bottom→top | C5 | climbing, 3-symbol book/lever puzzle |
| 4 | Undersea | vertical top→bottom | C5 | buoyancy + oxygen, mines, live cables |
| 5 | Desert | horizontal L→R | C6 | sinking sand, coins → NPC hints |
| 6 | Space station | horizontal L→R | C6 | laser traps, keycards, boss |

FSM: `STATE_LEVEL_PLAY → STATE_LEVEL_CLEAR → STATE_CUTSCENE → STATE_LOAD_NEXT`.

### 8.2 Scrolling — implemented and measured

Scrolling is two `OUT`s to CRTC R12/R13 plus a repaint of the one edge that is
new. `SCROLL` is the start address in words, always masked to 0-1023;
`WORLD_X` and `WORLD_CR` are where the top-left of the screen sits in the map,
in characters. The three step together or the picture and the map disagree.

**`R6 = 24`, not 25.** 24 character rows display 960 of the 1024 words, which
leaves 64 permanently off-screen — more than the 40 words of one character row.
That margin costs 8 scanlines of picture and is what makes vertical scrolling
tear-free. It is the single most important decision in the module.

**Syncing to VBLANK is not enough.** Every scroll step writes into memory that
is on screen at that moment, so what matters is *where*, and the answer differs
per axis:

| Axis | Order | Why |
|---|---|---|
| Horizontal | state → apply → paint | The incoming column is not hidden: under the old start address those cells are the left edge of each row below. Latch the new address first, then paint top-down and outrun the beam. |
| Vertical down | state → apply → paint | New bottom row lands at offset 960 — hidden. Painted long before the raster reaches line 184. |
| Vertical up | state → paint → apply | New top row lands at offset 984 — hidden — but the raster reaches line 0 only 18,432 T into the frame, far too early for a 51,600 T row redraw. Painting first and moving the picture one frame later is invisible and always correct. |

The horizontal race is won comfortably: VSYNC leaves 72 scanlines (18,432 T) of
head start, and a character cell costs ~1,290 T against the beam's 2,048 T per
character row. It only holds if `DRAW_COLUMN` runs **top to bottom**.

Getting any of this backwards does not crash and does not corrupt video RAM —
it puts a 4-pixel column of the wrong tile down one edge of every frame. That
is why `tools/test_module4.py` compares the **rendered framebuffer**, not just
RAM, and why it carries a negative control: reversing the horizontal ordering
leaves all 15,360 RAM bytes correct and produces 272 wrong pixels on screen.

Two traps the emulator sets while testing this:

* Its framebuffer is a **live raster buffer**, not a completed frame. Sampling
  mid-sweep returns the new frame's top over the old frame's bottom, which
  looks exactly like tearing and is not. Sample in the instant after VSYNC.
* The 300 Hz interrupt pulls the PC out of `WAIT_VSYNC` six times a frame, so
  "the PC left the spin" means "an interrupt fired", not "a frame ended". Watch
  a counter the game itself increments.

Tiles are 16×16 pixels = 8 bytes × 16 lines, so a tile spans 4 character
columns and 2 character rows. Map dimensions are powers of two (64×16) so the
map wraps with an `AND` instead of a divide. Tiles and map are staged into bank
C4 by `TILES_INSTALL`; they ride inside the core image, so the boot relocation
has already put them in base RAM, which is the only reason a plain `LDIR` into
the `&4000` window works.

Not yet done, and deliberately: **sprites over a scrolled screen.** The blitter
walks the screen with a fixed `+&0800` / `+&C050` step, which is only correct
while the start address is zero. Over a scrolled screen a sprite must take its
address from the same masked word index the tile engine uses, recomputed at
each character-row boundary, and handle the case where its 4 words straddle the
1024-word seam. Module 4's demo therefore does not draw Kara. This is the first
task of Module 5.

Tiles are 16×16 pixels = 8 bytes × 16 lines. Tilemaps live in banked RAM.

### 8.3 Dual pistols

```
MAG_LEFT     0-7      rounds in left pistol
MAG_RIGHT    0-7      rounds in right pistol
ACTIVE_GUN   0/1      alternates every shot, left first
RELOAD_TIMER frames   1.2 s = 60 frames @ 50 Hz
AMMO_RESERVE bytes    clips add 14
```

14 bullets in flight max, one pool entry per round: `{active, x, y, direction, life}`.
Bullets move 4 pixels/frame and die on a solid tile. Reload is manual (Down+Fire) or
automatic when both magazines hit 0; during reload the player is slowed or frozen.

### 8.4 Game state

```asm
PLAYER_HP:        db 100     ; 0-100, medkit restores 35, capped at 100
KEYS_COUNT:       db 0
COINS_COUNT:      db 0
AMMO_RESERVE:     db 28
STATUES_HELD:     db 0
CURRENT_BOOK_ID:  db 0
```

Interaction handlers: `CHECK_KEY_DOOR`, `PLACE_STATUE`, `READ_BOOK_PUZZLE`,
`TALK_NPC_COIN`, `USE_MEDKIT`, all gated by an AABB test in `ENTITY_COLLISION_CHECK`.

## 9. Performance budget — measured directly, and it closes

A frame is **79,872 T-states**.

**Do not use border bands to profile.** The demo still paints them, and they
are useful for *seeing* where time goes, but they under-report: the emulator
renders 40 of its 312 framebuffer rows as colour index 0 during vertical
blanking regardless of the border register, so those 40 scanlines (10,240 T)
are invisible to a counter — and they land on whichever phase runs first after
`WAIT_VSYNC`. That is how §9 came to record the erase at 6,144 T when it is
13,856, and the Module 4 scroll step at 21,504 T when it was 29,620.

Time routines by **calling them from a `DI` stub and summing `run_us()`**:

```python
m.write_ram(STUB, bytes([0xF3, 0xCD, lo, hi, 0x18, 0xFE]))   # di : call nn : jr $
m.set_pc(STUB)
while m.pc != STUB + 4: m.run_us(1)      # 1 us = 4 T
```

`tools/bench.py` wraps this; subtract the ~40 T stub overhead.

### Measured, after the Module 5 optimisation pass

| Routine | Before | After | |
|---|---:|---:|---|
| `HUD_UPDATE` (dirty) | 49,040 | **15,560** | one pass per row, not 7 `DRAW_BLOCK` calls |
| `DRAW_BLOCK` (3×8) | 3,308 | **1,696** | address computed once, not per scanline |
| `SCROLL_H_STEP` | 29,620 | **23,500** | hoisted tile lookup, word index in `BC` |
| `DRAW_ROW` (40 cells) | 49,208 | **37,124** | same, and now split across two frames |
| `KARA_DRAW` | 30,948 | 31,272 | +324 for scroll-aware addressing |
| `KARA_ERASE` | 13,584 | 13,856 | +272, same reason |
| `BUL_DRAW` / `BUL_ERASE` | | 1,876 / 1,192 | |
| `GAME_LOGIC` | | 1,780 | |

### The frame, in situ

Measured as the real loop period (time between `FRAME_COUNT` increments), not
as a sum of estimates:

| Loop | Worst frame | Result |
|---|---:|---|
| Kara over the scrolling city, horizontal | 19,972 µs | **50 Hz** |
| vertical down | 20,028 µs | **50 Hz** |
| vertical up | 19,976 µs | **50 Hz** |
| Module 1-3 acceptance screen | 24,252 µs | drops a frame when the HUD redraws |

The scrolling path — which is the game — closes at about 86% of a frame with
roughly 11,000 T spare. Two routines are 68% of it: `KARA_DRAW` at 31,272 and
`SCROLL_H_STEP` at 23,500.

### Three raster constraints, all of them load-bearing

The order of work in the main loop is not a data-dependency order, it is a
**beam chase**, and each of these was found by a test rather than by reasoning:

1. **The scroll step must go first.** Its incoming column is visible under the
   new start address; it only wins the race by starting at VSYNC.
2. **`KARA_DRAW` must stay ahead of the beam.** Her blitter runs at 651 T per
   line against the raster's 256, so she only survives on a lead. Starting at
   23,548 T holds to line 172 — past her last line at 159. Starting at 37,356 T
   (erase first, then scroll) means the beam overtakes her at line 137 and she
   flickers from the waist down: exactly 23 lines × 8 pixels = 184 wrong pixels,
   which is what `test_module4.py` measured.
3. **`KARA_ERASE` must stay behind it**, or it wipes her before the beam shows
   her. On a scroll frame the work above already costs 54,772 T and it trails
   naturally; on a light frame the draw alone ends at 31,272 T and it does not.
   The erase is therefore **raster-gated on the IM 1 interrupt count** — the
   only raster clock the CPC offers, since the 6845 exposes no scanline
   register. Ticks measured from the `WAIT_VSYNC` exit:

   | tick | 1 | 2 | 3 | 4 | 5 | 6 |
   |---|---:|---:|---:|---:|---:|---:|
   | T | 532 | 13,844 | 27,152 | 40,464 | 53,776 | 67,088 |

   The first lands after only 532 T, not a full 52-line period. Four ticks is
   40,464 T and still ahead of the beam — the first version of the gate used 4
   and did not work. **Five** clears 47,104 T and leaves 26,096 T for a
   13,856 T erase.

### What did not work, with the numbers

* **§9 remedy 1, "restore from the tilemap instead of saving under", is a
  pessimisation.** Kara's footprint is 24 cells; at the measured `DRAW_CELL`
  cost that is 25,248 T against `SPR_RESTORE`'s 13,856, and the save-under only
  costs ~6,100 T on the draw side. `LDI` moves a byte in 20 T; `DRAW_CELL`
  manages 56. A tilemap repaint cannot beat it.
* **Span-limited blitting (remedy 3) does not pay at 48 lines.** Only 59% of
  Kara's bounding box is inside her occupied span, which looks like a 10,000 T
  saving — but per-line span bookkeeping costs ~130 T against 48 lines, so the
  net is under 4,000 T for a large rise in complexity. It would pay for a
  shorter sprite.
* **Compiled sprites (remedy 4)** would be ~10 KB for four frames against 7,808
  bytes of headroom below `&4000`. They would have to live in a bank.

Remaining lever if more time is needed: **only redraw Kara when she moves** —
but note that while the view scrolls she moves relative to video RAM every
frame, so this only helps a standing player on a still screen.

## 10. Conventions and pitfalls

* Hex is `&` prefixed (RASM/CPC style), not `0x` — which requires `-amper`.
* Labels `SCREAMING_SNAKE`, local labels `.dotted`.
* Prefer `EXX` / shadow registers over push/pop in inner loops; document which shadow
  set a routine clobbers, since the interrupt handler uses them too.
* **Write the clobber list in the header comment of every routine, and check it at
  every call site.** The worst bug in Module 3 was not in the blitter — it was a
  helper that scratched `DE` while the caller was holding the screen address there,
  so the blitter cheerfully composited Kara over her own sprite data. The routine
  tested perfectly in isolation.
* **Buffers outside the loaded image start as whatever BASIC left there.** Anything
  in `&8000-&BFFF` that gets read before it is written — a save-under slot, an
  entity table — has to be cleared at startup or the first frame scatters writes
  across memory. See `BUFFERS_CLEAR`.
* Sprite frames must be **16-byte aligned**: the blitter's inner loop steps the
  sprite pointer with `INC L` and cannot carry into `H`.
* `LD SP,&BFFF` explicitly at startup. An SP that drifts into `&C000-&FFFF` shows up as
  random screen corruption, not as a crash.
* AMSDOS keeps its buffers around `&A700-&BFFF`. That region is only safe once the
  firmware is out of the picture — if disc access is needed mid-game, move the stack and
  the sprite buffers accordingly.
* Test the overscan and hardware scrolling on **CRTC types 0, 1, 2 and 4**; type
  differences bite hardest on R3/R7 timing and on start-address latching.
* Test data and scratch output go in the scratchpad dir, not in the repo.
* `plan.md:Zone.Identifier` is a Windows download artefact; add `*:Zone.Identifier` to
  `.gitignore` when the repo gets one.

## 11. Module order

Build strictly in sequence; each module must assemble **and run in the emulator** before
the next one starts.

1. ~~**Memory architecture + build pipeline**~~ — done: bootstrap/relocator, bank
   switching, `build.sh`, BASIC loader, `.dsk` generation, `tools/test_module1.py`.
2. ~~**Asset exporters**~~ — done: `cpclib.py`, `png2sprite.py`, `png2screen.py`,
   `blender_title.py`, wired into `build.sh`, with round-trip and on-hardware tests.
3. ~~**Sprite blitter + dual-pistol bullet pool**~~ — done: one-pass masked draw
   with save-under, LDI restore, 14-round pool, alternating magazines, reloading,
   HUD, and per-phase raster profiling.
4. ~~**Scrolling engine**~~ — done: CRTC R12/R13 hardware scroll, tile
   rendering out of bank C4, horizontal and both vertical directions,
   per-axis latch ordering, `tools/test_module4.py` with a render-level
   tearing check and a negative control.
5. **Objects, puzzles, NPCs** — inventory, interaction handlers, AABB.
   Starts with scroll-aware sprite addressing (§8.2), which is the one piece
   of Module 4 deliberately left out.
6. **Level FSM + cutscenes** — transitions, raster-interrupt water rise, palette fades.
7. **Audio** — `audio_pipeline.py` (ffmpeg → 3 channels), AY player in the 50 Hz
   interrupt, Channel C SFX priority.

## 12. Corrections to plan.md

Consult this list before implementing from the plan:

1. **Mode 0 bit table (§4.2)** — wrong; pen bits 0↔3 and 1↔2 are swapped. Use §6.3
   above, which was verified on the emulator.
2. **Overscan byte count (§4.3)** — a CRTC character is 2 bytes, not 4. R1=48 yields
   96 bytes/line, not 192. The resulting 192-pixel width and 26,112-byte total are
   correct.
3. **"19,968 T-states" (§6.1)** — 19,968 is the frame length in *microseconds*
   (312 × 64), not a T-state budget. The frame is 79,872 T-states; the intended ~25%
   sprite budget is ≈19,900 T-states.
4. **Aseprite (§5 Module 2)** — not installed and no MCP server for it; use a Python
   PNG encoder instead.
5. **"Overscan title buffer, 26 KB across 2 banks" (§4.1)** — right that it needs two
   buffers, but not because of bank size. It needs two because the CRTC cannot address
   more than 21 character rows in one raster block; the two halves are displayed by
   re-pointing R12/R13 mid-frame. See §6.5.
6. **The 25% sprite budget (§6.1)** — not reachable with a generic masked blitter at
   16×48; 384 bytes at 55 T-states each exceeds it before anything else runs. Measured
   cost and the four ways to claw it back are in §9.
7. **"Vertical roll without tearing (sync with VBLANK / HALT)" (§5 Module 4)** —
   VBLANK sync is necessary but nowhere near sufficient. Because the CRTC row
   stride *is* the displayed width, every step writes into memory that is on
   screen; tear-free scrolling needs `R6 = 24` to create a 64-word off-screen
   margin, a latch order that differs per axis, and a main loop ordered as a
   beam chase. See §8.2 and §9.
8. **RASM's `/` rounds to nearest**, it does not truncate: `&2240/256` is `&22`
   but `&2280/256` is `&23`. Use `>> 8`. `screen.asm` was correct only by luck.
9. **`assert (X & 15)` fails under `-amper`** — `&15` parses as a hex literal.
   Use `AND`. And `ASSERT` is evaluated eagerly in source order, so
   cross-module assertions must sit *after* every `include`.
