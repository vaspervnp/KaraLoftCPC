; =====================================================================
; player.asm - Kara's movement                             (MODULE 5)
;
; Coordinates are WORLD coordinates, and the two axes use different
; units on purpose:
;
;   KARA_WX  world byte column, 0-511   1 unit = 2 Mode 0 pixels
;   KARA_WY  world pixel row,   0-255   the box's TOP line
;
; BOTH ARE THE COLLISION BOX, NOT THE SPRITE. The sprite is 12 bytes
; wide and the box 6, and the box is centred in it: PLAYER_TO_SCREEN
; takes KARA_ART_X off once a frame and everything else - the probes
; here, the AABB in entity.asm, the enemy's sight line - reads her body's
; own edges with no arithmetic at all. See the note by KARA_BOX_W in
; collide.asm for what this was before and what it cost.
;
; X is byte-granular because the blitter is, and because the map column
; is then a shift rather than a divide. Y is a single byte, which wraps
; with the 256-pixel-tall map and makes every comparison 8-bit.
;
; The two axes are resolved SEPARATELY, X first. A combined test cannot
; tell a wall from a floor - the same probe coming back solid means
; "refuse the step" horizontally and "land" vertically.
;
; Both axes share ONE bank switch. BANK_SET_C4/BANK_RESTORE costs 116 T
; against a ~220 T probe, so paging per probe would nearly double the
; cost of the whole routine.
;
; WALKING AND SCROLLING DO NOT SHARE A STEP SIZE, AND THAT IS A BUG
; UNLESS IT IS HANDLED. The CRTC scrolls in whole characters, 2 bytes,
; and Kara walks 1 byte a frame, so inside the push zone at either
; screen edge CAMERA_DECIDE can only fire every other frame. Let her
; keep walking 1 byte a frame there and her SCREEN column - the one the
; blitter draws at - goes 54, 55, 54, 55 ... at 25 Hz: every frame is
; drawn and erased correctly, every RAM check passes, and on a monitor
; there are two Karas a character apart for as long as the screen
; moves. So in the push zone she moves the way the camera does: P_PUSH
; bytes on the camera's frame, nothing on the frame between, and her
; screen column never changes while the world goes by. Mid-screen she
; still walks 1 byte at 50 Hz.
; =====================================================================

P_WALK          equ 1           ; byte columns per frame = 2 pixels
P_RUN           equ 2           ; SHIFT: one CRTC character a frame
P_PUSH          equ 2           ; bytes per camera step: one CRTC character
P_GRAVITY       equ 1
P_VY_MAX        equ 8           ; MUST stay under one tile (16) - a
                                ; destination-only probe is only exact
                                ; while a single step cannot skip a tile
P_JUMP          equ -8          ; rises 8+7+...+1 = 36 px, about 2.2 tiles
P_CLIMB         equ 1           ; pixels a frame on a ladder. The vertical
                                ; scroll moves 8 lines every THREE frames,
                                ; so anything faster than 2 outruns the
                                ; camera and she walks off the bottom of
                                ; the display while it catches up.
WORLD_W         equ MAP_W * TILE_W_BYTES    ; 128 tiles of 4 = 512 bytes,
                                ; the same world the 64x16 map covered

; ---------------------------------------------------------------------
; PLAYER_UPDATE - one frame of movement.
;
; Reads (INPUT_NOW) and (INPUT_PRESSED); writes KARA_WX, KARA_WY,
; KARA_VY, KARA_GROUND, KARA_FACING. No paging: see below.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
                ; NO BANK SWITCH. The map is in base RAM since the 8x16
                ; art filled C4 (tilemap.asm), so the probes read it
                ; wherever the window happens to be pointing - and the
                ; 116 T this used to cost goes back to the frame.
                ; SHE IS STILL WHILE SHE TURNS TO THE LADDER. The cel
                ; is drawn standing on the ground (CLAUDE.md 7.1), so
                ; sliding it up a shaft or walking it along a street
                ; would show a figure with its feet in the wrong place
                ; for as long as it is up. Committed in action.asm, held
                ; here: the two have to agree or she moves under a cel
                ; that says she is not moving.
