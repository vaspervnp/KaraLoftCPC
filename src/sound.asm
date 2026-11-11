; =====================================================================
; sound.asm - the AY-3-8912: the music, the effects, and what the game
; did this frame to deserve them (CLAUDE.md 6.7, 11 step 9)
;
; Assembled into the SOUND image at &9400 (src/main.asm), base RAM that
; is never banked out, so any of it can be called at any time.
;
; THREE VOICES AND A FOURTH THAT STEALS ONE. Channel A is the melody,
; B the bass and C the drums - and C is also where every effect is
; heard (plan.md 7). An effect takes C for as long as its volumes last;
; the music on C goes on being COUNTED the whole time, so when the
; effect ends C comes back in step, on the envelope it had reached, and
; not re-struck: no click, and no drum a beat late.
;
; ONE TICK A GAME FRAME, 25 Hz, from the second sweep's wait for its
; head gate, which is time the loop had always spent doing nothing
; (src/main.asm) - and not from the interrupt, which is where plan.md
; puts a music player. The interrupt's tick inside the VSYNC pulse
; lands 532 T into the FIRST sweep, which is the top border and her
; whole lead over the beam (CLAUDE.md 9): every 320 T spent there is a
; line off the top of her. The idle window costs nothing. What the
; music pays for that is resolution - a length is a whole number of
; 40 ms ticks, so a sixteenth is 120 or 160 ms - and tools/make_music.py
; writes the tunes in those units.
;
; THE GAME DOES NOT CALL THIS FOR ITS EFFECTS. SND_WATCH reads, once a
; game frame, the handful of bytes that say what happened - her health,
; the rounds in her guns, her reserve, the key, the coins, the idol and
; the level's state - and turns each change into a request. Not one
; instruction is added to the first sweep, where the frame has 800 T on
; its tightest path (CLAUDE.md 9), and a sound cannot be forgotten at a
; site nobody thought of: a medkit, a fall and a spike all move the
; same byte. Only the drones' events are requested where they happen
; (src/enemy.asm), because nothing they leave behind says "hit".
;
; SHARING THE CHIP WITH THE KEYBOARD - read input.asm's header first.
; PPI port A is the PSG's data bus and the keyboard's, and INPUT_SCAN
; latches register 14 and turns the port round to read it. Neither
; side runs in the interrupt, so the two cannot meet halfway: INPUT_SCAN
; leaves port A an OUTPUT, which is what every write here needs, and
; every write here leaves port C at PSG_IDLE. And R7 bit 6 is the PSG's
; own port A direction: SND_MIX_OFF has it clear and the voices only
; ever clear further bits, so the keyboard cannot go deaf from here.
;
; THE ENVELOPES ARE SOFTWARE. The AY has one envelope generator for all
; three voices; amplitude bit 4 is never set and R11-R13 never written.
; =====================================================================

SND_TONE        equ 1           ; descriptor flags (tools/make_music.py)
SND_NOISE       equ 2
SND_MIX_OFF     equ %00111111   ; R7, a 0 bit ENABLES: tones A B C, then
                                ; noises A B C. Bits 6 and 7 stay 0.

PSG_DATA        equ &F4         ; PPI port A
PSG_CTRL        equ &F6         ; PPI port C
PSG_SELECT      equ &C0         ; BDIR + BC1: latch a register number
PSG_WRITE       equ &80         ; BDIR: write the data
PSG_IDLE        equ &00

; One music voice, IX-relative.
MV_PTR          equ 0           ; the next byte of its stream
MV_CNT          equ 2           ; ticks left of this event
MV_LEN          equ 3           ; the current length
MV_IPTR         equ 4           ; the current instrument's descriptor
MV_EPTR         equ 6           ; where in its envelope it is
MV_PER          equ 8           ; the tone period
MV_SWP          equ 10          ; ... and what is added to it a tick
MV_VOL          equ 12          ; the level this tick, 0-15
MV_ATT          equ 13          ; the channel's attenuation
MV_RET          equ 14          ; where a bar returns to
MV_LPTR         equ 16          ; a loop body's first byte
MV_LCNT         equ 18          ; ... and how many more times round
MV_FLG          equ 19          ; the instrument's tone and noise bits
MV_NOI          equ 20          ; ... and its noise period
MV_SIZE         equ 21

