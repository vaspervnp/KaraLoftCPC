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
ENEMY_SCRIPT    equ &8700               ; ... and the one enemy on screen has
                                        ; its own, the same size
EBUL_SAVE       equ &81C0               ; their rounds, 4 bytes a slot

KARA_HOME_Y     equ 96          ; the line the DEV SCREEN draws her on, and
                                ; nothing to do with KARA_BOX_H: that screen
                                ; runs the 16x48 placeholder path, not the
                                ; span blitter, and 96 puts it in the middle
                                ; of the stripes at 64-175
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

                ; ... and the level image after it, which is NOT part of
                ; the core and must not be: see the note by LEVEL_IMAGE.
                ; Its source straddles &8000 and its destination is well
                ; clear of it, so this is the same plain LDIR - but it
                ; can only run here, while the window is still the
                ; configuration the line above set and before LEVEL_LOAD
                ; pages a bank over it.
                ld   hl,LEVEL_FILE
                ld   de,LEVEL_IMAGE
                ld   bc,LEVEL_SIZE
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
                jp   SCROLL_DEMO            ; ... and straight to the roof

; ---------------------------------------------------------------------
; INTRO_SCREEN - the Module 1-3 acceptance screen: colour bars, the
; bank self-test's verdict, the stripe background, and Kara walking and
; firing over it out of the 16x48 placeholder blitter.
;
; IT IS NO LONGER ON THE WAY IN. The game starts on the rooftop; this
; is a development screen, kept because the whole of module 3 -
; sprite.asm, the HUD, the bullet pool's drawing - is still tested
; against it by tools/test_module3.py, which enters here directly. It
; puts the CRTC and the start address back the way it needs them,
; because the scrolling demo will have moved both.
; ---------------------------------------------------------------------
INTRO_SCREEN:   di
                ; Her position is the scrolling demo's by now - the boot
                ; goes there first - so put it back where this screen's
                ; own checks expect her.
                xor  a
                ld   (KARA_X),a
                ld   (KARA_FRAME),a
                ld   (RELOAD_TIMER),a
                ld   (BUL_LIVE),a           ; the pool's save-under belongs to
                ld   (BUL_DREW),a           ; a screen that is about to go,
                ld   (BUL_TOP),a            ; and so does how deep it went
                ld   (BUL_DREW_TOP),a
                ld   hl,BULLETS
                ld   de,BULLETS + 1
                ld   bc,BUL_MAX * BUL_STRIDE - 1
                ld   (hl),0
                ldir
                ld   (KARA_FACING),a        ; A is still 0: she walks right
                ld   (KARA_STEP),a          ; here, and the demo's firing
                ld   (FIRE_TIMER),a         ; timer starts from the top
                ld   a,MAG_SIZE
                ld   (MAG_LEFT),a
                ld   (MAG_RIGHT),a
                ld   a,BUL_MAX * 2
                ld   (AMMO_RESERVE),a
                ; AND NO MAP, because this screen is not a level. The
                ; city's map is still installed from the boot's level
                ; load, and a round's tile probe (bullets.asm) would
                ; read it through a WORLD_X that means nothing here -
                ; every shot died on a "wall" the moment it left the
                ; muzzle. Tile 0 is sky, and SCROLL_DEMO installs the
                ; real map again on the way back.
                ld   hl,MAP_ADDR
                ld   de,MAP_ADDR + 1
                ld   bc,MAP_W * MAP_H - 1
                ld   (hl),0
                ldir
                call BUFFERS_CLEAR
                ld   a,KARA_HOME_Y
                ld   (KARA_Y),a
                ld   hl,0
                ld   (SCROLL),hl
                call SCROLL_APPLY
                ld   b,CRTC_R6
                ld   c,25                   ; the firmware's own height
                call CRTC_SET
                xor  a
                call SCREEN_CLS
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

                ; The dev screen hands back to the scrolling demo when
                ; DEMO_TIMER runs out; tools/test_module3.py pins it open.
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

                ; THE REAL ART, off the disc. Level 1's gameplay set puts
                ; kcore in &C5 and kcore_l in &C6 - pinned there by
                ; tools/level_banks.py so the facing is one OUT - and the
                ; city tiles in &C4, which the placeholder tileset then
                ; goes back over. That order is deliberate: the 8x16
                ; tiles the art package ships need the addressing rewrite
                ; of CLAUDE.md 8.3, so the demo still scrolls the 16x16
                ; stand-ins while Kara herself is the drawn sprite.
                xor  a                      ; 0 = level 1, gameplay
                call LEVEL_LOAD
                ld   a,1
                jr   c,.loaded
                ; IT FAILED, AND THAT MUST NOT BE A BLACK SCREEN. The
                ; banks now hold whatever was in them, so drawing her out
                ; of one paints noise over the picture - the demo runs
                ; without her instead, and the controller's own words go
                ; on the top of the screen so the failure can be read off
                ; a photograph. See docs/AmstradDskReadHowTo.md.
                xor  a
