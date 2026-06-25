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
    GeneralAgent,
    connected_components,
    corridor_color_from_probes,
    edge_grid_bfs,
    floor_colors_from_probes,
    frame_to_cells,
    goal_centroid_px,
    grid_bfs,
    infer_direction_map,
    pick_goal_cell,
    pick_next_probe,
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


# ---------------------------------------------------------------------------
# infer_direction_map — HUD-drift rejection
# ---------------------------------------------------------------------------


def test_infer_direction_map_rejects_sub_pixel_hud_drift():
    """Purpose: a HUD / progress bar that creeps ~1px per action must NOT be
    mistaken for the player — this is the tu93 bug where a bottom step-counter
    bar drifting left polluted the direction map with bogus (-1,0) vectors and
    starved the real (6px-stepping) player of its learned directions.

    Expected feedback: pass means only the genuine multi-pixel mover is learned
    and the 1px-drift colour is filtered; a fail reproduces the HUD-hijack that
    left the planner with a wrong/incomplete direction map.
    """
    base = np.zeros((20, 20), dtype=np.int32)
    base[2:5, 2:5] = 9  # real player sprite (colour 9), steps by cell pitch
    base[18, 0:4] = 6  # a 4-px HUD bar (colour 6) along the bottom

    # ACTION4: player steps right by 6px; HUD bar drifts left by only 1px.
    after = _shift(_shift(base, 9, 0, 6), 6, 0, -1)
    probes = [{"aid": 4, "before": base, "after": after}]
    dir_map, player = infer_direction_map(probes, background=0)
    assert player is not None
    assert player["color"] == 9  # the player, not the HUD bar
    assert dir_map == {4: (6, 0)}  # only the real 6px step; no HUD (-1,0) entry


# ---------------------------------------------------------------------------
# pick_next_probe — recentering-aware discovery policy
# ---------------------------------------------------------------------------


def test_pick_next_probe_sweeps_breadth_first_before_retrying():
    """Purpose: every movement action must be probed ONCE before any is retried
    — the first sweep reveals which directions are unblocked from the start cell
    and yields learned inverses to recenter with. A depth-first policy (the old
    bug) burned the whole budget retrying the first wall-blocked action.

    Expected feedback: pass means the four targets are issued 1,2,3,4 in order
    on the first pass; a fail means the agent fixates on one action and never
    explores the others within budget.
    """
    targets = [1, 2, 3, 4]
    learned: dict[int, tuple[int, int]] = {}
    attempts: dict[int, int] = {}
    order = []
    last_probe = None
    last_moved = False
    for _ in range(4):
        kind, aid = pick_next_probe(targets, learned, attempts, last_moved, last_probe)
        assert kind == "probe"
        order.append(aid)
        attempts[aid] = attempts.get(aid, 0) + 1  # simulate a (blocked) probe
        last_probe, last_moved = aid, False
    assert order == [1, 2, 3, 4]


def test_pick_next_probe_recenters_before_retrying_blocked_action():
    """Purpose: once the first sweep has learned at least one direction, a
    still-unlearned (wall-blocked) action must be RETRIED only after a
    recentering move that frees the player — this is the fix for a player that
    starts wall-bound and cannot move up/left until it has moved away.

    Expected feedback: pass means a retry of a blocked target yields a
    "recenter" using a learned action, then the following call re-probes it; a
    fail means the agent re-probes from the same wall-bound cell forever and
    never learns the blocked direction.
    """
    targets = [1, 2, 3, 4]
    learned = {2: (0, 6), 4: (6, 0)}  # down + right already learned on sweep
    attempts = {1: 1, 2: 1, 3: 1, 4: 1}  # action 1 (up) was blocked once
    # Retry of unlearned action 1: previous call was a probe of 1 that did not move.
    kind, aid = pick_next_probe(targets, learned, attempts, last_moved=False, last_was_probe_of=1)
    assert kind == "recenter"
    assert aid in learned  # relocate using a known direction
    # After the recenter (modelled as last_was_probe_of=None), it re-probes 1.
    kind2, aid2 = pick_next_probe(
        targets, learned, attempts, last_moved=False, last_was_probe_of=None
    )
    assert kind2 == "probe"
    assert aid2 == 1


def test_pick_next_probe_done_when_all_learned_or_exhausted():
    """Purpose: discovery must terminate — once every target is learned or has
    used its attempt budget, the policy reports "done" so the FSM advances to
    planning instead of probing forever.

    Expected feedback: pass means a fully-learned target set ends discovery; a
    fail means the agent loops in the discovery phase and never plans.
    """
    targets = [1, 2, 3, 4]
    learned = {1: (0, -6), 2: (0, 6), 3: (-6, 0), 4: (6, 0)}
    kind, aid = pick_next_probe(targets, learned, {}, last_moved=True, last_was_probe_of=4)
    assert kind == "done"
    assert aid is None


