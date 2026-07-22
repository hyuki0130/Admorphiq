"""R96 STEP (v): the movement-family compiler (schema instance -> executable plan).

Given a verified :class:`~admorphiq.hypothesis_select.schema_movement.MovementHypothesis`
and a live :class:`~admorphiq.hypothesis_select.grounding.GroundingService`, emit a
plan a driver steps against the frame stream — the SAME plan-stepper contract as
the R95 cell-state compiler (``PlanStatus`` / ``Terminal`` / typed failure surfaces
are single-sourced from :mod:`admorphiq.hypothesis_select.compiler`). Dispatch is
on SCHEMA TAGS ONLY (objective + transition kind) — never a game id, no adapter
imports (the same quarantine as grounding).

One compilable plan (the movement family's executable arm):

* **ActorRelation x CoupledGridStep -> joint two-actor BFS.** The state is the pair
  of actor cells ``(pos_a, pos_b)``; each action applies BOTH actors' measured
  deltas with per-actor ``independent_stay`` blocking (an actor whose target is a
  wall stays while its partner may still move — the desync idx1 needs); a known
  hazard cell is ROUTED AROUND (an action that would drive either actor into a
  hazard is pruned, never relied on as a soft-reset); the goal is the instance's
  ``ActorRelation`` predicate (the oracle relation is ``same_cell`` — an exact
  merge). The search emits the action sequence, and each emitted move is CONFIRMED
  on the next frame — the observed actor cells must match the planned successor, or
  the plan is ``DIVERGED`` (never a silent continue).

Why the transition MODEL is read from live grounding, not the instance's carried
deltas: the action-id <-> delta numbering is HASH-VARIABLE per board (the same
finding that made the step-iv verifier structure-based), so only the board's OWN
measured delta table yields EXECUTABLE action ids. The instance supplies the
model-selected GOAL (``ActorRelation.relation``), the actor roles, and the dispatch
tag; grounding supplies the live world (actor positions, occupancy walls, hazard
cells) and the per-move confirmation oracle.

The verify-only ``EmpiricalMoveMatrix`` transition compiles to ``UNSUPPORTED`` — a
fixed per-cell matrix cannot represent the collision-dependent desync of coupled
actors, so it must never silently BFS (a typed compile-time surface, distinct from
an unknown objective/transition COMBINATION, which raises).

Failure surfaces are typed (``DIVERGED`` / ``GROUNDING_INCOMPLETE`` /
``UNSATISFIABLE`` / ``UNSUPPORTED``) — the attribution hooks for the live gate.

Scope: compilation + offline stepping only — no LLM, no live env driver (step vi).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Optional, Union

from admorphiq.hypothesis_select.compiler import PlanStatus, Terminal
from admorphiq.hypothesis_select.grounding import UNKNOWN, GroundingService
from admorphiq.hypothesis_select.schema_movement import (
    ActorRelation,
    CoupledGridStep,
    EmpiricalMoveMatrix,
    MovementHypothesis,
)

Cell = tuple[int, int]
JointState = tuple[Cell, Cell]
Bounds = tuple[int, int, int, int]
World = tuple[JointState, dict[int, tuple[Cell, Cell]], set[Cell], set[Cell], Bounds]


@dataclass(frozen=True)
class Move:
    """An emitted simple action (ACTION1-4) — movement has no coordinate, unlike the
    cell-state family's ACTION6 ``Click``."""

    action: int


MoveStepResult = Union[Move, Terminal]


@dataclass(frozen=True)
class MovementSolution:
    """The offline joint-BFS result: the emitted action sequence reaching the
    relation predicate, and the number of joint states expanded (an honest search
    cost — a large count on an ``UNSATISFIABLE`` verdict flags possibly-incomplete
    occupancy knowledge, not a proven impossibility). ``status`` is SOLVABLE / DONE
    / a typed failure."""

    status: PlanStatus
    actions: tuple[int, ...]
    states_searched: int


def _relation_satisfied(a: Cell, b: Cell, relation: str) -> bool:
    """The ``ActorRelation`` goal predicate over the two actor cells."""
    if relation == "same_cell" or relation == "overlap":
        return a == b
    if relation == "adjacent":
        return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
    return False


