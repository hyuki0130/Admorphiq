---
title: R36 — HUD-masked state graph + frontier BFS (the deep-level axis)
type: round-log
round: R36
axis: explicit-graph-search
keywords: [state-graph, hud-masking, frontier-bfs, segment-clicks, training-free, deep-levels, transfer]
verdict: BUILDING (convergent optimal plan from deep research)
commit: pending
date: 2026-07-05
---

# R36 — HUD-masked explicit state graph + frontier BFS

**Why (deep-research synthesis, 2026-07-05)**: ALL deep-level winners use explicit-graph search, not
reactive policy learning:
- Blind Squirrel (2nd, 6.71%): state graph + loop-pruning + value-ranked BFS → 13 levels.
- arXiv 2512.24156 (Graph-Based Exploration): **HUD-masked frame hash** (masks status bar/counter
  BEFORE hashing → states RECUR → finite graph) + exact observed edges + **frontier shortest-path
  BFS** + **segment-based ACTION6 reduction** (5 salience tiers, not 4096 coords). Training-free.
  **Median 30/52 levels over 6 games; 19 levels in a 4000-step constrained run** — our budget class.
- Executable-WM (32.58%, best): exact coded transitions + planning; bottleneck = planner, not model.
- StochasticGoose (1st, 12.58%): 18 levels but from ONLY 2 brute-forceable games, ~100k steps/game,
  8h/game preview budget (impossible on Kaggle 9h/110); author: "not a long-term answer".

**Why this dissolves our walls**: wall #1 (state-uniqueness) and #4 (forward-model accuracy) both
came from hashing near-unique RAW frames. HUD-masking makes states recur → the transition model is
the OBSERVED GRAPH (exact, free, no learning, no accuracy question). Wall #3 (goal): frontier BFS
needs no goal until one is seen; once a score-increase transition is found, shortest-path replay.
Training-free → inherently transfer-honest (no warm-start question at all).

**Existing assets to build on**: agent_graph.py (GraphAgent), planner/state_graph.py,
planner/graph_explorer.py, bfs_solver.py, R12 HUD-masking experience (inferential observation),
FrameAnalyzer segmentation, R33 goal/planner infra.

**Plan**: build a harness-contract agent (--agent graph_frontier): (1) HUD/animated-cell detection →
masked-frame hash; (2) graph of observed exact transitions; (3) frontier-driven shortest-path BFS;
(4) segment-based click candidates; (5) on level-up keep mechanism, fresh graph. Measure on the
9-game subset + full-25 vs from-scratch baseline 0.0014 (training-free = transfer-honest by design).
R35 (neural forward-model transfer test) proceeds in parallel as a complementary question.

**Related**: [[r34_metric-reexamination]], [[r32_neural-forward-model]], [[r10_object-state-hash]],
[[r12_clear-rate-stable]]. See map: [[rounds_index]]. Overview: [[online_rl_sprint_round_log]].

## R36 v1 measurement (2026-07-05 17:24) — implementation defect + a game-changing side discovery
- v1 RESULT: mean 0.0000 @3000 AND @8000 (identical); only M0R0/R11L clear L1, full budget burned.
  vs the paper's 19 levels @4000 steps → an IMPLEMENTATION defect (graph/BFS/masking), not the axis.
  Debugging (R36b), not discard — external evidence for the axis is strong.
- 🚨 SIDE DISCOVERY THAT CHANGES THE BUDGET MATH: 3000 actions completed in 1-6 SECONDS → the
  OFFLINE arcengine env.step is ~1000+/s, NOT ~60/s (that figure was the networked engine; our
  530s/game online-RL runs were dominated by CNN training, not stepping). Kaggle 9h/110 games =
  295s/game ⇒ a TRAINING-FREE agent can afford ~100k+ actions/game — the graph paper's 8h-class
  budget is actually FEASIBLE on Kaggle. The architect's 17k-ceiling arithmetic applied only to
  training-heavy agents. R36's upside is much larger than assumed.

## R36c/R36d progress (2026-07-05 18:28)
- R36c (region-bbox masking, salvaged from a session-limit-killed worktree +151 lines): **masking now
  WORKS** — GF_DEBUG on SP80 shows 189 distinct states recurring (vs 1-per-step before), masked≈700
  cells (counter region + dilation). But clears DROPPED to 1/9: a new stall surfaced.
