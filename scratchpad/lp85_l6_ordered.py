import sys
from pathlib import Path
from collections import deque
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import (Adapter,_planner_background,_detect_marker_colors,
    _detect_movers,_detect_dests,_scale_unit,_cint)
from admorphiq.adapters25.base import canonical_layer, click_action
from admorphiq.kernels import find_regions, learn_successor_from_series, frame_diff
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
dests=[c for _cl,c in _detect_dests(regions,marker,solid_min,span)]
# identify dest button = single press changes cells near >=2 dest centres
def near_dest_changes(cell):
    b=canonical_layer(env.observation_space); o=press(cell); a=canonical_layer(o)
    d=frame_diff(b,a); cnt=0
    for dd in dests:
        if any(abs(int(y)-dd[0])<=4 and abs(int(x)-dd[1])<=4 for y,x in d['cells']): cnt+=1
    # undo: press same ring (size-2) once more returns? no—just leave; we re-detect goals later
    return cnt
# probe each button once to find dest button (these presses count but fine)
scores={c:near_dest_changes(c) for c in btns}
destbtn=max(btns,key=lambda c:scores[c])
print("dest-change scores:",scores,"-> dest button",destbtn)
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
# LEARN DEST BUTTON FIRST, then the rest
order=[destbtn]+[c for c in btns if c!=destbtn]
K=8; maps={}
for cell in order: maps[cell]=learn_button(cell,K)
# coverage check
lat=set()
for m in maps.values():
    for k,v in m.items(): lat.add(k);lat.add(v)
def nearest(c): return min(lat,key=lambda q:(q[0]-c[0])**2+(q[1]-c[1])**2)
for dd in dests:
    n=nearest(dd); dist=round(((n[0]-dd[0])**2+(n[1]-dd[1])**2)**.5,1)
    print(f"  dest {dd} nearest lattice {n} dist {dist}")
lat=list(lat)
def snap(c): return min(lat,key=lambda q:(q[0]-c[0])**2+(q[1]-c[1])**2)
rs=find_regions(canonical_layer(env.observation_space),background=bg)
mv=sorted(c for _cl,c in _detect_movers(rs,marker,solid_min))
g=tuple(sorted(snap(c) for c in mv)); dc=frozenset(snap(c) for c in dests)
print("goals",g,"snapped dests",sorted(dc))
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
        if o.levels_completed>lb: print("*** L6 CLEARED (ordered learn) ***");break
    else: print("NOT cleared; levels",env.observation_space.levels_completed)
