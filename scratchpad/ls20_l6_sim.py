"""L6 GT-validation: multi-goal (either-order) + 3-synchronous-mover pixel sim +
joint BFS + live replay. Proves the model+search before any runtime detection.

Movers advance SYNCHRONOUSLY once per successful avatar move (engine steps all
wsoslqeku then undoes all on a block). Each mover follows dboxixicic.npdjlrkhsg
over its track region (horizontal for rot/shape, 2D for color). Multi-goal:
landing on an unsatisfied goal with its matching token satisfies+removes it; win
when all satisfied.
"""
from __future__ import annotations
import sys
from collections import deque
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.ls20 import Adapter

CELL = 5
A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4}
MOVES = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
# nakogfhyus: dir 0->(0,1) down, 1->(1,0) right, 2->(0,-1) up, 3->(-1,0) left
DIRVEC = {0: (0, 1), 1: (1, 0), 2: (0, -1), 3: (-1, 0)}


def build_movers(g):
    """Each mover: (kind, frozenset(on-track cells), (x,y,dir))."""
    tagkind = {"ttfwljgohq": "shape", "soyhouuebz": "color", "rhsxkxzdjz": "rot"}
    out = []
    for m in g.wsoslqeku:
        sp, tr = m._sprite, m.bfdcztirdu
        kind = next(k for t, k in tagkind.items() for s in g.current_level.get_sprites_by_tag(t) if s is sp)
        cells = set()
        for cx in range(tr.x, tr.x + tr.width, CELL):
            for cy in range(tr.y, tr.y + tr.height, CELL):
                ax, ay = cx - tr.x, cy - tr.y
                if 0 <= ax < tr.width and 0 <= ay < tr.height and int(tr.pixels[ay, ax]) >= 0:
                    cells.add((cx, cy))
        out.append((kind, frozenset(cells), (sp.x, sp.y, m._dir)))
    return out


def mover_step(cells, state):
    """One dboxixicic step over the track cells. Returns new (x,y,dir)."""
    x, y, d = state
    for cand in (d, (d - 1) % 4, (d + 1) % 4, (d + 2) % 4):
        dx, dy = DIRVEC[cand]
        nx, ny = x + dx * CELL, y + dy * CELL
        if (nx, ny) in cells:
            return (nx, ny, cand)
    return (x, y, d)


def build_static(g):
    lvl = g.current_level
    hard = frozenset((s.x, s.y) for s in lvl.get_sprites_by_tag("ihdgageizm"))
    goals = tuple((gg.x, gg.y) for gg in g.plrpelhym)
    reqs = tuple((g.ldxlnycps[i], g.yjdexjsoa[i], g.ehwheiwsk[i]) for i in range(len(g.plrpelhym)))
    ax0, ay0 = g.gudziatsk.x, g.gudziatsk.y
    ox, oy = ax0 % CELL, ay0 % CELL
    refills = frozenset(
        (s.x - (s.x - ox) % CELL, s.y - (s.y - oy) % CELL)
        for s in lvl.get_sprites_by_tag("npxgalaybz")
    )
    push = tuple((w.sprite.x, w.sprite.y, w.dx, w.dy, w.width, w.height) for w in g.hasivfwip)
    fj = frozenset(set(hard) | set(goals))
    return hard, goals, reqs, refills, push, fj


def carry_dist(fj, sx, sy, dx, dy, w, h):
    wcx, wcy = sx + dx, sy + dy
    for k in range(1, 12):
        if (wcx + dx * w * k, wcy + dy * h * k) in fj:
            return max(0, k - 1)
    return 0


