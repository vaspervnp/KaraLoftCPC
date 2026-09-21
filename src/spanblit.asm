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
; SPAN_CLIP_V - how much of a frame is on the display, vertically.
;
; Every caller of SPAN_DRAW needs this and none of them needs a
; different version of it: the frame's header says where its first
; drawn line sits inside the box and how many lines it stored, and the
; display is 0 to SCR_LINES whoever is being drawn. It was written out
; inside KARA_SPAN_DRAW first; the enemy is the second caller and two
; copies of a clip is how a sprite ends up folding over the top of the
; picture in one of them and not the other.
;
; IN : HL = the frame's header - its y0 byte
;      A  = the screen line the BOX's line 0 sits on. It is UNSIGNED,
;           so 192-255 means "above the top edge", which is what the
;           camera produces when it carries a sprite off that edge.
; OUT: HL = the frame's first group header
;      A  = the first screen line actually drawn
;      C  = lines to draw - 0 when none of it shows, and the caller
;           must still call SPAN_DRAW so the script is terminated
;      (SPAN_SKIP) = lines dropped off the top
;      destroys AF,DE
;
; IT DOES NOT CLIP IN X, AND THAT IS A DIFFERENT JOB RATHER THAN A
; MISSING HALF OF THIS ONE. A line is dropped in Y and a line is CUT in
; X, so the X clip cannot be a count handed to the fast path: it is a
; per-line correction to the frame pointer, in a loop that is at its
; floor. SPAN_DRAW_CX is that lane (CLAUDE.md 8.2, module 6d), and
; KARA_SPAN_DRAW picks it with one comparison. The enemy stays on the
; fast one deliberately - its drawable window keeps its whole box a
; character clear of both edges, because it is a persistent sprite and
; the incoming column would recycle its pixels (CLAUDE.md 8.7).
; ---------------------------------------------------------------------
SPAN_CLIP_V:    ld   d,a
                ld   a,(hl)             ; y0 - the first line of the box
                inc  hl                 ; with anything on it
                ld   e,(hl)             ; lines stored
                inc  hl                 ; ... and HL is now the groups
                add  a,d                ; screen line of that first line
                ld   d,a
                xor  a
                ld   (SPAN_SKIP),a

                ld   a,d
                cp   SCR_LINES
                jr   nc,.above          ; 192-255: above the top edge

                ; the top is on the display; how many lines fit below it
                ld   a,SCR_LINES
                sub  d
                cp   e
                jr   c,.clipped         ; the bottom runs off
                ld   a,e
.clipped:       ld   c,a                ; lines to draw
                ld   a,d
                ret

.above:         neg                     ; 256 - top = lines above line 0
                cp   e
                jr   nc,.culled         ; more than it has: nothing shows
                ld   (SPAN_SKIP),a
                ld   c,a
                ld   a,e
                sub  c                  ; what is left below line 0
                ld   c,a
                xor  a                  ; ... drawn from the top line
                ret

.culled:        xor  a
                ld   (SPAN_SKIP),a
                ld   c,a                ; nothing to draw, but the script
                ret                     ; still has to be terminated

; ---------------------------------------------------------------------
; SPAN_DRAW - composite one frame, saving what was underneath and
; writing the erase script.
;
; IN : HL = the frame's first GROUP header - the caller steps past the
;           y0/lines header itself
;      DE = screen address of box byte 0 on the FIRST DRAWN line
;      BC = script buffer
;      A  = lines to draw; drawing stops when they run out, so a sprite
;           clipped at the bottom just gets a smaller number
;      (SPAN_SKIP) = lines to drop off the TOP, for a sprite clipped
;           there. Those lines' data is walked past without drawing,
;           but their dskip still counts - the deltas are cumulative,
;           so a skipped group still moves where the next one starts.
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
                ld   (SPAN_NL),a        ; 16  the skip path needs it

                ld   a,(hl)             ; 8   bytes per line
                inc  hl                 ; 8
                ld   (SPAN_CNT + 1),a   ; 16  the script header writes it
                ld   (SPAN_STRIDE),a    ; 16  ... and so does the skip walk
                or   a                  ; 8
                jp   z,SPAN_BLANK       ; 12  count 0: lines with nothing on
                ld   (SPAN_IDX + 1),a   ; 16  the entry into SPAN_RUN
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
                ld   a,(SPAN_SKIP)      ; 16  still dropping lines off the
                or   a                  ; 8   top?
                jp   nz,SPAN_DO_SKIP    ; 12

