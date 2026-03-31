"""CNN unlimited action test - time-limited only (5min/game)."""
import sys
import time

sys.path.insert(0, "src")

import numpy as np

from arc_agi import Arcade, OperationMode
from arcengine import GameAction, GameState
from admorphiq.adapter import AdmorphiqAdapter
from admorphiq.utils.logger import GameLogger


def run_game(arcade, game_env, game_name):
    """Run a single game with unlimited actions, 5min time limit."""
    card_id = arcade.open_scorecard(tags=["unlimited_test"])
    env = arcade.make(game_env.game_id, scorecard_id=card_id)
    adapter = AdmorphiqAdapter()
    logger = GameLogger(game_env.game_id, "cnn_unlimited")
    adapter._agent.set_logger(logger)

    obs = env.step(GameAction.RESET)
    start = time.time()
    step = 0
    TIME_LIMIT = 300  # 5 min

    while time.time() - start < TIME_LIMIT:
        if obs.state == GameState.WIN:
            break
        if obs.state in [GameState.NOT_PLAYED, GameState.GAME_OVER]:
            obs = env.step(GameAction.RESET)
            step += 1
            continue

        action, data = adapter.choose_action_with_data([], obs)
        if action is None:
            break
        try:
            obs = env.step(action, data=data) if data else env.step(action)
        except Exception as e:
            print(f"  {game_name} step {step} error: {e}")
            continue
        step += 1

        if step % 200 == 0:
            elapsed = time.time() - start
            print(
                f"  {game_name} Step {step}: levels={obs.levels_completed}/{obs.win_levels}, "
                f"elapsed={elapsed:.0f}s, ms/action={elapsed/step*1000:.0f}"
            )

    elapsed = time.time() - start
    logger.log_summary(step, obs.levels_completed, elapsed)
    print(
        f"[DONE] {game_name}: {step} actions, levels={obs.levels_completed}/{obs.win_levels}, "
        f"{elapsed:.1f}s, {elapsed/max(step,1)*1000:.0f}ms/action"
    )
    arcade.close_scorecard(card_id)
    return {
        "game": game_name,
        "steps": step,
        "levels": obs.levels_completed,
        "win_levels": obs.win_levels,
        "elapsed": elapsed,
        "log_file": str(logger.log_file),
    }


def main():
    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    games = arcade.get_environments()

    # Find target games
    targets = {}
    for g in games:
        name = g.game_id.split("-")[0].upper()
        if name in ["DC22", "AR25", "LP85"]:
            targets[name] = g

    print(f"Found games: {list(targets.keys())}")
    results = []

    for name in ["DC22", "AR25", "LP85"]:
        if name not in targets:
            print(f"WARNING: {name} not found!")
            continue
        print(f"\n{'='*60}")
        print(f"Starting {name} (5min time limit, unlimited actions)")
        print(f"{'='*60}")
        result = run_game(arcade, targets[name], name)
        results.append(result)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for r in results:
        print(
            f"  {r['game']}: {r['steps']} steps, {r['levels']}/{r['win_levels']} levels, "
            f"{r['elapsed']:.0f}s, {r['elapsed']/max(r['steps'],1)*1000:.0f}ms/action"
        )
        print(f"    Log: {r['log_file']}")


if __name__ == "__main__":
    main()
