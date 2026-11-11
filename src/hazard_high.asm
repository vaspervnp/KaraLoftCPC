; =====================================================================
; hazard_high.asm - the half of src/hazard.asm that runs ONCE: putting a
; level's traps on their phases, and lighting an altar. Assembled into
; the HIGH image (main.asm), because the core had 676 bytes left and the
; traps took 827; what the frame calls every time stays in the core.
; CLAUDE.md 8.17.
; =====================================================================

; ---------------------------------------------------------------------
; HAZARD_SPAWN - the level's traps, out of its entity table. Called by
; MAP_DERIVE, so a restart puts every trap back on its own phase: the
; map was copied out of the pristine image a moment ago and holds cel 0.
;                                destroys AF,BC,DE,HL,IX
; ---------------------------------------------------------------------
HAZARD_SPAWN:   ld   hl,HZ_TABLE
                ld   de,HZ_TABLE + 1
                ld   bc,HZ_MAX * HZ_STRIDE - 1
                ld   (hl),0
                ldir
                xor  a
                ld   (HZ_COUNT),a
                ld   (HZ_PEND_N),a
                ld   a,(ENT_COUNT)
                or   a
                ret  z
                ld   b,a
                ld   ix,ENT_TABLE
.rec:           ld   a,(ix + ENT_KIND)
                cp   EK_HAZARD
                jr   nz,.next
                ld   a,(ix + ENT_FLAGS)
                and  EF_ACTIVE
                jr   z,.next
                ld   a,(ix + ENT_P0)
                cp   HZ_KINDS
                jr   nc,.next               ; a hazard this engine does not
                                            ; know: the editor refuses it
                ld   a,(HZ_COUNT)
                cp   HZ_MAX
                jr   nc,.next               ; ... and the ninth
                push bc
                call HZ_SPAWN_ONE
                pop  bc
.next:          ld   de,ENT_STRIDE
                add  ix,de
                djnz .rec
                ret

; IX = the record, A = its slot.
HZ_SPAWN_ONE:   ld   c,a
                inc  a
                ld   (HZ_COUNT),a
                ld   a,c
                add  a,a
                add  a,a
                add  a,a                    ; * HZ_STRIDE
                add  a,HZ_TABLE AND 255
                ld   l,a
                ld   h,HZ_TABLE >> 8
                push hl
                pop  iy
                push ix
                pop  hl
                ld   (iy + HZ_REC),l
                ld   (iy + HZ_REC + 1),h
                call ENT_CELL_OF            ; HL = its map byte
                ld   (iy + HZ_CELL),l
                ld   (iy + HZ_CELL + 1),h
                ld   a,(hl)
                ld   (iy + HZ_BASE),a       ; cel 0, out of the pristine map
                ld   a,(ix + ENT_P1)
                and  HZ_CELS - 1            ; the cel it starts on
                ld   c,a
                add  a,(iy + HZ_BASE)
                ld   (hl),a
                ld   b,0
                ld   hl,HZ_DUR
                add  hl,bc
                ld   a,(hl)
                add  a,a
                add  a,a
                or   c
                ld   (iy + HZ_TC),a
                ld   l,(ix + ENT_X)         ; x, pixels -> characters
                ld   h,(ix + ENT_X + 1)
                srl  h
                rr   l
                srl  h
                rr   l
                ld   (iy + HZ_WC),l
                ld   l,(ix + ENT_Y)         ; the BASE of a one-tile box,
                ld   h,(ix + ENT_Y + 1)     ; so its top is 16 lines up
                ld   de,0 - PICKUP_H        ; NOT -PICKUP_H: CLAUDE.md 10
                add  hl,de
                srl  h
                rr   l
                srl  h
                rr   l
                srl  h
                rr   l
                ld   (iy + HZ_WR),l
                ret

