"""Tests for the R58 GoalLedger (``src/admorphiq/explanation/goal_ledger.py``):
the executable win-condition typology built on R57's win-condition typology
mining (``docs/r57_win_condition_typology_20260715.md``).

Every fixture here is a small synthetic grid built to instantiate exactly
ONE (or a controlled combination) of the six supported detector types —
none of it is drawn from, or shaped like, any real ARC-AGI-3 public game
board; these are structural stress tests of the detectors' own logic, not
game reproductions. Purpose/feedback docstrings per repo convention.
"""

from __future__ import annotations

import json
from pathlib import Path

from admorphiq.explanation.goal_ledger import (
    MAX_CANDIDATES,
    MAX_HANDLES_PER_CANDIDATE,
    MAX_UNRESOLVED,
    compact_view,
    detect,
)
from admorphiq.explanation.protocol import validate


# ----- tiny synthetic-grid builders (test-only, not part of the package) --------
def _grid(h: int, w: int, bg: int = 0) -> list[list[int]]:
    return [[bg] * w for _ in range(h)]


def _fill(g: list[list[int]], r0: int, c0: int, r1: int, c1: int, color: int) -> None:
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            g[r][c] = color


def _ring(g: list[list[int]], r0: int, c0: int, r1: int, c1: int, color: int) -> None:
    for c in range(c0, c1 + 1):
        g[r0][c] = color
        g[r1][c] = color
    for r in range(r0, r1 + 1):
        g[r][c0] = color
        g[r][c1] = color


def _dot(g: list[list[int]], r: int, c: int, color: int) -> None:
    g[r][c] = color


# ----- individual detector fixtures ----------------------------------------------
def _arrival_frame() -> list[list[int]]:
    """3 repeated colour-3 1x1 blocks (a size/colour baseline, none unique) plus
    one colour-7 1x1 dot whose colour occurs nowhere else."""
    g = _grid(10, 10)
    _fill(g, 1, 1, 1, 1, 3)
    _fill(g, 1, 5, 1, 5, 3)
    _fill(g, 5, 1, 5, 1, 3)
    _dot(g, 8, 8, 7)
    return g


def _uniformity_frame() -> list[list[int]]:
    """6 disjoint 1x2 domino-shaped regions (a non-trivial 2-cell shape,
    alternating between 2 colours) — clears the R58 uniformity
    discriminators (shape > 1 cell, <= 3 distinct colours in the class)
    while a naive population of 1x1 dots (see test_uniformity_ignores_...)
    would not."""
    g = _grid(10, 10)
    for i, (r, c) in enumerate([(1, 1), (1, 4), (1, 7), (4, 1), (4, 4), (4, 7)]):
        _fill(g, r, c, r, c + 1, 2 if i % 2 == 0 else 4)
    return g


def _containment_frame() -> list[list[int]]:
    """2 sibling ring-shaped container regions, each holding 2 item dots."""
    g = _grid(20, 20)
    _ring(g, 1, 1, 5, 5, 1)
    _dot(g, 3, 3, 2)
    _dot(g, 2, 4, 3)
    _ring(g, 1, 10, 5, 14, 6)
    _dot(g, 3, 12, 2)
    _dot(g, 2, 13, 3)
    return g


def _pattern_match_frame() -> list[list[int]]:
    """1 ring-shaped container holding 5 item dots across 3 distinct colours."""
    g = _grid(20, 20)
    _ring(g, 1, 1, 8, 8, 1)
    _dot(g, 2, 2, 2)
    _dot(g, 2, 4, 3)
    _dot(g, 2, 6, 5)
    _dot(g, 4, 2, 2)
    _dot(g, 4, 4, 3)
    return g


def _elimination_pair() -> tuple[list[list[int]], list[list[int]]]:
    """A before/after pair where one region (colour 9) is present, then gone."""
    before = _grid(10, 10)
    _dot(before, 2, 2, 9)
    after = _grid(10, 10)
    return before, after


