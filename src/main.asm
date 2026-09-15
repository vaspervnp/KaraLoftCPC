; =====================================================================
; Kara Loft and the Illuminati
; MODULE 4 - hardware scrolling engine over a banked tilemap
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
; After DEMO_TIMER frames it switches to the Module 4 screen: the city
; tilemap, scrolled by the CRTC start address, right then down then up.
;
; The border turns red for exactly as long as the frame's drawing takes,
; which is how tools/test_module3.py measures the T-state cost.
; =====================================================================

                include "config.asm"

; Save-under buffers live in the sprite-buffer region of the memory map,
; not in the core image, so they cost nothing on disc.
KARA_SAVE       equ &8000               ; 384 bytes
BUL_SAVE        equ &8180               ; 56 bytes
SPAN_SCRIPT     equ &8200               ; the span blitter's erase script,
                                        ; which is also its save-under

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
MARK_COLUMN     equ 18                  ; bright green - the column head
MARK_TAIL       equ 24                  ; magenta - the column tail

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

                ; The Module 1-3 acceptance screen runs for a while, then
                ; hands over to the scrolling demo for good. Tests that
                ; want one or the other poke DEMO_TIMER.
                ld   hl,(DEMO_TIMER)
                dec  hl
                ld   (DEMO_TIMER),hl
                ld   a,h
                or   l
                jp   z,SCROLL_DEMO
                jp   MAIN_LOOP

; =====================================================================
; MODULE 4 demo - the city scrolls under CRTC control.
;
; Kara is deliberately not drawn here. Her blitter walks the screen with
; a fixed +&0800 / +&C050 step, which is only the right arithmetic while
; the start address is zero; over a scrolled screen a sprite has to take
; its address from the same masked word index the tile engine uses. That
; is the first job of Module 5, and doing it badly would be worse than
; not doing it - see CLAUDE.md 8.2.
; =====================================================================
; ---------------------------------------------------------------------
; WHICH OF KARA'S LINES THE ERASE HAS TO WAIT FOR.
;
; The erase walks top-down and so does the beam, so whether the first or
; the last line is the binding one is decided by which of them is
; faster per line. The raster spends 256 T on a line. Measured:
;
;   full-width restore, 8 LDIs a line     241 T a line  - FASTER
;   clipped restore, per-line overhead    336-466 T     - SLOWER
;
; A restore that is faster than the beam starts behind it and closes the
; gap, so its LAST line is the one that must already have been
; displayed. A restore that is slower can only fall further behind, so
; clearing its FIRST line is enough - and that is worth having, because
; her first line can be 47 lines and 12,000 T earlier than her last.
;
; Waiting on the last line in both cases would be safe but would put a
; clipped erase after tick 6 with 22,000 T of work and only 16,800 T of
; frame left.
; ---------------------------------------------------------------------
                ; ... and the erase has to fit between tick 6 and the END
                ; of the next VSYNC pulse, not its start. SPR_RESTORE is
                ; 11,628 T, 14,172 when a character row straddles the
                ; 1024-word seam; tick 6 plus the worst case is 81,260,
                ; which is 1,388 T past the pulse's start and 2,700 T
                ; inside it. WAIT_VSYNC tests the level, not an edge, so
                ; that frame starts late but on the SAME pulse - no frame
                ; is dropped, and FRAME_TICK0 is stamped by the interrupt
                ; inside the pulse rather than by the loop, so the frame's
                ; raster gates stay correct even when it starts late.
                ; The pulse is 16 scanlines: measured 4,060 and 4,112 T.
                assert 67088 + 14172 < 79872 + 4060

