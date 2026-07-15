"""Tests for the R11L centroid-assembly planner detection (R56, 2026-07-15).

See the module docstring: a creature's body sits at the integer centroid of
its clickable legs; a level wins when every body is on its target nest. The
planner detects legs + the target nest from frame structure, then composes
``points_with_centroid`` to place the legs so the body lands on the nest.
These tests pin the role-detection contract on a synthetic board (the live
solve is measured separately by ``scripts/script25.py``).
"""

from __future__ import annotations

from admorphiq.adapters25.r11l import _analyze_creatures, _hazard_cells

_BG = 5


def _grid(cells, h=64, w=64):
    """A background grid with ``cells`` = {(r, c): color} painted on."""
    g = [[_BG] * w for _ in range(h)]
    for (r, c), col in cells.items():
        g[r][c] = col
    return tuple(tuple(row) for row in g)


def _body(top, left, color, size=4):
    """A near-solid square (high bbox-fill) — a BODY marker."""
    return {(top + r, left + c): color for r in range(size) for c in range(size)}


def _leg(cr, cc, color):
    """A compact but NOT solid foot centred at ``(cr, cc)`` — a plus shape,
    ~0.36 bbox-fill, matching the game's legs (~0.48) which sit below the body
    fill threshold. (A solid square would read as a body.)"""
    return {
        (cr, cc): color,
        (cr - 1, cc): color,
        (cr - 2, cc): color,
        (cr + 1, cc): color,
        (cr + 2, cc): color,
        (cr, cc - 1): color,
        (cr, cc - 2): color,
        (cr, cc + 1): color,
        (cr, cc + 2): color,
    }


def _ring(centre_r, centre_c, color):
    """A hollow ring of scattered pixels (a target nest) around a centre."""
    offs = [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (-1, 1), (1, -1), (1, 1)]
    return {(centre_r + dr, centre_c + dc): color for dr, dc in offs}


def test_detects_legs_and_target_over_connectors():
    """Purpose: on a two-leg creature (compact feet colour 3 at (10,10) and
    (30,30), body colour 7 at their centroid (20,20), a target ring colour 7
    elsewhere, plus a thin low-fill connector colour 8 that ALSO forms two
    regions), the detector returns the two feet and the target-nest centre —
    not the connector colour. Expected feedback: a FAIL means the planner
    would try to move the non-clickable limb lines or aim at the wrong nest,
    and no level would clear efficiently."""
    cells: dict[tuple[int, int], int] = {}
    cells.update(_leg(10, 10, 3))  # foot 1
    cells.update(_leg(30, 30, 3))  # foot 2
    cells.update(_body(18, 18, 7))  # body ~ at legs' centroid (20, 20)
    cells.update(_ring(45, 50, 7))  # target nest (same colour as body), far away
    # A thin diagonal connector (colour 8), two clusters — the decoy pair.
    for i in range(6):
        cells[(12 + i, 12 + i)] = 8
    for i in range(6):
        cells[(24 + i, 24 + i)] = 8
    grid = _grid(cells)
    hazard = _hazard_cells(grid, _BG)
    result = _analyze_creatures(grid, _BG, hazard)
    assert result is not None
    assert len(result) == 1  # one creature
    leg_centres, target = result[0]
    assert len(leg_centres) == 2
    assert {tuple(c) for c in leg_centres} == {(10, 10), (30, 30)}
    # target near the ring centre (45, 50)
    assert abs(target[0] - 45) <= 2 and abs(target[1] - 50) <= 2


def test_detects_two_creatures_and_groups_legs_by_body():
    """Purpose: on a TWO-creature board (colour-6 body with 3 legs, colour-9
    body with 2 legs, each body at its own legs' centroid), the detector
    returns both creatures with legs correctly partitioned by nearest body.
    Expected feedback: a FAIL means multi-creature levels (r11l L1+) would be
    mis-grouped, so no deeper level clears."""
    cells: dict[tuple[int, int], int] = {}
    # Creature A: legs at (10,10),(10,30),(30,20) -> centroid (~16.7, 20).
    for lc in [(10, 10), (10, 30), (30, 20)]:
        cells.update(_leg(*lc, 3))
    cells.update(_body(15, 18, 6))  # body ~ (16.7, 20)
    cells.update(_ring(50, 10, 6))  # A's target
    # Creature B: legs at (50,45),(58,55) -> centroid (54, 50).
    for lc in [(50, 45), (58, 55)]:
        cells.update(_leg(*lc, 0))
    cells.update(_body(52, 48, 9))  # body ~ (54, 50)
    cells.update(_ring(20, 55, 9))  # B's target
    grid = _grid(cells)
    hazard = _hazard_cells(grid, _BG)
    result = _analyze_creatures(grid, _BG, hazard)
    assert result is not None
    assert len(result) == 2
    by_size = sorted(result, key=lambda cr: len(cr[0]))
    assert len(by_size[0][0]) == 2  # creature B: 2 legs
    assert len(by_size[1][0]) == 3  # creature A: 3 legs
    assert {tuple(c) for c in by_size[1][0]} == {(10, 10), (10, 30), (30, 20)}


def test_returns_none_on_non_creature_layout():
    """Purpose: a board with no same-colour body/target ring pair at the
    legs' centroid is not a centroid-assembly creature, so detection returns
    None and the adapter falls back to the generic explorer. Expected
    feedback: a FAIL means the planner would fabricate a bogus plan on an
    unrelated layout instead of deferring to the explorer."""
    cells: dict[tuple[int, int], int] = {}
    cells.update(_leg(10, 10, 3))
    cells.update(_leg(30, 30, 4))
    grid = _grid(cells)
    hazard = _hazard_cells(grid, _BG)
    assert _analyze_creatures(grid, _BG, hazard) is None
