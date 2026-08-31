"""L7 v3: TIMING INFERENCE for the hidden half of the mover's vertical track.
The mover steps once per successful avatar move and bounces at endpoints, so the
number of ticks it is invisible below the DEEPEST-visible track cell encodes the
hidden depth: cells_below = gap/2. Measure across >=2 excursions (falsify if
inconsistent), reconstruct the full track, then plan with the v2 sim.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.ls20 import Adapter
from admorphiq.adapters25.base import canonical_layer
from ls20_l7_v2 import (
    Mem, parse_disc, passable_of, _band_life, nav_life_aware, cell_vis,
    sim_bfs, MOVES, A, _CELL, _STEP_FULL,
)


def reveal_static(env, obs, grid_now, mem, cap=120):
    ea = 0
    for _ in range(cap):
        grid = grid_now()
        if not grid or len(grid) < 64:
            obs[0] = env.step(A[1]); ea += 1; continue
        av = parse_disc(grid, mem)
        if av is None:
            obs[0] = env.step(A[1]); ea += 1; continue
        have = mem.goal and mem.goal_req and mem.changer_cells["shape"] and mem.changer_cells["color"] and mem.changer_cells["rot"]
        if have:
            return ea, av
        pss = passable_of(mem) | {av}
        from collections import deque
        q = deque([(av, [])]); seen = {av}; step = None
        while q:
            c, p = q.popleft()
            if any((c[0] + dx * _CELL, c[1] + dy * _CELL) not in mem.static and 0 <= c[1] + dy * _CELL < 55
                   for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))):
                step = p; break
            for aid, (dx, dy) in MOVES.items():
                nb = (c[0] + dx * _CELL, c[1] + dy * _CELL)
                if nb in pss and nb not in seen:
                    seen.add(nb); q.append((nb, p + [aid]))
        if step is None:
            return ea, av
        if not step:
            done = False
            for aid, (dx, dy) in MOVES.items():
                nb = (av[0] + dx * _CELL, av[1] + dy * _CELL)
                if nb not in mem.static:
                    obs[0] = env.step(A[aid]); ea += 1; done = True; break
            if not done:
                obs[0] = env.step(A[1]); ea += 1
        else:
            obs[0] = env.step(A[step[0]]); ea += 1
    return ea, None


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("ls20")
    obs = [env.observation_space]
    g = env._game
    adapter = Adapter(giveup=9000)
    steps = 0
    while steps < 9000 and obs[0].levels_completed < 6:
        a = adapter.choose_action([], obs[0])
        obs[0] = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        steps += 1
    obs[0] = env.step(GameAction.ACTION1)

    def grid_now():
        return tuple(tuple(r) for r in canonical_layer(obs[0]))

    mem = Mem()
    ea, av = reveal_static(env, obs, grid_now, mem)
    print(f"phase1 reveal ea={ea} goal={mem.goal} req={mem.goal_req} "
          f"rot_seed={sorted(mem.changer_cells['rot'])}", flush=True)

    # PHASE 2: navigate to an observation cell that sees rot-track cells, then
    # CONTROLLED loiter (oscillate on two safe floor cells) recording the mover's
    # visible cell each successful move (tick).
    full = _STEP_FULL // 2
    ticks = []  # (mover_cell or None) per successful move while loitering
    for _ in range(400):
        grid = grid_now()
        if not grid or len(grid) < 64:
            obs[0] = env.step(A[1]); ea += 1; continue
        av = parse_disc(grid, mem)
        if av is None:
            obs[0] = env.step(A[1]); ea += 1; continue
        pss = passable_of(mem)
        rot_now = [c for c in mem.changer_cells["rot"] if cell_vis(c[0], c[1], av[0], av[1])]
        # observation cells: reachable floor from which at least the seed rot cell is visible
        seed = min(mem.changer_cells["rot"], key=lambda c: c[1]) if mem.changer_cells["rot"] else None
        obs_cells = {c for c in pss if c not in mem.changer_cells["rot"]
                     and seed and cell_vis(seed[0], seed[1], c[0], c[1])}
        band = _band_life(grid)
        if av in obs_cells and band > 3:
            # record this tick's mover observation, then make a safe oscillation move
            ticks.append(rot_now[0] if rot_now else None)
            nxt = None
            for aid, (dx, dy) in MOVES.items():
                nb = (av[0] + dx * _CELL, av[1] + dy * _CELL)
                if nb in obs_cells and nb != mem.goal:
                    nxt = aid; break
            obs[0] = env.step(A[nxt if nxt else 1]); ea += 1
            # stop once we have a long enough tick series with >=2 down-excursions
            if len(ticks) >= 60:
                break
            continue
        nav = nav_life_aware(pss, {c for c, t in mem.static.items() if t == "refill"}, av, obs_cells, band, full)
        if nav:
            obs[0] = env.step(A[nav]); ea += 1
        else:
            from collections import deque
            q = deque([(av, [])]); seen = {av}; step = None
            while q:
                c, p = q.popleft()
                if c in obs_cells:
                    step = p; break
                for aid, (dx, dy) in MOVES.items():
                    nb = (c[0] + dx * _CELL, c[1] + dy * _CELL)
                    if nb in (pss | {av}) and nb not in seen:
                        seen.add(nb); q.append((nb, p + [aid]))
            obs[0] = env.step(A[step[0] if step else 1]); ea += 1

    # analyze ticks: visible cells + gap-below-vmax excursions.
    vis = [t for t in ticks if t is not None]
    if not vis:
        print("NO mover ever observed during loiter; ticks", len(ticks)); return
    vmax = max(c[1] for c in vis)  # deepest visible track y
    vmin = min(c[1] for c in vis)  # shallowest visible track y
    xcol = vis[0][0]
    # gaps: runs of None between two vmax-sightings = down excursions.
    gaps = []
    last_vmax_i = None
    for i, t in enumerate(ticks):
        if t is not None and t[1] == vmax:
            if last_vmax_i is not None:
                seg = ticks[last_vmax_i + 1:i]
                if seg and all(s is None for s in seg):
                    gaps.append(len(seg) + 1)  # ticks from vmax-exit to vmax-return
            last_vmax_i = i
    print(f"phase2 ea={ea} ticks={len(ticks)} vmax={vmax} vmin={vmin} gaps_below={gaps}", flush=True)
    if not gaps or len(set(gaps)) > 1:
        print(f"FALSIFIED/insufficient: gaps inconsistent={gaps} -> park"); return
    g = gaps[0]
    cells_below = g // 2
    bottom = vmax + cells_below * _CELL
    # top: assume vmin is the top endpoint (visible bounce). Build full track.
    track = {(xcol, y) for y in range(vmin, bottom + 1, _CELL)}
    print(f"INFERRED track: top={vmin} bottom={bottom} cells={sorted(y for _, y in track)}", flush=True)
    print(f"GT track: x=54 y=5..30 (cells 5,10,15,20,25,30)", flush=True)

    # PHASE 3: build maze + plan. Current mover state from the last visible tick +
    # extrapolation is complex; instead re-observe one settled frame for a fresh
    # mover sighting, set (pos,dir) from the last two visible ticks.
    grid = grid_now()
    av = None
    for _ in range(6):
        if grid and len(grid) >= 64:
            av = parse_disc(grid, mem)
            if av is not None:
                break
        obs[0] = env.step(A[1]); grid = grid_now()
    if av is None:
        av = (g.gudziatsk.x, g.gudziatsk.y)
    walls = frozenset(c for c, t in mem.static.items() if t == "wall")
    refills = frozenset(c for c, t in mem.static.items() if t == "refill")
    static_changers = {c: "shape" for c in mem.changer_cells["shape"]}
    static_changers.update({c: "color" for c in mem.changer_cells["color"]})
    # mover current cell+dir from last two distinct visible ticks
    vseq = [t for t in ticks if t is not None]
    mcur = vseq[-1]
    mdir = 0
    DV = {0: (0, 1), 1: (1, 0), 2: (0, -1), 3: (-1, 0)}
    for j in range(len(vseq) - 1, 0, -1):
        v = (vseq[j][0] - vseq[j - 1][0], vseq[j][1] - vseq[j - 1][1])
        for d, (dx, dy) in DV.items():
            if (dx * _CELL, dy * _CELL) == v:
                mdir = d; break
        else:
            continue
        break
    band = _band_life(grid)
    m = {
        "goal": mem.goal, "req": mem.goal_req, "walls": walls, "refills": refills,
        "static_changers": static_changers, "mover_kind": "rot",
        "track": frozenset(track), "pushwalls": mem.pushwalls,
        "fj": frozenset(set(walls) | {mem.goal}), "step_full": _STEP_FULL // 2,
    }
    sh, co, ro = mem.token
    start = (av[0], av[1], sh, co, ro, band, frozenset(), (mcur[0], mcur[1], mdir))
    print(f"phase3 start={start} GT mover=({g.wsoslqeku[0]._sprite.x},{g.wsoslqeku[0]._sprite.y},{g.wsoslqeku[0]._dir})", flush=True)
    plan = sim_bfs(m, start)
    print("plan_len", len(plan) if plan else None, "total_ea", ea, flush=True)
    if not plan:
        print("NO PLAN"); return
    for i, act in enumerate(plan):
        obs[0] = env.step(A[act])
        if obs[0] is None:
            break
        if str(obs[0].state).endswith("WIN") or obs[0].levels_completed >= 7:
            print(f"*** LIVE L7 WIN at action {i+1}/{len(plan)} (ea={ea}) ***", flush=True); return
    print("replay ended; levels", obs[0].levels_completed, "state", obs[0].state, flush=True)


if __name__ == "__main__":
    main()
