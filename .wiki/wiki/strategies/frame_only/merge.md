---
type: strategy
name: merge
generalizes: yes
implementation: src/admorphiq/strategies/inferential.py::_plan_merge
dispatched_from: inferential_agent.PLAN_FNS["merge"]
---

# merge (plan fn)

> Click between same-color cluster pairs to drag them together
> (vacuum mechanic). Vacuum radius `R` is calibrated from
> observation-phase click probes; only pairs within `2R` are
> attempted. Each pair tries midpoint → 1/3 → 2/3 → on-A → on-B
> click positions in priority order.

## Applies When

- `goal["kind"] == "merge"` — Phase 3 inferred merge mechanic
  (count of same-color clusters drops after a probe click).
- `entity_map["merge_items"]` non-empty.
- Click action available (`6 in avail`).

## Algorithm

1. Calibrate vacuum radius `R` from observation probes:
   `R = max(L∞ distance from click coord to bbox edge of any
   probe-diff)`. Floor at 8 px.
2. Set `max_pair_distance = 2R`.
3. For up to 40 attempts:
   a. Reset env (via `_reset_then_replay`) and re-flood-fill clusters.
   b. Group clusters by color, build all same-color pairs with
      `size < 200`. Sort by Euclidean distance.
   c. Try the closest 6 pairs. For each pair, click candidates in order:
      midpoint → (2A+B)/3 → (A+2B)/3 → on-A → on-B.
   d. If post-click `levels_completed > base_levels`, return success.
   e. If post-click frame differs from pre-click frame, mark
      `progress_this_attempt`, break to outer attempt loop with
      fresh flood-fill.
   f. If `state == GAME_OVER`, return `(base_levels, used)`.
4. Bail when no pair makes any frame progress in a full attempt.

## Why It Generalizes

- No sprite tags, no game internals — clusters come from flood-fill
  on the live frame.
- Vacuum radius is observed, not hardcoded.
- Multiple click positions per pair handle non-midpoint vacuum
  geometry (small-radius vacuums where the literal midpoint falls
  outside pull range).

## Observable Signature

- `goal["kind"] == "merge"`.
- `len(entity_map["merge_items"]) ≥ 2`.
- At least one same-color pair within `max_pair_distance`.
- Click probes show non-zero diff (so `R` calibration produces a
  meaningful radius, not just the floor).

## Falsification Signature

- Returns `(base_levels, 0)` instantly: `merge_items` empty or
  `len(merge_items) < 2`.
- Returns `(base_levels, k_small)` with `k < 50`: no same-color pair
  exists at this game state. SU15 L1 pattern — see
  [[../../lessons/su15_l1_singleton_colors_20260423]].
- Returns `(base_levels, k_large)` after 40 attempts: pairs exist
  but vacuum radius too small OR clicks aren't actually merging
  (different mechanic — probably sort-order or paint).

## Tunable Parameters

- `R` floor: 8 px. Effect: lowering helps far-pair calibration; raising
  rejects more pairs.
- `max_pair_distance`: 2R. Effect: 3R-4R surfaces longer-range pairs
  for chained drags but increases failed-click cost.
- Cluster `size < 200` filter. Effect: drop / raise to include large
  background clusters (rare).
- Closest pairs tried per attempt: 6. Effect: more = wider per-attempt
  search, faster budget burn.
- Click-position candidate order: midpoint → 1/3 → 2/3 → on-A → on-B.
  Effect: for tight vacuum radius games, try on-A/on-B first.
- Outer attempt cap: 40. Effect: more attempts = tolerate
  resetting-after-bad-merge; fewer = faster bail.

## Next-Best

When the falsification signature triggers:

- [[paint_fill]] — when `entity_map["palettes"]` non-empty (the
  "merge" classification was wrong; this is paint).
- [[toggle]] — when `entity_map["clusters"]` is dense AND no
  same-color pair (cluster centroids might still toggle a
  lights-out-style overlay).
- (No plan fn available) — for SU15-class downgrade-then-merge
  games. Escalate via [[../../lessons/su15_l1_singleton_colors_20260423]]
  next-best section.

## Limitations

- Single-mechanic only — does not handle pre-merge phases (e.g.,
  SU15's enemy-downgrade-then-merge sequence).
- Assumes vacuum mechanic — for sort-puzzle-style "swap two clusters
  to a target order" (SB26), midpoint clicks are nonsense.
- No lookahead — greedy pair selection by distance may corner the
  game if a far merge unlocks a near merge.

## Related

- [[../../concepts/merge_mechanic]] — formal definition
- [[inferential_agent]] — outer loop
- [[../../lessons/su15_l1_singleton_colors_20260423]] — failure mode
- [[../../games/SU15]] — canonical instantiation

## Sources

- `src/admorphiq/strategies/inferential.py:702-806`
- `scripts/probe_su15.py` — instrumented trace
- R7 vacuum-radius commit, R21 entity heuristic loosening
