"""R98 STEP (ii): the FlowDeflectionDynamics family schema.

The THIRD hypothesis family (after R95's cell-state and R96's movement), for
TWO-PHASE place-then-propagate boards: the agent arranges deflector pieces during
a CHANGE phase, commits once, and a scripted SPILL propagates flow from fixed
emitters to a fixpoint, after which a settle verdict decides the level.

Reuses the shared envelope machinery from :mod:`admorphiq.hypothesis_select.schema`
(``Ownership``, ``_own``, ``Phase``, ``Verdict``, the guard/phase (de)serializers)
and adds only the flow-specific tagged unions.

Family variant v0 = ``PlaceThenPropagate`` (the sp80 idx0 oracle), scoped to
STRAIGHT splitter pieces. The design's central claim is that for this family the
transition model IS the simulator: the response table decides the predicted
trajectory, so a wrong table yields a plan the live spill falsifies. That claim is
measured, not asserted — the reference propagator built from this table reproduces
the engine's outcome on every reachable oracle placement and its cell-exact
trajectory on both probe placements.

Ownership (per the contract frozen 2026-08-22):
  * ``model_selected`` = the response-table slots and the objective's completion /
    hazard policy / sink-role binding, plus phase guards.
  * ``harness_measured`` = piece footprints, per-action deltas, control mode,
    emitters, initial direction, placement constraints, commit action, the budget
    and the failure semantics. Several of these are declared MEASURED PREMISES —
    supplied by the harness and excluded from model credit — because the certified
    discovery trace cannot establish them.
  * ``compiler_derived`` = the placement PLAN (not a schema field).

Gating, as MEASURED by ``scripts/rounds/R98/gated_enum_test.py``:
  * outcome-gated: ``piece_spawn``, ``piece_direction``, ``sink_predicate``,
    ``sink_miss``, ``hazard``;
  * verifier-gated only: ``piece_propagation`` (it changes trajectories but never
    who wins);
  * NON-GATING ``UNKNOWN``: ``own_flow`` and ``boundary`` — both were measured
    INERT at the criterion level, so forcing a closed choice from absent evidence
    would manufacture a false result.

Scope: schema only — no grounding / verifier / compiler / driver. The frozen mutant
table records EXPECTED verdicts, with honest ``UNKNOWN`` where the criterion level
offers no discriminating opportunity (proved by exhaustive placement sweep, not
assumed).
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

UNKNOWN = "unknown"

_COMPLETIONS = frozenset({"all", "count"})
_HAZARD_POLICIES = frozenset({"fatal_on_contact", "neutral"})
_PIECE_SPAWNS = frozenset({"empty_flanks_only", "both_flanks", "none"})
_PIECE_DIRECTIONS = frozenset({"preserved", "outward_turned"})
_PIECE_PROPAGATIONS = frozenset({"cellwise_iterative", "edge_teleport"})
_SINK_PREDICATES = frozenset({"same_sink_flanks", "contact"})
_SINK_MISSES = frozenset({"spread_like_piece", "stop", "absorb"})
_HAZARD_RESPONSES = frozenset({"terminate_fatal", "terminate_local", "pass_through", UNKNOWN})
_OWN_FLOW_RESPONSES = frozenset({"advance_front", "overwrite", "terminate", UNKNOWN})
_BOUNDARY_RESPONSES = frozenset({"terminate_harmless", "reflect", UNKNOWN})
_CONTROL_MODES = frozenset({"select_then_translate", "direct_translate"})
_PERSISTENCE = frozenset({"persists", "resets"})
_SELECTION_RESET = frozenset({"resets_to_default", "persists"})
_EXHAUSTION = frozenset({"terminal_loss", "no_op"})


def _check(value: str, allowed: frozenset[str], name: str) -> None:
    if value not in allowed:
        raise ValueError(f"{name}: {value!r} not in {sorted(allowed)}")


# ── objective union ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CoverAllSinks:
    """The executable objective: every sink region must end SATISFIED and the
    attempt must respect the hazard policy. ``completion`` and ``hazard_policy``
    are the model's semantic choices; the sink role binding selects which
    harness-shortlisted regions are sinks."""

    KIND = "cover_all_sinks"

    sink_roles: tuple[str, ...] = field(metadata=_own(Ownership.MODEL_SELECTED))
    completion: str = field(metadata=_own(Ownership.MODEL_SELECTED))
    hazard_policy: str = field(metadata=_own(Ownership.MODEL_SELECTED))
    completion_count: Optional[int] = field(default=None, metadata=_own(Ownership.MODEL_SELECTED))

    def __post_init__(self) -> None:
        _check(self.completion, _COMPLETIONS, "CoverAllSinks.completion")
        _check(self.hazard_policy, _HAZARD_POLICIES, "CoverAllSinks.hazard_policy")
        if (self.completion == "count") != (self.completion_count is not None):
            raise ValueError(
                "CoverAllSinks.completion_count is required exactly when completion == 'count'"
            )


@dataclass(frozen=True)
class AnySinkCovered:
    """VERIFY-ONLY objective: a single satisfied sink ends the level. Nameable by a
    mutant so the any-vs-all question is representable; the compiler maps it to
    UNSUPPORTED. It is NEVER counted as killed merely for being unsupported —
    only observed evidence may contradict it."""

    KIND = "any_sink_covered"

    sink_roles: tuple[str, ...] = field(metadata=_own(Ownership.MODEL_SELECTED))


FlowObjective = Union[CoverAllSinks, AnySinkCovered]
_OBJECTIVE_BY_KIND: dict[str, type] = {
    cls.KIND: cls for cls in (CoverAllSinks, AnySinkCovered)
}


# ── the response table: the model-selected semantics ────────────────────────


@dataclass(frozen=True)
class PieceResponse:
    """What the flow does when a deflector piece is directly ahead. Decomposed
    into three slots so that models which merely LOOK equivalent become distinct
    choices: a stream that teleports to the piece's outer edges and a stream that
    walks there one cell per tick predict the same endpoints but different
    trajectories, and an outward-turning split predicts different endpoints."""

    spawn: str = field(metadata=_own(Ownership.MODEL_SELECTED))
    direction: str = field(metadata=_own(Ownership.MODEL_SELECTED))
    propagation: str = field(metadata=_own(Ownership.MODEL_SELECTED))

    def __post_init__(self) -> None:
        _check(self.spawn, _PIECE_SPAWNS, "PieceResponse.spawn")
        _check(self.direction, _PIECE_DIRECTIONS, "PieceResponse.direction")
        _check(self.propagation, _PIECE_PROPAGATIONS, "PieceResponse.propagation")


@dataclass(frozen=True)
class SinkResponse:
    """What the flow does when a sink is directly ahead: the satisfaction
    predicate AND the behaviour on a miss. v1.1 left the miss untyped, which made
    'satisfies only from the mouth' and 'stops dead on any sink contact'
    indistinguishable by type."""

    predicate: str = field(metadata=_own(Ownership.MODEL_SELECTED))
    miss: str = field(metadata=_own(Ownership.MODEL_SELECTED))

    def __post_init__(self) -> None:
        _check(self.predicate, _SINK_PREDICATES, "SinkResponse.predicate")
        _check(self.miss, _SINK_MISSES, "SinkResponse.miss")


@dataclass(frozen=True)
class ResponseTable:
    """One closed choice per encountered class, keyed by piece CLASS so a board
    mixing straight and angled pieces stays a future extension rather than a
    silent misfit. ``own_flow`` and ``boundary`` default to ``UNKNOWN`` because
    they were measured INERT at the criterion level."""

    piece_by_class: tuple[tuple[str, PieceResponse], ...] = field(
        metadata=_own(Ownership.MODEL_SELECTED)
    )
    sink: SinkResponse = field(metadata=_own(Ownership.MODEL_SELECTED))
    hazard: str = field(metadata=_own(Ownership.MODEL_SELECTED))
    own_flow: str = field(default=UNKNOWN, metadata=_own(Ownership.MODEL_SELECTED))
    boundary: str = field(default=UNKNOWN, metadata=_own(Ownership.MODEL_SELECTED))

    def __post_init__(self) -> None:
        if not self.piece_by_class:
            raise ValueError("ResponseTable.piece_by_class: at least one piece class required")
        _check(self.hazard, _HAZARD_RESPONSES, "ResponseTable.hazard")
        _check(self.own_flow, _OWN_FLOW_RESPONSES, "ResponseTable.own_flow")
        _check(self.boundary, _BOUNDARY_RESPONSES, "ResponseTable.boundary")


# ── measured premises: supplied by the harness, excluded from model credit ───


@dataclass(frozen=True)
class PlacementConstraints:
    """Where a piece may go. ``established`` names the subset the certified
    discovery trace actually demonstrates; everything else is an UNESTABLISHED
    PREMISE and must never be scored as a measurement (Codex correction 2)."""

    sink_keepout_margin: int
    row_bound: Optional[int]
    pieces_mutually_permeable: bool
    blocked_by: tuple[str, ...]
    established: tuple[str, ...]


@dataclass(frozen=True)
class Budget:
    """The engine's own action allowance — a distinct resource from the commit
    cap, and terminal when exhausted. Typing it is what stops a hypothesis from
    silently assuming unlimited probing."""

    step_allowance: int
    consuming_actions: tuple[str, ...]
    exhaustion: str

    def __post_init__(self) -> None:
        _check(self.exhaustion, _EXHAUSTION, "Budget.exhaustion")


@dataclass(frozen=True)
class FailureSemantics:
    """What a failed commit restores. Without the flow and satisfaction fields a
    cumulative-progress-across-commits model stays representable and therefore
    unfalsified — the reason v1.1's single ``layout`` field was insufficient."""

    attempt_cap: int
    layout: str
    flow: str
    sink_satisfaction: str
    selection: str

    def __post_init__(self) -> None:
        _check(self.layout, _PERSISTENCE, "FailureSemantics.layout")
        _check(self.flow, _PERSISTENCE, "FailureSemantics.flow")
        _check(self.sink_satisfaction, _PERSISTENCE, "FailureSemantics.sink_satisfaction")
        _check(self.selection, _SELECTION_RESET, "FailureSemantics.selection")


