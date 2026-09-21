; =====================================================================
; Kara Loft and the Illuminati
; MODULE 5 - the city, and the heroine in it
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
; RUN"DISC STARTS ON THE ROOFTOP. The core boots, self-tests its banks,
; loads level 1 off the disc and goes straight to SCROLL_DEMO: the city
; tilemap scrolled by the CRTC start address, with Kara drawn over it
; out of her span blobs, the entity table, the drones and the ladders
; down to the street.
;
; THE MODULE 1-3 ACCEPTANCE SCREEN IS GONE. It was colour bars, the bank
; self-test's verdict, a striped background and the 16x48 placeholder
; heroine walking over it, kept as a development screen long after the
; game stopped going through it - and it was the only caller of the
; 16x48 blitter, of the placeholder sheet png2sprite.py exported, and of
; the coloured border bands. All of it has been deleted; what the game
; needs of module 3 - the address model, the bullet pool, the HUD - is
; still here and is tested in the game rather than on a screen of its
; own.
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

KARA_HOME_Y     equ 96          ; the line KARA_Y starts on before a level
                                ; has placed her
HUD_LEFT_LINE   equ 180
HUD_RIGHT_LINE  equ 190
BORDER_BLACK    equ 20          ; the game's border, set once and left
BORDER_HURT     equ 12          ; ... except for the frames she is hit on
HURT_FRAMES     equ 2           ; and there are two of them - which is the
                                ; same 80 ms the old four were at 50 Hz

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

                ; ... AND THERE IS NO LEVEL IMAGE TO RELOCATE ANY MORE.
                ; A second LDIR used to bring level_1.lvl and its tile
                ; flags down to &B000 out of the binary. A level the
                ; game LOADS cannot come out of a binary, so they are on
                ; the disc with the art and LEVEL_MAP_LOAD reads them -
                ; see the note by LEVEL_IMAGE.

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
; The erase walks top-down and so does the beam, and which line binds is
; decided by which of them is faster. The raster spends 256 T on a line;
; the span erase spends about 97 plus 24 a span byte, so it is faster
; and CLOSES on the beam - the binding line is its last.
;
; That is not the same as waiting for the beam to clear her last line,
; which is what this used to do and which waits her whole height too
; long. The gate in the loop is her FIRST line plus the measured lead
; the run needs to stay behind the beam all the way down.
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
                ; THE TITLE FIRST, AND THE PROMPT AFTER THE LOAD. The
                ; picture is five sectors and goes straight into video
                ; RAM (src/intro.asm); the 1.6 s LEVEL_LOAD below then
                ; runs with it on the screen and with interrupts off,
                ; which is exactly why "PRESS SPACE OR FIRE" is not put
                ; up until afterwards - nothing could answer it.
                call INTRO_SHOW

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
                jr   nc,.failed
                ; ... AND THE LEVEL'S OWN BYTES, which used to be in the
                ; binary. Both are disc reads with interrupts off and
                ; nothing on the screen but the title, so they go one
                ; after the other; the map has to be second only because
                ; a failed art read leaves the banks full of noise and
                ; there is no point reading a map for a level that
                ; cannot be drawn.
                xor  a                      ; 0 = level 1
                call LEVEL_MAP_LOAD
                ld   a,1
                jr   c,.loaded
                ; IT FAILED, AND THAT MUST NOT BE A BLACK SCREEN. The
                ; banks now hold whatever was in them, so drawing her out
                ; of one paints noise over the picture - the demo runs
                ; without her instead, and the controller's own words go
                ; on the top of the screen so the failure can be read off
                ; a photograph. See docs/AmstradDskReadHowTo.md.
                ;
                ; AND A MISSING MAP IS THE SAME ANSWER. LEVEL_MAP_LOAD
                ; returns carry clear for a level with no map on the
                ; disc as well as for a read that failed, and neither is
                ; a level: MAP_INSTALL would parse whatever &B000 holds.
