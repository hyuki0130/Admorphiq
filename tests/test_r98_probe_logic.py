"""Pins for the two pure functions in R98's probes whose silent breakage already cost this
round a wrong finding.

Purpose
-------
Most round scripts need a live engine and cannot be unit-tested. These two do not, and both
have a history: `_continued` corrected the step-off stop count from nine to four by asking
whether a walk resumed later, and the side-derivation in the spread sweep once used a parity
expression on a cell's coordinates and scored a rule nobody had measured.

Expected feedback
-----------------
A failure means a probe is back to reporting the number it reported before it was corrected,
and any table taken from it is that table again.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_R98 = Path(__file__).resolve().parents[1] / "scripts" / "rounds" / "R98"
sys.path.insert(0, str(_R98))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"r98_{name}", _R98 / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"r98_{name}"] = module
    spec.loader.exec_module(module)
    return module


walk_probe = _load("walk_probe")
spread_sweep = _load("spread_sweep")

from admorphiq.hypothesis_select.propagate_flow import Board  # noqa: E402


def _board(pieces: tuple = (frozenset({(5, 4), (5, 5), (5, 6)}),)) -> Board:
    return Board(
        pieces=pieces,
        sinks=(),
        hazard_cells=frozenset(),
        emitter_cells=frozenset(),
        standing_flow=frozenset(),
        size=10,
    )


def test_a_walk_that_resumes_later_is_not_a_stop() -> None:
    """Purpose: pins the check that took the step-off stop count from nine to four. A run is
    followed through CONSECUTIVE layers, so a walk that pauses and resumes reads as two runs
    and the join reads as a stop — five of nine "stops" were exactly that.
    Expected feedback: a failure means the probe counts pauses as stops again, and the
    resulting table over-reports refusals by more than it reports."""
    layers = [{(4, 4)}, {(4, 3)}, set(), {(4, 2)}]
    assert walk_probe._continued(layers, (4, 2)) is True
    assert walk_probe._continued(layers, (4, 1)) is False


def test_support_is_read_along_the_flow_and_the_edge_counts_as_supported() -> None:
    """Purpose: every extent in the walk table is cut by this, and an out-of-bounds cell must
    count as supported — a droplet at the board's edge is not standing over free space.
    Expected feedback: a failure flips the support pattern of every walked cell, which is what
    the `####.` strings in the round's tables are made of."""
    board = _board()
    assert walk_probe._supported(board, (4, 5)) is True     # a piece directly below
    assert walk_probe._supported(board, (4, 1)) is False    # nothing below
    assert walk_probe._supported(board, (9, 1)) is True     # the board's edge


def test_the_walking_side_comes_from_the_flank_index_not_the_coordinates() -> None:
    """Purpose: the sweep's first version derived which flank it was looking at from a parity
    expression on the cell's own coordinates. It scored 332 and would have been reported as a
    refutation of a rule nobody had implemented; taking the side from the index the propagator
    builds the flanks with gave 196.

    Expected feedback: a failure means the sweep is once again scoring a rule that is not the
    one described, and any verdict from it is about nothing."""
    board = _board()
    flanks = ((4, 3), (4, 7))          # (cell - lateral, cell + lateral) for downward flow
    wall: frozenset = frozenset()
    # index 0 walks outward to LOWER columns and index 1 to higher; the piece under (5,4..6)
    # supports the inner side, so the runs must differ by which index is asked.
    assert spread_sweep._support_run(board, flanks[0], (0, -1), (1, 0), wall) == 0
    assert spread_sweep._support_run(board, flanks[1], (0, 1), (1, 0), wall) == 0
    assert spread_sweep._support_run(board, (4, 4), (0, -1), (1, 0), wall) == 1
