; =====================================================================
; spanblit.asm - the span-compressed sprite blitter            (MODULE 5)
;
; Kara is 24x64 and only a third of that box has anything in it, so she
; is stored as spans: per line the bytes that are actually drawn and
; nothing else. tools/aseprite2spans.py writes the format and CLAUDE.md
; 7.1 has the numbers.
;
; ---------------------------------------------------------------------
; WHAT THE MEASUREMENT SAID
;
; The first version of this walked one line at a time and cost 43,136 T
; on the heaviest frame - 131 T for each of its 329 span bytes, when the
; composite itself is 72. At 5.7 bytes a line the per-LINE work, not the
; per-byte work, is the blitter: reading (skip, count), computing the
; entry into the unrolled run, testing for the seam, stepping the
; address.
;
; So the frame format groups consecutive lines that share a span - 3.5
; lines out of every 4 do - and everything above is said once per group
; instead of once per line.
;
; ---------------------------------------------------------------------
; THE ERASE SCRIPT IS THE SAVE BUFFER
;
; A span sprite has no fixed shape, so the erase has to be told what the
; draw touched. Reading it back out of the frame would mean decoding the
; groups again, stepping the screen address with the 2 KB fold, and
; keeping the sprite bank paged in - and the erase is the routine with
; the least frame left to spend.
;
; So the draw writes it down as it goes, in the same buffer as the
; background it saves, interleaved:
;
;       db  count                       bytes in this run
;       dw  screen address              where the draw put them
;       db  count bytes                 whatever was underneath
;       ...
;       db  255                         end
;
; The erase is then: read a count, read an address, LDIR. The saved
; bytes are already at (HL) when the count and address have been read,
; so LDIR's source needs no setting up; the addresses were folded
; correctly when the draw computed them, so there is no fold arithmetic
; and no line stepping; and nothing is read from the bank, so the window
; can stay wherever the rest of the frame wants it.
;
; One pointer does all of that, which is the only reason it fits: BC is
; LDIR's counter, DE the screen and HL the script, and there is no
; fourth register pair for a separate shape to live in.
;
; A run is not a line. A span that reaches the end of the 2 KB raster
; block folds back to the block's start, and the two halves are 2 KB
; apart - so such a line writes TWO runs and the erase never learns that
; anything unusual happened.
;
; ---------------------------------------------------------------------
; THE COUNT IS THE ENTRY POINT
;
; SPAN_RUN is twelve identical byte groups, entered N groups from the
; end to write N bytes - the same trick the clipped box blitter in
; sprite.asm uses, and for the same reason: a counted loop costs 24 T a
; byte in bookkeeping on top of 72 T of work.
;
; Picking the entry needs a multiply by the group size and there is no
; register pair free to do it in, so it is a lookup - and the lookup
; index is written into the instruction that reads it:
;
;       ld   (.idx + 1),a       ; A = count
;   .idx:  ld a,(SPAN_ENTRY)    ; ... reads SPAN_ENTRY + count
;
; which works because SPAN_ENTRY is page-aligned and count is 0-12, so
; the low byte of the address IS the index. 32 T, no scratch pair.
;
; SPAN_RUN does not RET. It falls through into the line step and the
; line loop, because it has exactly one caller and the 10 T are worth
; more than the tidiness.
;
; ---------------------------------------------------------------------
; REGISTERS, throughout
;       HL  the frame, walking forward: group headers and mask/data
;       DE  the screen, at the current line's span
;       BC  the script
;       B'  lines left in this group        C'  lines left in the sprite
; =====================================================================

SPAN_MAX_WIDTH  equ 12                  ; 24 pixels
SPAN_MAX_LINES  equ 64
SPAN_GROUP      equ 9                   ; bytes of one SPAN_RUN group
SPAN_END_MARK   equ 255                 ; a count no run can have
                ; Worst case every line is a full-width span that also
                ; straddles the fold, so two runs of header. Nothing
                ; near it in practice - the widest line of the real art
                ; is 11 bytes and the mean is 5.7 - but the buffer has
                ; to survive the worst frame anyone draws later.
SPAN_SCRIPT_MAX equ SPAN_MAX_LINES * (2 * 3 + SPAN_MAX_WIDTH) + 1

; ---------------------------------------------------------------------
; SPAN_DRAW - composite one frame, saving what was underneath and
; writing the erase script.
;
; IN : HL = the frame's first GROUP header - the caller steps past the
;           y0/lines header itself, because only the caller knows how
;           many lines clipping took off the top
;      DE = screen address of box byte 0 on the first drawn line
;      BC = script buffer
;      A  = lines to draw; drawing stops when they run out, so a sprite
;           clipped at the bottom just gets a smaller number
; OUT: the script, terminated; (SPAN_SCRIPT_END) = one past its last
;      byte, for the tests and the overrun assert
;      destroys AF,BC,DE,HL,B',C'
;
; NOT REENTRANT: it self-modifies four immediates per group.
; ---------------------------------------------------------------------
SPAN_DRAW:      or   a
                jp   z,SPAN_DONE
                exx
                ld   c,a                ; lines left in the sprite
                exx

