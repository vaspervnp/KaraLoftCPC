# CLAUDE.md — Kara Loft and the Illuminati (Amstrad CPC 6128)

Z80 assembly game for the Amstrad CPC 6128. The design document is [plan.md](plan.md)
(written in Greek); this file holds the technical contract that code must satisfy.
**Where this file and plan.md disagree, this file wins** — see §11 for the specific
corrections and why.

## 1. Status

**Modules 1-4 done; Module 5 in progress.** `./build.sh` regenerates the assets,
assembles, and produces `build/kara.dsk`. It boots, relocates, passes its bank
self-test, runs Kara walking and firing over a striped background with full
save-under restore, and then hands over to the scrolling city: a tilemap in bank
C4 moved by the CRTC start address, horizontally and both ways vertically, with
Kara drawn over it from keyboard or joystick input, walking, jumping and
colliding with the tiles, and the camera following her. The loop holds 50 Hz on
every path (§9).

`./tools/run_tests.sh` runs every acceptance suite and **all nine
pass**, including the frame budget: a scrolling frame on Kara's
heaviest animation frame is 78,764 T of 79,872, with the span blitter
at its floor and `DRAW_COLUMN` rewritten from 71 T a byte to 43. The
numbers are in §9.

```
src/main.asm      bootstrap at &4000 + core engine at &0040
src/config.asm    ports and memory map constants
src/bank.asm      bank switching (must stay outside &4000-&7FFF)
src/screen.asm    Mode 0 addressing, block fill, palette, vsync
src/palette.asm   the 16 pens + solid-pen byte table
src/sprite.asm    scroll-aware masked blitter, save-under restore
src/bullets.asm   dual pistols, 14-round pool, reloading
src/spanblit.asm  the span-compressed blitter and its erase script
src/unpack.asm    ZX0 into a bank, for the per-level art
src/vendor/       dzx0_fast, by spke - the ZX0 depacker, vendored
src/tilemap.asm   CRTC hardware scrolling, tile rendering out of bank C4
src/input.asm     keyboard and joystick scan, edge detection
src/collide.asm   tile attributes, box-against-map probes
src/player.asm    walking, jumping, gravity, and the camera
disc/disc.bas     ASCII BASIC loader

tools/cpclib.py            Mode 0 encoding, palette, screen layout - the one
                           place the bit interleaving is written down
tools/png2sprite.py        sprite sheet  -> data+mask binary (the placeholder)
tools/aseprite2spans.py    Aseprite sheet+JSON -> span-compressed bank
tools/spawns.py            projectile spawn points -> build/spawns.inc
tools/pack.py              ZX0 for everything that goes on the disc
tools/build_levels.py      the level art packages -> blobs, both facings
tools/level_banks.py       blobs -> bank images -> one ZX0 stream each
tools/png2screen.py        image         -> overscan.bin / 16K screen
tools/png2tiles.py         16x16 tile sheet -> 128 bytes/tile + .inc
tools/make_placeholder_level.py  the stand-in city tiles and 64x16 map
tools/blender_title.py     the title scene and its CPC render settings
tools/make_placeholder_sprites.py
tools/test_*.py            acceptance suites
tools/run_tests.sh         all of them, in order

assets/sprites/            the art package: the heroine, the projectiles,
                           common/ for the HUD, level<n>_<name>/ for each
                           level's tiles, characters and machines, each
                           with the artist's manifest.json
assets/placeholder/        stand-in tiles for the scrolling demo
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
| `&C4` | 0 | 4 | 2 | 3 | Tiles, tilemap, projectiles, one enemy type, level logic |
| `&C5` | 0 | 5 | 2 | 3 | Kara facing **right** + a second enemy type, right |
| `&C6` | 0 | 6 | 2 | 3 | Kara facing **left** + that enemy type, left |
| `&C7` | 0 | 7 | 2 | 3 | Title buffer; then Kara `run`/`roll`, both facings |

`tools/level_banks.py` does the allocation and writes
`build/levels/banks.inc` with every blob's bank and address. Measured,
with the shared set counted in every level:

| level | unpacked | banks | packed | set pieces |
|---|---:|---:|---:|---:|
| 1 city | 62,048 | 4 | 14,223 | 487 |
| 2 forest | 74,459 | 5 | 17,782 | — |
| 3 cave | 65,507 | 5 | 16,242 | — |
| 4 undersea | 59,226 | 4 | 13,877 | 1,074 |
| 5 desert | 76,553 | 5 | 16,066 | 2,101 |
| 6 station | 63,065 | 4 | 14,647 | 1,255 |

**Five banks, not four.** The window shows bank 1 as well as 4-7, so
there are 81,920 bytes of art storage; level 2 and level 5 need all
five. That puts the "level logic, collision data, entity management"
of §6.1 into `&8000-&BFFF` instead, which has 14 KB free after the
save-under buffers.

Two rules make it fit at all:

* **The set pieces load separately.** The escape car, the shuttle, the
  base door, the escape pod, the siphon and the computer are one fixed
  moment each; together they are 60 KB that never has to be resident
  during play. Level 5 is 55,526 bytes of art and 28,134 of it is the
  finale.
* **The swim set replaces the run/roll set.** She does not run or roll
  under water and she does not swim anywhere else.

**The banks are reloaded from disc at every level transition, and that
is what makes this fit.** The earlier map gave a bank to each PAIR of
levels' tiles, which only works while the tiles are the only large
asset. Kara alone is 36 KB across both facings (§7.1) and the six enemy
types are another 23 KB; one level's tiles are 3 KB. Since only one
level is ever loaded, "levels 1-2 / 3-4 / 5-6" was paying three banks
for something one bank holds at a time.

**Everything on the disc is ZX0-packed** (§7.4) as one stream per bank,
so a level transition reads 14-18 KB rather than 60-77 KB. Unpacking it
costs **0.8-1.05 s** — measured on a 6128, all six levels, byte-exact
(§7.5). The whole game's art packs to 97,754 bytes, which would fit in
RAM; the unpacked working set would not, which is why it is a disc read
and not a one-off load at boot.

`&C7` is the title buffer only while the title is on screen. By the
time the first level runs it is free, which is where the enemy frames
and the dialogue tables go.

Kara's core set is in `&C5` and stays paged in through normal play;
`&C6` is only needed when she runs, rolls or swims. A level that has no
water never pages it.

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
across two banks and assembled into VRAM in two passes — which it can
do freely, because no level is loaded while the title is up.

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

**Kara is 24×64 pixels** — 12 bytes wide × 64 lines — in
`assets/sprites/heroine_cpc_mode0.aseprite`, exported by Aseprite as a
sheet plus a JSON with the frame boxes and the animation tags. The
sheet has 40 frames and **nine of them are deliberately not shipped**:

| tag | drawn | shipped | dropped (1-based, as the artist counts them) |
|---|---:|---:|---|
| `idle` | 4 | 3 | 3 — it is pixel-identical to 4 |
| `walk` | 8 | 5 | 2, 4, 6 |
| `run` | 8 | 5 | 2, 4, 6 |
| `jump` | 6 | 4 | 3, 5 |
| `roll` | 8 | 8 | |
| `shoot_draw` | 2 | 2 | |
| `shoot` | 4 | 4 | |

`build.sh` passes the list to the exporter as `--drop tag=n,n`.
**A dropped frame's hold time is added to the frame before it**, so a
thinned cycle gets coarser and not faster — which matters for the walk,
where the feet have to keep up with the two pixels a frame she travels.
`build/kara_core_frames.json` records which sheet frames actually went
in, and `test_spans.py` reads it rather than re-deriving the list.

and a separate swimming sheet, `heroine_cpc_mode0_swim.aseprite`, of 12
frames at **64×24** — she is horizontal in the water — tagged `swim`
(8) and `swim_shoot` (4).

#### Frames are stored as SPANS, not boxes

A full box would be 12 × 64 = 768 bytes of data and as much mask, so
1,536 bytes a frame and **61,440 for the 40 land frames alone** — four
banks, and the machine has four in total. It would also cost 49,152 T
to composite, which is 62% of a frame before anything else runs.

Measured over the real art, **only about a third of the box is
occupied**, and a fifth of the lines are entirely empty. So the frame
stores the bytes that are actually drawn and nothing else:

| | full box | span | measured |
|---|---:|---:|---|
| 31 shipped land frames | 47,616 B | **18,065 B** | 34% occupancy |
| 12 swim frames | 18,432 B | **6,464 B** | 31% |
| composite, heaviest frame | 49,152 T | **23,688 T** | 329 span bytes |

`tools/aseprite2spans.py` does it, reading the Aseprite JSON for the
frame boxes and the tags. One frame is a header and then **groups of
lines that share a span**:

```
db  y0        first line of the box with any pixels
db  lines     lines stored; empty ones off the top and bottom dropped
then groups, until nlines = 0:
    db  nlines    consecutive lines with this same span
    db  count     bytes in the span, 0 for blank lines
    dw  dskip     this group's skip minus the last one's, signed and
                  sign-extended so ADD/ADC takes it without branching
    db  mask,data ... nlines x count times, interleaved
