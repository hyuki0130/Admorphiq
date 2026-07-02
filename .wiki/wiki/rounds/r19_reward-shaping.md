---
title: R19 — reward shaping
type: round-log
round: R19
axis: reward-shaping
keywords: [potential-based, reward-shaping, novelty-potential, depth, SHAPE_COEF]
verdict: KEEP (FIRST WIN)
commit: 2c93fc1
date: 2026-07-02
---

# R19 — reward shaping

**Axis**: reward-shaping · **Verdict**: KEEP (FIRST WIN) · **Commit**: `2c93fc1`
**Keywords**: potential-based, reward-shaping, novelty-potential, depth, SHAPE_COEF

Potential-based shaping F=gamma*Phi(s')-Phi(s), Phi=novelty, COEF=0.1. FIRST depth lever: M0R0/CD82->L2, FT09 4x efficiency; mean 0.0129->0.0134. The reward-signal axis works where action-selection didn't.

**Related rounds**: [[r08_budget-depth]], [[r13_efficiency-insight]], [[r20_shape-coef-sweep]]
See the map: [[rounds_index]]. Deployed-card lineage + reliable metric: [[online_rl_sprint_round_log]].
