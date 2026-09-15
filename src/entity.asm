; =====================================================================
; entity.asm - the things in a level that are not tiles     (MODULE 5)
;
; THE RECORD IS THE LEVEL FILE'S RECORD. docs/editor.md 9.2 fixes an
; entity at eight bytes - kind, x, y, flags, p0, p1 - and this is those
; eight bytes, in that order, so the loader of module 6 is an LDIR and
; not a conversion. Getting that wrong costs a change on both sides of
; a format that a web application is going to be written against; the
; cheap moment to agree is now, while nothing reads it yet.
;
;   +0 kind    EK_*, the editor's EntityKind enum in its own order
;   +1 x       u16, WORLD PIXELS - even ones are byte-aligned
;   +3 y       u16, world pixels, the BASE of the hitbox - what a
;              designer drops on a floor. Its top is y - height.
;   +5 flags   EF_*
;   +6 p0      per kind - see the table below
;   +7 p1
;
; X IS PIXELS AND THE ENGINE WORKS IN BYTES. One Mode 0 byte is two
; pixels, so every comparison here shifts x right by one first. The
; editor thinks in pixels because a designer does; the blitter cannot,
; because it writes bytes. Converting on the way in would be cheaper
; per frame and would put a conversion between the file and the table,
; which is the thing worth not having.
;
; WHAT p0 AND p1 MEAN IS PER KIND, and editor.md's Appendix A lists
; them as free text - so this is the engine's half of that agreement:
;
;   PICKUP      p0 = PU_*         p1 = amount, lock id, or symbol
;   DOOR        p0 = lock id      p1 = PU_* that opens it
;   RECEPTACLE  p0 = PU_* it takes  p1 = how many it still wants
;   NPC         p0 = coins asked  p1 = which line he says
;   ENEMY       p0 = patrol width in tiles   p1 = shots a second
;   HAZARD      p0 = damage       p1 = period
;
; No Module 5 code reads the enemy or hazard fields; they are named so
; the format is final.
; =====================================================================

; The editor's enum, in its declaration order (editor.md 5.3).
EK_PLAYER_START equ 0
EK_CHECKPOINT   equ 1
EK_ENEMY        equ 2
EK_NPC          equ 3
EK_PICKUP       equ 4
EK_HAZARD       equ 5
EK_DOOR         equ 6
EK_RECEPTACLE   equ 7
EK_OBJECTIVE    equ 8
EK_TRANSITION   equ 9
EK_CUTSCENE     equ 10
EK_COUNT        equ 11

EF_ACTIVE       equ %00000001   ; in play at all
EF_TAKEN        equ %00000010   ; picked up, opened, filled - done with
EF_SOLID        equ %00000100   ; a shut door: the physics must not pass it
EF_TOUCH        equ %00001000   ; acts on contact; without it, needs UP

; What a pickup IS. One list for every level, because a medkit is a
; medkit in all of them and the handlers are shared.
PU_KEY          equ 0
PU_AMMO         equ 1
PU_MEDKIT       equ 2
PU_COIN         equ 3
PU_IDOL         equ 4
PU_BOOK         equ 5           ; p1 carries which symbol

ENT_KIND        equ 0
ENT_X           equ 1
ENT_Y           equ 3
ENT_FLAGS       equ 5
ENT_P0          equ 6
ENT_P1          equ 7
ENT_STRIDE      equ 8
ENT_MAX         equ 24
ENT_TABLE       equ MAP_ADDR + MAP_W * MAP_H    ; &A800, straight after the
                                                ; map - both are the level's
                                                ; own data and both are base
                                                ; RAM because bank C4 is full

; Hitboxes, per kind, in BYTES and LINES - the art's own footprint.
; A pickup is 8x16 pixels, which is exactly one tile; the garage door is
; the 4x5 tile stamp of the manifest.
; The widest row below, which ENTITY_COLLISION_CHECK's cheap X reject
; is sized against. Widen the door and this has to widen with it.
HITBOX_W_MAX    equ 16
                align 32
ENT_HITBOX:     db  6, 64       ; PlayerStart - her own box
                db  4, 16       ; Checkpoint
                db  6, 64       ; Enemy
                db  6, 64       ; Npc
                db  4, 16       ; Pickup
                db  4, 16       ; Hazard
                db 16, 80       ; Door - the garage is 4 tiles by 5
                db  4, 16       ; Receptacle
                db  4, 16       ; Objective
                db  8, 32       ; Transition
                db  8, 32       ; Cutscene
                ds 32 - EK_COUNT * 2, 0

; ---------------------------------------------------------------------
; ENT_CLEAR - no entities. Called before a level's table is loaded, and
; at boot, because &A800 is whatever BASIC left there.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
ENT_CLEAR:      xor  a
                ld   (ENT_COUNT),a
                ld   (ENT_BAKED),a
                ld   hl,ENT_TABLE
                ld   de,ENT_TABLE + 1
                ld   bc,ENT_MAX * ENT_STRIDE - 1
                ld   (hl),0
                ldir
                ret

; ---------------------------------------------------------------------
; ENT_RECOUNT - how many slots the level actually used.
;
; Module 6's loader will take this from the file's header instead; until
; there is a file, counting the trailing empties is the same answer and
; keeps the scan honest either way.
;                                destroys AF,BC,HL
; ---------------------------------------------------------------------
ENT_RECOUNT:    ld   hl,ENT_TABLE + (ENT_MAX - 1) * ENT_STRIDE + ENT_FLAGS
                ld   b,ENT_MAX
.back:          ld   a,(hl)
                and  EF_ACTIVE
                jr   nz,.found
                ld   a,l
                sub  ENT_STRIDE
                ld   l,a
                jr   nc,.same
                dec  h
