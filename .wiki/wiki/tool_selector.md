---
title: Tool selector — observable frame signature → which algorithm to run FIRST
type: reasoning
keywords: [tool-selector, first-pick, observable-signature, graph-frontier, cnn-rl, world-model, paint-flood, de-aliasing, dead-signature, orchestrator]
date: 2026-07-08
description: The local LLM's decision table — map what you OBSERVE in the first frames to the FIRST tool to run, with how-to-use, falsification (when it's failing → switch), and next-best. Perfect first pick within the tight budget.
---

# Tool selector (perfect first pick for the runtime LLM)

You are the brain. These are your hands. Pick the FIRST tool from what you OBSERVE — do not
guess. Run it; if its falsification signature appears, switch to its next-best. Every tool is
generic (triggers on frame features, never game identity).

## Decision table (observe → run first)

| If you observe … | Run FIRST | Because |
|---|---|---|
| HIGH `avatar_mobility` — a small object TRANSLATES under directional actions (walls block) | **graph-frontier BFS** | navigation/state-space; the exact transition graph + shortest-path frontier clears it (our 18/25 engine). Beats paint_flood whenever avatar_mobility is high EVEN IF avg_changed_cells is large (R53 probe: ar25 mis-routed to paint without this signal) |
| A click (ACTION6) FILLS a connected region with one color (flood); goal is a color/pattern | **paint-flood tool** | plan clicks to fill toward the target coloring |
| Same frame + same action gives DIFFERENT next frames (a counter/timer/off-screen thing) | **de-aliasing state hash** → then graph-frontier | the frame hides state; de-alias so the graph stops corrupting (no M1 winner does this) |
| Transitions look learnable AND a monotone progress measure exists (count/order/fill) | **executable world model + goal planning** | synthesize predict_next_frame, roll out toward the goal measure |
| Reactive/timing game, dense small changes, steering an object under pressure | **CNN-RL online learner** | test-time RL adapts a reactive policy per game |
| ANY game, always on | **dead-signature prior** | stop re-probing action classes that never change anything → saves actions (efficiency) |

## Per-tool: when to use / falsification / next-best

### graph-frontier BFS  ([[rounds/r36_graph-frontier-bfs]])
- **Observable signature**: discrete state changes; a movable avatar; repeatable frames.
- **How to use**: let it build the transition graph and walk promising frontiers by tier.
- **Falsification**: `recent_distinct` collapses to 1–2 while `bfs_fail/random` climb, or the same
  (frame,action) yields different next frames → the graph is aliasing; switch.
- **Next-best**: de-aliasing state hash (partial observability) or the world-model tool.

### paint-flood tool  (`src/admorphiq/tools/paint_flood.py`; perception core built + verified)
- **Observable signature**: an ACTION6 click turns a background region into one color
  (measured su15: `0→5`, 30–50 cells/click); palette small; static between clicks.
- **How to use**: segment target vs filled; choose click points that flood uncovered target cells.
- **Falsification**: clicks stop changing the fill fraction, or fill overshoots the target.
- **Next-best**: executable world model (learn the exact fill rule) then plan.

### de-aliasing state hash  (US-11; novel, no M1 winner has it)
- **Observable signature**: identical visible frame + same action → different outcome (hidden
  timer/off-screen entity). Diagnostic: high nondeterminism under frame-hash (dc22/g50t/wa30/sc25).
- **How to use**: augment the node hash for detected-aliased nodes with a bounded action-history
  k-gram so true-states separate; then run graph-frontier.
- **Falsification**: state count explodes (every step a new node) → the augmentation is too wide.
- **Next-best**: shrink the k-gram; or CNN-RL if the game is reactive.

### executable world model + goal planning  ([[rounds/r52_ewm-integration]])
- **Observable signature**: deterministic transitions learnable from ~tens of probes; a clear
  progress measure (object count / ordering / fill / on-target).
- **How to use**: synthesize predict_next_frame from your own observations (adaptive configs,
  train-fit select); roll out candidate actions toward the goal measure.
- **Falsification**: train-fit stays < ~0.8, or planning picks moves that don't raise the measure.
- **Next-best**: graph-frontier (cheap exhaustive) or CNN-RL.

### CNN-RL online learner  ([[rounds/r36_graph-frontier-bfs]] era spine)
- **Observable signature**: reactive/timing dynamics, dense small frame changes, sparse level reward.
- **How to use**: online test-time RL (fresh per game, reset per level).
- **Falsification**: no level cleared after the convergence budget; reward flat.
- **Next-best**: graph-frontier or world-model.

### dead-signature prior  (US-12; always-on efficiency)
- **Observable signature**: an action class repeatedly produces no hash change.
- **How to use**: deprioritize that class within its tier (never remove; one change revives it).
- **Falsification**: none — it only reorders; a wrong guess costs one probe.
- **Next-best**: n/a (composes with every tool).

## Notes for the orchestrator
- Prefer the CHEAP tools first (dead-signature always; graph-frontier for movement) — they cost
  few actions and the squared-efficiency metric rewards short solutions.
- Reserve the LLM-heavy tools (world model, code edits) for where cheap tools plateau.
- Maximize tool COVERAGE: the more well-characterized algorithms here, the more games get a
  correct first pick. Add a row + a per-tool block whenever a new generic tool is built.

**Related**: [[architecture_self_improving_agent]] (the 3-layer brain/hands/knowledge harness),
[[lessons/top_solutions_survey_20260708]] (baselines to beat).

## Measured note (2026-07-08): paint_flood ≠ su15 live mechanic
Built `paint_flood` tool + `PaintFloodAgent` (LLM-free) and benched on su15: 0/9. Diagnosis
(300 live steps): the flood mechanic is NEVER detected live (fill_color stays -1) even with
background-centroid probing — so su15's `0→5` transitions in the OFFLINE dataset are a side-effect
of a different mechanic (historical "vacuum/merge"), NOT click-to-fill. The paint_flood tool is a
valid generic primitive (detects/rejects flood correctly on synthetic + offline data) but su15 is
the WRONG target for it. Lesson: a transition-diff color-flip pattern (0→C) does NOT by itself
prove a click-to-fill mechanic — verify the tool ELICITS the effect LIVE before trusting it.
su15 needs its true mechanic reverse-engineered (a distinct tool). Do not keep tuning paint_flood
against su15.
