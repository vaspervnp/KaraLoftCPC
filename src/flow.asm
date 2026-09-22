; =====================================================================
; flow.asm - the level's own state machine                    (MODULE 6)
;
; plan.md 8.1's diagram is STATE_LEVEL_PLAY -> STATE_LEVEL_CLEAR ->
; STATE_CUTSCENE -> STATE_LOAD_NEXT. What is here is that spine with
; the cutscenes left out and one state added that the diagram has no
; room for, because until now the engine had no answer to it at all:
; she dies.
;
;   GS_PLAY    the loop is the game
;   GS_DEAD    her `die` run has played through and held its last cel
;   GS_CLEAR   the way out has been opened
;
; THE CHECK IS CHEAP AND THE STEP IS NOT. FLOW_CHECK runs every game
; frame and is about forty T of comparisons; FLOW_STEP runs once, on
; the frame a state changes, and takes as long as it takes - a fade is
; two thirds of a second and a title screen is a disc read. Nothing is
; being drawn while it runs, which is the same licence LEVEL_LOAD has.
;
; ---------------------------------------------------------------------
; A RESTART IS SCROLL_INIT AND NOT A DISC READ, AND THAT IS WHY
; LEVEL_IMAGE IS A PRISTINE COPY.
;
; The map at &A000, the entity table at &A800 and the tile flags at
; &A900 are all WORKING copies, made by MAP_INSTALL out of the image at
; &B000 that came off the disc (src/unpack.asm). Play writes on every
; one of them - a taken pickup's cell goes back to the plain tile, a
; dead drone's record is marked EF_TAKEN, a baked pickup owns a scratch
; tile - and the image is never touched. So a re-init is exactly
; MAP_INSTALL again, and SCROLL_INIT is MAP_INSTALL plus putting the
; view back to the top left and repainting the playfield, which is the
; whole of what a restart means on the screen.
;
; It also re-bakes the pickups and re-spawns the enemies, because
; MAP_INSTALL calls ENT_BAKE and ENEMY_SPAWN and those two clear
; everything they own.
;
; WHAT IT DOES NOT OWN IS LEVEL_RESET'S, and that list is not one to
; reason about: a restart that forgets a byte is a level that plays
; slightly wrong in a way nobody can see. tools/test_flow.py compares
; the whole of the engine's RAM after a restart against a machine that
; has just booted, and every byte that differs has to be named.
; =====================================================================

GS_PLAY         equ 0
GS_DEAD         equ 1
GS_CLEAR        equ 2

; ---------------------------------------------------------------------
; FLOW_CHECK - has the level ended? Called from the main loop, every
; game frame, after ENT_UPDATE.
;                                destroys AF,HL
;
; AFTER ENT_UPDATE BECAUSE ENT_RESULT IS THIS FRAME'S. The sweep writes
; it on every frame and the handlers are the only things that set it to
; anything but ER_NOTHING, so `the door gave way` is a fact with a
; lifetime of one frame and this is the frame.
;
; AND DEATH IS KARA_DONE AND NOT PLAYER_HP. Zero hit points is the
; instant she is hit; what the player has to see is the six cels of the
; `die` run and the 600 ms the artist holds the last one for (7.1), and
; KARA_DONE is the animator saying that has happened. Reading PLAYER_HP
; here would take the screen away on the frame the round landed.
; ---------------------------------------------------------------------
FLOW_CHECK:     ld   a,(GAME_STATE)
                or   a
                ret  nz                     ; already on the way out
                ld   a,(ENT_RESULT)
                cp   ER_OPENED
                jr   z,.clear
                ld   a,(KARA_STATE)
                cp   KST_DIE
                ret  nz
                ld   a,(KARA_DONE)
                or   a
                ret  z
                ld   a,GS_DEAD
                ld   (GAME_STATE),a
                ret
.clear:         ld   a,GS_CLEAR
                ld   (GAME_STATE),a
                ret