; ---------------------------------------------------------------------
; SOUND_INIT - silence, and every register written on the first tick.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
SOUND_INIT:     ld   hl,SND_STATE
                ld   de,SND_STATE + 1
                ld   bc,SND_STATE_N - 1
                ld   (hl),0
                ldir
                ld   a,TUNE_N               ; no tune: SOUND_TUNE below
                ld   (SND_TUNE),a           ; will not take 0 for "this one"
                ld   hl,SND_LAST            ; &FF is a value no register
                ld   de,SND_LAST + 1        ; is written with here, so the
                ld   bc,11 - 1              ; first flush writes all eleven
                ld   (hl),&FF
                ldir
                push ix
                ld   hl,SND_QUIET_HDR
                call SND_START
                pop  ix
                jp   SND_SYNC

; ---------------------------------------------------------------------
; SOUND_TUNE - play tune A from its start, unless it is the one playing.
;                                destroys AF,BC,DE,HL
;
; THE SAME TUNE GOES ON. A death, and a door into the next level of the
; same environment, both come through here: the music is the
; environment's and not the level's, so it does not start again.
; ---------------------------------------------------------------------
SOUND_TUNE:     ld   hl,SND_TUNE
                cp   (hl)
                ret  z
                ld   (hl),a
                add  a,a
                ld   e,a
                ld   d,0
                ld   hl,TUNE_TABLE
                add  hl,de
                ld   e,(hl)
                inc  hl
                ld   d,(hl)
                ex   de,hl
                push ix
                call SND_START
                pop  ix
                ret

; HL = a tune's header, three stream addresses.
SND_START:      ld   ix,SND_VA
                call .one
                ld   ix,SND_VB
                call .one
                ld   ix,SND_VC
.one:           ld   a,(hl)
                ld   (ix + MV_PTR),a
                inc  hl
                ld   a,(hl)
                ld   (ix + MV_PTR + 1),a
                inc  hl
                ld   (ix + MV_CNT),1        ; the first tick reads an event
                ld   (ix + MV_LEN),1
                ld   (ix + MV_LCNT),0
                ld   (ix + MV_ATT),0
                ld   (ix + MV_VOL),0
                ld   (ix + MV_FLG),SND_TONE
                ld   (ix + MV_NOI),0
                xor  a
                ld   (ix + MV_PER),a
                ld   (ix + MV_PER + 1),a
                ld   (ix + MV_SWP),a
                ld   (ix + MV_SWP + 1),a
                ld   de,INS_0
                ld   (ix + MV_IPTR),e
                ld   (ix + MV_IPTR + 1),d
                ld   de,SND_ZERO
                ld   (ix + MV_EPTR),e
                ld   (ix + MV_EPTR + 1),d
                ret

; ---------------------------------------------------------------------
; SOUND_LEVEL - a level has started: its environment's tune, and the
; watch put level with what the level start left in her pockets.
;                                destroys AF,BC,DE,HL
;
; WITHOUT THE SYNC A RESTART IS A MEDKIT. LEVEL_RESET puts her health
; back to full, and to a watch that last saw 4 that is a heal - so the
; first thing every life after a death would do is play the medkit.
; ---------------------------------------------------------------------
SOUND_LEVEL:    call SND_SYNC
                ld   a,(LEVEL_ENV)
                cp   ENV_TUNE_N
                ld   a,TUNE_TITLE
                jp   nc,SOUND_TUNE
                ld   a,(LEVEL_ENV)
                ld   e,a
                ld   d,0
                ld   hl,ENV_TUNE
                add  hl,de
                ld   a,(hl)
                jp   SOUND_TUNE

