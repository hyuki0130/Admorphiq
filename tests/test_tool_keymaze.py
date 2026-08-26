"""Contract pins for the key-maze tool.

⛔ Two tests were REMOVED on 2026-08-27: `test_indicator_must_be_magnified` and
`test_detect_requires_four_directions_and_both_glyphs`. They pinned a NEWER version of
`tools/keymaze.py` whose standalone probe cleared 4 levels but which measured **-0.2382 on its own
game** through the harness (a probe drives a tool directly; the harness routes by `detect`). The
older implementation was kept on that measurement, so the tests pinned behaviour that is not in
the tree. A test that fails because we deliberately kept different code is not a regression signal
— see `.wiki/wiki/lessons/moving_target_measurement_20260827.md`.
"""

from __future__ import annotations

import re

import numpy as np

from admorphiq.tools.keymaze import KeyMazeTool, _find_indicator

# The board these fixtures draw, in this family's grammar:
#   pitch 5, lattice origin (0, 4); floor 3, wall 4; a lock cell of body 5 holding a
#   3x3 glyph; an indicator panel of body 5 holding the same glyph magnified 2x; a
#   budget bar pinned to the bottom edge.
_PITCH = 5
_FLOOR, _WALL, _BODY = 3, 4, 5
_KEY_A = ((1, 1, 1), (1, 0, 0), (1, 0, 1))     # the key the avatar starts holding
_KEY_B = ((1, 1, 1), (0, 0, 1), (1, 0, 1))     # _KEY_A turned one quarter clockwise


def _stamp(g: np.ndarray, y: int, x: int, bits, colour: int, scale: int) -> None:
    for r, row in enumerate(bits):
        for c, on in enumerate(row):
            if on:
                g[y + r * scale:y + (r + 1) * scale, x + c * scale:x + (c + 1) * scale] = colour


def _board(*, key=_KEY_A, want=_KEY_B, key_colour=9, want_colour=9,
           icon: tuple[int, int, int] | None = (6, 3, 0)) -> np.ndarray:
    """A 12x12 corridor board: avatar at (9, 6), lock at (2, 6), one icon cell."""
    g = np.full((64, 64), _WALL, dtype=int)
    g[:52, :4] = _BODY                                # letterbox down the left
    for r in range(1, 11):                            # a clear column and a clear row
        g[r * 5:r * 5 + 5, 4 + 6 * 5:4 + 7 * 5] = _FLOOR
    g[9 * 5:9 * 5 + 5, 4 + 3 * 5:4 + 7 * 5] = _FLOOR
    for r in range(6, 10):
        g[r * 5:r * 5 + 5, 4 + 3 * 5:4 + 4 * 5] = _FLOOR
    g[9 * 5:9 * 5 + 5, 4 + 6 * 5:4 + 7 * 5] = _FLOOR
    g[9 * 5:9 * 5 + 2, 4 + 6 * 5:4 + 7 * 5] = 12      # avatar: two colour bands
    g[9 * 5 + 2:9 * 5 + 5, 4 + 6 * 5:4 + 7 * 5] = 9
    ly, lx = 2 * 5, 4 + 6 * 5                         # lock cell
    g[ly:ly + 5, lx:lx + 5] = _BODY
    _stamp(g, ly + 1, lx + 1, want, want_colour, 1)
    if icon is not None:                              # icon: ink clear of its border
        r, c, ink = icon
        g[r * 5 + 2, 4 + c * 5 + 2] = ink
        g[r * 5 + 2, 4 + c * 5 + 3] = ink
    g[52, :] = _WALL                                  # indicator panel, bottom left
    g[53:63, 1:11] = _BODY
    _stamp(g, 55, 3, key, key_colour, 2)
    g[61:63, 13:55] = 11                              # edge-pinned budget bar
    return g


class _Obs:
    def __init__(self, g: np.ndarray, actions=(1, 2, 3, 4)) -> None:
        self.frame = [g.tolist()]
        self.available_actions = list(actions)
        self.state = "NOT_FINISHED"
        self.levels_completed = 0


def _calibrated(g: np.ndarray) -> KeyMazeTool:
    """A tool with the one-off measurements already made, so tests probe the planner."""
    tool = KeyMazeTool()
    tool.pitch, tool.origin, tool.floor = _PITCH, (0, 4), _FLOOR
    tool.dirs = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
    found = _find_indicator(g)
    assert found is not None
    tool.panel, tool.glyph_k = found
    tool.bar_colour, tool.unit_cost = 11, 2
    tool.full_units = tool._bar(g)
    return tool




