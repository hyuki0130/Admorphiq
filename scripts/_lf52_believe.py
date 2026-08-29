"""Why does pegjump take a capture that ends the level? Its MODEL says another one is reachable.

⛔ THE MEASUREMENT THIS FOLLOWS. `scripts/_lf52_fate.py` proved with an uncapped search of the
engine's own state that lf52 level 6 becomes unwinnable at level-6 action 124, on a capture made by
`pegjump`, and that at that position the losing capture is the ONLY capture on offer while all four
other legal moves keep a winning line alive. `scripts/_lf52_guard.py` then ported railpeg's
survivability rule into pegjump and measured `refusals: 0` with the capture still taken and the
score unchanged — the guard is REACHED (it is `plan_moves`, tier `plan`, that produces the move) and
it does not fire, because `capture_reachable` answers TRUE.

So the guard is not wrong; the BOARD IT RUNS ON is. This instrument says by how much, by putting the
tool's model beside the engine's state at the same action. Cells cannot be compared directly — the
tool has its own origin — so both sets are normalised to their own minimum corner, which is
translation-invariant and enough to show a piece that is missing or invented.

⛔ `detect` is never called off-schedule (rule 7ah): `PegJumpTool._ensure_plan` is wrapped, so the
model is read exactly where the tool itself reads it.

Expected feedback:
  `npieces_model` < `npieces_engine`   -> the model is short of pieces; every reachability answer it
              gives is about a smaller board, and a guard cannot be more right than its map.
  normalised sets equal, guard still 0 -> the model is right and the reachability rule is wrong, a
              different repair entirely.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

BANKED = [8, 52, 60, 64, 139]

_F = importlib.util.spec_from_file_location(
    "lf52_fate", Path(__file__).resolve().parent / "_lf52_fate.py")
FATE = importlib.util.module_from_spec(_F)
_F.loader.exec_module(FATE)


def _norm(cells):
    cells = sorted(tuple(c) for c in cells)
    if not cells:
        return []
    my = min(c[0] for c in cells)
    mx = min(c[1] for c in cells)
    return sorted([c[0] - my, c[1] - mx] for c in cells)


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.tools import pegjump as pj

    _spec = importlib.util.spec_from_file_location(
        "score_eff", Path(__file__).resolve().parent / "score_efficiency.py")
    se = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(se)

    view: dict = {"pieces": None, "carriers": None, "noncapture": None, "solved": None}
    raw_plan = pj.PegJumpTool._ensure_plan

    # ⛔ MEASURE THE CLAIM, DO NOT INFER IT (rule 7g). A model holding two pieces makes a jump that
    # leaves one, and `plan_moves` returns that with `solved=True` — a declared LEVEL WIN, not a
    # capture route. That is a different defect from "it picked the wrong capture", so the returned
    # flag is recorded rather than deduced from the piece count.
    raw_moves = pj.plan_moves

    def wrapped_moves(model, noncapture, node_cap=pj._NODE_CAP):
        res = raw_moves(model, noncapture, node_cap)
        if res is not None and res[0]:
            view["solved"] = bool(res[1])
        return res

    pj.plan_moves = pj.PegJumpTool._ensure_plan.__globals__["plan_moves"] = wrapped_moves

    def wrapped(self, m):
        score = raw_plan(self, m)
        view["pieces"] = sorted(list(c) for c in m.pieces)
        view["carriers"] = sorted(list(c) for c in m.carriers)
        view["noncapture"] = sorted(self._noncapture)
        return score

    pj.PegJumpTool._ensure_plan = wrapped

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
                view["pieces"] = None
                act = inner.choose_action(frames, obs)
                if o is not None:
                    o["tool"] = None if loop is None else loop._current
                    o["mp"] = view["pieces"]
                    o["mc"] = view["carriers"]
                    o["nc"] = view["noncapture"]
                    o["solved"] = view["solved"]
                    rows.append(o)
                return act

        return Watch()

    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=4000, adapter_factory=factory)
    per = [p["agent_actions"] for p in res.get("per_level", [])]
    out: dict = {
        "probe": "lf52_believe",
        "per_level": per,
        "total_actions": int(res.get("total_actions", -1)),
        "game_score": res.get("game_score"),
        "control_neg_ok": per == BANKED and int(res.get("total_actions", -1)) == 823,
    }
    six = [r for r in rows if r["lvl"] == 6]
    caps = [i for i in range(1, len(six)) if len(six[i]["pads"]) < len(six[i - 1]["pads"])]
    out["captures_at"] = caps
    reads = [{"i": i, "tool": six[i]["tool"],
              "npieces_engine": len(six[i]["pads"]), "npieces_model": len(six[i]["mp"]),
              "engine_norm": _norm([c for c, _n in six[i]["pads"]]),
              "model_norm": _norm(six[i]["mp"]),
              "noncapture": six[i]["nc"],
              "carriers_model": len(six[i]["mc"]), "carts_engine": len(six[i]["carts"]),
              "plan_declared_solved": six[i]["solved"]}
             for i in range(len(six)) if six[i]["mp"] is not None]
    out["model_reads"] = len(reads)
    out["at_losing_move"] = next((r for r in reads if r["i"] == 123), None)
    out["last_read_before_124"] = next((r for r in reversed(reads) if r["i"] < 124), None)
    out["agreements"] = sum(1 for r in reads if r["engine_norm"] == r["model_norm"])
    print(json.dumps(out))


if __name__ == "__main__":
    main()
