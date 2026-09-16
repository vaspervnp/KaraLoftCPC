; =====================================================================
; enemy.asm - the level's characters, and their fire        (MODULE 5)
;
; ONE ENEMY IS DRAWN AT A TIME, AND THAT IS A BUDGET DECISION. Measured
; on this build, through the same SPAN_DRAW and SPAN_ERASE Kara goes
; through:
;
;       cityagent      12x64 box, 194-274 span bytes  40,760-48,820 T
;       citydrone       8x20 box, 100-106 span bytes  17,144-19,240 T
;       citydroneshot    3x3 box,   7 span bytes                348 T
;
; against a scrolling frame with 420 T spare on her heaviest cel and
; about 17,300 on an average one (CLAUDE.md 9). So:
;
;   * A DRONE FITS AND AN AGENT DOES NOT, by a factor of two and a
;     half. Both are in the type table because the data is right and
;     the day the frame has room for one nothing here changes; level
;     1's map ships drones.
;   * ONLY THE ONE IN VIEW IS LIVE. The rest keep their hit points and
;     their place and do nothing. They are off screen; nobody can tell.
;   * tools/make_city_map.py spaces them more than a screen apart and
;     asserts it, so "one in view" is a property of the LEVEL. ENEMY_PICK
;     takes the first it finds anyway, because a level that got it
;     wrong should lose an enemy and not the frame.
;
; THEY ARE DRAWN AFTER HER AND ERASED BEFORE HER, for the reason in
; entity.asm: her draw is the first thing in the frame because the top
; border is her whole lead. Measured, she is safe while she starts
; before 256 * KARA_Y - 4,080 T; putting a 14,000 T enemy draw in front
; of her moves that threshold from screen line 10 to about 66, and she
; would tear every time she jumped. The cost is that an enemy standing
; on her is drawn in front of her.
;
; Their shots are a separate pool from hers. It hurts the other side,
; it is a different colour, and the 348 T of span art a drone shot
; costs is not worth paying when the round she fires is a solid block
; for a fifth of that.
; =====================================================================

; ---------------------------------------------------------------------
; p0 IS ALWAYS "WHICH THING THIS IS". CLAUDE.md 8.6 first gave the
; enemy record p0 = patrol width and p1 = shots a second, which leaves
; nowhere to say WHICH character it is, and makes the fire rate a
; property of the instance when it is plainly a property of the
; character. So an enemy record reads like a pickup's:
;
;       ENEMY   p0 = EN_*      p1 = patrol half-width in TILES
;
; and the rate, the speed, the box, the art and the hit points come
; from the type. A designer places a drone, not a set of numbers.
; ---------------------------------------------------------------------
EN_AGENT        equ 0
EN_DRONE        equ 1
EN_KINDS        equ 2

EN_T_BANK       equ 0           ; the RIGHT-facing blob's bank ...
EN_T_RIGHT      equ 1           ; dw
EN_T_BANK_L     equ 3           ; ... and the left one's, which is NOT the
EN_T_LEFT       equ 4           ; dw   same bank: level_banks.py puts a
                                ;      character's two facings in C5 and C6,
                                ;      exactly as it does Kara's, and at the
                                ;      same address in each - so one bank
                                ;      byte drew the right-facing art for
                                ;      both and the drone never turned round
EN_T_MOVE_F     equ 6           ; first cel of the walk or fly loop
EN_T_MOVE_N     equ 7
EN_T_FIRE_F     equ 8
EN_T_FIRE_N     equ 9
EN_T_W          equ 10          ; box width in BYTES
EN_T_H          equ 11          ; box height in lines
EN_T_SPEED      equ 12          ; world pixels a frame
EN_T_PERIOD     equ 13          ; frames between shots
EN_T_HP         equ 14
EN_T_DUR        equ 15          ; dw - the art's own cel durations
EN_T_SPAWNS     equ 17          ; dw - the artist's muzzle points, 0 if the
                                ; sheet has none
EN_T_USED       equ 19
EN_T_STRIDE     equ 32          ; a power of two, because ENEMY_TYPE_AT
                                ; indexes it with ADD A,ENEMY_TYPES AND 255

; ALIGNED TO THE WHOLE TABLE, NOT TO ONE ROW. `align 32` put it at
; &17E0, its 64 bytes crossed &1800, and ADD A,ENEMY_TYPES AND 255
; wrapped: every type but the first read the first one's padding, so a
; drone was 135 lines tall with 23 hit points. The assert in main.asm is
; what keeps it from happening again as the table grows.
                align 64
ENEMY_TYPES:
                db L1_CITYAGENT_BANK
                dw L1_CITYAGENT_ADDR
                db L1_CITYAGENT_L_BANK
                dw L1_CITYAGENT_L_ADDR
                db CITYAGENT_WALK_FIRST, CITYAGENT_WALK_COUNT
                db CITYAGENT_FIRE_FIRST, CITYAGENT_FIRE_COUNT
                db CITYAGENT_BOX_W, CITYAGENT_BOX_H
                db 1, 90, 3
                dw CITYAGENT_DURATION
                dw CITYAGENT_SPAWNS
                ds EN_T_STRIDE - EN_T_USED

                db L1_CITYDRONE_BANK
                dw L1_CITYDRONE_ADDR
                db L1_CITYDRONE_L_BANK
                dw L1_CITYDRONE_L_ADDR
                db CITYDRONE_FLY_FIRST, CITYDRONE_FLY_COUNT
                db CITYDRONE_FIRE_FIRST, CITYDRONE_FIRE_COUNT
                db CITYDRONE_BOX_W, CITYDRONE_BOX_H
                db 1, 70, 2
                dw CITYDRONE_DURATION
                dw 0                    ; the drone sheet has no spawn point:
                ds EN_T_STRIDE - EN_T_USED  ; its shot leaves the box's nose
ENEMY_TYPES_END:

; ---------------------------------------------------------------------
; One live enemy. Sixteen bytes, one per EK_ENEMY record in the level.
; ---------------------------------------------------------------------
ES_REC          equ 0           ; dw - its record, 0 for an empty slot
ES_X            equ 2           ; dw - world pixels
ES_Y            equ 4           ; db - world pixels, the TOP of the box
ES_TYPE         equ 5
ES_FACE         equ 6           ; 0 right, 1 left - KARA_FACING's convention
ES_CEL          equ 7           ; cel inside the blob
ES_TIMER        equ 8
ES_FIRE         equ 9           ; frames to the next shot
ES_HP           equ 10          ; 0 = dead, and the slot goes quiet
ES_HOME         equ 11          ; dw - where it was placed: the patrol centre
ES_SPAN         equ 13          ; db - half-width of the patrol, in pixels
ES_DIR          equ 14          ; db - 0 = moving right
ES_STRIDE       equ 16
ENEMY_MAX       equ 4

EBUL_MAX        equ 4
EBUL_STRIDE     equ 5
EBUL_ACTIVE     equ 0
EBUL_X          equ 1           ; screen byte column, exactly like BULLETS
EBUL_Y          equ 2
EBUL_DIR        equ 3
EBUL_LIFE       equ 4
EBUL_SPEED      equ 2
EBUL_LIFE_INIT  equ 70
EBUL_PEN        equ &0F         ; solid pen 3 - their shots are not hers
EBUL_DAMAGE     equ 8

EN_SIGHT        equ 90          ; bytes - about a screen, before it opens fire
EN_H_SIGHT      equ 40          ; lines  - and roughly level with it
EN_RETRY        equ 10          ; frames before it looks again, having missed

; ---------------------------------------------------------------------
; ENEMY_SPAWN - build the live table from the level's records.
; Called by MAP_INSTALL, straight after ENT_BAKE.
;                                destroys AF,BC,DE,HL,IX
; ---------------------------------------------------------------------
ENEMY_SPAWN:    ld   hl,ENEMY_SCRIPT
                ld   (hl),&FF
                xor  a
                ld   (ENEMY_DREW),a
                ld   (ENEMY_LIVE),a
                ld   (ENEMY_LAST_CNT),a
                ld   (ENEMY_CUR),a
                ld   (ENEMY_CUR + 1),a
                ld   hl,ENEMIES
                ld   de,ENEMIES + 1
                ld   bc,ENEMY_MAX * ES_STRIDE - 1
                ld   (hl),0
                ldir
                call EBUL_CLEAR

                ld   a,(ENT_COUNT)
                or   a
                ret  z
                ld   b,a
                ld   hl,ENT_TABLE
                ld   ix,ENEMIES
.next:          push bc
                push hl
                call ENEMY_ADD
                pop  hl
                ld   bc,ENT_STRIDE
                add  hl,bc
                pop  bc
                ld   a,(ENEMY_LIVE)
                cp   ENEMY_MAX
                ret  nc                     ; no more slots: the rest of the
                djnz .next                  ; level's enemies do not exist
                ret

; HL = a record, IX = the next free slot. Fills it if the record is an
; enemy that is still alive, and steps IX past it.
ENEMY_ADD:      ld   a,(hl)
                cp   EK_ENEMY
                ret  nz
                push hl
                ld   bc,ENT_FLAGS
                add  hl,bc
                ld   a,(hl)
                and  EF_ACTIVE + EF_TAKEN   ; TAKEN means already killed
                cp   EF_ACTIVE
                jr   nz,.no
                inc  hl
                ld   a,(hl)                 ; p0 = EN_*
                cp   EN_KINDS
                jr   nc,.no
                ld   (ix + ES_TYPE),a
                inc  hl
                ld   a,(hl)                 ; p1 = patrol half-width, tiles
                add  a,a
                add  a,a
                add  a,a                    ; ... in pixels
                ld   (ix + ES_SPAN),a

                pop  hl
                push hl
                ld   (ix + ES_REC),l
                ld   (ix + ES_REC + 1),h
                inc  hl
                ld   a,(hl)
                ld   (ix + ES_X),a
                ld   (ix + ES_HOME),a
                inc  hl
                ld   a,(hl)
                ld   (ix + ES_X + 1),a
                ld   (ix + ES_HOME + 1),a
                inc  hl
                ld   c,(hl)                 ; y - the record anchors the BASE

                ld   a,(ix + ES_TYPE)
                call ENEMY_TYPE_AT          ; -> HL = the type's row
                ld   de,EN_T_H
                add  hl,de
                ld   a,c
                sub  (hl)                   ; top = base - height
                ld   (ix + ES_Y),a
                ld   de,EN_T_HP - EN_T_H
                add  hl,de
                ld   a,(hl)
                ld   (ix + ES_HP),a
                ld   de,EN_T_PERIOD - EN_T_HP
                add  hl,de
                ld   a,(hl)
                ld   (ix + ES_FIRE),a

                xor  a
                ld   (ix + ES_FACE),a
                ld   (ix + ES_CEL),a
                ld   (ix + ES_DIR),a
                inc  a
                ld   (ix + ES_TIMER),a      ; 1, and the cel index is 0: the
                                            ; animator steps before it shows,
                                            ; so this opens on cel 1 - which
                                            ; is right for a loop and is the
                                            ; opposite of ACT_UPDATE's 255,
                                            ; where cel 0 is a recoil that
                                            ; has to be seen
                ld   bc,ES_STRIDE
                add  ix,bc
                ld   hl,ENEMY_LIVE
                inc  (hl)
.no:            pop  hl
                ret

; ---------------------------------------------------------------------
; ENEMY_TYPE_AT - A = EN_* -> HL = its row of ENEMY_TYPES.
;                                destroys AF
; ---------------------------------------------------------------------
ENEMY_TYPE_AT:  add  a,a
                add  a,a
                add  a,a
                add  a,a
                add  a,a                    ; * 32
                add  a,ENEMY_TYPES AND 255  ; aligned: cannot carry
                ld   l,a
                ld   h,ENEMY_TYPES >> 8
                ret

