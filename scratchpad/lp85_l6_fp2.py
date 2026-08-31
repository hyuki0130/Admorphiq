import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import Adapter
from admorphiq.adapters25.base import canonical_layer, click_action
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
lvl=game.current_level
def noop():  # inert click at letterbox corner -> re-render without state change
    a=click_action(x=0,y=0)
    return env.step(a, data=a.action_data.model_dump())
base=np.array(canonical_layer(noop()))
def footprint(s):
    ox,oy=s.x,s.y
    s.set_position(200,200)
    f2=np.array(canonical_layer(noop()))
    s.set_position(ox,oy)
    noop()
    d=np.argwhere(base!=f2)
    cols=sorted(set(int(base[r,c]) for r,c in d))
    return d,cols
for tag in ("goal","bghvgbtwcb"):
    for s in lvl.get_sprites_by_tag(tag):
        d,cols=footprint(s)
        if len(d)==0:
            print(f"  {tag} ({s.x},{s.y}): NO footprint (off-screen/occluded)")
        else:
            rs=[int(r) for r,c in d]; cs=[int(c) for r,c in d]
            print(f"  {tag} ({s.x},{s.y}): {len(d)}px rows{min(rs)}-{max(rs)} cols{min(cs)}-{max(cs)} colors={cols}")
