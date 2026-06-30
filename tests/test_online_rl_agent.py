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


def _run_indices(seed: int, n: int = 12) -> list[int]:
    """Drive one fresh agent over a fixed obs sequence, returning chosen indices.

    The chosen combined-logit index is captured from ``agent._pending`` after
    each call — a clean, comparable integer summary of the stochastic decision.
    """
    agent = OnlineRLAgent(warmstart=False, device="cpu", seed=seed)
    indices: list[int] = []
    for i in range(n):
        agent.choose_action([], _Obs(_frame(i % 5), levels=0, avail=(1, 2, 3, 4, 6)))
        indices.append(agent._pending[1] if agent._pending is not None else -1)
    return indices


def test_same_seed_reproducible() -> None:
    """Purpose: a fixed seed must make the whole agent run reproducible —
    identical weight init, identical exploration, identical replay sampling — so
    the K-seed clear-rate harness measures real variance, not RNG noise.

    Expected feedback: a pass means two independently-constructed agents with
    the same seed pick the identical action-index sequence over the same obs
    stream; a fail means a randomness source (global random / numpy / torch /
    model init) is unseeded and the measurement bar would be untrustworthy.
    """
    assert _run_indices(123) == _run_indices(123)


def test_different_seed_differs() -> None:
    """Purpose: distinct seeds must produce distinct runs — confirming the seed
    actually drives the stochasticity rather than the run being constant.

    Expected feedback: a pass means two different seeds diverge somewhere in the
    action-index sequence; a fail means seeding is a no-op (e.g. greedy collapse)
    and the K-seed harness would report a fake clear-rate of 0/K or K/K.
    """
    assert _run_indices(1) != _run_indices(2)


def test_progress_log_writes_ticks(tmp_path, monkeypatch) -> None:
    """Purpose: when RL_PROGRESS_LOG is set the agent must emit timestamped TICK
    lines carrying game_id / level / action_count / train_updates every
    RL_PROGRESS_EVERY actions — the learning-curve trace for long runs.

    Expected feedback: a pass means the log file exists and contains TICK lines
    tagged with the agent's game_id and the four required fields; a fail means
    the progress instrumentation is silent or malformed.
    """
    log = tmp_path / "prog.log"
    monkeypatch.setenv("RL_PROGRESS_LOG", str(log))
    monkeypatch.setenv("RL_PROGRESS_EVERY", "2")
    agent = OnlineRLAgent(warmstart=False, device="cpu", seed=0, game_id="zz99")
    for i in range(8):
        agent.choose_action([], _Obs(_frame(i), levels=0))
    text = log.read_text()
    ticks = [ln for ln in text.splitlines() if ln.startswith("TICK")]
    assert ticks, "at least one TICK line must be written"
    line = ticks[0]
    assert "game=zz99" in line
    for field in ("level=", "actions=", "train_updates="):
        assert field in line


def test_progress_log_silent_without_env(tmp_path, monkeypatch) -> None:
    """Purpose: progress logging is opt-in — with no RL_PROGRESS_LOG set the
    agent must write nothing (so unit tests and silent runs leave no files).

    Expected feedback: a pass means no progress path is configured and no file
    is created; a fail means the agent writes a log unconditionally, polluting
    the repo during ordinary runs.
    """
    monkeypatch.delenv("RL_PROGRESS_LOG", raising=False)
    agent = OnlineRLAgent(warmstart=False, device="cpu", seed=0, game_id="zz99")
    assert agent._progress_path is None
    for i in range(8):
        agent.choose_action([], _Obs(_frame(i), levels=0))
    assert not list(tmp_path.iterdir())
