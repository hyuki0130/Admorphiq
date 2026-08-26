"""Board rendering-scale kernels: read a frame's cell size, then read it in cells.

A frame is PIXELS; a board is CELLS. Every game that renders one board cell as an
s x s block of pixels needs the same three steps — infer s, sample one pixel per
cell, segment 4-connected components of one appearance — and getting the first of
them wrong makes everything downstream wrong in a way that looks like a modelling
error rather than a rendering one.

These moved here from ``admorphiq.hypothesis_select.grounding_flow``, unchanged,
so there is ONE implementation. The quarantined ``adapters25`` packages may import
``admorphiq.kernels`` but not ``hypothesis_select``, and a second copy written to
satisfy that lint would be a second copy to get the measured traps wrong in.

The traps are recorded in :func:`infer_board_scale`'s own docstring; each cost a
measurement to find.
"""

from __future__ import annotations

from typing import Optional

Cell = tuple[int, int]
Grid = tuple[tuple[int, ...], ...]

__all__ = ["cellify", "colour_regions", "infer_board_scale"]


def infer_board_scale(grid: Grid) -> Optional[int]:
    """The pixel side of one board cell, read off the frame itself: the largest
    block size whose blocks are uniform. Frame-only and probe-free.

    A status bar drawn over the outermost pixel row or two is a rendering overlay
    rather than board structure, so uniformity is tested with a margin of 0, then
    1, then 2 pixels excluded from every edge. The margin is deliberately TINY: an
    earlier version exempted whole border BLOCKS and happily accepted a scale
    twice too large, because real board content near an edge was excused as
    overlay.

    A featureless frame is uniform at every scale, so a candidate must also
    resolve at least two distinct cell values; otherwise this reports nothing and
    the caller re-infers on a later, more informative frame.
    """
    n = len(grid)
    if n == 0 or len(grid[0]) != n:
        return None
    for s in range(n // 4, 0, -1):
        if n % s:
            continue
        span = n // s
        for margin in (0, 1, 2):
            if margin * 2 >= n:
                break
            uniform = True
            for by in range(span):
                for bx in range(span):
                    seen = {
                        grid[y][x]
                        for y in range(by * s, by * s + s)
                        for x in range(bx * s, bx * s + s)
                        if margin <= y < n - margin and margin <= x < n - margin
                    }
                    if len(seen) > 1:
                        uniform = False
                        break
                if not uniform:
                    break
            if uniform:
                break
        if not uniform:
            continue
        sampled = {
            grid[r * s + s // 2][c * s + s // 2] for r in range(span) for c in range(span)
        }
        if len(sampled) >= 2:
            return s
    return None


def cellify(grid: Grid, scale: int) -> dict[Cell, int]:
    """One value per board cell, sampled at each cell's centre pixel."""
    n = len(grid) // scale
    return {
        (r, c): grid[r * scale + scale // 2][c * scale + scale // 2]
        for r in range(n)
        for c in range(n)
    }


def colour_regions(cells: dict[Cell, int], colour: int) -> list[frozenset[Cell]]:
    """4-connected components of one appearance. Safe HERE because callers only
    segment the SELECTED appearance (unique by construction) or a colour already
    known to be a single entity."""
    todo = {c for c, v in cells.items() if v == colour}
    out: list[frozenset[Cell]] = []
    while todo:
        seed = todo.pop()
        comp = {seed}
        stack = [seed]
        while stack:
            r, c = stack.pop()
            for n in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if n in todo:
                    todo.remove(n)
                    comp.add(n)
                    stack.append(n)
        out.append(frozenset(comp))
    return sorted(out, key=min)
