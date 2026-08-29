---
round: R101BP35ATT
axis: generic tools — crag (shaft/platform family), attempt accounting
keywords: [bp35, crag, level restart, attempts, alignment, window does not belong, re-seed, empty path, graph, measured negative]
verdict: MEASURED NEGATIVE — bp35's collapses are NOT wa30's replay disease; the silence is fixable and fixing it moves the score by NOTHING
commit: see scripts/rounds/R101BP35/COMMIT
---

> bp35's seven collapses are seven DIFFERENT attempts, so the wa30 mechanism does not apply. The
> real wall is that `crag` loses its map on board 6 and hands the game to `graph`. Re-seeding the
> map fixes the silence and changes the score by nothing — and creates the wa30 disease in the
> process. 0.2220 unchanged; the remaining headroom is on the boards it already clears.

# bp35 — the collapses are not replays, and repairing the silence buys nothing

## The question, and the answer

Taken from wa30: *are bp35's seven collapses seven attempts spent as one?* **No.** Measured through
a scorer-faithful loop (`scripts/_bp35_diag.py`), the eight attempts on the wall board are **eight
distinct action sequences** — `distinct/total = [8, 8]`. Nothing is being replayed. wa30's failure
was a tool that could not see a restart; bp35's tool sees them and already carries a lethal-glyph
vocabulary across them.

## What bp35 actually is, attempt by attempt

    done=0  18 CLEARED   crag
    done=1   8 SPIKE     crag        \
    done=1  34 SPIKE     crag         > board 2 costs 85 actions against a human 48
    done=1  43 CLEARED   crag        /
    done=2  45 CLEARED   crag
    done=3  23 CLEARED   crag
    done=4  14 SPIKE     crag        \
    done=4  14 SPIKE     crag         > board 5 costs 58 against a human 33
    done=4  30 CLEARED   crag        /
    done=5  65 CLOCK     crag 13, graph 51      <- crag hands the board over here
    done=5  64 CLOCK     graph   x6             <- and never speaks again
    done=5  51 RUN_END   graph

Two loss modes, separated by the counter at death: at 64 it is the clock (levels 1-6 allow 64, 7-9
allow 128, 10 allows 192 — `render_interface` calls `lose()` at the cap), below it a spike.

## Why crag goes silent — named, not assumed

`scripts/_bp35_silent.py` wraps its `_quit`. On board 6 it hands the turn back **eight times with a
single reason — `window does not belong to this board`** — its body position frozen at `(6, 8)`, its
world map 100 cells, `air`/`exit` both known. ⛔ It is **not** `_refuted` and its `_mute` is 0: the
kill switch never fires. The harness simply retires a tool that keeps returning nothing.

