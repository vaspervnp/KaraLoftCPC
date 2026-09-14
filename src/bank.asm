; =====================================================================
; bank.asm - RAM bank switching for the &4000-&7FFF window
;
; CRITICAL: every routine in this file is assembled into the core engine
; at &0040-&3FFF, i.e. OUTSIDE the window it switches. Executing a bank
; switch from within &4000-&7FFF pulls the instruction stream out from
; under the CPU. Do not move these routines.
;
; None of these preserve BC. All preserve everything else.
; =====================================================================

BANK_SET_C4:    ld   bc,GA_PORT * 256 + RAM_CFG_C4
                out  (c),c
                ret

BANK_SET_C5:    ld   bc,GA_PORT * 256 + RAM_CFG_C5
                out  (c),c
                ret

BANK_SET_C6:    ld   bc,GA_PORT * 256 + RAM_CFG_C6
                out  (c),c
                ret

BANK_SET_C7:    ld   bc,GA_PORT * 256 + RAM_CFG_C7
                out  (c),c
                ret

BANK_RESTORE:   ld   bc,GA_PORT * 256 + RAM_CFG_BASE
                out  (c),c
                ret

; ---------------------------------------------------------------------
; BANK_SELECT - select the configuration held in A (&C0-&C7).
; IN : A = RAM configuration byte
; OUT: -            destroys BC
; ---------------------------------------------------------------------
BANK_SELECT:    ld   bc,GA_PORT * 256
                out  (c),a
                ret
