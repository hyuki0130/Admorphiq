"""Tests for the FT09 glyph-decode logic (R56/R57 gold-trace reverse-
engineering, 2026-07-15) — the ring/glyph discovery and target-prediction
functions in ``admorphiq.adapters25.ft09``. See that module's docstring for
the full mechanic writeup; these tests pin the DECODE RULE itself (colour0
ink -> the glyph's own center/marker colour, colour2 ink -> the ring's other
observed colour, click iff mismatched) against small synthetic boards built
to the same button/pitch/glyph shape measured on the real game, not the
real 64x64 trace (kept fast and hermetic; the real-trace exact-match
validation lives in the dev-time decode session's scratchpad scripts, not
in the committed suite).
"""

from __future__ import annotations

from admorphiq.adapters25.ft09 import (
    _decode_ring_mismatches,
    _discover_rings,
    _is_hud_row,
    _read_glyph_compass,
)

_BG = 5
_MARKER = 8
_OTHER = 9
_INK_MARKER = 0
_INK_OTHER = 2
_SIZE = 20

# A single ring: button size 3x3, pitch 6, glyph gap at the ring's own
# center (9, 9). Ink pattern (NW/N/NE/W/C/E/SW/S/SE): corners get ink 0
# (-> target = marker), edges get ink 2 (-> target = other).
_GLYPH_CENTER = (9, 9)
_RING_OFFSETS = {
    "NW": (-6, -6), "N": (-6, 0), "NE": (-6, 6),
    "W": (0, -6), "E": (0, 6),
    "SW": (6, -6), "S": (6, 0), "SE": (6, 6),
}
_INK_PATTERN = {
    "NW": _INK_MARKER, "N": _INK_OTHER, "NE": _INK_MARKER,
    "W": _INK_OTHER, "E": _INK_OTHER,
    "SW": _INK_MARKER, "S": _INK_OTHER, "SE": _INK_MARKER,
}
# The colour each compass position should read once solved (derived from
# the ink pattern above, mirroring _decode_ring_mismatches' own rule).
_SOLVED_COLOUR = {
    name: (_MARKER if ink == _INK_MARKER else _OTHER) for name, ink in _INK_PATTERN.items()
}


def _blank_grid(size: int = _SIZE, bg: int = _BG) -> list[list[int]]:
    return [[bg] * size for _ in range(size)]


def _stamp(grid: list[list[int]], r0: int, c0: int, size: int, colour: int) -> None:
    for r in range(r0, r0 + size):
        for c in range(c0, c0 + size):
            grid[r][c] = colour


def _build_ring_board(button_colours: dict[str, int]) -> tuple[tuple[int, ...], ...]:
    """A grid with one 3x3-glyph-gap ring, each button 3x3, at the geometry
    ``_RING_OFFSETS``/``_GLYPH_CENTER`` describe. ``button_colours`` maps
    compass name -> the colour to stamp that button with (test controls the
    board's current state; the glyph itself is always ``_INK_PATTERN``)."""
    grid = _blank_grid()
    gr, gc = _GLYPH_CENTER
    for name, ink in _INK_PATTERN.items():
        dr, dc = _RING_OFFSETS[name]
        r0, c0 = gr + dr, gc + dc
        _stamp(grid, r0, c0, 3, button_colours[name])
    # glyph: 3x3, one ink-coloured pixel per compass cell (cell size 1px
    # here since the glyph itself is only 3x3 -- tile_bbox splits it into
    # a 1px-per-cell 3x3 reading, same shape as the real 6x6/2px-per-cell
    # glyphs, just scaled down for a fast test).
    for name, ink in _INK_PATTERN.items():
        dr, dc = {
            "NW": (0, 0), "N": (0, 1), "NE": (0, 2),
            "W": (1, 0), "E": (1, 2),
            "SW": (2, 0), "S": (2, 1), "SE": (2, 2),
        }[name]
        grid[gr + dr][gc + dc] = ink
    grid[gr + 1][gc + 1] = _MARKER  # glyph center = this ring's marker colour
    return tuple(tuple(row) for row in grid)


def test_discover_rings_finds_the_one_ring_with_correct_geometry():
    """Purpose: _discover_rings must locate a ring purely from measured
    button size/pitch (no hardcoded coordinates) and report the right glyph
    bbox and all 8 compass-position button regions.
    Expected feedback: failure means the discovery geometry (button-size
    selection, pitch-as-mode inference, or compass-offset ring search) is
    broken -- nothing downstream (decode, click targeting) can work."""
    grid = _build_ring_board({name: _SOLVED_COLOUR[name] for name in _RING_OFFSETS})
    rings = _discover_rings(grid)
    assert len(rings) == 1
    ring = rings[0]
    assert ring["glyph_bbox"] == (9, 9, 11, 11)
    assert set(ring["ring_cells"]) == set(_RING_OFFSETS)
    assert ring["ring_cells"]["NW"]["bbox"][:2] == (3, 3)
    assert ring["ring_cells"]["SE"]["bbox"][:2] == (15, 15)


