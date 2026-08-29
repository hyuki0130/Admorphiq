"""One tool, alone, on one game — so the stuck levels can be swept in parallel.

Rule 7b says sweep for an unused asset before digging, and the round has been digging one game at a
time on a 64-core box that sat idle. This forces a single tool to own every decision, so every
(game, tool) pair can be measured at once and any tool that clears a level another tool cannot is
found by measurement rather than by reasoning about detectors.
"""
from __future__ import annotations

import json
import sys


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    title, want = sys.argv[1], sys.argv[2]
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 3000

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    tools = [t for t in default_tools() if t.name == want]
    if not tools:
        print(json.dumps({"game": title, "tool": want, "error": "no such tool"}))
        return

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(tools, _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]
    lvl = 0
    step = 0
    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        lvl = max(lvl, int(getattr(obs, "levels_completed", lvl) or 0))
    print(json.dumps({"game": title, "tool": want, "levels": lvl, "actions": step + 1}))


if __name__ == "__main__":
    main()
