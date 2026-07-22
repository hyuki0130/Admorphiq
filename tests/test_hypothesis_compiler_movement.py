"""R96 step (v) tests: the movement compiler.

Tag-only dispatch (a grep guard), the offline oracle-plan reproduction on the real
m0r0 trace (joint two-actor BFS reaching the exact-merge state), stepped-replay
per-move confirmation reaching the merge, and the typed failure surfaces
(DIVERGED, GROUNDING_INCOMPLETE, UNSATISFIABLE, UNSUPPORTED). No live env.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from admorphiq.hypothesis_select import schema_movement as M
from admorphiq.hypothesis_select.compiler import PlanStatus, Terminal
from admorphiq.hypothesis_select.compiler_movement import (
    CoupledGridStepPlan,
    Move,
    UnsupportedMovementPlan,
    compile_movement_hypothesis,
)
from admorphiq.hypothesis_select.grounding import UNKNOWN, Grounded, GroundingService
from admorphiq.hypothesis_select.schema_movement import StaticOccupancy

_SRC = Path(__file__).resolve().parents[1] / "src" / "admorphiq" / "hypothesis_select" / "compiler_movement.py"

# ── synthetic fixture rendering (mirrors the grounding-movement tests) ────────
_SCALE = 4
_N = 48
_BG = 0
_ACTOR = 9
_WALL = 7
# A dense static wall scatter so a single-cell actor move is a tiny fraction of the
# frame's stable regions — otherwise the frame-stream Jaccard wholesale-change
# detector reads the move as a layout replacement (a real dense board never does).
_STRUCT = tuple((r, c) for r in (0, 2, 9, 11) for c in range(0, 12, 2))


def _frame(actors, walls=()):
    """A ``_N x _N`` grid: each ``(row, col)`` CELL is a ``_SCALE x _SCALE`` block on
    the ``_BG`` background, with the static ``_STRUCT`` scatter always present."""
    g = [[_BG] * _N for _ in range(_N)]
    for (r, c) in (*_STRUCT, *walls):
        for dr in range(_SCALE):
            for dc in range(_SCALE):
                g[r * _SCALE + dr][c * _SCALE + dc] = _WALL
    for (r, c) in actors:
        for dr in range(_SCALE):
            for dc in range(_SCALE):
                g[r * _SCALE + dr][c * _SCALE + dc] = _ACTOR
    return tuple(tuple(row) for row in g)


def _grounding_with_converge_delta(walls=()):
    """A grounding that has acquired action-4 = column convergence (actor_a +col,
    actor_b -col) from two non-merging probes — the minimal delta table a merge
    plan needs."""
    gs = GroundingService()
    for _ in range(2):
        gs.feed_transition(_frame([(5, 1), (5, 7)], walls), 4, (0, 0), _frame([(5, 2), (5, 6)], walls))
    return gs


def _to_grid(frame):
    arr = np.asarray(frame)
    if arr.ndim == 3:
        arr = arr[-1]
    return tuple(tuple(int(v) for v in row) for row in arr)


def test_dispatch_is_tag_only_no_game_ids_or_adapter_imports():
    """Purpose: the movement compiler dispatches on schema tags alone — its source
    contains no game id and no quarantined-adapter import.

    Expected feedback: pass proves the compiled plan generalises by family, not by a
    hardcoded game, and honours the runtime quarantine. Fail means a game id or an
    adapter import leaked into the compiler and the plan would not transfer."""
    src = _SRC.read_text().lower()
    for token in ("m0r0", "dc22", "tu93", "adapters25"):
        assert token not in src, f"compiler_movement.py leaked {token!r}"


def test_m0r0_oracle_plan_reaches_the_exact_merge_state():
    """Purpose: fed the real m0r0 gold trace + a level start board, the oracle
    instance compiles to a joint two-actor BFS whose emitted action sequence drives
    the pair to an EXACT same_cell merge.

    Expected feedback: pass proves the step-v reproduction gate on the real oracle
    board — joint BFS over the live occupancy with the measured mirror deltas finds
    the merge, at a plan length matching the gold action count. Fail on the joint
    reconstruction here is the contract's grounding/planning falsification signal."""
    d = np.load("data/traces/m0r0.npz")
    fr, nf, act, gold, lvl = d["frames"], d["next_frames"], d["actions"], d["is_gold"], d["level_index"]
    gs = GroundingService()
    for i in range(len(act)):
        if gold[i] and 1 <= act[i] <= 4:
            gs.feed_transition(_to_grid(fr[i]), int(act[i]), (0, 0), _to_grid(nf[i]))
    i0 = next(i for i in range(len(act)) if lvl[i] == 0)
    gs.feed(_to_grid(fr[i0]))  # the level start board -> live actors + occupancy
    plan = compile_movement_hypothesis(M.m0r0_oracle_instance(), gs)
    assert isinstance(plan, CoupledGridStepPlan)
    sol = plan.solve()
    assert sol.status is PlanStatus.SOLVABLE
    assert sol.states_searched > 0
    # the planned trajectory's end state is an exact merge (same cell for both actors)
    end_a, end_b = plan._traj[-1]
    assert end_a == end_b
    assert len(sol.actions) == 15  # matches the gold action count for this board


