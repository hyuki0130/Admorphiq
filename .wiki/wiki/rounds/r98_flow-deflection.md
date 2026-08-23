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
