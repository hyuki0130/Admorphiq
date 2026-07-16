"""Tests for the G50T momentary-plate + record-replay-ghost adapter (2026-07-16).

G50T L0 is an Adventures-of-Lolo puzzle whose single-cell barrier is opened
ONLY while a body stands on a MOMENTARY pressure plate; with one player it is
crossed by banking an ACTION5 ghost that seats on the plate and holds it open
while the reset player walks through (see the adapter module docstring). These
tests pin the pure, load-bearing pieces: the closed-loop hop selector, the
plate-candidate ordering, and — the crux — that the time-gated route BFS only
crosses a barrier cell AFTER the ghost has seated (move index > Lg). The live
first-clear itself (1/7 @ 0.0357, deterministic) is proven by the script25
measurement, not by a unit test.
"""

from __future__ import annotations

from types import SimpleNamespace

from arcengine import GameAction

from admorphiq.adapters25.g50t import Adapter


def _frame(grid: list[list[int]], levels: int = 0, state: str = "NOT_FINISHED") -> SimpleNamespace:
    return SimpleNamespace(
        frame=[[list(row) for row in grid]],
        state=SimpleNamespace(name=state),
        available_actions=[1, 2, 3, 4, 5],
        levels_completed=levels,
    )


def test_hop_picks_the_cardinal_action_toward_an_adjacent_target():
    """Purpose: every drive is a sequence of one-cell closed-loop hops; _hop must
    return the measured action id (1=up, 2=down, 3=left, 4=right) that steps from
    the player's cell toward the adjacent target.
    Expected feedback: failure means the driver walks the wrong direction and the
    ghost/player desync, so no route ever completes."""
    ad = Adapter()
    moves = [1, 2, 3, 4]
    assert ad._hop((5, 5), (4, 5), moves) == 1  # up
    assert ad._hop((5, 5), (6, 5), moves) == 2  # down
    assert ad._hop((5, 5), (5, 4), moves) == 3  # left
    assert ad._hop((5, 5), (5, 6), moves) == 4  # right


def test_frontier_circuit_orders_plate_candidates_farthest_from_goal_first():
    """Purpose: on L0 the barrier sits between the chamber and the goal, so the
    true plate is the frontier colour-8 cell FARTHEST from the goal; trying it
    first avoids a wasted probe on the barrier.
    Expected feedback: failure means discovery probes the barrier first (a wasted
    blocked move) or, worse, mis-picks it as the plate."""
    ad = Adapter()
    ad._off = (0, 0)  # cell (i, j) center is pixel (6i, 6j)
    ad._goal_cell = (10, 10)
    # 13x13 canvas; paint cell centres. Reachable floor at (0,0),(0,1),(1,1);
    # a colour-8 plate candidate at (0,2) [near-ish the goal] and one at (1,0)
    # [farthest]. _frontier_circuit reads colour at 6px-spaced cell centres.
    g = [[0] * 13 for _ in range(13)]
    for i, j in ((0, 0), (0, 1), (1, 1)):
        g[6 * i][6 * j] = 5
    g[6 * 0][6 * 2] = 8  # cell (0,2)
    g[6 * 1][6 * 0] = 8  # cell (1,0)
    grid = tuple(tuple(r) for r in g)
    reachable = {(0, 0), (0, 1), (1, 1)}
    order = ad._frontier_circuit(grid, reachable)
    assert order[0] == (1, 0)  # dist |1-10|+|0-10| = 19 (farthest) tried first


def test_gated_route_crosses_barrier_only_after_the_ghost_seats():
    """Purpose: THE load-bearing invariant. The ghost seats on the plate at the
    end of the player's Lg-th move and the engine validates the player's move
    BEFORE the ghost's replay in the same step, so a barrier cell is enterable
    only from the (Lg+1)-th move onward. The route BFS must therefore pad the
    player's path so it never enters a barrier cell at or before move Lg.
    Expected feedback: failure means the player walks into a still-closed barrier
    (a blocked no-op) and the run stalls forever — exactly the bug that made the
    first FSM hang at the barrier cell."""
    ad = Adapter()
    ad._start_cell = (0, 0)
    ad._goal_cell = (0, 4)
    # a straight corridor start..barrier..goal, plus a side cell (1,0) to wiggle.
    ad._base_floor = {(0, 0), (0, 1), (0, 2), (1, 0)}
    ad._barrier = {(0, 3)}
    ad._lg = 3
    route = ad._build_gated_route()
    assert route, "a gated route to the goal must exist"
    assert route[-1] == (0, 4)
    # move index is 1-based; the barrier cell must be entered strictly after Lg.
    for idx, cell in enumerate(route, start=1):
        if cell in ad._barrier:
            assert idx > ad._lg, f"barrier entered at move {idx} <= Lg {ad._lg}"


def test_gated_route_is_empty_when_no_path_exists():
    """Purpose: an unsolvable configuration (goal disconnected from the reachable
    floor) must return no route so the adapter degrades to its bounded explorer
    instead of emitting a bad plan.
    Expected feedback: failure means the adapter commits to an impossible plan and
    never falls back."""
    ad = Adapter()
    ad._start_cell = (0, 0)
    ad._goal_cell = (5, 5)  # disconnected from the floor
    ad._base_floor = {(0, 0), (0, 1)}
    ad._barrier = set()
    ad._lg = 0
    assert ad._build_gated_route() == []


def test_choose_action_always_returns_a_gameaction_on_a_blank_frame():
    """Purpose: every FSM branch must return a real GameAction — a raw-int return
    once crashed the env loop early. Drive a featureless frame (no movers) and
    assert the adapter still yields a valid action without raising.
    Expected feedback: failure means a code path returns a non-GameAction / raises
    and aborts the whole game run."""
    ad = Adapter()
    ad._levels_seen = 0  # suppress the level-up reset so state persists
    blank = [[0] * 24 for _ in range(24)]
    for _ in range(6):
        a = ad.choose_action([], _frame(blank))
        assert isinstance(a, GameAction)
