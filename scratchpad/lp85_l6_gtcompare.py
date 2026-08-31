import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import (Adapter,_planner_background,_detect_marker_colors,
    _detect_movers,_detect_dests,_scale_unit,_cint)
from admorphiq.adapters25.base import canonical_layer, click_action
from admorphiq.kernels import find_regions, frame_diff
import math
arcade=Arcade(operation_mode=OperationMode.OFFLINE); env=arcade.make("lp85"); obs=env.observation_space
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
def press(cell):
    r,c=cell;a=click_action(x=c,y=r);return env.step(a,data=a.action_data.model_dump())
obs=press((0,0)); grid=canonical_layer(obs); bg=_planner_background(grid); regions=find_regions(grid,background=bg)
unit=_scale_unit(regions,bg); solid_min=max(3,unit//2); span=max(6,3*math.isqrt(unit)); tilemax=2*unit
btns=sorted(_cint(r) for r in regions if int(r['color']) in (8,14) and 8<=int(r['size'])<=40)
marker=_detect_marker_colors(regions,solid_min,span)
name=game.ucybisahh; rings=game.uopmnplcnv[name]
# GT: for each button footprint, which rings; combined render-space permutation
foot=[]
for s in game.current_level._sprites:
    if s.tags and "button" in s.tags[0]:
        p=s.tags[0].split("_")
        if len(p)==3: foot.append((s.y,s.x+2,s.width,s.height,p[1]))
def rings_pressed(row,col):
    return frozenset(rid for (br,bc,w,h,rid) in foot if br<=row<br+h and bc<=col<bc+w)
def gt_map_for(cell):
    rs=rings_pressed(*cell); mp={}
    for rid in rs:
        m=rings[rid]['qcmzcjocmj']; mx=rings[rid]['oxbwsencfv']
        if mx<=1: continue
        byn={n:(p.y,p.x) for n,p in m.items()}
        for n,(cy,cx) in byn.items():
            nn=1 if n==mx else n+1; (ny,nx)=byn[nn]
            mp[(cy*3,cx*3+2)]=(ny*3,nx*3+2)   # render coords, top-left of sprite
    return mp
# learned synth maps (reuse learn_synth quickly, K=8, dest-first)
WILD=-99
def goal_occ(g):
    rs=find_regions(g,background=bg); occ=set()
    for r in rs:
        if int(r['color']) in marker and int(r['size'])>=solid_min:
            for (y,x) in r['cells']: occ.add((int(y),int(x)))
    return occ
def learn_synth(cell,K=8):
    frames=[canonical_layer(env.observation_space)]; occ=[goal_occ(frames[0])]
    for _ in range(K):
        o=press(cell); f=canonical_layer(o); frames.append(f); occ.append(goal_occ(f))
    rs0=find_regions(frames[0],background=bg)
    cells=[_cint(r) for r in rs0 if int(r['color']) not in (8,14) and int(r['size'])<=tilemax]
    series={}
    for (rr,cc) in cells:
        s=[WILD if any((rr+dy,cc+dx) in occ[t] for dy in(-1,0,1) for dx in(-1,0,1)) else int(frames[t][rr][cc]) for t in range(len(frames))]
        if len(set(v for v in s if v!=WILD))>1: series[(rr,cc)]=tuple(s)
    cs=list(series); edges=[]
    for a in cs:
        sa=series[a]
        for b in cs:
            if b==a: continue
            sb=series[b]
            good=sum(1 for t in range(1,len(sb)) if sb[t]!=WILD and sa[t-1]!=WILD and sb[t]==sa[t-1])
            bad=sum(1 for t in range(1,len(sb)) if sb[t]!=WILD and sa[t-1]!=WILD and sb[t]!=sa[t-1])
            if good>0: edges.append((good-2*bad,a,b))
    edges.sort(key=lambda e:-e[0]); succ={};used=set()
    for scr,a,b in edges:
        if a in succ or b in used or scr<=0: continue
        succ[a]=b;used.add(b)
    return succ
# compare on the 3 big-ring buttons + dest button (learn dest first)
destbtn=(55,54)
for cell in [destbtn,(28,15),(28,45),(58,30)]:
    learned=learn_synth(cell)
    gt=gt_map_for(cell)
    # gt keys are sprite TOP-LEFT; learned keys are region CENTROIDS (~top-left+0.5). match by nearest within 2px
    def near(k,mp): 
        cand=[m for m in mp if abs(m[0]-k[0])<=2 and abs(m[1]-k[1])<=2]
        return cand[0] if cand else None
    match=0; tot=0; mism=[]
    for k,v in learned.items():
        gk=near(k,gt)
        if gk is None: continue
        tot+=1; gv=gt[gk]
        if abs(v[0]-gv[0])<=2 and abs(v[1]-gv[1])<=2: match+=1
        else: mism.append((k,v,gv))
    print(f"button {cell}: learned {len(learned)} edges, GT {len(gt)}; matched-vs-GT {match}/{tot}  mism{len(mism)}")
    if mism[:3]: print("   sample mismatches (k, learned->, GT->):",mism[:3])
