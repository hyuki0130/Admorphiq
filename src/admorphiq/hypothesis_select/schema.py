"""R95b STEP (ii): the typed cell-state hypothesis schema + canonical instances.

This is the one-family (cell-state) envelope the R95a discriminative test
validated — ft09 (glyph-relational) + sc25's pattern phase (pattern-reference).
It is the schema the R95b compiler/verifier/model-selection substages build on;
this module ships ONLY the types, the two canonical ORACLE instances, the mutant
fixtures + expected-verdict table, and neutral serialization. No observation
service, no verifier, no compiler here (frozen R95b BUILD PLAN v1, step ii).

Design authority: ``docs/design_hypothesis_dsl_r95.md`` — "R95b BUILD PLAN v1"
and the FROZEN "R95b EVALUATION CONTRACT". Three principles drive the shapes:

* **Tagged objective union** — ``GlyphRelational | PatternReference``. The
  constraint SOURCE and the target RULE are coupled inside one arm, so an
  invalid cross-product (glyph source + XOR-preview target) is unrepresentable
  by type shape: XOR/preview semantics live only on ``PatternReference``, ink/
  coverage semantics only on ``GlyphRelational``.
* **Separately-tagged transition model** — ``OrderedCycle | BinaryFlip |
  EmpiricalEffectMatrix``. ``OrderedCycle`` carries the ORDERED colour
  transition function (not just a length); it is harness-measured at runtime.
* **Field ownership** — every field is tagged ``harness_measured`` /
  ``model_selected`` / ``compiler_derived`` (``OWNERSHIP`` table). Per the design
  the model selects exactly four SEMANTIC slots — coverage quantifier, ink/
  operator mapping, preview interpretation, and phase guards; the harness
  materializes measured structure (cell enumerations, incidence, the transition
  function, snapshot timing). ``MODEL_SELECTED_SEMANTICS`` pins that set.
"""

from __future__ import annotations

from dataclasses import MISSING, dataclass, field, fields
from enum import Enum
from typing import Any, Optional, Union


class Ownership(str, Enum):
    """Who supplies a field's value in the R95b pipeline."""

    HARNESS_MEASURED = "harness_measured"
    MODEL_SELECTED = "model_selected"
    COMPILER_DERIVED = "compiler_derived"


class Verdict(str, Enum):
    """The verifier's per-hypothesis verdicts (the future verifier's outputs)."""

    PASS = "PASS"
    CONTRADICTED = "CONTRADICTED"
    UNKNOWN = "UNKNOWN"


def _own(ownership: Ownership) -> dict[str, Any]:
    return {"ownership": ownership}


# ── objective union (source + target rule coupled per arm) ──────────────────

_COVERAGE_QUANTIFIERS = frozenset({"all_covering", "nearest_only"})
_INK_OPERATORS = frozenset({"equal", "differ", "none"})
_PREVIEW_INTERPRETATIONS = frozenset(
    {"xor_exact", "xor_near", "absolute_exact", "absolute_near"}
)


@dataclass(frozen=True)
class GlyphRelational:
    """A relational constraint objective read off marker glyphs: every covered
    cell must satisfy an equal/differ/no-constraint relation (per the ink→operator
    map) to each covering glyph's marker colour. The coverage quantifier decides
    whether ALL covering glyphs bind a cell or only its nearest. This arm has NO
    preview/XOR fields — those cross-products are unrepresentable by construction."""

    KIND = "glyph_relational"

    coverage_quantifier: str = field(metadata=_own(Ownership.MODEL_SELECTED))
    ink_operator_map: tuple[tuple[int, str], ...] = field(metadata=_own(Ownership.MODEL_SELECTED))
    no_cell_ink: int = field(metadata=_own(Ownership.HARNESS_MEASURED))

    def __post_init__(self) -> None:
        if self.coverage_quantifier not in _COVERAGE_QUANTIFIERS:
            raise ValueError(
                f"GlyphRelational.coverage_quantifier: {self.coverage_quantifier!r} "
                f"not in {sorted(_COVERAGE_QUANTIFIERS)}"
            )
        for ink, op in self.ink_operator_map:
            if not isinstance(ink, int):
                raise ValueError(f"GlyphRelational.ink_operator_map: ink {ink!r} is not an int")
            if op not in _INK_OPERATORS:
                raise ValueError(
                    f"GlyphRelational.ink_operator_map: operator {op!r} not in {sorted(_INK_OPERATORS)}"
                )


