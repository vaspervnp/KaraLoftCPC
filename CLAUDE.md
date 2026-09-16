# CLAUDE.md — Kara Loft and the Illuminati (Amstrad CPC 6128)

Z80 assembly game for the Amstrad CPC 6128. The design document is [plan.md](plan.md)
(written in Greek); this file holds the technical contract that code must satisfy.
**Where this file and plan.md disagree, this file wins** — see §11 for the specific
corrections and why.

## 1. Status

**Modules 1-4 done; Module 5 in progress, and the playfield is the
drawn art.** Tiles are 8x16 (§8.3) and come off the disc with the rest
of the level. `./build.sh` regenerates the assets,
assembles, and produces `build/kara.dsk`. It boots, relocates, passes its bank
self-test, runs Kara walking and firing over a striped background with full
save-under restore, and then hands over to the scrolling city: a tilemap in bank
C4 moved by the CRTC start address, horizontally and both ways vertically, with
Kara drawn over it from keyboard or joystick input, walking, jumping and
colliding with the tiles, and the camera following her. The loop holds 50 Hz on
every path (§9).

**`RUN"DISC` starts on the rooftop.** There is no longer an
introduction: the core boots, self-tests its banks and goes straight to
the city. The Module 1-3 acceptance screen — colour bars, the bank
verdict, the stripes and the 16x48 placeholder blitter — is kept as a
DEVELOPMENT screen at `INTRO_SCREEN`, which `tools/test_module3.py` and
`tools/test_module1.py` jump into; nothing else reaches it. It puts the
CRTC, the start address, her position, the bullet pool and the map back
the way it needs them, because the level it is entered from has moved
all five.

The scrolling demo loads level
1 off the disc at start-up, scrolls the drawn 8x16 city tiles, draws
the 24x64 drawn heroine out of her span blobs through the action state
machine of §8.4, and carries the level's entity table: her key, her
ammo, her medkit and her coin are on the roof and go into the
inventory when she walks into them (§8.6). Drones patrol the skyline,
shoot at her when she is in front of them, take damage from her
pistols and die (§8.7).

**And there is a way down.** Ladders run down the face of the building
from the roof's own row, and the street is 128 pixels below the roof —
far enough that the 192-line display cannot show both. So reaching the
pavement IS the vertical scroll, driven by the player rather than by a
test poking `V_REQUEST`, and it is what §8.2 built the axis for. She
turns to the ladder before she climbs it and turns off it again at the
bottom, because the climb is drawn from BEHIND and everything either
side of it is side on. See §8.8.

**She can also fall and she can die.** `drop` is a fall she did not
choose — walking off a roof edge, or letting go of a ladder — as
against the `jump` arc she asked for; `die` plays once and then holds
its last cel, and pre-empts everything including the committed states.
Nothing puts her back on her feet yet: there is no respawn and no game
over, and `ACT_UPDATE` chooses `die` from `PLAYER_HP == 0` and will
stop the moment something restores it. See §8.4.

`./tools/run_tests.sh` runs every acceptance suite and **all sixteen
pass**, including the frame budget: a scrolling frame on Kara's
heaviest animation frame is 79,712 T of 79,872, with the span blitter
at its floor and `DRAW_COLUMN` rewritten from 71 T a byte to 43. The
incoming ROW is painted in four pieces rather than two, because the
action sheet's cels are heavier than the gun's and a half row no longer
fits beside one. The numbers are in §9.

