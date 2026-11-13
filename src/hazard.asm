; =====================================================================
; hazard.asm - the forest's spike traps, the altar that stops them, and
; the first reader the level format's LINK section has ever had.
; CLAUDE.md 8.17.
;
; A TRAP IS A MAP CELL WHOSE TILE CHANGES. The artist drew the spike trap
; as a four-cel sprite and the altar as a two-state one, and neither of
; them moves across the screen: what changes is which picture is in the
; cell. tools/make_forest_map.py composites every cel of both over the
; tile it stands on, at build time, into consecutive indexes of the
; forest's tileset - so a trap is cel 0's index in the map and the three
; after it in the blob, and this file moves the cell from one to the
; next by writing ONE BYTE of the map and repainting it.
;
; AND THE BITE IS THE TILE'S, NOT THIS FILE'S. Cels 1-3 carry TA_HAZARD
; in the forest's flag table and cel 0 does not, so HAZARD_HURT (player.
; asm), which has read TA_HAZARD under her last line since the spike pits
; (8.12), bites her the frame a trap she is standing in comes up - an
; edge, exactly as it bites the frame she walks into a pit. Nothing here
; knows she exists, except where its picture would be drawn over hers.
;
; WHERE THE PICTURE GOES DOWN IS THE WHOLE OF THE DIFFICULTY, and it is
; CLAUDE.md 10's rule about anything that changes the background: it
; must not be painted under a sprite whose save-under has already taken
; the old pixels, or that sprite's erase puts them back. So a changed
; cell is PENDING until it is painted, and four passes may paint it
; (CLAUDE.md 8.17, 8.18):
;
;   HAZARD_PAINT_E  the top of the second sweep, before the HUD strip -
;                   a row step leaves the later passes no time, so a few
;                   cells go down here first
;   HAZARD_PAINT_B  the second sweep's wait for its head gate - 40,468 T
;                   the loop had always spent doing nothing - every cell
;                   that does not meet her box as she was drawn
;   HAZARD_PAINT_C  the END of the second sweep, after her erase: the
;                   cells she is standing in
;   HAZARD_PAINT_A  the top of the first sweep, before any sprite is
;                   drawn, and only while she is not moving: what C had
;                   no room for
;
; A MINE (8.19) IS THE THIRD KIND, AND THE FIRST THAT HOLDS. It does not
; go round a cycle: armed until her box meets it, then the fireball and
; the bubbles, then gone for good - a duration of 0 in HZ_DUR is a hold,
; and HZ_TOUCHED is what lets an armed one go. Its picture is a 2 x 2
; block, so a cel is four tiles and HZ_WRITE writes a second column.
; =====================================================================

HZ_SPIKETRAP    equ 0           ; p0 of a hazard record: WHICH hazard (8.6)
HZ_CABLE        equ 1           ; ... the sea's live cable (8.18)
HZ_MINE         equ 2           ; ... and its moored mine (8.19)
HZ_LASER        equ 3           ; ... and the station's laser (8.23)
HZ_KINDS        equ 4           ; ... and how many this engine knows
HZ_CELS         equ 4           ; a trap's cycle, cel 0 the safe one
HZ_MAX          equ 16          ; traps a level may have - a minefield
HZ_STRIDE       equ 8           ; is more than the eight it was (8.19)
HZ_REC          equ 0           ; dw the record
HZ_CELL         equ 2           ; dw its map byte
HZ_WC           equ 4           ; db world character column, 2 * tile
HZ_WR           equ 5           ; db world character row, 2 * tile
HZ_BASE         equ 6           ; db cel 0's tile index
HZ_TC           equ 7           ; db timer << 2 | cel
                                ; HZ_TABLE is in base RAM past the HIGH
                                ; image (main.asm): sixteen slots are 128
                                ; bytes, and the 64 between the entity
                                ; table and TILE_ATTR held eight

HZ_PEND_MAX     equ 16          ; cells waiting to be painted
HZ_A_MAX        equ 1           ; ... and how many of them may cost her
                                ; lead in one frame
HZ_B_TICKS      equ 4           ; a cell is begun in the second sweep's
                                ; wait only before this tick: 40,468 T,
                                ; which is the head gate's own (9). The
                                ; gate says NO EARLIER than tick 4, so
                                ; the head starts up to a cell late and
                                ; the beam is only further ahead of it.
                                ; It was 3, and the field changes all at
                                ; once: 26 game frames of 80 walking
                                ; across level 7's showed a trap a cel
                                ; behind that she was nowhere near. At 4
                                ; it is none, and the second sweep ends
                                ; by 72,848 T at worst, against 73,340
HZ_E_TICKS      equ 3           ; ... and in the pass at its very top,
HZ_E_MAX        equ 3           ; before the strip, only before this one
                                ; and only three cells PAINTED:
                                ; the strip has to be right before the
                                ; beam reaches row 22 - 63,488 T on a real
                                ; 6845 - and a row step down is 32,856 T
                                ; of it (7.8). The pass starts ~3,700 T in
                                ; and a cell is ~5,700, so three leave the
                                ; strip done by ~54,000. Three is a whole
                                ; cable, and tick 2 was one cell short of
                                ; it: measured, the third began 1,900 T
                                ; past the gate