@dataclass(frozen=True)
class PatternReference:
    """A pattern-match objective against a displayed reference (preview): the
    editable grid is complete when it equals the reference under the chosen
    preview interpretation. ``preview_interpretation`` folds the two orthogonal
    model choices into one closed slot — base derivation (XOR the parity base vs
    ABSOLUTE colours) x match tolerance (EXACT vs NEAR). Base-snapshot timing and
    two-read stability are grounding facts the harness measures. This arm has NO
    glyph/ink fields."""

    KIND = "pattern_reference"

    preview_interpretation: str = field(metadata=_own(Ownership.MODEL_SELECTED))
    base_snapshot_timing: str = field(metadata=_own(Ownership.HARNESS_MEASURED))
    two_read_stability: bool = field(metadata=_own(Ownership.HARNESS_MEASURED))

    def __post_init__(self) -> None:
        if self.preview_interpretation not in _PREVIEW_INTERPRETATIONS:
            raise ValueError(
                f"PatternReference.preview_interpretation: {self.preview_interpretation!r} "
                f"not in {sorted(_PREVIEW_INTERPRETATIONS)}"
            )


Objective = Union[GlyphRelational, PatternReference]


# ── transition model union (harness-measured dynamics) ──────────────────────


@dataclass(frozen=True)
class OrderedCycle:
    """A click advances only the clicked cell one step along an ORDERED colour
    cycle (``order[i] -> order[i+1] -> ... -> order[0]``). The order is the
    measured transition function, not merely a length."""

    KIND = "ordered_cycle"

    order: tuple[int, ...] = field(metadata=_own(Ownership.HARNESS_MEASURED))

    def __post_init__(self) -> None:
        if len(self.order) < 2:
            raise ValueError(f"OrderedCycle.order: needs >= 2 colours, got {self.order!r}")
        if any(not isinstance(c, int) for c in self.order):
            raise ValueError(f"OrderedCycle.order: all entries must be ints, got {self.order!r}")


@dataclass(frozen=True)
class BinaryFlip:
    """A click flips only the clicked cell between its two colours."""

    KIND = "binary_flip"


@dataclass(frozen=True)
class EmpiricalEffectMatrix:
    """A click flips a cell SET measured empirically from the click location.
    ``asserted_footprint`` (None = fully measured at runtime) lets a fixture
    assert a claimed multi-cell footprint (e.g. a neighbourhood stencil) that the
    verifier checks against observed single-cell transitions."""

    KIND = "empirical_effect_matrix"

    asserted_footprint: Optional[int] = field(default=None, metadata=_own(Ownership.HARNESS_MEASURED))

    def __post_init__(self) -> None:
        if self.asserted_footprint is not None and self.asserted_footprint < 1:
            raise ValueError(
                f"EmpiricalEffectMatrix.asserted_footprint: must be >= 1 or None, "
                f"got {self.asserted_footprint!r}"
            )


TransitionModel = Union[OrderedCycle, BinaryFlip, EmpiricalEffectMatrix]


# ── typed phase-guard vocabulary (a shallow conjunction of clauses) ─────────


@dataclass(frozen=True)
class StableForReads:
    KIND = "stable_for_reads"
    reads: int

    def __post_init__(self) -> None:
        if self.reads < 1:
            raise ValueError(f"StableForReads.reads: must be >= 1, got {self.reads!r}")


@dataclass(frozen=True)
class RolePresent:
    KIND = "role_present"
    role: str


@dataclass(frozen=True)
class RoleAbsent:
    KIND = "role_absent"
    role: str


@dataclass(frozen=True)
class RoleCountDelta:
    KIND = "role_count_delta"
    role: str
    delta: int


