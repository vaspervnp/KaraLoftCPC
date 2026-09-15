; =====================================================================
; player.asm - Kara's movement                             (MODULE 5)
;
; Coordinates are WORLD coordinates, and the two axes use different
; units on purpose:
;
;   KARA_WX  world byte column, 0-511   1 unit = 2 Mode 0 pixels
;   KARA_WY  world pixel row,   0-255   the box's TOP line
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
P_PUSH          equ 2           ; bytes per camera step: one CRTC character
P_GRAVITY       equ 1
P_VY_MAX        equ 8           ; MUST stay under one tile (16) - a
                                ; destination-only probe is only exact
                                ; while a single step cannot skip a tile
P_JUMP          equ -8          ; rises 8+7+...+1 = 36 px, about 2.2 tiles
WORLD_W         equ MAP_W * 8   ; the map in BYTES: 64 tiles of 8

; ---------------------------------------------------------------------
; PLAYER_UPDATE - one frame of movement.
;
; Reads (INPUT_NOW) and (INPUT_PRESSED); writes KARA_WX, KARA_WY,
; KARA_VY, KARA_GROUND, KARA_FACING.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
PLAYER_UPDATE:  call BANK_SET_C4            ; once, around both axes
                call PLAYER_X
                call PLAYER_Y
                jp   BANK_RESTORE

; ---------------------------------------------------------------------
; PLAYER_X - propose a step, probe the LEADING edge, refuse the whole
; step if it is blocked.
;
; Only the leading edge is probed: the trailing edge is somewhere she is
; already standing, so it cannot have become solid. Refusing the whole
; step rather than sliding to the wall costs at most one byte of gap and
; avoids a second probe to find where exactly she should stop.
; ---------------------------------------------------------------------
PLAYER_X:       ld   a,(INPUT_NOW)
                ld   c,a
                and  IN_LEFT + IN_RIGHT
                jr   nz,.moving
                xor  a                      ; idle: back to the standing frame
                ld   (KARA_ANIM),a
                ld   a,KCORE_IDLE_FIRST
                ld   (KARA_FRAME),a
                ret

                ; The blob's frames are not the sheet's: --drop and
                ; --tags renumber them, so a cel is KCORE_<tag>_FIRST
                ; plus an index that wraps at KCORE_<tag>_COUNT. Nine
                ; frames of the drawn sheet are not shipped at all
                ; (CLAUDE.md 7.1), which is why walk is 5 and not 8.
.moving:        ld   a,(KARA_STEP)          ; animate while she walks
                inc  a
                ld   (KARA_STEP),a
                and  3
                jr   nz,.same_cel           ; a new cel every four frames
                ld   a,(KARA_ANIM)
                inc  a
                cp   KCORE_WALK_COUNT
                jr   c,.keep
                xor  a
.keep:          ld   (KARA_ANIM),a
.same_cel:      ld   a,(KARA_ANIM)
                add  a,KCORE_WALK_FIRST
                ld   (KARA_FRAME),a
                ld   a,c
                and  IN_LEFT
                jr   nz,.left

                ; ---- right: leading edge is the box's right side ----
                xor  a
                ld   (KARA_FACING),a        ; 0 = right
                call PLAYER_SCREEN_X
                inc  a                      ; her screen column after 1 byte
                cp   CAM_RIGHT_EDGE
                ld   e,P_WALK
                jr   c,.step_r              ; still in the free zone
                ld   a,(WORLD_X)
                cp   MAP_W * 8 / 2 - SCR_CHARS
                jr   nc,.step_r             ; camera at the map's end: walk on
                call PUSH_PHASE
                ret  z                      ; the camera's off frame: hold
                ld   e,P_PUSH               ; its on frame: move as far as it
.step_r:        ld   d,0
                ld   hl,(KARA_WX)
                add  hl,de                  ; the proposed position
                ld   de,WORLD_W - KARA_W_BYTES
                or   a
                sbc  hl,de                  ; past the world's right edge?
                add  hl,de
                jr   c,.probe_r
                ex   de,hl                  ; ... then stop exactly on it
                ; The bound is on her SPRITE, not her collision box, and
                ; that is what keeps her whole on screen. WORLD_X stops at
                ; 216 characters = 432 bytes, so a KARA_WX of 504 is screen
                ; byte 72 and her eighth byte is the last one the display
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
                cp   CAM_LEFT_EDGE
                ld   e,P_WALK
                jr   nc,.step_l             ; still in the free zone
                ld   a,(WORLD_X)
                or   a
                jr   z,.step_l              ; camera at the map's start
                call PUSH_PHASE
                ret  z
                ld   e,P_PUSH
.step_l:        ld   d,0
                ld   hl,(KARA_WX)
                or   a
                sbc  hl,de                  ; the proposed position IS the
                jr   nc,.probe_l            ; leading edge
                ld   hl,0                   ; ... and 0 is as far as it goes.
                                            ; Without this she walks off the
                                            ; left of the world: KARA_WX wraps
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
                ld   (KARA_GROUND),a        ; walked off an edge
                ld   (KARA_VY),a
                ret

.jump:          ld   a,P_JUMP
                ld   (KARA_VY),a
                xor  a
                ld   (KARA_GROUND),a
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
CAM_LEFT_EDGE   equ 16          ; screen byte columns
CAM_RIGHT_EDGE  equ 56

CAMERA_DECIDE:  ld   a,(V_PHASE)            ; never both axes at once - see
                or   a                      ; SCROLL_SERVICE in tilemap.asm
                ret  nz
                call PLAYER_SCREEN_X        ; A = screen byte column
                cp   CAM_RIGHT_EDGE
                jr   c,.check_left
                ld   a,(WORLD_X)
                cp   MAP_W * 8 / 2 - SCR_CHARS
                ret  nc                     ; at the right edge of the map
                jp   H_REQUEST_RIGHT

.check_left:    cp   CAM_LEFT_EDGE
                ret  nc
                ld   a,(WORLD_X)
                or   a
                ret  z                      ; at the left edge of the map
                jp   H_REQUEST_LEFT

; PLAYER_SCREEN_X - A = her screen byte column (KARA_WX - WORLD_X * 2)
; in the view that is on screen NOW. This is what the physics and the
; camera reason about.               destroys AF,DE,HL
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
                cp   2
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
                ld   e,a
                ld   a,(KARA_WX)
                sub  e
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

KARA_WX:        dw 40
KARA_WY:        db 16           ; starts in the air and falls onto the roof.
                                ; HIGH ENOUGH THAT HER FEET START ABOVE IT:
                                ; 64 was right for a 44-line box and puts a
                                ; 60-line one inside the tiles, where the
                                ; landing snaps her a whole tile row too low
                                ; and BOX_SOLID_H then refuses every step -
                                ; she animates on the spot and never moves.
KARA_VY:        db 0
KARA_GROUND:    db 0
