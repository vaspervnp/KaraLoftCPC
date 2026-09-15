; =====================================================================
; disc.asm - reading the level data off the floppy, mid-game  (MODULE 5)
;
; The boot sequence disables both ROMs (see 4), so there is no firmware
; left to call: the OS is not in memory, AMSDOS is not paged in, and the
; engine itself lives at &0040-&3FFF where the lower ROM would be. Going
; back for a load would mean re-enabling the ROMs over the top of the
; engine, running the call from high RAM, and keeping the firmware's
; workspace at &B100-&BFFF and AMSDOS's buffers at &A700 intact for the
; whole game - three constraints on the memory map for the sake of a
; routine that is 250 bytes to write.
;
; So this talks to the uPD765 directly.
;
;       &FA7E   bit 0 = motor on          (write)
;       &FB7E   main status register      (read)
;       &FB7F   data register             (read/write)
;
; *** READ docs/AmstradDskReadHowTo.md BEFORE CHANGING ANY OF THIS. ***
;
; The first version of this file passed every test here and showed a
; BLACK SCREEN on Retro Virtual Machine, because the headless emulator
; models the controller as a state machine that resolves the instant
; the last command byte is written and never runs out of patience. A
; real uPD765 does neither. Four separate faults, every one of them
; invisible to cpcemu and every one of them already paid for in
; ~/repos/Homeplanet/src/sys/fdc.asm - this is that code's shape:
;
;   1. END OF CYLINDER IS NOT AN ERROR. A single-sector transfer sends
;      EOT equal to R, so a real controller reaches the end of the
;      cylinder as a matter of course and says so with IC=01 and ST1
;      bit 7. The data is already in memory. `AND &C0 / RET NZ` calls
;      that a failure; cpcemu returns IC=00 and never disagrees.
;   2. THE EXECUTION LOOP MUST WATCH RQM, DIO AND EXM TOGETHER. A
;      refused command never enters the execution phase at all, and a
;      transfer the controller gives up on leaves it early - either way
;      it is trying to hand us result bytes while we wait for data.
;      Testing EXM in a SEPARATE `in` before RQM is also a race: the
;      chip has not decided yet, EXM reads 0, and we settle down to
;      wait for a result phase that is not happening.
;   3. DRAIN THE RESULT BY STATUS, NOT BY COUNT. READ returns seven
;      bytes, SENSE INTERRUPT STATUS two - and SENSE with nothing
;      pending returns ONE. Counting to two there waits forever.
;   4. A SEEK IS COLLECTED WITH SENSE INTERRUPT STATUS, NOT BY WATCHING
;      CB. The datasheet raises CB microseconds after the last command
;      byte and clears it on the SENSE - so polling it either falls
;      straight through a seek that has not begun or waits for
;      something only the next line can cause. cpcemu never sets it.
;
; And a fifth that is ours: NOTHING HERE MAY HANG. A black screen with
; no way out is worse than a level that fails to load, so every wait
; that is not the inner transfer loop is counted out, and DISC_READ
; returns carry clear rather than spinning.
;
; THE LEVEL DATA IS NOT IN THE FILESYSTEM. tools/dskdata.py writes the
; packed streams to raw sectors from track DISC_DATA_TRACK on, past
; anything AMSDOS allocated, and emits their track and sector.
;
; INTERRUPTS MUST BE OFF during a transfer. The 765 has no FIFO on this
; machine - one byte in the data register and an overrun if it is not
; taken within 32 microseconds. The caller holds DI for the whole load
; and re-anchors the raster gates afterwards.
; =====================================================================

FDC_MOTOR       equ &FA7E                   ; bit 0 = motor on
FDC_STATUS      equ &FB7E                   ; main status register
FDC_DATA        equ &FB7F                   ; ... one INC C away. That is
                                            ; load-bearing: see the loop.

FDC_ST_RQM      equ %10000000               ; a byte can move
FDC_ST_DIO      equ %01000000               ; 1 = FDC to CPU
FDC_ST_EXM      equ %00100000               ; execution phase under way
FDC_ST_CB       equ %00010000               ; a command is in progress

FDC_ST0_SE      equ %00100000               ; seek end - the head arrived
FDC_ST0_NR      equ %00001000               ; not ready: no disc, no drive

FDC_ST1_MA      equ %00000001               ; missing address mark
FDC_ST1_ND      equ %00000100               ; no data: sector not found
FDC_ST1_OR      equ %00010000               ; overrun: we were too slow
FDC_ST1_DE      equ %00100000               ; data error: a CRC failed
FDC_ST1_REAL    equ FDC_ST1_MA + FDC_ST1_ND + FDC_ST1_OR + FDC_ST1_DE
                                            ; ... and NOT bit 7, EN, which
                                            ; a single-sector read always
                                            ; sets. See note 1 above.

