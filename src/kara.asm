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

; ---------------------------------------------------------------------
; HER FRAMES ARE IN TWO BLOBS AND THREE BANKS, and which one a cel comes
; from is part of the animation, not of the drawing. idle, walk, jump
; and the gun are `kcore`, one bank a facing; run and roll are `kextra`,
; both facings in one bank because the pair fits. So the drawer is told
; a SET and a frame, and looks the bank and the blob's base up here.
;
; The addresses come from build/levels/banks.inc, which the ALLOCATOR
; emits after checking that every level put them in the same place -
; tools/level_banks.py PINNED. A pin that stopped holding fails the
; build there rather than drawing garbage here.
; ---------------------------------------------------------------------
KSET_CORE       equ 0                       ; idle, walk, jump, shoot
KSET_EXTRA      equ 1                       ; run, roll
KSET_ACT        equ 2                       ; hang, use, hurt, climb_turn, climb
KSET_BYTES      equ 8
KSET_TWO_FACED  equ 255                     ; ... every frame of this set is

; AND THE FIRST BYTE OF A ROW IS WHERE THE SECOND FACING STOPS. `climb`
; is drawn from BEHIND - she is on a ladder with her back to the player
; - so it has no left and no right: mirrored, her holster and her braid
; swap sides of a figure that is otherwise symmetric. It is stored once,
; at the END of the right-facing blob, and the left-facing blob simply
; stops before it (tools/build_levels.py). Every cel that DOES have two
; facings is therefore at the same index in both, which is what lets
; KARA_ANIMS name one frame number for both and the duration table be
; the right-facing blob's.
;
; So a frame at or past this number is drawn out of the right-facing
; blob whichever way she is facing, and the test costs 18 T against a
; second frame table, a second duration table and 2,714 bytes of a bank
; level 5 has not got.
KARA_SETS:      db KSET_TWO_FACED
                db KCORE_PIN_BANK           ; facing right
                dw KCORE_PIN_ADDR
                db KCORE_L_PIN_BANK         ; facing left
                dw KCORE_L_PIN_ADDR
                db 0                        ; pad: * 8 is three ADDs

                db KSET_TWO_FACED
                db KEXTRA_PIN_BANK
                dw KEXTRA_PIN_ADDR
                db KEXTRA_L_PIN_BANK
                dw KEXTRA_L_PIN_ADDR
                db 0

                ; `kact` IS NOT PINNED, and this is the one set addressed
                ; by its LEVEL. tools/level_banks.py pins kcore, kextra
                ; and kswim because every level needs them in the same
                ; place; the action blob is allocated per level, and
                ; level 1 is the only one this demo loads. Module 6's
                ; level reader turns these two rows into a table the
                ; transition fills in - see CLAUDE.md 11.
                db KACT_TWO_FACED           ; ... and from here she has one
                db L1_KACT_BANK
                dw L1_KACT_ADDR
                db L1_KACT_L_BANK
                dw L1_KACT_L_ADDR
                db 0

; ---------------------------------------------------------------------
; KARA_SPAN_DRAW - composite her, clipped to the display.
;
; IN : (KARA_X) screen byte column of her box's left edge
;      (KARA_Y) screen line of her box's top, 192-255 meaning above it
;      (KARA_SET) which blob, (KARA_FRAME) the frame inside it,
;      (KARA_FACING) 0 right, 1 left
; OUT: (KARA_LAST_TOP) the first line she was drawn on and
;      (KARA_LAST_BOT) the last, for the erase's raster gate, and
;      (KARA_LAST_CNT) how many lines went down - 0 when she is entirely
;      off the display, which is the loop's cue not to wait for a beam
;      that has nothing to pass. The script is ALWAYS written, even
;      then, because a stale one would make the erase put old bytes
;      back over a screen that has moved on.
;      destroys AF,BC,DE,HL,B',C'
; ---------------------------------------------------------------------
KARA_SPAN_DRAW: ld   a,(KARA_SET)           ; which blob this cel is in
                add  a,a
                add  a,a
                add  a,a                    ; * KSET_BYTES
                ld   l,a
                ld   h,0
                ld   de,KARA_SETS
                add  hl,de
                ld   a,(KARA_FRAME)
                cp   (hl)                   ; past the second facing's last?
                inc  hl
                jr   nc,.face               ; a back view: right blob, always
                ld   a,(KARA_FACING)
                or   a
                jr   z,.face
                inc  hl                     ; the left entry is three bytes on
                inc  hl
                inc  hl
.face:          ld   c,(hl)                 ; its bank ...
                inc  hl
                ld   e,(hl)
                inc  hl
                ld   d,(hl)                 ; ... and the blob's base
                ld   b,&7F
                out  (c),c

                ; ---- the frame's record, from the table at the base --
                ld   a,(KARA_FRAME)
                add  a,a
                ld   l,a
                ld   h,0
                add  hl,de
                ld   a,(hl)                 ; the offset is relative, so a
                inc  hl                     ; blob can be loaded anywhere
                ld   h,(hl)
                ld   l,a
                add  hl,de

                ; ---- how much of her is on the display ---------------
                ld   a,(KARA_Y)
                call SPAN_CLIP_V            ; -> HL groups, A top, C lines
                ld   (KARA_LAST_TOP),a
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