PLAYER_UPDATE:  ld   a,(KARA_STATE)
                cp   KST_CLIMB_TURN
                ret  z
                ; AND SHE TAKES NO INPUT ONCE SHE IS DEAD, but gravity
                ; still owns her: the die cels are drawn standing on the
                ; ground and settling onto it, so she has to reach it.
                ; The body's own movement is inside the frames - nothing
                ; here may move her while they play.
                cp   KST_DIE
                jr   z,.dead

                ld   a,(KARA_CLIMB)
                or   a
                jp   nz,PLAYER_CLIMB        ; a ladder suspends both of them

                call PLAYER_X
                ; A LADDER BEATS A JUMP, so the grab is tested before
                ; PLAYER_Y and not after it. UP is the jump key as well,
                ; and a grab tested afterwards reads a KARA_GROUND that
                ; the jump has already cleared: standing at the foot of a
                ; ladder and holding UP hopped on the spot for ever.
                call CLIMB_ENTER
                ld   a,(KARA_CLIMB)
                or   a
                ret  nz
                jp   PLAYER_Y

.dead:          xor  a
                ld   (KARA_CLIMB),a         ; a ladder does not hold a body
                jp   PLAYER_Y

; ---------------------------------------------------------------------
; PLAYER_X - propose a step, probe the LEADING edge, refuse the whole
; step if it is blocked.
;
; Only the leading edge is probed: the trailing edge is somewhere she is
; already standing, so it cannot have become solid. Refusing the whole
; step rather than sliding to the wall costs at most one byte of gap and
; avoids a second probe to find where exactly she should stop.
; ---------------------------------------------------------------------
                ; NO ANIMATION HERE. Which cel shows is action.asm's
                ; business and it is decided AFTER the physics, because
                ; the jump state reads KARA_GROUND. This routine settles
                ; where she is and which way she faces; that is all the
                ; state machine needs from it.
PLAYER_X:       ld   a,(INPUT_NOW)
                ld   c,a
                and  IN_LEFT + IN_RIGHT
                ret  z                      ; nothing held: she stays put

                ; SHIFT is two bytes a frame, which is exactly the
                ; CRTC's scroll step - so in the camera's push zone a
                ; run scrolls every frame and a walk every other one.
                ld   a,c
                and  IN_RUN
                ld   a,P_WALK
                jr   z,.speed
                ld   a,P_RUN
.speed:         ld   (PLAYER_SPEED),a
                ld   a,c
                and  IN_LEFT
                jr   nz,.left

                ; ---- right: leading edge is the box's right side ----
                xor  a
                ld   (KARA_FACING),a        ; 0 = right
                call PLAYER_SCREEN_X
                inc  a                      ; her screen column after 1 byte
                sub  CAM_TRAIL              ; how far past the mark - and it
                cp   CAM_BAND               ; underflows to 255 short of it,
                ld   a,(PLAYER_SPEED)       ; which reads as "not at the mark"
                ld   e,a                    ; exactly as it should
                jr   nc,.step_r             ; free, or panning: walk normally
                ld   a,(WORLD_X)
                cp   WORLD_W / 2 - SCR_CHARS
                jr   nc,.step_r             ; camera at the map's end: walk on
                ld   a,(PLAYER_SPEED)
                cp   P_RUN
                jr   z,.push_r              ; running: the camera steps every
                call PUSH_PHASE             ; frame, so she may too
                ret  z                      ; walking, the camera's off frame
.push_r:        ld   e,P_PUSH               ; its on frame: move as far as it
.step_r:        ld   d,0
                ld   hl,(KARA_WX)
                add  hl,de                  ; the proposed position
                ld   de,WORLD_W - KARA_W_BYTES + KARA_ART_X
                or   a
                sbc  hl,de                  ; past the world's right edge?
                add  hl,de
                jr   c,.probe_r
                ex   de,hl                  ; ... then stop exactly on it
                ; The bound is on her SPRITE, not her collision box, and
                ; that is what keeps her whole on screen - which is why
                ; KARA_ART_X is added back on: KARA_WX is the box now, and
                ; the sprite starts that many bytes to the left of it.
                ; WORLD_X stops at 216 characters = 432 bytes, so the last
                ; byte her sprite reaches is the last one the display
                ; has. A box-width bound would let her reach byte 76, where
                ; the blitter has to clip - which is correct (see
                ; sprite.asm) but costs 34,412 T against 30,624, and a
                ; 48-line sprite that slow loses the raster from screen
                ; line 28 upward. Stopping her four bytes earlier is eight
                ; pixels of level nobody can see the edge of.
