"""Is (49,35) a fog mis-parse or a real wall? Walk the avatar physically to the
x=49 column via the GT route and dump the 5x5 cell readings at close range."""
from __future__ import annotations
import sys
from collections import deque
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.ls20 import Adapter, _find_avatar, _cell_counts
from admorphiq.adapters25.base import canonical_layer
from ls20_l7_v2 import A, _CELL, cell_vis

ar = Arcade(operation_mode=OperationMode.OFFLINE)
env = ar.make("ls20")
obs = env.observation_space
g = env._game
ad = Adapter(giveup=9000)
s = 0
while s < 9000 and obs.levels_completed < 6:
    a = ad.choose_action([], obs)
    obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    s += 1
lvl = g.current_level
gtw = {(sp.x, sp.y) for sp in lvl.get_sprites_by_tag("ihdgageizm")}
gtpass = {(x, y) for x in range(4, 60, 5) for y in range(0, 55, 5) if (x, y) not in gtw}

# BFS a GT route from start to (49,20) and step it, dumping key cells at range
start = (g.gudziatsk.x, g.gudziatsk.y)
def route(a, b):
    q=deque([(a,[])]); seen={a}
    while q:
        c,p=q.popleft()
        if c==b: return p
        for aid,(dx,dy) in {1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)}.items():
            nb=(c[0]+dx*_CELL,c[1]+dy*_CELL)
            if nb in gtpass and nb not in seen: seen.add(nb); q.append((nb,p+[aid]))
    return None
r = route(start, (49,20))
print("GT route start->(49,20):", len(r) if r else None, "actions")
# step it (avoid dying: it's within a life? print life). Refill-chain not needed
# for this diagnostic; just observe cell readings when avatar is adjacent.
for i, aid in enumerate(r or []):
    obs = env.step(A[aid])
    grid = tuple(tuple(row) for row in canonical_layer(obs))
    av = _find_avatar(grid)
    if av is None: continue
    for tgt in [(49,35),(49,30),(49,25),(44,35)]:
        if cell_vis(tgt[0], tgt[1], av[0], av[1]):
            hh=_cell_counts(grid, tgt[0], tgt[1])
            dom=hh.most_common(1)[0][0]
            print(f"  step{i} av={av} cell{tgt} dom={dom} counts={dict(hh)} GTpass={tgt in gtpass}")
    if obs.levels_completed>=7 or str(obs.state).endswith("WIN"):
        print("  (won during walk)"); break
