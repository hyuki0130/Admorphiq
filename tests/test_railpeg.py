"""Contract tests for the two railpeg defects that stopped lf52 at level 6.

Both are properties of SCROLLING boards in general, not of lf52: a tool whose model holds only
what the camera has shown must not mistake a predicate over that model for a predicate over the
board, and its "go and look" tier must be able to want to GET ON a cart rather than only to ride
one it is already on.
"""
from __future__ import annotations

from collections import Counter

from admorphiq.tools.railpeg import (
    Model,
    _novelty_field,
    _rail_reach,
    plan_level,
    railhead_moves,
    travel_moves,
)


def _ladder_board() -> Model:
    """A row of holes with a long track leaving it, two pieces of different colours at one end.

    Two colours because a lone piece cannot move at all — every jump needs something to jump over,
    so a piece of another colour is the only ladder a board like this offers.
    """
    m = Model()
    m.pitch = 6
    m.sockets = {(0, c) for c in range(5)}
    m.rails = {(0, c) for c in range(5, 21)}
    m.carts = {(0, 5)}
    m.pieces = {(0, 0): 14, (0, 1): 8}
    # ⚠️ The window covers one cell PAST the end of the track, so this board's far end is a buffer
    # stop the tool can SEE is a buffer stop. That is what makes the three tests below about
    # `_rail_reach`'s ordinary arithmetic rather than about the frontier bonus, which only applies
    # where the track runs out of screen — see the narrow-window test at the end of this file.
    m.window = {(0, c) for c in range(-1, 22)}
    return m


def test_rail_reach_scores_a_cart_by_the_track_it_rides_not_the_cell_it_sits_on() -> None:
    """Purpose: pin the term that makes boarding rankable — every cell of a rail component is
    worth that component's FARTHEST novelty, so a cart parked next to worked ground still scores
    for the territory its track opens.

    Expected feedback: a pass means "go and get on that cart" can outrank "walk one more hole".
    A fail means the boarding objective has collapsed back to the cart's own cell, which is the
    measured state in which thirty-two travel plans produced zero boardings.
    """
    m = _ladder_board()
    field = _novelty_field(m, touched={(0, 0), (0, 1)})
    reach = _rail_reach(m, field)
    # the cart sits four cells from worked ground, but its track runs to the far end
    assert field[(0, 5)] == 4
    assert reach[(0, 5)] == field[(0, 20)] == 19
    # every cell of one component shares the component's maximum, which is what makes it a plan
    assert len({reach[c] for c in m.rails}) == 1


def test_rail_reach_stays_quiet_when_the_track_goes_nowhere() -> None:
    """Purpose: the boarding bonus must be selective. A stub of track beside ground the pieces
    have already worked opens nothing, and boarding it must not outrank ordinary play.

    Expected feedback: a pass means the term is a statement about THIS board's track rather than a
    standing preference for carts. A fail means any board drawing a rail would pull the tool onto
    it, which is how a tier that pays on one game costs every other one.
    """
    long_track = _ladder_board()
    stub = _ladder_board()
    stub.rails = {(0, 5)}
    stub.carts = {(0, 5)}
    touched = {(0, 0), (0, 1)}
    long_reach = _rail_reach(long_track, _novelty_field(long_track, touched))[(0, 5)]
    stub_field = _novelty_field(stub, touched)
    stub_reach = _rail_reach(stub, stub_field)[(0, 5)]
    # ⛔ Two wrong versions of this assertion before the right one, and both were wrong about the
    # BOARD rather than about the code. "The stub scores zero" ignored that it sits past worked
    # ground; "the stub must not outrank ordinary play" ignored that the stub IS the farthest cell
    # on its row, so boarding it is worth exactly as much as walking there and no more. The
    # contract is that a cart carries no bonus of its own: it is worth precisely where its track
    # can take a piece, which is its own cell when the track stops there.
    assert stub_reach == stub_field[(0, 5)], "a track that ends here is worth exactly here"
    assert long_reach > 4 * stub_reach, "a track that goes somewhere is worth where it goes"


def test_travel_boards_the_cart_when_the_track_leaves_the_worked_region() -> None:
    """Purpose: the tier that exists to go and look must produce a plan that ENDS WITH A PIECE ON A
    CART when the only route onward is that cart.

    Expected feedback: a pass means the plan that clears a board wider than its screen is now
    reachable by search rather than only by hand. A fail means travel is again proposing drives and
    shuffles that never board, which is exactly the measured failure on lf52 level 6.
    """
    m = _ladder_board()
    moves = travel_moves(m, noncapture=frozenset(), touched={(0, 0), (0, 1)}, visited=set())
    assert moves, "travel produced no plan at all on a board with somewhere to go"
    # replay the jumps to see where the pieces end up; a boarding is a jump landing on a cart
    landings = [(c[0] + 2 * d[0], c[1] + 2 * d[1]) for kind, c, d in moves if kind == "jump"]
    assert any(land in m.carts for land in landings), (
        f"no move lands on a cart; plan was {moves}")


