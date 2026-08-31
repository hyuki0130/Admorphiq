"""L7 fog e2e v5: floor-preferring reveal + explore-to-mover + refill-chained
loiter at full-view posts (column xm-5) + joint BFS + open-loop replay.
Single adaptive loop. Frame-only (GT read only for a final sanity print)."""
from __future__ import annotations
import sys
from collections import deque
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.ls20 import Adapter
from admorphiq.adapters25.base import canonical_layer
from ls20_l7_v2 import (
    Mem, parse_disc, passable_of, _band_life, nav_life_aware, cell_vis,
    sim_bfs, bfs_path, MOVES, A, _CELL, _STEP_FULL,
)

DV = {0: (0, 1), 1: (1, 0), 2: (0, -1), 3: (-1, 0)}
NB4 = ((0, -1), (0, 1), (-1, 0), (1, 0))


def grid_of(obs):
    return tuple(tuple(r) for r in canonical_layer(obs))


def frontier_cells(mem, pss):
    """Revealed floor cells with an unrevealed in-arena neighbour."""
    out = set()
    for c in pss:
        for dx, dy in NB4:
            nb = (c[0] + dx * _CELL, c[1] + dy * _CELL)
            if nb not in mem.static and 4 <= nb[0] < 60 and 0 <= nb[1] < 55:
                out.add(c)
                break
    return out


