"""Sweep every click from EACH of the pocket's three mover positions.

The earlier sweep swept 1024 cells but only from one of the three boards the pocket contains, so two
thirds of the (mover position, click) combinations were never tried. A click's effect can depend on
where the mover is — the level's own switch is a click — so this closes the hole before dc22 is
called unwinnable from its arrival state.
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
        if n % 150 == 0:
            print(f"  ...{n} actions to reach level 6", flush=True)
    if int(getattr(obs, "levels_completed", 0) or 0) < 5:
        print("did not reach level 6", flush=True)
        return

    last = {"g": None}

    def h(o):
        # ⚠️ `frame` comes back EMPTY on some transitions — a click that ends a level, or a state
        # the engine is mid-way through. Reusing the previous board there is correct (nothing new is
        # observable) and stops the sweep dying 300 actions in, which is how this probe was lost once.
        fr = getattr(o, "frame", None)
        if fr:
            last["g"] = np.array(fr[-1], dtype=np.int16)
        if last["g"] is None:
            return "empty"
        return hashlib.md5(last["g"][:60, :60].tobytes()).hexdigest()[:8]

    seen = {h(obs)}
    # Position 0 = as arrived; 1 = after UP; 2 = after LEFT. Sweep every cell from each.
    for pos, prep in enumerate(((), (1,), (3,))):
        for a in prep:
            obs = env.step(agent._convert(GameAction.simple(ActionType(a))))
        base = h(obs)
        fresh = 0
        for cy in range(0, 64, 2):
            for cx in range(0, 64, 2):
                o = env.step(agent._convert(GameAction.coordinate(cx, cy)), data={"x": cx, "y": cy})
                k = h(o)
                if k not in seen:
                    seen.add(k)
                    fresh += 1
                obs = o
                if int(getattr(obs, "levels_completed", 0) or 0) != 5:
                    print(f"LEVEL CLEARED from position {pos} by a click at ({cy},{cx})", flush=True)
                    return
                # return to this position so each click is judged from the same board
                if k != base:
                    for a in (2, 4):
                        obs = env.step(agent._convert(GameAction.simple(ActionType(a))))
        print(f"  position {pos}: {fresh} boards not seen before; running total {len(seen)}",
              flush=True)
    print(f"pocket size across all three mover positions: {len(seen)} boards")


if __name__ == "__main__":
    main()
