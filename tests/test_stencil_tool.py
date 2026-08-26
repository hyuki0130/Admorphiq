"""Contract pins for the stencil tool (round r101).

These are engine-free: the frames are built here, so the pins hold on a clean checkout with no
game environments present.
"""

from __future__ import annotations

from admorphiq.tools.stencil import StencilTool, all_tiles, pitch, plan, read_code, tiles

BG = 5
BLANK = 9
MARKER = 8
GLYPH = [[0, 2, 2], [0, MARKER, 0], [0, 2, 2]]


def _blank_grid() -> list[list[int]]:
    return [[BG] * 64 for _ in range(64)]


def _put_tile(g: list[list[int]], oy: int, ox: int, colour: int) -> None:
    for y in range(oy, oy + 6):
        for x in range(ox, ox + 6):
            g[y][x] = colour


def _put_stencil(g: list[list[int]], oy: int, ox: int) -> None:
    _put_tile(g, oy, ox, 0)
    for i in range(3):
        for j in range(3):
            g[oy + 2 * i][ox + 2 * j] = GLYPH[i][j]


def _panel(g: list[list[int]], oy: int, ox: int, solved: bool) -> None:
    """A 3x3 panel. Solved => its plain tiles already realise the glyph."""
    for i in range(3):
        for j in range(3):
            y, x = oy + 8 * i, ox + 8 * j
            if (i, j) == (1, 1):
                _put_stencil(g, y, x)
            elif solved:
                _put_tile(g, y, x, MARKER if GLYPH[i][j] == 0 else BLANK)
            else:
                _put_tile(g, y, x, BLANK)


def _framed_board(g: list[list[int]]) -> None:
    """The live board, wrapped in a frame that touches every tile."""
    for y in range(32, 62):
        for x in range(32, 62):
            g[y][x] = 4
    _panel(g, 36, 36, solved=False)


def _scene() -> list[list[int]]:
    g = _blank_grid()
    _panel(g, 2, 4, solved=True)     # a worked example, off to the side
    _framed_board(g)
    return g


def test_the_live_board_is_the_framed_one() -> None:
    """Purpose: pin that a frame selects the live panel rather than merging the board away.

    Passing means `_peel` split the container and `tiles()` narrowed to what the game framed.
    Failing means either the whole board came back as one blob (the pre-fix behaviour) or the
    dead panels were treated as playable — on ft09 a click there resets the level.
    """
    g = _scene()
    assert len(all_tiles(g)) == 18
    live = tiles(g)
    assert len(live) == 9
    assert min(live) == (36, 36)


def test_pitch_is_the_modal_gap_not_the_smallest() -> None:
    """Purpose: pin the lattice step against the two-panels-two-pixels-apart trap.

    Passing means an unrelated neighbouring panel cannot masquerade as the board's pitch.
    Failing means every neighbour lookup silently misses and the tool plans nothing.
    """
    origins = [(0, 4), (0, 12), (0, 20), (0, 22), (8, 4)]
    assert pitch(origins, side=6) == 8
    assert min(b - a for a, b in zip(sorted({o[1] for o in origins}), sorted({o[1] for o in origins})[1:])) == 2


def test_code_is_read_from_the_worked_example_and_is_a_role() -> None:
    """Purpose: pin that ink meaning is learned from a solved panel, and stored as a role.

    Passing means the untouched live board (every ink mapping to the blank colour) was rejected
    as a source and the solved panel supplied the code. Failing means the tool guessed from ink
    frequency — which cannot separate the two inks here, as both appear four times.
    """
    g = _scene()
    code = read_code(g, all_tiles(g), pitch(list(all_tiles(g)), 6))
    assert code == {0: True, 2: False}


def test_plan_paints_exactly_the_marker_cells() -> None:
    """Purpose: pin the whole chain end to end on a board whose answer is known by construction.

    Passing means the four ink-0 neighbours are clicked and the four ink-2 ones are left alone.
    Failing means either half of the stencil is being ignored.
    """
    clicks, code = plan(_scene())
    assert code == {0: True, 2: False}
    assert clicks == [(38, 38), (46, 38), (46, 54), (54, 38)]


def test_tool_declines_a_frame_with_no_lattice() -> None:
    """Purpose: pin the withdrawal that makes the tool cheap on the games it does not fit.

    Passing means `detect` scores 0 on a blank frame. Failing means the harness would spend a
    game's budget on a mechanic that is not there — the sweep measured 24 of 25 sample games
    as non-matches, so declining cheaply is most of this tool's runtime behaviour.
    """
    class _Obs:
        frame = [[[BG] * 64 for _ in range(64)]]

    assert StencilTool().detect([], _Obs()) == 0.0


def test_tool_stops_on_a_revisited_tile_map() -> None:
    """Purpose: pin the cycle guard that protects levels already won.

    On ft09 a wrong click costs a level — one run lost all four (4 -> 0) by clicking on through
    a board its model did not fit. Passing means a board state the tool has already acted on
    makes it withdraw. Failing means it can spend a game's remaining budget, and its winnings,
    on a mechanic it has misread.

    The guard hashes the TILE MAP rather than the frame: this game marches an action counter one
    pixel per action, so a whole-frame hash is unique every step and detects nothing.
    """
    class _Obs:
        levels_completed = 0

        def __init__(self, grid: list[list[int]]) -> None:
            self.frame = [grid]

    tool = StencilTool()
    scene = _scene()
    assert tool.propose([], _Obs(scene)) != []
    assert tool.propose([], _Obs(scene)) == []


def test_a_marching_counter_is_not_a_board_response() -> None:
    """Purpose: pin that a progress bar cannot masquerade as the board answering.

    Passing means a probe sweep whose every response is one cell advancing along an edge reports
    ZERO responders. Failing means the tool reads a HUD as a lattice — measured on vc33 (50 of 50
    probes changed row 0 alone) and on ka59, whose "genuine one-cell rule" turned out to be the
    action counter walking backwards along row 63.
    """
    from admorphiq.tools.induce import _hud_cells

    raw = {(4, 8 * i): [(63, 63 - i)] for i in range(12)}
    hud = _hud_cells(raw, probes=12, size=64)
    assert all(cell in hud for delta in raw.values() for cell in delta)


def test_a_real_response_survives_the_counter_filter() -> None:
    """Purpose: pin the other direction, so the filter is not simply deleting everything.

    Passing means a probe whose delta is a block of board cells keeps that delta while the
    counter pixel riding along with it is removed. Failing means the filter is one-sided, which
    is how every checker in this repo has been wrong on its first run.
    """
    from admorphiq.tools.induce import _hud_cells

    raw = {
        (20 + 8 * i, 20): [(30 + i, 30), (30 + i, 31), (63, 63 - i)]
        for i in range(6)
    }
    hud = _hud_cells(raw, probes=6, size=64)
    assert (63, 63) in hud
    assert (30, 30) not in hud
