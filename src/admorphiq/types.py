"""Type abstractions for ARC-AGI-3 arcengine compatibility.

These mirror the arcengine types so the agent can be developed offline.
When arcengine is available, these can be replaced with direct imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import numpy as np


class GameState(Enum):
    """Game state as reported by arcengine."""
    NOT_PLAYED = auto()
    PLAYING = auto()
    WIN = auto()
    GAME_OVER = auto()


class ActionType(Enum):
    """Available action types in ARC-AGI-3."""
    ACTION1 = 1
    ACTION2 = 2
    ACTION3 = 3
    ACTION4 = 4
    ACTION5 = 5
    ACTION6 = 6  # requires coordinates
    ACTION7 = 7  # cancel/undo
    RESET = 8


@dataclass
class GameAction:
    """An action to take in the game."""
    action_type: ActionType
    x: int = 0
    y: int = 0

    @staticmethod
    def reset() -> GameAction:
        return GameAction(action_type=ActionType.RESET)

    @staticmethod
    def simple(action_type: ActionType) -> GameAction:
        return GameAction(action_type=action_type)

    @staticmethod
    def coordinate(x: int, y: int) -> GameAction:
        return GameAction(action_type=ActionType.ACTION6, x=x, y=y)


@dataclass
class FrameData:
    """A single frame from the game environment."""
    frame: np.ndarray  # (64, 64) uint8, values 0-15
    state: GameState = GameState.PLAYING
    score: dict[str, Any] = field(default_factory=dict)
    available_actions: list[ActionType] = field(default_factory=list)