db  0         end of frame
```

**Lines are grouped because the per-line bookkeeping, not the
composite, is what the blitter spends its time on.** The first version
walked line by line and cost 43,136 T on the heaviest frame — 131 T for
each of its 329 span bytes, where the composite itself is 72. At 5.7
bytes a line, reading `(skip, count)`, computing the entry into the
unrolled run and testing for the seam dominate. Consecutive lines share
a span 3.5 times in 4, so saying all of that once per group took the
same frame to 39,496 T.

and a blob is a table of `dw` frame offsets — relative, so the loader
can drop it at whatever address the bank window is — followed by the
frames. Interior empty lines stay as `count = 0`: the gap between her
arm and her boot is one byte, and a second index to skip it would cost
more than it saves.

**The sheet is split at export time**, because 24×64 does not fit one
bank whole. `--tags` picks which animations go into a blob and numbers
its frames from zero, so each bank is self-contained:

| blob | tags | bytes | spare in a 16 KB bank |
|---|---|---:|---:|
| `kara_core.bin` / `_l` | idle, walk, jump, shoot_draw, shoot | 10,910 | 5,474 |
| `kara_extra.bin` / `_l` | run, roll | 7,155 | 2,074 for the pair |
| `kara_swim.bin` / `_l` | swim, swim_shoot | 6,464 | 3,456 for the pair |

**That makes the 24×64 sprite CHEAPER to draw than the 16×48 one it
replaces** (30,072 T), which is the opposite of what §9 concluded when
it rejected span blitting — and the reason is in that entry: "It would
pay for a shorter sprite." It pays for a *sparser* one. At 16×48 the
placeholder filled 59% of its box; this art fills 34%.

#### BOTH facings are stored — mirroring at draw time costs a register it has not got

The earlier plan here was to store one facing and mirror through a
256-byte table at ~8 T a byte, ~2,000 T a frame. **That was wrong by a
factor of four, and the reason is register pressure, not arithmetic.**
Mirroring a Mode 0 byte is the fixed permutation `7↔6, 5↔4, 3↔2, 1↔0`,
which is one lookup — but the lookup needs an index register and the
inner loop has none: `HL` must hold the mask/data because only `(HL)`
works with `AND`/`OR`, `DE` is the screen and `BC` the save. Every way
round it was costed:

| | T a byte |
|---|---:|
| unmirrored | **72** |
| `IX` = frame, `HL` = table, `INC IX` twice a byte | 120 |
| `IX` = frame with fixed displacements, reloaded per line | 96 |
| self-modified absolute lookup, `LD (.p+1),A : LD A,(TBL)` | 136 |
| arithmetic swap, no table | needs two temporaries |

At 329 span bytes the cheapest of those is **+7,896 T a frame**, which
the frame has not got (§9). Mirroring at export time costs a bank
instead — and after the nine dropped frames there is a bank:

| | one facing | both |
|---|---:|---:|
| `kara_core` idle/walk/jump/shoot | 10,910 B | 21,820 B — two banks |
| `kara_extra` run/roll | 7,155 B | 14,310 B — one bank |
| `kara_swim` | 6,464 B | 12,928 B — one bank |

`--mirror` emits the left-facing blob: each line's span moves to
`BOX_W - skip - count`, its bytes reverse, and each byte's two pixels
swap. `test_spans.py` checks those blobs against the art flipped, not
merely against themselves.

#### Mask convention

Mask bits **set where the background shows through**, clear where the
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

**Pens 1 and 5 were given to the art.** They were Bright Blue and Bright
Magenta, and nothing — tiles, HUD or sprite — used either. They are now
**Pastel Cyan (hw 27)** and **Pink (hw 7)**:

* `(255,128,128)` is her skin: 4,574 pixels, a quarter of her opaque
  area, spread over the whole figure. Without Pink it quantised onto
  pen 13 Orange, 116 units away and *the same colour as her muzzle
  flash* — the two shared a pen.
* `(128,255,255)` is the goggle glint, two pixels a frame. Pastel Cyan
  also doubles as a better water and glass highlight for level 4 than
  the near-neon `(12,2,244)` it replaced.

With the swap all 11 art colours land on their own pen, worst distance
**27.8**; before it, worst 115.7 with a collision. **Pen 8 Green was
deliberately kept** — level 2 is a forest and it is the only mid green
in the set. The two spent pens were the only genuinely free ones, so
the next new colour costs a used one.

#### One art package, one directory per level

The art arrives as `assets/sprites/level<n>_<name>/` with a
`manifest.json` listing that level's sheets and what each is for, plus
a shared set at the top (the heroine, her actions, the projectiles) and
in `common/` (the HUD). **622 frames across 55 sheets.**

`tools/build_levels.py` walks all of it: tiles out raw, everything else
span-compressed, both facings for anything that turns to face her.
Nothing is hand-listed except that last judgement, which the manifests
do not record and which is written down in `MIRRORED` — a pickup, a
tile, a wall-mounted machine or a thing bolted to the scenery gets one
facing, and each of those saved is 2-20 KB of bank.

**The seven named characters replace the six generic enemies.**
`enemies_cpc_mode0.aseprite` (merc, hunter, commando, guard, raider,
heavy) was the first pass; the art now has `city_agent`,
`forest_sniper`, `cave_excavator`, `desert_mercenary`, `desert_nomad`,
`desert_informant` and `station_cyber`, one or more per level, in that
level's own directory. `common/preview_chars_lineup.png` is the set.
The generic sheet and `enemies_swim` are no longer exported.

**A blob has to fit one bank whole**, because its frame table is at its
start and its offsets are relative to it. Only the set pieces come
near: the shuttle is 20,162 bytes on its own, so `build_levels.py`
splits anything over 12 KB by tag and the engine refers to the smaller
blob.

**Where a shot leaves is art, not code.**
`assets/sprites/projectile_spawn_points.json` marks, per firing frame,
the pixel the projectile's left edge sits on, and `tools/spawns.py`
turns it into `build/spawns.inc`:

```
KCORE_SPAWNS:           ; 24x64
                db 14, 18, 17, PROJ_BULLET      ; shoot
                db 16, 18, 11, PROJ_BULLET      ; shoot
                db SPAWN_END
