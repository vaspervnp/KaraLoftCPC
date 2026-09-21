"""Direct T-state measurement for the CPC build.
loses the 40 framebuffer rows the emulator paints as colour 0 in vblank."""
import sys, os, re
sys.path.insert(0,"/home/vasilhs/cpcemu")
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from cpc import CPC
from cpcboot import past_intro
ROOT="/home/vasilhs/repos/KaraLoftCPC"
STUB=0x9000; SPIN=STUB+4

def symbols():
    d={}
    for l in open(f"{ROOT}/build/game.sym"):
        m=re.match(r"^(\S+) #([0-9A-F]+) ",l)
        if m: d[m.group(1)]=int(m.group(2),16)
    return d

def boot(sym, scroll=False, disc=None):
    # `disc` is for the suites that have to ask what came OFF the disc
    # rather than what the build put in the binary: a level's map, its
    # entity table and its tile flags are raw sectors now
    # (src/unpack.asm), so the only way to prove they travelled is to
    # boot a disc with different ones on it.
    m=CPC(); m.run_frames(150)
    m.insert_disc(os.path.abspath(disc or f"{ROOT}/build/kara.dsk")); m.type_text('RUN"DISC\n'); m.run_frames(400)
    # THE TITLE SCREEN IS IN THE WAY NOW, and it waits for a key rather
    # than a timer (CLAUDE.md 7.7). past_intro presses it; without this
    # every suite below measures a machine sitting on a still picture.
    past_intro(m, sym)
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

def sync(m, sym, half=0):
    """Step to the instant after VSYNC - the one where the last frame's
    work is finished and the next has not begun.

    THERE ARE TWO OF THEM A GAME FRAME NOW. The loop waits for two
    VSYNCs (CLAUDE.md 9): the first half draws her and thinks, the
    second erases her and puts the background right. Both spin in
    WAIT_VSYNC, and a sampler that took whichever it reached first got
    one frame with her on the screen and the next without - which reads
    as a sprite that is sometimes there and sometimes not, in a test
    that is about tiles. FRAME_HALF is the engine saying which, for the
    benefit of exactly this function; half=0 is the top of the loop,
    where she is erased and the background is finished.
    """
    lo,hi=sym["WAIT_VSYNC"],sym["WAIT_VSYNC.WAIT"]+6
    fh=sym.get("FRAME_HALF")
    for _ in range(80000):
        m.run_us(4)
        if lo<=m.pc<=hi and (fh is None or m.peek(fh)==half): return

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
