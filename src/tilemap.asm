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
; *** ONLY EVER CALL THIS INSIDE VERTICAL BLANKING. ***
;
; Not a style rule - a portability one, and it is CRTC-type dependent,
; which is exactly the class of bug CLAUDE.md 10 warns about. The
; headless emulator reloads its internal address latch from R12/R13
; only at vertical-total rollover (mc6845.h: ma_store is assigned from
; start_addr_hi/lo under co_vtotal and nowhere else), so a mid-frame
; write there silently defers to the next frame and looks harmless. A
; real 6845 takes the new address from the next CHARACTER ROW - that is
; the mechanism the CPC's split-screen trick is built on - so the same
; code splits the picture on hardware: everything above the write keeps
; the old view, everything below jumps to the new one.
;
; That is what a mid-frame apply in SCROLL_V_FINISH did: correct on the
; headless emulator, visibly torn on RetroVirtualMachine. WAIT_VSYNC
; returns at scanline 240 and the display starts 72 scanlines later, so
; anything called from the top of the main loop is safely inside the
; window; anything called after real work is not.
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
; start and gains ground on the beam every character row.
;
; A tile is 16 pixels tall and a character row is 8, so ONE tile covers
; two character rows. The map column is fixed for the whole column, so
; the map lookup is hoisted: the pointer is computed once and advanced
; by one map row every second character row. That is 12 lookups for the
; column instead of 24, and it is most of the difference between this
; and calling DRAW_CELL 24 times.
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
                add  a,e                    ; world character column
                ld   c,a
                and  3
                add  a,a
                ld   (COL_BYTEOFF),a        ; (wc AND 3) * 2

                ld   a,c
                rrca
                rrca
                and  &3F                    ; map column 0-63
                ld   e,a
                ld   a,(WORLD_CR)
                ld   (CELL_WR),a
                srl  a
                and  MAP_ROW_MASK           ; map row 0-15
                rrca
                rrca                        ; -> (row AND 3)<<6 | row>>2
                ld   d,a
                and  &C0
                or   e
                ld   l,a
                ld   a,d
                and  3
                add  a,MAP_ADDR >> 8
                ld   h,a
                ld   (COL_MAPPTR),hl

                call COL_FETCH              ; prime COL_TILEBASE
                ld   a,SCR_CHAR_ROWS
                ld   (COL_ROWS),a
                ld   bc,(CELL_WORD)         ; the word index lives in BC for
                                            ; the whole loop - the blit below
                                            ; touches only AF, DE and HL

                ; Screen address, 40 T, no scratch pair needed:
                ;   addr = &C000 + ((word * 2) AND &07FF)
                ; ADD A,A sets the carry out of the low byte and ADC A,A
                ; folds it into the high byte, so the mask is AND 7 on the
                ; doubled value rather than AND 3 on the word.
.row:           ld   a,c                    ; 4
                add  a,a                    ; 4
                ld   e,a                    ; 4
                ld   a,b                    ; 4   (LD does not touch flags)
                adc  a,a                    ; 4
                and  7                      ; 8
                add  a,SCREEN_BASE >> 8     ; 8
                ld   d,a                    ; 4   DE = screen, raster 0

                ld   hl,(COL_TILEBASE)
                ld   a,(CELL_WR)
                and  1
                jp   z,.top
                ld   a,l                    ; odd world row: the lower half
                add  a,64                   ; of the tile, 8 lines on
                ld   l,a
.top:

                repeat 8
                ld   a,(hl)                 ; 8
                ld   (de),a                 ; 8
                inc  l                      ; 4   a tile is 128 bytes on a
                inc  e                      ; 4   128-byte boundary, and
                ld   a,(hl)                 ; 8   word*2 is even, so neither
                ld   (de),a                 ; 8   of these can carry
                ld   a,l                    ; 4
                add  a,7                    ; 8   source: next tile line
                ld   l,a                    ; 4
                dec  e                      ; 4
                ld   a,d                    ; 4
                add  a,8                    ; 8   screen: next scanline
                ld   d,a                    ; 4   -- 76 T per raster
                rend

                ld   a,c                    ; word += 40: down one char row
                add  a,SCR_CHARS
                ld   c,a
                jp   nc,.same_page
                inc  b
.same_page:     ld   hl,CELL_WR
                inc  (hl)
                ld   a,(hl)
                and  1
                call z,COL_NEXT_TILE        ; crossed into a new map row
                ld   hl,COL_ROWS
                dec  (hl)
                jp   nz,.row
                ret

