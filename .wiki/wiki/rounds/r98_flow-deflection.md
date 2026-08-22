---
type: reasoning
round: R98
axis: agent25 — hypothesis-DSL family expansion #3 (two-phase place-then-propagate flow)
keywords: [agent25, hypothesis-dsl, family-expansion, flow-deflection, place-then-propagate, sp80, response-table, reference-propagator, gated-enum, inert-slot, equivalence-class, near-ood, oracle-certification, two-model]
verdict: IN PROGRESS — contract FROZEN 2026-08-22 after the Codex schema consult (CONDITIONAL GO, six corrections bound and discharged BY MEASUREMENT); oracle certified LIVE (sp80 idx0 clears in 4 actions); reference propagator reproduces the engine cell-exactly; schema_flow.py landed with all 9 mutants certified. Grounding / verifier / compiler / oracle gate / model stage still to run
commit: [f6f9dd8, 748bc04, ad759da, 216a9a9, e9fced6]
date: 2026-08-22
---

# R98 — FlowDeflectionDynamics (family expansion #3)

> The third hypothesis family after R95 (cell-state) and R96 (movement). Its
> central claim: for a two-phase place-then-propagate board the transition model
> **is** the simulator, so a wrong response table yields a plan the live spill
> falsifies. That claim is now MEASURED, not argued.

## Why sp80 and not a push family

The v0 draft picked PushDynamics and was PIVOTED by the Codex design review: the
15-game backlog has **no clean classic-sokoban row**. ka59 is a selected-mover
momentum launch, ls20 a static contact launcher, sk48 changes body topology — so
a ka59 clear under a one-cell-contact-push schema would have certified the WRONG
transition model. sp80 was the readiness-ranked alternative with a super-human
live idx0 oracle. Design: `docs/design_r98_family_expansion.md`.

## Decoded mechanics (dev-time), then CERTIFIED live

CHANGE phase: click a movable piece to select it, translate it one cell per
directional press, commit once. SPILL phase: droplets fall from fixed emitters
and, looking one cell ahead, either advance, wait behind their own front, SPLIT
perpendicular around a piece (keeping the original direction), satisfy a sink
**only from its mouth notch** (both flanking cells belonging to that same sink)
and spread around it otherwise, die fatally on the hazard row, or die harmlessly
at the boundary. Settle verdict: all sinks satisfied AND no hazard contact.

A failed commit resets FLOW and SATISFACTION and SELECTION — but **not the
LAYOUT**. That asymmetry is why budgets must be frozen against the persisted
post-probe board.

`scripts/rounds/R98/oracle_probe_idx0.py` certified three claims live:

1. the hand-authored oracle clears idx0 in **4 actions** (human baseline 39);
2. the commit observation carries **20 frame layers** — one sacrificial commit
   exposes the entire trajectory, which is what makes this family affordable;
3. the piece response is a direction-preserving perpendicular split, measured as
   a cell-exact frontier
   `(1,9)→(2,9)→(3,9)→(3,8)+(3,10)→(3,7)+(3,11)→(3,6)+(4,11)→(3,5)+(5,11)` —
   the stream walks outward one cell per tick along the piece and resumes falling
   at each outer edge, landing exactly on the two sink mouths.

## What the Codex schema consult changed (CONDITIONAL GO)

Six binding corrections; the two sharpest caught real errors in the v1.1 draft:

- the any-vs-all justification ("the failure flash names the unsatisfied sinks")
  was WRONG — the pristine spill covers zero sinks, so `any` predicts failure too;
- the claim that deeper angled levels were "already expressible" was FALSE for a
  board mixing straight and angled pieces under one global response, so the
  response table is now keyed by piece CLASS and the claim is withdrawn.

Also bound: type the step allowance and every reset a failed commit performs;
decompose the piece response into (spawn, direction, propagation) so edge-teleport
and outward-turn models stop fitting by accident; move causal rules out of
`harness_measured`; state every verifier-enforced rule in model-facing prose; and
prove each gated enum changes a prediction.

## Open questions CLOSED BY MEASUREMENT

An exhaustive sweep of every reachable placement
(`scripts/rounds/R98/evidence_probe_idx0.py`):

