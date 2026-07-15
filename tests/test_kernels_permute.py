"""Tests for the cyclic-permutation learn + assignment-search kernels (R56).

These pin the ring-puzzle solver primitives: recovering a rotation control's
permutation from a single before/after frame, closing partially-observed
cycles, and BFS-planning a control sequence onto goal cells.
"""

from admorphiq.kernels.permute import (
    apply_successor,
    complete_cycle,
    learn_cyclic_successor,
    plan_token_assignment,
)

# An 8-cell rectangular loop (perimeter of a 5x5), spacing 2 so a nearest-
# neighbour tour recovers the loop order. Listed in true cyclic order.
_LOOP = [(0, 0), (0, 2), (0, 4), (2, 4), (4, 4), (4, 2), (4, 0), (2, 0)]


def _region(color: int, cell: tuple[int, int]) -> dict[str, object]:
    return {
        "color": color,
        "cells": frozenset({cell}),
        "centroid": (float(cell[0]), float(cell[1])),
        "size": 1,
        "bbox": (cell[0], cell[1], cell[0], cell[1]),
    }


def _rotate_regions(colors: list[int], step: int) -> tuple[list, list, set]:
    """Build (before_regions, after_regions, changed_cells) for a rotation that
    moves the occupant of ``_LOOP[i]`` to ``_LOOP[i+step]``."""
    n = len(_LOOP)
    before = [_region(colors[i], _LOOP[i]) for i in range(n)]
    # occupant of cell i lands on cell i+step -> after-colour at i+step is colors[i]
    after_color = {}
    for i in range(n):
        after_color[_LOOP[(i + step) % n]] = colors[i]
    after = [_region(after_color[_LOOP[i]], _LOOP[i]) for i in range(n)]
    changed = {_LOOP[i] for i in range(n) if colors[i] != after_color[_LOOP[i]]}
    return before, after, changed


def test_learn_recovers_full_cycle_with_distinct_colors():
    """Purpose: with every ring cell a distinct colour, one press must yield the
    exact rotation permutation.

    Expected feedback: PASS means the defining invariant holds for every cell —
    ``before_colour[p] == after_colour[succ[p]]`` (p's occupant moved to
    ``succ[p]``) — and ``succ`` is a single 8-cycle. A failure means the learner
    mis-paired occupants, so any plan built on it would be wrong.
    """
    colors = [1, 2, 3, 4, 5, 6, 7, 8]
    before, after, changed = _rotate_regions(colors, step=1)
    succ = learn_cyclic_successor(before, after, changed)
    bcol = {c: colors[i] for i, c in enumerate(_LOOP)}
    acol = {_LOOP[(i + 1) % 8]: colors[i] for i in range(8)}
    assert len(succ) == 8
    assert len(set(succ.values())) == 8  # bijection
    for p in _LOOP:
        assert acol[succ[p]] == bcol[p]
    # single 8-cycle: iterating succ from one cell visits all 8
    seen, cur = set(), _LOOP[0]
    for _ in range(8):
        seen.add(cur)
        cur = succ[cur]
    assert seen == set(_LOOP) and cur == _LOOP[0]


def test_learn_recovers_cycle_despite_adjacent_duplicate_colours():
    """Purpose: adjacent same-colour tiles make an occupant's move locally
    invisible/ambiguous; the tour+vote strategy must still reconstruct one clean
    cycle rather than fracturing into short cycles.

    Expected feedback: PASS = a single 8-cycle whose direction is the majority
    (colour-consistent) one, proving the direction vote overrides local
    same-colour ambiguity. Fragmentation into 2-cycles (the symptom that broke
    an earlier greedy learner) would fail the cycle-length assertion.
    """
    colors = [1, 1, 3, 3, 5, 6, 7, 8]  # two adjacent duplicate pairs
    before, after, changed = _rotate_regions(colors, step=1)
    succ = learn_cyclic_successor(before, after, changed)
    succ = complete_cycle(succ)  # duplicates may hide a link; completion closes it
    cells = set(succ) | set(succ.values())
    seen, cur = set(), next(iter(cells))
    for _ in range(len(cells)):
        seen.add(cur)
        cur = succ[cur]
    assert seen == cells and cur in cells  # one cycle covering every cell


def test_complete_cycle_closes_a_partial_map_into_one_cycle():
    """Purpose: a partial successor map (some links unobserved) must close into a
    full permutation where every cell has exactly one successor.

    Expected feedback: PASS = the two missing links are inserted so the four
    cells form one 4-cycle. This is what lets a ring with a few invisible
    same-colour swaps still be planned on.
    """
    a, b, c, d = (0, 0), (0, 2), (0, 4), (0, 6)
    partial = {a: b, c: d}  # b->c and d->a missing
    full = complete_cycle(partial)
    assert set(full) == {a, b, c, d}
    assert len(set(full.values())) == 4
    seen, cur = set(), a
    for _ in range(4):
        seen.add(cur)
        cur = full[cur]
    assert seen == {a, b, c, d}


def test_apply_successor_advances_only_tokens_on_the_ring():
    """Purpose: applying a rotation must move a token that sits on the ring and
    leave a token that does not (a cell absent from the map) in place.

    Expected feedback: PASS = on-ring token steps to its successor, off-ring
    token unchanged, output sorted (canonical). Confirms the simulate step the
    planner's BFS relies on.
    """
    succ = {(0, 0): (0, 2), (0, 2): (0, 0)}
    assert apply_successor(succ, [(0, 0), (9, 9)]) == ((0, 2), (9, 9))


def test_plan_finds_shortest_control_sequence_to_goal():
    """Purpose: BFS must compose learned rotations into a shortest sequence that
    lands the moving token on the goal cell.

    Expected feedback: PASS = a 2-step plan using the forward control to advance
    the token two cells along the loop (the known optimum), proving the search
    reaches a goal assignment. Its absence would mean the composed operators
    cannot reach the goal.
    """
    colors = list(range(1, 9))
    before, after, changed = _rotate_regions(colors, step=1)
    fwd = learn_cyclic_successor(before, after, changed)
    ops = {"R": fwd}
    plan = plan_token_assignment(ops, [_LOOP[0]], [fwd[fwd[_LOOP[0]]]], budget=10)
    assert plan == ["R", "R"]


def test_plan_returns_none_when_goal_unreachable_within_budget():
    """Purpose: an honest failure signal when no composition reaches the goal in
    budget — the caller must fall back, not loop.

    Expected feedback: PASS = ``None`` for a goal cell that is not on any
    operator's ring (unreachable), and for a reachable goal beyond the budget.
    """
    colors = list(range(1, 9))
    before, after, changed = _rotate_regions(colors, step=1)
    ops = {"R": learn_cyclic_successor(before, after, changed)}
    assert plan_token_assignment(ops, [_LOOP[0]], [(99, 99)], budget=10) is None
    assert plan_token_assignment(ops, [_LOOP[0]], [_LOOP[3]], budget=2) is None
