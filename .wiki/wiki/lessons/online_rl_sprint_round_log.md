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

## 2026-07-04 — ⚠️ R29 TRANSFER RECKONING: judge everything warm-start OFF from now on
The card warm-starts from bc_policy_v6.pt (public-25 gold). warm-start OFF = 0.0014 vs ON = 0.0134
on the 9 PUBLIC games (which BC was trained on = max-favorable). BC = 0% transfer to the 110 private
(measured). So the card's real private number ≈ 0.0014, and ~90% of every score in this log is
public-gold inflation that does NOT transfer. THE RELIABLE METRIC IS NOW: 9 games @3000 3-seed with
RL_NO_WARMSTART=1 (transfer-honest, from-scratch ~0.0014 baseline). Optimizing warm-start-ON public
scores is proxy-gaming — banned. Real work = raise the from-scratch general learner, or find a prior
that transfers to UNSEEN games (public-gold BC does not).

## 2026-07-04 — R30: shaping does NOT transfer (confirms the reckoning)
warm-start OFF + shaping OFF = 0.0015 ≈ R29 (shaping ON, warm-start OFF) = 0.0014. R19 shaping's win
needed the BC warm-start; from scratch it is inert. TRANSFER-HONEST BASELINE ≈ 0.0015 and no sprint
micro-lever moves it. The reactive novelty CNN from scratch clears mostly L1 at 10-100x human actions.
A real private gain needs a NEW CAPABILITY. Candidates NOT yet tried from-scratch: (a) a warm-start
prior that transfers to UNSEEN games (procedural/self-play pretrain, or a game-agnostic change-seeking
prior) — NOT public-gold BC; (b) re-test R8 budget from-scratch (only plausibly-transferable lever);
(c) a learned neural forward model (big; R24 warns on convergence). Decision point — surfaced to user.

