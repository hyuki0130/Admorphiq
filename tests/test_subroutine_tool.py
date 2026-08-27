"""Contract tests for the subroutine tool's frame-only reading and its selectivity."""

from __future__ import annotations

import numpy as np

from admorphiq.tools.subroutine import Board, SubroutineProgramTool

BG = 4
BACKING = 5


class _Obs:
    """The slice of the observation API the tool reads."""

    def __init__(self, grid: np.ndarray) -> None:
        self.frame = [grid.tolist()]
        self.available_actions = [5, 6, 7]
        self.levels_completed = 0
        self.state = "NOT_FINISHED"


def _board(target_colours: list[int], slots: int, tray: list[tuple[str, int]]) -> np.ndarray:
    """A minimal board in the grammar: a target row, one rectangle of empty sockets, a tray."""
    g = np.full((64, 64), BG, dtype=np.int64)
    for i, colour in enumerate(target_colours):
        y, x = 1, 10 + 7 * i
        g[y:y + 6, x:x + 6] = colour
        g[y + 1:y + 5, x + 1:x + 5] = BACKING
    width = 6 + 6 * (slots - 1) + 4
    g[20:30, 10:10 + width] = 8
    g[21:29, 11:9 + width] = BG
    for i in range(slots):
        sy, sx = 23, 13 + 6 * i
        g[sy + 1:sy + 3, sx + 1:sx + 3] = 2
    for i, (kind, colour) in enumerate(tray):
        y, x = 57, 10 + 8 * i
        g[y:y + 4, x:x + 4] = colour
        if kind == "call":
            g[y + 1:y + 3, x + 1:x + 3] = BG
    return g


def test_reads_targets_sockets_and_tray_from_pixels_alone() -> None:
    """Purpose: pin that the board's grammar — target row, socket lattice, tray — is recovered
    from colour geometry only, with no coordinate, size or palette supplied.

    Expected feedback: a failure means the perception no longer separates the three regions, and
    every plan built on it is fiction rather than merely suboptimal.
    """
    g = _board([9, 11], slots=2, tray=[("emit", 9), ("emit", 11)])
    board = Board(g)
    assert board.targets == [9, 11]
    assert len(board.rects) == 1
    assert board.rects[0]["colour"] == 8
    assert board.content[0] == [None, None]
    assert sorted(board.tray.values()) == [("emit", 9), ("emit", 11)]


def test_places_the_token_the_program_needs_first() -> None:
    """Purpose: pin that the tool bids on a solved program and that its first move picks up the
    token the interpreter reaches first and drops it on that socket.

    Expected feedback: a failure means the synthesised program is not being turned into the two
    clicks the engine charges as one placement.
    """
    obs = _Obs(_board([9, 11], slots=2, tray=[("emit", 11), ("emit", 9)]))
    tool = SubroutineProgramTool()
    assert tool.detect([], obs) > 0.0
    # The tray is deliberately in the wrong order: the first socket demands colour 9, the second
    # tray token, so a tool that simply consumed the tray left-to-right would fail here.
    assert tool.propose([], obs) == [(6, (18, 57)), (6, (14, 24))]


def test_no_bid_without_the_tokens_to_finish() -> None:
    """Purpose: pin the selectivity rule — a board in the right SHAPE but missing the tokens the
    program needs draws no bid at all.

    Expected feedback: a failure means the tool would claim a game it cannot finish, which costs
    whichever tool could have solved it its entire budget.
    """
    obs = _Obs(_board([9, 11], slots=2, tray=[("emit", 9)]))
    assert SubroutineProgramTool().detect([], obs) == 0.0
