"""Hand-authored candidate hypothesis templates for the R95a selection test.

Two games, each a coherent cell-state-family case with decoded ground truth:

* **ft09** — a multi-ring glyph constraint-satisfaction toggle puzzle. The
  oracle reuses the REAL decoded parse from
  :mod:`admorphiq.adapters25.ft09` (``_discover_rings`` / ``_collect_constraints``
  / ``_satisfies`` / ``_cell_class``); the hard negatives are the historical
  wrong hypotheses (GF(2) neighbourhood stencil, nearest-glyph scoping, a
  uniform-colour goal, a cross-family preview-match win).
* **sc25** — a 3x3 spell-pattern toggle grid that auto-casts on an EXACT match
  to a displayed preview. The oracle is ``base XOR preview``; the negatives are
  a multi-state colour cycle, a near-match threshold, a neighbour stencil, and
  reading the preview as absolute colours (no base-parity XOR).

Every ``predict_click`` returns the set of ``(row, col)`` cells the template
expects a click at ``xy = (x, y)`` to CHANGE, or ``None`` when the template
makes no claim for that click (excluded from dynamics scoring). Every
``predict_win`` answers whether a board frame is a winning/cast state, reading
only that frame (the constraint glyphs / the preview widget are in-frame).

These parse helpers return ``None`` / ``False`` rather than raising on frames
whose expected structure is absent — recorded traces are an external data
boundary, so a missing lattice or an unreadable glyph is a legitimate
"no claim", not a programming error.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Optional

from admorphiq.adapters25.base import most_common_color
from admorphiq.adapters25.ft09 import (
    _cell_class,
    _collect_constraints,
    _discover_rings,
    _read_glyph_compass,
    _satisfies,
)
from admorphiq.kernels import find_regions, template_occupancy

Grid = tuple[tuple[int, ...], ...]
Cell = tuple[int, int]  # (row, col)
Xy = tuple[int, int]  # (x, y) = (col, row) — the ACTION6 click coordinate


@dataclass(frozen=True)
class HypothesisTemplate:
    """One candidate mechanic hypothesis for a game.

    ``predict_click(before, xy)`` returns the ``(row, col)`` cells this template
    expects the ACTION6 click at ``xy`` to CHANGE, or ``None`` for "no claim"
    (excluded from dynamics scoring). A single-cell claim is scored by exact set
    equality, a multi-cell claim by Jaccard >= 0.5.

    ``predict_win(board_frame)`` returns whether this template believes the
    frame is a winning/cast state — read from that frame alone.
    """

    name: str
    description: str
    predict_click: Callable[[Grid, Xy], Optional[set[Cell]]]
    predict_win: Callable[[Grid], bool]


# ── ft09 shared perception ──────────────────────────────────────────────────


def _ft09_click_regions(
    grid: Grid, xy: Xy
) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]]]:
    """The region the click landed on plus its four cardinal same-size
    neighbours (the GF(2) stencil footprint). ``xy`` is ``(x, y)`` so the
    clicked cell is ``(row=y, col=x)``. Returns ``(None, [])`` when the click
    misses every non-background region (a background click makes no claim)."""
    if not grid:
        return None, []
    x, y = xy
    bg = most_common_color(grid)
    regions = find_regions(grid, background=bg)
    clicked: Optional[dict[str, Any]] = None
    for r in regions:
        if (y, x) in r["cells"]:
            clicked = r
            break
    if clicked is None:
        return None, []

    cr, cc = clicked["centroid"]
    size = clicked["size"]
    same_size = [
        r for r in regions if abs(r["size"] - size) <= 1 and r["bbox"] != clicked["bbox"]
    ]
    neighbours: list[dict[str, Any]] = []
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        best: Optional[tuple[float, dict[str, Any]]] = None
        for r in same_size:
            rr, rc = r["centroid"]
            if dr != 0 and abs(rc - cc) <= 1.0 and (rr - cr) * dr > 0:
                dist = abs(rr - cr)
            elif dc != 0 and abs(rr - cr) <= 1.0 and (rc - cc) * dc > 0:
                dist = abs(rc - cc)
            else:
                continue
            if best is None or dist < best[0]:
                best = (dist, r)
        if best is not None:
            neighbours.append(best[1])
    return clicked, neighbours


def _ft09_click_single(grid: Grid, xy: Xy) -> Optional[set[Cell]]:
    """The clicked cell's own region cells — a single-cell (one-region) change
    claim: clicking a ft09 button recolours exactly that button."""
    clicked, _neighbours = _ft09_click_regions(grid, xy)
    if clicked is None:
        return None
    return set(clicked["cells"])


def _ft09_click_stencil(grid: Grid, xy: Xy) -> Optional[set[Cell]]:
    """The clicked cell plus its four cardinal neighbours — the historical GF(2)
    neighbourhood-toggle (``lights_out``) footprint, a multi-cell claim."""
    clicked, neighbours = _ft09_click_regions(grid, xy)
    if clicked is None:
        return None
    cells: set[Cell] = set(clicked["cells"])
    for r in neighbours:
        cells |= set(r["cells"])
    return cells


def _ft09_covered(grid: Grid) -> Optional[dict[Cell, tuple[dict[str, Any], list[Any]]]]:
    """Every board cell's full constraint set, via the REAL decoded parse. None
    when the board has no discoverable rings / no covered cell."""
    rings = _discover_rings(grid)
    if not rings:
        return None
    coverage = _collect_constraints(grid, rings)
    return coverage or None


def _ft09_win_all_constraints(grid: Grid) -> bool:
    """ORACLE win: every covered cell satisfies ALL its collected constraints."""
    coverage = _ft09_covered(grid)
    if coverage is None:
        return False
    return all(
        _satisfies(_cell_class(grid, cell["bbox"]), constraints)
        for cell, constraints in coverage.values()
    )


def _ft09_win_nearest_glyph(grid: Grid) -> bool:
    """N2 win: each covered cell need satisfy only its NEAREST glyph's
    constraint (others ignored). Rebuilds per-cell coverage keyed by the
    covering glyph's centre distance, then keeps the closest glyph only."""
    rings = _discover_rings(grid)
    if not rings:
        return False
    per_cell: dict[Cell, list[tuple[float, dict[str, Any], tuple[str, int]]]] = defaultdict(list)
    for ring in rings:
        glyph = _read_glyph_compass(grid, ring["glyph_bbox"])
        marker = glyph["C"]
        gr = (ring["glyph_bbox"][0] + ring["glyph_bbox"][2]) / 2
        gc = (ring["glyph_bbox"][1] + ring["glyph_bbox"][3]) / 2
        for name, cell in ring["ring_cells"].items():
            ink = glyph[name]
            if ink == 0:
                constraint: tuple[str, int] = ("==", marker)
            elif ink == 2:
                constraint = ("!=", marker)
            else:
                continue
            key = (cell["bbox"][0], cell["bbox"][1])
            crow, ccol = cell["centroid"]
            dist = abs(crow - gr) + abs(ccol - gc)
            per_cell[key].append((dist, cell, constraint))
    if not per_cell:
        return False
    for entries in per_cell.values():
        _dist, cell, constraint = min(entries, key=lambda e: e[0])
        if not _satisfies(_cell_class(grid, cell["bbox"]), [constraint]):
            return False
    return True


