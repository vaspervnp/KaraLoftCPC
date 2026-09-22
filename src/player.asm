; =====================================================================
; player.asm - Kara's movement                             (MODULE 5)
;
; Coordinates are WORLD coordinates, and the two axes use different
; units on purpose:
;
;   KARA_WX  world byte column, 0-511   1 unit = 2 Mode 0 pixels
;   KARA_WY  world pixel row,   0-1023  the box's TOP line. SIXTEEN
;            BITS, because a level taller than 256 pixels is a level
;            this byte cannot address (8.1)
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
; so inside the push zone at either screen edge CAMERA_DECIDE can only
; fire on the frames she covers two. Let her walk her own distance there
; and her SCREEN column - the one the blitter draws at - goes 54, 55,
; 54, 55 ... at 25 Hz: every frame is drawn and erased correctly, every
; RAM check passes, and on a monitor there are two Karas a character
; apart for as long as the screen moves. So in the push zone she moves
; the way the camera does: P_PUSH bytes on the camera's frame, nothing
; on the frames between, and her screen column never changes while the
; world goes by.
;
; AND THE WALK IS HALF THE SPEED IT WAS, WHICH IS WHAT THE ART ASKS FOR.
; It was 1 byte - 2 Mode 0 pixels - every frame, 100 pixels a second,
; and it crossed the 160-pixel display in a second and a half. The
; artist's walk cycle is 40 frames long and her feet are 9 pixels apart
; at full stride, so a cycle plants them 18 pixels of ground apart and
; the engine was carrying her 80: she skated four fifths of every step.
; At P_WALK_BEAT she covers 1 pixel a frame, and with the cycle halved
; in action.asm (KARA_RATE) the two agree to a pixel.
;
; A BYTE IS THE SMALLEST STEP THERE IS - KARA_X is a byte column and a
; Mode 0 pixel is half of one - so half speed is not a smaller step, it
; is a step she does not take: P_WALK on one frame in two, and in the
; push zone P_PUSH on one frame in four, which is the same ground.
;
; AND THE RUN IS A BYTE A FRAME, NOT THE CRTC'S WHOLE CHARACTER, BECAUSE
; THE FRAME CANNOT PAY FOR A COLUMN EVERY FRAME. Two bytes a frame is
; exactly one scroll step a frame, which puts H_HEAD and H_TAIL on the
; SAME frame - the pessimistic sum of CLAUDE.md 9, 84,544 T of 79,872 -
; and a frame that overruns waits for the next VSYNC. Measured over 200
; hardware frames, holding SHIFT and RIGHT: 107 loop iterations, which
; is 25 Hz, a character of scroll every other frame and Kara drawn on
; one frame in two. At a byte a frame the camera steps every other frame
; - which is the load the old walk carried and the whole of CLAUDE.md 9
; measures as locked - and it is 197 of 200.
;
; So the run is what the walk used to be and the walk is half of it.
; That also leaves the roof's gap where its measurements put it: the
; take-off window of 8.4 was derived at a byte a frame, so it is the RUN
; that clears it now and a walking jump that falls in.
; =====================================================================

; A GAME FRAME IS TWO HARDWARE FRAMES (25 Hz, src/main.asm), so a step
; every game frame is 25 of them a second. These are the speeds the
; 50 Hz loop had, in the units the 25 Hz one counts in: the walk was a
; byte on one frame in two and the run a byte on every frame, and both
; come to the same ground in the same second.
P_WALK          equ 1           ; byte columns a game frame = 2 pixels
P_RUN           equ 2           ; SHIFT: twice that, which is also exactly
                                ; one CRTC character - so a run scrolls
                                ; every game frame and a walk every other
P_PUSH          equ 2           ; bytes per camera step: one CRTC character
; THE PHYSICS IS PER GAME FRAME AND THERE ARE HALF AS MANY OF THEM, so
; every velocity doubles and gravity quadruples to leave the arc where
; it was in REAL time. Measured against the 50 Hz numbers: -15 with a
; gravity of 4 rises 15+11+7+3 = 36 pixels in four game frames, which
; is the same 36 pixels in the same eight hardware frames the old
; -8/1 took over eight.
P_GRAVITY       equ 4
; A FALL OF MORE THAN ONE AND A HALF OF HER OWN HEIGHT COSTS HER, AND
; ONLY THE EXCESS IS PAID FOR. The height is KARA_BOX_H and not a
; number, so a re-drawn heroine moves the threshold with her; the shift
; is a shift because RASM's `/' rounds to nearest (CLAUDE.md 12.8).
;
; WHAT THE LEVEL MAKES OF IT, measured off the map rather than chosen:
;
;   walking off the roof into ROOF_GAP   world y 32 -> 160, 128 lines
;                                        ... 32 over, so 32 points
;   letting go of the LEDGE              world y 90 -> 160,  70 lines
;                                        ... under 96, so free
;   a jump that lands where it left      36 lines of arc, free
;   climbing down the ladder             not a fall at all
;
; which is the design in one table: the ledge is the safe way down and
; the gap is the one that hurts, and she can take the gap three times.
; A point a pixel is the rate that makes those numbers, and the medkit
; is worth 35 (CLAUDE.md 8.6).
FALL_FREE       equ KARA_BOX_H + (KARA_BOX_H >> 1)