.same:          djnz .back
                xor  a
                ld   (ENT_COUNT),a
                ret
.found:         ld   a,b
                ld   (ENT_COUNT),a
                ret

; ---------------------------------------------------------------------
; ENT_OVERLAP - does the entity at HL overlap Kara's collision box?
;
; A separating-axis test, which is four comparisons and no multiplies:
; two boxes miss each other if one is entirely left of, right of, above
; or below the other. X is 16-bit because the world is 512 bytes wide;
; Y is 8-bit because it wraps at 256, which IS the map's height.
;
; IN : HL -> the record
; OUT: carry SET if they overlap. HL preserved.
;      destroys AF,BC,DE
; ---------------------------------------------------------------------
ENT_OVERLAP:    push hl
                ld   a,(hl)                 ; kind -> its hitbox
                add  a,a
                add  a,ENT_HITBOX AND 255   ; aligned: cannot carry
                ld   c,a
                ld   b,ENT_HITBOX >> 8
                ld   a,(bc)                 ; width, in bytes
                ld   e,a
                inc  bc
                ld   a,(bc)
                ld   d,a                    ; height, in lines

                ; ---- X, in world bytes ------------------------------
                inc  hl
                ld   c,(hl)
                inc  hl
                ld   b,(hl)                 ; BC = x in pixels
                srl  b
                rr   c                      ; ... in bytes
                push de
                ld   hl,(KARA_WX)
                ld   d,b
                ld   e,c                    ; DE = the entity's left edge
                or   a
                sbc  hl,de                  ; kara - entity
                jr   nc,.k_right
                ; she is to the LEFT: does her right edge reach it?
                add  hl,de                  ; undo
                ld   de,KARA_BOX_W
                add  hl,de
                or   a
                ld   d,b
                ld   e,c
                sbc  hl,de
                jr   c,.miss                ; her right edge stops short
                jr   z,.miss
                jr   .x_hit
.k_right:       ; she is to the RIGHT of its left edge: is she past its
                ; right edge? HL already holds kara - entity.
                pop  de
                push de
                ld   d,0                    ; E = its width in bytes
                or   a
                sbc  hl,de
                jr   nc,.miss               ; kara - entity >= width
.x_hit:         pop  de

                ; ---- Y, 8-bit and wrapping --------------------------
                pop  hl
                push hl
                ld   bc,ENT_Y
                add  hl,bc
                ld   a,(hl)                 ; y in pixels, low byte is enough:
                sub  d                      ; the map is 256 lines tall. The
                ld   c,a                    ; editor anchors Y at the BASE of
                                            ; the sprite, which is what a
                                            ; designer drops on a floor, so
                                            ; the hitbox top is y - height.
                ld   a,(KARA_WY)
                sub  c                      ; kara - entity
                jr   nc,.k_below
                ; she is ABOVE it: does her bottom reach?
                add  a,c                    ; undo
                add  a,KARA_BOX_H
                sub  c
                jr   c,.miss2
                jr   z,.miss2
                jr   .hit
.k_below:       cp   d                      ; D = its height
                jr   nc,.miss2
.hit:           pop  hl
                scf
                ret
.miss:          pop  de
.miss2:         pop  hl
                or   a
                ret

; ---------------------------------------------------------------------
; ENTITY_COLLISION_CHECK - the first live entity Kara is standing in.
;
; IN : A = EF_ mask an entity must have to count (EF_TOUCH for the
;      automatic ones, 0 for anything at all)
; OUT: carry SET and HL -> the record; carry clear and HL undefined.
;      destroys AF,BC,DE,HL
;
; FIRST, not nearest. Two overlapping pickups is a level-design fault
; and picking the nearer of them would hide it; taking the first makes
; it show up as the other one being unreachable.
; ---------------------------------------------------------------------
ENTITY_COLLISION_CHECK:
                ld   (ENT_WANT),a
                ld   hl,ENT_TABLE
                ; ENT_COUNT AND NOT ENT_MAX. Walking all 24 slots cost
                ; 4,004 T a frame with six of them in use - of a frame
                ; that had 1,324 to spare. The level file carries an
                ; entity count in its header (editor.md 9.2) for exactly
                ; this, so the scan stops where the level stops.
                ld   a,(ENT_COUNT)
                or   a
                ret  z
.next:          ld   (ENT_LEFT),a
                ld   a,(hl)                 ; kind 0 is PlayerStart, so an
                ld   bc,ENT_FLAGS           ; empty slot is told by its FLAGS
                add  hl,bc
                ld   a,(hl)
                ld   bc,-ENT_FLAGS
                add  hl,bc
                bit  0,a                    ; EF_ACTIVE
                jr   z,.skip
                bit  1,a                    ; EF_TAKEN: done with
                jr   nz,.skip
                ld   b,a
                ld   a,(ENT_WANT)
                and  b
                ld   c,a
                ld   a,(ENT_WANT)
                cp   c                      ; every wanted bit present?
                jr   nz,.skip
                ; A CHEAP X REJECT BEFORE THE REAL ONE. ENT_OVERLAP looks
                ; the hitbox up and then tests both axes, which is about
                ; 450 T to discover that something twenty tiles away is
                ; twenty tiles away. The widest row of ENT_HITBOX is the
                ; garage door at 16 bytes, so nothing can be touching her
                ; unless its left edge is within KARA_BOX_W to her right
                ; or HITBOX_W_MAX to her left, and that is one subtract.
                push hl
                inc  hl
                ld   e,(hl)
                inc  hl
                ld   d,(hl)                 ; DE = x in pixels
                srl  d
                rr   e                      ; ... in bytes
                ld   hl,(KARA_WX)
                or   a
                sbc  hl,de                  ; kara - entity
                ld   de,KARA_BOX_W - 1
                add  hl,de                  ; 0..(max + KARA_BOX_W - 2) if it
                ld   a,h                    ; can possibly be touching
                or   a
                jr   nz,.far
                ld   a,l
                cp   HITBOX_W_MAX + KARA_BOX_W - 1
                jr   nc,.far
                pop  hl
                call ENT_OVERLAP
                jr   nc,.skip
                ld   (ENT_HIT),hl           ; the handlers clobber HL and
                scf                         ; need to find it again
                ret
