# R56 kernel catalog

Reference for anyone writing a `script25` quarantine adapter, and future input
to the declared-intent offloading interface (task #42). See
[`docs/r56_codex_toolbase_verdict_20260715.md`](r56_codex_toolbase_verdict_20260715.md)
for the full decision this library implements.

## What a kernel is

A kernel is a **pure computation**: it takes explicit data (masks, grids,
score matrices, caller-supplied callables) and returns a result, with no
access to the game environment, no game titles or ids, no inferred goals, and
no autonomous decision-making. Every kernel in `src/admorphiq/kernels/` was
extracted from a game-specific solver's reusable MATH, with that solver's
role assignments, mechanic hypotheses, and policy stripped out — see each
module's docstring for exactly which source file it was extracted from and
what was deliberately left behind.

**Hard rule: kernels never gain game semantics.** A kernel must never read a
`game_title`, branch on a specific game id, or hardcode a role like "the
largest region is the goal" — those decisions belong to the caller (an
adapter script today, the LLM itself under the declared-intent interface
later). If a kernel needs a piece of semantic information (which cells are
background, which colour is the target, what "same state" means), that
information arrives as an explicit function argument, never as an inferred
default tied to one game's layout.

All modules are stdlib-only (no numpy) because they must run inside the
sandboxed REPL the LLM composes code in at runtime. Every micro-example below
was executed via `uv run python -c ...` against the actual code in this
repo — none are written from memory.

## Module reference

### `rewrite.py` — intent group: `rewrite_derivations`

Token-rewriting search: given a source token sequence and a set of `(LHS,
RHS)` production rules, derive reachable strings (and optionally find a
specific target) within a depth bound. Extracted for the TR87-class "is this
bar a valid derivation of that bar" win-rule family — the kernel knows
nothing about bars, dials, or levels.

| Function | Contract |
|---|---|
| `derive_rewrites(source_tokens, rules, max_depth, strategy="parallel", max_states=10_000) -> list[dict]` | BFS-derive every distinct token string reachable from `source_tokens` in 1..`max_depth` steps; each result is `{"result": tokens, "proof": [step, ...]}`. `strategy` is `"all_matches"` (branch every match position), `"leftmost"` (first match only), or `"parallel"` (all non-overlapping matches at once, L-system style). |
| `find_derivation(source_tokens, target_tokens, rules, max_depth, strategy="parallel", max_states=10_000) -> list[dict] \| None` | Same search, early-exiting on first hit; returns the proof steps to `target_tokens`, `[]` if source already equals target, or `None` if unreachable within `max_depth`. |

```python
>>> derive_rewrites(['a','b'], [(['a'],['c'])], max_depth=1, strategy='all_matches')
[{'result': ('c', 'b'), 'proof': [{'rule': 0, 'positions': [0], 'before': ('a', 'b'), 'after': ('c', 'b')}]}]

>>> find_derivation(['a'], ['c'], [(['a'],['b']),(['b'],['c'])], max_depth=2)
[{'rule': 0, 'positions': [0], 'before': ('a',), 'after': ('b',)},
 {'rule': 1, 'positions': [0], 'before': ('b',), 'after': ('c',)}]
```

### `shapes.py` — intent group: `shape_transforms_and_assignment`

Dihedral-group (D4) transforms of boolean masks, IoU shape scoring, and exact
bipartite assignment. Extracted from the S5I5-class rotation-puzzle family
(`admorphiq.rotation`) — the kernel knows nothing about pieces, frames,
references, or click widgets, only masks and score matrices. Masks are
tuple-of-tuples of `bool`, normalized internally from any nested
truthy/falsy sequence.

| Function | Contract |
|---|---|
| `dihedral_transforms(mask) -> list[dict]` | All 8 D4 symmetries in fixed order (`identity, rot90, rot180, rot270, flip_h, flip_h_rot90, flip_h_rot180, flip_h_rot270`); each entry is `{"name", "mask"}`. Rotating a non-square mask transposes its dimensions. |
| `crop_to_content(mask) -> dict` | Tight bounding box of truthy cells: `{"mask": cropped, "offset": (row, col)}`. An all-false mask returns an empty mask and offset `(0, 0)`. |
| `iou(mask_a, mask_b) -> float` | Intersection-over-union after top-left-aligned zero-padding to the common bounding size (NOT a registration search — crop first for translation invariance). Both-empty is defined as `1.0`. |
| `best_transform_match(source_mask, target_mask, crop=True) -> dict` | The D4 transform of `source_mask` maximizing IoU against `target_mask`; `{"name", "iou", "mask"}`. Ties broken by `dihedral_transforms`' fixed order. |
| `assign_pairs(score_matrix) -> list[tuple[int, int]]` | EXACT maximum-total-score bipartite assignment via bitmask DP (not greedy) — covers every row when columns >= rows, or every column otherwise. |

```python
>>> crop_to_content(((False,False,False),(False,True,True),(False,True,False)))
{'mask': ((True, True), (True, False)), 'offset': (1, 1)}

>>> iou(((True,True,False),), ((False,True,True),))
0.3333333333333333

>>> assign_pairs([[5,4],[4,0]])   # greedy would pick (0,0)+(1,1)=5; exact finds 8
[(0, 1), (1, 0)]
```

### `paths.py` — intent group: `shortest_path` / `configuration_path`

Grid BFS, multi-source distance fields, BFS over an observed transition
store, and a fully-generic BFS over a caller-supplied state space. Extracted
from `admorphiq.tools.graph_search` (frontier/transition-graph search) and
`admorphiq.delivery` (grid navigation + measured action-map conversion) — no
salience-ordered click policy, novelty ownership, tier unlocking, goal
inference, or player/item semantics travels with the math.

