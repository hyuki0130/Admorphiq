# R96 design — hypothesis-DSL family expansion: the MOVEMENT family

Status: DRAFT v0 (pre-Codex). Successor to R95 (`design_hypothesis_dsl_r95.md`,
round CLOSED with the contract complete on the cell-state family). R96 applies
the PROVEN R95 pipeline — family schema → grounding service → verifier →
compiler → live oracle gate → model substages — to the SECOND family, chosen
for maximum coverage.

## Family choice: movement / reach-coincidence (T1)

- Largest family in the R57 typology: 12+ of 25 public games cite T1
  (ar25, m0r0, dc22, bp35, sp80, tu93, ls20, cn04, sk48, s5i5, lp85, vc33).
- Kernel support exists: `kernels/paths.py` (BFS/A*), `kernels/motion.py`,
  `track_objects`, the graph-frontier experience, and the GoalLedger arrival
  detector.
- Per the R95 Codex correction, `reach_mode` is its own closed question:
  `click_locus | move_actor | move_non_actor | unknown`. R96 v0 scopes to
  **move_actor** (walk the avatar to a goal) — the simplest, most common
  sub-form.

## Oracle games (decoded ground truth, per the oracle-first doctrine)

- **m0r0** — FULLY CONQUERED (1.0, offline reconstruction + joint BFS): the
  primary oracle game; mechanics fully decoded.
- **dc22** — conquered at idx0 (efficient discovery ≤27 actions); the second
  variant game (movement + obstacle elimination flavour).
- OOD control (labelled, not gating): tu93 (corridor-follow motion — known
  NOT expressible as straight grid steps; expected honest UNKNOWN/DIVERGED).

## Schema sketch (MovementHypothesis envelope)

- `objective`: tagged union
  `ReachGoal { goal_selector (harness-shortlisted role), arrival_predicate }`
  | (future variants: ReachAllGoals, ReachThenReturn).
- `transition_model`: tagged
  `GridStep { dir_map (harness_measured from probe moves), passability
  (learned: blocked-cell set, harness_measured) }`
  | `StepUntilBlocked` | `EmpiricalMoveMatrix` (the discriminative
  multi-effect claim, verifier-checkable via move footprints).
- `phases`: same typed guard vocabulary (level_advanced terminal; future:
  key/door phases).
- Ownership per R95: model selects SEMANTICS (which shortlisted region is the
  goal, arrival predicate kind, guards); harness measures dir_map,
  passability, player identity, move footprints; compiler derives the path.

## Pipeline reuse vs new work

| component | reuse from R95 | new for R96 |
|---|---|---|
| contract | template (levels, fresh-reset, 2/3, leakage) | m0r0 idx0+idx1 + dc22 idx0 targets |
| schema | envelope/ownership/guard machinery | movement union above |
| grounding | service frame, epoch/rebind, UNKNOWN discipline | PLAYER tracking (mobility identity), dir_map + passability acquisition from probe moves |
| verifier | verdict machinery, episode splits, mutant-table gate | movement mutant set (wrong goal selector, wrong arrival predicate, move-matrix negative) |
| compiler | plan stepper contract, typed failure surfaces | GridStepPlan = paths.py BFS over learned passability, per-move confirmation |
| live driver | warm-up/discovery/gate flow, echo instrumentation | directional probe discovery (ACTION1-4 sweep), PROSE evidence lines from day one (the R95 lesson) |
| model stage | select + fill substages, both models rule | movement candidate instances + slots |

## Evidence lines (prose from day one — lesson prompt_notation_misparse)

- "Pressing <dir> moved the small region by <dx,dy> in <k> of <n> probes"
- "<M> directional presses produced no change (blocked)"
- "A distinct region of colour <c> did not move under any press" (goal
  candidate context, harness-shortlisted)

## Pre-declared risks

1. Player identity on multi-mobile-region games — grounding's mobility
   ranking must pick the controlled region; UNKNOWN if ambiguous (probe:
   does it move under EVERY direction?).
2. Passability learning is per-game online (like R95's cycle acquisition);
   budget-capped, GROUNDING_INCOMPLETE when the goal is unreachable in the
   learned graph.
3. dc22's elimination flavour may need a second objective variant — if so,
   scope v0 to m0r0 only and record dc22 as the first expansion candidate
   (no scope creep against the contract once frozen).