HZ_C_TICKS      equ 6           ; ... and at the END of it only before
                                ; this one: 67,088 T, so a cell begun
                                ; there is down by ~72,300 of 79,872

; The link kinds, in docs/editor.md 5.4's own order - the editor's
; LinkKind is the same list and tools/test_forest7.py holds them together.
LK_UNLOCKS      equ 0
LK_DISABLES     equ 1

; THE CYCLE, in game frames, A ROW A KIND.
;
; The spike trap: the artist's 200, 70, 200 and 70 ms at 40 ms a frame,
; the 70s rounded up because a cel held for one frame is a cel on the
; screen for one sweep in two.
;
; The cable: "1.5 s off, 1 s live; flash one spark frame as warning
; 250 ms before going live" (the sea's manifest), in a trap's four cels
; - off, the warning flash (which does not bite), off again for the
; 250 ms, and live (tools/make_sea_map.py). 30 + 2 + 6 + 25 is 63 game
; frames, 2.5 s, and each is inside HZ_TC's six bits.
; The mine: gone, armed, the fireball and the fireball breaking into
; bubbles (tools/make_sea_map.py). A DURATION OF 0 HOLDS - a running
; timer is never stored at 0, because the frame it would reach 0 it moves
; the cel on and reloads - so a gone mine stays gone and an armed one
; stays armed until HZ_TOUCHED says otherwise. The explosion is the
; artist's four frames in two cels: the flash's 60 ms with the fireball's
; 80 and the bubbles' 120 with the breaking's 100, 140 and 220 ms.
HZ_DUR:         db 5, 2, 5, 2               ; HZ_SPIKETRAP
                db 30, 2, 6, 25             ; HZ_CABLE
                db 0, 0, 4, 5               ; HZ_MINE
                db 20, 10, 10, 10           ; HZ_LASER: off, on, the
                                            ; flicker, on - the artist's
                                            ; 0.8 s and 1.2 s (8.23)
                assert $ - HZ_DUR == HZ_KINDS * HZ_CELS

; WHERE A MINE CAN BE TOUCHED, in bytes and lines of its 2 x 2 tiles: the
; artist's "contact radius about 5 columns x 9 rows around the sphere
; centre (8,11)" - pixels 3..13 across, lines 2..20 down - and her box
; is the swimmer's, because a mine is a thing of the water.
MINE_X0         equ 1
MINE_X1         equ 7
MINE_Y0         equ 2
MINE_Y1         equ 21
MINE_HURT       equ 32              ; two cells of the bar (7.8)

; ---------------------------------------------------------------------
; HAZARD_TICK - one game frame of every trap's cycle. In the second
; sweep's wait, BEFORE H_HEAD: the incoming column is painted out of the
; map, so the map has to be this frame's before it is.
;
; A trap whose record is EF_TAKEN has been disabled by its altar: it
; goes to cel 0 and stays there. Every cel that changes is written to
; the map at once - which is the bite as well as the picture - and its
; cell goes on the pending list for one of the two painters.
;                                destroys AF,BC,DE,HL,IY
; ---------------------------------------------------------------------
HAZARD_TICK:    ld   a,(HZ_COUNT)
                or   a
                ret  z
                ld   b,a
                ld   hl,(KARA_WY)           ; HER TOP CHARACTER ROW, once:
                srl  h                      ; HZ_TOUCHED's cheap reject
                rr   l
                srl  h
                rr   l
                srl  h
                rr   l
                ld   a,l
                ld   (HZ_KROW),a
                ld   iy,HZ_TABLE
.slot:          ld   a,(iy + HZ_TC)         ; 0 IS FOR GOOD: a trap its altar
                or   a                      ; has put down, and a mine that
                jr   z,.next_slot           ; has gone up - nothing moves it
                dec  a                      ; 1 IS AN ARMED MINE, and one more
                jr   nz,.busy               ; than four character rows from
                ld   a,(HZ_KROW)            ; her is all it costs: her box
                sub  (iy + HZ_WR)           ; spans four rows at most and its
                add  a,4                    ; contact box three, so only
                cp   8                      ; -3..2 can meet. An altar that
                jr   nc,.next_slot          ; disarmed one far off is honoured
.busy:          push bc                     ; when she comes this near
                ld   l,(iy + HZ_REC)
                ld   h,(iy + HZ_REC + 1)
                ld   de,ENT_FLAGS
                add  hl,de
                ld   a,(iy + HZ_TC)
                bit  1,(hl)                 ; EF_TAKEN: its altar holds the
                jr   z,.live                ; idol
                and  HZ_CELS - 1
                jr   z,.done                ; ... and it is down already
                xor  a                      ; down, and no timer
                jr   .set
