"""Tests for the M0R0 offline-reconstruction merge-maze adapter (R59,
2026-07-16). This adapter replaced the R56 joint hill-climb: it frame-parses
the FULL wall/hazard map up front and runs an offline joint BFS to MERGE the
two mirror players onto one cell. The tests below pin the load-bearing R59
findings (each was a real bug fixed this round):

  - centered-grid parsing when the offset EXCEEDS the cell scale (a 13-wide
    grid at scale 4 has offset 6, so ``pixel % scale`` is not the offset);
  - floor / wall / hazard classification, where the WALL colour varies per
    level (so walls are "not floor/player/hazard", never a fixed colour);
  - two ADJACENT players read as two distinct cells (``find_regions`` connects
    them, which stalled the final merge move);
  - the mirror control scheme so a hazard forbids a joint move, a wall blocks
    one side independently, and an adjacent pair merges via the cross-swap;
  - identity read from OBSERVED motion so a column crossing never inverts the
    mirrored controls;
  - the persistent scheme where a BLOCKED probe never clobbers a known delta
    (the bug that made ACTION1 look like a no-op after a settle step);
  - cvcer movable-block classification + relocation (L3), which lifts 2/6→3/6.

See the module docstring for the ground-truth + gold-oracle investigation.
"""

from __future__ import annotations

from types import SimpleNamespace

from admorphiq.adapters25.m0r0 import (
    _BLOCK_MOVE_LABELS,
    Adapter,
    _classify_cell,
    _parse_maze,
    _solve_axis,
)

_BG = 5
_PLAYER = 10
_HAZARD = 8
_BLOCK = 9  # cvcer movable-block colour
_WALL = 11  # a zone colour; the parser must not key on this specific value


def _build_frame(cellmap: dict[tuple[int, int], str], gh: int, gw: int, scale: int) -> tuple[tuple[int, ...], ...]:
    """A 64x64 rendered-style frame: a centered ``gh``x``gw`` grid at ``scale``
    px/cell painted from ``cellmap`` ('floor'/'wall'/'haz'/'p0'/'p1'), the rest
    padding (wall colour). Hazard cells are checkerboarded 8-over-floor, exactly
    as the live engine renders wyiex."""
    off_y = (64 - gh * scale) // 2
    off_x = (64 - gw * scale) // 2
    g = [[_WALL] * 64 for _ in range(64)]
    for gy in range(gh):
        for gx in range(gw):
            kind = cellmap.get((gy, gx), "wall")
            r0, c0 = off_y + gy * scale, off_x + gx * scale
            for rr in range(r0, r0 + scale):
                for cc in range(c0, c0 + scale):
                    if kind == "wall":
                        g[rr][cc] = _WALL
                    elif kind == "haz":
                        g[rr][cc] = _HAZARD if (rr + cc) % 2 == 0 else _BG
                    elif kind == "block":
                        g[rr][cc] = _BLOCK  # cvcer movable block (colour 9)
                    elif kind in ("p0", "p1"):
                        g[rr][cc] = _PLAYER
                    else:
                        g[rr][cc] = _BG
    return tuple(tuple(row) for row in g)


def _frame(grid: tuple[tuple[int, ...], ...], levels: int = 0, state: str = "NOT_FINISHED") -> SimpleNamespace:
    return SimpleNamespace(
        frame=[[list(row) for row in grid]],
        state=SimpleNamespace(name=state),
        levels_completed=levels,
        available_actions=[1, 2, 3, 4],
    )


def test_solve_axis_recovers_offset_that_exceeds_the_cell_scale():
    """Purpose: pin the exact R59 parse bug — a 13-wide grid at scale 4 has
    offset 6, which is GREATER than the scale, so ``pixel % scale`` (== 2)
    is not the offset. ``_solve_axis`` must instead pick the tightest centered
    grid whose offset aligns every player pixel and contains all content.
    Expected feedback: failure means L2's maze is parsed one cell off on
    every axis, silently mislocating every wall — the bug that made ACTION1
    look frozen and hid every desync path."""
    # players at grid cols 4 and 8 -> pixels 6+16=22 and 6+32=38 for gw=13.
    dim, off = _solve_axis(4, [22, 38], content_lo=6, content_hi=57)
    assert (dim, off) == (13, 6)


