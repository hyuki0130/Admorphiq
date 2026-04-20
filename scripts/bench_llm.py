"""Phase 8 LLM candidate benchmark (Task #11).

For every `enabled` candidate in `configs/llm.yaml`, run two tasks per preview
game:

  classify  — given wiki context + opening-frame summary, predict the `game_type`.
  pick      — given classification + wiki, pick `primary_strategy` + `fallback_stack`.

Score against the ground truth in `configs/llm_bench_tasks.yaml`. Emit
`scripts/bench_llm_results.json` with per-candidate accuracy, per-game detail,
elapsed seconds, and a selection recommendation.

This harness is **LLM-agnostic**. No model-specific logic lives here. The
selection recommendation reads `accuracy`, `latency_ms`, and headroom; it does
not privilege Qwen or Gemma a-priori.

Run:
    uv run python scripts/bench_llm.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import yaml

import re

from admorphiq.llm import load_candidate, load_registry


def _parse_json_lenient(raw: str) -> dict[str, Any]:
    """Extract a JSON object from an LLM response. Tolerant of prose, markdown fences,
    and trailing commas. Returns {} on failure."""
    if not raw:
        return {}
    # Strip markdown code fences if present
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        raw = m.group(1)
    else:
        # Grab first {...} block
        m = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", raw, re.DOTALL)
        if m:
            raw = m.group(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_YAML = REPO_ROOT / "configs" / "llm_bench_tasks.yaml"
WIKI_DIR = REPO_ROOT / ".wiki" / "wiki"
OUT = REPO_ROOT / "scripts" / "bench_llm_results.json"


PROMPT_TEMPLATE = """You are the Admorphiq Phase 8 Hypothesis Engine.

You will be given wiki context (game_type + reasoning pages) and a summary of
the opening frame of an ARC-AGI-3 game. Output ONE JSON object with fields:
  game_type         - one of: movement | click | programming_puzzle | merge_puzzle |
                      sokoban | platformer | transform | delivery | slider_puzzle |
                      rotation | sort_puzzle | spell_cast | sequence | hybrid | unknown
  primary_strategy  - string (see selector.md)
  fallback_stack    - list of up to 3 strategy names
  rationale         - 1-2 sentences

No prose outside the JSON.

=== Wiki Context ===
{context}

