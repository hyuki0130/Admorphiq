"""Run the DiffAgent on ARC-AGI-3 games and report results."""

import json
import time

from arc_agi import Arcade, OperationMode

from admorphiq.agent_diff import DiffAgent

MAX_ACTIONS = 100000  # effectively unlimited
TIME_LIMIT = 600.0   # 10 minutes per game
NUM_GAMES = 25


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    envs = arcade.get_environments()

    num_games = min(NUM_GAMES, len(envs))
    print(f"Available games: {len(envs)}")
    print(f"Running DiffAgent on {num_games} games (max {MAX_ACTIONS} actions each)\n")

    agent = DiffAgent(analysis_trials=3)
    results: list[dict] = []
    total_start = time.time()

    for i, env_info in enumerate(envs[:num_games]):
        game_id = env_info.game_id
        title = getattr(env_info, "title", "") or ""
        print(f"[{i + 1}/{num_games}] {game_id} ({title})")

        try:
            env = arcade.make(game_id)
            if env is None:
                print("  ERROR: make() returned None\n")
                results.append({"game_id": game_id, "error": "make() returned None"})
                continue

            result = agent.play_game(env, max_actions=MAX_ACTIONS, time_limit=TIME_LIMIT)
            result["game_id"] = game_id
            result["title"] = title
            results.append(result)

            if "error" in result:
                print(f"  ERROR: {result['error']}")
            else:
                print(
                    f"  Type: {result['game_type']}, "
                    f"Player: color={result['player_color']}, "
                    f"Actions: {result['actions']}, "
                    f"Time: {result['elapsed_s']}s"
                )
                print(
                    f"  State: {result['state']}, "
                    f"Levels: {result['levels_completed']}/{result['win_levels']}, "
                    f"Graph: {result['states_discovered']} states / "
                    f"{result['transitions_recorded']} transitions"
                )
        except Exception as e:
            print(f"  EXCEPTION: {type(e).__name__}: {e}")
            results.append({"game_id": game_id, "error": str(e)})
        print()

    total_elapsed = time.time() - total_start

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    successful = [r for r in results if "error" not in r]
    errored = [r for r in results if "error" in r]

    # Game type breakdown
    type_counts: dict[str, int] = {}
    for r in successful:
        gt = r.get("game_type", "unknown")
        type_counts[gt] = type_counts.get(gt, 0) + 1

    print(f"\nGame types: {type_counts}")
    print(f"Successful: {len(successful)}/{len(results)}")
    print(f"Errors: {len(errored)}")

    if successful:
        total_levels = sum(r.get("levels_completed", 0) for r in successful)
        total_win_levels = sum(r.get("win_levels", 0) for r in successful)
        avg_states = sum(r.get("states_discovered", 0) for r in successful) / len(successful)
        print(f"Total levels completed: {total_levels}/{total_win_levels}")
        print(f"Avg states discovered: {avg_states:.1f}")

    print(f"\nTotal time: {total_elapsed:.1f}s")

    # Per-game results
    print("\nPer-game results:")
    for r in results:
        gid = r.get("game_id", "?")
        if "error" in r:
            print(f"  {gid}: ERROR - {r['error']}")
        else:
            print(
                f"  {gid}: type={r['game_type']}, "
                f"levels={r['levels_completed']}/{r['win_levels']}, "
                f"actions={r['actions']}, "
                f"states={r['states_discovered']}"
            )

    # Save results to JSON
    output_path = "scripts/diff_results.json"
    with open(output_path, "w") as f:
        # Convert sets to lists for JSON serialization
        serializable = []
        for r in results:
            sr = {}
            for k, v in r.items():
                if k == "analysis" and isinstance(v, dict):
                    sr[k] = {
                        ak: list(av) if isinstance(av, set) else av
                        for ak, av in v.items()
                    }
                elif isinstance(v, set):
                    sr[k] = list(v)
                else:
                    sr[k] = v
            serializable.append(sr)
        json.dump(serializable, f, indent=2)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
