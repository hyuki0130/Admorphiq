---
title: R20 — shape coef sweep
type: round-log
round: R20
axis: reward-shaping
keywords: [shape-coef-sweep, tuning]
verdict: TUNE (0.1 best)
commit: none
date: 2026-07-02
---

# R20 — shape coef sweep

**Axis**: reward-shaping · **Verdict**: TUNE (0.1 best)
**Keywords**: shape-coef-sweep, tuning

SHAPE_COEF sweep: 0.1 (0.0134) > 0.0 baseline (0.0129) > 0.05 (0.0124). 0.1 is the sweet spot. S5I5 loss is coef-independent (its own flakiness).

**Related rounds**: [[r19_reward-shaping]], [[r22_progress-phi-on]]
See the map: [[rounds_index]]. Deployed-card lineage + reliable metric: [[online_rl_sprint_round_log]].
