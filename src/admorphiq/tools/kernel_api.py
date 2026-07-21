"""Curated r59 kernel vocabulary exposed to the runtime code-agent (agent25).

The script25 adapters compose ``admorphiq.kernels`` at DEV-TIME to express the
public-25 clears (card 32.96%). The runtime path is the LLM code-agent
(``tools/code_agent.py``): the model WRITES python that ``run_code`` execs in a
sandbox exposing only ``current_frame`` + shallow ``history``. Without the
kernels the model reimplements every composition from scratch — this module is
the bridge that lets it CALL them as ``K.<name>(...)``.

Scope (Codex design review 2026-07-21, APPROVE-WITH-CHANGES):

* Only kernels that are PURE and fit "operate on a grid / list of regions /
  masks the model already has from ``current_frame``" are exposed. Kernels that
  need previous frames or observed transition triples (motion/permute/
  reachable_frontier/configuration_path) are DEFERRED — the sandbox does not
  yet hand the model that data (see ``DEFERRED`` below). Grammar/GF(2)/callback
  kernels are left to mechanic-specific dev-time adapters, not the general
  runtime menu.
* Combinatorial kernels are BOUNDED here in code (not by prompt guidance): a
  call that would blow the exec budget raises ``ValueError``, which ``run_code``
  catches and degrades to an empty queue — never a hang.
* ``KERNEL_CARDS`` is the compact per-kernel signature card injected into the
  code prompt (behind ``HARNESS_KERNEL_API``) so the model calls them correctly.

Sandbox note: injecting live functions does not attenuate them
(``K.fn.__globals__`` reaches real builtins), but the sandbox's existing ``np``
and ``act`` already do the same, the code author is our own cooperative offline
model, and Kaggle runs with internet disabled — so this adds no practical
capability the sandbox did not already grant. The ``import`` block remains a
guard-rail against accidental imports, not a security boundary.
"""

from __future__ import annotations

from typing import Any, Callable

from admorphiq.kernels.geometry import (
    covering_offsets,
    elongated_axis,
    point_toward,
)
from admorphiq.kernels.parse import color_mode
from admorphiq.kernels.paths import grid_shortest_path, path_to_moves
from admorphiq.kernels.regions import (
    find_regions,
    multiset_signature,
    region_relations,
)
from admorphiq.kernels.shapes import (
    assign_pairs,
    best_transform_match,
    crop_to_content,
    dihedral_transforms,
)

__all__ = ["KERNEL_API", "KERNEL_CARDS", "FEW_SHOT", "DEFERRED"]

# Hard bounds enforced in code (Codex change #3): the combinatorial kernels that
# can exceed the exec timeout / exhaust memory on a fragmented 64x64 frame.
_MAX_REGIONS = 96      # region_relations is O(n^2) in region count
_MAX_ASSIGN_SLOTS = 12  # assign_pairs is O(items * 2^slots)
_MAX_GAP = 3           # find_regions gap enlarges the per-cell neighbourhood


def _find_regions(frame: Any, background: Any = None, connectivity: int = 4,
                  gap: int = 0) -> Any:
    if gap > _MAX_GAP:
        raise ValueError(f"gap {gap} > {_MAX_GAP} (bounded to keep exec cheap)")
    return find_regions(frame, background=background, connectivity=connectivity,
                        gap=gap)


def _region_relations(regions: Any) -> Any:
    regions = list(regions)
    if len(regions) > _MAX_REGIONS:
        raise ValueError(
            f"{len(regions)} regions > {_MAX_REGIONS}; filter before relating")
    return region_relations(regions)


def _assign_pairs(score_matrix: Any) -> Any:
    rows = list(score_matrix)
    ncols = len(rows[0]) if rows else 0
    if min(len(rows), ncols) > _MAX_ASSIGN_SLOTS:
        raise ValueError(
            f"assign_pairs smaller dim {min(len(rows), ncols)} > "
            f"{_MAX_ASSIGN_SLOTS} (exponential — reduce candidates first)")
    return assign_pairs(rows)


# The runtime menu: stable name -> pure, bounded, current_frame-composable kernel.
KERNEL_API: dict[str, Callable[..., Any]] = {
    # perception
    "find_regions": _find_regions,
    "region_relations": _region_relations,
    "multiset_signature": multiset_signature,
    "color_mode": color_mode,
    # geometry
    "elongated_axis": elongated_axis,
    "point_toward": point_toward,
    "covering_offsets": covering_offsets,  # self-bounded (exact <=12 else greedy)
    # paths (BFS over a <=64x64 passability grid — bounded by grid size)
    "grid_shortest_path": grid_shortest_path,
    "path_to_moves": path_to_moves,
    # shapes
    "dihedral_transforms": dihedral_transforms,
    "crop_to_content": crop_to_content,
    "best_transform_match": best_transform_match,
    "assign_pairs": _assign_pairs,
}

