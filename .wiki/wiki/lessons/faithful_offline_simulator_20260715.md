---
type: lesson
topic: faithful-offline-simulator
date: 2026-07-15
keywords: [faithful-simulator, state-model, offline-search, sparse-win-signal, dfs, a-star, portal, slide, ring, gated-path]
---

# When the live win-signal is sparse, reconstruct the state machine offline and search it

> Six R56 clears this sprint share one shape: rebuild the game's exact state
> machine offline, then run DFS/A*/BFS over it — instead of learning from the
> sparse live reward. The trigger is a win-signal too rare to learn from.

## Symptom

Blind live exploration (round-robin sweep, frontier BFS, novelty-reward RL)
clears single-goal reachability but stalls on any game that needs a CHAINED,
multi-subgoal plan: place N items into N slots, roll a token through a bending
corridor, rotate coupled rings until every marker lands. The live WIN signal
fires once, at the very end, so there is almost no gradient to learn the plan
from within a per-game action budget — the agent wastes hundreds of actions and
still does not connect the last subgoal.

## Root Cause

Sparse terminal reward + a large combinatorial plan space = nothing to hill-climb
on. But these games ARE deterministic and their mechanics are decodable from the
frame (and, dev-time, from the gold trace / source). So the missing ingredient is
not more live probing — it is a MODEL to search offline, where a full plan can be
evaluated for free before spending a single live action.

## Prevention

Build a **faithful offline simulator** of the game's exact state machine, then run
a classical search (DFS / A* / BFS) over it to produce the whole action sequence,
and replay that sequence live. "Faithful" is load-bearing: the simulator must
reproduce the real transitions (validate it against the gold trace / a live probe
before trusting it — see the divergence discipline in
[[false_claim_verification_20260715]]), or the plan it finds will diverge live.

Six evening clears instantiate the pattern (all numbers SUMMARY-verified in
[[../rounds/r56_generic-kernels]]):

- **sb26 8/8 @ 0.846** — `_simulate_portal_dfs` replays the exact portal traversal;
  DFS over portal→slot assignments finds the placement order.
- **sk48 3/8 @ 0.1667** — a faithful move-semantics simulator + A* over board
  states; the clears are super-human because the search is optimal.
- **lp85 3/8 @ 0.1637** — `kernels/permute.py` learns each ring's permutation, then
  BFS over goal-token positions composes the rotation sequence.
- **dc22 1/6 @ 0.0272** — `plan_gated_path` searches a product graph of
  (position × passability), the maze's true coupled state.
- **su15 3/9 @ 0.1035** — the vacuum-pull merge cascade is simulated to schedule
  merge-and-deliver order.
- **m0r0 1/6** (afternoon) — `configuration_path` searches the joint configuration
  state rather than the avatar position alone.

## Recovery

If a faithful simulator still does not clear a level, the bank is HONEST and
diagnostic: it localizes the wall to either (a) a mechanic the simulator does not
yet model (fix the model), or (b) a genuine new structure the search cannot reach
in budget (bank it). sk48's L3+ (`sys_click` controls are not ACTION6-selectable)
and lp85's L4 (20-ring self-test rejects single-press reconstruction) are
model-boundary banks of exactly this kind — the search is correct, the model or
the control surface is the limit.

## Falsification

The pattern fails where the state is NOT frame/-source-reconstructible: tu93's
slide is corridor-BENDING and a predictive model caps at 16% held-out, so no
faithful simulator exists — tu93 stays on a LEARNED transition graph (efficiency
lever only, [[../games/TU93]]), not an a-priori simulator. bp35's hidden velocity aliases
the frame-key graph similarly. So the rule is conditional: build the simulator
only when the mechanic is decodable; otherwise learn the model online.

## Related

- [[../rounds/r56_generic-kernels]] — the sprint; the evening table lists every
  clear and its mechanism.
- [[../games/SB26]], [[../games/SK48]] — the two games whose pages first recorded this pattern.
- [[../games/TU93]] — the counter-example: no faithful simulator exists, learn online.
- [[false_claim_verification_20260715]] — the validate-the-artifact sibling rule.
