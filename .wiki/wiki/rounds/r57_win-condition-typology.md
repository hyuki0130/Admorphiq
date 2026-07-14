---
type: reasoning
round: R57
axis: win-condition-typology
verdict: MEASUREMENT-ONLY (typology named, not yet a runtime detector)
keywords: [win-condition-typology, goal-evidence, gold-trace-mining, t1-t8, elimination, uniformity, containment, pattern-match, arrival, threshold, rewrite-derivation]
commit: [0b9e5f9]
date: 2026-07-15
---

# R57 — Win-Condition Typology (goal-evidence layer)

> Offline gold-trace mining across all 25 public games names eight
> transferable win-condition TYPES as observable predicates over R56's
> kernel outputs — the answer to R53's "the one open road is richer goal
> evidence", and the input R58's `GoalLedger` (P2) turns into an
> executable detector set.

## Why this exists

[[r53_unified-harness]] concluded the agent can *measure* structure
(toggle stencils, GF(2) systems, region graphs) but has no way to know
**what kind of predicate** a game's goal even is — 11 guessed FT09 targets
all missed the real win condition for exactly this reason (see
[[../lessons/ft09_glyph_decode_20260715]] for how that specific game was
eventually cracked). R57 mines the public games at the META level — not
"what is FT09's target" but "what IS a target, structurally, across
games" — per [[r56_generic-kernels]]'s "declared-intent offloading" model.

## Method

For every game, `data/traces/<game>.npz` stores a played regression
(`frames, next_frames, actions, level_index, levels_completed_after,
rewards, is_gold`). A level-up event is any row where
`levels_completed_after` increases. For each event: single-action diff
(`frame_diff` on just the triggering action), full-block diff (from the
level's first gold action to the win — several games trigger on a
confirm/submit action whose OWN single-frame diff is near zero, so the
single-action view alone is misleading, e.g. CD82/SC25), `find_regions`
region-set comparison before/after, and the action sequence shape (single
click vs. repeated action vs. short heterogeneous sequence). `tr87` (zero
captured level-ups) and a few ambiguous cases were cross-checked against
`.wiki/wiki/games/*.md` and, for `tr87`/`tn36` only, a **read-only** grep
of the win-check source function — labelled `source-labeled`, never
imported into a frame-only detector.

## Coverage (honest)

25/25 games have SOME evidence (24 frame-verified, `tr87` source-labeled
only). 67 level-up events total, but depth is uneven: only 5 games
(`cd82` 6/6, `ft09` 6/6, `sb26` 8/8, `su15` 9/9, `tn36` 7/7) have a
**complete** captured win sequence; 3 more are partial-deep; the remaining
16 captured only L0→L1. The typology below is therefore verified mostly
at shallow depth — whether the SAME predicate type holds deeper is
unconfirmed outside the 5 complete games.

## The typology (eight types)

Each type = an observable predicate over kernel outputs + the kernel
composition that would test it. Full per-game evidence tables (grades:
frame-verified / source-labeled / low-confidence) are in
`docs/r57_win_condition_typology_20260715.md`; summarized here.

