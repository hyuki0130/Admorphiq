"""Family-generic frame parse for the cell-state hypothesis family (R95b).

Lifted OUT of the quarantined ``admorphiq.adapters25`` game adapters so the
MODEL-FACING runtime (the grounding service, ``grounding.py``) and the R95a
templates parse ring/glyph and lattice structure WITHOUT importing quarantined
game-specific adapter code. Single implementation: both ``grounding.py`` and
``templates.py`` import from here. Pure frame observation - no game id, no
sprite tags, no internal game state. A test pins parse-here == adapter-there on
the real traces so the lift cannot silently drift.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Optional

from admorphiq.adapters25.base import most_common_color
from admorphiq.kernels import find_regions, tile_bbox

Cell = tuple[int, int]  # (row, col)
Grid = tuple[tuple[int, ...], ...]
Bbox = tuple[int, int, int, int]
Constraint = tuple[str, int]  # ("==" | "!=", marker_colour)

_MAX_CANDIDATE_FRACTION = 0.15
_RING_SIZE = 8
_MIN_RING_MEMBERS = 3
_COMPASS_ORDER = ("NW", "N", "NE", "W", "C", "E", "SW", "S", "SE")
_COMPASS_OFFSET_SIGNS = {
    "NW": (-1, -1), "N": (-1, 0), "NE": (-1, 1),
    "W": (0, -1), "E": (0, 1),
    "SW": (1, -1), "S": (1, 0), "SE": (1, 1),
}
_GLYPH_EQUAL_INK = 0
_GLYPH_NOT_EQUAL_INK = 2
_GLYPH_NO_CELL_INK = 3
_WHOLESALE_CHANGE_MAX_OVERLAP = 0.5

_SC25_MAX_CELL_AREA_FRACTION = 0.02
_SC25_MIN_LATTICE_CELLS = 9
_SC25_MAX_LATTICE_CELLS = 25

def _is_hud_row(bbox: Bbox, grid: Grid) -> bool:
    """A region confined entirely to the frame's LAST row (its bbox both
    starts and ends there, any column span) is the bottom HUD/status bar (a
    step counter or similar chrome), not a clickable cell -- excluded
    everywhere a candidate list is built. HUD-row contamination measured
    directly: a step counter incrementing every action inflates a region's
    diff bbox to span the whole frame, drowning out the real interaction
    points (see the FT09 decode session's CD82 cross-reference)."""
    if not grid:
        return False
    last_row = len(grid) - 1
    return bbox[0] == last_row and bbox[2] == last_row

def _region_candidates(grid: Grid) -> list[dict[str, Any]]:
    """Non-background, non-chrome candidate cell regions, in find_regions' own
    deterministic (bbox row0, bbox col0, colour) order."""
    if not grid:
        return []
    total_cells = len(grid) * len(grid[0])
    bg = most_common_color(grid)
    regions = find_regions(grid, background=bg)
    max_size = max(1, int(total_cells * _MAX_CANDIDATE_FRACTION))
    return [r for r in regions if r["size"] <= max_size and not _is_hud_row(r["bbox"], grid)]

def _is_wholesale_change(before: Grid, after: Grid) -> bool:
    """True when the board's own SET of candidate region POSITIONS (bbox,
    colour-blind) is mostly different before -> after -- a decoy -> reveal
    transition (measured: the visible layout is entirely replaced by a
    different, previously invisible one), not an ordinary click that only
    recolours existing regions in place (which keeps the SAME bbox set,
    jaccard overlap 1.0). This is what a trigger click is actually testing
    for; see ``_GLYPH_TRIGGER_BUDGET``'s docstring for why "did anything
    change" is the wrong question."""
    before_keys = {r["bbox"] for r in _region_candidates(before)}
    after_keys = {r["bbox"] for r in _region_candidates(after)}
    union = before_keys | after_keys
    if not union:
        return False
    overlap = before_keys & after_keys
    return len(overlap) / len(union) < _WHOLESALE_CHANGE_MAX_OVERLAP

def _cell_point(region: dict[str, Any]) -> Cell:
    r, c = region["centroid"]
    return (int(round(r)), int(round(c)))

def _cell_class(grid: Grid, bbox: Bbox) -> int:
    """The dominant colour within ``bbox`` on ``grid`` — this candidate
    cell's current 'state', read fresh from whatever is actually rendered
    there (never a stored/assumed colour)."""
    r0, c0, r1, c1 = bbox
    sub = tuple(row[c0 : c1 + 1] for row in grid[r0 : r1 + 1])
    return most_common_color(sub)

def _classify_glyph(glyph: dict[str, int]) -> tuple[str, int | None]:
    """Classify a discovered glyph's ROLE from its own ink pattern alone --
    never from a hardcoded game-specific ink literal. Returns ``("target",
    None)`` when every non-center compass value is within the known
    constraint alphabet (``_GLYPH_EQUAL_INK`` / ``_GLYPH_NOT_EQUAL_INK`` /
    ``_GLYPH_NO_CELL_INK``): an ordinary glyph whose reach constrains its
    neighbours' colours. Returns ``("control", stencil_ink)`` when every
    non-center value is EITHER the glyph's own marker colour (a "don't
    care" -- that compass position mirrors the control's own toggling
    state, see the module docstring's worked example) or exactly ONE other,
    non-alphabet colour shared across every such position -- that shared
    colour is the control's ACTION STENCIL ink, discovered per-glyph
    (measured: 6 on the one board with controls, but never assumed to be
    that literal). Returns ``("illegible", None)`` for anything else (a
    mixed bag of non-alphabet colours, or more than one control-ink
    candidate) -- rejected rather than guessed at, the precision guard the
    lowered ``_MIN_RING_MEMBERS`` floor needs now that low-member noise
    candidates are no longer filtered by count alone."""
    marker = glyph["C"]
    non_center = [v for name, v in glyph.items() if name != "C"]
    if all(v in (_GLYPH_EQUAL_INK, _GLYPH_NOT_EQUAL_INK, _GLYPH_NO_CELL_INK) for v in non_center):
        return ("target", None)
    other = {v for v in non_center if v != marker}
    if len(other) == 1:
        return ("control", next(iter(other)))
    return ("illegible", None)

def _discover_rings(grid: Grid) -> list[dict[str, Any]]:
    """Discover toggle rings and their center glyph gaps, ACCEPTING rings
    truncated by the frame edge. Pure frame observation: button size is the
    LARGEST size among same-sized regions occurring >= 8 times (a complete
    ring's own member count) -- largest, not most populous, because a
    glyph's own ink can fragment into many small same-sized pixels whose
    count can coincidentally rival or exceed the true button count on a
    small (single-ring) board, while buttons are consistently the larger
    regions on every measured board; pitch is the MODE of measured
    button-position gaps (the min is unreliable -- a smaller gap can be
    cross-cluster noise from an unrelated ring's columns landing nearby,
    measured directly on a real 4-ring board). A candidate glyph gap is
    accepted whenever it reads as a real glyph (non-background center) with
    at least ``_MIN_RING_MEMBERS`` real button neighbours AND a LEGIBLE ink
    pattern (``_classify_glyph`` -- rejects illegible noise now that the
    member floor alone is too low to do that job, see its own docstring);
    it need not have all 8 compass neighbours present as real buttons -- a
    board-edge-truncated ring simply has fewer (measured directly: 3-5 of
    8, the rest cut off by the frame boundary, with the missing positions'
    own ink value reading ``_GLYPH_NO_CELL_INK`` rather than 0/2).

    A second pass extends the button registry with a synthetic "cell" per
    discovered CONTROL glyph, keyed at its own glyph_bbox top-left exactly
    like a real button -- a control's own position is itself clickable and
    stateful (see the module docstring), and other glyphs' reach must be
    able to find it as an ordinary member. Every ring's ``ring_cells`` is
    then re-matched against the extended registry. This is a genuine no-op
    on any board with zero controls (the registry is unchanged, so
    re-matching reproduces the exact same result), which is why
    control-free levels are unaffected by this discovery step at all."""
    if not grid:
        return []
    bg = most_common_color(grid)
    regions = [r for r in find_regions(grid, background=bg) if not _is_hud_row(r["bbox"], grid)]
    size_counts = Counter(r["size"] for r in regions)
    button_sizes = [s for s, c in size_counts.items() if c >= _RING_SIZE]
    if not button_sizes:
        return []
    button_size = max(button_sizes)
    buttons = [r for r in regions if r["size"] == button_size]
    by_topleft = {(r["bbox"][0], r["bbox"][1]): r for r in buttons}

    btn_h = buttons[0]["bbox"][2] - buttons[0]["bbox"][0] + 1
    btn_w = buttons[0]["bbox"][3] - buttons[0]["bbox"][1] + 1
    row0s = sorted({r["bbox"][0] for r in buttons})
    col0s = sorted({r["bbox"][1] for r in buttons})
    row_gaps = [b - a for a, b in zip(row0s, row0s[1:]) if b - a >= btn_h]
    col_gaps = [b - a for a, b in zip(col0s, col0s[1:]) if b - a >= btn_w]
    if not row_gaps or not col_gaps:
        return []
    pitch_r = Counter(row_gaps).most_common(1)[0][0]
    pitch_c = Counter(col_gaps).most_common(1)[0][0]
    offsets = {
        name: (dr * pitch_r, dc * pitch_c)
        for name, (dr, dc) in _COMPASS_OFFSET_SIGNS.items()
    }

    candidate_centers = {
        (r0 - dr, c0 - dc) for r0, c0 in by_topleft for dr, dc in offsets.values()
    }
    # Pass 1: classify every LEGIBLE candidate (target or control), WITHOUT
    # yet applying the member-count floor. A candidate's own ink pattern is
    # independent of how many of its neighbours are real buttons, so
    # classification can happen before membership is finalised -- and it
    # MUST, because a genuine target glyph's member count can only be
    # correctly counted AFTER controls are known (see pass 2): one of its
    # real members can BE a control's own center, which isn't in the plain
    # button registry yet (measured directly: docs/r58_codex_ft09_l4_
    # solution_20260715.md's two 3-member target glyphs each have exactly
    # one control-center member -- checking the floor against by_topleft
    # alone always undercounts them by exactly the amount that matters).
    prelim: list[dict[str, Any]] = []
    for cr, cc in candidate_centers:
        if (cr, cc) in by_topleft:
            continue  # a real button, not a glyph gap
        glyph_bbox: Bbox = (cr, cc, cr + btn_h - 1, cc + btn_w - 1)
        if not _bbox_in_bounds(glyph_bbox, grid):
            continue  # the glyph itself must be fully on-frame to read it
        glyph = _read_glyph_compass(grid, glyph_bbox)
        if glyph["C"] == bg:
            continue  # not a real glyph -- just background at a lattice position
        kind, control_ink = _classify_glyph(glyph)
        if kind == "illegible":
            continue  # neither a readable target pattern nor a readable control stencil
        prelim.append({"glyph_bbox": glyph_bbox, "kind": kind, "control_ink": control_ink})

    # Pass 2: extend the button registry with a synthetic "cell" per
    # discovered CONTROL, keyed exactly like a real button -- a control's
    # own position is itself clickable and stateful (see the module
    # docstring), and other glyphs' reach must be able to find it as an
    # ordinary member. A no-op when no controls exist (extended_topleft ==
    # by_topleft), which is why control-free boards are unaffected.
    extended_topleft = dict(by_topleft)
    for cand in prelim:
        if cand["kind"] != "control":
            continue
        r0, c0, r1, c1 = cand["glyph_bbox"]
        centre_cell = {"bbox": cand["glyph_bbox"], "centroid": ((r0 + r1) / 2, (c0 + c1) / 2)}
        cand["centre_cell"] = centre_cell
        extended_topleft[(r0, c0)] = centre_cell

    # Pass 3: NOW match every candidate's members against the (possibly
    # control-extended) registry and apply the member-count floor -- the
    # floor's job (reject noise) only makes sense once true membership,
    # including control-center members, is known.
    rings: list[dict[str, Any]] = []
    for cand in prelim:
        cr, cc = cand["glyph_bbox"][0], cand["glyph_bbox"][1]
        neighbours = _ring_neighbours(extended_topleft, cr, cc, offsets)
        if len(neighbours) < _MIN_RING_MEMBERS:
            continue  # too few real members to be a genuine (even truncated) ring
        cand["ring_cells"] = neighbours
        rings.append(cand)
    return rings

def _bbox_in_bounds(bbox: Bbox, grid: Grid) -> bool:
    r0, c0, r1, c1 = bbox
    return 0 <= r0 and 0 <= c0 and r1 < len(grid) and c1 < len(grid[0])

def _ring_neighbours(
    by_topleft: dict[Cell, dict[str, Any]], cr: int, cc: int, offsets: dict[str, Cell]
) -> dict[str, dict[str, Any]]:
    """The button regions found at ``(cr, cc)``'s compass offsets -- a
    PARTIAL dict when some offsets have no real button (an edge-truncated
    ring, or a compass position the glyph itself marks as unconstrained).
    Never requires all 8; the caller treats a missing name as no cell to
    constrain there."""
    neighbours: dict[str, dict[str, Any]] = {}
    for name, (odr, odc) in offsets.items():
        pos = (cr + odr, cc + odc)
        if pos in by_topleft:
            neighbours[name] = by_topleft[pos]
    return neighbours

def _read_glyph_compass(grid: Grid, glyph_bbox: Bbox) -> dict[str, int]:
    """Split ``glyph_bbox`` into its 3x3 compass reading via the generic
    ``tile_bbox`` kernel (no hardcoded pixel offsets), sampling each
    sub-cell's top-left pixel (the glyph's own block-structured art)."""
    subs = tile_bbox(glyph_bbox, 3, 3)
    return {name: grid[r0][c0] for name, (r0, c0, _r1, _c1) in zip(_COMPASS_ORDER, subs)}

def _collect_constraints(
    grid: Grid, rings: list[dict[str, Any]]
) -> dict[Cell, tuple[dict[str, Any], list[Constraint]]]:
    """Build the FULL per-cell constraint set: for every board cell, collect
    an equality/inequality constraint from EVERY discovered glyph whose full
    8-neighbour reach includes it -- not just the 'nearest' glyph. A cell
    near where two or three rings meet can be, and measurably is, covered by
    more than one glyph simultaneously (the exact scenario the L3
    click-count formula's own falsification replay traced back to: a
    coverage-scoping bug, not a modelling error -- see the module
    docstring). Keyed by each button region's own bbox top-left (a stable
    per-cell identity, since the same region object is shared across every
    ring that reaches it)."""
    coverage: dict[Cell, tuple[dict[str, Any], list[Constraint]]] = {}
    for ring in rings:
        glyph = _read_glyph_compass(grid, ring["glyph_bbox"])
        marker = glyph["C"]
        for name, cell in ring["ring_cells"].items():
            key = (cell["bbox"][0], cell["bbox"][1])
            ink = glyph[name]
            if ink == _GLYPH_EQUAL_INK:
                constraint: Constraint | None = ("==", marker)
            elif ink == _GLYPH_NOT_EQUAL_INK:
                constraint = ("!=", marker)
            else:
                continue  # ink 3 (or anything else): no constraint from this glyph
            if key not in coverage:
                coverage[key] = (cell, [])
            coverage[key][1].append(constraint)
    return coverage

def _satisfies(colour: int, constraints: list[Constraint]) -> bool:
    for op, marker in constraints:
        if op == "==" and colour != marker:
            return False
        if op == "!=" and colour == marker:
            return False
    return True

def _sc25_regions(grid: Grid) -> list[dict[str, Any]]:
    if not grid:
        return []
    bg = most_common_color(grid)
    return find_regions(grid, background=bg)

def _sc25_lattice(grid: Grid) -> Optional[dict[str, Any]]:
    """Parse the 3x3 (>= 3x3) toggle lattice: >= 9 equal-size small regions
    whose centroids span >= 3 rows and >= 3 columns. Returns a dict with the
    cell regions, the ``(row_index, col_index) -> region`` map, the cell size,
    and the grid's row/col counts — or ``None`` when no lattice is present."""
    if not grid:
        return None
    height, width = len(grid), len(grid[0])
    max_area = _SC25_MAX_CELL_AREA_FRACTION * height * width
    by_size: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in _sc25_regions(grid):
        if r["size"] <= max_area:
            by_size[r["size"]].append(r)
    for size, members in sorted(by_size.items()):
        if not _SC25_MIN_LATTICE_CELLS <= len(members) <= _SC25_MAX_LATTICE_CELLS:
            continue
        row_centres = sorted({round(m["centroid"][0]) for m in members})
        col_centres = sorted({round(m["centroid"][1]) for m in members})
        if len(row_centres) < 3 or len(col_centres) < 3:
            continue
        index: dict[Cell, dict[str, Any]] = {}
        for m in members:
            ri = row_centres.index(round(m["centroid"][0]))
            ci = col_centres.index(round(m["centroid"][1]))
            index[(ri, ci)] = m
        return {
            "members": members,
            "index": index,
            "size": size,
            "rows": len(row_centres),
            "cols": len(col_centres),
        }
    return None
