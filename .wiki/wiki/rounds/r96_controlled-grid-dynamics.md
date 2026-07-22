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
- **(iii) two-actor grounding BUILT — the 55%-risk gate PASSES GREEN**
  (9e54634): on the real m0r0 trace the service finds both actors, acquires
  all 8 per-actor delta edges reproducing the decoded mirror structure
  (one symmetric-row pair + one antisymmetric-column pair), detects the
  MERGE as a named event, attributes no-ops 4 ways
  {collision_stay:30, blocked:24, settle:24}, parses 89 static walls at high
  confidence, and reports hazard cells honestly as 0 (gold enters none).
  Two hardening findings: action-number↔axis mapping is HASH-VARIABLE
  (structure invariant → verifier judges structure, per the
  api_hash_rotation doctrine), and replayed gold traces are per-transition
  DISCONTINUOUS (epoch churn) → actor identification made frame-based,
  robust to both replay and continuous live play. Process note: a
  delegation race created a transient duplicate implementation, caught and
  reconciled to a single clean one before commit.
- **(iv) movement verifier BUILT** (bfd6848): structure-based delta
  judgement (hash-variable action numbering never pinned), collision policy
  vs desync evidence, honest hazard-UNKNOWN at zero observations;
  **acceptance matrix matches the frozen table EXACTLY** (oracle PASS + 4
  CONTRADICTED + 2 honest UNKNOWN), no forcing.
- **(v) movement compiler BUILT** (eb4d3cf): CoupledGridStepPlan joint
  two-actor BFS (independent_stay, hazard avoidance), grounding-sourced
  executable deltas (the hash-robust design — the instance supplies only
  model_selected semantics), typed surfaces incl.
  UNSATISFIABLE-with-state-count and UNSUPPORTED(EmpiricalMoveMatrix).
  **Fixture: plan length 15 = EXACTLY the m0r0 gold count** (598 joint
  states, exact same_cell merge end state).
- **(vi) live driver BUILT + gate measured** (87aed80, b46ed61):
  **m0r0 idx0 CLEARED LIVE 3/3 at exactly 15 actions each (= gold,
  deterministic)** — discovery 9 actions acquires all 8 delta edges, joint
  BFS, stepped per-move confirmation, merge, clear. idx1: binds + compiles
  (SOLVABLE in isolation, 1181 states) but DIVERGED at execution — a
  four-defect ladder, each removed with instrumented evidence:
  1. v2 (fc9140b): settling absorption + stale idx0 grounding → per-level
     FRESH re-grounding (the per-board doctrine), moved DIVERGED →
     GROUNDING_INCOMPLETE.
  2. v3 (648124f): the all-8-edges requirement lived only in the driver →
     plan over the CONFIRMED edge subset (the missing (actor_b, up) edge is
     provably unnecessary offline).
  3. v3→v4 (0582f12): ALL 8 edges missing + rebind 21/run — my
     rebind-detector hypothesis was FALSIFIED by instrumentation; real cause
     = actor-colour misdetection of a vanishing colour-0 transient →
     PERSISTENCE gate (controllable colour must show 1-3 compact regions in
     both before AND after frames).
  4. v4 (6790b30): edges confirmed, plan compiles SOLVABLE (1181 states =
     offline), but stepped execution DIVERGED 3/3 with no step detail →
     step-level observability added (the R95 v7 lesson re-applied), and the
     instrumented run pinpointed it: **idx1's FIRST plan action produces
     zero displacement**. Fixed (01a4fa0): settle absorption — tolerate ONE
     fully no-op action at execution start (idx1's first GOLD action also
     moves nothing), consume + recompile. Validated live.
  5. Past absorption, idx1 diverged at step 5: actor_b blocked into (3,11)
     (independent_stay) — the occupancy parse MISSED that wall. Fixed
     (01a4fa0): **online occupancy learning** — unreached predicted cells
     (predicted − observed) are learned walls fed back via
     `compile_movement_hypothesis(extra_walls=…)`, bounded cap, recompile
     and route around. Live: learned 10 real walls one-by-one, routed
     step 5→15, ended at the honest UNSATISFIABLE surface.
