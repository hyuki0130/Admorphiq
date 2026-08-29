---
type: lesson
topic: perception
date: 2026-08-30
keywords: [standable, not-floor, learn-refusal, phase-grid, gantry, dc22, census, selectivity, r101]
---

# A colour condemned by one refusal condemns every drawn tile that CONTAINS it

> `phase.py`'s floor rule rejects an avatar-sized tile if ANY pixel in it is a condemned colour,
> and `_learn_refusal` condemns COLOURS board-wide from a single refusal. On dc22 that condemns
> the four pressure plates the crane's drives require — and the census says it condemns nothing
> anywhere else.

## What was measured

`scripts/_standable_census.py` instruments `PhaseGridTool.propose` and `GantryCraneTool.propose`
and, once per turn on the tool's own current world, classifies every avatar-sized window:

```
rejected for BACKGROUND        the rule working as intended, not counted
rejected, tile UNIFORMLY a condemned colour     a correct rejection
rejected, tile MIXED           has a condemned pixel, no background pixel, not uniform
                               <- the defect shape: a DRAWN THING condemned for one pixel
```

Full 25 (`pfan.sh stcensus`, one slot per game, zero errors):

```
game   turns with _not_floor   colours   MIXED rejections   distinct cells   PROOF
dc22            584             [0, 5]        107,969            344           0
every other game  0               []               0               0            0
```

⭐ **Twenty-four of twenty-five games record ZERO tool turns at all** — `phase_grid` and `gantry`
never propose on them, which is what their `detect` conjunction claims and is here measured from
the other side. So the defect's blast radius is **dc22 alone**, and the tools' selectivity is
confirmed as a by-product.

⭐ **THE PROOF NEEDS NO INTERPRETATION.** Re-run on dc22 with the arms that carry the avatar
through the aimed teleport into the plate cluster: **cell (55,34) is condemned at turn 582 and the
avatar STANDS IN IT at turn 680.** That is the plate which enables the crane's UP drive. One cell
is a floor and not a total — the other three plates are only ever occupied when the walk is forced
by hand.

## Why the rule condemns them

`_learn_refusal` condemns a COLOUR, board-wide, from one refusal; on dc22 `_not_floor` holds
`[0, 5]`. Every `njvd-rolo` pressure plate on level 6 is a 2x2 sprite drawn `[[1,0],[0,C]]`
(C = 12/15/14/10) — it CONTAINS colour 0. So `_standable` rejects every window overlapping a plate,
`_plan_full` returns a plan of length **zero** between all four plates, and the crane's drives are
unreachable BY PLAN even though each one works when the avatar is walked there by hand.

## Scope, corrected before it was acted on

⚠️ `sluice.py` does **NOT** import `phase.py`. It carries its own module-level
`_standable(board, cells, barred)` over its own `Board`. The only importers of `PhaseGridTool` are
`phase.py` and `gantry.py`, so this is a two-tool finding, not a three-tool one.

## What NOT to do about it

Two repairs were built and both are negative — see [[sample_games_mechanics]]:

* striking a walked-on colour out of `_not_floor` **fires** (colour 0 is struck) and still stops at
  five levels, while costing **+23 actions** on dc22's levels 1-5, where level 3 has only **8
  actions of slack**;
* unioning `_visited` into `_grid` **loses a level** (4 vs 5, 0.47619 vs 0.714286) and costs about
  ten times the wall clock.

So the rule is wrong and fixing it buys nothing today: the floor map opens and the crane is still
not learned, because pressing each drive from its own plate and learning the drawn `vcha` rail are
separate problems. **Correct, dc22-only, and not worth a shared-file change until something
downstream can use the opened cells.**

## Related

[[sample_games_mechanics]] · [[rounds/r101_silent-specialists]]