.loaded:        ld   (LEVEL_OK),a
                ; Full guns for the level: the Module 1-3 screen fires
                ; on a timer for a minute and leaves both magazines dry,
                ; and a dry gun goes to START_RELOAD instead of firing.
                ld   a,MAG_SIZE
                ld   (MAG_LEFT),a
                ld   (MAG_RIGHT),a
                xor  a
                ld   (RELOAD_TIMER),a
                call SCROLL_INIT            ; ... which installs the map
                ld   a,(LEVEL_OK)
                or   a
                call z,DISC_DIAG
                call INPUT_INIT
                call PLAYER_TO_SCREEN
                ; THE BORDER STAYS BLACK IN THE GAME. The coloured bands
                ; are a DEVELOPMENT instrument - they belong to the
                ; Module 1-3 screen, which tools/test_module3.py profiles
                ; from them - and down here they are eight colour changes
                ; a frame flickering down the left edge of a night-time
                ; city. They also cost about 560 T a frame that the frame
                ; would rather have, and CLAUDE.md 9 says not to profile
                ; from them anyway: they under-report by the 40 scanlines
                ; the emulator paints as colour 0 in vblank.
                ld   a,MARK_IDLE            ; black
                call BORDER_SET
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
                call ENEMY_PICK             ; which one is in view UNDER THE
                                            ; view just latched - see the note
                                            ; on ENEMY_UPDATE
                ld   a,(LEVEL_OK)
                or   a
                call nz,KARA_SPAN_DRAW      ; ahead of the beam, in the border
                call BUL_DRAW               ; over her: she fires past herself
                call EBUL_DRAW              ; ... and so do they
                call H_TAIL                 ; rows 18-23 of the committed column

                di
                call INPUT_SCAN             ; the AY address latch is shared
                ei                          ; with the sound chip
                call PLAYER_UPDATE
                call ENT_UPDATE             ; what she has walked into
                call ACT_UPDATE             ; ... which cel that makes her,
                call ENEMY_UPDATE           ; the one in view, and their fire
                call UPDATE_BULLETS         ; and whether one just left
                call ENEMY_SHOT_CHECK       ; ... and whether it landed
                call UPDATE_RELOAD
                call CAMERA_DECIDE          ; requests next frame's step
                call SCROLL_SERVICE         ; a vertical step in flight
                call PLAYER_TO_SCREEN       ; where she goes, in that view

                ld   c,4
                call TICK_WAIT
                call H_HEAD                 ; rows 0-17, behind the beam

                ld   a,(LEVEL_OK)
                or   a
                jr   z,.erased              ; she was never drawn
                ; The span erase replays the script the draw wrote, run
                ; by run, so there is no fast/slow lane to choose
                ; between any more: the beam only has to be past the
                ; last DRAWN line, which the draw recorded after
                ; clipping.
                ;
                ld   a,(KARA_LAST_CNT)      ; culled: she left no script, but
                or   a                      ; the rounds still have to come up
                jr   z,.bullets_only
                ld   a,(KARA_LAST_BOT)
                call RASTER_WAIT
                call EBUL_ERASE             ; reverse draw order: the rounds
                call BUL_ERASE              ; went down over her
                call KARA_SPAN_ERASE
                jr   .erased
.bullets_only:  call EBUL_ERASE
                call BUL_ERASE