P_VY_MAX        equ 15          ; MUST stay under one tile (16) - a
                                ; destination-only probe is only exact
                                ; while a single step cannot skip a tile.
                                ; TWICE THE OLD 8 WOULD BE EXACTLY 16 AND
                                ; IS NOT ALLOWED: 15 is as near as the
                                ; probe lets a 25 Hz fall get, and it is
                                ; 94% of the old speed in real time.
P_JUMP          equ -15         ; rises 15+11+7+3 = 36 px, about 2.2 tiles
P_COYOTE        equ 3           ; game frames after the ground goes away in which
                                ; UP is still a jump. SHE CROSSES THE ROOF'S
                                ; GAP IN A 15-FRAME ARC AND THE HOLE IS 12
                                ; BYTES, so the window to take off in is the
                                ; ten bytes before the lip - a fifth of a
                                ; second, and a press one frame late is a
                                ; 128-pixel fall. Measured: see PLAYER_Y.
P_CLIMB         equ 2           ; pixels a game frame on a ladder. The vertical
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
PLAYER_UPDATE:  call FALL_MARK              ; where this frame's fall began
                ld   a,(KARA_STATE)
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
                ld   a,(KARA_HANG)
                or   a
                jp   nz,PLAYER_HANG         ; ... and so does a ledge

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
                call EDGE_ENTER             ; DOWN at a lip: crouch, then hang
                ld   a,(KARA_HANG)
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

                ; THE BEAT TRAVELS WITH THE SPEED, because every step
                ; in this routine is a whole byte and what tells a walk
                ; from a run is how many frames apart they are. In the
                ; camera's push zone a run scrolls every other frame and
                ; a walk every fourth one.
                ld   a,c
                and  IN_RUN
                ld   a,P_WALK
                jr   z,.speed
                ld   a,P_RUN
.speed:         ld   (PLAYER_STEP),a        ; how far a free step carries her
                ld   a,c
                and  IN_LEFT
                jr   nz,.left

                ; ---- right: leading edge is the box's right side ----
                xor  a
                ld   (KARA_FACING),a        ; 0 = right
                call AIM_ROOTS_HER
                ret  nz
                call PLAYER_SCREEN_X
                inc  a                      ; her screen column after 1 byte
                sub  CAM_TRAIL              ; how far past the mark - and it
                cp   CAM_BAND               ; underflows to 255 short of it,
                ld   a,(PLAYER_STEP)        ; which reads as "not at the mark"
                ld   e,a                    ; exactly as it should
                jr   nc,.step_r             ; free, or panning: walk normally
                ld   a,(WORLD_X)
                cp   WORLD_W / 2 - SCR_CHARS
PM_PX_VIEW      equ  $ - 1
                jr   nc,.step_r             ; camera at the map's end: walk on
                call PUSH_PHASE
                ret  nz                     ; the camera's off frame
.push_r:        ld   e,P_PUSH               ; its on frame: move as far as it
.step_r:        ld   d,0
                ld   hl,(KARA_WX)
                add  hl,de                  ; the proposed position
                ld   de,WORLD_W - KARA_W_BYTES + KARA_ART_X
PM_KARA_XMAX    equ  $ - 2
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
                ld   de,(KARA_WY)
                call BOX_SOLID_H
                pop  hl
                ret  nz                     ; blocked - the step is refused
                ld   (KARA_WX),hl
                ret

.left:          ld   a,1
                ld   (KARA_FACING),a        ; 1 = left
                call AIM_ROOTS_HER
                ret  nz
                call PLAYER_SCREEN_X
                dec  a                      ; her screen column after 1 byte
                ld   c,a
                ld   a,CAM_LEAD
                sub  c                      ; how far short of the mark
                cp   CAM_BAND
                ld   a,(PLAYER_STEP)
                ld   e,a
                jr   nc,.step_l             ; free, or panning: walk normally
                ld   a,(WORLD_X)
                or   a
                jr   z,.step_l              ; camera at the map's start
                call PUSH_PHASE
                ret  nz
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
.probe_l:       ld   de,(KARA_WY)
                push hl
                call BOX_SOLID_H
                pop  hl
                ret  nz
                ld   (KARA_WX),hl
                ret

; ---------------------------------------------------------------------
; AIM_ROOTS_HER - NZ while SPACE is down, which is when she plants.
;
; THE FACING IS SET BEFORE THIS AND THE STEP AFTER IT, deliberately: she
; can turn round while she aims and she cannot walk. Aiming is a stance,
; not a pause - so gravity, the ladder and the jump are all untouched,
; and the moment SPACE comes up the four cels of the recoil play while
; she is free to move again.
;
; IN : C = (INPUT_NOW), as PLAYER_X left it.       destroys AF
; ---------------------------------------------------------------------
AIM_ROOTS_HER:  ld   a,c
                and  IN_FIRE
                ret

