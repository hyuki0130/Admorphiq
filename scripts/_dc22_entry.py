"""Is dc22's level-6 pocket real, or is it measured on a transitional frame?

Everything about the pocket was measured at the instant `levels_completed` reached 5. This
repository has already paid once for reading a board on a level-up frame (ar25 went 1 level -> 8/8
when that was fixed). Let the board SETTLE first, then re-measure how many distinct boards the four
directions reach.

Expected feedback: three boards after settling confirms the pocket. More than three means the pocket
was an artefact of reading the transition, and dc22's diagnosis has to start again.
"""
from __future__ import annotations

import hashlib

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
                if (i.title or i.game_id).lower().startswith("dc22"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    n = 0
    for _ in range(4000):
        if int(getattr(obs, "levels_completed", 0) or 0) >= 5:
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        n += 1
        if n % 100 == 0:
            print(f"  ...{n} actions, level {int(getattr(obs, 'levels_completed', 0) or 0)}",
                  flush=True)
    if int(getattr(obs, "levels_completed", 0) or 0) < 5:
        print("did not reach level 6", flush=True)
        return

    def h(o):
        return hashlib.md5(np.array(o.frame[-1], dtype=np.int16)[:60, :60].tobytes()).hexdigest()[:8]

    for settle in (0, 4, 12):
        # ACTION5 is a no-op in dc22's move table, so it advances time without moving anything.
        for _ in range(settle):
            obs = env.step(agent._convert(GameAction.simple(ActionType(5))))
        seen = {h(obs)}
        for rep in range(24):
            obs = env.step(agent._convert(GameAction.simple(ActionType((rep % 4) + 1))))
            seen.add(h(obs))
        print(f"  after {settle} settling actions: {len(seen)} distinct boards from 24 moves",
              flush=True)


if __name__ == "__main__":
    main()
