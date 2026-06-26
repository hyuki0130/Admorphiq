"""PATTERN-MATCH primitive: paint-to-match (cd82) + GF(2) lights/toggle (ft09).

Win-condition class 3 of ``docs/game_win_conditions_taxonomy.md``:

* **paint** (cd82) — ``next_level()`` when ``np.array_equal(editable.pixels[mask],
  reference.pixels[mask])`` (mask excludes the two diagonals of a 10x10). The
  agent must repaint the *editable* region to match the *reference* region.
  Mechanic: select a palette colour (click a swatch), then click cells to set
  their colour. Efficiency lever: only repaint cells that differ.
* **toggle / lights** (ft09) — ``next_level()`` when a board predicate holds and
  each click flips a fixed cell subset. This is a linear system over GF(2):
  measure the toggle stencil ``A`` by probing, then solve ``A x = b`` for the
  target ``b``; the solution is a click *subset* (``2^n`` candidates, not
  ``n!``). See ``.wiki/wiki/concepts/gf2_toggle_stencil.md``.

Everything here is pure (env-free) and detection is observable-signature based.
The proven GF(2) / cell-class helpers are reused from
``admorphiq.strategies.inferential`` so there is one implementation of the
maths.
"""

from __future__ import annotations

import numpy as np

from admorphiq.general_agent import connected_components
from admorphiq.strategies.inferential import (
    _extract_cell_class,
    _gf2_solve,
    _rank_subsets_by_prediction,
)

# ── Tunables ─────────────────────────────────────────────────────────────────

# A clickable grid cell renders as a compact blob; reject the background field
# and the giant frame border. Sizes are in pixels of the 64x64 canonical layer.
_CELL_MIN_SIZE = 6
_CELL_MAX_SIZE = 160
# Two centroids closer than this (px) are the same lattice node (dedup).
_CELL_DEDUP_PX = 4.0
# Candidate cell cap. Interactive toggle buttons are indistinguishable from
# decorative same-colour tiles WITHOUT probing, so the detector must return a
# superset (the agent's interactive measurement then filters to the cells that
# actually toggle). A small cap (12) plus a centre-bias sort silently dropped
# ft09's 8 real tiles (they sit off-centre between a legend panel and the
# board); a larger cap keeps the whole board in the candidate set.
_MAX_TOGGLE_CELLS = 48
# Patch radius for reading a cell's dominant-colour "state".
_PATCH_RADIUS = 2
# A click probe counts as toggling cell i when its patch class flips.
# A paint region pair must have bbox dims within this px tolerance to be "congruent".
_REGION_DIM_TOL = 3
# Sprite grid resolution used for the per-cell paint diff (cd82 sprites are 10x10).
_PAINT_GRID = 10
# A palette swatch is a small distinct-colour cell enclosed by a uniform frame
# (the swatch border). Sizes bound the inner colour blob (cd82: a 3x3 = 9px
# centre inside a 5x5 frame). The border test rejects same-size decoys such as
# the selection-indicator line, which sits on the background with no frame.
_SWATCH_MIN_SIZE = 4
_SWATCH_MAX_SIZE = 25
_SWATCH_BORDER_FRAC = 0.5


# ── grid-cell detection (shared by toggle) ───────────────────────────────────


