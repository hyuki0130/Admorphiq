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
