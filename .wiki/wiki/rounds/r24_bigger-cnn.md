---
title: R24 — bigger CNN capacity (1.5x)
type: round-log
round: R24
axis: model-capacity
keywords: [cnn-capacity, model-width, convergence-speed, online-training, test-time]
verdict: FAIL (0.0019 vs card 0.0134, 7x worse — slow online convergence)
commit: none (knob kept env-off, default=card byte-identical)
date: 2026-07-03
---

# R24 — bigger CNN capacity (RL_CNN_WIDTH=1.5)

**Axis**: model-capacity · **Verdict**: FAIL (decisive, clean 27-run measure)
**Keywords**: cnn-capacity, model-width, convergence-speed, online-training

Widened the online policy CNN's conv channels 1.5x (env RL_CNN_WIDTH, default off = card) to try to
break the ~0.013 depth ceiling. 9 games @3000, 3 seeds:

**mean game_score = 0.0019 vs R19 card 0.0134 (~7x WORSE).** The bigger net clears levels but with
EXPLODED action counts (FT09 2357, R11L 2547, BP35 2457 vs base CNN's 27–453) → near-zero efficiency
under squared RHAE. Only SP80 (43 actions) survived. Root cause: a bigger net does NOT converge
within the per-game online budget, so it clears LESS efficiently, not more.

(Note: an earlier partial read showed 21–24h/game — that was the laptop LOCKING overnight pausing
the process, NOT the CNN. True per-game time at 1.5x is ~850–950s, normal. The score verdict above
is from the clean, screen-lock-prevented 27-run rerun.)

**Decisive finding**: for TEST-TIME online learning, CONVERGENCE SPEED beats capacity. The small
34M default CNN is correct. Raw-capacity "stronger learner" axis is DEAD. Knob kept env-gated OFF
(default byte-identical to the R19 card); no commit needed.

**Consequence / next**: don't grow the net. Remaining structural levers = better USE of the small
net's per-game compute — object-centric world-model + short-horizon planning (CLAUDE.md R27 path),
or the reward/potential axis with proper sweeps (progress-Φ weight, object-prior P_OBJECT) which had
depth hints (R16/R21). Also: efficiency micro-band is ~0.013; the real jump needs reliable L2+.

**Related rounds**: [[r19_reward-shaping]], [[r23_train-convergence]], [[r13_efficiency-insight]]
See map: [[rounds_index]]. Overview: [[online_rl_sprint_round_log]].