; ---------------------------------------------------------------------
; PUSH_PHASE - NZ on the frames a pushing WALK sits still.
;
; The camera is decided at the top of the NEXT frame from the position
; this frame leaves behind, so "the frame she moves P_PUSH" and "the
; frame the camera steps" are one frame apart, and the low bits of
; FRAME_COUNT (incremented right after PLAYER_UPDATE) are a clock both
; halves agree on.
;
; THE PUSH STEP IS P_PUSH WHATEVER SHE IS DOING, because the CRTC
; scrolls a whole character and there is no smaller step to give it. So
; the frames she sits still on are however many it takes to cover the
; same ground as her free step would:
;
;     mask = P_PUSH / PLAYER_STEP - 1 = 2 - PLAYER_STEP
;
; which is 1 for a walk - two bytes every other frame against one byte
; every frame - and 0 for a run, whose free step IS a character, so it
; scrolls on every game frame and never sits still. CAMERA_DECIDE asks
; for nothing on the frames between, because she is behind the mark on
; every one of them: it reads her column, not this clock.
;                                        destroys AF,B
; ---------------------------------------------------------------------
PUSH_PHASE:     ld   a,2
                ld   hl,PLAYER_STEP
                sub  (hl)                   ; 1 walking, 0 running
                ld   b,a
                ld   a,(FRAME_COUNT)
                and  b
                ret

; ---------------------------------------------------------------------
; FALL_MARK - remember the line a descent started from.
;
; ONE RULE AND ONE CALL SITE: while she is NOT going down, the mark
; follows her; the instant she starts going down it stays where it is.
; That is the whole of it, and it gets every case right without knowing
; about any of them - a jump measures from its own APEX, because the
; mark follows her up and freezes on the frame gravity turns her round;
; a ladder measures from nothing, because she never descends under
; gravity on one; and letting go of a ledge measures from the ledge,
; because hanging holds KARA_VY at zero.
;
; It is called FIRST in PLAYER_UPDATE, before anything this frame has
; moved, so what it reads is last frame's verdict - which is the frame
; the descent actually began on.
;                                        destroys AF,HL
; ---------------------------------------------------------------------
FALL_MARK:      ld   a,(KARA_VY)
                bit  7,a                    ; rising: the mark follows her
                jr   nz,.follow
                or   a
                ret  nz                     ; descending: leave it where it is
.follow:        ld   hl,(KARA_WY)
                ld   (FALL_TOP),hl
                ret

; ---------------------------------------------------------------------
; FALL_DAMAGE - what the drop cost her, on the frame she lands.
;
; IN:  DE = the line she has landed on    destroys AF,BC,DE,HL
;
; THE DISTANCE IS SIXTEEN BITS AND THE DAMAGE IS EIGHT, which is a
; question a 256-pixel level could not ask: a fall of more than 255
; pixels is one no byte can hold, and rather than let it wrap it is
; taken as the most a fall can cost. Nothing survives 255 points.
; ---------------------------------------------------------------------
FALL_DAMAGE:    ld   hl,(FALL_TOP)
                ex   de,hl                  ; HL = where she landed
                or   a
                sbc  hl,de                  ; how far down she came
                ret  c                      ; ... and up is not a fall
                ld   a,h
                or   a
                ld   a,255                  ; LD does not touch the flags
                jr   nz,.hurt
                ld   a,l
                cp   FALL_FREE + 1
                ret  c                      ; a step, a jump, a ledge: free
                sub  FALL_FREE              ; only the excess is paid for,
.hurt:          ld   c,a                    ; a point a pixel
                ld   hl,PLAYER_HP
                ld   a,(hl)
                sub  c
                jr   nc,.store
                xor  a                      ; ... and no further than dead
.store:         ld   (hl),a
                ld   a,HURT_FRAMES          ; the border says so, the same way
                ld   (HURT_FLASH),a         ; a drone's round does (enemy.asm)
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
                jr   z,.coyote

                ; ---- standing ----------------------------------------
                ld   a,(INPUT_PRESSED)      ; edge-triggered, not level: a
                and  IN_UP                  ; held key must not re-jump
                jr   nz,.jump

                ; Still supported? Probed at feet + 1, NOT at the feet
                ; line. Probing the feet line makes GROUNDED blink two
                ; frames in three, and because the jump is edge-triggered
                ; that swallows two jump presses out of every three.
                ld   hl,(KARA_WY)
                ld   de,KARA_BOX_H
                add  hl,de
                ex   de,hl                  ; DE = the line under her feet
                ld   hl,(KARA_WX)
                ld   b,TA_BLOCK
                call BOX_SOLID_V
                ret  nz                     ; still on something
                xor  a
                ld   (KARA_GROUND),a        ; walked off an edge - which is
                ld   (KARA_VY),a            ; a DROP and not a jump, and this
                inc  a                      ; is the one place the two part
                ld   (KARA_FELL),a          ; company (action.asm)
                ld   a,P_COYOTE             ; ... and the one place the lip is
                ld   (KARA_COYOTE),a        ; still under her feet (below)
                ret

                ; ---- the lip she has just left -----------------------
                ; SHE CAN STILL JUMP FOR P_COYOTE FRAMES AFTER WALKING OFF
                ; AN EDGE, and the roof's gap is why. Measured: her arc is
                ; 15 frames and she covers a byte a frame, the hole is 12
                ; bytes and she must be 7 past its far lip to land, so the
                ; only take-off that clears it is one of the ten bytes
                ; before the edge - and the last of them is the frame the
                ; ground goes away on. A press one frame later used to do
                ; nothing at all, which is the whole 128-pixel fall for a
                ; 20 ms miss. It is NOT a second jump: .jump zeroes the
                ; counter, so the air holds exactly one.
