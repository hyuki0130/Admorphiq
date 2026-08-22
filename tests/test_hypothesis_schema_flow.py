"""R98 step (ii) tests: the FlowDeflectionDynamics family schema.

Pins the flow schema's contracts: neutral serialization is provenance-free and
round-trips exactly, the sp80 oracle encodes the mechanics that were certified
against the live engine, the gating tables match what the gated-enum test
MEASURED, the equivalence class protects a data-indistinguishable answer from
being scored wrong, and the frozen mutant table separates transition from
objective axes with honest UNKNOWNs. Schema only — no grounding/verifier/compiler.
"""

from __future__ import annotations

import pytest

from admorphiq.hypothesis_select import schema_flow as F
from admorphiq.hypothesis_select.schema import Ownership, Verdict


def test_sp80_oracle_is_the_certified_mechanics():
    """Purpose: the oracle instance encodes the response table whose reference
    propagator reproduced the engine's outcome on every reachable placement and
    its cell-exact trajectory on both probe placements — a direction-preserving
    cellwise split, mouth-only sink satisfaction with spreading on a miss, a fatal
    hazard, and a failed commit that keeps the LAYOUT while resetting flow,
    satisfaction and selection.

    Expected feedback: pass proves the fixture still matches
    scripts/rounds/R98/certification.txt and gated_enums.txt. Fail means the
    fixture drifted from the certified mechanics and every downstream stage is
    reasoning about a board the engine does not implement."""
    inst = F.sp80_oracle_instance()
    assert isinstance(inst.objective, F.CoverAllSinks)
    assert inst.objective.completion == "all"
    assert inst.objective.hazard_policy == "fatal_on_contact"

    tm = inst.transition_model
    assert isinstance(tm, F.PlaceThenPropagate)
    assert tm.control_mode == "select_then_translate"
    assert tm.observation_channel == "animation_layers"

    (_, piece), = tm.responses.piece_by_class
    assert (piece.spawn, piece.direction, piece.propagation) == (
        "empty_flanks_only",
        "preserved",
        "cellwise_iterative",
    )
    assert (tm.responses.sink.predicate, tm.responses.sink.miss) == (
        "same_sink_flanks",
        "spread_like_piece",
    )
    assert tm.responses.hazard == "terminate_fatal"

    fs = tm.failure_semantics
    assert (fs.layout, fs.flow, fs.sink_satisfaction, fs.selection) == (
        "persists",
        "resets",
        "resets",
        "resets_to_default",
    )


def test_inert_slots_default_to_unknown_and_are_not_gated():
    """Purpose: own_flow and boundary were MEASURED inert at the criterion level,
    so the schema must default them to UNKNOWN and the gating tables must exclude
    them.

    Expected feedback: pass proves the schema cannot force a closed choice out of
    absent evidence. Fail means a slot with no discriminating evidence is being
    scored, which manufactures false passes or false fails."""
    table = F.sp80_oracle_instance().transition_model.responses
    assert table.own_flow == F.UNKNOWN
    assert table.boundary == F.UNKNOWN
    assert F.NON_GATING_SLOTS == {"ResponseTable.own_flow", "ResponseTable.boundary"}
    assert not (F.NON_GATING_SLOTS & F.OUTCOME_GATED_SLOTS)
    assert not (F.NON_GATING_SLOTS & F.VERIFIER_GATED_SLOTS)


def test_gating_tables_match_the_measured_discriminability():
    """Purpose: the three gating tiers must be exactly what the live gated-enum
    test measured — five slots that change outcomes, one that changes only
    trajectories, two inert — and the tiers must be disjoint.

    Expected feedback: pass proves the contract's gated-slot list is the measured
    one. Fail means a slot is being gated at a level its evidence does not
    support, most dangerously piece_propagation, which never changes who wins."""
    assert F.OUTCOME_GATED_SLOTS == {
        "PieceResponse.spawn",
        "PieceResponse.direction",
        "SinkResponse.predicate",
        "SinkResponse.miss",
        "ResponseTable.hazard",
    }
    assert F.VERIFIER_GATED_SLOTS == {"PieceResponse.propagation"}
    assert not (F.OUTCOME_GATED_SLOTS & F.VERIFIER_GATED_SLOTS)
    gated = F.OUTCOME_GATED_SLOTS | F.VERIFIER_GATED_SLOTS
    assert gated <= F.FLOW_MODEL_SELECTED_SEMANTICS


def test_equivalence_class_protects_the_indistinguishable_spawn_answer():
    """Purpose: at the criterion level `both_flanks` is data-indistinguishable
    from the oracle's `empty_flanks_only` (the flanks are always empty when a
    split occurs), so scoring must accept either — the R95a ft09 precedent.

    Expected feedback: pass proves the scoring key records a CLASS. Fail means a
    model giving an answer the evidence cannot distinguish would be marked wrong,
    which is a false negative rather than a model failure."""
    classes = dict(F.EQUIVALENCE_CLASSES)
    assert "PieceResponse.spawn" in classes
    members = classes["PieceResponse.spawn"]
    (_, piece), = F.sp80_oracle_instance().transition_model.responses.piece_by_class
    assert piece.spawn in members
    assert "both_flanks" in members
    assert "none" not in members


