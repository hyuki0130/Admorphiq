"""Tests for the cyclic-permutation learn + assignment-search kernels (R56).

These pin the ring-puzzle solver primitives: recovering a rotation control's
permutation from a single before/after frame, closing partially-observed
cycles, and BFS-planning a control sequence onto goal cells.
"""

from admorphiq.kernels.permute import (
    apply_successor,
    complete_cycle,
    is_single_cycle,
    learn_cyclic_successor,
    learn_successor_from_series,
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


def test_learn_recovers_a_twisted_loop_via_observed_successors():
    """Purpose: pin the observation-first fix for TWISTED rings (measured on LP85
    L4). The true loop runs down two parallel columns in the SAME direction, so
    its cross-gap link is geometrically FAR — the nearest-neighbour tour returns
    the wrong simple-rectangle order. With distinct colours, the observed
    colour-successor must recover the true twist regardless of geometry.

    Expected feedback: PASS = ``succ`` equals the true twisted rotation (a single
    cycle following the far cross-gap links). A failure means the learner fell
    back to the geometric tour and mis-ordered the ring — exactly the L4 wall.
    """
    # Two columns; both traversed top->bottom, so (6,4)->(2,14) and (6,14)->(2,4)
    # are the true (far) links, not the near (6,4)->(6,14) rectangle link.
    loop = [(2, 4), (3, 4), (4, 4), (5, 4), (6, 4), (2, 14), (3, 14), (4, 14), (5, 14), (6, 14)]
    n = len(loop)
    colors = list(range(11, 11 + n))  # all distinct
    before = [_region(colors[i], loop[i]) for i in range(n)]
    after_color = {loop[(i + 1) % n]: colors[i] for i in range(n)}
    after = [_region(after_color[loop[i]], loop[i]) for i in range(n)]
    changed = set(loop)
    succ = learn_cyclic_successor(before, after, changed)
    true_succ = {loop[i]: loop[(i + 1) % n] for i in range(n)}
    assert succ == true_succ  # the far cross-gap twist links, not the rectangle order


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


def test_learn_recovers_a_fully_invisible_ring_cell_via_candidates():
    """Purpose: a ring cell whose colour matches BOTH neighbours never changes
    under a rotation, so it is absent from the frame diff -- learning from the
    diff alone drops it and the cycle comes back one cell short, which drifts a
    multi-step plan off target. Passing every token centroid as
    ``candidate_cells`` must splice that cell back geometrically into the tour's
    oversized gap.

    Expected feedback: PASS = with ``candidate_cells`` the completed cycle covers
    ALL ring cells including the invisible one, while omitting it leaves that cell
    out -- proving the augmentation, not luck, is what recovers it. This is what
    keeps LP85's ring maps complete when adjacent tiles share a colour.
    """
    colors = [1, 2, 3, 4, 5, 6, 7, 7]  # only LOOP[7] shares a colour with LOOP[6]
    before, after, changed = _rotate_regions(colors, step=1)
    invisible = _LOOP[7]  # (2, 0) -- its occupant moves but the diff never shows it
    assert invisible not in changed

    without = complete_cycle(learn_cyclic_successor(before, after, changed))
    assert invisible not in (set(without) | set(without.values()))

    candidates = list(_LOOP)  # every on-board token centroid
    with_cands = complete_cycle(
        learn_cyclic_successor(before, after, changed, candidate_cells=candidates)
    )
    cells = set(with_cands) | set(with_cands.values())
    assert cells == set(_LOOP)  # the invisible cell is back
    seen, cur = set(), invisible
    for _ in range(len(_LOOP)):
        seen.add(cur)
        cur = with_cands[cur]
    assert seen == set(_LOOP) and cur == invisible  # one full cycle through it


def test_plan_is_class_aware_when_labels_given():
    """Purpose: with several token/target classes (e.g. two marker colours), a
    token must only satisfy a SAME-class goal. On two DISJOINT rings a class-'a'
    token confined to ring 1 can never reach ring 2, so asking it to occupy a
    ring-2 cell must fail — proving the label constraint is enforced, not just
    position.

    Expected feedback: PASS = the correctly-labelled goal (each token to a cell
    on its own reachable ring) is planned, while routing a token to the other
    class's ring is ``None``. This is what lets LP85 L3's two marker colours be
    placed jointly without one cross-satisfying the other's target.
    """
    ring1 = [(0, 0), (0, 2), (2, 2), (2, 0)]
    ring2 = [(0, 10), (0, 12), (2, 12), (2, 10)]
    r1 = {ring1[i]: ring1[(i + 1) % 4] for i in range(4)}
    r2 = {ring2[i]: ring2[(i + 1) % 4] for i in range(4)}
    ops = {"R1": r1, "R2": r2}
    tokens = [ring1[0], ring2[0]]
    labels = ["a", "b"]
    ok = plan_token_assignment(
        ops, tokens, [ring1[1], ring2[1]], labels=labels, goal_labels=["a", "b"], budget=6
    )
    assert ok is not None and set(ok) <= {"R1", "R2"} and len(ok) == 2
    # ask the ring-1 'a' token to reach a ring-2 cell -> impossible
    unreachable = plan_token_assignment(
        ops, tokens, [ring2[1], ring2[3]], labels=labels, goal_labels=["a", "b"], budget=6
    )
    assert unreachable is None


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


def _rotation_series(order, necklace, presses):
    """Colour time-series each ring cell shows over ``presses`` R-rotations.

    ``order`` is the ring's true cyclic cell order; ``necklace[i]`` is the colour
    of the occupant that starts on ``order[i]``. An R press moves each occupant to
    the next cell, so cell ``order[j]`` at time ``t`` holds ``necklace[(j-t) % n]``.
    """
    n = len(order)
    return {
        cell: tuple(necklace[(j - t) % n] for t in range(presses + 1))
        for j, cell in enumerate(order)
    }


def test_is_single_cycle_distinguishes_loop_from_fragments():
    """Purpose: pin ``is_single_cycle`` — a learned ring map must be ONE closed
    loop, not fragments, for the planner to trust it.

    Expected feedback: PASS = True for a single Hamiltonian cycle; False for an
    empty map, a broken chain, and two disjoint sub-cycles (the exact mis-learn
    the exact-match stop guards against).
    """
    loop = {(0, 0): (0, 1), (0, 1): (0, 2), (0, 2): (0, 0)}
    assert is_single_cycle(loop) is True
    assert is_single_cycle({}) is False
    assert is_single_cycle({(0, 0): (0, 1), (0, 1): (0, 2)}) is False  # tail, no return
    two = {(0, 0): (0, 1), (0, 1): (0, 0), (5, 5): (5, 6), (5, 6): (5, 5)}
    assert is_single_cycle(two) is False


def test_learn_from_series_recovers_ring_under_duplicate_colours():
    """Purpose: the multi-press learner must recover a ring's full cyclic order
    even when its tokens reuse colours — the exact case where single-press σ²
    under-determines the order (LP85 L4: 6 colours over 20 cells, the fix-point
    finds no self-consistent cycle).

    Expected feedback: PASS = over a full cycle of presses the recovered successor
    map equals the TRUE ring order and reports ``all_exact`` (every cell's colour
    series uniquely fingerprints its successor); the map is one clean cycle. This
    is what lets LP85 L4 be learned where the 2-press signature collides.
    """
    # 6-cell ring, aperiodic necklace with every colour repeated (1,2,3 each twice)
    order = [(0, 0), (0, 2), (0, 4), (2, 4), (2, 2), (2, 0)]
    necklace = [1, 2, 1, 3, 2, 3]
    true_succ = {order[i]: order[(i + 1) % 6] for i in range(6)}
    series = _rotation_series(order, necklace, presses=6)
    succ, all_exact = learn_successor_from_series(series)
    assert succ == true_succ
    assert all_exact is True
    assert is_single_cycle(succ) is True


def test_learn_from_series_needs_multiple_presses_under_duplicates():
    """Purpose: pin WHY the learner presses many times — under duplicate colours a
    single press is not enough to fingerprint successors, so a too-short window can
    certify a WRONG map (all-exact + single-cycle yet not the true order). This is
    why the adapter's stop only fires well above one press.

    Expected feedback: PASS = a ONE-press window recovers a map that differs from
    the true ring order (single press insufficient), while a full-cycle window
    recovers the true order exactly. Demonstrates the multi-press necessity that
    resolved the LP85 L4 σ² conflict.
    """
    order = [(0, 0), (0, 2), (0, 4), (2, 4), (2, 2), (2, 0)]
    necklace = [1, 1, 2, 2, 3, 3]  # heavy adjacent duplication
    true_succ = {order[i]: order[(i + 1) % 6] for i in range(6)}
    one, _ = learn_successor_from_series(_rotation_series(order, necklace, presses=1))
    full, exact = learn_successor_from_series(_rotation_series(order, necklace, presses=6))
    assert one != true_succ  # one press cannot disambiguate the duplicate colours
    assert full == true_succ and exact is True
