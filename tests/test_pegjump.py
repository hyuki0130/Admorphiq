"""`pegjump` — the partial-map rule that keeps a window from being mistaken for a board.

Every case here pins a behaviour that was measured on lf52 level 6 (a 28-cell board against a
ten-cell screen) and is recorded in `OPERATING_RULES.md` rule 7bc/7be:

  * the model held 2 of the board's 6 pieces, purely because the other four were scrolled off;
  * jumping one over the other left ONE, so the planner returned it as a SOLVED level;
  * that single claim is the capture after which the level is provably unwinnable;
  * handed the true six pieces the same search stops calling it a win and still takes it, because
    it is the cheapest capture — so refusing the win is necessary and not sufficient.
"""
from __future__ import annotations

from admorphiq.tools.pegjump import (
    Model,
    capture_reachable,
    plan_moves,
    railhead_moves,
    runs_offscreen,
)


def _window_board() -> Model:
    """Two pieces on a strip of track whose rails run off both ends of the screen.

    The shape of lf52 level 6 at the losing decision, reduced to what the assertion needs: a
    horizontal run of sockets with two adjacent pieces, and rails continuing past the window.
    """
    m = Model()
    m.pitch, m.oy, m.ox = 6, 0, 0
    for c in range(0, 10):
        m.sockets.add((2, c))
        m.rails.add((4, c))
    m.pieces = {(2, 4): 0, (2, 5): 0}
    m.window = {(r, c) for r in range(0, 9) for c in range(0, 10)}
    return m


def test_runs_offscreen_sees_track_leaving_the_window() -> None:
    """Purpose: the a-priori partiality signal fires on a board whose track leaves the screen.

    Expected feedback: PASS means a planner can know its map is a window BEFORE it makes a claim,
    which is the only route available to a tool whose first claim is the losing move. FAIL means
    the signal is unavailable and only the learn-from-refutation route remains.
    """
    m = _window_board()
    # The rail row runs the full width of the window, so both ends continue into the unknown.
    assert runs_offscreen(m) is True


def test_runs_offscreen_is_false_for_a_board_that_fits() -> None:
    """Purpose: the signal does NOT fire on a board wholly inside the frame.

    Expected feedback: PASS means the rule is inert on self-contained boards, so nothing that
    already worked can change. FAIL means every board is treated as partial and real wins are
    refused everywhere.
    """
    m = _window_board()
    m.window = {(r, c) for r in range(-4, 14) for c in range(-4, 14)}
    assert runs_offscreen(m) is False


def test_partial_refuses_a_win_declared_over_a_window() -> None:
    """Purpose: on a partial map, reducing every VISIBLE piece to one is not a solved level.

    Expected feedback: PASS means the claim that cost lf52 level 6 can no longer be made from a
    two-piece window. FAIL means a predicate over a camera is still being read as a predicate over
    the state.
    """
    m = _window_board()
    whole = plan_moves(m, frozenset())
    assert whole is not None and whole[1] is True      # the defect, reproduced
    assert plan_moves(m, frozenset(), partial=True) is None


def test_partial_still_solves_when_a_further_capture_survives() -> None:
    """Purpose: the rule REFUSES a dead end, it does not refuse to play.

    A third piece within reach means a capture is still available after the first one, so the plan
    must come back rather than send the tool off to explore.

    Expected feedback: PASS means the guard is a survivability test and not a mute button. FAIL
    means the tool goes idle on boards it can still make progress on.
    """
    m = _window_board()
    m.pieces = {(2, 1): 0, (2, 2): 0, (2, 3): 0, (2, 4): 0}
    found = plan_moves(m, frozenset(), partial=True)
    assert found is not None and found[0]
    assert found[1] is False


def test_capture_reachable_is_false_once_one_piece_is_left() -> None:
    """Purpose: pin the verdict the guard actually acts on at the losing position.

    Expected feedback: PASS means "no further capture is reachable" is computed, not assumed — it
    is what turns the lf52 win claim into a refusal. FAIL means the guard is deciding on something
    other than reachability.
    """
    m = _window_board()
    after = ((((2, 6), 0),), (), ())
    assert capture_reachable(after, m.sockets, m.rails, frozenset()) is False


def test_non_partial_planning_is_unchanged() -> None:
    """Purpose: a board that fits on screen plans exactly as before.

    Expected feedback: PASS means the change is scoped to partial maps and cannot move a game whose
    board is wholly visible. FAIL means the default path was altered and every clear is at risk.
    """
    m = _window_board()
    m.window = {(r, c) for r in range(-4, 14) for c in range(-4, 14)}
    assert plan_moves(m, frozenset()) == plan_moves(m, frozenset(), partial=False)


def _railhead_board() -> Model:
    """A track that leaves the window on the RIGHT only, with a carrier on it and a piece nearby.

    The shape of lf52 level 6 at the stall. The left end of the run stops in plain view, so exactly
    one direction is open and the assertion on which way to ride is unambiguous.
    """
    m = Model()
    m.pitch, m.oy, m.ox = 6, 0, 0
    for c in range(3, 10):
        m.rails.add((2, c))
    for c in range(0, 10):
        m.sockets.add((3, c))
    m.carriers = {(2, 9)}
    m.rails |= m.carriers
    m.blockers = {(2, 8)}
    m.pieces = {(2, 7): 0, (5, 0): 0}
    m.sockets.add((2, 7))
    m.window = {(r, c) for r in range(0, 9) for c in range(0, 10)}
    return m


def test_railhead_boards_a_carrier_whose_track_leaves_the_screen() -> None:
    """Purpose: the tier that opens a board wider than the frame proposes board-then-drive.

    Expected feedback: PASS means the tool can grow its own map, which the frontier tier provably
    cannot — it is computed in model coordinates where no simulated move changes what is knowable
    (measured: eleven decisions, the known map fixed at 26 cells throughout). FAIL means the tool
    still has no move that widens a window.
    """
    m = _railhead_board()
    moves = railhead_moves(m, frozenset())
    assert moves, "no route onto the open-ended carrier"
    assert moves[-1][0] == "drive", "the ride is what moves the camera; boarding alone reveals none"
    assert moves[0] == ("jump", (2, 7), (0, 1))


def test_railhead_is_silent_when_the_track_stops_in_plain_view() -> None:
    """Purpose: a buffer stop the tool can SEE is not an open end.

    Expected feedback: PASS means the tier costs nothing on boards that fit on screen. FAIL means
    it drives at dead ends and burns the tool's barren budget for nothing.
    """
    m = _railhead_board()
    m.window = {(r, c) for r in range(-4, 14) for c in range(-4, 14)}
    assert railhead_moves(m, frozenset()) == []


def test_railhead_rides_a_carrier_that_already_has_a_passenger() -> None:
    """Purpose: when a piece is already aboard, the move is the drive and nothing else.

    Expected feedback: PASS means no action is spent re-boarding. FAIL means the cheapest opening
    move is being missed in the state it is most obviously available.
    """
    m = _railhead_board()
    m.pieces = {(2, 9): 0}
    assert railhead_moves(m, frozenset()) == [("drive", None, (0, 1))]
