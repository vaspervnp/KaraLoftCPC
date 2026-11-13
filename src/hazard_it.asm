; =====================================================================
; hazard_it.asm - the ENEMY's box as it was drawn, in world characters,
; for the trap painter's HZ_UNDER_IT (src/hazard.asm, CLAUDE.md 8.26).
; In the SOUND image, which is base RAM like the rest and had the room
; the core had not.
;
; A TRAP AND AN ENEMY IN ONE LEVEL. The enemy is a persistent sprite:
; its pixels stay on the screen between refreshes and its erase is its
; NEXT refresh, which puts back the background it saved when it was
; drawn (8.7). A trap cell painted under that box after the draw is put
; back as its old cel the moment the enemy moves - and a stale cel
; under a spike is a spike she cannot see. So no pass paints a cell
; under the box the enemy was last drawn in; it waits on the list until
; the enemy has gone, the way a cell under HER waits for her erase.
; Once a pass, and only when there is something to paint.
;                                destroys AF,BC,DE,HL
; =====================================================================
HZ_IT_BOUNDS:   ld   a,(ENEMY_DREW)
                ld   de,&00FF               ; first 255, last 0: nothing
                or   a
                jr   z,.rows                ; (and the rows alone decide it)
                ld   hl,(ENEMY_DREW_WX)
                ld   a,(ENEMY_DREW_W)
                ld   b,1                    ; bytes -> characters
                call HZ_HER_BOUNDS.first_last
                ld   (HZ_IX0),de
                ld   hl,(ENEMY_DREW_WY)
                ld   a,(ENEMY_DREW_H)
                ld   b,3                    ; lines -> character rows
                call HZ_HER_BOUNDS.first_last
.rows:          ld   (HZ_IY0),de
                ret
