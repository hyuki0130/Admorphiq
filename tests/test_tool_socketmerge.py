"""Contract tests for the socket-merge tool's perception and click geometry."""

from __future__ import annotations

import re

import numpy as np

from admorphiq.tools.socketmerge import SocketMergeTool


def _board(header_extra: list[tuple[int, int, int]] | None = None) -> np.ndarray:
    """A minimal frame in this family's grammar: header, disc socket, two solid squares."""
    g = np.full((64, 64), 5, dtype=int)
    g[:10] = 4                      # header, in a colour the playfield never uses
    g[63] = 0                       # edge-pinned budget bar
    g[4:7, 30:33] = 15              # header glyph: the wanted piece, in its own colour
    for y, x, c in header_extra or []:
        g[y, x] = c
    g[20:29, 40:49] = 9             # socket: a square footprint...
    for dy, dx in ((0, 0), (0, 8), (8, 0), (8, 8)):
        g[20 + dy, 40 + dx] = 5     # ...with its corners cut away
    g[40:43, 10:13] = 15
    g[40:43, 20:23] = 15
    return g


class _Obs:
    def __init__(self, g: np.ndarray) -> None:
        self.frame = [g.tolist()]
        self.available_actions = [6, 7]
        self.state = "NOT_FINISHED"
        self.levels_completed = 0


def test_header_colour_not_height_bounds_the_playfield():
    """Purpose: pin that the header is found by its own colour rather than a fixed height.

    Expected feedback: pass ⇒ a header that prints a legend on background-coloured cells
    is still read as header; fail ⇒ the "rows with no background" shortcut has crept back
    and the legend row would be handed to the planner as board content.
    """
    g = _board()
    g[0, :16] = 5      # a legend strip sits on background colour inside the header
    g[3, :16] = 5
    g[1:3, 1:3] = 15   # ...listing the one rank this board plays with
    tool = SocketMergeTool()
    board = tool._read(g)
    assert board is not None
    assert board.top == 10
    assert board.bottom == 62


def test_only_header_colours_count_as_pieces():
    """Purpose: pin the palette gate that keeps decoration out of the planner.

    One sample board draws a dotted guide line and a decoy square in a colour the header
    never shows; both are solid squares and would otherwise be planned over.

    Expected feedback: pass ⇒ exactly the two real squares are seen; fail ⇒ the tool will
    spend a level's budget clicking at scenery.
    """
    g = _board()
    g[44:47, 44:47] = 3                      # a decoy square inside the socket
    for i in range(8):
        g[50, 30 - 2 * i] = 3                # the dotted guide line, clear of the squares
    tool = SocketMergeTool()
    board = tool._read(g)
    assert board is not None
    assert sorted((p.x, p.y, p.side) for p in board.pieces) == [(10, 40, 3), (20, 40, 3)]
    assert board.sockets == ((44, 24),)


def test_no_click_is_offered_that_would_gather_a_third_equal_piece():
    """Purpose: pin the exact-sweep rule.

    MEASURED on a live board: a vacuum holding three equal pieces fuses the whole group
    into ONE piece of the next size, so the third is burnt and the board's total — which
    the level's target is cut from exactly — is permanently short.

    Expected feedback: pass ⇒ every offered click takes the two intended pieces and no
    other; fail ⇒ the tool can silently destroy the material the level needs.
    """
    g = _board()
    g[40:43, 30:33] = 15  # a third square, close enough to be swept up by a careless click
    tool = SocketMergeTool()
    tool._reach = 8
    board = tool._read(g)
    assert board is not None
    a, b = board.pieces[0], board.pieces[1]
    for px, py, _ in tool._clicks_for(board, [a, b], 64, 64):
        swept = tool._sweep(board, px, py, tool._reach)
        assert {(q.x, q.y) for q in swept} == {(a.x, a.y), (b.x, b.y)}


def test_detect_is_zero_without_a_socket():
    """Purpose: pin that the tool withdraws rather than bidding on a lookalike board.

    Expected feedback: pass ⇒ a board of solid squares with nothing to deliver them into
    scores 0 and the turn goes to a tool that can use it; fail ⇒ this tool can take a game
    it cannot finish, which is measured to be worth more than a solve it might have had.
    """
    g = _board()
    g[20:29, 40:49] = 5  # erase the socket
    tool = SocketMergeTool()
    assert tool.detect([], _Obs(g)) == 0.0