; ---------------------------------------------------------------------
; ENEMY_PICK - which one is near enough to be alive, and where.
;
; OUT: (ENEMY_CUR) = its slot, or 0 for none
;      (ENEMY_SX)  = screen byte column of its box
;      (ENEMY_SY)  = screen line of its top, unsigned
;      (ENEMY_TYP) = its type's row
;      (ENEMY_VIS) = 1 if it can actually be DRAWN there
;
; LIVE AND DRAWABLE ARE DIFFERENT QUESTIONS, and conflating them froze
; a drone at the edge of the picture: it patrolled its beat until its
; box no longer fitted, was culled, and - because the same test decided
; whether to update it - stopped moving, so it could never walk back
; into view. It is live within a screen either side of the view and
; drawable only when its whole box fits, which is what nothing here
; clipping in X costs (CLAUDE.md 8.2).
;
; IT TAKES THE FIRST ONE NEAR, DRAWABLE OR NOT, and that is a level
; constraint and not an engine one. The near zone is EN_NEAR either side
; of an 80-byte view - 52 tiles - so two enemies can be near at once
; with only one of them drawable, and this would then keep the wrong
; one. Scanning strict first and falling back was written and measured:
; it is a second pass over the table on every frame with nothing
; drawable, and it takes this routine from 764 T to 2,656. Over a walk
; the length of level 1's roof it never once changed the answer, because
; the drones are 40 tiles apart
; and a 20-tile screen cannot have one just off its left and another
; drawable at the same time. tools/make_city_map.py asserts the spacing;
; a level built to the minimum that assert allows would need the second
; pass back.
;                                destroys AF,BC,DE,HL,IX
; ---------------------------------------------------------------------
EN_NEAR         equ 64          ; bytes outside the view it stays awake for

ENEMY_PICK:     xor  a
                ld   (ENEMY_CUR),a
                ld   (ENEMY_CUR + 1),a
                ld   (ENEMY_VIS),a
                ld   a,(ENEMY_LIVE)
                or   a
                ret  z
                ld   b,a
                ld   ix,ENEMIES
.next:          push bc
                ld   a,(ix + ES_HP)
                or   a
                jp   z,.skip                ; dead

                ld   c,(ix + ES_X)
                ld   b,(ix + ES_X + 1)
                srl  b
                rr   c                      ; its world byte
                ; THE VIEW'S LEFT EDGE IS A 16-BIT NUMBER AND ADD A,A
                ; IS NOT. WORLD_X is in characters and reaches 216, so
                ; doubling it in the accumulator alone throws the carry
                ; away from character 128 on - the left edge came back as
                ; 0 instead of 256, every enemy's screen column was wrong
                ; by 256, and the drone she was looking at read as 112
                ; bytes off the left of the picture. What that looks like
                ; is a drone drawn and then erased, halfway along the
                ; level, and it is what was reported.
                ld   a,(WORLD_X)
                ld   h,0
                add  a,a                    ; the view's left edge, in bytes
                rl   h                      ; ... and its ninth bit
                ld   l,a
                ld   d,b
                ld   e,c
                ex   de,hl
                or   a
                sbc  hl,de                  ; HL = signed screen byte column
                ld   a,h
                or   a
                jr   z,.plus
                inc  a
                jr   nz,.skip               ; more than 255 to the left
                ld   a,l
                cp   256 - EN_NEAR
                jp   c,.skip                ; ... or more than EN_NEAR
                jr   .near
.plus:          ld   a,l
                cp   SCR_CHARS * 2 + EN_NEAR
                jp   nc,.skip               ; too far to the right
                ; ITS TYPE IS LOOKED UP ONLY ONCE IT IS NEAR. The row,
                ; the box and both facings' banks are 150 T to fetch and
                ; the near test needs none of them - it is ES_X against
                ; the view and nothing else. With three enemies in the
                ; level and one of them usually in range, that is 330 T
                ; a frame spent describing enemies that are twenty tiles
                ; away. The same reject ENT_OVERLAP got in CLAUDE.md 9,
                ; for the same reason.
.near:          ld   a,l
                ld   (ENEMY_SX),a
                push hl
                ld   a,(ix + ES_TYPE)
                call ENEMY_TYPE_AT
                ld   (ENEMY_TYP),hl
                ld   de,EN_T_W
                add  hl,de
                ld   a,(hl)
                ld   (ENEMY_W),a
                inc  hl
                ld   a,(hl)
                ld   (ENEMY_H),a
                pop  hl

                ld   a,(WORLD_CR)
                add  a,a
                add  a,a
                add  a,a                    ; the view's top, in lines
                ld   c,a
                ld   a,(ix + ES_Y)
                sub  c
                ld   (ENEMY_SY),a           ; unsigned: 192-255 is above
                ld   (ENEMY_CUR),ix

                ; ... and can its whole box be put down there?
                ld   a,h
                or   a
                jr   nz,.hidden             ; off the left edge
                ld   a,l
                cp   2
                jr   c,.hidden              ; the left edge's incoming column
                ld   a,(ENEMY_W)
                add  a,2                    ; ... and the right edge's
                neg
                add  a,SCR_CHARS * 2        ; the last column it fits at
                cp   l
                jr   c,.hidden

                ; ... AND VERTICALLY, which did not matter until the city
                ; had a street under it. ENEMY_SY is unsigned, so a drone
                ; left up on the roof while she is at the bottom of the
                ; ladder reads as 236 rather than -20, and drawn there its
                ; lines run through the off-screen margin and fold back
                ; over the top of the picture - the same fault KARA_DRAW
                ; is culled for in CLAUDE.md 8.2.
                ld   a,(ENEMY_SY)
                ld   c,a
                ld   a,(ENEMY_H)
                add  a,c
                jr   c,.hidden              ; wrapped: it is above the view
                cp   SCR_CHAR_ROWS * 8 + 1
                jr   nc,.hidden             ; ... or past the bottom of it

                ld   a,1
                ld   (ENEMY_VIS),a
