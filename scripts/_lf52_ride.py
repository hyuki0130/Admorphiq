"""lf52 level 6 — does the board-then-ride tier actually EXECUTE, and does the camera move?

⛔ RULE 7g, BOTH WAYS. `scripts/_lf52_fate.py` says the new tier changed the outcome — the level is
never lost and never restarted, where before it died at level-6 action 124 (`pegjump`) and again at
317 (`graph`). `scripts/_lf52_pcen.py` says the CAMERA NEVER MOVES: `cam` is [-57, 5] at every read
and the frame never carries more than two discs across twenty readings. Those two facts are both
true and they cannot both be the whole story, so this probe watches the tier itself.

Recorded at every `pegjump` decision on level 6: which tier filled the plan, what the plan was, and
— for a plan the tier produced — how much of it the tool actually PLAYS before something tears it
down. The drive half needs an action id the tool has not calibrated, and asking for one CLEARS the
plan by design (`_pending_drive`), so "the tier proposed a ride" and "the tool rode" are different
claims and are counted separately.

CONTROLS (rule 7ai)
  NEGATIVE  per-level actions [8, 52, 60, 64, 139] and total 823 — this probe reads and never
            steers (rule 7aj.2).
  POSITIVE  `railhead_calls` > 0. A tier that is never asked has not been measured.

Expected feedback:
  proposals > 0 and `drives_issued` == 0 -> the ride is planned and never played; the calibration
            probe tears the plan down each time and the tier spins.
  `drives_issued` > 0 with the camera fixed -> the ride is played and the ENGINE refuses it, which
            is a different repair: the direction or the passenger is wrong.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

BANKED = [8, 52, 60, 64, 139]
BANKED_TOTAL = 823

_F = importlib.util.spec_from_file_location(
    "lf52_fate", Path(__file__).resolve().parent / "_lf52_fate.py")
FATE = importlib.util.module_from_spec(_F)
_F.loader.exec_module(FATE)


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.tools import pegjump as pj

    _spec = importlib.util.spec_from_file_location(
        "score_eff", Path(__file__).resolve().parent / "score_efficiency.py")
    se = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(se)

    tally: Counter = Counter()
    view: dict = {"rail": None, "plan": None}
    raw_rail = pj.railhead_moves
    raw_plan = pj.PegJumpTool._ensure_plan
    raw_propose = pj.PegJumpTool.propose

    def wrapped_rail(model, noncapture, cost_cap=16, node_cap=40_000):
        moves = raw_rail(model, noncapture, cost_cap, node_cap)
        tally["railhead_calls"] += 1
        if moves:
            tally["railhead_proposals"] += 1
            tally["railhead_len_%d" % len(moves)] += 1
            view["rail"] = [[m[0], list(m[1] or []), list(m[2])] for m in moves]
        else:
            tally["railhead_empty"] += 1
        return moves

    pj.railhead_moves = wrapped_rail
    pj.PegJumpTool._ensure_plan.__globals__["railhead_moves"] = wrapped_rail

    def wrapped_plan(self, m):
        before = list(self._plan)
        score = raw_plan(self, m)
        if not before and self._plan:
            view["plan"] = [[x[0], list(x[1] or []), list(x[2])] for x in self._plan]
            tally["plans_filled"] += 1
            tally["plan_has_drive"] += any(x[0] == "drive" for x in self._plan)
        return score

    pj.PegJumpTool._ensure_plan = wrapped_plan

    def wrapped_propose(self, frames, obs):
        steps = raw_propose(self, frames, obs)
        for aid, xy in steps:
            tally["step_click" if aid == 6 else "step_simple"] += 1
        if self._pending_drive is not None:
            tally["calibration_probes_pending"] += 1
        return steps

    pj.PegJumpTool.propose = wrapped_propose

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("lf52"))
    held: dict = {}
    real_make = arcade.make

    def make(gid, *a, **k):
        env = real_make(gid, *a, **k)
        held["env"] = env
        return env

    arcade.make = make
    rows: list[dict] = []
    real_factory = se._make_agent

    def factory():
        inner = real_factory("unified", game_id=info.game_id)

        class Watch:
            restart_on_game_over = getattr(inner, "restart_on_game_over", False)

            def is_done(self, frames, obs):
                return inner.is_done(frames, obs)

            def choose_action(self, frames, obs):
                o = FATE._oracle(held.get("env"))
                loop = FATE._loop_of(inner)
                view["rail"] = view["plan"] = None
                act = inner.choose_action(frames, obs)
                if o is not None:
                    o["tool"] = None if loop is None else loop._current
                    o["rail"] = view["rail"]
                    o["plan"] = view["plan"]
                    o["act"] = str(getattr(act, "id", act))
                    rows.append(o)
                return act

        return Watch()

    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=4000, adapter_factory=factory)
    per = [p["agent_actions"] for p in res.get("per_level", [])]
    six = [r for r in rows if r["lvl"] == 6]
    out: dict = {
        "probe": "lf52_ride",
        "per_level": per,
        "total_actions": int(res.get("total_actions", -1)),
        "game_score": res.get("game_score"),
        "control_neg_ok": per == BANKED and int(res.get("total_actions", -1)) == BANKED_TOTAL,
        "tally": dict(tally),
        "control_pos_ok": tally["railhead_calls"] > 0,
        "l6_actions": len(six),
        "pegjump_actions": sum(1 for r in six if r["tool"] == "pegjump"),
        "tools": dict(Counter(r["tool"] for r in six)),
        "cams": sorted({tuple(r["cam"]) for r in six}),
        "simple_actions_by_pegjump": dict(Counter(
            r["act"] for r in six if r["tool"] == "pegjump")),
        "rail_proposals": [{"i": i, "rail": six[i]["rail"], "plan": six[i]["plan"]}
                           for i in range(len(six)) if six[i]["rail"]][:12],
    }
    print(json.dumps(out))


if __name__ == "__main__":
    main()