; ---------------------------------------------------------------------
; SOUND_TICK - the game loop's: what happened, and one tick of it all.
; SOUND_HALF - the same tick, for a loop that runs at 50 Hz: every
;              other call. The title waits here.
; SOUND_FADE - SOUND_HALF for the fade, with the MUSIC taken down a
;              step with every step of the palette (src/fade.asm).
;                                destroys AF,BC,DE,HL
;
; Only the game loop WATCHES. The title and the fade run between
; frames, while a level is being put back or replaced underneath them,
; and every byte the watch reads is in the middle of being written.
; ---------------------------------------------------------------------
SOUND_TICK:     call SND_WATCH
                xor  a
                jr   SND_TICK_AT

SOUND_HALF:     ld   hl,SND_PHASE
                inc  (hl)
                bit  0,(hl)
                ret  nz
                xor  a
                jr   SND_TICK_AT

SOUND_FADE:     ld   hl,SND_PHASE
                inc  (hl)
                bit  0,(hl)
                ret  nz
                ld   a,(FADE_STEP)
                add  a,a
                add  a,a                    ; four levels a step of the
                                            ; palette: 0, 4 and 8 - the AY's
                                            ; levels are about 3 dB apart
SND_TICK_AT:    ld   (SND_ATTEN),a
                push ix
                ld   hl,SND_TICKS
                inc  (hl)
                call SND_SFX_START
                ld   ix,SND_VA
                call SND_VOICE
                ld   ix,SND_VB
                call SND_VOICE
                ld   ix,SND_VC
                call SND_VOICE
                call SND_SFX_STEP
                call SND_MIX
                pop  ix
                jp   SND_FLUSH

; ---------------------------------------------------------------------
; SOUND_MUTE - all three levels to 0, now. A disc read runs with the
; interrupts off for up to 1.6 s and nothing ticks while it does
; (src/disc.asm): a note left sounding would hold for all of it.
;                                destroys nothing
; ---------------------------------------------------------------------
SOUND_MUTE:     push af
                push bc
                push de
                push hl
                xor  a
                ld   (SND_REGS + 8),a
                ld   (SND_REGS + 9),a
                ld   (SND_REGS + 10),a
                call SND_FLUSH
                pop  hl
                pop  de
                pop  bc
                pop  af
                ret

; ---------------------------------------------------------------------
; SFX_REQ - ask for effect A. The most important request of a tick
; wins, and the tick starts it if it is no less important than the
; effect already playing (SND_SFX_START).
;                                destroys NOTHING - flags included:
;
; IT IS CALLED FROM ENEMY_WOUND, WHOSE CARRY IS ITS ANSWER. The caller
; of that routine `ret c`s on "it died" and holds a pointer on the
; stack the other way round, so a request that left a carry behind
; would unbalance the stack on the first drone she shot.
; ---------------------------------------------------------------------
SFX_REQ:        push af
                push hl
                ld   hl,SFX_REQ_ID
                cp   (hl)
                jr   c,.keep
                ld   (hl),a
.keep:          pop  hl
                pop  af
                ret

; ---------------------------------------------------------------------
; SND_WATCH - what the game did since the last tick.
;
; THE ORDER IS THE PRIORITY ONLY THROUGH SFX_REQ: a frame in which she
; fires and is hit asks for both, and the hit wins because it is the
; more important, not because it is asked for last.
; ---------------------------------------------------------------------
SND_WATCH:      ; her health: down is a hit, or her death; up is a medkit
                ld   hl,SW_HP
                ld   a,(PLAYER_HP)
                cp   (hl)
                ld   (hl),a
                jr   z,.mags
                ld   b,SFX_MEDKIT
                jr   nc,.hp
                ld   b,SFX_HURT
                or   a
                jr   nz,.hp
                ld   b,SFX_DIE
.hp:            ld   a,b
                call SFX_REQ