# ---------------------------------------------------------------------------
# end-to-end discovery against a synthetic wall-bound-start env
# ---------------------------------------------------------------------------


class _Frame:
    """Minimal arcengine-shaped observation for driving the agent in tests."""

    def __init__(self, layer: np.ndarray, avail: list[int]) -> None:
        self.frame = [layer]  # (1, H, W) single-layer frame
        self.available_actions = avail
        self.levels_completed = 0

        class _S:
            name = "NOT_FINISHED"

        self.state = _S()


class _ScriptedMaze:
    """A 4-direction grid env whose player starts wall-bound at the top-left.

    Reproduces the tu93 failure mode: from the start cell the player can only
    move DOWN (action 2) and RIGHT (action 4); UP (1) and LEFT (3) are blocked
    until the player has moved into open space. A correct, recentering-aware
    discovery must still learn all four direction vectors.
    """

    PITCH = 6

    def __init__(self) -> None:
        self.col = 0  # player grid column (0 = left wall)
        self.row = 0  # player grid row (0 = top wall)
        self.maxr = 6
        self.maxc = 6

    def _layer(self) -> np.ndarray:
        layer = np.full((64, 64), 5, dtype=np.int32)  # background colour 5
        py = self.row * self.PITCH + 2
        px = self.col * self.PITCH + 2
        layer[py : py + 3, px : px + 3] = 9  # 3x3 player sprite, colour 9
        return layer

    def frame(self) -> _Frame:
        return _Frame(self._layer(), [1, 2, 3, 4])

    def step(self, aid: int) -> None:
        if aid == 1 and self.row > 0:  # up
            self.row -= 1
        elif aid == 2 and self.row < self.maxr:  # down
            self.row += 1
        elif aid == 3 and self.col > 0:  # left
            self.col -= 1
        elif aid == 4 and self.col < self.maxc:  # right
            self.col += 1


def test_discovery_learns_all_four_directions_from_wall_bound_start():
    """Purpose: the headline regression — discovery must learn ALL four movement
    directions even when the player starts pinned in a corner where two probes
    initially produce no movement. The original sweep learned only the two
    unblocked directions (down+right), leaving the grid planner unable to
    navigate up or left and clearing 0 levels.

    Expected feedback: pass means the agent's learned ``_dir_map`` contains a
    distinct vector for each of actions 1/2/3/4 with the correct signs (up/down
    on the y axis, left/right on the x axis); a fail reproduces the 2-direction
    map that made real navigation impossible.
    """
    maze = _ScriptedMaze()
    agent = GeneralAgent()
    frame = maze.frame()
    for _ in range(40):  # bounded; discovery must finish well within this
        action = agent.choose_action([], frame)
        aid = getattr(action, "id", None)
        if aid is None:
            aid = getattr(action, "value", 0)
        maze.step(int(aid))
        frame = maze.frame()
        if agent._phase != "discovery":
            break

    dir_map = agent._dir_map
    assert set(dir_map) == {1, 2, 3, 4}, f"missing directions: {dir_map}"
    # Sign check: action 1 = up (dy<0), 2 = down (dy>0), 3 = left (dx<0),
    # 4 = right (dx>0). Each is a one-axis step of the cell pitch.
    assert dir_map[1][1] < 0 and dir_map[1][0] == 0  # up
    assert dir_map[2][1] > 0 and dir_map[2][0] == 0  # down
    assert dir_map[3][0] < 0 and dir_map[3][1] == 0  # left
    assert dir_map[4][0] > 0 and dir_map[4][1] == 0  # right


# ---------------------------------------------------------------------------
# corridor_color_from_probes / edge_grid_bfs / goal_centroid_px
# ---------------------------------------------------------------------------


def test_corridor_color_from_probes_reads_edge_midpoint_not_destination():
    """Purpose: derive the open-edge (corridor) colour from the midpoint between
    a probe's before/after player centroids, even when the destination node
    itself renders as wall colour (the tu93-class interleaved-pitch maze).

    Expected feedback: pass means the agent learns colour 7 is the walkable
    corridor purely from where the player passed through; a fail means edge
    walkability falls back to the node-dominant model and tu93 cannot be
    navigated (the level-0-clear regression this whole fix targets).
    """
    bg = 5
    player = 9
    # 9x3 strip: player at cols 0-0 row1, corridor colour 7 at the midpoint
    # col 2, destination node at col 4 rendered as wall colour 0.
    before = np.full((3, 7), bg, dtype=np.int32)
    before[1, 0] = player  # player start centroid ~ (0, 1)
    before[1, 2] = 7  # the open edge midpoint
    before[1, 4] = 0  # destination node renders as wall colour
    after = np.full((3, 7), bg, dtype=np.int32)
    after[1, 4] = player  # player ended on the node that looked like wall
    probes = [{"aid": 4, "before": before, "after": after}]
    assert corridor_color_from_probes(probes, player, bg) == 7