def test_classify_cell_reads_floor_wall_and_hazard():
    """Purpose: the wall colour varies per level, so a cell is FLOOR only from
    a background/player pixel, HAZARD from any colour-8 pixel, and WALL
    otherwise — never keyed on a fixed wall colour.
    Expected feedback: failure means walls or the reset-triggering hazards are
    misclassified, so the joint search plans through solid walls or onto
    fatal cells."""
    floor = _build_frame({(0, 0): "floor"}, 1, 1, 4)
    haz = _build_frame({(0, 0): "haz"}, 1, 1, 4)
    wall = _build_frame({(0, 0): "wall"}, 1, 1, 4)
    off = (64 - 4) // 2
    assert _classify_cell(floor, off, off, 4, _BG, _PLAYER) == "floor"
    assert _classify_cell(haz, off, off, 4, _BG, _PLAYER) == "hazard"
    assert _classify_cell(wall, off, off, 4, _BG, _PLAYER) == "wall"


def test_parse_maze_separates_walls_hazards_and_two_players():
    """Purpose: end-to-end parse contract — from a rendered frame, recover the
    grid dims, the wall set, the hazard set, and BOTH player cells, with the
    outer padding (same colour as walls) excluded.
    Expected feedback: failure means the offline joint BFS is fed a wrong
    board and cannot reproduce a live merge."""
    # A floor-majority interior (so the background colour is the floor, as in
    # the real frames) with a couple of walls and one hazard.
    cellmap = {(gy, gx): "floor" for gy in range(5) for gx in range(5)}
    cellmap[(1, 1)] = "p0"
    cellmap[(1, 3)] = "p1"
    cellmap[(2, 2)] = "wall"
    cellmap[(3, 3)] = "haz"
    frame = _build_frame(cellmap, 5, 5, 12)
    maze = _parse_maze(frame, _PLAYER)
    assert maze is not None
    assert (maze.gh, maze.gw) == (5, 5)
    assert (2, 2) in maze.walls
    assert (3, 3) in maze.hazards
    assert maze.players == [(1, 1), (1, 3)]


def test_current_players_keeps_two_adjacent_players_distinct():
    """Purpose: regression pin for the R59 stall — when the two players become
    adjacent, ``find_regions`` connects them into ONE region, which made the
    adapter see a single player and idle instead of executing the final
    crossing merge. Player cells must be enumerated by grid cell so an
    adjacent pair reads as two distinct cells.
    Expected feedback: failure means an about-to-merge pair looks merged-but-
    not-won and the run stalls one move short of clearing the level."""
    # a separated pair to seed the maze parse (scale/offset), then an adjacent pair
    seed = {(gy, gx): "floor" for gy in range(5) for gx in range(5)}
    seed[(1, 1)] = "p0"
    seed[(1, 3)] = "p1"
    adjacent = {(gy, gx): "floor" for gy in range(5) for gx in range(5)}
    adjacent[(2, 2)] = "p0"
    adjacent[(2, 3)] = "p1"  # horizontally adjacent -> one region
    adapter = Adapter()
    adapter._player_color = _PLAYER
    adapter._maze = _parse_maze(_build_frame(seed, 5, 5, 12), _PLAYER)
    cells = adapter._current_players(_build_frame(adjacent, 5, 5, 12))
    assert cells == [(2, 2), (2, 3)]


