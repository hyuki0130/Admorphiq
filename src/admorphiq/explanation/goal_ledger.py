"""GoalLedger: the executable win-condition typology (R58 verdict §4).

Turns R57's win-condition typology mining
(``docs/r57_win_condition_typology_20260715.md``) into a set of cheap,
kernel-composed, PRE-CLEAR detectors — no level-up labels, no gold data,
no game identity, ever, at runtime. ``detect(observations)`` is a pure
function: it runs every detector that has enough input to fire, returns a
capped, compact set of competing goal candidates plus any unresolved
structural ambiguity, and is silent (an empty result) rather than
speculative when the evidence doesn't support a call.

**Evidence-strength scoring (R58 tuning round, 2026-07-15, real-trace
validation).** Every candidate carries a ``"strength"`` in ``[0, 1]``
computed ONLY from that detector's own structural evidence (never a
per-game constant) — candidates are sorted by strength descending, ties
broken by detector-execution order (Python's stable sort over the
fixed-order append list below does this for free). This was added after
validating the v1 (unscored) ledger against real early-trace frames for
all 24 R57-evidenced games: unscored, "the first detector that fired" was
a meaningless proxy for confidence (``elimination``/``threshold`` could
never rank first regardless of evidence quality, purely because they run
later in a fixed pipeline). Each detector's strength formula and its
rationale are documented in that detector's own docstring, below.
That validation pass also found two concrete over-firing patterns fixed
here as STRUCTURAL discriminators (never per-game constants):
``elimination`` firing on essentially any single early transition (almost
any action changes SOME region's exact signature somewhere on a real
board), and ``uniformity`` firing on decorative 1-cell texture noise
indistinguishable, under a naive same-shape count, from a real toggle
grid. See the per-detector docstrings for exactly what changed.

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
# package exists to avoid). ``_MAX_UNIFORM_SHAPE_COLORS`` is new in the R58
# tuning round (see :func:`_detect_uniformity`); everything else here is
# unchanged from v1 — this tuning round is strength scoring plus two named
# discriminators, NOT a general threshold sweep.
_MIN_UNIFORM_GRID_COUNT = 6
_MAX_UNIFORM_SHAPE_COLORS = 3
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


def _detect_arrival(regions: list[dict[str, Any]], frame_area: int, ledger: _Ledger) -> dict[str, Any] | None:
    """T1 Reach/Target-Coincidence -> ``arrival``. See module docstring.

    **R58 tuning round — size filter replaced.** v1 excluded any candidate
    ABOVE the median region size, meant to rule out one large dominant
    panel. Real-trace validation found this backfired: many real boards
    fragment their background into a large population of small decorative
    pieces, dragging the median size well below a genuine target/player
    sprite's size — the median filter then excluded the CORRECT target
    (measured directly: on one game the wiki's own winning strategy names
    the exact colour the ledger found and then discarded, purely because
    that region was above the median). Replaced with DOMINANCE exclusion:
    only a region covering more than half the frame is excluded; every
    other colour-unique region, regardless of its size relative to the
    population's median, is now a candidate. This still rules out "one
    huge dominant panel" (>50% of the board can't also be a small target
    marker) without penalizing an ordinary-or-larger-than-median sprite.

    **Strength** = ``uniqueness_sharpness * size_distinctness``:

    - ``uniqueness_sharpness = 1 / n_candidates`` — how many OTHER
      colour-unique, non-dominant regions exist in this same frame. Exactly
      one candidate is an unambiguous signal (sharpness 1.0); four tied
      candidates split the confidence four ways, since it's unclear which
      one is "the" marked locus.
    - ``size_distinctness = 1 - size / frame_area`` — smaller relative to
      the whole board reads as more marker-like (a player/goal sprite is
      usually a small fraction of the board; a large-but-still-unique-
      coloured region reads as weaker evidence, without being excluded
      outright the way the old median filter did).
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
    strength = uniqueness_sharpness * size_distinctness
    note = "region colour occurs nowhere else in the frame and does not dominate (>50%) the board"
    handle = ledger.evidence(idx, note)
    return {"id": ledger.candidate_id(), "type": "arrival", "support": [handle], "against": [], "strength": strength}


