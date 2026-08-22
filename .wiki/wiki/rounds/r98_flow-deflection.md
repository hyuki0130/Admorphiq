---
type: reasoning
round: R98
axis: agent25 — hypothesis-DSL family expansion #3 (two-phase place-then-propagate flow)
keywords: [agent25, hypothesis-dsl, family-expansion, flow-deflection, place-then-propagate, sp80, response-table, reference-propagator, gated-enum, inert-slot, equivalence-class, near-ood, oracle-certification, two-model]
verdict: IN PROGRESS — **LIVE ORACLE GATE 3/3 PASS end to end** (2026-08-22): discovery → grounding → verify → compile → execute clears sp80 idx0 in 10 actions / 2 commits against a frozen cap of 20 / 3. Contract FROZEN after the Codex schema consult (CONDITIONAL GO, six corrections bound and discharged BY MEASUREMENT); grounding earns 10/10 measured slots from observation alone; the verifier reproduces the frozen mutant table on live evidence; the model-stage driver self-tests 6/6 on deterministic stubs. Only the paired GPU model runs remain
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

## MODEL STAGE — first measurement (2026-08-23)

Three models, run as Kaggle kernels on the live env (`notebooks/r98_flow_bench.py`).
Artifacts: `scripts/rounds/R98/model/`.

### SELECT — two of three models reach oracle-gate performance

| model | select | detail |
|---|---|---|
| gemma4-31b-it | **3/3 PASS** | picked the EXACT truth every run → verifier PASS → plan SOLVABLE → 2 executed actions → cleared, 10 actions / 2 commits |
| **qwen3.8-27b** | **3/3 PASS** | identical, deterministically |
| gpt-oss-120b | 0/3 | picked wrong candidates; verifier CONTRADICTED, **zero actions executed** |

qwen3.8-27b was released 2026-08-14 (dense 27.8B, Apache 2.0, hybrid Gated
DeltaNet — vLLM 0.17+ implements those layers). It matched gemma4 exactly on its
first outing, which makes it a live candidate for the deploy model rather than a
curiosity.

The safety property held everywhere: every wrong hypothesis was blocked before a
single action was spent.

### FILL — 0/3 everywhere, and the reason is the prompt

Aggregated over 9 runs × 3 models:

| slot | truth | answers |
|---|---|---|
| `piece_response_direction` | `preserved` | **`outward_turned` 9/9** |
| `sink_response_predicate` | `same_sink_flanks` | **`contact` 9/9** |
| `hazard_response` | `terminate_fatal` | **`terminate_local` 9/9** |
| `piece_response_propagation` | `cellwise_iterative` | correct 8/9 |
| `sink_response_miss` | `spread_like_piece` | correct 7/9 |
| `piece_response_spawn` | equivalence class | correct 9/9 |

Three independent models, nine runs, unanimous on the same three wrong values —
while getting the other three right. That is a prompt defect, not a model verdict,
and the same defect explains gpt-oss's select failures (it picked exactly the
hazard-ignoring and outward-turning candidates). Full analysis:
[[../lessons/unanimous_wrong_answers_are_a_prompt_defect_20260823]].

The three defects, all in the ask:

1. the evidence described the split cells as having "moved outward", which is the
   animation's APPEARANCE and the opposite of the mechanism — flow cells persist,
   so a cell appearing further out is a NEW cell;
2. the closed choices were bare identifiers with no gloss, so `same_sink_flanks`
   had to be guessed rather than read;
3. hazard was split across a flow-level response and an objective-level policy
   whose required agreement was never stated.

All three are fixed and the re-measurement is running. Two operational traps were
also fixed on the way: the R98 driver did not honour `ARC_ENVIRONMENTS_DIR` (a GPU
session reached a healthy model server and then found an arcade with no games), and
a kernel pushed too soon after a dataset version pins the PREVIOUS version — the
dataset must be verified by FILE SIZE, not by its "ready" status.

## Next — the paired runs, ready to launch

`notebooks/r98_flow_bench.py` is the Kaggle kernel, built on the R95b boot path
verbatim (vLLM api_server on the mounted model, `ARC_ENVIRONMENTS_DIR` pointing at
the competition `environment_files` so the run drives the LIVE env). It runs BOTH
modes in one kernel and writes `r98_flow_bench_<model>.json`.

Two-model rule: run the kernel TWICE, once per mounted model
(`admorphiq-r98-flow-gemma4` and `admorphiq-r98-flow-gptoss`). No one-shot
verdicts.

Ship in the working tree: `scripts/probe_r98_model_bench.py` and the `admorphiq`
package. Per-model success is ≥2 of 3 runs per mode; CONFIRMED = both models.

Locally the same driver runs against any OpenAI-compatible endpoint via
`HARNESS_LLM_BASE_URL` / `HARNESS_LLM_MODEL`; the dev Mac cannot host either model,
which is why the measurement is a GPU kernel.

## Related

- [[r95_hypothesis-dsl]] — the family pipeline and the equivalence-class precedent.
- [[r96_controlled-grid-dynamics]] — family #2; the oracle-first and asymmetric-
  mobility doctrines this round inherits.
- [[r97_self-extension]] — tier-2; the "state every enforced constraint in the
  model-facing contract" lesson, applied preemptively here.
- [[r92_sp80-l2-premise-correction]] — the sp80 decode and the perception traps.
- [[../lessons/faithful_offline_simulator_20260715]] — learn an operator, then plan.
