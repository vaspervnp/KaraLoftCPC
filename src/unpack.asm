; =====================================================================
; unpack.asm - ZX0 into a bank                                 (MODULE 5)
;
; Every level's art is a handful of BANK IMAGES: the blobs laid out at
; fixed addresses inside one 16 KB bank, the whole bank ZX0-packed as a
; single stream. tools/level_banks.py builds them and writes
; build/levels/banks.inc, which says which bank and which address each
; blob ended up at.
;
; That makes loading a level three steps per bank - read the file into
; the staging buffer, page the bank in, unpack - with no directory to
; walk and no addresses to fix up. It also compresses better than
; packing each blob on its own, because ZX0 sees the repeats ACROSS
; blobs (two facings of the same character share most of their bytes)
; and because the unused tail of a bank is zeros.
;
; ZX0 was picked on measurement, not reputation: best ratio AND fastest
; depacker of the nine RASM ships, each run on a 6128 and compared byte
; for byte. See CLAUDE.md 7.4 and tools/pack.py.
;
; THE STAGING BUFFER MUST NOT BE IN THE WINDOW. The unpacker reads from
; HL and writes to &4000-&7FFF, which is the bank it just paged in, so
; the packed stream has to sit in base RAM - &8000 upward, where the
; save-under buffers live and where nothing is being drawn during a
; level change.
; =====================================================================

LEVEL_STAGE     equ &8000       ; the packed stream lands here; the
                                ; biggest measured is 4,695 bytes and
                                ; &8000-&9FFF holds 8,192
LEVEL_STAGE_MAX equ &2000

; ---------------------------------------------------------------------
; UNPACK_BANK - page a bank in and fill it from a packed stream.
;
; IN : A  = RAM configuration, &C0 or &C4-&C7 (see CLAUDE.md 6.2)
;      HL = the packed stream, anywhere OUTSIDE &4000-&7FFF
; OUT: the bank holds the unpacked image and is left paged in
;      destroys AF,BC,DE,HL,AF',BC',DE',HL',IX
;
; About 49 T a byte of OUTPUT, so a full 16 KB bank is ~800,000 T -
; ten frames. A level is four or five of those.
; ---------------------------------------------------------------------
UNPACK_BANK:    ld   c,a
                ld   b,&7F              ; the gate array's RAM select
                out  (c),c
                ld   de,&4000
                ; falls into the depacker, which ends in RET

                include "vendor/dzx0_fast.asm"
UNPACK_RUN:     ; ... and the macro expands here, so this is its entry
                DecompressZX0

; ---------------------------------------------------------------------
; UNPACK_AT - the same depacker, anywhere.
;
; The title screen goes STRAIGHT INTO VIDEO RAM: it is 16,336 bytes of
; a 200-line picture, there is no bank to stage it through, and nothing
; else is on the screen while it is up.
; IN : HL = packed stream, DE = destination
;      destroys what UNPACK_BANK destroys
; ---------------------------------------------------------------------
UNPACK_AT:      jp   UNPACK_RUN

; ---------------------------------------------------------------------
; UNPACK_LIST - unpack a whole level from a table already in RAM.
;
; IN : HL = table of  { db config : dw packed stream }  ending in db 0
;      destroys everything UNPACK_BANK does
;
; Used by the tests and by any path that has the streams resident. The
; disc path reads one file at a time into LEVEL_STAGE and calls
; UNPACK_BANK directly, because a level's packed data is ~17 KB and the
; staging buffer is 8 KB.
; ---------------------------------------------------------------------
UNPACK_LIST:    ld   a,(hl)
                inc  hl
                or   a
                ret  z
                ld   (UNPACK_CFG),a
                ld   e,(hl)
                inc  hl
                ld   d,(hl)
                inc  hl
                ld   (UNPACK_NEXT),hl
                ex   de,hl
                ld   a,(UNPACK_CFG)
                call UNPACK_BANK
                ld   hl,(UNPACK_NEXT)
                jr   UNPACK_LIST

UNPACK_CFG:     db 0
UNPACK_NEXT:    dw 0

