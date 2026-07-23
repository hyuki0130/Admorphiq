# R98 design — hypothesis-DSL family expansion #3: PushDynamics

Status: v0 draft (2026-07-23, pre-Codex). Successor to R96
(`design_r96_family_expansion.md`, ROUND COMPLETE — ControlledGridDynamics
measured end-to-end) and R97 (`design_r97_self_extension.md`, CONFIRMED
SEED-PASS both models). Applies the proven pipeline — family schema →
grounding → verifier → compiler → live oracle gate → model select+fill —
to its THIRD family, chosen from the 15-game inexpressible backlog.

## Family choice: PushDynamics (actor pushes movable blocks)

From the backlog, the push/delivery cluster is the R96-anticipated next
investment ("grid grounding/occupancy/path search are prerequisites for
future push/delivery families" — the prerequisites now EXIST and are
measured: two-actor grounding, typed occupancy with confidence/context/
epoch, joint BFS, online wall/hazard learning, observation-trumps-inference
invalidation, the transient-evidence model).

Core transition claim: the actor moves per directional keys; a MOVABLE
block in the actor's path moves one cell in the push direction iff its
destination cell is free (else both stay); walls block both; objective =
block(s) on goal cell(s) (sokoban-class) or actor-reaches-X-with-block-
state (variant).

## Oracle candidates (Codex to rank — oracle-first doctrine)

1. **ka59 idx0** (sokoban proper): L1 CLEARED, push mechanics DECODED
   (generic push-planner kernel, task #49; multi-round settled). Criterion
   level = idx0, exactly the R96 m0r0-idx0 pattern. Risk: only 1/7
   conquered — deeper levels lack gold; the criterion stays idx0-only.
2. **ls20** (fully conquered 7/7 @1.0, offline reconstruction incl. the L5
   sprite-pixel push-carry model + L1-L4 pushwall fixtures): richest gold,
   but the mechanic is COMPOSITE (push + refill + fog + entry-conditioned
   mutation) — risks conflating the push family with game-specific
   composition, the exact v0 mistake Codex corrected in R96.
3. **sk48 side-push grow/retract** (backlog entry): a DIFFERENT push
   variant (body extension, not block displacement) — likely a separate
   family; flagged so Codex can confirm exclusion.

## Schema sketch (PushHypothesis envelope — reuses the shared machinery)

- `objective`: tagged `BlocksOnGoals { goal_binding: harness-shortlisted
  goal cells; completion: all | count(n) }` | (variant: ActorAtWithBlocks).
- `transition_model`: `PushStep { actor_deltas (harness_measured),
  block_response: displaced_iff_destination_free (the discriminative
  claim), chain_push: none | single | multi (closed enum — whether a block
  can push another block), occupancy: typed as R96 }`.
- Mutants (frozen table with expected verdicts, R96-style): block-never-
  moves (pure wall) · block-moves-with-actor (carry, not push) ·
  chain-push-when-none · pull-instead-of-push · goal-is-actor-cell ·
  blocks-vanish-on-push.
- Field ownership per doctrine: model selects objective kind + completion
  + chain_push claim; harness measures deltas, occupancy, block identity/
  tracking; compiler derives the plan (push-planner kernel exists —
  kernels/ push search from task #49; the joint (actor, blocks) state
  space is the known sokoban cost, budget-capped).

## Pre-declared risks (Codex to re-estimate)

1. **Block-state grounding** (the R96-lesson analogue, likely dominant):
   tracking N movable blocks through pushes/occlusion; block-vs-wall
   classification from probe evidence (a block MOVES when pushed — the
   behavioural discriminator; static walls never do).
2. State-space cost: (actor × blocks) joint planning explodes with block
   count — budget-capped search + the R56 push-planner kernel as the
   engine, not a fresh BFS.
3. ka59's deeper levels are unconquered — the contract floor must be
   idx0(+idx1 attempt per the R96 "in sequence" precedent), NOT deep
   levels.
4. Evidence prose for pushes must be exact per-entity tuples (the twice-
   measured lesson: state every constraint and quantity in prose).

## Contract skeleton (to freeze post-Codex)

- Oracle game + criterion level per Codex ranking; fresh-reset; discovery
  ≤30, solve ≤150/level; 3 runs, ≥2/3; both models; select + fill
  substages; leakage prohibitions as R95/R96/R97; controls = near-OOD
  (a non-push movement game, e.g. m0r0) + far-OOD (tu93).
- Falsification clause: oracle-gate failure on block-state grounding =
  the pre-declared pivot to grounding work (the R96 pattern).
