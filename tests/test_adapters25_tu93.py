"""Tests for the TU93 slide-maze adapter's goal-directed exploration lever.

These pin the efficiency change that took TU93 from 637/226 actions per
level (blind nearest-frontier expansion) to 249/65 by biasing exploration
toward the frame-identifiable goal cell. The mechanic model (slide-until-wall
transition graph) is unchanged; only WHICH untried action / frontier cell the
adapter probes next is now goal-directed.
"""

from __future__ import annotations

from admorphiq.adapters25.tu93 import Adapter


def _adapter_with(transitions, goal_cell, active_cell, tried):
    ad = Adapter()
    ad._transitions = list(transitions)
    ad._goal_cell = goal_cell
    ad._active_cell = active_cell
    ad._tried_from = {c: set(s) for c, s in tried.items()}
    return ad


def test_learned_action_dirs_averages_and_drops_self_loops():
    """Purpose: the mean-direction signal each action id carries must be built
    only from transitions that actually MOVED the avatar (self-loops carry no
    direction), averaging the observed (dr, dc) deltas.
    Expected feedback: PASS = action 2's learned direction points purely +row
    (down) and the (0,0) self-loop is ignored; failure means self-loops pollute
    the direction estimate and goal-ward ordering would be misled."""
    ad = Adapter()
    ad._transitions = [
        ((0, 0), 2, (4, 0)),   # down 4
        ((4, 0), 2, (6, 0)),   # down 2
        ((6, 0), 2, (6, 0)),   # self-loop (blocked) -> ignored
        ((0, 0), 4, (0, 3)),   # right 3
    ]
    dirs = ad._learned_action_dirs()
    assert dirs[2] == (3.0, 0.0)   # (4+2)/2 rows, 0 cols
    assert dirs[4] == (0.0, 3.0)
    assert 2 in dirs and set(dirs) == {2, 4}  # only moving actions learned


def test_goal_ward_order_puts_goalward_action_first():
    """Purpose: when the goal lies south-east of the avatar, the untried action
    whose learned mean direction points most toward the goal (here 'down' and
    'right') must be tried before ones pointing away ('up', 'left').
    Expected feedback: PASS = the ranking leads with the goal-ward action;
    failure means probing is still undirected and the efficiency win is lost."""
    transitions = [
        ((0, 0), 1, (-2, 0)),  # up
        ((0, 0), 2, (2, 0)),   # down
        ((0, 0), 3, (0, -2)),  # left
        ((0, 0), 4, (0, 2)),   # right
    ]
    ad = _adapter_with(transitions, goal_cell=(20, 20), active_cell=(0, 0), tried={})
    order = ad._goal_ward_order([1, 2, 3, 4], (0, 0))
    # Goal is down-right -> actions 2 (down) and 4 (right) must lead 1 (up)/3 (left).
    assert order[0] in (2, 4) and order[1] in (2, 4)
    assert order[2] in (1, 3) and order[3] in (1, 3)


def test_goal_ward_order_keeps_unlearned_actions_after_ranked_ones():
    """Purpose: an action with no learned direction yet must not be dropped or
    promoted ahead of a known goal-ward action — it stays available, ordered
    after the ranked ones, so the frontier is still fully explorable.
    Expected feedback: PASS = the goal-ward known action leads and the unknown
    action is retained at the tail; failure means unlearned actions either
    vanish (frontier never fully probed) or wrongly jump the queue."""
    transitions = [((0, 0), 4, (0, 5))]  # only action 4's direction is known
    ad = _adapter_with(transitions, goal_cell=(0, 20), active_cell=(0, 0), tried={})
    order = ad._goal_ward_order([1, 4], (0, 0))
    assert order == [4, 1]


def test_goal_ward_order_falls_back_when_goal_unknown():
    """Purpose: before the goal cell is detected, ordering must be a no-op so
    the frontier is still explored (just not yet biased).
    Expected feedback: PASS = input order preserved when goal_cell is None;
    failure means the adapter reorders on missing information."""
    ad = _adapter_with([((0, 0), 2, (2, 0))], goal_cell=None, active_cell=(0, 0), tried={})
    assert ad._goal_ward_order([3, 1, 2], (0, 0)) == [3, 1, 2]


def test_nearest_untried_prefers_current_cell_free_probe():
    """Purpose: if the avatar's current cell still has an untried action,
    probing it costs no walk and may connect the goal immediately, so it must
    win over any distant frontier cell.
    Expected feedback: PASS = the current cell is returned when it has an
    untried action; failure means the adapter walks away to probe elsewhere
    when a free local probe was available."""
    transitions = [((0, 0), 1, (5, 5))]
    ad = _adapter_with(transitions, goal_cell=(9, 9), active_cell=(0, 0), tried={(0, 0): {1}})
    # (0,0) still has untried 2/3/4 -> returned despite (5,5) being nearer goal.
    assert ad._nearest_untried([1, 2, 3, 4]) == (0, 0)


def test_nearest_untried_picks_goal_nearest_frontier():
    """Purpose: once the current cell is fully probed, the frontier cell CLOSEST
    to the goal must be chosen so exploration heads toward the exit rather than
    the nearest-by-graph-hop cell (the blind behaviour that wasted actions).
    Expected feedback: PASS = the goal-proximal frontier cell is returned;
    failure means exploration still expands undirected and the 11x efficiency
    win regresses."""
    transitions = [
        ((0, 0), 1, (0, 2)),   # near cell, far from goal
        ((0, 0), 2, (8, 8)),   # far cell, near goal (10,10)
    ]
    tried = {(0, 0): {1, 2, 3, 4}, (0, 2): {1}, (8, 8): {1}}
    ad = _adapter_with(transitions, goal_cell=(10, 10), active_cell=(0, 0), tried=tried)
    assert ad._nearest_untried([1, 2, 3, 4]) == (8, 8)
