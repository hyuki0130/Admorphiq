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
import random
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
MAX_CANDIDATES = 4000
# How much longer to look for a cleaner winner after the first one is found.
WINNER_GRACE = 400     # cost-ordered layouts examined before giving up
PROMISING_PER_PIECE = 12  # per-piece shortlist size for the decomposed second pass
MAX_COMBINATIONS = 20000  # layouts examined in that second pass
BEAM_WIDTH = 8            # partial layouts carried between beam rounds
BEAM_ROUNDS = 4           # how many pieces a beam layout may move
BEAM_BUDGET = 30000       # layouts evaluated by the beam
SAMPLE_BUDGET = 40000     # seeded random layouts evaluated as the final fallback
SAMPLE_SEED = 98          # fixed, so a compiled plan is reproducible


@dataclass(frozen=True)
class Select:
    """Click a piece to make it the one the directional actions move.

    Carries the piece's FOOTPRINT as well as a click cell, because pieces pass
    through each other: by the time this step runs, another piece may be sitting on
    the anchor, and the click would select the wrong one. A driver should locate the
    footprint on the CURRENT board and click a cell that belongs to it alone,
    falling back to the stored cell only when it cannot."""

    cell: Cell
    footprint: frozenset[Cell] = frozenset()
    # Where this piece is meant to END UP. A plan that is only a list of presses
    # cannot tell whether it arrived; carrying the goal lets a driver press until
    # the piece is there and stop when it is.
    target: frozenset[Cell] = frozenset()


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
    # The layout the plan is FOR: a driver that only holds a list of presses cannot
    # tell whether it arrived at the placement whose spill it is counting on.
    intended: tuple[frozenset[Cell], ...] = ()
    # The board the forecast was taken ON, so a caller can tell whether the board it
    # ends up committing is the one the plan was ever about.
    planned_board: Optional[Board] = None
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


def _path_to(offset: tuple[int, int], deltas: dict[int, tuple[int, int]],
             along: Optional[tuple[tuple[int, int], int]] = None) -> Optional[tuple[int, ...]]:
    """The shortest action sequence realising a translation offset, using only the
    measured deltas. Returns None when no combination of measured actions reaches
    it — an honest failure rather than an invented press.

    ``along`` is (flow direction, budget) when the board has SHOWN what a piece
    survives. Some levels spend a piece on its second move along the flow: measured on
    idx3, where a piece moves once and the next move takes it off the board, while on
    idx0 one travels five steps untouched. So a path needing more moves than the budget
    is not a slow route, it is a plan that destroys the piece it moves — and the budget
    is only applied once a loss has actually shown it, never guessed."""
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
        count = abs(want) // step[1]
        if along is not None:
            (fr, fc), budget = along
            if (fr, fc)[axis] and count > budget:
                return None
        seq.extend([step[0]] * count)
    return tuple(seq)


def _forbidden_cells(board: Board, margin: int) -> set[Cell]:
    """Target cells expanded by the measured keep-out margin.

    The engine refuses a placement that comes within the margin of a target, not
    merely one that overlaps it. Filtering on overlap alone lets the search commit
    to layouts the engine will not build: the moves are simply dropped, the piece
    ends up somewhere else, and the spill that follows is the one nobody planned."""
    out: set[Cell] = set()
    for sink in board.sinks:
        rows = [r for r, _ in sink]
        cols = [c for _, c in sink]
        for r in range(min(rows) - margin, max(rows) + margin + 1):
            for c in range(min(cols) - margin, max(cols) + margin + 1):
                out.add((r, c))
    return out


def _piece_options(
    board: Board,
    index: int,
    deltas: dict[int, tuple[int, int]],
    sink_cells: set[Cell],
    row_bound: int = 0,
    along: Optional[tuple[tuple[int, int], int]] = None,
) -> list[tuple[Cell, tuple[int, ...]]]:
    """Every placement this piece can reach, as (offset, action path), cheapest
    first. A placement is admissible only if the piece stays on the board, respects
    the measured row bound, keeps clear of the targets' keep-out area, and can be
    REACHED without driving through another piece — the constraints the harness
    measured.

    The occupancy check is conservative: the other pieces are treated as standing
    where they stand now, though a plan may move one out of the way first. It can
    therefore hide a placement that would in fact be reachable, and it cannot admit
    one that is not. That trade is deliberate — measured on idx3, where the engine
    refused a press that would have driven a piece into a cell another piece held,
    and the plan had no way to know because reachability was computed from the
    measured deltas alone."""
    piece = board.pieces[index]
    out: list[tuple[int, Cell, tuple[int, ...]]] = []
    for dr in range(-MAX_OFFSET, MAX_OFFSET + 1):
        for dc in range(-MAX_OFFSET, MAX_OFFSET + 1):
            moved = {(r + dr, c + dc) for (r, c) in piece}
            if any(not (0 <= r < board.size and 0 <= c < board.size) for (r, c) in moved):
                continue
            if moved & sink_cells:
                continue
            if any(r < row_bound for (r, _) in moved):
                continue
            path = _path_to((dr, dc), deltas, along)
            if path is None:
                continue
            out.append((len(path), (dr, dc), path))
    out.sort()
    return [(offset, path) for _, offset, path in out]