.coyote:        ld   hl,KARA_COYOTE
                ld   a,(hl)
                or   a
                jr   z,.airborne
                dec  (hl)                   ; it runs out whether she uses it
                ld   a,(INPUT_PRESSED)      ; or not, so a long fall cannot
                and  IN_UP                  ; be rescued halfway down
                jr   z,.airborne

.jump:          ld   a,P_JUMP
                ld   (KARA_VY),a
                xor  a
                ld   (KARA_GROUND),a
                ld   (KARA_FELL),a          ; she chose this one
                ld   (KARA_COYOTE),a        ; and the air holds one jump
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

                ; ---- the proposed top line, in sixteen bits ---------
                ; THE VELOCITY IS A SIGNED BYTE AND THE LINE IS A WORD, so
                ; the byte is sign-extended into BC before it is added:
                ; RLA puts its sign in the carry and SBC A,A turns that
                ; into 0 or &FF, which is the whole of it.
                ld   c,a                    ; C = the velocity
                rla                         ; ... its sign into the carry
                sbc  a,a
                ld   b,a                    ; BC = it, sign-extended
                ld   hl,(KARA_WY)
                add  hl,bc
                ex   de,hl                  ; DE = the proposed top line
                bit  7,b
                jr   nz,.rising

                ; ---- falling: probe just past her feet ---------------
                push de
                ld   hl,KARA_BOX_H
                add  hl,de
                ex   de,hl
                ld   hl,(KARA_WX)
                ld   b,TA_BLOCK             ; a one-way platform blocks this
                call BOX_SOLID_V
                pop  de
                jr   nz,.land
                ld   (KARA_WY),de
                ret

.land:          ; Snap her feet ONTO the tile rather than into it: the
                ; blocking tile's top pixel row is (footY AND &F0), and the
                ; box's last line must be the row above it. Only the LOW
                ; byte is masked, because a tile boundary is every 16
                ; pixels and the high byte passes through.
                ld   hl,KARA_BOX_H
                add  hl,de
                ld   a,l
                and  &F0
                ld   l,a
                ld   de,KARA_BOX_H
                or   a
                sbc  hl,de
                ld   (KARA_WY),hl
                ex   de,hl                  ; DE = the line she landed on
                call FALL_DAMAGE
                xor  a
                ld   (KARA_VY),a
                ld   (KARA_FELL),a
                ld   (KARA_COYOTE),a
                inc  a
                ld   (KARA_GROUND),a
                ret

                ; ---- rising: probe the top line ---------------------
.rising:        ld   hl,(KARA_WX)
                ld   b,TA_SOLID             ; a platform is climbed through
                push de
                call BOX_SOLID_V
                pop  de
                jr   nz,.bump
                ld   (KARA_WY),de
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
                ld   hl,(KARA_WY)
                ld   de,KARA_BOX_H
                add  hl,de
                ex   de,hl
                call CLIMB_AT
                and  TA_CLIMB
                jr   nz,CLIMB_GRAB
                ret

.try_up:        ld   a,c
                and  IN_UP
                ret  z
                ; UP: the tile directly ABOVE the floor she is on - one
                ; line higher is inside it, whatever her feet are on.
                ld   hl,(KARA_WY)
                ld   de,KARA_BOX_H - 1      ; one line higher is inside it
                add  hl,de
                ex   de,hl
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
; own duration and then re-decide - which lands on CLIMB going up,
; moving or frozen, and on IDLE or WALK coming off.
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
; DE holds the feet line she is proposing and B the attributes of the
; tile it lands in - the line was C until it grew a second byte, and
; what CLIMB_AT preserving BC buys now is the ATTRIBUTES across the
; probe rather than the line, which goes on the stack.
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
                ld   hl,(KARA_WY)
                ld   de,KARA_BOX_H + P_CLIMB
                add  hl,de                  ; her feet, after the step
                ex   de,hl
                push de
                call CLIMB_AT
                pop  de
                ld   b,a
                and  TA_CLIMB
                jr   z,.off_bottom
                ld   hl,(KARA_WY)
                ld   de,P_CLIMB
                add  hl,de
                ld   (KARA_WY),hl
                ret

                ; Past the last rung. If there is a floor under it she
                ; stands on it; if there is not, she lets go and falls -
                ; a ladder that ends in mid-air must not leave her
                ; standing on nothing.
