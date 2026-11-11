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
; cell is PENDING until it is painted, and it is painted in one of two
; places:
;
;   HAZARD_PAINT_B  the second sweep's wait for its head gate - 40,468 T
;                   the loop had always spent doing nothing. Every cell
;                   that does not meet her box as she was drawn goes down
;                   here, ahead of the beam for any cell low enough to be
;                   on the ground, and costs the frame nothing at all.
;   HAZARD_PAINT_A  the top of the first sweep, after the horizontal latch
;                   and before ANY sprite is drawn - so no save-under can
;                   hold the old cel. What is left goes down here: the
;                   cells she is standing in. It costs her lead, ~320 T a
;                   scanline (9), so it is capped at HZ_A_MAX a frame.
;
; THE END OF THE SECOND SWEEP, where a taken pickup's cell is repainted,
; is NOT one of them, and that is a measurement: on level 5 her erase
; ends as late as 72,256 T of 79,872, and one cell is ~3,900.
; =====================================================================

HZ_SPIKETRAP    equ 0           ; p0 of a hazard record: WHICH hazard (8.6)
HZ_KINDS        equ 1           ; ... and how many this engine knows
HZ_CELS         equ 4           ; a trap's cycle, cel 0 the safe one
HZ_MAX          equ 8           ; traps a level may have
HZ_STRIDE       equ 8
HZ_REC          equ 0           ; dw the record
HZ_CELL         equ 2           ; dw its map byte
HZ_WC           equ 4           ; db world character column, 2 * tile
HZ_WR           equ 5           ; db world character row, 2 * tile
HZ_BASE         equ 6           ; db cel 0's tile index
HZ_TC           equ 7           ; db timer << 2 | cel
HZ_TABLE        equ ENT_TABLE + ENT_MAX * ENT_STRIDE   ; &A8C0 - the 64
                                ; bytes between the entity table and
                                ; TILE_ATTR, which nothing else uses

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
HZ_C_TICKS      equ 6           ; ... and at the END of it only before
                                ; this one: 67,088 T, so a cell begun
                                ; there is down by ~72,300 of 79,872

; The link kinds, in docs/editor.md 5.4's own order - the editor's
; LinkKind is the same list and tools/test_forest7.py holds them together.
LK_UNLOCKS      equ 0
LK_DISABLES     equ 1

; THE CYCLE, in game frames - the artist's 200, 70, 200 and 70 ms at
; 40 ms a frame, the 70s rounded up because a cel held for one frame is
; a cel on the screen for one sweep in two.
HZ_DUR:         db 5, 2, 5, 2

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
                ld   iy,HZ_TABLE
.slot:          push bc
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
.live:          sub  4                      ; timer - 1, in the top six bits
                cp   4
                jr   nc,.store              ; ... still running
                inc  a                      ; the next cel
                and  HZ_CELS - 1
                ld   c,a
                ld   b,0
                ld   hl,HZ_DUR
                add  hl,bc
                ld   a,(hl)
                add  a,a
                add  a,a
                or   c                      ; its own timer
.set:           ld   (iy + HZ_TC),a
                and  HZ_CELS - 1
                add  a,(iy + HZ_BASE)
                ld   l,(iy + HZ_CELL)
                ld   h,(iy + HZ_CELL + 1)
                ld   (hl),a                 ; the map - and so the bite
                ld   c,(iy + HZ_WC)
                ld   b,(iy + HZ_WR)
                call HZ_PEND_ADD
                jr   .done
.store:         ld   (iy + HZ_TC),a
.done:          ld   de,HZ_STRIDE
                add  iy,de
                pop  bc
                djnz .slot
                ret

; ---------------------------------------------------------------------
; HZ_PEND_ADD - C = world character column, B = row: a cell to paint.
; A full list drops the cell: the MAP is already right, so what is lost
; is one picture until that cell next changes, and it cannot be full
; with HZ_MAX traps and one altar on it.
;                                destroys AF,HL
; ---------------------------------------------------------------------
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
                xor  a                      ; she has been lifted off
                jr   HZ_PAINT_LIST
HAZARD_PAINT_B: ld   a,HZ_B_TICKS
                ld   (HZ_LIMIT),a
                ld   a,1                    ; she is on the screen: dodge her
HZ_PAINT_LIST:  ld   (HZ_DODGE),a
                ld   a,(HZ_PEND_N)
                or   a
                ret  z
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
                jr   nc,.keep               ; too late in the sweep to begin
                ld   a,(HZ_DODGE)
                or   a
                jr   nz,.her
                ld   a,(H_PENDING)
                or   a
                jr   z,.paint               ; no column in flight
                ld   a,(WORLD_X)
                ld   e,a
                ld   a,c
                sub  e
                inc  a                      ; -1, 0 -> 0, 1 and 38, 39 -> 39, 40
                cp   2
                jr   c,.keep                ; touches column 0
                cp   39
                jr   nc,.keep               ; ... or 39, or is off the screen
                jr   .paint
.her:           call HZ_UNDER_HER
                jr   c,.keep                ; hers to save: C or A paints it
.paint:         call HZ_PAINT
                pop  de
                pop  hl
                pop  bc
                djnz .cell
                jr   .count
.keep:          pop  de
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