.mags:          ; FEWER ROUNDS IN HER GUNS IS A SHOT. More is a reload
                ; finishing, which has said so already when it began.
                ld   a,(MAG_LEFT)
                ld   hl,MAG_RIGHT
                add  a,(hl)
                ld   hl,SW_MAG
                cp   (hl)
                ld   (hl),a
                ld   a,SFX_SHOT
                call c,SFX_REQ
                ; a reload starting: RELOAD_TIMER leaving zero
                ld   hl,SW_RLD
                ld   a,(RELOAD_TIMER)
                ld   b,(hl)
                ld   (hl),a
                or   a
                jr   z,.reserve
                ld   a,b
                or   a
                ld   a,SFX_RELOAD
                call z,SFX_REQ
.reserve:       ; MORE IN RESERVE IS A CLIP. Less is a reload taking
                ; fourteen rounds out of it, which is not a pickup.
                ld   hl,SW_RES
                ld   a,(AMMO_RESERVE)
                ld   c,SFX_CLIP
                call .up
                ld   hl,SW_KEY
                ld   a,(KEYS_COUNT)
                ld   c,SFX_KEY
                call .up
                ld   hl,SW_COIN
                ld   a,(COINS_COUNT)
                ld   c,SFX_COIN
                call .up
                ; the idol: picked up is a key's chime, put down on the
                ; altar is the altar's
                ld   hl,SW_IDOL
                ld   a,(STATUES_HELD)
                cp   (hl)
                ld   (hl),a
                jr   z,.state
                ld   a,SFX_KEY
                jr   nc,.idol
                ld   a,SFX_ALTAR
.idol:          call SFX_REQ
.state:         ; the way out opening is the level's GS_CLEAR
                ld   hl,SW_GS
                ld   a,(GAME_STATE)
                ld   b,(hl)
                ld   (hl),a
                cp   GS_CLEAR
                ret  nz
                cp   b
                ret  z
                ld   a,SFX_DOOR
                jp   SFX_REQ

; HL = the watched copy, A = the byte now, C = the effect if it went UP
.up:            cp   (hl)
                ld   (hl),a
                ret  z
                ret  c
                ld   a,c
                jp   SFX_REQ

; SND_SYNC - the watch's copies are what the bytes say now.
SND_SYNC:       ld   a,(PLAYER_HP)
                ld   (SW_HP),a
                ld   a,(MAG_LEFT)
                ld   hl,MAG_RIGHT
                add  a,(hl)
                ld   (SW_MAG),a
                ld   a,(RELOAD_TIMER)
                ld   (SW_RLD),a
                ld   a,(AMMO_RESERVE)
                ld   (SW_RES),a
                ld   a,(KEYS_COUNT)
                ld   (SW_KEY),a
                ld   a,(COINS_COUNT)
                ld   (SW_COIN),a
                ld   a,(STATUES_HELD)
                ld   (SW_IDOL),a
                ld   a,(GAME_STATE)
                ld   (SW_GS),a
                ret

; ---------------------------------------------------------------------
; SND_SFX_START - the tick's request, if it outranks what is playing.
;
; The period and the noise are stored ONE STEP BACK, so that the step
; below - which adds its sweep before anything is heard - brings them
; to where the descriptor says on the effect's first tick.
; ---------------------------------------------------------------------
SND_SFX_START:  ld   hl,SFX_REQ_ID
                ld   a,(hl)
                ld   (hl),0                 ; a request lasts one tick
                or   a
                ret  z
                ld   hl,SX_PRIO
                cp   (hl)
                ret  c                      ; something more important plays
                ld   (hl),a
                dec  a
                add  a,a
                ld   e,a
                ld   d,0
                ld   hl,SFX_TABLE
                add  hl,de
                ld   e,(hl)
                inc  hl
                ld   d,(hl)
                ex   de,hl
                ld   a,(hl)
                ld   (SX_FLG),a
                inc  hl
                ld   b,(hl)                 ; noise
                inc  hl
                ld   a,(hl)                 ; ... and its step
                ld   (SX_NOID),a
                inc  hl
                ld   c,a
                ld   a,b
                sub  c
                ld   (SX_NOI),a
                ld   e,(hl)                 ; period
                inc  hl
                ld   d,(hl)
                inc  hl
                ld   c,(hl)                 ; ... and its sweep
                inc  hl
                ld   b,(hl)
                inc  hl
                ld   (SX_SWP),bc
                ld   (SX_EPTR),hl
                ex   de,hl
                or   a
                sbc  hl,bc
                ld   (SX_PER),hl
                ret

