"""WHEN is lf52 level 6 lost? The engine's own legality predicate, asked about the RED piece.

⛔ Rule 7au names level-6 action 124 as the target: "make the third capture the eighth candidate".
Two measurements have already refuted the framing around it (`_lf52_cens.py`, `_lf52_who.py`):
`railpeg` REFUSES that capture at all 20 of its candidate turns and bids 0.0 from action 114, and
the jump is made by `pegjump` after the handover. This probe asks the remaining question, which is
the one that decides whether ANY ranking repair could have helped:

  the engine's fatal branch is (green lands on (16,2)) AND (red stands on (6,6)).
  WHEN DOES RED LAST HAVE A LEGAL MOVE? Past that action the second half of the conjunction is
  frozen, so every capture is fatal and there is no eighth candidate to prefer.

Per level-6 action, straight from the engine (`qikmikecdf`, its own legality predicate):
  red's cell, how many legal jumps RED has, how many legal jumps exist at all, and whether any
  legal move at all would vacate (6, 6).

CONTROLS (rule 7ai)
  NEGATIVE  per-level actions [8, 52, 60, 64, 139] / 823 total.
  POSITIVE  `red_mobile_actions` must be NON-EMPTY — red demonstrably moves (2,2)->(2,6)->(6,6)
            early in the level, so an instrument reporting red immobile everywhere has measured
            nothing. It must also be able to say NO: `red_last_mobile` < the level's last action.

Expected feedback:
  `red_last_mobile` far below 124 -> the trap is armed long before the capture and no ranking of
      capture candidates at 124 could have avoided it; the target named by rule 7au is unreachable.
  `red_last_mobile` >= 124 -> red was still movable at the decision and a tier that moved it would
      have been the repair.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]
BANKED = [8, 52, 60, 64, 139]
BANKED_TOTAL = 823
TRAP = (6, 6)


def _scene(env):
    g = getattr(env, "_game", None) or getattr(env, "game", None)
    return getattr(g, "ikhhdzfmarl", None) if g is not None else None


def _oracle(env) -> dict | None:
    sc = _scene(env)
    if sc is None:
        return None
    grid = getattr(sc, "hncnfaqaddg", None)
    if grid is None:
        return None
    try:
        pieces = grid.ndtvadsrqf("fozwvlovdui")
    except Exception:
        return None
    red_moves = 0
    all_moves = 0
    vacates = 0
    red_cell = None
    for p in pieces:
        pos = p.chahdtpdoz
        is_red = "red" in p.name
        if is_red:
            red_cell = list(pos)
        for d in DIRS:
            try:
                ok = bool(sc.qikmikecdf(pos, d))
            except Exception:
                continue
            if not ok:
                continue
            all_moves += 1
            if is_red:
                red_moves += 1
            # the move that would empty the trap cell: the piece standing on it moving off
            if pos == TRAP:
                vacates += 1
    return {
        "lvl": int(getattr(sc, "whtqurkphir", -1)),
        "used": int(getattr(sc, "asqvqzpfdi", -1)),
        "red": red_cell,
        "red_moves": red_moves,
        "all_moves": all_moves,
        "vacates": vacates,
        "occupied": any(p.chahdtpdoz == TRAP for p in pieces),
        "zv": bool(getattr(sc, "zvcnglshzcx", False)),
        "p": len(pieces),
    }


def main() -> None:
    from arc_agi import Arcade, OperationMode

    _spec = importlib.util.spec_from_file_location(
        "score_eff", Path(__file__).resolve().parent / "score_efficiency.py")
    se = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(se)

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
                o = _oracle(held.get("env"))
                act = inner.choose_action(frames, obs)
                if o is not None:
                    o["act"] = getattr(act, "name", str(act))
                    rows.append(o)
                return act

        return Watch()

    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=4000, adapter_factory=factory)

    per = [p["agent_actions"] for p in res.get("per_level", [])]
    six = [r for r in rows if r["lvl"] == 6]
    # ⛔ the level restarts in place at action 267 (rule 7as); the ATTEMPT that dies is 0..266.
    first = [r for r in six[:267]]
    mobile = [i for i, r in enumerate(first) if r["red_moves"] > 0]
    vac = [i for i, r in enumerate(first) if r["vacates"] > 0]
    arrived = next((i for i, r in enumerate(first) if r["red"] == list(TRAP)), None)
    out = {
        "probe": "lf52_arm",
        "levels_completed": int(res.get("levels_completed", -1)),
        "per_level": per,
        "total_actions": int(res.get("total_actions", -1)),
        "control_neg_ok": per == BANKED and int(res.get("total_actions", -1)) == BANKED_TOTAL,
        "l6_actions": len(six),
        "attempt1_actions": len(first),
        "red_track": sorted({tuple(r["red"]) for r in first if r["red"]}),
        "red_arrived_at_trap": arrived,
        "red_mobile_actions": mobile,
        "red_last_mobile": mobile[-1] if mobile else None,
        "vacate_actions": vac,
        "vacate_last": vac[-1] if vac else None,
        "capture_at": [i for i in range(1, len(first)) if first[i]["p"] < first[i - 1]["p"]],
        "zv_from": next((i for i, r in enumerate(first) if r["zv"]), None),
        "all_moves_at_124": first[124]["all_moves"] if len(first) > 124 else None,
    }
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
