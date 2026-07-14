"""Pure state-canonicalization kernels ("state canonicalization variants with
confidence", R56).

Generic hashing/grouping the LLM (or a quarantined public-game adapter
script) composes by supplying frame groups it BELIEVES are the same
underlying state — no game semantics, no automatic key-switching, no
ownership of when a search tool should change canonicalization. This is the
reusable measurement behind two solver-family concerns:

- :mod:`admorphiq.tools.graph_search` — a graph-search tool keys states by a
  hash of the visible frame; different hashing granularities (exact pixel,
  downsampled, histogram, shape-only) trade off precision against robustness
  to incidental noise, and picking the wrong one either fragments one true
  state into many nodes or merges distinct states into one.
- :mod:`admorphiq.tools.dealias` — hidden state the frame doesn't fully
  expose can make two DIFFERENT underlying states hash identically (an
  "inter-collision" in this kernel's vocabulary); that module's fix
  (append recent-action-history to a flagged hash) is a POLICY this kernel
  does not implement — it only MEASURES which canonicalization mode
  collides or fragments, on frame groups the caller has already labeled.

The caller decides what "same state" means (by grouping frames) and which
mode to adopt from the measurement; this module never infers, tracks, or
switches keys on its own.

Frames are 2D grids of ints (or any int-castable value); normalized
internally to a tuple-of-tuples of ints. Stdlib only — no numpy. These
kernels must run inside the sandboxed REPL where only the standard library
and explicitly provided modules exist.
"""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Sequence

Grid = tuple[tuple[int, ...], ...]

# Fixed cost ranking for the "cheapest mode" tie-break in
# choose_canonicalization: lower is cheaper/preferred. histogram is a single
# linear pass with no spatial structure at all (cheapest); shape is a linear
# pass plus a bounding-box crop; downsample is block-pooling over the full
# grid; exact retains the full grid (most expensive to compare/store).
_MODE_COST = {"histogram": 0, "shape": 1, "downsample": 2, "exact": 3}
_ALL_MODES: tuple[str, ...] = ("exact", "downsample", "histogram", "shape")


def _normalize_frame(frame: Sequence[Sequence[object]]) -> Grid:
    """Coerce any nested sequence of int-castable values into a ``Grid``.

    An empty outer sequence, or a sequence of empty rows, normalizes to an
    empty grid (``()``).
    """
    rows = tuple(tuple(int(v) for v in row) for row in frame)
    if not rows or all(len(row) == 0 for row in rows):
        return ()
    return rows


def _mode_color(counts: dict[int, int]) -> int:
    """The most frequent value in ``counts``; ties broken by smallest value."""
    return max(counts.items(), key=lambda kv: (kv[1], -kv[0]))[0]


def _downsample_key(grid: Grid, factor: int) -> Grid:
    """Mode-pool ``grid`` into ``factor``x``factor`` blocks (ragged edges allowed).

    Each block's key value is its most common color, ties broken toward the
    smallest color value for determinism.
    """
    if factor <= 0:
        raise ValueError(f"factor must be positive, got {factor}")
    h = len(grid)
    w = len(grid[0]) if h else 0
    if h == 0 or w == 0:
        return ()
    out: list[tuple[int, ...]] = []
    for i in range(0, h, factor):
        block_rows = grid[i : i + factor]
        row_out: list[int] = []
        for j in range(0, w, factor):
            counts: dict[int, int] = {}
            for r in block_rows:
                for v in r[j : j + factor]:
                    counts[v] = counts.get(v, 0) + 1
            row_out.append(_mode_color(counts))
        out.append(tuple(row_out))
    return tuple(out)


def _histogram_key(grid: Grid) -> tuple[tuple[int, int], ...]:
    """Sorted ``(color, count)`` pairs — a spatially-blind colour census."""
    counts: dict[int, int] = {}
    for row in grid:
        for v in row:
            counts[v] = counts.get(v, 0) + 1
    return tuple(sorted(counts.items()))


def _shape_key(grid: Grid, background: int | None) -> frozenset[tuple[int, int]]:
    """Bounding-box-normalized set of non-background cell positions.

    Colour of the non-background cells is NOT retained — this mode measures
    structural presence/absence only, which is what makes it translation-
    invariant: a sprite shifted anywhere over the same background produces
    the same key. ``background`` defaults to the grid's own most common
    colour (ties broken toward the smallest value) when not given.
    """
    h = len(grid)
    w = len(grid[0]) if h else 0
    if h == 0 or w == 0:
        return frozenset()
    bg = background
    if bg is None:
        counts: dict[int, int] = {}
        for row in grid:
            for v in row:
                counts[v] = counts.get(v, 0) + 1
        bg = _mode_color(counts)
    cells = [(r, c) for r in range(h) for c in range(w) if grid[r][c] != bg]
    if not cells:
        return frozenset()
    r0 = min(r for r, _c in cells)
    c0 = min(c for _r, c in cells)
    return frozenset((r - r0, c - c0) for r, c in cells)


