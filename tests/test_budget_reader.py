"""Contract pins for reading the on-screen action budget.

Engine-free: the frames are built here, so these hold on a clean checkout.
"""

from __future__ import annotations

import numpy as np

from admorphiq.tools.budget import BudgetReader


def _frame(consumed: int, size: int = 64) -> np.ndarray:
    """A board with a bar along the bottom row that shrinks one cell per action."""
    g = np.zeros((size, size), dtype=int)
    g[10:20, 10:20] = 3                     # some board content, well away from the edge
    g[size - 1, :] = 7
    if consumed:
        g[size - 1, size - consumed:] = 0
    return g


def test_reads_a_shrinking_bar_as_a_budget() -> None:
    """Purpose: pin the estimate against a bar whose budget is known by construction.

    64 cells consumed one per action is a 64-action budget. Passing means the reader recovers it
    from four observations. Failing means the searcher has no idea how many actions it may spend —
    and thirteen of the twenty-five sample games END THE GAME when that number is exceeded, at
    budgets as low as 13.
    """
    r = BudgetReader()
    for k in range(6):
        r.observe(_frame(k))
    assert r.total() is not None
    assert abs(r.total() - 64) <= 6


def test_counts_only_the_indicator_line_not_the_whole_edge() -> None:
    """Purpose: pin the fix for the defect that made every estimate ~15x too large.

    Passing means static chrome elsewhere on the edge does not inflate the remaining count.
    Failing means the reader licenses overrun on every game that draws anything at its border.
    """
    r = BudgetReader()
    for k in range(6):
        g = _frame(k)
        g[0, :] = 5                          # a static banner on the opposite edge
        g[:, 0] = 5
        r.observe(g)
    assert abs(r.total() - 64) <= 6


def test_returns_none_when_nothing_is_being_consumed() -> None:
    """Purpose: pin the refusal. A wrong budget is worse than no budget.

    Passing means a board with no indicator yields None, so the caller keeps treating the budget
    as unknown. Failing means a game with no budget gets strangled by an invented one.
    """
    r = BudgetReader()
    for _ in range(6):
        r.observe(_frame(0))
    assert r.total() is None


def test_returns_none_when_the_band_goes_back_up() -> None:
    """Purpose: pin that an animation in the border is not read as a budget.

    A budget indicator only ever shrinks. Passing means one tick upward voids the reading.
    Failing means a blinking or oscillating border produces a confident wrong number — the same
    shape of error as the oscillating edge band that had to be killed in the flow grounding.
    """
    r = BudgetReader()
    for k in (0, 1, 2, 1, 3, 4):
        r.observe(_frame(k))
    assert r.total() is None