.live:          cp   4
                jr   c,.held                ; a timer of 0: a mine's hold
                sub  4                      ; timer - 1, in the top six bits
                cp   4
                jr   nc,.store              ; ... still running
.next:          inc  a                      ; the next cel
                and  HZ_CELS - 1
                ld   c,a
                inc  hl                     ; HL was the record's flags, and
                ld   a,(hl)                 ; its p0 is next: which hazard,
                add  a,a                    ; which is its row of HZ_DUR
                add  a,a
                add  a,c
                ld   e,a
                ld   d,0
                ld   hl,HZ_DUR
                add  hl,de
                ld   a,(hl)
                add  a,a
                add  a,a
                or   c                      ; its own timer
.set:           ld   (iy + HZ_TC),a
                and  HZ_CELS - 1
                call HZ_WRITE               ; the map - and so the bite
                jr   .done
.held:          dec  a                      ; cel 1 is the ARMED mine, and
                jr   nz,.done               ; cel 0 the one that has gone
                push hl
                call HZ_TOUCHED
                pop  hl
                ld   a,1
                jr   c,.next                ; ... and it goes up
.store:         ld   (iy + HZ_TC),a
.done:          pop  bc
.next_slot:     ld   de,HZ_STRIDE
                add  iy,de
                djnz .slot
                ret

; ---------------------------------------------------------------------
; HZ_TOUCHED - IY = an armed mine's slot. Carry: her box meets where it
; can be touched (MINE_X0..MINE_Y1, above), and she has paid for it.
;
; It is HER box against ITS, in the world and as they are now - not her
; box as she was drawn, which is the painter's question - and the box is
; the swimmer's whatever the level, because only the sea has mines.
; Both differences are one subtraction and one unsigned bound:
; her - it lies in [x0 - W + 1, x1 - 1] exactly when the two meet.
;                                destroys AF,BC,DE,HL; keeps IY
; ---------------------------------------------------------------------
HZ_TOUCHED:     ld   de,(KARA_WY)         ; DOWN FIRST: the sea is a
                ld   l,(iy + HZ_WR)         ; vertical level, so that is
                ld   h,0                    ; the one that is usually far
                add  hl,hl
                add  hl,hl
                add  hl,hl                  ; its top line
                ld   bc,SWIM_BOX_H - 1 - MINE_Y0
                call .near
                ret  nc
                ld   a,l
                cp   MINE_Y1 - MINE_Y0 + SWIM_BOX_H - 1
                ret  nc
                ld   de,(KARA_WX)
                ld   l,(iy + HZ_WC)
                ld   h,0
                add  hl,hl                  ; its left byte
                ld   bc,SWIM_BOX_W - 1 - MINE_X0
                call .near
                ret  nc
                ld   a,l
                cp   MINE_X1 - MINE_X0 + SWIM_BOX_W - 1
                ret  nc
                ld   a,MINE_HURT
                call HURT_HER
                scf
                ret
; HL = it, DE = her, BC = the offset -> L = her - it + BC; NC if that is
; not a byte
.near:          ex   de,hl
                or   a
                sbc  hl,de
                add  hl,bc
                ld   a,h
                or   a
                scf
                ret  z
                ccf
                ret

