"""Brute-force hunt for ANY sequence that clears dc22's level 6.

Every cheap explanation is closed: no tool goes deeper, no combination helps, and the one mechanic
the source singles out (a colour-cycling tile) does not gate the level. Before building a new
capability for this board it is worth knowing whether the board can be beaten AT ALL by search — a
witness sequence would name what the tool must learn, and a wide failure would say the level needs
something no blind search finds.

One seed per process; the box runs sixty at once.
"""
from __future__ import annotations

import json
import sys

import numpy as np


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.types import ActionType, GameAction

    seed = int(sys.argv[1])
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 900

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("dc22"))
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
        print(json.dumps({"seed": seed, "error": "level 6 not reached"}))
        return

    rng = np.random.default_rng(seed)
    seen = set()
    for step in range(budget):
        # A mix of plain moves and clicks: the level's own switch is a click, and the mover is moved
        # by the four directions. Weighted toward moves because they are what advances a route.
        if rng.random() < 0.75:
            aid = int(rng.integers(1, 5))
            obs = env.step(agent._convert(GameAction.simple(ActionType(aid))))
        else:
            cy, cx = int(rng.integers(0, 64)), int(rng.integers(0, 64))
            obs = env.step(agent._convert(GameAction.coordinate(cx, cy)),
                           data={"x": cx, "y": cy})
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        if lvl != 5:
            print(json.dumps({"seed": seed, "CLEARED": True, "at": step + 1}))
            return
        seen.add(np.array(obs.frame[-1], dtype=np.int16)[:60, :60].tobytes())
    print(json.dumps({"seed": seed, "cleared": False, "distinct_states": len(seen)}))


if __name__ == "__main__":
    main()
