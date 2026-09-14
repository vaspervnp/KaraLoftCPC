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
PPI_PORT_B          equ &F5

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