.failed:        xor  a
.loaded:        ld   (LEVEL_OK),a
                ; Full guns for the level: the Module 1-3 screen fires
                ; on a timer for a minute and leaves both magazines dry,
                ; and a dry gun goes to START_RELOAD instead of firing.
                ld   a,MAG_SIZE
                ld   (MAG_LEFT),a
                ld   (MAG_RIGHT),a
                xor  a
                ld   (RELOAD_TIMER),a

                call INTRO_WAIT             ; ... and now it can be answered
                call PALETTE_SET            ; back off the artist's 16 colours
                xor  a
                call SCREEN_CLS
                call SCROLL_INIT            ; ... which installs the map
                jr   nc,.installed
                xor  a                      ; it refused: the bytes arrived
                ld   (LEVEL_OK),a           ; and were not a level
.installed:     ld   a,(LEVEL_OK)
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
                ld   a,BORDER_BLACK
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
                ; ---- SHE HAS JUST BEEN HIT --------------------------
                ; THE BORDER SAYS IT AS WELL AS THE BAR. There is an
                ; energy bar at the bottom left now (src/hud.asm), but it
                ; is six cells of twenty-four pixels and a hit can take
                ; less than one of them; four frames of red border say
                ; "that hurt" where the bar only says "this is how much
                ; is left". Two OUTs on the frames it changes and
                ; nothing on the rest, and it cannot be confused with
                ; the sprite the way flashing HER could.
                ld   hl,HURT_FLASH
                ld   a,(hl)
                or   a
                jr   z,.no_flash
                dec  (hl)
                ld   a,BORDER_HURT
                jr   nz,.flash
                ld   a,BORDER_BLACK         ; the last of them: put it back
