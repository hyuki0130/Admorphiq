"""BFS over the validated pixel sim (GT maze) -> plan -> replay to a live L5
win. Validates SEARCH before frame-detection is tackled.
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
from ls20_sim import Maze, SimState, step as sim_step, is_win
from ls20_lockstep import build_maze

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4}


def bfs(maze: Maze, start: SimState, cap=2_000_000):
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
            if (ns.ax, ns.ay) == (s.ax, s.ay) and ns.steps == s.steps - 1 and ns.mx == s.mx:
                pass  # blocked move (no position change) still costs a step; allow (waiting)
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
    obs = env.step(GameAction.ACTION1)  # settle
    maze = build_maze(g)
    decr = g._step_counter_ui.efipnixsvl
    full = g._step_counter_ui.osgviligwp // decr
    cur = g._step_counter_ui.current_steps // decr
    maze = Maze(maze.hard_walls, maze.goal, maze.goal_req, maze.changers, maze.refills,
                maze.pushwalls, maze.fjzuynaokm, maze.mover_track, maze.mover_my, full)
    m = g.wsoslqeku[0]
    start = SimState(g.gudziatsk.x, g.gudziatsk.y, g.fwckfzsyc, g.hiaauhahz, g.cklxociuu,
                     cur, frozenset(), m._sprite.x, m._dir)
    print("start", start, "full", full, "cur", cur)
    print("goal", maze.goal, "req", maze.goal_req)
    plan, exp = bfs(maze, start)
    print(f"BFS expansions={exp} plan_len={len(plan) if plan else None}")
    if not plan:
        print("NO PLAN")
        return
    print("plan", plan)
    # replay open-loop against the live engine
    for i, act in enumerate(plan):
        obs = env.step(A[act])
        if obs is None:
            print("obs None at", i)
            break
        st = str(obs.state)
        if st.endswith("WIN") or obs.levels_completed >= 5:
            print(f"*** LIVE L5 WIN at action {i+1}/{len(plan)} (levels_completed={obs.levels_completed}) ***")
            return
    print("replay ended; levels_completed=", obs.levels_completed, "state", obs.state)


if __name__ == "__main__":
    main()
