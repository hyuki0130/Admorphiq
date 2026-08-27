---
type: concept
topic: level-progression
date: 2026-08-27
keywords: [level-data, new-element-kinds, stall-diagnosis, overlay, plan-vs-model, r101]
---

# The level where a tool stops introduces element kinds it has never seen

> Six of the eight games stuck below 1.0 add previously-unseen sprite KINDS on their first
> uncleared level, and one of them does it while getting SMALLER — so "deeper levels are
> harder" is the wrong frame, and the right question is what the new kinds do.

## What was measured

`scripts/level_diff_probe.py <game>` diffs the last cleared level against the first uncleared
one, reading the games' own level data with the engine never started. Run over the eight games
holding the remaining 0.1219 of headroom:

| game | last cleared → first stuck | sprites | new kinds |
|---|---|---|---|
| g50t | L6 → L7 | 33 → **32** | 6 |
| ka59 | L6 → L7 | 9 → 10 | 6 |
| dc22 | L5 → L6 | 37 → 72 | 6 |
| s5i5 | L6 → L7 | 12 → 20 | 6 |
| ls20 | L6 → L7 | 102 → 103 | 5 |
| wa30 | L8 → L9 | 50 → 73 | 4 |
| bp35 | L5 → L6 | 1 → 1 | *unmeasurable* |
| lf52 | L5 → L6 | 1 → 1 | *unmeasurable* |

⚠️ **The last two rows are the probe's blind spot, not a negative result.** bp35 and lf52 build
their boards at RUNTIME, so their level data holds one sprite and the diff has nothing to
compare. Recording them as "nothing new" would be the [[../lessons/instrument_validity_20260825]]
error of reading a field for something it does not record. They are unknown here, and the first
version of this page's claim — *"every stuck game introduces new kinds"* — was carried past what
the measurement reached and had to be cut to six of eight within the hour.

## Why the count going DOWN is the load-bearing row

g50t's level 7 has **fewer sprites than level 6** and the tool cannot clear it. Whatever stops it
is not volume, not search depth, and not arrangement difficulty — for this game those are
measurably excluded. Six kinds are new. That single row is what turns the finding from a
plausible story into a discriminator.

## The near-full-screen element

Three of the six carry a new element at or beyond the size of the 64x64 board:

* ka59 `65x61`, g50t `56x61`, s5i5 `70x51`

An element larger than the board is not a game piece; it is a covering. **The hypothesis it
generates, and the one worth killing first, is that the level opens under an overlay and the
tool is planning against the overlay rather than the board.** That predicts the exact symptom
these games show — a plan is produced, actions are spent, nothing that matters moves — and if
true, no amount of planner work reaches it, because the plan is correct about a board that is
not there. Checking it costs one command: dump the frame layers on the stuck level's first
frame and compare against the previous level's. See [[frame_layer_timeline]].

## The reframe this forces on stall diagnosis

A tool that takes the board and then emits actions that change nothing **looks** like a planning
failure. It is equally what a CORRECT plan produces when aimed at objects whose behaviour the
model has wrong. From outside the tool the two are indistinguishable, and every round of planner
iteration spent on the second kind is wasted by construction.

The level data separates them in one command, before the engine starts. So the order is: diff the
level, log what the model believes each new kind IS, probe one, compare — and only then touch the
planner. This was written after several rounds were spent iterating planners on games whose real
gap was an unread element, and it is the same shape as
[[guard_about_the_model]]: the code ran, confidently, over a model that did not match the board.

## What it does not claim

It does not say the new kinds are always the cause — only that they are always present (in the
six measurable cases) and cheap to check first. A game could introduce furniture that is pure
decoration while the real wall sits elsewhere. The falsifier is direct: probe a new kind, find it
inert, and the finding is excluded for that game.

## Related

- [[frame_layer_timeline]] — how to read what a frame actually contains, layer by layer.
- [[guard_about_the_model]] — the same failure from the other side: correct code, wrong model.
- [[action_budget]] — the other thing the level data holds that changed a diagnosis.
- [[../lessons/instrument_validity_20260825]] — the blind-spot rule the first draft of this page broke.
- [[../rounds/r101_tool-development]] — the round.

## Two corrections, measured within the hour of the page being written

**1. The overlay hypothesis is DEAD.** The page proposed that the near-full-screen elements
(ka59 `65x61`, g50t `56x61`, s5i5 `70x51`) are coverings, and that the tools may be planning
against a covering rather than the board. Measured directly from the sprite pixels: colour `-1`
is a sentinel, not a colour, and those elements are **sparse**, not solid —

```
ka59 65x61  15% opaque      g50t 56x61  56%      s5i5 70x51  20%      ls20 64x64  11%
```

A 15%-opaque board-spanning sprite is a **structure** — track, wall network, maze — not a
covering. Worse for the hypothesis: g50t, ka59 and ls20 already carry a board-spanning sparse
sprite on the level they DO clear (`61x61` at 33%, `69x69` at 27%, the same `64x64` at 11%), so
its presence cannot be what stops them. The one genuinely solid large sprite in the set is dc22's
`32x64` at 100% opacity — and it is present on the cleared level too, at the same place. Nothing
here is an overlay and the hypothesis was pushed to four agents before it was checked.

**2. The kind counts were inflated by the probe's own key.** `level_diff_probe.py` keys a kind on
`(width, height, colours)`, so a structure that merely RESIZES between levels registers as new.
g50t's headline "six new kinds" includes `61x55 → 56x61`, which is one object breathing. Re-run
with a size-blind key (`scratchpad/kinds_recheck.py`):

| game | new kinds, size+colours | new kinds, **colours only** |
|---|---|---|
| dc22 | 20 | **17** |
| s5i5 | 16 | **7** |
| g50t | 9 | **4** |
| ka59 | 6 | **2** |
| ls20 | 5 | **4** |
| wa30 | 4 | **3** |

**The finding survives and the direction is unchanged** — every one of the six still introduces
genuinely new colour-combinations at exactly the level where its tool stops, and g50t still does it
while shrinking. But ka59 is 2, not 6, and dc22 is 17, not the 6 that were quoted to its agent
(the original print showed only the top six of twenty). ⛔ Both errors are the same one this page
already warns about in its own text: **a claim carried past what the measurement supports.** The
first was written into the page, the second into five agents' instructions, inside an hour of
writing the warning.

The lesson for the probe specifically: **a kind key that includes size cannot tell a new object
from a grown one**, and the difference is the whole finding. Report both keys or neither.