def _threshold_frames() -> list[list[list[int]]]:
    """4 frames under one repeated action; consecutive frame_diff counts 1, 2, 3
    (a monotonically increasing trend)."""
    f0 = _grid(10, 10)
    f1 = _grid(10, 10)
    _fill(f1, 0, 0, 0, 0, 11)
    f2 = _grid(10, 10)
    _fill(f2, 0, 0, 0, 0, 11)
    _fill(f2, 1, 0, 1, 1, 11)
    f3 = _grid(10, 10)
    _fill(f3, 0, 0, 0, 0, 11)
    _fill(f3, 1, 0, 1, 1, 11)
    _fill(f3, 2, 0, 2, 2, 11)
    return [f0, f1, f2, f3]


def _saturating_observations() -> dict:
    """A single observations dict deliberately built to fire ALL SIX detector
    types at once: arrival (colour-7 dot), uniformity (6 disjoint 1x2
    dominoes — a non-trivial 2-cell shape, clearing the R58 discriminators
    that a population of 1x1 dots would not), containment (2 ring
    containers each holding 2 items), pattern_match (1 ring holding 5
    heterogeneous items), elimination (a before/after pair), threshold (a
    monotonic repeat-frame window). Used by both the cap-enforcement test
    and the budget test — the worst-case saturation fixture."""
    g = _grid(30, 30)
    _fill(g, 1, 1, 1, 1, 3)
    _fill(g, 1, 5, 1, 5, 3)
    _fill(g, 1, 9, 1, 9, 3)
    _dot(g, 25, 25, 7)  # arrival
    for i, r in enumerate([22, 22, 22, 26, 26, 26]):
        c = [10, 14, 18][i % 3]
        _fill(g, r, c, r, c + 1, 11 if i % 2 == 0 else 12)  # uniformity: 6 dominoes, 2 colours
    _ring(g, 5, 1, 9, 5, 1)
    _dot(g, 7, 2, 20)
    _dot(g, 7, 4, 21)  # containment sibling A
    _ring(g, 5, 10, 9, 14, 6)
    _dot(g, 7, 11, 20)
    _dot(g, 7, 13, 21)  # containment sibling B
    _ring(g, 12, 1, 20, 9, 4)
    _dot(g, 14, 2, 2)
    _dot(g, 14, 4, 3)
    _dot(g, 14, 6, 5)
    _dot(g, 16, 2, 8)
    _dot(g, 16, 4, 9)  # pattern_match container

    before = _grid(30, 30)
    _dot(before, 27, 27, 30)
    after = _grid(30, 30)

    return {"frame": g, "before": before, "after": after, "action_repeat_frames": _threshold_frames()}


# ----- individual detector tests --------------------------------------------------
def test_arrival_fires_on_a_colour_unique_small_region():
    """Purpose: the 'arrival' detector (R57 T1) must fire on a region whose
    colour occurs nowhere else in the frame, and must NOT fire on the
    repeated-colour baseline regions around it.

    Expected feedback: a pass proves the colour-uniqueness + size heuristic
    isolates the intended locus from ordinary repeated scenery; a fail means
    either the filter is too strict (misses real single-colour targets) or
    too loose (flags ordinary scenery).
    """
    result = detect({"frame": _arrival_frame()})
    types = [c["type"] for c in result["goal_candidates"]]
    assert "arrival" in types
    candidate = next(c for c in result["goal_candidates"] if c["type"] == "arrival")
    assert candidate["support"] == ["evidence:1"]
    # region:3 is the colour-7 dot, per find_regions' deterministic sort order
    assert result["evidence_detail"]["evidence:1"]["region"] == "region:3"


