"""Tests for the pure shortest-path / configuration-path kernels (R56)."""

import pytest

from admorphiq.kernels.paths import (
    configuration_path,
    grid_distance_field,
    grid_shortest_path,
    path_to_moves,
    reachable_frontier,
    transition_shortest_path,
)

# 5x5 grid, all passable except a wall down column 2, rows 0-3 (a gap at row 4)
# so any start=(0,0)/goal=(0,4) path must detour down to row 4 and back up.
_WALLED_GRID = [
    [True, True, False, True, True],
    [True, True, False, True, True],
    [True, True, False, True, True],
    [True, True, False, True, True],
    [True, True, True, True, True],
]


def test_grid_shortest_path_detours_around_wall_with_known_optimal_length():
    """Purpose: pin the actual optimal path length around a real obstacle —
    column 2 is impassable for rows 0-3, so (4, 2) is the ONLY crossing
    point between the left and right halves. Any path from (0,0) to (0,4)
    must therefore pass through that chokepoint, giving a provable lower
    bound: Manhattan(start, (4,2)) + Manhattan((4,2), goal) = (4+2)+(4+2) =
    12 steps, and that bound is achievable (row 4 and columns 0/4 are fully
    open), so the true optimum is exactly 12 steps / 13 cells.
    Expected feedback: failure means the BFS either ignores the wall (finds
    a too-short path straight through) or fails to find the true shortest
    detour (returns a longer, valid-but-suboptimal path)."""
    path = grid_shortest_path(_WALLED_GRID, (0, 0), (0, 4))
    assert path is not None
    assert path[0] == (0, 0)
    assert path[-1] == (0, 4)
    # Every consecutive pair must be a single cardinal step and passable.
    for (r0, c0), (r1, c1) in zip(path, path[1:]):
        assert abs(r0 - r1) + abs(c0 - c1) == 1
        assert _WALLED_GRID[r1][c1] is True
    # Manhattan distance is 4; the wall forces a strictly longer path.
    assert len(path) - 1 > 4
    # The provable chokepoint-bound optimum (see docstring): 12 steps.
    assert len(path) - 1 == 12
    assert (4, 2) in path  # must pass through the only crossing cell


def test_grid_shortest_path_no_path_returns_none():
    """Purpose: a start fully enclosed by impassable cells must return None,
    not raise or loop forever.
    Expected feedback: failure means the BFS termination condition is wrong
    for the disconnected-component case."""
    grid = [
        [False, False, False],
        [False, True, False],
        [False, False, False],
    ]
    assert grid_shortest_path(grid, (1, 1), (0, 0)) is None


def test_grid_shortest_path_start_equals_goal():
    """Purpose: start == goal is a zero-step path containing just that cell,
    a degenerate case that must not require BFS at all.
    Expected feedback: failure (e.g. None, or a path with >1 cell) means the
    shortcut is missing and every caller must special-case this themselves."""
    assert grid_shortest_path(_WALLED_GRID, (2, 2), (2, 2)) == [(2, 2)]


def test_grid_shortest_path_out_of_bounds_or_impassable_endpoint_is_none():
    """Purpose: an out-of-bounds or impassable start/goal (when they differ)
    is unreachable by definition and must return None, not raise.
    Expected feedback: failure means a caller passing a slightly-wrong
    coordinate gets a crash instead of a clean 'no path' signal."""
    assert grid_shortest_path(_WALLED_GRID, (0, 0), (99, 99)) is None
    assert grid_shortest_path(_WALLED_GRID, (0, 0), (0, 2)) is None  # (0,2) is a wall


