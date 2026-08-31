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
lvl=game.current_level; name=game.ucybisahh
rings=game.uopmnplcnv[name]   # {id: {"qcmzcjocmj":{num:(y,x)}, "oxbwsencfv":max}}
print(f"level={name} #ring-ids={len(rings)}")
sizes={rid:r['oxbwsencfv'] for rid,r in rings.items()}
print("ring sizes:", dict(sorted(sizes.items(), key=lambda kv:-kv[1])))
# goal & target sprite coords -> coarse (÷3)
def coarse(v): return v//3
goals=[(s.x,s.y) for s in lvl.get_sprites_by_tag("goal")]
targets=[(s.x,s.y) for s in lvl.get_sprites_by_tag("bghvgbtwcb")]
print("goals(sprite x,y):", goals)
print("targets(sprite x,y):", targets)
# For each ring, the set of coarse cells (y,x)
ring_cells={rid:{(p.y,p.x) for p in r['qcmzcjocmj'].values()} for rid,r in rings.items()}
def rings_at(cx,cy):  # coarse x,y
    return [rid for rid,cells in ring_cells.items() if (cy,cx) in cells]
for (gx,gy) in goals:
    print(f"  goal sprite({gx},{gy}) coarse({coarse(gx)},{coarse(gy)}) on rings {rings_at(coarse(gx),coarse(gy))}")
for (tx,ty) in targets:
    # goal must land at target+1 (sprite), coarse of that
    dx,dy=tx+1,ty+1
    print(f"  target sprite({tx},{ty}) dest sprite({dx},{dy}) coarse({coarse(dx)},{coarse(dy)}) on rings {rings_at(coarse(dx),coarse(dy))}")