.probe_r:       push hl
                ld   de,KARA_BOX_W - 1
                add  hl,de                  ; ... and its leading edge
                ld   a,(KARA_WY)
                call BOX_SOLID_H
                pop  hl
                ret  nz                     ; blocked - the step is refused
                ld   (KARA_WX),hl
                ret

.left:          ld   a,1
                ld   (KARA_FACING),a        ; 1 = left
                call PLAYER_SCREEN_X
                dec  a                      ; her screen column after 1 byte
                ld   c,a
                ld   a,CAM_LEAD
                sub  c                      ; how far short of the mark
                cp   CAM_BAND
                ld   a,(PLAYER_SPEED)
                ld   e,a
                jr   nc,.step_l             ; free, or panning: walk normally
                ld   a,(WORLD_X)
                or   a
                jr   z,.step_l              ; camera at the map's start
                ld   a,(PLAYER_SPEED)
                cp   P_RUN
                jr   z,.push_l
                call PUSH_PHASE
                ret  z
.push_l:        ld   e,P_PUSH
.step_l:        ld   d,0
                ld   hl,(KARA_WX)
                or   a
                sbc  hl,de                  ; the proposed position IS the
                jr   c,.edge_l              ; leading edge
                ld   a,h                    ; ... and KARA_ART_X is as far as
                or   a                      ; it goes, not 0: KARA_WX is her
                jr   nz,.probe_l            ; BOX and her sprite starts that
                ld   a,l                    ; many bytes to the LEFT of it, so
                cp   KARA_ART_X             ; a box at 0 puts the sprite at -3
                jr   nc,.probe_l            ; - KARA_X comes back 253 and the
.edge_l:        ld   hl,KARA_ART_X          ; blitter culls her.
                                            ; Without a bound at all she walks
                                            ; off the left of the world:
                                            ; KARA_WX wraps
                                            ; to 65535, PLAYER_SCREEN_X reads a
                                            ; huge column, and CAMERA_DECIDE
                                            ; then scrolls RIGHT while she walks
                                            ; left. The map wraps with an AND,
                                            ; so there is no edge tile to stop
                                            ; her - the bound has to be here.
.probe_l:       ld   a,(KARA_WY)
                push hl
                call BOX_SOLID_H
                pop  hl
                ret  nz
                ld   (KARA_WX),hl
                ret

; ---------------------------------------------------------------------
; PUSH_PHASE - Z on the frames the camera sits still.
;
; The camera is decided at the top of the NEXT frame from the position
; this frame leaves behind, so "the frame she moves P_PUSH" and "the
; frame the camera steps" are one frame apart, and the parity of
; FRAME_COUNT (incremented right after PLAYER_UPDATE) is a clock both
; halves agree on.                       destroys AF
; ---------------------------------------------------------------------
PUSH_PHASE:     ld   a,(FRAME_COUNT)
                and  1
                ret

; ---------------------------------------------------------------------
; PLAYER_Y - jump, gravity, and landing.
;
; Rising probes the box's TOP line against TA_SOLID; falling probes the
; line just past its FEET against TA_BLOCK, so a one-way platform stops
; a descent but never a climb.
; ---------------------------------------------------------------------
PLAYER_Y:       ld   a,(KARA_GROUND)
                or   a
                jr   z,.airborne

                ; ---- standing ----------------------------------------
                ld   a,(INPUT_PRESSED)      ; edge-triggered, not level: a
                and  IN_UP                  ; held key must not re-jump
                jr   nz,.jump

                ; Still supported? Probed at feet + 1, NOT at the feet
                ; line. Probing the feet line makes GROUNDED blink two
                ; frames in three, and because the jump is edge-triggered
                ; that swallows two jump presses out of every three.
                ld   a,(KARA_WY)
                add  a,KARA_BOX_H
                ld   hl,(KARA_WX)
                ld   b,TA_BLOCK
                call BOX_SOLID_V
                ret  nz                     ; still on something
                xor  a
                ld   (KARA_GROUND),a        ; walked off an edge - which is
                ld   (KARA_VY),a            ; a DROP and not a jump, and this
                inc  a                      ; is the one place the two part
                ld   (KARA_FELL),a          ; company (action.asm)
                ret

