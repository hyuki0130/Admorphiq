"""R96 step (ii) tests: the ControlledGridDynamics movement-family schema.

Pins the movement schema's contracts: neutral serialization is provenance-free
and round-trips exactly, the family does not silently cross-product with the
cell-state family, ownership is correct (only the relation + role bindings +
guards are model_selected), and the m0r0 oracle + the 6 frozen mutants are the
decoded ground truth. Schema only — no grounding/verifier/compiler.
"""

from __future__ import annotations

from admorphiq.hypothesis_select import schema_movement as M
from admorphiq.hypothesis_select.schema import Ownership, Verdict


def test_m0r0_oracle_is_the_decoded_coupled_merge():
    """Purpose: the m0r0 oracle encodes the decoded mechanics — an exact-merge
    ActorRelation (same_cell), antisymmetric COLUMNS (action 1 diverges / action 4
    converges) with symmetric ROWS, independent-stay collision, and hazard
    soft-reset (not walls).

    Expected feedback: pass proves the oracle instance is faithful to
    .wiki/wiki/games/M0R0.md §L1 (the ground truth the selection + verifier stages
    depend on). Fail means the fixture drifted from the decoded scheme."""
    inst = M.m0r0_oracle_instance()
    assert inst.objective.relation == "same_cell"
    assert inst.objective.actors == ("actor_a", "actor_b")
    tm = inst.transition_model
    assert isinstance(tm, M.CoupledGridStep)
    assert tm.collision_policy == "independent_stay"
    assert tm.terminal_cells == "hazard_soft_reset"
    assert isinstance(tm.occupancy, M.StaticOccupancy)
    deltas = {(role, action): (dr, dc) for role, action, dr, dc in tm.per_action_deltas}
    # columns antisymmetric on actions 1 and 4
    assert deltas[("actor_a", 1)] == (0, -1) and deltas[("actor_b", 1)] == (0, 1)
    assert deltas[("actor_a", 4)] == (0, 1) and deltas[("actor_b", 4)] == (0, -1)
    # rows symmetric on actions 2 and 3
    assert deltas[("actor_a", 2)] == deltas[("actor_b", 2)] == (-1, 0)
    assert deltas[("actor_a", 3)] == deltas[("actor_b", 3)] == (1, 0)


def test_neutral_json_round_trips_the_oracle_and_every_mutant():
    """Purpose: to_neutral_json -> from_json reconstructs every canonical instance
    exactly (the oracle and all 6 mutants), including the typed occupancy and the
    per-actor deltas.

    Expected feedback: pass proves the model sees a faithful, reconstructable spec
    and the round-trip is lossless (the selection stage's serialize/deserialize
    contract). Fail means serialization dropped or altered a field."""
    for inst in [M.m0r0_oracle_instance()] + [m.instance for m in M.MUTANTS_MOVEMENT]:
        assert M.from_json(M.to_neutral_json(inst)) == inst


def test_serialized_form_carries_no_provenance_or_game_id():
    """Purpose: the neutral JSON of the oracle + every mutant exposes no game id, no
    'oracle'/'mutant' label, and no ownership tag — only neutral structural tags +
    values + neutral role names.

    Expected feedback: pass proves a model's pick cannot be driven by a leaked
    provenance token. Fail means a game id / ownership tag / oracle hint reached the
    model-facing serialization."""
    import json

    for inst in [M.m0r0_oracle_instance()] + [m.instance for m in M.MUTANTS_MOVEMENT]:
        blob = json.dumps(M.to_neutral_json(inst)).lower()
        for token in ("m0r0", "dc22", "tu93", "oracle", "mutant", "harness_measured", "model_selected", "ownership"):
            assert token not in blob, f"leaked {token!r}"


def test_movement_from_json_rejects_cell_state_cross_products():
    """Purpose: the movement family does NOT silently accept a cell-state objective
    or transition — from_json raises a field-named error on a foreign kind, so the
    two families cannot cross-product into an unrepresentable hybrid.

    Expected feedback: pass proves the schema boundary between families is enforced
    at deserialization (the cross-product-unrepresentability guarantee). Fail means
    a glyph/cycle tag would be accepted into a movement instance."""
    oracle = M.to_neutral_json(M.m0r0_oracle_instance())

    bad_objective = {**oracle, "objective": {"kind": "glyph_relational", "actors": ["a", "b"], "relation": "x"}}
    try:
        M.from_json(bad_objective)
        raise AssertionError("expected a foreign objective kind to be rejected")
    except ValueError as exc:
        assert "objective" in str(exc)

    bad_transition = {**oracle, "transition_model": {"kind": "ordered_cycle", "order": [9, 8, 12]}}
    try:
        M.from_json(bad_transition)
        raise AssertionError("expected a foreign transition kind to be rejected")
    except ValueError as exc:
        assert "transition_model" in str(exc)


