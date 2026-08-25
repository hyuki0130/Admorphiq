"""Would a DIFFERENT tool do better than the one the harness always picks?

Purpose: the harness picks `graph` on every measured game and never re-decides, because a stall
cannot fire where every action produces novelty. That says the alternatives are never TRIED; it
says nothing about whether they would be better. This forces each tool to run alone and reports
what it achieves, so the "graph is simply right here" reading can be checked rather than assumed.

Expected feedback: per tool, levels cleared and actions spent on one game. A tool that beats the
harness's own pick means the never-switching behaviour costs something; none beating it means the
pick is right and the missing re-decision is harmless.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction, GameState  # noqa: E402

from admorphiq.harness.loop import UnifiedAgent  # noqa: E402
from admorphiq.harness.registry import default_tools  # noqa: E402


def _no_llm(_messages: object) -> str:
    """The deployed LLM-free configuration: raising engages signature routing."""
    raise RuntimeError("LLM-free deployment")


def run(game: str, tool_name: str, cap: int) -> None:
    """Drive one game with a single tool and report what it reaches."""
    tools = [t for t in default_tools() if t.name == tool_name]
    if not tools:
        print(f"{game}/{tool_name}: no such tool")
        return
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    for env_info in arcade.get_environments():
        if game not in (env_info.title or env_info.game_id).lower():
            continue
        env = arcade.make(env_info.game_id)
        if env is None or env.observation_space is None:
            return
        obs = env.observation_space
        agent = UnifiedAgent(tools, _no_llm, giveup=cap, stall=80, ctx_budget=6000)
        actions, best = 0, 0
        while actions < cap:
            if agent.is_done([], obs):
                break
            action = agent.choose_action([], obs)
            if action is None:
                break
            nxt = (env.step(action, data=action.action_data.model_dump())
                   if action.is_complex() else env.step(action))
            actions += 1
            if nxt is None:
                break
            obs = nxt
            best = max(best, obs.levels_completed)
            if obs.state == GameState.GAME_OVER:
                obs = env.step(GameAction.RESET)
                actions += 1
        print(f"{game}/{tool_name}: levels={best} actions={actions}")
        return
    print(f"{game}/{tool_name}: no such environment")


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: tool_alternatives.py <game> <tool> [action-cap]")
        return 1
    run(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 3000)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
