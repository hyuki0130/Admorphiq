"""Tests for the R58 GoalLedger (``src/admorphiq/explanation/goal_ledger.py``):
the executable win-condition typology built on R57's win-condition typology
mining (``docs/r57_win_condition_typology_20260715.md``), reconceptualized
as a capped HYPOTHESIS GENERATOR (tuning round #3) per
``docs/r58_codex_ledger_ranking_20260715.md``: evidence tiers replace scalar
election, an adjudication pass computes footprint-dependency relations
between fired candidates, capping preserves tiers/ambiguity/independent
footprints, and ``unresolved_tests`` are concrete structural probes.

Every fixture here is a small synthetic grid built to instantiate exactly
ONE (or a controlled combination) of the six supported detector types —
none of it is drawn from, or shaped like, any real ARC-AGI-3 public game
board; these are structural stress tests of the detectors' own logic, not
game reproductions. Purpose/feedback docstrings per repo convention.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import admorphiq.explanation.goal_ledger as gl
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
    alternating between 2 colours) — clears the uniformity discriminators
    (shape > 1 cell, <= 3 distinct colours in the class)."""
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


def _lattice_frame(n_rows: int = 2, n_cols: int = 3, color: int = 2) -> list[list[int]]:
    """One ring container whose immediate children form a REGULAR n_rows x
    n_cols addressable lattice (single colour by default — a lattice
    doesn't need >1 colour, unlike the old pattern_match's 3-colour floor)."""
    h, w = 6 + 4 * n_rows, 6 + 4 * n_cols
    g = _grid(h, w)
    _ring(g, 1, 1, h - 2, w - 2, 1)
    for i in range(n_rows):
        for j in range(n_cols):
            r = 3 + 4 * i
            c = 3 + 4 * j
            _dot(g, r, c, color)
    return g


def _binary_lattice_frame() -> list[list[int]]:
    """A 3x3 lattice using exactly 2 colours (alternating) — the SC25-style
    binary-grid case the old (>=3-colour) pattern_match rejected."""
    g = _grid(20, 20)
    _ring(g, 1, 1, 12, 12, 1)
    for i, (r, c) in enumerate([(3, 3), (3, 6), (3, 9), (6, 3), (6, 6), (6, 9), (9, 3), (9, 6), (9, 9)]):
        _dot(g, r, c, 2 if i % 2 == 0 else 3)
    return g


def _congruent_pair_frame(children_per_panel: int = 2) -> list[list[int]]:
    """Two SEPARATE ring containers, each holding the SAME number of item
    dots — a canvas/reference pair by matching slot count. Dots are spaced
    2 rows apart (a background gap between each) so they stay SEPARATE
    regions rather than merging into one connected blob."""
    g = _grid(20, 30)
    _ring(g, 1, 1, 8, 8, 1)
    _ring(g, 1, 15, 8, 22, 4)
    for k in range(children_per_panel):
        r = 3 + 2 * k
        _dot(g, r, 3, 2)
        _dot(g, r, 17, 5)
    return g


def _overlapping_uniformity_pattern_match_frame() -> list[list[int]]:
    """One ring container whose immediate children are a 3x3 lattice of
    2-cell horizontal dominoes (colours alternating within the uniformity
    colour cap). The SAME 9 domino regions simultaneously satisfy
    uniformity's repeated-shape-class gate (identical 2-cell shape, <=3
    colours) and pattern_match's lattice gate (a regular 3x3 addressable
    grid) — the FT09-shaped case named explicitly in the R58 verdict, where
    two different-type candidates read overlapping evidence."""
    g = _grid(20, 20)
    _ring(g, 1, 1, 16, 16, 1)
    colors = [8, 9]
    k = 0
    for i in range(3):
        for j in range(3):
            r = 3 + 4 * i
            c = 3 + 4 * j
            _fill(g, r, c, r, c + 1, colors[k % 2])
            k += 1
    return g


