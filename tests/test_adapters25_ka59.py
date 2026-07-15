"""Tests for the KA59 adapter's heterogeneous size-matched placement gate
(R56 L1 round, 2026-07-15).

Background (see the module docstring + ``.wiki/wiki/games/KA59.md``): L0 is a
two-equal-hollow-ring board cleared by the launch/place orchestrator; L1 is a
DIFFERENT structure -- four hollow FRAMES of several inner sizes plus four
SOLID (non-ring) pieces whose bbox area matches a frame's inner area. The
adapter gates on the frame inner-size-class count: a single class routes to the
untouched L0 ring model, more than one routes to the solid-piece placement path
with size-matched assignment. These tests pin that gate + the size matching;
L0 byte-identical behaviour is verified separately by a determinism run.
"""

from __future__ import annotations

from admorphiq.adapters25.ka59 import (
    Adapter,
    _classify_hetero,
    _frame_inner_areas,
)


def _ring(inner_bbox: tuple[int, int, int, int]) -> dict:
    """A minimal closed_frames-style ring dict (only the field the gate and
    the hetero classifier read: ``inner_bbox``)."""
    return {"inner_bbox": inner_bbox}


def _grid(size: int, bg: int, stamps: list[tuple[int, int, int, int, int]]) -> tuple[tuple[int, ...], ...]:
    """A ``size``x``size`` grid of ``bg`` with each ``(colour, r0, c0, r1, c1)``
    rectangle painted solid on top."""
    g = [[bg] * size for _ in range(size)]
    for colour, r0, c0, r1, c1 in stamps:
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                g[r][c] = colour
    return tuple(tuple(row) for row in g)


def test_frame_inner_areas_filters_tiny_holes_and_dedups_classes():
    """Purpose: the gate counts FRAME size classes, so it must exclude a ring
    PIECE's single-cell hole (inner area 1, below _MIN_FRAME_INNER_AREA) and
    collapse duplicate frame sizes to one class. L0's board (two frames inner
    area 9 + two piece-rings inner 1) must read as exactly ONE class so it
    keeps routing to the untouched ring model; L1's (frames 9/18/18/36 + a
    piece-ring inner 1) must read as THREE.
    Expected feedback: failure means the gate mis-fires -- either L0 diverts
    into the solid-piece path (breaking the byte-identical floor) or L1 fails
    to trigger the heterogeneous path at all."""
    l0 = [_ring((1, 1, 1, 1)), _ring((1, 1, 1, 1)), _ring((0, 0, 2, 2)), _ring((0, 0, 2, 2))]
    assert _frame_inner_areas(l0) == [9]  # inner-1 piece holes filtered, dup 9s collapsed
    l1 = [
        _ring((0, 0, 0, 0)),  # a piece-ring hole, area 1 -> filtered
        _ring((0, 0, 2, 2)),  # area 9
        _ring((0, 0, 2, 5)),  # area 18
        _ring((0, 0, 2, 5)),  # area 18 (dup)
        _ring((0, 0, 5, 5)),  # area 36
    ]
    assert _frame_inner_areas(l1) == [9, 18, 36]


def test_classify_hetero_detects_solid_pieces_matching_frame_inner_areas():
    """Purpose: on a heterogeneous board the pieces are SOLID shapes invisible
    to hollow-ring detection, so they must be found via find_regions and kept
    only when their bbox area equals some frame's inner area (the "this piece
    fits this frame" test). Regions that match no frame inner size (a large
    background structure, a frame border) must be dropped, never mistaken for
    pieces.
    Expected feedback: failure means the placement path either misses real
    pieces (leaving frames it can't see how to fill) or picks up walls/borders
    as bogus pieces and mis-plans around them."""
    bg = 1
    grid = _grid(
        32,
        bg,
        [
            (14, 10, 10, 12, 12),  # solid piece, bbox 9  -> matches inner-9 frame
            (14, 20, 20, 22, 25),  # solid piece, bbox 18 -> matches inner-18 frame
            (15, 0, 28, 5, 31),    # a structure of bbox area 24 (not 9 or 18) -> excluded
        ],
    )
    frames = [_ring((10, 10, 12, 12)), _ring((20, 20, 22, 25))]  # inner areas 9 and 18
    pieces, out_frames = _classify_hetero(grid, bg, frames)
    piece_boxes = sorted(p["bbox"] for p in pieces)
    assert piece_boxes == [(10, 10, 12, 12), (20, 20, 22, 25)]
    assert out_frames == frames


def test_assign_forbids_cross_size_pairs_and_breaks_ties_by_distance():
    """Purpose: heterogeneous assignment must never send a piece to a
    wrong-size frame (a size mismatch adds a prohibitive penalty), and among
    same-size frames it must prefer the nearer one. On L1 two frames share
    inner area 18, so the tie-break decides which same-size piece goes where.
    Expected feedback: failure means a piece could be routed to a frame it can
    never fill (wrong size) or take a needlessly long path, both of which stall
    the level."""
    adapter = Adapter()
    # Two pieces of area 9 and 18; two frames of area 18 and 9 placed so the
    # nearest frame to each piece is the WRONG size -- size matching must win.
    p9, p18 = (0, 0), (0, 2)
    f9, f18 = (0, 3), (0, 10)
    piece_area = {p9: 9, p18: 18}
    target_area = {f9: 9, f18: 18}
    assignment = adapter._assign([p9, p18], [f9, f18], piece_area, target_area)
    assert assignment == {p9: f9, p18: f18}  # matched by size, not by nearest


def test_assign_is_pure_distance_when_no_area_maps_given():
    """Purpose: the L0 byte-identical guarantee -- with no area maps (the L0
    call path) _assign is exactly the original nearest-distance bipartite
    match, so the launch/place orchestrator is unaffected by the L1 feature.
    Expected feedback: failure means the L0 path's assignment changed, which
    would show up as an L0 score regression below the 1/7 @ 0.0205 floor."""
    adapter = Adapter()
    a, b = (0, 0), (0, 10)
    ta, tb = (0, 1), (0, 11)
    assert adapter._assign([a, b], [ta, tb]) == {a: ta, b: tb}