SPAN_CLIP_N:    ld   a,(SPAN_NL)        ; 16  how many of this group's lines
                exx                     ; 4   are still inside the sprite
                cp   c                  ; 4
                jr   c,.fits            ; 12
                ld   a,c                ; 4
.fits:          ld   b,a                ; 4
                ld   a,c                ; 4
                sub  b                  ; 4
                ld   c,a                ; 4
                exx                     ; 4
                                        ;     B cannot be 0 here: the budget
                                        ;     was non-zero on entry and
                                        ;     SPAN_NEXT_GROUP stops as soon
                                        ;     as it reaches zero
SPAN_IDX:       ld   a,(SPAN_ENTRY)     ; 16  patched with the count above
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
                ld   a,(SPAN_SKIP)
                or   a
                jr   z,.clip
                ; Blank lines carry no data, so skipping them is only a
                ; matter of counting: nothing to walk past.
                ;
                ; B IS THE SCRIPT POINTER'S HIGH BYTE. It looks like a
                ; free register here - the line counters are in the
                ; shadow set and A is busy - and it is not; using it
                ; sent the save-under into SPAN_ENTRY and corrupted
                ; every later frame. The two operands go in immediates
                ; instead.
                ld   (.sk + 1),a
                ld   a,(SPAN_NL)
                ld   (.nl + 1),a
                ld   a,(SPAN_SKIP)
.nl:            cp   0                  ; skip vs the group's lines
                jr   nc,.all_skipped
                ld   (.sub + 1),a
                ld   a,(SPAN_NL)
.sub:           sub  0                  ; part of the group survives
                ld   (SPAN_NL),a
                xor  a
                ld   (SPAN_SKIP),a
                jr   .clip
.all_skipped:   ld   a,(SPAN_NL)        ; skip -= nlines, all of it above
                neg                     ; the top edge
.sk:            add  a,0
                ld   (SPAN_SKIP),a
                jp   SPAN_GROUP_TOP

.clip:          ld   a,(SPAN_NL)
                exx
                cp   c
                jr   c,.fits
                ld   a,c
.fits:          ld   b,a
                ld   a,c
                sub  b
                ld   c,a
                exx
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
; SPAN_DO_SKIP - this group starts above the top of the display, whole
; or in part. Its pixel data is walked past; its delta has already been
; applied, because the deltas are cumulative and a group that is not
; drawn still moves where the next one starts.
;
; The walk is a loop of adds rather than a multiply: it costs up to
; 3,800 T, and it only happens on the frames where a vertical scroll has
; carried her off the top edge.
; ---------------------------------------------------------------------
SPAN_DO_SKIP:   ld   (.sk + 1),a        ; the lines still to skip. NOT in B:
                                        ; B is the script pointer's high
                                        ; byte - see SPAN_BLANK.
                ld   a,(SPAN_STRIDE)    ; the group's bytes a line ...
                add  a,a                ; ... as mask/data pairs
                ld   (.step + 1),a
                ld   a,(SPAN_NL)
                ld   (.nl + 1),a
                ld   a,(SPAN_SKIP)
.nl:            cp   0                  ; skip vs the group's lines
                jr   nc,.whole          ; all of them are above the edge

                ld   (.n + 1),a         ; part of it survives: walk past
                ld   (.sub + 1),a       ; `skip` lines and draw the rest
                xor  a
                ld   (SPAN_SKIP),a
                ld   a,(SPAN_NL)
.sub:           sub  0
                ld   (SPAN_NL),a
                call .walk
                jp   SPAN_CLIP_N

.whole:         ld   a,(SPAN_NL)        ; all of them walked past, and the
                ld   (.n + 1),a         ; skip shrinks by exactly that many
                neg
.sk:            add  a,0
                ld   (SPAN_SKIP),a
                call .walk
                jp   SPAN_GROUP_TOP

.walk:          ld   a,l                ; HL += n * (count * 2)
.step:          add  a,0
                ld   l,a
                jr   nc,.no_carry
                inc  h
