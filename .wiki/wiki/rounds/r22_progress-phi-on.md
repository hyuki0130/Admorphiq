---
title: R22 — progress phi on
type: round-log
round: R22
axis: reward-shaping
keywords: [progress-potential, phi-enabled]
verdict: NULL (no gain vs R19 card, within noise)
commit: none
date: 2026-07-02
---

# R22 — progress phi on

> Re-running with RL_PHI_PROGRESS_W=0.5 actually tested the progress potential: 0.0133 ~= the R19 card's 0.0134, within noise — progress-Phi adds nothing and the code was reverted.

**Axis**: reward-shaping · **Verdict**: NULL — 0.0133 ≈ R19 card 0.0134 (within noise); progress-Φ@0.5 adds nothing; code reverted
**Keywords**: progress-potential, phi-enabled

Re-run R21 code with RL_PHI_PROGRESS_W=0.5 to actually test the progress potential vs the R19 card (0.0134).

**Related rounds**: [[r21_progress-phi-off]], [[r19_reward-shaping]]
See the map: [[index]]. Deployed-card lineage + reliable metric: [[../lessons/online_rl_sprint_round_log]].
