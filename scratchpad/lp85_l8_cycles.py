import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
import admorphiq.adapters25.lp85 as L
arcade=Arcade(operation_mode=OperationMode.OFFLINE); env=arcade.make("lp85"); obs=env.observation_space
captured=[]
orig=L._learn_coupled_map
def cap(*a,**k):
    m=orig(*a,**k); captured.append(m); return m
L._learn_coupled_map=cap
adapter=L.Adapter(); steps=0
while steps<10000 and obs.levels_completed<7:
    if adapter.is_done([],obs): break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
    steps+=1
for i in range(250):
    if obs.levels_completed>=8 or adapter.is_done([],obs): break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
big=max(captured,key=len)
print(f"big map size={len(big)}")
# cycle decomposition
seen=set();cycles=[]
for start in big:
    if start in seen: continue
    cyc=[];cur=start
    while cur not in seen and cur in big:
        seen.add(cur);cyc.append(cur);cur=big[cur]
    cycles.append(len(cyc))
print(f"cycle lengths: {sorted(cycles,reverse=True)} (expected 16,15,14)")
# is it a bijection?
vals=list(big.values())
print(f"bijection: {len(set(vals))==len(vals)} ({len(vals)} edges, {len(set(vals))} distinct targets)")
# self-consistency: cells that are keys but not values (chain heads) and vice versa
keys=set(big);tgts=set(big.values())
print(f"heads(no predecessor)={len(keys-tgts)} tails(no successor)={len(tgts-keys)}")
