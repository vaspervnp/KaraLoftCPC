; =====================================================================
; sprite.asm - scroll-aware masked sprite blitter          (MODULE 5)
;
; Frame format (tools/png2sprite.py): mask and data interleaved per
; byte, 8 bytes wide, 48 lines, so one pointer walks both. Frames MUST
; be 16-byte aligned - the FAST inner loop advances the sprite pointer
; with INC L, which cannot carry into H. main.asm asserts it.
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
                ld   d,0                    ; 4
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
; SPR_DRAW_SAVE - composite a frame and stash what was underneath, in
; one pass.   SCREEN = (SCREEN AND MASK) OR DATA
;
; IN : HL = frame data (16-byte aligned)
;      DE = screen address of the top-left byte (from SCR_ADDR)
;      BC = save-under buffer, SPR_SAVE_SIZE bytes
; OUT: HL = frame + 768, DE = one scanline past the sprite,
;      BC = save + 384
;      destroys AF,BC,DE,HL and B' (the line counter).
;
; NOT REENTRANT and NOT INTERRUPT-SAFE: the line counter lives in the
; shadow B. Nothing in tilemap.asm, screen.asm or IRQ_HANDLER touches
; the shadow set today - if Module 6's raster split or Module 7's AY
; player ever EXX inside the interrupt, this breaks silently.
;
; 29,884 T measured (33,052 T when a character row straddles the seam).
; Fast byte group 64 T, last byte of a line 68 T, line test 28 T,
; counter 24 T, SPR_NEXT_LINE 68 T / 120 T across a character row.
; ---------------------------------------------------------------------
SPR_DRAW_SAVE:  exx
                ld   b,SPR_HEIGHT           ; the counter, not a memory static
                exx
                jp   .line

                ; The slow lane sits BEFORE the loop head on purpose: it
                ; lets the fast path fall through to .tail instead of
                ; paying a JP on all 48 lines.
.slow:          repeat SPR_WIDTH_BYTES
                ld   a,(de)             ; 8   screen as it stands
                ld   (bc),a             ; 8   ... straight into the save buffer
                and  (hl)               ; 8   punch the sprite's hole in it
                inc  hl                 ; 8   INC HL, not INC L: this lane does
                or   (hl)               ; 8   not rely on the 16-byte alignment
                inc  hl                 ; 8
                ld   (de),a             ; 8
                inc  bc                 ; 8
                call SPR_STEP_BYTE      ; 40  wrap-aware +1   (104 T per byte)
                rend
                call SPR_NEXT_LINE_W
                jp   .tail

.line:          ld   a,d                ; 4   does this line cross the seam?
                or   &F8                ; 8   Z iff (D AND 7) = 7, i.e. v >= &700
                inc  a                  ; 4
                jp   nz,.fast           ; 12  28 T on the common line
                ld   a,e                ; 4
                cp   SPR_SEAM_LO        ; 8
                jp   nc,.slow           ; 12  v >= 2040: the 8 bytes wrap

.fast:          repeat SPR_WIDTH_BYTES - 1
                ld   a,(de)             ; 8
                ld   (bc),a             ; 8
                and  (hl)               ; 8
                inc  l                  ; 4
                or   (hl)               ; 8
                inc  l                  ; 4
                ld   (de),a             ; 8
                inc  de                 ; 8   safe: v <= 2039, so the eight
                inc  bc                 ; 8   bytes are contiguous in RAM
                rend                    ;     64 T per byte group
                ld   a,(de)             ; last byte: the 16th sprite increment,
                ld   (bc),a             ; so it must carry into H
                and  (hl)
                inc  l
                or   (hl)
                inc  hl
                ld   (de),a
                inc  de
                inc  bc
                call SPR_NEXT_LINE

.tail:          exx                     ; 4
                dec  b                  ; 4
                exx                     ; 4
                jp   nz,.line           ; 12  24 T, against 48 for a memory count
                ret

; ---------------------------------------------------------------------
; SPR_RESTORE - put the saved background back.
;
; IN : HL = save-under buffer, DE = screen address (KARA_LAST_ADDR)
; OUT: HL = save + 384, DE = one scanline past
;      destroys AF,BC,DE,HL and B'.  Not reentrant - see SPR_DRAW_SAVE.
;      BC is UNDEFINED on exit: a straddling line skips its LDIs, so the
;      count no longer reaches zero. Nothing reads it; LDI only uses BC
;      for its flag here.
;
; The straddle test reads DE, not SCROLL. That is the load-bearing
; property of this whole module: the erase reproduces exactly the byte
; sequence the draw used, even if SCROLL moved in between, because both
; derive the geometry from the same absolute address.
;
; 14,392 T measured (17,872 T when a character row straddles).
; ---------------------------------------------------------------------
SPR_RESTORE:    exx
                ld   b,SPR_HEIGHT
                exx
                ld   bc,SPR_SAVE_SIZE   ; LDI only uses BC for its flag here
                jp   .line

