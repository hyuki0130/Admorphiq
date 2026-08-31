import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import Adapter
from admorphiq.adapters25.base import state_name
arcade = Arcade(operation_mode=OperationMode.OFFLINE)
env = arcade.make("lp85"); obs=env.observation_space
adapter=Adapter(); steps=0
# drive to L6
while steps<6000 and obs.levels_completed<5:
    if adapter.is_done([],obs): break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
    steps+=1
print(f"reached L6 at step {steps}, levels={obs.levels_completed}")
# now trace planner on L6
last=None
go_count=0
for i in range(400):
    if obs.levels_completed>=6:
        print(f"*** L6 CLEARED at trace step {i} ***"); break
    st=state_name(obs)
    ph=adapter._phase; act=adapter._planner_active
    tag=(ph,act,len(adapter._mp_rings),adapter._mp_scan_idx,adapter._mp_ring_idx,len(adapter._mp_frames),len(adapter._mp_ops),len(adapter._plan),st,obs.levels_completed)
    if tag!=last:
        print(f" step{i}: phase={ph} active={act} rings={len(adapter._mp_rings)} scan={adapter._mp_scan_idx} ring_idx={adapter._mp_ring_idx} frames={len(adapter._mp_frames)} ops={len(adapter._mp_ops)} plan={len(adapter._plan)} state={st} lvl={obs.levels_completed}")
        last=tag
    if st=="GAME_OVER": go_count+=1
    if adapter.is_done([],obs):
        print(f" is_done at trace step {i}, phase={ph} active={act}"); break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: print("obs None"); break
print(f"GAME_OVER count during L6: {go_count}")
print(f"final mp_rings sizes: {[len(rc) for _b,rc in adapter._mp_rings]}")
print(f"final mp_ops keys: {list(adapter._mp_ops.keys())}  plan len {len(adapter._plan)}")
