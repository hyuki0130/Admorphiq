"""Tests for the LS20 adapter's offline maze reconstruction + joint BFS
(dedicated session, 2026-07-15).

Background (see the module docstring + ``.wiki/wiki/games/LS20.md``): LS20 is a
shape/color/rotation-matching maze. Four rounds of online frame-keyed
exploration banked at 1/7 (L1 only, ~606 actions) because the full-reset
21-action lives make exploration economics not close. This adapter sidesteps
exploration: it parses the maze from a single settled frame and runs a JOINT
BFS over ``(cell, shape, color, rotation, steps_left, refills_taken)`` toward a
matching goal, executed open-loop. The parser was validated dev-time byte-exact
against the engine ground truth (L1 + L2) and the found plans replay to live
wins (L1 in 13 actions, L2 in 45). These tests pin the engine-free invariants
the reconstruction depends on: the appearance decoders, and the joint BFS's
goal-matching / rotation-changer / refill-budget / goal-blocking contracts.
"""

from __future__ import annotations

from collections import Counter

from admorphiq.adapters25.ls20 import (
    _BASE_SHAPES,
    _CELL,
    _FLOOR_COLOR,
    _PALETTE,
    _SHAPE_ROT,
    _STEP_DECR,
    _STEP_FULL,
    _WALL_COLOR,
    _classify_changer,
    _decode_shape3,
    _detect_pushwalls,
    _solve,
)


def _base_fill(shape_idx: int) -> dict[tuple[int, int], int]:
    """The rotation-0 filled cells of a base shape, painted the first palette
    colour — the exact input the goal-preview decoder builds from a frame."""
    mat = _BASE_SHAPES[shape_idx]
    return {
        (r, c): _PALETTE[0]
        for r in range(3)
        for c in range(3)
        if mat[r][c] != -1
    }


def test_shape_rot_table_covers_all_six_shapes_four_rotations():
    """Purpose: the decoder maps a filled-cell SET (under rotation) to
    ``(shape, rot)``; prove every base shape at every rotation has a distinct,
    resolvable entry so no token appearance is silently undecodable.
    Expected feedback: a failure means two shapes/rotations collide or one is
    missing — the parser would then mis-read the token or goal and plan a wrong
    (non-winning) route."""
    seen = set()
    for si in range(6):
        cells = frozenset(_base_fill(si))
        assert cells in _SHAPE_ROT
        assert _SHAPE_ROT[cells][0] == si  # rot-0 fill decodes to its own shape
        seen.add(cells)
    assert len(seen) == 6  # the six rot-0 fills are mutually distinct


def test_decode_shape3_reads_shape_color_rotation():
    """Purpose: pin the core appearance decode — a rot-0 fill of each shape in
    each palette colour must decode to that (shape, color, rot=0).
    Expected feedback: a failure means the token/goal-preview decode is wrong,
    so the joint BFS is seeded with the wrong start/target token."""
    for si in range(6):
        for ci, col in enumerate(_PALETTE):
            fill = {cell: col for cell in _base_fill(si)}
            assert _decode_shape3(fill) == (si, ci, 0)


def test_decode_shape3_rejects_non_shape_and_offpalette():
    """Purpose: the decoder must return None on garbage (an unknown filled set
    or an off-palette colour) so ``_parse`` gates to the explorer instead of
    fabricating a token.
    Expected feedback: a failure means a malformed frame would yield a bogus
    token and a wrong plan rather than a safe fallback."""
    assert _decode_shape3({}) is None
    assert _decode_shape3({(0, 0): _PALETTE[0]}) is None  # single cell: no shape
    off = {cell: 7 for cell in _base_fill(0)}  # colour 7 is not in the palette
    assert _decode_shape3(off) is None


