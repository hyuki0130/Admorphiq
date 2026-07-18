"""L7 core-claim proof: seed the static maze (walls/floor/refills/goal/changers)
from GT — isolating the fog-REVEAL sub-problem — then run the REAL fogged
refill-chained loiter at full-view posts to capture the mover track, plan, and
replay to a live win. If this wins, the observation-post mechanic is proven and
only the reveal remains."""
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



def carry_dist_pw(fj, sx, sy, dx, dy, w=_CELL, h=_CELL):
    for k in range(1, 12):
        if (sx + dx + dx * w * k, sy + dy + dy * h * k) in fj:
            return max(0, k - 1)
    return 0


def apply_push(cell, pushwalls, fj):
    ax, ay = cell
    for (sx, sy), (pdx, pdy) in pushwalls.items():
        if ax < sx + _CELL and sx < ax + _CELL and ay < sy + _CELL and sy < ay + _CELL:
            dist = carry_dist_pw(fj, sx, sy, pdx, pdy)
            if dist > 0:
                return (ax + pdx * _CELL * dist, ay + pdy * _CELL * dist)
            break
    return (ax, ay)


def nav_life_pw(pss, walls, pushwalls, fj, refills, goal, start, targets, life, full):
    """Life+pushwall+refill-aware BFS to any target; returns first action or None.
    Pushwall slides are applied so routing avoids the deflection zone."""
    from collections import deque as _dq
    if not targets:
        return None
    seen = {(start, life, frozenset())}
    q = _dq([(start, life, frozenset(), [])])
    while q:
        cell, lf, taken, path = q.popleft()
        if cell in targets and path:
            return path[0]
        if lf <= 0:
            continue
        for aid, (dx, dy) in MOVES.items():
            nb = (cell[0] + dx * _CELL, cell[1] + dy * _CELL)
            if nb in walls or nb == goal or nb not in pss:
                continue
            nb = apply_push(nb, pushwalls, fj)
            if nb not in pss:
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



def fresh_rot_cells(grid, av, xm):
    """Mover's CURRENT rot-icon cell(s) read FRESH from this frame (unpolluted by
    accumulated memory). On L7 the mover is the only rot icon, so this returns its
    single current cell. Scans the fog disc, classifies rot at column xm."""
    from admorphiq.adapters25.ls20 import _cell_counts, _classify_changer, _FLOOR_COLOR
    out = []
    ax, ay = av
    for y in range(0, 55, _CELL):
        c = (xm, y)
        if not cell_vis(xm, y, ax, ay):
            continue
        hh = _cell_counts(grid, xm, y)
        dom = hh.most_common(1)[0][0]
        if _classify_changer(hh, dom) == "rot":
            out.append((xm, y))
    return out


