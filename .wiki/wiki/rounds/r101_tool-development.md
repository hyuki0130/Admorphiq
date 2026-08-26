---
type: reasoning
round: R101
axis: stage 1 of the top policy — develop the generic tools until they clear all 25 sample games
keywords: [tool-development, 25-of-25, stage-one, inert-actions, dead-signature, goal-inference, graph-search, stall-diagnosis, per-game]
verdict: OPEN — the 25-game diagnosis is in and it splits the work into three named repairs.
date: 2026-08-26
---

# R101 — stage 1: develop the tools to 25/25

> Stage-one round: build frame-only rule-recovery tools until the 25 sample games clear — three tools registered, the action-budget finding, and the selectivity rule that governs how tools are kept.

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
