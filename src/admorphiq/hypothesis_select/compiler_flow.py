"""R98 STEP (v): the flow-family compiler (schema instance -> executable plan).

Given a verified :class:`~admorphiq.hypothesis_select.schema_flow.FlowHypothesis`
and a live :class:`~admorphiq.hypothesis_select.grounding_flow.FlowGrounding`,
emit the action sequence a driver steps. Dispatch is on SCHEMA TAGS ONLY — never a
game id, no adapter imports, the same quarantine as grounding and the verifier.

One compilable plan (the family's executable arm):

* **CoverAllSinks x PlaceThenPropagate -> placement search under the claimed
  response table.** The search enumerates placements reachable by the measured
  per-action deltas, runs the MODEL'S OWN response table as the simulator over the
  grounded board, and keeps a placement whose predicted settle satisfies the
  objective. The plan is the translation sequence plus the commit.

This is where the family's design claim pays: the compiler never consults a
hardcoded notion of how flow behaves, so a wrong response table produces a
confidently wrong plan that the live spill falsifies. Reusing a fixed simulator
here would make every hypothesis plan identically and the whole selection stage
meaningless.

Two arms are deliberately not executable:

* ``EmpiricalSpillMatrix`` — a lookup carries no propagation model, so it maps to
  the typed ``UNSUPPORTED`` terminal rather than silently planning.
* ``AnySinkCovered`` — the verify-only objective. It exists so a mutant can name
  it; it never plans.

Action ids come from the board's OWN measured delta table, because the
action-id <-> delta numbering is hash-variable per board. The instance supplies the
model-selected semantics; grounding supplies the live world.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from admorphiq.hypothesis_select import schema_flow as F
from admorphiq.hypothesis_select.compiler import PlanStatus
from admorphiq.hypothesis_select.grounding_flow import UNKNOWN, FlowGrounding
from admorphiq.hypothesis_select.propagate_flow import ORACLE, Board, ResponseTable, predict

MAX_OFFSET = 24  # placement search bound; a board is far smaller than this


@dataclass(frozen=True)
class FlowPlan:
    """A placement plan: the action ids to press, then the commit action.

    ``status`` is SOLVABLE with a sequence, or a typed failure surface. ``offset``
    records the chosen placement relative to the piece's current position, and
    ``predicted_satisfied`` how many sinks the claimed table expects to fill —
    the attribution hooks the live gate reads when a plan is wrong.
    """

    status: PlanStatus
    actions: tuple[int, ...] = ()
    offset: tuple[int, int] = (0, 0)
    predicted_satisfied: int = 0
    reason: str = ""


def _table_of(instance: F.FlowHypothesis) -> Optional[ResponseTable]:
    tm = instance.transition_model
    if not isinstance(tm, F.PlaceThenPropagate) or len(tm.responses.piece_by_class) != 1:
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


def _wins(board: Board, table: ResponseTable, objective: F.CoverAllSinks) -> tuple[bool, int]:
    prediction = predict(board, table)
    satisfied = len(prediction.satisfied)
    required = len(board.sinks) if objective.completion == "all" else (
        objective.completion_count or 0
    )
    fatal_blocks = objective.hazard_policy == "fatal_on_contact"
    return (satisfied >= required and not (fatal_blocks and prediction.fatal)), satisfied


def _path_to(offset: tuple[int, int], deltas: dict[int, tuple[int, int]]) -> Optional[tuple[int, ...]]:
    """The shortest action sequence realising a translation offset, using only the
    measured deltas. Returns None when no combination of measured actions reaches
    it — an honest failure rather than an invented press."""
    want_r, want_c = offset
    if (want_r, want_c) == (0, 0):
        return ()
    seq: list[int] = []
    for axis, want in ((0, want_r), (1, want_c)):
        if want == 0:
            continue
        step = None
        for action, (dr, dc) in sorted(deltas.items()):
            d = (dr, dc)[axis]
            other = (dr, dc)[1 - axis]
            if other == 0 and d != 0 and (d > 0) == (want > 0):
                step = (action, abs(d))
                break
        if step is None or abs(want) % step[1]:
            return None
        seq.extend([step[0]] * (abs(want) // step[1]))
    return tuple(seq)


def compile_flow_hypothesis(
    instance: F.FlowHypothesis, grounding: FlowGrounding
) -> FlowPlan:
    """Compile one hypothesis into a placement plan against live grounding."""
    tm = instance.transition_model
    if isinstance(tm, F.EmpiricalSpillMatrix):
        return FlowPlan(PlanStatus.UNSUPPORTED,
                        reason="a lookup transition carries no propagation model")
    if isinstance(instance.objective, F.AnySinkCovered):
        return FlowPlan(PlanStatus.UNSUPPORTED,
                        reason="verify-only objective: it names a claim, it does not plan")

    table = _table_of(instance)
    if table is None:
        return FlowPlan(PlanStatus.UNSUPPORTED, reason="transition model is not replayable")

    board_q = grounding.board()
    deltas_q = grounding.piece_deltas()
    commit_q = grounding.commit_action()
    if UNKNOWN in (board_q, deltas_q, commit_q):
        return FlowPlan(PlanStatus.GROUNDING_INCOMPLETE,
                        reason="the board, the delta table or the commit action is not grounded")

    board = board_q.value
    deltas = {action: (dr, dc) for action, dr, dc in deltas_q.value}
    commit = commit_q.value

    best: Optional[FlowPlan] = None
    for dr in range(-MAX_OFFSET, MAX_OFFSET + 1):
        for dc in range(-MAX_OFFSET, MAX_OFFSET + 1):
            moved = board.moved(dr, dc)
            if any(not (0 <= r < board.size and 0 <= c < board.size)
                   for (r, c) in moved.piece_cells):
                continue
            if moved.piece_cells & {c for s in board.sinks for c in s}:
                continue
            wins, satisfied = _wins(moved, table, instance.objective)
            if not wins:
                continue
            path = _path_to((dr, dc), deltas)
            if path is None:
                continue
            candidate = FlowPlan(
                PlanStatus.SOLVABLE,
                actions=path + (commit,),
                offset=(dr, dc),
                predicted_satisfied=satisfied,
                reason=f"placement {(dr, dc)} is predicted to satisfy {satisfied} sink(s)",
            )
            if best is None or len(candidate.actions) < len(best.actions):
                best = candidate

    if best is not None:
        return best
    return FlowPlan(
        PlanStatus.UNSATISFIABLE,
        reason="no reachable placement satisfies the objective under the claimed table",
    )


__all__ = ["FlowPlan", "compile_flow_hypothesis", "MAX_OFFSET"]
