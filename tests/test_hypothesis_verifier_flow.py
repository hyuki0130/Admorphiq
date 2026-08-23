"""R98 step (iv) tests: the flow-family verifier.

Pins what stops a wrong hypothesis from ever executing. The family's verifier is
an EXACT replay — the claimed response table is run as a simulator and compared
cell-for-cell against the recovered trajectory — so these tests pin that a
mispredicting table dies, that an honest UNKNOWN in a slot the evidence cannot
separate is neither rewarded nor punished, and that a verify-only transition never
reaches PASS.
"""

from __future__ import annotations

from admorphiq.hypothesis_select import schema_flow as F
from admorphiq.hypothesis_select.propagate_flow import ORACLE, Board, predict
from admorphiq.hypothesis_select.schema import Verdict
from admorphiq.hypothesis_select.verifier_flow import (
    FlowEvidence,
    neutralised,
    verify_with_evidence,
)

# A miniature board with the same structure as the criterion level: one emitter
# column, one horizontal piece, two mouth-notch sinks, a barrier row.
SIZE = 10
# A layout whose stream is walked out to columns 2 and 6 — straight into both
# mouths, so the attempt wins.
WIN_PIECE = frozenset({(3, 3), (3, 4), (3, 5)})
# A layout whose stream emerges one column WIDE of each mouth. The corner spread
# still fills both sinks, but a second branch runs on to the barrier, so the
# attempt fails despite full coverage. This is the layout that makes the sink
# predicate and the hazard policy discriminating, and it mirrors the criterion
# level's own +2 placement.
PIECE = frozenset({(3, 2), (3, 3), (3, 4)})
SINK_A = frozenset({(7, 1), (7, 3), (8, 1), (8, 2), (8, 3)})
SINK_B = frozenset({(7, 5), (7, 7), (8, 5), (8, 6), (8, 7)})
BARRIER = frozenset({(9, c) for c in range(SIZE)})


def _board(piece: frozenset = PIECE) -> Board:
    return Board(
        pieces=(piece,),
        sinks=(SINK_A, SINK_B),
        hazard_cells=BARRIER,
        emitter_cells=frozenset(),
        standing_flow=frozenset({(1, 4)}),
        size=SIZE,
    )


def _evidence(board: Board) -> FlowEvidence:
    """Evidence as the harness would recover it: the engine's own behaviour is
    stood in for by the ORACLE table, which was measured to reproduce it exactly."""
    prediction = predict(board, ORACLE)
    return FlowEvidence(
        board=board,
        trajectory=tuple(tuple(f) for f in prediction.frontier if f),
        advanced=prediction.wins,
        n_sinks=len(board.sinks),
    )


def _with(**changes):
    """The oracle instance with response-table slots overridden."""
    base = F.sp80_oracle_instance()
    tm = base.transition_model
    name, piece = tm.responses.piece_by_class[0]
    piece = F.PieceResponse(
        spawn=changes.get("spawn", piece.spawn),
        direction=changes.get("direction", piece.direction),
        propagation=changes.get("propagation", piece.propagation),
    )
    sink = F.SinkResponse(
        predicate=changes.get("sink_predicate", tm.responses.sink.predicate),
        miss=changes.get("sink_miss", tm.responses.sink.miss),
    )
    table = F.ResponseTable(
        piece_by_class=((name, piece),),
        sink=sink,
        hazard=changes.get("hazard", tm.responses.hazard),
        own_flow=changes.get("own_flow", tm.responses.own_flow),
        boundary=changes.get("boundary", tm.responses.boundary),
    )
    from dataclasses import replace

    return F.FlowHypothesis(
        objective=base.objective,
        transition_model=replace(tm, responses=table),
        phases=base.phases,
    )


def test_the_oracle_table_passes_its_own_evidence():
    """Purpose: the response table that reproduces the engine must verify against
    a trajectory produced by that same behaviour.

    Expected feedback: pass proves the verifier accepts the truth. Fail means the
    gate would reject a correct hypothesis and no model could ever succeed."""
    for piece in (WIN_PIECE, PIECE):
        verdict = verify_with_evidence(F.sp80_oracle_instance(), _evidence(_board(piece)))
        assert verdict.verdict is Verdict.PASS
        assert verdict.transition is Verdict.PASS
        assert verdict.objective is Verdict.PASS


