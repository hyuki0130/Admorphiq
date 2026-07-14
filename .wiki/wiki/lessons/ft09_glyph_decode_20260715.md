---
type: lesson
date: 2026-07-15
rounds: R56
status: live-cleared 4/6 (47.62% RHAE); level 5 (0-indexed 4) mystery with
  Codex; level 6 fully decoded, unreached live
---

# FT09 is a multi-glyph constraint-satisfaction puzzle, not a coupled GF(2) neighbourhood stencil (R56)

> Gold-trace reverse-engineering falsifies the R16-R18 "clicking couples
> neighbour cells" model: a click only ever changes the clicked cell. The
> real win condition is drawn on the board as one or more 3x3 compass
> glyphs, read via full multi-glyph coverage enumeration (a coverage-
> scoping near-miss taught that "nearest glyph" is the wrong scope). The
> R56 `src/admorphiq/adapters25/ft09.py` adapter decodes it directly and
> live-clears 4/6 levels; two levels remain open for different, documented
> reasons.

## Symptom

`_plan_lights_out` (the R16-R18 GF(2) path, see
[[gf2_lights_out_stencil_20260423]]) clears FT09 L1 but stalls on L2+:
the diff-sorted top-10 cells measure as 91-100% stencil density, which
that lesson page reads as "coupled display feedback, not real toggle
buttons" — eleven different guessed target hypotheses (majority colour,
minority colour, per-cell flip, ...) all missed the actual win condition.
R53's own conclusion ("the one open road is richer goal evidence") named
exactly this failure mode: the agent could measure structure but had no
way to know WHAT KIND of predicate the goal actually was.

## Root Cause

The R16-R18 model assumed FT09 is a coupled linear system: click cell `j`,
some SET of cells (possibly including `j`) flips, and the empirical
stencil `A[i][j]` needs to be measured and solved over GF(2). Gold-trace
decode (byte-for-byte replay against captured levels) falsifies this: a
click only ever changes the CLICKED cell on the levels this rule covers —
there is no coupling to measure, so every one of the eleven target
hypotheses was searching the wrong problem class from the start regardless
of how good the target guess was.

**The actual mechanic** (verified byte-for-byte on 4 of 6 public levels;
live-cleared on those same 4, 47.62% RHAE): the board is one or more
8-cell "rings" (a 3x3 button layout minus its own center) wrapped around a
small "glyph" that occupies the ring's center gap. The glyph is itself a
3x3 compass-position pattern (NW/N/NE/W/center/E/SW/S/SE). For every board
cell, collect a constraint from EVERY glyph whose 8-neighbour reach
includes it — see "The coverage-scoping near-miss" below for why this
must be EVERY glyph, not the nearest one. Ink colour **0** at a compass
position means that cell's colour must EQUAL the covering glyph's own
marker colour; ink colour **2** means it must DIFFER from the marker; ink
colour **3** means no constraint (a truncated ring's missing compass slot,
or plain background at a lattice point — see "Truncated rings" below). ALL
of a cell's covering constraints must hold simultaneously. A cell needing
more than one click walks the board's own MEASURED colour cycle one step
per click (2-value on most boards; a 3-value cycle `[9,8,12]` measured on
one level).

A second falsified assumption: some levels' board at level-start is a
"decoy" where every discoverable ring already matches its own glyph
(nothing for the decode rule to click) until ONE click anywhere
wholesale-replaces the visible region layout with a different,
previously-invisible ring set — the level's real puzzle. The reveal click
doubles as that new board's first real toggle.

## The coverage-scoping near-miss (a real falsification-replay failure, root-caused)

A Codex-derived formula for one level's 3-colour cycle (documented in
`docs/r58_codex_ft09_l3_formula_20260715.md`) claimed one gold click was
REDUNDANT — a specific cell's constraint set (as originally tabulated) was
`{≠12, ≠12}` from two nearby glyphs, and both candidate colours (9 and 8)
satisfied it, so gold's click there was allegedly an arbitrary, non-unique
choice. **The decisive test**: a LIVE deterministic offline replay of
gold's exact sequence, OMITTING only that one click, was run against the
real environment. **It failed to clear the level.** This directly
contradicted the redundant-click claim.

Root cause, found by reading the (obfuscated) environment source's own
completion check (`environment_files/ft09/*/ft09.py`, function `cgj()`) —
**read only AFTER deriving the candidate rule from data, verification
only, the same discipline Codex used for the original formula**: the
"redundant" cell was actually covered by a THIRD glyph the original
2-glyph tabulation had missed entirely. Its true constraint set was
`{≠12, ≠12, ≠9}` — uniquely satisfied ONLY by colour 8 in that board's
`[9,8,12]` alphabet. Re-deriving the FULL constraint table with exhaustive
per-glyph coverage checking (every discovered glyph's full 8-neighbour
reach against every cell, not "the nearest glyph or two") gave 18/18 cells
matching gold's win state exactly, with the previously-"redundant" cell
now uniquely determined.

