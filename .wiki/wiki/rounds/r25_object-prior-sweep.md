---
title: R25 — object-prior P_OBJECT sweep
type: round-log
round: R25
axis: exploration-prior
keywords: [object-prior, objectness, action6, click-prior, p-object, sweep, depth]
verdict: FAIL (sweep closed: P=0.7→0.0051, P=0.3→0.0060, both < card 0.0134)
commit: none (env-gated, default OFF = card)
date: 2026-07-03
---

# R25 — object-prior P_OBJECT sweep

**Axis**: exploration-prior · **Verdict**: sweeping (tune-before-discard)
**Keywords**: object-prior, objectness, action6, click-prior, p-object, depth

Re-added the object-centric ACTION6 click prior (reverted after R16/R18) as env RL_OBJECT_CLICK_PROB
(default 0.0 = OFF = card). Sweeping P_OBJECT because R16 hinted depth (CD82/M0R0 → L2).

- **P_OBJECT=0.7** (R25): mean game_score 0.0051 < card 0.0134. Too aggressive — FT09 hit L2 on one
  seed (0.0476) and CD82 0.0117, but M0R0/CN04/R11L collapsed and variance is high. Over-biasing
  clicks to objects starves the novelty exploration that already clears these.
- **P_OBJECT=0.3** (R25b): mean 0.0060 — still << card 0.0134. SWEEP CLOSED: object-prior net-hurts
  at both 0.3 and 0.7. Biasing clicks to objects starves the novelty exploration that already clears
  M0R0/CN04/BP35; high variance, lower mean. object-prior axis is DEAD (confirmed over 4 configs incl
  R16/R18). Card stays.

**Related rounds**: [[r16_object-click-prior]], [[r18_object-prior-full25]], [[r19_reward-shaping]]
See map: [[rounds_index]]. Overview: [[online_rl_sprint_round_log]].
