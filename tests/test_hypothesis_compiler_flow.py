"""R98 step (v) tests: the flow-family compiler.

Pins the dispatch surface and the search. The load-bearing property is that the
compiler plans with the HYPOTHESIS'S OWN response table as its simulator — if it
consulted a fixed notion of how flow behaves, every candidate would plan
identically and the selection stage would measure nothing.

A minimal stand-in for grounding is used deliberately: these tests are about the
compiler's dispatch and search, and the real grounding is certified against the
live engine in scripts/rounds/R98/grounding.txt.
"""

from __future__ import annotations

from dataclasses import replace

from admorphiq.hypothesis_select import schema_flow as F
from admorphiq.hypothesis_select.compiler import PlanStatus
from admorphiq.hypothesis_select.compiler_flow import compile_flow_hypothesis
from admorphiq.hypothesis_select.grounding_flow import UNKNOWN, Grounded
from admorphiq.hypothesis_select.propagate_flow import Board

SIZE = 10
PIECE = frozenset({(3, 2), (3, 3), (3, 4)})
SINK_A = frozenset({(7, 1), (7, 3), (8, 1), (8, 2), (8, 3)})
SINK_B = frozenset({(7, 5), (7, 7), (8, 5), (8, 6), (8, 7)})
BARRIER = frozenset({(9, c) for c in range(SIZE)})
DELTAS = ((1, -1, 0), (2, 1, 0), (3, 0, -1), (4, 0, 1))


_DEFAULT_BOARD = Board(
    pieces=(PIECE,),
    sinks=(SINK_A, SINK_B),
    hazard_cells=BARRIER,
    emitter_cells=frozenset(),
    standing_flow=frozenset({(1, 4)}),
    size=SIZE,
)


class _Grounding:
    """The query surface the compiler consumes, with fixed answers. Passing None
    for a slot means the harness could not ground it."""

    def __init__(self, board=_DEFAULT_BOARD, deltas=DELTAS, commit=5):
        self._board = board
        self._deltas = deltas
        self._commit = commit

    def board(self):
        return UNKNOWN if self._board is None else Grounded(self._board, "high")

    def piece_deltas(self):
        return UNKNOWN if self._deltas is None else Grounded(self._deltas, "high")

    def commit_action(self):
        return UNKNOWN if self._commit is None else Grounded(self._commit, "high")

    def idle_appearance_known(self):
        return True

    def move_budget(self):
        """UNKNOWN unless a test says otherwise: a budget is only real once the board
        has taken a piece, and levels that never take one must plan unconstrained."""
        return UNKNOWN

    def moves_spent(self):
        """Nothing spent: with no budget there is nothing to subtract from."""
        return UNKNOWN


def test_a_winning_placement_compiles_to_the_shortest_sequence_ending_in_a_commit():
    """Purpose: the compiler must find a placement its claimed table predicts will
    satisfy the objective, reach it with the MEASURED action deltas, and finish
    with the measured commit action.

    Expected feedback: pass proves the executable arm plans. Fail means the oracle
    gate could never clear the level even with a correct hypothesis."""
    plan = compile_flow_hypothesis(F.sp80_oracle_instance(), _Grounding())
    assert plan.status is PlanStatus.SOLVABLE
    assert plan.steps[-1] == 5
    assert plan.offset == (0, 1)
    assert plan.steps == (4, 5)
    assert plan.predicted_satisfied == 2


def test_the_plan_follows_the_claimed_table_not_a_fixed_simulator():
    """Purpose: the family's central design claim. A hypothesis claiming the flow
    is ABSORBED by a piece must not produce the same plan as the oracle — if it
    did, the compiler would be carrying the run regardless of what the model
    selected, which is how a false pass is manufactured.

    Expected feedback: pass proves the selected semantics reach the plan. Fail
    means the selection stage measures nothing."""
    base = F.sp80_oracle_instance()
    tm = base.transition_model
    name, piece = tm.responses.piece_by_class[0]
    absorbing = F.FlowHypothesis(
        objective=base.objective,
        transition_model=replace(
            tm,
            responses=replace(
                tm.responses,
                piece_by_class=((name, F.PieceResponse("none", piece.direction,
                                                       piece.propagation)),),
            ),
        ),
        phases=base.phases,
    )
    plan = compile_flow_hypothesis(absorbing, _Grounding())
    oracle_plan = compile_flow_hypothesis(base, _Grounding())
    assert oracle_plan.status is PlanStatus.SOLVABLE
    assert plan != oracle_plan
    assert plan.status is PlanStatus.UNSATISFIABLE


