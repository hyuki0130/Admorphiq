"""Is dc22's level-6 goal reachable at all, and what happens when the mover touches it?

The goal on level 6 is `goknoi-dokmdr` — pixel-identical to every earlier goal but also tagged
`buezna`, the class whose activation drives the colour cycle. gantry's route BFS returns no path.
Two very different things could be true: the goal cell is unreachable, or it is reachable and
touching it does something other than win. Sweep every cell for a click that moves the mover onto a
colour-11 block, and report what the board does.
"""
from __future__ import annotations

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

    g = np.array(obs.frame[-1], dtype=np.int16)
    # The goal is a 2x2 of colour 11; find every such block on the board.
    blocks = []
    for y in range(63):
        for x in range(63):
            if (g[y:y + 2, x:x + 2] == 11).all():
                blocks.append((y, x))
    keep = []
    for y, x in blocks:
        if not any(abs(y - a) < 3 and abs(x - b) < 3 for a, b in keep):
            keep.append((y, x))
    print(f"level 6: {len(keep)} colour-11 2x2 blocks at {keep}", flush=True)

    # Drive the four directions and see whether any block is ever consumed or reached.
    before = len(keep)
    for i in range(40):
        aid = (i % 4) + 1
        obs = env.step(agent._convert(GameAction.simple(ActionType(aid))))
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        if lvl != 5:
            print(f"LEVEL CLEARED after {i + 1} plain moves")
            return
    g2 = np.array(obs.frame[-1], dtype=np.int16)
    now = sum(1 for y in range(63) for x in range(63) if (g2[y:y + 2, x:x + 2] == 11).all())
    print(f"after 40 moves: colour-11 2x2 coverage {before} -> ~{now} (raw), level still 6")


if __name__ == "__main__":
    main()
