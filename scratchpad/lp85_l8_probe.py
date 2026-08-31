import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import (Adapter,_planner_background,_scale_unit,_detect_marker_colors,
    _detect_movers,_detect_dests,_detect_coupled_buttons,_cint)
from admorphiq.adapters25.base import canonical_layer, click_action, state_name
from admorphiq.kernels import find_regions
import math
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
print(f"reached levels={obs.levels_completed} at step {steps} state={state_name(obs)}")
if obs.levels_completed>=7:
    a=click_action(x=0,y=0); obs=env.step(a,data=a.action_data.model_dump())  # settle
    g=canonical_layer(obs); bg=_planner_background(g); rs=find_regions(g,background=bg)
    unit=_scale_unit(rs,bg); solid_min=max(3,unit//2); span=max(6,3*math.isqrt(unit))
    marker=_detect_marker_colors(rs,solid_min,span)
    mv=_detect_movers(rs,marker,solid_min); de=_detect_dests(rs,marker,solid_min,span)
    fb=_detect_coupled_buttons(rs,unit)
    print(f"L8 SETTLED: name={game.ucybisahh} unit={unit} filtered_buttons={len(fb)} marker={sorted(marker)} movers={len(mv)} dests={len(de)}")
    print(f"  movers={mv}")
    print(f"  dests={de}")
    lvl=game.current_level
    print("  GT goal sprites:",[(s.x,s.y) for s in lvl.get_sprites_by_tag('goal')])
    print("  GT bghvgbtwcb (targets):",[(s.x,s.y) for s in lvl.get_sprites_by_tag('bghvgbtwcb')])
    print("  GT goal-o:",[(s.x,s.y) for s in lvl.get_sprites_by_tag('goal-o')])
    print("  GT fdgmtkfrxl (target-o):",[(s.x,s.y) for s in lvl.get_sprites_by_tag('fdgmtkfrxl')])
    rings=game.uopmnplcnv[game.ucybisahh]
    print("  ring sizes:",{rid:r['oxbwsencfv'] for rid,r in rings.items()})
