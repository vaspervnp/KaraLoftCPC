; =====================================================================
; sprite.asm - where a pixel IS, on a screen the CRTC is moving
;                                                          (MODULE 5)
;
; What is left here is the address model and the line stepping every
; blitter in the game shares: SCR_ADDR, SPR_NEXT_LINE, SPR_ROW_FIX,
; SCR_NEXT_LINE and SPR_STEP_BYTE. The span blitter (spanblit.asm), the
; bullets and the enemies all walk the screen with them.
;
; THE 16x48 MASKED BLITTER THAT USED TO BE HERE IS GONE. It drew the
; placeholder heroine on the Module 1-3 acceptance screen and nothing
; else: the game draws her out of span-compressed blobs (CLAUDE.md 7.1)
; and has since module 5 wired SPAN_DRAW in. With the acceptance screen
; deleted, SPR_DRAW_SAVE, SPR_RESTORE, both clipped lanes, KARA_DRAW and
; KARA_ERASE had no caller left.
;
; --------------------------------------------------------------------
; THE ADDRESS MODEL. Video RAM is a 1024-word circular window
; (tilemap.asm EDGE 1), so a screen address is NOT a linear function of
; the pixel position once the CRTC start address moves. Work in v, the
; byte offset inside the 2 KB raster block:
;
;       v    = (2*SCROLL + 80*char_row + byte_column) AND &07FF
;       addr = &C000 + ((line AND 7) << 11) + v
;
; v is the word index times two plus the half-word parity, carried in
; one number, so the word index never has to be unpacked. Three
; consequences, and they are the whole difference from Module 3:
;
;  1. WITHIN a character row nothing changes. The raster field is
;     address bits 11-13 and v is bits 0-10 - disjoint - so +&0800 is
;     right at every scroll position. SPR_NEXT_LINE's +&07F8 stays.
;
;  2. CROSSING into the next character row is not +&C050. The page bits
;     are always &C0 (SCROLL_APPLY forces CRTC_PAGE = &30), so raster 7
;     IS &F800-&FFFF, so +&0800 ALWAYS carries out of &FFFF and leaves
;     DE holding exactly v. The carry flag is the boundary test and DE
;     is already the masked offset: add 80 (= 40 words), mask to 11
;     bits, put the page back. That is SPR_ROW_FIX.
;
;  3. Eight consecutive screen bytes are consecutive in RAM only while
;     v <= 2039. From v = 2040 the run reaches offset 2047 and must
;     fold back to offset 0 of the same raster block. One test per line
;     diverts those lines to a wrap-aware lane.
;
; THE THRESHOLD IS 2040, not "word >= 1021". Two independent failures
; sit under it:
;   (a) word wrap, v >= 2041 - the eight bytes are not contiguous;
;   (b) pointer overflow, v = 2040 on raster 7 - no word wraps, but the
;       bytes are &FFF8..&FFFF and the eighth INC DE leaves DE = &0000,
;       after which SPR_NEXT_LINE's +&07F8 does NOT carry, the row fixup
;       is skipped, and the next line is blitted from &07F8 - outside
;       VRAM, over the Z80 restart vectors.
; v >= 2040 covers both.
;
; Seam frequency, counted exhaustively over all 1024 scroll values x 73
; X positions x aligned and unaligned Y: at most ONE of Kara's 6-or-7
; character rows can straddle at a time (her rows are 40 words apart
; and the zone is 4 words wide), and 2.54% of positions put one there.
; 8 slow lines out of 48, about one frame in 39 - which is why a dumb
; wrap-aware byte loop is the right answer for it.
; =====================================================================

SPR_WIDTH_BYTES equ 8
SPR_HEIGHT      equ 48
SPR_FRAME_SIZE  equ SPR_WIDTH_BYTES * SPR_HEIGHT * 2    ; 768, mask + data
SPR_SAVE_SIZE   equ SPR_WIDTH_BYTES * SPR_HEIGHT        ; 384
SPR_SEAM_LO     equ &F8         ; low byte of v = 2040, the slow-lane edge