def test_read_glyph_compass_matches_the_stamped_ink_pattern():
    """Purpose: _read_glyph_compass must recover exactly the ink values
    (plus the center marker) that were stamped onto the glyph gap, via the
    generic tile_bbox kernel -- not an independent hand-rolled reading.
    Expected feedback: failure means tile_bbox composition or the glyph
    bbox computation in _discover_rings disagrees with where the ink
    pixels actually are."""
    grid = _build_ring_board({name: _SOLVED_COLOUR[name] for name in _RING_OFFSETS})
    rings = _discover_rings(grid)
    glyph = _read_glyph_compass(grid, rings[0]["glyph_bbox"])
    assert glyph["C"] == _MARKER
    for name, ink in _INK_PATTERN.items():
        assert glyph[name] == ink


def test_decode_ring_mismatches_pre_solved_ring_is_empty():
    """Purpose: a ring whose 8 cells already match their glyph-predicted
    colours must report ZERO mismatches -- the core "don't click what's
    already correct" behaviour, measured on 3 of L0's 4 real rings.
    Expected feedback: failure means the decode over- or under-detects on
    an already-solved board, which would make the adapter click cells it
    shouldn't (wasting the RHAE efficiency budget) or miss ones it should."""
    grid = _build_ring_board({name: _SOLVED_COLOUR[name] for name in _RING_OFFSETS})
    rings = _discover_rings(grid)
    mismatches = _decode_ring_mismatches(grid, rings[0])
    assert mismatches == []


def test_decode_ring_mismatches_uniform_other_colour_flags_exactly_the_marker_cells():
    """Purpose: a ring at a uniform "other" colour (mirrors L0's real Q_BR:
    all 8 cells start at colour9) must flag exactly the ink-0 (marker-
    target) compass positions as mismatched -- the exact shape of the gold-
    trace-verified L0 win condition (4 of 8 cells needed clicking, all and
    only the ones whose glyph predicted the marker colour).
    Expected feedback: failure means the ink0-vs-ink2 -> marker-vs-other
    mapping itself is wrong, the single most load-bearing rule in the
    decode."""
    grid = _build_ring_board({name: _OTHER for name in _RING_OFFSETS})
    rings = _discover_rings(grid)
    mismatches = _decode_ring_mismatches(grid, rings[0])

    # Translate each mismatched click-point back to its compass name by
    # bbox membership, then compare against the ink-0 (marker-target) names.
    matched_names = set()
    for name, cell in rings[0]["ring_cells"].items():
        r0, c0, r1, c1 = cell["bbox"]
        for pos, _target in mismatches:
            if r0 <= pos[0] <= r1 and c0 <= pos[1] <= c1:
                matched_names.add(name)
    expected_names = {name for name, ink in _INK_PATTERN.items() if ink == _INK_MARKER}
    assert matched_names == expected_names
    assert all(target == _MARKER for _pos, target in mismatches)


def test_decode_ring_mismatches_ambiguous_when_only_marker_colour_observed():
    """Purpose: if every button already shows the marker colour, there is
    no second observed colour to disambiguate ink-2's target against --
    the decode must return [] (nothing actionable) rather than guessing,
    per the module's documented "can't determine 'other'" contract.
    Expected feedback: failure means the adapter would invent a fabricated
    target colour instead of correctly declining to act."""
    grid = _build_ring_board({name: _MARKER for name in _RING_OFFSETS})
    rings = _discover_rings(grid)
    assert _decode_ring_mismatches(grid, rings[0]) == []


def test_is_hud_row_excludes_any_region_confined_to_the_last_row():
    """Purpose: a region CONFINED to the frame's last row (top and bottom of
    its bbox both equal the last row index) is HUD chrome regardless of its
    column span -- narrow OR full-width. A region that merely touches the
    last row while extending upward (a real candidate cell whose bbox
    happens to reach the bottom edge) must NOT be excluded.
    Expected feedback: failure means either HUD contamination leaks through
    (over-permissive) or real bottom-edge cells vanish (over-exclusive)."""
    grid = tuple(tuple(0 for _ in range(10)) for _ in range(10))
    assert _is_hud_row((9, 0, 9, 9), grid) is True
    assert _is_hud_row((9, 2, 9, 4), grid) is True
    assert _is_hud_row((0, 0, 9, 9), grid) is False


def test_no_rings_on_a_board_with_fewer_than_eight_same_sized_regions():
    """Purpose: _discover_rings must return [] (not raise, not hallucinate
    a partial ring) when the board has no candidate button-sized regions at
    all -- the signal the adapter uses to skip straight to the probe
    fallback for non-ring games/levels.
    Expected feedback: failure means a board with a handful of unrelated
    small regions gets misread as ring geometry."""
    grid = _blank_grid()
    _stamp(grid, 3, 3, 3, _MARKER)
    _stamp(grid, 3, 15, 3, _MARKER)
    grid = tuple(tuple(row) for row in grid)
    assert _discover_rings(grid) == []
