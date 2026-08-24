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
idx2: grounds and VERIFIES; stops at the compiler
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

**idx2 now VERIFIES too** — the replay matches the engine's trajectory on a board
with four pieces, three targets and three simultaneous sources. Two faithfulness
defects were found by chasing that divergence, both worth keeping:

5. barrier inference excluded only the TRACKED piece, so the other pieces were
   classified as barriers. The propagator checks barriers before pieces, so the flow
   was predicted to DIE exactly where the engine splits it. Mistaking a piece for a
   barrier is worse than missing a barrier;
6. spawning treated "empty" as "empty of flow", when the engine requires empty of
   EVERYTHING. Spreading into a cell a piece or target already occupies invents flow
   the engine never creates, and the error compounds from that tick on.

**idx2 now CLEARS too.** One hypothesis carries three levels:

```
idx0: CLEARED — 15 actions
idx1: CLEARED — 22 actions
idx2: CLEARED — 47 actions
idx3: stopped — verifier CONTRADICTED at step 4
```

Getting there took a search ladder and, at the end, one measurement that redirected
the whole effort.

**The search ladder.** Four passes, each covering what the previous one cannot: an
exhaustive scan of the cheapest neighbourhood; a decomposed product over the
placements each piece improves ON ITS OWN; a beam that re-ranks every piece against
the layout chosen so far; and finally seeded random sampling. The ranking signal also
had to change — `fatal` is boolean, and on this level EVERY single-piece placement
still touches a barrier, so a boolean gave every candidate the same score and the
ranking carried no information. Counting barrier contacts separates them.

**The measurement that redirected it.** After three structured passes had examined
~35,000 layouts without a winner, the honest question was whether the thing being
searched for was there at all. `feasibility_probe.py` sampled 40,000 random layouts:
**5 winners**, roughly one in eight thousand, at offsets moving all four pieces six
to ten cells each — far outside the cheap neighbourhood, invisible to shortlists that
rank by solo improvement, and past the plateau a hill-climb settles on. So the answer
was neither "search harder in the same way" nor "the model is wrong": it was that
random sampling covers exactly the region the structured passes cannot, at a measured
hit rate that makes it affordable.

**The defect the first successful plan exposed.** The compiler found a layout, the
driver executed all 43 steps, and the level did not clear — because the layout was
never built. Two pieces ended up cells away from their planned positions. The
placement filter forbade only overlap with a target, while the engine refuses any
placement within the measured KEEP-OUT MARGIN of one, and also enforces a row bound.
Both were sitting in the schema's `placement_constraints`, measured, and the compiler
was ignoring them. Filtering on overlap alone lets the search commit to layouts the
engine will not build: the moves are simply dropped, the piece ends up elsewhere, and
the spill that follows is the one nobody planned.

**Piece identity is remembered by SHAPE, in a multiset.** Recording a confirmed
piece by POSITION goes stale the moment it moves, and subtracting a stale region
from the current board leaves fragments that look like extra pieces — measured on
the four-source level, where a four-piece board was reported as six.

Remembering shapes instead fixes the drift but introduces a worse failure if the
shapes are treated as a set: a genuine six-wide piece is happily explained as two
three-wide ones, because the arithmetic works. That is inventing pieces the board
does not have, which is worse than reporting a merged pair whole. Each selection
therefore confirms one INSTANCE of a shape, an instance is spent once, and only an
exact cover counts — otherwise the region is reported whole. Coarser, never
invented.

An honest note on cost: idx2's plan spends 47 actions, so it would score poorly on
the efficiency metric. Whether the pipeline can solve a board and whether it solves it
efficiently are separate questions, and this walk answers only the first.

## A correction: the "idx3 misread" was a diagnostic artifact (2026-08-24)

The previous tick named the next thread as "grounding reads the wrong growth run on
idx3 — direction comes back downward where the emitters sit at the bottom". That was
wrong, and the way it was wrong is worth keeping.

A level boundary arrives as a MULTI-LAYER observation: idx3 was entered on a 25-layer
frame whose first layers still show idx2's board. Grounding reads the LAST layer and
was correct all along; the diagnostic reached for layer zero and confidently described
the previous level — reporting flow-coloured cells along the bottom row that belonged
to idx2, and concluding the direction and emitter set were misread.

Read correctly, idx3 is genuinely different rather than misgrounded: an emitter at
`(7,4)` sits INSIDE a row of pieces and the flow runs DOWNWARD from it, the targets
occupy a wide irregular band across rows 13-14, and the hazard is an L — the bottom
row plus a VERTICAL wall down column 15. Nothing in the family schema forbids any of
that; the walls there are the objective's shape and the search, not the model.

`FlowGrounding.board_view()` now exposes the board grounding is actually looking at,
so a diagnostic reads the same frame the harness does. The cheapest guard against a
whole tick spent explaining a measurement that was never real.

## A source can hide UNDER a piece (2026-08-24, measured)

idx3's divergence turned out to be a mechanic, not a defect. At step 4 the engine
produced two cells the prediction lacked, at `(3,3)` and `(3,8)` — exactly the cells
flanking a piece that spans columns 4-7 on row 3. Nothing fed them: the frame before
the commit shows no flow and no source anywhere in rows 0-3, and the animation shows
no cell above them at any tick.

The engine's own rules leave one possibility, and the level layout confirms it. A
piece keeps any source pixels it covers — the level setup recolours a piece's cells
EXCEPT the source-coloured ones — so a source can sit underneath a movable piece,
drawn over and invisible. Its flow is invisible too, until it walks out past the
piece: seeded under the piece, split at each tick, and finally emerging on both
flanks several ticks later. The same level shows the visible version of this at
`(7,4)`, a source pixel sitting inside a row of pieces.

`FlowGrounding.hidden_sources()` detects them as ORPHAN emergences — a new cell whose
predecessor along the flow direction was never part of the trail, and which is not
one of the run's own first cells. It reports the cell together with the obstruction
it emerged around, which is where the source must be. On idx3 it returns exactly
`((3,3) around (3,4))` and `((3,8) around (3,7))`; on idx0, idx1 and idx2 it returns
nothing, so the signal does not fire where there is nothing to find.

Detection landed first because it is what makes the claim checkable. It also fixed
an honesty defect immediately, before any modelling:

**A known board gap must not be charged to the hypothesis.** The verifier was
returning CONTRADICTED on idx3 — failing a hypothesis that is, as far as anything
here can tell, correct — because flow appeared that no model built from this board
could predict. Grounding already KNEW the board was incomplete. The verdict is now
UNKNOWN with the reason naming the gap:

```
idx3: verifier UNKNOWN — replay diverges at step 4, but the board is incomplete:
      3 source(s) hidden under a piece, not in the board model
```

This matters beyond the depth walk. The model stage scores a hypothesis by the
verifier's verdict, so on any level with a concealed source the old behaviour would
have marked a right answer wrong — a false negative attributable entirely to the
harness. On idx0, where no source is hidden, the frozen mutant table still
reproduces exactly, so the change removes a false failure without softening a real
one.

**Modelling landed too, and the replay now tracks idx3 through seven steps.** The
board carries `emergences` — each a `(cell, step)` pair as OBSERVED. That models the
observation rather than the concealment on purpose: the frames show where and when
flow appeared, while what sits behind the piece is inference, and a model built on
the observation stays checkable.

Getting it to line up took three corrections, each measured:

- **The comparison axis.** The engine renders PAUSES — ticks where nothing new
  appears, because a front is waiting behind itself — while the propagator advances
  on every tick it takes. Raw tick indices therefore do not correspond. Progress
  steps do, so both sides drop empty frontiers and anything measured in ticks is
  expressed on that axis.
- **The seed layer.** `frontier[0]` is the starting flow, not a step, so an
  emergence recorded at observed index 4 belongs to the frontier about to be
  produced — not to loop counter 4, which runs one behind.
- **Travel timing.** An emerged cell APPEARS at its step and travels from the NEXT
  one. Letting it travel immediately runs the whole stream one step ahead of the
  observation from then on.

Divergence moved from step 4 to step 8, with steps 0-7 matching cell for cell.

**Then the comparison itself turned out to be the wrong test.** What remained at step
8 was ordering: the engine spreads a split one cell per step — `(6,4)`, then
`(6,2)+(6,5)`, then `(6,1)`, then `(6,6)` — while the model produces both flanks
together. Flow cells PERSIST, so the physical claim is the TRAIL, and which of two
cells a splitting stream renders first is engine phase, not mechanics. Step COUNT is
phase for the same reason: the engine renders pauses the propagator does not take.

The verifier now compares trails and attributes at cell level: cells the replay
predicts that the flow never reached, or cells the flow reached that the replay
missed. The obvious worry is that this weakens the test — measured, it does not. On
idx0 the frozen mutant table reproduces EXACTLY as before (oracle PASS, 6
CONTRADICTED, 3 UNKNOWN), because a wrong model does not merely reorder cells, it
produces cells the engine never produces.

Those last cells had a single cause, and it was a classification conflict rather
than a missing rule. **A piece can carry a cell of another appearance**: a source
embedded in a bar renders in its own colour, so segmenting by appearance splits the
bar in two and leaves the odd cell belonging to nothing. A cell in no entity is a
FREE cell, and the flow walked straight through the middle of a bar the engine
treats as one obstruction. Pieces parted by a SINGLE non-background cell are now
bridged, absorbing it — one cell only, and never across empty space, because two
genuinely separate pieces are parted by exactly that.

Bridging alone did not fix it, which exposed the sharper defect underneath: the
barrier inference derived its own piece-cell set by appearance instead of using the
inventory. The embedded source was therefore a piece to one part of the harness and
a barrier to another — and the propagator checks barriers FIRST, so the flow died
exactly where the engine splits it. Both now read one inventory.

**idx3 now passes the verifier AND the compiler**, and executes a plan. It does not
yet clear, so the remaining question there is the objective rather than the model:

```
idx0: CLEARED — 15 actions
idx1: CLEARED — 22 actions
idx2: CLEARED — 47 actions
idx3: plans and executes; does not clear
```

## Targets are individuated by their MOUTH (2026-08-24)

idx3's plan was satisfying its objective and leaving the level unfinished, because
grounding had found ONE target where the board carries several. Two causes, both the
merge problem in a new dress:

- targets standing side by side merge into a single region under 4-connectivity,
  exactly as touching pieces do. A single merged target makes "satisfy every target"
  mean "satisfy the one blob", which a plan can do while the level stays open;
- the shape-repeat inference, which names targets the probing spill never reached,
  compared whole regions — so a row of identical targets matched nothing at all.

The family's own satisfaction rule individuates them, so no new assumption was
needed: a target is satisfied when the flow occupies the NOTCH in its edge — the cell
whose two flanking neighbours belong to that same target. Each notch is therefore one
target, region cells are attributed to the nearest one, and a region with fewer than
two notches is returned unchanged. Candidate regions are split this way BEFORE their
shapes are compared.

Measured on idx3: the shortlist went from **1 target to 3**, each a complete cup.
idx0 is unaffected — its two targets stand apart with one notch each, so nothing
splits — and the oracle gate stays 3/3.

Also fixed here, from the same investigation: **a piece can carry a cell of another
appearance**. A source embedded in a bar renders in its own colour, so segmenting by
appearance splits the bar and leaves the odd cell belonging to nothing — and a cell
in no entity is a FREE cell, so the flow walked through the middle of a bar the
engine treats as one obstruction. Pieces parted by a single non-background cell are
now bridged, absorbing it; never across empty space, because that is exactly what
parts two genuinely separate pieces. Bridging alone did not fix it, which exposed the
sharper defect: the barrier inference derived its own piece-cell set by appearance
instead of reading the inventory, so the embedded source was a piece to one part of
the harness and a barrier to another — and the propagator checks barriers FIRST.

idx3 still does not clear. What it now reports is a plan whose predicted coverage is
measured against the right number of targets, which is the precondition for the
objective question being asked correctly at all.

## Every emitted move is CONFIRMED (2026-08-24)

idx3 kept ending up cells away from its plan, so the walk now checks each move
against the next frame instead of assuming it landed — the R96 rule, arrived at here
by the same route: a plan that keeps going after a move failed builds a layout nobody
planned, and the spill that follows says nothing about the hypothesis.

The check compares an unordered MULTISET of footprints, never names. Pieces are
reported in board order, so moving one renames several, and the first
identity-based version of this check reported phantom movement on a level that
actually clears — a false alarm that would have sent the next tick chasing nothing.

What it found on idx3 is precise and was invisible before: pressing the action whose
measured delta is one column RIGHT moved a piece one column LEFT.

```
idx0: CLEARED — 15 actions
idx1: CLEARED — 22 actions
idx2: CLEARED — 47 actions
idx3: move 2 landed elsewhere — expected (7,4),(7,5)…, observed (7,3),(7,4)…
```

That is a contradiction between the measured delta table and what the board does,
and it is the next thread: either the table is being applied to a different piece
than the one selected, or the level's control mapping is not what the opening probes
measured.

## An unmeasured direction is not neutral (2026-08-24)

The delta table on idx3 was missing one of the four directions, and pressing it
plainly moved a piece. Two causes, and only one of them was a defect.

**Not a defect:** the opening probe tried that direction while the piece sat against
a bound, so it genuinely did not move, and the harness correctly recorded a blocked
contrast rather than a delta. The walk now RETRIES any direction that came back
unmeasured, from wherever the piece has since moved to. An unmeasured direction is
not neutral — it removes every placement that needs it from the planner's reach.

**A defect:** a piece coming to rest against a neighbour MERGES with it under
4-connectivity, so the "single region translated" test that attributes a move sees
the region count change and silently records nothing. Attribution now falls back to
reading the CHANGE SET itself — cells that stopped wearing an appearance and cells
that started wearing it, equal in number and related by one translation, is a move
however the regions merged.

The same merge blindness was in the move CONFIRMATION added last tick, which
compared footprint against footprint. It now asks the question that survives a
merge: does translating exactly one piece by the measured delta reproduce the board
now on screen?

idx3's stop is correspondingly sharper — a move merged two pieces and the inventory
cannot split them back apart, so it reports "6 footprints before, 5 after" instead
of silently continuing. All three cleared levels still clear, at a few more actions
each for the retried probes.

## Replanning, and what the search measurements actually said (2026-08-24)

**The walk now REPLANS when a move fails to land** instead of abandoning the level.
The board disagreeing with the plan is information: the engine refuses placements for
reasons the measured constraints do not always capture, and a piece coming to rest
against a neighbour changes what the inventory can tell apart. Re-reading the board
and planning again from what is there is what an agent has to do anyway.

Two measurements corrected assumptions worth recording, because both were the
opposite of the natural guess:

**The placement constraints are not excluding the answer — they concentrate it.**
When the compiler reported no layout on idx3, the obvious suspicion was that the
keep-out margin and row bound had filtered the solution away. Sampling both option
sets says otherwise: constrained placements win 198 times in 40,000 draws against 114
for unconstrained, on roughly half as many options per piece. Constraining the search
made it denser in winners, not poorer.

**And the compiler was never the blocker.** Called directly on idx3's board it
returns a SOLVABLE plan in 0.3 seconds, predicted to satisfy all three targets. The
UNSATISFIABLE report came from a REPLAN — after moves had failed to land and the
board had degraded, with pieces merged and the inventory coarser than when the first
plan was made.

So idx3's chain is now fully attributed: the plan is fine, the execution diverges, and
the divergence degrades the board that the next plan is built on. The wall is the
move that does not land, and everything downstream of it is a consequence.

## Two silent-wrongness fixes in the execution path (2026-08-24)

**The move confirmation was raising false alarms.** It compared footprint against
footprint, and two pieces coming to rest against each other merge into one region
while a piece closing over an embedded cell absorbs it — both change the footprint
list without changing where the pieces are. The check called that a failed move, the
walk replanned on a board it wrongly believed was broken, and the replan was built on
a WORSE reading than the plan it replaced. Confirmation now compares cells occupied:
the expected cells must be present, and extra cells are tolerated because a bridged
region legitimately reports cells no footprint contained before.

**A select could click the wrong piece.** Pieces pass through each other, so an
anchor chosen when the plan was made can be covered by a different piece by the time
the click runs — and after that, every directional press in the plan moves the wrong
thing. `Select` now carries the piece's FOOTPRINT, and the driver locates it on the
CURRENT board and clicks a cell only that piece occupies.

Both are silent-wrongness classes rather than crashes: nothing errored, the numbers
just quietly described a different board than the one on screen. Neither changed
idx3's outcome on the run measured, which is worth stating plainly — they remove ways
to be wrong, and that is worth doing whether or not a level falls out of it.

One measurement from the same session is worth keeping: the plan's INTENDED layout on
idx3 genuinely wins under the verified model — 3 of 3 targets, zero barrier contacts.
The layout is right; what is missing is arriving at it.

## The harness had SELECTED and IDLE the wrong way round (2026-08-24)

Chasing "the plan's moves do not arrive", the trace said the selection never changed
after the first click — every later `Select` appeared to do nothing. Reading the raw
board instead of the harness's belief said the opposite: **every click changed six to
eight cells.** The engine was responding perfectly. The trace was reading the wrong
colour, because grounding had the two appearances INVERTED — it believed the
appearance worn by fourteen cells was "selected" and the one worn by four was "idle".

The cause is that a selection transition shows TWO regions changing at once: the
clicked piece taking the selected appearance, and the previously selected one
dropping to the idle appearance. Both satisfy a test that merely asks "did a region
change colour in place", so the attribution could pick either — and on a board where
it picked the wrong one, the harness's entire notion of selection inverted. Every
later click then read as a no-op, and the walk concluded its moves were not landing
when they were.

