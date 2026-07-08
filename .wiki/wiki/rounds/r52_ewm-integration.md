---
title: R52 — EWM integration into the graph-frontier agent (GF_EWM, default OFF)
type: round-log
round: R52
axis: ewm-integration
keywords: [executable-world-model, gf-ewm, action-pruning, graph-frontier, runtime-fit-gap, no-change-pruning, adaptive-synthesis, null-result, ralph]
verdict: integration BUILT + measured; score delta +0.0000 (NULL) — no-change pruning is redundant with the agent's empirical self-loop learning; runtime raw-observation fit (mean 0.357, 3/24 >= gate) far below bench-curated fit; default-OFF safe; R53 = goal-conditioned WM, not no-change pruning
commit: pending
date: 2026-07-08
description: Productized the R49-R51 EWM into the deployed agent (GF_EWM, default OFF) — mechanically works but scores identically to baseline; the no-change pruning signal is redundant with empirical exploration, and runtime fit is far below bench fit
---

# R52 — EWM integration into the graph-frontier agent

Ralph run. Turned the measured executable-world-model findings ([[r50b_honest-k8]],
[[r51_fewshot-prior-sweep]]) into runtime machinery on the DEPLOYED agent, then measured it
honestly on the sample games. Game-agnostic throughout (no game ids in `src/admorphiq/ewm/`).

## What was built

- **`src/admorphiq/ewm/core.py`** — serialization / prompts / sandbox / scoring / `OllamaChat`
  extracted from the bench so runtime and dev-time share ONE implementation (US-1).
- **`src/admorphiq/ewm/synthesizer.py`** — `synthesize_world_model()`: adaptive multi-config
  (f15/f40/prior, the R51 union set), K-round refinement on TRAIN mismatches only, candidate
  scored on ALL observations, argmax-train-fit selection (ties→later), early-exit at fit_target,
  injectable LLM (US-2).
- **`GF_EWM` hook** in `graph_frontier_agent.py` (US-3, default OFF = byte-identical card): after
  `GF_EWM_MIN_OBS`=30 observed transitions, synthesize once from the agent's OWN observations;
  keep only at fit ≥ `GF_EWM_MIN_FIT`=0.8; untried actions the model predicts no-change sort
  after predicted-change within their tier (deprioritized, never removed).
- 12 new contract tests (synthesizer 4, GF_EWM 4, + the R50b/R51 harness pins); full suite 577.

## Measurement (US-4): GF_EWM=0 vs =1, full-25 @8000, gpt-oss:20b local

**Score delta = +0.0000.** Synthesis fits: n=24, mean 0.357, max 1.00, **3 kept** at the 0.8
gate (FT09 1.00, LP85 1.00, SP80 0.80). In every kept game, `base == ewm` exactly.

**Why NULL (the load-bearing insight):** no-change pruning is REDUNDANT with what the graph
agent already learns. A "no-change" action self-loops in the transition graph; the agent tries
it once, records the self-loop, and its tier/frontier machinery already deprioritizes it. The
world model predicts exactly what empirical exploration discovers on first contact — so it saves
~0 actions and cannot move the squared-efficiency metric. Lowering the gate to admit S5I5/SB26/
VC33 (fit 0.73-0.77) would not help: the kept-game evidence already shows the pruning signal is
inert on score.

**Runtime-vs-bench fit gap:** bench-curated 15/40-shot splits gave gemma4-31b 0.133 honest; here,
raw runtime observations (whatever the agent happened to probe, uncurated) yield mean fit 0.357
for gpt-oss:20b but only 3/24 clear the deploy gate. Observation QUALITY/curation at runtime is a
real secondary wall, distinct from model choice.

## Verdict + R53 direction

GF_EWM as a no-change pruner is **measured-inert for score** — kept default-OFF and safe; it is
NOT deleted (mechanically correct, zero-risk, and a substrate for goal-conditioned use). The
value of an executable world model is in FORWARD PLANNING toward an inferred goal (rollouts that
find a short action sequence), not in pruning no-change actions after the fact. R53 = feed the
synthesized `predict_next_frame` into goal-conditioned search (the `planner/goal.py` rollout
already exists), gated on high train-fit, measured on the games where fit clears the gate.

**Related**: [[r51_fewshot-prior-sweep]] (config union the synthesizer deploys), [[r50b_honest-k8]]
(honest protocol + train-fit selection), [[r36_graph-frontier-bfs]] (the host agent).
