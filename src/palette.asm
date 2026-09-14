; =====================================================================
; palette.asm - the 16 Mode 0 pens, and solid-pen byte patterns
;
; Colour values are hardware colours 0-31 already OR'd with &40 (the
; gate array's colour-select prefix). The firmware ink -> hardware
; mapping used here is in docs/cpc_palette.md; it was read back off the
; emulator rather than copied from memory.
; =====================================================================

PALETTE_DATA:
                db &54      ; pen  0  black            (hw 20)
                db &55      ; pen  1  bright blue      (hw 21)
                db &44      ; pen  2  blue             (hw  4)
                db &4C      ; pen  3  bright red       (hw 12)
                db &5C      ; pen  4  red              (hw 28)
                db &4D      ; pen  5  bright magenta   (hw 13)
                db &58      ; pen  6  magenta          (hw 24)
                db &52      ; pen  7  bright green     (hw 18)
                db &56      ; pen  8  green            (hw 22)
                db &53      ; pen  9  bright cyan      (hw 19)
                db &46      ; pen 10  cyan             (hw  6)
                db &4A      ; pen 11  bright yellow    (hw 10)
                db &5E      ; pen 12  yellow           (hw 30)
                db &4E      ; pen 13  orange           (hw 14)
                db &40      ; pen 14  white            (hw  0)
                db &4B      ; pen 15  bright white     (hw 11)
                db &54      ; border  black            (hw 20)

; ---------------------------------------------------------------------
; PEN_SOLID - the Mode 0 byte that paints BOTH of its pixels in pen N.
;
; Mode 0 interleaving (see CLAUDE.md 5.3): with both pixels equal,
;   bits 7,6 = pen bit 0   bits 5,4 = pen bit 2
;   bits 3,2 = pen bit 1   bits 1,0 = pen bit 3
; so the byte is  (pen.0)*&C0 + (pen.2)*&30 + (pen.1)*&0C + (pen.3)*&03.
; ---------------------------------------------------------------------
PEN_SOLID:      db &00, &C0, &0C, &CC, &30, &F0, &3C, &FC
                db &03, &C3, &0F, &CF, &33, &F3, &3F, &FF

PEN_GREEN       equ &FC     ; solid pen 7
PEN_RED         equ &CC     ; solid pen 3
