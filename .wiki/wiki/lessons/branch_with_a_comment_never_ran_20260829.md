---
type: lesson
topic: unreachable-branch
date: 2026-08-29
keywords: [rule-7g, unreachable-branch, dead-code, self-occlusion, avatar-hides-the-tile, portal, coverage, instrumentation, dc22, gantry]
---

# A comment describing a branch is not evidence the branch runs

> `gantry._act` carries a branch whose own comment says what it does and why the
> order matters. It has never executed. Not once, in the whole recorded history
> of the tool — and it guards the exact mechanic the level it was written for
> needs. Rule 7g's sharpest instance so far: the source says what is POSSIBLE;
> only a run says what HAPPENS.

## Symptom

A tool stalls on a board whose mechanic it demonstrably models. Reading the
source, the handling is *right there* — a named branch, a docstring explaining
the cost order, a comment naming the failure it was written to prevent. Every
review of the code concludes the tool already does this thing. Every run says
the thing never happens.

## The measured case

`gantry` plays dc22. Its `_act` has:

```python
# ⛔ Test a twin tile the moment the avatar is STANDING on one, before routing
# anywhere else. Routing first walks straight past it: the tile it is standing
# on is excluded from its own goal set, so the plan goes to the twin at the far
# end of the board, arrives, and walks back — for ever, without ever pressing
# anything.
if start in self._portals(board):
    for click in panel:
        if (click, start) not in self._warp_tested:
            return [self._press(geom, start, click, "probe")]
```

`_portals` returns objects whose tile PICTURE has exactly one twin, and it
re-reads every remembered object's picture **off the live board**. The avatar's
square is exactly one tile. So the tile the avatar is standing on reads as a
square of the avatar's own colour, pairs with nothing, and drops out of the set.

`start in self._portals(board)` is therefore **always False, by construction**.

Instrumented full game, every press logged with the cell it was made from:

```
268 presses over the whole game
presses of the teleport control from (47,18): 0
```

(47,18) is the tile whose teleport is the level's only way off the avatar's
starting island. The tool's own routes walked across it repeatedly.

With the occlusion repaired the same run measures the teleport immediately, and
finds it is AIMED by a second control:

```
(25,51) at (47,18), staircase 1/2/3       -> (51,32)
(25,51) at (47,18), staircase 4, aimer 3  -> (57,34)
```

## Root cause

**Self-occlusion.** The reader of a cell and the occupant of that cell are the
same size, so asking "what is at the cell I am on" returns the asker. Any
predicate of the form *"is the thing I am standing on interesting?"* has this
shape whenever the avatar covers a tile exactly, and it is invisible in review
because the code reads as though it obviously works.

## What to do

- **Instrument for BRANCH ARRIVAL, not for outcomes.** The cheap, decisive probe
  is not "did the tool clear the level" but "how many times did this branch
  fire". A branch with a hit count of zero over a full game is a bug report,
  and it costs one counter.
- **Suspect any predicate whose subject can hide its object.** Avatar-on-tile,
  cursor-over-cell, cart-on-track, crane-over-slab. If the occupant and the
  feature are drawn at the same scale, the live read is the occupant.
- **The repair is memory, and it must be NARROW.** ⛔ Remembering every object's
  picture so none can be occluded is MEASURED HARMFUL: dc22 goes from 5 levels
  to 3, because a family that repaints tiles for a living pairs tiles the board
  has since changed. Only the ONE currently-occluded cell may come from memory;
  everything visible is re-read.
- ⛔ **And do not "fix" it by probing earlier.** Moving the probe ahead of the
  plan in hand — so the tool cannot walk across the tile on its way elsewhere —
  also gives 3/6. The inherited cost order (press where you stand only after the
  route to the goal has failed) was already right; what was broken was the
  predicate, not the position.

## Falsification

If a branch's hit counter is non-zero on the boards it was written for, this
lesson does not apply to it. The claim is specifically about branches that read
plausible, are never counted, and are believed on the strength of their own
comment.

## Provenance

Measured 2026-08-29 on dc22 level 6 with `scripts/_dc22_ptrace.py` and
`scripts/_dc22_gantryx.py`; the 268-press log and the aimed-teleport table are
in `.wiki/wiki/sample_games_mechanics.md`. Related: `OPERATING_RULES.md` rule 7g (the source says what is POSSIBLE; only a run says what
HAPPENS) and its instrument-failure family, rules 7c/7d/7aj — neither was ever written as a wiki
page, and the two wiki links that named them had been dangling since this page was created.