def test_successors_forbid_hazard_block_wall_and_merge_on_crossing():
    """Purpose: the joint dynamics contract. Under the mirror scheme, a joint
    action that would land EITHER player on a hazard is forbidden (no
    successor); a wall blocks one side independently (it stays while the other
    moves); and an adjacent same-row pair moving to cross merges to the
    midpoint.
    Expected feedback: failure means the offline plan diverges from the live
    engine — stepping onto a hazard (reset), phasing through a wall, or never
    recognising the merge."""
    adapter = Adapter()
    adapter._scheme = {1: {0: (-1, 0), 1: (-1, 0)}, 2: {0: (1, 0), 1: (1, 0)},
                       3: {0: (0, -1), 1: (0, 1)}, 4: {0: (0, 1), 1: (0, -1)}}

    class _M:
        gh, gw = 5, 5
        walls = {(0, 2)}
        hazards = {(2, 4)}
    adapter._maze = _M()  # type: ignore[assignment]

    succ = adapter._successors([1, 2, 3, 4])

    # Cross-merge: players adjacent same row at (2,1),(2,2); ACTION4 swaps -> merge midpoint.
    out = dict(succ(((2, 1), (2, 2))))
    assert out[4] == ((2, 1), (2, 1))

    # Wall block: ACTION1 moves both up, but player0 at (1,2) hits wall (0,2) and stays.
    out2 = dict(succ(((1, 2), (1, 0))))
    assert out2[1] == ((1, 2), (0, 0))

    # Hazard forbidden: ACTION4 from (2,3),(?) would put player0 on (2,4) hazard -> no successor.
    out3 = dict(succ(((2, 3), (0, 0))))
    assert 4 not in out3


def test_assign_identity_reads_a_column_crossing_from_observed_motion():
    """Purpose: the two players share a colour and swap left/right order when
    they cross columns. Identity must be read from the OBSERVED motion — the
    cell whose displacement matches scheme[action][0] is player-0 — so the
    mirrored column controls are never inverted.
    Expected feedback: failure means the plan inverts its column moves after a
    crossing and drives the pair APART (the R59 corner-spreading stall)."""
    adapter = Adapter()
    adapter._scheme = {a: {} for a in (1, 2, 3, 4)}
    adapter._scheme[4] = {0: (0, 1), 1: (0, -1)}
    # Previous frame: p0 at (2,2), p1 at (2,3). ACTION4 moves p0 by (0,1) to
    # (2,3) and p1 by (0,-1) to (2,2) — they cross. player-0 is now the cell
    # (2,3) because it is the one displaced by scheme[4][0]=(0,1).
    adapter._prev_merge_players = [(2, 2), (2, 3)]
    adapter._last_action = 4
    adapter._assign_identity([(2, 2), (2, 3)])
    assert adapter._p0 == (2, 3)
    assert adapter._p1 == (2, 2)


def test_scheme_persists_and_a_blocked_probe_does_not_clobber_it():
    """Purpose: the control scheme is a game constant, so it persists across
    levels and a BLOCKED probe (zero delta, e.g. ACTION1 issued while a player
    sits against the top wall) must NEVER overwrite a known non-zero delta —
    the R59 bug that silently froze the column invariant and hid every desync.
    Expected feedback: failure means a later level re-measures an action as a
    no-op and the joint search can no longer move that axis."""
    cm = {(gy, gx): "floor" for gy in range(5) for gx in range(5)}
    cm[(0, 0)] = "p0"
    cm[(0, 2)] = "p1"
    before = _build_frame(cm, 5, 5, 12)
    adapter = Adapter()
    adapter._scheme[1] = {0: (-1, 0), 1: (-1, 0)}
    adapter._player_color = _PLAYER
    adapter._maze = _parse_maze(before, _PLAYER)
    adapter._prev_grid = before
    adapter._measure_action = 1
    adapter._measure_prev = [(0, 0), (0, 2)]
    adapter._absorb_probe(before)  # same frame => zero delta for action 1
    assert adapter._scheme[1] == {0: (-1, 0), 1: (-1, 0)}  # unchanged


