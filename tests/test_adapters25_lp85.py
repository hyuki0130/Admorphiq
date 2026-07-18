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
from math import isqrt
from types import SimpleNamespace

from admorphiq.adapters25.lp85 import (
    Adapter,
    _candidates_with_region,
    _cluster_frame_centres,
    _detect_dests,
    _detect_marker_colors,
    _detect_movers,
    _planner_background,
    _region_candidates,
    _round_robin_queue,
    _scale_unit,
)
from admorphiq.kernels import find_regions


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


def _stamp_frame(grid: list[list[int]], top_left: tuple[int, int], colour: int) -> None:
    """Stamp a solid 2x2 moving token of ``colour`` at ``top_left``."""
    r, c = top_left
    _stamp(grid, [(r, c), (r, c + 1), (r + 1, c), (r + 1, c + 1)], colour)


def _stamp_target(grid: list[list[int]], centre: tuple[int, int], colour: int) -> None:
    """Stamp a hollow 4-corner target frame of ``colour`` centred on ``centre``."""
    r, c = centre
    _stamp(grid, [(r - 2, c - 2), (r - 2, c + 2), (r + 2, c - 2), (r + 2, c + 2)], colour)


def test_detect_marker_colors_finds_every_class_and_matches_movers_to_dests():
    """Purpose: pin the L3 generalization -- marker classes are DISCOVERED per
    level (a colour appearing as both a solid moving token AND a hollow 4-corner
    target frame), not the single hard-coded colour the L2 code used. LP85 L3 has
    TWO classes (goal + goal-o) that must all be placed to win, so detection must
    surface both, each with its movers tagged by class and matched to same-class
    destinations.

    Expected feedback: PASS = both marker colours are found, and _detect_movers /
    _detect_dests tag and pair them by class (each class has equal mover/dest
    counts at the right centroids). Failure means the adapter regressed to a
    single-colour reading and would misdetect (or reject) any multi-class level."""
    size = 64
    grid = _blank_grid(size, bg=0)
    # A chrome panel so the two-most-common background exclusion has a real
    # second colour to drop -- markers stay rare and survive it.
    for r in range(40, 52):
        _stamp(grid, [(r, c) for c in range(2, 30)], 3)
    # Two button controls (colour 8) so detection has ≥1 control.
    _stamp(grid, [(1, 12), (1, 13)], 8)
    # Class colour-11: solid token + its own hollow target frame.
    _stamp_frame(grid, (20, 40), 11)
    _stamp_target(grid, (28, 16), 11)
    # Class colour-12: solid token + its own hollow target frame.
    _stamp_frame(grid, (34, 18), 12)
    _stamp_target(grid, (28, 46), 12)

    tup = tuple(tuple(row) for row in grid)
    bg = _planner_background(tup)
    assert 0 in bg and 3 in bg  # both backdrops excluded, neither marker colour
    regions = find_regions(tup, background=bg)

    marker_colors = _detect_marker_colors(regions)
    assert marker_colors == frozenset({11, 12})

    movers = _detect_movers(regions, marker_colors)
    dests = _detect_dests(regions, marker_colors)
    # Each class contributes exactly one mover and one destination.
    assert sorted(color for color, _ in movers) == [11, 12]
    assert sorted(color for color, _ in dests) == [11, 12]
    assert dict(dests) == {11: (28, 16), 12: (28, 46)}


def test_detect_marker_colors_ignores_a_solid_without_a_target_frame():
    """Purpose: a solid coloured blob that has NO matching hollow target frame is
    an ordinary ring tile / decoration, NOT a marker class -- requiring a real
    4-corner frame is what stops the multi-class discovery from mistaking every
    coloured region for a mover.

    Expected feedback: PASS = a lone solid colour (no frame) is excluded from the
    marker set. Failure means detection over-triggers and would inject phantom
    token classes, breaking the mover==dest count gate that guards planning."""
    size = 64
    grid = _blank_grid(size, bg=0)
    for r in range(40, 52):
        _stamp(grid, [(r, c) for c in range(2, 30)], 3)
    _stamp(grid, [(1, 12), (1, 13)], 8)
    # Colour-11 is a proper class (solid + frame); colour-7 is a bare solid.
    _stamp_frame(grid, (20, 40), 11)
    _stamp_target(grid, (28, 16), 11)
    _stamp_frame(grid, (34, 18), 7)  # solid only, no corner frame

    tup = tuple(tuple(row) for row in grid)
    regions = find_regions(tup, background=_planner_background(tup))
    assert _detect_marker_colors(regions) == frozenset({11})