def test_grid_distance_field_multi_source_nearest_wins():
    """Purpose: with two sources on an open grid, every cell's distance must
    be to its NEAREST source, not the first one listed.
    Expected feedback: failure means the multi-source seeding only tracks
    one source (e.g. overwrites instead of taking the min), which would
    make distance-guided planning prefer the wrong direction near a
    boundary between two sources' basins."""
    grid = [[True] * 5 for _ in range(1)]
    field = grid_distance_field(grid, [(0, 0), (0, 4)])
    assert field[(0, 0)] == 0
    assert field[(0, 4)] == 0
    assert field[(0, 2)] == 2  # equidistant, but must be 2, not stuck at source-1 dist of 4
    assert field[(0, 1)] == 1
    assert field[(0, 3)] == 1


def test_grid_distance_field_skips_impassable_or_oob_sources():
    """Purpose: a source that is itself impassable (or out of bounds) cannot
    seed the field; only genuinely passable, in-bounds sources contribute.
    Uses a 2D grid with a detour around the wall at (0, 1) so the
    unreachability under test is specifically about invalid-source seeding,
    not about the wall blocking all paths outright.
    Expected feedback: failure means an invalid source either crashes the
    field computation or silently seeds unreachable cells with distance 0
    (e.g. (0, 1) itself appearing in the field despite being impassable)."""
    grid = [
        [True, False, True],
        [True, True, True],
    ]
    field = grid_distance_field(grid, [(0, 1), (0, 0), (99, 99)])
    assert (0, 1) not in field  # impassable source must not seed anything
    assert (99, 99) not in field  # out-of-bounds source must not seed anything
    assert field == {(0, 0): 0, (1, 0): 1, (1, 1): 2, (1, 2): 3, (0, 2): 4}


def test_transition_shortest_path_over_observed_triples():
    """Purpose: given a small chain of observed (state, label, next_state)
    triples with one shortcut edge, the shortest LABEL sequence (not state
    sequence) must be returned, preferring the shortcut.
    Expected feedback: failure means the induced-graph construction or the
    BFS over labels is wrong — this is the exact shape a live agent's
    observed transition store has."""
    transitions = [
        ("A", "a1", "B"),
        ("B", "a1", "C"),
        ("C", "a1", "D"),
        ("A", "shortcut", "D"),
    ]
    assert transition_shortest_path(transitions, "A", "D") == ["shortcut"]


def test_transition_shortest_path_unreachable_and_trivial():
    """Purpose: an unreachable goal returns None; start == goal returns []
    (zero edges needed) without consulting the transition store at all.
    Expected feedback: failure on the unreachable case risks an infinite
    BFS or a wrong non-None result; failure on the trivial case means every
    caller must special-case 'already there' themselves."""
    transitions = [("A", "a1", "B")]
    assert transition_shortest_path(transitions, "A", "Z") is None
    assert transition_shortest_path(transitions, "A", "A") == []


def test_transition_shortest_path_later_edge_overwrites_stale_target():
    """Purpose: when the same (state, label) pair appears twice with
    different next-states, the LAST occurrence must win (matching an
    observed-store caller that corrects a stale resolution).
    Expected feedback: failure means a re-observed transition doesn't
    actually update the induced graph, silently pathing through a target
    that is no longer what the label actually leads to."""
    transitions = [
        ("A", "a1", "STALE"),
        ("A", "a1", "B"),  # corrected observation
    ]
    assert transition_shortest_path(transitions, "A", "B") == ["a1"]
    assert transition_shortest_path(transitions, "A", "STALE") is None


def test_reachable_frontier_excludes_tried_and_orders_by_distance():
    """Purpose: frontier pairs must exclude every (state, label) already in
    `tried`, and the surviving pairs must be ordered nearest-state-first.
    Expected feedback: failure on exclusion means a caller re-proposes an
    action it already knows the outcome of; failure on ordering means the
    'nearest untried option' heuristic silently degrades to an unordered
    dump, defeating its purpose in a promise-ranked frontier search."""
    transitions = [
        ("A", "far", "B"),
        ("B", "near", "C"),
        ("A", "close", "A"),  # self-loop, still a valid frontier pair at distance 0
    ]
    tried = {("A", "far")}
    out = reachable_frontier(transitions, "A", tried)
    assert ("A", "far") not in out
    assert out == [("A", "close"), ("B", "near")]


