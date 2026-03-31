"""Adapter bridging AdmorphiqAgent to the official ARC-AGI-3 Agent interface."""

from __future__ import annotations

from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

from .agent import AdmorphiqAgent
from .types import ActionType, FrameData, GameAction, GameState

# Try importing official framework types; fall back gracefully if unavailable.
try:
    from arcengine import GameAction as OfficialGameAction
    from arcengine import GameState as OfficialGameState

    _HAS_OFFICIAL = True
except ImportError:
    _HAS_OFFICIAL = False

# Official Agent base class is optional (only in ARC-AGI-3-Agents repo)
try:
    from agents.agent import Agent as OfficialAgent
except ImportError:
    OfficialAgent = object  # type: ignore[assignment,misc]

# Mapping from official state name strings to internal GameState.
_STATE_MAP: dict[str, GameState] = {
    "NOT_PLAYED": GameState.NOT_PLAYED,
    "NOT_FINISHED": GameState.PLAYING,
    "PLAYING": GameState.PLAYING,
    "WIN": GameState.WIN,
    "GAME_OVER": GameState.GAME_OVER,
}

# Official action int id → internal ActionType
_ACTION_ID_MAP: dict[int, ActionType] = {
    1: ActionType.ACTION1,
    2: ActionType.ACTION2,
    3: ActionType.ACTION3,
    4: ActionType.ACTION4,
    5: ActionType.ACTION5,
    6: ActionType.ACTION6,
    7: ActionType.ACTION7,
}


class AdmorphiqAdapter(OfficialAgent):  # type: ignore[misc]
    """Bridges the official ARC-AGI-3 Agent interface to our internal AdmorphiqAgent."""

    def __init__(self, **kwargs: Any) -> None:
        if _HAS_OFFICIAL:
            super().__init__(**kwargs)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self._agent = AdmorphiqAgent(device=device)

    # ------------------------------------------------------------------
    # Public interface (official Agent contract)
    # ------------------------------------------------------------------

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        internal_frame = self._convert_frame(latest_frame)
        return self._agent.is_done([], internal_frame)

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        internal_frame = self._convert_frame(latest_frame)
        internal_action = self._agent.choose_action([], internal_frame)
        return self._convert_action(internal_action)

    # ------------------------------------------------------------------
    # Type conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _layers_to_onehot(raw_frame: np.ndarray) -> torch.Tensor:
        """Convert (num_layers, 64, 64) int8 color indices to (16, 64, 64) float one-hot.

        For multi-layer frames, each layer is one-hot encoded independently
        and then merged via element-wise max (if any layer has that color at
        that position, the merged one-hot is 1).
        """
        if raw_frame.ndim == 2:
            raw_frame = raw_frame[np.newaxis]  # (1, 64, 64)

        layers = []
        for i in range(raw_frame.shape[0]):
            t = torch.from_numpy(raw_frame[i].astype(np.int64))  # (64, 64)
            onehot = F.one_hot(t.clamp(0, 15), num_classes=16)   # (64, 64, 16)
            layers.append(onehot.permute(2, 0, 1).float())       # (16, 64, 64)

        if len(layers) == 1:
            return layers[0]  # (16, 64, 64)

        stacked = torch.stack(layers)          # (num_layers, 16, 64, 64)
        return stacked.max(dim=0).values       # (16, 64, 64)

    @staticmethod
    def _convert_frame(official_frame: Any) -> FrameData:
        """Convert an official FrameData to our internal FrameData.

        Real frame format: (num_layers, 64, 64) int8 with color indices 0-15.
        num_layers varies per game (e.g. DC22=1, LF52=2).
        """
        # --- Frame data ---
        raw_frame = official_frame.frame if hasattr(official_frame, "frame") else official_frame
        if isinstance(raw_frame, np.ndarray):
            arr = raw_frame
        elif isinstance(raw_frame, list):
            arr = np.array(raw_frame, dtype=np.int8)
        else:
            arr = np.array(raw_frame, dtype=np.int8)

        # Preserve raw multi-layer data for proper one-hot encoding.
        raw_layers: np.ndarray | None = None
        if arr.ndim == 3:
            raw_layers = arr.copy()
            # Use first layer as canonical (H, W) index frame
            canonical = arr[0].astype(np.uint8)
        elif arr.ndim == 2:
            canonical = arr.astype(np.uint8)
        else:
            canonical = arr.astype(np.uint8)
        # canonical is (H, W) with values 0-15

        # --- State ---
        state = GameState.PLAYING
        if hasattr(official_frame, "state"):
            raw_state = official_frame.state
            if isinstance(raw_state, str):
                state = _STATE_MAP.get(raw_state, GameState.PLAYING)
            elif hasattr(raw_state, "name"):
                state = _STATE_MAP.get(raw_state.name, GameState.PLAYING)
            elif hasattr(raw_state, "value"):
                # Try matching by common enum patterns
                state = _STATE_MAP.get(str(raw_state.value), GameState.PLAYING)

        # --- Available actions ---
        available: list[ActionType] = []
        if hasattr(official_frame, "available_actions"):
            for a in official_frame.available_actions:
                action_id = a if isinstance(a, int) else getattr(a, "value", getattr(a, "id", None))
                if action_id is not None and action_id in _ACTION_ID_MAP:
                    available.append(_ACTION_ID_MAP[action_id])

        # --- Score ---
        score: dict[str, Any] = {}
        if hasattr(official_frame, "levels_completed"):
            score["levels_completed"] = official_frame.levels_completed
        elif hasattr(official_frame, "score") and isinstance(official_frame.score, dict):
            score = official_frame.score
        if hasattr(official_frame, "win_levels"):
            score["win_levels"] = official_frame.win_levels

        return FrameData(
            frame=canonical, state=state, score=score,
            available_actions=available, raw_layers=raw_layers,
        )

    @staticmethod
    def _convert_action(internal_action: GameAction) -> Any:
        """Convert our internal GameAction to an official GameAction."""
        if _HAS_OFFICIAL:
            if internal_action.action_type == ActionType.RESET:
                return OfficialGameAction.RESET  # type: ignore[union-attr]

            action_id = internal_action.action_type.value  # 1-7
            official = OfficialGameAction.from_id(action_id)  # type: ignore[union-attr]

            if internal_action.action_type == ActionType.ACTION6:
                official.set_data({"x": internal_action.x, "y": internal_action.y})

            return official

        # Fallback when official framework is not installed: return a dict representation
        result: dict[str, Any] = {"action": internal_action.action_type.name}
        if internal_action.action_type == ActionType.ACTION6:
            result["x"] = internal_action.x
            result["y"] = internal_action.y
        return result