def test_stepped_replay_confirms_each_move_and_reaches_merge():
    """Purpose: on a synthetic 2-cell-gap board the plan emits action-4 and, when the
    resulting merged frame is replayed, CONFIRMS the observed actor cell against the
    planned successor and terminates DONE at the merge.

    Expected feedback: pass proves per-move confirmation accepts a board that moved
    exactly as planned (the merge frame's single coincident cell matches the two
    coincident planned cells). Fail means confirmation rejects a correct replay or
    the plan does not terminate at the merge."""
    gs = _grounding_with_converge_delta()
    start = _frame([(5, 3), (5, 5)])  # gap 2 -> action-4 merges both onto (5, 4)
    gs.feed(start)
    plan = compile_movement_hypothesis(M.m0r0_oracle_instance(), gs)
    first = plan.step(start)
    assert isinstance(first, Move) and first.action == 4
    merged = _frame([(5, 4)])  # both actors coincide on one cell
    outcome = plan.step(merged)
    assert isinstance(outcome, Terminal) and outcome.status is PlanStatus.DONE


def test_replay_contradicting_the_planned_move_diverges():
    """Purpose: after the plan emits its move, replaying a frame where the actors did
    NOT move as planned (they stayed at the start) yields DIVERGED — never a silent
    continue.

    Expected feedback: pass proves execution is guarded by per-move confirmation (the
    attribution hook for the live gate): a board whose response contradicts the
    measured transition model stops the plan. Fail means the plan would keep issuing
    moves against a board that does not behave as grounded. (Because the action-id
    delta numbering is hash-variable, the executable model is the LIVE grounding
    measurement, so a 'wrong-delta' is realised as this model-vs-board mismatch at
    stepped replay — the reconciliation flagged to the lead.)"""
    gs = _grounding_with_converge_delta()
    start = _frame([(5, 3), (5, 5)])
    gs.feed(start)
    plan = compile_movement_hypothesis(M.m0r0_oracle_instance(), gs)
    first = plan.step(start)
    assert isinstance(first, Move)
    # the board did NOT respond as the plan predicted (actors stayed put)
    outcome = plan.step(start)
    assert isinstance(outcome, Terminal) and outcome.status is PlanStatus.DIVERGED


def test_withheld_deltas_is_grounding_incomplete():
    """Purpose: with only a single (unconfirmed) probe the delta table is UNKNOWN, so
    the plan reports GROUNDING_INCOMPLETE rather than guessing a path.

    Expected feedback: pass proves the honest incomplete-grounding surface — no
    measured deltas means no plan. Fail means the compiler fabricates a joint plan
    from an ungrounded transition model."""
    gs = GroundingService()
    gs.feed_transition(_frame([(5, 1), (5, 7)]), 4, (0, 0), _frame([(5, 2), (5, 6)]))  # one probe only
    assert gs.movement_deltas() is UNKNOWN
    gs.feed(_frame([(5, 3), (5, 5)]))
    plan = compile_movement_hypothesis(M.m0r0_oracle_instance(), gs)
    assert plan.solve().status is PlanStatus.GROUNDING_INCOMPLETE


