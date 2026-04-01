"""Run GraphAgent on all ARC-AGI-3 games — with toggle+sequence solvers, faster limits."""

import time

import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import GameAction, GameState

from admorphiq.agent_graph import GraphAgent
from admorphiq.planner.toggle_solver import ToggleSolver
from admorphiq.planner.sequence_solver import SequenceSolver

MAX_ACTIONS = 50000
TIME_LIMIT = 120.0  # 2 minutes per game


def _click(env, cx, cy):
    action = GameAction.from_id(6)
    action.set_data({"x": cx, "y": cy})
    return env.step(action, data={"x": cx, "y": cy})


def _get_frame(obs):
    f = np.array(obs.frame)
    return f[0] if f.ndim == 3 else f


def _get_levels(obs):
    return obs.levels_completed


def try_toggle_solve(env, obs):
    """Try toggle puzzle solver. Returns (levels_completed, obs)."""
    available = list(obs.available_actions)
    if 6 not in available:
        return 0, obs

    solver = ToggleSolver(max_groups=13)
    n = solver.discover_groups(env, GameAction.RESET, _click, _get_frame)

    if n == 0 or n > 13:
        obs = env.step(GameAction.RESET)
        return 0, obs

    combo = solver.brute_force_solve(env, GameAction.RESET, _click, _get_levels)
    if combo:
        obs = env.step(GameAction.RESET)
        obs = solver.apply_combo(env, _click)
        levels = obs.levels_completed if obs else 0
        print(f"  Toggle solver: L1 solved! clicks={sum(combo)}, levels={levels}/{obs.win_levels if obs else '?'}")
        return levels, obs

    obs = env.step(GameAction.RESET)
    return 0, obs


def try_sequence_solve(env, obs):
    """Try brute-force sequence solver. Returns (levels_completed, obs)."""
    available = list(obs.available_actions)

    solver = SequenceSolver(max_length=8, max_combos=50000)
    actions = solver.discover_actions(
        env, GameAction.RESET, _click, _get_frame, available
    )

    if not actions:
        return 0, obs

    n = len(actions)
    # Only try if search space is manageable
    if n > 10:
        obs = env.step(GameAction.RESET)
        return 0, obs

    result = solver.brute_force_solve(
        env, GameAction.RESET, _click, _get_levels, actions
    )

    if result:
        obs = env.step(GameAction.RESET)
        obs = solver.apply_sequence(env, _click)
        levels = obs.levels_completed if obs else 0
        seq_desc = [(t, a) if t == "action" else (t, a, b) for t, a, b in result]
        print(f"  Sequence solver: L1 solved! steps={len(result)}, seq={seq_desc}, levels={levels}/{obs.win_levels if obs else '?'}")
        return levels, obs

    obs = env.step(GameAction.RESET)
    return 0, obs


def run_game(arcade: Arcade, game_id: str, agent: GraphAgent) -> dict:
    env = arcade.make(game_id)
    if env is None:
        return {"game_id": game_id, "error": "make() returned None"}

    obs = env.observation_space
    if obs is None:
        return {"game_id": game_id, "error": "No observation after make()"}

    toggle_levels, obs = try_toggle_solve(env, obs)

    # Try sequence solver if toggle didn't solve
    seq_levels = toggle_levels
    if toggle_levels == 0:
        seq_levels, obs = try_sequence_solve(env, obs)

    solved_levels = max(toggle_levels, seq_levels)
    agent.explorer.on_level_complete()
    agent._last_levels_completed = solved_levels

    start_time = time.time()
    action_count = 0
    last_new_state_step = 0
    last_state_count = 0
    last_level_count = solved_levels
    STALE_THRESHOLD = 3000

    while action_count < MAX_ACTIONS:
        elapsed = time.time() - start_time
        if elapsed > TIME_LIMIT:
            break

        if agent.is_done([], obs):
            break

        stats = agent.get_stats()
        current_states = stats["unique_states"]
        current_levels = obs.levels_completed if obs else 0
        if current_states > last_state_count or current_levels > last_level_count:
            last_new_state_step = action_count
            last_state_count = current_states
            last_level_count = current_levels
        elif action_count - last_new_state_step > STALE_THRESHOLD:
            break

        action = agent.choose_action([], obs)

        if isinstance(action, GameAction):
            if action.is_complex():
                obs = env.step(action, data=action.action_data.model_dump())
            else:
                obs = env.step(action)
        else:
            break

        if obs is None:
            break

        action_count += 1

    elapsed = time.time() - start_time
    stats = agent.get_stats()
    levels = obs.levels_completed if obs else solved_levels

    return {
        "game_id": game_id,
        "actions": action_count,
        "elapsed_s": round(elapsed, 2),
        "levels_completed": levels,
        "win_levels": obs.win_levels if obs else 0,
        "unique_states": stats["unique_states"],
        "game_type": stats.get("game_type", "?"),
    }


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    envs = arcade.get_environments()

    print(f"Running {len(envs)} games with GraphAgent + toggle solver")
    print(f"Max {MAX_ACTIONS} actions, {TIME_LIMIT}s per game\n")

    agent = GraphAgent()
    results = []
    total_levels = 0
    total_win = 0

    for i, env_info in enumerate(envs):
        game_id = env_info.game_id
        print(f"[{i+1}/{len(envs)}] {game_id} ({env_info.title})")
        try:
            result = run_game(arcade, game_id, agent)
            results.append(result)
            if "error" in result:
                print(f"  ERROR: {result['error']}")
            else:
                total_levels += result["levels_completed"]
                total_win += result["win_levels"]
                marker = " ***" if result["levels_completed"] > 0 else ""
                print(
                    f"  {result['levels_completed']}/{result['win_levels']} levels, "
                    f"{result['actions']} actions, {result['elapsed_s']}s, "
                    f"{result['unique_states']} states, type={result['game_type']}{marker}"
                )
        except Exception as e:
            print(f"  EXCEPTION: {type(e).__name__}: {e}")
            results.append({"game_id": game_id, "error": str(e)})
        print()

    print("=" * 60)
    print(f"TOTAL: {total_levels}/{total_win} levels")
    if total_win > 0:
        print(f"Score: {total_levels/total_win*100:.2f}%")

    solved = [r for r in results if r.get("levels_completed", 0) > 0]
    print(f"\nSolved games ({len(solved)}):")
    for r in solved:
        print(f"  {r['game_id']}: {r['levels_completed']}/{r['win_levels']}")


if __name__ == "__main__":
    main()