```

The frame numbers are the **blob's**, not the sheet's — `--drop` and
`--tags` renumber, so the tool maps them through the exporter's
`*_frames.json` sidecar. Left-facing sprites mirror the x to
`frame_width - 1 - x`, which is one subtraction against doubling the
table.

### 7.2 Aseprite

plan.md assumed an Aseprite MCP server and §3 records that there is no
Aseprite on this machine. That is still true and no longer matters: the
art arrives as an **exported sheet plus its JSON**, which is the same
thing the MCP server would have produced. `png2sprite.py` reads the
JSON for the frame boxes and the tags rather than assuming a grid, so
re-exporting with different frame counts needs no code change.

### 7.4 Compression — ZX0, and it is not close

Every blob that goes on the disc is ZX0-packed by `tools/pack.py`
through RASM's own cruncher, and unpacked into its bank at the level
transition by `dzx0_fast` from `/home/vasilhs/rasm/decrunch`.

Nine crunchers were measured on `kara_core.bin` (10,910 bytes), each
one **run on a 6128 and compared byte for byte** with the original:

| algorithm | packed | ratio | depacker | T a byte | frames |
|---|---:|---:|---:|---:|---:|
| **ZX0, `dzx0_fast`** | **2,129** | **19.5%** | 189 B | **49.0** | 6.7 |
| ZX0, `dzx0_standard` | 2,129 | 19.5% | 70 B | 62.4 | 8.5 |
| Exomizer | 2,101 | 19.3% | 332 B | 153.7 | 21.0 |
| aPLib, fast | 2,153 | 19.7% | 238 B | 64.9 | 8.9 |
| ZX7 turbo | 2,284 | 20.9% | 90 B | 67.4 | 9.2 |
| LZ49 | 4,261 | 39.1% | 108 B | 53.2 | 7.3 |
| LZ48 | 4,583 | 42.0% | 72 B | 49.6 | 6.8 |

Exomizer packs 28 bytes tighter for three times the depack time and 143
more bytes of depacker; LZ48 is as fast and packs half as well. **ZX0
wins on both axes at once**, which is unusual and is why there is no
trade-off to argue about. Use `dzx0_standard` instead only if 119 bytes
of core image ever matter more than two frames of load time.

The whole asset set is **140,602 bytes raw, 40,177 packed — 28.6%**.
Sprite data packs hardest (17-29%) because the masks are nearly all
`&00` or `&FF` and adjacent frames share most of their bytes; the
dithered title screen packs worst (59%) because dithering is noise.

**This buys disc and load time, not frame time.** The blitter
composites from uncompressed bytes in a bank; it does not move the
budget in §9 by one T-state. `test_spans.py` depacks all 126 blobs on
the emulator and compares them, so a cruncher/depacker mismatch cannot
ship.

### 7.5 Loading a level

A level is four or five ZX0 streams, **one per bank**: the blobs laid
out at fixed addresses inside a 16 KB image, the whole image packed as
a single stream. That makes the loader three steps per bank — read the
file into the staging buffer, page the bank in, `dzx0_fast` — with no
directory to walk and no addresses to fix up. It also packs better than
per-blob streams, because ZX0 sees the repeats across blobs (two
facings of a character share most of their bytes) and the unused tail
of a bank is zeros.

```
tools/build_levels.py   manifests -> one blob per sheet per facing
tools/level_banks.py    blobs -> bank images -> one .zx0 each
                        ... and build/levels/banks.inc, which says
                        which bank and address every blob ended up at
