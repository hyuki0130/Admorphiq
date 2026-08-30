---
type: round
round: R101LP85CAP
axis: generic-tools
keywords: [lp85, cyclepress, level 4, efficiency, discovery cost, permutation recovery, confirmation press, inverse control, ring, RHAE cap, load-bearing]
verdict: CLOSED — lp85 level 4's two saveable presses are spent before the evidence that they are unnecessary exists; fifteen arms and two structural axes refuted
commit: pending
---

# R101LP85CAP — lp85 level 4, the last efficiency item in the corpus

> Level 4 costs **18 actions against a human 16**. The whole of it is model identification: with
> the converged model in hand at the OPENING board the level costs **EIGHT** actions, half the
> human baseline, and the ten probe presses leave the plan exactly as long as it was before them.
> The two presses that would have to be saved are spent at proposes 3 and 4; the evidence that
> they are unnecessary — a plan — does not exist until propose 12.

Banked: `scripts/rounds/R101SHIPPED/games/lp85.json`, `per_level [7,34,18,18,16,39,18,32]`,
total 182, game score **0.97668**, level 4 `(16/18)^2 = 0.790123`. Every probe here reproduces
those counts to the action before interpreting anything (rule **7aj**).

⚠️ The briefing for this round said 19 actions. The shipped number has been **18** since
`808cef67`; 19 was the count before the settled-layer read landed. A stale action count is the
cheapest kind of wrong premise and it survived into a task description.

## The eighteen, one by one

Instruments: `scripts/_lp85_l4_census.py` (already existed) and `scripts/_lp85_l4_converge.py`
(new), both mirroring `score_efficiency.py:run_game`.

```
 k  action         what it serves
 1  press (6,15)   fresh — first control, look class 1
 2  press (16,6)   fresh — look class 2
 3  press (16,25)  fresh — look class 3
 4  press (25,16)  fresh — look class 4   <- the budget indicator becomes readable here
 5  press (6,15)   re-press: no plan exists under the model on hand
 6  press (6,15)   re-press
 7  press (6,15)   re-press   <- (6,15)'s permutation first equals its converged value
 8  press (6,15)   re-press
 9  press (16,6)   re-press
10  press (16,6)   re-press   <- a plan first exists once this press is learned
11-18  the plan    eight presses, (6,15) x2 and (16,6) x6, one replan, no wasted step
```

## ⭐ The finding: the level is never a planning problem

`total_if_final_model_here` = `(k-1) + len(plan(board_k, final model))`:

```
k= 1 ->  8      k= 5 -> 12      k= 8 -> 15      k= 9 -> 15      k=10 -> 17      k=11 -> 18 (actual)
```

The plan is **eight presses from the opening board and still eight at propose 11**, so the ten
probes are positionally NET-NEUTRAL. Level 4 is an eight-press solution plus ten actions of model
identification, and a perfect model at action 1 would clear it in half the human's budget.

⛔ **The cap therefore needs the model plannable by propose 9 — after EIGHT presses.** Saving ONE
press lands on 17 (`(16/17)^2 = 0.8858`); only saving TWO reaches the cap. This is why the round
is not "find an action to shave": it is a two-action problem or nothing.

## ⛔ The confirmations are not discretionary, and this is a stronger proof than the arms

`_next_probe` returns `None` the moment a plan exists. Measured: `plan_presses` under the tool's
own model returns `None` at **every** propose until press 10 is learned. So every re-press happens
BECAUSE there is no plan — they are not slack that a rule declined to cut. The seven arms refuted
in `808cef67` showed that cutting them loses; this shows they cannot be cut at all under the rule.

## ⛔ Two structural axes, each closed by direct measurement

**1. Inverse adoption is UNSOUND at one press** (`scripts/_lp85_inverse.py`). The controls are
rings x directions, so each permutation is its opposed twin's exact inverse — the one constraint
the tool does not yet mine for RECOVERY (`_confirm_inverse` uses it only when two independent
recoveries come out exactly inverse; `_twin` adopts only from an already-CONFIRMED control, which
on level 4 never happens). Over the eight levels, **11** controls had another control's recovered
permutation invert into something that replays all of their own transitions — and **9 of the 11
disagree** with the permutation the tool converges on, **all four of them on level 4**. A single
transition does not pin a permutation, and neither does its inverse. The arm is dead before it is
written.

