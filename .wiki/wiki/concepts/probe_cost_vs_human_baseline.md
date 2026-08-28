---
type: concept
topic: efficiency
date: 2026-08-28
keywords: [probe-cost, human-baseline, action-budget, rhae, cyclepress, lp85, r101]
---

# A tool gated on the game's action allowance is not gated on the metric

> lp85 level 4: the tool spends **47 of 59 actions probing** and **10 pressing**, against a human's
> **16**. The plan already beats the human; the model-building is the entire loss. And the gate
> that limits probing watches the GAME's allowance, which on that level is many times the human
> count — so it permits a plan that scores 0.07 while never risking the level.

## The measurement

`cyclepress` on lp85, every action attributed to the branch that produced it:

```
lvl  probe  plan  replan  nudge  total   human   score
  1      2     4       1      0      7      17   1.0
  2     25     7       1      1     34      38   1.0
  3     16    14       1      1     32      31   0.938
  4     47    10       1      1     59      16   0.0735   <-- 80% probe
  5     16     8       1      1     26      41   1.0
  6     30     8       1      1     40      60   1.0
  7     19     5       1      1     26      26   1.0
  8     27     4       2      1     34     159   1.0
```

**182 of 258 actions across the game are probes.** Six levels score 1.0 anyway — not because
probing is cheap but because their human baselines are generous enough to absorb it. Level 4 has
the tightest baseline in the game (16) and is the one level that shows the cost. Level 3, at 31, is
already down to 0.938.

⚠️ So a game can sit at 0.89 with a *systemic* inefficiency and look like it has one bad level.
**The per-level table is the diagnosis; the game score hides it.**

## The structural mismatch

`_next_probe` gates its confirmation re-presses on `self._budget.remaining(...)` — an estimate of
the **game's own per-level action allowance** (thirteen games in this set declare one and END on
overrun). That gate is correct for *not losing the level* and irrelevant to the metric, which is
`(human/agent)²`. Where the allowance is 10× the human count, a tool can be fully within budget and
score near zero.

⛔ **Being safe against the game's budget is not being efficient against the human's.** Every tool
in this set inherits the same gate shape, so this is not a `cyclepress` defect.

## Two measured negatives — do not repeat them

Both obvious ways to spend fewer probes cost more than they save:

| change | lp85 | what happened |
|---|---|---|
| baseline | **0.8919** | 8/8, 258 actions |
| plan-first (probe only when planning fails) | **0.2894** | L4 59→29 and L3/L5 improved, but L2 34→**120** and the run stops at 5/8 |
| `_CONFIRM_STREAK` 2 → 1 | **0.7692** | L2/L3/L7/L8 improved, L4 59→**131**, L6 40→**115** |

**The probe sweep and its confirmation re-presses are both load-bearing.** A permutation that
replays every press seen so far always exists; the wrong one only stops replaying when one more
press is taken. Removing that check produces a confident wrong model, and the replans cost far
more than the confirmations did. Same shape as the retry loop in
[[guard_about_the_model]] that measured inert at its own site and was buying a direction.

## What the lever actually is

Not "probe less". **Probe against a human-scale target rather than the game's allowance.** The
runtime does not know the human count, but the plan length is a usable proxy: when a 10-press plan
exists, 31 confirmation presses are disproportionate to it. A gate of that shape would leave levels
2, 5, 6, 8 untouched (their baselines absorb the cost anyway) and bite exactly where the metric
does.

## Falsification

Attribute every action to its branch on a game scoring below 1.0 with all levels cleared. If probe
and plan are already balanced, this concept does not apply there — the loss is in the plan.

## Related

- [[action_budget]] — the game's own per-level allowance, the thing the gate does watch.
- [[guard_about_the_model]] — removing a check that measured inert lost a real capability.
- [[../rounds/r101_tool-development]] — the round.
