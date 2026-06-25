---
type: strategy
kind: frame_only
introduced: 2026-04-22
replaces: interactive_grid_toggle, sprite_cluster_interaction, push_bfs_grid, bfs_framehash
---

# InferentialAgent (strat_inferential_agent)

> Round-6 redesign. The four G1-G4 generic strategies shipped in round
> 5 were "generic" only in the first sense (no hardcoding) — their
> internals were still brute-force search. Round 6 rebuilds them as a
> single five-phase inference agent that learns the game's action
> semantics, identifies entities, infers the goal signal, and
> synthesizes a plan. This aligns with the Chollet framing used by
> ARC-AGI-3: intelligence = efficiency of skill acquisition in novel
> situations.

> See [[lessons/g1_g4_direct_test_20260422]] for why the previous
> design did not survive direct-testing.

## The five phases

### Phase 1 — Observation (action model learning)

Goal: learn what each action does without knowing the game in advance.

Process:
1. Reset env. Snapshot `f0`.
2. For each `aid` in `available_actions \ {0}`:
   a. If `aid` is in 1..5 or 7: reset, press `aid`, snapshot `f1`.
   b. If `aid` is 6: probe a stride-8 grid of `(x, y)` click coords
      (8x8 = 64 cells). Reset before each click.
   Record per-probe: `diff_magnitude`, `diff_mask_bbox`,
   `diff_mask_centroid`, `did_transition` (did `levels_completed`
   advance), `response_locality` ∈ {inert, local, regional, global}.
3. Aggregate into `action_profile`:
   - For each scalar action `aid ∈ 1..5 ∪ 7`, one profile entry.
   - For `aid == 6`, a list of profiles (one per probed coord).

Budget cap: ~100 actions. The observation phase is itself the first
100 of the 500k-action budget — cheap vs the gains.

### Phase 2 — Entity Detection

Goal: tag color clusters with functional roles from action effects.

Process:
1. Flood-fill `f0` into color-indexed clusters (like G2 did).
2. For each cluster, cross-reference with `action_profile`:
   - Moved under a movement action (diff centroid shifted by STEP) →
     tag as **player** candidate. Only the top-1 is `player`.
   - Cluster overlaps the bbox of a click that caused a large diff →
     tag as **executor** candidate.
   - Cluster overlaps palette swatch pattern (small diff, recolored
     cursor region) → tag as **palette**.
   - Cluster is stable AND bordered by distinct color AND in mid-frame
     → tag as **goal-region** candidate.
   - Cluster whose color appears in pairs (≥ 2 clusters same color) →
     tag as **merge-item** candidate.
   - Cluster is big and unmoving → tag as **obstacle/wall**.
3. Return `entity_map` dict with role-keyed lists.

### Phase 3 — Goal Inference

Goal: infer what state change constitutes "level cleared".

Process:
1. Check `action_profile` for any probe with `did_transition = True`.
   If found: compare (frame_before, frame_after). Diff classifies the
   goal:
   - "All cells of color X became color Y" → **paint-fill** goal.
   - "Player centroid reached a goal-region cluster" → **navigation**.
   - "All merge-item clusters merged (count dropped)" → **merge**.
   - "Color histogram changed to match a target pattern" → **sort**.
2. If no transition observed during probing: heuristic fallback.
   - Outlined rectangle of distinct color present but empty → **navigation**
     to that region.
   - Scattered same-color items present → **merge/collect**.
   - Grid of identical cells present → **paint-fill** to dominant target color.
3. Return `goal_signal = {kind, target_color, target_region, tolerance}`.

### Phase 4 — Plan Synthesis

Goal: pick a plan template based on (entity_map, goal_signal) and
execute with reset-replay.

Templates (ordered from most-specific to most-general):

1. **Navigation plan** — goal=navigation + player tagged. BFS over
   player-centroid state with reset-replay; tries directional actions
   until player centroid reaches the goal-region bbox.
2. **Merge plan** — goal=merge + merge-item clusters. Click each pair's
   midpoint, closest-first, re-flood after each click, stop on
   `levels_completed` ↑.
3. **Paint plan** — goal=paint-fill + palette tagged. Click palette
   swatch → click all target cells → click executor if present.
4. **Toggle plan** — goal=paint-fill without palette (lights-out). DFS
   over toggle cells up to depth 6, executor click last.
5. **Fallback plan** — nothing of the above. Dumb frame-hash BFS (what
   the retired `strat_bfs_framehash` was).

On plan success: advance to next level, rerun Phases 1-4 for that
level (frame layout changes between levels).

### Phase 5 — Learning Loop

Goal: don't declare failure on first miss. If Plan N failed to
advance the level:

1. Retry with doubled probe coverage (stride-4 instead of stride-8 for
   ACTION6).
2. If entity_map was sparse (few clusters tagged), run a second
   observation pass after a few no-op / exploration actions to surface
   items hidden behind dynamic entities.
3. If goal_signal was heuristic (no transition observed), try the
   second-best goal hypothesis.
4. Cap learning loop at 3 iterations per level.

## What this is NOT

