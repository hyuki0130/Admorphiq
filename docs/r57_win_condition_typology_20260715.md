# R57 — Win-Condition Typology (goal-evidence layer)

> Offline analysis, 2026-07-15. Data: `data/traces/*.npz` (24/25 games have ≥1
> captured level-up transition, 67 events total; `tr87` has zero — see
> Coverage below), `environment_files/<game>/<hash>/*.py` (source, read
> **verification-only**, never imported), `.wiki/wiki/games/*.md`. Kernels
> used: `find_regions`, `frame_diff`, `multiset_signature` /
> `multisets_equal` from `src/admorphiq/kernels` (R56). Scripts (throwaway,
> not committed): `scripts/_r57_inventory.py`, `scripts/_r57_win_moments.py`,
> `scripts/_r57_deepdive.py`.

## Why this exists

R53's conclusion was "the one open road is richer goal evidence" — our
agents can *measure* structure (toggle stencils, GF(2) systems, region
graphs) but 11 guessed FT09 targets all missed the real win condition
because nothing tells the agent **what kind of predicate** a game's goal
even is. This document mines the public games at the META level: not "what
is FT09's target" but "what IS a target, structurally, across games" — a
small, transferable vocabulary of win-condition TYPES, each defined as an
observable predicate over kernel outputs, so an unseen game can be
classified into a type from early-game frames and routed to the matching
detector composition, per the R56 "declared-intent offloading" model
(`docs/r56_codex_toolbase_verdict_20260715.md`).

## Method

For every game, `data/traces/<game>.npz` (schema:
`data/traces/SCHEMA.md`) stores `(frames, next_frames, actions,
level_index, levels_completed_after, rewards, is_gold)` for a played
regression. A **level-up event** is a row `i` where
`levels_completed_after[i] > levels_completed_after[i-1]`. For each event:

1. Single-action diff: `frame_diff(frames[i], next_frames[i])` — what the
   *triggering* action changed.
2. Full-block diff: `frame_diff(frames[block_start], next_frames[i])` where
   `block_start` is the first row of the gold block for that level — what
   changed over the *whole* level attempt (several games trigger win on a
   confirm/submit action whose own single-frame diff is 0–1 px, so the
   single-action view alone is misleading; see CD82/SC25 below).
3. `find_regions` (background = per-frame mode colour) before/after, plus
   colour-histogram vanish/appear sets and `(colour, multiset_signature)`
   set difference — a translation-invariant read on whether specific
   objects were added, removed, or merged.
4. Action sequence + `rewards` for the block, to see whether the trigger is
   a single click, a repeated action, or a short heterogeneous sequence.

Games with zero captured level-ups (`tr87`) or where the frame evidence was
ambiguous (`cd82`, `sc25`, `tn36` L1) were cross-checked against
`.wiki/wiki/games/<TITLE>.md` and, for `tr87`/`tn36`, a **read-only**
grep of `environment_files/<game>/*/*.py` for the win-check function
(`bsqsshqpox()` in `tr87.py`) — labelled `source-labeled` below, never used
to write a frame-only detector directly.

## Coverage (honest)

- **25/25 games have SOME evidence** (24 frame-verified via `data/traces`,
  1 source-labeled-only: `tr87`).
- **67 level-up events total**, but depth coverage is uneven: only 5 games
  captured a **complete** win-level sequence (`cd82` 6/6, `ft09` 6/6, `sb26`
  8/8, `su15` 9/9, `tn36` 7/7). Three more are **partial-deep** (`re86` 6/8,
  `ka59` 4/7, `wa30` 2/9). The remaining **16 games captured only the first
  level-up (L0→L1)** — the trace's recorded strategy solved level 1 and
  either stopped or was never re-run deeper. This means for most games the
  typology below is verified at shallow depth only; whether the SAME
  predicate type holds at deeper levels is unconfirmed except for the 8
  games above (and even for those, `re86`/`re86`-class games show the
  predicate recurring with different bboxes/colours each level, which is
  reassuring but not proof of invariance).
