"""Does lf52's level 6 RESTART, or did my restart detector measure something else?

⛔ THIS EXISTS BECAUSE THE FIRST INSTRUMENT MAY HAVE BEEN MEASURING THE WRONG QUANTITY. I reported
"~four genuine restarts on level 6" from a detector that fires when the MODEL's piece count goes
UP, on the reasoning that a capture game only ever removes pieces. But the model gains pieces when
the CAMERA REVEALS MORE BOARD, which is exactly what this level does — so the detector cannot tell
a restart from a discovery, and that is the plausible-number-for-the-wrong-quantity family that
cost this round twelve findings.

`scripts/attempt_probe.py` cannot settle it either: it prices attempts per COMPLETED level, so the
one level that never completes is invisible to it (it reports binned 0 for L1-L5 and says nothing
about L6).

The decisive signal is the RAW FRAME, not the model. A restart resets the board AND the camera, so
the level's opening frame reappears byte-for-byte; a discovery never reproduces it. This counts
exact recurrences of the first level-6 frame, and — because a restart might reset to a frame that
is not the first one seen — also reports how many distinct frames repeat at all, and the largest
backward jump to an already-seen frame.

The instrument proves itself: `frames` is how many level-6 frames it hashed, and 0 measured
nothing. `distinct` against `frames` says whether the board is moving at all.

Expected feedback: `opening_recurrences` > 0 means the level really is being lost and replayed, and
the earlier reading stands. 0, with a healthy `distinct`, means there are no restarts and my
"four attempts" was the camera revealing pieces — in which case the level stalls rather than dies,
and the work behind those two is opposite.
"""
from __future__ import annotations

import hashlib
import json
import sys

START = 5
MAX_ACTIONS = 4000


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    import numpy as np
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    def digest(o) -> str:
        arr = np.array(o.frame[-1], dtype=np.int16)
        return hashlib.md5(arr.tobytes()).hexdigest()[:12]

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("lf52"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=8000, stall=80, ctx_budget=6000)

    opening = None
    seen: dict[str, int] = {}
    order: list[str] = []
    recurrences: list[int] = []
    back_jumps: list[int] = []
    at6 = None
    for i in range(MAX_ACTIONS):
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        if lvl > START:
            break
        if lvl >= START:
            if at6 is None:
                at6 = i
            h = digest(obs)
            if opening is None:
                opening = h
            elif h == opening:
                recurrences.append(len(order))
            if h in seen:
                back_jumps.append(len(order) - seen[h])
            else:
                seen[h] = len(order)
            order.append(h)
        if agent.is_done([], obs):
            break
        act = agent.choose_action([], obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)

    print(json.dumps({
        "seed": seed, "at6": at6, "frames": len(order), "distinct": len(seen),
        "opening_recurrences": len(recurrences),
        "opening_recurred_at": recurrences[:12],
        "repeat_frames": len(back_jumps),
        "largest_backward_jump": max(back_jumps) if back_jumps else 0,
        "final_level": int(getattr(obs, "levels_completed", 0) or 0),
    }), flush=True)


if __name__ == "__main__":
    main()
