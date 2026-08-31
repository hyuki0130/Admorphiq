import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import Adapter
from admorphiq.adapters25.base import click_action
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
lvl=game.current_level
print("StepCounter:",game.toxpunyqe.current_steps)
foot={}
for s in lvl._sprites:
    if s.tags and "button" in s.tags[0]:
        p=s.tags[0].split("_")
        if len(p)==3: foot.setdefault(p[1],0); foot[p[1]]+=1
print("rings with a button:",sorted(foot))
rings=game.uopmnplcnv[game.ucybisahh]
print("ALL rings:",{rid:r['oxbwsencfv'] for rid,r in rings.items()})
# distinct press-sets
allf=[]
for s in lvl._sprites:
    if s.tags and "button" in s.tags[0]:
        p=s.tags[0].split("_")
        if len(p)==3: allf.append((s.y,s.x+2,s.width,s.height,p[1]))
def rp(row,col): return frozenset(rid for (br,bc,w,h,rid) in allf if br<=row<br+h and bc<=col<bc+w)
print("distinct press-sets:",sorted(set(rp(br,bc) for (br,bc,w,h,rid) in allf),key=len))