; ---------------------------------------------------------------------
; FLOW_STEP - leave the level. Called from the end of the main loop,
; and only when GAME_STATE is not GS_PLAY.
;                                destroys everything
;
; IT RETURNS INTO THE LOOP, which is what makes this a state machine
; and not a jump table: the loop's next iteration is the first frame of
; the level she is now in, with its raster gates re-anchored by the
; WAIT_VSYNC at the top of it.
; ---------------------------------------------------------------------
FLOW_STEP:      cp   GS_CLEAR
                jr   z,.clear

                ; ---- she died --------------------------------------
                ; The same level, from the image. No disc: her art is
                ; in the banks and the level's bytes are at &B000.
                ld   hl,PALETTE_DATA
                call FADE_OUT
                call LEVEL_RESTART
                jr   .back

                ; ---- the level is over, so go to the next one ------
                ; AND WHAT THAT COSTS DEPENDS ON WHETHER IT IS IN THE
                ; SAME ENVIRONMENT. LEVEL_GOTO reads the map either way
                ; - one sector - and the art only when the level it is
                ; going to wants a different set. Four levels of one
                ; environment are therefore three free transitions and
                ; one 1.6 s read to arrive.
                ;
                ; SHE KEEPS WHAT SHE IS CARRYING, which is LEVEL_ENTER
                ; rather than LEVEL_RESET: her health, her magazines,
                ; her reserve and her coins cross the door, and only a
                ; death puts them back. A level that handed out a full
                ; bar on the way in would make every door a medkit.
.clear:         ld   hl,PALETTE_DATA
                call FADE_OUT
                ld   a,(LEVEL_CUR)
                inc  a
                cp   DISC_LEVEL_N
                jr   nc,.over
                call LEVEL_GOTO
                jr   nc,.over               ; no map there: that was the last
                call LEVEL_ADVANCE
                jr   .back

                ; ---- ... and when there is no next one -------------
                ; The game goes back to its title and starts again from
                ; the first level, which is a loop a player can see the
                ; end of. It is also what an UNPAINTED level looks like:
                ; DISC_LEVEL_MAPS carries a zero for every level nobody
                ; has made yet, and LEVEL_GOTO refuses rather than
                ; letting MAP_INSTALL parse whatever &B000 held.
.over:          call INTRO_SHOW             ; ... a disc read, so interrupts
                call INTRO_WAIT             ; are off and the tick has stood
                                            ; still; the loop's own
                                            ; WAIT_VSYNC re-anchors it
                xor  a
                call SCREEN_CLS
                xor  a                      ; back to the first level, and
                call LEVEL_GOTO             ; its art if this is not it
                call LEVEL_RESTART

.back:          ; INTERRUPTS BACK ON, AND IT IS FOUR T TO NOT DEPEND ON AN
                ; ACCIDENT. LEVEL_GOTO is a disc read and returns with
                ; them off (src/unpack.asm); measured, the loop comes
                ; back anyway at 100 of 200 with IRQ_TICKS advancing its
                ; full 1,200 - because `di / call INPUT_SCAN / ei` in
                ; the loop body turns them on again a routine later, for
                ; the AY's address latch and nothing to do with this.
                ; That is a true fact about today's loop and a bad thing
                ; to rest a level transition on: everything between
                ; WAIT_VSYNC and INPUT_SCAN runs with them off, and the
                ; day a raster gate moves above that line the transition
                ; hangs and nothing here would say why.
                ei

                ; THE PALETTE IS BLACK AND THE PICTURE IS FINISHED, so
                ; the fade in is the whole of what is left. She is on
                ; the screen the moment it starts: LEVEL_RESTART has
                ; painted the playfield but not her, and the first loop
                ; iteration after this draws her - one frame of a city
                ; with nobody in it, at a palette one step off black.
                ld   hl,PALETTE_DATA
                call FADE_IN
                xor  a
                ld   (GAME_STATE),a
                ; AND LEAVE ON A FALLING EDGE. FADE_SHOW's last act is a
                ; WAIT_VSYNC, which returns at the START of a 16-scanline
                ; pulse (7.7) - so the loop's own WAIT_VSYNC would find
                ; the level still high, return at once, and run a frame
                ; whose raster gates are anchored a pulse late. One
                ; frame, once a transition, and four T to not have it.
                jp   WAIT_VSYNC_END

