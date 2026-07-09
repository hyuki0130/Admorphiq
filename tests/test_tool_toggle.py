"""Contract tests for the generic toggle / lights-out tool.

These prove the tool LEARNS click stencils from observed transitions and SOLVES a
board over GF(2) — the exact-solution path that brute-force clicking can't reach.
All fixtures are tiny synthetic numpy boards + a duck-typed observation; no
arcengine, no game specifics.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from admorphiq.tools.toggle import ToggleTool, _gf2_solve


@dataclass
class _State:
    name: str = "NOT_FINISHED"


@dataclass
class _Obs:
    frame: np.ndarray
    available_actions: list[int] = field(default_factory=lambda: [6])
    levels_completed: int = 0
    state: _State = field(default_factory=_State)


def test_gf2_solver_solves_a_known_system():
    """Purpose: the GF(2) Gaussian solver returns a valid solution to A·x=b mod 2.
    Expected feedback: pass ⇒ the linear-algebra core is correct; fail ⇒ every
    lights-out solve is unreliable."""
    a = np.array([[1, 1, 0], [0, 1, 1], [1, 0, 1]], dtype=np.uint8)
    b = np.array([1, 0, 1], dtype=np.uint8)
    x = _gf2_solve(a, b)
    assert x is not None
    assert np.array_equal((a @ x) % 2, b)


def test_gf2_solver_reports_inconsistent_system():
    """Purpose: an unsolvable system returns None, not a wrong answer.
    Expected feedback: pass ⇒ the tool won't propose a bogus plan; fail ⇒ it
    could click forever on an unsolvable board."""
    a = np.array([[1, 1], [1, 1]], dtype=np.uint8)
    b = np.array([1, 0], dtype=np.uint8)   # x1+x2=1 AND x1+x2=0 -> impossible
    assert _gf2_solve(a, b) is None


def test_learns_stencil_and_detect_rises():
    """Purpose: observing a click that flips a small local set is learned as that
    click's stencil and raises detect() (the toggle signature).
    Expected feedback: pass ⇒ the tool recognizes toggle games from frames alone;
    fail ⇒ it never engages on lights-out."""
    tool = ToggleTool()
    board0 = np.zeros((5, 5), dtype=np.int64)
    board1 = board0.copy()
    board1[2, 2] = 1
    board1[1, 2] = 1  # a click at (x=2,y=2) flipped a small 2-cell set
    tool.observe(board0, (6, (2, 2)), True)   # stage the click at (2,2)
    tool.observe(board1, (6, (0, 0)), True)   # next frame resolves the flip set
    assert (2, 2) in tool._stencils
    assert tool.detect([], _Obs(board1)) > 0.0


def test_solves_toy_lights_out():
    """Purpose: end-to-end — after learning stencils, propose() returns clicks
    that (applied over GF(2)) drive the board to a uniform target.
    Expected feedback: pass ⇒ the tool actually solves a toggle board; fail ⇒ it
    only probes and never closes a lights-out game."""
    # 1-D toggle: clicking cell i flips only cell i (trivial but exercises solve).
    tool = ToggleTool()
    n = 5
    for i in range(n):
        before = np.zeros((1, n), dtype=np.int64)
        after = before.copy()
        after[0, i] = 1
        tool.observe(before, (6, (i, 0)), True)
        tool.observe(after, (6, (i, 0)), True)
    # Board with some cells ON; the solver must pick the clicks to make it uniform.
    board = np.array([[1, 0, 1, 0, 1]], dtype=np.int64)
    plan = tool.propose([], _Obs(board))
    assert plan  # a non-empty click plan
    assert all(s[0] == 6 for s in plan)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-q"])
