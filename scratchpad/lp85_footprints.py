import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import (Adapter,_planner_background,_scale_unit,_detect_coupled_buttons,_cint)
from admorphiq.adapters25.base import canonical_layer, click_action
from admorphiq.kernels import find_regions, frame_diff
import math
def measure_level(target):
    arcade=Arcade(operation_mode=OperationMode.OFFLINE); env=arcade.make("lp85"); obs=env.observation_space
    adapter=Adapter(); steps=0
    while steps<10000 and obs.levels_completed<target:
        if adapter.is_done([],obs): break
        a=adapter.choose_action([],obs)
        obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        if obs is None: break
        steps+=1
    if obs.levels_completed<target: return None
    a=click_action(x=0,y=0); obs=env.step(a,data=a.action_data.model_dump())
    g=canonical_layer(obs); bg=_planner_background(g); rs=find_regions(g,background=bg)
    unit=_scale_unit(rs,bg); tilemax=2*unit
    btns=_detect_coupled_buttons(rs,unit)
    def press(cell):
        r,c=cell;aa=click_action(x=c,y=r);return env.step(aa,data=aa.action_data.model_dump())
    def tilecells(gg):
        rr=find_regions(gg,background=bg)
        return {_cint(r) for r in rr if int(r['color']) not in (8,14) and int(r['size'])<=tilemax}
    out=[]
    for cell in btns:
        before=canonical_layer(env.observation_space)
        ob=press(cell); after=canonical_layer(ob)
        d=frame_diff(before,after)
        # moved tile cells: tiles present before that are in the diff area
        tb=tilecells(before)
        moved=set((int(y),int(x)) for y,x in d['cells'])
        movedtiles=sum(1 for (rr,cc) in tb if any(abs(rr-my)<=1 and abs(cc-mx)<=1 for (my,mx) in moved))
        out.append((cell, d['count'], movedtiles))
    return out
for lvl,name in [(5,"L6"),(6,"L7"),(7,"L8")]:
    res=measure_level(lvl)
    if res is None: print(f"{name}: not reached"); continue
    print(f"{name}: buttons and (diff_px, moved_tiles):")
    for cell,px,mt in res:
        print(f"   {cell}: diff_px={px} moved_tiles={mt}")
