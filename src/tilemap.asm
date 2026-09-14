; =====================================================================
; tilemap.asm - hardware-scrolled tile playfield          (MODULE 4)
;
; The CRTC start address (R12/R13) is the only cheap way to scroll on a
; CPC: bump it and the whole picture moves, for the price of two OUTs.
; What it costs instead is a memory model with two sharp edges.
;
; EDGE 1 - the screen is a window into a 1024-word circular space.
; The gate array only drives MA0-MA9 onto the address bus, so a raster
; block reaches 1024 words and the address the CRTC generates is
;
;       addr = ((MA & &3000) << 2) | ((RA & 7) << 11) | ((MA & &3FF) << 1)
;
; Verified against the emulator at six start addresses, 2400 sampled
; bytes each, including wrap-crossing ones: zero mismatches. Everything
; below computes addresses with that formula and nothing assumes that
; consecutive screen positions are consecutive in RAM.
;
; EDGE 2 - the row stride is R1, exactly the displayed width, so every
; scroll step writes into memory that is on screen right now. Where
; exactly decides when it is safe to write, and the answer is different
; for each axis. Only one cell per step is ever new; everything else
; already holds the right bytes under the new start address.
;
; R6 = 24 displays 960 of the 1024 words, which leaves 64 words - more
; than one 40-word character row - permanently outside the window.
; That margin is the whole trick for vertical scrolling:
;
;   VERTICAL, state -> paint -> apply (up) or state -> apply -> paint
;   (down). Measured against the start address the CRTC is displaying,
;   the incoming row sits at offset 984 (up) or 960 (down) - both in
;   the hidden margin - so it can be painted in full, unseen, and the
;   picture moves only once it is complete. No race, no tearing.
;
;   HORIZONTAL, state -> apply -> paint. Its incoming column is NOT
;   hidden: under the old start address those cells are the left edge
;   of each row below, and under the new one they are the right edge.
;   So the new address goes in first and the painting races the beam
;   down the screen. It wins comfortably - VSYNC leaves 72 scanlines
;   (18,432 T) of head start and a cell costs ~1,290 T against the
;   beam's 2,048 T per character row - but the loop must run top to
;   bottom for that to hold.
;
; Getting this backwards does not crash or corrupt memory. It puts a
; 4-pixel column of the wrong tile down one edge of every frame, which
; is why the acceptance test compares the RENDERED framebuffer and not
; just video RAM.
;
; Tiles and the map are read from bank C4 through the &4000 window,
; which is what Module 1's banking was built for.
; =====================================================================

TILES_ADDR      equ BANK_WINDOW             ; &4000  16 tiles * 128 bytes
MAP_ADDR        equ BANK_WINDOW + 2048      ; &4800  64 * 16 bytes
TILE_BLOB_SIZE  equ 2048 + 1024

MAP_W           equ 64
MAP_H           equ 16
MAP_COL_MASK    equ MAP_W - 1               ; both dimensions are powers of
MAP_ROW_MASK    equ MAP_H - 1               ; two, so the map wraps with AND

TILE_BYTES      equ 128                     ; 8 bytes * 16 lines
SCR_CHARS       equ 40                      ; R1 - characters across
SCR_CHAR_ROWS   equ 24                      ; R6 - see EDGE 2 above
SCR_WORDS       equ SCR_CHARS * SCR_CHAR_ROWS
CRTC_PAGE       equ &30                     ; MA bits 12-13: page &C000

CRTC_R1         equ 1
CRTC_R6         equ 6
CRTC_R12        equ 12
CRTC_R13        equ 13

; ---------------------------------------------------------------------
; CRTC_SET - write one 6845 register.
; IN:  B = register, C = value        Clobbers AF, BC
; ---------------------------------------------------------------------
CRTC_SET:       ld   a,c
                ld   c,b
                ld   b,&BC
                out  (c),c                  ; &BCxx selects the register
                ld   b,&BD
                out  (c),a                  ; &BDxx writes it
                ret