; ---------------------------------------------------------------------
; LEVEL_GOTO - put a level in memory: its map always, its art only if
; that is not the art already in the banks.
;
; IN : A = level number, 0 based
; OUT: carry SET and the level is in RAM, LEVEL_CUR is it. Carry clear
;      means there is no such level - no map painted for it, or a read
;      that failed - and nothing has moved but the staging buffer.
;      destroys everything, INTERRUPTS OFF ON RETURN
;
; A LEVEL IS A MAP AND AN ENVIRONMENT IS A BANK SET, and keeping them
; apart is the whole of this routine. The map is 358 packed bytes, ONE
; SECTOR; the art is 16-20 KB and 1.6 s (CLAUDE.md 7.5). So four levels
; of one environment cost one read to arrive and a sector each after
; that, and the player crosses a door in the time the fade takes.
;
; THE MAP IS READ FIRST AND THE ENVIRONMENT COMES OUT OF IT. Byte 9 of
; the header is the level's own word for which tileset it wants, which
; makes the level file the single statement of it - a table here saying
; the same thing is a second place to get it wrong, and the day they
; disagreed the engine would follow one and the build the other. It
; also means a level with no map never loads art for a level that
; cannot be drawn.
; ---------------------------------------------------------------------
LEVEL_GOTO:     ld   (.want + 1),a
                call LEVEL_MAP_LOAD
                ret  nc
                ld   a,(LEVEL_LVL + LVL_TILESET)
                dec  a                      ; 1-6 in the file, 0-5 here
                ld   hl,LEVEL_ENV
                cp   (hl)
                jr   z,.have                ; the art is already in the banks
                ld   (hl),a                 ; ... and it is claimed BEFORE the
                add  a,a                    ; read, because a read that fails
                call LEVEL_LOAD             ; leaves the banks dirty either way
                jr   c,.have
                ld   a,&FF                  ; so nothing may be believed about
                ld   (LEVEL_ENV),a          ; them, and the next GOTO reloads
                ret                         ; carry clear, from LEVEL_LOAD
.have:
.want:          ld   a,0
                ld   (LEVEL_CUR),a
                scf
                ret

LEVEL_CUR:      db 0
LEVEL_ENV:      db &FF          ; which environment's art is in the banks,
                                ; and &FF is "none of them yet"

; ---------------------------------------------------------------------
; LEVEL_RESTART - the same level, as it was when it was loaded.
; LEVEL_ADVANCE - a DIFFERENT level, with what she is carrying intact.
;                                destroys everything
;
; The only difference is which of the two resets runs; what follows is
; the same, because SCROLL_INIT does not care how the image at &B000
; got there.
; ---------------------------------------------------------------------
LEVEL_RESTART:  call LEVEL_RESET
                jr   LEVEL_SHOW

LEVEL_ADVANCE:  call LEVEL_ENTER

LEVEL_SHOW:     call SCROLL_INIT
                ret  nc
                ; MAP_INSTALL refused. After a RESTART that means the
                ; image at &B000 has been damaged - nothing else can
                ; make a file that parsed once stop parsing - and after
                ; an ADVANCE it means the level that just came off the
                ; disc is not one this engine can read. There is no
                ; recovering from either here, so it is said the way a
                ; failed load is said (src/main.asm) and the loop runs
                ; on without her.
                xor  a
                ld   (LEVEL_OK),a
                ret

; ---------------------------------------------------------------------
; LEVEL_RESET - what a DEATH puts back, and then a level start.
;                                destroys AF,BC,DE,HL
;
; WHAT IS HERE RATHER THAN IN LEVEL_ENTER IS WHAT SHE CARRIES THROUGH A
; DOOR. Health, both magazines, the reserve and her coins cross a
; transition and only dying restores them: a level that handed out a
; full bar on the way in would make every door a medkit, and one that
; emptied her guns would make the last room of an environment the one
; she cannot fight her way out of. It falls straight into LEVEL_ENTER,
; which is everything that is per LEVEL whichever way she arrived.
;
; tools/test_flow.py compares the whole of the engine's RAM after a
; restart against a machine that has just booted, so this list is
; measured rather than reasoned about - and it knocks a line out of it
; as the control.
; ---------------------------------------------------------------------
LEVEL_RESET:    ld   a,HP_MAX
                ld   (PLAYER_HP),a
                ld   a,MAG_SIZE
                ld   (MAG_LEFT),a
                ld   (MAG_RIGHT),a
                ld   a,AMMO_START
                ld   (AMMO_RESERVE),a
                xor  a
                ld   (COINS_COUNT),a
                ; ... and on into the rest of a level start