@dataclass(frozen=True)
class RoleSignatureChanged:
    KIND = "role_signature_changed"
    role: str


@dataclass(frozen=True)
class RolesStateEqual:
    KIND = "roles_state_equal"
    lhs: str
    rhs: str
    mask: Optional[str] = None


@dataclass(frozen=True)
class SelectionAttached:
    KIND = "selection_attached"


@dataclass(frozen=True)
class AffordanceMarkersPresent:
    KIND = "affordance_markers_present"


@dataclass(frozen=True)
class LayoutReplaced:
    KIND = "layout_replaced"


@dataclass(frozen=True)
class LevelAdvanced:
    KIND = "level_advanced"


@dataclass(frozen=True)
class UnknownGuard:
    KIND = "unknown_guard"


GuardClause = Union[
    StableForReads,
    RolePresent,
    RoleAbsent,
    RoleCountDelta,
    RoleSignatureChanged,
    RolesStateEqual,
    SelectionAttached,
    AffordanceMarkersPresent,
    LayoutReplaced,
    LevelAdvanced,
    UnknownGuard,
]

_GUARD_CLASSES: tuple[type, ...] = (
    StableForReads,
    RolePresent,
    RoleAbsent,
    RoleCountDelta,
    RoleSignatureChanged,
    RolesStateEqual,
    SelectionAttached,
    AffordanceMarkersPresent,
    LayoutReplaced,
    LevelAdvanced,
    UnknownGuard,
)
_GUARD_BY_KIND = {cls.KIND: cls for cls in _GUARD_CLASSES}


@dataclass(frozen=True)
class Phase:
    """An ordered phase: an entry-guard conjunction (a shallow AND of typed
    clauses) and an optional phase objective (``None`` = the envelope's primary
    objective; navigation-only handover phases carry ``None`` since navigation is
    out of the cell-state family scope)."""

    guard: tuple[GuardClause, ...] = field(metadata=_own(Ownership.MODEL_SELECTED))
    objective: Optional[Objective] = field(default=None, metadata=_own(Ownership.HARNESS_MEASURED))


@dataclass(frozen=True)
class CellStateHypothesis:
    """The cell-state family envelope: a primary objective (tagged union arm),
    a separately-tagged transition model, and an ordered phase list. The union
    ARM is a model structural choice (variant-first selection); the four semantic
    LEAF slots inside are the ``model_selected`` fields (see ``OWNERSHIP``)."""

    objective: Objective = field(metadata=_own(Ownership.HARNESS_MEASURED))
    transition_model: TransitionModel = field(metadata=_own(Ownership.HARNESS_MEASURED))
    phases: tuple[Phase, ...] = field(default=(), metadata=_own(Ownership.HARNESS_MEASURED))


# ── ownership table (pinned by tests) ───────────────────────────────────────

_OWNED_CLASSES: tuple[type, ...] = (
    CellStateHypothesis,
    GlyphRelational,
    PatternReference,
    OrderedCycle,
    BinaryFlip,
    EmpiricalEffectMatrix,
    Phase,
)

OWNERSHIP: dict[str, Ownership] = {
    f"{cls.__name__}.{f.name}": f.metadata["ownership"]
    for cls in _OWNED_CLASSES
    for f in fields(cls)
    if "ownership" in f.metadata
}

# The four SEMANTIC slots the model fills, per the frozen design list. The
# union-arm choice and phase structure are model STRUCTURAL choices; these are
# the model-owned semantic leaves the verifier and compiler consume.
MODEL_SELECTED_SEMANTICS: frozenset[str] = frozenset(
    {
        "GlyphRelational.coverage_quantifier",
        "GlyphRelational.ink_operator_map",
        "PatternReference.preview_interpretation",
        "Phase.guard",
    }
)


# ── canonical ORACLE instances ──────────────────────────────────────────────