; ---------------------------------------------------------------------
; HZ_SATISFIED - HL = a receptacle that has just been given everything
; it wanted. Two things follow from it, and both are data:
;
;   ITS LINKS. Every `Disables` link whose source is this record marks
;   its target EF_TAKEN, and HAZARD_TICK puts that trap down and keeps
;   it there. The links are read out of the PRISTINE level image, which
;   nothing in play writes - so they cost no RAM and a restart cannot
;   find them half-spent.
;
;   ITS PICTURE. Every cell of the 3 x 2 around its own - its own and
;   the one either side, on its row and the row above - whose tile
;   carries TA_ADVANCE moves on to the next tile: the altar's empty
;   pieces carry it and its lit ones are the next index. A cell that is
;   not an altar's is left alone, so an editor's level with a receptacle
;   and no baked altar is not scribbled on (CLAUDE.md 8.17).
;                                destroys AF,BC,DE,HL,IX
; ---------------------------------------------------------------------
HZ_SATISFIED:   push hl
                pop  ix
                ; ---- which record this is ----------------------------
                ld   de,ENT_TABLE
                or   a
                sbc  hl,de
                ld   a,l                    ; / ENT_STRIDE: 23 * 8 = 184,
                rrca                        ; so the low byte is all of it
                rrca
                rrca
                and  &1F
                ld   (HZ_SRC),a
                ; ---- its links ---------------------------------------
                ld   a,(LEVEL_LVL + LVL_LINKS)
                or   a
                jr   z,.picture
                ld   b,a
                ld   hl,(LEVEL_LVL + LVL_OFF_LINK)
                ld   de,LEVEL_LVL
                add  hl,de
.link:          ld   a,(hl)
                cp   LK_DISABLES
                jr   nz,.next
                inc  hl
                ld   a,(HZ_SRC)
                cp   (hl)
                dec  hl
                jr   nz,.next
                push hl
                inc  hl
                inc  hl
                ld   a,(hl)                 ; the target
                ld   hl,ENT_COUNT
                cp   (hl)
                jr   nc,.bad                ; past the table: nothing
                add  a,a
                add  a,a
                add  a,a
                ld   l,a
                ld   h,0
                ld   de,ENT_TABLE + ENT_FLAGS
                add  hl,de
                set  1,(hl)                 ; EF_TAKEN: down, and staying
.bad:           pop  hl
.next:          inc  hl
                inc  hl
                inc  hl
                inc  hl
                djnz .link
                ; ---- its picture -------------------------------------
.picture:       push ix
                pop  hl
                call ENT_CELL_OF            ; HL = its own cell
                ld   (HZ_CELLP),hl
                ld   l,(ix + ENT_X)
                ld   h,(ix + ENT_X + 1)
                srl  h
                rr   l
                srl  h
                rr   l
                ld   a,l
                sub  TILE_CHAR_COLS         ; the column to its left
                ld   (HZ_WC0),a
                ld   l,(ix + ENT_Y)
                ld   h,(ix + ENT_Y + 1)
                ld   de,0 - PICKUP_H
                add  hl,de
                srl  h
                rr   l
                srl  h
                rr   l
                srl  h
                rr   l
                ld   a,l
                ld   (HZ_WR0),a             ; its own row
                ld   hl,(HZ_CELLP)
                dec  hl                     ; the cell to its left
                call HZ_ADVANCE_ROW
                ld   a,(HZ_WR0)
                sub  2                      ; a tile is two character rows
                ld   (HZ_WR0),a
                ld   hl,(HZ_CELLP)
                ld   de,(LEVEL_LVL + LVL_W) ; the map's own width: the row
                or   a                      ; above, in any of the shapes
                sbc  hl,de
                dec  hl
                ; fall through for the row above

; HL = the leftmost of three cells, (HZ_WC0)/(HZ_WR0) its world
; character column and row.
HZ_ADVANCE_ROW: ld   b,3
                ld   a,(HZ_WC0)
                ld   c,a
.cell:          push bc
                push hl
                ld   a,(hl)
                ld   e,a
                ld   d,TILE_ATTR >> 8
                ld   a,(de)
                and  TA_ADVANCE
                jr   z,.leave
                inc  (hl)                   ; on to its lit picture
                ld   a,(HZ_WR0)
                ld   b,a
                call HZ_PEND_ADD
.leave:         pop  hl
                pop  bc
                inc  hl
                ld   a,c
                add  a,TILE_CHAR_COLS
                ld   c,a
                djnz .cell
                ret


HZ_SRC:         db 0            ; HZ_SATISFIED's record index
HZ_CELLP:       dw 0            ; ... and its cell
