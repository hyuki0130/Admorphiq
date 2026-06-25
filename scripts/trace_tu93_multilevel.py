"""Instrument a tu93 run to find why GeneralAgent does not progress past L1.

Drives the env exactly like score_efficiency.py but logs, per action, the
level / phase / dir_map / player / state, with extra detail around each
level transition. Pure diagnostic; writes scripts/trace_tu93_multilevel.txt.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction, GameState  # noqa: E402

from admorphiq.general_agent import GeneralAgent, canonical_layer  # noqa: E402

TITLE_SUBSTR = sys.argv[1] if len(sys.argv) > 1 else "tu93"
MAX_ACTIONS = 600


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    envs = arcade.get_environments()
    env_info = next(
        e for e in envs if TITLE_SUBSTR in f"{e.game_id} {e.title or ''}".lower()
    )
    game_id = env_info.game_id
    print(f"game={game_id} title={env_info.title} baseline={env_info.baseline_actions}")

    agent = GeneralAgent()
    env = arcade.make(game_id)
    obs = env.observation_space
    win_levels = obs.win_levels
    prev_levels = obs.levels_completed
    total = 0
    this_level = 0
    lines: list[str] = []

    while total < MAX_ACTIONS:
        if agent.is_done([], obs):
            lines.append(f"[STOP] is_done @ total={total} state={obs.state}")
            break

        prev_phase = agent._phase
        action = agent.choose_action([], obs)
        if not isinstance(action, GameAction):
            lines.append(f"[STOP] non-GameAction {action}")
            break

        # Log around level transitions and phase changes.
        lvl = obs.levels_completed
        log_this = (
            total < 4
            or abs(total - 32) <= 6  # around L1 clear
            or prev_phase != agent._phase
            or lvl != prev_levels
        )

        if action.is_complex():
            obs = env.step(action, data=action.action_data.model_dump())
        else:
            obs = env.step(action)
        if obs is None:
            lines.append(f"[STOP] obs None @ total={total}")
            break

        total += 1
        this_level += 1
        cur = obs.levels_completed
        if cur > prev_levels:
            layer = canonical_layer(getattr(obs, "frame", obs))
            lines.append(
                f"[LEVELUP] {prev_levels}->{cur} @ total={total} this_level={this_level} "
                f"state={obs.state} layer_uniq={sorted(set(layer.flatten().tolist()))[:12]}"
            )
            this_level = 0
            prev_levels = cur

        if log_this:
            dm = {k: v for k, v in agent._dir_map.items()}
            lines.append(
                f"a={total:3d} act={action.name} phase={prev_phase}->{agent._phase} "
                f"lvl={lvl} pcolor={agent._player_color} bg={agent._background} "
                f"corridor={agent._corridor_color} ndirs={len(dm)} dm={dm} "
                f"probes={len(agent._probes)} state={obs.state}"
            )

        if obs.state in (GameState.WIN, GameState.GAME_OVER):
            lines.append(f"[TERMINAL] state={obs.state} @ total={total} lvl={obs.levels_completed}")
            break

    lines.append(
        f"\nFINAL levels_completed={obs.levels_completed}/{win_levels} "
        f"total_actions={total} state={obs.state} agent._action_count={agent._action_count}"
    )
    out = "\n".join(lines)
    print(out)
    Path("scripts/trace_tu93_multilevel.txt").write_text(out, encoding="utf-8")


if __name__ == "__main__":
    main()
