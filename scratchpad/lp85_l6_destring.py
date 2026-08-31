import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import Adapter,_planner_background,_scale_unit,_detect_marker_colors,_detect_dests
from admorphiq.adapters25.base import canonical_layer, click_action
from admorphiq.kernels import find_regions
import math
arcade=Arcade(operation_mode=OperationMode.OFFLINE); env=arcade.make("lp85"); obs=env.observation_space
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
unit=_scale_unit(regions,bg); solid_min=max(3,unit//2); span=max(6,3*math.isqrt(unit))
marker=_detect_marker_colors(regions,solid_min,span)
dests=[c for _cl,c in _detect_dests(regions,marker,solid_min,span)]
print("dests",dests," (uncovered one ~ (28,32))")
destbtn=(55,54)
# press dest button once, show ALL changed cells + their before/after colours, near each dest
before=np.array(canonical_layer(env.observation_space))
obs=press(destbtn)
after=np.array(canonical_layer(env.observation_space))
d=np.argwhere(before!=after)
print(f"dest-button press changed {len(d)} cells")
for dd in dests:
    near=[(int(r),int(c),int(before[r,c]),int(after[r,c])) for r,c in d if abs(r-dd[0])<=4 and abs(c-dd[1])<=4]
    print(f"  near dest {dd}: {near}")
# also full list grouped
print("all changed (r,c,before->after):", [(int(r),int(c),int(before[r,c]),int(after[r,c])) for r,c in d])