.far:           pop  hl
.skip:          ld   bc,ENT_STRIDE
                add  hl,bc
                ld   a,(ENT_LEFT)
                dec  a
                jr   nz,.next
                or   a
                ret

ENT_WANT:       db 0
ENT_LEFT:       db 0
ENT_COUNT:      db 0            ; slots in use, from the level's header

; =====================================================================
; The five interaction handlers of CLAUDE.md 8.6, and the state they
; move. Two kinds of contact, and the difference matters:
;
;   ON TOUCH   a pickup, the moment her box reaches it. Nothing to
;              press, because a key you have to ask for is a key the
;              player walks past.
;   ON UP      a door, a receptacle, an NPC. These CHANGE the world or
;              spend something, so they are asked for - and UP is the
;              ask, which is what plan.md 5.2 wanted before Z became
;              the roll (8.4).
; =====================================================================

HP_MAX          equ 100
HP_MEDKIT       equ 35          ; "medkit restores 35, capped at 100"
AMMO_CLIP       equ 14          ; "clips add 14"

; What the last interaction did, for the HUD and for the tests. It is
; not a return value: a handler that refuses has to say WHY, and "the
; carry was clear" cannot tell a locked door from an empty hand.
ER_NOTHING      equ 0
ER_TOOK         equ 1           ; a pickup went into the inventory
ER_HEALED       equ 2
ER_OPENED       equ 3           ; a door gave way
ER_LOCKED       equ 4           ; ... or did not: wrong key, or none
ER_PLACED       equ 5           ; a receptacle took what it wanted
ER_WRONG        equ 6           ; ... or was offered the wrong thing
ER_EMPTY        equ 7           ; nothing in hand to offer
ER_TOLD         equ 8           ; an NPC was paid and talked
ER_POOR         equ 9           ; ... or was not paid enough
ER_FULL         equ 10          ; already at full health

; ---------------------------------------------------------------------
; ENT_UPDATE - one frame of the world reacting to where she is.
;
; Call after PLAYER_UPDATE, so her box is where the physics left it.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
ENT_UPDATE:     xor  a
                ld   (ENT_RESULT),a

                ; THE TOUCH SWEEP TAKES THE FRAMES THE ENEMY REDRAW
                ; DOES NOT - see ENEMY_DRAW. At 2 bytes a frame she
                ; cannot cross a 4-byte pickup between two sweeps, and
                ; the pair of them on one frame is 376 T more than the
                ; frame has.
                ld   a,(FRAME_COUNT)
                rra
                jr   c,.asked
                ld   a,EF_TOUCH             ; the automatic ones first
                call ENTITY_COLLISION_CHECK
                jr   nc,.asked
                call ENT_ON_TOUCH

.asked:         ld   a,(INPUT_PRESSED)      ; and the asked-for ones. A
                and  IN_INTERACT            ; PRESS, not a hold: a held UP
                jr   z,.settle              ; is a jump, and a door that
                                            ; re-opened every frame would
                                            ; spend a key a frame
                xor  a
                call ENTITY_COLLISION_CHECK
                jr   nc,.settle
                call ENT_ON_INTERACT
                ; ... and then whatever that did to the world has to
                ; reach the picture: a pickup that has been taken is
                ; still baked into the tilemap until ENT_SETTLE puts the
                ; old tile back.
.settle:        jp   ENT_SETTLE

; ---------------------------------------------------------------------
; ENT_ON_INTERACT - UP, over something. HL -> the record.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
ENT_ON_INTERACT:
                ld   a,(hl)
                cp   EK_DOOR
                jp   z,CHECK_KEY_DOOR
                cp   EK_NPC
                jp   z,TALK_NPC_COIN
                cp   EK_RECEPTACLE
                ret  nz
                push hl
                ld   bc,ENT_P0
                add  hl,bc
                ld   a,(hl)                 ; what this one takes
                pop  hl
                cp   PU_IDOL
                jp   z,PLACE_STATUE
                cp   PU_BOOK
                jp   z,READ_BOOK_PUZZLE
                ret

; ---------------------------------------------------------------------
; ENT_ON_TOUCH - her box reached something marked EF_TOUCH.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
ENT_ON_TOUCH:   ld   a,(hl)
                cp   EK_PICKUP
                ret  nz
                push hl
                ld   bc,ENT_P0
                add  hl,bc
                ld   e,(hl)                 ; E = PU_*
                inc  hl
                ld   d,(hl)                 ; D = amount / id
                pop  hl

                ld   a,e
                cp   PU_MEDKIT
                jr   nz,.inventory
                ; A medkit is the one pickup that can be REFUSED: at full
                ; health it stays on the ground for when it is needed,
                ; which is the whole point of it being an item.
                push hl
                push de
                call USE_MEDKIT
                pop  de
                pop  hl
                ld   a,(ENT_RESULT)
                cp   ER_FULL
                ret  z                      ; leave it where it is
                jr   .consume

.inventory:     ld   a,e
                cp   PU_KEY
                jr   nz,.not_key
                ld   hl,KEYS_COUNT
                inc  (hl)
                jr   .took
.not_key:       cp   PU_AMMO
                jr   nz,.not_ammo
                ld   a,(AMMO_RESERVE)
                add  a,d
                jr   nc,.ammo_ok
                ld   a,255                  ; a reserve that wraps to nothing