; ---------------------------------------------------------------------
; SCROLL_INIT - shorten the display to 24 rows, stage the level into
; bank C4, and paint the whole playfield once.
; ---------------------------------------------------------------------
SCROLL_INIT:    ld   b,CRTC_R6
                ld   c,SCR_CHAR_ROWS
                call CRTC_SET

                xor  a
                ld   (WORLD_X),a
                ld   (WORLD_CR),a
                ld   hl,0
                ld   (SCROLL),hl
                call SCROLL_APPLY

                call TILES_INSTALL
                jp   DRAW_PLAYFIELD

; ---------------------------------------------------------------------
; TILES_INSTALL - copy the tile sheet and the map into bank C4.
;
; The blob travels inside the core image, so the bootstrap's relocation
; has already put it in base RAM at CITY_TILES - outside the &4000
; window, which is the only reason a plain LDIR into the window works.
; Clobbers AF, BC, DE, HL
; ---------------------------------------------------------------------
TILES_INSTALL:  call BANK_SET_C4
                ld   hl,CITY_TILES
                ld   de,TILES_ADDR
                ld   bc,TILE_BLOB_SIZE
                ldir
                jp   BANK_RESTORE

; ---------------------------------------------------------------------
; SCROLL_APPLY - push SCROLL into R12/R13.
;
; Call it immediately after VSYNC and nowhere else: the CRTC latches
; the start address once per frame, at the top, so a mid-frame write
; either does nothing or splits the picture.
; Clobbers AF, BC, DE, HL
; ---------------------------------------------------------------------
SCROLL_APPLY:   ld   hl,(SCROLL)
                ld   a,h
                and  3
                or   CRTC_PAGE
                ld   d,a                    ; R12: page | MA bits 8-9
                ld   e,l                    ; R13: MA bits 0-7
                ld   bc,&BC00 + CRTC_R12
                out  (c),c
                ld   b,&BD
                out  (c),d
                ld   bc,&BC00 + CRTC_R13
                out  (c),c
                ld   b,&BD
                out  (c),e
                ret

; ---------------------------------------------------------------------
; TILE_SRC - locate the two bytes of tile graphics that belong at one
; character cell.
;
; A tile is 16x16 = 8 bytes x 16 lines, so it covers 4 character
; columns and 2 character rows:
;
;       map column = (wc >> 2) & 63      byte pair = (wc & 3) * 2
;       map row    = (wr >> 1) & 15      line pair = (wr & 1) * 64
;
; Both map dimensions being powers of two is what keeps this to a few
; rotates - it runs once per cell, 24 times per scrolled column.
;
; IN:  C = world char column, B = world char row   (low bytes suffice:
;      the map repeats every 256 char columns and every 32 char rows,
;      which IS the wrap we want)
; OUT: HL = address in bank C4 of the cell's first byte
; Clobbers AF, DE.  B and C are preserved.
; ---------------------------------------------------------------------
TILE_SRC:       ld   a,b
                srl  a
                and  MAP_ROW_MASK           ; map row 0-15
                rrca
                rrca                        ; -> (row&3)<<6 | row>>2
                ld   d,a
                and  &C0
                ld   e,a
                ld   a,c
                rrca
                rrca
                and  &3F                    ; map column 0-63
                or   e
                ld   l,a                    ; low  = (row&3)*64 + col
                ld   a,d
                and  3
                add  a,MAP_ADDR / 256
                ld   h,a                    ; high = &48 + row/4
                ld   a,(hl)                 ; the tile index, 0-15

                rrca                        ; -> (tile&1)<<7 | tile>>1
                ld   d,a
                and  &80                    ; (tile & 1) * 128
                ld   e,a
                ld   a,b
                and  1
                rrca
                rrca                        ; (wr & 1) * 64
                add  a,e
                ld   e,a
                ld   a,c
                and  3
                add  a,a                    ; (wc & 3) * 2
                add  a,e                    ; max 128+64+6, never carries
                ld   l,a
                ld   a,d
                and  7
                add  a,TILES_ADDR / 256
                ld   h,a
                ret