def step(static, movers_cells, s, action):
    hard, goals, reqs, refills, push, fj, full = static
    ax, ay, sh, co, ro, steps, taken, mstates, satisfied = s
    dx, dy = MOVES[action]
    prov = tuple(mover_step(movers_cells[i], mstates[i]) for i in range(len(mstates)))
    nx, ny = ax + dx * CELL, ay + dy * CELL
    # goal blocks unless it is unsatisfied-but-matching OR already satisfied(removed)
    blocked = (nx, ny) in hard
    for gi, gc in enumerate(goals):
        if (nx, ny) == gc and gi not in satisfied:
            if (sh, co, ro) != reqs[gi]:
                blocked = True
    if blocked:
        return s  # mover undoes -> unchanged
    ax, ay = nx, ny
    # changer effect: mover on its NEW cell
    for i, (kind, cells) in enumerate(movers_cells_kind(movers_cells)):
        pass
    # apply mover changer if avatar landed on a mover's new cell
    for i in range(len(prov)):
        mk = MOVER_KINDS[i]
        if (ax, ay) == (prov[i][0], prov[i][1]):
            if mk == "rot":
                ro = (ro + 1) % 4
            elif mk == "color":
                co = (co + 1) % 4
            elif mk == "shape":
                sh = (sh + 1) % 6
    nsteps = steps - 1
    if (ax, ay) in refills and (ax, ay) not in taken:
        nsteps = full
        taken = taken | {(ax, ay)}
    if nsteps >= 0:
        for (sx, sy, pdx, pdy, w, h) in push:
            if ax < sx + w and sx < ax + CELL and ay < sy + h and sy < ay + CELL:
                dist = carry_dist(fj, sx, sy, pdx, pdy, w, h)
                if dist > 0:
                    ax += pdx * w * dist
                    ay += pdy * h * dist
                    break
    # multi-goal satisfaction
    nsat = satisfied
    for gi, gc in enumerate(goals):
        if gi not in satisfied and (ax, ay) == gc and (sh, co, ro) == reqs[gi]:
            nsat = satisfied | {gi}
    return (ax, ay, sh, co, ro, nsteps, taken, prov, nsat)


MOVER_KINDS = []


def movers_cells_kind(mc):
    return []


def bfs(static, movers_cells, start, cap=6_000_000):
    ngoals = len(static[1])
    seen = {start}
    q = deque([(start, [])])
    exp = 0
    while q and exp < cap:
        s, path = q.popleft()
        exp += 1
        if s[5] <= 0:
            continue
        for act in (1, 2, 3, 4):
            ns = step(static, movers_cells, s, act)
            if ns[5] < 0 or ns == s or ns in seen:
                continue
            if len(ns[8]) == ngoals:
                return path + [act], exp
            seen.add(ns)
            q.append((ns, path + [act]))
    return None, exp


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
    obs = env.step(GameAction.ACTION1)
    hard, goals, reqs, refills, push, fj = build_static(g)
    full = g._step_counter_ui.osgviligwp // g._step_counter_ui.efipnixsvl
    cur = g._step_counter_ui.current_steps // g._step_counter_ui.efipnixsvl
    static = (hard, goals, reqs, refills, push, fj, full)
    movers = build_movers(g)
    global MOVER_KINDS
    MOVER_KINDS = [m[0] for m in movers]
    movers_cells = [m[1] for m in movers]
    mstates = tuple(m[2] for m in movers)
    start = (g.gudziatsk.x, g.gudziatsk.y, g.fwckfzsyc, g.hiaauhahz, g.cklxociuu,
             cur, frozenset(), mstates, frozenset())
    print("goals", goals, "reqs", reqs, "kinds", MOVER_KINDS, "full", full, "cur", cur)
    print("mover tracks sizes", [len(c) for c in movers_cells], "mstates", mstates)
    plan, exp = bfs(static, movers_cells, start)
    print(f"BFS exp={exp} plan_len={len(plan) if plan else None}")
    if not plan:
        print("NO PLAN")
        return
    for i, act in enumerate(plan):
        obs = env.step(A[act])
        if obs is None:
            print("obs None"); break
        if str(obs.state).endswith("WIN") or obs.levels_completed >= 6:
            print(f"*** LIVE L6 WIN at action {i+1}/{len(plan)} (levels_completed={obs.levels_completed}) ***")
            return
    print("replay ended; levels", obs.levels_completed, "state", obs.state)


if __name__ == "__main__":
    main()
