import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
import admorphiq.adapters25.lp85 as L
arcade=Arcade(operation_mode=OperationMode.OFFLINE); env=arcade.make("lp85"); obs=env.observation_space
game=None
for n in dir(env):
    try: v=getattr(env,n)
    except: continue
    if hasattr(v,"current_level"): game=v;break
adapter=L.Adapter(); steps=0
captured={}
orig=L._learn_coupled_map
def cap(frames,bg,marker,solid_min,tile_max,unit):
    m=orig(frames,bg,marker,solid_min,tile_max,unit)
    captured[len(m)]=m  # key by size
    return m
L._learn_coupled_map=cap
while steps<10000 and obs.levels_completed<7:
    if adapter.is_done([],obs): break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
    steps+=1
for i in range(200):
    if obs.levels_completed>=8 or adapter.is_done([],obs): break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
# GT map for {D,E,F}
rings=game.uopmnplcnv[game.ucybisahh]
gt={}
for rid in ('D','E','F'):
    m=rings[rid]['qcmzcjocmj'];mx=rings[rid]['oxbwsencfv']
    byn={n:(p.y,p.x) for n,p in m.items()}
    for n,(cy,cx) in byn.items():
        nn=1 if n==mx else n+1;(ny,nx)=byn[nn]
        gt[(cy*3,cx*3+2)]=(ny*3,nx*3+2)
big=captured.get(44) or captured.get(45) or max(captured.items(),key=lambda kv:kv[0])[1]
print(f"learned big map size={len(big)} GT size={len(gt)}")
def near(k,mp):
    c=[m for m in mp if abs(m[0]-k[0])<=2 and abs(m[1]-k[1])<=2]
    return c[0] if c else None
match=0;tot=0;mism=[]
for k,v in big.items():
    gk=near(k,gt)
    if gk is None: continue
    tot+=1;gv=gt[gk]
    if abs(v[0]-gv[0])<=2 and abs(v[1]-gv[1])<=2: match+=1
    else: mism.append((k,v,gv))
print(f"matched {match}/{tot} vs GT; {len(mism)} wrong edges")
for m in mism[:8]: print("  wrong:",m)
