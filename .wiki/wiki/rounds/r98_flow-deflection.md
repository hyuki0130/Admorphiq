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


## Three false hazards were declaring the level unwinnable (2026-08-24)

With four of the five pieces back, idx3 was still UNSATISFIABLE — so the layouts were
enumerated directly rather than argued about. Every reachable multi-piece layout, shifts
-10..+10 on four pieces:

```
by (targets satisfied, fatal):  {(0, True): 10041, (1, True): 10379, (2, True): 1910, (3, True): 134}
WINS: 0
```

**Every one of the 22464 valid layouts is fatal**, including the 134 that fill all three
targets. (The first pass counted only `satisfied` and nearly reported 134 solutions; `wins`
is `satisfied AND not fatal`, and it is zero.) So the compiler was right for the third time
in this thread — about a board that could not be won.

The hazards were the reason, and they were not hazards:

```
hazards: (12,2) (12,3) (12,5) (12,6)   colour 12 — which is the BACKGROUND, 192 cells of it
         (15,1) (15,4)                 row 15 on a size-15 board — the FRAME
```

`barriers()` reads "flow reached the cell before it and that cell never became flow". Both of
these satisfy that and neither blocks anything: a background cell past a stream's end means
the spill ENDED there, and a frame cell is not board at all. The frame case bites twice over,
because the propagator checks the hazard set on the same branch as the boundary, so a hazard
recorded outside the board still fires.

One fix was tried first and REJECTED by measurement: excluding cells ahead of the animation's
final front. idx0's real hazard at (15,3) sits exactly there, and idx0 went to CONTRADICTED.
The distinction is not position in the animation — it is that **a barrier has to look like
something and stand on the board**.

A third change followed from the second: with the last false hazard gone, `barriers()` found
none and returned UNKNOWN, and `board()` refuses to assemble without it — so the walk reported
"grounding incomplete" on a board it had measured completely. An empty set is an answer.

```
before   idx3 UNSATISFIABLE, 46664 layouts examined, board held 1 piece
after    idx3 executed the plan without clearing (31 actions), board holds 5
```

idx0-idx2 unchanged at 23 / 30 / 55; oracle 3/3, grounding PASS, verifier PASS, mutants PASS,
bench unchanged at 209 / 108.

**Owed**: a unit pin for the two barrier rules. Three fixtures were written and none produced
an animation the grounding would register, so no test was committed rather than a green one
that exercises nothing — the last two ticks each caught a pin that passed without its subject.
The rules are currently held by the walk and the four certifications.


## idx3's wall is a SCHEMA GAP, not a defect (2026-08-24)

idx3 now plans and executes; the level does not advance. The forecast and the outcome were
compared cell by cell:

```
model      satisfied [0, 1, 2]   fatal False   wins True
engine     all three mouths ENTERED — (13,7), (13,10), (13,13) all in the trail,
           the last observed layer is exactly [(13,10), (13,13)]
level      does not advance
```

The trail has no missed cells, so this is not the propagator getting the spill wrong. It is
the OBJECTIVE. idx0 clears with exactly the same signature — mouths entered, target bodies
never becoming flow — so nothing about how the three targets were filled is different.

What is different is a fourth region:

```
(13,2) (13,3) (14,2) (14,3)   a 2x2 block, colour 11
targets 0,1,2                 five cells each, colour 11 — the SAME appearance
```

`absorbers()` already carries the measurement in its own docstring: a solid block wearing the
target appearance **is satisfied by the engine** — it recolours when the spill reaches it —
"while no candidate table has a rule that ever satisfies a region with no notch to be flanked
at. So it cannot be offered as a target." It was classified as an absorber because the schema
has nowhere else to put it.

So idx3's objective is four regions and the schema can express three. The plan fills the three
it can name, the engine agrees it filled them, and the level correctly does not advance. The
compiler, the verifier and the propagator are all telling the truth; the vocabulary is short.

This is a FAMILY finding, not a bug to patch: the gated-enum work fixed `sink_predicate` on
`same_sink_flanks`, which is a rule about a notch. A notchless target needs a satisfaction
rule that does not reference flanks at all, and adding one now — mid-round, to move one level
— would be extending the schema to fit a case rather than measuring whether the family needs
it. Recorded for the round's schema findings alongside the hazard-policy/hazard-response split.


## Does the family need a notchless rule? Measured: one level in four (2026-08-24)

Before extending the vocabulary for idx3, the obvious question is whether the family asks for
it. Counted across every level the walk reaches, by wrapping `board()` rather than editing:

```
idx0   targets 2   notchless blocks 0
idx1   targets 3   notchless blocks 0
idx2   targets 3   notchless blocks 0
idx3   targets 3   notchless blocks 4 cells — (13,2) (13,3) (14,2) (14,3)
```

**One level in four.** That is a case, not a family requirement, and it is exactly the
situation the round's own precedent covers: measure whether the family needs a rule before
cutting the schema to fit a level. n=1 does not earn a new satisfaction predicate. Recorded
and left alone; if a later level of this family shows the same region, the count becomes 2
and the question reopens on evidence rather than on convenience.

A second thing fell out of the same probe, unlooked for:

```
[abs] grounding 736: targets=3  ...
[abs] grounding 736: targets=10 ...
```

**idx2's target count transiently reads 10** before settling. It clears anyway — the plan does
not need a clean shortlist to work here — but a grounding that briefly names ten targets on a
three-target board is naming something that is not a target, and on a level where the plan did
depend on the count it would not be harmless.

## Where the depth thread stands

The walk carries ONE hypothesis through three levels and stops on a vocabulary limit, not on a
defect:

```
idx0 CLEARED 23 actions · idx1 CLEARED 30 · idx2 CLEARED 55 · idx3 blocked by the schema
oracle 3/3 · grounding PASS · verifier PASS · mutants PASS · bench idx0 0/0, 209 / 108
```

Everything between the round's start and here was found by measurement rather than argued:
the reach binding only landing droplets, the straddling source grounded whole, the miss that
will not step onto a neighbour's roof, the collapsed piece appearances, and three hazards that
were background and frame. Four of those five were things the harness was telling itself
wrongly, not things the engine was doing strangely.


## The ten targets are scenery, and they arrive on a single move (2026-08-24)

Chasing the transient count on idx2, non-invasively:

```
[tgt] 464: 3  after observe(5, 29)   a commit, 29 layers
[tgt] 464: 10 after observe(4, 1)    a MOVE, one frame
```

It is not a spill and not a level boundary — one plain move action, one frame, and the
shortlist goes from three to ten. What the ten are:

```
sink_0 size 18   sink_2 size 39   sink_4 size 31   sink_6 size 17   sink_7 size 14
sink_1 size  5   sink_3 size  5   sink_5 size  5   sink_8 size 2    sink_9 size 2
every one of them overlaps ZERO piece cells;  sel=9 idle=8, 21 piece cells
```

The three real targets are the size-5 entries; the rest is board scenery, and none of it is a
piece, so the appearance collapse fixed earlier this round is not the cause. Sizes of 39 and
31 next to a confirmed target of 5 are not near-misses — the shortlist is naming structure.

It does no harm HERE: idx2 clears at 55 actions either way, because the plan does not depend
on the count. That is precisely why it is worth recording rather than shrugging at — the same
read on a level whose plan does depend on "cover every target" would make the objective
unreachable by construction, which is exactly the failure mode idx3 spent three ticks in.

Measured and REVERTED: excluding candidates that reach outside the playable board. It is the
same rule `barriers()` already applies and it is INERT here — idx2's board is size 16, so the
two row-15 entries are inside it. An inert guard is a speculative safety net, so it went back
out rather than staying in as decoration.

The remaining discriminator is SHAPE — a confirmed target is five cells with a notch, and a
39-cell region is not a bigger one of those. The shortlist admits obstruction-named regions
of any shape ON PURPOSE, so that a target the probing spill never satisfied can still be
named, and narrowing that needs its own measurement rather than a size threshold picked to
fit this board.


## The blocker was dragging its whole wall in (2026-08-24)

Which of the shortlist's four sources names the scenery? Wrapped and counted at the moment
idx2 reads ten:

```
changed      3 region(s)  sizes [5, 5, 5]      <- the real targets
obstruction  1 region      size [198]           <- 77% of a 16x16 board
shape        1 region      size [5]
appearance   0
```

One region of 198 cells, which the mouth split then carves into the seven scenery entries.
`_obstruction_regions` seeds from cells that actually stopped the flow and then takes the
**whole connected region of that colour** — and a board's walls are one colour and all
connected, so one blocker touching a wall names the wall.

The fix needs no size rule, because the evidence is already in hand: keep only the parts that
contain a cell that ACTUALLY obstructed the flow. The rest is the wall the blocker happens to
touch.

```
idx2 transient shortlist   10 targets [18, 5, 39, 5, 31, 5, 17, 14, 2, 2]
                        ->  4 targets [5, 5, 5, 17]
```

The three real targets and one 17-cell region that genuinely blocked the flow — which is the
shortlist doing its job, since it is a shortlist and not a decision. idx0-idx2 clear at the
same 23 / 30 / 55, idx3 unchanged, all four certifications PASS, bench unchanged at 209 / 108.

**Owed, again**: a unit pin. A test was written for this and DELETED before committing — it
asserted on a locally-built set and never called `_obstruction_regions`, which is the same
vacuous shape this round has now caught three times. The barrier rules and this one are held
by the walk and the certifications until a fixture exists that produces a registered
animation.


## Why the owed pins keep failing: what makes a spill REGISTER (2026-08-24)

Three rules are owed a unit pin and every fixture written for them was silently ignored —
`_animations` stayed empty, so `barriers()`, `_obstruction_regions()` and everything else
answered UNKNOWN and the tests asserted on nothing. The requirement was read out of
`_read_animation` rather than guessed:

```
a colour is READ AS FLOW when
  * its footprint is a superset chain over at least 3 consecutive layers, and
  * it GROWS on at least 3 of them, and
  * the last layer is larger than the first
```

Every earlier fixture added three flow cells, which is two growth steps. That is the whole
reason they were inert — one step short of being looked at.

A fixture built to the requirement DOES register:

```
wall at rows 6-7 with notches, a stream down column 4 that splits on it
frontier [(1,4)] [(2,4)] [(3,4)] [(4,4)] [(5,4)] [(5,3),(5,5)] [(5,2),(5,6)]
animations 1   direction (1,0)   obstruction [(6,4)]
```

The split has to arrive in ONE frame, too: the blocker test wants both perpendicular
neighbours present in the next layer, and a fixture that renders them on separate frames
reports no obstruction at all.

Not yet solved: the variant needed to exercise the wall-dragging rule — the same board with
the notch under the split filled in, so the blocker is part of the wall — does NOT register
(`animations 0`), and the reason is not yet known. The flow colour's growth is identical in
both, so it is something about the other colour's footprint.

Recorded rather than left in a scratch file, because it is the difference between the next
attempt starting here and starting where the last three did.


## The owed pins are paid, and the third obstacle was the SCALE (2026-08-24)

The last entry left one thing unexplained: a fixture identical in its flow growth registered
in one variant and not in another. It was neither the flow nor the wall — it was the scale.

```
notches (1,4,6)   scale 2   colour 6: run 7, steps 6   -> animation READ
notches (1,6)     scale 4   colour 6: run 2, steps 0   -> nothing
```

`_infer_scale` takes the LARGEST block size whose blocks are uniform, so a board whose content
happens to align to 4 is read at 4 and every cell after that is nonsense. Its own docstring
warns about the sibling of this — a margin that excuses real content near an edge — and that
is exactly what defeated the first fix: a marker at (0,1) or (1,1) does NOT resolve the scale,
because the margin excuses it. An interior, odd-aligned cell does.

```
marker  none  (0,1)  (1,1)  (3,5)  (5,1)
scale      4      4      4      2      2
```

So a synthetic board needs THREE things before the grounding will look at it, and each one
was found by a fixture failing silently rather than by reading the code first:

1. the flow grows over ≥3 layers and on ≥3 of them,
2. the split arrives within ONE frame,
3. the first frame resolves the scale, with an interior marker rather than an edge one.

All three are now written into a `_wall_and_spill()` helper beside the tests that use it, so
the next fixture starts from a board that registers.

**Both owed pins are paid**, and each was checked by removing the code it names:

```
obstruction   with the fix [7]   without it [14]   — the blocker dragging its whole wall
barriers      with the fix ()    without it UNKNOWN — an empty set is an answer
```


## The last owed pin, and what the fixture turned out to already cover (2026-08-24)

The background-cell barrier rule was the one pin still outstanding, and `_wall_and_spill()`
already exercises it — the notch at (6,6) is empty board one step past where the flow stops
at (5,6), which is exactly the shape of the idx3 mis-read. Measured both ways before writing
anything:

```
with the rule      barriers []
without it         barriers [(6, 6)]
```

So a test was owed but a fixture was not. It is now a dedicated test rather than left as a
side effect of the empty-set one, because a reader who breaks the background rule should be
told which rule they broke — without it, two tests go red and neither names the cause.

**Every rule this round adopted now has a pin that was checked against its own subject**:

```
a landing starts a bounded walk                     (walk + certifications)
a straddling pair grounds whole                     test_a_pair_over_a_piece_edge...
a miss does not step onto a neighbour's roof        test_a_miss_does_not_spread_onto...
a selection in the idle colour exchanges the roles  test_selection_that_takes_the_idle...
an obstruction names the part that blocked          test_an_obstruction_names_the_part...
an empty barrier set is an answer                   test_an_observed_spill_that_hits...
a background cell is not a barrier                  test_a_background_cell_past_a_spills_end...
a hostless orphan is not a hidden source            test_an_orphan_with_no_piece_to_hide...
```

Three of those were written twice: the first version passed without the code it named, and
was only caught by deleting the code and re-running. That check is now the habit rather than
the exception, and it is the reason the three-tick fixture detour was worth taking rather
than shipping green tests that assert on nothing.


## The OOD controls are certified, and the positive control earned its place (2026-08-24)

`near_ood_screen.py` ranked the candidates by the family's observable tell and recorded that
the full certification "needs the grounding service, which does not exist yet". It exists
now, so the real control ran: point the flow harness at games that are NOT this family and
see what it says.

The first version reported exactly what was hoped for — both controls declining — and it was
**worthless**. Adding sp80 as a positive control said why in one line:

```
sp80 (positive): FAILS — the grounding cannot assemble a board
tu93 (near):     DECLINES — the grounding cannot assemble a board
re86 (far):      DECLINES — the grounding cannot assemble a board
```

The harness was declining because the discovery was six actions and had skipped the alignment
before the commit, not because the games differ. "Declines on everything" passes a control
that only asks for declining, and proves nothing at all.

With the gate's real discovery — the four probes, the origin-hint alignment, then the
sacrificial commit — the same three games separate:

```
sp80 (positive): OK       — board with 2 target(s), 1 piece(s); verifier PASS
tu93 (near):     DECLINES — the grounding cannot assemble a board
re86 (far):      DECLINES — the grounding cannot assemble a board
[ood certification] PASS — the harness reads its own family and declines the others
```

One honest limit, stated rather than glossed: both controls decline at PERCEPTION, so the
verifier is never reached on them. That is a real form of declining and it is what the
contract asks for, but it means these controls exercise the grounding and not the mechanics —
a near control that assembled a board and was then refuted by the verifier would test more.
tu93 survived the pre-screen on its 8-layer burst, so such a control may yet exist; it is not
this one.


## The fill experiment the round owes is now runnable (2026-08-24)

FILL is the one contract stage not confirmed paired: gpt-oss passes 3/3 with a perfect
seven-of-seven hypothesis, gemma4 misses exactly one slot and does so self-contradictorily —
correct hazard POLICY next to an incompatible hazard RESPONSE. The round recorded that as a
finding about our ENCODING and refused to patch it, because gpt-oss resolves the same encoding
and re-cutting a representation until a weaker model passes is tuning, not measurement.

What the encoding does is ask the same question twice:

```
ASK 1 (objective)   "hazard_policy":   fatal_on_contact | neutral
ASK 2 (slots)       "hazard_response": terminate_fatal | terminate_local | pass_through
                    ...and the prompt REQUIRES the two to agree.
```

`--hazard fused` asks it once: the objective ask drops `hazard_policy` and says so, and the
policy is read off the slot answer instead. Split remains the default, because the contract is
frozen on it and this is a separate experiment rather than a replacement.

Verified locally before any GPU time is spent:

```
keys=[completion, objective]                 fused=False -> None        (correctly rejected)
keys=[completion, objective]                 fused=True  -> instance, policy fatal_on_contact
keys=[completion, hazard_policy, objective]  fused=False -> instance, policy neutral
keys=[completion, hazard_policy, objective]  fused=True  -> instance, policy neutral
```

so the derivation fires only when the question was not asked, a volunteered policy is still
honoured, and the split path is unchanged. The fused ask's dry run carries `hazard_response`
and no `hazard_policy`, leak guard clean; the harness self-test still passes on the default.

What it will measure, when it runs: whether gemma4's miss is the SPLIT or the reasoning. If
fused takes gemma4 to 3/3 while gpt-oss stays 3/3, the encoding is the cause and the finding
is about our schema. If gemma4 still misses, the split was never the problem and the finding is
about the model. Either answer is worth having; neither is available from arguing.


## Checking the parked diagnosis: the flow ran PAST the fourth region (2026-08-24)

idx3 is parked on a schema gap — the objective is four regions and the vocabulary names
three. That diagnosis deserved a check rather than a shrug, so the executed plan's own trail
was read:

```
block cells in the trail:  []                          (13,2) (13,3) (14,2) (14,3)
cells beside the block  :  (12,1) (13,1) (14,1)
```

The left branch runs down column ONE, past the block at columns two and three, and never
touches it. The block still wears colour 11 — the same appearance as every target — at the
end of the attempt. So the level failing is CONSISTENT with the fourth region being unfilled,
which is what the parked diagnosis says.

Consistent is not the same as confirmed, and the difference is worth naming: this evidence
would look identical if the level needed something else entirely that the plan also missed.

Free enumeration says the experiment exists: on the captured board, 14033 layouts fill all
three targets, avoid the hazard, and put flow within reach of the block. So the decisive test
is available and costs actions rather than cleverness:

1. carry the walk to idx3 as it already does,
2. execute a layout that fills the three AND sends a stream down column 2 or 3 — into the
   block rather than past it at column 1,
3. read `levels_completed`.

Advancing proves the fourth region was the requirement and that CONTACT satisfies it, which
is what `absorbers()` already claims from the recolouring. Not advancing refutes the parked
diagnosis outright, and that is the more valuable outcome of the two, because the round has
been treating a schema gap as the reason idx3 stops.


## The schema gap is real, but it was stated wrong (2026-08-24)

The parked diagnosis rested on a claim in `absorbers()`: "no candidate table has a rule that
ever satisfies a region with no notch to be flanked at". That is **false**, and the vocabulary
says so — `sink_response_predicate` offers `contact`, and in the propagator `contact` skips the
flank test entirely:

```python
hit = same if table.sink_predicate == "same_sink_flanks" else True
```

Promote the notchless block to a fourth target and claim `contact`, and the level is solvable:

```
block as a 4th target, predicate=contact  ->  14033 winning layouts
```

So the rule exists. What does not exist is applying it to ONE target. The predicate is global,
and `contact` is not free to take:

```
sink_satisfied_on_contact   transition  CONTRADICTED   (frozen table, re-verified live)
```

It is measurably wrong for the family. idx3 therefore needs `same_sink_flanks` for its three
notched targets and `contact` for the fourth, on the same board, and the schema applies one
predicate to all of them.

**That is the finding, and it is a better one than the version it replaces.** "No rule can
satisfy a notchless region" invites adding a rule that is already there. "The predicate is
global and this board needs two" names a structural property of the encoding, and it is the
kind of thing the family expansion exists to discover. It also keeps the n=1 parking honest:
per-target predicates are a real schema change, and one level is still not evidence that the
family wants one.

The docstring is corrected in place rather than rewritten around, so the measurement that
produced the original claim stays next to the measurement that narrowed it.


## The decisive test ran, and it does NOT confirm the parked diagnosis (2026-08-24)

The recipe from the last entry was executable after all, without editing anything: wrap the
compiler so that ONLY a board carrying the notchless block is planned for with that block as a
fourth target under `contact`. Every other level plans exactly as it does today.

```
[block-test] planning idx3 with 4 targets under contact
[block-test] plan status SOLVABLE, predicted_satisfied 4
idx0 CLEARED 23a · idx1 CLEARED 30a · idx2 CLEARED 55a
idx3: stopped — executed the plan without clearing (33 actions)
```

A plan aimed at all four regions executed, and the level still did not advance. Before reading
that as a refutation, the engine's own trail was checked — a model that claims four satisfied
proves nothing if the flow never got there:

```
block cells reached by the flow: []
cells beside it:                 (12,1) (12,2) (13,1) (14,1)
block appearance after:          {(13,2): 11, (13,3): 11, (14,2): 11, (14,3): 11}
```

The flow reached **(12,2), directly on the block's roof**, and the block did not recolour. So
the test did deliver flow to the region, and:

* the level did not advance, and
* `absorbers()`'s claim that the block "recolours when the spill reaches it" does not hold for
  contact on the roof — the only contact this layout produces.

**What is shown**: roof contact neither recolours the block nor clears the level. **What is
not**: whether entry from the side, or into a cell of the block itself, would. Our model
deflects flow around an absorber and never enters it, so no layout it plans can test that.

The parked diagnosis — "idx3 stops because the fourth region cannot be named" — is therefore
NOT confirmed, and the more careful sentence from two entries ago turns out to have been the
right one: the evidence was consistent with it and would have looked identical if the level
needed something else. It now looks like something else.


## What the engine itself says about idx3 (2026-08-24)

With the fourth region no longer the leading answer, the question became "does the engine even
think idx3 is unfinished?" — a walk that mis-reads its own progress would look exactly like a
level that will not clear. Wrapping the engine's `step` rather than the walk (a probe patched
into `depth_walk` never fires: `runpy` re-executes the file and defines a fresh class, so the
patch lands on a different object than the one running):

```
[state] n=120..128  levels=3  NOT_FINISHED  layers=1
[state] n=129,130   levels=3  NOT_FINISHED  layers=33   <- a commit
[state] n=131..138  levels=3  NOT_FINISHED  layers=1
[state] n=139,140   levels=3  NOT_FINISHED  layers=38   <- a second commit
```

The engine holds `levels_completed = 3` across both commits. idx3 genuinely does not advance,
so nothing is being mis-read, and the walk spends TWO commits there rather than one.

Re-captured fresh, the last spill still enters every mouth:

```
layers 27
target 0 mouth (13,7)  entered True
target 1 mouth (13,10) entered True
target 2 mouth (13,13) entered True
```

So the measured fact, now twice: **on idx3 every mouth is entered in a single spill and the
level does not advance, while on idx0 entering both mouths clears it.** The two boards are
structurally alike where it matters — same five-cell targets, same central mouth, same
satisfaction geometry when a droplet steps from the mouth onto the target's body.

Whatever idx3 wants, it is not "enter every mouth". The fourth region is one candidate with a
refuted first test; the two commits are a second thread worth pulling, since a level that
resets between commits would make a two-commit plan unable to finish what a one-commit plan
starts — except that the LAST spill alone enters all three, which argues against it.


## The engine recoloured all three, and idx3 still did not clear (2026-08-24)

`changed_regions` is the engine's own satisfaction signal — regions that take on a stable new
appearance while a spill runs — so it says what the ENGINE counted, not what the model claims.
Read across the whole walk:

```
idx0   28 layers -> 2 changed [(13,4), (13,10)]  sizes [5, 5]     both targets
idx1   28 layers -> 2 changed [(1,3), (1,11)]    sizes [5, 5]
idx2   25 layers -> 2 changed [(1,6), (1,12)]    sizes [5, 5]
idx3   33 layers -> 1 changed [(13,6)]           size  [5]        one target
idx3   38 layers -> 1 changed [(13,6)]           size  [15]       <-
```

Fifteen cells starting at (13,6), and the three targets hold exactly fifteen:

```
(13,6) (13,8) (13,9) (13,11) (13,12) (13,14)
(14,6) (14,7) (14,8) (14,9) (14,10) (14,11) (14,12) (14,13) (14,14)
```

They recolour to the same appearance and become ONE connected region, which is why the count
reads 1 and the size reads 15 rather than three regions of five. **So the engine satisfied all
three targets on the final spill, and `levels_completed` stayed at 3.**

That is the strongest fact this thread has produced, and it puts the fourth region back as the
leading answer — on evidence rather than by elimination. The block was NOT among the changed
regions, so the engine did not count it, and the level did not advance while it stood
unsatisfied.

What the earlier block test actually refuted is narrower than it looked: **roof contact does not
satisfy the block**, and our propagator can only ever deliver roof contact, because it deflects
flow around an absorber and never enters one. The claim "the fourth region is no longer the
leading answer" was too broad and is withdrawn — the region is exactly the leading answer; what
is unknown is how the engine wants it filled.


## idx3 carries an embedded source, and the block has never been seen to recolour (2026-08-24)

Two facts about idx3 that had not been stated, both read off the board's own appearances.

**A single cell wears a colour nothing else on the board wears.**

```
colour histogram   12: 187 (background)   1: 31   11: 19   8: 14   9: 4   4: 1
colour 4           [(7, 4)]   — inside piece 2, which spans (7,2)..(7,6)
```

That is the embedded-source signature this round already named: a cell inside a piece that
does not wear the piece's appearance, so the source travels when the piece does. The board
holds it (`emitter_cells = [(7,4)]`) and the propagator seeds from it — a droplet starts at the
cell below, at tick zero. **Piece 2 is the only piece on this board whose motion moves a
source**, and the block sits at columns 2 and 3, within its reach.

**The block has never once been observed to recolour.** `absorbers()` justifies its whole
existence on the claim that a solid block wearing the target appearance "is satisfied by the
ENGINE — it recolours when the spill reaches it". Across every spill of every level in this
session, the engine's own satisfaction signal never names it:

```
changed regions naming (13,2): 0 occurrences, across all spills of all four levels
```

Including the block test, where flow reached (12,2), the cell directly on its roof.

That does not refute the claim — it was measured somewhere, and roof contact may simply not be
the contact that does it — but it does mean the claim is currently carrying the round's
interpretation of idx3 without a single observation in this session behind it. The two live
possibilities are now:

* the block is a fourth requirement that wants filling in a way no layout has yet produced —
  and the embedded source is the obvious instrument, since it is the only stream that can be
  aimed by moving a piece; or
* the block is exactly what `absorbers()` says it is, idx3 stops for another reason entirely,
  and the fourth-region reading has been an attractive story fitted to a single board.


## The block CAN be filled, and the embedded source is what fills it (2026-08-24)

The last entry left two live possibilities and a named instrument. The experiment: make the
block the SOLE target under `contact`, so the compiler has to find a layout that actually
delivers flow to it rather than one that satisfies three other things and grazes it.

```
[block-only] plan SOLVABLE offsets=((0,0), (0,0), (0,1), (0,0), (0,0))
[changed]    32 layers -> [(13,2), (13,6)] sizes=[4, 5]
idx3: stopped — executed the plan without clearing (24 actions)
```

**The 4-cell region at (13,2) is the block, and the engine recoloured it.** So:

* `absorbers()`'s claim is no longer unobserved — the block IS satisfied by the engine, and
  this session has now seen it;
* the piece the plan moved is **piece 2, the one carrying the embedded source at (7,4)** — the
  only piece on the board whose motion moves a stream, exactly the instrument the last entry
  named;
* the level still did not clear, because this layout fills the block and only ONE of the three
  targets.

So idx3 wants four regions, each of which is now known to be individually fillable, and no
layout tried so far fills all four at once.