- **(vi-b) occupancy-perception round (IN BUILD)** — the deeper root, and
  the contract's PRE-DECLARED 55% outcome (falsification clause → pivot to
  grounding work, not schema/model changes): `movement_occupancy`
  SYSTEMATICALLY under-detects idx1's edge walls (45 parsed, ≥10 missing,
  clustered rows 5-7 / cols 9-11 — likely background-coloured boundary
  cells the center-pixel parse reads as floor; idx0 parses 89 walls and is
  unaffected, 3/3 @15a throughout). NOT a CoupledGridStep expressibility
  gap — the schema plans idx1 perfectly given correct walls. Bounded
  assignment: one diagnostic (pixel evidence at the 10 learned-wall cells)
  → one generic fix (full-cell sampling / boundary-aware / reachability-
  consistent, per evidence) + idx0 89-wall regression pin → v5 re-gate.
  The learned-wall channel stays as the residual-error meter.
  **Diagnosis (pixel dump, 06:36) REFUTED the background-boundary
  hypothesis**: the missed walls are MINORITY-OBSTACLE cells (center=floor
  colour 5 but 3-10/25 obstacle pixels of colours 15/8/6) — and 3 of the 10
  "learned walls" ((6,9),(5,10),(6,10)) are pure {5:25} background, i.e.
  FALSE POSITIVES of the set-based predicted−observed learning (these
  over-constrained the plan into UNSATISFIABLE). Full-cell sampling was
  measured offline and REJECTED: idx0's floor cells carry colour-6
  anti-alias bleed in the SAME pixel range (2-5) as idx1's real obstacles
  (min 3) — no threshold separates them; any threshold catching idx1's
  obstacles marks idx0 89→94-118 walls and makes BOTH boards UNSATISFIABLE.
  The colour parse stays untouched. **Approved fix = make the ONLINE
  learning reliable** (driver, not movement_occupancy): learn a wall only
  from a CLEAN independent_stay block (exactly one actor stayed while its
  partner moved as predicted → the stayed actor's predicted target is the
  wall); both-actors-off-prediction learns nothing (ambiguous); seed
  extra_walls from discovery's blocked_by_wall attributions; bounded
  recompiles with cause logging (settle | learned-wall | ambiguous).
  **v5 gate (8fa8db6): FAIL 3/3 deterministic — but the clean-block rule
  WORKS** ((3,11) learned once, zero false positives, no spurious
  UNSATISFIABLE), and the cause log exposed defect 6, which is NOT walls:
  - **Double-block loop**: both actors blocked simultaneously (row-7
    targets) → ambiguous learns nothing → identical recompile → a
    deterministic period-10 loop to the recompile cap.
  - **Unlearned hazard soft-reset**: predicted ((9,2),(9,10)) → observed
    [(3,5),(3,8)] — a JOINT teleport home. The schema models
    hazard_soft_reset, but gold never entered a hazard on idx0 so the
    grounded hazard set is honestly empty; the plan cannot avoid what it
    does not know (and the hazard_resets counter missed these — spawn
    tolerance). Fix in build: double-block learns BOTH targets as walls;
    online HAZARD learning (joint-teleport detection → entered cells are
    hazards → extra_hazards twin of extra_walls → recompile post-reset).
  **Defect ladder continued (v6→v7, each 3/3-deterministic and
  instrumented)**:
  - Defect 6 (v6, bfeb358): double-block learning (both targets at once,
    breaking the v5 period-10 loop) + online HAZARD learning
    (joint-teleport detection → entered cells become `extra_hazards`,
    the twin of `extra_walls`; hazard_resets counted from teleports).
  - Defect 7 (v7, 2f14bc8): (6,9) proved a TRANSIENT/dynamic obstacle —
    blocked entry from (6,10)/action-4, PASSABLE from (6,8)/action-3 two
    steps later (idx1 has a patroller; same entity class as the
    persistence-gate colour-0 transient). Fixes: observation-trumps-
    inference wall invalidation (actor observed ON a learned wall →
    unlearn) + generalized total-no-op learning (planned-stay crack) +
    retry-before-learn transient tolerance (5ff9f70).
  - **v7 measured: the ENTIRE learning chain executes** (unlearn fired,
    no-op-blocks learned, hazard (8,5)/(8,7) learned + counted) and idx1
    reaches the ENDGAME — then stalls at the merge: from adjacent
    a=(2,6), b=(2,7) the plan predicts walk-onto-partner ((2,7),(2,7));
    the engine refuses. idx0's real merge was MEET-IN-THE-MIDDLE (both
    actors entering the same EMPTY cell simultaneously). **Defect 8 (in
    build) = compiler successor semantics**: merge ONLY on simultaneous
    same-empty-cell entry; walk-onto/swap engine-blocked; adjacent-gap
    parity forces a desync detour the BFS finds naturally.
  - Defect 8 (v8, 17a8898): compiler merge semantics — the engine merges
    ONLY by simultaneous same-empty-cell entry (idx0 evidence);
    walk-onto-stationary-partner and swap are engine-blocked (v7 endgame
    evidence). Successor tightened; adjacent-gap parity now forces a
    desync detour; idx0 pin 15 = gold holds (states 598→272).
  - Defect 9 (v9, f20cae6): the patroller sat on (3,7) at parse time and
    was BAKED INTO the static occupancy — the BFS routed its desync
    through the fictional wall → mirror-locked period-2 oscillation with
    no learning trigger. Observation-trumps-inference extended to
    GROUNDED walls (`unwalled` override; walls = (grounded − unwalled) ∪
    extra_walls). v9 measured: unwalling works, execution reaches step
    89; terminal pattern = **patroller CHURN at (3,9)** (learn → unlearn
    → re-learn period-6; static learning cannot converge on a toggled
    cell).
  - Defect 10 (in build): the pre-declared transient-region fallback —
    PERCEIVE-AND-AVOID: live transient-obstacle snapshot cells unioned
    into every compile (never learned/persisted), churn cells never-learn,
    bounded WAIT (K=6) when the next step is blocked by a visible
    transient. Time-expanded planning deferred unless perceive+wait
    measured-fails.
  (vii)–(viii) pending.

## Related

- [[r95_hypothesis-dsl]] — the closed round whose pipeline this reuses.
- [[r57_win-condition-typology]] — the T1 goal-detector count this round is
  careful NOT to read as transition coverage.
- [[../lessons/prompt_notation_misparse_20260723]] — prose evidence doctrine.
- [[index]]