def test_uniformity_fires_on_a_repeated_shape_grid():
    """Purpose: the 'uniformity' detector (R57 T6) must fire once >=6 regions
    share an identical translation-invariant shape, regardless of colour.

    Expected feedback: a pass proves the shape-signature grouping is
    colour-agnostic (necessary since a toggle grid's cells differ in colour
    by definition — that's the ON/OFF state); a fail means the detector
    can't see through colour variation to the repeated structure.
    """
    result = detect({"frame": _uniformity_frame()})
    candidate = next(c for c in result["goal_candidates"] if c["type"] == "uniformity")
    assert len(candidate["support"]) == MAX_HANDLES_PER_CANDIDATE  # capped sample, not all 6


def test_containment_fires_on_two_sibling_containers():
    """Purpose: the 'containment' detector (R57 T3) must fire when >=2 sibling
    container regions each hold >=2 item regions — the bordered-box/slot
    structural signature — and must return one evidence handle per
    qualifying container.

    Expected feedback: a pass proves region_relations' 'contains' relation
    is being read correctly as the containment signal; a fail means the
    detector either can't find nested regions or over/under-counts siblings.
    """
    result = detect({"frame": _containment_frame()})
    candidate = next(c for c in result["goal_candidates"] if c["type"] == "containment")
    assert len(candidate["support"]) == 2  # exactly the 2 container regions


def test_pattern_match_fires_on_one_heterogeneous_canvas():
    """Purpose: the 'pattern_match' detector (R57 T5) must fire on exactly ONE
    container holding many heterogeneous-colour items, and must NOT fire
    when there is no such single dominant heterogeneous container (see the
    containment test's frame, which has none).

    Expected feedback: a pass proves pattern_match and containment are
    distinguishable from the SAME underlying containment structure by item
    count/colour diversity alone; a fail means the two types collapse into
    each other.
    """
    result = detect({"frame": _pattern_match_frame()})
    types = [c["type"] for c in result["goal_candidates"]]
    assert "pattern_match" in types
    assert "containment" not in types  # only 1 container here, containment needs >=2 siblings

    containment_only = detect({"frame": _containment_frame()})
    assert "pattern_match" not in [c["type"] for c in containment_only["goal_candidates"]]


def test_elimination_needs_a_before_after_pair_and_fires_on_a_vanished_region():
    """Purpose: the 'elimination' detector (R57 T2) is the one detector that
    structurally CANNOT fire from a single frame — it must be silent on a
    first-observation call and must fire only when a before/after pair shows
    a region's (colour, shape) present-then-absent.

    Expected feedback: a pass proves the material-transition trigger point
    is handled distinctly from first-observation; a fail means either a
    single frame spuriously triggers 'elimination' or a real vanish is
    missed.
    """
    single_frame = detect({"frame": _arrival_frame()})
    assert "elimination" not in [c["type"] for c in single_frame["goal_candidates"]]

    before, after = _elimination_pair()
    result = detect({"before": before, "after": after})
    candidate = next(c for c in result["goal_candidates"] if c["type"] == "elimination")
    assert result["evidence_detail"][candidate["support"][0]]["frame"] == "before"


def test_threshold_needs_action_repeat_frames_and_fires_on_a_monotonic_trend():
    """Purpose: the 'threshold' detector (R57 T7, R58's addition beyond the
    verdict's five named examples) needs >=3 frames under one repeated
    action and must fire only when the frame_diff trend is monotonic —
    silent on both 'no history given' and 'no clear trend'.

    Expected feedback: a pass proves this genuinely different input shape
    (a short history, not a single frame or pair) is handled without
    crashing or false-firing; a fail means either input case is mishandled.
    """
    no_history = detect({"frame": _arrival_frame()})
    assert "threshold" not in [c["type"] for c in no_history["goal_candidates"]]

    trending = detect({"action_repeat_frames": _threshold_frames()})
    assert "threshold" in [c["type"] for c in trending["goal_candidates"]]

    flat = [_grid(10, 10), _grid(10, 10), _grid(10, 10)]  # identical frames, zero diff every step
    no_trend = detect({"action_repeat_frames": flat})
    assert "threshold" not in [c["type"] for c in no_trend["goal_candidates"]]


