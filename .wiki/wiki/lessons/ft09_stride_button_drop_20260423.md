---
type: lesson
date: 2026-04-23
rounds: R14
games: [FT09]
status: closed — stride-4 retry adopted as default fallback
---

# FT09 stride-2 finds 72 buttons that stride-8 misses (R14)

> The default observation stride of 8 px samples 64 candidate
> click cells on a 64×64 grid. On FT09, none of those samples
> hit a responsive button — `click_responsive_cells = 0` for
> every R6-R13 trace. R14 added a stride-4 retry pass after the
> first plan fails: stride-4 found 72 responsive cells where
> stride-8 found 0. The buttons are real and reachable; the
> default stride was just too coarse to land on them.

## What the measurement showed

R14 instrumented FT09 with a two-pass observation: stride-8
first (the default), then stride-4 if the first plan returns 0
levels. Counts on `ft09-0d8bbf25` L1:

| Stride | Cells probed | Responsive (diff ≥ 10) | Top diff_magnitude |
|--------|--------------|------------------------|---------------------|
| 8 | 64 | 0 | 0 |
| 4 | 256 | 72 | 94 |
| 2 | 1024 | 88 | 94 (same cells, denser sampling) |

The 72-vs-0 jump from stride-8 to stride-4 is what mattered.
Going from stride-4 to stride-2 added 16 more responsive cells
but at 4× the budget cost — diminishing return. R14 picked
stride-4 as the default fallback.

## Why default stride-8 fails on FT09 specifically

FT09's lights-out grid is 8 px wide per cell, anchored such that
every cell *boundary* falls on a stride-8 sample point. Probe
clicks land on borders, which are inert. Stride-4 puts the
sample at the cell *center* (offset by 4 px from the border),
hitting the responsive interior. Most other 8-px-grid games
(SB26, CD82) have grids anchored differently; stride-8 lands on
cell centers and works fine.

The stride choice is therefore a *probe-grid alignment* issue,
not a "FT09 needs more probes" issue. On a grid whose cell width
doesn't divide stride evenly, stride-8 will eventually find
responsive cells; on FT09's exact-multiple alignment it never
does.

## Falsification signature

A new env where every default-stride sample reports
`diff_magnitude = 0` AND no available action other than ACTION6
AND the entity phase reports a uniform-grid background → drop
to stride-4 immediately and re-probe before declaring "click
rare." The signature `avail = [6]`, `responsive_8 = 0`, dense
uniform-color grid is the falsifier for the
"`click_rare`-primary" classification.

## What the next-best plan looks like

The retry path is already in place — `observation_phase` accepts
a `stride` parameter and the outer loop calls it with stride=4
on plan-zero. Adoption count: FT09 +1 in R14 direct probe
(matches the 1/6 we still see in R20 results). The remaining 5
levels of FT09 are blocked on the L2+ wrong-cell-selection issue
called out in [[gf2_lights_out_stencil_20260423]] — finer
stride alone does not solve those.

## Why this generalises beyond FT09

Two corollaries:

1. Any "click-only env, default-stride dead" trace should
   trigger an automatic stride-4 retry. The cost is one extra
   observation pass (~500 actions); the upside is that grid-
   aligned envs become legible.
2. The runtime LLM should treat `responsive_8 = 0 AND
   responsive_4 ≥ 50` as a stride-alignment artifact, not as
   evidence that the game is "rare-click." This stops a
   misclassification from cascading into wrong primary plan
   choice.

## Decision

Stride-4 retry stays as the default fallback in the I-Agent's
outer loop. Document the falsifier here so the runtime LLM can
recognise the pattern in traces from new envs.

## Related

- [[../games/FT09]]
- [[../concepts/gf2_toggle_stencil]]
- [[../concepts/probe_signature]]
- [[../lessons/gf2_lights_out_stencil_20260423]] — L2+ residual gap
- [[../strategies/frame_only/inferential_agent]] — observation_phase

## Sources

- R14 trace (re-derived from `scripts/probe_ft09.py` outputs)
- `scripts/probe_inferential_direct.py` FT09 row
- R14 commit `173b399`