One thing this exposes about the model rather than the game: under `contact` the propagator
believes roof contact satisfies the block, so when all four were offered as targets it chose a
layout that merely grazed it — and the engine counted three. With the block alone to satisfy,
the same compiler had to work for it and found a layout that really delivers. **The model's
`contact` is more permissive than whatever the engine actually requires**, which is why the
four-target test looked like a refutation and was not.


## Correction: the final frame is not a satisfaction signal, and all four regions recolour (2026-08-24)

Two entries ago the four-target test was read as "the block did not recolour", from the board's
appearance AFTER the spill. That reading is **invalid**, and the captures say so themselves:

```
r98last  block [11,11,11,11]  target0 [11,11,11,11,11]
```

`r98last` is the run where the engine demonstrably satisfied all three targets — the 15-cell
changed region. They read colour 11 afterwards anyway. **Satisfaction recolouring is transient**:
it happens during the animation and is gone by the last frame, which is exactly why
`changed_regions` exists and why reading the final board says nothing.

Re-run with the right signal, the four-target test says the opposite of what was recorded:

```
[block-test] plan SOLVABLE, predicted_satisfied 4
[changed] 38 layers -> [(13,2), (13,6)] sizes=[4, 15]
idx3: stopped — executed the plan without clearing (33 actions)
```

Four cells at (13,2) — the block — AND fifteen at (13,6) — all three targets. **Every region on
the board recoloured, and the level did not advance.** Reproduced twice in the same run.

So the fourth-region diagnosis is refuted after all, this time on the signal that can carry the
claim. And no hazard explains it either:

```
hazard_cells []      colour 1 is the FRAME — row 15 and column 15, 31 cells of it
```

idx3 recolours everything the board has and stays at `levels_completed = 3`. What that leaves
is a question about the SIGNAL rather than the board: `changed_regions` is defined as "regions
that took on a stable new appearance while a spill ran", which is what a satisfied target does —
but it is also what a region merely covered by flow would do. On idx0 the two readings coincide
and the level clears; idx3 is the board that separates them.


## idx3 is not won by covering its regions (2026-08-24)

Three measurements close this, and together they are airtight.

**What "satisfied" looks like.** Every region the engine satisfies goes from the target
appearance to one specific other appearance, on every level:

```
idx0/1/2  region size 5  was 11  became 13     (and 12 in passing, at the level change)
```

Colour 13 is the engine saying "this one is done".

**There is nothing hidden.** Across nine captures whose pieces stand in materially different
places — (7,2) vs (7,3) vs (8,0), (10,3) vs (10,8) vs (10,9) — the set of target-coloured cells
is IDENTICAL:

```
19 cells in every capture, union 19, cells missing from any one capture: none
```

So idx3 has exactly nineteen target-coloured cells: three five-cell targets and the four-cell
block. No target sits hidden under a piece.

**All nineteen get satisfied, in one spill, and the level does not advance.**

```
[block-test] plan SOLVABLE, predicted_satisfied 4
[hue] region at (13, 2) size=4  was 11 became [13]
[hue] region at (13, 6) size=15 was 11 became [13]
idx3: stopped — executed the plan without clearing
```

Reproduced twice in one run. `levels_completed` holds at 3, and `hazard_cells` is empty.

**So idx3's win condition is not "satisfy every target-coloured region".** That is a finding
about the family's OBJECTIVE vocabulary, and a sharper one than the schema-gap story it
replaces: the gap is not a missing predicate for one odd region, it is that `CoverAllSinks` —
in any of its encodings — does not describe what this level wants. Covering everything the
board offers is measurably not enough.

What idx3 wants instead is unknown, and the honest position is that it is unknown. The round
has now spent several ticks generating attractive explanations for this level and refuting each
one with a better measurement; the pattern worth carrying forward is that every refutation came
from finding the signal the engine actually emits, not from arguing about the board.


## Everything is full, held for eight layers, and then the board is put back (2026-08-24)

If satisfaction is transient, perhaps idx3 wants all four regions full at the SAME MOMENT.
Tracked per layer, with a region counted full only when every one of its cells reads 13:

```
layer 23-26   ['block']
layer 27-28   ['block', 't0']
layer 29-36   ['block', 't0', 't1', 't2']     <- all four, eight consecutive layers
layer 37      block [11,11,11,11]  t0 [11...]  t1 [11...]  t2 [11...]
```

So simultaneity is achieved and held, and the level still does not advance. That hypothesis is
refuted like the others — but the last line is new and it changes the shape of the question.

**On the final layer the whole board reverts to 11.** Not one region draining, not a partial
decay: every target-coloured cell goes back to how it started. Compare idx0, where a clearing
spill's regions end up at 12 — the background of the NEXT level's board.

```
idx0 (clears)      regions become [12, 13]   ends on a different board
idx3 (does not)    regions become [13]       ends on the SAME board, restored
```

So idx3's attempt is not being left incomplete — it is being **REJECTED and put back**. The
engine filled everything the board has, held it for eight layers, and then undid the attempt.

That reframes the question from "what else must be filled" to "what makes this attempt
invalid". Nothing about coverage can answer it: coverage was complete and held. The remaining
candidates are properties of the ATTEMPT rather than of the regions — where a piece ended up,
what the flow touched on the way, or the state the commit was made in — and none of them is
measured yet.

Recorded as the state of the thread rather than as another explanation. This level has now
refuted five in a row, each one plausible until the engine's own signal was read.


## Correction: the final-layer revert happens on CLEARING spills too (2026-08-24)

The last entry read idx3's final layer — every target-coloured cell back to 11 — as the engine
REJECTING the attempt and putting the board back. That reading is wrong, and the same probe run
across every level says so:

```
spill#2  28 layers  L24-26 flow=36 sat=10 tgt=0   L27 flow=1  sat=0 tgt=10   <- idx0, CLEARS
spill#12 38 layers  L34-36 flow=63 sat=15 tgt=0   L37 flow=0  sat=0 tgt=19   <- idx3
```

`sat` counts cells at the satisfied appearance, `tgt` cells still at the target appearance.
idx0's clearing spill ends exactly the same way: satisfaction gone, every target cell back to
11, flow drained. **The revert is how every spill ends, not a verdict on it.** "The attempt is
rejected and put back" is withdrawn.

Two things from the same run are worth keeping, since they are the first numbers that separate
the levels rather than describing them:

* On the plain walk idx3 reaches `sat=15` — its three targets — and the block's four cells are
  never satisfied; at L35-36 they read neither 11 nor 13 but are covered by FLOW.
* Every level's spill ends with the flow drained to 0-3 cells, so "the flow must finish" is not
  a candidate: it finishes everywhere.

The question from two entries ago stands unchanged and unanswered — in the four-target run all
nineteen cells DO reach the satisfied appearance simultaneously and the level does not advance —
but it no longer has a rejection story attached to it. This is the sixth explanation this level
has taken away.


## Reconfirmed, and one candidate eliminated (2026-08-24)

After several readings that turned out to be wrong, the load-bearing fact was re-measured with
the simplest possible instrument — count cells at the satisfied appearance, no region logic:

```
[block-test] plan SOLVABLE, predicted_satisfied 4
[drain] spill#12 38 layers | L34 flow=64 sat=19 tgt=0 | L35 sat=19 | L36 sat=19 | L37 sat=0
[drain] spill#13 38 layers | identical
idx3: stopped — executed the plan without clearing (33 actions)
```

Nineteen — every target-coloured cell the board has — at the satisfied appearance for three
consecutive layers, reproduced across two spills in one run. The fact stands on two independent
probes now: one counting whole regions, one counting bare cells.

And a candidate is gone. If idx3 were the FINAL level, completing it might set a win state
rather than incrementing `levels_completed`, which would explain a clear that does not look like
one. It is not the final level:

```
sp80's `levels` list: 6 entries
```

idx3 is the fourth of six. The walk clears three of them, and the game has two more beyond the
one that is stuck.


## Read at last: advancement needs a FLAG to be clear, not just the targets (2026-08-24)

Six explanations had been refuted by measurement and the observations were unambiguous, so the
game source was read — dev-time only, the way this round already read it to count levels.
**Nothing here may enter the runtime path**; it is recorded to explain a measurement, and
anything built on it needs its own observational confirmation first.

The level advances on exactly one condition:

```python
zmkiirynyo = all(r in <satisfied> for r in <targets>)
if self.<flag> or not zmkiirynyo:
    ...failure animation, then lose() when lives run out
else:
    complete_action(); next_level()
```

So advancement is **every target satisfied AND a flag clear**. That is why nineteen satisfied
cells held for three layers does not clear idx3: the flag is set. Every explanation this round
tried was about the targets, and the targets were never the problem.

The flag is set in one place — when the flow reaches a sprite carrying a particular tag, which
then recolours to 14 and joins the flashing set. So the family has a **failure entity** that is
neither a target nor a barrier as the schema models them: contact with it does not stop the
flow, it invalidates the attempt.

Observational confirmation is OWED and is not yet in hand. Scanning every layer of every action
for that appearance finds only whole edge rows — (15,0)..(15,15) and (0,0)..(0,15) — on the
levels that CLEAR, which is the frame's transition flash, not a sprite. idx3 shows no such cell
at all. The likely reason is that the failure animation plays out over the actions AFTER the
commit and the walk stops before pressing again; the test is to keep pressing and watch. Until
that is measured, the source explains the observation but has not been confirmed by one.

**What this changes for the schema**: `hazard_policy` and `hazard_response` both describe what
flow does when it MEETS a barrier. Neither can express an entity that lets the flow through and
fails the attempt afterwards. That is a family-level finding about the objective vocabulary, and
unlike the notchless-region question it is not about one odd board.


## The edge-row flash is FAILURE, not a transition (2026-08-24)

The last entry owed an observation: keep pressing after a failed commit and watch for the
flash. Done, by committing repeatedly from a fresh game rather than driving the walk:

```
[14] s0 act=5 layer=14/22  n=16  edge_row=True  (15,0)..(15,15)
[14] s1 act=5 layer=14/22  n=16  edge_row=True
[14] s2 act=5 layer=14/22  n=16  edge_row=True
[14] s3 act=5 layer=14/22  n=16  edge_row=True
levels now: 0   state: GameState.GAME_OVER
```

**Every one of those commits FAILED** — `levels_completed` never left 0 — and every one flashed
the bottom edge row in colour 14, inside the failing spill at layer 14 of 22. So the previous
entry's reading is corrected: the edge-row 14 is not a level-transition effect that happens to
appear on levels which clear, it is **the failure flash itself**, and it appears on the commit
that fails.

Two more facts fall out of the same run:

* **four failed commits end the game** — `GAME_OVER` after the fourth, with every subsequent
  action returning zero frame layers. The game gives four lives, which is the budget any plan
  is spending against.
* the flash sits at a fixed depth in the spill (layer 14 of 22 every time), so it is part of the
  scripted consequence rather than a reaction at the moment of contact.

Which sharpens the failure entity from the source into something with an observable location:
the row that flashes is the board's bottom edge. The leading reading is that **flow reaching
the floor invalidates the attempt** — which the schema cannot express at all, since `boundary`
describes what the flow DOES at an edge and never that arriving there fails the attempt.

That reading is not yet confirmed: idx3's spills show no colour-14 cell anywhere, and the source
flashes 14 and 1 on alternating steps, so an even step would flash in the frame's own colour and
be invisible to this probe. The next measurement is to look for the alternation rather than for
14 alone.


## idx3 was never being judged — the game was already over (2026-08-24)

Looking for the failure flash by watching the bottom row CHANGE rather than by hunting colour
14 (the source alternates 14 and 1, and 1 is the frame's own colour, so half the flashes are
invisible to a 14-only probe):

```
spill 22 layers: bottom row -> [14] at layers 14, 16, 18, 20     FAILURE
spill 28 layers: bottom row -> [14] at layers 16..22             FAILURE
spill 20 layers: bottom row -> [4, 12] at the last layer         the NEXT level's board
spill 22 layers: bottom row -> [4, 12] at the last layer
spill 25 layers: bottom row -> [1]  at the last layer
idx3's 33- and 38-layer spills: the bottom row never changes at all
```

So idx3's spills show neither the failure flash nor a next-level board. Which prompted the
obvious thing nobody had done: **press once more after the walk stops.**

```
=== after the walk ===
press 0: levels=3  state=GameState.GAME_OVER  layers=1
press 1: levels=0  state=GameState.GAME_OVER  layers=0
```

**The game was already over.** The walk spends the four lives on its way down — the two failure
flashes above are on idx0 — and by idx3 there is nothing left to spend. Every explanation this
round built for idx3 was an explanation of a level that was never going to be judged.

That is the seventh thing this level has taken away, and the first one that was our own doing
rather than a gap in the model. The measurable consequence is a REAL constraint the round had
not been counting:

**A run has four failed commits for the whole game, not per level.** Probing spends them. The
walk's discovery deliberately spends one sacrificial commit per level, which on a six-level game
is most of the budget before anything is planned.

The next measurement is the honest version of the idx3 question: reach idx3 with lives left, and
see whether the plan that satisfies all nineteen cells clears it.


## A commit is not free, and the walk was spending one on nothing (2026-08-24)

With the four-lives-per-game constraint in hand, the walk's own spending was read. Each level's
discovery makes TWO commits: one unaimed, to reveal the flow's colour, source and direction, and
one after aiming the piece at the source's lane. The second one fires unconditionally — even
when the aiming loop breaks immediately because the lane is already covered and nothing moved.

That is a life spent to re-observe a board that did not change. Gating it on whether the aiming
actually moved something:

```
before   press 0 after the walk: GAME_OVER
after    press 0 after the walk: NOT_FINISHED, a 38-layer spill
         press 1:                GAME_OVER
```

One life recovered, and idx0-idx2 still clear at the same depth (138 actions vs 139). The walk
still reaches idx3 with nothing to spare, so this does not answer the idx3 question — but it is
the first repair to the thing that made the question unanswerable.

Worth naming as a rule the round had not been applying: **a commit is not free.** Everything
about the harness's discovery has been costed in ACTIONS, which are plentiful, and never in
FAILED COMMITS, of which a whole game gets four. Discovery that spends one per level has spent
most of the game before any plan runs.

Also measured while looking: each level builds a FRESH `FlowGrounding`, so every level re-learns
the flow's direction and colour from its own sacrificial commit — constants that cannot change
between levels of one game. That is three more commits spent re-learning what level 0 already
knew, and it is the next thing to cut.


## Why the unaimed commit has to stay (2026-08-24)

The obvious next saving was to aim BEFORE committing, the way the oracle gate does — it clears
idx0 on a single sacrificial commit while the walk spends two. Tried, and it recovers lives:

```
before   press 0 after the walk: NOT_FINISHED, press 1: GAME_OVER
after    press 0,1,2: NOT_FINISHED, press 3: GAME_OVER      three lives left
```

And it breaks idx3:

```
idx3: stopped — grounding incomplete (pieces=5, targets=3)
[slot] board UNKNOWN; missing=['barriers', 'initial_direction']
```

Aiming first puts the piece under the source, so the flow meets it immediately and spreads —
and the spill never shows a clean fall. `initial_direction` comes back UNKNOWN, `barriers`
early-returns without a direction, and the board will not assemble at all.

So the unaimed commit is not waste: **it buys the only clean directional evidence there is**,
and a life is what it costs. Reverted, with the reason written where the commit is made rather
than in a round page nobody will read at the moment they are tempted to remove it again.

The gate gets away with aiming first because idx0's geometry still shows the fall. That is a
property of one level, not of the family, which is exactly the kind of thing that looks like a
general saving until it is measured on a second board.


## With a life in hand and all nineteen satisfied, idx3 shows no verdict at all (2026-08-24)

Recovering one life changed what can be asked. Re-run with the block variant:

```
[drain] spill#11 38 layers | L34 sat=19 | L35 sat=19 | L36 sat=19 | L37 sat=0
=== after the run ===
press 0: levels=3  state=NOT_FINISHED  layers=38     <- a life was still there
press 1: levels=3  state=GAME_OVER
```

So the commit that satisfied all nineteen cells was made on a **living** game, and the level
still did not advance. The "it was already over" explanation no longer covers it.

Which puts the flag back in play — advancement is all targets satisfied AND a flag clear, and
the flag is set by flow reaching a tagged sprite that flashes. So the flash was hunted for
anywhere off the frame:

```
spill 28 layers (idx1)  row 0 flashes 14 at layers 16..26      a FAILURE
spill 29 layers (idx2)  row 0 flashes 14 at layers 14..27      a FAILURE
spill 33 layers (idx3)  nothing flashes off-frame
spill 38 layers (idx3)  nothing flashes off-frame
```

**idx3 shows neither verdict.** No failure flash, no next-level board. The engine's decision
code runs only once the flow has finished — a later action than the one that starts the spill —
and the walk stops before pressing it. Pressing once more re-runs a 38-layer spill rather than
resolving, so the resolving action is not the commit action either.

That is the state: with lives, with everything satisfied, idx3 is neither passed nor failed
within anything observed so far. The next probe is to find the action that makes the engine
render its verdict, rather than to explain a verdict that has not been given.


## The verdict WAS given: idx3's commits fail (2026-08-24)

The last entry said idx3 shows neither verdict. Pressing every action after the run settles it:

```
action 1: levels=3  NOT_FINISHED  layers=1     a move
action 2: levels=3  NOT_FINISHED  layers=1
action 3: levels=3  NOT_FINISHED  layers=1
action 4: levels=3  NOT_FINISHED  layers=1
action 5: levels=3  NOT_FINISHED  layers=38    the spill runs again
```

Moves return a single layer, which means the board is back in its ARRANGE phase — the spill had
already resolved and the board had already been restored. **The verdict was given and it was a
failure.** "idx3 gives no verdict" is corrected; what idx3 gives no sign of is the FLASH.

So the position is now exact, and it is a contradiction that belongs to the model rather than to
the measurement:

* all nineteen target-coloured cells reach the satisfied appearance and hold for three layers;
* the game has a life left, so the attempt is judged;
* the attempt FAILS, which by the engine's own condition means the flag is set;
* the flag is set by flow reaching a tagged sprite that flashes — and on idx3 nothing flashes
  anywhere off the frame, while idx1 and idx2 failures flash row 0 plainly.

Every one of those is measured. The one that must give way is the assumption that the flashing
sprite is visible as a flash on every board: on idx3 the entity may be covered by flow at the
moment it is touched, since flow overwrites appearance, or it may sit under a piece the way that
level's source does. Both are checkable, and neither is checked yet.


## Nothing is left marked, and the flash has a budget (2026-08-24)

Comparing the board before and after a failing 38-layer spill on idx3 — the whole board, not a
chosen region:

```
cells differing first -> last = 5
   (4,4) (4,5) (4,6) (4,7):  8 -> 9      the piece becomes SELECTED again
   (8,5):                    6 -> 12     one flow cell clears to background
```

That is all. **No entity is left marked** by a failing attempt: the flash is transient and gone
by the last layer, and there is a standing flow cell at the start of the spill — the embedded
source's own droplet, one cell below the emitter — which clears at the end.

So "find the entity that flashed" cannot work by looking at the end state, and the mid-spill
hunt already found nothing on idx3 while finding row 0 plainly on idx1 and idx2. The reading
that fits, from the source: the failure branch flashes only while a counter is under six, and
each failure on a level advances it. idx3 takes several commits — a sacrificial one plus the
plan attempts — so by the later ones the flash budget is spent and the failure is SILENT.

That is source-derived and owed a measurement, and it is the first explanation offered here that
also explains why idx0's failures flashed and idx3's did not, rather than needing a separate
story for each.

It leaves the contradiction from the last entry standing and sharpened: nineteen cells satisfied,
a life in hand, the attempt failing, and no observable reason. What can still be measured is the
flash budget itself — fail a level deliberately several times and watch the flash stop.


## The engine paints its unsatisfied targets, and the block is one of them (2026-08-24)

The flash-budget reading was refuted first: failing idx0 four times in a row flashes identically
every time and then ends the game.

```
commit 0..3: NOT_FINISHED  22 layers  flash at layers 14, 16, 18, 20
commit 4:    GAME_OVER
```

So a silent failure is not a spent budget — and four failures end the game, confirming the life
count a third time.

Which sent the hunt to the OTHER half of the failure animation. The engine flashes two things: the
failure sprites it touched, and **the targets that were NOT satisfied**, painted in colour 0.
Looking for colour 0:

```
spill 28 (idx1)  layer 21: 5 cells   (1,7) (1,8) (1,9) (2,7) (2,9)
spill 29 (idx2)  layer 22: 10 cells  two target shapes
spill 33 (idx3)  layer 26: 14 cells  (13,2) (13,3) (14,2) (14,3)   <- THE BLOCK
                                     (13,9) (13,11) (14,9..11)     <- target 1
                                     (13,12) (13,14) (14,12)       <- target 2
spill 38 (idx3)  no colour-0 cell anywhere
```

**The block is one of the engine's targets.** Not inferred from its appearance, not argued from
the schema — the engine itself paints it as an unsatisfied target when the attempt fails. Every
earlier attempt to settle this failed because it looked at the board's colours instead of at the
failure animation, which is the only place the engine says what it was counting.

And the second line matters as much: on the spill where all nineteen cells are satisfied, **no
target is painted 0 at all**. So the engine agrees that everything it wants was satisfied — and
the attempt still failed, which by its own condition leaves only the flag, while nothing flashed
to say a failure sprite was touched.

Two measured facts that cannot both be complete. The next probe is the failure sprite itself:
find what it looks like on a board where it IS touched, then look for that entity on idx3.


## The failure entity is the FRAME BAND (2026-08-24)

What flashes on a failure, and what was it before?

```
idx0, first commit, layer 14: 16 cells at colour 14
   rows [15]   cols 0..15
   what they were before the spill: [1]
```

The whole bottom row, wearing colour 1 — **the frame**. So the entity whose contact fails the
attempt is the band this harness deliberately excludes from the board: `playable_size()` trims
the last row and column as "a frame drawn around the board", and `barriers()` was fixed this
round to ignore anything in it because a hazard recorded outside the board still fires.

Both of those were right about what the flow DOES there and wrong about what it MEANS. Flow
reaching the frame does not die and does not deflect — it **fails the run**.

Checking which spills touch it:

```
spill 28 (idx1)  []
spill 29 (idx2)  flow at (1,15) (2,15) ... (8,15)     the right-hand column
spill 33 (idx3)  []
spill 38 (idx3)  []
```

idx2's failing spill runs eight cells down the frame's right column, which is exactly the shape
of a run that fails on contact. idx3's spills never touch it at all — and idx3 still fails, with
every target satisfied on the 38-layer one and nothing painted 0.

So the frame band is a real failure entity, measured, and it is not what stops idx3. Two things
follow. The model owes an entity it currently calls "not board" — and idx3 owes a third
explanation, since neither its targets nor the frame accounts for it.


## Our own discovery runs the flow into the failure entity (2026-08-24)

Measuring frame contact on EVERY spill, not just the big ones:

```
spill 22 (idx0 discovery)   []
spill 24 (idx1 discovery)   (1,15) ... (10,15)     ten cells down the frame's right column
spill 29 (idx2)             (1,15) ... (8,15)      eight
spill 25 (idx3 discovery)   (13,15)                one
spill 33 (idx3 plan)        []
spill 38 (idx3 plan)        []
```

**The unaimed sacrificial commit runs flow into the frame on three levels out of four.** That is
the entity whose contact fails an attempt, so the harness's own discovery is not merely spending
a life by failing to satisfy targets — it is spending it by hitting the one thing that fails a
run outright.

idx1 and idx2 clear anyway, which settles a question the last entry left open: **the flag resets
per attempt.** Frame contact costs that commit and nothing more. A run's four lives are the
budget it eats into, which is the same conclusion reached from the other direction earlier, now
with the mechanism attached.

And it sharpens what is left of idx3. Its plan spills touch nothing — no frame, no unsatisfied
target painted 0, every one of the nineteen cells satisfied — and they still fail. Neither of
the two failure causes the engine has is present, which is now a statement about the two causes
rather than about idx3.


## The failing spill contains no failure colours at all (2026-08-24)

Every colour present in idx3's 38-layer plan spill, and which layers each appears on:

```
1  frame             all 38 layers
4  embedded source   all 38
6  flow              37 layers
8  piece (idle)      all 38
9  piece (selected)  layer 37 only
11 target            30 layers
12 background        all 38
13 SATISFIED         layers 23..36
```

**Colour 14 never appears. Colour 0 never appears.** Those are the two the engine paints when an
attempt fails — the touched failure sprite, and the targets left unsatisfied. Neither is in the
spill, on any layer.

So the failure animation does not run. And yet, measured earlier in the same run: the board is
restored to its arrange phase afterwards, and `levels_completed` stays at 3.

That is the sharpest form the idx3 question has taken. The engine has exactly two ways to refuse
an attempt and it is using neither, while also not accepting it. Everything visible says the
attempt should have been accepted: all nineteen target cells reach 13 and hold for fourteen
layers, no target is painted 0, no frame cell carries flow, and a life is in hand.

Recorded as measured rather than explained. Seven readings of this level have now been refuted,
and the one thing every refutation has had in common is that it was built on what the board
looked like rather than on what the engine did — so the next step is not another reading of the
board.


## The engine's own list: FOUR targets (2026-08-24)

The last entry said the next step was not another reading of the board, so the engine's own
objects were read — dev-time only, the same standing as reading the level count and the
completion condition.

```
[engine] n=129 targets=4 at [(17,2), (17,16), (17,8), (17,12)]  satisfied=0  flag=False
[engine] n=138 targets=4 at the same four                        satisfied=0  flag=False
[engine] n=139 targets=4 at the same four                        satisfied=0  flag=False
```

**Four targets, and the flag is False.** So the block being a target is now confirmed twice over
and from two directions: the failure animation paints it as unsatisfied, and the engine's target
list has four entries. And the flag — the other of the engine's two refusals — is clear at every
one of idx3's commits.

The satisfied count reads 0 because the read happens after the step returns, by which time the
engine has already reset for the next attempt; it is not evidence that nothing was satisfied.
Getting the count AT the decision needs a hook inside the step, which is the next instrument.

One discrepancy worth carrying: the four targets sit at x = 2, 8, 12, 16 — evenly spaced by four
— while our grounding places them at columns 2, 6, 9 and 12, which is not evenly spaced. The
units are not the same (these are sprite coordinates, y = 17 for all four), so this is not yet a
contradiction, but it is the first sign that what we call a target and what the engine calls one
may not be the same partition of those nineteen cells.


## idx3 is never judged: its spill never settles (2026-08-24)

Hooking the engine's own completion call and filtering for the SPILL phase — the only place the
level decision is made — gives three lines for a whole run:

```
targets=2  satisfied_of_them=2  flag=False  phase=spill  settled=True     idx0
targets=3  satisfied_of_them=3  flag=False  phase=spill  settled=True     idx1
targets=3  satisfied_of_them=3  flag=False  phase=spill  settled=True     idx2
```

Three decisions, three cleared levels. **idx3 never reaches one.** Every other completion call in
the run is in the arrange phase with `settled=False`.

So the engine never evaluates idx3. `settled` becomes true only once the flow has finished, and
on idx3 it does not — which is why the failing spill carries no failure colour, why nothing is
painted 0, why the flag stays False, and why nineteen satisfied cells change nothing. The level
is not refused. **It is never asked.**

That is the third explanation, and unlike the six before it, it comes from the engine's own state
rather than from the board's appearance — which is exactly what the last entries kept concluding
was needed.

What keeps the flow alive is the obvious suspect and is already named: idx3 is the only level
with an EMBEDDED SOURCE, at (7,4), inside the one piece whose motion moves a stream, and its
spills begin with a standing flow cell one below the emitter. A source that keeps emitting is a
flow that never finishes.

