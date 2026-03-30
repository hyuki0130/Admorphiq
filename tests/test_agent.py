"""Tests for admorphiq.agent.AdmorphiqAgent."""

from unittest.mock import patch

import numpy as np

from admorphiq.agent import AdmorphiqAgent
from admorphiq.types import ActionType, FrameData, GameAction, GameState


def _make_frame_data(
    state: GameState = GameState.PLAYING,
    available_actions: list[ActionType] | None = None,
    score: dict | None = None,
) -> FrameData:
    """Create a FrameData with a random 64x64 frame."""
    if available_actions is None:
        available_actions = [ActionType.ACTION1, ActionType.ACTION2, ActionType.ACTION6]
    return FrameData(
        frame=np.random.randint(0, 16, (64, 64), dtype=np.uint8),
        state=state,
        score=score or {},
        available_actions=available_actions,
    )


class TestIsDone:
    def test_win_returns_true(self):
        agent = AdmorphiqAgent()
        fd = _make_frame_data(state=GameState.WIN)
        assert agent.is_done([], fd) is True

    def test_playing_returns_false(self):
        agent = AdmorphiqAgent()
        fd = _make_frame_data(state=GameState.PLAYING)
        assert agent.is_done([], fd) is False

    def test_game_over_returns_false(self):
        agent = AdmorphiqAgent()
        fd = _make_frame_data(state=GameState.GAME_OVER)
        assert agent.is_done([], fd) is False

    def test_not_played_returns_false(self):
        agent = AdmorphiqAgent()
        fd = _make_frame_data(state=GameState.NOT_PLAYED)
        assert agent.is_done([], fd) is False


class TestChooseAction:
    def test_not_played_returns_reset(self):
        agent = AdmorphiqAgent()
        fd = _make_frame_data(state=GameState.NOT_PLAYED)
        action = agent.choose_action([], fd)
        assert action.action_type == ActionType.RESET

    def test_game_over_returns_reset(self):
        agent = AdmorphiqAgent()
        fd = _make_frame_data(state=GameState.GAME_OVER)
        action = agent.choose_action([], fd)
        assert action.action_type == ActionType.RESET

    def test_playing_returns_valid_action(self):
        agent = AdmorphiqAgent()
        fd = _make_frame_data(state=GameState.PLAYING)
        action = agent.choose_action([], fd)
        assert isinstance(action, GameAction)
        # Should be one of the available action types or a coordinate action
        valid_types = {ActionType.ACTION1, ActionType.ACTION2, ActionType.ACTION6, ActionType.RESET}
        assert action.action_type in valid_types

    def test_action6_coordinates_in_range(self):
        """When ACTION6 is chosen, x and y should be 0~63."""
        agent = AdmorphiqAgent()
        # Run multiple times to increase chance of getting ACTION6
        for _ in range(50):
            fd = _make_frame_data(
                available_actions=[ActionType.ACTION6],  # force ACTION6 only
            )
            action = agent.choose_action([], fd)
            if action.action_type == ActionType.ACTION6:
                assert 0 <= action.x <= 63, f"x={action.x} out of range"
                assert 0 <= action.y <= 63, f"y={action.y} out of range"


class TestLevelTransition:
    def test_buffer_cleared_on_level_change(self):
        agent = AdmorphiqAgent()
        # Play some steps to populate buffer
        for _ in range(3):
            fd = _make_frame_data(score={"levels_completed": 0})
            agent.choose_action([], fd)

        prev_buffer_len = len(agent.buffer)

        # Simulate level completion
        fd = _make_frame_data(score={"levels_completed": 1})
        agent.choose_action([], fd)

        # Buffer should be cleared on level transition
        assert len(agent.buffer) == 0


class TestTraining:
    def test_train_called_at_frequency(self):
        agent = AdmorphiqAgent(train_frequency=5, batch_size=2)

        # Fill buffer with enough samples
        for i in range(10):
            fd = _make_frame_data(score={"levels_completed": 0})
            agent.choose_action([], fd)

        # At step 5 (and 10), _train_step should have been called if buffer >= batch_size
        # We verify indirectly: the agent should not crash during training
        # More direct test with mock:
        agent2 = AdmorphiqAgent(train_frequency=2, batch_size=2)
        # Fill buffer first
        for i in range(5):
            fd = _make_frame_data(score={"levels_completed": 0})
            agent2.choose_action([], fd)

        with patch.object(agent2, "_train_step") as mock_train:
            # Reset step count so we can control it
            agent2._step_count = 1  # next step will be 2, which is divisible by 2
            fd = _make_frame_data(score={"levels_completed": 0})
            agent2.choose_action([], fd)
            if len(agent2.buffer) >= agent2.batch_size:
                mock_train.assert_called_once()


class TestWorldModelIntegration:
    def test_world_model_initialized(self):
        agent = AdmorphiqAgent()
        assert agent.world_model is not None

    def test_alpha_parameter(self):
        agent = AdmorphiqAgent(alpha=0.7)
        assert agent.alpha == 0.7

    def test_world_model_reset_on_level_change(self):
        agent = AdmorphiqAgent()
        original_wm_id = id(agent.world_model)

        # Play some steps
        for _ in range(3):
            fd = _make_frame_data(score={"levels_completed": 0})
            agent.choose_action([], fd)

        # Trigger level transition
        fd = _make_frame_data(score={"levels_completed": 1})
        agent.choose_action([], fd)

        # World model should be a new instance
        assert id(agent.world_model) != original_wm_id

    def test_wm_train_called_at_frequency(self):
        agent = AdmorphiqAgent(train_frequency=2, batch_size=2)
        # Fill buffer
        for i in range(5):
            fd = _make_frame_data(score={"levels_completed": 0})
            agent.choose_action([], fd)

        with patch.object(agent, "_train_world_model_step") as mock_wm_train:
            agent._step_count = 1  # next step will be 2
            fd = _make_frame_data(score={"levels_completed": 0})
            agent.choose_action([], fd)
            if len(agent.buffer) >= agent.batch_size:
                mock_wm_train.assert_called_once()

    def test_combined_probs_without_enough_buffer(self):
        """With insufficient buffer, world model probs should be None (pure perception)."""
        agent = AdmorphiqAgent(batch_size=100)  # large batch_size so WM won't activate
        fd = _make_frame_data()
        action = agent.choose_action([], fd)
        # Should still produce a valid action using perception only
        assert isinstance(action, GameAction)
