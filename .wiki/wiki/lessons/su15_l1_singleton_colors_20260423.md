---
type: lesson
date: 2026-04-23
rounds: R21
games: [SU15]
status: open — generic merge plan still bails on L1
---

# SU15 L1 has zero same-color pairs (R21)

> SU15 looks like the canonical merge puzzle, so `_plan_merge`
> ought to fire. R21 measurement showed the env returns zero
> same-color fruit pairs at L1 start: every fruit on screen is
> a singleton color. The plan's "click the midpoint between the
> pair" heuristic has nothing to click. Goal must be reached
> through downgrade-then-merge or cross-color sequencing — both
> of which require lookahead the current plan does not do.

## What the probe showed

`scripts/probe_su15.py` (R21) instruments
`observation_phase` / `goal_phase` / `_plan_merge` of
`strat_inferential_agent`. On `su15-1944f8ab` L1 start the trace
emits, per call:

```
[obs#1]  base_levels=0 responsive>=10=N  used=...
[goal#1] kind=merge conf=0.30 merge_items=4 player=n goal_regions=0
[merge#1] levels=0 used=0 elapsed=0.0s
```

`merge_items=4` after R21 loosened the entity-phase heuristic to
also accept "size 8..150" singletons, but the four are four
distinct colors. The merge plan has this guard:

```python
pairs = [(a, b) for a, b in combinations(merge_items, 2)
         if a.color == b.color and dist(a, b) <= 2 * radius]
if not pairs: return 0, 0
```

The early bail (`elapsed=0.0s`, `used=0`) is the visible signature
of the same-color-pair count being zero.

## Why it matters

The merge mechanic page ([[../concepts/merge_mechanic]]) describes
the canonical pattern as "Phase 1 merge same-color, Phase 2
deliver." SU15 violates that ordering at L1: the colors on screen
are intentionally distinct, and the level requires the agent to
*produce* same-color pairs first by routing fruits past the
enemy (which downgrades them). L1 is a downgrade-then-merge
puzzle, not a merge puzzle.

This means the merge-plan-only path can never clear SU15 L1.
The brittle `strat_su15_vacuum` cleared 9/9 by reading the goal
spec from `game.rqdsgrklq` and planning the downgrade phase
explicitly. The frame-only equivalent needs an enemy-tracking
primitive (no plan currently has it).

## Falsification signature for the merge plan on this env

When `_plan_merge` runs on a frame whose `merge_items` are all
singleton colors, the plan returns `(0, 0)` instantly. That zero-
elapsed bail is the falsifier: the goal classification was
correct (merge IS the eventual mechanic) but the *current state*
has no same-color pair to act on. The runtime LLM should read
this as "merge plan correct in kind, wrong in phase — try a
preliminary downgrade phase or fall back to broader exploration."

## What the next-best plan looks like

Two candidates, both deferred:

1. **Cross-color downgrade probe** — vacuum-pull an over-color
   fruit toward the enemy cluster (detected by a non-merging
   sprite that destroys others on contact). After the downgrade,
   re-observe and look for new same-color pairs. Implementing
   this requires an enemy-detector primitive in `entity_phase`.
2. **Goal-spec inference** — read the per-level "needed colors"
   region (often a side panel) by detecting persistent static
   non-background pixels. Use it as the target vector and plan
   merges backward. Cannot be done with the current
   `goal_phase` heuristics.

## Decision

Document the falsification signature (above) so the runtime LLM
can recognise this case from the trace and request a fallback
plan rather than burning budget on a no-pair merge. Implement
either next-best in a future sprint when there's a Qwen-driven
proposal for the enemy primitive.

## Related

- [[../games/SU15]]
- [[../concepts/merge_mechanic]]
- [[../strategies/frame_only/inferential_agent]]
- [[../lessons/prefix_aware_navigation_20260423]] — companion R20-R22 fix

## Sources

- `scripts/probe_su15.py` — R21 instrumentation
- `scripts/inferential_direct_results.json` — SU15 31213 actions, 0 levels
- R21 commit `ce95929`
