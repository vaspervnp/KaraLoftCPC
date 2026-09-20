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

; AND THE ROUNDS SHE IS CARRYING SIT STRAIGHT AFTER THE BAR, WHICH IS
; WHAT MAKES THEM NEARLY FREE. The word a run leaves behind when the
; view steps is the one just past its LEFT end (HUD_VACATE), so two runs
; side by side vacate INTO EACH OTHER:
;
;   a step RIGHT   the bar leaves the last column of row 22, which
;                  H_TAIL has just painted, and the ammo leaves column
;                  5 - the bar's own last cell, which the bar writes on
;                  every step right. Nothing to repaint at all.
;   a step LEFT    the bar leaves column 6, which is the ammo's first
;                  cell and the one the ammo writes on every step left;
;                  the ammo leaves column 13, which is the DIGIT and is
;                  rewritten on every move because it has no neighbour
;                  to inherit from; and the digit leaves column 14, and
;                  that one costs a DRAW_COLUMN.
;
; Level 1 scrolls left to right, so the bottom row costs NOTHING to
; erase on the step the game actually makes. At the other end of the
; row it was the mirror and the two did not cancel: a DRAW_COLUMN every
; step whichever way she walked, and two DRAW_ROWs on every row step
; instead of one. Measured, that was 196 loop iterations in 200 walking
; and 148 running, against 199 and 172 with no ammo at all.
;
; ONE ROUND IS ONE PIXEL OF BULLET AND ONE OF GAP, so a 4-pixel cell
; holds two of them and her fourteen are seven characters. The art is
; the artist's own bullet out of hud_icons' `ammo' (tools/make_hud.py),
; and a cell is FULL, HALF or EMPTY because the rounds go out from the
; left: there is at most one half-spent cell and it is the seam.
HUD_AMMO_CELLS  equ 7
HUD_AMMO_BYTES  equ HUD_AMMO_CELLS * 2      ; 14 - a cell is 4 pixels
HUD_AMMO_ROUNDS equ HUD_AMMO_CELLS * 2      ; 14, both magazines
HUD_AMMO_COL    equ HUD_CELLS               ; straight after the bar
HUD_AMMO_BASE   equ HUD_ROW * SCR_CHARS + HUD_AMMO_COL
                assert HUD_AMMO_ROUNDS == MAG_SIZE * 2

; AND ONE DIGIT AFTER THEM: HOW MANY MAGAZINES THE RESERVE IS WORTH.
; A reload takes BUL_MAX rounds out of AMMO_RESERVE (src/bullets.asm),
; so the reserve IS a number of magazines and the digit is that number.
; It is the artist's own, out of hud_digits, and it is one character
; because nine spare magazines is 126 rounds and the game hands out 14
; at a time.
HUD_CLIPS_COL   equ HUD_AMMO_COL + HUD_AMMO_CELLS
HUD_CLIPS_BASE  equ HUD_ROW * SCR_CHARS + HUD_CLIPS_COL

; AND THEN WHAT SHE IS CARRYING, STRAIGHT AFTER THE DIGIT.
;
; An icon a kind and a count beside it: the key and the coins of level
; 1's entity table (CLAUDE.md 8.6), lit while she has one and the same
; silhouette in the dark while she has not - the convention the spent
; rounds already use, so an empty slot is a thing she has not found and
; not a hole in the row. The medkit is not among them because it is
; spent the instant she walks into it (USE_MEDKIT), and the magazines
; are already the digit at column 13.
;
; TWO CELLS FOR THE ICON AND NOT ONE, AND THAT IS THE ART'S ANSWER.
; hud_icons is 8x16 Mode 0 pixels against a strip that is eight lines
; tall, so an icon cannot go in whole; measured over all nine, every
; one is drawn 5 pixels wide inside its 8 and 6 to 9 lines tall, so the
; width already fits two characters and only the height is chosen -
; tools/make_hud.py takes the 8-line window with the most ink in it.
;
; AND THE RUN IS WRITTEN WHOLE, WHICH IS WHAT MAKES IT AFFORDABLE. An
; icon has no neighbour's content to inherit, so every cell of it is
; wrong after a step of one character and all six have to be rewritten
; on every frame the view moves - six HUD_PUTs would be 5,208 T, where
; twelve consecutive bytes on each of eight lines is ~2,700. It is the
; health bar's own argument (HUD_ALL) one group along, and it is why
; the layout lives in a buffer that only a CHANGED COUNT lays out.
HUD_INV_COL     equ HUD_CLIPS_COL + 1
HUD_INV_KINDS   equ 2                       ; the key and the coins
HUD_INV_CELLS   equ HUD_INV_KINDS * 3       ; two of icon and one of count
HUD_INV_BYTES   equ HUD_INV_CELLS * 2       ; 12 - twelve bytes a line
HUD_INV_BASE    equ HUD_ROW * SCR_CHARS + HUD_INV_COL

; THE FOUR OF THEM ARE ONE STRIP as far as HUD_VACATE is concerned -
; columns 0 to 19 of the bottom row - and that is what makes the erase
; nearly free: each one's leftover word is the cell before it, which
; the element to its left writes on the same frame.
HUD_STRIP_CELLS equ HUD_CELLS + HUD_AMMO_CELLS + 1 + HUD_INV_CELLS
                assert HUD_STRIP_CELLS <= SCR_CHARS

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
                ; ---- the view is not moving: only the counts can ----
                ld   bc,0
                call HUD_BAR
                call HUD_AMMO
                call HUD_CLIPS
                ld   bc,0
                jp   HUD_INV

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
                call HUD_VACATE             ; ... put back what both leave
                pop  bc
                push bc
                call HUD_BAR
                pop  bc
                push bc
                call HUD_AMMO
                call HUD_CLIPS
                pop  bc
                call HUD_INV
                ld   hl,(HUD_WANT)
                ld   (HUD_LAST),hl
                ret

; ---------------------------------------------------------------------
; HUD_DISOWN - say that nothing owns the strip's layout any more.
;
; WHAT A REPAINT HAS TO UNDO IS THE LAYOUT AND NOT THE NUMBERS. Every
; group here compares a COUNT and returns when it has not moved, so a
; health she cannot have is not enough: HUD_LEVEL finds the same six
; cells lit by &FF as by 100 and says so with the Z flag, which is the
; whole point of it. &FF is not a number of cells and not a number of
; keys, so it is the layouts that are stamped and a caller that wants
; the strip on the screen again has one call to make.
;
; Clobbers AF
; ---------------------------------------------------------------------
HUD_DISOWN:     ld   a,&FF
                ld   (HUD_HP),a
                ld   (HUD_LIT),a
                ld   (HUD_AMMO_SPENT),a
                ld   (HUD_INV_K),a          ; ... and the same for what she
                ld   (HUD_INV_C),a          ; is carrying
                ret

; ---------------------------------------------------------------------
; HUD_BAR - the six health cells at the bottom LEFT.
;
; IN:  BC = the step the view has just taken, 0 if it has not moved
; Clobbers AF,BC,DE,HL
; ---------------------------------------------------------------------
HUD_BAR:        ld   a,(PLAYER_HP)
                ld   hl,HUD_HP
                cp   (hl)
                jr   z,.same_bar
                push bc                     ; HUD_LEVEL wants BC, and the
                call HUD_LEVEL              ; dispatch below still needs the
                pop  bc                     ; step if it comes back Z
                jr   z,.same_bar            ; the health moved and the picture
                jp   HUD_ALL                ; did not: shift it, do not redraw

.same_bar:      ld   a,b
                or   c
                ret  z                      ; the view is still as well
                ld   a,b
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
                ret  z
                cp   HUD_CELLS
                ret  z                      ; no seam inside the bar
                dec  a
                jp   HUD_PUT

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
                ret  z
                cp   HUD_CELLS
                ret  z
                jp   HUD_PUT

.far:           jp   HUD_ALL                ; a bigger jump than the game
                                            ; can make in one frame

; ---------------------------------------------------------------------
; HUD_AMMO - the fourteen rounds in her two magazines, at the bottom
; RIGHT, emptying from the LEFT.
;
; WHAT IS COUNTED IS WHAT IS IN THE GUNS, not AMMO_RESERVE: the reserve
; is what a reload will find and these are the rounds she can fire now,
; which is what makes them go out one at a time as she shoots.
;
; The whole layout is one number - how many are SPENT - because the
; rounds go out from the left: cells 0..spent/2-1 are empty, the one
; after is half if `spent' is odd, and the rest are full. So a cell's
; picture is a comparison and there is no buffer to lay out (HUD_LEVEL
; needs one because six cells over 100 points is not a comparison).
;
; IN:  BC = the step the view has just taken, 0 if it has not moved
; Clobbers AF,BC,DE,HL
; ---------------------------------------------------------------------
HUD_AMMO:       call HUD_AMMO_STEP          ; 0 still, 1 right, 2 left, 3 far
                ld   (HUD_A_MOVED),a
                ld   a,(MAG_LEFT)
                ld   hl,MAG_RIGHT
                add  a,(hl)                 ; rounds in the two guns, 0-14
                ld   hl,HUD_AMMO_ROUNDS
                sub  l                      ; ... as SPENT rounds, 14-0
                neg
                ld   hl,HUD_AMMO_SPENT
                cp   (hl)
                jr   nz,.changed
                ld   a,(HUD_A_MOVED)        ; the count is where it was:
                or   a                      ; only a move can want anything
                ret  z
                ; ---- THE VIEW MOVED AND THE COUNT DID NOT ------------
                ; Every cell now holds its neighbour's picture, and the
                ; row is empties then fulls - so they differ in one
                ; place, at the end of the spent run, and at the cell
                ; the shift left with no neighbour to inherit from.
                cp   3
                jp   z,HUD_AMMO_ALL
                ; The cells whose picture differs from their NEIGHBOUR'S
                ; are e-1, where the spent run ends, and e as well when
                ; one cell is half spent. A shift right puts each of
                ; those wrong; a shift LEFT puts the cell ABOVE each of
                ; them wrong instead, which is the mirror and not the
                ; same window - it was written once for both and the
                ; suite caught it walking left, one cell of stale pips.
                call HUD_AMMO_SEAM
                ld   c,a                    ; C = e
                ld   a,(HUD_AMMO_SPENT)
                and  1
                ld   b,a                    ; B = 1 while a cell is half
                ld   a,(HUD_A_MOVED)
                dec  a
                ld   a,c
                jr   nz,.cs_left
                dec  a                      ; right: e-1, and e when odd
