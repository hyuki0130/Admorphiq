"""Tests for the pure, frame-only pieces of the tr87 adapter (R56) --
band classification, lattice-based bar tokenization (the step-3 fix),
bracket-column detection, and the extract_rules -> greedy_parse chain.
Synthetic boards only; the real gold-trace validation (all three
captured levels, oracle token-for-token equality) lives in
scripts/_tr87_integration.py (throwaway) -- these tests pin the
ADAPTER's own composed pieces in isolation, fast and hermetic."""

from admorphiq.adapters25.tr87 import (
    classify_bands,
    detect_bracket_column,
    discover_background,
    discover_bands,
    extract_bar_tokens,
    extract_rules,
)
from admorphiq.kernels import greedy_parse

_FILL, _INK = 9, 5

# Four small 3x3 ink patterns with genuinely distinct shapes (different ink
# cell counts, or a corner vs. a center) -- guaranteed to stay distinct
# under C4 rotation, so a test comparing recovered signatures can't pass
# by accidental rotational collision.
_PATTERNS = {
    "P": [[_INK, _FILL, _FILL], [_FILL, _FILL, _FILL], [_FILL, _FILL, _FILL]],  # 1 corner dot
    "Q": [[_INK, _INK, _FILL], [_FILL, _FILL, _FILL], [_FILL, _FILL, _FILL]],  # 2-cell edge
    "R": [[_INK, _FILL, _FILL], [_INK, _FILL, _FILL], [_INK, _FILL, _FILL]],  # 3-cell column
    "S": [[_FILL, _FILL, _FILL], [_FILL, _INK, _FILL], [_FILL, _FILL, _FILL]],  # center dot
}


def _blank(h, w, bg=0):
    return [[bg for _ in range(w)] for _ in range(h)]


def _paint_pattern(grid, row0, col0, name):
    for dr, row in enumerate(_PATTERNS[name]):
        for dc, v in enumerate(row):
            grid[row0 + dr][col0 + dc] = v


def _paint_col(grid, row0, row1, col, color):
    for r in range(row0, row1 + 1):
        grid[r][col] = color


def test_classify_bands_finds_rule_bar_and_bracket_bands():
    """Purpose: on a synthetic board shaped like TR87's real one (3
    rule-table bands each with 4 column-runs and a [small, LARGE, small]
    gap shape, 2 tall bar bands, 1 short bracket band adjacent to bar2 --
    with a genuine BACKGROUND ROW SEPARATING bar2 from the bracket, so
    they don't merge into one occupied_runs band), classify_bands must
    correctly split all six components purely from row/column structure.
    Expected feedback: failure means either the rule-table gap-shape
    signature, the tall-vs-short band split, or the bracket-adjacency
    check (which must NOT require touching bands, only being within a
    few px) is wrong -- this is the adapter's entire level-shape gate,
    so a bug here means every level (supported or not) gets mis-routed."""
    w = 12
    grid = _blank(30, w, bg=0)

    def make_rule_band(row0):
        for col in (0, 2, 6, 8):
            _paint_col(grid, row0, row0 + 3, col, 7)

    make_rule_band(0)
    make_rule_band(5)
    make_rule_band(10)
    for r in range(15, 19):
        for c in range(2, 10):
            grid[r][c] = 5
    for r in range(20, 24):
        for c in range(2, 10):
            grid[r][c] = 6
    # row 24 is a genuine background separator; bracket starts at 25
    _paint_col(grid, 25, 26, 5, 3)

    grid_t = tuple(tuple(row) for row in grid)
    bg = discover_background(grid_t)
    bands = discover_bands(grid_t, bg)
    result = classify_bands(grid_t, bands, bg)
    assert result is not None
    rule_bands, bar1_band, bar2_band, bracket_band = result
    assert [(b["start"], b["end"]) for b in rule_bands] == [(0, 4), (5, 9), (10, 14)]
    assert (bar1_band["start"], bar1_band["end"]) == (15, 19)
    assert (bar2_band["start"], bar2_band["end"]) == (20, 24)
    assert (bracket_band["start"], bracket_band["end"]) == (25, 27)