FDC_CMD_READ    equ &46                     ; READ DATA, MFM
FDC_CMD_SEEK    equ &0F
FDC_CMD_SENSE   equ &08                     ; SENSE INTERRUPT STATUS

DISC_SECT_FIRST equ &C1                     ; AMSDOS DATA format, 9 sectors
DISC_SECT_LAST  equ &C9
DISC_SECT_SIZE  equ 512
DISC_SECT_N     equ 2                       ; the N code for 512 bytes

FDC_SEEK_ROUNDS equ 0                       ; 0 = 256 times round
FDC_SEEK_SETTLE equ 1200                    ; ~8 ms of DEC BC at 4 MHz

; ---------------------------------------------------------------------
; DISC_MOTOR_ON / DISC_MOTOR_OFF
;
; The spin-up is only paid when the motor was actually off. It is about
; half a second on real hardware and the emulator does not care, but a
; read issued into a stopped drive fails on both.
;                                destroys AF,BC,HL
; ---------------------------------------------------------------------
DISC_MOTOR_ON:  ld   a,(DISC_MOTOR_STATE)
                or   a
                ret  nz
                inc  a
                ld   (DISC_MOTOR_STATE),a
                ld   bc,FDC_MOTOR
                out  (c),a
                ld   hl,20000               ; ~560,000 T of spin-up
.spin:          dec  hl
                ld   a,h
                or   l
                jr   nz,.spin
                ret

DISC_MOTOR_OFF: xor  a
                ld   (DISC_MOTOR_STATE),a
                ld   bc,FDC_MOTOR
                out  (c),a
                ret

; ---------------------------------------------------------------------
; FDC_OUT - one byte to the controller, once it says it wants one.
;
; IN : A = the byte
; OUT: carry SET if it went. Carry clear means the controller did not
;      ask inside ~3 ms, which is thousands of times longer than it
;      needs and is the difference between a failed load and a dead
;      machine.
;      destroys AF,BC,DE
; ---------------------------------------------------------------------
FDC_OUT:        ld   e,a
                ld   d,0                    ; 256 polls
                ld   bc,FDC_STATUS
.wait:          in   a,(c)
                and  FDC_ST_RQM + FDC_ST_DIO
                cp   FDC_ST_RQM             ; ready, and wanting one from us
                jr   z,.go
                dec  d
                jr   nz,.wait
                or   a                      ; timed out
                ret
.go:            inc  c                      ; -> FDC_DATA
                out  (c),e
                scf
                ret

; ---------------------------------------------------------------------
; FDC_IN - one byte from it. Carry SET if a byte came.
;                                destroys AF,BC,DE
; ---------------------------------------------------------------------
FDC_IN:         ld   d,0
                ld   bc,FDC_STATUS
.wait:          in   a,(c)
                and  FDC_ST_RQM + FDC_ST_DIO
                cp   FDC_ST_RQM + FDC_ST_DIO
                jr   z,.go
                dec  d
                jr   nz,.wait
                or   a
                ret
.go:            inc  c
                in   a,(c)
                scf
                ret

; ---------------------------------------------------------------------
; FDC_DRAIN - take every result byte the controller is holding.
;
; BY STATUS, NOT BY COUNT. READ returns seven, SENSE INTERRUPT STATUS
; returns two, and a SENSE with nothing pending returns ONE - so a
; counted drain has to have the count right everywhere, and being one
; too high is a wait for a byte that never comes.
;
; The first three bytes are kept as ST0/ST1/ST2 and the rest binned.
; Runs before the FIRST command too: AMSDOS ran before us and the chip
; keeps its state across the ROMs going out, so anything it left in the
; result phase would swallow our first command byte.
;
; OUT: (DISC_ST0/ST1/ST2). Returns at once when CB is already clear.
;      destroys AF,BC,HL
; ---------------------------------------------------------------------
FDC_DRAIN:      ld   hl,DISC_ST0
.drain:         ld   bc,FDC_STATUS
                in   a,(c)
                bit  4,a                    ; CB: still working?
                ret  z                      ; idle, nothing left to take
                bit  7,a                    ; RQM
                jr   z,.drain
                ld   bc,FDC_DATA
                in   a,(c)
                ld   (hl),a
                ld   a,l
                cp   DISC_SPILL AND 255     ; ST0, ST1, ST2, then the bin
                jr   z,.drain
                inc  hl
                jr   .drain