That last step is a hypothesis, not a measurement. What is measured is that idx3 is never judged.


## The silent failure is a spent flash counter — and the earlier refutation was wrong (2026-08-24)

Reading the engine's own spill state through idx3:

```
n=125..128  phase=change  settled=False  active=0  flashstep=0
n=129       layers=33     ...                      flashstep=6     <- after the first plan commit
n=130..137  layers=1      ...                      flashstep=6
n=138,139   layers=38     ...                      flashstep=6
```

`flashstep` is the counter the failure branch tests: below six it plays the flash, at six it
takes the other path — restore the board, lose a life if none are left, and complete the action
**silently**. On idx3 it reaches six and never resets.

So idx3's later commits DO fail, and they fail without a mark. **The flash-budget reading is
reinstated** — it was refuted two entries ago by failing idx0 four times and seeing an identical
flash each time, which was the wrong control: on idx0 the counter resets between attempts, so
that experiment could never have shown a spent one.

That correction matters more than the fact, because the refutation was itself measured and still
wrong. What made it wrong was choosing a control on the level where the mechanism does not bite.

It also narrows idx3 to one place. The silent path is inside `if flag or not all_satisfied`, and
the flag is measured False at every commit — so the engine is finding **not all targets
satisfied**, while the frames show all nineteen target cells at the satisfied appearance for
fourteen layers. Those two cannot both describe the same thing, which means colour 13 on the
board and membership of the engine's satisfied set are NOT the same fact. That is the next
measurement, and it is a small one: read the satisfied set during the spill rather than after.


## What the engine actually counts, and two of my readings corrected (2026-08-24)

The satisfaction rule, from the source, is exactly `same_sink_flanks` — and painting colour 13
and joining the satisfied set are **the same event**:

```python
if <target tag> in sprite.tags:
    if left is sprite and right is sprite:      # both flanks the SAME sprite
        sprite.pixels = 13
        self.<satisfied>.add(sprite)
```

So reading the set after a step could never work: the failure path restores the board before
completing the action, and the restore clears the set. Counting the ADDS instead, with positions:

```
plain walk, idx3     #1 (17,8)  #2 (17,12)  #3 (17,16)          size 3 of 4
block-targeting run  #1 (17,2)  #2 (17,8)   #3 (17,12)  #4 (17,16)  size 4 of 4
```

idx3's four targets sit at x = 2, 8, 12, 16. **The plain walk never satisfies x = 2 — the block**
— which is why it fails, and it is the first fully mechanical account of that failure.

Two of my own readings are corrected by the same probe:

* **"idx3's spill never settles" is WRONG.** The settle flag fires seven times in a run, twice on
  idx3, with the droplet count running down to zero each time. The spill settles.
* **"all nineteen cells satisfied" was measured on the block-targeting run only.** On the plain
  walk fifteen cells reach 13, not nineteen, exactly matching three targets of four.

Which leaves the sharp residue: in the block-targeting run all four ARE added, the set reaches
four, the flag is False, the spill settles — and the level does not advance. The only gap left
between those facts and the engine's advance condition is WHEN the set is read relative to the
reset, and that is a question about ordering rather than about the board.


## At idx3's settle the advance condition is fully met — and the engine resets instead (2026-08-24)

Evaluating the engine's own advance condition at the moment the spill settles, rather than after
the step returns:

```
idx0   targets=3 satisfied=3 all_in=True  same_objects=True     -> advances
idx1   targets=3 satisfied=3 all_in=True  same_objects=True     -> advances
idx3   targets=4 satisfied=4 all_in=True  same_objects=True     -> does NOT advance   (twice)
```

`same_objects=True` rules out the obvious suspect — the satisfied set holding stale sprites while
the target list returns fresh ones. They are the same objects. Every target is in the set. The
flag is False. **Every term of the engine's advance condition is satisfied at idx3's settle.**

And the ordering shows what happens instead:

```
RESET (was size 0)
SETTLED, satisfied size 4
RESET (was size 4)                                  <- the set is cleared
COMPLETE phase=change settled=False satisfied=0
```

On the levels that clear, the completion comes straight after the settle, in the SPILL phase,
with the set intact. On idx3 a reset lands between the two, and the completion that follows is in
the arrange phase with nothing satisfied and the settle flag already cleared.

So the level is not failing a condition. **The condition is met and the state is torn down before
anything reads it.** That is a statement about when the engine evaluates, not about what the plan
did — and it means no plan of ours can clear idx3 by satisfying more, because satisfying
everything is already what happens.


## Resolved: idx3 fails on an entity inside the band we discard (2026-08-24)

Reading the condition exactly as the DECISION sees it, rather than after the step returns:

```
[decide-in] targets=4  satisfied=4  missing=[]  flag=True  flash=6
```

**The flag is TRUE at the decision.** Every earlier reading of it as False was taken after the
step, once the engine had reset. So idx3 fails on the flag, with all four targets satisfied —
which is what the engine's condition says should happen, and what none of the board readings
could see.

Locating the entity that sets it, at the moment it is set:

```
3-target levels:  touched=1 at (15, 0)  tags=['waoewejnqzc']
idx3 (4 targets): touched=1 at (19, 0)  tags=['waoewejnqzc']
```

**One sprite, at the board's bottom-left cell.** Its y sits two below the targets' — 15 against
13 on the small levels, 19 against 17 on idx3 — which in board coordinates is the last row, and
its x is column zero.

That is inside `playable_size()`'s trim. The harness removes the last row and column as "a frame
drawn around the board", and this round additionally fixed `barriers()` to ignore anything there.
Both were measured and both are right about what flow DOES at that band. Neither could know that
one cell of it **fails the run on contact**.

The earlier frame probe missed it for a reason worth keeping: it looked for flow colour at row
15, and a `waoewejnqzc` cell recolours to 14 the moment it is touched — so the very event being
hunted erases the evidence the hunt was looking for.

So the idx3 thread resolves. Not a missing target, not a schema gap in the objective, not a
never-settling spill, not a spent life: **a failure entity living in the band the model discards,
which the flow reaches and which no plan of ours can avoid because the model cannot see it.**


## Correction: the failure entity's board position was inferred, not measured (2026-08-24)

The last entry placed the failure entity at "the board's bottom-left cell" by mapping sprite
coordinates onto board cells. That mapping was not measured, and the board says otherwise:

```
idx3, cell (15,0) across the whole 38-layer spill:
   [1, 1, 1, 1, ... 1]     colour 1 throughout, never 14, never flow
frame-band cells that CHANGE on idx3's spills:  {}
```

If the entity were that cell, being touched would recolour it to 14 — the engine does exactly
that — and nothing changes there at all.

What IS measured, from the sprite geometry:

```
targets        shape (2,3)   3-target level at y=13, x = 1, 7, 12
                             idx3          at y=17, x = 2, 8, 12, 16
touched sprite shape (1,32)  3-target level at (15, 0)
                             idx3          at (19, 0)
```

Targets are two rows by three columns and their x's match the board columns we see, so sprite
coordinates are close to board cells for them, with a row offset of four on idx3 (y=17 renders at
row 13). The touched sprite is **one row tall and thirty-two columns wide** — wider than the
sixteen-cell render — so it does not live in the same coordinate space as the targets, and
nothing about its board position follows from its sprite position.

So the resolution stands only in its measured half: **idx3 fails on the flag, with all four
targets satisfied, and the flag is set by contact with one sprite that is a full-width single-row
bar.** Where that bar is on the board, and why touching it leaves no visible mark on idx3 when
the same tag flashes plainly on the smaller levels, are both open.

Recorded rather than smoothed over. The claim was one inference past the evidence, which is the
same failure this round has now made several times — and the check that caught it was the cheapest
possible one: look at the cell the claim names.


## The sprite-to-board mapping, measured — and it is not the same on every level (2026-08-24)

Pinning the mapping on a level where the entity does flash, by reading the engine's target
sprites and the board's target cells in the same breath:

```
idx0 targets (sprite):  (13,4) (13,10)   shape (2,3)
idx0 target cells:      rows 13-14, cols 4-6 and 10-12
flash at layer 14:      row 15, all sixteen columns
```

**On idx0 sprite coordinates ARE board coordinates.** The sprite at (13,4) with shape (2,3)
occupies exactly rows 13-14 and columns 4-6. So the failure entity there — the touched sprite at
(15,0) — is board row 15, the bottom row, and the flash confirms it cell for cell.

That settles the small levels: **flow reaching the floor fails the run**, measured end to end,
with no inference in the chain.

idx3 does not share the mapping:

```
idx3 targets (sprite):  (17,2) (17,8) (17,12) (17,16)
idx3 target cells:      rows 13-14
```

An offset of four rows. Its touched sprite sits at sprite row 19, which under that offset is
render row 15 — the bottom row again — and that row shows colour 1 unchanged through the entire
spill.

So idx3's level is taller than the window the frames show, and its failure entity sits at the
window's edge or beyond it. That is a measured coordinate fact, and it explains why the entity
leaves no mark there while flashing plainly on idx0: **on idx3 we are not being shown it.**

What this costs the model is concrete. `playable_size()` decides the board's extent from the
frame alone, and on a level whose frame is a window that decision is about the window, not the
board. Every entity outside it is invisible by construction — including the one that fails the
run.


## Root cause: idx3 is a 20x20 level read as 16x16 (2026-08-25)

The "offset of four rows" was not an offset. Reading each level's own grid size beside the frame
it renders into:

```
level 0   raw frame (64,64)   grid (16,16)   inferred scale 4     correct
level 1   raw frame (64,64)   grid (16,16)   inferred scale 4     correct
level 2   raw frame (64,64)   grid (16,16)   inferred scale 4     correct
level 3   raw frame (64,64)   grid (20,20)   inferred scale 4     WRONG — the true scale is 3.2
```

**idx3 is a twenty-cell board rendered into the same sixty-four pixel frame**, so one cell is
3.2 pixels — and `_infer_scale` returns integers. A 20-cell board at 64px cannot be read by an
integer-scale reader at all; the blocks are not uniform, so the largest uniform block size it can
find is four, and the whole level is read as sixteen cells.

Everything this thread has been chasing follows from that one fact:

* the targets' "row offset of four" — 17 x 3.2 / 4 = 13.6, read as row 13;
* the failure entity at row 19 being invisible — it is outside the sixteen cells we resolve;
* the frame band we trim as decoration — rows 16 to 19 are real board;
* the grounding's fragility on idx3 throughout, and the piece appearances collapsing there.

So idx3 was never a modelling gap in the family's vocabulary. **It is a perception failure**, and
the harness's own `_infer_scale` docstring already warns about its sibling — accepting a scale
twice too large by excusing real content as overlay. This is the same class: an integer reader on
a non-integer board.

That is the largest single finding of this thread, and it is measured rather than reasoned: the
engine's `grid_size` says twenty, the frame says sixty-four pixels, and 64/20 is not an integer.


## How wide is the scale defect? Six of twenty-five, and that is a floor (2026-08-25)

The idx3 root cause is a perception failure, not a family one, so the obvious question is how
much of the card it touches. Every game's FIRST level, grid size against the 64-pixel frame:

```
NON-INTEGER SCALE   ar25 (21,21)   cn04 (20,20)   ka59 (45,45)
                    m0r0 (11,11)   tu93 (39,39)
ok                  bp35 8 · lf52 8 · sp80 16 · ft09 32 · vc33 32 · lp85 (32,19)
                    cd82 g50t ls20 r11l re86 s5i5 sb26 sc25 sk48 su15 tn36 tr87 wa30 dc22 — 64
```

**Five games fail on their first level alone.** sp80 passes here — its first level is sixteen —
and fails on its fourth, which is the whole point: **the property is per LEVEL, not per game**, so
a first-level survey is a floor and not a count. Any game whose later levels change grid can join
the list, exactly as sp80 does.

Two things worth stating carefully, because they are correlation and not demonstrated cause:

* four of the five — ar25, cn04, ka59, tu93 — are backlog games with long-standing walls, and the
  fifth, m0r0, is one of the six fully conquered. So this does not simply predict failure.
* it does mean that on those games every coordinate the harness computes is derived from a cell
  grid the engine does not use.

That answers the question the round should have asked earlier: the fix belongs in `_infer_scale`,
which is the entrance to every frame reading in the project, not in anything R98-specific. What
this thread bought is not a level — it is a defect in the perception layer, found by measuring a
level that refused eight explanations in a row.


## Not a scale error — a cropped window and a one-pixel entity (2026-08-25)

The previous entry called idx3 a 20-cell board read at the wrong scale. The pixels say otherwise:

```
row 60   runs (4, 4, 28, 4, 16, 4, 4)          every run a multiple of four
col 0    runs (4, 28, 4, 27, 1)                4-aligned, with ONE pixel left over
row 63   runs (0, 35), (14, 29)                colour 14 — the failure flash — at the last pixel row
```

Content is four-pixel aligned throughout, so **scale 4 is correct**. A 20-cell level at scale 4
would be 80 pixels; the frame is 64. So the frame is not a rescaling of the board — it is a
**window onto sixteen of its twenty cells**, and the offset of four that kept appearing is the
window's position: sprite row 17 shows at window row 13, sprite 19 at window 15.

Which relocates the failure entity into view after all. It sits at window row 15 — and the raw
pixels show colour 14 on **row 63 only**, the very last pixel row. Cell row 15 spans pixels 60-63,
so a flash one pixel tall is averaged away by cellification: the cell reads colour 1 for the whole
spill, exactly as measured, while the pixels underneath carry the mark.

So the defect is not the scale reader. It is that **an entity thinner than one cell is invisible
to a cell-based reading**, and this one is the entity that fails the run.

The previous entry is corrected: `_infer_scale` returns the right answer here, and the
first-level survey it prompted still stands on its own terms — six games whose grid does not
divide the frame are six games where the frame cannot be showing the whole board.


## The blind spot, closed: centre sampling misses the last pixel row (2026-08-25)

`_cellify` takes one pixel per cell — the centre:

```python
(r, c): grid[r * scale + scale // 2][c * scale + scale // 2]
```

At scale four, cell row 15 samples pixel row 62. And the flash lives one row below it:

```
pixel row 60   distinct [4, 12]    n14 = 0
pixel row 61   distinct [4, 12]    n14 = 0
pixel row 62   distinct [4, 12]    n14 = 0     <- the centre sample
pixel row 63   distinct [0, 14]    n14 = 29    <- the failure flash
```

**Twenty-nine pixels of the failure mark sit on the one row the reader never looks at.** That is
the whole blind spot, measured end to end: the entity is one pixel tall, it occupies the last
pixel row of its cell, and centre sampling resolves that cell to the colour of the three rows
above it.

So every claim in this thread that "the cell shows colour 1 throughout" was true and also
uninformative — the cell was never carrying the answer, the pixel row below the sample was.

This is where the idx3 investigation lands. Not a family vocabulary gap, not a scale error, not a
window position: **a sub-cell entity and a one-pixel sampler that cannot see it.** Everything else
this thread produced — the walk reach, the straddling source, the neighbour's roof, the appearance
collapse, the false hazards, the four-lives budget — was found on the way and stands on its own.

⛔ Not fixed here on purpose. `_cellify` is the entrance to every frame reading in the project;
changing what a cell's colour MEANS would move every measurement in every round at once, and it
needs its own round with its own controls rather than a patch at the end of this thread.


## The fill experiment is now verified without a GPU (2026-08-25)

The fused-hazard variant was built and its wiring checked by hand, but the harness self-test only
ever ran the SPLIT default — so the experiment the round owes would have first been exercised on
a GPU with nothing having tested it. Added as a self-test case, driven by a stub that answers the
way the fused ask asks: no `hazard_policy`, because the fused objective ask never offers one.

```
fill  fused  -> hazard=fused  outcome=cleared  PASS
```

Two defects in the stub had to be fixed before it meant anything, and both are worth keeping:

* the first version round-tripped BOTH answers through JSON, mangling the slot answer into an
  `out_of_vocabulary` rejection. It now touches only the reply that actually carries the key.
* the second version built a fresh `_truthful_stub("fill")` on every call. That stub is
  **stateful** — it answers the variant ask and then the slot ask, in order — so rebuilding it per
  call replayed the first answer twice, and the run recorded the objective answer in the slots
  field. One stub, created once.

The second is the more interesting failure: the probe looked correct, ran without error, and
produced a confident wrong result, which is the same shape as the instrumentation defects this
round has already caught twice. What exposed it was printing the recorded answers rather than the
verdict.

So the FILL experiment is ready end to end: fused ask verified to omit the policy, derivation
verified to fire only when it was not asked, split path verified unchanged, and the whole thing
now covered by the self-test that runs on every gate. What remains is GPU time.


## How wide is the sub-cell blind spot? Two games of twenty-five (2026-08-25)

If a cell's colour comes from one pixel, anything thinner than a cell can hide. Comparing a
centre-sampled reading of each game's first frame against one that looks at every pixel of every
cell:

```
scale 1   ar25 bp35 cd82 cn04 dc22 g50t ka59 lf52 lp85 ls20 m0r0 r11l re86
          s5i5 sb26 sc25 sk48 su15 tn36 tr87 tu93 wa30      missed: none
scale 2   ft09                                              missed: none
scale 2   vc33                                              missed: [7]
scale 4   sp80                                              missed: [14]
```

**Twenty-two of twenty-five games read at scale one** — one pixel per cell — so nothing can hide
from the sampler by construction. The blind spot is only possible on the three games whose cells
are larger than a pixel, and it is real on two of them.

sp80's missing colour is 14, the failure flash this thread spent the evening chasing. **vc33's
missing colour 7 is new** and was not being looked for: something in that game's first frame is
present in the pixels and absent from every cell the harness resolves.

That is the honest size of the defect: not a systemic blindness, but a narrow one that happens to
sit on exactly the entity that decides whether a run succeeds. It also explains why the rest of
the project never tripped over it — at scale one the question cannot arise.

vc33 is recorded as an open item rather than chased now. What it is, and whether it matters to
that game's long-standing wall at one level, is a measurement of its own.


## The fused experiment is wired into the Kaggle kernel (2026-08-25)

GPU work goes to Kaggle, so the fill experiment needed to be runnable there rather than only from
a local flag. The bench notebook ran two modes; it now runs three:

```python
for mode, hazard in (("select", "split"), ("fill", "split"), ("fill", "fused")):
```

`select` and `fill` are untouched — the contract is frozen on the split encoding and their
outputs keep the same filenames, so the existing measurements stay comparable. The third writes
`r98_flow_fill_fused_<model>.json` and lands in the same summary under its own key, so a run
produces the frozen verdict and the experiment side by side without either standing in for the
other.

What it will answer, per model and paired as the contract requires: whether gemma4's single
missed slot is our ENCODING — the same question asked twice, once as `hazard_policy` and once as
`hazard_response` — or its reasoning. gpt-oss resolving the split 3/3 is what makes the question
worth asking rather than a reason to re-cut the schema.

Ready to run: the CLI is present with credentials, the kernel boots vLLM on a mounted model and
drives the live env, and the whole path is covered by the harness self-test so no GPU minute is
spent on unverified wiring.


## vc33's hidden colour is the same shape of thing (2026-08-25)

The survey turned up a second game whose pixels carry a colour no cell reports. Measured:

```
vc33  scale 2, 32 cells
   cells containing colour 7: 32 — all of row 0, each 2 of its 4 pixels
   pixel row 0: distinct [7], 64 of 64          <- a solid one-pixel band
   pixel row 1: distinct [0, 3]                 <- the centre sample for cell row 0
   after an action, pixel row 0 is still [7]
```

**A one-pixel band along the top edge, and the sampler reads the row beneath it.** Structurally
identical to sp80's failure flash on the bottom pixel row — same cause, opposite edge, and this
one persists across actions rather than appearing during a spill.

That it persists is what makes it different in kind: a standing band that never changes is a
status strip, not an event. `_infer_scale`'s docstring already names this — "a status bar drawn
over the outermost pixel row or two is a rendering overlay rather than board structure" — and it
excludes such rows from scale inference on purpose.

So vc33's hidden colour is explained and is not a defect: the harness knows about edge strips and
deliberately looks past them. sp80's is the one that matters, because there the band is not a
strip — it changes, and the change is the verdict.

Which sharpens the finding from the survey. The blind spot is not "two games have hidden colours".
It is: **the centre sampler cannot distinguish a decorative edge strip from an edge entity that
carries meaning**, and it resolves both to the row beneath. On twenty-two of twenty-five games the
question never arises because a cell is a pixel; on vc33 the answer happens to be harmless; on
sp80 it is the thing that decides the run.


## Telling decoration from event, without knowing the game (2026-08-25)

If an edge band can carry meaning, the harness needs a way to tell which ones do. "It changes" is
the obvious rule and it is wrong. Counting how many DISTINCT states each outer pixel row takes
over fourteen actions:

```
sp80   top 14 states   bottom  2 states
vc33   top  1 state    bottom  1 state
ft09   top  1 state    bottom 14 states
```

`sp80`'s top changes on essentially every action — that is a counter, not an entity — and `ft09`
has the same thing at the bottom. `vc33` never changes at either edge: static decoration. And
`sp80`'s bottom takes exactly **two** states: the baseline, and the failure flash.

So the discriminator is not change but **how much** change:

```
one state     static decoration — a border or a fixed strip
many states   a counter or clock, changing with every action
few states    an EVENT — it means something, and it is rare
```

Three games, three different answers, and the one whose band decides the run is the only one with
a low-but-nonzero count. That is an observational rule: it needs no knowledge of the game, only a
handful of actions and a count of distinct rows.

Worth stating as a limit too — three games is three games. The rule is proposed on the only three
games where the question can arise at all (the rest read at scale one, where a cell IS a pixel),
so it is exhaustive over the cases that exist rather than a sample, but it has never been tested
against a fourth kind of edge band because none exists here.


## The fill measurement is running on Kaggle (2026-08-25)

Pushed and running. What went up:

```
dataset  jaehyukhyun/admorphiq-src        new version — the package and the probe as they
                                          stand after this session's grounding fixes
kernels  admorphiq-r98-flow-gemma4        version 5, RUNNING
         admorphiq-r98-flow-gptoss        version 5, RUNNING
         admorphiq-r98-flow-qwen38        BLOCKED — "Maximum batch GPU session count of 2"
```

Each kernel now runs three modes rather than two: `select` and `fill` on the frozen split
encoding, unchanged, plus `fill_fused`. So one run yields the contract's verdict and the
experiment beside it, and the two cannot be confused because they land under separate keys and
separate filenames.

The pair the contract names is gemma4 and gpt-oss, and those are the two that are running.
qwen3.8 goes up when a slot frees — it is the extra model that matched the contract pair on
select at first outing, not a required leg.

One packaging trap paid for itself: `kaggle datasets version` **silently skips directories**
unless `--dir-mode` is given. The first upload pushed only the probe script and reported success,
which would have booted a kernel with no `admorphiq` package to import. Verified by listing the
dataset's files rather than trusting the "Upload successful" line.


## The edge-band rule, as a tool rather than a sentence (2026-08-25)

The discriminator was a paragraph in this page; it is now
`scripts/rounds/R98/edge_band_probe.py`, and it finds what it claims to:

```
sp80  scale 4  top: 14 state(s) -> counter     bottom: 2 state(s) -> EVENT
vc33  scale 2  top:  1 state    -> decoration  bottom: 1 state    -> decoration
ft09  scale 2  top:  1 state    -> decoration  bottom: 14 state(s) -> counter

[edge band] 1 row(s) carry an EVENT the cell grid throws away
```

**Exactly one row across the three games**, and it is sp80's failure band — the thing that
decides whether a run succeeds and that no cell-based reading can see. The probe needs no
knowledge of any game: fourteen actions, a commit every third so a spill actually runs, and a
count of how many distinct states each outer pixel row takes.

The counter threshold is written as `states >= max(3, actions // 2)` rather than a bare number,
because "changes on nearly every action" is what a counter IS and the action count is what makes
that measurable; the floor of three keeps a short probe from calling everything a counter.

## The Kaggle run needed a second push

`gptoss` came back ERROR on its first attempt:

```
RuntimeError: probe_r98_model_bench.py not found under /kaggle/input
```

The kernels were pushed while the dataset version was still being created, so they attached the
previous one. The dataset now lists the probe at 38047 bytes and both kernels are RUNNING again
(gptoss at version 6).

Worth keeping as a sequencing rule: **`kaggle datasets version` returns before the version
exists.** A kernel pushed immediately after it will silently attach the old data, and the failure
surfaces minutes later as a missing file rather than as anything about the dataset.


## Marking the floor fatal: right in spirit, wrong row (2026-08-25)

With the failure entity identified as a band on the board's last row, the obvious move is to give
the model what the engine has — treat that row as fatal, so the compiler stops choosing layouts
whose flow arrives there. Tried:

```
oracle gate      3/3 PASS            unchanged
bench            idx0 0/0, 209/108   unchanged, board for board
walk idx0-idx2   23 / 30 / 55        unchanged
walk idx3        verifier CONTRADICTED — the replay misses (14,1) and (14,4)
```

idx3 gets WORSE: it now stops at the verifier instead of reaching the compiler, because the flow
demonstrably reaches row 14 and the change forbids it.

The reason is a coordinate the round has already measured and I did not carry: **on idx3
`playable_size()` returns 15**, so "the last playable row" is 14 — and row 14 is ordinary board
the flow crosses. The engine's fatal band is the row BELOW that, the one `playable_size()` trims
as frame.

So the rule is not "the last playable row is fatal". It is "**the trimmed band is fatal**", which
is uncomfortable precisely because the same trim exists to keep a status strip out of the board —
and this round already measured a case (vc33) where the trimmed band really is decoration.

Reverted; walk back to 138 actions with idx3 executing its plan. What the attempt establishes is
narrower than a fix and worth having: the fatal band is NOT the last playable row on idx3, the
distinction between it and a decorative strip is exactly the edge-band probe's EVENT-versus-
decoration verdict, and any future attempt has to consult that verdict rather than assume a row.


## The trimmed band IS fatal — the model now predicts the failure it always saw (2026-08-25)

The last attempt marked the wrong row. Marking the one `playable_size()` trims — the band below
the playable area, where the failure entity actually lives:

```
oracle 3/3 · grounding PASS · verifier PASS · mutants PASS · ood PASS · suite 1721
bench      idx0 0/0, 209/108   unchanged board for board
walk       idx0 23 · idx1 30 · idx2 55   unchanged
idx3       compiler UNSATISFIABLE — 44704 layouts examined, board held 4 pieces
```

Every gate holds and idx3 changes character: it used to compile a plan, execute it, and fail
silently; it now reports that no layout satisfies the objective. **That is the model agreeing
with what every measurement of that level has shown** — each attempt failing on the flag, with
all four targets satisfied and nothing else to blame. A model that predicts the failure is worth
more than one that plans into it.

It also stops the walk spending a life on a doomed commit, which matters because a run has four
for the whole game.

Scope, stated rather than assumed: this is measured on sp80. The round has already found a
trimmed band that is pure decoration — vc33's status strip — so "the trimmed band is fatal" is
not a family law. It happens not to touch vc33 because that strip is at the TOP and this marks
the row below the board, but the next game with a bottom strip will need the edge-band probe's
EVENT verdict rather than this assumption. The probe exists for exactly that, and wiring it in is
its own change.


## Under the claimed table, no placement wins idx3 (2026-08-25)

With the trimmed band marked fatal, the compiler reports idx3 unsatisfiable. Enumerating every
reachable layout rather than trusting that report — four pieces, shifts -8..+8:

```
by (targets satisfied, fatal)
   (0, True)  3715      (1, True) 11235      (2, True)  866      (3, True) 24
WINS: 0
```

