---
type: strategy
name: bfs_state_space
generalizes: yes
implementation: src/admorphiq/planner/bfs_solver.py
dispatched_from: strat_bfs_state_space in agent_ensemble.py
---

# bfs_state_space

> Generic breadth-first search over frame-hashed states. Depends only on observable frame + action response. Generalizes across game versions.

## When to use

- Deterministic transitions (pressed action produces same next-frame given same start-frame)
- Small reachable state set (≤ ~500K states)
- Level-up signal is observable (either via `state` change or `levels_completed` increment)

## Algorithm

1. Hash current frame into a compact key (downsample 64×64 → 16×16 + color palette)
2. Initialize BFS queue with current state
3. For each popped state:
   - Try every `available_action`
   - Observe resulting frame; re-hash
   - If already visited, skip
   - If level_up flagged, record path and return
   - Else enqueue
4. Budget-capped (default 500K expansions, 20K actions)

## Why it generalizes

- Uses only `FrameData.frame`, `FrameData.available_actions`, `FrameData.levels_completed`
- No sprite tag reads, no attribute access on game object
- Works on any game where frame = state

## Games cleared on both v1 and v2

| Game | v1 | v2 |
|------|-----|-----|
| AR25 | 2/8 | 2/8 |
| DC22 | 1/6 | 1/6 |
| M0R0 | 2/6 | 2/6 |
| SP80 | 1/6 | 1/6 |

## Limitations

- Slow on games with large state branching factor (e.g. ACTION6 × 4096 coordinates)
- Fails silently when level-up signal isn't coupled to frame state (e.g. TN36 where program is executed asynchronously)

## Observable Signature

The plan is the right pick when at DiscoveryReport time:

- `avail ⊇ {1, 2, 3, 4}` (cardinal directional moves available).
- Direction-probe uniformity ratio ≤ 2 (`max(probe_diffs[1..4]) / min ≈ 1`) → a single mover sprite shifts under each direction.
- `change_topology ∈ {local, regional}` — direction presses cause cell-scale motion, not whole-frame paint.
- `dir_map` populated (R2 derive) — at least three of the four directions classified into distinct cardinal classes.
- Click responsiveness either dead (`click_responsive == 0`) or sparse (1-2 high-diff cells, treated as goal markers).

When `_plan_navigation` (the inferential-agent wrapper around `BFSSolver`) is the entry, the same observable signature applies — `_plan_navigation` is the prefix-aware delegator, `bfs_state_space` is the underlying engine.

## Falsification Signature

The plan has failed AND should be swapped when:

- BFS exits with `actions ≈ max_states` AND `elapsed > 30s` AND `levels_cleared = 0` — search-ceiling, encoding is wrong (frame hash collapses too aggressively or expands too richly).
- All four direction probes report `diff_pixels = 0` (KA59-v2 pattern, see [[../../lessons/ka59_v2_action6_semantic_20260423]]) — movement mechanic deactivated; classification was wrong.
- Plan returns `levels_cleared = 1` then immediately re-returns `1` from a fresh observation cycle (CD82 pre-R20 pattern, see [[../../lessons/prefix_aware_navigation_20260423]]) — prefix is being ignored; engine is re-solving level 1.
- ACTION6 is in `avail` AND click probes show high responsiveness (≥ 3 cells diff ≥ 100) AND BFS exits at `max_depth` — pure dir-BFS misses the click-then-move composition (see [[click_then_move]]).

## Tunable Parameters

The runtime LLM can suggest tuning before swapping plans:

- `max_depth`: 50 (dir-only) / 25-35 (hybrid with click_coords). Effect: deeper reaches longer solutions but multiplies state expansion.
- `max_states`: 15 000 (hybrid) / 40 000 (dir-only) / 25 000 (sparse-click). Effect: bigger cap survives wider games at higher memory cost.
- `time_limit`: 60-90 s. Effect: longer budget when plan is making progress; cap shorter when used as a fallback.
- `click_coords`: top-N by HUD-masked diff_magnitude (N=20). Effect: smaller N tightens the click branching; larger N widens.
- `prefix`: `_ACTIVE_PREFIX` from outer loop. Critical for multi-level. Bypass only if a fresh-from-game-start search is intentional.
- Per-level cap (via `_try_plan` `PLAN_BUDGET_CAP`): 10 000 normal, 30 000 sokoban-like (`merge_items ≥ 3` AND goal=navigation, see [[../../lessons/sokoban_search_explosion_20260423]]).

## Next-Best

When the falsification signature triggers, try (in priority order):

- [[click_then_move]] — if click-responsive ≥ 1 with HUD-masked diff ≥ 10 AND dir actions still produce motion. Composing click → move covers CD82-style hybrids that pure dir-BFS misses.
- [[../../lessons/ka59_v2_action6_semantic_20260423]] (no plan; escalate) — when all dir probes are silent on a `{1..4, 6}` env. The runtime LLM should request a new probe pass that exercises ACTION6 first.
- [[merge]] — if entity_phase surfaces ≥ 2 same-color clusters within 2R (sokoban-like envs sometimes map onto merge mechanics).
- Larger `max_states` — only if BFS exited at the cap; never if elapsed was the binding constraint.

## Related

- [[inferential_agent]] — wrapper that adds prefix awareness via `_plan_navigation`
- [[../../game_types/movement]]
- [[../../lessons/prefix_aware_navigation_20260423]]
- [[../../lessons/sokoban_search_explosion_20260423]]
- Compatible refactor base for [[../brittle/internal_method_call]]