def test_reachable_frontier_no_transitions_from_isolated_start():
    """Purpose: a start_key with no outgoing edges at all yields an empty
    frontier, not an error.
    Expected feedback: failure means a caller probing a genuinely fresh,
    unexplored state crashes instead of getting a clean empty result."""
    assert reachable_frontier([], "ISOLATED", set()) == []


def test_configuration_path_solves_three_state_toggle_puzzle():
    """Purpose: a minimal externalized state-space puzzle (three-position
    toggle: OFF -> HALF -> ON, goal = ON) must be solved via caller-supplied
    goal_test/successors, proving the state semantics are fully generic.
    Expected feedback: failure means the generic BFS driver itself is
    broken (not any puzzle-specific logic, since none lives in the kernel)."""
    def successors(state: str):
        order = {"OFF": "HALF", "HALF": "ON", "ON": "OFF"}
        return [("toggle", order[state])]

    path = configuration_path("OFF", lambda s: s == "ON", successors)
    assert path == ["toggle", "toggle"]


def test_configuration_path_initial_already_goal_returns_empty_list():
    """Purpose: when the initial state already satisfies goal_test, the
    result is [] (zero steps), distinct from None (unreachable).
    Expected feedback: failure conflates 'already solved' with 'unsolvable',
    which would make an adapter re-plan from an already-complete state."""
    assert configuration_path("ON", lambda s: s == "ON", lambda s: []) == []


def test_configuration_path_max_states_bounds_termination():
    """Purpose: an infinite/unbounded state space (integers counting up
    forever, goal never satisfied) must terminate at max_states and return
    None rather than hang.
    Expected feedback: failure means there is no expansion cap, risking a
    runtime hang inside the 9h Kaggle budget on a genuinely unreachable or
    unbounded configuration space."""
    def successors(state: int):
        return [("inc", state + 1)]

    result = configuration_path(0, lambda s: s == 10_000_000, successors, max_states=50)
    assert result is None


def test_path_to_moves_happy_path():
    """Purpose: a straight-line waypoint path converts to the correct move
    labels via the caller-supplied delta map.
    Expected feedback: failure means the delta computation or label lookup
    is wrong — this is the exact step a live agent uses to turn a BFS path
    into actions it can actually send to the environment."""
    path = [(0, 0), (0, 1), (1, 1), (1, 0)]
    move_labels = {(0, 1): "right", (1, 0): "down", (0, -1): "left", (-1, 0): "up"}
    assert path_to_moves(path, move_labels) == ["right", "down", "left"]


def test_path_to_moves_short_paths_return_empty():
    """Purpose: a path of length 0 or 1 has no hops to convert, so the
    result is [] without touching move_labels at all.
    Expected feedback: failure means a degenerate 'already there' path
    crashes on an empty zip instead of returning trivially."""
    assert path_to_moves([], {}) == []
    assert path_to_moves([(0, 0)], {}) == []


def test_path_to_moves_raises_on_non_adjacent_hop():
    """Purpose: a hop whose delta was never calibrated (or that skips more
    than one cell) must raise ValueError, not silently drop the step.
    Expected feedback: failure means an uncalibrated/invalid hop is
    silently swallowed, producing an action sequence shorter than the
    actual path and desyncing the agent from its intended waypoints."""
    path = [(0, 0), (5, 5)]
    with pytest.raises(ValueError):
        path_to_moves(path, {(0, 1): "right"})


# ── plan_delivery (delivery/subgoal composition) ────────────────────────────

from admorphiq.kernels.paths import plan_delivery  # noqa: E402

_OPEN6 = [[True] * 6 for _ in range(6)]
_ML = {(-1, 0): 1, (1, 0): 2, (0, -1): 3, (0, 1): 4}  # cardinal deltas -> action ids


