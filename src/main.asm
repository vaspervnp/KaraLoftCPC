; =====================================================================
; Kara Loft and the Illuminati
; MODULE 3 - sprite blitter, save-under restore, dual pistol bullet pool
;
; Build: ./build.sh        Output: build/kara.dsk
;
; The binary is loaded at &4000 by the BASIC loader because that is the
; only place a disc load can land without overwriting the running BASIC
; program (which lives from &0170). &4000-&7FFF is the banked window
; though, so nothing may stay there. The code at &4000 is therefore a
; bootstrap that relocates the core engine down to &0040 and jumps to
; it, after which the window is free for level data.
;
; The demo screen doubles as the acceptance test for Modules 1-3:
;
;   lines   0- 31   16 colour bars, one per pen     (Mode 0 encoding)
;   lines  36- 51   5 bank markers, green = pass    (bank switching)
;   lines  56- 63   heartbeat and interrupt lamps   (IM 1, main loop)
;   lines  64-175   striped background              (masking, restore)
;   line     112    Kara, walking and firing
;   lines 180-197   two magazines of 7 rounds       (dual pistols)
;
; The border turns red for exactly as long as the frame's drawing takes,
; which is how tools/test_module3.py measures the T-state cost.
; =====================================================================

                include "config.asm"

; Save-under buffers live in the sprite-buffer region of the memory map,
; not in the core image, so they cost nothing on disc.
KARA_SAVE       equ &8000               ; 384 bytes
BUL_SAVE        equ &8180               ; 56 bytes

KARA_HOME_Y     equ 112
STRIPE_TOP      equ 64
STRIPE_BANDS    equ 14
HUD_LEFT_LINE   equ 180
HUD_RIGHT_LINE  equ 190
; Raster-time markers. The border is set to a different colour for each
; phase of the frame, so the coloured bands down the left edge ARE the
; profile - tools/test_module3.py counts their scanlines. 1 scanline =
; 64 us = 256 T-states.
MARK_ERASE      equ 21                  ; bright blue
MARK_LOGIC      equ 30                  ; yellow
MARK_SPRITE     equ 12                  ; bright red
MARK_BULLETS    equ 18                  ; bright green
MARK_HUD        equ 24                  ; magenta
MARK_IDLE       equ 20                  ; black

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
                call BUFFERS_CLEAR
                xor  a
                call SCREEN_CLS

                call BANK_TEST              ; must run before anything else
                call DRAW_COLOUR_BARS       ; uses the banked window
                call DRAW_BANK_RESULTS
                call DRAW_STRIPES

                ei

; ---------------------------------------------------------------------
; Main loop. Each phase paints the border its own colour first, so the
; frame's cost is legible as coloured bands down the left edge.
; ---------------------------------------------------------------------
MAIN_LOOP:      call WAIT_VSYNC

                ld   a,MARK_ERASE
                call BORDER_SET
                call BUL_ERASE              ; erase in reverse draw order:
                call KARA_ERASE             ; bullets were drawn over Kara

                ld   a,MARK_LOGIC
                call BORDER_SET
                call GAME_LOGIC

                ld   a,MARK_SPRITE
                call BORDER_SET
                call KARA_DRAW

                ld   a,MARK_BULLETS
                call BORDER_SET
                call BUL_DRAW

                ld   a,MARK_HUD
                call BORDER_SET
                call HUD_UPDATE

                ld   a,MARK_IDLE
                call BORDER_SET
                call LAMPS                  ; not game work, so not measured
                jp   MAIN_LOOP

; ---------------------------------------------------------------------
; BUFFERS_CLEAR - the save-under buffers sit at &8000, which is ordinary
; RAM holding whatever BASIC left there. BUL_ERASE reads an address out
; of each slot before anything has written one, so they must start as
; zero or the first frame scatters writes across memory.
; ---------------------------------------------------------------------
BUFFERS_CLEAR:  ld   hl,KARA_SAVE
                ld   de,KARA_SAVE + 1
                ld   bc,SPR_SAVE_SIZE + BUL_MAX * 4 - 1
                ld   (hl),0
                ldir
                ret

; ---------------------------------------------------------------------
; GAME_LOGIC - walk Kara across the screen, fire on a timer, age the
; rounds. Module 5 replaces this with real input and AI.
; ---------------------------------------------------------------------
GAME_LOGIC:     ld   a,(KARA_STEP)
                inc  a
                ld   (KARA_STEP),a
                and  1
                jr   nz,.no_walk            ; move one byte every other frame

                ld   a,(KARA_X)
                inc  a
                cp   SCREEN_WIDTH_BYTES - SPR_WIDTH_BYTES + 1
                jr   c,.store_x
                xor  a                      ; wrap to the left edge
.store_x:       ld   (KARA_X),a
                ld   a,(KARA_STEP)
                rrca
                rrca
                rrca
                and  3                      ; new walk frame every 8 frames
                ld   (KARA_FRAME),a
.no_walk:
                ld   a,(FIRE_TIMER)
                inc  a
                cp   10
                jr   c,.keep_timer
                call FIRE_BULLET
                xor  a
.keep_timer:    ld   (FIRE_TIMER),a

                call UPDATE_BULLETS
                call UPDATE_RELOAD

                ; Demo only: hand Kara another two clips when the reserve
                ; runs dry, so the firing and reloading keep cycling. The
                ; real game drops ammo as a pickup instead.
                ld   a,(AMMO_RESERVE)
                or   a
                ret  nz
                ld   a,BUL_MAX * 2
                ld   (AMMO_RESERVE),a
                ret

