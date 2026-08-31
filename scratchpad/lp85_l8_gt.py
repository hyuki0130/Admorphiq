import sys
from pathlib import Path
from collections import deque
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import Adapter
arcade=Arcade(operation_mode=OperationMode.OFFLINE); env=arcade.make("lp85"); obs=env.observation_space
game=None
for n in dir(env):
    try: v=getattr(env,n)
    except: continue
    if hasattr(v,"current_level"): game=v;break
adapter=Adapter(); steps=0
while steps<10000 and obs.levels_completed<7:
    if adapter.is_done([],obs): break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
    steps+=1
name=game.ucybisahh; rings=game.uopmnplcnv[name]
foot=[]
for s in game.current_level._sprites:
    if s.tags and "button" in s.tags[0]:
        p=s.tags[0].split("_")
        if len(p)==3: foot.append((s.y,s.x+2,s.width,s.height,p[1]))
def rp(row,col): return frozenset(rid for (br,bc,w,h,rid) in foot if br<=row<br+h and bc<=col<bc+w)
def succ_of(rid):
    r=rings[rid];m=r['qcmzcjocmj'];mx=r['oxbwsencfv']
    if mx<=1: return {}
    byn={n:(p.y,p.x) for n,p in m.items()}
    return {byn[n]:byn[1 if n==mx else n+1] for n in byn}
actions={}
for (br,bc,w,h,rid) in foot:
    rs=rp(br,bc); mp={}
    for r in rs: mp.update(succ_of(r))
    actions[(br,bc)]=mp
def coarse(v): return v//3
lvl=game.current_level
goals=tuple(sorted((coarse(s.y),coarse(s.x)) for s in lvl.get_sprites_by_tag("goal")))
dests=frozenset((coarse(s.y+1),coarse(s.x+1)) for s in lvl.get_sprites_by_tag("bghvgbtwcb"))
def ap(st,mp): return tuple(sorted(mp.get(c,c) for c in st))
seen={goals};q=deque([(goals,0)]);found=None
while q:
    st,d=q.popleft()
    if frozenset(st)==dests: found=d;break
    if d>=60: continue
    for cell,mp in actions.items():
        nx=ap(st,mp)
        if nx not in seen: seen.add(nx);q.append((nx,d+1))
    if len(seen)>5_000_000: print("cap",len(seen));break
print(f"L8 forward-only GT solution length: {found}")
print(f"ring sizes: {[(rid,r['oxbwsencfv']) for rid,r in rings.items()]}")
print(f"goals={goals} dests={sorted(dests)}")
