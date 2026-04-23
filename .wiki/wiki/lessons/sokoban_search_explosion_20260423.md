---
type: lesson
date: 2026-04-23
rounds: R19
status: ceiling identified; workaround needs specialized plan
---

# Frame-Hash BFS Saturates on 2-Player Sokoban (R19)

## What

`strat_bfs_state_space` uses a frame-hash state abstraction: two
env states hashing identically are treated as the same node.
BFSSolver has defaults `max_depth=25..50`, `max_states=15k..40k`
and a time limit of 60..90 s.

For a 2-player cooperative Sokoban with ≥ 4 pushable blocks,
per-step branching with `{dir × 2 players}` is at least 16 —
often 20 once ACTION6 is added (KA59 v2). A typical L1 solution
is 10-15 joint moves. The search space for depth 10 is
`24^10 ≈ 6 × 10^13` — many orders of magnitude larger than the
`15k` states BFS can explore before time-out.

## Why the frame-hash is wrong here

Two game states can show identical frames yet have distinct
successor sets — e.g., the two players visually swap positions
but one is "carrying" a block. Conversely, two frames may differ
by a step counter pixel yet represent the same gameplay state.
HUD masking helps the second case but doesn't address the first.

A **proper** Sokoban state is `(player1_xy, player2_xy,
block_set)` — a tuple of 2-4 coordinate pairs. Hashing this
abstract state instead of the raw frame gives a search space of
`(64² × 64² × 64²^k)` which for k=4 blocks is still large but has
a drastically higher useful-visit ratio, especially with a goal-
pursuit heuristic (A\* with Manhattan to goal zones).

## Observed outcome (R19)

KA59 v2 direct probe (`scripts/probe_ka59.py`):

```
[obs#1] base_levels=0 dir_transitions={1:0,2:0,3:0,4:0} obs_used=539
[goal#1] kind=navigation players=found merge_items=8 goal_regions=0
[nav#1] budget=30000
    -> levels=0 used=2050 elapsed=10s
```

The `dir_transitions=0/0/0/0` was initially alarming but is a
semantic non-issue: `observed_transitions` only records level-
advance events. Raw probing (`scripts/probe_ka59_raw.py`) confirms
each dir press produces ~19 px of diff at L1 start.

`nav#1` used only 2050 env steps out of 30k budget because BFS
exhausted its internal state / time caps. Same result at 10k and
30k budget.

## Decision

Frame-hash BFS cannot clear 2-player Sokoban within the Kaggle
envelope. The right fix is a specialist `_plan_push_bfs` that:

1. Identifies movable clusters (player1, player2, blocks) via
   pre/post-probe motion analysis.
2. Represents state as tuple of cluster centroids.
3. Runs A\* with Manhattan-to-goal-zone heuristic.

Until that lands, KA59 stays at 0 clears. The R19 commit kept the
budget-bump (`sokoban_like` signature → 30k nav budget) because
it's a cheap infrastructure win for other movement-hybrid games
without affecting AR25-class fast-bail.

## Falsification

If a frame-hash BFS ever clears KA59 L1 within 50k actions on the
preview env set, this lesson is wrong and the ceiling claim
should be revised. Until then, frame-hash BFS on N-player
Sokoban is ruled out.

## Related

- [[../games/KA59]]
- [[../games/WA30]]
- [[../game_types/sokoban]]
- [[../concepts/pushable_block]]