; ---------------------------------------------------------------------
; LEVEL_ENTER - everything a level start means that SCROLL_INIT does
; not own and that she does NOT take with her.
;                                destroys AF,BC,DE,HL
;
; SCROLL_INIT and MAP_INSTALL between them put back the view, the map,
; the entity table, the tile flags, the pickup bake, the enemies, their
; rounds and where she stands. What is left is the state that belongs
; to THIS LEVEL and to the FRAME, and it is in four groups.
; ---------------------------------------------------------------------
LEVEL_ENTER:    ; ---- this level's own puzzle state -----------------
                ; A KEY OPENS ONE GARAGE. The statues are level 2's and
                ; the book is level 3's, and each of them is a thing a
                ; designer placed for the door at the end of the level
                ; it is in - so they do not travel, and a level that
                ; started with the last one's key in her hand would be
                ; a level whose lock is already open.
                xor  a
                ld   (KEYS_COUNT),a
                ld   (STATUES_HELD),a
                ld   (CURRENT_BOOK_ID),a
                ld   (ENT_RESULT),a         ; ER_NOTHING, and it MUST be
                                            ; cleared: FLOW_CHECK reads it
                                            ; and ER_OPENED left standing
                                            ; would clear the level again
                                            ; on the first frame back

                ; ---- the guns' STATE, but not what is in them ------
                ; A round in the air belongs to the screen it was fired
                ; at, and so does a reload half way through; what is in
                ; the magazines is LEVEL_RESET's and crosses the door.
                ld   (ACTIVE_GUN),a
                ld   (RELOAD_TIMER),a
                ld   (BUL_LIVE),a
                ld   (BUL_DREW),a
                ld   (BUL_TOP),a
                ld   (BUL_DREW_TOP),a
                ld   hl,BULLETS
                ld   de,BULLETS + 1
                ld   bc,BUL_MAX * BUL_STRIDE - 1
                ld   (hl),0
                ldir
                ld   a,BUL_SLOW
                ld   (BUL_PHASE),a

                ; ---- what she is doing -----------------------------
                ; KARA_LAST_CNT IS THE ONE THAT MATTERS. SPAN_ERASE
                ; replays a list of ABSOLUTE addresses the draw wrote
                ; (9), and those addresses are in a screen that has just
                ; been repainted from the tilemap - so an erase that
                ; still believed in the last frame's draw would stamp
                ; the old background back over the new picture. Zero
                ; says nothing is on the screen to lift off.
                xor  a
                ld   (KARA_ANIM),a
                ld   (KARA_FRAME),a
                ld   (KARA_DONE),a
                ld   (KARA_LAST_CNT),a
                ld   (KARA_CLIP_W),a
                ld   (KARA_CLIP_H),a
                ld   (HURT_FLASH),a
                ld   (HAZARD_IN),a          ; a level that started with her
                                            ; already IN the spikes is one
                                            ; whose first pit is free
                ld   a,KST_IDLE
                ld   (KARA_STATE),a
                ld   a,KSET_CORE
                ld   (KARA_SET),a
                ld   a,1
                ld   (KARA_TIMER),a

                ; ---- and the frame ---------------------------------
                ; A STEP THAT WAS PENDING IS A STEP INTO THE OLD VIEW.
                ; SCROLL_INIT puts SCROLL, WORLD_X and WORLD_CR back to
                ; zero and latches them; a horizontal request left half
                ; done would then paint its incoming column into a
                ; picture that had moved under it, and a vertical one
                ; would latch a start address worked out against the
                ; view it was asked in.
                ; AND ITS PARAMETERS GO WITH ITS FLAGS. The five
                ; bytes below are what SAYS a step is in flight; the
                ; six after them are what the step WAS - the column
                ; and the view it was asked in, and the same for the
                ; row. Nothing reads them while the flags are clear,
                ; so they are dead - and half a record cleared with
                ; half left is the shape of every bug in CLAUDE.md 10.
                ; They are also what tools/test_flow.py's sweep found
                ; when the view stopped panning at a level start
                ; (CLAUDE.md 8.1): the pan used to rewrite them on the
                ; way, so a restart and a fresh boot agreed by accident.
                xor  a
                ld   (H_PENDING),a
                ld   (H_TAIL_DUE),a
                ld   (V_REQUEST),a
                ld   (VIEW_STEP),a
                ld   (V_PHASE),a
                ld   (H_COL),a
                ld   (H_WX),a
                ld   (V_WCR),a
                ld   (V_ROW),a
                ld   (H_SCROLL),a
                ld   (H_SCROLL + 1),a
                ld   (V_SCROLL),a
                ld   (V_SCROLL + 1),a
                ld   hl,0
                ld   (ENT_RP_DUE),hl        ; a pickup's cell, waiting to be
                                            ; repainted out of a map that is
                                            ; about to be replaced
                jp   HUD_DISOWN             ; ... and the strip is laid out
                                            ; again from what it now finds

GAME_STATE:     db GS_PLAY
