"""End-to-end FRAME-ONLY L5 solve: observe the mover cycle, parse the maze
from the settled frame, joint-BFS over the pixel sim, execute open-loop —
replaying against the live engine to a real L5 win. No engine internals used
in the solve (GT only cross-checked in asserts).
"""
from __future__ import annotations
import sys
from collections import deque
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.ls20 import Adapter, _find_avatar, _decode_token
from admorphiq.adapters25.base import canonical_layer
from ls20_sim import Maze, SimState, step as sim_step, is_win
from ls20_parse5 import parse_l5

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4}


def read_life(grid):
    """current_steps from the colour-11-region band on rows 61-62 (filled cells
    = current_steps). Returns life in ACTIONS (== filled // decrement, decr=2)."""
    H = len(grid)
    row = 61 if H > 62 else H - 2
    # band cols start at 13; count 'filled' cells: the fill colour is whatever
    # dominates the leftmost run. Count cells != background(3) and != life-dots.
    from collections import Counter
    band = [grid[row][c] for c in range(13, 13 + 42) if c < len(grid[0])]
    cnt = Counter(band)
    # filled colour = most common non-3 among the first cells
    fill = None
    for v in band:
        if v != 3:
            fill = v
            break
    if fill is None:
        return 0
    filled = sum(1 for v in band if v == fill)
    return filled // 2


def observe_mover(env, get_grid, max_obs=10):
    """Issue safe successful moves; record the rot-changer (mover) cell each
    settled frame. Returns (track_cells, mx, mdir, obs_actions)."""
    positions = []  # (mx, my) in observation order
    actions = []
    last_av = None
    for _ in range(max_obs):
        grid = get_grid()
        p = parse_l5(grid)
        # mover = the rot-changer cell (only rot changer on L5 is the mover)
        rots = [c for c, k in p["changers"].items() if k == "rot"]
        if rots:
            positions.append(rots[0])
        av = p["avatar"]
        # pick a move that will succeed (changes avatar position): try each
        moved = False
        for act in (4, 3, 2, 1):
            nx = av[0] + {4: 5, 3: -5, 2: 0, 1: 0}[act]
            ny = av[1] + {4: 0, 3: 0, 2: 5, 1: -5}[act]
            if (nx, ny) in p["passable"] and (nx, ny) != p["goal"]:
                obs = env.step(A[act])
                actions.append(act)
                moved = True
                break
        if not moved:
            obs = env.step(A[1])
            actions.append(1)
        # stop once we have enough distinct mover positions to see a reversal
        xs = [px for px, py in positions]
        if len(set(xs)) >= 3 and len(xs) >= 4:
            # detect reversal: seen an x repeat after going one way
            break
    return positions, actions


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("ls20")
    obs = env.observation_space
    g = env._game
    adapter = Adapter(giveup=6000)
    steps = 0
    while steps < 6000 and obs.levels_completed < 4:
        if adapter.is_done([], obs):
            break
        a = adapter.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        steps += 1

    holder = {"obs": obs}

    def get_grid():
        return tuple(tuple(r) for r in canonical_layer(holder["obs"]))

    # settle the entry frame (2-layer stale) with one probe
    holder["obs"] = env.step(GameAction.ACTION1)

    # observation phase — returns the FINAL frame we plan from (no extra action
    # after the last recorded mover position), so mover state is consistent.
    positions, obs_actions, grid = observe_mover_wrap(env, holder, get_grid)
    print("mover positions observed:", positions)
    xs = [px for px, py in positions]
    my = positions[0][1]
    track = tuple(sorted(set(range(min(xs), max(xs) + 1, 5))))
    mx = positions[-1][0]
    # direction from last two DISTINCT recorded positions
    mdir = 1
    for j in range(len(positions) - 1, 0, -1):
        if positions[j][0] != positions[j - 1][0]:
            mdir = 1 if positions[j][0] > positions[j - 1][0] else 3
            break
    print("track", track, "mx", mx, "mdir", mdir, "my", my)

    p = parse_l5(grid)
    ax, ay = p["avatar"]
    ox, oy = ax % 5, ay % 5
    # strip mover from static changers; build hard_walls without avatar
    changers = tuple((c, k) for c, k in p["changers"].items() if not (k == "rot" and c == (mx, my)))
    hard = frozenset(w for w in p["hard_walls"] if w != p["avatar"])
    fj = frozenset(set(hard) | {p["goal"]})
    full = 21
    life = read_life(grid)
    maze = Maze(hard, p["goal"], p["goal_req"], changers, frozenset(p["refills"]),
                tuple(p["pushwalls"]), fj, track, my, full)
    start = SimState(ax, ay, p["token"][0], p["token"][1], p["token"][2],
                     life, frozenset(), mx, mdir)
    print("start", start, "life", life)
    print("goal", maze.goal, "req", maze.goal_req, "changers", maze.changers)
    print("GT avatar", (g.gudziatsk.x, g.gudziatsk.y), "GT token", (g.fwckfzsyc, g.hiaauhahz, g.cklxociuu),
          "GT mover", (g.wsoslqeku[0]._sprite.x, g.wsoslqeku[0]._dir))

    plan, exp = bfs(maze, start)
    print(f"BFS exp={exp} plan_len={len(plan) if plan else None}")
    if not plan:
        print("NO PLAN — bank divergence")
        return
    for i, act in enumerate(plan):
        holder["obs"] = env.step(A[act])
        o = holder["obs"]
        if o is None:
            print("obs None"); break
        if str(o.state).endswith("WIN") or o.levels_completed >= 5:
            print(f"*** LIVE L5 WIN at action {i+1}/{len(plan)} (obs_actions={len(obs_actions)}) ***")
            return
    print("replay ended; levels", holder["obs"].levels_completed, "state", holder["obs"].state)


def observe_mover_wrap(env, holder, get_grid):
    positions = []
    actions = []
    grid = get_grid()
    for _ in range(10):
        p = parse_l5(grid)
        rots = [c for c, k in p["changers"].items() if k == "rot"]
        if rots:
            positions.append(rots[0])
        xs = [px for px, py in positions]
        if len(xs) >= 5 and len(set(xs)) >= 3:
            break  # stop WITHOUT another action; plan from THIS grid
        av = p["avatar"]
        moved = False
        for act in (4, 3, 2, 1):
            nx = av[0] + {4: 5, 3: -5, 2: 0, 1: 0}[act]
            ny = av[1] + {4: 0, 3: 0, 2: 5, 1: -5}[act]
            if (nx, ny) in p["passable"] and (nx, ny) != p["goal"]:
                holder["obs"] = env.step(A[act]); actions.append(act); moved = True; break
        if not moved:
            holder["obs"] = env.step(A[1]); actions.append(1)
        grid = get_grid()
    return positions, actions, grid


def bfs(maze, start, cap=3_000_000):
    seen = {start.key()}
    q = deque([(start, [])])
    exp = 0
    while q and exp < cap:
        s, path = q.popleft()
        exp += 1
        if s.steps <= 0:
            continue
        for act in (1, 2, 3, 4):
            ns = sim_step(maze, s, act)
            if ns.steps < 0:
                continue
            k = ns.key()
            if k in seen:
                continue
            if is_win(maze, ns):
                return path + [act], exp
            seen.add(k)
            q.append((ns, path + [act]))
    return None, exp


if __name__ == "__main__":
    main()
