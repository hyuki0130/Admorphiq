"""Tests for the R11L centroid-assembly planner detection (R56, 2026-07-15).

See the module docstring: a creature's body sits at the integer centroid of
its clickable legs; a level wins when every body is on its target nest. The
planner detects legs + the target nest from frame structure, then composes
``points_with_centroid`` to place the legs so the body lands on the nest.
These tests pin the role-detection contract on a synthetic board (the live
solve is measured separately by ``scripts/script25.py``).
"""

from __future__ import annotations

from admorphiq.adapters25.r11l import _LEG_SEP, Adapter, _analyze_creatures, _hazard_cells

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


def test_l1_body_free_detection_and_per_creature_colour_grouping():
    """Purpose (R60c): on the measured r11l L1 layout — a colour-12 creature
    (3 legs + body + target ring) and a colour-15 creature (2 legs + body +
    target) — the FROZEN-TARGET controller's detectors behave as its
    per-creature assignment requires: ``_detect_legs`` returns EXACTLY the 5
    legs (bodies and target rings excluded), ``_detect_bodies`` returns each
    creature's body keyed by colour, and ``_build_frozen`` keys each creature to
    its BODY colour (sampled by nearest body to the leg centroid, NOT the hollow
    target-ring centroid which reads background). Expected feedback: a FAIL
    means legs mis-group across creatures (the R60b thrash) or a body is driven
    like a leg (which fires the body-collision strike)."""
    cells: dict[tuple[int, int], int] = {}
    # colour-12 creature: 3 legs, body at their centroid ~(12,25), target ring.
    for lc in [(6, 17), (9, 49), (21, 8)]:
        cells.update(_leg(*lc, 3))
    cells.update(_body(11, 24, 12))
    cells.update(_ring(51, 40, 12))
    # colour-15 creature: 2 legs, body at their centroid ~(41,49), target ring.
    for lc in [(35, 45), (48, 54)]:
        cells.update(_leg(*lc, 3))
    cells.update(_body(41, 50, 15))
    cells.update(_ring(18, 57, 15))
    grid = _grid(cells)
    ad = Adapter()
    hazard = _hazard_cells(grid, _BG)

    legs = {ad._leg_centre(r) for r in ad._detect_legs(grid, _BG, hazard)}
    assert legs == {(6, 17), (9, 49), (21, 8), (35, 45), (48, 54)}

    bodies = ad._detect_bodies(grid, _BG, hazard)
    assert set(bodies) == {12, 15}
    assert abs(bodies[12][0] - 12) <= 2 and abs(bodies[12][1] - 25) <= 2
    assert abs(bodies[15][0] - 42) <= 2 and abs(bodies[15][1] - 51) <= 2

    creatures = _analyze_creatures(grid, _BG, hazard)
    assert creatures is not None and len(creatures) == 2
    ad._build_frozen(grid, _BG, creatures)
    # Each creature is keyed to the colour of the body nearest its leg centroid;
    # the 3-leg creature -> colour 12, the 2-leg creature -> colour 15.
    color_by_legs = {
        len(legs_c): ad._frozen_colors[i] for i, (legs_c, _t) in enumerate(ad._frozen_creatures)
    }
    assert color_by_legs[3] == 12
    assert color_by_legs[2] == 15


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


def test_strike_aware_plan_is_body_hazard_free_and_separates_legs():
    """Purpose (R85): the multi-creature strike-aware move planner must (a) never
    emit a move whose resulting BODY centroid lands on a body-hazard cell — the
    engine punishes a body dragged onto the in-play obstacle with a strike and
    reverts the move — and (b) keep every placed leg at least ``_LEG_SEP`` from
    the others, since closer legs fuse under region detection and become
    unselectable. Built on a synthetic board whose hazard blob covers the naive
    exact-centroid target cell, so the planner must use the target-box tolerance
    to seat the body just off the hazard.

    Expected feedback: a FAIL means the planner would drive a body through the
    obstacle (spending the 5-strike budget) or place legs the adapter can no
    longer tell apart — the two execution failures measured while building R85,
    each of which left the live L1 at 1/6."""
    ad = Adapter()
    ad._piece_half = 2
    # One 2-leg creature well below a target near (12, 30); a hazard rectangle
    # (size >> the hazard floor) sits over the target's own centre row band, so a
    # body seated exactly on the target centre would strike.
    legs = [(40, 24), (40, 36)]  # body starts at their mean (40, 30)
    target_centre = (12, 30)
    ad._frozen_creatures = [(legs, target_centre)]
    ad._cr_target_box = [(9, 27, 15, 33)]  # 7x7 ring bbox around the target
    ad._learned_haz = set()

    g = [[_BG] * 64 for _ in range(64)]
    haz_cells: set[tuple[int, int]] = set()
    for r in range(12, 18):  # covers the target centre row 12 and below
        for c in range(26, 35):
            g[r][c] = 8
            haz_cells.add((r, c))
    grid = tuple(tuple(row) for row in g)
    hazard = _hazard_cells(grid, _BG)  # the colour-8 rectangle is a large region
    assert haz_cells <= hazard  # the blob is recognised as a hazard

    result = ad._plan_creature(grid, _BG, hazard, legs, 0, avoid=set())
    assert result is not None, "a strike-free plan should exist (target box extends above the hazard)"
    moves, final_cfg = result

    # (a) every move's predicted body centroid is off the body hazard.
    for _frm, _to, body_after in moves:
        assert body_after not in hazard, f"planned body {body_after} lands on the obstacle (would strike)"

    # (b) the final legs are mutually separated.
    for i in range(len(final_cfg)):
        for j in range(i + 1, len(final_cfg)):
            assert ad._cheb(final_cfg[i], final_cfg[j]) >= _LEG_SEP

    # goal actually reached: the final body centroid sits inside the target bbox.
    n = len(final_cfg)
    body = (sum(p[0] for p in final_cfg) // n, sum(p[1] for p in final_cfg) // n)
    r0, c0, r1, c1 = ad._cr_target_box[0]
    assert r0 <= body[0] <= r1 and c0 <= body[1] <= c1
    assert body not in hazard
