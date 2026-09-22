; =====================================================================
; mapshape.asm - THE MAP'S SHAPE IS THE LEVEL'S, NOT THE BUILD'S
;
; MAP_W was 128 and MAP_H 16 because the City is a rooftop: one screen
; tall and six and a half wide. Level 3 is a cave and level 4 is the
; sea, and both of those are the same map stood on its end - so the
; shape has to come out of `level_<n>.lvl` and not out of an `equ`.
;
; W * H IS ALWAYS 2,048, and that is a memory-map fact rather than a
; choice: the map is 2,048 bytes of base RAM at MAP_ADDR and the entity
; table is at MAP_ADDR + 2048 (8.6). So a shape is one number - the
; width - and the height follows:
;
;      128 x 16   the City: 6.4 screens across, one down
;       64 x 32   2.1 screens across, 2.7 down
;       32 x 64   1.6 across, 5.3 down - the VERTICAL one
;       16 x 128  refused: 128 pixels of map against a 160-pixel display
;
; HOW IT IS DONE IS SELF-MODIFYING CODE, AND THE REASON IS THE FRAME.
; Every mask here sits in an inner loop - MAP_CELL is called ten to
; fifteen times a frame by the box probes and TILE_SRC once per cell of
; a repaint - and the run-and-fire path has about 800 T of slack (9).
; Reading a shape byte out of memory at each of them is 7 T against an
; immediate's 0, on thirty-six sites. Patched once at MAP_INSTALL they cost
; nothing at all, which is what lets the shape be a level's property
; without the City paying for it.
;
; AND THE TWO RUNS COST NOTHING EITHER, WHICH IS THE PART WORTH HAVING
; WRITTEN DOWN. Two places scale a row by the map's width with a run of
; shifts whose LENGTH is the shape - MAP_CELL's `sla e : rl d` and the
; tilemap's `rrca`. A run that is shorter than its slot is padded with
; NOPs, and a NOP is one byte and 4 T exactly like the `rrca` it
; replaces, and two NOPs are two bytes and 8 T exactly like the
; `sla e : rl d` pair. So the slot is a fixed length and a fixed cost
; whatever shape is patched into it, and there is no branch.
; =====================================================================

SHAPE_MIN_LOG   equ 5                       ; 32 wide
SHAPE_MAX_LOG   equ 7                       ; 128 wide
SHAPE_N         equ SHAPE_MAX_LOG - SHAPE_MIN_LOG + 1

; The row, and every field of it is a thing some instruction wants as
; an IMMEDIATE. Offsets are used by name below and by tools/ in the
; tests, so they are symbols and not counted by hand.
SH_COL_MASK     equ 0                       ; W - 1
SH_COL_COMP     equ 1                       ; the bits the ROW owns in the
                                            ; map pointer's low byte
SH_ROW_MASK     equ 2                       ; H - 1
SH_ROW_HI       equ 3                       ; ... its top nibble, which is
                                            ; all MAP_CELL sees of it
SH_STEP_W       equ 4                       ; one map row, for the steps
SH_ROT          equ 5                       ; rrca's that split a map row
SH_SCALE        equ 6                       ; sla/rl pairs that scale one
SH_PAGE_MASK    equ 7                       ; rows in a page, less one
SH_VIEW_X       equ 8                       ; the view's last character
SH_KARA_X       equ 9                       ; her last byte column, 16-bit
SH_V_CR_MAX     equ 11                      ; the view's last character row
SHAPE_STRIDE    equ 12

; W = 32: 1.6 screens across and 5.3 down - the vertical one
SHAPE_TABLE:    db  31, &E0, 63, 3, 32, 3, 1, 7
                db  32 * 2 - SCR_CHARS
                dw  32 * 4 - KARA_W_BYTES + KARA_ART_X
                db  (64 * 16 - SCR_CHAR_ROWS * 8) / 8
; W = 64
                db  63, &C0, 31, 1, 64, 2, 2, 3
                db  64 * 2 - SCR_CHARS
                dw  64 * 4 - KARA_W_BYTES + KARA_ART_X
                db  (32 * 16 - SCR_CHAR_ROWS * 8) / 8
; W = 128: the City, and what every immediate in the source already says
SHAPE_CITY:     db  127, &80, 15, 0, 128, 1, 3, 1
                db  128 * 2 - SCR_CHARS
                dw  128 * 4 - KARA_W_BYTES + KARA_ART_X
                db  (16 * 16 - SCR_CHAR_ROWS * 8) / 8

