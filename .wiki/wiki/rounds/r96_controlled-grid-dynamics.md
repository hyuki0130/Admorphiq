---
type: reasoning
round: R96
axis: agent25 — hypothesis-DSL family expansion (ControlledGridDynamics / CoupledActorMerge)
keywords: [agent25, hypothesis-dsl, family-expansion, movement, coupled-actors, m0r0, actor-relation, coupled-grid-step, typed-occupancy, mirror-deltas, merge-tracking, prereg]
verdict: IN PROGRESS — design v1 (Codex NO-GO→CONDITIONAL GO: the v0 draft conflated the win-predicate family with the transition family; narrowed to CoupledActorMerge, contract = m0r0 idx0+idx1 only, dc22 demoted to near-OOD control as a SECOND transition family); contract FROZEN (727b34b); step ii schema BUILT (b191834: ActorRelation + CoupledGridStep with decoded mirror deltas, typed occupancy, verify-only move matrix, 6 frozen mutants 4-CONTRADICTED/2-UNKNOWN); step iii two-actor grounding (the ~55%-risk component) in build
commit: [141fc8c, 727b34b, b191834]
date: 2026-07-23
---

# R96 — family expansion: ControlledGridDynamics (coupled actors, m0r0)

> The proven R95 pipeline (family schema → grounding → verifier → compiler →
> live oracle gate → model substages) applied to its second family: coupled
> two-actor grid movement ending in an exact-cell merge, oracle-first on the
> fully conquered m0r0.

## Design (binding: `docs/design_r96_family_expansion.md` v1)

Codex reshaped the v0 draft decisively: movement is the right second
investment (grid grounding/occupancy/path search are prerequisites for
future push/delivery families), but "move_actor over 12+ T1 games" conflated
R57's goal-detector count with transition-model expressibility — m0r0 is
COUPLED two-actor motion (antisymmetric column keys / symmetric row keys,
independent-stay collisions, hazard soft-resets, exact same-cell merge) and
dc22 is a different transition family entirely (click-mutated passability
product graph). v0 scope = CoupledActorMerge; risk re-estimate after
narrowing: ~55% grounding/state reconstruction (two-actor tracking through
crossing/adjacency/merge + full occupancy parsing), then verifier 20% /
model selection 15% / compiler-live 10%.

## Build log

- **(i) contract FROZEN** (727b34b): m0r0 idx0+idx1; split budget caps
  (discovery ≤30, solve ≤150/level, hazard resets count); 2/3 rule; dc22
  near-OOD + tu93 far-OOD controls; prose-only evidence (the
  [[../lessons/prompt_notation_misparse_20260723]] lesson applied from day
  one); grounding-failure falsification clause.
- **(ii) schema BUILT** (b191834): `schema_movement.py` sibling
  single-sourcing the shared envelope/guard machinery; ActorRelation
  (same_cell | adjacent | overlap), CoupledGridStep (per-actor deltas,
  independent_stay, TYPED occupancy union with confidence/context/epoch,
  hazard_soft_reset), verify-only EmpiricalMoveMatrix; m0r0 oracle instance
  carries the decoded mirror-delta scheme; 6 frozen mutants with an honest
  4-CONTRADICTED / 2-UNKNOWN expected-verdict table.
- (iii) two-actor grounding: in build (tracking through crossing/adjacency/
  MERGE as an event, per-actor delta acquisition with collision isolation,
  full-frame static occupancy parse, 4-way no-op attribution, hazard
  soft-reset evidence). (iv)–(viii) mirror R95.

## Related

- [[r95_hypothesis-dsl]] — the closed round whose pipeline this reuses.
- [[r57_win-condition-typology]] — the T1 goal-detector count this round is
  careful NOT to read as transition coverage.
- [[../lessons/prompt_notation_misparse_20260723]] — prose evidence doctrine.
- [[index]]
