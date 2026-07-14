"""Pure 1D/sequence kernels: background-gap window segmentation, per-window
colour majority/minority, generic size-jump clustering, and deterministic
greedy token-string parsing.

Distinct from :mod:`admorphiq.kernels.regions` (2D same-colour connected
components) and :mod:`admorphiq.kernels.rewrite` (branching BFS token-rewrite
search) — these are 1D/sequence primitives extracted from the TR87-class
"a row of the board is a strip of fixed-width glyph cells separated by
background gaps" structure (see
``docs/tr87_frame_only_grammar_design_20260715.md`` for the measurement that
motivated this module: naive same-colour connected-component segmentation
FRAGMENTS a two-colour glyph cell — one glyph's own "ink" pixels are not
guaranteed 4-connected — so isolating "one cell" needs a positional gap scan,
not a colour flood fill). No game semantics travel with the math: no
"glyph", "dial", "bar", or any other TR87-specific vocabulary appears below,
only bands/windows/tokens/rules.

Stdlib only — no numpy. These kernels must run inside the sandboxed REPL
where only the standard library and explicitly provided modules exist.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any

from admorphiq.kernels._common import normalize_frame as _normalize_frame

Cell = tuple[int, int]
Window = dict[str, Any]
Rule = tuple[Sequence[Any], Sequence[Any]]


def _resolve_background_set(grid: Sequence[Sequence[int]], background: int | Iterable[int] | None) -> set[int]:
    if background is None:
        counts = Counter(v for row in grid for v in row)
        return {counts.most_common(1)[0][0]}
    if isinstance(background, int):
        return {background}
    return {int(b) for b in background}


def gap_windows(band: Sequence[Sequence[int]], background: int | Iterable[int] | None = None) -> dict[str, Any]:
    """Segment a row-band into content windows separated by full-background column runs.

    ``band`` is a 2D slice (a tuple of rows, all the same width — e.g. the
    handful of rows spanning one horizontal strip of a frame). A column
    belongs to a gap only when EVERY row of ``band`` is in ``background`` at
    that column; a column with content in ANY row starts/extends a window —
    this is why a two-colour cell (fill + a second "ink" colour) stays one
    window even though same-colour connected-component segmentation would
    fragment it. ``background`` is a single colour, any iterable of colours,
    or (default) auto-derived as the single most-common colour across
    ``band`` — matching :mod:`admorphiq.kernels.regions`'s
    ``background: int | Iterable[int] | None`` convention.

    Returns ``{"windows": [...], "gaps": [...]}``. Each window is
    ``{"start": col, "end": col, "cells": frozenset[(row, col)]}`` — note
    ``end`` is EXCLUSIVE (half-open, Python-slice-style: ``band[r][start:end]``
    is the window's own row slice) — a deliberate departure from the rest of
    this kernel library's inclusive-bbox convention, chosen because a
    window's natural consumer is a slice/range, not a static rectangle;
    ``cells`` holds only the non-background cells within the window (its
    full column span may include background cells in some rows, since a
    column only needs ONE non-background row to join the window). ``gaps``
    has ``len(windows) - 1`` entries: the background-only column count
    strictly between consecutive windows. An all-background (or empty)
    ``band`` returns ``{"windows": [], "gaps": []}``.
    """
    grid = _normalize_frame(band)
    if not grid or not grid[0]:
        return {"windows": [], "gaps": []}
    bg = _resolve_background_set(grid, background)
    h, w = len(grid), len(grid[0])

    spans: list[tuple[int, int]] = []
    in_window = False
    start = 0
    for c in range(w):
        has_content = any(grid[r][c] not in bg for r in range(h))
        if has_content and not in_window:
            in_window, start = True, c
        elif not has_content and in_window:
            spans.append((start, c))
            in_window = False
    if in_window:
        spans.append((start, w))

    windows: list[Window] = []
    for c0, c1 in spans:
        cells = frozenset((r, c) for r in range(h) for c in range(c0, c1) if grid[r][c] not in bg)
        windows.append({"start": c0, "end": c1, "cells": cells})
    gaps = [windows[i + 1]["start"] - windows[i]["end"] for i in range(len(windows) - 1)]
    return {"windows": windows, "gaps": gaps}


def window_majority_color(
    band: Sequence[Sequence[int]], window: Window, background: int | None = None
) -> dict[str, Any]:
    """The most/second-most common colour within one ``gap_windows``-shaped window.

    Reads ``window["start"]``/``window["end"]`` (half-open, as produced by
    :func:`gap_windows`) and scans every cell of ``band`` in that column
    span (ALL rows, not just ``window["cells"]``'s non-background subset —
    this is what lets a caller ask "what's this window's OWN fill colour"
    even including background rows within the span). When ``background`` is
    given, cells equal to it are excluded from the count first (so a
    window's majority reflects its CONTENT structure, not a background
    colour that happens to also appear in some row of the span).

    Returns ``{"majority": colour, "minority": colour | None, "counts":
    {colour: count, ...}}``. ``minority`` is the second-most-common colour,
    or ``None`` when the (post-exclusion) window holds only one colour (or
    none at all, in which case ``majority`` is also ``None``). Tie rule:
    when two or more colours share the top (or second) count, the one
    encountered FIRST in row-major (top-to-bottom, left-to-right) scan
    order wins — ``collections.Counter.most_common()`` is a stable sort
    over a dict that preserves first-insertion order, so this falls out of
    the scan order directly rather than needing an explicit tie-break rule.
    """
    grid = _normalize_frame(band)
    start, end = window["start"], window["end"]
    counts = Counter(
        grid[r][c]
        for r in range(len(grid))
        for c in range(start, end)
        if background is None or grid[r][c] != background
    )
    if not counts:
        return {"majority": None, "minority": None, "counts": {}}
    ranked = counts.most_common()
    majority = ranked[0][0]
    minority = ranked[1][0] if len(ranked) > 1 else None
    return {"majority": majority, "minority": minority, "counts": dict(counts)}


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


def greedy_parse(tokens: Sequence[Any], rules: Sequence[Rule], direction: str = "ltr") -> dict[str, Any] | None:
    """Deterministic single-pass greedy token-string parse: NOT a search.

    Scans ``tokens`` from one end (``direction="ltr"`` from the left,
    ``"rtl"`` from the right), and at each position tries every rule *in
    list order*, applying the FIRST whose LHS matches a run of tokens
    starting there — no backtracking, and no consideration of any OTHER
    rule that might also have matched. On a match, the position advances
    past the consumed LHS run (not the RHS — the parse always consumes
    ``tokens``, the RHS only contributes to the OUTPUT). If NO rule matches
    at some position, the entire parse FAILS and this returns ``None`` —
    there is no partial-credit / pass-through-unmatched-tokens mode; every
    token must be covered by some rule's LHS.

    This is deliberately much simpler than
    :func:`admorphiq.kernels.rewrite.derive_rewrites` /
    :func:`admorphiq.kernels.rewrite.find_derivation`, which BFS-search over
    every possible sequence of rule applications (branching at every
    matching position and rule choice) to find ANY reachable derivation —
    genuinely necessary when multiple derivations may exist and a specific
    target must be found among them. ``greedy_parse`` makes exactly one
    commitment per position and never reconsiders it, which is the right
    (and much cheaper) tool when the task's own rule is itself a
    committed, non-backtracking left-to-right tiling (e.g. TR87's win-check
    parses its target row this way — see the design doc referenced in this
    module's docstring). When a greedy tiling genuinely doesn't exist for
    some input even though a valid (non-greedy, differently-ordered)
    derivation does, ``greedy_parse`` returns ``None`` where
    ``find_derivation`` would still find it — callers that need a fallback
    for that gap should reach for ``find_derivation``, not assume
    ``greedy_parse``'s ``None`` means truly unparseable under the rule set.

    Returns ``{"result": tokens, "steps": [{"rule": idx, "position": p,
    "before": lhs_tokens, "after": rhs_tokens}, ...]}`` on success —
    ``result`` is the concatenation of every matched rule's RHS, in match
    order; ``position`` is always reported in ORIGINAL (``ltr``) token
    coordinates regardless of ``direction``, so steps from an ``"rtl"``
    parse are directly comparable to an ``"ltr"`` one. An empty ``tokens``
    trivially succeeds with an empty result and no steps, regardless of
    ``rules``. Raises ``ValueError`` for an unknown ``direction`` or a rule
    with an empty LHS (an empty LHS can never advance the scan position,
    which would either loop forever or make "first match wins" ill-defined
    at every position simultaneously — same rejection
    :func:`admorphiq.kernels.rewrite.derive_rewrites` applies).
    """
    if direction not in ("ltr", "rtl"):
        raise ValueError(f"direction must be 'ltr' or 'rtl', got {direction!r}")
    normalized: list[tuple[tuple[Any, ...], tuple[Any, ...]]] = []
    for i, (lhs, rhs) in enumerate(rules):
        lhs_t, rhs_t = tuple(lhs), tuple(rhs)
        if not lhs_t:
            raise ValueError(f"rule {i}: empty LHS is not a valid production")
        normalized.append((lhs_t, rhs_t))

    tokens_t = tuple(tokens)
    if direction == "ltr":
        return _greedy_parse_ltr(tokens_t, normalized)

    n = len(tokens_t)
    rev_tokens = tuple(reversed(tokens_t))
    rev_rules = [(tuple(reversed(lhs)), tuple(reversed(rhs))) for lhs, rhs in normalized]
    parsed = _greedy_parse_ltr(rev_tokens, rev_rules)
    if parsed is None:
        return None
    steps = []
    for step in reversed(parsed["steps"]):
        lhs_len = len(step["before"])
        orig_pos = n - step["position"] - lhs_len
        steps.append(
            {
                "rule": step["rule"],
                "position": orig_pos,
                "before": tuple(reversed(step["before"])),
                "after": tuple(reversed(step["after"])),
            }
        )
    return {"result": tuple(reversed(parsed["result"])), "steps": steps}


def _greedy_parse_ltr(
    tokens: tuple[Any, ...], rules: list[tuple[tuple[Any, ...], tuple[Any, ...]]]
) -> dict[str, Any] | None:
    pos = 0
    n = len(tokens)
    steps: list[dict[str, Any]] = []
    result: list[Any] = []
    while pos < n:
        matched = None
        for idx, (lhs, rhs) in enumerate(rules):
            m = len(lhs)
            if tokens[pos : pos + m] == lhs:
                matched = (idx, lhs, rhs)
                break
        if matched is None:
            return None
        idx, lhs, rhs = matched
        steps.append({"rule": idx, "position": pos, "before": lhs, "after": rhs})
        result.extend(rhs)
        pos += len(lhs)
    return {"result": tuple(result), "steps": steps}