src/unpack.asm          UNPACK_BANK: A = config, HL = stream -> &4000
tools/test_levels.py    every bank of all six levels, byte-exact on a
                        6128, and banks.inc checked against the images
```

`LEVEL_STAGE` is `&8000`. **The staging buffer cannot be in the window**
— the unpacker reads from it and writes to `&4000-&7FFF` — so it sits
in base RAM on top of the save-under buffers, which are scratch while a
level is changing. The biggest stream measured is 4,695 bytes against
8 KB of room.

**What is still missing is the disc read.** The firmware went out with
the ROMs at boot (§4), so a mid-game load needs either the lower ROM
and the firmware's cassette entries brought back around the call, or a
765 FDC driver. `&A700-&BFFF` has to stay clear of AMSDOS's buffers
either way (§10).

Allocation is best-fit with a deterministic shuffle as a backstop.
First-fit-decreasing is the usual advice and it fails here: level 5 is
76,553 bytes into 81,920 and FFD strands 5,364 in fragments too small
for the 5,764-byte blob left over.

### 7.6 Blender

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
| Horizontal | request → paint head → *next frame* → latch → paint tail | The incoming column is not hidden: under the old start address those cells are the left edge of each row below. But the beam is *finished* with them once it has swept that row, so rows 0-17 go down **behind** the beam in the frame before the step (`H_HEAD`, from interrupt tick 4), the latch happens in the next vblank (`H_COMMIT`), and rows 18-23 go down ahead of the beam after it (`H_TAIL`). |
| Vertical down | state → apply → paint | New bottom row lands at offset 960 — hidden. Painted long before the raster reaches line 184. |
| Vertical up | state → paint → apply | New top row lands at offset 984 — hidden — but the raster reaches line 0 only 18,432 T into the frame, far too early for a 51,600 T row redraw. Painting first and moving the picture one frame later is invisible and always correct. |

Splitting the column across two frames is what buys the whole top border for
`KARA_DRAW`. Painting all 24 rows first left her starting 23,500 T in and the
beam overtook her; painting her first left the column's top rows under the
beam. Either way `DRAW_COLUMN` must run **top to bottom**.

**The walk speed and the scroll step are the same number or the picture
doubles.** The CRTC scrolls a whole character — 2 bytes — and Kara walks 1 byte
a frame, so inside the camera's push zone the camera can only fire every other
frame. Let her keep walking a byte a frame there and the column the blitter
draws her at goes 54, 55, 54, 55 at 25 Hz: every frame is drawn and erased
correctly, every RAM check passes, and on a real monitor there are two Karas a
character apart for as long as the screen moves. `PLAYER_X` therefore moves her
`P_PUSH` = 2 bytes on the camera's frame and nothing on the frame between, so
her screen column never changes while the world goes by. Mid-screen she still
walks 1 byte at 50 Hz. `test_module4.py` asserts the property directly: on
every frame where the view moved, `KARA_X` must not have.

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

**Sprites over a scrolled screen** — done, and it was the first task of Module
5. The blitter takes its address from the same masked word index the tile
engine uses (`SCR_ADDR`), recomputed at each character-row boundary, with a
slow lane for the lines whose 8 bytes straddle the 1024-word seam. It walks the
sprite in groups that follow the SCREEN's character rows rather than the
sprite's own 8-line blocks, because everything that varies per line — v, the
seam test, the carry into the next row — is decided per row.

**A sprite that leaves the display must be culled, not drawn.** `KARA_Y` is an
unsigned screen line and the camera can carry her off either edge during a
vertical scroll, which wraps it to 192-255. Drawn there, her 48 lines run past
the 24 displayed rows, through the 64-word margin, and fold back over the top
of the picture — and where the fold lands two of her own lines on one address,
the save-under captures the first line's *output* as the second line's
background and the erase leaves her debris behind. Measured at 32-56 bytes of
video RAM left wrong per frame, accumulating. `KARA_DRAW` now refuses.

**Still missing: clipping.** A sprite only PARTLY off the bottom still writes
into the margin and, past character row 23, folds onto the top of the picture.
The camera keeps Kara clear of both edges in normal play, so this only shows
under the vertical driver in `test_module4.py`, which pokes `V_REQUEST` with no
player behind it — which is why that suite still reports a residue. Levels 3
and 4 will not be so kind; Module 6 needs a real clip.

Tiles are 16×16 pixels = 8 bytes × 16 lines. Tilemaps live in banked RAM.

### 8.3 The level format, and the editor that writes it

[docs/editor.md](docs/editor.md) specifies a web editor (C# / ASP.NET
Core) that imports the Aseprite package, lets a designer paint levels
over it and exports `level_<n>.lvl` for this engine. Its §9.2 binary is
the contract between the two, and the engine reads it:

```
0  2  magic "LV"          9  1  tileset id
2  1  format version     10  1  entity count
3  1  level id           11  1  link count
4  1  flags: 0-1 scroll, 12  1  region count
      2 underwater,      13  8  u16 offsets: map, entities, links, regions
      3 map is RLE