.off_bottom:    ld   a,b
                and  TA_BLOCK
                jr   z,.let_go
                ld   a,e                    ; the floor is that tile's top
                and  &F0                    ; line, and only the LOW byte is
                ld   e,a                    ; masked: a tile row is 16 lines
.let_go:        ld   hl,0 - KARA_BOX_H      ; ... and her box hangs above it
                add  hl,de
                ld   (KARA_WY),hl
                ld   a,b
                and  TA_BLOCK
                jr   nz,CLIMB_LAND
                jr   CLIMB_LEAVE

                ; ---- up --------------------------------------------
.up:            ld   hl,(KARA_WY)
                ld   de,KARA_BOX_H - P_CLIMB
                add  hl,de
                ex   de,hl
                push de
                call CLIMB_AT
                pop  de
                and  TA_CLIMB
                jr   z,.off_top
                ld   hl,(KARA_WY)
                ld   de,0 - P_CLIMB
                add  hl,de
                ld   (KARA_WY),hl
                ret

                ; Off the top: her feet are in the tile ABOVE the shaft,
                ; so the floor is that tile's BOTTOM - which is the top
                ; line of the last rung's tile, 16 on from the mask.
.off_top:       ld   a,e
                and  &F0
                ld   e,a
                ld   hl,16 - KARA_BOX_H     ; the carry out of the mask is the
                add  hl,de                  ; 16-bit add's, not a byte's
                ld   (KARA_WY),hl
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
                ld   (KARA_COYOTE),a        ; a ladder is not a lip
                inc  a
                ld   (KARA_FELL),a
                ret

; =====================================================================
; THE LEDGE: DOWN at the lip of a floor, and the 40 frames after it
;
; A ladder is the way down a level gives you. This is the one the floor
; gives you: press DOWN facing the edge and she crouches, takes hold of
; the lip and hangs off it - the `hang` tag, which the artist redrew for
; exactly this (CLAUDE.md 7.1): the hands grip an edge in FRONT of her
; and above her, the body hangs below alongside the wall.
;
; WHICH WAY SHE FACES IS THE WALL, NOT THE DROP. The art is drawn with
; the building to her right, so hanging off a RIGHT-hand lip is the
; mirrored cel - she turns her back on the drop, which is what a person
; climbing down does. The grip is at column 11 of the 24-pixel box and
; the wall from column 12, so the snap below puts the lip's last solid
; byte under sprite byte 5 (mirrored) or its first under sprite byte 6.
;
; AND THEN IT IS A QUESTION. Let DOWN up and she waits HANG_HOLD frames
; and climbs back; press it again inside them and she lets go, which is
; a `drop` and not a jump. Holding DOWN forever holds her there forever:
; the count only starts when the key comes up.
; =====================================================================
HANG_BEAT       equ 5           ; game frames of crouch before she takes hold
HANG_DROP       equ 58          ; lines she drops when she does. Standing,
                                ; her feet are on the floor's top line and
                                ; the box's last line is the one above it;
                                ; hanging, the art puts that same floor
                                ; line on line 6 of the box. 64 - 6 = 58
HANG_HOLD       equ 20          ; game frames to make up her mind in

; ---------------------------------------------------------------------
; EDGE_ENTER - DOWN, on her feet, at the lip of the floor she faces.
;
; Called after CLIMB_ENTER, so a ladder under her takes it first: DOWN
; on a rung is a climb and DOWN at a lip is a hang, and a ladder that
; runs down the face of a building is both places at once.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
EDGE_ENTER:     ld   a,(KARA_GROUND)
                or   a
                ret  z
                ld   a,(INPUT_PRESSED)      ; a PRESS, not the key's state:
                and  IN_DOWN                ; walking to the edge with DOWN
                ret  z                      ; held would grab it on arrival

                ; ---- is the floor gone, just past the edge she faces?
                ld   a,(KARA_FACING)
                or   a
                ld   hl,(KARA_WX)
                jr   nz,.look_l
                ld   de,KARA_BOX_W          ; the byte just past her box
                add  hl,de
                jr   .probe
.look_l:        dec  hl
.probe:         push hl
                ld   hl,(KARA_WY)
                ld   de,KARA_BOX_H          ; the line under her feet
                add  hl,de
                ex   de,hl
                pop  hl
                push hl
                call MAP_ATTR
                pop  hl
                and  TA_BLOCK
                ret  nz                     ; still floor: DOWN is a crouch

                ; ---- the lip is that byte's TILE boundary -----------
                ld   a,l
                and  &FC                    ; HL = the open tile's first byte
                ld   l,a
                ld   a,(KARA_FACING)
                or   a
                jr   nz,.grab_l
                ld   de,-3                  ; a right-hand lip: the wall's
                add  hl,de                  ; last byte is sprite byte 5 of
                ld   a,1                    ; the MIRRORED cel
                jr   .grab
