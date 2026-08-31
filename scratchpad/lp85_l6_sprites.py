import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import Adapter
from arcengine import GameAction

arcade = Arcade(operation_mode=OperationMode.OFFLINE)
env = arcade.make("lp85")
obs = env.observation_space
game = None
for n in dir(env):
    try: v=getattr(env,n)
    except: continue
    if hasattr(v,"current_level"): game=v;break
adapter = Adapter()
steps=0
while steps<6000 and obs.levels_completed<5:
    if adapter.is_done([],obs): break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
    steps+=1
lvl=game.current_level
print("level_name",game.ucybisahh,"grid",lvl.grid_size)
def info(s):
    col=getattr(s,'color',None)
    tags=getattr(s,'tags',None)
    return (s.x,s.y,s.width,s.height,'col=%s'%col,tags[:2] if tags else tags)
for tag in ("bghvgbtwcb","goal"):
    for s in lvl.get_sprites_by_tag(tag):
        print(f"  {tag}: {info(s)}")
# what colors do the sprites carry? check a couple tile sprites
print("--- sample non-button sprites & their colors ---")
seen=set()
for s in lvl._sprites:
    c=getattr(s,'color',None)
    t=s.tags[0] if s.tags else None
    key=(c,t)
    if t and 'button' in str(t): continue
    if key in seen: continue
    seen.add(key)
    print(f"   color={c} tag0={t} pos=({s.x},{s.y}) wh=({s.width},{s.height})")
