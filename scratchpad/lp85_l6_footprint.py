import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import Adapter
from admorphiq.adapters25.base import canonical_layer
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
base=np.array(canonical_layer(obs))
def render_now():
    # re-fetch obs frame after a no-op? Instead, use camera to render level directly
    # fall back: use game to produce a frame. Try game.render or camera.render
    for m in ("render","_render","get_frame","observe"):
        f=getattr(game,m,None) or getattr(game.camera,m,None)
        if f:
            try:
                out=f(lvl) if 'level' in getattr(f,'__code__',type('x',(),{'co_varnames':()})).co_varnames else f()
                return np.array(out)
            except Exception:
                pass
    return None
# Identify render footprint of each goal/target by hiding it: temporarily shift far away
def footprint(sprite):
    ox,oy=sprite.x,sprite.y
    # move off-board
    sprite.set_position(500,500)
    f2=render_now()
    sprite.set_position(ox,oy)
    if f2 is None: return None
    diff=np.argwhere(base!=f2)
    return diff, sorted(set(int(base[r,c]) for r,c in diff))
rn=render_now()
print("render_now works:", rn is not None, None if rn is None else rn.shape)
if rn is not None:
    print("render_now matches obs frame:", bool((rn==base).all()))
for tag in ("goal","bghvgbtwcb"):
    for s in lvl.get_sprites_by_tag(tag):
        fp=footprint(s)
        if fp is None:
            print(f"  {tag} ({s.x},{s.y}): render_now unavailable"); continue
        diff,cols=fp
        if len(diff)==0:
            print(f"  {tag} ({s.x},{s.y}): NO render footprint (occluded/off-screen)")
        else:
            rs=[int(r) for r,c in diff]; cs=[int(c) for r,c in diff]
            print(f"  {tag} ({s.x},{s.y}): {len(diff)}px rows {min(rs)}-{max(rs)} cols {min(cs)}-{max(cs)} colors={cols}")
