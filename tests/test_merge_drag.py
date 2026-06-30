"""Unit tests for the frame-only CLICK-DRAG-TO-GOAL gather capability (R49).

These pin the click-drag MERGE / gather sub-class of the select-and-place
ARRANGEMENT family the world-model agent uses for click-only games where a
click pulls nearby tiles toward the click point and the level clears by walking
the movable tile(s) into a distinct goal container (SU15 L1 — one coloured value
tile in a corner plus a hollow goal ring; clears when the tile is dragged into
the ring). Every test is env-free on synthetic frames: the capability must be
observation-driven with no game-id / internal reads, so its behaviour is fully
exercised by hand-built layers.
"""

from __future__ import annotations

import numpy as np

from admorphiq.merge_drag import (
    DragLayout,
    detect_drag_layout,
    drag_probe_target,
    next_drag_click,
    next_merge_click,
)

_BG = 5


def _layer_with(boxes: list[tuple[int, int, int, int, int]]) -> np.ndarray:
    """Build a 64x64 background frame with coloured rectangles.

    ``boxes`` is a list of (color, r0, c0, r1, c1) inclusive rectangles.
    """
    layer = np.full((64, 64), _BG, dtype=np.int32)
    for color, r0, c0, r1, c1 in boxes:
        layer[r0 : r1 + 1, c0 : c1 + 1] = color
    return layer


def _su15_l1_layer() -> np.ndarray:
    """A synthetic SU15-L1-shaped layer: one small value tile + a goal ring.

    A 3x3 value tile (colour 15) in the bottom-left corner and a larger goal
    region (colour 9) top-right, mirroring the measured SU15 L1 geometry (tile
    ~(4,59), goal ~(48,15)).
    """
    return _layer_with(
        [
            (15, 57, 2, 59, 4),  # value tile, centroid ~(3,58)
            (9, 11, 44, 19, 52),  # goal ring region, centroid ~(48,15)
        ]
    )


def test_detect_drag_layout_picks_largest_as_goal():
    """Purpose: detect_drag_layout names the largest playfield cluster the goal
    and every smaller distinct-colour cluster a movable tile.

    Expected feedback: a PASS proves the frame-only reader separates the gather
    destination (the bigger container) from the pieces to drag into it; a FAIL
    means tile/goal roles are swapped or mis-segmented and the walk would push
    pieces away from the goal.
    """
    layout = detect_drag_layout(_su15_l1_layer(), _BG)
    assert layout is not None
    # Goal is the larger colour-9 region (top-right).
    assert 40 < layout.goal[0] < 56
    assert 8 < layout.goal[1] < 24
    # The colour-15 tile is the movable piece, not the goal.
    assert any(t[2] == 15 for t in layout.tiles)
    assert all(t[2] != 9 for t in layout.tiles)


def test_detect_returns_none_without_two_clusters():
    """Purpose: a frame with fewer than two playfield clusters is not a gather.

    Expected feedback: a PASS proves the plan needs both a tile and a goal to
    engage (no false positive on a near-empty frame); a FAIL means the plan
    could fire with nothing to gather.
    """
    assert detect_drag_layout(_layer_with([(15, 57, 2, 59, 4)]), _BG) is None
    assert detect_drag_layout(np.full((0, 0), _BG), _BG) is None


def test_detect_returns_none_on_dense_grid():
    """Purpose: a board tiled with many equal cells (a lights-out / bit-panel
    TOGGLE grid like FT09 / TN36) is rejected, not treated as a gather.

    Expected feedback: a PASS proves the tile-count falsifier keeps the drag plan
    off dense click games (the FT09/TN36 regression guard); a FAIL means the plan
    would hijack a toggle game and waste its budget walking phantom tiles.
    """
    boxes: list[tuple[int, int, int, int, int]] = [(9, 10, 10, 14, 14)]  # one goal
    # 15 separated equal tiles in a grid → more than _MAX_TILES, not a gather.
    for i in range(3):
        for j in range(5):
            r = 20 + i * 8
            c = 12 + j * 9
            boxes.append((4, r, c, r + 2, c + 2))
    assert detect_drag_layout(_layer_with(boxes), _BG) is None


