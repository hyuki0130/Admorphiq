"""Unit tests for R2 DiscoveryReport derivation helpers.

These tests cover the pure functions in `admorphiq.hypothesis.wiki_agent`
that turn raw probe frames into LLM-consumable features. No env required.
"""

from __future__ import annotations

import numpy as np
import pytest

from admorphiq.hypothesis.wiki_agent import (
    _connected_components,
    _derive_change_topology,
    _derive_click_responsive_cells,
    _derive_color_histogram,
    _derive_dir_map,
    _derive_movable_region_count,
    _derive_symmetry_score,
)


def _blank(size: int = 64) -> np.ndarray:
    return np.zeros((size, size), dtype=np.int32)


# ---------------------------------------------------------------------------
# _connected_components
# ---------------------------------------------------------------------------


def test_connected_components_empty():
    assert _connected_components(np.zeros((10, 10), dtype=bool)) == 0


def test_connected_components_single_blob():
    mask = np.zeros((10, 10), dtype=bool)
    mask[2:4, 2:4] = True  # 2x2 block, 1 component
    assert _connected_components(mask) == 1


def test_connected_components_two_disjoint():
    mask = np.zeros((10, 10), dtype=bool)
    mask[1, 1] = True
    mask[7, 7] = True
    assert _connected_components(mask) == 2


def test_connected_components_diagonal_not_connected():
    mask = np.zeros((10, 10), dtype=bool)
    mask[1, 1] = True
    mask[2, 2] = True  # diagonal = separate under 4-connectivity
    assert _connected_components(mask) == 2


# ---------------------------------------------------------------------------
# _derive_dir_map + player_color
# ---------------------------------------------------------------------------


def test_dir_map_north():
    before = _blank()
    before[32, 32] = 5
    after = _blank()
    after[28, 32] = 5  # moved up (row decreased)
    dir_map, player_color = _derive_dir_map({1: (before, after)})
    assert dir_map == {1: "N"}
    assert player_color == 5


def test_dir_map_south():
    before = _blank()
    before[32, 32] = 7
    after = _blank()
    after[36, 32] = 7
    dir_map, _ = _derive_dir_map({2: (before, after)})
    assert dir_map == {2: "S"}


def test_dir_map_east():
    before = _blank()
    before[32, 32] = 9
    after = _blank()
    after[32, 36] = 9
    dir_map, _ = _derive_dir_map({3: (before, after)})
    assert dir_map == {3: "E"}


def test_dir_map_west():
    before = _blank()
    before[32, 32] = 3
    after = _blank()
    after[32, 28] = 3
    dir_map, _ = _derive_dir_map({4: (before, after)})
    assert dir_map == {4: "W"}


def test_dir_map_no_motion_excluded():
    """Probes with zero diff or too-small diff (<1 px centroid shift) are skipped."""
    before = _blank()
    after = _blank()
    dir_map, player_color = _derive_dir_map({1: (before, after)})
    assert dir_map == {}
    assert player_color is None


def test_player_color_consistent_across_probes():
    """When the same color moves in every directional probe, it wins."""
    b1 = _blank(); b1[32, 32] = 5
    a1 = _blank(); a1[28, 32] = 5  # N
    b2 = _blank(); b2[32, 32] = 5
    a2 = _blank(); a2[36, 32] = 5  # S
    dir_map, player_color = _derive_dir_map({1: (b1, a1), 2: (b2, a2)})
    assert dir_map == {1: "N", 2: "S"}
    assert player_color == 5


# ---------------------------------------------------------------------------
# _derive_change_topology
# ---------------------------------------------------------------------------


def test_topology_no_change():
    before = _blank()
    after = _blank()
    assert _derive_change_topology({1: (before, after)}, 4096, {}) == "no_change"


def test_topology_level_transition():
    before = np.ones((64, 64), dtype=np.int32)
    after = np.full((64, 64), 7, dtype=np.int32)  # whole frame changed
    topo = _derive_change_topology({1: (before, after)}, 4096, {})
    assert topo == "level_transition"


