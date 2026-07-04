---
title: R32 — neural forward model + planning
type: round-log
round: R32
axis: neural-world-model
keywords: [forward-model, neural-world-model, change-mask, planning, transfer-honest, state-uniqueness]
verdict: PARTIAL — planning FIRES (beats state-uniqueness!) but 92% takeover crushes novelty (0.0017≈baseline, clears 2/9)
commit: none (env-gated OFF = card; forward_model.py kept)
date: 2026-07-04
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