; ---------------------------------------------------------------------
; FDC_SENSE_INT - what was the last interrupt about?
; OUT: A = ST0, and (DISC_ST0) the same. Zero if nothing came back.
;
; (DISC_ST0) is cleared FIRST, because FDC_DRAIN writes nothing at all
; when CB is already clear - so a controller that declines to answer
; would leave the PREVIOUS ST0 sitting there, and a previous ST0 with
; SEEK END in it reads as "the head has arrived" for a seek that has
; not started.
;                                destroys AF,BC,HL - D is left alone,
;                                FDC_SEEK counts rounds in it
; ---------------------------------------------------------------------
FDC_SENSE_INT:  xor  a
                ld   (DISC_ST0),a
                ld   a,FDC_CMD_SENSE
                push de
                call FDC_OUT
                pop  de
                call FDC_DRAIN
                ld   a,(DISC_ST0)
                ret

; ---------------------------------------------------------------------
; FDC_SEEK - put the head over (DISC_TRACK) and wait for it to arrive.
;
; READ DATA does NOT seek. It takes a cylinder number and checks it
; against what is under the head, so arriving on the wrong track is
; reported as "sector not found" with the word seek appearing nowhere.
; That is what makes this routine's one job worth more than it looks.
;                                destroys everything
; ---------------------------------------------------------------------
FDC_SEEK:       ; Take whatever seek-end the controller is still holding
                ; BEFORE starting ours, or the wait below takes that
                ; stale answer for this seek's and the read starts while
                ; the head is still moving. AMSDOS ran before us, and a
                ; seek of our own that timed out leaves one too.
                ld   d,4
.flush:         call FDC_SENSE_INT
                and  FDC_ST0_SE
                jr   z,.issue
                dec  d
                jr   nz,.flush

.issue:         ld   a,FDC_CMD_SEEK
                call FDC_OUT
                ret  nc
                xor  a
                call FDC_OUT                ; drive 0, head 0
                ret  nc
                ld   a,(DISC_TRACK)
                call FDC_OUT
                ret  nc

                ld   d,FDC_SEEK_ROUNDS
.wait:          call FDC_SENSE_INT
                and  FDC_ST0_SE
                scf
                ret  nz                     ; the head is where we asked
                ld   bc,FDC_SEEK_SETTLE
.settle:        dec  bc
                ld   a,b
                or   c
                jr   nz,.settle
                dec  d
                jr   nz,.wait
                or   a                      ; gave up: ~2 s, far longer than
                ret                         ; a 40-track seek can take

; ---------------------------------------------------------------------
; FDC_READ_ONE - sector (DISC_SECT) of (DISC_TRACK) into (DISC_PTR).
;
; OUT: carry SET on success, (DISC_PTR) advanced past the sector.
;      destroys everything
; ---------------------------------------------------------------------
FDC_READ_ONE:   ld   a,FDC_CMD_READ
                call FDC_OUT
                ret  nc
                xor  a
                call FDC_OUT                ; (head << 2) | unit
                ret  nc
                ld   a,(DISC_TRACK)
                call FDC_OUT                ; C - must match the head
                ret  nc
                xor  a
                call FDC_OUT                ; H
                ret  nc
                ld   a,(DISC_SECT)
                call FDC_OUT                ; R
                ret  nc
                ld   a,DISC_SECT_N
                call FDC_OUT                ; N
                ret  nc
                ld   a,(DISC_SECT)
                call FDC_OUT                ; EOT - the LAST sector of the
                ret  nc                     ; transfer, so R for a single one
                ld   a,&2A
                call FDC_OUT                ; GPL
                ret  nc
                ld   a,&FF
                call FDC_OUT                ; DTL, unused while N is non-zero
                ret  nc

                ; ---- execution phase ---------------------------------
                ; BC HOLDS THE STATUS PORT FOR THE WHOLE TRANSFER and the
                ; data port is one INC C away: &FB7E and &FB7F differ in
                ; bit 0 alone. Reloading both twice a byte is 20 T on a
                ; loop whose deadline is 128, and it is not a
                ; micro-optimisation - it is the difference between 26
                ; and 33 microseconds a byte, and the controller gives up
                ; at 32. cpcemu feeds the byte synchronously and can
                ; never produce the overrun.
                ld   hl,(DISC_PTR)
                ld   de,DISC_SECT_SIZE
                ld   bc,FDC_STATUS
.byte:          in   a,(c)                          ; 12
                and  FDC_ST_RQM+FDC_ST_DIO+FDC_ST_EXM   ; 8
                cp   FDC_ST_RQM+FDC_ST_DIO+FDC_ST_EXM   ; 8
                jr   z,.go                          ; 12  executing, byte ready
                bit  5,a                            ;     EXM still up? then it
                jr   nz,.byte                       ;     has not got there yet
                bit  7,a                            ;     RQM not up either?
                jr   z,.byte                        ;     it has not decided
                jr   .result                        ;     RQM up, EXM down:
.go:            inc  c                              ; 4   the result phase
                in   a,(c)                          ; 12
                dec  c                              ; 4
                ld   (hl),a                         ; 8
                inc  hl                             ; 8
                dec  de                             ; 8
                ld   a,d                            ; 4
                or   e                              ; 4
                jr   nz,.byte                       ; 12  -- 104 T a byte
                ld   (DISC_PTR),hl

.result:        call FDC_DRAIN
                ; falls into the verdict

; ---------------------------------------------------------------------
; FDC_XFER_OK - did the transfer actually move the data?
;
; "ST0 bits 7-6 are 00 or it failed" IS WRONG ON REAL HARDWARE, and it
; is the single reason this game showed a black screen on RVM while
; every test here passed. EOT equals R for a single sector, so the
; controller reaches the end of the cylinder as a matter of course and
; reports it with IC=01 and ST1 bit 7 - END OF CYLINDER. The bytes are
; already in memory; the chip is saying it has finished.
;
; So EN alone is success. A fault is IC != 00 together with NOT READY,
; or something in ST1 that names an actual failure, or anything in ST2.
; OUT: carry SET if the data is good.        destroys AF
; ---------------------------------------------------------------------
FDC_XFER_OK:    ld   a,(DISC_ST0)
                and  &C0
                jr   z,.ok                  ; IC = 00: plainly normal
                cp   &40
                jr   nz,.bad                ; &80 invalid, &C0 polling

                ld   a,(DISC_ST0)           ; NOT READY first: an empty drive
                and  FDC_ST0_NR             ; is ST0 = &48 with ST1 = &00, and
                jr   nz,.bad                ; a check that only read ST1 called
                                            ; that a successful read
                ld   a,(DISC_ST1)
                and  FDC_ST1_REAL
                jr   nz,.bad
                ld   a,(DISC_ST2)
                or   a
                jr   nz,.bad
.ok:            scf
                ret
.bad:           or   a
                ret

; ---------------------------------------------------------------------
; DISC_READ - consecutive sectors into memory, across tracks.
;
; IN : (DISC_TRACK) first track, (DISC_SECT) first sector id,
;      (DISC_COUNT) sectors to read, (DISC_PTR) destination
; OUT: carry SET on success; on failure carry clear and DISC_ST0/1/2
;      hold what the controller said.
;      destroys AF,BC,DE,HL
;
; ONE SECTOR AN OPERATION, not a multi-sector READ DATA with EOT.
; AMSDOS formats with a 2:1 interleave (C1 C6 C2 C7 ...) precisely so
; that reading in ID order leaves a sector's worth of time between one
; read and the next, which is what the command overhead fits into. The
; seek is only paid when the track actually changes.
; ---------------------------------------------------------------------
DISC_READ:      call DISC_MOTOR_ON
                call FDC_DRAIN              ; whatever AMSDOS left behind
                ld   a,&FF
                ld   (DISC_HEAD),a          ; seek on the first sector, so the
                                            ; controller and we agree on where
                                            ; the head is
.sector:        ld   a,(DISC_COUNT)
                or   a
                scf                         ; nothing left: success
                ret  z

                ld   a,(DISC_TRACK)
                ld   hl,DISC_HEAD
                cp   (hl)
                jr   z,.on_track
                ld   (hl),a
                call FDC_SEEK
                ret  nc                     ; the head never arrived
.on_track:
                call FDC_READ_ONE
                ret  nc

                ld   hl,DISC_COUNT
                dec  (hl)
                ld   hl,DISC_SECT
                inc  (hl)
                ld   a,(hl)
                cp   DISC_SECT_LAST + 1
                jr   c,.sector              ; still inside the track
                ld   (hl),DISC_SECT_FIRST
                ld   hl,DISC_TRACK
                inc  (hl)
                jr   .sector

DISC_MOTOR_STATE: db 0
DISC_HEAD:      db &FF          ; the track the head is on, &FF = unknown
DISC_TRACK:     db 0
DISC_SECT:      db 0
DISC_COUNT:     db 0
DISC_PTR:       dw 0
; These four are walked with an INC L in FDC_DRAIN, so they have to stay
; in this order, adjacent, and inside one page - main.asm asserts it.
DISC_ST0:       db 0
DISC_ST1:       db 0
DISC_ST2:       db 0
DISC_SPILL:     db 0