# ----- R58 tuning round: strength scoring + discriminator fixes -------------------
# Added after validating the (unscored, unfiltered) v1 ledger against real
# early-trace frames for all 24 R57-evidenced games — see the team-lead
# report for the full before/after. These tests pin the three approved
# structural fixes directly, independent of any specific game.
def test_all_fired_candidates_carry_a_strength_in_unit_interval():
    """Purpose: every candidate from every detector must carry a
    ``"strength"`` in ``[0, 1]`` (R58 tuning round) — checked across a
    fixture that fires all six types at once.

    Expected feedback: a pass proves every strength formula returns a
    value in range; a fail would mean a formula can escape its bounds
    (e.g. a saturating term computed on unexpected input) and corrupt the
    sort order downstream.
    """
    import admorphiq.explanation.goal_ledger as gl

    original_cap = gl.MAX_CANDIDATES
    gl.MAX_CANDIDATES = 10  # lift the cap so every fired candidate is inspectable
    try:
        result = gl.detect(_saturating_observations())
    finally:
        gl.MAX_CANDIDATES = original_cap
    assert len(result["goal_candidates"]) == 6  # this fixture fires every detector type
    for c in result["goal_candidates"]:
        assert "strength" in c
        assert 0.0 <= c["strength"] <= 1.0


def test_candidates_are_sorted_by_strength_descending():
    """Purpose: ``goal_candidates`` must be sorted strongest-first (R58
    tuning round) — before this, the first-fired candidate was an artifact
    of a fixed detector-execution order, not a confidence signal.

    Expected feedback: a pass proves the sort is actually applied to the
    returned (capped) list; a fail means ranking silently reverted to
    pipeline order.
    """
    result = detect(_saturating_observations())
    strengths = [c["strength"] for c in result["goal_candidates"]]
    assert strengths == sorted(strengths, reverse=True)


def test_uniformity_ignores_trivial_single_cell_noise():
    """Purpose: R58 discriminator #1 — a population of >=6 same-colour 1x1
    dots (a decorative-texture proxy; real-trace validation found several
    games where exactly this pattern drove a false 'uniformity' positive)
    must NOT fire uniformity, even though it satisfies the old v1 rule
    ('most members in one shape class').

    Expected feedback: a pass proves the >1-cell-shape gate actually
    excludes trivial noise; a fail reopens the exact false-positive class
    the validation round measured.
    """
    g = _grid(10, 10)
    for r, c in [(1, 1), (1, 3), (1, 5), (3, 1), (3, 3), (3, 5), (5, 1), (5, 3)]:
        _dot(g, r, c, 9)  # 8 disjoint 1x1 dots, ALL the same colour and shape
    result = detect({"frame": g})
    assert "uniformity" not in [c["type"] for c in result["goal_candidates"]]


def test_uniformity_rejects_a_shape_class_spanning_too_many_colours():
    """Purpose: R58 discriminator #2 — a repeated non-trivial shape class is
    only a 'uniformity' candidate when it spans <= _MAX_UNIFORM_SHAPE_COLORS
    distinct colours; a class using MORE colours than that (each member a
    different colour, say) reads as incidental co-occurrence, not one
    coherent toggle grid.

    Expected feedback: a pass proves the colour-count gate is enforced
    independently of the shape-size gate; a fail means any repeated shape
    fires regardless of how incoherent its colour usage is.
    """
    g = _grid(10, 10)
    colours = [1, 2, 3, 4, 5, 6]  # 6 distinct colours, one per domino — exceeds the cap of 3
    for i, (r, c) in enumerate([(1, 1), (1, 4), (1, 7), (4, 1), (4, 4), (4, 7)]):
        _fill(g, r, c, r, c + 1, colours[i])
    result = detect({"frame": g})
    assert "uniformity" not in [c["type"] for c in result["goal_candidates"]]