.flash:         call BORDER_SET
.no_flash:      call H_COMMIT               ; the HORIZONTAL latch. R12/R13 may
                                            ; only be written in blanking, and
                                            ; the VERTICAL one is in the second
                                            ; sweep now - see the note there
                call ENEMY_PICK             ; which one is in view UNDER THE
                                            ; view just latched - see the note
                                            ; on ENEMY_UPDATE
                ; THE ROUNDS GO DOWN BEFORE SHE DOES, AND THE REASON IS
                ; THE BEAM. They used to be drawn over her - she fires
                ; past herself - and her draw is 32,000-40,000 T, so
                ; BUL_DRAW was reached 10,200 us into the frame with the
                ; beam already at display line 98. A round leaving her
                ; muzzle on the ROOF is at line 43-49, which the beam
                ; passed at 6,980 us: it was written to video RAM behind
                ; the beam and lifted off again at 13,400, so it was
                ; never displayed at all. Down on the STREET the same
                ; round is at line 113, the beam gets there at 11,076,
                ; and it shows - which is exactly how it was reported:
                ; "I only see the bullets at street level".
                ;
                ; Drawn first they are 500 us in, ahead of the beam
                ; everywhere. The price is her lead: BUL_DRAW is 1,876 T
                ; with a full pool and nothing at all with an empty one
                ; (bullets.asm), so while she is firing she is drawn up
                ; to seven scanlines later and her safe line moves with
                ; it. The erase order below is reversed to match.
                call BUL_DRAW
                call EBUL_DRAW
                ld   a,(LEVEL_OK)
                or   a
                call nz,KARA_SPAN_DRAW      ; ahead of the beam, in the border
                call H_TAIL                 ; rows 18-23 of the committed column
                ; ... and the energy bar, which lives on row 23 and is
                ; therefore AFTER her: the beam does not reach it until
                ; 65,536 T and she never overlaps it (src/hud.asm).
                call HUD_SERVICE

                di
                call INPUT_SCAN             ; the AY address latch is shared
                ei                          ; with the sound chip
                call PLAYER_UPDATE
                call ENT_UPDATE             ; what she has walked into
                call ACT_UPDATE             ; ... which cel that makes her,
                ; ... AND WHETHER THE LEVEL IS OVER. Here because both
                ; of the things it reads are THIS frame's and neither
                ; lasts: ENT_RESULT is written by the sweep above on
                ; every frame, and KARA_DONE is ACT_UPDATE's word that
                ; her `die` run has finished playing (src/flow.asm).
                call FLOW_CHECK
                call ENEMY_UPDATE           ; the one in view, and their fire
                call UPDATE_BULLETS         ; and whether one just left
                call ENEMY_SHOT_CHECK       ; ... and whether it landed
                call UPDATE_RELOAD
                call CAMERA_DECIDE          ; requests next frame's step
                call SCROLL_SERVICE         ; a vertical step in flight
                                            ; PLAYER_TO_SCREEN is at the END of
                                            ; the second sweep now: the view it
                                            ; converts against is not final
                                            ; until the latch down there

                ; =====================================================
                ; THE SECOND VSYNC. THE GAME RUNS AT 25 Hz AND EVERY
                ; GAME FRAME IS DISPLAYED TWICE.
                ;
                ; WHY: a frame this loop drops is not a stutter, it is a
                ; frame with no heroine in it - she is drawn in the top
                ; border and erased at her raster gate, so an overrun
                ; sweeps the whole picture with her already lifted off
                ; (CLAUDE.md 9). At 50 Hz the heavy paths could not make
                ; the budget: 160 loop iterations in 200 running, which
                ; is 40 holes, and a play-test called it what it is -
                ; flicker. At 25 Hz the budget is 159,744 T against a
                ; pessimistic sum of 87,328, and every path fits with
                ; 45% to spare. A locked 25 Hz beats a jittery 32-50.
                ;
                ; AND THE SPLIT IS NOT "WAIT TWICE": it is WHICH HALF OF
                ; THE LOOP GOES ON WHICH HARDWARE FRAME, and two rules
                ; decide it, both of them the beam's.
                ;
                ;   SHE MUST STAY ON THE SCREEN FOR BOTH SWEEPS, so the
                ;   erase cannot stay on the frame she is drawn on - the
                ;   second sweep would find her gone. It moves here,
                ;   behind the beam of the SECOND frame, and the next
                ;   draw is in the top border of the first frame after
                ;   it: every sweep has her in it.
                ;
                ;   AND SO MUST H_HEAD, for the mirror of the same
                ;   reason. The incoming column's cells are the left
                ;   edge of each row BELOW under the old start address
                ;   (CLAUDE.md 8.2), which is why they go down behind
                ;   the beam - but "behind the beam" only buys the rest
                ;   of THAT sweep. Painted on the first frame they would
                ;   be swept a second time before the latch, and that is
                ;   a 4-pixel column of the wrong tile down the left
                ;   edge for a whole displayed frame. Painted here, the
                ;   latch at the top of the next first frame moves the
                ;   view before the beam sees them again.
                ;
                ; So the first frame draws and thinks, and the second
                ; frame erases and puts the background right. Everything
                ; that changes the BACKGROUND is already at the end of
                ; this loop for the older reason (CLAUDE.md 10) and
                ; needed no moving at all.
                ;
                ; IT IS AN EDGE AND NOT A LEVEL. WAIT_VSYNC tests the
                ; level and the pulse is 16 scanlines (CLAUDE.md 7.7):
                ; on the rare frame whose work ENDS inside the pulse, a
                ; bare wait would return at once and the erase would land
                ; on the frame of the draw - one blank sweep, which is
                ; the very thing this is here to stop. The pair costs
                ; that frame a third hardware frame instead, and she
                ; stays on the screen through all three.
                ld   a,1
                ld   (FRAME_HALF),a         ; ... and say which half we are in
                call WAIT_VSYNC_END
                call WAIT_VSYNC

                ; AND THE HEAD'S ANCHOR IS TAKEN HERE, BEFORE ANY OF
                ; IT. The gate below counts ticks from the WAIT_VSYNC
                ; exit, which is what CLAUDE.md 9's tick table measures
                ; from - and the latch and the strip that now run in
                ; between are up to 33,000 T, two and a half ticks.
                ; Anchored after them the head waits four ticks from
                ; THERE and lands past the end of the sweep: measured as
                ; 119 wrong pixels down column 0 by the check with no
                ; model in it, which is the same column and the same
                ; kind of fault as the tearing this loop already had.
                ld   a,(IRQ_TICKS)
                ld   (HEAD_ANCHOR),a

                ; ---- THE VERTICAL LATCH, AND THE HUD ONE INSTRUCTION
                ; AFTER IT. A play-test: "the hud leaves traces behind
                ; on the fall", and it was neither the vacate nor the
                ; step - it was WHEN.
                ;
                ; The latch used to be at the top of the FIRST sweep and
                ; HUD_SERVICE runs after H_TAIL, most of a sweep later.
                ; Measured on the latch frames of a fall, the strip was
                ; not right again until 82,700-94,300 T, where the beam
                ; reaches row 22 at 63,488 and row 23 at 65,536: one
                ; whole sweep with the strip's pixels still at their old
                ; words - which the latch has just made row 22 - and
                ; fresh tilemap at row 23. A fall makes six to eight row
                ; steps back to back, and that is the traces.
                ;
                ; IT CANNOT BE FIXED BY MAKING THE ERASE CHEAPER: to be
                ; clean the strip has to be right before 60,432 T, which
                ; means starting inside KARA_DRAW, and anything put in
                ; front of her draw comes off the lead the top border
                ; gives her at ~320 T a scanline (CLAUDE.md 9).
                ;
                ; SO THE LATCH COMES HERE, WHERE THERE IS ROOM. The
                ; second sweep does nothing at all until interrupt tick
                ; 4 - 40,468 T of waiting, every frame - and a downward
                ; row step is 32,856 of it. The strip is repaired before
                ; the beam of the very sweep the view moved on.
                ;
                ; WHAT MAKES IT SAFE is that her erase replays a script
                ; of ABSOLUTE addresses the draw wrote (spanblit.asm),
                ; so a start address that moves between her draw and her
                ; erase does not move where the erase writes. Her PIXELS
                ; move with the picture, which is what a world-fixed
                ; sprite is supposed to do - the same reason the enemy
                ; is a persistent sprite (CLAUDE.md 8.7).
                call SCROLL_VBLANK
                call HUD_SERVICE

                ; AND WAIT FOR THE INTERRUPT TO STAMP THIS FRAME'S ANCHOR
                ; BEFORE USING ANY GATE THAT COUNTS FROM IT. THIS WAS THE
                ; BUG A PLAY-TEST REPORTED AS A BAD COLUMN DOWN THE SIDE.
                ;
                ; FRAME_TICK0 is written by the handler on the tick that
                ; lands inside the VSYNC pulse, which is the whole reason
                ; a frame that starts late still gates correctly (9). The
                ; loop's FIRST wait is followed by thousands of T of
                ; drawing before anything reads it, so the stamp has long
                ; since happened. THIS one is followed immediately by
                ; TICK_WAIT - and WAIT_VSYNC returns at the START of the
                ; pulse, before the stamping interrupt has fired. So the
                ; anchor still held the PREVIOUS frame's value, SIX ticks
                ; had "already passed", TICK_WAIT returned at once, and
                ; the incoming column's head went down at the very top of
                ; the frame - AHEAD of the beam for every row it doubles
                ; as (tilemap.asm), and on the glass for that whole sweep.
                ;
                ; Measured: 237 wrong pixels down column 0 running right,
                ; and the SAME 237 at every tick from 2 to 5 - which is
                ; the signature of a gate that is not gating. What found
                ; it was reading the elapsed ticks at the moment H_HEAD
                ; is entered instead of trusting the number asked for.
                ;
                ; FOUR TICKS AND NOT FIVE, AND THE DRONE IS WHY. Five put
                ; ENEMY_REFRESH at tick 6, where its 17,968 T runs past
                ; the vblank: ENEMY_ROOM refused it, the draw was
                ; deferred EN_DEFER_MAX frames and taken anyway, and a
                ; play-test reported the drone appearing and
                ; disappearing. At COL_HEAD = 12 the head is 8,304 T, so
                ; from tick 4 its last row lands 3,716 T after the beam
                ; has left the row that cell doubles as ON THE MACHINE'S
                ; beam model - which is the one that counts (tilemap.asm)
                ; - and the refresh is reached at tick 5 with room.
                ;
                ; SO THE GATE ANCHORS ITSELF HERE instead of waiting for
                ; the handler to catch up, which is both correct and
                ; free: the tick table of 9 is measured FROM THE
                ; WAIT_VSYNC EXIT, and that is exactly where this is.
                ; Waiting for the stamp was written first and measured
                ; at 97 game frames per 200 hardware running, against
                ; 100 for this - the pulse is 4,060 T and a run has no
                ; room to spend them.
                ld   a,(HEAD_ANCHOR)        ; our own anchor, taken at the
                ld   c,a                    ; WAIT_VSYNC exit above
