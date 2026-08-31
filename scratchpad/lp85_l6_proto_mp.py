import sys
from pathlib import Path
from collections import deque
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import (Adapter, _planner_background, _detect_marker_colors,
    _detect_movers, _detect_dests, _scale_unit, _cint)
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
    r,c=cell; a=click_action(x=c,y=r); return env.step(a,data=a.action_data.model_dump())
obs=press((0,0))
grid=canonical_layer(obs); bg=_planner_background(grid); regions=find_regions(grid,background=bg)
unit=_scale_unit(regions,bg); solid_min=max(3,unit//2); span=max(6,3*math.isqrt(unit))
btns=sorted(_cint(r) for r in regions if int(r['color']) in (8,14) and 8<=int(r['size'])<=40)
marker=_detect_marker_colors(regions,solid_min,span)
dests=_detect_dests(regions,marker,solid_min,span)
print("buttons",len(btns),"dests",dests)
tilemax=2*unit
def tilecells(g):
    rs=find_regions(g,background=bg)
    return {_cint(r) for r in rs if int(r['color']) not in (8,14) and int(r['size'])<=tilemax}
K=8
presses=0
maps={}
for cell in btns:
    frames=[canonical_layer(env.observation_space)]
    for _ in range(K):
        obs=press(cell); presses+=1
        frames.append(canonical_layer(obs))
    # cells = tile centroids from frame0 that ever change colour
    cells=tilecells(frames[0])
    series={}
    for (rr,cc) in cells:
        s=tuple(int(frames[t][rr][cc]) for t in range(len(frames)))
        if len(set(s))>1: series[(rr,cc)]=s
    succ,all_exact=learn_successor_from_series(series)
    maps[cell]=succ
    print(f"  button {cell}: {len(succ)} moves all_exact={all_exact} (K={K})")
print("learning presses:",presses)
# lattice + snap
lat=set()
for m in maps.values():
    for k,v in m.items(): lat.add(k);lat.add(v)
lat=list(lat)
def snap(c): return min(lat,key=lambda q:(q[0]-c[0])**2+(q[1]-c[1])**2)
rs=find_regions(canonical_layer(env.observation_space),background=bg)
mv=_detect_movers(rs,marker,solid_min)
g=tuple(sorted(snap(c) for _cl,c in mv))
dc=frozenset(snap(c) for _cl,c in dests)
print("goals",g,"dests",sorted(dc))
def ap(st,mp): return tuple(sorted(mp.get(c,c) for c in st))
seen={g};q=deque([(g,[])]);found=None
while q:
    st,p=q.popleft()
    if frozenset(st)==dc: found=p;break
    if len(p)>=45: continue
    for cell,mp in maps.items():
        nx=ap(st,mp)
        if nx not in seen: seen.add(nx);q.append((nx,p+[cell]))
    if len(seen)>3_000_000: break
print(f"plan ({len(found) if found else 0}):",found)
if found:
    lb=env.observation_space.levels_completed
    for cell in found:
        obs=press(cell); presses+=1
        if obs.levels_completed>lb: print(f"*** CLEARED! total presses={presses} ***");break
    else: print(f"NOT cleared; levels={env.observation_space.levels_completed} total presses={presses}")
