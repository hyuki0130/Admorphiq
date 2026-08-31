import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import Adapter, _detect_buttons, _planner_background
from admorphiq.adapters25.base import canonical_layer, click_action
from admorphiq.kernels import find_regions
arcade = Arcade(operation_mode=OperationMode.OFFLINE)
env = arcade.make("lp85"); obs=env.observation_space
game=None
for n in dir(env):
    try: v=getattr(env,n)
    except: continue
    if hasattr(v,"current_level"): game=v;break
adapter=Adapter(); steps=0
while steps<6000 and obs.levels_completed<5:
    if adapter.is_done([],obs): break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
    steps+=1
a=click_action(x=0,y=0); obs=env.step(a,data=a.action_data.model_dump())
lvl=game.current_level
# button sprites: tag button_<id>_<L|R>, position (x,y) sprite coords -> render (row=y,col=x+2)
btns={}
for s in lvl._sprites:
    if s.tags and "button" in s.tags[0]:
        parts=s.tags[0].split("_")
        if len(parts)==3:
            rid,d=parts[1],parts[2]
            btns.setdefault(rid,{})[d]=(s.y, s.x+2, s.width, s.height)  # render row,col
need=['A','D','G','3','13','24','25','26','27']
print("=== buttons needed by the 14-press plan ===")
for rid in need:
    print(f"  ring {rid}: {btns.get(rid)}")
# detected button regions
grid=canonical_layer(obs); bg=_planner_background(grid); regions=find_regions(grid,background=bg)
det=_detect_buttons(regions)
print(f"\n#detected button cells={len(det)}: {sorted(det)}")
# total distinct button sprites
print(f"\ntotal ring ids with buttons: {len(btns)}")
allpos=[]
for rid,dd in btns.items():
    for d,(r,c,w,h) in dd.items():
        allpos.append((r,c,rid,d))
print(f"total button sprites: {len(allpos)}")
# how many detected cells land inside a button sprite footprint?
def near(cell):
    r,c=cell; best=None
    for rid,dd in btns.items():
        for d,(br,bc,w,h) in dd.items():
            if br<=r<br+h and bc<=c<bc+w: return f"{rid}_{d}"
    return None
for cell in sorted(det):
    print(f"  det {cell} -> sprite {near(cell)}")