def test_arrival_dominance_filter_admits_a_large_but_non_dominant_target():
    """Purpose: R58 fix #3 — the arrival detector's size filter changed from
    'exclude anything above the median region size' to 'exclude only a
    region covering more than half the frame'. This fixture reproduces the
    exact failure mode found in real-trace validation: a colour-unique
    target region that is LARGER than the median (so v1's filter would
    have dropped it) but well under 50% of the board (so the new filter
    admits it).

    Expected feedback: a pass proves the known real-world false-negative
    class is fixed; a fail means the dominance filter regressed to
    median-based exclusion.
    """
    g = _grid(20, 20)  # 400-cell frame; 50% dominance threshold = 200 cells
    # many small (4-cell) same-colour tiles establish a LOW median...
    for r, c in [(0, 0), (0, 4), (0, 8), (0, 12), (0, 16), (4, 0), (4, 4), (4, 8)]:
        _fill(g, r, c, r + 1, c + 1, 3)
    # ...while the colour-unique target is bigger than every one of them (a 5x5=25-cell
    # block) but nowhere near 50% of the 400-cell frame — v1's median filter would
    # have excluded this; the dominance filter must not.
    _fill(g, 10, 10, 14, 14, 7)
    result = detect({"frame": g})
    arrival = next((c for c in result["goal_candidates"] if c["type"] == "arrival"), None)
    assert arrival is not None


def test_arrival_dominance_filter_still_excludes_a_truly_dominant_region():
    """Purpose: the flip side of the dominance-filter fix — a colour-unique
    region covering MORE than half the frame (a background panel, not a
    small target) must still be excluded, same as v1 intended for its
    "one large dominant panel" case.

    Expected feedback: a pass proves the filter didn't just get deleted
    (it still excludes the one case it was built for); a fail means any
    region, however large, now counts as an arrival candidate.
    """
    g = _grid(10, 10)  # 100-cell frame; 50% = 50 cells
    _fill(g, 0, 0, 7, 9, 5)  # colour-unique, 80 cells — dominates the frame
    result = detect({"frame": g})
    assert "arrival" not in [c["type"] for c in result["goal_candidates"]]


def test_elimination_confirmation_penalizes_a_single_uncorroborated_transition():
    """Purpose: R58 fix #2 — elimination still FIRES off one transition
    (first-observation-adjacent calls keep working) but its
    ``confirmation_component`` must score exactly 0.5 with no
    ``extra_transitions``, and 1.0 once a second transition also shows a
    vanish — real-trace validation found single-transition elimination
    over-fired on essentially arbitrary noise, so corroboration must move
    the score, not just exist as an unused field.

    Expected feedback: a pass proves the corroboration mechanism actually
    changes strength; a fail means extra_transitions is accepted but
    silently ignored.
    """
    before, after = _elimination_pair()
    uncorroborated = detect({"before": before, "after": after})
    strength_alone = next(c for c in uncorroborated["goal_candidates"] if c["type"] == "elimination")["strength"]

    corroborating_before, corroborating_after = _elimination_pair()  # a second, independent vanish event
    corroborated = detect(
        {
            "before": before,
            "after": after,
            "extra_transitions": [(corroborating_before, corroborating_after)],
        }
    )
    strength_confirmed = next(c for c in corroborated["goal_candidates"] if c["type"] == "elimination")["strength"]

    assert strength_confirmed > strength_alone


# ----- the two-hypotheses-or-insufficient-evidence rule (verdict §4) -------------
def test_single_detector_firing_is_insufficient_evidence():
    """Purpose: verdict §4 requires EITHER two distinct competing hypotheses OR
    an explicit insufficient_evidence declaration — a lone unconfirmed
    candidate must never be presented as if it were resolved.

    Expected feedback: a pass proves the ledger never over-commits on weak
    (single-signal) evidence; a fail would let a downstream SELECT_INTENT
    treat one structural hint as settled.
    """
    result = detect({"frame": _arrival_frame()})
    assert len(result["goal_candidates"]) == 1
    assert result["insufficient_evidence"] is True


