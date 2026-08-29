"""Press-by-press trace of lp85 LEVEL 4 — why sixteen single presses buy no plan.

Level 4 draws sixteen buttons over four controls, spends 33 actions against a human 16, and the
split is fixed across every probing rule tried so far: 16 first presses, 9 confirming presses, 4
replans, 3 plan presses, 1 nudge. The first presses are net-IDENTITY (four copies of each of the
four controls, and the four controls are two rings times two directions), so they buy only the
model. This asks what the model is worth after each one: how many permutations are recovered, and
whether a press sequence to the markers exists yet.

First argument is the variant (see scripts/_lp85_split.py) so the trace can be taken under any
probing rule; the trace itself is printed only while level 4 is being played.
"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, "src")


def main() -> None:
    variant = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 4000

    import importlib.util
    from pathlib import Path

    from admorphiq.tools import cyclepress as cp
    from admorphiq.tools.base import frame_2d, has_frame
    from admorphiq.tools.track import markers_on, read_board

    spec = importlib.util.spec_from_file_location(
        "lp85split", Path(__file__).resolve().parent / "_lp85_split.py")
    split = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(split)
    split.install(split.FEATURES.get(variant, set()))
    base_propose = cp.CyclePressTool.propose
    trace: list[dict] = []
    live = {"on": False}

    def propose(self, frames, obs):
        out = base_propose(self, frames, obs)
        if not live["on"] or not has_frame(obs):
            return out
        g = frame_2d(obs)
        board = read_board(g)
        if board is None:
            return out
        tiles, side, _ = board
        marks = markers_on(g, tiles, side)
        controls = cp.press_points(g, tiles, side)
        plan = cp.plan_presses(tiles, marks, self._perm) if self._perm else None
        trace.append({
            "i": len(trace), "pending": list(self._pending) if self._pending else None,
            "controls": len(controls), "pressed": len(self._pairs), "inert": len(self._inert),
            "perms": len(self._perm), "distinct": len({tuple(sorted(p.items()))
                                                       for p in self._perm.values()}),
            "confirmed": sum(1 for c in self._streak if self._streak[c] >= cp._CONFIRM_STREAK),
            "plan": None if plan is None else len(plan),
            "marks": len(marks), "slots": len(tiles),
            "left": self._budget.remaining(self._last_frame),
        })
        return out

    cp.CyclePressTool.propose = propose

    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("lp85"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]
    levels = 0
    for step in range(cap):
        live["on"] = levels == 3
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now > levels:
            print(f"  v{variant} level {levels + 1} cleared at step {step + 1}", flush=True)
            if levels == 3:
                break
            levels = now
        elif now < levels:
            print(f"  v{variant} COLLAPSE {levels} -> {now}", flush=True)
            levels = now
        if step % 100 == 0:
            print(f"  v{variant} .. step {step} lvl {levels}", flush=True)
    for row in trace:
        print("   ", json.dumps(row), flush=True)
    print(json.dumps({"variant": variant, "l4_presses": len(trace),
                      "first_plan_at": next((r["i"] for r in trace if r["plan"]), None)}))


if __name__ == "__main__":
    main()
