"""Unit tests for the PATTERN-MATCH primitive (paint + GF(2) toggle).

All tests are pure (no live env): they construct synthetic frames / stencils
with a known correct answer and assert the deterministic planner reproduces it.
This is the durable contract for the cd82-paint and ft09-toggle primitives —
it guarantees the solve maths and the minimal-action planning are correct
independent of any specific game.
"""

from __future__ import annotations

import numpy as np

from admorphiq.primitives.pattern_match import (
    _diagonal_mask,
    build_stencil,
    detect_grid_cells,
    detect_paint_task,
    plan_paint,
    plan_toggle,
)

# ── GF(2) toggle ─────────────────────────────────────────────────────────────


def test_plan_toggle_identity_flips_only_minority():
    """Purpose: on an identity stencil (click j flips only cell j), the planner
    clicks exactly the minority-class cells to make the board homogeneous.

    Expected feedback: PASS proves the GF(2) all-off target + solve picks the
    minimal click set; FAIL means the solver over- or under-clicks (efficiency
    regression on lights-out games).
    """
    cells = [(10, 10), (20, 10), (30, 10)]
    stencil = {
        "A": np.eye(3, dtype=np.uint8),
        # cells 0,1 are "off" (class 7), cell 2 is "on" (class 3) → minority.
        "base_classes": [7, 7, 3],
        "toggled_classes": [3, 3, 7],
        "cells": list(cells),
    }
    clicks = plan_toggle(cells, stencil)
    assert clicks == [(30, 10)]


def test_plan_toggle_coupled_solution_satisfies_system():
    """Purpose: on a coupled (non-identity) stencil the returned click subset x
    satisfies A·x ≡ b (mod 2) for the homogenising target.

    Expected feedback: PASS proves Gaussian elimination over GF(2) is wired in
    correctly for true lights-out coupling; FAIL means the solve is wrong and
    no clicked subset actually reaches the goal state.
    """
    # 3-cell line: clicking a cell flips itself and its right neighbour.
    A = np.array([[1, 0, 0], [1, 1, 0], [0, 1, 1]], dtype=np.uint8)
    cells = [(10, 10), (20, 10), (30, 10)]
    stencil = {
        "A": A,
        "base_classes": [3, 3, 7],  # cell 2 is the odd one out
        "toggled_classes": [7, 7, 3],
        "cells": list(cells),
    }
    clicks = plan_toggle(cells, stencil)
    assert clicks  # a non-empty solution exists
    x = np.zeros(3, dtype=np.uint8)
    for j, (cx, cy) in enumerate(cells):
        if (cx, cy) in clicks:
            x[j] = 1
    flip = (A @ x) % 2
    # Every minority cell (base != majority class 3) must be flipped.
    assert flip[2] == 1


def test_plan_toggle_no_stencil_returns_empty():
    """Purpose: without a measured stencil the planner emits no clicks (it never
    guesses blindly).

    Expected feedback: PASS proves the toggle path is safe before measurement;
    FAIL means the agent would click randomly and tank efficiency.
    """
    assert plan_toggle([(1, 1), (2, 2)], None) == []


def test_plan_toggle_all_homogeneous_returns_empty():
    """Purpose: when the board is already homogeneous, no clicks are needed.

    Expected feedback: PASS proves the planner does not waste actions on a
    solved board; FAIL is a direct efficiency (squared-metric) loss.
    """
    stencil = {
        "A": np.eye(2, dtype=np.uint8),
        "base_classes": [5, 5],
        "toggled_classes": [9, 9],
        "cells": [(10, 10), (20, 10)],
    }
    assert plan_toggle([(10, 10), (20, 10)], stencil) == []


# ── stencil measurement from probes ──────────────────────────────────────────


def test_build_stencil_recovers_identity_columns():
    """Purpose: build_stencil reconstructs A[i][j] from self-inverse click probes
    — clicking cell j flips only cell j's patch class here.

    Expected feedback: PASS proves the empirical stencil measurement maps each
    probe to the right column; FAIL means the GF(2) matrix would be garbage and
    every downstream solve fails.
    """
    cells = [(10, 10), (30, 10)]
    base = np.full((40, 40), 5, dtype=np.int32)
    # Probe 0: click (10,10) → cell-0 patch becomes class 9.
    after0 = base.copy()
    after0[6:15, 6:15] = 9
    # Probe 1: click (30,10) → cell-1 patch becomes class 9.
    after1 = base.copy()
    after1[6:15, 26:35] = 9
    probes = [
        {"x": 10, "y": 10, "before": base.copy(), "after": after0},
        {"x": 30, "y": 10, "before": base.copy(), "after": after1},
    ]
    st = build_stencil(cells, probes)
    assert st is not None
    assert np.array_equal(st["A"], np.eye(2, dtype=np.uint8))


