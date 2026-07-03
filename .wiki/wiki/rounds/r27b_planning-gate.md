---
title: R27b — loosened planning gate (+ usage counter)
type: round-log
round: R27b
axis: world-model-planning
keywords: [planning, world-model, transition-table, state-uniqueness, plan-counter]
verdict: FAIL (planned=0 — world-model never predicts; same wall as R10)
commit: none (env-gated, default OFF = card)
date: 2026-07-04
---

# R27b — loosened planning gate + plan-usage counter

**Axis**: world-model-planning · **Verdict**: FAIL (root-cause diagnosed)

Re-added planning with a LOOSENED confidence gate + a plan-usage counter in the TICK line. Result:
**planned=0, fallback=2117** on every game — planning NEVER fired even at 2000+ actions, despite the
loosened gate. game_score 0.0134 = card exactly (novelty fallback ran 100%).

**ROOT CAUSE (decisive, same wall as R10 object-state-hash)**: the online world-model is a
(state-signature, action) → effect table, but ARC frames are near-UNIQUE (counters/moving elements),
so a (signature, action) is essentially never revisited → the transition table is always empty for
the current state → planning has nothing to predict → it can never fire. This is the SAME
state-uniqueness wall that killed R10. A tabular/empirical online world-model CANNOT work in this
domain without a strong state ABSTRACTION that makes signatures recur — and R10 showed the obvious
object-set abstraction doesn't recur enough either.

**Conclusion**: online world-model + planning is DEAD for this agent via the tabular route. A viable
world-model would need a LEARNED (neural) forward model that generalizes across unseen states — a
much bigger build, and R24 showed bigger nets don't converge online within budget. Card stays.

**Related rounds**: [[r10_object-state-hash]], [[r24_bigger-cnn]], [[r19_reward-shaping]]
See map: [[rounds_index]]. Overview: [[online_rl_sprint_round_log]].