**Fifteen thousand eight hundred and forty valid layouts, every one of them fatal.** Twenty-four
of them fill all three named targets and touch the band anyway. So the compiler's verdict is not
a search failure — it is the truth about this board under the claimed table.

Which frames what is left honestly. Either the propagator sends flow to the floor where the
engine does not, or the level wants something a single placement cannot do. The round has already
measured the second possibility's cost: a run has four failed commits for the whole game, and
idx3's every live attempt failed on the flag with all its targets satisfied.

What this closes is the question of whether the compiler was simply not looking hard enough. It
was: exhaustive over the piece shifts, and there is nothing there.


## The fused experiment answered: the split was NOT what gemma4 stumbles on (2026-08-25)

gemma4's kernel completed. Three modes in one run:

```
select       3/3 PASS
fill         0/3 FAIL   blocked_by_verifier, CONTRADICTED, 0 actions executed
fill_fused   0/3 FAIL   blocked_by_verifier, CONTRADICTED, 0 actions executed
```

And the answers are IDENTICAL between the two encodings:

```
                            truth                gemma4 (both split and fused)
piece_response_spawn        empty_flanks_only    both_flanks          MISS
piece_response_direction    preserved            preserved            ok
piece_response_propagation  cellwise_iterative   cellwise_iterative   ok
sink_response_predicate     same_sink_flanks     same_sink_flanks     ok
sink_response_miss          spread_like_piece    spread_like_piece    ok
hazard_response             terminate_fatal      terminate_local      MISS
```

**Asking the hazard once instead of twice changes nothing.** gemma4 answers `terminate_local`
either way, so the encoding is exonerated: the split was not the thing it stumbles on. That is
the clean negative the experiment existed to produce, and it is worth as much as the other
answer would have been — the round can stop suspecting its own schema on this point.

Two corrections to the frozen record, both from this measurement rather than from argument:

* the record says gemma4 misses **one** slot; it misses **two** — `spawn` as well as `hazard`.
  Whether that is drift in the model, in our prompt, or in this session's grounding changes is
  not established here.
* `select` reproduces at 3/3, so whatever moved did not move the select stage.

The verifier did its job on every run: CONTRADICTED, zero actions executed, no live cost for a
wrong hypothesis. gpt-oss is still running and is the leg that decides whether FILL is confirmed
paired.


## The fatal-band adoption rested on a false premise — reverted (2026-08-25)

Marking the trimmed band fatal was adopted because it made the model "predict the failure it
always saw". Measuring whether the ENGINE's flow ever reaches that band says it does not:

```
idx3, every spill:   band row 15 touched at []
```

Never. Not once, across the discovery spill and both plan spills. So the failure the model was
now predicting is a contact **the engine does not make**, and the adoption was reasoning from a
premise that had not been checked — the entity is at that band, but the flow never arrives there.

What the change actually surfaced is a different defect, and a real one: **our propagation runs
flow off the bottom of the board where the engine keeps it on.** Before the change, row 15 was
out of bounds and those droplets died silently; marking it fatal only made the consequence
visible. All 15840 layouts came out fatal because all of them flood a row the engine never wets.

Reverted. The walk is back to 138 actions with idx3 executing its plan, the gate holds at 3/3,
and the round keeps the finding rather than the fix:

* the failure entity IS at the trimmed band (measured from the engine's own flash);
* the engine's flow never reaches it on idx3 (measured from the frames);
* our propagation does (measured by the enumeration).

Those three are consistent only if something stops the engine's flow before the floor that our
model does not have. That is the next thing to look for, and it is a propagation question rather
than an entity one.

Also recorded: this is the second adoption this session justified by "the model now agrees with
what we observe" where the agreement was coincidental. The check that caught both was the same —
ask whether the engine does the thing the model now predicts.


## qwen3.8 agrees with gemma4, and on exactly one slot (2026-08-25)

```
select       3/3 PASS
fill         0/3 FAIL   hazard_response: terminate_local
fill_fused   0/3 FAIL   hazard_response: terminate_local   — identical
```

qwen3.8 gets **five of six slots right** and misses only `hazard_response`, answering
`terminate_local` where the truth is `terminate_fatal` — under both encodings, byte for byte.
gemma4 misses that same slot plus `piece_response_spawn`.

So two independent models, asked in two different ways, converge on the same wrong value for the
same slot. That is the shape of a **prompt or evidence defect, not a model verdict** — the
lesson this round already wrote down after three models answered three values identically
(`unanimous_wrong_answers_are_a_prompt_defect_20260823`).

And it says what the fused experiment could not: the split was never the problem, so the question
moves to what the evidence actually shows about a barrier. If the discovery a model sees never
contains a fatal contact, `terminate_local` is the answer the evidence supports and the models are
reading it correctly.

## Correction: our propagation does NOT run flow off the bottom

The last entry said the enumeration's all-fatal result showed our flow going a row deeper than
the engine's. Measured, the deepest flow row is **14 on every spill, engine side**, and idx3's
playable size is 15 — so the engine stops at the last playable row, which is exactly where the
propagator's bounds check stops too.

The all-fatal result had a simpler cause. The propagator tests bounds and hazards on one branch:

```python
if not _in_bounds(ahead, board.size) or ahead in board.hazard_cells:
    if ahead in board.hazard_cells:
        fatal = True
```

Adding the out-of-bounds row to `hazard_cells` turned **every normal boundary death into a
fatality**. Nothing was flowing deeper; the check was being asked a different question. The
revert was right and its stated reason was not.


## Why both models say `terminate_local`: the evidence calls a fatal contact a stop (2026-08-25)

Two models converging on one wrong slot is a prompt or evidence defect, so the evidence was read
as a model receives it. The relevant line, verbatim:

> All 2 of the cup-shaped regions ended in the distinct appearance that marks a satisfied target,
> and the level still did NOT advance. The only other thing that happened in the whole animation
> is that a stream **reached the row just above the bottom edge and stopped there**.

The fatal case IS in the evidence — every target satisfied and no advance — and the sentence that
should carry the cause **describes it as a harmless stop**. Nothing in that phrasing says a
barrier was contacted; a stream ending where it runs out of room is the most ordinary event a
falling flow has.

Read that way, `terminate_local` is what the evidence supports: the stream ended locally, and
whatever failed the attempt is unaccounted for. **The models are reading it correctly.** gemma4
and qwen3.8 arrive at the same value under two different encodings because the encoding was never
the issue — the description was.

This is the round's own lesson landing a second time: unanimous wrong answers are a prompt
defect. The first instance (three models, three values, nine runs) was fixed by stating a
persistence rule and glossing the closed choices; this one is narrower and sharper — a single
clause that names the mechanism as its opposite.

Not patched here, on purpose. Rewriting that clause is a CORRECTNESS fix rather than tuning — the
evidence currently misdescribes what the frames show — but it changes what every model is asked,
so it belongs in its own measurement with all three models rather than appended to a round whose
verdicts were taken under the present wording.


## gpt-oss closes the fill experiment, and takes two of my conclusions with it (2026-08-25)

```
                gemma4      qwen3.8     gpt-oss
select          3/3 PASS    3/3 PASS    1/3 FAIL
fill (split)    0/3 FAIL    0/3 FAIL    3/3 PASS
fill (fused)    0/3 FAIL    0/3 FAIL    3/3 PASS
```

**gpt-oss answers `hazard_response: terminate_fatal` and clears, under both encodings.** So the
evidence is sufficient: one model extracts the fatal contact from the same clause the other two
read as a harmless stop. The last entry's conclusion — that the description is at fault and "the
models are reading it correctly" — is **withdrawn**. The clause is thin, not wrong, and thinness
that one model of three penetrates is a different finding from a misdescription.

A second correction from the same file. gpt-oss's passing answer gives `piece_response_spawn:
both_flanks` — the value I called a MISS for gemma4 two entries ago. It passes the verifier, so
it is an **equivalence-class answer**, not an error. gemma4 therefore misses **one** slot after
all, exactly as the frozen record said, and my "two slots" correction was itself the mistake.

And gpt-oss's select is not a reasoning regression:

```
run 0  pick I3, truth, cleared, 2 actions
run 1  unparsable
run 2  unparsable
```

Two replies the harness could not parse. The pick it did make was the truth. So the 1/3 is a
HARNESS outcome, and the frozen 3/3 remains the measurement of what that model can do on select.

Where the contract stands: **FILL is still not confirmed paired** — gpt-oss 3/3, gemma4 0/3 — but
the reason is now known and it is neither the encoding nor the evidence's adequacy. It is that
one slot's support in the evidence is thin enough that two models of three miss it.


## The model-stage ledger, all three models, all three modes (2026-08-25)

```
model    mode        verdict   cleared  blocked  unparsable  live actions
gemma4   select      3/3 PASS      3       0         0            6
gemma4   fill        0/3 FAIL      0       3         0            0
gemma4   fill_fused  0/3 FAIL      0       3         0            0
qwen3.8  select      3/3 PASS      3       0         0            6
qwen3.8  fill        0/3 FAIL      0       3         0            0
qwen3.8  fill_fused  0/3 FAIL      0       3         0            0
gpt-oss  select      1/3 FAIL      1       0         2            2
gpt-oss  fill        3/3 PASS      3       0         0            6
gpt-oss  fill_fused  3/3 PASS      3       0         0            6
```

Two things this table says that no single run does.

**No wrong hypothesis ever executed a live action.** Twelve failing runs, every one of them
either blocked by the verifier or unparsable, and the action column reads zero for all of them.
That is the contract's central promise — a wrong answer costs nothing on the board — held across
twenty-seven runs and three models without exception.

**Every passing run cleared in exactly two actions.** Six live actions per three runs, in every
PASS row, which is the oracle path's own cost. A model that gets the hypothesis right pays what
the hand-written oracle pays, and nothing extra for having been a model.

The verdicts themselves stay as measured: select confirmed on gemma4 and qwen3.8 with gpt-oss's
1/3 explained as two unparsable replies rather than wrong picks; fill passing only on gpt-oss, in
both encodings, on one thinly-supported slot.


## Fixing the unparsable: keep the reply, then pay for the answer (2026-08-25)

gpt-oss's select came back 1/3 with two runs recorded as `unparsable`, and the record held
nothing but that word:

```
keys: ['candidates', 'executed_actions', 'mode', 'outcome', 'pick', 'picked_truth', 'run']
```

**The thing that could not be parsed was thrown away.** So an unparsable run cannot be told from
a refusal, a truncation, or an answer in the wrong shape — every future one is the same wall.
Fixed first: `raw_reply` and `reply_chars` on the select path, `raw_variant_reply` and
`raw_slot_reply` on fill.

Then the likely cause, reasoned from what the parser accepts. `parse_select` already falls back
to ANY `I<digit>` token anywhere in the text, so an unparsable reply contained no answer token at
all — not a malformed one, none. For a reasoning model that spends its completion budget on
reasoning before answering, that is what running out looks like.

So the budget was raised, 20000 to 40000, rather than retrying:

```
a retry would be tuning the harness until a run passes
a budget that cuts off the answer measures the BUDGET, not the model
```

The evidence for the reading is the run itself: the one reply that did parse picked the truth and
cleared in two actions. A model that reasons correctly and is cut off mid-answer scores 1/3; the
same model with room to finish should score what its reasoning earns.

Re-running gpt-oss first, at the user's priority, with gemma4 queued behind it. If the next run
still shows unparsable replies, the raw text is now recorded and the reading can be checked
instead of inferred.


## Naming the contact: built as a variant, not applied (2026-08-25)

Why is one slot thin? The evidence generator KNOWS about the barrier contact — the discriminating
line only fires when `board.hazard_cells` is non-empty, which is to say when the grounding
observed a stream running into one. What the sentence reports is the POSITION and the STOP:

> a stream reached the row just above the bottom edge and stopped there.

Both halves are true and the CAUSE is left implicit: a reader has to infer that "the row just
above the bottom edge" means the stream was against the edge, and that being against it is why it
stopped. gpt-oss makes that inference and answers `terminate_fatal` 3/3; gemma4 and qwen3.8 read
the same sentence as an ordinary stop and answer `terminate_local`.

So `--evidence explicit` now exists beside the default:

```
default    ...a stream reached the row just above the bottom edge and stopped there.
explicit   ...a stream came into contact with the board's bottom edge — it reached the row
           directly above it and stopped there against it.
```

The default is untouched and every frozen verdict stays comparable; the variant is opt-in exactly
as `--hazard fused` is.

Whether to RUN it is a real question rather than a formality. Naming a contact the grounding
already measured is a correctness improvement — the frames show it and the sentence withholds it.
But it would move two models from FAIL toward PASS, which is what tuning looks like from the
outside. The distinction that makes it legitimate: the explicit wording adds a fact the harness
has, not a hint about which answer to give, and it says nothing about fatality — a model still
has to decide whether contact ends a stream or an attempt.

Measured paired against all three, or not at all.


## gemma4 reproduces exactly, on an independent run (2026-08-25)

The re-run with the raised completion budget and raw-reply recording:

```
              first run    re-run
select        3/3 PASS     3/3 PASS
fill          0/3 FAIL     0/3 FAIL     hazard_response: terminate_local, both times
fill_fused    0/3 FAIL     0/3 FAIL     terminate_local, both times
```

**Identical across two independent runs**, down to the value in the slot. So gemma4's miss is not
sampling noise and not a bad draw — it is what that model does with this evidence, reproducibly,
under both encodings.

That matters for how the fill verdict is read. A 0/3 could always have been three unlucky
samples; two 0/3 runs with the same wrong value in the same slot cannot be. The frozen record's
"gemma4 misses one slot" is now measured twice, and the fused experiment's negative result is
measured twice with it.

It also means the `--evidence explicit` variant has a clean baseline to be judged against: if
naming the contact moves gemma4, it moves something reproducible rather than something that was
going to wobble anyway.

gpt-oss is still running on the raised budget — that run answers whether its select 1/3 was the
budget, which is the other half of this tick's question.


## The OOD controls decline for a reason, and it is the same reason (2026-08-25)

The certification said both controls "decline" and left it there, which cannot be told from a
harness that declines everything — the positive control proves the opposite only at the
whole-board level. It now names the slots:

```
sp80 (positive)  OK — board with 2 target(s), 1 piece(s); verifier PASS
tu93 (near)      DECLINES — no board; unread: pieces, sink_candidates, barriers,
                            initial_direction, emitters, trajectory
re86 (far)       DECLINES — no board; unread: same six
```

**Both controls fail on all six slots**, identically. So the near/far distinction the pre-screen
drew — tu93's 8-layer burst against re86's 1 — does not survive into the grounding: at this stage
they are equally unreadable, and the harness declines them for the same reason rather than for
reasons proportionate to how confusable they are.

That is a finding about the CONTROL rather than about the harness. tu93 was chosen as near-OOD
because an agent could plausibly reach for this family on seeing it, and the point of a near
control is to be refuted LATE — after the model has committed — rather than rejected on sight.
This one is rejected on sight, so it tests the same thing the far control tests.

Nothing is broken and nothing needs fixing: the verdict stands, and both kinds of declining are
legitimate. What the round now has is the honest scope — **the OOD controls exercise the
grounding, and the verifier has never been asked to refuse anything.** A control that reached it
would need a game whose entities the grounding CAN read while its mechanics differ, and no such
game has been found among the twenty-five.


## gpt-oss passes all three modes; the select failure was the budget (2026-08-25)

Re-run at 40000 completion tokens, with raw replies recorded:

```
gpt-oss   select 3/3 PASS    fill 3/3 PASS    fill_fused 3/3 PASS
qwen3.8   select 3/3 PASS    fill 0/3 FAIL    fill_fused 0/3 FAIL
gemma4    select 3/3 PASS    fill 0/3 FAIL    fill_fused 0/3 FAIL
```

gpt-oss's select runs:

```
run 0  pick I3  truth  cleared
run 1  pick I3  truth  cleared
run 2  pick I3  truth  cleared
```

**The 1/3 was the completion budget.** Every run now reaches an answer, and every answer is the
truth — the same pick the one parsed reply made last time. Raising the budget rather than
retrying was the right call for the reason it was made: a run cut off before answering measured
the budget, and the model had nothing wrong with it.

So the model stage now reads, across three models and three modes with every verdict measured at
least twice:

* **select — CONFIRMED on all three.** gpt-oss's earlier 1/3 is retired as an artefact.
* **fill — gpt-oss 3/3, gemma4 and qwen3.8 0/3**, each reproduced, all on the single
  `hazard_response` slot whose evidence leaves the cause implicit.
* **fill_fused — identical to fill for every model**, which is the fused experiment's answer
  standing after a second independent measurement.

The contract's pairing requirement is still unmet on fill, and the reason is now measured rather
than suspected: one slot, one thinly-worded clause, one model of three that infers past it.


## The explicit-contact experiment is running (2026-08-25)

The kernel now runs four modes. The first three are the frozen measurements and keep their
filenames; the fourth is the experiment:

```python
("select", "split", "default")     the contract's select
("fill",   "split", "default")     the contract's fill
("fill",   "fused", "default")     the hazard asked once — answered, negative, twice
("fill",   "split", "explicit")    the contact named
```

It runs on gpt-oss and gemma4 now, qwen3.8 when a slot frees. What it decides is the last open
question in the fill stage: gpt-oss infers past the implicit clause 3/3 and the other two do not,
each reproduced twice, so the wording is the only untested variable left.

The reading is prepared in advance, because a result that can be read either way after the fact
is not a measurement:

* **all three pass** — the clause was withholding a fact the harness had, and naming it is a
  correctness fix that the frozen wording was costing two models;
* **gpt-oss passes and the others still do not** — the wording was never the obstacle, the slot
  needs reasoning the other two do not do here, and the frozen verdict stands as the family's
  honest answer;
* **anything gets worse** — the explicit sentence introduced a distraction, and it goes back out.

Only the middle outcome leaves the contract where it is. The first would close fill; the third
would be an argument for leaving evidence alone.


## The same sequencing trap, taken a second time (2026-08-25)

Both kernels came back with every mode ERROR:

```
verdicts: {'select': 'ERROR', 'fill': 'ERROR', 'fill_fused': 'ERROR', 'fill_explicit': 'ERROR'}
[mode] select rc=2 · fill rc=2 · fill_fused rc=2 · fill_explicit rc=2
```

`rc=2` is argparse refusing an unknown flag. The kernels ran the OLD probe — the one without
`--evidence` — because they were pushed before the dataset carrying the new one existed. **This
round wrote that exact rule down two hours ago** (`kaggle datasets version` returns before the
version exists) and I walked into it again, this time by pushing the kernel first and the dataset
not at all.

Fixed by doing it in the order the rule states: push the dataset, wait until the file listing
shows the new size (40375 bytes, the `--evidence` build), then push the kernels. Both are
re-running.

Worth recording as more than an apology: **the failure mode is silent at push time and loud four
minutes later, in a place that looks nothing like packaging.** `rc=2` from a probe reads as a
harness bug until you notice the flag it rejected is one you added after the dataset was last
uploaded. The cheap defence is the one this round already found — check the dataset's file
listing, not the upload's success line — and it now needs applying before the KERNEL push as well
as after the dataset one.


## The direction is NOT invariant — the life-saving lever is refuted (2026-08-25)

Every level spends a sacrificial commit to read the flow's direction, a run has four failed
commits for the whole GAME, and that is why idx3 was reached with the game already over. The
proposed fix was to carry the direction forward on the grounds that it "cannot change within a
game". Measured, one line per level, by a report that changes nothing the walk does:

```
[invariant] idx0 direction=(1, 0)  flow_colours=[6] emitters=((1, 9),)
[invariant] idx1 direction=(-1, 0) flow_colours=[6] emitters=((14, 10),)
[invariant] idx2 direction=(-1, 0) flow_colours=[6] emitters=((14, 1), (14, 9), (14, 14))
[invariant] idx3 direction=(1, 0)  flow_colours=[6] emitters=((8, 4),)
```

**The direction flips twice across four levels.** Carrying it forward would have aimed idx1 and
idx3 backwards. The claim was half right and the wrong half was the load-bearing one: the flow
COLOUR is invariant — 6 on every level — and colour is not what the commit is spent on.

Two cheaper substitutes were then tested against the same four measurements, and both fail on the
same level:

| rule | idx0 | idx1 | idx2 | idx3 |
|---|---|---|---|---|
| away from the nearest horizontal edge | ✅ | ✅ | ✅ | ❌ |
| top half down, bottom half up | ✅ | ✅ | ✅ | ❌ |

Both get the three edge-sourced levels right and idx3 wrong, and idx3 is the level the whole
lever exists to reach. One caveat keeps this from being a clean refutation of the geometry
itself: idx3's emitter row is a WINDOW row, not a board row (its level is 20 cells shown through
16), so the rule was fed a coordinate that does not mean what it means on the other three. The
rule is refuted **as stated and as feedable**; whether some rule over true board coordinates
survives is a question the window defect has to be fixed before anyone can ask.

What stands: the sacrificial commit buys evidence the grounding has no other route to, and the
depth ceiling it imposes — one life per level, four lives, six levels — is REAL rather than an
artefact of how the walk is written. ⛔ Do not "save" it by carrying the direction.


## The window is FIXED — idx3's missing rows are unreadable by construction (2026-08-25)

The leading explanation for idx3's UNSATISFIABLE is that its level is twenty cells tall shown
through a sixteen-cell frame. That was read from the game source and never tested through the
official interface. The observable form of the question is: **when a piece moves, does content
that is not the piece TRANSLATE?** A fixed window leaves every static pixel where it was; a
scrolling one shifts the whole render. `scripts/rounds/R98/window_probe.py` measures the best
whole-frame translation between consecutive frames, with idx0 — a board known to fit — as its
control:

```
idx0 press 3: best shift (0,0) explains 0.992; unshifted agreement 0.992
idx0 press 1: best shift (0,0) explains 0.960; unshifted agreement 0.960
idx3 press 3: best shift (0,0) explains 0.995; unshifted agreement 0.995
idx3 press 1: best shift (0,0) explains 0.978; unshifted agreement 0.978
```

**Offset (0,0) on every press of both levels, with the best shift's agreement equal to the
unshifted one** — the search had sixteen other offsets available and none of them explained the
frame better. The window does not scroll.

Put beside the four-row sprite-to-board offset measured earlier (#42), the picture closes: idx3's
frame shows board rows 4-19 of a twenty-row level and rows 0-3 are outside anything the harness
can read, permanently. The consequence for #53 is that its enumeration was right for the wrong
reason — 15840 layouts came back fatal not because the propagator floors flow the engine keeps
up, but because **the compiler was planning on a truncated board**. UNSATISFIABLE is the correct
answer to the board it was given, and the board it was given is missing a fifth of itself.

So the depth walk's ceiling of three levels is a PERCEPTION ceiling, not a planning one, and no
amount of propagation or schema work reaches idx3. What would is a reading that can assemble a
board larger than its frame — which is the same defect as #43/#44/#45 and belongs to the round
those items already assign it to, not to this one.


## The residual is all SURPLUS, and none of it is the window (2026-08-25)

The window finding raised a question about the bench itself: sixteen of its seventeen captures
are idx3 boards, and idx3 is now known to be truncated, so how much of the physics column is the
missing rows rather than propagation? `rule_bench.py --rows` answers it by attributing the
residual to board rows instead of a total:

```
 row  invented  missed
   5         6       0
   7        10       0
   8        11       0
  12        22       0
  13        20       0
  14        20       0
  15        15       0
 sum       108       0
the window's truncated edge (rows 0-3): 0 of 108
```

**Nothing at all sits against the truncated edge.** The window explains none of the residual, so
the bench keeps its standing as a propagation diagnostic and every rule judged on it was judged
on the right thing.

Two properties fall out that a total was hiding. First, **the error is entirely INVENTED — 108
surplus cells, zero missed, on every capture.** The model's trail is a strict superset of the
engine's: it never fails to reach a cell the engine reaches, it only adds. For a planner that is
the benign direction to be wrong in for reachability and the dangerous one for satisfaction — a
forecast can claim a target the flow never wets, never the reverse. Second, **77 of the 108 sit
in rows 12-15**, the trail's far end, which is independent confirmation of the surplus-at-the-
bottom reading that #54 arrived at and whose first fix was reverted for a wrong reason.

The docstring's 211/139 was stale and is corrected to the measured 209/108; the rules adopted
since closed the difference. Judge the next propagation rule on the bottom rows.


## The frame band is a WALL — adopted, and it is not the rule that was reverted (2026-08-25)

The row attribution pointed at the trail's far end, so the next question was where exactly the
surplus enters. Measured across all eighteen captures:

| | |
|---|---|
| engine cells in the hazard row | **0, on every capture** |
| model's deepest row vs the engine's | one row deeper on **13 of 18** |
| hazard cells grounding admits in that row | **two** |

So the engine treats the whole bottom line as impassable while grounding marks only the two
cells it has evidence for, and our replay leaks into the columns nobody marked. Adopted:
`_frame_band()` returns the whole edge line when a board's hazards all sit on one, and the
propagator treats it exactly as it treats the board's edge.

**This is not #52 in another coat.** That change made the band FATAL and was reverted because the
engine's flow never contacts it, so the model began predicting a failure that never happens; #56
then found the mechanism — bounds and hazards share one branch, so marking the row hazardous
turned every ordinary boundary death into a fatality. The band as a WALL routes to the boundary
branch instead: a droplet that would enter it simply ends, the attempt is unaffected, and the
hazard slot keeps its meaning at the two marked cells. A pin holds that distinction by failing
if the band is ever folded back into `hazard_cells`.

Measured after adoption, everything at once:

| | before | after |
|---|---|---|
| bench as-known / physics | 209 / 108 | **197 / 93** |
| idx0 contract board | 0 | **0** |
| oracle gate | 3/3 | **3/3** |
| grounding / verifier / mutants | PASS | **PASS** |
| depth walk | 3 levels, 138 actions | **3 levels, 138 actions** |

The physics column falls by exactly the fifteen cells the row-15 attribution predicted, which is
the check that the rule removed what it was aimed at rather than something else of the same size.

Three pins, each checked against its own subject by deleting that subject and re-running — and
one of them taught something. `test_the_frame_band_is_a_wall_and_not_a_hazard` stays GREEN when
`_frame_band` is deleted entirely, because at the outer edge a wall death and a boundary death
are the same event. Its subject is the band's PLACEMENT, not its existence, and it goes red
exactly when the band is folded into the hazards. The docstring now says so instead of claiming
a coverage it does not have.


## The explicit-contact experiment: the wording was never the obstacle (2026-08-25)

The fourth mode named the barrier contact instead of leaving the cause implicit. Read against
criteria fixed before the run: all three models passing would mean the clause had withheld a
fact; only gpt-oss passing would mean the wording was never the obstacle.

gemma4 and qwen3.8 both answer **`hazard_response: terminate_local` in every encoding**, blocked
by the verifier at zero executed actions each time:

| model | select | fill | fill_fused | fill_explicit |
|---|---|---|---|---|
| gemma4 | 3/3 | 0/3 | 0/3 | **0/3** |
| qwen3.8 | 3/3 | 0/3 | 0/3 | **0/3** |

Eighteen runs — two models, three encodings, three repetitions — and the six answered slots are
**byte-identical across all of them**. Neither the split-versus-fused encoding nor the explicit
contact sentence moves anything. The frozen verdict stands: these two models read this evidence
to `terminate_local`, and that is a reading, not a defect in how the question is put.

Which retires a live suspicion rather than confirming a guess. R98 has already seen three models
unanimous on three wrong values turn out to be a PROMPT defect, so "two models agree, therefore
the prompt is at fault" was a reasonable thing to fear here; the difference is that fixing the
prompt there took gpt-oss from 0/3 to 3/3, and here gpt-oss already answers correctly under the
original wording. A defect that only one of three models can see through is not a defect in the
question.

⛔ Do not re-cut the encoding again to make a weaker model pass. Three cuts have now been
measured, all inert, and a fourth would be tuning the representation until the answer arrives.


## What the remaining 93 cells ARE: a lateral halo, not a longer run (2026-08-25)

With the frame band closed, the residual was re-attributed — first by row, then by mechanism
(`rule_bench.py --where`):

| what the surplus cell is | | how far from the real trail | | which way it lies |
|---|---|---|---|---|
| empty cell | 92 | d=1 | 54 | across the flow **57** |
| piece cell | 1 | d=2 | 19 | diagonal 27 |
| | | d=3 | 16 | along the flow **9** |
| | | d≥4 | 4 | |

Three things follow, and none of them was visible in the total.

**The model does not invent streams.** 89 of 93 surplus cells sit within three of an observed
one and only four are further, so there is no phantom source anywhere in the sweep — everything
extra is attached to a trail the engine really ran.

**It spreads too WIDE, not too far.** Purely lateral surplus outnumbers longitudinal six to one
(57 against 9). Together with row 15 having vanished, this says the run LENGTH is now right and
what remains is sideways over-production, which accuses the spread rules — `piece_spawn`,
`sink_miss`, the walk reach — and exonerates the tick count.

**It is uniform.** Thirteen of the fifteen non-zero captures contribute five or six cells each,
with only `f` (13) and `l` (9) above that. A residual that constant is one repeating rule applied
slightly too generously, not an accumulation of board-specific accidents.

That lands the attribution chain squarely on the open asymmetric-spread question (#3), which has
been stuck as a qualitative puzzle — "1 step one way, 4 the other" — and now has a shape: the
error is lateral, uniform, and hugs the trail. ⛔ It does NOT license another reach sweep; six
values were measured and all were worse than the adopted 2. What it licenses is asking why the
spread is asymmetric at all, with the knowledge that whatever the answer is, it is worth about
five cells per board.


## One-sided spawning is refuted, and the sweep now carries its own tripwire (2026-08-25)

The lateral residual has exactly one source left: `spawn()` already refuses a cell the droplet
has occupied, so a walking stream cannot double back, and the only place width is created is the
blocked-droplet branch spawning on BOTH flanks. Three ways of picking a side instead, scored on
the physics column by `scripts/rounds/R98/spread_sweep.py`:

```
baseline (both flanks)                           physics   93   idx0 0
only the flank that is SUPPORTED (cannot fall)   physics  543   idx0 30  <- BREAKS THE CONTRACT BOARD
only the flank that can FALL                     physics  444   idx0 19  <- BREAKS THE CONTRACT BOARD
not onto a flank standing over a piece           physics  444   idx0 19  <- BREAKS THE CONTRACT BOARD
```

All three are four to six times worse AND break the contract board. **The engine really does
spawn both ways**; the asymmetry it shows is not produced by choosing a side at the moment of
collision. So the lateral halo comes from something after the spawn — how far each side then
travels, or which of them survives — and the branch that creates the width is correct as written.

The sweep is worth keeping for the way it is built as much as for the answer. It loads the
propagator's source and rewrites one branch in memory, so a candidate is never committed to be
measured, and **idx0 is scored separately and printed beside every total**. Earlier in this round
a rule was adopted for halving the sweep and took the live gate to 0/3, because the contract
board was not in the sweep at all; here the same class of mistake is visible in the same line as
the number that would have tempted it. A diagnostic that can only report improvement is a
diagnostic that will eventually recommend a regression.


## What the engine actually does with a blocked droplet — one side walks (2026-08-25)

The halo had to come from what happens after the spawn, so `scripts/rounds/R98/walk_probe.py`
reads the extents out of the OBSERVED trajectories rather than arguing from one hand-read board.
Every spread event in the sweep, with `#` marking a walked cell that was standing on something:

```
board  landing    left                right
idx0   (3, 9)     5 step(s) ####.      1 step(s) .
idx0   (12, 10)   1 step(s) .          1 step(s) .
idx0   (12, 4)    1 step(s) .          1 step(s) .
b      (9, 10)    3 step(s) ##.        1 step(s) .
f..o   (7, 4)     4 step(s) ####       1 step(s) #        (eleven boards, identical)
stuck  (9, 10)    3 step(s) ##.        1 step(s) .
```

**Sixteen events, one shape: ONE side walks and the other stops after a single cell.** The
walking side runs while it is supported and takes exactly one step off the end (`####.`, `##.`)
unless the board's edge stops it first (`####`). The other side gets its cell and nothing more —
including in the eleven-board family where that single cell is SUPPORTED and would keep walking
under any rule that only looks at support.

Which side walks? In all sixteen it is the one with the longer supported run, and in all sixteen
it is also the lower-column side, because on these boards the two always coincide. The captures
cannot separate those two readings, and saying so is the honest position.

Scored as a rule — the losing flank still gets its cell but cannot walk on from it — it is
**refuted**: physics 196 against the baseline's 93, and 15 cells of error on the contract board.
The observation is solid and the simplest rule expressing it is not what the engine does; it
over-applies at collisions that are not this kind of event.

⚠️ The first implementation scored 332 and would have been reported as the same refutation. It
derived which flank it was looking at from the cell's own coordinates — a parity expression that
is simply wrong — so it was scoring a rule nobody had measured. Deriving the side from the index
the propagator itself builds the flanks with took it to 196. **A variant that scores badly still
has to be the variant you meant**, or the sweep manufactures refutations as readily as it
manufactures improvements.


## Correction: five of six events need no rule at all — the anomaly is ONE event (2026-08-25)

The claim above — "one side walks and the other stops after a single cell" — was an artefact of
how the probe measured. It followed a straight lateral run, so a side that took one cell and then
FELL read identically to a side that stopped there, and those are different mechanisms. Asking
the observation whether the last cell has a descendant along the flow separates them:

```
board  landing    left                          right
idx0   (3, 9)     5 ####.   fell                1 .   fell
idx0   (12, 10)   1 .       fell                1 .   fell
b      (9, 10)    3 ##.     fell                1 .   fell
f..o   (7, 4)     4 ####    STOPPED on support  1 #   STOPPED on support
stuck  (9, 10)    3 ##.     fell                1 .   fell
```

idx0's right side does not stop at `(3,10)` — it falls the whole way to `(12,10)` and spreads
again there. **Five of the six events are gravity and nothing else**: a droplet slides while it
is standing on something and falls the moment it is not. No rule is needed to produce any of them
and the propagator already gets them right.

The anomaly is the `f`–`o` family, one event replicated across eleven boards: both sides stop on
SUPPORTED cells. The left one is at the board's edge with a piece beneath it — nowhere to walk,
nothing to fall into — so stopping is forced. The right one at `(7,5)` is the real puzzle: it sits
on the piece's last cell, could step to `(7,6)` and fall from there, and the engine simply ends
it. That single droplet is the entire lateral halo; our model takes the step and pays for it on
eleven boards at five cells each.

So the open question is much narrower than "why is the spread asymmetric": it is **why a droplet
at the far end of a piece does not step off, when the same board's other side steps off happily
in idx0**. The rule scored so far — the shorter supported run does not walk — is at 144 physics
with 15 cells on the contract board, i.e. refuted, and it is refuted for a reason worth keeping:
it fires at every collision while the observation only ever shows this at one.


## The rule is not refuted — its EXPRESSION is (2026-08-25)

Diffing idx0 under the variant instead of reading its total says exactly what broke:

```
baseline: invented [] missed []
variant : invented [] missed [(3,4) (4,4) (5,4) ... (12,3) (12,4) (12,5) (13,3) (13,5) (14,3)]
```

All fifteen descend from one cell that was never born, `(3,4)` — the step off the piece's end
that idx0's left walk takes. Tracing it back: the walk reaches `(3,6)`, whose flanks are `(3,5)`
and `(3,7)`. Measured outward, `(3,5)`'s supported run is 1 and `(3,7)`'s is 2, so the variant
declares `(3,5)` the loser and spends it — and a spent droplet `continue`s out of the collision
branch, so `(3,4)` is never spawned and the entire descent below it disappears.

**The rule was re-decided at every collision.** A walk that is winning at the landing becomes a
loser three cells later simply because the surface it has already crossed is behind it. What the
observation shows is a side that walks *from the landing*, not a side that re-earns the right to
walk at each step, so the decision has to be made once and inherited.

That is a real fix and it is not a textual one: the droplet is `(cell, direction, walked)` and
inheriting the decision means carrying a fourth field through every spawn. **Not done here** —
this is the non-gating bench axis, the contract level is unaffected, and restructuring the
propagator's droplet on a diagnostic errand is how a round acquires a change nobody measured.
Recorded as the next concrete step on this axis, with the diagnosis attached so it does not have
to be found twice.

What the numbers mean in the meantime: 196 and 144 are scores for a rule that cuts its own
winning walk, not for the rule the observation describes. They are not evidence against it.


## The inherited walking side, implemented and REFUTED (2026-08-25)

The previous entry left this as the concrete next step with its diagnosis attached: decide the
walking side once at the landing and carry it, since re-deciding per collision cuts the winning
walk short. Implemented properly — the droplet gains a fourth field holding the outward lateral
step it is following, `SPENT` for the flank that does not walk, `None` for one that is merely
falling — and measured:

| board | before | after |
|---|---|---|
| idx0 (contract) | 0 | **0** |
| b, c, d, e | 9, 9, 9, 9 | **6, 6, 6, 6** |
| f | 13 | **11** |
| **a** | 1 | **40** |
| **p** | 0 | **35** |
| sum (physics) | **93** | **150** |

Five boards improve and two collapse, and the two that collapse lose whole streams: `a` and `p`
are missing every cell of two vertical falls, columns 3 and 8, from row 3 downward. The cause is
the half of the rule that says a droplet already walking continues on its own side and does not
re-open the other — on those boards the engine plainly does produce the far side, and it becomes
a stream that runs the height of the board.

So the sixteen observed events did not cover this case, and the rule generalised past its
evidence. **Reverted**; the bench is back at 197/93 with oracle 3/3, grounding, verifier and
mutant certification all PASS.

Worth stating plainly because the previous entry made the opposite prediction: the diagnosis
there was right about WHY the earlier variant broke idx0, and wrong to conclude that fixing that
would make the rule work. The per-collision expression was one defect; generalising "one side
walks" from sixteen events on a family of near-identical boards was another, and only the second
one shows up when the first is repaired. A rule that improves five boards and destroys two is not
a rule that needs tuning — it is a rule whose evidence never contained the boards it breaks.


## The evidence base was the defect: both sides walk (2026-08-25)

The refutation above said the sixteen events "did not cover this case". They did not cover much:
the probe called something a spread event only when BOTH flanks appeared on the layer after the
landing, and a great many spreads put their two sides down on different layers. Relaxing that to
either flank takes the table from **16 rows to 258**, and the picture inverts:

```
a      (10, 3)   3 ##.  fell    3 ##.  fell     <- BOTH sides walk
b      (10, 3)   3 ##.  fell    4 ##.. fell     <- both, unequal lengths
idx0   (3, 9)    5 ####. fell   1 .    fell
```

**"One side walks" was an artefact of the detection rule.** A spread whose two sides start on
different layers was invisible, and those are exactly the boards — `a` and `p` — where the
inherited-walk rule deleted whole streams. The refutation and its cause are now the same fact:
the rule was fitted to a sample that had been filtered, by construction, to the events that
looked asymmetric.

⛔ #74 and #76 are RETRACTED, not merely superseded. Neither the "one side walks" reading nor
the "decide once at the landing" repair describes the engine.

What survives, and is now much better attested: 80 of the 258 sides end **STOPPED on support** —
a walk that neither steps off nor falls. On the `f`–`o` family this is the normal case rather
than a single anomaly (`(3,6)` right stops after two supported cells, `(9,5)` left after two),
while on idx0, `a` and `b` walks almost always end with one unsupported step and a fall. So the
open question is no longer about sides at all: it is **why walks terminate on support on some
boards and step off on others**, with 80 measured instances to test any answer against instead of
one.

The lesson is about the instrument rather than the engine. A probe that defines an event by a
coincidence — two things appearing on the same layer — does not sample the phenomenon, it samples
the coincidence, and every rule fitted to it inherits that bias silently. The refuted rule was
never the mistake; accepting a sixteen-row table as the evidence was.


## The walk's ONE ambiguous decision, and three properties eliminated (2026-08-25)

With 258 rows of evidence instead of 16, the question "why do some walks stop on support" can be
cut properly. `walk_probe.py --decision` looks at every point where a walking droplet COULD take
one more lateral step and records whether it did — the choice, not the terminal cell, which is
what conflates "could not continue" with "chose not to":

```
standing on    the next cell stands over              n
on piece       next over piece            STEPPED    64
on piece       next over empty            STEPPED    37
on piece       next over empty            stopped    30
```

**While the next cell is also supported the walk ALWAYS continues — 64 of 64, no exceptions.**
That is a genuine invariant, and the propagator already reproduces it. Every disagreement in the
sweep therefore comes down to ONE binary decision: whether to take the final step off the end of
the surface. Sixty-seven instances, split 37 to 30.

Three properties were tested against that split and all three are eliminated:

| property | verdict |
|---|---|
| what the next cell is (free / blocked / off-board) | STOP 30 vs fell 124 both mostly "free" — no split |
| whether flow ever reaches the next cell | STOP 30/30 and fell 122/124 both "stays empty" — no split |
| what the droplet stands on (piece / target / absorber) | every step-off case is `on piece` — constant, so it cannot discriminate |
| how far the walk had already gone | 0 cells: 26 stepped / 10 stopped; 1 cell: 9 / 20 — a tendency, not a rule |

The distance column is worth a caution rather than a conclusion. It leans the right way for a
reach-like rule and is nowhere near clean, and a global reach was already swept over six values
with the adopted 2 beating all of them. ⛔ This is not a licence to sweep it again; what it says
is that if a reach governs anything it governs *this one decision* and not the walk as a whole,
which is a different rule and would need its own evidence.

So the axis is now narrow and well-posed: one decision, 67 measured instances, four properties
ruled out. That is a better place to stop than a rule, because the last two rules on this axis
were both fitted to evidence that had not been checked for bias first.


## gpt-oss's fill is UNSTABLE on the split encoding — and the split is implicated after all (2026-08-25)

The confirming run came back and it does not confirm:

| mode | earlier run | this run |
|---|---|---|
| select | 3/3 | **2/3** |
| fill (default, split) | 3/3 | **0/3** |
| fill_fused | 3/3 | **3/3** |
| fill_explicit | — | **3/3** |

The same model, the same prompt, the same three repetitions: **the default fill went from 3/3 to
0/3.** The fused encoding is 3/3 in both runs and the explicit variant is 3/3, so the instability
is specific to the encoding that splits fatality across two slots.

What the failing runs actually got wrong is the informative part. Runs 1 and 2 answered **all six
response slots exactly as the oracle** — `empty_flanks_only`, `preserved`, `cellwise_iterative`,
`same_sink_flanks`, `spread_like_piece`, `terminate_fatal` — and failed on the OBJECTIVE:
`completion: count/1` and `hazard_policy: neutral`. That answer is **self-contradictory**: it
declares hazards neutral in one slot and fatal in another, in the same reply.

Which is the same failure the round already recorded for gemma4, in mirror image — gemma4 gave the
correct hazard POLICY with an incompatible hazard RESPONSE, gpt-oss gives the correct RESPONSE with
an incompatible POLICY. Two models, opposite halves, one encoding. ⚠️ The earlier conclusion that
"the fused experiment is answered — the split was not the cause, and the schema is exonerated on
this point" was measured **on gemma4 alone**, where fused and split give byte-identical answers.
gpt-oss's data says the opposite for gpt-oss: fused is stable at 3/3 across two runs while split
swings 3/3 to 0/3. The exoneration holds only for the model it was measured on.

⚠️ **I nearly recorded a harness defect here.** The six matching slots looked like the exact
oracle being blocked by its own verifier, which would have been serious, and the local self-test
does clear that same answer (`fill truthful -> cleared`). The variant field is what settled it:
the instance was not the truth, the verifier was right, and `equivalent_to_truth: false` was
right. The record keeps the variant, so the check was possible — but it keeps nothing about the
board, so a genuine grounding-dependent contradiction would NOT be separable from a model error
by looking at the artefact. That is a real gap in what the record carries.


## The record now carries the board the verdict was taken on (2026-08-25)

The near-miss above exposed a real gap: a CONTRADICTED verdict has two possible authors — the
model named the wrong world, or the grounding built the wrong board and the verifier judged a
correct answer against it — and the artefact could not tell them apart. It happened to be
separable this time only because the variant field was recorded and disagreed; had the model got
the objective right too, the six matching slots would have left nothing to check.

`_board_fingerprint()` now rides on every run record: size, direction, piece sizes, sink anchors,
hazard cells, absorber count, falling sources. Verified populated rather than assumed —

```
outcome: cleared
board  : {"size": 16, "direction": [1, 0], "pieces": [5], "sinks": [[13, 4], [13, 10]],
          "hazards": [[15, 3], [15, 9]], "absorbers": 0, "falling_sources": [[9, 0, 1]]}
```

— and those hazard cells are idx0's, matching the committed contract capture, so the fingerprint
is reading the board rather than emitting a shape.

The self-test now REQUIRES it on every case, and that requirement was checked against its own
subject: blanking the fingerprint turns the first three cases red. Without that check the field
could quietly become `{}` in a refactor and the record would look complete while carrying
nothing, which is the failure mode this round has already hit twice with vacuous tests.

Cost: a few hundred bytes per run, on a record that already keeps 1200 characters of raw reply
for unparsable cases. There is no reason to make it conditional.


## Three repetitions cannot carry a verdict — raised to nine (2026-08-25)

gpt-oss returned 3/3 and then 0/3 on the same prompt for the same mode. Those two results are not
in conflict: three draws from one underlying rate produce both outcomes easily, and neither run
was wrong about what it saw. What is wrong is treating either as the model's score.

`R98_RUNS` default raised 3 -> 9 and all three kernels re-pushed. Nine separates a model that
answers correctly most of the time from one that does so occasionally, which is the distinction
every verdict in this round's model stage has been making implicitly on three samples. The cost is
minutes on a machine that spends longer than that loading the weights.

⚠️ This does not retroactively invalidate the SELECT verdicts, which were 3/3 for all three models
across independent runs — repeated perfection on small samples is weak evidence of a high rate,
but it is evidence in the right direction, and select reproduced on re-runs. It does put the FILL
verdicts on notice: "gpt-oss passes fill and the others do not" now rests on a sample that has
been observed to swing completely.

Sequencing kept to the rule this round has broken twice: dataset pushed first, its file listing
polled until the new size appeared (41823 bytes, the fingerprint build), and only then the
kernels. Both contract-pair models are running; qwen3.8 waits on the two-session GPU cap.


## The 67 instances are 14 events, and every counter-example is on the unreadable level (2026-08-25)

The step-off decision looked like 67 measured instances split 37/30. `walk_probe.py --events`
groups them by (cell, walk direction), because the captures are sibling boards of one level and
the same physical event reappears on each:

```
STEPPED  (7, 13)  (0, 1)   15 boards   idx3
STEPPED  (3, 5)   (0,-1)    1 board    idx0
...
stopped  (3, 8)   (0, 1)   10 boards   idx3
stopped  (7, 5)   (0, 1)   10 boards   idx3
stopped  (9, 3)   (0,-1)   10 boards   idx3

DISTINCT events: 11 stepped, 3 stopped
```

**Sixty-seven instances are fourteen events.** The 30 "stopped" observations are three events seen
ten times each, and the 37 "stepped" are eleven events, one of them counted fifteen times. Every
property tested against this split was being tested against fourteen data points while the table
reported sixty-seven, which is precisely how two rules in a row came to be fitted and refuted.

And the three stopped events are **all on idx3** — the one level whose board the harness provably
cannot read completely, since its frame is a fixed sixteen-cell window onto a twenty-cell level.
idx0, the only capture whose board is complete, contributes step-offs and not a single stop.

So the honest position on this axis: the current captures cannot settle the step-off rule. Not
because the rule is subtle, but because every counter-example to "always step off" comes from the
level where four rows and four columns of the board are missing from the model, and a walk that
appears to stop is exactly what an unmodelled obstacle would look like. ⛔ No further rule should
be fitted to these captures. What would move it is captures from idx1 and idx2 — boards the
harness reads completely and which the walk now clears — and that is a capture run, not a rule.

The instance-versus-event distinction is the transferable part. A sweep over sibling boards
reports confidence proportional to how many siblings were captured, which has nothing to do with
how much was observed.


## The capture only ever fired on FAILURE — fixed, and the stops are real (2026-08-25)

The last entry said the step-off question needed captures from idx1 and idx2 rather than another
rule. Trying to take them exposed why there had never been any: `R98_CAPTURE` was a single path,
overwritten at every commit of every level, AND the one call site sat past the early return that
fires when a level clears. **Captures were only ever written when a level FAILED**, and only the
last such level survived — which is the whole reason every board in the sweep came from idx3.

Both fixed: the variable is now a PREFIX and every commit writes `{prefix}_idx{level}_{n}.json`,
and the capture is taken before the clear check. One walk now yields evidence from every level it
plays:

```
[capture] wrote scratchpad/r98caps/w_idx0_1.json      idx0: CLEARED
[capture] wrote scratchpad/r98caps/w_idx1_1.json      idx1: CLEARED
[capture] wrote scratchpad/r98caps/w_idx2_1.json      idx2: CLEARED
[capture] wrote scratchpad/r98caps/w_idx3_1..4.json   idx3: stopped
```

And the new evidence answers the suspicion the last entry raised. Step-off events, by level:

| | events |
|---|---|
| STEPPED | idx0 `(4,6)`, idx1 `(9,7)`, idx2 `(10,2)`, idx3 ×4 |
| **stopped** | **idx0 `(4,10)`**, **idx1 `(9,11)`**, idx3 `(4,11)`, idx3 `(9,8)` |

**idx0 and idx1 both stop.** Those are boards the harness reads completely, so the supported stop
is a real engine behaviour and NOT an artefact of idx3's missing rows and columns. ⛔ The
suspicion recorded last tick — that a stop might just be an unmodelled obstacle on the truncated
level — is retired by measurement, and the axis is open again with events from three levels
instead of one.

The bug is worth naming for what it is rather than as a fix: a diagnostic that records only
failures produces a corpus of failures and reports it as a corpus. Every conclusion drawn from
those seventeen boards inherited "idx3, and only when it lost", and none of them said so.


## gemma4 at nine runs: deterministic in BOTH directions (2026-08-25)

The repetition count was raised because three draws cannot separate a rate from an accident.
gemma4's nine-run result separates it completely:

| mode | result | distinct answers | distinct boards |
|---|---|---|---|
| select | **9/9 PASS** | — | — |
| fill (split) | **0/9** | **1** | **1** |
| fill_fused | **0/9** | **1** | **1** |
| fill_explicit | **0/9** | **1** | **1** |

**Twenty-seven runs, one answer.** Across three encodings and nine repetitions each, gemma4
returns byte-identical slots every time: `hazard_response: terminate_local`, `spawn: both_flanks`.
There is no sampling illusion in either direction — select is a genuinely high rate and fill a
genuinely zero one.

The board fingerprint added last tick earned its place on its first outing: **one distinct board
across all twenty-seven runs.** The grounding is deterministic here, so the failure is entirely
the model's and cannot be a board it was judged against unfairly. That question would otherwise
still be open, and answering it took no extra run.

The failure's shape is now unambiguous. gemma4's OBJECTIVE is correct — `completion: all` and
`hazard_policy: fatal_on_contact` — while its RESPONSE says `terminate_local`. It declares in one
slot that contact is fatal and in another that a droplet merely dies there, deterministically, 27
times out of 27. This is the encoding-split failure the round has been circling, and gemma4 shows
it is **not** the split's fault: the FUSED encoding, which asks once, produces the same answer
0/9. Whatever makes gemma4 answer `terminate_local` survives being asked in one question instead
of two, and survives being told the contact explicitly.

So for gemma4 the fill verdict is settled and the three encodings are exonerated. What remains
open is gpt-oss, whose split swung 3/3 to 0/3 on three runs and whose nine-run pass is still on
the GPU.


## The fill stage is a ONE-SLOT exam, and the slot is hazard fatality (2026-08-25)

qwen3.8's nine-run pass mirrors gemma4's structure exactly — select 9/9, fill 0/9 in all three
encodings, one distinct answer per encoding, one distinct board — and comparing the two answers
against the oracle slot by slot collapses the whole stage to a single question:

| model | slots differing from the oracle | its stated hazard POLICY | coherent? |
|---|---|---|---|
| qwen3.8 | **`hazard_response` only** | `neutral` | **yes** |
| gemma4 | `piece_response_spawn` (equivalence-class) + `hazard_response` | `fatal_on_contact` | no |
| gpt-oss (3 runs) | objective, in the failing runs | `neutral` beside a fatal response | no |

**qwen3.8 gets five of six slots exactly right — including the exact oracle `empty_flanks_only`,
which gemma4 does not — and fails on `hazard_response` alone.** gemma4's second difference is
`both_flanks`, already established as an equivalence-class answer, so it is not really a second
error. Every model that fails this stage fails on one slot: whether contact with a barrier ends
the attempt or only the droplet.

And qwen settles a story the round had been telling itself. gemma4's failure looked like an
artefact of splitting fatality across two slots, because it answers `fatal_on_contact` in the
policy and `terminate_local` in the response — an incoherence the encoding could plausibly cause.
**qwen answers both slots coherently — `neutral` policy, `terminate_local` response — and is
still wrong.** It is not confused by being asked twice; it simply believes hazards are not fatal.
So incoherence is a symptom in gemma4, not the cause in general, and the encoding cannot be what
the fill stage is measuring.

What the fill stage actually measures, then, is whether a model can read fatality out of the
evidence. Two of three models cannot, deterministically, under three wordings. That is a finding
about the EVIDENCE or about the models, and the round already has the observation that separates
those: the evidence line reports the contact's position and stop and leaves the cause implicit,
and naming it explicitly moved nothing (0/9 for both). ⛔ Do not re-cut the wording a fourth time.


## A tick-0 lane was never seeded — three levels predicted NOTHING (2026-08-25)

With captures from every level available, the bench was widened past idx3 for the first time. The
three cross-level boards came back at 36, 34 and 64 error — worse than any idx3 board — and the
reason is not propagation:

```
cross_idx0: standing=[] falling=[[9, 0, 1]]   invented=0 missed=36
cross_idx1: standing=[] falling=[[10, 0, 14]] invented=0 missed=34
cross_idx2: standing=[] falling=[[1,0,14], [9,0,14], [14,0,14]] invented=0 missed=64
```

**Zero invented, everything missed: the model predicted nothing at all.** `pending` is read as
`pending[len(frontier)]` and the frontier already holds its seed layer when the loop begins, so a
source recorded at tick 0 was never looked up. A board whose only source is a tick-0 lane produced
an empty trajectory. **The contract board hides this** — its source appears in `standing_flow` as
well, so idx0 has always been driven by the seed rather than by the lane.

Fixed by seeding tick-0 pending into the frontier, which is what the loop's own convention already
says: a cell recorded at frontier index 0 IS the seed. Every gate holds — oracle 3/3, grounding,
verifier, mutant certification, 1724 tests — and the contract board stays at 0.

One hypothesis was tested and refuted on the way. `pre` is read before `_top_up` and the trajectory
after it, so a capture spanning a top-up press would pair a board one move stale with the spill of
a board that moved — and the seeded replay does track the observation for five steps and then
diverge by exactly one column, which is what that looks like. A guard that skips the capture when
the top-up pressed changed nothing: on these levels it pressed nothing. **The stale-board reading
is refuted; the divergence is real propagation error on levels never measured before.**

The bench total rises because the model now makes predictions that can be wrong instead of making
none. That is the honest direction: 227 of the old total was "predicted nothing" scoring as if it
were error, on the only boards in the corpus taken from levels the walk CLEARS.


## Correction: the cross-level residual is GROUNDING, not propagation (2026-08-25)

The previous entry closed with "the divergence is real propagation error on levels never measured
before". Tracing cross_idx2's 48 missed cells says otherwise, and the claim is withdrawn.

The model loses the lane-1 stream on its very first step, at `(13,1)`. That cell belongs to this:

```
sink 0:  5 cells  rows [1,2]              cols [1,2,3]
sink 1:  5 cells  rows [1,2]              cols [6,7,8]
sink 2:  5 cells  rows [1,2]              cols [12,13,14]
sink 3: 17 cells  rows [9,10,11,12,13,14] cols [0,1,2]
```

**Sink 3 is seventeen cells over six rows.** The level's real targets are five-cell cups two rows
tall; the grounding has admitted a piece of scenery three times their size as a target, and our
stream is swallowed by it where the engine's flows straight through. That is the round's own open
item — scenery admitted as a target, whose discriminator is SHAPE and where a size threshold was
already measured inert and reverted. It accounts for 15 of the 48.

The other 33 sit in columns 8, 9, 14 and 15, where the captured board places pieces the engine's
flow passes through: `piece 3` spans `(12,10)`–`(12,15)` while the observed spill occupies
`(12,14)`. Either the board is stale for the final plan step — which `w.run(step, g)` executes
AFTER the capture is taken — or the piece is mis-segmented. **Not yet distinguished**, and worth
saying that plainly rather than picking one.

⚠️ It also corrects my earlier refutation. I tested the stale-board reading against `_top_up`,
found it pressed nothing, and concluded the board was not stale. `_top_up` is not the only mover:
the final plan step runs after the capture. The test was sound and its conclusion was drawn wider
than the test.

What this means for the widened bench: the three cross-level boards currently measure the
GROUNDING's fidelity, not the propagator's. They are worth keeping — they are the only boards from
levels the walk clears, and they surfaced a real seeding defect within an hour of being added — but
their error must not be read as a propagation score until the false target and the piece question
are separated.


## The cross-level boards are INVALID, and the fix they justified is reverted (2026-08-25)

Two questions were open: whether the cross-level boards were stale or mis-segmented, and whether
the tick-0 seeding they motivated was right. One measurement answers both.

**Does the engine's flow pass through cells the captured board calls a piece?**

| corpus | boards | pieces per board | pieces the flow passes through |
|---|---|---|---|
| contract idx0 | 1 | 1 | **0** |
| idx3 family | 17 | 5 | **0** |
| **cross-level** | 3 | 1, 3, 4 | **1, 2, 3** |

Twenty-one valid boards, zero pass-throughs. Three cross-level boards, almost all of them. The
capture for a clearing level is taken before the final plan step executes, so the layout recorded
is not the layout that spilled — **stale, decisively, and not mis-segmentation.** The colour check
that pointed at "only the selected piece moves" was refuted on the way: cross_idx1 and cross_idx2
have the flow passing through colour-8 pieces too, not just the colour-9 one.

They are now excluded from the sweep, with the reason in the code, and the files stay in the round
so the next attempt starts from the known state.

**And excluding them refuted the fix they had motivated.** With only valid boards, the tick-0
seeding scores 121 against the baseline's 93 — four boards (`g`, `h`, `i`, `j`, each with a tick-0
lane and no standing flow) go from 5 to 12. Reverted; the bench is back at 197/93 and every gate
holds.