The discriminator needed no new observation: the engine selects exactly ONE piece at
a time, so the appearance worn by a single region is the selected one and the
appearance shared by the rest is idle. Measured after the fix, on every level where
both appearances exist, the selected colour is worn by fewer cells than the idle one
— which is what "one piece is selected" means.

This is the third defect in this round whose signature was the harness confidently
describing something other than what was on screen, after the stale-layer diagnostic
and the footprint-identity false alarm. All three were found the same way: read the
raw frame and compare it against what the harness believes.

## A fix that was never actually in effect (2026-08-24)

`Select` was given a FOOTPRINT so the driver could locate the intended piece on the
current board rather than trusting a plan-time anchor. Tracing it afterwards showed
every footprint arriving EMPTY: the compiler builds its plans through one shared
helper, and only the inline construction that helper had replaced was updated. The
anchor re-derivation was running on nothing, so the fix had no effect at all while
appearing to be in place.

Worth naming as its own failure mode. A change that is written, reviewed and
committed can still not be running, and nothing about the test suite or the level
outcome said so — the only thing that surfaced it was printing what the plan actually
contained. Verify the fix is IN EFFECT, not merely present.

With footprints populated, every Select now hits its intended piece:

```
step 3  Select (8,11)  -> selected (8,11)  HIT
step 7  Select (10,9)  -> selected (10,9)  HIT
```

The remaining stall on idx3 is finer: with the right piece selected, some presses
still do not reduce the distance to the intended layout, so a move is being refused
for a reason the placement constraints do not yet capture.

## Read the invariant, do not remember it (2026-08-24)

The selected/idle inversion came back. The previous fix disambiguated the two
appearances at the moment of a selection TRANSITION and then trusted that belief —
and a failed attempt re-selects a piece of the engine's choosing, so any belief
carried across that moment can silently invert again.

The rule that does not rot is the invariant itself: the engine selects exactly ONE
piece at a time, so among the two piece appearances the one worn by a single region
is the selected one. `piece_appearances()` now derives that from the CURRENT board on
every call, falling back to the remembered pair only when the board genuinely cannot
decide — a single piece, or no piece selected at that instant.

Alongside it, the driver gained a recovery instead of a verdict: **a press that
leaves the board unchanged re-selects the intended piece and retries once.** The
likeliest cause of a stalled press is that something re-selected a different piece,
and one retry costs an action while abandoning the level costs the level. One retry
only — a second identical refusal means the move is genuinely refused, and replanning
on the real board beats pressing harder.

Together these moved idx3 from "compiler UNSATISFIABLE on a degraded replan" to
executing its plan to completion:

```
idx0: CLEARED — 19 actions
idx1: CLEARED — 26 actions
idx2: CLEARED — 51 actions
idx3: executes the full plan; does not clear
```

## A plan is a layout, not a list of presses (2026-08-24)

Three defects on idx3, each hiding the next.

**1. The driver replayed presses and never checked it arrived.** The plan ran to
completion three cells short of the layout it had chosen, and the model was right
about what followed: replaying the achieved layout through the verified table
predicts 2 of 3 targets and 2 barrier contacts — exactly a failure. So `Select` now
carries the cells its piece must END UP on, `FlowPlan` carries the whole intended
layout, and the driver tops a piece up when its planned run leaves it short —
including the LAST piece, which has no successor to trigger the top-up and was the
one left short here. Which piece is being topped up is read off the board (the
single region wearing the selected appearance) rather than matched by cell count: a
piece resting against a neighbour is segmented differently from the one the plan
named, and identity-by-size loses it exactly when the top-up is needed.

**2. A moved piece left a false wall behind.** `barriers()` excluded cells occupied
by pieces NOW, but the trail it reasons over was recorded when the pieces stood
somewhere else. A piece that stopped the flow and was then moved away left the cell
it used to occupy classified as a permanent hazard — which is how idx3 came back
`UNSATISFIABLE` from the walk while compiling fine from a scripted entry on the same
level. Each animation now records where the pieces stood WHEN THAT SPILL RAN, and a
cell counts as a piece if it held one in either reading. Whether a cell was a wall is
a fact about that moment, not about now.

**3. What is left is the model, and it is the finding the family was built to
produce.** With both fixed, idx3 reaches its intended layout EXACTLY — short by zero
cells — and still does not clear:

```
idx0: CLEARED — 19 actions
idx1: CLEARED — 26 actions
idx2: CLEARED — 51 actions
idx3: intended layout achieved exactly; does not clear
```

The compiler predicted 3 of 3 targets for that layout; the engine disagrees. This is
the designed attribution path — for this family the transition model IS the simulator,
so a wrong response table yields a plan the live spill falsifies — and it is now
isolated to the table, with placement and execution ruled out by measurement rather
than argument. The next step is cell-level: replay the observed spill on that exact
layout against the predicted trail and name the slot that disagrees.

Gates unchanged: oracle gate 3/3 (10 actions), grounding certification PASS, verifier
and mutant certifications reproduce the frozen table.

## The plan was right; the target list was short (2026-08-24)

With placement and execution ruled out, the attribution on idx3 pointed at the
transition model. It was not the model.

Replaying the achieved layout printed one line that settled it: **`satisfied 2 of 4`**
— on a board the compiler had planned against with **three** targets. A fourth target
existed and became nameable only after the commit, when the spill ran into it. The
objective is *cover every target*; compiled against a short list it means *cover the
ones I happened to see*, and no execution however exact can win it.

The fourth target sat at `(13,2)` and had **four** cells, where the three named ones
had five. That is why every existing source missed it:

- it was never satisfied, so the satisfied-region source could not see it;
- the probing spill never ran into it, so the obstruction source could not either;
- and shape congruence — the source written precisely for untouched targets — requires
  an EXACT copy of a confirmed one, which a differently-sized target is not.

What it did share was its **appearance**: all three named targets and the missing one
wore the same colour. So the shortlist gained a fourth source: when every named target
agrees on one appearance, that appearance identifies targets, and the rest of the board
is read for it. Unanimity is the guard — appearance is weaker evidence than shape, and
one disagreeing group means the appearance is not the discriminator on that board. The
flow's own colour is never a target; movable pieces are excluded as everywhere else.

Measured effect: idx3 now plans against **four** targets, the true count, and idx0–idx2
are untouched and still clear. The new failure is honest and further along —

```
idx0: CLEARED — 19 actions
idx1: CLEARED — 26 actions
idx2: CLEARED — 51 actions
idx3: plans against all four targets; no layout found (61061 examined)
```

— and it is a SEARCH problem, not a modelling one: idx3's five pieces occupy nineteen
cells and its four targets span nineteen, so the board wants something close to an
exact packing, which cost-ordered scan plus sampling is the wrong instrument for.

~~The obvious replacement — assign each target the piece that satisfies it — does not
exist on this board: no single-piece placement satisfies ANY of the four targets.~~
**RETRACTED — that was my own measurement artifact.** `predict().satisfied` holds
target INDICES; the probe asked whether the target's cell-set was a member and so
answered False for every placement. Corrected sweep, same board, one piece moved at a
time over ~1,800 offsets: the entry layout already satisfies **2** targets, 66
placements reach **3**, and 30 of those are inside the compiler's legal option set.
The gradient the beam needs was there all along. Recorded as its own failure mode
below.

One correction to the previous section's reading: the trail divergence printed there
(`invented (8,4)`, `missed (9,5),(9,6)`) was computed on the POST-commit board against
the observed spill, so it compares a prediction for one board with a run on another. It
is not evidence about the response table, and is not carried forward as such.

## A wall wearing the target colour (2026-08-24)

The appearance source from the previous section named a fourth target on idx3 and the
compiler then reported no layout. Both were right, and the target was not a target.

Reading the board where the targets live makes it plain. Three of the four regions are
five-cell U's — two walls, a floor, and a **notch** between the walls. The fourth is a
solid two-by-two block of the same colour with **no notch at all**:

```
r13: · · 11 11 ·  ·  11 ·  11 11 ·  11 11 ·  11
r14: · · 11 11 ·  ·  11 11 11 11 11 11 11 11 11
       └block┘     └──U──┘  └──U──┘  └──U──┘
```

This family's satisfaction runs THROUGH a notch — the flow has to occupy the cell whose
two flanking neighbours belong to the same target — so a region without one can never be
satisfied however the pieces are placed. Measured: across ~1,800 single-piece layouts the
three notched targets are satisfied 1723, 1700 and 117 times respectively, and the block
**zero** times. Naming it made the objective unreachable, which is exactly what the
compiler reported.

So the weak source is gated on the evidence its own claim needs: **appearance names only
NOTCHED regions.** The stronger sources are untouched — a region the flow was obstructed
by has direct evidence behind it, and this block genuinely does obstruct the flow, which
is why it still enters the shortlist after the commit. idx3 is back to planning against
its three real targets, and idx0–idx2 are unchanged.

What the gate also surfaced is a level-over-level contrast worth stating, because it is
the first structural difference between the levels that clear and the one that does not:

```
idx0  regions of the target colour: (13,4) 5 cells 1 notch · (13,10) 5 cells 1 notch
idx1  (1,3) 5/1 · (1,7) 5/1 · (1,11) 5/1
idx2  (1,1) 5/1 · (1,6) 5/1 · (1,12) 5/1
idx3  (13,2) 4 cells 0 notches · (13,6) 5/1 · (13,9) 5/1 · (13,12) 5/1
```

Every level that clears carries notched targets and nothing else. idx3 is the first to
carry a mouthless block in the target's own colour, and it is the first that does not
clear even with every notched target satisfied. That is a correlation across four levels,
not a proof — but the alternative explanation, that the response table is simply wrong
about notched targets, is contradicted by idx0–idx2 clearing under that same table. The
hypothesis to test next is that the block is a target of a SECOND KIND, satisfied by
something other than a flanked notch.

## `satisfied` holds indices, and I compared it to cells (2026-08-24)

The retracted claim above deserves its own entry, because the shape of the mistake is
one this round has now made three times: **a probe that reads the right field the wrong
way answers confidently and wrongly.** `Prediction.satisfied` is a set of target
INDICES; the probe asked `sink in prediction.satisfied` with `sink` a frozenset of
cells, which is False for every placement ever tried. That produced "no single-piece
placement satisfies any target", a statement that survived into a round page and a
commit message before the next measurement contradicted it.

The earlier two were the same shape: comparing frontier INDICES when the quantity of
interest was the trail, and reading `frame[0]` at a level boundary when the first
layers still show the previous board. The countermeasure that works is cheap — before
trusting a sweep that returns all zeros or all ones, print one element of each side and
check they are the same kind of thing. A uniform answer is a defect signature, not a
finding.

## The forecast was about a board we never built (2026-08-24)

The previous section left idx3 with every notched target predicted satisfied and no
clear, and named the mouthless block as the suspect. Three measurements later the
suspect is cleared and the real defect is mine.

**First: the block IS satisfiable, and the model agrees with the engine about it.**
Reading each target-coloured region's fate after the spill — did the flow enter it, did
it change appearance — gives the engine's own satisfied signal:

```
(13,2)  4 cells  0 notches   entered=False  recoloured=TRUE
(13,6)  5 cells  1 notch     entered=False  recoloured=TRUE
(13,9)  5 cells  1 notch     entered=False  recoloured=False
(13,12) 5 cells  1 notch     entered=False  recoloured=False
```

Two targets satisfied — and the forecast taken on the board as committed says exactly
`satisfied {0, 1}`, which is those same two. So the response table is not wrong here.
(It also means my previous section's "every notched target satisfied and still no clear"
was a claim about a PREDICTION, not about the engine. Corrected: one notched target and
the block were satisfied.)

**Second: the forecast was never about the board that got committed.** Comparing the
board the compiler predicted on against the board at the moment of the commit:

```
pieces: planned {(7,4)…(7,8)} 5 cells   actual {(7,3)…(7,8)} 6 cells   ← merged with a neighbour
        planned {(10,4),(10,5),(10,6)}  actual {(10,6),(10,7),(10,8)}  ← two cells right
```

A piece sits two cells from where the plan put it, and another has come to rest against
its neighbour and is read as one six-cell region. The plan's forecast is a statement
about a specific layout; commit a different one and nothing has been tested.

**Third: my own arrival check could not see it.** It asked whether the intended cells
were a SUBSET of the occupied cells, and a subset test passes while one piece stands in
another's intended place and a merge supplies the rest. It is now exact set equality,
and the drift is reported with both directions (intended-but-empty, occupied-but-
unplanned). A subset test for "did we arrive" is a measurement that cannot fail.

With the exact check in place idx3 reports what is actually blocking it — **a press the
engine refuses while topping a piece up to its planned place.** The compiler's reachable
placements are computed from the measured deltas without regard for the other pieces, and
idx3 is the first level crowded enough (five pieces) for their paths to cross. Making
placement reachability respect occupancy is the next step.

One rejected idea, measured rather than argued: vetoing the commit when the pre-commit
forecast does not win. It looks obviously right and it breaks idx2, whose shortlist is
polluted to **fifteen** targets at that moment by the spill's own flow — and which clears
anyway. The forecast is trustworthy about which targets a layout satisfies; it is not
trustworthy as a veto, because the target list it scores against can be junk.

```
idx0: CLEARED — 19 actions   forecast 2 of 2, wins
idx1: CLEARED — 26 actions   forecast 3 of 3, wins
idx2: CLEARED — 51 actions   forecast 2 of 15, does not win (shortlist polluted)
idx3: the engine refuses a press the plan needs
```

## Pieces block each other, and the order is part of the plan (2026-08-24)

idx3's refused press was traced to the cell it was refused at. The report names the
occupant:

```
press 3 refused; would enter [(7,5)]: piece[(7,5)] target[] hazard[] off-board[]
```

Another piece was standing there. The compiler computes reachable placements from the
measured deltas and the board's static constraints — bounds, row bound, target keep-out
— and says nothing about the other pieces. idx3 is the first level crowded enough
(five pieces) for their paths to cross.

The obvious fix is wrong, and measurably so. Filtering each piece's placements against
where the other pieces stand at entry **broke idx2** (51 actions to clear → no clear):
on that board a blocker moves out of the way first, so a placement that is unreachable
at entry is perfectly reachable by the time the piece is asked to move.

Which is the real shape of it: **whether a path is clear depends on which pieces have
already moved, so the ORDER is part of the plan.** `_order_moves` now takes a chosen
layout and finds an order in which each move can actually be driven — greedily, taking
any piece whose path is clear against where the pieces stand at that moment, repeating
until nothing more can move. A layout no order can realise is not a plan: the compiler
returns nothing for it and keeps searching, rather than emitting steps that cannot run.

Alongside it the driver stopped taking its own plan on faith. **Every planned press is
now checked for landing**, and a press that does not move its piece ends the attempt
with the blocking cell named, because every later press in the path assumes this one
happened. Replanning from the board as it IS beats pressing harder — the refusal is
information the compiler did not have.

```
idx0: CLEARED — 19 actions
idx1: CLEARED — 26 actions
idx2: CLEARED — 51 actions
idx3: planned press 3 does not land; would enter (3,2), held by another piece
```

idx3 is still blocked, and now precisely: the ordering pass admitted a layout whose
press is still refused, so occupancy at execution time differs from what the ordering
assumed. The likeliest reason is on record from earlier in this round — pieces that come
to rest touching are read as ONE region, so the piece the plan names and the piece the
click selects need not be the same. That is the next thread.

## Read the tracked piece off the board (2026-08-24)

The previous section left idx3 with a planned press refused at a cell another piece
held, even though the plan's move order was built to avoid exactly that. Dumping the
board at the moment of the refusal explains it, and the defect is the same one this
round has now named three times.

```
[identity] plan named (7,2) 5 cells, selected (7,5) 1 cells
  r7  12 12 12  9  9  9  9  9  9 12 12 12 12 12 12
```

Six cells wear the selected appearance. `tracked_region()` reported **one**. It was
returning a remembered set maintained by matching translations, and a translation that
was refused — or a piece that has come to rest against a neighbour and is drawn as one
region from then on — leaves that memory describing a piece that is no longer there.
The driver then pressed on that answer, and the ordering pass had reasoned about a
board that did not exist.

The invariant is available on every frame: the engine selects exactly one piece at a
time, so **the region wearing the selected appearance IS the tracked piece.** The query
now reads it, and falls back to the remembered set only when the board genuinely cannot
say. The pin fails on the old behaviour.

That is the third instance, so it is worth stating as a rule rather than a fix: *if a
fact is visible on the current frame, read it there.* Remembering it is a cache, and
every cache in this harness has so far gone stale at exactly the moment it mattered —
the selected/idle appearances, the barrier map, and now the tracked piece.

**Second change: UNKNOWN is not a refutation.** With the tracked region correct, idx3
reached the verifier and stopped on an UNKNOWN whose stated cause is a board the
harness knows is incomplete — two flow sources hidden under pieces, so the replay is
missing flow the engine has. That says the EVIDENCE is short, not the hypothesis. The
walk now stops on CONTRADICTED and proceeds on UNKNOWN with the reason printed, which
keeps the verifier's real power while not throwing away a level over evidence it
already knows it lacks.

```
idx0: CLEARED — 19 actions
idx1: CLEARED — 26 actions
idx2: CLEARED — 51 actions
idx3: planned press 3 does not land; would enter (10,5) — piece[] target[] hazard[]
      off-board[]: NOTHING occupies it
```

