; =====================================================================
; collide.asm - tile collision                             (MODULE 5)
;
; The tilemap is the terrain. A probe converts a world position to a map
; cell, reads the tile index, and looks its attributes up in TILE_ATTR.
;
;   map_col = (BX >> 2) AND 127    1 byte = 2 pixels, a tile is 4 bytes
;   map_row = (Y  >> 4) AND 15     a tile is 16 pixels tall
;   cell    = MAP_ADDR + map_row * 128 + map_col
;
; Both map dimensions are powers of two, so a probe cannot fail a bounds
; check - it wraps, which is the topology the scroll engine already has.
; A real level puts solid tiles at its edges rather than relying on a
; clamp.
;
; MAP_ADDR + row*128 being linear in the row is what lets a probe step
; one tile DOWN with +128 and one tile RIGHT with +1 instead of converting a
; coordinate again. That is the whole reason MAP_CELL returns an address
; rather than an attribute.
;
; COORDINATES. X is a world BYTE column (1 unit = 2 Mode 0 pixels),
; because the blitter is byte-granular and map_col is then a shift. Y is
; a world PIXEL row in a single byte, which wraps with the 256-pixel-tall
; map and makes every comparison 8-bit.
;
; NO PAGING. The map used to sit in bank C4 and every probe needed the
; caller to page it in - 116 T against a ~220 T probe, which is why
; PLAYER_UPDATE batched one pair of switches around both axes. It moved
; to base RAM when the 8x16 art filled C4 (see the note by MAP_ADDR in
; tilemap.asm), so a probe is now callable from anywhere, and the pair
; came out of PLAYER_UPDATE.
; =====================================================================

TA_SOLID        equ %10000000   ; blocks from every direction
TA_PLATFORM     equ %01000000   ; one-way - blocks a descent only
TA_HAZARD       equ %00100000   ; damages on contact
TA_TRIGGER      equ %00010000   ; reserved for Module 5's entities
TA_CLIMB        equ %00001000   ; a ladder: UP and DOWN move her along it
TA_WATER        equ %00000100   ; RESERVED, level 4 - defined, never read
TA_SINK         equ %00000010   ; RESERVED, level 5 - defined, never read
TA_BLOCK        equ TA_SOLID + TA_PLATFORM

KARA_BOX_W      equ 6           ; bytes - 12 pixels, narrower than her sprite
KARA_BOX_H      equ 60          ; lines - her 64 less a little headroom

; A tile is TILE_W_BYTES wide, so a box of KARA_BOX_W bytes spans at
; most this many of them. At 8 bytes a tile the answer was always 1 or
; 2 and BOX_SOLID_V could carry it in a spare mask bit; at 4 it is 1, 2
; or 3, so it is a counter now.
BOX_COLS_MAX    equ (KARA_BOX_W - 1) / TILE_W_BYTES + 2

; The level-3/4/5 bits exist so the attribute format is final and no
; asset has to be re-exported later. No Module 5 code reads them.
;
; ONE ENTRY PER TILE OF THE DRAWN SHEET, in the artist's frame order -
; the same order tools/make_city_map.py reads out of the manifest. A
; tile that is scenery gets nothing: a solid prop standing on the
; rooftop is a wall she cannot walk past, which stops the camera and
; makes every scrolling test vacuous without failing it.
;
; This is the CITY's table. Level 2 onward will each want their own, and
; the level format (8.3) carries the flags in tileflags_<level>.bin - at
; which point this becomes the loader's target rather than a literal.
                align 256
