"""What does a SUCCESSFUL capture look like in lf52? Learn it where the tool already wins.

Level 6 resists every single click and every arrow, and the board it presents on entry has three
pads that nothing touches. But the tool clears levels 1-5, so a capture demonstrably happens there.
This logs every action that changes the pad-pixel count, with the action that caused it, so the
interaction protocol is read off a level that works rather than guessed at on the one that does not.

Expected feedback: a repeating (action, effect) pattern names the protocol — e.g. "a click at a pad
followed by a click N cells away". Pad pixels that only ever fall at a LEVEL BOUNDARY would mean the
captures are not what clears these levels at all, and the goal reading needs rework.
"""
from __future__ import annotations

import numpy as np

GREEN = 14


def ngreen(o) -> int:
    return int((np.array(o.frame[-1], dtype=np.int16) == GREEN).sum())


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("lf52"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    prev = ngreen(obs)
    lvl = 0
    print(f"level 1 start: {prev} green ({prev // 12} pads)", flush=True)
    for step in range(1200):
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        aid = int(getattr(act, "id", getattr(act, "value", -1)) or -1)
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = ngreen(obs)
        nl = int(getattr(obs, "levels_completed", 0) or 0)
        if nl != lvl:
            print(f"--- LEVEL {lvl} -> {nl} at step {step}; green {prev} -> {now} "
                  f"({now // 12} pads)", flush=True)
            lvl = nl
            prev = now
            if lvl >= 5:
                return
            continue
        # EVERY action for the first stretch, not only the ones that change the pad count. The
        # capturing clicks landed on odd steps, and inferring what the even steps were is exactly
        # the guess that has cost this round four wrong models.
        if step < 12 or now != prev:
            if data and "x" in data:
                gg = np.array(frames[-2].frame[-1], dtype=np.int16)
                under = int(gg[int(data["y"]), int(data["x"])])
                where = f"({data['x']},{data['y']}) on colour {under}"
            else:
                where = "simple"
            mark = f"  green {prev} -> {now}" if now != prev else ""
            print(f"  step {step} lvl{lvl} act={aid} {where}{mark}", flush=True)
            prev = now


if __name__ == "__main__":
    main()
