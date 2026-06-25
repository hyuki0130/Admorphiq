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

Per-strategy actions / elapsed (raw from `scripts/g1_g4_direct_results.json`):

| Strategy | Env | Levels | Actions | Elapsed (s) | Failure mode |
|---|---|---|---|---|---|
| `interactive_grid_toggle` | FT09 | 0 | 178 | 0.0 | early-bail (no responsive grid) |
| `interactive_grid_toggle` | CD82 | 0 | 16 | 0.0 | early-bail (HUD-noise pre-R12) |
| `interactive_grid_toggle` | TN36 | 0 | 98 | 0.0 | early-bail (no responsive grid) |
| `sprite_cluster_interaction` | SB26 | 0 | 28 | 0.0 | early-bail (no same-color pair) |
| `sprite_cluster_interaction` | SU15 | run_error | — | — | `list index out of range` |
| `push_bfs_grid` | KA59 | 0 | 48 012 | 4.1 | budget-near-cap, no progress (sokoban-search-explosion) |
| `push_bfs_grid` | WA30 | 0 | 50 000 | 1.8 | budget-cap, 0 BFS iterations (player not isolatable) |
| `bfs_framehash` | FT09 | 0 | 152 | 0.0 | early-bail (avail=[6], stride-8 0 responsive) |
| `bfs_framehash` | CD82 | **1** | 50 001 | 3.2 | L1 cleared then budget-exhausted (HUD-noise pre-R12) |
| `bfs_framehash` | SB26 | 0 | 37 688 | 34.8 | search-ceiling (state cap) |
| `bfs_framehash` | SU15 | 0 | 50 000 | 10.0 | budget-cap, no goal |
| `bfs_framehash` | KA59 | 0 | 50 000 | 4.9 | budget-cap, dir-silent v2 |

The action/elapsed split mirrors the three modes characterised in
[[inferential_budget_vs_algo_20260423]]: KA59/WA30 push_bfs_grid hit
budget-cap fast (low elapsed → fast env steps with no useful state
expansion); SB26 bfs_framehash burned 34.8 s at 37 688 actions
(search-ceiling — BFS exploring states without progress);
FT09/CD82/TN36 G1 early-bailed in 16-178 actions (no entry
condition matched).

**Narrative interpretation**:

- **G1 (interactive_grid_toggle) on FT09/CD82/TN36**: ran its
  probe-classify-search but singleton/pair/triple click sequences
  never triggered level-clear. The click-effect classifier ran but
  the search was brute-force over wrong hypotheses.
- **G2 (sprite_cluster_interaction) on SB26/SU15**: clicked
  same-color-pair midpoints. SU15's vacuum radius is ~8 px and far
  pair midpoints fell outside it; SB26's merge is sort-order
  dependent and midpoint-clicks never trigger the correct swap.
  SU15 additionally tripped a `list index out of range` — the
  function assumed at least one same-color pair existed, foreshadowing
  the same-color pair=0 issue characterised in
  [[su15_l1_singleton_colors_20260423]].
- **G3 (push_bfs_grid) on KA59/WA30**: KA59 ran 48 012 actions in
  4.1 s — that's pure env stepping with no productive BFS expansion
  because every direction probe returns 0 pixel diff on v2 (see
  [[ka59_v2_action6_semantic_20260423]]). WA30 hit 50 000 in 1.8 s
  for the same reason via a different shape: `_g3_detect_player`
  returned None because WA30 has multiple moving entities and the
  probe couldn't isolate a single displaced cluster.
- **G4 (bfs_framehash) on FT09**: consumed 152 of 50000 actions,
  then exited. FT09 is `avail=[6]` only, so dir_actions was empty
  and click-target discovery found few responsive cells; BFS over
  the resulting sparse action space could not reach a progress
  state within depth 30. (Same root cause as
  [[ft09_stride_button_drop_20260423]]: stride-8 lands on cell
  borders.)
- **G4 on CD82** is the lone "1 level" entry. The L1 clear was
  serendipity — pre-R12 HUD noise made one of the framehash states
  match a level-up boundary. Post-R12 HUD masking would suppress
  this; the 1/47 figure is therefore an upper-bound on G4's real
  generality. See [[cd82_paint_palette_signature_20260423]] for the
  HUD-mask diagnosis that explains why pre-R12 CD82 traces were
  noise-dominated.

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
