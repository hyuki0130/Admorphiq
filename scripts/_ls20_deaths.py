"""Does ls20's tool actually run out of fuel, or is its 302 actions pure exploration?

The source says the level carries ~21 actions of fuel, refilled by `npxgalaybz` pickups, and that
running dry costs one of three lives, returns the avatar to the start and paints a FULL-SCREEN
overlay. That overlay is now a meaningful detector rather than the noise that broke three earlier
instruments: a step that repaints most of the frame is a death.

Expected feedback: many overlay frames mean fuel is binding and routing through pickups is the
lever. None means the tool never runs dry, fuel is not the constraint, and the 302 is exploration
that has to be attacked some other way.
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
                if (i.title or i.game_id).lower().startswith("ls20"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    prev = None
    per_level: dict[int, list[int]] = {}
    lvl = 0
    for _ in range(4000):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        lvl = int(getattr(obs, "levels_completed", lvl) or 0)
        g = np.array(obs.frame[-1], dtype=np.int16)
        if prev is not None:
            per_level.setdefault(lvl, []).append(int((g != prev).sum()))
        prev = g
    print("level  steps  frames repainting >50% of the board (death overlays)")
    for k in sorted(per_level):
        d = per_level[k]
        big = sum(1 for n in d if n > 2048)
        print(f"  {k + 1:2d}   {len(d):5d}   {big}")


if __name__ == "__main__":
    main()
