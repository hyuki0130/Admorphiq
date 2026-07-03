---
title: R28 — keep-learning-across-levels
type: round-log
round: R28
axis: depth-transition
keywords: [keep-learning, level-transition, depth, policy-retention, L2]
verdict: FAIL (0.0121 < card 0.0134; retry of R6 confirms)
commit: none (env-gated, default OFF = card)
date: 2026-07-04
---

# R28 — keep-learning-across-levels

**Axis**: depth-transition · **Verdict**: FAIL
On level-up, keep policy/optimizer/buffer, refresh only novelty counts (env RL_KEEP_ACROSS_LEVELS,
default OFF = card). Retry of R6 on the R19 shaping base. Result: mean game_score 0.0121 < card
0.0134. M0R0 still touches L2 (maxlvl=2) but its MEAN dropped (0.0159→0.0043); rest identical to
card. Confirms R6: a new level is a DIFFERENT state space, so retaining the old policy HINDERS more
than helps. keep-learning axis DEAD (2 bases: R6 pre-shaping + R28 shaping). Card stays.

**Related rounds**: [[r06_depth-boost]], [[r19_reward-shaping]], [[r13_efficiency-insight]]
See map: [[rounds_index]]. Overview: [[online_rl_sprint_round_log]].
