# Reading a disc on an Amstrad CPC without the firmware

**Read this before touching `src/disc.asm`.** Every rule here was paid
for with a build that passed every test in this repository and then did
nothing, or hung, on real hardware. Most of them were paid for *twice* —
once in `~/repos/Homeplanet/src/sys/fdc.asm` and once here.

---

## 0. The one-paragraph version

The µPD765 is a separate chip running on its own clock. The headless
emulator (`~/cpcemu`, floooh/chips `upd765.h`) models it as a state
machine that resolves **synchronously** — the instant the last command
byte is written — and it **never runs out of patience**. A real
controller does neither. So every timing assumption and every
"what does the chip do next" assumption in disc code is one cpcemu will
agree with whether or not the hardware would.

> **cpcemu is right about memory, the gate array and the CRTC. It is not
> a witness about the FDC. Confirm on Retro Virtual Machine before
> believing disc code works.**

---

## 1. Decide first: do you need to drive the controller at all?

Two routes, and the cheap one is usually right.

### Route A — let AMSDOS do it, from the BASIC loader

`~/repos/TheShaft` does this. The loader pages each bank over `&4000`
and uses plain `LOAD`, before the game binary ever runs:

```basic
84 OUT &7F00,&C4:LOAD"levels0.bin",&4000
86 OUT &7F00,&C5:LOAD"levels1.bin",&4000
88 OUT &7F00,&C6:LOAD"levels2.bin",&4000
89 OUT &7F00,&C0
```

Note `MEMORY &3FFF` earlier in that loader: BASIC refuses to `LOAD` a
binary below HIMEM with "Memory full", so HIMEM has to come down first.

**Take this route whenever everything fits in RAM at once.** It is a
dozen bytes of BASIC, it uses the firmware's own well-tested driver, and
nothing below applies.

### Route B — drive the µPD765 yourself

Only when the data has to come off the disc **after** the firmware is
gone: the ROMs are disabled, the engine occupies `&0000-&3FFF`, or a
buffer has landed on AMSDOS's workspace at `&A700-&BFFF`. That is this
project (levels are reloaded at every transition and do not all fit) and
it is Homeplanet (a save written mid-game).

The rest of this file is Route B.

---

## 2. The ports, and the three-phase dance

```
&FA7E   bit 0 = motor on            (write)
&FB7E   main status register        (read)
&FB7F   data register               (read / write)
```

`&FB7E` and `&FB7F` differ **in bit 0 alone**. That is load-bearing —
see rule 3.

Main status register:

| bit | name | meaning |
|---|---|---|
| 7 | RQM | a byte can move |
| 6 | DIO | 1 = controller has one *for* us, 0 = it wants one *from* us |
| 5 | EXM | an execution phase is under way |
| 4 | CB | a command is still in progress |

Every command is the same three phases:

```
COMMAND     push N bytes while RQM=1, DIO=0
EXECUTION   push or pull 512 bytes, same handshake, EXM=1
RESULT      pull the result bytes, RQM=1, DIO=1
```

The controller **will not accept a new command until every result byte
has been taken.**

---

## 3. The five rules

### Rule 1 — END OF CYLINDER is not an error

*This is the one that showed a black screen on RVM while all ten suites
passed here.*

A single-sector transfer sends `EOT` equal to `R` — the last sector of
the transfer **is** the sector. So a real µPD765 reaches the end of the
cylinder as a matter of course and reports it: `IC = 01` in ST0 bits
7-6, and ST1 bit 7 (EN). **The bytes are already in memory.** The chip
is saying it has finished.

```asm
                ld   a,(DISC_ST0)       ; WRONG. Calls every successful
                and  &C0                ; single-sector read a failure on
                ret  nz                 ; real hardware.
```

cpcemu returns `IC = 00` for the same transfer, so a test suite built on
it agrees with the wrong check forever.

The right verdict is `FDC_XFER_OK`:

* `IC = 00` → good, plainly.
* `IC = 01` → look further. **NOT READY (ST0 bit 3) first** — an empty
  drive is `ST0 = &48` with `ST1 = &00`, and a check that only looked at
  ST1 called that a successful read. Then a real fault in ST1: missing
  address mark (0), sector not found (2), overrun (4), data error (5).
  **Not bit 7.** Then anything at all in ST2.
* `IC = 10` invalid command, `IC = 11` polling → not ours, fail.

### Rule 2 — the transfer loop watches RQM, DIO and EXM *together*, in one read

Three things can happen and the loop has to survive all of them:

* **The command is refused** — no disc, no such sector, write protected.
  The controller never enters the execution phase at all; it goes
  straight to handing back result bytes. A loop that only waits for
  "ready, wants a byte" waits forever.
* **The transfer ends early** — we were too slow, it gave up, it left
  the execution phase part way through. Same outcome.
* **It has not decided yet.** Testing `EXM` immediately after the last
  command byte is a race: the chip has not entered execution, `EXM`
  reads 0, and code that takes that for a refusal settles down to wait
  for result bytes it is not sending — while it waits for data we are
  not sending. **That is the RVM hang.**

Testing all three in one `AND`/`CP` is free — one more bit in a mask
that was already being compared. Do not "optimise" it back out:

```asm
.byte:          in   a,(c)
                and  FDC_ST_RQM+FDC_ST_DIO+FDC_ST_EXM
                cp   FDC_ST_RQM+FDC_ST_DIO+FDC_ST_EXM
                jr   z,.go              ; executing, and a byte is ready
                bit  5,a
                jr   nz,.byte           ; EXM up, RQM not: not there yet
                bit  7,a
                jr   z,.byte            ; neither: it has not decided
                jr   .result            ; RQM up, EXM down: result phase
```