def canonical_key(
    frame: Sequence[Sequence[object]],
    mode: str = "exact",
    factor: int = 4,
    background: int | None = None,
) -> Hashable:
    """A hashable canonicalization of ``frame`` under ``mode``.

    Modes:

    - ``"exact"``: the full grid, unchanged (as a hashable tuple-of-tuples).
    - ``"downsample"``: block-pooled ``factor``x``factor`` mode-colour grid
      (see :func:`_downsample_key`).
    - ``"histogram"``: sorted ``(colour, count)`` tuple — ignores all
      spatial structure.
    - ``"shape"``: frozenset of non-background cell positions, normalized to
      their bounding box's own origin (see :func:`_shape_key`).

    Raises ``ValueError`` for an unrecognized mode.
    """
    grid = _normalize_frame(frame)
    if mode == "exact":
        return grid
    if mode == "downsample":
        return _downsample_key(grid, factor)
    if mode == "histogram":
        return _histogram_key(grid)
    if mode == "shape":
        return _shape_key(grid, background)
    raise ValueError(f"unknown mode: {mode!r}")


def key_table(
    frames: Iterable[Sequence[Sequence[object]]],
    modes: Iterable[str],
    factor: int = 4,
    background: int | None = None,
) -> dict[str, list[Hashable]]:
    """``{mode: [canonical_key(frame, mode), ...]}`` over ``frames``, per mode."""
    frame_list = list(frames)
    mode_list = list(modes)
    return {
        mode: [canonical_key(f, mode=mode, factor=factor, background=background) for f in frame_list]
        for mode in mode_list
    }


def stability_report(
    frame_groups: Sequence[Sequence[Sequence[Sequence[object]]]],
    modes: Iterable[str] = _ALL_MODES,
    factor: int = 4,
    background: int | None = None,
) -> dict[str, dict[str, object]]:
    """Per-mode measurement of over-splitting vs over-merging on labeled groups.

    ``frame_groups`` is a list of lists of frames; each inner list is frames
    the CALLER asserts are the same underlying state, and different inner
    lists are asserted to be different states — this kernel never infers
    that grouping itself. For each mode, returns::

        {
            "intra_consistent": bool,   # every group maps to exactly one key
            "intra_splits": int,        # sum of (distinct keys in group - 1),
                                         # per group, over 0 — over-splitting
            "inter_collisions": int,    # sum of (groups sharing a key - 1),
                                         # per key, over 0 — over-merging
            "distinct_keys": int,       # total distinct keys used, all groups
        }

    ``intra_splits`` and ``inter_collisions`` are symmetric excess-counts:
    the former sums, per group, how many EXTRA keys beyond one that group
    produced (fragmentation); the latter sums, per key, how many EXTRA
    groups beyond one shared that key (aliasing/collision) — mirroring each
    other's accounting so a mode that neither fragments nor collides scores
    0 on both.
    """
    mode_list = list(modes)
    report: dict[str, dict[str, object]] = {}
    for mode in mode_list:
        group_keysets: list[set[Hashable]] = []
        key_to_groups: dict[Hashable, set[int]] = {}
        intra_splits = 0
        for gi, group in enumerate(frame_groups):
            keys = {canonical_key(f, mode=mode, factor=factor, background=background) for f in group}
            group_keysets.append(keys)
            intra_splits += max(0, len(keys) - 1)
            for k in keys:
                key_to_groups.setdefault(k, set()).add(gi)
        inter_collisions = sum(max(0, len(gis) - 1) for gis in key_to_groups.values())
        report[mode] = {
            "intra_consistent": all(len(ks) <= 1 for ks in group_keysets),
            "intra_splits": intra_splits,
            "inter_collisions": inter_collisions,
            "distinct_keys": len(key_to_groups),
        }
    return report


def choose_canonicalization(
    frame_groups: Sequence[Sequence[Sequence[Sequence[object]]]],
    modes: Iterable[str] = _ALL_MODES,
    factor: int = 4,
    background: int | None = None,
) -> dict[str, object]:
    """Pick the best canonicalization mode for ``frame_groups``.

    Priority: fewest ``inter_collisions`` first (zero is ideal — never merge
    distinct states), then fewest ``intra_splits`` (don't fragment a single
    state either), then the fixed cost ranking ``histogram < shape <
    downsample < exact`` as a final, fully deterministic tie-break (so the
    result never depends on ``modes``' iteration order). Returns ``{"mode":
    winning_mode_name, "report": full_stability_report}`` — the full
    per-mode report is included so the caller can see runner-up modes too,
    not just the winner's numbers.
    """
    mode_list = list(modes)
    report = stability_report(frame_groups, modes=mode_list, factor=factor, background=background)

    def sort_key(mode: str) -> tuple[int, int, int]:
        r = report[mode]
        return (r["inter_collisions"], r["intra_splits"], _MODE_COST.get(mode, len(_MODE_COST)))

    best_mode = min(mode_list, key=sort_key)
    return {"mode": best_mode, "report": report}