.ammo_ok:       ld   (AMMO_RESERVE),a       ; is a pickup that punishes you
                jr   .took
.not_ammo:      cp   PU_COIN
                jr   nz,.not_coin
                ld   a,(COINS_COUNT)
                add  a,d
                jr   nc,.coin_ok
                ld   a,255
.coin_ok:       ld   (COINS_COUNT),a
                jr   .took
.not_coin:      cp   PU_IDOL
                jr   nz,.not_idol
                ld   hl,STATUES_HELD
                inc  (hl)
                jr   .took
.not_idol:      cp   PU_BOOK
                ret  nz                     ; an unknown pickup is left alone
                ld   a,d                    ; the symbol she is now carrying
                ld   (CURRENT_BOOK_ID),a
.took:          ld   a,ER_TOOK
                ld   (ENT_RESULT),a
                ; HL was clobbered by the branches above, so find it again
                ; from what ENTITY_COLLISION_CHECK left in ENT_HIT
.consume:       ld   hl,(ENT_HIT)
                ld   bc,ENT_FLAGS
                add  hl,bc
                set  1,(hl)                 ; EF_TAKEN
                ret

; ---------------------------------------------------------------------
; CHECK_KEY_DOOR - a door, and a key that may or may not fit.
;
; p0 is the door's lock id and p1 the pickup that opens it, so a
; keycard door and a garage door are the same code with different
; bytes. Spending the key is what keeps a level honest: one key, one
; door.                          HL -> the door. destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
CHECK_KEY_DOOR: push hl
                ld   bc,ENT_P1
                add  hl,bc
                ld   a,(hl)                 ; which pickup opens it
                pop  hl
                cp   PU_KEY
                jr   nz,.locked             ; only keys, for now
                ld   a,(KEYS_COUNT)
                or   a
                jr   z,.locked
                dec  a
                ld   (KEYS_COUNT),a
                push hl
                ld   bc,ENT_FLAGS
                add  hl,bc
                set  1,(hl)                 ; EF_TAKEN: it is open
                res  2,(hl)                 ; ... and no longer solid
                pop  hl
                ld   a,ER_OPENED
                ld   (ENT_RESULT),a
                ret
.locked:        ld   a,ER_LOCKED
                ld   (ENT_RESULT),a
                ret

; ---------------------------------------------------------------------
; PLACE_STATUE - the forest altar. p1 is how many idols it still wants,
; so a two-idol altar is one byte's difference.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
PLACE_STATUE:   ld   a,(STATUES_HELD)
                or   a
                jr   z,.empty_handed
                dec  a
                ld   (STATUES_HELD),a
                push hl
                ld   bc,ENT_P1
                add  hl,bc
                dec  (hl)                   ; one fewer wanted
                ld   a,(hl)
                pop  hl
                or   a
                ld   a,ER_PLACED
                ld   (ENT_RESULT),a
                ret  nz                     ; it wants more
                push hl
                ld   bc,ENT_FLAGS
                add  hl,bc
                set  1,(hl)                 ; EF_TAKEN: satisfied, and the
                pop  hl                     ; Disables link fires off it
                ret
.empty_handed:  ld   a,ER_EMPTY
                ld   (ENT_RESULT),a
                ret

; ---------------------------------------------------------------------
; READ_BOOK_PUZZLE - a cave gate slot. It wants ONE symbol, p1, and she
; is carrying CURRENT_BOOK_ID. Three of them in the right order is the
; puzzle; a slot that takes the wrong book says so and keeps it.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
READ_BOOK_PUZZLE:
                ld   a,(CURRENT_BOOK_ID)
                or   a
                jr   z,.empty_handed
                ld   c,a
                push hl
                ld   de,ENT_P1
                add  hl,de
                ld   a,(hl)                 ; the symbol this slot wants
                pop  hl
                cp   c
                jr   nz,.wrong
                xor  a
                ld   (CURRENT_BOOK_ID),a    ; the book goes into the slot
                push hl
                ld   bc,ENT_FLAGS
                add  hl,bc
                set  1,(hl)                 ; lit
                pop  hl
                ld   a,ER_PLACED
                ld   (ENT_RESULT),a
                ret
.wrong:         ld   a,ER_WRONG
                ld   (ENT_RESULT),a
                ret
.empty_handed:  ld   a,ER_EMPTY
                ld   (ENT_RESULT),a
                ret

; ---------------------------------------------------------------------
; TALK_NPC_COIN - the desert informant. p0 is his price in coins; pay
; it and he talks, and p1 says which line. He only takes payment once -
; EF_TAKEN - so a player cannot be charged twice for the same hint.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
TALK_NPC_COIN:  push hl
                ld   bc,ENT_P0
                add  hl,bc
                ld   c,(hl)                 ; his price
                pop  hl
                ld   a,(COINS_COUNT)
                cp   c
                jr   c,.too_poor
                sub  c
                ld   (COINS_COUNT),a
                push hl
                ld   bc,ENT_FLAGS
                add  hl,bc
                set  1,(hl)                 ; paid: he keeps talking for free
                pop  hl
                push hl
                ld   bc,ENT_P1
                add  hl,bc
                ld   a,(hl)
                ld   (NPC_LINE),a           ; which line module 6 will show
                pop  hl
                ld   a,ER_TOLD
                ld   (ENT_RESULT),a
                ret
.too_poor:      ld   a,ER_POOR
                ld   (ENT_RESULT),a
                ret