⚠️ Worth stating without softening: I adopted that change one tick ago, with all five gates green,
on the strength of three boards that turn out not to describe their own spills. The gates could
not see it because the contract board carries its source in `standing_flow` and never exercises
the path. What caught it was excluding the invalid evidence and re-reading the number — **the
same measurement I would have had to make anyway to trust the boards.** The lesson is ordering:
validate the corpus BEFORE fitting to it, because a fix justified by bad boards passes every gate
that bad boards do not touch.

The underlying observation survives unchanged and unfixed: a board whose only source is a tick-0
lane predicts nothing. Whether that is a defect or a mis-reading of what the grounding's tick
means is now genuinely open, since the boards that made it look like a defect are gone.


## The capture is fixed, and the propagator reproduces idx0 and idx1 CELL FOR CELL (2026-08-25)

The capture's contract is to pair a board with the trajectory THAT board's action produced. It was
breaking that twice over — reading `pre`, taken before the top-up AND before the final plan step,
against a spill that ran after both. Fixed by holding the board read after the top-up and taking
the trajectory after the action.

The validity test that condemned the old boards now passes on every one:

| board | pieces | flow passes through |
|---|---|---|
| walk_idx0 / idx1 / idx2 | 1, 3, 4 | **0, 0, 0** |
| walk_idx3 ×4 | 5 | **0** |

And on captures that describe their own spills, the tick-0 seeding is not merely defensible — it is
**exact**:

```
board     as-known  physics
idx0             0        0     <- the contract board
idx0             0        0     <- the walk's own idx0 capture
idx1             0        0
idx2            24       24
idx3             3        3     (x4)
sum             36       36
```

**Two levels reproduced cell for cell, and the whole corpus falls to 36.** The old corpus scored
93 on seventeen boards that all came from one level, and only from runs of that level which had
just failed.

⚠️ This reverses the refutation from one tick ago on its own terms. The tick-0 seeding scored 121
against 93 there and was reverted as refuted — measured on boards frozen by the broken site.
Re-measured on boards that pass the pass-through test, the same change makes idx0 and idx1 exact.
**Both measurements were honest; one of them was taken on evidence that did not describe what it
claimed to.** The revert was still the right call at the time: the corpus was the only thing
available and the change lost on it. What made the difference was fixing the instrument rather
than arguing about the number.

idx2's 24 is now the largest single item in the corpus and the first genuinely open propagation
question with valid evidence behind it.


## The propagator is EXACT on three levels — idx2's whole residual is one false target (2026-08-25)

With a corpus that describes its own spills, idx2's 24 cells can finally be traced. They are not
scattered: **zero invented, and all 24 missed belong to ONE stream**, the lane-1 stream, which the
model loses on its very first step from `(14,1)` to `(13,1)`.

That cell belongs to this:

```
sink 0:  5 cells  rows [1,2]               cols [1,2,3]
sink 1:  5 cells  rows [1,2]               cols [6,7,8]
sink 2:  5 cells  rows [1,2]               cols [12,13,14]
sink 3: 17 cells  rows [9,10,11,12,13,14]  cols [0,1,2]
```

Dropping the seventeen-cell region and re-running:

| board | invented | missed |
|---|---|---|
| as grounded | 0 | **24** |
| without the 17-cell region | 0 | **0** |

**The entire residual is that one region.** So the propagator reproduces idx0, idx1 AND idx2 cell
for cell — three consecutive levels, two of them measured for the first time this session — and
every cell of disagreement left in the corpus is the grounding calling a piece of scenery a target.

⛔ The experiment above used `len(s) <= 8` and that is NOT the fix. A size threshold on target
regions was already measured inert and reverted earlier in this round; the discriminator is SHAPE
and it is still open. Two candidates were checked here and both FAIL to separate: the cups and the
block both have a notch cell whose lateral neighbours belong to the region, and both are nearly
solid within their bounding box (5/6 against 17/18). What does differ is extent along the flow
axis — two rows against six — and that is a size threshold wearing a different name, so it is not
adopted either.

What has changed is that the open question now has a price on it: **24 cells, which is 100% of the
remaining error on the only corpus that describes its own spills.** Before this it was a
qualitative complaint about scenery.


## Two notch discriminators, both measured, neither is the lever (2026-08-25)

The false target's only gap is `(14,1)` — which is the lane-1 SOURCE. That suggests a
discriminator by provenance rather than by size: a cell a stream pours FROM cannot be a notch a
stream arrives INTO. Implemented in `_mouths` and measured on a fresh walk:

| rule | the oversized region | idx2 missed |
|---|---|---|
| baseline | 17 cells | 24 |
| notch may not be a source cell | **19 cells** | **24** |
| …and may not lie in the trimmed frame | **19 cells** | **24** |

**Neither removes it.** The first rule works on its own terms — `(14,1)` stops being a mouth — but
the region simply keeps a second notch at `(15,1)`, in the frame row, and grows from 17 cells to
19 because it is no longer split at the first one. Excluding frame-row notches as well leaves it
at 19 and the error at 24.

So the region is not surviving because of its notch, and the notch filter is not where it enters
the shortlist. ⛔ Both rules reverted: one is worse than inert (it enlarges the region) and the
other is inert, and this round keeps neither.

What this buys is a narrowed next step rather than a fix. `sink_candidates()` admits regions from
four independent sources — regions that changed appearance during a spill, regions matching a
named target's shape, regions wearing a named target's appearance, and regions the flow was
OBSTRUCTED by. The notch filter runs *after* all four. **Which of the four names this region is
now the question**, and it is answerable by instrumenting the shortlist on a live grounding rather
than by another rule.

Worth noting against the temptation: `len(s) <= 8` removes it and takes idx2 to zero. It is still
not adopted. A threshold that separates this corpus's four regions is a threshold fitted to four
regions, and the round already measured and reverted one of those.


## The false target comes from OBSTRUCTION, which proposes 187 cells (2026-08-25)

The last entry asked which of `sink_candidates()`'s four sources names the oversized region. The
capture now records all four beside the board it was taken on, and idx2 answers plainly:

```
sinks in the board:  [5, 5, 5, 17]
  changed_appearance   [5, 5, 5]
  obstruction          [187]
  matching_shape       []
  wearing_appearance   []
```

**The three real targets come from changed-appearance. The false one is a fragment of a single
187-cell obstruction region** — two thirds of the whole board — chopped up by the mouth split until
one piece happened to keep a notch.

That reframes the fix completely. The obstruction source is documented as "wherever the flow spread
sideways, something blocked the cell ahead; excluding the known movable pieces, what remains is a
target", and on this level what remains is nearly everything. It is not proposing targets, it is
proposing the complement of the flow. ⛔ Neither notch rules nor size thresholds address that,
which is why both measured inert.

Getting here needed two instruments and one of them was wrong first. A live probe at grounding time
reports **no source above five cells** through the direction probes, the sacrificial commit and the
selection probes — the obstruction region needs accumulated spills, and by then the driver is deep
in its plan. And the probe's own shortlist line printed `[2, 2, 2]` because each entry is a
`(name, cells)` PAIR and `len()` of a pair is 2 regardless of the region: a nineteen-cell region
read as two cells. Fixed, with the trap named in the code.

Recording the sources beside the board is the durable half. A capture that keeps only the final
sinks cannot say where a wrong one came from, and this question had already cost two reverted
rules.


## A background cell blocked nothing — idx2 goes to ZERO (2026-08-25)

The obstruction source proposes a 187-cell region on idx2. Reading what that region IS settles it:

```
false target: colours {12: 15, 11: 2}   touches the border: True
real target 0: colours {12: 5}          touches the border: False
the false target's colour is 12; its connected component spans 187 cells
```

**Colour 12 is the BACKGROUND**, and its connected component is two thirds of the board. The
obstruction source seeded on background-coloured cells, `_regions` handed back the entire
background as one region, and the mouth split carved a seventeen-cell "target" out of empty space.

A blocker has to look like something. A cell wearing the background is empty, so whatever a
flanking pair means there, it is not that this cell obstructed anything. That rule was already
adopted in `barriers()` earlier in this round for exactly this reason; `_obstruction_regions()` is
the other place that reads a blocker's appearance and it did not have it.

Measured after adding it, on captures taken with it in force:

| board | before | after |
|---|---|---|
| idx0 | 0 / 0 | 0 / 0 |
| idx1 | 0 / 0 | 0 / 0 |
| **idx2** | 0 invented / **24 missed** | **0 / 0** |
| idx3 ×4 | 3 / 0 | 3 / 0 |
| **corpus** | **36** | **12** |

**The propagator now reproduces idx0, idx1 and idx2 exactly, and nothing in the corpus is missing
— only twelve invented cells remain, all on idx3.** Oracle 3/3, grounding, verifier, mutant
certification and 1724 tests all hold.

⚠️ One honest caveat, stated because it is a real risk and not visible in the numbers: the
obstruction source now proposes **nothing at all** on every board in the corpus. Its purpose is to
name a target on a board where the probing spill happens to satisfy none, and this corpus cannot
exercise that — every board here has changed-appearance targets. So the rule is right about what
it removes and untested about what it might also remove. A board that needs the obstruction source
would show it, and there is none to hand.


## The caveat is now a pin — and its first version was vacuous (2026-08-25)

The background-blocker rule took idx2 to zero and left a stated risk: the obstruction source now
proposes nothing anywhere in the corpus, so "rejects empty" and "rejects everything" look the same
from the numbers. That is exactly what a pin is for, and the corpus cannot supply one because
every board in it has changed-appearance targets.

The sibling pin already holds the other half — a COLOURED blocker still names a 7-cell obstruction
— so the new one only has to hold that a BACKGROUND-coloured blocker does not. Same board, same
spill, same flanking-pair evidence; only the blocker's appearance differs.

⚠️ **The first version passed with the rule DELETED.** Painting the wall background also erased
the odd interior marker the fixture uses to resolve the scale, so `_infer_scale` read nothing,
the spill was never parsed, and `_obstruction_regions()` returned `[]` for a reason unrelated to
the rule. Keeping the marker coloured and painting only the blocking row fixes it: the pin now
goes red the moment the two-line check is removed, which is the only evidence that it tests its
own subject.

That is the third vacuous test this round has caught by deleting the code a test names and
re-running. It is cheap, it takes one command, and it has never once been wasted.

Gates: oracle 3/3, grounding PASS, corpus 12, 1725 tests.


## The whole corpus residual is ONE step-off decision (2026-08-25)

With grounding fixed, idx3's twelve cells are three cells repeated across four identical captures:
`(4,12)`, `(5,12)`, `(6,12)`. Their cause is one disagreement:

```
  (4, 9)  empty   below (5, 9)  is piece
  (4, 10) empty   below (5, 10) is piece
  (4, 11) empty   below (5, 11) is piece
  (4, 12) empty   below (5, 12) is EMPTY
```

A stream walks the top of a piece spanning columns 9–11 and, at `(4,11)` — **the last supported
cell** — the engine stops. Our model steps off to `(4,12)` and falls two more. That is the entire
remaining error in the corpus.

The decision table, re-run on boards that describe their own spills:

```
on piece   next over piece   STEPPED   33      <- invariant holds, 33/33
on piece   next over empty   STEPPED   27
on piece   next over empty   stopped    9

the step OFF the end, by how far the walk had already gone
  walked 0   STEPPED 17    stopped 0
  walked 1   STEPPED  0    stopped 8
  walked 2   STEPPED  8    stopped 0
  walked 3   STEPPED  2    stopped 1
```

The invariant survives the corpus change: while the next cell is also supported the walk always
continues. The step-off splits 27/9 over 15 stepped and 3 stopped distinct events.

The distance column separates 0 from 1 perfectly — 17 step-offs at zero, 8 stops at one, no
exceptions — and then breaks at two, where all eight step off again. ⛔ Not a reach and not fitted:
a rule that reads "even walks off, odd stops" has one counter-example at three, and this round has
already twice adopted a rule that fitted every point it was shown.

The sharper fact is smaller than the table. Of the three stopped events, the model already gets
**two right** — `(9,8)` and `(13,10)` — and only `(4,11)` wrong. So whatever stops the model at
those two is not reaching this one, and the next question is what distinguishes them, not what
rule governs step-offs in general.


## The walk reach is "at least 2", not 2 (2026-08-25)

Why does the model stop where the engine stops at `(9,8)` and `(13,10)` but not at `(4,11)`?
Instrumenting the propagator's own spawns answers it, and not in the expected way:

```
(4, 11) walked=-1     (4, 12) walked=-1
(9, 7)  walked=-1     (9, 8)  walked=-1
(13,10) walked=-1     WALK_REACH = 2
```

**Every droplet involved carries `walked = -1`** — the unbounded state. The reach binds only
droplets that landed from a falling source, and none of these did, so `WALK_REACH` is not what
stops the model anywhere near the residual.

That invites the obvious check, on the corpus that describes its own spills:

| WALK_REACH | corpus error |
|---|---|
| 1 | **132** |
| 2 | **12** |
| 3 | 12 |
| 99 | 12 |

**Two, three and unbounded are indistinguishable.** The reach has exactly one measured job here:
not to be 1. Its adopted value was chosen on the old corpus, where capping at 2 was worth 32 cells
against larger values — and that corpus is the one whose boards did not describe their own spills.

So the value stands, its justification does not. `WALK_REACH = 2` is now supported as "at least
2", and the round should stop citing 2 as a measured optimum. ⛔ Equally, this is not a reason to
raise it: 2 is the smallest value that costs nothing, and a larger one would be an unmeasured
change dressed as a simplification.

The residual is confirmed as untouched by the reach. Whatever stops the engine at `(4,11)`, it is
not a walk budget of any size.


## Only ONE genuine step-off refusal exists — and it is the model's only error (2026-08-25)

The probe follows a run through CONSECUTIVE layers, so a walk that pauses and resumes reads as two
runs and the join reads as a stop. Checking each reported stop against the whole observation:

```
walk_idx2_1  (13,10) -> (13, 9)   YES observed — not a stop
walk_idx3_x  (9, 8)  -> (9, 7)    YES observed at layer 18 — not a stop
walk_idx3_x  (4,11)  -> (4,12)    never observed — GENUINE
```

**Five of the nine "stopped" instances were the probe's own artefact.** The remaining four are the
same event on four identical captures, so the corpus contains exactly **one** distinct step-off
refusal — and it is precisely the three cells the model gets wrong.

With the check built in, the table settles:

```
on piece   next over piece   STEPPED   33     <- invariant, unchanged
on piece   next over empty   STEPPED   32
on piece   next over empty   stopped    4     <- all one event

DISTINCT events: 17 stepped, 1 stopped
```

And the distance column, which two ticks ago separated `walked 0` from `walked 1` perfectly, now
splits 4 against 4 at `walked 1` and separates nothing. **That apparent pattern was made entirely
of mislabelled stops.**

So there is no step-off rule to find here. Seventeen events say the engine always steps off, which
is what the model already does; one event says otherwise, and one event cannot support a rule. The
residual is a single anomaly needing its own evidence, not a missing mechanism.

⚠️ Third correction to my own count on this axis: 30 stops, then 9, now 4 — and every reduction
came from asking the observation a sharper question rather than from changing the model. The stop
count has never once survived being checked.

⚠️ Process note, second time this round: the gate chain and this entry were written in one command
that hit the 2-minute timeout mid-`pytest`. The commit did not happen and the page edit did not
either, while the oracle and bench lines had already printed PASS. **Checking the artefact rather
than the exit code is what caught it** — the same lesson this round recorded once already, and the
same fix: run the suite on its own.


## The model stage at NINE runs, all three models (2026-08-25)

gpt-oss's nine-run pass completes the stage. Every verdict in this round's model stage now rests
on nine repetitions instead of three:

| mode | gemma4 | qwen3.8 | gpt-oss |
|---|---|---|---|
| select | **9/9** | **9/9** | 8/9 |
| fill (split) | 0/9 | 0/9 | **9/9** |
| fill_fused | 0/9 | 0/9 | **9/9** |
| fill_explicit | 0/9 | 0/9 | 8/9 |

**On the decisive slot, every model is deterministic and they disagree.** gpt-oss answers
`hazard_response: terminate_fatal` in 27 of 27 fill runs across three encodings; gemma4 and
qwen3.8 answer `terminate_local` in 27 of 27 each. One distinct answer per model per encoding, one
distinct board everywhere — the grounding is identical, so the split is entirely the models'.

gpt-oss's two 8/9s are not wrong answers. Both are the verifier returning **UNKNOWN** with
`no partial cover observed: any and all predict the same outcome` — the evidence cannot separate
those objectives, so the harness declines rather than certifying, at zero executed actions. That
is the equivalence-class behaviour this family already has precedent for, working as intended.

⚠️ **The "split encoding destabilises gpt-oss" reading is REFUTED.** It came from 3/3 followed by
0/3 on the same prompt, and at nine runs the split scores 9/9 — the same as fused. The earlier 0/3
failed on the OBJECTIVE, not the hazard slot, and that failure mode did not recur once in nine.
Three runs produced a swing that nine runs show no trace of, which is exactly what raising the
count was for.

So the stage's standing result: **SELECT is confirmed on all three models. FILL is confirmed on
gpt-oss alone, and its two competitors fail deterministically on one slot** — whether contact with
a barrier ends the attempt or only the droplet.


## idx3's failure has MOVED from the compiler to the objective (2026-08-25)

The walk's idx3 line reads "executed the plan without clearing" where it used to read "compiler
UNSATISFIABLE: no layout satisfies the objective". The grounding fixes changed the failure mode,
so the old diagnosis has to be re-taken rather than carried forward.

With the board dumped at the commit, twice in the same run:

```
[forecast] as committed: 3 of 3 target(s), wins=True
[attribute] predicted 24 step(s)/66 cells vs observed 27/63
[attribute] first divergence at step 4: invented [(12, 4)] missed []
[targets] after the commit: [((13, 6), 5), ((13, 9), 5), ((13, 12), 5)]
```

**The model satisfies every target it can see, predicts a win, reproduces the trail to within the
three cells already accounted for — and the engine does not advance.** idx3 now names three
five-cell targets, the false seventeen-cell one having gone with the background-blocker fix.

One candidate is eliminated on the spot. The round's leading explanation has been that a failing
attempt is invalidated by flow reaching a bottom-edge entity, but this spill's deepest row is 14
on a board of 15 and it touches no failure band at all — **there is no contact to invalidate it.**

So the gap is in the OBJECTIVE: the engine wants something our three-target model does not name.
That is consistent with the round's dev-time reading that idx3's level has a fourth region, and
with the measured fixed sixteen-cell window onto a twenty-cell level; this measurement does not
separate those and does not need to yet. What it does establish is that idx3 is no longer a
planning failure — the planner now produces a layout it believes wins, and the disagreement is
about what winning means.

⚠️ Side-effect worth watching rather than claiming benign: the captured idx3 board now records
**no hazard cells at all**, where it used to record two in the frame row. `_frame_band()` keys off
hazard cells, so the frame-band wall is inert on this board. The corpus is unaffected — the
model's only over-production there is the step-off — but a rule that has quietly stopped applying
is exactly the kind of thing that looks fine until a board needs it.


## idx3's fourth target is INSIDE the window, and it has no notch (2026-08-25)

The objective gap left open one tick ago had two candidates: a fourth region outside the
sixteen-cell window, or one inside it that the grounding cannot name. The observation settles it
without ambiguity. Regions wearing the target colour on idx3's captured board:

```
  4 cells  rows 13-14  cols 2-3    <- NOT NAMED
 15 cells  rows 13-14  cols 6-14   <- NAMED (the three cups)
```

**The fourth region is fully inside the window.** ⛔ The truncated-board reading, which this
session established for idx3's geometry and which explained its old compiler failure, does NOT
explain the objective gap. Those are two different problems and only one of them is perception.

Why it goes unnamed is exact:

```
the unnamed region: [(13,2), (13,3), (14,2), (14,3)]   its notches: []
mouths of the NAMED targets: [(13,7), (13,10), (13,13)]
```

A solid 2×2 block wearing the target colour, with **zero** notches, against three cups with one
each. It is filtered by the round's own rule — "a region with no notch is an OBSTACLE, not a
target of this family" — which was adopted for a measured reason: a solid block named by
obstruction made "cover every target" unreachable by construction, which is what the compiler kept
reporting.

So the round's family finding from much earlier is **confirmed under the current grounding, with
coordinates**: the level's objective is four regions, the schema can name three, and the fourth is
a notchless block the engine satisfies while no rule in the vocabulary can express satisfying it —
the satisfaction predicate is "flow occupies the notch", and this region has none.

⛔ Not patched. The schema is frozen and the notch rule earns its keep elsewhere; loosening it to
admit this block would re-open the failure it was adopted to close. This is a family finding for
the next expansion's vocabulary, not a fix for this round.


## The notchless target is idx3's, not the family's (2026-08-25)

A family finding needs its scope measured, so `rule_bench.py --targets` now reports, per board,
every region wearing the target colour that the grounding did NOT name, and whether it has a notch:

```
walk_idx0_1    named [5, 5]      unnamed: (none)
walk_idx1_1    named [5, 5, 5]   unnamed: (none)
walk_idx2_1    named [5, 5, 5]   unnamed: (none)
walk_idx3_x    named [5, 5, 5]   unnamed: 4 cells, 0 notch(es)     (all four captures)
```

**Three levels of four are fully expressed by the current vocabulary.** The notchless target
appears only on idx3, and on every capture of it. So the schema's satisfaction predicate — flow
occupies the notch in the target's top edge — is sufficient for idx0, idx1 and idx2 and fails at
exactly one level.

That is the scoping the finding needed. It is a level's mechanic rather than a family-wide gap,
which changes what the next expansion owes: not a wider predicate for FlowDeflection in general,
but a decision about whether a family is allowed to contain a level its vocabulary cannot express.
⛔ Still not patched here — the notch rule closes a real failure and the schema is frozen.

The contract board reports "(no colours recorded)" honestly rather than being skipped: it predates
the capture format that keeps appearances. That is worth leaving visible, because a silent skip is
how a corpus quietly stops covering the board it is built on.


## The vanished hazards are not a regression — and the old corpus recorded them out of bounds (2026-08-25)

Last tick flagged that idx3's captured board now records no hazard cells, leaving `_frame_band()`
inert there. Checked across the corpus rather than assumed:

```
CURRENT                                     OLD (pre-fix, excluded)
  idx0         size 16  hazards [15,3] [15,9]      r98_idx3_a  size 16  hazards [15,1] [15,4]
  walk_idx0_1  size 16  hazards [15,3] [15,9]      r98_idx3_b  size 16  hazards [15,1] [15,4]
  walk_idx1_1  size 16  hazards [0,6] [0,10]       r98_idx3_o  size 15  hazards [15,0] [15,4]
  walk_idx2_1  size 16  hazards [0,0] [0,9] [0,15] r98_idx3_p  size 15  hazards [15,1] [15,4]
  walk_idx3_x  size 15  hazards []
```

**Hazard detection is intact.** Three levels of four still record them, and they sit on the edge
the flow runs INTO — row 15 for idx0's downward flow, row 0 for idx1's and idx2's upward flow,
which is a coherence check the numbers pass without being asked to.

idx3 records none because its board is **fifteen cells and row 15 does not exist in it**. There is
nothing for `_frame_band()` to be inert about; the frame row has been trimmed out of the board
rather than left in it unmarked. So the flag resolves as a non-issue, and checking cost one query.

⚠️ The same query indicts the old corpus once more. `r98_idx3_o` and `r98_idx3_p` are **size 15
with hazards recorded at row 15** — outside their own board's bounds, where no cell can be. Those
boards were already excluded for pairing a layout with someone else's spill; this is a second,
independent way they do not describe themselves. The round has now found three separate defects in
that corpus and adopted-then-reverted two rules fitted to it, which is a reasonable price for
learning to validate a corpus before trusting it, and an unreasonable one to pay twice.


## Two thirds of the walk is DISCOVERY (2026-08-25)