| Type | Predicate | Kernel composition | Example games (evidence grade) |
|---|---|---|---|
| **T1** Reach/Target-Coincidence | a locus (player centroid or click target) coincides with a marked goal region | `track_objects` + bbox/point overlap | AR25, M0R0, DC22, BP35, SP80, TU93, LS20, CN04, SK48, S5I5, LP85, VC33 — 12+ games, the most common type |
| **T2** Elimination/Obstacle-Consumption | a tracked object fully disappears `(colour,shape)`, no matching reappearance elsewhere | `sig_before - sig_after` on a tracked region | DC22, KA59 |
| **T3** Assignment/Matching | a "pool" region set and a "reference" region set become equal as `(colour,shape)` multisets | `multisets_equal` (built for exactly this) | SB26 (complete, most regular signature in the dataset), SU15 (complete), RE86 (partial-deep), LF52 (low-confidence) |
| **T4** Delivery/Carry-and-Place | an item is transported to a target zone, then consumed/replaced by a "delivered" marker — compositionally T1+T2 on a NON-player object | `track_objects` on a pushed/carried region | WA30, KA59 (also T2) |
| **T5** Fill/Paint-to-Pattern | a canvas is painted to match a reference pattern; the win action's OWN single-frame diff is near-zero — must use the full-block diff | `canonical_key` equality at the confirm action | CD82 (complete, decisive full-block-vs-single-action contrast), SC25 phase 1 |
| **T6** Toggle-Parity | a fixed toggleable cell set must reach a required state; GF(2)-linear (click flips a fixed neighbourhood) | `gf2_solve`/`gf2_nullspace` over a measured stencil | FT09 (complete — the cleanest, most invariant signature in the whole dataset, though 11 prior *target* guesses still failed until [[../lessons/ft09_glyph_decode_20260715|R56's glyph decode]]), SC25 phase 2 |
| **T7** Threshold/Repeated-Action-Count | a hidden scalar counter advances per repeat of one action and must cross a bound; needs a TREND across >=3 repeats, not one frame pair | `learn_point_operators`/`motion_vectors` on the repeated-action sub-sequence | SC25 phase 1, LP85 (ambiguous vs T1), R11L (**unresolved** — may actually be T8) |
| **T8** Programmatic/Rewrite-Derivation | the frame encodes a program/rule table; win = the OUTCOME of executing/deriving from it, not a spatial predicate on the current frame | `derive_rewrites`/`find_derivation` (R56, built for exactly this) | TR87 (source-labeled only, 0 frame evidence — see Circularity risk below), TN36 (frame-verified structural churn + wiki-labeled semantics) |

## Load-bearing caveats (not resolved this round)

1. **Depth**: typology verified shallow (5/25 complete games) — untested
   whether a game's predicate TYPE stays fixed across its own levels.
2. **`tr87`'s circularity risk**: its T8 label rests entirely on a source
   read, zero frame evidence. If the typology must generalize to 110
   *hidden* games where source is never available, `tr87` proves at least
   one public-game class currently has NO frame-only evidence path — the
   agent would need to solve it once, blind, before this typology could
   even describe its win condition. T3/T4/T8 in general were named with
   wiki/source assistance; it is not yet demonstrated that a game
   INSTANTIATING one of these types is frame-classifiable *before* it is
   solved.
3. **R11L is genuinely unresolved** between T7 and T8 — flagged, not
   forced to a single type.
4. **T1 may be under-differentiated**: 12+ of 25 games cite it, but the
   click-target sub-form (one correct pixel) and the movement sub-form
   (walk to a cell) share a detector *shape* but need different *search*
   strategies — the typology narrows the hypothesis space without fully
   resolving it to one kernel call.

## What this fed into

[[r58_explanation-layer]]'s P2 artifact, `GoalLedger`
(`src/admorphiq/explanation/goal_ledger.py`), turns six of these eight
types (T1/T3/T5/T2/T6/T7 → arrival/containment/pattern_match/
elimination/uniformity/threshold) into executable, kernel-only,
pre-clear-state detectors. T4 (delivery) is treated as an arrival+
elimination harness-level composition rather than its own detector; T8
(rewrite) is honestly left unsupported (zero frame evidence in this
round's own mining, per the `tr87` caveat above).

## Related

- [[r53_unified-harness]] — named the "richer goal evidence" gap this
  round closes.
- [[r56_generic-kernels]] — supplies every kernel this round's detector
  sketches compose (`find_regions`, `frame_diff`, `multiset_signature`,
  `multisets_equal`, `track_objects`, `gf2_solve`, `derive_rewrites`).
- [[../lessons/ft09_glyph_decode_20260715]] — the concrete game-level
  falsification story behind the T6/FT09 row above: knowing the TYPE
  (toggle-parity) was necessary but not sufficient; the specific target
  rule still needed gold-trace decode.
- [[r58_explanation-layer]] — consumes this typology as its P2 artifact.
- [[index]]