This is still **not** a full program-synthesis agent. It does not
generalize to hidden rules that require multi-step counterfactual
reasoning ("if I push this box here, then the door opens"). Those
require a learned transition model + planning horizon > 1 step, which
is out of round-6 scope. Round 7+ candidate.

## Falsification

This design is wrong if:

- Probing a 64-cell stride-8 grid still produces `action_profile` too
  sparse to tag entities reliably (measured: goal=navigation picked
  for < 50% of movement games).
- Goal-inference heuristics fail on > 30% of seen envs (measured via
  CD82/FT09/SB26/SU15 direct-test).
- The five-phase pipeline costs > 5% of the Kaggle per-game budget —
  if discovery takes 5000 actions, there's nothing left for planning.

## Observable Signature

The agent is the right pick when at DiscoveryReport time the LLM
cannot decisively pick a single specialised plan from the wiki:

- The env's combined signature (avail × probe_diffs × dir_map ×
  click_responsive_cells) does not match any of the rules in
  `selector.md` rule 1-8.
- Or: the env matches multiple rules ambiguously and the LLM
  prefers a probe-then-decide approach.
- Or: this is the R11+ baseline state where
  `LLM_WHITELIST_ALLOWLIST = {"adaptive_bfs_solver"}` reduces all
  routing to this single entry — the runtime then defers to the
  agent's internal plan-selection (Phase 4).

`adaptive_bfs_solver` is the public alias used in the allowlist;
implementation is `strat_inferential_agent`.

## Falsification Signature

The agent has failed AND another approach is needed when:

- All inner plans return 0 levels AND the agent's outer loop hits
  the `no_progress_streak` cap (currently 12 levels with 0
  progress). Indicates probe / entity / goal classification is
  systematically wrong on the env class.
- Phase 1 (observation) consumes > 5 % of total budget without
  surfacing any tagged entities (see Falsification of the design
  above). Indicates probe stride is too coarse — see
  [[../../lessons/ft09_stride_button_drop_20260423]] for the
  retry-pattern that mitigates this.
- Plans cycle: each outer iteration picks the same `goal["kind"]`
  but the inner plan keeps returning 0. Indicates the goal heuristic
  is locked on a wrong hypothesis with no second-best (Phase 5
  exhausted).

## Tunable Parameters

- `stride` (observation): default 4 in the agent's outer loop
  (`observation_phase(env, stride=4, ...)`). Range 2-8. Smaller
  stride probes more cells at higher cost; FT09-class grid-aligned
  envs need ≤ 4 (see
  [[../../lessons/ft09_stride_button_drop_20260423]]).
- `probe_budget` (observation): scales as
  `max(200, min(600, (budget - used) // 5))` — 1/5 of remaining
  budget capped at 600 actions per level. Effect: late-level
  observations stay cheap.
- `PLAN_BUDGET_CAP` per kind: navigation 10 000 / 30 000
  (sokoban-like), toggle 15 000, merge 12 000, paint_fill 12 000,
  click_then_move 15 000, lights_out 20 000. Effect: budget-cap
  early-bail vs search-ceiling characterisation in
  [[../../lessons/inferential_budget_vs_algo_20260423]].
- Plan iteration order in `_try_plan`: inferred first, then
  siblings in fixed order (navigation, lights_out,
  click_then_move, merge, paint_fill, toggle). Effect: determines
  which specialised plan runs next when the inferred plan misses.
- `level` cap: 12. Effect: outer loop stops after 12 level
  attempts even with budget remaining; tuning higher costs
  observation overhead, lower drops late-game progression.

## Next-Best

This agent is itself usually the next-best when a more specialised
strategy fails. When this agent is the failing plan, candidates are:

- [[bfs_state_space]] (direct, no prefix-awareness) — for
  movement-pure envs where inferential's overhead is not paying for
  itself. Surrenders the multi-level prefix chaining; only viable
  for single-level games.
- A new specialised plan-fn in `inferential.PLAN_FNS` — author it
  via the `.wiki/schema.md` R23c template and add the goal-kind
  detection in `goal_phase` so the new plan auto-routes when its
  signature matches.
- Re-running with a different probe stride (`stride=2`) — quick
  diagnostic before declaring the env unsolvable.

## Related

- [[../../selector]] — dispatch rules, rule 9 (unknown) routes here
- [[../../architecture]] § Wiki-First Routing — why the LLM picks this
- [[../../reasoning/discovery_phase]] — what Phase 1 extends
- [[../../concepts/probe_signature]] — what Phase 1's output formalizes
- [[../../lessons/g1_g4_direct_test_20260422]] — why this redesign is needed
- [[../../lessons/inferential_budget_vs_algo_20260423]] — failure-mode taxonomy
- [[navigation]], [[merge]], [[paint_fill]], [[toggle]], [[lights_out]], [[click_then_move]] — inner plan fns

## Sources

- `src/admorphiq/agent_ensemble.py::strat_inferential_agent` — implementation
- `scripts/probe_inferential_direct.py` — direct-test harness
- `scripts/g1_g4_direct_results.json` — the measurement that triggered this design
