; =====================================================================
; screen.asm - Mode 0 screen setup and block fills
; =====================================================================

; ---------------------------------------------------------------------
; ROW_OFFSETS - character row * 80 bytes, which under R1 = 40 is also
; character row * 40 CRTC words. SCR_ADDR (sprite.asm) indexes it with
; ADD A,L, so ALIGN 64 is load-bearing: all 64 bytes must sit in one
; page. 32 entries, not 25, because SCR_ADDR masks the row with AND &1F
; and a mispositioned sprite must read a defined value.
;
; The two meanings agree only because R1 = 40 - see the assert.
; ---------------------------------------------------------------------
                align 64
ROW_OFFSETS:    dw 0,   80,  160,  240,  320,  400,  480,  560,  640
                dw 720, 800, 880,  960,  1040, 1120, 1200, 1280, 1360
                dw 1440,1520,1600, 1680, 1760, 1840, 1920
                dw 1920,1920,1920, 1920, 1920, 1920, 1920   ; rows 25-31 clamp

; ---------------------------------------------------------------------
; SCREEN_CLS - fill the whole 16 KB frame buffer with A.
; IN : A = byte value          destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
SCREEN_CLS:     ld   hl,SCREEN_BASE
                ld   de,SCREEN_BASE + 1
                ld   bc,&4000 - 1
                ld   (hl),a
                ldir
                ret

; ---------------------------------------------------------------------
; DRAW_BLOCK - fill a rectangle of screen bytes, scroll-correct.
;
; Module 3 called SCREEN_LINE once per scanline, which was both wrong
; under scroll (flat 80-byte model) and ruinously slow - 140 T of table
; lookup to place a 3-byte HUD fill. This computes the address once and
; steps it with the raster rule, and tests the seam once per row rather
; than per byte.
;
; Uses BLK_LINE / BLK_HEIGHT / BLK_X / BLK_W / BLK_VAL.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
DRAW_BLOCK:     ld   a,(BLK_HEIGHT)
                or   a
                ret  z
                ld   b,a                ; B = rows left
                ld   a,(BLK_W)
                or   a
                ret  z
                ld   c,a

                ld   a,(BLK_X)
                push bc
                ld   c,a
                ld   a,(BLK_LINE)
                call SCR_ADDR           ; HL = first byte, under SCROLL
                pop  bc
                ex   de,hl              ; DE = screen
                ld   a,(BLK_W)
                ld   l,a                ; L = width, master copy
                ld   a,(BLK_VAL)
                ld   h,a                ; H = fill byte - both hoisted out of
                                        ; the row loop, 32 T per row saved
.row:           ld   c,l                ; 4   C = bytes this row
                ld   a,d                ; 4   does this row reach past offset 2047?
                or   &F8                ; 8   Z iff (D AND 7) = 7
                inc  a                  ; 4
                jp   nz,.fast           ; 12
                ld   a,c                ; 4
                dec  a                  ; 4
                add  a,e                ; 4   E + W - 1 > 255 -> the run wraps
                jp   nc,.fast           ; 12

.slow:          push de                 ; rare: wrap-aware within the block
                ld   a,h
.sbyte:         ld   (de),a
                push af
                call SPR_STEP_BYTE
                pop  af
                dec  c
                jp   nz,.sbyte
                pop  de
                jp   .next

.fast:          push de                 ; 16
                ld   a,h                ; 4
.fbyte:         ld   (de),a             ; 8
                inc  de                 ; 8   safe: the run stays in the block
                dec  c                  ; 4
                jp   nz,.fbyte          ; 12
                pop  de                 ; 12

.next:          call SCR_NEXT_LINE      ; 40  scroll-correct raster step
                djnz .row               ; 16/12
                ret

BLK_LINE:       db 0
BLK_HEIGHT:     db 0
BLK_X:          db 0
BLK_W:          db 0
BLK_VAL:        db 0

; ---------------------------------------------------------------------
; PALETTE_SET - program 16 pens plus the border from PALETTE_DATA.
; Values in the table are already OR'd with GA_COLOUR_BASE.
;                                destroys AF,BC,HL
; ---------------------------------------------------------------------
PALETTE_SET:    ld   hl,PALETTE_DATA
                ; falls into PALETTE_LOAD

; ---------------------------------------------------------------------
; PALETTE_LOAD - the same, from any 17-byte table.
;
; The title screen is the artist's own 16 colours and not the game's
; (src/palette.asm), so there are two tables and one routine.
; IN:  HL = 16 pen values then the border, already OR'd with
;      GA_COLOUR_BASE      destroys AF,BC,HL
; ---------------------------------------------------------------------
PALETTE_LOAD:   ld   bc,GA_PORT * 256   ; C = 0 = select pen 0
.pen:           out  (c),c              ; %00xxxxxx - select pen C
                ld   a,(hl)
                inc  hl
                out  (c),a              ; %01xxxxxx - set its colour
                inc  c
                ld   a,c
                cp   16
                jr   c,.pen
                ld   c,GA_PEN_BORDER
                out  (c),c              ; select the border
                ld   a,(hl)
                out  (c),a
                ret

; ---------------------------------------------------------------------
; BORDER_SET - IN: A = hardware colour 0-31    destroys AF,BC
; ---------------------------------------------------------------------
BORDER_SET:     or   GA_COLOUR_BASE
                ld   bc,GA_PORT * 256 + GA_PEN_BORDER
                out  (c),c
                out  (c),a
                ret

; ---------------------------------------------------------------------
; WAIT_VSYNC - spin until the CRTC raises VSYNC (PPI port B, bit 0).
;                                destroys AF,BC
; ---------------------------------------------------------------------
WAIT_VSYNC:     ld   bc,PPI_PORT_B * 256
.wait:          in   a,(c)
                rra
                jr   nc,.wait
                ret

; ---------------------------------------------------------------------
; WAIT_VSYNC_END - spin until the CRTC drops VSYNC again.
;
; WAIT_VSYNC TESTS THE LEVEL, NOT AN EDGE, and the pulse is 16
; scanlines - about 4,100 T (CLAUDE.md 9). The main loop does not care:
; its own work always overruns the pulse. A loop whose body is a few
; hundred T does: INTRO_WAIT went round FOUR TIMES inside one pulse, so
; its prompt blinked at four times the rate it was written for and its
; keyboard was scanned four times a frame. Calling this at the end of
; the body makes the pair an edge.
;                                destroys AF,BC
; ---------------------------------------------------------------------
WAIT_VSYNC_END: ld   bc,PPI_PORT_B * 256
.wait:          in   a,(c)
                rra
                jr   c,.wait
                ret
