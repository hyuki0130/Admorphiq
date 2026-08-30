"""What does the tool COMMIT on s5i5's level 7 opening frame — and is it right?

Why this probe exists
---------------------
s5i5 scores **0.5833**, reaches six levels and clears **all six at 1.00**. Level 7 is the entire
gap, worth +0.0167 of the mean.

⭐ AND THE FIRST THING TO FIX IS WHICH TOOL IS EVEN INVOLVED. The brief named `telescope`. The
banked census (`scripts/rounds/R101DEADRECKON/when_arm.jsonl`) says otherwise:

```
telescope.py:1183   lvlmask 31  = levels_completed 0,1,2,3,4   the first FIVE boards
swivel.py:734       lvlmask 96  = levels_completed 5 and 6
swivel.py:1071      lvlmask 64  = levels_completed 6 only
```

`levels_completed == 6` IS the seventh board — the wall. So **`swivel` owns the level-7 opening
frame**, and it also owns level 6, which CLEARS in 31 actions. ⭐ That is a WITHIN-TOOL contrast:
the same `_begin`, the same commitment shape, one board that works and one that does not — far
stronger than comparing two different tools (rule 7b, and the four s5i5 readings that died for
want of exactly this).

What it records
---------------
At every `swivel._begin` and `telescope._begin`, per level: how many bars / places / freight /
fixed the board reading offers, how many rider markers are DRAWN, the `pinned` subset, whether the
fallback to "every bar is a candidate" fired, and what the `_Model` ends up holding. Plus which
guard returned False when `_begin` refuses, whether the tool goes `_dead`, and which tool the
harness gives each action to.

⛔ NO SOURCE EDITS — everything is a runtime wrapper. `telescope` carries the corpus's only known
transfer defect and is not to be perturbed by an instrument.

Both controls
-------------
POSITIVE — the run must reproduce banked s5i5 exactly: 0.583333, per-level
[13, 30, 47, 39, 32, 31]. And level 6 (index 5), which CLEARS, must show `_begin` succeeding.
NEGATIVE — whatever is true of the level-7 commitment must NOT be equally true of the six that
clear; every field is reported per level so that can be checked rather than asserted.

    bash scripts/pfan.sh s5i5l7 scripts/_s5i5_l7.py 1 "" 1
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts"))

BUDGET = 4000


def main() -> None:
    import score_efficiency as se
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness import registry
    from admorphiq.tools import swivel as sw
    from admorphiq.tools import telescope as te

    ctx = {"lvl": 0, "act": 0}
    begins: list[dict] = []
    picks: Counter = Counter()
    per_pick: dict[int, Counter] = {}

    # -- swivel's commitment ------------------------------------------------------------
    orig_sw_begin = sw.SwivelArmTool._begin

    def sw_begin(self, g):  # noqa: ANN001, ANN202
        rec = {"tool": "swivel", "lvl": ctx["lvl"], "act": ctx["act"]}
        wid = sw.read_widgets(g)
        rec["widgets"] = len(wid)
        marker = sw.marker_colour(g, sw._widget_colours(g, wid)) if wid else None
        rec["marker"] = None if marker is None else int(marker)
        reading = sw.read_board(g, wid, marker) if (wid and marker is not None) else None
        if reading is not None:
            rec["bars"] = len(reading.bars)
            rec["places"] = len(reading.places)
            rec["freight"] = len(reading.freight)
            rec["fixed"] = len(reading.fixed)
            rec["colours"] = len(getattr(reading, "colours", ()) or ())
            marks = sw.read_markers(g, marker)
            rec["drawn_movers"] = 0 if marks is None else len(marks.movers)
            rec["drawn_places"] = 0 if marks is None else len(marks.places)
        ok = orig_sw_begin(self, g)
        rec["ok"] = bool(ok)
        if ok and self._model is not None:
            rec["riders"] = len(self._model.riders)
            rec["model_places"] = len(self._model.places)
            rec["fellback"] = rec.get("bars") == len(self._model.riders) \
                and rec.get("bars", 0) > rec.get("drawn_movers", 0)
            rec["controls"] = [k for k, _ in self._controls]
        begins.append(rec)
        return ok

    sw.SwivelArmTool._begin = sw_begin

    # -- telescope's commitment, for the levels it owns ----------------------------------
    orig_te_begin = te.TelescopeArmTool._begin

    def te_begin(self, g):  # noqa: ANN001, ANN202
        rec = {"tool": "telescope", "lvl": ctx["lvl"], "act": ctx["act"]}
        ok = orig_te_begin(self, g)
        rec["ok"] = bool(ok)
        if ok and self._model is not None:
            rec["riders"] = len(self._model.riders)
            rec["model_places"] = len(self._model.places)
            rec["pieces"] = len(self._pieces)
        begins.append(rec)
        return ok

    te.TelescopeArmTool._begin = te_begin

    # -- who gets each action -------------------------------------------------------------
    def wrap(cls: type) -> None:
        if cls.__dict__.get("_l7_wrapped"):
            return
        op, nm = cls.propose, cls.__name__

        def p(self, frames, obs):  # noqa: ANN001, ANN202
            picks[nm] += 1
            per_pick.setdefault(ctx["lvl"], Counter())[nm] += 1
            return op(self, frames, obs)

        cls.propose, cls._l7_wrapped = p, True

    for t in registry.default_tools():
        wrap(type(t))

    orig_make = se._make_agent

    def make(*a, **k):  # noqa: ANN002, ANN003
        adapter = orig_make(*a, **k)
        inner = adapter.choose_action

        def choose(frames, obs):  # noqa: ANN001
            lvl = int(getattr(obs, "levels_completed", 0) or 0)
            if lvl != ctx["lvl"]:
                ctx["lvl"], ctx["act"] = lvl, 0
            out = inner(frames, obs)
            ctx["act"] += 1
            return out

        adapter.choose_action = choose
        return adapter

    se._make_agent = make

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = [e for e in arcade.get_environments()
            if "s5i5" in f"{e.game_id} {e.title or ''}".lower()][0]
    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=BUDGET)

    banked = json.loads((_ROOT / "scripts" / "rounds" / "R101SHIPPED"
                         / "games" / "s5i5.json").read_text())
    got = round(float(res.get("game_score", 0.0)), 6)
    print(json.dumps({
        "score": got,
        "banked": round(float(banked["total_score"]), 6),
        "BANKED_MISMATCH": abs(got - float(banked["total_score"])) > 1e-6,
        "per_level": [p.get("agent_actions") for p in res.get("per_level", [])],
        "levels": res.get("levels_completed"),
        "win_levels": res.get("win_levels"),
        "picks": dict(picks),
        "picks_per_level": {str(k): dict(v) for k, v in sorted(per_pick.items())},
        "begins": begins,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
