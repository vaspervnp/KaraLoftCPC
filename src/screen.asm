; =====================================================================
; screen.asm - Mode 0 screen setup and block fills
; =====================================================================

; ---------------------------------------------------------------------
; SCREEN_LINE - address of the first byte of a scanline.
;   addr = &C000 + (line AND 7) * &0800 + (line >> 3) * 80
; IN : A  = scanline 0-199
; OUT: HL = address              destroys AF,BC,DE
; ---------------------------------------------------------------------
SCREEN_LINE:    push af
                and  7
                add  a,a
                add  a,a
                add  a,a                ; (line AND 7) * 8 = high byte of *&0800
                add  a,SCREEN_BASE / 256
                ld   h,a
                ld   l,0
                pop  af
                rrca
                rrca
                rrca
                and  &1F                ; line >> 3 = character row 0-24
                ret  z
                ld   b,a
                ld   de,SCREEN_WIDTH_BYTES
.add_row:       add  hl,de
                djnz .add_row
                ret

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
; DRAW_BLOCK - fill a rectangle of screen bytes. Parameters live in
; memory because Module 1 has registers to spare and clarity to gain.
; Uses BLK_LINE / BLK_HEIGHT / BLK_X / BLK_W / BLK_VAL.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
DRAW_BLOCK:     ld   a,(BLK_HEIGHT)
                or   a
                ret  z
                ld   b,a
                ld   a,(BLK_LINE)
.row:           push bc
                push af
                call SCREEN_LINE        ; HL = start of this scanline
                ld   a,(BLK_X)
                ld   e,a
                ld   d,0
                add  hl,de
                ld   a,(BLK_W)
                or   a
                jr   z,.next
                ld   b,a
                ld   a,(BLK_VAL)
.fill:          ld   (hl),a
                inc  hl
                djnz .fill
.next:          pop  af
                inc  a
                pop  bc
                djnz .row
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
                ld   bc,GA_PORT * 256   ; C = 0 = select pen 0
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
