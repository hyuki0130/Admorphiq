"""Pure frame-diff, object-tracking, and learned-operator kernels ("track_motion_and_effects", R56).

Generic computation behind "compare two frames and attribute/learn what an
action did" — the recurring capability underneath several game-specific
solvers: :mod:`admorphiq.merge_drag` (region features, object tracking,
motion vectors, online estimation of click-induced displacement),
:mod:`admorphiq.rotation` and :mod:`admorphiq.slider` (changed-region
attribution — deciding which detected region a frame transition belongs to),
:mod:`admorphiq.world_model_agent` (click-effect evidence: observing what a
click wrote onto the frame), and :mod:`admorphiq.ring_paint` (learning an
overwrite mask from before/after frames, then planning a sequence of learned
overwrites toward a target). This module knows nothing about players,
goals, tiles, rings, or actions — only frames (grids of color indices) and
caller-supplied region dicts.

Frames are 2D grids of ints (color indices), normalized on entry to a tuple
of tuples so callers may pass any nested sequence; both frames in a diff
must share the same shape (a genuine precondition, not defensively checked
here — see the repo's "trust internal callers" convention). Regions are
plain dicts in the shape produced by :mod:`admorphiq.kernels.regions`'s
``find_regions`` — ``{"color", "cells", "bbox", "centroid", "size"}`` — but
this module does not import that module; it only reads those keys.

Stdlib only — no numpy. These kernels must run inside the sandboxed REPL
where only the standard library and explicitly provided modules exist.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from admorphiq.kernels._common import normalize_frame as _normalize_frame
from admorphiq.kernels.shapes import assign_pairs

Frame = tuple[tuple[int, ...], ...]
Cell = tuple[int, int]
Shift = tuple[int, int]
Region = Mapping[str, object]

# Score assigned to an (i, j) pair that violates max_shift when building
# track_objects' Stage-2 assignment matrix. A large FINITE negative number,
# not float("-inf"): shapes.assign_pairs' bitmask DP reconstruction compares
# floating-point sums for equality, and an actual -inf combined with the DP's
# own -inf "unreached state" sentinel can produce NaN differences that never
# satisfy that equality check (see the code review this constant grew out
# of), silently truncating the returned assignment. A finite sentinel this
# far below any real (non-negative) centroid distance can never be chosen
# over a genuinely eligible pair, while staying numerically well-behaved.
_INELIGIBLE_SCORE = -1e9


def _normalize_cells(cells: Iterable[Sequence[int]]) -> frozenset[Cell]:
    return frozenset((int(r), int(c)) for r, c in cells)


def frame_diff(before: Sequence[Sequence[int]], after: Sequence[Sequence[int]]) -> dict[str, object]:
    """Cell-level diff between two same-shape frames.

    Returns ``{"cells": frozenset[(row, col)], "bbox": (r0, c0, r1, c1) or
    None, "count": int}``. ``bbox`` is the inclusive bounding box of the
    changed cells, or ``None`` when nothing changed.
    """
    b = _normalize_frame(before)
    a = _normalize_frame(after)
    cells = frozenset(
        (r, c)
        for r, row_b in enumerate(b)
        for c, v in enumerate(row_b)
        if v != a[r][c]
    )
    if not cells:
        return {"cells": frozenset(), "bbox": None, "count": 0}
    rows = [r for r, _c in cells]
    cols = [c for _r, c in cells]
    bbox = (min(rows), min(cols), max(rows), max(cols))
    return {"cells": cells, "bbox": bbox, "count": len(cells)}


def changed_region_attribution(
    diff_cells: Iterable[Sequence[int]], regions: Sequence[Region]
) -> list[int]:
    """Rank ``regions`` by how much of ``diff_cells`` each one covers.

    Returns the indices of regions with at least one changed cell, sorted by
    intersection size descending, ties broken by index ascending. Regions
    with zero overlap are omitted entirely.
    """
    diff = _normalize_cells(diff_cells)
    scored = []
    for idx, region in enumerate(regions):
        overlap = len(_normalize_cells(region["cells"]) & diff)  # type: ignore[arg-type]
        if overlap > 0:
            scored.append((overlap, idx))
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return [idx for _overlap, idx in scored]


def _shape_signature(cells: Iterable[Sequence[int]]) -> frozenset[Cell]:
    """Cell set normalized so its bounding box's top-left corner is the origin."""
    normalized = _normalize_cells(cells)
    if not normalized:
        return frozenset()
    min_r = min(r for r, _c in normalized)
    min_c = min(c for _r, c in normalized)
    return frozenset((r - min_r, c - min_c) for r, c in normalized)


