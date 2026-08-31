"""FRAME-ONLY L6 end-to-end: observe the 3 phase-synced movers + multi-goal
parse → sim reusing L5 push-carry/refill-snap + general npdjlrkhsg mover step →
joint-BFS (satisfied-goals bitmask) → open-loop replay to a LIVE L6 win. No
engine internals in the solve (GT only cross-checked at the end).
"""
from __future__ import annotations
import sys
from collections import deque
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.ls20 import (
    Adapter, _find_avatar, _cell_counts, _classify_changer, _decode_goal_preview,
    _decode_token, _detect_pushwalls_pixel, _find_refill_sprites, _snap_to_lattice,
    _GOAL_BORDER, _PALETTE, _FLOOR_COLOR, _PLAYABLE_MAX_ROW, _CELL,
)
from admorphiq.adapters25.base import canonical_layer

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4}
MOVES = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
DIRVEC = {0: (0, 1), 1: (1, 0), 2: (0, -1), 3: (-1, 0)}  # nakogfhyus


def parse_multigoal(grid):
    """All goals + reqs, changers-by-cell, hard_walls, passable, refills, token,
    avatar, pushwalls. Returns None if unparseable."""
    avatar = _find_avatar(grid)
    if avatar is None:
        return None
    ax, ay = avatar
    ox, oy = ax % _CELL, ay % _CELL
    xs = list(range(ox, len(grid[0]) - _CELL + 1, _CELL))
    ys = list(range(oy, len(grid) - _CELL + 1, _CELL))
    pushwalls = [(sx, sy, dx, dy, _CELL, _CELL) for (sx, sy, dx, dy) in _detect_pushwalls_pixel(grid)]
    goals, reqs, changers, hard, passable = [], [], {}, set(), set()
    for x in xs:
        for y in ys:
            hh = _cell_counts(grid, x, y)
            dom = hh.most_common(1)[0][0]
            if y < _PLAYABLE_MAX_ROW and dom == _GOAL_BORDER and sum(hh.get(c, 0) for c in _PALETTE) >= 3:
                req = _decode_goal_preview(grid, x, y)
                if req is None:
                    return None
                goals.append((x, y)); reqs.append(req); passable.add((x, y))
                continue
            if dom == _FLOOR_COLOR:
                passable.add((x, y))
            else:
                hard.add((x, y))
            if y < _PLAYABLE_MAX_ROW:
                k = _classify_changer(hh, dom)
                if k is not None:
                    changers[(x, y)] = k
    token = _decode_token(grid)
    if token is None or not goals:
        return None
    refills = {_snap_to_lattice(sx, sy, ox, oy) for (sx, sy) in _find_refill_sprites(grid)}
    hard.discard(avatar); passable.add(avatar)
    for (sx, sy, dx, dy, w, h) in pushwalls:
        passable.add((sx, sy))
    return {"avatar": avatar, "goals": goals, "reqs": reqs, "changers": changers,
            "hard_walls": frozenset(hard), "passable": frozenset(passable),
            "refills": frozenset(refills), "token": token, "pushwalls": tuple(pushwalls)}


def mover_step(cells, x, y, d):
    for cand in (d, (d - 1) % 4, (d + 1) % 4, (d + 2) % 4):
        dx, dy = DIRVEC[cand]
        nx, ny = x + dx * _CELL, y + dy * _CELL
        if (nx, ny) in cells:
            return (nx, ny, cand)
    return (x, y, d)


def carry_dist(fj, sx, sy, dx, dy, w, h):
    wcx, wcy = sx + dx, sy + dy
    for k in range(1, 12):
        if (wcx + dx * w * k, wcy + dy * h * k) in fj:
            return max(0, k - 1)
    return 0


def l6_step(m, s, action):
    """m: maze dict. s: (ax,ay,sh,co,ro,steps,taken,movers,satisfied).
    movers: tuple of (x,y,dir) parallel to m['mover_kinds']/m['mover_tracks']."""
    ax, ay, sh, co, ro, steps, taken, movers, sat = s
    dx, dy = MOVES[action]
    prov = tuple(mover_step(m["mover_tracks"][i], *movers[i]) for i in range(len(movers)))
    nx, ny = ax + dx * _CELL, ay + dy * _CELL
    blocked = (nx, ny) in m["hard_walls"]
    for gi, gc in enumerate(m["goals"]):
        if (nx, ny) == gc and gi not in sat and (sh, co, ro) != m["reqs"][gi]:
            blocked = True
    if blocked:
        return s
    ax, ay = nx, ny
    for i, mk in enumerate(m["mover_kinds"]):
        if (ax, ay) == (prov[i][0], prov[i][1]):
            if mk == "rot":
                ro = (ro + 1) % 4
            elif mk == "color":
                co = (co + 1) % 4
            elif mk == "shape":
                sh = (sh + 1) % 6
    nsteps = steps - 1
    if (ax, ay) in m["refills"] and (ax, ay) not in taken:
        nsteps = m["step_full"]; taken = taken | {(ax, ay)}
    if nsteps >= 0:
        for (sx, sy, pdx, pdy, w, h) in m["pushwalls"]:
            if ax < sx + w and sx < ax + _CELL and ay < sy + h and sy < ay + _CELL:
                dist = carry_dist(m["fjzuynaokm"], sx, sy, pdx, pdy, w, h)
                if dist > 0:
                    ax += pdx * w * dist; ay += pdy * h * dist
                    break
    nsat = sat
    for gi, gc in enumerate(m["goals"]):
        if gi not in sat and (ax, ay) == gc and (sh, co, ro) == m["reqs"][gi]:
            nsat = sat | {gi}
    return (ax, ay, sh, co, ro, nsteps, taken, prov, nsat)


