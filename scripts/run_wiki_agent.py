"""Phase 8 Step 3 driver: run the WikiAgent on every enabled game.

For each arcengine environment, the WikiAgent:
  1. Resets and probes ACTION1..N to build a DiscoveryReport
  2. Retrieves a fixed slice of `.wiki/` (core reasoning + selector + lessons)
  3. Asks the configured LLM to classify + pick a frame-only strategy
  4. Dispatches the recommended strategy (with fallbacks) through the ensemble
  5. Records a trace to `scripts/wiki_agent_results.json`

The LLM is picked by `--candidate` (default: primary from `configs/llm.yaml`).
This script does no network I/O — the LLM is expected to be served locally
via Ollama (dev) or bundled weights (Kaggle). No Claude/GPT calls.

Run:
    uv run python scripts/run_wiki_agent.py
    uv run python scripts/run_wiki_agent.py --candidate qwen_3_14b_q4
    uv run python scripts/run_wiki_agent.py --limit 5   # first 5 games only
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from admorphiq.hypothesis import WikiAgent, default_strategy_registry
from admorphiq.llm import load_candidate, load_registry


REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "scripts" / "wiki_agent_results.json"


def _pick_default_candidate() -> str:
    for meta in load_registry():
        if meta.enabled:
            return meta.id
    raise RuntimeError("No enabled candidate in configs/llm.yaml")


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the Wiki-driven hypothesis agent")
    ap.add_argument("--candidate", default=None, help="LLM candidate id (default: first enabled)")
    ap.add_argument("--limit", type=int, default=0, help="Stop after N games (0 = all)")
    ap.add_argument(
        "--budget",
        type=int,
        default=3000,
        help="Per-strategy action budget (default 3000; lower for a quick sweep)",
    )
    args = ap.parse_args()

    # Lazy import: only need arc_agi once we actually run games
    from arc_agi import Arcade, OperationMode

    cid = args.candidate or _pick_default_candidate()
    print(f"Loading LLM candidate: {cid}", flush=True)
    llm = load_candidate(cid)
    agent = WikiAgent(llm=llm, strategy_registry=default_strategy_registry())

    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    env_infos = arcade.get_environments()
    if args.limit:
        env_infos = env_infos[: args.limit]
    print(f"Running on {len(env_infos)} env(s)", flush=True)

    results: list[dict] = []
    t_all = time.time()
    for i, info in enumerate(env_infos, 1):
        game_id = info.game_id
        title = info.title or "?"
        print(f"[{i:>2}/{len(env_infos)}] {game_id} ({title}) ...", flush=True)
        try:
            env = arcade.make(game_id)
        except Exception as exc:  # noqa: BLE001
            results.append({"status": "error", "stage": "make", "game_id": game_id, "error": str(exc)})
            continue
        if env is None:
            results.append({"status": "error", "stage": "make", "game_id": game_id, "error": "make() returned None"})
            continue
        trace = agent.run(env, title=title, budget_per_strategy=args.budget)
        trace["env_index"] = i
        trace["game_id"] = game_id
        results.append(trace)
        hyp = trace.get("hypothesis", {})
        best = trace.get("best_levels", "?")
        print(
            f"    type={hyp.get('game_type', '?'):<18s} "
            f"primary={hyp.get('primary_strategy', '?'):<20s} "
            f"levels={best}",
            flush=True,
        )
        # Persist after every env so a crash doesn't erase progress
        OUT.write_text(
            json.dumps(
                {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "candidate": cid,
                    "results": results,
                },
                indent=2,
            )
        )

    total = time.time() - t_all
    n_ok = sum(1 for r in results if r.get("status") == "ok")
    lvls = sum(int(r.get("best_levels", 0)) for r in results)
    print(f"\nDone. {n_ok}/{len(results)} games completed, {lvls} total levels, {total:.1f}s")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
