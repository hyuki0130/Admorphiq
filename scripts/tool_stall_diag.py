"""WHY does `graph` stop on a game — states opened, goals drawn, frontier state.

Purpose: stage one of the recorded plan is "strengthen the generic tools until they clear all 25"
(OPERATING_RULES rule 0). The sweep says fifteen games score zero under every tool; it does not say
what is missing. Strengthening a tool needs the failure NAMED per game, not counted.

⚠️ This drives the BARE `UnifiedAgent`, which is NOT the deployed generic path. `--agent chained`
puts `WorldModelAgent` in front, and that is where cd82's 6/6-in-108-actions comes from — this
script reports cd82 at 0 because it never runs that stage. Compare its numbers with each other,
never with GENERIC30's.

Expected feedback: per game — distinct states reached, distinct transitions, how many of
those are SELF-LOOPS (an action that changed nothing), and whether any goal was drawn. A game whose
frontier dries with few
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
    # `_edges` is a dict of {state_hash: {action_key: next_hash}} — the states are its keys and
    # the transitions are the inner entries. An earlier version read `_tried_from`, which this tool
    # does not have, so every game reported transitions=0 and that was the instrument, not a finding.
    edges = getattr(g, "_edges", {}) or {}
    states = len(edges)
    trans = sum(len(v) for v in edges.values())
    self_loops = sum(1 for h, d in edges.items() for nxt in d.values() if nxt == h)
    goal = getattr(g, "_external_goal", None) or getattr(g, "_goal", None)
    inert = (100 * self_loops // trans) if trans else 0
    print(f"{game:6s} levels={levels} steps={step} states={states} transitions={trans} "
          f"self_loops={self_loops} ({inert}% inert) goal={'yes' if goal else 'NO'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
