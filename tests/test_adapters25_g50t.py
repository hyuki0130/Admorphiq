"""Tests for the G50T reactive-maze adapter (R56, 2026-07-15).

G50T is a Sokoban / Adventures-of-Lolo reactive grid puzzle (see the adapter
module docstring): ACTION1-4 move a player one cell, ACTION5 is UNDO, moves
animate over several engine steps, enemies react to the player, and a hidden
goal must be reached before a scroll-timer expires. The adapter is a banked
best-effort hazard-learning explorer; these tests pin the pure helpers and the
regression that every branch returns a real GameAction (a raw-int return once
crashed the env loop at 7 actions).
"""

from __future__ import annotations

from types import SimpleNamespace

from arcengine import GameAction

from admorphiq.adapters25.g50t import _ANIMATING_DIFF, Adapter, _diff_count, _quantize, _sign


def _frame(grid: list[list[int]], levels: int = 0, state: str = "NOT_FINISHED") -> SimpleNamespace:
    return SimpleNamespace(
        frame=[[list(row) for row in grid]],
        state=SimpleNamespace(name=state),
        available_actions=[1, 2, 3, 4, 5],
        levels_completed=levels,
    )


def _blank(size: int = 24, bg: int = 0) -> list[list[int]]:
    return [[bg] * size for _ in range(size)]


def test_quantize_maps_pixels_to_the_six_pixel_cell_grid():
    """Purpose: the cell key is the centroid divided by the measured 6px render
    pitch, rounded — the stable state key the transition graph is built on.
    Expected feedback: failure means player cells alias or split across keys,
    corrupting every learned transition."""
    assert _quantize((0.0, 0.0)) == (0, 0)
    assert _quantize((12.0, 6.0)) == (2, 1)
    assert _quantize((13.0, 5.0)) == (2, 1)  # rounding to nearest cell


def test_sign_is_three_valued():
    """Purpose: displacement-direction evidence uses -1/0/+1 per axis so the
    '>=2 distinct directions' player test rejects the one-way scroll timer.
    Expected feedback: failure means the scroller could be mislabeled the
    player (it moves one direction forever)."""
    assert (_sign(-3), _sign(0), _sign(7)) == (-1, 0, 1)


def test_diff_count_separates_animating_from_settled_frames():
    """Purpose: a move animates over several steps (48-105 cells changing)
    while a settled/blocked frame changes only by the ~1-2px scroller tick; the
    adapter must hold (not plan) until settled. Pin that a big change reads as
    animating and a tiny one as settled, either side of the threshold.
    Expected feedback: failure means the adapter plans mid-animation on a
    half-moved player, recording bogus transitions."""
    a = tuple(tuple(row) for row in _blank())
    # One changed cell -> settled.
    b_settled = [list(row) for row in a]
    b_settled[3][3] = 9
    b_settled_t = tuple(tuple(row) for row in b_settled)
    assert _diff_count(a, b_settled_t) <= _ANIMATING_DIFF
    # Many changed cells -> animating.
    b_anim = [list(row) for row in a]
    for c in range(_ANIMATING_DIFF + 5):
        b_anim[5][c] = 8
    b_anim_t = tuple(tuple(row) for row in b_anim)
    assert _diff_count(a, b_anim_t) > _ANIMATING_DIFF


def test_choose_action_always_returns_a_gameaction_including_the_hold_branch():
    """Purpose: regression pin for the raw-int-return crash — every branch of
    choose_action, INCLUDING the mid-animation 'hold' branch, must return a
    real GameAction. A bare int once ended the env loop at 7 actions.
    Expected feedback: failure means the env-stepping loop aborts early
    (measured as an implausibly tiny action count) instead of running to
    budget."""
    ad = Adapter()
    ad._levels_seen = 0  # suppress the level-up reset so state persists

    settled = _blank()
    a1 = ad.choose_action([], _frame(settled))
    assert isinstance(a1, GameAction)

    # A frame that differs from the previous by far more than the animating
    # threshold drives the hold branch, which returned a raw int before the fix.
    animating = _blank()
    for c in range(_ANIMATING_DIFF + 8):
        animating[7][c] = 8
    a2 = ad.choose_action([], _frame(animating))
    assert isinstance(a2, GameAction)


def test_death_marks_the_last_move_fatal_and_keeps_the_graph():
    """Purpose: the compounding-across-lives contract — a GAME_OVER records the
    last (cell, action) as fatal and preserves the learned transition graph so
    the next life avoids the trap.
    Expected feedback: failure means every death re-explores from scratch,
    never converging away from known-lethal edges."""
    ad = Adapter()
    ad._levels_seen = 0
    ad._transitions = {((1, 1), 2, (1, 2))}
    ad._pending_from = (1, 2)
    ad._pending_action = 3
    action = ad.choose_action([], _frame(_blank(), state="GAME_OVER"))
    assert action == GameAction.RESET
    assert ((1, 2), 3) in ad._fatal
    assert ((1, 1), 2, (1, 2)) in ad._transitions  # graph survived the death