def ft09_oracle_instance() -> CellStateHypothesis:
    """The ft09 oracle: all-covering glyph-relational constraints (ink 0=equal /
    2=differ / 3=no-cell, the adapter's decoded alphabet) with a single clicked
    cell advancing one step through the board's measured colour cycle. The cycle
    is harness_measured at runtime; the fixture uses the adapter's decoded
    3-value cycle (9, 8, 12) (``adapters25/ft09.py``). Single implicit phase."""
    return CellStateHypothesis(
        objective=GlyphRelational(
            coverage_quantifier="all_covering",
            ink_operator_map=((0, "equal"), (2, "differ"), (3, "none")),
            no_cell_ink=3,
        ),
        transition_model=OrderedCycle(order=(9, 8, 12)),
        phases=(Phase(guard=(), objective=None),),
    )


def sc25_oracle_instance() -> CellStateHypothesis:
    """The sc25 oracle (pattern phase): the grid is complete when it equals the
    preview under the base-parity XOR interpretation, exact match; each click
    flips one cell. The base snapshot is taken on the settled frame after the
    first action, locked after two equal reads. Phase 1 is the cast handover,
    entered when the grid is stable for two reads AND equals the preview (typed
    guard conjunction); its objective is None (navigation is out of scope)."""
    return CellStateHypothesis(
        objective=PatternReference(
            preview_interpretation="xor_exact",
            base_snapshot_timing="after_first_settled_action",
            two_read_stability=True,
        ),
        transition_model=BinaryFlip(),
        phases=(
            Phase(guard=(), objective=None),
            Phase(
                guard=(StableForReads(2), RolesStateEqual("toggle_grid", "preview")),
                objective=None,
            ),
        ),
    )


# ── mutant fixtures + expected-verdict table (the verifier's acceptance data) ─


@dataclass(frozen=True)
class MutantCase:
    """A wrong hypothesis + the verdict the future verifier must return for it,
    with a one-line reason. Shipped as DATA (``MUTANTS``), the verifier's
    acceptance test."""

    name: str
    instance: CellStateHypothesis
    expected_verdict: Verdict
    reason: str


def _ft09_stencil_mutant() -> CellStateHypothesis:
    base = ft09_oracle_instance()
    return CellStateHypothesis(
        objective=base.objective,
        transition_model=EmpiricalEffectMatrix(asserted_footprint=5),
        phases=base.phases,
    )


def _ft09_nearest_only_mutant() -> CellStateHypothesis:
    base = ft09_oracle_instance()
    return CellStateHypothesis(
        objective=GlyphRelational(
            coverage_quantifier="nearest_only",
            ink_operator_map=((0, "equal"), (2, "differ"), (3, "none")),
            no_cell_ink=3,
        ),
        transition_model=base.transition_model,
        phases=base.phases,
    )


def _ft09_all_ink_equal_mutant() -> CellStateHypothesis:
    base = ft09_oracle_instance()
    return CellStateHypothesis(
        objective=GlyphRelational(
            coverage_quantifier="all_covering",
            ink_operator_map=((0, "equal"), (2, "equal"), (3, "none")),
            no_cell_ink=3,
        ),
        transition_model=base.transition_model,
        phases=base.phases,
    )


def _sc25_neighbour_flip_mutant() -> CellStateHypothesis:
    base = sc25_oracle_instance()
    return CellStateHypothesis(
        objective=base.objective,
        transition_model=EmpiricalEffectMatrix(asserted_footprint=2),
        phases=base.phases,
    )


def _sc25_near_match_mutant() -> CellStateHypothesis:
    base = sc25_oracle_instance()
    return CellStateHypothesis(
        objective=PatternReference(
            preview_interpretation="xor_near",
            base_snapshot_timing="after_first_settled_action",
            two_read_stability=True,
        ),
        transition_model=base.transition_model,
        phases=base.phases,
    )


def _sc25_absolute_preview_mutant() -> CellStateHypothesis:
    base = sc25_oracle_instance()
    return CellStateHypothesis(
        objective=PatternReference(
            preview_interpretation="absolute_exact",
            base_snapshot_timing="after_first_settled_action",
            two_read_stability=True,
        ),
        transition_model=base.transition_model,
        phases=base.phases,
    )


