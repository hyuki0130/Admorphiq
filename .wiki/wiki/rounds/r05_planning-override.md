---
title: R05 — planning override
type: round-log
round: R05
axis: action-selection
keywords: [planning, goal-directed, exploration-override]
verdict: FAIL (regressed 4 stable games)
commit: none
date: 2026-07-01
---

# R05 — planning override

**Axis**: action-selection · **Verdict**: FAIL (regressed 4 stable games)
**Keywords**: planning, goal-directed, exploration-override

Goal-directed planning that OVERRODE novelty exploration. Regressed AR25/FT09/LP85/M0R0. First proof that overriding novelty breaks the learner.

**Related rounds**: [[r09_additive-planning]], [[r19_reward-shaping]]
See the map: [[rounds_index]]. Deployed-card lineage + reliable metric: [[online_rl_sprint_round_log]].