SCROLL_DEMO:    di
                xor  a
                call SCREEN_CLS
                call SCROLL_INIT
                call INPUT_INIT
                call PLAYER_TO_SCREEN
                ei

                ; THE FRAME IS A BEAM CHASE, and this is its schedule. The
                ; beam reaches display line L about 15,400 + 256 L T after
                ; WAIT_VSYNC returns on the headless emulator (60 border
                ; scanlines) and 18,432 + 256 L on a 6845 programmed the
                ; way the firmware leaves it (72). Everything below that
                ; must be AHEAD of the beam is timed to the early figure,
                ; everything that must be BEHIND it to the late one.
                ;
                ;  - KARA_DRAW goes first, in the border, for the position
                ;    PLAYER_TO_SCREEN worked out last frame. At ~560 T a
                ;    line against the raster's 256 she only wins on a
                ;    lead, and the whole top border is that lead: she is
                ;    safe for any KARA_Y >= 13.
                ;  - the incoming column is not painted here at all: its
                ;    top 18 rows went in BEHIND the beam last frame
                ;    (H_HEAD), the last 6 go in now, ~45,000 T ahead of
                ;    the raster (H_TAIL).
                ;  - input, physics and the camera decision for the NEXT
                ;    frame sit in the middle, where nothing is urgent.
                ;  - H_HEAD waits for interrupt tick 4 (40,468 T): the
                ;    earliest moment every cell it touches is behind the
                ;    beam. See tilemap.asm.
                ;  - KARA_ERASE must trail the beam past her last line,
                ;    and still finish before the next VSYNC. The CPC has
                ;    no raster register, so the IM 1 interrupt is the only
                ;    clock and the gate is a WHOLE tick, picked from her
                ;    Y: 52 scanlines of granularity. A finer gate is not
                ;    worth having. A delay loop after the tick can only
                ;    measure from the moment it is entered, so a second
                ;    one in the same frame adds its whole wait on top of
                ;    the work between them: splitting the erase into two
                ;    halves that way put the lower half 13,600 T late and
                ;    dropped a frame on 12 scrolling frames out of 58.
                ;
                ;    Ticks, measured from the WAIT_VSYNC exit:
                ;      tick 1     532 T | tick 4  40,468 T
                ;      tick 2  13,844 T | tick 5  53,780 T
                ;      tick 3  27,152 T | tick 6  67,088 T
.loop:          call WAIT_VSYNC
                call SCROLL_VBLANK          ; R12/R13 may only be written here:
                call H_COMMIT               ; vertical, then horizontal

                ld   a,MARK_SPRITE
                call BORDER_SET
                call KARA_DRAW              ; ahead of the beam, in the border
                ld   a,MARK_TAIL
                call BORDER_SET
                call H_TAIL                 ; rows 18-23 of the committed column

                ld   a,MARK_LOGIC
                call BORDER_SET
                di
                call INPUT_SCAN             ; the AY address latch is shared
                ei                          ; with the sound chip
                call PLAYER_UPDATE
                call CAMERA_DECIDE          ; requests next frame's step
                call SCROLL_SERVICE         ; a vertical step in flight
                call PLAYER_TO_SCREEN       ; where she goes, in that view

                ld   a,MARK_IDLE
                call BORDER_SET
                ld   c,4
                call TICK_WAIT
                ld   a,MARK_COLUMN
                call BORDER_SET
                call H_HEAD                 ; rows 0-17, behind the beam

                ld   a,MARK_IDLE
                call BORDER_SET
                ld   hl,(KARA_LAST_ADDR)    ; culled: nothing to wait for
                ld   a,h
                or   l
                jr   z,.erased
                ld   a,(KARA_CLIP_W)        ; WHICH of her lines binds depends
                cp   SPR_WIDTH_BYTES        ; on which lane the erase will use
                ld   a,(KARA_LAST_BOT)      ; - see below
                jr   z,.gate
                ld   a,(KARA_LAST_TOP)
.gate:          call RASTER_WAIT
                ld   a,MARK_ERASE
                call BORDER_SET
                call KARA_ERASE
.erased:

                ld   hl,FRAME_COUNT
                inc  (hl)
                jp   .loop