- **hazard-fatal CERTIFIED** — placement `+2` fills EVERY sink and still fails;
  `+3` fills the same sinks and advances; the pair differs only in reaching the
  row above the bottom. This overturned the draft's pre-declared UNKNOWN.
- **all-vs-any UNKNOWN, with a PROOF OF ABSENCE** — no reachable placement fills a
  strict subset of the sinks, so no probe can rescue that mutant here.
- **contact-vs-mouth CERTIFIED** — the flow sat directly above a sink cell without
  satisfying it and spread sideways; satisfaction followed only from the mouth.
- **row-independence measured** — identical outcomes at three rows, so emergent
  columns are a function of the piece's columns alone.

Two detector traps worth remembering: water never OCCUPIES the hazard row (a
droplet dies on contact), so "reached the bottom row" is always false; and the HUD
paints the failure-flash colour every frame, so a colour-based flash detector
fires on every run. Both produced a wrong attribution before they were caught.

## The reference propagator, and what it proved

`scripts/rounds/R98/reference_propagator.py` implements the response table AS the
simulator. `gated_enum_test.py` ran it against the live engine:

- **FAITHFULNESS PASS** — reproduces the engine's outcome on all 12 reachable
  placements AND the cell-exact trajectory on both probe placements (20 and 17
  steps, zero divergence). This propagator is the verifier's core.
- **`own_flow` and `boundary` are INERT** — no alternative changes anything
  anywhere, so both are demoted to non-gating UNKNOWN. Independent confirmation of
  the review's prediction from absence of evidence.
- **`piece_propagation` is TRAJECTORY-ONLY** (5 trajectories, 0 outcomes) → gated
  at the verifier, never at the compiler; scoring it through outcomes is noise.
- **`piece_spawn: both_flanks` is data-indistinguishable** from the oracle at idx0
  (flanks are always empty when a split occurs), so it scores CORRECT as an
  equivalence-class member — the R95a ft09 precedent.

## Controls: the assignment SWAPPED, by measurement

The family's observable tell is one action triggering a scripted consequence
exposed as many frame layers. Measured bursts: sp80 22, **tu93 8**, sk48 2, and
re86 / ls20 / wa30 / tn36 / cn04 all 1.

- re86 is REJECTED as near-OOD — nothing about it is confusable; it is unrelated.
- **tu93 becomes the NEAR-OOD control** (an 8-layer scripted consequence, but
  actor corridor-motion with no source, no placement phase, no coverage
  objective), and re86 becomes far-OOD. The prior assignment had them backwards.

## Frozen contract (2026-08-22)

sp80 **idx0 only** (criterion-level-only — R96's idx0+idx1 was a coincidence, not
a rule); ONE cumulative cap of **20 actions** and 3 commits against a **9-action
certified path**; oracle gate 3/3; model substages ≥2/3 per model, CONFIRMED =
both models; near-OOD tu93, far-OOD re86; prose-only evidence; every
verifier-enforced rule must appear in the model-facing contract. Falsification: an
oracle-gate failure on GROUNDING pivots the round to grounding work.

## Landed

`src/admorphiq/hypothesis_select/schema_flow.py` — the family schema on the shared
envelope, with typed budget and failure semantics, placement premises that name
which constraints the discovery trace actually establishes, the three gating tiers
as measured, and the equivalence class. All **9 frozen mutants certified** against
the propagator (`mutant_certification.py`): the 6 CONTRADICTED diverge somewhere,
and the 3 UNKNOWNs diverge nowhere — the check that stops the table from
overstating the verifier's power. 9 new tests; suite 1677 passed, 1 skipped.

## Next

Grounding (piece identity by SELECTED appearance — never connected components of
the idle colour, the R92 merge bug), the trajectory verifier, the compiler's
placement search, the live oracle gate 3/3, then the paired model substages.

## Related

- [[r95_hypothesis-dsl]] — the family pipeline and the equivalence-class precedent.
- [[r96_controlled-grid-dynamics]] — family #2; the oracle-first and asymmetric-
  mobility doctrines this round inherits.
- [[r97_self-extension]] — tier-2; the "state every enforced constraint in the
  model-facing contract" lesson, applied preemptively here.
- [[r92_sp80-l2-premise-correction]] — the sp80 decode and the perception traps.
- [[../lessons/faithful_offline_simulator_20260715]] — learn an operator, then plan.