.no_carry:
.n:             ld   a,0
                dec  a
                ld   (.n + 1),a
                jr   nz,.walk
                ret

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

                ; ZERO IS NOT THE SAFE CASE. A run that ends EXACTLY on
                ; the last byte of the block - &FFFD..&FFFF - wraps no
                ; word, but the last INC DE leaves DE = &0000, and from
                ; there SPAN_STEP's +&0800 does not carry, SPR_ROW_FIX
                ; is skipped and the next line is written at &07FD, over
                ; the core. So it takes the folded lane too, with an
                ; empty second half: the fold-back and the wide step are
                ; exactly what put the pointer right.
                ld   (SPAN_N2),a
                ld   a,(SPAN_N1)
                call SPAN_SLOW          ; the bytes before the wrap
                ld   a,d                ; DE is at offset 0 of the NEXT
                sub  8                  ; raster; fold it back to offset 0
                ld   d,a                ; of this one
                ld   a,(SPAN_N2)
                or   a
                call nz,SPAN_SLOW       ; and the rest, if there is any
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

; =====================================================================
; THE CLIPPED LANE - the same frame, cut off at the left and right
; edges of the display.                                        (6d)
;
; WHAT IT IS FOR. Nothing here clipped in X, and the damage was
; measured off the erase script rather than argued about: at KARA_X 74
; three of her nine occupied columns fold onto column 0 of the NEXT
; character row, and off the left edge at -6 she is drawn WHOLE, ten
; bytes and twenty-four lines away from where she is - a second
; heroine, in the middle of the picture. CLAUDE.md 8.10 said the
; blitter culled her there. It did not; there was no cull and no clip.
;
; WHY IT IS A LANE AND NOT A BRANCH IN THE FAST ONE. SPAN_DRAW is at
; its floor (CLAUDE.md 9): the composite is nine instructions, all 8 T
; after the gate array's padding, and everything that varies per group
; is patched into an immediate so the per-LINE work is a jump, an add
; and a test. An X clip cannot live there, because the bytes DRAWN on
; a line stop matching the bytes STORED for it - so the frame pointer
; has to be corrected on EVERY line, and there is nowhere in that loop
; to put the correction that does not also charge the frames which are
; nowhere near an edge. This lane costs the fast one one comparison in
; its caller and nothing at all per group or per line.
;
; AND IT IS AFFORDABLE BECAUSE IT IS CLIPPED. It composites through
; SPAN_SLOW - the byte-at-a-time run the fold already uses - and
; measured over a whole 768-byte box it is 141 T a byte against the
; fast lane's 87.5. A sprite that needs it is by definition partly off
; the screen, so the bytes it does not draw are the bytes it does not
; pay for: at KARA_X -6 it draws 384 of the 768 for 65,696 T, which is
; less than the fast lane spends drawing all of them. The worst case
; is a box one column short of fitting, and the table is in
; CLAUDE.md 8.2.
;
; WHAT IT DUPLICATES IS THE DANGEROUS PART. SPAN_CLIP_V's own header
; says two copies of a clip is how a sprite ends up folding over the
; top of the picture in one of them and not the other - and CX_RUN is
; a second copy of the 2 KB fold, which is CLAUDE.md 9's third wiring
; bug. What holds them together is that tools/test_xclip.py drives
; this lane across every column AND every fold position against the
; same independent model tools/test_spanblit.py runs on the other.
; =====================================================================

; ---------------------------------------------------------------------
; SPAN_DRAW_CX - SPAN_DRAW's inputs, plus (SPAN_X).
;
; IN : HL = the frame's first GROUP header
;      DE = screen address of box byte 0 on the FIRST DRAWN line, which
;           for a box off the left edge is a SIGNED column - SCR_ADDR
;           sign-extends now, and the ring's own wrap is what makes it
;           the right address
;      BC = script buffer      A = lines to draw
;      (SPAN_SKIP) = lines to drop off the TOP
;      (SPAN_X) = the box's screen byte column, SIGNED: &FA is six
;           bytes off the left edge
; OUT: the same script the fast lane writes, which the same erase
;      replays; (SPAN_SCRIPT_END) as before
;      destroys AF,BC,DE,HL,B',C'
; ---------------------------------------------------------------------
SPAN_DRAW_CX:   or   a
                jp   z,SPAN_DONE
                exx
                ld   c,a                    ; lines left in the sprite
                exx
                ld   a,(SPAN_X)
                ld   (CX_COL),a             ; the column of box byte 0, and
                                            ; then of each group's span