def test_tool_source_carries_no_game_specifics():
    """Purpose: pin the frame-only rule for this tool's source.

    Expected feedback: pass ⇒ nothing in the module names a game or reads its internals;
    fail ⇒ the tool has been tuned to one board and will not transfer.
    """
    import admorphiq.tools.socketmerge as mod

    src = open(mod.__file__).read().lower()
    for tok in ("game_id", "game_title", "sprite"):
        assert tok not in src
    assert not re.search(r"\b[a-z]{2}\d{2}\b", src)


def test_the_two_header_strips_are_read_as_different_things():
    """Purpose: pin that the ladder key and the required items are told apart by the strip
    each is printed on, not by position.

    MEASURED: taking the palette from the whole header swallows a striker's icon, and the
    striker itself then reads as a handful of playable pieces — which cost a live board its
    whole step budget trying to fuse its own attacker.

    Expected feedback: pass ⇒ the key names the ladder while the chrome-field icons name
    what the sockets owe, and a required colour off the ladder is booked as a striker;
    fail ⇒ the tool plans against a requirement it has misread.
    """
    g = _board()
    g[0, :16] = 5
    g[3, :16] = 5
    g[1:3, 1:3] = 15                 # key: rank 0
    g[1:3, 5:7] = 11                 # key: rank 1
    g[4:8, 40:45] = 7                # a required item in a colour the key does not list
    tool = SocketMergeTool()
    board = tool._read(g)
    assert board is not None
    assert tool._ladder == [15, 11]
    assert board.want_rank == ((0, 1),)   # the chrome-field glyph of colour 15 = rank 0
    assert board.want_strikers == 1
    assert tool._striker_colours == {7}


def test_a_second_key_strip_is_not_part_of_the_ladder():
    """Purpose: pin that a header printing TWO keys keeps them apart.

    MEASURED on a live board: the deeper boards print the merge ladder on one strip and the
    roster of striker kinds on another. Read as a single row ordered by column, a striker
    colour landed at the bottom of the ladder, so every striker on the board counted as a
    piece of that rank and the requirement came out nonsense.

    Expected feedback: pass ⇒ only the strip whose colours appear as solid squares on the
    playfield is the ladder, and the other strip's colours are booked as striker kinds;
    fail ⇒ ranks are shifted and the plan is built against the wrong material.
    """
    g = _board()
    g[0, :16] = 5
    g[3, :16] = 5
    g[1:3, 1:3] = 15                 # the ladder: the colour the board's squares use
    g[5, :12] = 5                    # a second strip, lower down
    g[8, :12] = 5
    g[6:8, 1:3] = 7                  # a striker kind, never drawn as a solid square
    tool = SocketMergeTool()
    board = tool._read(g)
    assert board is not None
    assert tool._ladder == [15]
    assert 7 in tool._striker_colours
    assert sorted((p.x, p.y, p.side) for p in board.pieces) == [(10, 40, 3), (20, 40, 3)]


def test_the_settle_click_is_held_as_state_not_queued_behind_the_click():
    """Purpose: pin that the two halves of one vacuum cannot be separated.

    MEASURED: emitting the pair as a single two-step list works when the tool is driven
    directly and FAILS inside the harness, which empties its action queue the moment the
    level counter moves — and that counter moves DURING the win animation, one action
    before the next board is drawn. The dropped filler was replaced by a re-plan on the
    animating frame, which wedged a live board and cost the rest of its budget.

    Expected feedback: pass ⇒ propose offers ONE click and holds the settle itself, so
    nothing outside the tool can come between them; fail ⇒ deep levels are unreachable
    through the harness even though the tool reaches them when driven alone.
    """
    tool = SocketMergeTool()
    first = tool.propose([], _Obs(_board()))
    assert len(first) == 1
    assert tool._settling
    assert tool.propose([], _Obs(_board())) == [(6, (0, 0))]
    assert not tool._settling
