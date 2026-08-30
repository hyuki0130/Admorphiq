---
round: R101ABLATE (own / drop1 / drop1b / neg / squat / nograph)
axis: what does the harness do on a board whose mechanic NO TOOL implements — manufactured by removing each game's owner
keywords: [ablation, owner, ownership, latch, no-tool-fits, private-110, floor, transfer, graph, world_model, primary_owns, fallback, generic-path, unseen-game, ablategate]
verdict: MEASURED — 0.9082 -> 0.1932 with each game's owner removed, and THE FLOOR IS NOT FLAT (13 games at ~0, 9 at >=0.30, stdev 0.256). The latch is real but STRUCTURAL, not `graph`-specific: removing `graph` too moves the mean by 0.0007 because `world_model` does the identical thing. `_PRIMARY_CONF` is REFUTED as the latch mechanism — every latched tenure has `primary_owns` FALSE.
commit: a8d2941c, 3fb1d417
builds_on: [[r101_silent-specialists]]
---

# R101 — the harness on a board it has no tool for

> Every transfer instrument this campaign owns perturbs the **rendering** of a game whose mechanic
> one of our tools already implements — the archived re-render, the colour permutation, the
> identifier rename, the z-order swap. **None perturbs the MECHANIC.** But the private-110
> condition, for most of those 110 games, is exactly *a board whose mechanic no tool in the registry
> implements*. We cannot obtain a new mechanic. We can obtain the CONDITION: remove the tool that
> owns a game and score it again.

## The instrument

`scripts/ablategate.sh` + `scripts/ablate_run.py` + `scripts/ablate_report.py`. The ablation
monkeypatches `admorphiq.harness.registry.default_tools` for the lifetime of one measuring process
inside a private snapshot of HEAD on ceph-build — nothing is edited in the shared tree (rule 7l),
and nothing ships off the back of it (rule 7o). Six arms, 110 game-runs, budget 4000, PAR 12.

| arm | what it drops | dir |
| --- | --- | --- |
| `own` | nothing — the control, and where ownership is READ from | `scripts/rounds/R101ABLATEOWN` |
| `neg` | `toggle`, a tool with **zero actions on every one of the 25** | `R101ABLATENEG` |
| `drop1` | each game's level-clearing owner | `R101ABLATEDROP1` |
| `drop1b` | the same, re-run with `_primary_owns` recorded | `R101ABLATEDROP1B` |
| `squat` | the action-plurality holder where it differs from the clearing owner | `R101ABLATESQUAT` |
| `nograph` | each game's owner **and** `graph` | `R101ABLATENOGRAPH` |

## Both controls hold

```
NEGATIVE  drop 'toggle' (registry 47 -> 46), all 25 games
          differing from `own` in score, levels OR action count:  ZERO
CONTROL   `own` vs scripts/rounds/R101SHIPPED   0 of 25 differing
          `own` vs scripts/rounds/R101LP85GATE  0 of 25 differing   mean 0.9082
POSITIVE  drop1: 25 of 25 games MOVED. Not one is unchanged.
REPEAT    drop1 vs drop1b (same arm, run twice): 0 of 25 differing
```

⛔ The negative control is the one that matters. An ablation harness that scores identically when it
removes an idle tool has not demonstrated that it removes anything at all — it is the
fail-toward-nothing shape (rule 7aj), and here it comes back exact on score, levels **and** action
count, which is stronger than score alone.

## ⭐ Ownership by ACTION SHARE is wrong on three of five games, and the error INVERTS

The obvious ownership metric — which tool spent the most actions — is measured wrong here, and
wrong in the direction that would have destroyed the round. Read per action from
`UnifiedAgent._current`, never from `detect()` (rule 7g):

```
game   action-plurality   the tool that actually CLEARED the levels
bp35   graph  486         crag  (clears L0-L4; graph spends 486 on terminal L5 and clears nothing)
s5i5   linkage 463        swivel (clears L0-L5; linkage spends 463 on terminal L6)
lf52   railpeg 444        railpeg   (agrees)
ls20   keymaze 423        keymaze + fogscout — a GENUINE handover, fogscout clears L6
re86   cover_targets 379  cover_targets + reforge — genuine, reforge clears L5,L6,L7
```

The `squat` arm prices the difference directly, and it is the whole gap between a result and a
non-result:

```
game  dropped        ctrl     abl    delta   verdict
bp35  graph        0.2456  0.2456  +0.0000   the "owner" is worth EXACTLY ZERO
lf52  graph        0.2727  0.2727  +0.0000   "
s5i5  linkage      0.5833  0.5833  +0.0000   "
ls20  fogscout     0.9121  0.7500  -0.1621   a real second owner: costs the terminal level
re86  reforge      1.0000  0.4167  -0.5833   a real second owner: costs three levels
```