MUTANTS: tuple[MutantCase, ...] = (
    MutantCase(
        name="ft09_stencil_transition",
        instance=_ft09_stencil_mutant(),
        expected_verdict=Verdict.CONTRADICTED,
        reason="click claims a 5-cell plus footprint; observed transitions change exactly the clicked cell",
    ),
    MutantCase(
        name="ft09_nearest_only_quantifier",
        instance=_ft09_nearest_only_mutant(),
        expected_verdict=Verdict.UNKNOWN,
        reason="nearest-only vs all-covering never diverges on the recorded frames (0/1436) — data-indistinguishable",
    ),
    MutantCase(
        name="ft09_all_ink_equal",
        instance=_ft09_all_ink_equal_mutant(),
        expected_verdict=Verdict.CONTRADICTED,
        reason="treats differ-ink (2) as equal; the win state has covered cells that must differ from their marker",
    ),
    MutantCase(
        name="sc25_neighbour_flip_transition",
        instance=_sc25_neighbour_flip_mutant(),
        expected_verdict=Verdict.CONTRADICTED,
        reason="click claims cell+neighbour flip; observed flips exactly the clicked lattice cell",
    ),
    MutantCase(
        name="sc25_near_match_objective",
        instance=_sc25_near_match_mutant(),
        expected_verdict=Verdict.UNKNOWN,
        reason="no partial-match (7-8 of 9) frame exists in the trace to separate near-threshold from exact",
    ),
    MutantCase(
        name="sc25_absolute_preview_interpretation",
        instance=_sc25_absolute_preview_mutant(),
        expected_verdict=Verdict.CONTRADICTED,
        reason="reads the preview as absolute colours; the grid never renders its ON cells in the preview mark colour",
    ),
)


# ── neutral serialization (model-facing; no provenance labels) ──────────────


def _objective_to_json(obj: Objective) -> dict[str, Any]:
    if isinstance(obj, GlyphRelational):
        return {
            "kind": GlyphRelational.KIND,
            "coverage_quantifier": obj.coverage_quantifier,
            "ink_operator_map": [[ink, op] for ink, op in obj.ink_operator_map],
            "no_cell_ink": obj.no_cell_ink,
        }
    if isinstance(obj, PatternReference):
        return {
            "kind": PatternReference.KIND,
            "preview_interpretation": obj.preview_interpretation,
            "base_snapshot_timing": obj.base_snapshot_timing,
            "two_read_stability": obj.two_read_stability,
        }
    raise TypeError(f"objective: unserializable type {type(obj).__name__}")


def _transition_to_json(tm: TransitionModel) -> dict[str, Any]:
    if isinstance(tm, OrderedCycle):
        return {"kind": OrderedCycle.KIND, "order": list(tm.order)}
    if isinstance(tm, BinaryFlip):
        return {"kind": BinaryFlip.KIND}
    if isinstance(tm, EmpiricalEffectMatrix):
        return {"kind": EmpiricalEffectMatrix.KIND, "asserted_footprint": tm.asserted_footprint}
    raise TypeError(f"transition_model: unserializable type {type(tm).__name__}")


def _guard_to_json(clause: GuardClause) -> dict[str, Any]:
    data: dict[str, Any] = {"kind": clause.KIND}
    for f in fields(clause):
        data[f.name] = getattr(clause, f.name)
    return data


def _phase_to_json(phase: Phase) -> dict[str, Any]:
    return {
        "guard": [_guard_to_json(c) for c in phase.guard],
        "objective": _objective_to_json(phase.objective) if phase.objective is not None else None,
    }


def to_neutral_json(instance: CellStateHypothesis) -> dict[str, Any]:
    """The model-facing serialized form: neutral structural tags + values only,
    NO provenance (no ownership tags, no oracle/mutant labels, no game ids)."""
    return {
        "objective": _objective_to_json(instance.objective),
        "transition_model": _transition_to_json(instance.transition_model),
        "phases": [_phase_to_json(p) for p in instance.phases],
    }


def _require(data: dict[str, Any], key: str, path: str) -> Any:
    if key not in data:
        raise ValueError(f"{path}: missing required field {key!r}")
    return data[key]


