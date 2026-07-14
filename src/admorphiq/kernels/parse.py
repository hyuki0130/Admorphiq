"""Pure 1D/structural measurement kernels: axis-neutral occupied-run
projection, a generic colour-value histogram, and numeric ratio-jump
clustering.

Distinct from :mod:`admorphiq.kernels.regions` (2D same-colour connected
components) — these operate on a single axis (a row or column projection of
a 2D grid) or on a plain sequence of values, with no notion of "cell",
"glyph", or "token" baked into the primitives themselves; the caller decides
what a run or a colour count MEANS. Extracted while scoping TR87's rule-table
extraction (``docs/tr87_frame_only_grammar_design_20260715.md``) — same-colour
connected-component segmentation FRAGMENTS a two-colour (fill+ink) region,
since one colour's own pixels need not be 4-connected, so isolating "one
occupied run" needs a positional gap scan, not a colour flood fill. That
extraction ALSO revealed (Codex review, ``docs/r56_codex_tr87_review_20260715.md``,
and the level-1 capture in the same design doc) that a background-only gap
scan cannot, by itself, tell "one wide occupied run" apart from "several
adjacent runs with no gap between them" — a caller that needs that
distinction supplies additional structure (a known single-run pitch,
independent tokenization evidence, etc.); this module only measures what a
background-gap projection can measure, no more.

Stdlib only — no numpy. These kernels must run inside the sandboxed REPL
where only the standard library and explicitly provided modules exist.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any

from admorphiq.kernels._common import normalize_frame as _normalize_frame

Cell = tuple[int, int]
Bbox = tuple[int, int, int, int]
Run = dict[str, Any]


def _resolve_background_set(grid: Sequence[Sequence[int]], background: int | Iterable[int] | None) -> set[int]:
    if background is None:
        counts = Counter(v for row in grid for v in row)
        return {counts.most_common(1)[0][0]}
    if isinstance(background, int):
        return {background}
    return {int(b) for b in background}


def occupied_runs(
    frame: Sequence[Sequence[int]],
    axis: str = "col",
    bbox: Bbox | None = None,
    background: int | Iterable[int] | None = None,
) -> dict[str, Any]:
    """Project ``frame`` along ``axis`` and segment it into occupied runs separated by full-background gaps.

    ``axis="col"`` scans columns: a column is a GAP only when every row in
    ``bbox``'s row range is in ``background`` at that column; a column with
    non-background content in ANY of those rows extends/starts a run — this
    is why a two-colour region (e.g. a fill colour plus a second "content"
    colour) stays one run even though same-colour connected-component
    segmentation would fragment it. ``axis="row"`` is the transpose: scans
    rows, gap/content determined across ``bbox``'s column range. ``bbox`` is
    the inclusive ``(row0, col0, row1, col1)`` restricting the scan (default:
    the whole frame). ``background`` is a single colour, any iterable of
    colours, or (default) auto-derived as the single most-common colour
    within ``bbox`` — matching :mod:`admorphiq.kernels.regions`'s
    ``background: int | Iterable[int] | None`` convention.

    Returns ``{"runs": [...], "gaps": [...]}``. Each run is ``{"start": p,
    "end": p, "cells": frozenset[(row, col)]}`` where ``p`` is a position
    along ``axis`` (a column index for ``axis="col"``, a row index for
    ``axis="row"``) and ``end`` is EXCLUSIVE (half-open, Python-slice-style)
    — a deliberate departure from the rest of this kernel library's
    inclusive-bbox convention, chosen because a run's natural consumer is a
    slice/range, not a static rectangle; ``cells`` holds only the
    non-background cells within the run's extent (its full cross-axis span
    may include background cells on some lines, since one line only needs
    ONE non-background cell to keep the run alive). ``gaps`` has
    ``len(runs) - 1`` entries: the background-only count strictly between
    consecutive runs, in the same units as ``start``/``end``. An
    all-background (or empty) region returns ``{"runs": [], "gaps": []}``.

    This function does NOT know, and cannot tell you, whether a single wide
    run is genuinely one occupied thing or several adjacent things rendered
    with no gap between them — see this module's docstring.
    """
    if axis not in ("row", "col"):
        raise ValueError(f"axis must be 'row' or 'col', got {axis!r}")
    grid = _normalize_frame(frame)
    if not grid or not grid[0]:
        return {"runs": [], "gaps": []}
    h, w = len(grid), len(grid[0])
    r0, c0, r1, c1 = (0, 0, h - 1, w - 1) if bbox is None else bbox
    bg = _resolve_background_set(
        [row[c0 : c1 + 1] for row in grid[r0 : r1 + 1]], background
    )

    if axis == "col":
        primary = range(c0, c1 + 1)
        cross = range(r0, r1 + 1)

        def has_content(p: int) -> bool:
            return any(grid[q][p] not in bg for q in cross)

        def cell(p: int, q: int) -> Cell:
            return (q, p)
    else:
        primary = range(r0, r1 + 1)
        cross = range(c0, c1 + 1)

        def has_content(p: int) -> bool:
            return any(grid[p][q] not in bg for q in cross)

        def cell(p: int, q: int) -> Cell:
            return (p, q)

    spans: list[tuple[int, int]] = []
    in_run = False
    start = 0
    for p in primary:
        occ = has_content(p)
        if occ and not in_run:
            in_run, start = True, p
        elif not occ and in_run:
            spans.append((start, p))
            in_run = False
    if in_run:
        spans.append((start, primary.stop))

    runs: list[Run] = []
    for s, e in spans:
        cells = frozenset(
            cell(p, q) for p in range(s, e) for q in cross if grid[cell(p, q)[0]][cell(p, q)[1]] not in bg
        )
        runs.append({"start": s, "end": e, "cells": cells})
    gaps = [runs[i + 1]["start"] - runs[i]["end"] for i in range(len(runs) - 1)]
    return {"runs": runs, "gaps": gaps}


def color_mode(values: Iterable[Any], k: int = 2) -> list[dict[str, Any]]:
    """The top-``k`` most frequent values in ``values``, ranked descending by count.

    A plain frequency histogram over ANY iterable of hashable values — not
    specific to colours, not specific to 2D structure, and with no
    "background"/"ink"/"majority-is-fill" semantics baked in: the caller
    decides what ``values`` to feed in (every cell of a band, only the cells
    in one :func:`occupied_runs` result's ``"cells"``, colours with some
    known background value pre-filtered out, etc.) and what the ranked
    result MEANS for their own use case.

    Returns up to ``k`` entries ``{"color": v, "count": n}`` (fewer if fewer
    than ``k`` distinct values occur; ``[]`` for an empty ``values``), ordered
    by count descending. Tie rule: values tied on count are ordered by which
    was encountered FIRST while consuming ``values`` — ``collections.Counter``
    preserves first-insertion order for its keys and ``most_common()`` is a
    stable sort over that order, so this falls out directly rather than
    needing an explicit tie-break rule.
    """
    counts = Counter(values)
    ranked = counts.most_common(k)
    return [{"color": v, "count": n} for v, n in ranked]


def cluster_widths(widths: Sequence[int | float], ratio: float = 1.5) -> list[list[int]]:
    """Group indices of ``widths`` into size classes by consecutive-value jumps.

    Sorts indices by ``widths`` value ascending, then starts a new cluster
    whenever the next value divided by the previous exceeds ``ratio`` — the
    same "measured size outlier" technique :mod:`admorphiq.delivery` uses to
    split items from target zones (originally landed as
    :func:`admorphiq.kernels.regions.size_clusters`, generalised here to any
    numeric sequence — gap widths, region sizes, or anything else with the
    same "consecutive ratio jump = new class" structure; ``size_clusters``
    now delegates to this function, see its own docstring). A zero-valued
    element never triggers a new-cluster split against it as the PREVIOUS
    element (division-by-zero avoidance — a zero-width gap/size is treated
    as "same class as whatever precedes it," preserving
    ``size_clusters``'s original behaviour exactly). Returns indices (not
    the values themselves) grouped in ascending-value order, each group in
    original relative index order among ties (stable sort).
    """
    order = sorted(range(len(widths)), key=lambda i: widths[i])
    clusters: list[list[int]] = []
    current: list[int] = []
    prev: int | float | None = None
    for i in order:
        value = widths[i]
        if current and prev and (value / prev) > ratio:
            clusters.append(current)
            current = []
        current.append(i)
        prev = value
    if current:
        clusters.append(current)
    return clusters