; ---------------------------------------------------------------------
; SCR_ADDR - screen address of one byte under the current CRTC start.
; The single place the masked word arithmetic is written down for
; sprites, bullets and block fills alike.
;
; ROW_OFFSETS is reused verbatim: R1 = 40 characters IS 80 bytes, so
; the old "character row * 80" table is still numerically the right
; term. Only the 2*SCROLL addend and the AND &07FF were missing.
;
; IN : A = pixel line 0-199, C = byte column 0-79
; OUT: HL = screen address, always inside &C000-&FFFF
;      destroys AF,B,DE.  C IS PRESERVED - BUL_DRAW holds x there.
;
; 232 T including the CALL.
; ---------------------------------------------------------------------
SCR_ADDR:       ld   b,a                    ; 4   keep the raw line
                rrca                        ; 4
                rrca                        ; 4
                rrca                        ; 4
                and  &1F                    ; 8   character row 0-31
                add  a,a                    ; 4   word index into the table
                add  a,ROW_OFFSETS AND 255  ; 8   aligned: cannot carry
                ld   l,a                    ; 4
                ld   h,ROW_OFFSETS >> 8     ; 8   >> 8, NOT / 256: RASM's "/"
                ld   e,(hl)                 ; 8   ROUNDS TO NEAREST
                inc  l                      ; 4
                ld   d,(hl)                 ; 8   DE = character row * 80
                ld   hl,(SCROLL)            ; 20
                add  hl,hl                  ; 12  SCROLL counts words
                add  hl,de                  ; 12
                ld   e,c                    ; 4
                ; THE COLUMN IS SIGNED, which costs 8 T and buys the
                ; left-hand clip (spanblit.asm's CX lane): a box six
                ; bytes off the left edge is column -6, and the ring's
                ; own wrap is then the right address to step forward
                ; from. Every other caller passes 0..79, where this is
                ; the LD D,0 it replaces.
                ld   a,c                    ; 4
                add  a,a                    ; 4
                sbc  a,a                    ; 4   0, or &FF if C was negative
                ld   d,a                    ; 4
                add  hl,de                  ; 12
                ld   a,h                    ; 4
                and  7                      ; 8   ... AND &07FF  -> v
                ld   h,a                    ; 4
                ld   a,b                    ; 4
                and  7                      ; 8   raster 0-7
                add  a,a                    ; 4
                add  a,a                    ; 4
                add  a,a                    ; 4   -> address bits 11-13
                add  a,SCREEN_BASE >> 8     ; 8   <= &F8
                add  a,h                    ; 4   never carries: H <= 7
                ld   h,a                    ; 4
                ret                         ; 12

; ---------------------------------------------------------------------
; GROUPS. Both the draw and the restore walk the sprite in groups that
; follow the SCREEN'S character rows, not the sprite's own 8-line
; blocks: the sprite starts on any raster, so the first group is
; 8 - raster lines, then whole rows, then whatever is left. Everything
; that varies per line is decided per row - v, and with it the seam
; test and the carry into the next row - so the seam is tested once a
; group and the line step inside a group is a bare +&07F8 that cannot
; carry (raster 0-6 -> 1-7). Only a row's last raster pays for
; SPR_NEXT_LINE and its fixup. Getting this wrong is not a slow path,
; it is the &07F8 overflow described at the top of this file.
;
; GROUP_LINES - size of the group starting at DE.
; IN : DE = screen address of its first line, B' = lines remaining
; OUT: A = C' = lines in this group (1-8), B' reduced by it
;                                destroys AF
; ---------------------------------------------------------------------
GROUP_LINES:    ld   a,d
                rrca
                rrca
                rrca
                and  7                  ; raster of this line
                neg
                add  a,8                ; lines left in the character row
                exx
                cp   b
                jr   c,.fits
                ld   a,b                ; more than remain: the last group
.fits:          ld   c,a
                ld   a,b
                sub  c
                ld   b,a
                ld   a,c
                exx
                ret

; ---------------------------------------------------------------------
SPR_NEXT_LINE:  ld   a,e                ; 4
                add  a,&F8              ; 8
                ld   e,a                ; 4
                ld   a,d                ; 4
                adc  a,&07              ; 8
                ld   d,a                ; 4
                ret  nc                 ; 16/8  same character row
                ; falls through - SPR_ROW_FIX MUST stay directly below

; ---------------------------------------------------------------------
; SPR_ROW_FIX - raster 7 -> raster 0 of the next character row.
;
; On entry the carry has already reduced DE to v = w*2 + (x AND 1),
; 0..&07FF. The next row is 40 words down, so v += 80, masked back into
; 11 bits, with the page put back on. Because 80 is even, bit 0 - the
; half-word parity - survives untouched, which is why the word index
; never has to be unpacked.
;
; This replaces Module 3's "+&C050", which assumed an 80-byte linear
; stride from start address zero and was wrong for 240 of 1024 scroll
; values.
; IN/OUT: DE            destroys AF
; ---------------------------------------------------------------------
SPR_ROW_FIX:    ld   a,e                ; 4
                add  a,SCR_CHARS * 2    ; 8   40 words = 80 bytes
                ld   e,a                ; 4
                ld   a,d                ; 4
                adc  a,0                ; 8
                and  7                  ; 8   (v + 80) MOD 2048  (D was 0..8)
                add  a,SCREEN_BASE >> 8 ; 8
                ld   d,a                ; 4
                ret                     ; 12

; ---------------------------------------------------------------------
; SPR_NEXT_LINE_W - the line step for a line that took the slow lane.
; Its eight bytes already folded back over the end of the raster block,
; which subtracted 2048, so this owes a whole extra &0800: +&0FF8
; instead of +&07F8. Everything else is identical.
;                                destroys AF
; ---------------------------------------------------------------------
SPR_NEXT_LINE_W:
                ld   a,e
                add  a,&F8
                ld   e,a
                ld   a,d
                adc  a,&0F              ; +&0FF8
                ld   d,a
                ret  nc
                jp   SPR_ROW_FIX

; ---------------------------------------------------------------------
; SCR_NEXT_LINE - DE is at the START of a scanline; move it to the next.
; Plain +&0800, sharing the row fixup. Used by the bullet code and by
; DRAW_BLOCK, neither of which walks a sprite width first.
;                                destroys AF
; ---------------------------------------------------------------------
SCR_NEXT_LINE:  ld   a,d
                add  a,8
                ld   d,a
                ret  nc
                jp   SPR_ROW_FIX        ; D+8 wrapped, so DE = v already

; ---------------------------------------------------------------------
; SPR_STEP_BYTE - advance DE one screen byte, folding the end of the
; 2 KB raster block back to its start: offset 2047 is followed by
; offset 0, NOT by the next raster.
;
; D holds, low to high: offset bits 8-10, raster bits 3-5, page bits
; 6-7. So a carry from E into bit 11 is a wrong raster increment, and
; it is detectable as (D AND 7) having just become 0.
;                                destroys AF
; 40 T with the CALL on the common byte, 84 T on the fold.
; ---------------------------------------------------------------------
SPR_STEP_BYTE:  inc  e                  ; 4
                ret  nz                 ; 16/8
                inc  d                  ; 4
                ld   a,d                ; 4
                and  7                  ; 8
                ret  nz                 ; 16/8  ordinary 256-byte crossing
                ld   a,d                ; 4     offset wrapped 2047 -> 0:
                sub  8                  ; 8     undo the carry that leaked
                ld   d,a                ; 4     into the raster field
                ret                     ; 12
