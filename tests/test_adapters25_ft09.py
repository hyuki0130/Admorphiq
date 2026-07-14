"""Tests for the FT09 glyph-decode logic (R56/R57/R58 gold-trace reverse-
engineering, 2026-07-15) — the ring/glyph discovery and constraint-
satisfaction functions in ``admorphiq.adapters25.ft09``. See that module's
docstring for the full mechanic writeup; these tests pin the DECODE RULE
itself (colour0 ink -> the covering glyph's marker colour REQUIRED equal,
colour2 ink -> REQUIRED different, colour3 ink -> no constraint, ALL
covering glyphs' constraints hold simultaneously) against small synthetic
boards built to the same button/pitch/glyph shape measured on the real
game, not the real 64x64 trace (kept fast and hermetic; the real-trace
exact-match validation lives in the dev-time decode session's scratchpad
scripts, not in the committed suite).
"""

from __future__ import annotations

from types import SimpleNamespace

from admorphiq.adapters25.ft09 import (
    _GLYPH_TRIGGER_BUDGET,
    Adapter,
    _collect_constraints,
    _discover_rings,
    _is_hud_row,
    _is_wholesale_change,
    _read_glyph_compass,
    _satisfies,
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


def test_collect_constraints_pre_solved_ring_has_no_unsatisfied_cells():
    """Purpose: a ring whose 8 cells already satisfy their glyph-derived
    equality/inequality constraints must report every cell as satisfied --
    the core "don't click what's already correct" behaviour, measured on 3
    of L0's 4 real rings.
    Expected feedback: failure means the decode over- or under-detects on
    an already-solved board, which would make the adapter click cells it
    shouldn't (wasting the RHAE efficiency budget) or miss ones it should."""
    grid = _build_ring_board({name: _SOLVED_COLOUR[name] for name in _RING_OFFSETS})
    rings = _discover_rings(grid)
    coverage = _collect_constraints(grid, rings)
    assert len(coverage) == 8
    for cell, constraints in coverage.values():
        current = grid[cell["bbox"][0]][cell["bbox"][1]]
        assert _satisfies(current, constraints)


def test_collect_constraints_uniform_other_colour_flags_exactly_the_equal_ink_cells():
    """Purpose: a ring at a uniform "other" colour (mirrors L0's real Q_BR:
    all 8 cells start at colour9) must leave exactly the ink-0 (equality)
    compass positions unsatisfied -- the exact shape of the gold-trace-
    verified L0 win condition (4 of 8 cells needed clicking, all and only
    the ones whose glyph required equality to the marker).
    Expected feedback: failure means the ink0(equal)-vs-ink2(not-equal)
    mapping itself is wrong, the single most load-bearing rule in the
    decode."""
    grid = _build_ring_board({name: _OTHER for name in _RING_OFFSETS})
    rings = _discover_rings(grid)
    coverage = _collect_constraints(grid, rings)

    unsatisfied_names = set()
    for name, cell in rings[0]["ring_cells"].items():
        key = (cell["bbox"][0], cell["bbox"][1])
        current = grid[cell["bbox"][0]][cell["bbox"][1]]
        if not _satisfies(current, coverage[key][1]):
            unsatisfied_names.add(name)
    expected_names = {name for name, ink in _INK_PATTERN.items() if ink == _INK_MARKER}
    assert unsatisfied_names == expected_names


def test_collect_constraints_ink3_means_no_constraint():
    """Purpose: an ink value other than 0 or 2 (measured: 3, marking a
    compass position with no real cell on a truncated ring) contributes NO
    constraint for that position -- any colour there is trivially
    satisfied.
    Expected feedback: failure means the adapter would either fabricate a
    spurious constraint for an unconstrained position or crash on the
    unrecognised ink value."""
    pattern = dict(_INK_PATTERN)
    pattern["E"] = 3  # override one compass position to the "no constraint" ink
    grid_list = [[_BG] * _SIZE for _ in range(_SIZE)]
    gr, gc = _GLYPH_CENTER
    for name, ink in pattern.items():
        dr, dc = _RING_OFFSETS[name]
        r0, c0 = gr + dr, gc + dc
        colour = _MARKER if ink == _INK_MARKER else (_OTHER if ink == _INK_OTHER else 7)
        _stamp(grid_list, r0, c0, 3, colour)
    for name, ink in pattern.items():
        dr, dc = {
            "NW": (0, 0), "N": (0, 1), "NE": (0, 2),
            "W": (1, 0), "E": (1, 2),
            "SW": (2, 0), "S": (2, 1), "SE": (2, 2),
        }[name]
        grid_list[gr + dr][gc + dc] = ink
    grid_list[gr + 1][gc + 1] = _MARKER
    grid = tuple(tuple(row) for row in grid_list)

    rings = _discover_rings(grid)
    coverage = _collect_constraints(grid, rings)
    e_cell = rings[0]["ring_cells"]["E"]
    e_key = (e_cell["bbox"][0], e_cell["bbox"][1])
    # E's colour is 7 (neither marker nor other) -- with ink3 (no
    # constraint), this must still count as satisfied.
    assert e_key not in coverage or _satisfies(7, coverage[e_key][1])


def test_collect_constraints_cell_covered_by_two_glyphs_needs_both_satisfied():
    """Purpose: when two rings' 8-neighbour reach overlaps at a shared cell
    (measured on the real L3 board -- glyphs can and do overlap 3-deep near
    ring boundaries, the exact scenario a coverage-scoping bug on this rule
    once caused a real falsification-replay failure), that cell's
    constraint set must be the UNION of both glyphs' requirements, and it
    is only satisfied when ALL of them hold at once.
    Expected feedback: failure means multi-glyph overlap silently drops one
    glyph's requirement, which is exactly the class of bug this test
    exists to catch."""
    # Two rings sharing one pitch, positioned so ring B's NW member is ring
    # A's E member (pitch 6, rings 12 apart on the shared axis).
    grid_list = [[_BG] * 40 for _ in range(40)]

    def stamp_ring(center, ink_pattern, marker, other):
        gr, gc = center
        for name, ink in ink_pattern.items():
            dr, dc = _RING_OFFSETS[name]
            r0, c0 = gr + dr, gc + dc
            colour = marker if ink == _INK_MARKER else other
            _stamp(grid_list, r0, c0, 3, colour)
        for name, ink in ink_pattern.items():
            ddr, ddc = {
                "NW": (0, 0), "N": (0, 1), "NE": (0, 2),
                "W": (1, 0), "E": (1, 2),
                "SW": (2, 0), "S": (2, 1), "SE": (2, 2),
            }[name]
            grid_list[gr + ddr][gc + ddc] = ink
        grid_list[gr + 1][gc + 1] = marker

    # ring A: shared cell is A's E position (offset (0, 6) from A's center,
    # so A's E button's own bbox top-left is (9+0, 9+6) = (9, 15)).
    ink_a = {**_INK_PATTERN, "E": _INK_OTHER}  # E must differ from A's marker (8)
    stamp_ring((9, 9), ink_a, marker=8, other=9)
    # ring B: centered so its NW member lands exactly on A's E button. NW's
    # offset is (-6, -6), so solving center + (-6,-6) = (9, 15) gives
    # center = (15, 21) -- and (15,21) - (9,9) = (6,12), an exact multiple
    # of the pitch (6) in both dimensions, so both rings sit on ONE shared
    # lattice (mirroring how the real game's overlapping glyphs are always
    # on a single consistent pitch, not independently-offset lattices).
    ink_b = {**_INK_PATTERN, "NW": _INK_MARKER}  # NW must equal B's marker (12)
    stamp_ring((15, 21), ink_b, marker=12, other=9)

    grid = tuple(tuple(row) for row in grid_list)
    rings = _discover_rings(grid)
    assert len(rings) == 2
    coverage = _collect_constraints(grid, rings)

    shared_key = (9, 15)
    assert shared_key in coverage
    constraints = coverage[shared_key][1]
    assert ("!=", 8) in constraints  # from ring A: E is ink2, marker 8
    assert ("==", 12) in constraints  # from ring B: NW is ink0, marker 12
    # Only a colour satisfying BOTH (here, 12) is a valid resting state.
    assert _satisfies(12, constraints)
    assert not _satisfies(9, constraints)  # differs from 8 but not ==12
    assert not _satisfies(8, constraints)  # equals the forbidden marker


def test_discover_rings_accepts_a_truncated_ring_with_a_legible_glyph():
    """Purpose: a ring missing some of its 8 compass members (measured on
    the real game: an edge-truncated ring near the frame boundary, here
    simulated by simply not placing some buttons) must still be
    discovered, with a PARTIAL ``ring_cells`` dict -- not silently dropped
    the way the original (pre-truncation-support) discovery required all 8.
    Expected feedback: failure means truncated rings (a real, measured
    board shape) are invisible to the decode, losing real click targets."""
    grid_list = [[_BG] * 60 for _ in range(30)]
    # Ring A: full 8-member ring (needed so button-sized regions >= 8, the
    # discovery threshold) at center (9, 9).
    gr, gc = 9, 9
    for name, ink in _INK_PATTERN.items():
        dr, dc = _RING_OFFSETS[name]
        r0, c0 = gr + dr, gc + dc
        _stamp(grid_list, r0, c0, 3, _SOLVED_COLOUR[name])
    for name, ink in _INK_PATTERN.items():
        ddr, ddc = {
            "NW": (0, 0), "N": (0, 1), "NE": (0, 2),
            "W": (1, 0), "E": (1, 2),
            "SW": (2, 0), "S": (2, 1), "SE": (2, 2),
        }[name]
        grid_list[gr + ddr][gc + ddc] = ink
    grid_list[gr + 1][gc + 1] = _MARKER

    # Ring B: TRUNCATED -- glyph present, but only 4 of its 8 members
    # placed (matching the measured floor: both real truncated rings found
    # on the live game had exactly 4 real members); the rest are left as
    # background. Far enough from ring A that no member position
    # accidentally coincides with A's.
    br, bc = 9, 45
    for name in ("W", "E", "N", "S"):
        dr, dc = _RING_OFFSETS[name]
        r0, c0 = br + dr, bc + dc
        _stamp(grid_list, r0, c0, 3, _OTHER)
    for name, ink in _INK_PATTERN.items():
        ddr, ddc = {
            "NW": (0, 0), "N": (0, 1), "NE": (0, 2),
            "W": (1, 0), "E": (1, 2),
            "SW": (2, 0), "S": (2, 1), "SE": (2, 2),
        }[name]
        grid_list[br + ddr][bc + ddc] = ink
    grid_list[br + 1][bc + 1] = _MARKER

    grid = tuple(tuple(row) for row in grid_list)
    rings = _discover_rings(grid)
    truncated = [r for r in rings if r["glyph_bbox"][:2] == (br, bc)]
    assert len(truncated) == 1
    assert set(truncated[0]["ring_cells"]) == {"W", "E", "N", "S"}


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


def test_is_wholesale_change_distinguishes_recolour_from_reveal():
    """Purpose: pin the exact distinction a trigger click's success check
    relies on -- recolouring existing regions in place (same bbox set,
    different colours) is NOT a reveal; replacing the region layout
    entirely (disjoint bbox set) IS. This is the fix for a measured real
    bug: a naive "did anything change" check treats an ordinary,
    always-effective field-cell toggle as trigger success forever.
    Expected feedback: failure means the trigger-click safety net can't
    tell a real decoy->reveal transition from routine board activity,
    reintroducing the infinite-loop defect this function exists to fix."""
    before = _build_ring_board({name: _SOLVED_COLOUR[name] for name in _RING_OFFSETS})
    # Recolour ONE button in place (same bbox, different colour) -- an
    # ordinary click's effect, not a reveal.
    before_list = [list(row) for row in before]
    _stamp(before_list, 3, 3, 3, _OTHER if _SOLVED_COLOUR["NW"] == _MARKER else _MARKER)
    recoloured = tuple(tuple(row) for row in before_list)
    assert _is_wholesale_change(before, recoloured) is False

    # A wholesale reveal: every region moves to entirely different bboxes.
    reveal_list = [[_BG] * _SIZE for _ in range(_SIZE)]
    _stamp(reveal_list, 0, 0, 3, _MARKER)
    _stamp(reveal_list, 0, 17, 3, _MARKER)
    reveal = tuple(tuple(row) for row in reveal_list)
    assert _is_wholesale_change(before, reveal) is True


def test_glyph_trigger_loop_abandons_glyph_phase_within_budget_when_no_reveal_ever_happens():
    """Purpose: regression pin for the measured infinite-loop bug -- on a
    board that is ALWAYS "nothing unsatisfied" (a persistent decoy) where
    clicking a candidate cell is ALWAYS visibly effective (it toggles its
    own colour) but NEVER reveals a new board layout, the adapter must
    abandon glyph-phase play within a small, bounded number of trigger
    attempts (_GLYPH_TRIGGER_BUDGET, on DISTINCT cells) rather than
    clicking the same cell forever. Directly reproduces the exact live
    scenario found on a real board this session (60+ identical clicks,
    zero contradictions, before the fix).
    Expected feedback: failure (test hangs or exceeds the step budget with
    phase still "glyph") means the trigger success check is, once again,
    treating "something visibly changed" as "the board was revealed"."""
    pristine = _build_ring_board({name: _SOLVED_COLOUR[name] for name in _RING_OFFSETS})

    def toggle_step(grid: tuple[tuple[int, ...], ...], x: int, y: int) -> tuple[tuple[int, ...], ...]:
        """Simulate one click: if (y, x) lands within a 3x3 button, toggle
        that ENTIRE button between marker/other IN PLACE (same region
        bboxes throughout -- never a reveal), mirroring a real board where
        a decoy click is always visibly effective but never structural."""
        grid_list = [list(row) for row in grid]
        for name, (dr, dc) in _RING_OFFSETS.items():
            gr, gc = _GLYPH_CENTER
            r0, c0 = gr + dr, gc + dc
            if r0 <= y <= r0 + 2 and c0 <= x <= c0 + 2:
                current = grid_list[r0][c0]
                new_colour = _OTHER if current == _MARKER else _MARKER
                for r in range(r0, r0 + 3):
                    for c in range(c0, c0 + 3):
                        grid_list[r][c] = new_colour
                break
        return tuple(tuple(row) for row in grid_list)

    def make_frame(grid: tuple[tuple[int, ...], ...]) -> SimpleNamespace:
        return SimpleNamespace(
            frame=[[list(row) for row in grid]],
            state=SimpleNamespace(name="NOT_FINISHED"),
            levels_completed=0,
        )

    adapter = Adapter()
    grid = pristine
    obs = make_frame(grid)
    max_steps = _GLYPH_TRIGGER_BUDGET * 3 + 10  # generous margin past the budget
    for _ in range(max_steps):
        if adapter._phase != "glyph":
            break
        action = adapter.choose_action([], obs)
        x, y = action.action_data.x, action.action_data.y
        grid = toggle_step(grid, x, y)
        obs = make_frame(grid)
    assert adapter._phase != "glyph", (
        "adapter stayed in glyph phase past the trigger budget -- the "
        "infinite-loop bug is back"
    )


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
