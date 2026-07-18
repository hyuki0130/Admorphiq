"""L7 refill-chained observation-post FEASIBILITY (pure geometry, GT maze).

Answers the team-lead's precise question: is there a passable, reachable,
SURVIVABLE observation post — ideally adjacent to a refill — whose radius-20
disc reveals enough of the mover's vertical track (x=54, y=5..30) to reconstruct
it? Reports (a) full-track posts, (b) posts seeing y=15, (c) refill-adjacency,
(d) life-aware reachability from start.
"""
from __future__ import annotations
import math, re
from collections import deque
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "environment_files/ls20/9607627b/ls20.py").read_text().splitlines()
# L7 block = last Level(...) : from the last "level_id" style up to Fog:True(1465)
# Simpler: the L7 block is lines 1346..1466 (Fog False @1345 prev, Fog True @1465).
BLK = SRC[1345:1466]
def poss(tag):
    out = []
    for ln in BLK:
        m = re.search(rf'sprites\["{tag}[^"]*"\]\.clone\(\)\.set_position\((\d+), *(\d+)\)', ln)
        if m:
            out.append((int(m.group(1)), int(m.group(2))))
    return out

CELL = 5
walls = set(poss("ihdgageizm"))
refills_sprite = poss("npxgalaybz")
# snap refill sprites to lattice (ox=4, oy=0)
OX, OY = 4, 0
def snap(x, y):
    return (x - (x - OX) % CELL, y - (y - OY) % CELL)
refills = {snap(x, y) for x, y in refills_sprite}
goal = (29, 50)
shape_ch = (19, 40); color_ch = (9, 40)
track = [(54, y) for y in (5, 10, 15, 20, 25, 30)]
start = (19, 15)   # sfqyzhzkij
LIFE = 42 // 2     # 21? current_steps=38 at settle -> life at start = 42//2 = 21 actions
print("walls:", len(walls), "refills(lattice):", sorted(refills))
print("start:", start, "goal:", goal, "track:", track)

# lattice cells in the arena
xs = list(range(OX, 64 - CELL + 1, CELL))
ys = list(range(OY, 64 - CELL + 1, CELL))
PLAY = 55
lattice = {(x, y) for x in xs for y in ys if y < PLAY}
# passable = non-wall arena cells (floor); changers/refills/goal/track are floor too
passable = {(x, y) for (x, y) in lattice if (x, y) not in walls}
# the mover track cells are floor (avatar CAN stand there but triggers rot; treat
# as passable for reachability, but a POST should not be on the track)
print("passable cells:", len(passable))

def cell_vis(cx, cy, ax, ay):
    ccx, ccy = ax + 1.5, ay + 1.5
    return all(math.dist((cy + dy, cx + dx), (ccy, ccx)) <= 20.0
               for dx in (0, 4) for dy in (0, 4))

# for each passable cell, which track cells visible
post_vis = {}
for c in passable:
    if c in track:
        continue
    vis = [t for t in track if cell_vis(t[0], t[1], c[0], c[1])]
    if vis:
        post_vis[c] = vis

full = {c: v for c, v in post_vis.items() if len(v) == 6}
see15 = {c: v for c, v in post_vis.items() if (54, 15) in v}
print("\nposts seeing FULL track (all 6):", sorted(full))
print("posts seeing y=15:", len(see15), "->", sorted(see15)[:20])

# refill-adjacent posts (4-neighbour of a refill)
def neigh(c):
    return {(c[0] + dx * CELL, c[1] + dy * CELL) for dx, dy in ((0,-1),(0,1),(-1,0),(1,0))}
refill_adj = {c for c in post_vis if any(r in neigh(c) for r in refills)}
print("\nrefill-ADJACENT posts that see any track cell:")
for c in sorted(refill_adj):
    adj_r = [r for r in refills if r in neigh(c)]
    print(f"  post {c} sees {sorted(post_vis[c])} | adj refill {adj_r}")

# life-aware reachability from start, routing through refills; returns min life-cost
def reach(targets):
    seen = {(start, LIFE, frozenset())}
    q = deque([(start, LIFE, frozenset(), 0)])
    best = {}
    while q:
        cell, lf, taken, d = q.popleft()
        if cell in targets and cell not in best:
            best[cell] = (d, lf)
        if lf <= 0:
            continue
        for dx, dy in ((0,-1),(0,1),(-1,0),(1,0)):
            nb = (cell[0] + dx * CELL, cell[1] + dy * CELL)
            if nb not in passable:
                continue
            nl, nt = lf - 1, taken
            if nb in refills and nb not in taken:
                nl, nt = LIFE, taken | {nb}
            if nl < 0: continue
            key = (nb, nl, nt)
            if key in seen: continue
            seen.add(key); q.append((nb, nl, nt, d + 1))
    return best

# reachability + remaining life at each candidate post
cand = set(full) | set(see15)
best = reach(cand)
print("\nreachable candidate posts (dist, life_on_arrival):")
for c in sorted(cand):
    if c in best:
        d, lf = best[c]
        tag = "FULL" if c in full else "y15"
        adj = [r for r in refills if r in neigh(c)]
        print(f"  {c} [{tag}] dist={d} life_left={lf} sees={sorted(post_vis[c])} refill_adj={adj}")
    else:
        print(f"  {c} UNREACHABLE alive")
