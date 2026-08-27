---
type: concept
topic: perception
date: 2026-08-27
keywords: [frame-layers, animation, stale-frame, frame_2d, swallowed-action, transfer, r101]
---

# Frame layers are an ANIMATION TIMELINE, not a z-order

> Nine of the twenty-five sample games return more than one frame layer, and on six of them
> layer 0 differs from the last layer after an ordinary action. Every generic tool read
> `arr[0]` — the board BEFORE the action's animation had played out.

## Definition

An observation's `frame` is a stack of `(64, 64)` grids. It is tempting to read it as a
z-order (background, sprites, overlay) and take the first as "the board". Measured, it is a
**timeline**: successive rendered states of the same board as one action's animation resolves.
`arr[-1]` is the settled result; `arr[0]` is where it started.

`src/admorphiq/tools/base.py:frame_2d` — the only frame reader every generic tool uses —
takes `arr[0]`.

⛔ **"Then read the last layer" is WRONG, and was measured wrong the same hour.** Switching
`frame_2d` to `arr[-1]` and gating it on the full 25 gave mean 0.6733 -> **0.6525**, with
m0r0 -0.4286, g50t -0.1071 and ls20 -0.0317 against gains of only sc25 +0.0417, re86 +0.0043
and lp85 +0.0025. Reverted (`scripts/rounds/R101LAYER`). Note that g50t is one of the six
games whose layer 0 differs from its last, and reading its last layer made it WORSE — so the
stack is not simply "start of animation ... settled result", or not uniformly so.

What survives the revert is the evidence below, which is about the stack carrying information
`arr[0]` cannot see. What does NOT survive is any claim about which single index to read. A
tool that needs the stack should ask for the stack; picking a different constant index is
the same mistake with a different constant.

## Instantiating games

Measured on all 25 with a short fixed action script per game so animations actually fire:

```
max layers   sb26 42 · sc25 22 · sp80 22 · cd82 15 · g50t 9 · tu93 8 · bp35 5 · lf52 2 · sk48 2
layer 0 != last layer   sp80 · cd82 · g50t · tu93 · bp35 · sk48      (6 of 25)
```

Two of those six — **bp35 (0.1333) and g50t (0.1071)** — are among the four weakest games in
the set, and both differ on every probe (12/12 and 5/5). The games that score worst are the
games whose board the tools were reading one animation frame too early.

## Detection heuristics (frame-only)

`np.asarray(obs.frame).ndim >= 3` and `shape[0] > 1`. Nothing game-specific: a tool never
needs to know WHICH game animates, only to read the settled grid.

## How it surfaced

Not from a tool's failure but from a transfer measurement. Two tu93 boards — the live one and
an archived version hash — clear levels 1-4 in identical action counts and then diverge, 9/9
against 4/9, deterministically over three runs each. Their level-5 START FRAME is
**byte-identical on layer 0**, yet the same twenty-action script produces different responses
from action six onward. So no tool could have distinguished them by looking. The boards'
only recorded difference is one sprite's `layer` field (0 live, -1 archived), and in the
rendered frame that difference appears **only on the last layer**.

## tu93's transfer loss is PERCEPTION, and the proof is an action tape (2026-08-27)

`scripts/twinboard_probe.py` settles the question a score cannot: record the harness's own action
tape on one copy of a game and replay it, action for action, on the other.

```
tape recorded on the LIVE board -> replayed on the ARCHIVE board
   9 levels, clears at 18, 28, 47, 64, 93, 121, 135, 158, 187 — IDENTICAL to the control
```

**The archive board is winnable by the exact moves the tool already knows.** It is the same game;
the tool simply does not find them there. So the whole of tu93's 1.0000 -> 0.2222 is a perception
failure, and no planning or search work is called for.

`see` localises it to nine cells. A raw pixel diff would be noise — a re-render may permute the
PALETTE and draw at a different OFFSET — so it searches for the shift and colour mapping that
best explain one copy as the other and reports only what survives both:

```
tu93 level 5: 9 cells differ raw; after a shift of (0,0) and a palette map, 9 remain
   rows 44-46, cols 51-53      live 000 / 000 / 000      archive 999 / 999 / 949
```

**One 3x3 object, present on the archive copy and absent on the live one** — the maze it stands
on is drawn at a different LAYER in the two renders, so it is covered in exactly one of them.
That is the same single `layer` field the level-data diff found this morning, reached
independently from pixels.

⛔ Note what this does NOT license. The fix is not "read a different layer index" — that was
measured on the full 25 and regressed three games. It is that a tool on a multi-layer board must
resolve an object that one layer hides, and only the tool that needs it should pay for that.

## Related

- [[swallowed_action]] — the other half of the same phenomenon: an action arriving mid-animation
  is consumed without effect. That is about WHEN to act; this is about WHICH grid to read.
- [[../lessons/generic_transfer_20260827]] — the transfer run this came out of.
- [[no_progress_bail]] — also found by asking why a game spent actions without gaining.