CX_GROUP:       ld   a,(hl)                 ; lines in this group
                inc  hl
                or   a
                jp   z,SPAN_DONE            ; 0 ends the frame
                ld   (SPAN_NL),a
                ld   a,(hl)                 ; bytes a line, as STORED
                inc  hl
                ld   (CX_STORED),a
                add  a,a
                ld   (SPAN_STRIDE),a        ; ... as mask/data pairs, which
                                            ; is what both walks step by

                ; ---- THE DELTA MOVES THE ADDRESS AND THE COLUMN -----
                ; The deltas are cumulative, so accumulating the low
                ; byte onto the box's own column gives this group's
                ; span AS A SCREEN COLUMN, which is the one number the
                ; clip needs and the one the address cannot give back:
                ; DE is a ring address and "off the right edge" and
                ; "the next character row" are the same place in it.
                ; Eight bits is the whole of it - a skip is 0..11.
                ld   a,(hl)
                inc  hl
                ld   (CX_DSK + 1),a
                add  a,e
                ld   e,a
                ld   a,(hl)
                inc  hl
                adc  a,d
                xor  d                      ; only the three offset bits
                and  7                      ; of D may move: the raster and
                xor  d                      ; the page come back unchanged
                ld   d,a
                ld   a,(CX_COL)
CX_DSK:         add  a,0
                ld   (CX_COL),a

                ld   a,(SPAN_SKIP)
                or   a
                jp   nz,CX_DO_SKIP

CX_BUDGET:      ld   a,(SPAN_NL)            ; SPAN_CLIP_N's ten instructions
                exx                         ; again, and duplicated on
                cp   c                      ; purpose: a CALL into the fast
                jr   c,.fits                ; lane's copy would charge it 27 T
                ld   a,c                    ; on every group it ever draws,
.fits:          ld   b,a                    ; and there is not an address in
                ld   a,c                    ; here to get wrong
                sub  b
                ld   c,a
                exx

                ld   a,(SPAN_STRIDE)
                ld   (CX_NSTRIDE + 1),a
                ld   a,(CX_STORED)
                or   a
                jp   z,CX_NOTHING           ; a line with nothing on it

                ; ---- HOW MUCH OF THIS SPAN IS ON THE DISPLAY --------
                ld   a,(CX_COL)
                cp   SCR_CHARS * 2
                jr   nc,CX_OFF_LEFT         ; 80..255, which is off the right
                                            ; edge OR negative - the negatives
                                            ; are 244..255 and this one test
                                            ; sends both the right way
                xor  a
                ld   (CX_DROP),a
                ld   a,(CX_COL)
                cpl
                add  a,SCR_CHARS * 2 + 1    ; room to the edge, 1..80
                ld   (.room + 1),a
                ld   (CX_DRAWN),a           ; assume the edge binds
                ld   a,(CX_STORED)
.room:          cp   0
                jr   nc,CX_READY            ; stored >= room: it does
                ld   (CX_DRAWN),a           ; ... otherwise the span does
                jr   CX_READY

CX_OFF_LEFT:    cp   128
                jp   c,CX_NOTHING           ; 80..127: entirely off the right
                neg                         ; 1..12 bytes off the left
                ld   (CX_DROP),a
                ld   (.d + 1),a
                ld   a,(CX_STORED)
.d:             sub  0
                jp   z,CX_NOTHING           ; the whole span is off
                jp   c,CX_NOTHING
                ld   (CX_DRAWN),a
                ; A SPAN CLIPPED ON THE LEFT CANNOT ALSO BE CLIPPED ON
                ; THE RIGHT, so this is the end of the arithmetic: it
                ; starts at column 0 now and the widest the format
                ; carries is SPAN_MAX_WIDTH against a screen of 80.
                ; main.asm asserts it, where SCR_CHARS is in scope.

CX_READY:       ; ---- into the span, by the bytes that fall off -----
                ld   a,(CX_DROP)
                ld   (CX_UNDROPE + 1),a     ; the group's LAST line hands
                add  a,a                    ; both of these back - see there
                ld   (CX_UNDROP + 1),a
                or   a
                jr   z,.placed
                ld   (.h + 1),a
                ld   a,l
.h:             add  a,0
                ld   l,a
                jr   nc,.hok
                inc  h
.hok:           ld   a,(CX_DROP)
                add  a,e                    ; ... and the same ring-safe add
                ld   e,a                    ; the delta above makes
                ld   a,0
                adc  a,d
                xor  d
                and  7
                xor  d
                ld   d,a

                ; ---- the two numbers every line of this group uses --
                ; THE FRAME POINTER OWES THE SAME AMOUNT ON EVERY LINE,
                ; and it is one number rather than two: after the run
                ; it is short by the bytes this line stored and did not
                ; draw, and the NEXT line needs it moved on by the drop
                ; again - which add up to 2 * (stored - drawn) whether
                ; the clip was on the left, on the right, or both.
