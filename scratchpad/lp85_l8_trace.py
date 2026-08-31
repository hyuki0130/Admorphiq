import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
import admorphiq.adapters25.lp85 as L
from admorphiq.adapters25.base import state_name
arcade=Arcade(operation_mode=OperationMode.OFFLINE); env=arcade.make("lp85"); obs=env.observation_space
game=None
for n in dir(env):
    try: v=getattr(env,n)
    except: continue
    if hasattr(v,"current_level"): game=v;break
adapter=L.Adapter(); steps=0
while steps<10000 and obs.levels_completed<7:
    if adapter.is_done([],obs): break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
    steps+=1
print("at L8 start, StepCounter:",game.toxpunyqe.current_steps)
last=None
for i in range(400):
    if obs.levels_completed>=8: print(f"*** L8 CLEARED at trace {i} ***");break
    st=state_name(obs)
    tag=(adapter._phase,adapter._coupled,adapter._cb_idx,adapter._cb_k_current,len(adapter._cb_maps),len(adapter._plan),adapter._cb_tried,st)
    if tag!=last:
        print(f" {i}: phase={adapter._phase} coupled={adapter._coupled} cb_idx={adapter._cb_idx} K={adapter._cb_k_current} maps={len(adapter._cb_maps)} plan={len(adapter._plan)} tried={adapter._cb_tried} state={st} step={game.toxpunyqe.current_steps}")
        last=tag
    if adapter.is_done([],obs): print(f" is_done at {i}");break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
print(f"final: levels={obs.levels_completed} cb_maps sizes={[len(m) for m in adapter._cb_maps.values()]} plan={len(adapter._plan)} StepCounter={game.toxpunyqe.current_steps}")
