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

import heapq
from dataclasses import dataclass
from typing import Optional, Union

from admorphiq.hypothesis_select import schema_flow as F
from admorphiq.hypothesis_select.compiler import PlanStatus
from admorphiq.hypothesis_select.grounding_flow import UNKNOWN, FlowGrounding
from admorphiq.hypothesis_select.propagate_flow import (
    ORACLE,
    Board,
    Cell,
    ResponseTable,
    predict,
)

MAX_OFFSET = 24     # placement search bound; a board is far smaller than this
MAX_CANDIDATES = 4000  # cost-ordered layouts examined before giving up


@dataclass(frozen=True)
class Select:
    """Click a piece to make it the one the directional actions move. Carried in
    CELL coordinates; the driver resolves the pixel anchor."""

    cell: Cell


FlowStep = Union[int, Select]


@dataclass(frozen=True)
class FlowPlan:
    """A placement plan: the steps to execute, ending with the commit action.

    A step is either a simple action id or a :class:`Select` click, because a board
    with several movable pieces needs the right one selected before its directional
    actions land. ``status`` is SOLVABLE with a sequence, or a typed failure
    surface. ``offsets`` records the chosen placement per piece and
    ``predicted_satisfied`` how many targets the claimed table expects to fill —
    the attribution hooks the live gate reads when a plan is wrong.
    """

    status: PlanStatus
    steps: tuple[FlowStep, ...] = ()
    offsets: tuple[Cell, ...] = ()
    predicted_satisfied: int = 0
    reason: str = ""

    @property
    def offset(self) -> Cell:
        """The first piece's offset — the single-piece view of ``offsets``."""
        return self.offsets[0] if self.offsets else (0, 0)


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


def _piece_options(
    board: Board,
    index: int,
    deltas: dict[int, tuple[int, int]],
    sink_cells: set[Cell],
) -> list[tuple[Cell, tuple[int, ...]]]:
    """Every placement this piece can reach, as (offset, action path), cheapest
    first. A placement is admissible only if the piece stays on the board and out
    of the targets — the constraints the harness measured."""
    piece = board.pieces[index]
    out: list[tuple[int, Cell, tuple[int, ...]]] = []
    for dr in range(-MAX_OFFSET, MAX_OFFSET + 1):
        for dc in range(-MAX_OFFSET, MAX_OFFSET + 1):
            moved = {(r + dr, c + dc) for (r, c) in piece}
            if any(not (0 <= r < board.size and 0 <= c < board.size) for (r, c) in moved):
                continue
            if moved & sink_cells:
                continue
            path = _path_to((dr, dc), deltas)
            if path is None:
                continue
            out.append((len(path), (dr, dc), path))
    out.sort()
    return [(offset, path) for _, offset, path in out]


def _joint_layouts(
    options: list[list[tuple[Cell, tuple[int, ...]]]],
    limit: int,
) -> list[tuple[int, tuple[int, ...]]]:
    """Index combinations across pieces, in increasing total action cost.

    A product over pieces is far too large to enumerate, but the cheapest layouts
    are the ones worth trying first and a winning layout is usually a small number
    of presses away. This walks the frontier with a heap, so the search stops as
    soon as a layout wins instead of after examining everything."""
    if not options:
        return []
    start = tuple(0 for _ in options)
    seen = {start}
    heap = [(sum(len(options[i][0][1]) for i in range(len(options))), start)]
    out: list[tuple[int, tuple[int, ...]]] = []
    while heap and len(out) < limit:
        cost, picks = heapq.heappop(heap)
        out.append((cost, picks))
        for i, choice in enumerate(picks):
            if choice + 1 >= len(options[i]):
                continue
            nxt = picks[:i] + (choice + 1,) + picks[i + 1:]
            if nxt in seen:
                continue
            seen.add(nxt)
            heapq.heappush(
                heap,
                (sum(len(options[j][nxt[j]][1]) for j in range(len(options))), nxt),
            )
    return out


def _anchor(piece: frozenset[Cell]) -> Cell:
    rows = sorted({r for r, _ in piece})
    cols = sorted({c for _, c in piece})
    return (rows[len(rows) // 2], cols[len(cols) // 2])


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
    if not board.pieces:
        return FlowPlan(PlanStatus.GROUNDING_INCOMPLETE, reason="no movable piece is grounded")

    sink_cells = {c for s in board.sinks for c in s}
    options = [_piece_options(board, i, deltas, sink_cells) for i in range(len(board.pieces))]
    if any(not o for o in options):
        return FlowPlan(PlanStatus.UNSATISFIABLE,
                        reason="a piece has no reachable placement under the measured deltas")

    selectable = grounding.idle_appearance_known() or len(board.pieces) == 1
    examined = 0
    for _cost, picks in _joint_layouts(options, MAX_CANDIDATES):
        examined += 1
        offsets = tuple(options[i][pick][0] for i, pick in enumerate(picks))
        if not selectable and any(o != (0, 0) for i, o in enumerate(offsets) if i > 0):
            continue  # cannot select another piece yet, so cannot move it
        candidate = board.with_offsets(offsets)
        wins, satisfied = _wins(candidate, table, instance.objective)
        if not wins:
            continue

        steps: list[FlowStep] = []
        for i, pick in enumerate(picks):
            path = options[i][pick][1]
            if not path:
                continue
            if len(board.pieces) > 1:
                steps.append(Select(_anchor(board.pieces[i])))
            steps.extend(path)
        steps.append(commit)
        return FlowPlan(
            PlanStatus.SOLVABLE,
            steps=tuple(steps),
            offsets=offsets,
            predicted_satisfied=satisfied,
            reason=f"placement {offsets} is predicted to satisfy {satisfied} target(s)",
        )

    return FlowPlan(
        PlanStatus.UNSATISFIABLE,
        reason=f"no layout among the {examined} cheapest satisfies the objective under the "
               f"claimed table",
    )


__all__ = ["FlowPlan", "FlowStep", "Select", "compile_flow_hypothesis",
           "MAX_OFFSET", "MAX_CANDIDATES"]
