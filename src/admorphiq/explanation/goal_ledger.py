"""GoalLedger: the executable win-condition typology (R58 verdict §4).

Turns R57's win-condition typology mining
(``docs/r57_win_condition_typology_20260715.md``) into a set of cheap,
kernel-composed, PRE-CLEAR detectors — no level-up labels, no gold data,
no game identity, ever, at runtime. ``detect(observations)`` is a pure
function: it runs every detector that has enough input to fire, returns a
capped, compact set of competing goal candidates plus any unresolved
structural ambiguity, and is silent (an empty result) rather than
speculative when the evidence doesn't support a call.

Naming follows the verdict's OWN example vocabulary
(``goals/detectors/{elimination,uniformity,pattern_match,containment,
arrival}.yaml``) rather than inventing new type names, so a goal
candidate's ``"type"`` field is directly one of those five plus one R58
addition (``threshold`` — justified below). Each detector's docstring
cross-references which R57 typology letter (T1-T8) it operationalizes —
by LETTER only, never by public-game name (``scripts/explanation_lint.py``
enforces that on this file, same as every other file in the package; the
full per-game provenance for each type lives in R57's own doc, not here).

Coverage vs. R57's 8 types, and why:

  - ``arrival``       <- T1 Reach/Target-Coincidence. Supported: a
    colour-unique, smaller-than-median region is a cheap, zero-action,
    single-frame structural proxy for "the marked locus" (R57's biggest
    bucket: movement AND click sub-forms both reduce to a distinguished
    target locus).
  - ``uniformity``     <- T6 Toggle-Parity. Supported: many same-shape
    regions (grid of repeated cells) is the zero-action structural
    precondition R57 measured on its cleanest single signal in the whole
    mining pass (a constant-shape stencil flip every level). NOTE: firing
    does not prove GF(2) structure (verdict §4's "uniformity does not
    prove GF(2)") — it only proposes the HYPOTHESIS that the win
    condition is "these repeated cells reach a uniform/target state";
    confirming GF(2) linearity is the ``toggle_linear`` MECHANIC
    playbook's job, not this ledger's.
  - ``containment``    <- T3 Assignment/Matching. Supported: >=2 sibling
    container regions each holding >=2 item regions is a zero-action
    structural proxy for the bordered-box/slot family R57 frame-verified
    on two of its games (a portal-graph sort and a sprite-to-target
    assignment).
  - ``pattern_match``  <- T5 Fill/Paint-to-Pattern. Supported: exactly ONE
    container region holding many (>=5) HETEROGENEOUS (>=3 distinct
    colours) item regions, as opposed to containment's >=2 SIMILAR
    siblings — proxying R57's evidence for a single growing, multi-colour
    canvas per level (frame-verified there via a full-block-vs-single-
    action diff contrast).
  - ``elimination``    <- T2 Elimination/Obstacle-Consumption. Supported,
    but needs a before/after frame PAIR (the "material transition"
    ledger trigger, not first observation) — a region present before is
    entirely absent after, matching R57's frame-verified door/obstacle
    and box-consumption evidence.
  - ``threshold``      <- T7 Threshold/Repeated-Action-Count. Supported,
    R58 ADDITION beyond the verdict's five named examples (R57 judged
    this a genuine, distinct type from two independent repeated-action
    build-up games). Needs a short window (>=3) of frames observed under
    ONE repeated action; a monotonic frame_diff trend is the zero-label
    proxy for a hidden counter approaching a threshold.
  - T4 Delivery/Carry-and-Place — **UNSUPPORTED as an independent
    detector.** R57 found T4 is compositionally T1 (a NON-player region
    reaching a locus) + T2 (that same region then vanishing/converting to
    a "delivered" marker). This ledger is a pure per-call function with
    no persistent identity tracking across multiple ``detect()``
    invocations, so it cannot itself correlate "the region that arrived
    is the SAME region that later vanished" — that correlation is a
    harness-level job (compare two ``detect()`` calls' ``arrival``/
    ``elimination`` evidence over time), not a new zero-action structural
    primitive. Shipping a "delivery" detector here would just be
    ``arrival`` and ``elimination`` under a third name with no new
    evidence behind it.
  - T8 Programmatic/Rewrite-Derivation — **UNSUPPORTED, explicitly, not a
    weak proxy.** R57's own coverage table is blunt about this: the one
    game that anchored this type's typology label has **zero** captured
    level-up events across the entire mining pass — its T8 label rests
    entirely on a one-time inspection of that game's implementation
    (verification-only, never generalizable to a hidden game). No
    frame-only signature for "this is a rewrite/program-derivation game"
    was ever validated against real data. A structural stand-in (e.g. "a
    linear 1-D strip of repeated cells, as opposed to uniformity's 2-D
    grid") was considered and rejected — per the explicit R58 instruction
    to mark a type ledger-unsupported rather than ship a stretch.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from admorphiq.kernels import find_regions, frame_diff, multiset_signature, region_relations

MAX_CANDIDATES = 4
MAX_HANDLES_PER_CANDIDATE = 3
MAX_UNRESOLVED = 3

# Structural thresholds. Deliberately small integers, not tuned to any one
# game's exact geometry (that would smuggle a public-game constant back
# into a "generic" detector — the R56 toolbase-verdict failure mode this
# package exists to avoid).
_MIN_UNIFORM_GRID_COUNT = 6
_MIN_CONTAINMENT_SIBLINGS = 2
_MIN_CONTAINMENT_ITEMS_PER_SIBLING = 2
_MIN_PATTERN_MATCH_ITEMS = 5
_MIN_PATTERN_MATCH_DISTINCT_COLORS = 3
_MIN_THRESHOLD_REPEATS = 3

Frame = Sequence[Sequence[int]]


def _mode_color(frame: Frame) -> int:
    counts = Counter(v for row in frame for v in row)
    return counts.most_common(1)[0][0]


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
    containers: dict[int, list[int]] = {}
    for rel in relations:
        if rel["relation"] == "contains":
            containers.setdefault(rel["a"], []).append(rel["b"])
    return containers


def _detect_arrival(regions: list[dict[str, Any]], ledger: _Ledger) -> dict[str, Any] | None:
    """T1 Reach/Target-Coincidence -> ``arrival``. See module docstring.

    Size filter is ``<= median`` (not strictly ``<``) deliberately: many
    real boards have a whole population of same-small-size tiles sharing
    one size class, so a strict ``<`` would (and, measured directly while
    building this detector, DID) exclude every colour-unique candidate
    whenever it happened to share that common size — the filter's actual
    job is only to exclude a single large DOMINANT panel from being
    mistaken for a small target marker, which ``<=`` still does.
    """
    if len(regions) < 2:
        return None
    color_counts = Counter(r["color"] for r in regions)
    sizes = sorted(r["size"] for r in regions)
    median_size = sizes[len(sizes) // 2]
    unique = [
        (i, r) for i, r in enumerate(regions) if color_counts[r["color"]] == 1 and r["size"] <= median_size
    ]
    if not unique:
        return None
    idx, _region = min(unique, key=lambda pair: pair[1]["size"])
    note = "region colour occurs nowhere else in the frame and is smaller than the median region size"
    handle = ledger.evidence(idx, note)
    return {"id": ledger.candidate_id(), "type": "arrival", "support": [handle], "against": []}


def _detect_uniformity(regions: list[dict[str, Any]], ledger: _Ledger) -> dict[str, Any] | None:
    """T6 Toggle-Parity -> ``uniformity``. See module docstring."""
    groups: dict[frozenset, list[int]] = {}
    for i, r in enumerate(regions):
        groups.setdefault(multiset_signature(r), []).append(i)
    if not groups:
        return None
    _sig, members = max(groups.items(), key=lambda kv: len(kv[1]))
    if len(members) < _MIN_UNIFORM_GRID_COUNT:
        return None
    sample = members[:MAX_HANDLES_PER_CANDIDATE]
    handles = [
        ledger.evidence(i, f"one of {len(members)} regions sharing an identical translation-invariant shape")
        for i in sample
    ]
    return {"id": ledger.candidate_id(), "type": "uniformity", "support": handles, "against": []}


def _detect_containment(
    regions: list[dict[str, Any]], containers: dict[int, list[int]], ledger: _Ledger
) -> dict[str, Any] | None:
    """T3 Assignment/Matching -> ``containment``. See module docstring."""
    qualifying = {c: items for c, items in containers.items() if len(items) >= _MIN_CONTAINMENT_ITEMS_PER_SIBLING}
    if len(qualifying) < _MIN_CONTAINMENT_SIBLINGS:
        return None
    sample = list(qualifying.items())[:MAX_HANDLES_PER_CANDIDATE]
    handles = [
        ledger.evidence(c, f"container region holds {len(items)} item regions")
        for c, items in sample
    ]
    return {"id": ledger.candidate_id(), "type": "containment", "support": handles, "against": []}


def _detect_pattern_match(
    regions: list[dict[str, Any]], containers: dict[int, list[int]], ledger: _Ledger
) -> dict[str, Any] | None:
    """T5 Fill/Paint-to-Pattern -> ``pattern_match``. See module docstring."""
    heterogeneous = []
    for c, items in containers.items():
        colors = {regions[i]["color"] for i in items}
        if len(items) >= _MIN_PATTERN_MATCH_ITEMS and len(colors) >= _MIN_PATTERN_MATCH_DISTINCT_COLORS:
            heterogeneous.append((c, items, colors))
    if len(heterogeneous) != 1:
        return None
    c, items, colors = heterogeneous[0]
    handle = ledger.evidence(
        c, f"container region holds {len(items)} item regions spanning {len(colors)} distinct colours"
    )
    return {"id": ledger.candidate_id(), "type": "pattern_match", "support": [handle], "against": []}


def _detect_elimination(
    before: Frame, after: Frame, background: int | None, ledger: _Ledger
) -> dict[str, Any] | None:
    """T2 Elimination/Obstacle-Consumption -> ``elimination``. Needs a
    before/after PAIR (a material transition), not a single frame. See
    module docstring."""
    bg_before = background if background is not None else _mode_color(before)
    bg_after = background if background is not None else _mode_color(after)
    regs_before = find_regions(before, background=bg_before)
    regs_after = find_regions(after, background=bg_after)
    sig_before = Counter((r["color"], multiset_signature(r)) for r in regs_before)
    sig_after = Counter((r["color"], multiset_signature(r)) for r in regs_after)
    vanished = list((sig_before - sig_after).elements())
    if not vanished:
        return None
    color, shape = vanished[0]
    idx = next(i for i, r in enumerate(regs_before) if r["color"] == color and multiset_signature(r) == shape)
    handle = ledger.evidence(
        idx, "region present before the transition has no matching (colour, shape) after it", frame="before"
    )
    return {"id": ledger.candidate_id(), "type": "elimination", "support": [handle], "against": []}


def _detect_threshold(action_repeat_frames: Sequence[Frame], ledger: _Ledger) -> dict[str, Any] | None:
    """T7 Threshold/Repeated-Action-Count -> ``threshold``. Needs a short
    window of frames under one repeated action. See module docstring."""
    if len(action_repeat_frames) < _MIN_THRESHOLD_REPEATS:
        return None
    diffs = [
        frame_diff(a, b)["count"] for a, b in zip(action_repeat_frames, action_repeat_frames[1:], strict=False)
    ]
    if len(diffs) < 2 or diffs[0] == diffs[-1]:
        return None
    increasing = all(b >= a for a, b in zip(diffs, diffs[1:], strict=False))
    decreasing = all(b <= a for a, b in zip(diffs, diffs[1:], strict=False))
    if not (increasing or decreasing):
        return None
    direction = "upward" if increasing else "downward"
    handle = ledger.evidence(
        None, f"frame_diff cell count trends {direction} across {len(diffs)} repeats of one action", diffs=diffs
    )
    return {"id": ledger.candidate_id(), "type": "threshold", "support": [handle], "against": []}


def _build_unresolved(candidates: list[dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    types = sorted({c["type"] for c in candidates})
    if len(types) >= 2:
        notes.append(f"which of {types} is the true win condition is not yet determined by static structure alone")
    for c in candidates:
        if c["against"]:
            notes.append(
                f"{c['id']} ({c['type']}) has a structural contradiction — resolve with a cheap probe before committing"
            )
    return notes


def detect(observations: dict[str, Any]) -> dict[str, Any]:
    """Run every detector that has enough input, return goal candidates.

    ``observations`` (all keys optional; each detector uses only what it
    needs):

    - ``frame``: the current/first frame. Drives ``arrival``,
      ``uniformity``, ``containment``, ``pattern_match`` (all zero-action,
      single-frame).
    - ``background``: explicit background colour override; defaults to the
      frame's mode colour.
    - ``before`` / ``after``: a material-transition frame pair. Drives
      ``elimination``.
    - ``action_repeat_frames``: a short (>=3) sequence of frames observed
      under one repeated action. Drives ``threshold``.

    Returns ``{"goal_candidates": [...], "unresolved_tests": [...],
    "insufficient_evidence": bool, "evidence_detail": {...}}``.
    ``evidence_detail`` is HARNESS-ONLY bookkeeping (which region/frame each
    evidence handle points at) — call :func:`compact_view` on the result
    before injecting it into a model turn; the verdict's own example output
    shape (§4) has no such field.

    Per verdict §4: "goal type and mechanic intent must remain separate" —
    this function never mentions or selects a playbook/intent name, only a
    win-condition TYPE. Each detector fires at most once per call and the
    six detector types are mutually distinct by construction, so
    ``insufficient_evidence`` is simply "fewer than two candidates fired"
    (see the two-hypotheses-or-insufficient-evidence rule, verdict §4).
    """
    ledger = _Ledger()
    candidates: list[dict[str, Any]] = []

    frame = observations.get("frame")
    if frame is not None:
        background = observations.get("background")
        bg = background if background is not None else _mode_color(frame)
        regions = find_regions(frame, background=bg)
        relations = region_relations(regions)
        containers = _containers_map(relations)

        arrival = _detect_arrival(regions, ledger)
        uniformity = _detect_uniformity(regions, ledger)
        containment = _detect_containment(regions, containers, ledger)
        pattern_match = _detect_pattern_match(regions, containers, ledger)

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
        elimination = _detect_elimination(before, after, observations.get("background"), ledger)
        if elimination is not None:
            candidates.append(elimination)

    repeats = observations.get("action_repeat_frames")
    if repeats:
        threshold = _detect_threshold(repeats, ledger)
        if threshold is not None:
            candidates.append(threshold)

    # insufficient_evidence reflects the TRUE evidence found, before capping
    # (capping is an injection-size concern, not an evidence-strength one).
    insufficient_evidence = len(candidates) < 2
    capped = candidates[:MAX_CANDIDATES]
    # unresolved_tests is built from the CAPPED list so every id it cites is
    # guaranteed to actually appear in the returned goal_candidates.
    return {
        "goal_candidates": capped,
        "unresolved_tests": _build_unresolved(capped)[:MAX_UNRESOLVED],
        "insufficient_evidence": insufficient_evidence,
        "evidence_detail": ledger.evidence_detail,
    }


def compact_view(result: dict[str, Any]) -> dict[str, Any]:
    """The injectable subset of :func:`detect`'s output — drops
    ``evidence_detail`` (harness-only), matching the verdict §4 example
    output shape exactly: ``{"goal_candidates", "unresolved_tests"}`` plus
    the ``insufficient_evidence`` flag this module adds (verdict: "Require
    either two distinct competing goal hypotheses or an explicit
    insufficient_evidence declaration"). ``"unknown"`` is not re-declared
    here — it is already always selectable at SELECT_INTENT
    (:attr:`admorphiq.explanation.protocol.ExplanationProtocol.allowed_intents`);
    a low/insufficient ledger is exactly the signal that should route a
    caller toward it, not a field this pure function needs to assert for
    itself.
    """
    return {k: v for k, v in result.items() if k != "evidence_detail"}
