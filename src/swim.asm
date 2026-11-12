; =====================================================================
; swim.asm - the undersea: she SWIMS, and her box is another shape.
; CLAUDE.md 8.18.
;
; SHE IS 64x24 AND HORIZONTAL IN THE WATER, against 24x64 and upright
; everywhere else (7.1's swim sheet), and twenty-five immediates in six
; files say how big she is. They are the shape of a box the engine has
; always had exactly one of - the probes' widths, the camera's middle,
; the AABB, where her sprite starts relative to her box, the lane the
; blitter chooses - and every one of them sits on a path the frame runs.
;
; SO THE BOX IS PATCHED, THE WAY THE MAP'S SHAPE IS (src/mapshape.asm),
; and for the same reason: a patched immediate is an immediate, and
; reading a box byte out of memory at each site is 7 T a site on a frame
; whose tightest path has 800 (9). BOX_SET runs once, at MAP_INSTALL, out
; of the level header's underwater bit (8.3's flags byte, bit 2), and the
; City pays nothing for the sea.
;
; ONLY THE SITES A SWIMMER REACHES ARE IN THE TABLE. Twenty-nine more in
; player.asm and collide.asm read her box on the ladder, the ledge and
; the fall - none of which a level of water has - and are left as they
; were assembled. tools/test_sea.py holds the table to the source both
; ways: patched for land, every site is byte for byte the byte RASM
; wrote; patched for water, every one is the swimmer's.
;
; THIS FILE IS IN THE TOP IMAGE (src/main.asm), which is base RAM the
; level image and the stack both stop short of, and the per-frame half
; of it is too: base RAM is never paged out, so where code lives says
; nothing about how often it may run.
; =====================================================================

; HER BOX IN THE WATER. Measured off the shipped swim sheet, the opaque
; extent of its twelve cels is pixels 11..50 across and lines 1..21
; down: the body is the middle two thirds of a 64-pixel box and the
; legs trail behind it. So the box is 16 bytes - pixels 16..47 - centred
; in the 32, and all 24 lines.
SWIM_BOX_W      equ 16
SWIM_BOX_H      equ KSWIM_BOX_H                     ; 24
SWIM_W_BYTES    equ KSWIM_BOX_W                     ; 32
SWIM_ART_X      equ (SWIM_W_BYTES - SWIM_BOX_W) / 2 ; 8
SWIM_CAM_LEAD   equ SCR_CHARS * 2 - CAM_TRAIL - SWIM_BOX_W   ; 37
; A drone that follows her in the water (8.20): its middle this many
; bytes from hers - her half-sprite is 16 and the sea drone's 8, so 30
; leaves six bytes of water between them - and never nearer than the
; two sprites allow, (32 + 16) / 2; and its top level with hers, so its
; 16 lines are across her muzzle's lines 5 and 10.
SWIM_EN_DIST    equ 30
SWIM_EN_MIN     equ (SWIM_W_BYTES + SEADRONE_BOX_W) / 2
SWIM_EN_DY      equ 0

                ; her widest line fits the unrolled run, and a whole cel
                ; of them fits the script SPAN_SCRIPT_MAX sized for the
                ; tall ones (src/spanblit.asm)
                assert KSWIM_SPAN_MAX <= SPAN_MAX_WIDTH
                assert KSWIM_BOX_H * (2 * 3 + SPAN_MAX_WIDTH) + 1 <= SPAN_SCRIPT_MAX

; How much less of the world's right-hand end her box may reach, which
; MAP_SHAPE_SET takes off the shape's own bound: the bound is on her
; SPRITE (player.asm), and the swimmer's sprite is 15 bytes wider past
; her box than the walker's.
SWIM_XMAX_LESS  equ (SWIM_W_BYTES - SWIM_ART_X) - (KARA_W_BYTES - KARA_ART_X)

; ---------------------------------------------------------------------
; THE SITES. Each is the address of one immediate byte and the value it
; takes on land and in the water. Every 16-bit immediate here has the
; same high byte for both - asserted below - so only its low byte is in
; the table.
; ---------------------------------------------------------------------
                macro BOXSITE site,land,water
                dw  {site}
                db  ({land}) AND 255, ({water}) AND 255
                mend
                macro BOXSITEW site,land,water
                assert (({land}) AND &FF00) == (({water}) AND &FF00)
                dw  {site}
                db  ({land}) AND 255, ({water}) AND 255
                mend

