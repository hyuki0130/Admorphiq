"""Run GraphAgent on all ARC-AGI-3 games — pure graph-based exploration."""

import time

from arc_agi import Arcade, OperationMode
from arcengine import GameAction, GameState

from admorphiq.agent_graph import GraphAgent

MAX_ACTIONS = 500


def run_game(arcade: Arcade, game_id: str, agent: GraphAgent) -> dict:
    """Run a single game and return metrics."""
    env = arcade.make(game_id)
    if env is None:
        return {"game_id": game_id, "error": "make() returned None"}

    obs = env.observation_space
    if obs is None:
        return {"game_id": game_id, "error": "No observation after make()"}

    # Fresh explorer per game
    agent.explorer.on_level_complete()
    agent._last_levels_completed = 0

    start_time = time.time()
    action_count = 0

    while action_count < MAX_ACTIONS:
        if agent.is_done([], obs):
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

        if action_count % 50 == 0:
            stats = agent.get_stats()
            print(
                f"  Step {action_count}: state={obs.state}, "
                f"levels={obs.levels_completed}/{obs.win_levels}, "
                f"states={stats['unique_states']}, edges={stats['total_edges']}"
            )

    elapsed = time.time() - start_time
    stats = agent.get_stats()

    return {
        "game_id": game_id,
        "actions": action_count,
        "elapsed_s": round(elapsed, 2),
        "ms_per_action": round(elapsed / max(action_count, 1) * 1000, 1),
        "state": obs.state.name if obs else "UNKNOWN",
        "levels_completed": obs.levels_completed if obs else 0,
        "win_levels": obs.win_levels if obs else 0,
        "unique_states": stats["unique_states"],
        "total_edges": stats["total_edges"],
    }


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    envs = arcade.get_environments()

    print(f"Available games: {len(envs)}")
    print(f"Running ALL {len(envs)} games with GraphAgent (max {MAX_ACTIONS} actions each)\n")

    agent = GraphAgent()

    results = []
    total_levels = 0
    total_win_levels = 0

    for i, env_info in enumerate(envs):
        game_id = env_info.game_id
        print(f"[{i+1}/{len(envs)}] === {game_id} ({env_info.title}) ===")
        try:
            result = run_game(arcade, game_id, agent)
            results.append(result)
            if "error" in result:
                print(f"  ERROR: {result['error']}")
            else:
                total_levels += result["levels_completed"]
                total_win_levels += result["win_levels"]
                print(
                    f"  Actions: {result['actions']}, "
                    f"Time: {result['elapsed_s']}s ({result['ms_per_action']}ms/action), "
                    f"State: {result['state']}, "
                    f"Levels: {result['levels_completed']}/{result['win_levels']}, "
                    f"States: {result['unique_states']}, Edges: {result['total_edges']}"
                )
        except Exception as e:
            print(f"  EXCEPTION: {type(e).__name__}: {e}")
            results.append({"game_id": game_id, "error": str(e)})
        print()

    # Summary
    print("=" * 70)
    print("SUMMARY — GraphAgent (pure graph exploration)")
    print("=" * 70)
    completed_games = [r for r in results if "error" not in r]
    error_games = [r for r in results if "error" in r]

    print(f"Games run: {len(results)}, Errors: {len(error_games)}")
    print(f"Total levels completed: {total_levels}/{total_win_levels}")

    if total_win_levels > 0:
        score = total_levels / total_win_levels * 100
        print(f"Overall score: {score:.2f}%")

    print()
    print("Per-game results:")
    for r in results:
        if "error" in r:
            print(f"  {r['game_id']}: ERROR - {r['error']}")
        else:
            pct = (
                f"{r['levels_completed']/r['win_levels']*100:.0f}%"
                if r["win_levels"] > 0
                else "N/A"
            )
            print(
                f"  {r['game_id']}: {r['levels_completed']}/{r['win_levels']} levels ({pct}), "
                f"{r['actions']} actions, {r['elapsed_s']}s, "
                f"{r['unique_states']} states"
            )


if __name__ == "__main__":
    main()
