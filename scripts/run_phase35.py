"""Phase 3.5 game test — compare with Phase 2.5 baseline."""

import time

from arc_agi import Arcade, OperationMode
from arcengine import GameAction

from admorphiq.adapter import AdmorphiqAdapter
from admorphiq.utils import GameLogger

MAX_ACTIONS = 500


def log(msg: str) -> None:
    print(msg, flush=True)


def run_game(arcade: Arcade, name: str, game_id: str) -> dict:
    log(f"\n===== {name} ({game_id}) =====")

    adapter = AdmorphiqAdapter()
    agent = adapter._agent
    logger = GameLogger(game_id=game_id, agent_name="admorphiq_cnn")
    agent.set_logger(logger)

    env = arcade.make(game_id)
    if env is None:
        log("  make() returned None")
        return {"game": name, "error": "make() returned None"}

    obs = env.observation_space
    if obs is None:
        log("  No observation")
        return {"game": name, "error": "No observation"}

    log(f"  Layers: {len(obs.frame)}, Win levels: {obs.win_levels}")
    log(f"  Available actions: {obs.available_actions}")

    start = time.time()
    action_count = 0
    prev_levels = 0
    action_names = []

    while action_count < MAX_ACTIONS:
        if adapter.is_done([], obs):
            log(f"  DONE at step {action_count}!")
            break

        action = adapter.choose_action([], obs)

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
        action_names.append(action.name)

        if obs.levels_completed > prev_levels:
            t = time.time() - start
            log(f"  *** LEVEL UP at step {action_count}! levels={obs.levels_completed}/{obs.win_levels} (t={t:.1f}s)")
            prev_levels = obs.levels_completed

        if action_count % 30 == 0:
            t = time.time() - start
            recent = action_names[-20:]
            log(
                f"  Step {action_count}: levels={obs.levels_completed}/{obs.win_levels}, "
                f"buf={len(agent.buffer)}, unique_recent={len(set(recent))}/20, t={t:.1f}s"
            )

    elapsed = time.time() - start
    first_20 = action_names[:20]

    r = {
        "game": name,
        "actions": action_count,
        "time": round(elapsed, 2),
        "ms_per_action": round(elapsed / max(action_count, 1) * 1000, 1),
        "state": obs.state.name if obs else "NONE",
        "levels_completed": obs.levels_completed if obs else 0,
        "win_levels": obs.win_levels if obs else 0,
        "buffer": len(agent.buffer),
        "first_20_unique": len(set(first_20)),
        "first_20": first_20,
    }

    logger.log_summary(
        total_actions=action_count,
        levels_cleared=obs.levels_completed if obs else 0,
        elapsed=elapsed,
    )
    log(f"  Log saved: {logger.log_file}")
    log(f"  Result: {r['actions']} actions, {r['time']}s ({r['ms_per_action']}ms/act)")
    log(f"  Levels: {r['levels_completed']}/{r['win_levels']}")
    log(f"  Buffer: {r['buffer']}, First 20 unique: {r['first_20_unique']}")
    log(f"  First 20: {first_20}")
    return r


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    envs = arcade.get_environments()
    log(f"Available games: {len(envs)}")

    targets = {}
    for e in envs:
        if e.game_id.startswith("dc22"):
            targets["DC22"] = e.game_id
        elif e.game_id.startswith("lf52"):
            targets["LF52"] = e.game_id
        elif e.game_id.startswith("bp35"):
            targets["BP35"] = e.game_id

    log(f"Targets: {targets}")

    results = []
    for name, gid in targets.items():
        try:
            r = run_game(arcade, name, gid)
            results.append(r)
        except Exception as e:
            log(f"  EXCEPTION: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            results.append({"game": name, "error": str(e)})

    log("\n===== COMPARISON: Phase 2.5 vs Phase 3.5 =====")
    phase25 = {
        "DC22": ("0/6", "552.0"),
        "LF52": ("0/10", "462.7"),
        "BP35": ("0/9", "454.2"),
    }
    log(f"{'Game':<8} {'P2.5 Lvl':<12} {'P3.5 Lvl':<12} {'P2.5 ms':<12} {'P3.5 ms':<12}")
    for r in results:
        if "error" not in r:
            p = phase25.get(r["game"], ("?", "?"))
            log(
                f"{r['game']:<8} {p[0]:<12} "
                f"{r['levels_completed']}/{r['win_levels']:<10} "
                f"{p[1]:<12} {r['ms_per_action']:<12}"
            )


if __name__ == "__main__":
    main()