def _order_moves(board, options, picks, offsets, deltas) -> Optional[list[int]]:
    """An order in which every move can be driven without entering an occupied cell,
    or None if no such order exists.

    Greedy and sufficient: at each step take any piece whose path is clear against
    where the pieces stand NOW — those already moved at their new places, the rest
    where they started. A piece that has nowhere to go yet may be freed by a later
    move, so the scan repeats until nothing more can move."""
    placed = {i: board.pieces[i] for i in range(len(board.pieces))}
    todo = [i for i in range(len(board.pieces)) if options[i][picks[i]][1]]
    order: list[int] = []
    while todo:
        for i in list(todo):
            occupied = frozenset(c for k, cells in placed.items() if k != i for c in cells)
            if not _path_clear(board.pieces[i], options[i][picks[i]][1], deltas, occupied):
                continue
            placed[i] = frozenset(
                (r + offsets[i][0], c + offsets[i][1]) for (r, c) in board.pieces[i]
            )
            order.append(i)
            todo.remove(i)
            break
        else:
            return None
    return order + [i for i in range(len(board.pieces)) if i not in order]


def _path_clear(
    piece: frozenset[Cell],
    path: tuple[int, ...],
    deltas: dict[int, tuple[int, int]],
    occupied: frozenset[Cell],
) -> bool:
    """Whether the piece can be driven along this path without entering a cell another
    piece holds. Each press is a rigid step, so the check is per step, not just at the
    destination: a placement can be clear where it ends and blocked on the way."""
    if not occupied:
        return True
    current = piece
    for action in path:
        dr, dc = deltas[action]
        current = frozenset((r + dr, c + dc) for (r, c) in current)
        if current & occupied:
            return False
    return True


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


def _score(board: Board, table: ResponseTable) -> tuple[int, int]:
    """How good a layout looks: targets satisfied, and how FEW streams end on a
    barrier (negated so that larger is better). Used to rank placements, never to
    decide the objective.

    The barrier term is graded rather than boolean on purpose. Measured on the
    three-source level: every single-piece placement still touches a barrier, so a
    boolean gives them all the same score and the ranking carries no information —
    while the counts do separate them, and a placement that removes one contact is
    the half of a channeling solution that the other pieces complete."""
    prediction = predict(board, table)
    return len(prediction.satisfied), -prediction.barrier_hits