.grab_l:        inc  hl                     ; a left-hand one: its first byte
                xor  a                      ; is sprite byte 6 of the cel as
.grab:          ld   (KARA_FACING),a        ; drawn
                ld   (KARA_WX),hl
                ld   a,HANG_BEAT
                ld   (KARA_HANG_T),a
                ld   a,1                    ; 1 = crouching, about to take hold
                ld   (KARA_HANG),a
                ret

; ---------------------------------------------------------------------
; PLAYER_HANG - the crouch, the hold, and the 40 frames after it.
;
; Gravity does not run while this does: PLAYER_UPDATE comes straight
; here. Nothing else moves her either - the cel is drawn hanging off a
; fixed lip and a hand that slides along it is not a hand.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
PLAYER_HANG:    ld   a,(KARA_HANG)
                dec  a
                jr   nz,.holding

                ; ---- the crouch, and then she takes hold ------------
                ld   hl,KARA_HANG_T
                dec  (hl)
                ret  nz
                ld   hl,(KARA_WY)
                ld   de,HANG_DROP
                add  hl,de
                ld   (KARA_WY),hl
                ld   a,2
                ld   (KARA_HANG),a
                xor  a
                ld   (KARA_HANG_T),a        ; 0 = DOWN is still down
                ld   (KARA_GROUND),a
                ld   (KARA_VY),a
                ld   (KARA_FELL),a
                ret

.holding:       ld   a,(KARA_HANG_T)
                or   a
                jr   nz,.counting
                ld   a,(INPUT_NOW)          ; still holding the key she
                and  IN_DOWN                ; grabbed with: she hangs on
                ret  nz
                ld   a,HANG_HOLD
                ld   (KARA_HANG_T),a
                ret

.counting:      ld   a,(INPUT_PRESSED)
                and  IN_DOWN
                jr   nz,.let_go             ; asked again: she drops
                ld   hl,KARA_HANG_T
                dec  (hl)
                ret  nz

                ; ---- nobody said drop, so she pulls herself back up -
                xor  a
                ld   (KARA_HANG),a
                ld   hl,(KARA_WY)
                ld   de,0 - HANG_DROP
                add  hl,de
                ld   (KARA_WY),hl
                ld   a,1
                ld   (KARA_GROUND),a
                ret

.let_go:        xor  a
                ld   (KARA_HANG),a
                ld   (KARA_HANG_T),a
                ld   (KARA_VY),a
                ld   (KARA_GROUND),a
                inc  a
                ld   (KARA_FELL),a          ; letting go is a DROP
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
PM_CD_VIEW      equ  $ - 1
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
                ; THE VIEW'S TOP IS SIXTEEN BITS NOW and it has to be:
                ; WORLD_CR reaches V_CR_MAX, which is 8 on a 16-tile map
                ; and 104 on a 64-tile one, so WORLD_CR * 8 is 832 lines
                ; and no byte holds it.
                ;
                ; HER HALF-HEIGHT GOES ON TO HER AND NOT OFF THE VIEW,
                ; which is the same difference and NOT the same carry.
                ; Taking it off the view is one subtract fewer and the
                ; view's top is 0 for the first four rows of any level,
                ; so the subtrahend goes NEGATIVE - and `SBC HL,DE` sets
                ; the carry on an unsigned borrow, so every frame then
                ; read as "she is above the view" and the camera never
                ; followed her down a ladder. Her MIDDLE is what the band
                ; wants: measured from her head the band has to sit 30
                ; lines higher to frame her, and the view then stops one
                ; character row short of its limit with the road half off
                ; the bottom of the display.
                ld   a,(WORLD_CR)
                ld   l,a
                ld   h,0
                add  hl,hl
                add  hl,hl
                add  hl,hl                  ; the view's top, in lines
                ex   de,hl                  ; ... which is never negative
                ld   hl,(KARA_WY)
                ld   a,l
                add  a,KARA_BOX_H / 2       ; HER MIDDLE, in sixteen bits and
                ld   l,a                    ; without BC, which this routine
                ld   a,h                    ; has never destroyed
                adc  a,0
                ld   h,a
                or   a
                sbc  hl,de                  ; her middle's screen line
                jr   c,.up                  ; above the view entirely
                ld   a,h
                or   a
                jr   nz,.down               ; more than 255 lines below it
                ld   a,l
                cp   CAM_BOT + 1
                jr   nc,.down
                cp   CAM_TOP
                jr   c,.up
                xor  a                      ; inside the band: nothing to do
                ret

.down:          ld   a,(WORLD_CR)
                cp   V_CR_MAX
PM_CV_VCR       equ  $ - 1
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