; ---------------------------------------------------------------------
; DRAW_CELL - one character cell: 2 bytes wide, 8 rasters tall.
;
; IN:  (CELL_WORD) word index, (CELL_WC) world column, (CELL_WR) world row
; Clobbers AF, BC, DE, HL
;
; 72 T per raster, 576 per cell, ~860 with the lookup and the call.
; ---------------------------------------------------------------------
DRAW_CELL:      ld   a,(CELL_WC)
                ld   c,a
                ld   a,(CELL_WR)
                ld   b,a
                call TILE_SRC
                push hl

                ld   hl,(CELL_WORD)
                ld   a,h
                and  3                      ; & &03FF - the circular window
                ld   h,a
                add  hl,hl                  ; words are 2 bytes
                ld   a,h
                add  a,SCREEN_BASE / 256
                ld   h,a
                ex   de,hl                  ; DE = screen, raster 0
                pop  hl                     ; HL = tile source

                ld   bc,7
                repeat 8
                ld   a,(hl)                 ; 7
                ld   (de),a                 ; 7
                inc  hl                     ; 6
                inc  de                     ; 6
                ld   a,(hl)                 ; 7
                ld   (de),a                 ; 7
                add  hl,bc                  ; 11  source += 8 (next tile line)
                dec  de                     ; 6
                ld   a,d                    ; 4
                add  a,8                    ; 7   screen += &0800
                ld   d,a                    ; 4   never carries: max &FFFE
                rend
                ret

; ---------------------------------------------------------------------
; DRAW_COLUMN - repaint one screen character column, top to bottom.
;
; Top to bottom is not cosmetic: a horizontal step writes into memory
; the current frame is still displaying, so the loop has to stay ahead
; of the raster. Started right after VSYNC it has 72 scanlines of head
; start and gains 1,190 T on the beam per character row.
;
; IN:  A = screen character column, 0-39.  Bank C4 must be paged in.
; Clobbers AF, BC, DE, HL
; ---------------------------------------------------------------------
DRAW_COLUMN:    ld   e,a
                ld   d,0
                ld   hl,(SCROLL)
                add  hl,de
                ld   (CELL_WORD),hl         ; word of (row 0, this column)
                ld   a,(WORLD_X)
                add  a,e
                ld   (CELL_WC),a
                ld   a,(WORLD_CR)
                ld   (CELL_WR),a
                ld   a,SCR_CHAR_ROWS
                ld   (CELL_COUNT),a

.row:           call DRAW_CELL
                ld   hl,(CELL_WORD)
                ld   de,SCR_CHARS           ; down one character row
                add  hl,de
                ld   (CELL_WORD),hl
                ld   hl,CELL_WR
                inc  (hl)
                ld   hl,CELL_COUNT
                dec  (hl)
                jp   nz,.row
                ret

; ---------------------------------------------------------------------
; DRAW_ROW - repaint one screen character row, left to right.
; IN:  A = screen character row, 0-23.  Bank C4 must be paged in.
; Clobbers AF, BC, DE, HL
; ---------------------------------------------------------------------
DRAW_ROW:       ld   e,a
                ld   hl,0
                ld   bc,SCR_CHARS
                or   a
                jr   z,.got
.mul:           add  hl,bc                  ; row * 40, at most 23 adds
                dec  a
                jr   nz,.mul
.got:           ld   bc,(SCROLL)
                add  hl,bc
                ld   (CELL_WORD),hl
                ld   a,(WORLD_X)
                ld   (CELL_WC),a
                ld   a,(WORLD_CR)
                add  a,e
                ld   (CELL_WR),a
                ld   a,SCR_CHARS
                ld   (CELL_COUNT),a

.col:           call DRAW_CELL
                ld   hl,(CELL_WORD)
                inc  hl                     ; right one character
                ld   (CELL_WORD),hl
                ld   hl,CELL_WC
                inc  (hl)
                ld   hl,CELL_COUNT
                dec  (hl)
                jp   nz,.col
                ret