.jump:          ld   a,P_JUMP
                ld   (KARA_VY),a
                xor  a
                ld   (KARA_GROUND),a
                ld   (KARA_FELL),a          ; she chose this one
                                            ; fall through, so the jump moves
                                            ; her on the frame it is pressed

; ---- airborne --------------------------------------------------------
.airborne:      ld   a,(KARA_VY)
                add  a,P_GRAVITY
                bit  7,a                    ; CP is UNSIGNED, so a rising
                jr   nz,.store_vy           ; velocity of -7 (&F9 = 249) tests
                cp   P_VY_MAX + 1           ; as >= 9 and would be clamped to
                jr   c,.store_vy            ; +8 - she would fall at terminal
                ld   a,P_VY_MAX             ; velocity the instant she jumped.
.store_vy:      ld   (KARA_VY),a            ; Test the sign bit first.

                ld   b,a                    ; B = velocity
                ld   a,(KARA_WY)
                add  a,b                    ; the proposed top line
                ld   c,a
                bit  7,b
                jr   nz,.rising

                ; ---- falling: probe just past her feet ---------------
                add  a,KARA_BOX_H
                ld   hl,(KARA_WX)
                ld   b,TA_BLOCK             ; a one-way platform blocks this
                push bc
                call BOX_SOLID_V
                pop  bc
                jr   nz,.land
                ld   a,c
                ld   (KARA_WY),a
                ret

.land:          ; Snap her feet ONTO the tile rather than into it: the
                ; blocking tile's top pixel row is (footY AND &F0), and the
                ; box's last line must be the row above it.
                ld   a,c
                add  a,KARA_BOX_H
                and  &F0
                sub  KARA_BOX_H
                ld   (KARA_WY),a
                xor  a
                ld   (KARA_VY),a
                ld   (KARA_FELL),a
                inc  a
                ld   (KARA_GROUND),a
                ret

                ; ---- rising: probe the top line ---------------------
.rising:        ld   hl,(KARA_WX)
                ld   b,TA_SOLID             ; a platform is climbed through
                ld   a,c
                push bc
                call BOX_SOLID_V
                pop  bc
                jr   nz,.bump
                ld   a,c
                ld   (KARA_WY),a
                ret

.bump:          xor  a                      ; head hit - cancel the rest of
                ld   (KARA_VY),a            ; the climb, gravity takes over
                ret

; =====================================================================
; THE LADDER
;
; A ladder is a column of TA_CLIMB tiles cut through the wall, and its
; TOP tile sits in the roof's own row so that she can stand on it: it
; carries TA_PLATFORM as well, which is a floor from above and nothing
; from below (collide.asm).
;
;   DOWN, standing on a climb tile        -> she steps onto the ladder
;   UP,   standing with one over her head -> she steps onto the ladder
;   UP/DOWN on it                         -> P_CLIMB pixels, no gravity
;   past the last rung, either end        -> she is put on the floor
;
; EVERY PROBE HERE IS ONE COLUMN WIDE. Her box is three tiles across and
; the shaft is one, so the box probes read the brick either side of it
; and come back solid everywhere: CLIMB_AT asks about the single column
; she is centred on, and CLIMB_GRAB is what centres her.
;
; LEFT and RIGHT do nothing while she is on it. That is not laziness -
; PLAYER_X's push-zone logic moves her in lock step with the camera, and
; a step sideways out of the shaft would leave her standing in a wall.
; =====================================================================

; ---------------------------------------------------------------------
; CLIMB_ENTER - grab a ladder if she is asking for one.
;
; Called with KARA_GROUND as PLAYER_Y left it LAST frame, before this
; frame's jump has had a chance to clear it.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
CLIMB_ENTER:    ld   a,(KARA_GROUND)
                or   a
                ret  z                      ; only from a floor
                ld   a,(INPUT_NOW)
                ld   c,a
                and  IN_DOWN
                jr   z,.try_up

                ; DOWN: the tile she is STANDING ON. Her feet line is
                ; that tile's top line, so this is the tile itself and
                ; not the one below it.
                ld   a,(KARA_WY)
                add  a,KARA_BOX_H
                call CLIMB_AT
                and  TA_CLIMB
                jr   nz,CLIMB_GRAB
                ret