class CoupledGridStepPlan:
    """ActorRelation x CoupledGridStep: joint two-actor BFS over the live occupancy
    toward the relation predicate, with per-move confirmation."""

    def __init__(
        self, objective: ActorRelation, grounding: GroundingService, extra_walls: Optional[set[Cell]] = None
    ) -> None:
        self._relation = objective.relation
        self._g = grounding
        # Cells learned to block at EXECUTION time (a partial block revealed an actor
        # could not reach a cell the parse thought was floor) — an online occupancy
        # augmentation the driver feeds back so the recompiled plan routes around it.
        self._extra_walls = set(extra_walls) if extra_walls else set()
        self._solution: Optional[MovementSolution] = None
        self._traj: tuple[JointState, ...] = ()  # planned states: _traj[k] = state after k actions
        self._cursor = 0  # index of the next action to emit / the move awaiting confirmation

    # ── world read (live grounding — hash-correct deltas, per-board occupancy) ──

    def _read_world(self) -> Optional[World]:
        """The live movement world: (start joint state, per-action joint deltas,
        wall cells, hazard cells, bounds). ``None`` when the deltas / actors /
        occupancy are not yet grounded (-> GROUNDING_INCOMPLETE)."""
        deltas_g = self._g.movement_deltas()
        actors_g = self._g.movement_actors()
        occ_g = self._g.movement_occupancy()
        if deltas_g is UNKNOWN or actors_g is UNKNOWN or occ_g is UNKNOWN:
            return None
        pos = {aid: (int(r), int(c)) for aid, (r, c) in actors_g.value}
        if "actor_a" not in pos or "actor_b" not in pos:
            return None
        # per-action joint deltas: only actions where BOTH actors have a measured delta
        raw = dict(deltas_g.value)
        joint: dict[int, tuple[Cell, Cell]] = {}
        for action in sorted({act for _aid, act in raw}):
            da, db = raw.get(("actor_a", action)), raw.get(("actor_b", action))
            if da is not None and db is not None:
                joint[action] = (da, db)
        if not joint:
            return None
        walls = {(int(r), int(c)) for r, c in occ_g.value.blocked_cells} | self._extra_walls
        hazards_g = self._g.movement_hazard_cells()
        hazards = set() if hazards_g is UNKNOWN else {(int(r), int(c)) for r, c in hazards_g.value}
        start = (pos["actor_a"], pos["actor_b"])
        rows = [start[0][0], start[1][0]] + [r for r, _c in walls]
        cols = [start[0][1], start[1][1]] + [c for _r, c in walls]
        bounds = (min(rows), max(rows), min(cols), max(cols))
        return start, joint, walls, hazards, bounds

    def _step_actor(
        self, pos: Cell, delta: Cell, walls: set[Cell], hazards: set[Cell], bounds: Bounds
    ) -> Optional[Cell]:
        """One actor's next cell under ``delta`` with ``independent_stay`` blocking.
        Returns the new cell (a wall / out-of-bounds target -> STAY), or ``None`` iff
        the target is a hazard (the caller prunes the whole action — route around)."""
        tgt = (pos[0] + delta[0], pos[1] + delta[1])
        if tgt in hazards:
            return None
        r0, r1, c0, c1 = bounds
        if tgt in walls or not (r0 <= tgt[0] <= r1 and c0 <= tgt[1] <= c1):
            return pos  # blocked -> stay (independent of the partner)
        return tgt

    def _successor(
        self, state: JointState, joint_delta: tuple[Cell, Cell],
        walls: set[Cell], hazards: set[Cell], bounds: Bounds,
    ) -> Optional[JointState]:
        na = self._step_actor(state[0], joint_delta[0], walls, hazards, bounds)
        nb = self._step_actor(state[1], joint_delta[1], walls, hazards, bounds)
        if na is None or nb is None:
            return None  # an actor would enter a hazard -> prune (do not rely on the reset)
        return (na, nb)

    def solve(self) -> MovementSolution:
        """Joint two-actor BFS toward the relation predicate. GROUNDING_INCOMPLETE
        until deltas + actors + occupancy are grounded; DONE if the actors already
        satisfy the relation; SOLVABLE with the action sequence otherwise;
        UNSATISFIABLE (with the expanded-state count) when the joint graph has no
        satisfying state reachable from the start."""
        if self._solution is not None:
            return self._solution
        world = self._read_world()
        if world is None:
            return MovementSolution(PlanStatus.GROUNDING_INCOMPLETE, (), 0)
        start, joint, walls, hazards, bounds = world
        if _relation_satisfied(start[0], start[1], self._relation):
            self._solution = MovementSolution(PlanStatus.DONE, (), 1)
            self._traj = (start,)
            return self._solution
        parent: dict[JointState, tuple[JointState, int]] = {}
        seen = {start}
        frontier: deque[JointState] = deque([start])
        goal: Optional[JointState] = None
        while frontier:
            state = frontier.popleft()
            for action, jd in joint.items():
                nxt = self._successor(state, jd, walls, hazards, bounds)
                if nxt is None or nxt in seen:
                    continue
                seen.add(nxt)
                parent[nxt] = (state, action)
                if _relation_satisfied(nxt[0], nxt[1], self._relation):
                    goal = nxt
                    frontier.clear()
                    break
                frontier.append(nxt)
        if goal is None:
            self._solution = MovementSolution(PlanStatus.UNSATISFIABLE, (), len(seen))
            self._traj = (start,)
            return self._solution
        actions: list[int] = []
        states: list[JointState] = [goal]
        node = goal
        while node != start:
            prev, action = parent[node]
            actions.append(action)
            states.append(prev)
            node = prev
        actions.reverse()
        states.reverse()
        self._solution = MovementSolution(PlanStatus.SOLVABLE, tuple(actions), len(seen))
        self._traj = tuple(states)
        return self._solution

    def step(self, frame: Any) -> MoveStepResult:
        """Feed ``frame``, CONFIRM the previous move's planned successor against the
        observed actor cells (DIVERGED on mismatch), then emit the next planned Move
        or a terminal status. The observed cells are compared as a SET (robust to
        actor-id labelling / crossings and to the merge, where two cells coincide
        into one)."""
        self._g.feed(frame)
        if self._cursor > 0:
            observed = self._observed_cells()
            predicted = {self._traj[self._cursor][0], self._traj[self._cursor][1]}
            if observed is None or observed != predicted:
                return Terminal(PlanStatus.DIVERGED)
        solution = self.solve()
        if solution.status in (
            PlanStatus.GROUNDING_INCOMPLETE,
            PlanStatus.UNSATISFIABLE,
        ):
            return Terminal(solution.status)
        if self._cursor >= len(solution.actions):
            return Terminal(PlanStatus.DONE)
        action = solution.actions[self._cursor]
        self._cursor += 1
        return Move(action)

    def _observed_cells(self) -> Optional[set[Cell]]:
        actors = self._g.movement_actors()
        if actors is UNKNOWN:
            return None
        return {(int(r), int(c)) for _aid, (r, c) in actors.value}