def test_topology_sprite_move():
    before = _blank()
    before[32, 32] = 5
    after = _blank()
    after[28, 32] = 5
    # `1` is in dir_map → sprite_move
    topo = _derive_change_topology({1: (before, after)}, 4096, {1: "N"})
    assert topo == "sprite_move"


def test_topology_color_toggle():
    """Same positions change value without spatial displacement ⇒ color_toggle."""
    before = _blank()
    before[5, 5] = 1
    before[5, 6] = 1
    after = _blank()
    after[5, 5] = 2  # same cells, different colors
    after[5, 6] = 2
    # no dir_map entry for this action
    topo = _derive_change_topology({6: (before, after)}, 4096, {})
    assert topo == "color_toggle"


# ---------------------------------------------------------------------------
# _derive_color_histogram
# ---------------------------------------------------------------------------


def test_color_histogram_equal_split():
    frame = _blank()
    frame[:32, :] = 1
    frame[32:, :] = 2
    hist = _derive_color_histogram(frame)
    assert hist[1] == pytest.approx(0.5)
    assert hist[2] == pytest.approx(0.5)


def test_color_histogram_ordered_by_abundance():
    frame = _blank()
    frame[0, :] = 9  # only 64 pixels of 4096
    frame[1:, :] = 3
    hist = _derive_color_histogram(frame)
    keys = list(hist.keys())
    assert keys[0] == 3  # most abundant first
    assert hist[3] > hist[9]


# ---------------------------------------------------------------------------
# _derive_symmetry_score
# ---------------------------------------------------------------------------


def test_symmetry_score_all_zero():
    assert _derive_symmetry_score(_blank()) == 1.0


def test_symmetry_score_horizontally_symmetric():
    frame = _blank()
    frame[:, 10:54] = 5  # band symmetric about center
    assert _derive_symmetry_score(frame) == 1.0


def test_symmetry_score_asymmetric():
    frame = _blank()
    frame[:, :8] = 5  # only left side
    score = _derive_symmetry_score(frame)
    assert 0.0 <= score < 1.0


# ---------------------------------------------------------------------------
# _derive_movable_region_count
# ---------------------------------------------------------------------------


def test_movable_region_count_single_player():
    before = _blank()
    before[32, 32] = 5
    after = _blank()
    after[31, 32] = 5  # adjacent → connected
    assert _derive_movable_region_count({1: (before, after)}) == 1


def test_movable_region_count_two_characters():
    before = _blank()
    before[32, 32] = 5
    before[10, 10] = 7
    after = _blank()
    after[30, 32] = 5  # sprite 1 moved far — leaves 2 diff spots
    after[8, 10] = 7   # sprite 2 moved — leaves another 2 spots
    # Expect at least 2 disjoint diff regions (sprite 1 original+new and sprite 2 original+new)
    count = _derive_movable_region_count({1: (before, after)})
    assert count >= 2


# ---------------------------------------------------------------------------
# _derive_click_responsive_cells
# ---------------------------------------------------------------------------


def test_click_responsive_cells_records_diff_and_colors():
    before = _blank()
    after = _blank()
    after[32, 32] = 9  # click at (32, 32) turned cell 9
    probes_a6 = [(32, 32, before, after), (16, 16, _blank(), _blank())]
    cells = _derive_click_responsive_cells(probes_a6)
    # Only the responsive one is kept
    assert len(cells) == 1
    r = cells[0]
    assert r["x"] == 32 and r["y"] == 32
    assert r["color_before_at_click"] == 0
    assert r["color_after_at_click"] == 9
    assert r["diff"] >= 1


def test_click_responsive_cells_skips_inert():
    before = _blank()
    after = _blank()  # no change
    probes_a6 = [(32, 32, before, after)]
    assert _derive_click_responsive_cells(probes_a6) == []