.hidden:        pop  bc
                ret                         ; the FIRST one near, and only
                                            ; that one - see the header
.skip:          ld   bc,ES_STRIDE
                add  ix,bc
                pop  bc
                dec  b
                jp   nz,.next               ; JP, not JR: the loop body grew
                ret                         ; past a relative jump's reach

; ---------------------------------------------------------------------
; ENEMY_UPDATE - one frame of the one that is on screen, and of every
; shot in the air.
;
; Call after ENT_UPDATE, so her box is where the physics left it. IT
; DOES NOT PICK: the loop calls ENEMY_PICK at the top of the frame,
; straight after H_COMMIT, because that is the only moment WORLD_X and
; the CRTC agree - picking down here would give the NEXT frame's draw a
; screen column computed under the last frame's start address, and the
; enemy would jitter a character every time the screen scrolled.
;                                destroys AF,BC,DE,HL,IX
; ---------------------------------------------------------------------
ENEMY_UPDATE:   ld   hl,(ENEMY_CUR)
                ld   a,h
                or   l
                jp   z,EBUL_UPDATE          ; nobody in view; the air is not
                push hl                     ; empty though
                pop  ix

                ; ---- patrol ----------------------------------------
                ld   hl,(ENEMY_TYP)
                ld   de,EN_T_SPEED
                add  hl,de
                ld   c,(hl)                 ; C = speed
                ld   e,(ix + ES_X)
                ld   d,(ix + ES_X + 1)
                ld   a,(ix + ES_DIR)
                or   a
                jr   nz,.left
                ld   a,e
                add  a,c
                ld   e,a
                jr   nc,.moved
                inc  d
                jr   .moved
.left:          ld   a,e
                sub  c
                ld   e,a
                jr   nc,.moved
                dec  d
.moved:         ld   (ix + ES_X),e
                ld   (ix + ES_X + 1),d
                ; past the end of its beat? |x - home| > span
                ld   l,(ix + ES_HOME)
                ld   h,(ix + ES_HOME + 1)
                or   a
                ex   de,hl
                sbc  hl,de                  ; x - home
                jr   nc,.pos
                ; negative: negate it, so one compare does both sides
                ld   a,h
                cpl
                ld   h,a
                ld   a,l
                cpl
                ld   l,a
                inc  hl
.pos:           ld   a,h
                or   a
                jr   nz,.turn               ; more than 255 away: turn
                ld   a,(ix + ES_SPAN)
                cp   l
                jr   nc,.walked
.turn:          ld   a,(ix + ES_DIR)
                xor  1
                ld   (ix + ES_DIR),a
.walked:

                ; ---- face her, not its beat ------------------------
                ; A patrol turns at the end of its beat; a gun turns to
                ; whoever it is shooting at. They are different things
                ; and the sprite follows the gun.
                call ENEMY_SEES
                jr   nc,.blind
                ld   (ix + ES_FACE),a       ; ENEMY_SEES leaves the facing in A
                ld   a,(ix + ES_FIRE)
                dec  a
                ld   (ix + ES_FIRE),a
                jr   nz,.armed
                call ENEMY_FIRE
                ld   hl,(ENEMY_TYP)
                ld   de,EN_T_PERIOD
                add  hl,de
                ld   a,(hl)
                ld   (ix + ES_FIRE),a
                jr   .armed
.blind:         ld   a,(ix + ES_DIR)        ; out of sight: it faces its walk
                ld   (ix + ES_FACE),a
                ld   a,(ix + ES_FIRE)
                cp   EN_RETRY
                jr   c,.armed
                ld   a,EN_RETRY             ; ... and stops counting down to
                ld   (ix + ES_FIRE),a       ; a shot it cannot take
.armed:
                call ENEMY_ANIMATE
                jp   EBUL_UPDATE

; ---------------------------------------------------------------------
; ENEMY_SEES - is she in front of it and close enough to shoot?
;
; OUT: carry set and A = the facing that points at her, or carry clear
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
ENEMY_SEES:     ld   c,(ix + ES_X)
                ld   b,(ix + ES_X + 1)
                srl  b
                rr   c                      ; its world byte
                ld   hl,(KARA_WX)
                ld   d,b
                ld   e,c
                or   a
                sbc  hl,de                  ; kara - enemy
                ld   a,0                    ; ... and which way that is
                jr   nc,.right
                ld   a,h                    ; she is to the LEFT: negate
                cpl
                ld   h,a
                ld   a,l
                cpl
                ld   l,a
                inc  hl
                ld   a,1
.right:         ld   (ENEMY_FACE_WANT),a
                ld   a,h
                or   a
                ret  nz                     ; over 255 bytes: carry is clear
                ld   a,EN_SIGHT
                cp   l
                ret  c                      ; too far

                ld   a,(ix + ES_Y)          ; and roughly level with it
                ld   c,a
                ld   a,(KARA_WY)
                sub  c
                jr   nc,.below
                neg
.below:         cp   EN_H_SIGHT
                ret  nc                     ; carry clear: too high or too low
                ld   a,(ENEMY_FACE_WANT)
                scf
                ret

; ---------------------------------------------------------------------
; ENEMY_ANIMATE - step the cel, at the art's own rate.
;
; The cel set is the fire loop while a shot is on its way out and the
; move loop otherwise, which is why the fire tag is only two cels: it
; is a recoil, not a sequence.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
ENEMY_ANIMATE:  ld   a,(ix + ES_TIMER)
                dec  a
                ld   (ix + ES_TIMER),a
                ret  nz

                ld   hl,(ENEMY_TYP)
                ld   de,EN_T_MOVE_F
                add  hl,de
                ld   a,(ix + ES_FIRE)       ; just fired? the recoil plays
                ld   c,a
                ld   a,(ix + ES_CEL)
                ld   e,(hl)                 ; move first
                inc  hl
                ld   d,(hl)                 ; move count
                ; if the cel is inside the FIRE range, stay in it until it
                ; runs out; otherwise loop the move range.
                inc  hl
                ld   b,(hl)                 ; fire first
                inc  hl
                ld   c,(hl)                 ; fire count
                cp   b
                jr   c,.move                ; below the fire range
                ld   l,a
                sub  b
                cp   c
                jr   nc,.move               ; above it
                inc  l
                ld   a,l
                sub  b
                cp   c
                ld   a,l
                jr   c,.set                 ; still inside the recoil
                ld   a,e                    ; recoil done: back to the loop
                jr   .set
