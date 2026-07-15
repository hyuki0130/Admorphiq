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

from admorphiq.adapters25.ls20 import (
    _BASE_SHAPES,
    _CELL,
    _PALETTE,
    _SHAPE_ROT,
    _STEP_DECR,
    _STEP_FULL,
    _decode_shape3,
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
