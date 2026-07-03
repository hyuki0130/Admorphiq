---
title: Online-RL Sprint Round Log (R5–R21+)
type: lesson
status: living
updated: 2026-07-02
---

# Online-RL Sprint — Durable Round Log (narrative overview)

> **🔎 To FIND past work by topic, start at the retrieval map [[rounds_index]]**
> (`.wiki/wiki/rounds/index.md`) — keyword groups → per-round pages. Each round has its own
> page `.wiki/wiki/rounds/rNN_slug.md` with keywords, verdict, commit, and `[[backlinks]]`.
> This file is the NARRATIVE overview + reliable-metric + resume steps; the per-round pages
> are the searchable atoms. Do NOT scan this whole file to find a topic — use the index.

**Purpose**: cross-session memory so a resumed/compacted session does NOT repeat
already-failed experiments. This is the durable mirror of the session-scoped
`.omc/state/sessions/*/progress.txt` (which a NEW session cannot see). Every RL-spine
round appends here with: what was tried, measured result, keep/discard, and the lesson.

**Deployed card**: `src/admorphiq/online_rl_agent.py` — test-time online CNN+RL + count-based
novelty exploration + **potential-based reward shaping (SHAPE_COEF=0.1, committed R19 `2c93fc1`)**.
General (no game_id/title); learns fresh per game; transfers to the 110 private games. Wrapper:
`KaggleOnlineRLAgent` (MAX_ACTIONS 8000). Submission notebook deploys it (R7 `9c5d207`).

**Honest baseline (R17 `0266634`)**: deployed card full-25 mean game_score ≈ **0.005** (14/25 clear
≥1 level, seed1 @3000). DEPTH is the ceiling — mostly L1 clears; RHAE weights/squares deep levels,
so a perfect L1 caps a 6-level game at ~0.048.

## ⛔ DO NOT REPEAT — exploration/action-SELECTION tweaks (8 rounds, ALL failed)
The novelty online learner's action-SELECTION is a TIGHT local optimum. Every attempt to change
WHICH action it picks regressed or did nothing. Do not re-try these:
| Round | Tried | Result |
|---|---|---|
| R5 | goal-directed planning OVERRIDING novelty | regressed 4 stable games |
| R6 | depth-boost / keep-learning-after-levelup | regressed (LP85 depth down) |
| R9 | ADDITIVE goal-directed planning | no gain; diagnosed DC22/TU93 = state explosion |
| R10 | object-centric STATE hashing (novelty key) | no gain (frames rarely repeat exactly) |
| R14 | no-op suppression on (exact frame_hash, action) | byte-identical (exact frames never repeat) |
| R15 | generalized dead-action-type + dead-region pruning | regressed (0.0129→0.0064), lost S5I5 |
| R16 | object-centric ACTION6 click prior (9-subset) | net-regressed 9-subset (but hinted depth) |
| R18 | object-click prior re-tested on full-25 | no gain (0.0047 vs 0.0051 = single-seed NOISE) |

**Corollary lessons**:
- DC22/TU93 are budget-invariant walls (R8: 0/3 @1500/3000/6000). State explosion from moving
  objects; exploration can't crack them and object-state-hash (R10) didn't fix it.
- Single-seed full-25 is NOISE (R17 0.0051 vs R18 0.0047 with top games reshuffled). Use ≥3 seeds;
  deltas < ~0.002 are not signal. Reliable metric = 9 L1-stuck games @3000 3-seed.