.erased:        ; ... and NOW the things that change the BACKGROUND, once
                ; every sprite has been lifted off it: the cell a taken
                ; pickup left behind, and the enemy, which is a
                ; persistent sprite where she is not. See enemy.asm.
                call ENT_REPAINT_DUE
                call ENEMY_REFRESH

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
; IN : A = display line 0-191 - and 185-191 need the wrap fixup
;      below, which is why C is loaded before the ADD
;                                           destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
RASTER_WAIT:    ld   c,1
                add  a,73 - 2               ; scanlines past tick 1 (line 2)
                jr   nc,.tick

                ; DISPLAY LINE 185 AND UP OVERFLOWS THE BYTE: the sum is
                ; 256-262 and comes back as 0-6, which reads as tick 1.
                ; The erase then runs ~65,000 T EARLY - it wipes her
                ; before the beam has reached her, and she is simply
                ; absent from the bottom third of the picture. Invisible
                ; while the sprite was 48 lines and the camera kept her
                ; clear; a 64-line sprite reaches it in ordinary play.
                ; 256 scanlines is four ticks and 48 more, so put it
                ; back as exactly that.
                add  a,48
                ld   c,5
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

                ; ARRIVING LATE MUST NOT COST THE WHOLE REMAINDER AGAIN.
                ; The delay below can only count from the moment it is
                ; entered, so a caller that reaches here a tick or two
                ; after the one it asked for used to wait its 50-odd
                ; scanlines on top of however long it took to get here.
                ; Harmless while the frame had room; with the action
                ; state machine in it that was 13,000 T of a 79,872 T
                ; frame spent waiting for a beam that had gone by 23,000
                ; T earlier, and the loop dropped 6 frames in 200 while
                ; scrolling. Each whole tick late is 52 scanlines of
                ; beam already owed to us.
                ld   a,(IRQ_TICKS)
                ld   de,FRAME_TICK0
                ld   b,a
                ld   a,(de)
                neg
                add  a,b                    ; ticks since the VSYNC exit
                sub  c                      ; ... past the one asked for
                jr   z,.owed
                jr   c,.owed                ; earlier: TICK_WAIT saw to it
                ld   b,a
.catch:         ld   de,-52 * 8             ; a tick is 52 scanlines
                add  hl,de
                jr   nc,.none               ; the beam is already past it
                djnz .catch
.owed:          ld   a,h
                or   l
                ret  z
                jr   .delay
.none:          ret

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
                jp   ENT_CLEAR              ; the table and its erase chain

; ---------------------------------------------------------------------
; DISC_DIAG - the controller's three result bytes, as 24 blocks.
;
; There is no text output in this build and a failed load is otherwise
; silent, so ST0, ST1 and ST2 go on the top-left of the screen as one
; row of eight blocks each, bit 7 leftmost: white for a set bit, dark
; for a clear one. A photograph of the screen is then a complete bug
; report - which is exactly how the two FDC faults in
; docs/AmstradDskReadHowTo.md were finally pinned down.
;
; Read it as: ST0 bits 7-6 are the interrupt code, bit 3 NOT READY.
; ST1 bit 7 END OF CYLINDER (normal), bit 5 data error, bit 4 overrun,
; bit 2 sector not found, bit 0 missing address mark.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
DISC_DIAG:      ld   hl,DISC_ST0
                ld   de,0                   ; D = row, E unused
.row:           ld   a,(hl)
                ld   c,a                    ; C = the byte being shown
                push hl
                ld   a,d
                add  a,a
                add  a,a
                add  a,a                    ; row * 8 scanlines
                ld   (BLK_LINE),a
                ld   a,8
                ld   (BLK_HEIGHT),a
                ld   a,2
                ld   (BLK_W),a
                ld   b,8                    ; eight bits, 7 first
.bit:           ld   a,8
                sub  b
                add  a,a
                add  a,a                    ; bit index * 4 byte columns
                ld   (BLK_X),a
                rlc  c                      ; bit 7 into carry, and round
                ld   a,&00                  ; pen 0
                jr   nc,.dark
                ld   a,&FF                  ; pen 15 in both pixels