.move:          inc  a
                ld   l,a
                sub  e
                cp   d
                ld   a,l
                jr   c,.set
                ld   a,e                    ; round the loop
.set:           ld   (ix + ES_CEL),a
                call ENEMY_HOLD
                ld   (ix + ES_TIMER),a
                ret

; ---------------------------------------------------------------------
; ENEMY_HOLD - A = a cel -> A = how many frames the art holds it for.
;                                destroys AF,DE,HL
; ---------------------------------------------------------------------
ENEMY_HOLD:     push af
                ld   hl,(ENEMY_TYP)
                ld   de,EN_T_DUR
                add  hl,de
                ld   e,(hl)
                inc  hl
                ld   d,(hl)                 ; DE = the art's duration table
                pop  af
                ld   l,a
                ld   h,0
                add  hl,de
                ld   a,(hl)
                or   a
                ret  nz
                inc  a                      ; a zero would stop it dead
                ret

; ---------------------------------------------------------------------
; ENEMY_FIRE - one shot, from where the artist says it leaves.
;
; build/levels/spawns.inc marks, per firing cel, the pixel the shot's
; left edge sits on (CLAUDE.md 7.1). The humanoids have one; the drone
; sheet does not, and its shot leaves the nose of its box. A left-
; facing sprite mirrors the x to frame_width - 1 - x, which is one
; subtraction against storing the table twice.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
ENEMY_FIRE:     ld   hl,(ENEMY_TYP)
                ld   de,EN_T_FIRE_F
                add  hl,de
                ld   a,(hl)
                ld   (ix + ES_CEL),a        ; the recoil starts now ...
                ; ... AND ITS FIRST CEL HAS TO BE SEEN. A timer of 1
                ; here is counted straight down by the ENEMY_ANIMATE
                ; call that follows in the same ENEMY_UPDATE, which
                ; steps past cel 4 and opens the recoil on cel 5 - the
                ; same mistake CLAUDE.md 8.4 records for her entry
                ; cels. Load the art's own hold time for it instead.
                call ENEMY_HOLD
                ld   (ix + ES_TIMER),a

                ld   hl,(ENEMY_TYP)
                ld   de,EN_T_SPAWNS
                add  hl,de
                ld   e,(hl)
                inc  hl
                ld   d,(hl)
                ld   a,d
                or   e
                jr   z,.nose                ; no table: use the box
                ex   de,hl
                ld   a,(ix + ES_CEL)
                ld   c,a
.look:          ld   a,(hl)
                cp   SPAWN_END
                jr   z,.nose                ; this cel is not a firing one
                cp   c
                jr   z,.found
                inc  hl
                inc  hl
                inc  hl
                inc  hl
                jr   .look
.found:         inc  hl
                ld   a,(hl)                 ; x inside the box, in pixels
                inc  hl
                ld   c,(hl)                 ; y inside the box, in lines
                jr   .mirror
.nose:          ld   hl,(ENEMY_TYP)
                ld   de,EN_T_W
                add  hl,de
                ld   a,(hl)
                add  a,a
                dec  a                      ; the box's right edge, in pixels
                ld   c,a
                srl  c                      ; ... and its middle, in lines,
                inc  hl                     ; from the height
                ld   a,(hl)
                srl  a
                ld   c,a
                ld   hl,(ENEMY_TYP)
                ld   de,EN_T_W
                add  hl,de
                ld   a,(hl)
                add  a,a
                dec  a
.mirror:        ld   b,a                    ; B = x in pixels, C = y in lines
                ld   a,(ix + ES_FACE)
                or   a
                jr   z,.face
                ld   hl,(ENEMY_TYP)
                ld   de,EN_T_W
                add  hl,de
                ld   a,(hl)
                add  a,a
                dec  a
                sub  b                      ; frame_width - 1 - x
                ld   b,a
.face:          ; -> a screen position, which is what the pool holds
                ld   a,(ENEMY_SX)
                ld   l,a
                ld   a,b
                srl  a                      ; pixels to bytes
                add  a,l
                ld   b,a                    ; B = screen byte column
                ld   a,(ENEMY_SY)
                add  a,c
                ld   c,a                    ; C = screen line
                ld   a,(ix + ES_FACE)
                ; falls into EBUL_SPAWN

; ---------------------------------------------------------------------
; EBUL_SPAWN - A = direction, B = screen byte column, C = screen line.
;                                destroys AF,DE,HL
; ---------------------------------------------------------------------
EBUL_SPAWN:     ld   e,a
                ld   hl,EBULLETS
                ld   d,EBUL_MAX
.next:          ld   a,(hl)
                or   a
                jr   z,.free
                ld   a,EBUL_STRIDE
                add  a,l
                ld   l,a
                jr   nc,.same
                inc  h
.same:          dec  d
                jr   nz,.next
                ret                         ; all four in the air already
.free:          ld   (hl),1
                ld   a,(EBUL_LIVE)
                inc  a
                ld   (EBUL_LIVE),a
                inc  hl
                ld   (hl),b
                inc  hl
                ld   (hl),c
                inc  hl
                ld   (hl),e
                inc  hl
                ld   (hl),EBUL_LIFE_INIT
                ret