; ---------------------------------------------------------------------
; COL_FETCH - read the tile under COL_MAPPTR and work out the address of
; its first line, byte offset already folded in.
;                                Clobbers AF, HL
; ---------------------------------------------------------------------
COL_FETCH:      ld   hl,(COL_MAPPTR)
                ld   a,(hl)                 ; tile index 0-15
                rrca                        ; -> (tile AND 1)<<7 | tile>>1
                ld   h,a
                and  &80
                ld   l,a
                ld   a,(COL_BYTEOFF)
                add  a,l                    ; max 128+6, never carries
                ld   l,a
                ld   a,h
                and  7
                add  a,TILES_ADDR >> 8
                ld   h,a
                ld   (COL_TILEBASE),hl
                ret

; ---------------------------------------------------------------------
; COL_NEXT_TILE - step the map pointer down one row and refetch.
;
; The map is 1024 bytes at &4800, so the pointer runs &4800-&4BFF and
; RES 2,H folds &4C00 back to &4800 - which is the 16-row wrap, free.
;                                Clobbers AF, HL
; ---------------------------------------------------------------------
COL_NEXT_TILE:  ld   hl,(COL_MAPPTR)
                ld   a,l
                add  a,MAP_W
                ld   l,a
                jp   nc,.stored
                inc  h
.stored:        res  2,h
                ld   (COL_MAPPTR),hl
                jp   COL_FETCH

; ---------------------------------------------------------------------
; DRAW_ROW - repaint one screen character row, left to right.
;
; The mirror of DRAW_COLUMN. A tile is 16 pixels wide and a character is
; 4, so ONE tile covers four character columns; the map row is fixed
; across the row, so the lookup is hoisted the same way - 10 lookups for
; the row instead of 40.
;
; IN:  A = screen character row 0-23; (ROW_FIRST) = first character
;      column, (ROW_N) = how many. Bank C4 must be paged in.
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

                ld   a,(WORLD_CR)
                add  a,e                    ; E = screen char row -> world row
                ld   (ROW_WR),a             ; the map row needs it too, and C
                and  1                      ; is about to become the column
                rrca
                rrca                        ; (wr AND 1) * 64
                ld   (ROW_LINEOFF),a

                ld   a,(ROW_FIRST)
                ld   e,a                    ; start at this character column
                ld   d,0
                add  hl,de
                ld   (CELL_WORD),hl
                ld   a,(WORLD_X)
                add  a,e                    ; ... and the world column under it
                ld   c,a
                and  3
                add  a,a
                ld   (ROW_BYTEOFF),a        ; (wc AND 3) * 2

                ; map pointer = MAP_ADDR + (map_row << 6) + map_col
                ld   a,c
                rrca
                rrca
                and  &3F                    ; map column 0-63
                ld   e,a
                ld   a,(ROW_WR)
                srl  a
                and  MAP_ROW_MASK           ; map row 0-15
                rrca
                rrca                        ; -> (row AND 3)<<6 | row>>2
                ld   d,a
                and  &C0
                or   e
                ld   l,a
                ld   a,d
                and  3
                add  a,MAP_ADDR >> 8
                ld   h,a
                ld   (ROW_MAPPTR),hl

                call ROW_FETCH              ; prime ROW_TILEBASE
                ld   a,(ROW_N)
                ld   (ROW_COUNT),a
                ld   bc,(CELL_WORD)         ; word index lives in BC

.col:           ld   a,c                    ; screen address, 40 T
                add  a,a
                ld   e,a
                ld   a,b
                adc  a,a
                and  7
                add  a,SCREEN_BASE >> 8
                ld   d,a

                ld   hl,(ROW_TILEBASE)
                ld   a,(ROW_BYTEOFF)
                add  a,l                    ; max 192+6, never carries
                ld   l,a

                repeat 8
                ld   a,(hl)                 ; 8
                ld   (de),a                 ; 8
                inc  l                      ; 4
                inc  e                      ; 4
                ld   a,(hl)                 ; 8
                ld   (de),a                 ; 8
                ld   a,l                    ; 4
                add  a,7                    ; 8
                ld   l,a                    ; 4
                dec  e                      ; 4
                ld   a,d                    ; 4
                add  a,8                    ; 8
                ld   d,a                    ; 4   -- 76 T per raster
                rend

                inc  bc                     ; right one character
                ld   a,(ROW_BYTEOFF)
                add  a,2
                cp   8
                jr   c,.same_tile           ; still inside this tile
                call ROW_NEXT_TILE          ; every 4th character column
                xor  a
.same_tile:     ld   (ROW_BYTEOFF),a
                ld   hl,ROW_COUNT
                dec  (hl)
                jp   nz,.col
                ret

