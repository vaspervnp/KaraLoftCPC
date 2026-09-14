; =====================================================================
; Kara Loft and the Illuminati
; MODULE 1 - memory architecture, bank switching, build pipeline
;
; Build: ./build.sh        Output: build/kara.dsk
;
; The binary is loaded at &4000 by the BASIC loader because that is the
; only place a disc load can land without overwriting the running BASIC
; program (which lives from &0170). &4000-&7FFF is the banked window
; though, so nothing may stay there. The code at &4000 is therefore a
; bootstrap that relocates the core engine down to &0040 and jumps to
; it, after which the window is free for level data.
; =====================================================================

                include "config.asm"

; =====================================================================
; BOOTSTRAP - entered from BASIC with CALL &4000, firmware still live.
; =====================================================================
                org  BOOT_ADDR

BOOT:           di
                ld   sp,STACK_TOP           ; below VRAM, above everything else

                ; Mode 0 and both ROMs off. The lower ROM must go before we
                ; execute at &0040, otherwise reads from &0000-&3FFF come
                ; from the OS ROM rather than from the code we just copied.
                ld   bc,GA_PORT * 256 + RMR_MODE0
                out  (c),c

                ; Known RAM configuration before touching the window.
                ld   bc,GA_PORT * 256 + RAM_CFG_BASE
                out  (c),c

                ; Relocate the core engine image down to &0040. Source and
                ; destination do not overlap, so a plain LDIR is safe.
                ld   hl,CORE_IMAGE
                ld   de,CORE_ADDR
                ld   bc,CORE_SIZE
                ldir

                jp   CORE_ENTRY             ; no way back to BASIC from here

BOOT_END:
CORE_IMAGE      equ  BOOT_END               ; where the core bytes sit in the file

; =====================================================================
; CORE ENGINE - assembled for &0040, stored in the file after the
; bootstrap. ORG's second argument is what lets those differ.
; =====================================================================
                org  CORE_ADDR, BOOT_END

CORE_START:

CORE_ENTRY:     ; Install our own IM 1 handler. The firmware's lives in the
                ; lower ROM, which we just switched out, so &0038 must be
                ; rewritten before the first EI.
                ld   a,&C3                  ; JP nn
                ld   (IRQ_VECTOR),a
                ld   hl,IRQ_HANDLER
                ld   (IRQ_VECTOR + 1),hl
                im   1

                call PALETTE_SET
                xor  a
                call SCREEN_CLS

                call BANK_TEST              ; must run before anything else
                call DRAW_COLOUR_BARS       ; uses the banked window
                call DRAW_BANK_RESULTS

                ei

; ---------------------------------------------------------------------
; Main loop. Module 1 has no game yet; it displays two live indicators:
;   heartbeat block - toggles every 25 frames, proves the loop runs
;   interrupt block - green while IRQ_TICKS advances, proves IM 1 fires
; ---------------------------------------------------------------------
MAIN_LOOP:      call WAIT_VSYNC

                ld   a,(FRAME_COUNT)
                inc  a
                ld   (FRAME_COUNT),a
                cp   25
                jr   c,.skip_beat
                xor  a
                ld   (FRAME_COUNT),a
                ld   a,(HEARTBEAT)
                xor  &FF                    ; &FC <-> &03, pen 7 <-> pen 8
                ld   (HEARTBEAT),a
                ld   (BLK_VAL),a
                ld   a,150
                ld   (BLK_LINE),a
                ld   a,24
                ld   (BLK_HEIGHT),a
                ld   a,4
                ld   (BLK_X),a
                ld   a,8
                ld   (BLK_W),a
                call DRAW_BLOCK
.skip_beat:
                ld   a,(IRQ_TICKS)
                ld   hl,IRQ_LAST
                cp   (hl)                   ; unchanged across a whole frame?
                ld   (hl),a
                ld   a,PEN_RED              ; then the interrupt is dead
                jr   z,.irq_done
                ld   a,PEN_GREEN
.irq_done:      ld   (BLK_VAL),a
                ld   a,150
                ld   (BLK_LINE),a
                ld   a,24
                ld   (BLK_HEIGHT),a
                ld   a,16
                ld   (BLK_X),a
                ld   a,8
                ld   (BLK_W),a
                call DRAW_BLOCK

                jp   MAIN_LOOP