.dark:          ld   (BLK_VAL),a
                push bc
                call DRAW_BLOCK
                pop  bc
                djnz .bit
                pop  hl
                inc  hl
                inc  d
                ld   a,d
                cp   3
                jr   c,.row
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
                include "unpack.asm"
                include "disc.asm"
                include "levels/disc.inc"
                include "levels/banks.inc"
                include "levels/spawns.inc"
                ; The pickups' art, for ENT_ART. Level 1's own sheet and
                ; the shared HUD icons - module 6 makes this per level,
                ; with the rest of the level's table.
                include "levels/level1_city/citypickups.inc"
                include "levels/_shared/hudicon.inc"
                include "levels/level1_city/cityagent.inc"
                include "levels/level1_city/citydrone.inc"
                include "levels/_shared/kcore.inc"
                include "levels/_shared/kact.inc"
                include "kara.asm"
                include "levels/_shared/kextra.inc"
                include "action.asm"
                include "entity.asm"
                include "enemy.asm"
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
                ; The back view is the TAIL of the action blob, which is
                ; what lets KARA_SETS bound the second facing with one
                ; number. tools/build_levels.py builds the two blobs from
                ; the same tag list minus that tail, and test_spans.py
                ; checks the left blob's frames really are the right
                ; blob's first KACT_CLIMB_FIRST.
                assert KACT_TWO_FACED + KACT_CLIMB_COUNT == KACT_FRAMES
                assert KACT_TWO_FACED == KACT_CLIMB_FIRST
                assert (SPAN_ENTRY AND 255) == 0
                assert (SPAN_RUN AND &FF00) == (SPAN_RUN_END AND &FF00)
                assert SPAN_SCRIPT + SPAN_SCRIPT_MAX <= BUL_SAVE + &1000
                ; ENT_BAKE_ONE indexes ENT_ART the same way, and
                ; ENT_OVERLAP indexes ENT_HITBOX - both need every row
                ; in the SAME PAGE as the label, not merely aligned.
                assert (ENT_ART AND 255) + ENT_ART_KINDS * ENT_ART_BYTES <= 256
                assert (ENT_HITBOX AND 255) + EK_COUNT * 2 <= 256
                ; ENEMY_TYPE_AT does the same with a 32-byte stride, and
                ; the WHOLE table has to sit in one page: ADD A,low
                ; discards the carry, so a table that straddles a page
                ; boundary silently reads the wrong row.
                assert EN_T_STRIDE == 32
                assert (ENEMY_TYPES AND 255) + EN_KINDS * EN_T_STRIDE <= 256
                assert EN_T_USED <= EN_T_STRIDE
                assert ENEMY_TYPES_END - ENEMY_TYPES == EN_KINDS * EN_T_STRIDE
                ; The enemy's script sits above hers and below the round
                ; saves' ceiling, like every other buffer up there.
                assert ENEMY_SCRIPT >= SPAN_SCRIPT + SPAN_SCRIPT_MAX
                assert ENEMY_SCRIPT + SPAN_SCRIPT_MAX <= BUL_SAVE + &1000
                assert EBUL_SAVE >= BUL_SAVE + BUL_MAX * 4
                assert EBUL_SAVE + EBUL_MAX * 4 <= SPAN_SCRIPT
                ; The scratch tiles are addressed as tile indices, which
                ; needs them 64-aligned, and tools/level_banks.py must be
                ; holding back exactly as much of C4 as they take.
                assert (ENT_BAKE_ADDR AND 63) == 0
                assert ENT_BAKE_ADDR + ENT_BAKE_MAX * TILE_BYTES == &8000
                assert ENT_BAKE_TILE0 == 240
                ; FDC_DRAIN walks ST0..SPILL with INC L and compares the
                ; low byte, so the four have to be adjacent and in one
                ; page. Move one and the drain writes ST1 over whatever
                ; happens to follow.
                ; MAP_CELL builds the map address by shifting a page
                ; number left three times, so the map has to start on
                ; a 2 KB boundary - and it must not be inside the
                ; staging buffer a level load writes over.
                assert (MAP_ADDR AND 2047) == 0
                assert MAP_ADDR >= LEVEL_STAGE + LEVEL_STAGE_MAX
                assert MAP_ADDR + MAP_W * MAP_H <= STACK_TOP - 256
                assert DISC_ST1 == DISC_ST0 + 1
                assert DISC_ST2 == DISC_ST0 + 2
                assert DISC_SPILL == DISC_ST0 + 3
                assert (DISC_ST0 AND &FF00) == (DISC_SPILL AND &FF00)

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
KARA_STATE:     db KST_IDLE     ; CLAUDE.md 8.4 - see action.asm
KARA_SET:       db KSET_CORE    ; which blob KARA_FRAME counts in
KARA_TIMER:     db 1            ; 50 Hz frames left on this cel
KARA_DONE:      db 0            ; a held run has reached its last cel
KARA_FRAME:     db 0
KARA_FACING:    db 0                    ; 0 = RIGHT, 1 = left - the way
                                        ; player.asm writes it, and the
                                        ; way kara.asm indexes KARA_SETS