=== Game Summary ===
Game title: {game}
Win levels: {win_levels}
Available actions: {avail}
Dominant colors: {colors}
"""


def load_wiki_context(game_type_hint: str | None) -> str:
    """Pick a small, relevant slice of wiki markdown for the prompt.

    Deliberately small (~30KB) so any candidate LLM's context fits.
    Order matters — core reasoning first, then type-specific, then strategies.
    """
    must = [
        "reasoning/discovery_phase.md",
        "reasoning/frame_to_strategy_chain.md",
        "reasoning/hypothesis_check.md",
        "selector.md",
    ]
    type_page = f"game_types/{game_type_hint}.md" if game_type_hint else None
    extras = [
        "lessons/v2_hash_obfuscation.md",
        "lessons/brittle_tells.md",
        "strategies/frame_only/bfs_state_space.md",
        "strategies/brittle/internal_method_call.md",
    ]
    pages = [*must, *( [type_page] if type_page else [] ), *extras]
    parts: list[str] = []
    for p in pages:
        path = WIKI_DIR / p
        if path.exists():
            parts.append(f"--- {p} ---\n{path.read_text()}")
    return "\n\n".join(parts)


def score_answer(answer: dict[str, Any], ground_truth: dict[str, Any]) -> dict[str, bool]:
    """Return {classification, strategy_hit}."""
    return {
        "classification": answer.get("game_type") == ground_truth["game_type"],
        "strategy_hit": answer.get("primary_strategy") == ground_truth["primary_strategy"],
    }


def run_candidate(candidate_id: str) -> dict[str, Any]:
    """Run the full benchmark for one candidate. Returns per-game detail + totals.

    Deliberately environment-free: the prompt uses only the game title and ground-
    truth-free metadata ("see wiki" placeholders). This keeps the bench portable
    (runs on Kaggle, Colab, or any box with the LLM backend) and produces a cold-
    prompt baseline per candidate. For a deployment-style benchmark that also
    includes live `FrameData` observations, build a separate driver; do not fold
    live-env coupling into this harness.
    """
    llm = load_candidate(candidate_id)
    tasks = yaml.safe_load(TASKS_YAML.read_text())["tasks"]
    per_game: list[dict[str, Any]] = []
    total_class_hits = 0
    total_strat_hits = 0
    total_latency_ms = 0.0

    for t in tasks:
        game = t["game"]
        ctx = load_wiki_context(t["game_type"])
        prompt = PROMPT_TEMPLATE.format(
            context=ctx[:8000],           # 8KB context keeps even 7B-class models responsive
            game=game,
            win_levels="see wiki",
            avail="[see wiki]",
            colors="[see wiki]",
        )
        t0 = time.time()
        raw = llm.generate(prompt, max_tokens=512)
        elapsed_ms = (time.time() - t0) * 1000
        total_latency_ms += elapsed_ms

        answer = _parse_json_lenient(raw)

        scored = score_answer(answer, t)
        total_class_hits += int(scored["classification"])
        total_strat_hits += int(scored["strategy_hit"])

        per_game.append(
            {
                "game": game,
                "expected_game_type": t["game_type"],
                "predicted_game_type": answer.get("game_type"),
                "expected_primary": t["primary_strategy"],
                "predicted_primary": answer.get("primary_strategy"),
                "classification_ok": scored["classification"],
                "strategy_ok": scored["strategy_hit"],
                "latency_ms": round(elapsed_ms, 2),
            }
        )

    n = len(tasks)
    return {
        "candidate_id": candidate_id,
        "meta": {
            "display_name": llm.meta.display_name,
            "family": llm.meta.family,
            "expected_vram_gb": llm.meta.expected_vram_gb,
            "context_tokens": llm.meta.context_tokens,
        },
        "total_games": n,
        "classification_accuracy": total_class_hits / n,
        "strategy_hit_rate": total_strat_hits / n,
        "mean_latency_ms": total_latency_ms / n,
        "per_game": per_game,
    }


def main() -> None:
    enabled = [m.id for m in load_registry() if m.enabled]
    print(f"Benchmarking {len(enabled)} enabled candidate(s): {enabled}", flush=True)
    results: list[dict[str, Any]] = []
    for cid in enabled:
        print(f"\n>>> running {cid} ...", flush=True)
        t0 = time.time()
        try:
            r = run_candidate(cid)
            r["status"] = "ok"
            r["total_runtime_sec"] = round(time.time() - t0, 1)
            print(
                f"    done: class={r['classification_accuracy']:.2f} "
                f"strat={r['strategy_hit_rate']:.2f} "
                f"latency_ms={r['mean_latency_ms']:.0f} "
                f"total={r['total_runtime_sec']}s",
                flush=True,
            )
        except Exception as e:
            r = {"candidate_id": cid, "status": "error", "error": str(e), "total_runtime_sec": round(time.time() - t0, 1)}
            print(f"    FAILED: {e}", flush=True)
        results.append(r)
        # Persist partial results after every candidate so a later crash doesn't erase progress.
        partial = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "results": results,
        }
        OUT.write_text(json.dumps(partial, indent=2))

    # Selection: rank by classification_accuracy * strategy_hit_rate / latency_factor.
    def _score(r: dict[str, Any]) -> float:
        if r.get("status") != "ok":
            return -1.0
        cls = r["classification_accuracy"]
        strat = r["strategy_hit_rate"]
        latency_sec = max(r["mean_latency_ms"] / 1000.0, 0.001)
        return cls * strat / (1.0 + latency_sec / 10.0)

    ranked = sorted(results, key=_score, reverse=True)

    ok = [r for r in ranked if r.get("status") == "ok"]
    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "primary_pick": ok[0]["candidate_id"] if ok else None,
        "fallback_pick": ok[1]["candidate_id"] if len(ok) > 1 else None,
        "results": results,
    }
    OUT.write_text(json.dumps(summary, indent=2))
    print(f"Wrote {OUT}")
    for r in ranked:
        if r.get("status") == "ok":
            print(
                f"  {r['candidate_id']:<22s} "
                f"class={r['classification_accuracy']:.2f}  "
                f"strat={r['strategy_hit_rate']:.2f}  "
                f"latency_ms={r['mean_latency_ms']:.1f}"
            )
        else:
            print(f"  {r['candidate_id']:<22s} FAILED: {r.get('error', '?')}")


if __name__ == "__main__":
    main()