.placed:        ld   a,(CX_DRAWN)
                ld   (.sub + 1),a
                neg
                ld   (CX_STEP + 1),a        ; the screen's own step, &0800
                ld   (CX_STEPW + 1),a       ; less what the run walked
                ld   a,(CX_STORED)
.sub:           sub  0
                add  a,a
                ld   (CX_TAIL + 1),a

                ; THE LOCAL LABELS IN HERE ARE GLOBAL ONES, because
                ; the patched immediates in the middle of the block are
                ; labels too: a `.wide` written after CX_STEP belongs to
                ; CX_STEP and not to the jump that wanted it.
CX_LINES:       ld   a,(CX_DRAWN)
                call CX_RUN                 ; one line, in one run or two
                jr   c,CX_WIDE              ; it folded: the step owes &0800
                ld   a,e
CX_STEP:        add  a,0
                ld   e,a
                ld   a,d
                adc  a,7
                ld   d,a
                jr   CX_ROW
CX_WIDE:        ld   a,e
CX_STEPW:       add  a,0
                ld   e,a
                ld   a,d
                adc  a,&0F                  ; +&1000 - drawn, for the reason
                ld   d,a                    ; SPAN_MAYBE_FOLD gives
CX_ROW:         jr   nc,CX_SAME
                call SPR_ROW_FIX
CX_SAME:        ld   a,l                    ; ... and AFTER the step, which
CX_TAIL:        add  a,0                    ; reads the carry the run left
                ld   l,a
                jr   nc,CX_HOK
                inc  h
CX_HOK:         exx
                dec  b
                exx
                jp   nz,CX_LINES

                ; THE GROUP'S LAST LINE LEAVES THE FRAME POINTER ONE
                ; DROP TOO FAR, and this is the whole of what an X clip
                ; costs beyond the arithmetic. CX_TAIL moves it to the
                ; next LINE's span and then past the bytes that fall
                ; off the left of THAT - which is what every line but
                ; the last one wants. The next GROUP's header is 2 *
                ; drop before that.
                ;
                ; Read from the wrong place it is a header of 255 lines
                ; and 255 bytes, and what that looks like is measured:
                ; one group of one byte, and then a run of 168 at
                ; column 17 of a screen 80 wide.
                ; AND THE ADDRESS OWES THE SAME DROP, which is the
                ; half that does not show as a crash. The next group's
                ; delta is measured from the span this one did NOT
                ; draw, so a drop left in DE is added to the next
                ; drop and the next: at six bytes off the left edge
                ; the runs marched from column 0 to column 51 of an
                ; 80-column screen, one group at a time, with the line
                ; count and the run count both perfectly right.
                ld   a,e
CX_UNDROPE:     sub  0                      ; the drop
                ld   e,a
                ld   a,d
                sbc  a,0
                xor  d                      ; ring-safe, like every other
                and  7                      ; move this lane makes
                xor  d
                ld   d,a
                ld   a,l
CX_UNDROP:      sub  0                      ; 2 * drop, and SUB rather than
                ld   l,a                    ; ADD of its negative because a
                jr   nc,CX_NEXT             ; drop of 0 has to be a no-op and
                dec  h                      ; ADD 0 never carries
                jp   CX_NEXT                ; ... AND NOT A FALL-THROUGH: the
                                            ; block below is CX_NOTHING, so
                                            ; without this a group whose
                                            ; borrow fired walked itself a
                                            ; second time as a blank one.
                                            ; Data-dependent, which is why
                                            ; it showed as 1.3% of bytes

; ---------------------------------------------------------------------
; Nothing of this group is drawn - its span is entirely off one edge,
; or it is one of the blank lines the exporter keeps because the gap
; between her arm and her boot is one byte. The address walks and the
; data is stepped over; no run goes into the script, because a run of
; zero bytes is an LDIR of 65,536.
; ---------------------------------------------------------------------
CX_NOTHING:     ld   a,l
CX_NSTRIDE:     add  a,0
                ld   l,a
                jr   nc,.hok
                inc  h
.hok:           ld   a,d
                add  a,8
                ld   d,a
                jr   nc,.same_row
                call SPR_ROW_FIX
