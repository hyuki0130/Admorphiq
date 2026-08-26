---
name: project_online_rl_baseline
description: "Deployed online-RL card's honest RHAE baseline = full-25 mean game_score 0.0051 (14/25 clear, mostly L1); depth is the ceiling; learner saturated to exploration tweaks"
metadata:
  node_type: memory
  type: project
  originSessionId: c7e91ecf-c8c0-4c3c-bd62-4722ff123df5
---

Measured 2026-07-02 (R17, scripts/rounds/R17/SUMMARY.txt). The committed online-RL card (the
deployed general spine, KaggleOnlineRLAgent) scores **full-25 mean game_score = 0.0051** (seed1
@3000, 14/25 games clear >=1 level). This is the honest RHAE proxy-leaderboard number — any future
round must beat it.

**Why so low: DEPTH is the ceiling.** RHAE weights/squares deep levels, and we clear mostly LEVEL 1.
A perfect L1 clear caps a 6-level game at ~0.048 (best games: SP80 0.0476, R11L 0.040, LP85 0.028;
the other ~11 cleared games near 0). To move the score we must clear DEEPER levels efficiently, not
clear more L1s.

**The learner is SATURATED to exploration tweaks.** SEVEN rounds that perturbed exploration/
action-selection all failed: R5 planning-override, R6 depth-boost, R9 additive-planning, R10
object-state-hash, R14 noop-suppress, R15 dead-action-prune, R16 object-click-prior (net-regressed
the 9-subset). Only non-exploration levers moved anything (R8 budget = small depth). CONCLUSION:
local perturbation can't improve this learner; gains need STRUCTURE (object-centric world model +
planning) or a stronger learner — not another exploration tweak.

**One kept hint:** R16's object-click prior got CD82 (0.0004->0.0074) and M0R0 to LEVEL 2 — the only
L2 clears ever seen on these games. It net-regressed the 9-subset *efficiency*, but was judged on
the wrong metric; whether it helps the FULL-25 TOTAL (via depth) is the open question. Depth is the
real lever. Relates to [[feedback_online_rl_is_the_spine]], [[feedback_measurement_discipline]],
[[project_general_direction_worldmodel]].
