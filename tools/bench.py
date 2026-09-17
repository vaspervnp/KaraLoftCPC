"""Direct T-state measurement for the CPC build.
loses the 40 framebuffer rows the emulator paints as colour 0 in vblank."""
import sys, os, re
sys.path.insert(0,"/home/vasilhs/cpcemu")
from cpc import CPC
ROOT="/home/vasilhs/repos/KaraLoftCPC"
STUB=0x9000; SPIN=STUB+4

def symbols():
    d={}
    for l in open(f"{ROOT}/build/game.sym"):
        m=re.match(r"^(\S+) #([0-9A-F]+) ",l)
        if m: d[m.group(1)]=int(m.group(2),16)
    return d

def boot(sym, scroll=False):
    m=CPC(); m.run_frames(150)
    m.insert_disc(os.path.abspath(f"{ROOT}/build/kara.dsk")); m.type_text('RUN"DISC\n'); m.run_frames(400)
    if scroll:
        # WAIT FOR THE LEVEL, DO NOT COUNT FRAMES. LEVEL_LOAD is 1.4 s
        # with interrupts off (CLAUDE.md 7.5); a fixed 40-frame wait put
        # every measurement inside the disc read, with the map and the
        # entity table still unwritten under it.
        #
        # There is only one screen now - RUN"DISC goes straight to the
        # rooftop - so `scroll` no longer picks between two of them, it
        # only says whether to wait for the level to arrive.
        for _ in range(200):
            m.run_frames(2)
            if m.peek(sym["LEVEL_OK"]):
                m.run_frames(4)         # ... and let SCROLL_INIT finish
                break
    return m

def sync(m, sym):
    lo,hi=sym["WAIT_VSYNC"],sym["WAIT_VSYNC.WAIT"]+6
    for _ in range(40000):
        m.run_us(4)
        if lo<=m.pc<=hi: return

def raw(m, target):
    m.write_ram(STUB, bytes([0xF3,0xCD,target&0xFF,target>>8,0x18,0xFE])); m.set_pc(STUB)
    for us in range(1,400000):
        m.run_us(1)
        if m.pc==SPIN: return us
    return None

class Bench:
    def __init__(self, m, sym):
        self.m, self.sym = m, sym
        sync(m, sym); m.poke(0x9100,0xC9)
        self.base = raw(m, 0x9100)
    def T(self, name, setup=None):
        sync(self.m, self.sym)
        if setup: setup(self.m)
        us = raw(self.m, self.sym[name])
        return None if us is None else (us-self.base)*4
