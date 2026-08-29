"""s5i5 level 7 — every hypothesis about the one uncovered target, tested together (rule 7h).

READ OFF THE GAME'S OWN SOURCE FIRST (rule 0 / rule 6), then MEASURED here (rule 7g).

Level 7 (`environment_files/s5i5/18d95033/s5i5.py`, `levels[6]`, StepCounter 200):

  arms  (tag 0001qwdmnlybkb)  0006 wall(70x51 @-3,-3)  0007 c10  0008 c8
                              0059 c11 -> 0060 c14 -> 0061 c9 -> 0062 c12 -> mover
  movers(tag 0064ocqkuqacti)  (54,15) tip of the 0059 chain · (21,6) tip of arm 0007
  targets(tag 0087vvmblxkzdi) (24,15) UNCOVERED         · (21,6) covered at level start
  rotate buttons (0089)       c14 c11 c9 c8      length sliders (0066)  c14 c11 c9 c12 c10

So the whole level is: walk the 0059 chain's tip from (54,15) to (24,15) without moving arm 0007
(whose mover already sits on its target and which has NO rotate button, only slider c10).

Jobs, all run together by `bash scripts/pfan.sh scripts/_s5i5_reach.py 60`:

  1  INSTRUMENT: click every cell of the 64x64 grid on a fresh board and record what each one
     does. Proves the click alphabet rather than deriving it from sprite boxes.
  2  COLLAPSE: what actually ends the level, and after how many actions.
  3  FREE-SPACE: is the target reachable at all with collisions DISABLED (upper bound).
  4  swivel's own reading of this board, for comparison.
  5+ A* over the real engine with collisions ON, one variant per job.
"""
from __future__ import annotations

import json
import sys
import time
from heapq import heappop, heappush

MOD = "environment_files/s5i5/18d95033/s5i5.py"
LEVEL = 6
ARM = "0001qwdmnlybkb"
MOVER = "0064ocqkuqacti"
TARGET = "0087vvmblxkzdi"


