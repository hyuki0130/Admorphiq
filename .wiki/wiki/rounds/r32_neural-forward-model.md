---
title: R32 — neural forward model + planning
type: round-log
round: R32
axis: neural-world-model
keywords: [forward-model, neural-world-model, change-mask, planning, transfer-honest, state-uniqueness]
verdict: PARTIAL — planning FIRES (beats state-uniqueness!) but 92% takeover crushes novelty (0.0017≈baseline, clears 2/9)
commit: none (env-gated OFF = card; forward_model.py kept)
date: 2026-07-04
description: Neural forward model — planning fires on unseen frames (beats the state-uniqueness wall) but 92% takeover crushes novelty; 0.0017 ≈ baseline
---

# R32 — learned neural forward model (change-mask) + short-horizon planning

**Axis**: neural-world-model · **Verdict**: PARTIAL / needs gate fix
Small (18.7K-param) conv forward model predicting a change-mask, separate from the 34M policy,
trained online; short-horizon (H=3) planning scored by predicted change/novelty; warm-start OFF.

**BREAKTHROUGH (half)**: planning ACTUALLY FIRES — fwd_planned reaches 2584/2800 (92%). Unlike the
tabular R10/R27b (planned=0, dead on state-uniqueness), the NEURAL model produces predictions on
near-unique unseen frames, so planning is live. State-uniqueness wall is BEATEN for activation.

**FAILURE (the other half)**: it fires TOO MUCH. After a brief fallback warmup (~216 steps), planning
takes over 92% of actions and CRUSHES the novelty exploration that actually clears games. Result
0.0017 ≈ baseline 0.0014 but clears drop to 2/9 (baseline 4/9) — only SP80/R11L survive. Same pattern
as R5/R15/R25: planning/prior that OVERRIDES novelty regresses. The 18.7K model's change-mask
predictions aren't accurate enough to steer well, yet it dominates action selection.

**Next (R32b)**: make planning ADDITIVE and MINORITY — gate it hard on forward-model prediction
CONFIDENCE/ACCURACY (only act on a planned action when the model's recent prediction accuracy is
high), so novelty stays the primary driver and planning only nudges when the model is genuinely
reliable. Keep forward_model.py (the neural predictor is the real asset; the wall it beats is real).

**Related rounds**: [[r27b_planning-gate]], [[r10_object-state-hash]], [[r05_planning-override]], [[r29_warmstart-off]]
See map: [[rounds_index]]. Overview: [[online_rl_sprint_round_log]].

## R32b addendum (2026-07-04) — confidence gate didn't help; the wall is GOAL, not activation
Added a running change-mask prediction-accuracy gate (RL_FWD_MIN_ACC=0.85). Result 0.0013 ≈ baseline
0.0014, clears 3/9. Planning STILL fired 87% (2430/2800) — the model's change-mask accuracy exceeds
0.85 (it predicts WHAT changes well), so the gate stays open, but planning still doesn't help.

DECISIVE DIAGNOSIS: the neural forward model beats STATE-UNIQUENESS (it predicts on unseen frames)
but hits a new wall — GOAL ABSENCE. It predicts "what will change" accurately, but not "which change
leads to level completion". Planning scores rollouts by predicted change/novelty, so it just does
novelty-by-another-name + prediction noise → no efficiency/clear gain. Forward-model planning is
INERT for scoring toward the goal WITHOUT a goal-inference signal.

CONCLUSION: forward-model planning axis is dead UNTIL there is GOAL INFERENCE (what state = level
solved). The forward model (forward_model.py) remains a valid asset for a future goal-directed
planner, but planning-toward-novelty via the model does not transfer-beat 0.0014. Next real lever =
GOAL INFERENCE (detect the level-complete condition), which the offline LLM was meant to provide at
discovery — the CLAUDE.md R27 pipeline's missing piece.
