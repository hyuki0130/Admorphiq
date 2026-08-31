import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
import admorphiq.adapters25.lp85 as L
from admorphiq.adapters25.base import state_name

# Force single-press path: wrap _detect to clear multipress
orig_detect = L.Adapter._detect
def patched(self, grid):
    ok = orig_detect(self, grid)
    if self._levels_seen == 5:
        self._multipress = False   # FORCE single-press on L6 only
    return ok
L.Adapter._detect = patched

arcade = Arcade(operation_mode=OperationMode.OFFLINE)
env = arcade.make("lp85"); obs=env.observation_space
adapter=L.Adapter(); steps=0
while steps<6000 and obs.levels_completed<5:
    if adapter.is_done([],obs): break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
    steps+=1
print(f"reached L6 at {steps}")
last=None
for i in range(300):
    if obs.levels_completed>=6:
        print(f"*** L6 CLEARED at trace {i} ***"); break
    st=state_name(obs)
    tag=(adapter._phase,adapter._learn_idx,len(adapter._ops),len(adapter._plan),st,obs.levels_completed)
    if tag!=last:
        print(f" {i}: phase={adapter._phase} learn_idx={adapter._learn_idx} ops={len(adapter._ops)} plan={len(adapter._plan)} selftest_fails={adapter._selftest_fails} state={st} lvl={obs.levels_completed}")
        last=tag
    if adapter.is_done([],obs):
        print(f" is_done at {i}"); break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
print(f"final ops={list(adapter._ops.keys())} sizes={[len(v) for v in adapter._ops.values()]} plan={len(adapter._plan)}")
