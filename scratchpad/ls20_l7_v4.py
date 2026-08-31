"""L7 fog: FULL-VIEW-COLUMN loiter with REFILL-CHAIN (fresh angle). Frame-only.
Phase 1 reveal static maze (fog-disc mask). Phase 2 navigate to the mover-column
observation posts (xm-5) and LOITER with refill-chain, capturing the mover's full
vertical track (min..max y) directly (posts (xm-5,*) see the whole column). Phase 3
build maze + joint BFS + open-loop replay to a live L7 win.
"""
from __future__ import annotations
import sys
from collections import deque
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.ls20 import Adapter
from admorphiq.adapters25.base import canonical_layer
from ls20_l7_v2 import (
    Mem, parse_disc, passable_of, _band_life, nav_life_aware, cell_vis,
    sim_bfs, bfs_path, MOVES, A, _CELL, _STEP_FULL,
)


def grid_of(obs):
    return tuple(tuple(r) for r in canonical_layer(obs))


def reveal_static(env, obs_box, mem, cap=140):
    ea = 0
    for _ in range(cap):
        grid = grid_of(obs_box[0])
        if not grid or len(grid) < 64:
            obs_box[0] = env.step(A[1]); ea += 1; continue
        av = parse_disc(grid, mem)
        if av is None:
            obs_box[0] = env.step(A[1]); ea += 1; continue
        have = (mem.goal and mem.goal_req and mem.changer_cells["shape"]
                and mem.changer_cells["color"] and mem.changer_cells["rot"])
        pss = passable_of(mem) | {av}
        path, tgt = bfs_path(pss, av,
            lambda c: any((c[0]+dx*_CELL, c[1]+dy*_CELL) not in mem.static
                          and 0 <= c[1]+dy*_CELL < 55 for dx, dy in
                          ((0,-1),(0,1),(-1,0),(1,0))))
        if have and (path is None or len(path) > 4):
            return ea, av
        if path is None:
            return ea, av
        if not path:
            done = False
            for aid, (dx, dy) in MOVES.items():
                nb = (av[0]+dx*_CELL, av[1]+dy*_CELL)
                if nb not in mem.static:
                    obs_box[0] = env.step(A[aid]); ea += 1; done = True; break
            if not done:
                obs_box[0] = env.step(A[1]); ea += 1
        else:
            obs_box[0] = env.step(A[path[0]]); ea += 1
    return ea, av


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("ls20")
    obs_box = [env.observation_space]
    g = env._game
    ad = Adapter(giveup=9000)
    s = 0
    while s < 9000 and obs_box[0].levels_completed < 6:
        a = ad.choose_action([], obs_box[0])
        obs_box[0] = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1

    mem = Mem()
    ea, av = reveal_static(env, obs_box, mem)
    rot_seed = sorted(mem.changer_cells["rot"])
    print(f"P1 reveal ea={ea} av={av} goal={mem.goal} req={mem.goal_req} "
          f"shape={sorted(mem.changer_cells['shape'])} color={sorted(mem.changer_cells['color'])} "
          f"rot_seed={rot_seed} refills={sorted(c for c,t in mem.static.items() if t=='refill')}", flush=True)
    if not (mem.goal and mem.goal_req and mem.changer_cells["rot"]):
        print("P1 incomplete -> abort"); return

    # mover column = x of any observed rot cell (vertical track on L7)
    xm = rot_seed[0][0]
    full = _STEP_FULL // 2
    refills = {c for c, t in mem.static.items() if t == "refill"}

    # Phase 2: loiter at posts on column xm-5 (they see the whole vertical track),
    # refill-chained, collecting mover y until min/max stable for a full period.
    obs_y_seen = set()
    rot_seq = []             # ordered observed mover cells (for pos/dir at end)
    stable = 0
    STABLE_NEED = 14
    for _ in range(600):
        grid = grid_of(obs_box[0])
        if not grid or len(grid) < 64:
            obs_box[0] = env.step(A[1]); ea += 1; continue
        av = parse_disc(grid, mem)
        if av is None:
            obs_box[0] = env.step(A[1]); ea += 1; continue
        pss = passable_of(mem)
        band = _band_life(grid)
        rot_vis = [c for c in mem.changer_cells["rot"] if cell_vis(c[0], c[1], av[0], av[1])]
        # observation posts: reachable passable column xm-5 cells (see whole track)
        posts = {c for c in pss if c[0] == xm - _CELL}
        if not posts:  # fall back: any passable cell adjacent to column that sees a rot cell
            posts = {c for c in pss if c[0] in (xm - _CELL, xm + _CELL)
                     and any(cell_vis(t[0], t[1], c[0], c[1]) for t in mem.changer_cells["rot"])}
        at_post = av in posts
        if at_post and band > 4:
            # record this tick's mover sighting
            if rot_vis:
                mc = min(rot_vis, key=lambda c: c[1])  # single mover; pick any
                if mc[0] == xm:
                    prev_minmax = (min(obs_y_seen), max(obs_y_seen)) if obs_y_seen else None
                    obs_y_seen.add(mc[1])
                    if not rot_seq or rot_seq[-1] != mc:
                        rot_seq.append(mc)
                    new_minmax = (min(obs_y_seen), max(obs_y_seen))
                    stable = 0 if prev_minmax != new_minmax else stable + 1
                else:
                    stable += 1
            else:
                stable += 1
            if len(obs_y_seen) >= 2 and stable >= STABLE_NEED:
                break
            # oscillate to an adjacent post (a successful move advances the mover)
            nxt = None
            for aid, (dx, dy) in MOVES.items():
                nb = (av[0]+dx*_CELL, av[1]+dy*_CELL)
                if nb in posts and nb != mem.goal:
                    nxt = aid; break
            obs_box[0] = env.step(A[nxt if nxt else 1]); ea += 1
            continue
        # navigate: if low life head to a refill, else toward a post
        if band <= 4 and refills:
            nav = nav_life_aware(pss, refills, av, refills, band, full)
        else:
            nav = nav_life_aware(pss, refills, av, posts, band, full)
        if nav:
            obs_box[0] = env.step(A[nav]); ea += 1
        else:
            path, _ = bfs_path(pss | {av}, av, lambda c: c in posts)
            obs_box[0] = env.step(A[path[0] if path else 1]); ea += 1

    track = frozenset((xm, y) for y in range(min(obs_y_seen), max(obs_y_seen)+1, _CELL))
    print(f"P2 ea={ea} obs_y={sorted(obs_y_seen)} track={sorted(track)} "
          f"GT track=x54 y5..30 rot_seq_tail={rot_seq[-6:]}", flush=True)

    # Phase 3: build maze from current live state + captured track, plan, replay.
    grid = grid_of(obs_box[0])
    for _ in range(6):
        if grid and len(grid) >= 64 and parse_disc(grid, mem) is not None:
            break
        obs_box[0] = env.step(A[1]); ea += 1; grid = grid_of(obs_box[0])
    av = parse_disc(grid, mem)
    walls = frozenset(c for c, t in mem.static.items() if t == "wall")
    static_changers = {c: "shape" for c in mem.changer_cells["shape"]}
    static_changers.update({c: "color" for c in mem.changer_cells["color"]})
    mcur = rot_seq[-1]
    mdir = 0
    DV = {0:(0,1),1:(1,0),2:(0,-1),3:(-1,0)}
    for j in range(len(rot_seq)-1, 0, -1):
        v = (rot_seq[j][0]-rot_seq[j-1][0], rot_seq[j][1]-rot_seq[j-1][1])
        for d,(dx,dy) in DV.items():
            if (dx*_CELL, dy*_CELL) == v: mdir = d; break
        else: continue
        break
    band = _band_life(grid)
    m = {"goal": mem.goal, "req": mem.goal_req, "walls": walls, "refills": refills,
         "static_changers": static_changers, "mover_kind": "rot", "track": track,
         "pushwalls": mem.pushwalls, "fj": frozenset(set(walls) | {mem.goal}),
         "step_full": _STEP_FULL // 2}
    sh, co, ro = mem.token
    start = (av[0], av[1], sh, co, ro, band, frozenset(), (mcur[0], mcur[1], mdir))
    print(f"P3 start={start} mdir={mdir} band_life={band}")
    print(f"GT mover=({g.wsoslqeku[0]._sprite.x},{g.wsoslqeku[0]._sprite.y},{g.wsoslqeku[0]._dir}) "
          f"GT av=({g.gudziatsk.x},{g.gudziatsk.y}) tok=({g.fwckfzsyc},{g.hiaauhahz},{g.cklxociuu})", flush=True)
    plan = sim_bfs(m, start)
    print("plan_len", len(plan) if plan else None, "explore_ea", ea, flush=True)
    if not plan:
        print("NO PLAN"); return
    for i, act in enumerate(plan):
        obs_box[0] = env.step(A[act])
        if obs_box[0] is None: break
        if str(obs_box[0].state).endswith("WIN") or obs_box[0].levels_completed >= 7:
            print(f"*** LIVE L7 WIN action {i+1}/{len(plan)} explore={ea} total={ea+i+1} ***", flush=True); return
    print("replay ended; levels", obs_box[0].levels_completed, "state", obs_box[0].state, flush=True)


if __name__ == "__main__":
    main()
