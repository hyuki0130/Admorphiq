"""Does aiming at the GOAL clear lf52's level 6, where blind search does not?

The source says the level is won when the pad count (`fozwvlovdui`) falls to 2 at levels 6-7. The
pads are not directly visible, but the probe showed one colour changing SIZE as pieces move
(40 <-> 34 pixels) while every other colour holds its cell count — so a colour whose pixel count
DROPS is the pad set being consumed. This searches for actions that reduce it.

Expected feedback: a level clear (or a monotone drop in the shrinking colour's count) means the
lever is "count the pads and search toward fewer", and the tool work is worth doing. No drop under
any action means the pads are not what this colour tracks, and the goal reading needs another
source read before any tool is written.
"""
from __future__ import annotations

import sys

import numpy as np


def counts(o) -> dict[int, int]:
    g = np.array(o.frame[-1], dtype=np.int16)[:60, :60]
    v, c = np.unique(g, return_counts=True)
    return {int(a): int(b) for a, b in zip(v, c, strict=True)}


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.types import ActionType, GameAction

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    budget = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("lf52"))
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

    # ⛔ The trial loop below assumes ACTION7 restores the board. Verify it before trusting a
    # single number that loop produces: hash the board, act, undo, hash again.
    import hashlib

    def h(o) -> str:
        return hashlib.md5(np.array(o.frame[-1], dtype=np.int16)[:60, :60].tobytes()).hexdigest()[:8]

    for aid in (1, 2, 3, 4):
        h0 = h(obs)
        o1 = env.step(agent._convert(GameAction.simple(ActionType(aid))))
        h1 = h(o1)
        o2 = env.step(agent._convert(GameAction.simple(ActionType(7))))
        h2 = h(o2)
        print(f"  undo check aid={aid}: before {h0} after {h1} undone {h2} "
              f"-> {'RESTORES' if h2 == h0 else 'DOES NOT RESTORE'}", flush=True)
        obs = o2
    start = counts(obs)
    print("level 6 start counts:", {k: v for k, v in start.items() if v <= 300})
    best = dict(start)
    lvl0 = 5
    rng = np.random.default_rng(7)
    # ⛔ NO TRIALS. ACTION7 was measured NOT to restore the board (see the check above), so a
    # look-ahead that undoes its probe corrupts the very state it is scoring — an earlier version of
    # this loop did exactly that and reported two colours vanishing, which was the trials, not the
    # game. Every action here is committed and judged after the fact.
    for step in range(budget):
        aid = int(rng.integers(1, 5))
        obs = env.step(agent._convert(GameAction.simple(ActionType(aid))))
        now = counts(obs)
        for k in sorted(set(best) | set(now)):
            if 0 < best.get(k, 0) <= 300 and now.get(k, 0) != best.get(k, 0):
                print(f"  step {step} act{aid}: colour {k} {best.get(k, 0)} -> {now.get(k, 0)}",
                      flush=True)
        best = now
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        if lvl != lvl0:
            print(f"LEVEL CLEARED at step {step}: {lvl0} -> {lvl}", flush=True)
            return
        if str(getattr(obs, "state", "")).endswith("GAME_OVER"):
            print(f"GAME_OVER at step {step}")
            return
    print("no clear; final small-colour counts:",
          {k: v for k, v in best.items() if v <= 300})


if __name__ == "__main__":
    main()
