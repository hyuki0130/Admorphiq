import sys, math
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import (Adapter, _planner_background, _scale_unit,
    _detect_buttons, _detect_marker_colors, _detect_movers, _detect_dests,
    _cluster_frame_centres, _cint)
from admorphiq.adapters25.base import canonical_layer, click_action, most_common_color
from admorphiq.kernels import find_regions
arcade = Arcade(operation_mode=OperationMode.OFFLINE)
env = arcade.make("lp85"); obs=env.observation_space
adapter=Adapter(); steps=0
while steps<6000 and obs.levels_completed<5:
    if adapter.is_done([],obs): break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
    steps+=1
# settle with an inert click
a=click_action(x=0,y=0); obs=env.step(a,data=a.action_data.model_dump())
grid=canonical_layer(obs)
from collections import Counter
cnt=Counter(v for row in grid for v in row)
print("SETTLED color counts:", dict(sorted(cnt.items())))
sym={v:('.' if v in (3,4) else format(v,'x')) for v in cnt}
for r,row in enumerate(grid):
    line="".join(sym[v] for v in row)
    if line.strip('.'):
        print(f"{r:2d} {line}")
print("\n=== DETECTION on settled frame ===")
bg=_planner_background(grid); regions=find_regions(grid,background=bg)
unit=_scale_unit(regions,bg); solid_min=max(3,unit//2); span=max(6,3*math.isqrt(unit))
print(f"bg={sorted(bg)} unit={unit} solid_min={solid_min} span={span}")
buttons=_detect_buttons(regions); marker=_detect_marker_colors(regions,solid_min,span)
movers=_detect_movers(regions,marker,solid_min); dests=_detect_dests(regions,marker,solid_min,span)
print(f"buttons={len(buttons)} marker={sorted(marker)}")
print(f"movers({len(movers)})={movers}")
print(f"dests({len(dests)})={dests}")
a2=Adapter(); ok=a2._detect(grid)
print(f"REAL _detect={ok} multipress={a2._multipress}")
# all color-11 regions
c11=sorted(((int(r['size']),_cint(r)) for r in regions if int(r['color'])==11),reverse=True)
print(f"color-11 regions({len(c11)}): {c11}")
c5=sorted(((int(r['size']),_cint(r)) for r in regions if int(r['color'])==5),reverse=True)
print(f"color-5 regions({len(c5)}): {c5}")
