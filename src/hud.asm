; =====================================================================
; hud.asm - the energy bar, and why it is a bar and not a band
;                                                            (MODULE 6)
;
; THE ARTIST'S HUD IS A FULL-WIDTH 16-LINE STRIP (common/mockup_hud.png)
; and this engine cannot afford one. A band that stays still while the
; CRTC scrolls the picture under it needs a raster split, and a raster
; split on a 6845 is NOT a mid-frame write to R12/R13: the address latch
; is reloaded from those registers at vertical total and, on a UM6845R,
; during the scanlines of character row 0 - nowhere else. It is
; `rupture', reprogramming R4 so the CRTC restarts a frame mid-screen,
; and that needs one precisely timed write in the FIRST character row of
; each part. Neither of those rows has an interrupt in it: 4,588 T of
; counted delay to reach display line 0 from tick 2 and 4,096 more to
; reach line 16, against the 3,548 T the frame has spare (CLAUDE.md 9).
;
; SO THE HUD IS WHAT THE FRAME CAN PAY FOR. Six of the artist's own
; health cells, 24x8 Mode 0 pixels, at the BOTTOM left of the picture,
; written into place whenever the view moves - because anything
; screen-fixed on a hardware-scrolled display has to be, the address it
; lives at being the one the CRTC is about to show somewhere else.
;
; AND ONE CHARACTER OF MOVEMENT ONLY CHANGES TWO OF THE SIX. See
; HUD_SERVICE: a shift leaves every cell holding its neighbour's
; content, which is the same content everywhere but where the run of
; full cells ends.
;
; AND THE BOTTOM IS WHY IT IS FREE. At the top it had to be written
; BEFORE her - the beam reaches display line 0 at 18,432 T and her draw
; is 28,000 to 43,000 T long - so every T it spent came off the lead
; the top border gives her, and measured, it took the line she can be
; drawn from intact from 10 down the picture to 29 against a camera
; that never puts her above 32. At row 23 the beam does not arrive
; until 65,536 T, so it is written straight after H_TAIL at about
; 50,000 T with 15,000 to spare, and her draw is untouched.
;
; SHE NEVER OVERLAPS IT, which is what lets it go after her: the camera
; keeps her middle between 64 and 112 (8.8), so her box ends at line
; 144 at the very lowest and the bar starts at 184. Nothing else
; reaches it either - the drone patrols map row 4 and both bullet pools
; travel at the height they were fired from.
;
; The one thing that CAN paint over it is ENT_REPAINT_DUE, which puts
; the tiles back where a pickup was taken; that runs after the beam has
; passed row 23, and entity.asm forces the bar to be written again on
; the next frame, so the damage is never displayed.
; =====================================================================

HUD_CELLS       equ 6                       ; the mockup draws six
HUD_BYTES       equ HUD_CELLS * 2           ; 12 - a cell is 4 pixels
HUD_LINES       equ 8
HUD_ROW         equ SCR_CHAR_ROWS - 1       ; 23 - THE BOTTOM of the picture
HUD_BASE        equ HUD_ROW * SCR_CHARS     ; ... 920 words into the view

; The least health each cell needs to stay lit. Six cells over 100
; points is 16.67 apiece, and cell 0 lights at 1 rather than 0 so that
; "one point left" and "dead" are different pictures.
HUD_STEPS:      db 1, 17, 34, 50, 67, 84

; ---------------------------------------------------------------------
; HUD_SERVICE - what the main loop calls. Re-renders only when her
; health has moved; the copy runs every frame, because the picture
; underneath it may have.
; Clobbers AF,BC,DE,HL
; ---------------------------------------------------------------------
HUD_SERVICE:    ld   hl,(SCROLL)            ; the view just latched
                ld   (HUD_WANT),hl
                ld   de,(HUD_LAST)
                ld   a,l
                cp   e
                jr   nz,.moved
                ld   a,h
                cp   d
                jr   nz,.moved
                ; ---- the view is not moving: only health can have ----
                ld   a,(PLAYER_HP)
                ld   hl,HUD_HP
                cp   (hl)
                ret  z                      ; nothing at all to do
                call HUD_LEVEL
                ret  z                      ; ... and her HEALTH moving is not
                jp   HUD_ALL                ; the same thing as the PICTURE

                ; ---- IT IS MOVING, AND ONE CHARACTER OF MOVEMENT
                ; CHANGES AT MOST TWO OF THE SIX CELLS.
                ;
                ; The bar is c[0..5] with c[i] full while i < lit, so a
                ; shift of one character leaves every cell holding its
                ; NEIGHBOUR'S content - which is the same content
                ; everywhere except at the one place the run of full
                ; cells ends. Going left, word N+j held c[j-1] and wants
                ; c[j]: they differ only at j = lit. Word N is new and
                ; always wants writing. Going right it is the mirror:
                ; word N+5 is new and j = lit-1 is the seam.
                ;
                ; 1,464 T for the two against 4,908 for all six, and it
                ; matters because a camera PAN moves the view every
                ; frame for about twenty of them (CLAUDE.md 8.2) - the
                ; one path where this is drawn on every single frame.
                ; THE STEP IS MASKED TO THE RING, not signed. SCROLL is
                ; 0-1023 and wraps, so the frame it wraps on subtracts
                ; 1000 from 16 and a step of +40 arrives as -984. Taken
                ; as a signed number that is a jump no axis can make and
                ; the whole bar went down the slow path - six DRAW_COLUMNs
                ; and a divide by 40 apiece - once every 1024 words of
                ; scroll. Modulo 1024 there are only four answers and
                ; they are 1, 1023, 40 and 984.
.moved:         or   a
                sbc  hl,de
                ld   a,h
                and  3
                ld   b,a                    ; BC = the step, 0-1023
                ld   c,l
                push bc
                call HUD_VACATE             ; ... put back what it leaves
                pop  bc
                ld   a,(PLAYER_HP)
                ld   hl,HUD_HP
                cp   (hl)
                jr   z,.same_bar
                push bc                     ; HUD_LEVEL wants BC, and the
                call HUD_LEVEL              ; dispatch below still needs the
                pop  bc                     ; step if it comes back Z
                jr   z,.same_bar            ; the health moved and the picture
                call HUD_ALL                ; did not: shift it, do not redraw
                jr   .remember

.same_bar:      ld   a,b
                or   a
                jr   nz,.backwards
                ld   a,c
                dec  a
                jr   nz,.far                ; 1 is the only step right
                ; ---- RIGHT: the new cell is 5, the seam is lit-1 -----
                ld   a,HUD_CELLS - 1
                call HUD_PUT
                ld   a,(HUD_LIT)
                or   a
                jr   z,.remember
                cp   HUD_CELLS
                jr   z,.remember            ; no seam inside the bar
                dec  a
                call HUD_PUT
                jr   .remember

.backwards:     ld   a,b
                cp   3
                jr   nz,.far
                ld   a,c
                inc  a
                jr   nz,.far                ; 1023 is the only step left
                ; ---- LEFT: the new cell is 0, the seam is lit --------
                xor  a
                call HUD_PUT
                ld   a,(HUD_LIT)
                or   a
                jr   z,.remember
                cp   HUD_CELLS
                jr   z,.remember
                call HUD_PUT
                jr   .remember

.far:           call HUD_ALL                ; a bigger jump than the game
                                            ; can make in one frame
.remember:      ld   hl,(HUD_WANT)
                ld   (HUD_LAST),hl
                ret

; ---------------------------------------------------------------------
; HUD_VACATE - repaint the cells the bar is about to stop covering.
;
; THE BAR IS A PERSISTENT SPRITE AND THIS IS ITS ERASE. Its pixels sit
; in the ring at words HUD_LAST..+5; when the start address moves, the
; words it used to own are still on the screen somewhere else, and the
; new write only covers five of the six. Which one is left over depends
; on the direction, and two of the four cannot be seen at all:
;
;   right, +1    the leftover is one character past the bar's right end
;   LEFT,  -1    ... and one past its left, which is off the row
;   DOWN,  +40   the whole bar, one row UP. Visible.
;   UP,    -40   the whole bar, one row down - which at row 23 is off
;                the bottom of the display
;
; THE CELLS ARE FOUND BY ARITHMETIC AND NOT BY CASE, which is what
; makes it general: a word that lands inside the new bar is about to be
; written over, and one that lands past the 960 the display shows has
; fallen into the margin R6 = 24 keeps off it (CLAUDE.md 8.2). The game
; moves the view one character or one row a frame, but
; tools/test_module4.py drives the axes by poking H_REQUEST and
; V_REQUEST with no player behind them, and a bigger jump used to leave
; the bar smeared down every row of the picture.
;
; IN:  BC = the step the view has just taken
; Clobbers AF,BC,DE,HL
; ---------------------------------------------------------------------
; THE FOUR STEPS THE GAME CAN ACTUALLY TAKE ARE NAMED, and the
; arithmetic below is the fallback for the ones only a test can make.
; That is not a micro-optimisation: the general path divides a word
; index by 40 with repeated subtraction, which is 22 iterations for row
; 22, and it then paints each cell with DRAW_COLUMN at 1,148 T. Six of
; them was 17,836 T - a fifth of the frame, on the latch frame of every
; downward row step, and it dropped 23 frames in 200 climbing down
; (CLAUDE.md 7.8). The four answers are constants:
;
;      1  right  word HUD_BASE-1 - the LAST column of row 22, and the
;                incoming column of a step right, so H_TAIL has it
;   1023  left   word HUD_BASE+6, row 23 column 6
;     40  down   the whole bar, row 22 columns 0-5
;    984  up     row 24 - off the bottom of the display, nothing to do
;
; and DRAW_ROW paints a run of cells in ONE row with the map lookup
; hoisted, which is what the run is.
;
; IN: BC = the step, masked to the 1024-word ring by HUD_SERVICE.
HUD_VACATE:     ld   a,b
                or   a
                jr   nz,.high
                ld   a,c
                cp   1
                jr   z,.plus_one
                cp   SCR_CHARS
                jr   z,.plus_row
                jr   .general

.high:          cp   3                      ; 768-1023 are the steps back
                jr   nz,.general
                ld   a,c
                cp   &FF
                jr   z,.minus_one
                cp   256 - SCR_CHARS
                ret  z                      ; 984: it has left the display
                jr   .general

; AND THE STEP RIGHT COSTS NOTHING AT ALL, because H_TAIL has already
; done it. The word the bar leaves behind on a step right is the LAST
; column of row 22 - and the incoming column of a step right IS column
; 39, painted rows COL_HEAD..23 by H_TAIL four instructions before this
; is called (src/main.asm). The step LEFT has no such luck: its incoming
; column is 0 and the word left over is column 6 of the bar's own row.
                assert COL_HEAD <= HUD_ROW - 1
.plus_one:      ret

.minus_one:     ld   h,HUD_ROW
                ld   l,HUD_CELLS

; ONE CELL GOES THROUGH DRAW_COLUMN AND A RUN THROUGH DRAW_ROW, because
; a row hoists the map lookup across the whole run and charges 1,150 T
; of setup to do it. Measured: one cell is 1,148 T down the column and
; 2,100 T along the row; six cells are 6,888 and 6,332. The single-cell
; case is the WALKING one - it is paid on every frame the camera moves
; - so the 950 T is worth the second path.
;
; COL_FIRST and COL_N are put back the way H_TAIL puts them back, and
; for the same reason: DRAW_PLAYFIELD reads the defaults.
;
; H = screen character row, L = character column.
.one:           ld   a,h
                ld   (COL_FIRST),a
                ld   a,1
                ld   (COL_N),a
                ld   a,l
                push af
                call BANK_SET_C4
                pop  af
                call DRAW_COLUMN
                call BANK_RESTORE
                xor  a
                ld   (COL_FIRST),a
                ld   a,SCR_CHAR_ROWS
                ld   (COL_N),a
                ret

.plus_row:      ld   h,HUD_ROW - 1
                ld   l,0
                ld   a,HUD_CELLS

; H = screen character row, L = first column, A = how many.
;
; ROW_FIRST AND ROW_N ARE BORROWED, NOT OWNED. A vertical step walks
; ROW_FIRST across its four frames (tilemap.asm) and a horizontal step
; can latch while one is in flight, so the pair is put back - they are
; one word, which is what makes that two instructions.
.paint:         ld   de,(ROW_FIRST)
                push de
                ld   (ROW_N),a
                ld   a,l
                ld   (ROW_FIRST),a
                push hl
                call BANK_SET_C4
                pop  hl
                ld   a,h
                call DRAW_ROW
                call BANK_RESTORE
                pop  de
                ld   (ROW_FIRST),de
                ret

.general:       ld   (HUD_STEP),bc
                ld   a,1
                ld   (COL_N),a
                xor  a
                ld   (HUD_BANK),a           ; C4 is not paged in yet
                ld   b,0
.cell:          ld   l,b                    ; where this cell's word has
                ld   h,0                    ; landed under the new view
                ld   de,(HUD_STEP)
                or   a
                sbc  hl,de
                ld   de,HUD_BASE
                add  hl,de
                ld   a,h
                and  3                      ; the circular window
                ld   h,a
                push hl
                ld   de,HUD_BASE            ; ... is it inside the new bar?
                or   a
                sbc  hl,de
                ld   a,h
                and  3
                ld   h,a
                ld   de,HUD_CELLS
                or   a
                sbc  hl,de
                pop  hl
                jr   c,.next                ; yes: it is about to be written
                ld   de,SCR_CHARS * SCR_CHAR_ROWS
                or   a
                sbc  hl,de
                jr   nc,.next               ; it has fallen off the screen
                add  hl,de
                ; ---- 40 words is a character row -------------------
                ld   c,0
.row:           ld   a,l
                sub  SCR_CHARS
                ld   l,a
                ld   a,h
                sbc  a,0
                ld   h,a
                jr   c,.col
                inc  c
                jr   .row
.col:           ld   a,l
                add  a,SCR_CHARS            ; the remainder is the column
                push af
                ld   a,c
                ld   (COL_FIRST),a
                ld   a,(HUD_BANK)
                or   a
                jr   nz,.paged
                push bc
                call BANK_SET_C4
                pop  bc
                ld   a,1
                ld   (HUD_BANK),a
.paged:         pop  af
                push bc
                call DRAW_COLUMN
                pop  bc
.next:          inc  b
                ld   a,b
                cp   HUD_CELLS
                jr   c,.cell
                ld   a,(HUD_BANK)
                or   a
                ret  z                      ; nothing needed repainting
                jp   BANK_RESTORE

; ---------------------------------------------------------------------
; HUD_ALL - write all six cells, twelve contiguous bytes a line.
;
; SIX SEPARATE HUD_PUTs WOULD BE 4,908 T AND THIS IS 2,300, because the
; six cells are twelve consecutive bytes on each of the eight lines and
; the per-line address step is then paid once instead of six times.
; That matters where it is called from: HUD_SERVICE runs BEFORE her
; draw, so that her save-under captures the bar (CLAUDE.md 10), and
; everything spent here comes off the lead the top border gives her
; (9). It costs a 96-byte buffer, which HUD_LEVEL fills.
;
; The exception is the fold: at six of the ring's 1024 start positions
; the run crosses the 1024-word seam and comes back at the top of the
; same 2 KB block (6.4), and there it is two LDIRs a line.
; Clobbers AF,BC,DE,HL
; ---------------------------------------------------------------------
HUD_ALL:        ld   hl,(HUD_WANT)
                ld   de,HUD_BASE
                add  hl,de
                ld   a,h
                and  3
                ld   h,a
                add  hl,hl                  ; word -> byte offset, 0-2046
                ld   a,h
                cp   7
                jr   nz,.fast
                ld   a,l
                cp   256 - HUD_BYTES + 1
                jp   nc,.seam               ; the unrolled run below is too
.fast:          ld   a,h                    ; long to jr over
                add  a,SCREEN_BASE >> 8
                ld   d,a
                ld   e,l
                ld   hl,HUD_BUF
                repeat HUD_LINES, line
                repeat HUD_BYTES
                ldi                         ; 20 T a byte against LDIR's 24,
                rend                        ; and BC counts down past zero
                if line < HUD_LINES         ; where nobody reads it
                ld   a,e
                sub  HUD_BYTES
                ld   e,a
                ld   a,d
                sbc  a,0
                add  a,8                    ; the next raster block down
                ld   d,a
                endif
                rend
                ret

.seam:          neg                         ; 256 - l: the BYTES left in this
                ld   (HUD_N1),a             ; block, and the offset is always
                ld   c,a                    ; even, being a word index doubled
                ld   a,HUD_BYTES
                sub  c
                ld   (HUD_N2),a
                ld   a,h
                add  a,SCREEN_BASE >> 8
                ld   d,a
                ld   e,l
                ld   (HUD_DST),de
                ld   hl,HUD_BUF
                ld   a,HUD_LINES
                ld   (HUD_LN),a
.line:          ld   de,(HUD_DST)
                ld   a,(HUD_N1)
                ld   c,a
                ld   b,0
                ldir                        ; ... and HL walks the buffer
                ld   a,(HUD_N2)
                ld   c,a
                ld   b,0
                ld   a,(HUD_DST + 1)
                and  &F8                    ; the top of this same block
                ld   d,a
                ld   e,0
                ldir
                ld   a,(HUD_DST + 1)
                add  a,8
                ld   (HUD_DST + 1),a
                ld   a,(HUD_LN)
                dec  a
                ld   (HUD_LN),a
                jr   nz,.line
                ret

; ---------------------------------------------------------------------
; HUD_PUT - write cell A of the bar at word SCROLL + A.
;
; ONE CELL IS ONE CRTC CHARACTER, which is what makes the 1024-word
; seam free here: the fold is between characters, never inside one, so
; the address is a mask and the eight lines are &0800 apart with no run
; to split (CLAUDE.md 6.4). The eight are unrolled because the
; bookkeeping is most of the cost at two bytes a line.
; IN:  A = 0..5     Clobbers AF,BC,DE,HL
; ---------------------------------------------------------------------
HUD_PUT:        ld   c,a
                ld   hl,HUD_CELL_FULL
                ld   a,(HUD_LIT)
                cp   c
                jr   z,.empty               ; lit == k: k is the first dark
                jr   nc,.source             ; lit >  k: lit
.empty:         ld   hl,HUD_CELL_EMPTY
.source:        ld   e,c
                ld   d,0
                push hl
                ld   hl,(HUD_WANT)          ; the view just latched ...
                add  hl,de
                ld   de,HUD_BASE            ; ... and the bottom row of it
                add  hl,de
                ld   a,h
                and  3                      ; the circular window
                ld   h,a
                add  hl,hl                  ; words are two bytes
                ld   a,h
                add  a,SCREEN_BASE >> 8
                ld   d,a
                ld   e,l
                pop  hl

                repeat 8, line
                ld   a,(hl)                 ; 8
                ld   (de),a                 ; 8
                inc  hl                     ; 4
                inc  e                      ; 4   the offset is even and at
                ld   a,(hl)                 ; 8   most 2046, so +1 stays in
                ld   (de),a                 ; 8   the same 2 KB block
                inc  hl                     ; 4
                if line < 8
                dec  e                      ; 4
                ld   a,d                    ; 4
                add  a,8                    ; 7   the next raster down
                ld   d,a                    ; 4
                endif
                rend
                ret

; ---------------------------------------------------------------------
; HUD_LEVEL - how many cells her health lights, and remember it.
;
; RETURNS Z WHEN THE PICTURE HAS NOT MOVED, and that is the whole point
; of it: six cells over 100 points is 16.67 apiece and a drone's round
; takes EBUL_DAMAGE off her, so most hits change PLAYER_HP without
; changing which cells are lit. Laying the buffer out again and copying
; it is 5,732 + 2,348 T; comparing the count is 20.
;
; Clobbers AF,BC,HL,IX
; ---------------------------------------------------------------------
HUD_LEVEL:      ld   a,(PLAYER_HP)
                ld   (HUD_HP),a
                ld   hl,HUD_STEPS
                ld   b,0
                ld   c,HUD_CELLS
.count:         cp   (hl)
                jr   c,.done                ; below this cell's step
                inc  b
                inc  hl
                dec  c
                jr   nz,.count
.done:          ld   a,b
                ld   hl,HUD_LIT
                cp   (hl)
                ret  z                      ; the same cells are lit
                ld   (hl),a

                ; ---- and lay the bar out, line-major, for HUD_ALL ----
                ; Twelve bytes a line so that the copy is one run, and
                ; only ever done when her health has actually moved.
                ld   ix,HUD_CELL_FULL
                ld   de,HUD_BUF
                ld   a,HUD_LINES
                ld   (HUD_LN),a
.line:          ld   a,(HUD_LIT)
                ld   b,a
                or   a
                jr   z,.empties
.full:          ld   a,(ix + 0)
                ld   (de),a
                inc  de
                ld   a,(ix + 1)
                ld   (de),a
                inc  de
                djnz .full
.empties:       ld   a,(HUD_LIT)
                ld   b,HUD_CELLS
                sub  b
                jr   z,.next                ; all six lit
                neg
                ld   b,a
.dark:          ld   a,(ix + 16)            ; HUD_CELL_EMPTY follows FULL,
                ld   (de),a                 ; sixteen bytes on
                inc  de
                ld   a,(ix + 17)
                ld   (de),a
                inc  de
                djnz .dark
.next:          inc  ix
                inc  ix                     ; both cells' next line
                ld   a,(HUD_LN)
                dec  a
                ld   (HUD_LN),a
                jr   nz,.line
                or   1                      ; NZ: the buffer is new
                ret

HUD_WANT:       dw 0            ; the start address it is being written for
HUD_STEP:       dw 0            ; ... less the one it is written at now
HUD_BANK:       db 0            ; whether HUD_VACATE has paged C4 in yet
HUD_LAST:       dw 0            ; the start address it was last drawn at,
                                ; and 0 is SCROLL_INIT's own, so the first
                                ; frame vacates nothing
HUD_HP:         db &FF          ; the health it was last drawn for, and
                                ; &FF is none she can have, so the first
                                ; frame always draws
HUD_LIT:        db &FF          ; NOT 0 - see HUD_LEVEL: a count that
                                ; matches means the buffer is already right,
                                ; and it is not until it has been laid out once
HUD_N1:         db 0            ; bytes of a line before the 1024-word seam
HUD_N2:         db 0            ; ... and after it
HUD_DST:        dw 0
HUD_LN:         db 0
HUD_BUF:        ds HUD_LINES * HUD_BYTES

                include "hud_art.inc"
