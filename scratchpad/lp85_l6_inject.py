import sys
from pathlib import Path
from collections import deque
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
dests0=[c for _cl,c in _detect_dests(regions,marker,solid_min,span)]
def tilecells(g):
    rs=find_regions(g,background=bg)
    return {_cint(r) for r in rs if int(r['color']) not in (8,14) and int(r['size'])<=tilemax}
def learn_button(cell,K):
    frames=[canonical_layer(env.observation_space)]
    for _ in range(K):
        o=press(cell); frames.append(canonical_layer(o))
    cells=tilecells(frames[0]); series={}
    for (rr,cc) in cells:
        s=tuple(int(frames[t][rr][cc]) for t in range(len(frames)))
        if len(set(s))>1: series[(rr,cc)]=s
    succ,ae=learn_successor_from_series(series); return succ
K=8; maps={}
for cell in btns: maps[cell]=learn_button(cell,K)
# --- INJECT: build lattice, then for the dest button, learn dest-ring edges by
# pressing it and watching the GOAL (color 11) move (goals are visible tracers). ---
lat=set()
for m in maps.values():
    for k,v in m.items(): lat.add(k);lat.add(v)
# find which button controls the dests: the one whose learned cells are nearest to dests on avg
def buttoncov(cell):
    m=maps[cell]; c=0
    for d in dests0:
        if any(abs(k[0]-d[0])<=3 and abs(k[1]-d[1])<=3 for k in list(m)+list(m.values())): c+=1
    return c
destbtn=max(btns,key=buttoncov)
print("dest button:",destbtn,"coverage",buttoncov(destbtn))
# learn the dest button's effect on GOALS directly: press it, track color-11 solids
def goals_now():
    rs=find_regions(canonical_layer(env.observation_space),background=bg)
    return sorted(c for _cl,c in _detect_movers(rs,marker,solid_min))
# augment destbtn map with goal-observed edges over several presses
gmap=dict(maps[destbtn])
gb=goals_now()
for _ in range(6):
    o=press(destbtn); ga=goals_now()
    # match nearest before->after among goals that moved
    for b in gb:
        cand=sorted(ga,key=lambda a:(a[0]-b[0])**2+(a[1]-b[1])**2)
        if cand and cand[0]!=b and ((cand[0][0]-b[0])**2+(cand[0][1]-b[1])**2)<= (2*unit)**2:
            gmap[b]=cand[0]
    gb=ga
maps[destbtn]=gmap
for m in maps.values():
    for k,v in m.items(): lat.add(k);lat.add(v)
# inject dest cells
for d in dests0: lat.add(d)
lat=list(lat)
def snap(c): return min(lat,key=lambda q:(q[0]-c[0])**2+(q[1]-c[1])**2)
mv=goals_now(); g=tuple(sorted(snap(c) for c in mv)); dc=frozenset(snap(c) for c in dests0)
print("goals",g,"dests",sorted(dc), "presses so far ~", 56+6)
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
print(f"plan({len(found) if found else 0}):",found)
if found:
    lb=env.observation_space.levels_completed
    for cell in found:
        o=press(cell)
        if o.levels_completed>lb: print("*** L6 CLEARED via inject ***");break
    else: print("executed, NOT cleared; levels",env.observation_space.levels_completed)
