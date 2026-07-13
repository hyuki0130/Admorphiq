---
type: lesson
symptom: "A frame-only detector silently returns None / misreads at level entry — from a component size-floor dropping thin features, or reading during a level-transition frame-layer transient"
severity: warn
first_seen: 2026-07-14
---

# Two reusable detector traps: the component size-floor, and the settle-aware first read

> Both surfaced repeatedly on 2026-07-14 (SB26, CD82) and each has a general fix.
> A future frame-only detector that "returns None on a board it should solve"
> should check these two first before assuming the mechanic is unsupported.

## Trap 1 — the component size-floor drops thin features

A detector that filters connected components by a minimum `size` (to skip
anti-aliasing specks) will silently DROP legitimately-thin features. Measured on
**CD82 L3-L6**: the target's thin diagonal colour bands are <40px, so a `size >=
40` floor dropped them and `detect_paint_layout` returned None for the whole
target — the board looked "unsupported" when it was fully solvable. Lowering the
floor to `size >= 8` unlocked L3-L6 (1/6 → 6/6, game_score 0.0005 → 0.9463).

**Rule**: a size-floor gates NOISE, not content. Set it just above the
anti-aliasing speck size (a few px), not at the size of a "typical" region — a
target/legend can contain thin bands, single-row strips, or 1-2px connectors that
are real structure. When a detector returns None on a board you believe is
solvable, print the pre-filter component sizes FIRST.

**Audit hook (flagged by the lead)**: other detectors carry size floors that
could silently drop thin features — e.g. `sort_match._MIN_CLUSTER`, the
`ring_paint` swatch/canvas floors, `general_agent.connected_components`'
`min_size`. When extending any of them to a new/deeper board, re-check the floor
against the thinnest real feature on that board.

## Trap 2 — reading during the level-transition frame-layer transient

`obs.frame` is a frame-HISTORY stack. At a level transition it briefly stacks
MANY layers (measured: SB26 ~118, CD82 ~16) while the animation plays, collapsing
to a single layer once settled. `canonical_layer` = `frame[-1]` is the current
layer, but at the very first `choose_action` of a new level it can be a partial /
mid-animation frame — a detector run there mis-reads (canvas not yet uniform, a
region not yet drawn). Measured on CD82 L3: `detect` returned None at entry
(nlayers=16); after the frame settled to nlayers=1 it read cleanly (once Trap 1
was also fixed).

**Rule**: make a one-shot per-level detection SETTLE-AWARE — before detecting,
if `np.asarray(frame).ndim == 3 and shape[0] > 1`, emit a bounded no-op (ACTION6
at (0,0)) and retry next call until a single layer, THEN detect (and only then
set the one-shot `_attempted` flag, so the transient does not burn the attempt).
This is the same class as the delivery/transform settle-frame fixes (`a3b9c3c`)
— applied to SB26 portal-sort and CD82 ring-paint this session.

## Falsification

Either half is falsified if a detector proven to fail for one of these reasons is
re-measured and the true cause is elsewhere (e.g. a genuine mechanic gap). Record
the real cause and narrow this page rather than deleting it.

## Related

- [[../games/CD82]] — size-floor 40→8 + settle-aware read unlocked 6/6
- [[../games/SB26]] — canonical-layer (settled) read unlocked L2
- [[../rounds/r53_unified-harness]] — "cd82 paint-solver round", "SB26 L2 CLEARED"
