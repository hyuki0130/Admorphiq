"""Replay the first N clicks of the winning sweep — bisect what actually opens dc22's level 6.

The sweep clears the level after hundreds of sequential clicks, and the single cell it was on does
not clear it alone. The click ORDER is deterministic (row-major, stride 2, from the arrival
position), so replaying a prefix of length N and asking whether the level cleared localises the
cause. One N per process; the box runs many at once.
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

    want = int(sys.argv[1])

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
        print(json.dumps({"n": want, "error": "level 6 not reached"}))
        return

    import hashlib
    last = {"g": None}

    def h(o):
        fr = getattr(o, "frame", None)
        if fr:
            last["g"] = np.array(fr[-1], dtype=np.int16)
        if last["g"] is None:
            return "empty"
        return hashlib.md5(last["g"][:60, :60].tobytes()).hexdigest()[:8]

    base = h(obs)

    def alive(o):
        fr = getattr(o, "frame", None)
        return bool(fr)

    i = 0
    for cy in range(0, 64, 2):
        for cx in range(0, 64, 2):
            if i >= want:
                lvl = int(getattr(obs, "levels_completed", 0) or 0)
                print(json.dumps({"n": want, "cleared": lvl > 5, "level": lvl,
                                  "stopped_at": [cy, cx]}))
                return
            obs = env.step(agent._convert(GameAction.coordinate(cx, cy)), data={"x": cx, "y": cy})
            i += 1
            if int(getattr(obs, "levels_completed", 0) or 0) > 5:
                print(json.dumps({"n": want, "cleared": True, "at_click": i,
                                  "cell": [cy, cx]}))
                return
            # ⛔ THE RETURN MOVES ARE PART OF THE SEQUENCE. The sweep that cleared this level went
            # back to its base board after any click that changed the hash, by pressing DOWN then
            # RIGHT. A bisect that replays only the clicks fails at every prefix INCLUDING the full
            # 1024 — measured — because the win needs the interleaved moves too.
            k = h(obs)
            if k != base:
                for a in (2, 4):
                    obs = env.step(agent._convert(GameAction.simple(ActionType(a))))
                    if int(getattr(obs, "levels_completed", 0) or 0) > 5:
                        print(json.dumps({"n": want, "cleared": True, "at_click": i,
                                          "on_return_move": a, "cell": [cy, cx]}))
                        return
    print(json.dumps({"n": want, "cleared": False, "level": 5, "exhausted": True}))


if __name__ == "__main__":
    main()