; ---------------------------------------------------------------------
; VIEW_TO_PLAYER - put the view where the camera would have panned it,
; at the START of a level rather than over the next second and a half.
;
; OUT: WORLD_X, WORLD_CR and SCROLL set, and LATCHED.
;      destroys AF,BC,DE,HL
;
; SCROLL_INIT used to leave the view at the top left and let CAMERA_V
; and CAMERA_DECIDE walk it to her a character and a row at a time.
; That was invisible while every level started in its own first screen
; - level 1's record is byte 43 and the camera settles in about eight
; frames - and four levels an environment (CLAUDE.md 8.1) is what makes
; it reachable: measured at a start 64 bytes in, the view panned for
; about FORTY game frames with the loop at 98 of 200 while it did, and
; she spent them clipped against the right-hand edge.
;
; WHAT IT COMPUTES IS WHERE THE CAMERA STOPS, not where it would like
; to be, so that the first frame is the frame the pan converges to and
; nothing moves afterwards:
;
;   across  CAMERA_DECIDE steps right while her box column is at or past
;           CAM_TRAIL, so it stops one character PAST (KARA_WX -
;           CAM_TRAIL) / 2. Measured: level 1 settles at WORLD_X 9 and
;           this gives 9.
;   down    CAMERA_V steps down while her MIDDLE is past CAM_BOT, so it
;           stops at the first row that brings it inside the band -
;           ceil((KARA_WY - (CAM_BOT - KARA_BOX_H / 2)) / 8).
;
; AND IT IS 16-BIT ACROSS, which PLAYER_SCREEN_X is not: that one wants
; a small DIFFERENCE and takes KARA_WX modulo 256 to get it (8.10),
; where this wants an absolute column of a 512-byte world. Reading the
; low byte here would put the view at the wrong end of the map from
; byte 256 on, which is CLAUDE.md 8.7's own bug with the operands the
; other way round.
; ---------------------------------------------------------------------
VIEW_TO_PLAYER: ld   hl,(KARA_WX)
                ld   de,CAM_TRAIL
                or   a
                sbc  hl,de
                jr   c,.left                ; she is inside the first screen
                srl  h                      ; / 2: bytes to characters
                rr   l
                inc  hl                     ; ... and one past, which is where
                                            ; the stepping actually stops
                ld   a,h
                or   a
                jr   nz,.right              ; over 255, so over the limit too
                ld   a,l
                cp   WORLD_W / 2 - SCR_CHARS + 1
PM_VT_VIEW1     equ  $ - 1
                jr   c,.across
.right:
                ld   a,WORLD_W / 2 - SCR_CHARS
PM_VT_VIEW      equ  $ - 1
                jr   .across
.left:          xor  a
.across:        ld   (WORLD_X),a

                ld   hl,(KARA_WY)
                ld   de,CAM_BOT - KARA_BOX_H / 2
                or   a
                sbc  hl,de
                jr   c,.top                 ; her middle is inside the band
                ld   a,h
                or   l
                jr   z,.top                 ; with the view at the very top
                ld   de,7                   ; ceil, in sixteen bits: on a tall
                add  hl,de                  ; map the distance is not a byte
                srl  h
                rr   l
                srl  h
                rr   l
                srl  h
                rr   l
                ld   a,h
                or   a
                jr   nz,.bottom             ; past 255 rows down
                ld   a,l
                cp   V_CR_MAX + 1
PM_VT_VCR1      equ  $ - 1
                jr   c,.down
.bottom:
                ld   a,V_CR_MAX
PM_VT_VCR       equ  $ - 1
                jr   .down
.top:           xor  a
.down:          ld   (WORLD_CR),a

                ; ---- and the start address the two of them mean -----
                ; SCROLL is in WORDS and the counters are what a step
                ; moves beside it: a character across is 1 and a row
                ; down is SCR_CHARS. From 0/0/0 that makes it exactly
                ; WORLD_CR * SCR_CHARS + WORLD_X, and the mask is the
                ; 1024-word ring of CLAUDE.md 6.4 - which this cannot
                ; reach (8 rows and 216 characters is 536) and states.
                ld   h,0
                ld   l,a
                add  hl,hl
                add  hl,hl
                add  hl,hl                  ; x8
                ld   d,h
                ld   e,l
                add  hl,hl
                add  hl,hl                  ; x32
                add  hl,de                  ; x40 = SCR_CHARS
                ld   a,(WORLD_X)
                add  a,l
                ld   l,a
                jr   nc,.word
                inc  h
