; =====================================================================
; src/vortex.asm - the level's regions, and the siphon's current.
; CLAUDE.md 8.21.
;
; IN THE HIGH IMAGE (4), AND IT RUNS EVERY GAME FRAME. What runs once
; is what the HIGH image was for; this is here because the TOP image the
; swimmer lives in had eight bytes left, and REGION_AT - which was
; OXY_IN_AIR, and the bulk of the TOP's share of it - is what made the
; room for the current's one call. The HIGH image is base RAM like the
; rest, so where a routine lives costs nothing per call.
;
; THE CURRENT IS A HAND ON THE STICK, NOT A FORCE. Inside a region of
; kind RG_VORTEX, on two game frames in four, it rewrites INPUT_NOW
; before PLAYER_X and the swim's vertical step read it: a direction she
; is holding AWAY from the hole is let go, and with nothing held across
; it pushes TOWARD the middle; UP is let go, and with nothing held up or
; down it pushes DOWN. So every rule the water already keeps - the
; probes, the walls, her bounds, the camera's band - keeps the pull as
; well, for nothing; and what it costs her is measured in her own speed:
;
;   across, away from the hole      half a byte a game frame, not one
;   across, nothing held             half a byte TOWARD it
;   down, nothing held               three quarters of a line, not the
;                                    drift up
;   up                               a line and a quarter, not two
;
; TWO FRAMES IN FOUR AND NOT ONE IN TWO, BECAUSE OF THE CAMERA. Where it
; pushes, a walk is two bytes on the EVEN frames and nothing on the odd
; ones (8.2's PUSH_PHASE), so a pull on every even frame was the whole
; of her step there: nothing held, the current was as fast as she is,
; and holding away she did not move at all. Frames 0 and 1 of every four
; hold one even frame and one odd, so the push zone's step is taken on
; one pull frame and one free one, and the free walk's on two of each:
; half a byte a game frame both ways, in both zones.
;
; It never moves her faster than her own stroke, so it cannot outrun the
; camera, and it is only ever across or toward the floor - she can
; always swim out of it, which is what a key she has not found needs.
;
; AND THE THROAT IS THE DOOR. The siphon is an EK_DOOR the key opens
; (8.18); inside the current, with a key, the interact press is made for
; her on every frame, so the door's own handler opens it the frame her
; box meets the throat - the artist's "touching the throat triggers the
; transition", out of CHECK_KEY_DOOR rather than a second way to clear
; a level. Without a key nothing is pressed: she is held at the grate
; and swims out.
;
; INPUT_PREV IS ITS OWN BYTE (input.asm), so nothing written here to
; INPUT_NOW or INPUT_PRESSED reaches the next frame's edges.
; =====================================================================
RG_VORTEX       equ 6           ; docs/editor.md 5.5's six, and the
                                ; editor's RegionKind.Vortex after them

; ---------------------------------------------------------------------
; REGION_AT - is the middle of her box inside a region of kind A?
; IN:  A = the kind
; OUT: NZ, and E = the region's middle column minus hers, in tiles,
;      signed; Z if no region of that kind holds her middle
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
REGION_AT:      ld   (.kind + 1),a
                ld   a,(LEVEL_LVL + LVL_REGIONS)
                or   a
                ret  z                      ; a level with no regions
                ld   b,a
                push ix
                ld   hl,(LEVEL_LVL + LVL_OFF_REGION)
                ld   de,LEVEL_LVL
                add  hl,de
                push hl
                pop  ix                     ; the first region
                ld   hl,(KARA_WX)
                ld   de,SWIM_BOX_W / 2
                add  hl,de
                srl  h                      ; bytes -> tiles, four a tile
                rr   l
                srl  h
                rr   l
                ld   c,l                    ; C = her middle's column
                ld   hl,(KARA_WY)
                ld   de,SWIM_BOX_H / 2
                add  hl,de
                ld   a,l                    ; lines -> rows, sixteen a row
                srl  h
                rra
                srl  h
                rra
                srl  h
                rra
                srl  h
                rra
                ld   l,a                    ; L = her middle's row
.reg:           ld   a,(ix + 0)
.kind:          cp   0                      ; the kind asked for
                jr   nz,.next
                ld   a,c
                sub  (ix + 1)
                jr   c,.next                ; left of it
                cp   (ix + 5)
                jr   nc,.next               ; right of it
                ld   a,l
                sub  (ix + 3)
                jr   c,.next                ; above it
                cp   (ix + 6)
                jr   nc,.next               ; below it
                ld   a,(ix + 5)
                srl  a
                add  a,(ix + 1)             ; its middle column
                sub  c
                ld   e,a                    ; ... less hers
                pop  ix
                or   1                      ; NZ: she is in it
                ret
.next:          ld   de,RG_STRIDE
                add  ix,de
                djnz .reg
                pop  ix
                xor  a                      ; Z: she is not
                ret

; ---------------------------------------------------------------------
; VORTEX_SCAN - has this level a current at all? Once, from MAP_DERIVE.
;
; A LEVEL WITH NO CURRENT MUST NOT PAY FOR ONE - HAZARD_SCAN's rule
; (8.12) one table along. REGION_AT walks every region to find out she
; is in none of this kind, and that was measured at 812 T a game frame on
; levels 13 to 15, which have air and no current.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
VORTEX_SCAN:    xor  a
                ld   (VORTEX_ON),a
                ld   a,(LEVEL_LVL + LVL_REGIONS)
                or   a
                ret  z                      ; no regions: a land level
                ld   b,a
                ld   hl,(LEVEL_LVL + LVL_OFF_REGION)
                ld   de,LEVEL_LVL
                add  hl,de
                ld   de,RG_STRIDE
.reg:           ld   a,(hl)
                cp   RG_VORTEX
                jr   z,.yes
                add  hl,de
                djnz .reg
                ret
.yes:           ld   (VORTEX_ON),a          ; RG_VORTEX: not zero
                ret

VORTEX_ON:      db 0            ; non-zero: this level has a current

; ---------------------------------------------------------------------
; VORTEX_PULL - the siphon's current, on her stick. Called from
; PLAYER_SWIM before anything reads INPUT_NOW, alive only.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
VORTEX_PULL:    ld   a,(VORTEX_ON)
                or   a
                ret  z                      ; a level with no current
                ld   a,RG_VORTEX
                call REGION_AT
                ret  z                      ; not in the current
                ld   a,(KEYS_COUNT)
                or   a
                jr   z,.pull
                ld   hl,INPUT_PRESSED       ; with a key, the throat is
                set  0,(hl)                 ; asked: IN_INTERACT is IN_UP
.pull:          ld   a,(FRAME_COUNT)
                and  2
                ret  nz                     ; the current's off frames
                ld   hl,INPUT_NOW
                bit  0,(hl)                 ; IN_UP: fought
                jr   z,.not_up
                res  0,(hl)
                jr   .across
.not_up:        set  1,(hl)                 ; IN_DOWN, if nothing was held
.across:        ld   a,e
                or   a
                ret  z                      ; over the hole's middle
                jp   m,.left
                bit  2,(hl)                 ; the hole is to her RIGHT:
                jr   z,.right               ; LEFT held is let go,
                res  2,(hl)
                ret
.right:         set  3,(hl)                 ; ... nothing held is RIGHT
                ret
.left:          bit  3,(hl)                 ; ... and the mirror
                jr   z,.go_left
                res  3,(hl)
                ret
.go_left:       set  2,(hl)
                ret