# ── stall give-up (R59 addendum: wall-time fix, score-neutral) ────────────────


def _play_frame():
    return SimpleNamespace(state=SimpleNamespace(name="PLAYING"))


def test_stall_giveup_fires_once_planner_failed_and_sweep_stalled():
    """Purpose: after the ring planner deactivates on a level index >= 2 the sweep
    cannot clear, is_done must return True once _STALL_GIVEUP no-progress sweep
    actions have elapsed — sparing lp85's full-25 run from grinding thousands of
    zero-value dense-render sweep clicks (~3.7h -> minutes).
    Expected feedback: PASS proves the give-up arms in the genuinely stalled
    state; a failure means either the wall-time bug persists or it stops early."""
    from admorphiq.adapters25.lp85 import _STALL_GIVEUP

    ad = Adapter()
    ad._levels_seen = 3  # on L4 (L1-L3 cleared)
    ad._planner_active = False  # planner gave up
    ad._sweep_steps = _STALL_GIVEUP
    assert ad.is_done([], _play_frame()) is True


def test_stall_giveup_never_fires_on_the_L1_sweep_path():
    """Purpose: L0/L1 (index < 2) are cleared by the sweep itself, so the give-up
    must NEVER arm there, even after many sweep actions.
    Expected feedback: PASS guarantees the proven L1 sweep clear is not aborted."""
    from admorphiq.adapters25.lp85 import _STALL_GIVEUP

    ad = Adapter()
    ad._levels_seen = 0  # on L1
    ad._planner_active = False
    ad._sweep_steps = _STALL_GIVEUP * 5
    assert ad.is_done([], _play_frame()) is False


def test_stall_giveup_never_fires_while_planner_active():
    """Purpose: while the planner is still working (L2/L3, which it clears), the
    give-up must not arm regardless of the counter.
    Expected feedback: PASS confirms an in-progress planned clear is never cut."""
    ad = Adapter()
    ad._levels_seen = 3
    ad._planner_active = True
    ad._sweep_steps = 10**6
    assert ad.is_done([], _play_frame()) is False


def _stamp_block(grid: list[list[int]], top_left: tuple[int, int], n: int, colour: int) -> None:
    """Stamp a solid n×n block of ``colour`` (a token/tile at a larger render scale)."""
    r, c = top_left
    _stamp(grid, [(r + dr, c + dc) for dr in range(n) for dc in range(n)], colour)


