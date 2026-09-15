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
; SPR_DRAW_SAVE - composite a frame and stash what was underneath, in
; one pass.   SCREEN = (SCREEN AND MASK) OR DATA
;
; IN : HL = frame data (16-byte aligned)
;      DE = screen address of the top-left byte (from SCR_ADDR)
;      BC = save-under buffer, SPR_SAVE_SIZE bytes
; OUT: HL = frame + 768, DE = one scanline past the sprite,
;      BC = save + 384
;      destroys AF,BC,DE,HL and B',C' (the counters).
;
; NOT REENTRANT and NOT INTERRUPT-SAFE: the counters live in the shadow
; BC. Nothing in tilemap.asm, screen.asm or IRQ_HANDLER touches the
; shadow set today - if Module 6's raster split or Module 7's AY player
; ever EXX inside the interrupt, this breaks silently.
;
; Fast byte group 64 T, last byte of a line 68 T, line bookkeeping ~60 T
; against 120 for the per-line seam test this replaced.
; ---------------------------------------------------------------------
SPR_DRAW_SAVE:  exx
                ld   b,SPR_HEIGHT       ; lines remaining
                exx

.group:         call GROUP_LINES        ; C' = lines in this row
                ld   a,d                ; 4   does this ROW cross the seam?
                or   &F8                ; 8   Z iff (D AND 7) = 7, i.e. v >= &700
                inc  a                  ; 4
                jr   nz,.fastline       ; 12/8
                ld   a,e
                cp   SPR_SEAM_LO
                jr   nc,.slowline       ; v >= 2040: the 8 bytes wrap

.fastline:      repeat SPR_WIDTH_BYTES - 1
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
                exx                     ; 4
                dec  c                  ; 4
                exx                     ; 4
                jr   z,.rowend          ; 12/8  the row's last raster
                ld   a,e                ; 4   +&07F8 inside the row: no carry
                add  a,&F8              ; 8   is possible, raster 0-6 -> 1-7
                ld   e,a                ; 4
                ld   a,d                ; 4
                adc  a,7                ; 8
                ld   d,a                ; 4
                jp   .fastline          ; 12
.rowend:        call SPR_NEXT_LINE      ; raster 7 -> next row, with the fixup
                jp   .next

                ; The slow lane: wrap-aware, one byte at a time. About one
                ; frame in 39 sends one group here.
.slowline:      repeat SPR_WIDTH_BYTES
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
                call SPR_NEXT_LINE_W    ; per line: it carries the row fixup
                exx
                dec  c
                exx
                jr   nz,.slowline

.next:          exx
                ld   a,b
                exx
                or   a
                jp   nz,.group
                ret

; ---------------------------------------------------------------------
; SPR_RESTORE / SPR_RESTORE_N - put the saved background back.
;
; IN : HL = save-under buffer, DE = screen address (KARA_LAST_ADDR)
;      SPR_RESTORE_N: B = lines to restore, leaving DE and HL where a
;      second call would carry on. Nothing needs the partial form today -
;      see the raster-gate note in main.asm for why splitting the erase
;      across two waits did not work.
; OUT: HL = save + 8 * lines, DE = one scanline past the last line
;      destroys AF,BC,DE,HL and B',C'.  Not reentrant - see SPR_DRAW_SAVE.
;      BC is UNDEFINED on exit: LDI counts it down and nothing reads it.
;
; The straddle test reads DE, not SCROLL. That is the load-bearing
; property of this whole module: the erase reproduces exactly the byte
; sequence the draw used, even if SCROLL moved in between, because both
; derive the geometry from the same absolute address.
;
; A whole character row is unrolled - 8 LDI + 24 T a line, SPR_NEXT_LINE
; once - and the partial rows at the top and bottom of the sprite go
; through a one-line-at-a-time loop of the same code. A row on the seam
; is two LDI runs with the raster field folded back between them: the
; first n = 2048 - v bytes land at the end of the raster block and carry
; into the raster field, SUB 8 undoes that, the remaining 8 - n bytes
; start the block. That is SPR_STEP_BYTE's rule applied once per line
; instead of once per byte.
;
; Measured: 9,900 T for 48 lines, 11,300 with a row on the seam. The
; erase runs after the beam has passed Kara, so it has to fit between
; her last line and the next VSYNC - see the schedule in main.asm.
; ---------------------------------------------------------------------
SPR_RESTORE:    ld   b,SPR_HEIGHT
SPR_RESTORE_N:  ld   a,b
                exx
                ld   b,a                ; lines remaining
                exx
