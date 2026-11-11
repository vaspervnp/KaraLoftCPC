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
EN_SNIPER       equ 2           ; the forest's, and the first row here that
EN_KINDS        equ 3           ; is not the city's

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
;
; AND `align 64` WAS NOT ENOUGH EITHER, which the third row is what
; showed: 3 * 32 is 96 bytes, and an align of 64 can put those at
; offset 192 of a page, where they end at 288. The rule in CLAUDE.md 10
; says align to the WHOLE table and this is the table's own size
; rounded up - 128 holds four rows exactly, and the assert is what will
; say so on the fifth.
;
; AND THEN `align 128` WAS TOO MUCH, which the sea is what showed. What
; the indexing needs is that the table does not CROSS a page, and an
; align is only one way to get that: every byte the code in front of it
; grows by is free until the table would cross, and then the align
; costs up to 127 bytes at once. The cable's runs took the hazard code
; five bytes past &1B00 and the core past &4000 by about a hundred. So
; it moves to the next page only when it has to - here, and asserted in
; main.asm, which is the same rule written once more.
                if ($ AND 255) + EN_KINDS * EN_T_STRIDE > 256
                align 256
                endif
ENEMY_TYPES:
                db L1_CITYAGENT_BANK
                dw L1_CITYAGENT_ADDR
                db L1_CITYAGENT_L_BANK
                dw L1_CITYAGENT_L_ADDR
                db CITYAGENT_WALK_FIRST, CITYAGENT_WALK_COUNT
                db CITYAGENT_FIRE_FIRST, CITYAGENT_FIRE_COUNT
                db CITYAGENT_BOX_W, CITYAGENT_BOX_H
                db 2, 45, 3     ; speed, fire period, hit points - the
                                ; first two doubled and halved for the
                                ; 25 Hz game frame (src/main.asm)
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
                db 2, 35, 2     ; ... and the same on this one
                dw CITYDRONE_DURATION
                dw 0                    ; the drone sheet has no spawn point:
                ds EN_T_STRIDE - EN_T_USED  ; its shot leaves the box's nose

                ; THE FOREST'S SNIPER, AND IT IS AN AGENT-CLASS SPRITE.
                ; 12x64 like the cityagent, which 8.7 measured at
                ; 40,760-48,820 T drawn and erased against a 79,872 T
                ; frame and called unaffordable - and 9 says that at
                ; 25 Hz it is affordable ON PAPER, with nothing having
                ; measured it. Placing one is that measurement.
                db L2_FORESTSNIPER_BANK
                dw L2_FORESTSNIPER_ADDR
                db L2_FORESTSNIPER_L_BANK
                dw L2_FORESTSNIPER_L_ADDR
                db FORESTSNIPER_WALK_FIRST, FORESTSNIPER_WALK_COUNT
                db FORESTSNIPER_FIRE_FIRST, FORESTSNIPER_FIRE_COUNT
                db FORESTSNIPER_BOX_W, FORESTSNIPER_BOX_H
                db 2, 45, 3     ; speed, fire period, hit points
                dw FORESTSNIPER_DURATION
                dw FORESTSNIPER_SPAWNS
                ds EN_T_STRIDE - EN_T_USED
ENEMY_TYPES_END:

; ---------------------------------------------------------------------
; One live enemy. Seventeen bytes, one per EK_ENEMY record in the level.
;
; ES_Y IS A WORD AND WAS A BYTE, which is the same widening KARA_WY and
; ENT_CELL_OF have had: a map is 2,048 tiles of any power-of-two shape
; now (mapshape.asm), so a 32-wide level is 64 rows - 1,024 world lines
; - and a byte holds the top quarter of it. The slot was full, so the
; stride went 16 -> 17; nothing indexes a slot by shifting, both walks
; are LD BC,ES_STRIDE : ADD IX,BC.
; ---------------------------------------------------------------------
ES_REC          equ 0           ; dw - its record, 0 for an empty slot
ES_X            equ 2           ; dw - world pixels
ES_Y            equ 4           ; dw - world pixels, the TOP of the box
ES_TYPE         equ 6
ES_FACE         equ 7           ; 0 right, 1 left - KARA_FACING's convention
ES_CEL          equ 8           ; cel inside the blob
ES_TIMER        equ 9
ES_FIRE         equ 10          ; frames to the next shot
ES_HP           equ 11          ; 0 = dead, and the slot goes quiet
ES_HOME         equ 12          ; dw - where it was placed: the patrol centre
ES_SPAN         equ 14          ; db - half-width of the patrol, in pixels
ES_DIR          equ 15          ; db - 0 = moving right
ES_DIE          equ 16          ; db - frames of dying left, 0 = not
ES_STRIDE       equ 17
EN_DIE_FRAMES   equ 20          ; game frames the fall and the flashing last
EN_DIE_VY_MAX   equ 12          ; pixels a game frame on the way down
ENEMY_MAX       equ 4

EBUL_MAX        equ 4
EBUL_STRIDE     equ 5
EBUL_ACTIVE     equ 0
EBUL_X          equ 1           ; screen byte column, exactly like BULLETS
EBUL_Y          equ 2
EBUL_DIR        equ 3
EBUL_LIFE       equ 4
EBUL_SPEED      equ 4           ; bytes a GAME frame, on two frames in
                                ; three. THIS WAS MISSED WHEN THE GAME
                                ; WENT TO 25 Hz and hers was doubled: at
                                ; 2 it was half the real speed it had
                                ; been, and a play-test reported their
                                ; rounds as almost invisible
EBUL_LIFE_INIT  equ 53          ; game frames - and half as long again
                                ; than hers, because they
                                ; move on two frames in three now
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
                ; ... AND THE REST OF THE LAST DRAW'S RECORD WITH THEM.
                ; ENEMY_DREW gates every read of these three, so they
                ; are dead the moment it is zero and clearing them
                ; changes no behaviour at all. What it changes is that
                ; a level INSTALLED OVER A LEVEL THAT WAS PLAYED - which
                ; is what the FSM's restart is (src/flow.asm) - leaves
                ; nothing of the old one behind to explain. Half a
                ; record cleared and half left is the shape of every
                ; bug in CLAUDE.md 10, and this is 9 bytes once a level.
                ld   (ENEMY_LAST_BOT),a
                ld   (ENEMY_DREW_W),a
                ld   (ENEMY_DREW_WX),a
                ld   (ENEMY_DREW_WX + 1),a
                ; ... and the one that was following her is following
                ; nobody: the level is a new one, or the same one again.
                ld   (ENEMY_ENG),a
                ld   (ENEMY_ENG + 1),a
                ld   (ENEMY_SIDE),a
                ld   (ENEMY_DREW_H),a
                ld   (ENEMY_DREW_WY),a
                ld   (ENEMY_DREW_WY + 1),a
                ; ... and the rounds' keep-out, which ZONE_XW gates
                ; exactly as ENEMY_DREW gates the draw's record above.
                ld   (ZONE_X0),a
                ld   (ZONE_XW),a
                ld   (ZONE_Y0),a
                ld   (ZONE_YH),a
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
                inc  hl
                ld   b,(hl)                 ; ... and the record's y is a word

                ld   a,(ix + ES_TYPE)
                call ENEMY_TYPE_AT          ; -> HL = the type's row
                ld   de,EN_T_H
                add  hl,de
                ld   a,c
                sub  (hl)                   ; top = base - height, in sixteen
                ld   (ix + ES_Y),a          ; bits: a drone placed on row 20
                ld   a,b                    ; of a 64-row map anchors at world
                sbc  a,0                    ; line 336
                ld   (ix + ES_Y + 1),a