.try_up:        ld   a,c
                and  IN_UP
                ret  z
                ; UP: the tile directly ABOVE the floor she is on - one
                ; line higher is inside it, whatever her feet are on.
                ld   a,(KARA_WY)
                add  a,KARA_BOX_H
                dec  a
                call CLIMB_AT
                and  TA_CLIMB
                ret  z
                ; fall through

; ---------------------------------------------------------------------
; CLIMB_GRAB - put her ON the shaft and hand her to PLAYER_CLIMB.
;
; The shaft is TILE_W_BYTES wide and her box KARA_BOX_W, so "centred"
; puts the box's left edge one byte to the left of the tile's - and
; CLIMB_AT, which probes the same middle byte, then reads the shaft she
; is on. Her sprite follows, because the sprite is centred on the box.
;                                destroys AF,DE,HL
; ---------------------------------------------------------------------
CLIMB_GRAB:     ld   hl,(KARA_WX)
                ld   de,KARA_BOX_W / 2
                add  hl,de                  ; the byte her middle is over
                ld   a,l
                and  256 - TILE_W_BYTES     ; ... and its tile's left edge.
                ld   l,a                    ; H is untouched: TILE_W_BYTES
                                            ; divides 256, so the mask cannot
                                            ; borrow out of the low byte
                ld   de,TILE_W_BYTES / 2 - KARA_BOX_W / 2   ; -1
                add  hl,de
                ld   (KARA_WX),hl
                xor  a
                ld   (KARA_VY),a
                ld   (KARA_GROUND),a
                inc  a
                ld   (KARA_CLIMB),a
                jr   CLIMB_TURN_START       ; ... and turn to face it

; ---------------------------------------------------------------------
; CLIMB_TURN_START - play the one cel of her turning to the ladder.
;
; `climb` is a BACK view and idle, walk and hang are all side on, so
; there is no cut from one to the other that does not read as her
; spinning on the spot. The art has a single cel for it, and this is the
; whole of playing it: the same five stores ACT_UPDATE's own .want makes
; when a state changes, written from here because nothing action.asm can
; see distinguishes the frame she grabs a ladder from the frame after.
;
; KST_CLIMB_TURN is COMMITTED, so ACT_UPDATE will hold it for the cel's
; own duration and then re-decide - which lands on CLIMB or HANG going
; up, and on IDLE or WALK coming off.
;                                destroys AF
; ---------------------------------------------------------------------
CLIMB_TURN_START:
                ld   a,KST_CLIMB_TURN
                ld   (KARA_STATE),a
                xor  a
                ld   (KARA_DONE),a
                dec  a                      ; 255: ACT_ANIMATE steps in the
                ld   (KARA_ANIM),a          ; same call, so a state entered
                ld   a,1                    ; at cel 0 shows its SECOND cel
                ld   (KARA_TIMER),a         ; first - see action.asm
                ret

; ---------------------------------------------------------------------
; CLIMB_TURN_OFF - the same cel, coming off the ladder onto a floor,
; mirrored the way she is LEAVING.
;
; She has been facing whichever way she walked up to the shaft, and the
; cel is side on, so the direction she is holding at the moment she
; steps off is the one that reads right. Nothing is held: she keeps the
; facing she arrived with.
;                                destroys AF,BC
; ---------------------------------------------------------------------
CLIMB_TURN_OFF: ld   a,(INPUT_NOW)
                ld   c,a
                and  IN_LEFT
                jr   z,.not_left
                ld   a,1
                ld   (KARA_FACING),a
                jr   CLIMB_TURN_START
.not_left:      ld   a,c
                and  IN_RIGHT
                jr   z,CLIMB_TURN_START
                xor  a
                ld   (KARA_FACING),a
                jr   CLIMB_TURN_START

