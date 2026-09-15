; =====================================================================
; kara.asm - the heroine, drawn from her span blobs           (MODULE 5)
;
; This replaces the 16x48 full-box path in sprite.asm. She is 24x64 now
; and stored as spans in a bank (7.1), one blob per facing, so drawing
; her is: page the bank, find the frame, work out how much of her is on
; the display, and hand the rest to SPAN_DRAW.
;
; THE BANKS ARE A CONTRACT, not a lookup. tools/level_banks.py pins
; kcore to &C5 and kcore_l to &C6 in every level, each at the start of
; its bank, so the facing is one OUT and the blob base is a constant.
; The tilemap owns &C4 for the same reason, which is what lets the
; scrolling demo drop the placeholder tileset over the top of whatever
; the level loader put there.
;
; The erase needs no bank at all - SPAN_ERASE works from the script the
; draw left in base RAM.
; =====================================================================

KARA_W_BYTES    equ KCORE_BOX_W             ; 12 - 24 pixels
KARA_H          equ KCORE_BOX_H             ; 64 lines
KARA_BANK_R     equ &C5
KARA_BANK_L     equ &C6
KARA_BLOB       equ BANK_WINDOW             ; &4000, both facings

; ---------------------------------------------------------------------
; KARA_SPAN_DRAW - composite her, clipped to the display.
;
; IN : (KARA_X) screen byte column of her box's left edge
;      (KARA_Y) screen line of her box's top, 192-255 meaning above it
;      (KARA_FRAME) frame in the blob, (KARA_FACING) 0 right, 1 left
; OUT: (KARA_LAST_TOP) the first line she was drawn on and
;      (KARA_LAST_BOT) the last, for the erase's raster gate, and
;      (KARA_LAST_CNT) how many lines went down - 0 when she is entirely
;      off the display, which is the loop's cue not to wait for a beam
;      that has nothing to pass. The script is ALWAYS written, even
;      then, because a stale one would make the erase put old bytes
;      back over a screen that has moved on.
;      destroys AF,BC,DE,HL,B',C'
; ---------------------------------------------------------------------
KARA_SPAN_DRAW: ld   a,(KARA_FACING)
                or   a
                ld   a,KARA_BANK_R
                jr   z,.bank
                ld   a,KARA_BANK_L
.bank:          ld   c,a
                ld   b,&7F
                out  (c),c

                ; ---- the frame's record, from the table at the base --
                ld   a,(KARA_FRAME)
                add  a,a
                ld   l,a
                ld   h,0
                ld   de,KARA_BLOB
                add  hl,de
                ld   a,(hl)                 ; the offset is relative, so a
                inc  hl                     ; blob can be loaded anywhere
                ld   h,(hl)
                ld   l,a
                add  hl,de

                ld   a,(hl)                 ; y0 - the first line of the box
                inc  hl                     ; with anything on it
                ld   e,(hl)                 ; lines stored
                inc  hl                     ; ... and HL is now the groups

                ; ---- how much of her is on the display ---------------
                ld   d,a
                ld   a,(KARA_Y)
                add  a,d                    ; screen line of her first
                ld   d,a                    ; stored line
                xor  a
                ld   (SPAN_SKIP),a

                ld   a,d
                cp   SCR_LINES
                jr   nc,.above              ; 192-255: above the top edge

                ; her top is on the display; how many lines fit below it
                ld   a,SCR_LINES
                sub  d
                cp   e
                jr   c,.clipped             ; the bottom runs off
                ld   a,e
.clipped:       ld   c,a                    ; lines to draw
                ld   a,d
                jr   .draw

.above:         neg                         ; 256 - top = lines above line 0
                cp   e
                jr   nc,.culled             ; more than she has: nothing shows
                ld   (SPAN_SKIP),a
                ld   c,a
                ld   a,e
                sub  c                      ; what is left below line 0
                ld   c,a
                xor  a                      ; ... drawn from the top line
                jr   .draw

.culled:        xor  a
                ld   (SPAN_SKIP),a
                ld   c,a                    ; nothing to draw, but the script
                                            ; still has to be terminated

.draw:          ld   (KARA_LAST_TOP),a
                push hl                     ; SCR_ADDR RETURNS in HL, so the
                push bc                     ; frame pointer has to go on the
                                            ; stack - it is not a scratch
                                            ; register here, it is the sprite
                ld   h,a                    ; H = her first drawn line, now
                ld   a,c                    ; that the frame is saved
                ld   (KARA_LAST_CNT),a
                or   a
                jr   z,.nobot               ; culled: BOT = TOP, and the loop
                dec  a                      ; reads CNT and waits for neither
.nobot:         add  a,h
                ld   (KARA_LAST_BOT),a      ; the last line the beam must pass
                ld   a,(KARA_X)
                ld   c,a                    ; C = byte column, preserved
                ld   a,h                    ; A = the screen line
                call SCR_ADDR
                ex   de,hl                  ; DE = screen
                pop  bc                     ; C = lines to draw
                pop  hl                     ; HL = the frame's groups
                ld   a,c
                ld   bc,SPAN_SCRIPT
                call SPAN_DRAW
                jp   BANK_RESTORE

; ---------------------------------------------------------------------
; KARA_SPAN_ERASE - put back what she was drawn over.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
KARA_SPAN_ERASE:
                jp   SPAN_ERASE
