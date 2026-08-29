"""How many of the 25 games can BudgetReader actually read?

`tools/budget.py` records that thirteen games declare a per-level budget and END on overrun, and it
is imported by exactly one tool. On wa30 it returns None on every level, because wa30 paints its
budget as a PROPORTION bar rather than consuming a fixed drawing. Before extending the reader, size
the extension: run it on every game and count how many it reads at all.

⛔ Direction named (rule 7f): report the level reached, never just that it changed.
"""
from __future__ import annotations

import json
import sys


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.budget import BudgetReader

    title = sys.argv[1]
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 400

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    reader = BudgetReader()
    frames = [obs]
    reads = 0
    seen_total = None
    for _ in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        fr = getattr(obs, "frame", None)
        if fr:
            reader.observe(fr[-1])
        if reader.total() is not None:
            reads += 1
            seen_total = reader.total()
    print(json.dumps({"game": title, "frames_with_a_reading": reads, "total_seen": seen_total,
                      "level": int(getattr(obs, "levels_completed", 0) or 0)}))


if __name__ == "__main__":
    main()