class UnsupportedMovementPlan:
    """The verify-only ``EmpiricalMoveMatrix`` arm: a KNOWN transition tag that the
    compiler deliberately will not execute (a fixed matrix cannot represent
    collision-dependent desync). Every step is the typed ``UNSUPPORTED`` terminal —
    it never BFSes."""

    def solve(self) -> MovementSolution:
        return MovementSolution(PlanStatus.UNSUPPORTED, (), 0)

    def step(self, _frame: Any) -> MoveStepResult:
        return Terminal(PlanStatus.UNSUPPORTED)


MovementPlan = Union[CoupledGridStepPlan, UnsupportedMovementPlan]


def compile_movement_hypothesis(
    instance: MovementHypothesis, grounding: GroundingService, extra_walls: Optional[set[Cell]] = None
) -> MovementPlan:
    """Compile a movement hypothesis into a plan, dispatching ONLY on the schema's
    objective + transition-model tags (never a game id). ``EmpiricalMoveMatrix`` maps
    to the typed ``UNSUPPORTED`` plan; an unknown objective/transition COMBINATION
    raises (distinct from a known-but-non-executable tag). ``extra_walls`` are cells
    learned to block at execution time (online occupancy augmentation)."""
    objective, transition = instance.objective, instance.transition_model
    if isinstance(objective, ActorRelation):
        if isinstance(transition, CoupledGridStep):
            return CoupledGridStepPlan(objective, grounding, extra_walls=extra_walls)
        if isinstance(transition, EmpiricalMoveMatrix):
            return UnsupportedMovementPlan()
    raise ValueError(
        f"no compiled movement plan for objective {type(objective).__name__} x "
        f"transition {type(transition).__name__}"
    )


__all__ = [
    "Move",
    "MoveStepResult",
    "MovementSolution",
    "CoupledGridStepPlan",
    "UnsupportedMovementPlan",
    "MovementPlan",
    "compile_movement_hypothesis",
]
