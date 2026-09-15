; =====================================================================
; collide.asm - tile collision                             (MODULE 5)
;
; The tilemap is the terrain. A probe converts a world position to a map
; cell, reads the tile index, and looks its attributes up in TILE_ATTR.
;
;   map_col = (BX >> 3) AND 63     1 byte = 2 pixels, a tile is 8 bytes
;   map_row = (Y  >> 4) AND 15     a tile is 16 pixels tall
;   cell    = MAP_ADDR + map_row * 64 + map_col
;
; Both map dimensions are powers of two, so a probe cannot fail a bounds
; check - it wraps, which is the topology the scroll engine already has.
; A real level puts solid tiles at its edges rather than relying on a
; clamp.
;
; MAP_ADDR + row*64 being linear in the row is what lets a probe step one
; tile DOWN with +64 and one tile RIGHT with +1 instead of converting a
; coordinate again. That is the whole reason MAP_CELL returns an address
; rather than an attribute.
;
; COORDINATES. X is a world BYTE column (1 unit = 2 Mode 0 pixels),
; because the blitter is byte-granular and map_col is then a shift. Y is
; a world PIXEL row in a single byte, which wraps with the 256-pixel-tall
; map and makes every comparison 8-bit.
;
; PAGING. MAP_ADDR is inside the &4000-&7FFF window, so every probe needs
; bank C4 paged in BY THE CALLER. The pair costs 116 T against a ~220 T
; probe, so callers batch: PLAYER_UPDATE pages once around both axes.
; =====================================================================

TA_SOLID        equ %10000000   ; blocks from every direction
TA_PLATFORM     equ %01000000   ; one-way - blocks a descent only
TA_HAZARD       equ %00100000   ; damages on contact
TA_TRIGGER      equ %00010000   ; reserved for Module 5's entities
TA_CLIMB        equ %00001000   ; RESERVED, level 3 - defined, never read
TA_WATER        equ %00000100   ; RESERVED, level 4 - defined, never read
TA_SINK         equ %00000010   ; RESERVED, level 5 - defined, never read
TA_BLOCK        equ TA_SOLID + TA_PLATFORM

KARA_BOX_W      equ 4           ; bytes - 8 pixels, narrower than her sprite
KARA_BOX_H      equ 44          ; lines - her 48 less a little headroom

; The level-3/4/5 bits exist so the attribute format is final and no
; asset has to be re-exported later. No Module 5 code reads them.
                align 256
TILE_ATTR:      db 0                        ;  0 SKY
                db 0                        ;  1 STAR
                db TA_SOLID                 ;  2 ROOF
                db TA_SOLID                 ;  3 BRICK
                db TA_SOLID                 ;  4 WINDOW
                db TA_PLATFORM              ;  5 LEDGE - one-way
                db TA_SOLID                 ;  6 PIPE  - TA_CLIMB in level 3
                db TA_SOLID                 ;  7 RUBBLE
                ds 248, 0                   ;  8-255 unused for now

; ---------------------------------------------------------------------
; MAP_CELL - address in bank C4 of the cell covering a world position.
;
; row*64 falls out of the base address: load L with Y AND &F0 (= row*16)
; and H with MAP_ADDR/1024, then ADD HL,HL twice. &1200 -> &2400 ->
; &4800, so the map base and the row scaling come from the same two
; adds. The column then fits in L without carrying, because
; (row AND 3)*64 + 63 <= 255.
;
; IN : HL = world byte column 0-511, A = world pixel row 0-255
; OUT: HL = map cell address. Bank C4 must already be paged in.
;      destroys AF,DE,HL.  *** BC IS PRESERVED *** - BOX_SOLID_H keeps
;      its row counter in B and BOX_SOLID_V its mask.
; ---------------------------------------------------------------------
MAP_CELL:       and  &F0                    ; Y AND &F0 = map row * 16
                ld   e,a
                ld   a,l
                srl  h
                rra
                srl  h
                rra
                srl  h
                rra                         ; A = BX >> 3
                and  &3F                    ; map column 0-63
                ld   d,a
                ld   l,e
                ld   h,MAP_ADDR / 1024      ; exact multiple - safe to divide
                add  hl,hl
                add  hl,hl
                ld   a,d
                add  a,l                    ; cannot carry
                ld   l,a
                ret

