; =====================================================================
; bullets.asm - dual pistols and the 14-round bullet pool
;
; Two magazines of 7 fire alternately. When the gun whose turn it is
; runs dry the other one takes the shot; when both are empty the reload
; timer starts. 14 rounds can be in flight at once, one pool slot each.
; =====================================================================

MAG_SIZE        equ 7
BUL_MAX         equ MAG_SIZE * 2        ; 14
BUL_STRIDE      equ 5
BUL_ACTIVE      equ 0                   ; slot layout
BUL_X           equ 1                   ; screen byte column 0-79
BUL_Y           equ 2                   ; scanline
BUL_DIR         equ 3                   ; 0 = RIGHT, 1 = left - KARA_FACING's
                                        ; convention, because that is what
                                        ; BUL_SPAWN copies into it. It used to
                                        ; be the other way round here and
                                        ; nowhere else: the Module 1-3 screen
                                        ; never writes KARA_FACING, so it sat
                                        ; at its initialiser and both readings
                                        ; agreed by accident. The first shot
                                        ; fired from the scrolling demo, where
                                        ; the player code does write it, went
                                        ; backwards out of her own muzzle.
BUL_LIFE        equ 4

BUL_SPEED       equ 2                   ; bytes per frame = 4 Mode 0 pixels
BUL_LIFE_INIT   equ 60
BUL_PEN         equ &CF                 ; solid pen 11, bright yellow
RELOAD_FRAMES   equ 60                  ; 1.2 s at 50 Hz

; ---------------------------------------------------------------------
; FIRE_BULLET - one trigger pull.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
FIRE_BULLET:    ld   a,(RELOAD_TIMER)
                or   a
                ret  nz                 ; still reloading
                ld   a,(ACTIVE_GUN)
                ld   e,a
                call GUN_MAG_PTR
                ld   a,(hl)
                or   a
                jr   nz,.fire
                ld   a,e                ; this one is dry - try the other
                xor  1
                ld   e,a
                call GUN_MAG_PTR
                ld   a,(hl)
                or   a
                jp   z,START_RELOAD     ; both dry
.fire:          dec  (hl)
                ld   a,e
                xor  1
                ld   (ACTIVE_GUN),a     ; next shot comes from the other gun
                ld   a,1
                ld   (HUD_DIRTY),a
                jp   BUL_SPAWN          ; E = the gun that actually fired

; IN: E = gun (0 left, 1 right)   OUT: HL -> its magazine
GUN_MAG_PTR:    ld   hl,MAG_LEFT
                bit  0,e
                ret  z
                ld   hl,MAG_RIGHT
                ret

; ---------------------------------------------------------------------
; BUL_SPAWN - take a free pool slot. IN: E = firing gun.
; ---------------------------------------------------------------------
BUL_SPAWN:      ld   hl,BULLETS
                ld   b,BUL_MAX
.scan:          ld   a,(hl)
                or   a
                jr   z,.take
                repeat BUL_STRIDE
                inc  hl
                rend
                djnz .scan
                ret                     ; pool full - drop the shot

                ; THE MUZZLE IS WHERE THE ARTIST PUT IT. (MUZZLE_X) and
                ; (MUZZLE_Y) are set by ACT_MUZZLE from the firing cel's
                ; own spawn point, so the two pistols differ because the
                ; drawing differs and not because of an "E lines below"
                ; fudge. X is in PIXELS inside her box; a left-facing
                ; sprite mirrors it to (width - 1 - x), which is the one
                ; subtraction tools/spawns.py's header describes.
                ; HOW DEEP THE POOL HAS EVER BEEN SINCE IT LAST
                ; EMPTIED. B counted down from BUL_MAX, so the slot just
                ; taken is BUL_MAX - B and this is one past it. Every
                ; walk of the pool stops there instead of at BUL_MAX -
                ; see the note on UPDATE_BULLETS.
.take:          ld   a,BUL_MAX + 1
                sub  b
                ld   de,BUL_TOP
                ex   de,hl
                cp   (hl)
                jr   c,.deep
                ld   (hl),a
.deep:          ex   de,hl

.found:         ld   (hl),1
                ld   a,(BUL_LIVE)
                inc  a
                ld   (BUL_LIVE),a
                inc  hl
                ld   a,(MUZZLE_X)
                ld   d,a
                ld   a,(KARA_FACING)
                or   a
                ld   a,d
                jr   z,.muzzle          ; 0 = facing right: as drawn
                neg
                add  a,KARA_W_BYTES * 2 - 1
.muzzle:        srl  a                  ; pixels -> screen bytes
                ld   d,a
                ld   a,(KARA_X)
                add  a,d
                ld   (hl),a             ; x
                inc  hl
                ld   a,(MUZZLE_Y)
                ld   d,a
                ld   a,(KARA_Y)
                add  a,d
                ld   (hl),a             ; y
                inc  hl
                ld   a,(KARA_FACING)
                ld   (hl),a             ; direction
                inc  hl
                ld   (hl),BUL_LIFE_INIT
                ret

