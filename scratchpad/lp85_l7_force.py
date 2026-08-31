import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
import admorphiq.adapters25.lp85 as L
from admorphiq.adapters25.base import state_name
# Force coupled gate to movers>=2 (to test L7). Also lower _CB_BUTTONS_MIN to 4.
orig_detect=L.Adapter._detect
def pdet(self,grid):
    ok=orig_detect(self,grid)
    if self._levels_seen==6:  # L7 only
        # recompute coupled with relaxed thresholds
        from admorphiq.kernels import find_regions
        regions=find_regions(grid,background=self._bg)
        cb=L._detect_coupled_buttons(regions,self._unit)
        movers=L._detect_movers(regions,self._marker_colors,self._solid_min)
        if self._unit==4 and len(movers)>=2 and len(cb)>=2:
            self._coupled=True; self._multipress=False; self._cb_buttons=cb
    return ok
L.Adapter._detect=pdet
# check L7 StepCounter
arcade=Arcade(operation_mode=OperationMode.OFFLINE); env=arcade.make("lp85"); obs=env.observation_space
game=None
for n in dir(env):
    try: v=getattr(env,n)
    except: continue
    if hasattr(v,"current_level"): game=v;break
adapter=L.Adapter(); steps=0
while steps<8000 and obs.levels_completed<6:
    if adapter.is_done([],obs): break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
    steps+=1
print("at L7, StepCounter:", game.toxpunyqe.current_steps, "cb_buttons will be detected")
# continue and watch for L7 clear
start=steps
for i in range(300):
    if obs.levels_completed>=7: print(f"*** L7 CLEARED! (levels={obs.levels_completed}) after {steps-start} more actions ***"); break
    if adapter.is_done([],obs): print(f"done at levels={obs.levels_completed}, phase={adapter._phase}, coupled={adapter._coupled}"); break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
    steps+=1
print(f"final levels={obs.levels_completed} coupled={adapter._coupled} cb_maps={len(adapter._cb_maps)} plan_len={len(adapter._plan)}")
