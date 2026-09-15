; =====================================================================
; input.asm - keyboard and joystick, with no firmware underneath
;
; The CPC keyboard is not a port. It is a matrix wired to the AY-3-8912's
; I/O port A, reached through the 8255 PPI, and the game has switched
; both ROMs out - so every step the OS would normally do has to be done
; here. The sequence below was established on the emulator, one key at a
; time, with a negative control for each failure mode:
;
;   1. OUT &F7,&82   PPI port A = OUTPUT
;   2. OUT &F4,14    AY register number 14 onto the bus
;   3. OUT &F6,&C0   BDIR+BC1: latch that register address
;   4. OUT &F6,&00   release
;   5. OUT &F7,&92   PPI port A = INPUT
;   6. per row: OUT &F6,&40|row  then  IN A,(&F4)
;   7. OUT &F7,&82   hand the chip back
;
; A bit reads 0 while its key is held, so the scan complements.
;
; FOUR WAYS THIS GOES WRONG, each verified by building it wrong:
;
;  1. The AY address latch is ONE global register shared with the sound
;     chip. If an interrupt lands between step 3 and step 6 and a music
;     player re-points it, the scan reads a tone period instead of the
;     keyboard: 45 of 301 scans came back corrupt. INPUT_SCAN must be
;     called with interrupts disabled. It does not do its own DI - see
;     the note on interrupt phase below.
;  2. A PPI mode-set word (&82 or &92) also zeroes all three output
;     latches, port C included. Write the control word BEFORE the row
;     select, never after, or the row number is wiped.
;  3. AY register 7 bit 6 sets port A's direction. If a sound driver
;     ever writes R7 with bit 6 SET, every row reads &FF for ever and
;     the game looks like it has dead input rather than a sound bug.
;     *** CONTRACT FOR MODULE 7: R7 bit 6 must always be 0. ***
;  4. Leaving port A an INPUT on exit makes the sound driver's register
;     writes vanish silently. The scan exits with it an OUTPUT.
;
; INTERRUPT PHASE: the caller's DI displaces whichever interrupt it
; overlaps. Called at the top of a frame that measurably moved the first
; interrupt by 4.4 scanlines, which Module 6's raster splits would
; inherit. The scan therefore runs mid-frame, after the scroll step.
; =====================================================================

; THE BYTE IS FULL, and the two controls the action state machine needs
; cost the two spare bits. Bits 0-3 have to stay in the JOYSTICK's own
; order - that is what lets row 9 fold in below with no shifting at all
; - so the new ones took 5 and 7:
IN_UP           equ %00000001   ; jump, and interact (plan.md 5.2: "αν πατηθεί UP")
IN_DOWN         equ %00000010   ; crouch, and with FIRE, reload
IN_LEFT         equ %00000100
IN_RIGHT        equ %00001000
IN_FIRE         equ %00010000   ; SPACE - draw, hold, release (CLAUDE.md 8.4)
IN_ROLL         equ %00100000   ; Z
IN_PAUSE        equ %01000000   ; ESC
IN_RUN          equ %10000000   ; SHIFT
IN_INTERACT     equ IN_UP       ; Z WAS a second interact alongside RETURN.
                                ; It is the roll now and RETURN went with
                                ; it, which leaves interact as UP alone -
                                ; what plan.md 5.2 asked for in the first
                                ; place. A ninth control needs a second
                                ; byte, not a re-shuffle.

                macro KEYROW row,ident
                ld   bc,PPI_PORT_C * 256 + AY_REG_READ + {row}
                out  (c),c              ; select the row, assert BC1
                ld   b,PPI_PORT_A
                in   a,(c)              ; that row's key bits
                cpl                     ; 1 = pressed
                ld   e,a                ; keep it for the KEYBITs
                if {ident}
                and  {ident}            ; bits already on the right action
                or   d
                ld   d,a
                endif
                mend

                macro KEYBIT bit,action
                bit  {bit},e            ; 8
                jr   z,$+4              ; 12/8 - skips exactly the 2-byte SET
                set  {action},d         ; 8
                mend

