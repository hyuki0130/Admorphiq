"""Click, THEN move — the combination dc22's pocket was never tested against.

From the arrival position the four directions reach three boards and single clicks reach seven. But
the level's own machinery is a click that changes terrain (a `buezna` advances a colour cycle), so
the intended shape is plausibly "change the board, then walk". Sweep a band of cells: click each,
then try all four moves, and report any board outside the known pocket.

⛔ Direction is named explicitly (rule 7f): a level number that FALLS is a collapse, not a clear.
"""
from __future__ import annotations

import hashlib
import json
import sys

import numpy as np


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.types import ActionType, GameAction

    y0, y1 = int(sys.argv[1]), int(sys.argv[2])

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
        print(json.dumps({"band": [y0, y1], "error": "level 6 not reached"}))
        return

    last = {"g": None}

    def h(o):
        fr = getattr(o, "frame", None)
        if fr:
            last["g"] = np.array(fr[-1], dtype=np.int16)
        if last["g"] is None:
            return "empty"
        return hashlib.md5(last["g"][:60, :60].tobytes()).hexdigest()[:8]

    seen = {h(obs)}
    novel = 0
    for cy in range(y0, y1, 2):
        for cx in range(0, 64, 2):
            obs = env.step(agent._convert(GameAction.coordinate(cx, cy)), data={"x": cx, "y": cy})
            lv = int(getattr(obs, "levels_completed", 0) or 0)
            if lv > 5:
                print(json.dumps({"band": [y0, y1], "CLEARED": True, "cell": [cy, cx]}))
                return
            if lv < 5:
                print(json.dumps({"band": [y0, y1], "collapsed_at": [cy, cx], "to_level": lv}))
                return
            for a in (1, 2, 3, 4):
                obs = env.step(agent._convert(GameAction.simple(ActionType(a))))
                lv = int(getattr(obs, "levels_completed", 0) or 0)
                if lv > 5:
                    print(json.dumps({"band": [y0, y1], "CLEARED": True,
                                      "cell": [cy, cx], "then_move": a}))
                    return
                if lv < 5:
                    print(json.dumps({"band": [y0, y1], "collapsed_at": [cy, cx],
                                      "then_move": a, "to_level": lv}))
                    return
                k = h(obs)
                if k not in seen:
                    seen.add(k)
                    novel += 1
    print(json.dumps({"band": [y0, y1], "cleared": False, "boards": len(seen), "novel": novel}))


if __name__ == "__main__":
    main()