.head_gate:     ld   a,(IRQ_TICKS)
                sub  c                      ; ticks since the VSYNC exit
                cp   4                      ; ... and the head wants four
                jr   c,.head_gate

                ; TICK 5, NOT 4, AND A PLAY-TEST ON REAL HARDWARE IS
                ; WHY. The incoming column's cells double as the left
                ; edge of the row BELOW until the latch (tilemap.asm), so
                ; the head must be written LATE - after the beam has left
                ; the row it doubles as. How late is enough was measured
                ; HERE, on an emulator whose border above the picture is
                ; 60 scanlines; a real 6845 left as the firmware programs
                ; it has 72, so every one of those deadlines falls
                ; 3,056 T LATER on the machine than in the measurement.
                ; The head's whole slack at COL_HEAD = 14 is 1,552 T.
                ; 1,552 - 3,056 = -1,504: on hardware it clears the row
                ; about six scanlines EARLY, and the incoming column
                ; shows down the left edge - reported from RVM as a bad
                ; column on the side she is running away from, which is
                ; exactly the side the arithmetic puts it on.
                ;
                ; A whole tick of delay is 13,312 T and buys margin on
                ; both models at once: +11,808 on the machine, +14,864
                ; here. NOTHING ELSE WOULD: the split is squeezed from
                ; both ends, and the tail's own slack moves the other
                ; way, so no value of COL_HEAD is comfortable on the two
                ; beam models together.
                ;
                ; AND IT IS AFFORDABLE ONLY BECAUSE OF THE SECOND VSYNC.
                ; At 50 Hz this sat on the same frame as her draw, the
                ; logic and the erase, and a whole tick of waiting was a
                ; tick the frame did not have. This half of a 25 Hz game
                ; frame has the column, the erase and the background and
                ; nothing else.
                call H_HEAD                 ; rows 0..COL_HEAD-1, behind the beam


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
                ; THE GATE IS HER FIRST LINE PLUS A MEASURED LEAD, NOT
                ; HER LAST, AND THE DIFFERENCE IS WHAT THE FALL COST.
                ;
                ; Both walk downwards. The erase is FASTER than the beam
                ; - about 97 T a line plus 24 a span byte, against the
                ; raster's 256 - so it closes on the beam and the line
                ; that binds really is the last one. But "the beam has
                ; passed her last line" is not what that requires: the
                ; erase needs the whole of its own run to REACH that
                ; line, so what it actually needs is
                ;
                ;     start >= beam(first line) + max over k of
                ;              (256k - what the erase has spent by k)
                ;
                ; and over all 59 shipped cels the worst that maximum
                ; comes to is 17.8 scanlines. Waiting for the beam to
                ; clear her LAST line waits 62.
                ;
                ; Free while the frame had room. Falling through the
                ; roof's gap it is not: she is low in the picture, the
                ; camera is stepping the view under her, and the erase
                ; started 1,767 us into her own frame's last third and
                ; ran 1,300 us past the vblank. FOUR DROPPED FRAMES down
                ; the fall - and a dropped frame is one with no heroine
                ; in it at all, because she has been erased and the next
                ; draw waits for the vblank after next. "A little
                ; flicker on the fall", and that is what it was.
                ;
                ; KARA_ERASE_LEAD is the margin on top: the beam is that
                ; many lines past her first line before the erase starts,
                ; which is what a line whose spans are denser than
                ; average can eat into without catching it up.
                ld   a,(KARA_LAST_CNT)
                ld   b,a
                ld   a,(KARA_LAST_BOT)
                sub  b                      ; her first drawn line, less one
                add  a,1 + KARA_ERASE_LEAD
                cp   192
                jr   c,.gate
                ld   a,191                  ; the bottom of the picture
