import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
import admorphiq.adapters25.lp85 as L
from admorphiq.adapters25.base import state_name
from admorphiq.kernels import find_regions, plan_token_assignment

orig_detect=L.Adapter._detect
def pdet(self,grid):
    ok=orig_detect(self,grid)
    if self._levels_seen==5: self._multipress=False
    return ok
L.Adapter._detect=pdet

orig_bp=L.Adapter._build_plan
def pbp(self,grid):
    ops={k:v for k,v in self._ops.items() if len(v)>=2}
    lattice=set()
    for mp in ops.values():
        for c in (*mp.keys(),*mp.values()): lattice.add(c)
    regions=find_regions(grid,background=self._bg)
    movers=L._detect_movers(regions,self._marker_colors)
    print(f"  _build_plan: ops={list(ops.keys())} sizes={[len(v) for v in ops.values()]}")
    print(f"    lattice size={len(lattice)}")
    print(f"    movers({len(movers)})={movers}")
    print(f"    dests({len(self._dests)})={self._dests}")
    if movers and len(movers)==len(self._dests):
        latl=list(lattice)
        toks=[L._snap(c,latl) for _cl,c in movers]
        gls=[L._snap(c,latl) for _cl,c in self._dests]
        print(f"    snapped tokens={toks}")
        print(f"    snapped goals ={gls}")
        # is each goal token even ON a learned ring?
        for _cl,c in movers:
            on=[k for k,v in ops.items() if c in v or c in v.values()]
            sn=L._snap(c,latl)
            on_s=[k for k,v in ops.items() if sn in v or sn in v.values()]
            print(f"    mover {c} snap {sn}: on rings(raw)={on} on rings(snap)={on_s}")
    r=orig_bp(self,grid)
    print(f"    -> _build_plan returned {r}, plan len {len(self._plan)}")
    return r
L.Adapter._build_plan=pbp

arcade=Arcade(operation_mode=OperationMode.OFFLINE)
env=arcade.make("lp85"); obs=env.observation_space
adapter=L.Adapter(); steps=0
while steps<6000 and obs.levels_completed<5:
    if adapter.is_done([],obs): break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
    steps+=1
for i in range(200):
    if obs.levels_completed>=6: print("CLEARED"); break
    if adapter.is_done([],obs): print(f"done at {i}"); break
    a=adapter.choose_action([],obs)
    obs=env.step(a,data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
