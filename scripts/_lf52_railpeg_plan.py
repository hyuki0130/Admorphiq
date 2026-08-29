"""What railpeg actually PLAYS on lf52 level 6, and whether the board obeys.

The tier counts already measured (`win 45 / travel 36 / capture 4`, `_elsewhere` true, four pieces
still standing after 400 actions) say the tool plans constantly and lands nothing. That is one of
two very different faults and the counts cannot separate them: either the PLANS are wrong for the
board, or the plans are right and the CLICKS miss.

So this logs, per proposal: the move at the head of the plan, the two pixels it clicks, the colour
under each pixel, and whether the board changed at all. A select click must land on a pad — colour
14 GREEN or colour 8 RED — and the landing click on bare floor.

Expected feedback: select clicks that land on floor mean the model's lattice is off and the fix is
geometric. Select clicks that land on a pad, with the board refusing anyway, mean the JUMP is
illegal on the real board and the fix is in the planner's notion of what may be jumped.
"""
from __future__ import annotations

import json
import sys
from collections import Counter

import numpy as np

START_LEVEL = 5


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.railpeg import RailPegTool

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("lf52"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tools = default_tools()
    peg = next(t for t in tools if isinstance(t, RailPegTool))

    at6 = [False]
    log: list[dict] = []
    kinds = Counter()
    raw = RailPegTool.propose

    def wrapped(self, frames, o):
        steps = raw(self, frames, o)
        if at6[0] and steps:
            g = np.array(o.frame[-1], dtype=np.int16) if getattr(o, "frame", None) else None
            rec = {"steps": [[s[0], list(s[1]) if s[1] else None] for s in steps]}
            if g is not None:
                rec["under"] = [int(g[p[1], p[0]]) if s[0] == 6 and s[1] else None
                                for s in steps for p in [s[1] or (0, 0)]]
            kinds[str([s[0] for s in steps])] += 1
            if len(log) < 60:
                log.append(rec)
        return steps

    RailPegTool.propose = wrapped
    try:
        agent = UnifiedAgent(tools, _no_llm, giveup=4000, stall=80, ctx_budget=6000)
        frames = [obs]
        start_i = 0
        for i in range(2000):
            lvl = int(getattr(obs, "levels_completed", 0) or 0)
            if lvl >= START_LEVEL and not at6[0]:
                at6[0] = True
                start_i = i
                print(f"# level 6 at action {i}", file=sys.stderr, flush=True)
            if lvl > START_LEVEL:
                break
            if at6[0] and i - start_i > 300:
                break
            act = agent.choose_action(frames, obs)
            data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
            obs = env.step(act, data=data) if data else env.step(act)
            frames.append(obs)
    finally:
        RailPegTool.propose = raw

    g = np.array(obs.frame[-1], dtype=np.int16)
    print(json.dumps({
        "seed": seed, "level": int(getattr(obs, "levels_completed", 0) or 0),
        "green_px": int((g == 14).sum()), "red_px": int((g == 8).sum()),
        "shapes": dict(kinds), "proposals": len(log),
        "sample": log[:24],
        "tiers": dict(getattr(peg, "_tiers", {})),
        # ⛔ The direction map is the suspect: on this board the carts leave the ten-cell window
        # after two or three presses, so `_calibrate` sees no displacement to read and ages out,
        # EXCLUDING the one action that works. An empty `_dirmap` with ACTION4 in `_excluded` is
        # that trap, measured rather than inferred.
        "dirmap": {str(k): v for k, v in getattr(peg, "_dirmap", {}).items()},
        "excluded": {str(k): sorted(v) for k, v in getattr(peg, "_excluded", {}).items()},
        "pending": str(getattr(peg, "_pending", None)),
    }), flush=True)


if __name__ == "__main__":
    main()