SHAPE_NOW:      ds  SHAPE_STRIDE            ; the shape in force

                ; ... AND THE TABLE HAS EXACTLY THE ROWS MAP_SHAPE_SET
                ; INDEXES. It does `A - SHAPE_MIN_LOG` times SHAPE_STRIDE
                ; and reads twelve bytes; a row added without a
                ; SHAPE_MAX_LOG to go with it, or a field added to one
                ; row and not the others, is a shape read out of the
                ; next one's bytes. RASM counts it here instead.
                assert SHAPE_NOW - SHAPE_TABLE == SHAPE_N * SHAPE_STRIDE

; ---------------------------------------------------------------------
; MAP_SHAPE_SET - A = log2 of the map's width. Carry set = refused.
;
; It is called from MAP_INSTALL, before the map is copied and before
; anything reads it, and it is called again on every level start -
; including a restart, which is why tools/test_flow.py's byte-for-byte
; sweep of engine RAM covers these bytes like any others.
;                                Clobbers AF, BC, DE, HL
; ---------------------------------------------------------------------
MAP_SHAPE_SET:  cp   SHAPE_MIN_LOG
                jr   c,.no                  ; too narrow to fill the screen
                cp   SHAPE_MAX_LOG + 1
                jr   c,.take
.no:            scf
                ret
.take:          sub  SHAPE_MIN_LOG
                ld   e,a                    ; * SHAPE_STRIDE = 12
                add  a,a
                add  a,e
                add  a,a
                add  a,a
                ld   e,a
                ld   d,0
                ld   hl,SHAPE_TABLE
                add  hl,de
                ld   de,SHAPE_NOW
                ld   bc,SHAPE_STRIDE
                ldir

                ; ---- the plain immediates --------------------------
                ld   a,(SHAPE_NOW + SH_COL_MASK)
                ld   hl,PT_COL_MASK
                call SHAPE_POKE
                ld   a,(SHAPE_NOW + SH_COL_COMP)
                ld   hl,PT_COL_COMP
                call SHAPE_POKE
                ld   a,(SHAPE_NOW + SH_ROW_MASK)
                ld   hl,PT_ROW_MASK
                call SHAPE_POKE
                ld   a,(SHAPE_NOW + SH_ROW_HI)
                ld   hl,PT_ROW_HI
                call SHAPE_POKE
                ld   a,(SHAPE_NOW + SH_STEP_W)
                ld   hl,PT_STEP_W
                call SHAPE_POKE
                ld   a,(SHAPE_NOW + SH_PAGE_MASK)
                ld   hl,PT_PAGE_MASK
                call SHAPE_POKE

                ; ---- and the two the player's bounds want, one of
                ; ---- which is wanted one higher as well
                ld   a,(SHAPE_NOW + SH_VIEW_X)
                ld   hl,PT_VIEW_X
                call SHAPE_POKE
                ld   a,(SHAPE_NOW + SH_VIEW_X)
                inc  a
                ld   hl,PT_VIEW_X1
                call SHAPE_POKE
                ld   a,(SHAPE_NOW + SH_V_CR_MAX)
                ld   hl,PT_V_CR_MAX
                call SHAPE_POKE
                ld   a,(SHAPE_NOW + SH_V_CR_MAX)
                inc  a
                ld   hl,PT_V_CR_MAX1
                call SHAPE_POKE
                ld   hl,(SHAPE_NOW + SH_KARA_X)
                ld   (PM_KARA_XMAX),hl

                ; ---- the runs --------------------------------------
                ld   a,(SHAPE_NOW + SH_ROT)
                ld   d,&0F                  ; rrca
                ld   hl,PT_ROT
                call SHAPE_RUNS
                ld   a,(SHAPE_NOW + SH_ROT)
                ld   d,&87                  ; add a,a
                ld   hl,PT_ROT_ADD
                call SHAPE_RUNS
                ld   a,(SHAPE_NOW + SH_ROT)
                ld   d,&07                  ; rlca
                ld   hl,PT_ROT_RL
                call SHAPE_RUNS
                ld   a,(SHAPE_NOW + SH_SCALE)
                call MAP_SCALE_SET
                or   a                      ; carry clear: the shape took
                ret

; ---------------------------------------------------------------------
; SHAPE_POKE - write A at every address in the 0-terminated list at HL.
;                                Clobbers AF, BC, DE, HL
; ---------------------------------------------------------------------
SHAPE_POKE:     ld   c,a
.loop:          ld   e,(hl)
                inc  hl
                ld   d,(hl)
                inc  hl
                ld   a,d
                or   e
                ret  z
                ld   a,c
                ld   (de),a
                jr   .loop

