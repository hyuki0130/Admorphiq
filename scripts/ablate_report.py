"""Read an `ablategate.sh` round: ownership census, or the ablation table against a control.

    uv run python scripts/ablate_report.py scripts/rounds/R101ABLATEOWN
    uv run python scripts/ablate_report.py scripts/rounds/R101ABLATEDROP1 \
        scripts/rounds/R101ABLATEOWN

⛔ IT REFUSES RATHER THAN AVERAGING OVER A HOLE. A game whose ablation arm dropped `none`,
or dropped a tool that never held the board in the control, contributes NOTHING to the
floor — those are printed as NO VERDICT. An "ablation" that removed a tool the game never
used scores identically for a reason that has nothing to do with the harness coping, and
that is the fail-toward-nothing shape this campaign has paid for eight times.
"""

from __future__ import annotations

import glob
import json
import os
import sys
from typing import Any


def load(directory: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in glob.glob(os.path.join(directory, "games", "*.json")):
        try:
            with open(path) as handle:
                blob = json.load(handle)
        except Exception:  # noqa: BLE001
            continue
        g = (blob.get("games") or [{}])[0]
        rows[os.path.basename(path)[:-5]] = {
            "score": float(blob.get("total_score") or 0.0),
            "dropped": blob.get("dropped"),
            "registry_size": blob.get("registry_size"),
            "levels": g.get("levels_completed"),
            "win_levels": g.get("win_levels"),
            "actions": g.get("total_actions"),
            "own": g.get("ownership", {}),
        }
    return rows


def census(rows: dict[str, dict[str, Any]]) -> int:
    print(f"{'game':6s} {'score':>7s} {'lv':>5s} {'owner':<16s} {'share':>6s} "
          f"{'tools':>5s} {'tenures':>7s}  runner-up")
    single = 0
    for game in sorted(rows):
        r = rows[game]
        own = r["own"]
        by = own.get("by_tool", {})
        rest = [f"{k} {v}" for k, v in list(by.items())[1:3]]
        share = own.get("owner_share") or 0.0
        if share >= 0.99:
            single += 1
        print(f"{game:6s} {r['score']:7.4f} {str(r['levels']) + '/' + str(r['win_levels']):>5s} "
              f"{str(own.get('owner')):<16s} {share:6.2f} {own.get('n_tools_used', 0):5d} "
              f"{own.get('tenures', 0):7d}  {', '.join(rest)}")
    print(f"\n{single} of {len(rows)} games are played >=99% by ONE tool.")
    print(f"MEAN {sum(r['score'] for r in rows.values()) / len(rows):.4f} over {len(rows)}")
    return single


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    rows = load(sys.argv[1])
    if not rows:
        print(f"⛔ NO VERDICT: {sys.argv[1]} holds no results.")
        return 2
    if len(sys.argv) < 3:
        census(rows)
        return 0

    control = load(sys.argv[2])
    if not control:
        print(f"⛔ NO VERDICT: control {sys.argv[2]} holds no results.")
        return 2

    print(f"{'game':6s} {'ctrl':>7s} {'abl':>7s} {'delta':>8s}  {'lv ctrl':>7s} {'lv abl':>6s}  "
          f"dropped -> who inherits")
    judged: list[tuple[str, float, float]] = []
    refused: list[tuple[str, str]] = []
    for game in sorted(set(control) & set(rows)):
        c, a = control[game], rows[game]
        dropped = a["dropped"]
        held = (c["own"].get("by_tool") or {}).get(dropped, 0)
        if dropped in (None, "none"):
            refused.append((game, "the arm dropped NOTHING"))
            continue
        if held == 0:
            refused.append((game, f"'{dropped}' never held the board in the control"))
            continue
        by = a["own"].get("by_tool", {})
        if dropped in by:
            refused.append((game, f"'{dropped}' still played {by[dropped]} actions — not removed"))
            continue
        judged.append((game, c["score"], a["score"]))
        heir = ", ".join(f"{k} {v}" for k, v in list(by.items())[:3])
        print(f"{game:6s} {c['score']:7.4f} {a['score']:7.4f} {a['score'] - c['score']:+8.4f}  "
              f"{str(c['levels']) + '/' + str(c['win_levels']):>7s} "
              f"{str(a['levels']):>6s}  {dropped} -> {heir}")
    for game, why in refused:
        print(f"{game:6s} ⛔ NO VERDICT — {why}")

    if not judged:
        print("\n⛔ NO VERDICT: not one game had its actual owner removed.")
        return 1
    deltas = sorted(a - c for _, c, a in judged)
    print(f"\nJUDGED {len(judged)} game(s).  mean control "
          f"{sum(c for _, c, _ in judged) / len(judged):.4f} -> ablated "
          f"{sum(a for _, _, a in judged) / len(judged):.4f}")
    print(f"per-game delta: min {deltas[0]:+.4f}  median {deltas[len(deltas) // 2]:+.4f}  "
          f"max {deltas[-1]:+.4f}")
    kept = [g for g, c, a in judged if abs(a - c) < 1e-9]
    if kept:
        print(f"⚠️  UNCHANGED despite losing their owner ({len(kept)}): {', '.join(kept)} — "
              f"a game that does not feel the loss was not really owned by that tool.")
    if refused:
        print(f"⛔ {len(refused)} game(s) excluded from the floor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