⛔ **Three of the five games do not feel the loss of the tool that spent most of their actions.** A
`drop1` built on action share would have ablated nothing on bp35, lf52 and s5i5 and reported "the
harness copes". This is rule 7aj's fourth clause — prefer a quantity that IS what it measures —
caught before it cost a verdict, because `ablate_report.py` refuses a game whose ablated score is
identical rather than averaging it in. ⭐ And the *reason* it is zero is already banked: those
actions are all spent on a level the game never clears, which scores zero however it is spent
(rule 7bq).

## The ablation table — the whole point of the round

Each game scored with the tool that clears its levels removed. Budget 4000; runs end early on the
outer `no_progress` guard (500 actions since the last level-up).

```
game     ctrl     abl    delta   lv ctrl  lv abl   dropped -> who inherits
ar25   1.0000  0.0000  -1.0000     8/8       0     reflect_cover -> graph 500
bp35   0.2456  0.0000  -0.2456     5/9       0     crag          -> graph 500
cd82   1.0000  0.0064  -0.9936     6/6       1     stamppaint    -> graph 649
cn04   1.0000  0.0000  -1.0000     6/6       0     assemble      -> graph 500
dc22   0.7143  0.4762  -0.2381     5/6       4     gantry        -> graph 438, phase_grid 291
ft09   1.0000  0.0000  -1.0000     6/6       0     stencil       -> graph 500
g50t   1.0000  0.1071  -0.8929     7/7       2     clonewalk     -> maze 460, graph 191
ka59   1.0000  0.4532  -0.5468     7/7       5     blastclock    -> graph 412, slotlaunch 260
lf52   0.2727  0.0182  -0.2545    5/10       1     railpeg       -> graph 457, pegjump 50
lp85   0.9767  0.3394  -0.6373     8/8       5     cyclepress    -> graph 484, track 103
ls20   0.9121  0.0000  -0.9121     7/7       0     keymaze       -> graph 500
m0r0   1.0000  0.7143  -0.2857     6/6       5     decouple      -> mirror 731
r11l   1.0000  0.0043  -0.9957     6/6       1     tether        -> graph 572
re86   1.0000  0.0278  -0.9722     8/8       1     cover_targets -> graph 492, reforge 31
s5i5   0.5833  0.4167  -0.1667     6/8       5     swivel        -> linkage 335, telescope 168
sb26   1.0000  0.0000  -1.0000     8/8       0     subroutine    -> graph 500
sc25   1.0000  0.4345  -0.5655     6/6       4     sigilgate     -> graph 424, pattern_cast 147
sk48   1.0000  0.0000  -1.0000     8/8       0     tube_order    -> graph 500
sp80   1.0000  0.7143  -0.2857     6/6       5     sluice        -> graph 492, spill 95
su15   1.0000  0.4882  -0.5118     9/9       7     orderforge    -> graph 440, socketmerge 206
tn36   1.0000  0.0069  -0.9931     7/7       1     progbits      -> graph 572
tr87   1.0000  0.0000  -1.0000     6/6       0     rule_rewrite  -> graph 500
tu93   1.0000  0.0000  -1.0000     9/9       0     lattice_maze  -> graph 500
vc33   1.0000  0.0000  -1.0000     7/7       1     pillar_transfer -> graph 810
wa30   1.0000  0.6222  -0.3778     9/9       7     shepherd      -> haul 696, graph 253

MEAN 0.9082 -> 0.1932      median 0.0069   stdev 0.2558   min 0.0000   max 0.7143
levels: 25 of 25 games reach level 1 in the control; 16 of 25 with the owner gone
13 games score below 0.01 · 9 games score at or above 0.30
```

## ⛔ THE FLOOR IS NOT FLAT — and a single number must not be quoted

The hoped-for result was a boring, uniform row: *"with its owner removed every game falls to roughly
X"*, which would have been the campaign's first quantitative statement about the 110. **It is not
what came back.** The distribution is bimodal with almost nothing between the modes, and the
separator is measured, not guessed — whether any surviving tool CLAIMS the orphaned board, read
from `_primary_owns` at the first tenure of the ablated run:

```
                                        n   mean     median  levels  actions
a second tool CLAIMS the board         11   0.3725   0.4345    4.2      648
no tool claims it (generic path alone) 14   0.0523   0.0000    0.6      567
   ... of those 14, m0r0 alone scores 0.7143; the other 13 average 0.0014
```

CLAIMED: dc22 g50t ka59 lf52 lp85 re86 s5i5 sc25 sp80 su15 wa30
UNCLAIMED: ar25 bp35 cd82 cn04 ft09 ls20 m0r0 r11l sb26 sk48 tn36 tr87 tu93 vc33

⚠️ **`m0r0` is the honest exception and is not smoothed over here**: `mirror` takes the board with
`primary_owns` FALSE, holds all 731 actions, and still clears 5 of 6 levels for 0.7143. So
"claimed" predicts the mode but does not determine it, and the round does not claim it does.

