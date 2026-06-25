---
type: lesson
date: 2026-04-23
rounds: R20, R12
games: [CD82]
status: closed — observation signature characterised; multi-level plan still TODO
---

# CD82 paint signature — HUD masking exposes 2-cell palette+canvas pattern (R12, R20)

> Pre-HUD-masking, CD82's discovery phase reported 71 of 71
> probe clicks as "responsive" because a step-counter at (63,63)
> incremented on every action. Entity phase then tagged 67 of
> them as palettes, drowning out the two real interaction cells
> at (32,25). The R12 HUD-masking pass collapsed the responsive
> count to 2/71 and palette count to 0 — the two surviving cells
> are the actual game button (`(36, 4)` and `(37, 4)`, both
> `diff_magnitude=94`, single shared centroid). That two-cell
> signature is what `_plan_navigation` should look for in any
> CD82-shaped paint game, not the noisy raw count.

## What the probe showed

`scripts/probe_cd82.py` (R20) instruments `observation_phase`,
`goal_phase`, and every `PLAN_FNS` entry. On
`cd82-fb555c5d` L1 start, with R12 HUD masking enabled:

```
[obs#1] base_levels=0 responsive>=10=2 big>=100=0 used=...
   top-big centroids: [(36, 4, 94), (37, 4, 94)]
[goal#1] kind=navigation conf=0.40 source=...
   players=found merge_items=0 executors=0 palettes=0
   [plan=navigation] levels=1 used=... elapsed=...s
```

Compare to the pre-R12 trace (no HUD mask):

```
[obs#1] responsive>=10=71 big>=100=0
   palettes=67 (every probe-clicked cell labelled palette)
```

Same env, same code, same actions — the only difference is the
HUD mask filtering pixels that change under ≥80% of probes.

## Why it matters

R20's `_plan_navigation` rewrite cleared CD82 L1 directly via
`BFSSolver.solve` with click_coords seeded from the masked
profile. The two surviving "responsive" cells co-locate at one
centroid, which BFS treats as a single clickable goal — a 5-step
solve ((click, dir, dir, dir, dir) shape) that the prior
67-palette signature buried under combinatorial fan-out. The
LLM-relevant takeaway: **"click responsive cells = 2 with shared
centroid" is the paint-game L1 signature**, not "responsive ≥ 5
plus 1-4-asymmetric probe ratio" as
[[../concepts/probe_signature]] rule 3b currently states.

## The L2+ gap

CD82 L1 clears via navigation-style BFS once the HUD mask
exposes the two-cell button. L2+ does not: the paint mechanic
(select swatch → navigate basket → fire launcher) has
combinatorial depth beyond the BFS state cap. The frame-only
plan that solves L2+ requires:

1. Detect swatch grid (3×3 or N×M cluster of distinct-color
   cells in a fixed corner).
2. Read the per-level target pattern (a region the level
   updates after each canvas paint).
3. Identify the launcher (a cell that, when clicked, commits
   the basket's current color to the canvas).

Without those, BFS is searching the wrong state space — every
"click swatch" branch looks like a no-op because the canvas
update is delayed until launcher click.

## Falsification signature

When `_plan_navigation` returns `(1, used)` on a CD82-shaped
env (responsive=2, shared-centroid, navigation goal) but
subsequent observation calls show `levels` stuck at 1 with
`base_levels=1` repeating, the plan is no longer the right
fit — the paint mechanic has activated at L2 and a
swatch+launcher detector is needed.

## Decision

Keep `_plan_navigation` as the L1 entry on paint-game-shaped
envs (the masked signature is robust). Defer L2+ to a future
sprint that ships `_plan_paint_pattern` with swatch detection.
Update [[../concepts/probe_signature]] rule 3b to additionally
mention the two-cell shared-centroid sub-case.

## Why HUD masking matters more broadly

Any env with a step counter, timer, score readout, or animated
overlay produces the same false-positive cascade. R12 HUD
masking is now a precondition for any plan that consumes
`click_responsive_cells`. The mask is computed once per
observation phase (`profile["hud_mask"]`) and subtracted from
every per-probe statistic before the entity phase runs.

## Related

- [[../games/CD82]]
- [[../concepts/probe_signature]] — rule 3b paint signature
- [[../strategies/frame_only/inferential_agent]] — observation_phase + HUD mask
- [[../lessons/prefix_aware_navigation_20260423]] — the R20 nav rewrite that cleared CD82 L1

## Sources

- `scripts/probe_cd82.py` — instrumented trace
- `scripts/inferential_direct_results.json` — CD82 13662 actions, 1 level
- R12 commit `84e53d1`
- R20 commit `afe6ab8`