def detect_grid_cells(layer: np.ndarray, background: int | None = None) -> list[tuple[int, int]]:
    """Centroids ``(x, y)`` of the compact, clickable grid blobs in ``layer``.

    Observable signature: a toggle / lights board is a lattice of similarly
    sized coloured blocks separated by background. We take every non-background
    connected component whose size is in ``[_CELL_MIN_SIZE, _CELL_MAX_SIZE]``,
    dedup near-coincident centroids, and return up to ``_MAX_TOGGLE_CELLS``
    nearest the frame centre (the board is usually central; HUD chrome hugs the
    edges). Pure / env-free.
    """
    if layer.size == 0:
        return []
    if background is None:
        vals, counts = np.unique(layer, return_counts=True)
        background = int(vals[int(counts.argmax())])
    comps = [
        c
        for c in connected_components(layer, background, min_size=_CELL_MIN_SIZE)
        if _CELL_MIN_SIZE <= c["size"] <= _CELL_MAX_SIZE
    ]
    cents: list[tuple[int, int]] = []
    for c in comps:
        cx, cy = int(round(c["cx"])), int(round(c["cy"]))
        if all((cx - px) ** 2 + (cy - py) ** 2 > _CELL_DEDUP_PX**2 for px, py in cents):
            cents.append((cx, cy))
    h, w = layer.shape
    midx, midy = w / 2, h / 2
    cents.sort(key=lambda p: (p[0] - midx) ** 2 + (p[1] - midy) ** 2)
    return cents[:_MAX_TOGGLE_CELLS]


# ── toggle / GF(2) ───────────────────────────────────────────────────────────


def build_stencil(
    cells: list[tuple[int, int]],
    click_probes: list[dict],
    patch_radius: int = _PATCH_RADIUS,
) -> dict | None:
    """Build the GF(2) stencil ``A`` from self-inverse click probes.

    ``click_probes`` is a list of ``{"x", "y", "before", "after"}`` where the
    click at ``(x, y)`` transformed frame ``before`` into ``after`` (and was
    then undone, so each probe is measured from the base state). ``A[i][j] = 1``
    iff clicking ``cells[j]`` flips ``cells[i]``'s dominant-colour patch class.
    Returns ``{"A", "base_classes", "toggled_classes", "cells"}`` or None when
    no probe maps to a known cell. Mirrors
    ``inferential._measure_toggle_stencil`` but consumes recorded probes
    instead of a live env, so it is pure.
    """
    n = len(cells)
    if n == 0 or not click_probes:
        return None
    base_frame = click_probes[0]["before"]
    base_classes = [_extract_cell_class(base_frame, x, y, patch_radius) for x, y in cells]
    A = np.zeros((n, n), dtype=np.uint8)
    toggled_classes: list[int] = [-1] * n
    mapped = 0
    for probe in click_probes:
        # Which cell index does this probe click?
        px, py = int(probe["x"]), int(probe["y"])
        j = _nearest_cell(cells, px, py)
        if j is None:
            continue
        after = probe["after"]
        before = probe.get("before", base_frame)
        bcls = [_extract_cell_class(before, x, y, patch_radius) for x, y in cells]
        mapped += 1
        for i, (ix, iy) in enumerate(cells):
            cls_after = _extract_cell_class(after, ix, iy, patch_radius)
            if cls_after != bcls[i]:
                A[i, j] = 1
                if toggled_classes[i] == -1:
                    toggled_classes[i] = cls_after
    if mapped == 0:
        return None
    return {
        "A": A,
        "base_classes": base_classes,
        "toggled_classes": toggled_classes,
        "cells": list(cells),
    }


def detect_toggle_task(layer: np.ndarray, probes: list[dict]) -> dict | None:
    """Detect a GF(2) toggle board and (when click probes exist) its stencil.

    Returns ``{"cells": [(x, y), ...], "stencil": {...} | None}`` or None when
    no lattice of clickable cells is present. ``stencil`` is None until click
    probes are supplied — the caller then issues a self-inverse probe sweep and
    re-invokes this detector (or :func:`build_stencil`) with the recordings.
    Observable signature only — never keys on a game id / title.
    """
    cells = detect_grid_cells(layer)
    if len(cells) < 2:
        return None
    click_probes = [p for p in probes if "x" in p and "y" in p and "after" in p and p.get("after") is not None]
    stencil = build_stencil(cells, click_probes) if click_probes else None
    return {"cells": cells, "stencil": stencil}