def test_empirical_move_matrix_compiles_to_unsupported():
    """Purpose: an EmpiricalMoveMatrix transition compiles to the typed UNSUPPORTED
    plan and never BFSes — a fixed matrix cannot represent collision-dependent desync.

    Expected feedback: pass proves the verify-only transition has a distinct
    compile-time surface (UNSUPPORTED), separate from an unknown COMBINATION (which
    raises). Fail means the matrix silently compiles to an executable search."""
    base = M.m0r0_oracle_instance()
    instance = M.MovementHypothesis(
        objective=base.objective,
        transition_model=M.EmpiricalMoveMatrix(asserted_footprint=1),
        phases=base.phases,
    )
    gs = _grounding_with_converge_delta()
    plan = compile_movement_hypothesis(instance, gs)
    assert isinstance(plan, UnsupportedMovementPlan)
    assert plan.solve().status is PlanStatus.UNSUPPORTED
    assert isinstance(plan.step(_frame([(5, 3), (5, 5)])), Terminal)
    assert plan.step(_frame([(5, 3), (5, 5)])).status is PlanStatus.UNSUPPORTED


class _StubMoveGrounding:
    """A movement-grounding stand-in returning a CONTROLLED partial delta table +
    fixed actors/occupancy — so the compiler's confirmed-subset alphabet logic is
    unit-tested without driving probes."""

    def __init__(self, deltas, actors, walls=(), hazards=()):
        self._deltas, self._actors, self._walls, self._hazards = deltas, actors, walls, hazards

    def movement_deltas(self):
        return Grounded(dict(self._deltas), "high") if self._deltas else UNKNOWN

    def movement_actors(self):
        return Grounded(list(self._actors), "high") if self._actors else UNKNOWN

    def movement_occupancy(self):
        return Grounded(StaticOccupancy(tuple(self._walls), "high", "stub", 0), "high")

    def movement_hazard_cells(self):
        return Grounded(frozenset(self._hazards), "high")


def test_plan_over_confirmed_subset_reaches_goal_without_the_unconfirmed_edge():
    """Purpose: with one (actor, direction) edge unconfirmed, the joint BFS plans over
    the CONFIRMED action alphabet (actions confirmed for BOTH actors) and still reaches
    the merge — full-alphabet knowledge is not required.

    Expected feedback: pass proves the compiler does not demand all 8 edges (the idx1
    defect): the merge is reached via the confirmed subset and the plan never emits the
    action whose edge is unconfirmed for one actor. Fail means an unconfirmed edge
    wrongly blocks an achievable plan."""
    # actor_b's action-1 (up) edge is UNCONFIRMED; convergence uses action 4 (a right,
    # b left), confirmed for both — so the pair (2,3)/(2,7) merges without action 1.
    deltas = {
        ("actor_a", 1): (-1, 0), ("actor_a", 2): (1, 0), ("actor_a", 3): (0, -1), ("actor_a", 4): (0, 1),
        ("actor_b", 2): (1, 0), ("actor_b", 3): (0, 1), ("actor_b", 4): (0, -1),
    }
    gs = _StubMoveGrounding(deltas, [("actor_a", (2, 3)), ("actor_b", (2, 7))])
    plan = compile_movement_hypothesis(M.m0r0_oracle_instance(), gs)
    sol = plan.solve()
    assert sol.status is PlanStatus.SOLVABLE
    assert 1 not in sol.actions  # action 1 is not in the confirmed alphabet (actor_b lacks it)
    assert plan._traj[-1][0] == plan._traj[-1][1]  # exact merge