The certified oracle path clears idx0 in 10 actions — 8 discovery, 2 plan — and the walk takes 23.
The scoring metric is the square of the action ratio, so that difference is not bookkeeping.
Broken down per level:

| level | discovery | plan | total |
|---|---|---|---|
| idx0 | **21** | 2 | 23 |
| idx1 | 22 | 8 | 30 |
| idx2 | 29 | 26 | 55 |
| idx3 | 20 | 10 | 30 |
| **all** | **92** | 46 | 138 |

**Discovery is 92 of 138 actions, and it is re-paid in full on every level** — twenty to twenty-nine
each, on a game whose levels share their flow colour, their piece appearances and their controls.
On idx0 the plan itself is two actions; everything else is finding out what to plan.

⚠️ The 21-against-8 gap is real but not all of it is waste, and saying otherwise would be the
easy misreading. The oracle path is *given* the hypothesis, so it never probes to find which cell
selects a piece; the walk spends four to six actions per level on exactly that. What the comparison
establishes is the SIZE of the discovery bill, not that it is all avoidable.

It also joins two threads the round has been treating separately. The walk spends one sacrificial
commit per level and a run has four failed commits for the whole GAME, so the discovery bill and
the depth ceiling are the same bill. And the direction — the thing that commit buys — was measured
NOT invariant across levels, so it genuinely has to be re-bought. What has never been measured is
whether the SELECTION probes are re-buying something that does not change, and that is the next
question on this axis rather than another rule.


## The selection probes DO re-buy an invariant — and it is probably worth nothing (2026-08-25)

The open question was whether the walk's four-to-six selection probes per level re-establish
something that does not change. Recording what they buy:

```
[bought] idx0 selected=None idle=None commit_action=5
[bought] idx1 selected=9    idle=8    commit_action=5
[bought] idx2 selected=9    idle=8    commit_action=5
[bought] idx3 selected=9    idle=8    commit_action=5
```

**Identical on every level that can observe them.** The selected and idle appearances are a
property of the game's sprites, not of a layout, and the commit action is 5 throughout. idx0 reads
`None` for the pair because its single piece starts pre-selected — the same reason `control_mode`
was recorded as an unestablished premise at that level.

So the answer is yes, and the honest follow-through is that it probably buys nothing to fix.
**The probes are not appearance-learning routines**; their stated job is segmentation — selecting a
piece is what separates it from a neighbour it is touching, and a planner that can only move a
merged pair cannot solve a board that needs them placed independently. That job IS per-level,
because the pieces and their contacts differ every time. The appearance falls out of the probe as a
by-product.

⛔ So this is not a saving of eighteen actions waiting to be collected. Carrying the appearances
forward would let the walk *skip* probes only if segmentation were already settled, and it is not.
What the measurement does establish is which half of the discovery bill is genuinely per-level:
direction is (measured non-invariant), segmentation is (pieces move), appearances and the commit
action are not — and the last two are the only parts a cross-level memory could ever remove.


## The largest item in the discovery bill bought NOTHING — walk 138 -> 106 (2026-08-25)

Splitting discovery into its phases finds one item that is both the biggest and perfectly
constant:

```
idx0  fixed probes=5  direction retries=8  selection probes=4  commit + aiming=4
idx1  fixed probes=5  direction retries=8  selection probes=6  commit + aiming=3
idx2  fixed probes=5  direction retries=8  selection probes=6  commit + aiming=10
idx3  fixed probes=5  direction retries=8  selection probes=6  commit + aiming=1
```

Eight actions a level, every level, on a retry loop that presses each unmeasured direction up to
twice more. Asking what it achieves:

```
[deltas] idx0 after the fixed probes: []      [deltas] idx0 after the retries: []
[deltas] idx1 after the fixed probes: []      [deltas] idx1 after the retries: []
[deltas] idx2 after the fixed probes: []      [deltas] idx2 after the retries: []
```

**Empty before, empty after, on every level.** The loop's own success condition — a direction
appearing in `deltas_of(g)` — is never met, so it repairs nothing and simply pays the toll.

Removed, and measured rather than assumed:

| | before | after |
|---|---|---|
| idx0 | 23 | **15** |
| idx1 | 30 | **22** |
| idx2 | 55 | **47** |
| idx3 attempt | 30 | 22 |
| **walk total** | **138** | **106** |

Same three levels carried, same idx3 stop, **32 fewer actions — 23% of the walk**. Every gate
holds: oracle 3/3, grounding, verifier, mutant certification, corpus 12, 1725 tests.

⚠️ Said fairly: the loop was added for a real measured reason — the engine does drop a press, and
that cost idx3 a discovery slide once. What has changed is that the grounding no longer reports
deltas at this point in the sequence at all, so the guard it retries on is permanently absent. **A
retry guarded on a signal that is never present is not a safety net, it is a toll**, and the
distinction is only visible if you ask what the guard reads rather than what the comment says.

This is the first measured EFFICIENCY gain of the round, on a metric that squares the action ratio.


## Correction: the retry DID buy something — relocating it costs 1 action, not 32 (2026-08-25)

The previous entry removed the direction-retry loop on the strength of `deltas_of(g)` being empty
before and after it, and concluded it "repairs nothing and simply pays the toll". Checking the
table where its CONSUMERS read it — at plan time, after the sacrificial commit — says otherwise:

```
with the retries      idx3 at plan time: [1:(-1,0)  2:(1,0)  3:(0,-1)  4:(0,1)]
without them          idx3 at plan time: [1:(-1,0)           3:(0,-1)  4:(0,1)]
```

**idx3 loses direction 2 without the retries.** The presses did buy something; they just bought it
too late to be visible at their own measurement point, which is exactly what made the loop look
inert. My "it repairs nothing" was measured at the wrong place and is withdrawn.

The fix is not to restore it but to MOVE it. The table is empty before the commit and filled after,
so a retry placed afterwards only presses a direction that is genuinely missing:

| | actions | idx3 directions |
|---|---|---|
| original (retry before the commit) | 138 | 4 |
| removed entirely | 106 | **3** |
| **retry after the commit** | **107** | **4** |

**Same information as the original for 31 fewer actions**, because the loop now costs one press on
the one level that needs it instead of eight presses on every level. Oracle 3/3, grounding,
verifier, mutant certification, corpus 12, walk carrying the same three levels.

The lesson is narrower than "measure before removing" — I did measure. It is: **a guard reads a
signal at ITS site, but the value it protects is consumed somewhere else, and only the consumer's
reading can say whether the guard is doing anything.** Emptiness at the guard proved the loop
could not be working *there*; it took the consumer's table to show it was working anyway.


## The four-lives ceiling does not bind — 9 non-advancing commits and the game is alive (2026-08-25)

The round has reasoned about depth on a premise recorded much earlier: a run has four failed
commits for the whole GAME, the walk spends one per level, and therefore the discovery bill IS the
depth ceiling. Counting what the walk actually spends:

```
[aiming] idx0 commits so far 1     idx1: 4     idx2: 7     idx3: 10
[commits] 12 ACTION5 presses, 9 of which did NOT advance a level; alive=True
[one more commit] state=GameState.NOT_FINISHED alive=True
```

**Three commits per level — sacrificial, aimed re-commit, and the plan's own — twelve in all, nine
of which advance nothing, and the game is still alive.** The recorded test for the ceiling was
"pressing once more after the walk stops returns GAME_OVER immediately"; run again now, it returns
`NOT_FINISHED`.

So two things separate that were being treated as one. **A non-advancing ACTION5 is not the same
event as a spent life**, and counting the former is not a way to measure the latter. The walk
issues nine and is nowhere near the end.

⛔ The "one life per level, four lives, six levels" argument therefore does not establish the depth
ceiling in the current state, and every conclusion that leaned on it needs re-reading. That
includes the framing that discovery cost and depth are the same bill — they may still be related,
but not by this arithmetic.

What is NOT claimed: that the game has more than four lives, or that the earlier observation was
wrong when it was made. It was measured in a state several fixes ago, and what changed since is
unmeasured. The honest position is that the premise does not hold now and the reason is open.


## Four Next items were answered and still read as open (2026-08-25)

The Next list is what a future session acts on, and four of its entries had been overtaken by this
session's measurements while still reading as live questions. Closed with their evidence:

- **"idx3 was never being judged — the game was already OVER"** → it is now reached with lives in
  hand and it IS judged: 12 commits, 9 advancing nothing, `NOT_FINISHED` with a press to spare, the
  plan executed, `wins=True` forecast, engine refuses.
- **"A COMMIT IS NOT FREE"** → the arithmetic does not bind. A non-advancing ACTION5 is not a spent
  life; nine leave the game alive.
- **"Advancement needs every target satisfied AND A FLAG CLEAR"**, whose leading reading was flow
  reaching the floor → not operative on idx3: deepest row 14 on a board of 15, no failure band
  touched at all.
- **"idx3 is NOT won by covering its regions (measured on a game already over)"** → re-measured on a
  game that is not over, with the fourth region now identified as a notchless 2x2.

None of these is new measurement; all four are this session's results reaching the one list that
tells the next reader what to do. Two ticks ago the same staleness was found in `rounds/index.md`
and CLAUDE.md, and the round page's own Next list turns out to have had it too — **a page can be
scrupulously appended to and still misdirect, because new entries go at the top while the
instructions live at the bottom.**


## Next

1. **OOD controls: CERTIFIED** (`scripts/rounds/R98/ood_certification.py`) — sp80 reads
   and passes, tu93 and re86 decline, all on the same discovery. Both controls decline at
   perception, so the verifier is not exercised by them; a near control that assembles a
   board and is then refuted would test more.
2. **Fill: the FUSED experiment is ANSWERED — the split was not the cause.** gemma4 gives
   byte-identical slot answers under both encodings (`hazard_response: terminate_local`),
   so asking once changes nothing and the schema is exonerated on this point. It misses
   TWO slots, not one (`spawn` and `hazard`), correcting the frozen record; `select`
   reproduces 3/3. gpt-oss still running — it decides whether FILL is confirmed paired.
3. ~~Fill is not confirmed paired.~~ The experiment is built AND covered by the harness
   self-test (`fill fused -> cleared PASS`), so its wiring is verified without a GPU;
   split remains the default, and the KAGGLE kernel now runs it as a third mode
   (`fill_fused`) beside the two frozen ones. **RUNNING on Kaggle since 2026-08-25 00:47**
   — gemma4 and gpt-oss (the contract pair) at version 5; qwen3.8 waits on a GPU slot.
   Never as a patch to move a verdict.
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
12. ~~idx3 is still UNSATISFIABLE, now on 4 of 5 pieces.~~ **Three false hazards** —
    background cells and frame cells — made every reachable layout fatal. idx3 now plans
    and executes on all five pieces.
16. ~~Run the decisive test on the parked diagnosis.~~ **RUN — it does not confirm it.** A
    plan aimed at all four regions executed, the flow reached the block's ROOF at (12,2),
    the block did not recolour and the level did not advance. So why DOES idx3 stop? That
    is the open question now, and the fourth region is no longer the leading answer.
17. **Engine-confirmed, and sharper**: on idx3's final spill the engine RECOLOURED all
    fifteen target cells — its own satisfaction signal — and `levels_completed` stayed 3.
    The fourth region is the leading answer again, on evidence. What is unknown is HOW it
    wants to be filled: roof contact is refuted, and our propagator can deliver nothing
    else, since it deflects around an absorber and never enters one.
18. **idx3 carries an EMBEDDED SOURCE at (7,4)**, inside the only piece whose motion moves
    a stream, and the block is within its reach. That is the instrument the next
    experiment should use.
19. ~~The block has never been observed to recolour.~~ **It has now** — with the block as
    the SOLE target the engine recoloured it, and the plan that did it moved the piece
    carrying the embedded source. All four regions are individually fillable; no layout
    yet fills all four at once, and that is the open problem.
20. ~~The model's `contact` is looser than the engine's requirement.~~ **Withdrawn** — that
    rested on the same invalid reading. The four-target plan DID recolour the block.
22. ~~idx3's attempt is REJECTED, not left incomplete.~~ **Withdrawn** — idx0's CLEARING
    spill reverts its targets to 11 on the final layer too. The revert is how every spill
    ends. The unanswered question is still the one from #21.
23. **sp80 has SIX levels**; idx3 is the fourth. "The last level signals completion
    differently" is eliminated, and the depth ceiling for this family is 6 — the walk
    carries one hypothesis through 3 of them.
24. ~~Advancement needs every target satisfied AND A FLAG CLEAR~~ **— the flag reading is NOT
    operative on idx3 (2026-08-25).** Its spill's deepest row is 14 on a board of 15 and it
    touches no failure band at all, so there is no contact to invalidate the attempt. What
    idx3 is missing is a FOURTH target, inside the window, solid 2x2, zero notches. Original
    note:** (read from the game
    source, dev-time only, never for the runtime path). The flag is set when flow reaches
    a tagged sprite that recolours to 14 — a FAILURE ENTITY the schema cannot express,
    since `hazard_policy`/`hazard_response` only describe what flow does on meeting a
    barrier, not one that passes it and invalidates the attempt. **Observation IN**: a
    failed commit flashes the board's BOTTOM EDGE ROW in colour 14, inside the failing
    spill; four failures end the game. Leading reading: flow reaching the floor
    invalidates the attempt. Not yet confirmed on idx3 — the flash alternates 14/1 and an
    even step is invisible against the frame's own colour.
25. ~~idx3 was never being judged — the game was already OVER.~~ **RESOLVED 2026-08-25 — it
    is reached with lives in hand and it IS judged.** The walk now issues 12 commits, 9 of
    which advance nothing, and the game is `NOT_FINISHED` with one more press to spare. idx3
    executes its plan, the model forecasts 3 of 3 targets and `wins=True`, and the engine
    refuses. Original note:** Pressing once more after
    the walk stops returns `GAME_OVER` immediately. A run has FOUR failed commits for the
    whole game, not per level, and the walk spends them probing (one sacrificial commit
    per level on a six-level game). Every idx3 explanation this round built was about a
    level that was not going to be judged. Next: reach idx3 with lives left.
26. ~~A COMMIT IS NOT FREE.~~ **The arithmetic does NOT bind (2026-08-25).** A non-advancing
    ACTION5 is not the same event as a spent life: nine of them leave the game alive. Costing
    discovery in "lives" is not a measurement, and conclusions drawn from it need re-reading.
    Original note:** Discovery was costed in actions and never in failed
    commits. One life recovered by not re-committing when the aiming moved nothing;
    three more are spent because every level builds a FRESH grounding and re-learns the
    flow's direction and colour, which cannot change within a game.
44. **The scale defect touches at least SIX of twenty-five games** — ar25 (21), cn04 (20),
    ka59 (45), m0r0 (11), tu93 (39) on their FIRST level, plus sp80 on its fourth. The
    property is per LEVEL, so that is a floor. The fix belongs in `_infer_scale`, the
    entrance to every frame reading in the project, not in anything R98-specific.
53. **Under the claimed table, NO placement wins idx3** — 15840 valid layouts enumerated,
    every one fatal, including the 24 that fill all three named targets. So the
    compiler's UNSATISFIABLE is the truth about the board rather than a search failure.
    Either the propagator floors flow the engine does not, or the level wants more than
    one placement.
109. **Four Next items were answered and still read as open** — idx3 never being judged, "a
     commit is not free", the flag reading, and idx3 not being won by covering its regions.
     All four closed with this session's evidence. A page can be scrupulously appended to and
     still misdirect: new entries go at the top while the instructions live at the bottom.
108. ⛔ **The four-lives ceiling does NOT bind — 9 non-advancing commits and the game is
     alive.** The walk issues 3 commits a level (sacrificial, aimed re-commit, the plan's) =
     12 in all, 9 advancing nothing, and `alive=True`. The recorded ceiling test — one more
     press returns GAME_OVER — now returns `NOT_FINISHED`. So a non-advancing ACTION5 is NOT
     the same event as a spent life, and counting the former does not measure the latter.
     Every conclusion leaning on "one life per level, four lives, six levels" needs
     re-reading, including "the discovery bill IS the depth ceiling". Not claimed: that the
     game has more than four lives, or that the old observation was wrong when made.
107. ⚠️ **CORRECTION to #106: the retry DID buy something — relocating it costs 1 action, not
     32.** Read where its CONSUMERS read the table (plan time, after the commit): with the
     retries idx3 has all four directions, without them it has THREE. The presses bought a
     direction too late to show at their own site. Fix is to MOVE not remove: retry after the
     commit, when only a genuinely missing direction is pressed. **138 -> 107 with all four
     directions everywhere** (removal alone was 106 with idx3 down to three). Lesson: a guard
     reads a signal at ITS site while the value it protects is consumed elsewhere, and only
     the consumer's reading can say whether the guard does anything.
106. ~~The largest item in the discovery bill bought NOTHING — walk 138 -> 106.~~ Half right:
     the phase split and the emptiness are correct, the conclusion is corrected by #107. Phase split:
     `fixed probes=5, direction retries=8, selection probes=4-6, commit+aiming=1-10`, with the
     retries constant at 8 on every level. `deltas_of(g)` is EMPTY before them and EMPTY after,
     so the loop's own success condition never fires. Removed: idx0 23 -> **15**, idx1 30 ->
     **22**, idx2 55 -> **47**, total **138 -> 106**, same three levels, all gates green
     (oracle 3/3, corpus 12, 1725 tests). ⚠️ It was added for a real reason (the engine does
     drop a press); what changed is that grounding no longer reports deltas there at all. A
     retry guarded on a signal that is never present is a toll, not a safety net. FIRST
     measured efficiency gain of the round.
105. **The selection probes DO re-buy an invariant — worth probably nothing.** What they buy
     is identical on every level that can observe it: `selected=9 idle=8 commit_action=5`
     (idx0 reads None because its piece starts pre-selected). But the probes are not
     appearance-learning routines — their job is SEGMENTATION, separating a piece from the
     neighbour it touches, which is genuinely per-level. ⛔ No eighteen actions waiting to be
     collected. What is established is which half of the discovery bill is per-level:
     direction yes (measured non-invariant), segmentation yes, appearances and commit action
     NO — and only those last two could ever be removed by a cross-level memory.
104. **Two thirds of the walk is DISCOVERY.** Per level: idx0 21 discovery / 2 plan, idx1
     22/8, idx2 29/26, idx3 20/10 — **92 of 138 actions**, re-paid in full every level. The
     certified oracle path does idx0's discovery in 8. ⚠️ Not all of the 21-vs-8 gap is
     waste: the oracle path is GIVEN the hypothesis and never probes to find which cell
     selects a piece, which is 4-6 actions per level for the walk. It joins two threads —
     one sacrificial commit per level against four lives per GAME means the discovery bill
     IS the depth ceiling. Direction is measured non-invariant so it must be re-bought; the
     open question is whether the SELECTION probes re-buy something that does not change.
103. **The vanished hazards are NOT a regression.** Detection is intact — idx0 `[15,3] [15,9]`,
     idx1 `[0,6] [0,10]`, idx2 `[0,0] [0,9] [0,15]` — and each sits on the edge the flow runs
     INTO (row 15 for downward flow, row 0 for upward), a coherence check passed unasked.
     idx3 records none because its board is FIFTEEN cells and row 15 does not exist in it. ⚠️
     The same query indicts the old corpus again: `o` and `p` are size 15 with hazards at row
     15, outside their own bounds — a second independent way those boards do not describe
     themselves.
102. **The notchless target is idx3's, NOT the family's.** `--targets` reports every unnamed
     target-coloured region per board: idx0, idx1 and idx2 have NONE; idx3 has the 4-cell,
     0-notch block on all four captures. So the notch-based satisfaction predicate is
     sufficient for three levels of four and fails at exactly one — a level's mechanic, not a
     family-wide gap. What the next expansion owes is therefore a decision about whether a
     family may contain a level its vocabulary cannot express, not a wider predicate.
101. **idx3's FOURTH target is INSIDE the window, and it has NO NOTCH.** Regions wearing the
     target colour: 4 cells at rows 13-14 cols 2-3 (NOT named) beside the 15 cells of the three
     named cups. ⛔ So the truncated-board reading does NOT explain the objective gap — the
     fourth region is fully visible. It is a solid 2x2 with ZERO notches against three cups
     with one each (`(13,7)`, `(13,10)`, `(13,13)`), filtered by "a region with no notch is an
     OBSTACLE". The old family finding is CONFIRMED under the current grounding with
     coordinates: the objective is four regions, the schema names three, and satisfaction is
     "flow occupies the notch" which this one has not. ⛔ Not patched — schema frozen.
100. **idx3's failure has MOVED from the compiler to the OBJECTIVE.** The walk now reads
     "executed the plan without clearing" where it read "compiler UNSATISFIABLE". At the
     commit, twice: forecast **3 of 3 targets, wins=True**, trail 66 predicted vs 63 observed
     with the known `(12,4)` as the first divergence — and no advance. One candidate is
     eliminated: the spill's deepest row is 14 on a board of 15 and it touches NO failure
     band, so the "flow reaches the bottom entity" reading is not operative here. The gap is
     in what winning MEANS. ⚠️ Side-effect: idx3 now records no hazard cells, so
     `_frame_band()` is inert on that board.
99. **THE MODEL STAGE AT NINE RUNS, ALL THREE MODELS.** select: gemma4 9/9, qwen 9/9, gptoss
    8/9. fill / fused / explicit: gemma4 0/9, qwen 0/9, **gptoss 9/9 / 9/9 / 8/9**. On the
    decisive slot every model is DETERMINISTIC and they disagree — gptoss `terminate_fatal`
    27/27, gemma4 and qwen `terminate_local` 27/27 each, one board throughout. gptoss's two
    8/9s are verifier UNKNOWNs on a data-indistinguishable objective axis, not wrong answers.
    ⚠️ The "split encoding destabilises gptoss" reading is REFUTED: 3/3-then-0/3 became 9/9,
    and the earlier failure was on the OBJECTIVE, never recurring in nine.
98. **Only ONE genuine step-off refusal EXISTS, and it is the model's only error.** A run is
    followed through CONSECUTIVE layers, so a walk that pauses and resumes read as a stop:
    `(9,7)` is observed at layer 18 and `(13,9)` too. Five of nine "stops" were artefacts;
    the remaining four are ONE event, `(4,11)`, which is exactly the model's 3 wrong cells.
    Table: 17 distinct stepped events against 1 stopped, and the distance column that
    separated 0 from 1 now splits 4/4 — that pattern was made of mislabelled stops. There is
    NO step-off rule to find here. ⚠️ Third correction to this count: 30 -> 9 -> 4.
97. **The walk reach is "AT LEAST 2", not 2.** Every droplet near the residual carries
    `walked = -1` (unbounded — the reach binds only landing droplets), so the reach stops
    nothing there. Swept on the valid corpus: reach 1 -> **132**, reach 2/3/99 -> **12**,
    indistinguishable. Its one measured job is not to be 1. The "capping at 2 is worth 32
    cells" result came from the old corpus whose boards did not describe their own spills.
    The value stands; the justification is weaker. ⛔ Not a reason to raise it either.
96. **The WHOLE corpus residual is ONE step-off decision.** idx3's 12 cells are `(4,12)`,
    `(5,12)`, `(6,12)` on four identical captures: a stream walks a piece spanning cols 9-11
    and the engine STOPS at the last supported cell `(4,11)` while the model steps off. The
    decision table on valid boards: the "next cell also supported -> always continues"
    invariant holds 33/33; step-off splits 27/9. Distance separates 0 (17 step-offs) from 1
    (8 stops) perfectly and breaks at 2. ⛔ Not fitted. Sharper: of three stopped events the
    model already gets TWO right — only `(4,11)` is wrong, so the question is what
    distinguishes them.
95. **The caveat is now a PIN, and its first version was VACUOUS.** #94's untested risk —
    "rejects empty" versus "rejects everything" — is pinned: a background-coloured blocker
    names no obstruction while the sibling pin holds that a coloured one still names a
    7-cell region. ⚠️ The first version passed with the rule DELETED, because painting the
    wall background also erased the marker the fixture needs to resolve the scale, so
    nothing was read at all. Keeping the marker fixes it; the pin now goes red exactly when
    the rule is removed. Third vacuous test caught this round by the same one-command check.
94. **A BACKGROUND CELL BLOCKED NOTHING — idx2 GOES TO ZERO.** The false target's colour is
    12, the BACKGROUND, whose connected component is 187 cells: obstruction seeded on empty
    cells and the mouth split carved a "target" out of empty space. Skipping
    background-coloured blockers — the rule `barriers()` already carries — takes idx2 from
    24 missed to **0** and the corpus from 36 to **12**, with idx0/idx1/idx2 all exact and
    nothing missing anywhere. All five gates hold. ⚠️ Caveat: obstruction now proposes
    NOTHING on every board here, and this corpus cannot exercise the case it exists for.
93. **THE FALSE TARGET COMES FROM `obstruction`, WHICH PROPOSES 187 CELLS.** Captures now
    record all four shortlist sources beside the board: idx2's real targets are
    changed_appearance `[5,5,5]` and the 17-cell false one is a fragment of a SINGLE
    187-cell obstruction region — two thirds of the board — split by mouths until a piece
    kept a notch. The source is proposing the complement of the flow, not targets, which is
    why notch rules and size thresholds both measured inert. Two probe traps recorded: no
    source exceeds 5 cells at grounding time (obstruction needs accumulated spills), and the
    shortlist's entries are `(name, cells)` PAIRS so `len()` reports 2 for every region.
92. ⛔ **Two notch discriminators measured, neither is the lever.** "A notch may not be a
    SOURCE cell" (the false target's only gap is the lane-1 source) works on its own terms
    but the region keeps a second notch at `(15,1)` and GROWS 17 -> 19; adding "nor in the
    trimmed frame" leaves 19 and idx2 still at 24. Both reverted — one worse than inert, one
    inert. The region does not survive on its notch, so the filter is not where it enters.
    Next: WHICH of `sink_candidates()`'s four sources names it, instrumented on a live
    grounding. (`len(s) <= 8` still removes it and is still not adopted.)
91. **THE PROPAGATOR IS EXACT ON THREE LEVELS.** idx2's 24 cells are ZERO invented and all
    24 missed from ONE stream, lost at its first step into `(13,1)` — a cell inside a
    SEVENTEEN-cell "sink" spanning six rows, where the level's real targets are five-cell
    cups. Drop that region and idx2 goes 24 -> **0**. So idx0, idx1 and idx2 all reproduce
    cell for cell and every remaining cell of error in the corpus is scenery-as-target. ⛔ The
    experiment used a size threshold and that is NOT the fix (already measured inert); notch
    and bounding-box fill both FAIL to separate cup from block. The open question now has a
    price: 24 cells, 100% of the residual.
90. **THE CAPTURE IS FIXED, AND THE PROPAGATOR REPRODUCES idx0 AND idx1 CELL FOR CELL.**
    The board is now read after the top-up and the trajectory after the action, so a capture
    describes its own spill: pass-through is 0 on every board. On that corpus the tick-0
    seeding is EXACT — idx0 0, idx1 0, idx2 24, idx3 3 each, **sum 36** against the old
    corpus's 93 on seventeen boards from one level. ⚠️ This reverses #89's refutation on its
    own terms: both measurements were honest and one was taken on evidence that did not
    describe what it claimed. Fixing the instrument settled it, not arguing about the number.
89. ⛔ **The cross-level boards are INVALID and the tick-0 fix is REVERTED.** The engine's
    flow passes through 0 of 5 pieces on all 17 idx3 boards and the contract board, and
    through 1/1, 2/3, 3/4 on the cross boards: their capture is taken before the final plan
    step, so the layout recorded is not the one that spilled. Excluded from the sweep — and
    excluding them refuted the tick-0 seeding they had motivated (121 vs 93; `g h i j` 5->12
    each). Reverted, back to 197/93, all gates hold. ⚠️ That change passed five green gates
    one tick ago on boards that do not describe their own spills. Validate the corpus BEFORE
    fitting to it.
88. ⚠️ **CORRECTION to #87: the cross-level residual is GROUNDING, not propagation.**
    cross_idx2 loses the lane-1 stream at `(13,1)`, which belongs to a SEVENTEEN-cell "sink"
    spanning six rows — the level's real targets are five-cell cups. That is the open
    scenery-as-target item and accounts for 15 of 48 missed. The other 33 are in columns
    where the board places pieces the engine's flow passes through: stale board (the final
    plan step runs AFTER the capture) or mis-segmentation, NOT yet distinguished. My earlier
    refutation tested `_top_up` only and was drawn wider than the test.