.word:          ld   a,h
                and  &03
                ld   h,a
                ld   (SCROLL),hl
                jp   SCROLL_APPLY

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
; PLAYER_SPAWN - put her where the LEVEL says, not where the assembler
; did.
;
; IN : the entity table, installed - so after MAP_INSTALL and not before
; OUT: carry SET if the level carried an EK_PLAYER_START, and she is at
;      it with every byte of her movement state back to what a start
;      means. Carry CLEAR if it did not, and then NOTHING has been
;      touched: a level with no start record honestly leaves her where
;      she was, which at boot is the assembler's own numbers.
;                                        destroys AF,BC,DE,HL
;
; KARA_WX AND KARA_WY WERE INITIALISERS AND THAT IS ONE LEVEL AND ONE
; LIFE. They are applied when the bootstrap relocates the core image
; and never again - the image at &4027 is under bank C4 by the time a
; level has loaded - so a second level would start her on the first
; one's roof and a death has nowhere to put her back to. The level FSM
; needs both.
;
; THE RECORD'S Y IS THE BASE OF THE HITBOX AND KARA_WY IS ITS TOP (8.6),
; so the height comes off here. That is make_city_map.py's own
; conversion run backwards, and it is why the editor's marker hangs in
; the row above the line it stands on.
;
; X IS WORLD PIXELS AND KARA_WX IS A BYTE COLUMN, which is the one other
; unit in the record. One right shift, in 16 bits, because the map is
; 1,024 pixels across and 511 byte columns.
; ---------------------------------------------------------------------
PLAYER_SPAWN:   ld   a,(ENT_COUNT)
                or   a
                ret  z                      ; ... and OR leaves carry clear
                ld   b,a
                ld   hl,ENT_TABLE
                ld   de,ENT_STRIDE
.find:          ld   a,(hl)
                or   a                      ; EK_PLAYER_START is 0, so the
                jr   nz,.next               ; test for it is the test for zero
                push hl
                ld   bc,ENT_FLAGS
                add  hl,bc
                bit  0,(hl)                 ; EF_ACTIVE - a slot is told by
                pop  hl                     ; its flags and not by its kind
                jr   nz,.found
.next:          add  hl,de
                djnz .find
                or   a                      ; no start record in this level
                ret

.found:         inc  hl
                ld   e,(hl)
                inc  hl
                ld   d,(hl)                 ; DE = x, world pixels
                inc  hl
                ld   c,(hl)
                inc  hl
                ld   b,(hl)                 ; BC = y, world pixels - BOTH
                                            ; bytes of it now, because a
                                            ; level can be taller than 256
                                            ; pixels (8.1). B is free here:
                                            ; the search's counter is spent
                ld   hl,0 - KARA_BOX_H      ; the record's y is the BASE
                add  hl,bc
                ld   (KARA_WY),hl
                ld   (FALL_TOP),hl          ; ... and she is not falling from
                                            ; anywhere yet, so the mark is
                                            ; her own line (FALL_MARK)
                ex   de,hl
                srl  h
                rr   l
                ld   (KARA_WX),hl

                ; ---- and the state a start means --------------------
                ; Everything PLAYER_UPDATE keeps between frames. She is
                ; off the ground on purpose: KARA_GROUND = 0 lets her
                ; fall onto whatever the record stands her over, which
                ; is what the City's own start has always done, and it
                ; costs nothing when the record is already on a floor.
                xor  a
                ld   (KARA_VY),a
                ld   (KARA_GROUND),a
                ld   (KARA_CLIMB),a
                ld   (KARA_COYOTE),a
                ld   (KARA_HANG),a
                ld   (KARA_HANG_T),a
                ld   (KARA_FELL),a
                ld   (KARA_FACING),a        ; 0 = right, and every level in
                                            ; this game runs left to right
                scf
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
                ld   l,a
                ld   h,0
                add  hl,hl
                add  hl,hl
                add  hl,hl                  ; WORLD_CR * 8 = screen top, pixels
                ex   de,hl
                ld   hl,(KARA_WY)
                or   a
                sbc  hl,de
                ld   a,l                    ; ... and KARA_Y is a BYTE, which
                ld   (KARA_Y),a             ; is what makes 192-255 mean above
                ret                         ; the display (8.2)

PLAYER_STEP:    db P_WALK       ; byte columns a free step carries her: 1
                                ; walking, 2 running. SHE STEPS ON EVERY
                                ; GAME FRAME and a speed is the SIZE of the
                                ; step now, not how many frames apart they
                                ; are - at 25 Hz there is no half-frame to
                                ; skip (src/main.asm).
KARA_WX:        dw 43           ; her BOX - the sprite's left edge is 40
KARA_WY:        dw 16           ; starts in the air and falls onto the roof.
                                ; HIGH ENOUGH THAT HER FEET START ABOVE IT:
                                ; 64 was right for a 44-line box and puts a
                                ; 64-line one inside the tiles, where the
                                ; landing snaps her a whole tile row too low
                                ; and BOX_SOLID_H then refuses every step -
                                ; she animates on the spot and never moves.
FALL_TOP:       dw 0            ; the line this descent began at - her own
                                ; if she is not descending (FALL_MARK)
KARA_VY:        db 0
KARA_GROUND:    db 0
KARA_CLIMB:     db 0   ; non-zero while she is on a ladder
KARA_COYOTE:    db 0   ; frames of edge left to jump from, see PLAYER_Y
KARA_HANG:      db 0   ; 0 = no, 1 = the crouch before the grab, 2 = holding
KARA_HANG_T:    db 0   ; the beat, then the 40 frames after DOWN comes up
KARA_FELL:      db 0   ; non-zero while she is in the air WITHOUT having
                       ; jumped - which is `drop` and not `jump` (8.4)
