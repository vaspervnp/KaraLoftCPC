; =====================================================================
; sentry.asm - the enemies that keep a POST (CLAUDE.md 8.27): the City's
; agent, the forest's sniper, the desert's mercenary and the station's
; cyber guard, which are 24x64 and drawn COMPILED, and the station's
; wall turret, which is 8x16 and is not.
;
; A 24x64 character through the span blitter is 35,000 T a cel drawn and
; 11,000 erased, and a second sweep that has to carry it on every frame
; does not hold: placed in level 5 where the wolf is, the loop was 84 of
; 200 standing and 67 running. tools/compile_sprite.py turns a cel into
; the code that draws it - every mask and data byte an immediate - and
; that is 15,500 to 19,700 T, writing the same pixels and the same erase
; script byte for byte (tools/test_sentries.py). What it costs is room:
; four and a half times the span record. So a facing is TWO cels, the aim
; and the recoil, and only the aim is compiled whole: the recoil is a
; TOGGLE over it, 3,000 to 4,000 T, which is what lets a sentry be seen
; to fire (the blob's own layout is tools/compile_sprite.py's).
;
; TWO BITS OF EN_T_KIND, beside melee.asm's two:
;
;   EN_FIXED     it keeps its post. Its speed is 0, so the patrol moves
;                it nowhere; it is never ENGAGED, so the follow never
;                takes it and the next enemy can come after it; it goes
;                down where it stands; and it is REDRAWN ONLY WHEN
;                SOMETHING ABOUT IT CHANGES - its cel, its facing, it
;                leaving the window - because a sprite that does not move
;                is world-fixed and the CRTC carries its pixels for
;                nothing (8.7). What could spoil them is kept away from
;                it: her save-under puts back what she drew over, the
;                rounds are not drawn in its keep-out (ROUND_HIDDEN), the
;                trap painter waits for it (HZ_UNDER_IT), and the tools
;                place no pickup and no trap under one.
;   EN_COMPILED  its blobs ARE the cels' code, one a facing, and the draw
;                jumps to them (EN_DRAW_C). A new facing is a redraw; a
;                new CEL is not - the blob toggles the one on the screen
;                into the other, and EN_STILL sends it there past the lift
;                (ENEMY_KEEP, in ENEMY_REFRESH).
;
; WHERE A COMPILED CEL IS DRAWN IS A PROMISE THE LEVEL MAKES. The code
; steps along a line with INC E and down one with ADD 8 to D, so no line
; of its box may cross a 256-byte page of video RAM - and a world
; character (X, R) is ALWAYS at word 40R + X of the ring, because SCROLL
; starts as WORLD_CR * 40 + WORLD_X and every scroll step moves the three
; together (8.1). A sentry does not move, so the map tools check its box
; once (compile_sprite.page_safe) and the engine never has to.
; =====================================================================
EN_FIXED        equ 4           ; EN_T_KIND: it keeps its post
EN_COMPILED     equ 8           ; ... and its blobs are the cel's code

; ---------------------------------------------------------------------
; EN_STILL - CARRY if the enemy ENEMY_REFRESH is about to redraw is a
; sentry already on the screen exactly as it would draw it - or a sentry
; whose change can wait for a slot at the top of the sweep, because the
; end of one is where she stands over it, and a redraw there has no
; deadline (8.7). No carry: redraw it. The carry is the answer because
; AND, OR and XOR clear it, so every test below can return on its own
; flag.                                   destroys AF,C,DE,HL,IX
; ... and a THIRD answer, which is not a return: a compiled sentry whose
; cel alone has changed is sent on into ENEMY_REFRESH past its lift.
;
; The slot is told by the LOW byte of its address: they are ES_STRIDE
; apart and 24 of them never span 256.
; ---------------------------------------------------------------------
EN_STILL:       ld   a,(ENEMY_DREW)
                or   a
                ret  z                      ; nothing of it up there
                ld   a,(ENEMY_VIS)
                or   a
                ret  z                      ; it has left the window: lift it
                ld   a,(ENEMY_CUR)
                ld   hl,EN_DREW_SLOT
                xor  (hl)
                ret  nz                     ; another one is up there
                call EN_KIND
                ld   c,a
                and  EN_FIXED
                ret  z                      ; one that moves: every frame
                ld   ix,(ENEMY_CUR)
                ld   a,(ix + ES_DIE)
                or   a
                ret  nz                     ; going down: it flashes
                ld   a,(ENEMY_EARLY)
                cp   1
                ret  c                      ; the end of the sweep: not now
                ld   a,(EN_DREW_FACE)
                xor  (ix + ES_FACE)
                ret  nz                     ; it has turned
                ld   a,(EN_DREW_CEL)
                xor  (ix + ES_CEL)
                scf
                ret  z                      ; the same cel
                bit  3,c                    ; EN_COMPILED?
                ccf
                ret  z                      ; no: redraw it
                ; A COMPILED ONE CHANGES CEL WITHOUT BEING LIFTED. Its two
                ; cels are the aim and the recoil, the screen holds the
                ; other one exactly, and the blob turns it into this one
                ; with the background its first draw saved (the TOGGLE,
                ; tools/compile_sprite.py) - so ENEMY_REFRESH is resumed
                ; past its lift and past the line that empties the script.
                pop  hl
                jp   ENEMY_KEEP

; ---------------------------------------------------------------------
; EN_DRAW_C - ENEMY_REFRESH's draw for a COMPILED sentry (src/sentry.asm,
; CLAUDE.md 8.27). DE = the blob, its bank paged in, and the blob IS the
; cels' code, which wants its own address in BC: a blob is placed by the
; allocator after it is compiled, so it reaches its toggle as an offset
; from that. Jumped to, so the RET that ends the cel's code is
; BANK_RESTORE's, and BANK_RESTORE's RET is ENEMY_REFRESH's. Here and
; not in the core, which needed its 20 bytes for HZ_PEND_ADD's reject.
; ---------------------------------------------------------------------
EN_DRAW_C:      ld   hl,BANK_RESTORE
                push hl
                push de                     ; ... after the cel
                push de                     ; ... which has to know where it
                ld   a,(ENEMY_SX)           ; is to reach its own toggle
                ld   c,a
                ld   a,(ENEMY_SY)
                call SCR_ADDR               ; its box's top-left, which the
                ex   de,hl                  ; level put on a character row
                pop  bc                     ; BC = the blob
                ld   hl,ENEMY_SCRIPT
                ret