def test_a_mispredicting_table_is_contradicted_and_names_the_offending_cells():
    """Purpose: a table that predicts a different FLOW must die, and the reason must
    name cells — either ones the flow never reached, or ones it reached and the
    prediction missed.

    The comparison is on the TRAIL rather than the per-step frontier: flow cells
    persist, so the trail is the physical claim, while which of two cells a
    splitting stream renders first is engine phase. A frontier comparison calls that
    phase difference a contradiction; the trail does not, and stays just as sharp
    against a wrong model — which produces cells the engine never produces.

    Expected feedback: pass proves wrong hypotheses are blocked BEFORE any action is
    executed, with cell-level attribution. Fail means either a wrong model survives
    or a right one is failed for render phase."""
    for changed in ({"spawn": "none"}, {"direction": "outward_turned"},
                    {"propagation": "edge_teleport"}, {"sink_predicate": "contact"}):
        verdict = verify_with_evidence(_with(**changed), _evidence(_board()))
        assert verdict.verdict is Verdict.CONTRADICTED, changed
        assert verdict.transition is Verdict.CONTRADICTED, changed
        assert "cell(s)" in verdict.reason


def test_render_phase_alone_is_not_a_contradiction():
    """Purpose: two runs that reach exactly the same cells, differing only in the
    order the cells appear, describe the same world. The verdict must not be
    CONTRADICTED.

    Expected feedback: pass proves the verifier judges mechanics, not animation
    timing. Fail means a correct hypothesis dies on any board whose engine renders a
    split one step apart — measured on the fourth level, where it does."""
    board = _board()
    evidence = _evidence(board)
    shuffled = FlowEvidence(
        board=evidence.board,
        # same cells, redistributed across steps
        trajectory=tuple((c,) for layer in evidence.trajectory for c in layer),
        advanced=evidence.advanced,
        n_sinks=evidence.n_sinks,
    )
    verdict = verify_with_evidence(F.sp80_oracle_instance(), shuffled)
    assert verdict.verdict is not Verdict.CONTRADICTED


def test_a_claim_in_a_slot_the_evidence_cannot_separate_is_unknown_not_pass():
    """Purpose: own_flow and boundary were measured INERT. A hypothesis that
    ASSERTS one of them cannot be verified, so reporting PASS would overstate the
    verifier's power — the verdict must be UNKNOWN. Leaving them UNKNOWN is the
    correct answer and must still PASS.

    Expected feedback: pass proves the verifier neither credits nor penalises an
    unverifiable claim. Fail means the mutant table's honest UNKNOWNs would turn
    into false confidence."""
    asserted = verify_with_evidence(_with(own_flow="overwrite"), _evidence(_board()))
    assert asserted.verdict is Verdict.UNKNOWN
    assert "separates" in asserted.reason

    honest = verify_with_evidence(F.sp80_oracle_instance(), _evidence(_board()))
    assert honest.verdict is Verdict.PASS


def test_a_verify_only_transition_never_passes():
    """Purpose: EmpiricalSpillMatrix names a claim without a propagation model, so
    it can be reported but never verified.

    Expected feedback: pass proves a lookup cannot masquerade as a verified
    model."""
    base = F.sp80_oracle_instance()
    instance = F.FlowHypothesis(
        objective=base.objective,
        transition_model=F.EmpiricalSpillMatrix(asserted_entries=4),
        phases=base.phases,
    )
    verdict = verify_with_evidence(instance, _evidence(_board()))
    assert verdict.verdict is Verdict.UNKNOWN
    assert verdict.transition is Verdict.UNKNOWN


def test_an_objective_that_disagrees_with_the_outcome_is_contradicted():
    """Purpose: the completion predicate is judged against what actually happened.
    A hazard-neutral objective predicts a win on a layout that filled every sink
    yet failed, so it must be CONTRADICTED even though its trajectory is right.

    Expected feedback: pass proves transition and objective are judged separately,
    which is what lets the round report the two axes apart."""
    board = _board()
    prediction = predict(board, ORACLE)
    assert prediction.fatal and len(prediction.satisfied) == 2, "fixture must fill all and fail"

    base = F.sp80_oracle_instance()
    neutral = F.FlowHypothesis(
        objective=F.CoverAllSinks(
            sink_roles=("sink_0", "sink_1"), completion="all", hazard_policy="neutral"
        ),
        transition_model=base.transition_model,
        phases=base.phases,
    )
    verdict = verify_with_evidence(neutral, _evidence(board))
    assert verdict.verdict is Verdict.CONTRADICTED
    assert verdict.transition is Verdict.PASS
    assert verdict.objective is Verdict.CONTRADICTED