def load():
    import importlib.util

    spec = importlib.util.spec_from_file_location("s5i5mod", MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    g = mod.S5i5()
    g.set_level(LEVEL)
    g.gwiuiwqizb.current_steps = 10 ** 9
    return mod, g


def act(g, x, y):
    from arcengine import ActionInput, GameAction

    return g.perform_action(ActionInput(id=GameAction.ACTION6, data={"x": x, "y": y}), raw=True)


def movable(g):
    seen, out = set(), []
    for s in g.current_level.get_sprites():
        if (ARM in s.tags or MOVER in s.tags) and id(s) not in seen:
            seen.add(id(s))
            out.append(s)
    return out


def snap(g):
    return [(s, s.x, s.y, s.pixels.copy()) for s in movable(g)]


def restore(g, sn):
    for s, x, y, p in sn:
        s.set_position(x, y)
        s.pixels = p.copy()
    g.whoonmfbnp = {}
    g.gwiuiwqizb.current_steps = 10 ** 9


def key(g):
    return tuple(sorted((s.name, s.x, s.y, s.width, s.height) for s in movable(g)))


def coverage(g):
    tg = [(s.x, s.y) for s in g.current_level.get_sprites_by_tag(TARGET)]
    mv = [(s.x, s.y) for s in g.current_level.get_sprites_by_tag(MOVER)]
    cov = [t for t in tg if t in mv]
    free_t = [t for t in tg if t not in mv]
    free_m = [m for m in mv if m not in tg]
    return tg, mv, cov, free_t, free_m


def gap(g):
    _, _, _, ft, fm = coverage(g)
    if not ft:
        return 0
    if not fm:
        return 999
    return min(abs(a - c) + abs(b - d) for a, b in ft for c, d in fm)


def maze_field(g):
    """BFS distance from the uncovered target over cells the STATIC furniture does not occupy.

    Manhattan is a bad guide here: a vertical wall runs the full height of the board between the
    arm and its target, so the tip has to go down, left and back up. The wall is itself an arm
    (tag 0001) and is the one no control drives, which is how it is identified.
    """
    from collections import deque

    driven = {a.name for arms in g.pigtralzpb.values() for a in arms}
    blocked = [[False] * 64 for _ in range(64)]
    for s in g.current_level.get_sprites_by_tag(ARM):
        if s.name in driven:
            continue
        px = s.pixels
        for j in range(px.shape[0]):
            for i in range(px.shape[1]):
                if px[j, i] >= 0 and 0 <= s.y + j < 64 and 0 <= s.x + i < 64:
                    blocked[s.y + j][s.x + i] = True
    _, _, _, ft, _ = coverage(g)
    dist = [[-1] * 64 for _ in range(64)]
    q = deque()
    for tx, ty in ft:
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
    return dist


def maze_gap(g, dist):
    _, _, _, ft, fm = coverage(g)
    if not ft:
        return 0
    if not fm:
        return 999
    best = 999
    for x, y in fm:
        d = dist[y][x] if 0 <= x < 64 and 0 <= y < 64 else -1
        best = min(best, d if d >= 0 else 200)
    return best


def alphabet(g):
    """Every click that does something, derived from the sprites the engine itself dispatches on."""
    out = []
    for b in g.current_level.get_sprites_by_tag("0089rvqdprjwpz"):
        c = int(b.pixels[b.height // 2, b.height // 2])
        out.append(("turn", c, b.x + b.width // 2, b.y + b.height // 2))
    for s in g.current_level.get_sprites_by_tag("0066ghlkyvdbgg"):
        c = int(s.pixels[1, 1])
        wide = s.width > s.height
        half = (s.width if wide else s.height) // 2
        lo = (s.x + 1, s.y + s.height // 2) if wide else (s.x + s.width // 2, s.y + 1)
        hi = (s.x + half + 2, s.y + s.height // 2) if wide else (s.x + s.width // 2, s.y + half + 2)
        out.append(("shrink", c, lo[0], lo[1]))
        out.append(("grow", c, hi[0], hi[1]))
    return out


def job1():
    mod, g = load()
    base = key(g)
    hits = {}
    sn = snap(g)
    for y in range(64):
        for x in range(64):
            restore(g, sn)
            act(g, x, y)
            k = key(g)
            if k != base:
                hits[f"{x},{y}"] = gap(g)
        if y % 16 == 0:
            print(f"# scan row {y}", file=sys.stderr, flush=True)
    restore(g, sn)
    tg, mv, cov, ft, fm = coverage(g)
    print(json.dumps({"job": 1, "targets": tg, "movers": mv, "covered": cov,
                      "uncovered_target": ft, "free_mover": fm,
                      "live_click_cells": len(hits), "gap0": gap(g),
                      "alphabet": alphabet(g),
                      "cells_by_gap": sorted({v for v in hits.values()})}))


def job2():
    import random

    mod, g = load()
    g.gwiuiwqizb.current_steps = g.current_level.get_data("StepCounter")
    alpha = alphabet(g)
    rng = random.Random(2)
    start = g.level_index
    for i in range(1, 1001):
        _, _, x, y = rng.choice(alpha)
        act(g, x, y)
        if i % 25 == 0:
            print(f"# {i} steps_left={g.gwiuiwqizb.current_steps} lvl={g.level_index}",
                  file=sys.stderr, flush=True)
        if g.level_index > start:
            print(json.dumps({"job": 2, "CLEARED": True, "at": i, "level": g.level_index}))
            return
        if str(g._state) .endswith("GAME_OVER"):
            print(json.dumps({"job": 2, "lost_after": i, "steps_left": g.gwiuiwqizb.current_steps,
                              "declared_budget": g.current_level.get_data("StepCounter"),
                              "level": g.level_index}))
            return
    print(json.dumps({"job": 2, "survived": 1000, "steps_left": g.gwiuiwqizb.current_steps}))


def search(no_collide: bool, weight: int, cap: int, hmode: int, max_open: int, deadline: float):
    mod, g = load()
    if no_collide:
        g.qownxibuiy = lambda: False
    alpha = [a for a in alphabet(g) if a[1] not in (10,)]
    field = maze_field(g)
    h = (lambda: maze_gap(g, field)) if hmode else (lambda: gap(g))
    start = g.level_index
    # The bars a slider can lengthen — the only ones a length cap should bind. The wall is an
    # arm too (tag 0001) and is 70x51, so capping every arm prunes the start state itself.
    used = {a[1] for a in alpha}
    drivable = {a.name for sl, arms in g.pigtralzpb.items() for a in arms
                if int(sl.pixels[1, 1]) in used}
    sn0 = snap(g)
    seen = {key(g)}
    heap = [(weight * h(), 0, 0, sn0, ())]
    tick = 0
    opened = 0
    best = h()
    while heap:
        if time.time() > deadline or opened > max_open:
            return {"found": False, "opened": opened, "best_gap": best, "reason": "cap"}
        _, _, _, sn, path = heappop(heap)
        for ai, (kind, colour, x, y) in enumerate(alpha):
            restore(g, sn)
            act(g, x, y)
            opened += 1
            tick += 1
            if tick % 2000 == 0:
                print(f"# opened={opened} best_gap={best} heap={len(heap)} depth={len(path)}",
                      file=sys.stderr, flush=True)
            if g.level_index > start:
                return {"found": True, "level": g.level_index, "plan_len": len(path) + 1,
                        "plan": [list(alpha[i]) for i in path] + [[kind, colour, x, y]],
                        "opened": opened}
            k = key(g)
            if k in seen:
                continue
            if any(max(s.width, s.height) > cap * 3 for s in movable(g)
                   if s.name in drivable):
                continue
            seen.add(k)
            gg = h()
            best = min(best, gg)
            heappush(heap, (len(path) + 1 + weight * gg, gg, len(seen), snap(g), path + (ai,)))
    return {"found": False, "opened": opened, "best_gap": best, "reason": "exhausted"}


def main() -> None:
    job = int(sys.argv[1])
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
    deadline = time.time() + budget
    print(f"# job {job} start", file=sys.stderr, flush=True)
    if job == 1:
        return job1()
    if job == 2:
        return job2()
    if job == 3:
        r = search(True, 4, 20, 1, 400_000, deadline)
        print(json.dumps({"job": 3, "collisions_disabled": True, **r}))
        return
    if job == 4:
        mod, g = load()
        print(json.dumps({"job": 4, "alphabet": alphabet(g), "gap": gap(g),
                          "coverage": [list(map(list, c)) for c in coverage(g)]}))
        return
    weights = [1, 2, 3, 4, 6, 8, 12, 20]
    caps = [5, 7, 10, 14, 20]
    j = job - 5
    hmode = j % 2
    w = weights[(j // 2) % len(weights)]
    cap = caps[(j // 16) % len(caps)]
    r = search(False, w, cap, hmode, 3_000_000, deadline)
    print(json.dumps({"job": job, "weight": w, "cap": cap, "hmode": hmode, **r}))


if __name__ == "__main__":
    main()