def test_a_track_running_off_the_screen_outranks_every_cell_on_the_map() -> None:
    """Purpose: novelty is measured over cells the tool KNOWS, so the only destination worth the
    journey — board it has never seen — scores exactly zero. A rail component whose continuation is
    off SCREEN (not merely absent) must therefore be worth more than any known cell can be.

    Expected feedback: a pass means "the track leaves the picture" is a reason to ride, which is
    what a board wider than its window needs. A fail means the tool arrives at the edge of its own
    map and reports, correctly on that map, that nothing gains — the measured state in which it
    grew its map from 61 cells to 99 and was then retired with the board unfinished.
    """
    m = _ladder_board()
    m.window = {(0, c) for c in range(0, 11)}      # the track leaves the picture at column 10
    field = _novelty_field(m, touched={(0, 0), (0, 1)})
    reach = _rail_reach(m, field)
    assert reach[(0, 5)] > max(field.values()), "an open track must outrank the whole known map"

    stopped = _ladder_board()                      # identical board, far end in plain view
    assert _rail_reach(stopped, field)[(0, 5)] == max(field.values()), (
        "a track whose end can be SEEN is worth its end and no more")


def test_railhead_drives_a_laden_cart_at_the_gap_in_the_screen_and_only_then() -> None:
    """Purpose: `_shunt` rolls a cart only onto a cell the model already calls track, so at the edge
    of the known map every ride stops one cell short of the only place worth going. The railhead
    tier makes that one move; it must require a PASSENGER (the camera follows a piece, so an empty
    cart driven off the map reveals nothing) and must not fire where the track visibly ends.

    Expected feedback: a pass means the tool can learn track it has never seen, at a cost of one
    action and — because a refused drive is now read — never twice. A fail means the frontier is
    unreachable and the tool goes barren at the edge of its own map.
    """
    def frontier(window_to: int) -> Model:
        """A cart at the last cell of track the tool has mapped, `window_to` the last cell it can
        currently SEE — so window_to == 10 puts the track's end at the edge of the picture and
        window_to == 11 shows the plain floor beyond it."""
        m = Model()
        m.pitch = 6
        m.sockets = {(0, c) for c in range(5)}
        m.rails = {(0, c) for c in range(5, 10)}
        m.carts = {(0, 10)}
        m.pieces = {(0, 0): 14, (0, 1): 8}
        m.window = {(0, c) for c in range(0, window_to + 1)}
        return m

    assert railhead_moves(frontier(10)) == [], "an empty cart must not be driven off the map"

    laden = frontier(10)
    laden.pieces[(0, 10)] = 14                     # a passenger boards the cart
    assert railhead_moves(laden) == [("drive", None, (0, 1))], "drive at the gap in the screen"

    seen = frontier(11)                            # same board, the floor beyond in plain view
    seen.pieces[(0, 10)] = 14
    assert railhead_moves(seen) == [], "nothing to learn where the track visibly stops"

    twice = frontier(10)
    twice.pieces[(0, 10)] = 14
    assert railhead_moves(twice, refused=Counter({((0, 1), (0, 10)): 2})) == [], (
        "a direction the engine has already refused twice is not track")


def test_a_local_win_is_not_claimed_once_the_board_is_known_to_be_wider_than_the_screen() -> None:
    """Purpose: `_won` counts the pieces in the MODEL. On a scrolling board the model is a fraction
    of the board, so `refuse_local_win` must stop the planner reporting `solved`.

    Expected feedback: a pass means the tool keeps the useful route (the captures are still
    planned) while dropping the false claim, and so goes looking instead of replaying the same
    "win". A fail means it returns to claiming the same local win over and over — measured at
    forty-three claims on one level, with the tier that would have gone looking never reached.
    """
    m = Model()
    m.pitch = 6
    m.sockets = {(0, c) for c in range(6)}
    m.pieces = {(0, 0): 14, (0, 1): 14, (0, 3): 14}
    m.window = set(m.sockets)

    honest = plan_level(m, noncapture=frozenset())
    assert honest is not None and honest[1] is True, "the visible board really is solvable locally"

    guarded = plan_level(m, noncapture=frozenset(), refuse_local_win=True)
    assert guarded is not None, "refusing the CLAIM must not throw the route away"
    assert guarded[1] is False, "a win seen through a camera is not a win"
    assert guarded[0], "the plan must still contain the moves that take real captures"
