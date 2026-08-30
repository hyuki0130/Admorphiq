"""Read a `rendergate.sh` round: per arm, per game, score AND per-level action counts.

⛔ IT REFUSES RATHER THAN REPORTING ABSENCE. Three states are NOT a pass and are printed as
NO VERDICT: the identity control arm missing or short, a mutation that turned out INERT on
a game (it changed no cell, so an identical score says nothing), and a mutation ruled
INVALID on a game (a translation that would have destroyed board content — a broken
mutation and a brittle tool produce the same lower number, and only the accounting can
tell them apart).

⭐ IT COMPARES ACTION COUNTS, NOT ONLY THE SCORE. Rule 7ab's sharp form: a game score can
hide one level that got slower and another that got faster. Two runs that agree per level,
action for action, are playing the same moves.

    uv run python scripts/rendergate_compare.py scripts/rounds/R101RENDERR1 [reference-dir]

The optional reference is a round dir measured at an OLDER commit (e.g.
`scripts/rounds/R101SHIPPED`). It is reported as CODE DRIFT and never mixed into the
mutation verdict — every mutation arm is read against the identity arm from this same run.
"""

from __future__ import annotations

import glob
import json
import os
import sys
from typing import Any


def _arm(directory: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in glob.glob(os.path.join(directory, "games", "*.json")):
        game = os.path.basename(path)[:-5]
        try:
            with open(path) as handle:
                blob = json.load(handle)
        except Exception:  # noqa: BLE001
            continue
        g = (blob.get("games") or [{}])[0]
        rows[game] = {
            "score": float(blob.get("total_score") or 0.0),
            "levels": g.get("levels_completed"),
            "actions": [lv.get("agent_actions") for lv in g.get("per_level", [])],
            # Both instruments write their accounting under their own key and share
            # this reader: `rendergate_run.py` relabels the OBSERVATION,
            # `zordergate_run.py` re-paints the FRAME. The verdict vocabulary
            # ('applied' / 'inert' / 'invalid' / 'control', plus z-order's 'partial')
            # is identical, so one comparator serves both.
            "mutation": g.get("render_mutation") or g.get("zorder_mutation") or {},
        }
    return rows


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    root = sys.argv[1]
    reference = sys.argv[2] if len(sys.argv) > 2 else None
    arms = sorted(d for d in os.listdir(root)
                  if os.path.isdir(os.path.join(root, d, "games")))
    if "identity" not in arms:
        print("⛔ NO VERDICT: no identity control arm in this round. Every mutation arm is "
              "read against it; without it a code difference and a render dependence are "
              "the same number.")
        return 2
    control = _arm(os.path.join(root, "identity"))
    if not control:
        print("⛔ NO VERDICT: the identity arm produced no results.")
        return 2
    print(f"control: identity, {len(control)} games, "
          f"mean {sum(r['score'] for r in control.values()) / len(control):.4f}")

    if reference:
        ref = _arm(reference)
        drift = [g for g in sorted(set(ref) & set(control))
                 if abs(ref[g]["score"] - control[g]["score"]) > 1e-9]
        print(f"\n=== CODE DRIFT vs {reference} (informational, NOT a mutation result)")
        if drift:
            for g in drift:
                print(f"  {g:6s} {ref[g]['score']:.4f} -> {control[g]['score']:.4f}")
        else:
            print(f"  none — the control reproduces the reference on all "
                  f"{len(set(ref) & set(control))} shared games")

    status = 0
    for arm in arms:
        if arm == "identity":
            continue
        rows = _arm(os.path.join(root, arm))
        print(f"\n=== ARM {arm}")
        missing = sorted(g for g in control if g not in rows)
        if missing:
            print(f"⛔ NO VERDICT for {len(missing)} game(s) with no result: "
                  f"{', '.join(missing)}")
            status = 1
        judged, moved, refused = [], [], []
        for game in sorted(set(control) & set(rows)):
            a, b = control[game], rows[game]
            verdict = b["mutation"].get("verdict", "missing")
            if verdict != "applied":
                refused.append((game, verdict,
                                (b["mutation"].get("violations") or [""])[0][:70]))
                continue
            judged.append(game)
            same_score = abs(a["score"] - b["score"]) < 1e-9
            same_moves = a["actions"] == b["actions"]
            if not (same_score and same_moves):
                moved.append(game)
                print(f"  {game:6s} {a['score']:.4f} -> {b['score']:.4f}  "
                      f"levels {a['levels']}->{b['levels']}")
                print(f"         control {a['actions']}")
                print(f"         mutated {b['actions']}")
        for game, verdict, why in refused:
            print(f"  {game:6s} ⛔ NO VERDICT — mutation {verdict}"
                  f"{': ' + why if why else ''}")
        if judged:
            cm = sum(control[g]["score"] for g in judged) / len(judged)
            am = sum(rows[g]["score"] for g in judged) / len(judged)
            ident = len(judged) - len(moved)
            print(f"  JUDGED {len(judged)} game(s): {ident} identical action-for-action, "
                  f"{len(moved)} moved. mean control {cm:.4f} -> mutated {am:.4f}"
                  f"{'  ratio ' + format(am / cm, '.4f') if cm else ''}")
        else:
            print("  ⛔ NO VERDICT: not one game reached the 'applied' state in this arm.")
            status = 1
        if refused:
            print(f"  ⛔ {len(refused)} game(s) excluded — an inert or invalid mutation "
                  "scoring identically is not evidence of anything.")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
