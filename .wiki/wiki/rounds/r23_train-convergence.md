---
title: R23 — training convergence (TRAIN_EVERY sweep)
type: round-log
round: R23
axis: training-convergence
keywords: [train-every, gradient-steps, convergence, efficiency, overtraining]
verdict: FAIL (sweep closed: =4 0.0114, =6 0.0112, both < =8 card 0.0134; default 8 stays)
commit: none
date: 2026-07-02
---

# R23 — training convergence speed (TRAIN_EVERY sweep)

**Axis**: training-convergence · **Verdict**: FAIL — sweep closed. =4→0.0114, =6→0.0112, both below the =8 card (0.0134). More frequent training = overtraining/instability on this small learner. Default TRAIN_EVERY=8 stays.
**Keywords**: train-every, gradient-steps, convergence, efficiency, overtraining

Hypothesis: faster online training → fewer actions to clear → higher efficiency (R13 lever).
On the R19 shaping card, env override RL_TRAIN_EVERY.

- **TRAIN_EVERY=4** (2x more frequent, R23): mean game_score 0.0134 → **0.0114 (WORSE)**. Mixed —
  SOME efficiency gains (FT09 453→300, CN04 831→222, LS20 253→142 actions) but OVERTRAINING
  instability elsewhere (M0R0 154→1163, CD82 524→1183 actions blew up), S5I5 lost, BP35 flaky.
  Also ~2x wall-clock/game (cost↑) for a lower score — a clear loss at =4.
- **TRAIN_EVERY=6** (R23b): mean 0.0112 — also WORSE. FT09/CD82 touched L2 but seed variance
  (FT09 0.0175→0.0003) + CN04 worse + S5I5 lost sank the net. SWEEP CLOSED: =8 default is best;
  more-frequent training doesn't help this learner (tune-before-discard honored with 2 configs).

**Related rounds**: [[r13_efficiency-insight]], [[r19_reward-shaping]], [[r08_budget-depth]]
See map: [[rounds_index]]. Overview: [[online_rl_sprint_round_log]].