; ---------------------------------------------------------------------
; HZ_WRITE - A = the cel a trap is now showing: its tile into its map
; cell, and into every cell of its RUN, each one pending a paint.
;
; A TRAP IS A COLUMN OF CELLS, NOT ONE, since the sea (8.18). The
; forest's spike trap is one tile; the sea's cable hangs between two
; anchors and is as tall as the gap between two ledges, and one record a
; cell would spend HZ_MAX on two cables. So the record's p1 carries the
; run's length in its top nibble - the cells BELOW the first - and the
; cel it starts on in its bottom two bits, which is all p1 ever was.
; Every spike trap in the forest has a top nibble of 0, so the forest is
; byte for byte the trap it was.
;
; AND A MINE IS TWO COLUMNS AS WELL AS TWO ROWS (8.19). Its picture is
; four different tiles, not one tile four times, so a cel is FOUR
; consecutive indexes - top left, top right, bottom left, bottom right -
; and cel c's top left is its base + 4c. Its p1 says one cell below, the
; way a cable's does, which is what puts a level with mines on the long
; way here; the second column is this routine's own, and the tool keeps
; a mine off the map's last column so the cell to its right is the next
; byte.
;
; IN : A = the cel, IY = the trap's slot     destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
HZ_WRITE:       ld   e,a                    ; E = the cel
                ld   a,(HZ_RUNS)            ; ... AND A LEVEL WITH NO RUN IN
                or   a                      ; IT PAYS NOTHING FOR THEM: the
                jr   nz,.runs               ; forest's field changes eight
                ld   a,e                    ; cells at once, and the painter
                add  a,(iy + HZ_BASE)       ; had no time to give a record
                ld   l,(iy + HZ_CELL)       ; read for each (8.17's margin)
                ld   h,(iy + HZ_CELL + 1)
                ld   (hl),a
                ld   c,(iy + HZ_WC)
                ld   b,(iy + HZ_WR)
                jp   HZ_PEND_ADD
.runs:          ld   l,(iy + HZ_REC)
                ld   h,(iy + HZ_REC + 1)
                ld   bc,ENT_P0
                add  hl,bc
                ld   a,(hl)                 ; which hazard
                sub  HZ_MINE
                ld   (HZ_WIDE),a            ; 0 for a mine: two columns
                jr   nz,.tall
                sla  e                      ; ... and four tiles a cel
                sla  e
.tall:          ld   a,e
                add  a,(iy + HZ_BASE)
                ld   e,a                    ; E = the tile
                inc  hl
                ld   a,(hl)                 ; p1
                rrca
                rrca
                rrca
                rrca
                and  15
                inc  a
                ld   d,a                    ; D = cells in the run
                ld   l,(iy + HZ_CELL)
                ld   h,(iy + HZ_CELL + 1)
                ld   c,(iy + HZ_WC)
                ld   b,(iy + HZ_WR)
.cell:          ld   (hl),e
                push hl
                call HZ_PEND_ON             ; BC and DE survive it
                pop  hl
                ld   a,(HZ_WIDE)
                or   a
                jr   nz,.down
                inc  hl                     ; its right-hand cell, which
                inc  e                      ; is the next tile
                ld   (hl),e
                inc  c
                inc  c
                push hl
                call HZ_PEND_ON
                pop  hl
                dec  hl
                dec  c
                dec  c
                inc  e                      ; ... and the row below starts
.down:          dec  d                      ; at the next one again
                ret  z
                inc  b                      ; a tile is two character rows
                inc  b
                call MAP_ROW_DOWN           ; HL one map row down, wrapped
                jr   .cell

; ---------------------------------------------------------------------
; HZ_PEND_ADD - C = world character column, B = row: a cell to paint.
; A full list drops the cell: the MAP is already right, so what is lost
; is one picture until that cell next changes, and it cannot be full
; with HZ_MAX traps and one altar on it.
;                                destroys AF,HL
; ---------------------------------------------------------------------
; HZ_PEND_ON is the same for a cell of a RUN, which is refused at the
; door when it is wholly off the left or the right: its column comes in
; from the map, which has the new cel - the passes' .off, before the
; list. A laser off the screen was eight of level 23's twelve cells on
; the frame three changed, and its tick 14,252 T (CLAUDE.md 8.27). The
; forest's spike traps come in at HZ_PEND_ADD and do not pay the 36 T:
; at eight cells a change that was the field's last cell on 4 frames.
; ---------------------------------------------------------------------
HZ_PEND_ON:     ld   a,(WORLD_X)
                sub  c
                add  a,SCR_CHARS - 1        ; -1 .. 39 on the screen -> 0 .. 40
                cp   SCR_CHARS + 1
HZ_OFF_ADD      equ  $ - 1                  ; (test_station's control)
                ret  nc
HZ_PEND_ADD:    ld   a,(HZ_PEND_N)
                or   a
                jr   z,.room
                ; ... ONCE. A trap under her stays pending while its cel
                ; goes on changing, and appended at every change it was
                ; on the list four times a cycle: measured standing in
                ; level 7's field, ten entries for eight traps, every
                ; extra one a paint in front of her draw for a picture
                ; that was already right. The paint reads the MAP, so
                ; one entry paints whatever the cell is by then.
                push bc
                push de
                ld   e,c
                ld   d,b
                ld   b,a
                ld   hl,HZ_PEND
.seen:          ld   a,(hl)
                inc  hl
                cp   e
                ld   a,(hl)
                inc  hl
                jr   nz,.other
                cp   d
                jr   z,.dup
.other:         djnz .seen
                pop  de
                pop  bc
                ld   a,(HZ_PEND_N)
.room:          cp   HZ_PEND_MAX
                ret  nc
                inc  a
                ld   (HZ_PEND_N),a
                dec  a
                add  a,a
                ld   l,a
                ld   h,0
                push de
                ld   de,HZ_PEND
                add  hl,de
                pop  de
                ld   (hl),c
                inc  hl
                ld   (hl),b
                ret
.dup:           pop  de
                pop  bc
                ret

; ---------------------------------------------------------------------
; HAZARD_PAINT_C - what B left, at the END of the second sweep: after
; her erase and the rounds', so there is no save-under on the screen to
; put an old cel back and the cells she is standing in are as safe as
; any other. Only BEGUN before tick HZ_C_TICKS, because a frame that
; runs past the vblank is a frame with no heroine in it (9).
;
; IT IS THE CELLS UNDER HER FEET. B leaves them for fear of her
; save-under and A will not paint while she moves, so walking across
; level 7's field the cell she was standing in was a cel behind the map
; on 65 game frames; with this, 15 - the ones whose sweep ended past
; its tick. Every other cell is B's, and B has room for all of them.
;
; AND NOT IN THE INCOMING COLUMN'S WORDS. While a horizontal step is in
; flight H_HEAD has already painted the head of the incoming column into
; column 0 of the rows below (a step right) or column 39 of the rows
; above (a step left), under the start address that is still on the
; screen (8.2). A tile touching either column is left for B, which
; paints it against the view after the latch.
;
; HAZARD_PAINT_B - the pending cells that are not under her, in the
; second sweep's wait. After ENEMY_SLOT, which has worked out her box as
; she was drawn (EN_KX, EN_KY, EN_KW, EN_KH, world bytes and lines), and
; before the head gate - so a cell is only BEGUN while there is a whole
; tick to spare in front of it.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
HAZARD_PAINT_C: ld   a,HZ_C_TICKS
                ld   (HZ_LIMIT),a
                ld   c,255                  ; as many as there are
                xor  a                      ; she has been lifted off
                jr   HZ_PAINT_LIST
HAZARD_PAINT_E: ld   a,(HZ_PEND_N)          ; HER BOX IN CHARACTERS, ONCE A
                or   a                      ; FRAME: it is the box she was
                ret  z                      ; drawn in, which B's pass later
                call HZ_HER_BOUNDS          ; in this sweep shares - and a
                ld   a,HZ_E_TICKS           ; cell B finds was on the list
                ld   c,HZ_E_MAX             ; here first, since nothing adds
                jr   HZ_PAINT_DODGE         ; one in between (HZ_PEND_ADD)
HAZARD_PAINT_B: ld   a,HZ_B_TICKS
                ld   c,255
HZ_PAINT_DODGE: ld   (HZ_LIMIT),a
                ld   a,1                    ; she is on the screen: dodge her
HZ_PAINT_LIST:  ld   (HZ_DODGE),a
                ld   a,c
                ld   (HZ_BUDGET),a          ; how many it may PAINT - not
                ld   a,(HZ_PEND_N)          ; look at: the cells under her
                or   a                      ; are on the list too, and the
                ret  z                      ; first version counted them
                call HZ_IT_BOUNDS           ; the enemy's box, this pass
                ld   a,(HZ_PEND_N)
                ld   b,a
                ld   hl,HZ_PEND
                ld   de,HZ_PEND             ; the kept ones, compacted
.cell:          push bc
                ld   c,(hl)
                inc  hl
                ld   b,(hl)
                inc  hl
                push hl
                push de
                ld   a,(HEAD_ANCHOR)
                ld   e,a
                ld   a,(IRQ_TICKS)
                sub  e
                cp   HZ_B_TICKS
HZ_LIMIT        equ  $ - 1                  ; the entry's tick, patched
                jr   nc,.spent              ; too late in the sweep to begin
                ld   a,(WORLD_CR)           ; WHOLLY ON THE SCREEN is the
                ld   e,a                    ; answer nearly every time, so it
                ld   a,b                    ; is asked here, inline, and
                sub  e                      ; HZ_WHERE only for the rest
                cp   SCR_CHAR_ROWS - 1
                jp   nc,.where              ; out of line: the rare case
.on:            ld   a,(WORLD_X)            ; WHOLLY OFF THE LEFT OR THE
                ld   e,a                    ; RIGHT, it is off the list: its
                ld   a,c                    ; column comes in from the map,
                sub  e                      ; which has the new cel, and a
                inc  a                      ; paint of it is 1,868 T that
                cp   SCR_CHARS + 1          ; draws nothing (CLAUDE.md 8.23)
HZ_OFF_COL      equ  $ - 1                  ; (test_station's control)
                jp   nc,.off                ; -1, 0 -> 0, 1 and 38, 39 -> 39, 40
                ld   e,a
                call HZ_UNDER_IT            ; NEVER UNDER THE ENEMY, in any
                jr   c,.keep                ; pass: it is not lifted off
                ld   a,(HZ_DODGE)
                or   a
                jr   nz,.her
                ld   a,(H_PENDING)
                or   a
                jr   z,.paint               ; no column in flight
                ld   a,e
                cp   2
HZ_GUARD_L      equ  $ - 1                  ; (named for test_forest7's control)
                jr   c,.keep                ; touches column 0
                cp   39
HZ_GUARD_R      equ  $ - 1
                jr   nc,.keep               ; ... or 39
                jr   .paint
.her:           call HZ_UNDER_HER
                jr   c,.keep                ; hers to save: C or A paints it
.paint:         ld   a,255                  ; the pass's budget, patched:
HZ_BUDGET       equ  $ - 1                  ; three for the one before the
                sub  1                      ; strip, and for the others more
                jr   c,.spent               ; than the list holds
                ld   (HZ_BUDGET),a
                call HZ_PAINT
                ld   a,(HZ_HALF)            ; set only by .where's half case:
                or   a                      ; the ordinary cell pays 28 T for
                jr   nz,.half               ; it and no push of its own
.drop:          pop  de
                pop  hl
                pop  bc
                djnz .cell
                jr   .count
.half:          pop  de                     ; half of it is still to come in:
                pop  hl                     ; its column and row are back out
                dec  hl                     ; of the list it came from, which
                ld   b,(hl)                 ; the compaction has not reached
                dec  hl                     ; (DE <= HL - 2)
                ld   c,(hl)
                inc  hl
                inc  hl
                push hl
                push de
.keep:          xor  a                      ; a half cell may be kept unpainted
                ld   (HZ_HALF),a            ; (her box, the column): never
                pop  de                     ; leave the flag for the next one
                ld   a,c
                ld   (de),a
                inc  de
                ld   a,b
                ld   (de),a
                inc  de
                pop  hl
                pop  bc
                djnz .cell
.count:         ex   de,hl                  ; HL = past the last kept one
                ld   de,HZ_PEND
                or   a
                sbc  hl,de
                srl  l
                ld   a,l
                ld   (HZ_PEND_N),a
                ret
; THE PASS IS OVER - its tick has gone or its budget is spent, and both
; only get worse down the list - so this entry and every one after it
; stay as they are, in one copy, rather than each going round the loop
; to be kept. In the forest that was ~200 us of the eight cells' sweep.
.spent:         xor  a
                ld   (HZ_HALF),a
                pop  de                     ; the kept ones' end
                pop  hl                     ; past this entry
                pop  bc                     ; B = this one and the rest
                dec  hl
                dec  hl
                ld   a,b
                add  a,a
                ld   c,a
                ld   b,0
                ldir                        ; forward, so safe: DE <= HL
                jr   .count
.where:         call HZ_WHERE               ; up and down, against the view
                or   a
                jr   z,.drop                ; far off: its row comes in from
                cp   HZ_EDGE                ; the map, with the new cel
                jr   z,.keep                ; at the edge: wait for it
                cp   HZ_ON
                jp   z,.on
                ld   (HZ_HALF),a            ; half on: paint it, and keep it
                jp   .on
.off:           xor  a                      ; it may have been half on up
                ld   (HZ_HALF),a            ; or down (.where): no flag left
                jp   .drop                  ; for the next one

; ---------------------------------------------------------------------
; HAZARD_PAINT_A - what C had no room for, at the top of the first
; sweep: after H_COMMIT, so against the view the beam is about to show,
; and before BUL_DRAW, so before any save-under is taken. HZ_A_MAX of
; them a frame, oldest first; the rest wait for the next one. It is the
; fallback and not the rule: C paints the cells she stands in whenever
; the second sweep ends before its tick.
;
; AND ONLY WHILE SHE IS NOT WALKING OR RUNNING, which is a measurement.
; A cell here is ~4,100 T in front of her draw (HZ_PAINT_ROW), and the
; run with the gun has 800 T of room in its first sweep (CLAUDE.md 9):
; running and firing across level 7's field with the `ret nz` below a
; NOP and C off, so that A has the cells under her, is 98 game frames in
; 200 against 100 as built - two frames with no heroine in them. (A
; plain run once paid it too, at 5,200 T a cell; it has room for one
; now, and the gun is what it has not.) Moving, the cell under her is C's at the end of the second
; sweep, or B's once she is off it; until then it is a cel behind the
; map - and the BITE is not, because the bite is the map's
; (HAZARD_HURT).
; Standing on a trap, which is when the spikes coming up have to be
; SEEN, she is planted and this paints it on the next frame.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
HAZARD_PAINT_A: ld   a,(HZ_PEND_N)
                or   a
                ret  z
                ld   a,(INPUT_NOW)
                and  IN_LEFT + IN_RIGHT
                ret  nz                     ; on the move: B paints it later
                ; THE SAME WALK AS THE OTHER THREE (8.26), with no tick to
                ; watch - the top of the first sweep, before any sprite of
                ; hers is down - and HZ_A_MAX cells: it dodges the ENEMY's
                ; box, which is on the screen here as everywhere, and it
                ; drops what is off the screen instead of painting nothing.
                ld   a,255
                ld   (HZ_LIMIT),a
                ld   c,HZ_A_MAX
                xor  a                      ; she is not on the screen yet
                jp   HZ_PAINT_LIST

HZ_FAR          equ 0
HZ_EDGE         equ 1
HZ_HALF2        equ 2
HZ_ON           equ 3

; ---------------------------------------------------------------------
; HZ_UNDER_HER - C, B = a cell's world character column and row: carry
; if its 4 x 16 box meets hers as she was drawn. A cell she was NOT drawn
; over (EN_KH = 0) meets nothing.
;
; IN CHARACTERS, against bounds HZ_HER_BOUNDS worked out once for the
; pass - and that is the same question as the byte-and-line one, because
; a tile's left edge 2c is even, so 2c <= n is c <= n / 2 rounded down.
; It was two 16-bit MEETS and ~1,070 T a cell, asked of EVERY cell on
; the list including the ones twenty tiles from her; walking across
; level 7's field the eight that change at once spent about 8,000 T of
; the second sweep on it and the paint ended a cell short of its tick.
;                                destroys AF,HL; keeps BC,DE
; ---------------------------------------------------------------------
HZ_UNDER_HER:   ld   hl,HZ_HX0
                jr   HZ_UNDER_BOX
; ... HZ_UNDER_IT is the same question about the ENEMY's box as it was
; drawn, which HZ_IT_BOUNDS works out once a pass (8.26). A trap and an
; enemy in one level is what this is for: the enemy is a persistent
; sprite, its erase is its next refresh, and a cell painted under the
; box it saved comes back as the old cel the moment it moves.
HZ_UNDER_IT:    ld   hl,HZ_IX0
; HL -> a box's first and last character column, then row
HZ_UNDER_BOX:   ld   a,c
                inc  a
                cp   (hl)
                jr   c,.apart               ; the cell ends left of the box
                inc  hl
                ld   a,(hl)
                cp   c
                jr   c,.apart               ; ... or the box ends left of it
                inc  hl
                ld   a,b
                inc  a
                cp   (hl)
                jr   c,.apart               ; ... or the cell ends above it
                inc  hl
                ld   a,(hl)
                cp   b                      ; ... or the box ends above it:
                ccf                         ; carry, and no carry is a meeting
                ret
.apart:         or   a
                ret

; ---------------------------------------------------------------------
; HZ_HER_BOUNDS - her box as she was drawn (EN_KX, EN_KY, EN_KW, EN_KH,
; world bytes and lines) as the character columns and rows it touches,
; for HZ_UNDER_HER. Not drawn (EN_KH = 0): bounds nothing can meet.
;
; Once a pass and only when there is something to paint. Her box ends
; inside the world - KX + KW <= 512 bytes and KY + KH <= 1,024
; lines - so both halves of each are a byte.
;                                destroys AF,DE,HL; keeps BC
; ---------------------------------------------------------------------
HZ_HER_BOUNDS:  ld   a,(EN_KH)
                or   a
                jr   z,.none
                push bc
                ld   hl,(EN_KX)
                ld   a,(EN_KW)
                ld   b,1                    ; bytes -> characters: / 2
                call .first_last
                ld   (HZ_HX0),de            ; HZ_HX0, then HZ_HX1
                ld   hl,(EN_KY)
                ld   a,(EN_KH)
                ld   b,3                    ; lines -> character rows: / 8
                call .first_last
                ld   (HZ_HY0),de
                pop  bc
                ret
.none:          ld   de,&00FF               ; first 255, last 0: nothing
                ld   (HZ_HX0),de
                ld   (HZ_HY0),de
                ret
; HL = the start, A = the length, B = halvings (B > 0)
;   -> E = start >> B, D = (start + A - 1) >> B, both shifted as WORDS
.first_last:    push hl
                dec  a
                add  a,l
                ld   l,a
                jr   nc,.nc
                inc  h
.nc:            ld   c,b
.end:           srl  h
                rr   l
                djnz .end
                ld   d,l
                pop  hl
                ld   b,c
.start:         srl  h
                rr   l
                djnz .start
                ld   e,l
                ret

; ---------------------------------------------------------------------
; HZ_PAINT - C, B = a cell's world character column and row (even: the
; top left of a tile): its four character cells out of the map, each
; one only if it is on the display - a tile half off either edge still
; has a half on it - and none of them under the HUD strip, which is
; screen-fixed and covers them; the strip's own vacate repaints them
; from the map when it moves (7.8).
;
; THE TILE IS FOUND ONCE AND NOT FOUR TIMES. The first version handed
; each character cell to DRAW_CELL, which looks the map up again and
; then walked down the screen a row at a time with a DJNZ - 7,208 T a
; tile, which at the top of the first sweep is 22 lines of her lead.
; TILE_SRC once, SCR_ADDR per cell and DRAW_CELL's own copy (CELL_COPY)
; is what is left.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
HZ_PAINT:       call TILE_SRC               ; HL = the tile's first byte -
                ld   (HZ_SRC0),hl           ; the map is base RAM; BC kept
                ld   a,(WORLD_X)
                ld   e,a
                ld   a,c
                sub  e
                ld   (HZ_WC0),a             ; the left cell's SCREEN column,
                ld   a,(WORLD_CR)           ; modulo 256 - no true one
                ld   e,a                    ; aliases into 0..39, because
                ld   a,b                    ; WORLD_X is at most 216 (8.17)
                sub  e
                ld   (HZ_WR0),a             ; ... and the top cell's row
                ; ... AND ONLY THEN THE BANK, because BANK_SET_C4 is
                ; `ld bc,&7FC4 : out (c),c`: the first version paged
                ; with the cell's column and row still in C and B, and
                ; every cell came out at column 196, row 127, which is
                ; nowhere - a trap that scrolled in showed cel 0 for as
                ; long as it was on the screen while the map went round
                ; its cycle under it. CLAUDE.md 10's rule about a
                ; register held across a call, one instruction long.
                call BANK_SET_C4
                ld   hl,(HZ_SRC0)
                ld   a,(HZ_WR0)
                call HZ_PAINT_ROW           ; the tile's lines 0-7
                ld   hl,(HZ_SRC0)
                ld   a,l
                add  a,16                   ; ... and 8-15: column-major, so
                ld   l,a                    ; inside the tile, never a carry
                ld   a,(HZ_WR0)
                inc  a
                call HZ_PAINT_ROW
                jp   BANK_RESTORE

; ---------------------------------------------------------------------
; HZ_PAINT_ROW - A = a screen character row (modulo 256), HL = the
; source of the row's LEFT cell, HZ_WC0 = its screen column: that cell
; and the one to its right, each only if it is on the display and not
; under the strip (HZ_VISIBLE).
;
; ONE SCR_ADDR A ROW AND NOT ONE A CELL. The right cell is the next word
; of the ring: two bytes on inside the same 2 KB block, the block bits
; of D kept and its offset bits stepped - which is also right for a
; left cell OFF the left edge, because SCR_ADDR takes a signed column
; and gives the ring's own address one word before the row's start. It
; was a SCR_ADDR, a fetch of the view and the cell's source worked out
; from nothing, four times a tile: 5,204 T against ~3,700 now.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
HZ_PAINT_ROW:   cp   SCR_CHAR_ROWS
                ret  nc                     ; off the top or the bottom
                ld   (HZ_PROW),a
                push hl                     ; the left cell's source
                add  a,a
                add  a,a
                add  a,a
                ld   e,a                    ; the row's first line
                ld   a,(HZ_WC0)
                add  a,a
                ld   c,a                    ; its byte column, signed
                ld   a,e
                call SCR_ADDR               ; HL = the left cell's raster 0
                pop  de                     ; DE = its source
                push hl
                push de
                ld   a,(HZ_WC0)
                call HZ_VISIBLE
                ex   de,hl                  ; DE = the screen, HL = the source
                call c,CELL_COPY
                pop  hl                     ; the left cell's source ...
                ld   a,l
                add  a,32                   ; ... and the right column's
                ld   l,a
                pop  de                     ; the left cell's screen ...
                ld   a,e
                add  a,2                    ; ... and the next word's, with
                ld   e,a                    ; the 2 KB block it is in kept
                ld   a,d
                adc  a,0
                xor  d
                and  7
                xor  d
                ld   d,a
                ld   a,(HZ_WC0)
                inc  a
                call HZ_VISIBLE
                ret  nc
                jp   CELL_COPY

; A = a cell's screen column (modulo 256), HZ_PROW its row: carry if it
; is on the display and not under the strip, which is screen-fixed and
; covers it - the strip's own vacate repaints it from the map when it
; moves (7.8).                     destroys AF,B; keeps DE,HL
HZ_VISIBLE:     cp   SCR_CHARS
                ret  nc                     ; off the left or the right
                ld   b,a
                ld   a,(HZ_PROW)
                cp   HUD_ROW
                scf
                ret  nz                     ; not the strip's row: paint it
                ld   a,b
                cp   HUD_STRIP_CELLS
                ccf                         ; under the strip: no carry
                ret

HZ_COUNT:       db 0            ; traps in HZ_TABLE
HZ_DODGE:       db 0            ; HZ_PAINT_LIST: 1 = leave her cells
HZ_PROW:        db 0            ; HZ_PAINT_ROW's screen row, for the strip
HZ_HX0:         db 0            ; her drawn box in world characters, for
HZ_HX1:         db 0            ; HZ_UNDER_HER (src/hazard_high.asm)
HZ_HY0:         db 0
HZ_HY1:         db 0
HZ_IX0:         db 0            ; ... and the enemy's, for HZ_UNDER_IT
HZ_IX1:         db 0            ; (HZ_IT_BOUNDS, src/books.asm)
HZ_IY0:         db 0
HZ_IY1:         db 0
HZ_HALF:        db 0            ; non-zero: the cell being painted is half on
                                ; the screen and stays on the list - set by
                                ; HZ_PAINT_LIST's .where, cleared at its .keep
HZ_RUNS:        db 0            ; non-zero: some trap here is a run of cells
HZ_WIDE:        db 0            ; HZ_WRITE's: 0 while it writes a mine
HZ_KROW:        db 0            ; her top character row, this tick
HZ_PEND_N:      db 0            ; cells on HZ_PEND, which is base RAM past
                                ; the HIGH image (main.asm)
HZ_WC0:         db 0            ; HZ_ADVANCE_ROW's cell in world characters,
HZ_WR0:         db 0            ; and HZ_PAINT's tile on the SCREEN
HZ_SRC0:        dw 0            ; ... and HZ_PAINT's tile, in bank C4