; SND_SFX_STEP - the effect's next tick; when its volumes run out, C is
; the music's again from this tick on.
SND_SFX_STEP:   ld   a,(SX_PRIO)
                or   a
                ret  z
                ld   hl,(SX_PER)
                ld   de,(SX_SWP)
                add  hl,de
                ld   (SX_PER),hl
                ld   a,(SX_NOID)
                ld   hl,SX_NOI
                add  a,(hl)
                ld   (hl),a
                ld   hl,(SX_EPTR)
                ld   a,(hl)
                cp   &FF
                jr   z,.done
                inc  hl
                ld   (SX_EPTR),hl
                ld   (SX_VOL),a
                ret
.done:          xor  a
                ld   (SX_PRIO),a
                ret

; ---------------------------------------------------------------------
; SND_VOICE - one tick of the voice at IX.
;
; The sweep comes FIRST, so the tick a note is struck is heard at the
; note's own period and the sweep moves it from the next tick on. That
; is what a kick drum is: a tone that starts at G3 and falls.
; ---------------------------------------------------------------------
SND_VOICE:      ld   l,(ix + MV_PER)
                ld   h,(ix + MV_PER + 1)
                ld   e,(ix + MV_SWP)
                ld   d,(ix + MV_SWP + 1)
                add  hl,de
                ld   (ix + MV_PER),l
                ld   (ix + MV_PER + 1),h
                dec  (ix + MV_CNT)
                jp   nz,SND_ENV
                ld   l,(ix + MV_PTR)
                ld   h,(ix + MV_PTR + 1)
SND_EVENT:      ld   a,(hl)
                inc  hl
                cp   &60
                jp   c,SND_NOTE
                jp   z,SND_REST
                cp   &61
                jp   z,SND_TIE
                cp   &C0
                jr   c,.len
                cp   &E0
                jr   c,.ins
                cp   &F0
                jr   c,.att
                cp   &F9
                jr   z,.lend
                cp   &FA
                jr   z,.lbeg
                cp   &FC
                jr   z,.ret
                cp   &FD
                jr   z,.call
                ld   a,(hl)                 ; &FF: go to
                inc  hl
                ld   h,(hl)
                ld   l,a
                jr   SND_EVENT
.len:           and  &3F
                inc  a
                ld   (ix + MV_LEN),a
                jr   SND_EVENT
.ins:           and  &1F
                add  a,a
                ld   e,a
                ld   d,0
                push hl
                ld   hl,SND_INSTR
                add  hl,de
                ld   e,(hl)
                inc  hl
                ld   d,(hl)
                pop  hl
                ld   (ix + MV_IPTR),e
                ld   (ix + MV_IPTR + 1),d
                jr   SND_EVENT
.att:           and  &0F
                ld   (ix + MV_ATT),a
                jr   SND_EVENT
.call:          ld   e,(hl)
                inc  hl
                ld   d,(hl)
                inc  hl
                ld   (ix + MV_RET),l
                ld   (ix + MV_RET + 1),h
                ex   de,hl
                jr   SND_EVENT
.ret:           ld   l,(ix + MV_RET)
                ld   h,(ix + MV_RET + 1)
                jr   SND_EVENT
.lbeg:          ld   a,(hl)
                inc  hl
                ld   (ix + MV_LCNT),a
                ld   (ix + MV_LPTR),l
                ld   (ix + MV_LPTR + 1),h
                jp   SND_EVENT
.lend:          dec  (ix + MV_LCNT)
                jp   z,SND_EVENT
                ld   l,(ix + MV_LPTR)
                ld   h,(ix + MV_LPTR + 1)
                jp   SND_EVENT

; A = the note, HL = the byte after it
SND_NOTE:       ld   (ix + MV_PTR),l
                ld   (ix + MV_PTR + 1),h
                ld   b,4                    ; shifts = octave + 4