# ── transition union ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PlaceThenPropagate:
    """The executable transition: arrange pieces under measured controls, commit
    once, then propagate flow from the emitters under the response table until a
    fixpoint, and read the settle verdict."""

    KIND = "place_then_propagate"

    control_mode: str = field(metadata=_own(Ownership.HARNESS_MEASURED))
    piece_deltas: tuple[tuple[int, int, int], ...] = field(metadata=_own(Ownership.HARNESS_MEASURED))
    piece_footprints: tuple[tuple[str, tuple[Cell, ...]], ...] = field(
        metadata=_own(Ownership.HARNESS_MEASURED)
    )
    emitters: tuple[Cell, ...] = field(metadata=_own(Ownership.HARNESS_MEASURED))
    initial_direction: tuple[int, int] = field(metadata=_own(Ownership.HARNESS_MEASURED))
    commit_action: int = field(metadata=_own(Ownership.HARNESS_MEASURED))
    placement_constraints: PlacementConstraints = field(metadata=_own(Ownership.HARNESS_MEASURED))
    budget: Budget = field(metadata=_own(Ownership.HARNESS_MEASURED))
    failure_semantics: FailureSemantics = field(metadata=_own(Ownership.HARNESS_MEASURED))
    responses: ResponseTable = field(metadata=_own(Ownership.MODEL_SELECTED))
    observation_channel: str = field(
        default="animation_layers", metadata=_own(Ownership.HARNESS_MEASURED)
    )
    epoch: str = field(
        default="settle_to_fixpoint_then_verdict", metadata=_own(Ownership.HARNESS_MEASURED)
    )

    def __post_init__(self) -> None:
        _check(self.control_mode, _CONTROL_MODES, "PlaceThenPropagate.control_mode")


