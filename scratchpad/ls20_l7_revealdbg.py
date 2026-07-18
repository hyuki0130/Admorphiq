"""Debug: after the static reveal, dump the revealed passable region and check
whether the mover column (x=49/54) and refill (49,5) are reachable in the
REVEALED graph, and why the frontier search terminates."""
from __future__ import annotations
import sys
from collections import deque
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.ls20 import Adapter
from admorphiq.adapters25.base import canonical_layer
from ls20_l7_v2 import Mem, parse_disc, passable_of, MOVES, A, _CELL
from ls20_l7_v4 import reveal_static, grid_of

ar = Arcade(operation_mode=OperationMode.OFFLINE)
env = ar.make("ls20")
obs_box = [env.observation_space]
g = env._game
ad = Adapter(giveup=9000)
s = 0
while s < 9000 and obs_box[0].levels_completed < 6:
    a = ad.choose_action([], obs_box[0])
    obs_box[0] = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    s += 1
mem = Mem()
ea, av = reveal_static(env, obs_box, mem, cap=250)
pss = passable_of(mem)
print("ea", ea, "final av", av, "revealed passable", len(pss))
print("revealed floor xs:", sorted({c[0] for c in pss}))
print("revealed cells with x>=44:", sorted(c for c in pss if c[0] >= 44))
walls = {c for c,t in mem.static.items() if t=="wall"}
print("revealed walls x in 39..54:", sorted(c for c in walls if 39<=c[0]<=54))
# reachability in revealed graph from av
seen={av}; q=deque([av])
while q:
    c=q.popleft()
    for dx,dy in ((0,-1),(0,1),(-1,0),(1,0)):
        nb=(c[0]+dx*_CELL,c[1]+dy*_CELL)
        if nb in pss and nb not in seen: seen.add(nb); q.append(nb)
print("reachable in revealed:", len(seen), "max x reachable:", max(c[0] for c in seen))
# GT passable near column
lvl=g.current_level
gtw={(sp.x,sp.y) for sp in lvl.get_sprites_by_tag("ihdgageizm")}
print("GT: is (44,15) wall?", (44,15) in gtw, " (49,15) wall?", (49,15) in gtw,
      " (49,5) wall?", (49,5) in gtw, " (44,20) wall?", (44,20) in gtw)
# is column reachable in GT?
gtpass={(x,y) for x in range(4,60,5) for y in range(0,55,5) if (x,y) not in gtw}
seen2={(19,15)}; q=deque([(19,15)])
while q:
    c=q.popleft()
    for dx,dy in ((0,-1),(0,1),(-1,0),(1,0)):
        nb=(c[0]+dx*_CELL,c[1]+dy*_CELL)
        if nb in gtpass and nb not in seen2: seen2.add(nb); q.append(nb)
print("GT reachable from start:", len(seen2), "(49,15) reachable?", (49,15) in seen2,
      "(49,20)?", (49,20) in seen2, "(49,5)?", (49,5) in seen2)
# the corridor: print GT passable at x=44 and x=49
print("GT passable x=44:", sorted(c for c in gtpass if c[0]==44))
print("GT passable x=49:", sorted(c for c in gtpass if c[0]==49))
print("GT passable x=39:", sorted(c for c in gtpass if c[0]==39))