## 2026-07-04 — DIRECTION DECISION (user): learned NEURAL forward model + planning
After the R29/R30 reckoning (transfer-honest baseline ~0.0015, all micro-levers warm-start-dependent),
user chose: build a LEARNED NEURAL forward model. Design targets the two named walls:
- Beats STATE-UNIQUENESS: neural model generalizes across near-unique unseen frames (tabular can't).
- Beats ONLINE-CONVERGENCE-BUDGET: keep it SMALL and fast by predicting a CHANGE-DELTA / change-mask
  (not full pixels), SEPARATE from the policy net, so it converges within the per-game budget.
- Used for SHORT-HORIZON PLANNING (rollouts scored by predicted change/novelty/goal-proximity) → cut
  actions-to-clear (the RHAE efficiency lever, R13).
- JUDGED TRANSFER-HONEST: warm-start OFF (RL_NO_WARMSTART=1) is the metric now, baseline ~0.0015.
Rounds R32+. Env-gated OFF by default (regression guard). This is the "new capability", not a tweak.

## 2026-07-04 — R31: budget also does NOT transfer (warm-start OFF, budget 6000 = 3000 = 0.0014)
From-scratch, budget 6000 = budget 3000 = 0.0014. R8's budget "win" was ALSO warm-start-dependent.
CONFIRMED: EVERY micro-lever (budget, shaping, all others) is inert without warm-start. Transfer-honest
baseline is firmly ~0.0014. Only a NEW CAPABILITY (R32 neural forward model) can move it.

## 2026-07-04 — R32/R32b: neural forward model beats state-uniqueness but hits GOAL-ABSENCE wall
Neural change-mask forward model (18.7K params) makes planning FIRE on unseen frames (unlike tabular
R10/R27b) — state-uniqueness wall BEATEN. But planning scored by predicted change/novelty does NOT
beat baseline (R32 0.0017 @92% planning crushes novelty→clears 2/9; R32b conf-gate 0.0013 @87%, 3/9).
NEW NAMED WALL #3 — GOAL-ABSENCE: the model predicts WHAT changes, not WHICH change = level-solved,
so planning is novelty-by-another-name. Forward-model planning is inert WITHOUT goal inference.
=> Next real lever = GOAL INFERENCE (detect level-complete condition), the CLAUDE.md R27 pipeline's
missing piece (offline LLM at discovery, or a heuristic goal detector). forward_model.py kept as an
asset for a future goal-directed planner.

## 2026-07-05 — DIRECTION (user): offline LLM goal inference (R27 정공법)
After R32b named the GOAL-ABSENCE wall, user chose offline-LLM goal inference. Infra confirmed:
Ollama local has qwen3:8b/14b/30b; hypothesis/ module exists. Plan (R33+): at DISCOVERY (a few LLM
calls per game, not per action → fits 9h), Qwen observes the probe frames + observed changes and
emits a STRUCTURED goal spec (goal-type enum + params, e.g. fill-all-color-X / move-player-to-region
/ maximize-count-of-Z). The R32 neural forward model then does goal-directed planning: score rollouts
by predicted GOAL-PROXIMITY (not novelty) → directed toward level completion. Env-gated OFF = card;
judged warm-start OFF (baseline 0.0014). This is the R27 pipeline's missing piece (goal inference).
forward_model.py + the goal spec are the reusable assets. Unit-testable with a deterministic goal
stub; LLM only at runtime.

## 2026-07-05 — R33 (goal-directed planning) built; blocked by FORWARD-MODEL ACCURACY (4th wall)
The full R27 pipeline is now BUILT and correct: neural forward model (state-uniqueness ✓, R32) +
structured goal spec + LLM goal inference at discovery (qwen3:8b) + goal-directed planning scoring
rollouts by goal-proximity. 468 tests, planning fires, LLM goal parses. BUT warm-start OFF:
R33a heuristic goal = 0.0013, R33b LLM goal = 0.0013, = baseline 0.0014. Better goals don't help.
NAMED WALL #4 — FORWARD-MODEL ACCURACY: a small from-scratch model can't predict rollouts accurately
enough within the per-game budget for lookahead to beat reactive novelty. Giving a correct GOAL is
useless if the model can't predict which action moves toward it.

### GRAND SUMMARY after ~35 rounds (transfer-honest, warm-start OFF baseline ~0.0014)
NOTHING beats 0.0014 from scratch. Four named walls: (1) state-uniqueness [neural fwd model beats it],
(2) online-convergence-budget [big nets fail], (3) goal-absence [goal spec+LLM addresses it], (4)
forward-model-accuracy [the current binding constraint]. Every micro-lever (exploration, reward,
budget, capacity, planning, goal) is inert on the from-scratch learner. The reactive novelty CNN from
scratch clears mostly L1 at 10-100x human actions ≈ 0.0014, and that appears to be the ceiling of
"learn a game from scratch in a few thousand actions with a small net". The public-25 0.0134 was BC
warm-start inflation (does not transfer). Assets built & kept: forward_model.py, planner/goal.py,
planner/goal_inference.py — all env-gated OFF, reusable if forward-model accuracy is later solved
(needs sample-efficiency: better predictor arch, or a transferable pretrained forward model — NOT
public-gold BC). DECISION POINT for the user: the from-scratch online-RL ceiling looks fundamental.

## 2026-07-05 — R34 METRIC RECKONING: we BEAT random; the 0.18 baseline was bogus
Measured random + stochastic on our 9-game harness: BOTH = 0.0000 (27 runs each, clear nothing). Our
from-scratch online-RL (0.0014) therefore BEATS random decisively — it is NOT sub-random. The whole-
night "100x below random" fear came from a BOGUS baseline: the "random 0.18 / top 1.21" figures in the
docs are unverified and impossible on RHAE. Web-verified reality: RHAE top (StochasticGoose) = 12.58%
(0.1258), 2nd = 6.71%; RHAE random ≈ 0.001 (≈ our measured 0.0000). Our harness is faithful. The real
gap is L1-only (~0.035 subset ceiling) vs DEEP-level clears (12.58% team cleared 18 levels). ACTION:
purge 0.18/0.25/1.21 from docs; anchors are random≈0 and top=0.1258. The from-scratch micro-lever
ceiling still stands, but we are ABOVE random and the target (deep-level efficient clears) is clear.

## 2026-07-05 — DIRECTION (user): attack deep levels via forward-model sample-efficiency (R35)
After R34 corrected the framing (we beat random; harness faithful; target = deep clears at ~0.06-0.13),
user chose to attack deep levels head-on. Target wall #4 (forward-model accuracy) via a KEY untested
idea: a FORWARD MODEL may TRANSFER where the BC POLICY did not. BC policy = 0% transfer because the
right ACTIONS differ per game; but a forward model ("action X changes region Y this way") captures
game-agnostic core-knowledge physics (push→move, click→toggle) that could generalize across games.
R35 plan: (1) collect (frame,action,next_frame) transitions from public games via random/exploration
rollouts; (2) PRETRAIN the small change-mask forward model on them; (3) measure held-out change-mask
prediction ACCURACY (train on N games, test on held-out — mirror scripts/_transfer_test.sh) → does the
forward model transfer? (4) if yes, plug the pretrained model into the R33 goal-directed planner and
measure RHAE (warm-start-OFF policy, pretrained forward model). Step 3 is the cheap pivotal test
BEFORE any full RL run. If forward-model accuracy transfers, planning (R33, built) finally has an
accurate model to plan with — the escape from wall #4.

## 2026-07-05 — ARCHITECT SYNTHESIS (decision-grade): scale-up is DEAD by arithmetic; R35 is the pivotal test
Deep re-research (user ralph directive). Architect findings:
1. "Top team ~100k steps/game" is ARITHMETICALLY IMPOSSIBLE: env.step ~60/s (CPU, GPU-invariant) →
   100k × 110 games = 51h of stepping alone vs the 9h budget. Real ceiling ≈ 17k actions/game
   (uniform 295s/game), practical ≈ 8k. Kaggle's RTX 6000 speeds GRADIENTS, not experience.
2. Wall #2 re-verdict: only the gradient-throughput half is a dev artifact. "Scale the card on the
   big GPU" is DEAD: (a) env.step caps experience; (b) RHAE squares away extra actions; (c) R31
   budget 6000=3000 from-scratch; (d) R23 more-gradients-per-action regressed. Expected gain ≈ 0.
3. ONLY unfalsified lever = pretrained TRANSFERABLE forward model (path b): BC policy=0% transfer
   (policy is game-specific) but change-mask DYNAMICS are game-agnostic core-knowledge; R32 proved
   the model fires on unseen frames; R33 planner is built & correct, starved only by wall #4.
4. R35 DECISION GATE (exact): collect ~20-50k transitions, 18/7 game split (mirror _transfer_test.sh),
   pretrain the 18.7K ForwardModel (change-BCE + colour-CE), measure HELD-OUT change-mask F1 vs the
   trivial "predict-no-change" baseline (ARC frames mostly static — report it explicitly).
   F1 ≥ ~0.5 ⇒ path (b) live → plug pretrained model into R33 planner, measure RHAE (target 0.06-0.13).
   F1 ≈ trivial ⇒ kill path (b) cheaply → ship card + optimize discovery/seed-selection.
5. Ship the current card as M1 safety net regardless (already deployed: KaggleOnlineRLAgent, 9c5d207).

## 2026-07-05 — DEEP-RESEARCH CONVERGENCE: the deep-level axis is EXPLICIT GRAPH SEARCH (R36)
Researcher (primary sources: DriesSmit repo code-read, 30-day-learnings blog, arXiv 2512.24156,
arXiv 2605.05138) + architect converge: deep levels are cleared by HUD-MASKED state-graph +
frontier BFS + segment-click reduction (training-free, exact transitions), NOT by reactive policy
learning (StochasticGoose = 2-game brute-force at 100k steps/8h-per-game, impossible on Kaggle) and
NOT by neural forward-model planning (our walls #1/#4 dissolve once the HUD is masked before
hashing — the winners' states RECUR; ours never did because we hashed raw frames). Graph paper:
19 levels in a 4000-STEP constrained run = our budget class. R36 builds it. R35 (neural transfer)
continues as a complementary secondary. Scale-up stays dead (env.step arithmetic).