```
src/main.asm      bootstrap at &4000 + core engine at &0040
src/config.asm    ports and memory map constants
src/bank.asm      bank switching (must stay outside &4000-&7FFF)
src/screen.asm    Mode 0 addressing, block fill, palette, vsync
src/palette.asm   the 16 pens + solid-pen byte table
src/sprite.asm    scroll-aware masked blitter, save-under restore
src/bullets.asm   dual pistols, 14-round pool, reloading
src/spanblit.asm  the span-compressed blitter and its erase script
src/unpack.asm    ZX0 into a bank, and LEVEL_LOAD
src/disc.asm      the uPD765 driver - raw sectors, no firmware.
                  READ docs/AmstradDskReadHowTo.md BEFORE TOUCHING IT
src/vendor/       dzx0_fast, by spke - the ZX0 depacker, vendored
src/tilemap.asm   CRTC hardware scrolling, tile rendering out of bank C4
src/input.asm     keyboard and joystick scan, edge detection
src/collide.asm   tile attributes, box probes, and the ladder's one-column
                  probe
src/player.asm    walking, jumping, gravity, the ladder, and both cameras
src/kara.asm      the heroine: bank, frame, clip, then SPAN_DRAW
src/action.asm    her action state machine and the cel timer (8.4)
src/entity.asm    the entity table, the AABB, the five interaction
                  handlers, and the pickup bake (8.6)
src/enemy.asm     the level's characters: patrol, sight, fire, damage,
                  and the persistent sprite that pays for them (8.7)
disc/disc.bas     ASCII BASIC loader

tools/cpclib.py            Mode 0 encoding, palette, screen layout - the one
                           place the bit interleaving is written down
tools/png2sprite.py        sprite sheet  -> data+mask binary (the placeholder)
tools/aseprite2spans.py    Aseprite sheet+JSON -> span-compressed bank
tools/spawns.py            projectile spawn points -> build/spawns.inc
tools/pack.py              ZX0 for everything that goes on the disc
tools/build_levels.py      the level art packages -> blobs, and which of
                           them get a second facing
tools/level_banks.py       blobs -> bank images -> one ZX0 stream each
tools/dskdata.py           those streams onto the disc as raw sectors
tools/png2screen.py        image         -> overscan.bin / 16K screen
tools/make_city_map.py     the City's 128x16 map, over the DRAWN tiles
tools/blender_title.py     the title scene and its CPC render settings
tools/make_placeholder_sprites.py
tools/bench.py             T-states by calling a routine from a DI stub
tools/test_climb.py        the ladder, the street and the vertical camera
tools/test_*.py            acceptance suites, fourteen of them
tools/run_tests.sh         all of them, in order

assets/sprites/            the art package: the heroine, the projectiles,
                           common/ for the HUD, level<n>_<name>/ for each
                           level's tiles, characters and machines, each
                           with the artist's manifest.json and, for the
                           tiles, tile_table.json - which tiles are
                           overlays and which are a plain copy (7.3)
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
             ... &A000 the map, &A800 the entity table, &B000 the
             pristine LEVEL_IMAGE the bootstrap lands there (10)
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
`build/levels/banks.inc` with every blob's bank and address. **The top
1 KB of C4 is not the allocator's to give** — 16 scratch tiles live
there for the pickup bake of §8.6. Measured, with the shared set
counted in every level:

| level | unpacked | banks | packed | set pieces |
|---|---:|---:|---:|---:|
| 1 city | 68,420 | 5 | 16,916 | 487 |
| 2 forest | 78,109 | 5 | 19,547 | — |
| 3 cave | 71,879 | 5 | 18,888 | — |
| 4 undersea | 63,296 | 5 | 15,838 | 1,074 |
| 5 desert | 71,989 | 5 | 17,356 | 2,101 |
| 6 station | 66,715 | 5 | 16,736 | 1,255 |

**Five banks, not four.** The window shows bank 1 as well as 4-7, so
there are 81,920 bytes of art storage — 80,896 after the bake reserve
above — and **every level now needs all five.** That puts the "level
logic, collision data, entity management" of §6.1 into `&8000-&BFFF`
instead, which has 14 KB free after the save-under buffers.

**The heroine is two thirds of it.** `kcore` and `kcore_l` are 10,802
each, `kextra` and `kextra_l` 6,931, `kact` 10,659 and `kact_l` 7,937:
**53,062 bytes before a level has drawn a single tile.** The action
sheet is what moved it — `drop` and `die` added 8,144 to every level at
once, and at that point level 2 had 65 bytes of slack and level 5 was
2,029 over. Four rules make it fit, and the last two are new:

* **The set pieces load separately.** The escape car, the shuttle, the
  base door, the escape pod, the siphon and the computer are one fixed
  moment each; together they are 60 KB that never has to be resident
  during play. Level 5 is 100,123 bytes of art and 28,134 of it is the
  finale.
* **The swim set replaces the run/roll set.** She does not run or roll
  under water and she does not swim anywhere else.
* **A level with no ladder carries no `climb`.** Only levels 1 and 3
  have a `ladder` tile in their tilesets and `level_banks.py` reads that
  off `tile_table.json` rather than being told; the other four take an
  action blob 2,714 bytes shorter, with every frame they DO get at the
  same index (§7.1).
* **A character that never moves gets one facing.** `desert_nomad` and
  `desert_informant` are the only two in the game whose sheets have no
  movement tag. 8,214 bytes, and level 5 does not fit without them.

**The banks are reloaded from disc at every level transition, and that
is what makes this fit.** The earlier map gave a bank to each PAIR of
levels' tiles, which only works while the tiles are the only large
asset. Kara alone is 53 KB across both facings (§7.1) and the seven
characters another 23 KB; one level's tiles are 3 KB. Since only one
level is ever loaded, "levels 1-2 / 3-4 / 5-6" was paying three banks
for something one bank holds at a time.

**Everything on the disc is ZX0-packed** (§7.4) as one stream per bank,
so a level transition reads 16-20 KB rather than 63-78 KB. Unpacking it
costs **0.89-1.11 s** — measured on a 6128, all six levels, byte-exact
(§7.5). The whole game's art packs to 110,198 bytes, which would fit in
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

#### The ACTION sheet, and the one tag in it that has no left and right

`heroine_actions_cpc_mode0.aseprite` is the second land sheet: same
24×64 box, **144×448, 19 frames, one tag to a sheet row**, nothing
dropped. It is where everything that is not walking, jumping or
shooting lives:

| tag | frames | sheet row | ms | plays | mirrored |
|---|---:|---:|---|---|---|
| `climb` | 4 | y=0 | 120 each | loops | **NO — see below** |
| `hang` | 2 | y=64 | 240 | loops | yes |
| `use` | 2 | y=128 | 140, 220 | once | yes |
| `hurt` | 2 | y=192 | 90, 130 | once | yes |
| `climb_turn` | 1 | y=256 | 120 | once | yes |
| `drop` | 2 | y=320 | 100 each | loops | yes |
| `die` | 6 | y=384 | 90,120,130,160,110,600 | once, then **holds** | yes |

**`climb` IS DRAWN FROM BEHIND.** She is on a ladder with her back to
the player, so the cel has no left and no right: mirrored, her holster
and her braid swap sides of a figure that is otherwise symmetric, and
nothing about the pixels says so. **It is stored once**, and
`--single-facing climb` is how:

* the tag is emitted **LAST** in the right-facing blob, so every cel
  that does have two facings keeps the same index in both blobs — which
  is what lets `KARA_ANIMS` name one frame number for both and
  `KARA_DURATIONS` point at the right-facing blob's table;
* the mirrored blob simply stops before it — `kact` is 19 frames and
  10,659 bytes, `kact_l` is 15 and 7,937;
* the exporter emits `KACT_TWO_FACED`, and `src/kara.asm` puts it in
  the `KARA_SETS` row: **a frame at or past that number is drawn out of
  the right-facing blob whichever way she is facing**, at 18 T against a
  second frame table, a second duration table and 2,714 duplicated
  bytes (§8.10).

`tools/test_climb.py` checks it on the screen rather than in the table
— the same cel must come out pixel for pixel with `KARA_FACING` either
way round, while `climb_turn`, which is side on, must not — and its
negative control tells `KARA_SETS` the set has two facings all the way
up and watches the left blob index past the end of its own frame table.

**`climb_turn` is what makes the back view usable at all.** Everything
around it — idle, walk, hang — is side on, so there is no cut from one
to the other that does not read as her spinning on the spot. The artist
drew one cel of her turning to the ladder, standing on the ground with
her sole on line 63 like `idle`, and it plays once at each end:

```
idle/walk -> climb_turn -> climb (loop)          stepping on
climb     -> climb_turn -> idle/walk             stepping off onto a floor
```

mirrored the way she is LEAVING, which is the direction held at the
moment she steps off. **The engine holds her still while it is up**,
because the cel is drawn standing on the ground and sliding it up a
shaft would put her feet through the wall — §8.4 for how, §8.8 for where.

**`drop` is a fall she did not choose** — walking off a roof, or letting
go of a ladder that ends in mid-air — as against `jump`, which is the
arc she asked for. The physics is identical and only the cels differ,
so `KARA_FELL` is written where the two part company and not worked out
from a velocity that looks the same halfway down (§8.4). Its two cels
are a line apart vertically, which is the shake; the body is placed
from the hips like `jump`, not from the ground.

**`die` runs once and then holds its last cel for ever.** Its first cel
is a recoil, drawn so it can be cut to from any standing state, so it
pre-empts even the committed states of §8.4; the body walks BACKWARD
inside the frame as she kneels, so **nothing in the engine may move her
while it plays** — the movement is in the art. She keeps her input
locked out and gravity keeps her, so a death in mid-air still reaches
the floor. There is no way out of it yet because there is no respawn:
`ACT_UPDATE` chooses it from `PLAYER_HP == 0` and will stop choosing it
the moment something puts her hit points back.

**Which frames a level carries is not the same question as which frames
exist.** Only levels 1 and 3 have a `ladder` tile in their tileset, and
`tools/level_banks.py` reads that off `tile_table.json` (§7.3) rather
than being told: the other four take a blob that stops before `climb`
and is 2,714 bytes smaller. After `drop` and `die` joined the sheet
there was no level with room to carry frames it cannot draw — level 5
is 80,203 bytes of 80,896 with them and does not pack. The frames it
does get are at the same indices, so nothing in the engine changes.

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
| `kcore.bin` / `_l` | idle, walk, jump, shoot_draw, shoot | 10,802 | 5,582 |
| `kextra.bin` / `_l` | run, roll | 6,931 | 2,522 for the pair |
| `kswim.bin` / `_l` | swim, swim_shoot | 6,450 | 3,484 for the pair |
| `kact.bin` | hang, use, hurt, climb_turn, drop, die, **climb** | 10,659 | 5,725 |
| `kact_l.bin` | ... the same minus `climb`, which is a back view | 7,937 | 8,447 |

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
| `kcore` idle/walk/jump/shoot | 10,802 B | 21,604 B — two banks |
| `kextra` run/roll | 6,931 B | 13,862 B — one bank |
| `kswim` | 6,450 B | 12,900 B — one bank |
| `kact` the actions | 10,659 B | 18,596 B — the back view is not doubled |

`--mirror` emits the left-facing blob: each line's span moves to
`BOX_W - skip - count`, its bytes reverse, and each byte's two pixels
swap. `test_spans.py` checks those blobs against the art flipped, not
merely against themselves.

**And a tag with no left and right is stored ONCE** — `climb`, which is
a back view. `--single-facing` puts those tags at the end of the
right-facing blob and leaves them out of the mirrored one; every other
cel keeps its index in both, and `{NAME}_TWO_FACED` tells the engine
where the second facing stops. See the action sheet above.

**Two characters get one facing for the same kind of reason.**
`desert_nomad` and `desert_informant` are the only two in the whole
game with **no movement tag** — `idle` and `talk`, nothing else; every
other character walks, runs, flies, charges or scans. They stand where
the designer puts them and say a line, so they are drawn the way the
artist drew them and the player walks round to the front. It is 8,214
bytes and level 5 has not got them (§7.5).

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
in `common/` (the HUD). **631 frames across 56 sheets.**

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
The generic sheet and `enemies_swim` are no longer exported. **Five of
the seven get both facings and two do not** — the tags say which, and
the rule is above.

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

### 7.3 Tiles — the transparency contract

**The tile sheets carry explicit transparency now, and it is a TABLE,
not a property of the pixels.**

```
pen 0 = transparent        pen 1 = opaque black
```

Both come out black on the screen, so **nothing about a tile's pixels
says whether it is an overlay** — only the table does. Counted over all
six levels' shipped tables:

| | tiles |
|---|---:|
| in the six levels' sheets | 275 |
| carrying any pen 0 | 69 |
| ... of which OVERLAY | 34 |
| ... of which OPAQUE, and copied anyway | **35** |

**More than half the tiles with transparent-looking pixels are opaque
ones**, and the two populations overlap rather than sit either side of a
threshold: the emptiest opaque tile that is not wholly empty is
`sky_stars` at **126 of 128**, while the fullest overlay, the cave's
`beam_top`, is **14**. There is no pixel count that separates them and
guessing gets the common cases backwards.

#### The second half of the convention is NOT true of this project's pens

**`pen 1` here is Pastel Cyan, not black** (§7.1 gave it to the art).
58 pixels of the city sheet use it and every one is a bright highlight —
the roof cap `roof_l/m/r` stands on, the kerb at the top of `sidewalk`,
the lid of `ac_unit`. So "pen 1 = opaque black" states the authoring
*intent*; what the shipped sheets and the table actually carry is the
**pen 0 half**. Never quantise tile art onto pen 1 expecting black: on
this palette it comes out as the colour Kara's boots rest on.

#### The two sources, per level, in `assets/sprites/<level>/`

| file | what it is |
|---|---|
| `manifest.json` | each `"kind":"tiles"` sheet may carry `"overlay": [...]` of tags and/or tile names. **Anything not listed is opaque.** |
| `tile_table.json` | the derived per-tile table — the manifest's list resolved against the real pixels |

```json
{ "level": "level1_city", "about": "...",
  "sheets": [ { "sheet": "city_tiles",
                "file": "city_tiles_cpc_mode0_sheet.png",
                "tile": [8, 16],          // Mode 0 pixels (8 wide = 16 square units)
                "count": 41, "names_from": "...",
                "tiles": [ { "index": 16,           // frame order in the sheet
                             "name": "ac_unit", "tag": "deco_roof",
                             "draw": "overlay",     // "opaque" | "overlay"
                             "pen0": 48,            // transparent pixels of 8*16 = 128
                             "bbox": [0, 5, 8, 11], // [x,y,w,h] of the non-transparent area
                             "mask_bytes": 64,      // Mode 0 mask size, 0 if opaque
                             "empty": false } ] } ] }
