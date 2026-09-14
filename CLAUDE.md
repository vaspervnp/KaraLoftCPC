# CLAUDE.md — Kara Loft and the Illuminati (Amstrad CPC 6128)

Z80 assembly game for the Amstrad CPC 6128. The design document is [plan.md](plan.md)
(written in Greek); this file holds the technical contract that code must satisfy.
**Where this file and plan.md disagree, this file wins** — see §11 for the specific
corrections and why.

## 1. Status

Pre-code. The repository contains only `plan.md` and no commits yet. There is no
`src/`, no build script, and no assets. Module 1 (§10) creates the skeleton.

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
| Aseprite | **not available** — no CLI and no MCP server is connected | see §6.2 |

RASM can emit the DSK itself via a `SAVE "GAME.BIN",start,length,AMSDOS,"kara.dsk"`
directive, which is usually simpler than post-processing with iDSK. Use iDSK when you
need to inspect or patch an existing image:

```bash
iDSK kara.dsk -l
```

Typical two-step build if you prefer explicit control:

```bash
rasm src/main.asm -o build/game && iDSK build/kara.dsk -n && iDSK build/kara.dsk -i build/game.bin -t 1 -c 4000 -e 4000 -f
```

`-t 1` = binary, `-c` = load address, `-e` = execution address, `-f` = overwrite.

## 4. Test loop — always verify in the emulator

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

## 5. CPC 6128 hardware reference

### 5.1 Memory map (base 64 KB)

```
&0000-&003F  Z80 restart vectors + IM 1 interrupt handler
&0040-&3FFF  Core engine, scrolling engine, sound driver      (never banked out)
&4000-&7FFF  Level logic, collision data, entity management   (BANKED WINDOW)
&8000-&BFFF  Sprite buffers, background restore buffers, temp (never banked out)
&C000-&FFFF  Primary video RAM
```

### 5.2 Banking (gate array port `&7Fxx`)

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

### 5.3 Mode 0 pixel encoding — VERIFIED

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

### 5.4 Screen addressing

Standard (non-overscan) layout, 80 bytes per line, base `&C000`:

```
addr = base + (line & 7) * &0800 + (line >> 3) * 80 + x_byte
```

Advancing one scanline inside the blitter:

```asm
                ld   bc,&0800
                add  hl,bc          ; next scanline within the char row
                jr   nc,.same_row   ; crossed the 8-line boundary?
                ld   bc,&C050       ; +&C050 wraps to the next char row
                add  hl,bc
.same_row:
```

### 5.5 Overscan title screen (192×272)

CRTC registers. **One CRTC character = 2 bytes**, so R1=48 gives 96 bytes/line:

| Reg | Value | Meaning |
|---|---|---|
| R0 | 63 | horizontal total (64 chars) |
| R1 | 48 | horizontal displayed → 96 bytes/line → 192 Mode 0 pixels |
| R2 | 50 | horizontal sync position |
| R6 | 34 | vertical displayed → 34 × 8 = 272 scanlines |
| R7 | 35 | vertical sync position |

96 bytes × 272 lines = **26,112 bytes**, which is why the buffer spans two banks.
plan.md's "48 chars × 4 bytes = 192 bytes" is arithmetically wrong but arrives at the
correct 192-pixel width and the correct 26,112-byte total; use 96 bytes/line.

### 5.6 Palette and fades

Gate array port `&7F00`: write `&00-&0F` to select a pen (`&10` for border), then the
hardware colour value. Fades walk each pen through a luminance-ordered ramp toward
black and back; keep the ramp as a table, not as arithmetic on colour codes.

### 5.7 AY-3-8912

Accessed through PPI port A (`&F4`) with control on `&F6`. Register set: R0-R5 tone
periods, R6 noise period, R7 mixer, R8-R10 channel volumes, R11-R13 hardware envelope.
The music player runs from the 50 Hz interrupt. Channel C is the SFX carrier: gunshots
and hurt sounds steal it via the noise generator and volume envelope, then hand it back
to the music without a re-trigger click.

## 6. Asset pipeline

### 6.1 Sprites

Kara Loft is 16×48 pixels → 8 bytes wide × 48 lines.

```
data frame : 8 × 48 = 384 bytes
AND mask   : 8 × 48 = 384 bytes
total      : 768 bytes per frame
```

Mask convention: **`&F`-nibble set (1) where the background shows through, 0 where the
sprite pixel is opaque** — i.e. the mask is ANDed with the screen, then the data is ORed:

```
SCREEN = (SCREEN AND MASK) OR DATA
```

Because Mode 0 packs 2 pixels per byte, mask nibbles are per-pixel, not per-bit: a
transparent pixel contributes `&F` in its interleaved bit positions.

Sprites are emitted as raw binaries for `INCBIN` (`kara_sprites.bin`).

### 6.2 Aseprite is not available

plan.md assumes an Aseprite MCP server. Nothing on this machine provides Aseprite.
Until that changes, write the sprite encoder as a **standalone Python script** that
reads PNG sheets (Pillow is installed) and emits the data+mask binary. That keeps the
pipeline working and stays trivially portable to Aseprite later.

### 6.3 Blender

Blender is reachable through the MCP tools, not a CLI. Title-screen renders use an
orthographic camera at 192×272, quantised to 16 pens chosen from the CPC's 27 hardware
colours, then laid out into the overscan VRAM order and written as `overscan.bin`
(26,112 bytes). Inspect the scene before changing it; do not assume object names.

## 7. Game architecture

### 7.1 Level flow

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

### 7.2 Scrolling

* **Horizontal** — CRTC hardware scroll via R12/R13, coarse steps of 2 bytes
  (4 Mode 0 pixels). Each step refreshes one tile column at the incoming edge.
* **Vertical** — CRTC start-address offset by whole lines. Levels 3 and 4 use opposite
  directions; level 4 additionally applies upward buoyancy each frame unless the player
  swims down.
* Both update the start address **only after `HALT` / VBLANK sync** to avoid tearing,
  and both must handle seamless wrap-around of the 16 KB VRAM window.

Tiles are 16×16 pixels = 8 bytes × 16 lines. Tilemaps live in banked RAM.

### 7.3 Dual pistols

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

### 7.4 Game state

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

## 8. Performance budget

A frame is **79,872 T-states**. Allow ~25% (≈19,900 T-states) for drawing Kara plus
background restore plus 14 bullets; the remaining 75% covers scrolling, tile refresh,
collision, AI, and the music player.

Count T-states in comments on any loop that runs per-scanline or per-entity. Remember
the gate array rounds instruction timings up to whole microseconds, so the practical
throughput is nearer 3.3 MHz than 4 MHz — measured frame counts in the emulator beat
hand-counted totals when the two disagree.

## 9. Conventions and pitfalls

* Hex is `&` prefixed (RASM/CPC style), not `0x`.
* Labels `SCREAMING_SNAKE`, local labels `.dotted`.
* Prefer `EXX` / shadow registers over push/pop in inner loops; document which shadow
  set a routine clobbers, since the interrupt handler uses them too.
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

## 10. Module order

Build strictly in sequence; each module must assemble **and run in the emulator** before
the next one starts.

1. **Memory architecture + build pipeline** — `main.asm`, bank switching, `build.sh`,
   BASIC loader, `.dsk` generation.
2. **Asset exporters** — Blender → `overscan.bin`, PNG → `kara_sprites.bin` (§6.2).
3. **Sprite blitter + dual-pistol bullet pool** — masked 8×48 blit, `FIRE_BULLET`,
   `UPDATE_BULLETS`.
4. **Scrolling engine** — horizontal CRTC scroll and both vertical variants.
5. **Objects, puzzles, NPCs** — inventory, interaction handlers, AABB.
6. **Level FSM + cutscenes** — transitions, raster-interrupt water rise, palette fades.
7. **Audio** — `audio_pipeline.py` (ffmpeg → 3 channels), AY player in the 50 Hz
   interrupt, Channel C SFX priority.

## 11. Corrections to plan.md

Consult this list before implementing from the plan:

1. **Mode 0 bit table (§4.2)** — wrong; pen bits 0↔3 and 1↔2 are swapped. Use §5.3
   above, which was verified on the emulator.
2. **Overscan byte count (§4.3)** — a CRTC character is 2 bytes, not 4. R1=48 yields
   96 bytes/line, not 192. The resulting 192-pixel width and 26,112-byte total are
   correct.
3. **"19,968 T-states" (§6.1)** — 19,968 is the frame length in *microseconds*
   (312 × 64), not a T-state budget. The frame is 79,872 T-states; the intended ~25%
   sprite budget is ≈19,900 T-states.
4. **Aseprite (§5 Module 2)** — not installed and no MCP server for it; use a Python
   PNG encoder instead.