def _ft09_win_uniform_colour(grid: Grid) -> bool:
    """N3 win: all ring-member cells share one colour."""
    rings = _discover_rings(grid)
    if not rings:
        return False
    colours: set[int] = set()
    for ring in rings:
        for cell in ring["ring_cells"].values():
            colours.add(_cell_class(grid, cell["bbox"]))
    return len(colours) == 1


def _ft09_win_all_ink_equal(grid: Grid) -> bool:
    """N4 win: constraints evaluated with NOT_EQUAL ink (colour 2) treated as
    EQUAL — every covered cell must EQUAL each covering glyph's marker."""
    coverage = _ft09_covered(grid)
    if coverage is None:
        return False
    for cell, constraints in coverage.values():
        forced = [("==", marker) for _op, marker in constraints]
        if not _satisfies(_cell_class(grid, cell["bbox"]), forced):
            return False
    return True


def ft09_oracle_name() -> str:
    return "glyph_constraints"


def ft09_templates() -> list[HypothesisTemplate]:
    """The 5 ft09 candidates: oracle ``glyph_constraints`` + 4 hard negatives."""
    return [
        HypothesisTemplate(
            name="glyph_constraints",
            description=(
                "ORACLE — a click changes exactly the clicked cell (colour "
                "cycle step); win = every covered cell satisfies ALL its "
                "collected glyph constraints simultaneously."
            ),
            predict_click=_ft09_click_single,
            predict_win=_ft09_win_all_constraints,
        ),
        HypothesisTemplate(
            name="gf2_stencil",
            description=(
                "N1 — the historical lights_out GF(2) hypothesis: a click flips "
                "the clicked cell AND its 4 cardinal neighbours (multi-cell "
                "claim); win = same as the oracle (dynamics is the discriminator)."
            ),
            predict_click=_ft09_click_stencil,
            predict_win=_ft09_win_all_constraints,
        ),
        HypothesisTemplate(
            name="nearest_glyph_only",
            description=(
                "N2 — same single-cell dynamics as the oracle; win = each covered "
                "cell satisfies only its NEAREST glyph's constraint."
            ),
            predict_click=_ft09_click_single,
            predict_win=_ft09_win_nearest_glyph,
        ),
        HypothesisTemplate(
            name="uniform_colour",
            description=(
                "N3 — same single-cell dynamics as the oracle; win = all "
                "ring-member cells share one colour."
            ),
            predict_click=_ft09_click_single,
            predict_win=_ft09_win_uniform_colour,
        ),
        HypothesisTemplate(
            name="all_ink_equal",
            description=(
                "N4 — same single-cell dynamics as the oracle; win = constraints "
                "with NOT_EQUAL ink (colour 2) treated as EQUAL."
            ),
            predict_click=_ft09_click_single,
            predict_win=_ft09_win_all_ink_equal,
        ),
    ]


