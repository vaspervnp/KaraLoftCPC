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
                ; THE CITY'S AGENT, A SENTRY (8.27): 24 x 64, drawn
                ; COMPILED - one cel, the aim, in each facing - and it
                ; keeps its post. Through the span blitter it was 35,000
                ; T a cel and no level could place one. Its blob IS the
                ; code, so the cel fields only time the shot: the aim is
                ; its loop, and the shot's cel is the art's own, which
                ; is where CITYAGENT_SPAWNS puts the round.
                db L1_CITYAGENTC_BANK
                dw L1_CITYAGENTC_ADDR
                db L1_CITYAGENTC_L_BANK
                dw L1_CITYAGENTC_L_ADDR
                db CITYAGENT_FIRE_FIRST, 1
                db CITYAGENT_FIRE_FIRST + 1, 1
                db CITYAGENT_BOX_W, CITYAGENT_BOX_H
                db 0, 45, 3     ; it does not move, a shot, hit points
                dw CITYAGENT_DURATION
                dw CITYAGENT_SPAWNS
                db EN_FIXED + EN_COMPILED, 0
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
                db 0, 0          ; it shoots and it flies: kind 0, no bite
                ds EN_T_STRIDE - EN_T_USED  ; its shot leaves the box's nose

                ; THE FOREST'S SNIPER, a sentry like the agent: placed
                ; in level 5 through the span blitter it held the loop at
                ; 84 of 200 standing and 67 running (8.27).
                db L2_FORESTSNIPERC_BANK
                dw L2_FORESTSNIPERC_ADDR
                db L2_FORESTSNIPERC_L_BANK
                dw L2_FORESTSNIPERC_L_ADDR
                db FORESTSNIPER_FIRE_FIRST, 1
                db FORESTSNIPER_FIRE_FIRST + 1, 1
                db FORESTSNIPER_BOX_W, FORESTSNIPER_BOX_H
                db 0, 45, 3
                dw FORESTSNIPER_DURATION
                dw FORESTSNIPER_SPAWNS
                db EN_FIXED + EN_COMPILED, 0
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
                db 0, 0          ; it shoots and it flies: kind 0, no bite
                ds EN_T_STRIDE - EN_T_USED
                ; THE CAVE'S BAT (8.24): 16 x 16 pixels, `fly` and
                ; `swoop`, and the first character in the game that
                ; BITES - its "shot" is the swoop, a charge at her side
                ; (src/melee.asm). One of her rounds brings it down.
                db L3_CAVEBATS_BANK
                dw L3_CAVEBATS_ADDR
                db L3_CAVEBATS_L_BANK
                dw L3_CAVEBATS_L_ADDR
                db CAVEBATS_FLY_FIRST, CAVEBATS_FLY_COUNT
                db CAVEBATS_SWOOP_FIRST, CAVEBATS_SWOOP_COUNT
                db CAVEBATS_BOX_W, CAVEBATS_BOX_H
                db 2, 45, 1     ; speed, frames between swoops, hit points
                dw CAVEBATS_DURATION
                dw 0
                db EN_MELEE, 8  ; it bites, for a drone's round
                ds EN_T_STRIDE - EN_T_USED

                ; THE FOREST'S WOLF: 32 x 24, `run` and `attack`, on the
                ; ground it was put on. It keeps its distance and lunges.
                db L2_FORESTWOLF_BANK
                dw L2_FORESTWOLF_ADDR
                db L2_FORESTWOLF_L_BANK
                dw L2_FORESTWOLF_L_ADDR
                db FORESTWOLF_RUN_FIRST, FORESTWOLF_RUN_COUNT
                db FORESTWOLF_ATTACK_FIRST, FORESTWOLF_ATTACK_COUNT
                db FORESTWOLF_BOX_W, FORESTWOLF_BOX_H
                db 2, 35, 2     ; speed, frames between lunges, hit points
                dw FORESTWOLF_DURATION
                dw 0
                db EN_MELEE + EN_GROUND, 8
                ds EN_T_STRIDE - EN_T_USED

                ; ... AND THE BOAR, "heavier": slower to charge, harder
                ; to stop, and it costs her two cells of the bar.
                db L2_FORESTBOAR_BANK
                dw L2_FORESTBOAR_ADDR
                db L2_FORESTBOAR_L_BANK
                dw L2_FORESTBOAR_L_ADDR
                db FORESTBOAR_CHARGE_FIRST, FORESTBOAR_CHARGE_COUNT
                db FORESTBOAR_ATTACK_FIRST, FORESTBOAR_ATTACK_COUNT
                db FORESTBOAR_BOX_W, FORESTBOAR_BOX_H
                db 2, 50, 3     ; speed, frames between charges, hit points
                dw FORESTBOAR_DURATION
                dw 0
                db EN_MELEE + EN_GROUND, 16
                ds EN_T_STRIDE - EN_T_USED
                ; THE DESERT'S MERCENARY AND THE STATION'S GUARD, sentries
                ; as the agent is. Their sheets are the agent's shape - 12
                ; by 64, FIRE at cel 4, and cels 4 and 5 held 9 and 4 -
                ; so they time the shot off CITYAGENT_DURATION rather than
                ; costing six bytes each of a table that says the same
                ; (tools/test_sentries.py reads all three).
                db L5_DESERTMERCENARYC_BANK
                dw L5_DESERTMERCENARYC_ADDR
                db L5_DESERTMERCENARYC_L_BANK
                dw L5_DESERTMERCENARYC_L_ADDR
                db CITYAGENT_FIRE_FIRST, 1
                db CITYAGENT_FIRE_FIRST + 1, 1
                db CITYAGENT_BOX_W, CITYAGENT_BOX_H
                db 0, 45, 3
                dw CITYAGENT_DURATION
                dw DESERTMERCENARY_SPAWNS
                db EN_FIXED + EN_COMPILED, 0
                ds EN_T_STRIDE - EN_T_USED

                db L6_STATIONCYBERC_BANK
                dw L6_STATIONCYBERC_ADDR
                db L6_STATIONCYBERC_L_BANK
                dw L6_STATIONCYBERC_L_ADDR
                db CITYAGENT_FIRE_FIRST, 1
                db CITYAGENT_FIRE_FIRST + 1, 1
                db CITYAGENT_BOX_W, CITYAGENT_BOX_H
                db 0, 40, 4     ; the guard takes a round more
                dw CITYAGENT_DURATION
                dw STATIONCYBER_SPAWNS
                db EN_FIXED + EN_COMPILED, 0
                ds EN_T_STRIDE - EN_T_USED

                ; THE STATION'S WALL TURRET: 16 x 16, `scan` and `fire`,
                ; a sentry that is small enough for the span blitter. Its
                ; scan is a loop of four cels, so it is redrawn when its
                ; cel moves on and not between; it has no spawn point and
                ; its shot leaves the box's nose.
                db L6_STATIONTURRET_BANK
                dw L6_STATIONTURRET_ADDR
                db L6_STATIONTURRET_L_BANK
                dw L6_STATIONTURRET_L_ADDR
                db STATIONTURRET_SCAN_FIRST, STATIONTURRET_SCAN_COUNT
                db STATIONTURRET_FIRE_FIRST, STATIONTURRET_FIRE_COUNT
                db STATIONTURRET_BOX_W, STATIONTURRET_BOX_H
                db 0, 40, 2
                dw STATIONTURRET_DURATION
                dw 0
                db EN_FIXED, 0
                ds EN_T_STRIDE - EN_T_USED
ENEMY_TYPES_END:

; ---------------------------------------------------------------------
; EN_KIND - A = the current enemy's EN_T_KIND.   destroys AF,DE,HL
; Here and not beside melee.asm's callers because the TOP image had no
; room for it once EN_DRAW_C went there (8.27); it is base RAM either
; way, and after the table, so the table is still the whole of its page.
; ---------------------------------------------------------------------
EN_KIND:        ld   hl,(ENEMY_TYP)
                ld   de,EN_T_KIND
                add  hl,de
                ld   a,(hl)
                ret
