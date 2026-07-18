"""Verify movable-9 hrel shift under a REAL vertical collision, and confirm the
pixel-based collision model (sparse cross moves free unless a bar crosses the
obstacle). Get the frame col-overlapping the obstacle and above it, push DOWN,
log hrel + frame each push."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter, _l5_movables, _station_boxes
from admorphiq.adapters25.base import canonical_layer
A = {1:GameAction.ACTION1,2:GameAction.ACTION2,3:GameAction.ACTION3,4:GameAction.ACTION4,5:GameAction.ACTION5}
def marker(g):
    for r,row in enumerate(g):
        for c,v in enumerate(row):
            if v==0: return (r,c)
def get(g,sb):
    for m in _l5_movables(g,set(),sb,subtract_boxes=False):
        if m["color"]==9: return m
def st(m):
    cs=set(m["cells"]); rs=[r for r,_ in cs]; cc=[c for _,c in cs]
    r0,r1,c0,c1=min(rs),max(rs),min(cc),max(cc); h,w=r1-r0+1,c1-c0+1
    vc=[c for c in range(c0,c1+1) if sum((r,c) in cs for r in range(r0,r1+1))>=h*0.7]
    hr=[r for r in range(r0,r1+1) if sum((r,c) in cs for c in range(c0,c1+1))>=w*0.7]
    return r0,r1,c0,c1,(vc[len(vc)//2] if vc else c0),(hr[len(hr)//2] if hr else r0)
def sel(env,sb,obs):
    for _ in range(12):
        g=canonical_layer(obs);mk=marker(g);m=get(g,sb)
        if m and mk and abs(m["cen"][0]-mk[0])<=15 and abs(m["cen"][1]-mk[1])<=15: return obs
        obs=env.step(A[5])
    return obs
ar=Arcade(operation_mode=OperationMode.OFFLINE);env=ar.make("re86");ad=Adapter(giveup=8000)
obs=env.observation_space;steps=0
while steps<2500 and int(getattr(obs,'levels_completed',0) or 0)<5 and not ad.is_done([],obs):
    a=ad.choose_action([],obs);obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a);steps+=1
for _ in range(3): obs=env.step(A[5])
g=canonical_layer(obs);_s,sb=_station_boxes(g)
dm=dict(ad._dir_global)
up=next(a for a,s in dm.items() if s==(-1,0));down=next(a for a,s in dm.items() if s==(1,0))
left=next(a for a,s in dm.items() if s==(0,-1));right=next(a for a,s in dm.items() if s==(0,1))
obs=sel(env,sb,obs)
# move to col-overlap (cols ~15-39) while staying above obstacle (rows 3-27): move left freely
for _ in range(20):
    g=canonical_layer(obs);m=get(g,sb);r0,r1,c0,c1,va,ha=st(m)
    if c0<=15: break
    obs=env.step(A[left])
g=canonical_layer(obs);m=get(g,sb);print(f"pos: {st(m)} (r0,r1,c0,c1,vbar_abs,hbar_abs)")
print("-- push DOWN (expect: free translate until hbar hits obstacle row 28, then hrel shift) --")
prev=None
for k in range(14):
    obs=env.step(A[down]);g=canonical_layer(obs);m=get(g,sb)
    if m is None: print(f"  D{k+1}: GONE"); continue
    r0,r1,c0,c1,va,ha=st(m); hrel=ha-r0; vrel=va-c0
    s=f"frame r{r0}-{r1} c{c0}-{c1} vbar_abs={va}(vrel{vrel}) hbar_abs={ha}(hrel{hrel})"
    if s!=prev: print(f"  D{k+1}: {s}"); prev=s
