---
title: R13 — efficiency insight
type: round-log
round: R13
axis: measurement insight
keywords: [efficiency, game_score, RHAE, depth-ceiling]
verdict: KEY INSIGHT
commit: 00b3ae4
date: 2026-07-01
---

# R13 — efficiency insight

> Inspecting real RHAE game_score showed clears run 4-60x over human action count into near-zero scores — efficiency dominates and depth is the ceiling (L1-only caps ~0.05/game).

**Axis**: measurement insight · **Verdict**: KEY INSIGHT · **Commit**: `00b3ae4`
**Keywords**: efficiency, game_score, RHAE, depth-ceiling

Inspecting actual RHAE game_score: clears are 4-60x over human action count -> near-zero scores. EFFICIENCY dominates; DEPTH is the ceiling (L1-only caps ~0.05/game).

**Related rounds**: [[r17_full25-baseline]], [[r19_reward-shaping]]
See the map: [[index]]. Deployed-card lineage + reliable metric: [[../lessons/online_rl_sprint_round_log]].