SPAN_GROUP_TOP: ld   a,(hl)             ; 8   lines in this group
                inc  hl                 ; 8
                or   a                  ; 8
                jp   z,SPAN_DONE        ; 12  0 ends the frame

                exx                     ; 4   clip the group to what is
                cp   c                  ; 4   left of the sprite
                jr   c,.fits            ; 12
                ld   a,c                ; 4
.fits:          ld   b,a                ; 4   lines to draw from this group
                ld   a,c                ; 4
                sub  b                  ; 4
                ld   c,a                ; 4
                exx                     ; 4

                ld   a,(hl)             ; 8   bytes per line
                inc  hl                 ; 8
                ld   (SPAN_CNT + 1),a   ; 16  the script header writes it
                or   a                  ; 8
                jp   z,SPAN_BLANK       ; 12  count 0: lines with nothing on
                ld   (.idx + 1),a       ; 16  the entry into SPAN_RUN
                neg                     ; 8   and the line step, which is
                ld   (SPAN_STEP_N + 1),a ; 16 the line step, &0800 - count
                ld   (SPAN_STEPW_N + 1),a ; 16 ... and the folded lane's

                ; Move to this group's span. The delta is signed and
                ; sign-extended, so ADD/ADC takes it either way with no
                ; branch - but it must not leak out of the 2 KB raster
                ; block, so only the three offset bits of the sum are
                ; kept and the raster and page come back unchanged.
                ld   a,(hl)             ; 8   dskip low
                inc  hl                 ; 8
                add  a,e                ; 4
                ld   e,a                ; 4
                ld   a,(hl)             ; 8   dskip high: 0 or &FF
                inc  hl                 ; 8
                adc  a,d                ; 4
                xor  d                  ; 4   the bits that changed ...
                and  7                  ; 8   ... of which only these may
                xor  d                  ; 4   ... so put the rest back
                ld   d,a                ; 4
.idx:           ld   a,(SPAN_ENTRY)     ; 16
                ld   (SPAN_ENTER + 1),a ; 16
                ; falls into the line loop

; ---------------------------------------------------------------------
; One line. Can the run reach the end of the 2 KB block? Only if the
; offset is within SPAN_MAX_WIDTH of 2048, which needs its top three
; bits set and a high low byte - so the cheap half of the test rejects
; more than 95% of lines.
; ---------------------------------------------------------------------
SPAN_LINE:      ld   a,e                ; 4
                cp   256 - SPAN_MAX_WIDTH   ; 8
                jp   nc,SPAN_MAYBE_FOLD ; 12  (JR is out of range past SPAN_RUN)

SPAN_HEADER:                            ; the run's script header
SPAN_CNT:       ld   a,0                ; 8   count, patched per group
                ld   (bc),a             ; 8
                inc  bc                 ; 8
                ld   a,e                ; 4
                ld   (bc),a             ; 8
                inc  bc                 ; 8
                ld   a,d                ; 4
                ld   (bc),a             ; 8
                inc  bc                 ; 8
SPAN_ENTER:     jp   SPAN_RUN           ; 12  patched per group

; ---------------------------------------------------------------------
; SPAN_RUN - up to twelve composited bytes, entered N groups from the
; end, falling through to the line step. Must not cross a page:
; SPAN_ENTER patches only the low byte of the jump into it, and
; main.asm asserts it.
; ---------------------------------------------------------------------
                align 128
SPAN_RUN:       repeat SPAN_MAX_WIDTH
                ld   a,(de)             ; 8   the background ...
                ld   (bc),a             ; 8   ... into the script
                and  (hl)               ; 8   punch the sprite's hole in it
                inc  hl                 ; 8
                or   (hl)               ; 8   and fill the hole
                inc  hl                 ; 8
                ld   (de),a             ; 8
                inc  de                 ; 8
                inc  bc                 ; 8
                rend                    ;     72 T a byte
SPAN_RUN_END:

                ; Next line: DE is at the span's end, so it wants
                ; &0800 - count. The carry out is the same one
                ; SCR_NEXT_LINE tests, because -count borrows from the
                ; +8 exactly when the byte walk did not carry already.
SPAN_STEP:      ld   a,e                ; 4
SPAN_STEP_N:    add  a,0                ; 8   -count, patched per group
                                        ;     (the label is on the ADD: the
                                        ;      LD above is one byte, so a
                                        ;      "+1" off the wrong label
                                        ;      patches an opcode)
                ld   e,a                ; 4
                ld   a,d                ; 4
                adc  a,7                ; 8
                ld   d,a                ; 4
SPAN_STEP_TAIL: jr   nc,.same_row       ; 12
                call SPR_ROW_FIX        ;     raster 7 -> next char row
.same_row:      exx                     ; 4
                dec  b                  ; 4
                exx                     ; 4
                jp   nz,SPAN_LINE       ; 12

SPAN_NEXT_GROUP:
                exx                     ; 4   any of the sprite left?
                ld   a,c                ; 4
                exx                     ; 4
                or   a                  ; 8
                jp   nz,SPAN_GROUP_TOP  ; 12

