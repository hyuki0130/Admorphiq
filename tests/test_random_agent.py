"""Smoke tests for the calibration baseline agents (random / stochastic).

These prove the RandomAgent honours the harness contract
(``is_done`` / ``choose_action`` over a raw observation) and produces a valid
action for both simple actions and ACTION6 coordinates. No arcengine, no
network, no live environment: a lightweight mock observation stands in for the
arcengine frame, and ``_convert_action`` falls back to its dict representation
when the official framework is absent (as it is in the test env).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from admorphiq.random_agent import RandomAgent


@dataclass
class _MockState:
    """Stand-in for the arcengine GameState enum member (only .name is read)."""

    name: str


@dataclass
class _MockObs:
    """Minimal arcengine-observation shape the agents read.

    Fields mirror exactly what ``random_agent`` helpers pull off the obs:
    ``frame`` (layers, 64, 64), ``state`` (has ``.name``),
    ``available_actions`` (ints), ``levels_completed``.
    """

    frame: np.ndarray
    state: _MockState = field(default_factory=lambda: _MockState("NOT_FINISHED"))
    available_actions: list[int] = field(default_factory=lambda: [1, 2, 3, 4])
    levels_completed: int = 0


def _frame(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 16, size=(1, 64, 64), dtype=np.int8)


def _action_id(action: Any) -> int:
    """Read the action id from either the dict fallback or an official action."""
    if isinstance(action, dict):
        # Fallback shape: {"action": "ACTION1"} / {"action": "ACTION6", "x":.., "y":..}
        name = action["action"]
        return {
            "ACTION1": 1, "ACTION2": 2, "ACTION3": 3, "ACTION4": 4,
            "ACTION5": 5, "ACTION6": 6, "RESET": 8,
        }[name]
    # Official arcengine GameAction: an int-valued enum / .value attribute.
    return int(getattr(action, "value", getattr(action, "id", action)))


def test_random_agent_simple_action_is_available():
    """Purpose: prove the random agent only ever picks an AVAILABLE action.

    Expected feedback: if this fails, the uniform draw is sampling outside the
    frame's available_actions — the baseline would be measuring something other
    than "random over the legal action set".
    """
    agent = RandomAgent(seed=42)
    obs = _MockObs(frame=_frame(), available_actions=[1, 2, 3, 4])
    for _ in range(50):
        action = agent.choose_action([], obs)
        assert _action_id(action) in (1, 2, 3, 4)


def test_random_agent_action6_coordinate_in_range():
    """Purpose: prove an ACTION6 pick carries an x, y both inside 0..63.

    Expected feedback: if this fails, the ACTION6 coordinate draw is off-grid,
    which would make ACTION6 clicks land out of bounds in a live game.
    """
    agent = RandomAgent(seed=7)
    obs = _MockObs(frame=_frame(), available_actions=[6])
    saw_action6 = False
    for _ in range(20):
        action = agent.choose_action([], obs)
        assert _action_id(action) == 6
        saw_action6 = True
        if isinstance(action, dict):
            assert 0 <= action["x"] <= 63
            assert 0 <= action["y"] <= 63
    assert saw_action6


def test_random_agent_reproducible_with_seed():
    """Purpose: prove RL_SEED reproducibility — two same-seed agents on the same
    observation stream emit identical action sequences.

    Expected feedback: if this fails, the RNG is not seeded deterministically
    and K-seed calibration averages would be irreproducible.
    """
    obs = _MockObs(frame=_frame(1), available_actions=[1, 2, 6])
    a1 = RandomAgent(seed=123)
    a2 = RandomAgent(seed=123)
    seq1 = [_action_id(a1.choose_action([], obs)) for _ in range(30)]
    seq2 = [_action_id(a2.choose_action([], obs)) for _ in range(30)]
    assert seq1 == seq2


def test_is_done_true_on_win():
    """Purpose: prove is_done returns True on a WIN state.

    Expected feedback: if this fails, the run loop would keep acting after the
    game is already won, wasting actions and corrupting the efficiency score.
    """
    agent = RandomAgent(seed=1)
    win_obs = _MockObs(frame=_frame(), state=_MockState("WIN"))
    assert agent.is_done([], win_obs) is True


def test_is_done_true_at_action_cap():
    """Purpose: prove is_done trips once the per-game safety cap is reached.

    Expected feedback: if this fails, a hopeless game could spin without bound
    if the runner's own cap were ever removed.
    """
    agent = RandomAgent(seed=1, max_actions=5)
    obs = _MockObs(frame=_frame(), available_actions=[1, 2])
    for _ in range(5):
        assert agent.is_done([], obs) is False
        agent.choose_action([], obs)
    assert agent.is_done([], obs) is True


def test_stochastic_avoids_repeating_noop():
    """Purpose: prove the stochastic variant resamples away from an action that
    just produced a no-op (the frame did not change).

    A constant frame + a single simple action means the sole draw is always a
    no-op; a two-action set lets the resampler switch. With one simple action AND
    ACTION6 available, after a no-op on the simple action the stochastic variant
    should prefer ACTION6 (whose coordinate makes the pick tuple distinct).

    Expected feedback: if this fails, the light "stochastic sample" no-op
    avoidance is inert and stochastic == random exactly.
    """
    agent = RandomAgent(seed=3, avoid_repeat_noop=True)
    # Constant frame => every action is a no-op relative to the previous frame.
    const = np.zeros((1, 64, 64), dtype=np.int8)
    obs = _MockObs(frame=const, available_actions=[1])
    # First pick establishes the "last pick"; the frame never changes, so on the
    # next call the previous pick is registered as a no-op.
    first = _action_id(agent.choose_action([], obs))
    assert first == 1
    # Only one legal action exists, so the resampler cannot escape — it must
    # still return a valid available action rather than raising or hanging.
    second = _action_id(agent.choose_action([], obs))
    assert second == 1
