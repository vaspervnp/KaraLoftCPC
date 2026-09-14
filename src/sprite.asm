; =====================================================================
; sprite.asm - masked sprite blitter with save-under restore
;
; Frame format (produced by tools/png2sprite.py): mask and data
; interleaved per byte, 8 bytes wide, 48 lines, so one pointer walks
; both. Frames MUST be 16-byte aligned - the inner loop advances the
; sprite pointer with INC L, which is 2 T-states cheaper than INC HL but
; cannot carry into H. A line is exactly 16 bytes, so alignment
; guarantees a line never straddles a page.
; =====================================================================

SPR_WIDTH_BYTES equ 8
SPR_HEIGHT      equ 48
SPR_FRAME_SIZE  equ SPR_WIDTH_BYTES * SPR_HEIGHT * 2    ; 768, mask + data
SPR_SAVE_SIZE   equ SPR_WIDTH_BYTES * SPR_HEIGHT        ; 384

; ---------------------------------------------------------------------
; SPR_DRAW_SAVE - composite a frame onto the screen and stash what was
; underneath, in ONE pass. The screen byte is written to the save buffer
; on its way into the ALU, which is cheaper than a separate save pass.
;
;   SCREEN = (SCREEN AND MASK) OR DATA
;
; IN : HL = frame data (16-byte aligned)
;      DE = screen address of the top-left byte
;      BC = save-under buffer, SPR_SAVE_SIZE bytes
;      destroys AF,BC,DE,HL
;
; Cost: 55 T per byte, 57 for the last byte of a line (its increment has
; to carry), 42 to step to the next scanline and 40 for the loop
; counter. About 520 T per line, so roughly 25,000 for all 48 - see
; CLAUDE.md 9 for what that means for the frame budget.
; ---------------------------------------------------------------------
SPR_DRAW_SAVE:  ld   a,SPR_HEIGHT
                ld   (SPR_COUNT),a

.line:          repeat SPR_WIDTH_BYTES - 1
                ld   a,(de)             ; 7   screen as it stands
                ld   (bc),a             ; 7   ... straight into the save buffer
                and  (hl)               ; 7   punch the sprite's hole in it
                inc  l                  ; 4
                or   (hl)               ; 7   drop the sprite in the hole
                inc  l                  ; 4
                ld   (de),a             ; 7
                inc  de                 ; 6
                inc  bc                 ; 6
                rend
                ld   a,(de)             ; last byte: this is the 16th increment
                ld   (bc),a             ; of the line, so it must carry into H
                and  (hl)
                inc  l
                or   (hl)
                inc  hl
                ld   (de),a
                inc  de
                inc  bc

                call SPR_NEXT_LINE      ; DE -= 8, DE += one scanline

                ld   a,(SPR_COUNT)
                dec  a
                ld   (SPR_COUNT),a
                jp   nz,.line
                ret

; ---------------------------------------------------------------------
; SPR_RESTORE - put the saved background back. Straight copy, so LDI
; carries it: 16 T per byte against 26 for a load/store pair.
;
; IN : HL = save-under buffer
;      DE = screen address of the top-left byte
;      destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
SPR_RESTORE:    ld   a,SPR_HEIGHT
                ld   (SPR_COUNT),a
                ld   bc,SPR_SAVE_SIZE   ; LDI only uses BC for its flag here

.line:          repeat SPR_WIDTH_BYTES
                ldi                     ; 16
                rend

                call SPR_NEXT_LINE

                ld   a,(SPR_COUNT)
                dec  a
                ld   (SPR_COUNT),a
                jp   nz,.line
                ret

; ---------------------------------------------------------------------
; SPR_NEXT_LINE - DE is sitting 8 bytes past the start of the line it
; just drew; move it to the start of the next scanline.
;
;   +&0800 - 8 = +&07F8 within a character row
;   and the classic +&C050 fixup when that carries out of &FFFF
;
; Done with 8-bit arithmetic on A so that BC and HL, which hold the save
; buffer and the sprite, stay untouched.
;                                destroys AF
; ---------------------------------------------------------------------
SPR_NEXT_LINE:  ld   a,e                ; 4
                add  a,&F8              ; 7
                ld   e,a                ; 4
                ld   a,d                ; 4
                adc  a,&07              ; 7
                ld   d,a                ; 4
                ret  nc                 ; 11/5  same character row
                ld   a,e                ; crossed into the next character row
                add  a,&50
                ld   e,a
                ld   a,d
                adc  a,&C0
                ld   d,a
                ret

; ---------------------------------------------------------------------
; SCR_NEXT_LINE - DE is at the start of a scanline; move it to the start
; of the next one. Plain +&0800, with the same &C050 fixup when that
; carries out of &FFFF. Used by anything that does not walk the full
; sprite width first.
;                                destroys AF
; ---------------------------------------------------------------------
SCR_NEXT_LINE:  ld   a,d
                add  a,8
                ld   d,a
                ret  nc
                ld   a,e
                add  a,&50
                ld   e,a
                ld   a,d
                adc  a,&C0
                ld   d,a
                ret

SPR_COUNT:      db 0

; ---------------------------------------------------------------------
; KARA_DRAW / KARA_ERASE - the player sprite, wrapped up with its
; position and the address it was last drawn at.
; ---------------------------------------------------------------------
KARA_DRAW:      ld   a,(KARA_Y)
                call SCREEN_LINE
                ld   a,(KARA_X)
                ld   e,a
                ld   d,0
                add  hl,de
                ld   (KARA_LAST_ADDR),hl
                ex   de,hl              ; DE = screen
                ld   a,(KARA_FRAME)
                call KARA_FRAME_PTR     ; HL = frame data
                ld   bc,KARA_SAVE
                jp   SPR_DRAW_SAVE

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