ENEMY_Y_HI      equ  $ - 6                  ; the six bytes a suite replaces
                                            ; with `ld (ix + ES_Y + 1),0` and
                                            ; two NOPs, to ask what the 8-bit
                                            ; slot would have done with the
                                            ; same record
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
;      (ENEMY_TYP) = its type's row, (ENEMY_W) and (ENEMY_H) its box
;      (ENEMY_SX)  = screen byte column of its box, and (ENEMY_SXH)
;                    the high byte of that: only 0 is a column of this
;                    view
;      (ENEMY_SY)  = screen line of its top, a SIGNED WORD: only a
;                    high byte of 0 is a line of this picture
;      (ENEMY_VIS) = 1 if it can actually be DRAWN there
;      ... and the rounds' keep-out round it (ENEMY_ZONE)
;
; THE ONE FOLLOWING HER COMES FIRST, AND IT IS THE ONLY ONE THERE IS
; UNTIL IT IS DEAD. A drone that has been on the screen is ENGAGED
; (ENEMY_REFRESH) and does not patrol a beat any more: it keeps to her,
; on its own side of her, and never leaves the view (ENEMY_FOLLOW). A
; play-test reported the drones "jumping from one place to another,
; disappearing and coming back" - which was a redraw this engine could
; afford on one frame in two and on no frame the picture moved, a cull
; at a hard edge, and a beat the camera walked away from - and asked
; for this instead: from the moment one appears, fast but not abrupt,
; and on the screen until she kills it or it kills her. So the scan
; below is only ever for the NEXT one, once the last has finished
; falling.
;
; LIVE AND DRAWABLE ARE DIFFERENT QUESTIONS, and conflating them froze
; a drone at the edge of the picture: it patrolled its beat until its
; box no longer fitted, was culled, and - because the same test decided
; whether to update it - stopped moving, so it could never walk back
; into view. It is live within EN_NEAR either side of the view, and
; drawable only inside the window ENEMY_PLACE says.
;
; IT TAKES THE FIRST ONE NEAR, DRAWABLE OR NOT, and that is a level
; constraint and not an engine one: tools/make_city_map.py spaces their
; beats more than a screen apart and asserts it. A strict pass first
; and a fallback was written and measured - 764 T to 2,656 on every
; frame with nothing drawable - and over a walk the length of level
; 1's roof it never once changed the answer.
;                                destroys AF,BC,DE,HL,IX
; ---------------------------------------------------------------------
EN_NEAR         equ 64          ; bytes outside the view it stays awake for

; WHERE ONE MAY BE DRAWN - and an ENGAGED one never leaves it (below).
EN_XL           equ 4           ; bytes clear of the left and right edges:
                                ; TWO characters, not one. The incoming
                                ; column's head is painted into the
                                ; screen's outer column on the frame
                                ; before a step and its next one into the
                                ; column inside that on a run, and a
                                ; refresh whose erase lands after either
                                ; puts stale tiles back into it (ENEMY_SLOT)
EN_YB           equ 176         ; ... and the line its box must end above:
                                ; rows 22 and 23 are the strip's and the
                                ; strip's vacate (CLAUDE.md 7.8), and a
                                ; persistent save-under is what put a copy
                                ; of the HUD on the wall last time

; WHAT AN ENGAGED ONE DOES. Every distance is from her, and every speed
; is a GAME frame's - 25 Hz (src/main.asm).
EN_DIST         equ 22          ; bytes, her middle to its middle: twelve
                                ; bytes of air between the two sprites
EN_SWAY         equ 8           ; world pixels either side of that it drifts
EN_CHASE        equ 4           ; world pixels a frame, catching up: two
                                ; bytes, which is her run - so it keeps up
EN_MIN          equ 10          ; bytes, middle to middle, that are closer
                                ; than the two boxes allow: (12 + 8) / 2.
                                ; A place on its side that close to her is
                                ; no place, and it changes sides
EN_DY           equ 12          ; lines below her top it hovers at: its box
                                ; is then across her muzzle's line, which
                                ; is where every map in the City put it
EN_VY           equ 4           ; lines a frame it climbs or sinks to her
EN_XSTEP        equ 2           ; bytes: the view can scroll a character
                                ; between its move and its draw
EN_VTOP         equ 8           ; lines it keeps inside the view's top and
EN_VBOT         equ EN_YB - 8   ; ... above this bottom, at its own logic:
                                ; the vertical latch is between that and
                                ; the draw and moves the view a row

ENEMY_PICK:     xor  a
                ld   (ENEMY_CUR),a
                ld   (ENEMY_CUR + 1),a
                ld   (ENEMY_VIS),a
                ld   (ZONE_XW),a            ; no keep-out until one is near
                ld   a,(ENEMY_LIVE)
                or   a
                ret  z

                ld   hl,(ENEMY_ENG)         ; the one following her, for as
                ld   a,h                    ; long as it is alive or still
                or   l                      ; falling
                jr   z,.scan
                push hl
                pop  ix
                ld   a,(ix + ES_HP)
                or   (ix + ES_DIE)
                jr   nz,.take
                ld   (ENEMY_ENG),a          ; dead and down: let go (A = 0)
                ld   (ENEMY_ENG + 1),a

.scan:          ld   a,(ENEMY_LIVE)
                ld   b,a
                ld   ix,ENEMIES
.next:          push bc
                ld   a,(ix + ES_HP)
                or   (ix + ES_DIE)          ; dead AND done falling. One that
                jr   z,.skip                ; is still coming down is live
                call ENEMY_COLUMN           ; HL = its signed screen column
                ld   a,h
                or   a
                jr   z,.plus
                inc  a
                jr   nz,.skip               ; more than 255 to the left
                ld   a,l
                cp   256 - EN_NEAR
                jr   c,.skip                ; ... or more than EN_NEAR
                jr   .near
.plus:          ld   a,l
                cp   SCR_CHARS * 2 + EN_NEAR
                jr   nc,.skip               ; too far to the right
                ; ITS TYPE IS LOOKED UP ONLY ONCE IT IS NEAR. The row,
                ; the box and both facings' banks are 150 T to fetch and
                ; the near test needs none of them - it is ES_X against
                ; the view and nothing else. The same reject ENT_OVERLAP
                ; got in CLAUDE.md 9, for the same reason.
.near:          pop  bc
.take:          ld   (ENEMY_CUR),ix
                ld   a,(ix + ES_TYPE)
                call ENEMY_TYPE_AT
                ld   (ENEMY_TYP),hl
                call ENEMY_PLACE
                jp   ENEMY_ZONE             ; the FIRST one near, and only
                                            ; that one - see the header
.skip:          ld   bc,ES_STRIDE
                add  ix,bc
                pop  bc
                djnz .next
                ret

; ---------------------------------------------------------------------
; ENEMY_COLUMN - IX = a slot -> HL = its box's screen byte column, a
; SIGNED WORD.                    destroys AF,DE,HL
;
; THE VIEW'S LEFT EDGE IS A 16-BIT NUMBER AND ADD A,A IS NOT. WORLD_X
; is in characters and reaches 216, so doubling it in the accumulator
; alone throws the carry away from character 128 on - the left edge came
; back as 0 instead of 256, every enemy's screen column was wrong by
; 256, and the drone she was looking at read as 112 bytes off the left
; of the picture. What that looked like was a drone drawn and then
; erased, halfway along the level, and it is what was reported.
; ---------------------------------------------------------------------
ENEMY_COLUMN:   ld   l,(ix + ES_X)
                ld   h,(ix + ES_X + 1)
                srl  h
                rr   l                      ; its world byte
                ld   a,(WORLD_X)
                ld   d,0
                add  a,a                    ; the view's left edge, in bytes
                rl   d                      ; ... and its ninth bit
                ld   e,a
                or   a
                sbc  hl,de
                ret