.cs_left:       ld   (HUD_A_LO),a           ; left:  e,   and e+1 when odd
                add  a,b
                ld   (HUD_A_HI),a
                jr   .paint

                ; ---- THE COUNT MOVED --------------------------------
                ; A SHOT IS ONE PIP AND AT MOST TWO CELLS: the seam is
                ; spent/2 and one round moves it by nought or one, so
                ; the window from min(old,new)-1 to max(old,new) holds
                ; every cell whose picture is now wrong. A RELOAD puts
                ; fourteen rounds back at once and the first frame has
                ; nothing drawn at all; both lay out the whole row.
.changed:       ld   d,(hl)                 ; the count it was drawn at
                ld   (hl),a
                srl  a
                ld   e,a                    ; E = the new seam
                ld   a,(HUD_A_MOVED)
                cp   3
                jp   z,HUD_AMMO_ALL         ; a row step or a jump
                ld   a,d
                inc  a
                jp   z,HUD_AMMO_ALL         ; &FF: nothing is drawn yet
                ld   a,d
                srl  a
                ld   d,a                    ; D = the old seam
                sub  e
                jr   nc,.gap
                neg
.gap:           cp   2
                jp   nc,HUD_AMMO_ALL        ; more than a round's worth
                ld   a,d
                cp   e
                jr   c,.lo_old
                ld   a,e