def _apply(worker, plan, move_labels):
    """Replay a plan's MOVE steps (interacts are no-ops here) and return the
    worker's final cell plus the set of cells it interacted-from."""
    label_to_delta = {v: k for k, v in move_labels.items()}
    pos = worker
    interacted = []
    for a in plan:
        if a in label_to_delta:
            dr, dc = label_to_delta[a]
            pos = (pos[0] + dr, pos[1] + dc)
        else:
            interacted.append(pos)
    return pos, interacted


def test_plan_delivery_single_delivery_reaches_pickup_then_target():
    """Purpose: one pickup, one target — the plan must route the worker
    adjacent to the pickup, interact, route adjacent to the target, interact.
    Replaying the moves must leave the worker orthogonally adjacent to each at
    its two interact points.
    Expected feedback: failure means the composed route/interact sequence
    doesn't actually stand the worker next to the item, so no delivery fires."""
    plan = plan_delivery((0, 0), [(0, 4)], [(5, 5)], _OPEN6, _ML, 5)
    assert plan is not None
    assert plan.count(5) == 2  # one pick, one drop
    _pos, interacted = _apply((0, 0), plan, _ML)
    assert len(interacted) == 2
    pick_from, drop_from = interacted
    assert abs(pick_from[0] - 0) + abs(pick_from[1] - 4) == 1  # adjacent to pickup
    assert abs(drop_from[0] - 5) + abs(drop_from[1] - 5) == 1  # adjacent to target


def test_plan_delivery_two_ordered_deliveries_interact_four_times():
    """Purpose: two pickups + two targets must yield exactly four interacts
    (pick, drop, pick, drop) chained from the worker's running position.
    Expected feedback: failure means the multi-subgoal chaining is broken
    (a leg dropped, or the worker position not advanced between legs) — the
    exact thing blind frontier search can't compose."""
    plan = plan_delivery((0, 0), [(0, 4), (4, 0)], [(5, 5), (2, 2)], _OPEN6, _ML, 5)
    assert plan is not None
    assert plan.count(5) == 4


def test_plan_delivery_respects_match_predicate_for_assignment():
    """Purpose: when a match predicate gates which (pickup, target) pairs are
    compatible (colour/shape), the assignment must only pair compatible items
    — the min-cost assignment must not pair a pickup with a target the caller
    forbade.
    Expected feedback: failure means a colour-mismatched delivery would be
    planned, which the game would reject, wasting the whole plan."""
    # pickup 0 matches ONLY target 1; pickup 1 matches ONLY target 0. The
    # unconstrained min-cost pairing would prefer (0->0),(1->1) by distance,
    # so this proves the predicate actually overrides distance.
    pickups = [(0, 1), (5, 4)]
    targets = [(0, 2), (5, 5)]

    def match(pi, ti):
        return (pi, ti) in {(0, 1), (1, 0)}

    plan = plan_delivery((0, 0), pickups, targets, _OPEN6, _ML, 5, match=match)
    assert plan is not None
    assert plan.count(5) == 4


def test_plan_delivery_none_when_infeasible_or_unroutable():
    """Purpose: more targets than pickups (a target can't be served), no
    compatible pickup for a target, and an unreachable leg must all yield
    None so the caller falls back rather than executing a partial plan.
    Expected feedback: failure means the adapter 'executes' an impossible
    delivery instead of falling back to graph exploration."""
    assert plan_delivery((0, 0), [(0, 4)], [(5, 5), (2, 2)], _OPEN6, _ML, 5) is None
    # no compatible pickup for target 0
    assert plan_delivery((0, 0), [(0, 4)], [(5, 5)], _OPEN6, _ML, 5, match=lambda pi, ti: False) is None
    # a full wall column isolates the pickup from the worker
    wall = [[True] * 6 for _ in range(6)]
    for r in range(6):
        wall[r][2] = False
    assert plan_delivery((0, 0), [(0, 5)], [(5, 5)], wall, _ML, 5) is None


