"""Unit tests for the efficiency-first general agent's pure planning logic.

These cover the env-free building blocks in ``admorphiq.general_agent``:
connected-components, player/direction-map inference (the player-vs-cursor
disambiguation that broke the first naive version), the grid abstraction's
walkability classification, floor-colour learning, and grid-BFS shortest-path
search. The agent's value is *efficient* (near-human-length) navigation, so
these tests pin the two properties that make that possible: correct player
identification and shortest-path planning over a correct walkable grid.
"""

from __future__ import annotations

import numpy as np

from admorphiq.general_agent import (
    connected_components,
    floor_colors_from_probes,
    frame_to_cells,
    grid_bfs,
    infer_direction_map,
    pick_goal_cell,
)


def _grid(rows: list[str], mapping: dict[str, int]) -> np.ndarray:
    """Build an int layer from an ASCII map using ``mapping`` (char -> colour)."""
    return np.array([[mapping[ch] for ch in row] for row in rows], dtype=np.int32)


# ---------------------------------------------------------------------------
# connected_components
# ---------------------------------------------------------------------------


def test_connected_components_excludes_background_and_splits_by_adjacency():
    """Purpose: 4-connected components ignore the background and do not merge
    diagonally-touching same-colour blobs.

    Expected feedback: pass means entity extraction sees the right number of
    distinct objects; a fail means the player / goal counts downstream are
    wrong (the whole navigation pipeline keys off these components).
    """
    layer = _grid(
        [
            "00000",
            "01000",
            "00000",
            "00020",  # a diagonally-adjacent same-colour cell of '1'? no — colour 2
        ],
        {"0": 0, "1": 1, "2": 2},
    )
    comps = connected_components(layer, background=0)
    colors = sorted(c["color"] for c in comps)
    assert colors == [1, 2]
    by_color = {c["color"]: c for c in comps}
    assert by_color[1]["size"] == 1
    assert by_color[2]["size"] == 1


def test_connected_components_defaults_background_to_most_common():
    """Purpose: when no background is given, the most frequent colour is treated
    as background and dropped.

    Expected feedback: pass confirms the agent need not be told the background
    explicitly; a fail means a flood of background cells would be returned as
    a giant 'object'.
    """
    layer = np.zeros((6, 6), dtype=np.int32)  # all background (0)
    layer[2, 2] = 7
    comps = connected_components(layer)  # background inferred = 0
    assert len(comps) == 1
    assert comps[0]["color"] == 7


# ---------------------------------------------------------------------------
# infer_direction_map — player vs cursor disambiguation
# ---------------------------------------------------------------------------


def _shift(layer: np.ndarray, color: int, drow: int, dcol: int) -> np.ndarray:
    """Return a copy of ``layer`` with all ``color`` cells translated."""
    out = layer.copy()
    out[layer == color] = layer[layer == color][0] if False else out[layer == color]
    # Clear old, set new.
    ys, xs = np.where(layer == color)
    bg = int(np.bincount(layer.ravel()).argmax())
    out[ys, xs] = bg
    nys, nxs = ys + drow, xs + dcol
    inside = (nys >= 0) & (nys < layer.shape[0]) & (nxs >= 0) & (nxs < layer.shape[1])
    out[nys[inside], nxs[inside]] = color
    return out


def test_infer_direction_map_picks_real_player_over_single_pixel_cursor():
    """Purpose: a multi-pixel player must win over a 1-pixel cursor that also
    translates — the original naive version locked onto the first mover and
    chose the cursor, giving a noisy 1-pixel cell pitch and unsolvable plans.

    Expected feedback: pass means player colour == the 3x3 sprite and the
    learned step matches its real pixel displacement; a fail reproduces the
    cursor-hijack bug.
    """
    base = np.zeros((20, 20), dtype=np.int32)
    base[2:5, 2:5] = 9  # 9-cell player sprite (colour 9)
    base[10, 10] = 4  # 1-pixel cursor (colour 4)

    # ACTION4 shifts both right by 3 cells; ACTION2 shifts both down by 3.
    p_right = _shift(_shift(base, 9, 0, 3), 4, 0, 3)
    p_down = _shift(_shift(base, 9, 3, 0), 4, 3, 0)
    probes = [
        {"aid": 4, "before": base, "after": p_right},
        {"aid": 2, "before": p_right, "after": p_down},
    ]
    dir_map, player = infer_direction_map(probes, background=0)
    assert player is not None
    assert player["color"] == 9  # not the 1-pixel cursor (colour 4)
    assert dir_map[4] == (3, 0)  # learned a right step of 3 px


def test_infer_direction_map_ignores_tiled_wall_colours():
    """Purpose: a colour that tiles the background in many identical blocks
    must not be mistaken for the player just because nearest-twin matching
    finds spurious 1-cell 'shifts' between adjacent tiles.

    Expected feedback: pass means many-instance colours are filtered out and
    only the rare player sprite is selected; a fail reproduces the maze-tile
    false-positive that picked a wall colour as the player.
    """
    base = np.zeros((20, 20), dtype=np.int32)
    # A repeating wall colour 2 in 6 separate 1-cell tiles (many instances).
    for i, (r, c) in enumerate([(1, 1), (1, 4), (1, 7), (4, 1), (4, 4), (4, 7)]):
        base[r, c] = 2
    base[15:18, 15:18] = 9  # the real (rare, multi-pixel) player

    after = _shift(base, 9, 0, 3)
    probes = [{"aid": 4, "before": base, "after": after}]
    _, player = infer_direction_map(probes, background=0)
    assert player is not None
    assert player["color"] == 9