- `tr87` (0 events): the regression never solved a single `tr87` level in
  this trace set, so this game's win-condition type rests entirely on a
  source read (`environment_files/tr87/*/tr87.py:1035` `bsqsshqpox()`), not
  frame evidence. Flagged explicitly in the table.
- `data/transitions/train/*.npz` (the other data source named in the task)
  was checked and is **not usable for this task** — it stores raw
  `(frames, actions, next_frames)` exploration transitions with no
  `level_index` / `levels_completed_after` / gold labelling at all (verified
  via its actual npz keys, which differ from `data/traces`' schema). All
  win-moment evidence in this document comes from `data/traces/`.

## The typology

Eight types. Each entry: definition as an observable predicate, the kernel
composition that would test it, and which games instantiate it with an
evidence grade.

### T1 — Reach / Target-Coincidence

**Predicate**: a distinguished locus (the player's region centroid, OR an
action's target coordinate) comes to coincide with a marked goal
region/cell. Two sub-forms share one detector shape: *movement* (the player
region's cells enter the goal region's bbox over several `ACTION1-4`) and
*click* (a single `ACTION6(x,y)` lands inside the goal region's cells — the
"click the one correct pixel" games).

**Detector sketch**: `track_objects` across early probes to find the
highest-mobility region (player) or, for click games, treat the rare/
distinct-colour region as the candidate target; test
`(x, y) in goal_region["cells"]` or bbox overlap between mover and goal
after each action.

**Evidence**:

| Game | Evidence | Grade |
|---|---|---|
| AR25 | player region enters new-region territory each level (region count +1/+3, sig_appear 4/6); movement-only actions (`2,2,…,3,3,3`) | frame-verified, L1-2/8 |
| M0R0 | small localized diff (25, 48 px) at fixed offsets, movement game per wiki | frame-verified, L1-2/6 |
| DC22 | movement+button hybrid; door region (colour 11) vanishes on exit — also T2 | frame-verified, L1/6 |
| BP35 | gravity platformer, diff 44 near a fixed `+`-shaped exit marker per wiki | frame-verified, L1/9 |
| SP80 | `4,4,4,5` (move×3 + confirm); marker colour 9→8/0 swap at goal | frame-verified, L1/6 |
| TU93 | small diff (19px), region count unchanged — exit-cell interaction in an otherwise static maze | frame-verified, L1/9 |
| LS20 | wiki: "player marker + ACTION1-4, BFS-solvable goal-seeking… reach a goal-marker cell" (corrected 2026-07-13 from an earlier wrong shape-match hypothesis) | frame-verified, L1/7 |
| CN04 | `zig3_A2A4` = alternating ACTION2/ACTION4 (movement zigzag, not a click); marked cell colour 8→3 on arrival | frame-verified, L1/5 |
| SK48 | snake-style; head reaches food cell, region count grows (+2, tail growth is a side-effect of T1) | frame-verified, L1/8 |
| S5I5 (axis variant) | wiki: "clicking a slider moves its goal marker… goal markers reach target positions" — 1D-projected coincidence, use `project_to_axis`/`point_toward` instead of 2D bbox | frame-verified, L1/8 |
| LP85, VC33 | wiki explicit: "click at a specific coordinate clears the level" (`click_c8_(30,4)`, `click_c9_(33,60)`); LP85's 69-click block is the *search* for that pixel, not 69 independent triggers — also touches T7 | frame-verified, L1/8 and L1/7 |
| CD82 | secondary: the final confirm click (`ACTION5`) must land on/near a specific slot — primary type is T5 | frame-verified, L0-5/6 |

### T2 — Elimination / Obstacle-Consumption

**Predicate**: a specific object (obstacle, box, barrier) that blocked
progress is entirely removed from the frame (region present before, absent
after — a full `(colour, shape)` disappearance, not a repaint).

**Detector sketch**: `(sig_before − sig_after)` non-empty for a specific
tracked region, with no matching `sig_appear` of the same colour elsewhere
(rules out "it moved" vs "it was consumed").

**Evidence**:

| Game | Evidence | Grade |
|---|---|---|
| DC22 | colour 11 fully vanishes (`vanished_colors=[11]`, region count −1) coincident with the exit action | frame-verified, L1/6 |
| KA59 | region count −1/-1 at two of four captured levels, sokoban-cooperative per wiki (box pushed onto goal cell, consumed) — overlaps T4 | frame-verified, L1-4/7 |

### T3 — Assignment / Matching (multiset equality)

**Predicate**: two designated region sets — a "pool" and a "reference/
target" — must become equal as multisets of `(colour, shape)`. This is
*exactly* what `multisets_equal` (kernels/regions.py) was built to test —
its docstring literally cites `sort_match`'s "does the pool supply the
reference set" comparison, which is `SB26`'s mechanic.

**Detector sketch**: `multisets_equal(regions_pool, regions_reference)` —
already implemented, generic, no game constants.

**Evidence**:

| Game | Evidence | Grade |
|---|---|---|
| SB26 | **Constant Δ−2 / diff-41 pattern every single one of 8 captured levels** — the most regular signature in the whole dataset. Wiki (confirmed 2026-07-13): "portal-graph traversal… level clears when a DFS traversal… visits plain-item slots" whose accumulated multiset matches the reference frame | frame-verified, L0-7/8 complete |
| SU15 | region count net-negative across levels (sig_vanish > sig_appear most levels), wiki: "same-colour fruits merge on overlap to colour+1 (like 2048)… goal zones… N fruits of colour C" — merge-to-target-multiset | frame-verified, L0-8/9 complete |
| RE86 | moderate, recurring sig_vanish/appear (6-12) every level, wiki: "multiple sprites must be moved to target positions… correct assignment depends on sprite and target colours" — bipartite colour-assignment, a T3 variant scored by position not pure multiset | frame-verified, L0-5/8 partial-deep |
| LF52 | region count collapses sharply over an 11-click block (58→44) — pattern consistent with pairwise elimination/matching, but wiki itself says mechanic is "Unknown post-regression" | **low confidence**, frame-partial, L0/10 |

### T4 — Delivery / Carry-and-Place

**Predicate**: an item region is transported (pushed/carried) from a source
to a marked target zone; the item is consumed or replaced by a "delivered"
marker on arrival. Compositionally T1 (reach, but for a non-player object)
+ T2 (the item disappears) — kept as its own entry because the detector
must track a *pushed* object's trajectory, not the agent's own.

**Detector sketch**: `track_objects` on a non-player region across a push/
carry sequence; win when its trajectory terminates inside a distinct
"target zone" region AND the item's `(colour, shape)` signature vanishes
(or a new "filled" marker appears at that zone).

**Evidence**:

| Game | Evidence | Grade |
|---|---|---|
| WA30 | wiki: "pick up items and deliver to target zones… worker navigates pickups and drop-off zones"; frame: colour 2 vanishes at L0→1 (pickup/delivery), colour 3 vanishes + 2/12 appear at L1→2 | frame-verified, L0-1/9 |
| KA59 | wiki: "cooperative Sokoban: two agents push blocks… goal zones accept pushed blocks" | frame-verified, L0-3/7 partial-deep |

### T5 — Fill / Paint-to-Pattern

**Predicate**: a canvas region must be painted, cell by cell, to match a
target reference pattern; the win-triggering action is often a
confirm/submit click whose *own* single-frame diff is near zero (0-1 px) —
the real work happened over the preceding block.

**Detector sketch**: this is the one type where the *single-action* diff is
actively misleading; must use the full-block diff. Predicate test:
`canonical_key(canvas_region, mode="exact") == canonical_key(reference_region, mode="exact")` at the confirm action.

**Evidence**:

| Game | Evidence | Grade |
|---|---|---|
| CD82 | **Decisive full-block-vs-single-action contrast.** Single-action diff at the win row is 0-1 px for 4 of 6 levels; full-block diff (from the level's first gold action to the win) is 232-589 px with region count growing (13→17→31→30→32→36). Action pattern `[colour-pick, colour-pick, …, 6, 5]` repeats; final `5` (or `6`) is the confirm with reward=1.0. Matches wiki "`paint_game`" + R56 doc's "fixed CD82 canvas geometry and win masking" note (source-informed extent, frame-verified pattern) | frame-verified, L0-5/6 complete |
| SC25 (phase 1) | 30-action block of `3×22, 6×4, 3×4` before reward=1.0 on the 30th action; full-block diff 128px, region +1. Wiki: "cast the correct spell pattern on a 3×3 grid, then… exit" — phase 1 (build the pattern) is closer to T5/T7 hybrid, phase 2 ("navigate to exit") is T1 | frame-verified, L0-1/6 |

### T6 — Toggle-Parity (fixed-cell pattern match)

**Predicate**: a fixed set of cells, each independently toggleable, must
each reach a required state (colour) simultaneously; a GF(2)-linear
structure (clicking toggles the clicked cell plus a fixed neighbourhood).
This is the one type that already has a dedicated kernel
(`kernels/gf2.py`, built in R16-R18 specifically for this class).

**Detector sketch**: `gf2_solve`/`gf2_nullspace` over a toggle-stencil
matrix inferred from probe clicks; predicate = current state vector equals
the (separately-inferred) target vector.

**Evidence**:

| Game | Evidence | Grade |
|---|---|---|
| FT09 | **Constant 36-cell diff (a 6×6 block) at every one of 6 captured levels**, region count unchanged, exactly one `(colour, shape)` pair swaps — a single stencil flip each time. Wiki: "classic lights-out variant over GF(p)". This is the *cleanest, most invariant signature in the whole dataset* — the predicate type is unambiguous even though 11 prior attempts to find the specific target readout failed | frame-verified, L0-5/6 complete |
| SC25 (phase 2, sibling) | "click exact 3×3 spell slots" — an exact spatial pattern match without GF(2)/toggle semantics (no XOR neighbourhood, direct set-equality instead) | source/wiki-labeled |

### T7 — Threshold / Repeated-Action-Count

**Predicate**: a scalar (hidden) counter advances by a fixed amount per
repetition of one action and must cross a threshold; frames show
monotonic, small, cumulative visual change rather than a qualitative
structural jump, and the action log is a long run of one repeated action
id.

**Detector sketch**: NOT recoverable from a single before/after frame pair
— requires observing the *trend* across ≥3 repeats of the same action at
the same locus (`learn_point_operators`/`motion_vectors` on the repeated-
action sub-sequence) to estimate whether a measured quantity (region size,
colour intensity, a small counter-shaped region) is moving toward a bound.

**Evidence**:

| Game | Evidence | Grade |
|---|---|---|
| SC25 (phase 1) | 22 consecutive `ACTION3` before other actions kick in — see T5, likely a T5/T7 hybrid (repeat builds the pattern, not a pure counter) | frame-verified, L0/6 |
| LP85 | 69 consecutive `ACTION6` clicks (same/near position) before reward — "click_rare" strategy name suggests a *search* for a rare pixel, not a counter; ambiguous between T7 (grinding toward a threshold) and T1 (search-then-click) | **ambiguous**, frame-verified pattern, L0/8 |
| R11L | 11 consecutive `ACTION6`; wiki: "short action sequences trigger progression… `seq_repeat`/`seq_search`… a short PERIOD that repeats on success" — this reads more like "discover the right short SEQUENCE" than "count repeats to a threshold", i.e. it may actually belong in T8, not T7 | **low confidence, unresolved** — flagged as a load-bearing uncertainty below |

### T8 — Programmatic / Rewrite-Derivation

**Predicate**: the frame encodes a small program, rule table, or symbol
sequence; the win check is not a spatial predicate on the *current* frame
but on the *outcome of executing/deriving* from the encoded state — e.g. a
rewrite chain reaching a terminal form, or an encoded bit-program's
simulated trajectory reaching a target. This is qualitatively different
from T1-T7: the right kernel is `derive_rewrites`/`find_derivation`
(kernels/rewrite.py, built in R56 specifically for `tr87`-class games), not
a region/diff predicate.

**Detector sketch**: extract tokens/rules from the frame (symbol regions +
their relative layout), call
`derive_rewrites(source_tokens, rules, max_depth)`, and test whether any
derived result matches the required terminal token sequence.

**Evidence**:

| Game | Evidence | Grade |
|---|---|---|
| TR87 | **Zero frame-verified win moments** (0/6 levels ever captured in `data/traces/tr87.npz`). Source read (`environment_files/tr87/*/tr87.py`, function `bsqsshqpox()` at line 1035): cycles through symbol "sets" via ACTION1-4 (select slot) / ACTION3-4 (edit value); win check looks up a `cifzvbcuwqe` rule table for the current symbol config and tests whether it matches a stored derivation chain (`rule[0]`); on match, plays an animation (`self.yfetxjexviz = 0`) then calls `next_level()`. Confirms the "rewrite/rule-match" hypothesis directly from source — this game's typology label rests **entirely** on the source read, not frames | **source-labeled only, 0 frame evidence** |
| TN36 | Wiki: "bit cells… toggle on/off when clicked… Play button… executes the encoded program as a series of movement steps… player sprite navigates on execution; kill zones end level". Frame evidence is consistent (huge, level-varying region churn — 88, 2591, 594, 432, 674, 742, 409 px — on each single `ACTION6` "run" click, since running the program re-simulates a whole trajectory in one step) but does not by itself distinguish "program executed correctly" from "program executed, then something else happened"; the *program* semantics come from the wiki/source description | frame-verified (structural churn) + wiki-labeled semantics, L0-6/7 complete |

### Unclassified / low-confidence

- **G50T** — wiki itself says the mechanic is unresolved ("Hybrid… discovering which objects respond to ACTION5 or specific coordinates"); only one captured event (region +1, sig_appear 2). Tentatively T1-adjacent but not asserted.

## Coverage/limitations summary

1. **Depth**: only 5/25 games have a complete captured win sequence; 16/25
   have only the L0→L1 transition. The typology is a *shallow-depth* survey
   — whether FT09-class games stay T6 at L2+ (the wiki already flags this as
   an open question: "L2+ buttons are elsewhere… additional constraint-
   indicator detection… is needed") or whether other games' predicate TYPE
   changes with depth is unverified for most of the set.
2. **`tr87` has zero frame evidence.** Its T8 label is a pure source read.
   If the typology is meant to generalize to 110 *hidden* games where source
   is never available, `tr87` is a reminder that at least one public-game
   class currently has **no frame-only evidence path at all** — the agent
   would have needed to solve it once, blind, before this document could
   even describe its win condition. That is the typology's central
   circularity risk: types T3/T4/T8 in particular were named with wiki/
   source assistance, and it is not yet demonstrated that a game
   INSTANTIATING one of these types is frame-classifiable *before* it is
   solved.
3. **R11L is genuinely unresolved** between T7 (repeat-to-threshold) and T8
   (discover-a-short-sequence) — the wiki's own language ("discovering the
   sequence") leans T8, but the frame evidence (monotonic-ish region
   shrinkage under one repeated action id) leans T7. This is exactly the
   kind of ambiguity a hidden game could also produce, so the two types'
   detectors should probably both be attempted rather than the classifier
   forced to pick one upfront.
4. **T1 is doing a lot of work** (12+ of 25 games cite it as primary or
   secondary) — it may be under-differentiated. The click-target sub-form
   (LP85/VC33/CN04's "one correct pixel") and the movement sub-form
   (AR25/M0R0/LS20/TU93's "walk to a cell") share a detector *shape*
   (locus-vs-goal coincidence) but arguably need different *search*
   strategies (a BFS/path-plan vs. a rare-colour scan), so a runtime router
   would still need a movement-vs-click discriminator even after committing
   to "this is a T1 game" — the typology narrows the hypothesis space but
   does not fully resolve it to a single kernel call.