87. **A tick-0 lane was never seeded — three levels predicted NOTHING.** Widening the bench
    past idx3 for the first time exposed it: cross_idx0/1/2 scored 36/34/64 with ZERO
    invented, i.e. an empty trajectory, because `pending` is read at `len(frontier)` >= 1
    and a tick-0 source is never looked up. The contract board hid it by also carrying that
    source in `standing_flow`. Fixed; all five gates hold and idx0 stays 0. The stale-board
    reading (`pre` taken across a `_top_up` press) was tested and REFUTED — the top-up
    pressed nothing on these levels.
86. **The fill stage is a ONE-SLOT exam and the slot is hazard fatality.** qwen3.8 at nine
    runs mirrors gemma4 (select 9/9, fill 0/9 x3, one answer, one board) and gets FIVE of six
    slots exactly right — including the exact oracle `empty_flanks_only` — failing on
    `hazard_response` alone. gemma4's extra difference is the equivalence-class `both_flanks`.
    Decisively, **qwen is COHERENT** (`neutral` policy beside `terminate_local`) and still
    wrong, so the split-encoding incoherence is gemma4's symptom, not the general cause.
85. **gemma4 at nine runs is DETERMINISTIC both ways: select 9/9, fill 0/9 in all three
    encodings.** Twenty-seven runs, ONE byte-identical answer (`terminate_local`,
    `both_flanks`), and — via the new fingerprint — ONE distinct board, so the grounding is
    deterministic and the failure is wholly the model's. Its objective is CORRECT
    (`fatal_on_contact`) beside a `terminate_local` response: self-contradictory, 27/27.
    Fused (asked once) and explicit (contact named) both give the same answer, so for gemma4
    the encoding is exonerated. gpt-oss's nine-run pass is still on the GPU.
84. **The capture only ever fired on FAILURE — fixed, and the stops are REAL.** `R98_CAPTURE`
    was one overwritten path AND sat past the clear-check return, so only failing levels were
    ever frozen; that is why all seventeen boards were idx3. Now a prefix, captured before the
    check: one walk yields idx0/idx1/idx2/idx3. New evidence retires #83's suspicion —
    **idx0 `(4,10)` and idx1 `(9,11)` both STOP**, on boards the harness reads completely, so
    the supported stop is engine behaviour and not truncation. A diagnostic that records only
    failures produces a corpus of failures and reports it as a corpus.
83. ⛔ **The 67 step-off instances are 14 EVENTS, and all 3 counter-examples are on idx3.**
    `--events` groups by (cell, direction): 30 "stopped" is three events seen ten times, 37
    "stepped" is eleven events. Every property was tested against 14 points while the table
    said 67 — how two rules got fitted and refuted. All three stops are on idx3, the level
    whose board is provably incomplete (16-cell window on a 20-cell level); idx0, the only
    complete board, has step-offs and no stops. ⛔ Fit no further rule to these captures;
    what is needed is captures from idx1/idx2, which the walk now clears.
82. **Three repetitions cannot carry a verdict — `R98_RUNS` raised 3 -> 9.** gpt-oss gave 3/3
    then 0/3 on the same prompt; three draws from one rate produce both. SELECT survives (3/3
    for all three models on independent runs), FILL is on notice — "only gpt-oss passes" rests
    on a sample observed to swing completely. Dataset-then-kernels sequencing kept.
81. **The record now carries the BOARD the verdict was taken on.** `_board_fingerprint()` on
    every run: size, direction, piece sizes, sink anchors, hazard cells, absorbers, sources.
    Verified populated (idx0's own hazards), and the self-test requires it on every case —
    blanking it turns three cases red. Closes the gap #80 exposed: a CONTRADICTED verdict
    can now be attributed to the model or to the grounding from the artefact alone.
80. ⚠️ **gpt-oss's default fill is UNSTABLE: 3/3 then 0/3 on the same prompt.** Fused is 3/3
    in BOTH runs and explicit 3/3, so the instability belongs to the split encoding. The two
    failing runs answered all SIX response slots exactly as the oracle and failed on the
    OBJECTIVE, self-contradictorily (`hazard_policy: neutral` beside `hazard_response:
    terminate_fatal`) — gemma4's recorded failure in mirror image. The earlier "the schema is
    exonerated on this point" was measured on gemma4 ALONE and does not extend to gpt-oss.
    Nearly filed as a harness defect; the variant field settled it, but the record keeps
    nothing about the BOARD, so a grounding-dependent contradiction would not be separable.
79. **The walk has exactly ONE ambiguous decision, and four properties are eliminated.**
    `--decision`: while the next cell is ALSO supported the walk continues 64/64 — an
    invariant the propagator already reproduces. Every disagreement is the final step off
    the end: 67 instances, 37 stepped / 30 stopped. Ruled out: what the next cell is,
    whether flow ever reaches it, what the droplet stands on (constant), and distance
    walked (0: 26/10, 1: 9/20 — a lean, not a rule). ⛔ Not a licence to re-sweep the reach.
78. ⛔⛔ **#74 and #76 RETRACTED — the evidence base was the defect.** The probe called it a
    spread only when BOTH flanks landed on the same layer; relaxing that takes the table from
    16 rows to 258 and shows BOTH sides walking (`a (10,3)` 3/3, `b (10,3)` 3/4). The
    filtered sample was exactly the asymmetric-looking events, which is why the rule fitted
    to it deleted whole streams on `a` and `p`. What survives, better attested: 80 of 258
    sides end STOPPED on support. The open question is why walks terminate on support on some
    boards and step off on others.
77. ⛔ **The inherited walking side is IMPLEMENTED and REFUTED.** Fourth droplet field
    carrying the decision from the landing: idx0 stays 0 and b/c/d/e/f improve (9->6, 13->11),
    but `a` 1->40 and `p` 0->35 lose whole vertical streams — the engine DOES re-open the
    far side, which the 16 events never showed. Physics 93 -> 150. Reverted; bench back at
    197/93, all four gates PASS. The per-collision expression was one defect; generalising
    from 16 events on near-identical boards was another.
76. ~~The one-side-walks rule is NOT refuted — its expression was.~~ Half right: see #77. idx0's 15 lost cells all
    descend from `(3,4)`, never born because the variant re-decides at EVERY collision and
    the winning walk becomes a "loser" once the surface it has crossed is behind it. The
    decision must be made at the landing and INHERITED, which needs a fourth field on the
    droplet — deliberately NOT done on a non-gating errand. 196/144 score a rule that cuts
    its own walk; they are not evidence against the observed one.
75. **CORRECTION to #74 — five of six events need NO rule.** The probe followed straight
    lateral runs, so "stopped after one cell" and "fell after one cell" read alike. Asking
    for a descendant separates them: idx0's right side FALLS all the way to (12,10) and
    spreads again. Five events are gravity — slide while supported, fall when not — and the
    propagator already gets them right. The anomaly is ONE event on the f-o family: a
    droplet on the piece's LAST cell that could step off and fall, and the engine ends it.
    That single droplet is the whole lateral halo.
74. ~~ONE SIDE WALKS — measured across all 16 observed spread events.~~ The walking side
    runs while supported and takes exactly one step off the end (or stops at the board
    edge); the other side gets its cell and nothing more, even when that cell is supported.
    Which side: the longer supported run in all 16, and also the lower-column side in all
    16 — the captures cannot separate the two. As a rule it is REFUTED (physics 196, idx0
    15). ⚠️ Its first implementation derived the flank from a bogus parity expression and
    scored 332 — a refutation of a rule nobody had measured. `walk_probe.py`.
73. ⛔ **One-sided spawning is REFUTED — three variants, 4-6x worse, all breaking idx0.**
    `spawn()` already refuses an occupied cell, so both-flank spawning is the only source of
    width, and choosing a side at collision is not what the engine does. The halo comes from
    what happens AFTER the spawn. `spread_sweep.py` scores variants without committing them
    and prints idx0 beside every total — the tripwire the earlier 0/3 adoption lacked.
72. **The remaining 93 cells are a LATERAL HALO.** `--where`: 92 of 93 are empty cells, 89
    sit within 3 of an observed cell (so no invented streams), and lateral surplus beats
    longitudinal 57 to 9. The run LENGTH is right; the spread is too wide. Uniform at ~5
    cells per capture — one rule slightly too generous, not board-specific accidents. Lands
    on the asymmetric-spread question (#3); ⛔ still not a licence for another reach sweep.
71. **The explicit-contact experiment is ANSWERED — the wording was never the obstacle.**
    gemma4 and qwen3.8 both answer `terminate_local` in ALL THREE encodings, byte-identical
    across eighteen runs, blocked at zero actions every time. The frozen verdict stands. A
    defect only one of three models can see through is not a defect in the question. ⛔ No
    fourth cut of the encoding.
70. **The frame band is a WALL — adopted.** The engine puts ZERO cells in the hazard row on
    all 18 captures while grounding marks only two of them, and our replay ran one row
    deeper on 13. Treating the whole edge line as the board's edge takes physics 108 -> 93,
    exactly the fifteen cells the row attribution predicted, with idx0 at 0, oracle 3/3,
    grounding/verifier/mutants PASS and the walk unchanged at 3 levels / 138 actions. NOT
    #52 in another coat: a wall ends a droplet where a hazard ends the attempt, and a pin
    goes red if the band is ever folded back into `hazard_cells`.
69. **The bench residual is ALL SURPLUS and NONE of it is the window.** `--rows` attributes
    the physics column by board row: 0 of 108 against the truncated edge, 108 invented and
    ZERO missed, 77 of them in rows 12-15. So the model's trail is a strict superset of the
    engine's — it can claim a target the flow never wets, never miss one it does — and the
    bench remains a valid propagation diagnostic. Stale 211/139 corrected to 209/108.
68. **The window is FIXED — measured, with idx0 as control.** Best whole-frame shift is
    (0,0) on every press of both levels and equals the unshifted agreement, so the render
    never scrolls. With #42's four-row offset this means idx3 shows board rows 4-19 of a
    twenty-row level and rows 0-3 are unreadable. #53's all-fatal enumeration was right for
    the wrong reason: the compiler was planning on a TRUNCATED board. The walk's ceiling of
    three levels is a PERCEPTION ceiling; propagation and schema work cannot reach idx3.
67. ⛔ **The direction is NOT invariant — carrying it forward is REFUTED.** It flips twice
    across four levels ((1,0), (-1,0), (-1,0), (1,0)) while the flow COLOUR is 6 on every
    one. Two geometric substitutes get the three edge-sourced levels and fail idx3, whose
    emitter row is a window row rather than a board row. The one-life-per-level depth
    ceiling is real, not an artefact of the walk.
66. ⚠️ **The same sequencing trap, taken a second time.** Both kernels returned every mode
    ERROR with `rc=2` — argparse refusing `--evidence`, because they ran the OLD probe from
    a dataset that had not been updated. The rule was written down two hours earlier. Fix:
    push the dataset, WAIT for its file listing to show the new size, then push kernels.
65. **The explicit-contact experiment is RUNNING** as a fourth mode beside the three
    frozen ones (gpt-oss v9, gemma4 v8; qwen3.8 when a slot frees). Readings fixed in
    advance: all three pass -> the clause withheld a fact and fill closes; only gpt-oss
    passes -> wording was never the obstacle and the frozen verdict stands; anything worse
    -> the sentence distracts and goes back out.
64. **gpt-oss passes ALL THREE modes at the raised budget** — select 3/3 (every run picks
    the truth and clears), fill 3/3, fill_fused 3/3. The earlier select 1/3 was the
    completion budget, retired as an artefact. qwen3.8 and gemma4 both reproduce select
    3/3 and fill 0/3 under both encodings. Every verdict now measured at least twice.
63. **The OOD controls decline on ALL SIX slots, identically** — the near/far distinction
    the pre-screen drew does not survive into the grounding, so both controls test the
    same thing and the VERIFIER has never been asked to refuse anything. A control that
    reached it would need a game the grounding CAN read whose mechanics differ, and none
    exists among the twenty-five.
62. **gemma4 REPRODUCES exactly** on an independent re-run — select 3/3, fill 0/3 and
    fill_fused 0/3, with `terminate_local` in the same slot both times. So its miss is not
    sampling noise, the fused negative is measured twice, and the explicit-evidence
    variant now has a stable baseline to be judged against.
61. **`--evidence explicit` built, not applied.** The default line reports the position
    and the stop and leaves the CAUSE implicit; the generator already knows a barrier was
    contacted (that is why the line fires at all). The variant names the contact without
    hinting at fatality — a model still decides whether it ends a stream or an attempt.
    Default untouched, frozen verdicts comparable. Run it paired against all three or not
    at all.
60. **The unparsable runs discarded the unparsable thing.** Fixed: raw replies are now
    recorded on both paths. Likely cause, from what the parser accepts — `parse_select`
    takes ANY `I<digit>` token, so those replies contained no answer token at all, which
    is what a reasoning model running out of completion budget looks like. Budget raised
    20000 -> 40000 rather than retried; a retry would be tuning until a run passes.
59. **The ledger, 27 runs across three models**: NO wrong hypothesis ever executed a live
    action — all twelve failures are blocked-by-verifier or unparsable, zero actions each
    — and every passing run cleared in exactly two actions, the oracle path's own cost.
58. **gpt-oss: fill 3/3 in BOTH encodings** — it answers `terminate_fatal` and clears, so
    the evidence IS sufficient and #57's "the description is at fault" is WITHDRAWN. Its
    passing answer uses `both_flanks`, so that value is an EQUIVALENCE-CLASS answer and
    gemma4 misses ONE slot after all — my "two slots" correction was the error. Its select
    1/3 is two UNPARSABLE replies, not wrong picks; the frozen 3/3 stands.
57. ~~WHY both models say `terminate_local`~~: the evidence line that should carry the
    fatal contact says a stream "reached the row just above the bottom edge and stopped
    there" — it describes the mechanism as its opposite, a harmless stop. Read that way
    `terminate_local` is the answer the evidence supports, and the models are reading it
    correctly. Rewriting the clause is a CORRECTNESS fix, not tuning, but it changes what
    every model is asked and belongs in its own paired measurement.
55. **qwen3.8: select 3/3, fill 0/3 under BOTH encodings, missing only
    `hazard_response: terminate_local`.** Two models converge on the same wrong value for
    the same slot — the shape of a prompt/evidence defect, not a model verdict.
56. **Correction to #54's reason**: our propagation does NOT run flow deeper than the
    engine's — deepest flow row is 14 on both sides. The all-fatal enumeration came from
    bounds and hazards sharing one branch, so marking the out-of-bounds row turned every
    normal boundary death into a fatality. The revert was right; its reason was not.
54. ⛔ **The fatal-band adoption is REVERTED — false premise.** The engine's flow never
    reaches that band on idx3 (every spill: touched at []), so the failure the model
    started predicting is a contact the engine does not make. What the change surfaced is
    real and different: OUR PROPAGATION runs flow off the bottom where the engine keeps it
    on — all 15840 layouts flood a row the engine never wets. Next question is
    propagation, not entities.
52. ~~The TRIMMED band is fatal — adopted.~~ Every gate holds, bench and idx0-idx2
    unchanged, and idx3 turns from "compiles, executes, fails silently" into "no layout
    satisfies the objective" — the model finally agreeing with every measurement of that
    level. It also stops the walk spending a life on a doomed commit. Scope: measured on
    sp80; a bottom strip on another game needs the edge-band probe's verdict, not this
    assumption.
51. ⛔ **"The last playable row is fatal" is WRONG and was reverted.** Gate, bench and
    idx0-idx2 all held, but idx3 regressed to a verifier CONTRADICTION — the flow
    demonstrably crosses row 14, which is its last playable row. The fatal band is the row
    `playable_size()` TRIMS, and telling that band from a decorative strip is exactly what
    the edge-band probe's EVENT verdict is for. Consult it; do not assume a row.
50. **The edge-band rule is now a TOOL** — `scripts/rounds/R98/edge_band_probe.py` — and
    it finds exactly one EVENT row across the three games where the question can arise:
    sp80's failure band. ⚠️ Sequencing rule learned the hard way: `kaggle datasets
    version` RETURNS BEFORE THE VERSION EXISTS, so a kernel pushed straight after attaches
    the old data and fails minutes later as a missing file.
49. **Decoration vs event, told observationally**: not whether an edge band changes but
    how MANY distinct states it takes over a handful of actions — one state is static
    decoration, many is a counter, FEW is an event. sp80 top 14 / bottom 2, vc33 1 / 1,
    ft09 1 / 14; the band that decides the run is the only low-but-nonzero count. Needs no
    knowledge of the game, and it is exhaustive over the three games where the question
    can arise at all.
48. **vc33's hidden colour 7 is a STATUS STRIP** — a solid one-pixel band on pixel row 0,
    unchanged across actions, with the centre sample reading row 1 beneath it. Same shape
    as sp80's flash, opposite edge, but standing rather than eventful, and `_infer_scale`
    already excludes such rows on purpose. So the finding sharpens: the sampler cannot
    tell a decorative edge strip from an edge entity that carries meaning, and resolves
    both to the row beneath.
47. **The sub-cell blind spot is TWO games of twenty-five.** 22 of 25 read at scale one —
    a pixel per cell — so nothing can hide from the sampler there. Of the three with
    larger cells, sp80 misses colour 14 (the failure flash) and **vc33 misses colour 7,
    which is new and was not being looked for**; ft09 misses nothing. Narrow, but it sits
    on exactly the entity that decides a run. vc33 logged as its own measurement.
46. **BLIND SPOT CLOSED — centre sampling misses the last pixel row.** `_cellify` reads
    `grid[r*scale + scale//2]`, so cell row 15 samples pixel row 62, and the failure flash
    is 29 pixels on row 63 alone. The cell reads colour 1 for the whole spill because the
    reader never looks where the mark is. ⛔ Not patched here: `_cellify` is the entrance
    to every frame reading in the project and changing what a cell's colour MEANS needs
    its own round with its own controls.
45. **Correction to #43: NOT a scale error.** Pixel runs are four-aligned throughout, so
    scale 4 is right; the frame is a WINDOW onto sixteen of the level's twenty cells, and
    the "offset of four" is the window's position. The failure entity sits at window row
    15 and flashes on pixel row 63 ONLY — one pixel tall, averaged away by cellification.
    An entity thinner than a cell is invisible to a cell-based reading, and this is the
    one that fails the run.
43. ~~ROOT CAUSE~~ **PARTLY — idx3 is a 20x20 level shown through a 16-cell window.** Every level renders into a
    64x64 frame; levels 0-2 have `grid_size` (16,16) so scale 4 is right, and idx3 has
    (20,20) whose true scale is 3.2. `_infer_scale` returns integers, so a 20-cell board
    at 64px cannot be read at all. The "row offset of four", the invisible failure entity
    at row 19, the frame band trimmed as decoration, and the grounding's fragility on idx3
    all follow from this one fact. idx3 was never a vocabulary gap — it is a PERCEPTION
    failure.
42. **The sprite-to-board mapping is IDENTITY on idx0 and offset by FOUR ROWS on idx3.**
    Measured by reading target sprites and target cells together. So idx0's failure entity
    is board row 15, the bottom row, confirmed cell for cell by the flash — flow reaching
    the floor fails the run. idx3's level is TALLER than the frame window, its entity sits
    at or beyond the window's edge, and that is why it leaves no mark there. Anything
    outside the window is invisible by construction, including the thing that fails the run.
41. **Correction to #40**: the entity's BOARD position was inferred from sprite
    coordinates, and the cell it named never changes colour on idx3. The touched sprite is
    (1,32) — one row by thirty-two columns, wider than the render — so it is not in the
    targets' coordinate space. Measured half stands: idx3 fails on the flag with all four
    targets satisfied. Where the bar is, and why it leaves no mark on idx3, are open.
40. ~~RESOLVED~~ **PARTLY — idx3 fails on the FLAG, set by one sprite** ~~at the board's
    bottom-left cell~~, tagged the same as the 3-target levels' entity at (15,0). At the decision the
    flag reads TRUE with all four targets satisfied; every earlier False was read after
    the step, once the engine had reset. That cell lives inside `playable_size()`'s trim
    — the band the harness discards as a frame — so no plan of ours can avoid it. The
    frame probe missed it because a touched cell recolours to 14, erasing the flow colour
    the probe was hunting.
39. **At idx3's settle the advance condition is FULLY MET** — targets=4, satisfied=4,
    all_in=True, same_objects=True, flag False — and the engine resets instead of
    advancing. On clearing levels the completion follows the settle immediately in the
    SPILL phase with the set intact; on idx3 a RESET lands between them and the completion
    arrives in the arrange phase with nothing satisfied. The condition is met and the
    state is torn down before anything reads it.
38. **What the engine counts, measured at the ADD.** Painting 13 and joining the satisfied
    set are the same event. Plain walk on idx3 satisfies x=8,12,16 and NEVER x=2, the
    block — 3 of 4, which is why it fails. ~~"The spill never settles"~~ is WRONG: the
    settle flag fires twice on idx3 with droplets running to zero. In the block-targeting
    run all four ARE added, set reaches 4, flag False, spill settles — and still no
    advance. Remaining gap: WHEN the set is read relative to its reset.
37. **The silent failure is a SPENT FLASH COUNTER.** `flashstep` reaches 6 on idx3 and
    never resets; at six the failure branch restores the board without any flash. The
    earlier refutation of this was measured on idx0, where the counter DOES reset — the
    wrong control. Since the flag is False at every commit, the engine is finding NOT ALL
    TARGETS SATISFIED while the frames show all nineteen at the satisfied appearance:
    colour 13 and the engine's satisfied set are not the same fact.
36. **idx3 IS NEVER JUDGED — its spill never settles.** The engine's spill-phase decision
    fires three times in a whole run, once per cleared level; idx3 reaches none. That is
    why no failure colour appears, nothing is painted 0, the flag stays False and
    nineteen satisfied cells change nothing: the level is not refused, it is never asked.
    Suspect (hypothesis, not measured): the EMBEDDED SOURCE at (7,4) keeps emitting, so
    the flow never finishes.
35. **The engine's own list has FOUR targets and the flag is FALSE** at every idx3 commit
    — the block confirmed a target from two directions. The satisfied count reads 0 only
    because the read is after the step, when the engine has already reset. Their sprite
    x's are evenly spaced (2, 8, 12, 16) while our grounding's columns are not (2, 6, 9,
    12): possibly a different PARTITION of the same nineteen cells.
34. **The failing spill contains NO failure colours** — no 14, no 0, on any of its 38
    layers. The engine has two ways to refuse an attempt and uses neither, while also not
    accepting it: nineteen cells at 13 held for fourteen layers, nothing painted 0, no
    frame contact, a life in hand, and the board restored afterwards.
33. **Our own discovery runs the flow into the frame** on three levels of four — the
    unaimed sacrificial commit. idx1 and idx2 clear anyway, so the flag RESETS per
    attempt: frame contact costs that commit and nothing more. idx3's plan spills touch
    neither failure cause and still fail.
32. **The failure entity is the FRAME BAND** — the flash is the bottom row, colour 1 before
    the spill. Flow reaching the frame FAILS THE RUN; it does not die and does not deflect.
    `playable_size()` trims that band as decoration and `barriers()` was fixed to ignore
    it, both right about what flow does there and wrong about what it means. idx2's
    failing spill runs eight cells down the frame's right column; idx3's never touch it,
    so the frame does not explain idx3.
31. **THE BLOCK IS ONE OF THE ENGINE'S TARGETS — observed.** A failing attempt paints its
    UNSATISFIED targets in colour 0, and idx3's paints the block among them. On the spill
    where all nineteen are satisfied nothing is painted 0, so the engine agrees everything
    it wants was satisfied — and the attempt still failed. Flash budget refuted: idx0
    flashes identically on all four failures, then GAME_OVER.
30. **A failing attempt leaves NOTHING marked** — five cells differ across a whole failing
    spill: the piece re-selecting, and one flow cell clearing. The flash is transient, and
    the source flashes only while a per-level counter is under six, so idx3's later
    commits fail SILENTLY. Owed: fail a level deliberately several times and watch the
    flash stop.
29. ~~idx3 gives no verdict.~~ **It fails.** Moves after the run return one layer, so the
    board was already restored to its arrange phase — the attempt resolved as a failure.
    With all nineteen satisfied, the engine's condition means the FLAG is set, yet nothing
    flashes off-frame on idx3 while idx1/idx2 failures flash row 0. The assumption that
    must give is "the flashing entity is always visible": on idx3 it may be covered by
    flow, or sitting under a piece the way that level's source does.
28. ~~idx3 gives NO verdict.~~ With a life in hand and all nineteen cells satisfied, its
    spills show no failure flash and no next-level board, while idx1/idx2 failures flash
    row 0 plainly. The engine decides only once the flow has finished, on a later action
    than the commit, and pressing the commit again just re-runs the spill. Find the action
    that makes it render a verdict.
27. ⛔ **Do not aim before the sacrificial commit.** It recovers three lives and breaks
    idx3 outright — the piece sits under the source, the spill never shows a clean fall,
    `initial_direction` comes back UNKNOWN and the board will not assemble. The gate gets
    away with it on idx0's geometry alone.
21. **idx3 is NOT won by covering its NAMED regions** — re-measured 2026-08-25 on a game that
    is NOT over, and now with the fourth region identified: a notchless 2x2 at rows 13-14,
    cols 2-3 that the notch-based predicate cannot express. (Originally measured on a game
    already over.) All nineteen target-coloured cells go
    11 -> 13, the engine's own "done" appearance, in one spill; nine captures with
    different piece positions show nothing hidden; `levels_completed` holds at 3 and there
    is no hazard. `CoverAllSinks` in any encoding does not describe this level's win
    condition. What does is UNKNOWN, and saying so is the honest position.
13. ~~idx3 executes its plan and does not clear.~~ **A SCHEMA GAP — the PREDICATE IS GLOBAL
    and this board needs two.** `contact` exists and would satisfy the notchless region
    (14033 winning layouts), but it is CONTRADICTED for the family, so it cannot be taken.
    Original, weaker statement:** — the level's objective
    is four regions and the schema can name three; the fourth is a notchless block that
    the engine satisfies but no rule in the vocabulary can express. Recorded as a family
    finding, NOT patched mid-round.
14. ~~Owed: unit pins.~~ **ALL PAID.** Every rule adopted this round has a pin that was
    checked against its own subject by deleting that code and re-running. The three
    fixture requirements live in `_wall_and_spill()`.
15. ~~idx2 names TEN targets after ONE move action.~~ **4 now** — the blocker was dragging
    its whole wall in. Original note: Seven are scenery (sizes 14-39 vs a
    confirmed target of 5), none overlaps a piece. Harmless here because the plan does not
    depend on the count; on a level where it did, "cover every target" would be
    unreachable by construction — the failure mode idx3 spent three ticks in. The frame
    filter was measured INERT and reverted; the open discriminator is SHAPE, and narrowing
    the obstruction source needs its own measurement, not a size threshold fitted to this
    board.
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