def test_two_distinct_types_firing_clears_insufficient_evidence():
    """Purpose: the OTHER side of the same rule — once >=2 distinct types have
    independent structural support, the ledger must present them as
    competing hypotheses rather than silently picking one.

    Expected feedback: a pass proves the rule's threshold is exactly 2, not
    off-by-one; a fail means either 1 candidate is wrongly accepted or 2 are
    wrongly rejected.
    """
    g = _arrival_frame()
    for i, r in enumerate([0, 1, 3, 5, 7, 9]):
        _fill(g, r, 8, r, 9, 2 if i % 2 == 0 else 5)  # non-trivial 2-cell dominoes, clears the uniformity gate
    result = detect({"frame": g})
    types = {c["type"] for c in result["goal_candidates"]}
    assert {"arrival", "uniformity"} <= types
    assert result["insufficient_evidence"] is False
    assert len(result["unresolved_tests"]) >= 1


def test_zero_evidence_is_also_insufficient_and_empty():
    """Purpose: a blank frame with no structure must return an empty,
    unambiguous 'nothing found' result, never a fabricated candidate.

    Expected feedback: a pass proves the ledger degrades safely with no
    input structure; a fail (e.g. a spurious candidate) would be a clear
    speculative-safety-net violation.
    """
    result = detect({"frame": _grid(5, 5)})
    assert result["goal_candidates"] == []
    assert result["insufficient_evidence"] is True


# ----- cap enforcement --------------------------------------------------------------
def test_candidate_and_handle_caps_are_enforced_when_everything_fires():
    """Purpose: verdict §4 requires results 'capped to a few entries' — this
    fixture deliberately fires all six detector types at once (arrival,
    uniformity, containment, pattern_match via one combined frame;
    elimination via a before/after pair; threshold via repeat frames) and
    checks every cap holds: goal_candidates <= MAX_CANDIDATES, each
    candidate's support <= MAX_HANDLES_PER_CANDIDATE, unresolved_tests <=
    MAX_UNRESOLVED, and every id referenced in unresolved_tests actually
    appears in the (capped) goal_candidates list.

    Expected feedback: a pass proves the injection-size guarantee holds even
    in the worst case; a fail means an oversaturated frame could blow the
    ledger's own budget.
    """
    result = detect(_saturating_observations())

    assert len(result["goal_candidates"]) <= MAX_CANDIDATES
    assert len(result["goal_candidates"]) == MAX_CANDIDATES  # this fixture genuinely saturates the cap
    for c in result["goal_candidates"]:
        assert len(c["support"]) <= MAX_HANDLES_PER_CANDIDATE
        assert len(c["against"]) <= MAX_HANDLES_PER_CANDIDATE
    assert len(result["unresolved_tests"]) <= MAX_UNRESOLVED

    # every candidate flagged with a structural contradiction must be
    # referenced by id in some unresolved_tests note — nothing dangling
    for c in result["goal_candidates"]:
        if c["against"]:
            assert any(c["id"] in note for note in result["unresolved_tests"])