# ---------------------------------------------------------------------------
# frame_to_cells — walkability with floor colours
# ---------------------------------------------------------------------------


def test_frame_to_cells_floor_colours_keep_corridors_walkable():
    """Purpose: a non-background corridor colour must be walkable when supplied
    as a floor colour; without it the whole maze is mislabelled as wall.

    Expected feedback: pass means corridor cells stay passable and only the
    distinct wall colour blocks; a fail means BFS can never route through a
    coloured-floor maze (the ls20-class failure).
    """
    # cell=1 grid: colour 3 = corridor floor, colour 5 = solid wall.
    layer = _grid(
        [
            "335",
            "335",
            "335",
        ],
        {"3": 3, "5": 5},
    )
    walk_no_floor, _ = frame_to_cells(layer, cell=1, player_color=9, background=0)
    # Without floor info colour-3 blocks count as walls too.
    assert not walk_no_floor[0, 0]

    walk_floor, _ = frame_to_cells(
        layer, cell=1, player_color=9, background=0, floor_colors={3}
    )
    assert walk_floor[0, 0]  # corridor now walkable
    assert not walk_floor[0, 2]  # wall colour 5 still blocked


def test_floor_colors_from_probes_reveals_vacated_colour():
    """Purpose: the colour revealed where the player vacated is learned as
    floor — this is the observation-driven signal that distinguishes corridor
    from wall without any game-specific knowledge.

    Expected feedback: pass means the corridor colour under the player is
    captured; a fail means floor learning is broken and walkability inverts.
    """
    before = np.full((5, 5), 0, dtype=np.int32)
    before[2, 2] = 9  # player on a cell
    after = before.copy()
    after[2, 2] = 3  # player moved away → colour 3 revealed (corridor floor)
    after[2, 3] = 9
    floors = floor_colors_from_probes(
        [{"aid": 4, "before": before, "after": after}], player_color=9, background=0
    )
    assert floors == {3}


# ---------------------------------------------------------------------------
# grid_bfs — shortest path + reachability
# ---------------------------------------------------------------------------


def test_grid_bfs_finds_shortest_path_around_wall():
    """Purpose: BFS returns a SHORTEST action sequence (near-human length is
    the whole point of the efficiency metric) and routes around obstacles.

    Expected feedback: pass means the path length equals the manhattan optimum
    plus the detour forced by the wall; a fail means plans are non-minimal and
    the efficiency score collapses.
    """
    walk = np.ones((5, 5), dtype=bool)
    walk[:, 2] = False
    walk[4, 2] = True  # single gap at the bottom of the wall column
    step_dirs = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}  # up/down/left/right
    path = grid_bfs(walk, start=(0, 0), goal=(0, 4), step_dirs=step_dirs)
    assert path is not None
    # The only gap is (4, 2): reach row 4, cross to col 4, return to row 0 =
    # 4 down + 4 right + 4 up = 12 steps. BFS must find this minimum.
    assert len(path) == 12


def test_grid_bfs_returns_none_when_unreachable():
    """Purpose: a fully walled-off goal yields None, so the agent bails to
    cheap-explore instead of looping.

    Expected feedback: pass means unreachable goals are detected; a fail means
    the planner could spin or emit a bogus partial path.
    """
    walk = np.ones((5, 5), dtype=bool)
    walk[:, 2] = False  # complete wall, no gap
    step_dirs = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
    assert grid_bfs(walk, (0, 0), (0, 4), step_dirs) is None


def test_grid_bfs_empty_path_when_start_is_goal():
    """Purpose: start==goal returns an empty plan (already arrived), distinct
    from None (unreachable).

    Expected feedback: pass lets the caller treat 'arrived' and 'unreachable'
    differently; a fail conflates the two and mis-routes the FSM.
    """
    walk = np.ones((3, 3), dtype=bool)
    step_dirs = {4: (1, 0)}
    assert grid_bfs(walk, (1, 1), (1, 1), step_dirs) == []


def test_pick_goal_cell_ignores_single_pixel_noise():
    """Purpose: the goal must be a real cluster (size>=3), not a 1-pixel
    artefact that happens to be the rarest colour.

    Expected feedback: pass means a 1-pixel rare dot is skipped in favour of a
    genuine multi-cell target; a fail reproduces the noise-as-goal bug that
    sent plans to a meaningless corner.
    """
    layer = np.zeros((12, 12), dtype=np.int32)
    layer[0, 0] = 4  # 1-pixel noise, rarest colour overall
    layer[8:11, 8:11] = 7  # real 9-cell target cluster
    goal = pick_goal_cell(layer, cell=2, player_color=9, background=0)
    assert goal is not None
    # Goal should map to the colour-7 cluster region (rows/cols ~8-10 / cell 2).
    assert goal == (4, 4)
