---
type: concept
topic: perception
date: 2026-08-27
keywords: [segmentation, level-geometry, alpha-channel, connected-components, walls, r101]
---

# The board's walls arrive as ONE sprite, and a naive segmentation sees one object

> Five of six stuck games carry a board-sized sprite that IS the level geometry — the cell
> lattice and the maze walls — drawn as a single sprite with `-1` as the engine's alpha channel.
> A connected-components pass keyed on opaque pixels sees one object where the board has many
> corridors, and a tool in that state does not fail to plan: it plans THROUGH WALLS.

## What it is

`arcengine/sprites.py` composites with `non_transparent = blk[blk != -1]` and
`np.where(other_pixels != -1, other_pixels, other_region)`. **`-1` is the alpha value.** Every
sprite that is not a solid rectangle carries it, so its presence is encoding, not a mechanic
shared between games — a coincidence that misled a whole afternoon (below).

Rendered, these elements are unmistakable. g50t's constant `61x61` at 2px per character:

```
###############################
#..#..#..#..#..#..#..#..#..#..#
###############################
#..#..#..#..#..#..#..#..#..#..#
###############################
```

— the playing field's cell lattice. Its L7 `56x61`:

```
......####.....#############
......####.....####.........
......####..################
..................####..####
####..##########..####..####
####........####..####..####
####.....#############..####
```

— a maze. ka59's `65x61` is walls and corridors; it sits at `(-1, 3)` and exceeds the 64-wide
board by a pixel because it is a **wall ring drawn one pixel outside the field**, not because it
extends past it.

## Why it is easy to get wrong

Opacity runs **8% to 70%**. At the sparse end a segmentation keyed on opaque pixels merges every
corridor into a single blob, or discards it as background. Neither failure announces itself: the
tool still returns a plan, still spends actions, and the board still does not move. **That is the
same observable symptom as a covering, from the opposite cause** — and the covering reading sends
you to dismiss the sprite when the correct response is to SEGMENT it.

So the question to put to a stalled tool is not *is something covering the board* but:

> **does your segmentation resolve this one big sprite into walls, or read it as a single object?**

Density is not the discriminator, and this matters because it is the tempting shortcut: s5i5
clears a level whose geometry sprite is **9%** opaque and stalls on one at **20%**. Dump what the
segmentation actually returns.

## Provenance, and the false premise this replaced

The claim that these elements are **new at the stuck level is FALSE**, and one table killed it:

```
game   levels                       oversized elements        opaque%
ka59   L0                                            51x51        70%
ka59   L1..L5                             63x63 … 69x69     16–41%
ka59   L6  (stuck)                                   65x61        15%
g50t   L0..L5   61x61 at (1,1) EVERY level, same name          33%
g50t   L6  (stuck)                        61x61, 56x61, 59x51  33/56/8%
s5i5   L1..L4                             58x70 … 70x70      9–16%
s5i5   L6  (stuck)                                   70x51        20%
```

g50t's `gehwhuvxqq` is at `(1,1)` with 33% opacity on **every** level L0–L6 — same name, same
position, same coverage. **An element present where the tool succeeds cannot be what makes it
fail.** No frame render could have rescued the premise, which is why the assignment to render
frames was cancelled rather than run.

⛔ The overlay hypothesis that this replaced was pushed to four agents before being checked, on
the strength of `-1` appearing in several games at once — a shared alpha value read as a shared
mechanic. Cost: four agents redirected twice. See [[new_kinds_at_the_wall]] for the other half of
the same error and [[../lessons/instrument_validity_20260825]] for the rule both broke.

## Related

- [[new_kinds_at_the_wall]] — the finding this corrects; its small-kind half survives.
- [[guard_about_the_model]] — a correct plan over a wrong model, which this is an instance of.
- [[../rounds/r101_tool-development]] — the round.

## The shared segmentation can DISCARD the geometry entirely

`tools/base.py:connected_components()` defaults to `background=None`, which treats **the most
common colour on the board as background and skips it**. When the walls are the most common
colour, every tool calling it sees a board with no walls — and plans straight through them.

Measured on the stuck level of all six stuck games (`scratchpad/bg_swallows_walls.py`, level data
composited, engine never started):

```
ka59 L7  bg=c0   65x61:c2                              not swallowed
s5i5 L7  bg=c0   70x51:c15                             not swallowed
ls20 L7  bg=c4   64x64:c5   (its c4 half is background, partially)
dc22 L6  bg=c0   32x66:c5                              not swallowed
wa30 L9  bg=c0   no board-sized geometry at all
g50t L7  bg=c5   56x61:c5 AND 59x51:c5                 BOTH SWALLOWED
```

**One game in six, and it is graded rather than binary** — which is what makes it usable. g50t
swallows one geometry sprite from L5 onward and **clears L5 and L6 anyway**; L7 is the first level
where a *second* one goes. So the swallow is not sufficient to stop a tool, and the thing to look
at is what the additional sprite carried.

⚠️ Two instrument notes, both mine, both the same error:

* the first version of this probe compared only the **largest** sprite against the background and
  reported g50t clean. Checking one representative instead of the set hid the entire finding;
* the composite is static — layering the level data by hand rather than reading an engine frame —
  so it is a screening tool, not a verdict. Verify on a real frame before building on it.

⛔ And apply the same test this page already carries: **before calling a swallow the cause, check
the levels the tool CLEARS.** Here that check downgraded the finding from an explanation to a
graded lead, in one command.