; ---------------------------------------------------------------------
; USE_MEDKIT - 35 points, capped at 100, and REFUSED at full health so
; the pickup stays on the ground for when it is worth something.
;                                destroys AF
; ---------------------------------------------------------------------
USE_MEDKIT:     ld   a,(PLAYER_HP)
                cp   HP_MAX
                jr   nc,.full
                add  a,HP_MEDKIT
                cp   HP_MAX
                jr   c,.store
                ld   a,HP_MAX
.store:         ld   (PLAYER_HP),a
                ld   a,ER_HEALED
                ld   (ENT_RESULT),a
                ld   a,1
                ld   (HUD_DIRTY),a
                ret
.full:          ld   a,ER_FULL
                ld   (ENT_RESULT),a
                ret

; ---------------------------------------------------------------------
; The game state of CLAUDE.md 8.6. AMMO_RESERVE is not here: it belongs
; to the guns and lives in bullets.asm, which is the module that spends
; it.
; ---------------------------------------------------------------------
PLAYER_HP:      db HP_MAX       ; 0-100
KEYS_COUNT:     db 0
COINS_COUNT:    db 0
STATUES_HELD:   db 0
CURRENT_BOOK_ID:db 0            ; 0 = empty-handed, so symbols start at 1
NPC_LINE:       db 0
ENT_RESULT:     db ER_NOTHING
ENT_HIT:        dw 0            ; the record ENTITY_COLLISION_CHECK found

; =====================================================================
; DRAWING THEM - BY BAKING THEM INTO A TILE, AND THE MEASUREMENT THAT
; DECIDED IT
;
; The obvious thing is to draw a pickup like Kara: page its bank, find
; its cel, SPAN_DRAW with a save-under, SPAN_ERASE at the end of the
; frame. That was written, and measured:
;
;       ENT_DRAW, one pickup on screen          9,912 T
;       ENT_ERASE                               2,204 T
;                                              -------
;                                              12,116 T a frame
;
; against the 1,324 T a scrolling frame has spare (CLAUDE.md 9). It is
; not close, and the reason is the one 9 already records: "the remedy
; is decided by sparseness for SIZE and by bytes-per-line for TIME".
; A pickup is FOUR bytes a line. The span blitter's 168 T of per-line
; bookkeeping is sized against Kara's 64 lines of 5.7 bytes; at 4 bytes
; a line it is almost all of the cost, and no amount of sparseness
; helps because there is nothing to be sparse about.
;
; So a pickup is not a sprite. A pickup is 8x16 pixels, which is
; EXACTLY ONE TILE, and it never moves until it is taken - which makes
; it scenery, and scenery is already free. DRAW_COLUMN copies a tile
; into the incoming column for 64 T a raster whether that tile has a
; key drawn on it or not.
;
; So at level install each pickup is composited ONCE, into a private
; copy of the tile it is standing on, and the map cell is pointed at
; the copy. From then on it costs nothing at all: no draw, no erase, no
; save-under, no raster gate, and it scrolls because the whole picture
; scrolls. When it is taken the map byte goes back and the four
; character cells it covered are repainted, once.
;
; WHAT IT COSTS INSTEAD:
;
;   * 1 KB at the top of bank C4 for 16 scratch tiles, taken out of the
;     allocator's hands in tools/level_banks.py. Every level still fits,
;     the tightest with 5 bytes to spare.
;   * THE PICKUPS DO NOT ANIMATE. The sheets draw the key over 4 cels
;     and the ammo over 3; the baked one is cel 0. 12,116 T a frame is
;     what the bob would cost, and the frame has 1,324.
;   * A pickup has to sit ON the tile grid. The editor's record is in
;     world pixels and an unaligned one would need four scratch tiles
;     instead of one, so ENT_BAKE takes the cell the record's top-left
;     falls in. tools/make_city_map.py places them on the grid already.
; =====================================================================
PICKUP_W        equ 4                       ; bytes - one tile
PICKUP_H        equ 16                      ; lines

; The scratch tiles: the top of C4, which tools/level_banks.py holds
; back. TILE_SRC reads ANY 64-aligned address in that bank as a tile
; index - index = (addr - &4000) >> 6 - so the reserve only has to be
; aligned and out of the allocator's way.
ENT_BAKE_MAX    equ 16
ENT_BAKE_ADDR   equ &8000 - ENT_BAKE_MAX * TILE_BYTES       ; &7C00
ENT_BAKE_TILE0  equ (ENT_BAKE_ADDR - TILES_ADDR) >> 6       ; 240, NOT "/64"
ENT_FRAME_BUF   equ LEVEL_STAGE             ; the load is over by now

; One per baked pickup: which record, which map cell, and what the cell
; held before - which is what makes taking it a single byte write.
ENT_BAKE_REC    equ 0
ENT_BAKE_CELL   equ 2
ENT_BAKE_WAS    equ 4
ENT_BAKE_STRIDE equ 5

; ---------------------------------------------------------------------
; WHICH ART A PICKUP IS. Four bytes a kind: bank and blob. It is level
; 1's, and module 6 makes it per level along with the rest of the
; level's table - every address comes from build/levels/banks.inc, so
; the shape does not change, only where it is read from.
;
; The city's own sheet draws a key and an ammo clip and nothing else,
; which is right: a medkit is not city art. The other four kinds fall
; back on `hudicon`, which is 4x16 as well, carries one cel of every
; pickup in the game, and is in every level's bank set already because
; the HUD needs it.
; ---------------------------------------------------------------------
ENT_ART_BYTES   equ 4
                align 32                    ; indexed with ADD A,ENT_ART AND 255
