"""Local game execution test — runs AdmorphiqAdapter on real ARC-AGI-3 games."""

import time

from arc_agi import Arcade, OperationMode
from arcengine import GameAction, GameState

from admorphiq.adapter import AdmorphiqAdapter

MAX_ACTIONS = 500
NUM_GAMES = 3


def run_game(arcade: Arcade, game_id: str, adapter: AdmorphiqAdapter) -> dict:
    """Run a single game and return metrics."""
    env = arcade.make(game_id)
    if env is None:
        return {"game_id": game_id, "error": "make() returned None"}

    obs = env.observation_space
    if obs is None:
        return {"game_id": game_id, "error": "No observation after make()"}

    start_time = time.time()
    action_count = 0

    while action_count < MAX_ACTIONS:
        # Check done
        if adapter.is_done([], obs):
            break

        # Choose action via adapter
        action = adapter.choose_action([], obs)

        # Step
        if isinstance(action, GameAction):
            if action.is_complex():
                obs = env.step(action, data=action.action_data.model_dump())
            else:
                obs = env.step(action)
        else:
            # Fallback: shouldn't happen with _HAS_OFFICIAL=True
            break

        if obs is None:
            break

        action_count += 1

        if action_count % 10 == 0:
            print(
                f"  Step {action_count}: state={obs.state}, "
                f"levels={obs.levels_completed}/{obs.win_levels}"
            )

    elapsed = time.time() - start_time

    return {
        "game_id": game_id,
        "actions": action_count,
        "elapsed_s": round(elapsed, 2),
        "ms_per_action": round(elapsed / max(action_count, 1) * 1000, 1),
        "state": obs.state.name if obs else "UNKNOWN",
        "levels_completed": obs.levels_completed if obs else 0,
        "win_levels": obs.win_levels if obs else 0,
    }


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    envs = arcade.get_environments()

    print(f"Available games: {len(envs)}")
    print(f"Testing first {NUM_GAMES}: {[e.game_id for e in envs[:NUM_GAMES]]}\n")

    adapter = AdmorphiqAdapter()

    results = []
    for env_info in envs[:NUM_GAMES]:
        game_id = env_info.game_id
        print(f"=== {game_id} ({env_info.title}) ===")
        try:
            result = run_game(arcade, game_id, adapter)
            results.append(result)
            if "error" in result:
                print(f"  ERROR: {result['error']}")
            else:
                print(
                    f"  Actions: {result['actions']}, "
                    f"Time: {result['elapsed_s']}s ({result['ms_per_action']}ms/action), "
                    f"State: {result['state']}, "
                    f"Levels: {result['levels_completed']}/{result['win_levels']}"
                )
        except Exception as e:
            print(f"  EXCEPTION: {type(e).__name__}: {e}")
            results.append({"game_id": game_id, "error": str(e)})
        print()

    print("=== Summary ===")
    for r in results:
        if "error" in r:
            print(f"  {r['game_id']}: ERROR - {r['error']}")
        else:
            print(
                f"  {r['game_id']}: {r['actions']} actions, "
                f"{r['levels_completed']}/{r['win_levels']} levels, "
                f"{r['elapsed_s']}s"
            )


if __name__ == "__main__":
    main()
