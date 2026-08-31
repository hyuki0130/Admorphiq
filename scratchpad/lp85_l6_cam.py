import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import Adapter
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
cam=game.camera
print("camera attrs:", {k:getattr(cam,k) for k in dir(cam) if not k.startswith('_') and isinstance(getattr(cam,k,None),(int,float))})
# try grid_to_display / display_to_grid on known sprite coords
for name in ("grid_to_display","display_to_grid"):
    f=getattr(cam,name,None)
    if f:
        for pt in [(9,18),(45,12),(24,45),(23,26),(29,26),(26,32)]:
            try: print(f"  {name}{pt} = {f(*pt)}")
            except Exception as e: print(f"  {name}{pt} err {e}")
# also each goal sprite: does camera expose its render bbox? print sprite pixel footprint by scanning obs frame around mapping
