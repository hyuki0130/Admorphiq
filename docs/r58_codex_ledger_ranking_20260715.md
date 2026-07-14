# Codex verdict — GoalLedger ranking design (2026-07-15)

> Input: scripts/_r58_ledger_ranking_brief.md (three measurement rounds). Verdict:
> hypothesis GENERATOR not classifier — evidence tiers (predicate/behavioral/
> affordance) + footprint-dependency relations replace scalar election; strength is
> detector-local margin; REPLACE pattern_match (canvas/reference lattice detector);
> TOP1 secondary — measure supported-type recall under cap + probe resolution.

## Recommendation

Use a hybrid of **(c) and (d)**, with a narrow form of **(a)**:

- Treat GoalLedger as a **capped hypothesis generator**, not a six-class classifier.
- Replace the total scalar ranking with **evidence tiers plus explicit evidence-dependency relations**.
- Preserve overlapping hypotheses; do not introduce hard type-pair exclusions.
- Replace—not merely tighten—the current `pattern_match` proxy.
- Make `unresolved_tests` concrete enough for the harness to resolve ambiguity through later observations.

TOPK is closer to the actual contract than TOP1, but 16/21 coverage is not yet sufficient to declare the ledger finished.

## Why floor anchoring cannot solve this

Floor anchoring is mathematically correct as a normalization of each detector’s **margin above its own gate**. It is not calibration in the classifier sense.

A `0.45` from `arrival` and a `0.45` from `uniformity` do not estimate the same probability, likelihood ratio, or information gain. Their gates, evidence modalities, and formulas are different. Mapping every gate to `0.2` does not create a common semantic scale.

Consequently, [sorting all candidates by `strength`](/Users/nhn/Workspace/Admorphiq/src/admorphiq/explanation/goal_ledger.py:762) asserts more comparability than the formulas support. I would retain the value, but rename its conceptual role to `margin` or document it as detector-local—not global confidence.

## Why hard mutual exclusion is wrong

The R57 ontology itself says several pairs are compositional or nested:

- Arrival + elimination compose delivery ([R57 T4](/Users/nhn/Workspace/Admorphiq/docs/r57_win_condition_typology_20260715.md:156)).
- Pattern matching + threshold co-occur in SC25 ([R57 T5/T7](/Users/nhn/Workspace/Admorphiq/docs/r57_win_condition_typology_20260715.md:176)).
- T6 is explicitly a “fixed-cell pattern match” ([R57 T6](/Users/nhn/Workspace/Admorphiq/docs/r57_win_condition_typology_20260715.md:194)).
- SC25 contains a pattern-building phase and an arrival/exit phase.

Therefore a learned or hand-written `pattern_match` versus `uniformity` exclusion table would encode the wrong semantics. The existing arrival/containment cross-check is better understood as a **same-evidence tension**, not proof that only one type can be true ([cross-check](/Users/nhn/Workspace/Admorphiq/src/admorphiq/explanation/goal_ledger.py:732)).

The useful part of option (a) is evidence dependency:

- `shared_evidence`: two candidates interpret overlapping regions.
- `subsumed_evidence`: one candidate’s support is largely or wholly contained in another’s.
- `independent_evidence`: their supports are structurally separate.
- `temporal_composition`: one may follow or combine with the other.

Shared evidence should not count twice as independent corroboration, but neither candidate should be silently deleted.

## Concrete ranking design

Have each detector return internal metadata in addition to the compact candidate:

```python
{
    "type": "uniformity",
    "strength": 0.451,       # detector-local margin
    "_evidence_stage": "behavioral",  # affordance | behavioral | predicate
    "_footprint": {
        "regions": frozenset(...),
        "container": ...,
        "cells": frozenset(...),
    },
    "_basis": {"repeated_shape_class", "transition_alignment"},
}
```

Strip the private fields in `compact_view()` as today.

Then add an adjudication pass after all detectors fire:

1. Build pairwise footprint relations using set intersection/containment. No game constants are necessary.
2. Assign evidence stages:

   - `affordance`: a static board structure merely permits the type.
   - `behavioral`: observed transitions behave as the type predicts.
   - `predicate`: an actual candidate/reference or endpoint predicate has been identified.

3. Produce rank tiers, not a fictitious total probability:

   - Tier 1: predicate-backed.
   - Tier 2: behaviorally corroborated.
   - Tier 3: static affordances.