_FULL_MIRROR_DELTAS = {
    ("actor_a", 1): (-1, 0), ("actor_a", 2): (1, 0), ("actor_a", 3): (0, -1), ("actor_a", 4): (0, 1),
    ("actor_b", 1): (-1, 0), ("actor_b", 2): (1, 0), ("actor_b", 3): (0, 1), ("actor_b", 4): (0, -1),
}


def _arena(rows, cols):
    """A blocking border box of ``rows x cols`` cells (interior is floor)."""
    return (
        [(0, c) for c in range(cols)] + [(rows - 1, c) for c in range(cols)]
        + [(r, 0) for r in range(rows)] + [(r, cols - 1) for r in range(rows)]
    )


def test_merge_is_meet_in_the_middle_not_walk_onto():
    """Purpose: the joint BFS merges the actors ONLY by both entering the SAME empty
    cell simultaneously (meet-in-the-middle) — the plan's final state coincides on a
    cell that was NEITHER actor's pre-merge position.

    Expected feedback: pass proves the successor models the engine's merge rule (walking
    onto the partner's occupied cell is refused; the only coincidence is a simultaneous
    entry into an empty cell). Fail means the plan walks an actor onto a stationary
    partner — the v7 endgame stall."""
    gs = _StubMoveGrounding(_FULL_MIRROR_DELTAS, [("actor_a", (2, 4)), ("actor_b", (2, 6))], walls=_arena(6, 10))
    plan = compile_movement_hypothesis(M.m0r0_oracle_instance(), gs)
    sol = plan.solve()
    assert sol.status is PlanStatus.SOLVABLE
    end, pre = plan._traj[-1], plan._traj[-2]
    assert end[0] == end[1]  # merged onto one cell
    assert end[0] not in (pre[0], pre[1])  # BOTH actors entered an empty cell (not a walk-onto)


def test_adjacent_start_merges_only_via_a_desync_detour():
    """Purpose: from an ADJACENT (gap-1) same-axis start, a same-axis merge is
    parity-impossible with mirror deltas, so an OPEN arena is UNSATISFIABLE; a
    desync-enabling wall (blocking one actor on a symmetric move to change parity) makes
    it SOLVABLE, ending in a simultaneous meet-in-the-middle entry.

    Expected feedback: pass proves the successor forces the idx0-style desync route
    (never a walk-onto/swap) and honestly reports parity-impossible merges as
    UNSATISFIABLE. Fail means the BFS fabricated an illegal adjacent merge."""
    actors = [("actor_a", (3, 4)), ("actor_b", (3, 5))]
    open_sol = compile_movement_hypothesis(
        M.m0r0_oracle_instance(), _StubMoveGrounding(_FULL_MIRROR_DELTAS, actors, walls=_arena(7, 10))
    ).solve()
    assert open_sol.status is PlanStatus.UNSATISFIABLE  # gap-1 same-axis: parity-impossible without a desync

    gs = _StubMoveGrounding(_FULL_MIRROR_DELTAS, actors, walls=_arena(7, 10) + [(2, 4)])
    plan = compile_movement_hypothesis(M.m0r0_oracle_instance(), gs)
    sol = plan.solve()
    assert sol.status is PlanStatus.SOLVABLE  # the wall enables a parity-changing detour
    end, pre = plan._traj[-1], plan._traj[-2]
    assert end[0] == end[1] and end[0] not in (pre[0], pre[1])  # final step: simultaneous same-empty-cell entry