; ---------------------------------------------------------------------
; INPUT_SCAN - sample the control scheme.
;
; OUT: (INPUT_NOW)     actions held
;      (INPUT_PRESSED) actions that went down since the last scan
; destroys AF,BC,DE.  HL, IX, IY, SP and both shadow sets untouched.
;
; *** CALL WITH INTERRUPTS DISABLED *** - see hazard 1 above.
;
; Six rows, not ten: rows 3, 4, 6 and 7 carry no bound key and cost 60 T
; each to learn nothing.
; ---------------------------------------------------------------------
INPUT_SCAN:     ld   bc,PPI_CONTROL * 256 + PPI_CTL_PA_OUT
                out  (c),c
                ld   bc,PPI_PORT_A * 256 + AY_R14_KEYBOARD
                out  (c),c
                ld   bc,PPI_PORT_C * 256 + AY_REG_SELECT
                out  (c),c              ; latch the register address
                ld   bc,PPI_PORT_C * 256 + AY_INACTIVE
                out  (c),c
                ld   bc,PPI_CONTROL * 256 + PPI_CTL_PA_IN
                out  (c),c              ; zeroes port C again - hence always
                ld   d,0                ; BEFORE the row select

                ; ---- row 9: joystick 0 ------------------------------
                ; BOTH fire bits fold onto IN_FIRE. Neither is bound to a
                ; second action: this machine cannot distinguish them, and
                ; guessing wrong makes every trigger pull open doors.
                ld   bc,PPI_PORT_C * 256 + AY_REG_READ + 9
                out  (c),c
                ld   b,PPI_PORT_A
                in   a,(c)
                cpl
                and  %00111111          ; drop DEL (b7) and the spare pin
                ld   e,a
                and  %00100000          ; fire-b ...
                rrca                    ; ... folded onto fire-a
                or   e
                and  %00011111
                ld   d,a

                ; ---- the keyboard bindings, and nothing else ---------
                KEYROW 0,IN_UP          ; cursor UP already sits on bit 0
                KEYBIT 1,3              ; cursor RIGHT -> IN_RIGHT
                KEYBIT 2,1              ; cursor DOWN  -> IN_DOWN
                KEYROW 1,0
                KEYBIT 0,2              ; cursor LEFT  -> IN_LEFT
                KEYROW 2,0
                KEYBIT 6,7              ; SHIFT        -> IN_RUN
                KEYROW 5,0
                KEYBIT 7,4              ; SPACE        -> IN_FIRE
                KEYROW 8,0
                KEYBIT 2,6              ; ESC          -> IN_PAUSE
                KEYBIT 7,5              ; Z            -> IN_ROLL

                ld   bc,PPI_CONTROL * 256 + PPI_CTL_PA_OUT
                out  (c),c              ; hand the AY back to the sound driver

                ; ---- edge detection, on its OWN previous-state byte ---
                ld   a,(INPUT_PREV)
                cpl
                and  d                  ; down now AND NOT down before
                ld   (INPUT_PRESSED),a
                ld   a,d
                ld   (INPUT_NOW),a
                ld   (INPUT_PREV),a
                ret

; ---------------------------------------------------------------------
; INPUT_DISCARD - swallow everything currently held until it is released.
;
; INPUT_PREV is a separate byte from INPUT_NOW precisely so this cannot
; leave INPUT_NOW = &FF. A version that poisoned INPUT_NOW gave Kara one
; frame of walking left AND right while jumping AND crouching, which in a
; physics integrator is how a sprite ends up inside a wall.
;                                destroys AF
; ---------------------------------------------------------------------
INPUT_DISCARD:  ld   a,&FF
                ld   (INPUT_PREV),a
                xor  a
                ld   (INPUT_PRESSED),a
                ld   (INPUT_NOW),a
                ret

; ---------------------------------------------------------------------
; INPUT_INIT - claim the PPI. Nothing else in the game writes &F7, and
; the dead firmware's port direction is not ours to inherit.
;                                destroys AF,BC
; ---------------------------------------------------------------------
INPUT_INIT:     ld   bc,PPI_CONTROL * 256 + PPI_CTL_PA_OUT
                out  (c),c
                jp   INPUT_DISCARD      ; the RETURN still held from RUN"DISC
                                        ; must not fire a round on frame 1

INPUT_NOW:      db 0
INPUT_PREV:     db &FF
INPUT_PRESSED:  db 0
