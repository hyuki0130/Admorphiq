---
title: R21 — progress phi off
type: round-log
round: R21
axis: reward-shaping
keywords: [progress-potential, phi, off-by-default]
verdict: NULL (measured off)
commit: none
date: 2026-07-02
---

# R21 — progress phi off

> A composite Phi=novelty+progress was added but PHI_PROGRESS_W defaulted to 0 and the runner never enabled it, so the result was byte-identical to R19 — new reward terms must be enabled via env in the runner.

**Axis**: reward-shaping · **Verdict**: NULL (measured off)
**Keywords**: progress-potential, phi, off-by-default

Added composite Phi=novelty+progress but PHI_PROGRESS_W defaulted 0 and the runner didn't enable it -> byte-identical to R19. Lesson: enable new terms via env in the runner.

**Related rounds**: [[r19_reward-shaping]], [[r22_progress-phi-on]]
See the map: [[index]]. Deployed-card lineage + reliable metric: [[../lessons/online_rl_sprint_round_log]].