EBUL_CLEAR:     xor  a
                ld   (EBUL_LIVE),a
                ld   (EBUL_DREW),a
                ld   hl,EBULLETS
                ld   de,EBULLETS + 1
                ld   bc,EBUL_MAX * EBUL_STRIDE - 1
                ld   (hl),0
                ldir
                ld   hl,EBUL_SAVE
                ld   de,EBUL_SAVE + 1
                ld   bc,EBUL_MAX * 4 - 1
                ld   (hl),0
                ldir
                ret

; ---------------------------------------------------------------------
; EBUL_UPDATE - move their rounds, and hurt her where one lands.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
EBUL_UPDATE:    ld   a,(EBUL_LIVE)
                or   a
                ret  z
                ld   hl,EBULLETS
                ld   b,EBUL_MAX
.next:          push hl
                ld   a,(hl)
                or   a
                jr   z,.skip

                push hl
                ld   de,EBUL_LIFE
                add  hl,de
                dec  (hl)
                pop  hl
                jr   z,.kill

                push hl
                inc  hl
                ld   a,(hl)                 ; x
                inc  hl
                inc  hl
                bit  0,(hl)                 ; direction: 0 = right
                pop  hl
                jr   nz,.left
                add  a,EBUL_SPEED
                cp   SCR_CHARS * 2
                jr   nc,.kill
                jr   .store
.left:          sub  EBUL_SPEED
                jr   c,.kill
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
                jr   .hit_her
.hit_her:       call EBUL_HITS_HER
                jr   nc,.skip
.kill:          ld   (hl),0
                ld   a,(EBUL_LIVE)
                dec  a
                ld   (EBUL_LIVE),a
.skip:          pop  hl
                ld   de,EBUL_STRIDE
                add  hl,de
                djnz .next
                ret

; ---------------------------------------------------------------------
; EBUL_HITS_HER - HL = a round. Carry set if it just hit her, and her
; health has already been taken off.
;
; Her box is in WORLD units and the round is in SCREEN ones, so the
; comparison is done on screen: KARA_X and KARA_Y are where the loop
; draws her, which is exactly where the player sees her get hit. KARA_X
; is her SPRITE's left edge, so KARA_ART_X puts the box back on her body
; - a round that passed six pixels to her left used to count as a hit.
;                                destroys AF,BC,DE
; ---------------------------------------------------------------------
EBUL_HITS_HER:  push hl
                inc  hl
                ld   d,(hl)                 ; its screen byte column
                inc  hl
                ld   e,(hl)                 ; its screen line
                ld   a,(KARA_X)
                add  a,KARA_ART_X
                ld   c,a
                ld   a,d
                sub  c
                jr   c,.miss
                cp   KARA_BOX_W
                jr   nc,.miss
                ld   a,(KARA_Y)
                ld   c,a
                ld   a,e
                sub  c
                jr   c,.miss
                cp   KARA_BOX_H
                jr   nc,.miss
                ld   a,(PLAYER_HP)
                sub  EBUL_DAMAGE
                jr   nc,.alive
                xor  a
.alive:         ld   (PLAYER_HP),a
                pop  hl
                scf
                ret
.miss:          pop  hl
                or   a
                ret

; ---------------------------------------------------------------------
; ENEMY_SHOT_CHECK - her rounds against the one on screen.
;
; Called from the loop after UPDATE_BULLETS, so a round that has just
; been killed by a wall is not also credited with a kill.
;                                destroys AF,BC,DE,HL,IX
; ---------------------------------------------------------------------
ENEMY_SHOT_CHECK:
                ld   hl,(ENEMY_CUR)
                ld   a,h
                or   l
                ret  z
                push hl
                pop  ix
                ld   a,(ix + ES_HP)
                or   a
                ret  z
                ld   hl,(ENEMY_TYP)
                ld   de,EN_T_W
                add  hl,de
                ld   a,(hl)
                ld   (ENEMY_W),a
                inc  hl
                ld   a,(hl)
                ld   (ENEMY_H),a

                ld   a,(BUL_LIVE)
                or   a
                ret  z                      ; she has not fired
                ld   a,(BUL_TOP)            ; only as deep as the pool went -
                or   a                      ; see UPDATE_BULLETS
                ret  z
                ld   b,a
                ld   hl,BULLETS
.next:          push hl
                ld   a,(hl)
                or   a
                jr   z,.skip
                inc  hl
                ld   d,(hl)                 ; its screen byte column
                inc  hl
                ld   e,(hl)                 ; its screen line
                ld   a,(ENEMY_SX)
                ld   c,a
                ld   a,d
                sub  c
                jr   c,.skip
                ld   c,a
                ld   a,(ENEMY_W)
                cp   c
                jr   c,.skip
                jr   z,.skip
                ld   a,(ENEMY_SY)
                ld   c,a
                ld   a,e
                sub  c
                jr   c,.skip
                ld   c,a
                ld   a,(ENEMY_H)
                cp   c
                jr   c,.skip
                jr   z,.skip
                pop  hl
                ld   (hl),0                 ; the round is spent
                ld   a,(BUL_LIVE)
                dec  a
                ld   (BUL_LIVE),a
                call ENEMY_WOUND
                ret  c                      ; it died: nothing else can hit it
                push hl
.skip:          pop  hl
                ld   de,BUL_STRIDE
                add  hl,de
                djnz .next
                ret

; ENEMY_WOUND - one hit on IX. Carry set if that killed it.
;                                destroys AF,DE,HL
ENEMY_WOUND:    ld   a,(ix + ES_HP)
                dec  a
                ld   (ix + ES_HP),a
                ret  nz
                ; Dead. Mark the RECORD too, so a reload of the level
                ; does not put it back on its feet.
                ld   l,(ix + ES_REC)
                ld   h,(ix + ES_REC + 1)
                ld   de,ENT_FLAGS
                add  hl,de
                ld   a,(hl)
                or   EF_TAKEN
                ld   (hl),a
                scf
                ret

