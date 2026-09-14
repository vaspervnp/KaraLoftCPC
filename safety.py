import sys, os, re
sys.path.insert(0,"/home/vasilhs/cpcemu")
from cpc import CPC
ROOT=sys.argv[1]; STUB=0x8400
def symbols():
    out={}
    for line in open(os.path.join(ROOT,"build","game.sym")):
        m=re.match(r"^([A-Za-z_][A-Za-z0-9_.]*)\s+#([0-9A-Fa-f]+)",line.strip())
        if m: out[m.group(1)]=int(m.group(2),16)
    return out
sym=symbols()
c=CPC(); c.run_frames(200); c.insert_disc(os.path.join(ROOT,"build","kara.dsk"))
c.type_text('RUN"DISC\n'); c.run_frames(1100)
def call(a):
    code=bytes([0xF3,0xCD,a&0xFF,a>>8,0x18,0xFE])
    for i,b in enumerate(code): c.poke(STUB+i,b)
    c.set_pc(STUB)
    for _ in range(400000):
        c.run_us(1)
        if c.pc==STUB+4: return True
    return False
def poke16(a,v): c.poke(a,v&0xFF); c.poke(a+1,v>>8)

def straddle_scrolls(x,y):
    out=[]
    for s in range(1024):
        line=0; cr0=(y>>3)&0x1F
        while line<48:
            cr=cr0+((y&7)+line)//8
            if ((2*s+80*cr+x)&0x7FF)>=2040: out.append(s); break
            line+=8-((y+line)&7)
    return out

worst=0; total=0
for y in (112,115):
  for x in (0,1,72):
    for s in straddle_scrolls(x,y)[:6]:
        total+=1
        poke16(sym['SCROLL'],s); c.poke(sym['KARA_X'],x); c.poke(sym['KARA_Y'],y)
        c.poke(sym['KARA_FRAME'],1); poke16(sym['KARA_LAST_ADDR'],0)
        # snapshot everything that is NOT vram and NOT the save buffers
        before=bytes(c.read_ram(0x0000,0x8000))
        after_sav=bytes(c.read_ram(0x81B8,0x3E48))   # above the declared buffers
        call(sym['KARA_DRAW'])
        a1=bytes(c.read_ram(0x0000,0x8000)); a2=bytes(c.read_ram(0x81B8,0x3E48))
        d=sum(1 for i in range(0x8000) if before[i]!=a1[i])
        d+=sum(1 for i in range(len(after_sav)) if after_sav[i]!=a2[i] and (0x81B8+i)!=STUB)
        call(sym['KARA_ERASE'])
        a1=bytes(c.read_ram(0x0000,0x8000))
        d+=sum(1 for i in range(0x8000) if before[i]!=a1[i])
        worst=max(worst,d)
print(f"{total} seam draws+erases: bytes changed OUTSIDE &C000-&FFFF and outside the save buffers: worst={worst}")
