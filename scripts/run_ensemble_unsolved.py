"""Run EnsembleAgent on the 14 unsolved games."""

import time
from arc_agi import Arcade, OperationMode
from admorphiq.agent_ensemble import EnsembleAgent

TARGET_GAMES = [
    "tu93", "re86", "su15", "tr87", "sc25", "g50t",
    "sb26", "lf52", "bp35", "sk48", "wa30", "cd82", "tn36", "dc22",
]


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    envs = arcade.get_environments()
    target_envs = [e for e in envs if any(e.game_id.startswith(t) for t in TARGET_GAMES)]
    print(f"Testing {len(target_envs)} unsolved games with EnsembleAgent\n")

    agent = EnsembleAgent(total_budget=50000)
    total_new = 0

    for i, env_info in enumerate(target_envs):
        gid = env_info.game_id
        t0 = time.time()
        try:
            env = arcade.make(gid)
            result = agent.solve_game(env, game_id=gid)
            elapsed = time.time() - t0
            lvl = result["levels_completed"]
            wl = result["win_levels"]
            strat = result.get("strategy", "")
            mark = " ***" if lvl > 0 else ""
            print(f"{gid.upper()}: {lvl}/{wl} [{elapsed:.0f}s] {strat}{mark}")
            if lvl > 0:
                total_new += lvl
        except Exception as e:
            print(f"{gid.upper()}: ERROR {e}")

    print(f"\nTOTAL NEW: {total_new} levels")


if __name__ == "__main__":
    main()
