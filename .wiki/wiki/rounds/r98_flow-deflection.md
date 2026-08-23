---
type: reasoning
round: R98
axis: agent25 — hypothesis-DSL family expansion #3 (two-phase place-then-propagate flow)
keywords: [agent25, hypothesis-dsl, family-expansion, flow-deflection, place-then-propagate, sp80, response-table, reference-propagator, gated-enum, inert-slot, equivalence-class, near-ood, oracle-certification, two-model]
verdict: **MODEL STAGE MEASURED (2026-08-23) — SELECT CONFIRMED ON BOTH CONTRACT MODELS (gemma4 3/3, gpt-oss 3/3, and qwen3.8-27b 3/3), each picking the EXACT truth every run and clearing the level at oracle-gate efficiency; FILL passed outright by gpt-oss-120b 3/3 with a perfect 7-of-7 hypothesis, gemma4 missing exactly one slot.** Live oracle gate 3/3 end to end (2026-08-22): discovery → grounding → verify → compile → execute clears sp80 idx0 in 10 actions / 2 commits against a frozen cap of 20 / 3. Contract FROZEN after the Codex schema consult (CONDITIONAL GO, six corrections bound and discharged BY MEASUREMENT); grounding earns 10/10 measured slots from observation alone; the verifier reproduces the frozen mutant table on live evidence; the model-stage driver self-tests 6/6 on deterministic stubs. Only the paired GPU model runs remain
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

## The harness, built and certified

**Grounding** (`grounding_flow.py`) — the pre-declared 40%-risk component, **10/10
slots PASS live**. Everything is earned: the flow is whichever colour grows
incrementally across a layer run, the piece is whichever region translates rigidly
under a press, the commit action is whichever action returns more than one layer.
The strongest check available passed — the RECOVERED trajectory equals the
propagator's PREDICTION for the committed placement, 20 steps, exactly.

Four defects were found by measurement, each a real trap:

1. an edge-pinned HUD is ONE PIXEL ROW over the cell grid; it defeated scale
   inference and reduced every downstream slot to UNKNOWN. The first fix — exempt
   whole border BLOCKS — was worse: it accepted a scale twice too large by excusing
   real board content as overlay. The rule is a 1–2 pixel margin.
2. a featureless frame is uniform at EVERY scale, so inferring from one silently
   overestimates. A candidate must now resolve at least two distinct cell values.
3. the growth run must stop at a board reset, and flow must be separated from a
   target that lights up when satisfied by GROWTH STEPS, not final size.
4. a failure animation makes status bands oscillate, and an edge-pinned band
   touches the cells below the real targets — merging them under 4-connectivity into
   one phantom region. The **R92 merge trap in a new guise**; only a change that is
   STABLE at the end of the run counts.

Measured and recorded as an UNESTABLISHED PREMISE: at idx0 `control_mode` is
**unobservable**. The single piece starts pre-selected, so a click produces no
frame change and the two control modes are behaviourally identical. The harness
passes by saying so at low confidence, and the premise is excluded from model
credit.

**Propagator** (`propagate_flow.py`) — the response table run AS the simulator,
moved out of the certification script into `src` so there is exactly one
implementation. Pure: boards arrive as measured cell sets, never read from colours.

**Verifier** (`verifier_flow.py`) — an EXACT replay, not a feature comparison.
Live certification reproduces the frozen mutant table with no disagreement: oracle
PASS, 6 CONTRADICTED, 3 UNKNOWN. Three honesty rules: non-gating slots are
neutralised; a POSITIVE claim in a slot measured inert returns UNKNOWN rather than
PASS, because a matching replay proves nothing about it; a verify-only transition
is reported but never passes.

**Compiler** (`compiler_flow.py`) — placement search under the hypothesis's OWN
table. That is the design claim paying off: a wrong table yields a confidently
wrong plan the live spill falsifies, where a fixed simulator would make every
candidate plan identically and void the selection stage.

## LIVE ORACLE GATE — 3/3 PASS

```
run 1: verdict=PASS plan=SOLVABLE offset=(0,1) actions=10 (discovery 8 + plan 2) commits=2 cleared=True
run 2: identical
run 3: identical
```

Inside the frozen cap of 20 actions / 3 commits, with the same plan every run.

## Model stage — driver built, self-test 6/6

`scripts/probe_r98_model_bench.py`: `--mode select` picks among neutrally
serialized candidates; `--mode fill` generates the objective variant then the
gated slots. `own_flow` and `boundary` are NEVER ASKED — both measured inert, and
forcing a choice from absent evidence manufactures a false result. Evidence is
PROSE rendered from the measured trajectory; the full enforced rule set is stated
verbatim to the model; scoring accepts the equivalence class.

One harness defect the self-test caught: candidates deviating only in an inert
slot serialize IDENTICALLY to the truth once neutralised, so offering all nine
mutants would have asked the model to choose between three indistinguishable
options — a random failure baked into the stage. They are excluded from the select
list and keep their real job in the mutant table.

Self-test: truthful select and fill both clear; wrong picks are blocked by the
verifier at **zero executed actions**; an equivalence-class answer scores correct;
the leak guard is clean.

## MODEL STAGE — MEASURED (2026-08-23)

Three models as Kaggle kernels against the live env. Two prompt versions were run;
the first exposed a defect, the second is the result.

### Final result (corrected ask) — artifacts `scripts/rounds/R98/model_v2/`

| model | select | fill | per-slot correct (of 3 runs) |
|---|---|---|---|
| gemma4-31b-it | **3/3 PASS** | 0/3 | 6 of 7 perfect; ONLY `hazard_response` wrong |
| qwen3.8-27b | **3/3 PASS** | 0/3 | 5 of 7; both hazard slots wrong |
| gpt-oss-120b | **3/3 PASS** | **3/3 PASS** | **7 of 7 perfect** |

