# R28 — Object-Centric Online World-Model Agent

Status: first bounded deliverable (prototype). Source-of-truth for
`src/admorphiq/world_model_agent.py`.

## Why this exists

The R27 held-out transfer test measured **0% transfer** for behaviour cloning:
a BC policy trained on public gold memorises the 25 preview games and clears
**0 of 7** unseen holdout games (CLAUDE.md "DIRECTION CORRECTION (2026-06-29)",
memory `project_bc_transfer_ceiling`). The leaderboard is **110 PRIVATE unseen
games**, so any agent that learns *only* at dev-time from public gold cannot be
the spine.

The general path (memory `project_general_direction_worldmodel`,
`docs/sprint_m1_architecture_20260625.md` §8) is an agent that does its
learning **at test time, per game** — nothing about the agent's competence is
baked in from public gold, so it transfers by construction. This module is the
first bounded increment of that path.

It is **deliberately distinct** from `general_agent.py`. `GeneralAgent` is an
FSM with hand-built primitive detectors (paint / GF(2) toggle / edge-maze) bolted
on. `WorldModelAgent` instead factors the same idea into the four clean,
separately-testable stages the direction calls for: an explicit `EffectModel`
that is *learned online*, a goal inferred from observation + completion
correlation, and a planner that *searches inside the learned model*.

## The metric shapes the design

Per level `s = min(human/agent_actions, 1)²`, level-index weighted, mean over
games. Squaring means **short solutions dominate**: a level cleared in a small
multiple of the human action count scores well; a brute-force clear in hundreds
scores ≈ 0. Two consequences are load-bearing here:

1. Discovery/probing actions also count against the ratio, so the probe phase is
   **budget-bounded** (`PROBE_BUDGET`).
2. The planner must emit **short** action sequences. Navigation uses shortest-
   path BFS in the learned grid model; interaction is greedy over the *predicted*
   effect, not blind enumeration.

## Hard constraints (repo discipline)

- **No `game_id` / `game_title` branching anywhere.** Every trigger is a
  function of the frame, `available_actions`, and `levels_completed`. Titles are
  invisible on the private eval.
- **No game-internal / sprite-tag reads.** Only the official observation
  (`.frame`, `.state`, `.available_actions`, `.levels_completed`).
- **No placeholders / stubs / dead safety-nets** — everything below is
  implemented.

## Architecture — four stages

### (a) Perception → objects  `segment_objects(layer, background)`

Game-agnostic. The canonical (top) 2-D layer is segmented into 4-connected
same-colour components, excluding the background (most-frequent colour). Reuses
the proven, unit-tested `connected_components` from `general_agent` (the repo's
shared object-extraction primitive); each object is `{color, size, cx, cy,
cells}`. Per-action *effects* on objects are measured by reusing
`perception.frame_analyzer.FrameAnalyzer.analyze_action`, which reports per-colour
centroid translation and changed-pixel counts from a before/after frame diff.

### (b) Online world model  `class EffectModel`

Built **fresh per game** from the agent's OWN probes — no public gold. It is a
compact *abstract* transition model (entity translations + per-action change
statistics), NOT a raw 64×64 predictor. State it learns:

- `move_map: action_id -> (dx, dy)` — the player's pixel shift under each
  movement action, inferred via `infer_direction_map` (the player-vs-cursor
  disambiguator: the colour that translates consistently across the most distinct
  action directions). `player_color` falls out of the same inference.
- `action_stats: key -> ActionStat` — for each simple action (and ACTION6 in
  aggregate) the `(tried, changed, total_pixels, changed_colors)` tallies.
  `change_prob(key)` = Laplace-smoothed `P(frame changes | action)`.
- `click_obs` — per-cell ACTION6 responsiveness, so `responsive_clicks()` returns
  the cells where clicking actually changed the frame.
- `completion_sigs` — recorded each time `levels_completed` increments: the
  action, coord, and the set of colours whose regions changed on that transition.
  This is the **goal-correlation signal** — "what frame-change correlates with a
  level completing". `completion_target_colors()` surfaces it for later levels.

`observe(action_id, coord, before, after, level_up)` is the single online-update
entry point. It can be called for *every* action — discovery probes AND real
plan moves — keeping the model improving the whole game (it recomputes the
direction map from a bounded probe buffer, capped at `_MOVE_PROBE_CAP` so cost
stays O(1) per call).

