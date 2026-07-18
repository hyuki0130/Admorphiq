"""L7 feasibility v2 — walls from the ENGINE (get_sprites_by_tag ihdgageizm),
authoritative. Recompute observation-post visibility + reachability."""
from __future__ import annotations
import math, sys
from collections import deque
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.ls20 import Adapter

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
# do NOT settle-probe (keep true start); read level start state
lvl = g.current_level
walls = {(sp.x, sp.y) for sp in lvl.get_sprites_by_tag("ihdgageizm")}
refills = {(sp.x, sp.y) for sp in lvl.get_sprites_by_tag("npxgalaybz")}
CELL = 5
OX, OY = 4, 0
def snap(x, y): return (x-(x-OX)%CELL, y-(y-OY)%CELL)
refills = {snap(x, y) for x, y in refills}
start = (g.gudziatsk.x, g.gudziatsk.y)
mv = g.wsoslqeku[0]
track = [(54, y) for y in (5, 10, 15, 20, 25, 30)]
mover_now = (mv._sprite.x, mv._sprite.y, mv._dir)
LIFE = g._step_counter_ui.current_steps // 2
print("start(GT):", start, "mover_now:", mover_now, "life:", LIFE, "steps:", g._step_counter_ui.current_steps)
print("walls:", len(walls), "refills:", sorted(refills))

xs = list(range(OX, 64-CELL+1, CELL)); ys = list(range(OY, 64-CELL+1, CELL))
lattice = {(x, y) for x in xs for y in ys if y < 55}
passable = {c for c in lattice if c not in walls}
print("passable:", len(passable), "start in passable:", start in passable)

def cell_vis(cx, cy, ax, ay):
    ccx, ccy = ax+1.5, ay+1.5
    return all(math.dist((cy+dy, cx+dx), (ccy, ccx)) <= 20.0 for dx in (0,4) for dy in (0,4))

post_vis = {}
for c in passable:
    if c in track: continue
    v = [t for t in track if cell_vis(*t, *c)]
    if v: post_vis[c] = v
full = {c: v for c, v in post_vis.items() if len(v) == 6}
print("\nFULL-track posts:", sorted(full))
def neigh(c): return {(c[0]+dx*CELL, c[1]+dy*CELL) for dx,dy in ((0,-1),(0,1),(-1,0),(1,0))}

def reach(targets):
    seen={(start,LIFE,frozenset())}; q=deque([(start,LIFE,frozenset(),0)]); best={}
    while q:
        cell,lf,tk,d=q.popleft()
        if cell in targets and cell not in best: best[cell]=(d,lf)
        if lf<=0: continue
        for dx,dy in ((0,-1),(0,1),(-1,0),(1,0)):
            nb=(cell[0]+dx*CELL, cell[1]+dy*CELL)
            if nb not in passable: continue
            nl,nt=lf-1,tk
            if nb in refills and nb not in tk: nl,nt=LIFE,tk|{nb}
            if nl<0: continue
            k=(nb,nl,nt)
            if k in seen: continue
            seen.add(k); q.append((nb,nl,nt,d+1))
    return best

cand = set(full) | {c for c in post_vis if (54,15) in post_vis[c]}
best = reach(cand)
print("\nreachable candidates (dist, life_on_arrival):")
for c in sorted(cand):
    tag = "FULL" if c in full else "y15 "
    adj = [r for r in refills if r in neigh(c)]
    if c in best:
        d, lf = best[c]
        print(f"  {c} [{tag}] dist={d:2d} life={lf:2d} sees={sorted(post_vis[c])} refill_adj={adj}")
    else:
        print(f"  {c} [{tag}] UNREACHABLE sees={sorted(post_vis[c])} refill_adj={adj}")
# also: reachability of the refill (49,5) and column x=49 posts
print("\nrefill (49,5) reachable:", (49,5) in reach({(49,5)}))