def test_ownership_pins_only_relation_bindings_and_guards_as_model_selected():
    """Purpose: ownership is correct — only the ActorRelation relation + actor-role
    bindings (and the shared Phase.guard) are model_selected; the deltas, occupancy,
    collision policy, terminal cells, and identified actors are harness_measured.

    Expected feedback: pass proves the model never authors a harness-measured value
    (the R95 ownership discipline extended to motion). Fail means a measured field
    leaked into the model's writable set (or vice versa)."""
    model_selected = {k for k, v in M.MOVEMENT_OWNERSHIP.items() if v is Ownership.MODEL_SELECTED}
    assert model_selected == {"ActorRelation.actors", "ActorRelation.relation"}
    assert M.MOVEMENT_MODEL_SELECTED_SEMANTICS == {
        "ActorRelation.actors", "ActorRelation.relation", "Phase.guard",
    }
    for measured in (
        "CoupledGridStep.actors", "CoupledGridStep.per_action_deltas",
        "CoupledGridStep.collision_policy", "CoupledGridStep.occupancy",
        "CoupledGridStep.terminal_cells", "EmpiricalMoveMatrix.asserted_footprint",
    ):
        assert M.MOVEMENT_OWNERSHIP[measured] is Ownership.HARNESS_MEASURED


def test_frozen_mutant_set_is_six_single_field_deviations_with_verdicts():
    """Purpose: the frozen mutant table is exactly the 6 decoded m0r0 mutants, each a
    single-field deviation from the oracle, each carrying its expected verdict + a
    reason (honest UNKNOWN where the trace cannot discriminate).

    Expected feedback: pass proves the verifier round has its acceptance data (the
    2 UNKNOWN cases — adjacency near-miss + no-hazard-entry — are recorded honestly,
    the 4 CONTRADICTED cases name their refuting observation). Fail means a mutant is
    missing, mislabeled, or not a clean single-field deviation."""
    names = {m.name for m in M.MUTANTS_MOVEMENT}
    assert names == {
        "m0r0_adjacent_relation", "m0r0_static_goal_not_relation", "m0r0_single_actor_motion",
        "m0r0_same_delta_both_actors", "m0r0_all_or_nothing_blocking", "m0r0_hazard_as_wall",
    }
    by_name = {m.name: m for m in M.MUTANTS_MOVEMENT}
    assert by_name["m0r0_adjacent_relation"].expected_verdict is Verdict.UNKNOWN
    assert by_name["m0r0_hazard_as_wall"].expected_verdict is Verdict.UNKNOWN
    for contradicted in (
        "m0r0_static_goal_not_relation", "m0r0_single_actor_motion",
        "m0r0_same_delta_both_actors", "m0r0_all_or_nothing_blocking",
    ):
        assert by_name[contradicted].expected_verdict is Verdict.CONTRADICTED
    for m in M.MUTANTS_MOVEMENT:
        assert m.reason and m.instance != M.m0r0_oracle_instance()  # a real deviation with a reason


def test_empirical_move_matrix_is_representable_as_a_verify_only_transition():
    """Purpose: EmpiricalMoveMatrix is schema-representable and round-trips (so the
    verify/mutant path can name it), distinct from the executable CoupledGridStep.

    Expected feedback: pass proves the verify-only tag exists in the schema (the
    compiler will later map it to UNSUPPORTED). Fail means the tag is missing and a
    multi-cell move claim could not be verified/rejected."""
    inst = M.MovementHypothesis(
        objective=M.ActorRelation(actors=("actor_a", "actor_b"), relation="same_cell"),
        transition_model=M.EmpiricalMoveMatrix(asserted_footprint=5),
        phases=(),
    )
    assert M.from_json(M.to_neutral_json(inst)) == inst
