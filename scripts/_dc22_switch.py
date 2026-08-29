"""Can the cycling tile at (18, 48) actually be advanced, and does anything open when it is?

The source says one `buezna` interaction advances one tile through four colours, and that gantry
retires on this level because its route BFS finds no path. If those two facts are connected, driving
the switch should change the board near (row 48, col 18) — and the point of building anything for
dc22 depends on it.

Expected feedback: a click that changes that neighbourhood names the switch and confirms the
mechanic is reachable. Nothing changing anywhere means the trigger needs a state the tool must reach
first, which is a different and larger problem.
"""
from __future__ import annotations

import numpy as np


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.types import GameAction

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
        print("did not reach level 6")
        return

    def board(o):
        return np.array(o.frame[-1], dtype=np.int16)

    # The tile the source names, in frame coordinates, with a small margin.
    ty0, ty1, tx0, tx1 = 44, 53, 14, 23
    hits = []
    for cy in range(0, 64, 4):
        for cx in range(0, 64, 4):
            before = board(obs)
            obs = env.step(agent._convert(GameAction.coordinate(cx, cy)),
                           data={"x": cx, "y": cy})
            after = board(obs)
            tile = int((before[ty0:ty1, tx0:tx1] != after[ty0:ty1, tx0:tx1]).sum())
            whole = int((before != after).sum())
            if tile:
                hits.append((cy, cx, tile, whole))
            if int(getattr(obs, "levels_completed", 0) or 0) != 5:
                print(f"LEVEL CLEARED by a click at ({cy},{cx})")
                return
    print(f"clicks that changed the tile neighbourhood: {len(hits)}")
    for cy, cx, tile, whole in hits[:8]:
        print(f"  click ({cy},{cx}): {tile} px at the tile, {whole} on the whole board")


if __name__ == "__main__":
    main()