def _centroid_distance(a: Sequence[float], b: Sequence[float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def track_objects(
    regions_before: Sequence[Region],
    regions_after: Sequence[Region],
    max_shift: float | None = None,
) -> dict[str, object]:
    """Match regions across two frames of the same scene.

    Only same-color region pairs are considered candidates. Matching runs in
    two deterministic passes, per colour: first, pairs whose cell sets share
    an identical :func:`_shape_signature` (i.e. the same shape, only
    translated) are matched greedily nearest-centroid-first; second, the
    STILL-UNMATCHED same-color regions are matched via
    :func:`admorphiq.kernels.shapes.assign_pairs` — an EXACT
    minimum-total-distance assignment (not greedy) over the remaining
    same-colour pairs, scored by negated centroid distance. Each region is
    matched at most once. When ``max_shift`` is given, a pair is only
    eligible when its centroid-to-centroid Euclidean distance is <=
    ``max_shift``; ineligible pairs get :data:`_INELIGIBLE_SCORE` in the
    Stage-2 score matrix (so ``assign_pairs`` only picks them when no
    eligible pair exists to fill that slot, since it always returns a full
    assignment over the smaller side) and are then filtered back OUT of the
    result — a forced-ineligible pick is not a real match, it means that
    region genuinely has no viable partner and should count as
    vanished/appeared instead.

    Returns ``{"matches": [{"before": i, "after": j, "shift": (dr, dc)},
    ...], "vanished": [i, ...], "appeared": [j, ...]}``. ``shift`` is the
    rounded centroid displacement (exact, integer, when the pair is a true
    shape-preserving translation).
    """
    before_by_color: dict[object, list[int]] = {}
    for i, region in enumerate(regions_before):
        before_by_color.setdefault(region["color"], []).append(i)
    after_by_color: dict[object, list[int]] = {}
    for j, region in enumerate(regions_after):
        after_by_color.setdefault(region["color"], []).append(j)

    shapes_before = {i: _shape_signature(regions_before[i]["cells"]) for i in range(len(regions_before))}  # type: ignore[arg-type]
    shapes_after = {j: _shape_signature(regions_after[j]["cells"]) for j in range(len(regions_after))}  # type: ignore[arg-type]

    def _dist(i: int, j: int) -> float:
        return _centroid_distance(regions_before[i]["centroid"], regions_after[j]["centroid"])  # type: ignore[arg-type]

    def _shift(i: int, j: int) -> Shift:
        br, bc = regions_before[i]["centroid"]  # type: ignore[misc]
        ar, ac = regions_after[j]["centroid"]  # type: ignore[misc]
        return (round(ar - br), round(ac - bc))

    def _eligible(i: int, j: int) -> bool:
        return max_shift is None or _dist(i, j) <= max_shift

    matched_before: set[int] = set()
    matched_after: set[int] = set()
    matches: list[dict[str, object]] = []

    for color in sorted(set(before_by_color) & set(after_by_color), key=repr):
        before_idxs = before_by_color[color]
        after_idxs = after_by_color[color]

        shape_candidates = sorted(
            (_dist(i, j), i, j)
            for i in before_idxs
            for j in after_idxs
            if shapes_before[i] == shapes_after[j] and _eligible(i, j)
        )
        for _d, i, j in shape_candidates:
            if i in matched_before or j in matched_after:
                continue
            matched_before.add(i)
            matched_after.add(j)
            matches.append({"before": i, "after": j, "shift": _shift(i, j)})

        remaining_before = [i for i in before_idxs if i not in matched_before]
        remaining_after = [j for j in after_idxs if j not in matched_after]
        if remaining_before and remaining_after:
            score_matrix = [
                [
                    -_dist(i, j) if _eligible(i, j) else _INELIGIBLE_SCORE
                    for j in remaining_after
                ]
                for i in remaining_before
            ]
            for row, col in assign_pairs(score_matrix):
                i, j = remaining_before[row], remaining_after[col]
                if not _eligible(i, j):
                    continue  # forced by assign_pairs' full-coverage guarantee, not a real match
                matched_before.add(i)
                matched_after.add(j)
                matches.append({"before": i, "after": j, "shift": _shift(i, j)})

    matches.sort(key=lambda m: m["before"])  # type: ignore[arg-type,return-value]
    vanished = [i for i in range(len(regions_before)) if i not in matched_before]
    appeared = [j for j in range(len(regions_after)) if j not in matched_after]
    return {"matches": matches, "vanished": vanished, "appeared": appeared}


def motion_vectors(matches: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Summarize per-object shifts from :func:`track_objects`'s ``matches`` list.

    Returns ``{"per_object": [(dr, dc), ...], "dominant": (dr, dc) or None}``
    where ``per_object`` preserves ``matches``' order and ``dominant`` is the
    most common nonzero shift. Ties are broken by smallest L1 norm, then
    lexicographically smallest ``(dr, dc)``. ``dominant`` is ``None`` when
    every shift is ``(0, 0)`` (or there are no matches).
    """
    per_object = [tuple(m["shift"]) for m in matches]  # type: ignore[arg-type]
    counts: dict[Shift, int] = {}
    for shift in per_object:
        if shift == (0, 0):
            continue
        counts[shift] = counts.get(shift, 0) + 1
    if not counts:
        return {"per_object": per_object, "dominant": None}
    dominant = max(
        counts,
        key=lambda s: (counts[s], -(abs(s[0]) + abs(s[1])), -s[0], -s[1]),
    )
    return {"per_object": per_object, "dominant": dominant}


def learn_point_operators(observations: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """Learn reusable "click at a point writes this footprint" operators.

    ``observations`` is ``[{"point": (r, c), "before": frame, "after":
    frame}, ...]``. For each observation this computes the frame diff and
    the writes it produced relative to ``point``: ``wrote = {(dr, dc):
    after[r][c] for (r, c) in diff_cells}`` (an observation whose diff is
    empty has ``wrote == {}``). Observations with an identical ``wrote``
    mapping are then clustered into one operator: ``{"footprint":
    frozenset(offsets), "writes": {offset: color}, "support": count,
    "points": [point, ...]}``, in first-seen order. A no-effect observation
    therefore clusters into its own operator with an empty ``footprint`` —
    distinguishable from any real-effect operator, rather than silently
    dropped.

    Limitation (v1): ``writes`` records absolute output colors, not
    colors relative to what was there before, so operators only cluster
    across observations whose points started from frames that already
    agreed on every cell the operator touches. Color-relative footprints
    (writing "the value that was NOT the background", say) are not
    attempted here.
    """
    clusters: dict[tuple[tuple[Shift, int], ...], dict[str, object]] = {}
    order: list[tuple[tuple[Shift, int], ...]] = []
    for obs in observations:
        point = (int(obs["point"][0]), int(obs["point"][1]))  # type: ignore[index]
        before = _normalize_frame(obs["before"])  # type: ignore[arg-type]
        after = _normalize_frame(obs["after"])  # type: ignore[arg-type]
        diff = frame_diff(before, after)
        wrote = {(r - point[0], c - point[1]): after[r][c] for r, c in diff["cells"]}  # type: ignore[union-attr]

        key = tuple(sorted(wrote.items()))
        if key not in clusters:
            clusters[key] = {
                "footprint": frozenset(wrote.keys()),
                "writes": dict(wrote),
                "support": 0,
                "points": [],
            }
            order.append(key)
        clusters[key]["support"] = clusters[key]["support"] + 1  # type: ignore[operator]
        clusters[key]["points"].append(point)  # type: ignore[union-attr]

    return [clusters[key] for key in order]


def plan_overwrites(
    initial: Sequence[Sequence[int]],
    target: Sequence[Sequence[int]],
    operators: Sequence[Mapping[str, object]],
    max_steps: int = 64,
) -> list[dict[str, object]] | None:
    """Greedily sequence learned operators (from :func:`learn_point_operators`) to reach ``target``.

    Applying ``operator`` at ``point`` sets, for each ``(offset, color)`` in
    ``operator["writes"]``, the cell ``point + offset`` to ``color`` (offsets
    that land outside the grid are skipped). At each step this exact-greedy
    search evaluates every ``(operator, point)`` combination and picks the
    one whose application fixes the most currently-wrong cells net of any
    cells it would newly break (``net = fixed - broken``); ties go to
    whichever ``(operator, point)`` is enumerated first (operators in input
    order, points in row-major order). The search stops and returns the
    step list once ``target`` is reached, or returns ``None`` once no
    remaining step has ``net > 0`` (or ``max_steps`` is exhausted) without
    having reached ``target``.

    This is deliberately simple and not globally optimal (a step that helps
    now can foreclose a better later step); callers that need optimality
    should search over :func:`learn_point_operators`'s output externally
    (e.g. BFS over operator sequences).
    """
    state = [list(row) for row in _normalize_frame(initial)]
    target_grid = _normalize_frame(target)
    height = len(state)
    width = len(state[0]) if height else 0

    def _solved() -> bool:
        return all(state[r][c] == target_grid[r][c] for r in range(height) for c in range(width))

    steps: list[dict[str, object]] = []
    for _ in range(max_steps):
        if _solved():
            return steps
        best_step: dict[str, object] | None = None
        best_net = 0
        for op_idx, operator in enumerate(operators):
            writes: Mapping[Shift, int] = operator["writes"]  # type: ignore[assignment]
            for r in range(height):
                for c in range(width):
                    fixed = broken = 0
                    for (dr, dc), color in writes.items():
                        rr, cc = r + dr, c + dc
                        if not (0 <= rr < height and 0 <= cc < width):
                            continue
                        was_correct = state[rr][cc] == target_grid[rr][cc]
                        would_be_correct = color == target_grid[rr][cc]
                        if was_correct and not would_be_correct:
                            broken += 1
                        elif not was_correct and would_be_correct:
                            fixed += 1
                    net = fixed - broken
                    if net > best_net:
                        best_net = net
                        best_step = {"point": (r, c), "operator": op_idx}
        if best_step is None:
            return None
        steps.append(best_step)
        r, c = best_step["point"]  # type: ignore[misc]
        for (dr, dc), color in operators[best_step["operator"]]["writes"].items():  # type: ignore[union-attr]
            rr, cc = r + dr, c + dc
            if 0 <= rr < height and 0 <= cc < width:
                state[rr][cc] = color
    return steps if _solved() else None