def _promising_offsets(
    board: Board,
    index: int,
    options: list[tuple[Cell, tuple[int, ...]]],
    table: ResponseTable,
    baseline: tuple[int, bool],
) -> list[int]:
    """Option indices for one piece that IMPROVE the board on their own.

    A decomposition heuristic, and honestly a lossy one: a layout where two pieces
    only help jointly, neither improving anything alone, is invisible to it. It
    exists because the cost-ordered scan is exhaustive but shallow — it reaches only
    layouts a few presses from the start — while a channeling solution can need
    several pieces moved far. Ranking by what each piece can achieve alone is the
    cheapest way to find the placements worth combining.
    """
    scored: list[tuple[tuple[int, int], int, int]] = []
    for pick, (offset, path) in enumerate(options):
        if offset == (0, 0):
            continue
        value = _score(board.moved(offset[0], offset[1], index), table)
        if value <= baseline:
            continue
        scored.append((value, len(path), pick))
    scored.sort(key=lambda e: (-e[0][0], -e[0][1], e[1]))
    return [pick for _, _, pick in scored[:PROMISING_PER_PIECE]]


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

    constraints = getattr(tm, "placement_constraints", None)
    margin = getattr(constraints, "sink_keepout_margin", 0) or 0
    row_bound = getattr(constraints, "row_bound", None) or 0
    sink_cells = _forbidden_cells(board, margin)
    budget = grounding.move_budget()
    spent = grounding.moves_spent()
    spent_by = {} if spent is UNKNOWN else {frozenset(c): n for c, n in spent.value}
    options = []
    for i in range(len(board.pieces)):
        # each piece plans within what IT has left, not within the level's total
        along = None
        if budget is not UNKNOWN:
            left = budget.value - spent_by.get(board.pieces[i], 0)
            along = (board.direction, max(0, left))
        options.append(_piece_options(board, i, deltas, sink_cells, row_bound, along))
    if any(not o for o in options):
        return FlowPlan(PlanStatus.UNSATISFIABLE,
                        reason="a piece has no reachable placement under the measured deltas")

    selectable = grounding.idle_appearance_known() or len(board.pieces) == 1
    examined = 0
    # Winners are not equal. A layout that wins with streams still ending on a barrier is
    # a layout whose win rests on the parts of the model least likely to be right, and on
    # idx3 a descent over the same options finds one with NO barrier contact at all. So
    # the first winner is kept and the scan continues a little, taking the best by
    # barrier contact — without reordering the options, because reordering changes what
    # the capped search reaches and cost idx2 its clear when it was tried.
    best: tuple | None = None
    grace = 0
    for _cost, picks in _joint_layouts(options, MAX_CANDIDATES):
        examined += 1
        if best is not None:
            grace += 1
            if grace > WINNER_GRACE:
                break
        offsets = tuple(options[i][pick][0] for i, pick in enumerate(picks))
        if not selectable and any(o != (0, 0) for i, o in enumerate(offsets) if i > 0):
            continue  # cannot select another piece yet, so cannot move it
        candidate = board.with_offsets(offsets)
        wins, satisfied = _wins(candidate, table, instance.objective)
        if not wins:
            continue
        hits = predict(candidate, table).barrier_hits
        if best is None or hits < best[0]:
            plan = _plan_from(board, options, picks, offsets, satisfied, commit, deltas)
            if plan is not None:
                best = (hits, plan)
                if hits == 0:
                    return plan
    if best is not None:
        return best[1]

    # Second pass: the cheap neighbourhood held nothing, so combine the placements
    # each piece can reach that improve the board on its OWN. Explicitly a
    # heuristic — see _promising_offsets — so its failure is reported as such.
    baseline = _score(board, table)
    # A placement counts as promising if it improves EITHER component: more targets,
    # or fewer barrier contacts. Requiring both is what made the first pass blind to
    # the pieces whose only job is to catch a branch.

    shortlists: list[list[int]] = []
    for i in range(len(board.pieces)):
        identity = next((k for k, (o, _) in enumerate(options[i]) if o == (0, 0)), None)
        picks = _promising_offsets(board, i, options[i], table, baseline)
        if identity is not None:
            picks = [identity] + picks
        shortlists.append(picks or ([identity] if identity is not None else []))

    # The product is walked LAZILY up to the cap rather than skipped when it looks
    # too big: with four pieces the count exceeds any sane bound, and abandoning the
    # pass on that basis examines nothing at all — which is strictly worse than
    # examining the first MAX_COMBINATIONS of it.
    if selectable:
        seen = 0
        for picks in _product(shortlists):
            seen += 1
            if seen > MAX_COMBINATIONS:
                break
            examined += 1
            offsets = tuple(options[i][pick][0] for i, pick in enumerate(picks))
            candidate = board.with_offsets(offsets)
            wins, satisfied = _wins(candidate, table, instance.objective)
            if not wins:
                continue
            plan = _plan_from(board, options, picks, offsets, satisfied, commit, deltas)
            if plan is not None:
                return plan

        # Third pass: a BEAM. The static shortlists are computed against the entry
        # layout, so a piece whose only job is to catch a branch that ANOTHER piece's
        # placement creates never looks promising and is never offered — measured on
        # the three-source level, where the best static combination satisfies every
        # target but still leaves two streams on a barrier. Re-ranking each piece
        # against the layout chosen SO FAR is what makes those placements visible.
        picks, offsets, satisfied, evaluated = _beam_search(
            board, options, table, instance.objective
        )
        examined += evaluated
        if picks is not None:
            plan = _plan_from(board, options, picks, offsets, satisfied, commit, deltas)
            if plan is not None:
                return plan

        # Final pass: SEEDED RANDOM layouts. Inelegant, and measured to work where
        # the structured passes cannot. On the three-source level a winning layout
        # moves all four pieces by six to ten cells each — far outside the cheap
        # neighbourhood, invisible to shortlists that rank by solo improvement, and
        # past the plateau a hill-climb settles on. Sampling finds one roughly once
        # in eight thousand draws, so a budget of this size finds several. The seed
        # is fixed so a compiled plan stays reproducible.
        rng = random.Random(SAMPLE_SEED)
        for _ in range(SAMPLE_BUDGET):
            examined += 1
            picks = tuple(rng.randrange(len(options[i])) for i in range(len(options)))
            offsets = tuple(options[i][pick][0] for i, pick in enumerate(picks))
            candidate = board.with_offsets(offsets)
            wins, satisfied = _wins(candidate, table, instance.objective)
            if wins:
                plan = _plan_from(board, options, picks, offsets, satisfied, commit, deltas)
                if plan is not None:
                    return plan

    return FlowPlan(
        PlanStatus.UNSATISFIABLE,
        reason=f"no layout satisfies the objective under the claimed table: "
               f"{examined} examined across the cheapest neighbourhood and the "
               f"per-piece shortlists",
    )


