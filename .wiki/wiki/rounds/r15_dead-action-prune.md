---
title: R15 — dead action prune
type: round-log
round: R15
axis: efficiency action-selection
keywords: [dead-action, dead-region, pruning]
verdict: FAIL (0.0129->0.0064)
commit: none
date: 2026-07-02
---

# R15 — dead action prune

> Frame-invariant dead-action-type + dead-region pruning regressed the score by half, losing S5I5 by removing actions novelty was using.

**Axis**: efficiency action-selection · **Verdict**: FAIL (0.0129->0.0064)
**Keywords**: dead-action, dead-region, pruning

Frame-invariant dead-action-type + dead-region pruning. Regressed (halved score), lost S5I5 — removed actions novelty was using.

**Related rounds**: [[r14_noop-suppress]], [[r16_object-click-prior]]
See the map: [[index]]. Deployed-card lineage + reliable metric: [[../lessons/online_rl_sprint_round_log]].