.oct:           cp   12
                jr   c,.semi
                sub  12
                inc  b
                jr   .oct
.semi:          add  a,a
                ld   e,a
                ld   d,0
                ld   hl,SND_NOTE_BASE
                add  hl,de
                ld   a,(hl)
                inc  hl
                ld   h,(hl)
                ld   l,a
                dec  b                      ; (b >> (s - 1)) + 1, then >> 1:
.sh:            srl  h                      ; the rounded b >> s, with the
                rr   l                      ; floor arithmetic of
                djnz .sh                    ; tools/make_music.py
                inc  hl
                srl  h
                rr   l
                ld   (ix + MV_PER),l
                ld   (ix + MV_PER + 1),h
                ; ... and the instrument: flags, noise, sweep, envelope
                ld   l,(ix + MV_IPTR)
                ld   h,(ix + MV_IPTR + 1)
                ld   a,(hl)
                ld   (ix + MV_FLG),a
                inc  hl
                ld   a,(hl)
                ld   (ix + MV_NOI),a
                inc  hl
                ld   a,(hl)
                ld   (ix + MV_SWP),a
                inc  hl
                ld   a,(hl)
                ld   (ix + MV_SWP + 1),a
                inc  hl
                jr   SND_ARM_ENV

SND_REST:       ld   (ix + MV_PTR),l
                ld   (ix + MV_PTR + 1),h
                xor  a
                ld   (ix + MV_SWP),a
                ld   (ix + MV_SWP + 1),a
                ld   hl,SND_ZERO
SND_ARM_ENV:    ld   (ix + MV_EPTR),l
                ld   (ix + MV_EPTR + 1),h
                jr   SND_ARM

SND_TIE:        ld   (ix + MV_PTR),l
                ld   (ix + MV_PTR + 1),h
SND_ARM:        ld   a,(ix + MV_LEN)
                ld   (ix + MV_CNT),a
                ; THE ENVELOPE: this tick's level, and a step on - unless
                ; the next byte is the &FF that says hold this one
SND_ENV:        ld   l,(ix + MV_EPTR)
                ld   h,(ix + MV_EPTR + 1)
                ld   a,(hl)
                ld   (ix + MV_VOL),a
                inc  hl
                ld   a,(hl)
                inc  a
                ret  z
                ld   (ix + MV_EPTR),l
                ld   (ix + MV_EPTR + 1),h
                ret

; ---------------------------------------------------------------------
; SND_MIX - the eleven registers this tick wants, into SND_REGS.
; ---------------------------------------------------------------------
SND_MIX:        ld   ix,SND_VA
                ld   hl,SND_REGS
                call .period
                ld   ix,SND_VB
                call .period
                ld   a,(SX_PRIO)
                or   a
                jr   nz,.sfx
                ld   ix,SND_VC
                call .period
                ld   a,(ix + MV_NOI)
                and  &1F
                ld   (hl),a                 ; R6
                ld   a,(ix + MV_FLG)
                ld   (SND_CFLG),a
                call .level
                jr   .mixer
.sfx:           ld   de,(SX_PER)
                ld   (hl),e                 ; R4
                inc  hl
                ld   a,d
                and  &0F
                ld   (hl),a                 ; R5
                inc  hl
                ld   a,(SX_NOI)
                and  &1F
                ld   (hl),a                 ; R6
                ld   a,(SX_FLG)
                ld   (SND_CFLG),a
                ld   a,(SX_VOL)             ; an effect is never faded
.mixer:         ld   (SND_REGS + 10),a
                ; R7: everything off, and each voice clears its own bits
                ld   c,SND_MIX_OFF
                ld   a,(SND_VA + MV_FLG)
                rra
                jr   nc,.a_quiet
                res  0,c
.a_quiet:       ld   a,(SND_VB + MV_FLG)
                rra
                jr   nc,.b_quiet
                res  1,c
.b_quiet:       ld   a,(SND_CFLG)
                rra
                jr   nc,.c_tone
                res  2,c
.c_tone:        rra
                jr   nc,.c_noise
                res  5,c