- MEASURED STALL: call 500→1000 adds only +1 state/+15 edges with 175 frontier states available and
  bfs_fires frozen at 55 → the agent loops instead of reaching the frontier. Suspects: BFS
  unreachability with failure-caching, ping-pong fallback, click-action keys not quantized (every
  centroid shift = new action identity), mask growth churning hashes.
- R36d (fresh agent) fixing the stall; acceptance = SP80 L1 + ≥4/9 L1 + ideally an L2.

## R36d SUCCESS (2026-07-05 18:44, commit 5e4665d) — first transfer-honest improvement of the sprint
Stall fixed (self-absorbing sink + post-masking state explosion). 9-subset @3000: **mean game_score
0.0055, 4/9 L1 (CD82 342a, M0R0 228a, SP80 844a, R11L 14a→0.0476 ≈ its L1 cap)** vs online-RL
from-scratch 0.0014 — **4x, training-free** (no warm-start inflation possible). Masked-state
recurrence + frontier BFS demonstrably work. R37 measuring budget upside (@8000/@30000) + full-25.

## R37/R37b (2026-07-05 18:55) — budget upside + L2 BREAKTHROUGH
- R37 full-25 @8000: **8/25 clear L1** (adds LP85/TN36/VC33), mean 0.0020 transfer-honest.
  @30000 initially identical to @8000 → traced to GF_GIVEUP default 8000 capping internally.
- **R37b (GF_GIVEUP=30000 @30000): CD82 reaches L2 (342+26,965 actions) and VC33 reaches L2
  (954+12,389)** — the graph agent BREAKS the L2 wall that no online-RL configuration ever did.
  Depth scales with budget exactly as the reference paper showed. Scores still tiny (deep clears
  are slow → squared efficiency ≈0) — efficiency of deep discovery is the next axis (salience
  tiers, better frontier prioritization).
- STRATEGIC: Kaggle gives ~295s/game ≈ 100-300k actions for a training-free agent (env.step
  ~1000+/s offline). The graph axis owns that regime. DECISION: deploy graph_frontier as the
  submission agent (transfer-honest 9-subset 0.0055 vs online-RL from-scratch 0.0014; L2-capable;
  zero warm-start inflation). Online-RL card retained as an alternative.

## R38 (2026-07-05 21:29) — salience tiering: modest safe win
Tiered click candidates (GF_TIER_PRIORITY=1): TN36 L1 862→145 actions (6x, score 0→0.0017); all else
identical (deterministic); CD82/VC33 L2 intact; deep mean 0.0062→0.0064; quick profile unchanged.
Promise-frontier + tier-gate implemented but DEFAULT OFF — measured to lose deep clears when on.
Open lever: L2 discovery cost (CD82 26,965 / VC33 12,389 actions) untouched by local tiering.

## R39 (2026-07-05 22:42) — sticky mask + area-cap: CN04 new L1, VC33 L2 7.5x faster
Top failure class across the 17 non-clearing games = mask churn / over-masking. Fix (sticky trusted
mask + region area-cap, default on): CN04 0→L1(815a); VC33 L2 954+12389→173+1654 (7.5x); TN36
145→72a; SP80 844→442a; CD82 L2 intact; quick 5/9. Only M0R0 mildly slower. 9-game deep set now
clears 11 levels total. Open: CD82 L2 still 26,965a (different blocker); L3 not yet reached anywhere
(VC33 has 28k spare budget after L2 — L3 blocker worth a look); remaining 15 non-clearing games.

## R40 (2026-07-05 23:16) — honest negative + FIRST L3 (budget confirms deployed depth)
Diagnosis: VC33 L3 / CD82 L2 are NOT defects — "healthy graph, goal genuinely far" (VC33 L3 =
combinatorial toggle+reshuffle; CD82 L2 = large productive space, zero prunable waste). The
disruptive-action-demotion lever probed byte-identical (no gain) → discarded per no-dead-weight.
MILESTONE: **VC33 clears L3 @60k (173+1,654+55,209 actions)** — first L3 ever; within the deployed
Kaggle budget class (MAX_ACTIONS=100k). Dev 30k probes UNDERESTIMATE deployed depth. Open: blockers
are now "goal genuinely far" → goal-DIRECTED frontier ranking (R33 score_goal on actual frontier
frames — no forward model needed in the graph context) is the designed next lever (R41).

