; =====================================================================
; config.asm - hardware ports and memory map constants
; See CLAUDE.md sections 5.1 / 5.2 for the rationale behind the layout.
; =====================================================================

; ---------------------------------------------------------------------
; Gate array (port &7Fxx). The top two bits of the value select the
; register: %00 = pen, %01 = colour, %10 = ROM/mode, %11 = RAM config.
; ---------------------------------------------------------------------
GA_PORT             equ &7F

; ROM/mode register. bit4 = interrupt counter reset, bit3 = upper ROM
; disable, bit2 = lower ROM disable, bits1-0 = screen mode.
; &8C = mode 0 with BOTH ROMs disabled, which is what makes &0000-&3FFF
; and &C000-&FFFF plain RAM. This MUST be set before executing in low RAM.
RMR_MODE0           equ &8C

; RAM configurations. Only the &4000-&7FFF window differs between them.
RAM_CFG_BASE        equ &C0     ; 0/1/2/3 - power-on default
RAM_CFG_C4          equ &C4     ; 0/4/2/3 - levels 1-2
RAM_CFG_C5          equ &C5     ; 0/5/2/3 - levels 3-4
RAM_CFG_C6          equ &C6     ; 0/6/2/3 - levels 5-6
RAM_CFG_C7          equ &C7     ; 0/7/2/3 - title screen + dialogue

GA_PEN_BORDER       equ &10     ; pen index 16 selects the border
GA_COLOUR_BASE      equ &40     ; %01xxxxxx - OR with a 0-31 hardware colour

; ---------------------------------------------------------------------
; PPI - port B bit 0 is the CRTC VSYNC flag
; ---------------------------------------------------------------------
PPI_PORT_A          equ &F4     ; AY data bus
PPI_PORT_B          equ &F5     ; bit 0 = VSYNC
PPI_PORT_C          equ &F6     ; bits 7-6 AY BDIR/BC1, bits 3-0 keyboard row
PPI_CONTROL         equ &F7

; PPI mode-set words. Writing EITHER of these also zeroes ports A, B and
; C, so the control word must always be written BEFORE the row select.
PPI_CTL_PA_OUT      equ &82     ; port A output - what an AY writer needs
PPI_CTL_PA_IN       equ &92     ; port A input  - what a keyboard read needs

; AY-3-8912 control lines, in PPI port C bits 7-6.
AY_INACTIVE         equ &00
AY_REG_READ         equ &40     ; BC1 - also selects the keyboard row
AY_REG_SELECT       equ &C0     ; BDIR+BC1 - latch a register number
AY_R14_KEYBOARD     equ 14      ; AY port A is wired to the key matrix

; ---------------------------------------------------------------------
; Memory map
; ---------------------------------------------------------------------
IRQ_VECTOR          equ &0038   ; IM 1 entry point
CORE_ADDR           equ &0040   ; core engine runs here after relocation
BANK_WINDOW         equ &4000   ; banked window - never execute from here
BOOT_ADDR           equ &4000   ; AMSDOS loads and calls the bootstrap here
STACK_TOP           equ &BFFF   ; never let SP reach &C000 (VRAM)
SCREEN_BASE         equ &C000
SCREEN_WIDTH_BYTES  equ 80
SCREEN_HEIGHT_LINES equ 200
