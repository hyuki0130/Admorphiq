import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import Adapter,_planner_background,_scale_unit,_detect_marker_colors,_detect_movers,_detect_dests,_cint
from admorphiq.adapters25.base import canonical_layer, click_action
from admorphiq.kernels import find_regions
import math
# drive through each level, at each level-start settle + report filtered button count + unit
arcade=Arcade(operation_mode=OperationMode.OFFLINE); env=arcade.make("lp85"); obs=env.observation_space
adapter=Adapter()
def report(obs,lvl):
    a=click_action(x=0,y=0); obs2=env.step(a,data=a.action_data.model_dump())
    g=canonical_layer(obs2); bg=_planner_background(g); rs=find_regions(g,background=bg)
    unit=_scale_unit(rs,bg); solid_min=max(3,unit//2); span=max(6,3*math.isqrt(unit))
    fb=[_cint(r) for r in rs if int(r['color']) in (8,14) and 2*unit<=int(r['size'])<=10*unit]
    marker=_detect_marker_colors(rs,solid_min,span)
    mv=_detect_movers(rs,marker,solid_min); de=_detect_dests(rs,marker,solid_min,span)
    print(f"L{lvl+1}: unit={unit} filtered_buttons={len(fb)} movers={len(mv)} dests={len(de)}")
    return obs2
seen=-1; steps=0
while steps<6000 and obs.levels_completed<6:
    if obs.levels_completed!=seen:
        seen=obs.levels_completed
        obs=report(obs,seen)
    if adapter.is_done([],obs): break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
    steps+=1