@dataclass(frozen=True)
class EmpiricalSpillMatrix:
    """VERIFY-ONLY transition: a committed-layout to outcome lookup with no
    propagation model. The compiler maps it to UNSUPPORTED so it can never
    silently plan — the ``EmpiricalMoveMatrix`` precedent from R96."""

    KIND = "empirical_spill_matrix"

    asserted_entries: Optional[int] = field(default=None, metadata=_own(Ownership.HARNESS_MEASURED))


FlowTransition = Union[PlaceThenPropagate, EmpiricalSpillMatrix]


# ── envelope ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FlowHypothesis:
    """The flow-family envelope: a coverage objective, a flow transition
    (``PlaceThenPropagate`` executable / ``EmpiricalSpillMatrix`` verify-only),
    and an ordered phase list using the shared ``Phase`` machinery."""

    objective: FlowObjective = field(metadata=_own(Ownership.HARNESS_MEASURED))
    transition_model: FlowTransition = field(metadata=_own(Ownership.HARNESS_MEASURED))
    phases: tuple[Phase, ...] = field(default=(), metadata=_own(Ownership.HARNESS_MEASURED))


# ── ownership + gating tables (pinned by tests) ─────────────────────────────

_FLOW_OWNED_CLASSES: tuple[type, ...] = (
    FlowHypothesis,
    CoverAllSinks,
    AnySinkCovered,
    PieceResponse,
    SinkResponse,
    ResponseTable,
    PlaceThenPropagate,
    EmpiricalSpillMatrix,
)