.c_noise:       ld   a,c
                ld   (SND_REGS + 7),a
                ld   ix,SND_VA
                call .level
                ld   (SND_REGS + 8),a
                ld   ix,SND_VB
                call .level
                ld   (SND_REGS + 9),a
                ret

; the period at IX into (HL) and (HL+1), and on
.period:        ld   a,(ix + MV_PER)
                ld   (hl),a
                inc  hl
                ld   a,(ix + MV_PER + 1)
                and  &0F
                ld   (hl),a
                inc  hl
                ret

; A = the level at IX, less its attenuation and the fade's, not below 0
.level:         ld   a,(ix + MV_VOL)
                sub  (ix + MV_ATT)
                jr   c,.zero
                ld   e,a
                ld   a,(SND_ATTEN)
                ld   d,a
                ld   a,e
                sub  d
                ret  nc
.zero:          xor  a
                ret

; ---------------------------------------------------------------------
; SND_FLUSH - every register whose wanted value is not the one last
; written, written. On a tick with nothing new that is the three levels
; at most, and an unchanged period is never rewritten - which on this
; chip is also the safe thing, since nothing here wants a tone's phase
; touched.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
SND_FLUSH:      ld   hl,SND_REGS
                ld   de,SND_LAST
.reg:           ld   a,(de)
                cp   (hl)
                jr   z,.same
                ld   a,(hl)
                ld   (de),a
                ld   a,l
                sub  SND_REGS AND 255       ; the register number
                ld   b,PSG_DATA
                out  (c),a
                ld   bc,PSG_CTRL * 256 + PSG_SELECT
                out  (c),c
                ld   c,PSG_IDLE
                out  (c),c
                ld   a,(hl)
                ld   b,PSG_DATA
                out  (c),a
                ld   bc,PSG_CTRL * 256 + PSG_WRITE
                out  (c),c
                ld   c,PSG_IDLE
                out  (c),c
.same:          inc  hl
                inc  de
                ld   a,l
                cp   (SND_REGS + 11) AND 255
                jr   nz,.reg
                ret

; A tune with nothing in it, which is what plays before the first one.
SND_QUIET_HDR:  dw SND_QUIET, SND_QUIET, SND_QUIET
SND_QUIET:      db &80 + 63, &60, &FF
                dw SND_QUIET
SND_ZERO:       db 0, &FF                   ; a rest's envelope

; ---------------------------------------------------------------------
; The state. SOUND_INIT clears all of it.
; ---------------------------------------------------------------------
SND_STATE:
SND_VA:         ds MV_SIZE
SND_VB:         ds MV_SIZE
SND_VC:         ds MV_SIZE
SND_REGS:       ds 11           ; what this tick wants, R0..R10
SND_LAST:       ds 11           ; ... and what the chip was last given
SND_TUNE:       db 0            ; the tune playing
SND_TICKS:      db 0            ; ticks played - what a test syncs on
SND_PHASE:      db 0            ; SOUND_HALF's other call
SND_ATTEN:      db 0            ; the fade's, for the music only
SND_CFLG:       db 0            ; channel C's flags this tick
SFX_REQ_ID:     db 0            ; the tick's request, 0 for none
SX_PRIO:        db 0            ; the effect playing, 0 for none
SX_FLG:         db 0
SX_NOI:         db 0
SX_NOID:        db 0
SX_VOL:         db 0
SX_PER:         dw 0
SX_SWP:         dw 0
SX_EPTR:        dw 0
SW_HP:          db 0            ; the watch's copies (SND_WATCH)
SW_MAG:         db 0
SW_RLD:         db 0
SW_RES:         db 0
SW_KEY:         db 0
SW_COIN:        db 0
SW_IDOL:        db 0
SW_GS:          db 0
SND_STATE_N     equ $ - SND_STATE

                ; SND_FLUSH counts registers by the LOW byte of HL
                assert (SND_REGS AND &FF00) == ((SND_REGS + 11) AND &FF00)
                assert ((SND_REGS + 11) AND 255) != 0

                include "music.inc"
