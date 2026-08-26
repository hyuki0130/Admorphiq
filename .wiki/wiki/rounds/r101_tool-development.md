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