# ── sc25 shared perception ──────────────────────────────────────────────────

_SC25_MAX_CELL_AREA_FRACTION = 0.02
_SC25_MIN_LATTICE_CELLS = 9
_SC25_MAX_LATTICE_CELLS = 25
_SC25_PREVIEW_ROW_MARGIN = 6


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


def _sc25_cell_colour(grid: Grid, region: dict[str, Any]) -> int:
    r, c = region["centroid"]
    return grid[round(r)][round(c)]


def _sc25_on_set(grid: Grid, lattice: dict[str, Any]) -> frozenset[Cell]:
    """Cells whose colour differs from the lattice's majority (base) colour —
    the displayed toggle pattern (base-parity relative)."""
    index = lattice["index"]
    colours = [_sc25_cell_colour(grid, region) for region in index.values()]
    base = max(set(colours), key=lambda v: (colours.count(v), -v))
    return frozenset(k for k, region in index.items() if _sc25_cell_colour(grid, region) != base)


def _sc25_read_target(grid: Grid, lattice: dict[str, Any]) -> Optional[frozenset[Cell]]:
    """The preview target ON-set: small mark regions of a non-grid colour, in
    the block beside the grid, binned to the lattice's rows x cols by
    :func:`admorphiq.kernels.template_occupancy`. None when unreadable."""
    members = lattice["members"]
    grid_colours = {_sc25_cell_colour(grid, m) for m in members}
    gc0 = min(round(m["centroid"][1]) for m in members)
    gr0 = min(round(m["centroid"][0]) for m in members)
    gr1 = max(round(m["centroid"][0]) for m in members)
    mark_max = lattice["size"]
    regions = _sc25_regions(grid)
    marks = [
        r
        for r in regions
        if r["size"] < mark_max
        and r["color"] not in grid_colours
        and r["centroid"][1] < gc0
        and gr0 - _SC25_PREVIEW_ROW_MARGIN <= r["centroid"][0] <= gr1 + _SC25_PREVIEW_ROW_MARGIN
    ]
    if not marks:
        return None
    pts = [m["centroid"] for m in marks]
    block = _sc25_enclosing_block(regions, marks, pts)
    rows, cols = lattice["rows"], lattice["cols"]
    occ = template_occupancy(pts, block, rows, cols)
    return frozenset(
        (ri, ci) for ri in range(rows) for ci in range(cols) if occ[ri][ci]
    )


