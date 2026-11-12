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
; The words blink, and they blink by being two strips rather than a font
; and a save-under: the blink is one LDIR either way.
;
; NEITHER STRIP IS IN THE IMAGE. They were 1,216 bytes of the HIGH image
; and the one without the words is the picture itself, so INTRO_SHOW
; copies it out of video RAM the moment the picture is up; the one WITH
; them is that copy with the lit pixels set to the prompt's pen, and
; which pixels are lit is INTRO_TEXT_MASK - two bits a byte, 152 bytes,
; out of tools/make_intro.py. Both go in the MAP's working copy, which
; nothing reads from the title until the next MAP_INSTALL copies the
; level over it (SCROLL_INIT, after INTRO_WAIT on both of the paths
; that reach here). This whole file is in the HIGH image now (main.asm):
; nothing in play calls it.
; =====================================================================

INTRO_BLINK_MASK equ 15         ; frames a state: 16 on, 16 off
INTRO_TEXT_OFF  equ MAP_ADDR    ; the picture as it is, out of VRAM ...
INTRO_TEXT_ON   equ MAP_ADDR + INTRO_TEXT_BYTES * INTRO_TEXT_LINES
                                ; ... and with the words on it
                assert INTRO_TEXT_ON + INTRO_TEXT_BYTES * INTRO_TEXT_LINES <= MAP_ADDR + MAP_BYTES

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
                call INTRO_STRIPS
                scf
                ret

; ---------------------------------------------------------------------
; INTRO_STRIPS - the prompt's two strips, out of the picture on the
; screen: the eight lines it covers copied as they are, and then again
; with every pixel INTRO_TEXT_MASK lights set to the prompt's pen. Mode
; 0's left pixel is the byte's &AA bits and its right one the &55 (CLAUDE.md
; 6.3), so a byte is (picture AND NOT lit) OR (pen AND lit).
;                                destroys AF,BC,DE,HL,IX
; ---------------------------------------------------------------------
INTRO_STRIPS:   ld   ix,INTRO_TEXT_ADDR
                ld   de,INTRO_TEXT_OFF
                ld   b,INTRO_TEXT_LINES
.line:          ld   l,(ix + 0)
                ld   h,(ix + 1)
                inc  ix
                inc  ix
                push bc
                ld   bc,INTRO_TEXT_BYTES
                ldir
                pop  bc
                djnz .line
                ld   hl,INTRO_TEXT_OFF      ; DE is INTRO_TEXT_ON, which
                ld   ix,INTRO_TEXT_MASK     ; is straight after it
                ld   c,INTRO_TEXT_BYTES * INTRO_TEXT_LINES / 4
.quad:          ld   a,(ix + 0)
                inc  ix
                ld   b,4
.byte:          rlca                        ; this byte's two bits, into
                rlca                        ; bits 1 and 0
                push af
                push bc
                ld   c,0
                rrca                        ; bit 0: the right pixel
                jr   nc,.left
                ld   c,&55
.left:          rrca                        ; bit 1: the left one
                jr   nc,.mix
                ld   a,c
                or   &AA
                ld   c,a
.mix:           ld   a,c                    ; C = the pen's bits
                cpl
                and  (hl)                   ; the picture where it is not
                ld   b,a
                ld   a,c
                and  INTRO_TEXT_PEN         ; ... and the pen where it is
                or   b
                ld   (de),a
                inc  hl
                inc  de
                pop  bc
                pop  af
                djnz .byte
                dec  c
                jr   nz,.quad
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
                ld   a,TUNE_TITLE           ; the title has its own tune,
                call SOUND_TUNE             ; and this loop is 50 Hz, so it
                                            ; ticks every other frame
                ld   a,INTRO_BLINK_MASK     ; so the first frame draws them
                ld   (INTRO_BLINK),a        ; ON rather than off
                ei
.frame:         call WAIT_VSYNC
                call SOUND_HALF
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
                call SOUND_HALF
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