; ---------------------------------------------------------------------
; LEVEL_LOAD - a whole level's art, from the disc into its banks.
;
; IN : A = index into DISC_LEVEL_SETS - the level number times two, plus
;      one for its set pieces
; OUT: carry SET on success, and the window left paged at the last bank.
;      Carry clear means the disc read failed; DISC_ST0/ST1/ST2 say why.
;      destroys everything, INTERRUPTS OFF ON RETURN
;
; Interrupts stay off for the whole load: the 765 has no FIFO and an
; overrun loses the sector (src/disc.asm). Nothing is being drawn during
; a level change, but the caller has to re-anchor the raster gates
; afterwards - WAIT_VSYNC and a fresh FRAME_TICK0 - because the tick
; count has been standing still.
;
; About 1.3 s: 0.3 reading and 0.8-1.05 unpacking, per CLAUDE.md 7.5.
; ---------------------------------------------------------------------
LEVEL_LOAD:     di
                add  a,a
                ld   e,a
                ld   d,0
                ld   hl,DISC_LEVEL_SETS
                add  hl,de
                ld   e,(hl)
                inc  hl
                ld   d,(hl)
                ld   a,d
                or   e
                scf
                ret  z                      ; this level has no such set
                ex   de,hl

                ld   a,(hl)                 ; how many banks
                inc  hl
                ld   (LEVEL_BANKS),a

.bank:          ld   a,(hl)                 ; the RAM configuration
                inc  hl
                ld   (LEVEL_CFG),a
                ld   a,(hl)                 ; track
                inc  hl
                ld   (DISC_TRACK),a
                ld   a,(hl)                 ; first sector
                inc  hl
                ld   (DISC_SECT),a
                ld   a,(hl)                 ; how many sectors
                inc  hl
                ld   (DISC_COUNT),a
                ld   (LEVEL_NEXT),hl

                ld   hl,LEVEL_STAGE         ; ... which is outside the window,
                ld   (DISC_PTR),hl          ; so the unpack can page freely
                call DISC_READ
                ret  nc

                ld   a,(LEVEL_CFG)
                ld   hl,LEVEL_STAGE
                call UNPACK_BANK

                ld   hl,LEVEL_BANKS
                dec  (hl)
                ld   hl,(LEVEL_NEXT)
                jr   nz,.bank

                call DISC_MOTOR_OFF
                scf
                ret

LEVEL_BANKS:    db 0
LEVEL_CFG:      db 0
LEVEL_NEXT:     dw 0

; ---------------------------------------------------------------------
; LEVEL_MAP_LOAD - a level's OWN bytes, from the disc into LEVEL_IMAGE.
;
; IN : A = level number, 0-5
; OUT: carry SET, and LEVEL_IMAGE holds the tile flags and then the
;      .lvl (tools/make_level_image.py). Carry clear means either that
;      the disc read failed - DISC_ST0/ST1/ST2 say why - or that this
;      level has no map on the disc at all, which is five of the six.
;      destroys everything, INTERRUPTS OFF ON RETURN
;
; THE MAP USED TO RIDE IN THE CORE IMAGE and that is why this exists.
; main.asm INCBINed level_1.lvl and its tile flags at LEVEL_IMAGE and
; the bootstrap LDIRed them down, which costs 2,200 bytes of a binary
; that loads at &4000 and relocates below it. One level fits. Six is
; 13 KB and there is no 13 KB - so a level's own bytes travel with its
; art now, and a transition reads them the same way.
;
; It is LEVEL_LOAD's shape with the paging taken out: one record, read
; into the staging buffer like any other, and unpacked into BASE RAM
; rather than into the window. 354 bytes on the disc for the City, one
; sector, against 2,405 unpacked.
; ---------------------------------------------------------------------
LEVEL_MAP_LOAD: di
                add  a,a
                ld   e,a
                ld   d,0
                ld   hl,DISC_LEVEL_MAPS
                add  hl,de
                ld   e,(hl)
                inc  hl
                ld   d,(hl)
                ld   a,d
                or   e                      ; ... and OR leaves carry clear,
                ret  z                      ; which is what "no map" says
                ex   de,hl

                inc  hl                     ; the bank count, always one
                inc  hl                     ; ... and its RAM configuration,
                                            ; which nothing pages here
                ld   a,(hl)                 ; track
                inc  hl
                ld   (DISC_TRACK),a
                ld   a,(hl)                 ; first sector
                inc  hl
                ld   (DISC_SECT),a
                ld   a,(hl)                 ; how many
                ld   (DISC_COUNT),a

                ld   hl,LEVEL_STAGE
                ld   (DISC_PTR),hl
                call DISC_READ
                ret  nc

                call DISC_MOTOR_OFF
                ld   hl,LEVEL_STAGE
                ld   de,LEVEL_IMAGE
                call UNPACK_AT
                scf
                ret