TILE_ATTR:      db 0                        ;  0 sky_stars
                db 0                        ;  1 void
                db 0                        ;  2 sky_mid
                db 0                        ;  3 sky_low
                db 0                        ;  4 far_tower      background
                db 0                        ;  5 far_block
                db 0                        ;  6 far_step
                db 0                        ;  7 far_fill
                ; THE BUILDING'S FACE IS BACKGROUND, NOT A WALL, and
                ; the artist's own street mockup is what says so: she
                ; walks the pavement in FRONT of a brick facade that runs
                ; floor to roof. Made solid, the foot of every ladder is
                ; a place she arrives inside a wall - her box is three
                ; tiles wide, the shaft is one, and BOX_SOLID_H then
                ; refuses every step she tries to take along the street.
                ; What holds her up is the roof at the top and the
                ; pavement at the bottom; the 128 rows of brick between
                ; them are scenery, and a roof edge she walks off is a
                ; fall to the street, which is what a roof edge is.
                db 0                        ;  8 brick
                db 0                        ;  9 brick_win_lit
                db 0                        ; 10 brick_win_dark
                db 0                        ; 11 brick_top
                db TA_SOLID                 ; 12 concrete
                db TA_SOLID                 ; 13 roof_l         the runway
                db TA_SOLID                 ; 14 roof_m
                db TA_SOLID                 ; 15 roof_r
                db 0                        ; 16 ac_unit        props: she
                db 0                        ; 17 chimney        walks through
                db 0                        ; 18 antenna        them
                db 0                        ; 19 tank_00
                db 0                        ; 20 tank_01
                db 0                        ; 21 tank_10
                db 0                        ; 22 tank_11
                db 0                        ; 23 tank_20
                db 0                        ; 24 tank_21
                ; A LADDER IS A FLOOR AS WELL AS A SHAFT. Its top tile
                ; sits in the roof's own row (tools/make_city_map.py), so
                ; she has to be able to stand on it before she can step
                ; onto it - TA_PLATFORM is what a one-way floor is, and
                ; it is what DOWN then takes her through.
                db TA_CLIMB + TA_PLATFORM   ; 25 ladder
                db TA_SOLID                 ; 26 sidewalk
                db TA_SOLID                 ; 27 curb
                db TA_SOLID                 ; 28 street
                db TA_SOLID                 ; 29 street_line
                db TA_SOLID                 ; 30 jamb_l         the garage
                db TA_SOLID                 ; 31 sign_p
                db TA_SOLID                 ; 32 jamb_r
                db TA_SOLID + TA_TRIGGER    ; 33 lock_red       needs the key
                db TA_SOLID                 ; 34 shutter
                db TA_SOLID                 ; 35 shutter_bottom
                db TA_TRIGGER               ; 36 lock_green     unlocked
                db 0                        ; 37 open_ramp      walk in
                db 0                        ; 38 lamp_top
                db 0                        ; 39 lamp_pole
                db TA_SOLID                 ; 40 crate
                ds 215, 0                   ; 41-255 unused for now

; ---------------------------------------------------------------------
; MAP_CELL - address in bank C4 of the cell covering a world position.
;
; row*128 falls out of the base address: load L with Y AND &F0
; (= row*16) and H with MAP_ADDR >> 11, then ADD HL,HL three times.
; &1400 -> &2800 -> &5000 -> &A000, so the map base and the row scaling
; come from the same three adds - which is why MAP_ADDR has to be a
; multiple of 2048 and main.asm asserts it. The column then fits in L
; without carrying, because (row AND 1)*128 + 127 = 255.
;
; IN : HL = world byte column 0-511, A = world pixel row 0-255
; OUT: HL = map cell address, in BASE RAM - no paging needed.
;      destroys AF,DE,HL.  *** BC IS PRESERVED *** - BOX_SOLID_H keeps
;      its row counter in B and BOX_SOLID_V its column counter.
; ---------------------------------------------------------------------
MAP_CELL:       and  &F0                    ; Y AND &F0 = map row * 16
                ld   e,a
                ld   a,l
                srl  h
                rra
                srl  h
                rra                         ; A = BX >> 2
                and  MAP_COL_MASK           ; map column 0-127
                ld   d,a
                ld   l,e
                ld   h,MAP_ADDR >> 11       ; >> 11, NOT / 2048: RASM's "/"
                add  hl,hl                  ; rounds to nearest
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
                and  7                      ; 2 KB of map = eight pages
                or   MAP_ADDR >> 8
                ld   h,a
                ret

