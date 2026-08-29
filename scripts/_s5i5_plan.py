"""s5i5 level 7 — stage the chain's ORIENTATION first, then search only the lengths.

⛔ MEASURED, not read off the source (rule 7g). The relative angle between a bar and its parent
takes only THREE values — 0, 90, 270 — never 180, and the last bar of the chain is RIGIDLY 90
clockwise of its parent because no control turns it. Reading `bhgumdfgqr`'s double-turn branch gave
{90, 180, 270}, which is wrong; enumerating the turns against the engine gives exactly 36 reachable
orientation tuples for the four-bar chain (`scripts/_s5i5_reach.py` job 4 prints the controls).

That matters because the board is a MAZE, not an open field: a wall column seals x=39..41 for the
whole height of the visible grid and the strip ABOVE the grid is solid wherever x >= 39, so the
chain's rider can only reach the target's chamber by going DOWN the right chamber, LEFT along the
floor, and UP through one of two three-cell gaps at x=6..8 or x=30..32. The last bar then points 90
clockwise of the riser, so a riser through x=30..32 sends the rider the wrong way and only the
x=6..8 gap can work — and a bar of a fourth colour sits across that approach and must be turned out
of it first.

So the search is split: pick one of the 36 orientations (the job index), reach it with turn clicks,
then A* over LENGTHS ONLY with a free-space distance heuristic. Nine moves instead of twelve and no
orientation branching left.
"""
from __future__ import annotations

import json
import sys
import time
from collections import deque
from heapq import heappop, heappush
from itertools import permutations

sys.path.insert(0, "scripts")

from _s5i5_reach import (  # noqa: E402
    ARM,
    MOVER,
    TARGET,
    act,
    alphabet,
    key,
    load,
    movable,
    restore,
    snap,
)

CHAIN = ["0059xvflfxsfdj", "0060dfuyhhnifq", "0061zkkjucxyoq", "0062xugehusbvg"]


def dirs(g):
    out = []
    for n in CHAIN:
        s = next(x for x in g.current_level.get_sprites() if x.name == n)
        out.append(g.gnpdxxlhrp(s))
    return tuple(out)


def controlled(g):
    """Bar colours some control can drive — the rest is furniture that never moves."""
    cols = {a[1] for a in alphabet(g)}
    return cols


def fields_per_target(g):
    """One free-space distance field PER DESTINATION, blocked ONLY by uncontrollable bars.

    ⛔ ONE FIELD AND A MIN OVER RIDERS IS WRONG, and it cost a whole fan-out. Taking the nearest
    rider's distance to the nearest destination reports 9 on this board the moment the ALREADY
    PARKED rider steps off its own destination — that rider is nine cells from the other one and
    can never turn to reach it, so the search was being pulled toward a rider that cannot help
    while the one that can sat at 60. The win is an ASSIGNMENT, so the estimate has to be one
    too: every destination costs the distance of whichever rider is assigned to it.

    A bar some control can turn or lengthen is not furniture; blocking it would lie about the
    only approach the board allows.
    """
    cols = controlled(g)
    blocked = [[False] * 64 for _ in range(64)]
    for s in g.current_level.get_sprites_by_tag(ARM):
        if int(s.pixels[1, 1]) in cols:
            continue
        px = s.pixels
        for j in range(px.shape[0]):
            for i in range(px.shape[1]):
                if px[j, i] >= 0 and 0 <= s.y + j < 64 and 0 <= s.x + i < 64:
                    blocked[s.y + j][s.x + i] = True
    out = []
    for tx, ty in [(s.x, s.y) for s in g.current_level.get_sprites_by_tag(TARGET)]:
        dist = [[-1] * 64 for _ in range(64)]
        q = deque()
        for dy in range(3):
            for dx in range(3):
                x, y = tx + dx, ty + dy
                if 0 <= x < 64 and 0 <= y < 64 and dist[y][x] < 0:
                    dist[y][x] = 0
                    q.append((x, y))
        while q:
            x, y = q.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < 64 and 0 <= ny < 64 and dist[ny][nx] < 0 and not blocked[ny][nx]:
                    dist[ny][nx] = dist[y][x] + 1
                    q.append((nx, ny))
        out.append(((tx, ty), dist))
    return out


def h_of(g, fields):
    """Cheapest assignment of riders to destinations under the per-destination fields."""
    movers = [(s.x, s.y) for s in g.current_level.get_sprites_by_tag(MOVER)]
    if len(movers) < len(fields):
        return 999

    def cost(t_i, m):
        x, y = m
        d = fields[t_i][1][y][x] if 0 <= x < 64 and 0 <= y < 64 else -1
        return d if d >= 0 else 200

    best = None
    for pick in permutations(range(len(movers)), len(fields)):
        tot = sum(cost(i, movers[m]) for i, m in enumerate(pick))
        best = tot if best is None else min(best, tot)
    return best


