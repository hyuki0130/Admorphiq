"""Run DiffAgent on the 15 unsolved games with 200K actions."""

import time

from arc_agi import Arcade, OperationMode

from admorphiq.agent_diff import DiffAgent

MAX_ACTIONS = 200000
TIME_LIMIT = 300.0  # 5 minutes per game

# 15 unsolved games
TARGET_GAMES = [
    "dc22", "tu93", "re86", "su15", "tr87", "sc25", "g50t",
    "sb26", "lf52", "bp35", "s5i5", "sk48", "wa30", "cd82", "tn36",
]


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    envs = arcade.get_environments()

    # Filter to target games
    target_envs = [e for e in envs if any(e.game_id.startswith(t) for t in TARGET_GAMES)]
    print(f"Available: {len(envs)}, Target: {len(target_envs)} unsolved games")
    print(f"Config: max {MAX_ACTIONS} actions, {TIME_LIMIT}s time limit\n")

    agent = DiffAgent(analysis_trials=3)
    results: list[dict] = []
    total_start = time.time()

    for i, env_info in enumerate(target_envs):
        game_id = env_info.game_id
        title = getattr(env_info, "title", "") or ""
        print(f"[{i + 1}/{len(target_envs)}] {game_id} ({title})")

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
    print(f"SUMMARY — DiffAgent on 15 unsolved games (200K actions, {TIME_LIMIT}s)")
    print("=" * 60)

    successful = [r for r in results if "error" not in r]

    if successful:
        total_levels = sum(r.get("levels_completed", 0) for r in successful)
        total_win_levels = sum(r.get("win_levels", 0) for r in successful)
        print(f"Total levels completed: {total_levels}/{total_win_levels}")

    # Sort by states discovered (most promising)
    successful.sort(key=lambda r: r.get("states_discovered", 0), reverse=True)
    print("\nPer-game results (sorted by states discovered):")
    for r in successful:
        gid = r.get("game_id", "?")
        print(
            f"  {gid}: type={r['game_type']}, "
            f"levels={r['levels_completed']}/{r['win_levels']}, "
            f"actions={r['actions']}, time={r['elapsed_s']}s, "
            f"states={r['states_discovered']}"
        )

    print(f"\nTotal time: {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
