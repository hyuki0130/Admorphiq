"""Contract tests for the two rules that took wa30 from 8 of 9 levels to 9 of 9.

Both are durable invariants of the shepherd tool, not one-off calibration, and both were wrong in
a way that a whole-game measurement showed and no per-level probe could:

  1. A level whose action allowance runs out RESTARTS, and nothing positional survives that.
     Purpose: prove `_reborn` fires on a restart and — the half that matters more — does NOT fire
     on either of the two things that look like one on their own. Failing the first case means the
     tool replays a dead attempt's endgame on every retry; failing either of the others means it
     throws away a live plan mid-level, which is worse.
  2. A helper that cannot WALK to a piece is not delivering it. Purpose: prove `_start_haul` ranks
     by the route to a helper and not by the straight line, so a helper sealed behind furniture
     stops suppressing the pieces it happens to be near. Failing this means the carrier walks away
     from the only pieces nothing else will ever collect.

Env-free: both run on a hand-built `_Board`, so they test the rule and not the pixel reader.
"""

from __future__ import annotations

from admorphiq.tools.haul import _Board
from admorphiq.tools.shepherd import ShepherdRelayTool


def _board(rows: int, cols: int) -> _Board:
    board = _Board()
    board.side = 4
    board.origin = (0, 0)
    board.rows, board.cols = rows, cols
    return board


def _mid_attempt(tool: ShepherdRelayTool) -> None:
    """Put the tool in the state a restart has to clear: a plan in hand, a piece on the hook."""
    tool._plan = [4, 4, 5]
    tool._offset = (0, 1)
    tool._camped = 3
    tool._actors = {(0, 0): 7}
    tool._fresh = False


def test_reborn_clears_only_on_a_teleport_with_pieces_returning() -> None:
    """A restart is a carrier jump AND pieces reappearing loose; neither half alone.

    Pass means the tool starts the retry from scratch and never abandons a live plan; fail on the
    first case is six identical losing attempts, fail on the others is a plan dropped mid-haul.
    """
    tool = ShepherdRelayTool()
    before = _board(8, 8)
    before.carrier = (7, 7)
    before.bays = {(0, 0), (0, 1), (0, 2)}
    before.cargo = {(0, 0), (0, 1), (5, 5)}          # two delivered, one loose
    _mid_attempt(tool)
    tool._reborn(before)
    assert tool._plan == [4, 4, 5], "the first frame of a level cannot be a restart"

    after = _board(8, 8)
    after.carrier = (0, 0)                            # jumped seven cells back to the start
    after.bays = before.bays
    after.cargo = {(4, 4), (5, 5), (6, 6)}            # all three loose again
    tool._reborn(after)
    assert tool._plan == []
    assert tool._offset is None
    assert tool._camped == 0
    assert tool._fresh is True
    assert tool._actors == {}

    # A jump with no pieces returning: the reader losing the carrier on the frame's edge ring.
    lost = ShepherdRelayTool()
    lost._reborn(before)
    moved = _board(8, 8)
    moved.carrier = (0, 0)
    moved.bays = before.bays
    moved.cargo = set(before.cargo)
    _mid_attempt(lost)
    lost._reborn(moved)
    assert lost._plan == [4, 4, 5], "a mislaid carrier is not a restart"

    # Pieces returning with no jump: thieves emptying bays while the carrier walks.
    raided = ShepherdRelayTool()
    raided._reborn(before)
    robbed = _board(8, 8)
    robbed.carrier = (7, 6)                           # one cell, as a step must be
    robbed.bays = before.bays
    robbed.cargo = {(1, 0), (1, 1), (5, 5)}           # both taken back out
    _mid_attempt(raided)
    raided._reborn(robbed)
    assert raided._plan == [4, 4, 5], "a raid is not a restart"


def test_start_haul_ignores_a_helper_that_cannot_reach_the_piece() -> None:
    """The piece beside a SEALED helper is chosen over the piece a walking helper is near.

    The straight line calls the sealed helper two cells from the right-hand piece and so ranks
    that piece as already-taken-care-of. Pass means the route is what counts; fail means the
    carrier leaves the pieces no helper can ever collect.
    """
    board = _board(5, 11)
    board.carrier = (2, 5)
    board.facing = 4
    #    col 0123456789 10
    # row 2  W . B . . C . . A # S      (# = wall, S sealed in the pocket behind it)
    board.blocked = {(2, 9), (1, 10), (3, 10)}
    board.cargo = {(2, 3), (2, 8)}
    board.bays = {(0, 4), (0, 5)}
    board.hostile = True

    tool = ShepherdRelayTool()
    tool._actors = {(2, 0): 12, (2, 10): 12}          # working helper, sealed helper
    act = tool._start_haul(board, board.carrier)

    assert act == 4, (
        "expected the carrier to set off RIGHT toward the piece the sealed helper cannot reach; "
        f"got {act} with plan {tool._plan}"
    )
    assert tool._plan, "a chosen haul is a whole plan, not one step"