; ---------------------------------------------------------------------
; UPDATE_BULLETS - age and move every live round.
;
; Rounds die on their life timer or at the screen edge. Tile collision
; belongs here too, but there is no tilemap until Module 4; the hook is
; marked below.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
UPDATE_BULLETS: ld   a,(BUL_LIVE)
                or   a
                jr   nz,.busy           ; AN IDLE POOL IS FOURTEEN SLOTS OF
                                        ; NOTHING. Walking them cost 1,500 T
                                        ; here, 1,848 in the draw, 1,164 in
                                        ; the erase and 1,476 in
                                        ; ENEMY_SHOT_CHECK - 6,000 T a frame
                                        ; out of the 420 a scrolling frame
                                        ; has, for rounds that are not there
                ld   (BUL_TOP),a        ; ... and the pool is empty, so the
                ret                     ; high-water mark goes back down

                ; AND A BUSY POOL IS FOURTEEN SLOTS FOR THREE ROUNDS,
                ; which is the same fault one step along and it is the
                ; bigger one. Measured over all four walks: one live
                ; round costs 7,452 T and each extra one 1,224, so
                ; 6,228 T of every firing frame was the THIRTEEN DEAD
                ; SLOTS behind it. The frame has 160 T spare (CLAUDE.md
                ; 9), so tap-firing while the screen scrolled dropped
                ; 43 frames in 200 and she stopped advancing - which is
                ; what a player sees, because in the camera's push zone
                ; her screen column is fixed and the walk IS the scroll.
                ;
                ; BUL_SPAWN always takes the lowest free slot, so the
                ; live rounds are a prefix with holes in it and the
                ; high-water mark bounds them exactly. It costs nothing
                ; per slot, which an exact live-count test would not.
.busy:          ld   a,(BUL_TOP)
                or   a
                ret  z                  ; B = 0 is 256 turns of DJNZ and 1,280
                                        ; bytes of pool: a live count without a
                                        ; depth is a table written by hand, and
                                        ; it must not scribble
                ld   b,a
                ld   hl,BULLETS
.next:          push hl
                ld   a,(hl)
                or   a
                jr   z,.skip

                push hl
                repeat BUL_LIFE
                inc  hl
                rend
                dec  (hl)               ; life
                pop  hl
                jr   z,.kill

                push hl
                inc  hl
                ld   a,(hl)             ; x
                inc  hl
                inc  hl
                bit  0,(hl)             ; direction: 0 = right
                pop  hl
                jr   nz,.left
                add  a,BUL_SPEED
                cp   SCREEN_WIDTH_BYTES
                jr   nc,.kill           ; off the right edge
                jr   .store
.left:          sub  BUL_SPEED
                jr   c,.kill            ; off the left edge
.store:         inc  hl
                ld   (hl),a                 ; its new x
                inc  hl
                ; ---- and the tile it has just flown into -------
                ; THE POOL IS IN SCREEN COORDINATES AND THE MAP IS IN
                ; WORLD ONES, so the round's byte column and its
                ; scanline are lifted into the world before the probe:
                ; + WORLD_X * 2 across and + WORLD_CR * 8 down. The row
                ; wraps in a byte, which IS the map's own height.
                ;
                ; TA_SOLID ONLY. A platform is a floor you jump up
                ; through; a round crossing its edge should not stop
                ; dead in mid-air.
                ld   c,(hl)                 ; its scanline
                dec  hl
                dec  hl                     ; back to the slot
                push hl
                ld   l,a
                ld   h,0
                ld   a,(WORLD_X)
                ld   e,a
                ld   d,0
                add  hl,de
                add  hl,de                  ; HL = world byte column
                ld   a,(WORLD_CR)
                add  a,a
                add  a,a
                add  a,a
                add  a,c                    ; ... and world pixel row
                call MAP_ATTR
                pop  hl
                and  TA_SOLID
                jr   nz,.kill
                jr   .skip

.kill:          ld   (hl),0
                ld   a,(BUL_LIVE)
                dec  a
                ld   (BUL_LIVE),a
.skip:          pop  hl
                repeat BUL_STRIDE
                inc  hl
                rend
                djnz .next
                ret

; ---------------------------------------------------------------------
; BUL_DRAW / BUL_ERASE - a round is one byte wide and two lines tall.
; Each slot remembers the address it was drawn at and the two bytes it
; covered, so erasing needs no knowledge of where the round is now.
;
; Both step down a scanline with SCR_NEXT_LINE, not SPR_NEXT_LINE: the
; blitter's version folds in a -8 to undo the eight bytes it just wrote
; across, and a round is only one byte wide.
; ---------------------------------------------------------------------
BUL_DRAW:       ld   a,(BUL_LIVE)
                ld   (BUL_DREW),a       ; ... and the erase must make exactly
                or   a                  ; the same decision, on the count as
                ret  z                  ; it was at DRAW time: UPDATE_BULLETS
                                        ; runs in between and can kill a
                                        ; round that still has to be lifted
                                        ; off the screen
                ld   a,(BUL_TOP)        ; ... and on the same DEPTH, for the
                ld   (BUL_DREW_TOP),a   ; same reason: ACT_MUZZLE can fire in
                or   a                  ; between and raise the mark, and the
                ret  z                  ; erase must not walk past what the
                ld   b,a                ; draw wrote save entries for
                ld   hl,BULLETS
                ld   de,BUL_SAVE
