"""Read the ACTION BUDGET off the frame.

⛔ Why this is load-bearing, measured 2026-08-27 from the sample games' own level data: **thirteen
of the twenty-five declare a per-level action budget and END THE GAME when it runs out** — 20
actions on one level, 13 on another, 32-320 typically. A searcher that opens hundreds of states
before acting has already lost, and the scorer keeps counting actions across the restart, so the
level's score is spent on the exploration rather than earned by it. That is the whole gap between
the generic path (0.0200 over the 25) and the hand-written adapters (0.3162).

The budget is DRAWN. Every instance seen is an edge-pinned indicator that shrinks or advances by a
roughly constant amount per action: a bar along a row, a counter marching sideways, a sprite
scrolling off screen. So it is readable without knowing the game:

  1. find the LINE in the outer band where cells stop matching their initial value — one row or
     one column, because an indicator is a segment, not a scatter;
  2. fit the consumption RATE (cells per action) along that line;
  3. remaining actions ~= cells of that line still matching / rate.

  ⛔ Step 1 is what makes it work. Counting the whole band instead put the static chrome into the
  numerator and overestimated every budget by roughly fifteen times — 768 where the game declares
  50. The indicator is a small part of the edge; the rest of the edge is furniture.

⛔ What this does NOT do: guess. With too few actions observed, or no monotone band, it returns
None and the caller must behave as though the budget were unknown. A wrong budget is worse than
no budget — it would either strangle a game that has none or licence overrun on one that does.
"""

from __future__ import annotations

from typing import Any

import numpy as np

__all__ = ["BudgetReader"]

# Actions to watch before a rate is trusted. Two points fit any line; the third is what makes it
# evidence. Deliberately small — the budgets being protected start at 13.
_MIN_SAMPLES = 4
# The indicator sits at the frame edge. Same reasoning, and the same fraction, as the HUD band in
# `tools/induce.py`: deliberately tiny, so real board content is never mistaken for chrome.
_MARGIN_DIV = 16


class BudgetReader:
    """Estimates the actions remaining in the current level from the frame alone."""

    def __init__(self) -> None:
        self._first: np.ndarray | None = None
        self._acted = 0
        self._line: tuple[str, int] | None = None   # ("row"|"col", index) of the indicator
        self._history: list[tuple[int, int]] = []   # (actions taken, cells of the line still matching)

    def reset(self) -> None:
        """A new level redraws the indicator, so nothing carries over."""
        self._first = None
        self._acted = 0
        self._line = None
        self._history.clear()

    def observe(self, frame: Any) -> None:
        grid = np.asarray(frame)
        if grid.ndim != 2:
            return
        if self._first is None or self._first.shape != grid.shape:
            self._first = grid.copy()
            self._acted = 0
            self._line = None
            self._history = []
            return
        self._acted += 1
        if self._line is None:
            self._line = self._find_line(grid)
        if self._line is None:
            return
        self._history.append((self._acted, self._matching(grid)))

    def _edge_mask(self, shape: tuple[int, int]) -> np.ndarray:
        h, w = shape
        m = max(1, min(h, w) // _MARGIN_DIV)
        edge = np.zeros(shape, dtype=bool)
        edge[:m, :] = edge[-m:, :] = True
        edge[:, :m] = edge[:, -m:] = True
        return edge

    def _find_line(self, grid: np.ndarray) -> tuple[str, int] | None:
        """The single row or column in the edge band holding every change so far."""
        assert self._first is not None
        diff = (grid != self._first) & self._edge_mask(grid.shape)
        ys, xs = np.nonzero(diff)
        if ys.size == 0:
            return None
        if np.unique(ys).size == 1:
            return ("row", int(ys[0]))
        if np.unique(xs).size == 1:
            return ("col", int(xs[0]))
        return None

    def _matching(self, grid: np.ndarray) -> int:
        assert self._first is not None and self._line is not None
        kind, idx = self._line
        cur = grid[idx, :] if kind == "row" else grid[:, idx]
        ref = self._first[idx, :] if kind == "row" else self._first[:, idx]
        return int((cur == ref).sum())

    def remaining(self) -> int | None:
        """Estimated actions left, or None when the frame does not show a budget."""
        if self._line is None or len(self._history) < _MIN_SAMPLES:
            return None
        acted = [a for a, _ in self._history]
        same = [s for _, s in self._history]
        if same[-1] >= same[0]:
            return None                              # nothing is being consumed
        # A budget indicator only ever shrinks. One tick upward means the band is showing
        # something else — an animation, a score, a board edge — and the reading is void.
        if any(b > a for a, b in zip(same, same[1:])):
            return None
        rate = (same[0] - same[-1]) / max(1, acted[-1] - acted[0])
        if rate <= 0:
            return None
        return int(same[-1] / rate)

    def total(self) -> int | None:
        """Estimated budget for the level as a whole (remaining + already spent)."""
        left = self.remaining()
        return None if left is None else left + self._acted