; ---------------------------------------------------------------------
; HAZARD_PAINT_A - what C had no room for, at the top of the first
; sweep: after H_COMMIT, so against the view the beam is about to show,
; and before BUL_DRAW, so before any save-under is taken. HZ_A_MAX of
; them a frame, oldest first; the rest wait for the next one. It is the
; fallback and not the rule: C paints the cells she stands in whenever
; the second sweep ends before its tick.
;
; AND ONLY WHILE SHE IS NOT WALKING OR RUNNING, which is a measurement.
; A cell here is ~5,200 T in front of her draw, and a run has 800 T of
; room in its first sweep (CLAUDE.md 9): running across level 7's field
; was 98 game frames in 200 with this painting, 100 with it poked to
; RET - two frames with no heroine in them - and 99 once C took most of
; its cells. Moving, the cell under her is C's at the end of the second
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
                ld   a,(HZ_PEND_N)
                cp   HZ_A_MAX + 1
                jr   c,.n
                ld   a,HZ_A_MAX
.n:             ld   b,a
                ld   hl,HZ_PEND
.cell:          push bc
                ld   c,(hl)
                inc  hl
                ld   b,(hl)
                inc  hl
                push hl
                call HZ_PAINT
                pop  hl
                pop  bc
                djnz .cell
                ; ... and the ones not painted move to the front
                ld   a,(HZ_PEND_N)
                ld   c,a
                cp   HZ_A_MAX + 1
                jr   c,.all
                sub  HZ_A_MAX
                ld   (HZ_PEND_N),a
                add  a,a
                ld   c,a
                ld   b,0                    ; HL is past the painted ones
                ld   de,HZ_PEND
                ldir
                ret
.all:           xor  a
                ld   (HZ_PEND_N),a
                ret

; ---------------------------------------------------------------------
; HZ_UNDER_HER - C, B = a cell's world character column and row: carry
; if its 4 x 16 box meets hers as she was drawn. A cell she was NOT drawn
; over (EN_KH = 0) meets nothing.
;                                destroys AF,DE,HL; keeps BC
; ---------------------------------------------------------------------
HZ_UNDER_HER:   ld   a,(EN_KH)
                or   a
                ret  z                      ; not drawn: carry clear
                push bc
                ld   l,c
                ld   h,0
                add  hl,hl                  ; characters -> bytes
                ld   de,(EN_KX)
                ld   a,(EN_KW)
                ld   c,a
                ld   b,TILE_W_BYTES
                call MEETS
                jr   nc,.apart
                pop  bc
                push bc
                ld   l,b
                ld   h,0
                add  hl,hl
                add  hl,hl
                add  hl,hl                  ; character rows -> lines
                ld   de,(EN_KY)
                ld   a,(EN_KH)
                ld   c,a
                ld   b,TILE_H
                call MEETS
.apart:         pop  bc
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
HZ_PAINT:       ld   a,c
                ld   (HZ_WC0),a
                ld   a,b
                ld   (HZ_WR0),a
                call TILE_SRC               ; HL = the tile's first byte -
                ld   (HZ_SRC0),hl           ; the map is base RAM
                ; ... AND ONLY THEN THE BANK, because BANK_SET_C4 is
                ; `ld bc,&7FC4 : out (c),c`: the first version paged
                ; with the cell's column and row still in C and B, and
                ; every cell came out at column 196, row 127, which is
                ; nowhere - a trap that scrolled in showed cel 0 for as
                ; long as it was on the screen while the map went round
                ; its cycle under it. CLAUDE.md 10's rule about a
                ; register held across a call, one instruction long.
                call BANK_SET_C4
                ld   b,0                    ; B = row within the tile
.row:           ld   c,0                    ; C = column within it
.col:           push bc
                ld   a,(WORLD_CR)
                ld   d,a
                ld   a,(HZ_WR0)
                add  a,b
                sub  d                      ; screen character row
                cp   SCR_CHAR_ROWS
                jr   nc,.skip               ; off the top or the bottom
                ld   d,a
                ld   a,(WORLD_X)
                ld   e,a
                ld   a,(HZ_WC0)
                add  a,c
                sub  e                      ; screen character column - a
                cp   SCR_CHARS              ; difference modulo 256, and no
                jr   nc,.skip               ; true one aliases into 0..39:
                ld   e,a                    ; WORLD_X is at most 216 (8.17)
                ld   a,d
                cp   HUD_ROW
                jr   nz,.addr
                ld   a,e
                cp   HUD_STRIP_CELLS
                jr   c,.skip                ; under the strip
.addr:          ld   a,e
                add  a,a
                ld   c,a                    ; the byte column
                ld   a,d
                add  a,a
                add  a,a
                add  a,a                    ; the row's first line
                call SCR_ADDR               ; HL = its raster 0
                ex   de,hl
                pop  bc
                push bc
                ld   a,c
                rrca
                rrca
                rrca                        ; column * 32
                ld   c,a
                ld   a,b
                rrca
                rrca
                rrca
                rrca                        ; row * 16
                add  a,c
                ld   hl,(HZ_SRC0)
                add  a,l                    ; inside one tile: never carries
                ld   l,a
                call CELL_COPY
.skip:          pop  bc
                inc  c
                ld   a,c
                cp   TILE_CHAR_COLS
                jr   c,.col
                inc  b
                ld   a,b
                cp   2                      ; a tile is two character rows
                jr   c,.row
                jp   BANK_RESTORE

HZ_COUNT:       db 0            ; traps in HZ_TABLE
HZ_DODGE:       db 0            ; HZ_PAINT_LIST: 1 = leave her cells
HZ_PEND_N:      db 0            ; cells on HZ_PEND, which is base RAM past
                                ; the HIGH image (main.asm)
HZ_WC0:         db 0            ; HZ_PAINT's and HZ_ADVANCE_ROW's cell,
HZ_WR0:         db 0            ; world characters
HZ_SRC0:        dw 0            ; ... and HZ_PAINT's tile, in bank C4