def l6_bfs(m, start, cap=8_000_000):
    ng = len(m["goals"])
    seen = {start}
    q = deque([(start, [])])
    exp = 0
    while q and exp < cap:
        s, path = q.popleft(); exp += 1
        if s[5] <= 0:
            continue
        for act in (1, 2, 3, 4):
            ns = l6_step(m, s, act)
            if ns[5] < 0 or ns == s or ns in seen:
                continue
            if len(ns[8]) == ng:
                return path + [act], exp
            seen.add(ns); q.append((ns, path + [act]))
    return None, exp


def dir_from(prev, cur):
    v = (cur[0] - prev[0], cur[1] - prev[1])
    for d, (dx, dy) in DIRVEC.items():
        if (dx * _CELL, dy * _CELL) == v:
            return d
    return None


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("ls20")
    obs = env.observation_space
    g = env._game
    adapter = Adapter(giveup=8000)
    steps = 0
    while steps < 8000 and obs.levels_completed < 5:
        a = adapter.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        steps += 1
    obs = env.step(GameAction.ACTION1)  # settle entry

    def grid():
        return tuple(tuple(r) for r in canonical_layer(obs))

    # OBSERVE: record each kind's mover cell over successful moves until each
    # mover's visited-cell set is stable for `stable_need` moves (cap).
    visited = {"rot": set(), "shape": set(), "color": set()}
    order = {"rot": [], "shape": [], "color": []}
    stable = 0
    obs_moves = 0
    prev_av = None
    for _ in range(30):
        p = parse_multigoal(grid())
        if p is None:
            obs = env.step(A[1]); continue
        av = p["avatar"]
        moved = prev_av is None or av != prev_av
        if moved:
            grew = False
            for c, k in p["changers"].items():
                if k in visited and c not in visited[k]:
                    grew = True
                if k in visited:
                    visited[k].add(c)
                    order[k].append(c)
            stable = 0 if grew else stable + 1
        prev_av = av
        if obs_moves >= 6 and stable >= 5:
            break
        # safe successful move
        act = None
        for cand in (4, 3, 2, 1):
            dx, dy = MOVES[cand]
            nb = (av[0] + dx * _CELL, av[1] + dy * _CELL)
            if nb in p["passable"] and nb not in p["hard_walls"] and nb not in p["goals"]:
                act = cand; break
        act = act or 1
        obs = env.step(A[act]); obs_moves += 1
    print("observed cells:", {k: sorted(v) for k, v in visited.items()}, "obs_moves", obs_moves)

    # build maze from the FINAL settled parse
    p = parse_multigoal(grid())
    kinds = [k for k in ("rot", "shape", "color") if visited[k]]
    tracks = [frozenset(visited[k]) for k in kinds]
    # current pos = last observed; dir = from last two DISTINCT observed cells
    curmov = []
    for k in kinds:
        seq = order[k]
        pos = seq[-1]
        d = 1
        for j in range(len(seq) - 1, 0, -1):
            dd = dir_from(seq[j - 1], seq[j])
            if dd is not None:
                d = dd; break
        curmov.append((pos[0], pos[1], d))
    full = 42  # decrement 1 on L6 -> life (actions) == StepCounter band count
    m = {
        "goals": p["goals"], "reqs": p["reqs"], "hard_walls": p["hard_walls"],
        "refills": p["refills"], "pushwalls": p["pushwalls"],
        "fjzuynaokm": frozenset(set(p["hard_walls"]) | set(p["goals"])),
        "mover_kinds": kinds, "mover_tracks": tracks, "step_full": full,
    }
    ax, ay = p["avatar"]; sh, co, ro = p["token"]
    life = _band_life(grid())
    start = (ax, ay, sh, co, ro, life, frozenset(), tuple(curmov), frozenset())
    print("goals", m["goals"], "reqs", m["reqs"], "kinds", kinds)
    print("tracks", [sorted(t) for t in tracks], "curmov", curmov, "life", life)
    print("GT movers", [(mm._sprite.x, mm._sprite.y, mm._dir) for mm in g.wsoslqeku],
          "GT token", (g.fwckfzsyc, g.hiaauhahz, g.cklxociuu), "GT avatar", (g.gudziatsk.x, g.gudziatsk.y))
    plan, exp = l6_bfs(m, start)
    print(f"BFS exp={exp} plan_len={len(plan) if plan else None}")
    if not plan:
        print("NO PLAN"); return
    for i, act in enumerate(plan):
        obs = env.step(A[act])
        if obs is None:
            print("obs None"); break
        if str(obs.state).endswith("WIN") or obs.levels_completed >= 6:
            print(f"*** LIVE L6 WIN at action {i+1}/{len(plan)} (obs_moves={obs_moves}) ***"); return
    print("replay ended; levels", obs.levels_completed, "state", obs.state)


def _band_life(grid):
    """current_steps from the counter band (decrement 1 on L6 -> life==steps)."""
    H, W = len(grid), len(grid[0])
    row = min(61, H - 2)
    return sum(1 for c in range(13, min(13 + 42, W)) if grid[row][c] != _FLOOR_COLOR)


if __name__ == "__main__":
    main()
