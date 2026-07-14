"""Tests for the pure 1D/sequence kernels (gap windows, colour majority,
size-jump clustering, greedy token parse) (R56)."""

import pytest

from admorphiq.kernels import (
    cluster_widths,
    find_derivation,
    gap_windows,
    greedy_parse,
    size_clusters,
    window_majority_color,
)

# Two-row band with THREE two-colour content windows (fill+ink, neither
# colour alone would stay 4-connected across both rows) separated by
# gaps of different widths (2 and 3 background columns) -- the exact
# "single-colour connected components fragment a 2-colour cell" scenario
# that motivated this module (see parse.py's docstring). Row1 col3 is
# deliberately background (0) so window 1's "cells" must exclude it even
# though columns 2-4 all belong to the window's column SPAN.
_ROW0 = [0, 0, 5, 9, 5, 0, 0, 7, 9, 7, 0, 0, 0, 5, 9, 0, 0]
_ROW1 = [0, 0, 9, 0, 9, 0, 0, 9, 7, 9, 0, 0, 0, 9, 5, 0, 0]
_BAND = [_ROW0, _ROW1]


def test_gap_windows_segments_two_colour_content_correctly():
    """Purpose: a row-band with 2-colour (fill+ink) glyph-style content must
    segment into exactly its 3 true windows by background-only column runs
    -- NOT fragment into more windows the way single-colour connected-
    component segmentation would (a 2-colour block's own ink pixels need
    not be 4-connected). Also pins that "cells" excludes a background cell
    that falls WITHIN a window's column span (row1 col3).
    Expected feedback: failure means the has-content test or the cells
    filter is wrong, corrupting every downstream token extraction."""
    out = gap_windows(_BAND, background=0)
    windows = out["windows"]
    assert [(w["start"], w["end"]) for w in windows] == [(2, 5), (7, 10), (13, 15)]
    assert windows[0]["cells"] == frozenset({(0, 2), (0, 3), (0, 4), (1, 2), (1, 4)})
    assert windows[1]["cells"] == frozenset(
        {(0, 7), (0, 8), (0, 9), (1, 7), (1, 8), (1, 9)}
    )
    assert windows[2]["cells"] == frozenset({(0, 13), (0, 14), (1, 13), (1, 14)})


def test_gap_windows_gap_widths_between_consecutive_windows():
    """Purpose: the reported gap widths must be the exact background-only
    column counts strictly BETWEEN consecutive windows (2 then 3 here, by
    construction), with exactly len(windows)-1 entries.
    Expected feedback: failure means the gap-width arithmetic is off by
    one, or gaps are computed against the wrong pair of windows -- this
    directly feeds the rule-pair-vs-rule-boundary distinction the design
    doc's gap-width finding depends on."""
    out = gap_windows(_BAND, background=0)
    assert out["gaps"] == [2, 3]


def test_gap_windows_all_background_band_is_empty():
    """Purpose: a band with no content at all must return empty windows AND
    empty gaps, not raise or return a spurious single window.
    Expected feedback: failure means the in-window/out-of-window state
    machine mishandles the degenerate all-background case."""
    assert gap_windows([[0, 0, 0], [0, 0, 0]], background=0) == {"windows": [], "gaps": []}


def test_window_majority_color_tie_breaks_by_first_scan_order():
    """Purpose: when two colours are exactly tied for the most common count
    within a window, the one encountered FIRST in row-major scan order
    must win -- both for majority AND minority -- a fixed, reproducible
    rule rather than dict/set iteration luck.
    Expected feedback: failure means Counter.most_common()'s stability
    guarantee was broken by an intermediate re-ordering step, making tie
    resolution nondeterministic across equivalent runs."""
    band = [[9, 5, 5, 7, 7, 9], [9, 5, 5, 7, 7, 9]]
    window = {"start": 1, "end": 5}  # cols 1-4: 5,5,7,7 in both rows -- exact tie
    out = window_majority_color(band, window)
    assert out == {"majority": 5, "minority": 7, "counts": {5: 4, 7: 4}}


def test_window_majority_color_background_exclusion_can_leave_single_colour():
    """Purpose: excluding a background colour from the count can collapse a
    two-colour tie down to a single remaining colour -- minority must then
    be None (not some stale leftover value), proving the exclusion is
    applied BEFORE ranking, not after.
    Expected feedback: failure means background exclusion is applied too
    late (after minority is already picked) or not at all."""
    band = [[9, 5, 5, 7, 7, 9], [9, 5, 5, 7, 7, 9]]
    window = {"start": 1, "end": 5}
    out = window_majority_color(band, window, background=5)
    assert out == {"majority": 7, "minority": None, "counts": {7: 4}}


def test_cluster_widths_matches_size_clusters_on_the_same_fixture():
    """Purpose: regions.size_clusters now DELEGATES to cluster_widths --
    calling cluster_widths directly on the regions' own size list must
    produce the byte-identical clustering size_clusters returns (using the
    fixture already pinned by test_kernels_regions.py's own
    test_size_clusters_splits_at_ratio_jump, so this also proves the
    refactor didn't silently change size_clusters' observable behaviour).
    Expected feedback: failure means the delegation changed sort/tie-break
    behaviour, silently breaking every existing size_clusters caller."""
    regions = [
        {"size": 10},
        {"size": 50},
        {"size": 12},
        {"size": 55},
        {"size": 11},
        {"size": 48},
    ]
    widths = [r["size"] for r in regions]
    expected = [[0, 4, 2], [5, 1, 3]]
    assert cluster_widths(widths, ratio=1.5) == expected
    assert size_clusters(regions, ratio=1.5) == expected


