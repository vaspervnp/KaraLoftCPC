# CLAUDE.md — Kara Loft and the Illuminati (Amstrad CPC 6128)

Z80 assembly game for the Amstrad CPC 6128. The design document is [plan.md](plan.md)
(written in Greek); this file holds the technical contract that code must satisfy.
**Where this file and plan.md disagree, this file wins** — see §11 for the specific
corrections and why. The same holds for [docs/editor.md](docs/editor.md),
which now carries its own §0 of four corrections this file forced (§8.3).

## 1. Status

**Modules 1-4 done, Module 5 all but its last test, and Module 6
started: the engine reads `level_1.lvl` and `tileflags_level1_city.bin`
off the disc (6a), the level's overlay tiles are composited into the
tileset at build time rather than masked at run time (6b, §7.3), and
her health is on the screen — six cells at the bottom left, her fourteen
rounds straight after them and a digit for the spare magazines,
rewritten wherever the view goes (6c, §7.8). The playfield is the drawn art.** Tiles are 8x16 (§8.3) and come off the disc with the rest
of the level. `./build.sh` regenerates the assets,
assembles, and produces `build/kara.dsk`. It boots, relocates, passes its bank
self-test, runs Kara walking and firing over a striped background with full
save-under restore, and then hands over to the scrolling city: a tilemap in bank
C4 moved by the CRTC start address, horizontally and both ways vertically, with
Kara drawn over it from keyboard or joystick input, walking, jumping and
colliding with the tiles, and the camera following her. **The loop holds
50 Hz standing, walking and on the street, and drops frames where §9's
table says it does** — firing past a drone, climbing, and running, which
is the fastest thing the frame can carry. **A play-test reported the
run's flicker and the answer was in the logic, not the drawing**: the
touch sweep takes one frame in four instead of one in two, and which of
the two odd phases it takes was worth more than the quartering (§9).

**AND THE LEVEL EDITOR HAS STARTED, FROM THE EXPORTER RATHER THAN FROM A
SCREEN.** `editor/` is a .NET 10 solution — a Domain, an Assets library, an
Exporters library and an xUnit suite — and what it does today is read
`build/level_1.lvl` and write it back **byte for byte**, bake level 1's ten
overlay pairs into the same `citytiles.bin` the build ships, and emit the
same 51 bytes of tile flags. `tools/test_format.py` then loads the editor's
own file on the emulator and passes all 21 of its checks. The golden file
§11 step 7 was waiting for now runs both ways (§8.3).

**AND THE TILES COME OFF THE ARTIST'S SHEET NOW, NOT OUT OF THE BUILD'S
OWN OUTPUT.** The editor imports the asset package — the PNG, its frame
boxes, the names in `tile_table.json` and the draw table — quantises it
against `src/palette.asm`'s sixteen pens and packs it column-major, and
**level 1's 41 tiles come out as the first 2,624 bytes of `citytiles.bin`
exactly**. That is not a new comparison so much as an honest one: until the
import existed those 41 tiles were *taken from* the blob they were checked
against, so only the ten baked ones were really under test. All 51 are now,
and the importer reads all nine tile sheets of all six levels — 275 tiles,
34 overlays, which is §7.3's own table. What is left is the painter.

**`RUN"DISC` opens on the title picture and then starts on the
rooftop.** The core boots, self-tests its banks, puts the artist's
160x200 screen up off the disc with KARA LOFT baked into it, loads
level 1 underneath it, blinks PRESS SPACE OR FIRE on the pavement, and
goes to the city on the press (7.7). **The Module 1-3 acceptance screen has been deleted** — colour
bars, the bank verdict, the stripes, the liveness lamps and the 16x48
placeholder blitter that drew a stand-in heroine over them. It was the
only caller of `sprite.asm`'s masked blitter, of the sheet
`png2sprite.py` exported and of the coloured border bands, and all of
that has gone with it: 4,625 bytes of core image, two tools and two
suites. What it proved is still checked, in the game rather than on a
screen of its own — `tools/test_module1.py` reads `BANK_TEST`'s own
verdict bytes instead of five green blocks.

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

**The roof is open at three tiles**, `ROOF_GAP`, so the fall is
something a player can walk into rather than a state only a test can
reach — and it is put where no other suite's walk goes, because a hole
in front of a scrolling test turns it into a falling test without
failing it (§8.8).

**The border flashes red for four frames when she is hit**, because
there is no HUD yet and a static one over a scrolling screen needs a
raster split the frame cannot pay for — §9 has the measurement and §8.3
the plan.

**And there is a third way off the roof.** DOWN at the lip and she
crouches, takes hold of it and hangs off it on the `hang` cels; let the
key up and she pulls herself back in 40 frames, press it again inside
them and she lets go (§8.8).

**She can crouch**: DOWN on its own, on her feet, plays the roll's
first cel and holds it — and takes 23 lines off the top of her hitbox,
so a drone's shot goes over her (§8.4). **And a drone she kills falls
out of the sky flashing** instead of vanishing on the frame the shot
landed (§8.7).

**And she can jump it.** `P_COYOTE` gives her six frames of edge after
the ground has gone, which takes the take-off window from 8 frames to
14 and is the difference between a gap and a wall with a longer
animation (§8.4). **The street runs past the garage**, which was four
solid tiles across a pavement she is three tiles wide on (§8.8), and
**stopping on a ladder holds the climb cel** she stopped on instead of
playing two side-on `hang` cels in the middle of a back view (§8.4).

**Aiming plants her**: SPACE down and she turns but does not walk
(§8.4). **And the border is black** — the coloured profiling bands
belong to the development screen (§9). **A drone coming into view no
longer costs her a frame**, which on this loop is not a stutter but a
frame with no heroine in it (§8.7).

**THE LAND SHEET WAS REDRAWN AND THE FRAME PAID FOR IT.** Her heaviest
`kcore` cel went from 284 span bytes to 323 — 2,808 T of composite at
the blitter's floor — and `kcore` from 11,328 bytes to 12,290, which
took level 2 over five banks until the artist pulled 3,008 bytes out of
the forest's wolf and boar. The T-states were not paid back: firing
while she moves now drops frames where it did not, and every floor in
`tools/test_enemies.py` and `tools/test_module5.py` is the new
measurement with the reason beside it. §9 has the table and the one
lever that would buy it back.