def test_extract_bar_tokens_lattice_survives_internal_background_gap():
    """Purpose: the step-3 fix itself -- a bar with TWO glyphs at a known
    pitch, where the SECOND glyph has a column that is entirely fill
    colour (no ink anywhere in that column across every row), the exact
    shape that fragmented TR87's real bar1 C4 glyph and bar2 generally
    under the old occupied_runs-based segmentation. The lattice split
    must still recover exactly 2 tokens (not 3, not a wrong boundary),
    each matching a DIRECT manual slice-and-canonicalize of its own
    pitch-width window.
    Expected feedback: failure means the lattice split is landing at the
    wrong column boundaries or is still deferring to background-gap
    detection somewhere -- a regression back to the exact bug this
    kernel composition was built to fix."""
    rows = [
        [_INK, _FILL, _FILL, _INK, _FILL, _FILL],
        [_FILL, _INK, _FILL, _FILL, _FILL, _FILL],
        [_FILL, _FILL, _INK, _FILL, _FILL, _INK],
    ]
    grid = tuple(tuple(row) for row in rows)
    bg = {0}
    band = {"start": 0, "end": 3}
    pitch = 3

    tokens = extract_bar_tokens(grid, band, bg, pitch)
    assert len(tokens) == 2
    assert tokens[0] != tokens[1]

    from admorphiq.adapters25.tr87 import canon_sig_c4

    def slice_mask(c0, c1):
        return tuple(tuple(grid[r][c] != _FILL for c in range(c0, c1)) for r in range(3))

    assert tokens[0] == canon_sig_c4(slice_mask(0, 3))
    assert tokens[1] == canon_sig_c4(slice_mask(3, 6))


def test_detect_bracket_column_maps_ink_to_the_right_slot():
    """Purpose: a bracket band whose own ink is concentrated over ONE of
    three known column-slot bounds must report that slot's index -- the
    adapter's only way to know which bar2 column is currently selected
    (the game's own bracket cursor is never assumed to start at a fixed
    index).
    Expected feedback: failure means the overlap-counting logic picks the
    wrong slot, which would make the dial executor edit the wrong column
    silently (no exception, just a wrong action plan)."""
    bg = {0}
    col_bounds = [(0, 3), (3, 6), (6, 9)]
    grid = (
        (0, 0, 0, 7, 7, 0, 0, 0, 0),
        (0, 0, 0, 0, 7, 0, 0, 0, 0),
    )
    idx = detect_bracket_column(grid, {"start": 0, "end": 2}, bg, col_bounds)
    assert idx == 1


def test_extract_rules_then_greedy_parse_derives_the_target():
    """Purpose: end-to-end on the pure (non-frame-discovery) half of the
    pipeline -- extract_rules recovers 2 one-token rules from a single
    rule-table band (4 runs, gap shape [1,3,1]), and feeding a bar1
    reading (two copies of rule0's own LHS token, lattice-extracted the
    SAME way bar1 always is) through greedy_parse against those rules
    must derive exactly [rule0's RHS, rule0's RHS] -- the actual
    "predict bar2's target" step the dial executor drives toward.
    Expected feedback: failure means either extract_rules' LHS|RHS
    grouping-before-splitting is wrong, or the token identities it
    produces don't round-trip through greedy_parse the way the real
    adapter's plan_bar2_target depends on."""
    # Wide margin of true board background is necessary here, not
    # cosmetic: with a narrow board, the glyphs' own FILL colour (a
    # majority within their small bounding boxes) can rival background's
    # own pixel count and get folded into discover_background's returned
    # set, corrupting occupied_runs' own background exclusion.
    w = 60
    grid = _blank(3, w, bg=0)
    positions = {"lhs0": ("P", 0), "rhs0": ("Q", 4), "lhs1": ("R", 10), "rhs1": ("S", 14)}
    for name, col in positions.values():
        _paint_pattern(grid, 0, col, name)
    grid_t = tuple(tuple(row) for row in grid)
    bg = discover_background(grid_t)

    result = extract_rules(grid_t, [{"start": 0, "end": 3}], bg)
    assert result is not None
    rules, pitch = result
    assert [(len(lhs), len(rhs)) for lhs, rhs in rules] == [(1, 1), (1, 1)]

    bar1_grid = _blank(3, 30, bg=0)
    _paint_pattern(bar1_grid, 0, 0, "P")
    _paint_pattern(bar1_grid, 0, 3, "P")
    bar1_tokens = extract_bar_tokens(tuple(tuple(r) for r in bar1_grid), {"start": 0, "end": 3}, {0}, pitch)
    assert bar1_tokens == [rules[0][0][0], rules[0][0][0]]

    greedy_rules = [(list(lhs), list(rhs)) for lhs, rhs in rules]
    parsed = greedy_parse(bar1_tokens, greedy_rules)
    assert parsed is not None
    assert list(parsed["result"]) == [rules[0][1][0], rules[0][1][0]]