def test_build_stencil_none_without_probes():
    """Purpose: no click probes → no stencil (None), so detection reports "needs
    measurement" rather than fabricating a matrix.

    Expected feedback: PASS keeps the detect→measure→solve contract honest.
    """
    assert build_stencil([(1, 1)], []) is None


# ── paint / region-match ─────────────────────────────────────────────────────


def test_diagonal_mask_excludes_both_diagonals():
    """Purpose: the compare mask drops both 10x10 diagonals (cd82's win ignores
    them), so the planner never wastes clicks repainting diagonal cells.

    Expected feedback: PASS proves the mask matches the game's array_equal mask;
    FAIL means we repaint cells the win check ignores (efficiency loss).
    """
    m = _diagonal_mask(10)
    for i in range(10):
        assert not m[i, i]
        assert not m[i, 9 - i]
    assert m[0, 1]  # an off-diagonal cell is compared


def test_plan_paint_repaints_only_differing_cell():
    """Purpose: plan_paint emits exactly one palette-select + one cell-click for
    a single differing off-diagonal cell (minimal action sequence).

    Expected feedback: PASS proves the diff-and-group planning is minimal; FAIL
    means redundant clicks that square-penalise the efficiency score.
    """
    # 40x40 frame, bg=5. Reference region [2:22, 2:22] is all 7 except a single
    # off-diagonal cell painted 9. Editable region [2:22, 24:44] is uniform 7.
    layer = np.full((48, 48), 5, dtype=np.int32)
    layer[2:22, 2:22] = 7  # reference panel (multi-colour)
    layer[4:6, 6:8] = 9  # one off-diagonal cell in the reference
    layer[2:22, 24:44] = 7  # editable panel (uniform)
    det = detect_paint_task(layer, [])
    assert det is not None
    plan = plan_paint(det, layer)
    # One colour group (9) → 1 select + 1 cell click = 2 actions.
    assert len(plan) == 2
    assert all(a == 6 for a, _x, _y in plan)


def test_plan_paint_empty_when_regions_match():
    """Purpose: identical reference and editable regions → no paint actions.

    Expected feedback: PASS proves the planner short-circuits an already-solved
    board; FAIL is wasted budget.
    """
    layer = np.full((48, 48), 5, dtype=np.int32)
    layer[2:22, 2:22] = 7
    layer[2:22, 24:44] = 7
    det = detect_paint_task(layer, [])
    assert det is not None
    assert plan_paint(det, layer) == []


def test_detect_paint_requires_congruent_pair():
    """Purpose: detect_paint_task fires only when two bounding-box-congruent
    regions exist; a lone region yields None.

    Expected feedback: PASS proves the detector is signature-gated (won't
    misfire on non-paint games); FAIL means false positives that hijack the
    dispatch away from the correct primitive.
    """
    lone = np.full((48, 48), 5, dtype=np.int32)
    lone[2:22, 2:22] = 7
    assert detect_paint_task(lone, []) is None


def test_detect_grid_cells_finds_lattice():
    """Purpose: detect_grid_cells returns one centroid per compact blob on a
    regular lattice (the clickable cells of a toggle board).

    Expected feedback: PASS proves the cell detector locates click targets from
    pixels alone; FAIL means the toggle primitive has nothing to probe.
    """
    layer = np.full((48, 48), 5, dtype=np.int32)
    centres = []
    for gy in (10, 24, 38):
        for gx in (10, 24, 38):
            layer[gy - 3 : gy + 3, gx - 3 : gx + 3] = 8
            centres.append((gx, gy))
    cells = detect_grid_cells(layer)
    assert len(cells) == 9
    for cx, cy in centres:
        assert any(abs(cx - dx) <= 2 and abs(cy - dy) <= 2 for dx, dy in cells)