def plan_toggle(
    cells: list[tuple[int, int]],
    stencil: dict | None,
    top_k: int = 1,
) -> list[tuple[int, int]]:
    """Minimal click subset to drive the board to the most-homogeneous state.

    With a measured ``stencil`` we enumerate every subset ``x`` virtually
    (``_rank_subsets_by_prediction``), pick the highest-homogeneity solution
    (the typical "all the same" lights-out goal), and return the clicked cells
    ``[cells[j] for x[j] == 1]``. As a fast first try we also attempt a direct
    GF(2) solve toward the all-equal target. Efficiency: returns ONLY the
    solution cells, never an exhaustive sweep. Returns ``[]`` when no stencil is
    available or no informative subset exists.
    """
    if stencil is None:
        return []
    A = np.asarray(stencil["A"], dtype=np.uint8)
    n = A.shape[0]
    if n == 0 or int(A.sum()) == 0:
        return []
    base = stencil["base_classes"]
    toggled = stencil["toggled_classes"]

    # Fast path: solve A x = b directly for the "flip the minority cells to the
    # majority class" target, when toggled classes are known.
    direct = _direct_gf2_subset(A, base, toggled)
    if direct is not None:
        return [cells[j] for j in range(n) if direct[j]]

    ranked = _rank_subsets_by_prediction(A, base, toggled)
    for x_vec, _score in ranked[: max(1, top_k)]:
        if int(x_vec.sum()) > 0:
            return [cells[j] for j in range(n) if int(x_vec[j]) == 1]
    return []


