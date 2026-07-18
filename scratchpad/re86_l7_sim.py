"""Faithful offline simulator of the re86 CROSS bar-shift handler (source
`ucpbzrcoui` else-branch @2004-2059, bounds `rtivumgcjd` @1943). State is the
cross as (x, y, vrel, hrel) with fixed w,h; the obstacle is a fixed box. This
lets us BFS the exact push sequence to a target place-state instead of a
hand-tuned oscillating FSM (the repo "learn-the-operator-then-plan" method).

Coordinate convention matches the engine: x = column, y = row; a push is
(dx, dy); ACTION1 up=(0,-3), 2 down=(0,+3), 3 left=(-3,0), 4 right=(+3,0).
vrel = vbar_abs_col - x, hrel = hbar_abs_row - y. Board 64x64.
"""
from __future__ import annotations
from collections import deque

STEP = 3
BOARD = 64


def _collides(x, y, vrel, hrel, w, h, ob):
    """A cross pixel intersects the obstacle box ob=(r0,c0,r1,c1)."""
    r0, c0, r1, c1 = ob
    vbar_col = x + vrel
    hbar_row = y + hrel
    vbar_hits = c0 <= vbar_col <= c1 and y <= r1 and y + h - 1 >= r0
    hbar_hits = r0 <= hbar_row <= r1 and x <= c1 and x + w - 1 >= c0
    return vbar_hits or hbar_hits


def sim_move(state, dx, dy, w, h, ob):
    """Return the next (x, y, vrel, hrel) after one push, exactly per source."""
    x, y, vrel, hrel = state
    r0, c0, r1, c1 = ob
    nx, ny = x + dx, y + dy
    # bounds check on the sprite CENTER (rtivumgcjd)
    cx, cy = nx + w // 2, ny + h // 2
    if not (0 <= cx < BOARD and 0 <= cy < BOARD):
        return (x, y, vrel, hrel)
    if not _collides(nx, ny, vrel, hrel, w, h, ob):
        return (nx, ny, vrel, hrel)
    vbar_in = c0 <= nx + vrel <= c1
    hbar_in = r0 <= ny + hrel <= r1
    if dx != 0:
        a = -STEP if dx > 0 else STEP          # ajczmtpezh
        b = STEP if dx > 0 else -STEP          # vytvprkfky
        canA = (vrel > 0) if dx > 0 else (vrel < w - 2)
        canB = (vrel < w - 2) if dx > 0 else (vrel > 0)
        if vbar_in and hbar_in:
            return (x, y, vrel, hrel)
        if vbar_in:
            return (nx, ny, vrel + a, hrel) if canA else (x, y, vrel, hrel)
        if hbar_in:
            return (x, y, vrel + b, hrel) if canB else (x, y, vrel, hrel)
        return (nx, ny, vrel, hrel)
    else:
        a = -STEP if dy > 0 else STEP
        b = STEP if dy > 0 else -STEP
        canA = (hrel > 0) if dy > 0 else (hrel < h - 2)
        canB = (hrel < h - 2) if dy > 0 else (hrel > 0)
        if hbar_in and vbar_in:
            return (x, y, vrel, hrel)
        if hbar_in:
            return (nx, ny, vrel, hrel + a) if canA else (x, y, vrel, hrel)
        if vbar_in:
            return (x, y, vrel, hrel + b) if canB else (x, y, vrel, hrel)
        return (nx, ny, vrel, hrel)


DIRS = {1: (0, -STEP), 2: (0, STEP), 3: (-STEP, 0), 4: (STEP, 0)}


def bfs_plan(start, goal, w, h, ob, max_nodes=400000, valid=None):
    """BFS over push actions from start to goal state (x,y,vrel,hrel). Returns a
    list of action ids [1..4] or None. `valid(state)`, if given, prunes states
    the plan must never enter (e.g. rising into the station row)."""
    start = tuple(start); goal = tuple(goal)
    if start == goal:
        return []
    seen = {start}
    q = deque([(start, [])])
    while q and len(seen) < max_nodes:
        st, path = q.popleft()
        for a, (dx, dy) in DIRS.items():
            ns = sim_move(st, dx, dy, w, h, ob)
            if ns in seen or (valid is not None and not valid(ns)):
                continue
            if ns == goal:
                return path + [a]
            seen.add(ns)
            q.append((ns, path + [a]))
    return None


def bfs_plan_pred(start, pred, w, h, ob, max_nodes=400000):
    """BFS to the first state satisfying pred(state). Returns (path, state)."""
    start = tuple(start)
    if pred(start):
        return [], start
    seen = {start}
    q = deque([(start, [])])
    while q and len(seen) < max_nodes:
        st, path = q.popleft()
        for a, (dx, dy) in DIRS.items():
            ns = sim_move(st, dx, dy, w, h, ob)
            if ns in seen:
                continue
            if pred(ns):
                return path + [a], ns
            seen.add(ns)
            q.append((ns, path + [a]))
    return None, None
