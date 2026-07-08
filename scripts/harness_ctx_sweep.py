"""Sweep HARNESS_CTX to find the wiki-context size that maximises performance.

The runtime model has a bounded window; too little context and it can't pick
the right tool, too much and a weak model's attention degrades (and latency +
token cost rise). This runs the unified harness on the same games across a set
of context-char budgets and reports score + actions per budget, so the deploy
HARNESS_CTX is a MEASURED choice, not a guess.

Usage (on the Kaggle-matched VM):
  uv run python scripts/harness_ctx_sweep.py --games ar25,re86 \
      --budgets 2000,4000,8000,16000 --max-actions 400
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _run(games: str, ctx: int, max_actions: int, model: str) -> dict:
    out = f"/tmp/ctxsweep_{ctx}.json"
    env = {
        **os.environ,
        "HARNESS_CTX": str(ctx),
        "HARNESS_MODEL": model,
        "GF_GIVEUP": str(max_actions),
    }
    subprocess.run(
        [sys.executable, str(REPO / "scripts" / "score_efficiency.py"),
         "--agent", "unified", "--titles", games,
         "--max-actions", str(max_actions), "--out", out],
        env=env, capture_output=True, timeout=7200, check=False,
    )
    return json.load(open(out))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", required=True, help="comma-separated titles")
    ap.add_argument("--budgets", default="2000,4000,8000,16000")
    ap.add_argument("--max-actions", type=int, default=400)
    ap.add_argument("--model", default="gemma4:31b-it-q8_0")
    ap.add_argument("--out", default="/tmp/harness_ctx_sweep.json")
    a = ap.parse_args()

    budgets = [int(b) for b in a.budgets.split(",")]
    rows = []
    for ctx in budgets:
        print(f"=== HARNESS_CTX={ctx} ===", flush=True)
        res = _run(a.games, ctx, a.max_actions, a.model)
        total = res.get("total_score", 0.0)
        acts = sum(g.get("total_actions", 0) for g in res.get("games", []))
        lvls = sum(g.get("levels_completed", 0) for g in res.get("games", []))
        rows.append({"ctx": ctx, "total_score": total, "levels": lvls, "actions": acts})
        print(f"  total_score={total:.4f} levels={lvls} actions={acts}", flush=True)

    best = max(rows, key=lambda r: (r["total_score"], -r["actions"])) if rows else None
    json.dump({"sweep": rows, "best": best}, open(a.out, "w"), indent=2)
    print(f"\nBEST: {best}", flush=True)
    print(f"written: {a.out}", flush=True)


if __name__ == "__main__":
    main()