**Lesson, stated generally**: cells near where two or three rings' 8-
neighbour reaches overlap are, measurably, covered by MORE than one glyph
simultaneously — this is not a rare edge case, it happened on the very
first multi-glyph board investigated closely enough to check. Any
coverage-collection code for this class of puzzle must enumerate every
discovered glyph's full reach against every candidate cell; scoping to
"nearby" or "the closest N" glyphs will silently drop real constraints and
produce wrong (non-unique-looking) predictions that are actually unique.
This is the single most load-bearing correction in the whole decode arc —
a genuinely wrong auxiliary claim, caught by a decisive negative replay,
root-caused to a scoping bug rather than a modelling error, which is the
STRONGEST possible outcome for a falsification test (see
[[../rounds/r58_explanation-layer]]'s framing of decisive tests).

## Truncated rings (measured, level 6)

A ring can have FEWER than 8 real button members: measured directly on
one board, two separate rings near the top and bottom frame edges had
exactly 4 real members each (the rest cut off by the frame boundary), with
their missing compass positions' own ink value reading **3** (the "no
constraint" value) rather than 0 or 2. Discovery accepts a candidate glyph
gap once it reads as legible (non-background center) AND has at least a
measured floor of real neighbours (4 — the exact minimum observed on both
real truncated rings; lower thresholds admit spurious 1-2-member
candidates from geometric noise on any board with more than one ring,
confirmed by a synthetic test that found 33 phantom "rings" before this
floor was added).

## Cell coupling (measured, level 6)

On the same board, a single click sometimes advances a SECOND cell too —
not a coupled stencil in the R16-R18 sense, but a fixed, MEASURED
geometric offset from the clicked cell (8 rows outward from the ring's own
center, same column, discovered empirically per board rather than
hardcoded). What looks like a "swap" between two cells (one goes A->B, the
other B->A in the same click) is actually just BOTH cells independently
stepping the SAME colour cycle from whatever phase they each individually
started in — same-phase pairs look like "both flip the same way",
opposite-phase pairs look like a swap. Verified against ALL 13 real gold
clicks on this level with an exact predicted-vs-actual check on both the
clicked cell and its offset partner, zero exceptions, including every case
where the partner position is background (correctly predicts "nothing
happens there").

## A third glyph type — "commit" glyphs (level 5, UNRESOLVED)

On a different level's revealed board, 3 of 9 candidate glyph positions
were initially read as harmless false-positive discovery noise — their
ink values (6 and 14) don't match the confirmed 0/2/3 vocabulary, so the
confirmed rule assigns them zero constraints (correctly harmless under
that rule, but this was a premature dismissal). All 3 share an IDENTICAL
pattern: corners = ink 14 ("don't care"), all 4 edges (N/W/E/S) = ink
**6**, a value never seen on any other level. Clicking DIRECTLY on one of
these glyphs' own gap position (not a field cell — the glyph's own center)
produces a real, structured effect: it normalizes that glyph's 4 edge
members toward "at most one marked", reverting extras to the base colour
and, in one measured case, also advancing the sole unmarked edge.

**Two decisive negative replays prove this is structurally necessary, not
optional error-correction**: (1) clicking exactly the confirmed rule's
9 predicted target cells (from the 6 "normal" glyphs on this board) does
NOT clear the level; (2) clicking all 27 field cells once each also does
NOT clear the level. Gold's actual winning sequence needs 3 additional
clicks directly on the commit-glyph gap positions, after all 17 target-
cell clicks. The exact win invariant these commit glyphs enforce is
UNRESOLVED — full per-click evidence table and 5 concrete open questions
are in `scripts/_r58_ft09_l4_mystery_brief.md`, with Codex as of this
writing (parallel structure to the L3 formula brief that produced the
coverage-scoping fix above).

## The trigger-click infinite-loop bug (found live, fixed, unrelated to whether level 5 is ever solved)

Live-testing on level 5 (not gold replay — driving the actual adapter
against the real environment) surfaced a genuine, separate defect: the
adapter's "nothing unsatisfied, try a trigger click" fallback judged
success by "did anything visibly change" (`frame_diff(...)["count"] > 0`).
On THIS board, an ordinary field-cell click is ALWAYS visibly effective
(it toggles 14<->15 regardless of correctness) — so the trigger's own
attempt counter kept resetting to zero on every single click, and the
adapter clicked the SAME cell forever (60+ identical actions observed
live, zero contradictions ever detected, before the fix).

**Fix**: trigger success is now judged by `_is_wholesale_change` — a
Jaccard-overlap comparison of the SET of candidate region bboxes (position
only, colour-blind) before vs after the click. An ordinary recolour keeps
the exact same bbox set (overlap 1.0, not a reveal); a genuine decoy ->
reveal transition replaces the layout almost entirely (overlap near 0, a
reveal). Trigger attempts are also now bounded to DISTINCT cells (a budget
of 5, never retrying the same cell), and a separate per-level total-action
budget (150) bounds the fallback machinery too, so no board — solved or
not — can grind indefinitely; this matters for wall-clock risk on
Kaggle's 9h ceiling across ~110 games. **Live-verified**: identical 4/6
score / 47.62% before and after the fix (the bug never changed the SCORE,
only the wasted action count), but total actions on the same 500-action
smoke dropped from 500 (fully exhausted) to 195 — 45 real clicks across
levels 1-4 plus exactly the new 150-action bounded bail once level 5
proved unsolvable under the current rule. A regression test
(`test_glyph_trigger_loop_abandons_glyph_phase_within_budget_when_no_reveal_ever_happens`)
directly reproduces the bug scenario on a synthetic board and pins that
the adapter exits glyph phase within budget rather than hanging.

## Prevention

The adapter (`src/admorphiq/adapters25/ft09.py`) treats "discovery found
zero unsatisfied cells" as a signal to make a probing trigger click, not a
giveup, and — critically — RE-RUNS ring discovery AND rebuilds the full
per-cell constraint set from the live frame on every single
`choose_action` call rather than trusting a cached board reading. That
single design choice is what makes the decoy->reveal transition fall out
for free: there is no stale candidate list to invalidate, because nothing
is ever cached across calls in the first place. Ring/pitch/glyph geometry
is discovered purely from frame observation (modal button size, MODE — not
min — of measured button-gap distances, `tile_bbox` 3x3 split of the
discovered glyph bbox), so no fixed pixel offset is hardcoded anywhere the
way the old sprite-tag solver was.

## Recovery

A per-cell click cap (`_GLYPH_PER_CELL_CLICK_CAP = 5`), a seen-colour loop
detector (a cell revisiting an already-seen, still-unsatisfying colour has
exhausted its measured cycle without a solution), a bounded distinct-cell
trigger budget (`_GLYPH_TRIGGER_BUDGET = 5`), and a bounded per-level
action budget (`_LEVEL_ACTION_BUDGET = 150`) together fall back to the
pre-existing measured-GF(2)-stencil probe/execute/fallback machinery
unchanged, if the glyph decode turns out not to apply to some board this
adapter hasn't seen (level 5, currently). The R16-R18 stencil path is not
deleted — it remains FT09's second-line strategy, exactly the "no plan
fits, propose a fix" self-healing shape the architecture doc calls for,
except decided at dev-time by gold-trace + live evidence instead of a
runtime LLM proposal.

## Falsification

This reading is falsified if: (a) a real board is found where a click
changes a cell OTHER than the clicked one AND the offset/relationship
can't be explained by the measured coupling model above (breaks "clicks
only affect their own cell, or a single measured coupled partner"); (b) a
glyph ink value is observed that is neither 0/2/3 (the confirmed
vocabulary) NOR the level-5 commit glyphs' 6/14 pattern (would mean a
FOURTH glyph type exists); (c) a ring is found with fewer than 4 real
compass members (would mean the measured truncation floor is wrong); or
(d) a decoy board is found where the reveal trigger is not simply "any
click, judged by wholesale layout replacement" (would need a more
specific trigger-detection rule).

