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

; THE BIT ORDER IS THE EDITOR'S, NOT THIS FILE'S. docs/editor.md 9.2
; ships a tileflags_<level>.bin of one byte a tile and names the bits;
; every probe here is symbolic (`AND TA_SOLID`, `LD B,TA_BLOCK`) and
; none of them cared which bit it was, so the engine took the format's
; numbering rather than asking the exporter to translate. A translation
; pass is 256 bytes of nothing to go wrong in, and this way the golden
; file and the running table hold the same byte.
TA_SOLID        equ %00000001   ; blocks from every direction
TA_PLATFORM     equ %00000010   ; one-way - blocks a descent only
TA_HAZARD       equ %00000100   ; damages on contact
TA_CLIMB        equ %00001000   ; a ladder: UP and DOWN move her along it
TA_WATER        equ %00010000   ; RESERVED, level 4 - defined, never read
TA_SINK         equ %00100000   ; RESERVED, level 5 - quicksand
TA_DEADLY       equ %01000000   ; RESERVED - a fall that does not end well
TA_BLOCK        equ TA_SOLID + TA_PLATFORM

; ---------------------------------------------------------------------
; HER BOX, AND WHERE THE SPRITE SITS ON IT
;
; KARA_WX / KARA_WY are the BOX, not the sprite. The drawer subtracts
; KARA_ART_X once a frame (PLAYER_TO_SCREEN) and every probe in this
; file, in entity.asm and in enemy.asm gets the body's own edges for
; nothing - which matters, because the frame has 160 T spare (CLAUDE.md
; 9) and adding the offset at each of the six probe sites instead cost
; more than that.
;
; THEY USED TO BE THE SPRITE, and the box was its LEFT HALF: 6 bytes of
; box against a 12-byte sprite box, with the figure drawn in bytes 3..9
; of it. So her collision box was three bytes - six pixels - to the left
; of her boots, everywhere. Nothing in the City showed it because the
; roof has no edge to stand on the lip of, and the ladder made it
; visible for the first time: centred by the box she was drawn climbing
; the brick beside the shaft.
;
; BOTH NUMBERS ARE MEASURED OFF THE SHIPPED BLOBS, not guessed:
;
;   * every cel's last drawn line is 63 - all 18 of kcore, all 10 of
;     kact, and 11 of kextra's 13 (the two that stop at 60 are run cels
;     with the back foot lifted). So the box is the full 64 and her
;     boots rest ON the floor line instead of three pixels through it.
;   * the boots occupy bytes 3..8 on the idle and walk cels and 1..9 at
;     the widest stride, so a 6-byte box at KARA_ART_X = 3 is centred
;     under what she stands on.
;
; KARA_ART_X falls out of the two widths - (12 - 6) / 2 - which is the
; same statement as "the box is centred in the sprite box", and is why
; it is written that way rather than as a literal 3.
; ---------------------------------------------------------------------
KARA_BOX_W      equ 6           ; bytes - 12 pixels, narrower than her sprite
KARA_BOX_H      equ 64          ; lines - all of it: her feet are on line 63
KARA_ART_X      equ (KARA_W_BYTES - KARA_BOX_W) / 2   ; 3 - the sprite's left
                                ; edge, relative to the box's

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
; THE TABLE IS RAM AND THE LEVEL BRINGS IT. It used to be a literal in
; this file, in the artist's frame order, which is fine for exactly one
; level: the City. It is now tileflags_<level>.bin (docs/editor.md 9.1),
; one byte a tile, written by tools/make_level.py and LDIRed here by
; LEVEL_PARSE - so level 2's tileset does not need a second table in the
; engine and the editor writes the same bytes the loader reads.
;
; IT MUST BE PAGE-ALIGNED: ATTR_OF indexes it with `LD D,TILE_ATTR >> 8`
; and a tile number in E, which discards any carry out of E.
TILE_ATTR       equ &A900       ; 256 bytes, above the entity table
TILE_ATTR_N     equ 256

; ---------------------------------------------------------------------
; MAP_CELL - address in bank C4 of the cell covering a world position.
;
; THE ROW IS SIXTEEN BITS AND IT IS SCALED SEPARATELY FROM THE BASE,
; which is a change and the reason for it is a level taller than 256
; pixels. It used to fold the two together: L took Y AND &F0 (= row*16),
; H took MAP_ADDR >> 11, and three ADD HL,HL carried both to row*128 and
; to &A000 at once - elegant, 28 T cheaper, and it ties the map's WIDTH
; to the base address's alignment, so a map of another shape cannot have
; one without moving the other.
;
; Scaled apart, the two numbers are what they say they are:
;
;   row * W = (Y AND ((H - 1) * 16)) << (log2 W - 4)
;
; and the base is added at the end. The column still cannot carry into
; H: row*W's low byte is a multiple of W and the column is at most
; W - 1, so their sum is at most 255 for every shape.
;
; IN : HL = world byte column, DE = world pixel row
; OUT: HL = map cell address, in BASE RAM - no paging needed.
;      destroys AF,DE,HL.  *** BC IS PRESERVED *** - BOX_SOLID_H keeps
;      its row counter in B and BOX_SOLID_V its column counter.
; ---------------------------------------------------------------------
MAP_CELL:       ld   a,d
                and  MAP_ROW_MASK >> 4      ; the row's own high bits
PM_MC_ROWHI     equ  $ - 1
                ld   d,a
                ld   a,e
                and  &F0                    ; ... and the pixel inside the
                ld   e,a                    ; tile goes, leaving row * 16
