---
type: lesson
symptom: "Generic-named strategies (G1-G4) shipped in round 5 were not real inference — pure brute-force search dressed up"
severity: blocker
first_seen: 2026-04-22
---

# G1-G4 direct-test arc (2026-04-22)

> Round-5 shipped four generic strategies — `interactive_grid_toggle`,
> `sprite_cluster_interaction`, `push_bfs_grid`, `bfs_framehash` —
> intended to replace brittle game-internal-access solvers. Round-5
> bench revealed Qwen never picked them, masking the real problem.
> Round-6 direct-test (bypassing the LLM router) revealed the real
> problem: the implementations themselves don't work.

## The measurement

`scripts/probe_generics_direct.py` ran each Gx on its target envs
with 50 000-action budget, bypassing WikiAgent entirely.

| Strategy | Cleared | Brittle baseline | Ratio |
|---|---|---|---|
| `interactive_grid_toggle` | 0 | 19 (FT09=6, CD82=6, TN36=7) | 0/19 |
| `sprite_cluster_interaction` | 0 | 17 (SB26=8, SU15=9) | 0/17 |
| `push_bfs_grid` | 0 | 6 (KA59=4, WA30=2) | 0/6 |
| `bfs_framehash` | 1 | 33 (sum of above five envs) | 1/33 |

**G1-G4 cleared 1 level total across 12 target env runs.**

## What each Gx actually did

- **G1 (interactive_grid_toggle) on FT09/CD82/TN36**: ran its
  probe-classify-search but singleton/pair/triple click sequences
  never triggered level-clear. The click-effect classifier ran but
  the search was brute-force over wrong hypotheses.
- **G2 (sprite_cluster_interaction) on SB26/SU15**: clicked
  same-color-pair midpoints. SU15's vacuum radius is ~8 px and far
  pair midpoints fell outside it; SB26's merge is sort-order
  dependent and midpoint-clicks never trigger the correct swap.
- **G3 (push_bfs_grid) on WA30**: bailed at 1.8 s with 0 BFS
  iterations. `_g3_detect_player` returned None because WA30 has
  multiple moving entities and the probe couldn't isolate a single
  displaced cluster.
- **G4 (bfs_framehash) on FT09**: consumed 152 of 50000 actions,
  then exited. FT09 is `avail=[6]` only, so dir_actions was empty
  and click-target discovery found few responsive cells; BFS over
  the resulting sparse action space could not reach a progress
  state within depth 30.

## The meta-error

Round 5 declared G1-G4 "generic" in two different senses conflated:

1. **No hardcoding** — no sprite tags, no game ids, no attribute
   reads. ✓ This is real.
2. **Combining signals to infer game rules** — probing + frame
   analysis + search. ✗ This is aspirational. What was actually
   implemented was dumb BFS / brute-force enumeration gated on a
   thin probe step.

The first sense is a necessary condition for Kaggle-private-test
survival. The second sense is what actually solves games. Round-5
unit tests validated only the first sense (mock envs that respond
deterministically) — they never caught the implementations' inability
to handle real game semantics (vacuum radius, sort-order coupling,
multi-entity probe ambiguity, sparse click spaces).

## What it taught

Mock envs are inadequate for strategy validation. Any new strategy
must be direct-tested on at least one real target env before it is
registered in `default_strategy_registry()`. The round-6
`scripts/probe_generics_direct.py` script is now the reference harness
for this requirement.

The real fix is the five-phase InferentialAgent design (see
[[../strategies/frame_only/inferential_agent]]) which probes for
game semantics before planning, instead of planning first and hoping
the probe matches.

## Follow-ups

- `.wiki/wiki/strategies/frame_only/inferential_agent.md` — design doc
  for the replacement strategy.
- `scripts/probe_inferential_direct.py` — direct-test harness (round
  6 deliverable).
- `strat_inferential_agent` in `agent_ensemble.py` — implementation
  (round 6 deliverable).
- Retire G1-G4 from the whitelist once I-Agent passes direct-test.

## Falsification

This lesson becomes obsolete if a future round ships strategies that
pass `probe_generics_direct.py` at ≥ 50% of brittle baseline without
reading internals. As of 2026-04-22 no such strategy exists.

## Related

- [[../strategies/frame_only/inferential_agent]] — the redesigned replacement
- [[../architecture]] § Wiki-First Routing — why G1-G4 couldn't be
  rescued by routing tweaks alone
- [[schema_enforcement_round1_20260421]] — round-1 pattern of
  measuring implementation gaps

## Sources

- `scripts/probe_generics_direct.py` — direct-test harness
- `scripts/g1_g4_direct_results.json` — raw results (2026-04-22)
- `scripts/wiki_agent_results_round5.json` — the round-5 bench that
  masked this with routing non-selection
- `.omc/rounds/round_006/` — round metadata
