"""Is lf52's level 6 reachable by SEARCH over the launch mechanic?

Level 6 offers exactly one effective direction at its start (RIGHT, a six-cell launch) and the
other three are inert. This walks the state graph over the four directions, hashing the board, to
answer the only question that decides whether a tool can be built for it: does the reachable set
grow, or does the level cycle between a handful of states?

Expected feedback: a growing distinct-state count (and ideally levels_completed rising) means a
launch-aware search clears the level and the tool lever is "model the launch, then BFS". A set that
saturates at two or three states means the level needs a verb this walk does not have.
"""
from __future__ import annotations

import sys

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
    obs = env.step(agent._convert(GameAction.simple(ActionType(5))))   # fresh level

    def board(o) -> bytes:
        g = np.array(o.frame[-1], dtype=np.int16)
        return g[:60, :60].tobytes()          # drop the edge counter, which changes every action

    seen = {board(obs)}
    lvl0 = int(getattr(obs, "levels_completed", 0) or 0)
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    rng = np.random.default_rng(seed)
    for step in range(600):
        aid = int(rng.integers(1, 5))
        obs = env.step(agent._convert(GameAction.simple(ActionType(aid))))
        seen.add(board(obs))
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        if lvl != lvl0:
            print(f"LEVEL CHANGED at step {step}: {lvl0} -> {lvl}", flush=True)
            lvl0 = lvl
        if str(getattr(obs, "state", "")).endswith("GAME_OVER"):
            print(f"GAME_OVER at step {step}", flush=True)
            break
    print(f"seed {seed}: {len(seen)} distinct boards over 600 moves; levels={lvl0}")


if __name__ == "__main__":
    main()