.group:         call GROUP_LINES        ; A = C' = lines in this row
                ld   c,a
                ld   a,d
                or   &F8
                inc  a
                jr   nz,.fast
                ld   a,e
                cp   SPR_SEAM_LO
                jp   nc,.slowline       ; JP: the unrolled row is 170 bytes

.fast:          ld   a,c
                cp   8
                jp   nz,.partial        ; JP: the unrolled row is in the way
                repeat 7                ; rasters 0-6: +&07F8 each
                repeat SPR_WIDTH_BYTES
                ldi                     ; 20  (not 16: the gate array pads the
                rend                    ;      5 T M-cycle up to 8)
                ld   a,e
                add  a,&F8
                ld   e,a
                ld   a,d
                adc  a,7
                ld   d,a
                rend
                repeat SPR_WIDTH_BYTES  ; raster 7, then the row step
                ldi
                rend
                call SPR_NEXT_LINE
                jr   .next

.partial:       repeat SPR_WIDTH_BYTES  ; C' lines of a row, one at a time.
                ldi                     ; C', not C: LDI counts BC down, so
                rend                    ; a counter in C is eight short after
                exx                     ; every line and the loop runs off
                dec  c                  ; the end of memory
                exx
                jr   z,.plast
                ld   a,e
                add  a,&F8
                ld   e,a
                ld   a,d
                adc  a,7
                ld   d,a
                jr   .partial
.plast:         call SPR_NEXT_LINE      ; the row's last raster - or the
                jr   .next              ; sprite's last line; DE ends right
                                        ; either way

.slowline:      ld   a,e                ; a row on the seam, C' lines
                neg                     ; n = 2048 - v: bytes before the fold
                push af
.run1:          ldi
                dec  a
                jr   nz,.run1
                ld   a,d                ; the run carried into the raster
                sub  8                  ; field: fold offset 2048 back to 0
                ld   d,a
                pop  af
                ld   b,a
                ld   a,8
                sub  b                  ; 8 - n bytes after the fold, 0-7
                jr   z,.run2done
.run2:          ldi
                dec  a
                jr   nz,.run2
.run2done:      call SPR_NEXT_LINE_W    ; per line: it carries the row fixup
                exx
                dec  c
                exx
                jr   nz,.slowline

.next:          exx
                ld   a,b
                exx
                or   a
                jp   nz,.group
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
; OUT: KARA_LAST_ADDR = the absolute address she was drawn at,
;      KARA_LAST_Y = the screen line, for the erase gate.
;      destroys AF,BC,DE,HL,B',C'.
;
; KARA_LAST_ADDR is an ABSOLUTE RAM address and stays valid across a
; scroll step - changing R12/R13 moves the view, not the pixels. What it
; does NOT survive is the incoming column or row being repainted over
; her, which the camera's edge margins rule out (CAM_RIGHT_EDGE + 8
; bytes leaves 7 characters to the incoming column).
; ---------------------------------------------------------------------
KARA_DRAW:      ld   a,(KARA_Y)
                cp   SCR_CHAR_ROWS * 8  ; entirely off the display?
                jr   c,.on_screen
                ld   hl,0               ; ... then do not draw her at all, and
                ld   (KARA_LAST_ADDR),hl ; tell the erase there is nothing to
                ret                     ; put back
                ; Not an optimisation - a correctness fix. Her Y is an
                ; unsigned screen line and the camera can carry her off
                ; either edge during a vertical scroll, which wraps it to
                ; 192-255. Drawn there, her 48 lines run past the 24
                ; displayed character rows, through the 64-word margin,
                ; and fold back over the TOP of the screen - and because
                ; the fold can land two of her own lines on one address,
                ; the save-under holds the first line's output as the
                ; second one's background and the erase leaves her debris
                ; behind. Measured: 32 to 56 bytes of video RAM left wrong
                ; per frame, accumulating, with her at Y = 196..244.
                ;
                ; STILL MISSING: clipping. A sprite that is PARTLY off the
                ; bottom still writes into the margin and, past character
                ; row 23, folds onto the top of the picture. The camera
                ; keeps her away from both edges today; levels 3 and 4
                ; will not, so Module 6 needs a real clip.
.on_screen:     ld   (KARA_LAST_Y),a    ; the erase gate needs the line she
                ld   b,a                ; is ON
                ld   a,(KARA_X)
                ld   c,a
                ld   a,b
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
;      destroys AF,BC,DE,HL,B',C'.  BC is clobbered by SPR_RESTORE's
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
