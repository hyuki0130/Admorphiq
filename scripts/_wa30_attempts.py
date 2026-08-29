"""Inside wa30's level 9: does shepherd make progress and get cut off, or flail?

The level allows 70 actions and losing on overrun restarts it, so the 508 actions shepherd spends
are roughly seven attempts. Budget awareness is only worth wiring if the attempts are PROGRESSING
and being cut short. Segment the 508 by the restarts and report how much of the board each attempt
changes, and whether later attempts differ from earlier ones.

⛔ Direction named (rule 7f): a level number that falls is a restart, not a clear.
"""
from __future__ import annotations

import numpy as np


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("wa30"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    lvl = 0
    while lvl < 8:
        if agent.is_done(frames, obs):
            print("agent stopped before level 9", flush=True)
            return
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        lvl = int(getattr(obs, "levels_completed", lvl) or 0)
    print("on level 9", flush=True)

    prev = None
    run = 0
    changed = 0
    attempts = []
    for _ in range(520):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", 8) or 0)
        if now > 8:
            print(f"CLEARED level 9 after {run} actions in this attempt", flush=True)
            return
        fr = getattr(obs, "frame", None)
        g = np.array(fr[-1], dtype=np.int16) if fr else prev
        run += 1
        if prev is not None and g is not None:
            d = int((g != prev).sum())
            changed += d > 8
            if d > 2048:                      # a restart repaints the board
                attempts.append((run, changed))
                run = changed = 0
        prev = g
    attempts.append((run, changed))
    print(f"attempts on level 9 (actions, actions that moved the board): {attempts}", flush=True)


if __name__ == "__main__":
    main()
