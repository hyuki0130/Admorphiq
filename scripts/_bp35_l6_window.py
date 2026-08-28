"""What is in the window crag cannot place on bp35's level 6?

crag stitches a world from camera windows and refuses to act when a new window scores below
`_ALIGN_FIT` against it. On level 6 it scores 0.60 and 0.565 against 0.82, and accepting those
windows anyway (threshold lowered to 0.50) does not help — so the window is not merely misjudged.
Nobody has looked at what the disagreeing cells actually are.

Expected feedback: if the disagreement is concentrated in cells that MOVE, the world needs those
marked volatile and the alignment is fine. If it is spread across static terrain, the stitch is
placing the window at the wrong offset and the shift search is the thing at fault.
"""
from __future__ import annotations

import numpy as np


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("bp35"))
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

    # ⛔ crag's stitch searches VERTICAL shifts only — `self._world.get((r + shift, c))` uses the
    # column unchanged — because its docstring records a board "three to four times as deep" as the
    # ten-row window. If this level pans HORIZONTALLY the window can never be placed, which is
    # exactly the "window does not belong to this board" it reports. Measure the pan directly:
    # take a lateral action and see whether the static content shifts in ROWS, COLUMNS, or neither.
    from admorphiq.types import ActionType, GameAction

    def board(o):
        return np.array(o.frame[-1], dtype=np.int16)

    def best_shift(a, b, axis):
        """The offset that best explains b as a shifted copy of a, and how well it does."""
        best = (0.0, 0)
        for d in range(-12, 13):
            aa = np.roll(a, d, axis=axis)
            if d > 0:
                sl = (slice(d, None), slice(None)) if axis == 0 else (slice(None), slice(d, None))
            elif d < 0:
                sl = (slice(None, d), slice(None)) if axis == 0 else (slice(None), slice(None, d))
            else:
                sl = (slice(None), slice(None))
            score = float((aa[sl] == b[sl]).mean())
            if score > best[0]:
                best = (score, d)
        return best

    for aid, name in ((3, "LEFT"), (4, "RIGHT"), (1, "UP"), (2, "DOWN")):
        g0 = board(obs)
        obs = env.step(agent._convert(GameAction.simple(ActionType(aid))))
        g1 = board(obs)
        if (g0 == g1).all():
            print(f"  {name}: board unchanged", flush=True)
            continue
        rs, rd = best_shift(g0, g1, 0)
        cs, cd = best_shift(g0, g1, 1)
        print(f"  {name}: best ROW shift {rd:+d} fits {rs:.3f} | "
              f"best COLUMN shift {cd:+d} fits {cs:.3f}", flush=True)


if __name__ == "__main__":
    main()