; ---------------------------------------------------------------------
; IRQ_HANDLER - the CPC fires 6 interrupts per frame (300 Hz). For now
; it only counts; the music player and raster splits hang off it later.
; ---------------------------------------------------------------------
IRQ_HANDLER:    push af
                ld   a,(IRQ_TICKS)
                inc  a
                ld   (IRQ_TICKS),a
                pop  af
                ei
                ret

; ---------------------------------------------------------------------
; BANK_TEST - acceptance test for Module 1.
; Writes a distinct marker through each configuration and reads them all
; back. Distinct values surviving proves the four expansion banks are
; physically separate and that BANK_RESTORE really restores.
;                                destroys AF,BC,HL
; ---------------------------------------------------------------------
BANK_TEST:      call BANK_RESTORE
                ld   a,&A0
                ld   (BANK_WINDOW),a
                call BANK_SET_C4
                ld   a,&A4
                ld   (BANK_WINDOW),a
                call BANK_SET_C5
                ld   a,&A5
                ld   (BANK_WINDOW),a
                call BANK_SET_C6
                ld   a,&A6
                ld   (BANK_WINDOW),a
                call BANK_SET_C7
                ld   a,&A7
                ld   (BANK_WINDOW),a

                ld   hl,BANK_RESULT
                call BANK_RESTORE
                ld   a,(BANK_WINDOW)
                cp   &A0
                call BANK_STORE
                call BANK_SET_C4
                ld   a,(BANK_WINDOW)
                cp   &A4
                call BANK_STORE
                call BANK_SET_C5
                ld   a,(BANK_WINDOW)
                cp   &A5
                call BANK_STORE
                call BANK_SET_C6
                ld   a,(BANK_WINDOW)
                cp   &A6
                call BANK_STORE
                call BANK_SET_C7
                ld   a,(BANK_WINDOW)
                cp   &A7
                call BANK_STORE
                jp   BANK_RESTORE

; IN: Z = pass, HL = result slot. LD does not touch flags, so the test
; result survives until it is consumed here.
BANK_STORE:     ld   a,PEN_GREEN
                jr   z,.ok
                ld   a,PEN_RED
.ok:            ld   (hl),a
                inc  hl
                ret

; ---------------------------------------------------------------------
; DRAW_COLOUR_BARS - 16 bars, one per pen, 5 bytes wide, 64 lines tall.
; Proves the Mode 0 encoding, the palette write and the VRAM addressing
; in one picture: bar N must read back as pen N.
; ---------------------------------------------------------------------
DRAW_COLOUR_BARS:
                ld   hl,PEN_SOLID
                xor  a
                ld   (BLK_X),a
                ld   (BLK_LINE),a
                ld   a,64
                ld   (BLK_HEIGHT),a
                ld   a,5
                ld   (BLK_W),a
                ld   b,16
.bar:           push bc
                push hl
                ld   a,(hl)
                ld   (BLK_VAL),a
                call DRAW_BLOCK
                ld   a,(BLK_X)
                add  a,5
                ld   (BLK_X),a
                pop  hl
                inc  hl
                pop  bc
                djnz .bar
                ret

; ---------------------------------------------------------------------
; DRAW_BANK_RESULTS - five blocks: &C0, C4, C5, C6, C7. Green = pass.
; ---------------------------------------------------------------------
DRAW_BANK_RESULTS:
                ld   hl,BANK_RESULT
                ld   a,100
                ld   (BLK_LINE),a
                ld   a,32
                ld   (BLK_HEIGHT),a
                ld   a,10
                ld   (BLK_W),a
                ld   a,4
                ld   (BLK_X),a
                ld   b,5
.blk:           push bc
                push hl
                ld   a,(hl)
                ld   (BLK_VAL),a
                call DRAW_BLOCK
                ld   a,(BLK_X)
                add  a,14
                ld   (BLK_X),a
                pop  hl
                inc  hl
                pop  bc
                djnz .blk
                ret

                include "bank.asm"
                include "screen.asm"
                include "palette.asm"

; ---------------------------------------------------------------------
; Core variables
; ---------------------------------------------------------------------
FRAME_COUNT:    db 0
HEARTBEAT:      db PEN_GREEN
IRQ_TICKS:      db 0
IRQ_LAST:       db 0
BANK_RESULT:    ds 5

CORE_END:
CORE_SIZE       equ  CORE_END - CORE_START