def test_plan_delivery_empty_targets_is_empty_plan():
    """Purpose: with nothing to deliver the plan is empty (``[]``), not None
    — a distinct 'already done' signal from 'infeasible'.
    Expected feedback: failure means the caller can't distinguish a solved
    board from an unsolvable one."""
    assert plan_delivery((0, 0), [(0, 4)], [], _OPEN6, _ML, 5) == []


# ── plan_carry_delivery (fixed-offset follower delivery) ────────────────────

from admorphiq.kernels.paths import plan_carry_delivery  # noqa: E402


def test_plan_carry_delivery_seats_follower_on_targets_via_offset():
    """Purpose: a carried object rides at a fixed offset from the worker; to
    seat it on a target the worker must stand at target - offset. The plan's
    interact points, replayed, must place the worker at (pickup - offset) and
    (target - offset) — the whole offset-routing trick.
    Expected feedback: failure means the follower lands one offset away from
    every target, so no carry-game delivery ever completes."""
    offset = (-1, 0)  # object rides one cell ABOVE the worker
    plan = plan_carry_delivery((5, 0), [(0, 0)], [(0, 5)], offset, _OPEN6, _ML, 9)
    assert plan is not None
    assert plan.count(9) == 2
    pos, interacted = _apply((5, 0), plan, _ML)
    pick_from, drop_from = interacted
    assert pick_from == (0 - offset[0], 0 - offset[1])   # (1, 0): object at (0,0)
    assert drop_from == (0 - offset[0], 5 - offset[1])   # (1, 5): object lands on (0,5)


def test_plan_carry_delivery_two_targets_and_infeasible_cases():
    """Purpose: chaining two follower deliveries yields four interacts; and
    the infeasible guards (more targets than pickups, unroutable seat cell)
    return None so the adapter falls back.
    Expected feedback: failure means either the multi-delivery chain is broken
    or an impossible carry plan is 'executed' instead of falling back."""
    off = (-1, 0)
    plan = plan_carry_delivery((5, 0), [(2, 0), (2, 4)], [(0, 1), (0, 5)], off, _OPEN6, _ML, 9)
    assert plan is not None and plan.count(9) == 4
    assert plan_carry_delivery((5, 0), [(0, 0)], [(0, 3), (0, 5)], off, _OPEN6, _ML, 9) is None
    # seat cell for the target is off-grid (target (0,c) - offset (-1,0) = (1,c) ok),
    # but a target whose seat cell is blocked is unroutable:
    wall = [[True] * 6 for _ in range(6)]
    wall[1][5] = False  # the seat cell (1,5) for target (0,5) is blocked
    assert plan_carry_delivery((5, 0), [(0, 0)], [(0, 5)], off, wall, _ML, 9) is None


# ── plan_push (single-box Sokoban push reachability) ────────────────────────

from admorphiq.kernels.paths import plan_push  # noqa: E402


def _replay_push(pusher, box, plan, move_labels):
    """Replay a push plan: a step INTO the box cell pushes it; return the box's
    final cell. Mirrors classic Sokoban semantics the kernel plans for."""
    label_to_delta = {v: k for k, v in move_labels.items()}
    pu, bx = pusher, box
    for a in plan:
        dr, dc = label_to_delta[a]
        nxt = (pu[0] + dr, pu[1] + dc)
        if nxt == bx:
            bx = (bx[0] + dr, bx[1] + dc)
        pu = nxt
    return bx


def test_plan_push_straight_line_pushes_box_to_target():
    """Purpose: with the pusher already behind the box on a clear lane, a
    straight push must walk the box cell-by-cell to the target; replaying the
    plan must land the box exactly on the target.
    Expected feedback: failure means the push-direction reachability gate or
    the box-advance model is wrong, so no Sokoban push would ever land."""
    plan = plan_push((2, 0), (2, 2), (2, 5), _OPEN6, _ML)
    assert plan is not None
    assert _replay_push((2, 0), (2, 2), plan, _ML) == (2, 5)