def test_scatter_line_dropped_but_merge_cloud_kept():
    """Purpose: a long scattered single-colour HUD line is dropped from tile
    candidates while a smaller scattered same-colour merge cloud is kept.

    Expected feedback: a PASS proves the scatter falsifier distinguishes SU15's
    ~21-dot diagonal chrome line (rejected) from its 8-dot value-0 merge cloud
    (kept), which is what lets the merge phase engage on SU15 L2 without firing
    on the chrome line; a FAIL means either the merge tiles vanish (L2 lost) or
    the chrome line is mistaken for tiles.
    """
    # Goal container + a 16-dot diagonal chrome line (color 3) + an 8-dot merge
    # cloud (color 10). The line must be dropped, the cloud kept as tiles.
    boxes: list[tuple[int, int, int, int, int]] = [(9, 20, 40, 28, 48)]  # goal
    for k in range(16):  # diagonal chrome line, > _SCATTER_MIN_CLUSTERS
        boxes.append((3, 12 + k * 3, 2 + k * 3, 12 + k * 3, 2 + k * 3))
    cloud = [(18, 18), (37, 20), (16, 24), (49, 26), (14, 30), (47, 32), (16, 34), (41, 22)]
    for cx, cy in cloud:  # 8-dot merge cloud, < _SCATTER_MIN_CLUSTERS
        boxes.append((10, cy, cx, cy, cx))
    layout = detect_drag_layout(_layer_with(boxes), _BG)
    assert layout is not None
    tile_colors = {t[2] for t in layout.tiles}
    assert 10 in tile_colors  # merge cloud kept
    assert 3 not in tile_colors  # chrome line dropped


def test_next_merge_click_merges_then_gathers():
    """Purpose: next_merge_click clicks the midpoint of a touching same-colour
    pair (to merge) and, when no pair remains, drives a lone tile toward the goal.

    Expected feedback: a PASS proves the merge planner combines equal tiles
    before gathering (the SU15 deep-level 2048 chain); a FAIL means it would try
    to gather un-merged tiles or skip the merge step.
    """
    # Two touching colour-10 tiles → expect a midpoint click between them.
    pair_layer = _layer_with(
        [
            (9, 40, 40, 48, 48),  # goal
            (10, 30, 30, 30, 30),  # tile a
            (10, 31, 32, 31, 32),  # tile b ~2px away (within merge dist)
        ]
    )
    cell = next_merge_click(pair_layer, _BG)
    assert cell is not None
    x, y = cell
    assert 29 <= x <= 33 and 29 <= y <= 33  # midpoint of the pair

    # A single distinct tile + goal → no pair, so it gathers toward the goal.
    lone_layer = _layer_with(
        [
            (9, 40, 40, 48, 48),  # goal centroid ~(44,44)
            (10, 10, 10, 12, 12),  # lone tile bottom-left
        ]
    )
    cell2 = next_merge_click(lone_layer, _BG)
    assert cell2 is not None
    # Gather step heads toward the goal (down-right of the lone tile).
    assert cell2[0] > 11 and cell2[1] > 11


def test_drag_probe_target_steps_toward_goal():
    """Purpose: the first TEST click is a short step from the goal-nearest tile
    toward the goal (the cheapest drag-hypothesis confirmation).

    Expected feedback: a PASS proves the probe click is placed between the tile
    and the goal so a confirmed pull advances the tile the right way; a FAIL
    means the probe could drag the tile away from the goal or land off-board.
    """
    layout = detect_drag_layout(_su15_l1_layer(), _BG)
    assert layout is not None
    x, y = drag_probe_target(layout)
    assert 0 <= x <= 63 and 0 <= y <= 63
    # The tile sits bottom-left, goal top-right → the probe must move up-right.
    tile = next(t for t in layout.tiles if t[2] == 15)
    assert x >= tile[0] and y <= tile[1]


def test_next_drag_click_drives_farthest_tile():
    """Purpose: next_drag_click drives the tile FARTHEST from the goal one step
    toward the goal so no piece is abandoned half-walked.

    Expected feedback: a PASS proves each live-frame walk click advances a
    straggler toward the container; a FAIL means the walk stalls or oscillates
    and the gather never completes.
    """
    layer = _su15_l1_layer()
    cell = next_drag_click(layer, _BG)
    assert cell is not None
    x, y = cell
    # Goal top-right, lone far tile bottom-left → click must head up-right of it.
    assert x > 3 and y < 58


def test_next_drag_click_none_when_gathered():
    """Purpose: with every tile already inside the goal-reach radius, the walk
    reports nothing left to do (None) so the agent stops clicking.

    Expected feedback: a PASS proves the gather terminates cleanly once the
    pieces are on the container (no wasted post-clear clicks); a FAIL means the
    walk would keep clicking the placed tile and burn budget.
    """
    # Tile centroid coincident with the goal centroid → already gathered.
    layer = _layer_with(
        [
            (9, 20, 20, 28, 28),  # goal region, centroid ~(24,24)
            (15, 23, 23, 25, 25),  # tile centroid ~(24,24), inside goal
        ]
    )
    assert next_drag_click(layer, _BG) is None


def test_layout_dataclass_shape():
    """Purpose: DragLayout carries the tile list and goal centroid the plan
    functions consume.

    Expected feedback: a PASS proves the detected-layout contract (tiles as
    (cx,cy,color,size) tuples + a (cx,cy) goal) is stable for callers; a FAIL
    means a downstream plan reads the wrong field shape.
    """
    layout = DragLayout(tiles=[(4.0, 59.0, 15, 9)], goal=(48.0, 15.0))
    assert layout.goal == (48.0, 15.0)
    assert layout.tiles[0][2] == 15
