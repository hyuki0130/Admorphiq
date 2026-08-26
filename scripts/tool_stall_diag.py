"""WHY does `graph` stop on a game — states opened, goals drawn, frontier state.

Purpose: stage one of the recorded plan is "strengthen the generic tools until they clear all 25"
(OPERATING_RULES rule 0). The sweep says fifteen games score zero under every tool; it does not say
what is missing. Strengthening a tool needs the failure NAMED per game, not counted.

Expected feedback: per game — distinct states reached, distinct transitions, whether any goal was
drawn, and whether the frontier ran dry or the budget did. A game whose frontier dries with few
states has a perception/expansion problem; one with many states and no goal has a goal-inference
problem; one that exhausts budget while still expanding has a search-efficiency problem. Those are
three different repairs.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402

from admorphiq.harness.loop import UnifiedAgent  # noqa: E402
from admorphiq.harness.registry import default_tools  # noqa: E402


def _no_llm(_messages: object) -> str:
    raise RuntimeError("LLM-free deployment")


def main() -> int:
    game = sys.argv[1]
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next((i for i in arcade.get_environments()
                 if (i.title or i.game_id).lower().startswith(game)), None)
    if info is None:
        print(f"{game}: no such game")
        return 1
    env = arcade.make(info.game_id)
    obs = env.reset()
    tools = default_tools()
    agent = UnifiedAgent(tools, _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]
    levels = 0
    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        levels = getattr(obs, "levels_completed", levels)
    g = next((t for t in tools if type(t).__name__ == "GraphSearchTool"), None)
    states = len(getattr(g, "_edges", {}) or getattr(g, "_nodes", {}) or {})
    tried = getattr(g, "_tried_from", {}) or {}
    trans = sum(len(v) for v in tried.values()) if isinstance(tried, dict) else 0
    goal = getattr(g, "_external_goal", None) or getattr(g, "_goal", None)
    print(f"{game:6s} levels={levels} steps={step} states={states} transitions={trans} "
          f"goal={'yes' if goal else 'NO'} frontier_dry={states > 0 and trans >= states * 3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
