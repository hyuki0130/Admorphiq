"""Tests for admorphiq.types module."""

import numpy as np

from admorphiq.types import ActionType, FrameData, GameAction, GameState


class TestGameState:
    def test_enum_members(self):
        assert GameState.NOT_PLAYED is not None
        assert GameState.PLAYING is not None
        assert GameState.WIN is not None
        assert GameState.GAME_OVER is not None

    def test_enum_uniqueness(self):
        values = [s.value for s in GameState]
        assert len(values) == len(set(values)) == 4


class TestActionType:
    def test_action_values(self):
        assert ActionType.ACTION1.value == 1
        assert ActionType.ACTION6.value == 6
        assert ActionType.ACTION7.value == 7
        assert ActionType.RESET.value == 8

    def test_all_actions(self):
        assert len(ActionType) == 8


class TestGameAction:
    def test_reset(self):
        action = GameAction.reset()
        assert action.action_type == ActionType.RESET

    def test_simple(self):
        action = GameAction.simple(ActionType.ACTION3)
        assert action.action_type == ActionType.ACTION3
        assert action.x == 0
        assert action.y == 0

    def test_coordinate(self):
        action = GameAction.coordinate(32, 48)
        assert action.action_type == ActionType.ACTION6
        assert action.x == 32
        assert action.y == 48

    def test_default_coords(self):
        action = GameAction(action_type=ActionType.ACTION1)
        assert action.x == 0
        assert action.y == 0


class TestFrameData:
    def test_defaults(self):
        frame = np.zeros((64, 64), dtype=np.uint8)
        fd = FrameData(frame=frame)
        assert fd.state == GameState.PLAYING
        assert fd.score == {}
        assert fd.available_actions == []

    def test_custom_fields(self):
        frame = np.ones((64, 64), dtype=np.uint8)
        fd = FrameData(
            frame=frame,
            state=GameState.WIN,
            score={"levels_completed": 1},
            available_actions=[ActionType.ACTION1, ActionType.ACTION6],
        )
        assert fd.state == GameState.WIN
        assert fd.score["levels_completed"] == 1
        assert len(fd.available_actions) == 2