def test_corridor_color_from_probes_none_without_translation():
    """Purpose: a probe where the player did not move yields no corridor vote.

    Expected feedback: pass confirms blocked / no-op probes never invent a
    corridor colour; a fail would let a stationary frame poison the maze model.
    """
    bg = 5
    player = 9
    frame = np.full((3, 5), bg, dtype=np.int32)
    frame[1, 1] = player
    probes = [{"aid": 1, "before": frame, "after": frame.copy()}]
    assert corridor_color_from_probes(probes, player, bg) is None


def test_edge_grid_bfs_navigates_interleaved_pitch_maze():
    """Purpose: edge_grid_bfs finds a shortest action path over a node grid
    whose nodes render as wall colour but whose connecting edges are the
    corridor colour — the model the node-dominant frame_to_cells cannot express.

    Expected feedback: pass proves the navigation primitive can actually reach a
    goal in a tu93-style maze; a fail means closed-loop execution would have no
    path and bail to explore (0 levels, the bug being fixed).
    """
    bg = 5
    player = 9
    corridor = 2
    pitch = 2  # nodes 2px apart, edge midpoint at +1px
    # 7x7 frame. Player node at px (1,1) -> anchor. Goal marker colour 14 at
    # px (5,5). Open a straight L-path: right edge at (1,3) open, down edges.
    layer = np.full((7, 7), bg, dtype=np.int32)
    # Nodes render as wall colour 0 at the 2px grid points (1,1),(1,3),(1,5),...
    for ny in (1, 3, 5):
        for nx in (1, 3, 5):
            layer[ny, nx] = 0
    layer[1, 1] = player  # player sits on its node
    # Open edges along the path: (1,1)->(1,3) right [mid (1,2)],
    # (1,3)->(1,5) right [mid (1,4)], (1,5)->(3,5) down [mid (2,5)],
    # (3,5)->(5,5) down [mid (4,5)].
    layer[1, 2] = corridor
    layer[1, 4] = corridor
    layer[2, 5] = corridor
    layer[4, 5] = corridor
    layer[5, 5] = 14  # goal marker (overrides the node wall colour)
    step_dirs = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}  # up/down/left/right
    path = edge_grid_bfs(
        layer, (1.0, 1.0), pitch, (5.0, 5.0), step_dirs, corridor, player, bg
    )
    assert path is not None
    # Shortest L-path is right, right, down, down = 4 moves (actions 4,4,2,2).
    assert path == [4, 4, 2, 2]


def test_edge_grid_bfs_returns_none_when_walled_off():
    """Purpose: when no open edge leads toward the goal, edge_grid_bfs returns
    None rather than a wrong path.

    Expected feedback: pass means the planner honestly reports 'unreachable' so
    the agent can fall back; a fail would emit phantom moves into walls.
    """
    bg = 5
    player = 9
    corridor = 2
    layer = np.full((7, 7), bg, dtype=np.int32)
    layer[1, 1] = player
    layer[5, 5] = 14
    # No corridor pixels at all -> every edge is closed.
    step_dirs = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
    path = edge_grid_bfs(
        layer, (1.0, 1.0), 2, (5.0, 5.0), step_dirs, corridor, player, bg
    )
    assert path is None


def test_goal_centroid_px_picks_rare_marker_centroid():
    """Purpose: goal_centroid_px returns the sub-pixel centroid of the distinct
    rare-colour marker the player must reach (tu93's colour-14 exit).

    Expected feedback: pass confirms the edge navigator anchors the goal node on
    the real exit; a fail means it aims at the wrong cluster and never clears.
    """
    bg = 5
    player = 9
    layer = np.full((10, 10), bg, dtype=np.int32)
    # A big non-goal object (colour 0) and a small rare marker (colour 14).
    layer[0:5, 0:5] = 0
    layer[7:10, 7:10] = 14  # 3x3 marker, centroid (8, 8)
    centroid = goal_centroid_px(layer, player, bg)
    assert centroid is not None
    cx, cy = centroid
    assert round(cx) == 8 and round(cy) == 8
