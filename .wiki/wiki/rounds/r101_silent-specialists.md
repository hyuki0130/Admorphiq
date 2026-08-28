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

## The grids, side by side — and three more hypotheses killed with the treatment verified

The world and the window, one glyph per distinct cell signature, SHARING the glyph map so identical
signatures would print as the same letter:

```
  W 0 aaaaaabaaa      B 0 aaggggggba
  W 1 aacccbbbba      B 1 aaaaaaaaba
  W 2 aabbbbbaba      B 2 aaaaaaaaba
  W 3 aadddaaaba      B 3 ahhhahhhba
  W 4 aabbbbbbba      B 4 abibjbbbka
  W 5 aaaaaaeaaa      B 5 alllmlllna
  W 6 aabbbbbbba      B 6 aaaaaaaaaa
  W 9 aaffffffba      B 9 aaaaaaaaaa
```

They share only `a` and `b`. Every other signature in the window (g,h,i,j,k,l,m,n) is absent from
the world, and every one in the world (c,d,e,f) is absent from the window.

| hypothesis | test, with the treatment VERIFIED | result |
|---|---|---|
| the window is deeper than the search | shift range widened 4x, marker confirms span **-36..45** instead of -10..19 | best score **0.60/0.565, unchanged** |
| the camera scrolls horizontally | body column tracked while it ACTUALLY MOVES: 2->3->4->5->6->7->6->5->4, window always cols 0..9 | no horizontal scroll; columns are absolute and consistent |
| the disagreement is small-sample noise | cells compared reported alongside each score | the 0.60 uses 20 cells; the 69-79 cell candidates score 0.55-0.57 |

So: same columns, eighty-two vertical offsets, a board that changes 12 of 4096 cells on its own —
and no placement agrees. **The remaining suspect is the WORLD's own construction**, which crag's
docstring already warns about: "on a window that has just filled with rock, two origins tie and the
tie flips". If the first few readings of the level were taken at a wrong origin, the map is nonsense
and nothing will ever match it.

⛔ Note the shape of the last two entries. The horizontal test done EARLIER in this round used
actions that changed nothing and was invalid; redone on a body that actually moves, it gives a real
answer. Same hypothesis, same tool, opposite evidential value — the difference is whether the
treatment was applied.

## bp35, the answer: HALF THE SCREEN CHANGES INSIDE THE LEVEL

The last measurement of the chain, and it inverts the diagnosis.

```
PIXDIFF 1961 of 4096 | absorbed on level 5, now level 5
PIXDIFF 1968 of 4096 | absorbed on level 5, now level 5      (eight consecutive failures)
```

**Forty-eight per cent of the picture differs between the frame crag last absorbed and the frames it
then refuses — inside one level.** The body is one cell, about 36 pixels. Nothing about a moving
avatar can account for half a screen.

So crag is RIGHT to say "window does not belong to this board". Its map is not misbuilt and its
search is not too narrow: the board it is looking at is genuinely not the board it recorded, a few
actions earlier, in the same level. Every fix aimed at the stitch — the threshold, the shift range,
the origin set, the revival — was aimed at the wrong half of the problem, which is why all four
measured identical.

⛔ The confound was nearly published. The first version of this measurement compared against "the
last absorbed frame" without recording WHICH LEVEL that frame came from — and a level-5 frame
against a level-6 board would differ by half the screen for a trivial reason. Printing the level
beside the number is what made it a finding rather than an artefact.

**What bp35 actually needs**: a tool that expects the board to be rewritten mid-level. The world
model here assumes a static level that is merely revealed a window at a time — the assumption every
one of crag's clears depends on, and the one this level breaks.

## bp35, the cause: THE GRAVITY REVERSAL crag itself performs

Logging the harness's action beside crag's alignment failures:

```
ACT (6, (39, 33))            <- a click
LOST gdir=-1 origin=0        <- gravity is now REVERSED, and the stitch fails
ACT (3, None)  LOST gdir=-1 origin=0
ACT (3, None)  LOST gdir=-1 origin=0          ... and never recovers
```

**The first failure comes immediately after the click that reverses gravity, and the tool never
recovers.** That accounts for the 1,961 changed pixels: reversing gravity re-renders the whole
board. crag's own docstring anticipates exactly this — "the lattice ORIGIN moves when gravity
reverses ... the pixel origin moves under the tool's feet" — and at the moment of failure its
`origin` is still 0.

So the tool is defeated by a mechanic IT ITSELF INVOKES, and every fix aimed at the stitch — the
0.82 threshold, the shift range, the origin set, the pitch, the revival — was aimed downstream of
the cause. That is why all five measured identical.

⛔ Two of my own conclusions in this section were reached with actions that change nothing, and both
were wrong: "the camera does not pan" (lateral moves that did not move the body) and "the board does
not fill" (sixty lateral moves with a flat colour census, while crag's failure needs the CLICK it
makes). **An action that leaves the frame unchanged is not evidence about anything.** Third time this
round, and the first two were caught only because the treatment was verified afterwards.

**bp35's lever, named**: re-derive the lattice origin after a gravity reversal, or treat a reversal
as a new board rather than as a continuation. Not the threshold, not the range, not the pitch.

## Two fixes for the reversal, measured

With the cause named, the obvious repair was built and measured, then narrowed and measured again:

| change | bp35 |
|---|---|
| baseline | 0.2220 |
| a reversal is a NEW BOARD — drop the map, reseed from the current window | **0.0995** ⛔ |
| keep the map, re-fit only the pixel origin | 0.2220 (inert) |

Both results are informative and neither is a fix:

- **The map is load-bearing ACROSS a flip.** Dropping it costs 0.12 — more than half the game's
  current score — so the terrain genuinely is the same board after a reversal. "New board" is the
  wrong model of what a flip does.
- **The origin is not the obstacle.** Re-fitting it changes nothing, because the reading loop
  already offers every sub-cell row origin (measured earlier: six candidates, `oy` 0..5).

So what a reversal changes is neither the terrain nor the pixel origin: it is the FRAME the terrain
is indexed in. The map's rows are stored in the old gravity's sense, and after a flip the same
physical cell is a different row. The remaining candidate is a re-indexing of the map into the new
gravity frame — not a reset, not an origin re-fit.
