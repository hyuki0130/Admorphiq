---
type: reasoning
round: R101
axis: stage 1 of the top policy — develop the generic tools until they clear all 25 sample games
keywords: [tool-development, 25-of-25, stage-one, generic-tools, fan-out, selectivity, transfer,
  depth-vs-efficiency, attempt-vs-search, instrumentation, action-budget, adapters, per-game]
verdict: **ACTIVE — generic tools ALONE, zero adapters: 0.0200 -> 0.8602 over the 25, FIFTEEN
  games at 1.0000 (re86 0.9908 makes sixteen at or above 0.99), SEVENTEEN clearing every level,
  ~25 gates with cumulative regressions ZERO.** Method: one background agent per GAME owning two
  new files, the parent integrating ONE at a time, a full 25 on ceph deciding
  (`scripts/rounds/gate_tool.sh`). ⛔ The card is NOT the property that matters — the shipped
  `--agent kaggle_detect` scores 0.5422, so the thirteen adapters now COST 0.318 and only ls20
  earns its board (submission-affecting, the user's call). ✅ TRANSFER 0.9981, 13 of 14
  re-rendered games IDENTICAL. Load-bearing findings, each measured: a tool with no plan must bid
  0.0; DEPTH without efficiency is worth nothing (two extra levels bought +0.0011 where the same
  levels made cheaper bought +0.0304); a level LOST AND RETRIED is invisible in the score, and
  splitting a run into attempts took re86 from 0.8349 to 0.9908; COUNT how often each branch runs
  before tuning any of them; a guard whose condition can never be false is the commonest defect
  here. Open: bp35, lf52, s5i5, dc22, ls20, ka59, g50t, wa30 — 0.1219 of card, all assigned.
date: 2026-08-26
updated: 2026-08-27
---
# R101 — stage 1: develop the tools to 25/25

> Stage-one round: build frame-only rule-recovery tools until the 25 sample games clear. The
> generic path went 0.0200 -> 0.8602 in two days with zero cumulative regressions, and every
> number below was decided by a full-25 run rather than by a single-game probe.

Per `OPERATING_RULES.md` rule 0: I build the generic tools until they clear all 25 sample games;
only then does the LLM patch and combine them on hidden games. This round is stage 1.

## The diagnosis, all 25 games

`scripts/tool_stall_diag.py`, bare `UnifiedAgent`, 3000 actions each, run in parallel on ceph-build.
⚠️ This is NOT the deployed generic path (`--agent chained` puts `WorldModelAgent` first, which is
where cd82's 6/6 comes from), so these numbers compare with each other and never with GENERIC30's.

```
game    lv  states  trans  inert%  goal
lp85     1      14   1054    99%   yes     |
ft09     0      24   1610    99%   yes     |
vc33     0      57   1841    97%   yes     |
s5i5     0      59   2016    97%   yes     |  ELEVEN GAMES:
sb26     0     122   1416    87%   yes     |  most actions change NOTHING
dc22     0     101    812    86%   yes     |
m0r0     0      96    686    81%   yes     |
tn36     1     236   1550    76%   yes     |
cd82     0     190    958    75%   yes     |
sc25     0     161    991    73%   yes     |
r11l     1     421   1763    72%   yes     |

cn04     0    1079   2507    33%    NO     |  TWO GAMES: never draw a goal
sp80     0     964   2354    15%    NO     |

sk48 ar25 bp35 lf52 ka59 re86 tr87 wa30 tu93 su15 ls20 g50t
                                           |  TWELVE GAMES: expand and aim, still 0
```

## Three repairs, not one

**1. Inert actions — eleven games.** `ft09` tries 1,610 transitions and opens **24 states**: 1,586
attempts changed nothing. `lp85` is 99% inert over 1,054. The tool is not failing to search; it is
searching a space where almost every action it picks is a no-op. `dead_signature.py` exists in the
tool set for exactly this and is plainly not biting.

**2. No goal — two games.** `cn04` opens 1,079 states and `sp80` 964, both without ever drawing a
target. They have somewhere to go and no idea where.

**3. Expands, aims, still zero — twelve games.** `sk48` reaches 979 states with a goal and clears
nothing; `ls20` is 8% inert over 1,462 transitions. Here the search and the aim both work and the
plan does not.

⛔ These need different fixes and must not be attacked as one problem. The first is action-space
pruning, the second is goal inference, the third is planning.

## Where to start

Repair 1 is the largest group, has the sharpest signal, and already has a tool meant to do it. Start
by measuring why `dead_signature` does not prune on `ft09` — the most extreme case at 99% inert with
only 24 states opened.


## Reading the 25 game wikis: the tool set does not match what the games ask for

Before improving any tool, rule 0 now requires judging whether it is the right tool. Counting what
each game's own wiki page dwells on (mentions of simulation / win-condition / perception / sequencing
vocabulary across all 25 pages):

```
capability the games ask for              games mentioning it     tool that provides it
perception — occlusion, sensors,          25 / 25                 NONE (each tool improvises)
  frame-identifiable targets, colour-      lp85 75x, r11l 68x,
  blind detection                          ls20 41x, su15 37x
sequencing / assignment / multi-goal      25 / 25                 NONE
  coverage                                 re86 68x, r11l 37x,
                                           sb26 37x, lp85 36x
a faithful offline simulator              17 / 25                 world_model (measured 0/25 alone)
  g50t 33x, ls20 33x, sb26 28x, su15 27x
reading the win condition                  9 / 25                 llm_goal (fails with no LLM)
```

And the six tools we have:

```
graph        state-graph search      the only one clearing anything on 19 of 20 boards
toggle       exact GF(2) solve       one game (vc33)
paint        fill planning           one game (cd82, and only via the chained path)
world_model  online dynamics         measured 0/25 standalone
dealias      hash de-aliasing        an augmentation
llm_goal     goal inference          fails without an LLM
```

**The two capabilities every single game asks for — perception and sequencing — have no dedicated
tool**, while four of the six tools serve one game, or none.

⛔ **So `dead_signature`'s inertness is a symptom, not the disease.** The set was assembled from
solutions we happened to build rather than from what the games demand, and the harness runs ONE of
them at a time — while the games ask for perception AND sequencing AND simulation together. A tool
that must learn in the background cannot exist in a one-active-tool loop, which is exactly why it
learned 0 keys in 599 actions.

⚠️ This is a reading of what the wiki pages EMPHASISE, which is a proxy for what the games require —
a page can dwell on perception because perception was hard for us, not because the game demands it.
It is enough to show the mismatch is worth taking seriously; it is not yet a specification. The next
step is to derive the required tool set from the games' MECHANICS rather than from their pages'
vocabulary.

## Derived from MECHANICS: the 25 games are four classes, and `graph` fits one

Not counting page vocabulary this time — grouping the 25 declared mechanics by what each
structurally requires:

```
A. NAVIGATE an avatar through constrained space (goal = reach a cell)          7 games
   dc22 tu93 ls20 m0r0 g50t bp35 s5i5
   requires: an avatar identified by MOTION + reachability over blocked cells + a goal cell

B. TRANSPORT objects to places (goal = every item on its target)               6 games
   wa30 re86 ka59 su15 r11l lp85
   requires: object identity + a carry/attach model + PAIRING items to destinations

C. SET a configuration, then the board RESOLVES it (goal = the resolution wins) 5 games
   sp80 tn36 sc25 cd82 ar25
   requires: a faithful SIMULATOR of the resolution + search over CONFIGURATIONS, not actions

D. TRANSFORM the board by a discovered rule (goal = a target arrangement)      7 games
   ft09 sb26 sk48 tr87 lf52 cn04 vc33
   requires: the RULE induced from observed transitions + a target read off the board + ordering
```

**`graph` expands a state graph over ACTIONS. That is class A's shape and only class A's.**

* **Class C** needs search over CONFIGURATIONS. One configuration is tens of actions, so an action
  graph explodes before it reaches a second candidate — and the resolution (the spill, the program
  run, the cast) is a single step the graph cannot see inside.
* **Class D** needs the rule INDUCED first. Without it, every click is a guess — which is exactly the
  72-99% inert measurement: ft09 (class D) opens 24 states from 1,610 transitions.
* **Class B** needs assignment — which item to which destination — a question an action graph never
  poses.

That is the mismatch stated structurally rather than by word-count. **Eighteen of twenty-five games
are in classes B, C and D**, and the only tool that clears anything is built for class A.

⚠️ The classes are mine, drawn from the adapters' own one-line mechanic declarations. They are a
hypothesis about what the games demand, and the test is whether a tool built to a class's shape clears
its games — not whether the grouping reads well.

## T-D step 1 measured on ft09: the rule induces in 49 probes

Before writing `induce`, the premise was tested — can the rule actually be recovered from probe
transitions on the worst inert case?

```
ft09: simple actions = []  click = True     (click-only)
49 clicks on a stride-8 grid -> 8 of them change anything
   live cells: (36,36) (36,44) (36,52)
               (44,36)         (44,52)
               (52,36) (52,44) (52,52)
   each changes EXACTLY 38 cells, running along its own row from the click point
```

**A 3x3 lattice at stride 8 with its centre absent**, and every live cell flips the same 38-cell
footprint. That is a GF(2) toggle rule, fully specified by **49 probes**.

Against what the harness actually does on this game: **1,610 transitions to open 24 states, 99%
inert.** It is searching 4,096 click coordinates without ever noticing that only 8 do anything.

**So T-D's step order is not a design preference, it is the measurement:**

1. **Find the lattice** — probe on a stride, keep the cells that change anything. 49 actions here.
2. **Measure each live cell's effect** — the footprint it flips, as a vector.
3. **Solve in rule space** — GF(2) over those vectors toward the target read off the board.

Steps 1 and 2 cost ~60 actions and replace an unbounded guess with a solvable system. ⛔ The stride is
the one free parameter and must be derived, not fixed: 8 worked here because ft09's lattice happens to
sit on it, and a tool that hardcodes 8 is tuned to ft09. The generic form is to probe coarse, and
refine the stride where a change is found — which is the next thing to build and measure.

## `discover_lattice` measured on all 25, in parallel

`src/admorphiq/tools/induce.py` + `scripts/induce_probe.py`, 150-probe budget, run at once on
ceph-build (`scripts/rounds/INDUCE/probe.log`). The stride is derived, never fixed: the sweep starts
coarse, halves if nothing responds, and the reported PITCH comes from the responders' own coordinates
rather than from the sweep.

```
uniform operator — the rule is directly solvable
  ft09   8 responders   pitch 8    footprint [38]     <- the GF(2) system, in 64 probes
  lp85   2              pitch 56   [293]
  ka59  41              pitch 8    [1]
  m0r0  27              pitch 8    [2]

mixed footprints
  cd82 [1, 94, 95]   cn04 [1, 135, 136]   dc22 [1, 49, 129]   tn36 [1, 4, 70]
  sb26 [20, 40]      sc25 [9, 13]         su15 [33, 66, 77, 79]   r11l [1, 2, 53, 62]
  bp35 [1, 17, 26, 27]   lf52 [1, 9, 21, 25]   s5i5 [1, 2, 11]   vc33 [1, 2]   sp80 [2, 3]

no click action — a different class entirely
  g50t ls20 re86 tr87 tu93 wa30

NO RESPONSE in 150 probes, despite having a click
  ar25   sk48
```

**The headline**: on ft09 the harness spends 1,610 transitions to open 24 states at 99% inert. The
same board's complete rule — which 8 cells respond and what each flips — is recovered in **64 probes**.

⚠️ **The `1` in so many footprint lists is almost certainly a HUD counter**, not a rule response. sp80
cost a measurement earlier for exactly this: *"an edge-pinned 1-pixel HUD defeating scale inference"*.
Filtering single-cell changes that recur on every probe should collapse several of these to uniform
operators — that is the next change, and it must be measured rather than assumed, because a genuine
1-cell rule exists too (`ka59` reports `[1]` alone).

⛔ **`ar25` and `sk48` respond to nothing in 150 probes while offering a click.** That is a real
finding about them, not a tool failure: their click does something other than act on a lattice —
selection-then-commit, most likely. They are not class D on this evidence, whatever the grouping said,
and the classification owes them a re-read.

## The HUD filter, and why the obvious version could not work

The recurring `1` in the footprint lists was hypothesised to be a HUD counter. A frequency filter —
cells changing under 80% of probes — found **zero** on cd82, ft09 and ka59, so the hypothesis looked
wrong. Measuring what those single-cell changes actually are:

```
cd82: 40 probes changed exactly ONE cell, 2 changed many
  (4,4)  -> (63,63)     (4,20) -> (63,62)     (4,28) -> (63,61)     (12,4) -> (63,58)
  distinct cells among the forty: 40
```

**It is a progress bar filling one step per action**, marching right to left along row 63. It never
repeats a cell, so a frequency test scores it zero and it survives as forty "responders". The filter
had to be POSITIONAL: single-cell changes confined to an edge-pinned band, in aggregate.

⛔ The margin is `size // 16` — deliberately tiny, for the reason sp80's own HUD test records after an
earlier version there excused real board content as overlay. And the filter never empties a board,
because `ka59` answers with one cell and nothing else and that is a genuine one-cell rule.

**Re-measured on all 25, the picture changes substantially:**

```
game   responders before -> after   footprint            hud removed
cd82        42 -> 2                 [94, 95]                  40
dc22        33 -> 2                 [49, 129]                 31
cn04        29 -> 4                 [135, 136]                25
bp35        64 -> 8                 [17, 26, 27, 47]          56
lf52        64 -> 9                 [9, 21, 25, 57]           55
tn36        61 -> 5                 [4, 70]                   56
lp85         2 -> 2                 [293] -> [5]             288
vc33        50 -> 14                [2]  now UNIFORM          36
s5i5        50 -> 16                [2, 11]                   34
r11l        60 -> 50                [2, 53, 62, 66]           10
ft09         8 -> 8                 [38] uniform               0   untouched
ka59        41 -> 41                [1]  uniform               0   real rule preserved
m0r0        27 -> 27                [2]  uniform               0
```

**Most "responders" were the counter.** cd82's real response count is 2 of 64, dc22's is 2, cn04's is
4 — the tool had been reporting a progress bar as forty discoveries. And `lp85`'s footprint was 293
cells of which **288 were HUD**; its real effect is five.

**Uniform operators are now four** — ft09 [38], ka59 [1], m0r0 [2], and vc33 [2], which only became
uniform once its 36 HUD cells were removed.

⚠️ `ar25` and `sk48` still answer nothing in 150 probes. That stands as a finding about those two
games rather than about the filter.

## The HUD is a BAND, not single cells — and that revealed ft09's rule exactly

Measuring what one responder does colour-wise, rather than counting cells:

```
ft09, click (36,36) -> 38 cells changed
   colour 9 -> 8   x36 cells   rows 36-41, cols 36-41   = a 6x6 TILE
   colour 12 -> 11 x2 cells    row 63                   = the counter
```

⛔ **The counter moved TWO cells, so the `len(delta) == 1` filter could not see it.** A progress bar
is defined by WHERE it sits, not by how many of its cells move at once. The filter now removes the
edge-pinned BAND — and only the part of a delta that falls in the band, never a whole response — with
two guards so a board whose real rule lives at the edge is not gutted: at least three distinct band
cells, and no band cell touched by more than half the probes.

```
game   footprint before -> after   hud   uniform
ft09   [38] -> [36]                 16   YES   <- exactly the 6x6 tile
cd82   [94, 95] -> [94]             41   YES   <- became uniform
ka59   [1]                           0   YES
m0r0   [2]                           0   YES
```

**Five uniform operators now**, and ft09's rule is fully recovered: **eight responders on a stride-8
lattice, each toggling its own 6x6 tile from colour 9 to 8.** That is a GF(2) system, and the target
is on the board — the adapter's own decode records it as glyph constraints, *"ink colour 0 means the
cell's colour must EQUAL that glyph's marker; ink colour 2 means it must DIFFER"*.

⚠️ `lp85` went the other way: it filtered 288 HUD cells under the single-cell rule and filters 0 under
the band rule. With only two responders the "no band cell touched by more than half the probes" guard
cannot separate a counter from a rule — two samples are not a distribution. That is a real limit of
the guard on sparse boards and is not yet fixed.

## ft09 CLEARED from the induced rule — 4 clicks, nothing hardcoded

The full chain, every step from the frame:

```
1. discover_lattice        8 responders, pitch 8 INFERRED from their own coordinates
2. the lattice point that does NOT respond   -> that is the glyph's seat
3. read the glyph          3x3 compass of 2x2 pixels; centre pixel is the MARKER
                           marker = 8,  ink = [[0,2,2],[0,8,0],[0,2,2]]
4. derive the target       ink 0 -> this tile must EQUAL the marker
                           ink 2 -> this tile must DIFFER from it
                           compare against each tile's current dominant colour
   -> clicks needed: (36,36) (44,36) (44,52) (52,36)

executed -> levels_completed = 1, in FOUR actions
```

**No game id, no coordinate constant, no stride constant.** The pitch came from the responders, the
glyph's seat from which lattice point stayed silent, the marker from the glyph's own centre, and the
target from the ink-versus-marker comparison.

For scale: the harness spends 1,610 transitions on this board to open 24 states at 99% inert. The
game-specific adapter clears it in 4 actions — **the induced generic path matches that**, on a rule it
recovered rather than one written into it.

⚠️ One level, one game. What it establishes is that the T-D chain closes end to end: probe -> lattice
-> rule -> target -> plan -> clear. What it does NOT establish is that the glyph reading generalises
— ft09's compass is one target encoding, and sb26, sk48, tr87, lf52, cn04 and vc33 will each display
their target differently. The next step is deeper levels of ft09 (do the glyphs change?) and then the
same chain against a second class-D game.

## The stencil chain, measured to 4 of 6 levels on ft09 (2026-08-27)

`scripts/glyph_stencil_probe.py` clears **ft09 levels 1-4 in 62 actions** with no game id, no
coordinate constant, no tile size and no pitch written down. Every one of those is derived, and
each derivation below was WRONG first and fixed by a measurement, so the failures are the
content of this section.

| # | What broke | The measurement that named it | The rule that replaced it |
|---|---|---|---|
| 1 | probing the whole 64x64 | the first probe changed 3,140 cells and nothing responded after | a click outside the board is fatal; probe inside the board |
| 2 | "the panels are a recap screen" | ACTION1 (illegal — `available_actions == [6]`) produced the SAME 3,556-cell change | it is a reset screen, not a panel switch. WITHDRAWN |
| 3 | "the tiles are a magnified copy of the glyph, so the rule is a tautology" | level 1's board is UNIFORM colour 9 before any click | the rule is real: paint the stencil onto the lattice. WITHDRAWN |
| 4 | connected components find 36 tiles at pitch 2 | the live board is ONE 900-cell component — its colour-4 frame touches every tile | `_peel`: a component far larger than its siblings is a CONTAINER, not a tile |
| 5 | pitch taken as the smallest gap | two unrelated panels sit 2 pixels apart, so every neighbour lookup missed | pitch is the COMMONEST gap, never the smallest |
| 6 | the plan clicked panel tiles | a panel click is an out-of-board click, i.e. #1, i.e. fatal | the container marks the LIVE region — a frame is the game saying which panel is live |
| 7 | ink role inferred from frequency | both inks appear exactly four times on level 1 | read the code off the WORKED EXAMPLES on screen; a panel counts only if its ink->colour map is one-to-one |
| 8 | the code stored as ink -> absolute colour | level 1 paints in colour 8 and level 2 in colour 12, so the code was dead one level on | store ink -> ROLE (marker / not-marker) and CARRY it: level 2 ships no worked example at all |
| 9 | only the "paint this" half of the stencil was acted on | level 3 starts MIXED, and two of its four stencils demand cells that must NOT carry the marker | a stencil states both halves; target = marker or the other palette colour |
| 10 | a batch plan executed across a level boundary | the frame after a level-up still shows the board just finished, so level 2's plan ran level 1's board | replan after EVERY click |

⛔ Two of these (#2, #3) were stated here as findings and then withdrawn by the next
measurement. Both were reached by reading a board and reasoning; both died to one probe.

**Where it stops.** Level 5 is a different size of problem: 38 tiles, 11 stencils, four inks
(0/2/3/6) where levels 1-4 used two, markers 14 and 15 side by side, stencils whose neighbours
run off the board (`None`), and several tiles that are themselves 14/6 checkerboards rather
than plain. The two-colour target model cannot express it. Open, not failed.

**Level 5's shape, banked** — the stencils at (12,22), (28,22) and (44,38) are IDENTICAL
`[[14,6,14],[6,14,6],[14,6,14]]` checkerboards, which is not a stencil alphabet, so the
tile/stencil split ("more than one colour means it instructs") is the next thing to falsify.


## What the stencil tool transfers to: ft09 and nothing else (measured 2026-08-27)

Swept over all 25 sample games. ft09 4 levels / 62 actions; **every other game 0 levels in 3
actions** — the tool finds no plan, spends three idle clicks and withdraws. So it is not a
general tool; it is one MECHANISM's tool with a 0/24 false-positive rate, which it earns by
recovering the rule rather than by recognising the game.

That is the honest scale of stage 1: covering 25 sample games means roughly this much work per
mechanic, and the harness needs the tool to be cheap when it does not apply. Three actions is
cheap.

**Lattice census** (`scripts/lattice_census.py`, one frame per game, zero actions): only
**ft09 (36 tiles, side 6, pitch 8)**, **tn36 (33 tiles, side 4, pitch 4)** and **lp85 (20
tiles, side 4, pitch 6)** present equal square tiles on frame 1. ⛔ The other 22 score zero
because the DETECTOR wants a solid square single-colour block — a sokoban grid whose walls run
together reads as one component. The census is evidence only in the positive direction; its
zeros say nothing about the games.

Next target: **tn36** — a genuine 4x4-tile lattice at pitch 4 with one marked tile, and the
game whose brittle solver drove a bit-encoded program straight into the engine, so a rule
recovered from frames is exactly what it has been missing.


## Promoted to a harness tool (2026-08-27)

`src/admorphiq/tools/stencil.py` — `StencilTool` on the `base.Tool` contract, so the mechanic
is something the runtime model can be handed rather than a script only I can run. The probe
script now imports from it: ONE implementation, and the ft09 walk is byte-identical after the
move (4 levels, same per-level tile counts and pitch).

`detect` is the load-bearing half for the harness. It returns 0 on a frame with no lattice,
0.4 when a lattice with a marked tile exists but yields no plan, and 0.9 when it has clicks to
make. That is what makes it cheap on the 24 games it does not fit — measured, three actions to
withdraw.

Pins in `tests/test_stencil_tool.py`, engine-free (frames built in the test), covering the two
traps that cost the most: the frame that merges the board into one component, and the pitch
read off two unrelated panels sitting 2 pixels apart. 1760 tests pass.

## tn36's interaction surface, decoded but NOT solved (2026-08-27)

The lattice census pointed here and the frame reading was cheap, so it is banked rather than
left for the next session to re-derive:

* the board is a brick-offset lattice of 4x4 tiles (even rows at cols 14/22/30/38/46, odd rows
  offset by 4), inside a bordered box at rows 8-47;
* **clicking a tile does nothing at all** — the only cell that changes is one pixel at row 1,
  which marches left by one per action. That is an action counter, i.e. a HUD;
* the input is a row of **five bit slots** at cols 21/26/31/36/41, rows 44-46, pitch 5. Colour
  5 is off and colour 1 is on, and a click on a slot toggles it. Initial value off/on/off/on/on;
* a large colour-9 disc sits at rows 51-59. Clicking it lights it (69 cells 9 -> 10) and the
  next click elsewhere unlights it. ⛔ It is NOT a run trigger — pressing it moved none of the
  30 colour-11 cells, and four following ticks moved nothing either.

So the thing that consumes the five bits has not been found. That is the open question, and it
is a question about the board, not about the strip.

**Correction, measured the same day: the disc IS the submit button, and submitting a wrong
answer ENDS THE GAME.** A sweep of the 32 bit patterns — set the bits, press, read
`levels_completed` — died after the THIRD press with an empty frame. So the earlier reading
("pressing it moved nothing, therefore it is not a run trigger") was right about the frame and
wrong about the button: nothing moves because the answer is wrong, and the game is counting.

**What the level data says (read 2026-08-27, no engine):** levels 2 and beyond carry a
`Programs` list — one entry per piece, e.g. `[[1,1,1,1],[33,33,33,33]]` on level 2 and
`[[3,3,3,3],[33,33,33,33],[34,34,34,34],[2,2,2,2]]` on level 3 — alongside `Positions`,
`Rotations` and `Reset`. The values are small integers with bit structure (33 = 0b100001,
34 = 0b100010), which is the bit-encoded program the five slots compose.

⛔ **Level 1 carries NO data at all.** So the five bits cannot be looked up even in principle on
the level a tool meets first; they have to be DERIVED from the board. That closes the question of
where the answer lives and leaves the harder one — what on the board determines it — open.

⛔ **tn36 cannot be brute-forced.** Roughly three attempts exist per game. The five bits have to
be DERIVED from the board — most likely from the 30 colour-11 cells, which is where a tool
should look next — and a tool that guesses here does not lose a level, it loses the game.

This is the second sample game measured to punish a wrong action (ft09 charges a level). Worth
treating as the default assumption rather than the exception: **a generic tool needs a reason
to act, not merely the absence of a reason not to.**


## ft09 level 5 is a WALL, and the wall cost levels before it was recognised (2026-08-27)

Two facts measured here, in this order:

1. **A wrong click on ft09 costs a LEVEL.** One click took the run from 4 cleared to 3; a run
   that kept clicking through level 5 spent 130 actions and went **4 -> 0**. This game does not
   merely waste an exploratory action, it spends the winnings.
2. **The neighbourhood model contradicts itself on that board.** Collecting every stencil's
   demand per tile found **4 tiles demanded in two colours at once**. So "each stencil
   constrains its eight lattice neighbours" is not what level 5 is doing.

Three fixes, each measured, two of which were wrong first:

* **decorated tiles are not stencils** — level 5 carries three identical
  `[[14,6,14],[6,14,6],[14,6,14]]` checkerboards. Read as stencils they taught the code two
  inks no real stencil uses. The discriminator: a stencil's CENTRE colour appears exactly once
  among its nine sample points, because a marker names one cell — itself;
* **"the other colour" comes from the tiles, not the markers** — reading markers first looked
  right for level 5 (all tiles start colour 14 while stencils name 14 and 15) and REGRESSED
  level 4, whose two-colour palette already answers the question. Palette first, markers only
  when the palette is a single colour;
* **stop on a REVISITED tile map** — the first guard demanded the outstanding-demand count fall
  on every click, which killed level 4: one click can retire one stencil's demand while breaking
  a neighbour's, so a legitimate plateau reads as failure. ⛔ And the state hash must cover the
  TILE MAP only — this game marches an action counter one pixel per action, so a whole-frame
  hash is unique every step and the guard never fired at all.

**Result: 4 levels in 60 actions, and level 5 now stops the tool instead of emptying it.** The
tool ends a game holding what it won. Level 5's actual mechanic is open.


## What probing COSTS, and what drives each game (2026-08-27)

`scripts/probe_safety_census.py`, 17 actions per game — twelve clicks on a derived grid, then
each of the five simple actions.

**Probing is free on all 25.** Zero levels lost, zero games ended, everywhere. ⛔ That NARROWS
the earlier reading: ft09 and tn36 punish a wrong **commit** (a tile click that contradicts the
stencil; a submit press), not looking. "Explore first" is affordable; "act on a guess" is not.

**What the engine declares legal** (`available_actions`, the authoritative answer):

| driver | games |
|---|---|
| click-only `[6]`-ish | ft09, lp85, r11l, s5i5, su15, tn36, vc33 |
| move-only | g50t, ls20, re86, tr87, tu93, wa30 |
| click + move | ar25, bp35, cd82, cn04, dc22, ka59, lf52, m0r0, sb26, sc25, sk48, sp80 |

⛔ **A visible change is not evidence that an action was accepted**, and the first version of this
census reported exactly that error: it scored all five simple actions as working on ft09, which
declares `[6]` alone — an illegal action draws a REFUSAL SCREEN, and the refusal is a change.
The column stays in the output next to `avail` so the discrepancy is visible rather than
smoothed away.

**Also measured, and also a fact about the instrument**: the HUD detector found nothing on any
game, because ft09's counter MARCHES — a different pixel each action — so no single cell reaches
the 80% threshold. The band filter that `tools/induce.py` already carries is what is needed here;
until then `resp` is inflated wherever a game has a moving counter.


## A guard that was preserving a counter and calling it a rule (2026-08-27)

`tools/induce.py` carried a "the filter never empties a board" guard, justified in its own
docstring as protecting ka59, which "answers with a single cell and nothing else ... a genuine
one-cell rule". **Measured: those cells are (63,63), (63,62), (63,61), (63,60) — one per probe,
marching right to left along the bottom row.** ka59 is inert to clicks at those positions and
the only thing moving is the action counter. The guard was protecting a HUD.

It cost exactly what a wrong guard costs: on vc33, where all 50 probes changed row 0 alone, the
sweep reported **50 responders on a board that answers nothing**, and that number was on its way
into a tool-selection decision.

Replaced by the counter's real signature — it MARCHES: its position advances monotonically with
probe order along one edge line, which no rule of a board does. After the fix:

| game | responders | pitch | footprint |
|---|---|---|---|
| ft09 | 8 | 8 | 36 (its 6x6 tile) |
| cd82 | 2 | 8 | 94 |
| s5i5 | 2 | 8 | 10 |
| vc33 | 0 | — | — |
| ka59 | 0 | — | — |

⛔ The lesson is the one already on `lessons/instrument_validity_20260825`, in a new guise: the
justification for a guard is a CLAIM about the data, and it decays. This one had been written
down, believed, and never re-measured. Pinned in both directions now — a sweep that is all
counter reports zero, and a real block response survives with its counter pixel stripped.


## Where a click does something, across all 25 (2026-08-27, counter-filtered)

`scripts/induce_sweep.py` — 64 probes per game at stride 8, HUD counters removed.

| shape | games | reading |
|---|---|---|
| **uniform footprint** — every response flips the same count | ft09 [36], cd82 [94], cn04 [135], s5i5 [10], lp85 [293] | a single operator: toggle / parity / paint. The stencil family's shape |
| two footprints | sc25 [3,9], sb26 [12,24], dc22 [48,128] | two operators, or one operator and a selector |
| many footprints | su15 (32 responders), r11l (49), bp35 (8), lf52 (9), tn36 (5) | position-dependent effect — a richer state, not one rule |
| **no response found** | ar25, g50t, ka59, ls20, m0r0, re86, sk48, sp80, tr87, tu93, vc33, wa30 | move-driven, or answering somewhere this sweep does not look |

⛔ The last row is about the SWEEP, not the games — it reads one layer and probes stride 8.
sp80 sits in it and is known to answer a placement with a twenty-layer spill. Recorded on the
script itself so the number is not quoted later as "these games ignore clicks".

**⛔ "Next tool target: cn04" — WITHDRAWN the same day, by measurement.** The single 135-cell
footprint is not an operator. cn04's colour-0 shape is 15x15 = 135 cells, and its clicks merely
BLINK it; the shape MOVES three cells per simple action (A1 up, A2 down, A3 left, A4/A5 right,
stopping at the wall). cn04 is a navigation game with a large moving body, which is `graph`
territory and not a new mechanic at all.

Two corrections follow, and the second is the useful one:

* **a uniform footprint means one operator OR one object** — a move leaves two disjoint congruent
  blobs (vacated + occupied) where an edit leaves one, and the sweep now reports which;
* **this sweep is CLICK-ONLY and therefore silent about movement.** Twelve games show no click
  response and every one of them is driven by the simple actions. So the map's real message is
  not "here are the induce games" but: **the click-driven mechanics are a minority, and the
  coverage gap for stage 1 is movement games walling at level 2** — which is exactly what the
  2026-08-26 measurement already said (`median 1.3x human on level 1, then stop`) and what this
  round had drifted away from.


## Why `graph` stops, named per game — and g50t taken apart (2026-08-27)

`scripts/tool_stall_diag.py` at 1500 steps on the move-driven games:

| game | states | transitions | inert | goal drawn | reading |
|---|---|---|---|---|---|
| re86 | 318 | 554 | 26% | yes | search / goal problem |
| tr87 | 266 | 596 | 18% | yes | search / goal problem |
| tu93 | 250 | 584 | 10% | yes | search / goal problem |
| **g50t** | **18** | 57 | **42%** | yes | **expansion problem — the frontier dries** |
| ar25 | 507 | 1215 | 43% | yes | search / goal problem |
| sk48 | 578 | 1356 | 44% | yes | search / goal problem |
| ls20 | 501 | 1174 | 9% | yes | search / goal problem |
| wa30 | 209 | 408 | 15% | yes | search / goal problem |

**The unified reading: seven of the eight open hundreds of states, draw a goal, and still clear
nothing.** That is not a perception failure and not an expansion failure — it is that the goal
being drawn is not the objective, or the search never heads for it. ls20 is the sharpest case:
9% inert, 501 states, and its hand-written adapter clears 7/7 at efficiency 1.0, so the game is
comfortably solvable and the generic tool is looking in the wrong direction, not looking too
narrowly.

Two of them (ar25 43%, sk48 44%) spend nearly half their actions on transitions that change
NOTHING, which is a second, independent and much cheaper defect.

g50t is the outlier by an order of magnitude, so it got taken apart. What is now MEASURED:

* **the player is a 24-cell colour-9 blob at (8,14)**, and there are THREE colour-9 regions —
  the player plus a 19-cell and a 1-cell piece at (49,43)/(52,46) that form the goal;
* **the move quantum is 6 rows**, one corridor cell;
* **the first action after a reset changes nothing.** Every sequence tried begins with a
  zero-delta action whatever that action is;
* **ACTION4 and ACTION5 never moved the player** in any probe.

⛔ **The action -> direction map is NOT fixed, and I could not identify the rule.** The
measurements contradict each other and are recorded as such rather than smoothed:
`A3` repeated from reset never moves; `A3` after `A2` moves down; `A1` moved down once and up
later from the same board; `A4` moved the player down in one episode and never in another.
Whatever governs it is not "action k is direction d", and the next attempt should start from
these traces, not from a story built on top of them.

⛔ **I walked straight into the trap this repository already records.** CLAUDE.md says g50t's
2/7 came from "ONE perception root-cause — two colour-9 blobs, diagnostics tracked the static
GOAL". My first three measurements tracked `min(row)` over all colour-9 cells and produced
displacement figures that mixed the player with the goal, and I reasoned on them for two rounds
before separating the components. **A recorded trap costs exactly what an unrecorded one costs
if the record is not read before the probe is written.**

⛔ Also: a probe that calls `arcade.make()` per trial measures only the absorbed first action.
Three sweeps reported g50t inert for that reason, including a BFS that concluded the game has
ONE reachable state.


## The tool is in the harness, and it costs the other games nothing (2026-08-27)

`StencilTool` registered FIRST in `harness/registry.default_tools()` — most selective first, so
the tool that is cheap to be wrong about is asked before the ones that always propose something.

**ft09 through the harness: 4 levels**, the tool chosen by the harness's own signature routing
(`click_fraction=1.00, has_movement=False`), with no LLM in the path.

**Verified no-op elsewhere.** Twelve games re-run at 1500 steps against the numbers taken before
registration: tu93 250/584/63, re86 318/554/148, tr87 266/596/109, g50t 18/57/24, wa30 209/408/64,
ls20 501/1174/113, ar25 507/1215/523, sk48 578/1356/604 — **identical in every field**. The
0/24 detect measurement holds inside the harness, not just in the standalone sweep.

Two extremes surfaced in the same run and are worth their own line:

* **vc33: 94% inert** — 1016 of 1071 transitions change nothing. Consistent with its click probe,
  where all 50 responders were the row-0 counter and the board answers nothing at stride 8;
* **lp85: 3 states, 100% inert, 1 level** — it clears a level and then every transition is a
  self-loop. Its adapter clears 8/8, so this is the widest generic-vs-adapter gap on the board.


## The inert-action tool was registered, unfed, unread, and lied to (2026-08-27)

`DeadSignatureTool` exists to stop the searcher spending budget on actions that do nothing. It
had **three independent defects, each of which alone made it a no-op**, and all three had to be
fixed before anything moved:

1. **Nothing ever called its pruning API.** `is_dead` / `live_actions` are referenced by exactly
   one line in the repository — inside the tool itself. Its own docstring says "the orchestrator
   ... consults [them] before spending an action". No orchestrator did.
2. **It was never fed a transition.** `harness/loop.py` feeds `observe` to the ACTIVE tool only,
   with a comment recording why (feeding every tool pollutes a graph's edges — a real
   measurement). An always-on augmenter is never the active tool, so after 400 steps it held
   **zero counters**. The rule is right for stateful tools and wrong for these.
3. **Its `changed` flag counted the HUD.** `changed = (prev != frame).any()` is true for every
   action on a board whose counter sits at the frame edge, so a board that is 94% inert reported
   **zero** inert action classes.

Fixes: an `augmenter` flag on the tool and a second `observe` pass in the loop; a `_board_changed`
helper that ignores changes confined to the outer band; and global `(action_class -> tried,
changed, distinct states)` counters exposed as `globally_dead`, consumed by the graph tool's
candidate list.

⛔ **Reordering was tried first and measured to change NOTHING** — byte-identical output on all
twelve games. With a budget that exhausts a state's candidates anyway, order decides when an
inert action is spent, not whether. Withholding is the lever.

⛔ **And one self-inflicted defect worth its own line**: the `deadsig` reference was assigned in
`GraphSearchTool.reset()` instead of `__init__`, so it was wiped on construction and on every
level-up. The wiring measured as PRESENT when the registry was called on its own and ABSENT in
every real run — two full measurement cycles produced byte-identical results before that was
found.

**Measured at 1500 steps, before -> after, no game lost a level:**

| game | states | inert | levels |
|---|---|---|---|
| g50t | **18 -> 562** | 42% -> 33% | 0 |
| tu93 | 250 -> 360 | 10% -> 9% | 0 |
| **cd82** | 190 -> 143 | 67% -> 74% | **0 -> 1** |
| **vc33** | 57 -> 59 | 94% -> 93% | **0 -> 1** |
| ar25 | 507 -> 517 | 43% -> 44% | 0 |
| re86 / tr87 / wa30 / ls20 / su15 / sk48 / lp85 | unchanged | unchanged | unchanged |

g50t's frontier no longer dries — the expansion failure diagnosed above was the searcher
re-learning the same dead clicks at every state. **lp85 remains the outlier**: 3 states, every
transition a self-loop, while its adapter clears 8/8.


## The card after the harness change: 0.3162, UNCHANGED (2026-08-27, ceph-build, full 25)

The repository's rule is that a change to the harness is a change to the card, so the shipped
configuration was re-measured: `scripts/rounds/R101CARD`, `--agent kaggle_detect`, budget 4000,
all 25 games, PAR=20 (load peaked at 11.8 against the 60 cap).

**Mean = 0.3162, exactly the recorded current card. No game moved.** The three deltas against
`R99CARD` (sc25 +0.0427, sp80 +0.1428, tn36 +0.0919) are the adapter ports landed after that
round was measured, not this change.

⛔ **So the bench gains did NOT reach the card, and that is the honest headline.** cd82 and vc33
each newly clear a level under the bare `UnifiedAgent`, and g50t's state count went 18 -> 562 —
but the shipped path runs `KaggleChainedAgent` (WorldModelAgent first, then the unified member,
at the deployed budget), and under it cd82 is already adapter-handled at 0.9463 while vc33 scores 1e-06 — it DOES clear a
level there, in 4,000 actions, which the squared metric prices at zero. And it cleared exactly
one level in the previous round too, so even that is not this change's doing. Levels tell the
same story: 74 -> 79 across the two rounds, entirely from sc25 (0->3), sp80 (1->2) and tn36
(1->2), all adapter ports. A number measured on the bare harness is not a number about the card,
and the two were being read as one thing until this run.

What the run does establish: **the harness change is card-neutral — zero regression across 25
games**, which is the gate that had to be passed before any of it could stay.


## What actually ships from this round (2026-08-27)

`kaggle_chained_agent.py` builds its unified member from `harness.registry.default_tools()`, so
**`StencilTool` is in the submission** and will fire on any hidden game carrying the mechanic —
alongside the augmenter fixes, which change how the searcher spends its budget on every game.

That is the part the card cannot show and the part that matters: the card is 25 PUBLIC games of
which thirteen are adapter-handled, and the eval is 110 PRIVATE ones. A tool that recovers a rule
from frames transfers by construction; an adapter that recognises a game does not. The card being
unmoved is therefore the expected result of this round, not a disappointing one — but it is also
not evidence the tool helps, and nothing here should be read as such until a hidden score moves.


## ⛔ The whole probing method was the wrong one (2026-08-27, user-raised)

Asked directly: "can't you work the sample games out from the DATA, without running them?" The
answer is yes, and it always was.

Each game is ONE python file holding its rules AND its data — a `sprites = {...}` table and a
`levels = [...]` list. Two scripts now read them: `read_sample_games.py` (action dispatch, win
and lose predicates) and `dump_sample_levels.py` (**all 25 games, 179 levels**, every sprite with
tags/position/size and the level's own data dict). Neither starts the engine.

**What that immediately retired from this very page:**

* "ft09 level 5 is a WALL — its neighbourhood model self-contradicts, four tiles demanded in two
  colours at once" -> the level's `cwU` palette has **three** colours and the model had two;
* "three identical checkerboard tiles, not a stencil alphabet" -> they are `NTi` sprites, whose
  mask is `[[0,0,0],[0,1,0],[0,0,0]]`: they toggle ONLY THEMSELVES;
* "the action->direction map is NOT fixed and the rule is unidentified" (g50t) -> `ACTION1..4` are
  up/down/left/right, and an action arriving while the avatar animates is swallowed;
* "probing is free on all 25" -> **six games LOSE when an action budget runs out**, and ft09's is
  in the data: 32, 32, 96, 96, 128, 128 per level.

Twenty live measurements on one game, ten of them correcting an earlier reading, produced a worse
answer than one command. The failures recorded above are real and the fixes stand, but the METHOD
that generated them was the wrong one and is now written into `OPERATING_RULES.md`.


The abstraction is now [[../concepts/action_budget]]; the timing trap that goes with it is
[[../concepts/swallowed_action]]; the mechanics read out of every game's own source are
[[../sample_games_mechanics]].

## The budget is READABLE from the frame — 9 of 13 recovered (2026-08-27)

`src/admorphiq/tools/budget.py` (`BudgetReader`). Watch the outer band, find the single row or
column where cells stop matching their initial value, fit the consumption rate along that line,
and divide. Measured against the budgets declared in each game's own level data, after **eight
actions**:

| game | declared | estimated |
|---|---|---|
| tu93 | 50 | **50** |
| vc33 | 50 | **50** |
| s5i5 | 50 | **50** |
| sp80 | 30 | 29 |
| su15 | 32 | 33 |
| re86 | 100 | 111 |
| ka59 | 100 | 111 |
| wa30 | 200 | 191 |
| dc22 | 128 | 148 |
| cn04 | 75 | 191 (over) |
| ar25 / ft09 / lp85 | 64 / 32 / 13 | **None** |

Nine of thirteen inside 30%, four of them essentially exact. The four misses return **None**
rather than a guess, which is the required behaviour: a wrong budget either strangles a game that
has none or licences overrun on one that does.

⛔ The defect worth recording: the first version counted the WHOLE edge band and overestimated
every budget by roughly fifteen times (768 where the game declares 50), because the static chrome
around the border went into the numerator. The indicator is a segment; the rest of the edge is
furniture. Pinned in `tests/test_budget_reader.py`, both directions — a board with no indicator
must return None, and an oscillating border must too.


## Stage one's scoreboard, and the one thing on it that works (2026-08-27)

`scripts/rounds/R101GEN` — the generic tools ALONE (`--agent unified`), full 25, budget 4000.
**Mean 0.0200** against the card's 0.3162. Level-1 cost against each game's DECLARED budget:

| game | levels | actions to clear L1 | human | declared budget | |
|---|---|---|---|---|---|
| **ft09** | 4 | **4** | 43 | 32 | **within budget, and super-human** |
| vc33 | 1 | 316 | 7 | 50 | over 6.3x |
| tu93 | 2 | 1119 | 19 | 50 | over 22.4x |
| lp85 | 1 | 924 | 17 | 13 | over 71.1x |
| sp80 | 1 | 3274 | 39 | 30 | over 109.1x |
| cd82 / lf52 / m0r0 / r11l / tn36 | 1 each | 150 / 59 / 604 / 73 / 73 | 55 / 32 / 30 / 22 / 32 | — | |
| ar25 bp35 cn04 dc22 g50t ka59 ls20 re86 s5i5 sb26 sc25 sk48 su15 tr87 wa30 | **0** | — | — | — | **16 of 25 never clear anything** |

**One tool on this board plays at human efficiency, and it is the one built today.** ft09 clears
its first level in FOUR actions where the human baseline is 43 and the game allows 32 — because
`StencilTool` recovers the rule and then acts, instead of searching for a state that satisfies an
inferred goal. Every searching path on the table is 6x to 109x over the budget the game declares.

⛔ **So the answer to "is this a hard algorithmic problem" is no, or at least not the hard part.**
The searching architecture is mis-specified for these games: it treats the board as something to
explore and the budget as something to spend, when the budget IS the loss condition and the
mechanic is recoverable from a handful of probes. Stage one needs more rule-recovery tools, not a
better search. The measurement that says so is this table.


## Second rule-recovery tool: TrackAlignTool (2026-08-27)

Built from the DATA, not from probing: `dump_sample_levels.py` showed lp85 level 0 as 19 tiles,
two buttons tagged `button_A_L` / `button_A_R`, one static marker, one goal tile, a 13-action
budget, and a win predicate reading "a goal sits at the marker's position". The tool recovers all
of that from frames — a closed loop of equal tiles, a static marker beside one slot, controls that
rotate the loop — and rotates to the computed offset.

**lp85 level 1 in FIVE actions.** The budget is 13, the human baseline 17, and the searching
generic path took **924**.

Three derivations were wrong first, each fixed by one measurement:

* the tile side is the one whose blocks form a closed LOOP, not the one that finds the most
  blocks — a 4x4 tile contains four 2x2 ones, so the smallest side always wins a count;
* the loop is found by PEELING blocks that cannot lie on a cycle, not by requiring every block to
  have two neighbours: the controls are blocks too, and have none;
* a control is COMPACT — the largest non-track blob on the board is the frame's own one-pixel
  border, and probing it spends an action to learn that a border does nothing.

**Transfer, measured**: swept over all 25, `track` fires on lp85 alone and costs **zero actions**
on the other 24 (it declines before proposing); `stencil` fires on ft09 alone and costs three.
Two tools, two mechanics, **0/24 false positives each**.

**Registered, and the regression that measured the registration**: the first version bid 0.3 for
"there is a loop here" even with no marker, and that took **ft09 from 0.4762 to 0.3819** on the
full 25 while lp85 gained 0.0278 — a net LOSS. A lattice that happens to contain a cycle is not
this mechanic, and a tool with nothing to propose must not compete for the turn. With `detect`
returning 0.0 instead, the re-run is clean:

```
generic tools alone, full 25:  0.0200 -> 0.0211
only lp85 moved (0.0000 -> 0.0278); ft09 restored to 0.4762; 23 games byte-identical
```

⛔ **The multi-ring attempt was measured and REVERTED (2026-08-27).** Loosening the ring reader
so it could see a three-ring board made the track tool fire on ft09's lattice: **ft09 0.4762 ->
0.0476, mean 0.0211 -> 0.0037** on the full 25, while the standalone ft09 probe still scored 4
levels the whole time. A 20x net loss bought by a gain of zero. Reverted; the full 25 re-run is
byte-identical to 0.0211. The attempt is kept at `/tmp` only — what survives is the lesson,
[[../lessons/tool_selectivity_20260827]]: in a shared harness a tool's mistake steals another
tool's turn, so selectivity is a harder constraint than solving, and a single-game probe cannot
see the cost.

**Open**: lp85 level 2 is three CONCENTRIC rings with their own control pairs and 2-pixel tiles.
The reader now finds them (pitch candidates include multiples of the observed gap, because
adjacency at the base gap links the rings and the peel then deletes the whole track), and the
tool acts — 44 actions inside a 60-action budget — but does not yet clear it.


## Third tool: MirrorMergeTool (2026-08-27)

Built from the source read, not from probing: m0r0's `step()` shows that clicking a `sys_click`
marker SELECTS it, that 1-4 then move it, and that clicking empty space flips to a mode where
every marker moves at once with per-name MIRRORING; `next_level()` fires when no active marker
remains. The frame shows two mirrored mazes with one actor each.

The tool learns each control's per-actor delta from four probes — never assuming the mirror from
geometry — then BFS-plans the join over the joint state.

**m0r0 level 1 in 19 actions** against a human baseline of 30 and a searching generic path of
**604**. (A hand-run of the same plan takes 15; the tool spends 4 on learning the controls.)

Two ordering traps, both fixed by measurement:

* the delta must be keyed by which HALF an actor is in. The corner list is sorted, so the moment
  two actors' sort order flips, an index-keyed delta is applied to the wrong actor and every plan
  after that is fiction. This is the same trap that made a hand-written model look wrong when it
  was exactly right — the "mismatch" was two identical positions in a different order;
* the actor COLOUR must be pinned for the level. Re-picking "the rarest colour" each frame latched
  onto a different colour mid-plan and reported the actors at two opposite corners of the frame.

**Measured before keeping it** (the discipline this round paid for): full 25, generic tools alone,
`0.0211 -> 0.0230`, **only m0r0 moved** (0.0001 -> 0.0476), and the shipped card is unchanged at
0.3162. 1769 tests pass.

**Open**: m0r0 level 2 adds obstacle sprites and the tool overruns the 150-action budget.

## Stage one standing, three tools in

| | generic tools alone | card (with adapters) |
|---|---|---|
| start of round | 0.0200 | 0.3162 |
| now | **0.0230** | 0.3162 |

ft09 0.4762 (stencil) · m0r0 0.0476 (mirror) · lp85 0.0278 (track) · the rest unchanged.
**3 of 25 games have a rule-recovery tool. 16 still clear nothing.**

⛔ **No Kaggle submission until the sample games are cleared** (user directive, 2026-08-27,
recorded in `OPERATING_RULES.md` above rule 6).


## How the build runs from here: fan out, then integrate (2026-08-27, user-set)

Serial tool work was stopped by directive — it leaves the 64-core box idle and spends a session on
one game, and this round measured what that costs: six or seven iterations on ONE level of ONE game
before the full-25 run revealed a net loss.

The protocol is now `OPERATING_RULES.md` rule 8 and [[../parallel_build_protocol]]: one background
agent per GAME, all launched together, each owning exactly two NEW files and forbidden to touch the
registry, the loop, the shared segmentation module, another agent's tool, or the git index. The
parent registers one tool at a time and runs the full 25 on ceph-build at PAR=25, keeping a tool
only when no game regressed.

**The load-bearing reason integration stays central**: selectivity is a property of the TOOL SET,
not of any one tool. No agent can see the cost its `detect` imposes on the other twenty-four games,
so no agent may decide whether its own work is kept.

First fan-out: **nine games at once** — ls20, tr87, su15, sb26, g50t, cn04, s5i5, sc25, re86.


## MILESTONE — all 25 sample games clear a level under the generic tools (2026-08-27)

```
generic tools alone, zero adapters, full 25 on ceph-build
  start of day   0.0200   ·  9 of 25 clearing  ·  0 rule-recovery tools
  end of day     0.2257   ·  25 of 25 clearing ·  19 rule-recovery tools
  cumulative regressions: ZERO
conquered: ar25 1.000 · sb26 1.000 · tr87 1.000
```

⛔ **"Clears" is not "conquered."** Six games — tn36 0.007, cd82 0.006, lf52 0.005, r11l 0.004,
vc33 0.000, tu93 0.000, sp80 0.000 — clear a level and spend so many actions that
`(human/agent)²` prices it at approximately nothing. The remaining work is not more tools; it is
solving inside [[../concepts/action_budget]].

## The last zero was a BID, not a solver (dc22)

dc22 was the final game at 0.0000. Its tool, `phase`, had been clearing **3 levels in 170 actions**
under its own probe the whole time. Traced through the harness: over 600 steps, `graph` took
**every single one**. The tool's `detect` returned **0.35** on its own board and lost every
comparison.

Raised to 0.85, with the hard constraint verified independently by the integrator — **0.85 on
dc22, 0.00 on all 24 other games** — the game went **0.0000 -> 0.2857** with nothing else
regressing.

This is the same lesson as [[../lessons/tool_selectivity_20260827]] read from the other side, and
both halves are now in every agent brief:

* bid too LOW on your own board and you never act — measured, one game at 0.0000 for a whole day;
* bid ANYTHING on a board you cannot solve and you take the turn from the tool that could —
  measured, 0.4762 -> 0.0476 on a game the offending tool never touched.

**A tool's confidence is not self-expression. It is a claim on someone else's budget.**


## ⛔ The remaining gap is DEPTH, not efficiency — my own diagnosis, corrected by measurement

I wrote that the low-scoring games "clear a level but spend so many actions that the squared
metric prices it at zero", and briefed a whole wave of agents on that basis. The per-level costs
say otherwise:

| game | score | levels | actions on L1 | human | ratio |
|---|---|---|---|---|---|
| lp85 | 0.0278 | 1 | **5** | 17 | 0.3x |
| tn36 | 0.0357 | 1 | 14 | 32 | 0.4x |
| s5i5 | 0.0278 | 1 | 13 | 20 | 0.7x |
| cn04 | 0.0476 | 1 | 18 | 29 | 0.6x |
| m0r0 | 0.0476 | 1 | 19 | 30 | 0.6x |
| su15 | 0.0222 | 1 | 17 | 22 | 0.8x |

**Every one of them clears its first level FASTER than the human baseline.** The score is low
because they stop at level ONE, and RHAE weights by level index: a first level out of eight is
`1/(1+2+…+8) = 1/36` of the game. Making level 1 faster is worth almost nothing; reaching level 2
is worth twice level 1, and level 8 is worth eight times it.

So the brief for the deepening wave is not "spend fewer actions" — it is **"reach the next
level"**, and the two questions to ask per game are (a) does the tool's mechanic even appear on
level 2, and (b) is the harness stopping it before the tool does.

⛔ This is the second time today a direction was set from a plausible reading of an aggregate and
corrected by opening the per-item breakdown — the first was reading a 5.6x card gain as progress
when the hidden score had not moved. **Before a number becomes a direction, look at the breakdown
that would refute it.**


## Where the day ended: 0.5241 on the generic tools alone

```
                       morning    now
generic tools only      0.0200    0.5241      26x
games clearing a level     9/25     25/25
conquered outright            0        10
cumulative regressions        —         0
deployed card (13 adapters)          0.3162   <- the generic path is now 1.66x past it
```

Conquered: **ar25 · sb26 · tr87 · cd82 · cn04 · r11l · tu93 · vc33 · tn36** (+ ft09 partial).

**Why the comparison with the card matters.** The card's 0.3162 comes from thirteen hand-written
per-game adapters, and the transfer failure is already measured: the card rose 5.6x while the
hidden score went 0.20 -> 0.18, because a private game carrying none of those thirteen mechanics
gets the generic fallback. The 0.5241 is that fallback. It transfers by construction — each tool
RECOVERS a rule from frames rather than recognising a game.

**tn36 is the sharpest single result.** It ENDS after about three wrong submissions, so brute force
is impossible in principle; `progbits` clears every level in 111 actions, which means the five bits
are being DERIVED from the board.

## The shape of what is left

Every remaining game has the same profile — fast on level 1, stopped by depth:

| game | score | levels | L1 actions | human |
|---|---|---|---|---|
| s5i5 | 0.028 | 1 | 13 | 20 |
| lf52 | 0.055 | 2 | 8 | 32 |
| g50t | 0.107 | 2 | 52 | 78 |
| bp35 | 0.133 | 3 | 15 | 21 |
| m0r0 | 0.143 | 2 | 19 | 30 |
| sk48 | 0.167 | 3 | 14 | **61** |
| sc25 | 0.244 | 3 | 18 | 36 |
| re86 | 0.269 | 4 | 25 | 26 |

⛔ **And every number on this page is the LLM-FREE fallback.** The deployed path asks a model to
name a tool, and exercising it for the first time today found that the model's menu AND its ranking
were both hardcoded to eight literal names — the tools built today were unnameable. Both are fixed;
the LLM path's 25-game score is still UNMEASURED and needs a GPU. See
[[../lessons/harness_owns_the_routing_20260827]].


## ft09 CONQUERED — and the "wall" was my own misreading

This round opened by recording ft09 level 5 as a wall: first "the two-colour target model cannot
express it", then "its neighbourhood model self-contradicts — 4 tiles demanded in two colours at
once". Both were concluded from live probes, without reading the game.

One command refutes it:

```
L3 data: cwU = [9, 8, 12]                     <- THREE palette colours, not two
L4 tags: Hkx 27, NTi 3    L5 tags: Hkx 0, NTi 22
elp (every level) = [[0,0,0],[0,1,0],[0,0,0]]
```

`Hkx` toggles its 3x3 NEIGHBOURHOOD; `NTi` toggles ONLY ITSELF — that is what the `elp` mask is —
and level 5 is entirely the second kind. A two-colour, one-operator model on a three-colour,
two-operator board is not a contradiction in the game; it is a model that stops early.

**ft09 now clears 6/6 in 80 actions**, level 1 in 4 against a human baseline of 43, with
`detect` = 0.00 on all 24 other games. Twelve of the twenty-five are conquered and the generic
path is at **0.6711**.

⛔ **A wall that has not been checked against the level data is not yet a wall.** Paid for twice
in this round: here, and on the game whose "action -> direction map is NOT fixed and the rule is
unidentified" turned out to be up/down/left/right with actions swallowed during animations.

## The LLM path had never been measured at width (2026-08-27)

Every number on this page — `0.0200 -> 0.6825`, eleven games conquered — was measured on the
**LLM-FREE fallback**. `harness/loop.py` drops to signature routing whenever the llm call
raises, and the ceph round runners name no model, so that is what ran. ceph-build has no GPU
and one 26B model on its shared CPUs takes about 37 cores, which is why the shipped path
stayed unmeasured for the whole round.

`notebooks/r101_llm_full25.py` measures it on a Kaggle GPU kernel: both arms through the same
runner subprocess, differing only in whether a served model is named. Four defects were found
and fixed BEFORE the first push, each of which would have cost a session — the openai path
reads `HARNESS_LLM_MODEL` and not `HARNESS_MODEL`, so the wrong name makes every call raise
and the LLM arm silently BECOMES the fallback arm; setting the vars globally leaked the base
URL into the fallback arm, producing the same collapse from the opposite direction; the runner
is not under `scripts/` on Kaggle because `--dir-mode zip` strips the top level; and a model
mounts several levels deeper than a dataset.

The first GPU run still failed, and instructively:
[[../lessons/wrong_env_var_name_20260827]] — it scored 0.00% over ZERO games while the model
server was healthy and the preflight replied, because our own record named the wrong
environment variable. An arm that scores no games now raises instead of averaging into a
verdict.

## Baseline at commit 3f66c4b — all 25, generic tools alone (2026-08-27)

```
mean 0.6733    ELEVEN at 1.0000    25 of 25 clear at least one level
1.0000  ar25 cd82 cn04 ft09 r11l sb26 sk48 tn36 tr87 tu93 vc33
0.7500 ls20 · 0.7143 m0r0, sp80 · 0.6222 wa30 · 0.4882 su15 · 0.4762 dc22
0.4532 ka59 · 0.4345 sc25 · 0.4074 re86 · 0.3394 lp85
0.1333 bp35 · 0.1091 lf52 · 0.1071 g50t · 0.0833 s5i5
```

Two measurement corrections came out of taking it, and both are cheap to repeat:

**The measured tree was not a committed tree.** The tarball sent to ceph carried 407
uncommitted lines in `hop.py`, so the number was attributable to nothing. Committed at
3f66c4b. This is the same trap as [[../lessons/moving_target_measurement_20260827]], reached
from the other direction — there a snapshot caught a file mid-edit, here it caught finished
work that was never committed.

**ka59 spends its whole budget after it has finished winning.** The harness probe shows five
of seven levels cleared at actions 12, 56, 89, 128 and 173 — then 3,800 more actions on level
six with no further clear. It is the only game in the set that burns its budget this way. The
score is unaffected (0.4532 either way), but at width it is the difference between a game
costing four minutes and twenty. A tool that cannot make progress needs to say so, which is
the same rule as "a tool with no plan must bid zero" applied one step later in the loop.

**FIXED and gated the same hour** — [[../concepts/no_progress_bail]]. And ka59 was not the
problem, only its loudest case: **fourteen of the twenty-five games** were spending most of
their budget after their last level-up. The threshold is measured, not chosen — across all
25, the most expensive level anyone ever CLEARED cost 120 actions, so 1200 is a 10x margin
that could not have cost a measured clear. Full-25 gate: **every one of the 25 scores
identical**, total actions 57,885 -> 21,382, wall-clock 1,882s -> 774s.

Open work is DEPTH on the four weakest — s5i5, g50t, lf52, bp35 — plus lp85 and re86, all six
running as parallel per-game agents under [[../parallel_build_protocol]].

### Budget is not the lever — closed by measurement (2026-08-27)

With the bail in, raising the cap costs wall-clock only on games that keep winning, so the
budget question became cheap to settle. Measured: **@8000 is identical to @4000 on all 25**,
mean 0.6733 either way, not one game differing. Every game bails 1200 actions after its last
clear, so a larger cap is simply never reached.

⛔ Do not re-run a budget sweep on this axis. The remaining loss is that the tools stop
knowing what to do, and no cap fixes that.

### First transfer evidence for the generic path (2026-08-27)

`scripts/rounds/R101XFER` — the generic tools against the archived version hashes:
**twelve of fourteen re-rendered games score IDENTICALLY**, ratio 0.91, and sk48 (whose
archive hash equals its live hash) reproduces exactly as the control. Full detail and the
weak-vs-strong-transfer caveat: [[../lessons/generic_transfer_20260827]].

The two losses are the open leads — tu93 1.0000 -> 0.2222 (9/9 -> 4/9) and s5i5 0.0833 ->
0.0000. In both the tool still ENGAGES, so the plan generalises less far than the detection
does. That is the opposite of the usual failure and the sharper signal.

### Parallel fan-out, integrated one at a time (2026-08-27)

Six per-game agents, each owning two new files and forbidden the registry. The parent
registered ONE at a time and ran the full 25 between each. Every gate below is a separate
25-game run on ceph-build @4000; cumulative regressions ZERO.

```
cyclepress   lp85  0.3394 -> 0.8919   8/8, 258 actions   mean 0.6733 -> 0.6954
clonewalk    g50t  0.1071 -> 0.5357   5/7, every level faster than the human count
telescope    s5i5  0.0833 -> 0.4167   5/8               mean 0.7125 -> 0.7259
pegjump      lf52  0.1091 -> 0.1818   4/10              mean 0.7259 -> 0.7288
reforge      re86  0.4074 -> 0.8350   8/8               mean 0.7288 -> 0.7459
shaft        bp35  NOT KEPT — see below
```

**All four of the weakest games moved**, and thirteen of twenty-five now clear EVERY level.

**re86 level 8 is winnable.** A quarantined per-game adapter reached 7/8 and recorded level 8
as *provably unwinnable as modelled*; the claim was handed to the tool's author as a hypothesis
to verify rather than a fact, and the tool clears 8/8. That is the third time a terminal wall
in this repository has turned out to be a measurement artifact — the rule "verify parks, do not
trust them" keeps paying.

**shaft is the instructive rejection.** Its selectivity was perfect first time: it bids on
exactly one of the 25 boards and 0.00 on the other twenty-four. But bp35 already has `ledge`,
bidding 0.6 against shaft's 0.5, so shaft never got a turn and the gate reported it INERT —
mean unchanged, no game moved. ⛔ **A full-25 gate cannot tell a tool that never gets a turn
from one that has nothing to offer, and those need opposite responses.** Removing `ledge` and
re-running bp35 settled it: ledge 3 levels, shaft 1. The bid ordering was right. Returned to
its author with the measurement rather than deleted.

### Where the remaining score is — ranked (2026-08-27, at mean 0.7459)

Two questions, both answered from the round's own per-level data rather than by intuition.

**Is it efficiency on levels we already clear?** No — and this cheaply re-confirms the rule
already on this page. Across all 25 games only THREE cleared levels score below 0.5:

```
re86 L6   544 vs 139 human   0.0653      su15 L7   18 vs 8   0.1975
lp85 L4    59 vs  16 human   0.0735
```

Bringing all three to human parity is worth **0.0153** of the mean card. Efficiency on cleared
levels is not the axis.

**It is the levels we do not reach.** Twelve games stop short, and RHAE weights a level by its
1-indexed number over the sum of ALL levels, so an unreached deep level is worth far more than a
shallow one — and a game whose FINAL level is unreached is capped below 1.0 however efficient
the rest is:

```
bp35 3/9  0.8667      lf52 4/10 0.8182     s5i5 5/8  0.5833     sc25 4/6  0.5238
dc22 4/6  0.5238      ka59 5/7  0.4643     g50t 5/7  0.4643     wa30 7/9  0.3778
su15 7/9  0.3778      sp80 5/6  0.2857     m0r0 5/6  0.2857     ls20 6/7  0.2500
```

Total locked: **5.8214**, i.e. **0.2329** of the mean card. Clearing every remaining level at
human parity would put the generic tools at **0.9788**. That number is the work list, in order.

### Depth without efficiency is worth nothing — measured to four decimals (2026-08-27)

The round already recorded that the remaining score is DEPTH rather than efficiency on levels
already cleared. bp35 shows the other half of that, and it is sharper than the general claim.

Two tools, same board, measured through the real runner with the loser removed from the
registry so the winner actually drives:

```
ledge   3 of 9 levels   0.1333    L1 15/21   L2 47/48   L3 35/44
crag    5 of 9 levels   0.1344    L1 31/21   L2 124/48  L3 81/44   L4 35/38   L5 116/33
```

**Two extra levels bought +0.0011.** RHAE prices a level at `(human/ours)^2`, so ledge's three
clears at human parity are worth ~1.0 each while crag's are worth 0.46, 0.15, 0.29, 1.0 and 0.08.
The level COUNT doubled and the score did not move.

⛔ So "which tool goes deeper" is not the question, and a report that gives only the level count
cannot be acted on. The bar handed to per-game agents is stated in levels because it is easy to
check, but the decision is made on the per-level costs — ask for both.

crag is NOT registered. Registering it ahead of `ledge` also does nothing on its own: ordering
breaks TIES, and `_signature_default` takes the argmax, so ledge's 0.6 beats crag's 0.5 wherever
it is placed. An inert tool in the registry is a risk on boards nobody has seen and no gain on
the ones we have.

### lf52's level 6: churn eliminated, and it was not the blocker (2026-08-27)

A worked example of instrumenting a guard instead of reasoning about it, and of reverting a fix
that works. Its author instrumented every plan-invalidation site during level 6:

```
offscreen 377   install 42   everything else 0
```

**90% of plan deaths were one predicate**: a jump is played as TWO CLICKS so both cells must be
on screen, while a drive is a button that never needs the screen. The planner, free to plan over
the whole map, kept opening plans with jumps in regions that had scrolled away. Constraining only
the FIRST move barely moved it (377 -> 339) because the plan dies MID-execution — every
horizontal cart move with a piece aboard pans the view one column, so a jump playable when
planned is off screen by the time the plan reaches it.

Applying the window to every state **eliminates the churn: offscreen 339 -> 0, install 69 -> 9**,
and the tool plays level 6 far deeper, taking the visible region from five pieces to two with
real capture chains. ⛔ **It still does not clear, and it costs level 3 four actions** — 57 -> 61
against a human 60, dropping that level 1.0 -> 0.967 and lf52 0.2727 -> 0.2710. Reverted:
necessary, evidently not sufficient, and not free.

**What is actually in the way is exploration policy.** With churn at zero the tool stops in
exactly the same place — two greens left in the visible left region, four more in regions it has
never seen, no route proposed. Those regions are reached by riding a cart along a rail while the
camera follows; the tool HAS the piece on the cart and HAS the drives, and does not go. Its
tiers run capture -> close-the-pair -> frontier -> untouched-cell, and the first two are
satisfied locally while the last two are too weak to commit to a 15-drive journey on the chance
of finding pieces.

Two more model-invariant guards surfaced in the same pass; the pattern is now a concept page:
[[../concepts/guard_about_the_model]].

### lf52 level 6 is PARKED, with the reason read off the level's own data

Five rounds of exploration-policy work ended in a structural fact, not a tuning gap:

```
level 6 rail columns: [7..17] and [23,24,25]    <- TWO DISCONNECTED NETWORKS
```

**There is no road.** No cart route exists from the region the tool can see to the four pieces it
cannot. The bridge is a row-2 socket run crossed by a chain of JUMPS, and a jump needs something
to jump over — so crossing consumes the very pieces that would let you cross. Every travel and
frontier variant tried was looking for a road that is not on the board.

What level 6 actually asks: the tool's first two captures already MATCH the offline solution
exactly, and it must then choose a third among seven candidates that look identical from the left
region and differ only in what they cost on a side it cannot reach without spending them. That is
genuine partial observability. The game agrees — its own hardcoded dead-end detector is what
fires when the wrong one is taken.

⚠️ **The park carries its falsification**, which is the only kind kept here: the one signal
available on frame 1 that the board extends past the screen is that its TRACK LEAVES THE VISIBLE
REGION, no failed win required.

⛔ **AND THE PARK'S AUTHOR THEN FALSIFIED HALF OF IT.** The topology claim holds — read off the
level's own data, a 15-cell rail component spanning columns 7..17 and a 9-cell one spanning
23..25, with carts at (7,6), (8,6) and (23,4). What was wrong was the sentence *"every travel and
frontier variant was looking for a road that is not on the board"*, which conflates REACHING with
SEEING, and on this level those come apart:

* the cart at **(7,6)** sits immediately right of the left socket block, so once the opening
  leapfrog has moved pieces into row 6, a piece at (5,6) jumping right over (6,6) lands ON that
  cart — a capture and a boarding in one move;
* landing at (7,6) is **level 6's own scripted pan trigger**, worth about 3.3 columns;
* and the level makes the camera FOLLOW a cart-borne piece moving right, so riding that component
  east to column 17 pans the view across the board.

**The right-hand pieces cannot be REACHED by cart and can be REVEALED by one.** The park stopped
one step early because "travel found no gain" was generalised into "there is nowhere to go",
where the measurement only supported "there is nowhere the travel objective scores".

The lever that hands the next round, stated to be falsifiable and NOT yet built: on a board known
to extend past the screen, a capture that lands a piece ON A CART is worth more than an
equal-cost capture that does not, because it buys sight as well as a capture. It is a preference
inside the existing eight-candidate choice rather than a new tier, so it costs nothing when no
cart landing is available.

Shipped from those five rounds: reason codes on every empty return in all four planners (off by
default), so one run reports both which tier fired and why the others declined —
[[../concepts/guard_about_the_model]]. Behaviour byte-identical, full-25 0.8540 both.

### "Final levels are harder" — asked, measured, and NO (2026-08-27)

Five games stall with exactly ONE level left and in every case it is the game's LAST level. That
pattern invites a cross-game theory — that final levels are structurally different and there is a
single lever behind all five. Read off the level data, engine never started:

```
game   last cleared -> first uncleared     sprites      distinct kinds
dc22        5 -> 6                          37 -> 72       25 -> 28
wa30        8 -> 9                          50 -> 73        8 ->  9
ls20        6 -> 7                         102 -> 103      19 -> 18
ka59        6 -> 7                           9 -> 10        7 ->  9
g50t        6 -> 7                          33 -> 32       20 -> 23
```

Two roughly double their sprite count; three are flat, and one of those has FEWER sprites than
the level before it. There is no shared structure, so there is no shared lever — the tools stop
at the last level for game-specific reasons, and the per-game agent split is the right shape.

⛔ Recorded as a NEGATIVE so it is not re-asked. The pattern that made it tempting is an artifact
of how the work is ordered: an agent takes the deepest level it can reach, so "the level we are
stuck on" is always the last one we have not cleared, and in a game we have nearly finished that
is the final level by definition.

### Every stuck game is DETERMINISTIC — retries buy nothing (2026-08-27)

All eight games with headroom left, run twice each at @4000 (`scripts/rounds/R101DET`):

```
bp35 (0.1648, 5, 1508)   dc22 (0.7143, 5, 1626)   g50t (0.7500, 6, 1462)   ka59 (0.7500, 6, 1404)
lf52 (0.2727, 5, 1520)   ls20 (0.7500, 6, 1629)   s5i5 (0.4204, 6, 1622)   wa30 (0.8000, 8, 1801)
```

Score, level count and total actions are **identical across both runs of all eight**, and so are
the per-level action counts. Not one is stochastic.

Two consequences, and both save work:

* **No retry, resample or budget change can help any of these.** A stochastic failure is worth
  re-running; a deterministic one is a fact about the tool and only a code change moves it. That
  closes an axis for eight agents at once.
* **Every measurement of a stuck game is reproducible to the action.** A tool author can compare
  a change against an exact prior trace rather than a distribution, which is why single-run
  before/after numbers have been trustworthy all round — this measures the assumption they rested
  on rather than assuming it.

⚠️ It also means a fix that "sometimes works" is not a fix here: if a change makes a level clear,
it will clear every time, and if it does not, no amount of running will surface it.

### A restart is INVISIBLE in the level counter — search problem or attempt problem (2026-08-27)

`scripts/attempt_probe.py` names a distinction nothing in the harness could express. When a level
is failed the engine restores the board and hands back a fresh allowance, but the score carries
the actions already spent — so **a level cleared on the third try reads exactly like a level
cleared slowly**, and the two want opposite work:

* the winning run is slow -> the route is bad, improve the SEARCH;
* the winning run is fast and the cost is in attempts that were binned -> the route is already
  right, and what to improve is NOT DYING.

Its `where` mode splits a real harness run into levels and, inside each, ATTEMPTS, and prices
them. The last column is what the game would score if only its winning attempts were paid for: a
ceiling near the score is a SEARCH problem, a ceiling far above it is an ATTEMPT problem.

```
re86   0.8349 -> 0.9794   +0.1445     401 actions binned
bp35   0.1648 -> 0.2931   +0.1283   1,329 actions binned
s5i5   0.4203 -> 0.4381   +0.0177   1,355 actions binned
wa30   0.8000 -> 0.8000   +0.0000   1,217 actions binned   <- binning, but on levels never cleared
everything else            +0.0000       0 actions binned
```

⛔ **It refuted the instruction I had given bp35's author hours earlier.** I read its per-level
costs — 18/21, 94/48, 83/44, 23/38, 72/33 — as a slow route and told them levels 2, 3 and 5 at
~2x human were worth more than depth. The attempt split says the winning attempts there run at or
BETTER than the human count and every bit of the shortfall is in earlier attempts that were
binned. No amount of route improvement pays for that, and the tool's author says two days could
have gone into it.

⚠️ Note wa30: 1,217 binned actions and a ceiling EQUAL to its score, because its binning is on
levels it never clears at all. Binned actions are not themselves the signal — the ceiling is.

Only three games have any attempt headroom, and two of them are worth having: re86 +0.1445 and
bp35 +0.1283, together **+0.0109 of the card**.

#### The per-level number answers TWO questions and is only right for one

`per_level.agent_actions` is the actions PAID on a level, failed attempts included. That is
exactly right for scoring — RHAE prices what you spent — and exactly wrong as a measure of route
quality, which is what it was read as all round, including by me in the instruction above.

bp35, split by attempt:

```
        paid   won in   binned   human      as quoted     actually
L2        94       57       37      48       1.96x         1.19x
L3        83       43       40      44       1.89x         0.98x  (better than human)
L5        72       38       34      33       2.18x         1.15x
```

Every "2x the human count" in the instruction I gave was an artifact of counting deaths as route.
The routes are at parity.

⚠️ **The DECISION that rested on those numbers still stands, and it is worth being exact about
why.** `crag` replaced `ledge` on a SCORE comparison — 0.1648 against 0.1333 — and score is the
metric, not a proxy for it. What was wrong was the explanation I attached, and the explanation is
what got passed on to an agent as instruction. A right decision reached through a wrong reading
is still a wrong reading, and it propagates.

⛔ When comparing two tools' per-level costs, split by attempt first. `attempt_probe.py where`
does it in one command.

#### The attempt axis, fully mapped — it is two games

Running `attempt_probe.py where` on all four games that bin anything settles which of them the
attempt axis can actually help:

```
re86  L6 only   [200x 201x 144c]   binned 401   won in 144 vs human 139   ceiling +0.1445
bp35  L2,L3,L5  winning runs 57/48, 43/44, 38/33 — at or better than human   ceiling +0.1283
s5i5  L6 only   [150x 106c]        binned 150   won in 106 vs human  38    ceiling +0.0177
wa30  ZERO binned on every level it clears; its 1,217 binned actions are all on level 9,
      which it never clears at all                                          ceiling +0.0000
```

**wa30 is the case that keeps the reading honest.** It bins more actions than re86 and has no
attempt headroom whatsoever, because binning on a level you never clear costs nothing you were
going to be paid for. Read the ceiling column; the binned count is not the signal.

**s5i5 is the case that is neither.** Its level 6 bins one attempt AND wins in 106 against a
human 38 — so it is 2.8x on the route as well, and its ceiling is small because a level priced
that low cannot return much. Attempt work and route work would both be nearly worthless there;
the value in s5i5 is levels 7 and 8.

So the attempt axis is **two games — re86 and bp35, together +0.0109 of the card** — and both
have a route that is already at human parity.

#### re86: the overrun belongs to a DIFFERENT tool, and I guessed wrong twice before counting

The largest recoverable amount in the set is re86's level 6 — 401 actions binned across
`[200x 201x 144c]`, worth +0.1445. Two guesses were made about it before anyone counted, and
both were wrong:

1. **"the route is slow"** — refuted by the attempt split: the winning run is 144 against a human
   139, and five of the other seven levels beat the human count outright.
2. **"it is `reforge`'s overrun"** — reforge is the tool that was working the game and the one
   its author had been improving, so it was the obvious target. Wrong.

Logging the acting tool per action, split on the level counter and on GAME_OVER:

```
level 6, actions by tool, per attempt
   attempt 1:  200 actions  {cover_targets: 200}
   attempt 2:  201 actions  {cover_targets: 201}
   attempt 3:   71 actions  {cover_targets: 14, reforge: 57}
```

**Both overruns are entirely `cover_targets`.** `reforge` only enters on the third attempt and
wins. So an author was sent to fix a tool that is not in the failing window, and a change to it
measured byte-identical — which is exactly what should have happened and is why the change was
not kept.

⚠️ `cover_targets` is not removable either, and that was the next obvious thought: taken out of
the registry, re86 scores **0.0278 with one level** instead of 0.8350 with eight. It carries
levels 1 through 5. The tool that is losing level 6 is the tool that wins the other seven.

⛔ Three guesses, three measurements, three corrections — and every correction cost one command.
The rule this round keeps re-learning is not "instrument when stuck", it is **instrument BEFORE
naming a cause**, because a plausible cause is what gets sent to an agent as instruction.

#### bp35: 24 deaths, and only SIX of them cost anything

`scripts/deathcount_probe.py` — built after four failed attempts to measure this from outside,
and carrying all four in its docstring — answers the question the score cannot:

```
bp35: 5 levels in 1509 actions   acted {graph: 1071, crag: 437}
   24 deaths
      6 on levels that were LATER CLEARED  -- these cost score
     18 after the last clear               -- these cost nothing

   [COSTS] L2 action  20  crag ACTION6      [COSTS] L3 action 123  crag ACTION3
   [COSTS] L2 action  55  crag ACTION6      [COSTS] L3 action 152  crag ACTION3
   [COSTS] L5 action 231  crag ACTION6      [COSTS] L5 action 252  crag ACTION6

   who took the deaths that cost score: {crag: 6}
   the free deaths are PERIODIC at 65 actions -- that is a clock, not a hazard
```

Two findings, and the second is a MECHANIC nobody had named:

* **All six costly deaths are `crag`'s**, two per level on exactly the three levels that bin
  attempts — matching `[2x 35x 57c]`, `[11x 29x 43c]`, `[13x 21x 38c]` from the attempt split.
  The other eighteen are `graph`'s, all on level 6, all free.
* **Level 6 kills every 65 actions, on the dot.** Fourteen deaths at 614, 679, 744, 809, 874,
  939, 1004, 1069, 1134, 1199, 1264, 1329, 1394, 1459 — a period, not a hazard the tool walked
  into. bp35's level 6 runs a clock, and no amount of route or policy work survives it; it has to
  be planned inside.

⚠️ Note how differently the same run reads through the two instruments. `attempt_probe` prices
what the deaths COST and says +0.1283; `deathcount_probe` says who took them and that
three-quarters were free. Neither alone would have pointed at `crag`'s six.

#### The clock is COMMON — and outside bp35 the deaths cost nothing

Swept across the eight games with headroom:

```
game   deaths   costing score          periodic clock
bp35     24      6  (all crag's)        65 actions
s5i5      6      1  (telescope)        201 actions
ls20     14      0                      -
wa30     14      0                      71 actions
g50t      9      0                     131 actions
ka59      6      0                     201 actions
lf52      1      0                      -
dc22      1      0                      -
```

**Five of the eight kill on a fixed period**, each with its own: 65, 71, 131, 201, 201. So the
clock is a family trait of these boards rather than a bp35 peculiarity, and a tool that plans a
long leg on any of them is planning against a deadline it has not read.

⛔ **But the deaths are only costing score in ONE game.** Seventy-four deaths across the other
seven and exactly one of them lands on a level later cleared. Everywhere else the dying happens
after the last clear, on levels never solved under any configuration — the same shape as wa30's
1,217 binned actions and lf52's 664 held actions, both of which measured worth exactly zero.

So the death axis, like the attempt axis and the held-while-silent axis before it, is **one game
wide**: bp35, whose six `crag` deaths are the whole of its +0.1283. Three different instruments,
three different counts, and each time the honest answer was that most of what they measure is
free.

⚠️ That is worth stating as a rule, because three sweeps in a row have gone the same way: **a
count of bad events is not a count of lost score.** Price it before assigning it.

### Close of 2026-08-27 — the measured position

```
generic tools ALONE, zero adapters, full 25 on ceph-build @4000
   mean 0.8602    FIFTEEN at 1.0000    re86 0.9908 makes SIXTEEN at or above 0.99
   SEVENTEEN clear every level         25 of 25 clear at least one
   ~28 gates, cumulative regressions ZERO

transfer   ratio 0.9981, 13 of 14 re-rendered games IDENTICAL   (scripts/rounds/R101XFER9)
shipped    --agent kaggle_detect 0.5422 — the adapters now COST 0.318, only ls20 earns its board
LLM path   25 of 25 identical to the LLM-free fallback, zero routing losses (Kaggle GPU, v5)
cost       10,310 actions and 610s for the full 25, down from 57,885 and 1,882s this morning
```

Eight games still hold headroom, 0.1219 of card between them, every one assigned:

```
bp35 0.1648 5/9   lf52 0.2727 5/10   s5i5 0.4204 6/8   dc22 0.7143 5/6
ls20 0.7500 6/7   ka59 0.7500 6/7    g50t 0.7500 6/7   wa30 0.8000 8/9
```

⚠️ **Three axes were opened and each turned out to be ONE GAME WIDE.** Attempts (re86, then
bp35), deaths (bp35 alone — five of eight games kill on a fixed clock and only one of those
deaths costs score), and held-while-silent (lf52 looked worst by double and measured worth
exactly zero). Each sweep produced a count of bad events and each time the count was not a count
of lost score. **Price it before assigning it** is the rule that came out of all three.

### EVERY stuck level introduces element kinds the tool has never met (2026-08-27)

Asked of ls20 after its tool had been iterated eight times without the level moving, then of the
rest. `scripts/level_diff_probe.py` reads it off the level data with the engine never started:

```
game   last cleared -> first uncleared        new element kinds on the uncleared level
ls20   L6           -> L7  (103 sprites, 18 kinds)   5, incl. a 1x29 bar with no analogue on L6
wa30   L8  (50, 8)  -> L9  (73 sprites,  9 kinds)    4, incl. 22 copies of one 4x4
dc22   L5  (37,25)  -> L6  (72 sprites, 28 kinds)    6, incl. 19 copies of one 4x4
ka59   L6  ( 9, 7)  -> L7  (10 sprites,  9 kinds)    6, on a board of ten sprites
g50t   L6  (33,20)  -> L7  (32 sprites, 23 kinds)    6, with FEWER sprites than L6
s5i5   L6  (12,11)  -> L7  (20 sprites, 17 kinds)    6
```

**Not one of them is the same puzzle at greater depth.** Every stuck level asks the tool to read
furniture it has never seen, and g50t is the sharpest case — its level 7 has FEWER sprites than
level 6 and six kinds it has never met, so "harder" is the wrong word entirely.

⚠️ This reframes a diagnosis I gave and several agents were working from. ls20's tool bids
correctly, takes the board, and then produces 23 consecutive actions that change nothing; I read
that as a planning problem. **Actions that change nothing are equally what a CORRECT plan
produces when it is aimed at objects whose behaviour the model has wrong.** The two are
indistinguishable from the outside, and the level data separates them in one command.

⛔ It also corrects [[#final-levels-are-harder--asked-measured-and-no]], which found no
structural jump in sprite COUNT and concluded there was no shared cause. There is one; it is in
the KINDS, and counting sprites could not see it. The negative was right about what it measured
and the question was asked one level too coarse.

## The stuck levels introduce element kinds the tool has never seen (2026-08-27)

Ran `scripts/level_diff_probe.py` over all eight games holding the remaining 0.1219 — last
cleared level against first uncleared, engine never started. **Six of the eight introduce
previously-unseen sprite KINDS at exactly the wall**; the other two (bp35, lf52) build their
boards at runtime and the probe is blind to them, which is unknown, not negative.

The load-bearing row is g50t: level 7 has **fewer sprites** than level 6 and six new kinds. That
excludes volume and arrangement difficulty for at least one game and makes the finding a
discriminator rather than a story. Three games (ka59 `65x61`, g50t `56x61`, s5i5 `70x51`) add an
element at or beyond the size of the 64x64 board — a covering, not a piece — which generates the
first hypothesis to kill: the level opens under an overlay and the tool plans against the overlay.

⚠️ It also corrects how this round has been directed. A tool emitting actions that change nothing
**looks** like a planning failure and is equally what a CORRECT plan produces when aimed at objects
whose behaviour the model has wrong. Indistinguishable from outside the tool; separated by one
command before the engine starts. Every agent on a stuck game was redirected from planner
iteration to reading the new kinds.

Written up as [[../concepts/new_kinds_at_the_wall]]. ⛔ The first version of the claim said *every*
stuck game — carried two games past the measurement, cut within the hour, and it is the same error
[[../lessons/instrument_validity_20260825]] already records.

## 0.8702, sixteen at the cap — and the work-list was behind the tree (2026-08-27)

`R101NOW`, full-25 on ceph-build, current tree:

```
g50t   0.7500 -> 1.0000   +0.2500
s5i5   0.4204 -> 0.4202   -0.0002
MEAN   0.8602 -> 0.8702        16/25 at the cap
```

⛔ **The +0.25 was sitting UNCOMMITTED and nobody knew.** Five agents held 846 lines of in-flight
work across five tools; one of them (`clonewalk`) had already solved g50t 7/7 — L7 in **42 actions
against a human's 67** — while the recorded baseline still said 0.75 and I sent that agent **three**
messages about the level as if it were a wall. It was found by an agent's probe, not by the record.

**The failure is not staleness by age. The TREE WAS AHEAD OF THE RECORD**, which is the opposite of
the contamination this round has been guarding against all day (a measurement running against code
the repository does not have). Both are the same invariant broken in opposite directions, and only
one of them had a guard.

Two fixes landed:

* the tree was banked as measured (`89eb4f0f`), jointly attributed by construction with the riders
  recorded — see the RIDERS step added to `gate_tool.sh` the same hour, which is what surfaced the
  five dirty tools in the first place;
* the stuck-list at its source (`level_diff_probe.py`) now carries the refresh command inline and a
  ⛔ against working from memory. **A hardcoded work-list is a cached measurement**, and it decays
  exactly like any other.

### One run is not a rate — and a probe that is not the runner is not the scorer

The same agent's next row reported **ka59 7/7 WIN**. Five independent runs of `score_efficiency` on
the same tree returned **0.7500 five times out of five** — deterministic, `(1+…+6)/(1+…+7)`, six of
seven. So the divergence is not nondeterminism; the probe's own stepping loop over-reports clears.

⚠️ This is the exact mirror of the trap already on
[[../lessons/instrument_validity_20260825]]: *"using the runner is not the same as letting the
runner build the agent"*. The inverse now has a measured instance — **letting the runner build the
agent is not the same as using the runner's loop.** `run_game` does more than step.

Held the remaining rows until the cause is found. ⛔ A probe that over-reports clears would have
pulled agents off unfinished games — the same damage the g50t row prevented, in reverse.

### What the click-truth instrument DID establish

Its other half needs no clear count and is the strongest result of the day:

```
game   status         board-changing actions   clicks landing on nothing
g50t   SOLVED  7/7            100%             no clicks at all
ka59   6/7 deterministic       89.5%            0%
s5i5   STUCK   6/8              7.6%           90.2%   (451 of 500)
```

Validity is airtight on the s5i5 row: of 37 board-changing clicks, **37 hit a sprite and 0 hit
nothing**, so the coordinate space is sound and the misses are real misses. **The failing shape is
aiming at objects that are not there** — position and existence wrong, not dynamics — and it appears
only where a game is stuck, which is not a tautology: a stuck game could have shown 100% effective
actions and a bad plan.

And it moved s5i5's target off the level it is stuck on: **L6 is already CLEARED and scores 0.0212**
— 261 actions against a human's 38, same disease at 11.5% — so up to 6/36 of that game's weight is
recoverable **with no new capability at all**.

### The refreshed list (0.0798 across nine games)

```
bp35 0.1648   lf52 0.2727   s5i5 0.4202   dc22 0.7143   ka59 0.7500
ls20 0.7500   wa30 0.8000   lp85 0.8919   re86 0.9908
```

lp85 and re86 had gone unassigned all day because they were not on the stale list. Both are
fully cleared and lose to efficiency on ONE level each — lp85 L4 (59 actions vs 16, worth 0.108 of
its 0.108 gap) and re86 L2 (46 vs 42, worth 0.009). ka59 is the opposite: six levels all at the cap
and a seventh never cleared, so its whole 0.25 is one clear.

## 0.8867, seventeen at the cap — and the "regression" was the fix (2026-08-28)

`R101KA`, full-25 on ceph-build: **ka59 0.7500 -> 1.0000, mean 0.8767 -> 0.8867, no game
regressed.** Seventeen of twenty-five now score at the 1.0 cap.

The change was ka59's agent's **uncommitted** `blastclock`, and it does two things at once — clears
level 7 in 290 actions against a human's 326, and makes the game **machine-independent**:

```
blastclock d33922ec (was HEAD)     Mac 1.0000/294   ceph 0.7500/700   diverges
blastclock 393762f2 (now HEAD)     Mac 1.0000/290   ceph 1.0000/290   portable
```

⛔ **That file was reported as a regression the day before and nearly reverted.** The report rested
on a measurement whose instrument was never attached. It was the fix all along, and it sat
uncommitted while three parties argued about which machine was right.

### Three instrument failures crossed to reach a one-file answer

1. **`PYTHONPATH` does not select the code the runner runs** — `scripts/score_efficiency.py:35`
   does `sys.path.insert(0, <its own repo>/src)` and precedes it. Two "the clock never fires on
   ceph" readings were of ceph's *uninstrumented* code, caught only when an unconditional
   `INSTR-ATTACHED` marker failed to print.
2. **`scripts/measure_frozen.sh` had the identical defect** — built the day before to prevent
   exactly this, and "validated" by importing `admorphiq` under `PYTHONPATH` rather than by running
   the runner. It printed snapshot fingerprints beside live-tree numbers. Now it snapshots
   `scripts/` too and runs the snapshot's own runner; re-validated through the real runner in both
   directions.
3. **A file-list diff without `LC_ALL=C`** buried the single real difference under dozens of
   ordering artefacts — a trap `CLAUDE.md` already records. Locale-fixed, the entire difference
   between the two trees was **one file**.

⚠️ The wall-clock explanation published for this on 2026-08-27 is **withdrawn**: instrumented on
both machines, none of `blastclock`'s clock bounds fire, the node cap is never reached, the
cumulative budget never refuses, and the tool pick is byte-identical. See
[[../lessons/wall_clock_budget_20260827]], which now carries its own retraction.

### What the guards bought

Both gate additions from the previous day earned their place on this run: RIDERS named the
in-flight tools (`blastclock`, `swivel`) so the measurement is honestly joint, and the
tree-integrity check returned its first green — *identical before/after and on the box* — which is
what makes the number attributable to a named tree at all.

### Remaining: 0.1133 across eight games

```
bp35 0.1648   lf52 0.2727   s5i5 0.5833   dc22 0.7143
ls20 0.7500   wa30 0.8000   lp85 0.8919   re86 0.9908
```

All eight agents are rate-limited until 2026-09-01 20:00 KST. Open question now being measured:
**does any other committed tool score differently on the two machines?** ka59 proved one did; a
card that is not portable across machines cannot predict the Kaggle number either.

## Where the remaining 0.1126 actually sits — priced per level (2026-08-28)

`R101LP` (mean **0.8874**, seventeen at the cap). Each loss weighted by its own level index over
the game's full weight sum, so these are directly comparable and directly subtractable:

```
game   score    cleared   UNCLEARED costs   cheapest CLEARED-level losses
bp35   0.1648     5/9         0.6667        L5 0.0878 (72 vs 33) · L3 0.0479 (83 vs 44)
lf52   0.2727    5/10         0.7273        —
s5i5   0.5833     6/8         0.4167        —
dc22   0.7143     5/6         0.2857        —
ls20   0.7500     6/7         0.2500        —
wa30   0.8000     8/9         0.2000        —
lp85   0.9099     8/8         0.0000        L4 0.0850 (33 vs 16)
re86   0.9908     8/8         0.0000        L2 0.0092 (46 vs 42)
```

**The "no new capability needed" bucket is worth 0.237 and bp35 owns 0.136 of it** — more than
everything else combined. bp35 is also the lowest-scoring game in the set, so it is both the
cheapest and the largest target.

### bp35 is a PLAN-LENGTH problem, not a waste problem

Per level, with the acting tool and the fraction of actions that change the board:

```
lvl  tool     actions  changed  rate
  1  crag          18       18  100%
  2  crag          92       92  100%
  3  crag          81       81  100%
  4  crag          23       23  100%
  5  crag          70       70  100%
  6  graph        356      356  100%   <- the wall
  6  crag         144      144  100%
```

**Every action crag takes changes the board.** There is nothing to trim — the routes are valid and
about twice as long as they need to be (92 vs 48, 81 vs 44, 70 vs 33). That is shortest-path work,
not aiming work, and it is the opposite of s5i5 (90% of clicks landing on empty space) and of lp85
(80% of level 4 spent probing). ⛔ **Three stuck games, three different causes — the effectiveness
rate separates them in one run and should be measured before any of them is worked.**

### A measured non-gain worth not repeating

dc22 level 6 spends **499 of 500 actions** on `gantry`'s `if geom is None: return []` — the tool
cannot read that board, correctly returns nothing, and its own `detect` correctly returns 0.0. The
harness was not listening: `self._queue = legal or self._probe(...)` silently substitutes a probe
action, forever, so no re-decision ever happened. A patch retiring a tool after 8 consecutive empty
proposals fixes the mechanism — and **dc22's score does not move**, because all 499 actions fall
AFTER the last clear, where the metric charges nothing. It also fired at step 9 on level 1, which is
real regression risk on other games for no measured gain, so it was **not kept**.

⛔ Same rule as the deaths sweep: **a count of bad events is not a count of lost score — price it
before assigning it.** "A tool with no plan must bid zero" is only half a rule; the harness acting
on the bid is the other half, and it is worth fixing when something measurable depends on it.

### bp35: every route is ALREADY shortest — the 2x is the cost of discovering the board

Refining the plan-length reading above, which was too coarse. `crag._search` is breadth-first over
unit costs, and its own docstring says so: for `"exit"` the first route found IS the shortest. So
nothing is being walked the long way. Counting the searches instead:

```
lvl  exit  new  end  searches   actions  human
  1     1    5    0         6        18     21
  2     1   51    1        53        92     48
  3    19   39    0        58        81     44
  4     4    6    0        10        23     38
  5    32   32    1        65        70     33
  6     0    3    0         3       144      —
```

**Dozens of `"new"` searches per level.** Each is a frontier-exhausting search for the best next
resting place, followed by a short walk to it. The tool learns the board a resting place at a time,
and the 2x against the human is the accumulated cost of that discovery — not a single bad route.
Level 5 alternates almost evenly (32 exit attempts against 32 explorations), i.e. it repeatedly
tries to leave before it knows where the exit is.

⚠️ So bp35 belongs with **lf52**, not with s5i5 or lp85: both are games where the board is not
visible and the score is paid in revealing it. lf52's park says the same thing from the other side
— *get the whole board into the map before spending something irreversible*
([[../concepts/guard_about_the_model]], fourth variant).

**The lever is reveal-per-action, and the machinery already exists**: `_reveals(at, gdir)` scores how
much a resting place would show, and the ranking already puts GROUND GAINED third and cost last —
deliberately, because ranking by cost alone measured *worse* (the tool broke sixteen blocks in
twenty-nine actions and dropped into a slot it could not climb out of). ⛔ So this is not a knob to
turn up; it is a measured trade with a recorded failure on the cheap side. The open question is
whether a resting place can be chosen to reveal MORE per action without spending blocks, and
`_reveals > 0` is currently used only as a boolean filter (line 896) rather than as a magnitude.

## 0.8929 — and the day's biggest gain needed no new code (2026-08-28, evening)

```
mean 0.8929 over 25   SEVENTEEN at 1.0000   cumulative regressions ZERO
bp35 0.2078 · lf52 0.2727 · s5i5 0.5833 · dc22 0.7143
wa30 0.8000 · ls20 0.8442 · lp85 0.9099 · re86 0.9908
```

Banked today, each gated on the full 25 with no game regressing: **ka59 +0.2500**, **ls20 +0.0942**,
**bp35 +0.0431**, **lp85 +0.0179**, a harness fix removing 448 wasted centre-clicks, and the
submission notebook switched to the generic tools.

### ⛔ An unregistered tool measures exactly like an absent one

`fogscout.py` was committed on 2026-08-27 and never added to `default_tools()`. It was then
measured, found "inert", and set aside. **That measurement was of nothing** — an unregistered tool
does not bid and does not propose. Registering it took ls20 from 0.7500 to **0.8442, 7/7**.

The hole is now pinned by `tests/test_every_tool_is_registered.py`, validated in both directions.
Two tools stay unregistered and both are named on the record with the measurement that retired
them: `ledge` (superseded by crag) and `shaft` (registered alongside crag and measured IDENTICAL on
both games it targets — bp35 0.2078, lf52 0.2727).

### Read the game's own level DATA, not only its frames

ls20 was stuck at 6/7 and every frame-side reading agreed the tool was right to decline the board:
it parsed cleanly, found the avatar, and found **zero locks across all 13 attempts** where levels
1-6 always found one or two. One field settled it — level 7 is the ONLY level with `Fog = True`,
and its other settings match level 5, which clears at the cap in 67 actions. **Level 7 is level 5
under fog.** No amount of frame instrumentation prints the word "Fog"; `get_data` does, with the
engine never started.

Generalised as `scripts/level_data_diff.py` (print only the settings that VARY), which immediately
produced the next constraint — **the stuck level's own action budget**:

```
game   stuck level   its budget   actions we spend there
ls20        7            42               500
wa30        9            70               500
s5i5        7           200               500
dc22        6          1024               500
bp35 / lf52  6          none          144+356 / —
```

**wa30 level 9 gives SEVENTY actions and the tool spends five hundred** — measured as 7 GAME_OVERs
at ~71 actions each, i.e. the budget exhausted seven times over. So the target on those three is
"solve within N", never "search longer".

⚠️ wa30 is nonetheless the best-parked board in the set and my marginal value there is low: its
author measured five ranking rules, eight weightings, four drop-cell rules, five bay rules, five
hand-off caps, 300 randomised target orders and four beam searches **using exact engine state**,
and broke the 70 actions down to 9 latches / 20 towing / 6 turns / 45 walking / ~2 recoverable. The
one lever they name as untested is reading the drawn budget so the carrier can decline a plan it
cannot finish.

### The remaining causes, per game

* **dc22** — no waste at all (917 of 925 actions are real tool proposals), budget not binding at
  1024, board reads fine. A planning problem, and the largest unexplored headroom left (0.2857).
* **s5i5** — 448 of 500 level-7 actions were the harness's centre-click fallback; fixed, and the
  level still does not clear within its 200.
* **bp35 / lf52** — the board is not visible; the score is paid in revealing it.
* **lp85** — parked, four probe configurations measured.
* **ls20** — CLEARED 7/7.

### dc22: the wall traced two layers down (2026-08-28)

dc22 was the largest unexplored headroom left (0.2857) and the read was wrong before the plan ever
ran. Two layers, each measured:

**1. The board was never read.** `_split_columns` took the FIRST column whose modal colour differs
from the board's ground. On level 6 that is column 9 — an object standing INSIDE the board — and
the modal colour to its right is the ground again, so the rule concluded "no panel" on every one of
that level's 500 actions:

```
4@0-8   2@9-11   4@12-19   0@20-21   4@22-39   0@40-41   5@42-63
```

The panel is plainly the terminal run `5@42-63`. Fixed by defining the panel as **the band that
reaches the frame's edge** — full 25 identical, no game changed, dc22's levels 1-5 still clear.
⚠️ The first version of that fix was a FALLBACK behind the old test; that is slop, because the old
test is not occasionally unlucky, it is wrong whenever a board object owns a full column. Replaced.

**2. With the split fixed, the read reaches `_pieces` and fails there** — ten times, `squares=[]`.
`_pieces` wants the two rarest colours that each paint exactly ONE congruent square; on level 6
**none of the six rarest colours (15, 9, 11, 6, 10, 14) paints a square at all.** So it is not
merely that level 6 is multi-piece (`tacugo` x25, `bg` x19, `crzsjq` x5, all 4x4) — the pieces this
tool knows how to look for are not on that board in that shape.

⛔ **Not a parse defect and not a budget problem**: level 6 allows 1024 actions and the run spends
500; raising the no-progress bail to 1200 and 3000 gives 1626 and 3427 actions and the same
5/6, 0.7143. It is a capability gap, and it now has an exact statement to design against.

⚠️ Also measured en route: with the read failing, `gantry` stalls after 7 actions, the harness
hands the board to the general searcher permanently, and `graph` spends 491 refills on it. The
level's 925 actions are 917 real tool proposals — **there is no waste on dc22 at all.**

#### dc22 level 6, third layer: the pieces are TWO-TONE and the guard against two-tone is what blocks it

Reading the game's own sprites, TANGIBLE squares inside the board (x < 40):

```
L5 (clears)   crzsjq-1  8x8 colour 8   ·  plflho1 2x2 colour 14  ·  tovemc-plelvb1 4x4 colour 9
L6 (stuck)    plflho1   2x2 colour 14  ·  tewfutblrmbx2 2x2 colours (9,10)
                                       ·  tewfutyefmyf2 2x2 colours (11,12)
                                       ·  tewfutpibpar1 2x2 colours (6,7)
                                       ·  tewfutpibpar2 2x2 colours (6,7)
```

**Level 5's pieces are single-colour squares; level 6's are two-tone 2x2 tokens.** `_pieces` asks
for the rarest colours that each paint ONE COMPLETE congruent square, and each colour of a two-tone
token paints only half of one — hence `squares=[]` over the six rarest colours.

⛔ **And that requirement is not an oversight — it is a guard, and its own docstring names this
exact board**: *"a board carrying two-tone tokens gave four colours tied at the avatar's own pixel
count, and taking the rarest two read the halves of a token as the pieces."* So the rule that keeps
the tool honest on one board is what makes another unreadable. The design question is therefore not
"relax the square test" but **"recognise a token as a 2x2 block of exactly two colours, and treat
the block rather than either colour as the piece."**

⚠️ One cheap idea measured and REVERTED: the panel is drawn with a border (`coorbs-bg-1` starts at
column 40 while the colour change is at 42), so the board region carries two columns of panel
chrome. Extending the terminal run left through non-ground columns removes them — and **regresses
dc22 to 0.6550**, because on other levels it eats real board. Not kept.

#### dc22 level 6, fourth layer — and the third-layer reading was WRONG

⛔ **The two-tone-token story is withdrawn.** Implementing it (recognise a 2x2 block of exactly two
colours as one piece) measured 0.7143 — no change — and instrumenting the branch showed why: it
runs and returns None for every colour, because the (6,7) tokens come in a PAIR and "all of this
colour's cells lie in one block" is then false. Worse, the premise was never the problem.

Counting the composed board's own histogram (columns 0..41, engine never started):

```
L5 board   colour 11 -> 4 cells   colour 14 -> 4 cells      two complete 2x2 squares
L6 board   colour 11 -> 3 cells   colour 14 -> 5 cells      neither is a square
```

The tool locks onto `(11, 2)` and `(14, 2)` on every level it clears — measured 35/52/58/86/194
times on levels 1-5. On level 6 those same two colours paint **3 and 5 cells**: the pieces are
partly OCCLUDED or overlapped, so neither forms the 4-cell square `_one_square` requires, and the
scan returns a single candidate `[(9, 2)]` with nothing to pair it with.

**So the capability gap is occlusion, not two-tone drawing**: the piece is there, and something is
drawn over part of it. That is a different fix — recover a piece from a PARTIAL square — and it has
to answer why 5 cells is also wrong, i.e. what is bleeding an extra cell into colour 14.

⚠️ Three readings of this one level in one session, each measured and each replacing the last:
"multi-piece" → "two-tone tokens" → "occluded pieces". The first two were inferred from sprite
LISTS; only the third came from the composed board's own histogram. ⛔ **Count the pixels the tool
actually sees, not the sprites the level declares.**

#### dc22 level 6, fifth layer: ONE STRAY PIXEL — and two attempts to remove it, both measured

Composing the board and asking who drew each cell:

```
colour 14   (52,28) (52,29) (53,28) (53,29)  drawn by plflho1        <- a clean 2x2 PIECE
            (59,37)                          drawn by sprite_81-2    <- an unrelated decoration
colour 11   (4,5) (5,4)                      drawn by tewfutyefmyf2  <- a DIAGONAL pair, not a block
            (18,7)                           drawn by piyqze-buezna-pueite-1
```

**The piece is intact. One stray pixel of the same colour, from a decoration on the other side of
the board, is what makes `hist[14] == 5` and fails `side*side == count`.** That is the whole reason
`_pieces` returns nothing and dc22's level 6 has never been read.

Two fixes measured, both rejected:

| change | dc22 | why |
|---|---|---|
| drop cells with no 4-neighbour before the square test | 0.7143 | `squares` on L6 still `[]` — the *count* check in `_pieces` still used the unfiltered `hist` |
| also count only contiguous cells in `_pieces` | **0.0000** | levels 1-5 collapse: the filter removes pieces the tool depends on |

⛔ **The second is the important measurement.** "A piece is contiguous, a lone pixel is chrome"
sounds principled and is wrong here: applied to the count, it destroys every level the tool
currently clears. So the stray cannot be filtered globally — it has to be excluded *with respect to
the candidate square*, i.e. accept a colour when its cells contain exactly one solid `side x side`
block and treat anything outside that block as not part of the piece.

⚠️ Colour 11 stays unsolved either way: on level 6 it paints a DIAGONAL pair inside a two-tone
token, so it is not a block at any threshold. Whatever reads that level has to recognise the token
as the piece, and the earlier attempt at that measured 0.7143 with the branch running and returning
None on every colour (the (6,7) tokens come in a pair, so "all cells in one block" is false).

**Five readings of this level today**, each measured, each replacing the last: multi-piece →
two-tone tokens → occlusion → one stray pixel → the stray cannot be filtered globally. The live
tree is unchanged; everything above ran in snapshots.

#### dc22 level 6: the board is READ now, and the next wall is that nothing moves

Banked: a piece is ONE SOLID BLOCK and the stray is excluded **relative to that block**; failing a
solid block, a colour is a piece when it fills one block of exactly two colours and appears nowhere
else. Full 25 identical, dc22 levels 1-5 unchanged, and level 6 goes from `squares=[]` on all 500
actions to `squares=[(9,2),(14,2)]` — the board reaches the planner for the first time.

With the read fixed the tool gets four more branches deep and then latches dead at its own test:

```
L6 branch counts   line580=7 (dead/retired)   line612=4 (sense probe)   line616=1
line616 = "Neither square moved under any simple action: this is not the mechanic."
```

So gantry probes, finds that neither of the two squares it located responds to a move, and
correctly declines. **The avatar is missing from the pair**: it should be colour 11
(`tewfutyefmyf2`), which the token rule refuses because colour 11 ALSO has a stray cell at (18,7)
from `piyqze-buezna-pueite-1`, and that rule's "appears nowhere else" test is global.

⛔ **Relaxing that global test measured dc22 at 0.1429** (from 0.7143 — levels 1-5 collapse to 2).
So it is load-bearing, and the stray-tolerance that works for solid blocks does NOT transfer to
tokens: without "appears nowhere else", the token branch accepts colours it must refuse.

The state of this level is therefore: read ✓, pieces found ✓, but the pair is `(9,14)` where it
needs `(11,14)`, and no rule tried so far admits colour 11 without also admitting colours it must
not. That is the next design problem, stated exactly.

**Six measured readings of one level in one session.** Everything above ran in snapshots; the only
change banked is the one that measured full-25 identical.

#### dc22 level 6: exactly where it stands, and the next probe

BANKED (full 25 identical, no game changed): a piece is ONE SOLID BLOCK with the stray excluded
**relative to that block**. Level 6 went from `squares=[]` on all 500 actions to
`squares=[(9,2),(14,2)]` — the board is read for the first time and reaches the planner.

STILL MISSING: the avatar. The tool locks onto colours **11 and 14** on every level it clears; on
level 6, colour 11 is drawn as a two-tone 2x2 whose composed pixels are

```
y=4    12  11
y=5    11  12          plus one stray cell at (18,7) from `piyqze-buezna-pueite-1`
```

so gantry finds only `(14,2)`, probes, sees neither square move, and correctly declares the board
not its mechanic (`line616`).

Four rules tried for admitting colour 11, all measured, none kept:

| rule | dc22 | why |
|---|---|---|
| token = 2-colour block, colour appears NOWHERE else | 0.7143 | the stray disqualifies the avatar |
| drop that test entirely | **0.1429** | levels 1-5 collapse: `(6,2),(7,2)` pair before `(11,14)` |
| tolerate only ISOLATED strays outside the block | **0.1429** | same — the ordering, not the tolerance, is what breaks |
| + solid blocks outrank tokens (ordering fixed) | 0.7143 | levels 1-5 restored, level 6 still lacks colour 11 |
| + anchor on every block CONTAINING a cell, not only blocks whose top-left is one | 0.7143 | level 6 still lacks colour 11 |

**The ordering fix is real and worth keeping when something needs it** — solids before tokens
restored 0.1429 to 0.7143 — but on its own it buys nothing, so it is not banked.

⛔ **Next probe, and it is one measurement**: instrument `_solid_block` for colour 11 on that board
and print which of its guards refuses — `len(vals) != 2`, the outside-stray test, or the two-block
ambiguity return. The composed block above is unambiguously two colours, so one of the three is
firing on data that does not look like it should fire. Everything else about this level is now
known and written down.

#### dc22: the last guard found, and why the thread stops here

The avatar's colour was being thrown away by the ambiguity test, and the reason is general enough
to be worth more than this game:

```
[why] ACCEPT (3,4) side=2          <- the avatar's real token, colours 11 and 12
[why] AMBIG had=(3,4) now=(16,6)   <- the STRAY at (17,7), sitting on flat ground
```

⛔ **A LONE PIXEL ON FLAT GROUND IS ALWAYS A VALID TWO-COLOUR BLOCK.** So every stray manufactures
a phantom token, the "this colour lies in exactly one block" test sees two, and the real piece is
refused. Requiring a token half to be at least TWO cells removes the phantom, and level 6 then
offers `tokens=[(9,2),(11,2),(10,2)]` — the avatar is admitted for the first time.

**And the score does not move.** `_pieces` returns the FIRST congruent pair, so level 6 locks onto
`(14, 9)` where it needs `(14, 11)`; gantry probes, neither square moves, and it declines exactly as
before. Ordering by rarity is arbitrary here — which square is the avatar is decided by the PROBE,
not by the histogram.

⛔ **Not banked.** Three changes (solid-before-token ordering, anchor on every containing block,
a token half is >= 2 cells) restore what a relaxation broke and admit the avatar, and together they
buy **zero score**. The rule against keeping unmeasured changes applies to my own work.

**What the next attempt should do instead of another read fix**: `_pieces` should offer CANDIDATE
pairs rather than commit to one, and let gantry's existing probe — which already asks which square
moves — choose. That is a contract change, not a heuristic, and it is the first thing in this game
that is not guesswork.

#### dc22 level 6 — CLOSED: the tool's core premise is false on that board

The contract change was made and measured: `_pieces` now offers EVERY candidate at the chosen side
instead of the first congruent pair, and `_settle_move` — which already watches which square moves —
picks the avatar. Levels 1-5 are unchanged and now show the mechanism working with more candidates
than two:

```
level 1  avatar=14 from rare=(11, 14)
level 4  avatar=14 from rare=(11, 14, 12)
level 5  avatar=14 from rare=(11, 14, 1)
level 6  — no avatar line at all —
```

**On level 6 the candidate list includes colour 11 (the piece the earlier layers were fighting to
admit) and NOTHING MOVES.** No candidate square responds to any simple action, so `_avatar` is
never assigned and the tool declines — correctly, and for a reason no read fix can reach.

⛔ **So the premise `phase_grid` is built on — one of the rare squares moves under a simple
action — is FALSE on dc22 level 6.** Every layer below it was real (the panel split, the stray
pixel, the two-tone token, the phantom token from a lone pixel on flat ground) and each was worth
finding, but none of them was the reason the level does not clear.

⛔ Not banked: levels 1-5 identical, level 6 identical, zero score. Six read repairs measured on
this level today and exactly one banked — the solid-block rule, which was full-25 neutral and made
the board readable for the first time.

**What dc22 level 6 needs is a different tool or a different mechanic model**, and the useful
statement for whoever takes it is the negative one: the board is read, the pieces are found, the
avatar is among them, and no simple action moves any of them.

#### s5i5 level 7: the tool understands the board and cannot route it

The harness fix banked earlier already changed this level materially. Per-action sources, measured:

```
before   448 of 500 actions were PROBE cur=swivel  -> click (32,32), the board centre
after    461 tool/linkage  ·  30 tool/swivel  ·  7 PROBE/swivel
```

**The 448 wasted centre-clicks are gone**; the level is now played with real proposals. It still
does not clear, and the reason is in s5i5's OWN tool rather than in the fallback that inherits it.

`swivel` clears levels 1-5 by delegating to `TelescopeArmTool` and clears level 6 on its own path.
On level 7 it runs that same path 31 times and then latches dead — at `REPLAN-FAIL`, not at
assembly:

```
level 7   no-pairing  tried=2  planfail=2  solved=0  riders=2  places=2  refuted=2
```

So the board is read, the controls are probed, the model assembles, and **both possible
rider-to-place pairings are tried and both fail to yield a route**. The tool then correctly gives
up rather than spending the level, and `linkage` takes over with 461 actions that also do not solve
it.

⛔ **This is a PLANNER limit, not a perception one** — the opposite of dc22, where perception was
broken and the premise turned out false. `plan(model, cfg, moves, banned)` finds nothing for either
pairing on a board whose budget is 200 actions and whose human baseline is 86.

The useful next question is narrow: with `riders=2, places=2`, is the level genuinely unroutable
under the moves this tool has learned, or is `plan` missing a move it needs? The `_retry_unknown`
path already exists for controls that were jammed at probe time — its own note records a board
where three of nine controls were unreadable when first tried — so the first thing to measure is
whether level 7's controls are fully known when the two pairings are attempted.

##### s5i5: the three unknown controls are not a retry-budget problem

At the moment both pairings fail, the tool's own state is:

```
unknown = 3 of 9 controls · tries=[1,1,1,2,1,1,2,1,2] · banned=0 · moves=13
```

— exactly the situation `_retry_unknown`'s note describes ("three of one board's nine were
unreadable at probe time"), and the retry budget is spent (`_MAX_TRIES = 2`, several controls at 2).

⛔ **Raising it changes nothing.** Sweeping `_MAX_TRIES` to 3, 4 and 6 (with `_MAX_RETRIES` lifted
in step) gives **0.5833 at every value** — 6/8 levels, identical. So those three controls do not
move however often they are pressed; they are jammed or they are not controls.

⚠️ Worth noting for whoever continues: `_MAX_RETRIES` ships at **1** while `_retry_unknown` skips
any control with `tries >= _MAX_RETRIES`, so a control pressed once in the first pass can never be
retried by that path at all. Lifting it was part of the sweep above and still bought nothing here,
but the default makes the retry path dead on every board where the first pass already pressed
everything once — which is every board.

The next question for s5i5 is therefore not "press them again" but **whether those three are
controls at all** — i.e. whether widget detection over-counts, leaving `plan` to route through
things that were never operable.

##### s5i5 level 7: the model reads TWO riders where the board draws at least five — ⛔ WITHDRAWN, see below

Reading the game's own sprites, the level's structure changes kind between 6 and 7:

```
L6   12 TANGIBLE   riders drawn as 7x7,  colours (2,4,X)   — three of them
L7   20 TANGIBLE   riders drawn as 11x5, colours (2,3,4,X) — 0075(14) 0076(11) 0077(9)
                                                              0078(12) 0081(10), at least five
```

The tool reports **`riders=2 places=2`** on that board. So the two pairings it exhausts are two of
the ways to match a model that has already lost most of the level — which is why every pairing
fails to route and why pressing the three unknown controls harder changes nothing.

⛔ **The wall on s5i5 is the same SHAPE as ls20's, not as dc22's**: the tool's perception of the
level is incomplete in one specific, nameable way, and everything downstream is honest work on a
wrong model. ls20's version of this was solved by registering a tool that already existed; s5i5's
needs `read_widgets` to see the 11x5 family, or a tool that does.

⚠️ Also visible in the level data and worth carrying: `0063ylopfyonpu` appears TWICE on level 7 at
different positions under one name, where level 6 has a single instance — so any code keyed on
sprite name rather than position will collapse them.

##### ⛔ WITHDRAWN: the s5i5 "two riders where the board draws five" claim

That entry rested on a carry-forward attribution — the very error recorded as the sixth instrument
failure on [[../lessons/instrument_validity_20260825]], committed by me two entries after writing
it down. Measured per call instead, with a marker inside `_begin` and one at every `propose`:

```
levels 1-5   delegate=True             swivel hands the board to TelescopeArmTool
level 6      bars=3 places=1 drawn=1 pinned=1 -> riders=1     (clears)
level 7      bars=6 places=2 drawn=2 pinned=2 -> riders=2
```

`riders=2` on level 7 is what `pinned` yields because **exactly two markers are DRAWN** — the rule
at `swivel.py:713` takes the pinned bars when there are at least as many as there are places, and
falls back to every bar otherwise. Nothing establishes that the five `11x5` sprites are all riders;
they may be destinations, or the bars themselves. **The claim was unsupported and is withdrawn.**

What survives, and is measured per call rather than by proximity:

* `swivel` clears levels 1-5 through its delegate and level 6 on its own path;
* on level 7 it builds a model (`bars=6, places=2, riders=2`), exhausts both pairings, and dies at
  `REPLAN-FAIL` — the planner finds no route for either;
* three of nine controls never move, and raising the retry budget to 3, 4 and 6 leaves the score at
  **0.5833 at every value**;
* `_MAX_RETRIES` ships at 1 while `_retry_unknown` skips controls with `tries >= _MAX_RETRIES`, so
  that path cannot fire on any board whose first pass pressed every control once.

⛔ The honest state of s5i5 is therefore: **the model is small (2 riders, 2 places, 6 bars) and no
pairing routes.** Whether the model is WRONG is not established — that is the measurement to make,
and it needs the board's own semantics, not another proximity-attributed trace.

##### s5i5 measured properly, with the new self-attributing instrument

Re-run with the level printed ON each event line and grouped by `scripts/trace_attribute.py`, so
none of this rests on proximity:

```
level 6 (clears)   bars=3 places=1 drawn=1 pinned=1 widgets=6   riders=1
level 7 (stuck)    bars=6 places=2 drawn=2 pinned=2 widgets=9   riders=2
level 7 failure    riders=[2,4]  places=2  refuted=2  moves=13  unknownctl=[3,6,8]
both levels        grow=0  turn=0  moved=6 of 9 controls
```

⛔ **Two of my own readings die on that last line.** The clearing level has the SAME empty
`grow_of`/`turn_of` maps and the SAME three unknown controls as the stuck one — so neither
"the control map is empty" nor "three controls are unknown" is the differentiator. Both were
plausible and both were wrong, and the contrast with a level that clears is what settled it.

**What actually differs is scale.** One rider and one place pair trivially; level 7 has two riders
(bars 2 and 4) and two places, offers exactly two pairings, and the planner finds no route for
either — with the same amount of control knowledge that suffices for one rider.

So the statement for s5i5 is: **routing ONE rider works on this family; routing TWO does not, and
it is not for want of probing.** Whether that is a planner limitation or a genuine property of the
board is the open question, and the cheapest way at it is the game's own semantics rather than
another trace — the same route that resolved ls20 in one field.

##### s5i5 level 7 is the board swivel's own docstring analysed — and the designed path is not running

`Children`, from the game's own level data, is a parent -> child chain:

```
level 6 (clears)   0047 -> 0048 -> 0049                       ONE chain, depth 3
level 7 (stuck)    0097 -> 0058                               TWO chains,
                   0059 -> 0060 -> 0061 -> 0062               one of depth 4
```

That matches the model exactly (`bars=6`, `riders=[2,4]`, `places=2`) and it matches what
`swivel`'s planner docstring already says about **"the seventh board"**:

> MEASURED on the seventh board it is over 336,000 configurations and still growing when cut off,
> from six bars and eleven controls, and no joint search gets near a state with BOTH riders home.
> But that board never needed a joint search: no control there moves more than one rider — one
> control drives the first rider's arm and nothing else, five drive the second's. When that holds,
> the riders are independent problems ... so they are solved in sequence and the plans concatenated.
> Order can matter when one chain parks across the other's route, so both orders are tried.

So this exact board is already analysed, the independence it relies on is confirmed by the
`Children` data (the two chains share no sprite), and the sequential path is the DESIGNED answer.
⛔ **And it is not producing a plan**: `refuted=2` means both pairings were tried and both returned
nothing, so the sequential solve is failing where its own analysis says it should work.

**That is a much better lead than "two riders do not route."** The next measurement is inside the
sequential path rather than at its output: for each of the two pairings, does the FIRST rider's
solve succeed and the second fail, or does the first already fail? `_joint` exists only as the
shared-control fallback and the docstring says this board must not need it — so if `_joint` is what
is running here, that is the defect.

##### s5i5 level 7 — the planner WORKS. The plans fail in EXECUTION. (⛔ overturns the entry above)

Instrumented inside `_replan`, with the level read from the code rather than hardcoded:

```
level 6   pairing=[(0,0)]         found=25          (clears)
level 7   pairing=[(0,2),(1,4)]   found=26
          pairing=[(0,2),(1,4)]   found=20
          pairing=[(0,2),(1,4)]   found=0
```

And inside the sequential solve the designed path engages exactly as its docstring says it should:
`sequential=True`, every control's reach is 1 rider, both riders solve (`place=0 bar=2 got=yes`,
`place=1 bar=4 got=yes`), `SOLVED=True plan_len=26`.

⛔ **So "the planner finds no route for either pairing" was WRONG.** It finds a 26-click plan, then
a 20-click plan. The `refuted=2` I reported earlier was the state at the LAST call — after the
earlier plans had been found, executed, and refuted by the board. The order is: plan -> execute ->
the board does not end up solved -> the pairing is refuted -> try the next -> exhausted -> dead.

**The defect is prediction, not search.** The model yields plans it believes solve the board and the
board disagrees when they are played. That is a much sharper target: `_settle` already compares each
click's predicted outcome against the frame and kills the tool on a mismatch, so the next
measurement is which click in the 26 first diverges from its prediction.

⚠️ Two instrument notes from this dive, both mine. I hardcoded `lvl=7` into a marker and the new
attributor faithfully reported "level 8" — a literal is not a measurement, and the fix was to carry
the real level in a module global set by `propose`. And the earlier `refuted=2` reading was a
last-call snapshot presented as the whole story; printing every call is what showed the two plans
that came before it.

##### s5i5 level 7: ONE CONTROL, state-dependently refused — and the model has no term for it

Instrumented at `_settle`, which sees every click's outcome, with the level carried from `propose`:

```
level 6 (clears)   24 plan clicks, 0 refused
level 7 (stuck)    19 plan clicks, 2 refused — and BOTH are the same control:

    refused=1 ctrl=0 step=1 plan_left=18     the 8th click of the 26-click plan
    refused=1 ctrl=0 step=1 plan_left=9      the 11th click of the 20-click plan

level 7            ctrl=0 also PASSES twice elsewhere in the same level
level 7 probes     6 of 12 learning clicks refused
```

**Control 0 with step +1 is legal in some board states and refused in others, and the model carries
no term that distinguishes them.** Both plans die on exactly that click, which is why both pairings
are refuted and the tool then has nothing left to try.

⛔ So the chain for s5i5 level 7 is now complete and each link is measured:
perception ✓ (bars=6, riders=[2,4], places=2 match the game's own `Children` chains) ->
sequential path engages ✓ (`sequential=True`, every control reaches one rider) ->
both riders solve ✓ -> a 26-click plan is produced ✓ -> **its 8th click is refused by the engine**
-> the pairing is refuted -> a 20-click plan -> **its 11th click, same control, same refusal** ->
pairings exhausted -> dead.

The tool already BANS a refused edge (`self._model.illegal.add(...)`) so it does not loop on the
same move — that guard works. What it cannot do is generalise: the ban is keyed on the exact
configuration, so the same control refuses again from a different state and the plan dies again.

**The target is therefore one question about the game: what makes `ctrl=0 step=+1` illegal?** The
tool's own note already suspects geometry it cannot see — it records a board "framed by a
board-spanning wall placed at (-3,-3), three cells outside the visible grid on every side" — and
s5i5 level 7 carries exactly such a sprite (`0008iqvkanhnxj`, 3x15, and a 70x51 at (-3,-3)).

##### s5i5's refusal rule, from the game's own source: ARMS MUST NOT OVERLAP

The question the measured chain ended on — what makes `ctrl=0 step=+1` illegal in some states and
legal in others — is answered in one function of the game's own code:

```python
def qownxibuiy(self) -> bool:                     # tag 0001qwdmnlybkb == the arm sprites
    arms = self.current_level.get_sprites_by_tag("0001qwdmnlybkb")
    for a in arms:
        if any(a.collides_with(other) for other in arms):
            return True
    return False
```

and both callers do the same thing with it: after applying an edit, `if self.qownxibuiy(): return`
— the edit is abandoned and the saved state kept. On success the saved state is cleared.

**So a click is refused exactly when the configuration it would produce makes two arms overlap.**
That is why the same control passes twice and refuses twice on one level: it depends on where the
other arm is standing.

⛔ `swivel` bans the refused CONFIGURATION (`self._model.illegal.add(want.key())`) but has no
general overlap predicate, so the ban cannot generalise — the same control refuses again from a
different state and each plan dies at a different click. Its own docstring claims "legality is still
checked at every single step, so arms from different chains cannot pass through each other", and the
two refusals measured on level 7 say that check does not reproduce the engine's.

**This is a RULE, not a heuristic, and it is the actionable target for s5i5**: give the model an
arms-do-not-overlap test over the configuration it is about to propose, so the planner never emits
the click the engine will refuse. Level 6 needs it too and never trips it (24 plan clicks, zero
refusals), which is why it clears — so the fix is testable as "level 6 unchanged, level 7's plans
survive their 8th click".

⚠️ Reached by reading the game's own source after the frame-side chain was complete — the fifth time
today that route ended a question the measurements had only narrowed.

##### ⛔ CORRECTION, and the real cause: the ENGINE counts SEVEN arms, the model tracks SIX

The previous entry said the fix was "give the model an arms-do-not-overlap predicate". **That was
wrong — the predicate already exists.** `legal()` tests `_overlap(a, b)` over every pair of
`cfg.bars + cfg.freight`, and its docstring opens with "No two moving boxes may overlap".

So the model already forbids overlap; it simply does not know about every arm. Counting by the
engine's own tag (`0001qwdmnlybkb`):

```
level 6 (clears)   arms=4   0005 (57x15, a frame) + the chain 0047 -> 0048 -> 0049     riders=1
level 7 (stuck)    arms=7   0006 (70x51 at (-3,-3))  +  0007 (15x3)  +  0008 (3x15)
                            + the chain 0059 -> 0060 -> 0061 -> 0062                    riders=2
```

The model reports `bars=6`, which is the two `Children` chains (2 + 4). **`0006`, `0007` and `0008`
are arms to the engine and absent from the model** — and `0006` is a 70x51 sprite anchored at
`(-3,-3)`, i.e. the board-spanning frame that extends outside the visible grid. `swivel`'s own note
already suspected exactly this furniture ("the model cannot see that furniture at all, so 77 of 189
planned actions came back refused until refusals were banked by configuration").

**So the refusals are collisions with arms the model has no box for**, which is why banking the
refused configuration is the only defence it has and why that defence cannot generalise.

⚠️ Level 6 has the same shape at smaller scale — one frame arm (`0005`) plus its chain — and clears,
because with one rider the plan never needs the configuration where the chain meets the frame.

The target is now exact: **give the model a box for every sprite the engine tags as an arm**, frame
included, rather than only the ones on a `Children` chain. Verification stays as stated — level 6
unchanged, level 7's plans surviving their 8th click.

##### s5i5: learning on-board solid cells — implemented, wired, and it buys NOTHING

The off-grid mechanism (`offblocked`) learns hidden furniture cell by cell from unexplained
refusals, and its docstring calls it "a superset, but a learned and shrinking one". The missing arms
`0007` (15x3) and `0008` (3x15) sit INSIDE the grid, so that mechanism cannot see them. Extended it
symmetrically — an `onblocked` set filled from the same unexplained refusals and consulted by
`legal()`:

```
level 7   learned=9 total=9      first refusal banks nine on-board cells
level 7   learned=0 total=9      second refusal banks NOTHING NEW
legal()   consulted the learned cells 4,422,834 times — fully wired
score     0.5833, unchanged
```

⛔ **The second refusal learning nothing is the informative half.** The cells that move would occupy
are already banked, or they belong to the bar's own current footprint — and in either case `legal()`
cannot refuse the configuration in advance. So the collision that kills the plan is not with a cell
the model can mark as solid: it is between boxes the model already has, in a way `_overlap` does not
catch, or with an arm sitting exactly where a bar already stands.

⛔ Not kept — zero score change, and a set consulted four million times per run is not free.

**What this rules out**, so it is not tried again: the refusal is NOT explained by unknown solid
cells on the board, the way the off-grid case was. The engine's rule is
`any(arm.collides_with(other) for arm in arms)` over SPRITES, and reproducing it needs the arms'
actual footprints — not a cell-set approximation reconstructed from refusals.

##### s5i5: the hidden frame IS being learned, and the order rules out the obvious repair

The refused moves' own boxes, printed at the ban, show what the collision is with:

```
refusal 1  want_bars = [... (6,48,8,65) ... (9,63,14,65)]        x reaches 65, past the grid edge
refusal 2  want_bars = [(-3,42,14,44) ... (-3,45,-1,50)]         y reaches -3
```

No pair of the model's own boxes overlaps in either configuration — so the collision is with the
**arm the model has no box for**: `0006`, the 70x51 sprite anchored at `(-3,-3)`. That is exactly
what `offblocked` exists to learn, and it IS learning it: **18 cells after the first refusal, 45
after the second.**

So the hypothesis was "the learning is real but the pairings run out before it converges — clear
`refuted` whenever the model gains a fact". Implemented, and the branch fires twice:

```
level 7   offblocked=18  cleared=0
level 7   offblocked=45  cleared=0
```

⛔ **`cleared=0` both times: the refutation set is EMPTY at the moment the learning happens.** The
model gains its facts BEFORE any pairing is refuted, so there is nothing to un-refute and the repair
cannot help. Score 0.5833, unchanged. Not kept.

**What the order actually says**: by the time pairings are being refuted, the frame is already 45
cells known — and plans are STILL produced and STILL refused. So the failure is not "too little
learned too late". Either 45 cells is far short of the frame's real footprint (it is only about a
fifth opaque, so a superset built from two refusals cannot cover it), or the plans die on something
else entirely.

⚠️ Three repairs measured on this board tonight — on-board cell learning, un-refuting on new
knowledge, and (earlier) raising the control-retry budget — all **0.5833, no change**. Each ruled
out a different story, and all three ran in snapshots; the live tree is untouched.

##### s5i5: the numbers that settle it — 291 hidden cells outside, and two arms fully INSIDE

Every sprite the engine tags as an arm on level 7, with its real footprint:

```
0006vwqootnonz  70x51 at (-3,-3)   solid=708   outside the grid=291
0007ronybdlipn  15x3  at (21,6)    solid=45    outside=0      <-- entirely ON the board
0008iqvkanhnxj  3x15  at (12,6)    solid=45    outside=0      <-- entirely ON the board
0059 / 0060 / 0061 / 0062  the chain, solid 9/18/18/9, outside=0
```

Two facts close the question:

1. **`offblocked` learns 45 of the frame's 291 hidden cells** — a sixth — from the two refusals the
   pairing budget allows. The docstring's "a superset, but a learned and shrinking one" is honest
   about the mechanism and the arithmetic says it cannot converge here: the sprite is only about a
   fifth opaque, so no small number of refusals covers it.
2. ⛔ **`0007` and `0008` have ZERO cells outside the grid.** They are 45-cell arms sitting entirely
   ON the board, and `offblocked` — which by construction only records cells with
   `y < 0 or x < 0 or y > 63 or x > 63` — **can never learn them at all.** A collision with either
   is a refusal the model has no representation for, at any budget.

**So the diagnosis for s5i5 level 7 is complete and it is a perception gap with an exact shape**: the
model needs boxes for the arms it does not derive from the `Children` chains — two on-board arms of
45 cells each, plus a board-spanning frame — and it cannot reach them through the refusal-learning
path, which is off-grid only.

That is why every repair measured tonight came back 0.5833: on-board cell learning (the cells belong
to bars' own footprints), un-refuting on new knowledge (`cleared=0`, the learning precedes any
refutation), and a bigger control-retry budget (those controls never move). ⛔ **Three stories ruled
out, one cause left, and it is stated precisely enough to build against.**

##### s5i5: `stripes` swallows seven pieces, and the frame's exclusion is a MEASURED decision

Two things found by reading `swivel.read_board` rather than instrumenting around it.

**1. Giving the frame a box is already known to be wrong.** Its own note:

> ⛔ Only RECTANGLES may be carried. A wall is an L or a frame and its bounding box covers most of
> the board — measured, one board's two wall blobs came back as boxes spanning (27,3)-(41,8) and
> (27,18)-(41,59), which makes every configuration illegal.

So `0006` (70x51) is deliberately furniture, handled through `solid_cells` — "the immovable
background is what is LEFT OVER, never what a classifier labelled". **My planned repair — a box for
every arm — would reintroduce a failure this code already measured and designed around.**

**2. The classification on level 7, measured:**

```
level 6 (clears)   pieces=8    owned=3   stripes=3   freight=0   non-rect=2
level 7 (stuck)    pieces=16   owned=6   stripes=7   freight=1   non-rect=2
```

**Seven pieces become `stripes` on level 7** — excluded as "the anchor stripe now lives inside the
bar's box" — against three on level 6, and only ONE piece survives as freight. `0007` and `0008` are
15x3 and 3x15 rectangles of 45 cells each; if either is swallowed by that rule, it leaves the box
list entirely and `legal()` cannot see the collision.

⛔ The `stripes` test is `_overlap(piece.box, bar.box)` — it cannot tell "this stripe is part of that
bar" from "this arm happens to stand where that bar's box reaches". On a board with two chains and a
frame, the second reading is available and the rule takes the first.

**That is the sharpest statement of the s5i5 gap so far, and it is a rule to fix rather than a
quantity to tune**: distinguish a bar's own anchor stripe from an unrelated arm that merely overlaps
its bounding box. Verification unchanged — level 6 must stay at its 24-clicks-no-refusals, and level
7's plans must survive their 8th click.

##### ⛔ s5i5 CORRECTION: 0007 and 0008 are ALREADY modelled. The only unmodelled arm is the frame.

Printed the role of every piece whose box matches those two arms:

```
[pc] box=(7,12,20,14)  3x14  colour=8   rect=True  role=owned
[pc] box=(6,21,8,34)  14x3   colour=10  rect=True  role=owned
```

**Both are `owned` — they ARE bars in the model.** So `bars=6` is not "the two Children chains
(2+4)"; it includes these two, and my inference from the chain data was wrong. The only arm the
engine counts that the model has no box for is **`0006`, the 70x51 frame** — and `read_board`'s own
measured note forbids boxing it ("its bounding box covers most of the board ... makes every
configuration illegal").

The stripes fix was still made and measured: requiring a stripe to be CONTIGUOUS with its anchor
rather than merely overlapping its bounding box moved the classification `stripes 7 -> 6` on level
7, freeing one piece — which is not a rectangle, so it became furniture, the box list did not change
and the score stayed **0.5833**. Correct in principle, inert here, **not kept**.

**So the standing account of s5i5 level 7 is:** every arm but the frame is modelled; the frame is
deliberately furniture and is learned cell-by-cell through `offblocked`, which reaches 45 of its 291
hidden cells before the pairings run out. Four repairs measured tonight — on-board cell learning,
un-refuting on new knowledge, a larger control-retry budget, contiguous stripes — **all 0.5833.**

⚠️ **Four of my readings on this one board were wrong and each was killed by a measurement rather
than by argument**: "riders=2 where the board draws five", "the planner finds no route", "the model
lacks an overlap predicate", and now "0007/0008 are unmodelled". The pattern in all four is the
same — I inferred the model's contents from the GAME's data instead of asking the model.

##### s5i5: the refusal-learning is EXACT, and the attempt budget is not the bottleneck

Two measurements close this axis.

**The learning has zero false positives.** The 45 cells banked from the two refusals, checked
against the frame sprite's real pixels:

```
learned cells 45   actually solid 45   wrongly banned 0
the frame's hidden footprint: 291 cells
```

The docstring calls `offblocked` "a superset, but a learned and shrinking one" — on this board it is
not even a superset, it is an exact subset. Every cell it bans is genuinely solid. **The mechanism is
right; it has only seen a sixth of the wall.** The cells learned are precisely the two refused moves'
own footprints outside the grid: rows 6-14 at columns 64-65, then rows -3..-1 at columns 42-50.

**And more attempts do not buy more learning.** Multiplying the pairing-attempt budget by eight:

```
before   refusals 2, offblocked reaches 45
after    refusals 2, offblocked reaches 45      score 0.5833, unchanged
```

⛔ So the tool does not stop because it runs out of permission to try; **a third plan is never
produced.** After the second refusal the search finds nothing for either pairing under the 45 cells
it now knows — the bans are correct, and they are enough to close every route the planner can see
while leaving 246 unknown cells that would close more.

**Five repairs measured on this board tonight, all 0.5833** — on-board cell learning, un-refuting on
new knowledge, a larger control-retry budget, contiguous stripes, and now an eightfold attempt
budget. The axis they all probe (make the model learn the hidden frame faster or longer) is closed:
the learning is exact, bounded by how many refusals the board offers, and the board offers two.

**What is left is to stop needing the refusals**: read the frame's occupancy from the frame itself.
The sprite is drawn — 708 solid cells, 291 of them outside the visible grid — and the tool sees the
visible part every turn. ⛔ It cannot be given as a BOX (measured: its bounding box makes every
configuration illegal), so it has to enter the model as CELLS, the way `offblocked` already stores
them, but derived from the picture rather than from refusals.

##### s5i5 CLOSED by a measured impossibility: the hidden margin cannot be inferred from the picture

The last remaining idea was "stop needing refusals — read the frame's occupancy from the frame
itself". The frame's own pixels refute it.

```
y=-3..-1 (outside the grid)   FFFFFFFFFFFFFFFFF   X=40..56 fully solid
y= 0.. 2 (inside, visible)    FF...............   the same columns are EMPTY
```

**The hidden rows are solid exactly where the first visible row is empty.** Quantified over the
whole sprite:

```
outside-grid cells within the sprite   498      solid 291 (58%)
"extend the nearest visible cell"      right 243   wrong 255   -> 51% error
```

⛔ **A predictor built from the visible border is worse than a coin toss**, and a blanket "the margin
is solid" rule would ban 207 free cells — which is the failure `swivel`'s own note already records
("a tool that blocks the margin by default loses that level instead").

So the axis is closed by arithmetic rather than by another attempt:

* refusal-learning is **exact** (45 of 45 cells genuinely solid) and **cannot be hurried** (an
  eightfold attempt budget yields the same two refusals);
* the frame **cannot be boxed** (its bounding box makes every configuration illegal — measured);
* the hidden margin **cannot be predicted** from the visible picture (51% error);
* and every arm except the frame is **already modelled** (`0007`/`0008` print `role=owned`).

**s5i5 level 7 needs information the tool cannot obtain by any route now available to it.** That is
a park with a proof, not a to-do — and the honest next move on this game is a different mechanic
model, not another repair to this one.

⚠️ **Six repairs measured on this board tonight, every one 0.5833**: on-board cell learning,
un-refuting on new knowledge, a larger control-retry budget, contiguous stripes, an eightfold
attempt budget, and the picture-derived margin (refuted before implementation by the 51% figure).
Four of my readings of the board were also wrong and each was killed by a measurement. The live
tree is untouched.

##### The control that confirms the s5i5 park: the clearing level's frame hides NOTHING

Before accepting "the level needs information the tool cannot obtain", the obvious objection is that
level 6 has a frame too and clears anyway. Measured:

```
level 6 (clears)   frame 0005  57x15 at (3,27)    hidden solid cells = 0     entirely on-screen
level 7 (stuck)    frame 0006  70x51 at (-3,-3)   hidden solid cells = 291
```

**Level 6's frame is fully inside the grid, so the tool sees all of it.** That is the single
structural difference between the level that clears and the level that does not, and it turns the
park from an assertion into a controlled result: the same tool, the same mechanic, the same planner,
differing only in whether the furniture is visible — and it clears exactly when it is.

⛔ So the park stands, and it is now falsifiable in one line: **make the hidden 291 cells knowable by
any means and level 7 should clear.** Anything that does not add that information has already been
measured not to help, six times.

##### ⛔ THE s5i5 PARK IS FALSIFIED — perfect knowledge of the hidden furniture changes NOTHING

The park's own one-line falsifier was "make the hidden 291 cells knowable and level 7 should clear".
Ran it: an oracle probe reads the level file and injects the exact hidden footprint into the model's
`offblocked` before planning begins.

```
[oracle] lvl=5 handed 0 hidden cells       (level 6 — nothing is hidden there, as measured)
[oracle] lvl=6 handed 291 hidden cells     (level 7 — the entire hidden frame)
[oracle] injected total offblocked=291
         levels=6/8   game_score=0.5833    UNCHANGED
```

⛔ **So the missing information is NOT the cause.** With perfect knowledge of every hidden cell the
level still does not clear, which means the whole chain I built tonight — refusal-learning reaching
only a sixth of the wall, the attempt budget, the unpredictable margin, the control that "confirmed"
it — explains a real difference between the levels that is **not what stops this one.**

⚠️ The control (level 6 hides zero cells, level 7 hides 291) is still a true and clean measurement.
It just does not license the causal claim I drew from it: a difference that correlates perfectly
with success is not thereby the cause, and the only way to know was to supply the missing quantity
and look. **Six repairs and one park, all resting on an inference an oracle refutes in one run.**

**What this leaves for s5i5**: the tool reads the board correctly, models every arm but the frame,
plans successfully, and its plans are refused by the engine for a reason that is NOT collision with
hidden furniture. The refusals are real (`ctrl=0 step=+1`, twice, in states where the same control
passes elsewhere) and their cause is now genuinely unknown — every candidate tonight has been
measured and rejected.

⛔ The oracle is a PROBE and was never in the live tree; it reads `environment_files` directly and is
unshippable by construction. It is worth keeping the technique: **when a park says "it needs
information X", hand it X and see.** That took one run and overturned an evening's reasoning.

##### The "already there but unused" sweep — two tie-breaks found, both measured WORSE

After a night that moved the score by zero, the honest read was that the three gains of the day were
all one shape: something already present that was not being used (`fogscout` unregistered, `_reveals`
used as a boolean, confirmations unbounded by the plan). So instead of digging further into a parked
game, the whole stuck set was swept for the same shape — **which tool bids and never gets to act.**

Printing every decision's bid table found exactly two ties, both broken by registration order:

```
lf52   railpeg 0.95   pegjump 0.95   <- pegjump never wins the board
wa30   shepherd 0.75  haul 0.75      <- haul never wins the board
```

Both were tested by reversing the registry order, and both are **worse**:

```
wa30   shepherd (current)  0.8000      haul first   0.6222
lf52   railpeg  (current)  0.2727      pegjump first 0.1818
```

⛔ So the registration order is already the right answer on both boards — it encodes a measured
preference, not an accident, exactly as `concepts/tool_claim_breadth` says it should. The sweep is
closed with no gain, and that is worth recording precisely so it is not re-run: **there is no
unregistered tool and no losing tie-break left in the stuck set.**

⚠️ The sweep itself was the right instinct at the right moment — the day's three gains came from that
shape and cost minutes each, while the evening's deep dive into one board cost hours and produced
diagnosis without score. The lesson is about ordering the work: **sweep for unused assets first,
dig second.**

##### crag's ranking is now measured at every position — the axis is closed

bp35 0.2078 -> **0.2220** came from moving `reach` above the block count. Four further orderings,
run in parallel on the box against the current key:

```
current  (fresh, safe, reach, -marks, -leg)     bp35 0.2220   lf52 0.2727
v1       (fresh, reach, safe, -marks, -leg)          0.2220        0.2727
v2       (fresh, safe, reach, -leg, -marks)          0.2214        0.2727
v3       (fresh, reach, -marks, safe, -leg)          0.2220        0.2727
v4       (reach, fresh, safe, -marks, -leg)          0.1294        0.2727
```

**Nothing beats the current key**, `safe` and `reach` are interchangeable in the second and third
slots, and ⛔ **`fresh` must stay first** — demoting it costs 0.093 on bp35. The reveal cap is
already optimal too (1 -> 0.2033; 2, 3 and 6 all -> 0.2220).

⚠️ Why `reach` matters at all is in the board, not the tuning: bp35's level 2 offers **280 of 323**
candidate landings at `reveal=1`, so the magnitude term is flat across nearly the whole frontier and
whatever ranks below it decides the level. That is also why the earlier magnitude change helped
level 3 (81 -> 45 actions) and slightly hurt level 2.

**No further ordering work on this tool.** lf52 is untouched by every variant, so its 0.2727 is not
a ranking problem either.

##### lf52 reads its CAMERA per level, and levels 1-5 are the horizontal-only ones

lf52 builds its board at runtime, so `level_data_diff` and the sprite diff both see one sprite per
level and say nothing. The game's own code does say something: it branches on the level number
(`whtqurkphir = _current_level_index + 1`) to choose how far the camera moves:

```
level 4      (-dx*8, 0)     and (0,0) when grid_y >= 11
level 5      (-dx*6, 0)
level 6      (-dx*6, 0)
levels 7,10  (0, 0)          camera pinned
level 8      (0, -dy*6)      VERTICAL scroll
otherwise    (-dx*6, -dy*6)  BOTH axes
```

**The five levels the tool clears — all at the 1.0 cap and all faster than the human (8/32, 52/81,
57/60, 64/71, 138/205) — are exactly the horizontal-only ones.** Levels 7 and beyond introduce a
pinned camera, vertical scrolling, and two-axis scrolling.

⚠️ **But level 6 uses the SAME rule as level 5** `(-dx*6, 0)` and is not cleared, so the camera is
not what stops the run — something else does, and it stops it one level before the camera changes.
That is a useful negative: it rules out "the tool cannot handle vertical scroll" as the explanation
for the FIRST failure, while flagging it as a real wall waiting at level 8.

⛔ It also explains why every `crag` ranking variant left lf52 at exactly 0.2727: the game is stuck
on something the ranking cannot reach.

##### THE CARD IS PORTABLE TO KAGGLE HARDWARE — three environments agree to six decimals

Kernel v6, pushed at commit `9f1bb9b2` (generic tools, zero adapters), run on the competition's own
GPU machine:

```
arm_llm        total_score=0.893487   25 games    real gemma-4-31b behind vLLM
arm_fallback   total_score=0.893487   25 games    signature routing
games differing: 0
ceph-build     0.8935                 the same tree, measured on the box
```

**ceph-build, this laptop and the Kaggle GPU now produce the same number.** Two days ago ka59 alone
scored 1.0000 on one machine and 0.7500 on another from byte-identical code; that class of drift is
gone, and it is the precondition for the public number saying anything about the hidden one.

⛔ **And the LLM still changes nothing** — 25 of 25 identical, as on 2026-08-27 when both arms scored
0.853963. The tools improved by +0.04 and both arms moved together, so every number this round has
ever quoted is the LLM-free path and the model's contribution on these boards remains exactly zero.

##### lf52 level 6: no waste, no aiming problem, two tools and 404 actions

Attributed per action with the event carrying its own level:

```
level 6   railpeg 285   pegjump 119   PROBE 0
levels 1-5  railpeg only, 8/52/57/64/138 actions against human 32/81/60/71/205 — all at the cap
```

**Every action on the stuck level is a real tool proposal**, and two different tools take turns at it
without clearing. So lf52 joins bp35 in the "the plan is honest and insufficient" class rather than
the waste class — and combined with the camera finding (level 6 uses the same horizontal-only rule
as level 5, which clears), what stops it is neither the camera nor the harness.

##### lf52 level 6: railpeg plans and executes all the way through, and the board does not advance

Instrumented with `scripts/instrument_tool.py` — score preserved at 0.2727 and zero propose errors,
so the reading is of the tool and not of a broken copy:

```
558 marker lines,  0 propose errors
site=1304  309x   execute the planned move, one step        <- the main path
site=1288  142x   execute a multi-step move
site=1253   88x   a settle click
site=1252   11x   return [] (the settle cap)
```

**`railpeg` keeps planning and executing on the stuck level** — the empty return fires eleven times
out of 558. Yet the harness swaps it out at step 381 on `action no new state x15`, and `pegjump`
then spends 119 more actions without clearing.

So the plans run to completion and **the board does not reach a new state**. That is neither waste
(zero probe actions), nor aiming, nor perception, nor the camera (level 6 uses the same
horizontal-only rule as level 5, which clears at the cap). lf52's remaining 0.727 sits behind a plan
that executes and does not achieve anything — the same class as bp35, and the sharpest statement
available without a model of what level 6 asks for.

##### lf52 and bp35 are NOT the same class after all — one wastes a third of its actions

Measured per action at the runner, with the frame compared before and after (score preserved, zero
propose errors, so the instrument is clean):

```
lf52   L1-L5 100% effective        L6  500 actions, 329 changed the board  (66%)
bp35   L1-L5 100% effective        L6  500 actions, 500 changed the board  (100%)
```

⛔ **lf52 level 6 wastes 171 actions — a third of the level — on moves the engine refuses**, while
every earlier level is perfectly effective. bp35's stuck level wastes nothing at all.

That splits what I had put in one class last night. bp35 really is "an honest plan that is
insufficient": every action does something and the level still does not fall. lf52 is a REFUSAL
problem — the tool proposes moves that leave the board untouched, and it does so only on the level
it cannot clear.

⚠️ And it corrects the earlier lf52 reading. "Zero probe waste" was true — the harness never
substitutes a probe there — but zero probe waste is not zero waste: the tool's OWN proposals are
what the engine declines. Counting only the harness's fallback missed a third of the level.

##### lf52's waste is ONE DIRECTION: ACTION1 is refused 133 times out of 154

Every level-6 action tagged with its kind and whether the frame changed (score preserved at 0.2727,
zero propose errors):

```
              refused   accepted    refusal rate
ACTION1          133        21          86%      <- the whole of the waste
ACTION3           11        76          13%
ACTION2            3         9          25%
ACTION4            0        35           0%
click             24       188          11%
```

**171 wasted actions and 133 of them are the same key.** The tool keeps pressing a direction the
board almost always refuses, while the other three and the clicks work normally.

⛔ This is not "an insufficient plan" and not a perception failure — it is a MOVE MODEL that has not
learned an axis is blocked. `railpeg` reaches its execute branch 309 times (measured earlier) and a
large share of those executions are a key press the engine declines.

⚠️ Note how the readings narrowed, because the order mattered: "zero probe waste" (true, and
misleading) -> "34% of the level is refused" (the runner comparing frames) -> "one direction is 86%
of it". Each step needed the previous instrument to be verified harmless first — the score stayed at
0.2727 through all three.

**The lever is now specific**: a direction refused this consistently should stop being proposed. The
tool has a `_dirmap` and a settle counter; what it lacks is a per-axis refusal memory. That is a
small, testable change with a clear verification — levels 1-5 must stay at their 8/52/57/64/138
actions, and level 6's 500 must stop containing 133 refused ACTION1 presses.

##### lf52 level 6: THE MAP IS NOT WHAT STOPS IT, and the last column is not needed to win

Instrument: `scripts/_lf52_map.py`. `score_efficiency.run_game` drives the steps (rule 7aj.1 — the
loop is never re-implemented); `arcade.make` is wrapped only to capture the env and the adapter only
to READ. Once per action the oracle takes the ENGINE's own state — level, in-level counter, camera
offset `grid.cdpcbbnfdp`, pieces, carts, who rides a cart, and, using the engine's OWN legality
predicate `qikmikecdf`, how many jumps are legal and how many of them LAND ON A CART — beside
railpeg's `len(model.known())`, its column span and its piece count. That is a dev-time oracle for
diagnosis only; the tool is untouched and stays frame-only.

**Both controls, before any arm is read** (rule 7ai):

```
NEGATIVE  the instrument must not perturb    per-level [8, 52, 60, 64, 139], 823 actions, 0.272727
                                             — identical to the banked R101BP35 lf52.json        OK
POSITIVE  the oracle must be able to say YES camera seen MOVING on levels 3, 4, 5, 6
                                             boarding move seen on levels 2, 3, 4, 5, 6          OK
```

The positive control is the load-bearing one: without it an all-zero level-6 reading is
indistinguishable from an oracle that measures nothing, which is how nine instruments failed in two
days.

**The census, level 6, 500 actions:**

```
known 54 -> 98 by level-action 44, then FLAT for the remaining 456 actions   known_drops = 0
camera  (5,5) -> (-15,5) at action 26 -> -21 -21 ... -75 by action 43 -> NEVER past -75
boarding moves exist at 22 decision points, actions 24..123 — and at none of the 377 after
the ENGINE offers ZERO legal jumps at 213 of the 500 decision points, from action 29 onward
pieces 8 -> 7 (a14) -> 6 (a16) -> 5 (a124) -> nothing for the rest of the level
```

**H4 (the model discards its map) is REFUTED**: `known_drops = 0` and `known_final == known_max ==
98`. Nothing is retracted, re-anchored or overwritten.

**H3 (growth is possible but never ranked) is REFUTED at the position**: past action 123 there is no
boarding move to rank, and at five of the seven moments the camera sits at the one offset that still
matters the engine has NO legal jump at all. `_rail_reach` already ranks boarding by what a track can
reach, and it fired — the (7,6) boarding at action 26 is that tier working.

**H2 is CONFIRMED, and the game's own source names the mechanism.** In
`environment_files/lf52/271a04aa/lf52.py` the level-6 camera moves in exactly three ways and no
others:

```
(a) cfilhtifcb   a jump LANDING on cell (7,6) — which is a cart — while the offset is (5,5)   -20
(b) tmhxwcojkh   a cart drive while a plain `fozwvlovdui` rides that cart                     -6 each
(c) cfilhtifcb   a jump landing on cell (18,2) while the offset is EXACTLY (-57,5)            -44
```

The run performs (a) once and (b) eleven times, and that is the entire -75. Then (b) is exhausted:
row 6 carries rail from column 7 to column 17 and the laden cart is at its end. Only (c) is left,
and (c) is a landing square — (18,2) is reachable only from (16,2) over (17,2) or from (20,2) over
(19,2), and both midpoints start EMPTY, so the jump has to be CONSTRUCTED two moves ahead. The run
stands at offset -57 seven times (actions 38, 52, 68, 94, 109, 111, 113) and the engine has zero
legal jumps at five of them.

⭐ **AND NONE OF IT MATTERS, which is worth more than the census.** The board is 28 columns wide and
90 cells; the three the tool never sees are (26,2), (26,3), (26,4). Level 6's win predicate is
`len(ndtvadsrqf("fozwvlovdui")) == 2` — take eight pieces down to two — and the red piece is
uncapturable (`cfilhtifcb` removes the jumped piece only when `qcerbdpdcl.name == uywtlohliu.name`),
so the level asks for six captures of the seven plain pieces and **the piece at (26,3) can simply be
the survivor**. Opening column 26 wins nothing. ⛔ Nobody spends a day on lf52's map.

**What actually stops the level, measured**: the tool is at 6 pieces by action 16 — two captures in
sixteen actions, the free half — and then takes its third at action 124, after which the ENGINE has
zero legal jumps for the remaining 143 actions of the attempt. That is the same verdict
`scripts/_lf52_stall.py` reached by forcing every legal move, and the same one `plan_level`'s own
docstring records from the other side: *"at the third capture, the seven cheapest candidates are each
a dead end and the eighth is not — taking it finishes the level in 87 actions against a human
baseline of 148"*. Three independent readings agree that lf52 level 6 is decided at capture three.

⚠️ So `plan:all-candidates-fatal` firing 11-18 times is the veto being RIGHT, and the one time the
last-resort override fires it loses the level. The lever is not a bigger map and not a looser veto —
it is finding the eighth branch among eight, on a map that is already complete enough to contain it.

##### lf52 level 6: the game DECLARES the branch lost, the tool then presses its restart button by accident — and 376 of 500 actions go to that

Same instrument, one field added: the engine's own `zvcnglshzcx` — the flag that means "the restart
control is live". `equnaohchtj.pchvqimdvj()` raises it when the level reaches a position the DESIGNER
marks as lost (it greys the pieces and floats a `cwyrzsciwms` sprite up from the bottom-left), and
`Lf52.jxyktkxwle` then treats **any ACTION6 with `x < 16 and y > 48` as "restart this level"**.

```
level      zv_points   in-level counter falls   railpeg's piece count at the end
1-5            0             none                    2   (the level was won)
6            143          at action 267             5   (the board has EIGHT)
```

Read the twelve actions before the fall and it is unambiguous:

```
255 used=255 act=ACTION2 cam=(-57,5) p=5 legal=0 zv=True  mp=5 st=NOT_FINISHED
...  eleven more, ten of them ACTION6, every one with zv=True and legal=0
266 used=266 act=ACTION6 cam=(-57,5) p=5 legal=0 zv=True  mp=5 st=NOT_FINISHED
267 used=  0 act=ACTION1 cam=( 5,5)  p=8 legal=2 zv=False mp=5 st=NOT_FINISHED   <- LEVEL RESTARTED
```

Three things, each measured:

1. ⭐ **The game hands out a free fatality oracle and the tool does not read it.** `zv` goes TRUE at
   level-action 124 — the exact action of the third capture — and stays TRUE for 143 actions. The
   engine is saying *this branch is lost* in the frame, for a quarter of the level, while
   `plan_level`'s veto is separately deducing the same thing by search. `plan_level`'s own docstring
   already names this signal (*"the game SHIPS A DETECTOR for exactly that, greying the pieces out
   and offering a restart"*) — nothing in the tool observes it.

2. ⛔ **The restart has NO state signal, and this is a counterexample to rule 7z.** `obs.state` reads
   `NOT_FINISHED` on every one of the 500 actions; `levels_completed` never moves; the agent issues
   zero `RESET`s. The ONLY evidence a restart happened is the engine's private in-level counter
   falling 266 -> 0 — invisible to any frame-only tool that is not looking for the board to jump back
   to its opening. Rule 7s said a restarting level reads like a continuing one; rule 7z answered
   "`GAME_OVER` is the only reliable signal". **On lf52 level 6 there is no `GAME_OVER` either.**

3. ⛔ **The model survives the restart and is then wrong for 233 actions.** After the fall the board
   holds 8 pieces at the opening camera; railpeg still says 5, and still says so at the last action of
   the game. `_align` succeeds (the lattice is identical, which is exactly why the restart is
   invisible) and `_install` deliberately keeps what the window cannot see — correct on a scrolling
   board, fatal after a restart. The second attempt makes **zero captures and zero camera movement in
   233 actions**.

**Price**: 143 actions after the game called the branch lost, plus 233 on a stale model = **376 of
level 6's 500 actions, 75%**, spent in positions that could not produce a clear. It costs nothing in
RHAE today (an uncleared level scores 0 either way) and it costs the whole of the second attempt,
which is the only place a different third capture could have been tried.

⚠️ Careful with the obvious repair. "Do not click the bottom-left corner" is NOT it — `_settle_click`
already avoids the edges (it scans `x >= w // 3`), so the offending clicks are ordinary planned
`propose` clicks whose coordinates happen to land there once the camera has scrolled. And "detect the
restart and re-anchor" is only half: re-anchoring without remembering that the third capture was
fatal buys a second attempt that repeats it.

##### lf52 level 6: the third capture is the DESIGNED losing move, and the model is blind to exactly the two pieces that would show it

Same instrument, one field added: the ENGINE's piece cells beside the model's, matched on the single
translation that fits the most of them (the same test `_align` uses). At level-action 123 — the
decision immediately before the fatal capture — the offset `model = (engine_y - 2, engine_x + 3)`
places four of six:

```
engine  6 pieces   (6,6) RED   (14,2)  (15,2)  (20,7)  (22,5)  (26,3)
model   5 pieces               (14,2)  (15,2)  (20,7)  (22,5)          + one cell that maps off-board
MISSING            (6,6) and (26,3) — and they are the only two that matter
```

At action 124 the engine's pieces are `(6,6) (16,2) (20,7) (22,5) (26,3)`: a jump from (14,2) over
(15,2) landing on (16,2), capturing (15,2). Now read the game's own level-6 branch in `cfilhtifcb`:

```python
elif self.whtqurkphir == 6:
    if fldpqdkmge == (16, 2) and uywtlohliu.name == "fozwvlovdui":
        if self.hncnfaqaddg.whdmasyorl("fozwvlovdui_red")[0].chahdtpdoz == (6, 6):
            self.pchvqimdvj()      # grey the pieces out, float up the restart control
```

⭐ **Landing a plain piece on (16,2) while the red piece stands on (6,6) is the ONE position this
level's author marks as lost, and it is exactly the capture railpeg takes.** Both halves of that
conjunction are the tool's own doing: red starts at (2,2) and nothing but the agent moves it, so the
tool armed the trap and then sprang it — while its model held neither the red piece nor the
precondition's meaning. `zvcnglshzcx` goes TRUE on that action and stays TRUE for 143.

⭐ **And the other missing piece, (26,3), is PROVABLY INERT** — which strengthens the earlier
conclusion rather than weakening it. Its left neighbour (25,3) is `kraubslpehi-up`, rail with no
hole, so `posalhhmjq` forbids any piece ever standing there to be jumped over; (27,3), (26,1) and
(26,5) are off the board entirely. It can never jump, never be jumped over, never be captured. **So
it must be the survivor**, the level asks for exactly six captures of the other six plain pieces, and
the column the map never reaches is worth exactly nothing to open. What its absence DOES cost is
arithmetic: `_won` over a model that lacks it is satisfied one capture early — the "a win that did
not win" case `_ensure_plan` already detects, and `_elsewhere` is set at level-action 4.

**So the corrected picture of lf52 level 6, three measurements deep:**

```
actions   0- 16   two captures, free, on the visible left of the board
actions  24- 44   boards the cart at (7,6), rides it out, map 54 -> 98 and complete for its purpose
actions  45-123   crosses the frontier back and forth; the engine offers <= 2 legal jumps, mostly 0
action     124    takes the third capture — the position the game itself calls lost
actions 124-266   143 actions with zero legal jumps and the restart control lit
action     267    a click lands in the restart zone; the level silently restarts
actions 267-500   233 actions against a board the model is wrong about
```

⛔ The lever is the ONE move at action 124, and neither a bigger map nor a looser veto reaches it.

##### The restarting click, MEASURED — and why it is invisible to any tool reasoning in world coordinates

The twelve actions before the counter falls, now with the click coordinates:

```
256 ACTION6 xy=(40,21)  zv=True legal=0        263 ACTION6 xy=( 4,42)  zv=True legal=0
258 ACTION6 xy=(43,21)  zv=True legal=0        264 ACTION6 xy=(30,25)  zv=True legal=0
260 ACTION6 xy=(29,24)  zv=True legal=0        265 ACTION6 xy=(48,25)  zv=True legal=0
262 ACTION6 xy=(28,30)  zv=True legal=0        266 ACTION6 xy=( 6,56)  zv=True legal=0   <- x<16, y>48
267 the board is back at 8 pieces and the opening camera
```

`Lf52.jxyktkxwle` intercepts **any** ACTION6 with `x < 16 and y > 64 - 16` as "restart this level"
whenever `zvcnglshzcx` is live — before `dghsidbuet` ever looks at what is under the cursor. So the
click at (6, 56) is an ordinary planned click on a board cell that, at camera offset -57, happens to
sit under a screen-space control.

⛔ **railpeg's guard cannot catch this and neither can any successor of it.** `propose` already
refuses a plan whose pixels fall outside the frame — `(6, 56)` is comfortably inside. The hot-zone is
in SCREEN space and the tool plans in WORLD space; once the camera scrolls, ordinary playfield lands
under the control. There is no frame-only rule that distinguishes them without first noticing that a
control appeared.

**Both directions of the control, and this is what makes it a finding rather than a story:**

```
level   hot-zone clicks   of those, while the control was live   restart
  3            1                        0                          no
  4            1                        0                          no
  6           10                        1                          YES
```

⭐ The same click shape happens on levels that CLEAR and costs nothing there. It is destructive only
in the 143-action window where the game has already declared the branch lost — which means the
exposure disappears the moment the tool stops playing into a position with zero legal moves. **The
cheap repair is not "avoid a corner"; it is "stop clicking when nothing is legal".**
