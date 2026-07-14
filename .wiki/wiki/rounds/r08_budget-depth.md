---
title: R08 — budget depth
type: round-log
round: R08
axis: budget
keywords: [budget, max-actions, depth]
verdict: KEEP
commit: 850ee02
date: 2026-07-01
---

# R08 — budget depth

> Raising per-game budget (MAX_ACTIONS 8000) raised depth without regression (LP85 2.33->3.67) — the first non-exploration lever that helped.

**Axis**: budget · **Verdict**: KEEP · **Commit**: `850ee02`
**Keywords**: budget, max-actions, depth

More per-game budget raises depth WITHOUT regression (LP85 2.33->3.67). Set MAX_ACTIONS 8000. First non-exploration lever that helped.

**Related rounds**: [[r13_efficiency-insight]], [[r19_reward-shaping]]
See the map: [[index]]. Deployed-card lineage + reliable metric: [[../lessons/online_rl_sprint_round_log]].
