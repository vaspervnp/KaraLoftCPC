; =====================================================================
; boot.asm - GAME.BIN: what AMSDOS loads at &4000 and BASIC CALLs.
;
; THE ENGINE IS NOT IN THIS FILE AS IT RUNS. src/main.asm assembles
; four images - the core for &0040, the HIGH image for &AA00, the
; SOUND image for &9400 and the TOP image for &BB00 - into
; build/engine.bin, and tools/make_boot.py
; packs each of them with ZX0 and assembles this around them. So the
; whole of the boot is: the ROMs off, and four streams unpacked
; straight to where they run (CLAUDE.md 4).
;
; IT IS PACKED BECAUSE THE DISC RAN OUT OF FILE BLOCKS, NOT BECAUSE OF
; LOAD TIME. The sound image took GAME.BIN from 18 blocks to 21, and
; AMSDOS's allocation past the raw data area's first block at track 9
; (tools/dskdata.py). Packed it is 13 - 20,842 bytes to 12,778 - which
; is enough to put the data back at TRACK 8, where it was before the
; label screen went on the disc, and to give the level streams the nine
; sectors that pulls them back inside a standard 40-track disc.
;
; THE ORDER MATTERS ONCE. The lower ROM must go before anything is
; unpacked to &0040: writes always reach RAM, but ZX0 READS back what
; it has written - every match is a copy out of its own output - and
; with the ROM in, a read below &4000 is the firmware's bytes. The file
; itself ends below &9400, so none of the four streams is overwritten
; while it is being read; the assert at the end says so.
; =====================================================================

                include "boot.inc"          ; build/, by tools/make_boot.py

                org  BOOT_ADDR

BOOT:           di
                ld   sp,STACK_TOP           ; below VRAM, above everything else
                ld   bc,GA_PORT * 256 + RMR_MODE0
                out  (c),c                  ; Mode 0, both ROMs off
                ld   bc,GA_PORT * 256 + RAM_CFG_BASE
                out  (c),c                  ; a known window before writing
                ld   hl,PK_CORE
                ld   de,CORE_ADDR
                call UNZX0
                ld   hl,PK_HIGH
                ld   de,HIGH_ADDR
                call UNZX0
                ld   hl,PK_SOUND
                ld   de,SOUND_ADDR
                call UNZX0
                ld   hl,PK_TOP
                ld   de,TOP_ADDR
                call UNZX0
                jp   CORE_ENTRY             ; no way back to BASIC from here

UNZX0:          include "vendor/dzx0_fast.asm"
                DecompressZX0               ; ... which ends in RET

PK_CORE:        incbin "boot_core.zx0"
PK_HIGH:        incbin "boot_high.zx0"
PK_SOUND:       incbin "boot_sound.zx0"
PK_TOP:         incbin "boot_top.zx0"
BOOT_FILE_END:
                assert BOOT_FILE_END <= SOUND_ADDR
                assert BOOT_FILE_END <= HIGH_ADDR
                assert CORE_ADDR + CORE_SIZE <= BOOT_ADDR