.lo_old:        ld   (HUD_A_LO),a           ; lo = min(old, new)
                ld   a,d
                cp   e
                jr   nc,.hi_old
                ld   a,e
.hi_old:        ld   (HUD_A_HI),a           ; hi = max(old, new)
                ; AND THE SHIFT WIDENS IT BY ONE, on the side it shifts
                ; from: going right every cell holds its right-hand
                ; neighbour's picture, so the cell BELOW the window is
                ; wrong too, and going left the one above it. A still
                ; view widens it by nothing - the cell below the seam
                ; was empty and stays empty.
                ld   a,(HUD_A_MOVED)
                dec  a
                jr   z,.wide_r              ; 1: one character right
                dec  a
                jr   nz,.paint              ; 0: still, and the window is
                ld   a,(HUD_A_HI)           ; every cell there is to write
                inc  a                      ; 2: one character left
                ld   (HUD_A_HI),a
                jr   .paint
.wide_r:        ld   a,(HUD_A_LO)
                dec  a
                ld   (HUD_A_LO),a

                ; ---- write the window, then the shift's own cell -----
                ; LO IS -1 WHENEVER THE SEAM IS CELL 0, and -1 is 255 in
                ; a byte: walked from there the loop wraps at 256 and
                ; comes round for ever, which is exactly what it did.
                ; Both ends are tested against 255 before the walk
                ; starts - an empty window is a real answer (the row is
                ; all full and only the shift's own cell is wrong).
.paint:         ld   a,(HUD_A_HI)
                inc  a
                jr   z,.edge                ; no window at all
                ld   a,(HUD_A_LO)
                inc  a
                jr   z,.cell                ; -1: start at 0, which INC made
                dec  a
.cell:          cp   HUD_AMMO_CELLS
                jr   nc,.edge               ; past the right-hand end
                push af
                call HUD_AMMO_PUT
                pop  af
                inc  a
                ld   hl,HUD_A_HI
                cp   (hl)
                jr   c,.cell
                jr   z,.cell

.edge:          ld   a,(HUD_A_MOVED)
                or   a
                ret  z                      ; the view is still: that is all
                dec  a
                ld   a,HUD_AMMO_CELLS - 1   ; right: cell 6 is the new one
                jp   z,HUD_AMMO_PUT
                xor  a                      ; left: cell 0 is
                jp   HUD_AMMO_PUT

; ---------------------------------------------------------------------
; HUD_CLIPS - the digit: how many magazines the reserve is worth.
;
; ONE CHARACTER, AND IT IS THE CHEAPEST THING ON THE ROW, because its
; picture only changes when AMMO_RESERVE does - a reload, or a clip
; picked up (8.6) - and it has no seam to work out. What it does pay is
; the view: a single cell has no neighbour whose content it can inherit,
; so it is written on every frame the start address moves.
;
; THE DIVISION IS SKIPPED WHEN THE RESERVE HAS NOT MOVED, which is every
; frame but a handful: repeated subtraction by 14 is 18 iterations at
; worst and it would otherwise be paid for a picture that is already on
; the screen.
;
; IN:  (HUD_A_MOVED), as HUD_AMMO left it
; Clobbers AF,BC,DE,HL
; ---------------------------------------------------------------------
HUD_CLIPS:      ld   a,(AMMO_RESERVE)
                ld   hl,HUD_CLIPS_RES
                cp   (hl)
                jr   z,.same
                ld   (hl),a
                ld   b,0
.count:         cp   BUL_MAX                ; a reload takes BUL_MAX of it
                jr   c,.got
                sub  BUL_MAX
                inc  b
                jr   .count
.got:           ld   a,b
                cp   10
                jr   c,.digit
                ld   a,9                    ; nine is as many as a digit says
.digit:         ld   hl,HUD_CLIPS_N
                cp   (hl)
                jr   z,.same                ; a different reserve, the same
                ld   (hl),a                 ; number of magazines in it
                jp   HUD_CLIPS_PUT

.same:          ld   a,(HUD_A_MOVED)
                or   a
                ret  z
                ; fall through: the view moved, so the digit has to be
                ; put back where it was

; ---------------------------------------------------------------------
; HUD_CLIPS_PUT - the digit, wherever the view has gone.
; Clobbers AF,DE,HL
; ---------------------------------------------------------------------
HUD_CLIPS_PUT:  ld   a,(HUD_CLIPS_N)
                add  a,a                    ; sixteen bytes a digit
                add  a,a
                add  a,a
                add  a,a
                ld   e,a
                ld   d,0
                ld   hl,HUD_DIGITS
                add  hl,de
                ld   de,HUD_CLIPS_BASE
                jp   HUD_CELL_BLIT

; ---------------------------------------------------------------------
; HUD_AMMO_STEP - what the view did, as one number.
;
; The ammo needs it after HUD_AMMO_PUT has had BC, so it is taken apart
; once and kept in a byte: 0 the view is still, 1 one character right,
; 2 one character left, 3 anything else - a row step, or a jump only a
; test can make. Modulo the 1024-word ring there are no other answers
; the game can produce (HUD_SERVICE).
;
; IN:  BC = the step      OUT: A = 0..3     destroys AF,DE
; ---------------------------------------------------------------------
HUD_AMMO_STEP:  ld   a,b
                or   a
                jr   nz,.back
                ld   a,c
                or   a
                ret  z                      ; 0: still
                dec  a
                ld   a,1
                ret  z                      ; 1: one character right
                ld   a,3
                ret
.back:          cp   3
                jr   nz,.far
                ld   a,c
                inc  a
                ld   a,2
                ret  z                      ; 1023: one character left
.far:           ld   a,3
                ret

; ---------------------------------------------------------------------
; HUD_AMMO_ALL - all seven cells, one HUD_AMMO_PUT each.
;
; NOT A BUFFER AND AN LDI RUN like HUD_ALL, and it was written both ways
; before that was settled. A 112-byte buffer copies the row in 2,668 T
; against these 6,744 - but it has to be KEPT, and one cell of it is
; 1,056 T to lay out, which is paid on every shot. Measured in play, the
; buffer was 192 loop iterations in 200 walking and 175 firing against
; 198 and 182 for the puts: the cheap paths are the common ones, and
; this is the rare one.
; Clobbers AF,BC,DE,HL
; ---------------------------------------------------------------------
HUD_AMMO_ALL:   ld   b,0
.cell:          ld   a,b
                push bc
                call HUD_AMMO_PUT
                pop  bc
                inc  b
                ld   a,b
                cp   HUD_AMMO_CELLS
                jr   c,.cell
                ret

; ---------------------------------------------------------------------
; HUD_AMMO_PUT - write cell A of the ammo row.
;
; IN:  A = 0..6    Clobbers AF,BC,DE,HL
; ---------------------------------------------------------------------
HUD_AMMO_PUT:   ld   c,a
                call HUD_AMMO_ART
                ld   e,c
                ld   d,0
                push hl
                ld   hl,HUD_AMMO_BASE
                add  hl,de
                ex   de,hl
                pop  hl
                jp   HUD_CELL_BLIT

; ---------------------------------------------------------------------
; HUD_AMMO_ART - which of the three pictures cell C is showing.
;
; IN:  C = 0..6    OUT: HL -> its 16 bytes    destroys AF
; ---------------------------------------------------------------------
HUD_AMMO_ART:   call HUD_AMMO_SEAM          ; A = the first cell with a round
                cp   c
                jr   z,.half                ; c == e: half, if spent is odd
                ld   hl,HUD_PIP_EMPTY
                ret  nc                     ; c <  e: both rounds gone
                ld   hl,HUD_PIP_FULL
                ret
.half:          ld   a,(HUD_AMMO_SPENT)
                and  1
                ld   hl,HUD_PIP_FULL
                ret  z                      ; even: this cell is whole
                ld   hl,HUD_PIP_HALF
                ret

; ---------------------------------------------------------------------
; HUD_AMMO_SEAM - A = the first cell with a round in it, CARRY SET
; while that cell is on the row.
;
; Fourteen spent rounds put it at 7, which is one past the row, and the
; carry says so rather than every caller testing.     destroys AF
; ---------------------------------------------------------------------
HUD_AMMO_SEAM:  ld   a,(HUD_AMMO_SPENT)
                srl  a
                cp   HUD_AMMO_CELLS         ; carry while it is 0..6
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
;      1  right  the bar leaves word HUD_BASE-1 - the LAST column of
;                row 22, and the incoming column of a step right, so
;                H_TAIL has it - and the ammo leaves the bar's own last
;                cell, which the bar is about to write. Nothing to do.
;   1023  left   the bar leaves word HUD_BASE+6, which is the ammo's
;                first cell and the one the ammo is about to write; the
;                ammo leaves the digit and the digit the inventory's
;                first cell, both of which are written on every step -
;                and the INVENTORY leaves column 20, which is real.
;     40  down   all four runs, one row UP: row 22 columns 0-19, which
;                is ONE run and one DRAW_ROW
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

; AND THE STEP RIGHT COSTS NOTHING AT ALL, because H_TAIL and the bar
; have already done it. The word the BAR leaves behind on a step right
; is the LAST column of row 22 - and the incoming column of a step right
; IS column 39, painted rows COL_HEAD..23 by H_TAIL four instructions
; before this is called (src/main.asm). The word the AMMO leaves is the
; bar's own last cell, and HUD_BAR writes that cell on every step right
; (it is the one with no neighbour to inherit from).
;
; The step LEFT has no such luck at one end: the bar's leftover is the
; ammo's first cell, which HUD_AMMO writes on every step left, and the
; ammo's is the digit, which is written whenever the view moves - but
; the DIGIT's leftover is column 14, one past the strip, and that one
; has to come back off the tilemap.
                assert COL_HEAD <= HUD_ROW - 1
.plus_one:      ret

.minus_one:     ld   h,HUD_ROW
                ld   l,HUD_STRIP_CELLS

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

; ONE RUN AND ONE MAP LOOKUP, because the three are adjacent: fourteen
; cells from column 0. At the other end of the row it was two DRAW_ROWs
; - 6,332 T and 7,000 - on the latch frame of every row step, which a
; climb makes every five frames.
.plus_row:      ld   h,HUD_ROW - 1
                ld   l,0
                ld   a,HUD_STRIP_CELLS

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

; AND IT IS ONE RUN OF FOURTEEN, because the bar, the rounds and the
; digit are adjacent: everything below is "where has word (base + k)
; gone, and does anything still show it", and the three of them are one
; strip from column 0. HUD_V_BASE and HUD_V_N are what say which.
.general:       ld   (HUD_STEP),bc
                ld   a,1
                ld   (COL_N),a
                xor  a
                ld   (HUD_BANK),a           ; C4 is not paged in yet
                ld   hl,HUD_BASE
                ld   (HUD_V_BASE),hl
                ld   a,HUD_STRIP_CELLS
                ld   (HUD_V_N),a
                call .run
                ld   a,(HUD_BANK)
                or   a
                ret  z                      ; nothing needed repainting
                jp   BANK_RESTORE

.run:           ld   b,0
.cell:          ld   l,b                    ; where this cell's word has
                ld   h,0                    ; landed under the new view
                ld   de,(HUD_STEP)
                or   a
                sbc  hl,de
                ld   de,(HUD_V_BASE)
                add  hl,de
                ld   a,h
                and  3                      ; the circular window
                ld   h,a
                push hl
                ld   de,(HUD_V_BASE)        ; ... is it inside the new run?
                or   a
                sbc  hl,de
                ld   a,h
                and  3
                ld   h,a
                ld   a,(HUD_V_N)
                ld   e,a
                ld   d,0
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
                ld   a,(HUD_V_N)
                cp   b
                jr   nz,.cell
                ret

; ---------------------------------------------------------------------
; HUD_INV - what she is carrying, at columns 14-19 of the bottom row.
;
; TWO QUESTIONS AND THEY ARE NOT THE SAME ONE. What the six cells SAY
; changes only when she picks something up, which is a handful of times
; in a level; where they are WRITTEN changes on every frame the view
; moves, which is most of them. So the layout goes into a 96-byte
; buffer and the copy runs off it - HUD_LEVEL's argument for the health
; bar, and the numbers are the same shape: laying it out is ~4,000 T
; and copying it ~2,700.
;
; IN:  BC = the step the view has just taken, 0 if it has not moved
; Clobbers AF,BC,DE,HL,IX
; ---------------------------------------------------------------------
HUD_INV:        ld   a,(KEYS_COUNT)
                ld   hl,HUD_INV_K
                cp   (hl)
                jr   nz,.changed
                ld   a,(COINS_COUNT)
                ld   hl,HUD_INV_C
                cp   (hl)
                jr   nz,.changed
                ld   a,b                    ; the picture is right and the
                or   c                      ; view has not moved: there is
                ret  z                      ; nothing for it to be wrong at
                jr   .copy

                ; ---- AND THE LAYOUT WAITS FOR THE SECOND SWEEP, WHICH
                ; IS THE WHOLE OF THE FRAME THIS GROUP WAS COSTING.
                ;
                ; The copy is 2,516 T and runs on every frame the view
                ; moves; HUD_INV_LAYOUT is 6,480 and runs when a COUNT
                ; changes, which is a handful of times in a level. So
                ; the strip's cost is not what drops a frame - the
                ; LAYOUT is, on the one frame it lands on. Measured on
                ; the walk, sweep by sweep against the 19,968 us each
                ; hardware sweep has:
                ;
                ;   sweep A, worst ordinary frame      18,582 us
                ;   ... the frame the layout lands on  20,870   over by 902
                ;   sweep B, worst frame               17,236   2,732 spare
                ;
                ; The first sweep latches the horizontal step and paints
                ; the incoming column's tail; the second waits 40,468 T
                ; for its head gate (9). So the layout goes where the
                ; room is, and what that costs is that the COUNT on the
                ; glass is a game frame behind its variable - 40 ms, the
                ; same lag the magazine digit has had since it went in
                ; and for the same reason.
                ;
                ; THE COPY STILL RUNS ON THE SWEEP THAT SKIPS THE
                ; LAYOUT, and not only when the view moved. ENT_REPAINT_DUE
                ; can paint over the strip and stamps these counts with
                ; &FF to say so (entity.asm); if a stale buffer were also
                ; a reason not to write anything, that damage would stay
                ; on the screen until the next count change.
.changed:       ld   a,(FRAME_HALF)
                or   a
                jr   z,.copy                ; the first sweep: write the
                                            ; buffer it has, and lay the
                                            ; new one out in the second
                call HUD_INV_LAYOUT

                ; AND THE COPY IS THE BAR'S, NOT A SECOND ONE. Both
                ; runs are six cells of twelve bytes on eight lines, so
                ; there is one unrolled LDI run and two callers - see
                ; HUD_RUN12, which is also where the 1024-word fold is
                ; handled. This used to be a pair of LDIRs with the
                ; destination re-read out of memory every line, 4,068 T
                ; against 2,300, and the 1,768 T was a whole game frame
                ; in 200 on the paths that step the camera (7.8).
.copy:          ld   de,HUD_INV_BASE
                ld   hl,HUD_INV_BUF
                jp   HUD_RUN12

; ---------------------------------------------------------------------
; HUD_INV_LAYOUT - the six cells into HUD_INV_BUF, line by line.
;
; The counts are remembered here and not by the caller, because this is
; the one place that knows the buffer now matches them.
; Clobbers AF,BC,DE,HL,IX
; ---------------------------------------------------------------------
HUD_INV_LAYOUT: ld   a,(KEYS_COUNT)
                ld   (HUD_INV_K),a
                call HUD_INV_DIGIT
                ld   hl,HUD_ICON_KEY
                or   a
                jr   nz,.key
                ld   hl,HUD_ICON_KEY_DARK
.key:           ld   de,HUD_INV_BUF
                call HUD_INV_ITEM

                ld   a,(COINS_COUNT)
                ld   (HUD_INV_C),a
                call HUD_INV_DIGIT
                ld   hl,HUD_ICON_COIN
                or   a
                jr   nz,.coin
                ld   hl,HUD_ICON_COIN_DARK
.coin:          ld   de,HUD_INV_BUF + 6
                ; falls into HUD_INV_ITEM

; ---------------------------------------------------------------------
; HUD_INV_ITEM - one icon and its count into the buffer.
;
; IN:  HL = the 8x4 icon, IX = its digit, DE = where the item starts
; Clobbers AF,BC,DE,HL,IX
; ---------------------------------------------------------------------
HUD_INV_ITEM:   ld   b,HUD_LINES
.line:          push bc
                ld   c,4                    ; the icon is two characters
.icon:          ld   a,(hl)
                ld   (de),a
                inc  hl
                inc  de
                dec  c
                jr   nz,.icon
                ld   a,(ix + 0)             ; ... and the count is one
                ld   (de),a
                inc  de
                ld   a,(ix + 1)
                ld   (de),a
                inc  de
                inc  ix
                inc  ix
                ld   a,e                    ; the next line of the buffer,
                add  a,HUD_INV_BYTES - 6    ; past the other item
                ld   e,a
                ld   a,d
                adc  a,0
                ld   d,a
                pop  bc
                djnz .line
                ret

; ---------------------------------------------------------------------
; HUD_INV_DIGIT - IX = the artist's digit for the count in A.
;
; CAPPED AT NINE because one character is what the row can pay for -
; the magazine digit's own rule, one group along.
; A is preserved.            Clobbers BC,HL,IX
; ---------------------------------------------------------------------
HUD_INV_DIGIT:  push af
                cp   10
                jr   c,.ok
                ld   a,9
.ok:            ld   l,a
                ld   h,0
                add  hl,hl
                add  hl,hl
                add  hl,hl
                add  hl,hl                  ; sixteen bytes a digit
                ld   bc,HUD_DIGITS
                add  hl,bc
                push hl
                pop  ix
                pop  af
                ret

; ---------------------------------------------------------------------
; HUD_ALL - write all six cells of the health bar.
;
; SIX SEPARATE HUD_PUTs WOULD BE 4,908 T AND THIS IS 2,300, because the
; six cells are twelve consecutive bytes on each of the eight lines and
; the per-line address step is then paid once instead of six times.
; That matters where it is called from: HUD_SERVICE runs BEFORE her
; draw, so that her save-under captures the bar (CLAUDE.md 10), and
; everything spent here comes off the lead the top border gives her
; (9). It costs a 96-byte buffer, which HUD_LEVEL fills.
; Clobbers AF,BC,DE,HL
; ---------------------------------------------------------------------
HUD_ALL:        ld   de,HUD_BASE
                ld   hl,HUD_BUF
                ; falls into HUD_RUN12

; ---------------------------------------------------------------------
; HUD_RUN12 - twelve contiguous bytes on each of eight lines, from a
; buffer into a run of six cells at a word offset into the view.
;
; IN:  DE = the run's word offset into the view
;      HL = the 96-byte buffer
; Clobbers AF,BC,DE,HL
;
; THE INVENTORY GROUP SHARES IT, AND THAT IS WHAT THIS ROUTINE IS FOR.
; Both runs are six cells of twelve bytes on eight lines - the bar's
; and the icons-and-counts of 7.8 - and the second one was copying
; itself with a pair of LDIRs and a destination re-read out of memory
; every line: 4,068 T against this 2,300. Measured in play, that
; difference was a whole game frame in 200 on the three paths that step
; the camera hardest (7.8), so the second copy of the unrolled run was
; worth 240 bytes of core image and it is cheaper to share one.
;
; The exception is the fold: at six of the ring's 1024 start positions
; the run crosses the 1024-word seam and comes back at the top of the
; same 2 KB block (6.4), and there it is two LDIRs a line.
; ---------------------------------------------------------------------
                assert HUD_INV_BYTES == HUD_BYTES
HUD_RUN12:      ld   (HUD_SRC),hl
                ld   hl,(HUD_WANT)
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
                ld   hl,(HUD_SRC)
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
                ld   hl,(HUD_SRC)
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
; HUD_PUT - write cell A of the health bar at word SCROLL + A.
;
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
                ld   hl,HUD_BASE            ; the bottom row of the view
                add  hl,de
                ex   de,hl
                pop  hl
                ; falls into HUD_CELL_BLIT

; ---------------------------------------------------------------------
; HUD_CELL_BLIT - one 4x8 cell, wherever in the bottom row it goes.
;
; ONE CELL IS ONE CRTC CHARACTER, which is what makes the 1024-word
; seam free here: the fold is between characters, never inside one, so
; the address is a mask and the eight lines are &0800 apart with no run
; to split (CLAUDE.md 6.4). The eight are unrolled because the
; bookkeeping is most of the cost at two bytes a line.
;
; IN:  DE = the word offset into the view, HL = the cell's 16 bytes
; Clobbers AF,DE,HL
; ---------------------------------------------------------------------
HUD_CELL_BLIT:  push hl
                ld   hl,(HUD_WANT)          ; the view just latched
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
HUD_V_BASE:     dw 0            ; which run HUD_VACATE's general path is on,
HUD_V_N:        db 0            ; ... and how many cells it has
HUD_BANK:       db 0            ; whether HUD_VACATE has paged C4 in yet
HUD_LAST:       dw 0            ; the start address it was last drawn at,
                                ; and 0 is SCROLL_INIT's own, so the first
                                ; frame vacates nothing
HUD_HP:         db &FF          ; the health it was last drawn for, and
                                ; &FF is none she can have, so the first
                                ; frame always draws
HUD_AMMO_SPENT: db &FF          ; ... and the same for the rounds: &FF is
                                ; not a number of spent rounds either
HUD_A_MOVED:    db 0            ; what the view did: HUD_AMMO_STEP's 0-3
; Where HUD_RUN12 keeps the buffer it was handed, because the fold's
; slow lane reloads it once a line and the fast lane once a call.
HUD_SRC:        dw 0

HUD_INV_K:      db &FF          ; the counts the inventory's six cells were
HUD_INV_C:      db &FF          ; ... laid out for, &FF being no layout yet
HUD_INV_BUF:    defs HUD_INV_BYTES * HUD_LINES
HUD_CLIPS_RES:  db &FF          ; the reserve the digit was worked out from,
                                ; and &FF is not one the game hands out
HUD_CLIPS_N:    db 0            ; ... and the digit itself
HUD_A_LO:       db 0            ; the window of ammo cells whose picture
HUD_A_HI:       db 0            ; ... is wrong, inclusive
HUD_LIT:        db &FF          ; NOT 0 - see HUD_LEVEL: a count that
                                ; matches means the buffer is already right,
                                ; and it is not until it has been laid out once
HUD_N1:         db 0            ; bytes of a line before the 1024-word seam
HUD_N2:         db 0            ; ... and after it
HUD_DST:        dw 0
HUD_LN:         db 0
HUD_BUF:        ds HUD_LINES * HUD_BYTES

                include "hud_art.inc"
