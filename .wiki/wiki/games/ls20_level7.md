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

## Mechanics — RESOLVED by reading the game's own source

The solid colour-4 blocks are **genuine walls**, and the tool is right to call them walls. From
`environment_files/ls20/*/ls20.py`, every one of them:

```
name='ihdgageizm' (x3), 'krdypjjivz', 'mxfhnkdzvf', 'ubyunwkbpx'
layer=-5  blocking=PIXEL_PERFECT  interaction=TANGIBLE  is_collidable=True
```

**The board simply has no locks.** Counting what the parser finds at its own return, per level:

```
L1  17 parses   locks 0..1        L5  199 parses  locks 0..1
L2 109 parses   locks 0..1        L6  298 parses  locks 0..2
L3  67 parses   locks 0..1        L7   13 parses  locks 0..0   <- none, ever
L4  73 parses   locks 0..1
```

So `keymaze` is not failing to SEE a lock; level 7 has none. The tool's whole plan shape is
"reach the lock that matches the token you carry", and that objective does not exist on this board.
⛔ **This is a missing capability, not a parsing defect** — the level is won some other way, and
what that way is has not been established. Level 7 also drops both 7x7 sprites that level 6 carries
and adds `irgjxweouz`, a `1x29` bar in colour 14.

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
