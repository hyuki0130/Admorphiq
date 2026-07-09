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
# local (lights-out flips ~1-5 cells), not a full-board repaint.
_MAX_STENCIL = 12
# Learn at least this many distinct click stencils before attempting a solve.
_MIN_STENCILS = 4


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
        # click (x, y) -> frozenset of flipped (row, col) cells (its stencil)
        self._stencils: dict[tuple[int, int], frozenset[tuple[int, int]]] = {}
        self._prev_click: tuple[int, int] | None = None
        self._last_frame: np.ndarray = np.zeros((1, 1), dtype=np.int64)
        self._solution: list[Step] | None = None
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
                    self._solution = None  # new evidence invalidates a stale plan
        self._prev_click = (int(action[1][0]), int(action[1][1])) if action[1] is not None else None
        self._last_frame = prev2d

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        """Once enough stencils are known, solve the board over GF(2) and return
        the clicks that reach a uniform target; otherwise probe an unclicked cell
        to learn more stencils."""
        if not has_frame(obs):
            return []
        frame = frame_2d(obs)
        _, action6_ok = availability(obs)
        if not action6_ok:
            return []

        if self._solution:
            return self._solution[:]

        if len(self._stencils) >= _MIN_STENCILS:
            plan = self._solve_board(frame)
            if plan:
                self._solution = plan
                return plan[:]

        # Not enough evidence yet: probe a cell we haven't clicked, to learn a
        # new stencil (grid-ordered so coverage is systematic).
        probe = self._next_probe(frame)
        return [probe] if probe is not None else []

    # ── solving ──────────────────────────────────────────────────────────────

    def _solve_board(self, frame: np.ndarray) -> list[Step] | None:
        """Build A·x = b over GF(2) from the learned stencils and current board,
        for BOTH uniform targets (all-off / all-on); return the click plan for
        whichever solves with the fewest clicks."""
        bits, _off, _on = _binarize(frame)
        h, w = bits.shape
        clicks = sorted(self._stencils)
        cell_index = {(r, c): r * w + c for r in range(h) for c in range(w)}
        n_cells = h * w
        a = np.zeros((n_cells, len(clicks)), dtype=np.uint8)
        for j, click in enumerate(clicks):
            for (r, c) in self._stencils[click]:
                if 0 <= r < h and 0 <= c < w:
                    a[cell_index[(r, c)], j] = 1

        best: list[Step] | None = None
        for target in (0, 1):
            b = ((bits.reshape(-1) ^ target) % 2).astype(np.uint8)
            x = _gf2_solve(a, b)
            if x is None:
                continue
            plan = [(6, (int(clicks[j][0]), int(clicks[j][1]))) for j in range(len(clicks)) if x[j]]
            if plan and (best is None or len(plan) < len(best)):
                best = plan
        return best

    def _next_probe(self, frame: np.ndarray) -> Step | None:
        """A click on a cell not yet clicked — coarse grid order so stencils are
        learned across the board, not clustered."""
        h, w = frame.shape
        step = max(1, min(h, w) // 8)
        for y in range(step // 2, h, step):
            for x in range(step // 2, w, step):
                if (x, y) not in self._stencils and (x, y) != self._prev_click:
                    return (6, (int(x), int(y)))
        return None


def _to_2d(arr: Any) -> np.ndarray:
    a = np.asarray(arr)
    if a.ndim >= 3:
        a = a[0]
    return a.astype(np.int64)