def test_neutral_json_round_trips_the_oracle_and_every_mutant():
    """Purpose: to_neutral_json -> from_json reconstructs every canonical instance
    exactly, including the response table, the placement premises, the budget and
    the failure semantics.

    Expected feedback: pass proves the model-facing wire form is lossless, so a
    model's reply can be compared to a canonical instance by value. Fail means
    selection scoring would compare mangled structures."""
    instances = [F.sp80_oracle_instance()] + [m.instance for m in F.MUTANTS_FLOW]
    for inst in instances:
        assert F.from_json(F.to_neutral_json(inst)) == inst


def test_neutral_json_carries_no_provenance():
    """Purpose: the model must never see ownership labels, oracle/mutant names or
    game identifiers — the leakage prohibition every prior round froze.

    Expected feedback: pass proves the serialized form is leakage-free. Fail means
    the model could score by reading a label instead of by reasoning."""
    blob = repr(F.to_neutral_json(F.sp80_oracle_instance())).lower()
    for banned in ("sp80", "oracle", "mutant", "harness_measured", "model_selected",
                   "compiler_derived", "ownership"):
        assert banned not in blob


def test_ownership_marks_only_semantics_as_model_selected():
    """Purpose: the model chooses the response table and the objective's semantic
    slots; structure (footprints, deltas, emitters, budget, failure semantics)
    is harness-measured.

    Expected feedback: pass proves the boundary the review corrected is still in
    place. Fail means the model is being asked to select something it cannot
    ground, or is being credited for something the harness supplied."""
    own = F.FLOW_OWNERSHIP
    for structural in (
        "PlaceThenPropagate.piece_footprints",
        "PlaceThenPropagate.piece_deltas",
        "PlaceThenPropagate.emitters",
        "PlaceThenPropagate.budget",
        "PlaceThenPropagate.failure_semantics",
        "PlaceThenPropagate.placement_constraints",
    ):
        assert own[structural] is Ownership.HARNESS_MEASURED
    for semantic in ("PieceResponse.spawn", "SinkResponse.predicate", "ResponseTable.hazard"):
        assert own[semantic] is Ownership.MODEL_SELECTED
    assert "PlaceThenPropagate.responses" in own
    assert own["PlaceThenPropagate.responses"] is Ownership.MODEL_SELECTED


def test_mutants_are_distinct_split_by_axis_and_verdict_honestly():
    """Purpose: every mutant differs from the oracle, verdicts are only
    CONTRADICTED or UNKNOWN, both axes are represented separately (the review
    required transition and objective mutants to be reported apart), and the two
    measured-inert slots plus the unreachable partial cover are UNKNOWN rather
    than optimistically CONTRADICTED.

    Expected feedback: pass proves the frozen table is honest about what the
    criterion level can and cannot separate. Fail means a mutant is claimed
    discriminable without evidence, which would inflate the verifier's apparent
    power."""
    oracle = F.sp80_oracle_instance()
    names = [m.name for m in F.MUTANTS_FLOW]
    assert len(names) == len(set(names))

    for m in F.MUTANTS_FLOW:
        assert m.instance != oracle, m.name
        assert m.expected_verdict in (Verdict.CONTRADICTED, Verdict.UNKNOWN)
        assert m.axis in ("transition", "objective")
        assert m.reason.strip()

    by_name = {m.name: m for m in F.MUTANTS_FLOW}
    assert by_name["any_sink_suffices"].expected_verdict is Verdict.UNKNOWN
    assert by_name["flow_overwrites_own_trail"].expected_verdict is Verdict.UNKNOWN
    assert by_name["boundary_reflects"].expected_verdict is Verdict.UNKNOWN
    assert by_name["hazard_ignored"].expected_verdict is Verdict.CONTRADICTED
    assert by_name["hazard_ignored"].axis == "objective"
    assert {m.axis for m in F.MUTANTS_FLOW} == {"transition", "objective"}


def test_schema_rejects_out_of_vocabulary_and_incoherent_values():
    """Purpose: the closed choices are enforced by the type, and the completion
    quantifier is coupled to its count so `count` without a number (or `all` with
    one) is unrepresentable.

    Expected feedback: pass proves an invalid model reply fails at parse time with
    a named field rather than silently reaching the compiler. Fail means malformed
    hypotheses could execute."""
    with pytest.raises(ValueError, match="PieceResponse.spawn"):
        F.PieceResponse(spawn="teleport", direction="preserved", propagation="cellwise_iterative")
    with pytest.raises(ValueError, match="SinkResponse.predicate"):
        F.SinkResponse(predicate="whenever", miss="stop")
    with pytest.raises(ValueError, match="ResponseTable.hazard"):
        F.ResponseTable(
            piece_by_class=(("straight", F.PieceResponse("none", "preserved", "edge_teleport")),),
            sink=F.SinkResponse("contact", "stop"),
            hazard="explodes",
        )
    with pytest.raises(ValueError, match="completion_count"):
        F.CoverAllSinks(sink_roles=("s",), completion="count", hazard_policy="neutral")
    with pytest.raises(ValueError, match="completion_count"):
        F.CoverAllSinks(
            sink_roles=("s",), completion="all", hazard_policy="neutral", completion_count=2
        )