def _sc25_enclosing_block(
    regions: list[dict[str, Any]],
    marks: list[dict[str, Any]],
    pts: list[tuple[float, float]],
) -> tuple[int, int, int, int]:
    markset = {id(m) for m in marks}
    best: Optional[tuple[int, tuple[int, int, int, int]]] = None
    for r in regions:
        if id(r) in markset:
            continue
        r0, c0, r1, c1 = r["bbox"]
        if all(r0 <= mr <= r1 and c0 <= mc <= c1 for mr, mc in pts):
            area = (r1 - r0) * (c1 - c0)
            if best is None or area < best[0]:
                best = (area, r["bbox"])
    if best is not None:
        return best[1]
    boxes = [m["bbox"] for m in marks]
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _sc25_click_single(grid: Grid, xy: Xy) -> Optional[set[Cell]]:
    """The clicked lattice cell's own region cells — a single-cell toggle claim.
    None when the click is outside the lattice (or no lattice is present)."""
    lattice = _sc25_lattice(grid)
    if lattice is None:
        return None
    x, y = xy
    for region in lattice["index"].values():
        if (y, x) in region["cells"]:
            return set(region["cells"])
    return None


def _sc25_click_stencil(grid: Grid, xy: Xy) -> Optional[set[Cell]]:
    """N3 — the clicked lattice cell AND >= 1 lattice neighbour: the clicked
    cell's region plus its 4-connected lattice neighbours' regions (multi-cell
    claim). None when the click is outside the lattice."""
    lattice = _sc25_lattice(grid)
    if lattice is None:
        return None
    index = lattice["index"]
    x, y = xy
    hit: Optional[Cell] = None
    for key, region in index.items():
        if (y, x) in region["cells"]:
            hit = key
            break
    if hit is None:
        return None
    cells: set[Cell] = set(index[hit]["cells"])
    ri, ci = hit
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        neighbour = index.get((ri + dr, ci + dc))
        if neighbour is not None:
            cells |= set(neighbour["cells"])
    return cells


def _sc25_win_exact_xor(grid: Grid) -> bool:
    """ORACLE win: the lattice's base-parity ON-set EXACTLY equals the preview
    target (grid == base XOR preview)."""
    lattice = _sc25_lattice(grid)
    if lattice is None:
        return False
    target = _sc25_read_target(grid, lattice)
    if target is None:
        return False
    return _sc25_on_set(grid, lattice) == target


def _sc25_win_near_match(grid: Grid) -> bool:
    """N2 win: >= 7 of 9 (>= rows*cols - 2) cells match the target."""
    lattice = _sc25_lattice(grid)
    if lattice is None:
        return False
    target = _sc25_read_target(grid, lattice)
    if target is None:
        return False
    on_set = _sc25_on_set(grid, lattice)
    total = len(lattice["index"])
    matches = sum(1 for k in lattice["index"] if (k in on_set) == (k in target))
    return matches >= total - 2


def _sc25_win_multistate(grid: Grid) -> bool:
    """N1 win: the lattice shows a multi-state colour cycle (> 2 distinct cell
    colours) — the ft09-style multi-state reading, which sc25's binary toggle
    never produces."""
    lattice = _sc25_lattice(grid)
    if lattice is None:
        return False
    colours = {_sc25_cell_colour(grid, region) for region in lattice["index"].values()}
    return len(colours) > 2


def _sc25_win_absolute_preview(grid: Grid) -> bool:
    """N4 win: read the preview as ABSOLUTE colours (no base XOR) — the lattice
    cells that literally show the preview's mark colour must equal the target
    ON-set. Mispredicts whenever the grid renders its ON cells in a colour other
    than the preview's mark colour (i.e. base parity is not the mark colour)."""
    lattice = _sc25_lattice(grid)
    if lattice is None:
        return False
    target = _sc25_read_target(grid, lattice)
    if target is None:
        return False
    mark_colour = _sc25_preview_mark_colour(grid, lattice)
    if mark_colour is None:
        return False
    absolute_on = frozenset(
        k for k, region in lattice["index"].items() if _sc25_cell_colour(grid, region) == mark_colour
    )
    return absolute_on == target