; ---------------------------------------------------------------------
; SHAPE_RUNS - fill every four-byte run in the 0-terminated list at HL
; with A copies of the opcode in D, NOPs after.
;
; THE LIVE COPIES GO AT THE END OF THE SLOT and the NOPs in front, which
; is arbitrary and has to be SAID: the opcodes here are all rotations of
; the accumulator, so n of them in a row is n of them in a row wherever
; in the slot they sit.
;                                Clobbers AF, BC, DE, HL
; ---------------------------------------------------------------------
SHAPE_RUNS:     ld   (.count + 1),a
                ld   a,d
                ld   (.op + 1),a
.list:          ld   e,(hl)
                inc  hl
                ld   d,(hl)
                inc  hl
                ld   a,d
                or   e
                ret  z
                push hl                     ; ... the list
                ex   de,hl                  ; HL = the run to write
                ld   b,4
.slot:          ld   a,b
.count:         cp   0                      ; patched: how many are live
                jr   z,.put
                jr   c,.put
                xor  a                      ; a NOP, and it costs what the
                jr   .store                 ; rotation it stands in for does
.put:
.op:            ld   a,0                    ; patched: the opcode
.store:         ld   (hl),a
                inc  hl
                djnz .slot
                pop  hl
                jr   .list

; ---------------------------------------------------------------------
; MAP_SCALE_SET - A = how many `sla e : rl d` pairs MAP_CELL's row scale
; wants, of the three it has room for. The rest are NOPs, and a pair of
; NOPs is 8 T exactly like the pair it replaces.
;                                Clobbers AF, BC, HL
; ---------------------------------------------------------------------
MAP_SCALE_SET:  ld   c,a
                ld   hl,PM_SCALE
                ld   b,3
.slot:          ld   a,b
                cp   c
                jr   z,.live
                jr   c,.live
                xor  a
                ld   (hl),a
                inc  hl
                ld   (hl),a
                inc  hl
                ld   (hl),a
                inc  hl
                ld   (hl),a
                inc  hl
                djnz .slot
                ret
.live:          ld   (hl),&CB
                inc  hl
                ld   (hl),&23               ; sla e
                inc  hl
                ld   (hl),&CB
                inc  hl
                ld   (hl),&12               ; rl  d
                inc  hl
                djnz .slot
                ret

; ---------------------------------------------------------------------
; AND THESE ARE THE SITES. Each list is 0-terminated and each entry is
; the address of an IMMEDIATE, because that is what a PM_ symbol IS:
; `equ $ - 1` after the instruction, not a label on it. A LABEL WOULD
; NOT DO, and the reason is RASM's: a `.dotted` local belongs to the
; last GLOBAL label above it, so a global dropped into the middle of a
; routine takes every local after it into a scope of its own and the
; routine's own `jr .step_r` stops resolving. An `equ` is not a label
; and breaks nothing. In the run lists the symbol is the first byte of
; the run itself.
;
; A LIST IS THE ONLY RECORD THAT A SITE EXISTS, so a mask added to the
; engine and not added here is a mask that keeps the City's shape in a
; cave: nothing fails, nothing looks wrong, and one probe in the engine
; reads the wrong cell. tools/test_shape.py walks the built image for
; `and` immediates that hold a shape's value and are in no list.
; ---------------------------------------------------------------------
PT_COL_MASK:    dw  PM_TS_COLM, PM_DC_COLM, PM_DR_COLM
                dw  PM_RN_COLM, PM_MC_COLM, PM_CR_COLM
                dw  PM_EC_COLM, PM_RP_COLM
                dw  0

PT_COL_COMP:    dw  PM_TS_COMP, PM_DC_COMP, PM_DR_COMP
                dw  PM_RN_COMP, PM_EC_COMP
                dw  0

PT_ROW_MASK:    dw  PM_TS_ROWM, PM_DC_ROWM, PM_DR_ROWM
                dw  PM_EC_ROWM
                dw  0

PT_ROW_HI:      dw  PM_MC_ROWHI
                dw  0

PT_STEP_W:      dw  PM_DC_STEP, PM_MD_STEP
                dw  0

PT_PAGE_MASK:   dw  PM_RP_PAGE
                dw  0

PT_VIEW_X:      dw  PM_PX_VIEW, PM_CD_VIEW, PM_VT_VIEW
                dw  0
PT_VIEW_X1:     dw  PM_VT_VIEW1
                dw  0

PT_V_CR_MAX:    dw  PM_CV_VCR, PM_VT_VCR
                dw  0
PT_V_CR_MAX1:   dw  PM_VT_VCR1
                dw  0

PT_ROT:         dw  PM_TS_ROT, PM_DC_ROT, PM_DR_ROT, PM_EC_ROT
                dw  0
PT_ROT_ADD:     dw  PM_RP_ADD
                dw  0
PT_ROT_RL:      dw  PM_RP_ROT
                dw  0
