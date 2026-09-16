; =====================================================================
; action.asm - what Kara is DOING, and which cel shows it   (MODULE 5)
;
; CLAUDE.md 8.4 is the specification and it is a table, so this is a
; table: seven states, each naming a blob, a run of frames inside it and
; whether that run loops or stops on its last cel.
;
;   IDLE  no direction, on the ground          idle,       loops
;   WALK  left or right on the ground          walk,       loops
;   RUN   SHIFT and a direction                run,        loops
;   JUMP  off the ground, however she got off  jump,       holds
;   ROLL  Z, on the ground                     roll,       runs out
;   AIM   SPACE held                           shoot_draw, holds
;   FIRE  SPACE released from AIM              shoot,      runs out
;
; TWO OF THEM ARE COMMITTED. A roll runs its frames whatever the input
; does - that is what makes it a dodge rather than a nudge - and so does
; the shot, which is what stops a tapped trigger from playing one frame
; of a four-frame recoil. Everything else is re-decided every frame, so
; the input can change her mind mid-cel and usually should.
;
; THE CEL RATE COMES FROM THE ART. Every blob ships a Kxxxx_DURATION
; table - how many 50 Hz frames Aseprite held each cel for - and nine
; frames of the drawn sheet are not shipped at all, with each dropped
; cel's time added to the one before it (CLAUDE.md 7.1). Running the
; animation at a fixed rate instead would make the thinned walk cycle
; faster than the artist drew it and out of step with the two bytes a
; frame she travels.
; =====================================================================

KST_IDLE        equ 0
KST_WALK        equ 1
KST_RUN         equ 2
KST_JUMP        equ 3
KST_ROLL        equ 4
KST_AIM         equ 5
KST_FIRE        equ 6
KST_COUNT       equ 7
KST_BYTES       equ 4

; set, first frame in that blob, cels, loops?
KARA_ANIMS:     db KSET_CORE,  KCORE_IDLE_FIRST,       KCORE_IDLE_COUNT,       1
                db KSET_CORE,  KCORE_WALK_FIRST,       KCORE_WALK_COUNT,       1
                db KSET_EXTRA, KEXTRA_RUN_FIRST,       KEXTRA_RUN_COUNT,       1
                db KSET_CORE,  KCORE_JUMP_FIRST,       KCORE_JUMP_COUNT,       0
                db KSET_EXTRA, KEXTRA_ROLL_FIRST,      KEXTRA_ROLL_COUNT,      0
                db KSET_CORE,  KCORE_SHOOT_DRAW_FIRST, KCORE_SHOOT_DRAW_COUNT, 0
                db KSET_CORE,  KCORE_SHOOT_FIRST,      KCORE_SHOOT_COUNT,      0

; One duration table per SET, indexed by the frame's number in its blob.
KARA_DURATIONS: dw KCORE_DURATION
                dw KEXTRA_DURATION

; ---------------------------------------------------------------------
; ACT_ROW - HL = the KARA_ANIMS row for state A.    destroys AF,DE,HL
; ---------------------------------------------------------------------
ACT_ROW:        add  a,a
                add  a,a                    ; * KST_BYTES
                ld   l,a
                ld   h,0
                ld   de,KARA_ANIMS
                add  hl,de
                ret

; ---------------------------------------------------------------------
; ACT_UPDATE - pick the state, then age the cel.
;
; Call AFTER PLAYER_UPDATE: the jump test reads KARA_GROUND, which the
; physics has just settled, and a state chosen from last frame's ground
; flag shows her standing for one frame in mid-air.
;
; Reads (INPUT_NOW), (INPUT_PRESSED), (KARA_GROUND).
; Writes (KARA_STATE), (KARA_ANIM), (KARA_TIMER), (KARA_DONE),
;        (KARA_SET), (KARA_FRAME).
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
ACT_UPDATE:     ; ---- is the current state still owed its frames? -----
                ld   a,(KARA_STATE)
                cp   KST_ROLL
                jr   z,.committed
                cp   KST_FIRE
                jr   nz,.choose
.committed:     ld   a,(KARA_DONE)
                or   a
                jp   z,ACT_ANIMATE          ; nothing may interrupt it

                ; ---- off the ground beats everything ----------------
.choose:        ld   a,(KARA_GROUND)
                or   a
                ld   a,KST_JUMP
                jr   z,.want

                ; ---- a roll is DOWN AND A DIRECTION, from the ground -
                ; It was Z. It is the two keys a player's hands are
                ; already on, which is what a dodge wants, and it frees
                ; bit 5 of the input byte that 8.4 called full.
                ;
                ; A PRESS OF EITHER HALF WHILE THE OTHER IS HELD, not
                ; the state of both: a committed 8-cel roll that
                ; re-triggered on the frame it ended would never let go
                ; while the player kept crouching and walking.
                ld   a,(INPUT_NOW)
                ld   c,a
                and  IN_DOWN
                jr   z,.no_roll
                ld   a,c
                and  IN_LEFT + IN_RIGHT
                jr   z,.no_roll
                ld   a,(INPUT_PRESSED)
                and  IN_DOWN + IN_LEFT + IN_RIGHT
                ld   a,KST_ROLL
                jr   nz,.want