`scripts/_bp35_lost.py` then separates the three faults hiding behind that one word, because
guessing between them is how R101SILENT's thirteen reverted repairs happened (**`alignment
threshold` and `admissibility bypass` are both on that list** — A and B below have each been tried
blind already):

| fault | measured |
| --- | --- |
| A: physics refuses every shift | **No.** Once `allow` goes `None`, 0 of 168 pairs are refused. |
| B: the threshold is too tight | **No.** Best agreement **0.60** against a 0.82 threshold — not close, and stable across all eight events. |
| C: the window is genuinely not this board | **Yes.** 100 pairs scored, top five 0.60/0.60/0.60/0.60/0.565. |

⛔ **And lowering the threshold is the one thing that must not be done.** `_stitch`'s own docstring
records that a window laid fifteen rows off its home still agrees nine cells in ten; accepting one
such false fit taught the tool that a block reverses gravity and cost it every later board. 0.60 is
worse than the false fit already paid for.

## The repair, and its measured verdict

Candidate, and it is the wa30 lesson in general form — **positional state that no longer matches the
board is worse than no positional state**: after N consecutive losses, throw the MAP away and
re-seed from the current window, keeping the vocabulary (`_lethal`, `_open`, `_solid`, `_swap`,
`_flip`), which is about the game's glyphs and stays true.

    control                     5 levels, 730 actions   crag hands over after 13 actions
    re-seed after 3 losses      5 levels, 730 actions   crag KEEPS the board for 4 whole attempts
    re-seed after 1 loss        5 levels, 730 actions   same
    _ALIGN_FIT 0.82 -> 0.55     5 levels, 730 actions   crag survives 29 actions, still hands over

**It works mechanically and it is worth nothing.** crag goes from 13 actions on board 6 to four
complete 64-action attempts, and the score does not move.

⚠️ **And it CREATES the wa30 disease.** Holding the board, crag emits the identical 64-action losing
sequence `9d60301b0a` three times running. The control's attempts looked varied only because
`graph` was driving them. So the two findings compose: repairing an EMPTY path exposes the replay
problem underneath it, and neither alone is the score.

⛔ Not shipped. Zero score change, and it replaces a tool that hands over with a tool that repeats
itself — worse in kind at equal score.

## Why board 6 is not reachable from here at all

A previous agent proved offline that crag's candidate rule **excludes every solution** to board 6
(24,644 states, 74,615 nodes, zero wins at allowance 64 AND at 200, 9 of 9 runs) and that widening
it costs 4.6x the search plus two more knobs for +0.0053 — and declined to ship it. The re-seed run
is an independent LIVE confirmation: it hands crag exactly what the offline proof assumes it lacked
— a fresh, correct map and four full attempts — and crag still does not clear.

## ⭐ Where bp35's headroom actually is: the boards it ALREADY clears

Not the wall. Per level, from the gate baseline:

| level | agent | human | score | composition |
| --- | --- | --- | --- | --- |
| 2 | 87 | 48 | 0.3044 | 8 spike + 34 spike + **43 cleared** |
| 5 | 60 | 33 | 0.3025 | 14 spike + 14 spike + **30 cleared** |

**The winning attempt is already faster than the human on both** (43 < 48, 30 < 33). Every point
lost there is exploratory deaths, not slowness. Removing them takes bp35 from **0.2220 to 0.3304 —
+0.108 on the game, +0.0043 on the 25-game mean** — comparable to what a board-6 clear would pay
(6/45 weight), and it does not need board 6 solved.

⚠️ But they are not repeated mistakes and no restart bookkeeping reaches them. `_learn_death`
already strikes the exact `(place, axis, action)` and only names a glyph lethal on an *unexplained*
landing; the two deaths per board are the cost of discovering which drawn kinds kill, and the tool
deliberately gambles on unseen ground ("unseen ground is the better bet"). Closing that gap needs
lethality read from the FRAME before it is touched — a perception capability crag does not claim,
and a different round.

Related: [[r101_wa30-level-restart]], [[r101_silent-specialists]], [[r101_allowance-ledger]]

---

## ⭐ THE ANSWER TO THIS PAGE'S CLOSING QUESTION — the killer IS readable, and one of the four deaths was free (2026-08-30)

This page closed on *"closing that gap needs lethality read from the FRAME before it is touched — a
perception capability crag does not claim, and a different round."* That question is now a
measurement rather than a hope.

### The census: a lethal glyph is PERFECTLY distinguishable before contact

`scripts/_bp35_glyphcensus.py` plays bp35 through the scorer's own agent factory, reads every frame
with **crag's own** `fit_lattice` / `read_lattice`, maps each screen cell to its board cell through
the camera, and files the cell's signature against the sprite names the ENGINE has there.

```
730 actions, levels 1-6            10 distinct signatures seen
signatures that are LETHAL-only     2      covering  5,049 cell reads
signatures covering BOTH a lethal cell and a safe one     0
alignment self-check      72,900 aligned : 100 unaligned
```

⛔ **Zero ambiguity.** The two lethal signatures are

```
ubhhgljbnpu   {5:4, 15:12}                levels 2,3,4,5,6    2,279 reads
hzusueifitk   {0:1, 5:4, 11:2, 15:9}      levels 5,6          2,770 reads
```

⚠️ But the colours are NOT a marker. `ubhhgljbnpu`'s ink set `{5,15}` is shared with the safe
pass-through decoration `jcyhkseuorf` `{5:6, 15:10}` and with the copier's animation frame; only the
exact pixel COUNTS separate them, which is what `_sig` already is. And nothing in the frame says
which of the ten kinds kills — **distinguishable is not identifiable, and one death per drawn kind
is irreducible.** (Cross-check from the source: `_body`'s docstring already says "one of the body's
colours is shared with a hazard on the later boards" — that is colour 11, the player's `r` pixels
and `hzusueifitk`'s `x` pixels, and the census finds it independently.)

### What the four deaths actually are — two are the price, two are DELIBERATE

`scripts/_bp35_deaths.py` wraps `_learn_death`; `scripts/_bp35_blind.py` wraps `_take` and records
the verdict of every emitted leg. Over the same 730-action run:

```
L2 a25   verdict "blind"   names ubhhgljbnpu           <- discovery, irreducible
L2 a59   verdict "dead"    names NOTHING (blind=None)  <- _stranded ENDING the attempt on purpose
L5 a184  verdict "blind"   names hzusueifitk           <- discovery of the SAME ART FLIPPED
L5 a198  verdict "dead"    names NOTHING (blind=None)  <- _stranded again
```

⛔ **The two `blind=None` deaths are not a defect.** `_search(…, "end", …)` is the one caller that
`return`s a `"dead"` leg, and `_stranded` uses it: walled in, the attempt is over whatever happens
next, and dying in two actions beats serving out thirty of clock. Exactly **2** of the 229 legs
emitted in the run carry verdict `"dead"`, and both are that. Do not "fix" them.

⇒ **Of bp35's four spike deaths, exactly ONE was avoidable**: L5's, because `hzusueifitk` is
`ubhhgljbnpu` reversed and crag had known that kind lethal since board 2.

### The fix: a face window that is closed under the flip

`_sig` is a histogram of `_cores`' window, which insets a pixel on BOTH sides — rows 1..p-2 of a
glyph drawn p+1 tall. The flip sends row r to row p-r, so that window is **not** flip-closed: rows
1..4 of a seven-row sprite map to rows 5..2. Rows 1..p-1 are equally this cell's own (only the last
row and column are shared with the neighbour) and that window **is** closed.

`_faces` reads it; `_mirror_join` names lethal any kind whose single face is the flip of a
known hazard's single face. `_sig` is untouched — every routing decision still runs on the
histogram, and the face is a side table nothing else reads.

⛔ **It has to run at SIGHTING time, and the first version did not.** Hung off `_learn_death` the
rule is INERT and measures so — bp35 `0.221988` with **zero joins**, identical to baseline to six
places. The twin is not on screen when the first kind is named (it belongs to a board three levels
later), and by the time it IS named it is already lethal and there is nothing left to join. Rule 7g,
paid in one run: the branch existed, could fire, and did not.

### Measured

```
                        L1   L2   L3   L4   L5    game
