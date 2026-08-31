import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
import admorphiq.adapters25.lp85 as L
from admorphiq.kernels import find_regions, plan_token_assignment
orig=L.Adapter._cb_build_plan
def patched(self,grid):
    ops={c:m for c,m in self._cb_maps.items() if len(m)>=2}
    lat=set()
    for m in ops.values():
        for k,v in m.items(): lat.add(k);lat.add(v)
    regions=find_regions(grid,background=self._bg)
    movers=L._detect_movers(regions,self._marker_colors,self._solid_min)
    dests=L._detect_dests(regions,self._marker_colors,self._solid_min,self._span)
    print(f"  _cb_build_plan: ops sizes={[len(m) for m in ops.values()]} lattice={len(lat)}")
    print(f"    movers({len(movers)})={movers}")
    print(f"    dests({len(dests)})={dests}")
    latl=list(lat)
    def snap(c): return min(latl,key=lambda q:(q[0]-c[0])**2+(q[1]-c[1])**2)
    for cl,c in movers:
        s=snap(c); print(f"    mover {c}->snap {s} d={round(((s[0]-c[0])**2+(s[1]-c[1])**2)**.5,1)}")
    for cl,c in dests:
        s=snap(c); print(f"    dest {c}->snap {s} d={round(((s[0]-c[0])**2+(s[1]-c[1])**2)**.5,1)}")
    r=orig(self,grid)
    print(f"    -> returned {r} plan={len(self._plan)}")
    return r
L.Adapter._cb_build_plan=patched
arcade=Arcade(operation_mode=OperationMode.OFFLINE); env=arcade.make("lp85"); obs=env.observation_space
adapter=L.Adapter(); steps=0
while steps<10000 and obs.levels_completed<7:
    if adapter.is_done([],obs): break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
    steps+=1
for i in range(400):
    if obs.levels_completed>=8: print("CLEARED");break
    if adapter.is_done([],obs): break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