; MAP_COL_RIGHT - one map column right, wrapping inside the 128-column
; row: bits 0-6 of the low byte are the column and bit 7 belongs to the
; row, so the wrap is a mask and not a compare. The branchless fold is
; the same one the span blitter uses on a screen address, and it is here
; because it needs NO SCRATCH REGISTER - BOX_SOLID_V has none to give.
;      destroys AF.  HL stepped.
MAP_COL_RIGHT:  ld   a,l
                inc  a
                xor  l                      ; the bits that changed ...
                and  MAP_COL_MASK           ; ... of which only the column's
                xor  l                      ; may, so put the row bit back
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
;      destroys AF,BC,DE,HL.
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
; THE PROBE COUNT IS COMPUTED, and it has to be: a tile is 4 bytes wide
; now and her box is 6, so it lands on two of them or three depending on
; where the left edge sits - never reliably one or two. It used to be
; exactly that, "one or two", carried in a spare bit of the attribute
; mask; at 8 bytes a tile that was true and at 4 it silently stops
; probing the last quarter of her width, which is a wall she walks into
; from the left and through from the right.
;
; IN : HL = box left edge, A = world pixel row,
;      B  = attribute mask (TA_SOLID rising, TA_BLOCK falling)
; OUT: Z = clear, NZ = blocked. (PROBE_ACC) = merged attributes.
;      destroys AF,BC,DE,HL - HL included now, where it used to be
;      pushed and popped for no caller that wanted it.
; ---------------------------------------------------------------------
BOX_SOLID_V:    ld   c,a                    ; C = the scanline for a moment
                ld   a,b
                ld   (PROBE_MASK),a         ; the mask, out of the way: B is
                                            ; the only register left to count
                                            ; columns with, once MAP_CELL has
                                            ; HL, ATTR_OF has DE and the
                                            ; accumulator has C
                ld   a,l
                and  TILE_W_BYTES - 1       ; how far into its tile the edge is
                add  a,KARA_BOX_W - 1       ; ... plus her width: 0..8
                rrca                        ; / TILE_W_BYTES - and RRCA wraps
                rrca                        ; bit 0 round to bit 7, so the AND
                and  &3F                    ; below is not optional
                inc  a
                ld   b,a                    ; B = 1, 2 or 3 tiles across
                ld   a,c
                call MAP_CELL               ; BC preserved
                ld   c,0                    ; ... and now C accumulates
.col:           ld   a,(hl)
                call ATTR_OF                ; HL preserved
                or   c
                ld   c,a
                dec  b
                jr   z,.done
                call MAP_COL_RIGHT
                jr   .col
.done:          ld   a,c
                ld   (PROBE_ACC),a
                ld   hl,PROBE_MASK
                and  (hl)
                ret

; ---------------------------------------------------------------------
; CLIMB_AT - the attributes of the tile under the MIDDLE of her box, at
; world pixel row A.
;
; A LADDER IS ONE TILE WIDE AND HER BOX IS THREE, so BOX_SOLID_V asks
; the wrong question on a ladder: it merges the brick either side of the
; shaft and every probe inside the wall comes back solid. The climb
; therefore probes ONE column.
;
; AND IT IS THE MIDDLE OF HER FIGURE, NOT OF HER COLLISION BOX. Those
; are not the same byte: KARA_WX is the left edge of her 12-byte sprite
; and KARA_BOX_W is 6, so the box is her LEFT HALF while the drawn
; figure sits in bytes 3..9 of it - measured off the blobs. A player
; lines the ladder up with what they can see, and CLIMB_GRAB then puts
; what they can see on it.
;
; IN : A = world pixel row      OUT: A = attribute byte
;      destroys AF,DE,HL.  BC preserved - PLAYER_CLIMB keeps the line it
;      proposed in C and the attribute it read in B.
; ---------------------------------------------------------------------
CLIMB_AT:       push af
                ld   hl,(KARA_WX)
                ld   de,KARA_W_BYTES / 2    ; the middle of her SPRITE
                add  hl,de
                pop  af
                jp   MAP_ATTR

PROBE_ACC:      db 0
PROBE_MASK:     db 0