| Function | Contract |
|---|---|
| `grid_shortest_path(passable, start, goal, moves=CARDINAL) -> list[Cell] \| None` | BFS shortest path over a passability grid, both endpoints inclusive. `start == goal` returns `[start]`; an out-of-bounds/impassable endpoint returns `None`. |
| `grid_distance_field(passable, sources, moves=CARDINAL) -> dict[Cell, int]` | Multi-source BFS distance to the nearest source; invalid sources are silently skipped. |
| `transition_shortest_path(transitions, start_key, goal_key) -> list[label] \| None` | Shortest LABEL sequence over the graph induced by observed `(state, label, next_state)` triples; a later-observed edge for the same `(state, label)` overwrites an earlier one. |
| `reachable_frontier(transitions, start_key, tried) -> list[(state, label)]` | `(state, label)` pairs reachable from `start_key` and not in the caller-supplied `tried` set, nearest-BFS-distance-first. Owns no novelty tracking itself. |
| `configuration_path(initial, goal_test, successors, max_states=100_000) -> list[label] \| None` | Generic BFS over any hashable state space; `goal_test`/`successors` must be deterministic. `[]` when `initial` already satisfies `goal_test`. |
| `path_to_moves(path, move_labels) -> list[label]` | Converts consecutive waypoint deltas to labels via a caller-supplied `{(dr,dc): label}` map; raises `ValueError` on an uncalibrated/non-adjacent hop. |
| `plan_delivery(worker, pickups, targets, passable, move_labels, interact_label, match=None, max_states=100000) -> list[label] \| None` | Ordered pick->deliver subgoal composition: assign each target a pickup (`assign_pairs`, min Manhattan cost, optional `match(pi,ti)` gate), order the pairs nearest-first from the worker's running position, and route each `worker -> adjacent(pickup) -> interact -> adjacent(target) -> interact` leg (`grid_shortest_path` + `path_to_moves`). `[]` when no targets; `None` when infeasible (more targets than pickups, no compatible pickup, or an unroutable leg). Plans routes + interaction points only — does NOT model game-specific interaction preconditions (facing/rotation, carry-follow); a caller whose game needs those refines the result or encodes them in the passability grid. |
| `plan_carry_delivery(worker, pickups, targets, carry_offset, passable, move_labels, interact_label, match=None, max_states=100000) -> list[label] \| None` | Offset-routing generalisation of `plan_delivery` for CARRY / follower games: a picked object rides at `carry_offset` from the worker, so seating it on any cell `C` (pickup point or delivery target) means routing the worker to `C - carry_offset`. Every leg routes to `cell - carry_offset` and interacts. Same assignment/ordering/`match`/None semantics. Like `plan_delivery`, models routes + interaction points, not facing or follower-collision — the caller refines (e.g. a facing nudge before pickups). |

The delivery planner (`plan_delivery`) is the generic "ordered subgoal
composition over a worker + pickups + targets" core — the reusable half of the
delivery/sokoban family (`admorphiq.adapters25.wa30`). It composes
`assign_pairs` (from `shapes.py`) with `grid_shortest_path` / `path_to_moves`;
`paths.py` therefore now imports `shapes.py` (no cycle: `shapes.py` is
stdlib-only). It knows nothing about wa30 — the caller supplies the roles, the
passability grid, the move-label map, and the interact action. Its deliberate
limit (documented in its docstring): it plans routes and interaction points,
not carry/facing physics, so a game whose delivery requires the carried item
to follow the worker onto the goal needs that modelled by the adapter, not the
kernel.

```python
>>> grid_shortest_path([[True, False], [True, True]], (0,0), (1,1))
[(0, 0), (1, 0), (1, 1)]

>>> transition_shortest_path([('A','a1','B'), ('B','a1','C'), ('A','shortcut','C')], 'A', 'C')
['shortcut']

>>> path_to_moves([(0,0),(0,1),(1,1)], {(0,1): 'right', (1,0): 'down'})
['right', 'down']
```

### `motion.py` — intent groups: `track_motion_and_effects` + `learned_operators_and_search`

Two related families sharing one module: comparing frames / tracking
detected regions across a transition (`frame_diff`, `changed_region_attribution`,
`track_objects`, `motion_vectors`), and learning + sequencing reusable
"action at a point writes this footprint" operators from observation
(`learn_point_operators`, `plan_overwrites`). Extracted from
`admorphiq.merge_drag` (region features, object tracking, motion vectors),
`admorphiq.rotation`/`admorphiq.slider` (changed-region attribution), and
`admorphiq.ring_paint` (learned overwrite operators + planning). Regions are
plain dicts in the shape `regions.py`'s `find_regions` produces
(`{"color","cells","bbox","centroid","size"}`) — this module reads those
keys but does not import `regions.py`.