# Kernels intentionally NOT exposed to the general runtime menu, with the reason.
# Wiring any of these needs either sandbox enrichment (previous_frame + observed
# transition triples) or a mechanic-specific adapter — tracked for a Phase-2 pass.
DEFERRED: dict[str, str] = {
    "frame_diff": "needs previous_frame (sandbox exposes only current_frame)",
    "separate_by_motion": "needs before/after frame pair",
    "track_objects": "needs before/after regions",
    "learn_cyclic_successor": "needs observed transition triples",
    "complete_cycle": "only useful with a learned successor map",
    "is_single_cycle": "only useful with a learned successor map",
    "reachable_frontier": "needs observed (state,action)->state transitions",
    "configuration_path": "needs goal_test + successors callbacks (model programs a search)",
    "plan_token_assignment": "needs learned permutation operators + budget",
    "plan_delivery": "many semantic args + callback; max_states param is a no-op",
    "points_with_centroid": "needs an is_free callback",
    "gf2_solve": "toggle-mechanic specific; model must build the coefficient matrix",
    "derive_rewrites": "token-grammar search, not grid/region shaped",
    "find_derivation": "token-grammar search, not grid/region shaped",
    "connected_components": "tools.base variant; conflicts with find_regions background rule",
}

# Compact per-kernel card for the prompt (arg shapes, (row,col) convention,
# return shape, hard limits). Kept terse — it competes for the model's context.
KERNEL_CARDS = """\
KERNEL TOOLBOX — call as K.<name>(...). All coords are (row, col). Pure helpers;
prefer them over reimplementing. A bad call raises (caught) — read the cards.

PERCEPTION
- K.find_regions(frame, background=None, connectivity=4, gap=0) -> [region...]
    region = {"color","cells"(frozenset (r,c)),"bbox"(r0,c0,r1,c1),"centroid"(r,c),"size"}.
    background: int/iterable of bg colours to skip, or None to keep all. gap<=3.
- K.region_relations(regions) -> per-region adjacency/containment dicts (<=96 regions).
- K.multiset_signature(region) -> frozenset of (dr,dc) offsets (translation-invariant shape).
- K.color_mode(values, k=2) -> top-k [{"value","count"}] most common values.

GEOMETRY
- K.elongated_axis(region, min_aspect=3.0) -> {"axis","angle",...} or None (is it a bar?).
- K.point_toward(origin(r,c), target(r,c), distance=1) -> the (r,c) one step toward target.
- K.covering_offsets(shape_cells, target_points) -> minimal [(dr,dc)...] translating the
    shape to cover every target point.

PATHS
- K.grid_shortest_path(passable, start(r,c), goal(r,c)) -> [cells incl. both] or None.
    passable: 2D truthy grid (True/1 = walkable). BFS, cardinal moves.
- K.path_to_moves(path, move_labels) -> [label...]; move_labels maps (dr,dc)->your action id.

SHAPES (mask = 2D truthy grid of one object)
- K.dihedral_transforms(mask) -> the 8 rotations/reflections as [{"mask","name"}...].
- K.crop_to_content(mask) -> {"mask","bbox"} tight-cropped.
- K.best_transform_match(source_mask, target_mask, crop=True) -> best {"name","iou",...}.
- K.assign_pairs(score_matrix) -> [(i,j)...] max-score matching (smaller dim <=12).
"""

# Model-AGNOSTIC worked example: the cards alone did not get the model to call
# the kernels (measured: kernel_replies=0). This shows the K. API end-to-end on a
# generic navigate-to-target goal. No model-specific tokens — teaches the API, not
# a phrasing. Adapt the roles/goal to what YOU see; do not copy verbatim.
FEW_SHOT = """\
EXAMPLE — a solver block that USES the kernels (adapt to what you see, don't copy):
```python
# Goal (inferred): move the mobile object onto the lone target cell.
regs = K.find_regions(current_frame, background=0)          # objects on the board
if len(regs) >= 2:
    player = min(regs, key=lambda r: r["size"])             # smallest = the mover
    target = max(regs, key=lambda r: r["size"])             # example role guess
    h, w = len(current_frame), len(current_frame[0])
    wall = 5                                                # a colour you judge impassable
    passable = [[current_frame[r][c] != wall for c in range(w)] for r in range(h)]
    pr, pc = int(player["centroid"][0]), int(player["centroid"][1])
    gr, gc = int(target["centroid"][0]), int(target["centroid"][1])
    path = K.grid_shortest_path(passable, (pr, pc), (gr, gc))
    if path:
        labels = {(-1, 0): "UP", (1, 0): "DOWN", (0, -1): "LEFT", (0, 1): "RIGHT"}
        for m in K.path_to_moves(path, labels)[:6]:
            act(m)
```
"""