def test_verify_only_arms_never_plan():
    """Purpose: a lookup transition and the any-sink objective exist so mutants can
    name them; neither carries a model that could be executed.

    Expected feedback: pass proves both map to the typed UNSUPPORTED terminal.
    Fail means an unexecutable claim could silently drive the agent."""
    base = F.sp80_oracle_instance()
    lookup = F.FlowHypothesis(
        objective=base.objective,
        transition_model=F.EmpiricalSpillMatrix(asserted_entries=3),
        phases=base.phases,
    )
    assert compile_flow_hypothesis(lookup, _Grounding()).status is PlanStatus.UNSUPPORTED

    any_sink = F.FlowHypothesis(
        objective=F.AnySinkCovered(sink_roles=("sink_0", "sink_1")),
        transition_model=base.transition_model,
        phases=base.phases,
    )
    assert compile_flow_hypothesis(any_sink, _Grounding()).status is PlanStatus.UNSUPPORTED


def test_missing_grounding_is_reported_as_incomplete_not_guessed():
    """Purpose: without a board, a delta table or a commit action there is nothing
    to plan against, and the compiler must say so rather than invent a press.

    Expected feedback: pass proves the typed failure surface is used. Fail means
    the agent would spend actions on a fabricated plan."""
    for kwargs in ({"board": None}, {"deltas": None}, {"commit": None}):
        plan = compile_flow_hypothesis(F.sp80_oracle_instance(), _Grounding(**kwargs))
        assert plan.status is PlanStatus.GROUNDING_INCOMPLETE, kwargs


def test_an_unreachable_offset_is_not_planned():
    """Purpose: the path to a placement is built only from MEASURED deltas, so a
    board offering no horizontal action cannot be planned horizontally.

    Expected feedback: pass proves the compiler never emits an action it has not
    seen work. Fail means plans would contain invented presses."""
    vertical_only = ((1, -1, 0), (2, 1, 0))
    plan = compile_flow_hypothesis(F.sp80_oracle_instance(), _Grounding(deltas=vertical_only))
    assert plan.status is PlanStatus.UNSATISFIABLE


def test_the_move_order_is_part_of_the_plan():
    """Purpose: which pieces are in the way depends on which have already moved, so a
    plan is not just a set of placements but an ORDER for reaching them. Measured on
    idx3: the engine refused a press that would have driven a piece into a cell
    another piece held, and the plan had no way to know.

    Two pieces sit in one row, and the left one's placement is only reachable through
    the cell the right one currently occupies — so the right one has to move first.

    Expected feedback: pass proves the compiler emits the moves in an order each can
    actually be driven in. Fail means a plan can be unrealisable while looking
    perfectly good on paper, and the level is lost to a refused press."""
    left = frozenset({(3, 1), (3, 2)})
    right = frozenset({(3, 3), (3, 4)})
    board = replace(_DEFAULT_BOARD, pieces=(left, right))

    plan = compile_flow_hypothesis(F.sp80_oracle_instance(), _Grounding(board=board))
    assert plan.status is PlanStatus.SOLVABLE

    # replay: every press must move its piece into free cells only
    deltas = {a: (dr, dc) for a, dr, dc in DELTAS}
    where = {left: set(left), right: set(right)}
    held = None
    for step in plan.steps[:-1]:
        if not isinstance(step, int):
            held = next(k for k in where if step.cell in where[k] or step.footprint == k)
            continue
        assert held is not None
        moved = {(r + deltas[step][0], c + deltas[step][1]) for (r, c) in where[held]}
        others = {c for k, cells in where.items() if k is not held for c in cells}
        assert not (moved & others), \
            f"press {step} drives {sorted(where[held])} into {sorted(moved & others)}"
        where[held] = moved
