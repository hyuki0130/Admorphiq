---
title: R29 — warm-start OFF (transfer-honest baseline)
type: round-log
round: R29
axis: transfer-honesty
keywords: [warm-start, bc-prior, transfer, public-gold, inflation, from-scratch, private-leaderboard]
verdict: CRITICAL — OFF 0.0014 vs ON 0.0134 (~90% of score is public-gold BC inflation)
commit: none (measurement)
date: 2026-07-04
---

# R29 — warm-start OFF (transfer-honest baseline)

**Axis**: transfer-honesty · **Verdict**: CRITICAL REFRAMING

The deployed card warm-starts the per-game policy from `bc_policy_v6.pt`, trained on PUBLIC-25 gold.
Every prior round measured warm-start ON. R29 measures RL_NO_WARMSTART=1 (from scratch) on the 9
games @3000 3-seed:

**warm-start OFF = 0.0014 vs ON = 0.0134 — a ~10x drop; clears 4/9 vs 8-9/9.**

### Why this is the number that matters
- The 9 test games ARE the public games BC-v6 was trained on → warm-start ON is the MAXIMALLY
  FAVORABLE case (the prior already knows these games).
- Eval = 110 PRIVATE games where BC has 0% transfer (measured, [[project-bc-transfer-ceiling]]).
- So the true private-leaderboard number of the current card is close to the OFF value (~0.0014),
  NOT 0.0134. ~90% of our measured score is public-gold BC inflation that will NOT transfer.
- The entire R5-R28 micro-tuning sprint was largely optimizing a warm-start-inflated public proxy.
  R19 shaping's M0R0→L2, R13's efficiency gains — substantially enabled by the BC prior absent on
  private games.

### Consequence (strategic)
The genuinely transferable target is the FROM-SCRATCH (no-warmstart) learner, currently ~0.0014.
Two honest paths:
1. Improve the from-scratch general learner directly (measure with RL_NO_WARMSTART=1 as the metric),
   OR
2. Obtain a warm-start prior that ACTUALLY transfers to unseen games (BC-on-public-gold does not;
   would need a prior trained for generality, e.g. self-play/procedural pretraining, or a
   game-agnostic "things that cause change" prior).
Do NOT keep optimizing warm-start-ON public scores — that is proxy-gaming (the exact trap CLAUDE.md
warns about). All future RL-spine rounds should be judged with warm-start OFF (transfer-honest).

**Related rounds**: [[r13_efficiency-insight]], [[r19_reward-shaping]], [[r17_full25-baseline]]
See map: [[rounds_index]]. Overview: [[online_rl_sprint_round_log]].
