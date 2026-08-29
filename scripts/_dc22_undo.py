"""Does dc22 have a restoring undo? If it does, its level 6 can be searched EXHAUSTIVELY.

Sixty blind searches reached at most 130 distinct boards in 900 actions, so the reachable space is
narrow — narrow enough to enumerate, IF a state can be restored. The game keeps an `UndoState`, and
ACTION5 is a no-op in the move table, so one of the actions may put the board back. Test each one:
hash the board, act, try the candidate restore, hash again.
"""
from __future__ import annotations

import hashlib

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
        print("did not reach level 6", flush=True)
        return

    def h(o):
        return hashlib.md5(np.array(o.frame[-1], dtype=np.int16)[:60, :60].tobytes()).hexdigest()[:8]

    # The four directions only produce three boards from here — 1 and 2 are exact inverses, so are
    # 3 and 4. The mover is in a POCKET. Does any click escape it? Sweep every cell and count the
    # distinct boards reachable in one action.
    seen = {h(obs)}
    n = 0
    escapes = []
    for cy in range(0, 64, 2):
        for cx in range(0, 64, 2):
            o = env.step(agent._convert(GameAction.coordinate(cx, cy)), data={"x": cx, "y": cy})
            k = h(o)
            if k not in seen:
                seen.add(k)
                escapes.append((cy, cx, k))
            obs = o
            n += 1
            if n % 128 == 0:
                print(f"  swept {n}/1024, distinct boards {len(seen)}", flush=True)
            if int(getattr(obs, "levels_completed", 0) or 0) != 5:
                print(f"LEVEL CLEARED by a click at ({cy},{cx})")
                return
    print(f"clicks swept: 1024; distinct boards reached: {len(seen)}")
    for cy, cx, k in escapes[:10]:
        print(f"  new board {k} from click ({cy},{cx})")