; ---------------------------------------------------------------------
; PLAYER_CLIMB - one frame on a ladder.
;
; C holds the feet line she is proposing and B the attributes of the
; tile it lands in, which is why CLIMB_AT preserves BC.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
PLAYER_CLIMB:   ld   a,(INPUT_NOW)
                ld   c,a
                and  IN_UP
                jr   nz,.up
                ld   a,c
                and  IN_DOWN
                ret  z                      ; hanging on, going nowhere

                ; ---- down ------------------------------------------
                ld   a,(KARA_WY)
                add  a,KARA_BOX_H + P_CLIMB ; her feet, after the step
                ld   c,a
                call CLIMB_AT
                ld   b,a
                and  TA_CLIMB
                jr   z,.off_bottom
                ld   a,(KARA_WY)
                add  a,P_CLIMB
                ld   (KARA_WY),a
                ret

                ; Past the last rung. If there is a floor under it she
                ; stands on it; if there is not, she lets go and falls -
                ; a ladder that ends in mid-air must not leave her
                ; standing on nothing.
.off_bottom:    ld   a,b
                and  TA_BLOCK
                jr   z,.let_go
                ld   a,c
                and  &F0                    ; the floor is that tile's top line
                sub  KARA_BOX_H
                ld   (KARA_WY),a
                jr   CLIMB_LAND
.let_go:        ld   a,c
                sub  KARA_BOX_H
                ld   (KARA_WY),a
                jr   CLIMB_LEAVE

                ; ---- up --------------------------------------------
.up:            ld   a,(KARA_WY)
                add  a,KARA_BOX_H - P_CLIMB
                ld   c,a
                call CLIMB_AT
                and  TA_CLIMB
                jr   z,.off_top
                ld   a,(KARA_WY)
                sub  P_CLIMB
                ld   (KARA_WY),a
                ret

                ; Off the top: her feet are in the tile ABOVE the shaft,
                ; so the floor is that tile's BOTTOM - which is the top
                ; line of the last rung's tile, 16 on from the mask.
.off_top:       ld   a,c
                and  &F0
                add  a,16
                sub  KARA_BOX_H
                ld   (KARA_WY),a
                ; fall through

                ; SHE ARRIVED ON A FLOOR, so she turns off the ladder
                ; the way she turned onto it. CLIMB_LEAVE below does not:
                ; that is the ladder ending in mid-air, and what follows
                ; is a fall, which is a JUMP and not a turn.
CLIMB_LAND:     xor  a
                ld   (KARA_CLIMB),a
                ld   (KARA_VY),a
                ld   (KARA_FELL),a
                inc  a
                ld   (KARA_GROUND),a
                jp   CLIMB_TURN_OFF

                ; LETTING GO IS A DROP, not a jump: the ladder ended in
                ; mid-air and what follows is a fall she did not choose.
CLIMB_LEAVE:    xor  a
                ld   (KARA_CLIMB),a
                ld   (KARA_VY),a
                ld   (KARA_GROUND),a
                inc  a
                ld   (KARA_FELL),a
                ret

