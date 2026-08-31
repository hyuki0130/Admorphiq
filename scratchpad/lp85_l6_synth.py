import sys
from pathlib import Path
from collections import deque
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import (Adapter,_planner_background,_detect_marker_colors,
    _detect_movers,_detect_dests,_scale_unit,_cint)
from admorphiq.adapters25.base import canonical_layer, click_action
from admorphiq.kernels import find_regions, frame_diff
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
WILD=-99
def goal_occ(g):
    rs=find_regions(g,background=bg); occ=set()
    for r in rs:
        if int(r['color']) in marker and int(r['size'])>=solid_min:
            for (y,x) in r['cells']: occ.add((int(y),int(x)))
    return occ
def learn_synth(cell,K):
    frames=[canonical_layer(env.observation_space)]; occ=[goal_occ(frames[0])]
    for _ in range(K):
        o=press(cell); f=canonical_layer(o); frames.append(f); occ.append(goal_occ(f))
    rs0=find_regions(frames[0],background=bg)
    cells=[_cint(r) for r in rs0 if int(r['color']) not in (8,14) and int(r['size'])<=tilemax]
    series={}
    for (rr,cc) in cells:
        s=[]
        for t in range(len(frames)):
            occl=any((rr+dy,cc+dx) in occ[t] for dy in(-1,0,1) for dx in(-1,0,1))
            s.append(WILD if occl else int(frames[t][rr][cc]))
        if len(set(v for v in s if v!=WILD))>1: series[(rr,cc)]=tuple(s)
    # SYNTH: best-score bijection (like learn_successor_from_series) but WILD samples don't vote
    cs=list(series); edges=[]
    for a in cs:
        sa=series[a]
        for b in cs:
            if b==a: continue
            sb=series[b]
            good=sum(1 for t in range(1,len(sb)) if sb[t]!=WILD and sa[t-1]!=WILD and sb[t]==sa[t-1])
            bad =sum(1 for t in range(1,len(sb)) if sb[t]!=WILD and sa[t-1]!=WILD and sb[t]!=sa[t-1])
            if good>0: edges.append((good-2*bad,good,a,b))  # penalize mismatch, don't veto
    edges.sort(key=lambda e:(-e[0],-e[1]))
    succ={};used=set()
    for scr,good,a,b in edges:
        if a in succ or b in used or scr<=0: continue
        succ[a]=b; used.add(b)
    return succ
def near_dest(cell):
    b=canonical_layer(env.observation_space);o=press(cell);a=canonical_layer(o)
    d=frame_diff(b,a);return sum(1 for dd in dests if any(abs(int(y)-dd[0])<=4 and abs(int(x)-dd[1])<=4 for y,x in d['cells']))
sc={c:near_dest(c) for c in btns}; destbtn=max(btns,key=lambda c:sc[c])
order=[destbtn]+[c for c in btns if c!=destbtn]
K=8; maps={c:learn_synth(c,K) for c in order}
print("map sizes:",{c:len(m) for c,m in maps.items()})
lat=set()
for m in maps.values():
    for k,v in m.items(): lat.add(k);lat.add(v)
lat=list(lat)
def snap(c): return min(lat,key=lambda q:(q[0]-c[0])**2+(q[1]-c[1])**2)
rs=find_regions(canonical_layer(env.observation_space),background=bg)
mv=sorted(c for _cl,c in _detect_movers(rs,marker,solid_min))
g=tuple(sorted(snap(c) for c in mv)); dc=frozenset(snap(c) for c in dests)
for dd in dests:
    n=snap(dd);print(f"  dest {dd}->{n} d={round(((n[0]-dd[0])**2+(n[1]-dd[1])**2)**.5,1)}")
print("goals",g,"dests",sorted(dc))
def ap(st,mp): return tuple(sorted(mp.get(c,c) for c in st))
seen={g};q=deque([(g,[])]);found=None
while q:
    st,p=q.popleft()
    if frozenset(st)==dc: found=p;break
    if len(p)>=30: continue
    for cell,mp in maps.items():
        nx=ap(st,mp)
        if nx not in seen: seen.add(nx);q.append((nx,p+[cell]))
    if len(seen)>3_000_000: break
print(f"plan({len(found) if found else 0}):",found)
if found:
    lb=env.observation_space.levels_completed
    for cell in found:
        o=press(cell)
        if o.levels_completed>lb: print("*** L6 CLEARED (synth learn) ***");break
    else: print("NOT cleared; levels",env.observation_space.levels_completed)
