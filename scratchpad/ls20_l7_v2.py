"""L7 fog explorer v2 (frame-only): phased explore (reveal static maze) + loiter
(capture the mover track) + joint-BFS (1 goal + static changers + 1 mover) +
open-loop replay to a live L7 win. Self-contained sim (L6 mover step + static
changers). Measures whether the full frame-only pipeline clears L7.
"""
from __future__ import annotations
import math, sys
from collections import deque
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.ls20 import (
    Adapter, _find_avatar, _cell_counts, _classify_changer, _decode_goal_preview,
    _decode_token, _detect_pushwalls_pixel, _find_refill_sprites, _snap_to_lattice,
    _GOAL_BORDER, _PALETTE, _FLOOR_COLOR, _WALL_COLOR, _PLAYABLE_MAX_ROW, _CELL, _STEP_FULL,
)
from admorphiq.adapters25.base import canonical_layer

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4}
MOVES = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
DIRVEC = {0: (0, 1), 1: (1, 0), 2: (0, -1), 3: (-1, 0)}
FOG_R = 20.0


def cell_vis(cx, cy, ax, ay):
    ccx, ccy = ax + 1.5, ay + 1.5
    return all(math.dist((cy + dy, cx + dx), (ccy, ccx)) <= FOG_R for dx in (0, 4) for dy in (0, 4))


class Mem:
    def __init__(self):
        self.static = {}       # cell -> floor|wall|goal|refill
        self.goal = None
        self.goal_req = None
        self.changer_cells = {"shape": set(), "color": set(), "rot": set()}
        self.pushwalls = {}
        self.token = None
        self.ox = self.oy = 4


def parse_disc(grid, mem):
    av = _find_avatar(grid)
    if av is None:
        return None
    ax, ay = av
    mem.ox, mem.oy = ax % _CELL, ay % _CELL
    t = _decode_token(grid)
    if t is not None:
        mem.token = t
    xs = list(range(mem.ox, len(grid[0]) - _CELL + 1, _CELL))
    ys = list(range(mem.oy, len(grid) - _CELL + 1, _CELL))
    for (sx, sy, dx, dy) in _detect_pushwalls_pixel(grid):
        if cell_vis(sx, sy, ax, ay):
            mem.pushwalls[(sx, sy)] = (dx, dy)
    for (rx, ry) in _find_refill_sprites(grid):
        c = _snap_to_lattice(rx, ry, mem.ox, mem.oy)
        if cell_vis(c[0], c[1], ax, ay):
            mem.static[c] = "refill"
    for x in xs:
        for y in ys:
            if not cell_vis(x, y, ax, ay):
                continue
            hh = _cell_counts(grid, x, y)
            dom = hh.most_common(1)[0][0]
            if y < _PLAYABLE_MAX_ROW and dom == _GOAL_BORDER and sum(hh.get(c, 0) for c in _PALETTE) >= 3:
                mem.static[(x, y)] = "goal"
                mem.goal = (x, y)
                if mem.goal_req is None:
                    r = _decode_goal_preview(grid, x, y)
                    if r:
                        mem.goal_req = r
                continue
            kind = _classify_changer(hh, dom) if y < _PLAYABLE_MAX_ROW else None
            if kind is not None:
                mem.changer_cells[kind].add((x, y))
                if mem.static.get((x, y)) not in ("refill", "goal"):
                    mem.static[(x, y)] = "floor"  # floor is authoritative (but a
                    # collected refill stays a refill LOCATION, restored on death)
            elif dom == _FLOOR_COLOR:
                if mem.static.get((x, y)) not in ("refill", "goal"):
                    mem.static[(x, y)] = "floor"  # floor overrides wall, not refill
            elif dom == _WALL_COLOR:
                # a wall reading NEVER overwrites an established floor cell: floor
                # detection is reliable, wall reads at the fog-disc edge are not.
                if mem.static.get((x, y)) != "floor":
                    mem.static[(x, y)] = "wall"
    mem.static[av] = "floor"
    return av