FLOW_OWNERSHIP: dict[str, Ownership] = {
    f"{cls.__name__}.{f.name}": f.metadata["ownership"]
    for cls in _FLOW_OWNED_CLASSES
    for f in fields(cls)
    if "ownership" in f.metadata
}

FLOW_MODEL_SELECTED_SEMANTICS: frozenset[str] = frozenset(
    {
        "PieceResponse.spawn",
        "PieceResponse.direction",
        "PieceResponse.propagation",
        "SinkResponse.predicate",
        "SinkResponse.miss",
        "ResponseTable.hazard",
        "CoverAllSinks.completion",
        "CoverAllSinks.hazard_policy",
        "CoverAllSinks.sink_roles",
        "Phase.guard",
    }
)

# Measured by scripts/rounds/R98/gated_enum_test.py against the live engine.
OUTCOME_GATED_SLOTS: frozenset[str] = frozenset(
    {
        "PieceResponse.spawn",
        "PieceResponse.direction",
        "SinkResponse.predicate",
        "SinkResponse.miss",
        "ResponseTable.hazard",
    }
)
VERIFIER_GATED_SLOTS: frozenset[str] = frozenset({"PieceResponse.propagation"})
NON_GATING_SLOTS: frozenset[str] = frozenset(
    {"ResponseTable.own_flow", "ResponseTable.boundary"}
)

# Data-indistinguishable answers at the criterion level: scoring must accept any
# member of a class, never only the oracle's member (the R95a ft09 precedent).
EQUIVALENCE_CLASSES: tuple[tuple[str, frozenset[str]], ...] = (
    ("PieceResponse.spawn", frozenset({"empty_flanks_only", "both_flanks"})),
)


# ── neutral serialization (model-facing; no provenance, no game ids) ────────


def _objective_to_json(obj: FlowObjective) -> dict[str, Any]:
    if isinstance(obj, CoverAllSinks):
        out = {
            "kind": obj.KIND,
            "sink_roles": list(obj.sink_roles),
            "completion": obj.completion,
            "hazard_policy": obj.hazard_policy,
        }
        if obj.completion_count is not None:
            out["completion_count"] = obj.completion_count
        return out
    return {"kind": obj.KIND, "sink_roles": list(obj.sink_roles)}


def _responses_to_json(t: ResponseTable) -> dict[str, Any]:
    return {
        "piece_by_class": [
            {
                "piece_class": name,
                "spawn": r.spawn,
                "direction": r.direction,
                "propagation": r.propagation,
            }
            for name, r in t.piece_by_class
        ],
        "sink": {"predicate": t.sink.predicate, "miss": t.sink.miss},
        "hazard": t.hazard,
        "own_flow": t.own_flow,
        "boundary": t.boundary,
    }