.gate:          call RASTER_WAIT
                call KARA_SPAN_ERASE        ; reverse draw order: she went
                call EBUL_ERASE             ; down OVER the rounds, so her
                call BUL_ERASE              ; save-under holds their pixels
                                            ; and has to put them back before
                                            ; they restore the background
                jr   .erased
.bullets_only:  call EBUL_ERASE
                call BUL_ERASE
.erased:        ; ... and NOW the things that change the BACKGROUND, once
                ; every sprite has been lifted off it: the cell a taken
                ; pickup left behind, and the enemy, which is a
                ; persistent sprite where she is not. See enemy.asm.
                call ENT_REPAINT_DUE
                call ENEMY_REFRESH

                ; AND NOW WHERE SHE GOES, because the view is final: the
                ; vertical latch happened at the top of this sweep, and
                ; a screen position worked out before it would draw her
                ; a character row out of place. It is after the erase
                ; and not before because the erase's raster gate is
                ; picked from the lines the DRAW recorded, not from
                ; these.
                call PLAYER_TO_SCREEN

                xor  a
                ld   (FRAME_HALF),a         ; the next wait is the FIRST one
                ld   hl,FRAME_COUNT
                inc  (hl)
                ; ONE FRAME IN THREE THE ROUNDS HOLD STILL. Both pools
                ; step whole BYTES - 4 Mode 0 pixels - so a third off
                ; their speed is not a smaller step, it is a step they
                ; do not take. The counter is here because
                ; UPDATE_BULLETS returns early on an empty pool and
                ; their rounds would then run at a speed that depended
                ; on whether she was firing.
                ld   hl,BUL_PHASE
                dec  (hl)
                jr   nz,.phased
                ld   (hl),BUL_SLOW
                ; AND IF THE LEVEL ENDED, IT ENDS HERE - at the bottom
                ; of the frame, with every sprite lifted off and the
                ; background finished, which is the only moment a fade
                ; and a repaint can have the machine to themselves.
                ; A game frame's worth of work is nothing to it: the
                ; fade alone is 36 of them.
