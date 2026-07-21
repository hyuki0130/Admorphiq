"""Toggle / lights-out tool — learn the click stencil, solve the board over GF(2).

A whole class of click games (lights-out and relatives) work like this: the board
is a grid of ON/OFF cells, and a click at a cell FLIPS a fixed local pattern of
cells (itself + neighbours, a row/column, etc.). The level clears when the board
reaches a uniform target (all-off or all-on). Brute-force clicking never solves
these efficiently, but they are exactly solvable: over GF(2) each click is a fixed
toggle vector, and reaching the target is a linear system A·x = b (mod 2).

This tool is fully generic — it LEARNS each click's toggle stencil from the
agent's own observed (click → flipped-cells) transitions (no game ids, no sprite
tags), then, once it has enough stencils, solves the GF(2) system and proposes the
exact clicks that reach a uniform board. If the mechanic isn't a clean toggle, it
proposes nothing and its detect() stays low so the harness routes elsewhere.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from admorphiq.tools.base import (
    Step,
    availability,
    changed_mask,
    color_histogram,
    frame_2d,
    has_frame,
)

__all__ = ["ToggleTool"]

# A click's flipped-cell set counts as a toggle STENCIL only if it is small and
# local (lights-out flips ~1-5 cells), not a full-board repaint. The minimum
# stencil count before a solve is attempted lives in ``solver_core`` (the core
# owns the solve/probe decision).
_MAX_STENCIL = 12


def _binarize(frame: np.ndarray) -> tuple[np.ndarray, int, int]:
    """Reduce the board to a 0/1 grid: the most common colour is OFF (0), the
    rest ON (1). Returns (bits, off_color, on_color) — a two-colour board is the
    toggle-game assumption; a multi-colour board simply won't solve cleanly."""
    hist = color_histogram(frame)
    off = int(hist.argmax()) if hist.any() else 0
    on_candidates = [c for c in range(len(hist)) if hist[c] > 0 and c != off]
    on = on_candidates[0] if on_candidates else off
    bits = (frame != off).astype(np.uint8)
    return bits, off, on


def _gf2_solve(a: np.ndarray, b: np.ndarray) -> np.ndarray | None:
    """Solve A·x = b over GF(2) by Gaussian elimination. ``a`` is (n_cells,
    n_vars) uint8, ``b`` is (n_cells,) uint8. Returns one solution x (n_vars,)
    or None if inconsistent. Free variables are set to 0 (fewest clicks bias)."""
    m = np.concatenate([a.copy() % 2, (b.copy() % 2).reshape(-1, 1)], axis=1).astype(np.uint8)
    rows, cols = m.shape
    nvars = cols - 1
    pivot_col_of_row: list[int] = []
    r = 0
    for c in range(nvars):
        piv = None
        for rr in range(r, rows):
            if m[rr, c]:
                piv = rr
                break
        if piv is None:
            continue
        m[[r, piv]] = m[[piv, r]]
        for rr in range(rows):
            if rr != r and m[rr, c]:
                m[rr] ^= m[r]
        pivot_col_of_row.append(c)
        r += 1
        if r == rows:
            break
    # Consistency: any all-zero row on the left with a 1 on the right => no solution.
    for rr in range(rows):
        if not m[rr, :nvars].any() and m[rr, nvars]:
            return None
    x = np.zeros(nvars, dtype=np.uint8)
    for i, c in enumerate(pivot_col_of_row):
        x[c] = m[i, nvars]
    return x


class ToggleTool:
    """Lights-out solver as a harness :class:`Tool` (learn stencils → GF(2))."""

    name = "toggle"

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        # click (x, y) -> frozenset of flipped (row, col) cells (its stencil).
        # Kept for detect(); the solve/probe DECISION is delegated to solver_core.
        self._stencils: dict[tuple[int, int], frozenset[tuple[int, int]]] = {}
        self._prev_click: tuple[int, int] | None = None
        self._last_frame: np.ndarray = np.zeros((1, 1), dtype=np.int64)
        # Raw click transitions the core rebuilds stencils from (same dict shape
        # the code sandbox sees): {"action", "xy": [x, y], "before", "after"}.
        self._records: list[dict[str, Any]] = []
        self._trace: list[str] = []  # last propose()'s core decision log
        self._toggle_evidence = 0   # clicks that flipped a small local set
        self._click_evidence = 0    # clicks observed at all

    def detect(self, frames: list[Any], obs: Any) -> float:
        """HIGH once observed clicks consistently flip a SMALL local cell set on a
        low-colour board (the toggle signature); ~0 before any toggle evidence."""
        if self._click_evidence == 0:
            return 0.0
        ratio = self._toggle_evidence / self._click_evidence
        return 0.75 * ratio if ratio >= 0.5 else 0.1

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Learn the stencil of the click just taken: the set of cells it flipped
        (resolved against the frame supplied on the NEXT call, like the other
        tools' one-frame-delayed transitions)."""
        prev2d = _to_2d(prev)
        if self._prev_click is not None:
            flipped = changed_mask(self._last_frame, prev2d)
            if flipped.size and flipped.any():
                ys, xs = np.where(flipped)
                cells = frozenset(zip(map(int, ys), map(int, xs)))
                self._click_evidence += 1
                if 1 <= len(cells) <= _MAX_STENCIL:
                    self._toggle_evidence += 1
                    self._stencils[self._prev_click] = cells
            # Record the raw transition (regardless of flip size) so the core can
            # rebuild stencils from the SAME evidence the code sandbox would see.
            if self._last_frame.shape == prev2d.shape:
                self._records.append({
                    "action": "CLICK",
                    "xy": [self._prev_click[0], self._prev_click[1]],
                    "before": self._last_frame,
                    "after": prev2d,
                })
                self._records = self._records[-256:]
        self._prev_click = (int(action[1][0]), int(action[1][1])) if action[1] is not None else None
        self._last_frame = prev2d

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        """Delegate the solve-or-probe decision to ``solver_core.toggle_core`` —
        the SAME code the LLM patches and the code sandbox executes. The core
        rebuilds stencils from the recorded transitions, GF(2)-solves for a
        uniform board, and queues either the click plan or the next probe."""
        if not has_frame(obs):
            return []
        frame = frame_2d(obs)
        _, action6_ok = availability(obs)
        if not action6_ok:
            return []
        # Lazy import breaks the toggle <-> solver_core cycle (solver_core reuses
        # _gf2_solve / _binarize from this module).
        from admorphiq.tools.solver_core import toggle_core

        self._trace = []
        plan: list[Step] = []

        def _act(name: str, x: int | None = None, y: int | None = None) -> None:
            if x is not None and y is not None:
                plan.append((6, (int(x), int(y))))

        toggle_core(frame, self._records, _act, self._trace)
        return plan


def _to_2d(arr: Any) -> np.ndarray:
    a = np.asarray(arr)
    if a.ndim >= 3:
        a = a[0]
    return a.astype(np.int64)