def _transition_to_json(tm: FlowTransition) -> dict[str, Any]:
    if isinstance(tm, EmpiricalSpillMatrix):
        return {"kind": tm.KIND, "asserted_entries": tm.asserted_entries}
    pc = tm.placement_constraints
    return {
        "kind": tm.KIND,
        "control_mode": tm.control_mode,
        "piece_deltas": [list(d) for d in tm.piece_deltas],
        "piece_footprints": [
            {"piece": name, "cells": [list(c) for c in cells]}
            for name, cells in tm.piece_footprints
        ],
        "emitters": [list(c) for c in tm.emitters],
        "initial_direction": list(tm.initial_direction),
        "commit_action": tm.commit_action,
        "placement_constraints": {
            "sink_keepout_margin": pc.sink_keepout_margin,
            "row_bound": pc.row_bound,
            "pieces_mutually_permeable": pc.pieces_mutually_permeable,
            "blocked_by": list(pc.blocked_by),
            "established": list(pc.established),
        },
        "budget": {
            "step_allowance": tm.budget.step_allowance,
            "consuming_actions": list(tm.budget.consuming_actions),
            "exhaustion": tm.budget.exhaustion,
        },
        "failure_semantics": {
            "attempt_cap": tm.failure_semantics.attempt_cap,
            "layout": tm.failure_semantics.layout,
            "flow": tm.failure_semantics.flow,
            "sink_satisfaction": tm.failure_semantics.sink_satisfaction,
            "selection": tm.failure_semantics.selection,
        },
        "responses": _responses_to_json(tm.responses),
        "observation_channel": tm.observation_channel,
        "epoch": tm.epoch,
    }


def to_neutral_json(instance: FlowHypothesis) -> dict[str, Any]:
    """The model-facing serialized form: neutral structural tags and values only —
    no ownership tags, no oracle/mutant labels, no game ids."""
    return {
        "objective": _objective_to_json(instance.objective),
        "transition_model": _transition_to_json(instance.transition_model),
        "phases": [_phase_to_json(p) for p in instance.phases],
    }


def _cell(raw: Any) -> Cell:
    return (int(raw[0]), int(raw[1]))


def _objective_from_json(data: dict[str, Any], path: str) -> FlowObjective:
    kind = _require(data, "kind", path)
    roles = tuple(str(r) for r in _require(data, "sink_roles", f"{path}.sink_roles"))
    if kind == AnySinkCovered.KIND:
        return AnySinkCovered(sink_roles=roles)
    if kind == CoverAllSinks.KIND:
        return CoverAllSinks(
            sink_roles=roles,
            completion=_require(data, "completion", f"{path}.completion"),
            hazard_policy=_require(data, "hazard_policy", f"{path}.hazard_policy"),
            completion_count=data.get("completion_count"),
        )
    raise ValueError(f"{path}.kind: unknown flow objective kind {kind!r}")


def _responses_from_json(data: dict[str, Any], path: str) -> ResponseTable:
    raw = _require(data, "piece_by_class", f"{path}.piece_by_class")
    sink = _require(data, "sink", f"{path}.sink")
    return ResponseTable(
        piece_by_class=tuple(
            (
                str(_require(e, "piece_class", f"{path}.piece_by_class[{i}].piece_class")),
                PieceResponse(
                    spawn=_require(e, "spawn", f"{path}.piece_by_class[{i}].spawn"),
                    direction=_require(e, "direction", f"{path}.piece_by_class[{i}].direction"),
                    propagation=_require(
                        e, "propagation", f"{path}.piece_by_class[{i}].propagation"
                    ),
                ),
            )
            for i, e in enumerate(raw)
        ),
        sink=SinkResponse(
            predicate=_require(sink, "predicate", f"{path}.sink.predicate"),
            miss=_require(sink, "miss", f"{path}.sink.miss"),
        ),
        hazard=_require(data, "hazard", f"{path}.hazard"),
        own_flow=data.get("own_flow", UNKNOWN),
        boundary=data.get("boundary", UNKNOWN),
    )


