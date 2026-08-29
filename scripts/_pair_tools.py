"""Two or three tools together on one game — does a PAIR reach deeper than either alone?

The full sweep found exactly one stuck game where more than one tool has real competence: lf52,
where railpeg reaches 5 levels, pegjump 4 and hop 3, independently. If they know different things,
the harness giving them the board in turn should reach further than any of them alone. If they know
the same thing, it will not, and lf52's ceiling is a property of the mechanic rather than of who
holds it.
"""
from __future__ import annotations

import json
import sys


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    title = sys.argv[1]
    names = sys.argv[2].split(",")
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 2500

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    tools = [t for t in default_tools() if t.name in names]
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(tools, _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]
    lvl = step = 0
    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        lvl = max(lvl, int(getattr(obs, "levels_completed", lvl) or 0))
    print(json.dumps({"game": title, "tools": sys.argv[2], "levels": lvl, "actions": step + 1}))


if __name__ == "__main__":
    main()