; ---------------------------------------------------------------------
; ATTR_OF - tile index in A -> attribute byte in A.
;      destroys AF,DE.  *** HL IS PRESERVED *** - which is what lets the
;      box probes keep walking the map with it.
; ---------------------------------------------------------------------
ATTR_OF:        ld   e,a
                ld   d,TILE_ATTR >> 8
                ld   a,(de)
                ret

; MAP_ATTR - the isolated form: world position -> attribute byte.
; IN : HL = world byte column, A = world pixel row   OUT: A = attributes
;      destroys AF,DE,HL.  BC preserved.
MAP_ATTR:       call MAP_CELL
                ld   a,(hl)
                jp   ATTR_OF

; MAP_ROW_DOWN - one map row down, wrapping inside the 1 KB map.
;      destroys AF.  HL stepped.
MAP_ROW_DOWN:   ld   a,l
                add  a,MAP_W
                ld   l,a
                ret  nc
                inc  h
                ld   a,h
                and  3
                or   MAP_ADDR >> 8
                ld   h,a
                ret

; MAP_COL_RIGHT - one map column right, wrapping inside the 64-column
; row: bits 0-5 of the low byte are the column, bits 6-7 belong to the
; row, so the wrap is a mask and not a compare.
;      destroys AF,DE.  HL stepped.
MAP_COL_RIGHT:  ld   a,l
                inc  a
                and  &3F
                ld   e,a
                ld   a,l
                and  &C0
                or   e
                ld   l,a
                ret

; ---------------------------------------------------------------------
; BOX_SOLID_H - would Kara's box hit a wall if its LEADING edge sat at
; world byte column HL?
;
; Only the leading edge is probed. The trailing edge is somewhere she is
; already standing, so it cannot have become solid - which is what makes
; this 3 or 4 samples rather than 8.
;
; The probe count is COMPUTED, not fixed. A 44-line box crosses three
; tile rows when its top is tile-aligned and four when it is not.
; Probing a fixed four reads a tile BELOW her feet, and she then refuses
; to walk toward a wall a whole tile beneath her - invisible in a static
; test, obvious on a rooftop.
;
; IN : HL = leading edge, A = world pixel row of the box top
; OUT: Z = clear, NZ = blocked. (PROBE_ACC) = OR of every attribute seen,
;      so a hazard falls out of the reads the wall test already did.
;      destroys AF,BC,DE,HL.  Bank C4 must be paged in.
; ---------------------------------------------------------------------
BOX_SOLID_H:    push af
                call MAP_CELL               ; the column, resolved once
                pop  af
                and  15                     ; how far into its tile is the top?
                add  a,KARA_BOX_H - 1
                rrca
                rrca
                rrca
                rrca
                and  15
                inc  a                      ; 3 rows aligned, 4 otherwise
                ld   b,a
                ld   c,0
.row:           ld   a,(hl)
                call ATTR_OF
                or   c
                ld   c,a
                call MAP_ROW_DOWN
                djnz .row
                ld   a,c
                ld   (PROBE_ACC),a
                and  TA_SOLID               ; a platform never blocks sideways
                ret

; ---------------------------------------------------------------------
; BOX_SOLID_V - is the horizontal line at world pixel row A, spanning the
; box's KARA_BOX_W bytes from world byte column HL, blocked?
;
; The two samples are 3 byte columns apart inside an 8-byte-wide tile, so
; 5 starting positions in 8 put both in the same cell and the second
; probe is skipped outright.
;
; IN : HL = box left edge, A = world pixel row,
;      B  = attribute mask (TA_SOLID rising, TA_BLOCK falling)
; OUT: Z = clear, NZ = blocked. (PROBE_ACC) = merged attributes.
;      destroys AF,BC,DE,HL.  Bank C4 must be paged in.
; ---------------------------------------------------------------------
BOX_SOLID_V:    ld   c,a                    ; C = the scanline, until MAP_CELL
                ld   a,l                    ;     needs A
                and  7
                add  a,KARA_BOX_W - 1
                cp   8
                jr   c,.single
                set  0,b                    ; the masks are &80 or &C0, so bit 0
                                            ; is always free to carry this flag
.single:        ld   a,c
                push hl
                call MAP_CELL
                ld   a,(hl)
                call ATTR_OF
                ld   c,a
                bit  0,b
                jr   z,.done
                call MAP_COL_RIGHT
                ld   a,(hl)
                call ATTR_OF
                or   c
                ld   c,a
.done:          pop  hl
                res  0,b
                ld   a,c
                ld   (PROBE_ACC),a
                and  b
                ret

PROBE_ACC:      db 0