def grid_of(obs):
    return tuple(tuple(r) for r in canonical_layer(obs))


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
    # ---- SEED static maze from GT (isolates the reveal sub-problem) ----
    lvl = g.current_level
    OX, OY = 4, 0
    def snap(x, y): return (x - (x - OX) % _CELL, y - (y - OY) % _CELL)
    walls = {(sp.x, sp.y) for sp in lvl.get_sprites_by_tag("ihdgageizm")}
    for x in range(OX, 60, _CELL):
        for y in range(OY, 55, _CELL):
            mem.static[(x, y)] = "wall" if (x, y) in walls else "floor"
    for sp in lvl.get_sprites_by_tag("npxgalaybz"):
        mem.static[snap(sp.x, sp.y)] = "refill"
    mem.goal = (29, 50); mem.goal_req = (0, 3, 2)
    mem.static[mem.goal] = "goal"
    mem.changer_cells["shape"].add((19, 40)); mem.static[(19, 40)] = "floor"
    mem.changer_cells["color"].add((9, 40)); mem.static[(9, 40)] = "floor"
    mem.token = (g.fwckfzsyc, g.hiaauhahz, g.cklxociuu)
    # pushwalls seed (from GT sprite direction suffix)
    from admorphiq.adapters25.ls20 import _detect_pushwalls_pixel
    # keep pushwalls empty-seeded; they'll be filled from the frame during loiter
    xm = 54  # mover column (would be learned when the mover is first seen)

    full = _STEP_FULL // 2
    ea = 0
    obs_y = set(); rot_seq = []
    saw_rev = {"min": False, "max": False}  # mover reversal seen at each endpoint
    consumed = set()  # refills already collected on the current life
    home = None       # the level-start cell (where a death/reset returns the avatar)
    prev_band = None  # to detect a reset (band jumps from ~0 up to full)
    prev_av = None

    def step(aid):
        nonlocal ea
        box[0] = env.step(A[aid]); ea += 1

    for _ in range(900):
        grid = grid_of(box[0])
        if not grid or len(grid) < 64:
            step(1); continue
        av = parse_disc(grid, mem)   # updates token, pushwalls, refresh (floor-preferring)
        if av is None:
            step(1); continue
        band_now = _band_life(grid)
        refills_all = {c for c, t in mem.static.items() if t == "refill"}
        # track consumed refills (for a faithful plan anchor): a refill is consumed
        # when the avatar stands on it and the band jumps up. A death restores ALL
        # refills (band jumps to full while NOT on a refill) -> clear consumed.
        if prev_band is not None and band_now > prev_band:
            if av in refills_all:
                consumed.add(av)
            elif band_now >= full - 1:
                consumed.clear()
                home = av  # the reset returns the avatar to the level start
        prev_band = band_now
        prev_av = av
        pss = passable_of(mem)
        refills = {c for c, t in mem.static.items() if t == "refill"}
        band = _band_life(grid)
        posts = {c for c in pss if c[0] == xm - _CELL}
        if av[0] >= 44:
            print(f'    near ea={ea} av={av} band={band} at_post={av in posts} '
                  f'rotvis={[c for c in mem.changer_cells["rot"] if c[0]==xm and cell_vis(c[0],c[1],av[0],av[1])]}', flush=True)
        rot_vis = fresh_rot_cells(grid, av, xm)
        at_post = av in posts
        if at_post and band > 3:
            if len(rot_vis) == 1:
                mc = rot_vis[0]
                obs_y.add(mc[1])
                if not rot_seq or rot_seq[-1] != mc:
                    rot_seq.append(mc)
                # confirm both endpoints via direction reversals: the track extent
                # is known once the mover has bounced (reversed) at BOTH its lowest
                # and highest observed cell. This finishes within one bounce period
                # (much sooner than a fixed stable-count), keeping the life budget.
                if len(rot_seq) >= 3:
                    a, b, c = rot_seq[-3][1], rot_seq[-2][1], rot_seq[-1][1]
                    if a < b > c:
                        saw_rev["max"] = True
                    if a > b < c:
                        saw_rev["min"] = True
            if len(obs_y) >= 2 and saw_rev["min"] and saw_rev["max"]:
                break
            nxt = None
            for aid, (dx, dy) in MOVES.items():
                nb = (av[0] + dx * _CELL, av[1] + dy * _CELL)
                if nb in posts and nb != mem.goal:
                    nxt = aid; break
            step(nxt if nxt else 1); continue
        tgt = refills if (band <= 3 and refills) else posts
        wallset0 = frozenset(c for c, ty in mem.static.items() if ty == 'wall')
        fj0 = frozenset(set(wallset0) | {mem.goal})
        nav = nav_life_pw(pss, wallset0, mem.pushwalls, fj0, refills, mem.goal, av, tgt, band, full)
        if ea < 40:
            print(f'  ea={ea} av={av} band={band} nav={nav} npss={len(pss)} '
                  f'tgt_is_refills={tgt is refills} nposts={len(posts)}', flush=True)
        if nav is not None:
            step(nav); continue
        path, _ = bfs_path(pss | {av}, av, lambda c: c in posts)
        step(path[0] if path else 1)
        if ea % 50 == 0:
            print(f"  ea={ea} av={av} band={band} obs_y={sorted(obs_y)} at_post={at_post}", flush=True)

    if not obs_y:
        print(f"NO MOVER captured ea={ea} rot={sorted(mem.changer_cells['rot'])}"); return
    track = frozenset((xm, y) for y in range(min(obs_y), max(obs_y) + 1, _CELL))
    print(f"CAPTURE ea={ea} obs_y={sorted(obs_y)} track={sorted(track)}", flush=True)

    # --- plan from the CURRENT live state (no death). The avatar at a full-view
    #     column post directly SEES the mover, so its true phase reads fresh; the
    #     refills consumed on this life are tracked (`consumed`) for a faithful
    #     anchor. Proven: (49,20) band>=7 taken={(49,5)} -> replayable plan. ---
    wallset = frozenset(c for c, t in mem.static.items() if t == "wall")
    fj = frozenset(set(wallset) | {mem.goal})
    refills = {c for c, t in mem.static.items() if t == "refill"}
    static_changers = {c: "shape" for c in mem.changer_cells["shape"]}
    static_changers.update({c: "color" for c in mem.changer_cells["color"]})
    m = {"goal": mem.goal, "req": mem.goal_req, "walls": wallset, "refills": frozenset(refills),
         "static_changers": static_changers, "mover_kind": "rot", "track": track,
         "pushwalls": mem.pushwalls, "fj": fj, "step_full": _STEP_FULL // 2}

    def read_mover():
        grid = grid_of(box[0])
        av = parse_disc(grid, mem)
        if av is None:
            return None, None, None
        rc = fresh_rot_cells(grid, av, xm)
        return av, (rc[0] if len(rc) == 1 else None), _band_life(grid)

    fullview = {c for c in passable_of(mem) if c[0] == xm - _CELL
                and all(cell_vis(t[0], t[1], c[0], c[1]) for t in track)}

    # hop (minimal, life-aware) to a full-view post so the mover reads cleanly
    for _ in range(20):
        av, _mc, band = read_mover()
        if av is None:
            step(1); continue
        if av in fullview:
            break
        nav = nav_life_pw(passable_of(mem), wallset, mem.pushwalls, fj, refills,
                          mem.goal, av, fullview, band, full)
        if nav is None:
            break
        step(nav)
        if av in refills:
            consumed.discard(av)  # already accounted; re-collect only tops life
        if band < _band_life(grid_of(box[0])) and av in refills:
            consumed.add(av)

    # mover pos fresh + dir over one obs move (band budget allows; threshold is 7)
    av, m0, band = read_mover()
    for aid, (dx, dy) in MOVES.items():
        nb = (av[0] + dx * _CELL, av[1] + dy * _CELL)
        if nb in fullview and nb != mem.goal:
            step(aid); break
    av, m1, band = read_mover()
    mdir = 0
    if m0 and m1 and m0 != m1:
        v = (m1[0] - m0[0], m1[1] - m0[1])
        for d, (dx, dy) in DV.items():
            if (dx * _CELL, dy * _CELL) == v: mdir = d; break
    mover = m1 or m0
    sh, co, ro = mem.token
    taken = frozenset(consumed)
    start = (av[0], av[1], sh, co, ro, band, taken, (mover[0], mover[1], mdir))
    print(f"PLAN start={start} consumed={sorted(consumed)} pushwalls={mem.pushwalls} "
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
    return

    # --- (unused legacy death-reset path retained below for reference) ---
    # --- read the mover's CURRENT (pos, dir) fresh, over two successive obs moves,
    #     while at a mover-visible post. Then blocked-die to reset to a clean start
    #     (avatar->start, token->start, all refills restored) while the mover stays
    #     FROZEN (blocked moves undo the mover step), so we plan from a fully-known
    #     deterministic anchor + the frozen mover state.
    def read_mover():
        grid = grid_of(box[0])
        av = parse_disc(grid, mem)
        if av is None:
            return None, None
        rc = fresh_rot_cells(grid, av, xm)
        return av, (rc[0] if len(rc) == 1 else None)

    av, m0 = read_mover()
    # one successful oscillation move to get the mover direction
    posts = {c for c in passable_of(mem) if c[0] == xm - _CELL}
    m1, mdir = m0, 0
    for aid, (dx, dy) in MOVES.items():
        nb = (av[0] + dx * _CELL, av[1] + dy * _CELL)
        if nb in posts and nb != mem.goal:
            step(aid); break
    av2, m1b = read_mover()
    if m0 and m1b and m0 != m1b:
        v = (m1b[0] - m0[0], m1b[1] - m0[1])
        for d, (dx, dy) in DV.items():
            if (dx * _CELL, dy * _CELL) == v: mdir = d; break
        m1 = m1b
    elif m1b:
        m1 = m1b
    print(f"mover read m0={m0} m1={m1} mdir={mdir}", flush=True)

    # blocked-die: press into a known wall (mover frozen) until the reset returns
    # the avatar to the start with full life.
    wallset = frozenset(c for c, t in mem.static.items() if t == "wall")
    start_cell = None
    for _ in range(60):
        grid = grid_of(box[0])
        av = parse_disc(grid, mem)
        band = _band_life(grid)
        if av is not None and band >= (_STEP_FULL // 2) - 1 and start_cell is not None and av == start_cell:
            break  # reset detected (back at start, life refilled)
        if av is not None and start_cell is None and band <= 2:
            start_cell = None  # will capture start after reset
        # choose a blocked direction (neighbour is a known wall)
        die = None
        if av is not None:
            for aid, (dx, dy) in MOVES.items():
                nb = (av[0] + dx * _CELL, av[1] + dy * _CELL)
                if nb in wallset:
                    die = aid; break
        step(die if die else 3)
        grid = grid_of(box[0]); av = parse_disc(grid, mem); band = _band_life(grid)
        if av is not None and band >= (_STEP_FULL // 2) - 1:
            start_cell = av
    grid = grid_of(box[0])
    for _ in range(6):
        av = parse_disc(grid, mem)
        if av is not None and _band_life(grid) >= (_STEP_FULL // 2) - 1:
            break
        # settle without advancing the mover: press into a wall (blocked)
        die = None
        if av is not None:
            for aid, (dx, dy) in MOVES.items():
                if (av[0] + dx * _CELL, av[1] + dy * _CELL) in wallset:
                    die = aid; break
        step(die if die else 3); grid = grid_of(box[0])
    av = parse_disc(grid, mem)
    band = _band_life(grid)
    sh, co, ro = mem.token
    print(f"post-reset av={av} token=({sh},{co},{ro}) band={band} "
          f"GT_av=({g.gudziatsk.x},{g.gudziatsk.y}) GT_tok=({g.fwckfzsyc},{g.hiaauhahz},{g.cklxociuu}) "
          f"GT_mv=({g.wsoslqeku[0]._sprite.x},{g.wsoslqeku[0]._sprite.y},{g.wsoslqeku[0]._dir})", flush=True)

    refillset = frozenset(c for c, t in mem.static.items() if t == "refill")
    static_changers = {c: "shape" for c in mem.changer_cells["shape"]}
    static_changers.update({c: "color" for c in mem.changer_cells["color"]})
    m = {"goal": mem.goal, "req": mem.goal_req, "walls": wallset, "refills": refillset,
         "static_changers": static_changers, "mover_kind": "rot", "track": track,
         "pushwalls": mem.pushwalls, "fj": frozenset(set(wallset) | {mem.goal}),
         "step_full": _STEP_FULL // 2}
    start = (av[0], av[1], sh, co, ro, band, frozenset(), (m1[0], m1[1], mdir))
    print(f"PLAN start={start} pushwalls={mem.pushwalls}", flush=True)
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
