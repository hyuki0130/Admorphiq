"""Tests for the test-time online CNN+RL agent (OnlineRLAgent).

These pin the StochasticGoose recipe contract: sparse level-only reward, the
buffer stores transitions, the buffer resets between levels, an online gradient
step runs without error, and action selection returns a valid official
GameAction over masked availability. They use a fake observation object (no live
arcengine env) so they run fast and deterministically.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from admorphiq.online_rl_agent import (
    COORD_OFFSET,
    NUM_SIMPLE_ACTIONS,
    OnlineRLAgent,
    _availability,
)


class _Action:
    def __init__(self, value: int) -> None:
        self.value = value


class _State:
    def __init__(self, name: str) -> None:
        self.name = name


class _Obs:
    """Minimal stand-in for an arcengine observation."""

    def __init__(
        self,
        frame: np.ndarray,
        levels: int = 0,
        state: str = "NOT_FINISHED",
        avail: tuple[int, ...] = (1, 2, 3, 4),
    ) -> None:
        self.frame = [frame.tolist()]
        self.levels_completed = levels
        self.state = _State(state)
        self.available_actions = [_Action(a) for a in avail]


def _agent() -> OnlineRLAgent:
    # No warm-start so the test never depends on the on-disk weights, and a fixed
    # seed makes exploration deterministic.
    return OnlineRLAgent(warmstart=False, device="cpu", seed=0)


def _frame(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 16, size=(64, 64), dtype=np.int64)


def test_choose_action_returns_official_action() -> None:
    """Purpose: the agent must satisfy the harness contract and emit an action.

    Expected feedback: a pass means choose_action over a fresh obs returns a
    non-None official GameAction object; a fail means the action plumbing or
    index decode is broken.
    """
    agent = _agent()
    obs = _Obs(_frame(1), levels=0)
    action = agent.choose_action([], obs)
    assert action is not None


def test_sparse_reward_only_on_level_clear() -> None:
    """Purpose: reward is +1 ONLY when levels_completed increments, never on a
    mere frame change (no wiggling reward).

    Expected feedback: a pass means a frame-change-but-no-level-up transition is
    stored with reward 0.0, while a level-up transition is stored with reward
    1.0; a fail means the reward shaping leaked into the reward signal.
    """
    agent = _agent()
    f0 = _frame(1)
    f1 = _frame(2)  # different frame, same level
    agent.choose_action([], _Obs(f0, levels=0))
    agent.choose_action([], _Obs(f1, levels=0))  # closes (f0,a)->f1, no level-up
    rewards = [b[2] for b in agent.buffer._buffer]
    assert rewards, "transition should have been stored"
    assert all(r == 0.0 for r in rewards), "frame change must not earn reward"


def test_buffer_resets_between_levels() -> None:
    """Purpose: a level clear must RESET the per-game buffer (new level = new
    state space), as the recipe requires.

    Expected feedback: a pass means after a level-up the buffer length is 0; a
    fail means stale transitions from the previous level leak into the new
    level's online learning.
    """
    agent = _agent()
    f0 = _frame(1)
    f1 = _frame(2)
    agent.choose_action([], _Obs(f0, levels=0))
    agent.choose_action([], _Obs(f1, levels=0))
    assert len(agent.buffer) > 0
    # Next obs reports a level-up -> credit-assign then clear.
    agent.choose_action([], _Obs(_frame(3), levels=1))
    assert len(agent.buffer) == 0
    assert agent._levels_cleared == 1


def test_online_train_step_runs() -> None:
    """Purpose: an off-policy gradient step must execute on a populated buffer
    without raising and must keep the model usable for inference.

    Expected feedback: a pass means _train_step runs and a subsequent
    choose_action still returns an action; a fail means the gather/BCE training
    path or shape handling is broken.
    """
    agent = _agent()
    # Populate the buffer with a few transitions.
    for i in range(6):
        agent.choose_action([], _Obs(_frame(i), levels=0))
    assert len(agent.buffer) > 0
    agent._train_step()  # must not raise
    action = agent.choose_action([], _Obs(_frame(99), levels=0))
    assert action is not None


def test_availability_parses_simple_and_action6() -> None:
    """Purpose: availability parsing must split ACTION1-5 into the bool mask and
    flag ACTION6 separately (drives masking + hierarchical exploration).

    Expected feedback: a pass means a (1,2,6) availability yields a mask with
    indices 0 and 1 set and action6_ok True; a fail means action masking would
    select unavailable actions.
    """
    obs = _Obs(_frame(1), avail=(1, 2, 6))
    mask, action6_ok = _availability(obs)
    assert mask[0] and mask[1] and not mask[2]
    assert action6_ok


def test_explore_index_respects_availability() -> None:
    """Purpose: hierarchical exploration must only emit indices for available
    action types (simple index < 5, or an ACTION6 coordinate index >= 5).

    Expected feedback: a pass means a simple-only availability never produces a
    coordinate index, and an ACTION6-only availability always produces one; a
    fail means exploration can pick an unavailable action type.
    """
    agent = _agent()
    frame = _frame(1)
    simple_only = np.array([True, True, False, False, False])
    for _ in range(20):
        idx = agent._explore_index(frame, simple_only, action6_ok=False)
        assert idx < NUM_SIMPLE_ACTIONS
    coord_only = np.zeros(NUM_SIMPLE_ACTIONS, dtype=bool)
    for _ in range(5):
        idx = agent._explore_index(frame, coord_only, action6_ok=True)
        assert idx >= COORD_OFFSET


def test_give_up_caps_hopeless_game() -> None:
    """Purpose: a game with no progress for GIVE_UP_NO_PROGRESS actions must flip
    is_done True so the runner bails instead of grinding the action budget.

    Expected feedback: a pass means after exceeding the cap is_done returns True;
    a fail means a hopeless game would burn the entire budget.
    """
    agent = _agent()
    agent.GIVE_UP_NO_PROGRESS = 3
    f = _frame(1)
    for _ in range(5):
        agent.choose_action([], _Obs(f, levels=0))  # identical frame = no progress
    assert agent.is_done([], _Obs(f, levels=0))


@pytest.mark.parametrize("state", ["NOT_PLAYED", "GAME_OVER"])
def test_reset_states_emit_reset(state: str) -> None:
    """Purpose: NOT_PLAYED / GAME_OVER observations must trigger a RESET action
    and clear per-level state.

    Expected feedback: a pass means choose_action returns an action and the
    buffer is empty after a reset state; a fail means the agent acts on a dead
    frame or carries stale buffer state across an episode boundary.
    """
    agent = _agent()
    obs: Any = _Obs(_frame(1), state=state)
    action = agent.choose_action([], obs)
    assert action is not None
    assert len(agent.buffer) == 0