def test_unwalled_overrides_a_grounded_wall_an_actor_occupies():
    """Purpose: a GROUNDED (statically-parsed) wall passed in ``unwalled`` is treated as
    floor — the plan may route through / merge on it — while without the override the
    same grounded wall is respected and never entered.

    Expected feedback: pass proves observation-trumps-inference reaches the static parse:
    a dynamic obstacle baked into the occupancy at parse time can be invalidated once an
    actor is seen standing on it (the v8 fictional-wall endgame). Fail means a false
    grounded wall permanently blocks the plan."""
    arena = _arena(6, 10)
    actors = [("actor_a", (2, 4)), ("actor_b", (2, 6))]
    gs = _StubMoveGrounding(_FULL_MIRROR_DELTAS, actors, walls=arena + [(2, 5)])
    # grounded wall on the meet-in-the-middle cell (2,5): respected -> never routed onto
    plan_wo = compile_movement_hypothesis(M.m0r0_oracle_instance(), gs)
    assert plan_wo.solve().status is PlanStatus.SOLVABLE  # merges elsewhere (another row)
    assert all((2, 5) not in state for state in plan_wo._traj)
    # unwalling (2,5) treats it as floor -> a one-action meet-in-the-middle merge there
    plan = compile_movement_hypothesis(M.m0r0_oracle_instance(), gs, unwalled={(2, 5)})
    sol = plan.solve()
    assert sol.status is PlanStatus.SOLVABLE
    assert len(sol.actions) == 1 and plan._traj[-1] == ((2, 5), (2, 5))


def test_extra_hazards_are_routed_around_like_walls():
    """Purpose: a cell learned to HAZARD (soft-reset on entry) at execution time is
    routed around — the joint BFS prunes any action that would drive an actor into it,
    and no planned state places an actor on it.

    Expected feedback: pass proves the online-hazard channel (the twin of extra_walls)
    feeds back into planning: a hazard the grounding never saw (gold avoided it) can be
    added and the recompiled plan avoids it. Fail means learned hazards are ignored and
    the plan re-enters the reset cell."""
    deltas = {
        ("actor_a", 1): (-1, 0), ("actor_a", 2): (1, 0), ("actor_a", 3): (0, -1), ("actor_a", 4): (0, 1),
        ("actor_b", 1): (-1, 0), ("actor_b", 2): (1, 0), ("actor_b", 3): (0, 1), ("actor_b", 4): (0, -1),
    }
    box = (
        [(0, c) for c in range(10)] + [(5, c) for c in range(10)]
        + [(r, 0) for r in range(6)] + [(r, 9) for r in range(6)]
    )
    gs = _StubMoveGrounding(deltas, [("actor_a", (2, 3)), ("actor_b", (2, 7))], walls=box)
    plan = compile_movement_hypothesis(M.m0r0_oracle_instance(), gs, extra_hazards={(2, 5)})
    sol = plan.solve()
    assert sol.status is PlanStatus.SOLVABLE  # still merges, via a different row
    assert all((2, 5) not in state for state in plan._traj)  # never routes an actor onto the hazard


def test_confirmed_subset_with_no_convergence_is_unsatisfiable():
    """Purpose: when the confirmed alphabet cannot bring the actors together (only a
    shared vertical move, columns fixed), the joint BFS exhausts and reports
    UNSATISFIABLE with the expanded-state count — not a false plan.

    Expected feedback: pass proves GROUNDING_INCOMPLETE/UNSATISFIABLE fire only on a
    genuinely-unreachable goal (the driver may then re-probe). Fail means an
    unmergeable confirmed subset is mislabelled."""
    # only action 2 (down, identical for both) is confirmed: columns never change, so a
    # column-separated pair can never coincide.
    deltas = {("actor_a", 2): (1, 0), ("actor_b", 2): (1, 0)}
    gs = _StubMoveGrounding(deltas, [("actor_a", (2, 3)), ("actor_b", (2, 7))])
    sol = compile_movement_hypothesis(M.m0r0_oracle_instance(), gs).solve()
    assert sol.status is PlanStatus.UNSATISFIABLE
    assert sol.states_searched > 0