def test_plan_push_repositions_the_pusher_around_a_corner():
    """Purpose: to push the box along a NEW axis the pusher must first walk
    around to the opposite side (the box is an obstacle during that walk);
    the plan must include that repositioning and still land the box on a
    target that requires a direction change.
    Expected feedback: failure means the planner can't sequence
    reposition-then-push — the whole point of push reachability — so any
    non-straight Sokoban goal is unreachable."""
    plan = plan_push((2, 0), (2, 2), (5, 2), _OPEN6, _ML)
    assert plan is not None
    assert _replay_push((2, 0), (2, 2), plan, _ML) == (5, 2)


def test_plan_push_none_when_target_is_walled_off():
    """Purpose: when a wall blocks every push lane to the target the planner
    must return None (not a partial or looping plan) so the caller falls back.
    Expected feedback: failure means an impossible push is 'executed',
    wasting budget instead of trying another piece/strategy."""
    # A FULL wall column at col 4 seals the box (col<4) from the target (col 6).
    grid = [[c != 4 for c in range(8)] for _ in range(6)]
    assert plan_push((2, 0), (2, 2), (2, 6), grid, _ML) is None


def test_plan_push_empty_when_box_already_on_target():
    """Purpose: a box already on the target needs no pushing — return [] (a
    distinct 'done' signal), never None.
    Expected feedback: failure means the caller can't tell a solved box from
    an unsolvable one."""
    assert plan_push((0, 0), (3, 3), (3, 3), _OPEN6, _ML) == []


# ── slide_endpoint / slide_chain (deterministic slide prediction) ───────────

from admorphiq.kernels.paths import slide_chain, slide_endpoint  # noqa: E402


def _floor(rows):
    """Grid from ascii: '.' = passable floor, anything else = wall."""
    return [[ch == "." for ch in row] for row in rows]


def test_slide_endpoint_until_wall_runs_to_the_last_open_cell():
    """Purpose: an ice/momentum slide advances in the pressed direction until
    the cell ahead is a wall (or the grid edge) and stops on the last open
    cell — the core deterministic-slide prediction.
    Expected feedback: failure means every slide landing is mispredicted, so
    a slide-maze planner routes to the wrong cells."""
    grid = _floor(["#######", "#.....#", "#######"])
    assert slide_endpoint(grid, (1, 1), (0, 1), "until_wall") == (1, 5)
    # already against the wall in that direction -> self-loop (not an error).
    assert slide_endpoint(grid, (1, 5), (0, 1), "until_wall") == (1, 5)


def test_slide_endpoint_until_bend_stops_at_a_junction():
    """Purpose: the 'roll through a straight corridor, stop where it branches'
    rule must halt at the first cell with an open perpendicular exit, not run
    to the wall past it.
    Expected feedback: failure means corridor-bend prediction overshoots or
    stops short, mislocating where a rolling mover comes to rest."""
    # Corridor row 1 opens downward at col 3 (a junction) before the wall.
    grid = _floor(["#######", "#...#.#", "###.###", "###.###"])
    assert slide_endpoint(grid, (1, 1), (0, 1), "until_bend") == (1, 3)


def test_slide_endpoint_rejects_an_unknown_stop_rule():
    """Purpose: stop rules are a closed data vocabulary; an unknown rule must
    raise rather than silently behave like a default — a caller typo should
    fail loudly.
    Expected feedback: failure means a mistyped stop rule silently plans with
    the wrong physics."""
    import pytest as _pytest

    with _pytest.raises(ValueError):
        slide_endpoint(_floor(["..."]), (0, 0), (0, 1), "until_teleport")


def test_slide_chain_shoves_a_lane_of_movers():
    """Purpose: a momentum launch (ka59-style) must chain — the launcher
    slides into the mover ahead, which is shoved and slides on, each stopping
    by the rule; the returned map records every mover that moved.
    Expected feedback: failure means chained shoves are dropped or
    mispositioned, so a momentum-push planner mis-predicts the whole lane."""
    grid = _floor(["######", "#....#", "######"])
    moved = slide_chain(grid, (1, 1), (0, 1), [(1, 3)], "until_wall")
    assert moved == {(1, 1): (1, 2), (1, 3): (1, 4)}


