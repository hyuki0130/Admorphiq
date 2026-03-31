"""Graph-based agent for ARC-AGI-3 — pure exploration, no learning.

Uses state hashing and graph search to systematically explore game environments.
Based on the approach of the ARC-AGI-3 2nd place team (6.71%).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .planner.graph_explorer import GraphExplorer
from .types import ActionType, GameState

# Try importing official framework types
try:
    from arcengine import GameAction as OfficialGameAction
    from arcengine import GameState as OfficialGameState

    _HAS_OFFICIAL = True
except ImportError:
    _HAS_OFFICIAL = False

try:
    from agents.agent import Agent as OfficialAgent
except ImportError:
    OfficialAgent = object  # type: ignore[assignment,misc]

# State name string -> internal GameState
_STATE_MAP: dict[str, GameState] = {
    "NOT_PLAYED": GameState.NOT_PLAYED,
    "NOT_FINISHED": GameState.PLAYING,
    "PLAYING": GameState.PLAYING,
    "WIN": GameState.WIN,
    "GAME_OVER": GameState.GAME_OVER,
}

# Official action int id -> ActionType
_ACTION_ID_MAP: dict[int, ActionType] = {
    1: ActionType.ACTION1,
    2: ActionType.ACTION2,
    3: ActionType.ACTION3,
    4: ActionType.ACTION4,
    5: ActionType.ACTION5,
    6: ActionType.ACTION6,
    7: ActionType.ACTION7,
}


class GraphAgent(OfficialAgent):  # type: ignore[misc]
    """ARC-AGI-3 agent using pure graph-based exploration."""

    def __init__(self, **kwargs: Any) -> None:
        if _HAS_OFFICIAL and OfficialAgent is not object:
            super().__init__(**kwargs)
        self.explorer = GraphExplorer()
        self._last_levels_completed: int = 0

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        state = self._get_state(latest_frame)
        return state == GameState.WIN

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        state = self._get_state(latest_frame)

        # Handle terminal states
        if state in (GameState.NOT_PLAYED, GameState.GAME_OVER):
            return self._make_reset()

        # Get frame data
        frame = self._get_frame(latest_frame)

        # Detect level transition
        levels_completed = self._get_levels_completed(latest_frame)
        if levels_completed > self._last_levels_completed:
            self._last_levels_completed = levels_completed
            self.explorer.on_level_complete()

        # Record transition from previous action
        self.explorer.record_transition(frame)

        # Get available actions
        available_ids, action6_available = self._get_available_actions(latest_frame)

        if not available_ids and not action6_available:
            return self._make_reset()

        # Choose action via graph explorer
        action_id, x, y = self.explorer.choose_action(frame, available_ids, action6_available)

        # Convert to official action
        return self._make_action(action_id, x, y)

    def get_stats(self) -> dict[str, int]:
        """Return exploration statistics."""
        return self.explorer.stats()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_state(frame: Any) -> GameState:
        if hasattr(frame, "state"):
            raw = frame.state
            if isinstance(raw, str):
                return _STATE_MAP.get(raw, GameState.PLAYING)
            if hasattr(raw, "name"):
                return _STATE_MAP.get(raw.name, GameState.PLAYING)
        return GameState.PLAYING

    @staticmethod
    def _get_frame(frame: Any) -> np.ndarray:
        raw = frame.frame if hasattr(frame, "frame") else frame
        if isinstance(raw, np.ndarray):
            return raw
        return np.array(raw, dtype=np.int8)

    @staticmethod
    def _get_levels_completed(frame: Any) -> int:
        if hasattr(frame, "levels_completed"):
            return frame.levels_completed
        if hasattr(frame, "score") and isinstance(frame.score, dict):
            return frame.score.get("levels_completed", 0)
        return 0

    @staticmethod
    def _get_available_actions(frame: Any) -> tuple[list[int], bool]:
        """Extract available action ids and whether ACTION6 is available."""
        available_ids: list[int] = []
        action6 = False
        if hasattr(frame, "available_actions"):
            for a in frame.available_actions:
                aid = a if isinstance(a, int) else getattr(a, "value", getattr(a, "id", None))
                if aid is not None:
                    if aid == 6:
                        action6 = True
                    available_ids.append(aid)
        return available_ids, action6

    @staticmethod
    def _make_reset() -> Any:
        if _HAS_OFFICIAL:
            return OfficialGameAction.RESET  # type: ignore[union-attr]
        return {"action": "RESET"}

    @staticmethod
    def _make_action(action_id: int, x: int | None, y: int | None) -> Any:
        if _HAS_OFFICIAL:
            official = OfficialGameAction.from_id(action_id)  # type: ignore[union-attr]
            if action_id == 6 and x is not None and y is not None:
                official.set_data({"x": x, "y": y})
            return official
        result: dict[str, Any] = {"action": f"ACTION{action_id}"}
        if action_id == 6 and x is not None:
            result["x"] = x
            result["y"] = y
        return result
