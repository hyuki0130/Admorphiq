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
REGION, no failed win required. Whether "look before spending an irreversible capture" can pay
here is open, and on this level may not be answerable, because looking costs the pieces that make
looking possible.

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
