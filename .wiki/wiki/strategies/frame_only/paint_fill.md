---
type: strategy
name: paint_fill
generalizes: yes
implementation: src/admorphiq/strategies/inferential.py::_plan_paint_fill
dispatched_from: inferential_agent.PLAN_FNS["paint_fill"]
---

# paint_fill (plan fn)

> Paint sequence: click a palette swatch to select a color, click
> each target cell that isn't already that color, optionally click
> an executor to commit. Tries up to 3 palettes × 12 cells × 2
> executors before bailing.

## Applies When

- `goal["kind"] == "paint_fill"` — Phase 3 inferred a uniform-fill
  goal (target color emerges from probe-effect transition).
- `entity_map["palettes"]` non-empty.
- `goal["target_color"]` set (or fallback to top-left frame color).

## Algorithm

1. Reset env, snapshot frame `f`.
2. Flood-fill `f`, collect clusters where `color != target_color` and
   `size < 100` as `cells_to_fill`.
3. For each palette in `palettes[:3]`:
   a. Reset.
   b. Click palette location.
   c. For each (cx, cy) in `cells_to_fill[:12]`:
      - Click (cx, cy).
      - If `levels_completed > base_levels`, return success.
   d. For each executor in `executors[:2]`:
      - Click executor location.
      - If `levels_completed > base_levels`, return success.
4. Bail.

## Why It Generalizes

- Palettes / executors / target_color all come from frame analysis +
  probe transitions, not sprite tags.
- Cluster filter (`size < 100`) avoids painting large background
  regions (which are usually goal canvases, not targets).
- Three-palette / twelve-cell / two-executor caps keep budget bounded.

## Observable Signature

- `goal["kind"] == "paint_fill"`.
- `len(entity_map["palettes"]) ≥ 1`.
- `goal["target_color"]` is a discrete int (probe identified the goal
  color from a transition observation).
- Click responsiveness ≥ 3 cells with diff ≥ 10 (lots of clickable
  cells, consistent with paint).
- Probe direction asymmetry ratio ≥ 5 — direction inputs do level-wide
  paint, not fine movement (see [[../../concepts/probe_signature]] rule 3b).

## Falsification Signature

- Returns `(base_levels, k_small)` with `k < 50`: no palettes or no
  cells_to_fill — classification was wrong (target_color picked the
  background color, so every cluster is already "filled").
- Returns `(base_levels, k_full)` after exhausting all 3 × 12 × 2
  combinations: palette-click → cell-click sequence isn't the right
  composition (game might need explicit executor click between, or
  palette persists across resets).
- The CD82 multi-level pattern: L1 cleared via [[navigation]] but L2+
  enters paint phase that isn't reachable here — see
  [[../../lessons/cd82_paint_palette_signature_20260423]] for the
  swatch-grid + target-pattern + launcher detection that's missing.

## Tunable Parameters

- Palette cap: 3. Effect: more covers ambiguous palette tagging at
  budget cost.
- Cell cap: 12. Effect: more handles dense canvases; cell-cluster
  filter (`size < 100`) prevents painting backgrounds.
- Executor cap: 2. Effect: more executors handles multi-button paint
  games.
- `target_color` fallback: `int(f[0, 0])`. Effect: usually wrong; tune
  by improving Phase 3 goal detection.
- Cluster `size < 100` filter. Effect: lower bound = include smaller
  decoration cells; upper bound = paint backgrounds (don't).

## Next-Best

When the falsification signature triggers:

- [[toggle]] — palette tagging was wrong; cells respond to clicks but
  there's no select-and-paint phase. Toggle's broader candidate pool
  (every flood-filled centroid) covers this.
- [[click_then_move]] — when CD82-style L2+ paint phase has a clear
  button signature. The two-cell shared-centroid pattern from
  [[../../lessons/cd82_paint_palette_signature_20260423]] routes
  better via click_then_move.
- (No plan fn available) for full paint-pattern games — the missing
  swatch-grid detector is queued for a future sprint.

## Limitations

- Greedy: doesn't search palette × cell × executor permutations beyond
  the cap × cap × cap baseline.
- No target-pattern read — assumes uniform fill, not arbitrary pattern.
- Executor is optional and rarely tagged correctly without R12 HUD masking.

## Related

- [[../../concepts/probe_signature]] — rule 3b paint signature
- [[inferential_agent]] — outer loop
- [[../../lessons/cd82_paint_palette_signature_20260423]] — observation note
- [[../../games/CD82]] — canonical instantiation

## Sources

- `src/admorphiq/strategies/inferential.py:809-855`
- `scripts/probe_cd82.py` — instrumented trace