idx3's blocker has changed character. The engine now refuses a press into a cell that
is empty by every measured category, so what stops it is a constraint the board model
does not carry — not occupancy, which is the thing the previous section added. Two
sources are known to be hidden under pieces on this level; whether a piece standing on
one can be moved at all is the first thing to test.

## The press was not refused — it was dropped (2026-08-24)

idx3's blocker looked like an unmodelled obstacle: a press refused at a cell holding
no piece, no target, no hazard, no flow, on the board, and painted plain background.
Probing the refused state settles it, and the answer is not geometry at all.

First, the refusal is POSITIONAL, not about the piece: press up, then the same press
left lands. Then the sharper test — repeat the refused press **immediately**, with
nothing in between:

```
press 3 repeated immediately: LANDS
press 3 repeated immediately: LANDS
press 3 repeated immediately: LANDS
```

Three times out of three. The engine occasionally drops a press. It is not an
observation running a frame behind either: the board still showed the piece on its old
cells, so the move had genuinely not happened and repeating it cannot double it.

So a planned press that does not land is retried once, and the retry is checked to have
moved the piece by exactly one delta. With that, **idx3 executes its plan to completion
for the first time** — the exact-layout gate passes, so the board committed IS the board
the forecast was about.

## The unmodelled target absorbs the flow (2026-08-24)

And now the level's real structure is visible. On the committed layout:

```
forecast: 3 of 3 target(s), wins=True        ← our three notched targets
engine:   (13,2)  recoloured   ← the mouthless block: SATISFIED
          (13,6)  recoloured
          (13,9)  recoloured
          (13,12) not recoloured
```

The engine satisfied **three of four** — including the solid block this round earlier
excluded from the shortlist for having no notch. Our board does not carry the block at
all, so our propagation runs flow straight past it; the engine's flow is absorbed there,
and the target downstream never gets its share. That is why the forecast says 3 of 3 and
the level does not clear.

This closes the "second kind of target" question from two sections ago with evidence
rather than correlation: the block IS satisfiable, the engine satisfies it, and our
response table has no rule that ever does. Excluding it from the shortlist was right for
the compiler — a target the model cannot satisfy makes every layout lose — and wrong for
the propagator, which needs it as a flow-absorbing entity whether or not the objective
counts it.

That split is the next step: a region can be an OBSTACLE the flow must be routed around
and a TARGET the objective counts, and idx3 is the first board where those two roles
come apart.

```
idx0: CLEARED — 19 actions
idx1: CLEARED — 26 actions
idx2: CLEARED — 51 actions
idx3: plan executed in full, layout exact, 3 of the engine's 4 targets satisfied
```

## The obstacle role, split from the target role (2026-08-24)

The block that the engine satisfies and no table can is now carried on the board in its
own role. `Board.absorber_cells` swallows a stream that reaches it: no satisfaction, no
hazard contact, no onward flow. Grounding names them exactly like the weak target source
minus the notch — a region wearing the appearance every named target agrees on, with no
notch to be flanked at — so idx3 grounds the 2×2 block and **every earlier level grounds
an empty set** and is untouched.

```
idx0  absorbers []
idx1  absorbers []
idx2  absorbers []
idx3  absorbers [(13,2), (13,3), (14,2), (14,3)]
```

It did not change idx3's outcome, which is itself the finding: with the absorber in
place the forecast still says 3 of 3 and the engine still leaves (13,12) unfilled. So
the stream our model sends past the block was never the one the engine sends to (13,12),
and the divergence is elsewhere. Comparing the two trails cell for cell says where:

```
predicted-only  (6,2) (7,2) (8,2) (9,2) (10,2) (11,2) (12,2) · (12,12) (12,13) (13,13) · (6,9) (8,4)
observed-only   (12,4) (13,4) (14,4)
```

We run a whole stream down **column 2** that the engine never produces, and the engine
runs one down **column 4** that we never predict. The two hidden sources are grounded as
the PAIRS `((3,3),(3,4))` and `((3,8),(3,7))` — a source and the cell beside it — and the
emergence injected into the board is one member of each pair. The engine's flow appearing
in column 4 rather than column 2 or 3 says the injected member is likely the wrong one.
Testing that is cheap and is the next step.

Note what this does NOT say: the absorber is not vindicated by idx3 clearing, because it
did not clear. What is measured is that the role is grounded where it should be, absent
where it should be, and that its presence moved the remaining disagreement into a
different, sharper place.

## An emergence is an observation, and observations do not travel between layouts (2026-08-24)

The previous section guessed that the wrong member of a hidden-source pair was being
injected. That guess was wrong, and the truth is simpler and worse.

`emergences()` reports OBSERVED entries — the cell and tick at which flow appeared —
which is what makes a replay checkable. But the observation is made under the layout the
probing spill ran on, and the plan then MOVES the pieces. Replaying those entries onto
the committed layout is what produced both halves of the disagreement:

```
observed first layers on the committed spill  [(9,5), (9,6)] then [(9,4), (9,7)]
emergences the model injected                 (3,3) (3,8) (7,9)
```

The committed spill enters at **row 9**, spreading symmetrically outward on one row —
the signature of a source under a piece. The model was injecting row-3 entries seen when
the pieces stood somewhere else. So an emergence is now dropped when the piece layout it
was observed under is not the layout being predicted.

Effect: idx0–idx2 are unchanged and still clear. idx3 no longer plans at all —
`UNSATISFIABLE`, because without those entries the model does not know where the flow
comes in for a layout it has not yet seen. That is a worse walk and a better model: it
now fails where its knowledge actually ends instead of predicting confidently from
observations that no longer apply.

The next step is visible in the same measurements. Probing idx3 and moving a piece three
cells with the flow committed either side:

```
entry after the probe layout      [(8,4)]
entry after moving one piece      [(8,4)]
```

The entry does not move with the piece: **the source sits at a fixed board cell**, and
the row-9 entry on the committed layout is what that same source looks like when
something is standing on it. `standing_flow` already grounds (8,4). Modelling "a source
at a fixed cell, emerging past whatever covers it" would let the model predict the entry
for a layout it has never observed — which is exactly what planning requires.

## The entry is fixed; the "hidden sources" are not (2026-08-24)

`scripts/rounds/R98/source_probe.py` commits the spill under a series of layouts on the
same level and records where the flow first appears. On idx3, across five layouts that
move a piece left, left again, right and up:

```
after (no move)  entry [(8,4)]   pieces (3,4)4 (4,9)4 (7,2)5 (8,11)3 (10,9)3
after (3,)       entry [(8,4)]   pieces (3,3)4 …
after (3,3)      entry [(8,4)]   pieces (3,2)4 …
after (4,)       entry [(8,4)]   pieces (3,3)3 …
after (1,)       entry [(8,4)]   pieces — the row-3 piece is gone — then GAME OVER
```

The entry does not move with the pieces. That is the fixed-source claim, measured five
times, and it is what `standing_flow` already grounds.

The same run falsifies something else, though: `hidden_sources()` reports positions that
**move with the piece** — `((3,3),(3,4))`, then `((3,7),(3,6))`, then `((6,5),(6,6))`.
A fixed source would be revealed at the same cells whichever way the piece slides. So
that query is reporting the sighting relative to the current cover, not the source, and
it cannot be used as-is to predict an entry for an unobserved layout. Naming it
"hidden_sources" oversold what it measures.

Two more observations, recorded at the strength they were measured:

* The row-3 piece **shrank from four cells to three and then disappeared, and the game
  ended.** Our own measure says the flow never touched it. Re-probing row 3 directly
  across two commits did NOT reproduce the shrink — the piece stayed four cells while
  moving right — so this is an observation made once and not yet reproduced, not a
  mechanic. It matters because losing a piece ended the run.
* A commit **re-selects a piece**: row 3 reads `8 8 8 8` before the commit and `9 9 9 9`
  after it, i.e. the idle piece is wearing the selected appearance afterwards. This is
  consistent with the re-selection already noted in this round and is why beliefs about
  which piece is selected must be read from the board rather than carried across a
  commit.

The thread continues at the same place: to plan on a layout it has not seen, the model
needs the SOURCE, and what the harness currently has is a sighting. The next step is to
find what stays invariant across these layouts — the entry cell did, so the question is
whether the row-3 entries are a second source whose cover moves, or the same source seen
past a different obstruction.

## There is a second source, and it emits from above onto whatever is under it (2026-08-24)

The "hidden sources" question is settled, and the answer is that there were never any
hidden sources — there is a second SOURCE, and what the harness had been recording was
its interaction with a piece.

The whole spill, layer by layer, on the entry layout:

```
 0: (8,4)          ← the standing source, running down column 4
 2: (9,4)   3: (10,4)   4: (11,4)
 6: (3,3) (3,8) (12,4)  ← two streams BEGIN at row 3, while the first is still falling
 7: (4,3) (4,8) (13,4)
 8: (5,3) (5,8) (14,4)
```

Two streams start at row 3 at tick 6 — sequenced after the first, not with it. Their
cells sat at the flanks of the row-3 piece, which is what made them look like sources
concealed beneath it. Moving that piece two rows DOWN settles it: with the piece at
(5,4)–(5,7) the spill contains **no row-3 flow at all**, and instead:

```
 5: (4,5) (4,6)    ← directly ABOVE the piece, at its middle
 6: (4,4) (4,7)    ← spreading outward along the piece's top
 7: (4,3) (4,8)    ← and off both ends, from where they fall
```

So the second source emits downward into columns 5 and 6, lands on whatever is beneath
it, runs along that surface to its ends, and falls off both sides. The entries we
recorded were the fall-off points, which is why they tracked the piece and why replaying
them onto a moved layout produced flow in the wrong columns.

This is the invariant the model was missing. The source is fixed — in its COLUMNS, not
in the cell where flow becomes visible — and the visible entry is derivable for any
layout from the piece the stream lands on. That is what makes an unobserved layout
predictable, and it is the next thing to ground.

Two corrections it forces on this round's own record:

* `hidden_sources()` is not merely a "sighting" (the previous section's word) — it is a
  fall-off point, and the concealment it names does not exist. The query is misnamed
  and the concept behind it should go.
* The `emergences` the propagator injects are the same fall-off points. Dropping them
  when the layout changes was right; the replacement is not a better sighting but the
  source-plus-surface model above.

## The column is the invariant, and discovering it costs one slide (2026-08-24)

Dropping the covering piece one row at a time turns the second source's behaviour into
a rule, confirmed at two heights:

```
piece at row 4   →  flow appears at (3,5) (3,6)
piece at row 5   →  flow appears at (4,5) (4,6)
```

Always the cell directly ABOVE the obstacle, always the same two columns. So the source
pours down columns 5 and 6 and becomes visible where it lands. The COLUMN is what stays
true across layouts, and unlike an emergence it is derivable for a layout the agent has
never seen: given any placement, the stream lands on whatever is topmost in that column.

`falling_columns()` grounds it from the landing signature — a cell that appears with no
flow behind or beside it while the cell directly ahead is occupied. Measured live, it
returns `(5, 6)` on idx3 and repeats that answer after a further slide.

There is a catch worth stating, because it changes what the agent has to DO. In the
level's own starting layout the query is `UNKNOWN` — on every level:

```
idx0 UNKNOWN   idx1 UNKNOWN   idx2 UNKNOWN   idx3 UNKNOWN
idx3 after sliding the covering piece one row down  →  (5, 6)
```

The reason is that a stream falling onto a piece that is directly beneath it never
travels: it spills off the ends immediately, and fall-off looks nothing like landing.
The column only becomes observable once the cover moves. That makes this a fact the
agent has to go and GET — one selection and one press, then a commit — rather than one
it can read off the opening frame. Discovery here is an action, not an observation, and
the probe phase is where it belongs.

## An unmeasured direction is not neutral (2026-08-24)

Wiring the discovery slide into the walk took three attempts, and each failure was
worth more than the feature.

**Unconditional discovery costs more than it earns.** Sliding a cover during every
probe phase cost idx0 its clear outright and left idx2 with a piece that had no
reachable placement. Putting the cover back fixed the layout but not the evidence — the
verifier then CONTRADICTED on idx0, because the spill it was judging belonged to the
slid layout, not the restored one. Committing once more after the restore fixed that,
and idx0 still failed to clear: three extra actions in the wrong place are enough to
change a level's outcome. So the slide runs **only when the compiler is already stuck
and the columns are still unknown**, and idx0–idx2 return to exactly their previous
action counts.

**And then it did not fire.** The slide needs an action that moves a piece ALONG the
flow, and on idx3 the measured delta table held only up, left and right:

```
[discover] no measured action moves along (1, 0); measured [(1,(-1,0)), (3,(0,-1)), (4,(0,1))]
```

Down exists — the manual probe used it — but the probe phase pressed it once, the press
was dropped, and the direction was recorded as unmeasurable. This round already measured
that the engine drops presses (three times out of three on a repeat), so the delta probe
now retries an unmeasured direction once. That single retry is what an unmeasured
direction is worth: it removes every placement needing that direction from the planner's
reach, and here it also cost the agent the discovery it was trying to run.

```
idx0: CLEARED — 23 actions (was 19)
idx1: CLEARED — 30 actions (was 26)
idx2: CLEARED — 55 actions (was 51)
idx3: plans and executes its plan again — no longer UNSATISFIABLE
```

The four extra actions per level are the retries, and they are a real cost under a
squared-efficiency metric. They buy idx3 the ability to plan at all, which is the right
trade while the model is still being built; a cheaper probe that only retries the
directions a plan actually needs is a later refinement.

## The lane, wired into the model (2026-08-24)

With the down direction finally measured, `falling_columns()` grounds at plan time on
idx3 — `(5, 6)` — and the sequencing comes with it: `falling_sources()` reports
`((5, 3), (6, 3))`, both lanes starting three steps into the spill. The board now
carries them, and the propagator injects each stream at **the cell just short of the
first thing in its lane**, scanning from the edge it falls from.

That is the whole point of a lane over an emergence. An emergence says "flow appeared
HERE"; move a piece and the statement is false. A lane says "flow pours down THIS
column", and where it comes to rest is computed from the layout being predicted — so a
layout the agent has never seen is predictable, which is what planning needs. The test
pins exactly that: the same lane over a piece at row 3 lands at row 2, and over a piece
at row 5 lands at row 4.

Wiring it exposed a latent hole in the propagator. A stream arriving while nothing else
is running was **dropped entirely**: the loop breaks on an empty active set before the
newly-arrived cells are turned into a layer. On every live board another stream was
always mid-fall when these appear, so the bug was invisible until an isolated one was
predicted. An arriving stream now starts running on its own.

All four certifications hold with the changed propagation — oracle 3/3, grounding,
verifier and the frozen mutant table — and the walk is unchanged on the first three
levels:

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: plans WITH the second stream now; a planned press is refused by another piece
```

idx3's failure has moved back to the ordering pass, which is the honest place for it:
the model now knows about the stream it was missing, and what stops the plan is a piece
standing where another piece has to pass.

## A phantom piece, and the inversion it caused (2026-08-24)

idx3's plan kept being refused at a cell the ordering pass believed was free. The
board at that moment says why:

```
r9  12 12  9  9  4  9  9 12 …
[identity] plan named (7,2) 5 cells, selected (8,4) 1 cells
[identity] plan's pieces  (4,4)4 (4,9)4 (9,1)5 (8,11)3 (10,8)3
[identity] board's pieces (4,4)4 (4,9)4 (8,11)3 (9,2)5 (9,4)1 (10,9)3
```

One cell of a stationary five-cell bar renders in colour 4 — the appearance the harness
had learned for a piece IN MOTION. `_bridge` correctly absorbed it and reported the bar
whole, and then the moving-appearance pass reported that same cell AGAIN as a one-cell
piece inside it. Six pieces where the plan had five, and the extra one sitting exactly
where a press had to pass.

It cost a second thing as well. Splitting the bar's own colour into two regions broke
the "worn by exactly one region" test that decides which appearance is selected, so the
harness read **selected 8, idle 9** where the board had it the other way round — the
same inversion this round has now chased three times, arriving by a new route.

Both are one fix each, and both are about not letting segmentation invent entities:

* a region already contained in another is not a second piece;
* the appearance count bridges single foreign cells before counting, so a piece
  carrying one is still one region.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: executes its plan in full; the board now reports the same five pieces the plan does
```

The remaining disagreement on idx3 is smaller than it has ever been — nine predicted
cells the engine never produces, five it produces that we do not:

```
predicted-only  (8,4) (12,5) (13,5) (14,5) (15,5) (15,0) (12,12) (12,13) (13,13)
observed-only   (11,3) (12,3) (12,4) (13,4) (14,4)
```

We route a stream toward column 12–13 and the engine routes it down column 3–4. One
stream, one wrong turn, and it is the same target — (13,12) — that goes unfilled.

## The source travels with the piece that carries it (2026-08-24)

idx3's first divergence was at **step 0**: our model started the spill at (8,4) while
the engine started it at (11,3). The board at that moment explains both:

```
r10  12  8  8  4  8  8 12 12  8  8  8 12 …
```

`(10,3)` is a cell of a piece rendered in its own colour, and the flow starts in the
cell just past it. Earlier in the round the entry looked FIXED — (8,4) across five
probe layouts — but those probes never moved the piece that carries it; when a plan
finally did, the entry moved with it. So this round's "the entry is a fixed board cell"
is corrected: **the source is embedded in a piece and travels with it.**

`embedded_sources()` names those cells — cells inside a piece that do not wear that
piece's appearance, the same ones `_bridge` absorbs so the flow cannot walk through a
bar. The board seeds from them instead of from an observed flow cell, and the observed
cell is used only when no embedded source is known. The result is measurable:

```
before  first divergence at step 0: invented (8,4)  missed (11,3)
after   first divergence at step 1: invented (3,5) (3,6)  missed (12,4)

predicted-only  9 cells → 8      observed-only  5 cells → 3
```

The first stream now starts where the engine starts it, and what is left is the timing
of the falling lanes.

### Two corrections to the previous section

**The bridging-in-count change never applied, and when applied it hurts.** The previous
commit said the appearance count bridges single foreign cells before counting. The edit
silently did not match, so only the phantom-piece drop was in effect — and that is the
one that produced the measured improvement. Applying the count change for real makes
idx3 WORSE: the inventory drops to four pieces from five and the layout drifts by eleven
cells. It is rejected by measurement, not carried as an unverified claim. (A guard for
the case where both appearances are the same colour is kept — that one crashed.)

**The diagnostics were invasive.** `_refusal_probe` PRESSES ACTIONS, so a run under
`R98_DUMP_BOARD=1` drifted where the same run without the dump executed its plan. An
observational dump that changes the thing it observes is worse than no dump. The probe
now lives behind its own `R98_PROBE=1`.

## The block deflects; it does not swallow (2026-08-24)

The lane timing was not the problem — the observed spill puts the lane cells at index 3
and the board injects them at tick 3. The problem was that OUR first stream was shorter
than the engine's, so the compacted comparison shifted everything after it. The engine's
opening steps say why:

```
obs 0: (12,3)   obs 1: (12,4)   obs 2: (13,4)   obs 3: (3,5) (3,6) (14,4)
```

Step 1 is SIDEWAYS. `(13,3)` is the solid block, and the stream steps around it and
carries on down — while the block itself is satisfied. So this round's "absorber"
reading was wrong in its most important part: the block does not swallow the stream, it
**deflects** it exactly as a piece does.

Modelling it that way emptied the observed-only surplus outright — every cell the engine
produces, the model now produces. But deflecting to BOTH flanks invented a stream down
the far side, because that side is blocked by the block's own second column. Adding the
one condition the geometry demands — deflect only to a side whose own way ahead is not
blocked — moved the first divergence from step 1 to **step 12**:

```
before   first divergence step 1   predicted-only 12   observed-only 5
after    first divergence step 12  predicted-only  8   observed-only 0
```

`observed-only` empty is the meaningful half: the model no longer misses anything the
engine does. What is left is over-production — eight cells the model makes that the
engine does not, all of them downstream of step 12.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: executes in full; trail matches the engine for twelve steps
```

All four certifications hold, including the frozen mutant table — the deflection is
board-level behaviour, not a slot in the response table, so it does not disturb what the
model stage measures.

## A one-step shift, and a rule that looked right and was not (2026-08-24)

The remaining idx3 error is entirely surplus and it starts late — every extra cell is
produced at step 18 or after:

```
(12,5) 18  (12,12) 18  (12,13) 19  (13,5) 19  (13,13) 20  (14,5) 20  (15,0) 20  (15,5) 21
```

Laid side by side, the tails are the same trail one step apart:

```
predicted 17: (12,0) (12,6) (12,11)      observed 18: (12,0) (12,6) (12,11)
predicted 18: (12,5) (12,10) (12,12) (13,0)   observed 19: (12,10) (13,0)
```

And the shift has a visible origin at step 12, where a droplet stopped at a piece
produces its LEFT flank while the engine produces left at 12 and right at 13:

```
step 12: predicted (9,7) (9,9) (10,3)  |  observed (9,7) (10,3)
step 13: predicted (9,10) (10,2) …     |  observed (9,9) (10,4) (10,7)
```

The obvious rule — a split emits one side this step and the other next — was implemented
and **measured false**. It costs idx2 its clear outright and produces surplus in BOTH
directions there (34 observed cells missing, 18 invented), where before it had neither.
So whatever staggers idx3's split is not a general property of splitting, and the rule is
rejected rather than tuned until one level agrees.

Reverted; idx0–idx3 are back to their previous behaviour. What this tick adds is the
measurement that localises the disagreement — surplus cells with the step that produced
them, and a tail-by-tail comparison — and one hypothesis struck off with evidence.

## The win rests on flow the engine never makes (2026-08-24)

Naming the targets rather than counting them settles what idx3's surplus actually costs:

```
forecast satisfies   (13,6)  (13,9)  (13,12)
engine satisfied     (13,2)  (13,6)  (13,9)      — (13,12) not recoloured
```

Two agree. The one we claim and the engine does not is exactly the target our surplus
flow reaches: the extra cells are `(12,12) (12,13) (13,13)`, a stream running right along
row 12 and dropping into the mouth of `(13,12)`. The engine's stream reaches `(12,11)`
and goes no further.

So the remaining error is not a tail artifact and not a timing offset — **the model wins
on paper because it produces flow the engine does not.** That is a sharper problem than
"eight surplus cells", and it is the one worth solving: a plan compiled on this model
will keep choosing layouts whose win depends on a stream that will not exist.

The duration hypothesis is ruled out on the way: idx0's spill is 14 steps long across
three consecutive commits, so the engine has no fixed 21-step budget that would explain
the truncation. The engine's row-12 stream stops because of something local at column 11,
not because the spill ran out.

Also fixed here: the attribution named satisfied targets by indexing the CURRENT board's
sink list, while the forecast had been computed on the pre-commit board with a different
list — which printed `(13,2) (13,6) (13,6)`, a duplicate that is not a possible answer.
Indices are only meaningful next to the list they were produced against.

## Three rules for the row-12 stop, all falsified (2026-08-24)

The engine's stream reaches `(12,11)`, turns LEFT to `(12,10)` and drops into the mouth
at `(13,10)`, satisfying `(13,9)`. It never goes right. Ours goes both ways and walks
three cells along the top of the targets into the mouth of `(13,12)` — the one target we
claim and the engine does not. Three rules that would explain the stop were implemented
and measured; all three are wrong.

**1. Spread only toward a side whose way ahead is free** (the condition that fixed the
block). Surplus grew from 8 cells to 23 and the compiler chose a different layout
altogether — further from the engine, not closer.

**2. Spread only toward a side not walled by a target.** Byte-identical outcome to (1):
same 23-cell surplus, same changed plan. The narrower reading buys nothing.

**3. A sink miss spreads ONE way, as the engine appeared to do here.** Contradicted on
idx0 within a single level — the verifier reports four cells the replay misses, so the
engine demonstrably spreads BOTH ways there.

(3) is the useful one: it rules out a whole family of explanations. The stop at `(12,11)`
is not a property of sink-miss spreading, because the same spreading demonstrably goes
both ways on another level. Something about that position on idx3 stops the right-hand
branch, and it is not the geometry the model currently carries.

Everything is reverted; the four levels are unchanged. The tick's product is three
eliminations, which is what the ⛔ list is for.

## A filled target takes no more flow (2026-08-24)

A fourth spreading rule went the way of the first three — "slide toward the notch of the
target you hit" is contradicted on idx0 within one level, six cells missed. But reading
the observation that killed it turned up the rule that works, and it is not about
spreading at all.

The engine's own sequence on idx3:

```
obs 17: (11,0) (11,6) (11,11) (13,7)     ← (13,7) is the NOTCH of target (13,6)
obs 18: (12,0) (12,6) (12,11)            ← a stream arrives on (13,6)'s wall …
obs 19: (12,10) (13,0)                   ← … and simply ends
```

The target was filled at step 17 by a droplet entering its notch. The stream that
arrives on it at step 18 does not spread, does not deflect, does not continue — it ends.
**A target that is already satisfied takes no more flow.**

That single rule accounts for most of what was left:

```
before   predicted 22 steps / 56 cells   surplus 8 cells
after    predicted 21 steps / 52 cells   surplus 4 cells   (observed: 21 / 48)
```

The step counts now match exactly, the whole invented column-5 stream is gone, and the
four cells left are `(12,12) (12,13) (13,13)` — the walk into `(13,12)`'s mouth — plus
`(15,0)`.

All four certifications hold, including the frozen mutant table: the rule is a property
of the board's state during a spill, not a slot in the response table, so what the model
stage measures is untouched. idx0–idx2 clear in the same action counts as before.

The remaining four cells are the same disagreement as before, now isolated: our stream
reaches `(12,11)`, the engine's turns left and fills `(13,9)`, and ours also goes right
along two targets' roofs into a mouth the engine never reaches. Four rules have now been
eliminated for that turn; the fifth candidate is that a droplet on a target's roof is not
free to travel indefinitely.

## Judge a rule against evidence that does not move (2026-08-24)

Four spreading rules were rejected in the last two ticks because re-running the walk
after each change made the numbers worse. That verdict was worthless, and the reason is
structural: **the compiler's choice moves with the model.** Change a propagation rule and
the compiler picks a different layout, so the comparison is a new rule on a new board —
which says nothing about the rule.

`depth_walk.py R98_CAPTURE=<path>` now freezes the board AS COMMITTED together with the
spill the engine produced on it, and `scripts/rounds/R98/rule_bench.py` replays that fixed
evidence under the current propagator. It reproduces the walk's own numbers exactly —
4 invented, 0 missed, first divergence at step 12 — so it is measuring the same thing,
without the moving target.

Re-judged on fixed evidence, the rule rejected last tick is an improvement:

```
baseline                   invented 4  missed 0   satisfies (13,6) (13,9) (13,12)
no chained spread          invented 2  missed 0   satisfies (13,6) (13,9)
roof travel bounded to 1   invented 1  missed 0   satisfies (13,6) (13,9)
```

The satisfied list is the part that matters. The engine filled `(13,2)`, `(13,6)` and
`(13,9)` and left `(13,12)` empty; the baseline claims `(13,12)`, and both variants stop
claiming it. A model that no longer wins on flow the engine does not produce is the point
of this whole thread.

**A droplet produced by a miss does not spread again** is now the rule. All four
certifications hold — oracle 3/3, grounding, verifier, and the frozen mutant table —
and idx0–idx2 clear in the same action counts. idx3 now compiles a different plan (40
actions) and still does not clear, which is the honest result: the model is more
faithful, and faithfulness alone has not yet found a winning layout there.

The bounded-roof variant scores better still (1 invented) and is not adopted in the same
breath: it is a second change to the same rule, and it deserves its own measurement rather
than riding along on this one.

## The source is a CELL, and a covered source emits sideways (2026-08-24)

Capturing a second board and benching both settled what the falling stream really is.
The two boards differ only in where the covering piece stands:

```
a  pieces on row 4   observed  step 3: (3,5) (3,6)   then (3,4) (3,7), (3,3) (3,8), (4,3) (4,8)
b  pieces on row 3   observed  step 4: (3,3)          then (4,3) — and nothing else up there
```

On (a) the stream appears AT `(3,5)` and `(3,6)`. On (b), with a piece standing on those
very cells, it appears at `(3,3)` — beside the piece, on the same row — and never above
it. So the source is a fixed CELL at row 3 in lanes 5 and 6, not an opening at the top of
the board: a covered source emits beside its cover rather than on top of it.

Our model drops the stream from the board's edge and lands it on the first obstacle,
which on (b) puts flow at `(2,5)` and `(2,6)` — a row the engine never uses — and that
single error accounts for the bulk of (b)'s 24 invented cells.

Grounding now records the source's row alongside its lane. The propagator does **not**
enforce it yet, and that is deliberate: clamping the landing to the source's row is only
half the mechanic, and the half without its partner is worse than neither. Measured —
with the clamp alone the second stream simply never appears when a piece covers the
source, and idx3 goes from executing a plan to `UNSATISFIABLE`. The companion rule, emit
beside the cover, is the next change and gets its own measurement.

### A pin was lost and is restored

Rewriting the end of `test_hypothesis_verifier_flow.py` for the absorber test silently
deleted the falling-source pin — the file went from eleven tests to ten while the suite
stayed green, because a deleted test cannot fail. It is restored, with its claim narrowed
to what it actually measures: the landing rule, not the source row, which nothing yet
enforces.

Two lessons this round keeps re-learning in new clothes: **verify a fix is in effect**
(three silent no-match edits so far), and now **verify a test still exists** — a suite
that gets greener by losing coverage looks exactly like a suite that is passing.

## "Emit beside the cover" is right about one cell and wrong about the board (2026-08-24)

The companion rule was implemented — a covered source emits at the nearer free end of the
run that covers it, on its own row — and measured against both captured boards.

```
board a (sources free)     invented 2  missed  0    unchanged: the rule is inert here
board b (sources covered)  invented 5  missed 25    was: invented 24, missed 0
```

It gets the cell right: board b's stream really does appear at `(3,3)`, the closer end of
the run covering lanes 5 and 6, and the model now puts it there instead of a row above the
board's own pieces. But total error goes UP, because the model now produces one stream
where the engine has more. Reading board b's spill from the start shows why:

```
 0: (12,3)   1: (12,4)   2: (13,4)   3: (14,4)
 4: (3,3)    5: (4,3)  …  11: (10,3)  12: (10,4)
13: (7,11) (7,12) (10,2) (10,5)
```

The `(3,3)` stream runs down column 3 to the piece at row 11 and spreads — and at step 13
a THIRD stream begins at `(7,11)` and `(7,12)`, which neither of the two grounded lanes
explains. So the board carries more sources than the harness has found, and modelling the
two it knows more faithfully makes the model produce LESS than the engine rather than the
same.

Reverted. Both boards return to their previous numbers, all four levels are unchanged, and
what the tick establishes is the shape of the remaining gap: it is not a propagation rule
any more, it is missing entities. The next question is what emits at `(7,11)`/`(7,12)` at
step 13, and whether it is a source that only some layouts expose.

## A lane is standing knowledge, and the harness was throwing it away (2026-08-24)

The third stream is found. `(7,11)` and `(7,12)` sit directly above the piece at
`(8,11)` — the landing signature again — and re-grounding after the commit says so
outright:

```
[lanes] after the commit: ((11, 13, 7), (12, 13, 7))
```

Lanes 11 and 12, starting at step 13. But that reading REPLACED lanes 5 and 6 rather than
adding to them, because the query read only the last animation. A lane is a standing
property of the board — the same source pours down it whatever the pieces do — so a lane
learned from one spill is still true at the next. Grounding now accumulates across every
spill and reports all four:

```
((5, 3, 3), (6, 3, 3), (11, 13, 7), (12, 13, 7))
```

Two things fall out of it.

**`falling_columns` and `falling_sources` disagreed.** They answered from separate scans,
one accumulating and one not, so a lane learned earlier was reported by one and forgotten
by the other. The columns query is now derived from the sources query — one scan, one
answer.

**The walk did not act on what a commit taught it.** A plan that executed in full and did
not clear returned without replanning, so knowledge gained by the commit was never used.
It now replans when the source set has grown, which is not a retry of the same plan but
the first plan the model is equipped to make.

On idx3 that produces an honest and unwelcome answer: with all four lanes, the compiler
reports **no satisfiable layout from the position the first commit left it in.** The extra
lanes are provably not the cause — on fixed evidence, two lanes and four lanes score
identically (24 invented, 0 missed, same targets satisfied) — so this is a verdict about
the position, not a fidelity regression. The first commit spent the level.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: plans with four lanes; no winning layout remains after the first commit
```

## The shortlist was making the objective impossible (2026-08-24)

`UNSATISFIABLE` after idx3's first commit turned out not to be about the position at all.
Coordinate descent over the FULL legal option set on that board plateaus at 3 satisfied —
of **five** targets. Listing them says why:

```
(13,2)   4 cells  notches []          ← a solid block; no rule can ever satisfy it
(13,6)   5 cells  notches [(13,7)]
(13,6)   5 cells  notches [(13,7)]    ← the same target, listed twice
(13,9)   5 cells  notches [(13,10)]
(13,12)  5 cells  notches [(13,13)]
```

Two defects, both in the shortlist rather than the board. A region with no notch cannot be
satisfied by any candidate table, so requiring it makes "cover every target" unreachable by
construction — and the compiler had been reporting exactly that, correctly, about an
objective the harness had made impossible. And a region named by two sources at once was
listed twice, so the objective counted one target as two.

Both are fixed where they belong. The notch rule now applies to EVERY source, not just the
weak appearance one — a notchless region is an obstacle and goes to the absorbers — and the
shortlist drops duplicates. On idx3 the compiler plans again instead of declaring the level
lost, and idx0–idx2 clear in the same action counts.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: plans again; a planned press fails to land twice
```

One existing pin had to change with the contract: the oscillating-band test used 1-cell
targets, which have no notch and are therefore no longer shortlisted. Its real claim — the
band must never merge with the targets — is intact, restated with notched targets and a
direct assertion that no band cell is ever named. Changing a test to match a contract change
is legitimate; what is not is changing one to match an outcome, and the distinction is
whether the claim survives the rewrite. This one does.

## A press can CONSUME the piece it moves (2026-08-24)

idx3's remaining blocker is a press that fails to land twice — the retry that reliably
rescues a dropped press does nothing here. The board says why: the piece is not there any
more.

```
[identity] plan named (11,1) 5 cells, selected (11,1) 2 cells
plan's pieces   (3,4)4 (3,8)4 (8,11)3 (10,8)3 (12,0)5
board's pieces  (3,4)4 (3,8)4 (8,11)3 (10,8)3            ← four, not five
```

The full board confirms it: three regions, fourteen cells, where the level began with five
pieces and nineteen. And the counts taken either side of the press pin the moment —
**pieces 4 vs planned 5 immediately after a press that was 5 before it.** The press did not
fail; it consumed the piece it was moving.

This is the second sighting. Earlier in the round a row-3 piece "shrank from four cells to
three and then disappeared, and the game ended", recorded as observed-once-not-reproduced.
It is reproduced now, in a different place and by a different route, so piece loss is real
and the model has no rule for it.

What is NOT yet measured is the cause. The press was a downward move into `(12,1)` and
`(12,2)`, both plain background, with the target row two rows below — so "moved onto a
target" does not explain it, and neither does contact with flow, which the trail does not
show there. That is the next question, and it is worth answering: a plan that unknowingly
destroys its own piece cannot be repaired by better placement.

The driver now checks the inventory against what the plan counts on and replans when it
finds fewer, and the failure note carries both numbers. Noticing a piece is gone costs one
action; pressing on at a ghost costs the level.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: a press consumes the piece it moves; three plans exhausted
```

## A piece survives ONE press along the flow's axis (2026-08-24)

`scripts/rounds/R98/piece_loss_probe.py` drives one piece in one direction, step by step,
printing the inventory each time. On idx3 the answer is unambiguous and reproducible:

```
piece (10,9)  DOWN   step 0: 5 -> 5 pieces      step 1: 5 -> 4    LOST
piece (10,9)  UP     step 0: 5 -> 5 pieces      step 1: 5 -> 4    LOST
piece (4,4)   DOWN   step 0: 5 -> 5 pieces      step 1: 5 -> 4    LOST
piece (4,9)   DOWN   step 0: 5 -> 5 pieces      step 1: 5 -> 4    LOST
piece (10,9)  LEFT   steps 0-3: 5 -> 5 pieces   (no loss)
piece (10,9)  RIGHT  steps 0-3: 5 -> 5 pieces   (no loss)
```

Four pieces, both vertical directions: the FIRST press moves the piece and the SECOND
destroys it. Across the axis, four presses in a row do nothing of the sort. So this is not
a hazard or a collision — **a piece may be moved once along the flow's axis, and a second
press consumes it.** (One piece was lost on its first press in the probe, which fits: the
delta-measuring phase had already spent its move.)

That explains the failures of the last two ticks directly. A plan that places a piece two
rows away is not slow — it is a plan that destroys the piece it is moving, and everything
downstream (the "refused" press, the ghost the driver kept pressing at, the shrinking
inventory) follows from that one unmodelled rule.

Enforcing it in the compiler is NOT adopted here, and the reason is a measurement: limiting
travel along the ROW axis costs idx2 its clear (55 actions to a clear, then no clear at
all). The budget was measured on idx3 alone, and the axis it applies to is the flow's, not
the board's — idx1 runs its flow upward. Applying a level-specific number as a global rule
is exactly the mistake the rule bench exists to prevent, so the mechanic is recorded and
the constraint waits for a measurement that covers every level.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: a second press along the flow's axis consumes the piece
```

## The move budget is per PIECE, per LEVEL — and idx0 has none (2026-08-24)

Last tick's rule was stated too broadly. Running the same probe across every level, along
each level's own flow axis, corrects it:

```
idx0  one piece, driven along the flow   steps 0-4: 1 -> 1 pieces      NO loss
idx1  the piece will not move at all (blocked)                          no loss
idx2  moves one step, then blocked                                      no loss
idx3  step 0 moves · step 1 LOSES the piece                             reproduced
```

On idx0 a piece travels five steps along the flow axis untouched. So "a piece survives one
press along the flow's axis" is not a family rule — it is true of idx3 and false of idx0,
and the constraint the compiler must respect is a per-level quantity, which is exactly why
it was not adopted.

Two refinements the cross-level run also settles:

* **It is a budget, not a consecutive-press effect.** Flow, then cross, then flow still
  loses the piece: the cross press moves it happily and does not restore anything.
* **It is spent by a MOVE, not by a press.** idx3's probe phase presses along the flow
  axis several times and costs nothing, because those presses are blocked where the pieces
  start — which is why the walk still sees five pieces at plan time while this probe loses
  one immediately after deliberately moving it.

That last point is useful: the harness can learn the budget for free, by watching whether
the inventory shrinks after a move it already makes, rather than spending a piece to find
out. Wiring that is the next step; the mechanic is recorded and the constraint still waits
for it.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: a second MOVE along the flow axis consumes the piece — on this level only
```

## The budget is learned from a loss, never guessed (2026-08-24)

The mechanic is now in the model, on the terms the cross-level measurement demanded.

Grounding counts each piece's moves ALONG the flow — per move, never per press, because a
press the board refuses costs nothing — and when a piece that had moved is no longer on the
board, what it survived becomes `move_budget()`. Until a piece is actually lost the query
is `UNKNOWN`, and the compiler applies nothing: guessing a limit is what cost idx2 its clear
two ticks ago, and no level is required to have one.

Live, it learns exactly what the probe measured:

```
after move 0: 5 pieces   budget UNKNOWN
after move 1: 4 pieces   budget 1
```

`_path_to` now refuses a path needing more moves along the flow than the budget allows. On
idx0-idx2 nothing changes — no piece is ever lost there, so no budget exists and the
planner is untouched, and all three clear in the same action counts. On idx3 the compiler
reports **no satisfiable layout within the budget**, which is a truthful answer: a plan
that needs two moves along the flow is not slow, it is a plan that destroys the piece it
moves, and the compiler no longer writes one.

Two implementation traps worth the note. The counter must be read as SURVIVED moves — the
move that spends a piece never lands, so it is never counted, and an off-by-one made the
first measurement report a budget of zero. And the loss must be read from the BOARD: asking
the inventory whether a piece is still there answers with the memory of it, because the
remembered piece survives its own disappearance. That is the fourth time this round that a
remembered value outlived the thing it described.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: plans within the learned budget; no winning layout inside it
```

### The commit that claimed a green suite

That change was committed with "suite 1708 passed" in its message while the suite was
**4 failed, 1704 passed**. The gate log had the failures in it and the line was written
from expectation instead of from the log — the exact failure this round has been
cataloguing all day, committed by the person cataloguing it.

The failures were the compiler tests: their stand-in grounding has no `move_budget`, so
the new call raised `AttributeError` on every plan it makes. Fixed by giving the stub the
honest default — `UNKNOWN`, because a budget is only real once the board has taken a
piece — and the suite is green again. The commit message stands as written; this note is
the correction, because a commit that misreports its own gates is worth more as a record
than as a tidy line.

## Each piece plans within what IT has left (2026-08-24)

The budget is per piece and partly SPENT by the time it is known. It is learned only when
a piece is lost, and by then every survivor has moved too — so the replan after idx3's
first loss was still handing each piece the level's full allowance. `moves_spent()` now
reports what each piece on the board has used, and the compiler plans each one within
`budget − spent`.

idx0–idx2 are untouched (no loss, no budget, nothing to subtract) and clear in the same
action counts. idx3 stays `UNSATISFIABLE`, more tightly than before, which is the honest
consequence: the pieces that moved have nothing left, so the level was decided by the
FIRST plan — the one made while the budget was still unknown.

That is the shape of the remaining problem, and it is not a modelling gap any more. The
agent cannot know the budget before spending a piece, and the plan it makes in ignorance
is the plan that spends it.

**A heuristic that looked free and was not.** Preferring placements that use fewer moves
along the flow — an ordering change, not a constraint, and available without knowing any
budget — costs **idx2 its clear**: reordering changes which layouts the capped search
reaches, and idx2's winner falls outside the cap once the order changes. Reverted. Any
"free" preference that reorders the search is a change to what the search finds, and has
to be measured like one.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: each piece plans within its remainder; the first plan already spent them
```

The same stub broke the same way twice: adding `moves_spent()` to the grounding surface
left the compiler tests' stand-in without it, four tests red. Caught this time by reading
the gate log before writing the commit line rather than after — which is the whole of the
correction from the previous tick, applied. A stand-in for a growing interface is a
maintenance cost the interface has to pay each time it grows.

## A winner exists within the budget — the search was taking the first one (2026-08-24)

The question the last three ticks circled was never asked directly: **is idx3 winnable at
all within one move per piece?** Coordinate descent over exactly the options the budget
allows, from the entry board, answers it:

```
targets 3 | options per piece within one flow move: 39 39 36 42 42
best within one flow move per piece: (3, 0) of 3 targets
```

Three of three satisfied, **zero barrier contacts**. The level is winnable from where it
starts, inside the constraint the board itself imposes. So the problem was never that the
budget makes idx3 impossible.

Winners are not equal, though, and the compiler was returning the first one it met. A
layout that wins with streams still ending on a barrier wins by the parts of the model
least likely to be right; a layout that wins with none has nothing riding on them. The
compiler now keeps the first winner and scans a little further — `WINNER_GRACE` candidates
— taking the best by barrier contact, and returns immediately on a clean one. The option
lists are NOT reordered, because reordering changes what the capped search reaches and
that is precisely what cost idx2 its clear when it was tried last tick.

Measured: every layout the walk now chooses has **zero barrier contacts**, on all four
levels, and idx0–idx2 clear in the same action counts as before.

```
idx0: CLEARED — 23 actions   chosen layout: 0 barrier contacts
idx1: CLEARED — 30 actions   chosen layout: 0 barrier contacts
idx2: CLEARED — 55 actions   chosen layout: 0 barrier contacts
idx3: first plan clean and executed; the engine still disagrees about (13,12)
```

idx3's first plan is now the kind of plan the model is most entitled to believe, and the
engine still does not clear on it. That narrows what is left to the response table on that
one target — which is where the round's remaining four invented cells have been pointing
all along.

## The covered-source rule, retried with everything we now know (2026-08-24)

When "emit beside the cover" was first measured it lost, and the diagnosis at the time was
that the model then produced ONE stream where the engine had more — a third stream that no
grounded lane explained. That third stream is grounded now (lanes 11 and 12, accumulated
across spills), so the rule deserved a second measurement rather than an assumption.

It still loses, and the numbers say precisely how:

```
board a  (sources free)     invented  2  missed  0    unchanged — the rule is inert here
board d  (sources covered)  invented  5  missed 18    was: invented 23, missed 0
```

Twenty-three invented cells become five, and zero missed become eighteen. **Total error is
unchanged**, and the satisfied set gets worse — from `(13,6) (13,9) (13,12)` down to
`(13,6)` alone, where the engine fills three. Trading a wrong stream for a missing one is
not progress, and the extra lanes did not change that.

So the covered-source emission is now measured twice, with and without the lanes that were
supposed to explain the first failure. It is not adopted. What the two measurements
together say is that the model's error on a covered board is not localised to where the
stream STARTS: putting the start in the right place leaves the rest of the spill wrong in
the opposite direction.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: unchanged; the covered-source board remains the model's worst
```

## Beside the cover, and LATE — the half that was missing (2026-08-24)

The layer-by-layer comparison on the covered board shows exactly what the model was doing
wrong, and it was not where the stream starts:

```
 !! 3: predicted (2,5) (2,6) (13,4)   observed (13,4)
 !! 4: predicted (2,4) (2,7) (14,4)   observed (14,4)
 !! 5: predicted (2,3) (2,8)          observed (3,3)
 !! 6: predicted (2,9) (3,3)          observed (4,3)
```

Ours drops the stream from the board's edge onto row 2, walks it along that row and falls
off the left end at `(3,3)` **on step 6**. The engine simply has `(3,3)` **on step 5** and
nothing on row 2 at all. The cell was right in the earlier attempt; the TIMING was not, and
the row-2 walk was pure invention.

The rule that survives measurement is both halves together: a covered source emits at the
nearer free end of the run covering it, **delayed by the distance travelled to get there**
— lane 5's own tick is 3, the free end is two cells away, and the engine emits on step 5.

On identical evidence, with the same lane set:

```
baseline (edge drop)   invented 23  missed 0   satisfies (13,6) (13,9) (13,12)
beside + delay         invented  9  missed 0   satisfies (13,6) (13,9) (13,12)
```

**A correction to the previous two ticks.** Both earlier measurements of "emit beside the
cover" reported `missed 18` and were read as the rule failing. That number came from the
EVIDENCE, not the rule: the board was captured at the first plan, when only two lanes were
grounded, so the whole region fed by lanes 11 and 12 was missing from the model no matter
what the emission rule did. Filling in the lane set the harness had already learned turns
the same comparison into a clean win. A fixed-evidence bench is only as honest as the
evidence, and a board captured before the harness finished learning is a board the model
cannot be judged on.

idx3 now plans and executes again rather than reporting `UNSATISFIABLE`, and learns further
lanes while doing it. idx0–idx2 clear in the same action counts; all four certifications
hold.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: executes in 58 actions and learns three more lanes
```

## The frame is not board (2026-08-24)

Nine invented cells were left on the covered board, and eight of them sat on the last row
or the last column. Those two lines are filled with a single colour that is not the
background — a frame drawn around the play area — and across all three captured boards the
engine's flow enters them **zero times**:

```
a: observed cells on the last row/column: []
c: observed cells on the last row/column: []
d: observed cells on the last row/column: []
```

They are not hazards either: nothing dies at them, and calling them hazards would make
every stream that reaches the bottom fatal. They are simply not board. Grounding now
reports a `playable_size()` that trims the outermost line when the last row AND the last
column are each uniform in the same non-background colour — an edge that merely happens to
be empty is not a frame — and the propagator's own boundary rule handles the rest.

Measured on identical evidence, changing nothing but the board's extent:

```
size 16   invented 9  missed 0   satisfies (13,6) (13,9) (13,12)
size 15   invented 3  missed 0   satisfies (13,6) (13,9) (13,12)
```

No piece and no target lies outside the trimmed board, so nothing real is cut away. idx0–
idx2 clear in the same action counts and all four certifications hold.

The synthetic for this pin needed interior content before it would work: a board that is
uniform apart from its frame resolves at the wrong cell scale, and the trim then reported
3 of a 4-cell grid. That is the scale trap from the start of this round arriving in a test
rather than in the harness.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: three invented cells left on the covered board
```

## What a level spends is DISPLACEMENT, not moves (2026-08-24)

The move budget was recorded as a count, and the count is wrong. Driving one piece three
different ways from the same start:

```
up, down, up   survives all three moves
up, up         taken on the second
down, down     taken on the second
```

A piece may sit **one cell off the line it started on**. Going out spends the allowance
and coming back restores it — three moves cost nothing if they end where two of them
cancel. Counting moves called the surviving sequence a double spend and would have
forbidden a plan the board allows.

Grounding now tracks each piece's displacement from its own starting line rather than its
number of moves, and `moves_spent()` reports that:

```
after (-1,0): displacement 1
after ( 1,0): displacement 0
after (-1,0): displacement 1
```

One trap inside the fix, worth its own line: the origin has to belong to the piece that
MOVED. Taking it from whichever piece happened to be tracked before measured a
displacement of seven where the truth was one — the same class of error as every other
remembered value this round, in a new place.

The compiler's constraint is unchanged in form and now correct in meaning: a straight path
of N steps along the flow displaces by N, so `budget − spent` is an allowance in cells.
idx0–idx2 clear in the same action counts, all four certifications hold, and idx3 still
stops on a press the engine refuses into empty cells.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: a planned press is refused into four background cells, twice
```

## Two drops in a row, and a check that ran too early (2026-08-24)

idx3's refused press turned out not to be refused at all. Probing at the exact point where
the driver gave up:

```
[refusal] press 2 repeated immediately: LANDS
```

The press the driver had already retried once landed on the very next attempt. Drops come
in twos here, so a press the board appears to have swallowed is now repeated while the
piece is still where it was, up to `PRESS_RETRIES` times — in the plan's own path and in
the top-up alike. Repeating is safe precisely because the board still shows the piece
unmoved; there is nothing to double.

That carried idx3 past the refusal and into a layout drift, which was two separate things:

```
[drift] intended-but-empty []                          occupied-but-unplanned [(4,8)]
[drift] intended-but-empty [(9,1)…(9,5)]               occupied-but-unplanned [(10,1)…(10,5)]
```

The first is one extra cell — a piece resting against a neighbour is segmented with one
cell more, which is rendering, not misplacement. The second is a five-cell piece one row
short, which is exactly what the top-up exists to fix — and the check was running BEFORE
the last top-up, so it threw the plan away instead of letting the top-up finish. The check
now runs after it, and tolerates one cell of segmentation slack.

idx3 executes its plan in full and learns five more lanes while doing it. idx0–idx2 clear
in the same action counts.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: plan executed in 54 actions; learns five more lanes; does not clear
```

## The last stale sighting (2026-08-24)

With execution healthy, the first divergence on the committed board was at **step 0**:

```
predicted [(8,4)]   observed [(3,5), (3,6)]
```

We open the spill at `(8,4)` and the engine opens it at its two lane cells. Reading the
captured board says why:

```
emitters: []            standing: [(8,4)]
```

No embedded source was found on this layout — the piece carrying it has changed shape and
position — so the board fell back to an observed flow cell, and that cell belongs to a
spill watched on a different layout. It is the same mistake as replaying an emergence, in
the one slot that had not yet been guarded.

`standing_flow` now falls back to a sighting only while the pieces still stand where that
sighting was made. Measured on the same level, re-captured:

```
before   predicted 23 steps / 69 cells   invented 20+   first divergence step 0
after    predicted 20 steps / 58 cells   invented 14    first divergence step 3
```

Three cells go from matching to missed in the trade, and fourteen invented remain, but the
opening now agrees with the engine and the disagreement has moved three steps later into
the spill.

That is every observation-shaped slot on the board accounted for: emergences, the lane
ticks, the tracked piece, the selected appearance, the barrier map, and now the standing
flow. Each one was a value the harness remembered past the moment it described.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: executes in 54 actions; the spill now opens where the engine opens it
```

## Each stream leaves its perch at the NEARER end (2026-08-24)

With the opening now correct, the mid-spill disagreement on idx3 is one invented stream.
The layer comparison isolates it:

```
    2: predicted (3,8) (4,4)      observed (3,8) (4,4)
 !! 3: predicted (3,9) (5,4)      observed (5,4)
 !! 4: predicted (4,9) (6,4)      observed (6,4)
```

Both agree through `(3,8)`. Then ours steps to `(3,9)`, falls off the piece's right end and
runs a whole stream down the right of the board — `(4,9) (5,9) (5,8) (5,10) (5,7) (5,11)
(5,12) (6,12) (7,12)` — none of which the engine produces. Nothing occupies `(3,9)` or
`(4,9)`; the engine's right-going spread simply stops at the piece's edge while its
left-going one drops and carries on.

Two boards of the same level fix the rule between them:

```
board a   piece spans 4..7, sources at 5 and 6   BOTH ends drop
board g   piece spans 5..8, sources at 5 and 6   only the LEFT drops
```

On (a) source 5's nearer end is the left and source 6's is the right, so each takes its own
and both sides fall. On (g) both sources are nearer the left, and only the left falls. So
**a stream resting on a piece leaves it at the nearer end of that piece** — the same
"nearer end" the covered-source emission already uses, now recognised as the general shape.

**The implementation that follows from it is not the obvious one.** Replacing the landing
cell with the fall-off cell scores WORSE: it loses the cells along the piece's top, which
the engine does produce — board a goes from nothing missed to missing `(3,4) (3,5) (3,6)
(3,7)`. The stream spreads along the top AND leaves at one end; the rule belongs on the
spreading side, not on the injection. Reverted, with the rule recorded and the wrong place
to put it recorded too.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: one invented stream, off the far end of a piece the engine never leaves that way
```

## The rule needs per-droplet state, and a cell set is not that (2026-08-24)

"Leaves at the nearer end" was implemented where the previous tick said it belonged — on
the spreading side, marking the droplets that walk toward a piece's FAR end so they lay
their cells but never fall off. Measured on both boards:

```
board g   invented 14 -> 6     (the invented right-side stream is gone)
board a   invented  2 -> 1  but missed 0 -> 7
```

g improves and a breaks, and the reason is the mark itself. The flag lives on CELLS, and
two streams share cells: source 5's walk right marks `(3,6)` as far-side — and `(3,6)` is
where source 6 LANDS. Source 6 inherits a restriction that belongs to another stream, its
whole right-hand branch dies, and board a loses seven cells it had matched.

Exempting landing cells recovers part of it (`a` 8 cells of error instead of 15) but not
all: the flag still leaks wherever two walks cross, and a is a level the walk CLEARS, so a
regression there is not a trade worth making.

Reverted. What the two attempts establish together is the shape of the fix: **the
restriction belongs to a droplet, not to a cell.** The propagator carries active droplets
as `(cell, direction)` pairs, and this rule needs a third component — where the walk began
— which is a change to the propagator's own representation rather than another condition
bolted onto the spread. That is the next step, and it is worth doing properly.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: unchanged; the invented far-end stream is understood but not yet removable
```

## Per-droplet state, and the rule still does not hold (2026-08-24)

The propagator's droplets now carried a third component — `(cell, direction, may_drop)` —
so "leaves at the nearer end" could travel with a droplet instead of with a cell. The
representation change alone is inert: identical numbers on both boards, which is the right
sanity check before hanging a rule on it.

With the rule hung on it, the result is the same as the cell-flag version:

```
board a   invented 2, missed 0   ->   invented 1, missed 7
board g   invented 14            ->   invented 6
```

So the leak was never the problem. Board a's losses are not the row-3 fall-offs the rule
was derived from — they are mid-board cells, `(11,6) (12,6) (12,10) (12,11) (13,10)
(10,11) (11,11)` — which means the rule is killing a branch the engine keeps, somewhere
the two-board evidence never looked.

**The rule is not adoptable.** It was read off the landing row of two boards and it
describes that row well; applied to every piece a stream meets, it is an
over-generalisation, and a is a level the walk clears. Both the rule and the representation
are reverted — an inert third component with no rule using it is scaffolding, and this
round does not keep scaffolding.

What survives is the negative result, which is worth as much as the rule would have been:
the nearer-end behaviour is real on the landing row and false as a general property of
piece encounters. Whatever governs the far-end fall-off distinguishes the landing row from
the rest, and no measurement so far says what.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: unchanged
```

## A landing stream walks two cells, and no further (2026-08-24)

Tabulating every captured board of the level — where the stream lands, which piece it
rests on, and which overhangs actually fall — turns the puzzle into a number:

```
board   landing row   piece span   cells walked on that row   overhang   fell
a       3             (4, 12)      3 4 5 6 7 8                3          3
f, g    3             (5,  8)      4 5 6 7 8                  4          4
b..e    7             (11, 13)     10 11 12 13 14             10, 14     10, 14
```

Every one of them is the same rule: **a stream that comes to rest on a piece walks at most
two cells each way from where it landed**, and falls off wherever that walk carries it past
the piece's end. On board a the landings sit two cells from the left end and the left
overhang drops while the right end is never reached; on g both landings are nearer the left
and the right end is out of reach; on b–e the piece is narrow enough that both ends are.

The reach binds only streams that LANDED from a falling source, and that distinction is
measured, not assumed: capping every piece encounter at two cuts long walks the engine
plainly performs deeper in the board, costing every board cells it had matched.

Across all eight boards, with and without:

```
a  2 -> 2      b  30 -> 30    c  30 -> 30    d  23 -> 23
e  9 -> 9      f  22 -> 22    g  17 -> 14    stuck 10 -> 10
```

Seven identical, one better, none worse — which is the bar a rule has to clear here. The
pin fails without the reach, walking the full width of the piece.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: executes in 54 actions; the invented far-end stream is gone
```

## A source that starts in mid-air (2026-08-24)

With the far-end stream gone, what is left on the covered board is mostly MISSED — flow the
engine makes that the model does not. It is a single stream, and the layers place it:

```
   6: predicted (7,3) (7,5)     observed (7,3) (7,5)
!! 7: predicted (7,2) (7,6)     observed (6,7) (7,2)
!! 8: predicted (7,1) (8,6)     observed (7,1) (7,7)
```

Ours carries on rightward along row 7; the engine's appears at `(6,7)` — a row ABOVE — and
descends column 7 from there. Nothing precedes it: it is a source, and no grounded lane
explains it.

The reason grounding could not see it is the landing signature. A lane was only recognised
where the flow came to REST on something, and `(6,7)` has a free cell below it — the stream
starts in mid-air and falls straight away. The landing requirement was there to keep
fall-off points out of the lane list, and it turns out to be redundant: a fall-off always
has flow BESIDE it, which the flank test already excludes. Removing it, grounding learns
`lane 7 at row 6` on the covered board, exactly the stream that was missing.

Measured by hand on the same board before changing anything:

```
as grounded                  invented 5  missed  9  (total 14)
plus lane 7 at row 6         invented 2  missed 10  (total 12)
```

idx0–idx2 clear in the same action counts and all four certifications hold.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: learns lane 7 at row 6 — the stream the landing signature could not see
```

One pin had to widen with the contract: a synthetic asserted the lane list was exactly
`(4,)`, and the plain descending stream it uses to fix the flow direction is now grounded
as a source too — correctly, since it appears with nothing behind or beside it. The
assertion checks the landing column is present and states why column 0 belongs there.

## An embedded source is not a lane (2026-08-24)

Dropping the landing requirement found the mid-air source and admitted two false lanes with
it. On a fresh capture the model opened at `(8,6)` where the engine opens at its lane cells,
and the arithmetic is unambiguous:

```
all 7 grounded lanes    invented 14  missed  3   (total 17)
without lanes 3 and 4   invented  2  missed 10   (total 12)
```

Lanes 3 and 4 are not lanes. Lane 4's entry sits at `(8,4)` with the cell BEHIND it a piece
— it is the output of a source EMBEDDED in that piece, the same thing this round measured
travelling with its carrier. Grounded as a lane it keeps pouring into a column the piece has
since left.

Repetition does not separate them: on the probe layout lanes 4, 5 and 6 each appear in all
three spills. What separates them is what lies behind the entry, so an entry whose
predecessor cell was a piece at that moment is no longer taken as a lane.

Measured on the covered board, captured fresh:

```
before  invented 14, missed  3   (total 17)
after   invented  2, missed 10   (total 12)
```

The ten missed are the lane-7 stream, which this run learns only after the plan is made —
the same "the commit teaches what the plan needed" shape as the lanes before it. idx0–idx2
clear in the same action counts.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: total error 17 -> 12 on the covered board
```

## A source starts where it is, not where it stops (2026-08-24)

Ten of the twelve cells left on the covered board were a stream the model already knew
about. Tracing the engine's own trail near that column:

```
 7: (6,7)    8: (7,7)    9: (8,7)   11: (9,7)   13: (11,7)   16: (13,7)
```

`(6,7)` is the lane-7 source and the engine renders every step of its descent. The model
injected it at the cell the stream comes to REST on — the landing computation written when
sources were thought to pour in from off the board — so the whole fall was skipped and only
its final cell contributed. An uncovered source now starts at its own cell and falls from
there.

```
board k   total error 12 -> 8      every other board unchanged
```

Two pins moved with the contract, and one of them taught something. The reach — how far a
landing stream walks along its piece — was attached to the injected droplet, so with the
injection moved to the source the reach no longer bound anything. Carrying it down the fall
looks like the obvious repair and is **measured worse**: b and c go 30 → 35, g and h 14 →
18, k 8 → 10. So the reach belongs to a source that comes to rest DIRECTLY on a piece, not
to everything descended from one, and the pin now says so.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: the covered board is down to eight cells of disagreement
```

## The last eight cells, placed — and one more rule struck off (2026-08-24)

The covered board's remaining disagreement is small enough to read cell by cell:

```
 !!  7: predicted (7,2) (7,6)            observed (6,7) (7,2)
 !!  8: predicted (6,7) (7,1) (8,6)      observed (7,1) (7,7)
 !! 10: predicted (8,7) (10,6)           observed (9,5) (9,6)
 !! 11: predicted (9,7) (11,6)           observed (9,4) (9,7) (10,6) …
```

Two facts, both narrow:

* **The lane-7 stream runs one step late.** The engine opens it at step 7 and the model at
  step 8; from there the two descend column 7 in lockstep, one apart.
* **Our row-7 walk goes RIGHT and the engine's goes LEFT.** At `(7,5)` — the right end of
  the piece below — we step to `(7,6)` and fall, giving `(8,6)` and the column-6 stream.
  The engine never has `(7,6)`: its walk runs left to `(7,0)` and stops, and its column-6
  flow arrives later, from a row-9 spread we do not produce (`(9,3) (9,4) (9,5)`).

The obvious reading — that a walker never falls off the end it reaches — is **measured and
false**, comprehensively:

```
a 2->38   b 30->33   c 30->33   d 23->28   e 9->23   f 22->36
g 14->37  h 14->37   i 17->30   j 17->30   k 8->29   stuck 10->29
sum 196 -> 383
```

Falling off the end is not the exception, it is the rule; board k's row-7 branch is the
exception, and what makes it one is still unnamed. Four rules have now been struck off
around this same behaviour (side-conditions on spreading, one-sided sink miss, notch-seeking,
walkers-never-fall), which is worth as much as the list of what does work.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: eight cells, both causes located, neither yet explained
```

## The source that rides inside a piece, and why shape is not enough (2026-08-24)

Reading the covered board's whole spill places the last missing stream exactly:

```
 9: (7,0) (8,7)
10: (9,5) (9,6)        <- appear together, with nothing above either of them
11: (9,4) (9,7) (10,6)
12: (9,3) (10,7) (11,6)
```

`(9,5)` and `(9,6)` have the row-8 bar directly above them and no flow anywhere adjacent.
They are a source PAIR emitting from inside that bar — the same "embedded source" this round
measured travelling with its carrier, in a place the colour-based detector cannot see it
because the bar is drawn uniformly.

The lane rule excludes exactly these entries (an entry whose cell behind was a piece), which
stops the false fixed-lane injection and throws the real flow away with it. So the trail's
own evidence was recorded instead — the carrier's SHAPE plus the offset of the source within
it — and replayed onto whichever piece wears that shape.

**Measured on the same board, that is worse, not better:**

```
with carried sources    invented 11  missed 3   (total 14)
without                 invented  5  missed 3   (total  8)
```

The emitters it produces are `(4,8)` and `(6,11)` — cells inside two OTHER pieces that
happen to share the shape. A shape is not an identity: this level has several pieces of the
same footprint, and attaching a learned source to all of them pours flow from three places
where the engine pours from one.

Reverted. What stands is the localisation — the last missing stream is a source riding
inside the row-8 bar — and the constraint on any fix: the carrier has to be identified as a
PIECE, not as a shape, which the harness cannot currently do across a move.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: eight cells; the missing stream's source is named, its carrier is not
```

## Carrying the source by identity does not help either (2026-08-24)

The last tick's objection to shape-matching was that a shape is not an identity, and the
harness does have one: its move records follow a specific piece across its own moves. So the
carried source was re-recorded against the carrier's CELLS and migrated with it — the same
mechanism that follows a piece's displacement budget.

Measured on the same board, that is worse too:

```
with the carried source   invented 14  missed 3   (total 17)
without                   invented  5  missed 3   (total  8)
```

The single emitter it learns is `(6,11)`, inside the row-6 piece — not the row-8 bar the
missing stream actually comes from — and injecting it adds nine cells the engine never
produces. So identity was not the obstacle: the entries excluded as "behind is a piece" are
not, as a class, sources that emit on every spill, and re-injecting them under the current
emission model costs more than the stream they were meant to recover.

Two attempts now, by shape and by identity, both measured worse and both reverted. The
missing `(9,5) (9,6)` pair stays unexplained, and the useful residue is a boundary: whatever
emits it does not emit every time, so a rule that pours from it on every commit is wrong
before it starts.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: eight cells, unchanged
```

## The reach starts where the source rests, measured three ways (2026-08-24)

A third placement for the walk budget: start it at the first piece a droplet RESTS on,
whatever brought it there — narrower than propagating it down the fall, broader than binding
it to injected landings only.

```
a  2->14   b 30->35   c 30->35   d 23->30   e  9->16   f 22->21   g 14->16
h 14->16   i 17->10   j 17->10   k  8->10   l 14->19   m 17->18   stuck 10->19
sum 227 -> 269
```

Two boards improve (i and j, 17 → 10) and nine get worse; the sum is clearly worse. So the
reach belongs where it is: to a source that comes to rest DIRECTLY on a piece, and to
nothing descended from one. Three placements measured, one adopted, and the two rejected
are on the record because the adopted one looks arbitrary without them.

### Where the round's propagation model stands

The covered board — the hardest of the fourteen captured — is at **8 cells of disagreement
out of 47 observed**, five invented and three missed, with the opening, the sequencing and
every source but one reproduced exactly. Six candidate rules have been struck off around the
remaining two causes:

* side-conditions on spreading (twice: free-side, target-walled)
* a one-sided sink miss (contradicted on idx0 outright)
* notch-seeking on a miss
* walkers never falling off the end (196 → 383, comprehensively false)
* carrying a source with its piece, by shape and by identity (8 → 14, 8 → 17)

What is left needs evidence the harness cannot currently get: whatever emits `(9,5) (9,6)`
does not emit on every spill, and whatever stops the engine's row-7 walk going right leaves
no trace in any board field the harness reads. Both are conditional behaviours, and the
round's instrument — a spill per commit — samples one condition at a time.

## One variable at a time, and the embedded source holds up (2026-08-24)

`scripts/rounds/R98/condition_probe.py` changes a single thing between two spills — one
piece, one cell — so a difference in the trail belongs to that cell and not to whatever else
two captured boards failed to share. Moving one piece one cell right on idx3:

```
baseline           piece (7,2) 5 cells    walk on row 6: 1..8   fall-offs row 7: 1, 7, 8
                   downstream streams in columns 1, 4, 7, 8
moved right        piece (7,3) 5 cells    walk on row 6: 2..8   fall-offs row 7: 2, 8
                   downstream streams in columns 2, 5, 8
```

Every fall-off column shifts exactly with the piece, and so does the middle stream — 4 → 5.
That stream is the embedded source riding inside the piece, and the first layers say it
plainly: the spill opens at `(8,4)` in the baseline and `(8,5)` after the move, one cell
below the piece each time.

**And the model gets both right:**

```
baseline      emitters ((7,4),)   ->  spill opens (8,4)   observed (8,4)
moved right   emitters ((7,5),)   ->  spill opens (8,5)   observed (8,5)
```

So the embedded-source model — a source carried inside a piece, emitting just past it, moving
when the piece moves — is confirmed by a probe that varies one thing. That matters for what
is left: on the covered board the same query returns NOTHING, and this measurement says the
gap there is a DETECTION failure, not a modelling one. The carrier's odd cell is visible on
this layout and invisible on that one, and finding out why is a question about appearances
rather than about mechanics.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: eight cells; the embedded-source model is confirmed, its detection is the gap
```

## The carrier renders uniformly, and two sources shared a column (2026-08-24)

The appearance question has a flat answer. Capturing the board's colours alongside its
geometry — the capture now carries them — and reading each piece's interior on the covered
board:

```
piece (4,5)  4 cells: colours 9 9 9 9
piece (6,8)  4 cells: colours 8 8 8 8
piece (8,0)  6 cells: colours 8 8 8 8 8 8
piece (8,11) 3 cells: colours 8 8 8
piece (10,3) 3 cells: colours 8 8 8
```

Every piece is uniform. There is no odd cell to find, so appearance-based detection cannot
work there **by measurement, not by weakness** — the source's only trace is the flow it makes.

Classifying every sourceless entry on that board then turns up something better:

```
entry step  0  (3,5)   free behind
entry step  0  (3,6)   free behind
entry step  7  (6,7)   free behind
entry step 10  (9,5)   PIECE behind
entry step 10  (9,6)   free behind
entry step 11  (7,11)  PIECE behind
entry step 11  (7,12)  free behind
```

Each pair straddles a piece's edge: one member has the piece behind it and the other does
not. So `(9,6)` was grounded as a lane in column 6 — and the lane list was keyed by COLUMN,
where a source at row 3 already sat. One silently replaced the other and the model poured
from whichever was seen last.

Keyed by (column, row) instead, both are held: the covered board now grounds `(6,0,3)` and
`(6,10,9)` together. Every previously captured board keeps its score and the two fresh
captures sit at **8 cells**, the best measured for that board. The pin fails when the key is
collapsed back to the column.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: two stacked sources in one column are both kept
```

## Timing the pair fixes what is missing and over-produces instead (2026-08-24)

The pairs straddling a piece's edge are the same mechanic as the confirmed embedded source —
a carrier that renders uniformly, so only its flow betrays it. The earlier attempts injected
it at tick 0; an embedded source has a TICK, like a lane. Injecting the pair at the step the
engine shows it:

```
baseline                        invented  5  missed 3   (total  8)
emitting at tick 0              invented 21  missed 0   (total 21)
the pair at its observed tick   invented 12  missed 0   (total 12)
as a source rather than an
emergence (so the reach binds)  invented 12  missed 0   (total 12)
```

Timing removes **every missed cell** — the stream is real and the model can produce it — and
adds seven of its own:

```
(7,6) (8,6)                              the old row-7 right-walk
(9,2) (10,2) (11,2) (12,1) (12,2)
(13,1) (14,1)                            a column-2 descent the engine never makes
(12,5) (13,5) (14,5)
```

Net worse, so not adopted. But the shape of the surplus is informative: the engine's row-9
spread runs `(9,3) (9,4) (9,5) (9,6) (9,7)` — exactly two cells each way from the injection —
and ours continues to `(9,2)` and descends. Two cells each way is the walk reach already
measured and adopted, and injecting the pair as a source rather than an emergence does not
make it bind, which means the reach is not reaching the injected droplet by the path it
travels.

That is a mechanism question inside the propagator rather than another candidate rule, and it
is the first time this thread has produced one.

A second measurement from the same probe, worth its line: moving the piece at `(8,11)` one
cell right changes the trail **not at all** — every row identical. Not every piece
participates, and knowing which do not is how the one-variable probe earns its actions.

```
idx0: CLEARED — 23 actions
idx1: CLEARED — 30 actions
idx2: CLEARED — 55 actions
idx3: eight cells; the missing stream is producible, the surplus is a reach that does not bind
```

## An arriving source was rendered once and then frozen (2026-08-24)

Timing the pair produced the flow but over-ran it, and the surplus was a spread going two
cells past the adopted reach. That reach is not another rule to tune — it is the propagator's
own, so the question was mechanical: how does an injected cell become a moving droplet?

It does not. `active` is rebuilt from `nxt` each step, and an emerged cell was only ever put
into `born` (what gets drawn). The one place it reached `active` was the `if not active:`
branch — nothing else flowing. So a source that arrives while another stream is still falling
is drawn on its own cell and then never moves again, and the cells attributed to it downstream
came from whatever else happened to pass by.

Putting emerged cells into `nxt` — appear this step, travel from the next, `walked = 0` when
the cell is a landing — is what the surrounding code already says it does. Scored over every
captured board, replaying fixed evidence:

```
a 2->2   b 30->30  c 30->30  d 23->23  e  9->9   f 22->19  g 14->14  h 14->14
i 17->8  j 17->8   k  8->8   l 14->12  m 17->8   n  8->8   o  8->8   stuck 10->10
                                                                    sum 243 -> 211
```

Six boards improve, none gets worse, and the three that fall 17 -> 8 land exactly on the error
of the board this thread has been measuring. The fix is upstream of every rule tried against
these boards for the last several ticks: those rules were being scored against a propagator
that dropped its second source.


## Correction: the mechanism was the reach, not a frozen source (2026-08-24)

The previous entry claimed an arriving source "was rendered once and then frozen" — that an
emerged cell never entered the next active set. **That is false, and the commit that carried
it is wrong on its cause.** A loop at the bottom of the step already appended every emerged
cell to `nxt`; it predates the change. Reading the top of the step and stopping there is what
produced the story.

What the change actually did was append a SECOND copy carrying `walked = 0`, which then won
the race for the cells ahead because it was processed first. The improvement was real; the
account of it was not, and the form was order-dependent by accident.

Rewriting it as the one thing it turns out to be — a landing cell starts a BOUNDED walk
instead of an unlimited one — scores identically, which is what makes the mechanism rather
than the duplicate the cause:

```
before the change      243
duplicate entry        211
one explicit entry     211
```

So the adopted rule is: an emerged cell that is a landing enters the frontier with `walked = 0`.
Unlimited was worth 32 cells across the boards — the arriving stream walked as far as the board
allowed instead of the two cells the engine gives it.

Recorded because this is the second time in this round a green measurement carried a wrong
explanation. The number was reproducible; the sentence next to it was not measured. **Where a
fix touches one end of a loop, read the other end before naming the cause.**

## Two thirds of the residual is evidence poverty, not model error (2026-08-24)

Splitting the remaining error by board shows the misses track how many sources the grounding
found, not how hard the board is:

```
board  invented  missed   grounded sources
b             5      25   2   missed cells sit in lanes 7..14; grounding knows lanes 5,6
c             5      25   2
d             5      18   2   missed cells sit in lanes 10..14; grounding knows lanes 5,6
i,j,k,m,n,o   5       3   4..7
```

b, c and d are captures taken before enough spills accumulated, and 83 of the 211 total is
flow from lanes the model was never told about. Scoring a physics rule against that sum charges
it for evidence it never had. The bench should report those boards apart from the rest.

What IS uniform is the invented set: `(12,5) (13,5) (14,5)` appears on every board. On board o
the engine's column-5 stream shows at rows 3, 7 and 9 and stops — row 10 holds a piece — and
spreads along row 9 instead, which is exactly the `(9,3) (9,4) (9,5)` we miss. Our model passes
the blocker and resumes below it. One mechanism, present everywhere, and the next thing to
measure.


## A third of the bench's error was never propagation (2026-08-24)

Splitting the residual by board showed the misses tracking how many sources the grounding
held, not how hard the board is — b, c and d carry 2 grounded sources while their missed
cells sit in lanes 7..14. Re-running the grounding's own scan over each capture's spill
says why, and it is not the exclusion rule:

```
frozen falling: [(5,3,3), (6,3,3), (7,11,6), (12,15,7)]
rescan kept   : [(5,0,3), (6,0,3), (7,7,6), (6,10,9), (12,11,7)]
```

The scan admits `(6,10,9)` — the source at (9,6) — and the capture does not. **The frozen
sources predate the spill being scored.** At runtime that is exactly right: you cannot
plan a commit using the spill that commit has not produced yet. But it means the bench was
charging propagation rules for evidence that did not exist at prediction time.

So `rule_bench.py --all` now reports two totals:

```
board     as-known  physics        as-known  what the agent predicts with; dominated by
b               30       10                  evidence TIMING, not by the rules
d               23        9        physics   the same boards with the sources the scan
f               19       13                  admits from the spill itself, unioned onto
g,h             14        8                  what was already known
sum            211      139
```

No board is worse under the union and six are much better. **Judge a propagation rule on
the physics column.** The 72-cell gap is the cost of predicting before observing, and it
belongs to the walk's grounding cadence, not to the propagator.

Also measured and NOT adopted: injecting every co-occurring missed pair as a source at its
observed tick takes 211 to 159. That reads the answer, so it is a diagnostic only — but it
confirms by construction that b/c/d's error is missing sources rather than wrong physics.

Board o's geometry, for the record: the pieces are horizontal bars, flow walks the top of
one and falls off its edge, and `(7,11,6)` grounds as a real source at (6,7) — so the
column-7 descent is a source, not a walk product. The uniform invented tail `(12,5) (13,5)
(14,5)` remains, and is now measurable against a number that isn't drowning in evidence
timing.


## Half a source is worse than none (2026-08-24)

With the physics column to judge on, board o's remaining misses are `(9,3) (9,4) (9,5)` —
and they are not a physics gap at all. `(9,5)` sits over the piece at row 10, so its flow
is blocked below and walks left, exactly two cells, which is the reach already adopted.
Give the model that source and it reproduces the row.

It never gets it. The grounding drops an entry whose behind-cell is a piece, as the output
of a source EMBEDDED in that piece — a rule measured earlier and worth five wrong cells on
the covered board. Here it cuts one source in half: `(9,5)` is dropped for the piece behind
it while `(9,6)` beside it, in the same layer, is admitted. The half it keeps pours down;
the half it drops is the one whose flow the engine walks along row 9.

So the exclusion is kept for an entry that stands ALONE and lifted for one that appears
beside an admitted lane in its own layer — two cells arriving together, one over a piece,
are two halves of one source.

```
physics    139 -> 112     nine boards improve (g,h,i,j,k,m,n,o 8->5, l 12->9), none worse
```

The as-known column does not move, and should not: the captures freeze the grounding's
OUTPUT, so a replay cannot be re-grounded. The rule reaches the live walk, not the replay.
`rule_bench`'s scan is a deliberate copy of the grounding's, and had to be changed with it
— the first run after the fix still reported 139 because only one of the two had moved.

Pinned by `test_a_pair_over_a_piece_edge_is_one_source_not_half_of_one`, and the pin was
CHECKED: the first version of it passed without the rescue, because the synthetic board's
bar never entered the piece inventory — `pieces()` only reports one after it has watched a
piece move — so the branch was never executed. A test that passes without the code it names
pins nothing. Driving the same fallback the class itself uses makes it fail without the
rescue and pass with it.


## Five walk rules killed, and one that halves the bench still fails the gate (2026-08-24)

With the pair grounded whole, the misses on nine boards go to ZERO — everything left is
over-production. Board o invents exactly `(7,6) (8,6) (12,5) (13,5) (14,5)`, and the same
five appear on every board of that family.

The engine's spread along a blocked row is ASYMMETRIC, measured cell by cell:

```
row 3 from (3,5) LEFT : (3,4) is OFF the piece, appears, and falls to (4,4)   1 step
row 3 from (3,6) RIGHT: (3,7) (3,8) on the piece, stops                       2 steps
row 7 from (7,4) LEFT : (7,3) (7,2) (7,1) (7,0) on the piece to the edge      4 steps
row 7 from (7,4) RIGHT: (7,5) on the piece, stops                             1 step
```

Five rules were scored against this on the physics column, and the reach that is already
adopted beats all of them:

```
reach 2 (current)                    112
reach 1                              253
reach 2, may not leave the piece     478
free walk, may not leave the piece   478
free walk                            258
"only a falling droplet may leave"   462
```

`(3,4)` is off the piece's end and the engine renders it, so "never step off" is refuted by
observation as well as by score. The asymmetry is real and none of these explains it.

### The one that halved the bench — and was reverted

Tracking `(12,5)` found something better. Target 0 owns `(13,6) (14,6) (14,7)`. The droplet
that misses at `(12,6)` goes RIGHT to `(12,7)` and down to `(13,7)` — directly over `(14,7)`,
the same target's own cell. It is looking for a way IN. Left leads nowhere and the engine
never goes there, while our replay ran a column to the board's floor.

Restricting the miss-spread to the target's own lanes scored:

```
physics   112 -> 44      every board improves or holds; b,c,d 10,10,9 -> 1,1,1
as-known  211 -> 157
```

**And the live oracle gate went 0/3, reproducibly, verdict CONTRADICTED on all three runs.**
Reverted. idx0's engine DOES spread off a target's footprint, so the rule is wrong and the
captured boards reward it for suppressing invented cells that some OTHER error produces.

**This is the lesson of the round so far, and it is now measured rather than argued: the
captured bench is a DIAGNOSTIC, not a gate.** A rule can halve it and still contradict the
level the contract is built on. Nothing gets adopted on the bench alone.

Two test findings came out of the attempt and are worth keeping even though the rule went
back:
- the shared verifier fixture reached its barrier by spreading off a missed target and
  wandering down a column belonging to nothing — behaviour the engine may not have. A
  fixture can depend on a bug.
- both new tests were checked against their own subject by removing the code they name.
  One of them, in its first version, passed without it.


## Correction, and the contradiction stated properly (2026-08-24)

The previous entry said target 0 on board o "owns (13,6) (14,6) (14,7)". **Wrong** — that
was read off a probe that printed only the cells I asked it about, and I reported the answer
to my question as the shape of the target. Grounded, board o's targets are well-formed and
identical in shape to idx0's:

```
board o    13 ......0.01.12.2      sink 0 = (13,6)(13,8)(14,6)(14,7)(14,8)  lanes 6,7,8
           14 ......000111222      sink 1 = ...(13,9)(13,11)...             lanes 9,10,11

idx0       13 ....A.A...B.B...     sink 0 = (13,4)(13,6)(14,4)(14,5)(14,6)  lanes 4,5,6
           14 ....AAA...BBB...     sink 1 = (13,10)(13,12)(14,10..12)       lanes 10,11,12
```

Both are the same five-cell shape with a MOUTH in the middle of the top row — (13,5) on
idx0, (13,7) on board o. So the footprint rule was not tested against a mis-grouped target,
and the disagreement it exposed is real:

```
idx0     droplet at (12,4), mouth to its right at (13,5)
         t17 [(12,3), (12,5)]     spreads BOTH ways; (12,3) is off the footprint
         t18 [(13,3), (13,5)]     the right half enters the mouth and satisfies
         t19 [(14,3)]             the left half runs down and stops

board o  droplet at (12,6), mouth to its right at (13,7)
         t15 [(12,7)]             spreads ONE way only
         t16 [(13,7)]             into the mouth
```

Same shape, same relative mouth, opposite behaviour. Both spread toward the mouth; idx0
ALSO spreads away from it and board o does not. That is the whole of the disagreement, and
it is now stated in terms that can be tested rather than as "the rule halves the bench".

The idx0 board is worth recording on its own: 16 wide, one piece of five cells at row 4,
two targets, hazards at (15,3) and (15,9) only. Two streams, one down lane 9 and one down
lane 4 after walking the piece's top from (3,9) to (3,4) — SEVEN cells, which no reach of 2
allows either. The reach that scores best on the captured boards does not describe this
level's walk at all, and idx0 is the level the contract is built on.


## The bench now contains the level the contract is built on (2026-08-24)

Question 7 answered first, and it was not a contradiction: idx0's stream walks seven cells
along the piece's top because the reach binds only LANDING droplets. Its single source
(`falling_sources = [[9, 0, 1]]`, one lane, one row) is a free fall, and a free fall walks
unbounded. Captured and replayed, the model reproduces idx0's whole spill **cell for cell —
zero invented, zero missed**.

That capture is now the first board in `rule_bench --all`, and it is the point of the tick.
Last tick a rule halved the sweep (112 -> 44, every board improving) and took the live gate
to 0/3. The sweep could not see it **because idx0 was not in the sweep.** With idx0 present
the same rule announces itself immediately:

```
board     as-known  physics
idx0             6        6  <- CONTRACT, must stay 0
```

Six — exactly the "the replay misses 6 cell(s) the flow reached" the verifier reported. The
diagnostic and the gate now say the same thing at the same moment, instead of the diagnostic
saying one thing for a whole tick.

The capture lives at `scripts/rounds/R98/evidence/idx0.json`, WITH the round rather than in
the scratchpad, because the scratchpad is git-ignored and a contract board that does not
survive the session guards nothing.


## The miss-spread is mouth-ward, and idx0 is the exception (2026-08-24)

Rather than argue about two events, every miss event on every capture was counted — a
droplet one step from a target cell, and whether each flank appears in the next two layers:

```
idx0     (12, 4)   sink 0  lanes 4,5,6    mouth 5    left YES   right YES
idx0     (12,10)   sink 1  lanes 10,11,12 mouth 11   left YES   right YES

idx3 ×15 (12, 6)   sink 0  lanes 6,7,8    mouth 7    left no    right YES
idx3 ×15 (12,11)   sink 1  lanes 9,10,11  mouth 10   left YES   right no
idx3 ×15 (12,14)   sink 2  lanes 12,13,14 mouth 13   left YES   right no
idx3 ×15 (13, 7)   on the mouth lane itself           neither
idx3 ×15 (13,10)   on the mouth lane itself           neither
```

Every one of the sixty-odd idx3 events spreads **toward the mouth and only toward it**, and
the direction flips with the mouth's side — right for a mouth at 7, left for a mouth at 10
or 13. A droplet already on the mouth lane spreads neither way. There is no counter-example.
idx0 spreads BOTH ways at both of its events.

This is what the footprint rule was groping at: the mouth is inside the footprint, so
restricting to lanes happened to allow the mouth-ward flank and forbid the other on idx3 —
and on idx0 it forbade a flank the engine renders. "Toward the mouth" is the same
observation stated properly, and it makes idx0 a clean exception rather than a muddle.

The exception is not explained. Both droplets are free falls arriving one row above the
target's top; the away-side cell is free space in both; the targets are the same five-cell
shape. The one structural difference measured so far is that idx0's two targets stand alone
with empty board between them while idx3's three are contiguous — but board o's away-side
flank (12,5) is free space, so contiguity does not cover that case either.

⛔ Do not "fix" this by making the spread mouth-ward. It is right on 60 events and wrong on
the 2 that the contract, the oracle gate and the mutant table are all built on.

**RESOLVED (2026-08-24)**: mouth-ward was right about what it saw and wrong about why. On
the idx3 boards the away side is ANOTHER TARGET'S ROOF; idx0's targets stand alone, so its
away side is open and the flow takes it. Forbidding only the step onto a neighbour scores
209/108 with idx0 untouched at 0.


## The walk re-run: the obstacle now names itself (2026-08-24)

Several ticks of grounding work had not been measured on the LIVE walk, only on captures.
Run end to end:

```
idx0: CLEARED — 23 actions (4 selection probes)
idx1: CLEARED — 30 actions (6 selection probes)
idx2: CLEARED — 55 actions (6 selection probes)
  [verifier] UNKNOWN — proceeding: the replay predicted 1 cell the flow never reached
             (e.g. (12,9)), but the board is INCOMPLETE:
             2 source(s) hidden under a piece, not in the board model
idx3: stopped — compiler UNSATISFIABLE: no layout satisfies the objective under the
      claimed table: 40084 examined across the cheapest neighbourhood and the per-piece
      shortlists
[depth walk] one hypothesis carried 3 levels; 139 actions total
```

Two things moved, and neither is a score:

**idx2's verifier stopped saying "CONTRADICTED" and started naming the cause.** It now
reports one surplus cell AND the reason the board cannot account for it — two sources still
hidden under pieces. The pair-rescue fixed the case where one half of a straddling source
was admitted and the other dropped; this is the harder case where the whole source is
covered and nothing of it is visible except its flow. The verifier degrading to UNKNOWN
with a named gap, rather than failing with a mismatch, is the harness working as designed.

**idx3 moved from mis-predicting to honestly unsatisfiable.** It used to execute a plan
whose trail disagreed with the engine; now the compiler examines 40084 layouts and reports
that none satisfies three targets. That is not progress in levels and it is not a
regression — it is the model no longer claiming a plan it cannot justify, which is the
behaviour the contract asks for.

Action counts are unchanged at 23 / 30 / 55, so nothing bought depth at the cost of
efficiency.


## The harness was excusing itself with evidence it did not have (2026-08-24)

idx2's verifier had stopped failing and started reporting "2 source(s) hidden under a piece,
not in the board model" — which read like the harness naming its own gap, and the last entry
recorded it as the next lever. Two attempts to feed those sources into the board were
BYTE-IDENTICAL on the walk. A mechanism inert twice is worth instrumenting rather than
guessing, so `embedded_sources` was made to print what it was actually handed:

```
[dbg] inventory=5 prev_cells=True hidden=(((3, 5), None), ((3, 6), None))
```

**Both hosts are None, and the two cells are (3,5) and (3,6)** — the ordinary lane sources at
the top of the board, already grounded as `(5,3,3)` and `(6,3,3)`. Nothing was hidden and no
piece was involved. `hidden_sources` reports an orphan whether or not it can name a piece for
it to hide under, and `build_flow_evidence` then phrased every orphan as "hidden under a
piece" and set `incomplete_board`, which **downgrades the verifier's verdict to UNKNOWN**.

So a real mismatch was being excused by a reason the evidence did not support. Requiring a
host — a source hidden under a piece must name the piece — changes the walk:

```
before   idx2 [verifier] UNKNOWN — ... 2 source(s) hidden under a piece
         idx3 stopped — compiler UNSATISFIABLE: 40084 layouts examined
         139 actions

after    idx2 (no verifier line: clean)
         idx3 stopped — verifier CONTRADICTED: the replay predicted 1 cell(s) the flow
              never reached, for example [(12, 9)]
         129 actions
```

The excuse was masking a **one-cell** disagreement, and the compiler's "no layout satisfies
the objective" was downstream of a board carrying two sources that do not exist. idx0–idx2
still clear at 23 / 30 / 55.

A harness that excuses itself on evidence it does not have is worse than one that fails:
the failure is information and the excuse is not. This is the second time in the round that
a green-looking message was hiding a real disagreement — the first was a diagnostic bench
that could not see the contract level.


## The walk's whole remaining disagreement was one cell, and it is closed (2026-08-24)

With the false "hidden source" excuse gone, idx3 stopped on an honest verdict: one surplus
cell, `(12,9)`. To study it the walk now freezes the board WHEN THE VERIFIER CONTRADICTS —
without that it reports a disagreement and then throws away the only evidence of it, since
the next run plans differently and the board is gone.

Replayed, the cell sets agree except for that one (47 predicted vs 46 observed), and the
rest of the divergence is TIMING: our first stream runs a step ahead of the engine's from
step 4 on. `_trim` already drops pauses on both sides, so the verdict was charged the cell
and nothing else.

```
  15: predicted [(9,7), (11,1), (12,7), (12,9)]
      observed  [(8,7), (9,1)]                     ... (12,7) arrives at 17, (12,9) never
```

The droplet at `(12,8)` misses target 0 (lanes 6,7,8, mouth at 7). It spreads to `(12,7)`,
toward its own target's mouth, and **not** to `(12,9)` — which stands over target 1.

That is NOT the mouth-ward rule that took the gate to 0/3. On idx0 the away-side flank is
free space and the engine DOES go there; here the away-side flank is a neighbour's roof.
Forbidding only the step onto another target keeps idx0 exactly as it was:

```
                        as-known   physics   idx0
before                       211       112      0
not onto another target      209       108      0
```

And on the live walk, idx3's verifier no longer contradicts — it passes and the walk
proceeds to planning, where the next wall is the compiler reporting that no layout satisfies
three targets. idx0-idx2 still clear at 23 / 30 / 55.

Worth naming: the mouth-ward observation was RIGHT about what it saw and wrong about why.
Every idx3 miss spreads mouth-ward because on those boards the away side is another target's
roof; idx0's targets stand alone, so its away side is open and the flow takes it. One rule,
two appearances.


## The compiler was telling the truth about a board missing four fifths of its pieces (2026-08-24)

idx3's next wall said "no layout satisfies the objective ... 40084 examined". Freezing that
board (`R98_CAPTURE_STUCK`) and enumerating every placement of every piece:

```
single-piece placements by targets satisfied:  {0 targets: 2, 1 target: 10}
target 0 reachable by shifts [-4,-3,-2,-1,0,3,4,5,6,7]
targets never reachable: [1, 2]
```

**The board holds ONE piece.** The same level, captured at the verifier a run earlier, holds
five:

```
p        pieces=5   (4,4..7) (4,9..12) (7,2..6) (8,11..13) (10,9..11)
stuck    pieces=1   (4,4..7)
```

Sources are at lanes 5 and 6, and both are landings, so the reach of 2 binds their walk from
the source cell — the flow cannot pass lane 8. Targets 1 and 2 sit at lanes 9-11 and 12-14.
With that single bar they are unreachable, and the compiler saying so is correct rather than
broken. It is answering honestly about a board that is missing four fifths of itself.

That the reach binds from the source is why idx0 differs: idx0's source is far above its
piece, and a droplet that merely FALLS resets to unbounded, so it walks seven cells. On idx3
the source sits directly over the bar and the reach applies immediately — which is exactly
what the engine does there, stopping the right walk at (3,8) on the observed boards. The
model is right; the board is short.

The walk now reports the count with the verdict — `[board held 1 piece(s)]` — because
"unsatisfiable" and "unsatisfiable on a board with one piece" are different statements and
only one of them is actionable. Capturing before the cover-slide as well was added at the
same time and did NOT fire, which is itself the answer: the inventory was already short
before any slide, so the slide is not what lost them.

The sweep now carries the new captures, so its TOTAL is not comparable with the last tick's
— only per-board is:

```
idx0 0 · p 0        p is the board the neighbour rule closed, and it closed completely
s3 25 · stuck2 25   the 1-piece boards: they measure the INVENTORY gap, not the propagator
sum 267 / 158       over 20 boards, against 209 / 108 over 17
```

A bench whose membership changes needs its membership stated with its total, the same way a
score needs its budget and its env.


## Correction, and a defect: asking for the inventory changes what the walk does (2026-08-24)

The last entry said the compiler "was planning on 1 of the level's 5 pieces", from two boards
captured in DIFFERENT runs. Comparing across runs is not comparing. Repeated within one run
and then across runs:

```
uninstrumented, 6 runs of 7   idx3 UNSATISFIABLE, [board held 1 piece(s)]
                1 run  of 7   idx3 planned and failed on a press
with one g.pieces() call
  placed right after verify   idx3 SOLVABLE with 5 pieces, 2 runs of 2
```

The difference is a single **read**. Nothing else changed: no extra action, no different plan
input, one call asking the grounding how many pieces it holds. With it, idx3's compiler gets
a five-piece board and produces a SOLVABLE plan; without it, a one-piece board and
"no layout satisfies the objective".

A bare `g.board()` placed EARLIER, before verification, does not do this (2 runs of 2), so it
is not "any read" — it is `pieces()` asked at that point. The inventory is computed lazily
and does not answer the same way depending on when it is first asked, and the walk's plan
quality rides on that.

So the previous entry's conclusion is **withdrawn**: the compiler is not "answering honestly
about a board missing four fifths of itself" as a property of the level. It is answering
about a board whose contents depend on observation order. The enumeration in that entry —
one bar, sources at lanes 5-6, reach binding from the source, targets 1 and 2 out of
reach — remains correct FOR A ONE-PIECE BOARD, which is not the board the level presents.

What this buys, measured: with the five pieces present, idx3 IS satisfiable. The wall moves
from "no layout exists" to "planned press 2 did not land; pieces 4 vs planned 5" — an
execution problem, and a much better one to have.

⛔ Do not fix this by leaving a probe call in the walk. A diagnostic that changes the result
is not a diagnostic. The lazy inventory is the defect; the read is only what exposed it.


## The diagnostic was not reading the program, it was rewriting it (2026-08-24)

The previous entry withdrew a conclusion on the strength of this: one `g.pieces()` call after
verification took idx3 from UNSATISFIABLE-on-one-piece to SOLVABLE-on-five, twice out of
twice. **That withdrawal was wrong, and so was its evidence.**

A bare `g.pieces()` at the same point, with no print and nothing else, does not change the
outcome — 2 runs of 2, against a paired control of 2 that also does not. So the read is not
what did it. Isolating the other half of the instrumentation printed its own context:

```
    while attempts < REPLAN_LIMIT:
        attempts += 1
        plan = compile_flow_hypothesis(hypothesis, g)
    if os.environ.get("R98_PROBE_B") == "1":     <- FOUR spaces, in an EIGHT-space body
        g.pieces()
```

The inserted block was dedented relative to the loop it was inserted into, which **ended the
`while` body**. Everything after it left the loop. The program that produced "SOLVABLE with
five pieces" was not the walk with a probe in it; it was a different program.

So: the walk is deterministic. Eleven runs, every one of them:

```
idx0 CLEARED 23a · idx1 CLEARED 30a · idx2 CLEARED 55a
idx3 UNSATISFIABLE, [board held 1 piece(s)]
```

The conclusion of two entries ago — the compiler answering honestly about a one-piece board,
with sources at lanes 5-6 and the reach binding from the source putting targets 1 and 2 out
of range — **stands, and the withdrawal is itself withdrawn.**

The lesson is not "be careful with probes". It is that a probe inserted by string
manipulation can change the program's STRUCTURE while looking like an addition, and nothing
in the output says so. Both instrumented runs agreed with each other, twice, which is exactly
what a real effect looks like. What caught it was isolating one half of the change and
printing the surrounding lines — reading the code as it ended up, not as it was meant.

⛔ When a diagnostic changes a result, suspect the diagnostic first, and print its context
before believing it.


## One frame was erasing what a piece looks like (2026-08-24)

Why does idx3's board hold ONE piece when the level presents five? Observed WITHOUT editing
the walk this time — the class was wrapped from a separate driver, so nothing about the
program's structure could change:

```
[inv] idx3: None -> 5 -> 4 -> 5 -> 4 -> 1
      at the collapse:  shapes=8  sel=9  idle=9  moving=4  regions={9: 1, 4: 0}
```

**Selected and idle are BOTH 9.** `pieces()` scans the board once per appearance, so with one
distinct colour it scans once, finds one region, and reports one piece. Everything downstream
follows honestly from that: the compiler examines forty thousand layouts of a one-piece board
and says none satisfies three targets.

The cause is in the selection reader. `_selected_colour` is assigned unconditionally while
`_idle_colour` is only updated when the observation happens to name another colour, so a
selection observed in the colour already recorded as IDLE leaves both equal.

Exactly one piece is selected at a time, so the two appearances are distinct by construction.
If what now wears the selected appearance is the colour we had down as idle, the roles
EXCHANGED and what we had down as selected is what the rest now wear:

```
board held 1 piece(s),  40084 layouts   ->   board held 4 piece(s),  46664 layouts
```

idx3 is still UNSATISFIABLE, but on a board with four of its five pieces rather than one.
idx0-idx2 unchanged at 23 / 30 / 55, all four certifications PASS, and the bench is unchanged
board for board.

The four captures taken while the appearances were collapsed were REMOVED from the sweep. A
board whose piece inventory is known to be wrong measures the reader, not the propagator, and
each was carrying 25 cells of error that no propagation rule could ever answer for. The sweep
is back to 209 / 108 over seventeen boards.

Method note, after the previous tick: this measurement wrapped `FlowGrounding.observe` from a
separate script instead of inserting lines into the walk. Nothing was edited, so nothing could
be mis-indented, and the observation cost nothing but a wrapper.


## Next

1. **Fill is not confirmed paired.** gemma4 misses one slot, and the cause is our
   encoding rather than its reasoning. Measure the hazard orthogonalisation as its
   own experiment against all three models — never as a patch to move a verdict.
2. ~~Why does the walk reach not bind an injected source?~~ **ANSWERED — it WAS the reach.**
   A landing cell entered the frontier with an unlimited walk; giving it `walked = 0` is
   worth 32 cells (243 -> 211). The intermediate claim that the cell never entered the
   frontier at all was wrong and is corrected in the body.
3. **The blocked-row spread is ASYMMETRIC and nothing yet explains it** — 1 step one way,
   4 the other, on the same board. Six rules measured, all worse than the adopted reach 2.
   The remaining error is now entirely over-production.
6. **Why does idx0 spread AWAY from the mouth when NO idx3 event does?** Counted across
   every capture: 60+ idx3 events spread mouth-ward only, with the direction flipping with
   the mouth's side and no counter-example; idx0 spreads both ways at both events. The
   rule is sharp and idx0 is a clean exception. ⛔ Do not adopt mouth-ward — it is wrong
   on exactly the level the contract is built on.
7. ~~idx0's walk is SEVEN cells long.~~ **Not a contradiction** — the reach binds only
   LANDING droplets, and idx0's single source is a free fall. The model reproduces idx0
   cell for cell, and that capture is now the first board in the sweep.
4. ~~Report b, c and d apart from the rest.~~ **DONE** — `rule_bench.py --all` now reports
   as-known 211 and physics 139. Judge propagation rules on the physics column.
5. ~~Sources FULLY hidden under a piece.~~ **There were none** — the message named the two
   ordinary lane sources with no piece anywhere near them, and it was suppressing a real
   verdict. Fixed by requiring a host. What it was hiding is the actual next item:
9. ~~idx3 disagrees by ONE cell, `(12,9)`.~~ **CLOSED** — a miss does not spread onto a
   neighbouring target's roof. idx3's verifier passes; the next wall is the compiler.
10. ~~idx3's compiler: no layout satisfies three targets.~~ **It was right** — the board it
    planned on held ONE of the level's five pieces, and with sources at lanes 5-6 and the
    reach binding from the source the flow cannot pass lane 8. The real question is:
11. ~~Why does the grounding hold ONE piece on idx3?~~ **It was the reader** — selected and
    idle had collapsed to the same colour, so `pieces()` scanned one appearance and found
    one region. Fixed by exchanging the roles; idx3 now plans on 4 pieces.
12. **idx3 is still UNSATISFIABLE, now on 4 of 5 pieces.** The fifth is the next question,
    and after that whether four suffice.
8. **Close the 72-cell gap at the walk, not the propagator.** It is the cost of planning
   a commit before its spill exists, so the lever is the grounding CADENCE — re-ground on
   each spill before the next plan — and it should be measured on the live walk.
3. **Measure the bounded-roof variant on fixed evidence** — 1 invented cell against the
   adopted rule's 2, deliberately not adopted in the same change.
3. **Multi-piece placement**, the burden the idx1 observation named: idx1 carries
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