## ✅ WHAT WORKED
| Round | Tried | Result | Committed |
|---|---|---|---|
| R7 | deploy online-RL solo (not world-model/ensemble) | transfer-honest | `9c5d207` |
| R8 | more per-game budget | depth ↑ w/o regression (LP85 2.33→3.67); MAX_ACTIONS 8000 | `850ee02` |
| R11/R12 | breadth measurement | 14/25 clear, 12/14 STABLE (3-seed) | measure |
| R13 | RHAE game_score inspection | **EFFICIENCY is the real lever** (clears 4-60x over human → ~0 score) | `00b3ae4` |
| **R19** | **potential-based reward shaping** F=γΦ(s')−Φ(s), Φ=novelty, COEF=0.1 | **first depth lever: M0R0/CD82→L2, FT09 4x efficiency; mean 0.0129→0.0134** | **`2c93fc1`** |
| R20 | SHAPE_COEF sweep | 0.1 best (>0.0 baseline >0.05) | — |

**Key finding**: exploration-SELECTION is saturated, but the **REWARD-SIGNAL axis works**.
Potential-based shaping (policy-invariant, no wiggle-reward) is the one lever that opened DEPTH
(M0R0/CD82 reach L2). Iterate the REWARD/potential axis, not action-selection.

## Open / in progress
- R21: richer potential Φ (progress-potential: novelty + object-structure/frame-change) — measuring.
- Next candidates (reward/structure axis, NOT selection): better Φ; stronger learner (bigger CNN);
  object-centric world-model + planning toward inferred goal (CLAUDE.md R27 general path).

## How to resume
1. Read this log + `memory/project_online_rl_baseline.md` + `memory/feedback_measurement_discipline.md`.
2. Measurements = background shells (survive rate-limit), never inside agents. Fixed convention:
   `scripts/rounds/RN/run.sh` → live `SUMMARY.txt` via `scripts/rounds/aggregate.py`.
3. Reliable metric: 9 L1-stuck games (ft09,m0r0,bp35,cd82,cn04,ls20,r11l,s5i5,sp80) @3000, 3 seeds,
   judged by mean **game_score** (not level count). Beat 0.0134 (R19 card) with no net clear loss.
4. Do NOT re-run the ⛔ list. Iterate the reward/structure axis.

## R21 (2026-07-02) — progress-potential Φ measured OFF-by-default (no signal); re-run as R22
Added composite Φ = PHI_NOVELTY_W·novelty + PHI_PROGRESS_W·progress. But defaults are
PHI_NOVELTY_W=1.0, PHI_PROGRESS_W=0.0 (regression guard = committed behavior), and the R21 runner
did NOT set RL_PHI_PROGRESS_W → progress term was OFF → result BYTE-IDENTICAL to R19 (mean 0.0134,
same per-game actions). Not a discard — the feature was simply disabled by default. R22 re-runs the
SAME code with RL_PHI_PROGRESS_W=0.5 to actually test the progress potential. LESSON: when a new
term defaults to 0 for a regression guard, the measurement runner MUST set the env var to enable it,
else you measure the old behavior.

## 2026-07-04 — "check all possibilities" batch (R25-R28, R27b) ALL FAIL; two structural walls named
Ran the full remaining candidate set in parallel (code) + serial (measure). None beat the R19 card
(9-subset 0.0134 / full-25 ~0.005):
- R25 object-prior sweep (P=0.7→0.0051, P=0.3→0.0060) — starves novelty. DEAD (4 configs w/ R16/R18).
- R26 progress-Φ sweep (w=0.5→0.0133, w=1.0→0.0124) — reward-shaping axis EXHAUSTED (novelty-only best).
- R27/R27b world-model+planning — planning NEVER fires (planned=0): tabular (state-sig,action) model
  has no data for near-unique ARC frames. SAME WALL AS R10. DEAD via tabular route.
- R28 keep-learning-across-levels (0.0121) — new level = different state space; retaining policy hurts.
  Confirms R6 on a 2nd base. DEAD.

### TWO NAMED STRUCTURAL WALLS (why micro-levers are exhausted)
1. STATE-UNIQUENESS: ARC frames are near-unique (counters/motion), so anything keyed on exact/near
   state recurrence fails — tabular world-model (R10,R27b), exact no-op cache (R14). A world-model
   here needs a LEARNED neural forward model that generalizes across unseen states.
2. ONLINE-CONVERGENCE-BUDGET: bigger nets (R24) don't converge within the per-game action budget on
   MPS/CPU — so "more capacity" backfires. The small 34M CNN + novelty + shaping is the practical
   optimum for the reactive policy.
=> Micro-levers on the reactive novelty learner are SATURATED. A real jump needs a learned
generalizing forward model (big, careful build) OR accept the current card and optimize a different
pipeline stage (e.g. discovery/goal-inference, or per-game seed selection at deploy).
