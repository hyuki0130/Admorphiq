"""Does bp35's level 6 FILL over time?

The board is repainted mid-level: 1,961 of 4,096 pixels differ from the frame crag last mapped,
background (colour 10) giving way to colour 5, across all 64 rows. And the difference grew by one
pixel per action across eight consecutive failures. A progressive fill would make this level a timed
escape, which is a different problem from the static-terrain descent crag models and clears.

Expected feedback: a monotone rise in the fill colour names the mechanic and the tool needed. A flat
count means the repaint is a one-off event, and what matters is what triggers it.
"""
from __future__ import annotations

import numpy as np


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.types import ActionType, GameAction

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("bp35"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    for _ in range(4000):
        if int(getattr(obs, "levels_completed", 0) or 0) >= 5:
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
    if int(getattr(obs, "levels_completed", 0) or 0) < 5:
        print("did not reach level 6")
        return

    def census(o):
        g = np.array(o.frame[-1], dtype=np.int16)
        v, c = np.unique(g, return_counts=True)
        return {int(a): int(b) for a, b in zip(v, c, strict=True)}

    print("step  colour5  colour10  (fill vs background)", flush=True)
    for step in range(60):
        c = census(obs)
        if step % 5 == 0:
            print(f"  {step:3d}  {c.get(5, 0):6d}  {c.get(10, 0):7d}", flush=True)
        obs = env.step(agent._convert(GameAction.simple(ActionType(3 if step % 2 else 4))))
        if str(getattr(obs, "state", "")).endswith("GAME_OVER"):
            print(f"  GAME_OVER at step {step}", flush=True)
            break
    c = census(obs)
    print(f"  end   {c.get(5, 0):6d}  {c.get(10, 0):7d}")


if __name__ == "__main__":
    main()
