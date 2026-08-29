"""Is dc22 level 6's single cycling tile visible and live?

The source gives the whole level a very small centre of gravity: on level 6, and only there, exactly
ONE `tewfut` sprite — the one at (18, 48) — is given the `tewfut-color-cycle` tag, and
`mzuiagpcmy` advances it through four types in a fixed order. Everything else is static.

Before building anything for it, check that it is real and observable: does a small region of the
board change colour on its own while nothing else does?

Expected feedback: one small region cycling confirms the mechanic and gives the tool something to
detect. Nothing cycling means the tag is inert without some trigger, and that trigger is the next
thing to find.
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

    g0 = np.array(obs.frame[-1], dtype=np.int16)
    print(f"level 6 reached; colours {sorted(set(np.unique(g0).tolist()))}", flush=True)
    hist = []
    for i in range(12):
        obs = env.step(agent._convert(GameAction.simple(ActionType(7))))
        g = np.array(obs.frame[-1], dtype=np.int16)
        d = np.argwhere(g != g0)
        if len(d):
            ys, xs = d[:, 0], d[:, 1]
            hist.append((len(d), int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())))
        g0 = g
    if not hist:
        print("nothing changes under twelve inert actions — the cycle needs a trigger")
        return
    for n, y0, y1, x0, x1 in hist[:8]:
        print(f"  changed {n} px in rows {y0}..{y1} cols {x0}..{x1}")


if __name__ == "__main__":
    main()
