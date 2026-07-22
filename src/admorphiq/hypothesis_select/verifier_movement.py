"""R96 STEP (iv): the movement-family verifier (PASS / CONTRADICTED / UNKNOWN).

Judges a :class:`~admorphiq.hypothesis_select.schema_movement.MovementHypothesis`
over MOVEMENT GROUNDING output — never raw pixels. Verdict machinery + aggregation
mirror the R95 cell-state verifier (single-sourced ``Verdict`` + the same
CONTRADICTED-dominates / PASS-iff-both aggregate shape).

Claims verified:

* **transition** (``CoupledGridStep``) — judged on the acquired per-actor deltas by
  STRUCTURE, not literal action numbers: the mirror scheme is "a symmetric pair +
  an antisymmetric-column pair present", because the action->axis numbering is
  hash-variable (api_hash_rotation doctrine). A claim that an actor is STATIC while
  the grounding observed it move, or that lacks the observed antisymmetric column
  coupling, is CONTRADICTED. ``collision_policy`` is judged against the collision
  evidence (``all_or_nothing`` CONTRADICTED once a one-moved-one-stayed desync is
  observed; ``independent_stay`` is consistent with it). ``terminal_cells``:
  ``hazard_soft_reset`` is the unrefuted default; ``blocking_wall`` is a POSITIVE
  claim needing a hazard-block observation — absent one (0 hazard cells) it is
  honest UNKNOWN, and CONTRADICTED if hazards were seen to soft-reset instead.
  ``EmpiricalMoveMatrix`` is VERIFY-ONLY (its footprint is judged; it never
  compiles).
* **objective** (``ActorRelation``) — judged on the terminal evidence: ``same_cell``
  PASSes iff a MERGE event was observed at the win (CONTRADICTED if the actors
  never coincide); ``adjacent`` / ``overlap`` are honest UNKNOWN (no near-terminal
  non-merge negative separates exact merge from adjacency, per the frozen mutant
  table); a role bound to a NON-actor (static) region is CONTRADICTED because the
  partner is observed to move.

Aggregation: any CONTRADICTED => CONTRADICTED; PASS iff transition PASS AND
objective PASS; else UNKNOWN.

Scope: verification only — no compiler, no LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from admorphiq.hypothesis_select import schema_movement as M
from admorphiq.hypothesis_select.grounding import UNKNOWN, GroundingService
from admorphiq.hypothesis_select.schema import Verdict
from admorphiq.hypothesis_select.verifier import VTransition, load_trace

_ACTOR_ROLES = frozenset({"actor_a", "actor_b"})


@dataclass(frozen=True)
class MovementInstanceVerdict:
    """The aggregate verdict + the per-claim verdicts."""

    verdict: Verdict
    transition: Verdict
    objective: Verdict


@dataclass(frozen=True)
class MovementEvidence:
    """The grounded movement evidence a game's trace yields once, reusable across
    hypotheses: the acquired per-(actor, action) deltas, the collision-stay count,
    whether a merge terminal was observed, whether the actors move, and the hazard
    cells."""

    deltas: dict[tuple[str, int], tuple[int, int]]
    collision_obs: int
    merge_observed: bool
    partner_moves: bool
    hazard_cells: frozenset[tuple[int, int]]


def build_movement_evidence(trace: list[VTransition], game: str) -> MovementEvidence:
    """Feed the trace's gold directional transitions through a fresh grounding and
    read off the movement evidence (deltas / collision / merge / hazard). Doing this
    ONCE per game and verifying many instances against it mirrors the R95 pattern."""
    gs = GroundingService()
    for t in trace:
        if t.is_gold and 1 <= t.action <= 4:
            gs.feed_transition(t.before, t.action, t.xy, t.after)
    deltas_g = gs.movement_deltas()
    deltas = {} if deltas_g is UNKNOWN else dict(deltas_g.value)
    collision = gs.movement_collision_evidence()
    merge = gs.movement_merge_event()
    hazards = gs.movement_hazard_cells()
    return MovementEvidence(
        deltas=deltas,
        collision_obs=0 if collision is UNKNOWN else int(collision.value),
        merge_observed=merge is not UNKNOWN,
        partner_moves=any(d != (0, 0) for d in deltas.values()),
        hazard_cells=frozenset() if hazards is UNKNOWN else frozenset(hazards.value),
    )


def _coupling_signature(deltas: dict[tuple[str, int], tuple[int, int]]) -> dict[str, bool]:
    """The STRUCTURAL signature of a per-actor delta table: which coupling TYPES are
    present across actions — symmetric (both actors move the same), antisymmetric in
    columns / rows (opposite), or a static actor. Action-number-invariant."""
    by_action: dict[int, dict[str, tuple[int, int]]] = {}
    for (aid, action), delta in deltas.items():
        by_action.setdefault(action, {})[aid] = delta
    sig = {"symmetric": False, "antisym_col": False, "antisym_row": False, "static_actor": False}
    for pair in by_action.values():
        a, b = pair.get("actor_a"), pair.get("actor_b")
        if a is None or b is None:
            continue
        if a == (0, 0) or b == (0, 0):
            sig["static_actor"] = True
        if a == b and a != (0, 0):
            sig["symmetric"] = True
        if a[1] == -b[1] and a[1] != 0:
            sig["antisym_col"] = True
        if a[0] == -b[0] and a[0] != 0:
            sig["antisym_row"] = True
    return sig


def _verify_transition(tm: Any, ev: MovementEvidence) -> Verdict:
    if isinstance(tm, M.EmpiricalMoveMatrix):
        if tm.asserted_footprint is None:
            return Verdict.UNKNOWN
        return Verdict.PASS if tm.asserted_footprint == 1 else Verdict.CONTRADICTED
    if not isinstance(tm, M.CoupledGridStep):
        return Verdict.UNKNOWN
    if not ev.deltas:
        return Verdict.UNKNOWN  # min-probe: no acquired deltas to judge against
    acquired = _coupling_signature(ev.deltas)
    claim = _coupling_signature(
        {(role, action): (dr, dc) for role, action, dr, dc in tm.per_action_deltas}
    )
    if claim["static_actor"] and not acquired["static_actor"]:
        return Verdict.CONTRADICTED  # claims an actor never moves; both are observed to move
    if acquired["antisym_col"] and not claim["antisym_col"]:
        return Verdict.CONTRADICTED  # claim lacks the observed antisymmetric column coupling
    if claim["symmetric"] != acquired["symmetric"] or claim["antisym_col"] != acquired["antisym_col"]:
        return Verdict.CONTRADICTED  # the coupling structure does not match the observed scheme
    if tm.collision_policy == "all_or_nothing" and ev.collision_obs > 0:
        return Verdict.CONTRADICTED  # a one-moved-one-stayed desync refutes all-or-nothing
    if tm.terminal_cells == "blocking_wall":
        # a positive claim: hazards impassable. Needs a hazard-block observation.
        return Verdict.CONTRADICTED if ev.hazard_cells else Verdict.UNKNOWN
    return Verdict.PASS


def _verify_objective(obj: Any, ev: MovementEvidence) -> Verdict:
    if not isinstance(obj, M.ActorRelation):
        return Verdict.UNKNOWN
    if not set(obj.actors) <= _ACTOR_ROLES:
        # a role bound to a NON-actor (static) region — the partner actually moves
        return Verdict.CONTRADICTED if ev.partner_moves else Verdict.UNKNOWN
    if obj.relation == "same_cell":
        return Verdict.PASS if ev.merge_observed else Verdict.CONTRADICTED
    return Verdict.UNKNOWN  # adjacent / overlap: no near-terminal negative to separate them


def _aggregate(transition: Verdict, objective: Verdict) -> Verdict:
    if Verdict.CONTRADICTED in (transition, objective):
        return Verdict.CONTRADICTED
    if transition == Verdict.PASS and objective == Verdict.PASS:
        return Verdict.PASS
    return Verdict.UNKNOWN


def verify_with_evidence(instance: M.MovementHypothesis, evidence: MovementEvidence) -> MovementInstanceVerdict:
    """Verify a movement hypothesis against pre-built :class:`MovementEvidence`."""
    transition = _verify_transition(instance.transition_model, evidence)
    objective = _verify_objective(instance.objective, evidence)
    return MovementInstanceVerdict(_aggregate(transition, objective), transition, objective)


def verify_movement_instance(
    instance: M.MovementHypothesis, trace: list[VTransition], game: str
) -> MovementInstanceVerdict:
    """The aggregate verdict for a movement hypothesis on ``game``'s trace."""
    return verify_with_evidence(instance, build_movement_evidence(trace, game))


__all__ = [
    "MovementInstanceVerdict",
    "MovementEvidence",
    "build_movement_evidence",
    "verify_with_evidence",
    "verify_movement_instance",
    "load_trace",
]