def test_matching_key_walks_straight_to_the_lock():
    """Purpose: prove the lock opens on glyph equality — pattern AND colour, not either.

    Expected feedback: pass ⇒ a matching key routes the seven cells to the lock and a
    key differing only in colour does not; fail ⇒ either the lock test ignores colour
    (and the avatar walks into a refusal) or it ignores the pattern.
    """
    g = _board(key=_KEY_B)                    # already the key the lock asks for
    tool = _calibrated(g)
    board = tool._parse(g)
    assert board is not None and board.avatar == (9, 6) and set(board.locks) == {(2, 6)}
    plan = tool._plan(board, tool._read_token(g), g)
    assert plan == [1] * 7                    # seven cells straight up, no detour

    wrong_colour = _board(key=_KEY_B, key_colour=14)
    tool2 = _calibrated(wrong_colour)
    board2 = tool2._parse(wrong_colour)
    assert tool2._plan(board2, tool2._read_token(wrong_colour), wrong_colour) != [1] * 7


def test_unmeasured_icon_is_visited_before_it_is_trusted():
    """Purpose: pin that an icon of unknown effect is a thing to MEASURE, not to assume.

    Expected feedback: pass ⇒ the plan walks to the unnamed icon; fail ⇒ the search has
    started guessing what an icon does, which is the assumption this tool exists to avoid.
    """
    g = _board()                              # key needs a quarter turn; icon unnamed
    tool = _calibrated(g)
    board = tool._parse(g)
    assert (6, 3) in board.icons
    plan = tool._plan(board, tool._read_token(g), g)
    cell = board.avatar
    for action in plan:
        d = tool.dirs[action]
        cell = (cell[0] + d[0], cell[1] + d[1])
    assert cell == (6, 3)


def test_a_turn_icon_generalises_from_one_sighting():
    """Purpose: pin the one mutation that never needs a second visit.

    A turn is recoverable from the bitmap itself, so three turns can be planned after
    seeing one. A recolour cannot, and must stay unplannable until its step is seen.

    Expected feedback: pass ⇒ a named turn icon yields a complete plan that ends at the
    lock; fail ⇒ the tool re-measures what it already knows and burns the budget bouncing.
    """
    g = _board(key=_KEY_A, want=_KEY_B)
    tool = _calibrated(g)
    board = tool._parse(g)
    tool.icon_kind[board.icons[(6, 3)]] = "turn"
    plan = tool._plan(board, tool._read_token(g), g)
    cell, key = board.avatar, tool._read_token(g)
    for action in plan:
        d = tool.dirs[action]
        cell = (cell[0] + d[0], cell[1] + d[1])
        if cell in board.locks:
            break
        if cell in board.icons:
            key = tool._mutate(board.icons[cell], key)
    assert cell == (2, 6) and key == board.locks[(2, 6)]


def test_icon_under_the_avatar_is_not_forgotten():
    """Purpose: pin the recall that makes a second trigger of one icon plannable.

    An avatar standing on an icon hides it. Measured: without recall, a level needing
    three triggers of one icon stalls after the first with a plan that reads as impossible.

    Expected feedback: pass ⇒ the icon is still in view while stood on; fail ⇒ bouncing
    on an icon is invisible to the search and multi-trigger levels cannot be planned.
    """
    g = _board()
    tool = _calibrated(g)
    assert (6, 3) in tool._parse(g).icons
    on_top = _board(icon=None)                # avatar moved onto the icon cell
    on_top[9 * 5:9 * 5 + 5, 4 + 6 * 5:4 + 7 * 5] = _FLOOR
    on_top[6 * 5:6 * 5 + 2, 4 + 3 * 5:4 + 4 * 5] = 12
    on_top[6 * 5 + 2:6 * 5 + 5, 4 + 3 * 5:4 + 4 * 5] = 9
    board = tool._parse(on_top)
    assert board.avatar == (6, 3) and (6, 3) in board.icons


def test_budget_is_searched_not_checked_afterwards():
    """Purpose: pin that the remaining budget gates the search itself.

    Expected feedback: pass ⇒ a budget too small for the seven-cell walk yields no
    budgeted plan; fail ⇒ the planner commits to routes it cannot finish and dies at the
    far end of the maze, which is how the sample board's second level was lost.
    """
    g = _board(key=_KEY_B, icon=None)
    tool = _calibrated(g)
    board = tool._parse(g)
    token = tool._read_token(g)
    assert tool._search(board, token, g, tool.unit_cost) == [1] * 7
    starved = _board(key=_KEY_B, icon=None)
    starved[61:63, 13:55] = 4
    starved[61:63, 13:19] = 11                # three actions' worth of bar left
    board = tool._parse(starved)
    tool.full_units = 84
    assert tool._search(board, token, starved, tool.unit_cost) == []


def test_no_game_specifics_in_source():
    """Purpose: generality guard — the tool must contain no game ids, titles, or
    sprite tags so it transfers to the unseen private games.

    Expected feedback: pass ⇒ frame-only and portable; fail ⇒ a game-specific
    leak crept in and the tool won't generalize.
    """
    import admorphiq.tools.keymaze as mod

    src = open(mod.__file__).read().lower()
    for tok in ("game_id", "game_title", "sprite"):
        assert tok not in src
    assert not re.search(r"\b[a-z]{2}\d{2}\b", src)
