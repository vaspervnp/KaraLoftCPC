; =====================================================================
; disc.asm - reading the level data off the floppy, mid-game  (MODULE 5)
;
; The boot sequence disables both ROMs (see 4), so there is no firmware
; left to call: the OS is not in memory, AMSDOS is not paged in, and the
; engine itself lives at &0040-&3FFF where the lower ROM would be. Going
; back for a load would mean re-enabling the ROMs over the top of the
; engine, running the call from high RAM, and keeping the firmware's
; workspace at &B100-&BFFF and AMSDOS's buffers at &A700 intact for the
; whole game - which is three constraints on the memory map for the sake
; of a routine that is 200 bytes to write.
;
; So this talks to the uPD765 directly.
;
;       &FA7E   bit 0 = motor on          (write)
;       &FB7E   main status register      (read)
;       &FB7F   data register             (read/write)
;
; Main status bits: 7 RQM (a byte can move), 6 DIO (1 = FDC to CPU),
; 5 EXM (execution phase), 4 CB (busy).
;
; THE LEVEL DATA IS NOT IN THE FILESYSTEM. tools/dskdata.py writes the
; packed streams to raw sectors from track DISC_DATA_TRACK on, past
; anything AMSDOS allocated, and emits their track and sector. That
; costs nothing but a build step and saves parsing a directory.
;
; INTERRUPTS MUST BE OFF during a transfer. The 765 has no FIFO on this
; machine - one byte in the data register and an overrun if it is not
; taken in time. A level change is not running the game loop, so the
; whole load runs under DI and the raster gates are re-anchored after.
; =====================================================================

FDC_MOTOR       equ &FA7E
FDC_STATUS      equ &FB7E                   ; ... and &FB7F is the data

DISC_SECT_FIRST equ &C1                     ; AMSDOS DATA format, 9 sectors
DISC_SECT_LAST  equ &C9
DISC_SECT_SIZE  equ 512

; ---------------------------------------------------------------------
; DISC_MOTOR_ON - and wait for the drive to come up to speed.
;
; The delay is only paid when the motor was actually off. It is about a
; second on real hardware and the emulator does not care, but a read
; issued into a stopped drive fails on both.
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

; ---------------------------------------------------------------------
; DISC_MOTOR_OFF                destroys AF,BC
; ---------------------------------------------------------------------
DISC_MOTOR_OFF: xor  a
                ld   (DISC_MOTOR_STATE),a
                ld   bc,FDC_MOTOR
                out  (c),a
                ret

; ---------------------------------------------------------------------
; DISC_READ - read consecutive sectors into memory, across tracks.
;
; IN : (DISC_TRACK) first track, (DISC_SECT) first sector id,
;      (DISC_COUNT) sectors to read, (DISC_PTR) destination
; OUT: carry SET on success. On failure carry is clear and (DISC_ST)
;      holds the seven result bytes, whose ST0 bits 6-7 are the error.
;      destroys AF,BC,DE,HL
;
; ONE SECTOR AN OPERATION, not a multi-sector READ DATA with EOT.
; Partly because the emulator does not implement the EOT form and
; asserts on it, so a driver written that way could not be tested at
; all - but mostly because it costs nothing here: AMSDOS formats with a
; 2:1 interleave (C1 C6 C2 C7 ...) precisely so that reading in ID
; order leaves a sector's worth of time between one read and the next,
; which is what the command overhead fits into. The seek is only paid
; when the track actually changes.
; ---------------------------------------------------------------------
DISC_READ:      call DISC_MOTOR_ON
                call FDC_RECAL

.sector:        ld   a,(DISC_COUNT)
                or   a
                scf                         ; nothing left: success
                ret  z

                ld   a,(DISC_TRACK)         ; seek only when the head has
                ld   hl,DISC_HEAD           ; to move
                cp   (hl)
                jr   z,.on_track
                ld   (hl),a
                call FDC_SEEK
.on_track:
                call FDC_READ_ONE
                ret  nc

                ld   hl,(DISC_PTR)          ; on to the next sector
                ld   de,DISC_SECT_SIZE
                add  hl,de
                ld   (DISC_PTR),hl
                ld   hl,DISC_COUNT
                dec  (hl)
                ld   hl,DISC_SECT
                inc  (hl)
                ld   a,(hl)
                cp   DISC_SECT_LAST + 1
                jr   c,.sector              ; still inside the track
                ld   (hl),DISC_SECT_FIRST   ; over the end: the next one
                ld   hl,DISC_TRACK
                inc  (hl)
                jr   .sector

