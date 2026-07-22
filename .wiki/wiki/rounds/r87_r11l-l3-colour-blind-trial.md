---
round: R87
axis: depth / colour-blind detection + nested-colourset discriminator + speculative-target-trial
keywords: r11l, l3, colour-blind, connectivity, nested-colourset, target-discriminator, speculative-trial, multi-colour, dirwzt, depth, script25
verdict: r11l 3/6 → 4/6 @ 0.2594 (deterministic ×2); L3 cleared (172a, inefficient); floor byte-identical; L4-efficiency + L5 are reopens
commit: (this round)
---

# R87 — r11l L3 cleared: colour-blind detection + nested discriminator + trial

> The r11l L3 conquest round: colour-blind connectivity detection + nested
> colour-set target discriminator + speculative-target trial net take r11l
> 3/6 → 4/6 @ 0.2594 (deterministic ×2), floor byte-identical.

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

- **L3 efficiency (single-life clear) — the PAD lever is MEASURED-DEAD (R88 attempt,
  ⛔ do not re-try).** Padding the connectivity-path body-hazard by 1 does NOT
  transfer from L1's off-to-side band to L3's central obstacle: padding the body
  footprint EVERYWHERE regresses L3 to 3/6 (the dilated body can't satisfy
  goal-in-box near the central obstacle — measured @600, per-level [7,36,54]); padding
  only the intermediate moves (goal at true half) thrashes (timeout, no clear). Both
  fail the "L3 must still clear" constraint; reverted to R87 (ba4b39e).
- **The persistent-leg-tracking restructure ALSO FAILED (R88 task #114, ⛔) — the
  churn's re-detection VARIABILITY was load-bearing.** Built it: `_creature_legs`
  seeded from the build grouping, updated on each verified move, `_build_move_plan`
  reads it (colour-blind path only) instead of re-detecting. L0-L2 stayed
  byte-identical (7/36/54), but **L3 REGRESSED to 3/6 with 11 strikes** (was 2).
  Root cause: with tracking the replan is fully DETERMINISTIC, so after a strike it
  regenerates the SAME striking plan on the central obstacle — the learned-hazard
  doesn't fix it because the frame hazard misses the true (non-hazard-coloured)
  obstacle cell, so the new plan just strikes a different missed cell, looping to 11
  strikes and losing the clear. The re-detection "churn" I tried to remove was
  accidentally load-bearing: its frame-to-frame variability let the planner ESCAPE
  strike loops. Reverted to R87 (ba4b39e).
- **VERDICT: 4/6 @ 0.2594 is the honest ceiling for L3 efficiency.** Both efficiency
  levers (hazard-pad, leg-tracking) fail at the SAME root: the frame hazard set does
  not match the engine's obstacle pixels (part of `defgjl-Level7` renders as
  non-hazard colours). Any deterministic single-life planner strike-loops there; the
  only thing that clears is the stochastic re-detect+learn+replan loop (172a). A real
  fix needs a FAITHFUL body-obstacle model (recover the exact obstacle mask the
  engine collides against) — a perception research problem, not a planner tweak. ⛔
  do not re-try pad or tracking.
- **L5** (5th level) uncracked — a further multi-creature level; next depth round.

Related: [[r85_r11l-strike-aware-assembly]] · [[r86_r11l-l3-connectivity-detection]]
· [[../games/R11L]] Notes R87.