**AND THEN THE WALK WAS HALVED AND THE REDRAW WAS PAID FOR.** She
covered 2 Mode 0 pixels a frame and crossed the display in a second and
a half; the artist's walk cycle is 40 frames and plants her feet 18
pixels of ground apart, so the engine was carrying her 80 and she skated
four fifths of every step. She steps a byte on one frame in two now, the
cycle is halved to match (§8.4's `KARA_RATE`), and because the camera
then steps on one frame in four instead of one in two **every loop count
in §9 came back**: firing past a drone 173 → 194 of 200, jumping and
firing 158 → 191.

**SHIFT RUNS HER, AND UNTIL NOW IT COULD NOT.** `input.asm` read row 2
bit 6, which is `\`, where SHIFT is bit 5 — so the run state, its cels
in `kextra` and its step existed and nothing in the game could reach
them. A run is a byte a frame, twice the walk; it is **not** the CRTC's
whole character, because a column of tilemap every frame is 107 loop
iterations in 200 — 25 Hz — and at a byte a frame it is 172 (§8.2, §9).
**The roof's gap is a run-jump now**: the 15-frame arc carries 15 bytes
at a run and 7 at a walk, against a 12-byte hole (§8.8).

`./tools/run_tests.sh` runs every acceptance suite and **all seventeen
pass again.** Eighteen checks in four of them did not, and how they
divide is the part worth having written down: **fourteen were suites
that had not caught up with a decision the engine already made, and four
were a report that the game HAD got worse** — which is exactly why a red
suite is dangerous rather than merely untidy. The real finding was
sitting among the stale ones and nobody could see it.

| suite | checks | what it was |
|---|---:|---|
| `test_module4.py` | 8 | **the display's top scanline, found two lines out.** `find_display_top` scored its guesses over the top 24 lines of the picture, and those are the night sky: one flat pen, so an offset two scanlines wrong scored exactly as well and the search kept the lowest of the plateau — reporting "256 of 256 probes matched" while doing it. Every rendered check then compared the picture against a model two lines up: 8,600 wrong pixels of 30,720 on a build whose picture was correct. It scores the whole 192 lines now and asserts the MARGIN to the runner-up, so a plateau is a visible fact |
| | | ... and three more: the model did not know about the inventory group (96 bytes, to the byte); the Kara-position check paired the picture with the wrong frame's `KARA_Y`, because `PLAYER_TO_SCREEN` moved to the end of the second sweep (§7.8); and the horizontal step was measuring the camera's vertical catch-up, which is half again as fast now that a row step is two game frames |
| `test_module5.py` | 5 | **a round steps four bytes and the suite expected two** — §9's own table of what 25 Hz cost, read off `BUL_SPEED`/`EBUL_SPEED` now instead of written down. And three floors counted in 50 Hz frames, re-derived: firing costs nothing at all with the strip silent, the frames she spends planted are counted off `INPUT_NOW` rather than halved out of the tap pattern, and `BUL_TOP` forced to `BUL_MAX` costs frames but no longer costs ground, because 5,408 T of overrun fits in a 25 Hz frame |
| `test_enemies.py` | 4 | **the inventory group, and this one was real.** See below |
| `test_climb.py` | 1 | a jump twelve frames early used to end inside the roof's gap; at 25 Hz speeds it ends short of the near lip and she lands back on the roof. The early end of the window is searched for now instead of written down — it is four frames |

**AND THE ONE THAT WAS NOT A STALE FLOOR: THE INVENTORY GROUP COST A
GAME FRAME, AND IT HAS BEEN PAID.** Measured over all seven of
`test_enemies.py`'s paths with `HUD_INV` poked to `RET` as the control,
walking right, jumping-and-firing and running right were **99 game
frames in 200 hardware frames with the six cells and 100 without
them**, and running-and-firing 97 against 98. **All four are back**, and
what took them back was not the drawing: the inventory's LAYOUT moved
to the second sweep, where the head gate is idle for 40,468 T; its copy
became the health bar's own unrolled `LDI` run instead of a second pair
of `LDIR`s; and — the last two frames, and the surprise — **a pickup's
repaint stops disowning the whole strip's layout when it cannot reach
it.** Six of the seven paths are 100 of 200 now with the strip in them
and `HUD_SERVICE` poked out changing nothing on any of them; the
seventh is the run with the gun at 98 either way, which is its own
cels. §7.8 has the measurements, including the one that settled it: a
delay of a KNOWN length in `HUD_INV`'s place, which cost the frame at
484 T and at 2,884 alike — so no cheaper copy could ever have bought
it.

The frame budget is asserted where
it can be measured now, and that is a change worth knowing about. The
pessimistic sum of every call the loop makes is **87,328 T of 79,872 on
her heaviest cel**, over by 7,456, because it adds worsts that do not
co-occur; what says whether a frame holds is the count of loop
iterations against interrupt ticks, and every path
`tools/test_enemies.py` and `tools/test_climb.py` drive carries its own
floor with the reason beside it — 201 standing, 198 walking, 191 firing
past a drone, 193 climbing and 160 running. The span
blitter is at its floor and `DRAW_COLUMN` was rewritten from 71 T a byte
to 43; the incoming ROW is painted in four pieces rather than two,
because the action sheet's cels are heavier than the gun's. The numbers
are in §9.

```
src/main.asm      bootstrap at &4000 + core engine at &0040
src/config.asm    ports and memory map constants
src/bank.asm      bank switching (must stay outside &4000-&7FFF)
src/screen.asm    Mode 0 addressing, block fill, palette, vsync
src/palette.asm   the 16 pens + solid-pen byte table
src/sprite.asm    where a pixel IS: the address model and the line
                  stepping every blitter shares
src/bullets.asm   dual pistols, 14-round pool, reloading
src/spanblit.asm  the span-compressed blitter and its erase script
src/unpack.asm    ZX0 into a bank, into VRAM, and LEVEL_LOAD
src/intro.asm     the title picture and its blinking prompt (7.7)
src/hud.asm       the energy bar, redrawn wherever the view goes (7.8)
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
disc/disc.bas     ASCII BASIC loader - straight into the game, and what
                  every suite runs
build/kara.bas    ... and the PLAYER's one, generated: the label screen
                  first, then the same load (7.9)

editor/                    the level editor (§11 step 7), C# / ASP.NET Core
  src/...Domain/           the model: the level, the entity record, the tile
                           and its flags, and Mode 0's bit interleaving
  src/...Assets/           the artist's package in: a PNG decoder with no
                           package behind it, the palette out of palette.asm,
                           and the tile sheets of all six levels
  src/...Exporters/        level_<n>.lvl, tileflags_<level>.bin, and the
                           build-time bake of the overlay pairs
  tests/...Tests/          xUnit, against build/'s own golden files

tools/cpclib.py            Mode 0 encoding, palette, screen layout - the one
                           place the bit interleaving is written down
tools/aseprite2spans.py    Aseprite sheet+JSON -> span-compressed bank
tools/spawns.py            projectile spawn points -> build/spawns.inc
tools/pack.py              ZX0 for everything that goes on the disc
tools/build_levels.py      the level art packages -> blobs, and which of
                           them get a second facing
tools/level_banks.py       blobs -> bank images -> one ZX0 stream each
tools/dskdata.py           those streams onto the disc as raw sectors
tools/png2screen.py        image         -> overscan.bin / 16K screen
tools/make_intro.py        the title .scr -> the CRTC's screen order,
                           packed, plus its palette and the prompt (7.7)
tools/make_hud.py          the artist's health cells -> Mode 0 bytes
tools/make_loader.py       the label screen's palette note -> kara.bas,
                           the disc's front door (7.9)
tools/make_city_map.py     the City's 128x16 map, over the DRAWN tiles,
                           and the build-time bake of its overlay tiles
tools/make_level.py        that map + the entity table -> level_1.lvl,
                           the reference implementation of editor.md 9.2
tools/blender_title.py     the title scene and its CPC render settings
tools/bench.py             T-states by calling a routine from a DI stub
tools/test_climb.py        the ladder, the street and the vertical camera
tools/test_intro.py        the title screen, its palette and the press
tools/test_hud.py          the energy bar, and that it STAYS put
tools/test_loader.py       RUN"KARA: the label screen in video RAM, and
                           the hold from both ends
tools/test_format.py       the level file, the engine's reading of it,
                           and the overlay bake
tools/test_*.py            acceptance suites, seventeen of them
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
| Hardware frame | 312 scanlines × 64 µs = 19,968 µs = 79,872 T-states @ 50 Hz |
| **Game frame** | **two of them — 159,744 T @ 25 Hz** (§9) |

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
| .NET SDK | `/home/vasilhs/.dotnet/dotnet` — **not on PATH**, call it by full path | 10.0.400, for `editor/` (§11 step 7) |

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
| 1 city | 74,184 | 5 | 19,174 | 487 |
| 2 forest | **80,225** | 5 | 21,297 | — |
| 3 cave | 77,003 | 5 | 20,740 | — |
| 4 undersea | 67,588 | 5 | 17,700 | 1,074 |
| 5 desert | 77,113 | 5 | 19,406 | 2,101 |
| 6 station | 71,839 | 5 | 18,792 | 1,255 |

**Five banks, not four.** The window shows bank 1 as well as 4-7, so
there are 81,920 bytes of art storage — 80,896 after the bake reserve
above — and **every level now needs all five.** That puts the "level
logic, collision data, entity management" of §6.1 into `&8000-&BFFF`
instead, which has 14 KB free after the save-under buffers.

**The heroine is two thirds of it.** `kcore` and `kcore_l` are 12,290
each, `kextra` and `kextra_l` 7,435, `kact` 11,229 and `kact_l` 8,507:
**59,186 bytes before a level has drawn a single tile**, and 671 is all
the room level 2 has left after them. The action
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
  action blob 2,722 bytes shorter, with every frame they DO get at the
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
where the feet have to keep up with the ground she covers — see
§8.4's `KARA_RATE`, which is the other half of that.
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
| `hang` | 2 | y=64 | 240 | loops | yes — **and nothing plays it** |
| `use` | 2 | y=128 | 140, 220 | once | yes |
| `hurt` | 2 | y=192 | 90, 130 | once | yes |
| `climb_turn` | 1 | y=256 | 120 | once | yes |
| `drop` | 2 | y=320 | 100 each | loops | yes |
| `die` | 6 | y=384 | 90,120,130,160,110,600 | once, then **holds** | yes |

**`hang` IS A LEDGE, NOT A LADDER, AND NOW IT HAS ONE.** It was the
state for standing still on a ladder and that was wrong twice over.
The old cels were SIDE ON in the middle of a back view, so she stopped
climbing and turned to face the player without moving a pixel — the
same cut `climb_turn` exists to avoid. And the artist has since redrawn
them as what the tag is actually for: **the hands grip an edge in FRONT
of her and above her, in the direction she faces, and the body hangs
below it alongside the wall** — a roof edge or a ledge, not a rung. The
two cels are the body swaying while the hands stay put. So stopping on
a ladder freezes the `climb` cel she stopped on (§8.4), and `hang` is
what DOWN at the lip of a floor plays — §8.8's ledge, which is the
mechanic it was drawn for.

**Its anchor is written down here because a ledge-grab will have to line
up with it**, and because it is now identical in both cels — the half
pixel frame 5 used to drift is gone, and any compensation for it must
go with it. Read off the shipped sheet, in Mode 0 pixels from the
frame's left:

| | |
|---|---|
| the near hand's grip, centre | column 11, line 5 — the same in both cels |
| the ledge's top surface | line 6 |
| where the building's wall may start | column 12 and right; below line 9 no part of her is in it (checked over both cels: 0 pixels) |
| the body | columns 1..12, not centred, because the arms reach forward |

Mirrored like every other side-on cel: column c becomes 23 − c, so the
grip is column 12 and the wall runs left from column 11 — **which is
why hanging off a RIGHT-hand lip is the mirrored cel**: the building is
to her left there, and she turns her back on the drop. Letting go is
`drop`; climbing back over the edge is the same 58 lines in reverse
(§8.8).

**`drop` was redrawn in the same box** — a thinner braid, in an arc, and
the body one Mode 0 pixel further right inside the frame. The artist
offers a −1 column while it plays to cancel that and **the engine cannot
spend it**: `KARA_X` is a BYTE column and a Mode 0 pixel is half a byte,
so the smallest step the blitter can take is two of them. It does not
need to. Measured on the shipped sheets, the opaque centroid of the two
`drop` cels moved from 10.66 / 10.97 to **11.79 / 12.09**, against
`idle` at 11.51 and `walk` at 11.16-11.63: the new cels sit CLOSER to
the states she leaves the ground from than the old ones did. And
`jump` → `drop` is not a transition this engine makes — `KARA_FELL` is
cleared for the whole of a jump arc (§8.4) — so the cut the note is
about is walk → drop, and it is now within half a pixel.

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
  11,229 bytes, `kact_l` is 15 and 8,507;
* the exporter emits `KACT_TWO_FACED`, and `src/kara.asm` puts it in
  the `KARA_SETS` row: **a frame at or past that number is drawn out of
  the right-facing blob whichever way she is facing**, at 18 T against a
  second frame table, a second duration table and 2,722 duplicated
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
and is 2,722 bytes smaller. After `drop` and `die` joined the sheet
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
| `kcore.bin` / `_l` | idle, walk, jump, shoot_draw, shoot | 12,290 | 4,094 |
| `kextra.bin` / `_l` | run, roll | 7,435 | 1,514 for the pair |
| `kswim.bin` / `_l` | swim, swim_shoot | 6,538 | 3,308 for the pair |
| `kact.bin` | hang, use, hurt, climb_turn, drop, die, **climb** | 11,229 | 5,155 |
| `kact_l.bin` | ... the same minus `climb`, which is a back view | 8,507 | 7,877 |

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
| `kcore` idle/walk/jump/shoot | 12,290 B | 24,580 B — two banks |
| `kextra` run/roll | 7,435 B | 14,870 B — one bank |
| `kswim` | 6,538 B | 13,076 B — one bank |
| `kact` the actions | 11,229 B | 19,736 B — the back view is not doubled |

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

**That convention is the SPAN format's** (above) — `png2sprite.py`, the
full-box exporter that also wrote it, went with the Module 1-3 screen
it fed. Sprites are quantised against the pens in `src/palette.asm`,
not against their own image, so they match the level they are drawn
over.

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

**AND THE SHARED SET IS NOT ALLOWED TO BE SPLIT, WHATEVER IT
MEASURES.** The engine addresses Kara by constant — `KARA_SETS` names
one blob and one frame table per set (`src/kara.asm`), `KARA_ANIMS`
names a frame number in it, and `level_banks.py` pins all of them at the
same address in every level. A tag split turns `kcore.bin` into seven
files and takes that name off the disc, **and nothing says so**: the
build carries on, the level packs, and the game draws out of a bank with
no heroine in it.

It has happened once, and it is why the rule is written down. The artist
redrew the land sheet and `KCORE` went from 11,328 bytes to **12,290 —
two bytes past the 12 KB limit**; the build was clean and the only sign
was `tools/test_spans.py` reporting 1,219 wrong pixels in 18 of 18
frames, which reads like a broken exporter and is a missing file. A
shared blob over 12 KB is now fine and a shared blob over **a whole
bank** is an error with the blob's name in it.

**The redraw is also where the twelfth colour came in.** Her land sheet
carried eleven and now carries twelve: `(255,0,0)`, 40 pixels of it,
which lands on **pen 3** at a distance of 14.3 with nothing else near it
— so §7.1's warning that "the next new colour costs a used one" has not
been called in yet, and the one after it will be. Measured over the
whole sheet, every one of the twelve still has a pen to itself.

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
thing the MCP server would have produced. `aseprite2spans.py` reads the
JSON for the frame boxes and the tags rather than assuming a grid, so
re-exporting with different frame counts needs no code change — and
`meta.frameTags` is what it reads, never the filename.

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

**The mask column is what a masked path WOULD store, and nothing
stores it.** Level 1 spends 640 bytes on 10 composited tiles instead of
704 on masks, and pays nothing per frame for them — the next section.
The number to watch is not the mask size but how many distinct
(overlay, background) PAIRS a level places: the masks are per tile and
the composites are per pair, so a lamp post down a whole wall of four
different bricks is four tiles, not one.

#### THE ENGINE HAS NO MASKED TILE PATH AND IS NOT GETTING ONE — THE OVERLAYS ARE BAKED AT BUILD TIME

`DRAW_COLUMN`, `DRAW_ROW` and `DRAW_CELL` are plain copies and they
stay that way. The masked path was Module 6's job on paper; measured
against what it would buy, it is the wrong trade:

| | |
|---|---:|
| `DRAW_COLUMN`, one character cell of the incoming column | **669 T** |
| the same cell masked, at the 2-3x this section's table quotes | 1,338-2,007 T |
| a scrolling frame's headroom (§9) | **3,548 T** |

So two overlay cells in one column is the whole budget, and the column
is repainted every character step. **The composite does not change
between frames** — an overlay tile and the tile under it are both
scenery — so it is done ONCE, at build time, exactly like the pickups
of §8.6 and for the same reason.

`tools/make_city_map.py` routes every overlay placement through
`put_overlay(x, y, over, under)`, which records the pair; `bake_overlays()`
then composites each distinct pair out of the artist's sheet — the
overlay's pens where they are not 0, the background's where they are —
appends the result to `citytiles.bin` as a new tile, and remaps the map
cells to it. The baked tile inherits the BACKGROUND's tile flags, because
what the cell does is what it did before something was drawn on it.
`build/city_baked.json` is the record, and `tools/test_format.py`
recomposites every pair independently and compares the blob byte for
byte.

| | |
|---|---:|
| pairs placed in level 1 | 11 |
| baked into new tiles | **10**, 640 bytes of bank C4 |
| dropped — the composite came out byte for byte the overlay | 1 (`tank_10`) |
| per frame, for ever after | **0** |

**`far_fill` IS NOT ALL BLACK, so the roof props were not right by
accident after all.** It carries 4 lit pixels of its 128, and this
section used to say the props over it "come out right". Composited,
`ac_unit` recovers 3 of them, `chimney` 4 and `antenna` 3 — small, and
the point is that the old rule ("an overlay may only be placed over
black") was being satisfied by a tile nobody had counted. What the bake
recovers, per pair, measured:

| pair | pixels of 128 |
|---|---:|
| `lamp_pole` over `brick` | **84** |
| `lamp_top` over `brick_win_lit` | **64** |
| `tank_00` over `far_step` | 42 |
| `tank_01` over `far_block` | 40 |
| `tank_21` over `ac_unit_on_far_fill` | 35 |
| the three roof props over `far_fill` | 3, 4, 3 |
| `tank_11`, `tank_20` over `far_fill` | 2, 2 |
| | **279** |

**An overlay can stand on a BAKED tile**, which is the water tank's
top-right corner over the air-conditioning unit: the pair's `under` is
another composite, so the bake resolves recursively and so does the
test. That is also why the sidecar records `under` after the remap and
not before.

**What this does NOT solve is the format question.** The map still
carries one byte a cell and that byte is now the composite's index, so
`level_<n>.lvl` still has nowhere to say "this cell is an overlay over
that one" — the pairing lives in the generator and dies there. A level
editor that lets a designer drop a lamp on a wall has to either write
the composite itself or grow the format a layer (§11 step 7). The
engine's rule is unchanged and now enforced by construction rather than
by care: **a map cell is a finished tile; nothing is drawn over
anything at run time.**

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

### 7.7 The title screen, and the layout the artist's `.scr` is NOT in

`assets/intro/intro_cpc_mode0.scr` is the picture the game opens on:
160x200 Mode 0, the artist's own sixteen inks, 16,000 bytes. **Those
bytes are 200 lines one after another and a CPC screen is not laid out
that way.** Line L lives at `(L AND 7) * &800 + (L >> 3) * 80` (6.4), so
200 lines of it span **16,336** bytes across eight interleaved raster
blocks — which is also why 16,000 could never have been a screen. Loaded
straight to `&C000`, as the `INTRO.BAS` shipped beside it does, the
picture comes out in eight bands.

`tools/make_intro.py` does the conversion, checks it against the `.png`
the same export produced, and ZX0-packs the result: **16,336 -> 2,473
bytes, five sectors and one read.** It goes on the disc as raw sectors
with the level data (7.5) and `src/intro.asm` unpacks it **straight into
video RAM** — there is no bank to stage it through and no reason for
one, because nothing else is on the screen while the title is up.

**The picture goes up BEFORE the level loads and the prompt AFTER**, and
that order is the whole design:

```
CORE_ENTRY -> BANK_TEST -> INTRO_SHOW   picture on screen, 0.2 s
                        -> LEVEL_LOAD   1.6 s, interrupts off (7.5)
                        -> INTRO_WAIT   PRESS SPACE OR FIRE, blinking
                        -> PALETTE_SET  back to the game's sixteen
                        -> SCROLL_INIT  and she is on the roof
```

A prompt put up first would be a lie for a second and a half: nothing
can be pressed during `LEVEL_LOAD`, which runs with interrupts off. Put
up after, it means what it says — the press starts the game on the next
frame.

**And the credit is baked like the title, for the same reason.**
`REVIVE8BIT - 2026 - VASPER` sits under her feet and does not blink, so
it goes into the picture before it is packed and costs nothing at all —
not a byte of the core image and not a T-state. **Where it goes was
measured**: counted pen by pen off the artist's own `.scr`, the ledge
she stands on is lines 162-171, 154 to 157 pixels of pen 3 on each of
them, and her boots rest on its top line — so line 163 is the one clear
run in the picture that is directly under her. The band below it is the
rails and the pavement at 185-199 is where the prompt already blinks.
It is **pen 1**, the picture's own black: pen 11 is the prompt's white
and a second white line would read as a second prompt.

**AND IT ONLY FITS AT A SIX-PIXEL PITCH.** The glyphs are 5 pixels of
ink inside a 7-wide cell, so 26 letters at the prompt's 8-pixel pitch
is 208 pixels of a 160-pixel screen; at 6 it is 156, with one pixel of
gap left between neighbours. `stamp` takes the pitch as an argument
now, and seven glyphs the prompt never used — `B V - 0 2 6 8` — went
into the font with it.

**The words are two pre-rendered strips, not a font and a save-under.**
The build knows the picture and it knows where the words go, so it emits
the picture with them and the picture without; the blink is one `LDIR`
either way, 76 bytes on each of eight lines. The eight lines are in
eight different 2 KB blocks, so their addresses are a table rather than
a stride. They sit on lines 4-11, which is the night sky — measured, not
assumed: lines 0-15 of this image are 1,259 pixels of pen 1 out of 1,280.

**`WAIT_VSYNC` TESTS THE LEVEL AND THE PULSE IS 16 SCANLINES LONG**, so
a loop whose body is a few hundred T goes round it several times inside
one pulse. The main loop never notices — its own work always overruns
the pulse — but `INTRO_WAIT` went round **four times a frame**, blinking
at four times the rate it was written for and scanning the keyboard four
times over. `WAIT_VSYNC_END` spins until the pulse drops, and the pair
of them is an edge. Anything else with a short body needs the same.

**It waits for the RELEASE as well as the press.** The same bit is her
trigger and the gun is draw-hold-release (8.4), so a press still held
when the level starts is an `AIM` that plants her where she stands, and
letting go of it fires a round the player never asked for.

`tools/test_intro.py` compares **the whole picture in video RAM, byte
for byte** against what the build produced — that is four
transformations checked at once: the layout change, ZX0, five raw
sectors and a depacker writing into VRAM. Its controls are the two
mistakes that look almost right: comparing against the LINEAR `.scr`
(which must FAIL, and does, at 4,348 of 16,000 bytes agreeing by
coincidence), and starting the game without pressing anything (which
must not happen, and `FRAME_COUNT` says so). The palette is checked
**where it shows** — the gate array's pen registers cannot be read back,
here or on the machine, so a pixel whose pen the picture knows is
sampled out of the framebuffer, which is indexed by hardware colour.

**The two palettes share eleven of their sixteen hardware colours**, so
after the handover a colour-set comparison proves nothing; the city's
pens are decoded out of video RAM through the engine's own scrolled
address model instead and every pixel checked against the colour
`src/palette.asm` gives that pen — with 1,914 of them that would be
wrong under the title's pens, which is what stops the check passing
either way. **Her own box is excluded and nothing is wrong with it**:
she is drawn and erased inside one frame (8.7), so at the `WAIT_VSYNC`
the erase has put the background back in RAM while the framebuffer still
holds the frame she was in.

### 7.8 The HUD is fourteen characters of one row, and the band it is not is a hardware answer

`assets/sprites/common/mockup_hud.png` is what the artist drew: a
**full-width 16-line strip** — heart, health, ammo, coins, key, oxygen.
This engine cannot have one, and the reason is not the frame's arithmetic
but the CRTC's.

**A band that stays still while the picture scrolls needs a raster
split, and a mid-frame write to R12/R13 IS NOT ONE.** The 6845 reloads
its row-start latch from those registers at **vertical total** and, on a
UM6845R, during the scanlines of **character row 0** — nowhere else. (If
it reloaded at every character row a normal screen would repeat its top
row 24 times.) That is also what the tear this project already saw on
RVM was: `SCROLL_APPLY` called after real work landed inside row 0, where
a type-1 CRTC does re-read them. The real split is **rupture** —
reprogramming R4 so the CRTC restarts a frame mid-screen — and it needs
one precisely timed write in the FIRST character row of each part:

| | |
|---|---:|
| display row 0 begins at | 18,432 T |
| nearest interrupt before it (tick 2) | 13,844 T |
| ... so the first write costs a counted delay of | **4,588 T** |
| display row 2 begins at | 22,528 T |
| ... so the second costs another | **4,096 T** |
| a scrolling frame's headroom (§9) | 3,548 T |

**~8,700 T against 3,548**, and the shorter play area gives back only
1,338. There is no tick anywhere near either row — the free split points
the interrupt cadence does offer are display lines 40, 88 and 144, which
buy a 40-line HUD and a 19-row play area. And none of it can be checked
here: **cpcemu cannot witness a split**, so the whole thing would ship on
RVM's word alone.

**So the HUD is what the frame can pay for.** A strip along the BOTTOM
LEFT of the picture — screen character row 23, **columns 0-13**, word
`HUD_BASE` = 920 into the view — and it is three things in one run:

| | columns | what it is |
|---|---|---|
| health | 0-5 | six of the artist's own `hud_bars` cells, 24x8 Mode 0 pixels |
| ammo | 6-12 | fourteen pips, two to a cell — the rounds in her two magazines |
| magazines | 13 | one of the artist's digits — what `AMMO_RESERVE` is worth |
| **what she carries** | **14-19** | **an icon and a count for the key and for the coins** |

**They are one strip because two adjacent runs vacate into each other**
— the rest of this section is what that buys and what it still costs.

**THE BOTTOM IS WHY IT CAN GO AFTER HER.** At the top it had to be
written BEFORE her — the beam reaches display line 0 at 18,432 T and her
draw is 28,000 to 43,000 T long — so every T it spent came off the lead
the top border gives her, and measured, it took the line she can be
drawn from intact **from 10 down the picture to 29**, against a camera
that never puts her above 32. At row 23 the beam does not arrive until
65,536 T, so the bar goes in straight after `H_TAIL` at about 50,000 T
with 15,000 to spare, and her draw is not touched at all.

#### What it costs, measured

`HUD_SERVICE` is called once a frame and does nothing unless the view or
her health has moved:

| | bar only | + the rounds | **+ the digit** |
|---|---:|---:|---:|
| the view is still and nothing has moved | 136 | 400 | **504** |
| the view stepped one character RIGHT — the level's own direction | 1,188 | 2,704 | **3,568** |
| ... one character LEFT | 2,688 | 5,284 | **6,148** |
| the view stepped one row DOWN — a climb, or a fall | 9,208 | 22,292 | **23,856** |
| ... one row UP | 2,780 | 9,996 | **10,860** |
| `HUD_ALL`, the twelve bytes a line | 2,348 | |
| `HUD_PUT`, one cell of either run | 796 | 868 |
| `HUD_LEVEL` when the same cells stay lit | 348 | |
| ... and when they do not | 5,684 | |

**A HIT IS NOT THE SAME EVENT AS A CELL GOING OUT.** Six cells over 100
points is 16.67 apiece and a drone's round takes `EBUL_DAMAGE` off her,
so most hits move `PLAYER_HP` without changing which cells are lit.
`HUD_LEVEL` compares the count and returns Z, and the caller skips
`HUD_ALL`: 348 T against 8,032. Measured on the build it went into,
standing under fire went from 199 loop iterations per 200 hardware
frames to 201 — the land sheet's redraw has since taken it to 198 (§9)
— and the frame a cell DOES go out on is still one of the two the
drone's own refresh is paid on.

#### And the rounds she is carrying, straight after the bar

**Fourteen pips at the bottom left, going out from the LEFT as she
fires** — screen character row 23, columns 6-12, immediately after the
health bar's six, one per round in her two magazines
(`MAG_LEFT + MAG_RIGHT`, §8.5) — **and then one digit at column 13:
how many spare magazines the reserve is worth.** A reload takes
`BUL_MAX` = 14 rounds out of `AMMO_RESERVE` (§8.5), so the reserve IS a
number of magazines and the digit is that number, capped at 9 because
one character is what the row can pay for. The digits are the artist's
own `hud_digits`. The whole strip is **fourteen characters, columns
0-13**. A round is one pixel of
bullet and one of gap, so a 4-pixel cell holds two of them and her
fourteen are seven characters; a cell is FULL, HALF or EMPTY, and
because the rounds go out from the left there is at most one half-spent
cell in the row.

**The bullet is the artist's own**, cut out of `hud_icons`' `ammo` by
`tools/make_hud.py` — the icon is three of them, one pixel wide with an
orange tip and a yellow body, which is exactly the two-pixel pitch a
Mode 0 byte holds. There is no ammo cell in `hud_bars`; the sheet has
health and oxygen. **A spent round is the same silhouette in the dark**,
which is the convention the bars already use: `(128,128,0)` quantises to
pen 12 against the bullet's pen 11, so a spent round is the dark of its
own colour and not a hole in the row. The artist's mockup draws the ammo
as that icon and a two-digit number, which is the RESERVE; what is on
the screen is what is in the guns, because those are the rounds that go
out one at a time as she shoots.

**THEY SIT NEXT TO THE BAR BECAUSE TWO ADJACENT RUNS VACATE INTO EACH
OTHER.** A run leaves the word just past its LEFT end whichever way the
view goes (`HUD_VACATE`), so:

| | a step RIGHT leaves | a step LEFT leaves |
|---|---|---|
| the bar, columns 0-5 | the last column of row 22 — **free**, `H_TAIL` has just painted it | column 6, the rounds' first cell and one they write on every step left — **free** |
| the rounds, columns 6-12 | column 5, the bar's own last cell and one it writes on every step right — **free** | column 13, the digit, which is written on every move — **free** |
| the digit, column 13 | column 12, the rounds' last cell and one they write on every step right — **free** | column 14 — one `DRAW_COLUMN` |

so the bottom row costs **nothing at all** to erase on a step right,
which is the step level 1 makes, and one `DRAW_COLUMN` stepping left.
**The digit is the one element with no neighbour's content to inherit**
— it is one cell — so it is rewritten on every frame the view moves,
864 T.
And a row step is ONE run of thirteen cells through `DRAW_ROW`, with
one map lookup instead of two.

**AT THE OTHER END OF THE ROW IT WAS THE MIRROR AND THE TWO DID NOT
CANCEL**, which is what put them here. With the rounds at columns 33-39
the bar was free stepping right and the rounds free stepping left, so
the row cost a `DRAW_COLUMN` every step whichever way she walked, and
two `DRAW_ROW`s on every row step. Measured over the same 200 frames:
walking 196 against **198**, firing 178 against **184**, running 148
against **161**.

**A SHOT IS ONE PIP AND AT MOST TWO CELLS.** The seam is `spent / 2` and
one round moves it by nought or one, so the window from
`min(old, new)` to `max(old, new)` holds every cell whose picture is now
wrong — and **a shift widens that window by one on the side it shifts
from**, because every cell then holds its neighbour's picture. Written
once for both directions it left a cell of stale pips walking LEFT, and
`tools/test_hud.py` caught it: 24 wrong pixels of 224, which is exactly
one cell. A reload puts fourteen rounds back at once and lays out the
whole row.

**Seven `HUD_PUT`s and not a buffer, and it was written both ways.** A
112-byte buffer copies the row in 2,668 T against 6,744 for the puts —
but it has to be KEPT, and one cell of it is 1,056 T to lay out, which
is paid on every shot. Measured in play, the buffer was **192** loop
iterations in 200 walking and **175** firing against **198** and **182**
for the puts: the cheap paths are the common ones, and all-seven is the
rare one.

**And what it costs in play is not nothing**, measured over the same
200 frames as §9's table:

| | bar only | + the rounds | **+ the digit** | the rounds at the RIGHT end |
|---|---:|---:|---:|---:|
| walking right, a drone in view | 199 | 198 | **198** | 196 |
| walking right and FIRING, past a drone | 194 | 184 | **183** | 178 |
| running right | 172 | 161 | **151** | 148 |
| turning round, walking left into it | 193 | 192 | **191** | 192 |

The firing path is where it lands, and for the reason §9 gives for
everything else on that frame: a firing frame already carries the
heaviest cel in the game, a round in the air and a drone, and the rounds
change on it as well. The RUN pays twice over, because it steps the
camera on every other frame.

#### And what she is carrying, after the digit

Level 1's entity table hands her a key, a medkit, a clip and a coin
(§8.6), and two of those are things she still HAS afterwards. Columns
14-19 are an icon and a count for each: **lit while she has one and the
same silhouette in the dark while she has not**, which is the
convention the spent rounds already use — an empty slot is a thing she
has not found and not a hole in the row. The medkit is not among them
because it is spent the instant she walks into it, and the magazines
are already the digit at column 13.

**TWO CELLS FOR THE ICON AND NOT ONE, AND THAT IS THE ART'S ANSWER.**
`hud_icons` is 8x16 Mode 0 pixels against a strip that is eight lines
tall, so an icon cannot go in whole. Measured over all nine of them,
every one is drawn **5 pixels wide inside its 8 and 6 to 9 lines
tall**, so the width already fits two characters and only the height
has to be chosen — `tools/make_hud.py` takes the 8-line window with the
most ink in it, so a re-drawn icon re-crops itself.

**AND THE SIX CELLS ARE WRITTEN AS ONE RUN, WHICH IS THE ONLY REASON
THEY FIT.** An icon has no neighbour's content to inherit — it is the
magazine digit's problem six times over — so every cell of it is wrong
after a step of one character and all six have to be rewritten on every
frame the view moves. Six `HUD_PUT`s would be 5,208 T; twelve
consecutive bytes on each of eight lines is **4,068**, and the layout
itself only happens when a COUNT changes, which is a handful of times
in a level. It is `HUD_ALL`'s own argument one group along.

| | fourteen cells | **twenty** |
|---|---:|---:|
| the view is still | 504 | **648** |
| one character RIGHT | 3,568 | **7,636** |
| ... one character LEFT | 6,148 | **10,216** |
| one row DOWN | 23,856 | **32,856** |
| ... one row UP | 10,860 | **14,928** |

**AND THE LOOP DID NOTICE, ON THE FOUR PATHS THAT STEP THE CAMERA
HARDEST — AND THE FRAME WAS NOT WHERE IT LOOKED.** This section used to
say it did not, on a measurement of the walk and the climb. Driven over
all seven of `tools/test_enemies.py`'s paths, game frames per 200
hardware ones, with `HUD_INV` poked to `RET` as the control:

| | with the six cells | `HUD_INV` = `RET` | **now** |
|---|---:|---:|---:|
| standing still | 100 | 100 | 100 |
| walking right, scrolling | **99** | 100 | **100** |
| walking left, into it | 100 | 100 | 100 |
| walking right + firing | 100 | 100 | 100 |
| jumping + firing, scrolling | **99** | 100 | **100** |
| running right, scrolling | **99** | 100 | **100** |
| running right + firing | **97** | 98 | **98** |

**AND THE COPY TURNED OUT NOT TO BE THE COST AT ALL.** Three changes
took all four frames back and only the first two are about the strip:

1. **THE LAYOUT WAITS FOR THE SECOND SWEEP.** What the six cells SAY
   changes when she picks something up, a handful of times in a level;
   where they are WRITTEN changes on every frame the view moves. So
   `HUD_INV_LAYOUT` (6,480 T) and the copy (2,516) are separate
   questions, and only the second has to be on the sweep that latches.
   Measured on the walk, sweep by sweep against the 19,968 µs each
   hardware sweep has: sweep A's worst ordinary frame is **18,582 µs**,
   the frame the layout lands on **20,870 — over by 902**, and sweep
   B's worst **17,236, with 2,732 to give**, because the second sweep
   waits 40,468 T for its head gate (§9). What it costs is that the
   count on the glass is one game frame — 40 ms — behind its variable,
   which is the lag the magazine digit has had since it went in.
2. **AND THE COPY IS THE BAR'S, NOT A SECOND ONE.** Both runs are six
   cells of twelve bytes on eight lines, so there is one unrolled `LDI`
   run and two callers — `HUD_RUN12`, which is also where the
   1024-word fold's slow lane lives. The inventory was copying itself
   with a pair of `LDIR`s and a destination re-read out of memory every
   line: **4,068 T against 2,300**.

That left two paths at 99, and the next measurement is the one worth
copying. **`HUD_INV` was replaced by a delay of a KNOWN length** — `ld
b,n : djnz $ : ret`, benched from a DI stub — so the question stopped
being "is the copy too dear" and became "what could that frame have
paid for". The answer on both paths was **nothing: 484 T cost the frame
and so did 2,884.** A sweep with under 484 T of room cannot be bought
with a cheaper copy, and every idea for one — four cells instead of
six, a compiled `push` run — was dead before it was written.

**SO THE INSTRUMENT WAS TURNED ON THE FRAME INSTEAD, AND IT HAS NO
MODEL IN IT.** Two traces of the same path sampled at every hardware
frame, one with `HUD_INV` returning at once and one with the delay:
they are the same machine until the frame that cannot pay, so **the
hardware frame they part on IS that frame**. Both parted within seven
frames of the start — on the frame she picks the key up.

3. **`ENT_REPAINT_DUE` DISOWNED THE WHOLE STRIP'S LAYOUT WHEREVER THE
   REPAINT LANDED, AND THAT IS THE GAME FRAME.** A taken pickup's cell
   is put back from the tilemap at the very end of the frame, and that
   cell *may* be under the bottom row — so the five counts were stamped
   `&FF` and the next `HUD_SERVICE` laid the whole strip out again:
   `HUD_LEVEL` and its copy 8,032 T, all seven ammo cells 6,076, the
   digit 864 and the six icons after them, **~17,000 T on a first sweep
   with under 484 to spare**. Measured, a level-1 pickup is never over
   the strip at all: the roof is world character row 12 and the view's
   own row is 0 to 8, so the cell comes out at screen row 4 to 12
   against a strip at 23. The stamp is `HUD_DISOWN` now and the guard
   is two comparisons in `ENT_CELL_REPAINT`, where the screen row and
   column have already been worked out — the cell is two character rows
   and two columns, so it meets row 23 only from row 22 and only left
   of the strip's last cell.

**Six of the seven paths are 100 of 200 with the whole strip in them**,
and `HUD_SERVICE` poked out changes nothing on any of them. The seventh
is the run with the gun at 98 either way — its cels are 351 span bytes
against the 324 of her heaviest `kcore` one (§9), and that is not the
bottom row. `tools/test_enemies.py` asserts each path exactly, with the
whole-HUD control on the one that is short; `tools/test_entities.py`
drives the guard at a cell chosen to land on row 22 and at two that do
not, because a guard that never fired would pass the negative halves on
its own.

`tools/test_hud.py` builds the expected 96 bytes out of `hud_art.inc`
independently and compares them in video RAM through the engine's own
circular address model, at five counts, walking both ways, with the
same negative control the bar and the rounds have: with `HUD_INV`
returning at once the run is still drawn and the CRTC carries **all 96
bytes** of it off with the world.

#### THE STRIP IS REPAIRED AFTER THE BEAM HAS SHOWN IT, AND ON A ROW STEP THAT IS A GHOST

**A play-test found it and a measurement named it**: *"στην πτώση το
hud αφήνει πίσω traces"* — falling off the ledge left the magazine
digit several rows above the strip. It is neither the vacate being
wrong nor a step being misclassified; both were checked and both are
right. It is **when**.

`SCROLL_VBLANK` latches R12/R13 at the TOP of the game frame's first
hardware sweep (`src/main.asm`) and `HUD_SERVICE` runs after `H_TAIL`,
most of a sweep later. Measured on the latch frames of a fall, stepping
to the instant `HUD_SERVICE` is reached and reading the elapsed time
from the `WAIT_VSYNC` exit:

| | T |
|---|---:|
| `HUD_SERVICE` reached, over six consecutive latch frames | **49,848 - 61,444** |
| ... plus a downward row step | +32,856 |
| so the strip is right again at | **82,700 - 94,300** |
| the beam reaches row 22 (emulator / a real 6845) | 60,432 / **63,488** |
| ... and row 23 | 62,480 / **65,536** |

So on the frame the view steps down a row, the beam sweeps the whole
picture with the strip's pixels still at their old words — **which are
now row 22** — and the freshly painted tilemap at row 23. One hardware
sweep, 1/50 s, on every row step; a fall makes six to eight of them
back to back, which is what "traces" is.

**It is one sweep and not two**, because the repaint runs past the end
of its own sweep and lands ~5,000 T into the next one, ahead of that
sweep's row 22. That is also why nothing shows in RAM at a sync point
and why `tools/test_hud.py`'s walking checks pass: by the time anything
samples, the strip is right. The witness is the beam.

**And it cannot be fixed by making the vacate cheaper.** To be clean
the strip has to be right before the beam reaches row 22, which means
starting by ~27,500 T — inside `KARA_DRAW`. Put in front of her draw it
costs her lead at ~320 T a scanline (§9), and 32,856 T is the whole top
border and then some. The measurement says the repaint has to
**immediately follow the latch**, and the one place in the game frame
with room for it is the second sweep's idle window: `.head_gate` waits
for interrupt tick 4, which is **40,468 T of doing nothing**, every
frame.

**SO THE VERTICAL LATCH MOVED THERE, AND THE STRIP WITH IT.**
`SCROLL_VBLANK` and a `HUD_SERVICE` are now the first two calls after
the second sweep's `WAIT_VSYNC`, and the first sweep keeps the
horizontal latch and its own `HUD_SERVICE` exactly where they were.
Measured on the same six latch frames of the same fall:

| | before | after |
|---|---:|---:|
| `HUD_SERVICE` reached | 49,848 - 61,444 | **6,320 - 12,648** |
| ... so the strip is right again at | 82,700 - 94,300 | **39,000 - 45,500** |
| against the beam at row 22 | 63,488 | 63,488 |

**WHAT MAKES IT SAFE IS THE ERASE SCRIPT.** `SPAN_ERASE` replays a
list of ABSOLUTE addresses the draw wrote (§9), so a start address
that moves between her draw and her erase does not move where the
erase writes; her PIXELS move with the picture, which is exactly what a
world-fixed sprite is supposed to do and the same reason the enemy is a
persistent sprite (§8.7). Three things had to move with it:

* **`PLAYER_TO_SCREEN` goes to the END of the second sweep.** It
  converts her world position against the view, and the view is not
  final until the latch; left in the first sweep she was drawn a
  character row out of place. It is after the erase and not before
  because the erase's raster gate is picked from the lines the DRAW
  recorded.
* **`KARA_ERASE_LEAD` is 32 and was 24.** The gate is picked from those
  recorded lines, and a step UP now puts her pixels 8 lines BELOW them.
  The worst any cel needs is 17.8 scanlines, so 24 had 6.2 to give and
  a character row is 8.
* **The head's gate anchors at the `WAIT_VSYNC` exit, in a byte.** It
  used to take `IRQ_TICKS` where it stood, which was immediately after
  the wait; the latch and the strip now run in between and are up to
  33,000 T, two and a half ticks, so anchored after them the head waits
  four ticks from THERE and lands past the end of the sweep. Measured
  as **119 wrong pixels down column 0** by the check with no model in
  it — the same column and the same kind of fault as §9's tearing, and
  found the same way.

**AND IT MADE THE CAMERA FASTER, WHICH IS NOT A SIDE EFFECT ANYONE
ASKED FOR BUT IS WHY THE FALL LOOKS RIGHT NOW.** The latch used to be
tested at the top of the frame and the row's last piece painted at the
bottom of the same one, so a step took `V_PARTS` + 1 = **three** game
frames; tested at the top of the second sweep it takes **two**.
`tools/test_climb.py` went from four failing checks to one: "the camera
catches up with her on the street", "the street is on screen with her"
and "the view had to scroll the whole way to follow her" all pass now,
and the one left is the 25 Hz coyote budget in the test itself.

#### AND THE WHOLE OF THE VERTICAL COST IS THE ERASE, MEASURED

A downward row step is 23,856 T and that is about 10,000 more than the
latch frame has. Driven by a vertical step every frame — which is
`tools/test_module4.py`'s driver, and harsher than the camera, which
asks for one row every five frames — the loop is **180 iterations in
200**; with `HUD_VACATE` poked to `RET` and everything else left in, it
is **201**. The redraws are not the cost:

| | loops / 200 |
|---|---:|
| as it is | 180 |
| the rounds' redraw off | 182 |
| the rounds' and the digit's redraw off | 181 |
| **`HUD_VACATE` off** | **201** |

**Fourteen characters of tilemap repainted one row up, at ~950 T a
cell.** `DRAW_ROW` hoists the map lookup across the run and still costs
~59 T a byte, where an `LDI` from a save-under would be 20 — so the one
lever left on it is to keep what was under the strip and put it back
instead of re-rendering it, which is 224 bytes of RAM and a rotating
ring of per-cell captures (one horizontal step covers one new word).
That is **not** written: it is the next thing to do if the fall's frames
matter more than the code does. What it costs today is measured, in
`tools/test_climb.py` (climbing down) and in `tools/test_module4.py`,
whose raster sweep scores the frames either side of a latch and prints
how many it skipped.

**THE BAR IS A PERSISTENT SPRITE AND `HUD_VACATE` IS ITS ERASE.** Its
pixels sit in the ring at `HUD_LAST..+5`; when the start address moves,
the words it used to own are still on the screen somewhere else, and the
write at the new place only covers five of the six. Which word is left
over is a property of the step, and there are only four steps:

| step | the word it leaves | |
|---|---|---|
| **1** right | `HUD_BASE-1` — the LAST column of row 22 | **free** — see below |
| **1023** left | `HUD_BASE+14` — row 23 column 14 | one `DRAW_COLUMN` |
| **40** down | the whole strip, row 22 columns 0-13 | the dear one |
| **984** up | row 24 — off the bottom of the display | free |

**The step is taken modulo the 1024-word ring, not as a signed
number.** `SCROLL` is 0-1023 and wraps, so on the frame it wraps a step
of +40 arrives as a subtraction of 1000 from 16 — and read as a signed
number that is a jump no axis can make. The whole bar then went down the
general path once every 1024 words of scroll.

**And the general path was 17,836 T.** It finds each leftover word by
arithmetic — which is right, and is what stops a test's bigger jump
smearing the strip down every row — but it divides the word index by 40
with repeated subtraction (22 iterations for row 22) and then paints
each cell with `DRAW_COLUMN` at 1,148 T. Six of those on the frame the
CRTC latches a downward row step **dropped 23 frames in 200 climbing
down**, and a ladder is exactly that step repeated. The four answers
above are constants, so they are written as constants; the arithmetic
stays as the fallback for the jumps only a test makes.

**A run of cells goes through `DRAW_ROW` and a single cell through
`DRAW_COLUMN`**, because a row hoists the map lookup across the whole
run and charges 1,150 T of setup to do it. Measured: one cell is
**1,148 T** down the column against 2,100 along the row; six cells are
**6,332 T** along the row against 6,888 down six columns. The
single-cell case is the walking one — paid on every frame the camera
moves — so it is worth the second path.

**AND THE STEP RIGHT COSTS NOTHING AT ALL, BECAUSE `H_TAIL` HAS ALREADY
DONE IT.** The word the strip leaves behind on a step right is the last
column of row 22 — and the incoming column of a step right IS column 39,
painted rows `COL_HEAD`..23 by `H_TAIL` four instructions before
`HUD_SERVICE` is called. The step LEFT has no such luck: its incoming
column is 0, so the word left over is column 14, one past the strip's
own end, and has to come back off the tilemap. **That is what decides
which corner the strip goes in**: at the bottom RIGHT it would be the
mirror — the step left free and the step right 1,148 T — and level 1
scrolls left to right. The pan after a turn is where it is dearest
either way, and `tools/test_enemies.py` carries the number: walking left
into a drone is 191 loop iterations per 200 hardware frames against 198
walking right.

#### What is left of it is lines off the top of her picture

A tilemap repaint is ~59 T a byte and the strip's fourteen cells are 224
of them; the strip puts itself back at 24 T a byte. There is no third
source for the pixels under it, so a downward row step costs ~13,300 T
of `DRAW_ROW` plus ~9,300 of write-back on the frame the CRTC latches —
and that frame runs over. **The next frame then starts late, and she
loses ~320 T of lead a line**, so every 320 T of overrun is a line off
the top of the picture:

| | she is drawn intact from |
|---|---:|
| no strip at all | every line the driver can reach |
| the bar at the top | line 29 |
| six cells at the bottom | line 21 |
| ... and then the land sheet was redrawn (§9) | **line 43** |
| the camera's own limit (§8.8) | `KARA_Y` >= 32 |

`tools/test_module4.py` measures it rather than assuming it, and
`KARA_RASTER_SAFE` carries the number. **A save-under WOULD buy these
back now, and it did not when the strip was six cells** — which is the
one thing the second element changed about this argument. Restoring 224
bytes with `LDI` is ~4,500 T against ~13,300, but a capture taken on the
same frame costs the same again and the latch frame gains nothing. What
makes it pay is that the capture does NOT have to be taken then: a
horizontal step uncovers exactly ONE new word, so a ring of per-cell
captures kept up as the view moves leaves the latch frame with nothing
but the restore. That is 224 bytes of RAM and it is not written.

**And the erase CANNOT be made free by shortening the play area**, which
is the one arrangement that would do it. If the playfield were 23
character rows and the HUD the 24th, a downward step's incoming row
would be painted at row 22 — exactly where the old bar is — and a step
right would paint the incoming column through it as well. But then
nothing ever paints columns 6-39 of row 23, so the HUD has to own the
whole row; and a full-width strip that stays still is 640 bytes rewritten
at every scroll step, which is 15,360 T. That is the band again, by
another road.

**The 224 bytes ARE the cost, and they are not optional.** Anything
screen-fixed on a hardware-scrolled display has to be rewritten every
time the start address changes, because the address it lives at is the
one the CRTC is about to show somewhere else. `tools/test_hud.py`'s
negative control is exactly that: with `HUD_SERVICE` returning at once
the strip is still drawn, and 108 of the bar's 192 pixels are wrong
within 90 frames of walking.

Three more things about it are load-bearing:

* **It is drawn LAST**, with `ENT_REPAINT_DUE` and `ENEMY_REFRESH`,
  because it is BACKGROUND. She never overlaps it — the camera keeps her
  middle between 64 and 112 (§8.8), so her box ends at line 144 at the
  very lowest and the strip starts at 184 — but `ENT_REPAINT_DUE` can
  paint over it, and `entity.asm` forces it to be written again on the
  next frame so the damage is never displayed. **Forcing it is
  disowning the LAYOUT, not the health**: `HUD_HP = &FF` on its own
  changed nothing, because `HUD_LEVEL` compares the number of cells LIT
  and &FF lights the same six as 100 does. `HUD_LIT`,
  `HUD_AMMO_SPENT` and both inventory counts are stamped with it too —
  which is `HUD_DISOWN` — so what `HUD_SERVICE` finds is a layout
  nobody owns and it lays the whole strip out again. **AND IT IS ONLY
  DONE WHEN THE REPAINT CAN REACH THE STRIP**: two comparisons in
  `ENT_CELL_REPAINT`, where the screen row and column are already
  worked out, and a whole game frame on the two paths that had none to
  give — see the third measurement below.
* **ONE CHARACTER OF MOVEMENT ONLY CHANGES TWO OF THE SIX CELLS.** The
  bar is `c[0..5]` with `c[i]` full while `i < lit`, so a shift of one
  character leaves every cell holding its NEIGHBOUR'S content — the same
  content everywhere except where the run of full cells ends. 1,512 T for
  the two against 2,348 for all six, and it matters because a camera PAN
  moves the view on every frame for about twenty of them (§8.2).
* **AND THE SAME IS TRUE OF THE PIPS, WITH ONE MIRROR IN IT.** The ammo
  is a run of full cells too, so a shift moves its window by one and the
  window has to WIDEN on the side the shift comes from — right:
  `e-1 .. e`, left: `e .. e+1`, where `e` is the seam `spent / 2`. It
  was written once for both directions and `tools/test_hud.py` caught
  what that leaves: 24 wrong pixels of 224 walking left, which is
  exactly one cell of stale pips.
* **Six characters wide crosses the 1024-word seam at six of the ring's
  1024 positions**, where the run folds back to the top of its own 2 KB
  block (§6.4). The common case is twelve unrolled `LDI`s a line (20 T a
  byte against `LDIR`'s 24); the fold takes a slow lane of two `LDIR`s.
  **That path was written wrong and the test caught it** — the fold count
  was doubled as if it were characters when it was already bytes — which
  is why the suite drives all six positions and keeps word 1018, the last
  that does NOT fold, as their control. **The ammo and the digit need no
  such lane at all**, and it is not care that spares them: they are
  written a CELL at a time, a cell is one word, and one word cannot
  straddle a boundary between words. Only a run can fold.

**The old ammo HUD is gone.** `HUD_UPDATE` and `HUD_ROW` drew two rows of
seven round indicators for the Module 1-3 acceptance screen; that screen
was deleted and nothing has called them since.

### 7.9 The disc's front door: the label screen, then the game

`RUN"KARA` is what a player types. It puts REVIVE8BIT's screen up,
holds it for **ten seconds or until SPACE**, and then loads the game
exactly the way `disc.bas` does. `RUN"DISC` still goes straight in and
is what every suite runs, so the splash is never in a measurement's
way.

**IT IS BASIC AND NOT THE ENGINE, and that is a memory-map decision.**
The engine disables both ROMs before it runs (§4) and drives the disc
itself (§7.5), so a picture shown from inside it would cost a place in
the bank map and a read through `src/disc.asm`. Shown from BASIC it
costs one `LOAD` and nothing at all afterwards: by the time `CALL
&4000` happens, BASIC and its screen are both gone.

**AND THE LOADER IS GENERATED, BECAUSE THE PALETTE IS THE ARTIST'S.**
`assets/revive8b.scr` arrives with a note giving sixteen firmware inks,
one per pen; typed into a `.bas` once, a re-exported picture would come
up in the last one's colours and nothing would say so.
`tools/make_loader.py` reads the note. Two details in what it writes
are load-bearing:

* **`MEMORY &3FFF` comes before there is a variable to lose**, in the
  same line as the `MODE`. It drops HIMEM to just under the game's load
  address so `LOAD"GAME.BIN"` at &4000 lands above BASIC's stack
  instead of through it.
* **The ten seconds are counted AFTER the load**, not before it.
  Interrupts are off for a disc read, so `TIME` stands still through
  it; started first, the hold would be ten seconds minus the read. And
  `TIME` counts in 1/300 s — the gate array's interrupt (§9), not the
  frame — so ten seconds is 3,000.

**The press is not swallowed.** The game's own title waits for the
RELEASE as well as the press (§7.7), so a SPACE still held when the
game starts does not run straight past it.

#### What it cost the disc, and it was a track

The label screen is a whole 16 KB and BASIC cannot unpack anything, so
it goes on as a plain AMSDOS binary. That took AMSDOS's own allocation
from block 18 to **36 — which IS the first data block at track 8** —
and `tools/dskdata.py` said so rather than letting the level streams be
overwritten. `DATA_TRACK` is **9** now: the first data block is 40, the
files have four 1 KB blocks of room left, and the data ends at sector
346 of 360. Both ends are checked by the build.

`tools/test_loader.py` compares **video RAM with the artist's file byte
for byte** — the AMSDOS header, BASIC's `LOAD` at &C000 and the file
itself, three transformations at once — with the mistake that looks
almost right as its control: the game's own title is a 16 KB Mode 0
screen as well, and only 493 of 16,384 bytes agree with it by
coincidence. The hold is checked from both ends, which is its own
control: **968 frames left alone against 536 with SPACE**, and a loader
that ignored the key would give the same number twice.

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
own byte and she drifts across the picture as she covers it, arriving
in about 40 frames at a walk and 20 at a run. A pan is exactly a run's frame cost — a column every frame — and
it is the one thing that makes the loop drop a frame or two (§9).
`CAM_BAND` is what tells "the camera is following her" from "the camera
is panning to catch up": only the first gets the lock-step below, and
without it she would freeze at whatever column she turned round on
while the camera panned for ever.

**The walk speed and the scroll step are the same number or the picture
doubles.** The CRTC scrolls a whole character — 2 bytes — so inside the camera's
push zone the camera can only fire on the frames she covers two. Let her keep
walking her own distance there and the column the blitter
draws her at goes 54, 55, 54, 55 at 25 Hz: every frame is drawn and erased
correctly, every RAM check passes, and on a real monitor there are two Karas a
character apart for as long as the screen moves. `PLAYER_X` therefore moves her
`P_PUSH` = 2 bytes on the camera's frame and nothing on the frames between, so
her screen column never changes while the world goes by.
`test_module4.py` asserts the property directly: on
every frame where the view moved, `KARA_X` must not have.

**A STEP IS A WHOLE BYTE AND A SPEED IS HOW MANY FRAMES APART THE STEPS
ARE.** `KARA_X` is a byte column and a Mode 0 pixel is half of one, so
there is no smaller step to give her: half speed is a step she does not
take. `PLAYER_BEAT` is the mask — `FRAME_COUNT AND beat` must be 0 —
and `PUSH_PHASE` doubles it for the push zone, where the step is the
CRTC's two bytes:

| | free zone | in the push zone | pixels a game frame |
|---|---|---|---:|
| **walk** | 1 byte **every** game frame | 2 bytes on one frame in **two** | 2 |
| **run**, SHIFT | **2** bytes every game frame | 2 bytes **every** frame | 4 |

**AT 25 Hz A SPEED IS THE SIZE OF THE STEP, NOT HOW MANY FRAMES APART
THEY ARE** (§9). At 50 Hz a byte a frame was as fast as the frame could
carry the scroll, so the only way to be slower was to skip frames and
`PLAYER_BEAT` was a mask; a game frame is two hardware frames now and
there is no half-frame left to skip, so `PLAYER_STEP` holds the step
itself — 1 walking, 2 running — and she steps on every one. Both cover
exactly the ground per SECOND that the 50 Hz numbers did. **And a run's
free step IS one CRTC character**, so in the push zone it scrolls on
every game frame and never sits still: `PUSH_PHASE`'s mask is
`2 - PLAYER_STEP`.

**The walk was 2 pixels a frame and it is 1**, which is the artist's
own answer: her walk cycle is 40 frames and her feet are 9 pixels apart
at full stride, so a cycle plants them 18 pixels of ground apart and
the engine was carrying her 80. See §8.4 for what the other half of
that fix was.

**And the run is a byte a frame, not the CRTC's whole character, because
the frame cannot pay for a column every frame.** Two bytes a frame is
exactly one scroll step a frame, which puts `H_HEAD` and `H_TAIL` on
the same frame — §9's pessimistic sum, 87,328 T of 79,872 — and a frame
that overruns waits for the next VSYNC. Measured over 200 hardware
frames holding SHIFT and RIGHT: **107 loop iterations**, which is 25 Hz,
a character of scroll every other frame and Kara on the screen for one
frame in two. At a byte a frame the camera steps every other frame,
which is the load the old walk carried and the whole of §9 measures as
locked.

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

**Every tile blitter here is a plain copy and stays one.** Level 1's 11
overlays are composited into new tiles at build time instead, because a
masked cell is 2-3x a copy against a frame with 3,548 T in it — §7.3
has the numbers and what the bake recovers.

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

**THAT BIT ORDER IS THE ENGINE'S TOO, and settling it was half of §11
step 7's homework.** `collide.asm`'s `TA_*` used to run the other way
up — `TA_SOLID` was bit 7 — for no reason anyone wrote down: every
probe in the engine is symbolic (`AND TA_SOLID`, `LD B,TA_BLOCK`) and
not one of them cared which bit it was. So the engine took the format's
numbering rather than asking the exporter to translate, and
`tileflags_level1_city.bin` IS the table `TILE_ATTR` holds. `TA_TRIGGER`,
which had no counterpart in the format and no reader in the engine, is
gone; `TA_DEADLY` comes in from the format's own list.

**And the table is RAM the level fills, not a literal in the engine.**
It was a `db` per tile in `collide.asm` in the artist's frame order,
which is fine for exactly one level; `MAP_INSTALL` now clears all 256
entries at &A900 and LDIRs the file over them, so level 2's tileset
needs no second table in the image.

#### The engine reads `level_1.lvl`, and that is where Module 6 starts

`tools/make_level.py` writes the bytes of §9.2 — header, map, entities,
links, regions — and `MAP_INSTALL` reads them: the magic, the shape
(128×16 or it is refused, because `MAP_CELL` scales the row out of the
base address at compile time), the header's entity count straight into
`ENT_COUNT`, the map and the records by `LDIR` because **the record on
disc IS the record in RAM**, and the tileset's flags into `TILE_ATTR`.

The City is 2,149 bytes of it: 21 of header, 2,048 of map, 80 of
entities, no links and no regions. `tools/test_format.py` is the golden
file — an independent reader takes the header apart field by field, and
then the engine is checked against what it read, with three controls a
loader that ignored the file would fail: **break the magic and it
refuses**, **give it a map of another shape and it refuses**, and
**take `TA_CLIMB` off the ladder in the FILE and the table in RAM loses
it too**. The five cells where RAM and file disagree are the pickups
`ENT_BAKE` stamps into scratch tiles (§8.6), and the test says so by
name.

**Those are what a tile DOES; `tile_table.json` says how it is DRAWN**
(§7.3), and the two are independent — `ladder` is an overlay in level 3
and an opaque tile in level 1, with the same `Ladder` flag in both. The
format has nowhere to put "this cell is an overlay over that one" yet,
which is the same gap: a cell is one byte and an overlay needs the tile
under it as well. The tile flag byte is settled above and
`param0`/`param1` are in §8.6.

#### AND THE EDITOR WRITES THESE BYTES NOW, WHICH MAKES THE GOLDEN FILE RUN BOTH WAYS

`editor/` is the C# side of the contract (§11 step 7): a Domain that holds
a level the way a designer does, and an Exporters library that turns it
into the bytes above. **It reads `build/level_1.lvl` and writes it back
byte for byte — 2,149 of them — and `tools/test_format.py` then loads the
result on the emulator and passes every check with its three controls
intact.** So the format is no longer something one implementation asserts
about itself: an independent reader and an independent writer, in another
language, agree with `make_level.py` and with `MAP_INSTALL`.

**Four things the exporter has to get right that are easy to get NEARLY
right**, all of them found by writing it:

* **`SCROLL_H` is ZERO**, so a horizontally-scrolling level's flags byte is
  `&00` and not `&01`. A writer that treats "horizontal" as a bit to set
  differs from the shipped file in the header alone.
* **An empty section still gets a real offset**, and with no links and no
  regions both of those equal the FILE'S OWN LENGTH.
* **A region is SEVEN bytes** and the header's count is `length / 7`, so a
  record padded to eight reports a count that is nearly right.
* **The live records are contiguous from zero and every one is
  `EF_ACTIVE`.** The engine clears its 24 slots and `LDIR`s `count * 8`
  bytes over the front, so an inactive record inside the count is not a
  gap — kind 0 is `EK_PLAYER_START`, so an all-zero record is a real
  entity at (0,0).

**THE OVERLAY PAIRING LIVES IN THE EDITOR AND STILL DIES BEFORE THE
FILE.** The gap above is real and is not closed by growing the format: the
editor keeps `(overlay, background)` in a layer of its own and composites
at export exactly as `bake_overlays()` does, so a map cell is still a
finished tile and the engine is untouched. `OverlayBaker` reproduces level
1's ten baked tiles and the `citytiles.bin` they go in **byte for byte**,
drops the one pair whose composite came out the overlay again (`tank_10`),
resolves the overlay that stands on another composite
(`tank_21_on_ac_unit_on_far_fill`), and gives each baked tile the flags of
what is UNDERNEATH it — 51 bytes of `tileflags_level1_city.bin`, also byte
for byte.

**What is NOT part of the contract is the NUMBERING.** A pair takes its
index the first time it is placed, so a different placement order gives
different indices and therefore different map bytes for the same picture.
`make_city_map.py` sweeps prop by prop and an editor paints cell by cell,
and neither is more correct. Handed the placements in the generator's own
order the C# baker reproduces `city_baked.json` exactly, which is what the
suite drives; what a golden test may assert in general is a pair's CONTENT
and the map's consistency, not the number it was given.

**`docs/editor.md` had four things wrong and they are written into its own
§0 now**, because a spec that is read after the code is written is read by
somebody who does not know which half to believe: the HUD band and the
level size are §8.3's two corrections below, and the two the exporter
found are the entity flags byte (editor.md says bit 0 is "facing left";
the engine and the shipped file both say `EF_ACTIVE`, and there is no
facing bit at all) and the enemy's `param0`/`param1`, which were the wrong
way round in `src/entity.asm`'s own header comment as well.

#### Two corrections to editor.md, both forced by the CRTC

**1. Tiles are 8×16 — ~~which this engine does not do yet~~, and now it
does.** A tile is **4 bytes × 16 lines**, so it spans 2 CRTC character
columns and 2 character rows, and the City's map is 128×16 of them.
`tilemap.asm` and `collide.asm` were rewritten around it when the drawn
art arrived; what is left of Module 6 is the play area with its HUD
(6c) and the X clip (6d) — the masked path is not coming, the overlays
are baked at build time instead (§7.3).

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
| `JUMP` | `jump` 6 | UP pressed while grounded, **or within `P_COYOTE` frames of walking off** | she lands |
| `ROLL` | `roll` 8 | **DOWN + left or right**, on the ground | the 8 frames are done |
| `CROUCH` | `roll` cel 0, held | **DOWN alone**, on the ground, with no ladder under her and the trigger up | DOWN is released |
| `HANG` | `hang` 2 | **DOWN at the lip of a floor**, after `HANG_BEAT` frames of the crouch | she climbs back, or lets go |
| `AIM` | `shoot_draw` 2 then hold | **SPACE held** | SPACE released |
| `FIRE` | `shoot` 4 | **SPACE released** from `AIM`, with a round in a magazine | the 4 frames are done |
| `CLIMB` | `climb` 4 | on a ladder — the cycle runs while UP or DOWN is held and **freezes on the cel she stopped on** when neither is | she steps off it |
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

**AND A FALL OF MORE THAN ONE AND A HALF OF HER OWN HEIGHT COSTS HER.**
`FALL_FREE` is `KARA_BOX_H + KARA_BOX_H / 2` = **96 lines** — her own
box and not a number, so a re-drawn heroine moves the threshold with
her — and only the EXCESS is paid for, at a point a pixel. What the
level makes of that is the design in one table, measured off the map
rather than chosen:

| | fell | cost |
|---|---:|---:|
| walking off the roof into `ROOF_GAP` | 128 lines | **32 points** |
| letting go of the LEDGE | 70 | free |
| a jump that lands where it left | 36 | free |
| climbing down the ladder | — | not a fall at all |

**So the ledge is the safe way down and the gap is the one that hurts**,
which is what a ledge is for (§8.8); and she can take the gap three
times, against a medkit worth 35 (§8.6). **A fourth kills her**, and
`ACT_UPDATE` then chooses `die` from `PLAYER_HP == 0` like any other
death — there is still no respawn.

**THE MARK IS ONE RULE AND ONE CALL SITE, and that is what makes it
right everywhere without knowing about anywhere.** `FALL_MARK` runs
first in `PLAYER_UPDATE`, before anything this frame has moved: while
she is NOT going down the mark follows her, and the instant she starts
going down it stays put. A jump therefore measures from its own APEX,
because the mark follows her up and freezes on the frame gravity turns
her round; a ladder measures nothing, because she never descends under
gravity on one; and letting go of a ledge measures from the ledge,
because hanging holds `KARA_VY` at zero. The alternative — remembering
where each of the six places she can leave the ground put her — is six
sites that have to agree, and §10 is mostly about what that costs.

`tools/test_climb.py` checks the damage against the distance **the
machine itself measured** rather than against the number 32, which is
what makes it a check on the proportion; the gap and the ledge are each
other's control, and `FALL_DAMAGE` poked to `RET` makes the same fall
free, which is what says the 32 is the fall and not a drone's round on
the way down.

**SHE CAN STILL JUMP FOR `P_COYOTE` = 6 FRAMES AFTER THE GROUND GOES
AWAY**, and the roof's gap is the measurement that set the number. Her
arc is 15 frames and a RUN covers about a byte a frame; the hole is 12
bytes and she has to be 7 past its far lip for `BOX_SOLID_V` to find
anything under her, so the only take-off that clears it is one of the
ten bytes before the edge. A press one frame later did nothing at all
— and "nothing at all" is a 128-pixel fall for a 20 ms miss, which is
how it was reported. Measured on the gap, in frames from the lip:

| UP pressed | before | after |
|---|---|---|
| 8 or more frames early | falls in | falls in |
| 7 to 1 frames early | clears | clears |
| the frame the roof runs out | clears | clears |
| 1 to 6 frames late | **falls in** | **clears** |
| 7 frames late or more | falls in | falls in |

so the window went from 8 frames to 14. It is **not** a second jump and
not a rescue: `.jump` zeroes the counter, so the air holds exactly one;
the counter runs down whether she uses it or not, so nothing can be
saved halfway down a fall; and it is armed in the ONE place the ground
goes away under her feet, so letting go of a ladder (`CLIMB_LEAVE`) does
not get one. `tools/test_climb.py` has both ends of the window as
controls — too early lands her in the hole, too late is past the coyote.

**AND STOPPING ON A LADDER FREEZES THE CEL RATHER THAN PLAYING
ANOTHER.** `ACT_UPDATE` used to choose `hang` when no direction was
held; `hang` is side on and `climb` is a back view, so she stopped and
turned to face the player without moving (§7.1). The state stays
`CLIMB` and the animator is simply not called — `ACT_SHOW` still
publishes the set and the frame, so she is on exactly the rung and
exactly the cel she stopped on, and the cel's timer keeps whatever it
had left for when she starts again. The state is gone from the table,
not merely unused.

**THE LADDER TURN IS THE ONE STATE NOTHING IN `action.asm` CHOOSES.**
`climb` is a back view and idle and walk are side on, so she cannot cut
from one to the other (§7.1). `player.asm` plays the cel by
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
`shoot` and fires on its first frame — **unless both magazines are dry
or she is reloading**, in which case the release plays nothing at all
and starts the reload instead: the `shoot` cels carry the muzzle flash
and an empty gun must not show one (§8.5). That is what the two-frame
`shoot_draw` tag is for, and its `draw_offset_x=4` in the JSON is the
muzzle's X inside the box — the bullet spawns there, not at the edge of
the sprite.

**AND AIMING PLANTS HER.** SPACE down is a stance: `PLAYER_X` sets her
facing and then refuses the step, so she can turn round while she aims
and she cannot walk. Only the horizontal step goes — gravity, the
ladder and the jump are untouched, and she is free again the instant
SPACE comes up, with the four cels of the recoil playing while she
moves. `AIM_ROOTS_HER` is the whole of it.

**That makes "she covers the same ground firing as not" false by
design**, and `tools/test_module5.py` asserts the sharper thing
instead: **she loses exactly the frames the trigger was down and not
one more.** The aiming frames are counted off the test's own tap
pattern, so re-timing the tap re-derives the expectation rather than
invalidating it — and a dropped frame still shows, because a dropped
frame is ground lost on a frame she was NOT aiming.

**DOWN ON ITS OWN IS A CROUCH, AND IT IS THE LAST THING DOWN MEANS.**
The roll's first cel is her on one knee, so the pose is drawn and ships
already; what it is FOR is their rounds. `EBUL_HITS_HER` takes
`KARA_CROUCH_TOP` = 23 lines off the top of her box while it is up —
measured off the sheet, where the crouch is drawn from line 23 of the
64-line box and standing from line 6 — and her feet do not move, so
only the top of the box does. Measured in front of a drone over 400
frames: **standing she takes 6 hits and goes from 100 to 52; crouching
she takes none.**

Everything else DOWN can mean is tested first: a ladder under her feet
(`player.asm` has already put her on the shaft by the time
`ACT_UPDATE` runs), DOWN with a direction (the roll), and the gun — so
a player holding DOWN can still shoot back rather than pressing a
trigger that does nothing. She stands up to aim; ducking is not cover
she can fire from.

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
than it was drawn and out of step with itself. So `ACT_ANIMATE` reloads
its timer from that table, and the test compares every cel's dwell
against it.

**AND THE RATE THE WHOLE CYCLE RUNS AT IS THE ENGINE'S, BECAUSE THAT IS
THE ONE THING ASEPRITE CANNOT KNOW: HOW MUCH FLOOR GOES UNDER HER WHILE
IT PLAYS.** `KARA_RATE` is one right shift of the art's dwell per state.
It is 1 for the two states that carry her along the ground and 0 for the
other eleven, and both are measured off her feet on the shipped sheet:

| state | cels | cycle | stride | she covers | skate |
|---|---|---:|---:|---|---:|
| `walk` | 10,10,10,5,5 | 40 fr | 18 px | 40 fr @ 1 px | 2.2x → **20 fr, 1.1x** |
| `run` | 7,7,7,4,4 | 29 fr | 29 px | 29 fr @ 2 px | 2.0x → **13 fr, 0.9x** |

"Stride" is twice the distance between her two feet on the cel they are
furthest apart — 9 px walking, 14.5 running — because a cycle is two
steps. **The shift is the most halvings that still leave her covering at
least the stride**: a second one takes the walk to 10 frames and 10
pixels of ground against 18 of feet, which is skating backwards.
Before the walk was halved (§8.2) it carried her 80 pixels through an
18-pixel cycle, which is four fifths of every step skated.

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

`RUN` steps her a byte on every frame and a walk steps the same byte on
one frame in two, so inside the camera's push zone a run scrolls every
other frame and a walk every fourth one — see §8.2 for the table and for
why the run is not the CRTC's whole character.

**AND SHIFT WAS NEVER SCANNED.** `input.asm` read row 2 **bit 6**, which
is `\`, where SHIFT is bit 5 — so the run state, its two banks of cels
and its step were all reachable, by a key nobody would ever press.
Nothing failed and nothing looked wrong; what found it was a play-test
report that SHIFT did not run. Measured on the machine by holding one
key at a time and reading `INPUT_NOW`: `\` set `IN_RUN` and SHIFT did
not, and with the bit moved it is the other way round. **The lesson is
in §10** — the CPC's key matrix is usually tabulated bit 7 first and
this engine numbers from bit 0, so every binding in that macro is one
the table has to be read backwards for.

### 8.5 Dual pistols

```
MAG_LEFT     0-7      rounds in left pistol
MAG_RIGHT    0-7      rounds in right pistol
ACTIVE_GUN   0/1      alternates every shot, left first
RELOAD_TIMER frames   1.2 s = 60 frames @ 50 Hz
AMMO_RESERVE bytes    clips add 14
```

14 bullets in flight max, one pool entry per round: `{active, x, y, direction, life}`.

**AN EMPTY GUN HAS NO RECOIL TO PLAY.** The four `shoot` cels are drawn
WITH the muzzle flash in them — it is the pen her skin nearly shared
(§7.1) — so a release on two dry magazines showed a shot that never
left, which is what a play-test reported. `GUN_HAS_ROUND` is
`FIRE_BULLET`'s own first two tests in one place, and `ACT_UPDATE` asks
it before it enters `FIRE` (§8.4): no round, no cels, no flash. The
release still starts the reload, which is what a trigger pull on an
empty gun is for.
**Bullets move 4 pixels on two frames in three.** A round steps whole
BYTES, so a third off the speed is not a smaller step, it is a step it
does not take: `BUL_PHASE` counts 3, 2, 1 in the main loop and both
pools hold still at 1. The loop owns the counter because
`UPDATE_BULLETS` returns early on an empty pool, and their rounds would
otherwise run at a speed that depended on whether she was firing. The
lives went up by half — 60 → 90 frames and 70 → 105 — so the slower
round still reaches as far. Reload is manual (Down+Fire) or
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
round in the air costs **2,160 T with the walk bounded at the deepest
slot taken and 7,568 bounded at `BUL_MAX`**: 5,408 T of every firing
frame was the thirteen DEAD slots behind the first. The frame
had 160 T spare (§9), so tap-firing while the screen scrolled dropped
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
| trigger HELD — she is planted, and aiming fires nothing | 200 | 0 |
| tapping the trigger, 68 frames of it aiming | 200 | 135 |
| ... with `BUL_TOP` forced to `BUL_MAX` | 191 | 129 |

**THE IN-PLAY NUMBERS ARE NOT THE NEGATIVE CONTROL ANY MORE, AND THAT
IS THE INTERESTING PART.** With 160 T of headroom the dead slots dropped
43 frames in 200; with the 3,940 T §9 now has they drop 9, because
5,408 T of overrun mostly fits. A control written as a frame count with
a threshold under it was a hostage to the budget: the day `ENEMY_PICK`
gave 2,200 T back, the same fault measured a third as large and the
threshold failed. **What the mark does is take work off the frame, so
`tools/test_module5.py` times the work** — the two `BUL_TOP` depths
benched from a DI stub — and keeps the in-play comparison only as
"still fewer loops and less ground".

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

**IT TAKES THE FIRST ONE NEAR, DRAWABLE OR NOT, and that is a LEVEL
constraint.** The near zone is `EN_NEAR` = 64 bytes either side of an
80-byte view — 52 tiles — so two enemies can be near at once with only
one drawable, and `ENEMY_PICK` would then keep the wrong one.

Scanning strict first and falling back was written and measured, and
**thrown away**: a second pass over the table on every frame with
nothing drawable takes `ENEMY_PICK` from **764 T to 2,656**, and over a
walk the length of level 1's roof it never once changed the answer.
It cannot: the drones are 40 tiles apart and a 20-tile screen cannot
have one just off its left edge and another drawable at the same time.
`make_city_map.py` asserts the spacing; a level built to the minimum
that assert allows would need the second pass back, and now knows what
it costs.

**And the type row is looked up only once an enemy is NEAR.** The row,
the box and both facings' banks are ~150 T to fetch and the near test
wants none of them — it is `ES_X` against the view and nothing else.
That is 330 T a frame that was spent describing enemies twenty tiles
away, and it is the same cheap reject `ENT_OVERLAP` got (§9).

#### The drone that was drawn and then erased — and it was ADD A,A

A play-test on real hardware reported the drone appearing and then
being lifted off the screen, halfway along the level, rather than
staying until it was killed. **`ENEMY_PICK` was doubling `WORLD_X` in
the accumulator.** `WORLD_X` is in CHARACTERS and reaches 216, so from
character 128 on `ADD A,A` threw the carry away: the view's left edge
came back as 0 instead of 256, every enemy's screen column was out by
256, and the drone she was looking at read as 112 bytes off the left of
the picture — near, not drawable, so the refresh erased it and drew
nothing. Measured: the second drone was on screen for 8 frames instead
of 47, and the fault began on the exact frame `WORLD_X` reached 128.

`ENEMY_PIX_SAFE` had the same line and the same bug. Both now double in
16 bits (`ADD A,A` then `RL H`, 8 T).

**`PLAYER_SCREEN_X` does the same doubling and is CORRECT**, which is
why this was not obvious by inspection: it computes
`KARA_WX - WORLD_X * 2` and both ends are truncated to 8 bits, so
modular arithmetic gives the right small difference. The enemy code
wants a SIGNED 16-bit column — "112 to the left" has to be told from
"144 to the right" — and there the truncation is fatal. **The test to
apply to any `ADD A,A` on a world coordinate is whether the RESULT is
used modulo 256**; `bullets.asm` and `enemy.asm`'s round-vs-tile probes
add `WORLD_X` twice into `HL` and were never affected.

#### And then the heroine flickered when a drone appeared

The next play-test: "when a drone appears the player has flicker" —
Kara, not the drone. Two things were happening on the frame it came
into view and each of them cost her a whole displayed frame.

**A DROPPED FRAME HERE IS NOT A STUTTER, IT IS A HOLE WHERE SHE WAS.**
She is drawn in the top border and erased at her raster gate; if the
work overruns the vblank, `WAIT_VSYNC` waits for the NEXT pulse and the
beam sweeps a whole frame with her already lifted off. One overrun is
one frame with no Kara in the middle of the picture, and the frame
before and after it have her — which is exactly what a flicker is.

**First, the drawable window is a hard edge and the drone jitters
across it.** It patrols a byte at a time against a two-byte camera
step, so walking up to the first one its screen column read **70, 71,
69** on three consecutive frames: drawable, not drawable, drawable. The
refresh drew it, lifted it off and drew it again, and two of those
three frames overran — measured, 39,941 µs each against a 19,968 µs
frame. `EN_HYST` = 4 bytes is the fix: **coming in it has to clear the
edge by four bytes; going out the strict fit is still the bound**,
because that one is the incoming column's and is not negotiable.

**Second, one draw is 15,520 T and the frame has between 5,300 and
14,600 left.** Measured over a walk past a drone by stepping to the
instant `ENEMY_REFRESH` is reached and reading the interrupt tick: it
is **tick 5 on the roomy frames and tick 6 on the tight ones, with
nothing in between**, and which one a frame is alternates with the
incoming column's two halves. So the entry draw waits for a frame it
fits in and the tick is the clock that says which — `EN_DRAW_TICK` = 5.
That alone is still 240 T short, so it also takes the frame
`ENT_UPDATE` does NOT sweep the pickups on: the same alternation the
deferred path already used, worth 2,800 T. The two together leave about
2,500 T of margin.

**Only the entry waits, and only for `EN_DEFER_MAX` = 5 frames.**
Lifting stale pixels off is 1,600 T and cannot wait — the incoming
column is about to recycle them — and a level whose every frame is
tight must still show its enemies, so after five deferred frames it is
drawn wherever the beam is. The drone comes on screen one or two frames
later than it did, four bytes further in, at the edge of the picture.

Measured end to end over the encounter, the worst frame in it is now
**74,584 T of 79,872** and nothing overruns, where before there were
two doubled frames three frames apart. `tools/test_enemies.py` reports
**200 loop iterations in 200 hardware frames on all five input paths**;
two of them were 199 and are the transients §9 used to name.

#### A drone that is killed falls out of the sky, flashing

It used to vanish on the frame the last round landed, which reads as a
bug rather than a kill: the shot and the disappearance are the same
frame, so nothing on screen says one caused the other. `ES_DIE` is a
counter in the slot's spare byte and `ENEMY_WOUND` sets it to
`EN_DIE_FRAMES` = 40 instead of letting the slot go quiet:

* `ENEMY_PICK` keeps picking a slot whose hit points are 0 while that
  counter runs;
* `ENEMY_DYING` takes it away from the patrol and the gun and drops it
  a pixel a frame more every four, to `EN_DIE_VY_MAX` = 6. **The fall
  is not physics** — there is no ground under a drone over a roof gap,
  and a death that had to land somewhere would cost a probe a frame for
  something nobody watches;
* the refresh draws it on four frames of that counter and not on the
  next four, and the erase it does anyway IS the dark half — a flash
  costs nothing but the draws it skips;
* at zero the slot goes quiet and the next refresh lifts it off.

Measured from the kill: it falls from world y 98 to 229 over 40 frames,
drawn four frames on and four off, and is gone. The draws go through
`ENEMY_ROOM` (below) like the entry draw does, so the death animates at
about 25 Hz while she walks and every frame while she does not, and
never on a frame that cannot pay for it.

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
| `ENT_UPDATE`'s touch sweep is due | together they are 80,248 T of a 79,872 T frame — over by 376. The sweep takes **one frame in four** and `ENEMY_ROOM` refuses all the odd ones, which is more conservative than it needs to be and deliberately so (§9). Neither loses anything: she cannot cross a 4-byte pickup in the byte a frame she can travel. The INTERACT pass still runs every frame, because a keypress lasts one. |

**AND THE PHASE IS NOT ARBITRARY ANY MORE: THE SWEEP TAKES ONE ODD
FRAME IN FOUR, AND WHICH ONE IS MEASURED.** She steps on even frames and
`CAMERA_DECIDE` asks for the scroll there, so `H_HEAD` paints fourteen
rows of the incoming column on that frame and `H_TAIL`'s six land on the
next — 13,872 T against 4,920, and the sweep belongs with the cheaper
half. It was the even ones, which is the head's own frame; moving it is
worth **3 loop iterations in 200 walking and 7 running**. Quartering it
is worth **11 more running** and nothing walking, and choosing phase 3
over phase 1 is worth **8 and 15 on the two firing paths** — §9 has both
tables and the play-test that asked for them.
`tools/test_entities.py` drives all four phases of the beat and runs her
over the roof's key, with the gate slowed to one frame in 64 as the
control.

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

**AND IT HAS TO BE ON THE SCREEN BEFORE IT CAN SHOOT.** Live and drawn
are a few frames apart now — it has to clear the drawable edge by
`EN_HYST` and then wait for a frame with room for its draw — so it
could open fire from a screen the player cannot see it on. Rounds
arriving out of nowhere are not a difficulty setting: `ENEMY_DREW` is
the honest test, and the sight test is what it costs.
`tools/test_enemies.py` holds its pixels off the screen for 260 frames
in its sights and watches nothing leave the gun, then lets go of
`ENEMY_DREW` and watches it fire — which is what keeps the first half
from passing on a dead gun.

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

**AND SO IS THE GARAGE.** It is four tiles wide and five tall, standing
on the pavement in the same plane as the brick around it, and its five
tiles were `TA_SOLID`: a wall across the street. Her box is three tiles
wide, so `BOX_SOLID_H` refused every step into it and the pavement
beyond one was somewhere she could not walk — the street is cut in two
at tiles 30 and 90, and the crate at tile 18 is the only other thing on
it (which she can jump). A shut door is something she opens with the
key (`EK_DOOR`, §8.6); it is not something the physics stops her at, and
what stops her walking THROUGH it is that there is nothing behind it to
walk to. The locks keep `TA_TRIGGER`, which nothing reads yet.

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

#### And the other way off: the gap between two buildings

A ladder is the way down you choose. **`drop` is the one you do not**,
and nothing in a level with an unbroken roof can ever play it — so the
City's roof is open at three tiles, `ROOF_GAP`, from the roof's own row
down to the pavement. Walking off its edge is a 128-pixel fall to the
street and the only thing in the level that drives the vertical camera
faster than it can follow.

**Three tiles, and the number is `BOX_SOLID_V`'s.** It ORs the
attributes of every tile under her box, and her box is 6 bytes against
a 4-byte tile — two of them, three when it is not aligned — so a
two-tile gap has positions where she is still standing across solid
roof. Three gives seven byte positions where every tile under her is
open, which she reaches whether she is walking or running.

**And it is at tile 95 because the longest walk any suite makes along
this roof reaches tile 83** — measured by holding the joystick right
for the 290 frames `tools/test_enemies.py` holds it and reading
`KARA_WX` back. `make_city_map.py` asserts the margin. A hole in front
of those walks would turn every one of them from a test of the scroll
into a test of the fall, silently, which is the same failure its header
warns about for a step UP in the roof line.

**AND SHE CAN JUMP IT — AT A RUN.** A gap you can only fall into is a
wall with a longer animation, and this one was very nearly that: the
take-off window was the ten bytes before the lip and a press one frame
later did nothing at all. `P_COYOTE` (§8.4) is what makes it a jump a
player can make — the window is 14 frames, measured, with a control at
each end. Jumping too early still lands her in the hole, which is what
makes it a gap.

**Every one of those measurements is a RUN's now.** The arc is the same
15 frames whatever she is doing and what changed is how far they carry
her: a run covers a byte a frame and clears the 12-byte hole exactly as
the window was derived, and the half-speed walk (§8.2) covers 7 bytes
and does not. That is a design fact and not a defect — **the gap is what
the run is for** — and `tools/test_climb.py` carries it as a third
control beside the two ends of the window: the same press off the same
lip, walking, lands her on the street.

#### And the third way off it: over the edge, hand over hand

A ladder is the way down the level gives you and the gap is the one it
does not. **The ledge is the one the floor gives you**: DOWN pressed at
the lip of the roof and she crouches, takes hold of it and hangs off it
on the `hang` cels §7.1 describes. `EDGE_ENTER` and `PLAYER_HANG` in
`player.asm` are the whole of it, and three things in them are the
art's rather than the code's:

* **which way she faces is the WALL, not the drop.** The cel is drawn
  with the building to her right, so a right-hand lip is the mirrored
  one — she turns her back on the drop, which is what a person climbing
  down does;
* **where she snaps to is the grip.** The art puts the hand at column
  11 of the 24-pixel box and the wall from column 12, so the lip's last
  solid byte goes under sprite byte 5 (mirrored) or its first under
  sprite byte 6. A hand gripping two bytes of air is the whole reason
  the anchor is written down;
* **how far she drops is `HANG_DROP` = 58 lines**, which is 64 − 6:
  standing, her feet are on the floor's top line; hanging, the same
  line is line 6 of the box.

**AND THEN IT IS A QUESTION.** Let DOWN up and she waits `HANG_HOLD` =
40 frames and pulls herself back up; press it again inside them and she
lets go, which is a `drop` and not a jump. Holding DOWN holds her there
for ever — the count only starts when the key comes up, so nothing
happens to a player who is thinking about it. Gravity does not run
while she hangs and nothing moves her: the cel is drawn on a fixed lip
and a hand that slides along it is not a hand.

The probe is one byte past the edge she faces, at the line under her
feet, and it is a PRESS and not the key's state — walking to the edge
with DOWN held would otherwise grab it on arrival. `tools/test_climb.py`
drives both answers and carries the control that matters: **DOWN in the
middle of the roof is a crouch and nothing more.**

**AND THAT IS WHY THE LEDGE EXISTS AT ALL, now that a fall costs
something.** 70 lines hanging against 128 walking off the edge, against
a free height of 96 (§8.4): the same street, and one of the two ways
down is paid for.

**The fall outruns the camera and that is not a fault.** She reaches
`P_VY_MAX` in a few frames and covers the 128 pixels in 25; `CAMERA_V`
asks for one character row at a time and a row takes `V_PARTS` frames,
so it arrives about 35 frames later. She stays on the display the whole
way — `SPAN_CLIP_V` clips the bottom, which is what stops the fold over
the top of the picture — and the street is framed by the time she has
landed. `tools/test_climb.py` checks all of it and fills the hole in
for its negative control.

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
body's own edges for nothing, which matters because the frame had 160 T
spare when it was written (§9): adding the offset at each of the six probe sites instead
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

A hardware frame is **79,872 T-states**. **A GAME FRAME IS TWO OF THEM:
159,744 T at 25 Hz**, and that is the single most important number in
this section.

### The game runs at 25 Hz, and a play-test is what settled it

**A frame this loop drops is not a stutter, it is a frame with no
heroine in it.** She is drawn in the top border and erased at her raster
gate, so a frame whose work overruns the vblank sweeps the whole picture
with her already lifted off (§8.7). At 50 Hz the heavy paths could not
make the budget and the table below shows exactly where: 160 loop
iterations in 200 running is **40 holes**, and a play-test called it
what it is — *"it flickers a bit when she runs"*.

**So the loop waits for two VSYNCs and every game frame is displayed
twice.** Measured, that is **100 game frames in 200 hardware frames on
every path** — standing, walking, firing, jumping and firing, running,
running and firing — which is a hard lock with nothing left to drop.

**IT IS NOT "WAIT TWICE": IT IS WHICH HALF OF THE LOOP GOES ON WHICH
HARDWARE FRAME**, and two rules decide it, both the beam's:

| | goes on | because |
|---|---|---|
| the latch, her draw, `H_TAIL`, the HUD, all the logic | frame **A** | unchanged — the beam chase within a frame is what §9 always described |
| **her erase** | frame **B** | she must be on the screen for BOTH sweeps. Erased on A, the second sweep finds her gone — which is the flicker, at 100% |
| **`H_HEAD`** | frame **B** | the incoming column's cells are the left edge of each row BELOW under the old start address (§8.2), so painting them behind the beam only buys the rest of THAT sweep. On A they would be swept a second time before the latch: a 4-pixel column of the wrong tile down the left edge, for a whole displayed frame |
| `ENT_REPAINT_DUE`, `ENEMY_REFRESH` | frame **B** | they change the background and must follow every erase — which is where they already were (§10) |

**The wait is an EDGE, not a level.** `WAIT_VSYNC` tests the level and
the pulse is 16 scanlines (§7.7): on the rare frame whose work ends
inside the pulse a bare wait returns at once, and the erase would land on
the frame of the draw — one blank sweep, the very thing this is for.
`WAIT_VSYNC_END` then `WAIT_VSYNC` costs that frame a third hardware
frame instead, and she stays on the screen through all three.

#### The bug it cost, and it was a gate that was not gating

**The first 25 Hz build tore a column down the side she was running away
from**, on RVM, and passed everything here. It took a play-test, two
wrong theories and one instrument to find.

`H_HEAD` waits for interrupt tick 4 before it paints, so that the
incoming column's cells — which double as the opposite edge one row
along until the latch (§8.2) — go down BEHIND the beam. Measured at the
moment `H_HEAD` is entered, **six ticks had already passed**:
`FRAME_TICK0` is stamped by the interrupt handler on the tick inside
the VSYNC pulse, and at 50 Hz the head sat at the END of the loop body,
thousands of T after the stamp. Moved to the top of the second hardware
frame it now runs **immediately** after `WAIT_VSYNC` — which returns at
the START of the pulse, before the stamping interrupt has fired. The
anchor still held the previous frame's value, `TICK_WAIT` returned at
once, and the head went down at the very top of the frame: ahead of the
beam for every row it doubles as, and on the glass for a whole sweep.

**The tell was that the tick did not matter.** 237 wrong pixels down
column 0 running right, and the SAME 237 at ticks 2, 3, 4 and 5. A gate
whose argument changes nothing is not a gate.

**The instrument that found it was a check with NO MODEL in it.** Every
model here had been wrong at least once — the sync point, the stale
sprite, the lagging digit — so the question became one the picture can
answer alone: *when the view steps one character right, every pixel of
the new frame must be the old frame shifted four Mode 0 pixels left.*
Anything else is wrong on the glass and no model can be blamed. It
named column 0 immediately, and poking `H_HEAD` to `RET` took it from
237 to 11.

**The fix is that the gate anchors itself** at the `WAIT_VSYNC` exit
rather than waiting for the handler — which is what §9's tick table
measures from anyway, and free where waiting for the stamp cost 3 game
frames in 200 running. `COL_HEAD` went 14 → 12 so the head still fits
between tick 5 and the erase.

### What 159,744 T buys, besides the flicker

* **The enemy's gate is gone.** `ENEMY_ROOM` asked whether the frame
  could afford a 15,520 T draw and deferred the entry draw up to
  `EN_DEFER_MAX` frames waiting for one; it now returns "room" always.
  The drone is redrawn **every game frame** instead of one frame in two
  at best and never while the picture scrolled.
* **`ENT_UPDATE`'s touch sweep is back on every frame.** It was on one
  frame in two, then one in four on a measured phase, because the pair
  of it and the enemy redraw was 376 T more than a 50 Hz frame had.
* **The incoming ROW is painted in halves, not quarters** (`V_PARTS` 4 →
  2), so a vertical step is three game frames instead of five.
* **And the agent is affordable on paper for the first time**: 40,760 T
  drawn and erased against a budget of 159,744 with ~87,000 spent. That
  is not the same as saying it fits — nothing has measured it — but the
  entry in "what did not work" that says a second span sprite is
  impossible was written against a 79,872 T frame.

### What it costs

**Every constant counted in frames now counts game frames**, so each was
re-derived to leave the game where it was in REAL time, not in frames:

| | 50 Hz | 25 Hz | |
|---|---:|---:|---|
| walk | 1 byte on one frame in 2 | **1 byte a frame** | 25 bytes/s either way |
| run | 1 byte a frame | **2 bytes a frame** | 50 bytes/s — and 2 bytes IS one CRTC character, so a run scrolls every game frame |
| jump | `P_JUMP` −8, `P_GRAVITY` 1 | **−15, 4** | 15+11+7+3 = the same 36 px in the same 8 hardware frames |
| terminal fall | `P_VY_MAX` 8 | **15** | twice would be 16, which is a whole tile — see below |
| coyote | 6 frames | **3** | |
| the ladder | 1 px a frame | **2** | |
| the ledge | `HANG_BEAT` 10, `HANG_HOLD` 40 | **5, 20** | |
| a round | 2 bytes a frame, 2 frames in 3 | **4 bytes** | |
| reload, hurt flash, a drone's death | 60, 4, 40 | **30, 2, 20** | |
| the cel rate | `KARA_RATE` 0/1 | **1/2** | one more right shift of the art's own dwell |

**`P_VY_MAX` IS THE ONE THAT COULD NOT SIMPLY DOUBLE.** The probe is
destination-only and is exact only while a single step cannot skip a
tile, so 16 — one whole tile — is not available. 15 is as near as a
25 Hz fall can get, which is 94% of the old speed.

**And the physics is sampled half as often.** Her jump is four updates
to the apex where it was eight, and a fall steps 15 pixels where it
stepped 8. Nothing in the level notices — a floor is 16 pixels and the
probe still cannot cross one — but it is the real cost of the decision
and it is what the coyote window and the roof's gap were re-measured
against.

**THE GAME'S BORDER IS BLACK, EXCEPT WHEN SHE IS HIT.** The coloured
profiling bands were a DEVELOPMENT instrument and they went with the
Module 1-3 screen they belonged to; down in the city they were eight
colour changes a frame flickering down the left edge of a night-time
skyline, and they cost about 560 T a frame.

What the border does now is the one thing there is no HUD for yet:
**four frames of red when her health goes down**. A static HUD over a
screen the CRTC is scrolling needs a raster split, and the split needs
a frame this one has not got — §8.3 puts it in module 6 with the 20x11
play area, where the 16-line HUD is already designed. Measured, the
alternatives were a 16-line HUD costing 8,704 T of raster wait in the
interrupt handler (which the budget cannot pay and which would push her
draw into the beam) or a 40-line one that lands free on interrupt tick
3 and takes a fifth of the picture. The border costs two OUTs on the
frames it changes and nothing on the rest, and **it cannot be confused
with the sprite** the way flashing HER could — a heroine who blinks is
the bug this section spent the day removing.

**Do not use border bands to profile.** The dev screen still paints them, and
they are useful for *seeing* where time goes, but they under-report: the emulator
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
| `INPUT_SCAN` / `PLAYER_UPDATE` / `CAMERA_DECIDE` | | 784 / 1,248 / 548 | the ledge, the crouch and the hang |
| `HUD_SERVICE` (§7.8), the view still | | **504** | 3,568 on a step right, 23,856 down a row - the bar, the rounds and the digit |

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

**AND THE TABLE BELOW IS NOW HISTORY, WHICH IS WHY IT IS KEPT.** Every
one of its columns is a 50 Hz measurement — the loop counted against
interrupt ticks, 200 iterations per 200 hardware frames being the lock.
At 25 Hz the lock is **100 per 200 and every path reaches it**, so the
table no longer separates the paths; what it still does is say what each
thing cost while the frame was the budget, which is the record of how
the engine got here and the first place to look when something has to be
taken back out.

| Loop, at 25 Hz | game frames / 200 hardware |
|---|---:|
| standing, walking either way, walking + firing, jumping + firing, running right | **100** |
| running right + firing | **98** |

**IT WAS NOT 100 EVERYWHERE FOR A WHILE, AND THE INVENTORY WAS BLAMED
FOR ALL OF IT.** The six cells of §7.8's inventory group went on the
end of the bottom row and four paths dropped a frame; with `HUD_INV`
poked to `RET` three came straight back, so the six cells were written
into the floors as the cause. **Two of those frames were not the copy
at all** — they were a pickup's repaint disowning the whole strip's
layout on a sweep that had under 484 T to give, which is §7.8's third
measurement and the one that needed an instrument with no model in it.
All four are back. The run-and-fire path is **98 with the whole of
`HUD_SERVICE` silent as well**: its two frames are the run's own cels,
351 span bytes against the 324 of her heaviest `kcore` one.

**EVERY COLUMN OF THIS TABLE IS THE SAME BUILD WITH ONE THING CHANGED**,
in the order the changes happened, so what a row costs can be read off
against what put it there: the bar poked to `RET`, the bar running, the
artist's redrawn land sheet, the walk at half speed (with SHIFT to run —
§8.4), the fourteen pips beside the bar, and the magazine digit after
them. **The last column is what the suites assert**; the run paths did
not exist before the fourth, because SHIFT was bound to a key nobody
presses (§8.4).

| Loop | no bar, old art | + the bar | + the redraw | + the half-speed walk | + the rounds | + the digit | **+ the sweep's quarter** |
|---|---:|---:|---:|---:|---:|---:|---:|
| standing still, under fire | 201 | 199 | 198 | 201 | 201 | 201 | **201** |
| walking right with a drone in view | 199 | 199 | 198 | 199 | 198 | 198 | **198** |
| turning round, walking left into it | 194 | 190 | 186 | 193 | 192 | 191 | **191** |
| walking right and FIRING, past a drone | 196 | 195 | 173 | 194 | 184 | 183 | **191** |
| jumping and firing, scrolling | 195 | 193 | 158 | 191 | | 174 | **189** |
| climbing down the ladder | 200 | 200 | 200 | 200 | | 193 | **193** |
| standing on the street | 201 | 201 | 201 | 201 | 201 | 201 | **201** |
| walking the street | 201 | 201 | 201 | 201 | 201 | 200 | **200** |
| **running right, scrolling** | — | — | — | 172 | 161 | 151 | **160** |
| **running right and firing** | — | — | — | 185 | | 151 | **164** |

**THE CLIMB IS WHERE THE ERASE LANDS AND THE RUN IS WHERE THE REDRAW
DOES, AND THEY ARE NOT THE SAME COST.** A climb steps a whole ROW, so
the strip's fourteen cells come back off the TILEMAP at ~59 T a byte —
~13,300 T on the frame the CRTC latches. Measured with `HUD_VACATE`
poked to `RET`, a saturated vertical driver is **201 of 200; with it,
180**: the whole vertical cost is the erase, and the lever is the
save-under ring of §7.8.

**Stepping RIGHT the erase is free and poking `HUD_VACATE` out gives
back NOTHING**, which is the measurement that corrects what this
paragraph used to say. A run's cost is the strip's REDRAW — ~3,568 T on
every camera step, and a run steps every other frame. Poked out one at
a time on the run path, over 200 frames:

| | loops / 200 |
|---|---:|
| as it was | 151 |
| `HUD_VACATE` = `RET` | 151 |
| `BUL_DRAW` + `BUL_ERASE` = `RET` | 151 |
| `ENT_REPAINT_DUE` = `RET` | 152 |
| `EBUL_DRAW` = `RET` | 155 |
| `ENEMY_REFRESH` = `RET` | 163 |
| `ENT_UPDATE` = `RET` | 175 |
| **`HUD_SERVICE` = `RET`** | **183** |

**A run's dropped frames are the LOGIC on an already-full frame, not the
drawing**, and that is what the next entry takes back.

**THE LAST COLUMN IS A PLAY-TEST ANSWER AND IT COST FOUR
INSTRUCTIONS.** *"It flickers a bit when she runs"* — and on this loop
a flicker is not a stutter, it is a frame with no heroine in it (§8.7):
she is drawn in the top border and erased at her raster gate, so a
frame that overruns the vblank sweeps with her already lifted off. 151
of 200 is 49 such frames.

**`ENT_UPDATE`'s touch sweep is one frame in FOUR now**, not one in
two, and what makes that safe is her speed against the overlap rather
than the frame count: four frames is 4 bytes at a run, against a
6-byte box plus a 4-byte pickup, so at least two sweeps land inside the
ten bytes they overlap for. `tools/test_entities.py` runs her over the
roof's key to prove it and slows the gate to one frame in 64 as the
control that she then misses it.

**AND WHICH OF THE TWO ODD PHASES IT TAKES WAS WORTH MORE THAN THE
QUARTERING**, which nothing in a T-state sum could have said. Both keep
the enemy redraw's frames clear (§8.7), and measured over the same six
paths:

| | phase 1 | **phase 3** |
|---|---:|---:|
| walking right and firing | 182 | **191** |
| jumping and firing | 173 | **189** |
| turning round, walking left | 189 | **191** |
| running right | **162** | 160 |
| running right and firing | 159 | **164** |

Phase 3 lands between the drone's own two draws instead of on top of
one: eight frames back on one firing path and fifteen on the other, for
two off the plain run. **Widening `ENEMY_ROOM` to match** — letting the
refresh have the odd frames the sweep no longer takes — was measured
too and is NOT taken: it is worth 185 firing but **155 running**, and
the run is the path the play-test was about.

**THE REDRAW IS THE DEARER OF THE TWO AND IT LANDS ON THE GUN.** Her
heaviest `kcore` cel went from 284 span bytes to **323** — 39 bytes at
the composite's 72 T floor is 2,808 T, and drawn plus erased the cel
went 54,820 to **57,524**. A firing frame already carries the heaviest
cel in the game, a round in the air and a drone, so that is where the
frames went: 42 of the 200 while jumping and firing.

**AND HALVING THE WALK GAVE IT BACK, WHICH NOTHING IN THE BLITTER
COULD.** The walk is a byte every other frame now (§8.2), so the camera
steps on one frame in four instead of one in two and the incoming
column's two halves land on half as many frames. Nothing was made
faster: the work is on fewer frames. Measured on the same build, only
the beat changed — 173 → **194** firing past a drone, 158 → **191**
jumping and firing, 186 → **193** turning round. The logic moved with
it as well, because `PLAYER_X` returns without probing anything on the
frames she does not step on.

**AND THE ROUNDS NEXT TO THE BAR TOOK SOME OF IT BACK OFF AGAIN, AND
THEN THE DIGIT TOOK A LITTLE MORE.** Fourteen pips are seven more
characters of screen-fixed pixels on the bottom row and the magazine
count is a fourteenth, and a firing frame changes the pips as well as
everything else it carries. A step right is 1,188 T with the bar alone,
**2,704** with the pips and **3,568** with the digit — the erase is
still free, because adjacent runs vacate into each other (§7.8).
Measured, firing past a drone went 194 → 184 → **183** and the run
172 → 161 → **151**. At the RIGHT-hand end of the same row, where the
erase is not free, the first two were 178 and 148.

**THE DIGIT COSTS TEN FRAMES OF THE RUN AND ONE OF EVERYTHING ELSE**,
which is the same fact as the run's own row: it is the one element with
no neighbour's content to inherit, so it is written on every frame the
view moves — 864 T — and a run moves the view twice as often as a walk.

**THE RUN IS THE ONE PATH THAT DROPS FRAMES NOW, AND ITS CELS ARE WHY.**
`kextra`'s run cels are **351 span bytes** against the 324 of her worst
`kcore` cel — the heaviest in the game — which is about 4,000 T more on
the frames they land on, and a run steps every frame so the camera steps
every other one. 172 of 200 before the bottom row grew, **151** with it,
and what overruns is measured: the heavy
cel meeting the column's HEAD. Two things were tried and are recorded
because neither is free: at **two** bytes a frame, which is what `P_RUN`
said for as long as SHIFT was unreachable, it is **107 of 200** — a
character of scroll every frame puts `H_HEAD` and `H_TAIL` together and
nothing fits; and moving `ENT_UPDATE`'s touch sweep off the head's frame
(§8.7) is worth **3 iterations walking and 7 running**, which is taken.
What is left is the entry at the bottom of this section.

**It was accepted deliberately.** The alternative was that entry —
dropping the mask on the 74% of her span bytes
that are fully opaque, 56 T a byte against 72, measured at **3,952 T on
this cel** and ~3,900 bytes a facing off the blob. That is a format, an
exporter and a blitter, and it is still on the table; the floors in
`tools/test_enemies.py` are the measurement of what was chosen instead.

**FIRING PAST A DRONE IS THE PATH THAT USED TO DROP FRAMES, AND IT WAS
THE ENCOUNTER.** (It is 194 of 200 now — the half-speed walk, above.) Tap-firing while the screen scrolls is 200 of 200
with the level's drones taken off and 196-200 with them on, tracking how
many of the 200 frames the drone was on screen for — measured over four
starting phases, with the drone-off run as the control, so the cost is
the encounter and not the gun. The frames it loses are frames carrying
the `shoot` cel, which at 54,444 T drawn and erased is the heaviest in
the game, plus one of the drone's two unmissable draws (§8.7).
`ENEMY_ROOM`'s gate cannot see it: the tick is a whole 13,312 T and a
firing frame that reaches the refresh at tick 5 has thousands of T less
than the walking frame the gate was measured against. Tightening the
gate by a whole tick was tried and measured — 196 to 196 — so the cost
is not the refresh, and the entry and exit draws are not negotiable.
**Four frames in 200 while she shoots next to a drone.**

**The two transients that used to be named here are gone, and a play-
test is what found them.** A drone costs 17,968 T and a scrolling frame
cannot carry it, so it is a persistent sprite (§8.7) — but the frame it
came into view on paid whatever it cost, "because what the screen shows
is not negotiable", and that frame is one where Kara has been erased
and is not redrawn until the vblank after next. **She blinked**, twice,
because a hard drawable edge had the drone crossing it three times.
Hysteresis and a tick-gated entry draw (§8.7) put both paths back at
200 of 200. `tools/test_enemies.py` keeps the old numbers as its floors
and prints the reason beside them, because the transient is affordable
and not impossible — a level whose frames are all tight will see it
again.

A scrolling frame on her heaviest cel is **87,328 T of the 79,872
available — over by 7,456**, measured by summing every call the loop
makes. It was 76,324 with 3,548 to spare: the ledge, the crouch and the
hang took `PLAYER_UPDATE` from 704 to 1,248 and `CAMERA_DECIDE` from 108
to 548, the land sheet's redraw is 2,704 of it, and the bottom row is
3,568 more — the walk halving gave some of that back, because
`PLAYER_X` stops probing anything on the frames she does not step on.
The logic is **13,268 T** of the sum. `tools/test_spanblit.py`
re-derives all of it from the routines the loop actually calls rather
than from this paragraph. The three biggest pieces are the span
blitter's draw 43,688, the column 16,536 across its two halves, and the
erase 13,836.

**It was 160 to spare and the 3,780 came out of three places, none of
them the drawing:** `ENEMY_PICK` no longer looks a type row up for an
enemy twenty tiles away (330 T) and no longer runs a second pass
(1,892 T, and it never changed an answer — §8.7); and the game's border
is black, which is eight `BORDER_SET` calls a frame gone (~560 T).

**THAT MODEL IS THE PESSIMISTIC ONE AND THE IN-SITU COUNT IS THE
AUTHORITY, AND IT NOW MATTERS WHICH IS WHICH.** The sum adds the worst
placement of the heaviest cel to the worst of everything else AND to
both halves of the incoming column — and `H_HEAD` and `H_TAIL` only
land on the same frame when she RUNS, which is a step every frame
instead of every other one. Those do not co-occur. The loop counted
against interrupt ticks is what says whether the frame holds, and the
table above is where it holds and where it does not. `tools/test_spanblit.py`
asserts the LIGHTEST cel closes (4,100 to spare) and that the heaviest's
overrun does not grow past the **7,456** it was measured at; the 50 Hz
assertions live where they can be measured, in `tools/test_enemies.py`
and `tools/test_climb.py`.

**The masked tile path was the first claim on the headroom and did not
survive the measurement** — 669 T a cell copied against 1,338-2,007
masked, so two overlay cells in one column would be all of it; the
overlays are composited at build time instead (§7.3).

**The logic is 13,268 T now, not the 5,416 this section used to
record.** `HUD_SERVICE` on a step right is the biggest single piece of
it and `ENT_UPDATE` at 3,288 the next;
`PLAYER_UPDATE` went 704 -> 1,248 and `CAMERA_DECIDE` 108 -> 548 for the
ledge, the crouch and the hang, and `HUD_SERVICE` is 3,568 of it on a
step right.

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
  **5,408 T** of every frame she fired on and dropped 43 frames in 200
  — measured, and visible in play as a character who stops walking
  while she shoots (§8.5). `BUL_TOP` bounds the walk at the deepest slot
  ever taken, which in play is 3.
* **A cheap X reject before the real one.** `ENT_OVERLAP` looks the
  hitbox up and tests both axes, about 450 T to discover that something
  twenty tiles away is twenty tiles away. The widest row of
  `ENT_HITBOX` is 16 bytes, so one 16-bit subtract rejects nearly
  everything: `ENT_UPDATE` 3,200 -> 2,636 with nine entities in the
  level.

The next thing added has to pay for itself out of 3,940 T on a
scrolling frame, or be scheduled onto a frame that is not scrolling —
which is what §8.7 does with the enemies. A `citydrone` is 17,968 and
still does not fit; the agent at 40,760 is not close.

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
3. **THE ROUNDS GO DOWN BEFORE SHE DOES.** They were drawn over her —
   she fires past herself — and her draw is 32,000-40,000 T, so
   `BUL_DRAW` was reached 10,200 µs into the frame with the beam already
   at display line 98. A round leaving her muzzle **on the roof** is at
   line 43-49, which the beam passed at 6,980 µs: written to video RAM
   behind the beam and lifted off again at 13,400, so it was never
   displayed at all. Down **on the street** the same round is at line
   113, the beam gets there at 11,076, and it shows. That is exactly how
   it was reported — *"I only see the bullets at street level"* — and the
   fix is the order: drawn first they are 300 µs in, ahead of the beam
   everywhere. The price is her lead, `BUL_DRAW` being 1,876 T with a
   full pool and nothing at all with an empty one, and the erase order
   is reversed to match (she goes down OVER the rounds, so her
   save-under holds their pixels and has to put them back before they
   restore the background).
4. **`KARA_ERASE` must stay behind the beam**, and still finish before the next
   VSYNC. The IM 1 interrupt is the only raster clock the CPC offers — the 6845
   exposes no scanline register — so the gate is a **whole tick** picked from
   her Y: tick 4 up to Y=38, tick 5 up to 90, tick 6 up to 142. Ticks measured
   from the `WAIT_VSYNC` exit:

   | tick | 1 | 2 | 3 | 4 | 5 | 6 |
   |---|---:|---:|---:|---:|---:|---:|
   | T | 532 | 13,844 | 27,152 | 40,468 | 53,780 | 67,088 |

   The first lands after only 532 T, not a full 52-line period.

   **AND THE GATE IS HER FIRST LINE, NOT HER LAST.** Both walk
   downwards and the erase is FASTER — about 97 T a line plus 24 a span
   byte, against the raster's 256 — so it closes on the beam and the
   line that binds really is the last one. But "the beam has passed her
   last line" is not what that requires: the erase needs its whole run
   to REACH that line, so what it actually needs is

   ```
   start >= beam(her first line) + max over k of (256k - C(k))
   ```

   where `C(k)` is what the erase has spent by its k-th line. Computed
   over all 59 shipped cels from their span widths, the worst that
   maximum comes to is **17.8 scanlines**; `KARA_ERASE_LEAD` is 24.
   Waiting for the beam to clear her last line waits 62, and **that is
   what the fall cost**: low in the picture with the camera stepping
   under her, the erase started in her own frame's last third and ran
   past the vblank. **Four dropped frames down the fall**, and a dropped
   frame here is not a stutter, it is a frame with no heroine in it —
   she has been erased and the next draw waits for the vblank after
   next. *"A little flicker on the fall."* With the measured lead it is
   **0 dropped frames**, and the worst frame in the whole fall is 74,584
   T of 79,872.

   **A finer gate than one tick does not work, and the failure is instructive.**
   A delay loop after the tick can only measure from the moment it is entered,
   so a second one in the same frame adds its whole wait on top of whatever ran
   between them. Splitting the erase into halves gated that way put the lower
   half 13,600 T late and dropped a frame on 12 scrolling frames out of 58 —
   visible on hardware as the sprite flickering while the screen moves.
5. **`RASTER_WAIT` must credit the time already spent.** Its delay can
   only count from the moment it is entered, so a caller that arrives a
   whole tick after the one it asked for used to wait the remaining
   50-odd scanlines *on top of* however long it took to get there. That
   was harmless while the frame had room. With the action state machine
   in it, it became 13,000 T of a 79,872 T frame spent waiting for a
   beam that had gone by 23,000 T earlier, and the loop **dropped 6
   frames in 200 while scrolling** - the whole `ACT_UPDATE` is 724 T,
   so the cost was never the new code. Each whole tick late is 52
   scanlines already owed, and subtracting them is four instructions.
6. **`FRAME_TICK0` is stamped by the interrupt handler, not by the main loop.**
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

**HER RASTER THRESHOLD HAS MOVED TWICE AND IT IS NO LONGER CLEAR OF THE
CAMERA.** At ~576 T a line against the raster's 256 the top border is
her whole lead, and the line she can be drawn from intact is what is
left of it after everything that overran the frame before her:

| | drawn intact from |
|---|---:|
| the 16x48 placeholder | line 13 |
| the 24x64 span sprite, no HUD | line 10 |
| ... with the energy bar at the top | line 29 |
| ... with the bar at the BOTTOM (§7.8) | line 21 |
| ... and then the land sheet was redrawn | **line 43** |
| what the camera can produce (§8.8) | `KARA_Y` 32 to 80 |

**Nothing in that column touches her draw** — the bar is written after
her and the redraw only made the draw longer. What moves the threshold
is the frame OVERRUNNING: the next frame then starts late and she loses
~320 T of lead a line, so every 320 T of overrun is a line off the top
of the picture. `tools/test_module4.py` measures it under a driver that
asks for a vertical step on EVERY frame, asserts she is clean from
`KARA_RASTER_SAFE` down, and asserts that its sweep went ABOVE the
threshold so the check cannot pass vacuously.

**43 is inside the camera's band and that is new.** Every earlier figure
was clear of the 32 the camera can reach; this one is not, so there is a
band at the top of her range where a saturated vertical scroll can let
the beam catch her last lines. It is also right at the edge: line 35
came out torn on one run of the suite and clean on the next, which is
what a threshold looks like from close up. **cpcemu is not the witness
that counts for the raster** (§7.5) — this one is for a play-test on
RVM.

**It used to demand a TORN line up there as well, and that assertion
had to go.** The highest line the vertical driver can put her at is 5,
and line 5 came out torn on one run of the suite and clean on the next
- a few hundred T either side of the beam, with nothing changed between
them that could account for it. That is what a threshold looks like
from close up and it is exactly why the safe line is recorded as 10 and
not as 5; it also makes a terrible assertion, because it fails half the
time for the right reason. The suite prints which way line 5 fell on
each run instead.

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
* **74% of Kara's span bytes are fully opaque** — counted on the
  shipped blob, mask byte by mask byte, and the share did not move
  across the redraw (3,549 of 4,782 before, 3,966 of 5,392 after). The
  save-under is three of the composite's nine instructions and stays
  whatever the mask is, so an opaque byte with the mask dropped from the
  format is 56 T against 72: **3,952 T on her heaviest cel**, and
  ~3,900 bytes a facing off the blob, which would take `kcore` from
  12,290 to about 8,400 and hand level 2 back 8 KB of bank instead of
  671 bytes. It is the biggest lever left on the blitter itself, it is
  the one thing that would pay for the redraw outright, and it costs a
  format change, an exporter change and a blitter rewrite. **It was
  offered and declined** when the redraw put the frame 2,808 T over: the
  dropped frames were taken instead and written into the floors of
  `tools/test_enemies.py`. It is still not big enough to buy an agent.
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
* **THE CPC'S KEY MATRIX IS USUALLY TABULATED BIT 7 FIRST AND THIS
  ENGINE NUMBERS FROM BIT 0.** `KEYBIT` takes the bit as the hardware
  delivers it — row 0 bit 0 is cursor UP — so every published table has
  to be read backwards before it is used. Row 2 read the other way up is
  `CLR, [, RETURN, ], f4, SHIFT, \, CONTROL`, and SHIFT is **bit 5**;
  the engine bound **bit 6** and therefore ran on backslash. Nothing
  failed, nothing looked wrong, and the run state was simply unreachable
  for as long as it existed (§8.4). The check is one line in the
  emulator: hold one key and read `INPUT_NOW`.
* **A GATE THAT COUNTS FROM `FRAME_TICK0` IS NOT ARMED THE INSTANT
  `WAIT_VSYNC` RETURNS.** The anchor is stamped by the interrupt handler
  on the tick inside the VSYNC pulse, and `WAIT_VSYNC` returns at the
  pulse's START — so a `TICK_WAIT` placed immediately after it reads the
  PREVIOUS frame's anchor, finds six ticks already elapsed and returns at
  once. It cost a column of tearing that every suite here passed (§9).
  Anchor such a gate on `IRQ_TICKS` read at the wait's exit, which is
  what §9's tick table measures from; and the test to apply to any raster
  gate is not "is the number right" but **"does changing the number
  change anything"**.
* **`B` IS A LOOP COUNTER SOMEWHERE ABOVE YOU.** `EBUL_HITS_HER` was
  given a second register for the crouch's shorter hitbox and took `B`;
  its caller holds the pool's slot count there and finishes with `DJNZ`,
  so one round landing on her walked the pool 256 times and wrote zeros
  across the core. **On real hardware that is a reset on the second hit
  you take**, which is how it was reported, and it is the entry below
  with a different register. The test to apply is not "is this register
  free here" but "is it free at every call site".
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
2. ~~**Asset exporters**~~ — done: `cpclib.py`, `aseprite2spans.py`, `png2screen.py`,
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
      came out of it, all in §9's new entry. (`png2sprite.py` and the
      16x48 path served the Module 1-3 screen until step 15 deleted
      both);
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
   12. ~~what the play-tests found~~ — done, and all four came off
      real hardware rather than out of a suite: **the drone drawn and
      then erased** was `ENEMY_PICK` doubling `WORLD_X` in the
      accumulator and losing the carry from character 128 on (§8.7);
      **aiming now plants her** (§8.4); **the border is black**, the
      coloured bands being the development screen's (§9); and **the
      roof has a gap** so `drop` is something a player can walk into
      (§8.8). The frame came out 3,780 T lighter for it;
   13. ~~what the SECOND round of play-tests found~~ — done, and the
      first three are one sentence each because the measurement is in
      the section named: **she can jump the gap** — the take-off window
      was ten bytes and a press one frame late did nothing at all, so
      there are `P_COYOTE` = 6 frames of edge after the ground goes
      away and the window is 14 frames (§8.4); **the garage is not a
      wall** — four solid tiles across a pavement she is three tiles
      wide on, cutting the street in two (§8.8); **stopping on a ladder
      holds the climb cel** rather than playing two side-on `hang` cels
      in the middle of a back view, and the state is gone (§8.4, §7.1);
      and **the heroine flickered when a drone appeared**, which was
      two frames of hers dropped to a drawable edge the drone crossed
      three times — hysteresis and a tick-gated entry draw, and all
      five of `test_enemies.py`'s input paths are 200 of 200 now
      (§8.7). `tools/test_climb.py` grew the jump window and the street
      walk, with a control at each end of both;
   14. ~~what the THIRD round of play-tests found~~ — done, and two of
      the four were the raster rather than the code: **the rounds were
      only visible at street level**, because her draw put `BUL_DRAW`
      behind the beam (§9); **the fall flickered**, because the erase
      waited for the beam to clear her LAST line when it only ever
      needed her first plus 24 (§9); **DOWN alone is a crouch** that
      their rounds go over (§8.4); and **a killed drone falls out of the
      sky flashing** instead of vanishing on the frame it was hit
      (§8.7). One regression came out of it and is written down in §10:
      `B` is a loop counter somewhere above you;
   15. ~~delete the Module 1-3 acceptance screen~~ — done. Colour bars,
      the bank verdict, the stripes, the liveness lamps, `GAME_LOGIC`'s
      stand-in walk and the 16x48 masked blitter that drew the
      placeholder heroine over them, plus `png2sprite.py`,
      `make_placeholder_sprites.py` and the two suites whose subject
      they were. 4,625 bytes of core image; the build writes no preview
      PNGs any more either. What module 1 proved is checked in the game
      instead: `tools/test_module1.py` reads `BANK_TEST`'s verdict bytes,
      `IRQ_TICKS` and `FRAME_COUNT`;
   16. ~~the ledge, and three more play-test answers~~ — done: **DOWN
      at the lip of a floor** crouches her, takes hold and hangs her off
      it, with 40 frames to decide between climbing back and letting go
      (§8.8) — which is what the redrawn `hang` tag was for; **a drone
      shoots only once its pixels are on the screen**, because live and
      drawn are a few frames apart now (§8.7); **every round is a third
      slower**, which is a frame in three it does not move rather than a
      step it cannot take (§8.5); and **the border flashes red for four
      frames when she is hit**, because there is no HUD yet. The HUD
      itself is a raster split and the split is module 6's, with the
      measurement in §9.

      **Steps 12-16 are confirmed on Retro Virtual Machine**, which is
      the only witness that counts for the raster: every one of them
      came out of a play-test report and was played back on the same
      machine. The suites are necessary and the hardware is sufficient;
   17. ~~the walk, the run, and the key that was never scanned~~ —
      done, out of a play-test report that the walk was too fast and
      that SHIFT did not run: **the walk is half of what it was** and
      her cycle is halved with it, because the artist's 40-frame cycle
      plants her feet 18 pixels apart and the engine was carrying her 80
      (§8.2, §8.4); **SHIFT was bound to backslash** — row 2 bit 6
      against SHIFT's bit 5 — so the run state was unreachable for as
      long as it had existed (§10); and **the run is a byte a frame**,
      not the CRTC's whole character, because a column every frame is
      25 Hz (§9). The half-speed walk paid the land sheet's redraw back
      in full: the two firing paths of `tools/test_enemies.py` went 173
      to 194 and 158 to 191 of 200, and the suite has two run paths in
      it now. The roof's gap is a run-jump (§8.8), which
      `tools/test_climb.py` drives with the walking press as a third
      control.

      **Confirmed on RVM, and it came back with one more thing: she
      flickers when she runs.** On this loop that is a frame with no
      heroine in it, and 151 of 200 is 49 of them. Measured by poking
      one routine at a time out of the run path, the frames are going to
      the LOGIC on a frame that already carries the incoming column and
      the heaviest cel in the game — not to the drawing and not to the
      strip's erase, which gives back nothing. `ENT_UPDATE`'s touch
      sweep is one frame in four now and on the phase the drone's own
      draws are not on: **160 of 200 running, 164 running and firing,
      and 191/189 on the two firing paths, which are better than they
      have ever been.** §9 has both tables, and `tools/test_entities.py`
      runs her over the roof's key with the gate slowed to one frame in
      64 as the control;
   18. `tools/test_module5.py` — started, with the bullet/tile checks
      and what firing costs her in it. It still owes the rest of the
      module.

   **What the action sheet needs that does not exist yet**: there is no
   `hurt` state, no respawn and no game over. `die` is chosen from
   `PLAYER_HP == 0` and holds its last cel for ever, which is the hook
   the level FSM (step 8) plugs into; `use` and `hurt` are exported and
   nothing plays them. **A deadly fall IS a thing the engine knows
   now**: a drop of more than one and a half of her height costs her the
   excess at a point a pixel, so the roof's 128-pixel gap is 32 points
   and the fourth one kills her (§8.4). What happens then is still
   nothing — `drop` ends in `idle` when she survives and `die` holds its
   last cel when she does not, because there is no respawn to leave
   either of them for.
6. **The level format, engine side** — 8×16 tiles and a 20×11 play
   area (§8.3), which is a rewrite of `tilemap.asm`'s addressing and of
   `collide.asm`'s probes, then a reader for `level_<n>.lvl` and
   `tileflags_<level>.bin`, then one hand-built level played end to
   end. **The masked tile path is not part of it** — §7.3 measured it
   at 1,338-2,007 T a cell against 3,548 T of frame and bakes the
   overlays into new tiles at build time instead, 10 pairs and 640
   bytes for level 1. What is still open is the FORMAT half: a map cell
   is one byte and there is nowhere to say it is an overlay over
   another, so the pairing lives in `make_city_map.py` and an editor
   would have to bake it itself. `tools/make_level.py` writes the same
   bytes the editor will, so the format gets a reference implementation
   and a golden file before anything else is built against it, and
   `tools/test_format.py` reads it back through the engine.

   Its slices: **6a** the format reader (done — `MAP_INSTALL` parses
   `level_1.lvl`, `TILE_ATTR` comes out of `tileflags_level1_city.bin`,
   and the hand-written attribute table is gone); **6b** the overlays
   (done — the bake above); **6c** the HUD (done, and **not** as the
   20x11 play area and 16-line band §8.3 asks for — that is a raster
   split and the frame has not got the 8,700 T it costs, §7.8. What
   shipped is fourteen characters of the bottom row — six health cells,
   her fourteen rounds and a digit for the spare magazines — rewritten
   wherever the view goes, for 504 T standing still, 3,568 on a step
   right and 23,856 down a row, which is the one that hurts);
   **6d** a real X clip for sprites at the screen edges (§8.2).

   **The band is still the right answer and it is still unaffordable**,
   and §7.8 now records what a 23-row playfield would buy and why it
   does not help: it would make the bar's erase free in every direction
   and then oblige the HUD to own all forty cells of row 23, which is
   15,360 T a scroll step. **Only RVM can witness a split** either way
   (§8.2's note on `SCROLL_APPLY`: a real 6845 takes a new start address
   at the next character row and the headless emulator only reloads at
   vtotal).
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

   ~~Two things to settle before it starts~~ — both settled, which is
   what let it start: the tile flag byte is the format's own numbering
   and the engine took it rather than asking the exporter to translate
   (§8.3), and `param0`/`param1` are in §8.6 under the rule that **`p0`
   is always "which thing this is"**.

   **The exporter is done and it is the part that had to be first.**
   `editor/` is a .NET 10 solution of a Domain, an Exporters library and
   an xUnit suite — no web application yet, and deliberately: the first
   thing worth having is not a screen, it is the editor emitting
   `level_1.lvl` byte for byte and the engine reading it. It does both.
   Measured, in this order, each check a stricter witness than the one
   before it:

   | | |
   |---|---|
   | Mode 0 encode → decode → the same pens | 256 of 256, and the wrong table of plan.md §4.2 disagrees on a quarter of the city's real tile bytes, which is what says this is pinning the hardware's |
   | `build/level_1.lvl` read and written again | **2,149 bytes identical**; a single changed map byte breaks it |
   | the ten baked tiles and `citytiles.bin` | **3,264 bytes identical**, the drop of `tank_10` and the chained `tank_21` among them |
   | `tileflags_level1_city.bin` | **51 bytes identical**, each baked tile carrying what is underneath it |
   | **`tools/test_format.py` on the editor's own file** | **all 21 checks, on the emulator, with its three controls intact** |

   ```
   /home/vasilhs/.dotnet/dotnet test editor/CpcLevelEditor.slnx
   ```

   **`.slnx`, not `.sln`** — .NET 10's own solution format, which is what
   `dotnet new sln` writes. And the SDK is not on PATH (§3). The suite
   reads its golden files out of `build/` rather than out of copies:
   a copied golden file stops being golden the first time the generator
   changes and nobody re-copies it.

   Every one of those carries a negative control, because this project's
   rule is that a comparison proves nothing until something shows it
   would have noticed: the plan.md bit table, a flipped map byte, a
   composite done the wrong way round, and the same ten flags moved one
   tile along — which keeps every count right and the file wrong.

   **AND PHASE 2 IS DONE: THE ASSET PACK GOES IN.**
   `CpcLevelEditor.Assets` reads the artist's package and builds a
   tileset out of it — and the measurement that says it is right is the
   one the bake test was already making, only honestly. Level 1's 41
   tiles used to be taken out of the front of `citytiles.bin`, so the
   blob comparison had 2,624 of its 3,264 bytes copied from the file it
   was compared against; imported from the PNG, **all 3,264 are under
   test and they still agree byte for byte.** Four transformations at
   once: the decoder, the quantiser, the column-major packing and the
   frame order.

   | | |
   |---|---|
   | level 1's tiles, imported against `citytiles.bin` | **2,624 bytes identical**, and the whole baked blob with them |
   | every tile sheet in the package | **9 sheets, 6 levels, 275 tiles, 34 overlays** — §7.3's table, re-derived |
   | `tileflags_level1_city.bin`'s artist half | **41 bytes identical** |
   | every `*_sheet.png`, against the size Aseprite recorded | 56 of 56 |

   **THE PNG DECODER IS WRITTEN HERE AND THAT IS DELIBERATE.** An image
   package is a NuGet restore between this repository and a build, for
   two hundred lines that can be checked against the shipped sheets byte
   for byte. It does 8-bit colour types 2, 3 and 6, non-interlaced,
   **which is every one of the 137 PNGs in `assets/` — 77, 58 and 2,
   counted rather than assumed** — and refuses everything else with the
   header it found in the message, because a decoder that guessed would
   return a picture and a wrong picture quantises to a plausible
   tileset. Its own tests hand it all five scanline filters
   on a picture whose pixels are known, since a wrong Paeth decodes most
   real images almost correctly.

   Each check carries a negative control: the palette as it was before
   §7.1 gave pens 1 and 5 to the art produces different bytes (so the
   check would notice which palette was read), and the same 64 bytes
   row-major instead of column-major do too.

   **Four things the import had to be written around**, all found by
   reading the shipped pack rather than the spec: the manifest's `file`
   fields point at `out/frames_*.txt` that do not exist and `city_agent`
   is missing from level 1's manifest altogether, so the sheet is found
   through `tile_table.json` and then by scanning the directory;
   **only `tile_table.json` names every tile** — two sheets of the nine
   carry `tile_names`, one states the frame order in prose, and **five
   say nothing at all** — so the table is the source and the manifest is
   kept as a cross-check, which for level 1 is two independent
   statements of the same order that have to agree; **which tiles are
   overlays is the table's word and never the pixels'**, and level 1
   alone shows why — counted on the bytes the engine gets, its eleven
   overlays run from 32 to 94 transparent pixels of 128 and its thirty
   opaque tiles from 0 to 128, so the best threshold there is still gets
   twelve of the forty-one wrong; and **there is no file anywhere that
   carries collision flags.** `tile_table.json` says how a tile is DRAWN
   and the only statement of what it DOES was a dict written by hand in
   `make_city_map.py` — so the flags are data the EDITOR owns,
   `LevelFlagSeeds` is where level 1's start, and
   `tileflags_<level>.bin` is the output.

   **What is left is phase 3 of editor.md §15**: the painter itself.
   Phase 4 this project does not need.
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