4. Candidates within the same tier are genuine ties. Their local `strength` may determine deterministic presentation order, but must not be interpreted as a uniquely preferred goal.
5. When capping to four, preserve:

   - the highest evidence tiers;
   - both sides of an explicit ambiguity;
   - candidates based on independent footprints;
   - then use local margin/stable detector order only as the final size-control tie-break.

A compact candidate could add only `"tier": 2`; the richer footprints remain harness-only. This stays compatible with the §4 requirement to return competing hypotheses rather than one forced answer ([contract](/Users/nhn/Workspace/Admorphiq/docs/r58_codex_explanation_layer_20260715.md:214)).

## Replace the current `pattern_match` detector

Option (b), interpreted as “add another threshold,” is the wrong fix. The current predicate:

```python
>=5 descendants
>=3 colours
exactly one qualifying bbox-container
```

does not implement R57’s actual T5 detector sketch. R57 calls for a canvas/reference relationship and accumulated editing evidence, specifically warning that the final single transition can be misleading ([R57 T5](/Users/nhn/Workspace/Admorphiq/docs/r57_win_condition_typology_20260715.md:176)). The implementation currently tests only heterogeneous bbox containment ([implementation](/Users/nhn/Workspace/Admorphiq/src/admorphiq/explanation/goal_ledger.py:427)).

It also has two structural problems:

- `region_relations` containment is bbox containment, and `_containers_map()` includes all descendants, not only immediate children ([mapping](/Users/nhn/Workspace/Admorphiq/src/admorphiq/explanation/goal_ledger.py:215)).
- The three-colour requirement is not entailed by pattern matching and directly conflicts with binary grids such as SC25’s 3×3 pattern.

A better detector would be:

1. Convert bbox containment to an **immediate containment hierarchy** by transitive reduction.
2. Find panel/canvas hypotheses based on at least one of:

   - children occupying a regular, addressable two-axis slot lattice;
   - two panels with congruent slot geometry, suitable for canvas/reference comparison.

3. Do not require three colours or exactly one container.
4. Treat a single static panel as `affordance`, not strong pattern-match evidence.
5. Promote it when a short transition window shows:

   - changes confined to canvas slots while a comparable reference remains stable;
   - cumulative localized edits;
   - optionally, a low-diff confirm transition following those edits.

Existing `group_by_axis`, `canonical_key`, `frame_diff`, and region signatures are sufficient for most of this. If the history is held by the harness and passed as a `transition_window`, `detect()` remains pure and stateless.

## Applying this to the four cases

- **FT09:** preserve `uniformity` and `pattern_match` as two readings of overlapping panel evidence. The first transition already offers the decisive kind of evidence: a changed footprint closely aligned with one repeated 36-cell region. That should behaviorally promote `uniformity`; the generic container reading stays an affordance. No hard exclusion is needed.

- **DC22:** the pattern and uniformity readings are dependent panel evidence, while arrival is a separate hypothesis. Mark the dependency and emit a probe distinguishing mover/target behavior from panel editing. Discounting pattern merely because uniformity exists would be less principled than marking both as dependent.

- **LS20:** a heterogeneous collection incidentally inside a large bbox should no longer qualify unless it forms an addressable lattice, has a corresponding reference panel, or gains transition corroboration. This is where the pattern detector should stop firing.

- **SC25:** the binary 3×3 structure should be eligible despite using fewer than three colours. Arrival should remain because the game is phased and eventually includes an exit. A single game-level “primary” label cannot honestly determine which current-frame hypothesis must rank first.

## What to measure next

TOP1 should become secondary. The validation script compares one early snapshot against a mostly single game-level primary label ([scoring](/Users/nhn/Workspace/Admorphiq/scripts/_r58_ledger_validation.py:108)), even though the typology records hybrids and phases. That is not the same target as a per-turn hypothesis ledger.

Primary metrics should be:

- supported-type recall under the cap;
- misses caused by detector non-firing versus cap eviction;
- number of independent evidence footprints, not just candidate count;
- abstention/`insufficient_evidence` quality;
- resolution after one or two safe probes;
- eventual intent/playbook success when citing each hypothesis.

The always-legal `unknown` path already supports this design ([protocol](/Users/nhn/Workspace/Admorphiq/src/admorphiq/explanation/protocol.py:317)). But the weak LLM should not be handed four scores and asked to invent the disambiguation itself: GoalLedger should return a specific structural test such as “whether edits follow a translated fixed stencil or directly repaint one canvas slot.”

In short: **stop asking the six local margins to elect a winner. Preserve a small dependency-aware hypothesis set, promote candidates through evidence stages, and spend the next detector change on making `pattern_match` match its actual predicate.**