⛔ **AND 0.1932 IS PROBABLY OPTIMISTIC AS A PRIVATE-110 ANALOGUE.** In all eleven CLAIMED games the
claimant is another of OUR specialists that happens to partially fit a PUBLIC board we built
against — `phase_grid` on dc22, `slotlaunch` on ka59, `haul` on wa30. An unseen game has no such
near-miss waiting for it by construction. **The 13-game UNCLAIMED figure of ~0.0014 is the closer
analogue of "no tool fits", and 0.1932 is the closer analogue of "the mechanic is new but adjacent
to one we implement".** Quote the pair, never the mean alone.

## ⭐ The latch is REAL, is STRUCTURAL, and `_PRIMARY_CONF` is refuted as its cause

The design question was: with the owner gone, does a wrong tool latch and hold the board for the
whole budget — `_PRIMARY_CONF = 0.70` in `harness/loop.py` makes a tool bidding above it unretirable
— or does the harness cycle and keep searching? **Both happen, and the mechanism is not the one the
threshold suggests.** From the decision log, not the source (rule 7g):

```
14 of 25 ablated games have exactly ONE `[harness] pick=` line for the entire run.
ar25:  1:graph   -> 500 actions, ZERO levels, never re-decided
sb26:  1:graph   -> 500 actions, ZERO levels, never re-decided
tu93:  1:graph   -> 500 actions, ZERO levels, never re-decided
```

⛔ **AND EVERY ONE OF THOSE FOURTEEN TENURES HAS `primary_owns` FALSE.** The latching tool is *not*
exempt from stall retirement; it is eligible and is never retired anyway. It never goes silent
(`_EMPTY_TOLERANCE`, 8 consecutive empties) and it never stalls (`stall`, 80 steps without a new
state) because a frontier explorer always proposes a move and always reaches a new state. **It looks
productive by every signal the harness watches, while clearing nothing.** That is a much worse
failure than a confidence threshold, because no threshold tuning addresses it.

The eleven cycling games show the harness working exactly as designed, and always ending the same way:

```
dc22   1:phase_grid*PRIMARY*   292:none   293:graph      -> 4/6
wa30   1:haul*PRIMARY*         697:none   698:graph      -> 7/9
s5i5   1:telescope*PRIMARY* 169:none 170:linkage*PRIMARY* 505:none 506:graph -> 5/8
```

⭐ **In every cycling game the chain terminates at `graph` and the game ends there.** A tool that
genuinely claims the board is picked, is retired when it runs out, and the generic explorer inherits
what is left. The harness *does* know how to keep searching — it simply runs out of claimants, and
what it falls back to cannot tell that it is lost.

## The latch is not about `graph` — measured, not argued

The obvious repair is to stop `graph` seizing orphaned boards. The `nograph` arm removes each game's
owner **and** `graph`:

```
drop owner            mean 0.1932
drop owner + graph    mean 0.1925      4 of 25 games differ, ALL DOWNWARD
                                       cd82 0.0064->0, r11l 0.0043->0,
                                       tn36 0.0069->0, vc33 0.00002->0
```

`world_model` steps into `graph`'s place and does the identical thing — 492 actions against
`graph`'s 500, clearing nothing, on eleven boards at once. ⛔ **So "a wrong tool latches" is a
property of the fallback POSITION, not of the tool occupying it.** Any generic explorer put at the
end of the chain behaves this way, and deleting the current occupant promotes the next one. This
closes "remove/demote `graph`" as a repair before anyone spends a day on it.

## What this says for the 110

1. **The generic path, on a board no tool claims, reaches level 1 nine times out of twenty-five and
   scores ~0.0014.** The campaign's 0.9082 is a statement about twenty-five boards for which
   twenty-five specialists were written.
2. **The failure is silent.** The harness has no signal that says "I do not understand this board".
   Every retirement condition it owns — empty proposes, stall, death clock — is satisfied by a tool
   that explores productively and solves nothing. ⭐ **A tool that knows it is lost has no way to say
   so**, and the fallback that inherits is the one tool that never knows.
3. **Therefore the lever is not another specialist and not a routing tweak.** It is giving the
   fallback position something that can recognise its own failure, or giving the harness a
   goal-progress signal independent of "reached a new state" — the one quantity every latched run
   satisfies for 500 actions while scoring zero.

⛔ Nothing here ships. This is a measurement (rule 7o); any change built on it needs a `snapgate.sh`
gate on the full 25 showing no game regressed.

## Related

- [[r101_silent-specialists]] — the map of where the remaining loss sits
- Rule **7cj** in `OPERATING_RULES.md` — the condensed form of this round
- Rules 7ba / 7bb / 7bq — no tool alone beats the harness; 17 of 47 never hold a board; tenure
  fires nine times in 7,049 decisions. This round is the complement: what happens when the ONE tool
  that does hold a board is taken away.
- Rule 7ch — a live LLM on a GPU changes nothing on these 25. ⚠️ This round is the case 7ch says it
  cannot see: **routing is exactly what breaks when the right tool is absent**, and the model does
  not currently rescue it.