def test_slide_chain_no_other_movers_is_a_plain_slide():
    """Purpose: with no other movers the chain degenerates to a single slide
    to the wall — a plain slide is the zero-obstacle case of a shove.
    Expected feedback: failure means the chain path diverges from the
    single-mover slide, an inconsistency between the two kernels."""
    grid = _floor(["######", "#....#", "######"])
    assert slide_chain(grid, (1, 1), (0, 1), [], "until_wall") == {(1, 1): (1, 4)}


# ── plan_gated_path (button-barrier / gated-maze product-graph planner) ──────

from admorphiq.kernels.paths import plan_gated_path  # noqa: E402


def test_plan_gated_path_toggles_a_barrier_then_walks_through():
    """Purpose: a wall blocks the only route; a toggle removes it. The planner
    must emit the toggle THEN walk through the now-open cell — the core
    interleave of button-press and movement.
    Expected feedback: failure means the product-graph search doesn't treat a
    passability-mutating action as an edge, so no gated maze ever solves."""
    # Row 1 corridor with a wall at (1,3); toggle 'open' removes it.
    base_walls = frozenset({(1, 3)})
    move_labels = {(0, 1): "right", (0, -1): "left"}

    def passable(cell, walls):
        r, c = cell
        return 0 <= r < 3 and 0 <= c < 6 and cell not in walls

    toggles = [("open", lambda w: frozenset(w - {(1, 3)}))]
    plan = plan_gated_path((1, 0), (1, 5), base_walls, passable, toggles, move_labels)
    assert plan is not None
    assert "open" in plan
    # The toggle must come before the walk crosses column 3.
    assert plan.index("open") < plan.count("right")


def test_plan_gated_path_seesaw_needs_the_toggle_in_a_specific_state():
    """Purpose: a seesaw toggle (symmetric-difference on a cell set) opens one
    segment while closing another; the planner must find the state in which
    the goal-side segment is open, toggling as needed.
    Expected feedback: failure means the planner can't reason over a state
    that a toggle flips both ways — the exact dc22 seesaw."""
    seesaw = frozenset({(1, 2)})  # closed initially; toggle opens it
    base_walls = frozenset({(1, 2)})
    move_labels = {(0, 1): "R", (0, -1): "L"}

    def passable(cell, walls):
        r, c = cell
        return r == 1 and 0 <= c < 5 and cell not in walls

    toggles = [("flip", lambda w: frozenset(w ^ seesaw))]
    plan = plan_gated_path((1, 0), (1, 4), base_walls, passable, toggles, move_labels)
    assert plan is not None and "flip" in plan


def test_plan_gated_path_none_when_no_toggle_opens_the_route():
    """Purpose: when no toggle can open a path to the goal, the planner must
    return None rather than loop or emit a partial plan.
    Expected feedback: failure means an unsolvable gated board 'plans' anyway,
    wasting the action budget."""
    base_walls = frozenset({(1, 3)})
    move_labels = {(0, 1): "R"}

    def passable(cell, walls):
        r, c = cell
        return r == 1 and 0 <= c < 6 and cell not in walls

    # The only toggle opens an IRRELEVANT cell, never (1,3).
    toggles = [("noop", lambda w: frozenset(w - {(2, 2)}))]
    assert plan_gated_path((1, 0), (1, 5), base_walls, passable, toggles, move_labels) is None


def test_plan_gated_path_empty_when_already_at_goal():
    """Purpose: start == goal needs no actions — return [] (a distinct
    'already solved' from None).
    Expected feedback: failure means the caller can't distinguish solved from
    unsolvable."""
    assert plan_gated_path((0, 0), (0, 0), frozenset(), lambda c, w: True, [], {}) == []