ENT_ART:        db L1_CITYPICKUPS_BANK      ; PU_KEY
                dw L1_CITYPICKUPS_ADDR
                db CITYPICKUPS_KEY_FIRST
                db L1_CITYPICKUPS_BANK      ; PU_AMMO
                dw L1_CITYPICKUPS_ADDR
                db CITYPICKUPS_AMMO_FIRST
                db L1_HUDICON_BANK          ; PU_MEDKIT
                dw L1_HUDICON_ADDR
                db HUDICON_HEART_FIRST
                db L1_HUDICON_BANK          ; PU_COIN
                dw L1_HUDICON_ADDR
                db HUDICON_COIN_FIRST
                db L1_HUDICON_BANK          ; PU_IDOL
                dw L1_HUDICON_ADDR
                db HUDICON_IDOL_FIRST
                db L1_HUDICON_BANK          ; PU_BOOK
                dw L1_HUDICON_ADDR
                db HUDICON_BOOK_FIRST
ENT_ART_KINDS   equ 6

; ---------------------------------------------------------------------
; ENT_BAKE - composite every pickup into the map, once.
;
; Called by MAP_INSTALL, after the map and the table are in place and
; while the level's art banks still hold what LEVEL_LOAD put there.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
ENT_BAKE:       xor  a
                ld   (ENT_BAKED),a
                ld   a,(ENT_COUNT)
                or   a
                ret  z
                ld   b,a
                ld   hl,ENT_TABLE
.next:          push bc
                push hl
                call ENT_BAKE_ONE
                pop  hl
                ld   de,ENT_STRIDE
                add  hl,de
                pop  bc
                ld   a,(ENT_BAKED)
                cp   ENT_BAKE_MAX
                jr   nc,.full               ; out of scratch tiles: the rest
                djnz .next                  ; stay invisible rather than
.full:          jp   BANK_RESTORE           ; overwrite someone else's art

; ---------------------------------------------------------------------
; ENT_BAKE_ONE - HL = a record. Bakes it if it is a pickup that is
; still on the ground and has art; does nothing otherwise.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
ENT_BAKE_ONE:   ld   a,(hl)
                cp   EK_PICKUP
                ret  nz
                push hl                     ; the record, for the list
                ld   de,ENT_FLAGS
                add  hl,de
                ld   a,(hl)
                and  EF_ACTIVE + EF_TAKEN
                cp   EF_ACTIVE
                jr   nz,.no                 ; gone, or never there
                inc  hl
                ld   a,(hl)                 ; p0 = PU_*
                cp   ENT_ART_KINDS
                jr   nc,.no                 ; a kind with no art
                ld   (ENT_PU),a

                ; ---- the map cell it stands on ----------------------
                pop  hl
                push hl
                call ENT_CELL_OF            ; -> HL = the map byte
                ld   (ENT_CELLP),hl
                ld   a,(hl)
                ld   (ENT_WAS),a            ; what was there before

                ; ---- its cel, copied out of the art bank ------------
                ; It cannot be composited in place: the art is in C7 and
                ; the tile is in C4, and both are the SAME &4000 window.
                ld   a,(ENT_PU)
                add  a,a
                add  a,a                    ; * ENT_ART_BYTES
                add  a,ENT_ART AND 255
                ld   l,a
                ld   h,ENT_ART >> 8
                ld   c,(hl)                 ; bank
                inc  hl
                ld   e,(hl)
                inc  hl
                ld   d,(hl)                 ; DE = the blob
                inc  hl
                ld   a,(hl)                 ; its first cel - cel 0 of the
                ld   b,&7F                  ; animation, see the note above
                out  (c),c
                add  a,a
                ld   l,a
                ld   h,0
                add  hl,de
                ld   a,(hl)                 ; the offset is relative, so a
                inc  hl                     ; blob can be loaded anywhere
                ld   h,(hl)
                ld   l,a
                add  hl,de
                call ENT_FRAME_COPY

                ; ---- its own copy of the tile, with it drawn on -----
                call BANK_SET_C4
                ld   a,(ENT_BAKED)
                call ENT_SLOT_ADDR          ; -> HL = the scratch tile
                ld   (ENT_TILEP),hl
                ex   de,hl
                ld   a,(ENT_WAS)
                call ENT_TILE_ADDR          ; -> HL = the map's own tile
                ld   bc,TILE_BYTES
                ldir
                ld   hl,ENT_FRAME_BUF
                call ENT_STAMP

                ; ---- and the map points at it ----------------------
                ld   a,(ENT_BAKED)
                ld   hl,(ENT_CELLP)
                add  a,ENT_BAKE_TILE0
                ld   (hl),a

                ; ---- remember how to undo it -----------------------
                ld   a,(ENT_BAKED)
                call ENT_LIST_ADDR          ; -> HL = its row in the list
                ex   de,hl
                pop  hl                     ; the record
                push hl
                ex   de,hl
                ld   (hl),e
                inc  hl
                ld   (hl),d
                inc  hl
                ld   de,(ENT_CELLP)
                ld   (hl),e
                inc  hl
                ld   (hl),d
                inc  hl
                ld   a,(ENT_WAS)
                ld   (hl),a
                ld   hl,ENT_BAKED
                inc  (hl)
.no:            pop  hl
                ret

; ---------------------------------------------------------------------
; ENT_CELL_OF - HL = a record -> HL = the map byte it stands on.
;
; The map byte for (col, row) is MAP_ADDR + row * 128 + col, which is
; the same address TILE_SRC builds from a character cell - MAP_W is
; 128, so the row is the top of the low byte and the column is the rest.
;                                destroys AF,BC,DE
; ---------------------------------------------------------------------
ENT_CELL_OF:    inc  hl
                ld   c,(hl)                 ; x, world pixels
                inc  hl
                ld   b,(hl)
                inc  hl
                ld   e,(hl)                 ; y, the BASE of the box
                srl  b
                rr   c
                srl  b
                rr   c
                srl  b
                rr   c                      ; x >> 3 = the map column
                ld   a,c
                and  MAP_COL_MASK
                ld   c,a
                ld   a,e
                sub  PICKUP_H               ; the record anchors the BASE
                rrca
                rrca
                rrca
                rrca
                and  MAP_ROW_MASK           ; (y - 16) >> 4 = the map row
                rrca                        ; -> (row&1)<<7 | row>>1
                ld   h,a
                and  &80
                ld   l,a
                ld   a,h
                and  7
                add  a,MAP_ADDR >> 8
                ld   h,a
                ld   a,l
                add  a,c                    ; l is 0 or 128 and c < 128
                ld   l,a
                ret

