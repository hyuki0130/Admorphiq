import sys
from pathlib import Path
from collections import deque, Counter
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import Adapter, _planner_background
from admorphiq.adapters25.base import canonical_layer, click_action
from admorphiq.kernels import find_regions
arcade = Arcade(operation_mode=OperationMode.OFFLINE)
env = arcade.make("lp85"); obs=env.observation_space
game=None
for n in dir(env):
    try: v=getattr(env,n)
    except: continue
    if hasattr(v,"current_level"): game=v;break
adapter=Adapter(); steps=0
while steps<6000 and obs.levels_completed<5:
    if adapter.is_done([],obs): break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
    steps+=1
a=click_action(x=0,y=0); obs=env.step(a,data=a.action_data.model_dump())
lvl=game.current_level; name=game.ucybisahh
rings=game.uopmnplcnv[name]
# button sprites -> render, group by SHARED click cell (overlapping buttons rotate together)
btncell={}  # render (row,col) -> set of ring ids
for s in lvl._sprites:
    if s.tags and "button" in s.tags[0]:
        p=s.tags[0].split("_")
        if len(p)==3:
            key=(s.y, s.x+2)  # a representative cell; overlaps share
            btncell.setdefault((s.y,s.x+2,s.width,s.height),set()).add(p[1])
# collapse by overlapping footprint: a click at any cell inside a footprint rotates all rings whose sprite covers it
# build: press at footprint f rotates the union of rings whose sprite footprint contains f's top-left
foot=[]
for s in lvl._sprites:
    if s.tags and "button" in s.tags[0]:
        p=s.tags[0].split("_")
        if len(p)==3: foot.append((s.y,s.x+2,s.width,s.height,p[1]))
def rings_pressed(row,col):
    out=set()
    for (br,bc,w,h,rid) in foot:
        if br<=row<br+h and bc<=col<bc+w: out.add(rid)
    return frozenset(out)
# distinct press-actions = distinct ring-sets reachable by clicking each button's own cell
press_actions={}
for (br,bc,w,h,rid) in foot:
    rs=rings_pressed(br,bc)
    press_actions[(br,bc)]=rs
distinct=set(press_actions.values())
print(f"#button footprints={len(foot)}  #distinct press cells={len(press_actions)}  #distinct ring-sets={len(distinct)}")
overlaps=[rs for rs in press_actions.values() if len(rs)>1]
print(f"press cells that rotate >1 ring: {len(overlaps)}; example sets: {sorted(set(overlaps),key=len)[-5:]}")

# forward-only (R) ground-truth solve, each press = rotate a ring-SET by R
def succ_of(rid):
    r=rings[rid]; m=r['qcmzcjocmj']; mx=r['oxbwsencfv']
    if mx<=1: return {}
    byn={n:(pp.y,pp.x) for n,pp in m.items()}
    return {byn[n]:byn[1 if n==mx else n+1] for n in byn}
# an action = a press cell -> combined successor over its ring set
actions={}
for cell,rs in press_actions.items():
    mp={}
    for rid in rs:
        mp.update(succ_of(rid))  # NB overlapping rings could conflict; rare
    actions[cell]=mp
def coarse(v): return v//3
goals=tuple(sorted((coarse(s.y),coarse(s.x)) for s in lvl.get_sprites_by_tag("goal")))
dests=frozenset((coarse(s.y+1),coarse(s.x+1)) for s in lvl.get_sprites_by_tag("bghvgbtwcb"))
def apply(st,mp): return tuple(sorted(mp.get(c,c) for c in st))
seen={goals}; q=deque([(goals,0)]); par={goals:None}; found=None
while q:
    st,d=q.popleft()
    if frozenset(st)==dests: found=(st,d);break
    if d>=40: continue
    for cell,mp in actions.items():
        nx=apply(st,mp)
        if nx not in seen:
            seen.add(nx);par[nx]=(st,cell);q.append((nx,d+1))
    if len(seen)>3_000_000: print("cap");break
if found:
    st,d=found; path=[];cur=st
    while par[cur] is not None: pst,cell=par[cur];path.append(cell);cur=pst
    path.reverse()
    print(f"*** forward-only SOLVED in {d} presses ***")
    print("press cells:",path)
else:
    print("no forward-only solution within depth 40; seen=",len(seen))

# now: how many of these press cells are FRAME-DETECTABLE?
grid=canonical_layer(obs); bg=_planner_background(grid); regions=find_regions(grid,background=bg)
c814=[(int(r['size']),(round(r['centroid'][0]),round(r['centroid'][1]))) for r in regions if int(r['color']) in (8,14)]
print(f"\n#color-8/14 regions in frame={len(c814)}: sizes {Counter(s for s,_ in c814)}")
print("their cells:",sorted(c for _,c in c814))