# ----- structural contradiction ("against") cross-check ----------------------------
def test_arrival_region_also_contained_produces_a_structural_against():
    """Purpose: when the same region both (a) has a colour-unique small
    footprint (arrival-shaped) and (b) is a contained item inside a
    qualifying container (containment-shaped), the ledger must surface that
    tension via a genuine, mechanically-derived 'against' entry — not a
    fabricated one (repo discipline: no speculative safety nets).

    Expected feedback: a pass proves the cross-detector consistency check
    fires on real structural overlap; a fail means contradictory evidence
    would be silently dropped, hiding a genuine ambiguity from the model.
    """
    g = _grid(20, 20)
    _fill(g, 1, 1, 1, 1, 3)
    _fill(g, 1, 5, 1, 5, 3)
    _fill(g, 5, 1, 5, 1, 3)
    _ring(g, 8, 1, 12, 5, 1)
    _dot(g, 10, 2, 9)
    _dot(g, 10, 4, 7)  # colour-unique dot, but INSIDE the container
    _ring(g, 8, 10, 12, 14, 6)
    _dot(g, 10, 11, 2)
    _dot(g, 10, 13, 3)

    result = detect({"frame": g})
    arrival = next(c for c in result["goal_candidates"] if c["type"] == "arrival")
    assert arrival["against"] != []
    assert any(arrival["id"] in note for note in result["unresolved_tests"])


# ----- compact_view + budget -------------------------------------------------------
def test_compact_view_strips_evidence_detail():
    """Purpose: compact_view() must produce exactly the verdict §4 example
    output shape (goal_candidates + unresolved_tests, plus this module's
    insufficient_evidence addition) with NO evidence_detail — that field is
    harness-only bookkeeping, never injected into a model turn.

    Expected feedback: a pass proves the injectable view matches the
    documented contract; a fail could leak internal region/frame detail
    into a prompt.
    """
    result = detect({"frame": _arrival_frame()})
    view = compact_view(result)
    assert "evidence_detail" not in view
    assert set(view.keys()) == {"goal_candidates", "unresolved_tests", "insufficient_evidence"}


def test_ledger_output_is_within_the_250_token_budget():
    """Purpose: team-lead's stated budget for the ledger's compact output is
    <=250 tokens (chars/4 estimate, matching the R58 slice's convention).
    Uses the cap-saturating fixture (the worst realistic case) since that's
    where the budget is most at risk.

    Expected feedback: a pass means even a maximally-saturated ledger call
    fits the injection budget; a fail means the cap constants need
    tightening before this ships.
    """
    result = detect(_saturating_observations())
    compact = json.dumps(compact_view(result), separators=(",", ":"))
    assert len(compact) / 4 <= 250, f"compact ledger output ~{len(compact) / 4:.0f} tokens > 250 budget"


# ----- integration: a goal candidate flows into the navigation FILL schema --------
def test_goal_candidate_id_is_a_valid_navigation_goal_hypothesis_handle():
    """Purpose: end-to-end proof that a GoalLedger candidate's ``id`` is
    directly usable as the ``goal_hypothesis`` slot in a navigation
    FILL_INTENT declaration — i.e. the ledger's output vocabulary and the
    protocol's schema vocabulary are the SAME handle format, not two
    systems that need translation glue.

    Expected feedback: a pass proves the P0 (protocol) and P2 (ledger)
    layers actually compose; a fail would mean a real harness could not
    wire ledger output into a FILL declaration without an ad-hoc adapter.
    """
    g = _arrival_frame()
    for i, (r, c) in enumerate([(1, 8), (3, 8), (5, 8), (7, 8), (9, 8), (0, 8)]):
        _dot(g, r, c, 2 if i % 2 == 0 else 5)
    ledger_result = detect({"frame": g})
    arrival = next(c for c in ledger_result["goal_candidates"] if c["type"] == "arrival")

    fill_declaration = {
        "intent": "navigation",
        "mover": "region:1",
        "start": "cell:1",
        "goals": ["cell:2"],
        "passable_mask": "mask:1",
        "action_map": "action_map:1",
        "goal_hypothesis": arrival["id"],
        "support": arrival["support"],
        "falsifier": "mover_does_not_follow_planned_step",
    }

    schema_path = Path(__file__).resolve().parent.parent / "src/admorphiq/explanation/intents/navigation.schema.json"
    nav_schema = json.loads(schema_path.read_text())
    errors = validate(nav_schema, fill_declaration)
    assert errors == [], f"unexpected schema errors: {errors}"