def bfs_path(passable, start, goal_pred, blocked=None):
    q = deque([(start, [])])
    seen = {start}
    while q:
        c, p = q.popleft()
        if goal_pred(c):
            return p, c
        for aid, (dx, dy) in MOVES.items():
            nb = (c[0] + dx * _CELL, c[1] + dy * _CELL)
            if nb in passable and nb not in seen and (blocked is None or nb not in blocked):
                seen.add(nb)
                q.append((nb, p + [aid]))
    return None, None


def passable_of(mem):
    return {c for c, t in mem.static.items() if t in ("floor", "goal", "refill")}


def _band_life(grid):
    row = min(61, len(grid) - 2)
    return sum(1 for c in range(13, min(13 + _STEP_FULL, len(grid[0]))) if grid[row][c] != _FLOOR_COLOR) // 2


def nav_life_aware(passable, refills, start, targets, life, full):
    """Life-aware BFS to reach any target cell alive, routing through refills.
    State (cell, life, refills_taken). Returns the first action or None."""
    if not targets:
        return None
    seen = {(start, life, frozenset())}
    q = deque([(start, life, frozenset(), [])])
    while q:
        cell, lf, taken, path = q.popleft()
        if cell in targets and path:
            return path[0]
        if lf <= 0:
            continue
        for aid, (dx, dy) in MOVES.items():
            nb = (cell[0] + dx * _CELL, cell[1] + dy * _CELL)
            if nb not in passable:
                continue
            nl, nt = lf - 1, taken
            if nb in refills and nb not in taken:
                nl, nt = full, taken | {nb}
            if nl < 0:
                continue
            key = (nb, nl, nt)
            if key in seen:
                continue
            seen.add(key)
            q.append((nb, nl, nt, path + [aid]))
    return None


# ── self-contained L7 sim: 1 goal + static changers + 1 general mover ────────

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


def sim_step(m, s, action):
    ax, ay, sh, co, ro, steps, taken, mst = s
    dx, dy = MOVES[action]
    prov = mover_step(m["track"], *mst)
    nx, ny = ax + dx * _CELL, ay + dy * _CELL
    matched = (nx, ny) == m["goal"] and (sh, co, ro) == m["req"]
    if (nx, ny) in m["walls"] or ((nx, ny) == m["goal"] and not matched):
        return s
    ax, ay = nx, ny
    # static changers
    k = m["static_changers"].get((ax, ay))
    # mover (rot) on its new cell
    if (ax, ay) == (prov[0], prov[1]):
        k = m["mover_kind"]
    if k == "rot":
        ro = (ro + 1) % 4
    elif k == "color":
        co = (co + 1) % 4
    elif k == "shape":
        sh = (sh + 1) % 6
    nsteps = steps - 1
    if (ax, ay) in m["refills"] and (ax, ay) not in taken:
        nsteps = m["step_full"]
        taken = taken | {(ax, ay)}
    if nsteps >= 0:
        for (sx, sy), (pdx, pdy) in m["pushwalls"].items():
            if ax < sx + _CELL and sx < ax + _CELL and ay < sy + _CELL and sy < ay + _CELL:
                dist = carry_dist(m["fj"], sx, sy, pdx, pdy, _CELL, _CELL)
                if dist > 0:
                    ax += pdx * _CELL * dist
                    ay += pdy * _CELL * dist
                    break
    return (ax, ay, sh, co, ro, nsteps, taken, prov)


