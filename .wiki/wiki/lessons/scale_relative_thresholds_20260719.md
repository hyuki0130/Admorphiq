---
type: lesson
symptom: "A frame-only detector uses a fixed pixel size, span, or coordinate and silently fails on a differently-scaled board / version hash"
severity: blocker
first_seen: 2026-07-19 (LP85 L5 — every fixed pixel threshold mis-fired at once on the coarse render)
---

# Fixed Pixel Thresholds Are Scale Debt

> An absolute pixel constant (`size >= 3`, `size <= 6`, `span <= 6`, a coordinate) is a
> bet that the render scale never changes. It does. The SAME game renders its sprites at
> different pixel sizes per level (internal grid shrinks with depth → the 64×64 render
> scales up), and a v2 hash can re-scale too. This is the same brittleness class as a
> fixed COLOUR constant — both hardcode a property of one specific render.

## Symptom

- A detector keyed on `region["size"] >= K` or `<= K`, or an L∞ `span <= K`, works on one
  level and returns nothing on another level of the SAME game.
- Downstream: `_detect_*` returns empty → the planner never engages → the adapter silently
  falls back to a blind sweep, scoring far below what the mechanic allows.

## Why it fails (measured, LP85)

LP85 L4's internal grid is 57×57, L5's is 27×32. The canonical 64×64 render therefore
scales L5's sprites ~4× larger: a ring tile / goal token is **4px on L4 but 16px on L5**,
and a single-pixel target corner is **1px vs 4px**. Every fixed threshold broke at once:
`_SOLID_MIN_SIZE=3` bucketed L5's size-4 corners as solids (no target frame found →
`_detect_marker_colors` empty), `size<=6` dropped the 16px ring tiles from the learner,
`_DEST_CLUSTER_SPAN=6` was marginal for the wider corner spacing. None of it was a logic
bug — the thresholds were simply calibrated to L4's scale.

## Fix — derive the constant from the frame, express thresholds relative

Read a **unit** off the frame itself and scale every threshold by it:

- LP85: `u = _scale_unit(regions)` = the modal small non-background region size (the 2×2
  tile/goal block). Then `solid_min = max(3, u//2)`, `span = max(6, 3·isqrt(u))`,
  `tile_max = max(6, 2u)`. At the shallow-level unit (u=4) these EQUAL the old constants,
  so those levels stay byte-identical; the coarse board (u=16) relaxes them proportionally.
  Result: LP85 4/8 → 5/8, and L1 (also coarse, u=16) improved as a free side effect once
  its markers became detectable.

The general recipe: **find the smallest repeated unit the board is built from (a tile, a
sprite pixel, a grid pitch), and phrase every size/distance test as a multiple of it.** A
`max(old_constant, derived)` form keeps the already-working scale byte-identical while
generalizing to new ones — the same guard pattern lets you ship the fix without a regression.

## Related

- [[hardcoded_is_anti]] — the parent anti-pattern (per-level lookup tables / magic
  coordinates); a fixed pixel size is the perception-layer version of the same bet.
- [[brittle_tells]] — how to spot a threshold that is secretly scale/hash-coupled.
- [[../games/S5I5]] — the COLOUR-constant sibling of this bug: a detector keyed on a fixed
  goal/target colour finds zero goals when the level recolours them. Same root (an absolute
  render property hardcoded), same fix shape (make perception role-based, not constant-based).
- [[../games/LP85]] — the win this lesson was extracted from (R60 L5, scale-robust detection).
- [[v2_hash_obfuscation]] — version hashes re-scale/recolour/rename; frame-derived units
  survive it where fixed constants do not.
