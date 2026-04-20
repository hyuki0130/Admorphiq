---
type: reasoning
input_type: one or more LLM candidates (Qwen 3 / Gemma 4 MoE / Gemma 4 E4B / future)
output_type: ranked selection + per-candidate accuracy & latency
---

# Benchmark Protocol (Phase 8 Step 3-pre, Task #11)

> How to select the Hypothesis Engine LLM without a-priori bias. Runs each candidate through the same labeled task suite and ranks by measured accuracy × 1/latency.

## Artifacts

- `configs/llm.yaml` — candidate registry (set `enabled: true` after staging weights)
- `configs/llm_bench_tasks.yaml` — labeled ground truth (25 games × (game_type, primary_strategy, fallback_stack))
- `src/admorphiq/llm/registry.py` — backend protocol + MockLLM stub
- `scripts/bench_llm.py` — harness; reads the registry, runs every enabled candidate, writes `scripts/bench_llm_results.json`

## The two scored tasks

For each game the LLM sees:
1. Wiki context (selected via `[[wiki_retrieval_recipe]]`)
2. Opening frame summary (game title, available_actions, win_levels, dominant colors)

And must output a single JSON object:
```json
{
  "game_type": "...",
  "primary_strategy": "...",
  "fallback_stack": ["...", "..."],
  "rationale": "..."
}
```

Scoring:
- **classification_accuracy** = fraction of games where `game_type` matches ground truth.
- **strategy_hit_rate** = fraction of games where `primary_strategy` matches ground truth.
- **mean_latency_ms** = wall-clock average per game.

## Ranking formula

```
score = classification_accuracy × strategy_hit_rate / (1 + mean_latency_ms/10000)
```

The denominator penalises latency above 10 seconds but is lenient below. The highest-score candidate becomes `primary_pick`; the runner-up is the `fallback_pick`. Both are written to `scripts/bench_llm_results.json`.

## Guarantees

- **Model-agnostic harness**: `scripts/bench_llm.py` imports only `admorphiq.llm`; adding a new candidate is a YAML edit + one Python class.
- **Ground truth in sync with wiki**: `configs/llm_bench_tasks.yaml` ground truth is hand-authored to match the latest `.wiki/wiki/games/*.md` entries. A test in `tests/` (to be written) will enforce drift detection.
- **MockLLM validates the harness**: the stub answers deterministically from the ground truth dataset, so running the bench with `candidates: [{id: mock, enabled: true}]` always scores 100%. If the mock drops below 100%, the harness itself has a bug.

## Pre-run checklist (when staging a real candidate)

1. Download weights: `huggingface-cli download <huggingface_id> --local-dir ./models/<id>`
2. Implement a concrete backend in `src/admorphiq/llm/<family>.py` that subclasses `LLMBackend`.
3. Wire it into `registry.load_candidate` (match on `meta.family`).
4. Flip `enabled: true` in `configs/llm.yaml` for that candidate.
5. Run `uv run python scripts/bench_llm.py`.
6. Record results in `.wiki/raw/commits.md` under the date the benchmark ran.
7. Select the primary; record decision in `memory/project_llm_selection.md`.

## Pitfalls

- **Context leakage**: wiki context may accidentally contain the expected answer verbatim. Keep ground-truth strings out of the wiki where possible; if unavoidable, note it.
- **JSON parse failures**: some LLMs emit prose around JSON. Harness already handles `json.loads` failure by counting the answer as wrong; make sure the prompt requests strict JSON.
- **Cache skew**: running the bench without clearing a candidate's KV cache between games can inflate latency for later games; reset per game.
- **Single-run noise**: temperature > 0 can cause accuracy jitter. Run 3× per candidate and take the median.

## Related

- [[wiki_retrieval_recipe]] — defines which pages are fed as context
- [[../selector]] — the dispatch rules the LLM is learning to reproduce
- [[../../CLAUDE.md]] §LLM Selection — policy, decision timing