def test_game_over_preserves_scheme_and_parsed_maze():
    """Purpose: a soft reset (a player hit a hazard) must keep every parsed
    fact — the control scheme and the maze — and only drop the current
    attempt's plan/identity, so each life compounds instead of re-measuring
    from scratch.
    Expected feedback: failure means every hazard bump throws away the learned
    scheme/maze, wasting the action budget re-discovering them."""
    cm = {(gy, gx): "floor" for gy in range(5) for gx in range(5)}
    cm[(0, 0)] = "p0"
    cm[(0, 2)] = "p1"
    adapter = Adapter()
    adapter._scheme[2] = {0: (1, 0), 1: (1, 0)}
    adapter._maze = _parse_maze(_build_frame(cm, 5, 5, 12), _PLAYER)
    assert adapter._maze is not None
    saved_scheme = {k: dict(v) for k, v in adapter._scheme.items()}
    saved_maze = adapter._maze
    adapter.choose_action([], SimpleNamespace(state=SimpleNamespace(name="GAME_OVER")))
    assert adapter._scheme == saved_scheme
    assert adapter._maze is saved_maze
    assert adapter._p0 is None and adapter._p1 is None


def test_is_done_bails_after_sustained_no_plan_streak():
    """Purpose: on an unmodelled level variant the deterministic search returns
    no merge plan indefinitely; ``is_done`` must bail once that streak is
    sustained, rather than burning the shared action budget for no score change.
    A level that merely needs a long path always returns a non-empty plan, so
    its streak stays zero.
    Expected feedback: failure means an unclearable late level spins to the
    full giveup cap, wasting runtime across the 110-game budget."""
    adapter = Adapter()
    frame = _frame(_build_frame({(0, 0): "floor"}, 1, 1, 4))
    assert adapter.is_done([], frame) is False
    adapter._no_plan_streak = 10_000
    assert adapter.is_done([], frame) is True


def test_classify_cell_distinguishes_block_solid8_wall_and_checkerboard_hazard():
    """Purpose: L3's zone WALL colour is 8 — the same colour a wyiex hazard
    uses — so the classifier must tell them apart by the checkerboard: a
    hazard cell mixes colour 8 with floor pixels, a zone wall is SOLID 8, and a
    cvcer movable block is colour 9.
    Expected feedback: failure means half of L3 is mass-mis-read as hazards
    (solid-8 walls) or the blocks vanish into the floor, and the merge never
    plans correctly."""
    off = (64 - 4) // 2

    def _solid(color):
        return tuple(tuple(color for _ in range(64)) for _ in range(64))

    assert _classify_cell(_solid(_BLOCK), off, off, 4, _BG, _PLAYER) == "block"
    assert _classify_cell(_solid(_HAZARD), off, off, 4, _BG, _PLAYER) == "wall"  # SOLID 8 = zone wall
    haz = _build_frame({(0, 0): "haz"}, 1, 1, 4)  # checkerboard 8-over-floor
    assert _classify_cell(haz, off, off, 4, _BG, _PLAYER) == "hazard"


def test_parse_maze_reports_cvcer_blocks_separately_from_walls():
    """Purpose: the parse must surface cvcer movable blocks as ``maze.blocks``
    (not folded into walls), so the clearing phase knows what to relocate,
    while a wall-heavy floor colour (colour 5 is a fixed constant, never the
    most-common colour) still bounds the grid.
    Expected feedback: failure means the adapter cannot see the blocks and
    treats L3 as an unsolvable static maze."""
    cellmap = {(gy, gx): "floor" for gy in range(5) for gx in range(5)}
    cellmap[(1, 1)] = "p0"
    cellmap[(1, 3)] = "p1"
    cellmap[(2, 2)] = "block"
    cellmap[(3, 3)] = "wall"
    maze = _parse_maze(_build_frame(cellmap, 5, 5, 12), _PLAYER)
    assert maze is not None
    assert (2, 2) in maze.blocks
    assert (2, 2) not in maze.walls
    assert (3, 3) in maze.walls


def test_block_move_labels_are_the_raw_grid_directions():
    """Purpose: a SELECTED cvcer block moves in raw grid directions (up/down/
    left/right for ACTION1/2/3/4), verified live — used to route it via
    grid_shortest_path.
    Expected feedback: failure means the block-relocation routes send it the
    wrong way and clearing never opens the merge path."""
    assert _BLOCK_MOVE_LABELS == {(-1, 0): 1, (1, 0): 2, (0, -1): 3, (0, 1): 4}
