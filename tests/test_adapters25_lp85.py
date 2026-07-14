"""Tests for the LP85 rare-colour click adapter (R56 divergence-first fix,
2026-07-15) -- ``_region_candidates``'s per-PIXEL enumeration. See that
module's docstring for the gold-trace divergence finding this fix is based
on: the winning pixel belongs to a rare-coloured region whose CENTROID is a
different, non-winning pixel, and clicking other pixels within the SAME
region has independently observable (but non-winning) effects -- so a
region must be probed pixel-by-pixel, not centroid-only.
"""

from __future__ import annotations

from collections import deque
from types import SimpleNamespace

from admorphiq.adapters25.lp85 import Adapter, _candidates_with_region, _region_candidates, _round_robin_queue


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


def test_round_robin_queue_visits_every_regions_first_pixel_before_any_second_pixel():
    """Purpose: regression pin for the round-robin base ordering (R56, this
    revision) -- one untried pixel per region per round, region-rarity
    order within a round, deepest rounds last. This is what makes
    promotion (see below) meaningful: without round-robin, a single
    region's own pixels are already fully consecutive by construction (see
    ``_candidates_with_region``), so "promote the rest of this region"
    would be a no-op relative to that baseline. Round-robin genuinely
    interleaves regions, matching gold's own breadth-before-depth pattern
    (dozens of unrelated regions touched once each before the productive
    one is ever reached) cheaply -- reaching every region's OWN first
    pixel after one pass over every rarer-or-tied region, not after
    exhausting their full pixel counts.
    Expected feedback: failure means the base queue is back to one region
    fully before the next, which would make a later fix's "before
    continuing the outer sweep" framing meaningless (there would be
    nothing to skip past)."""
    grid = _blank_grid(20, bg=0)
    rare_cells = [(1, 1), (1, 2)]  # colour 9, 2 pixels -- rarer, first in region order
    common_cells = [(5, 5), (5, 6), (5, 7)]  # colour 3, 3 pixels -- less rare
    _stamp(grid, rare_cells, 9)
    _stamp(grid, common_cells, 3)
    grid = tuple(tuple(row) for row in grid)

    candidates, region_of = _candidates_with_region(grid)
    queue = list(_round_robin_queue(candidates, region_of))

    # Round 0: rare region's 1st pixel, then common region's 1st pixel.
    assert queue[0] == rare_cells[0]
    assert queue[1] == common_cells[0]
    # Round 1: rare region's 2nd (last) pixel, then common region's 2nd.
    assert queue[2] == rare_cells[1]
    assert queue[3] == common_cells[1]
    # Round 2: only the common region has a 3rd pixel left.
    assert queue[4] == common_cells[2]
    assert len(queue) == 5


def test_promote_region_moves_the_same_regions_untried_pixels_to_the_front():
    """Purpose: regression pin for the local-focus sweep (R56, this
    revision) -- once a pixel shows a visible reaction, every OTHER
    untried pixel belonging to the SAME region must move to the FRONT of
    the probe queue, ahead of whatever unrelated candidates the outer
    rarity sweep had queued next, so a responsive region finishes before
    the sweep resumes elsewhere.
    Expected feedback: failure means a responsive region's own remaining
    pixels stay buried behind unrelated candidates, reproducing gold's own
    breadth-first inefficiency (69 actions vs a 17-action human baseline)
    this fix is meant to beat."""
    adapter = Adapter()
    region_a = (0, 0, 0, 2)
    region_b = (5, 5, 5, 6)
    a1, a2, a3 = (0, 0), (0, 1), (0, 2)
    b1, b2 = (5, 5), (5, 6)
    adapter._region_of = {a1: region_a, a2: region_a, a3: region_a, b1: region_b, b2: region_b}
    # Outer sweep order interleaves B between A's own remaining pixels --
    # the exact shape a rarity tie-break could produce.
    adapter._queue = deque([a2, b1, a3, b2])

    adapter._promote_region(a1)  # a1 (already clicked) belongs to region A

    assert list(adapter._queue) == [a2, a3, b1, b2]


def test_promote_region_is_a_no_op_for_an_unknown_or_exhausted_region():
    """Purpose: promoting a point with no region membership (never a
    candidate at all) or whose region has no OTHER untried pixels left
    must leave the queue untouched -- not raise, not reorder spuriously.
    Expected feedback: failure means the promotion step corrupts the queue
    on a harmless edge case, risking a crash or a lost candidate live."""
    adapter = Adapter()
    b1, b2 = (5, 5), (5, 6)
    adapter._region_of = {b1: (5, 5, 5, 6), b2: (5, 5, 5, 6)}
    adapter._queue = deque([b1, b2])

    adapter._promote_region((99, 99))  # never a candidate at all
    assert list(adapter._queue) == [b1, b2]

    adapter._region_of[(1, 1)] = (1, 1, 1, 1)  # its own region has no OTHER pixels
    adapter._promote_region((1, 1))
    assert list(adapter._queue) == [b1, b2]


def _make_frame(grid: list[list[int]], levels_completed: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        frame=[[list(row) for row in grid]],
        state=SimpleNamespace(name="NOT_FINISHED"),
        levels_completed=levels_completed,
    )


def test_adapter_finishes_a_responsive_region_before_returning_to_the_outer_sweep():
    """Purpose: end-to-end pin for the local-focus sweep through the real
    choose_action loop -- colour 9 (2 pixels, rarer) and colour 3 (3
    pixels) round-robin-interleave under the base ordering (colour9's 2nd
    pixel would otherwise land AFTER colour3's 1st, per the round-robin
    test above), but once colour9's first pixel reacts, its own remaining
    pixel must be promoted immediately, landing consecutively right after
    the reacting click rather than waiting for its round-robin turn.
    Expected feedback: failure means the live adapter reproduces gold's
    own breadth-first waste instead of the local-focus improvement this
    fix targets."""
    size = 20
    bg = 0

    def build(reacted: set[tuple[int, int]]) -> list[list[int]]:
        g = [[bg] * size for _ in range(size)]
        for r, c in [(1, 1), (1, 2)]:  # colour 9, 2 pixels -- responsive region
            g[r][c] = 9
        for r, c in [(5, 5), (5, 6), (5, 7)]:  # colour 3, 3 pixels -- inert region
            g[r][c] = 3
        # A responsive click leaves a visible mark elsewhere on the board
        # (a HUD-style side effect), mirroring the measured LP85 fill-bar.
        if reacted:
            g[10][10] = 8
        return g

    adapter = Adapter()
    reacted_clicks: set[tuple[int, int]] = set()
    grid = build(reacted_clicks)
    obs = _make_frame(grid)
    clicked_order: list[tuple[int, int]] = []

    # Exactly 5 candidates exist on this board; stop before the adapter
    # would enter its second-pass recycle tier (which may legitimately
    # re-click a responsive point again -- a different mechanism, not the
    # one under test here).
    for _ in range(5):
        action = adapter.choose_action([], obs)
        point = (action.action_data.y, action.action_data.x)
        clicked_order.append(point)
        if point in ((1, 1), (1, 2)):
            reacted_clicks.add(point)
        grid = build(reacted_clicks)
        obs = _make_frame(grid)

    # The two colour-9 pixels must appear consecutively (no colour-3 pixel
    # wedged between them) once the first one reacts.
    idx9 = [i for i, p in enumerate(clicked_order) if p in ((1, 1), (1, 2))]
    assert idx9 == [0, 1]
