import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import Adapter
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
rings=game.uopmnplcnv[game.ucybisahh]
# render cells per ring (coarse (y,x) -> render (y*3, x*3+2))
for rid in ('D','E','F'):
    m=rings[rid]['qcmzcjocmj']
    cells=sorted((p.y*3,p.x*3+2) for p in m.values())
    rmin=min(c[0] for c in cells);rmax=max(c[0] for c in cells)
    cmin=min(c[1] for c in cells);cmax=max(c[1] for c in cells)
    print(f"ring {rid} ({len(cells)} cells): rows {rmin}-{rmax} cols {cmin}-{cmax}")
    print(f"    cells={cells}")