```

#### What a renderer does with it

* **`draw == "opaque"`: a plain copy.** This is the fast path. **Do not
  give it a mask even when `pen0 > 0`** — the tile was drawn over black
  and its pen 0 *must* come out black. `void` is the extreme case:
  `pen0` 128, `empty` true, and still a copy, because painting black
  over what was there is the whole job.
* **`draw == "overlay"`: a masked blit** — `AND mask / OR data`, 2 pixels
  a byte, over the tile already in place. About 2-3x a copy, plus
  `mask_bytes` of storage a tile.
* **`bbox`** lets the blit skip wholly empty rows and columns.
* **`empty == true`** on an *overlay*: draw nothing at all.

#### Coverage today — counted out of the shipped tables

| level | sheet | tiles | overlays | mask |
|---|---|---:|---:|---:|
| 1 city | `city_tiles` | 41 | **11** — roof props, the water tank, the lamp post | 704 B |
| 2 forest | `forest_tiles` | 42 | 0 | — |
| 3 cave | `cave_tiles` | 47 | **9** — crystals, beams, lamps, the ladder, the open gate | 576 B |
| 3 cave | `cave_quake` | 13 | **8** — the waterfall and the flood's surface | 512 B |
| 4 undersea | `sea_tiles` | 42 | 0 | — |
| 5 desert | `desert_tiles` / `desert_quicksand` | 41 / 4 | 0 | — |
| 6 station | `station_tiles` | 39 | 0 | — |
| 6 station | `station_laser` | 6 | **6** — the laser beams | 384 B |
| | | **275** | **34** | **2,176 B** |

**Forest, undersea and desert are at zero because their sheets have no
pen 0 in them at all** — not an oversight and not a decision, just art
that has not needed it yet. `station_tiles` is the other case and the
one to be careful about: 9 of its tiles carry pen 0, every one of them
`opaque`, and `bg_far_1` is at 126 of 128.

#### THIS ENGINE HAS NO MASKED TILE PATH, AND IT ALREADY SHOWS

`DRAW_COLUMN`, `DRAW_ROW` and `DRAW_CELL` are plain copies, and
`tools/make_city_map.py` places all eleven of level 1's overlay tiles as
ordinary map cells. So their pen 0 is painted black, and what that
looks like depends entirely on what it lands on:

* the roof props — `ac_unit`, `chimney`, `antenna` — sit on
  `far_fill`, which is black, so they come out right **by accident**;
* the water tank's top row lands on the skyline row and punches a black
  hole in `far_tower`/`far_block`;
* `lamp_top` and `lamp_pole` are on brick, and their 78 and 84
  transparent pixels paint **an 8x32 black rectangle out of the wall** —
  rendered from the shipped tiles and the generated map, not predicted.

**And the cost argument in the table does not transfer unchanged.**
"Once a room, not every frame" assumes a room-at-a-time renderer; this
one scrolls, and repaints a 384-byte column every character step (§9).
An overlay tile in that column is 32 of those bytes at 2-3x, every step
— which is affordable for the eleven decorations level 1 has and is a
number to check before a level puts overlays down a whole wall.

The masked path belongs to Module 6's tilemap rewrite (§11), with the
map format saying which layer a cell is on. Until then the rule for
`make_city_map.py` is the one the picture already enforces: **an overlay
tile may only be placed over black.**

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

The whole asset set is **224,897 bytes raw, 45,035 packed — 20%**.
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
level is changing. The biggest stream measured is 4,836 bytes against
8 KB of room.

#### Getting it off the disc: the engine drives the 765 itself

The boot sequence disables both ROMs (§4), so by the time a level
changes there is no firmware to call: the OS is not in memory, AMSDOS
is not paged in, and the engine occupies `&0040-&3FFF` where the lower
ROM would be. Bringing it back would mean re-enabling the ROMs over the
top of the engine, running the call from high RAM, and keeping the
firmware's workspace at `&B100-&BFFF` and AMSDOS's buffers at `&A700`
intact for the whole game — three standing constraints on the memory
map for the sake of a routine that is 250 bytes to write.

`src/disc.asm` talks to the uPD765 directly instead:

```
&FA7E   bit 0 = motor on      (write)
&FB7E   main status register  (read)   7 RQM  6 DIO  5 EXM  4 CB
&FB7F   data register         (read/write)
```

**The level data is not in the filesystem.** `tools/dskdata.py` writes
the packed streams to raw sectors from track 8 on — past anything
AMSDOS allocated, which it checks — and emits their track and sector
into `build/levels/disc.inc`. That costs a build step and saves parsing
a directory. It runs twice: once before RASM to write the include from
the stream sizes, once after iDSK to patch the image, so the two agree
by construction.

#### It passed every test here and black-screened on real hardware

**cpcemu is not a witness about the FDC.** `chips/upd765.h` resolves the
controller synchronously - the instant the last command byte is written
- and never runs out of patience. A real uPD765 does neither, so every
timing and sequencing assumption disc code makes is one cpcemu will
agree with whether or not the hardware would. The first version of
`disc.asm` passed all ten suites and showed **a black screen on Retro
Virtual Machine**, with four separate faults, every one of them already
paid for once in `~/repos/Homeplanet/src/sys/fdc.asm`:

1. **END OF CYLINDER is not an error.** A single-sector transfer sends
   EOT equal to R, so a real controller ends at the end of the cylinder
   as a matter of course and says so with IC=01 and ST1 bit 7. The
   bytes are already in memory. `AND &C0 / RET NZ` calls that a
   failure; cpcemu returns IC=00 and never disagrees.
2. **The transfer loop must watch RQM, DIO and EXM in ONE read.** A
   refused command never enters the execution phase and a transfer the
   controller abandons leaves it early - either way it is handing back
   result bytes while we wait for data. Reading EXM separately, before
   RQM, is also a race: the chip has not decided, EXM reads 0, and both
   sides wait for the other.
3. **Drain the result by status, not by count.** READ returns seven
   bytes, SENSE INTERRUPT STATUS two, and SENSE with nothing pending
   ONE. And drain before the FIRST command, because AMSDOS ran before
   us and the chip keeps its state across the ROMs going out.
4. **A seek is collected with SENSE INTERRUPT STATUS, not by polling
   CB.** CB rises microseconds after the last command byte and is
   cleared by the SENSE, so polling it either falls through a seek that
   has not begun or waits for something only the next line can cause.
   cpcemu never sets it at all.

Plus one rule of this project's own: **nothing may hang**. Every wait
outside the inner loop is counted out, `LEVEL_LOAD` returns carry clear
rather than spinning, the demo then runs without the sprite instead of
drawing out of a bank full of noise, and `DISC_DIAG` paints ST0/ST1/ST2
as 24 blocks in the corner so a photograph of the screen is a complete
bug report.

`tools/test_fdc.py` checks what can be checked without a real
controller: ten result-byte verdicts, the transfer loop counted from
the source against the 128 T deadline, and that every wait is bounded.
It carries a negative control - restoring `AND &C0` fails it. **Passing
it is necessary and not sufficient; confirm on RVM.** The whole of it
is written down in [docs/AmstradDskReadHowTo.md](docs/AmstradDskReadHowTo.md),
including when NOT to write this code at all: if everything fits in RAM
at once, load the banks from the BASIC loader with the firmware's own
driver, the way `~/repos/TheShaft` does.

**One sector an operation, not a multi-sector READ DATA with EOT.**
Partly because the emulator does not implement the EOT form and asserts
on it, so a driver written that way could not be tested at all — but
mostly because it costs nothing: AMSDOS formats with a 2:1 interleave
(C1 C6 C2 C7 …) precisely so that reading in ID order leaves a sector's
worth of time between one read and the next, which is what the command
overhead fits into. The seek is only paid when the track changes.

**Interrupts are off for the whole load.** The 765 has no FIFO on this
machine — one byte in the data register and an overrun if it is not
taken in time. Nothing is being drawn during a level change, but the
caller has to re-anchor the raster gates afterwards, because the tick
count has been standing still.

Measured end to end, `LEVEL_LOAD` off a real disc image:

| level | banks | T | |
|---|---:|---:|---:|
| 1 city | 5 | 6,497,920 | 1.62 s |
| 2 forest | 5 | 7,404,240 | **1.85 s** |
| 3 cave | 5 | 7,056,908 | 1.76 s |
| 4 undersea | 5 | 6,093,152 | 1.52 s |
| 5 desert | 5 | 6,622,436 | 1.66 s |
| 6 station | 5 | 6,435,328 | 1.61 s |
| a set piece | 1-2 | | 0.20-0.46 s |

of which 0.14 s is motor spin-up, ~0.6 s the read and ~1.1 s the
unpacking. `tools/test_levels.py` loads every set of every level and
compares each bank byte for byte; flipping a single byte of one sector
makes it report 12,144 wrong, because ZX0 amplifies.

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

**The incoming ROW is split FOUR ways, and the number is a frame-budget
decision and nothing else.** Nothing the beam can see changes until the
latch, so how many frames the row is painted over is free — it only
costs latency. It was two halves of 16,742 T, and that fitted until
`climb` arrived: the back view is 324 span bytes and **55,548 T drawn
and erased, more than her heaviest gun cel**, so a half row on the
frame it landed on took the loop to **195 iterations per 200 hardware
frames**. Four quarters are 9,192 T each and it is 200 again — measured
on the five frames that dropped, every one of them a frame with a paint
in it. `V_PARTS` is the constant.

That makes a vertical step **five frames**: `SCROLL_V_STEP` and part 0,
then `SCROLL_V_PART` three times, then `SCROLL_VBLANK` latches R12/R13.
A climb at `P_CLIMB` = 1 needs the next row after eight, so the camera
still keeps up; a level that scrolls faster than a row every five frames
does not tear, it lags — which is what the three-frame version did
sooner. **A test that counts FRAMES to drive this axis is counting the
wrong thing** and `tools/test_module4.py` says so: written against the
old cadence it sampled five steps where it used to sample eight, and its
tearing negative control passed for the wrong reason.

**The camera keeps her BEHIND the middle of where she is going.** One
fixed column cannot do that in both directions, so the mark moves with
her facing: walking right she rides at `CAM_TRAIL` = 27 and the 44
bytes of level in front of her are the ones on screen; walking left she
rides at `CAM_LEAD` = 47, its mirror. It was a static zone of 16..56,
which meant walking right she sat at column 56 with 18 bytes of
warning.

**The marks are BOX columns, because `PLAYER_SCREEN_X` returns one**
(§8.10). While `CAM_TRAIL` was a sprite column and `KARA_BOX_W` a box
width the mirror was out by the difference: 50 bytes of warning walking
left against 44 walking right. Mixing the two units in one expression
is the whole class of bug §8.10 is about.

**Turning round therefore PANS.** She is 20 bytes from the new mark, so
the camera scrolls a whole character every frame while she walks her
own byte and she drifts across the picture at 1 byte a frame, arriving
in 20. A pan is exactly a run's frame cost — a column every frame — and
it is the one thing that makes the loop drop a frame or two (§9).
`CAM_BAND` is what tells "the camera is following her" from "the camera
is panning to catch up": only the first gets the lock-step below, and
without it she would freeze at whatever column she turned round on
while the camera panned for ever.

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

**Every tile blitter here is a plain copy**, which is correct for the 30
opaque tiles of level 1 and wrong for its 11 overlays — see §7.3 for
what that already costs the picture, and §11's Module 6 for where the
masked path goes.

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

**Those are what a tile DOES; `tile_table.json` says how it is DRAWN**
(§7.3), and the two are independent — `ladder` is an overlay in level 3
and an opaque tile in level 1, with the same `Ladder` flag in both. The
format has nowhere to put "this cell is an overlay over that one" yet,
which is the same gap: a cell is one byte and an overlay needs the tile
under it as well. Settle it here before the editor is written, with the
tile flag byte and the `param0`/`param1` meanings (§11 step 7).

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
| `ROLL` | `roll` 8 | **DOWN + left or right**, on the ground | the 8 frames are done |
| `AIM` | `shoot_draw` 2 then hold | **SPACE held** | SPACE released |
| `FIRE` | `shoot` 4 | **SPACE released** from `AIM` | the 4 frames are done |
| `CLIMB` | `climb` 4 | UP or DOWN on a ladder | she steps off it |
| `HANG` | `hang` 2 | on a ladder, nothing held | UP or DOWN |
| `TURN` | `climb_turn` 1 | grabbing a ladder, or stepping off one onto a floor | the cel's own 120 ms |
| `DROP` | `drop` 2 | off the ground **without having jumped** | she lands |
| `DIE` | `die` 6 | `PLAYER_HP` reaches 0 | **never** — it holds its last cel |
| `SWIM` | `swim` 8 | level 4, in water | out of the water |
| `SWIM_FIRE` | `swim_shoot` 4 | SPACE released while swimming | the 4 frames are done |

**A JUMP AND A FALL ARE DIFFERENT ANIMATIONS AND THE SAME PHYSICS.**
`jump` is the arc she chose; `drop` is the ground going away — walking
off a roof edge, or letting go of a ladder that ends in mid-air. Only
the cels differ, so nothing can tell them apart from the state halfway
down: `KARA_FELL` is set in the two places where the ground goes away
without her asking (`PLAYER_Y`'s "walked off an edge" and
`CLIMB_LEAVE`) and cleared in the three where she chooses to leave it or
arrives back on it (`.jump`, `.land`, `CLIMB_LAND`).

**THE LADDER TURN IS THE ONE STATE NOTHING IN `action.asm` CHOOSES.**
`climb` is a back view and idle, walk and hang are all side on, so she
cannot cut from one to the other (§7.1). `player.asm` plays the cel by
writing the state itself — `CLIMB_TURN_START` at the grab,
`CLIMB_TURN_OFF` when she steps off onto a floor, which also faces her
the way she is leaving. It is COMMITTED, which is what makes it stick
for the cel's own duration, and `PLAYER_UPDATE` **holds her still for
exactly as long**: the cel is drawn standing on the ground, and the two
have to agree or she moves under a cel that says she is not moving.

**DEATH PRE-EMPTS EVERYTHING, INCLUDING THE COMMITTED STATES.** The
artist drew `die`'s first cel as a recoil precisely so it can be cut to
from anything she is standing in, so the `PLAYER_HP == 0` test is the
first thing `ACT_UPDATE` does — 30 T a frame. While it plays she takes
no input but gravity still owns her, so a death in mid-air reaches the
floor; **nothing moves her sprite**, because the body's own walk
backward as she kneels is inside the frames. It has no exit: the run
holds its last cel and the test keeps choosing it, so she stays down
until something puts her hit points back. **There is no respawn and no
game over yet** — that is §11 step 8's, and this is the hook it needs.

**The gun is draw-hold-release, not a trigger.** SPACE going down plays
`shoot_draw` and then holds its last frame; SPACE coming up plays
`shoot` and fires on its first frame. That is what the two-frame
`shoot_draw` tag is for, and its `draw_offset_x=4` in the JSON is the
muzzle's X inside the box — the bullet spawns there, not at the edge of
the sprite.

**Three states are committed**: a roll runs its 8 frames whatever the
input does, which is what makes it a dodge and not a nudge; the shot
runs its 4, which is what stops a tapped trigger playing one frame of a
four-frame recoil; and the ladder turn runs its one. A roll cannot start
in the air.

**Implemented** - `src/action.asm`, one table, driven by
`tools/test_actions.py`. Two things about it are worth having written
down, because neither is obvious from the table:

**THE CEL RATE IS THE ART'S.** Every blob ships a `Kxxxx_DURATION`
table - the milliseconds Aseprite held each cel for, rounded to 50 Hz
frames - and nine cels of the drawn sheet are not shipped, with each
dropped one's time added to the cel before it (§7.1). Running the
animation at a fixed rate instead makes the thinned walk cycle faster
than it was drawn and out of step with the two bytes a frame she
travels. So `ACT_ANIMATE` reloads its timer from that table, and the
test compares every cel's dwell against it.

**ENTERING A STATE LEAVES THE CEL INDEX AT 255, NOT 0.** The animator
runs the timer down and steps in the same call, so a state entered at
cel 0 with a timer of 1 shows its SECOND cel first: idle opened on
frame 1, a four-cel recoil played three, and a looping walk never came
back round to where it started. `INC A` wrapping 255 to 0 is the whole
fix, and the check that catches it has to drive the transition rather
than poke `KARA_ANIM` - a test that sets up the state itself is testing
its own setup, which is exactly what the first version of it did.

**Her frames are in two blobs and three banks**, so `KARA_SET` travels
with `KARA_FRAME`: `kcore` is idle/walk/jump/shoot, one bank a facing
(`&C5`/`&C6`); `kextra` is run and roll, BOTH facings in `&C7` because
the pair fits. `tools/level_banks.py` PINS all three in every level and
emits the addresses only after checking they agree, so the engine
addresses her by constant instead of reloading a table at each
transition.

**Which cel fires is art too.** `KCORE_SPAWNS` (from
`projectile_spawn_points.json`) marks the pixel a shot leaves on each
firing cel, and the `shoot` tag has two of them - cels 14 and 16 -
which is the pair of pistols of §8.5 alternating. `ACT_MUZZLE` walks
that table when a cel changes, so the gun code holds no cel numbers and
a re-drawn recoil moves the shot with it.

**0 IS FACING RIGHT.** `bullets.asm` read the flag the other way round
and nowhere else did. The Module 1-3 screen never writes
`KARA_FACING`, so it sat at its initialiser and both readings agreed by
accident for two modules; the first shot fired from the scrolling demo,
where the player code does write it, went backwards out of her own
muzzle.

**The input byte is now full**, and the two new controls cost the two
spare bits. Bits 0-3 have to stay in the joystick's own order — that is
what lets row 9 fold in with no shifting (`input.asm`) — so:

```
0 UP  1 DOWN  2 LEFT  3 RIGHT  4 FIRE(SPACE)  5 spare  6 PAUSE(ESC)  7 RUN(SHIFT)
```

**The roll is DOWN and a direction, and bit 5 is free again.** It was Z;
it is now the two keys a player's hands are already on, which is what a
dodge wants. It triggers on a PRESS of either half while the other is
held, not on the state of both — a committed 8-cel roll that
re-triggered on the frame it ended would never let go while the player
kept crouching and walking. `DOWN` + `FIRE` is still the manual reload
(§8.5), so nothing collides.

Z was `IN_ACTION`, a second interact key alongside RETURN, then the
roll, and is now bound to nothing. Interact is `UP` alone, which is what
plan.md §5.2 asked for in the first place ("αν πατηθεί UP").

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
Bullets move 4 pixels/frame. Reload is manual (Down+Fire) or
automatic when both magazines hit 0; during reload the player is slowed or frozen.

**A round dies on a solid tile, and the probe is a coordinate
conversion.** The pool holds SCREEN coordinates and the map is in WORLD
ones, so the round's byte column and its scanline are lifted into the
world — `+ WORLD_X * 2` across and `+ WORLD_CR * 8` down, the row
wrapping in a byte because that IS the map's height — and handed to
`MAP_ATTR`. `TA_SOLID` only: a platform is a floor you jump up through
and a round crossing its edge should not stop dead in mid-air. Their
rounds use the same code.

**An idle pool is fourteen slots of nothing**, so `BUL_LIVE` counts the
rounds in the air and every routine that walks the pool returns at once
when it is zero (§9). The draw and the erase have to make that decision
on the SAME count, because `UPDATE_BULLETS` runs between them and can
kill a round that still has to be lifted off the screen; `BUL_DREW` is
the count as the draw found it.

**And a BUSY pool is fourteen slots for three rounds, which is the same
fault one step along and the bigger one.** Measured over all four walks
— `UPDATE_BULLETS`, `BUL_DRAW`, `BUL_ERASE`, `ENEMY_SHOT_CHECK` — one
live round costs 7,452 T and each extra one 1,224, so **6,228 T of every
firing frame was the thirteen DEAD slots behind the first**. The frame
has 160 T spare (§9), so tap-firing while the screen scrolled dropped
**43 frames in 200**.

**What that looks like is a character who has stopped walking**, which
is how it was reported and why it survived so long. In the camera's push
zone her screen column never changes — the walk IS the scroll (§8.2) —
so a dropped frame is not a stutter, it is a byte of ground she does not
cover. She travelled 159 bytes in 200 frames instead of 199.

`BUL_TOP` is the fix: **one past the deepest slot ever taken since the
pool last emptied**. `BUL_SPAWN` always takes the lowest free slot, so
the live rounds are a prefix with holes and the mark bounds them
exactly; it costs nothing per slot, which an exact live-count test would
not. Measured in play it peaks at **3**. `BUL_DREW_TOP` is its snapshot
at draw time, for the same reason `BUL_DREW` is `BUL_LIVE`'s: `ACT_MUZZLE`
fires between the draw and the erase and can raise the mark, and the
erase must not walk past what the draw wrote save entries for. With it,
tap-firing while scrolling is **198 loop iterations in 200** and she
covers her full 199 bytes.

| walking right, scrolling | loops / 200 | bytes travelled |
|---|---:|---:|
| not firing | 199 | 199 |
| trigger HELD | 198 | 199 |
| tapping the trigger | 198 | 199 |
| ... with `BUL_TOP` forced to `BUL_MAX` | 174 | 175 |

**THE TEST THAT MISSED THIS HELD THE TRIGGER.** The gun is
draw-hold-RELEASE (§8.4), so `JOY_FIRE` held down for 200 frames is
`AIM` and never puts a round in the air: every "walking right + firing"
measurement in `tools/test_enemies.py` was a frame with an idle pool.
Both of its firing cases tap now, and `tools/test_module5.py` owns the
property that was actually broken — **she must cover the same ground
firing as not** — with the last row of that table as its negative
control.

### 8.6 The entity table, and game state — implemented

```asm
PLAYER_HP:        db 100     ; 0-100, medkit restores 35, capped at 100
KEYS_COUNT:       db 0
COINS_COUNT:      db 0
AMMO_RESERVE:     db 28
STATUES_HELD:     db 0
CURRENT_BOOK_ID:  db 0
```

**The record in RAM is the record in the file.** `src/entity.asm` lays
an entity out as editor.md §9.2's eight bytes, in that order, so module
6's loader is an `LDIR` and not a conversion — `kind, x u16, y u16,
flags, p0, p1`, at `ENT_TABLE` (`&A800`, straight after the map),
`ENT_MAX` = 24 of them. X and Y are **world pixels**, because a
designer thinks in pixels; Y anchors the **base** of the hitbox, which
is what a designer drops on a floor, so the top is `y - height`.

The level's header carries an entity count (editor.md §9.2 byte 10) and
`ENT_COUNT` is it. **Walking all 24 slots instead cost 4,004 T a
frame** with six in use, out of a frame that had 1,324 spare; stopping
where the level stops took it to 2,916. A test that writes the table by
hand has to write the count too.

`p0`/`p1` are per kind, which editor.md's Appendix A leaves as free
text — this is the engine's half of that agreement:

| kind | p0 | p1 |
|---|---|---|
| `PICKUP` | `PU_*` | amount, lock id, or symbol |
| `DOOR` | lock id | `PU_*` that opens it |
| `RECEPTACLE` | `PU_*` it takes | how many it still wants |
| `NPC` | coins asked | which line he says |
| `ENEMY` | `EN_*` — which character | patrol half-width in tiles |
| `HAZARD` | damage | period |

**`p0` is always "which thing this is".** The enemy row first read
`p0 = patrol width, p1 = shots a second`, which leaves nowhere to say
which character it is and makes the fire rate a property of the
instance when it is plainly a property of the character. The rate, the
speed, the box, the art and the hit points come from the type instead
(§8.7), so a designer places a drone and not a set of numbers.

`ENTITY_COLLISION_CHECK` takes the `EF_` bits an entity must have in
`A` and publishes the first record whose box meets hers in `ENT_HIT`.
The AABB is a separating-axis test — X 16-bit in bytes, Y 8-bit
because the map is 256 lines tall. `ENT_UPDATE` runs it twice: once for
`EF_TOUCH` (a pickup, taken on contact — a key you have to ask for is a
key the player walks past) and once, on an `IN_INTERACT` **press**, for
the things that spend something. The five handlers are
`CHECK_KEY_DOOR`, `PLACE_STATUE`, `READ_BOOK_PUZZLE`, `TALK_NPC_COIN`
and `USE_MEDKIT`, and each reports through `ENT_RESULT` rather than the
carry, because "it refused" has to say *why*: a locked door and an
empty hand are not the same message.

**A slot is told by its FLAGS, not by its kind.** Kind 0 is
`EK_PLAYER_START`, so an all-zero record is a real entity at (0,0)
unless `EF_ACTIVE` decides it.

#### Pickups are drawn by being baked into the tilemap

A pickup is 8x16 pixels — **exactly one tile** — and it does not move
until it is taken, which makes it scenery, and scenery is already free:
`DRAW_COLUMN` copies a tile into the incoming column at 64 T a raster
whether there is a key drawn on it or not. So `ENT_BAKE` composites
each one **once**, at level install, into a private copy of the tile it
stands on, and points the map cell at the copy. From then on it costs
nothing at all — no draw, no erase, no save-under, no raster gate — and
it scrolls because the whole picture scrolls. When it is taken,
`ENT_SETTLE` puts the map byte back and repaints the four character
cells, once.

The alternative was written first and measured: see §9.

| | |
|---|---:|
| 16 scratch tiles, top of bank C4 (`&7C00`, indices 240-255) | 1,024 B |
| `ENT_BAKE`, four pickups, once a level | 348,052 T |
| per frame, for ever after | **0** |

Three things it costs:

* **1 KB of C4, taken out of the allocator's hands** in
  `tools/level_banks.py`. Every level still fits; the tightest has 5
  bytes to spare. `TILE_SRC` reads any 64-aligned address in that bank
  as a tile index, so the reserve only has to be aligned.
* **The pickups do not animate.** The sheets draw the key over 4 cels
  and the ammo over 3; the baked one is cel 0.
* **A pickup sits on the tile grid.** An unaligned one would need four
  scratch tiles instead of one, so `ENT_BAKE` takes the cell its
  top-left falls in. `tools/make_city_map.py` places them on the grid.

`ENT_STAMP` is the one place the column-major tile layout of §9 is
*written* rather than read, so it is the one place the formula appears
the other way round:

```
tile offset = (byte >> 1) * 32 + line * 2 + (byte AND 1)
```

Level 1's own sheet draws a key and an ammo clip and nothing else,
which is right — a medkit is not city art. The other four kinds fall
back on `hudicon`, which is 4x16 as well, carries one cel of every
pickup in the game, and is in every level's bank set already.

### 8.7 The enemies — one on screen, and it is a persistent sprite

`src/enemy.asm`. Their records are `EK_ENEMY` rows of the same entity
table (§8.6): `p0` is `EN_*`, `p1` the patrol half-width in tiles. The
type table holds the rest, per character — both facings' bank and
address, the move and fire cel ranges, the box, the speed, the fire
period and the hit points.

**Only the one in view is live.** The rest keep their hit points and
their place and do nothing; they are off screen and nobody can tell.
`tools/make_city_map.py` spaces them more than a screen apart and
asserts it, so "one on screen" is a property of the LEVEL; `ENEMY_PICK`
takes the first it finds anyway, because a level that got it wrong
should lose an enemy and not the frame.

**Live and drawable are different questions**, and conflating them
froze a drone at the edge of the picture: it patrolled until its box no
longer fitted, was culled, and — because the same test decided whether
to *update* it — stopped moving, so it could never walk back in. It is
live within a screen either side of the view and drawable only when its
whole box fits with a character to spare at both ends.

#### What an enemy costs, and how it is paid for

| | draw | erase | both |
|---|---:|---:|---:|
| `cityagent`, 12×64, 194-274 span bytes | 30,652-36,792 | 10,108-12,028 | **40,760-48,820** |
| `citydrone`, 8×20, 100-106 span bytes | 12,940-14,892 | 4,204-4,348 | **17,144-19,240** |
| `citydroneshot`, 3×3 | 272 | 76 | 348 |

against a scrolling frame that had **420 T spare** before this module
started. **A drone fits and an agent does not**, by a factor of two and
a half; both are in the type table because the data is right and the
day the frame has room nothing here changes, and level 1's map ships
drones. Drawn like Kara — draw and erase inside one frame — one drone
took the loop from 200 iterations per 200 hardware frames to **114**.

**So the enemy is a PERSISTENT sprite and she is not.** Hers is drawn
and erased inside a frame because she moves every frame. The enemy's
pixels are *left on the screen* between refreshes:

* while the picture scrolls they stay right **for nothing**, because
  the CRTC moves every pixel on the screen and a world-fixed sprite is
  supposed to move exactly that far;
* Kara's save-under captures them where she walks over it and her erase
  puts them back, and both bullet pools do the same;
* the incoming column is the one thing that would disturb them, and the
  drawable window keeps the whole box a character clear of both edges
  so it cannot.

A frame that cannot afford 17,968 T of enemy therefore does not spend
it, and **nothing flickers** — which is the whole difference between
this and skipping a draw-and-erase pair. Two frames do not pay:

| | |
|---|---|
| the picture is moving | `VIEW_STEP`, set by `H_REQUEST` and counted down. The enemy is redrawn 25 Hz while she walks and not at all while she runs; it stays put and stays correct. |
| `ENT_UPDATE`'s touch sweep is due | they alternate on `FRAME_COUNT` bit 0. Together they are 80,248 T of a 79,872 T frame — over by 376 — and neither loses anything: she cannot cross a 4-byte pickup in the 2 bytes a frame she can travel. The INTERACT pass still runs every frame, because a keypress lasts one. |

**The refresh is the LAST thing in the frame**, after every sprite has
been erased. It cannot go before her draw: she is 560 T a line against
the raster's 256 and the top border is her entire lead, so 18,000 T in
front of her tears her from screen line 38 down. It cannot go between
her draw and her erase either — she would save the enemy's new pixels
and her erase would then paint background over them. The same applies
to the cell a taken pickup leaves behind, which is why `ENT_SETTLE`
queues the repaint rather than doing it (`ENT_REPAINT_DUE`): done in
the logic phase it put the new tiles down and her erase put the pickup
straight back over the twelve bytes she overlapped.

**Their fire is a separate pool** — four rounds, a different pen, and a
solid two-line block like hers rather than the `citydroneshot` art,
because 348 T a shot is not worth paying for six pixels. Her rounds
kill; theirs take `EBUL_DAMAGE` off `PLAYER_HP`. A dead enemy's
**record** is marked `EF_TAKEN`, not just its slot, so reloading the
level does not put it back on its feet.

**Where a shot leaves is art, where the sheet says so.**
`EN_T_SPAWNS` points at the character's `*_SPAWNS` table from
`build/levels/spawns.inc`; the drone sheet has none and its shot leaves
the nose of its box. A left-facing sprite mirrors the x to
`frame_width - 1 - x`, one subtraction against storing the table twice.

### 8.8 The ladder, the street, and the vertical camera

The City's map is 128x16 tiles = 1024x256 world pixels and the display
is 192 lines, so the view's top can sit anywhere in 0..64 pixels — eight
character rows, and that is the whole vertical budget. The level spends
it: the roof's surface is world y 96, the pavement's is 224, and no view
shows both. Climbing down therefore drives the camera the whole way,
which is the first time anything but a test has driven §8.2's vertical
axis.

| | world y | map row |
|---|---:|---:|
| the roof she walks on | 96 | 6 |
| the last row of wall | 208 | 13 |
| the pavement she walks on | 224 | 14 |

**The ladder's top tile is in the ROOF's own row**, and it carries
`TA_CLIMB + TA_PLATFORM`. That pairing is the whole mechanism: a
platform is a floor from above and nothing from below, so she walks
over the top rung like any other roof tile, and DOWN on it steps her
onto the shaft. A ladder that started one row lower — which is where
the artist's mockup draws it — would be a thing she could only fall
onto.

**Every probe on a ladder is ONE COLUMN wide.** Her collision box is
6 bytes and spans three of the 4-byte tiles; the shaft is one, so
`BOX_SOLID_V` merges the brick either side of it and comes back solid
at every rung. `CLIMB_AT` (collide.asm) asks about a single column
instead.

**And the ladder is what found §8.10's bug.** Her collision box used to
be the LEFT HALF of her sprite box, so centring the box on the shaft
drew her climbing the brick three bytes to the right of it. The box is
centred under her body now and the snap is `KARA_BOX_W / 2` — the
middle of the box, which is also the middle of the figure.

**THE BUILDING'S FACE IS BACKGROUND, NOT A WALL.** `brick`,
`brick_win_lit`, `brick_win_dark` and `brick_top` have no attributes.
Made solid — which they were — the foot of every ladder is a place she
arrives *inside* a wall: she is three tiles wide, the shaft is one, and
`BOX_SOLID_H` then refuses every step she tries to take along the
street. What holds her up is the roof at the top and the pavement at the
bottom; the rows between them are scenery, and a roof edge she walks off
is a fall to the street, which is what a roof edge is. The artist's own
`mockup_city_street.png` shows exactly that: she walks the pavement in
front of a facade that runs floor to roof.

**The camera follows her MIDDLE.** `CAMERA_V` keeps `KARA_WY +
KARA_BOX_H / 2` between `CAM_TOP` and `CAM_BOT` (64..112) and asks for
one character row at a time. Measured from the top of her box instead,
the band has to sit 30 lines higher to frame her and the view stops one
row short of its limit with the road half off the bottom of the
display. It requests a step only while none is pending, because a
vertical step takes three frames and a second request inside that window
would be worked out from a start address the CRTC has not been given
yet — and it stands down for the frame when it has asked for one, so
the two axes never fly together (§8.2).

**A test that pokes `V_REQUEST` now has to hold it up EVERY frame.**
There is a driver on the other end of that byte, and it only stands down
while a request is pending; a driver that pokes on some frames and not
others hands the wheel back on the frames it skips and measures the
camera's correction as a step in the wrong direction.
`tools/test_module4.py`'s `vstep` says so.

**SHE TURNS TO THE LADDER AND TURNS OFF IT AGAIN.** `climb` is a back
view and everything around it is side on, so one cel of `climb_turn`
plays at each end (§7.1): `CLIMB_GRAB` starts it, `CLIMB_LAND` starts it
again — facing the way she is leaving — and `CLIMB_LEAVE` does not,
because a ladder that ended in mid-air is followed by a fall and a fall
is `drop`, not a turn. **`PLAYER_UPDATE` holds her still while it is
up.** The cel is drawn standing on the ground with her sole on line 63,
so sliding it up a shaft would draw her feet through the wall; the state
is committed in `action.asm` for exactly as long, and the two have to
agree.

`tools/test_climb.py` drives the whole thing from the joystick — onto
the ladder, down to the pavement, along it, back up to the roof — and
checks her feet land on exactly the surface lines above, that the view
travelled its full range, that the turn plays first and holds her where
she is for the art's own beat, that the cels come out of `kact` and not
`kcore`, and that the loop still holds 50 Hz. It also checks the back
view **on the screen**: a climb cel must come out pixel for pixel with
`KARA_FACING` either way round while `climb_turn`, which is side on,
must not. Two negative controls — `TA_CLIMB` taken off the ladder tile,
after which DOWN does nothing at all, and `KARA_SETS` told the action
set has two facings all the way up, after which the left-hand draw
indexes past the end of `kact_l`'s frame table.

### 8.9 The art package's mockups are the reference for composition

`assets/sprites/level<n>_<name>/mockup_*.png` are screens of the level
composed by the artist, and reading one back tile by tile is the fastest
way to settle a question the tiles alone cannot answer. Two came out of
`mockup_city.png` and `mockup_city_street.png`:

* **The walkable surface is the TOP LINE of its tile**, and in this art
  that line is the bright pen-1 cap — `roof_m`'s and `sidewalk`'s alike.
  The mockup stands her on it with one line of gap under her boots,
  which is what the engine does.
* **`brick_top` is not used.** It draws a black band and then a pale
  ledge five lines in, and the map used to put it directly under the
  roof, where it reads as a SECOND floor 16 pixels below the one she is
  standing on. A play-test report (`errors/wrongwalkplace.png`) circled
  her boots and pointed an arrow at that ledge. She was never in the
  wrong place; the picture had two roofs. The wall under a roof she
  walks on is plain brick and windows.

The lesson generalises: when a report says something is in the wrong
place, check the composition against the mockup before moving the thing
that was reported. Moving Kara down to the arrow was tried first and it
put her knee-deep in the parapet.

### 8.10 Her collision box, and where the sprite sits on it

**`KARA_WX` / `KARA_WY` are the BOX, not the sprite.** The sprite box is
12 bytes by 64 lines; the collision box is 6 by 64, centred in it, and
the drawer takes the difference off once a frame:

```
KARA_BOX_W  6       bytes            KARA_ART_X  (KARA_W_BYTES - KARA_BOX_W) / 2
KARA_BOX_H  64      lines                        = 3, the sprite's left edge
                                                 relative to the box's