## R41 (2026-07-06 00:00) — goal-ranked frontier: real but class-dependent → default OFF
GF_GOAL_RANK=1 wins on paint/click (CD82 L2 −47%, VC33 L3 −31%) but regresses navigation (M0R0
level lost); 3 configs tried. Ships default OFF (documented lever; future: per-game-type gating via
goal-type inference). PLATEAU GATE: R40 (honest negative) + R41 (default-OFF) = 2 consecutive rounds
without a default-config improvement → per the ralph PRD, the current card is at its near-term
ceiling. Proceeding to FINAL full-25 measurement at deployed budget + architect verification.

## R42 (2026-07-06 12:29) — adaptive pool-downshift: TU93 0→L3 (verified)
Per-level hash-pool downshift on collapse signatures (default on). TU93 — the wall that beat every
online-RL round — clears THREE levels (8199+682+3643 @30k). Zero regression. Build-agent's S5I5/SB26
claims did NOT reproduce (0/3 retries; possibly env-knob leakage in its runs) — kept in remaining
set. Remaining 9: DC22, G50T, KA59, RE86, S5I5, SB26, SC25, SU15, WA30. Cleared now 16/25.

## R43 (2026-07-06 12:58) — diagnosis of the 9 blocked games (honest 0 new clears) + ACTION7 fix
Full GF_DEBUG diagnosis table (see commit message + agent report). Blocker classes: (a) DC22
pool-tension (jitter-absorb vs small real movement); (b) S5I5/SB26 1-cell/action moving
counter/cursor breaks pool=1 recurrence; (c) KA59/SB26 semantic goals (sokoban/sort) unreachable by
undirected BFS; (d) SU15/WA30/RE86 sticky over-masking (mask ~1700-2000 cells) erases click targets
or blocks downshift; (e) G50T/SC25 pure state-explosion/goal-far. 7 lever configs all 0 — these need
REWORK not knobs: ① monotone-moving-band mask (detects counters/cursors specifically), ② object-
segmented state hash (player position as grid cell), ③ goal-type-aware planning. ACTION7
movement-gated fix landed (real bug; SU15 prerequisite). 16/25 stands.

## R44 (2026-07-06 13:41) — moving-band mask landed (infrastructure; prerequisite for ②③)
Drift-coherence detector masks 1-cell/action counters/cursors. S5I5/DC22 recurrence restored
(330→64 states); zero loss. No new clears yet — semantic sinks remain beneath (slider/sort/sokoban
= levers ② object-segmented hash, ③ goal-aware planning). 16/25 stands.

## R45 (2026-07-06 14:26) — object-segmented hash landed (lever ②; infrastructure)
3rd downshift rung: object-multiset key gives jitter-absorption + movement-sensitivity together.
Recurrence + edge determinism achieved on the explosion class; zero loss. Still 0 new clears —
residual barriers: goal-distance, stochasticity, large-object centroid merging. Both mask/hash
levers (①②) now landed as substrate; the remaining blocker set is SEMANTIC → lever ③ goal-aware
planning is the last of the three. 16/25 stands.

## R46 (2026-07-06 15:44) — lever ③ landed (infra); frontier-ranking honest OFF; taxonomy levers EXHAUSTED
Semantic measures (order/on-target/count) + inference + stall-gating built & tested; ranking OFF
(0 new + CD82 regression when on). VERDICT after R43→R46: all three taxonomy levers are landed as
substrate, yet the 9 games stand — their blocker is the PARADIGM: undirected/heuristic graph search
cannot cross semantic puzzles (sokoban push-planning, sort sequences, slider combinatorics). The
literature's answer at this exact wall = executable world model + directed planning (arXiv
2605.05138, 32.58%, 106/209 levels). That is a NEW BUILD (LLM-written per-game transition rules +
plan search), not a graph tweak. 16/25 · 21 levels stands as the honest graph-paradigm result.

## R47 (2026-07-06 16:35) — measure-expansion OFF-ship + KA59 VERIFIED = 17/25
Independent verification: KA59 clears at BASELINE @30k (18,785a — the "remaining 9" list was an @8k
probe artifact; substrate levers made it reachable). SC25 clears 2/2 with GF_MEASURE_EXPAND=1
(28,696a) but the knob breaks KA59 → default OFF, SC25 = documented conditional lever. TU93 L3 now
9.2k total (was 12.5k). **17/25 verified · 23+ levels.** Remaining 7 (+SC25 conditional): DC22,
G50T, RE86, S5I5, SB26, SU15, WA30 — the semantic core. In-paradigm exploration complete.
