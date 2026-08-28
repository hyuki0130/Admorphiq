---
type: game
topic: ls20
date: 2026-08-28
keywords: [ls20, keymaze, locks, glyph, level-7, depth, r101]
---

# ls20 level 7: the tool declines the board, and it is right to

> `keymaze` clears six levels at the 1.0 cap and then hands level 7 away after ten actions,
> because the board comes back with **`locks=0`**. Level 7 introduces four SOLID 5x5 blocks in a
> colour the tool learned as a wall — and a solid cell has no glyph, so it is not a lock by this
> tool's definition. Nothing is misparsed; the mechanic is unrecognised.

## Current Status

6/7 levels, score **0.7500**, every cleared level at the cap and all of them faster than the human
(17/22, 101/123, 63/73, 66/84, 67/96, 100/192). The whole remaining 0.25 is one level.

## Observations

Measured at the moment `keymaze` gives up (per-call markers, no carry-forward):

```
pitch=5  dirs=4  floor=3  walls=[4, 5, 11]  locks=0  floorcells=16  walls_found=128  icons=1
```

Level 7 introduces, against level 6 (size-blind colour key, engine never started):

```
colour 4   5x5  x4   100% opaque      <- solid
colour 11  3x3  x3    88% opaque
colour 1   5x5  x1    20% opaque
```

Why every candidate fails the lock test, counted per call:

```
48255  uniform side=5      <- a solid 5x5 cell carries no glyph at all
 4239  border extent=2x2   <- partial overlaps touching the cell border
 2075  border extent=5x2
```

## Mechanics Hypothesis

The four solid colour-4 blocks are a level-7 mechanic this tool has no vocabulary for. They are
exactly one lattice cell each at `pitch=5`, so they are placed like walls and read like walls —
but level 6 has none of them, and level 6 clears.

## Notes / what was tried

⛔ **Reordering the parse so the glyph test runs BEFORE the learned wall-colour test measured
0.7500 — no change.** The reorder is sound in principle (a colour that only ever walled on the
levels seen so far can carry a lock later; membership of a learned set is not evidence against
positive glyph evidence) but it is not what stops this level: the blocks fail the glyph test
itself, as uniform cells. **Not kept**, because an unmeasured change is not an improvement.

## Lessons Learned

⚠️ Four instruments were wrong before one was right, and each failure was mine:
* attributing actions to the **last marker seen** turned ten read failures into "499 of 500
  actions" — see [[../lessons/instrument_validity_20260825]], sixth entry;
* replacing the **first match** of a string that appears more than once put a marker in the wrong
  function and produced silence that read as "the branch never runs";
* a marker calling `levels_completed`, which `keymaze` does not import, made `propose` throw on
  every call — **the harness caught it silently** and the game scored 0.0000 while looking like a
  measurement.
⛔ Assert the marker landed at the intended SITE, not merely that its text is in the file.

## Related

- [[../concepts/new_kinds_at_the_wall]] — every stuck game introduces unseen kinds at its wall.
- [[../rounds/r101_tool-development]] — the round.
