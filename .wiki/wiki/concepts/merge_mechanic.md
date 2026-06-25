---
type: concept
instantiating_games: [SU15]
detection_frame_only: yes
---

# Merge Mechanic

> When two same-color sprites overlap, they combine into a single sprite of `color + 1`. Analogous to 2048. Higher colors take more merges to produce and are often the goal.

## Definition

A game implements the merge mechanic if, after an action causes two same-color sprites to occupy the same location:
1. The two sprites disappear.
2. A single sprite of `color + 1` appears at (approximately) the merge location.

Usually the game also has an inverse mechanic — an **enemy** sprite that chases and **downgrades** (color − 1) on contact. Together these primitives define the arithmetic of the puzzle.

## Detection heuristics (frame-only)

After a vacuum-style click on a cluster of two same-color sprites:
1. Count the number of distinct color-c clusters before and after.
2. If `count_c` decreased by 2 and `count_{c+1}` increased by 1 → merge confirmed.
3. If there is a cluster that persistently chases the nearest fruit and downgrades colors on overlap → enemy confirmed.

## Instantiating games

| Game | Role | Notes |
|------|------|-------|
| [[../games/SU15]] | canonical | fruits + enemies + goal zones; target color varies per level |

## Key abstractions

- **Fruit sprite** — movable, can merge with same-color peer
- **Enemy sprite** — AI-controlled, chases nearest fruit, downgrades on overlap
- **Goal zone** — static region that accepts specific-color fruits
- **Vacuum click** — `ACTION6(x, y)` attracts all nearby sprites (fruits and enemies) toward the click

## Solver pattern

1. Phase 0 — downgrade: route high-color fruits to enemies to reduce them to the target color.
2. Phase 1 — merge: pair same-color fruits by vacuum-pulling them together.
3. Phase 2 — deliver: vacuum-pull target-color fruits into goal zones.

Ordering matters: if you merge first and then discover you have too many of color c+1 without enough of color c, you may be stuck. Plan from goal backward.

## Related concepts

- [[sprite_cluster]] — detection primitive
- Vacuum-click action semantics (an `ACTION6(x, y)` that attracts nearby sprites toward the click) are what enable the merge; no dedicated concept page yet.
- [[../lessons/frame_diff_as_probe]] — using frame diff to confirm a merge occurred

## Related games

- [[../games/SU15]]

## Sources

- `src/admorphiq/agent_ensemble.py` — `strat_su15_vacuum` (brittle v1) implementation
- SU15 game source: `environment_files/su15/4c352900/su15.py`