def test_greedy_parse_first_matching_rule_wins_regardless_of_length():
    """Purpose: at a position where MULTIPLE rules' LHS match, greedy_parse
    must commit to whichever is FIRST in rule list order -- not the longest,
    not the "best" for eventual full coverage. Swapping the same two rules'
    order must swap which one wins, proving list order (not shape) decides.
    Expected feedback: failure means the match loop isn't scanning rules in
    strict list order, breaking the "no search, no backtracking" contract
    that distinguishes this from rewrite.find_derivation."""
    short_first = [(("a",), ("x",)), (("a", "a"), ("y",))]
    out = greedy_parse(("a", "a"), short_first)
    assert out == {
        "result": ("x", "x"),
        "steps": [
            {"rule": 0, "position": 0, "before": ("a",), "after": ("x",)},
            {"rule": 0, "position": 1, "before": ("a",), "after": ("x",)},
        ],
    }

    long_first = [(("a", "a"), ("y",)), (("a",), ("x",))]
    out2 = greedy_parse(("a", "a"), long_first)
    assert out2 == {
        "result": ("y",),
        "steps": [{"rule": 0, "position": 0, "before": ("a", "a"), "after": ("y",)}],
    }


def test_greedy_parse_fails_where_find_derivation_succeeds():
    """Purpose: prove greedy_parse and rewrite.find_derivation are
    genuinely different engines, not just different call signatures for the
    same search. Rule 0 ('a'->'x') greedily consumes the first 'a' in
    ('a','a','b'), leaving a lone 'b' no rule can ever cover -> greedy_parse
    must FAIL (None), even though rule 1 ('a','a','b'->'z') -- unreachable
    from position 0 once rule 0 already committed -- covers the ENTIRE
    input in one shot. find_derivation's branching search (which tries
    rule 1 as an alternative, not just rule 0's first match) finds exactly
    that derivation to target ('z',) at depth 1.
    Expected feedback: failure of the first assert means greedy_parse grew
    backtracking (violating its documented contract); failure of the
    second means find_derivation regressed on a case its own test suite
    doesn't otherwise cover (an all_matches branch at position 0 that is
    NOT the first-listed rule)."""
    tokens = ("a", "a", "b")
    rules = [(("a",), ("x",)), (("a", "a", "b"), ("z",))]
    assert greedy_parse(tokens, rules) is None
    proof = find_derivation(tokens, ("z",), rules, max_depth=1, strategy="all_matches")
    assert proof == [{"rule": 1, "positions": [0], "before": tokens, "after": ("z",)}]


def test_greedy_parse_rtl_scans_from_the_right_and_can_differ_from_ltr():
    """Purpose: direction="rtl" must genuinely change WHICH matches are made
    (not just relabel ltr's own steps) when the rule set is ambiguous, and
    must report "position" back in ORIGINAL (ltr) token coordinates so rtl
    and ltr results are directly comparable. Here the 2-token rule can only
    grab a pair of 'a's starting from wherever the scan begins: ltr grabs
    (0,1) then a lone 'a' at 2; rtl grabs (1,2) then a lone 'a' at 0 --
    genuinely different tilings, both correctly covering all 3 tokens.
    Expected feedback: failure means the reversed-rule construction or the
    position back-conversion math (n - rev_pos - lhs_len) is wrong."""
    tokens = ("a", "a", "a")
    rules = [(("a", "a"), ("P",)), (("a",), ("Q",))]

    ltr = greedy_parse(tokens, rules, direction="ltr")
    assert ltr == {
        "result": ("P", "Q"),
        "steps": [
            {"rule": 0, "position": 0, "before": ("a", "a"), "after": ("P",)},
            {"rule": 1, "position": 2, "before": ("a",), "after": ("Q",)},
        ],
    }

    rtl = greedy_parse(tokens, rules, direction="rtl")
    assert rtl == {
        "result": ("Q", "P"),
        "steps": [
            {"rule": 1, "position": 0, "before": ("a",), "after": ("Q",)},
            {"rule": 0, "position": 1, "before": ("a", "a"), "after": ("P",)},
        ],
    }


def test_greedy_parse_empty_tokens_trivially_succeeds():
    """Purpose: an empty token sequence has nothing to cover, so it must
    succeed trivially with an empty result and no steps -- regardless of
    what rules are supplied (even an empty rule list).
    Expected feedback: failure means the while-loop's termination condition
    doesn't handle n=0, either raising or misreporting failure."""
    assert greedy_parse((), [(("a",), ("x",))]) == {"result": (), "steps": []}


def test_greedy_parse_rejects_empty_lhs_rule():
    """Purpose: a rule with an empty LHS could never advance the scan
    position, which would make "first match wins" ill-defined at every
    position simultaneously (an empty LHS trivially "matches" everywhere)
    -- this must be rejected up front, mirroring rewrite.derive_rewrites'
    identical rejection.
    Expected feedback: failure means a degenerate rule silently produces an
    infinite loop or nonsensical zero-width steps instead of a clear error."""
    with pytest.raises(ValueError, match="empty LHS"):
        greedy_parse(("a",), [((), ("x",))])