; ---------------------------------------------------------------------
; ROW_FETCH - tile under ROW_MAPPTR -> ROW_TILEBASE, with the half-tile
; line offset folded in.                Clobbers AF, HL
; ---------------------------------------------------------------------
ROW_FETCH:      ld   hl,(ROW_MAPPTR)
                ld   a,(hl)                 ; tile index 0-15
                rrca                        ; -> (tile AND 1)<<7 | tile>>1
                ld   h,a
                and  &80
                ld   l,a
                ld   a,(ROW_LINEOFF)
                add  a,l
                ld   l,a
                ld   a,h
                and  7
                add  a,TILES_ADDR >> 8
                ld   h,a
                ld   (ROW_TILEBASE),hl
                ret

; ---------------------------------------------------------------------
; ROW_NEXT_TILE - step the map pointer right one tile, wrapping inside
; the map row: bits 0-5 of the low byte are the column, bits 6-7 carry
; part of the row, so the wrap is a mask rather than a compare.
;                                Clobbers AF, DE, HL
; ---------------------------------------------------------------------
ROW_NEXT_TILE:  ld   hl,(ROW_MAPPTR)
                ld   a,l
                inc  a
                and  &3F
                ld   e,a
                ld   a,l
                and  &C0
                or   e
                ld   l,a
                ld   (ROW_MAPPTR),hl
                jp   ROW_FETCH

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
; SCROLL_V_STEP / SCROLL_V_FINISH - one character row, 8 scanlines.
;
; A whole row is 40 cells and 37,124 T - 46% of a frame - which does not
; fit alongside Kara. It does not have to: measured against the start
; address the CRTC is still displaying, the incoming row lands in the 64
; words R6 = 24 keeps off-screen,
;
;   down: new bottom row = SCROLL + 40 + 23*40  -> offset 960, hidden
;   up:   new top row    = SCROLL - 40          -> offset 984, hidden
;
; so it is invisible until SCROLL_APPLY moves the view. That buys the
; freedom to paint it in two halves on consecutive frames and only then
; latch the new start address. Nothing can tear, because nothing the
; beam can see changes until both halves are down.
;
; Three frames, because the latch may only happen in vertical blanking:
;   frame N   SCROLL_V_STEP   state + left half   V_PHASE 0 -> 1
;   frame N+1 SCROLL_V_FINISH right half          V_PHASE 1 -> 2
;   frame N+2 SCROLL_VBLANK   latch R12/R13       V_PHASE 2 -> 0
;
; SCROLL_V_STEP:   IN A = 0 to scroll down the map, non-zero to scroll up.
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
                ld   a,SCR_CHAR_ROWS - 1    ; incoming row at the bottom
                jr   .half

.up:            ld   a,(WORLD_CR)
                dec  a
                ld   (WORLD_CR),a
                ld   hl,(SCROLL)
                ld   de,-SCR_CHARS
                add  hl,de                  ; 16-bit wrap, then masked
                call SCROLL_WRAP
                xor  a                      ; incoming row at the top

.half:          ld   (V_ROW),a
                ld   a,1
                ld   (V_PHASE),a
                xor  a
                ld   (ROW_FIRST),a          ; left half: columns 0-19
                ld   a,SCR_CHARS / 2
                ld   (ROW_N),a
                jr   V_PAINT

SCROLL_V_FINISH:
                ld   a,SCR_CHARS / 2        ; right half: columns 20-39
                ld   (ROW_FIRST),a
                ld   (ROW_N),a
                call V_PAINT
                ld   a,2                    ; the row is whole; the view moves
                ld   (V_PHASE),a            ; at the next VSYNC, not here
                ret

; ---------------------------------------------------------------------
; SCROLL_VBLANK - the only place a vertical step's new start address is
; ever latched. Call it FIRST in the frame, before any drawing, while
; the raster is still in the border.
;                                Clobbers AF, BC, DE, HL
; ---------------------------------------------------------------------
SCROLL_VBLANK:  ld   a,(V_PHASE)
                cp   2
                ret  nz
                xor  a
                ld   (V_PHASE),a
                jp   SCROLL_APPLY

V_PAINT:        call BANK_SET_C4
                ld   a,(V_ROW)
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
COL_BYTEOFF:    db 0
COL_MAPPTR:     dw 0
COL_TILEBASE:   dw 0
COL_ROWS:       db 0
ROW_LINEOFF:    db 0
ROW_BYTEOFF:    db 0
ROW_MAPPTR:     dw 0
ROW_TILEBASE:   dw 0
ROW_COUNT:      db 0
ROW_WR:         db 0
ROW_FIRST:      db 0
ROW_N:          db SCR_CHARS
V_ROW:          db 0
V_PHASE:        db 0
