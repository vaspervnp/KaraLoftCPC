; =====================================================================
; melee.asm - the enemies that BITE: the cave's bats and the forest's
; wolf and boar (CLAUDE.md 8.24). In the TOP image, because the core had
; 65 bytes and this is the logic of three characters, not the frame's.
;
; THEY ARE THE ENGAGED DRONE WITH TWO THINGS CHANGED, and each is a bit
; of the type row's EN_T_KIND, so the drone and the sea drone - kind 0 -
; are the engine they were:
;
;   EN_MELEE    its "shot" is a CHARGE. Where ENEMY_FIRE would put a
;               round in the air it starts ES_CHARGE instead, and while
;               that counts down the follow makes for the place beside
;               her rather than EN_DIST from her, and a box that reaches
;               hers is a bite of EN_T_BITE, once, which ends the charge.
;   EN_GROUND   it keeps to the line it was put on: the follow does not
;               climb or sink. A wolf does not come up a branch after
;               her, and a jump is how she lets a charge go under her.
;
; THE CHARGE STOPS A BYTE SHORT OF HER SPRITE, AND THAT IS THE FRAME'S
; RULE. A box that meets the one she was DRAWN in is a refresh at the
; end of the second sweep (ENEMY_SLOT), which has no deadline (8.7); a
; box a byte away is one at the top of it, in time the sweep always had.
; Her drawn box is her SPRITE's, twelve bytes, and not her body's six -
; the first version stopped a byte from her body, two inside her sprite,
; and every charge was a frame of 86,000 T. AND THE BYTE HAS TO BE
; THREE, because what is tested is her box as drawn THIS frame against
; its box as drawn LAST frame: she walks a byte a frame and runs two,
; and walking into a wolf a byte away was the same frame again. So it
; makes for the place EN_AIR from her sprite, and what bites is its box
; widened by EN_REACH either side - across the air and her art - against
; her body: the bite reaches across the gap and the sprites never meet.
; =====================================================================
EN_MELEE        equ 1           ; EN_T_KIND: it bites instead of shooting
EN_GROUND       equ 2           ; ... and keeps to its own line
EN_CHARGE_N     equ 10          ; game frames a charge lasts at most
EN_AIR          equ 3           ; bytes between its box and her SPRITE's at
                                ; the end of a charge: what a run covers in
                                ; a frame, and one more
EN_REACH        equ EN_AIR + (KARA_W_BYTES - KARA_BOX_W) / 2 + 1
                                ; bytes either side of its box it bites in:
                                ; the air, her art either side of her body,
                                ; and one more - against her BODY's box

; ---------------------------------------------------------------------
; EN_MELEE_FIRE - ENEMY_FIRE's question, its recoil cel already set:
; carry if this one bites, and then its charge has begun and there is
; no round. IX = it.                       destroys AF,DE,HL
; ---------------------------------------------------------------------
EN_MELEE_FIRE:  call EN_KIND
                rrca                        ; EN_MELEE is bit 0: the carry
                ret  nc
                ld   (ix + ES_CHARGE),EN_CHARGE_N   ; (LD keeps the carry)
                ret

; ---------------------------------------------------------------------
; EN_BITE_STEP - a frame of a charge, in the logic: has it reached her?
; Its box widened by EN_REACH either side, against hers as she was drawn
; (EN_MEETS_HER). A bite ends the charge. IX = it.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
EN_BITE_STEP:   ld   a,(ix + ES_CHARGE)
                or   a
                ret  z
                dec  a
                ld   (ix + ES_CHARGE),a
                ld   l,(ix + ES_X)
                ld   h,(ix + ES_X + 1)
                srl  h
                rr   l                      ; its left edge, world bytes
                ld   de,0 - EN_REACH
                add  hl,de                  ; ... and the reach outside it
                ld   e,(ix + ES_Y)
                ld   d,(ix + ES_Y + 1)
                ld   a,(ENEMY_W)
                add  a,EN_REACH * 2
                ld   b,a
                ld   a,(ENEMY_H)
                ld   c,a
                call EN_MEETS_HER
                ret  nc
                ld   (ix + ES_CHARGE),0     ; one bite a charge
                ld   hl,(ENEMY_TYP)
                ld   de,EN_T_BITE
                add  hl,de
                ld   a,(hl)
                jp   HURT_HER

