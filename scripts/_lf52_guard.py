"""Does pegjump's survivability guard FIRE, and does refusing the losing capture buy anything?

⛔ WHAT THIS IS TESTING, and it is not the thing rule 7au says. `scripts/_lf52_fate.py` measured,
with the engine's state and an uncapped search of `scripts/_lf52_l6_model.py`, that lf52 level 6 is
still WINNABLE after railpeg's two captures and becomes UNWINNABLE at action 124 — the capture made
by `pegjump`, not by railpeg — and that at that position the losing capture is the ONLY capture on
offer while all four other legal moves keep a winning line alive. So the repair is not "disarm a
trap" and not "rank the eighth candidate": it is railpeg's already-written rule, ported to the tool
that lacks it — when nothing on offer survives, a capture is not the move.

⛔ AND IT PROVES THE BRANCH FIRES (rule 7g). A guard that is never reached and a guard that is
reached and changes nothing want opposite repairs. `plan_moves` is wrapped so that every refusal is
counted ALONGSIDE what the unguarded call would have returned, so `refusals` counts only the calls
where behaviour actually differs.

CONTROL. The unguarded number is banked and was re-reproduced twice today by `_lf52_fate.py`:
per-level [8, 52, 60, 64, 139], total 823, game_score 0.272727, level-6 captures at 14/16 (railpeg)
and 124 (pegjump), the position unwinnable from 124 and the level restarted at 267.

Expected feedback:
  `refusals` == 0                     -> the guard never fires; the diagnosis or the wiring is wrong.
  `refusals` > 0, `l6_lost_at` null   -> the guard works: the level is no longer thrown away. Whether
                                         the SCORE moves is a separate question this also answers.
  `game_score` > 0.272727             -> ship it, and gate on the full 25.
  `game_score` == 0.272727            -> the guard is correct and inert; a measured negative, and the
                                         remaining gap is planning capability, not this move.
"""
from __future__ import annotations

import importlib.util
import json
import sys
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

    counts = {"calls": 0, "refusals": 0, "plan": 0, "explore": 0, "probe": 0}
    src = {"last": None, "age": 0}
    raw = pj.plan_moves
    raw_explore = pj.explore_moves
    raw_probe = pj.probe_moves

    def wrapped(model, noncapture, node_cap=pj._NODE_CAP, lookahead=pj._LOOKAHEAD,
                refuse_fatal=False):
        res = raw(model, noncapture, node_cap, lookahead, refuse_fatal)
        if refuse_fatal:
            counts["calls"] += 1
            if res is None:
                bare = raw(model, noncapture, node_cap, lookahead, False)
                if bare is not None and bare[0]:
                    counts["refusals"] += 1
        if res is not None and res[0]:
            counts["plan"] += 1
            src["last"], src["age"] = "plan", 0
        return res

    def wrapped_explore(*a, **k):
        res = raw_explore(*a, **k)
        if res:
            counts["explore"] += 1
            src["last"], src["age"] = "explore", 0
        return res

    def wrapped_probe(*a, **k):
        res = raw_probe(*a, **k)
        if res:
            counts["probe"] += 1
            src["last"], src["age"] = "probe", 0
        return res

    # ⛔ WHICH TIER PRODUCED THE MOVE. A guard placed in `plan_moves` cannot stop a capture that
    # `explore_moves` proposed — an exploring jump captures whatever it happens to pass over — and
    # the two want opposite repairs. Measured rather than assumed (rule 7g).
    g = pj.PegJumpTool._ensure_plan.__globals__
    pj.plan_moves = g["plan_moves"] = wrapped
    pj.explore_moves = g["explore_moves"] = wrapped_explore
    pj.probe_moves = g["probe_moves"] = wrapped_probe

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
                act = inner.choose_action(frames, obs)
                if o is not None:
                    o["act"] = getattr(act, "name", str(act))
                    o["tool"] = None if loop is None else loop._current
                    o["src"] = src["last"]
                    o["src_age"] = src["age"]
                    src["age"] += 1
                    rows.append(o)
                return act

        return Watch()

    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=4000, adapter_factory=factory)

    per = [p["agent_actions"] for p in res.get("per_level", [])]
    out: dict = {
        "probe": "lf52_guard",
        "levels_completed": int(res.get("levels_completed", -1)),
        "per_level": per,
        "total_actions": int(res.get("total_actions", -1)),
        "game_score": res.get("game_score"),
        "levels_1_5_unchanged": per[:5] == BANKED,
        "guard_calls": counts["calls"],
        "refusals": counts["refusals"],
        "tier_fills": {k: counts[k] for k in ("plan", "explore", "probe")},
    }
    six = [r for r in rows if r["lvl"] == 6]
    out["l6_actions"] = len(six)
    if six:
        caps = [i for i in range(1, len(six)) if len(six[i]["pads"]) < len(six[i - 1]["pads"])]
        out["l6_captures"] = [{"i": i, "tool": six[i - 1]["tool"], "src": six[i - 1]["src"],
                               "src_age": six[i - 1]["src_age"]} for i in caps]
        out["l6_restarts_at"] = [i for i in range(1, len(six))
                                 if len(six[i]["pads"]) > len(six[i - 1]["pads"])]
        out["l6_zv_from"] = next((i for i, r in enumerate(six) if r["zv"]), None)
        w, c, _n = FATE.winnable(FATE._state_of(six[-1]))
        out["l6_end_winnable"] = w
        out["l6_end_capped"] = c
        out["l6_tools"] = sorted({r["tool"] for r in six if r["tool"]})
    print(json.dumps(out))


if __name__ == "__main__":
    main()