def _transition_from_json(data: dict[str, Any], path: str) -> FlowTransition:
    kind = _require(data, "kind", path)
    if kind == EmpiricalSpillMatrix.KIND:
        return EmpiricalSpillMatrix(asserted_entries=data.get("asserted_entries"))
    if kind != PlaceThenPropagate.KIND:
        raise ValueError(f"{path}.kind: unknown flow transition_model kind {kind!r}")

    pc = _require(data, "placement_constraints", f"{path}.placement_constraints")
    bd = _require(data, "budget", f"{path}.budget")
    fs = _require(data, "failure_semantics", f"{path}.failure_semantics")
    return PlaceThenPropagate(
        control_mode=_require(data, "control_mode", f"{path}.control_mode"),
        piece_deltas=tuple(
            (int(a), int(dr), int(dc))
            for a, dr, dc in _require(data, "piece_deltas", f"{path}.piece_deltas")
        ),
        piece_footprints=tuple(
            (str(e["piece"]), tuple(_cell(c) for c in e["cells"]))
            for e in _require(data, "piece_footprints", f"{path}.piece_footprints")
        ),
        emitters=tuple(_cell(c) for c in _require(data, "emitters", f"{path}.emitters")),
        initial_direction=_cell(_require(data, "initial_direction", f"{path}.initial_direction")),
        commit_action=int(_require(data, "commit_action", f"{path}.commit_action")),
        placement_constraints=PlacementConstraints(
            sink_keepout_margin=int(_require(pc, "sink_keepout_margin", f"{path}.pc.margin")),
            row_bound=pc.get("row_bound"),
            pieces_mutually_permeable=bool(
                _require(pc, "pieces_mutually_permeable", f"{path}.pc.permeable")
            ),
            blocked_by=tuple(str(b) for b in _require(pc, "blocked_by", f"{path}.pc.blocked_by")),
            established=tuple(str(b) for b in _require(pc, "established", f"{path}.pc.established")),
        ),
        budget=Budget(
            step_allowance=int(_require(bd, "step_allowance", f"{path}.budget.step_allowance")),
            consuming_actions=tuple(
                str(a) for a in _require(bd, "consuming_actions", f"{path}.budget.consuming")
            ),
            exhaustion=_require(bd, "exhaustion", f"{path}.budget.exhaustion"),
        ),
        failure_semantics=FailureSemantics(
            attempt_cap=int(_require(fs, "attempt_cap", f"{path}.fs.attempt_cap")),
            layout=_require(fs, "layout", f"{path}.fs.layout"),
            flow=_require(fs, "flow", f"{path}.fs.flow"),
            sink_satisfaction=_require(fs, "sink_satisfaction", f"{path}.fs.sink_satisfaction"),
            selection=_require(fs, "selection", f"{path}.fs.selection"),
        ),
        responses=_responses_from_json(
            _require(data, "responses", f"{path}.responses"), f"{path}.responses"
        ),
        observation_channel=data.get("observation_channel", "animation_layers"),
        epoch=data.get("epoch", "settle_to_fixpoint_then_verdict"),
    )


def from_json(data: dict[str, Any]) -> FlowHypothesis:
    """Reconstruct a ``FlowHypothesis`` from ``to_neutral_json`` output, round-trip
    exact. Validation errors name the offending field path — the model's later
    error-feedback channel."""
    return FlowHypothesis(
        objective=_objective_from_json(_require(data, "objective", "objective"), "objective"),
        transition_model=_transition_from_json(
            _require(data, "transition_model", "transition_model"), "transition_model"
        ),
        phases=tuple(
            _phase_from_json(p, f"phases[{i}]")
            for i, p in enumerate(_require(data, "phases", "phases"))
        ),
    )


# ── canonical ORACLE instance (sp80 idx0, certified against the live engine) ─


