; =====================================================================
; intro.asm - the title picture and its prompt                (MODULE 6)
;
; The artist's 160x200 Mode 0 screen, ZX0-packed onto the disc as five
; raw sectors and unpacked STRAIGHT INTO VIDEO RAM. There is no bank to
; stage it through and no reason for one: nothing else is on the screen
; while the title is up, and a 16,336-byte picture would not fit beside
; a level's art anyway.
;
; IT IS SHOWN BEFORE THE LEVEL LOADS AND THE PROMPT AFTER, which is the
; whole point of the order. LEVEL_LOAD is 1.6 s with interrupts off
; (CLAUDE.md 7.5) and nothing can be pressed during it, so a prompt put
; up first would be a lie for a second and a half. Put up after, it
; means what it says: the press starts the game on the next frame.
;
; The words blink, and they blink by being two pre-rendered strips
; rather than a font and a save-under - tools/make_intro.py knows both
; the picture and where the words go, so it emits the picture with them
; and the picture without, and the blink is one LDIR either way.
; =====================================================================

                ; The picture's palette, the prompt's two strips and
                ; the eight screen addresses they go to, all written by
                ; tools/make_intro.py. It is included FIRST because the
                ; equates in it are used below and RASM evaluates those
                ; in source order.
                include "intro.inc"

INTRO_BLINK_MASK equ 15         ; frames a state: 16 on, 16 off

; ---------------------------------------------------------------------
; INTRO_SHOW - the picture, off the disc and onto the screen.
;
; OUT: carry SET on success; carry CLEAR means the read failed and the
;      screen still holds whatever it held - the caller carries on, the
;      way SCROLL_DEMO does with a level that would not load.
;      destroys everything. INTERRUPTS ARE OFF ON RETURN: the 765 has
;      no FIFO (src/disc.asm).
; ---------------------------------------------------------------------
INTRO_SHOW:     di
                ; A PLAIN 200-LINE SCREEN AT &C000. R6 is still the
                ; firmware's 25 - SCROLL_INIT does not run until the
                ; game starts - but the start address is wherever BASIC
                ; left it after scrolling its own text up.
                ld   hl,0
                ld   (SCROLL),hl
                call SCROLL_APPLY
                ld   hl,INTRO_PALETTE
                call PALETTE_LOAD

                ld   hl,D_INTRO_SCR + 2     ; past the bank count and the
                ld   a,(hl)                 ; RAM config, which this one
                ld   (DISC_TRACK),a         ; has no use for
                inc  hl
                ld   a,(hl)
                ld   (DISC_SECT),a
                inc  hl
                ld   a,(hl)
                ld   (DISC_COUNT),a
                ld   hl,LEVEL_STAGE
                ld   (DISC_PTR),hl
                call DISC_READ
                ret  nc
                call DISC_MOTOR_OFF
                ld   hl,LEVEL_STAGE
                ld   de,&C000
                call UNPACK_AT
                scf
                ret

; ---------------------------------------------------------------------
; INTRO_PROMPT - put the words up, or take them down again.
; IN:  A = 0 for the picture as it was, anything else for the words
;      destroys AF,BC,DE,HL,IX
; ---------------------------------------------------------------------
INTRO_PROMPT:   or   a
                ld   hl,INTRO_TEXT_OFF
                jr   z,.strip
                ld   hl,INTRO_TEXT_ON
.strip:         ld   ix,INTRO_TEXT_ADDR
                ld   b,INTRO_TEXT_LINES
.line:          ld   e,(ix + 0)             ; the eight lines are in eight
                ld   d,(ix + 1)             ; different 2 KB blocks, so the
                inc  ix                     ; addresses are a table and not
                inc  ix                     ; a stride
                push bc
                ld   bc,INTRO_TEXT_BYTES
                ldir                        ; ... and HL walks the strip
                pop  bc
                djnz .line
                ret

; ---------------------------------------------------------------------
; INTRO_WAIT - blink the prompt until SPACE or the joystick's fire.
;
; It waits for the RELEASE as well. The same bit is her trigger, and the
; gun is draw-hold-release (CLAUDE.md 8.4): a press still held when the
; level starts is an AIM that plants her where she stands, and letting
; go of it then fires a round she never asked for.
;      destroys everything
; ---------------------------------------------------------------------
INTRO_WAIT:     call INPUT_INIT
                ld   a,INTRO_BLINK_MASK     ; so the first frame draws them
                ld   (INTRO_BLINK),a        ; ON rather than off
                ei
.frame:         call WAIT_VSYNC
                ld   hl,INTRO_BLINK
                inc  (hl)
                ld   a,(hl)
                and  INTRO_BLINK_MASK
                jr   nz,.keys
                ld   a,(hl)
                and  INTRO_BLINK_MASK + 1
                call INTRO_PROMPT
.keys:          di
                call INPUT_SCAN             ; the AY address latch is shared
                ei                          ; with the sound chip
                ld   a,(INPUT_NOW)
                and  IN_FIRE
                jr   nz,.held
                call WAIT_VSYNC_END         ; ... and the pulse is 16 lines
                jr   .frame                 ; long: see screen.asm

.held:          call WAIT_VSYNC_END
.release:       call WAIT_VSYNC
                di
                call INPUT_SCAN
                ei
                ld   a,(INPUT_NOW)
                and  IN_FIRE
                jr   z,.gone
                call WAIT_VSYNC_END
                jr   .release
.gone:
                xor  a                      ; and take the words off the
                jp   INTRO_PROMPT           ; picture on the way out

INTRO_BLINK:    db 0
