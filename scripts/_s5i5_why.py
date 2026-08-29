"""Five hypotheses for s5i5 level 7, tested together (rule 7h) — not one probe, five.

The level needs one more of two targets covered; the harness never raises the count in 503 actions
and all sixty random seeds COLLAPSE the level. Hypotheses, selected by the first argument:

  1  what the uncovered target and the movers actually are (positions, counts)
  2  does ANY single action cover it
  3  what collapses the level — which action class loses it
  4  is the collapse immediate or after N actions
  5  can the mover reach the target's row/column at all
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

    which = int(sys.argv[1])

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

    def state():
        lvl = getattr(game, "current_level", None) if game else None
        if lvl is None:
            return None
        tgt = [(s.x, s.y) for s in lvl.get_sprites_by_tag("0087vvmblxkzdi")]
        mov = [(s.x, s.y) for s in lvl.get_sprites_by_tag("0064ocqkuqacti")]
        return tgt, mov

    for _ in range(4000):
        if int(getattr(obs, "levels_completed", 0) or 0) >= 6:
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
    if int(getattr(obs, "levels_completed", 0) or 0) < 6:
        print(json.dumps({"h": which, "error": "level 7 not reached"}))
        return

    st = state()
    if which == 1:
        tgt, mov = st
        cov = [t for t in tgt if t in mov]
        print(json.dumps({"h": 1, "targets": tgt, "movers": mov, "covered": cov}))
        return

    if which == 2:
        tgt, mov = st
        for aid in (1, 2, 3, 4, 5, 7):
            o = env.step(agent._convert(GameAction.simple(ActionType(aid))))
            s2 = state()
            lv = int(getattr(o, "levels_completed", 0) or 0)
            if lv != 6 or (s2 and len([t for t in s2[0] if t in s2[1]]) > len(
                    [t for t in tgt if t in mov])):
                print(json.dumps({"h": 2, "action": aid, "level": lv,
                                  "covered": len([t for t in s2[0] if t in s2[1]]) if s2 else None}))
                return
        print(json.dumps({"h": 2, "no_single_simple_action_helps": True}))
        return

    if which in (3, 4):
        rng = np.random.default_rng(which)
        for step in range(300):
            aid = int(rng.integers(1, 6))
            o = env.step(agent._convert(GameAction.simple(ActionType(aid))))
            lv = int(getattr(o, "levels_completed", 0) or 0)
            if lv < 6:
                print(json.dumps({"h": which, "collapsed_after": step + 1, "by_action": aid,
                                  "to_level": lv}))
                return
        print(json.dumps({"h": which, "survived_300_moves": True}))
        return

    tgt, mov = st
    print(json.dumps({"h": 5, "target_rows": sorted({t[1] for t in tgt}),
                      "mover_rows": sorted({m[1] for m in mov}),
                      "target_cols": sorted({t[0] for t in tgt}),
                      "mover_cols": sorted({m[0] for m in mov})}))


if __name__ == "__main__":
    main()