Against the frozen contract (per-model ≥2/3, CONFIRMED = both contract models):

- **SELECT: CONFIRMED on both models.** Every model picked the EXACT truth on every
  run, then verifier PASS → plan SOLVABLE → 2 executed actions → level cleared, at
  10 actions and 2 commits against the 20/3 cap. That is oracle-gate performance
  reached by the model rather than by a hand-authored hypothesis.
- **FILL: gpt-oss-120b passes outright, 3/3, with a perfect hypothesis.** Not
  confirmed paired: gemma4 misses exactly one slot.

### What the first prompt version taught

The first run had gemma4 3/3 and qwen 3/3 on select but gptoss 0/3, and 0/3 fill
everywhere. Aggregating the answers exposed the cause: three independent models were
unanimous on the same three wrong values across nine runs, while getting the other
three right. That is a prompt defect, not a model verdict — the full argument is in
[[../lessons/unanimous_wrong_answers_are_a_prompt_defect_20260823]].

Three fixes: state that flow cells PERSIST and warn that a repeating split only
LOOKS like sideways travel; gloss every closed-choice value (no model can map
`same_sink_flanks` onto "occupied the notch in the target's top edge" by guessing);
and say that the two hazard answers must agree.

The effect was large and one-directional. gpt-oss went **0/3 → 3/3 on select and
0/3 → 3/3 on fill**; gemma4 and qwen went from three wrong slots to one and two.

### The one honest residue: hazard is encoded twice

gemma4's failure is a single slot, and it is self-contradictory in a telling way: it
answered `hazard_policy: fatal_on_contact` (correct — barrier contact fails the
attempt) while answering `hazard_response: terminate_local`, whose gloss says the
attempt can still succeed. Both halves of its reasoning are right about the world;
our encoding splits fatality across two slots and lets an incoherent pair through.

**This is recorded, not patched.** gpt-oss resolves the same encoding from the same
evidence 3/3, so the encoding is learnable and re-cutting it now would be tuning the
representation until the weaker models pass — metric gaming, not measurement. The
proposed orthogonalisation (`hazard_response` = `ends | passes_through` about the
STREAM only, fatality owned solely by `hazard_policy`) is a schema change to be
measured on its own, against all three models, as its own experiment.

### Operational traps fixed along the way

- the R98 driver did not honour `ARC_ENVIRONMENTS_DIR`, so a GPU session booted a
  healthy model server and only then found an arcade with zero games. Every entry
  point now honours it, and the notebook preflights the directory BEFORE the server
  boots.
- a kernel pushed too soon after a dataset version pins the PREVIOUS version, and
  `datasets status` reports "ready" at the dataset level, not the version level. The
  dataset must be verified by FILE SIZE before the kernel is pushed.

## DEPTH WALK — one hypothesis carries two levels (2026-08-23, non-gating)

`scripts/rounds/R98/depth_walk.py` → `depth.txt`. Consecutive levels, same
hypothesis, same harness, each level entered fresh (a level boundary replaces the
layout, so grounding is rebuilt, pieces re-inventoried and the flow's direction
re-learned). Nothing carries across but the hypothesis.

```
idx0: CLEARED — 15 actions (4 selection probes)
idx1: CLEARED — 18 actions (2 selection probes)
idx2: stopped — verifier CONTRADICTED at step 7
```

idx1 is not a re-run of idx0: three pieces instead of one, three targets instead of
two, and the flow runs UPWARD. It clears with no level-specific code, which is the
first real evidence that the schema describes a FAMILY rather than a level.

What each wall taught, in order:

1. the propagator's heading was a hardcoded "down" — idx1 runs up, so the constant
   mispredicted every step there;
2. `Board` held ONE piece, so the flow split around pieces the model did not have;
3. the target shortlist only named targets the probing spill happened to REACH, so
   "satisfy every target" quietly meant "satisfy the ones I saw" — fixed by naming
   regions congruent to a confirmed target;
4. direction inference required one cell per frontier, which is false on any
   multi-source board — idx2 has three sources and reported UNKNOWN until the rule
   became "the unit step that maps the first frontier onto the second".

**Where it stops now**: idx2 grounds completely (4 pieces, 3 targets, 3 emitters)
and the replay tracks the engine for six steps before diverging — the observed
frontier carries a flanking pair the prediction lacks, so something obstructs the
flow that the board does not model. That is the next thread, and it is a precise
one rather than a vague "deeper levels are harder".

## Next

1. **Fill is not confirmed paired.** gemma4 misses one slot, and the cause is our
   encoding rather than its reasoning. Measure the hazard orthogonalisation as its
   own experiment against all three models — never as a patch to move a verdict.
2. **Multi-piece placement**, the burden the idx1 observation named: idx1 carries
   three pieces and three targets, so a single-piece placement satisfies nothing and
   the sink shortlist comes back empty. That, plus a shortlist that can name targets
   from static structure and not only from satisfaction, is the next expansion.
3. qwen3.8-27b matched the contract models on select at first outing and is a live
   deploy candidate rather than a curiosity — worth carrying into the next family.

## Related

- [[r95_hypothesis-dsl]] — the family pipeline and the equivalence-class precedent.
- [[r96_controlled-grid-dynamics]] — family #2; the oracle-first and asymmetric-
  mobility doctrines this round inherits.
- [[r97_self-extension]] — tier-2; the "state every enforced constraint in the
  model-facing contract" lesson, applied preemptively here.
- [[r92_sp80-l2-premise-correction]] — the sp80 decode and the perception traps.
- [[../lessons/faithful_offline_simulator_20260715]] — learn an operator, then plan.
