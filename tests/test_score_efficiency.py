"""Unit tests for the score_efficiency module (pure scoring math only).

No live model, no network, no arc_agi environment required.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "score_efficiency.py"
_SPEC = importlib.util.spec_from_file_location("score_efficiency", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules["score_efficiency"] = _MOD
_SPEC.loader.exec_module(_MOD)

level_score = _MOD.level_score
game_score = _MOD.game_score
total_score = _MOD.total_score


# ─────────────────────────────── level_score ────────────────────────────────


def test_level_score_perfect():
    """Purpose: verify that an agent matching the human action count exactly earns 1.0.

    Expected feedback: if this fails, the squaring or clamping is broken —
    the base ratio 1.0**2 should equal 1.0.
    """
    assert level_score(50, 50) == 1.0


def test_level_score_faster_than_human_capped():
    """Purpose: verify the min(..., 1.0) cap — an agent faster than the human
    earns exactly 1.0, not more.

    Expected feedback: if this fails, the clamping is missing or applied after
    squaring instead of before.
    """
    assert level_score(50, 10) == 1.0


def test_level_score_twice_as_slow():
    """Purpose: verify the squared penalty for an agent using twice human actions.

    min(50/100, 1.0)**2 = 0.5**2 = 0.25

    Expected feedback: if this fails, either the ratio is inverted or the
    squaring step is absent.
    """
    assert abs(level_score(50, 100) - 0.25) < 1e-9


def test_level_score_ten_times_slower():
    """Purpose: verify heavy penalty for very slow agents.

    min(10/100, 1.0)**2 = 0.1**2 = 0.01

    Expected feedback: if this fails, the squaring amplification of the penalty
    is broken.
    """
    assert abs(level_score(10, 100) - 0.01) < 1e-9


def test_level_score_zero_agent_actions():
    """Purpose: verify that zero agent actions returns 0.0 without division error.

    Expected feedback: if this fails, there is a ZeroDivisionError guard missing.
    """
    assert level_score(50, 0) == 0.0


# ─────────────────────────────── game_score ─────────────────────────────────


def test_game_score_all_perfect_single_level():
    """Purpose: verify a 1-level game where the agent is perfect earns 1.0.

    Denominator = 1, numerator = 1*1.0 = 1.0 → game_score = 1.0.

    Expected feedback: if this fails, the 1-indexed weight logic is broken.
    """
    assert game_score([1.0], win_levels=1) == 1.0


def test_game_score_level_index_weighting():
    """Purpose: verify that later levels carry higher weight.

    3-level game, only level 1 cleared (score 1.0), levels 2 and 3 not cleared.
    per_level_scores = [1.0]  (only the cleared level is passed in)
    Denominator = 1+2+3 = 6, numerator = 1*1.0 = 1.0 → game_score = 1/6.

    Expected feedback: if this fails, the denominator is not computed over all
    win_levels — likely only over len(per_level_scores) instead.
    """
    result = game_score([1.0], win_levels=3)
    assert abs(result - 1 / 6) < 1e-9


def test_game_score_all_levels_cleared_equal_scores():
    """Purpose: verify a fully cleared game with uniform per-level scores.

    All scores = 0.25.  Weighted mean of equal values equals the value itself.
    (1*0.25 + 2*0.25 + 3*0.25) / (1+2+3) = 0.25*6/6 = 0.25

    Expected feedback: if this fails, the weighting calculation has an
    arithmetic error.
    """
    result = game_score([0.25, 0.25, 0.25], win_levels=3)
    assert abs(result - 0.25) < 1e-9


def test_game_score_later_levels_higher_weight():
    """Purpose: verify that clearing a harder (later) level is worth more.

    3-level game.  Case A: only level 1 cleared (score 1.0).
    Case B: only level 3 cleared (score 1.0).

    Case A: 1*1.0 / 6 ≈ 0.167
    Case B: 3*1.0 / 6 = 0.5

    Expected feedback: if this fails, level weights are not 1-indexed or are
    applied in the wrong order.
    """
    score_only_level1 = game_score([1.0], win_levels=3)
    score_only_level3 = game_score([0.0, 0.0, 1.0], win_levels=3)
    assert score_only_level3 > score_only_level1


def test_game_score_no_wins():
    """Purpose: verify that zero cleared levels yields 0.0.

    Expected feedback: if this fails, the empty numerator path is broken.
    """
    assert game_score([], win_levels=5) == 0.0


def test_game_score_zero_win_levels():
    """Purpose: verify that a game with no levels reports 0.0 without divison error.

    Expected feedback: if this fails, the win_levels=0 guard is missing.
    """
    assert game_score([], win_levels=0) == 0.0


# ─────────────────────────────── total_score ────────────────────────────────


def test_total_score_arithmetic_mean():
    """Purpose: verify total_score is the plain arithmetic mean over scored games.

    Expected feedback: if this fails, a weighted mean or other aggregation has
    been substituted for the simple mean.
    """
    result = total_score([1.0, 0.0])
    assert abs(result - 0.5) < 1e-9


def test_total_score_empty_list():
    """Purpose: verify that excluding all games (no baselines) returns 0.0.

    Expected feedback: if this fails, there is a division-by-zero error or the
    empty-list guard is absent.
    """
    assert total_score([]) == 0.0


def test_total_score_single_game():
    """Purpose: verify the trivial single-game case is returned unmodified.

    Expected feedback: if this fails, the averaging logic introduces rounding
    or normalization when it shouldn't.
    """
    assert abs(total_score([0.36]) - 0.36) < 1e-9


# ─────────────────────────────── end-to-end formula ─────────────────────────


def test_end_to_end_two_games():
    """Purpose: verify the complete scoring pipeline on two synthetic games.

    Game 1: 2 levels, win_levels=2.
      Level 1: human=30, agent=60  → score = (30/60)**2 = 0.25
      Level 2: human=60, agent=60  → score = 1.0
      game_score = (1*0.25 + 2*1.0) / (1+2) = 2.25 / 3 = 0.75

    Game 2: 1 level, win_levels=1.
      Level 1: human=20, agent=10  → capped → score = 1.0
      game_score = 1.0

    total_score = (0.75 + 1.0) / 2 = 0.875

    Expected feedback: if this fails, there is a cross-function integration
    error — check level_score capping, game_score weighting, or total_score mean.
    """
    # Game 1
    ls1a = level_score(30, 60)   # 0.25
    ls1b = level_score(60, 60)   # 1.0
    gs1 = game_score([ls1a, ls1b], win_levels=2)
    assert abs(gs1 - 0.75) < 1e-9

    # Game 2
    ls2a = level_score(20, 10)   # capped to 1.0
    gs2 = game_score([ls2a], win_levels=1)
    assert abs(gs2 - 1.0) < 1e-9

    ts = total_score([gs1, gs2])
    assert abs(ts - 0.875) < 1e-9