; ---------------------------------------------------------------------
; RASTER_WAIT - spin until the beam has FINISHED display line A.
;
; The CPC has no raster register, so this is the IM 1 interrupt as an
; anchor plus a counted delay for the remainder. The interrupts fall at
; scanlines 2, 54, 106, 158, 210 and 262 after the VSYNC exit - measured,
; not assumed - and line A is finished at scanline A + 73 on the late
; (72-border) model. So: wait for the last tick at or before that, then
; delay the difference at 8 turns of a 32 T loop a scanline.
;
; *** ONE OF THESE PER FRAME, AND IT MUST BE THE LAST THING THAT WAITS.
; The delay can only count from the moment it starts, so a second call
; with work in between adds its whole remainder on top of that work.
; That is exactly how the erase came to run 13,600 T late and drop a
; frame on 12 scrolling frames out of 58. ***
;
; Arriving late is otherwise safe: the remainder is counted from a tick
; that has already gone by, so the answer is only ever later than asked
; for, never earlier.
;
; IN : A = display line 0-191                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
RASTER_WAIT:    add  a,73 - 2               ; scanlines past tick 1 (line 2)
                ld   c,1
.tick:          cp   52                     ; one tick is 52 scanlines
                jr   c,.rem
                sub  52
                inc  c
                jr   .tick
.rem:           ld   l,a                    ; C = the tick, A = lines past it
                ld   h,0
                add  hl,hl
                add  hl,hl
                add  hl,hl                  ; 8 turns of 32 T = 256 T = a line
                push hl
                call TICK_WAIT
                pop  hl
                ld   a,h
                or   l
                ret  z
.delay:         dec  hl                     ; 8
                nop                         ; 4   measured at 28 T without it
                ld   a,h                    ; 4
                or   l                      ; 4
                jr   nz,.delay              ; 12  = 32 T a turn
                ret

; ---------------------------------------------------------------------
; TICK_WAIT - spin until C interrupt ticks have passed since FRAME_TICK0.
; Returns at once if they already have.       destroys AF,HL
; ---------------------------------------------------------------------
TICK_WAIT:      ld   a,(IRQ_TICKS)
                ld   hl,FRAME_TICK0
                sub  (hl)                   ; wraps cleanly for small values
                cp   c
                jr   c,TICK_WAIT
                ret

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

; IN: A = top line, C = rounds left        Clobbers AF, BC, DE, HL
;
; One pass over the whole row rather than seven DRAW_BLOCK calls. The
; seven indicators are 3 bytes wide on a 5-byte pitch, so a scanline is
; 21 writes and six 2-byte gaps - ONE address computation for the row
; instead of one per indicator per scanline. That is the difference
; between 49,040 T (61% of a frame, every time a shot is fired) and the
; number now in CLAUDE.md 9.
;
; Scroll-correct vertically (SCR_NEXT_LINE carries the raster rule), but
; the 33-byte horizontal run is NOT seam-tested: it assumes the row does
; not cross offset 2047. True wherever the HUD is drawn today, which is
; the unscrolled Module 1-3 screen. The scrolling game needs a
; split-screen HUD anyway - that is Module 6's R12/R13 mid-frame change.
HUD_ROW:        push bc                     ; C = rounds left
                ld   c,4                    ; byte column of indicator 0
                call SCR_ADDR               ; HL = its address under SCROLL
                pop  bc
                ex   de,hl                  ; DE = line base
                ld   a,8
                ld   (HUD_LINES),a

.line:          ld   h,d                    ; working copy - DE keeps the base
                ld   l,e
                ld   b,MAG_SIZE
.ind:           ld   a,MAG_SIZE
                sub  b                      ; index of this indicator
                cp   c
                ld   a,PEN_AMMO_FULL
                jp   c,.set
                ld   a,PEN_AMMO_EMPTY
.set:           ld   (hl),a                 ; 3 bytes of indicator
                inc  hl
                ld   (hl),a
                inc  hl
                ld   (hl),a
                inc  hl
                inc  hl                     ; 2 bytes of gap
                inc  hl
                djnz .ind

                call SCR_NEXT_LINE
                ld   hl,HUD_LINES
                dec  (hl)
                jp   nz,.line
                ret