.no_roll:

                ; ---- the gun is draw-hold-RELEASE ------------------
                ; SPACE going down plays shoot_draw and holds its last
                ; cel; SPACE coming up plays shoot. That is what the
                ; two-frame shoot_draw tag is for, and it is why the
                ; release is recognised by the state she is LEAVING
                ; rather than by an INPUT_RELEASED byte that would have
                ; to be kept in step with it.
                ld   a,(INPUT_NOW)
                ld   c,a
                and  IN_FIRE
                ld   a,KST_AIM
                jr   nz,.want
                ld   a,(KARA_STATE)
                cp   KST_AIM
                ld   a,KST_FIRE
                jr   z,.want

                ; ---- on her feet: still, walking or running ---------
                ld   a,c
                and  IN_LEFT + IN_RIGHT
                ld   a,KST_IDLE
                jr   z,.want
                ld   a,c
                and  IN_RUN
                ld   a,KST_RUN
                jr   nz,.want
                ld   a,KST_WALK

.want:          ld   hl,KARA_STATE
                cp   (hl)
                jr   z,ACT_ANIMATE          ; unchanged: just age the cel
                ld   (hl),a
                xor  a
                ld   (KARA_DONE),a
                ; A NEW STATE STARTS ONE CEL BEFORE ITS FIRST, because
                ; the line below runs the timer down and steps THIS
                ; frame. Starting it at cel 0 with a timer of 1 skips
                ; cel 0 entirely: idle opened on its second frame, a
                ; four-cel recoil played three, and the loop test caught
                ; it by never coming back round to where it started.
                dec  a                      ; 255 - and INC A wraps it to 0
                ld   (KARA_ANIM),a
                ld   a,1
                ld   (KARA_TIMER),a
                ; falls into ACT_ANIMATE

; ---------------------------------------------------------------------
; ACT_ANIMATE - one frame of the current state's cel timer.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
ACT_ANIMATE:    ld   hl,KARA_TIMER
                dec  (hl)
                jr   nz,ACT_SHOW            ; this cel is still up

                ld   a,(KARA_STATE)
                call ACT_ROW                ; HL -> set, first, count, loop
                inc  hl
                inc  hl
                ld   c,(hl)                 ; C = cels in this state
                inc  hl
                ld   b,(hl)                 ; B = does it loop?
                ld   a,(KARA_ANIM)
                inc  a
                cp   c
                jr   c,.ok                  ; still inside the run
                inc  b
                dec  b
                jr   z,.stop
                xor  a                      ; loops: back to the first cel
                jr   .ok
.stop:          ld   a,c                    ; holds: stay on the last one and
                dec  a                      ; say so, which is what lets a
                ld   b,a                    ; committed state be left
                ld   a,1
                ld   (KARA_DONE),a
                ld   a,b
.ok:            ld   (KARA_ANIM),a

; ---------------------------------------------------------------------
; ACT_SHOW - publish (KARA_SET) and (KARA_FRAME), and reload the timer
; from the art's own duration table when the cel has just changed.
; ---------------------------------------------------------------------
ACT_SHOW:       ld   a,(KARA_STATE)
                call ACT_ROW
                ld   c,(hl)                 ; C = the set
                ld   a,c
                ld   (KARA_SET),a
                inc  hl
                ld   a,(hl)                 ; the state's first frame ...
                ld   hl,KARA_ANIM
                add  a,(hl)                 ; ... plus the cel
                ld   (KARA_FRAME),a

                ld   hl,KARA_TIMER          ; only reload a timer that ran out
                ld   b,(hl)
                inc  b
                dec  b
                ret  nz

                ld   b,a                    ; B = the frame, for the lookup
                ld   a,c
                add  a,a
                ld   l,a
                ld   h,0
                ld   de,KARA_DURATIONS
                add  hl,de
                ld   e,(hl)
                inc  hl
                ld   d,(hl)                 ; DE = this set's duration table
                ld   a,b
                add  a,e
                ld   e,a
                jr   nc,.same
                inc  d
.same:          ld   a,(de)
                or   a
                jr   nz,.got
                inc  a                      ; a zero-length cel would stop the
.got:           ld   (KARA_TIMER),a         ; animation dead
                ; falls into ACT_MUZZLE - a cel has just changed, which is
                ; the only moment a shot can leave

; ---------------------------------------------------------------------
; ACT_MUZZLE - if the cel that just came up is a firing one, fire.
;
; WHICH CELS FIRE IS ART, NOT CODE. The artist marked the pixel a
; projectile leaves from on each firing frame and tools/spawns.py turned
; that into KCORE_SPAWNS, in the BLOB's frame numbering. The `shoot` tag
; has two of them - cels 14 and 16 - which is exactly the pair of
; pistols of CLAUDE.md 8.5 alternating, so the gun logic needs no cel
; numbers of its own and a re-drawn recoil moves the shot with it.
;
; IN : C = the set, (KARA_FRAME) the new cel
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
ACT_MUZZLE:     ld   a,c
                or   a
                ret  nz                     ; only kcore carries a gun so far
                ld   a,(KARA_FRAME)
                ld   b,a
                ld   hl,KCORE_SPAWNS
.next:          ld   a,(hl)
                inc  a
                ret  z                      ; SPAWN_END
                dec  a
                cp   b
                jr   z,.fire
                ld   de,4                   ; frame, x, y, kind
                add  hl,de
                jr   .next
.fire:          inc  hl
                ld   a,(hl)                 ; x, in pixels inside her box
                ld   (MUZZLE_X),a
                inc  hl
                ld   a,(hl)                 ; y, in lines from its top
                ld   (MUZZLE_Y),a
                jp   FIRE_BULLET