def test_classify_changer_types_by_icon_signature():
    """Purpose: pin the changer-type classifier's ordering — the colour changer
    icon (soyhouuebz) carries a colour-0 pixel AND a multi-palette icon, so the
    palette test MUST precede the colour-0 shape test or a colour changer is
    mis-typed "shape" (the exact bug that made L3/L4 unsolvable before this
    fix). Also: a changer only exists on a FLOOR cell — colour-1 markers on WALL
    cells (push-walls / arena edges) must NOT register as rotation changers.
    Expected feedback: a failure means the parser mis-reads which attribute a
    changer cycles, and the joint BFS plans a route that can never match the
    goal token."""
    # rotation icon: floor-dominant cell carrying colour-1 (+ colour-0) pixels.
    rot = Counter({_FLOOR_COLOR: 20, 0: 3, 1: 2})
    assert _classify_changer(rot, _FLOOR_COLOR) == "rot"
    # colour icon: floor cell with a multi-palette icon AND one colour-0 pixel.
    color = Counter({_FLOOR_COLOR: 16, 9: 2, 14: 2, 8: 2, 12: 2, 0: 1})
    assert _classify_changer(color, _FLOOR_COLOR) == "color"
    # shape icon: floor cell with colour-0 pixels only.
    shape = Counter({_FLOOR_COLOR: 21, 0: 4})
    assert _classify_changer(shape, _FLOOR_COLOR) == "shape"
    # colour-1 marker on a WALL cell (dom colour-4) is NOT a rotation changer.
    wall_marker = Counter({_WALL_COLOR: 20, 1: 5})
    assert _classify_changer(wall_marker, _WALL_COLOR) is None
    # plain floor is not a changer.
    assert _classify_changer(Counter({_FLOOR_COLOR: 25}), _FLOOR_COLOR) is None


def test_detect_pushwalls_reads_direction_from_the_edge_line():
    """Purpose: a push-wall renders as a 5-pixel colour-1 edge LINE and pushes
    the avatar TOWARD that edge (the sprite body extends into the neighbour), so
    the collision cell is one cell past the line and the direction points that
    way. Pin all four orientations.
    Expected feedback: a failure means the offline model shoves the avatar the
    wrong way (or to the wrong cell) and every push-wall level desyncs on replay."""
    cell, n = _CELL, 3
    xs = ys = [cell * i for i in range(n)]

    def grid_with_line(edge: str) -> tuple[tuple[int, ...], ...]:
        # a colour-1 line on one edge of cell (cell, cell) == (5,5); floor else.
        g = [[_FLOOR_COLOR] * (cell * n) for _ in range(cell * n)]
        bx, by = cell, cell
        for k in range(cell):
            if edge == "right":
                g[by + k][bx + cell - 1] = 1
            elif edge == "left":
                g[by + k][bx] = 1
            elif edge == "bottom":
                g[by + cell - 1][bx + k] = 1
            elif edge == "top":
                g[by][bx + k] = 1
        return tuple(tuple(r) for r in g)

    assert _detect_pushwalls(grid_with_line("right"), xs, ys) == {(cell * 2, cell): (1, 0)}
    assert _detect_pushwalls(grid_with_line("left"), xs, ys) == {(0, cell): (-1, 0)}
    assert _detect_pushwalls(grid_with_line("bottom"), xs, ys) == {(cell, cell * 2): (0, 1)}
    assert _detect_pushwalls(grid_with_line("top"), xs, ys) == {(cell, 0): (0, -1)}


def test_solve_slides_off_a_pushwall_and_stops_before_the_goal():
    """Purpose: stepping onto a push-wall collision cell must slide the avatar in
    the push direction, stopping before a wall OR the goal (the engine's push
    stops at goal cells), after which a normal move lands on the goal — the exact
    L3 endgame (a down-push stops one cell above the goal).
    Expected feedback: a failure means the push slide over/under-shoots or lands
    on the goal directly, which the live engine never allows."""
    # corridor (0,0)-(20,0); (5,0) is a right-pushing collision cell.
    passable = {(_CELL * i, 0) for i in range(5)}
    parsed = {
        "avatar": (0, 0), "goal": (_CELL * 4, 0), "goal_req": (5, 1, 0),
        "token": (5, 1, 0), "changers": {}, "refills": frozenset(),
        "passable": passable, "pushwalls": {(_CELL, 0): (1, 0)},
    }
    # step right onto (5,0) -> slides to (15,0) (stops before goal (20,0)),
    # then one more right move lands on the goal.
    assert _solve(parsed) == [4, 4]