def test_detection_is_scale_robust_for_a_coarse_board():
    """Purpose: pin the LP85 L5 fix — on a COARSE-scale board (small internal grid
    → large render scale) a target's corners render as size-4 BLOCKS and the goal
    token as a size-16 block, so the fixed L1–L4 thresholds (solid≥3, span 6)
    mis-bucket every corner as a solid and find no target frame. The scale-derived
    thresholds (unit 16 → solid≥8, span 12) must recover the target and the mover.

    Expected feedback: PASS = _scale_unit reads the 16-px tile unit, and with the
    derived solid_min/span the target frame's centre is a destination and the
    size-16 block is the mover (corners excluded); with the DEFAULT thresholds the
    colour is NOT detected as a marker at all — proving the scale relativity is
    load-bearing, not cosmetic. This is what lets the L5 planner engage."""
    size = 64
    grid = _blank_grid(size, bg=0)
    for r in range(48, 60):  # second backdrop to drop
        _stamp(grid, [(r, c) for c in range(2, 40)], 3)
    _stamp_block(grid, (1, 10), 2, 8)  # a button control
    # Coarse ring tiles (colour 9, 4×4 = size 16) set the modal unit to 16.
    for c in (2, 8, 14, 20, 26):
        _stamp_block(grid, (30, c), 4, 9)
    # Marker colour-11: a size-16 goal token + a target whose 4 corners are size-4.
    _stamp_block(grid, (20, 40), 4, 11)  # goal token, size 16
    for (dr, dc) in ((0, 0), (0, 6), (6, 0), (6, 6)):  # 4 corners, size 4, span 6
        _stamp_block(grid, (4 + dr, 16 + dc), 2, 11)

    tup = tuple(tuple(row) for row in grid)
    bg = _planner_background(tup)
    regions = find_regions(tup, background=bg)

    unit = _scale_unit(regions, bg)
    assert unit == 16  # modal small region = the 4×4 tile/token
    solid_min = max(3, unit // 2)  # 8
    span = max(6, 3 * isqrt(unit))  # 12

    # scale-derived thresholds recover the marker, its target, and its mover
    marker = _detect_marker_colors(regions, solid_min, span)
    assert marker == frozenset({11})
    dests = _detect_dests(regions, marker, solid_min, span)
    movers = _detect_movers(regions, marker, solid_min)
    assert [c for c, _ in dests] == [11] and len(dests) == 1
    assert [c for c, _ in movers] == [11] and len(movers) == 1  # the size-16 block only

    # the fixed L1–L4 thresholds miss it entirely (corners look like solids)
    assert _detect_marker_colors(regions) == frozenset()


def test_cluster_frame_centres_separates_tightly_packed_frames():
    """Purpose: pin the LP85 L6 detection fix — three hollow target frames packed
    corner-pitch apart (the inter-frame gap equals the intra-frame corner span, both
    = 3) must resolve to THREE distinct centres. The earlier single-linkage span
    grouping merged all 12 corners into one dest (movers=3 vs dests=1 → DETECT_OK
    false, the L6 wall); disjoint 4-corner-square extraction keeps them separate.

    Expected feedback: PASS = the real L6 corner geometry yields exactly 3 centres,
    one per frame; a FAIL (1 or 2 centres) means the packed-frame separation
    regressed and L6 detection is broken again. The lattice used is the measured
    L6 render: rows {26,29,32,35} × cols {25,28,31,34} in a brick arrangement."""
    # frame A rows{26,29}×cols{25,28}; B rows{26,29}×cols{31,34}; C rows{32,35}×cols{28,31}
    corners = [
        (26, 25), (26, 28), (29, 25), (29, 28),  # A
        (26, 31), (26, 34), (29, 31), (29, 34),  # B
        (32, 28), (32, 31), (35, 28), (35, 31),  # C
    ]
    centres = _cluster_frame_centres(corners, span=6)
    assert len(centres) == 3, centres
    # each centre is the middle of its own 3-pitch square (±rounding), all distinct
    assert sorted(centres) == [(28, 26), (28, 32), (34, 30)]


def test_cluster_frame_centres_preserves_separated_and_occluded_frames():
    """Purpose: the L6 packed-frame fix must NOT change the well-separated /
    occluded cases the L2/L3/L5 planner already relies on — a lone frame is one
    centre, two distant frames are two, and a 3-corner (one occluded) frame still
    yields its centre.

    Expected feedback: PASS = separated frames still cluster 1:1 and a 3-corner
    frame is tolerated; a FAIL means the disjoint-square extraction broke the
    separated-frame contract (a floor-level regression risk for L2/L3/L5)."""
    lone = [(10, 10), (10, 13), (13, 10), (13, 13)]
    assert _cluster_frame_centres(lone, span=6) == [(12, 12)]
    two = lone + [(40, 40), (40, 43), (43, 40), (43, 43)]
    assert _cluster_frame_centres(two, span=6) == [(12, 12), (42, 42)]
    occluded = [(10, 10), (10, 13), (13, 10)]  # one corner missing
    assert _cluster_frame_centres(occluded, span=6) == [(12, 12)]
    # a coarse-board frame (wider corner spacing) still clusters as one
    coarse = [(10, 10), (10, 18), (18, 10), (18, 18)]
    assert _cluster_frame_centres(coarse, span=12) == [(14, 14)]