; ---------------------------------------------------------------------
; ENEMY_REFRESH - lift the enemy off the screen and put it back down
; where it is now. ONE CALL, AT THE END OF THE FRAME, AFTER HERS.
;
; THE ENEMY IS A PERSISTENT SPRITE AND SHE IS NOT, and that is what
; makes it affordable. Hers is drawn and erased inside one frame,
; because she moves every frame. The enemy's pixels are LEFT ON THE
; SCREEN between refreshes:
;
;   * while the picture scrolls they stay right for nothing, because
;     the CRTC moves every pixel on the screen and a world-fixed sprite
;     is supposed to move exactly that far;
;   * Kara's save-under captures them where she walks over it and her
;     erase puts them back, and the two bullet pools do the same, so
;     nothing else on the screen disturbs them;
;   * the incoming column is the one thing that would, and ENEMY_PICK
;     keeps the whole box a character clear of both edges so it cannot.
;
; So a frame that cannot afford 17,968 T of enemy simply does not spend
; it, and nothing flickers - which is the whole difference between this
; and skipping a draw-and-erase pair.
;
; WHY IT IS LAST. It cannot go before her draw: she is 560 T a line
; against the raster's 256 and the top border is her entire lead, so
; 18,000 T in front of her tears her from screen line 38 down. It
; cannot go between her draw and her erase either: she would save the
; enemy's new pixels and then her erase would paint background over
; them. After her erase, both problems are gone and the beam is past
; the lines it writes.
;
; OUT: (ENEMY_LAST_CNT) lines drawn, 0 if none
;      (ENEMY_LAST_BOT) the lowest line it reached
;      (ENEMY_DREW)     non-zero while its pixels are on the screen
;      destroys AF,BC,DE,HL,IX,B',C'
; ---------------------------------------------------------------------
ENEMY_REFRESH:  ; ---- WHAT THE SCREEN SHOWS MUST MATCH THE STATE ----
                ; The budget gate below may postpone the sprite's
                ; ANIMATION and its patrol. Whether it is on the screen
                ; at all is not negotiable, and getting that wrong
                ; showed up twice on real hardware:
                ;
                ;   * a drone she WALKED past was never drawn, because a
                ;     walk keeps VIEW_STEP up for as long as it lasts;
                ;   * one that had been drawn was never lifted off, so
                ;     the scroll carried its pixels out of the picture
                ;     and the 1024-word ring brought them back at the
                ;     opposite edge a character row up - copies of
                ;     itself, trailing behind it.
                ;
                ; So two frames an encounter pay whatever it costs: the
                ; one it comes into view on and the one it leaves on.
                ld   a,(ENEMY_DREW)
                or   a
                jr   z,.absent

                ; ---- its pixels are up there. Do they still belong? --
                ; NOT "is the enemy visible" - where its PIXELS are. The
                ; two drift apart because it keeps patrolling while the
                ; refresh is postponed, by up to its whole beat, and it
                ; is the pixels the incoming column is about to recycle.
                call ENEMY_PIX_SAFE
                jr   nc,.afford
                ld   hl,(ENEMY_CUR)
                ld   a,h
                or   l
                jr   z,.afford              ; it died, or left the level's
                ld   a,(ENEMY_VIS)          ; near zone
                or   a
                jr   z,.afford
                jr   .optional

.absent:        ld   hl,(ENEMY_CUR)         ; nothing on the screen: should
                ld   a,h                    ; there be?
                or   l
                ret  z
                ld   a,(ENEMY_VIS)
                or   a
                ret  z
                jr   .afford

                ; ---- the screen is already right, so only the cel and
                ; the patrol are waiting - and those can wait.
                ;
                ; WHILE THE PICTURE IS MOVING IT DOES NOT HAVE TO BE
                ; REDRAWN, and that is not a compromise, it is the CRTC
                ; doing the work: a world-fixed sprite has to move left
                ; when the camera pans right, and every pixel on the
                ; screen does exactly that when R12/R13 step.
                ;
                ; AND NOT ON THE FRAME ENT_UPDATE SWEEPS THE PICKUPS.
                ; Measured, the frame that pays for both is 80,248 T of
                ; 79,872 - over by 376 - so they take alternate frames.
                ; She cannot cross a 4-byte pickup in the 2 bytes a
                ; frame she can travel, and ENT_UPDATE's INTERACT pass
                ; still runs every frame because a keypress lasts one.
.optional:      ld   a,(FRAME_COUNT)
                rra
                jr   nc,.hold
                ld   hl,VIEW_STEP
                ld   a,(hl)
                or   a
                jr   z,.afford
                dec  (hl)
.hold:          ld   a,(ENEMY_LAST_CNT)
                ret

.afford:        ; LIFT THE LAST ONE OFF BEFORE PUTTING THIS ONE DOWN.
                ; A persistent sprite is erased by the refresh that
                ; replaces it and by nothing else, so this is the ONLY
                ; place its pixels ever come off the screen. Without it
                ; every refresh left the last image where it was and
                ; drew another one beside it - the enemy trailing copies
                ; of itself across the roof.
                ld   a,(ENEMY_DREW)
                or   a
                jr   z,.gone
                ld   hl,ENEMY_SCRIPT
                call SPAN_ERASE_AT
.gone:          xor  a
                ld   (ENEMY_DREW),a
                ld   (ENEMY_LAST_CNT),a
                ld   (ENEMY_LAST_BOT),a
                ld   hl,ENEMY_SCRIPT        ; an empty script, so nothing can
                ld   (hl),&FF               ; restore the same bytes twice
                ld   hl,(ENEMY_CUR)
                ld   a,h
                or   l
                ret  z
                push hl
                pop  ix
                ld   a,(ix + ES_HP)
                or   a
                ret  z
                ld   a,(ENEMY_VIS)
                or   a
                ret  z                      ; near, but its box does not fit
                inc  a
                ld   (ENEMY_DREW),a         ; its pixels are on the screen now
                ld   a,(ENEMY_W)
                ld   (ENEMY_DREW_W),a       ; ... this wide, and at THIS world
                ld   l,(ix + ES_X)          ; byte, which is what
                ld   h,(ix + ES_X + 1)      ; ENEMY_PIX_SAFE watches - not
                srl  h                      ; where it has patrolled to since
                rr   l
                ld   (ENEMY_DREW_WX),hl

                ld   hl,(ENEMY_TYP)
                ld   a,(ix + ES_FACE)
                or   a
                jr   z,.face
                ld   de,EN_T_BANK_L         ; the facings are in different
                add  hl,de                  ; banks, at the same address
                jr   .bank
