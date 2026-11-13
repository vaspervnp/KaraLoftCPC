; =====================================================================
; books.asm - the cave's gate and its books (CLAUDE.md 8.25). In the
; SOUND image, which is base RAM like the rest and had room: both of
; these run on a keypress or once a level, never every frame.
;
; plan.md's cave is "a puzzle with the covers of ancient books that
; opens a gate", and the artist drew it: a gate four slots wide -
; sun, moon, eye, star - a book for each symbol, the slot with its book
; in, and two stone tablets, one carved sun-and-moon and one
; eye-and-star. THE TABLET IS THE CLUE. A gate wants the two symbols of
; ONE tablet, the level shows that tablet where she comes in, and the
; level has books of all four symbols in it. The two the gate does not
; want are CURSED: picking one up costs her, and it is gone.
;
;   a book's p1     its symbol's bit - sun 1, moon 2, eye 4, star 8, the
;                   slots' order - and bit 7 if it is cursed. A good one
;                   is ORed into CURRENT_BOOK_ID, so she carries a SET;
;                   a cursed one is HURT_HER and nothing (ENT_ON_TOUCH)
;   the gate's lock an EK_RECEPTACLE whose p0 is PU_BOOK and whose p1 is
;                   the set it wants. It is the record BEFORE the door,
;                   because the interact pass stops at the first box it
;                   meets: with the books in, the lock is satisfied and
;                   taken, and the next UP finds the door
;
; IT TAKES THEM ALL AT ONCE OR NOT AT ALL, and she keeps what she offered
; when it refuses - so nothing she can do with a good book loses it, and
; the only thing the puzzle can cost her is a curse. Satisfied, it gives
; her the gate's key and HZ_SATISFIED lights its slots: the slots it
; wanted are the artist's empty ones COPIED, carrying TA_ADVANCE, with
; the slot-with-its-book at the next index (tools/make_cave_map.py), so
; they move on exactly as the forest's altar and the station's reader
; do (8.17, 8.23).
; =====================================================================
BOOK_ENV        equ 2           ; the cave, 0 based: where the books are drawn
BOOK_HURT       equ TILE_HURT   ; a curse costs what a spike does: a cell

; ---------------------------------------------------------------------
; BOOK_LOCK - UP at the gate's lock. HL -> it.
;                                destroys AF,BC,DE,HL,IX
; ---------------------------------------------------------------------
BOOK_LOCK:      push hl
                ld   bc,ENT_P1
                add  hl,bc
                ld   c,(hl)                 ; the set it wants
                pop  hl
                ld   a,(CURRENT_BOOK_ID)
                ld   b,a
                or   a
                ld   a,ER_EMPTY             ; (LD keeps the Z of the OR)
                jr   z,.say
                ld   a,b
                and  c
                cp   c
                ld   a,ER_WRONG
                jr   nz,.say                ; not every one: she keeps them all
                ld   a,b
                xor  c
                ld   (CURRENT_BOOK_ID),a    ; they go into its slots
                push hl
                ld   hl,KEYS_COUNT
                inc  (hl)                   ; ... and the gate is unlocked
                pop  hl
                ld   a,ER_PLACED
                ld   (ENT_RESULT),a
                push hl
                ld   bc,ENT_FLAGS
                add  hl,bc
                set  1,(hl)                 ; EF_TAKEN: the next UP is the door
                pop  hl
                jp   HZ_SATISFIED           ; and its slots light
.say:           ld   (ENT_RESULT),a
                ret

; BOOK_CEL's arithmetic (src/entity.asm): the four tags two cels apart,
; in the slots' order.
                assert CAVEBOOKS_BOOK_MOON_FIRST == CAVEBOOKS_BOOK_SUN_FIRST + 2
                assert CAVEBOOKS_BOOK_EYE_FIRST == CAVEBOOKS_BOOK_SUN_FIRST + 4
                assert CAVEBOOKS_BOOK_STAR_FIRST == CAVEBOOKS_BOOK_SUN_FIRST + 6