SPAN_DONE:      ld   a,SPAN_END_MARK
                ld   (bc),a
                inc  bc
                ld   (SPAN_SCRIPT_END),bc
                ret

; ---------------------------------------------------------------------
; Lines with nothing on them. The exporter keeps them - the gap between
; her arm and her boot is one byte and a second index to skip it would
; cost more than it saves - so all that happens is the address walks.
; ---------------------------------------------------------------------
SPAN_BLANK:     inc  hl                 ; past the delta, which is 0
                inc  hl
.line:          ld   a,d
                add  a,8
                ld   d,a
                jr   nc,.same_row
                call SPR_ROW_FIX
.same_row:      exx
                dec  b
                exx
                jp   nz,.line
                jp   SPAN_NEXT_GROUP

; ---------------------------------------------------------------------
; The offset is within SPAN_MAX_WIDTH of the end of the raster block.
; If the run really does cross it, it goes down as two runs: the bytes
; that fit, then the rest at the offset the block started from. The
; erase reads runs, not lines, so it needs to know nothing about this.
; ---------------------------------------------------------------------
SPAN_MAYBE_FOLD:
                ld   a,d
                and  7
                cp   7
                jp   nz,SPAN_HEADER     ; a plain 256-byte crossing is fine
                ld   a,e
                neg                     ; bytes left in the block, 1..11
                ld   (SPAN_N1),a
                ld   (.split + 1),a
                ld   a,(SPAN_CNT + 1)   ; count
.split:         sub  0
                jp   c,SPAN_HEADER      ; stops short of the wrap after all
                jp   z,SPAN_HEADER
                ld   (SPAN_N2),a
                ld   a,(SPAN_N1)
                call SPAN_SLOW          ; the bytes before the wrap
                ld   a,d                ; DE is at offset 0 of the NEXT
                sub  8                  ; raster; fold it back to offset 0
                ld   d,a                ; of this one
                ld   a,(SPAN_N2)
                call SPAN_SLOW          ; and the rest
                ; This line's step owes an extra &0800, because the fold
                ; took one off. Undoing it with a separate ADD to D does
                ; not work: at raster 7 with the offset high, D is &F8
                ; and +8 carries out of the byte, throwing away the very
                ; carry that tells the step it crossed a character row.
                ; So it goes into the step as +&1000 - count, which is
                ; SPR_NEXT_LINE_W's trick for the same reason.
                ld   a,e
SPAN_STEPW_N:   add  a,0                ; -count, patched with the other
                ld   e,a
                ld   a,d
                adc  a,&0F
                ld   d,a
                jp   SPAN_STEP_TAIL

; ---------------------------------------------------------------------
; SPAN_SLOW - one run, header and bytes, a byte at a time with the
; count in a self-modified immediate.
;
; SPAN_RUN cannot be used here: it falls through into the line step,
; which is exactly what makes it cheap, and a split line needs to come
; back for its second half. A second RET-terminated copy of the
; unrolled block would cost 109 bytes to speed up a case that happens
; on about one line in two hundred, so this lane pays 112 T a byte
; instead of 72 and nobody notices.
;
; IN : A = count (>= 1), DE = screen, BC = script, HL = mask/data pairs
;                                                 destroys AF
; ---------------------------------------------------------------------
SPAN_SLOW:      ld   (bc),a
                inc  bc
                ld   (.n + 1),a
                ld   a,e
                ld   (bc),a
                inc  bc
                ld   a,d
                ld   (bc),a
                inc  bc
.loop:          ld   a,(de)
                ld   (bc),a
                and  (hl)
                inc  hl
                or   (hl)
                inc  hl
                ld   (de),a
                inc  de
                inc  bc
.n:             ld   a,0
                dec  a
                ld   (.n + 1),a
                jr   nz,.loop
                ret

                align 256
SPAN_ENTRY:     repeat SPAN_MAX_WIDTH + 1, n
                db (SPAN_RUN_END - (n - 1) * SPAN_GROUP) AND 255
                rend

SPAN_N1:        db 0            ; the folded lane's two halves
SPAN_N2:        db 0
SPAN_SCRIPT_END:dw 0

; ---------------------------------------------------------------------
; SPAN_ERASE - put back what SPAN_DRAW saved.
;
; IN : none. Walks the script from the start.
;      destroys AF,BC,DE,HL
;
; No bank, no fold arithmetic, no line stepping: every address in the
; script was worked out by the draw.
; ---------------------------------------------------------------------
SPAN_ERASE:     ld   hl,SPAN_SCRIPT
.run:           ld   a,(hl)             ; 8   count, or the end mark
                inc  hl                 ; 8
                inc  a                  ; 8
                ret  z                  ; 16/8
                dec  a                  ; 8
                ld   c,a                ; 4
                ld   b,0                ; 8
                ld   e,(hl)             ; 8
                inc  hl                 ; 8
                ld   d,(hl)             ; 8
                inc  hl                 ; 8
                or   a                  ; 8   LDIR with BC = 0 would move
                jr   z,.run             ; 12  65536 bytes
                ldir                    ;     the saved bytes are already
                jr   .run               ; 12  at (HL), which is the point