def _detect_uniformity(regions: list[dict[str, Any]], ledger: _Ledger) -> dict[str, Any] | None:
    """T6 Toggle-Parity -> ``uniformity``. See module docstring.

    **R58 tuning round — two discriminators added.** v1 picked whichever
    shape-signature class had the MOST members, with no check on what that
    shape actually was. Real-trace validation found this over-fires on
    decorative background texture: several games' single biggest
    same-shape class was a population of dozens to hundreds of TRIVIAL
    1x1-cell regions (a dithered/textured backdrop), which is
    indistinguishable under a naive "most members" rule from a genuine
    toggle grid. The one true-positive game's winning class was
    qualitatively different: a non-trivial multi-cell shape spanning only
    2 colours. Two hard discriminators now apply to EVERY candidate shape
    class, and classes are tried in population-descending order so a large
    disqualified (trivial) class no longer masks a smaller genuine one
    further down:

    1. the shape must span more than 1 cell (kills 1x1 decorative noise);
    2. the class's members must use ``<= _MAX_UNIFORM_SHAPE_COLORS``
       distinct colours (a coherent toggle grid alternates between a
       handful of states; a class spanning many unrelated colours reads as
       incidental co-occurrence, not one grid).

    Known accepted residual false positive (not fixed by this round):
    genuine repeated MULTI-cell tiling that isn't a toggle grid at all
    (e.g. maze wall tiles) still passes both discriminators — that needs a
    connectivity/legend-based discriminator this round does not add.

    **Strength** = ``population_frac * non_triviality * colour_fit``:

    - ``population_frac = len(members) / n_total_regions`` — scale-
      invariant fraction of the board's OWN region population in this
      class (works whether the board has 20 or 200 regions, no fixed
      count reference needed).
    - ``non_triviality = 1 - 1/shape_cell_count`` — saturates toward 1 as
      the repeated shape gets larger/more distinctive; a bare 2-cell shape
      (the minimum that clears discriminator 1) still scores modestly (0.5).
    - ``colour_fit = 1 - (n_colours - 1) / _MAX_UNIFORM_SHAPE_COLORS`` —
      reuses the SAME cap as discriminator 2 rather than a new constant: a
      single-colour class scores 1.0, a class right at the cap scores low
      but still positive.
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
        if len(sig) <= 1:
            continue  # trivial 1-cell shape — decorative texture, not a toggle grid
        colours = {regions[i]["color"] for i in members}
        if len(colours) > _MAX_UNIFORM_SHAPE_COLORS:
            continue  # too many colours for one coherent toggle-grid class
        population_frac = len(members) / n_total
        non_triviality = 1 - 1 / len(sig)
        colour_fit = 1 - (len(colours) - 1) / _MAX_UNIFORM_SHAPE_COLORS
        strength = population_frac * non_triviality * colour_fit
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
        }
    return None


def _detect_containment(
    regions: list[dict[str, Any]], containers: dict[int, list[int]], ledger: _Ledger
) -> dict[str, Any] | None:
    """T3 Assignment/Matching -> ``containment``. See module docstring.

    Firing criteria unchanged this round (not a target of the approved
    tuning fixes) — only strength scoring is new.

    **Strength** = ``sibling_component * regularity``:

    - ``sibling_component = 1 - 1/n_siblings`` — saturating in the sibling
      COUNT (2 siblings is the minimum that can fire at all, scoring 0.5;
      more corroborating siblings raise confidence toward 1).
    - ``regularity = 1 - stdev(item_counts) / mean(item_counts)`` (clamped
      to ``[0, 1]``) — a real slot-grid/pool structure holds roughly EQUAL
      item counts per sibling; wildly uneven counts read as an incidental
      bbox-containment match rather than a designed matching structure.
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
    strength = sibling_component * regularity
    sample = list(qualifying.items())[:MAX_HANDLES_PER_CANDIDATE]
    handles = [ledger.evidence(c, f"container region holds {len(items)} item regions") for c, items in sample]
    return {
        "id": ledger.candidate_id(),
        "type": "containment",
        "support": handles,
        "against": [],
        "strength": strength,
    }