PM_SCALE        equ  $
                sla  e                      ; * MAP_W / 16: three doublings
                rl   d                      ; at 128 wide, one at 32 - and
                sla  e                      ; the pairs this shape does not
                rl   d                      ; want are NOPs, which are 8 T a
                sla  e                      ; pair exactly like the shifts
                rl   d                      ; they stand in for
                ld   a,l
                srl  h
                rra
                srl  h
                rra                         ; A = BX >> 2
                and  MAP_COL_MASK           ; map column 0-127
PM_MC_COLM      equ  $ - 1
                ld   l,a
                ld   h,MAP_ADDR >> 8
                add  hl,de
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
; IN : HL = world byte column, DE = world pixel row  OUT: A = attributes
;      destroys AF,DE,HL.  BC preserved.
MAP_ATTR:       call MAP_CELL
                ld   a,(hl)
                jp   ATTR_OF

; MAP_ROW_DOWN - one map row down, wrapping inside the 1 KB map.
;      destroys AF.  HL stepped.
MAP_ROW_DOWN:   ld   a,l
                add  a,MAP_W
PM_MD_STEP      equ  $ - 1
                ld   l,a
                ret  nc
                inc  h
                ld   a,h
                and  MAP_PAGES - 1          ; 2 KB of map = eight pages
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
PM_CR_COLM      equ  $ - 1
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
; IN : HL = leading edge, DE = world pixel row of the box top
; OUT: Z = clear, NZ = blocked. (PROBE_ACC) = OR of every attribute seen,
;      so a hazard falls out of the reads the wall test already did.
;      destroys AF,BC,DE,HL.
; ---------------------------------------------------------------------
                ; THE NIBBLE IS TAKEN BEFORE THE CALL, not after it: the
                ; row is sixteen bits now and MAP_CELL destroys DE.
BOX_SOLID_H:    ld   a,e
                and  15                     ; how far into its tile is the top?
                push af
                call MAP_CELL               ; the column, resolved once
                pop  af
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
; IN : HL = box left edge, DE = world pixel row,
;      B  = attribute mask (TA_SOLID rising, TA_BLOCK falling)
; OUT: Z = clear, NZ = blocked. (PROBE_ACC) = merged attributes.
;      destroys AF,BC,DE,HL - HL included now, where it used to be
;      pushed and popped for no caller that wanted it.
; ---------------------------------------------------------------------
BOX_SOLID_V:    ld   a,b
                ld   (PROBE_MASK),a         ; the mask, out of the way: B is
                                            ; the only register left to count
                                            ; columns with, once MAP_CELL has
                                            ; HL and ATTR_OF has DE
                ld   a,l
                and  TILE_W_BYTES - 1       ; how far into its tile the edge is
                add  a,KARA_BOX_W - 1       ; ... plus her width: 0..8
                rrca                        ; / TILE_W_BYTES - and RRCA wraps
                rrca                        ; bit 0 round to bit 7, so the AND
                and  &3F                    ; below is not optional
                inc  a
                ld   b,a                    ; B = 1, 2 or 3 tiles across
                call MAP_CELL               ; DE = the row, BC preserved
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
; The middle of her box, which is now also the middle of her figure -
; see the note by KARA_ART_X. A player lines a ladder up with what they
; can see, and CLIMB_GRAB puts what they can see on it.
;
; IN : DE = world pixel row      OUT: A = attribute byte
;      destroys AF,DE,HL.  BC preserved - PLAYER_CLIMB keeps the line it
;      proposed in C and the attribute it read in B.
; ---------------------------------------------------------------------
CLIMB_AT:       push de
                ld   hl,(KARA_WX)
                ld   de,KARA_BOX_W / 2      ; the middle of her
                add  hl,de
                pop  de
                jp   MAP_ATTR

PROBE_ACC:      db 0
PROBE_MASK:     db 0

; Does THIS level have a TA_HAZARD tile in it at all? ORed out of the
; whole of TILE_ATTR by HAZARD_SCAN, once, the instant the flags arrive
; (MAP_INSTALL), and read by HAZARD_HURT (player.asm) on every frame.
; It lives here because it is a property of the attribute table and not
; of the player - the one that writes it and the one that reads it are
; two other modules, and this is the one that owns what it is about.
LEVEL_HAZARD:   db 0

; ---------------------------------------------------------------------
; HAZARD_SCAN - can this level's scenery hurt her?
;
; A HAZARD PROBE IS ~560 T AND THE TIGHTEST PATH HAS 800 (CLAUDE.md 9),
; so a level with no spikes in it must not pay for one. The whole table
; is ORed once, here, where it has just arrived: four of the six
; environments have no TA_HAZARD tile anywhere and for those
; HAZARD_HURT is three instructions and a RET. It is "a level with no
; ladder carries no climb" (CLAUDE.md 6.2), one table along.
;
; It is a routine rather than eight lines inside MAP_INSTALL because
; putting them there took that routine past 128 bytes of its own span
; and two of its `jr .refuse` stopped reaching - a refusal is exactly
; what must not be one insertion away from breaking.
;                                destroys AF,BC,HL
; ---------------------------------------------------------------------
HAZARD_SCAN:    ld   hl,TILE_ATTR
                ld   b,0                    ; 256 entries - which is what
                ld   c,0                    ; DJNZ makes of a count of 0
.next:          ld   a,(hl)
                or   c
                ld   c,a
                inc  hl
                djnz .next
                ld   a,c
                and  TA_HAZARD
                ld   (LEVEL_HAZARD),a
                ret