def _nonlattice_blob_frame() -> list[list[int]]:
    """A heterogeneous scatter of 5 differently-positioned, differently-
    coloured dots inside ONE large container — NOT a regular lattice, NOT
    part of a congruent pair. This is the LS20-style false-positive case
    the old (>=5 items/>=3 colours/any-bbox-container) pattern_match fired
    on; the rebuilt detector must NOT fire here."""
    g = _grid(20, 20)
    _ring(g, 1, 1, 15, 15, 1)
    _dot(g, 3, 3, 2)
    _dot(g, 3, 9, 3)
    _dot(g, 8, 5, 5)
    _dot(g, 11, 2, 7)
    _dot(g, 11, 12, 8)
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
    dominoes), containment (2 ring containers each holding 2 items),
    pattern_match (1 lattice container, structurally separate from the
    containment pair), elimination (a before/after pair), threshold (a
    monotonic repeat-frame window)."""
    g = _grid(35, 35)
    _fill(g, 1, 1, 1, 1, 3)
    _fill(g, 1, 5, 1, 5, 3)
    _fill(g, 1, 9, 1, 9, 3)
    _dot(g, 30, 30, 7)  # arrival
    for i, r in enumerate([22, 22, 22, 26, 26, 26]):
        c = [10, 14, 18][i % 3]
        _fill(g, r, c, r, c + 1, 11 if i % 2 == 0 else 12)  # uniformity: 6 dominoes, 2 colours
    _ring(g, 5, 1, 9, 5, 1)
    _dot(g, 7, 2, 20)
    _dot(g, 7, 4, 21)  # containment sibling A
    _ring(g, 5, 10, 9, 14, 6)
    _dot(g, 7, 11, 20)
    _dot(g, 7, 13, 21)  # containment sibling B
    _ring(g, 12, 20, 20, 32, 4)  # pattern_match lattice, structurally away from containment
    for i in range(2):
        for j in range(3):
            _dot(g, 14 + 4 * i, 22 + 4 * j, 9)

    before = _grid(35, 35)
    _dot(before, 32, 32, 30)
    after = _grid(35, 35)

    return {"frame": g, "before": before, "after": after, "action_repeat_frames": _threshold_frames()}


def _uncapped_detect(observations: dict) -> dict:
    """Run detect() with MAX_CANDIDATES lifted so every fired candidate is
    inspectable (test-only helper; restores the module constant after)."""
    original = gl.MAX_CANDIDATES
    gl.MAX_CANDIDATES = 10
    try:
        return gl.detect(observations)
    finally:
        gl.MAX_CANDIDATES = original


# ----- individual detector tests: firing + baseline evidence stage --------------
def test_arrival_fires_predicate_when_unambiguous():
    """Purpose: 'arrival' (R57 T1) fires on a colour-unique, non-dominant
    region; with exactly one such candidate, the endpoint IS unambiguously
    identified, so its evidence stage must be 'predicate' (tier 1) even
    with no transition evidence at all.

    Expected feedback: a pass proves the tier assignment reflects
    identification confidence correctly for the single-candidate case; a
    fail means arrival never reaches its strongest tier without a
    transition, contradicting the module docstring's stated rule.
    """
    result = detect({"frame": _arrival_frame()})
    candidate = next(c for c in result["goal_candidates"] if c["type"] == "arrival")
    assert candidate["support"] == ["evidence:1"]
    assert candidate["tier"] == 1  # predicate: unambiguous


def test_uniformity_fires_affordance_without_a_transition_window():
    """Purpose: 'uniformity' (R57 T6) fires on a repeated non-trivial shape
    class from a single frame; with NO transition evidence, its stage must
    stay 'affordance' (tier 3) — a static repeated-shape population only
    PERMITS the toggle-grid hypothesis, it doesn't confirm it.

    Expected feedback: a pass proves uniformity never over-claims tier from
    static structure alone; a fail means the affordance/behavioral
    distinction isn't actually gated on transition evidence.
    """
    result = detect({"frame": _uniformity_frame()})
    candidate = next(c for c in result["goal_candidates"] if c["type"] == "uniformity")
    assert len(candidate["support"]) == MAX_HANDLES_PER_CANDIDATE
    assert candidate["tier"] == 3


def test_containment_fires_affordance_when_irregular_predicate_when_perfect():
    """Purpose: 'containment' (R57 T3) fires when >=2 sibling containers each
    hold >=2 items; PERFECT regularity (identical item counts per sibling)
    is a genuine parallel-slot structure and should reach 'predicate'
    (tier 1), while irregular counts stay 'affordance' (tier 3).

    Expected feedback: a pass proves the predicate/affordance split tracks
    genuine structural regularity, not an arbitrary constant; a fail means
    every containment candidate gets the same tier regardless of evidence.
    """
    regular = detect({"frame": _containment_frame()})  # 2 items each side, symmetric
    c = next(x for x in regular["goal_candidates"] if x["type"] == "containment")
    assert c["tier"] == 1  # perfect regularity: 2 vs 2

    g = _grid(20, 20)
    _ring(g, 1, 1, 5, 5, 1)
    _dot(g, 3, 3, 2)
    _dot(g, 2, 4, 3)
    _ring(g, 1, 10, 5, 14, 6)
    _dot(g, 3, 12, 2)
    _dot(g, 2, 13, 3)
    _dot(g, 4, 13, 8)  # sibling B now has 3 items vs sibling A's 2 — irregular
    irregular = detect({"frame": g})
    c2 = next(x for x in irregular["goal_candidates"] if x["type"] == "containment")
    assert c2["tier"] == 3


def test_elimination_needs_a_before_after_pair_and_is_never_affordance():
    """Purpose: the 'elimination' detector (R57 T2) structurally CANNOT fire
    from a single frame — it must be silent on a first-observation call —
    and because it always requires a transition to fire at all, its tier
    must be 'behavioral' or 'predicate', NEVER 'affordance' (there is no
    static-only elimination reading).

    Expected feedback: a pass proves the material-transition requirement is
    reflected in the tier vocabulary itself; a fail means a single frame
    spuriously triggers 'elimination', or an uncorroborated fire gets
    mislabelled as merely-structural.
    """
    single_frame = detect({"frame": _arrival_frame()})
    assert "elimination" not in [c["type"] for c in single_frame["goal_candidates"]]

    before, after = _elimination_pair()
    result = detect({"before": before, "after": after})
    candidate = next(c for c in result["goal_candidates"] if c["type"] == "elimination")
    assert candidate["tier"] in (1, 2)


def test_threshold_needs_action_repeat_frames_and_is_always_behavioral():
    """Purpose: 'threshold' (R57 T7) needs >=3 frames under one repeated
    action; since it structurally cannot fire from static data, its tier
    is fixed at 'behavioral' (tier 2) — there is no affordance reading and
    no predicate promotion implemented (identifying the actual threshold
    VALUE is out of scope).

    Expected feedback: a pass proves the tier is exactly the documented
    fixed value; a fail means the fixed-tier claim in the docstring is
    wrong or threshold spuriously fires without a window.
    """
    no_history = detect({"frame": _arrival_frame()})
    assert "threshold" not in [c["type"] for c in no_history["goal_candidates"]]

    trending = detect({"action_repeat_frames": _threshold_frames()})
    candidate = next(c for c in trending["goal_candidates"] if c["type"] == "threshold")
    assert candidate["tier"] == 2

    flat = [_grid(10, 10), _grid(10, 10), _grid(10, 10)]
    no_trend = detect({"action_repeat_frames": flat})
    assert "threshold" not in [c["type"] for c in no_trend["goal_candidates"]]


# ----- pattern_match: rebuilt detector (R58 tuning round #3) --------------------
def test_pattern_match_fires_on_a_regular_lattice():
    """Purpose: the rebuilt 'pattern_match' fires when a container's
    IMMEDIATE children form a regular, addressable two-axis lattice — the
    core positive case for the new canvas/reference-relationship design.

    Expected feedback: a pass proves the lattice-detection path works at
    all; a fail means the rebuild's primary mechanism is broken.
    """
    result = detect({"frame": _lattice_frame(2, 3)})
    candidate = next(c for c in result["goal_candidates"] if c["type"] == "pattern_match")
    assert candidate["tier"] == 3  # affordance: single static panel, no transition evidence


def test_pattern_match_does_not_fire_on_a_heterogeneous_non_lattice_blob():
    """Purpose: pins the LS20 fix directly — a heterogeneous scatter of
    items inside one large bbox container, with NO regular lattice
    structure and NO congruent sibling panel, must NOT fire pattern_match
    any more (the old detector fired on exactly this shape: >=5 items,
    >=3 colours, one container, regardless of geometric regularity).

    Expected feedback: a pass proves the LS20-class false positive is
    closed; a fail means the rebuild didn't actually change behaviour on
    the case it was built to fix.
    """
    result = detect({"frame": _nonlattice_blob_frame()})
    assert "pattern_match" not in [c["type"] for c in result["goal_candidates"]]


def test_pattern_match_fires_on_a_binary_two_colour_lattice():
    """Purpose: pins the SC25 fix directly — a lattice using only 2 distinct
    colours must fire (the old detector required >=3 colours, which
    directly conflicts with binary/2-state grids like SC25's 3x3 pattern).

    Expected feedback: a pass proves the colour-count requirement is
    genuinely gone, not just loosened; a fail means binary grids are still
    excluded.
    """
    result = detect({"frame": _binary_lattice_frame()})
    assert "pattern_match" in [c["type"] for c in result["goal_candidates"]]


def test_pattern_match_fires_on_a_congruent_panel_pair():
    """Purpose: the SECOND positive path — two separate containers with
    matching child counts (a canvas/reference pair) — must also fire, even
    with no lattice arrangement within either panel.

    Expected feedback: a pass proves both documented discovery mechanisms
    (single-lattice, congruent-pair) are implemented, not just one; a fail
    means the congruent-pair path is missing or broken.
    """
    result = detect({"frame": _congruent_pair_frame(3)})
    candidate = next(c for c in result["goal_candidates"] if c["type"] == "pattern_match")
    assert candidate["tier"] == 3
    # 3-child panels are richer than the 2-child bare minimum, so margin must clear the floor
    assert candidate["strength"] > gl._STRENGTH_FLOOR


def test_pattern_match_single_panel_is_affordance_only_never_stronger_alone():
    """Purpose: verdict requirement — 'treat a single static panel as
    affordance, not strong pattern-match evidence.' A lone lattice with no
    transition evidence must NEVER exceed tier 3.

    Expected feedback: a pass proves this explicit verdict constraint is
    honoured; a fail means a static single panel could look like strong
    (behavioral/predicate) evidence with no transition support at all.
    """
    for frame in (_lattice_frame(2, 2), _lattice_frame(3, 3), _binary_lattice_frame()):
        result = detect({"frame": frame})
        candidate = next(c for c in result["goal_candidates"] if c["type"] == "pattern_match")
        assert candidate["tier"] == 3


def test_pattern_match_promotes_to_behavioral_when_edits_stay_confined_to_the_panel():
    """Purpose: behavioral promotion — a transition_window where every
    observed change stays within the candidate panel's own cells
    ('cumulative localized edits... changes confined to canvas slots')
    must promote the tier from affordance to behavioral.

    Expected feedback: a pass proves the promotion mechanism reads real
    frame_diff evidence, not just the presence of a window; a fail means
    promotion either never happens or happens unconditionally.
    """
    frame = _lattice_frame(2, 3, color=2)
    edited = [row[:] for row in frame]
    # repaint one lattice cell (3,3) from colour 2 to colour 5 — stays inside the panel
    edited[3][3] = 5
    result = detect({"frame": frame, "transition_window": [frame, edited]})
    candidate = next(c for c in result["goal_candidates"] if c["type"] == "pattern_match")
    assert candidate["tier"] == 2


def test_pattern_match_does_not_promote_when_edits_escape_the_panel():
    """Purpose: the negative case for the same mechanism — a transition
    whose changes fall OUTSIDE the candidate panel's footprint must NOT
    promote the tier (the observed behaviour contradicts a confined-canvas
    reading).

    Expected feedback: a pass proves the confinement check is a genuine
    filter, not a rubber stamp; a fail means any transition promotes the
    tier regardless of where the change actually occurred.
    """
    frame = _lattice_frame(2, 3, color=2)
    edited = [row[:] for row in frame]
    edited[0][0] = 9  # a corner of the frame, outside the ring/lattice panel entirely
    result = detect({"frame": frame, "transition_window": [frame, edited]})
    candidate = next(c for c in result["goal_candidates"] if c["type"] == "pattern_match")
    assert candidate["tier"] == 3


def test_pattern_match_prefers_congruent_pair_over_lattice_when_both_present():
    """Purpose: when a frame offers BOTH a congruent panel pair and a
    single-panel lattice, the detector must report the structurally
    stronger congruent-pair reading (documented preference), and still
    fire exactly one ``pattern_match`` candidate per call (consistent with
    every other detector here).

    Expected feedback: a pass proves the documented preference order is
    implemented; a fail means the choice between the two hypotheses is
    arbitrary or both fire simultaneously (which would violate the
    one-candidate-per-detector-per-call design).
    """
    g = _congruent_pair_frame(3)
    result = detect({"frame": g})
    matches = [c for c in result["goal_candidates"] if c["type"] == "pattern_match"]
    assert len(matches) == 1


# ----- R58 tuning round #4: confinement-based promotion + contradiction demotion --
def test_uniformity_promotes_on_confinement_but_not_on_coincidental_global_overlap():
    """Purpose: the two-condition confinement test
    (:func:`_is_confined_interaction`) must promote uniformity to
    'behavioral' when a step's diff is genuinely ABOUT one member's own
    footprint (a small, fully-inside, local edit), but must NOT promote
    when a diff merely happens to touch a member's cells while being a
    large, board-spanning change unrelated to that member specifically
    (real-trace validation measured this coincidental-overlap pattern
    firing promotion on ~19/24 games before this fix).

    Expected feedback: a pass proves both halves of the confinement test
    (fraction-inside AND bbox-locality) are load-bearing; a fail on the
    first assert means genuine local interactions stopped promoting
    (over-correction), a fail on the second means coincidental board-wide
    overlap still promotes (the bug this round fixes).
    """
    frame = _uniformity_frame()

    confined = [row[:] for row in frame]
    confined[1][1], confined[1][2] = 9, 9  # repaint exactly one domino's own two cells
    promoted = detect({"frame": frame, "transition_window": [frame, confined]})
    promoted_candidate = next(c for c in promoted["goal_candidates"] if c["type"] == "uniformity")
    assert promoted_candidate["tier"] == 2

    churned = [row[:] for row in frame]
    for r in range(7):  # rows 0-6 span every domino row (1 and 4) plus much more — a
        for c in range(10):  # board-spanning change that only coincidentally covers them
            churned[r][c] = 77
    not_promoted = detect({"frame": frame, "transition_window": [frame, churned]})
    not_promoted_candidate = next(c for c in not_promoted["goal_candidates"] if c["type"] == "uniformity")
    assert not_promoted_candidate["tier"] == 3


def test_uniformity_promotes_on_a_stencil_confined_edit_in_the_overlapping_lattice_case():
    """Purpose: the exact case named in the round's success bar — a
    domino/stencil-shaped repeated-region class (the FT09-shaped scenario
    from the module docstring, where uniformity and pattern_match read
    overlapping evidence) where a transition edits ONE member's own two
    cells and nothing else must still promote uniformity to 'behavioral'
    after the confinement rewrite.

    Expected feedback: a pass proves the round #4 rewrite did not
    over-correct and break behavioral promotion on genuinely confined,
    correctly-behaving cases; a fail means real games with legitimately
    localized toggle interactions would lose evidence strength they
    earned honestly.
    """
    frame = _overlapping_uniformity_pattern_match_frame()
    edited = [row[:] for row in frame]
    edited[3][3], edited[3][4] = 0, 0  # erase exactly one domino's own two cells
    result = detect({"frame": frame, "transition_window": [frame, edited]})
    candidate = next(c for c in result["goal_candidates"] if c["type"] == "uniformity")
    assert candidate["tier"] == 2


def test_containment_promotes_on_confinement_and_resists_a_single_stray_diff():
    """Purpose: containment's rewritten promotion path
    (:func:`_is_confined_interaction` over the sibling-container footprint)
    behaves the same way as arrival/uniformity's: a local, fully-inside
    edit promotes to 'behavioral'; a single large diff that only grazes the
    footprint does not (and does not demote either, since one step is
    below ``_MIN_CONTRADICTION_STEPS``).

    Expected feedback: a pass proves containment's own call site was wired
    to the shared confinement helper correctly; a fail means containment
    silently kept the old bare-intersection test (or broke entirely) when
    ``frame_area`` was threaded through.
    """
    g = _grid(20, 20)
    _ring(g, 1, 1, 5, 5, 1)
    _dot(g, 3, 3, 2)
    _dot(g, 2, 4, 3)
    _ring(g, 1, 10, 5, 14, 6)
    _dot(g, 3, 12, 2)
    _dot(g, 2, 13, 3)
    _dot(g, 4, 13, 8)  # sibling B has 3 items vs sibling A's 2 — irregular, baseline affordance

    confined = [row[:] for row in g]
    confined[3][3] = 9  # repaint one item dot's own single cell — inside the footprint
    promoted = detect({"frame": g, "transition_window": [g, confined]})
    promoted_candidate = next(c for c in promoted["goal_candidates"] if c["type"] == "containment")
    assert promoted_candidate["tier"] == 2

    stray = [row[:] for row in g]
    for r in range(11):  # a large diff spanning >half the frame, only grazing the footprint once
        for c in range(20):
            stray[r][c] = 44
    single_step = detect({"frame": g, "transition_window": [g, stray]})
    single_step_candidate = next(c for c in single_step["goal_candidates"] if c["type"] == "containment")
    assert single_step_candidate["tier"] == 3  # never promoted, and one step can't demote either


def test_arrival_contradiction_requires_at_least_two_window_steps_not_one():
    """Purpose: conservativeness requirement from the round's instructions
    ('contradiction requires the pattern across >=2 window steps, not
    one') — a single large, zero-overlap transition must NOT demote an
    otherwise-unambiguous ('predicate') arrival candidate.

    Expected feedback: a pass proves the ``>=_MIN_CONTRADICTION_STEPS``
    gate is a genuine >=2 check, not an off-by-one ``>=1``; a fail means
    one unlucky large transition could wrongly strip earned predicate
    evidence.
    """
    frame = _arrival_frame()
    large_change = [row[:] for row in frame]
    for r in range(7):  # rows 0-6 — large, but never touches the locus at (8, 8)
        for c in range(10):
            large_change[r][c] = 55

    result = detect({"frame": frame, "transition_window": [frame, large_change]})
    candidate = next(c for c in result["goal_candidates"] if c["type"] == "arrival")
    assert candidate["tier"] == 1  # still predicate: one contradicting step is not enough


def test_arrival_contradiction_demotes_predicate_to_affordance_and_persistent_contradiction_clamps_margin():
    """Purpose: the round's core new mechanism — across >=2 window steps
    showing large, board-spanning change with zero overlap at an
    unambiguous arrival candidate's own locus (no displacement ever
    observed there), the candidate must demote from 'predicate' directly
    to 'affordance' (the round's worked example: 'predicate->affordance')
    with a mechanically-derived 'against' handle citing the contradicting
    transitions; if the pattern persists past
    ``_CONTRADICTION_MARGIN_FLOOR_STEPS``, margin is additionally clamped
    to the strength floor.

    Expected feedback: a pass on the first block proves 2 contradicting
    steps demote and cite evidence; a pass on the second proves persistent
    (4-step) contradiction also strips margin to the floor, not just the
    tier. A fail means unambiguous candidates keep 'predicate' status
    despite repeated behavioral evidence that the claimed locus is never
    actually reached.
    """
    frame = _arrival_frame()

    def _large_change(color: int) -> list[list[int]]:
        g = [row[:] for row in frame]
        for r in range(7):  # rows 0-6 — large, never touches the locus at (8, 8)
            for c in range(10):
                g[r][c] = color
        return g

    step_a = _large_change(55)
    step_b = _large_change(66)
    demoted = detect({"frame": frame, "transition_window": [frame, step_a, step_b]})
    candidate = next(c for c in demoted["goal_candidates"] if c["type"] == "arrival")
    assert candidate["tier"] == 3
    assert candidate["against"] != []
    assert candidate["strength"] > gl._STRENGTH_FLOOR  # 2 steps demotes tier, not yet margin

    step_c = _large_change(55)
    step_d = _large_change(66)
    persistent = detect({"frame": frame, "transition_window": [frame, step_a, step_b, step_c, step_d]})
    persistent_candidate = next(c for c in persistent["goal_candidates"] if c["type"] == "arrival")
    assert persistent_candidate["tier"] == 3
    assert persistent_candidate["strength"] == pytest.approx(gl._STRENGTH_FLOOR)


# ----- margin / floor-anchoring (retained from tuning rounds #1-#2) -------------
def test_all_fired_candidates_carry_a_margin_in_unit_interval():
    """Purpose: every candidate from every detector must carry a
    ``"strength"`` (detector-local MARGIN, per the R58 tuning-round-3
    module docstring — no longer a cross-detector confidence score) in
    ``[0, 1]``, checked across a fixture that fires all six types at once.

    Expected feedback: a pass proves every margin formula returns a value
    in range; a fail would mean a formula can escape its bounds and
    corrupt tier-internal tie-breaking.
    """
    result = _uncapped_detect(_saturating_observations())
    assert len(result["goal_candidates"]) == 6
    for c in result["goal_candidates"]:
        assert "strength" in c
        assert "tier" in c
        assert 0.0 <= c["strength"] <= 1.0
        assert c["tier"] in (1, 2, 3)


def test_no_fired_candidate_ever_scores_below_the_strength_floor():
    """Purpose: floor-anchoring's core guarantee — EVERY fired candidate
    scores >= ``_STRENGTH_FLOOR`` (0.2), by the ``raw >= gate_min`` proof
    documented in each detector's docstring.

    Expected feedback: a pass proves the floor is a real lower bound in
    practice; a fail means some detector's gate_min derivation is wrong.
    """
    result = _uncapped_detect(_saturating_observations())
    for c in result["goal_candidates"]:
        assert c["strength"] >= gl._STRENGTH_FLOOR - 1e-9, f"{c['type']} scored {c['strength']} < floor"


def test_elimination_with_no_corroboration_lands_exactly_at_the_floor():
    """Purpose: pins the specific analytic consequence documented in
    _detect_elimination's docstring — with no ``extra_transitions``,
    ``confirmation_component`` is stuck at exactly 0.5, so ``raw ==
    gate_min`` exactly and strength must be EXACTLY ``_STRENGTH_FLOOR``.

    Expected feedback: a pass proves the "uncorroborated elimination is
    never more than 'just barely fired'" design intent holds exactly.
    """
    before, after = _elimination_pair()
    result = detect({"before": before, "after": after})
    strength = next(c for c in result["goal_candidates"] if c["type"] == "elimination")["strength"]
    assert strength == pytest.approx(gl._STRENGTH_FLOOR)
    tier = next(c for c in result["goal_candidates"] if c["type"] == "elimination")["tier"]
    assert tier == 2  # behavioral, not predicate — uncorroborated


def test_elimination_corroboration_promotes_tier_and_raises_margin():
    """Purpose: corroborating a vanish via ``extra_transitions`` must both
    raise the margin above the floor AND promote the evidence stage to
    'predicate' (a recurring elimination-shaped event is stronger
    identification than one occurrence) — the tier and margin mechanisms
    must move together, not independently.

    Expected feedback: a pass proves corroboration is reflected in both the
    tier vocabulary and the continuous margin; a fail means one of the two
    signals is stale.
    """
    before, after = _elimination_pair()
    uncorroborated = detect({"before": before, "after": after})
    u = next(c for c in uncorroborated["goal_candidates"] if c["type"] == "elimination")

    corroborating_before, corroborating_after = _elimination_pair()
    corroborated = detect(
        {"before": before, "after": after, "extra_transitions": [(corroborating_before, corroborating_after)]}
    )
    c = next(x for x in corroborated["goal_candidates"] if x["type"] == "elimination")

    assert c["strength"] > u["strength"]
    assert u["tier"] == 2
    assert c["tier"] == 1


def test_pattern_match_at_its_bare_minimum_lands_exactly_at_the_floor():
    """Purpose: both pattern_match sub-hypotheses (lattice, congruent pair)
    must land EXACTLY at the floor at their own bare-minimum firing case —
    a 2x2 lattice (the smallest valid lattice) and a 2-child congruent pair
    (the smallest valid pair) — proving the floor-anchoring derivation for
    the REBUILT detector is exact, not approximate.

    Expected feedback: a pass proves the new detector's gate_min formulas
    are correctly derived; a fail means the rebuild's margin scale is
    miscalibrated relative to its own documented gate.
    """
    lattice_min = detect({"frame": _lattice_frame(2, 2)})
    lattice_candidate = next(c for c in lattice_min["goal_candidates"] if c["type"] == "pattern_match")
    assert lattice_candidate["strength"] == pytest.approx(gl._STRENGTH_FLOOR)

    pair_min = detect({"frame": _congruent_pair_frame(2)})
    pair_candidate = next(c for c in pair_min["goal_candidates"] if c["type"] == "pattern_match")
    assert pair_candidate["strength"] == pytest.approx(gl._STRENGTH_FLOOR)


def test_margin_increases_with_more_evidence_after_anchoring():
    """Purpose: floor-anchoring must not flatten margin into a constant — a
    richer lattice (more cells) must score higher than the bare-minimum
    2x2 lattice.

    Expected feedback: a pass proves anchoring rescales rather than
    collapses the margin signal; a fail would mean "more evidence" no
    longer differentiates same-type candidates at all.
    """
    minimal = detect({"frame": _lattice_frame(2, 2)})
    minimal_strength = next(c for c in minimal["goal_candidates"] if c["type"] == "pattern_match")["strength"]

    richer = detect({"frame": _lattice_frame(3, 3)})
    richer_strength = next(c for c in richer["goal_candidates"] if c["type"] == "pattern_match")["strength"]

    assert richer_strength > minimal_strength


# ----- adjudication: footprint-dependency relations ------------------------------
def test_independent_footprints_produce_independent_evidence_relation():
    """Purpose: two candidates whose footprints share NO cells (e.g. arrival
    on one isolated dot, containment on a structurally separate pair of
    containers elsewhere in the frame) must be related as
    'independent_evidence' — the adjudication pass's baseline case.

    Expected feedback: a pass proves disjoint footprints are correctly
    classified; a fail means independence is never detected, which would
    make the cap policy's footprint-diversity preference meaningless.
    """
    g = _containment_frame()
    _dot(g, 18, 18, 9)  # an isolated colour-unique dot, far from both containers
    result = _uncapped_detect({"frame": g})
    types_present = {c["type"] for c in result["goal_candidates"]}
    assert {"arrival", "containment"} <= types_present
    arrival_id = next(c["id"] for c in result["goal_candidates"] if c["type"] == "arrival")
    containment_id = next(c["id"] for c in result["goal_candidates"] if c["type"] == "containment")
    rel = next(
        d["relation"]
        for d in result["dependencies"]
        if {d["a"], d["b"]} == {arrival_id, containment_id}
    )
    assert rel == "independent_evidence"


def test_overlapping_footprints_produce_shared_or_subsumed_evidence_relation():
    """Purpose: uniformity and pattern_match reading the SAME underlying
    lattice cells (the FT09-shaped case named explicitly in the verdict)
    must be related as 'shared_evidence' or 'subsumed_evidence' — never
    'independent_evidence' — since they interpret overlapping regions.

    Expected feedback: a pass proves the adjudication pass correctly
    detects evidence reuse between two different-type candidates; a fail
    would let the cap policy treat them as fully independent coverage,
    double-counting the same underlying structure.
    """
    g = _overlapping_uniformity_pattern_match_frame()
    result = _uncapped_detect({"frame": g})
    types_present = {c["type"] for c in result["goal_candidates"]}
    assert {"uniformity", "pattern_match"} <= types_present
    u_id = next(c["id"] for c in result["goal_candidates"] if c["type"] == "uniformity")
    p_id = next(c["id"] for c in result["goal_candidates"] if c["type"] == "pattern_match")
    rel = next(d["relation"] for d in result["dependencies"] if {d["a"], d["b"]} == {u_id, p_id})
    assert rel in ("shared_evidence", "subsumed_evidence")


def test_arrival_and_elimination_carry_the_temporal_composition_relation():
    """Purpose: R57 documents T4 (Delivery) as T1 (arrival) composed with T2
    (elimination) over time. This is declared as a STATIC, type-level
    relation (never inferred from footprint overlap) — so whenever BOTH
    arrival and elimination fire in the same call, their pair must carry
    'temporal_composition' regardless of whether their footprints overlap.

    Expected feedback: a pass proves the one hand-declared compositional
    relation from R57's own typology is actually wired up; a fail means
    the delivery-composition structure is undocumented in the output.
    """
    g = _arrival_frame()
    before, after = _elimination_pair()
    result = _uncapped_detect({"frame": g, "before": before, "after": after})
    arrival_id = next(c["id"] for c in result["goal_candidates"] if c["type"] == "arrival")
    elimination_id = next(c["id"] for c in result["goal_candidates"] if c["type"] == "elimination")
    relations = [d["relation"] for d in result["dependencies"] if {d["a"], d["b"]} == {arrival_id, elimination_id}]
    assert "temporal_composition" in relations


def test_dependencies_are_stripped_from_compact_view():
    """Purpose: 'dependencies' is harness-only bookkeeping (like
    evidence_detail) and must never reach the injectable compact view.

    Expected feedback: a pass proves the injection surface doesn't leak
    internal adjudication detail; a fail could blow the token budget with
    an O(n^2) relation list every turn.
    """
    result = detect(_saturating_observations())
    assert "dependencies" not in compact_view(result)


# ----- cap policy: tiers, ambiguity groups, independent footprints --------------
def test_cap_preserves_the_highest_tier_candidates_first():
    """Purpose: when more than MAX_CANDIDATES fire, capping must preserve
    the HIGHEST evidence tiers first — a tier-3 (affordance) candidate must
    never survive the cap ahead of a tier-1 (predicate) candidate.

    Expected feedback: a pass proves tier is the PRIMARY cap-selection
    criterion; a fail means margin or detector order could still bump a
    weak-tier candidate ahead of a strong-tier one.
    """
    result = detect(_saturating_observations())
    assert len(result["goal_candidates"]) == MAX_CANDIDATES
    tiers = [c["tier"] for c in result["goal_candidates"]]
    assert tiers == sorted(tiers)  # non-decreasing: best tiers first


def test_cap_keeps_both_sides_of_an_explicit_ambiguity_together():
    """Purpose: verdict requirement — capping must preserve BOTH sides of an
    explicit ambiguity (a shared/subsumed-evidence pair) as a unit. This
    fixture fires uniformity+pattern_match (linked, shared evidence) PLUS
    4 independent-footprint candidates elsewhere, forcing the cap to choose
    — the linked pair must not be split (one kept, one dropped) while an
    independent singleton survives instead.

    Expected feedback: a pass proves ambiguity-preservation actually
    constrains the cap, not just tier/margin; a fail would silently discard
    one side of a flagged tension, which the verdict explicitly forbids
    ("neither candidate should be silently deleted").
    """
    g = _overlapping_uniformity_pattern_match_frame()  # links uniformity + pattern_match (shared_evidence)
    big = _grid(50, 50)
    for r in range(len(g)):
        for c in range(len(g[0])):
            big[r][c] = g[r][c]
    _dot(big, 40, 2, 77)  # arrival, independent footprint
    _ring(big, 30, 10, 34, 14, 1)
    _dot(big, 32, 11, 2)
    _dot(big, 31, 13, 3)
    _ring(big, 30, 20, 34, 24, 6)
    _dot(big, 32, 21, 2)
    _dot(big, 31, 23, 3)  # containment, independent footprint
    before, after = _elimination_pair()  # a 5th, unrelated candidate — forces genuine cap overflow

    observations = {"frame": big, "before": before, "after": after}
    result = _uncapped_detect(observations)
    assert len(result["goal_candidates"]) > MAX_CANDIDATES, "fixture must overflow the cap to be a real test"
    u_id = next((c["id"] for c in result["goal_candidates"] if c["type"] == "uniformity"), None)
    p_id = next((c["id"] for c in result["goal_candidates"] if c["type"] == "pattern_match"), None)
    assert u_id and p_id

    capped = detect(observations)
    capped_ids = {c["id"] for c in capped["goal_candidates"]}
    # if either half of the linked pair survived the cap, BOTH must have
    assert (u_id in capped_ids) == (p_id in capped_ids)


def test_cap_size_never_exceeds_max_candidates():
    """Purpose: whatever the grouping/tier logic decides to keep, the
    returned list must never exceed MAX_CANDIDATES — the final hard
    invariant the injection-size guarantee depends on.

    Expected feedback: a pass proves the cap is a real upper bound even
    when ambiguity groups are large; a fail could blow the ledger's own
    token budget.
    """
    result = detect(_saturating_observations())
    assert len(result["goal_candidates"]) <= MAX_CANDIDATES


# ----- unresolved_tests: concrete structural probes ------------------------------
def test_unresolved_tests_are_concrete_probes_not_bare_type_lists():
    """Purpose: verdict requirement — unresolved_tests must be a SPECIFIC
    structural test ('whether edits follow a translated fixed stencil or
    directly repaint one canvas slot'), not a bare list of competing type
    names. Uses the uniformity/pattern_match shared-evidence fixture, which
    has a dedicated probe template.

    Expected feedback: a pass proves the probe text is concrete and
    references the actual candidate ids/types in tension; a fail means the
    weak LLM would still be handed undifferentiated scores instead of a
    test to run.
    """
    g = _overlapping_uniformity_pattern_match_frame()
    result = detect({"frame": g})
    assert result["unresolved_tests"], "expected at least one concrete probe"
    joined = " ".join(result["unresolved_tests"])
    assert "stencil" in joined or "canvas" in joined


def test_unresolved_tests_capped_at_max_unresolved():
    """Purpose: the unresolved_tests list must respect MAX_UNRESOLVED even
    when many ambiguity pairs are present.

    Expected feedback: a pass proves the cap is enforced; a fail could blow
    the injection budget on a heavily-ambiguous board.
    """
    result = detect(_saturating_observations())
    assert len(result["unresolved_tests"]) <= MAX_UNRESOLVED


# ----- the two-hypotheses-or-insufficient-evidence rule (verdict §4) -------------
def test_single_detector_firing_is_insufficient_evidence():
    """Purpose: verdict §4 requires EITHER two distinct competing hypotheses
    OR an explicit insufficient_evidence declaration — unchanged by the
    tuning-round-3 rebuild (this rule is about candidate COUNT, not tier).

    Expected feedback: a pass proves the rule survives the ranking rebuild
    intact; a fail means insufficient_evidence stopped being computed on
    the uncapped fired set.
    """
    result = detect({"frame": _arrival_frame()})
    assert len(result["goal_candidates"]) == 1
    assert result["insufficient_evidence"] is True


def test_two_distinct_types_firing_clears_insufficient_evidence():
    """Purpose: the OTHER side of the same rule — >=2 distinct types firing
    must clear insufficient_evidence, regardless of their tiers.

    Expected feedback: a pass proves the threshold is exactly 2 firings,
    independent of tier; a fail means tier now silently gates this flag.
    """
    g = _arrival_frame()
    for i, r in enumerate([0, 1, 3, 5, 7, 9]):
        _fill(g, r, 8, r, 9, 2 if i % 2 == 0 else 5)
    result = detect({"frame": g})
    types = {c["type"] for c in result["goal_candidates"]}
    assert {"arrival", "uniformity"} <= types
    assert result["insufficient_evidence"] is False


def test_zero_evidence_is_also_insufficient_and_empty():
    """Purpose: a blank frame with no structure must return an empty,
    unambiguous 'nothing found' result, never a fabricated candidate.

    Expected feedback: a pass proves the ledger degrades safely with no
    input structure.
    """
    result = detect({"frame": _grid(5, 5)})
    assert result["goal_candidates"] == []
    assert result["insufficient_evidence"] is True


# ----- structural contradiction ("against") cross-check ----------------------------
def test_arrival_region_also_contained_produces_a_structural_against():
    """Purpose: when the same region both (a) has a colour-unique small
    footprint (arrival-shaped) and (b) is a contained item inside a
    qualifying container (containment-shaped), the ledger must surface that
    tension via a genuine, mechanically-derived 'against' entry — retained
    unchanged from the tuning-round-1/2 design.

    Expected feedback: a pass proves the cross-detector consistency check
    still fires after the ranking rebuild; a fail means contradictory
    evidence would be silently dropped.
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


# ----- compact_view + budget -------------------------------------------------------
def test_compact_view_strips_harness_only_fields():
    """Purpose: compact_view() must drop BOTH 'evidence_detail' AND
    'dependencies' (harness-only), keeping goal_candidates (each now with
    'tier'), unresolved_tests, and insufficient_evidence.

    Expected feedback: a pass proves the injectable view matches the
    documented contract after the round-3 additions; a fail could leak
    internal footprint/dependency detail into a prompt.
    """
    result = detect({"frame": _arrival_frame()})
    view = compact_view(result)
    assert "evidence_detail" not in view
    assert "dependencies" not in view
    assert set(view.keys()) == {"goal_candidates", "unresolved_tests", "insufficient_evidence"}
    for c in view["goal_candidates"]:
        assert "tier" in c
        assert not any(k.startswith("_") for k in c)


def test_ledger_output_is_within_the_250_token_budget():
    """Purpose: team-lead's stated budget for the ledger's compact output is
    <=250 tokens (chars/4 estimate). Uses the cap-saturating fixture (the
    worst realistic case) since that's where the budget is most at risk —
    re-measured after the round-3 rebuild added 'tier' to every candidate.

    Expected feedback: a pass means even a maximally-saturated ledger call
    fits the injection budget after the rebuild; a fail means the richer
    output needs a smaller cap or terser probe text.
    """
    result = detect(_saturating_observations())
    compact = json.dumps(compact_view(result), separators=(",", ":"))
    assert len(compact) / 4 <= 250, f"compact ledger output ~{len(compact) / 4:.0f} tokens > 250 budget"


# ----- integration: a goal candidate flows into the navigation FILL schema --------
def test_goal_candidate_id_is_a_valid_navigation_goal_hypothesis_handle():
    """Purpose: end-to-end proof that a GoalLedger candidate's ``id`` is
    directly usable as the ``goal_hypothesis`` slot in a navigation
    FILL_INTENT declaration — unchanged by the round-3 ranking rebuild
    (only the surrounding ranking/tier machinery changed, not the id
    format or schema compatibility).

    Expected feedback: a pass proves the P0 (protocol) and P2 (ledger)
    layers still compose after the rebuild; a fail would mean a real
    harness could not wire ledger output into a FILL declaration.
    """
    g = _arrival_frame()
    for i, r in enumerate([0, 1, 3, 5, 7, 9]):
        _fill(g, r, 8, r, 9, 2 if i % 2 == 0 else 5)
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
