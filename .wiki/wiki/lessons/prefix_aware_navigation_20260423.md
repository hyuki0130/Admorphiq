---
type: lesson
date: 2026-04-23
rounds: R20-R22
status: regression-then-fix; infrastructure correct
---

# Prefix-Aware Navigation Plan (R20-R22)

> `_plan_navigation` must resume BFS from the current level start using the cumulative prefix and chain `solve_all_levels` internally; R20 accidentally dropped multi-level chaining (AR25/M0R0 regressed 2→1), and R22 restored it with prefix awareness so one plan call clears multiple levels in sequence.

## What

`_plan_navigation` in `src/admorphiq/strategies/inferential.py`
previously delegated to `strat_bfs_state_space` in
`src/admorphiq/agent_ensemble.py`. That function internally calls
`reset(env)` and runs `BFSSolver.solve_all_levels` — a loop that
chains single-level BFS calls, growing a cumulative action list.

Round 20 rewrote `_plan_navigation` to call `BFSSolver.solve`
directly with `prefix=_ACTIVE_PREFIX` (the R15 cumulative prefix)
so that BFS resumes from the CURRENT level start, not game start.

## Why the rewrite

The delegated version ignored `_ACTIVE_PREFIX`. On multi-level
games (CD82), every observation call after L1 cleared showed "BFS
solver: level 1 solved!" because the ensemble BFS re-reset and
re-solved L1 each time. Outer `best` was already 1, so no
progression. Diagnosed via `scripts/probe_cd82.py`.

## The R20 regression

The rewrite accidentally replaced `solve_all_levels` (multi-level
chaining) with `solve` (single-level). On games where L1 BFS
completes within one `_plan_navigation` call, the plan should
continue solving L2, L3, ... within the same call. R20's version
stopped at L1 and relied on the outer loop's next iteration —
which has to re-run observation_phase (+500 env steps) and re-
initialise a fresh BFSSolver with a small per-plan budget cap.

Measured regression on the 10-env direct probe (2026-04-23):

| env | R6 baseline | R20 single-solve |
|---|---|---|
| AR25 | 2/2 | **1/2** |
| M0R0 | 2/2 | **1/2** |
| DC22 | 1/1 | 1/1 |
| FT09 | 0/6 | **1/6** (new) |

Net: +1 (FT09) -2 (AR25, M0R0) = -1 raw.

## The R22 fix

Restored `solve_all_levels`-style internal chaining INSIDE
`_plan_navigation`, but with prefix awareness:

```python
while True:
    result = solver.solve(
        env, ...,
        prefix=prefix_actions + cumulative_new,
        expected_base_levels=base_levels + levels_cleared,
    )
    if result is None:
        break
    cumulative_new.extend(result)
    levels_cleared += 1
```

Each inner iteration extends the prefix with the last level's
winning actions, so the next BFS searches for the next level from
the correct state. One plan call can now clear multiple levels in
sequence.

## Falsification

If a future change to the plan registry calls the old delegated
`strat_bfs_state_space` from elsewhere without the prefix, the
same regression will resurface. A contract test pinning "plan
navigation clears AR25 L2 after L1" would catch it — deferred
until live-env bench tooling allows cheap per-env regression
checks.

## Related

- [[../strategies/frame_only/inferential_agent]]
- [[../games/AR25]]
- [[../games/M0R0]]
- [[../games/CD82]]