5  2  width in tiles      map      1 byte a tile, row-major
7  2  height in tiles     entity   8 bytes: kind, x u16, y u16, flags, p0, p1
                          link     4 bytes: kind, source, target, param
                          region   7 bytes: kind, x u16, y u16, w, h
```

Tile flags travel separately in `tileflags_<level>.bin`, one byte a
tile: `Solid 1, Platform 2, Hazard 4, Ladder 8, Water 16, Quicksand 32,
Deadly 64`.

#### Two corrections to editor.md, both forced by the CRTC

**1. Tiles are 8×16, which this engine does not do yet.** The current
tilemap is 16×16 (8 bytes × 16 lines) and the map is 64×16. At 8×16 a
tile is **4 bytes × 16 lines**, so it spans 2 CRTC character columns
and 2 character rows, and a map of the same world width has twice the
columns. `tilemap.asm` and `collide.asm` both assume the old size.

**2. The play area is 20×11 tiles and the HUD is 16 lines, not 24.**
editor.md §2.1 asks for 176 lines of play plus a 24-line HUD = 200
lines = **R6 = 25**, and R6 = 25 displays 1,000 of the 1,024 words the
CRTC can address. That leaves 24 words off-screen where a character row
is 40, which is exactly the margin §8.2 calls "the single most
important decision in the module" — vertical scrolling tears without
it. So:

| | lines | char rows | words |
|---|---:|---:|---:|
| play area, 20×11 tiles | 176 | 22 | 880 |
| HUD | **16** | 2 | 80 |
| displayed, R6 = 24 | 192 | 24 | 960 |
| off-screen margin | | | **64** |

A 16-line HUD is what the art wants anyway: `hud_icons` is 8×16 and the
digits and bars are 4×8, so they sit two to a row. The picture is 8
scanlines shorter than editor.md assumes and those 8 lines are border.

### 8.4 Kara's actions

The art decides the state machine, so it is written down here next to
the frame counts in §7.1 rather than inferred at each call site.

| State | Frames | Entered by | Leaves when |
|---|---|---|---|
| `IDLE` | `idle` 4 | no direction held, on the ground | a direction, a jump, a roll or the gun |
| `WALK` | `walk` 8 | left/right on the ground | the key goes, or SHIFT is added |
| `RUN` | `run` 8 | **SHIFT + left/right** | SHIFT or the direction goes |
| `JUMP` | `jump` 6 | UP pressed while grounded | she lands |
| `ROLL` | `roll` 8 | **Z**, on the ground | the 8 frames are done |
| `AIM` | `shoot_draw` 2 then hold | **SPACE held** | SPACE released |
| `FIRE` | `shoot` 4 | **SPACE released** from `AIM` | the 4 frames are done |
| `SWIM` | `swim` 8 | level 4, in water | out of the water |
| `SWIM_FIRE` | `swim_shoot` 4 | SPACE released while swimming | the 4 frames are done |

**The gun is draw-hold-release, not a trigger.** SPACE going down plays
`shoot_draw` and then holds its last frame; SPACE coming up plays
`shoot` and fires on its first frame. That is what the two-frame
`shoot_draw` tag is for, and its `draw_offset_x=4` in the JSON is the
muzzle's X inside the box — the bullet spawns there, not at the edge of
the sprite.

A roll is committed: it runs its 8 frames whatever the input does, which
is what makes it a dodge. It cannot start in the air.

**The input byte is now full**, and the two new controls cost the two
spare bits. Bits 0-3 have to stay in the joystick's own order — that is
what lets row 9 fold in with no shifting (`input.asm`) — so:

```
0 UP  1 DOWN  2 LEFT  3 RIGHT  4 FIRE(SPACE)  5 ROLL(Z)  6 PAUSE(ESC)  7 RUN(SHIFT)
```

Z was `IN_ACTION`, a second interact key alongside RETURN; it is the
roll now, and RETURN goes with it. Interact is `UP` alone, which is what
plan.md §5.2 asked for in the first place ("αν πατηθεί UP"). A ninth
control needs a second byte, not a re-shuffle.

`RUN` moves her 2 bytes a frame, which is exactly the CRTC's scroll
step, so inside the camera's push zone a run scrolls every frame and a
walk every other one — see §8.2.

### 8.5 Dual pistols

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

### 8.6 Game state

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
| `DRAW_COLUMN` (24 rows) | 29,620 | **16,052** | a tile an iteration, stepped address, map in `BC`, column-major tiles |
| `DRAW_ROW` (40 cells) | 49,208 | **31,008** | same, split across two frames, column-major tiles |
| `KARA_DRAW` | 30,948 | **30,072** | scroll-aware, and grouped by character row |
| `KARA_ERASE` | 13,584 | **11,592** | a whole row unrolled: 8 `LDI` + 24 T a line |
| `BUL_DRAW` / `BUL_ERASE` | | 1,876 / 1,192 | |
| `INPUT_SCAN` / `PLAYER_UPDATE` / `CAMERA_DECIDE` | | 804 / 704 / 108 | |

`H_HEAD` is 18 of those rows (13,872 T) and `H_TAIL` the other 6
(4,920 T — the `.skip` loop is gone, replaced by arithmetic).
A seam-straddling character row costs `KARA_DRAW` 33,248 T and `KARA_ERASE`
14,172, worst of 525 positions swept across scroll, X, Y and frame.

### The frame, in situ

**Do not measure the frame as the time between `FRAME_COUNT` increments.** The
counter is bumped at the end of the loop body, so the interval between bumps is
the work length, and the work length legitimately differs between a scrolling
frame and a still one. That makes a locked 50 Hz read as 21,372 µs alternating
with 18,568 µs and invites a fix for a bug that is not there. Count **loop
iterations against interrupt ticks** instead — the gate array delivers exactly
6 per 50 Hz frame, so 200 iterations per 1,200 ticks is a hard lock:

| Loop | iterations | hardware frames | |
|---|---:|---:|---|
| standing still | 200 | 200.00 | **locked** |
| walking right, scrolling | 200 | 200.00 | **locked** |
| walking left, scrolling | 200 | 200.17 | **locked** |
| jumping while scrolling | 200 | 200.00 | **locked** |

A scrolling frame is ~71,000 T of the 79,872 available, and the three biggest
pieces are `KARA_DRAW` 30,072, the column 27,952 across its two halves, and
`KARA_ERASE` 11,592.

### Raster constraints, all of them load-bearing

The order of work in the main loop is not a data-dependency order, it is a
**beam chase**, and each of these was found by a test rather than by reasoning.
Two models of when the beam reaches display line L, both measured:

| | border above the picture | line L displayed at |
|---|---:|---|
| headless emulator | 60 scanlines | 15,376 + 256 L |
| a 6845 left as the firmware programs it | 72 scanlines | 18,432 + 256 L |

Time anything that must be **ahead** of the beam against the early figure and
anything that must be **behind** it against the late one.

1. **`KARA_DRAW` goes first**, in the top border, at ~560 T a line against the
   raster's 256. The whole border is her lead and she is safe for any
   `KARA_Y >= 13`. Starting her after the column instead left her at 23,548 T
   and the beam overtook her from the waist down.
2. **The incoming column is split across two frames** so it never competes with
   her for the border. See §8.2.
3. **`KARA_ERASE` must stay behind the beam**, and still finish before the next
   VSYNC. The IM 1 interrupt is the only raster clock the CPC offers — the 6845
   exposes no scanline register — so the gate is a **whole tick** picked from
   her Y: tick 4 up to Y=38, tick 5 up to 90, tick 6 up to 142. Ticks measured
   from the `WAIT_VSYNC` exit:

   | tick | 1 | 2 | 3 | 4 | 5 | 6 |
   |---|---:|---:|---:|---:|---:|---:|
   | T | 532 | 13,844 | 27,152 | 40,468 | 53,780 | 67,088 |

   The first lands after only 532 T, not a full 52-line period.

   **A finer gate than one tick does not work, and the failure is instructive.**
   A delay loop after the tick can only measure from the moment it is entered,
   so a second one in the same frame adds its whole wait on top of whatever ran
   between them. Splitting the erase into halves gated that way put the lower
   half 13,600 T late and dropped a frame on 12 scrolling frames out of 58 —
   visible on hardware as the sprite flickering while the screen moves.
4. **`FRAME_TICK0` is stamped by the interrupt handler, not by the main loop.**
   The handler reads PPI port B and, on the tick that lands inside the VSYNC
   pulse, records the count. `WAIT_VSYNC` tests the level rather than an edge,
   so a frame whose work overran into the 16-scanline pulse starts late on the
   *same* pulse — and its raster gates still fire at the right absolute time
   because the anchor came from the interrupt. Stamping at the top of the loop
   instead shifts every gate in that frame by a whole tick.

### The span blitter, measured — and the frame that does not close

`src/spanblit.asm` replaces the 16×48 full-box blitter. It is correct
(`tools/test_spanblit.py` composites 20 placements against an
independent v-model, including spans that straddle the 2 KB fold, and
checks the erase restores every byte) and it is **at its floor**: the
composite is nine instructions, all 8 T after the gate array's padding,
so 72 T a byte is not negotiable.

| | span bytes | draw | erase | both |
|---|---:|---:|---:|---:|
| lightest frame (a `jump`) | 203 | 28,192 | 9,612 | 37,804 |
| mean of 18 `kara_core` frames | | | | 46,313 |
| heaviest (a `shoot`) | 329 | 39,496 | 13,500 | **52,996** |
| the 16×48 pair it replaces | 384 | 30,072 | 11,592 | 41,664 |

It moves FEWER bytes than the old sprite and costs more, because 64
lines of 5.7 bytes carry far more per-line bookkeeping than 48 lines of
8. Grouping equal spans (§7.1) took the heaviest frame from 43,136 to
39,496; the remaining per-line cost is 168 T — a 64 T script header, a
32 T address step, a 24 T seam test, a 24 T loop and a 12 T dispatch —
and everything left on the table is worth about 2,000 T in total.

That did not close a scrolling frame until `DRAW_COLUMN` was rewritten,
and **the lever was the column, not the blitter**:

| | before | after |
|---|---:|---:|
| the incoming column, `H_HEAD` + `H_TAIL` | 27,244 | **16,504** |
| input, player, camera, bullets, logic | 7,080 | 7,080 |
| + Kara, lightest | 72,128 | 61,388 |
| + Kara, heaviest | 87,320 — over by 7,448 | **76,580 — fits, 3,292 spare** |

`DRAW_COLUMN` was 71 T a byte to copy 384 bytes out of the tile bank,
against 32 for a plain `LD A,(HL)` / `LD (DE),A` pair. Its inner raster
was 76 T for 2 bytes and still is; all 8,452 T came out of the other
two thirds:

* **Two character rows an iteration, because two character rows are one
  tile.** The map is read once for the pair and `HL` walks straight
  from the tile's line 7 into its line 8, so the lower half needs no
  fetch, no parity test and no reload — 68 T a row gone.
* **The screen address steps instead of being recomputed.** Eight
  rasters of `+&0800` leave `D` exactly where the next row wants to
  start: `D` is `&C0 + (v >> 8)` with `v >> 8` in 0-7, so eight times
  `+8` is `+64`, which carries out of the byte and leaves `DE = v` with
  the page bits gone. Adding 80 and masking to 11 bits is the whole
  step, and the word index in `BC` is not needed at all.
* **The map pointer lives in `BC`** and is read with `LD A,(BC)`, so
  the fetch and the row advance are inline instead of three `CALL`s
  through memory.
* **`COL_FIRST` is arithmetic, not a loop.** Skipping to row 18 for
  `H_TAIL` was 18 iterations of pointer walking, ~3,800 T; it is now
  one multiply in the setup.

**And then the tiles were stored column-major**, which took another
2,296 T off the column and 6,116 off `DRAW_ROW`. A tile is now, for
each of its character columns, that column's 16 lines' two bytes
consecutively:

```
offset = char_column * 32 + line * 2 + byte
```

Every blitter here paints a character column at a time, two bytes a
raster for eight rasters, so in row-major order the source had to step
8 bytes a line — `LD A,L / ADD A,7 / LD L,A`. Column-major it is one
`INC L`: **64 T a raster instead of 76**, and it costs nothing in space
because it is the same 128 bytes in a different order. That all three
blitters wanted the same reordering is the sign it is the right one.

| | row-major | column-major |
|---|---:|---:|
| `DRAW_COLUMN`, 24 rows | 18,348 | **16,052** |
| `H_HEAD` + `H_TAIL` | 18,792 | **16,504** |
| `DRAW_ROW`, 40 cells | 37,124 | **31,008** |

### What did not work, with the numbers

* **§9 remedy 1, "restore from the tilemap instead of saving under", is a
  pessimisation.** Kara's footprint is 24 cells; at the measured `DRAW_CELL`
  cost that is 25,248 T against `SPR_RESTORE`'s 13,856, and the save-under only
  costs ~6,100 T on the draw side. `LDI` moves a byte in 20 T; `DRAW_CELL`
  manages 56. A tilemap repaint cannot beat it.
* **Span-limited blitting (remedy 3) pays on data size and NOT on
  time, which is the opposite of what both earlier entries here said.**
  The placeholder filled 59% of its 16×48 box; the drawn art fills 34%
  of a 24×64 one. That takes the 40 land frames from 61,440 bytes to
  18,065 — the difference between four banks and one — and it takes the
  composite from 49,152 T to 23,688. But "~18,500 T a frame" was a
  composite-only figure with the per-line bookkeeping left out, and the
  bookkeeping is 40% of the real cost. Measured: 52,996 T for draw plus
  erase against the old 41,664. **The remedy is decided by sparseness
  for SIZE and by bytes-per-line for TIME, and those are different
  questions.**
* **Mirroring at draw time costs a register the inner loop has not
  got** — 96-136 T a byte against 72, or ~7,900 T a frame, not the
  "~8 T a byte" §7.1 first claimed. Both facings are stored instead.
  See §7.1.
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
   In progress. Done: scroll-aware sprite addressing and clipping (§8.2,
   §7.1), input, tile collision, the player's physics, the camera.
   Still to do, in this order:
   1. ~~the exporter~~ — done: `aseprite2spans.py`, one blob per bank
      and per facing, with `test_spans.py` compositing every frame of
      all 26 blobs back over a random background through the blitter's
      own `(SCREEN AND MASK) OR DATA`. Five deliberate corruptions of
      the format each fail it;
   2. ~~the span blitter~~ — done: `src/spanblit.asm`, correct and
      measured (§9), with `tools/test_spanblit.py`. **It is not yet
      wired into the game**: `KARA_DRAW` still runs the 16×48 path,
      because switching over needs the bank loader below;
   3. ~~the column~~ — done: `DRAW_COLUMN` 23,560 -> 18,348 T and the
      head/tail pair 27,244 -> 18,792, which is what closes the frame
      (§9), and then column-major tiles took it to 16,052 and
      `DRAW_ROW` to 31,008;
   4. the level loader — **half done**: `src/unpack.asm` unpacks a
      packed bank image into its bank and `tools/test_levels.py` proves
      every bank of all six levels comes back byte-exact on a 6128
      (§7.5). What is missing is the disc read that gets the stream
      into the staging buffer, because the firmware went out with the
      ROMs at boot (§4). Then switch `KARA_DRAW`/`KARA_ERASE` to
      `SPAN_DRAW`/`SPAN_ERASE` and retire `png2sprite.py`;
   5. the action state machine and its controls (§8.4);
   6. the entity table and the five interaction handlers, with the AABB;
   7. the enemies: the seven named characters and the level machines
      (§7.1), their fire using the generated spawn points in
      `build/levels/spawns.inc`;
   8. bullet-against-tile collision (`src/bullets.asm:130`) and the game
      state of §8.5;
   9. `tools/test_module5.py`.
6. **The level format, engine side** — 8×16 tiles and a 20×11 play
   area (§8.3), which is a rewrite of `tilemap.asm`'s addressing and of
   `collide.asm`'s probes, then a reader for `level_<n>.lvl` and
   `tileflags_<level>.bin`, then one hand-built level played end to
   end. `tools/make_level.py` writes the same bytes the editor will, so
   the format gets a reference implementation and a golden file before
   anything else is built against it.
7. **The level editor** — [docs/editor.md](docs/editor.md), a C# /
   ASP.NET Core MVC web application. **It comes here and not earlier,
   and the reason is the golden file.** The editor's whole output is
   `level_<n>.lvl`; if it is written before the engine reads that
   format, the first thing that tests the format is a web app, and a
   disagreement then costs a change on both sides. Built after step 6
   it has something to be correct against: a level the engine already
   plays, byte for byte, on real hardware. Its own phases are in
   editor.md §15; phases 1-3 (import, painting, binary export) are what
   this project needs, phase 4 is not.

   Two things to settle before it starts, both of which are engine
   decisions and not editor decisions: the tile flag byte (§8.3) and
   the entity `param0`/`param1` meanings per entity kind, which
   editor.md's Appendix A lists as free text.
8. **Level FSM + cutscenes** — transitions, raster-interrupt water rise, palette fades.
9. **Audio** — `audio_pipeline.py` (ffmpeg → 3 channels), AY player in the 50 Hz
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
