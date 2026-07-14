"""Tests for the LP85 rare-colour click adapter (R56 divergence-first fix,
2026-07-15) -- ``_region_candidates``'s per-PIXEL enumeration. See that
module's docstring for the gold-trace divergence finding this fix is based
on: the winning pixel belongs to a rare-coloured region whose CENTROID is a
different, non-winning pixel, and clicking other pixels within the SAME
region has independently observable (but non-winning) effects -- so a
region must be probed pixel-by-pixel, not centroid-only.
"""

from __future__ import annotations

from admorphiq.adapters25.lp85 import _region_candidates


def _blank_grid(size: int, bg: int) -> list[list[int]]:
    return [[bg] * size for _ in range(size)]


def _stamp(grid: list[list[int]], cells: list[tuple[int, int]], colour: int) -> None:
    for r, c in cells:
        grid[r][c] = colour


def test_region_candidates_enumerates_every_pixel_not_just_a_centroid():
    """Purpose: regression pin for the divergence-first fix -- a single
    connected region must contribute ALL of its own pixels as distinct
    candidates, not one centroid point. This is the exact shape of the
    measured LP85 bug: the true win pixel was a DIFFERENT pixel than the
    region's own centroid, within the same 40-pixel colour-8 blob.
    Expected feedback: failure means the adapter is back to trying only one
    point per region, reproducing the 0/8 divergence this fix closed."""
    grid = _blank_grid(20, bg=0)
    # A small L-shaped region of colour 5 (not centroid-symmetric, so its
    # OWN centroid rounds to a cell that ISN'T even part of the region --
    # exactly the class of mismatch the gold trace showed).
    cells = [(2, 2), (2, 3), (2, 4), (3, 2)]
    _stamp(grid, cells, 5)
    grid = tuple(tuple(row) for row in grid)

    cands = _region_candidates(grid)
    assert set(cands) == set(cells)
    assert len(cands) == len(cells)  # every pixel present exactly once


def test_region_candidates_orders_rarest_colour_first_then_position():
    """Purpose: pin the ordering contract -- candidates are grouped by the
    colour's OWN total pixel count (ascending, rarest first) across every
    qualifying region, and within one colour's pixels, by position
    (row, col) ascending -- matching the retired click_rare strategy's own
    raster-order pixel enumeration within a colour.
    Expected feedback: failure means a common colour's pixels could be
    tried before a rarer colour's, wasting budget on the less-likely
    target class before the more-likely one."""
    grid = _blank_grid(20, bg=0)
    rare_cells = [(1, 1), (1, 2)]  # colour 9, 2 pixels total -- rarer
    common_cells = [(5, 5), (5, 6), (5, 7)]  # colour 3, 3 pixels total -- less rare
    _stamp(grid, rare_cells, 9)
    _stamp(grid, common_cells, 3)
    grid = tuple(tuple(row) for row in grid)

    cands = _region_candidates(grid)
    # All rare-colour pixels must precede all common-colour pixels.
    rare_idx = [cands.index(c) for c in rare_cells]
    common_idx = [cands.index(c) for c in common_cells]
    assert max(rare_idx) < min(common_idx)
    # Within the rare colour, pixels are position-ordered.
    assert cands[:2] == sorted(rare_cells)


def test_region_candidates_excludes_chrome_sized_regions():
    """Purpose: a region spanning a large fraction of the frame (a
    backdrop/panel) must still be excluded entirely -- per-pixel
    enumeration must not turn chrome into thousands of candidates.
    Expected feedback: failure means a board-spanning panel would flood
    the candidate list with useless clicks, the exact waste the chrome
    exclusion threshold exists to prevent."""
    size = 20
    grid = _blank_grid(size, bg=0)
    # A panel covering half the frame (10 of 20 rows) -- comfortably over
    # the 0.15-fraction chrome threshold.
    for r in range(10):
        for c in range(size):
            grid[r][c] = 7
    small_cells = [(15, 15), (15, 16)]
    _stamp(grid, small_cells, 5)
    grid = tuple(tuple(row) for row in grid)

    cands = _region_candidates(grid)
    assert set(cands) == set(small_cells)


def test_region_candidates_returns_empty_for_a_blank_grid():
    """Purpose: a grid with nothing but background must report no
    candidates at all, not raise or fabricate a click target.
    Expected feedback: failure means the adapter would crash or click a
    bogus point on a level genuinely without any candidate region."""
    grid = tuple(tuple(0 for _ in range(10)) for _ in range(10))
    assert _region_candidates(grid) == []
    assert _region_candidates(()) == []
