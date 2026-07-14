"""GoalLedger: the executable win-condition typology (R58 verdict §4).

Turns R57's win-condition typology mining
(``docs/r57_win_condition_typology_20260715.md``) into a set of cheap,
kernel-composed, PRE-CLEAR detectors — no level-up labels, no gold data,
no game identity, ever, at runtime. ``detect(observations)`` is a pure
function: it runs every detector that has enough input to fire, and returns
a **capped hypothesis set**, not an elected winner.

**R58 tuning round #3 (2026-07-15) — reconceptualization per Codex verdict
`docs/r58_codex_ledger_ranking_20260715.md`.** Two prior rounds (evidence-
strength scoring, then floor-anchoring) tried to make the six detectors'
``"strength"`` values comparable enough to sort into a single ranked list
and elect a TOP1 winner. Real-trace validation across three measurement
rounds (same 24-game battery) showed this framing was wrong at the root:
floor-anchoring is a mathematically correct normalization of each
detector's margin ABOVE ITS OWN FIRING GATE, but a ``0.45`` from
``arrival`` and a ``0.45`` from ``uniformity`` never estimated the same
probability, likelihood ratio, or information gain — their gates, evidence
modalities, and formulas differ, so sorting them into one scalar order
asserts more comparability than the formulas support. Codex's verdict,
adopted here:

- ``GoalLedger`` is a **capped hypothesis generator**, not a six-class
  classifier. ``"strength"`` is kept but is a detector-LOCAL MARGIN above
  that detector's own gate — never a cross-detector confidence score.
- Every candidate carries an **evidence stage** (``affordance`` <
  ``behavioral`` < ``predicate``, weakest to strongest) reflecting WHAT KIND
  of evidence built it — a static frame permitting the type, an observed
  transition behaving as the type predicts, or an actual reference/endpoint
  identified — not how numerically large its raw formula happened to run.
  Ranking is TIER FIRST; candidates within the same tier are genuine ties
  (``"strength"``/detector order only break ties for deterministic
  presentation, never to claim one is "more true").
- An **adjudication pass** computes pairwise evidence-DEPENDENCY relations
  between fired candidates via footprint set operations (``shared_evidence``,
  ``subsumed_evidence``, ``independent_evidence``) plus one structural,
  type-level relation (``temporal_composition``, R57's own documented T4 =
  arrival∘elimination composition) — never a hard mutual-exclusion table.
  R57 itself records several type PAIRS as compositional or co-occurring
  (T4 = T1+T2; T6 is itself "a fixed-cell pattern match"; at least one
  public game genuinely has both a pattern-building phase and an
  arrival/exit phase), so a learned or hand-written "only one of these can
  be true" table would encode the wrong semantics. Shared evidence is
  marked, never silently double-counted or silently deleted.
- Capping to ``MAX_CANDIDATES`` preserves the highest evidence tiers, BOTH
  sides of an explicit ambiguity (a ``shared_evidence``/``subsumed_evidence``
  pair), and candidates with mutually INDEPENDENT footprints, before
  falling back to margin/detector-order as a final size-control tie-break.
- ``unresolved_tests`` are now CONCRETE structural probes ("whether edits
  follow a translated fixed stencil or directly repaint one canvas slot"),
  not a bare list of competing type names — a weak offline LLM should be
  handed a specific test to run, not four scores to interpret itself.

Naming follows the verdict's OWN example vocabulary
(``goals/detectors/{elimination,uniformity,pattern_match,containment,
arrival}.yaml``) rather than inventing new type names, so a goal
candidate's ``"type"`` field is directly one of those five plus one R58
addition (``threshold``). Each detector's docstring cross-references which
R57 typology letter (T1-T8) it operationalizes — by LETTER only, never by
public-game name (``scripts/explanation_lint.py`` enforces that on this
file, same as every other file in the package; the full per-game
provenance for each type lives in R57's own doc, not here).

Coverage vs. R57's 8 types, and why:

  - ``arrival``       <- T1 Reach/Target-Coincidence.
  - ``uniformity``     <- T6 Toggle-Parity ("NOTE: firing does not prove
    GF(2) structure — it only proposes the HYPOTHESIS that the win
    condition is 'these repeated cells reach a uniform/target state';
    confirming GF(2) linearity is the ``toggle_linear`` MECHANIC playbook's
    job, not this ledger's" — verdict §4).
  - ``containment``    <- T3 Assignment/Matching.
  - ``pattern_match``  <- T5 Fill/Paint-to-Pattern. REBUILT this round (see
    :func:`_detect_pattern_match`) — the v1/v2 heterogeneous-bbox-container
    proxy did not implement R57's actual canvas/reference-relationship
    sketch and is replaced by an immediate-containment-hierarchy +
    addressable-lattice / congruent-panel-pair detector.
  - ``elimination``    <- T2 Elimination/Obstacle-Consumption. Needs a
    before/after frame PAIR — inherently transitional evidence, so its tier
    ranges ``behavioral``/``predicate`` only, never ``affordance``.
  - ``threshold``      <- T7 Threshold/Repeated-Action-Count, R58 ADDITION
    beyond the verdict's five named examples. Needs a repeated-action
    window — also inherently transitional, ``behavioral`` only.
  - T4 Delivery/Carry-and-Place — **UNSUPPORTED as an independent
    detector**, but its compositional relationship to ``arrival`` +
    ``elimination`` IS now represented structurally via
    ``temporal_composition`` in the adjudication pass (not correlated
    across ``detect()`` calls — this ledger is still stateless per call;
    the relation is declared once, type-level, from R57's own typology,
    not inferred from any per-game footprint overlap).
  - T8 Programmatic/Rewrite-Derivation — **UNSUPPORTED, explicitly, not a
    weak proxy.** R57's own coverage table is blunt: the one game that
    anchored this type's typology label has zero captured level-up events
    across the entire mining pass; its label rests entirely on a one-time
    source inspection, never validated against real frame data.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from admorphiq.kernels import (
    find_regions,
    frame_diff,
    group_by_axis,
    multiset_signature,
    region_relations,
)

MAX_CANDIDATES = 4
MAX_HANDLES_PER_CANDIDATE = 3
MAX_UNRESOLVED = 3

# Structural thresholds. Deliberately small integers, not tuned to any one
# game's exact geometry (that would smuggle a public-game constant back
# into a "generic" detector — the R56 toolbase-verdict failure mode this
# package exists to avoid).
_MIN_UNIFORM_GRID_COUNT = 6
_MAX_UNIFORM_SHAPE_COLORS = 3
_MIN_UNIFORM_SHAPE_CELLS = 2  # ">1 cell", named for use in gate_min derivations below
_MIN_CONTAINMENT_SIBLINGS = 2
_MIN_CONTAINMENT_ITEMS_PER_SIBLING = 2
_MIN_LATTICE_CHILDREN = 4  # a 2x2 addressable grid is the smallest genuine lattice
_MIN_PANEL_PAIR_CHILDREN = 2
_MIN_THRESHOLD_REPEATS = 3
_MIN_THRESHOLD_DIFFS = 2  # named for use in gate_min derivations below (was a bare literal)

# Floor-anchoring: FLOOR is where a "just barely cleared this detector's own
# firing gate" candidate lands after rescaling; uniform across all six
# detectors (a per-detector floor would just reintroduce the calibration
# problem this exists to fix). Per the R58 tuning-round-3 verdict, this
# value is now explicitly a detector-LOCAL MARGIN — see the module
# docstring — not a cross-detector confidence estimate, so its exact value
# matters far less than it did when candidates were sorted by it alone.
_STRENGTH_FLOOR = 0.2

# Evidence-stage tiers (verdict §"Concrete ranking design"): predicate is
# STRONGEST (an actual reference/endpoint identified), affordance is
# WEAKEST (static structure merely permits the type). Rank 1 = best.
_TIER_RANK: dict[str, int] = {"predicate": 1, "behavioral": 2, "affordance": 3}

# The one structural, type-level compositional relation R57 documents
# explicitly (T4 Delivery = T1 Reach/Target-Coincidence + T2
# Elimination/Obstacle-Consumption composed over time) — declared once,
# generically, never inferred from a specific game's footprint overlap.
_TEMPORAL_COMPOSITION_PAIRS: frozenset[frozenset[str]] = frozenset(
    {frozenset({"arrival", "elimination"})}
)

Frame = Sequence[Sequence[int]]
Cell = tuple[int, int]


def _mode_color(frame: Frame) -> int:
    counts = Counter(v for row in frame for v in row)
    return counts.most_common(1)[0][0]


def _floor_anchor(raw: float, gate_min: float, gate_max: float = 1.0) -> float:
    """Rescale ``raw`` (a detector's un-anchored margin) so ``gate_min``
    (that formula's value at its OWN minimum firing threshold — computed
    analytically per detector, see each ``_detect_*`` docstring) maps to
    ``_STRENGTH_FLOOR`` and ``gate_max`` maps to ``1.0``. Provably safe:
    ``raw >= gate_min`` always holds by construction (a fired detector's
    gated terms are, by definition, never below their own gate), so the
    result is always in ``[_STRENGTH_FLOOR, 1.0]``. The
    ``max(0.0, min(1.0, ...))`` clamp is defensive only (floating-point
    safety), not load-bearing. This value remains a detector-LOCAL margin
    (see module docstring) — comparable across candidates of the SAME
    detector, not across detectors.
    """
    denom = max(gate_max - gate_min, 1e-9)
    return _STRENGTH_FLOOR + (1 - _STRENGTH_FLOOR) * max(0.0, min(1.0, (raw - gate_min) / denom))


class _Ledger:
    """Per-call bookkeeping: sequential evidence/candidate handle minting plus
    the region-index detail behind each evidence handle (harness-facing
    only — stripped by :func:`compact_view` before injection)."""

    def __init__(self) -> None:
        self._evidence_seq = 0
        self._candidate_seq = 0
        self.evidence_detail: dict[str, dict[str, Any]] = {}

    def evidence(self, region_index: int | None, note: str, **extra: Any) -> str:
        self._evidence_seq += 1
        handle = f"evidence:{self._evidence_seq}"
        detail: dict[str, Any] = {"note": note, **extra}
        if region_index is not None:
            detail["region"] = f"region:{region_index}"
            detail["region_index"] = region_index
        self.evidence_detail[handle] = detail
        return handle

    def candidate_id(self) -> str:
        self._candidate_seq += 1
        return f"goal:{self._candidate_seq}"

    def region_index_of(self, evidence_handle: str) -> int | None:
        return self.evidence_detail.get(evidence_handle, {}).get("region_index")


def _containers_map(relations: list[dict[str, Any]]) -> dict[int, list[int]]:
    """ALL bbox descendants per container (region_relations' 'contains' is
    already transitively closed — every strictly-containing pair, not just
    immediate parent/child). See :func:`_immediate_children` for the
    transitive reduction the new ``pattern_match`` detector needs."""
    containers: dict[int, list[int]] = {}
    for rel in relations:
        if rel["relation"] == "contains":
            containers.setdefault(rel["a"], []).append(rel["b"])
    return containers


def _immediate_children(regions: list[dict[str, Any]], containers_all: dict[int, list[int]]) -> dict[int, list[int]]:
    """Transitive reduction of ``containers_all`` to IMMEDIATE containment
    only: for every descendant, its immediate parent is the containing
    region with the SMALLEST bbox area among all regions that contain it —
    by construction, no other container can sit strictly between the
    tightest enclosing container and the descendant, since the tightest
    one IS the smallest. Pure set/geometry reasoning, no game constants.
    """
    descendant_to_containers: dict[int, list[int]] = {}
    for p, descendants in containers_all.items():
        for d in descendants:
            descendant_to_containers.setdefault(d, []).append(p)

    def _area(idx: int) -> int:
        r0, c0, r1, c1 = regions[idx]["bbox"]
        return (r1 - r0 + 1) * (c1 - c0 + 1)

    immediate: dict[int, list[int]] = {}
    for d, parents in descendant_to_containers.items():
        tightest = min(parents, key=_area)
        immediate.setdefault(tightest, []).append(d)
    return immediate


def _lattice_shape(regions: list[dict[str, Any]], children: list[int]) -> tuple[int, int] | None:
    """Do ``children`` (region indices) form a regular, addressable
    two-axis slot lattice? Groups by row then by column (:func:`group_by_axis`)
    and requires >=2 rows, >=2 columns, and a UNIFORM row width AND column
    height (every row has the same child count, every column has the same
    child count) — a strict, self-consistent MxN grid, not merely "roughly
    aligned". Returns ``(n_rows, n_cols)`` or ``None``.
    """
    if len(children) < _MIN_LATTICE_CHILDREN:
        return None
    subset = [regions[i] for i in children]
    row_groups = group_by_axis(subset, axis="row")
    col_groups = group_by_axis(subset, axis="col")
    n_rows, n_cols = len(row_groups), len(col_groups)
    if n_rows < 2 or n_cols < 2:
        return None
    row_sizes = {len(g) for g in row_groups}
    col_sizes = {len(g) for g in col_groups}
    if len(row_sizes) != 1 or len(col_sizes) != 1:
        return None
    return (n_rows, n_cols)


def _find_congruent_panel_pair(
    regions: list[dict[str, Any]], immediate: dict[int, list[int]]
) -> tuple[int, list[int], int, list[int], str] | None:
    """Two DIFFERENT immediate-containment container regions whose children
    counts match (and whose lattice shapes match, if both form lattices) —
    a canvas/reference pair suitable for comparison. Deterministic: returns
    the first congruent pair found in ``immediate``'s (regions-sorted,
    hence deterministic) iteration order.
    """
    items = [(c, kids) for c, kids in immediate.items() if len(kids) >= _MIN_PANEL_PAIR_CHILDREN]
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            c1, kids1 = items[i]
            c2, kids2 = items[j]
            if len(kids1) != len(kids2):
                continue
            shape1 = _lattice_shape(regions, kids1)
            shape2 = _lattice_shape(regions, kids2)
            tag = "congruent_lattice" if (shape1 and shape1 == shape2) else "congruent_count"
            return (c1, kids1, c2, kids2, tag)
    return None


def _cells_of(regions: list[dict[str, Any]], indices: Sequence[int]) -> frozenset[Cell]:
    out: set[Cell] = set()
    for i in indices:
        out |= regions[i]["cells"]
    return frozenset(out)


def _detect_arrival(
    regions: list[dict[str, Any]],
    frame_area: int,
    ledger: _Ledger,
    transition_window: Sequence[Frame] | None,
) -> dict[str, Any] | None:
    """T1 Reach/Target-Coincidence -> ``arrival``. See module docstring.

    Fires when >=1 region's colour occurs nowhere else in the frame AND its
    size does not dominate (>50% of) the board — a colour-unique,
    non-dominant region is the candidate marked locus. Among such
    candidates, the smallest is picked (sharpest single-locus reading).

    **Margin** = ``uniqueness_sharpness * size_distinctness``:
    ``uniqueness_sharpness = 1/n_candidates`` (fewer competing unique-colour
    regions = sharper signal); ``size_distinctness = 1 - size/frame_area``
    (smaller relative to the board reads as more marker-like). Floor-
    anchored with ``gate_min = uniqueness_sharpness_actual * 0.5`` (only the
    size term is gated, at the dominance boundary; sharpness is ungated and
    cancels out of the rescaling).

    **Evidence stage**: ``predicate`` when the candidate is UNAMBIGUOUS
    (exactly one colour-unique, non-dominant region — the endpoint really
    IS identified, not merely one of several plausible readings);
    ``behavioral`` when a ``transition_window`` is supplied and at least
    one observed transition's changed cells overlap the candidate's OWN
    cells (something interacted directly at the locus); ``affordance``
    otherwise (a plausible target exists, nothing more).
    """
    if len(regions) < 2 or frame_area <= 0:
        return None
    color_counts = Counter(r["color"] for r in regions)
    unique = [
        (i, r) for i, r in enumerate(regions) if color_counts[r["color"]] == 1 and r["size"] <= 0.5 * frame_area
    ]
    if not unique:
        return None
    idx, region = min(unique, key=lambda pair: pair[1]["size"])
    uniqueness_sharpness = 1 / len(unique)
    size_distinctness = 1 - region["size"] / frame_area
    raw = uniqueness_sharpness * size_distinctness
    gate_min = uniqueness_sharpness * 0.5
    strength = _floor_anchor(raw, gate_min)

    stage = "predicate" if len(unique) == 1 else "affordance"
    basis = {"colour_uniqueness", "dominance_exclusion"}
    if transition_window and len(transition_window) >= 2:
        candidate_cells: frozenset[Cell] = region["cells"]
        for a, b in zip(transition_window, transition_window[1:], strict=False):
            if frame_diff(a, b)["cells"] & candidate_cells:
                if stage != "predicate":
                    stage = "behavioral"
                basis.add("transition_interaction")
                break

    note = "region colour occurs nowhere else in the frame and does not dominate (>50%) the board"
    handle = ledger.evidence(idx, note)
    return {
        "id": ledger.candidate_id(),
        "type": "arrival",
        "support": [handle],
        "against": [],
        "strength": strength,
        "_evidence_stage": stage,
        "_footprint": {"regions": frozenset({idx}), "cells": region["cells"]},
        "_basis": basis,
    }


def _detect_uniformity(
    regions: list[dict[str, Any]],
    ledger: _Ledger,
    transition_window: Sequence[Frame] | None,
) -> dict[str, Any] | None:
    """T6 Toggle-Parity -> ``uniformity``. See module docstring.

    Fires when >=``_MIN_UNIFORM_GRID_COUNT`` regions share an identical
    translation-invariant shape signature, that shape spans >1 cell, and
    the class uses <=``_MAX_UNIFORM_SHAPE_COLORS`` distinct colours
    (candidate classes tried in population-descending order, so a
    disqualified large class never masks a smaller valid one).

    **Margin** = ``population_frac * non_triviality * colour_fit``, floor-
    anchored with ``gate_min = (_MIN_UNIFORM_GRID_COUNT/n_total) * 0.5 *
    (1/3)`` (ALL three terms are gated, so this is a pure per-call number).

    **Evidence stage**: ``affordance`` by default (a repeated non-trivial
    shape-class population exists — a static permission, nothing more).
    Promoted to ``behavioral`` when a ``transition_window`` shows a
    transition whose changed-cell footprint is a subset of, or equal to,
    ONE of the class's member regions' own cells — "a changed footprint
    closely aligned with one repeated N-cell region" (a case named
    explicitly in the R58 verdict for a public toggle-grid game). No
    ``predicate`` promotion is implemented — identifying the actual
    target/constraint PATTERN (which
    cells must reach which state) is out of scope here and belongs to the
    ``toggle_linear`` MECHANIC playbook, not this goal-typology ledger.
    """
    if not regions:
        return None
    groups: dict[frozenset, list[int]] = {}
    for i, r in enumerate(regions):
        groups.setdefault(multiset_signature(r), []).append(i)
    n_total = len(regions)
    for sig, members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if len(members) < _MIN_UNIFORM_GRID_COUNT:
            break  # population-descending order: no later class clears this bar either
        if len(sig) < _MIN_UNIFORM_SHAPE_CELLS:
            continue  # trivial 1-cell shape — decorative texture, not a toggle grid
        colours = {regions[i]["color"] for i in members}
        if len(colours) > _MAX_UNIFORM_SHAPE_COLORS:
            continue  # too many colours for one coherent toggle-grid class
        population_frac = len(members) / n_total
        non_triviality = 1 - 1 / len(sig)
        colour_fit = 1 - (len(colours) - 1) / _MAX_UNIFORM_SHAPE_COLORS
        raw = population_frac * non_triviality * colour_fit
        gate_min = (
            (_MIN_UNIFORM_GRID_COUNT / n_total)
            * (1 - 1 / _MIN_UNIFORM_SHAPE_CELLS)
            * (1 - (_MAX_UNIFORM_SHAPE_COLORS - 1) / _MAX_UNIFORM_SHAPE_COLORS)
        )
        strength = _floor_anchor(raw, gate_min)

        stage = "affordance"
        basis = {"repeated_shape_class"}
        if transition_window and len(transition_window) >= 2:
            member_cell_sets = [regions[i]["cells"] for i in members]
            for a, b in zip(transition_window, transition_window[1:], strict=False):
                diff_cells = frame_diff(a, b)["cells"]
                if not diff_cells:
                    continue
                if any(diff_cells <= mc or mc <= diff_cells for mc in member_cell_sets):
                    stage = "behavioral"
                    basis.add("transition_alignment")
                    break

        sample = members[:MAX_HANDLES_PER_CANDIDATE]
        handles = [
            ledger.evidence(
                i, f"one of {len(members)} regions sharing an identical {len(sig)}-cell translation-invariant shape"
            )
            for i in sample
        ]
        return {
            "id": ledger.candidate_id(),
            "type": "uniformity",
            "support": handles,
            "against": [],
            "strength": strength,
            "_evidence_stage": stage,
            "_footprint": {"regions": frozenset(members), "cells": _cells_of(regions, members)},
            "_basis": basis,
        }
    return None


def _detect_containment(
    regions: list[dict[str, Any]],
    containers: dict[int, list[int]],
    ledger: _Ledger,
    transition_window: Sequence[Frame] | None,
) -> dict[str, Any] | None:
    """T3 Assignment/Matching -> ``containment``. See module docstring.

    Fires when >=``_MIN_CONTAINMENT_SIBLINGS`` sibling container regions
    each hold >=``_MIN_CONTAINMENT_ITEMS_PER_SIBLING`` item regions.

    **Margin** = ``sibling_component * regularity``, floor-anchored with
    ``gate_min = (1 - 1/_MIN_CONTAINMENT_SIBLINGS) * regularity_actual``
    (only sibling count is gated; regularity is ungated and cancels).

    **Evidence stage**: ``predicate`` when regularity is PERFECT
    (``stdev == 0`` — every sibling holds exactly the same item count, a
    genuine parallel slot structure, not merely roughly-similar);
    ``behavioral`` when a ``transition_window`` shows a transition whose
    changed cells touch the containment structure's own footprint (items
    appearing to move/appear/vanish within it); ``affordance`` otherwise.
    """
    qualifying = {c: items for c, items in containers.items() if len(items) >= _MIN_CONTAINMENT_ITEMS_PER_SIBLING}
    if len(qualifying) < _MIN_CONTAINMENT_SIBLINGS:
        return None
    counts = [len(items) for items in qualifying.values()]
    n = len(counts)
    mean = sum(counts) / n
    stdev = (sum((c - mean) ** 2 for c in counts) / n) ** 0.5
    regularity = max(0.0, 1 - (stdev / mean if mean else 1.0))
    sibling_component = 1 - 1 / n
    raw = sibling_component * regularity
    gate_min = (1 - 1 / _MIN_CONTAINMENT_SIBLINGS) * regularity
    strength = _floor_anchor(raw, gate_min)

    all_indices = list(qualifying.keys()) + [i for items in qualifying.values() for i in items]
    footprint_cells = _cells_of(regions, all_indices)
    stage = "predicate" if stdev == 0 else "affordance"
    basis = {"sibling_containers", "item_regularity"}
    if transition_window and len(transition_window) >= 2:
        for a, b in zip(transition_window, transition_window[1:], strict=False):
            if frame_diff(a, b)["cells"] & footprint_cells:
                if stage != "predicate":
                    stage = "behavioral"
                basis.add("transition_interaction")
                break

    sample = list(qualifying.items())[:MAX_HANDLES_PER_CANDIDATE]
    handles = [ledger.evidence(c, f"container region holds {len(items)} item regions") for c, items in sample]
    return {
        "id": ledger.candidate_id(),
        "type": "containment",
        "support": handles,
        "against": [],
        "strength": strength,
        "_evidence_stage": stage,
        "_footprint": {"regions": frozenset(all_indices), "cells": footprint_cells},
        "_basis": basis,
    }


def _detect_pattern_match(
    regions: list[dict[str, Any]],
    containers_all: dict[int, list[int]],
    ledger: _Ledger,
    transition_window: Sequence[Frame] | None,
) -> dict[str, Any] | None:
    """T5 Fill/Paint-to-Pattern -> ``pattern_match``. See module docstring.

    **R58 tuning round #3 — REPLACED, not tightened.** The v1/v2 detector
    tested only "exactly one bbox-container holds >=5 heterogeneous
    (>=3-colour) descendants" — ALL bbox descendants (not immediate
    children), and a 3-colour floor that directly conflicts with binary
    (2-colour) grids. It never implemented R57's actual T5 sketch: a
    canvas/reference RELATIONSHIP with accumulated editing evidence. Per
    the Codex verdict, this rebuild:

    1. Reduces bbox containment to an IMMEDIATE-containment hierarchy
       (:func:`_immediate_children` — transitive reduction).
    2. Finds a panel/canvas hypothesis via EITHER:
       (a) one container's immediate children form a regular, addressable
           two-axis slot LATTICE (:func:`_lattice_shape`), OR
       (b) TWO containers have CONGRUENT slot geometry — matching child
           counts (and matching lattice shape, if both are lattices) —
           suitable for canvas/reference comparison
           (:func:`_find_congruent_panel_pair`).
    3. No colour-count requirement of any kind (fixes a binary/2-colour
       grid conflict flagged in the R58 verdict) and no "exactly one
       container" requirement (fixes a known false-positive class flagged
       there too — an incidental heterogeneous blob inside one large bbox
       no longer qualifies unless it ALSO forms a genuine lattice or has a
       congruent sibling panel).
    4. A single static panel/pair is ``affordance`` ONLY (never strong
       evidence on its own) — promoted to ``behavioral`` when a
       ``transition_window`` shows every observed change confined to the
       candidate panel's own cells (cumulative localized edits, or a
       low-diff confirm transition following them — both read the same
       way here: "nothing changed outside the hypothesised canvas").

    **Margin**: for the congruent-pair reading, ``1 - 1/min(len(kids1),
    len(kids2))`` (richer congruent panels = stronger evidence), floor-
    anchored at the minimum pair size (``_MIN_PANEL_PAIR_CHILDREN``); for
    the single-lattice reading, ``1 - 1/n_children``, floor-anchored at the
    minimum lattice size (``_MIN_LATTICE_CHILDREN``, a 2x2 grid). If BOTH
    hypotheses are found, the congruent pair is preferred (a two-panel
    canvas/reference claim is structurally stronger than one lattice
    alone) — only one candidate fires per call, consistent with every
    other detector here.
    """
    immediate = _immediate_children(regions, containers_all)
    pair_hit = _find_congruent_panel_pair(regions, immediate)
    lattice_hit: tuple[int, list[int], tuple[int, int]] | None = None
    if pair_hit is None:
        for container_idx, kids in immediate.items():
            shape = _lattice_shape(regions, kids)
            if shape is not None:
                lattice_hit = (container_idx, kids, shape)
                break
    if pair_hit is None and lattice_hit is None:
        return None

    basis: set[str] = {"immediate_containment"}
    if pair_hit is not None:
        c1, kids1, c2, kids2, tag = pair_hit
        basis.add(tag)
        all_indices = [c1, c2, *kids1, *kids2]
        footprint_cells = _cells_of(regions, all_indices)
        smaller = min(len(kids1), len(kids2))
        raw = 1 - 1 / smaller
        gate_min = 1 - 1 / _MIN_PANEL_PAIR_CHILDREN
        note = f"two container regions hold congruent children ({len(kids1)} vs {len(kids2)}, {tag})"
        support_region = c1
    else:
        container_idx, kids, shape = lattice_hit  # type: ignore[misc]
        basis.add("addressable_lattice")
        all_indices = [container_idx, *kids]
        footprint_cells = _cells_of(regions, all_indices)
        raw = 1 - 1 / len(kids)
        gate_min = 1 - 1 / _MIN_LATTICE_CHILDREN
        note = f"container region's children form a regular {shape[0]}x{shape[1]} addressable lattice"
        support_region = container_idx

    strength = _floor_anchor(raw, gate_min)
    stage = "affordance"
    if transition_window and len(transition_window) >= 2:
        confined_edits = 0
        observed = 0
        for a, b in zip(transition_window, transition_window[1:], strict=False):
            diff_cells = frame_diff(a, b)["cells"]
            if not diff_cells:
                continue
            observed += 1
            if diff_cells <= footprint_cells:
                confined_edits += 1
        if observed > 0 and confined_edits == observed:
            stage = "behavioral"
            basis.add("confined_localized_edits")

    handle = ledger.evidence(support_region, note)
    return {
        "id": ledger.candidate_id(),
        "type": "pattern_match",
        "support": [handle],
        "against": [],
        "strength": strength,
        "_evidence_stage": stage,
        "_footprint": {"regions": frozenset(all_indices), "cells": footprint_cells},
        "_basis": basis,
    }


def _vanished_signatures(
    before: Frame, after: Frame, background: int | None
) -> tuple[list[dict[str, Any]], list[tuple[Any, frozenset]]]:
    """Regions of ``before`` plus the list of ``(colour, shape)`` signatures
    present in ``before`` with no match in ``after``. Shared by
    :func:`_detect_elimination`'s primary-evidence pick and its
    multi-transition confirmation pass, so the same signature-diff logic
    is computed identically (and only once per transition) in both uses.
    """
    bg_before = background if background is not None else _mode_color(before)
    bg_after = background if background is not None else _mode_color(after)
    regs_before = find_regions(before, background=bg_before)
    regs_after = find_regions(after, background=bg_after)
    sig_before = Counter((r["color"], multiset_signature(r)) for r in regs_before)
    sig_after = Counter((r["color"], multiset_signature(r)) for r in regs_after)
    return regs_before, list((sig_before - sig_after).elements())


def _detect_elimination(
    before: Frame,
    after: Frame,
    background: int | None,
    ledger: _Ledger,
    extra_transitions: Sequence[tuple[Frame, Frame]] | None = None,
) -> dict[str, Any] | None:
    """T2 Elimination/Obstacle-Consumption -> ``elimination``. Needs a
    before/after PAIR (a material transition), not a single frame — so,
    unlike the four frame-based detectors above, its evidence is inherently
    TRANSITIONAL: its tier ranges ``behavioral``/``predicate`` only, never
    ``affordance`` (there is no "static-only" elimination reading).

    **Margin** = ``size_component * signature_distinctness *
    confirmation_component`` (unchanged since the R58 tuning-round-1/2
    passes — see prior round's inline history if needed); floor-anchored
    with ``gate_min = size_component_actual * signature_distinctness_actual
    * 0.5`` (only confirmation is gated, at its own provable floor of 0.5 —
    the primary transition alone always contributes >=1 to
    ``n_transitions_with_a_vanish``).

    **Evidence stage**: ``predicate`` when CORROBORATED (``extra_transitions``
    supplied and at least one shows an independent vanish, i.e.
    ``confirmation_component == 1.0`` — a recurring elimination-shaped
    event is stronger identification than a single occurrence);
    ``behavioral`` otherwise (an uncorroborated single-transition vanish is
    still real transitional evidence, just weaker).
    """
    regs_before, vanished = _vanished_signatures(before, after, background)
    if not vanished:
        return None
    color, shape = vanished[0]
    idx = next(i for i, r in enumerate(regs_before) if r["color"] == color and multiset_signature(r) == shape)

    frame_area = len(before) * len(before[0]) if before and before[0] else 1
    vanished_frac = regs_before[idx]["size"] / frame_area
    before_sizes = sorted(r["size"] for r in regs_before)
    median_frac = (before_sizes[len(before_sizes) // 2] if before_sizes else regs_before[idx]["size"]) / frame_area
    denom = max(vanished_frac, median_frac, 1e-9)
    size_component = max(0.0, 1 - abs(vanished_frac - median_frac) / denom)

    n_distinct_vanished = len(set(vanished))
    signature_distinctness = 1 / n_distinct_vanished

    transitions = [(before, after), *(extra_transitions or [])]
    n_with_vanish = sum(1 for b, a in transitions if _vanished_signatures(b, a, background)[1])
    confirmation_component = min(1.0, n_with_vanish / 2)

    raw = size_component * signature_distinctness * confirmation_component
    gate_min = size_component * signature_distinctness * 0.5
    strength = _floor_anchor(raw, gate_min)

    stage = "predicate" if confirmation_component >= 1.0 else "behavioral"
    handle = ledger.evidence(
        idx, "region present before the transition has no matching (colour, shape) after it", frame="before"
    )
    return {
        "id": ledger.candidate_id(),
        "type": "elimination",
        "support": [handle],
        "against": [],
        "strength": strength,
        "_evidence_stage": stage,
        "_footprint": {"regions": frozenset({idx}), "cells": regs_before[idx]["cells"]},
        "_basis": {"vanished_signature", "corroborated" if stage == "predicate" else "single_transition"},
    }


def _detect_threshold(action_repeat_frames: Sequence[Frame], ledger: _Ledger) -> dict[str, Any] | None:
    """T7 Threshold/Repeated-Action-Count -> ``threshold``. Needs a short
    window of frames under one repeated action — also inherently
    transitional evidence, so its tier is fixed at ``behavioral`` (no
    ``affordance`` reading is possible; no ``predicate`` promotion is
    implemented — identifying the actual threshold VALUE a hidden counter
    must cross is out of scope for a structural proxy).

    **Margin** = ``run_length_component * magnitude_component``, floor-
    anchored with ``gate_min = 0.5 * magnitude_component_actual`` (only
    run-length is gated; magnitude is ungated and cancels).
    """
    if len(action_repeat_frames) < _MIN_THRESHOLD_REPEATS:
        return None
    diffs = [
        frame_diff(a, b)["count"] for a, b in zip(action_repeat_frames, action_repeat_frames[1:], strict=False)
    ]
    if len(diffs) < _MIN_THRESHOLD_DIFFS or diffs[0] == diffs[-1]:
        return None
    increasing = all(b >= a for a, b in zip(diffs, diffs[1:], strict=False))
    decreasing = all(b <= a for a, b in zip(diffs, diffs[1:], strict=False))
    if not (increasing or decreasing):
        return None
    direction = "upward" if increasing else "downward"
    run_length_component = 1 - 1 / len(diffs)
    magnitude_component = abs(diffs[-1] - diffs[0]) / max(diffs[-1], diffs[0], 1)
    raw = run_length_component * magnitude_component
    gate_min = (1 - 1 / _MIN_THRESHOLD_DIFFS) * magnitude_component
    strength = _floor_anchor(raw, gate_min)
    handle = ledger.evidence(
        None, f"frame_diff cell count trends {direction} across {len(diffs)} repeats of one action", diffs=diffs
    )
    footprint_cells: frozenset[Cell] = frozenset()
    for a, b in zip(action_repeat_frames, action_repeat_frames[1:], strict=False):
        footprint_cells |= frame_diff(a, b)["cells"]
    return {
        "id": ledger.candidate_id(),
        "type": "threshold",
        "support": [handle],
        "against": [],
        "strength": strength,
        "_evidence_stage": "behavioral",
        "_footprint": {"regions": frozenset(), "cells": footprint_cells},
        "_basis": {"monotonic_diff_trend"},
    }


# ----- adjudication pass: footprint-dependency relations ------------------------
def _footprint_relation(a: dict[str, Any], b: dict[str, Any]) -> str | None:
    """Pairwise footprint-set relation between two candidates' ``_footprint``
    cell sets — pure set arithmetic, no game constants. Returns
    ``"subsumed_evidence"`` when one footprint is a (non-empty) subset of
    the other, ``"shared_evidence"`` when they overlap without either
    containing the other, ``"independent_evidence"`` when disjoint, or
    ``None`` when either footprint is empty (nothing to compare).
    """
    fa = a["_footprint"]["cells"]
    fb = b["_footprint"]["cells"]
    if not fa or not fb:
        return None
    if fa <= fb or fb <= fa:
        return "subsumed_evidence"
    if fa & fb:
        return "shared_evidence"
    return "independent_evidence"


def _adjudicate(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """All pairwise dependency relations among fired candidates. A pair may
    carry BOTH a footprint relation and ``temporal_composition`` (they are
    independent axes: footprint overlap is about evidence reuse,
    ``temporal_composition`` is about R57's own declared type-level
    compositions). Every relation is symmetric; each pair is emitted once.
    """
    relations: list[dict[str, Any]] = []
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            a, b = candidates[i], candidates[j]
            rel = _footprint_relation(a, b)
            if rel is not None:
                relations.append({"a": a["id"], "b": b["id"], "relation": rel})
            if frozenset({a["type"], b["type"]}) in _TEMPORAL_COMPOSITION_PAIRS:
                relations.append({"a": a["id"], "b": b["id"], "relation": "temporal_composition"})
    return relations


# ----- capping: preserve tiers, ambiguity pairs, and independent footprints -----
def _cluster_ambiguity_groups(
    candidates: list[dict[str, Any]], dependencies: list[dict[str, Any]]
) -> list[list[dict[str, Any]]]:
    """Union-find over ``shared_evidence``/``subsumed_evidence`` edges only —
    an "explicit ambiguity" per the verdict's cap policy, kept or dropped
    TOGETHER. ``independent_evidence``/``temporal_composition`` never merge
    a group (independence is the opposite signal; composition is a noted
    relationship, not an evidence tension forcing joint retention).
    """
    parent = {c["id"]: c["id"] for c in candidates}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for dep in dependencies:
        if dep["relation"] in ("shared_evidence", "subsumed_evidence"):
            union(dep["a"], dep["b"])

    by_root: dict[str, list[dict[str, Any]]] = {}
    for c in candidates:
        by_root.setdefault(find(c["id"]), []).append(c)
    return list(by_root.values())


def _apply_cap(
    candidates: list[dict[str, Any]], dependencies: list[dict[str, Any]], max_candidates: int
) -> list[dict[str, Any]]:
    """Cap to ``max_candidates`` while preserving (in priority order): the
    highest evidence tiers, both sides of an explicit ambiguity (an
    ambiguity GROUP is added or skipped as a unit — never split, except as
    a last-resort truncation when a single group alone exceeds the cap),
    and coverage of mutually INDEPENDENT footprints (greedy: at each step,
    prefer the best-tier remaining group that adds the most previously-
    uncovered footprint). Margin/detector-order are the FINAL tie-break,
    applied only to sequence groups that are otherwise equal.
    """
    if len(candidates) <= max_candidates:
        return candidates
    groups = _cluster_ambiguity_groups(candidates, dependencies)
    for g in groups:
        g.sort(key=lambda c: (_TIER_RANK[c["_evidence_stage"]], -c["strength"]))

    def group_tier(g: list[dict[str, Any]]) -> int:
        return min(_TIER_RANK[c["_evidence_stage"]] for c in g)

    def group_margin(g: list[dict[str, Any]]) -> float:
        return max(c["strength"] for c in g)

    def group_cells(g: list[dict[str, Any]]) -> frozenset[Cell]:
        out: set[Cell] = set()
        for c in g:
            out |= c["_footprint"]["cells"]
        return frozenset(out)

    remaining = list(groups)
    selected: list[dict[str, Any]] = []
    covered: set[Cell] = set()
    while remaining and len(selected) < max_candidates:

        def key(g: list[dict[str, Any]]) -> tuple[int, int, float]:
            new_coverage = len(group_cells(g) - covered)
            return (group_tier(g), -new_coverage, -group_margin(g))

        best = min(remaining, key=key)
        remaining.remove(best)
        room = max_candidates - len(selected)
        selected.extend(best[:room])  # truncate only if a single group alone overflows the cap
        covered |= group_cells(best)
    selected.sort(key=lambda c: (_TIER_RANK[c["_evidence_stage"]], -c["strength"]))
    return selected


# ----- unresolved_tests: concrete structural probes -----------------------------
_PROBE_TEMPLATES: dict[frozenset[str], str] = {
    frozenset({"uniformity", "pattern_match"}): (
        "whether edits follow a translated fixed stencil (uniformity) or directly repaint one "
        "addressable canvas slot (pattern_match)"
    ),
    frozenset({"arrival", "elimination"}): (
        "whether the region reached (arrival) is the SAME region later consumed (elimination) — a "
        "delivery composition — or these are two independent events"
    ),
    frozenset({"arrival", "containment"}): (
        "whether the candidate region is an isolated target to reach (arrival) or a slot to be "
        "filled/matched within the containment structure"
    ),
    frozenset({"containment", "pattern_match"}): (
        "whether children must be individually matched to slots (containment) or the container is "
        "painted/filled as a whole (pattern_match)"
    ),
}


def _probe_for(a: dict[str, Any], b: dict[str, Any]) -> str:
    key = frozenset({a["type"], b["type"]})
    if key in _PROBE_TEMPLATES:
        return f"{a['id']}/{b['id']}: {_PROBE_TEMPLATES[key]}"
    return (
        f"{a['id']} ({a['type']}) vs {b['id']} ({b['type']}): resolve via a targeted probe action "
        "before committing to either reading"
    )


def _build_unresolved(candidates: list[dict[str, Any]], dependencies: list[dict[str, Any]]) -> list[str]:
    ids_present = {c["id"] for c in candidates}
    by_id = {c["id"]: c for c in candidates}
    notes: list[str] = []
    seen_pairs: set[frozenset[str]] = set()
    for dep in dependencies:
        if dep["a"] not in ids_present or dep["b"] not in ids_present:
            continue
        if dep["relation"] not in ("shared_evidence", "subsumed_evidence"):
            continue
        pair_key = frozenset({dep["a"], dep["b"]})
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)
        notes.append(_probe_for(by_id[dep["a"]], by_id[dep["b"]]))
    for c in candidates:
        if c["against"]:
            notes.append(
                f"{c['id']} ({c['type']}) has a structural contradiction — resolve with a cheap probe before committing"
            )
    return notes


def detect(observations: dict[str, Any]) -> dict[str, Any]:
    """Run every detector that has enough input, return a CAPPED HYPOTHESIS
    SET — not an elected winner (see module docstring, R58 tuning round #3).

    ``observations`` (all keys optional; each detector uses only what it
    needs):

    - ``frame``: the current/first frame. Drives ``arrival``,
      ``uniformity``, ``containment``, ``pattern_match`` (all zero-action,
      single-frame at minimum).
    - ``background``: explicit background colour override; defaults to the
      frame's mode colour.
    - ``transition_window``: optional list of >=2 CONSECUTIVE observed
      frames (still pre-clear — no level-up label, just more early
      observation). Used by ``arrival``/``uniformity``/``containment``/
      ``pattern_match`` to promote from ``affordance`` to ``behavioral``
      evidence stage when observed transitions behave as the type
      predicts. ``detect()`` remains pure/stateless — this is caller-
      supplied data, not internal memory.
    - ``before`` / ``after``: a material-transition frame pair. Drives
      ``elimination`` (inherently transitional; never ``affordance``).
    - ``extra_transitions``: optional additional ``(before, after)`` pairs
      beyond the primary one — corroborating evidence for ``elimination``'s
      confirmation component and its ``predicate`` promotion.
    - ``action_repeat_frames``: a short (>=3) sequence of frames observed
      under one repeated action. Drives ``threshold`` (inherently
      transitional; always ``behavioral``).

    Returns ``{"goal_candidates": [...], "unresolved_tests": [...],
    "insufficient_evidence": bool, "evidence_detail": {...}, "dependencies":
    [...]}``. Each ``goal_candidates`` entry additionally carries
    ``"tier"`` (1=predicate, 2=behavioral, 3=affordance — the compact,
    injectable form of ``_evidence_stage``). ``evidence_detail`` and
    ``dependencies`` are HARNESS-ONLY bookkeeping — call :func:`compact_view`
    before injecting into a model turn.

    Per verdict §4: "goal type and mechanic intent must remain separate" —
    this function never mentions or selects a playbook/intent name, only
    win-condition TYPES. ``insufficient_evidence`` is "fewer than two
    candidates fired" (verdict's two-hypotheses-or-insufficient-evidence
    rule), computed on the UNCAPPED fired set — capping is an injection-size
    concern, not an evidence-strength one.

    **Ranking (R58 tuning round #3).** ``goal_candidates`` is TIER-ORDERED
    first (predicate > behavioral > affordance), margin/detector-order only
    breaking ties for deterministic presentation — never asserting one
    same-tier candidate is "more true" than another. Capping
    (:func:`_apply_cap`) preserves top tiers, both sides of an explicit
    ambiguity, and independent-footprint coverage before falling back to
    margin. This replaces the R58 tuning-round-1/2 "sort everything by one
    scalar strength" design, which real-trace validation (three measurement
    rounds, `docs/r58_codex_ledger_ranking_20260715.md`) showed asserted
    more cross-detector comparability than the formulas actually supported.
    """
    ledger = _Ledger()
    candidates: list[dict[str, Any]] = []
    transition_window = observations.get("transition_window")

    frame = observations.get("frame")
    if frame is not None:
        background = observations.get("background")
        bg = background if background is not None else _mode_color(frame)
        regions = find_regions(frame, background=bg)
        relations = region_relations(regions)
        containers = _containers_map(relations)
        frame_area = len(frame) * len(frame[0]) if frame and frame[0] else 0

        arrival = _detect_arrival(regions, frame_area, ledger, transition_window)
        uniformity = _detect_uniformity(regions, ledger, transition_window)
        containment = _detect_containment(regions, containers, ledger, transition_window)
        pattern_match = _detect_pattern_match(regions, containers, ledger, transition_window)

        if arrival is not None:
            candidates.append(arrival)
        if uniformity is not None:
            candidates.append(uniformity)
        if containment is not None:
            candidates.append(containment)
        if pattern_match is not None:
            candidates.append(pattern_match)

        # Cross-check: is the arrival locus ALSO a contained item somewhere?
        # A genuine structural tension (not a fabricated contradiction) —
        # "isolated target" and "slot to be filled/matched" are competing
        # readings of the same region.
        if arrival is not None:
            contained_indices = {idx for items in containers.values() for idx in items}
            arrival_region = ledger.region_index_of(arrival["support"][0])
            if arrival_region in contained_indices:
                container_idx = next(c for c, items in containers.items() if arrival_region in items)
                against_handle = ledger.evidence(
                    container_idx,
                    "the same region is also a contained item within a containment structure, "
                    "contradicting an isolated-arrival reading",
                )
                arrival["against"].append(against_handle)

    before, after = observations.get("before"), observations.get("after")
    if before is not None and after is not None:
        elimination = _detect_elimination(
            before, after, observations.get("background"), ledger, observations.get("extra_transitions")
        )
        if elimination is not None:
            candidates.append(elimination)

    repeats = observations.get("action_repeat_frames")
    if repeats:
        threshold = _detect_threshold(repeats, ledger)
        if threshold is not None:
            candidates.append(threshold)

    insufficient_evidence = len(candidates) < 2
    dependencies = _adjudicate(candidates)
    capped = _apply_cap(candidates, dependencies, MAX_CANDIDATES)

    compact_candidates = [
        {k: v for k, v in c.items() if not k.startswith("_")} | {"tier": _TIER_RANK[c["_evidence_stage"]]}
        for c in capped
    ]
    return {
        "goal_candidates": compact_candidates,
        "unresolved_tests": _build_unresolved(capped, dependencies)[:MAX_UNRESOLVED],
        "insufficient_evidence": insufficient_evidence,
        "evidence_detail": ledger.evidence_detail,
        "dependencies": dependencies,
    }


def compact_view(result: dict[str, Any]) -> dict[str, Any]:
    """The injectable subset of :func:`detect`'s output — drops
    ``evidence_detail`` and ``dependencies`` (harness-only), matching the
    verdict §4 example output shape: ``{"goal_candidates", "unresolved_tests"}``
    plus the ``insufficient_evidence`` flag this module adds (verdict:
    "Require either two distinct competing goal hypotheses or an explicit
    insufficient_evidence declaration") and the ``"tier"`` field this R58
    tuning-round-3 rebuild adds to each candidate (verdict: "A compact
    candidate could add only `\"tier\": 2`"). ``"unknown"`` is not
    re-declared here — it is already always selectable at SELECT_INTENT
    (:attr:`admorphiq.explanation.protocol.ExplanationProtocol.allowed_intents`);
    a low/insufficient ledger is exactly the signal that should route a
    caller toward it, not a field this pure function needs to assert for
    itself.
    """
    return {k: v for k, v in result.items() if k not in ("evidence_detail", "dependencies")}
