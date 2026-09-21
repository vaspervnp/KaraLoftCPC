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

                ; ---- the level is over -----------------------------
                ; AND THERE IS NOWHERE TO GO YET, WHICH IS A LEVEL'S
                ; PROBLEM AND NOT THIS ROUTINE'S. Five of the six
                ; levels have their art on the disc and no map on it
                ; (tools/make_level_image.py), so LEVEL_MAP_LOAD would
                ; refuse and MAP_INSTALL would parse whatever &B000
                ; held. Rather than pretend, the game goes back to its
                ; title and starts again - which is a loop a player can
                ; see the end of, and the one line to change the day a
                ; second level exists.
.clear:         ld   hl,PALETTE_DATA
                call FADE_OUT
                call INTRO_SHOW             ; ... a disc read, so interrupts
                call INTRO_WAIT             ; are off and the tick has stood
                                            ; still; the loop's own
                                            ; WAIT_VSYNC re-anchors it
                xor  a
                call SCREEN_CLS
                call LEVEL_RESTART

.back:          ; THE PALETTE IS BLACK AND THE PICTURE IS FINISHED, so
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
; LEVEL_RESTART - the level as it was when it was loaded.
;                                destroys everything
; ---------------------------------------------------------------------
LEVEL_RESTART:  call LEVEL_RESET
                call SCROLL_INIT
                ret  nc
                ; MAP_INSTALL refused, which after a level has been
                ; PLAYED means the image at &B000 has been damaged -
                ; nothing else can make a file that parsed once stop
                ; parsing. There is no recovering from that here, so it
                ; is said the way a failed load is said (src/main.asm)
                ; and the loop runs on without her.
                xor  a
                ld   (LEVEL_OK),a
                ret

; ---------------------------------------------------------------------
; LEVEL_RESET - everything a level start means that SCROLL_INIT does
; not own.
;                                destroys AF,BC,DE,HL
;
; SCROLL_INIT and MAP_INSTALL between them put back the view, the map,
; the entity table, the tile flags, the pickup bake, the enemies, their
; rounds and where she stands. What is left is the state that belongs
; to HER and to the FRAME, and it is in four groups.
; ---------------------------------------------------------------------
LEVEL_RESET:    ; ---- what she is carrying --------------------------
                ld   a,HP_MAX
                ld   (PLAYER_HP),a
                xor  a
                ld   (KEYS_COUNT),a
                ld   (COINS_COUNT),a
                ld   (STATUES_HELD),a
                ld   (CURRENT_BOOK_ID),a
                ld   (ENT_RESULT),a         ; ER_NOTHING, and it MUST be
                                            ; cleared: FLOW_CHECK reads it
                                            ; and ER_OPENED left standing
                                            ; would clear the level again
                                            ; on the first frame back

                ; ---- the guns --------------------------------------
                ld   a,MAG_SIZE
                ld   (MAG_LEFT),a
                ld   (MAG_RIGHT),a
                ld   a,AMMO_START
                ld   (AMMO_RESERVE),a
                xor  a
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
                xor  a
                ld   (H_PENDING),a
                ld   (H_TAIL_DUE),a
                ld   (V_REQUEST),a
                ld   (VIEW_STEP),a
                ld   (V_PHASE),a
                ld   hl,0
                ld   (ENT_RP_DUE),hl        ; a pickup's cell, waiting to be
                                            ; repainted out of a map that is
                                            ; about to be replaced
                jp   HUD_DISOWN             ; ... and the strip is laid out
                                            ; again from what it now finds

GAME_STATE:     db GS_PLAY