.phased:        ld   a,(GAME_STATE)
                or   a
                call nz,FLOW_STEP
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
                ld   c,3
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

; THE AMMO HUD IS GONE WITH THE SCREEN IT BELONGED TO. HUD_UPDATE and
; HUD_ROW drew two rows of seven round indicators for the Module 1-3
; acceptance screen, which has been deleted; nothing has called them
; since, and their one surviving comment - "the scrolling game needs a
; split-screen HUD anyway" - turned out to be the wrong answer as well
; (src/hud.asm has the measurement). The energy bar is in hud.asm.


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

                include "bank.asm"
                include "screen.asm"
                include "palette.asm"
                include "fade.asm"
                include "sprite.asm"
                include "spanblit.asm"
                include "unpack.asm"
                include "intro.asm"
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
                include "hud.asm"
                include "flow.asm"

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
KARA_LAST_ADDR: dw 0
KARA_LAST_TOP:  db 0            ; her first and last DRAWN screen lines,
KARA_LAST_BOT:  db 0            ; which clipping makes different from Y, Y+63
KARA_LAST_CNT:  db 0            ; lines drawn; 0 = entirely off the display
KARA_ANIM:      db 0            ; index within the current tag's frames
LEVEL_OK:       db 0            ; did the disc load work? 0 = draw no sprite
KARA_SAVE_PTR:  dw 0            ; where in KARA_SAVE the drawn part starts
KARA_ERASE_LEAD equ 32          ; scanlines of beam the erase starts behind
                                ; 24 + the 8 a vertical latch can move her
                                ; by between her draw and her erase: the
                                ; gate is picked from the lines the draw
                                ; recorded, and a step UP puts her pixels
                                ; 8 lines BELOW them. The worst any cel
                                ; needs is 17.8, so 24 had 6.2 to give
                                ; and a row is 8
                                ; her FIRST drawn line, and the number is
                                ; measured over all 59 shipped cels - see the
                                ; gate in the loop. The worst of them needs
                                ; 17.8, the worst one anything PLAYS 15.3.

