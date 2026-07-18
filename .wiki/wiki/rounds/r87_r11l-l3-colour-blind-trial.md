---
round: R87
axis: depth / colour-blind detection + nested-colourset discriminator + speculative-target-trial
keywords: r11l, l3, colour-blind, connectivity, nested-colourset, target-discriminator, speculative-trial, multi-colour, dirwzt, depth, script25
verdict: r11l 3/6 → 4/6 @ 0.2594 (deterministic ×2); L3 cleared (172a, inefficient); floor byte-identical; L4-efficiency + L5 are reopens
commit: (this round)
---

# R87 — r11l L3 cleared: colour-blind detection + nested discriminator + trial

The L3 conquest round on top of [[r85_r11l-strike-aware-assembly]] (r11l 3/6) and
the [[r86_r11l-l3-connectivity-detection]] bank. **r11l 3/6 → 4/6 @ 0.2594,
deterministic ×2** (@600 and @3000 identical; loader `r11l/495a7899`). Floor
byte-identical (L0-L2 = 7/36/54 actions, unchanged). Four premise-checks preceded
this (ring-geometry, colour-set matching, decoy-filter, size/distance priors — all
falsified in R86); the crack came from a discriminator R86 missed.

## The three pieces (all frame-only; fallback-gated so L0-L2 are byte-identical)

1. **Colour-blind connectivity detection** (`_analyze_creatures_connectivity`,
   fires ONLY when the per-colour `_analyze_creatures_bycolor` returns None — L3's
   MULTI-COLOUR shared-colour bodies): fill bands separate pieces; high-fill body
   pieces are proximity-fused into N creature bodies (colour-blind); legs → nearest
   body. Recovers L3's 3 creatures + perfect 2+2+3 grouping.
2. **NESTED-colour-set target discriminator** (`_target_score`) — the load-bearing
   insight that retires the R86 "target assignment ambiguous" wall. A real ring's
   colours are NESTED with its body's (`target ⊆ body` or `body ⊆ target`); every
   decoy carries a foreign colour → non-nested. On L3 this UNIQUELY identifies all
   three targets (orrqlj (51,36){15} ⊆ {12,14,15}; decoys {10,12}/{9,12}/{10,14}
   non-nested), where R86's raw colour-overlap had ≥4 equally-optimal ties.
3. **Speculative-target-trial** (`_advance_trial`) — the general net for any still-
   ambiguous target: place the sure creatures, then drive the ambiguous body to
   each candidate (nested-first) until the ENGINE'S WIN fires ("the win condition
   is the missing sensor" — same pattern as su15's oracle pin / lp85 L7).
   Candidates persist across `restart_on_game_over` lives.

## Result + honest efficiency

- **4/6 @ 0.2594.** Per-level: L0 1.0 (7a) / L1 0.8403 (36a) / L2 0.8920 (54a) /
  **L3 0.023 (172a — a REAL but INEFFICIENT clear)**. 1412 tests pass; ruff +
  quarantine lint clean; durable test
  `test_connectivity_fallback_groups_legs_and_picks_nested_target`.
- The nested discriminator made orrqlj's best-guess CORRECT, so the trial rarely
  fires; the 172a cost is NOT wasted target-trials but strike-learn + replan cycles
  on the central `defgjl-Level7` obstacle (board-centre, unlike L1's off-to-side
  band), where the frame-hazard imperfection (obstacle partly rendered as
  non-hazard colours) costs a few strikes before the learned-hazard set converges.
- **Card impact is small** (0.2551 → 0.2594 game = +0.017pp on the 25-game card),
  bounded by the low L3 efficiency; the value is the **4/6 coverage milestone** +
  the reusable colour-blind-detection / nested-discriminator / trial machinery.

## Reopen

- **L3 efficiency (single-life clear)** — pad the connectivity-path body-hazard by
  1 (halves the missed-fringe strikes, measured on L1) and stop the replan-churn
  that re-places already-placed creatures; a ~54a single-life L3 (score ~0.6) would
  take r11l game_score 0.259 → ~0.37 (+~0.4pp card). The bigger lever than coverage.
- **L5** (5th level) uncracked — a further multi-creature level; next depth round.

Related: [[r85_r11l-strike-aware-assembly]] · [[r86_r11l-l3-connectivity-detection]]
· [[../games/R11L]] Notes R87.