def test_extra_walls_are_respected_and_routed_around():
    """Purpose: a cell learned to block at execution time (``extra_walls``) is treated
    as impassable — the joint BFS routes around it and no planned state places an actor
    on it, while the same board without the learned wall merges directly through it.

    Expected feedback: pass proves the online-occupancy augmentation feeds back into
    planning (the partial-block recovery): a wall the parse missed can be added and the
    recompiled plan avoids it. Fail means learned walls are ignored."""
    deltas = {
        ("actor_a", 1): (-1, 0), ("actor_a", 2): (1, 0), ("actor_a", 3): (0, -1), ("actor_a", 4): (0, 1),
        ("actor_b", 1): (-1, 0), ("actor_b", 2): (1, 0), ("actor_b", 3): (0, 1), ("actor_b", 4): (0, -1),
    }
    box = (
        [(0, c) for c in range(10)] + [(5, c) for c in range(10)]
        + [(r, 0) for r in range(6)] + [(r, 9) for r in range(6)]
    )  # a 6x10 arena so the actors have room to route around an interior wall
    gs = _StubMoveGrounding(deltas, [("actor_a", (2, 3)), ("actor_b", (2, 7))], walls=box)

    direct = compile_movement_hypothesis(M.m0r0_oracle_instance(), gs).solve()
    assert direct.status is PlanStatus.SOLVABLE  # converges to a merge in row 2

    plan = compile_movement_hypothesis(M.m0r0_oracle_instance(), gs, extra_walls={(2, 5)})
    sol = plan.solve()
    assert sol.status is PlanStatus.SOLVABLE  # still solvable via a different row
    assert all((2, 5) not in state for state in plan._traj)  # never routes an actor onto the learned wall


def test_no_action_confirmed_for_both_actors_is_grounding_incomplete():
    """Purpose: when no single action has a confirmed edge for BOTH actors, the joint
    alphabet is empty and the plan is GROUNDING_INCOMPLETE (nothing to search).

    Expected feedback: pass proves an empty confirmed alphabet is the incomplete-
    grounding surface, distinct from an exhausted search (UNSATISFIABLE). Fail means the
    compiler searches an empty alphabet or mislabels it."""
    deltas = {("actor_a", 2): (1, 0), ("actor_b", 3): (0, 1)}  # no shared action
    gs = _StubMoveGrounding(deltas, [("actor_a", (2, 3)), ("actor_b", (2, 7))])
    assert compile_movement_hypothesis(M.m0r0_oracle_instance(), gs).solve().status is PlanStatus.GROUNDING_INCOMPLETE


def test_no_merge_path_is_unsatisfiable_with_searched_count():
    """Purpose: when a wall between the actors makes convergence impossible under the
    only measured action, the joint BFS exhausts and reports UNSATISFIABLE carrying
    the count of expanded states (an honest search cost, not a proof of impossibility).

    Expected feedback: pass proves the compiler reports 'no path in the known graph'
    as its own typed surface with the search size recorded (the driver may re-probe
    to complete the occupancy). Fail means an unmergeable board is mislabelled or the
    search size is lost."""
    wall = [(5, 4)]  # a wall on the convergence cell blocks column-merge under action 4
    gs = _grounding_with_converge_delta(walls=wall)
    gs.feed(_frame([(5, 2), (5, 6)], walls=wall))
    plan = compile_movement_hypothesis(M.m0r0_oracle_instance(), gs)
    sol = plan.solve()
    assert sol.status is PlanStatus.UNSATISFIABLE
    assert sol.states_searched > 0


def test_orbit_none_is_byte_identical_to_the_untimed_planner():
    """Purpose: with no orbit (or a single-phase table), solve() takes the untimed path
    unchanged — the P=1 degeneracy the (B) design requires so idx0 (no transients) keeps
    its exact 15-gold plan.

    Expected feedback: pass proves adding the orbit parameter never perturbs the
    orbit-free case (same action sequence). Fail means the time dimension leaked into the
    static-board plan — an idx0 regression."""
    gs = _StubMoveGrounding(_FULL_MIRROR_DELTAS, [("actor_a", (2, 3)), ("actor_b", (2, 7))], walls=_arena(6, 10))
    base = compile_movement_hypothesis(M.m0r0_oracle_instance(), gs).solve()
    # a single-phase (P=1) table degenerates to the untimed planner (guarded at len >= 2)
    degen = compile_movement_hypothesis(
        M.m0r0_oracle_instance(), gs, orbit_phases=[frozenset()], orbit_start_phase=0
    ).solve()
    assert base.status is PlanStatus.SOLVABLE
    assert degen.actions == base.actions
    assert len(base.actions) == 2  # the direct 2-step meet-in-the-middle at (2,5)