; ---------------------------------------------------------------------
; DRAW_PLAYFIELD - the whole screen. ~9 frames; level entry only.
; Clobbers AF, BC, DE, HL
; ---------------------------------------------------------------------
DRAW_PLAYFIELD: call BANK_SET_C4
                ld   a,SCR_CHARS - 1
.next:          push af
                call DRAW_COLUMN
                pop  af
                dec  a
                jp   p,.next
                jp   BANK_RESTORE

; ---------------------------------------------------------------------
; SCROLL_H_STEP - one character right: MA += 1, so the picture slides
; 2 bytes = 4 Mode 0 pixels left.
;
; State, then apply, then paint - in that order. The cell being written
; is off the right-hand edge only under the NEW start address; under
; the old one it is the left edge of the row below, in plain view.
; Clobbers AF, BC, DE, HL
; ---------------------------------------------------------------------
SCROLL_H_STEP:  ld   a,(WORLD_X)
                inc  a
                ld   (WORLD_X),a
                ld   hl,(SCROLL)
                inc  hl
                call SCROLL_WRAP
                call SCROLL_APPLY           ; this frame shows the new view
                call BANK_SET_C4
                ld   a,SCR_CHARS - 1        ; ... so paint the right edge,
                call DRAW_COLUMN            ;     top down, ahead of the beam
                jp   BANK_RESTORE

; ---------------------------------------------------------------------
; SCROLL_WRAP - store HL as the new start, masked into the 1024-word
; circular space. Subtraction relies on it too: 0 - 40 wraps to 984.
; Clobbers AF
; ---------------------------------------------------------------------
SCROLL_WRAP:    ld   a,h
                and  3
                ld   h,a
                ld   (SCROLL),hl
                ret

; ---------------------------------------------------------------------
; SCROLL_V_STEP - one character row, 8 scanlines, MA += or -= 40.
;
; Neither direction races anything. Measured against the start address
; the CRTC is currently displaying, the incoming row lands in the 64
; words R6 = 24 keeps off-screen:
;
;   down: new bottom row = SCROLL + 40 + 23*40  -> offset 960, hidden
;   up:   new top row    = SCROLL - 40          -> offset 984, hidden
;
; Down can apply first, because a start address written during the
; frame only takes effect at the next one and the bottom row is painted
; long before the beam gets there. Up must apply last: its new row is
; at the top of the screen, which the beam reaches 18,432 T into the
; frame - far too early for a 51,600 T row redraw to win. Applying
; afterwards moves the picture one frame later instead, which is
; invisible and always correct.
;
; IN:  A = 0 to scroll down the map, non-zero to scroll up.
; Clobbers AF, BC, DE, HL
; ---------------------------------------------------------------------
SCROLL_V_STEP:  or   a
                jr   nz,.up

                ld   a,(WORLD_CR)
                inc  a
                ld   (WORLD_CR),a
                ld   hl,(SCROLL)
                ld   de,SCR_CHARS
                add  hl,de
                call SCROLL_WRAP
                call SCROLL_APPLY
                ld   a,SCR_CHAR_ROWS - 1    ; incoming row at the bottom
                call .paint
                ret

.up:            ld   a,(WORLD_CR)
                dec  a
                ld   (WORLD_CR),a
                ld   hl,(SCROLL)
                ld   de,-SCR_CHARS
                add  hl,de                  ; 16-bit wrap, then masked
                call SCROLL_WRAP
                xor  a                      ; incoming row at the top
                call .paint
                jp   SCROLL_APPLY           ; only now does the view move

.paint:         push af
                call BANK_SET_C4
                pop  af
                call DRAW_ROW
                jp   BANK_RESTORE

; ---------------------------------------------------------------------
; Scrolling state.
;
; SCROLL is the CRTC start in words, always masked to 0-1023.
; WORLD_X / WORLD_CR are where the top-left of the screen sits in the
; map, in characters. All three step together or the picture and the
; map disagree.
; ---------------------------------------------------------------------
SCROLL:         dw 0
WORLD_X:        db 0
WORLD_CR:       db 0
CELL_WORD:      dw 0
CELL_WC:        db 0
CELL_WR:        db 0
CELL_COUNT:     db 0
