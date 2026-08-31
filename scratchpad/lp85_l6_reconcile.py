import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import (Adapter,_planner_background,_detect_marker_colors,
    _detect_movers,_detect_dests,_scale_unit,_cint)
from admorphiq.adapters25.base import canonical_layer, click_action
from admorphiq.kernels import find_regions, learn_successor_from_series
import math
arcade=Arcade(operation_mode=OperationMode.OFFLINE); env=arcade.make("lp85"); obs=env.observation_space
adapter=Adapter(); steps=0
while steps<6000 and obs.levels_completed<5:
    if adapter.is_done([],obs): break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
    steps+=1
def press(cell):
    r,c=cell;a=click_action(x=c,y=r);return env.step(a,data=a.action_data.model_dump())
obs=press((0,0)); grid=canonical_layer(obs); bg=_planner_background(grid); regions=find_regions(grid,background=bg)
unit=_scale_unit(regions,bg); solid_min=max(3,unit//2); span=max(6,3*math.isqrt(unit)); tilemax=2*unit
btns=sorted(_cint(r) for r in regions if int(r['color']) in (8,14) and 8<=int(r['size'])<=40)
marker=_detect_marker_colors(regions,solid_min,span)
# dests + movers BEFORE any learning
dests0=_detect_dests(regions,marker,solid_min,span)
movers0=_detect_movers(regions,marker,solid_min)
print("BEFORE learning: movers",movers0)
print("BEFORE learning: dests",dests0)
def tilecells(g):
    rs=find_regions(g,background=bg)
    return {_cint(r) for r in rs if int(r['color']) not in (8,14) and int(r['size'])<=tilemax}
K=8; maps={}
for cell in btns:
    frames=[canonical_layer(env.observation_space)]
    for _ in range(K):
        obs=press(cell); frames.append(canonical_layer(obs))
    cells=tilecells(frames[0]); series={}
    for (rr,cc) in cells:
        s=tuple(int(frames[t][rr][cc]) for t in range(len(frames)))
        if len(set(s))>1: series[(rr,cc)]=s
    succ,ae=learn_successor_from_series(series); maps[cell]=succ
lat=set()
for m in maps.values():
    for k,v in m.items(): lat.add(k);lat.add(v)
lat=sorted(lat)
print(f"\nlattice size={len(lat)}")
def nearest(c,n=3):
    return sorted(lat,key=lambda q:(q[0]-c[0])**2+(q[1]-c[1])**2)[:n]
# The dests are FIXED (targets don't move). Check each dest's nearest lattice cells:
for col,dc in dests0:
    nn=nearest(dc)
    dists=[round(((q[0]-dc[0])**2+(q[1]-dc[1])**2)**.5,1) for q in nn]
    print(f"  dest {dc}: nearest lattice {nn} dists {dists}")
# which button's map contains cells near each dest?
for col,dc in dests0:
    for cell,m in maps.items():
        near=[k for k in m if abs(k[0]-dc[0])<=3 and abs(k[1]-dc[1])<=3]
        if near: print(f"    dest {dc} <- button {cell} has cells {near}")
