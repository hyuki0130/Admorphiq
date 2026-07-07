---
title: R50b — honest-protocol K=8 re-measurement (leakage removed)
type: round-log
round: R50b
axis: llm-selection
keywords: [executable-world-model, honest-protocol, leakage, k8-refinement, gemma4-31b, gpt-oss-120b, deploy-candidate, few-shot-limit]
verdict: HONEST baseline = gemma4-31b-q8 0.133/0.139 (deploy candidate) ≫ gpt-oss-120b 0.039/0.061 (leak-inflated 7x); ar25 0→0.80 proves genuine execution-feedback climb; hard-semantic unlocks were leakage mirages
commit: pending
date: 2026-07-07
description: Leakage-free K=8 on Kaggle-identical HW — gemma4-31b-q8 0.133/0.139 is the real EWM baseline; gpt-oss-120b collapses to 0.039; prior "hard game unlocks" were held-out-leak mirages
---

# R50b — honest-protocol K=8 (the number that maps to Kaggle)

Same VM/config as [[r50_cloud-bench-k3]] but with the leakage fix (`aea406d`): refinement
feedback from TRAIN mismatches only, train-fit round selection recorded natively. K=8, top-2
models from the leaky pass, 18 games.

## Results (exact-frame keep-last / keep-best)

| model | honest K=8 | leaky K=3 | inflation |
|---|---|---|---|
| **gemma4:31b-it-q8_0** | **0.133 / 0.139** | 0.433 / 0.494 | 3.3x |
| gpt-oss:120b | 0.039 / 0.061 | 0.272 / 0.294 | **7.0x** |

- **Deploy candidate = gemma4-31b-q8** (3.4x gpt-oss honest; valid 1.00 vs 0.83).
- gpt-oss's leaky #2 ranking was mostly leak-exploitation — it fit revealed test answers
  exceptionally well; gemma4-31b's lead survives the fix, so its advantage is real induction.
- **ar25 0→0.80 over 8 honest rounds** — the cleanest proof that the execution-feedback loop
  works with ONLY train labels (the Kaggle-realizable protocol). lf52 = 1.00 zero-shot.
- Honest traction set (either model >0): ar25 0.80, lf52 1.00, dc22 0.30, sc25 0.20, ka59/sb26/
  tr87/tn36/g50t 0.10 — **9/18 games**, but only 3 are strong (≥0.3). The R49-era "hard semantic
  unlocks" (su15 0.60, re86 0.40, tr87 0.50 …) did NOT reproduce → they were held-out-leak
  mirages. ⛔ Do not cite any pre-R50b absolute EWM number as a Kaggle expectation.
- last = sel = best across nearly all games: honest refinement is monotone-stable (no
  late-round regressions once test-fitting is impossible) → deploying the LAST round's code
  is safe at runtime.

## What limits honest performance (R51 axes, in leverage order)

1. **Few-shot budget**: 15 transitions is thin for stochastic/multi-mechanic games. Axis: 40-80
   transitions (npz files hold hundreds) + longer diffs; 64k ctx has room.
2. **Game-class routing**: EWM is decisively good on a minority of games (ar25/lf52/dc22-class).
   Integration design: run EWM synthesis at discovery; deploy its plan only when train-fit is
   high; else fall back to the graph agent ([[r36_graph-frontier-bfs]]).
3. Model: gemma4-31b-q8 is the working pick; revisit only after 1-2 are exhausted.

## Ops

Total cloud spend for R50+R50b ≈ $10-12 spot (credits). VM `ewm-bench` STOPPED (disk kept)
— restart with `gcloud compute instances start ewm-bench --zone=asia-east1-a`.

**Related**: [[r50_cloud-bench-k3]] (leaky pass + fix provenance), [[r49_ewm-bench-partial]]
(local runs — same leak, treat as relative-only), [[r48_llm-selection-ewm]].