PLAYER_TO_SCREEN:   KARA_X = KARA_WX - view * 2 - KARA_ART_X
```

That is the ONLY place the offset is paid. Every probe — `BOX_SOLID_H`,
`BOX_SOLID_V`, `CLIMB_AT`, `ENT_OVERLAP`, `ENEMY_SEES` — reads her
body's own edges for nothing, which matters because the frame has 160 T
spare (§9): adding the offset at each of the six probe sites instead
cost more than that.

**It was the other way round and it was wrong.** `KARA_WX` was the
SPRITE's left edge and the box its leftmost 6 bytes, so her collision
box sat three bytes — six pixels — to the left of her boots, and
`KARA_BOX_H` was 60 against a figure whose feet are on line 63, so her
boots were drawn three lines THROUGH whatever she was standing on.
Nothing in the City showed the horizontal half because the roof has no
edge to stand on the lip of; the ladder showed it at once (§8.8).

**Both numbers are measured off the shipped blobs, not chosen:**

| | |
|---|---|
| every cel's last drawn line | 63 wherever she is standing on something — all 18 of `kcore`, 11 of `kextra`'s 13, and 13 of `kact`'s 19 |
| her boots' byte range | 3..8 on idle and walk, 1..9 at the widest stride |

so the box is the full 64 lines and 6 bytes at an offset of 3. Her
boots now rest ON the floor line, which is what the artist's
`mockup_city.png` draws (§8.9).

**The six that stop at 62 are the six with nothing on the floor**, and
they are drawn from the body rather than from the ground: `climb` 1 and
3, which is the one-line bob written into the ladder cycle; `drop` 0,
placed from the hips like a `jump` cel; and `die` 3, 4 and 5, where she
is already down and the body has walked backward inside the frame. None
of them is standing, so none of them measures the box.

**What else moved with it**, and each of these was a mixed-unit bug:

* `CAM_TRAIL` / `CAM_LEAD` are box columns now, because
  `PLAYER_SCREEN_X` returns one. See §8.2.
* The world's edges are still the SPRITE's, because what must stay on
  screen is the picture: the right bound is
  `WORLD_W - KARA_W_BYTES + KARA_ART_X` and the left one is
  `KARA_ART_X`, not 0. A box clamped to 0 puts the sprite at -3,
  `KARA_X` comes back 253 and the blitter culls her — which is how the
  left-hand bound was found, by measuring her screen column at the edge
  rather than by looking at the picture.
* `EBUL_HITS_HER` compares on SCREEN, where `KARA_X` is the sprite, so
  it adds `KARA_ART_X` back. A round six pixels to her left used to
  count as a hit.
* `ENT_HITBOX`'s PlayerStart row is `KARA_BOX_W, KARA_BOX_H` rather
  than a copied `6, 64` — it said 64 while `KARA_BOX_H` said 60 and
  neither side knew.

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
| `DRAW_ROW` (40 cells) | 49,208 | **33,456** | same, split across two frames, column-major tiles. Back up 2,448 at 8x16: a tile is two character columns, so the map is read twice as often across a row |
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

| Loop | iterations per 200 hardware frames | |
|---|---:|---|
| standing still | 200 | **locked** |
| walking right with a drone in view | 199 | one frame an encounter |
| turning round, with a drone in view | 199 | the camera's pan |
| walking right and FIRING, with a drone | 198 | the pool costs her nothing now |
| jumping and firing, scrolling | 198 | |
| climbing down the ladder | 200 | **locked** — and the view scrolling with her |
| standing on the street | 201 | **locked** |
| walking the street | 201 | **locked** |

**The two transients are named rather than hidden behind a loose
threshold.** A drone costs 17,968 T and a scrolling frame cannot carry
it, so it is a persistent sprite (§8.7) — but the frame it comes into
view on and the frame it leaves on pay whatever it costs, because what
the screen shows is not negotiable. And turning round makes the camera
pan (§8.2): a whole column every frame for about 20 frames instead of
every other one, which is a run's cost applied to a walk.
`tools/test_enemies.py` carries those two numbers as its floors and
prints the reason beside them.

A scrolling frame on her heaviest cel is **79,712 T of the 79,872
available — 160 to spare**, measured by summing every call the loop
makes. The three biggest pieces are the span blitter's draw 41,388, the
column 16,536 across its two halves, and the erase 13,524.

**That model is the pessimistic one and the in-situ count is the
authority.** It adds the worst placement of the heaviest cel to the
worst of everything else, and those do not co-occur; the loop counted
against interrupt ticks holds 50 Hz on every path in the table above,
climbing and street included. But 160 T is not headroom, and the next
thing added has to come out of the logic the way the enemies' did.

The ladder, the street and the vertical camera cost **672 T** of it
between them — `CLIMB_ENTER` on every grounded frame, `CAMERA_V` on
every frame, and `ENEMY_PICK`'s new vertical cull. `ENT_UPDATE` is the
other 2,000: it sweeps the entity table on every other frame and the
table went from nine records to ten.

#### The action sheet moved the worst case, and the row paint paid for it

The heaviest cel in the game is no longer a gun cel. Measured draw plus
erase, `kact` against `kcore`'s worst:

| cel | span bytes | lines | draw | erase | both |
|---|---:|---:|---:|---:|---:|
| `drop` 1 | 294 | 63 | 43,496 | 13,140 | **56,636** |
| `drop` 0 | 315 | 62 | 42,180 | 13,548 | 55,728 |
| `climb` 0 | 324 | 62 | 41,784 | 13,764 | 55,548 |
| `kcore` `shoot` | 324 | 58 | 41,064 | 13,380 | 54,444 |
| `die` 5, the cel she holds | 133 | 19 | 17,720 | 5,052 | 22,772 |

**`drop` 1 carries 21 span bytes FEWER than `drop` 0 and costs 1,316 T
more**, which is §7.1's per-line bookkeeping showing through: it is a
line taller and its spans group worse. Bytes alone do not order these.

A `climb` cel and a **half** of the incoming row (16,742 T) came to
72,290 before the logic, and the loop dropped **five frames in 200**
climbing — every one of them on a frame with a paint in it, measured by
counting loop iterations against hardware frames one at a time rather
than in aggregate. Splitting the row four ways (§8.2) puts a quarter at
**9,192 T** and the climb back at **200 of 200**. The heaviest case
left is a `drop` cel over a vertical step at 65,828 T before the logic,
and the two axes cannot fire together (§8.8).

It was 79,452 with 420 to spare before the enemies went in, and the
4,300 came out of the logic, not the drawing:

* **An idle pool is fourteen slots of nothing.** `BUL_LIVE` counts the
  rounds in the air and `UPDATE_BULLETS`, `BUL_DRAW`, `BUL_ERASE` and
  `ENEMY_SHOT_CHECK` return at once when it is zero — 6,000 T a frame
  for rounds that are not there. The draw and the erase must make the
  same decision on the same count, because `UPDATE_BULLETS` runs
  between them and can kill a round that still has to be lifted off the
  screen; `BUL_DREW` is that count as the draw found it.
* **And a busy pool was fourteen slots for three rounds**, which cost
  **6,228 T** of every frame she fired on and dropped 43 frames in 200
  — measured, and visible in play as a character who stops walking
  while she shoots (§8.5). `BUL_TOP` bounds the walk at the deepest slot
  ever taken, which in play is 3.
* **A cheap X reject before the real one.** `ENT_OVERLAP` looks the
  hitbox up and tests both axes, about 450 T to discover that something
  twenty tiles away is twenty tiles away. The widest row of
  `ENT_HITBOX` is 16 bytes, so one 16-bit subtract rejects nearly
  everything: `ENT_UPDATE` 3,200 -> 2,636 with nine entities in the
  level.

The next thing added has to pay for itself out of 160 T on a
scrolling frame, or be scheduled onto a frame that is not scrolling —
which is what §8.7 does with the enemies.

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
4. **`RASTER_WAIT` must credit the time already spent.** Its delay can
   only count from the moment it is entered, so a caller that arrives a
   whole tick after the one it asked for used to wait the remaining
   50-odd scanlines *on top of* however long it took to get there. That
   was harmless while the frame had room. With the action state machine
   in it, it became 13,000 T of a 79,872 T frame spent waiting for a
   beam that had gone by 23,000 T earlier, and the loop **dropped 6
   frames in 200 while scrolling** - the whole `ACT_UPDATE` is 724 T,
   so the cost was never the new code. Each whole tick late is 52
   scanlines already owed, and subtracting them is four instructions.
5. **`FRAME_TICK0` is stamped by the interrupt handler, not by the main loop.**
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

(Those were the figures the day the column was rewritten. The loop has
grown the action state machine and the entity table since; the frame as
it stands is 79,452, and `tools/test_spanblit.py` re-derives it from
the routines the loop actually calls rather than from this table.)

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

### Wiring her in: four bugs, and what each one taught

The span blitter was correct in isolation and the loop was correct with
the old sprite. Every one of these lived in the join.

1. **`SCR_ADDR` returns in `HL`, and `HL` was the frame.** The frame
   pointer has to go on the stack across the call. Assembled clean,
   composited garbage.
2. **`B` is the script pointer's high byte.** `SPAN_DO_SKIP` and
   `SPAN_BLANK`'s skip path used it as a scratch counter - it looks free,
   because the line counters are in the shadow set - and the save-under
   then went to `&0B00`, straight over the `SPAN_ENTRY` dispatch table.
   One clipped frame corrupted every frame after it. Both now keep the
   count in self-modified immediates.
3. **A span ending EXACTLY on the last byte of a 2 KB block.** Bytes
   `&FFFD-&FFFF` wrap no word, but the last `INC DE` leaves `DE = &0000`
   and `SPAN_STEP`'s `+&0800` then does not carry, so `SPR_ROW_FIX` is
   skipped and the next line is written at `&07FD` - over the core. The
   fold test treated "fits exactly" as the safe case; it is not, and it
   now takes the folded lane with an empty second half.
4. **`RASTER_WAIT` overflowed for display line 185 and up.**
   `ADD A,73-2` on a line of 185+ is 256-262, comes back as 0-6 and
   reads as tick 1, so the erase ran ~65,000 T early - it wiped her
   before the beam reached her and **she was simply absent from the
   bottom third of the picture**. A 48-line sprite could reach
   `KARA_LAST_BOT = 191` too; the camera just never put it there. 256
   scanlines is four ticks and 48 more, which is how it is put back.

And one thing that was not a bug in the new code at all: **`COL_HEAD`
had to move from 18 to 14**, because the *faster* `DRAW_COLUMN` finishes
the head sooner and a head that finishes early paints the incoming
column ahead of the beam. The split is squeezed from both sides and has
to be re-derived whenever either cost moves - the table is in
`tilemap.asm`.

**Her raster threshold did not move.** At ~576 T a line against the
raster's 256 the top border is her whole lead, and she is drawn intact
from screen line 10 down; above it the beam catches her last lines.
That is the same limit §9 recorded for the 16x48 sprite (13), because
the 24x64 one is taller but no dearer per line.
`tools/test_module4.py` now measures the threshold and asserts both
halves of it - clean below, torn above - so a slower blitter cannot
push it down the picture unnoticed.

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
* **A second span sprite drawn like the first does not fit, and no
  amount of scheduling makes it.** One `citydrone` through
  `SPAN_DRAW`/`SPAN_ERASE` is 17,968 T a frame plus 3,800 of its own
  logic, against 420 spare; the loop went from 200 iterations per 200
  hardware frames to **114**. Halving its update rate does not help,
  because the frames that *do* redraw it are still 15,428 T over. What
  works is not redrawing it: it is world-fixed, the CRTC carries it,
  and its pixels can simply stay on the screen (§8.7). **The lever was
  the frame it is drawn ON, not the cost of drawing it.**
* **77% of Kara's span bytes are fully opaque**, which looks like a
  free 30% off the composite and is not: the save-under is three of the
  nine instructions and stays whatever the mask is, so an opaque byte
  with the mask dropped from the format is 56 T against 72. That is
  4,048 T on her heaviest cel for a format change, an exporter change
  and a blitter rewrite. It is the biggest lever left on the blitter
  itself and it is still not big enough to buy an agent.
* **A pickup through the span blitter costs nine times the frame's
  headroom.** It was written — page its bank, find its cel, `SPAN_DRAW`
  with a save-under, `SPAN_ERASE` at the end of the frame — and then
  measured:

  | | T |
  |---|---:|
  | `ENT_DRAW`, one pickup on screen | 9,912 |
  | `ENT_ERASE` | 2,204 |
  | | **12,116 a frame** |
  | a scrolling frame's headroom | 1,324 |

  The reason is the entry above it, read the other way round: **the
  remedy is decided by bytes-per-line for TIME, and a pickup is four
  bytes a line.** The blitter's 168 T of per-line bookkeeping is sized
  against Kara's 64 lines of 5.7 bytes; at 4 bytes a line it is almost
  all of the cost, and sparseness cannot help because there is nothing
  to be sparse about. A 4x16 full-box blitter was costed at ~6,400 T
  and is no answer either. The frame has no room for **any** per-frame
  sprite besides her, which is why the pickups are baked into the
  tilemap instead (§8.6).

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
* **The enemy's pixels are lifted off by the refresh that replaces them
and by nothing else.** A persistent sprite has no erase at the end of
its frame, so the one place it ever comes off the screen is the top of
the next refresh — and a refresh that drew without erasing first left
the last image where it was and put another one beside it, the enemy
trailing copies of itself across the roof.
* **A table indexed with `ADD A,TABLE AND 255` must fit ENTIRELY in one
  page, not merely be aligned.** The carry is discarded, so a table that
  straddles a page boundary silently reads the wrong row — `align 32`
  put `ENEMY_TYPES` at `&17E0`, its 64 bytes crossed `&1800`, and every
  type but the first read the first one's padding: a drone came out 135
  lines tall with 23 hit points. Align to the whole table and assert
  `(TABLE AND 255) + rows * stride <= 256`. `ENT_ART` and `ENT_HITBOX`
  are indexed the same way and carry the same assert.
* **Anything that changes the BACKGROUND must run after every sprite
  has been lifted off it**, at the very end of the frame. A sprite's
  save-under was captured before the change and its erase will put the
  old bytes straight back over it — which is how a repainted tile got
  its pickup back over the twelve bytes Kara overlapped, and why both
  `ENT_REPAINT_DUE` and `ENEMY_REFRESH` are the last two calls in the
  loop.
* `LD SP,&BFFF` explicitly at startup. An SP that drifts into `&C000-&FFFF` shows up as
  random screen corruption, not as a crash.
* AMSDOS keeps its buffers around `&A700-&BFFF`, and the firmware its
  workspace at `&B100-&BFFF`. Neither matters here: the engine reads
  the disc itself (§7.5) and never calls back into either, which is
  what lets the stack sit at `&BFFF` and the buffers at `&8000`.
* Test the overscan and hardware scrolling on **CRTC types 0, 1, 2 and 4**; type
  differences bite hardest on R3/R7 timing and on start-address latching.
* **The relocated core image must end before `&4000`, and `main.asm`
  asserts it now.** It did not, and it went wrong silently: 2,240 bytes
  of map and entity table used to ride inside the image, the ladder and
  the camera pushed `CORE_END` to `&4070`, and the last 112 bytes of the
  entity table landed in bank C4 on top of the city's tile art. Nothing
  crashed and nothing looked wrong. `ENT_RECOUNT` read tile bytes as
  entity flags, reported 24 live entities instead of 10, and
  `ENT_UPDATE` swept fourteen slots of noise every other frame — 2,728 T,
  which is what took the budget over. The map and the entity table are a
  separate image now (`LEVEL_IMAGE`, `&B000`) that the bootstrap lands
  in base RAM directly: they are data, they are copied into their
  working addresses anyway, and there is no reason for them to be in an
  image with a ceiling.
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
   4. ~~the level loader~~ — done: `src/disc.asm` drives the uPD765,
      `src/unpack.asm` unpacks a bank image, and `LEVEL_LOAD` chains
      them. Every set of every level loads off a real disc image and
      comes back byte-exact, in 1.52-1.85 s (§7.5);
   5. ~~wire the span blitter in~~ — done: `src/kara.asm` pages the
      facing's bank, finds the frame, clips it to the display and hands
      the rest to `SPAN_DRAW`; the loop calls it and `SPAN_ERASE`, and
      `SCROLL_DEMO` loads level 1 off the disc first. `tools/test_kara.py`
      checks 296 placements against an independent v-model. Four bugs
      came out of it, all in §9's new entry. `png2sprite.py` and the
      16x48 path still serve the Module 1-3 screen;
   6. ~~the action state machine and its controls~~ - done:
      `src/action.asm`, seven states from one table, cel timing out of
      the art's own duration tables, the gun's two pistols driven by
      the artist's spawn points, and `tools/test_actions.py` driving
      every transition with a negative control on the entry cel. SWIM
      and SWIM_FIRE are not in it: they need level 4's water, which is
      §6's job;
   7. ~~the entity table and the five interaction handlers, with the
      AABB~~ — done: `src/entity.asm` (§8.6). The record is editor.md
      §9.2's eight bytes so module 6's loader can be an `LDIR`; the
      pickups are drawn by being baked into the tilemap, because a
      sprite path for them costs nine times the frame's headroom (§9).
      `tools/test_entities.py` checks the AABB against an independent
      separating-axis model over 1,684 swept placements, drives every
      handler twice so a key that opened two doors would fail, and
      checks the bake against an independent reading of the span
      format, on the screen, and un-baked again when she takes it. Two
      negative controls: a stamp that writes nothing fails three of its
      six checks, a missing un-bake fails the sixth;
   8. **the enemies** — done for the engine, and level 1 ships drones:
      `src/enemy.asm` (§8.7) spawns them from the entity table,
      patrols, faces her, fires on the character's own period from the
      artist's spawn points, takes her rounds and gives damage back.
      `tools/test_enemies.py` checks the type table against the
      exporter's constants, the patrol and the animation in the running
      game, the kill and the record it marks, that a skipped frame
      leaves the sprite on the screen, and that the loop still locks
      50 Hz on five input paths.

      **One enemy is on screen at a time, and that is the frame
      budget.** A `cityagent` is 40,760-48,820 T drawn and erased and
      the frame has 4,732; a `citydrone` is 17,144-19,240 and is
      affordable only because it is never redrawn on a scrolling frame
      (§8.7). The agent's row is in the type table and its art is on
      the disc; putting it on the screen needs the frame to lose about
      30,000 T, and §9 says where the remaining levers are and how
      small they are. **The level machines are not done** and are a
      separate problem: they are set pieces, loaded for one fixed
      moment, and nothing else is on screen while they are;
   9. ~~bullet-against-tile collision and the game state of §8.5~~ —
      done: both pools lift the round's screen position into the world
      and probe `TA_SOLID` through `MAP_ATTR`, and `tools/test_module5.py`
      drives it from both sides — a brick under the round kills it, sky
      does not — with a negative control that puts the brick at the
      UNCONVERTED cell and checks the round survives;
   10. ~~a way off the roof~~ — done: ladders down the building, a
      street 128 pixels below it, `TA_CLIMB` + `TA_PLATFORM` on the
      ladder tile, `KST_CLIMB`/`KST_HANG` out of the `kact` blob, and
      `CAMERA_V` — the first thing but a test to drive §8.2's vertical
      axis. `tools/test_climb.py` drives all of it from the joystick and
      carries a negative control. See §8.8;
   11. ~~the rest of the action sheet~~ — done: `climb_turn`, `drop` and
      `die` are states of §8.4, the back-view `climb` is stored once and
      drawn from the right-facing blob whichever way she faces (§7.1),
      and the incoming row is painted in four pieces because the new
      cels are heavier than the gun's (§8.2, §9). What that cost the
      memory map is §6.2: a level with no ladder carries no `climb`, and
      the two characters who never move carry one facing;
   12. `tools/test_module5.py` — started, with the bullet/tile checks in
      it. It still owes the rest of the module.

   **What the action sheet needs that does not exist yet**: there is no
   `hurt` state, no respawn and no game over. `die` is chosen from
   `PLAYER_HP == 0` and holds its last cel for ever, which is the hook
   the level FSM (step 8) plugs into; `use` and `hurt` are exported and
   nothing plays them. **And a deadly fall is not a thing the engine
   knows**: `drop` ends in `idle` however far she fell, because there is
   no fall damage to turn it into a `die`.
6. **The level format, engine side** — 8×16 tiles and a 20×11 play
   area (§8.3), which is a rewrite of `tilemap.asm`'s addressing and of
   `collide.asm`'s probes, then a reader for `level_<n>.lvl` and
   `tileflags_<level>.bin`, then one hand-built level played end to
   end. **The masked tile path of §7.3 belongs here too**, with whatever
   the map format grows to say which cell is an overlay over which — the
   art has 34 overlay tiles across three levels and the engine has no
   way to draw one. `tools/make_level.py` writes the same bytes the editor will, so
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