.slow:          repeat SPR_WIDTH_BYTES
                ld   a,(hl)             ; 8
                ld   (de),a             ; 8
                inc  hl                 ; 8
                call SPR_STEP_BYTE      ; 40  64 T per byte against 20 for LDI
                rend
                call SPR_NEXT_LINE_W
                jp   .tail

.line:          ld   a,d                ; 4
                or   &F8                ; 8
                inc  a                  ; 4
                jp   nz,.fast           ; 12
                ld   a,e                ; 4
                cp   SPR_SEAM_LO        ; 8
                jp   nc,.slow           ; 12

.fast:          repeat SPR_WIDTH_BYTES
                ldi                     ; 20  (not 16: the gate array pads the
                rend                    ;      5 T M-cycle up to 8)
                call SPR_NEXT_LINE

.tail:          exx
                dec  b
                exx
                jp   nz,.line
                ret

; ---------------------------------------------------------------------
; SPR_NEXT_LINE - DE is 8 bytes past the start of the line just drawn;
; move it to the start of the next scanline.  +&0800 - 8 = +&07F8.
;
; The carry out of &FFFF is not a quirk to be patched around, it IS the
; test: the page bits are always &C0, so raster 7 is &F800-&FFFF, so
; the carry happens exactly when a character row boundary is crossed -
; and what it leaves in DE is exactly v, the masked byte offset.
;
; PRECONDITION, enforced by the caller's per-line test and NOT by this
; routine: the line just drawn had v <= 2039. At v >= 2040 the eight
; INC DEs have already taken DE past &FFFF to &0000-&0007, the +&07F8
; then does NOT carry, the fixup below is skipped, and this returns
; &07F8-&07FF - outside VRAM, over the Z80 restart vectors. Verified on
; the emulator: fed DE = &0000 it returns &07F8. Those lines must go to
; the slow lane and end with SPR_NEXT_LINE_W instead.
;
; IN/OUT: DE.  Only DE and AF are written, which is what lets the caller
; keep the save buffer in BC and the sprite in HL.
;                                destroys AF
; 68 T with the CALL, 120 T across a character row.
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

; ---------------------------------------------------------------------
; KARA_DRAW - the player sprite.
;
; IN : none.  Reads KARA_X, KARA_Y, KARA_FRAME, SCROLL.
; OUT: KARA_LAST_ADDR = the absolute address she was drawn at.
;      destroys AF,BC,DE,HL,B'.
;
; KARA_LAST_ADDR is an ABSOLUTE RAM address and stays valid across a
; scroll step - changing R12/R13 moves the view, not the pixels. What it
; does NOT survive is the incoming column or row being repainted, so the
; erase must run BEFORE the scroll step. See the ordering note in
; main.asm's MAIN_LOOP.
; ---------------------------------------------------------------------
KARA_DRAW:      ld   a,(KARA_X)
                ld   c,a
                ld   a,(KARA_Y)
                call SCR_ADDR           ; HL = top-left, under SCROLL
                ld   (KARA_LAST_ADDR),hl
                ex   de,hl              ; DE = screen
                ld   a,(KARA_FRAME)
                call KARA_FRAME_PTR     ; HL = frame data; scratches BC, NOT DE
                ld   bc,KARA_SAVE
                jp   SPR_DRAW_SAVE

; ---------------------------------------------------------------------
; KARA_ERASE - put the background back.
;
; IN : none.  Reads KARA_LAST_ADDR.
;      destroys AF,BC,DE,HL,B'.  BC is clobbered by SPR_RESTORE's
;      "ld bc,SPR_SAVE_SIZE", not by anything visible here.
;
; Pairs with KARA_DRAW, which must run every frame: this never clears
; KARA_LAST_ADDR, so a skipped draw would erase against a stale buffer.
; CLAUDE.md 9's "only redraw when she moves" needs that pairing made
; explicit before it is safe.
; ---------------------------------------------------------------------
KARA_ERASE:     ld   de,(KARA_LAST_ADDR)
                ld   a,d
                or   e
                ret  z                  ; nothing drawn yet
                ld   hl,KARA_SAVE
                jp   SPR_RESTORE

; IN: A = frame index   OUT: HL = frame data     destroys AF,BC
;
; Scratches BC, NOT DE: KARA_DRAW has the screen address in DE by the
; time it calls this, and handing SPR_DRAW_SAVE the sprite base as its
; destination writes the composite straight over the sprite data.
KARA_FRAME_PTR: ld   b,a
                add  a,a
                add  a,b                ; frame * 3
                ld   h,a
                ld   l,0                ; * 256 -> frame * 768
                ld   bc,KARA_SPRITES
                add  hl,bc
                ret