baseline (R101WA30)     18   87   45   23   60    0.221988
with the mirror rule    18   87   45   23   46    0.245560     +0.0236
```

Levels 1-4 byte-identical; L5 60 -> 46 = the 14-action discovery attempt, gone. Deterministic 3/3.

**Blast radius measured, not assumed** — the same probe on thirteen other games
(`scripts/_bp35_score.py`, one title per fan slot): `ar25 ka59 m0r0 r11l sk48 sp80 tu93 vc33` all
1.000000, `ls20 0.912085`, `dc22 0.714286`, `lf52 0.272727` — **every one equal to the R101WA30
baseline, and `mirror_joins` EMPTY on all thirteen.** The rule fires exactly once in the whole set.

Guards, each pinned in `tests/test_crag_mirror.py`: the join is refused unless BOTH kinds have been
drawn with exactly one face (a histogram two arrangements share can never drag a kind in), refused
for any kind the body has already stood on unharmed (an observation outranks an inference), and it
only ever COPIES a verdict — with no hazard named, shape alone names nothing.

### What is left on bp35

L2's 87 is `7 discovery + 34 walled-in + 43 clear`, and the winning attempt still beats the human
(43 < 48). The remaining headroom is `_stranded`: the tool reaches a pocket after 34 actions on
board 2 and after 14 on board 5, and ending the attempt early is the best move ONCE THERE. Not
walking in is a different round. ⛔ Level 6 stays closed — see this page's proof of absence above.