KARA_STEP:      db 0
KARA_LAST_ADDR: dw 0
KARA_LAST_TOP:  db 0            ; her first and last DRAWN screen lines,
KARA_LAST_BOT:  db 0            ; which clipping makes different from Y, Y+63
KARA_LAST_CNT:  db 0            ; lines drawn; 0 = entirely off the display
KARA_ANIM:      db 0            ; index within the current tag's frames
LEVEL_OK:       db 0            ; did the disc load work? 0 = draw no sprite
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
DEMO_TIMER:     dw 600                  ; frames of the Module 1-3 dev screen,
                                        ; which nothing reaches any more unless
                                        ; it jumps to INTRO_SCREEN
DEMO_PHASE:     db 0                    ; 0 = right, 1 = down, 2 = up
DEMO_PHASE_T:   db 0
FRAME_TICK0:    db 0

                ; SPR_DRAW_SAVE advances the sprite pointer with INC L, so
                ; every frame has to start on a 16-byte boundary.
                align 16
KARA_SPRITES:   incbin "kara_sprites.bin"
                ; The fast blitter lane walks a 16-byte line with INC L.
                assert (KARA_SPRITES AND 15) == 0

                ; The MAP rides inside the core image, so the boot
                ; relocation lands it in base RAM - which is the only
                ; reason MAP_INSTALL can LDIR it to MAP_ADDR.
                ;
CORE_END:
CORE_SIZE       equ  CORE_END - CORE_START

; *** EVERYTHING ABOVE HERE IS RELOCATED TO &0040 AND MUST END BEFORE
; *** &4000, BECAUSE &4000 IS THE BANKED WINDOW (CLAUDE.md 6.1).
;
; There was no check on that and it went wrong silently. 2,240 bytes of
; map and entity table used to ride inside this image; the climb, the
; camera and the ladder pushed CORE_END to &4070, and the last 112 bytes
; of the entity table landed in bank C4 on top of the city's tile art.
; Nothing crashed. ENT_RECOUNT read tile bytes as flags, came back with
; 24 live entities instead of 10, and ENT_UPDATE swept fourteen slots of
; noise every other frame - 2,728 T a frame, which is what took the
; budget over. A corrupt entity table is cheaper to find than that.
                assert CORE_END <= BOOT_ADDR

; =====================================================================
; THE LEVEL IMAGE - the map and its entity table, 2,240 bytes.
;
; DATA, not code: copied into their working addresses at every level
; init and never executed, so there is no reason for them to be in an
; image that has to fit under &4000. The bootstrap drops them in base
; RAM at LEVEL_IMAGE and MAP_INSTALL takes its working copy from there -
; a working copy and not the original, because ENT_BAKE stamps each
; pickup into the map and a re-init needs the map it started with.
;
; Module 6 reads both out of level_<n>.lvl instead, which is the same
; LDIR from a different source (see MAP_INSTALL).
; =====================================================================
LEVEL_IMAGE     equ  &B000      ; above the map and its table, below the stack
LEVEL_FILE      equ  BOOT_END + CORE_SIZE   ; where the loader left the bytes

                org  LEVEL_IMAGE, LEVEL_FILE

LEVEL_START:
                ; THE TILES DO NOT COME THIS WAY ANY MORE. They are the
                ; level's own, unpacked into bank C4 by LEVEL_LOAD
                ; (tools/level_banks.py pins them at &4000 of it), and
                ; the 2 KB the stand-in sheet used to take of the core
                ; image goes back to the engine.
CITY_MAP:       incbin "city_map.bin"
                ; ... and the level's entities, in the eight-byte
                ; record docs/editor.md 9.2 fixes. The editor will
                ; write these; this is the same bytes by hand, so
                ; the engine's half of the format is exercised
                ; before a web application is built against it.
CITY_ENTITIES:  incbin "city_entities.bin"
LEVEL_END:
LEVEL_SIZE      equ  LEVEL_END - LEVEL_START

                assert CITY_MAP == LEVEL_IMAGE
                assert LEVEL_IMAGE + LEVEL_SIZE < STACK_TOP - 1024
                ; and it must not land on top of what it is copied INTO
                assert LEVEL_IMAGE >= ENT_TABLE + ENT_MAX * ENT_STRIDE
