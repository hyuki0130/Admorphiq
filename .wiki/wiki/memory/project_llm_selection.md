---
name: LLM Selection for Phase 8 Hypothesis Engine
description: Qwen 3 8B is primary Kaggle candidate; 14B as reserve; Gemma 4 26B MoE excluded due to T4 VRAM; edge variants dropped
type: project
originSessionId: 96a72d05-e421-4801-9b30-810c293777f0
---
## Status (2026-04-21): Qwen 3 8B selected as primary candidate, bench in progress

Decision path:
1. Initial Qwen 3 / Gemma 4 MoE / Gemma 4 E4B three-way bench planned.
2. Correction: Gemma 4 26B MoE Q4 = 17 GB → **does not fit Kaggle T4 16 GB VRAM** alongside CNN (34M) + World Model (1.6M) + ~2 GB KV/activation. Effectively unavailable for submission.
3. Correction: Gemma 4 E2B / E4B are **edge-tuned**, weaker on pure reasoning than Qwen 3 8B. Not meaningful competitors for the reasoning-heavy Hypothesis Engine task.
4. Final candidate set is Qwen-family only. Gemma 4 26B MoE kept as disabled "local ceiling reference" in `configs/llm.yaml`.

## Active candidates (Kaggle T4 16 GB deployable)

| Candidate | Q4 weights | KV @ 4K ctx | Total @ 4K | T4 fit? | Status |
|-----------|-----------|-------------|------------|---------|--------|
| **Qwen 3 8B Q4** | ~5 GB | ~1.5 GB | ~8 GB | ✅ 8 GB margin | `enabled: true` (primary) |
| Qwen 3 14B Q4 | ~8.5 GB | ~3.2 GB | ~13 GB | ✅ 3 GB margin | `enabled: false` (reserve if 8B insufficient) |

Context budget rule: **keep effective prompt ≤ 4K tokens on T4**. The wiki retrieval recipe produces ~2K tokens by default, well under the cap.

## Disabled but preserved (reference only)

| Candidate | Reason |
|-----------|--------|
| Gemma 4 26B MoE Q4 | 17 GB, exceeds T4 16 GB. Kept for local 24 GB unified-memory ceiling runs only. |
| Gemma 4 E2B / E4B | Removed from registry 2026-04-21. Edge-optimized, weaker reasoning than Qwen 3 8B. Re-add only if future task needs on-device audio/vision. |

## Decision rubric after Qwen 3 8B bench completes

- **classification_accuracy ≥ 0.80 AND strategy_hit_rate ≥ 0.80** → Qwen 3 8B primary, no need to test 14B. LoRA fallback reserved if ever insufficient.
- **accuracy 0.60-0.80** → also bench Qwen 3 14B; pick whichever wins after accounting for latency (14B is ~2-3× slower on T4).
- **accuracy < 0.60** → revisit: either the wiki context is insufficient (improve retrieval recipe) or 14B needed or LoRA needed. Do not pre-commit.

## Bench Run 1 results (2026-04-21)

### Run 1a — thinking mode ON (Qwen 3 default)
- classification_accuracy: 24%
- strategy_hit_rate: 32%
- mean_latency: 12,436 ms/call
- total_runtime: 311 s (5.2 min for 25 games)
- **Finding**: Qwen 3 defaults to a `<think>...</think>` phase that occupies all of `num_predict` tokens. Raw `response` came back empty on 13/25 prompts; parser scored these as None/None.

### Run 1b — thinking mode OFF (`/no_think` prefix + `"think": false`)
- classification_accuracy: 32%
- strategy_hit_rate: 40%
- mean_latency: **1,748 ms/call** (7× faster than Run 1a)
- total_runtime: 43.7 s
- **Finding**: Parse success rises to ~100% but accuracy still low. Qwen answers `movement/bfs_state_space` for almost every game — treating it as a default when the prompt lacks concrete observations.

### Why Run 1 is NOT a fair verdict on Qwen 3 8B
The bench prompt only gave the model:
```
Game title: {game}
Win levels: see wiki
Available actions: [see wiki]
Dominant colors: [see wiki]
```
Real frame observations were not inlined. The wiki context loaded via `load_wiki_context(game_type_hint)` included the `reasoning/` pages + the game-type page, but **not** the target game's own page. So Qwen could not correctly classify a game purely from its title — guessing "movement" matched 8/25 games by coincidence.

Decision: **do not reject Qwen 3 8B on Run 1**. The bench is unfair. Next:
- Run 2: enrich prompt with actual frame summary (available_actions, dominant_colors, action-probe diff) captured at reset.
- Run 2: let retrieval include the target game's wiki page (mimics real inference retrieval).

Updated rubric still applies (accuracy thresholds), but against Run 2 numbers, not Run 1.

## Implementation notes discovered

- OllamaBackend must prepend `/no_think` for `family: qwen3`; also pass `think: false` in body. Already patched in `src/admorphiq/llm/ollama_backend.py`.
- `max_tokens=512` is enough for clean JSON output when thinking is off. When thinking is on, budget must be ≥ 2048 to leave room for the answer after thoughts.
- JSON parsing in `scripts/bench_llm.py` is already lenient (`_parse_json_lenient`) — handles markdown fences, trailing commas, surrounding prose.

## Why not Claude Code / Anthropic API
- Kaggle internet disabled at inference. Only pre-downloadable open-weight models viable.

## How to apply
- `configs/llm.yaml` is the single source of truth; scripts load via `admorphiq.llm.registry`.
- Do not hardcode model names in scripts — use `load_candidate(id)`.
- When pre-staging weights on Kaggle, upload as a Kaggle Dataset containing the Ollama blob files or HF model directory; note the dataset ID in `kaggle_dataset_id` field.
- Re-run `scripts/bench_llm.py` after any wiki content change that could affect retrieval.

## Related artifacts
- `configs/llm.yaml` — candidate registry
- `configs/llm_bench_tasks.yaml` — 25-game labeled evaluation set
- `scripts/bench_llm.py` — benchmark harness (partial-save safe)
- `src/admorphiq/llm/ollama_backend.py` — HTTP backend for Ollama-served models
- `.wiki/wiki/reasoning/benchmark_protocol.md` — protocol doc
- `.wiki/wiki/reasoning/wiki_retrieval_recipe.md` — context assembly rules