Conditions (a)-through-(c) as ORIGINALLY WORDED in this lesson's first
draft have already each been triggered once and resolved by extending the
model (coupling, the commit-glyph type, truncated rings) rather than by
abandoning the core rule — that is itself evidence the constraint-
satisfaction framing is the right level of abstraction, even though its
FULL vocabulary (ink values, glyph types) is still being discovered
level-by-level.

## Open items

- **Level 5's commit-glyph win invariant** — unresolved, Codex pass in
  flight on `scripts/_r58_ft09_l4_mystery_brief.md`.
- **Level 6 has never been exercised live** — its mechanic is fully
  decoded and offline-verified (22/22 covered cells match gold's win
  state; the coupling model matches all 13 real gold clicks exactly), but
  it sits sequentially behind level 5, which is unsolved, so it has never
  actually been reached in a live run. Once level 5 clears, re-smoke to
  confirm level 6 also clears as predicted — this is the one remaining
  "gold-trace verified, live smoke not yet run" gap left in this arc.

## Related

- [[gf2_lights_out_stencil_20260423]] — the R16-R18 stencil model this
  lesson falsifies; kept as FT09's fallback strategy, not deleted.
- [[../concepts/gf2_toggle_stencil]] — the coupled-toggle concept the
  glyph-decode reading no longer applies to for FT09 specifically (the
  concept page still applies to any game that genuinely IS a coupled
  toggle system).
- [[../games/FT09]] — the game's own entity page, updated alongside this
  lesson with the full falsification-journey narrative and live 4/6 table.
- [[../rounds/r56_generic-kernels]] — the round this decode work landed
  under (kernel composition: `find_regions`, `tile_bbox`), and where the
  live measurement + trigger-loop fix are recorded.
- [[../rounds/r57_win-condition-typology]] — the gold-trace win-moment
  mining method this decode reused (per-level-up frame diffing against
  `data/traces/*.npz`).