def run():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("ls20")
    box = [env.observation_space]
    g = env._game
    ad = Adapter(giveup=9000)
    s = 0
    while s < 9000 and box[0].levels_completed < 6:
        a = ad.choose_action([], box[0])
        box[0] = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1

    mem = Mem()
    full = _STEP_FULL // 2
    ea = 0
    obs_y = set()          # observed mover y values
    rot_seq = []           # ordered mover sightings
    stable = 0
    STABLE_NEED = 14
    phase = "explore"

    def step(aid):
        nonlocal ea
        box[0] = env.step(A[aid]); ea += 1

    for _ in range(1200):
        grid = grid_of(box[0])
        if not grid or len(grid) < 64:
            step(1); continue
        av = parse_disc(grid, mem)
        if av is None:
            step(1); continue
        pss = passable_of(mem)
        refills = {c for c, t in mem.static.items() if t == "refill"}
        band = _band_life(grid)
        rot_cells = set(mem.changer_cells["rot"])
        xm = min({c[0] for c in rot_cells}, default=None)

        if phase == "explore":
            if ea % 60 == 0:
                print(f"  [explore] ea={ea} av={av} maxx_rev={max((c[0] for c in pss), default=0)} "
                      f"posts_rev={sorted(c for c in pss if xm and c[0]==xm-_CELL)} xm={xm} band={band} "
                      f"revfloor={len(pss)}", flush=True)
            # found the mover column AND can define full-view posts? -> loiter
            if xm is not None:
                posts = {c for c in pss if c[0] == xm - _CELL}
                if av in posts or (posts and nav_life_aware(pss, refills, av, posts, band, full)):
                    phase = "loiter"
                    continue
            # else keep revealing: navigate life-aware to nearest frontier
            fr = frontier_cells(mem, pss)
            # bias toward the mover column region if xm known
            targets = ({c for c in pss if c[0] == xm - _CELL} if xm is not None else set()) or fr
            nav = nav_life_aware(pss, refills, av, targets, band, full) if targets else None
            if nav is None and refills and band <= 3:
                nav = nav_life_aware(pss, refills, av, refills, band, full)
            if nav is not None:
                step(nav); continue
            # no life-safe route: try a plain path to a frontier, else nudge
            path, _ = bfs_path(pss | {av}, av, lambda c: c in fr) if fr else (None, None)
            if path:
                step(path[0]); continue
            done = False
            for aid, (dx, dy) in MOVES.items():
                nb = (av[0] + dx * _CELL, av[1] + dy * _CELL)
                if nb not in mem.static and 4 <= nb[0] < 60 and 0 <= nb[1] < 55:
                    step(aid); done = True; break
            if not done:
                step(1)
            continue

        # ---- loiter: oscillate at full-view posts, refill-chain, capture track ----
        posts = {c for c in pss if c[0] == xm - _CELL}
        rot_vis = [c for c in rot_cells if cell_vis(c[0], c[1], av[0], av[1]) and c[0] == xm]
        at_post = av in posts
        if at_post and band > 3:
            if rot_vis:
                mc = rot_vis[0]
                pm = (min(obs_y), max(obs_y)) if obs_y else None
                obs_y.add(mc[1])
                if not rot_seq or rot_seq[-1] != mc:
                    rot_seq.append(mc)
                nm = (min(obs_y), max(obs_y))
                stable = 0 if pm != nm else stable + 1
            else:
                stable += 1
            if len(obs_y) >= 2 and stable >= STABLE_NEED:
                break
            nxt = None
            for aid, (dx, dy) in MOVES.items():
                nb = (av[0] + dx * _CELL, av[1] + dy * _CELL)
                if nb in posts and nb != mem.goal:
                    nxt = aid; break
            step(nxt if nxt else 1); continue
        # need life or not at a post: route to refill (if low) else to a post
        tgt = refills if (band <= 3 and refills) else posts
        nav = nav_life_aware(pss, refills, av, tgt, band, full)
        if nav is not None:
            step(nav); continue
        path, _ = bfs_path(pss | {av}, av, lambda c: c in posts)
        step(path[0] if path else 1)

    if not obs_y:
        print(f"NO MOVER captured (ea={ea}); rot_cells={sorted(mem.changer_cells['rot'])}"); return
    track = frozenset((xm, y) for y in range(min(obs_y), max(obs_y) + 1, _CELL))
    print(f"CAPTURE ea={ea} obs_y={sorted(obs_y)} track={sorted(track)} (GT x54 y5..30)", flush=True)

    # build maze + plan from current live state
    grid = grid_of(box[0])
    for _ in range(6):
        if grid and len(grid) >= 64 and parse_disc(grid, mem) is not None:
            break
        step(1); grid = grid_of(box[0])
    av = parse_disc(grid, mem)
    walls = frozenset(c for c, t in mem.static.items() if t == "wall")
    refills = frozenset(c for c, t in mem.static.items() if t == "refill")
    static_changers = {c: "shape" for c in mem.changer_cells["shape"]}
    static_changers.update({c: "color" for c in mem.changer_cells["color"]})
    mcur = rot_seq[-1]
    mdir = 0
    for j in range(len(rot_seq) - 1, 0, -1):
        v = (rot_seq[j][0] - rot_seq[j - 1][0], rot_seq[j][1] - rot_seq[j - 1][1])
        for d, (dx, dy) in DV.items():
            if (dx * _CELL, dy * _CELL) == v:
                mdir = d; break
        else:
            continue
        break
    band = _band_life(grid)
    m = {"goal": mem.goal, "req": mem.goal_req, "walls": walls, "refills": refills,
         "static_changers": static_changers, "mover_kind": "rot", "track": track,
         "pushwalls": mem.pushwalls, "fj": frozenset(set(walls) | {mem.goal}),
         "step_full": _STEP_FULL // 2}
    sh, co, ro = mem.token
    start = (av[0], av[1], sh, co, ro, band, frozenset(), (mcur[0], mcur[1], mdir))
    print(f"PLAN start={start} mdir={mdir} band={band} "
          f"GT_mv=({g.wsoslqeku[0]._sprite.x},{g.wsoslqeku[0]._sprite.y},{g.wsoslqeku[0]._dir}) "
          f"GT_av=({g.gudziatsk.x},{g.gudziatsk.y}) GT_tok=({g.fwckfzsyc},{g.hiaauhahz},{g.cklxociuu})", flush=True)
    plan = sim_bfs(m, start)
    print("plan_len", len(plan) if plan else None, "explore_ea", ea, flush=True)
    if not plan:
        print("NO PLAN"); return
    for i, act in enumerate(plan):
        box[0] = env.step(A[act])
        if box[0] is None: break
        if str(box[0].state).endswith("WIN") or box[0].levels_completed >= 7:
            print(f"*** LIVE L7 WIN action {i+1}/{len(plan)} explore={ea} total={ea+i+1} ***", flush=True); return
    print("replay ended; levels", box[0].levels_completed, "state", box[0].state, flush=True)


if __name__ == "__main__":
    run()