HUD_LINES:      db 0

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
                push bc
                ld   bc,PPI_PORT_B * 256
                in   a,(c)
                rra                         ; carry = VSYNC still up: this is
                ld   a,(IRQ_TICKS)          ; tick 1, 2 scanlines into the pulse
                inc  a
                ld   (IRQ_TICKS),a
                jr   nc,.counted
                dec  a                      ; FRAME_TICK0 = the count before
                ld   (FRAME_TICK0),a        ; tick 1. Stamped HERE and not in
.counted:       pop  bc                     ; the main loop, so a frame that
                pop  af                     ; starts late (WAIT_VSYNC returns at
                ei                          ; once inside the 16-line pulse) can
                ret                         ; not shift every raster gate by a
                                            ; tick for the rest of the run.

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
                include "spanblit.asm"
                include "bullets.asm"
                include "input.asm"
                include "collide.asm"
                include "player.asm"
                include "tilemap.asm"

; ---------------------------------------------------------------------
; Cross-module invariants. They live here, after every include, because
; RASM evaluates ASSERT eagerly in source order - a forward reference to
; a symbol from a later include fails even though instructions that
; reference it resolve fine in a later pass.
;
; Note AND, not "&": under -amper (which build.sh requires) "& 15"
; parses as the hex literal &15 and the assert reports a bogus failure.
; ---------------------------------------------------------------------
                ; ROW_OFFSETS is read as "char row * 80 bytes" by
                ; DRAW_BLOCK and as "char row * 40 CRTC words" by
                ; SCR_ADDR. Those are the same number only while R1 = 40.
                assert SCR_CHARS * 2 == SCREEN_WIDTH_BYTES
                ; SCR_ADDR indexes ROW_OFFSETS with ADD A,L over 64 bytes.
                assert (ROW_OFFSETS AND 63) == 0
                ; SPAN_EMIT indexes SPAN_ENTRY by writing the count into
                ; the low byte of the address it reads, and patches only
                ; the low byte of the jump into SPAN_RUN. So the table
                ; has to start a page and the whole run has to stay in
                ; one - both are alignment accidents waiting to happen
                ; the next time anything above them grows.
                assert (SPAN_ENTRY AND 255) == 0
                assert (SPAN_RUN AND &FF00) == (SPAN_RUN_END AND &FF00)
                assert SPAN_SCRIPT + SPAN_SCRIPT_MAX <= BUL_SAVE + &1000

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
KARA_LAST_TOP:  db 0            ; her first and last DRAWN screen lines,
KARA_LAST_BOT:  db 0            ; which clipping makes different from Y, Y+47
KARA_SAVE_PTR:  dw 0            ; where in KARA_SAVE the drawn part starts
KARA_CLIP_W:    db 0            ; the drawn rectangle, so KARA_ERASE can
KARA_CLIP_H:    db 0            ; replay exactly what KARA_DRAW wrote
CLIP_SY0:       db 0            ; ... and the working state both lanes use
CLIP_SX0:       db 0
CLIP_SLINE:     db 0
CLIP_OFF:       dw 0
CLIP_ADDR:      dw 0
CLIP_SPR:       dw 0
CLIP_SAVE:      dw 0
CLIP_STEP:      dw 0
FIRE_TIMER:     db 0
DEMO_TIMER:     dw 600                  ; frames of Module 1-3 screen
DEMO_PHASE:     db 0                    ; 0 = right, 1 = down, 2 = up
DEMO_PHASE_T:   db 0
FRAME_TICK0:    db 0

                ; SPR_DRAW_SAVE advances the sprite pointer with INC L, so
                ; every frame has to start on a 16-byte boundary.
                align 16
KARA_SPRITES:   incbin "kara_sprites.bin"
                ; The fast blitter lane walks a 16-byte line with INC L.
                assert (KARA_SPRITES AND 15) == 0

                ; Level data rides inside the core image, so the boot
                ; relocation lands it in base RAM - which is the only
                ; reason TILES_INSTALL can LDIR it into the &4000 window.
                ; The two must stay adjacent and in this order.
CITY_TILES:     incbin "city_tiles.bin"
CITY_MAP:       incbin "city_map.bin"

CORE_END:
CORE_SIZE       equ  CORE_END - CORE_START