; ---------------------------------------------------------------------
; ENEMY_PLACE - IX = the slot, (ENEMY_TYP) its row. Where it is on the
; screen under the view as it stands NOW, and whether it can be drawn.
;
; IT IS CALLED TWICE A FRAME AND THE SECOND IS THE ONE THAT DRAWS. The
; first is ENEMY_PICK's, at the top of the frame, for the logic: the
; shot check and the gun both work in screen units. The second is
; ENEMY_REFRESH's, in the second sweep - after the patrol has moved it
; and after the VERTICAL latch has moved the view, both of which used
; to land between the number and the pixels: it was drawn at a column
; the patrol had already left (CLAUDE.md 8.7's "66..73 against 65 or
; 67"), and on a frame the view stepped a row, eight lines from where
; it was.
;
; THE WINDOW IS EN_XL CLEAR OF BOTH EDGES AND ENDS AT EN_YB, and an
; engaged one is held inside it by ENEMY_FOLLOW, so for one that is
; following her the answer is always yes.
;
; OUT: (ENEMY_W), (ENEMY_H), (ENEMY_SX), (ENEMY_SXH), (ENEMY_SY),
;      (ENEMY_VIS)                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
ENEMY_PLACE:    ld   hl,(ENEMY_TYP)
                ld   de,EN_T_W
                add  hl,de
                ld   a,(hl)
                ld   (ENEMY_W),a
                inc  hl
                ld   a,(hl)
                ld   (ENEMY_H),a
                call ENEMY_COLUMN
                ld   a,l
                ld   (ENEMY_SX),a
                ld   a,h
                ld   (ENEMY_SXH),a
                ; AND THE VIEW'S TOP IS A 16-BIT NUMBER FOR THE SAME
                ; REASON ITS LEFT EDGE IS. WORLD_CR reaches V_CR_MAX,
                ; which is 104 on a 32x64 map, so WORLD_CR * 8 is 832 and
                ; three ADD A,A in the accumulator throw the carry away.
                ld   a,(WORLD_CR)
                ld   d,0
                add  a,a
                rl   d
                add  a,a
                rl   d
                add  a,a
                rl   d
                ld   e,a                    ; DE = the view's top, in lines
                ld   a,(ix + ES_Y)
                sub  e
                ld   (ENEMY_SY),a
                ld   c,a
                ld   a,(ix + ES_Y + 1)
                sbc  a,d
                ld   (ENEMY_SY + 1),a       ; signed: 0 is the only drawable
                                            ; high byte, and 255 is above
                ; ... and can its whole box be put down there?
                ;
                ; ES_Y IS A WORD, so "above" is not the only way to be off
                ; the picture by more than a byte: on a 64-row map a
                ; drone 300 lines BELOW the view has a low byte of 44,
                ; which is a line in the middle of the picture. The two
                ; high bytes are the whole of that test.
                ld   b,0                    ; B = the answer, no until yes
                or   h
                jr   nz,.out                ; off the left or right by more
                                            ; than a byte, or above or below
                ld   a,l
                cp   EN_XL
                jr   c,.out                 ; inside the left edge's two
                ld   a,(ENEMY_W)
                add  a,EN_XL
                neg
                add  a,SCR_CHARS * 2        ; the last column it may start
                cp   l                      ; at, clear of the right edge's
                jr   c,.out                 ; two
                ld   a,(ENEMY_H)
                add  a,c
                jr   c,.out                 ; wrapped: it is above the view
                cp   EN_YB + 1
                jr   nc,.out                ; ... or into the strip's rows
                inc  b
.out:           ld   a,b
                ld   (ENEMY_VIS),a
                ret

; ---------------------------------------------------------------------
; ENEMY_ZONE - the rounds' keep-out round the one ENEMY_PICK found.
;
; THE REFRESH RUNS BEFORE THE ROUNDS COME OFF NOW (ENEMY_SLOT), and a
; round drawn over the drone's box breaks it either way round: the
; round's save-under holds the drone's pixels and its erase puts them
; back after the drone has moved on - a piece of the old drone left on
; the wall - or the drone saves the round as its background and puts a
; stray round back a frame later. A round that close to it is a frame
; from hitting it or a frame out of its gun, so it is not DRAWN: EN_ZX
; bytes and EN_ZY lines round its box, which is what one frame of its
; own movement, a scroll step and a row step can take it. Hers still
; hits it and its own still flies - nothing about either is changed
; but whether the beam shows it for that frame or two.
;                                destroys AF,BC
; ---------------------------------------------------------------------
EN_ZX           equ 6           ; bytes: its chase, and a scroll step
EN_ZY           equ 20          ; lines: its climb or its fall, and a row

ENEMY_ZONE:     ld   a,(ENEMY_SXH)
                ld   b,a
                ld   a,(ENEMY_SY + 1)
                or   b
                ret  nz                     ; not in this picture: no zone
                ld   a,(ENEMY_SX)
                cp   SCR_CHARS * 2
                ret  nc
                ld   a,(ENEMY_SY)
                cp   SCR_LINES
                ret  nc
                ld   a,(ENEMY_SX)
                sub  EN_ZX
                jr   nc,.x0
                xor  a
.x0:            ld   (ZONE_X0),a
                ld   b,a
                ld   a,(ENEMY_SX)
                ld   c,a
                ld   a,(ENEMY_W)
                add  a,c
                add  a,EN_ZX                ; one past its last column, and
                sub  b                      ; the margin
                ld   (ZONE_XW),a
                ld   a,(ENEMY_SY)
                sub  EN_ZY + 1              ; a round is two lines tall
                jr   nc,.y0
                xor  a
.y0:            ld   (ZONE_Y0),a
                ld   b,a
                ld   a,(ENEMY_SY)
                ld   c,a
                ld   a,(ENEMY_H)
                add  a,c
                jr   c,.ycap                ; an agent's 64 lines can carry
                add  a,EN_ZY
                jr   nc,.yok
.ycap:          ld   a,255
.yok:           sub  b
                ld   (ZONE_YH),a
                ret

; ---------------------------------------------------------------------
; ROUND_HIDDEN - C = a round's screen column, A = its line. Carry set if
; it is inside ENEMY_ZONE's keep-out and must not be drawn this frame.
; Called by BUL_DRAW and EBUL_DRAW.  destroys F only
; ---------------------------------------------------------------------
ROUND_HIDDEN:   push hl
                ld   l,a
                ld   a,(ZONE_X0)
                ld   h,a
                ld   a,c
                sub  h
                ld   h,a                    ; x - X0, unsigned
                ld   a,(ZONE_XW)
                cp   h
                jr   c,.out
                jr   z,.out                 ; one past the zone
                ld   a,(ZONE_Y0)
                ld   h,a
                ld   a,l
                sub  h
                ld   h,a
                ld   a,(ZONE_YH)
                cp   h
                jr   c,.out
                jr   z,.out
                ld   a,l
                pop  hl
                scf
                ret
.out:           ld   a,l
                pop  hl
                or   a
                ret

; ---------------------------------------------------------------------
; ENEMY_UPDATE - one frame of the one that is on screen, and of every
; shot in the air.
;
; Call through ENEMY_THINK, in the second sweep: her box is where the
; first sweep's physics left it, and the screen units its gun works in
; are the view as latched. IT DOES NOT PICK: the loop calls ENEMY_PICK
; at the top of the frame, straight after H_COMMIT. Where it is DRAWN
; is worked out again when it is drawn (ENEMY_PLACE), after this has
; moved it.
;                                destroys AF,BC,DE,HL,IX
; ---------------------------------------------------------------------
ENEMY_UPDATE:   ld   hl,(ENEMY_CUR)
                ld   a,h
                or   l
                jp   z,EBUL_UPDATE          ; nobody in view; the air is not
                push hl                     ; empty though
                pop  ix

                ; ---- dead ones fall before they go -----------------
                ld   a,(ix + ES_DIE)
                or   a
                jp   nz,ENEMY_DYING

                ; ---- one that is following her moves elsewhere -----
                ; ENEMY_MOVE, at the END of the second sweep: the first
                ; one carries her draw, the column's tail, the strip and
                ; all of the logic, and on a run with the gun it has
                ; under a thousand T to give (CLAUDE.md 9). The patrol
                ; below is cheap and stays.
                call ENEMY_IS_ENG
                jr   z,.walked

                ; ---- patrol ----------------------------------------
.patrol:        ld   hl,(ENEMY_TYP)
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
                ; IT HAS TO BE ON THE SCREEN BEFORE IT CAN SHOOT.
                ; Being LIVE and being DRAWN are different things: a
                ; drone is live within EN_NEAR of the view and drawn
                ; only once its whole box is inside the window, so it
                ; could open fire from a screen the player cannot see it
                ; on. Rounds arriving out of nowhere are not a difficulty
                ; setting. ENEMY_DREW is the honest test - its pixels are
                ; up there - and the sight test below is what it costs.
                call ENEMY_SEES
                jr   nc,.blind
                ld   (ix + ES_FACE),a       ; ENEMY_SEES leaves the facing in A
                ld   a,(ENEMY_DREW)
                or   a
                jr   z,.armed               ; live, but nobody can see it yet
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
; ENEMY_IS_ENG - Z if the one in ENEMY_CUR is the one following her.
;                                destroys AF,DE,HL
; ---------------------------------------------------------------------
ENEMY_IS_ENG:   ld   hl,(ENEMY_ENG)
                ld   a,h
                or   l
                jr   z,.no
                ld   de,(ENEMY_CUR)
                or   a
                sbc  hl,de
                ret                         ; Z: the same slot
.no:            or   1                      ; NZ: nobody is following her
                ret

; ---------------------------------------------------------------------
; ENEMY_MOVE - the one following her, one frame on. Called at the END
; of the second sweep, after its refresh, so the place it works out is
; the one the NEXT frame's logic aims with and the next frame's refresh
; draws - the two agree, and neither waits on the other.
;
; THE VIEW IT CLAMPS AGAINST MOVES ONCE MORE BEFORE THAT DRAW: the next
; frame's H_COMMIT can step it a character either way, and its
; SCROLL_VBLANK a row. So the wall is a scroll step and a row inside the
; window ENEMY_PLACE draws in (EN_CLAMP_X, EN_VTOP, EN_VBOT).
;                                destroys AF,BC,DE,HL,IX
; ---------------------------------------------------------------------
ENEMY_MOVE:     ld   a,(ENEMY_EARLY)
                cp   EN_HOLD
                ret  z                      ; held this frame (ENEMY_SLOT)
                call ENEMY_IS_ENG
                ret  nz
                ld   ix,(ENEMY_ENG)
                ld   a,(ix + ES_HP)
                or   a
                ret  z                      ; dead: ENEMY_DYING has it
                ld   a,(ix + ES_DIE)
                or   a
                ret  nz
                ; falls into ENEMY_FOLLOW

; ---------------------------------------------------------------------
; ENEMY_FOLLOW - one frame of the one that is following her. IX = it.
;
; ACROSS: it keeps EN_DIST bytes from her, on its own side, drifting
; EN_SWAY either side of that at its own speed and catching up at
; EN_CHASE - which is her run, so nothing she does leaves it behind.
; Where its side has no room - she is at the screen's edge, which only
; the ends of a map allow - it goes to the other side.
;
; DOWN: it climbs or sinks EN_VY lines a frame to her chest, EN_DY below
; her top, so it is always across the line she fires along and the
; line its own sight test wants her on.
;
; AND THE VIEW IS A WALL. Whatever those two say, it is put back inside
; EN_XL of both edges and EN_VTOP..EN_VBOT of the top - here, at the
; logic, before the latch that can still move the view a row, which is
; what the eight lines of margin are for - so the window ENEMY_PLACE
; draws in is one it never leaves. That is the whole of "it does not
; disappear": nothing takes it off the screen but her gun.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
ENEMY_FOLLOW:   ld   hl,(KARA_WX)
                ld   de,KARA_BOX_W / 2
BX_FOLLOW       equ  $ - 2                  ; AFTER the instruction it names:
                                            ; before it, it named the operand
                                            ; of ld hl,(KARA_WX) (CLAUDE.md 10)
                add  hl,de
                ld   (EN_HERMID),hl         ; her middle, world bytes
                ld   b,2                    ; its side, and then the other
.side:          push bc
                ld   hl,(EN_HERMID)
                ld   de,EN_DIST
                ld   a,(ENEMY_SIDE)
                or   a
                jr   z,.right
                ld   de,-EN_DIST
.right:         add  hl,de                  ; the middle it wants
                call EN_HALF_W
                or   a
                sbc  hl,de                  ; ... as its box's left edge
                call EN_CLAMP_X             ; ... inside the view
                ld   (EN_TGT),hl
                call EN_HALF_W
                add  hl,de                  ; the middle it can have
                ld   de,(EN_HERMID)
                or   a
                sbc  hl,de                  ; ... less hers: + is her right
                ld   a,(ENEMY_SIDE)
                or   a
                jr   z,.gap
                ex   de,hl                  ; on her left the gap is -d
                ld   hl,0
                or   a
                sbc  hl,de
.gap:           ld   de,EN_MIN
                or   a
                sbc  hl,de                  ; the gap less the least it may be
                pop  bc
                bit  7,h
                jr   z,.placed              ; room on its side
                ld   a,(ENEMY_SIDE)
                xor  1
                ld   (ENEMY_SIDE),a
                djnz .side                  ; none: try the other side

.placed:        ld   hl,(EN_TGT)
                add  hl,hl                  ; the place, in world pixels
                ld   (EN_TGT),hl
                call EN_FROM_TGT            ; HL = how far, A = which way
                ld   c,a
                ld   a,h
                or   a
                jr   nz,.chase
                ld   a,l
                cp   EN_SWAY + 1
                jr   c,.drift
.chase:         ld   (ix + ES_DIR),c        ; out of its sway: straight there
                ld   c,EN_CHASE
                call EN_STEP
                jr   .across
.drift:         ld   hl,(ENEMY_TYP)         ; inside it: on at its own speed,
                ld   de,EN_T_SPEED          ; and where that would take it
                add  hl,de                  ; out, it holds for a frame and
                ld   c,(hl)                 ; turns round - a hover at each
                call EN_STEP                ; end, the patrol's own turn
                call EN_FROM_TGT
                ld   a,h
                or   a
                jr   nz,.turn
                ld   a,l
                cp   EN_SWAY + 1
                jr   c,.across
.turn:          ld   a,(ix + ES_DIR)
                xor  1
                ld   (ix + ES_DIR),a
                call EN_STEP                ; ... back where it was
.across:        ld   l,(ix + ES_X)          ; and the view is a wall: the
                ld   h,(ix + ES_X + 1)      ; camera can have stepped under
                srl  h                      ; it since the place was chosen
                rr   l
                call EN_CLAMP_X
                add  hl,hl
                ld   (ix + ES_X),l
                ld   (ix + ES_X + 1),h
                ; ... and a wall it is turned round by, like the end of
                ; its sway. Without that, a place of its own on the wall -
                ; she is near the screen's edge on its side - is a drift
                ; INTO the wall for ever, and measured standing there it
                ; did not move a byte in 49 frames.
                or   a
                jr   z,.level_x             ; it was inside
                dec  a                      ; 1: put at the left edge, so it
                ld   (ix + ES_DIR),a        ; goes right (0); 2: at the right
.level_x:

                ; ---- down: to her chest, EN_VY lines a frame --------
                ld   hl,(KARA_WY)
                ld   de,EN_DY
                add  hl,de                  ; where its top wants to be
                ld   e,(ix + ES_Y)
                ld   d,(ix + ES_Y + 1)
                or   a
                sbc  hl,de                  ; ... less where it is
                jr   z,.level
                jr   c,.rise
                ld   a,h                    ; below it: sink
                or   a
                jr   nz,.smax
                ld   a,l
                cp   EN_VY
                jr   c,.sby
.smax:          ld   a,EN_VY
.sby:           add  a,e
                ld   e,a
                jr   nc,.vput
                inc  d
                jr   .vput
.rise:          ld   a,h                    ; above it: climb, by the size
                cpl                         ; of the difference negated
                ld   h,a
                ld   a,l
                cpl
                ld   l,a
                inc  hl
                ld   a,h
                or   a
                jr   nz,.rmax
                ld   a,l
                cp   EN_VY
                jr   c,.rby
.rmax:          ld   a,EN_VY
.rby:           ld   c,a
                ld   a,e
                sub  c
                ld   e,a
                jr   nc,.vput
                dec  d
.vput:          ld   (ix + ES_Y),e
                ld   (ix + ES_Y + 1),d

.level:         ; ... and the view is a wall top and bottom too
                ld   a,(WORLD_CR)
                ld   l,a
                ld   h,0
                add  hl,hl
                add  hl,hl
                add  hl,hl                  ; the view's top, world lines
                ld   de,EN_VTOP
                add  hl,de                  ; HL = the highest it may be
                ld   e,(ix + ES_Y)
                ld   d,(ix + ES_Y + 1)
                ex   de,hl                  ; HL = its top, DE = that
                or   a
                sbc  hl,de
                jr   c,.to_de               ; above it
                add  hl,de                  ; its top again
                push hl
                ld   a,(ENEMY_H)
                neg
                add  a,EN_VBOT - EN_VTOP
                ld   l,a
                ld   h,0
                add  hl,de
                ex   de,hl                  ; DE = the lowest its top may be
                pop  hl
                push hl
                or   a
                sbc  hl,de
                pop  hl
                ret  c                      ; above that: it is in
                ret  z
.to_de:         ld   (ix + ES_Y),e
                ld   (ix + ES_Y + 1),d
                ret

; EN_HALF_W - DE = half the box's width, in bytes.   destroys AF
EN_HALF_W:      ld   a,(ENEMY_W)
                srl  a
                ld   e,a
                ld   d,0
                ret

; EN_FROM_TGT - IX = a slot -> HL = |(EN_TGT) - its x|, in world pixels,
; and A = the way to EN_TGT: 0 right, 1 left.        destroys DE
EN_FROM_TGT:    ld   hl,(EN_TGT)
                ld   e,(ix + ES_X)
                ld   d,(ix + ES_X + 1)
                or   a
                sbc  hl,de                  ; the place less where it is
                ld   a,0                    ; (LD leaves the carry alone)
                ret  nc                     ; at it, or to its right
                ex   de,hl
                ld   hl,0
                or   a
                sbc  hl,de
                ld   a,1
                ret

; EN_STEP - IX = a slot: x += C world pixels, the way ES_DIR says.
;                                destroys AF,B,HL
EN_STEP:        ld   l,(ix + ES_X)
                ld   h,(ix + ES_X + 1)
                ld   b,0
                ld   a,(ix + ES_DIR)
                or   a
                jr   z,.add
                sbc  hl,bc                  ; OR A above cleared the carry
                jr   .put
.add:           add  hl,bc
.put:           ld   (ix + ES_X),l
                ld   (ix + ES_X + 1),h
                ret

; ---------------------------------------------------------------------
; EN_CLAMP_X - HL = a box's left edge in world bytes -> HL inside the
; drawable window of the view showing now, a scroll step in from it:
; EN_XL + EN_XSTEP clear of both edges, for a box (ENEMY_W) wide. A
; negative HL - a place worked out past the map's own left end - is put
; at the window's left edge, which is what an unsigned compare would get
; backwards. A = 0 if it was inside, 1 if it was put at the left edge,
; 2 at the right.
;                                destroys AF,DE
; ---------------------------------------------------------------------
EN_CLAMP_X:     push hl
                ld   a,(WORLD_X)
                ld   h,0
                add  a,a
                rl   h
                ld   l,a
                ld   de,EN_XL + EN_XSTEP
                add  hl,de
                ex   de,hl                  ; DE = the leftmost it may be
                pop  hl
                bit  7,h
                jr   nz,.to_lo              ; negative: the left edge
                push hl
                or   a
                sbc  hl,de
                pop  hl
                jr   c,.to_lo               ; left of it
                push hl
                ld   a,(ENEMY_W)
                neg
                add  a,SCR_CHARS * 2 - (EN_XL + EN_XSTEP) * 2
                ld   l,a
                ld   h,0
                add  hl,de
                ex   de,hl                  ; DE = the rightmost it may be
                pop  hl
                push hl
                or   a
                sbc  hl,de
                pop  hl
                ld   a,0                    ; (LD leaves the flags alone)
                ret  c                      ; left of that: it is in
                ret  z
                ld   a,2
                ex   de,hl
                ret
.to_lo:         ld   a,1
                ex   de,hl
                ret

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
                ; KARA_WY IS A WORD AND THIS READS ITS LOW BYTE, which is
                ; right for the same reason PLAYER_SCREEN_X's truncation
                ; is (8.7): what is wanted is a small DIFFERENCE, and
                ; modular arithmetic gives it as long as the two are
                ; within 128 lines - which EN_H_SIGHT is what enforces.
                ; Both are words now and both are read a byte at a time
                ; here, and that is the same answer as before rather than
                ; a saving: a modular difference needs no high byte.
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
                ld   a,SFX_ESHOT            ; the drone's own sound: nothing
                jp   SFX_REQ                ; it leaves behind says "fired"

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

                ld   a,(BUL_PHASE)          ; the frame they hold still on -
                dec  a                      ; see bullets.asm
                jr   z,.skip
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
                push hl                     ; ... and the row in DE, sixteen
                ld   a,(WORLD_CR)           ; bits of it: WORLD_CR * 8 is 832
                ld   l,a                    ; lines on a 64-tile map
                ld   h,0
                add  hl,hl
                add  hl,hl
                add  hl,hl
                ld   e,c
                ld   d,0
                add  hl,de
                ex   de,hl
                pop  hl
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
BX_EB_ART       equ  $ - 1
                ld   c,a
                ld   a,d
                sub  c
                jr   c,.miss
                cp   KARA_BOX_W
BX_EB_W         equ  $ - 1
                jr   nc,.miss
                ld   a,(KARA_Y)
                ld   c,a
                ld   a,e
                sub  c
                jr   c,.miss
                cp   KARA_BOX_H
BX_EB_H         equ  $ - 1
                jr   nc,.miss
                ; AND SHE IS SHORTER WHEN SHE CROUCHES. The pose is the
                ; roll's first cel and the artist draws it from line 23
                ; of the box where she stands from line 6, so a box that
                ; stayed 64 lines tall would take hits on a head that is
                ; not there. Her FEET do not move, so only the top of
                ; the box does - see KARA_CROUCH_TOP in action.asm.
                ;
                ; B IS THE CALLER'S LOOP COUNTER. EBUL_UPDATE holds the
                ; slot count in it across this call and finishes with
                ; DJNZ, so the obvious two-register form of this test
                ; walked the pool for ever and wrote over the core.
                ld   c,a                    ; C = the line inside her box
                ld   a,(KARA_STATE)
                cp   KST_CROUCH
                jr   nz,.body
                ld   a,c
                cp   KARA_CROUCH_TOP
                jr   c,.miss                ; over her head, and she ducked
.body:
                ld   a,(PLAYER_HP)
                sub  EBUL_DAMAGE
                jr   nc,.alive
                xor  a
.alive:         ld   (PLAYER_HP),a
                ld   a,HURT_FRAMES          ; and the border says so, because
                ld   (HURT_FLASH),a         ; there is no HUD yet (main.asm)
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
                ; AND ITS SCREEN LINE HAS TO BE ONE. This runs on the one
                ; that is NEAR, drawable or not (ENEMY_PICK), and the
                ; pool holds screen positions - so with a 16-bit ES_Y a
                ; drone 300 lines below the view compares at line 44 and
                ; is shot through the floor. ENEMY_PICK's own vertical
                ; test, which is the high byte and nothing else.
                ld   a,(ENEMY_SY + 1)
                or   a
                ret  nz
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
ENEMY_WOUND:    ld   a,SFX_EHIT             ; SFX_REQ keeps the flags: the
                call SFX_REQ                ; carry below is this routine's
                ld   a,(ix + ES_HP)         ; answer (src/sound.asm)
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
                ; AND IT FALLS OUT OF THE SKY BEFORE IT GOES. A drone
                ; that simply vanished on its last hit read as a bug -
                ; the shot that killed it and the frame it disappeared
                ; on are the same one, so nothing on screen says which
                ; of them did it. It keeps its slot for EN_DIE_FRAMES
                ; more frames instead, falling and flashing, and
                ; ENEMY_PICK above keeps picking it while it does.
                ld   (ix + ES_DIE),EN_DIE_FRAMES
                ld   a,SFX_EKILL
                call SFX_REQ
                scf
                ret

; ---------------------------------------------------------------------
; ENEMY_DYING - it is dead and on its way down. IX = the slot.
;
; No patrol, no gun, no animation: it falls, gathering speed, and
; ENEMY_REFRESH flashes it on and off around this counter. When the
; counter runs out the slot goes quiet and the next refresh lifts its
; pixels off for good.
;
; THE FALL IS NOT THE PHYSICS. There is no ground under a drone hovering
; over a roof gap or a street, and a death that had to land somewhere
; would need a probe per frame for something nobody is going to watch.
; It falls for as long as the counter lasts and then it is gone.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
ENEMY_DYING:    ld   a,(ix + ES_DIE)
                dec  a
                ld   (ix + ES_DIE),a
                ld   b,a
                ld   a,EN_DIE_FRAMES
                sub  b                      ; frames since the hit
                srl  a
                srl  a                      ; ... a pixel more every four
                inc  a
                cp   EN_DIE_VY_MAX + 1
                jr   c,.vy
                ld   a,EN_DIE_VY_MAX
.vy:            ; AND "OFF THE BOTTOM OF THE WORLD" IS THE MAP'S OWN
                ; HEIGHT NOW, not a byte's. It used to be the carry out
                ; of an 8-bit add, which is the same number only while a
                ; level is 16 rows; the map is 2,048 tiles of any
                ; power-of-two shape (mapshape.asm), the row count is a
                ; power of two of at least 16, so rows * 16 has a low
                ; byte of zero and the high byte is the whole comparison.
                add  a,(ix + ES_Y)
                ld   e,a
                ld   a,(ix + ES_Y + 1)
                adc  a,0
                ld   d,a                    ; DE = where it has fallen to
                ld   a,(SHAPE_NOW + SH_ROW_MASK)
                inc  a                      ; rows
                rrca
                rrca
                rrca
                rrca                        ; (rows * 16) >> 8
                cp   d
                jr   c,.gone                ; past the bottom of the map
                jr   z,.gone
                ld   (ix + ES_Y),e
                ld   (ix + ES_Y + 1),d
                jp   EBUL_UPDATE

.gone:          ld   (ix + ES_DIE),0        ; the refresh lifts it off next
                jp   EBUL_UPDATE

; ---------------------------------------------------------------------
; ENEMY_REFRESH - lift the enemy off the screen and put it back down
; where it is now. ONCE EVERY GAME FRAME, IN THE SLOT ENEMY_SLOT CHOSE:
; the top of the second sweep, or its end.
;
; THE ENEMY IS A PERSISTENT SPRITE AND SHE IS NOT. Hers is drawn and
; erased inside one game frame; the enemy's pixels are LEFT ON THE
; SCREEN from one refresh to the next, and are lifted off by the
; refresh that replaces them and by nothing else:
;
;   * while the picture scrolls they stay right for nothing, because
;     the CRTC moves every pixel on the screen and a world-fixed sprite
;     is supposed to move exactly that far;
;   * Kara's save-under captures them where she walks over it and her
;     erase puts them back, so a refresh that comes after her erase
;     needs nothing from her;
;   * the incoming column is the one thing that would disturb them, and
;     the window keeps the box two characters clear of both edges.
;
; AND IT IS REDRAWN ON EVERY GAME FRAME NOW, WHICH IT NEVER WAS. At the
; end of the sweep, after her erase, there was not room for a 19,000 T
; refresh on a frame the incoming column was painted in - measured,
; 82,000 to 84,500 T against 79,872 - so it was put off while the
; picture moved and taken on one game frame in two when it did not.
; What that looked like was the play-test's report: standing still, two
; bytes on one frame in two; walking, frozen for up to 34 bytes of its
; patrol and then all of them at once. Its first slot is the TOP of the
; sweep instead, in the border, ahead of the beam and in the 40,000 T
; the sweep used to spend waiting for interrupt tick 4 (ENEMY_SLOT).
;
; OUT: (ENEMY_LAST_CNT) lines drawn, 0 if none
;      (ENEMY_LAST_BOT) the lowest line it reached
;      (ENEMY_DREW)     non-zero while its pixels are on the screen
;      (ENEMY_ENG)      the one that is following her, from the first
;                       frame it was drawn
;      destroys AF,BC,DE,HL,IX,B',C'
; ---------------------------------------------------------------------
ENEMY_REFRESH:  ; LIFT THE LAST ONE OFF BEFORE PUTTING THIS ONE DOWN.
                ; This is the ONLY place its pixels ever come off the
                ; screen. Without it every refresh left the last image
                ; where it was and drew another one beside it - the enemy
                ; trailing copies of itself across the roof.
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
                call ENEMY_PLACE            ; where it is NOW: after its move
                                            ; and after the vertical latch
                ld   a,(ix + ES_HP)
                or   a
                jr   nz,.living
                ; DEAD AND STILL COMING DOWN: it flashes. The erase above
                ; has already lifted it off, so a refresh that draws
                ; nothing IS the dark half of the flash - four frames of
                ; the dying counter on and four off, for nothing.
                ld   a,(ix + ES_DIE)
                and  4
                ret  z
                jr   .shown
.living:        ld   a,(ENEMY_VIS)
                or   a
                ret  z                      ; near, but its box does not fit
                ; THE FIRST FRAME IT IS ON THE SCREEN IT STARTS TO FOLLOW
                ; HER, on the side of her it came in on, and from then on
                ; it is the one ENEMY_PICK takes until it is dead.
                ld   hl,(ENEMY_ENG)
                ld   a,h
                or   l
                jr   nz,.shown
                ld   (ENEMY_ENG),ix
                ld   l,(ix + ES_X)
                ld   h,(ix + ES_X + 1)
                srl  h
                rr   l
                call EN_HALF_W
                add  hl,de                  ; its middle, world bytes
                ld   de,(KARA_WX)
                or   a
                sbc  hl,de
                ld   de,KARA_BOX_W / 2
BX_EN_MID       equ  $ - 2
                or   a
                sbc  hl,de                  ; ... less hers
                ld   a,h
                rlca
                and  1                      ; negative: it is on her left
                ld   (ENEMY_SIDE),a

.shown:         ld   a,(ENEMY_VIS)
                or   a
                ret  z                      ; a dying one that has left it
                inc  a
                ld   (ENEMY_DREW),a         ; its pixels are on the screen now
                ld   a,(ENEMY_W)            ; ... in this box, which is what
                ld   (ENEMY_DREW_W),a       ; ENEMY_SLOT tests her against
                ld   a,(ENEMY_H)            ; next frame
                ld   (ENEMY_DREW_H),a
                ld   l,(ix + ES_X)
                ld   h,(ix + ES_X + 1)
                srl  h
                rr   l
                ld   (ENEMY_DREW_WX),hl
                ld   l,(ix + ES_Y)
                ld   h,(ix + ES_Y + 1)
                ld   (ENEMY_DREW_WY),hl

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
                                            ; (no HUD_CLIP: EN_YB keeps the
                                            ; whole box above the strip's
                                            ; rows, which is the stronger
                                            ; rule - see ENEMY_PLACE)
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
; ENEMY_SLOT - which slot of the second sweep ENEMY_REFRESH goes in.
; Call at the TOP of the second sweep, BEFORE SCROLL_VBLANK: every box
; it compares is in the view the first sweep drew in.
;
; THE TOP IS THE BORDER AND IT IS FREE. The sweep waits for interrupt
; tick 4 - 40,468 T - before the incoming column's head may go down
; (src/main.asm), and a refresh started straight after the latch is
; ahead of the beam for any box whose top is EN_EARLY_TOP or lower:
; the erase is a run of LDIs that outruns the beam, and the draw is
; about 650 T a line against the beam's 256, which the 60 lines of
; border above the picture pay for. Each place is then shown for this
; sweep and the next, exactly as her own is shown for the first and
; this one.
;
; BUT ANYTHING ON THE SCREEN THAT IS LIFTED OFF OR REPAINTED LATER IN
; THE SWEEP MUST NOT MEET IT, because a save-under taken before the
; drone moved is replayed after it: her own, over the drone's old box or
; its new one, and a taken pickup's cell, which is under her. Either
; puts it in the old slot, the END of the sweep, after both - where a
; frame that also paints the incoming column can run 2,000 to 4,600 T
; past the vblank and cost a hardware frame. An engaged one keeps
; EN_DIST from her give or take its sway, and never comes nearer than
; EN_MIN, which is exactly where the two boxes stop meeting
; (ENEMY_FOLLOW) - so for her that is the frames it is crossing to her
; other side and no others. The rounds cannot meet it at all:
; ENEMY_ZONE keeps them off it.
;
; AND ON A FRAME THE VIEW STEPS A ROW DOWN IT IS NEITHER: IT HOLDS. That
; frame's strip vacates the whole of row 22 - 35,000 T of HUD_SERVICE,
; the dearest thing it does (CLAUDE.md 7.8) - and with the refresh's
; 19,200 in front of it her erase's RASTER_WAIT is reached AFTER the
; tick it waits for. It cannot tell how far into that tick it is, so it
; waits the whole of the delay again from where it stands: measured down
; level 1's fall, her erase put off from 60,784 T to 72,232, the sweep
; ended at 85,132 of 79,872, and the game frame was three hardware ones.
; A drone that does not move needs no refresh - it is world-fixed and
; the latch carries its pixels exactly as far as the world goes - so on
; those frames it is not redrawn and ENEMY_MOVE does not move it: a
; game frame of standing still, at most one in three and only while the
; camera is going down, and nothing owed for the next draw to show at
; once. Its window keeps EN_VTOP and EN_VBOT of room for exactly one
; latch between where it was put and where it is drawn (ENEMY_FOLLOW).
;
; OUT: (ENEMY_EARLY) 1 for the top of the sweep, 0 for its end, EN_HOLD
;      for neither
;                                destroys AF,BC,DE,HL,IX
; ---------------------------------------------------------------------
EN_EARLY_TOP    equ 24          ; lines, in the view before the latch:
                                ; the refresh is done by about 22,500 T
                                ; and the beam reaches a drone's last line
                                ; at 15,376 + 256 * (top + 19) on the
                                ; emulator's model - the earlier of the
                                ; two - so its top has to be 9 or lower
                                ; on the screen, and the latch can still
                                ; take it up a row

EN_HOLD         equ 2           ; ENEMY_EARLY: not redrawn, not moved

ENEMY_SLOT:     ; HER BOX, AS SHE WAS DRAWN, in world units - FIRST,
                ; before the hold below can return, because the spike
                ; traps read it too (src/hazard.asm) and a frame the view
                ; steps a row down is a frame she is falling: a trap's
                ; cell under her has to be told from one that is not on
                ; exactly the frames this used to skip. It is worked out
                ; in the view she was drawn in, which is the one before
                ; SCROLL_VBLANK latches.
                ld   a,KARA_W_BYTES
BX_EN_KW        equ  $ - 1
                ld   (EN_KW),a
                ld   a,(KARA_LAST_CNT)
                ld   (EN_KH),a
                or   a
                jr   z,.hold                ; she was not drawn: nothing
                                            ; of hers to meet
                ld   a,(KARA_X)             ; SIGNED: the clipped lane's
                ld   l,a
                rlca
                sbc  a,a
                ld   h,a
                ld   a,(WORLD_X)
                ld   e,a
                ld   d,0
                add  hl,de
                add  hl,de                  ; + the view's left edge, bytes
                ld   (EN_KX),hl
                ld   a,(WORLD_CR)
                ld   l,a
                ld   h,0
                add  hl,hl
                add  hl,hl
                add  hl,hl
                ld   a,(KARA_LAST_TOP)
                ld   e,a
                ld   d,0
                add  hl,de
                ld   (EN_KY),hl
.hold:          ld   a,(V_PHASE)            ; does SCROLL_VBLANK latch a row
                cp   V_PARTS                ; step this sweep ...
                jr   nz,.slot
                ld   a,(WORLD_CR)
                ld   b,a
                ld   a,(V_WCR)
                cp   b
                jr   z,.slot
                jr   c,.slot                ; ... DOWN?
                ld   a,EN_HOLD
                ld   (ENEMY_EARLY),a
                ret
.slot:          xor  a
                ld   (ENEMY_EARLY),a        ; the end, unless all of it says
                                            ; the top
.new:           ; THE BOX IT WILL BE DRAWN IN
                ld   hl,(ENEMY_CUR)
                ld   a,h
                or   l
                jr   z,.old
                push hl
                pop  ix
                ld   a,(WORLD_CR)           ; is it low enough to be drawn
                ld   e,a                    ; ahead of the beam?
                ld   d,0
                ex   de,hl
                add  hl,hl
                add  hl,hl
                add  hl,hl
                ex   de,hl                  ; DE = the view's top
                ld   l,(ix + ES_Y)
                ld   h,(ix + ES_Y + 1)
                or   a
                sbc  hl,de                  ; its top, on the screen
                ld   a,h
                or   a
                jr   nz,.meet               ; off the picture: nothing to race
                ld   a,l
                cp   EN_EARLY_TOP
                ret  c                      ; too high: the end of the sweep
.meet:          ld   l,(ix + ES_X)
                ld   h,(ix + ES_X + 1)
                srl  h
                rr   l
                ld   a,(ENEMY_W)
                ld   b,a
                ld   e,(ix + ES_Y)
                ld   d,(ix + ES_Y + 1)
                ld   a,(ENEMY_H)
                ld   c,a
                call EN_MEETS
                ret  c
.old:           ld   a,(ENEMY_DREW)         ; ... and the box it is in now
                or   a
                jr   z,.early
                ld   hl,(ENEMY_DREW_WX)
                ld   a,(ENEMY_DREW_W)
                ld   b,a
                ld   de,(ENEMY_DREW_WY)
                ld   a,(ENEMY_DREW_H)
                ld   c,a
                call EN_MEETS
                ret  c
.early:         ld   a,1
                ld   (ENEMY_EARLY),a
                ret

; EN_MEETS - HL = a box's left in world bytes, B its width, DE its top
; in world lines, C its height. Carry set if it meets her box as she was
; drawn (ENEMY_SLOT worked that out) or the cell a taken pickup left
; behind, if one is due: that is repainted at the end of the sweep, so a
; drone drawn over it now would save the pickup as its background.
;
; THE CELL AND NOT HER BOX GROWN BY A TILE, WHICH IS WHAT IT WAS. She
; has just touched it, so her box grown a tile either way holds it - and
; also holds the bytes a drone keeping EN_DIST from her sways through,
; which put the refresh at the end of the sweep on the frame after every
; pickup: measured on test_enemies' walk past the roof's key, 91,840 T
; of a 79,872 T sweep, and one hardware frame with no heroine in it.
; ENT_SETTLE writes the cell's box beside ENT_RP_DUE (src/entity.asm).
;                                destroys AF,BC,DE,HL
EN_MEETS:       push hl
                push de
                push bc
                call EN_MEETS_HER
                pop  bc
                pop  de
                pop  hl
                ret  c
                push hl
                ld   hl,(ENT_RP_DUE)
                ld   a,h
                or   l                      ; clears the carry
                pop  hl
                ret  z                      ; no cell is due
                push bc
                push de
                ld   de,(ENT_RP_X)
                ld   c,TILE_W_BYTES
                call MEETS                  ; across
                pop  hl                     ; HL = its top
                pop  bc                     ; C = its height
                ret  nc
                ld   b,c
                ld   de,(ENT_RP_Y)
                ld   c,TILE_H
                jp   MEETS                  ; and down

; EN_MEETS_HER - the half of that which is her own box.
;                                destroys AF,BC,DE,HL
EN_MEETS_HER:   ld   a,(EN_KH)
                or   a
                ret  z                      ; she was not drawn: carry clear
                push de
                push bc
                ld   de,(EN_KX)
                ld   a,(EN_KW)
                ld   c,a
                call MEETS                  ; across
                pop  bc
                pop  de
                ret  nc
                ex   de,hl                  ; HL = its top
                ld   de,(EN_KY)
                ld   b,c                    ; B = its height
                ld   a,(EN_KH)
                ld   c,a                    ; C = hers
                jp   MEETS                  ; and down

; ---------------------------------------------------------------------
; MEETS - do [HL, HL + B) and [DE, DE + C) share anything? Sixteen-bit
; starts, byte lengths. Carry set if they do.   destroys AF,HL
; ---------------------------------------------------------------------
MEETS:          push de
                push hl
                ld   a,e                    ; DE = the second's end
                add  a,c
                ld   e,a
                jr   nc,.b
                inc  d
.b:             or   a
                sbc  hl,de                  ; the first's start less that:
                pop  hl                     ; it has to be negative
                pop  de
                ret  nc                     ; apart, carry clear
                push de
                ld   a,l                    ; HL = the first's end
                add  a,b
                ld   l,a
                jr   nc,.a
                inc  h
.a:             ex   de,hl                  ; HL = the second's start
                or   a
                sbc  hl,de                  ; ... less the first's end:
                pop  de                     ; negative is a meeting
                ret

ENEMY_REFRESH_EARLY:
                ld   a,(ENEMY_EARLY)
                dec  a
                ret  nz                     ; the end of the sweep, or held
                jp   ENEMY_REFRESH

ENEMY_REFRESH_LATE:
                ld   a,(ENEMY_EARLY)
                or   a
                ret  nz
                jp   ENEMY_REFRESH

; ---------------------------------------------------------------------
; ENEMY_PICK_NEXT - ENEMY_PICK for the NEXT game frame, in the second
; sweep of this one (src/main.asm), in the view that frame will be drawn
; in.
;
; IT WAS THE TOP OF THE FIRST SWEEP, AND 1,372 T THERE IS WHAT THAT
; SWEEP HAS NOT GOT. Running left with a drone behind her - the run's
; heaviest cel, the strip's step LEFT and its rounds in the air - the
; first sweep measured 79,780 T of 79,872 with ENEMY_THINK already gone
; to the second (above): a frame that holds by 92 T is a frame that
; does not, the day anything moves. It is in the second sweep's wait
; for its head gate, straight after the follow has moved the drone -
; and NOT at that sweep's end, which was tried first: on the street her
; erase ends at 76,400 T and this took the sweep past the vblank.
;
; AND THE VIEW IS THE ONE H_COMMIT IS ABOUT TO LATCH, so nothing it
; leaves is a frame out. The vertical latch is already behind it, at the
; top of this sweep; a horizontal step that is pending is swapped in
; around the call, exactly as H_HEAD swaps it in around its paint
; (src/tilemap.asm). Every number it leaves - the slot, its screen box,
; the rounds' keep-out - is the one ENEMY_PICK worked out straight after
; H_COMMIT when it was called there.
;                                destroys AF,BC,DE,HL,IX
; ---------------------------------------------------------------------
ENEMY_PICK_NEXT:
                ld   a,(H_PENDING)
                or   a
                jp   z,ENEMY_PICK
                ld   a,(WORLD_X)
                push af
                ld   a,(H_WX)
                ld   (WORLD_X),a
                call ENEMY_PICK
                pop  af
                ld   (WORLD_X),a
                ret

; ---------------------------------------------------------------------
; ENEMY_THINK - ENEMY_UPDATE, in the time the second sweep spends
; waiting for its head gate (src/main.asm).
;
; IT WAS THE FIRST SWEEP'S LOGIC AND THAT SWEEP HAD NOTHING TO SPARE FOR
; IT. A drone that follows her is always near and always firing, so its
; sight, its gun, its cels and the flight of its rounds are paid on
; every frame of the level now - and the first sweep is where her
; heaviest cel, the strip's step LEFT and its own rounds already are.
; Measured running left with one behind her: 82,092 T of a 79,872 T
; sweep, six game frames in 150 that took three hardware frames, and
; none at all with the level's drones off. Here it is about 2,300 T of
; the 16,000 the sweep would otherwise spend doing nothing.
;
; NOTHING IT TOUCHES IS STILL IN USE BY THEN. Its rounds come off the
; screen by the addresses their draw saved (EBUL_ERASE), so moving them
; before the erase moves nothing that is lifted off; and its gun spawns
; a round at ENEMY_SX/ENEMY_SY, which the refresh has just placed in the
; view as latched - and which, on a frame the refresh is put off to the
; end of the sweep or held (ENEMY_SLOT), are placed here instead, so
; that a row step between ENEMY_PICK and this is not a round eight lines
; from the muzzle.
;                                destroys AF,BC,DE,HL,IX
; ---------------------------------------------------------------------
ENEMY_THINK:    ld   a,(ENEMY_EARLY)
                dec  a
                jp   z,ENEMY_UPDATE         ; placed by the refresh already
                ld   hl,(ENEMY_CUR)
                ld   a,h
                or   l
                jp   z,ENEMY_UPDATE
                push hl
                pop  ix
                call ENEMY_PLACE
                jp   ENEMY_UPDATE

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
                ld   a,(ZONE_XW)            ; out of its own gun, and not
                or   a                      ; yet clear of its box - and as
                ld   a,(hl)                 ; cheap as BUL_DRAW's when there
                call nz,ROUND_HIDDEN        ; is no zone
                jr   c,.hidden
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
.hidden:        pop  hl
                pop  bc
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
ENEMY_SXH:      db 0            ; ... and its high byte: 0 is this view
ENEMY_SY:       dw 0            ; signed: see ENEMY_PICK
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
ENEMY_DREW_WY:  dw 0            ; ... at this world line, this tall
ENEMY_DREW_H:   db 0
ENEMY_ENG:      dw 0            ; the one following her, 0 for none
ENEMY_SIDE:     db 0            ; ... and which side of her: 0 right, 1 left
ENEMY_EARLY:    db 0            ; 1: refreshed at the top of the second
                                ; sweep, 0: at its end (ENEMY_SLOT)
ZONE_X0:        db 0            ; where a round may not be drawn: the
ZONE_XW:        db 0            ; columns X0 .. X0 + XW - 1, 0 wide for
ZONE_Y0:        db 0            ; none, and the lines Y0 .. Y0 + YH - 1
ZONE_YH:        db 0            ; (ENEMY_ZONE)
EN_KX:          dw 0            ; her box as she was drawn, world bytes
EN_KY:          dw 0            ; ... and world lines,
EN_KH:          db 0            ; ... this tall, 0 if she was not,
EN_KW:          db 0            ; ... and this wide
EN_HERMID:      dw 0            ; ENEMY_FOLLOW's: her middle, and the place
EN_TGT:         dw 0            ; it is making for
ENEMIES:        ds ENEMY_MAX * ES_STRIDE
EBULLETS:       ds EBUL_MAX * EBUL_STRIDE
