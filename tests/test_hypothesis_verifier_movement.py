"""R96 step (iv) tests: the movement verifier — the frozen-mutant acceptance gate.

The load-bearing test runs the oracle + all 6 MUTANTS_MOVEMENT against the real
m0r0 trace and asserts the produced verdicts match the frozen expected table
EXACTLY (oracle PASS + 4 CONTRADICTED + 2 UNKNOWN). Plus structure-judgement units
(hash-variable action numbering) and the verify-only EmpiricalMoveMatrix.
"""

from __future__ import annotations

from admorphiq.hypothesis_select import schema_movement as SM
from admorphiq.hypothesis_select.schema import Verdict
from admorphiq.hypothesis_select.verifier_movement import (
    MovementEvidence,
    build_movement_evidence,
    load_trace,
    verify_with_evidence,
)


def _m0r0_evidence() -> MovementEvidence:
    return build_movement_evidence(load_trace("m0r0"), "m0r0")


def test_acceptance_gate_matches_the_frozen_mutant_verdict_table():
    """Purpose: on the real m0r0 trace the verifier returns the oracle PASS and the
    exact frozen verdict for every one of the 6 canonical mutants (4 CONTRADICTED +
    2 UNKNOWN), judging structure — not literal action numbers.

    Expected feedback: pass proves the verifier is sound on the decoded ground truth
    and its acceptance data (the mutant table) holds — the gate the round's model
    substages depend on. Fail (per the contract: investigate-don't-force) means a
    verdict diverged from the frozen expectation and the discriminator is wrong."""
    evidence = _m0r0_evidence()
    matrix: dict[str, Verdict] = {}

    oracle = verify_with_evidence(SM.m0r0_oracle_instance(), evidence)
    matrix["m0r0_oracle"] = oracle.verdict
    assert oracle.verdict is Verdict.PASS, f"oracle: {oracle}"

    for mutant in SM.MUTANTS_MOVEMENT:
        got = verify_with_evidence(mutant.instance, evidence)
        matrix[mutant.name] = got.verdict
        assert got.verdict is mutant.expected_verdict, (
            f"{mutant.name}: expected {mutant.expected_verdict}, got {got.verdict} "
            f"(transition={got.transition}, objective={got.objective}) — {mutant.reason}"
        )

    # the frozen shape: oracle PASS, 4 CONTRADICTED, 2 UNKNOWN
    verdicts = list(matrix.values())
    assert verdicts.count(Verdict.PASS) == 1
    assert verdicts.count(Verdict.CONTRADICTED) == 4
    assert verdicts.count(Verdict.UNKNOWN) == 2


def test_real_trace_evidence_reproduces_the_decoded_scheme():
    """Purpose: the evidence the verifier is built on is the decoded m0r0 ground
    truth — a merge observed, both actors mobile, a symmetric + antisymmetric-column
    coupling present, and (honestly) zero hazard cells.

    Expected feedback: pass proves the verifier judges against faithful evidence.
    Fail means the grounding->evidence bridge regressed."""
    ev = _m0r0_evidence()
    assert ev.merge_observed and ev.partner_moves
    assert ev.collision_obs > 0  # independent-stay evidence exists
    assert ev.hazard_cells == frozenset()  # gold enters no hazard (honest)
    from admorphiq.hypothesis_select.verifier_movement import _coupling_signature

    sig = _coupling_signature(ev.deltas)
    assert sig["symmetric"] and sig["antisym_col"] and not sig["static_actor"]


def test_transition_judged_by_structure_not_action_numbers():
    """Purpose: a delta table with the mirror structure under DIFFERENT action
    numbers than the acquired one still verifies PASS (the api_hash_rotation
    doctrine — action->axis numbering is hash-variable).

    Expected feedback: pass proves the verifier is hash-robust. Fail means it pins
    literal action ids and would reject a valid hypothesis on a rotated env hash."""
    ev = _m0r0_evidence()
    # the oracle fixture uses a DIFFERENT action->axis numbering than the trace, yet
    # its coupling structure matches -> PASS.
    v = verify_with_evidence(SM.m0r0_oracle_instance(), ev)
    assert v.transition is Verdict.PASS


def test_empirical_move_matrix_is_verify_only_footprint():
    """Purpose: EmpiricalMoveMatrix is judged by its footprint claim (single-cell
    PASS, multi-cell CONTRADICTED vs the observed single-cell moves) — a verify-only
    tag that never compiles.

    Expected feedback: pass proves the multi-cell move claim is checkable/rejectable
    at the verifier. Fail means the verify-only footprint judgement is missing."""
    ev = _m0r0_evidence()
    single = SM.MovementHypothesis(
        objective=SM.ActorRelation(actors=("actor_a", "actor_b"), relation="same_cell"),
        transition_model=SM.EmpiricalMoveMatrix(asserted_footprint=1),
        phases=(),
    )
    multi = SM.MovementHypothesis(
        objective=single.objective,
        transition_model=SM.EmpiricalMoveMatrix(asserted_footprint=5),
        phases=(),
    )
    assert verify_with_evidence(single, ev).transition is Verdict.PASS
    assert verify_with_evidence(multi, ev).transition is Verdict.CONTRADICTED