.face:          ld   de,EN_T_BANK
                add  hl,de
.bank:          ld   c,(hl)
                inc  hl
                ld   e,(hl)
                inc  hl
                ld   d,(hl)                 ; DE = the blob
                ld   b,&7F
                out  (c),c

                ld   a,(ix + ES_CEL)
                add  a,a
                ld   l,a
                ld   h,0
                add  hl,de
                ld   a,(hl)                 ; relative, like Kara's
                inc  hl
                ld   h,(hl)
                ld   l,a
                add  hl,de

                ld   a,(ENEMY_SY)
                call SPAN_CLIP_V            ; -> HL groups, A top, C lines
                ld   b,a                    ; B = its first drawn line
                ld   a,c
                ld   (ENEMY_LAST_CNT),a
                or   a
                jr   z,.none
                dec  a
                add  a,b
                ld   (ENEMY_LAST_BOT),a
.none:          push hl
                push bc
                ld   a,(ENEMY_SX)
                ld   c,a
                ld   a,b
                call SCR_ADDR
                ex   de,hl                  ; DE = screen
                pop  bc                     ; C = lines to draw
                pop  hl                     ; HL = the frame's groups
                ld   a,c
                ld   bc,ENEMY_SCRIPT
                call SPAN_DRAW              ; called even at 0 lines: a stale
                jp   BANK_RESTORE           ; script would put back old bytes

; ---------------------------------------------------------------------
; ENEMY_PIX_SAFE - are the pixels that ARE on the screen still a
; character clear of both edges, under the view showing now?
;
; OUT: carry set if they are.        destroys AF,DE,HL
; ---------------------------------------------------------------------
ENEMY_PIX_SAFE: ld   hl,(ENEMY_DREW_WX)     ; the world byte they were put at
                ld   a,(WORLD_X)            ; 16 bits, and for the reason in
                ld   d,0                    ; ENEMY_PICK: ADD A,A alone loses
                add  a,a                    ; the carry from character 128 on
                rl   d
                ld   e,a
                or   a
                sbc  hl,de                  ; -> their screen byte column
                ld   a,h
                or   a
                jr   nz,.unsafe             ; off the left edge entirely
                ld   a,l
                cp   2
                jr   c,.unsafe              ; inside the left incoming column
                ld   a,(ENEMY_DREW_W)
                add  a,2
                neg
                add  a,SCR_CHARS * 2        ; the last column it fits clear at
                cp   l
                jr   c,.unsafe
                scf
                ret
.unsafe:        or   a
                ret

; ---------------------------------------------------------------------
; EBUL_DRAW / EBUL_ERASE - one byte wide, two lines tall, exactly like
; her rounds and for the same reason: a span-compressed shot is 348 T
; and this is 134.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
EBUL_DRAW:      ld   a,(EBUL_LIVE)
                ld   (EBUL_DREW),a
                or   a
                ret  z
                ld   b,EBUL_MAX
                ld   hl,EBULLETS
                ld   de,EBUL_SAVE
.next:          ld   a,(hl)
                or   a
                jr   z,.none
                push bc
                push hl
                inc  hl
                ld   c,(hl)
                inc  hl
                ld   a,(hl)
                push de
                call SCR_ADDR               ; C = x survives it
                pop  de
                ld   a,l
                ld   (de),a
                inc  de
                ld   a,h
                ld   (de),a
                inc  de
                ld   a,(hl)
                ld   (de),a
                ld   (hl),EBUL_PEN
                inc  de
                ex   de,hl
                call SCR_NEXT_LINE
                ex   de,hl
                ld   a,(hl)
                ld   (de),a
                ld   (hl),EBUL_PEN
                inc  de
                pop  hl
                pop  bc
                jr   .step
.none:          xor  a
                ld   (de),a
                inc  de
                ld   (de),a
                inc  de
                inc  de
                inc  de
.step:          push de
                ld   de,EBUL_STRIDE
                add  hl,de
                pop  de
                djnz .next
                ret

EBUL_ERASE:     ld   a,(EBUL_DREW)
                or   a
                ret  z
                ld   b,EBUL_MAX
                ld   hl,EBUL_SAVE
.next:          ld   e,(hl)
                inc  hl
                ld   d,(hl)
                inc  hl
                ld   a,d
                or   e
                jr   z,.empty
                ld   a,(hl)
                ld   (de),a
                inc  hl
                call SCR_NEXT_LINE
                ld   a,(hl)
                ld   (de),a
                inc  hl
                djnz .next
                ret
.empty:         inc  hl
                inc  hl
                djnz .next
                ret

ENEMY_LIVE:     db 0            ; slots in use
ENEMY_CUR:      dw 0            ; the one on screen, 0 for none
ENEMY_TYP:      dw 0            ; ... and its row of ENEMY_TYPES
ENEMY_SX:       db 0
ENEMY_SY:       db 0
ENEMY_W:        db 0
ENEMY_H:        db 0
ENEMY_FACE_WANT:db 0
EBUL_LIVE:      db 0            ; their rounds in the air
EBUL_DREW:      db 0
ENEMY_VIS:      db 0            ; can the one in ENEMY_CUR be drawn?
ENEMY_LAST_CNT: db 0
ENEMY_LAST_BOT: db 0
ENEMY_DREW:     db 0            ; its pixels are on the screen
ENEMY_DREW_WX:  dw 0            ; ... at this world byte, this wide
ENEMY_DREW_W:   db 0
ENEMIES:        ds ENEMY_MAX * ES_STRIDE
EBULLETS:       ds EBUL_MAX * EBUL_STRIDE