**2. The recovery cost cannot be reweighted** (`scripts/_lp85_cost.py`). `recover_permutation`
picks the least-total-Manhattan permutation that replays the press; it gets **14 of 34** controls
exactly right from ONE press. Level 4's two USED controls are not among them, and their truth is
not cheapest under any objective tried: it costs **more** total distance (76 vs 70) and has
**fewer** long steps (4 vs 7) than the permutation the rule picks. Charging per long step
(2 / 8 / 64 / 1000) recovers no more controls and breaks ones the shipped rule gets right —
including level 1's control and level 4's own two EASY controls.

⚠️ Read the truth column carefully: for the two controls the plan never uses, "truth" is their own
single-press recovery, unvalidated. The two that matter — `(6,15)` and `(16,6)` — are validated by
the level clearing on the plan's last press, and both are wrong under every cost tried.

## Eight more arms, all refuted (`scripts/_lp85_arm2.py`)

```
arm                     per_level                     L4    game_score
control                 [7,34,18,18,16,39,18,32]      18    0.976680   <- positive control
maxpresses4             [7,34,18,18,16,39,18,32]      18    0.976680   IDENTICAL
maxpresses5             [7,34,18,18,16,39,18,32]      18    0.976680   IDENTICAL
maxpresses6             [7,34,18,18,16,39,18,32]      18    0.976680   IDENTICAL
confirm3                [7,34,18,18,16,48,18,33]      18    0.976680   L6 +9, L8 +1
longstep2               [7,18,20,20,16,39,10,34]      20    0.960000   LOSS
longstep8               [7,18,20,57,14,60,10,34]      57    0.897644   LOSS
maxpresses4+longstep8   [7,18,20,57,14,57,10,34]      57    0.897644   LOSS
```

⛔ **`_MAX_PRESSES` is a NEGATIVE CONTROL, not a lever.** 4, 5 and 6 are byte-identical because the
cap never binds — `(6,15)` leaves the confirmation queue on its streak, not on the cap. Three arms
that look like three experiments are one measurement of a constant that does nothing.

⚠️ **`longstep2` makes levels 2 and 7 CHEAPER (34 -> 18, 18 -> 10) and still LOSES**, because both
already sit at the metric's cap. Actions are not score, and an arm bench that reported total
actions would have promoted it. Same shape as [[r101_inert-actions]].

## Why the two presses cannot be saved

The plan uses only `(6,15)` and `(16,6)`. `(16,25)` and `(25,16)` are pressed at proposes **3 and
4** and never used again. Skipping them is the only route to eight discovery presses, and:

- the information that would justify skipping them — that a plan exists — is **not available until
  propose 12**;
- the one rule that would skip them regardless, a ready-check ahead of a fresh press, is measured
  in `808cef67` to cost level 1 **7 -> 21 actions** (0.9581);
- the confirm-before-breadth branch that would reorder them is gated on the budget indicator, and
  `_BudgetBar` needs two spent cells to fix its axis — four actions on this board. Opening that
  gate earlier is the ungated confirmation that took level 1 from 7 to 59 actions.

**No scheduling rule can use information it does not have.** That is the closure.

## For the record — the oracle

`scripts/_lp85_oracle.py`, reading the game's own cycle data: level 4 draws **sixteen** button
sprites over **four** distinct controls (two rings x two directions), allows 150 actions, and its
shortest engine-exact sequence is **12** presses (`button_B_L` x4 then `button_A_L` x8).

⚠️ The tool's plan measures **8** from the same opening board. The instruments differ because
`plan_presses` treats tiles of one colour as interchangeable while the oracle tracks named sprites.
The 8 is the one validated by the level clearing on the plan's last press; the 12 is an upper
bound on a stricter problem. ⛔ Do not quote either as "the minimum" without the predicate.

## What would reopen this

Only a recovery rule that pins a permutation from ONE press on a board where twenty slots move.
Nothing else in the round has slack: the plan is optimal under the model, the confirmations are
forced, the reorderings are refuted, and the constants are inert.

Related: [[r101_conquest-wave]] (the seven first-pass arms), [[r101_inert-actions]] (the +0.00796
structural bound on the whole efficiency half), [[r101_shipped-and-transfer]] (the baseline).
