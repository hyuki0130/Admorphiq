import sys
from pathlib import Path
from collections import deque
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import (Adapter, _planner_background, _detect_buttons,
    _detect_marker_colors, _detect_movers, _detect_dests, _scale_unit, _cint)
from admorphiq.adapters25.base import canonical_layer, click_action
from admorphiq.kernels import find_regions, frame_diff
import math

def drive_to_l6():
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    env = arcade.make("lp85"); obs=env.observation_space
    adapter=Adapter(); steps=0
    while steps<6000 and obs.levels_completed<5:
        if adapter.is_done([],obs): break
        a=adapter.choose_action([],obs)
        obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        if obs is None: break
        steps+=1
    a=click_action(x=0,y=0); obs=env.step(a,data=a.action_data.model_dump())
    return env,obs

def press(env,cell):
    r,c=cell; a=click_action(x=c,y=r)
    return env.step(a,data=a.action_data.model_dump())

env,obs=drive_to_l6()
grid=canonical_layer(obs)
bg=_planner_background(grid); regions=find_regions(grid,background=bg)
# 7 real buttons: color 8/14 regions with size >= 8 (drops HUD size-4) and not the size-64 bar
btns=sorted(_cint(r) for r in regions if int(r['color']) in (8,14) and 8<=int(r['size'])<=40)
print("filtered buttons:",btns, "count",len(btns))
unit=_scale_unit(regions,bg); solid_min=max(3,unit//2); span=max(6,3*math.isqrt(unit))
marker=_detect_marker_colors(regions,solid_min,span)
movers=_detect_movers(regions,marker,solid_min); dests=_detect_dests(regions,marker,solid_min,span)
print("marker",sorted(marker),"movers",movers,"dests",dests)

def tiles(g):  # small non-button colored regions -> {cell:color}
    rs=find_regions(g,background=bg)
    return {_cint(r):int(r['color']) for r in rs if int(r['color']) not in (8,14) and int(r['size'])<=2*unit}

# learn each button's direct permutation via single press + colour match (multi-cycle allowed)
def learn(env,cell):
    g0=canonical_layer(obs if False else canonical_layer.__self__ if False else env.observation_space)
    before=env.observation_space
    b=canonical_layer(before)
    tb=tiles(b)
    ob=press(env,cell)
    a=canonical_layer(ob)
    ta=tiles(a)
    d=frame_diff(b,a)
    moved=set((int(y),int(x)) for y,x in d['cells'])
    # cells (tile centroids) that are in moved area
    bc={c:col for c,col in tb.items()}
    ac={c:col for c,col in ta.items()}
    # map before-cell -> after-cell of same colour, nearest, as bijection over moved tiles
    src=[c for c in bc if any(abs(c[0]-m[0])<=1 and abs(c[1]-m[1])<=1 for m in moved)]
    dst=[c for c in ac if any(abs(c[0]-m[0])<=1 and abs(c[1]-m[1])<=1 for m in moved)]
    succ={}; used=set()
    # greedy: for each src, nearest same-colour dst not equal to itself
    for s in sorted(src):
        cands=sorted([t for t in dst if ac[t]==bc[s] and t not in used],
                     key=lambda t:(t[0]-s[0])**2+(t[1]-s[1])**2)
        for t in cands:
            if t!=s:
                succ[s]=t; used.add(t); break
    return succ, ob

# learn all 7
maps={}
for cell in btns:
    m,obs2=learn(env,cell)
    globals()['obs']=obs2
    maps[cell]=m
    print(f"  button {cell}: learned {len(m)} cell-moves")

# BFS goals->dests over learned maps (goal cells snapped to lattice)
lattice=set()
for m in maps.values():
    for k,v in m.items(): lattice.add(k); lattice.add(v)
lattice=list(lattice)
def snap(c): return min(lattice,key=lambda q:(q[0]-c[0])**2+(q[1]-c[1])**2)
gcells=tuple(sorted(snap(c) for _cl,c in movers))
dcells=frozenset(snap(c) for _cl,c in dests)
print("snapped goals",gcells,"dests",sorted(dcells))
def ap(st,mp): return tuple(sorted(mp.get(c,c) for c in st))
seen={gcells};q=deque([(gcells,[])]);found=None
while q:
    st,p=q.popleft()
    if frozenset(st)==dcells: found=p;break
    if len(p)>=40: continue
    for cell,mp in maps.items():
        nx=ap(st,mp)
        if nx not in seen: seen.add(nx);q.append((nx,p+[cell]))
    if len(seen)>2_000_000: break
print("plan found:",found if found else f"NONE (seen {len(seen)})")

# ---- VERIFY: re-detect goals post-learning, re-plan, execute, check win ----
print("\n=== VERIFY with post-learning state ===")
def curstate():
    g=canonical_layer(env.observation_space); rs=find_regions(g,background=bg)
    mv=_detect_movers(rs,marker,solid_min)
    return mv
mv2=curstate()
print("post-learn movers:",mv2)
g2=tuple(sorted(snap(c) for _cl,c in mv2))
seen={g2};q=deque([(g2,[])]);found2=None
while q:
    st,p=q.popleft()
    if frozenset(st)==dcells: found2=p;break
    if len(p)>=40: continue
    for cell,mp in maps.items():
        nx=ap(st,mp)
        if nx not in seen: seen.add(nx);q.append((nx,p+[cell]))
    if len(seen)>2_000_000: break
print(f"post-learn plan ({len(found2) if found2 else 0}):",found2)
lvl_before=env.observation_space.levels_completed
if found2:
    for cell in found2:
        ob=press(env,cell)
        if ob.levels_completed>lvl_before:
            print(f"*** L6 CLEARED! levels {lvl_before}->{ob.levels_completed} ***"); break
    else:
        print(f"plan executed, levels now {env.observation_space.levels_completed} (was {lvl_before}) - NOT cleared")