def _detect_pattern_match(
    regions: list[dict[str, Any]], containers: dict[int, list[int]], ledger: _Ledger
) -> dict[str, Any] | None:
    """T5 Fill/Paint-to-Pattern -> ``pattern_match``. See module docstring.

    Firing criteria unchanged this round — only strength scoring is new.

    **Strength** = ``item_richness * colour_richness``, both saturating
    ``1 - 1/n`` forms (consistent with the other detectors' population-
    based components): more items, and more distinct colours among them,
    read as stronger evidence of a genuine heterogeneous painting canvas
    rather than an incidental few-item, few-colour coincidence.
    """
    heterogeneous = []
    for c, items in containers.items():
        colors = {regions[i]["color"] for i in items}
        if len(items) >= _MIN_PATTERN_MATCH_ITEMS and len(colors) >= _MIN_PATTERN_MATCH_DISTINCT_COLORS:
            heterogeneous.append((c, items, colors))
    if len(heterogeneous) != 1:
        return None
    c, items, colors = heterogeneous[0]
    item_richness = 1 - 1 / len(items)
    colour_richness = 1 - 1 / len(colors)
    strength = item_richness * colour_richness
    handle = ledger.evidence(
        c, f"container region holds {len(items)} item regions spanning {len(colors)} distinct colours"
    )
    return {
        "id": ledger.candidate_id(),
        "type": "pattern_match",
        "support": [handle],
        "against": [],
        "strength": strength,
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
    before/after PAIR (a material transition), not a single frame. See
    module docstring.

    **R58 tuning round — corroboration is now a strength PENALTY, not a
    firing gate.** v1 fired (and scored, once strength existed) off a
    SINGLE transition alone. Real-trace validation found this over-fires
    badly: on a real board, almost any single action changes some region's
    exact (colour, shape) signature somewhere, for reasons unrelated to the
    game's actual win condition (camera/layout redraws, cosmetic
    animation) — measured directly on two games where the "vanished"
    region the detector caught was NOT the door/box R57 identified as the
    real elimination event. This still FIRES off one transition (a
    harness's first-observation-adjacent call must keep working — this is
    a scoring change, not a new hard gate) but its strength is penalized
    unless corroborated by ``extra_transitions``: additional (before,
    after) pairs the caller supplies when a short window of history is
    available (e.g. a few early transitions already observed in normal
    play — still no level-up label, still pre-clear).

    **Strength** = ``size_component * signature_distinctness *
    confirmation_component``:

    - ``size_component`` — ``1 - |vanished_frac - median_frac| /
      max(vanished_frac, median_frac)`` where both fractions are of the
      SAME board's own frame area. Reads "how close is this vanish's size
      to a typical (median) region's size on this same board" — closer to
      typical scores higher than either a single-pixel blip or a
      whole-scene-sized reshuffle, using only this board's own population
      as the reference (no fixed size constant).
    - ``signature_distinctness = 1 / n_distinct_vanished_signatures`` — how
      many DIFFERENT ``(colour, shape)`` pairs vanished in the SAME
      transition; one clean vanish is unambiguous (1.0), a transition where
      many signatures vanish at once (a scene-wide reshuffle) is ambiguous
      about which one, if any, is the meaningful event.
    - ``confirmation_component = min(1, n_transitions_with_a_vanish / 2)`` —
      the corroboration penalty: exactly one available transition (no
      ``extra_transitions``) scores 0.5; two or more transitions
      independently showing SOME vanish event reach full confidence 1.0.
      Deliberately counts "a vanish recurred", not "the identical object
      vanished twice" — tracking one object's identity ACROSS transitions
      is exactly the harness-level correlation problem this ledger's own
      module docstring rules out of scope for the T4 (delivery) case.
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

    strength = size_component * signature_distinctness * confirmation_component
    handle = ledger.evidence(
        idx, "region present before the transition has no matching (colour, shape) after it", frame="before"
    )
    return {
        "id": ledger.candidate_id(),
        "type": "elimination",
        "support": [handle],
        "against": [],
        "strength": strength,
    }


def _detect_threshold(action_repeat_frames: Sequence[Frame], ledger: _Ledger) -> dict[str, Any] | None:
    """T7 Threshold/Repeated-Action-Count -> ``threshold``. Needs a short
    window of frames under one repeated action. See module docstring.

    Firing criteria unchanged this round — only strength scoring is new.

    **Strength** = ``run_length_component * magnitude_component``:

    - ``run_length_component = 1 - 1/n_diffs`` — a longer confirmed
      monotonic run is stronger evidence than the minimum 2-diff run that
      barely clears the firing gate.
    - ``magnitude_component = |diffs[-1] - diffs[0]| / max(diffs[-1],
      diffs[0], 1)`` — a trend that grows/shrinks by a large relative
      amount is a clearer signal than one that's technically monotonic but
      barely moves (e.g. 1 cell to 2 cells, still monotonic, weak evidence).
    """
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
    run_length_component = 1 - 1 / len(diffs)
    magnitude_component = abs(diffs[-1] - diffs[0]) / max(diffs[-1], diffs[0], 1)
    strength = run_length_component * magnitude_component
    handle = ledger.evidence(
        None, f"frame_diff cell count trends {direction} across {len(diffs)} repeats of one action", diffs=diffs
    )
    return {
        "id": ledger.candidate_id(),
        "type": "threshold",
        "support": [handle],
        "against": [],
        "strength": strength,
    }


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
    - ``extra_transitions``: optional additional ``(before, after)`` pairs
      (beyond the primary ``before``/``after``) — corroborating evidence
      for ``elimination``'s confirmation-strength component (R58 tuning
      round). Still pre-clear: just more early observed transitions, no
      level-up label.
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

    **Candidate ordering (R58 tuning round).** ``goal_candidates`` is sorted
    by ``"strength"`` descending before capping — each detector's strength
    formula is in its own docstring. Ties keep the original fixed
    detector-execution order (``arrival``, ``uniformity``, ``containment``,
    ``pattern_match``, ``elimination``, ``threshold``) via Python's stable
    sort. Before this round, the FIRST-FIRED candidate (an artifact of
    pipeline position, not evidence quality) stood in for "top pick" —
    validated against real traces to be a poor proxy, since ``elimination``
    and ``threshold`` could never rank first regardless of how strong their
    evidence was.
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
        frame_area = len(frame) * len(frame[0]) if frame and frame[0] else 0

        arrival = _detect_arrival(regions, frame_area, ledger)
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

    # Sort by strength descending; Python's stable sort preserves the fixed
    # append order above (arrival, uniformity, containment, pattern_match,
    # elimination, threshold) as the tie-break, per verdict §4/team-lead
    # ruling ("ties by detector order").
    candidates.sort(key=lambda c: -c["strength"])

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