; ---------------------------------------------------------------------
; HUD_UPDATE - two rows of seven. Only redrawn when a magazine changes;
; fourteen block fills every frame would cost more than the sprite does.
; ---------------------------------------------------------------------
HUD_UPDATE:     ld   a,(HUD_DIRTY)
                or   a
                ret  z
                xor  a
                ld   (HUD_DIRTY),a
                ld   a,(MAG_LEFT)
                ld   c,a
                ld   a,HUD_LEFT_LINE
                call HUD_ROW
                ld   a,(MAG_RIGHT)
                ld   c,a
                ld   a,HUD_RIGHT_LINE
                ; fall through

; IN: A = top line, C = rounds left
HUD_ROW:        ld   (BLK_LINE),a
                ld   a,8
                ld   (BLK_HEIGHT),a
                ld   a,3
                ld   (BLK_W),a
                ld   a,4
                ld   (BLK_X),a
                ld   b,MAG_SIZE
.one:           push bc
                ld   a,MAG_SIZE
                sub  b                      ; index of this indicator
                cp   c
                ld   a,PEN_AMMO_FULL
                jr   c,.set
                ld   a,PEN_AMMO_EMPTY
.set:           ld   (BLK_VAL),a
                call DRAW_BLOCK
                ld   a,(BLK_X)
                add  a,5
                ld   (BLK_X),a
                pop  bc
                djnz .one
                ret

; ---------------------------------------------------------------------
; LAMPS - the Module 1 liveness indicators.
;   heartbeat toggles every 25 frames  -> the main loop is running
;   interrupt lamp green while ticking -> IM 1 is firing
; ---------------------------------------------------------------------
LAMPS:          ld   a,(FRAME_COUNT)
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
                ld   a,4
                ld   (BLK_X),a
                call LAMP_BLOCK
.skip_beat:
                ld   a,(IRQ_TICKS)
                ld   hl,IRQ_LAST
                cp   (hl)                   ; unchanged across a whole frame?
                ld   (hl),a
                ld   a,PEN_RED              ; then the interrupt is dead
                jr   z,.irq_done
                ld   a,PEN_GREEN
.irq_done:      ld   (BLK_VAL),a
                ld   a,16
                ld   (BLK_X),a
                ; fall through

LAMP_BLOCK:     ld   a,56
                ld   (BLK_LINE),a
                ld   a,8
                ld   (BLK_HEIGHT),a
                ld   a,8
                ld   (BLK_W),a
                jp   DRAW_BLOCK

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
; DRAW_COLOUR_BARS - 16 bars, one per pen, 5 bytes wide, 32 lines tall.
; Proves the Mode 0 encoding, the palette write and the VRAM addressing
; in one picture: bar N must read back as pen N.
; ---------------------------------------------------------------------
DRAW_COLOUR_BARS:
                ld   hl,PEN_SOLID
                xor  a
                ld   (BLK_X),a
                ld   (BLK_LINE),a
                ld   a,32
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
                ld   a,36
                ld   (BLK_LINE),a
                ld   a,16
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

; ---------------------------------------------------------------------
; DRAW_STRIPES - the background Kara walks over. Six pens in rotation, so
; a blitter that loses a byte, shifts a line or restores the wrong row
; shows up as a broken stripe rather than as nothing at all.
; ---------------------------------------------------------------------
DRAW_STRIPES:   ld   a,STRIPE_TOP
                ld   (BLK_LINE),a
                ld   a,8
                ld   (BLK_HEIGHT),a
                xor  a
                ld   (BLK_X),a
                ld   a,SCREEN_WIDTH_BYTES
                ld   (BLK_W),a
                ld   hl,STRIPE_PENS
                ld   b,STRIPE_BANDS
.band:          push bc
                push hl
                ld   a,(hl)
                ld   (BLK_VAL),a
                call DRAW_BLOCK
                ld   a,(BLK_LINE)
                add  a,8
                ld   (BLK_LINE),a
                pop  hl
                inc  hl
                pop  bc
                djnz .band
                ret

STRIPE_PENS:    db &0C, &3C, &03, &0F, &33, &3F      ; pens 2, 6, 8, 10, 12, 14
                db &0C, &3C, &03, &0F, &33, &3F
                db &0C, &3C

                include "bank.asm"
                include "screen.asm"
                include "palette.asm"
                include "sprite.asm"
                include "bullets.asm"

; ---------------------------------------------------------------------
; Core variables
; ---------------------------------------------------------------------
FRAME_COUNT:    db 0
HEARTBEAT:      db PEN_GREEN
IRQ_TICKS:      db 0
IRQ_LAST:       db 0
BANK_RESULT:    ds 5

KARA_X:         db 0
KARA_Y:         db KARA_HOME_Y
KARA_FRAME:     db 0
KARA_FACING:    db 1                    ; 1 = right, 0 = left
KARA_STEP:      db 0
KARA_LAST_ADDR: dw 0
FIRE_TIMER:     db 0

                ; SPR_DRAW_SAVE advances the sprite pointer with INC L, so
                ; every frame has to start on a 16-byte boundary.
                align 16
KARA_SPRITES:   incbin "kara_sprites.bin"

CORE_END:
CORE_SIZE       equ  CORE_END - CORE_START