; ---------------------------------------------------------------------
; FDC_READ_ONE - sector (DISC_SECT) of (DISC_TRACK) into (DISC_PTR).
;                                destroys AF,BC,HL
; ---------------------------------------------------------------------
FDC_READ_ONE:   ld   a,&46                  ; READ DATA, MFM
                call FDC_SEND
                xor  a
                call FDC_SEND               ; drive 0, head 0
                ld   a,(DISC_TRACK)
                call FDC_SEND               ; C
                xor  a
                call FDC_SEND               ; H
                ld   a,(DISC_SECT)
                call FDC_SEND               ; R
                ld   a,2
                call FDC_SEND               ; N - 512 bytes
                ld   a,(DISC_SECT)
                call FDC_SEND               ; EOT - the same one
                ld   a,&2A
                call FDC_SEND               ; GPL
                ld   a,&FF
                call FDC_SEND               ; DTL, unused at N = 2

                ld   hl,(DISC_PTR)
                ld   bc,FDC_STATUS
.exec:          in   a,(c)
                and  &20                    ; EXM: still transferring?
                jr   z,.result
                in   a,(c)
                add  a,a                    ; RQM into carry
                jr   nc,.exec
                inc  c
                in   a,(c)
                ld   (hl),a
                inc  hl
                dec  c
                jr   .exec

.result:        ld   hl,DISC_ST
                ld   b,7
.res:           push bc
                call FDC_RECV
                ld   (hl),a
                inc  hl
                pop  bc
                djnz .res

                ld   a,(DISC_ST)            ; ST0 bits 6-7: 00 = normal
                and  &C0
                ret  nz                     ; ... carry clear, so a failure
                scf
                ret

; ---------------------------------------------------------------------
; FDC_RECAL / FDC_SEEK - the head, and waiting for it to arrive.
;
; The 765 finishes a seek asynchronously and then holds an interrupt
; until SENSE INTERRUPT STATUS is read, so every seek has to be
; collected or the next command sees a busy controller.
;                                destroys AF,BC
; ---------------------------------------------------------------------
FDC_RECAL:      xor  a
                ld   (DISC_HEAD),a          ; the head will be on track 0
                ld   a,&07                  ; RECALIBRATE
                call FDC_SEND
                xor  a
                call FDC_SEND
                jr   FDC_SENSE

FDC_SEEK:       ld   a,&0F
                call FDC_SEND
                xor  a
                call FDC_SEND               ; drive 0, head 0
                ld   a,(DISC_TRACK)
                call FDC_SEND
                ; falls into FDC_SENSE

FDC_SENSE:      ld   bc,FDC_STATUS
.busy:          in   a,(c)
                and  &10                    ; CB - still seeking
                jr   nz,.busy
                ld   a,&08                  ; SENSE INTERRUPT STATUS
                call FDC_SEND
                call FDC_RECV               ; ST0
                jp   FDC_RECV               ; PCN

; ---------------------------------------------------------------------
; FDC_SEND - A to the data register, once the controller wants it.
; FDC_RECV - a byte from it, once it has one.    destroys AF,BC
; ---------------------------------------------------------------------
FDC_SEND:       push af
                ld   bc,FDC_STATUS
.wait:          in   a,(c)
                add  a,a                    ; RQM -> carry
                jr   nc,.wait
                add  a,a                    ; DIO must be 0: CPU to FDC
                jr   c,.wait
                pop  af
                inc  c
                out  (c),a
                ret

FDC_RECV:       ld   bc,FDC_STATUS
.wait:          in   a,(c)
                add  a,a
                jr   nc,.wait
                inc  c
                in   a,(c)
                ret

DISC_MOTOR_STATE: db 0
DISC_HEAD:      db &FF          ; the track the head is on, &FF = unknown
DISC_TRACK:     db 0
DISC_SECT:      db 0
DISC_COUNT:     db 0
DISC_RUN:       db 0
DISC_PTR:       dw 0
DISC_ST:        ds 7