| Function | Contract |
|---|---|
| `frame_diff(before, after) -> dict` | `{"cells": frozenset[(r,c)], "bbox": (r0,c0,r1,c1) \| None, "count": int}` for two same-shape frames. |
| `changed_region_attribution(diff_cells, regions) -> list[int]` | Region indices with nonzero overlap with `diff_cells`, sorted by overlap size descending (index ascending on ties). |
| `track_objects(regions_before, regions_after, max_shift=None) -> dict` | Matches same-colour regions across two frames, per colour: Stage 1 greedily matches identical (translation-invariant) shape pairs nearest-centroid-first; Stage 2 finds the EXACT minimum-total-distance assignment among the remaining pairs via `shapes.assign_pairs` (not greedy — see API-inconsistency note #2's resolution below). `{"matches": [{"before","after","shift"}], "vanished": [...], "appeared": [...]}`. |
| `motion_vectors(matches) -> dict` | Summarizes `track_objects`' matches: `{"per_object": [(dr,dc),...], "dominant": (dr,dc) \| None}` (most common nonzero shift). |
| `learn_point_operators(observations) -> list[dict]` | From `[{"point","before","after"}, ...]`, clusters observations with an identical relative write footprint into `{"footprint","writes","support","points"}` operators — a no-effect click clusters into its own empty-footprint operator, not dropped. |
| `plan_overwrites(initial, target, operators, max_steps=64) -> list[dict] \| None` | Greedy step sequence (from `learn_point_operators`' output) toward `target`; each step picks the `(operator, point)` maximizing net newly-correct cells. Not globally optimal by design — see its docstring. |
| `reflect_cells(cells, axis) -> frozenset` | Reflect cells across `axis = (kind, position)`: `"col"` maps `(r,c)->(r,position-c)`, `"row"` maps `(r,c)->(position-r,c)`. `position` is the DOUBLED axis coordinate (`2m`), always integer. |
| `reflection_orbit(cells, axes, bounds=None, max_depth=12) -> frozenset` | Closure of `cells` under the group generated by `axes` — the "kaleidoscope" a mirror puzzle renders. `bounds=(h,w)` clips off-grid images (and guarantees termination for multi-axis groups). |
| `learn_reflection_operators(observations, background=None) -> dict` | From `[{"before","after","label"}, ...]` (each a move that translated a piece rendered with reflected copies), recovers `{"axes", "piece_colors", "piece_cells", "delta_map", "moving_colors", "correspondences"}`: the mirror axes (from a move that splits a piece from its image by opposite shift), the driven piece's colours + full colour-membership footprint, and its per-action displacement. Empty axes ⇒ not a reflective puzzle (caller falls back). |
| `plan_reflection_coverage(piece_cells, axes, target_cells, delta_map, bounds, max_states=100000) -> list \| None` | BFS (`configuration_path`) over piece translations (`delta_map` = `{action_label: (dr,dc)}`) for one whose rendered footprint (piece + reflections across `axes`, clipped to `bounds`) is a superset of `target_cells`. Returns the shortest action-label sequence, `[]` if already covered, `None` if unreachable or the model is empty. |
| `learn_flow_operators(layer_frames, background=None) -> dict` | From a spill's stacked animation layers (one per tick), recovers `{"flow_color", "fall_dir", "source_cells"}`: the flowing colour (count grows across layers), the unit fall direction (dominant axis of the flow centroid's advance), and the layer-0 emit cells. Empty model ⇒ caller uses a geometry-derived direction. |
| `simulate_flow(source_cells, blocked_cells, target_regions, fall_dir, bounds, max_cells=…) -> dict` | Droplet BFS: fluid advances in `fall_dir`; at a blocked cell it spreads to the two perpendicular cells and resumes (flow around an obstacle); a target region is SATISFIED on an interior hit (both perpendicular neighbours the same region). Returns `{"satisfied": frozenset[int], "water_cells": frozenset}`. |
| `plan_flow_coverage(movable_cells, delta_map, static_blocked, source_cells, target_regions, fall_dir, bounds, max_states=100000) -> list \| None` | BFS (`configuration_path`) over movable-obstacle translations for one where `simulate_flow` (over `static_blocked` + the translated movable) satisfies EVERY `target_regions`. Returns the shortest action-label sequence, `[]` if already covered, `None` if unreachable or the model is empty. |

The reflective-symmetry pair (`learn_reflection_operators` /
`plan_reflection_coverage`, plus `reflect_cells` / `reflection_orbit`) is the
mirror analogue of `learn_point_operators` / `plan_overwrites` the codex
verdict proposed. Extracted as the generic core of the AR25-class
mirror-coverage family (`admorphiq.adapters25.ar25`): a movable piece is drawn
together with its reflections; a level wins when a static goal glyph is fully
covered by the piece's rendered footprint. The kernel imports `find_regions`
(segmentation) and `configuration_path` (search); it holds no colour or
game constants — the axis, piece, deltas, and goal are all learned from
frames. `motion.py` therefore now depends on `regions.py` and `paths.py`
(no cycle: neither imports `motion.py`).

The fluid-flow trio (`learn_flow_operators` / `simulate_flow` /
`plan_flow_coverage`) is the same shape generalised to fluid propagation —
the generic core of the SP80-class water-routing family
(`admorphiq.adapters25.sp80`): a movable obstacle deflects a fluid emitted
from a source; a level wins when the flow covers every target's interior. The
fall direction and source cells are learned from a spill's stacked animation
layers; the flow-around-obstacle rule is generic (spread perpendicular, resume
falling), parameterised only by the learned fall direction; the planner
searches obstacle placements by simulating. No water physics or game constants
live in the kernel.

```python
>>> frame_diff([[0,0],[0,0]], [[0,5],[0,0]])
{'cells': frozenset({(0, 1)}), 'bbox': (0, 1, 0, 1), 'count': 1}

>>> obs = [{'point': (0,0), 'before': [[0,0],[0,0]], 'after': [[0,3],[0,0]]},
...        {'point': (1,0), 'before': [[0,0],[0,0]], 'after': [[0,0],[0,3]]}]
>>> learn_point_operators(obs)
[{'footprint': frozenset({(0, 1)}), 'writes': {(0, 1): 3}, 'support': 2, 'points': [(0, 0), (1, 0)]}]
>>> plan_overwrites([[0,0],[0,0]], [[0,3],[0,0]], learn_point_operators(obs))
[{'point': (0, 0), 'operator': 0}]
```

### `regions.py` — intent group: `regions_and_relations`

Same-colour (or gap-tolerant) connected-component segmentation, pairwise
spatial relations, axis clustering, shape-multiset comparison, and integer-fair
bbox tiling. Extracted from `admorphiq.sort_match` (row/column grouping,
multiset comparison), `admorphiq.delivery` (size clustering, slot tiling),
`admorphiq.transform_route` (gap-tolerant clustering), and
`admorphiq.merge_drag` (region features). No role assignment travels with
the math — no "largest is the goal", no "small rings are items".

| Function | Contract |
|---|---|
| `find_regions(frame, background=None, connectivity=4, gap=0) -> list[Region]` | Same-colour connected components (4- or 8-connectivity, or gap-tolerant Chebyshev clustering when `gap > 0`); each `{"color","cells","bbox","centroid","size"}`, sorted by `(bbox row0, bbox col0, color)`. |
| `region_relations(regions) -> list[dict]` | Every pairwise `contains` / `adjacent` (4-connectivity) / `aligned_row` / `aligned_col` (centroid within 0.5 cells) relation that holds, as `{"a","b","relation"}`. |
| `group_by_axis(regions, axis="row", tolerance=1.0) -> list[list[int]]` | Chains region indices into groups by centroid position on `axis`, transitively within `tolerance` of the previous member. |
| `multiset_signature(region) -> frozenset` | Translation-invariant shape signature: `region["cells"]` re-expressed relative to its own bbox origin. |
| `multisets_equal(regions_a, regions_b) -> bool` | Do the two lists hold the same multiset of `(colour, multiset_signature)`? Order-independent, translation-invariant. |
| `size_clusters(regions, ratio=1.5) -> list[list[int]]` | Groups region indices into size classes, starting a new cluster whenever consecutive sorted sizes jump by more than `ratio`. |
| `tile_bbox(bbox, rows, cols) -> list[Bbox]` | Integer-fair tiling of `bbox` into `rows x cols` sub-bboxes (sizes differ by at most 1), row-major order. |

```python
>>> frame = [[5,5,0],[9,9,0]]
>>> regions = find_regions(frame, background=0)
>>> region_relations(regions)
[{'a': 0, 'b': 1, 'relation': 'adjacent'}, {'a': 0, 'b': 1, 'relation': 'aligned_col'}]

>>> multisets_equal(find_regions([[5,5,0,0]], background=0), find_regions([[0,0,5,5]], background=0))
True

>>> tile_bbox((0,0,3,3), rows=2, cols=2)
[(0, 0, 1, 1), (0, 2, 1, 3), (2, 0, 3, 1), (2, 2, 3, 3)]
```

### `canonical.py` — intent group: `state_canonicalization` (see note below)

Four hashing/grouping strategies for frame state identity (`exact`,
`downsample`, `histogram`, `shape`), plus measurement of how well each mode
dealiases a caller-labeled set of "same state" / "different state" frame
groups. Extracted from `admorphiq.tools.graph_search`'s state hashing and
`admorphiq.tools.dealias`'s aliasing-detection CONCEPT — the kernel measures
which mode over-splits or over-merges; it never switches keys or owns policy
about when to escalate, that stays with the caller.

**Note**: this is a 7th kernel group, not one of the six the verdict doc's
"Proposed decomposition" section originally listed (`regions_and_relations`,
`track_motion_and_effects`, `shortest_path`/`configuration_path`,
`shape_transforms_and_assignment`, `learned_operators_and_search`,
`rewrite_derivations`) — it was added because the `graph_search.py` row of
the decomposition table explicitly calls for "state canonicalization
variants with confidence" as a safe extraction. Anyone designing the
declared-intent interface (task #42) should plan for 7 intents, not 6.

| Function | Contract |
|---|---|
| `canonical_key(frame, mode="exact", factor=4, background=None) -> Hashable` | `"exact"`=full grid; `"downsample"`=`factor`x`factor` mode-pooled grid (ties toward smallest colour); `"histogram"`=sorted `(colour,count)` tuple; `"shape"`=frozenset of non-background cells normalized to their own bbox origin (background auto-inferred as the most common colour when `None`). Raises `ValueError` on an unknown mode or non-positive `factor`. |
| `key_table(frames, modes, factor=4, background=None) -> dict[str, list]` | `{mode: [canonical_key(frame, mode) for frame in frames]}` convenience wrapper. |
| `stability_report(frame_groups, modes=ALL, factor=4, background=None) -> dict` | Per mode: `{"intra_consistent": bool, "intra_splits": int, "inter_collisions": int, "distinct_keys": int}` measured against caller-labeled `frame_groups` (each inner list = frames asserted to be the same true state). |
| `choose_canonicalization(frame_groups, modes=ALL, factor=4, background=None) -> dict` | `{"mode", "report"}` — picks by `(inter_collisions, intra_splits, fixed_cost_rank)` ascending; collision-avoidance strictly dominates cost (cost only breaks true ties: `histogram < shape < downsample < exact`). |

```python
>>> frame = [[0,0,0],[0,5,0],[0,0,0]]
>>> canonical_key(frame, mode='histogram')
((0, 8), (5, 1))
>>> canonical_key(frame, mode='shape')
frozenset({(0, 0)})

>>> groups = [[[[0,0,0],[0,5,0],[0,0,0]], [[1,0,0],[0,5,0],[0,0,0]]], [[[5,0,0],[0,0,0],[0,0,0]]]]
>>> stability_report(groups, modes=('exact','histogram'))
{'exact': {'intra_consistent': False, 'intra_splits': 1, 'inter_collisions': 0, 'distinct_keys': 3},
 'histogram': {'intra_consistent': False, 'intra_splits': 1, 'inter_collisions': 1, 'distinct_keys': 2}}
```

### `geometry.py` — intent group: `shape_geometry` (see note below)

Closed-frame (ring/hollow-border) detection, elongated-region axis
extraction + point-to-axis projection, point-stepping toward a target,
near-axis offset snapping, minimal covering-translation search, and
thin-path connector detection between two regions. Extracted from
`admorphiq.delivery` (closed-frame/ring detection), `admorphiq.slider`
(elongated-region detection, axis/endpoints, point-to-axis projection),
`admorphiq.transform_route` (axis snapping, `covering_offsets`-style set
cover), `admorphiq.sort_match` (hollow-box + connector extraction), and
`admorphiq.merge_drag` (`point_toward`-style stepping) — no role semantics
travel with the math (no "small ring is an item", no "foreign cell is a
tip", no "ring dot is the required colour").

**Note**: this closes both of the previous catalog version's "not yet
covered" gap entries #1 (structural closed-shape detection) and #2
(geometry primitives) — see the updated Gaps section below. It is also an
8th kernel intent group (alongside `canonical.py`'s `state_canonicalization`
as the 7th), beyond the verdict doc's original six.

| Function | Contract |
|---|---|
| `closed_frames(frame, background=None) -> list[dict]` | Rectangular one-colour rings that fully enclose a hole — a component qualifies only when its cells are EXACTLY its own bbox border (a solid filled rectangle has extra interior cells and fails). `{"border_color","outer_bbox","inner_bbox","hole_cells"}` per ring. |
| `elongated_axis(region, min_aspect=3.0) -> dict \| None` | The principal axis of a `region` (bbox-based) when `length/thickness >= min_aspect`; `{"axis": "row"\|"col", "endpoints", "length", "thickness"}`, else `None`. |
| `project_to_axis(point, axis_info) -> Cell` | Nearest cell on an `elongated_axis`-shaped segment to `point` (clamped into the endpoint range on the fixed coordinate). |
| `point_toward(origin, target, distance=1) -> Cell` | The integer cell `distance` px from `origin` toward `target` along the straight line; clamps to `target` exactly rather than overshooting. |
| `axis_snap(offset, tolerance=1) -> Shift` | Snaps a near-axis `(dr, dc)` offset to the pure axis when the minor component is `<= tolerance` AND strictly smaller than the major one; otherwise unchanged. |
| `covering_offsets(shape_cells, target_points) -> list[Shift]` | A minimal set of translations of `shape_cells` covering every point in `target_points` — exact minimum set cover for <=12 candidates, greedy most-newly-covered-first above that. |
| `connectors(frame, regions, background=None) -> list[dict]` | Thin (<=2 cells thick) same-colour paths linking EXACTLY two of `regions` (cells already claimed by any `regions` entry are excluded from the search). `{"a","b","path_cells","color"}` per connector. |

```python
>>> closed_frames([[3,3,3],[3,0,3],[3,3,3]], background=0)
[{'border_color': 3, 'outer_bbox': (0, 0, 2, 2), 'inner_bbox': (1, 1, 1, 1), 'hole_cells': frozenset({(1, 1)})}]

>>> region = {'bbox': (0, 3, 9, 5)}   # 10 rows x 3 cols
>>> axis_info = elongated_axis(region, min_aspect=3.0)
>>> axis_info
{'axis': 'row', 'endpoints': ((0, 4), (9, 4)), 'length': 10, 'thickness': 3}
>>> project_to_axis((-5, 4), axis_info)
(0, 4)

>>> point_toward((0, 0), (10, 0), distance=3)
(3, 0)
>>> axis_snap((5, 1), tolerance=1)
(5, 0)

>>> shape = frozenset({(0, 0), (0, 1)})
>>> sorted(covering_offsets(shape, [(0, 0), (0, 1), (5, 5), (5, 6)]))
[(0, 0), (5, 5)]

>>> frame = [[3, 6, 6, 6, 4]]
>>> from admorphiq.kernels.regions import find_regions
>>> endpoints = [r for r in find_regions(frame, background=0) if r['color'] in (3, 4)]
>>> connectors(frame, endpoints, background=0)
[{'a': 0, 'b': 1, 'path_cells': frozenset({(0, 1), (0, 2), (0, 3)}), 'color': 6}]
```

**Also in `geometry.py` but missing from the previous catalog version**:
`split_fused_frame` and `recover_occluded_frame` — de-fusion counterparts to
`closed_frames` above, for the two ways a hollow ring's exact
cells-equal-border test can fail on a genuinely-hollow ring: extra cells
fused onto it (a same-colour appendage protruding off the border), or
missing cells (a portion of the border occupied by a DIFFERENT, already-
detected component crossing it). Extracted while recovering SB26's second
portal frame (`.wiki/wiki/rounds/r56_generic-kernels.md`'s "sb26" section) —
`split_fused_frame` closed the first shape (a box + protruding pipe, same
colour, one connected component); `recover_occluded_frame` closed a second,
genuinely different shape found in the same trace (a foreign-colour
connector physically crossing the ring's own border at exactly the missing
cells).

| Function | Contract |
|---|---|
| `split_fused_frame(region_or_cells, frame=None, background=None) -> dict \| None` | Finds the maximal rectangular ring embedded in a same-colour connected component via row/column SPAN-MODE (the ring's own border rows/columns share one common span regardless of an appendage widening the raw bbox), validates the candidate border is a subset of the cells and the hole is empty, then groups every leftover cell into appendage components by 4-connectivity among themselves. `None` if no candidate ring survives. |
| `recover_occluded_frame(region_or_cells, occluders) -> dict \| None` | Candidate bbox is the cells' own bbox directly (no span-mode search — nothing pushes it outward the way an appendage does); `missing = full_perimeter - cells`, and every missing cell must be covered by the union of caller-supplied `occluders`' cells (else `None`, a genuinely unexplained gap). Returns `None` (not a ring) when `missing` is already empty — call `closed_frames` first, this only on rejection. |

```python
>>> # A 3x3 ring (colour 3) with a 1-cell appendage off the right wall.
>>> frame = [[3,3,3,0], [3,0,3,3], [3,3,3,0]]
>>> cells = [(r,c) for r,row in enumerate(frame) for c,v in enumerate(row) if v == 3]
>>> split_fused_frame(cells, frame=frame, background=0)
{'frame': {'border_cells': frozenset({(0, 1), (1, 2), (2, 1), (0, 0), (2, 0), (0, 2), (2, 2), (1, 0)}), 'outer_bbox': (0, 0, 2, 2), 'inner_bbox': (1, 1, 1, 1), 'hole_cells': frozenset({(1, 1)})}, 'appendages': [{'cells': frozenset({(1, 3)}), 'attach_point': (1, 2)}]}

>>> # Same 3x3 ring, but its bottom-middle border cell is missing -- covered
>>> # by a foreign-colour pipe crossing it.
>>> ring_cells = [(0,0),(0,1),(0,2),(1,0),(1,2),(2,0),(2,2)]  # (2,1) missing
>>> pipe = {'cells': frozenset({(2,1),(3,1)})}
>>> recover_occluded_frame(ring_cells, occluders=[pipe])
{'frame': {'border_cells': frozenset({(0, 1), (1, 2), (2, 1), (0, 0), (2, 0), (0, 2), (2, 2), (1, 0)}), 'outer_bbox': (0, 0, 2, 2), 'inner_bbox': (1, 1, 1, 1), 'hole_cells': frozenset({(1, 1)})}, 'occluded_cells': frozenset({(2, 1)}), 'occluded_by': [{'occluder_index': 0, 'cells': frozenset({(2, 1)})}]}
```

### `parse.py` — intent group: `axis_projection_and_pitch_splitting` (9th group)

Axis-neutral occupied-run projection (a row/column scan segmenting on
full-background gaps, distinct from `regions.py`'s 2D same-colour
connected-component segmentation — a two-colour fill+ink region stays ONE
run here even though it would fragment under colour-flood-fill), exact
pitch-based run re-splitting, a generic value-frequency histogram, and
numeric ratio-jump clustering. Extracted while scoping TR87's rule-table
extraction (`docs/tr87_frame_only_grammar_design_20260715.md`) — a
same-colour connected-component scan fragments a two-colour glyph, so
isolating "one occupied run" needs a positional gap scan instead. No
"cell"/"glyph"/"token" semantics travel with the math; the caller decides
what a run or a colour count MEANS.

| Function | Contract |
|---|---|
| `occupied_runs(frame, axis="col", bbox=None, background=None) -> dict` | Projects `frame` along `axis`, segmenting into runs separated by full-background gaps (a column/row is a gap only when EVERY cross-axis line in `bbox` is background there). Returns `{"runs": [{"start","end","cells"} half-open, Python-slice-style], "gaps": [...]}` (`len(gaps) == len(runs) - 1`). Cannot itself distinguish one wide run from several adjacent runs rendered with no gap — that's `split_runs_by_pitch`'s job, given an explicit pitch. |
| `split_runs_by_pitch(runs, pitch, *, axis) -> list[dict]` | Splits each run into `pitch`-wide equal children. `pitch` is REQUIRED and never inferred (a run's own minimum width is not a safe pitch estimate — measured TR87 counterexample: `[3,1,1,3,...]`-width runs where the smallest width is debris, not a genuine glyph pitch). Raises `ValueError` if a run's width isn't an exact multiple of `pitch` (a remainder means `pitch` is wrong, never silently truncated). Each child carries `parent_index` back to its source run. |
| `color_mode(values, k=2) -> list[dict]` | Top-`k` most frequent values in any iterable of hashable values, `[{"color": v, "count": n}, ...]` ranked descending, ties broken by first-encountered order. |
| `cluster_widths(widths, ratio=1.5) -> list[list[int]]` | Groups `widths`' INDICES into size classes: sorts by value ascending, starts a new cluster whenever the next/previous ratio exceeds `ratio`. Generalises `regions.size_clusters` (which now delegates here) to any numeric sequence. |

```python
>>> frame = [[0,7,7,0,0,7,0,7,7,7,7,0]]
>>> r = occupied_runs(frame, axis='col', background=0)
>>> r
{'runs': [{'start': 1, 'end': 3, 'cells': frozenset({(0, 1), (0, 2)})}, {'start': 5, 'end': 6, 'cells': frozenset({(0, 5)})}, {'start': 7, 'end': 11, 'cells': frozenset({(0, 7), (0, 8), (0, 9), (0, 10)})}], 'gaps': [2, 1]}

>>> split_runs_by_pitch([r['runs'][2]], pitch=2, axis='col')
[{'start': 7, 'end': 9, 'cells': frozenset({(0, 7), (0, 8)}), 'parent_index': 0}, {'start': 9, 'end': 11, 'cells': frozenset({(0, 9), (0, 10)}), 'parent_index': 0}]

>>> color_mode([1, 1, 2, 3, 3, 3, 4], k=2)
[{'color': 3, 'count': 3}, {'color': 1, 'count': 2}]

>>> cluster_widths([1, 1, 2, 10, 11, 50])
[[0, 1], [2], [3, 4], [5]]
```

### `gf2.py` — intent group: `linear_algebra_over_gf2` (10th group)

Gaussian elimination over the field with two elements (0/1, addition =
XOR): solves a system `A x = target` and computes the null space (solution
space) of `A`. Pure parity-system math — a row states "the XOR of these
variables equals this target bit"; the kernel knows nothing about what the
variables represent (lights-out toggle cells, control-glyph states,
anything else reducible to a linear system over GF(2)). Public rows are
tuples of 0/1 ints; packed-integer bitmasks are used internally for the
actual elimination (XOR-ing whole rows as ints is simpler/faster than
per-column tuple arithmetic) but never cross the public boundary.

| Function | Contract |
|---|---|
| `gf2_solve(matrix_rows, target) -> Row \| None` | ONE particular solution to `A x = target` (every free variable set to 0), or `None` if the system is inconsistent. Combine with any `gf2_nullspace` vector (elementwise XOR) to reach other valid solutions when under-determined. `matrix_rows=[]` trivially solves to `()`. |
| `gf2_nullspace(matrix_rows) -> list[Row]` | A basis for `{x : A x = 0}` — one length-n tuple per free variable/degree of freedom; every 0/1 linear combination (XOR) of the basis is also a solution. |

```python
>>> # x0 xor x1 = 1 ; x1 xor x2 = 0  (3 vars, 2 eqns -- under-determined)
>>> matrix = [[1, 1, 0], [0, 1, 1]]
>>> target = [1, 0]
>>> gf2_solve(matrix, target)
(1, 0, 0)
>>> gf2_nullspace(matrix)
[(1, 1, 1)]
```

## Composition recipes

Each recipe marks, explicitly, which step is a **CALLER decision** (a role,
goal, or hypothesis the adapter/LLM supplies) versus a **kernel** (pure
computation with no say in the outcome) — that boundary is the entire point
of R56: kernels never make the decisions in the CALLER lines below.

The code blocks below are illustrative composition sketches with placeholder
names (`before_frame`, `goal_cell`, `b0`/`a0`, ...) standing in for whatever
frames/points a real adapter observed — they are not meant to be pasted and
run verbatim. Each recipe's "Verified run" line gives the actual concrete
numbers produced by running the equivalent code with real frames, confirmed
via `uv run python -c ...` against this repo.

### (a) Navigation

```python
from admorphiq.kernels.motion import track_objects
from admorphiq.kernels.regions import find_regions
from admorphiq.kernels.paths import grid_shortest_path, path_to_moves

regions_before = find_regions(before_frame, background=0)   # kernel
regions_after  = find_regions(after_frame, background=0)    # kernel
matched = track_objects(regions_before, regions_after)      # kernel

# CALLER: which matched region is "the player"? Here: the one with a nonzero shift.
mover = next(m for m in matched['matches'] if m['shift'] != (0, 0))
player_color = regions_before[mover['before']]['color']

# CALLER: the measured action -> delta map (from repeating this probe per action).
move_labels = {(0, 1): 'right', (0, -1): 'left', (-1, 0): 'up', (1, 0): 'down'}

# CALLER: which colour is "wall" -> passability grid.
wall_cells = set().union(*(r['cells'] for r in regions_after if r['color'] == 9))
passable = [[(r, c) not in wall_cells for c in range(w)] for r in range(h)]

player_cell = next(iter(r['cells'] for r in regions_after if r['color'] == player_color))
path = grid_shortest_path(passable, next(iter(player_cell)), goal_cell)  # kernel
actions = path_to_moves(path, move_labels)                               # kernel
```

Verified run (3x3 board, wall at `(2,2)`, player at `(1,2)` moving toward
`(0,0)`): `path = [(1, 2), (0, 2), (0, 1), (0, 0)]`,
`actions = ['up', 'left', 'left']`.

### (b) Paint

```python
from admorphiq.kernels.motion import learn_point_operators, plan_overwrites

# CALLER: which click observations to feed in (which points were probed).
observations = [{'point': (0,0), 'before': b0, 'after': a0},
                 {'point': (1,1), 'before': b1, 'after': a1}, ...]

operators = learn_point_operators(observations)   # kernel: clusters into reusable write footprints

# CALLER: what the target frame looks like (the goal — never inferred by the kernel).
plan = plan_overwrites(initial_frame, target_frame, operators)   # kernel: greedy sequence toward target
```

Verified run: two observations at `(0,0)` and `(1,1)` both writing `+(0,1) ->
3` learn ONE operator with `support=2`; planning `[[0,0,0],[0,0,0]] ->
[[0,3,0],[0,0,3]]` returns
`[{'point': (0, 0), 'operator': 0}, {'point': (1, 1), 'operator': 0}]`.

### (c) State graph

```python
from admorphiq.kernels.canonical import choose_canonicalization, canonical_key
from admorphiq.kernels.paths import transition_shortest_path, reachable_frontier

# CALLER: which probe frames are asserted to be the SAME true state (labeling).
choice = choose_canonicalization([[g1a, g1b], [g2a]])   # kernel: measures, picks a mode
mode = choice['mode']

# CALLER: which (frame, action, next_frame) triples were observed during play.
s0 = canonical_key(frame_start, mode=mode)     # kernel
s1 = canonical_key(frame_mid, mode=mode)       # kernel
s2 = canonical_key(frame_goal, mode=mode)      # kernel
transitions = [(s0, 'right', s1), (s1, 'down', s2)]

path = transition_shortest_path(transitions, s0, s2)          # kernel
frontier = reachable_frontier(transitions, s0, tried=set())   # kernel
```

Verified run: `choice['mode'] == 'exact'` on the shared canonical.py fixture;
`path == ['right', 'down']`; `frontier` lists both `(s0, 'right')` and `(s1,
'down')` as untried options reachable from `s0`.

## Gaps versus the Codex decomposition table

Comparing every row of the decomposition table in
`docs/r56_codex_toolbase_verdict_20260715.md` against the nine modules
above:

**Closed since the previous version of this catalog** (both were "not yet
covered" entries; `geometry.py` landed and covers them):

- **Structural "closed shape" detection** (ring / hollow-frame extraction —
  the old `rotation._is_ring_component` test). Needed by the `rotation.py`,
  `delivery.py`, and `sort_match.py` rows. Now covered by
  `geometry.closed_frames` (ring/hole detection) and `geometry.connectors`
  (the `sort_match.py` hollow-box/connector-extraction half specifically).
- **Geometry primitives**: `point_toward`, elongated-region axis/endpoint
  extraction + point-to-axis projection, axis snapping, and the verdict
  doc's explicitly-named `covering_offsets(shape, points)`. Now covered by
  `geometry.point_toward`, `geometry.elongated_axis` +
  `geometry.project_to_axis`, `geometry.axis_snap`, and
  `geometry.covering_offsets` respectively — the exact function name match
  is not a coincidence, `geometry.py`'s teammate implemented these directly
  against the verdict doc's own wording.

**Still not yet covered by any kernel:**

1. **Colour-boundary-crossing single-mover isolation** (`merge_drag.py`'s
   "multi-colour motion tracking" and `transform_route.py`'s
   "motion-isolated object extraction" — the `detect_mover_by_motion` /
   `detect_sprite_by_motion` technique of tracking the UNION of whichever
   cells changed under one calibration press, independent of which
   sub-colour carries the change). `motion.frame_diff` gives the raw
   changed-cell set; `motion.track_objects` requires PRE-segmented
   same-colour regions as input — neither covers "partition this raw diff
   into one coherent mover that may legitimately span colours".
2. **Change-probability / passive forward-simulation** (`world_model_agent.py`
   row: "change probability", passive `predict(action)`).
   `motion.learn_point_operators` answers "what does an action at a point
   write" structurally (with a `support` count), but nothing estimates a
   probability from accumulated observations or forward-simulates a
   hypothetical action's effect without running `plan_overwrites`' full
   search.

**Explicitly NOT gaps** (composable by the caller in a few lines, so not
worth a dedicated kernel — noted here so they aren't accidentally
re-implemented):

- `graph_search.py`'s "caller-supplied scorer" re-ranking a frontier:
  `reachable_frontier`'s output is a plain list the caller can sort/filter
  with their own scoring function directly.
- `sort_match.py`'s "region graph construction" from spatial relations:
  `region_relations`' pairwise facts are already in a shape a caller can
  fold into `(state, label, next_state)` triples for `transition_shortest_path`
  in a short loop.

## API inconsistencies noticed while writing this (feedback for before the library calcifies)

1. **FIXED — frame normalization was duplicated three times, inconsistently.**
   `motion.py`, `regions.py`, and `canonical.py` each defined their own
   private `_normalize_frame`; `regions._normalize_frame` was missing the
   `int(v)` cast the other two applied. Now unified: `src/admorphiq/kernels/
   _common.py` (private, not exported via `__all__`) holds ONE
   `normalize_frame` (int-casting, no empty-row collapse); `motion.py` and
   `regions.py` import it directly as `_normalize_frame`, and
   `canonical.py` layers its own extra "collapse all-empty-rows to `()`"
   behavior on top of it (a genuine, tested `canonical.py`-specific
   contract, not something the other two modules ever had or need — see
   `_common.py`'s and `canonical._normalize_frame`'s docstrings). Regression
   test: `tests/test_kernels_regions.py::test_find_regions_normalizes_mixed_int_float_cells_to_int_color`
   — note the actual bug this caught was NOT grouping (Python's `==`/`hash`
   already treat `1 == 1.0`, so grouping worked even pre-fix), it was
   `region["color"]`'s TYPE being scan-order-dependent (int if an int cell
   was flood-filled first, float if a float cell was) — now always `int`.
   **Remaining scope note**: `geometry.py` (landed after this catalog's
   first version) has the SAME duplicate pattern, still using its own
   private `_normalize_frame` rather than `_common.py` — not fixed in this
   round (out of the explicitly requested scope), flagged for a follow-up.
2. **FIXED — `track_objects` re-implemented greedy matching instead of
   composing `assign_pairs`.** Its Stage 2 (the no-shape-match fallback,
   previously nearest-centroid-first greedy) now scores every remaining
   same-colour pair by negated centroid distance and calls
   `shapes.assign_pairs` for the EXACT minimum-total-distance assignment.
   `max_shift`-ineligible pairs get a large finite negative sentinel score
   (`motion._INELIGIBLE_SCORE = -1e9`, deliberately NOT `float("-inf")` —
   `assign_pairs`' bitmask-DP reconstruction compares floating-point sums
   for equality, and a real `-inf` combined with the DP's own `-inf`
   "unreached state" sentinel can produce a `NaN` difference that never
   satisfies that equality check, silently truncating the returned
   assignment); `assign_pairs` always returns a FULL assignment over the
   smaller side even when forced through a sentinel-scored pair, so Stage 2
   re-checks eligibility on its output and discards any forced-ineligible
   pick rather than accepting it as a real match. Proven with a genuine
   greedy-vs-optimal counterexample (not merely a refactor with identical
   output): `tests/test_kernels_motion.py::test_track_objects_stage2_finds_exact_optimum_greedy_would_miss`
   crafts centroids where greedy grabs the single nearest edge first
   (total distance 11.05) while the true optimum is the crossed pairing
   (total 10.0) — searched for numerically (`assign_pairs` vs a simulated
   greedy pass) rather than hand-derived, since 2x2 counterexamples are
   easy to get wrong by hand. A second test,
   `test_track_objects_stage2_forced_full_coverage_pick_is_filtered_by_max_shift`,
   pins the sentinel-then-filter behaviour specifically. All pre-existing
   `track_objects` tests still pass UNCHANGED (33 tests, 0 modified) — none
   of them happened to exercise a case where greedy and exact disagree.
3. **Two incompatible "shape" representations exist for the same concept.**
   `shapes.crop_to_content` represents a cropped shape as `{"mask": ...,
   "offset": ...}` (a full 2D mask plus its origin); `canonical.canonical_key(mode="shape")`
   represents the same idea as a bare `frozenset` of bbox-normalized
   `(row, col)` offsets (positions only, no mask grid, no colour). Both are
   legitimate for their own module's use case, but a future caller wanting
   to compare "is this shapes.py shape the same as that canonical.py shape"
   has no direct bridge between the two representations. Worth deciding on
   one canonical "shape" data type before more modules need one.
4. **Coordinate convention was, positively, unified.** Related to (3): the
   library standardized on `(row, col)` coordinates everywhere (masks,
   cells, bboxes, shifts, moves), even though some of the ORIGINAL reference
   sources used `(x, y)` (e.g. `rotation.widget_candidates`,
   `delivery.bfs_path`'s waypoints). This is a deliberate, positive
   consistency win worth calling out explicitly so adapter authors don't
   accidentally flip row/col when porting logic from those reference files.
5. **Validation strictness varies by module, apparently by design.**
   `shapes.py`, `paths.py`, `regions.py`, and `canonical.py` all raise
   `ValueError` at documented input-contract boundaries (unknown mode/
   strategy/axis, non-positive factor/n, invalid connectivity/gap).
   `motion.py` does not — its module docstring explicitly states that
   same-shape frame preconditions are "a genuine precondition, not
   defensively checked here", per the repo's "trust internal callers"
   convention. That is a deliberate, documented choice, not an oversight,
   but it means a caller passing mismatched frame shapes to `motion.py`
   gets a raw `IndexError`/`KeyError` instead of the clean `ValueError`
   every other module gives for its own bad-input cases — worth flagging so
   nobody "fixes" one module's strictness to match the others without
   realizing the asymmetry is intentional in `motion.py`'s case.
