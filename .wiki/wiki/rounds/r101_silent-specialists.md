---
type: round
round: R101SILENT
axis: generic-tools
keywords: [silent tool, empty propose, retirement, revival, patience, alignment threshold, search cap]
verdict: five axes closed by measurement; score unchanged at 0.8935
---

# R101SILENT — why the last eight games stop, and five explanations that are not it

> Every stuck game retires its specialist because the tool proposes NOTHING, and five separate
> cheap explanations for that silence have now been measured and refuted.

## The finding

At the level that stops each game, the specialist is retired through the EMPTY path — it returns no
steps at all — and the general searcher inherits the board for the remaining ~500 actions.

```
bp35   crag       s5i5  swivel      dc22  gantry, phase_grid      lf52  railpeg
```

Their MODELS are correct, checked line by line against each game's own win predicate: swivel
optimises s5i5's cover-every-target, gantry routes to dc22's goal cell, crag's gravity/settle/gem/
spike/reversal model agrees with bp35's `fsvnqdbzrp` despite being recovered from frames alone, and
railpeg plays exactly the peg-solitaire protocol that clears lf52's first five levels.

## Five explanations, all measured, all refuted

| explanation | test | result |
|---|---|---|
| not enough patience | `HARNESS_NOPROGRESS=3000`, 6x | seven games, all identical to four decimals |
| the specialist is swapped out too early | `HARNESS_STALL=4000` | identical — **and a marker proved the knob never kept the specialist at all** |
| crag's window-alignment threshold is too strict | `_ALIGN_FIT` 0.82 -> 0.50, accepting every rejected window | bp35 unchanged at 0.2220 |
| swivel's search cap is binding | `_MAX_OPEN` 120k -> 4M | ONE GAME does not finish in forty minutes; the whole 25 normally takes fifteen |
| the silence is the instance's own history | give each tool one revival per level (reset instead of retire) | REVIVE fired, bp35 unchanged at 0.2220 |

The revival test was the most promising and the most instructive. A FRESH instance of crag bids
**0.50 and proposes a step** on the very board its live instance went silent on — so the board is
not structurally beyond it. Given that fresh start in the harness, it explores, fails to place its
window again, and re-mutes. The bid was real; the progress was not.

## What this round changed

Nothing in the tree. Two candidate changes were built, measured and reverted (a harness probe-order
memory, gated on the full 25 at 0.8935 -> 0.8935; and this revival). The score is 0.8935, seventeen
games at the cap, cumulative regressions zero.

⛔ **The instrument check earned its place five times.** `HARNESS_STALL` would have been written up
as evidence that patience is not the answer, when it never applied the treatment. Every claim here
that an intervention did nothing is backed by a marker showing the intervention happened.

## Related

[[lessons/instrument_validity_20260825]] · [[rounds/r101_probe-fallback]]

## bp35's window, looked at rather than reasoned about

crag reports "window does not belong to this board" and scores 0.60/0.565 against its 0.82
threshold. Three explanations for a stitch that cannot place a window, each measured on the level-6
board:

- **moving terrain** — only **12 of 4096 cells** change under twelve inert actions, and all twelve
  are background. The board is static; the disagreement is not things moving.
- **a horizontal pan** (crag's stitch searches VERTICAL shifts only — `self._world.get((r + shift,
  c))` leaves the column alone, because its docstring records a board three to four times deeper
  than the window) — measured by fitting the best row and column offset after each direction:
  **best shift 0 on BOTH axes, fit 0.989**. The camera does not pan, and no action moves more than
  1.1% of the board.
- **a transitional frame** — the board is already stable at the instant the level is entered.

So the three cheap causes are out, and what remains is inside crag's own `_readings` — the glyph
quantisation the world is built from. That is where a bp35 dig should start, and it should start by
dumping those readings rather than by reasoning about them.

⛔ A note on the instrument: the first version of this probe printed nothing and exited 0, because
an edit that replaced the tail of the file removed `if __name__ == "__main__": main()`. A script
that defines its work and never calls it looks exactly like a script whose measurement came back
empty.

## bp35 PARKED — the stitch's own numbers, dumped rather than reasoned about

Following this page's own instruction. At the moment crag declares the window foreign, on level 6:

```
READINGS pitch=6 origins=6 world=100 top=[(0.48,69,90) (0.49,49,100) (0.53,59,100) (0.57,69,100)]
                                          (score, cells compared, cells in window)
ORIGINS  in_use=(0,0) offered=[(0,0) (1,0) (2,0) (3,0) (4,0) (5,0)]  body_rows=[4,4,4,4,4,4]
```

- **Every offered origin has `ox = 0`.** Six candidates that differ only in the ROW sub-cell origin.
  The code does widen it (`oxs = {self._ox} | {fitted[1]}`) but `_best_origin` returns 0 on this
  board, so horizontal placement is never varied. Whether 0 is right is not established.
- **The 0.60 headline is a small-sample artefact**: it compares TWENTY cells. The well-supported
  candidates compare 69-79 and score **0.55-0.57**. So the disagreement is real, over a solid
  sample, and lowering the threshold cannot fix a placement that is genuinely wrong.
- The world holds 100 cells and a window holds ~100 — crag has accumulated roughly ONE window, and
  the very next reading disagrees with it at every offered offset.

⛔ **My own pan test was INVALID and nearly banked as fact.** It fitted row and column shifts after
LEFT/RIGHT/UP/DOWN and reported "best shift 0 on both axes, fit 0.989" — but 0.989 means those
actions changed almost nothing. Concluding "the camera does not pan" from actions that did not move
anything is the same error shape as reading a maximum without its sample size. The camera during an
actual FALL has still not been measured.

Deaths are NOT involved: every failing frame is `NOT_FINISHED`, at steps 6-14 of the level, which
matches crag's own docstring — "the tool went blind eight actions into the level".

**Next step, named**: dump the window and the stored world side by side as grids at the moment of
disagreement, and see WHICH cells differ. Everything above narrows where to look; none of it says
what the 40% actually is.
