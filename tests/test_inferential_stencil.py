"""Round 16 — lights-out toggle stencil measurement tests.

These tests pin the R16 measurement layer that R17's GF(2) solver
consumes. They exercise `_extract_cell_class` as a pure patch-mode
reader and `_measure_toggle_stencil` against a synthetic env that
implements a known toggle stencil.
"""

from __future__ import annotations

import numpy as np
import pytest

from arcengine import GameAction

from admorphiq.strategies import inferential as inf


def test_extract_cell_class_returns_mode_color():
    """Purpose: pin the cell-state classifier to mode-of-patch behavior.

    Expected feedback: failure means the patch-mode extractor drifted
    and stencil measurement would misread cell states, producing a
    garbage A matrix.
    """
    frame = np.zeros((64, 64), dtype=np.int32)
    frame[10:15, 10:15] = 7
    assert inf._extract_cell_class(frame, 12, 12, 2) == 7
    assert inf._extract_cell_class(frame, 0, 0, 2) == 0


def test_extract_cell_class_handles_edge_clipping():
    """Purpose: confirm edge patches don't crash and return a sane mode.

    Expected feedback: failure means near-border cells crash
    measurement on small grids — FT09 has buttons at x=38,46,54 which
    sit comfortably inside 64x64, but CD82 and others have border
    indicators.
    """
    frame = np.full((64, 64), 3, dtype=np.int32)
    frame[63, 63] = 9
    assert inf._extract_cell_class(frame, 63, 63, 2) == 3


class _StencilEnv:
    """Minimal env that implements a known toggle stencil.

    RESET returns the base-state frame. ACTION6 at (x, y) finds the
    matching cell index j and XORs every cell i where stencil[i][j]
    is set, then re-renders each cell as its base or toggled patch.
    """

    def __init__(self, cells, base_classes, toggled_classes, stencil, patch_radius=2):
        self._cells = list(cells)
        self._base_classes = list(base_classes)
        self._toggled_classes = list(toggled_classes)
        self._stencil = stencil
        self._r = patch_radius
        self._n = len(cells)
        self._state = [0] * self._n

    def _render(self):
        frame = np.full((64, 64), 5, dtype=np.int32)
        r = self._r
        for i in range(self._n):
            cx, cy = self._cells[i]
            cls = self._toggled_classes[i] if self._state[i] else self._base_classes[i]
            frame[max(0, cy - r):cy + r + 1, max(0, cx - r):cx + r + 1] = cls
        return _FrameObs(frame)

    def step(self, action, data=None):
        if action == GameAction.RESET:
            self._state = [0] * self._n
            return self._render()
        if action == GameAction.ACTION6 and data is not None:
            x, y = int(data["x"]), int(data["y"])
            j = next(
                (k for k, (cx, cy) in enumerate(self._cells) if cx == x and cy == y),
                None,
            )
            if j is not None:
                for i in range(self._n):
                    if self._stencil[i, j]:
                        self._state[i] ^= 1
            return self._render()
        return self._render()


class _FrameObs:
    def __init__(self, frame: np.ndarray):
        self.frame = [frame.tolist()]
        self.levels_completed = 0
        self.available_actions = [6]
        self.state = _State("NOT_FINISHED")


class _State:
    def __init__(self, name: str):
        self.name = name


def test_measure_toggle_stencil_identity():
    """Purpose: when each click toggles only its own cell (identity
    stencil), _measure_toggle_stencil must recover A = I.

    Expected feedback: failure means the measurement conflates cells
    or reset state carries over between probes — both would break
    R17's GF(2) solve on any real game.
    """
    cells = [(10, 10), (20, 20), (30, 30)]
    base_classes = [5, 5, 5]
    toggled_classes = [7, 7, 7]
    stencil = np.eye(3, dtype=np.uint8)
    env = _StencilEnv(cells, base_classes, toggled_classes, stencil)
    inf._ACTIVE_PREFIX.clear()
    A, bc, tc, used = inf._measure_toggle_stencil(
        env, cells, patch_radius=2, budget=200,
    )
    assert A.shape == (3, 3)
    assert np.array_equal(A, np.eye(3, dtype=np.uint8))
    assert bc == [5, 5, 5]
    assert tc == [7, 7, 7]
    assert used > 0


def test_measure_toggle_stencil_plus_shape():
    """Purpose: classic lights-out 'plus' stencil where clicking a
    center cell flips itself + 4 neighbors. _measure must recover A
    correctly across a 3-cell row.

    Expected feedback: failure means the stencil is being read as
    identity only (missing neighbor toggles) — R17 would under-solve.
    """
    cells = [(20, 32), (32, 32), (44, 32)]
    base_classes = [5, 5, 5]
    toggled_classes = [7, 7, 7]
    stencil = np.array(
        [
            [1, 1, 0],
            [1, 1, 1],
            [0, 1, 1],
        ],
        dtype=np.uint8,
    )
    env = _StencilEnv(cells, base_classes, toggled_classes, stencil)
    inf._ACTIVE_PREFIX.clear()
    A, _, _, _ = inf._measure_toggle_stencil(env, cells, patch_radius=2, budget=200)
    assert np.array_equal(A, stencil)


def test_measure_toggle_stencil_budget_cap():
    """Purpose: when the budget runs out mid-measurement, the
    function returns a partial A without crashing and reports used ≤
    budget (modulo the single in-flight click).

    Expected feedback: failure means the plan could exceed budget
    during observation, leaving nothing for the brute-force retry.
    """
    cells = [(10, 10), (20, 20), (30, 30), (40, 40), (50, 50)]
    base_classes = [5] * 5
    toggled_classes = [7] * 5
    stencil = np.eye(5, dtype=np.uint8)
    env = _StencilEnv(cells, base_classes, toggled_classes, stencil)
    inf._ACTIVE_PREFIX.clear()
    A, _, _, used = inf._measure_toggle_stencil(
        env, cells, patch_radius=2, budget=4,
    )
    assert used <= 6  # at most one extra action past the budget check
    assert A.shape == (5, 5)


def test_measure_toggle_stencil_records_toggled_classes_once_per_cell():
    """Purpose: toggled_classes[i] should latch on the first click
    that flips cell i and not overwrite on subsequent flips. Since
    every flip restores base then flips again to the same toggled
    color, this tests measurement integrity under repeated probing.

    Expected feedback: failure means R17 loses information about
    which visual class corresponds to 'on' for a given cell, so the
    target-state inference pass (base vs toggled) breaks.
    """
    cells = [(10, 10), (20, 20)]
    base_classes = [5, 5]
    toggled_classes = [7, 9]  # distinct toggled classes per cell
    stencil = np.ones((2, 2), dtype=np.uint8)  # every click flips both
    env = _StencilEnv(cells, base_classes, toggled_classes, stencil)
    inf._ACTIVE_PREFIX.clear()
    _, _, tc, _ = inf._measure_toggle_stencil(
        env, cells, patch_radius=2, budget=200,
    )
    assert tc == [7, 9]
