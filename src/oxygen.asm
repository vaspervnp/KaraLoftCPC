; =====================================================================
; oxygen.asm - her air, in the water. CLAUDE.md 8.18.
;
; IN THE TOP IMAGE WITH THE REST OF THE SWIMMER, because nothing here
; runs out of the water. It was in the core while the core had room, and
; the spike traps' paint - the early pass before the strip and the cell
; test in characters (src/hazard.asm) - took the core to &4000 exactly.
; 188 bytes; the TOP image has twelve left after it (src/main.asm).
; Base RAM is base RAM - where a routine lives says nothing about how
; often it runs.
;
; HER AIR. She holds a breath of OXY_MAX and spends a unit every
; OXY_RATE game frames; the surface and a vent's column of bubbles give
; it back, OXY_GULP a frame, and an oxygen tank (PU_OXYGEN) fills it.
; Out of air, the water takes DROWN_HURT of her health every DROWN_RATE
; frames until she breathes or dies.
;
;   99 units at a unit every 7 game frames is 693 frames - 27.7 s of a
;   level that is 1,024 lines deep and swum at 2 lines a frame, so a
;   straight dive is 20 s and anything else needs air on the way.
;
; WHERE THE AIR IS, IS THE LEVEL'S AND NOT THE ENGINE'S: a REGION of
; kind OxygenVent (docs/editor.md 5.5, the format's region section).
; Nothing read the region section until now - every level shipped with
; none - and it is read the way the links are (src/hazard_high.asm), out
; of the pristine level image at LEVEL_IMAGE, which nothing in play
; writes. The surface is a region like any other, so a level that wants
; her to drown at the top can say so.
;
; THE HUD SHOWS IT AS A DIGIT, in the coins' slot (BOX_WORDS above):
; OXY_DIGIT is OXYGEN / 11, nine for a full breath and nought for the
; last eleven units - and the icon goes dark at nought, the convention
; every slot on the strip already keeps for a thing she has run out of.
; =====================================================================
OXY_MAX         equ 99
OXY_RATE        equ 7           ; game frames a unit
OXY_GULP        equ 4           ; units a game frame, breathing
OXY_PER_DIGIT   equ 11          ; 99 / 11 = 9, the HUD's widest digit
DROWN_RATE      equ 25          ; a game frame is 40 ms: a bite a second
DROWN_HURT      equ EBUL_DAMAGE ; ... and the size of a drone's round
RG_OXYGEN       equ 2           ; docs/editor.md 5.5's OxygenVent
RG_STRIDE       equ 7           ; kind, x u16, y u16, w, h - in TILES
OXY_FULL        equ OXY_MAX     ; OXYGEN and OXY_T as one word: a full
                                ; breath and a fresh count

OXY_STEP:       call OXY_IN_AIR
                jr   z,.hold
                ld   a,(OXYGEN)
                add  a,OXY_GULP
                cp   OXY_MAX + 1
                jr   c,.breathe
                ld   a,OXY_MAX
.breathe:       ld   (OXYGEN),a
                xor  a
                ld   (OXY_T),a
                jr   .digit
.hold:          ld   hl,OXY_T
                inc  (hl)
                ld   a,(OXYGEN)
                or   a
                jr   z,.drown
                ld   a,(hl)
                cp   OXY_RATE
                ret  c
                ld   (hl),0
                ld   hl,OXYGEN
                dec  (hl)
                jr   .digit
.drown:         ld   a,(hl)
                cp   DROWN_RATE
                ret  c
                ld   (hl),0
                ld   a,(PLAYER_HP)
                sub  DROWN_HURT
                jr   nc,.hp
                xor  a
.hp:            ld   (PLAYER_HP),a
                ld   a,HURT_FRAMES          ; the border, the way every
                ld   (HURT_FLASH),a         ; other hurt does
                ret
.digit:         ld   a,(OXYGEN)             ; / 11, by subtraction: nine
                ld   b,-1                   ; at most
.div:           inc  b
                sub  OXY_PER_DIGIT
                jr   nc,.div
                ld   a,b
                ld   (OXY_DIGIT),a
                ret

; ---------------------------------------------------------------------
; OXY_IN_AIR - NZ if the middle of her box is inside a region of air.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
OXY_IN_AIR:     ld   a,(LEVEL_LVL + LVL_REGIONS)
                or   a
                ret  z                      ; a level with no air at all
                ld   b,a
                push ix
                ld   hl,(LEVEL_LVL + LVL_OFF_REGION)
                ld   de,LEVEL_LVL
                add  hl,de
                push hl
                pop  ix                     ; the first region
                ld   hl,(KARA_WX)
                ld   de,SWIM_BOX_W / 2
                add  hl,de
                srl  h                      ; bytes -> tiles, four a tile
                rr   l
                srl  h
                rr   l
                ld   c,l                    ; C = her middle's column
                ld   hl,(KARA_WY)
                ld   de,SWIM_BOX_H / 2
                add  hl,de
                ld   a,l                    ; lines -> rows, sixteen a row
                srl  h
                rra
                srl  h
                rra
                srl  h
                rra
                srl  h
                rra
                ld   l,a                    ; L = her middle's row
.reg:           ld   a,(ix + 0)
                cp   RG_OXYGEN
                jr   nz,.next
                ld   a,c
                sub  (ix + 1)
                jr   c,.next                ; left of it
                cp   (ix + 5)
                jr   nc,.next               ; right of it
                ld   a,l
                sub  (ix + 3)
                jr   c,.next                ; above it
                cp   (ix + 6)
                jr   nc,.next               ; below it
                pop  ix
                or   1                      ; NZ: she is breathing
                ret
.next:          ld   de,RG_STRIDE
                add  ix,de
                djnz .reg
                pop  ix
                xor  a                      ; Z: she is not
                ret

OXYGEN:         db OXY_MAX      ; her breath - and OXY_T straight after it,
OXY_T:          db 0            ; so BOX_SET fills both with one word
OXY_DIGIT:      db OXY_MAX / OXY_PER_DIGIT  ; what the HUD's slot shows
