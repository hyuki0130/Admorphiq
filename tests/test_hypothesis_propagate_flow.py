"""Pins for the flow propagator's own mechanics, apart from the verifier that uses it.

Purpose
-------
The propagator IS the transition model for the FlowDeflection family — the
verifier's consistency check and the compiler's search oracle are the same code —
so a rule adopted here changes what every plan predicts. These pin the rules whose
first versions were adopted and reverted, and each was checked against its subject
by deleting that subject and re-running.

Expected feedback
-----------------
A failure means the propagator's mechanics moved. That is legitimate only with a
measurement behind it, so a red test here is a request for the evidence, not for a
fixture edit.
"""

from __future__ import annotations

from admorphiq.hypothesis_select.propagate_flow import ORACLE, Board, predict

SIZE = 10


def _sparse_frame_board() -> Board:
    """A board whose bottom frame is admitted at TWO cells, with the stream aimed
    at neither.

    Grounding only marks a hazard where it has evidence, so the rest of the frame
    row arrives unmarked — the exact shape of every captured sp80 board, where the
    row carries two marks and the engine's flow enters none of it."""
    return Board(
        pieces=(),
        sinks=(),
        hazard_cells=frozenset({(SIZE - 1, 1), (SIZE - 1, 4)}),
        emitter_cells=frozenset(),
        standing_flow=frozenset({(1, 7)}),
        size=SIZE,
    )


def test_flow_stops_above_a_sparsely_marked_frame() -> None:
    """The whole edge line a board's hazards sit on is impassable, not just the
    marked cells.

    Purpose: proves the frame band is treated as a wall across its full width.
    Expected feedback: a failure means flow is leaking into the columns grounding
    never marked — the 15-cell surplus this rule was adopted to remove."""
    prediction = predict(_sparse_frame_board(), ORACLE)
    reached = {cell for layer in prediction.frontier for cell in layer}
    assert not [c for c in reached if c[0] == SIZE - 1]
    assert (SIZE - 2, 7) in reached


def test_the_frame_band_is_a_wall_and_not_a_hazard() -> None:
    """Ending on the unmarked part of the frame is an ordinary boundary death.

    Purpose: guards the band's PLACEMENT, not its existence. Its subject is the
    wall branch rather than `_frame_band` — deleting the band entirely leaves this
    green, because at the outer edge a wall death and a boundary death are the same
    event, and that is checked. What it does catch is the band being folded into
    `hazard_cells`, the shape adopted and reverted earlier in this round: the ORACLE
    table answers terminate_fatal, so every ordinary boundary death would fail the
    attempt.
    Expected feedback: a failure means the band has become a hazard again, and the
    model mispredicts failure on layouts the engine is perfectly happy with."""
    prediction = predict(_sparse_frame_board(), ORACLE)
    assert prediction.fatal is False
    assert prediction.barrier_hits == 0


def test_a_marked_frame_cell_still_answers_to_the_hazard_slot() -> None:
    """The two cells grounding DID mark keep their hazard semantics.

    Purpose: the wall must not swallow the hazard slot, or the response table's
    hazard choice would stop being discriminating and every mutant that differs
    only there would score as the truth.
    Expected feedback: a failure means hazard contact is no longer detected, and
    the mutant table's hazard rows are no longer meaningful."""
    board = Board(
        pieces=(),
        sinks=(),
        hazard_cells=frozenset({(SIZE - 1, 1), (SIZE - 1, 4)}),
        emitter_cells=frozenset(),
        standing_flow=frozenset({(1, 4)}),
        size=SIZE,
    )
    prediction = predict(board, ORACLE)
    assert prediction.barrier_hits == 1
    assert prediction.fatal is True