; ---------------------------------------------------------------------
; ENT_TILE_ADDR - A = tile index -> HL = its bytes in the paged bank.
; ENT_SLOT_ADDR - A = scratch slot -> HL = its scratch tile.
; ENT_LIST_ADDR - A = scratch slot -> HL = its row of the bake list.
;                                destroys AF,DE
; ---------------------------------------------------------------------
ENT_TILE_ADDR:  rrca                        ; -> (t&3)<<6 | t>>2
                rrca
                ld   h,a
                and  &C0
                ld   l,a
                ld   a,h
                and  &3F
                add  a,TILES_ADDR >> 8
                ld   h,a
                ret

ENT_SLOT_ADDR:  rrca
                rrca
                ld   h,a
                and  &C0
                ld   l,a
                ld   a,h
                and  &3F
                add  a,ENT_BAKE_ADDR >> 8
                ld   h,a
                ret

ENT_LIST_ADDR:  ld   h,0
                ld   l,a
                add  hl,hl                  ; * 4 ...
                add  hl,hl
                ld   d,0
                ld   e,a
                add  hl,de                  ; ... + 1 = * 5
                ld   de,ENT_BAKE_LIST
                add  hl,de
                ret

; ---------------------------------------------------------------------
; ENT_FRAME_COPY - HL = a span frame in the paged bank, copied to
; ENT_FRAME_BUF so it can be read with a different bank in the window.
;
; It walks the format to find the end rather than copying a fixed
; block, because the last blob in a bank has nothing after it to read.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
ENT_FRAME_COPY: ld   de,ENT_FRAME_BUF
                ldi                         ; y0
                ldi                         ; lines stored
.group:         ld   a,(hl)                 ; nlines
                ldi
                or   a
                ret  z                      ; 0 ends the frame
                ld   c,a                    ; C = lines in this group
                ld   a,(hl)                 ; count
                ldi
                ldi                         ; dskip, low and high
                ldi
                or   a
                jr   z,.group               ; blank lines carry no bytes
                ld   b,a
.row:           push bc
.pair:          ldi                         ; mask
                ldi                         ; data
                djnz .pair
                pop  bc
                dec  c
                jr   nz,.row
                jr   .group

; ---------------------------------------------------------------------
; ENT_STAMP - composite the frame at HL over the tile at (ENT_TILEP).
;
;       tile offset = (byte >> 1) * 32 + line * 2 + (byte AND 1)
;
; which is the column-major layout of CLAUDE.md 9 written the other way
; round: the blitters READ it a character column at a time, and this is
; the one place that WRITES it. Bank C4 must be paged in.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
ENT_STAMP:      ld   a,(hl)
                inc  hl
                ld   (ENT_LINE),a           ; y0 - the box line its first
                inc  hl                     ; stored line sits on
                xor  a
                ld   (ENT_SKIP),a           ; the deltas are cumulative
.group:         ld   a,(hl)                 ; nlines
                inc  hl
                or   a
                ret  z
                ld   (ENT_NL),a
                ld   a,(hl)                 ; count
                inc  hl
                ld   (ENT_CNT),a
                ld   e,(hl)                 ; dskip, signed - only the low
                inc  hl                     ; byte can matter across a box
                inc  hl                     ; four bytes wide
                or   a                      ; A is still the count
                jr   z,.blank               ; SPAN_BLANK steps past the delta
                ld   a,(ENT_SKIP)           ; without adding it, so this must
                add  a,e                    ; too, or the two drawers would
                ld   (ENT_SKIP),a           ; disagree the day one is not 0
.lines:         call ENT_STAMP_LINE
                ld   a,(ENT_LINE)
                inc  a
                ld   (ENT_LINE),a
                ld   a,(ENT_NL)
                dec  a
                ld   (ENT_NL),a
                jr   nz,.lines
                jr   .group
.blank:         ld   a,(ENT_LINE)           ; a run of empty lines still
                ld   b,a                    ; moves the line counter on
                ld   a,(ENT_NL)
                add  a,b
                ld   (ENT_LINE),a
                jr   .group

; HL = this line's mask/data pairs; returns HL past them.
ENT_STAMP_LINE: ld   a,(ENT_SKIP)
                ld   c,a                    ; C = the byte inside the box
                ld   a,(ENT_CNT)
                ld   b,a
.byte:          push bc
                push hl
                ld   a,c
                srl  a                      ; its character column, 0 or 1
                add  a,a
                add  a,a
                add  a,a
                add  a,a
                add  a,a                    ; * 32
                ld   e,a
                ld   a,c
                and  1                      ; which of that column's bytes
                add  a,e
                ld   e,a
                ld   a,(ENT_LINE)
                add  a,a                    ; line * 2
                add  a,e
                ld   e,a
                ld   d,0
                ld   hl,(ENT_TILEP)
                add  hl,de
                ex   de,hl                  ; DE = the byte in the tile
                pop  hl
                push hl
                ld   a,(de)
                and  (hl)                   ; mask: set where the tile shows
                inc  hl
                or   (hl)                   ; SCREEN = (SCREEN AND MASK) OR DATA
                ld   (de),a
                pop  hl
                inc  hl
                inc  hl
                pop  bc
                inc  c
                djnz .byte
                ret