.same_row:      exx
                dec  b
                exx
                jp   nz,CX_NOTHING

CX_NEXT:        exx                         ; any of the sprite left?
                ld   a,c
                exx
                or   a
                jp   nz,CX_GROUP
                jp   SPAN_DONE

; ---------------------------------------------------------------------
; This group starts above the top of the display, whole or in part.
; Its pixel data is walked past; the ADDRESS is not stepped, because DE
; was computed for the first line that is actually drawn.
; ---------------------------------------------------------------------
CX_DO_SKIP:     ld   (.sk + 1),a            ; the lines still to skip. NOT in
                                            ; B: B is the script pointer's
                                            ; high byte (CLAUDE.md 10)
                ld   a,(SPAN_NL)
                ld   (.nl + 1),a
                ld   a,(SPAN_SKIP)
.nl:            cp   0
                jr   nc,.whole
                ld   (.n + 1),a             ; part of the group survives
                ld   (.sub + 1),a
                xor  a
                ld   (SPAN_SKIP),a
                ld   a,(SPAN_NL)
.sub:           sub  0
                ld   (SPAN_NL),a
                call .walk
                jp   CX_BUDGET
.whole:         ld   a,(SPAN_NL)
                ld   (.n + 1),a
                neg
.sk:            add  a,0
                ld   (SPAN_SKIP),a
                call .walk
                jp   CX_GROUP

.walk:          ld   a,(SPAN_STRIDE)        ; HL += n * stride
                or   a
                ret  z                      ; blank lines carry no data
                ld   (.step + 1),a
.loop:          ld   a,l
.step:          add  a,0
                ld   l,a
                jr   nc,.nc
                inc  h
.nc:
.n:             ld   a,0
                dec  a
                ld   (.n + 1),a
                jr   nz,.loop
                ret

; ---------------------------------------------------------------------
; CX_RUN - one line's bytes, as one run or as two across the 2 KB fold.
;
; IN : A = bytes to draw, 1..SPAN_MAX_WIDTH; DE screen, BC script,
;      HL the mask/data pairs
; OUT: carry SET if the line folded, so the caller's step owes an extra
;      &0800; DE one past the last byte written, folded back
;      destroys AF
;
; THIS IS SPAN_MAYBE_FOLD'S ARITHMETIC A SECOND TIME and it is the one
; thing in this file worth being afraid of - see the header. The cheap
; test is first for the same reason it is there: the offset can only
; reach the end of the block from within SPAN_MAX_WIDTH of it.
; ---------------------------------------------------------------------
CX_RUN:         ld   (CX_N1),a
                ld   a,e
                cp   256 - SPAN_MAX_WIDTH
                jr   c,.whole
                ld   a,d
                and  7
                cp   7
                jr   nz,.whole              ; a plain 256-byte crossing
                ld   a,e
                neg                         ; bytes left in the block, 1..12
                ld   (.split + 1),a
                ld   (CX_N2),a
                ld   a,(CX_N1)
.split:         sub  0
                jr   c,.whole               ; stops short of the wrap
                ; ZERO IS NOT THE SAFE CASE: a run ending EXACTLY on the
                ; block's last byte wraps no word, but the last INC DE
                ; leaves DE at offset 0 of the next raster and the step
                ; then does not carry. It takes this lane too, with an
                ; empty second half.
                ld   (CX_N1),a
                ld   a,(CX_N2)
                call SPAN_SLOW              ; the bytes before the wrap
                ld   a,d
                sub  8                      ; fold back to offset 0 of THIS
                ld   d,a                    ; raster
                ld   a,(CX_N1)
                or   a
                call nz,SPAN_SLOW
                scf
                ret
.whole:         ld   a,(CX_N1)
                call SPAN_SLOW
                or   a
                ret

SPAN_X:         db 0            ; the box's screen column, SIGNED
CX_COL:         db 0            ; ... and the current group's span
CX_STORED:      db 0            ; bytes a line the frame holds
CX_DRAWN:       db 0            ; ... and how many of them show
CX_DROP:        db 0            ; bytes off the LEFT edge
CX_N1:          db 0            ; CX_RUN's two halves
CX_N2:          db 0

SPAN_SKIP:      db 0            ; lines still to drop off the top
SPAN_NL:        db 0            ; this group's line count
SPAN_STRIDE:    db 0            ; ... and its bytes a line
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
SPAN_ERASE_AT:  ; ... or from HL, for a second sprite's own script
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
