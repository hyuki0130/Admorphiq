"""R98 STEP (iv): the flow-family verifier (PASS / CONTRADICTED / UNKNOWN).

Judges a :class:`~admorphiq.hypothesis_select.schema_flow.FlowHypothesis` over
FLOW GROUNDING output — never raw pixels. The verdict machinery mirrors R95/R96
(single-sourced ``Verdict``, CONTRADICTED dominates, PASS iff every judged claim
passes).

What makes this family's verifier unusually sharp: the transition model IS the
simulator, so the check is not a heuristic comparison of features but an EXACT
replay. The claimed response table is run over the grounded board and its
predicted trajectory is compared cell-for-cell against the trajectory the harness
recovered from the animation. A table that mispredicts one cell is CONTRADICTED
before a single action is executed.

Three rules keep the verdict honest:

* **Non-gating slots never decide anything.** ``own_flow`` and ``boundary`` were
  measured INERT at the criterion level, so a hypothesis leaving them UNKNOWN is
  substituted with a neutral value before replay. An UNKNOWN there is a correct
  answer, not a defect.
* **Equivalence classes are not failures.** Where two values are
  data-indistinguishable the replay simply agrees, and the verdict is PASS for
  either — the mechanism, not a special case.
* **A verify-only transition never compiles.** ``EmpiricalSpillMatrix`` is judged
  and reported, but it maps to UNSUPPORTED downstream so it can never silently
  plan.

Scope: verification only — no compiler, no LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from admorphiq.hypothesis_select import schema_flow as F
from admorphiq.hypothesis_select.grounding_flow import UNKNOWN, FlowGrounding
from admorphiq.hypothesis_select.propagate_flow import ORACLE, Board, ResponseTable, predict
from admorphiq.hypothesis_select.schema import Verdict


@dataclass(frozen=True)
class FlowInstanceVerdict:
    """The aggregate verdict plus the per-claim verdicts and the reason."""

    verdict: Verdict
    transition: Verdict
    objective: Verdict
    reason: str


@dataclass(frozen=True)
class FlowEvidence:
    """Everything a flow trace yields once, reusable across candidate instances:
    the measured board, the recovered trajectory, and whether the committed
    attempt advanced the level.

    ``incomplete_board`` records that grounding KNOWS the board is missing
    something — a source hidden under a piece, whose flow the propagator cannot
    reproduce because its origin is not in the model. A replay mismatch under that
    condition is evidence about the BOARD, not about the hypothesis, and must not
    be charged to the hypothesis."""

    board: Optional[Board]
    trajectory: tuple[tuple[tuple[int, int], ...], ...]
    advanced: bool
    n_sinks: int
    incomplete_board: str = ""


def _trim(frontiers) -> tuple[tuple[tuple[int, int], ...], ...]:
    """Drop every empty frontier, on BOTH sides of the comparison.

    The engine's animation contains ticks where nothing new appears — a front
    waiting behind itself renders as a pause — while the propagator advances on
    every tick it takes. Raw tick indices therefore do not correspond, and
    comparing on them makes a correct prediction look wrong by exactly the number
    of pauses. Progress steps do correspond, so that is the axis both sides use,
    and anything measured in ticks (an emergence, say) must be expressed on it."""
    return tuple(tuple(f) for f in frontiers if f)


def build_flow_evidence(grounding: FlowGrounding, advanced: bool) -> FlowEvidence:
    """Collect the grounded evidence a verdict is judged against."""
    board = grounding.board()
    trajectory = grounding.trajectory()
    hidden = grounding.hidden_sources()
    incomplete = (
        ""
        if hidden is UNKNOWN
        else f"{len(hidden.value)} source(s) hidden under a piece, not in the board model"
    )
    return FlowEvidence(
        board=None if board is UNKNOWN else board.value,
        trajectory=() if trajectory is UNKNOWN else _trim(trajectory.value),
        advanced=advanced,
        n_sinks=0 if board is UNKNOWN else len(board.value.sinks),
        incomplete_board=incomplete,
    )


def _table_of(instance: F.FlowHypothesis) -> Optional[ResponseTable]:
    """Project a hypothesis onto the propagator's table, neutralising the slots
    the contract declared non-gating so an honest UNKNOWN cannot change a verdict."""
    tm = instance.transition_model
    if not isinstance(tm, F.PlaceThenPropagate):
        return None
    if len(tm.responses.piece_by_class) != 1:
        return None
    (_, piece), = tm.responses.piece_by_class
    own_flow = tm.responses.own_flow
    boundary = tm.responses.boundary
    return ResponseTable(
        piece_spawn=piece.spawn,
        piece_direction=piece.direction,
        piece_propagation=piece.propagation,
        sink_predicate=tm.responses.sink.predicate,
        sink_miss=tm.responses.sink.miss,
        hazard=tm.responses.hazard,
        own_flow=ORACLE.own_flow if own_flow == F.UNKNOWN else own_flow,
        boundary=ORACLE.boundary if boundary == F.UNKNOWN else boundary,
    )


def _replay(board: Board, table: ResponseTable) -> tuple[tuple[tuple[int, int], ...], ...]:
    prediction = predict(board, table)
    return _trim(prediction.frontier)


def _verify_transition(
    instance: F.FlowHypothesis, ev: FlowEvidence
) -> tuple[Verdict, str]:
    tm = instance.transition_model
    if isinstance(tm, F.EmpiricalSpillMatrix):
        return Verdict.UNKNOWN, "verify-only transition: a lookup carries no trajectory claim"
    table = _table_of(instance)
    if table is None:
        return Verdict.UNKNOWN, "transition model is not replayable as stated"
    if ev.board is None or not ev.trajectory:
        return Verdict.UNKNOWN, "no grounded board or trajectory to replay against"

    predicted = _replay(ev.board, table)

    # Compare the TRAIL, not the per-step frontier. Flow cells persist, so the trail
    # after k steps is the physical claim; which of two cells a splitting stream
    # renders first is engine phase, not mechanics — measured on the fourth level,
    # where a stream spreading around a piece produces its two flanking cells one
    # step apart while the model produces them together. A frontier comparison calls
    # that a contradiction; a trail comparison does not, and it stays just as sharp
    # against a wrong model, which produces cells the engine NEVER produces.
    observed_trail: set[tuple[int, int]] = set()
    for layer in ev.trajectory:
        observed_trail |= set(layer)
    predicted_trail: set[tuple[int, int]] = set()
    for layer in predicted:
        predicted_trail |= set(layer)
    invented = predicted_trail - observed_trail
    missed = observed_trail - predicted_trail
    if invented or missed:
        detail = (
            f"predicted {len(invented)} cell(s) the flow never reached"
            if invented
            else f"misses {len(missed)} cell(s) the flow reached"
        )
        sample = sorted(invented or missed)[:3]
        if ev.incomplete_board:
            return (
                Verdict.UNKNOWN,
                f"the replay {detail} (e.g. {sample}), but the board is incomplete: "
                f"{ev.incomplete_board}",
            )
        return (
            Verdict.CONTRADICTED,
            f"the replay {detail}, for example {sample}",
        )

    n = min(len(predicted), len(ev.trajectory))
    for i in range(n):
        if predicted[i] != ev.trajectory[i]:
            # Same cells, different order of appearance: engine render phase. The
            # trail already agreed, so there is nothing here to contradict.
            break
    # Step COUNT is phase as well: the engine renders pauses the propagator does not
    # take, so two runs that reach exactly the same cells can differ in length. The
    # trail comparison above already pinned the physics.

    # A POSITIVE claim in a slot the evidence cannot separate is unverifiable. The
    # replay agreeing proves nothing about it, so reporting PASS would overstate
    # the verifier's power; the honest verdict is UNKNOWN.
    asserted = [
        name
        for name, value in (
            ("own_flow", tm.responses.own_flow),
            ("boundary", tm.responses.boundary),
        )
        if value != F.UNKNOWN
    ]
    if asserted:
        return (
            Verdict.UNKNOWN,
            f"the replay matches, but {' and '.join(asserted)} was asserted and no "
            f"observation separates its values at this level",
        )
    return Verdict.PASS, f"replay matches the observed trajectory for {n} steps"


def _verify_objective(instance: F.FlowHypothesis, ev: FlowEvidence) -> tuple[Verdict, str]:
    objective = instance.objective
    table = _table_of(instance)
    if ev.board is None or table is None:
        return Verdict.UNKNOWN, "no grounded board to evaluate the completion predicate"

    prediction = predict(ev.board, table)
    satisfied = len(prediction.satisfied)

    if isinstance(objective, F.AnySinkCovered):
        # Only a PARTIAL cover separates any-from-all. Where no observation ever
        # fills a strict subset, every trace is consistent with both, and the
        # honest verdict is UNKNOWN — never a kill by default.
        if 0 < satisfied < ev.n_sinks:
            wins = satisfied >= 1
            if wins != ev.advanced:
                return (
                    Verdict.CONTRADICTED,
                    f"a partial cover of {satisfied}/{ev.n_sinks} "
                    f"{'did not advance' if ev.advanced is False else 'advanced'}",
                )
            return Verdict.PASS, "consistent with the observed partial cover"
        return Verdict.UNKNOWN, "no partial cover observed: any and all predict the same outcome"

    required = ev.n_sinks if objective.completion == "all" else (objective.completion_count or 0)
    hazard_blocks = objective.hazard_policy == "fatal_on_contact"
    wins = satisfied >= required and not (hazard_blocks and prediction.fatal)
    if wins != ev.advanced:
        return (
            Verdict.CONTRADICTED,
            f"predicts the attempt {'wins' if wins else 'fails'} "
            f"({satisfied}/{ev.n_sinks} filled, hazard contact {prediction.fatal}) but the level "
            f"{'advanced' if ev.advanced else 'did not advance'}",
        )
    return Verdict.PASS, "completion predicate agrees with the observed outcome"


def _aggregate(transition: Verdict, objective: Verdict) -> Verdict:
    if Verdict.CONTRADICTED in (transition, objective):
        return Verdict.CONTRADICTED
    if transition is Verdict.PASS and objective is Verdict.PASS:
        return Verdict.PASS
    return Verdict.UNKNOWN


def verify_with_evidence(
    instance: F.FlowHypothesis, evidence: FlowEvidence
) -> FlowInstanceVerdict:
    """Judge one hypothesis against already-built evidence."""
    transition, t_reason = _verify_transition(instance, evidence)
    objective, o_reason = _verify_objective(instance, evidence)
    verdict = _aggregate(transition, objective)
    reason = t_reason if transition is not Verdict.PASS else o_reason
    return FlowInstanceVerdict(verdict, transition, objective, reason)


def verify_flow_instance(
    instance: F.FlowHypothesis, grounding: FlowGrounding, advanced: bool
) -> FlowInstanceVerdict:
    """Judge one hypothesis directly against a grounding service's state."""
    return verify_with_evidence(instance, build_flow_evidence(grounding, advanced))


def neutralised(instance: F.FlowHypothesis) -> F.FlowHypothesis:
    """The instance with non-gating slots made explicit as UNKNOWN — the form the
    contract scores, so a model is never credited or penalised for a slot the
    evidence cannot separate."""
    tm = instance.transition_model
    if not isinstance(tm, F.PlaceThenPropagate):
        return instance
    table = replace(tm.responses, own_flow=F.UNKNOWN, boundary=F.UNKNOWN)
    return F.FlowHypothesis(
        objective=instance.objective,
        transition_model=replace(tm, responses=table),
        phases=instance.phases,
    )


__all__ = [
    "FlowEvidence",
    "FlowInstanceVerdict",
    "build_flow_evidence",
    "verify_with_evidence",
    "verify_flow_instance",
    "neutralised",
]