def _beam_search(board: Board, options, table: ResponseTable, objective):
    """Hill-climb the layout, re-ranking every piece against the layout chosen so far.

    Returns ``(picks, offsets, satisfied, evaluated)`` with ``picks`` None if nothing
    won. Each round tries moving ONE more piece from each surviving layout, keeps the
    best few by score, and stops as soon as a layout satisfies the objective. It is
    a heuristic — a hill-climb can sit on a plateau that only a coordinated pair of
    moves leaves — but unlike the static product it can find a placement whose value
    exists only in the presence of another."""
    identity = tuple(
        next((k for k, (o, _) in enumerate(options[i]) if o == (0, 0)), 0)
        for i in range(len(board.pieces))
    )
    beam: list[tuple[tuple[int, int], tuple[int, ...]]] = [
        (_score(board, table), identity)
    ]
    evaluated = 0
    seen: set[tuple[int, ...]] = {identity}

    for _round in range(BEAM_ROUNDS):
        nxt: list[tuple[tuple[int, int], tuple[int, ...]]] = []
        for _value, picks in beam:
            base_offsets = tuple(options[i][pick][0] for i, pick in enumerate(picks))
            current = board.with_offsets(base_offsets)
            for i in range(len(board.pieces)):
                for pick, (offset, _path) in enumerate(options[i]):
                    if pick == picks[i]:
                        continue
                    trial = picks[:i] + (pick,) + picks[i + 1:]
                    if trial in seen:
                        continue
                    seen.add(trial)
                    evaluated += 1
                    if evaluated > BEAM_BUDGET:
                        return None, (), 0, evaluated
                    offsets = base_offsets[:i] + (offset,) + base_offsets[i + 1:]
                    candidate = current.with_offsets(offsets)
                    wins, satisfied = _wins(candidate, table, objective)
                    if wins:
                        return trial, offsets, satisfied, evaluated
                    nxt.append((_score(candidate, table), trial))
        if not nxt:
            break
        nxt.sort(key=lambda e: (-e[0][0], -e[0][1]))
        beam = nxt[:BEAM_WIDTH]
    return None, (), 0, evaluated


def _product(shortlists: list[list[int]]):
    """Every combination across the per-piece shortlists, cheapest-looking first."""
    if not shortlists:
        return
    stack: list[tuple[int, ...]] = [()]
    while stack:
        picks = stack.pop()
        depth = len(picks)
        if depth == len(shortlists):
            yield picks
            continue
        for choice in reversed(shortlists[depth]):
            stack.append(picks + (choice,))


def _plan_from(board, options, picks, offsets, satisfied, commit, deltas) -> Optional[FlowPlan]:
    """Turn a chosen layout into steps, or return None if no ORDER of the moves can
    realise it.

    Which pieces are in the way depends on which have already moved, so the order is
    part of the plan and not an afterthought. Measured on idx3: the engine refused a
    press that would have driven a piece into a cell another piece held. Filtering
    those placements out per-piece against the entry layout is too strong — it broke
    idx2, where a blocker moves out of the way first — so the constraint is applied
    where it actually lives, at the moment each move is made."""
    order = _order_moves(board, options, picks, offsets, deltas)
    if order is None:
        return None
    steps: list[FlowStep] = []
    intended = tuple(
        frozenset((r + offsets[i][0], c + offsets[i][1]) for (r, c) in piece)
        for i, piece in enumerate(board.pieces)
    )
    for i in order:
        pick = picks[i]
        path = options[i][pick][1]
        if not path:
            continue
        if len(board.pieces) > 1:
            steps.append(
                    Select(
                        _anchor(board.pieces[i]),
                        board.pieces[i],
                        frozenset(
                            (r + offsets[i][0], c + offsets[i][1])
                            for (r, c) in board.pieces[i]
                        ),
                    )
                )
        steps.extend(path)
    steps.append(commit)
    return FlowPlan(
        PlanStatus.SOLVABLE,
        steps=tuple(steps),
        offsets=offsets,
        intended=intended,
        planned_board=board.with_offsets(offsets),
        predicted_satisfied=satisfied,
        reason=f"placement {offsets} is predicted to satisfy {satisfied} target(s)",
    )


__all__ = ["FlowPlan", "FlowStep", "Select", "compile_flow_hypothesis",
           "MAX_OFFSET", "MAX_CANDIDATES"]