def test_orbit_blocks_the_merge_cell_at_its_phase_forcing_a_timed_detour():
    """Purpose: the time-expanded BFS plans over (pos_a, pos_b, t mod P); a patroller
    predicted on the merge cell at the actors' arrival phase blocks it, so the plan waits
    a full period and merges when the cell is free — a strictly longer, phase-correct plan.

    Expected feedback: pass proves the orbit model actually re-routes/waits through a
    deterministic obstacle (the whole point of (B)) while still reaching the exact merge.
    Fail means the orbit is ignored (same length as untimed) or the merge is lost."""
    gs = _StubMoveGrounding(_FULL_MIRROR_DELTAS, [("actor_a", (2, 3)), ("actor_b", (2, 7))], walls=_arena(6, 10))
    # phase 2 puts the patroller on the merge cell (2,5); the naive 2-step merge lands
    # there at phase 2, so it must wait one period and merge at phase 0.
    phases = [frozenset(), frozenset(), frozenset({(2, 5)})]
    plan = compile_movement_hypothesis(
        M.m0r0_oracle_instance(), gs, orbit_phases=phases, orbit_start_phase=0
    )
    sol = plan.solve()
    assert sol.status is PlanStatus.SOLVABLE
    assert len(sol.actions) == 3  # one longer than the untimed 2-step merge (the orbit detour)
    merge_cell = plan._traj[-1]
    assert merge_cell[0] == merge_cell[1]  # still an exact merge
    # the only 2-step merge cell (2,5) is blocked at the arrival phase, so the timed plan
    # either merges elsewhere (a row detour) or waits a period — never the blocked t=2 arrival
    assert not (len(sol.actions) == 2 and merge_cell[0] == (2, 5))


def test_timed_successor_blocks_a_target_and_prunes_a_collision():
    """Purpose: the phase-aware successor (a) treats a next-phase patroller cell as a wall
    for a target (the actor STAYS instead of entering), and (b) prunes the whole action
    when an actor would END on a next-phase patroller cell (a collision — route/wait).

    Expected feedback: pass proves the two orbit-interaction rules the (B) spec names.
    Fail means the actor walks into the patroller (b) or ignores a timed block (a)."""
    gs = _StubMoveGrounding(_FULL_MIRROR_DELTAS, [("actor_a", (2, 4)), ("actor_b", (2, 7))], walls=_arena(6, 10))
    bounds = (0, 5, 0, 9)
    # (a) actor_a's target (2,5) is a patroller cell at next phase -> a stays at (2,4)
    plan = compile_movement_hypothesis(
        M.m0r0_oracle_instance(), gs, orbit_phases=[frozenset(), frozenset({(2, 5)})], orbit_start_phase=0
    )
    bbp = [set(_arena(6, 10)) | ph for ph in plan._orbit_phases]
    nxt = plan._timed_successor(((2, 4), (2, 7), 0), ((0, 1), (0, -1)), bbp, set(), bounds)
    assert nxt == ((2, 4), (2, 6), 1)  # a blocked -> stays (2,4); b moves left to (2,6)
    # (b) actor_a can only stay on (2,4) (its left target (2,3) is a wall) and (2,4) is the
    # patroller's next-phase cell -> the whole action is pruned (collision avoidance)
    plan2 = compile_movement_hypothesis(
        M.m0r0_oracle_instance(), gs, orbit_phases=[frozenset(), frozenset({(2, 4)})], orbit_start_phase=0
    )
    bbp2 = [(set(_arena(6, 10)) | {(2, 3)}) | ph for ph in plan2._orbit_phases]
    nxt2 = plan2._timed_successor(((2, 4), (2, 7), 0), ((0, -1), (0, -1)), bbp2, set(), bounds)
    assert nxt2 is None  # actor_a would remain on the patroller's next-phase cell -> prune
