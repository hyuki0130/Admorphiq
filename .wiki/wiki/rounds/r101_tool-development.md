---
type: reasoning
round: R101
axis: stage 1 of the top policy — develop the generic tools until they clear all 25 sample games
keywords: [tool-development, 25-of-25, stage-one, inert-actions, dead-signature, goal-inference, graph-search, stall-diagnosis, per-game]
verdict: OPEN — the 25-game diagnosis is in and it splits the work into three named repairs.
date: 2026-08-26
---

# R101 — stage 1: develop the tools to 25/25

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