### Rule 3 — the loop has 32 µs a byte, and the port stays in BC

The controller has no FIFO on this machine. One byte sits in the data
register and it is an **overrun** if it is not taken in about 32 µs —
**128 T-states at 4 MHz.**

Reloading `BC` with the port address twice a byte costs 20 T. That is
not a micro-optimisation, it is the bug: Homeplanet measured 33.1 µs a
byte against the 32 µs deadline and RVM reported `ST1 = &90` — EN with
OVERRUN — on the first sector after a track advance, 63 sectors into the
load. cpcemu feeds the byte synchronously and **can never produce an
overrun**, so the loop passed every test for the life of the project.

`&FB7E` and `&FB7F` differ in bit 0, so `BC` holds the status port for
the whole transfer and the data port is one `INC C` away. Ours counts
104 T; `tools/test_fdc.py` counts it from the source on every run.

Interrupts must be **off** for the whole transfer. A 50 Hz handler that
runs between two bytes loses the sector.

### Rule 4 — drain the result by status, not by count

`READ DATA` returns seven bytes. `SENSE INTERRUPT STATUS` returns two.
**A `SENSE` with nothing pending returns one.** Counting means the count
has to be right everywhere, and being one too high is a wait for a byte
that is never coming.

So: read until `CB` clears. Keep ST0, ST1, ST2; bin the rest.

Run the drain **before the first command too**. AMSDOS ran before us and
the chip keeps its state across the ROMs being switched out, so anything
it left in the result phase would swallow our first command byte — and
then `FDC_OUT` waits for a `DIO` that never clears.

### Rule 5 — a seek is collected with SENSE INTERRUPT STATUS, never by watching CB

`READ DATA` **does not seek.** It takes a cylinder number and checks it
against what is under the head, so arriving on the wrong track is
reported as *sector not found* — in the vocabulary of sectors, with the
word "seek" appearing nowhere.

Watching the drive-busy bit is wrong in both directions at once, and
cpcemu cannot show either because it never sets that bit:

* the datasheet raises it a few microseconds **after** the last command
  byte, so a poll five microseconds later reads zero and falls straight
  through a seek that has not begun;
* it is cleared by `SENSE INTERRUPT STATUS`, not by the head arriving,
  so on a controller that reads the datasheet the other way the loop
  waits for something only the next line can cause.

Ask instead, which is what the CPC firmware does: `SENSE INTERRUPT
STATUS` until ST0 says SEEK END. With nothing pending the reply is
`ST0 = &80` — invalid command, one byte, SE clear — which **is** the
"not yet".

And **flush any seek-end the controller is still holding before issuing
yours**, or the wait takes that stale answer for this seek's and the
read starts while the head is still moving. AMSDOS ran before us; so did
any seek of ours that timed out.

---

## 4. Rules of our own

### Nothing may hang

A black screen with no way out is worse than a level that fails to load.
Every wait that is not the inner transfer loop is counted out, and the
entry point returns carry clear rather than spinning. In this project
`SCROLL_DEMO` then runs **without** the sprite rather than drawing it
out of a bank full of whatever was there.

### Put the result bytes on the screen

There is no text output in this build and a failed load is otherwise
silent. `DISC_DIAG` paints ST0, ST1 and ST2 as 24 blocks in the top-left
corner, so a photograph of the screen is a complete bug report. Both of
Homeplanet's FDC bugs were pinned down that way, after two wrong guesses
had been spent on the seek and on the timing budget.

### Raw sectors, not a file

Implementing directory allocation is several hundred bytes. Writing the
data to raw sectors past anything AMSDOS allocated is a build step:
`tools/dskdata.py` writes from track `DISC_DATA_TRACK` on, checks that
AMSDOS's highest allocated block has not reached there, and emits the
track and sector into an include. It runs twice — once before RASM to
write the include from the stream sizes, once after iDSK to patch the
image — so the two agree by construction.

The trade is honest and worth writing down: copy another file onto the
disc with CP/M and it may land on the level data.

### One sector an operation

Not a multi-sector `READ DATA` with a real `EOT`. Partly because cpcemu
does not implement that form and asserts on it (`upd->sector_info.r ==
upd->fifo[6]`), so a driver written that way could not be tested here at
all — but mostly because it costs nothing: AMSDOS formats with a 2:1
interleave (C1 C6 C2 C7 …) precisely so that reading in ID order leaves
a sector's worth of time between one read and the next, which is what
the command overhead fits into.

---

## 5. Checklist before believing it works

1. `tools/test_fdc.py` passes — including the ten result-byte verdicts
   and the counted transfer loop.
2. `tools/test_levels.py` passes — every bank of every level, byte-exact.
3. **It has been run on Retro Virtual Machine.** Nothing above
   substitutes for this. If it fails there, photograph the top-left
   corner: `DISC_DIAG` has already told you which of the five rules was
   broken.

---

## 6. Where the code is

| | |
|---|---|
| this project | [`src/disc.asm`](../src/disc.asm), [`src/unpack.asm`](../src/unpack.asm), [`tools/dskdata.py`](../tools/dskdata.py) |
| the tests | [`tools/test_fdc.py`](../tools/test_fdc.py), [`tools/test_levels.py`](../tools/test_levels.py) |
| the reference implementation | `~/repos/Homeplanet/src/sys/fdc.asm` — read its comments, they name the failures |
| the firmware route | `~/repos/TheShaft/src/shaft.bas` |