def sp80_oracle_instance() -> FlowHypothesis:
    """The decoded sp80 idx0 hypothesis. Its response table is the one whose
    reference propagator reproduces the engine's outcome on every reachable
    placement and its cell-exact trajectory on both probe placements. Structural
    values (footprints, emitters, deltas) are harness_measured live; the fixture
    records the measured criterion-level values so the schema shape is faithful."""
    straight = PieceResponse(
        spawn="empty_flanks_only", direction="preserved", propagation="cellwise_iterative"
    )
    return FlowHypothesis(
        objective=CoverAllSinks(
            sink_roles=("sink_0", "sink_1"), completion="all", hazard_policy="fatal_on_contact"
        ),
        transition_model=PlaceThenPropagate(
            control_mode="select_then_translate",
            piece_deltas=((1, -1, 0), (2, 1, 0), (3, 0, -1), (4, 0, 1)),
            piece_footprints=(
                ("piece_0", ((4, 3), (4, 4), (4, 5), (4, 6), (4, 7))),
            ),
            emitters=((0, 9),),
            initial_direction=(1, 0),
            commit_action=5,
            placement_constraints=PlacementConstraints(
                sink_keepout_margin=1,
                row_bound=3,
                pieces_mutually_permeable=True,
                blocked_by=("board_bounds", "sink_halo", "row_bound"),
                established=("row_bound",),
            ),
            budget=Budget(
                step_allowance=30,
                consuming_actions=("select", "translate", "commit"),
                exhaustion="terminal_loss",
            ),
            failure_semantics=FailureSemantics(
                attempt_cap=4,
                layout="persists",
                flow="resets",
                sink_satisfaction="resets",
                selection="resets_to_default",
            ),
            responses=ResponseTable(
                piece_by_class=(("straight", straight),),
                sink=SinkResponse(predicate="same_sink_flanks", miss="spread_like_piece"),
                hazard="terminate_fatal",
            ),
        ),
        phases=(Phase(guard=(LevelAdvanced(),)),),
    )


# ── frozen mutant fixtures + expected-verdict table ─────────────────────────


@dataclass(frozen=True)
class FlowMutantCase:
    """A wrong flow hypothesis plus the verdict the verifier must return, with a
    one-line reason. Shipped as DATA. Verdicts marked CONTRADICTED are certified
    against observed transitions; UNKNOWN entries are certified ABSENT — the
    exhaustive placement sweep proves the criterion level offers no discriminating
    opportunity, so no probe can rescue them."""

    name: str
    instance: FlowHypothesis
    expected_verdict: Verdict
    axis: str  # transition | objective
    reason: str


def _with_responses(**changes: Any) -> FlowHypothesis:
    base = sp80_oracle_instance()
    tm = base.transition_model
    table = tm.responses
    piece_changes = {k: v for k, v in changes.items() if k in {"spawn", "direction", "propagation"}}
    table_changes = {k: v for k, v in changes.items() if k not in piece_changes}
    name, piece = table.piece_by_class[0]
    if piece_changes:
        piece = PieceResponse(
            spawn=piece_changes.get("spawn", piece.spawn),
            direction=piece_changes.get("direction", piece.direction),
            propagation=piece_changes.get("propagation", piece.propagation),
        )
    sink = table.sink
    if "sink_predicate" in table_changes or "sink_miss" in table_changes:
        sink = SinkResponse(
            predicate=table_changes.get("sink_predicate", sink.predicate),
            miss=table_changes.get("sink_miss", sink.miss),
        )
    new_table = ResponseTable(
        piece_by_class=((name, piece),),
        sink=sink,
        hazard=table_changes.get("hazard", table.hazard),
        own_flow=table_changes.get("own_flow", table.own_flow),
        boundary=table_changes.get("boundary", table.boundary),
    )
    from dataclasses import replace as _replace

    return FlowHypothesis(
        objective=base.objective,
        transition_model=_replace(tm, responses=new_table),
        phases=base.phases,
    )


def _objective_mutant(objective: FlowObjective) -> FlowHypothesis:
    base = sp80_oracle_instance()
    return FlowHypothesis(
        objective=objective, transition_model=base.transition_model, phases=base.phases
    )


