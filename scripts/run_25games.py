#!/usr/bin/env python3
"""Run all 25 games with StochasticGoose-style CNN agent.

Config: binary reward, coord /4096, train_frequency=5, perception only.
500 actions per game, 180s timeout per game.
"""

import sys
import time

sys.path.insert(0, "src")

from arc_agi import Arcade, OperationMode
from arcengine import GameAction

from admorphiq.adapter import AdmorphiqAdapter

MAX_ACTIONS = 500
TIMEOUT_SEC = 180


def log(msg: str) -> None:
    print(msg, flush=True)


def run_game(arcade: Arcade, game_id: str) -> dict:
    adapter = AdmorphiqAdapter()
    agent = adapter._agent

    env = arcade.make(game_id)
    if env is None:
        return {"game_id": game_id, "error": "make() returned None"}

    obs = env.observation_space
    if obs is None:
        return {"game_id": game_id, "error": "No observation"}

    win_levels = obs.win_levels
    n_layers = len(obs.frame)
    available = obs.available_actions
    log(f"  Layers: {n_layers}, Win levels: {win_levels}, Actions: {available}")

    start = time.time()
    action_count = 0
    action6_count = 0
    simple_count = 0
    levels_completed = 0

    while action_count < MAX_ACTIONS:
        # Timeout check
        elapsed = time.time() - start
        if elapsed > TIMEOUT_SEC:
            log(f"  TIMEOUT after {action_count} actions, {elapsed:.1f}s")
            return {
                "game_id": game_id, "actions": action_count,
                "levels_completed": levels_completed, "win_levels": win_levels,
                "time": round(elapsed, 2),
                "ms_per_action": round(elapsed / max(action_count, 1) * 1000, 1),
                "action6_count": action6_count, "simple_count": simple_count,
                "timed_out": True,
            }

        if adapter.is_done([], obs):
            log(f"  DONE at step {action_count}!")
            break

        action = adapter.choose_action([], obs)

        if not isinstance(action, GameAction):
            break

        if action.name == "ACTION6":
            action6_count += 1
        else:
            simple_count += 1

        if action.is_complex():
            obs = env.step(action, data=action.action_data.model_dump())
        else:
            obs = env.step(action)

        if obs is None:
            break

        action_count += 1

        if obs.levels_completed > levels_completed:
            t = time.time() - start
            log(f"  *** LEVEL UP at step {action_count}! levels={obs.levels_completed}/{win_levels} (t={t:.1f}s)")
            levels_completed = obs.levels_completed

        if action_count % 100 == 0:
            t = time.time() - start
            log(f"  Step {action_count}: levels={obs.levels_completed}/{win_levels}, "
                f"act6={action6_count}, simple={simple_count}, t={t:.1f}s")

    elapsed = time.time() - start
    levels_completed = obs.levels_completed if obs else levels_completed

    return {
        "game_id": game_id, "actions": action_count,
        "levels_completed": levels_completed, "win_levels": win_levels,
        "time": round(elapsed, 2),
        "ms_per_action": round(elapsed / max(action_count, 1) * 1000, 1),
        "action6_count": action6_count, "simple_count": simple_count,
        "timed_out": False,
    }


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    envs = arcade.get_environments()
    log(f"Available games: {len(envs)}")

    results = []

    for i, e in enumerate(envs):
        game_id = e.game_id
        log(f"\n===== [{i+1}/{len(envs)}] {game_id} =====")

        try:
            r = run_game(arcade, game_id)
            results.append(r)
            if "error" not in r:
                status = "TIMEOUT" if r["timed_out"] else "OK"
                log(f"  Result: {r['actions']} actions, {r['time']}s ({r['ms_per_action']}ms/act), "
                    f"levels={r['levels_completed']}/{r['win_levels']}, "
                    f"act6={r['action6_count']}, simple={r['simple_count']}, status={status}")
            else:
                log(f"  ERROR: {r['error']}")
        except Exception as ex:
            log(f"  EXCEPTION: {type(ex).__name__}: {ex}")
            import traceback
            traceback.print_exc()
            results.append({"game_id": game_id, "error": str(ex)})

    # Summary table
    log("\n" + "=" * 90)
    log("SUMMARY: 25-Game CNN Test (StochasticGoose-style)")
    log(f"Config: binary reward, coord /4096, train_freq=5, perception only, max {MAX_ACTIONS} actions")
    log("=" * 90)
    log(f"{'Game':<25} {'Levels':<12} {'ms/act':<10} {'ACT6':<8} {'Simple':<8} {'Status':<10}")
    log("-" * 73)

    total_levels = 0
    total_wins = 0
    ok_count = 0
    total_act6 = 0
    total_simple = 0
    ms_sum = 0.0

    for r in results:
        if "error" in r:
            log(f"{r['game_id']:<25} {'ERROR':<12}")
            continue

        status = "TIMEOUT" if r["timed_out"] else "OK"
        lvl_str = f"{r['levels_completed']}/{r['win_levels']}"
        log(f"{r['game_id']:<25} {lvl_str:<12} {r['ms_per_action']:<10.1f} "
            f"{r['action6_count']:<8} {r['simple_count']:<8} {status:<10}")

        total_levels += r["levels_completed"]
        total_act6 += r["action6_count"]
        total_simple += r["simple_count"]
        ms_sum += r["ms_per_action"]
        if not r["timed_out"]:
            ok_count += 1
        if r["levels_completed"] == r["win_levels"] and r["win_levels"] > 0:
            total_wins += 1

    log("-" * 73)
    n_valid = len([r for r in results if "error" not in r])
    total_actions = total_act6 + total_simple
    act6_pct = (total_act6 / total_actions * 100) if total_actions > 0 else 0
    avg_ms = ms_sum / max(n_valid, 1)

    log(f"Total levels cleared: {total_levels}")
    log(f"Games fully solved: {total_wins}/{len(results)}")
    log(f"Games completed (no timeout): {ok_count}/{len(results)}")
    log(f"Avg ms/action: {avg_ms:.1f}")
    log(f"ACTION6 ratio: {total_act6}/{total_actions} ({act6_pct:.1f}%)")


if __name__ == "__main__":
    main()
