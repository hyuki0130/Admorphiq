# GoalLedger ranking design question — brief for Codex

**Repo**: `/Users/nhn/Workspace/Admorphiq` (ARC-AGI-3 agent, project "Admorphiq"). This brief is
self-contained — no prior conversation context is assumed. All file paths are absolute or
repo-relative from that root.

## 1. The system

`GoalLedger` (`src/admorphiq/explanation/goal_ledger.py`) is the executable win-condition
typology layer of a larger "EXPLANATION layer" design
(full spec: `docs/r58_codex_explanation_layer_20260715.md` — win-condition typology is §4,
quoted in full below since it's the governing contract). The bigger picture: an offline,
weak (~27-31B) LLM plays unseen ARC-AGI-3 games through a harness-enforced protocol
(`src/admorphiq/explanation/protocol.py`) that forces it to declare a typed intent, fill typed
slots referencing observation handles, and let the harness auto-invoke the matching kernel — the
model never freehands tool calls. `GoalLedger.detect(observations)` is one input to that loop: a
**pure, stateless function** that inspects the CURRENT frame (plus, when available, one
before/after transition and a short window of repeated-action frames) and proposes which
**win-condition TYPE** the game's goal probably is — entirely separate from which *mechanic*
strategy (navigation, toggle-puzzle, etc.) the model later picks to pursue it. It runs with
**zero label leakage**: no level-up markers, no gold traces, nothing but observable pixels —
because the eventual deployment target is 110 *hidden* competition games, and any detector that
implicitly depends on knowing when a level cleared cannot transfer.

Verdict §4, quoted in full (the binding contract this module implements):

> Do not make the model read a prose checklist of every goal type.
>
> Turn R57 into an executable `GoalLedger`:
> - At first observation, after a material transition, and after level-up, automatically run
>   all cheap zero-action detector sketches.
> - Return only the top evidence and contradictions, capped to a few entries.
> - Require either two distinct competing goal hypotheses or an explicit `insufficient_evidence`
>   declaration.
> - Keep `unknown` available.
> - Goal type and mechanic intent must remain separate. "Arrival" does not imply ordinary
>   navigation; "uniformity" does not prove GF(2).
>
> Example result:
> ```json
> {
>   "goal_candidates": [
>     {"id":"goal:3","type":"containment","support":["e12","e18"],"against":["e21"]},
>     {"id":"goal:4","type":"elimination","support":["e18"],"against":[]}
>   ],
>   "unresolved_tests":["whether region:7 must vanish or enter region:2"]
> }
> ```

### The six detectors, current state (commit `29a9ca8`, `src/admorphiq/explanation/goal_ledger.py`)

Each detector is a pure function of kernel-computed structural evidence (region segmentation,
shape signatures, containment relations, frame diffs — from `src/admorphiq/kernels/`), fires
`None` or exactly one candidate `{"id", "type", "support": [evidence handles], "against": [...],
"strength": float in [0,1]}`, and every candidate's `"strength"` is now **floor-anchored**
(explained below). `detect()` collects whichever of the six fire, sorts by `strength` descending
(ties broken by a fixed detector-execution order), caps to `MAX_CANDIDATES = 4`, and returns
`{"goal_candidates", "unresolved_tests", "insufficient_evidence" (True iff <2 candidates fired),
"evidence_detail"}`.

| Type | Firing gate (hard, unchanged since round 1) | Raw strength formula | `gate_min` (floor-anchoring reference point) |
|---|---|---|---|
| `arrival` | >=1 region whose colour is globally unique in the frame AND whose size is <=50% of the frame area (dominance exclusion) | `uniqueness_sharpness * size_distinctness`, where `uniqueness_sharpness = 1/n_such_candidates`, `size_distinctness = 1 - size/frame_area` | `uniqueness_sharpness_actual * 0.5` (size term at its dominance boundary; sharpness term ungated, cancels) |
| `uniformity` | >=6 regions share an identical translation-invariant shape signature, that shape spans >1 cell, and the class uses <=3 distinct colours (classes tried population-descending, so a disqualified large class doesn't mask a smaller valid one) | `population_frac * non_triviality * colour_fit` = `(members/n_total) * (1-1/shape_cells) * (1-(n_colours-1)/3)` | `(6/n_total) * 0.5 * (1/3)` = `1/n_total` (ALL three terms are gated, so gate_min is a pure per-call number, no ungated factor) |
| `containment` | >=2 sibling "container" regions (via `region_relations`' bbox-containment relation), each holding >=2 contained item regions | `sibling_component * regularity` = `(1-1/n_siblings) * (1 - stdev(item_counts)/mean(item_counts))` | `0.5 * regularity_actual` (only sibling count gated; regularity ungated, cancels) |
| `pattern_match` | exactly ONE container region holding >=5 item regions spanning >=3 distinct colours | `item_richness * colour_richness` = `(1-1/n_items) * (1-1/n_colours)` | `(1-1/5) * (1-1/3)` = `0.8 * 0.667` ≈ **0.533** (BOTH terms gated — a FIXED constant, independent of any per-call data) |
| `elimination` | needs a before/after frame pair; >=1 region's exact `(colour, shape)` signature present before, absent after | `size_component * signature_distinctness * confirmation_component`. `size_component` = 1 minus the normalized gap between the vanished region's size-fraction and the board's own median region size-fraction. `signature_distinctness = 1/n_distinct_vanished_signatures_in_this_transition`. `confirmation_component = min(1, n_transitions_with_a_vanish/2)` — optionally corroborated by a caller-supplied `extra_transitions` list of additional (before,after) pairs; with none supplied it's fixed at exactly 0.5 | `size_component_actual * signature_distinctness_actual * 0.5` (only confirmation gated; with no `extra_transitions`, `raw == gate_min` EXACTLY, so an uncorroborated elimination call always lands exactly at the floor) |
| `threshold` | needs >=3 frames under one repeated action, giving >=2 consecutive `frame_diff` counts that are monotonic and not flat | `run_length_component * magnitude_component` = `(1-1/n_diffs) * (|diffs[-1]-diffs[0]|/max(diffs[-1],diffs[0],1))` | `0.5 * magnitude_component_actual` (only run-length gated; magnitude ungated, cancels) |

**Floor-anchoring** (the round-2 mechanism, added specifically because round-1's raw,
un-normalized strengths caused a measured ranking regression — see §2): every raw strength is
rescaled via `strength = FLOOR + (1-FLOOR)*(raw - gate_min)/(gate_max - gate_min)`, `FLOOR = 0.2`,
`gate_max = 1.0` for all six (each raw formula is a product of `[0,1]`-bounded terms). `gate_min`
is derived **analytically per detector** (table above): substitute every term that has an
explicit numeric gate with its own boundary value, and leave every other (already-observed,
un-gated) term at its actual value — those ungated terms then appear identically in both `raw`
and `gate_min` and cancel out of the subtraction. This gives a **provable** invariant
`raw >= gate_min` for every detector (proof: a fired detector's gated terms are, by definition of
having fired, never below their own gate), so `strength` is provably always in `[0.2, 1.0]`.

Two other structural properties, both load-bearing for the ranking discussion below:
- **T4 (Delivery/Carry-and-Place) and T8 (Programmatic/Rewrite-Derivation)** from the underlying
  R57 win-condition typology (`docs/r57_win_condition_typology_20260715.md`) are explicitly
  **unsupported** — no detector ships for them. T4 is compositionally `arrival` + `elimination` on
  the SAME region over time, which this stateless function cannot correlate across calls. T8's
  one anchor game had zero frame-verified win events in the underlying mining pass, so no
  frame-only signature was ever validated for it.
- `detect()` is **stateless per call** — it has no memory of prior calls, no persistent object
  identity across transitions, and does not know which mechanic-intent (if any) the model
  previously tried.

## 2. Measurement history — three rounds, same 24-game battery

**The battery**: 24 of the 25 ARC-AGI-3 public preview games (the 25th, `tr87`, is excluded — it
has zero frame-verified win events in the underlying R57 mining, so there's no ground truth to
score against). For each game, one `detect()` call is built from real early-trace data only:
`frame` = the very first observed frame; `before`/`after` = the first observed transition (row 0
of the trace); `action_repeat_frames` = an early run of frames under one repeated action, when the
trace happens to have one. **No level-up label is ever used to build the call** — only the ground
truth used to SCORE the result afterward is. Ground truth is a hand-transcribed mapping from each
game's R57-assigned win-condition type to this ledger's vocabulary. Scoring: **TOP1** = the
ground-truth type is `goal_candidates[0]` (highest-ranked); **TOPK** = the ground-truth type
appears anywhere in the (capped, up to 4) list; **MISS** = absent. 21 of the 24 games have a
ground truth in this ledger's supported vocabulary and are scored (3 are excluded from scoring:
one is itself unresolved in R57's own typology, two are the explicitly-unsupported T4/T8 cases —
their ledger output is reported but not scored as hit/miss).

Reproduction: `uv run python scripts/_r58_ledger_validation.py` from the repo root (reads
`data/traces/*.npz`, prints the table, writes `scripts/_r58_ledger_validation_results.json`). This
script has been run **unchanged** across all three rounds below — it is the fixed regression
benchmark; only `goal_ledger.py` changed between rounds.

### Aggregate, all three rounds (n=21 scored games)

| Round | What changed | TOP1 | TOPK | MISS |
|---|---|---|---|---|
| v1 (pre-scoring) | Candidates ranked by fixed detector-execution order (no `"strength"` field existed) | 8/21 (38.1%) | 12/21 (57.1%) | 9/21 (42.9%) |
| Round 1 | Added `"strength"` (un-anchored raw formulas, see table in §1 minus the floor-anchoring column) + two discriminators (`elimination` corroboration penalty added but not yet load-bearing without `extra_transitions`; `uniformity`'s two hard gates added) + `arrival`'s dominance-exclusion filter replacing a broken median filter | 6/21 (28.6%) | 16/21 (76.2%) | 5/21 (23.8%) |
| Round 2 (current, commit `29a9ca8`) | Floor-anchoring added (table in §1) — no firing-gate changes | 6/21 (28.6%) | 16/21 (76.2%) | 5/21 (23.8%) |

Round 1 vs. v1: TOPK coverage improved sharply (+19.1pp) and MISS dropped correspondingly, with
**zero coverage regressions** (no game that had the right type anywhere in its list lost it) — but
TOP1 regressed (-9.5pp), traced to `pattern_match`'s raw formula sitting at ~0.533 even at its
bare-minimum firing case, while `arrival`'s raw formula can legitimately be much lower under
ambiguity (dividing by however many colour-unique candidates exist) — so `pattern_match` started
winning ranking comparisons purely because its formula family runs numerically higher, not because
its evidence was stronger.

Round 2 vs. round 1: the AGGREGATE numbers are **exactly identical** — but this is a wash, not
"nothing changed". Only two individual games moved: `cd82` TOP1→TOPK (a new small regression) and
`sp80` TOPK→TOP1 (an improvement), netting to zero. Every other game's category is byte-identical.
Floor-anchoring's effect is visible in the per-detector breakdown, not the per-game verdict counts.

### Per-detector fire-rate / TOP1-rate, all three rounds (out of 24 games; includes the 3
unscored games since firing itself is still informative there)

| Type | fires v1 | fires r1 | fires r2 | TOP1 v1 | TOP1 r1 | TOP1 r2 |
|---|---|---|---|---|---|---|
| `arrival` | 12/24 | 22/24 | 22/24 | 12/24 | 13/24 | 16/24 |
| `uniformity` | 14/24 | 9/24 | 9/24 | 10/24 | 1/24 | 1/24 |
| `containment` | 10/24 | 10/24 | 10/24 | 0/24 | 1/24 | 1/24 |
| `pattern_match` | 8/24 | 8/24 | 8/24 | 0/24 | 6/24 | 4/24 |
| `elimination` | 17/24 | 15/24 | 15/24 | 1/24 | 1/24 | 0/24 |
| `threshold` | 5/24 | 6/24 | 6/24 | 1/24 | 2/24 | 2/24 |

Read: floor-anchoring DID do real work — `arrival`'s TOP1 count climbed 13→16 (partial recovery)
and `pattern_match`'s dropped 6→4 (partial fix) — but the aggregate stayed flat because the
remaining `pattern_match` wins are not calibration artifacts (see §3). Note `pattern_match`'s and
every other detector's **fire rate is unchanged across rounds 1→2** — floor-anchoring only
re-ranks candidates that already fired; it cannot make a detector fire less often.

### Current (round 2) per-game verdict table, candidates in final strength-sorted order

```
game   gt_primary       verdict    candidates(strength)
ar25   arrival          TOP1       [arrival(0.461), elimination(0.200)]
bp35   arrival          TOPK       [pattern_match(0.371), arrival(0.360), threshold(0.282), containment(0.238)]
cd82   pattern_match    TOPK       [arrival(0.463), containment(0.200), pattern_match(0.200), elimination(0.200)]
cn04   arrival          TOP1       [arrival(0.357), threshold(0.201)]
dc22   arrival          TOPK       [pattern_match(0.352), arrival(0.314), uniformity(0.253), elimination(0.200)]
ft09   uniformity       TOPK       [pattern_match(0.496), arrival(0.458), uniformity(0.451), threshold(0.400)]
g50t   unclassified     N/A        [arrival(0.465), pattern_match(0.200)]                 (unscored — R57 itself has no confident type for this game)
ka59   elimination      TOPK       [threshold(0.374), arrival(0.360), containment(0.200), elimination(0.200)]
lf52   containment      TOPK       [arrival(0.933), uniformity(0.554), containment(0.200), elimination(0.200)]
lp85   arrival          TOP1       [arrival(0.984), uniformity(0.311)]
ls20   arrival          TOPK       [pattern_match(0.486), arrival(0.314), containment(0.296), elimination(0.200)]
m0r0   arrival          TOP1       [arrival(0.298)]                                        (insufficient_evidence=True — only 1 candidate)
r11l   threshold        MISS       [arrival(0.467), containment(0.200), elimination(0.200)]
re86   containment      MISS       [arrival(0.467), uniformity(0.418), elimination(0.200)]
s5i5   arrival          MISS       [containment(0.200), elimination(0.200)]
sb26   containment      TOPK       [arrival(0.972), pattern_match(0.486), containment(0.200)]
sc25   pattern_match    TOPK       [arrival(0.950), uniformity(0.365), containment(0.325)]
sk48   arrival          MISS       [threshold(0.249), containment(0.220), uniformity(0.214), elimination(0.200)]
sp80   arrival          TOP1       [arrival(0.288), elimination(0.200)]
su15   containment      MISS       [arrival(0.459), threshold(0.369), elimination(0.200)]
tn36   unsupported(T8)  N/A        [arrival(0.862), uniformity(0.704), pattern_match(0.403), elimination(0.200)]   (unscored — no detector for T8 by design)
tu93   arrival          TOPK       [uniformity(0.417), arrival(0.314), elimination(0.200)]
vc33   arrival          TOP1       [arrival(0.465), elimination(0.200)]
wa30   unsupported(T4)  N/A        [arrival(0.314)]                                        (unscored — no detector for T4 by design; insufficient_evidence=True)
```

## 3. The residual problem, precisely

On `dc22`, `ft09`, `ls20`, `sc25` — 4 of the 6 games where the ground-truth type is NOT ranked
first — the wrong-type detector outranks the true type with **genuine, non-artifactual** evidence,
not an inflated floor. Concrete per-board numbers (re-derived directly from `detect()` against
each game's real first frame/transition, `data/traces/<game>.npz`):

```
dc22 (ground truth: arrival)
  pattern_match  strength=0.3524  "container region holds 15 item regions spanning 3 distinct colours"
  arrival        strength=0.3141  "region colour occurs nowhere else in the frame and does not dominate (>50%) the board"  <- GROUND TRUTH
  uniformity     strength=0.2529  "one of 13 regions sharing an identical 4-cell translation-invariant shape"
  elimination    strength=0.2000  (uncorroborated, at floor)

ft09 (ground truth: uniformity — this is R57's SINGLE CLEANEST signal in its entire mining pass)
  pattern_match  strength=0.4958  "container region holds 17 item regions spanning 4 distinct colours"
  arrival        strength=0.4583  "region colour occurs nowhere else in the frame and does not dominate (>50%) the board"
  uniformity     strength=0.4507  "one of 32 regions sharing an identical 36-cell translation-invariant shape"  <- GROUND TRUTH
  threshold      strength=0.4000

ls20 (ground truth: arrival)
  pattern_match  strength=0.4857  "container region holds 8 item regions spanning 5 distinct colours"
  arrival        strength=0.3141  "region colour occurs nowhere else in the frame and does not dominate (>50%) the board"  <- GROUND TRUTH
  containment    strength=0.2962  "container region holds 8 item regions"
  elimination    strength=0.2000

sc25 (ground truth: pattern_match, per R57 — though R57 itself calls this a pattern_match/uniformity hybrid)
  arrival        strength=0.9500  "region colour occurs nowhere else in the frame and does not dominate (>50%) the board"
  uniformity     strength=0.3651  "one of 9 regions sharing an identical 9-cell translation-invariant shape"
  containment    strength=0.3255  "container region holds 9 item regions"
  (pattern_match did not fire on this board at all — 0/4 candidates)
```

Two distinct sub-patterns inside "residual":

1. **`pattern_match` genuinely fires with rich (not floor-clamped) evidence on boards where it
   is not the ground truth.** Its fire rate is unchanged at 8/24 across every round — the
   FIRING criteria (`>=5 items, >=3 colours, in exactly one container`) were never touched by
   either tuning round, only its ranking score was. On `ft09` specifically, its 17-item/4-colour
   "container" is almost certainly a superset or near-superset of the SAME 32 cells that
   correctly drive `uniformity` there (`ft09` is a lights-out-style toggle grid whose entire cell
   population sits inside one bordering region) — i.e. `pattern_match` may literally be re-reading
   `uniformity`'s own evidence through a different lens (many-heterogeneous-items-in-one-container)
   rather than an unrelated false signal.
2. **`arrival` also occasionally wins on the wrong board with very high, non-floor confidence**
   (`sc25`: 0.950 — a single, totally unambiguous colour-unique tiny region) even though
   `arrival` is not `sc25`'s ground truth. This is NOT a `pattern_match`-specific problem; any
   detector with genuinely strong local evidence can outrank the true type if the true type's own
   detector has comparatively weaker (but still valid) evidence on that specific board.

Floor-anchoring's provable guarantee (`raw >= gate_min`, `strength` always in `[0.2, 1.0]`) fixes
comparability AT the point each detector fires — it says nothing about, and cannot fix, whether
the RIGHT SET of detectors fired at all for a given board, or which of several genuinely-plausible
firings is contextually the correct one for THIS SPECIFIC game.

## 4. The question

**How should GoalLedger's cross-detector ranking work, given that within-detector calibration
(floor-anchoring) is provably correct but demonstrably insufficient?**

Candidate directions — please evaluate, do not assume one is correct:

**(a) Game-context weighting / mutual exclusion between types.** E.g., a board with a strong
`uniformity` population (many same-shape, few-colour, non-trivial regions) should discount a
`pattern_match` reading whose item pool substantially overlaps the same regions — the `ft09` case
above is a concrete instance to test any proposed rule against. More generally: are there
principled priors over which TYPE PAIRS are structurally more likely to be mutually exclusive vs.
genuinely co-occurring (verdict §4 explicitly wants competing hypotheses to be preserved when they
ARE genuinely competing, e.g. the shipped `containment`-vs-`arrival` "against" cross-check already
in `detect()` — see `src/admorphiq/explanation/goal_ledger.py` around the "Cross-check" comment,
lines ~732-746 — which flags when an `arrival` region is ALSO a contained item, as a genuine
tension rather than silently picking one).

**(b) Tighten `pattern_match`'s firing gate specifically.** Its 8/24 fire rate has been constant
across all three rounds/two tuning passes — it has never been the TARGET of a firing-criteria
change, only a scoring one. Is `>=5 items / >=3 colours / exactly one container` simply too loose
a structural proxy for "this is a paint/fill canvas, not incidentally-containing structure"? What
additional evidence (e.g. relative container size vs. frame, whether the container's OWN shape
looks like a bounded canvas vs. a grid-like region cluster) would discriminate `ft09`-style
false positives from genuine fill/paint boards without smuggling in a per-game constant (repo
constraint: **no per-game thresholds** — any fix must be justifiable purely from structural
properties, the same discipline the two tuning rounds already followed)?

**(c) Accept TOPK as the deliverable; let the LLM disambiguate.** Verdict §4 already REQUIRES
"two distinct competing goal hypotheses OR an explicit insufficient_evidence declaration" — i.e.
the design was arguably never meant to hand the model one confident answer; TOP1 precision might
be measuring the wrong thing entirely if the actual downstream consumer is built to receive and
reason over 2+ competing candidates. See §5 for the exact downstream contract.

**(d) Something else** — a different ranking mechanism, an entirely different candidate-selection
strategy, or a finding that the six-detector design itself needs restructuring (e.g. detectors
that share underlying evidence, like `pattern_match`/`uniformity` on `ft09`, maybe shouldn't be
independent siblings).

## 5. Downstream consumer contract (for evaluating option (c) especially)

`GoalLedger`'s candidates feed `SELECT_INTENT`, the first stage of the harness-enforced protocol
in `src/admorphiq/explanation/protocol.py`. Its schema
(`src/admorphiq/explanation/intents/select.schema.json`) requires `{"intent": <snake_case name>,
"support": [evidence handles]}`, where `intent` must be one of a **dynamic allowlist** the harness
supplies at runtime (currently just `navigation`, since only one mechanic playbook exists — see
`src/admorphiq/explanation/playbooks/navigation.yaml`) **plus the always-legal escape value
`"unknown"`**. The model is never forced to commit to a single goal hypothesis it isn't confident
in — `unknown` is always selectable regardless of what `GoalLedger` returns, and
`GoalLedger.compact_view()`'s `insufficient_evidence` flag is explicitly designed to signal
"route toward `unknown`" without the ledger needing to assert that itself (see
`compact_view`'s docstring in `goal_ledger.py`). A `goal_candidate`'s `"id"` (e.g. `"goal:3"`)
is designed to flow directly into a later `navigation` FILL_INTENT declaration's
`goal_hypothesis` slot (proven end-to-end by a passing test,
`tests/test_goal_ledger.py::test_goal_candidate_id_is_a_valid_navigation_goal_hypothesis_handle`).
So the realistic per-turn shape available to the model is: however many candidates
`GoalLedger` capped to (up to 4, sorted by strength), each independently citable as a
`goal_hypothesis` when the model later commits to a mechanic. Nothing currently prevents the model
from reasoning over 2, 3, or 4 candidates rather than only the top-ranked one — TOP1 accuracy was
chosen as this validation's headline metric by analogy to typical classifier evaluation, not
because the downstream contract structurally requires a single top pick.

## 6. Constraints on any proposed solution

- **Structural fixes only — no per-game thresholds or constants.** Every existing gate/formula is
  justified from general structural properties (region counts, shape-signature classes, bbox
  containment, frame-diff trends) that must generalize to the 110 *hidden* competition games, never
  tuned to make one of these 24 *public* games pass. This is a hard repo-wide discipline (see
  `scripts/explanation_lint.py`, which mechanically rejects any runtime artifact under
  `src/admorphiq/explanation/` referencing a public game id/title, and the module docstring's own
  repeated "never a per-game constant" framing).
- **Detectors stay kernel-composed and pre-clear-only.** No level-up labels, no gold-trace data, at
  runtime. `src/admorphiq/kernels/` (region segmentation, shape signatures, containment relations,
  frame diffs) is the only computational primitive layer available — new structural signals should
  ideally compose from what's already there (`find_regions`, `region_relations`,
  `multiset_signature`, `frame_diff`) rather than requiring a new kernel, though a new kernel is not
  ruled out if genuinely justified.
- **`detect()` is a pure, stateless, single-call function** — no cross-call memory, no persistent
  object identity, no knowledge of which mechanic intent the model previously attempted. Any
  proposed direction that requires state should say so explicitly and where that state would live
  (this ledger module vs. the harness/protocol layer).

## Deliverable requested

A recommendation among (a)-(d) (or a hybrid, or a rejection of the framing), with reasoning
grounded in the concrete `dc22`/`ft09`/`ls20`/`sc25` evidence above wherever possible, and — if a
new structural rule is proposed — a sketch concrete enough to implement against
`src/admorphiq/explanation/goal_ledger.py`'s existing six-detector, floor-anchored architecture.