MUTANTS_FLOW: tuple[FlowMutantCase, ...] = (
    FlowMutantCase(
        name="piece_absorbs",
        instance=_with_responses(spawn="none"),
        expected_verdict=Verdict.CONTRADICTED,
        axis="transition",
        reason=(
            "the observed frontier emits a flanking pair at the piece row; absorption predicts an "
            "empty frontier there"
        ),
    ),
    FlowMutantCase(
        name="piece_turns_outward",
        instance=_with_responses(direction="outward_turned"),
        expected_verdict=Verdict.CONTRADICTED,
        axis="transition",
        reason=(
            "an outward turn predicts the branches travelling sideways; both observed branches "
            "resume the original downward direction after clearing the piece"
        ),
    ),
    FlowMutantCase(
        name="piece_edge_teleport",
        instance=_with_responses(propagation="edge_teleport"),
        expected_verdict=Verdict.CONTRADICTED,
        axis="transition",
        reason=(
            "teleporting to the piece's outer edges predicts the same endpoints but skips the "
            "intermediate cells; the observed frontier walks one cell per tick"
        ),
    ),
    FlowMutantCase(
        name="sink_satisfied_on_contact",
        instance=_with_responses(sink_predicate="contact"),
        expected_verdict=Verdict.CONTRADICTED,
        axis="transition",
        reason=(
            "the flow was observed directly above a sink cell without satisfying it, then spread "
            "sideways; satisfaction followed only from the mouth column"
        ),
    ),
    FlowMutantCase(
        name="sink_stops_flow",
        instance=_with_responses(sink_miss="stop"),
        expected_verdict=Verdict.CONTRADICTED,
        axis="transition",
        reason=(
            "stopping at a sink miss predicts no onward flow; the observed miss produced two "
            "flanking cells that continued and later satisfied the sink"
        ),
    ),
    FlowMutantCase(
        name="hazard_ignored",
        instance=_objective_mutant(
            CoverAllSinks(
                sink_roles=("sink_0", "sink_1"), completion="all", hazard_policy="neutral"
            )
        ),
        expected_verdict=Verdict.CONTRADICTED,
        axis="objective",
        reason=(
            "one placement fills every sink and still fails while another fills the same sinks and "
            "advances; the pair differs only in reaching the row above the bottom"
        ),
    ),
    FlowMutantCase(
        name="any_sink_suffices",
        instance=_objective_mutant(AnySinkCovered(sink_roles=("sink_0", "sink_1"))),
        expected_verdict=Verdict.UNKNOWN,
        axis="objective",
        reason=(
            "no reachable placement fills a strict subset of the sinks, so every observation is "
            "consistent with both all and any; certified absent by exhaustive sweep, not assumed"
        ),
    ),
    FlowMutantCase(
        name="flow_overwrites_own_trail",
        instance=_with_responses(own_flow="overwrite"),
        expected_verdict=Verdict.UNKNOWN,
        axis="transition",
        reason=(
            "measured inert at the criterion level: no observation distinguishes waiting behind the "
            "front from overwriting it"
        ),
    ),
    FlowMutantCase(
        name="boundary_reflects",
        instance=_with_responses(boundary="reflect"),
        expected_verdict=Verdict.UNKNOWN,
        axis="transition",
        reason="measured inert at the criterion level: the flow never exits sideways",
    ),
)


__all__ = [
    "UNKNOWN",
    "CoverAllSinks",
    "AnySinkCovered",
    "FlowObjective",
    "PieceResponse",
    "SinkResponse",
    "ResponseTable",
    "PlacementConstraints",
    "Budget",
    "FailureSemantics",
    "PlaceThenPropagate",
    "EmpiricalSpillMatrix",
    "FlowTransition",
    "FlowHypothesis",
    "FLOW_OWNERSHIP",
    "FLOW_MODEL_SELECTED_SEMANTICS",
    "OUTCOME_GATED_SLOTS",
    "VERIFIER_GATED_SLOTS",
    "NON_GATING_SLOTS",
    "EQUIVALENCE_CLASSES",
    "to_neutral_json",
    "from_json",
    "sp80_oracle_instance",
    "FlowMutantCase",
    "MUTANTS_FLOW",
]
