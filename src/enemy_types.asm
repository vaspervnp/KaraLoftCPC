; =====================================================================
; enemy_types.asm - the characters, one 32-byte row each (src/enemy.asm
; has the fields). In the HIGH image, at its START: HIGH_ADDR is &AA00,
; so the table begins on a page and cannot cross one until it is eight
; rows long, which ENEMY_TYPE_AT's ADD A,ENEMY_TYPES AND 255 needs and
; main.asm asserts. It was the last thing in the core's enemy code and
; cost a page's alignment there the day it grew a fourth row - the
; history is below.
; =====================================================================

; ALIGNED TO THE WHOLE TABLE, NOT TO ONE ROW. `align 32` put it at
; &17E0, its 64 bytes crossed &1800, and ADD A,ENEMY_TYPES AND 255
; wrapped: every type but the first read the first one's padding, so a
; drone was 135 lines tall with 23 hit points. The assert in main.asm is
; what keeps it from happening again as the table grows.
;
; AND `align 64` WAS NOT ENOUGH EITHER, which the third row is what
; showed: 3 * 32 is 96 bytes, and an align of 64 can put those at
; offset 192 of a page, where they end at 288. The rule in CLAUDE.md 10
; says align to the WHOLE table and this is the table's own size
; rounded up - 128 holds four rows exactly, and the assert is what will
; say so on the fifth.
;
; AND THEN `align 128` WAS TOO MUCH, which the sea is what showed. What
; the indexing needs is that the table does not CROSS a page, and an
; align is only one way to get that: every byte the code in front of it
; grows by is free until the table would cross, and then the align
; costs up to 127 bytes at once. The cable's runs took the hazard code
; five bytes past &1B00 and the core past &4000 by about a hundred. So
; it moved to the next page only when it had to - and then the fourth
; row made that 130 bytes the core had not got, so it is here now, at
; the one address in base RAM a page starts on for free.
ENEMY_TYPES:
                db L1_CITYAGENT_BANK
                dw L1_CITYAGENT_ADDR
                db L1_CITYAGENT_L_BANK
                dw L1_CITYAGENT_L_ADDR
                db CITYAGENT_WALK_FIRST, CITYAGENT_WALK_COUNT
                db CITYAGENT_FIRE_FIRST, CITYAGENT_FIRE_COUNT
                db CITYAGENT_BOX_W, CITYAGENT_BOX_H
                db 2, 45, 3     ; speed, fire period, hit points - the
                                ; first two doubled and halved for the
                                ; 25 Hz game frame (src/main.asm)
                dw CITYAGENT_DURATION
                dw CITYAGENT_SPAWNS
                ds EN_T_STRIDE - EN_T_USED

                db L1_CITYDRONE_BANK
                dw L1_CITYDRONE_ADDR
                db L1_CITYDRONE_L_BANK
                dw L1_CITYDRONE_L_ADDR
                db CITYDRONE_FLY_FIRST, CITYDRONE_FLY_COUNT
                db CITYDRONE_FIRE_FIRST, CITYDRONE_FIRE_COUNT
                db CITYDRONE_BOX_W, CITYDRONE_BOX_H
                db 2, 35, 2     ; ... and the same on this one
                dw CITYDRONE_DURATION
                dw 0                    ; the drone sheet has no spawn point:
                ds EN_T_STRIDE - EN_T_USED  ; its shot leaves the box's nose

                ; THE FOREST'S SNIPER, AND IT IS AN AGENT-CLASS SPRITE.
                ; 12x64 like the cityagent, which 8.7 measured at
                ; 40,760-48,820 T drawn and erased against a 79,872 T
                ; frame and called unaffordable - and 9 says that at
                ; 25 Hz it is affordable ON PAPER, with nothing having
                ; measured it. Placing one is that measurement.
                db L2_FORESTSNIPER_BANK
                dw L2_FORESTSNIPER_ADDR
                db L2_FORESTSNIPER_L_BANK
                dw L2_FORESTSNIPER_L_ADDR
                db FORESTSNIPER_WALK_FIRST, FORESTSNIPER_WALK_COUNT
                db FORESTSNIPER_FIRE_FIRST, FORESTSNIPER_FIRE_COUNT
                db FORESTSNIPER_BOX_W, FORESTSNIPER_BOX_H
                db 2, 45, 3     ; speed, fire period, hit points
                dw FORESTSNIPER_DURATION
                dw FORESTSNIPER_SPAWNS
                ds EN_T_STRIDE - EN_T_USED

                ; THE SEA'S SECURITY DRONE: 32 x 16 pixels "so it reads
                ; next to the 64-wide swimmers", and the City's drone's
                ; rules - it follows her once it has been on the screen -
                ; with her box the swimmer's (src/swim.asm patches what
                ; the follow takes for it). It has no spawn point: its
                ; torpedo leaves the box's nose, as the City's shot does.
                db L4_SEADRONE_BANK
                dw L4_SEADRONE_ADDR
                db L4_SEADRONE_L_BANK
                dw L4_SEADRONE_L_ADDR
                db SEADRONE_SWIM_FIRST, SEADRONE_SWIM_COUNT
                db SEADRONE_FIRE_FIRST, SEADRONE_FIRE_COUNT
                db SEADRONE_BOX_W, SEADRONE_BOX_H
                db 2, 40, 3     ; speed, fire period, hit points
                dw SEADRONE_DURATION
                dw 0
                ds EN_T_STRIDE - EN_T_USED
ENEMY_TYPES_END:
