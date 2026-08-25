"""What fraction of the fallback's clicks CHANGE the frame, first time and on repeat?

Purpose
-------
The fallback clears some games at hundreds of times a human's action count, and the remedy
depends entirely on WHY. If its clicks land, the gap is knowing which cell to press — mechanic
understanding, which does not transfer to unseen games. If its clicks are inert, the waste is
removable and skipping a cell already shown to do nothing needs no mechanic knowledge at all.

The first two games measured DISAGREE: vc33 changes the frame on 100% of clicks, first and
repeat; sk48 on 6% and 22%. Two games cannot say which regime is typical, which is what this
exists to widen.

Expected feedback
-----------------
Per game, the change rate for FIRST clicks on a cell and for RE-clicks. A high rate means there
is no removable waste in that game; a low rate means there is.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction, GameState  # noqa: E402

from admorphiq.adapters25.base import canonical_layer  # noqa: E402
from admorphiq.kaggle_chained_agent import build_chained  # noqa: E402


def measure(game: str, cap: int) -> None:
    """Drive the fallback on one game and report click efficacy."""
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    for env_info in arcade.get_environments():
        if game not in (env_info.title or env_info.game_id).lower():
            continue
        env = arcade.make(env_info.game_id)
        if env is None or env.observation_space is None:
            return
        obs = env.observation_space
        agent = build_chained()
        seen: Counter = Counter()
        stat = Counter()
        actions = 0

        while actions < cap:
            if agent.is_done([], obs):
                break
            action = agent.choose_action([], obs)
            before = canonical_layer(obs)
            if action.is_complex():
                data = action.action_data.model_dump()
                cell = (data["x"], data["y"])
                nxt = env.step(action, data=data)
            else:
                cell = None
                nxt = env.step(action)
            actions += 1
            if nxt is None:
                break
            if cell is not None:
                kind = "repeat" if seen[cell] else "first"
                stat[f"{kind}_{'changed' if canonical_layer(nxt) != before else 'inert'}"] += 1
                seen[cell] += 1
            obs = nxt
            if obs.levels_completed >= 1:
                print(f"{game}: L1 cleared at {actions} actions")
                break
            if obs.state == GameState.GAME_OVER:
                obs = env.step(GameAction.RESET)
                actions += 1

        first = stat["first_changed"] + stat["first_inert"]
        repeat = stat["repeat_changed"] + stat["repeat_inert"]
        print(f"{game}: FIRST {stat['first_changed']}/{first} "
              f"({100 * stat['first_changed'] / max(1, first):.0f}%)  "
              f"REPEAT {stat['repeat_changed']}/{repeat} "
              f"({100 * stat['repeat_changed'] / max(1, repeat):.0f}%)")
        return
    print(f"{game}: no such environment")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: click_efficacy.py <game> [action-cap]")
        return 1
    measure(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3000)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