KARA_CLIP_W:    db 0            ; the drawn rectangle, so KARA_ERASE can
KARA_CLIP_H:    db 0            ; replay exactly what KARA_DRAW wrote
DEMO_PHASE:     db 0                    ; 0 = right, 1 = down, 2 = up
DEMO_PHASE_T:   db 0
FRAME_TICK0:    db 0
BUL_PHASE:      db BUL_SLOW     ; 3, 2, 1, 3, ... - at 1 the rounds hold
; WHICH HALF OF THE GAME FRAME THE LOOP IS IN: 0 while it is drawing
; and thinking, 1 while it is erasing and putting the background right
; (see the note on the second VSYNC above). The engine never reads it.
; IT IS THERE FOR THE TESTS, and they need it: every one of them samples
; video RAM "at the instant after VSYNC, with Kara already erased", and
; there are TWO such instants a game frame now - one with her on the
; screen and one without. 7 T a frame to make the two tellable apart is
; cheaper than every suite guessing.
HEAD_ANCHOR:    db 0            ; IRQ_TICKS at the second sweep's VSYNC
                                ; exit - the head's gate counts from it
FRAME_HALF:     db 0
HURT_FLASH:     db 0            ; frames of red border left on a hit
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
; THE LEVEL IMAGE - a level's own bytes, READ OFF THE DISC.
;
; DATA, not code: copied into their working addresses at every level
; init and never executed. MAP_INSTALL takes its working copy from
; here - a working copy and not the original, because ENT_BAKE stamps
; each pickup into the map and a re-init needs the map it started with.
;
; ~~The bootstrap drops them in base RAM at LEVEL_IMAGE~~ - IT DID, AND
; THAT ONLY EVER WORKED FOR ONE LEVEL. level_1.lvl and its tile flags
; were INCBINed here and LDIRed down at boot, which costs 2,200 bytes
; of a binary that loads at &4000 and relocates below it. Six levels is
; 13 KB of that and there is no 13 KB - and a level the game LOADS
; cannot come out of an image that was assembled before it existed.
;
; So a level's own bytes go on the disc with its art, packed as one
; stream, and LEVEL_MAP_LOAD reads them here (tools/make_level_image.py,
; src/unpack.asm). Nothing of a level is in the core image any more.
;
;   LEVEL_IMAGE + 0     256 bytes   the tile flags, ZERO-PADDED
;   LEVEL_IMAGE + 256   ...         level_<n>.lvl, as the editor writes it
;
; THE FLAGS ARE FIRST AND PADDED so that MAP_INSTALL's copy into
; TILE_ATTR is ONE LDIR of a constant length with no clear in front of
; it: the table is 256 entries because a map byte is an index and every
; one of the 256 has to answer, so filling it exactly is both simpler
; and faster than clearing it and copying a length the engine would
; have to be told. The padding is free on the disc - ZX0 eats a zero
; run - and the whole image packs to 354 bytes of one sector.
; =====================================================================
LEVEL_IMAGE     equ  &B000      ; above the map and its table, below the stack
LEVEL_TILEFLAGS equ  LEVEL_IMAGE
LEVEL_TILEFLAGS_N equ TILE_ATTR_N
LEVEL_LVL       equ  LEVEL_IMAGE + LEVEL_TILEFLAGS_N

                ; LEVEL_IMAGE_SIZE is the biggest image the build made,
                ; written by tools/make_level_image.py - so the one
                ; number is generated from the data and the assembler
                ; does the checking, the way banks.inc and disc.inc
                ; already work. A level that grew past the stack would
                ; otherwise corrupt it at the moment it loaded.
                include "levels/mapimage.inc"
                assert LEVEL_IMAGE + LEVEL_IMAGE_SIZE < STACK_TOP - 1024
                ; and it must not land on top of what it is copied INTO
                assert LEVEL_IMAGE >= ENT_TABLE + ENT_MAX * ENT_STRIDE