def indicator_flip_sets(
    layer: np.ndarray, toggle_cells: list[tuple[int, int]]
) -> list[list[tuple[int, int]]]:
    """Candidate flip-sets read from a central *indicator* sprite.

    Many toggle puzzles are NOT "make every cell the same colour" — the win is
    a target *pattern* dictated by a small indicator (a clue / legend sprite)
    sitting amid the interactive cells (ft09: an 8-cell ring around one clue).
    The indicator encodes, per surrounding cell, a marker colour drawn from a
    tiny set (typically two values = "match me" / "differ from me"). Which
    marker means "flip" is not knowable from pixels alone, so we partition the
    ring cells by their marker value and return EACH partition as a candidate
    flip-set; the caller tries them against the live win predicate.

    Pure / env-free. Observable-signature only (no game id / title). Returns
    ``[]`` when fewer than two cells or no usable marker split exists.
    """
    if len(toggle_cells) < 2 or layer.size == 0:
        return []
    cix = int(round(sum(c[0] for c in toggle_cells) / len(toggle_cells)))
    ciy = int(round(sum(c[1] for c in toggle_cells) / len(toggle_cells)))
    xs = sorted({c[0] for c in toggle_cells})
    ys = sorted({c[1] for c in toggle_cells})

    def _pitch(vals: list[int]) -> int:
        gaps = [b - a for a, b in zip(vals, vals[1:]) if b - a > 0]
        return min(gaps) if gaps else 8

    px, py = _pitch(xs), _pitch(ys)
    off = max(1, min(px, py) // 4)
    h, w = layer.shape
    groups: dict[int, list[tuple[int, int]]] = {}
    for cx, cy in toggle_cells:
        sx = (cx > cix) - (cx < cix)
        sy = (cy > ciy) - (cy < ciy)
        my = min(h - 1, max(0, ciy + sy * off))
        mx = min(w - 1, max(0, cix + sx * off))
        marker = int(layer[my, mx])
        groups.setdefault(marker, []).append((cx, cy))
    # Only a genuine TWO-marker split is informative (one value = flip, the
    # other = leave). A single marker means the ring sits on a uniform field
    # (no indicator) — defer to the homogeneity planner instead.
    if len(groups) < 2:
        return []
    # Smaller partitions first: minimal-intervention targets are likelier and
    # cheaper to execute, and keep the move-budget metric happy.
    return sorted(groups.values(), key=len)


def _direct_gf2_subset(A: np.ndarray, base: list[int], toggled: list[int]) -> np.ndarray | None:
    """A GF(2) solution that flips every minority-class cell, or None.

    Builds the target flip vector ``b[i] = 1`` iff cell ``i`` is in the minority
    class and has a known alternate (``toggled[i] != -1``), then solves
    ``A x = b``. Returns the boolean subset or None when unsolvable.
    """
    n = A.shape[0]
    known = [i for i in range(n) if toggled[i] != -1]
    if not known:
        return None
    from collections import Counter

    majority = Counter(base[i] for i in known).most_common(1)[0][0]
    b = np.zeros(n, dtype=np.uint8)
    for i in known:
        if base[i] != majority:
            b[i] = 1
    if int(b.sum()) == 0:
        return None
    x = _gf2_solve(A, b)
    if x is None:
        return None
    return x.astype(bool)


# ── paint / region-match ─────────────────────────────────────────────────────


def _filled_regions(layer: np.ndarray, background: int) -> list[dict]:
    """Bounding-box descriptors of large, roughly rectangular coloured regions.

    Returns one dict per region (the merged bbox of all non-background pixels
    inside a connected mask of "not background"). Used to find the congruent
    reference + editable panels of a paint task.
    """
    mask = layer != background
    comps = connected_components(np.where(mask, np.int32(1), np.int32(0)), background=0, min_size=64)
    out: list[dict] = []
    for c in comps:
        ys = [r for r, _ in c["cells"]]
        xs = [col for _, col in c["cells"]]
        ymin, ymax, xmin, xmax = min(ys), max(ys), min(xs), max(xs)
        out.append(
            {
                "xmin": xmin,
                "xmax": xmax,
                "ymin": ymin,
                "ymax": ymax,
                "w": xmax - xmin + 1,
                "h": ymax - ymin + 1,
                "size": c["size"],
            }
        )
    return out


def detect_paint_task(layer: np.ndarray, probes: list[dict]) -> dict | None:
    """Detect a paint-to-match task: a reference region + a congruent editable region.

    Observable signature: two non-background regions whose bounding boxes have
    (near-)equal width and height — one is the *reference* pattern to copy, the
    other is the *editable* canvas. The reference is the more colourful of the
    pair (it already carries the target pattern); the editable is the more
    uniform one (it must be repainted). Returns
    ``{"reference_region", "editable_region", "palette"}`` (each region a
    ``(xmin, ymin, xmax, ymax)`` tuple, ``palette`` the list of colours the
    reference uses), or None when no congruent pair is found. Pure / env-free.
    """
    if layer.size == 0:
        return None
    vals, counts = np.unique(layer, return_counts=True)
    background = int(vals[int(counts.argmax())])
    regions = _filled_regions(layer, background)
    if len(regions) < 2:
        return None

    # All congruent pairs (matching bbox dims), preferring the largest panels.
    best: tuple[dict, dict] | None = None
    best_area = -1
    for i in range(len(regions)):
        for j in range(i + 1, len(regions)):
            a, b = regions[i], regions[j]
            if abs(a["w"] - b["w"]) <= _REGION_DIM_TOL and abs(a["h"] - b["h"]) <= _REGION_DIM_TOL:
                area = a["w"] * a["h"]
                if area > best_area:
                    best_area = area
                    best = (a, b)
    if best is None:
        return None

    a, b = best
    colours_a = _region_colours(layer, a, background)
    colours_b = _region_colours(layer, b, background)
    # The reference carries the pattern (more distinct colours); the editable is
    # the uniform canvas (fewer). Tie → the lower region is conventionally the
    # canvas, but we just pick by colour count which is observable.
    if len(colours_b) > len(colours_a):
        a, b = b, a
        colours_a, colours_b = colours_b, colours_a
    reference, editable = a, b
    palette = sorted(colours_a)
    return {
        "reference_region": (reference["xmin"], reference["ymin"], reference["xmax"], reference["ymax"]),
        "editable_region": (editable["xmin"], editable["ymin"], editable["xmax"], editable["ymax"]),
        "palette": palette,
    }


def _region_colours(layer: np.ndarray, region: dict, background: int) -> set[int]:
    """Set of non-background colours inside ``region``'s bounding box."""
    sub = layer[region["ymin"] : region["ymax"] + 1, region["xmin"] : region["xmax"] + 1]
    return {int(v) for v in np.unique(sub) if int(v) != background}


def _sample_cells(layer: np.ndarray, region: tuple[int, int, int, int], grid: int = _PAINT_GRID) -> np.ndarray:
    """Downsample ``region`` to a ``grid``x``grid`` array of dominant cell colours.

    Returns ``(grid, grid)`` int array; cell ``[r, c]`` is the mode colour of the
    corresponding sub-block of the region. This is the per-cell colour map the
    paint planner diffs.
    """
    xmin, ymin, xmax, ymax = region
    w = xmax - xmin + 1
    h = ymax - ymin + 1
    out = np.zeros((grid, grid), dtype=np.int32)
    for r in range(grid):
        for c in range(grid):
            y0 = ymin + (r * h) // grid
            y1 = ymin + ((r + 1) * h) // grid
            x0 = xmin + (c * w) // grid
            x1 = xmin + ((c + 1) * w) // grid
            block = layer[max(y0, ymin) : max(y1, y0 + 1), max(x0, xmin) : max(x1, x0 + 1)]
            if block.size == 0:
                continue
            v, cnt = np.unique(block, return_counts=True)
            out[r, c] = int(v[int(cnt.argmax())])
    return out


def _diagonal_mask(grid: int = _PAINT_GRID) -> np.ndarray:
    """Boolean ``grid``x``grid`` mask EXCLUDING both diagonals (True = compared).

    cd82's win compares ``pixels[mask]`` where ``mask[i, i] = mask[i, n-1-i] =
    False``. Cells on a diagonal are ignored by the win check, so the planner
    must not waste clicks repainting them.
    """
    mask = np.ones((grid, grid), dtype=bool)
    for i in range(grid):
        mask[i, i] = False
        mask[i, grid - 1 - i] = False
    return mask


def plan_paint(
    detection: dict,
    layer: np.ndarray,
    grid: int = _PAINT_GRID,
    action_id: int = 6,
) -> list[tuple[int, int, int]]:
    """Minimal ``(action_id, x, y)`` clicks to repaint editable → reference.

    Samples both regions to a ``grid``x``grid`` colour map, diffs them under the
    no-diagonals mask, and for each colour that some editable cell must become,
    emits ONE palette-select click (the reference cell of that colour) followed
    by a click on every editable cell that needs it. Grouping by colour
    minimises palette re-selection — the efficiency lever for the squared
    metric. Returns ``[]`` when the regions already match.
    """
    ref_region = detection["reference_region"]
    edit_region = detection["editable_region"]
    ref = _sample_cells(layer, ref_region, grid)
    cur = _sample_cells(layer, edit_region, grid)
    mask = _diagonal_mask(grid)

    exmin, eymin, exmax, eymax = edit_region
    ew = exmax - exmin + 1
    eh = eymax - eymin + 1

    def edit_px(r: int, c: int) -> tuple[int, int]:
        x = exmin + int((c + 0.5) * ew / grid)
        y = eymin + int((r + 0.5) * eh / grid)
        return x, y

    # Colour -> list of editable (x, y) cells that must become that colour.
    by_colour: dict[int, list[tuple[int, int]]] = {}
    for r in range(grid):
        for c in range(grid):
            if not mask[r, c]:
                continue
            if cur[r, c] == ref[r, c]:
                continue
            by_colour.setdefault(int(ref[r, c]), []).append(edit_px(r, c))

    if not by_colour:
        return []

    # Palette swatch location per colour: the first reference cell of that colour.
    rxmin, rymin, rxmax, rymax = ref_region
    rw = rxmax - rxmin + 1
    rh = rymax - rymin + 1
    swatch: dict[int, tuple[int, int]] = {}
    for r in range(grid):
        for c in range(grid):
            col = int(ref[r, c])
            if col not in swatch:
                x = rxmin + int((c + 0.5) * rw / grid)
                y = rymin + int((r + 0.5) * rh / grid)
                swatch[col] = (x, y)

    plan: list[tuple[int, int, int]] = []
    for colour, targets in by_colour.items():
        sx, sy = swatch.get(colour, targets[0][:2])
        plan.append((action_id, sx, sy))
        for tx, ty in targets:
            plan.append((action_id, tx, ty))
    return plan


def detect_palette_swatches(
    layer: np.ndarray,
    background: int | None = None,
    exclude: list[tuple[int, int, int, int]] | None = None,
) -> list[tuple[int, int, int]]:
    """Centroids + colour of palette swatches: small framed colour cells.

    Observable signature: a colour palette is a row/column of small swatches,
    each a distinct interior colour enclosed by a uniform *frame* colour. We
    return one ``(x, y, colour)`` per swatch (``x, y`` the click point, the
    swatch centre). The frame test — the 1px ring around the blob's bounding
    box must be dominated by a single non-background colour different from the
    blob — rejects same-size decoys (the selection-indicator line, stray sprite
    fragments) that sit on bare background. ``exclude`` lists region bounding
    boxes (reference / editable panels) whose interior swatch-sized blobs are
    not palette swatches. Pure / env-free; never keys on a game id / title.
    """
    if layer.size == 0:
        return []
    if background is None:
        vals, counts = np.unique(layer, return_counts=True)
        background = int(vals[int(counts.argmax())])
    exclude = exclude or []
    h, w = layer.shape
    cand: list[tuple[int, int, int, int]] = []  # (cx, cy, colour, frame_colour)
    for c in connected_components(layer, background, min_size=_SWATCH_MIN_SIZE):
        if not (_SWATCH_MIN_SIZE <= c["size"] <= _SWATCH_MAX_SIZE):
            continue
        cx, cy = int(round(c["cx"])), int(round(c["cy"]))
        if any(xmin <= cx <= xmax and ymin <= cy <= ymax for xmin, ymin, xmax, ymax in exclude):
            continue
        frame = _frame_colour(layer, c["cells"], int(c["color"]), h, w)
        if frame is not None:
            cand.append((cx, cy, int(c["color"]), frame))
    if not cand:
        return []
    # Real swatches share one frame colour; a hollow frame-ring blob has the
    # swatch colour AS its own colour (and a different surround). Keep only blobs
    # wrapped by the majority frame colour, dropping any whose own colour IS that
    # frame colour (those are the border rings, not selectable swatches).
    frame_vals, frame_counts = np.unique([f for *_, f in cand], return_counts=True)
    common_frame = int(frame_vals[int(frame_counts.argmax())])
    out = [
        (cx, cy, colour)
        for cx, cy, colour, frame in cand
        if frame == common_frame and colour != common_frame
    ]
    out.sort(key=lambda s: (s[1], s[0]))
    return out


def _frame_colour(
    layer: np.ndarray,
    cells: set[tuple[int, int]],
    colour: int,
    h: int,
    w: int,
) -> int | None:
    """The single frame colour enclosing ``cells``' bbox on all 4 sides, or None.

    A palette swatch's interior blob is wrapped by a closed border (the swatch
    frame); a decoy — the selection-indicator line, the hollow frame ring
    itself, a sprite fragment — is bordered on at most one side. We take each
    side's majority colour just outside the bbox and require all four to agree
    on a single colour ≠ the blob's own colour, returning that frame colour.
    Holds even when the swatch sits on a coloured panel (a bare-background test
    would misfire). ``_SWATCH_BORDER_FRAC`` guards a side being mostly empty.
    """
    ys = [r for r, _ in cells]
    xs = [col for _, col in cells]
    ymin, ymax, xmin, xmax = min(ys), max(ys), min(xs), max(xs)

    def _side_majority(coords: list[tuple[int, int]]) -> int | None:
        vals = [int(layer[y, x]) for y, x in coords if 0 <= y < h and 0 <= x < w]
        if not vals:
            return None
        u, counts = np.unique(vals, return_counts=True)
        if int(counts.max()) < _SWATCH_BORDER_FRAC * len(vals):
            return None
        return int(u[int(counts.argmax())])

    sides = [
        _side_majority([(ymin - 1, x) for x in range(xmin - 1, xmax + 2)]),
        _side_majority([(ymax + 1, x) for x in range(xmin - 1, xmax + 2)]),
        _side_majority([(y, xmin - 1) for y in range(ymin, ymax + 1)]),
        _side_majority([(y, xmax + 1) for y in range(ymin, ymax + 1)]),
    ]
    frame = sides[0]
    if frame is None or frame == colour:
        return None
    return frame if all(s == frame for s in sides) else None


def plan_region_fill(detection: dict, layer: np.ndarray, grid: int = _PAINT_GRID) -> list[dict]:
    """Decompose editable → reference into a minimal set of half-region fills.

    Many paint-to-match games (cd82) do NOT set individual cells on click — a
    tool fills a whole *half* of the editable canvas (top / bottom 5 rows or
    left / right 5 cols) with the selected colour, the fill side chosen by the
    tool's position. This planner reads the reference's band structure: when the
    target splits into two uniform horizontal bands (or two vertical bands) over
    the diagonal-excluded mask, it returns the ``{"side", "colour"}`` fills whose
    target band the editable does not already match. Filling a whole band to its
    uniform reference colour reaches the win predicate regardless of the
    editable's current (possibly probe-corrupted) state — the two half-fills
    repaint every compared cell. Returns ``[]`` when the reference is not a
    two-band axis-aligned pattern (the caller then falls back). Pure / env-free.
    """
    ref = _sample_cells(layer, detection["reference_region"], grid)
    cur = _sample_cells(layer, detection["editable_region"], grid)
    mask = _diagonal_mask(grid)
    return _decompose_region_fills(ref, cur, mask, grid)


def _decompose_region_fills(
    ref: np.ndarray, cur: np.ndarray, mask: np.ndarray, grid: int
) -> list[dict]:
    """Two-band (horizontal preferred, else vertical) fill decomposition."""
    half = grid // 2
    bands_h = [
        ("top", _strip(grid, rows=(0, half))),
        ("bottom", _strip(grid, rows=(half, grid))),
    ]
    bands_v = [
        ("left", _strip(grid, cols=(0, half))),
        ("right", _strip(grid, cols=(half, grid))),
    ]
    for bands in (bands_h, bands_v):
        colours = [_uniform_masked_colour(ref, region & mask) for _, region in bands]
        if any(c is None for c in colours):
            continue
        ops: list[dict] = []
        for (side, region), colour in zip(bands, colours):
            cmp_cells = cur[region & mask]
            if cmp_cells.size and bool(np.any(cmp_cells != colour)):
                ops.append({"side": side, "colour": int(colour)})
        return ops
    return []


def _strip(
    grid: int,
    rows: tuple[int, int] | None = None,
    cols: tuple[int, int] | None = None,
) -> np.ndarray:
    """Boolean ``grid``x``grid`` mask selecting a row-band or col-band strip."""
    m = np.zeros((grid, grid), dtype=bool)
    r0, r1 = rows if rows is not None else (0, grid)
    c0, c1 = cols if cols is not None else (0, grid)
    m[r0:r1, c0:c1] = True
    return m


def _uniform_masked_colour(grid_arr: np.ndarray, region: np.ndarray) -> int | None:
    """The single colour of ``grid_arr`` over ``region``, or None if not uniform."""
    cells = grid_arr[region]
    if cells.size == 0:
        return None
    vals = np.unique(cells)
    return int(vals[0]) if vals.size == 1 else None


# ── small helpers ────────────────────────────────────────────────────────────


def _nearest_cell(cells: list[tuple[int, int]], x: int, y: int, tol: float = 6.0) -> int | None:
    """Index of the cell within ``tol`` px of ``(x, y)``, else None."""
    best, bestd = None, tol * tol
    for j, (cx, cy) in enumerate(cells):
        d = (cx - x) ** 2 + (cy - y) ** 2
        if d <= bestd:
            best, bestd = j, d
    return best
