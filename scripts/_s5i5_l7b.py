"""s5i5 level 7: the commitment is right, so what stops it 37 actions later?

Why this probe exists
---------------------
`scripts/_s5i5_l7.py` settled the perception question on a run reproducing banked s5i5 exactly
(0.583333, [13, 30, 47, 39, 32, 31]):

```
lvl 5 (CLEARS, 31a)  swivel._begin ok   6 widgets  3 bars  1 place   drawn 1  riders 1  fellback FALSE
lvl 6 (the wall)     swivel._begin ok   9 widgets  6 bars  2 places  drawn 2  riders 2  fellback FALSE
```

⭐ The level-7 opening-frame commitment is CORRECT: both riders are PINNED by drawn markers, the
candidate set is 2 of 6 bars, and the "every bar is a candidate" fallback never fires. So this is
not rule 7cd's visibility defect and no amount of better perception at action 0 helps.

⛔ WHAT IS UNVERIFIED IS THE PARK. The recorded closure is *"the win opens by moving a rider that is
already home, which `swivel`'s decomposition can never propose"*. That is a claim about the
DECOMPOSITION, and a park naming a missing capability is exactly the shape that has twice turned
out to be a measurement artefact here. It has two halves and both are checkable on a run:

  A  is a rider ALREADY on a place at the opening frame? — compare `rider_at(cfg, i)` for each
     committed rider against `reading.places`, on level 6 AND on level 5 which clears.
  B  what actually ends swivel's turn? It proposes 37 actions of level 6's budget and then
     `LinkageReachTool` takes 463. Either `_settle` failed and set `_dead`, or `_next` ran out of
     plan and returned nothing. Those are different repairs.

Both controls
-------------
POSITIVE — the run must reproduce banked s5i5, and level 5 (which CLEARS under the same tool) is
the within-tool control: whatever is blamed for level 7 must not be equally true there.
NEGATIVE — if `dead` never becomes True and `_next` simply empties, then "the decomposition cannot
propose it" is a statement about the PLAN, not about a crash, and must be said that way.

    bash scripts/pfan.sh s5i5l7b scripts/_s5i5_l7b.py 1 "" 1
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

    from admorphiq.tools import swivel as sw

    ctx = {"lvl": 0, "act": 0}
    home: list[dict] = []
    turns: list[dict] = []
    settles: Counter = Counter()

    orig_begin = sw.SwivelArmTool._begin

    def begin(self, g):  # noqa: ANN001, ANN202
        ok = orig_begin(self, g)
        if ok and self._model is not None and self._cfg is not None:
            places = [tuple(p) if isinstance(p, (list, tuple)) else p
                      for p in self._model.places]
            at = {}
            for i in self._model.riders:
                try:
                    at[i] = sw.rider_at(self._cfg, i)
                except Exception as exc:  # noqa: BLE001
                    at[i] = f"ERR {type(exc).__name__}: {exc}"
            already = [i for i, v in at.items() if v in set(places)]
            home.append({
                "lvl": ctx["lvl"],
                "riders": list(self._model.riders),
                "rider_at": {str(k): str(v) for k, v in at.items()},
                "places": [str(p) for p in places],
                "ALREADY_HOME": already,
                "n_already_home": len(already),
            })
        return ok

    sw.SwivelArmTool._begin = begin

    orig_settle = sw.SwivelArmTool._settle

    def settle(self, g, refused):  # noqa: ANN001, ANN202
        out = orig_settle(self, g, refused)
        settles[f"lvl{ctx['lvl']}_{'ok' if out else 'FAIL'}"] += 1
        return out

    sw.SwivelArmTool._settle = settle

    orig_propose = sw.SwivelArmTool.propose

    def propose(self, frames, obs):  # noqa: ANN001, ANN202
        was_dead = bool(getattr(self, "_dead", False))
        steps = orig_propose(self, frames, obs)
        turns.append({
            "lvl": ctx["lvl"], "act": ctx["act"],
            "steps": len(steps),
            "dead": bool(getattr(self, "_dead", False)),
            "became_dead": (not was_dead) and bool(getattr(self, "_dead", False)),
            "plan": len(getattr(self, "_plan", ()) or ()),
            "pending": getattr(self, "_pending", None) is not None,
            "tries": list(getattr(self, "_tries", ()) or ()),
        })
        return steps

    sw.SwivelArmTool.propose = propose

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
    by: dict[int, dict] = {}
    for t in turns:
        d = by.setdefault(t["lvl"], {"turns": 0, "empty": 0, "became_dead_at": None,
                                     "dead_turns": 0, "plan_max": 0})
        d["turns"] += 1
        d["empty"] += 1 if not t["steps"] else 0
        d["dead_turns"] += 1 if t["dead"] else 0
        d["plan_max"] = max(d["plan_max"], t["plan"])
        if t["became_dead"] and d["became_dead_at"] is None:
            d["became_dead_at"] = t["act"]
    print(json.dumps({
        "score": got,
        "banked": round(float(banked["total_score"]), 6),
        "BANKED_MISMATCH": abs(got - float(banked["total_score"])) > 1e-6,
        "per_level": [p.get("agent_actions") for p in res.get("per_level", [])],
        "home": home,
        "settles": dict(settles),
        "by_level": {str(k): v for k, v in sorted(by.items())},
    }, sort_keys=True))


if __name__ == "__main__":
    main()