def _objective_from_json(data: dict[str, Any], path: str) -> Objective:
    kind = _require(data, "kind", path)
    if kind == GlyphRelational.KIND:
        raw = _require(data, "ink_operator_map", f"{path}.ink_operator_map")
        return GlyphRelational(
            coverage_quantifier=_require(data, "coverage_quantifier", f"{path}.coverage_quantifier"),
            ink_operator_map=tuple((int(ink), op) for ink, op in raw),
            no_cell_ink=_require(data, "no_cell_ink", f"{path}.no_cell_ink"),
        )
    if kind == PatternReference.KIND:
        return PatternReference(
            preview_interpretation=_require(
                data, "preview_interpretation", f"{path}.preview_interpretation"
            ),
            base_snapshot_timing=_require(data, "base_snapshot_timing", f"{path}.base_snapshot_timing"),
            two_read_stability=_require(data, "two_read_stability", f"{path}.two_read_stability"),
        )
    raise ValueError(f"{path}.kind: unknown objective kind {kind!r}")


def _transition_from_json(data: dict[str, Any], path: str) -> TransitionModel:
    kind = _require(data, "kind", path)
    if kind == OrderedCycle.KIND:
        return OrderedCycle(order=tuple(int(c) for c in _require(data, "order", f"{path}.order")))
    if kind == BinaryFlip.KIND:
        return BinaryFlip()
    if kind == EmpiricalEffectMatrix.KIND:
        return EmpiricalEffectMatrix(asserted_footprint=data.get("asserted_footprint"))
    raise ValueError(f"{path}.kind: unknown transition_model kind {kind!r}")


def _guard_from_json(data: dict[str, Any], path: str) -> GuardClause:
    kind = _require(data, "kind", path)
    cls = _GUARD_BY_KIND.get(kind)
    if cls is None:
        raise ValueError(f"{path}.kind: unknown guard kind {kind!r}")
    kwargs = {f.name: data[f.name] for f in fields(cls) if f.name in data}
    missing = [f.name for f in fields(cls) if f.default is MISSING and f.name not in kwargs]
    if missing:
        raise ValueError(f"{path}: missing required guard field(s) {missing}")
    return cls(**kwargs)


def _phase_from_json(data: dict[str, Any], path: str) -> Phase:
    guards = _require(data, "guard", f"{path}.guard")
    objective_data = data.get("objective")
    return Phase(
        guard=tuple(_guard_from_json(g, f"{path}.guard[{i}]") for i, g in enumerate(guards)),
        objective=_objective_from_json(objective_data, f"{path}.objective")
        if objective_data is not None
        else None,
    )


def from_json(data: dict[str, Any]) -> CellStateHypothesis:
    """Reconstruct a ``CellStateHypothesis`` from ``to_neutral_json`` output,
    round-trip exact. Validation errors name the offending field path (the
    model's later error-feedback channel)."""
    return CellStateHypothesis(
        objective=_objective_from_json(_require(data, "objective", "objective"), "objective"),
        transition_model=_transition_from_json(
            _require(data, "transition_model", "transition_model"), "transition_model"
        ),
        phases=tuple(
            _phase_from_json(p, f"phases[{i}]")
            for i, p in enumerate(_require(data, "phases", "phases"))
        ),
    )


__all__ = [
    "Ownership",
    "Verdict",
    "GlyphRelational",
    "PatternReference",
    "Objective",
    "OrderedCycle",
    "BinaryFlip",
    "EmpiricalEffectMatrix",
    "TransitionModel",
    "StableForReads",
    "RolePresent",
    "RoleAbsent",
    "RoleCountDelta",
    "RoleSignatureChanged",
    "RolesStateEqual",
    "SelectionAttached",
    "AffordanceMarkersPresent",
    "LayoutReplaced",
    "LevelAdvanced",
    "UnknownGuard",
    "GuardClause",
    "Phase",
    "CellStateHypothesis",
    "OWNERSHIP",
    "MODEL_SELECTED_SEMANTICS",
    "ft09_oracle_instance",
    "sc25_oracle_instance",
    "MutantCase",
    "MUTANTS",
    "to_neutral_json",
    "from_json",
]