; ---------------------------------------------------------------------
; ENT_SETTLE - a pickup that was just taken stops being scenery.
;
; Called at the end of ENT_UPDATE. The map byte goes back to the tile
; that was under it and the four character cells it covered are
; repainted - about 3,440 T, once, on the frame it is taken.
;
; The repaint is not gated against the raster. It changes four cells
; that are being changed anyway, and the worst a badly timed one can do
; is show half a key for one frame.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
ENT_SETTLE:     ld   a,(ENT_RESULT)
                or   a
                ret  z                      ; nothing happened this frame
                ld   hl,(ENT_HIT)
                ld   de,ENT_FLAGS
                add  hl,de
                ld   a,(hl)
                and  EF_TAKEN
                ret  z                      ; it is still on the ground
                ld   a,(ENT_BAKED)
                or   a
                ret  z
                ld   b,a
                xor  a
.find:          push af
                push bc
                call ENT_LIST_ADDR
                ld   e,(hl)
                inc  hl
                ld   d,(hl)                 ; DE = the record it baked
                ld   bc,(ENT_HIT)
                ld   a,e
                cp   c
                jr   nz,.no
                ld   a,d
                cp   b
                jr   z,.found
.no:            pop  bc
                pop  af
                inc  a
                djnz .find
                ret                         ; it was never baked
.found:         inc  hl
                ld   e,(hl)
                inc  hl
                ld   d,(hl)                 ; DE = its map cell
                inc  hl
                ld   a,(hl)                 ; ... and what was under it
                ex   de,hl
                ld   (hl),a
                pop  bc
                pop  af
                ; AND THE SCREEN IS REPAINTED AT THE END OF THE FRAME,
                ; NOT HERE. ENT_SETTLE runs in the logic phase, with
                ; Kara still drawn and her save-under holding the BAKED
                ; tile; repainting the cell now puts the new tiles down
                ; and her erase then puts the pickup straight back over
                ; the twelve bytes she overlapped. The loop calls
                ; ENT_REPAINT_DUE once she is off the screen, next to
                ; ENEMY_REFRESH and for the same reason.
                ld   (ENT_RP_DUE),hl
                ret

; ---------------------------------------------------------------------
; ENT_REPAINT_DUE - the cell a taken pickup left behind, if there is one.
; Call at the END of the frame, after every sprite has been erased.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
ENT_REPAINT_DUE:
                ld   hl,(ENT_RP_DUE)
                ld   a,h
                or   l
                ret  z
                ld   de,0
                ld   (ENT_RP_DUE),de
                ; fall through with HL = the map cell
; ---------------------------------------------------------------------
; ENT_CELL_REPAINT - HL = a map byte. Repaints the four character cells
; it covers, if they are on the display.
;                                destroys AF,BC,DE,HL
; ---------------------------------------------------------------------
ENT_CELL_REPAINT:
                ld   a,l
                and  MAP_COL_MASK
                add  a,a
                ld   (ENT_RP_WC),a          ; world character column
                ld   a,h
                sub  MAP_ADDR >> 8
                add  a,a                    ; (h - &A0) * 2 = row AND NOT 1
                ld   c,a
                ld   a,l
                rlca                        ; bit 7 of l is the row's bit 0
                and  1
                or   c
                add  a,a
                ld   (ENT_RP_WR),a          ; world character row

                ld   a,(ENT_RP_WC)
                ld   c,a
                ld   a,(WORLD_X)
                neg
                add  a,c                    ; screen character column
                cp   SCR_CHARS - 1
                ret  nc                     ; it or its partner is off
                ld   c,a
                ld   a,(ENT_RP_WR)
                ld   b,a
                ld   a,(WORLD_CR)
                neg
                add  a,b                    ; screen character row
                cp   SCR_CHAR_ROWS - 1
                ret  nc
                ld   b,a

                ld   hl,(SCROLL)            ; word index of the top-left cell
                ld   d,0
                ld   e,c
                add  hl,de
                inc  b
                dec  b
                jr   z,.at
                ld   de,SCR_CHARS
.down:          add  hl,de
                djnz .down
.at:            ld   (ENT_RP_WORD),hl

                call BANK_SET_C4
                ld   b,0                    ; B = row within the tile, 0-1
.row:           ld   c,0                    ; C = column within it, 0-1
.col:           push bc
                ld   hl,(ENT_RP_WORD)
                ld   a,b
                or   a
                jr   z,.same
                ld   de,SCR_CHARS
                add  hl,de
.same:          ld   d,0
                ld   e,c
                add  hl,de
                ld   (CELL_WORD),hl
                ld   a,(ENT_RP_WC)
                add  a,c
                ld   (CELL_WC),a
                ld   a,(ENT_RP_WR)
                add  a,b
                ld   (CELL_WR),a
                call DRAW_CELL
                pop  bc
                inc  c
                ld   a,c
                cp   TILE_CHAR_COLS
                jr   c,.col
                inc  b
                ld   a,b
                cp   2                      ; a tile is two character rows
                jr   c,.row
                jp   BANK_RESTORE

ENT_PU:         db 0
ENT_WAS:        db 0
ENT_LINE:       db 0
ENT_SKIP:       db 0
ENT_NL:         db 0
ENT_CNT:        db 0
ENT_BAKED:      db 0            ; scratch tiles in use
ENT_CELLP:      dw 0
ENT_TILEP:      dw 0
ENT_RP_WC:      db 0
ENT_RP_WR:      db 0
ENT_RP_WORD:    dw 0
ENT_RP_DUE:     dw 0            ; a cell waiting to be repainted
ENT_BAKE_LIST:  ds ENT_BAKE_MAX * ENT_BAKE_STRIDE