Prediction surface (what makes it a *world* model, not just stats):
`step_dirs()` quantises `move_map` to unit grid steps, and the planner expands
the abstract player position through them — i.e. the planner *simulates the
learned dynamics*. `predict_player_shift(aid)` exposes the one-step prediction
used for surprise detection.

### (c) Goal inference  `infer_goal(layer, model) -> Goal`

Returns one of three kinds, observation-driven:

- `"navigate"` — a player + a plausible goal region exist (player colour known,
  direction map learned, `pick_goal_cell` finds a target). If a colour was seen
  changing at a *past level completion* and is present now, it becomes the
  preferred `target_color` (completion correlation over the rarest-colour
  heuristic).
- `"interact"` — no navigable player, but the model has observed responsive
  clicks or a high-change action.
- `"explore"` — nothing learned yet; disciplined fallback.

### (d) Search-based planning

- `plan_navigation(layer, model, goal)` — builds the walkable grid
  (`frame_to_cells`, using floor colours the player was seen standing on) and runs
  shortest-path `grid_bfs` from the player cell to the goal cell over the learned
  `step_dirs`. Returns a **short** action-id list. This is BFS *in the learned
  model*: the transition it expands is exactly the learned per-action shift.
- `plan_interaction(layer, model)` — an ordered candidate list (observed
  responsive cells first, then rare-cluster centroids, then frame-changing simple
  actions), consumed greedily by expected change. Short-horizon and online: every
  emitted action feeds back into `EffectModel.observe`.

## Agent FSM and harness wiring

`class WorldModelAgent` exposes the harness contract used by every agent in this
repo and by `scripts/score_efficiency.py`:

- `is_done(frames, latest_frame) -> bool` — stop on `WIN` or action budget.
- `choose_action(frames, latest_frame) -> GameAction` — emit the next action.
- `choose_action_with_data(frames, latest_frame) -> (GameAction, data|None)` —
  thin wrapper returning the ACTION6 `{x, y}` for the official base.

Per call: credit the previous action's observation into the (game-scope)
`EffectModel` **before** any level reset, detect level-up (reset per-level plan
state, keep the model), then dispatch by phase:

```
PROBE   -> probe each available move once + a coarse ACTION6 grid (budget-bounded)
            ; on exhaustion infer goal + build a plan
EXECUTE -> emit the BFS nav plan one action/call; surprise check (observed vs
            predicted player centroid) triggers replan; bail to INTERACT after
            EXECUTE_BAIL actions without a level-up
INTERACT-> greedy over the learned effect model; rotates live candidates,
            rebuilding from the model as the frame evolves
```

Control knowledge (`move_map`, `player_color`) lives at **game** scope and
persists across levels (controls are level-invariant; only the layout changes),
so later levels can replan immediately. Plan/goal/probe state is **per level**.

`scripts/score_efficiency.py::_make_agent("worldmodel")` returns
`WorldModelAgent()`; the run loop is otherwise agent-agnostic.

## What is intentionally NOT in R28 (handed to R29)

- The PyTorch `world_model/` CNN (residual-delta `TransitionPredictor` +
  `ChangePredictor`) is **not trained online** here: a full CNN fit inside the
  ~5-min/game budget is heavy and risky, and the sprint doc §3 mandates an
  *abstract*-state model for planning. R28's `EffectModel` is that abstract model;
  the CNN is the R29 neural upgrade (warm-started from BC) once the symbolic loop
  is proven.
- RL / policy improvement on top (BC as warm-start prior) — R29+.
- Recenter-aware probing (freeing a wall-bound player before re-probing a blocked
  direction, as `GeneralAgent` does) — R28 uses a single bounded sweep.
- LLM goal hypothesis at discovery — the `Goal` interface is the seam where it
  plugs in (it would supply `target_color` / `kind`); not wired in R28.

## Test surface (`tests/test_world_model_agent.py`)

Pure, deterministic, env-free units for each stage: object segmentation, the
online effect-model update (change-prob + move-map inference), goal inference
(all three kinds), and the navigation planner (shortest path over a synthetic
grid). One optional slow live-env smoke, skipped by default.
