"""WHY does `crag._stitch` return "lost" on bp35's level 6? Separate the three causes.

Why this probe exists
---------------------
`scripts/_bp35_see.py` localised bp35's depth loss to one branch, on a run reproducing the banked
0.24556 / [18, 87, 45, 23, 46] exactly:

```
level  turns  steps  quits  stitch outcomes   world  rows  vocab
1-5      216    216      0  grow 214, home 2  260..370  10  4..14      <- the CONTRAST, all clear
6         14      6      8  grow 6, LOST 8        100    9    15      <- 8 of 14 turns refused
```

Every quit on level 6 is `"window does not belong to this board"`, which is `_stitch` returning
`lost`. `crag` then gets 14 turns and never bids again — `_idle` reaches 8 against its own
`_GIVE_UP` of 16 and `_mute` stays 0, so it never retires ITSELF — and `GraphSearchTool` spends 382
actions on the level and clears nothing.

⛔ "THE STITCH FAILS" IS NOT AN ATTRIBUTION. `_stitch` returns `lost` from exactly three places and
they demand different repairs:

  C1  every candidate shift was refused by `_admissible` — the PHYSICS gate. The body moved in a
      way `_allow` says is impossible, which is what a platform crumbling under it would look like.
  C2  every candidate had `total < _ALIGN_MIN` (16) — too few comparable cells to judge at all.
  C3  the best agreement was below `_ALIGN_FIT` (0.82) — the terrain genuinely DISAGREES, which is
      what four shrinking sprites read as four glyph kinds would do.

This re-runs the scan read-only after a `lost` and reports which. On `lost`, `_stitch` mutates
nothing before returning, so replaying its loop is safe.

⛔ AND IT CARRIES THE CONTRAST. Levels 1-5 produce ZERO `lost` in 216 turns. Whatever is blamed for
level 6 must not be equally true of them, so every counter is reported per level.

Both controls
-------------
POSITIVE — the run must reproduce banked bp35 (0.24556, [18, 87, 45, 23, 46]) and must record 8
`lost` calls on level 6. An instrument that sees no refusal has measured nothing.
NEGATIVE — levels 1-5 must record zero `lost`.

    bash scripts/pfan.sh bp35lost scripts/_bp35_lost.py 1 "" 1
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

    from admorphiq.tools import crag as cg

    ctx = {"lvl": 0, "act": 0}
    lost: list[dict] = []
    per_level: Counter = Counter()

    orig_stitch = cg.CragTool._stitch

    def stitch(self, readings, allow):  # noqa: ANN001, ANN202
        out = orig_stitch(self, readings, allow)
        if not (isinstance(out, tuple) and out[0] == "lost"):
            return out
        per_level[ctx["lvl"]] += 1
        # -- replay the scan, read-only, counting WHY each candidate was dropped -------------
        n_admiss = n_thin = n_scored = 0
        best_score = -1.0
        best_total = 0
        worst_cells: list = []
        lo = min(r for r, _ in self._world)
        hi = max(r for r, _ in self._world)
        for _idx, (_oy, _ox, board, _inks, body) in enumerate(readings):
            for shift in range(lo - self._rows, hi + self._rows + 1):
                if not self._admissible(body[0] + shift, allow):
                    n_admiss += 1
                    continue
                agree = total = 0
                bad: list = []
                for (r, c), sg in board.items():
                    if (r, c) == body:
                        continue
                    was = self._world.get((r + shift, c))
                    if was is None or was in self._volatile or sg in self._volatile:
                        continue
                    total += 1
                    if was == sg:
                        agree += 1
                    else:
                        bad.append([r + shift, c, was, sg])
                if total < cg._ALIGN_MIN:
                    n_thin += 1
                    continue
                n_scored += 1
                score = agree / total
                if score > best_score:
                    best_score, best_total, worst_cells = score, total, bad
        # ⛔ Summarise the BEST candidate's disagreements, not the last loop iteration's. The two
        # are different lists and reading the wrong one describes a shift that was never chosen.
        sgs = Counter(str(b[3]) for b in worst_cells)
        olds = Counter(str(b[2]) for b in worst_cells)
        lost.append({
            "n_disagree": len(bad),
            "distinct_new_sigs": len(sgs),
            "top_new_sig": sgs.most_common(3),
            "top_old_sig": olds.most_common(3),
            "lvl": ctx["lvl"], "act": ctx["act"],
            "allow": allow,
            "n_readings": len(readings),
            "world": len(self._world),
            "rows": self._rows,
            "refused_by_physics": n_admiss,
            "refused_too_thin": n_thin,
            "scored": n_scored,
            "best_score": round(best_score, 3),
            "best_total": best_total,
            "ALIGN_FIT": cg._ALIGN_FIT,
            "ALIGN_MIN": cg._ALIGN_MIN,
            "cause": ("C1_physics" if n_scored == 0 and n_admiss and not n_thin else
                      "C2_too_thin" if n_scored == 0 and n_thin else
                      "C3_terrain_disagrees" if n_scored else "C0_no_candidate"),
            "disagreeing_cells": [[b[0], b[1], str(b[2]), str(b[3])] for b in worst_cells[:6]],
            "volatile": len(self._volatile),
        })
        return out

    cg.CragTool._stitch = stitch

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
            if "bp35" in f"{e.game_id} {e.title or ''}".lower()][0]
    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=BUDGET)

    banked = json.loads((_ROOT / "scripts" / "rounds" / "R101SHIPPED"
                         / "games" / "bp35.json").read_text())
    got = round(float(res.get("game_score", 0.0)), 6)
    print(json.dumps({
        "score": got,
        "banked": round(float(banked["total_score"]), 6),
        "BANKED_MISMATCH": abs(got - float(banked["total_score"])) > 1e-6,
        "per_level": [p.get("agent_actions") for p in res.get("per_level", [])],
        "lost_per_level": dict(per_level),
        "causes": dict(Counter(r["cause"] for r in lost)),
        "lost": lost,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
