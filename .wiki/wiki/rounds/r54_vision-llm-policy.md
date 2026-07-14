---
type: reasoning
round: R54
axis: vision-llm-as-policy
keywords: [vision-llm, vlm-policy, multimodal, gemma4, reki, forge, labeled-image, pick-json-action, reflection-memory, dead-signature, plan-queue, latency, proxy-model]
verdict: built (local validation deferred to Kaggle 31B path — proxy latency)
commit: pending
date: 2026-07-14
description: Built the vision-LLM-as-policy agent (the M1 #2/#3 Reki/forge lever) — render frame to a labeled image, multimodal LLM picks ONE JSON action/turn under legal-action masking, with reflection memory + dead-signature avoidance + a 1-4 action plan queue + JSON self-repair. Additive module + `--agent vlm`. Local measurement halted: the small gemma4-26b vision proxy costs ~26s per changing-board turn (30-action su15 probe >700s), so policy-quality validation moves to the Kaggle 31B kernel path (phase B); the build is banked and tested.
---

# R54 — Vision-LLM-as-policy (Reki/forge lever)

> A multimodal LLM plays the game directly: each turn renders the 64×64 frame to
> a LABELED image + ASCII grid, and the model returns ONE JSON action (or a short
> 1-4 action plan) under legal-action constraints, with reflection memory,
> dead-signature avoidance, and JSON self-repair. This is the evidence-backed
> lever from the M1 top-team research — #2 (Reki) and #3 (forge) both use exactly
> this pattern with Gemma-4-31B.

## Why this round

`[[../lessons/lb_top_team_research_20260714]]` established that all M1 top-3 use offline LLM
brains, and that the untried lever for our stack is vision-LLM-as-policy (Reki /
forge): labeled frame image → pick-JSON action + reflection memory (~10 steps) +
dead-signature avoidance + legal-action constraints + 1-4 action plan queue +
numpy fallback. "Simple > complex" (best runs had extra machinery OFF). Because
the policy plays FEW actions per level (near-human counts), per-action LLM latency
is acceptable and it can score on RHAE where exhaustive search scores ~0. This
round builds and measures that path — additively, alongside (not replacing) the
LLM-free chained card.

## What was built (M1 + M2)

New module `src/admorphiq/vlm_policy.py` (generic, no game ids):

- **Labeled-image renderer** `render_frame_png` — upscales the 64×64 index grid
  (ARC 16-color palette) to a readable PNG with a coordinate ruler: columns
  labeled x, rows labeled y, both 0-63, light gridlines every 8 cells. Plus
  `ascii_grid` (base-16 color digits with x/y ruler headers) so the model gets a
  textual cross-reference to the image.
- **Multimodal plumbing** `ollama_vlm(prompt, images)` — ollama `/api/chat` with
  base64 PNG attached. **Model-agnostic** via `VLM_MODEL` (default the local
  proxy; the 31B deploy swap is config-only).
- **JSON action schema + self-repair** `parse_plan` — extracts the first JSON
  object (tolerating prose / code fences), returns a legal-masked list of
  `(action_id, x, y)` tuples + the model's `observation` / `hypothesis`.
  Repairs single-action dicts, string action ids (`"ACTION6"`), missing coords;
  drops illegal ids and ACTION6-without-coordinates.
- **Policy loop** `VLMPolicyAgent` (harness contract, `restart_on_game_over`):
  per decision boundary render → prompt (state summary + reflection memory +
  legal actions + dead-signature list) → parse a 1-4 action plan → queue it.
  Queued actions run WITHOUT further LLM calls (amortizing latency); the loop
  re-plans when the queue empties. Online per-game learning: dead-signature set
  from observed no-change actions (coarse 8×8 cell for clicks), running
  reflection memory from the model's hypothesis, recent action→effect history.
  Degrades to an exploratory fallback when the model is unreachable (never
  crashes a bench run).

Registered `--agent vlm` in `scripts/score_efficiency.py` (7-line additive
branch). 13 unit tests in `tests/test_vlm_policy.py` (renderer/ASCII shapes,
parser self-repair + legal masking, loop amortization, dead-signature growth,
reflection capture, level reset, offline degradation). Full suite **791 passed**,
ruff clean. The change is purely additive — the 10 chained/WMA/graph guards'
code paths are untouched (byte-identical by construction).

## Measured: local proxy vision latency is the blocker (M3 suspended)

**Proxy model**: `gemma4:26b-a4b-it-qat` (15 GB, vision-capable, gemma family →
prompt-format continuity with the gemma4-31b-q8 deploy target). Chosen because it
is <18 GB (the Mac WindowServer-crash ceiling) and the closest local stand-in.

- **Vision plumbing verified**: rendered a red/blue two-square board, asked for
  the red square's center → model returned exactly `{"x":16,"y":16}` (square spans
  cols/rows 8-24, true center 16,16). Spatial grounding works.
- **Per-turn latency**: an ollama-cached *identical* repeat call is 0.5s, but the
  board CHANGES every turn, so each real decision is a cache-miss ≈ **26 s**
  (consistent with the R53 finding that gemma's sliding-window attention defeats
  prompt caching). A 30-action su15 probe exceeded the 700 s cap without
  finishing.
- **Consequence**: a 5-game × 300-action local battery is impractical on the Mac
  proxy (each wall game ≈ 2 h). Per team-lead direction, **local measurement is
  suspended and policy-quality validation moves to the Kaggle-kernel path** with
  the 31B model on RTX PRO 6000 (faster vision + the real deploy model). The
  build is banked and unit-verified; the head-to-head vs the chained card is a
  phase-B Kaggle measurement.

## Proxy-model caveat (honesty)

Any local number here would be a **LOWER BOUND** for the 31B deploy model: the
26 B-a4b proxy is smaller and QAT-quantized, and the Mac GPU is far slower than
the Kaggle RTX PRO 6000. A weak/slow proxy result is NOT a verdict on the lever
(`[[../lessons/lb_top_team_research_20260714]]` falsification requires a *fair* bring-up at
gemma-31b scale). This round delivers the validated, tested machinery so the
31B Kaggle run is a config swap (`VLM_MODEL=gemma4:31b-it-q8_0`), not a rebuild.

## Next (phase B, Kaggle 31B)

1. Run `--agent vlm` on the Kaggle/GCP 96 GB box with the 31B model: the 2 sanity
   games (su15, ls20) + 3 walls (bp35, dc22, g50t), `--max-actions 300`, ×2 for
   clears; record per-game actions/levels/wall-clock.
2. Head-to-head vs the chained card on the public 25 (fair bring-up: prompt
   iterations + the Reki efficiency kit already in the loop).
3. If it measures below the LLM-free card after a fair bring-up, update the
   falsification section of `[[../lessons/lb_top_team_research_20260714]]`.

## Related

- [[../lessons/lb_top_team_research_20260714]] — the evidence and the lever definition.
- [[r53_unified-harness]] — the current architecture; gemma SWA latency finding.
- [[r55_code-repl-agent]] — the code-REPL arm; Round-2 pairs this JSON-policy
  agent against it in the 2×2 ablation.
- [[index]]
