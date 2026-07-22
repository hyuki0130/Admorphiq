"""R96 STEP (ii): the ControlledGridDynamics movement-family schema.

The SECOND hypothesis family (after R95's cell-state), for COUPLED multi-actor
grid motion. Reuses the shared envelope / ownership / guard / phase machinery
from :mod:`admorphiq.hypothesis_select.schema` (single-sourced — the ``Ownership``
enum, ``_own`` metadata, ``Phase``, and the guard/phase (de)serializers are
imported, never re-defined) and adds only the movement-specific tagged unions.

Family variant v0 = **CoupledActorMerge** (the m0r0 oracle, idx0 + idx1): two
mirror-controlled actors whose per-action deltas are ANTISYMMETRIC in one axis
(a diverge/converge action pair) and SYMMETRIC in the other, ending when they
satisfy an ``ActorRelation`` (the oracle relation is ``same_cell`` — an EXACT
merge, not adjacency). Occupancy is a TYPED union carrying provenance (a bare
blocked-cell set is unsafe — Codex v1 correction); hazards SOFT-RESET on entry
rather than block, so they are ``terminal_cells``, not walls.

Ownership (per the frozen contract):
  * ``model_selected`` = the ``ActorRelation`` relation kind + actor-role
    bindings (from harness shortlists) + phase guards.
  * ``harness_measured`` = the per-action deltas, the occupancy (type + contents),
    the collision policy, the terminal cells, the identified actors.
  * ``compiler_derived`` = the executed PATH (not a schema field).

Scope: schema only — no grounding / verifier / compiler / driver. The verifier
round validates mutant DISCRIMINABILITY; here the frozen mutant table records the
EXPECTED verdicts (honest ``UNKNOWN`` where the m0r0 trace lacks discriminating
evidence).
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, Optional, Union

from admorphiq.hypothesis_select.schema import (
    LevelAdvanced,
    Ownership,
    Phase,
    Verdict,
    _own,
    _phase_from_json,
    _phase_to_json,
    _require,
)

Cell = tuple[int, int]


# ── objective: ActorRelation ────────────────────────────────────────────────


@dataclass(frozen=True)
class ActorRelation:
    """The completion predicate: two actor ROLES stand in a spatial RELATION. The
    role bindings (which harness-shortlisted regions are role_a / role_b) and the
    relation KIND are the model_selected semantics; ``same_cell`` is an EXACT
    merge (the m0r0 oracle), distinct from ``adjacent`` / ``overlap``."""

    KIND = "actor_relation"
    actors: tuple[str, str] = field(metadata=_own(Ownership.MODEL_SELECTED))
    relation: str = field(metadata=_own(Ownership.MODEL_SELECTED))  # same_cell | adjacent | overlap


# ── occupancy: a TYPED union (never a bare blocked-cell set) ─────────────────


@dataclass(frozen=True)
class StaticOccupancy:
    """Walls that do not change within a layout epoch — the full-frame static
    parse (m0r0 idx0/idx1). Carries provenance so a stale/low-confidence read is
    never silently trusted."""

    KIND = "static_occupancy"
    blocked_cells: tuple[Cell, ...]
    confidence: str
    observation_context: str
    layout_epoch: int


@dataclass(frozen=True)
class ObservedEdgeGraph:
    """Passability learned as observed per-cell MOVE edges (which (from -> to)
    steps were seen to succeed) rather than a cell mask — safer where a
    no-displacement probe is ambiguous between wall / dropped-input / settle."""

    KIND = "observed_edge_graph"
    passable_edges: tuple[tuple[Cell, Cell], ...]
    confidence: str
    observation_context: str
    layout_epoch: int


@dataclass(frozen=True)
class StateDependentOccupancy:
    """Passability that is a pure function of state — momentary pressure-plate
    gates (m0r0 L5/L6, banked as inexpressible-in-v0 but REPRESENTABLE here): each
    gate is a plate cell that opens its conditional-wall cells while occupied."""

    KIND = "state_dependent_occupancy"
    gates: tuple[tuple[Cell, tuple[Cell, ...]], ...]  # (plate_cell, conditional_wall_cells)
    confidence: str
    observation_context: str
    layout_epoch: int


Occupancy = Union[StaticOccupancy, ObservedEdgeGraph, StateDependentOccupancy]
_OCCUPANCY_BY_KIND: dict[str, type] = {
    cls.KIND: cls for cls in (StaticOccupancy, ObservedEdgeGraph, StateDependentOccupancy)
}


# ── transition: CoupledGridStep + the verify-only EmpiricalMoveMatrix ────────


@dataclass(frozen=True)
class CoupledGridStep:
    """Per-actor grid steps under one action: each identified actor has its OWN
    ``(dr, dc)`` per action (harness_measured — mirror motion is antisymmetric in
    one axis, symmetric in the other), each blocked INDEPENDENTLY by the occupancy
    (``independent_stay`` — a blocked actor stays while its partner may still
    move, the desync that idx1 needs), with hazard ``terminal_cells`` that
    SOFT-RESET on entry rather than block."""

    KIND = "coupled_grid_step"
    actors: tuple[str, ...] = field(metadata=_own(Ownership.HARNESS_MEASURED))
    # flat per-(role, action) deltas: each entry is (role, action_id, dr, dc)
    per_action_deltas: tuple[tuple[str, int, int, int], ...] = field(
        metadata=_own(Ownership.HARNESS_MEASURED)
    )
    collision_policy: str = field(metadata=_own(Ownership.HARNESS_MEASURED))  # independent_stay | all_or_nothing
    occupancy: Occupancy = field(metadata=_own(Ownership.HARNESS_MEASURED))
    terminal_cells: str = field(metadata=_own(Ownership.HARNESS_MEASURED))  # hazard_soft_reset | blocking_wall


@dataclass(frozen=True)
class EmpiricalMoveMatrix:
    """VERIFY-ONLY transition tag: a fixed per-cell move-effect footprint. The
    verifier MAY check transitions against it, but the compiler will map it to
    UNSUPPORTED — a fixed matrix cannot represent the collision-dependent desync
    of coupled actors, so it must never silently BFS. Schema-representable so the
    mutant / verify path can name it."""

    KIND = "empirical_move_matrix"
    asserted_footprint: Optional[int] = field(default=None, metadata=_own(Ownership.HARNESS_MEASURED))


MovementTransition = Union[CoupledGridStep, EmpiricalMoveMatrix]


# ── envelope ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MovementHypothesis:
    """The movement-family envelope: an ``ActorRelation`` objective, a movement
    transition (``CoupledGridStep`` executable / ``EmpiricalMoveMatrix``
    verify-only), and an ordered phase list (shared ``Phase`` machinery)."""

    objective: ActorRelation = field(metadata=_own(Ownership.HARNESS_MEASURED))
    transition_model: MovementTransition = field(metadata=_own(Ownership.HARNESS_MEASURED))
    phases: tuple[Phase, ...] = field(default=(), metadata=_own(Ownership.HARNESS_MEASURED))


# ── ownership table (pinned by tests) ────────────────────────────────────────

_MOVEMENT_OWNED_CLASSES: tuple[type, ...] = (
    MovementHypothesis,
    ActorRelation,
    CoupledGridStep,
    EmpiricalMoveMatrix,
    StaticOccupancy,
    ObservedEdgeGraph,
    StateDependentOccupancy,
)

MOVEMENT_OWNERSHIP: dict[str, Ownership] = {
    f"{cls.__name__}.{f.name}": f.metadata["ownership"]
    for cls in _MOVEMENT_OWNED_CLASSES
    for f in fields(cls)
    if "ownership" in f.metadata
}

# The semantic slots the model fills for the movement family (the union-arm and
# structural choices are separate). Phase.guard is shared with the cell-state
# family (imported from schema).
MOVEMENT_MODEL_SELECTED_SEMANTICS: frozenset[str] = frozenset(
    {"ActorRelation.actors", "ActorRelation.relation", "Phase.guard"}
)


# ── neutral serialization (model-facing; no provenance labels, no game ids) ──


def _occupancy_to_json(occ: Occupancy) -> dict[str, Any]:
    common = {
        "confidence": occ.confidence,
        "observation_context": occ.observation_context,
        "layout_epoch": occ.layout_epoch,
    }
    if isinstance(occ, StaticOccupancy):
        return {"kind": occ.KIND, "blocked_cells": [[r, c] for r, c in occ.blocked_cells], **common}
    if isinstance(occ, ObservedEdgeGraph):
        return {
            "kind": occ.KIND,
            "passable_edges": [[[a[0], a[1]], [b[0], b[1]]] for a, b in occ.passable_edges],
            **common,
        }
    if isinstance(occ, StateDependentOccupancy):
        return {
            "kind": occ.KIND,
            "gates": [[[p[0], p[1]], [[w[0], w[1]] for w in walls]] for p, walls in occ.gates],
            **common,
        }
    raise TypeError(f"occupancy: unserializable type {type(occ).__name__}")


def _objective_to_json(obj: ActorRelation) -> dict[str, Any]:
    return {"kind": obj.KIND, "actors": list(obj.actors), "relation": obj.relation}


def _transition_to_json(tm: MovementTransition) -> dict[str, Any]:
    if isinstance(tm, CoupledGridStep):
        return {
            "kind": tm.KIND,
            "actors": list(tm.actors),
            "per_action_deltas": [[role, action, dr, dc] for role, action, dr, dc in tm.per_action_deltas],
            "collision_policy": tm.collision_policy,
            "occupancy": _occupancy_to_json(tm.occupancy),
            "terminal_cells": tm.terminal_cells,
        }
    if isinstance(tm, EmpiricalMoveMatrix):
        return {"kind": tm.KIND, "asserted_footprint": tm.asserted_footprint}
    raise TypeError(f"transition_model: unserializable type {type(tm).__name__}")


def to_neutral_json(instance: MovementHypothesis) -> dict[str, Any]:
    """The model-facing serialized form: neutral structural tags + values only, NO
    provenance (no ownership tags, no oracle/mutant labels, no game ids). Reuses
    the shared ``_phase_to_json`` so guard/phase serialization is single-sourced."""
    return {
        "objective": _objective_to_json(instance.objective),
        "transition_model": _transition_to_json(instance.transition_model),
        "phases": [_phase_to_json(p) for p in instance.phases],
    }


def _cell(raw: Any) -> Cell:
    return (int(raw[0]), int(raw[1]))


def _occupancy_from_json(data: dict[str, Any], path: str) -> Occupancy:
    kind = _require(data, "kind", path)
    conf = _require(data, "confidence", f"{path}.confidence")
    ctx = _require(data, "observation_context", f"{path}.observation_context")
    epoch = _require(data, "layout_epoch", f"{path}.layout_epoch")
    if kind == StaticOccupancy.KIND:
        cells = _require(data, "blocked_cells", f"{path}.blocked_cells")
        return StaticOccupancy(tuple(_cell(c) for c in cells), conf, ctx, epoch)
    if kind == ObservedEdgeGraph.KIND:
        edges = _require(data, "passable_edges", f"{path}.passable_edges")
        return ObservedEdgeGraph(tuple((_cell(a), _cell(b)) for a, b in edges), conf, ctx, epoch)
    if kind == StateDependentOccupancy.KIND:
        gates = _require(data, "gates", f"{path}.gates")
        return StateDependentOccupancy(
            tuple((_cell(p), tuple(_cell(w) for w in walls)) for p, walls in gates), conf, ctx, epoch
        )
    raise ValueError(f"{path}.kind: unknown occupancy kind {kind!r}")


def _objective_from_json(data: dict[str, Any], path: str) -> ActorRelation:
    kind = _require(data, "kind", path)
    if kind != ActorRelation.KIND:
        raise ValueError(f"{path}.kind: unknown movement objective kind {kind!r}")
    actors = _require(data, "actors", f"{path}.actors")
    return ActorRelation(
        actors=(str(actors[0]), str(actors[1])),
        relation=_require(data, "relation", f"{path}.relation"),
    )


def _transition_from_json(data: dict[str, Any], path: str) -> MovementTransition:
    kind = _require(data, "kind", path)
    if kind == CoupledGridStep.KIND:
        deltas = _require(data, "per_action_deltas", f"{path}.per_action_deltas")
        return CoupledGridStep(
            actors=tuple(str(a) for a in _require(data, "actors", f"{path}.actors")),
            per_action_deltas=tuple(
                (str(role), int(action), int(dr), int(dc)) for role, action, dr, dc in deltas
            ),
            collision_policy=_require(data, "collision_policy", f"{path}.collision_policy"),
            occupancy=_occupancy_from_json(_require(data, "occupancy", f"{path}.occupancy"), f"{path}.occupancy"),
            terminal_cells=_require(data, "terminal_cells", f"{path}.terminal_cells"),
        )
    if kind == EmpiricalMoveMatrix.KIND:
        return EmpiricalMoveMatrix(asserted_footprint=data.get("asserted_footprint"))
    raise ValueError(f"{path}.kind: unknown movement transition_model kind {kind!r}")


def from_json(data: dict[str, Any]) -> MovementHypothesis:
    """Reconstruct a ``MovementHypothesis`` from ``to_neutral_json`` output,
    round-trip exact. Reuses the shared ``_phase_from_json``. Validation errors
    name the offending field path (the model's later error-feedback channel)."""
    return MovementHypothesis(
        objective=_objective_from_json(_require(data, "objective", "objective"), "objective"),
        transition_model=_transition_from_json(
            _require(data, "transition_model", "transition_model"), "transition_model"
        ),
        phases=tuple(
            _phase_from_json(p, f"phases[{i}]")
            for i, p in enumerate(_require(data, "phases", "phases"))
        ),
    )


# ── canonical ORACLE instance (m0r0 idx0/idx1, decoded ground truth) ─────────


def _m0r0_occupancy() -> StaticOccupancy:
    """A representative static wall parse for the m0r0 oracle fixture. The exact
    cells are harness_measured live (a full-frame parse: floor = background
    colour, walls = the level's zone-sprite cells); the fixture records the TYPE +
    provenance + an illustrative border so the schema shape is faithful."""
    border = tuple((0, c) for c in range(13)) + tuple((12, c) for c in range(13))
    return StaticOccupancy(
        blocked_cells=border,
        confidence="high",
        observation_context="full-frame static parse: floor=background colour, walls=zone-sprite cells",
        layout_epoch=0,
    )


def m0r0_oracle_instance() -> MovementHypothesis:
    """The m0r0 oracle (CoupledActorMerge): two mirror actors MERGE onto one cell
    (``same_cell``). Per-action deltas are the decoded mirror scheme — COLUMNS
    antisymmetric (action 1 diverges the pair, action 4 converges it), ROWS
    symmetric (actions 2/3 move both the same way); each actor is blocked
    independently (``independent_stay``, enabling idx1's wall-desync); hazards
    soft-reset on entry (``hazard_soft_reset``), not walls. Decoded in
    ``.wiki/wiki/games/M0R0.md`` §L1."""
    return MovementHypothesis(
        objective=ActorRelation(actors=("actor_a", "actor_b"), relation="same_cell"),
        transition_model=CoupledGridStep(
            actors=("actor_a", "actor_b"),
            per_action_deltas=(
                ("actor_a", 1, 0, -1), ("actor_a", 2, -1, 0), ("actor_a", 3, 1, 0), ("actor_a", 4, 0, 1),
                ("actor_b", 1, 0, 1), ("actor_b", 2, -1, 0), ("actor_b", 3, 1, 0), ("actor_b", 4, 0, -1),
            ),
            collision_policy="independent_stay",
            occupancy=_m0r0_occupancy(),
            terminal_cells="hazard_soft_reset",
        ),
        phases=(Phase(guard=(LevelAdvanced(),), objective=None),),
    )


# ── frozen mutant fixtures + expected-verdict table ──────────────────────────


@dataclass(frozen=True)
class MovementMutantCase:
    """A wrong movement hypothesis + the verdict the future verifier must return,
    with a one-line reason. Shipped as DATA (``MUTANTS_MOVEMENT``); the verifier
    round validates DISCRIMINABILITY, so honest ``UNKNOWN`` is recorded where the
    m0r0 trace lacks a separating frame."""

    name: str
    instance: MovementHypothesis
    expected_verdict: Verdict
    reason: str


def _adjacent_relation_mutant() -> MovementHypothesis:
    base = m0r0_oracle_instance()
    return MovementHypothesis(
        objective=ActorRelation(actors=base.objective.actors, relation="adjacent"),
        transition_model=base.transition_model,
        phases=base.phases,
    )


def _static_goal_mutant() -> MovementHypothesis:
    base = m0r0_oracle_instance()
    return MovementHypothesis(
        # role_b bound to the partner's STATIC spawn region instead of the moving actor
        objective=ActorRelation(actors=("actor_a", "partner_spawn_static"), relation="same_cell"),
        transition_model=base.transition_model,
        phases=base.phases,
    )


def _single_actor_mutant() -> MovementHypothesis:
    base = m0r0_oracle_instance()
    tm = base.transition_model
    frozen_b = tuple(
        (role, action, 0, 0) if role == "actor_b" else (role, action, dr, dc)
        for role, action, dr, dc in tm.per_action_deltas
    )
    return MovementHypothesis(
        objective=base.objective,
        transition_model=CoupledGridStep(
            actors=tm.actors, per_action_deltas=frozen_b, collision_policy=tm.collision_policy,
            occupancy=tm.occupancy, terminal_cells=tm.terminal_cells,
        ),
        phases=base.phases,
    )


def _same_delta_mutant() -> MovementHypothesis:
    base = m0r0_oracle_instance()
    tm = base.transition_model
    a_deltas = {action: (dr, dc) for role, action, dr, dc in tm.per_action_deltas if role == "actor_a"}
    symmetric = tuple(
        (role, action, a_deltas[action][0], a_deltas[action][1])
        for role, action, _dr, _dc in tm.per_action_deltas
    )
    return MovementHypothesis(
        objective=base.objective,
        transition_model=CoupledGridStep(
            actors=tm.actors, per_action_deltas=symmetric, collision_policy=tm.collision_policy,
            occupancy=tm.occupancy, terminal_cells=tm.terminal_cells,
        ),
        phases=base.phases,
    )


def _all_or_nothing_mutant() -> MovementHypothesis:
    base = m0r0_oracle_instance()
    tm = base.transition_model
    return MovementHypothesis(
        objective=base.objective,
        transition_model=CoupledGridStep(
            actors=tm.actors, per_action_deltas=tm.per_action_deltas, collision_policy="all_or_nothing",
            occupancy=tm.occupancy, terminal_cells=tm.terminal_cells,
        ),
        phases=base.phases,
    )


def _hazard_as_wall_mutant() -> MovementHypothesis:
    base = m0r0_oracle_instance()
    tm = base.transition_model
    return MovementHypothesis(
        objective=base.objective,
        transition_model=CoupledGridStep(
            actors=tm.actors, per_action_deltas=tm.per_action_deltas, collision_policy=tm.collision_policy,
            occupancy=tm.occupancy, terminal_cells="blocking_wall",
        ),
        phases=base.phases,
    )


MUTANTS_MOVEMENT: tuple[MovementMutantCase, ...] = (
    MovementMutantCase(
        name="m0r0_adjacent_relation",
        instance=_adjacent_relation_mutant(),
        expected_verdict=Verdict.UNKNOWN,
        reason=(
            "the merge terminal satisfies both same_cell and adjacent-just-before; no near-terminal "
            "non-merge frame in the trace separates exact merge from adjacency"
        ),
    ),
    MovementMutantCase(
        name="m0r0_static_goal_not_relation",
        instance=_static_goal_mutant(),
        expected_verdict=Verdict.CONTRADICTED,
        reason=(
            "binds role_b to the partner's static spawn cell; the partner is observed to move, so the "
            "actors coincide elsewhere at the merge -> same_cell there is false"
        ),
    ),
    MovementMutantCase(
        name="m0r0_single_actor_motion",
        instance=_single_actor_mutant(),
        expected_verdict=Verdict.CONTRADICTED,
        reason=(
            "claims role_b never moves (all-zero deltas); probe frames show role_b displaces under "
            "every action"
        ),
    ),
    MovementMutantCase(
        name="m0r0_same_delta_both_actors",
        instance=_same_delta_mutant(),
        expected_verdict=Verdict.CONTRADICTED,
        reason=(
            "claims both actors share the same delta on every action; actions 1/4 are observed to move "
            "the actors in OPPOSITE column directions (antisymmetric) — rejects naive greedy convergence"
        ),
    ),
    MovementMutantCase(
        name="m0r0_all_or_nothing_blocking",
        instance=_all_or_nothing_mutant(),
        expected_verdict=Verdict.CONTRADICTED,
        reason=(
            "claims a blocked move freezes BOTH actors; idx1's wall-desync (one actor blocked while the "
            "partner advances) is observed, refuting all-or-nothing"
        ),
    ),
    MovementMutantCase(
        name="m0r0_hazard_as_wall",
        instance=_hazard_as_wall_mutant(),
        expected_verdict=Verdict.UNKNOWN,
        reason=(
            "the gold path enters ZERO hazard cells, so wall-blocking vs soft-reset-on-entry is not "
            "discriminable from the trace"
        ),
    ),
)


__all__ = [
    "ActorRelation",
    "StaticOccupancy",
    "ObservedEdgeGraph",
    "StateDependentOccupancy",
    "Occupancy",
    "CoupledGridStep",
    "EmpiricalMoveMatrix",
    "MovementTransition",
    "MovementHypothesis",
    "MOVEMENT_OWNERSHIP",
    "MOVEMENT_MODEL_SELECTED_SEMANTICS",
    "to_neutral_json",
    "from_json",
    "m0r0_oracle_instance",
    "MovementMutantCase",
    "MUTANTS_MOVEMENT",
]
