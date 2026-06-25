---
type: strategy
name: navigation
generalizes: yes
implementation: src/admorphiq/strategies/inferential.py::_plan_navigation
dispatched_from: inferential_agent.PLAN_FNS["navigation"]
---

# navigation (plan fn)

> Prefix-aware wrapper around [[bfs_state_space]]. Resumes BFS from
> `_ACTIVE_PREFIX` (the cumulative winning sequence so far) so
> multi-level games can keep solving forward without re-resolving
> level 1 every iteration.

## Applies When

- `goal["kind"] == "navigation"` — Phase 3 of inferential agent
  inferred a player + goal-region structure.
- `avail ⊇ {1..4}` (cardinal moves) OR `avail ⊇ {1..4, 6}`
  (movement-hybrid).
- `_ACTIVE_PREFIX` non-empty on level ≥ 2 (otherwise navigation
  reduces to first-level BFS).

## Algorithm

1. Convert `_ACTIVE_PREFIX` (list of `("act", aid)` /
   `("click", x, y)` tuples) into BFSSolver wire format
   (`int` for dir, `(x, y)` tuple for click).
2. Build `click_coords` from probes with `diff_magnitude ≥ 10`,
   sorted by descending magnitude, top 20.
3. Choose `(max_depth, max_states, time_limit)` from click density:
   - Hybrid (click_coords > 5): (25, 15 000, 60 s).
   - Sparse-click (click_coords ≤ 5): (35, 25 000, 60 s).
   - Dir-only (no click_coords): (50, 40 000, 90 s).
4. R22 chaining loop — repeatedly call `BFSSolver.solve` with
   `prefix = prefix_actions + cumulative_new` and
   `expected_base_levels = base_levels + levels_cleared`. Each
   solve clears the next level; extend `cumulative_new` and loop
   until `solve` returns None or budget / wall-clock exhausted.
5. Replay the full winning sequence once at the end so the env is
   left at the post-plan state. Record `_LAST_WIN_SEQUENCE` for the
   outer loop to extend the prefix.

## Why It Generalizes

- Reads only `action_profile["scalar"]`, `action_profile["click"]`,
  and `action_profile["base_levels"]` — no game-internal access.
- Click coords come from observation probes, not sprite tags.
- Multi-level chaining is purely positional: each `solve` call sees
  the prior winning prefix + current level's BFS expansion.

## Observable Signature

The plan fn is the right pick when at DiscoveryReport time:

- `goal["kind"] == "navigation"` from `goal_phase`.
- Player cluster tagged in `entity_map["player"]` (size > 4, mobility ≥ 2).
- One of: dir-only (`avail ⊇ {1..4}`, no click responsiveness) or
  movement-hybrid (`avail ⊇ {1..4, 6}` with sparse click_responsive).
- Direction-probe uniformity ratio ≤ 2 (consistent with the player
  cluster shifting by similar magnitudes under each direction).

## Falsification Signature

The plan has failed AND should be swapped when after running:

- `levels_cleared = 0` AND `actions ≪ budget_cap` AND `elapsed < 1 s` —
  early-bail (no `avail_scalar` AND no `has_click`, or `_ACTIVE_PREFIX`
  trivially insufficient).
- `levels_cleared = 0` AND `actions ≈ max_states` AND
  `elapsed ≥ time_limit` — search-ceiling (state space exceeds BFS cap;
  see [[../../lessons/sokoban_search_explosion_20260423]]).
- `levels_cleared = 1` followed by another `_plan_navigation` call on
  the next observation cycle that also returns `1` — prefix not
  extending (regression mode of [[../../lessons/prefix_aware_navigation_20260423]]).

## Tunable Parameters

- `max_depth`: 25-50 by click density. Effect: longer paths reachable
  at higher state-expansion cost.
- `max_states`: 15 000-40 000 by click density. Effect: wider state
  space tolerated; affects memory and wall-clock.
- `time_limit`: 60-90 s. Effect: cap on inner BFS wall-clock per
  `solve` call.
- `click_coords` count: top-20 by HUD-masked diff_magnitude. Effect:
  smaller value tightens click branching, larger widens.
- `soft_time_budget`: max(time_limit, 90 s). Effect: caps the chaining
  loop's total wall-clock.
- Per-plan budget cap (set by inferential outer loop): 10 000 normal /
  30 000 sokoban-like.

## Next-Best

When the falsification signature triggers:

- [[click_then_move]] — when click_responsive ≥ 1 high-diff cell after
  HUD mask AND dir probes uniform. Composes click → move 2-3 steps.
- [[merge]] — when entity_phase surfaces ≥ 2 same-color clusters
  within 2R (rare for nav-classified envs but possible if classification
  was borderline).
- Re-probe with `stride = 2` — when dir probes were silent
  ([[../../lessons/ka59_v2_action6_semantic_20260423]]) but ACTION6
  is in `avail`.

## Limitations

- BFSSolver state-space cap (max_states) is the binding constraint on
  Sokoban-like envs (KA59) — state space is combinatorial in
  (player_position, block_set) and naive frame-hashing can't capture
  the structure.
- Multi-player coordination not supported — the plan assumes a single
  movable player cluster.

## Related

- [[bfs_state_space]] — the underlying solver
- [[inferential_agent]] — outer loop that owns `_ACTIVE_PREFIX`
- [[../../lessons/prefix_aware_navigation_20260423]] — R20-R22 history
- [[../../lessons/sokoban_search_explosion_20260423]] — state-space ceiling
- [[../../lessons/inferential_budget_vs_algo_20260423]] — failure-mode classification
- [[../../games/AR25]], [[../../games/M0R0]], [[../../games/DC22]] — clears

## Sources

- `src/admorphiq/strategies/inferential.py:587-699`
- R20 commit `afe6ab8`, R22 chaining-fix commit
- `scripts/probe_inferential_direct.py` — direct-test harness
