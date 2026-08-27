"""Tests for the maze tool — the exit grammar it bids on, and the traps it survives."""

from __future__ import annotations

import re

import numpy as np

from admorphiq.tools.maze import MazeRunTool

BACKGROUND = 0
FLOOR = 5
MARK = 9


def _board() -> np.ndarray:
    """A floor with a ring-marked exit and a body whose middle shows the floor through it."""
    grid = np.full((64, 64), BACKGROUND, dtype=int)
    grid[7:57, 7:57] = FLOOR
    grid[8:13, 14:19] = MARK            # the body, five across
    grid[10, 16] = FLOOR                # its middle: the cell the engine actually tests
    grid[49:56, 43:50] = MARK           # the exit ring
    grid[50:55, 44:49] = FLOOR          # hollow
    grid[52, 46] = MARK                 # the loose cell at its centre
    return grid


def test_scene_reads_body_exit_and_floor():
    """Purpose: the board grammar — a hollow ring with a loose cell at its centre is the
    exit, the other region of that colour is the body, and the colour showing through the
    body's own middle is the floor.

    Expected feedback: pass ⇒ the tool can plan on an unseen board of this family; fail ⇒
    it is steering the wrong object or walking on the wrong colour.
    """
    scene = MazeRunTool()._scene(_board())
    assert scene is not None
    assert scene.body == (10, 16)
    assert scene.exit == (52, 46)
    assert scene.floor == FLOOR
    assert scene.background == BACKGROUND


def test_ring_without_a_centre_mark_is_not_an_exit():
    """Purpose: the mark at the ring's centre is what makes the ring an exit rather than a
    frame, a counter, or a window.

    Expected feedback: pass ⇒ the tool will not steer toward decoration; fail ⇒ its bid is
    resting on "a rectangle is somewhere on the board".
    """
    grid = _board()
    grid[52, 46] = FLOOR
    assert MazeRunTool()._scene(grid) is None


def test_no_bid_without_the_grammar():
    """Purpose: ⛔ detect must be 0.0 when the tool has no plan. A tool that bids on a
    resemblance takes the turn from one that could have solved the board — measured at
    0.4286 of another game's score.

    Expected feedback: pass ⇒ bidding only where it can act; fail ⇒ it will steal turns.
    """
    class Obs:
        def __init__(self, grid):
            self.frame = [grid.tolist()]
            self.available_actions = [1, 2, 3, 4, 5]
            self.state = "NOT_FINISHED"
            self.levels_completed = 0

    tool = MazeRunTool()
    assert tool.detect([], Obs(_board())) > 0.0
    blank = np.full((64, 64), BACKGROUND, dtype=int)
    blank[7:57, 7:57] = FLOOR
    assert tool.detect([], Obs(blank)) == 0.0


def test_a_jump_home_is_the_rewind_and_a_jump_elsewhere_is_not():
    """Purpose: pins the two displacements that are not steps. Landing back on the start is
    the rewind, which arrives one action after the control that asked for it; landing
    anywhere else is the board moving the body (linked pads swap their occupants).

    Expected feedback: pass ⇒ neither is charged to a working direction; fail ⇒ the tool
    retires a control it needs and strands itself.
    """
    tool = MazeRunTool()
    assert tool._is_step((6, 0), 6)
    assert not tool._is_step((6, 6), 6)
    assert not tool._is_step((0, -24), 6)


def test_no_game_specifics_in_source():
    """Purpose: generality guard — the tool must contain no game ids, titles, or sprite
    tags so it transfers to the unseen private games.

    Expected feedback: pass ⇒ frame-only and portable; fail ⇒ a game-specific leak crept
    in and the tool won't generalize.
    """
    import admorphiq.tools.maze as mod

    src = open(mod.__file__).read().lower()
    for tok in ("game_id", "game_title", "sprite"):
        assert tok not in src
    assert not re.search(r"\b[a-z]{2}\d{2}\b", src)


def test_route_carries_the_latch_state():
    """Purpose: a latching door is opened by ARRIVING on its plate, and arriving again shuts
    it. The search state is therefore (cell, latch bits), not cell — a route that crosses the
    plate on its way out must account for having flipped the door behind it.

    Expected feedback: pass ⇒ routes stay valid once walked; fail ⇒ the tool plans a route,
    walks two steps of it across the plate, finds the door it needed now shut, and turns round.
    """
    tool = MazeRunTool()
    tool._delta = {1: (-6, 0), 2: (6, 0), 3: (0, -6), 4: (0, 6)}
    #  plate at (10, 10) drives the door at (10, 22); the only way on is through both.
    tool._gates = {(10, 22): (10, 10)}
    tool._latched = {(10, 10)}
    free = {(10, 4), (10, 10), (10, 16), (10, 28)}

    tool._flip = {}                       # door shut: the plate has to be crossed to open it
    assert tool._route((10, 4), {(10, 28)}, free) == [(10, 10), (10, 16), (10, 22), (10, 28)]

    tool._flip = {(10, 22): True}         # already open, and crossing the plate would shut it
    assert tool._route((10, 16), {(10, 28)}, free) == [(10, 22), (10, 28)]


def test_a_clone_holding_a_plate_is_not_a_latch():
    """Purpose: separates the two ways a door can be open with the body elsewhere — it latched,
    or a clone is standing on its plate. Only the first means no clone is needed.

    Expected feedback: pass ⇒ clone-held doors are still treated as costing a clone; fail ⇒ the
    tool retires the very plate its clone was spent on and has none left for the next one.
    """
    tool = MazeRunTool()
    grid = np.full((64, 64), BACKGROUND, dtype=int)
    tool._palette = {BACKGROUND, FLOOR, MARK}
    grid[20:25, 20:25] = 3                # a colour the level did not start with = a clone
    near = tool._aliens(grid, grid, 2)
    assert near[22, 22] and near[19, 19]
    assert not near[40, 40]