; ---------------------------------------------------------------------
; CAMERA_DECIDE - Kara drives the scroll engine, one frame ahead.
;
; Runs right after PLAYER_UPDATE and only REQUESTS a step: the column
; is painted behind the beam later this frame (H_HEAD) and the CRTC is
; given the new address at the next VSYNC (H_COMMIT). So the frame that
; shows the step also shows Kara drawn from PLAYER_TO_SCREEN below,
; which resolves her against that same pending view.
;
; It refuses while a vertical step is in flight. Both axes hold a
; PENDING start address worked out from the one on screen when the step
; was asked for, and a step on the other axis in between makes that
; stale by a whole character row: the view jumps 40 words while the map
; cursor does not, and the picture and the tilemap disagree from then
; on. No level scrolls both ways (CLAUDE.md 8.1), so the guard costs a
; frame of delay in a case the game never reaches.
;                                destroys AF,HL
; ---------------------------------------------------------------------
; ---------------------------------------------------------------------
; THE CAMERA KEEPS HER BEHIND THE MIDDLE OF WHERE SHE IS GOING.
;
; One fixed column cannot do that in both directions, so the mark moves
; with her facing: walking right she rides at CAM_TRAIL and the 50
; bytes of level in front of her are the ones on screen; walking left
; she rides at CAM_LEAD, its mirror, and the 50 bytes are behind her.
; It used to be a static zone of 16..56, which meant walking right she
; sat at column 56 with 18 bytes of warning.
;
; TURNING ROUND THEREFORE PANS. She is 26 bytes from the new mark, the
; camera scrolls a whole character every frame until she reaches it and
; she keeps walking her own byte, so she drifts across the screen at 1
; byte a frame and arrives in 26. A pan is exactly a run's frame cost -
; a column every frame - which CLAUDE.md 9 already measures as locked.
;
; CAM_BAND is what tells "the camera is following her" from "the camera
; is panning to catch up", and only the first gets the lock-step of
; P_PUSH below. Without it she would freeze at whatever column she
; turned round on and the camera would pan for ever.
; ---------------------------------------------------------------------
; PLAYER_SCREEN_X returns her BOX's screen column, so these are in box
; columns - and the mirror below is then exactly right, which it was not
; while CAM_TRAIL was a sprite column and KARA_BOX_W a box width. At
; CAM_TRAIL = 27 her sprite's left edge is 24 and 44 bytes of level are
; in front of her; at CAM_LEAD = 47 her sprite's right edge is 55 and
; the same 44 bytes are in front of her the other way.
CAM_TRAIL       equ 27          ; her box's column while she walks RIGHT
CAM_LEAD        equ SCR_CHARS * 2 - CAM_TRAIL - KARA_BOX_W   ; 47, its mirror
CAM_BAND        equ 4           ; within this of the mark, she is pushing it
                                ; and not drifting toward it

CAM_TOP         equ 64          ; the band her screen line has to stay in
CAM_BOT         equ 112         ; before the view follows her down or up
V_CR_MAX        equ (MAP_H * 16 - SCR_CHAR_ROWS * 8) / 8

CAMERA_DECIDE:  ld   a,(V_PHASE)            ; never both axes at once - see
                or   a                      ; SCROLL_SERVICE in tilemap.asm
                ret  nz
                call CAMERA_V
                ret  nz                     ; it asked for one: the horizontal
                                            ; camera stands down this frame
                ; WHICH WAY SHE FACES DECIDES WHICH WAY THE CAMERA CAN
                ; GO. A single pair of thresholds would have to overlap
                ; to put her behind the middle in both directions, and
                ; then standing still between them would scroll both
                ; ways on alternate frames.
                ld   a,(KARA_FACING)
                or   a
                jr   nz,.facing_left
                call PLAYER_SCREEN_X        ; A = screen byte column
                cp   CAM_TRAIL
                ret  c                      ; behind the mark: let her walk up
                ld   a,(WORLD_X)
                cp   WORLD_W / 2 - SCR_CHARS
                ret  nc                     ; at the right edge of the map
                jp   H_REQUEST_RIGHT

.facing_left:   call PLAYER_SCREEN_X
                cp   CAM_LEAD
                ret  nc                     ; ahead of the mark: let her walk
                ld   a,(WORLD_X)
                or   a
                ret  z                      ; at the left edge of the map
                jp   H_REQUEST_LEFT

; ---------------------------------------------------------------------
; CAMERA_V - follow her down the building, and back up it.
;
; The display is 192 lines of a 256-line world, so the view's top can
; only sit in 0..V_CR_MAX character rows - 0 to 64 pixels. That is the
; whole vertical budget and the level spends it: the roof is framed with
; the view at 0 and the street needs it at its limit, so climbing down
; the ladder IS the vertical scroll, not a thing that happens near it.
;
; ONE STEP AT A TIME, AND ONLY WHEN THE LAST HAS LANDED. A vertical step
; takes three frames (tilemap.asm) and a second request inside that
; window would be worked out from a start address the CRTC has not been
; given yet. V_REQUEST is the queue, and it is one deep.
;
; OUT: NZ if a step was requested, Z if not.  destroys AF,DE,HL
; ---------------------------------------------------------------------
CAMERA_V:       ld   a,(V_REQUEST)
                or   a
                ret  nz                     ; one is already waiting
                ld   a,(WORLD_CR)
                add  a,a
                add  a,a
                add  a,a                    ; the view's top, in lines
                ld   e,a
                ld   a,(KARA_WY)
                add  a,KARA_BOX_H / 2       ; HER MIDDLE, not the top of her
                                            ; box: measured from her head the
                                            ; band has to sit 30 lines higher
                                            ; to frame her, and the view then
                                            ; stops one character row short of
                                            ; its limit with the road half off
                                            ; the bottom of the display
                sub  e                      ; her screen line
                jr   c,.up                  ; above the view entirely
                cp   CAM_BOT + 1
                jr   nc,.down
                cp   CAM_TOP
                jr   c,.up
                xor  a                      ; inside the band: nothing to do
                ret