def _corridor(length: int) -> dict[tuple[int, int], object]:
    """A horizontal passable corridor of ``length`` cells starting at (0,0),
    stepping right by one grid unit."""
    return {(_CELL * i, 0) for i in range(length)}


def test_solve_trivial_when_already_on_matching_goal():
    """Purpose: standing on the goal with a matching token is a zero-action
    solve — pin the terminal contract.
    Expected feedback: a non-empty/None result means the goal test is wrong."""
    parsed = {
        "avatar": (0, 0), "goal": (0, 0), "goal_req": (5, 1, 0),
        "token": (5, 1, 0), "changers": {}, "refills": frozenset(),
        "passable": {(0, 0)},
    }
    assert _solve(parsed) == []


def test_solve_routes_through_rotation_changer_then_goal():
    """Purpose: when the goal needs a token one rotation off, the plan must
    visit the rotation changer (cycling +1) before the goal — the core
    token-transform contract of the maze.
    Expected feedback: a failure means the changer effect or the goal-blocking
    (can't stand on the goal until matched) is mis-modelled."""
    passable = _corridor(3)  # (0,0) start, (5,0) changer, (10,0) goal
    parsed = {
        "avatar": (0, 0), "goal": (10, 0), "goal_req": (5, 1, 1),
        "token": (5, 1, 0), "changers": {(5, 0): "rot"}, "refills": frozenset(),
        "passable": passable,
    }
    plan = _solve(parsed)
    # right to the changer (rot 0->1), then right to the matching goal.
    assert plan == [4, 4]


def test_solve_needs_refill_to_survive_a_long_corridor():
    """Purpose: a goal farther than one life (``_STEP_FULL // _STEP_DECR``
    actions) is only reachable by collecting a step-refill mid-run; prove the
    budget/refill arithmetic makes the difference between None and a plan.
    Expected feedback: a failure means the life budget or the refill top-up is
    wrong — exactly the L2 mechanic (45 actions > a 21-action life)."""
    life = _STEP_FULL // _STEP_DECR
    far = life + 3  # goal at cell `far`, beyond a single life
    passable = _corridor(far + 1)
    base = {
        "avatar": (0, 0), "goal": (_CELL * far, 0), "goal_req": (5, 1, 0),
        "token": (5, 1, 0), "passable": passable, "changers": {},
    }
    # Without a refill the corridor cannot be crossed within one life.
    assert _solve({**base, "refills": frozenset()}) is None
    # A refill partway along tops the budget back up, making it reachable.
    refill_cell = (_CELL * (life - 2), 0)
    plan = _solve({**base, "refills": frozenset({refill_cell})})
    assert plan is not None and len(plan) == far  # straight walk, no wasted steps


def test_solve_returns_none_when_token_cannot_be_transformed():
    """Purpose: if the goal needs an attribute the maze has no changer for, the
    puzzle is unsolvable and ``_solve`` must return None (so the adapter gates),
    not loop or fabricate.
    Expected feedback: a failure means a wrong-token route could be committed
    and executed open-loop, wasting the whole budget."""
    passable = _corridor(3)
    parsed = {
        "avatar": (0, 0), "goal": (10, 0), "goal_req": (5, 2, 0),  # needs colour idx 2
        "token": (5, 1, 0), "changers": {(5, 0): "rot"},  # only a rotation changer
        "refills": frozenset(), "passable": passable,
    }
    assert _solve(parsed) is None