def sim_bfs(m, start, cap=8_000_000):
    if (start[0], start[1]) == m["goal"] and (start[2], start[3], start[4]) == m["req"]:
        return []
    seen = {start}
    q = deque([(start, [])])
    exp = 0
    while q and exp < cap:
        s, path = q.popleft()
        exp += 1
        if s[5] <= 0:
            continue
        for aid in (1, 2, 3, 4):
            ns = sim_step(m, s, aid)
            if ns[5] < 0 or ns == s or ns in seen:
                continue
            if (ns[0], ns[1]) == m["goal"] and (ns[2], ns[3], ns[4]) == m["req"]:
                return path + [aid]
            seen.add(ns)
            q.append((ns, path + [aid]))
    return None


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("ls20")
    obs = env.observation_space
    g = env._game
    adapter = Adapter(giveup=9000)
    steps = 0
    while steps < 9000 and obs.levels_completed < 6:
        a = adapter.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        steps += 1
    obs = env.step(GameAction.ACTION1)

    mem = Mem()
    ea = 0

    def grid_now():
        return tuple(tuple(r) for r in canonical_layer(obs))

    # PHASE 1: frontier sweep until goal + req + shape + color changers found.
    for _ in range(250):
        grid = grid_now()
        if not grid or len(grid) < 64:
            obs = env.step(A[1]); ea += 1; continue
        av = parse_disc(grid, mem)
        if av is None:
            obs = env.step(A[1]); ea += 1; continue
        have = mem.goal and mem.goal_req and mem.changer_cells["shape"] and mem.changer_cells["color"] and mem.changer_cells["rot"]
        pss = passable_of(mem)
        # frontier: nearest known-floor cell with an unrevealed neighbour
        path, tgt = bfs_path(pss | {av}, av,
                             lambda c: any((c[0] + dx * _CELL, c[1] + dy * _CELL) not in mem.static
                                           and 0 <= c[1] + dy * _CELL < 55 for dx, dy in DIRVEC.values()))
        if have and path is not None and len(path) > 3:
            break  # enough revealed near-hand; go capture the mover
        if path is None:
            break
        if not path:  # at a frontier cell: step into the unrevealed neighbour
            done = False
            for aid, (dx, dy) in MOVES.items():
                nb = (av[0] + dx * _CELL, av[1] + dy * _CELL)
                if nb not in mem.static:
                    obs = env.step(A[aid]); ea += 1; done = True; break
            if not done:
                obs = env.step(A[1]); ea += 1
        else:
            obs = env.step(A[path[0]]); ea += 1
    print(f"phase1 done ea={ea} goal={mem.goal} req={mem.goal_req} "
          f"shape={sorted(mem.changer_cells['shape'])} color={sorted(mem.changer_cells['color'])} "
          f"rot={sorted(mem.changer_cells['rot'])}")

    # PHASE 2: life-aware nav to a rot-changer OBSERVATION cell, then loiter to
    # capture the mover sweep. Observation cells = revealed floor within fog
    # radius of the seed rot cell (but NOT on it, to avoid triggering rotation).
    rot_seed = next(iter(mem.changer_cells["rot"]), None)
    rot_track = set(mem.changer_cells["rot"])
    rot_seq = []
    full = _STEP_FULL // 2
    if rot_seed is not None:
        for _ in range(400):
            grid = grid_now()
            if not grid or len(grid) < 64:
                obs = env.step(A[1]); ea += 1; continue
            av = parse_disc(grid, mem)
            if av is None:
                obs = env.step(A[1]); ea += 1; continue
            for c in list(mem.changer_cells["rot"]):
                if cell_vis(c[0], c[1], av[0], av[1]):
                    if not rot_seq or rot_seq[-1] != c:
                        rot_seq.append(c)
                    rot_track.add(c)
            if ea % 20 == 0:
                print(f"  phase2 ea={ea} av={av} rot_track={len(rot_track)} seq={len(rot_seq)}", flush=True)
            if len(rot_track) >= 4 and len(rot_seq) >= 5:
                break
            pss = passable_of(mem)
            band = _band_life(grid)
            obs_cells = {c for c in pss
                         if c not in mem.changer_cells["rot"]
                         and any(cell_vis(t[0], t[1], c[0], c[1]) for t in rot_track)}
            # if already at an observation cell with life, loiter (small move)
            if av in obs_cells and band > 4:
                moved = False
                for aid, (dx, dy) in MOVES.items():
                    nb = (av[0] + dx * _CELL, av[1] + dy * _CELL)
                    if nb in obs_cells and nb != mem.goal:
                        obs = env.step(A[aid]); ea += 1; moved = True; break
                if not moved:
                    obs = env.step(A[1]); ea += 1
                continue
            # else navigate life-aware toward the nearest observation cell (or a
            # refill first if life is low)
            plan_nav = nav_life_aware(pss, {c for c, t in mem.static.items() if t == "refill"},
                                      av, obs_cells, band, full)
            if plan_nav:
                obs = env.step(A[plan_nav]); ea += 1
            else:
                # cannot route alive: head greedily toward the seed (accumulate
                # over lives; memory persists across deaths)
                path, _t = bfs_path(pss | {av}, av, lambda c: c in obs_cells)
                obs = env.step(A[path[0] if path else 1]); ea += 1
    print(f"phase2 done ea={ea} rot_track={sorted(rot_track)} rot_seq={rot_seq}")

    # PHASE 3: build maze + plan + replay.
    grid = grid_now()
    while not grid or len(grid) < 64:
        obs = env.step(A[1]); grid = grid_now()
    av = parse_disc(grid, mem) or (g.gudziatsk.x, g.gudziatsk.y)
    walls = frozenset(c for c, t in mem.static.items() if t == "wall")
    refills = frozenset(c for c, t in mem.static.items() if t == "refill")
    static_changers = {}
    for c in mem.changer_cells["shape"]:
        static_changers[c] = "shape"
    for c in mem.changer_cells["color"]:
        static_changers[c] = "color"
    # mover current cell + dir
    mcur = rot_seq[-1] if rot_seq else next(iter(rot_track), (54, 5))
    mdir = 0
    for j in range(len(rot_seq) - 1, 0, -1):
        v = (rot_seq[j][0] - rot_seq[j - 1][0], rot_seq[j][1] - rot_seq[j - 1][1])
        for d, (dx, dy) in DIRVEC.items():
            if (dx * _CELL, dy * _CELL) == v:
                mdir = d
                break
        else:
            continue
        break
    # life from band
    row = min(61, len(grid) - 2)
    band = sum(1 for c in range(13, min(13 + _STEP_FULL, len(grid[0]))) if grid[row][c] != _FLOOR_COLOR)
    decr = 2
    m = {
        "goal": mem.goal, "req": mem.goal_req, "walls": walls, "refills": refills,
        "static_changers": static_changers, "mover_kind": "rot",
        "track": frozenset(rot_track), "pushwalls": mem.pushwalls,
        "fj": frozenset(set(walls) | {mem.goal}), "step_full": _STEP_FULL // decr,
    }
    sh, co, ro = mem.token
    start = (av[0], av[1], sh, co, ro, band // decr, frozenset(), (mcur[0], mcur[1], mdir))
    print(f"phase3 start={start} track={sorted(rot_track)} mdir={mdir} band_life={band // decr}")
    print(f"GT mover now=({g.wsoslqeku[0]._sprite.x},{g.wsoslqeku[0]._sprite.y},{g.wsoslqeku[0]._dir}) "
          f"GT avatar=({g.gudziatsk.x},{g.gudziatsk.y}) GT token=({g.fwckfzsyc},{g.hiaauhahz},{g.cklxociuu})")
    plan = sim_bfs(m, start)
    print("plan_len", len(plan) if plan else None, "total explore actions", ea)
    if not plan:
        print("NO PLAN"); return
    for i, act in enumerate(plan):
        obs = env.step(A[act])
        if obs is None:
            print("obs None"); break
        if str(obs.state).endswith("WIN") or obs.levels_completed >= 7:
            print(f"*** LIVE L7 WIN at action {i+1}/{len(plan)} (explore={ea}) ***"); return
    print("replay ended; levels", obs.levels_completed, "state", obs.state)


if __name__ == "__main__":
    main()