.down:          ld   a,(WORLD_CR)
                cp   V_CR_MAX
                jr   nc,.none               ; the world's bottom is on screen
                ld   a,1                    ; 1 = down the map
                ld   (V_REQUEST),a
                ret                         ; NZ

.up:            ld   a,(WORLD_CR)
                or   a
                jr   z,.none                ; the world's top is on screen
                ld   a,2                    ; 2 = up the map
                ld   (V_REQUEST),a
                ret                         ; NZ

.none:          xor  a
                ret

; PLAYER_SCREEN_X - A = her BOX's screen byte column (KARA_WX -
; WORLD_X * 2) in the view that is on screen NOW. This is what the
; physics and the camera reason about; the sprite's column is
; KARA_ART_X less, and only PLAYER_TO_SCREEN wants that.
;                                    destroys AF,DE,HL
PLAYER_SCREEN_X:
                ld   a,(WORLD_X)
                add  a,a                    ; world byte column of screen 0
                ld   e,a
                ld   a,(KARA_WX)
                sub  e
                ret

; VIEW_NEXT_X / VIEW_NEXT_CR - WORLD_X / WORLD_CR as they will be when
; the NEXT frame is shown: the pending horizontal step if there is one,
; the vertical step if it has reached the frame before its latch.
;                                destroys AF
VIEW_NEXT_X:    ld   a,(H_PENDING)
                or   a
                ld   a,(WORLD_X)            ; LD leaves the flags alone
                ret  z
                ld   a,(H_WX)
                ret

VIEW_NEXT_CR:   ld   a,(V_PHASE)
                cp   V_PARTS                ; the row is whole, so the next
                                            ; VSYNC is where the view moves
                ld   a,(WORLD_CR)
                ret  nz
                ld   a,(V_WCR)
                ret

; ---------------------------------------------------------------------
; PLAYER_TO_SCREEN - refresh KARA_X / KARA_Y, which is what the blitter
; draws from at the top of the NEXT frame - so they are resolved against
; the view that frame will show, not the one on screen now. Getting that
; wrong is the "two Karas" of the vertical scroll: she was drawn 8 lines
; into a view the CRTC had not been given yet.
;                                destroys AF,DE
; ---------------------------------------------------------------------
PLAYER_TO_SCREEN:
                call VIEW_NEXT_X
                add  a,a
                add  a,KARA_ART_X           ; THE ONE PLACE THE ART OFFSET IS
                ld   e,a                    ; PAID: KARA_X is the sprite's
                ld   a,(KARA_WX)            ; left edge and KARA_WX the box's,
                sub  e                      ; and the blitter wants the sprite
                ld   (KARA_X),a
                call VIEW_NEXT_CR
                add  a,a
                add  a,a
                add  a,a                    ; WORLD_CR * 8 = screen top, pixels
                ld   e,a
                ld   a,(KARA_WY)
                sub  e
                ld   (KARA_Y),a
                ret

PLAYER_SPEED:   db P_WALK       ; this frame's step, walk or run
KARA_WX:        dw 43           ; her BOX - the sprite's left edge is 40
KARA_WY:        db 16           ; starts in the air and falls onto the roof.
                                ; HIGH ENOUGH THAT HER FEET START ABOVE IT:
                                ; 64 was right for a 44-line box and puts a
                                ; 64-line one inside the tiles, where the
                                ; landing snaps her a whole tile row too low
                                ; and BOX_SOLID_H then refuses every step -
                                ; she animates on the spot and never moves.
KARA_VY:        db 0
KARA_GROUND:    db 0
KARA_CLIMB:     db 0   ; non-zero while she is on a ladder
KARA_FELL:      db 0   ; non-zero while she is in the air WITHOUT having
                       ; jumped - which is `drop` and not `jump` (8.4)