; ---------------------------------------------------------------------
; EN_CHARGE_TGT - ENEMY_FOLLOW's first question: is this one charging?
; If it is, it makes for the place beside her on its own side with
; EN_AIR between the boxes - inside the view's wall - straight
; there at EN_CHASE and never PAST it, and the follow goes on at its
; wall and its height (carry). IX = it, EN_HERMID = her middle. Beside
; her SPRITE, EN_AIR of air: see the top of the file.
;
; NOT THROUGH THE FOLLOW'S OWN DRIFT, which wanders EN_SWAY either side
; of its target: four bytes of wander round a place a byte from her is
; three bytes inside her, and two boxes that meet are a refresh at the
; end of the sweep (8.7), which is what EN_AIR is for.
;
; Her half-width is the LAND sprite's: no melee character is placed
; under water, where she is the 32-byte swimmer (src/swim.asm).
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
EN_CHARGE_TGT:  ld   a,(ix + ES_CHARGE)
                or   a
                ret  z                      ; no carry: the follow's own way
                call EN_HALF_W              ; DE = half its width
                ld   hl,KARA_W_BYTES / 2 + EN_AIR
                add  hl,de
                ex   de,hl                  ; DE = middle to middle, EN_AIR apart
                ld   hl,(EN_HERMID)
                ld   a,(ENEMY_SIDE)
                or   a                      ; (and no carry for the SBC)
                jr   nz,.left
                add  hl,de
                jr   .mid
.left:          sbc  hl,de
.mid:           call EN_HALF_W
                or   a
                sbc  hl,de                  ; ... as its box's left edge
                call EN_CLAMP_X
                add  hl,hl                  ; ... in world pixels
                ld   (EN_TGT),hl
                call EN_FROM_TGT            ; HL = how far, A = which way
                ld   (ix + ES_DIR),a
                ld   a,h
                or   a
                jr   nz,.far
                ld   a,l
                cp   EN_CHASE
                jr   c,.step                ; nearer than a stride: the rest
.far:           ld   a,EN_CHASE
.step:          ld   c,a
                call EN_STEP
                scf
                ret

; ---------------------------------------------------------------------
; EN_SIGHT_Y - ENEMY_SEES's "roughly level with it": the line her TOP
; is compared with. For a drone that is its own top, which the follow
; keeps EN_DY below hers. FOR A BEAST ON THE GROUND IT IS WHERE HER TOP
; WOULD BE STANDING ON ITS LINE - its feet less her height - because a
; 24-line wolf and a 64-line heroine on one floor have tops exactly
; EN_H_SIGHT apart, and the first wolf placed never saw her at all.
; Low byte only: ENEMY_SEES wants a small modular difference (8.7).
;                                destroys AF,DE,HL
; ---------------------------------------------------------------------
EN_SIGHT_Y:     call EN_KIND
                and  EN_GROUND
                ld   a,(ix + ES_Y)          ; (LD keeps the Z of the AND)
                ret  z
                ld   hl,ENEMY_H
                add  a,(hl)                 ; its feet ...
                sub  KARA_BOX_H             ; ... less her height
                ret

; ---------------------------------------------------------------------
; EN_HIT_BAND - the screen lines her rounds hit the current one in, for
; ENEMY_SHOT_CHECK: its own box, and for a beast on the GROUND the
; EN_LOW_REACH lines above it as well.
;
; THAT IS A COMPROMISE AND IT IS WRITTEN DOWN AS ONE. Her muzzle is
; lines 11 and 17 of her 64-line box (KCORE_SPAWNS) - 91 and 97 standing
; on the forest's ground - and a 24-line wolf on that ground is lines
; 120 to 143, so every round she fires goes over its back. Nothing in
; the art fires lower: she stands up to aim (8.4), there is no crouching
; shot, and DOWN with the trigger is the manual reload. So a round that
; crosses a beast's column within 32 lines of its back is a hit. On the
; screen it is a round that stops over the wolf as it flashes.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
EN_LOW_REACH    equ 32

EN_HIT_BAND:    ld   a,(ENEMY_SY)
                ld   (EN_HIT_Y),a
                ld   a,(ENEMY_H)
                ld   (EN_HIT_H),a
                call EN_KIND
                and  EN_GROUND
                ret  z
                ld   hl,EN_HIT_Y
                ld   a,(hl)
                sub  EN_LOW_REACH
                jr   nc,.top
                xor  a                      ; no higher than the screen's top
.top:           ld   b,a
                ld   a,(hl)
                sub  b                      ; how far up the band went
                ld   (hl),b
                ld   hl,EN_HIT_H
                add  a,(hl)
                ld   (hl),a
                ret

EN_HIT_Y:       db 0
EN_HIT_H:       db 0