def turn_paths(g, sn, no_collide: bool = False):
    """Every reachable chain orientation and the shortest turn-click path to it.

    With collisions ON this is what the board actually offers from its compact start — 26 of the
    36 tuples. `no_collide` lifts the refusals so the other ten can be reasoned about too: an
    orientation a turn cannot reach while the bars are short may still be reachable once they are
    long, and treating the 26 as the whole space would turn a search limit into a false verdict.
    """
    if no_collide:
        g.qownxibuiy = lambda: False
    turns = [a for a in alphabet(g) if a[0] == "turn"]
    start = dirs(g)
    seen = {start: ()}
    q = deque([(start, ())])
    while q:
        d, path = q.popleft()
        for i, t in enumerate(turns):
            restore(g, sn)
            for j in path:
                act(g, turns[j][2], turns[j][3])
            act(g, t[2], t[3])
            nd = dirs(g)
            if nd not in seen:
                seen[nd] = path + (i,)
                q.append((nd, path + (i,)))
    restore(g, sn)
    return turns, seen


def main() -> None:
    job = int(sys.argv[1])
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 1200
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 24
    deadline = time.time() + budget
    print(f"# job {job} start", file=sys.stderr, flush=True)

    _mod, g = load()
    start_level = g.level_index
    sn0 = snap(g)
    turns, reach = turn_paths(g, sn0)
    orients = sorted(reach)
    if job > len(orients):
        print(json.dumps({"job": job, "skip": "only %d orientations" % len(orients)}))
        return
    target_dirs = orients[job - 1]
    prefix = reach[target_dirs]
    restore(g, sn0)
    for i in prefix:
        act(g, turns[i][2], turns[i][3])
    if dirs(g) != target_dirs:
        print(json.dumps({"job": job, "error": "orientation not reached", "want": target_dirs,
                          "got": dirs(g)}))
        return
    print(f"# job {job} staged to {target_dirs} in {len(prefix)} turns", file=sys.stderr, flush=True)

    fields = fields_per_target(g)
    # Lengths only, plus the one turn that moves the bar parked across the approach.
    chain_cols = {int(next(x for x in g.current_level.get_sprites() if x.name == n).pixels[1, 1])
                  for n in CHAIN}
    moves = [a for a in alphabet(g) if a[0] != "turn"]
    moves += [a for a in alphabet(g) if a[0] == "turn" and a[1] not in chain_cols]
    used = {a[1] for a in moves}
    drivable = {a.name for sl, arms in g.pigtralzpb.items() for a in arms
                if int(sl.pixels[1, 1]) in used}
    sn = snap(g)
    seen = {key(g)}
    best = h_of(g, fields)
    heap = [(4 * best, 0, 0, sn, ())]
    opened = 0
    tips: dict = {}
    while heap:
        if time.time() > deadline:
            break
        _, _, _, cur, path = heappop(heap)
        for ai, (kind, colour, x, y) in enumerate(moves):
            restore(g, cur)
            act(g, x, y)
            opened += 1
            if opened % 2000 == 0:
                print(f"# opened={opened} best={best} heap={len(heap)} depth={len(path)}",
                      file=sys.stderr, flush=True)
            if g.level_index > start_level:
                plan = [[turns[i][0], turns[i][1], turns[i][2], turns[i][3]] for i in prefix]
                plan += [list(moves[i]) for i in path] + [[kind, colour, x, y]]
                print(json.dumps({"job": job, "CLEARED": True, "level": g.level_index,
                                  "orientation": list(target_dirs), "plan_len": len(plan),
                                  "plan": plan, "opened": opened}))
                return
            k = key(g)
            if k in seen:
                continue
            if any(max(s.width, s.height) > cap * 3 for s in movable(g) if s.name in drivable):
                continue
            seen.add(k)
            hh = h_of(g, fields)
            best = min(best, hh)
            for t in [(sp.x, sp.y) for sp in g.current_level.get_sprites_by_tag(MOVER)]:
                tips[t] = min(tips.get(t, 999), hh)
            heappush(heap, (len(path) + 1 + 4 * hh, hh, len(seen), snap(g), path + (ai,)))
    print(json.dumps({"job": job, "CLEARED": False, "orientation": list(target_dirs),
                      "turns": len(prefix), "opened": opened, "best": best,
                      "n_tips": len(tips),
                      "nearest_tips": sorted(tips, key=lambda t: tips[t])[:6]}))


if __name__ == "__main__":
    main()