def test_neutralised_strips_positive_claims_from_non_gating_slots():
    """Purpose: the contract scores the neutralised form, so a model is never
    credited or penalised for a slot the evidence cannot separate.

    Expected feedback: pass proves the scoring form exists and is idempotent on an
    already-honest instance."""
    stripped = neutralised(_with(own_flow="overwrite", boundary="reflect"))
    table = stripped.transition_model.responses
    assert table.own_flow == F.UNKNOWN and table.boundary == F.UNKNOWN
    assert neutralised(F.sp80_oracle_instance()) == F.sp80_oracle_instance()


def test_a_known_board_gap_is_not_charged_to_the_hypothesis():
    """Purpose: when grounding KNOWS the board is missing something — a source
    hidden under a piece, whose flow no model built from this board could predict —
    a replay mismatch is evidence about the BOARD, not about the hypothesis. The
    verdict must be UNKNOWN, never CONTRADICTED.

    Expected feedback: pass proves a correct hypothesis cannot be failed for a
    grounding gap the harness already detected. Fail means the model stage would
    score a right answer as wrong on any level with a concealed source."""
    board = _board()
    evidence = _evidence(board)
    # a trajectory carrying flow the board cannot produce, exactly as a concealed
    # source does
    contaminated = FlowEvidence(
        board=evidence.board,
        trajectory=evidence.trajectory[:2] + (((0, 0),),) + evidence.trajectory[2:],
        advanced=evidence.advanced,
        n_sinks=evidence.n_sinks,
        incomplete_board="1 source(s) hidden under a piece, not in the board model",
    )
    verdict = verify_with_evidence(F.sp80_oracle_instance(), contaminated)
    assert verdict.verdict is Verdict.UNKNOWN
    assert "incomplete" in verdict.reason

    # without the flag, the same mismatch IS charged to the hypothesis
    plain = FlowEvidence(
        board=contaminated.board,
        trajectory=contaminated.trajectory,
        advanced=contaminated.advanced,
        n_sinks=contaminated.n_sinks,
    )
    assert verify_with_evidence(F.sp80_oracle_instance(), plain).verdict is Verdict.CONTRADICTED


def test_an_absorber_swallows_the_stream_without_satisfying_or_killing():
    """Purpose: idx3 carries a solid block wearing the target colour that the ENGINE
    satisfies — it recolours when the spill reaches it — while no candidate table has
    a rule that ever satisfies a region with no notch to be flanked at. It cannot be a
    sink, and it is not a hazard: contact is not fatal. Left out of the board, our flow
    ran straight through what the engine's flow ended at.

    Expected feedback: pass proves an absorber ends the stream that reaches it, counts
    for nothing, and does not kill the attempt. Fail means a board with one of these
    predicts flow downstream of it that the engine never produces."""
    from dataclasses import replace as _replace

    plain = _board(WIN_PIECE)
    baseline = predict(plain, ORACLE)
    assert baseline.satisfied, "the control layout should satisfy something"

    # put an absorber directly under the stream, above the sinks
    blocked = _replace(plain, absorber_cells=frozenset({(5, c) for c in range(SIZE)}))
    stopped = predict(blocked, ORACLE)

    assert not stopped.satisfied, "an absorber must not satisfy anything"
    assert not stopped.fatal, "an absorber is not a hazard"
    reached = {c for layer in stopped.frontier for c in layer}
    assert not any(r >= 5 for r, _ in reached), \
        f"flow continued past the absorber: {sorted(c for c in reached if c[0] >= 5)}"


def test_a_falling_source_lands_on_whatever_is_topmost_in_its_lane():
    """Purpose: an emergence records where a stream was SEEN to appear, so it is tied
    to the layout it was seen under and cannot be replayed once a plan moves the
    pieces. A LANE can: the stream lands on whatever is topmost in it, which is
    computable for a layout never observed. Measured on idx3 — sliding the covering
    piece one row moved the sighting one row with it while the lane stayed put.

    The tick is on the replay's own axis, where index 0 is the seed frontier — the
    same convention emergences already use.

    Expected feedback: pass proves the injected stream appears just short of the first
    thing in its lane, and moves when that obstacle moves. Fail means the model can
    only predict layouts it has already watched."""
    from dataclasses import replace as _replace

    lane = 4
    high = _replace(_board(frozenset({(3, 3), (3, 4), (3, 5)})),
                    standing_flow=frozenset(), falling_sources=((lane, 2),))
    low = _replace(high, pieces=(frozenset({(5, 3), (5, 4), (5, 5)}),))

    def _first(board):
        cells = [c for layer in predict(board, ORACLE).frontier for c in layer]
        return [c for c in cells if c[1] == lane][:1]

    assert _first(high) == [(2, lane)], f"expected a landing above row 3: {_first(high)}"
    assert _first(low) == [(4, lane)], f"the landing did not follow the piece: {_first(low)}"
