"""Contract pins for the jigsaw assemble tool's proposal shape.

Purpose: prove the tool never hands the harness an EMPTY proposal while its plan still owes work.
Expected feedback: a failure here means the loop will substitute a probe action for the tool's
silence, and on a board whose first simple action slides the selected piece that probe pushes the
tool's own arrangement off target — measured 2026-08-27 as six levels alone against one in the
harness, with no other symptom.
"""

from __future__ import annotations

import numpy as np

from admorphiq.tools.assemble import JigsawAssembleTool


def _seated(at: list[tuple[int, int]]) -> JigsawAssembleTool:
    """A tool mid-execution: one single-cell piece per entry, each already on its plan target."""
    tool = JigsawAssembleTool()
    tool._scale, tool._off, tool._cells = 1, 0, 8
    tool._forms = [[np.array([[3]])] for _ in at]
    tool._marks = [[np.array([[False]])] for _ in at]
    tool._closed = [True] * len(at)
    tool._cur = [0] * len(at)
    tool._at = list(at)
    tool._marker = 4
    tool._plan = [(i, 0, at[i]) for i in range(len(at))]
    tool._selected = 0
    return tool


def test_piece_already_on_target_does_not_yield_an_empty_proposal() -> None:
    """A piece owing no slide is skipped in the same call, not answered with silence."""
    tool = _seated([(1, 1), (5, 5)])
    steps = tool._execute(np.zeros((8, 8), dtype=int))
    assert steps, "a live plan must never propose nothing"
    # The first piece owes nothing, so the move handed back belongs to the SECOND one.
    assert steps[0][0] == 6, steps


def test_vacant_cell_is_one_no_piece_stands_on() -> None:
    """The last-resort idle click selects nothing — an occupied cell would select a piece."""
    tool = _seated([(0, 0), (1, 0)])
    cell = tool._vacant()
    assert cell not in tool._taken()
