import sys
from pathlib import Path
from collections import deque
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import Adapter
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
lvl=game.current_level; name=game.ucybisahh
rings=game.uopmnplcnv[name]
# build successor maps in coarse (y,x): for each ring, R: num n -> cell of n+1
succ={}  # (rid,'R'/'L') -> {cell:cell}
for rid,r in rings.items():
    m=r['qcmzcjocmj']; mx=r['oxbwsencfv']
    if mx<=1: continue
    byn={n:(p.y,p.x) for n,p in m.items()}
    R={}; L={}
    for n,cell in byn.items():
        nn = 1 if n==mx else n+1
        pn = mx if n==1 else n-1
        R[cell]=byn[nn]; L[cell]=byn[pn]
    succ[(rid,'R')]=R; succ[(rid,'L')]=L
def coarse(v): return v//3
goals=tuple(sorted((coarse(s.y),coarse(s.x)) for s in lvl.get_sprites_by_tag("goal")))
dests=frozenset((coarse(s.y+1),coarse(s.x+1)) for s in lvl.get_sprites_by_tag("bghvgbtwcb"))
print("start goals(coarse y,x):",goals)
print("dest cells(coarse y,x):",sorted(dests))
ops=list(succ.items())
print("num ops:",len(ops))
def apply(state,mp):
    return tuple(sorted(mp.get(c,c) for c in state))
start=goals; goalset=dests
seen={start}; q=deque([(start,0)]); parent={start:None}
found=None; MAXN=4_000_000
while q:
    st,d=q.popleft()
    if frozenset(st)==goalset:
        found=(st,d); break
    if d>=60: continue
    for (name_op,mp) in ops:
        nx=apply(st,mp)
        if nx not in seen:
            seen.add(nx); parent[nx]=(st,name_op); q.append((nx,d+1))
            if len(seen)>MAXN: break
    if len(seen)>MAXN:
        print("node cap hit at",len(seen)); break
if found:
    st,d=found
    # reconstruct
    path=[]; cur=st
    while parent[cur] is not None:
        pst,op=parent[cur]; path.append(op); cur=pst
    path.reverse()
    print(f"*** SOLVED in {d} presses ***")
    print("plan ops:",path)
    from collections import Counter
    print("rings used:",Counter(op[0] for op in path))
else:
    print("NO solution within depth 60 / node cap; seen=",len(seen))