def _sc25_preview_mark_colour(grid: Grid, lattice: dict[str, Any]) -> Optional[int]:
    """The dominant colour of the preview mark regions (a non-grid colour beside
    the grid) — what N4 reads as the absolute ON colour."""
    members = lattice["members"]
    grid_colours = {_sc25_cell_colour(grid, m) for m in members}
    gc0 = min(round(m["centroid"][1]) for m in members)
    gr0 = min(round(m["centroid"][0]) for m in members)
    gr1 = max(round(m["centroid"][0]) for m in members)
    mark_max = lattice["size"]
    marks = [
        r
        for r in _sc25_regions(grid)
        if r["size"] < mark_max
        and r["color"] not in grid_colours
        and r["centroid"][1] < gc0
        and gr0 - _SC25_PREVIEW_ROW_MARGIN <= r["centroid"][0] <= gr1 + _SC25_PREVIEW_ROW_MARGIN
    ]
    if not marks:
        return None
    counts: dict[int, int] = defaultdict(int)
    for r in marks:
        counts[r["color"]] += r["size"]
    return max(counts, key=lambda c: (counts[c], -c))


def sc25_oracle_name() -> str:
    return "binary_flip_xor"


def sc25_templates() -> list[HypothesisTemplate]:
    """The 5 sc25 candidates: oracle ``binary_flip_xor`` + 4 hard negatives."""
    return [
        HypothesisTemplate(
            name="binary_flip_xor",
            description=(
                "ORACLE — a click flips exactly the clicked lattice cell; "
                "win/cast = the grid's base-parity ON-set EXACTLY equals the "
                "displayed preview (base XOR preview)."
            ),
            predict_click=_sc25_click_single,
            predict_win=_sc25_win_exact_xor,
        ),
        HypothesisTemplate(
            name="colour_cycle",
            description=(
                "N1 — same single-cell dynamics; win = the lattice shows a "
                "multi-state colour cycle (> 2 colours), an ft09-style reading "
                "the binary toggle never produces."
            ),
            predict_click=_sc25_click_single,
            predict_win=_sc25_win_multistate,
        ),
        HypothesisTemplate(
            name="near_match_threshold",
            description=(
                "N2 — same single-cell dynamics; win = >= 7 of 9 cells match the "
                "target (the game highlights near-matches, so this over-fires)."
            ),
            predict_click=_sc25_click_single,
            predict_win=_sc25_win_near_match,
        ),
        HypothesisTemplate(
            name="neighbour_stencil",
            description=(
                "N3 — a click changes the cell AND >= 1 lattice neighbour "
                "(multi-cell claim); win = same exact XOR as the oracle."
            ),
            predict_click=_sc25_click_stencil,
            predict_win=_sc25_win_exact_xor,
        ),
        HypothesisTemplate(
            name="absolute_preview",
            description=(
                "N4 — same single-cell dynamics; win = lattice colours equal the "
                "preview colours DIRECTLY (no base-parity XOR), mispredicting "
                "whenever the ON colour is not the preview's mark colour."
            ),
            predict_click=_sc25_click_single,
            predict_win=_sc25_win_absolute_preview,
        ),
    ]


def _sc25_state_signature(frame: Grid) -> Optional[frozenset[Cell]]:
    """A colour-canonical board-STATE signature for sc25: the lattice's
    base-parity ON-set. Two frames with the same ON-set are the same board
    configuration regardless of transient cursor / cast-animation colours, so
    the probe can recognise (and exclude from the negative pool) a cast-state
    frame that is not byte-identical to the selected win frame. Returns ``None``
    when no lattice is present (the frame carries no comparable state). This is
    a perception primitive (ON-set only) — it never references a target, so it
    does NOT encode the oracle's win predicate (``on_set == target``)."""
    lattice = _sc25_lattice(frame)
    if lattice is None:
        return None
    return _sc25_on_set(frame, lattice)


def state_signature_for(game: str) -> Optional[Callable[[Grid], Optional[object]]]:
    """A per-game frame -> hashable board-state signature, or ``None`` when the
    game has no colour-canonical signature (the caller falls back to raw
    byte-equality). Used to exclude genuine cast/win states — repeated under
    transient colours — from the specificity (false-positive) pool."""
    if game.lower() == "sc25":
        return _sc25_state_signature
    return None


def templates_for_game(game: str) -> tuple[list[HypothesisTemplate], str]:
    """The candidate set + oracle name for ``game`` (``"ft09"`` or ``"sc25"``)."""
    key = game.lower()
    if key == "ft09":
        return ft09_templates(), ft09_oracle_name()
    if key == "sc25":
        return sc25_templates(), sc25_oracle_name()
    raise ValueError(f"unknown game {game!r} — expected 'ft09' or 'sc25'")