.next:          ld   a,(hl)
                or   a
                jr   z,.none

                push bc
                push hl                 ; pool slot
                inc  hl
                ld   c,(hl)             ; x
                inc  hl
                ld   a,(hl)             ; y
                push de                 ; SCR_ADDR clobbers DE (and B, which
                call SCR_ADDR           ; is already pushed); C = x survives
                pop  de                 ; DE = its save entry

                ld   a,l                ; remember where it went, so the
                ld   (de),a             ; erase does not have to work it out
                inc  de
                ld   a,h
                ld   (de),a
                inc  de

                ld   a,(hl)             ; first line: save, then draw
                ld   (de),a
                ld   (hl),BUL_PEN
                inc  de

                ex   de,hl              ; DE = screen, HL = save entry
                call SCR_NEXT_LINE
                ex   de,hl              ; HL = screen, DE = save entry

                ld   a,(hl)             ; second line
                ld   (de),a
                ld   (hl),BUL_PEN
                inc  de

                pop  hl
                pop  bc
                jr   .step

.none:          xor  a                  ; a zero address means "nothing drawn"
                ld   (de),a
                inc  de
                ld   (de),a
                inc  de
                inc  de
                inc  de
.step:          repeat BUL_STRIDE
                inc  hl
                rend
                djnz .next
                ret

BUL_ERASE:      ld   a,(BUL_DREW)
                or   a
                ret  z
                ld   a,(BUL_DREW_TOP)
                or   a
                ret  z
                ld   b,a
                ld   hl,BUL_SAVE
.next:          ld   e,(hl)
                inc  hl
                ld   d,(hl)             ; DE = where this round was drawn
                inc  hl
                ld   a,d
                or   e
                jr   z,.empty
                ld   a,(hl)
                ld   (de),a             ; first line back
                inc  hl
                call SCR_NEXT_LINE      ; touches AF and DE only
                ld   a,(hl)
                ld   (de),a             ; second line back
                inc  hl
                djnz .next
                ret
.empty:         inc  hl
                inc  hl
                djnz .next
                ret

; ---------------------------------------------------------------------
; Reloading
; ---------------------------------------------------------------------
START_RELOAD:   ld   a,RELOAD_FRAMES
                ld   (RELOAD_TIMER),a
                ret

UPDATE_RELOAD:  ld   a,(RELOAD_TIMER)
                or   a
                ret  z
                dec  a
                ld   (RELOAD_TIMER),a
                ret  nz                 ; still counting down

                ld   a,(AMMO_RESERVE)   ; timer expired: refill
                or   a
                ret  z                  ; out of ammo entirely
                cp   BUL_MAX
                jr   c,.partial
                ld   a,BUL_MAX
.partial:       ld   b,a                ; B = rounds to load
                ld   a,(AMMO_RESERVE)
                sub  b
                ld   (AMMO_RESERVE),a
                ld   a,b
                sub  MAG_SIZE
                jr   c,.left_only
                ld   c,MAG_SIZE         ; left full, remainder to the right
                ld   b,a
                jr   .store
.left_only:     ld   c,b
                ld   b,0
.store:         ld   a,c
                ld   (MAG_LEFT),a
                ld   a,b
                ld   (MAG_RIGHT),a
                xor  a
                ld   (ACTIVE_GUN),a
                inc  a
                ld   (HUD_DIRTY),a
                ret

; ---------------------------------------------------------------------
; State
; ---------------------------------------------------------------------
MAG_LEFT:       db MAG_SIZE
MAG_RIGHT:      db MAG_SIZE
ACTIVE_GUN:     db 0
RELOAD_TIMER:   db 0
BUL_LIVE:       db 0            ; rounds in the air
BUL_DREW:       db 0            ; ... as BUL_DRAW found it
BUL_TOP:        db 0            ; slots used, one past the deepest ever taken
BUL_DREW_TOP:   db 0            ; ... as BUL_DRAW found THAT
AMMO_RESERVE:   db 28
HUD_DIRTY:      db 1

MUZZLE_X:       db 18           ; where the current firing cel's shot leaves,
MUZZLE_Y:       db 17           ; in pixels/lines inside her box - ACT_MUZZLE
                                ; sets them from the art's own spawn points
BULLETS:        ds BUL_MAX * BUL_STRIDE
