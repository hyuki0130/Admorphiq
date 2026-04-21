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

## Related

- [[selector]] — dispatch rules, rule 9 (unknown) routes here
- [[architecture]] § Wiki-First Routing — why the LLM picks this
- [[reasoning/discovery_phase]] — what Phase 1 extends
- [[concepts/probe_signature]] — what Phase 1's output formalizes
- [[lessons/g1_g4_direct_test_20260422]] — why this redesign is needed

## Sources

- `src/admorphiq/agent_ensemble.py::strat_inferential_agent` — implementation
- `scripts/probe_inferential_direct.py` — direct-test harness
- `scripts/g1_g4_direct_results.json` — the measurement that triggered this design
