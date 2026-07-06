---
title: R34 — problem-setup / metric re-examination
type: round-log
round: R34
axis: metric-calibration
keywords: [rhae, metric-scale, random-baseline, leaderboard, representativeness, depth-ceiling, calibration]
verdict: reframes the sprint — our 0.0014 is ~RHAE-random (NOT sub-random); "0.18/1.21" baselines were unverified & wrong
commit: measured
date: 2026-07-05
description: Metric reckoning — measured random = 0.0000 on our harness (we beat random); the 0.18/0.25/1.21 anchors were bogus; real top = 12.58%
---

# R34 — problem-setup / metric re-examination

**Why**: after ~35 rounds hit a from-scratch ceiling ~0.0014, a red flag: leaderboard "random ≈ 0.18"
vs our 0.0014 (100x). User asked to re-examine the setup. Researcher report + (pending) random
calibration on our harness.

## Findings (researcher, read-only)
1. **The "random 0.18 / stochastic 0.25 / top 1.21" baselines are UNVERIFIED and wrong-scale.**
   They appear in docs/sprint_m1_architecture, PRE_SUBMISSION_CHECKLIST, submission_strategy_r7 with
   NO source URL. Independently web-verified actual RHAE scores: StochasticGoose (1st, Dries Smit/Tufa)
   = **12.58% (0.1258)**, Blind Squirrel (2nd) = 6.71%. `.wiki/raw/commits.md:20` also records 12.58%
   as the RHAE top. 1.21 is impossible on RHAE (needs every level of every game cleared above human
   efficiency) — a mis-transcribed different metric.
2. **Our harness is FAITHFUL to official RHAE** (score_efficiency.py:92-147 matches methodology;
   only per-level cap 1.0 vs 1.15, irrelevant since we never beat human action counts).
3. **0.0014 is NOT sub-random.** True RHAE-scale random ≈ 0.001 (random clears almost no levels; to
   reach 0.18 you'd need to clear ALL levels of ALL games at ~2.36x human efficiency — impossible).
   We are near RHAE-random, which is expected for from-scratch mostly-L1 clears.
4. **Our 9-game subset is representative, not abnormally hard.** Its ceiling if L1-only-perfect = 0.0354;
   full clear = 1.0. DEPTH is the real ceiling (already known: L1-only caps ~0.048/game).
5. **Realistic target**: top teams 0.06-0.13, achieved by clearing DEEP levels efficiently (18 levels
   for the 12.58% team), NOT by L1 breadth.

## Consequence
The whole-night "0.0014 = we're 100x worse than random" fear was based on a BOGUS baseline. We are at
RHAE-random, and the real gap is L1-only vs deep-level clears. The from-scratch ceiling conclusion
stands DIRECTIONALLY (micro-levers don't move it) but the framing "catastrophically sub-random" was
wrong. ACTION ITEM: purge the unverified 0.18/0.25/1.21 baselines from the docs; use 0.1258 (verified
top) and ~0.001 (RHAE random) as the real anchors.

**Related**: [[r29_warmstart-off]], [[r13_efficiency-insight]], [[r33_goal-directed-planning]]
See map: [[rounds_index]]. Overview: [[online_rl_sprint_round_log]]. MEASURED: random = **0.0000**, stochastic = **0.0000** on our 9-game harness (27 runs each) — random clears NOTHING. Confirms: our from-scratch online-RL (0.0014) clearly BEATS random; we are NOT sub-random. The '0.18 random' baseline is empirically false on the faithful RHAE harness.