BOX_SITES:      BOXSITE  BX_SOLID_H,   KARA_BOX_H - 1, SWIM_BOX_H - 1
                BOXSITE  BX_SOLID_V,   KARA_BOX_W - 1, SWIM_BOX_W - 1
                BOXSITE  BX_HUD_CLIP,  KARA_W_BYTES, SWIM_W_BYTES
                BOXSITE  BX_LANE,      SCR_CHARS * 2 - KARA_W_BYTES + 1, SCR_CHARS * 2 - SWIM_W_BYTES + 1
                BOXSITE  BX_MUZZLE,    KARA_W_BYTES * 2 - 1, SWIM_W_BYTES * 2 - 1
                BOXSITEW BX_FOLLOW,    KARA_BOX_W / 2, SWIM_BOX_W / 2
                BOXSITE  BX_EB_ART,    KARA_ART_X, SWIM_ART_X
                BOXSITE  BX_EB_W,      KARA_BOX_W, SWIM_BOX_W
                BOXSITE  BX_EB_H,      KARA_BOX_H, SWIM_BOX_H
                BOXSITEW BX_EN_MID,    KARA_BOX_W / 2, SWIM_BOX_W / 2
                BOXSITE  BX_EN_KW,     KARA_W_BYTES, SWIM_W_BYTES
                BOXSITE  ENT_HITBOX,   KARA_BOX_W, SWIM_BOX_W
                BOXSITE  ENT_HITBOX+1, KARA_BOX_H, SWIM_BOX_H
                BOXSITEW BX_ENT_W,     KARA_BOX_W, SWIM_BOX_W
                BOXSITEW BX_ENT_H,     KARA_BOX_H, SWIM_BOX_H
                BOXSITEW BX_ENT_W1,    KARA_BOX_W - 1, SWIM_BOX_W - 1
                BOXSITE  BX_ENT_WMAX,  HITBOX_W_MAX + KARA_BOX_W - 1, HITBOX_W_MAX + SWIM_BOX_W - 1
                BOXSITEW BX_PROBE_R,   KARA_BOX_W - 1, SWIM_BOX_W - 1
                BOXSITE  BX_LEAD_X,    CAM_LEAD, SWIM_CAM_LEAD
                BOXSITE  BX_EDGE_CP,   KARA_ART_X, SWIM_ART_X
                BOXSITEW BX_EDGE_L,    KARA_ART_X, SWIM_ART_X
                BOXSITEW BX_LAST_LINE, KARA_BOX_H - 1, SWIM_BOX_H - 1
                BOXSITE  BX_LEAD_CAM,  CAM_LEAD, SWIM_CAM_LEAD
                BOXSITE  BX_CAM_MID,   KARA_BOX_H / 2, SWIM_BOX_H / 2
                BOXSITEW BX_VIEW_MID,  CAM_BOT - KARA_BOX_H / 2, CAM_BOT - SWIM_BOX_H / 2
                BOXSITEW BX_SPAWN,     0 - KARA_BOX_H, 0 - SWIM_BOX_H
                BOXSITE  BX_TO_SCREEN, KARA_ART_X, SWIM_ART_X
                ; ... and where a drone that follows her keeps itself
                ; (src/enemy.asm's ENEMY_FOLLOW): its middle EN_DIST from
                ; hers, never nearer than the two sprites allow, and its
                ; top EN_DY below hers - her sprite is 32 bytes across
                ; and 24 lines down in the water, and her muzzle is on
                ; lines 5 and 10 of it (KSWIM_SPAWNS)
                BOXSITEW BX_EN_DIST,   EN_DIST, SWIM_EN_DIST
                BOXSITEW BX_EN_DISTN,  0 - EN_DIST, 0 - SWIM_EN_DIST
                BOXSITEW BX_EN_MIN,    EN_MIN, SWIM_EN_MIN
                BOXSITEW BX_EN_DY,     EN_DY, SWIM_EN_DY
BOX_SITES_END:  dw  0
BOX_SITES_N     equ (BOX_SITES_END - BOX_SITES) / 4

; ... AND FOUR WHOLE ADDRESSES, which are not her box: the HUD's second
; slot is the coins on land and her AIR in the water (src/hud.asm). A
; level of water has no coin in it, and the strip has no cell to spare
; for a seventh thing she carries (7.8) - so the count and the icon the
; slot reads are swapped instead. Site, land, water; a word each.
BOX_WORDS:      dw  HX_SLOT2_A,    COINS_COUNT,        OXY_DIGIT
                dw  HX_SLOT2_B,    COINS_COUNT,        OXY_DIGIT
                dw  HX_ICON2,      HUD_ICON_COIN,      HUD_ICON_OXYGEN
                dw  HX_ICON2_DARK, HUD_ICON_COIN_DARK, HUD_ICON_OXYGEN_DARK
                dw  0

; ---------------------------------------------------------------------
; BOX_SET - A = the level header's flags byte. Bit 2 is "underwater"
; (docs/editor.md 9.2), and it decides which box every site gets.
;
; It is called from MAP_INSTALL BEFORE MAP_SHAPE_SET, because the
; world's right-hand bound is the shape's and the box's at once and the
; shape patcher takes BOX_XMAX_LESS off its own figure. And it is called
; on every level start, a restart included, so a level of water after a
; level of land - or the other way round - gets the right one whatever
; the last level left behind.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
BOX_SET:        and  4                      ; the underwater bit
                jr   z,.land
                ld   a,1
.land:          ld   (LEVEL_SWIM),a
                ld   c,a                    ; 0 = land, 1 = water - and C
                                            ; is what the loop below reads,
                                            ; so it is taken HERE: it was
                                            ; taken after the breath below,
                                            ; out of the digit, and every
                                            ; level on land got the
                                            ; swimmer's box
                ld   a,SWIM_XMAX_LESS
                jr   nz,.less               ; (flags still from AND 4)
                xor  a
.less:          ld   (BOX_XMAX_LESS),a
                ld   hl,SWIM_AIM
                ld   (hl),0                 ; no trigger carried in from the
                                            ; last level or the last life
                ld   hl,OXY_FULL
                ld   (OXYGEN),hl            ; ... and a full breath: OXYGEN
                                            ; and OXY_T, and the digit with
                ld   a,OXY_MAX / OXY_PER_DIGIT  ; them
                ld   (OXY_DIGIT),a
                ld   hl,BOX_SITES
.site:          ld   e,(hl)
                inc  hl
                ld   d,(hl)
                inc  hl
                ld   a,d
                or   e
                jr   z,BOX_SET_WORDS        ; the bytes are done: the words
                ld   a,c
                or   a
                ld   a,(hl)                 ; the land value ...
                jr   z,.put
                inc  hl
                ld   a,(hl)                 ; ... or the water's
                dec  hl
.put:           ld   (de),a
                inc  hl
                inc  hl
                jr   .site

; ... and the words, the same way, two bytes at a time
BOX_SET_WORDS:  ld   hl,BOX_WORDS
.site:          ld   e,(hl)
                inc  hl
                ld   d,(hl)                 ; DE = the site
                inc  hl
                ld   a,d
                or   e
                ret  z
                ld   a,(LEVEL_SWIM)
                or   a
                jr   z,.take
                inc  hl                     ; the water's is two bytes on
                inc  hl
.take:          ld   a,(hl)
                ld   (de),a
                inc  hl
                inc  de
                ld   a,(hl)
                ld   (de),a
                inc  hl
                ld   a,(LEVEL_SWIM)         ; on land HL is at the water's
                or   a                      ; value: step over it
                jr   nz,.site
                inc  hl
                inc  hl
                jr   .site

LEVEL_SWIM:     db 0            ; non-zero: this level is water, she swims
BOX_XMAX_LESS:  db 0            ; what MAP_SHAPE_SET takes off her right bound

; =====================================================================
; THE SWIMMER'S PHYSICS. Called from PLAYER_UPDATE in place of all of
; it, because none of it is here: no ground, no gravity, no jump, no
; ladder, no ledge and no fall. What she keeps is PLAYER_X, whole -
; the step, the facing, the camera's push and the world's two edges are
; the same questions in water as on a roof, and the box patched above
; is what makes its answers the swimmer's.
;
; SHE MOVES SWIM_VY LINES A GAME FRAME UP OR DOWN, AND IT IS THE LADDER'S
; NUMBER FOR THE CAMERA'S SAKE. A row step of the view is 8 lines and
; takes three game frames (8.2), so anything faster than 2.67 lines a
; frame held for long enough leaves the camera's band; P_CLIMB is 2 and
; climbing down is measured at the lock (9). So is this.
;
; AND WITH NEITHER KEY HELD THE WATER LIFTS HER, a line on one game
; frame in two - the artist's "drifts up slowly when idle". A body is
; lifted too: dead, she takes no input and the drift still runs.
;
; Each line is probed on its own, so a step that would put her into
; rock stops her flush against it, rather than refused whole with a
; line of water left between her and the ledge.
;                                destroys AF,BC,DE,HL
; =====================================================================
SWIM_VY         equ P_CLIMB     ; lines a game frame, up or down
SWIM_DRIFT      equ 1           ; ... and the water's, on one frame in two

PLAYER_SWIM:    xor  a
                ld   (KARA_VY),a            ; nothing falls in the water, so
                                            ; FALL_MARK follows her and no
                                            ; fall is ever measured
                ld   a,(KARA_STATE)
                cp   KST_DIE
                ld   c,0                    ; dead: nothing held
                jr   z,.vertical
                call OXY_STEP               ; her air, alive
                call VORTEX_PULL            ; ... and the siphon's current
                                            ; on her stick (vortex.asm)
                ld   hl,INPUT_NOW
                res  7,(hl)                 ; IN_RUN: she does not run in the
                                            ; water, and the run's cels are
                                            ; not in this bank set (6.2)
                call PLAYER_X
                ld   a,(INPUT_NOW)
                ld   c,a
.vertical:      ld   a,c
                and  IN_UP
                ld   a,0 - SWIM_VY
                jr   nz,.go
                ld   a,c
                and  IN_DOWN
                ld   a,SWIM_VY
                jr   nz,.go
                ld   a,(FRAME_COUNT)
                and  1
                ret  nz                     ; the drift's off frame
                ld   a,0 - SWIM_DRIFT
.go:            or   a
                jp   p,.down
                neg
                ld   b,a
.up:            push bc
                ld   hl,(KARA_WY)
                dec  hl
                bit  7,h                    ; above line 0 of the world
                jr   nz,.stop
                push hl
                ex   de,hl                  ; DE = the line her top would be
                ld   hl,(KARA_WX)
                ld   b,TA_SOLID
                call BOX_SOLID_V
                pop  hl
                jr   nz,.stop
                ld   (KARA_WY),hl
                pop  bc
                djnz .up
                ret
.down:          ld   b,a
.dn:            push bc
                ld   hl,(KARA_WY)
                inc  hl
                push hl
                ld   de,SWIM_BOX_H - 1
                add  hl,de
                ex   de,hl                  ; DE = the line her bottom would be
                ld   hl,(KARA_WX)
                ld   b,TA_SOLID
                call BOX_SOLID_V
                pop  hl
                jr   nz,.stop
                ld   (KARA_WY),hl
                pop  bc
                djnz .dn
                ret
.stop:          pop  bc
                ret

; ---------------------------------------------------------------------
; ACT_SWIM - which cel, in the water. Jumped to from ACT_UPDATE once the
; death and the committed states have had their turn, and it jumps back
; into ACT_UPDATE's own tail with the state in A.
;
; THE GUN IS STILL DRAW-HOLD-RELEASE (8.4), and there is no `shoot_draw`
; to show while it is held: the swim sheet has `swim` and `swim_shoot`
; and that is all. So holding SPACE swims on - planted, because
; PLAYER_X plants her while she aims, exactly as on land - and the
; RELEASE is what fires, read off SWIM_AIM rather than off a state
; nothing draws. An empty gun starts the reload instead, as on land.
; ---------------------------------------------------------------------
ACT_SWIM:       ld   a,(INPUT_NOW)
                and  IN_FIRE
                jr   z,.released
                ld   a,1
                ld   (SWIM_AIM),a           ; the trigger is down
                ld   a,KST_SWIM
                jp   ACT_WANT
.released:      ld   hl,SWIM_AIM
                or   (hl)                   ; A is 0: was it down last frame?
                ld   (hl),0
                ld   a,KST_SWIM
                jp   z,ACT_WANT
                call GUN_HAS_ROUND
                ld   a,KST_SWIM_FIRE
                jp   nz,ACT_WANT
                call START_RELOAD
                ld   a,KST_SWIM
                jp   ACT_WANT

SWIM_AIM:       db 0            ; the trigger was down on the last frame
