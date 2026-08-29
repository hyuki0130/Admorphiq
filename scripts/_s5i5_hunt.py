"""Does a solution to s5i5 level 7 exist within reach of search? One seed per process.

The level needs ONE more target covered: two targets, one already covered at the start, and the
harness spends 503 actions without the count ever rising. Before building a tool for it, establish
whether any sequence covers the second target — a witness names what the tool must do, and a wide
failure says the level needs something search cannot stumble into.

Reports the game's own predicate (covered/total), not a guess from pixels.
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
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 700

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("s5i5"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    game = getattr(env, "_game", None) or getattr(env, "game", None)

    def cover():
        lvl = getattr(game, "current_level", None) if game else None
        if lvl is None:
            return None
        tgt = lvl.get_sprites_by_tag("0087vvmblxkzdi")
        mov = lvl.get_sprites_by_tag("0064ocqkuqacti")
        return sum(1 for t in tgt if any(m.x == t.x and m.y == t.y for m in mov)), len(tgt)

    for _ in range(4000):
        if int(getattr(obs, "levels_completed", 0) or 0) >= 6:
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
    if int(getattr(obs, "levels_completed", 0) or 0) < 6:
        print(json.dumps({"seed": seed, "error": "level 7 not reached"}))
        return

    rng = np.random.default_rng(seed)
    best = cover()
    for step in range(budget):
        if rng.random() < 0.5:
            obs = env.step(agent._convert(GameAction.simple(ActionType(int(rng.integers(1, 6))))))
        else:
            cy, cx = int(rng.integers(0, 64)), int(rng.integers(0, 64))
            obs = env.step(agent._convert(GameAction.coordinate(cx, cy)), data={"x": cx, "y": cy})
        lv = int(getattr(obs, "levels_completed", 0) or 0)
        if lv > 6:
            print(json.dumps({"seed": seed, "CLEARED": True, "at": step + 1}))
            return
        if lv < 6:
            print(json.dumps({"seed": seed, "collapsed_to": lv, "at": step + 1}))
            return
        c = cover()
        if c and best and c[0] > best[0]:
            best = c
            print(json.dumps({"seed": seed, "coverage_rose_to": c[0], "of": c[1], "at": step + 1}))
    print(json.dumps({"seed": seed, "cleared": False, "best": best}))


if __name__ == "__main__":
    main()
