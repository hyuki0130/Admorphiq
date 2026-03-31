"""Systematic exploration strategy — prioritize untried (state, action) pairs."""

from __future__ import annotations

import hashlib
from collections import deque

import numpy as np
import torch


class SystematicExplorer:
    """Tracks tried actions per state and provides exploration bonuses.

    During early exploration, systematically tries all available actions.
    For ACTION6, samples on an 8x8 grid (stride=8) for coverage.
    """

    # 8x8 grid points for systematic ACTION6 exploration
    GRID_COORDS: list[tuple[int, int]] = [
        (x, y) for y in range(4, 64, 8) for x in range(4, 64, 8)
    ]

    # Minimum ACTION6 grid points to force during systematic phase
    FORCED_GRID_COORDS: list[tuple[int, int]] = [
        (4, 4), (32, 4), (60, 4), (4, 32),
        (32, 32), (60, 32), (4, 60), (32, 60),
    ]

    def __init__(self) -> None:
        self.tried_actions: dict[str, set[int]] = {}  # state_hash → {action_idx}
        self._action_queue: deque[int] = deque()
        self._current_state_hash: str | None = None
        self._global_tried: set[int] = set()  # actions tried across ALL states (for diversity)

    @staticmethod
    def hash_frame(frame_tensor: torch.Tensor) -> str:
        """Compute a compact hash of a frame tensor."""
        return hashlib.md5(frame_tensor.cpu().numpy().tobytes()).hexdigest()[:16]

    def get_exploration_bonus(
        self, state_hash: str, action_idx: int, num_available: int,
    ) -> float:
        """Return bonus for untried actions. 1.0 if untried, 0.0 if already tried."""
        tried = self.tried_actions.get(state_hash, set())
        if action_idx not in tried:
            return 1.0
        return 0.0

    def get_exploration_bonuses(
        self, state_hash: str, num_logits: int, available_mask: np.ndarray,
    ) -> np.ndarray:
        """Return exploration bonus array for all 4101 logits."""
        tried = self.tried_actions.get(state_hash, set())
        bonuses = np.zeros(num_logits, dtype=np.float64)
        for i in range(num_logits):
            if available_mask[i] and i not in tried:
                bonuses[i] = 1.0
        return bonuses

    def record_action(self, state_hash: str, action_idx: int) -> None:
        """Record that an action was tried in a given state and globally."""
        if state_hash not in self.tried_actions:
            self.tried_actions[state_hash] = set()
        self.tried_actions[state_hash].add(action_idx)
        self._global_tried.add(action_idx)

    def suggest_action(
        self, state_hash: str, available_simple: list[int], action6_available: bool,
    ) -> int | None:
        """Suggest an untried action, ensuring diversity across states.

        Priority:
        1. Simple actions never tried globally
        2. Forced ACTION6 grid points never tried globally
        3. Simple actions untried in current state
        4. Full ACTION6 grid untried in current state
        """
        tried = self.tried_actions.get(state_hash, set())

        # Priority 1: globally untried simple actions
        for idx in available_simple:
            if idx not in self._global_tried:
                return idx

        # Priority 2: forced ACTION6 grid points never tried globally
        if action6_available:
            for gx, gy in self.FORCED_GRID_COORDS:
                coord_idx = 5 + gy * 64 + gx
                if coord_idx not in self._global_tried:
                    return coord_idx

        # Priority 3: per-state untried simple actions
        for idx in available_simple:
            if idx not in tried:
                return idx

        # Priority 4: full grid untried in current state
        if action6_available:
            for gx, gy in self.GRID_COORDS:
                coord_idx = 5 + gy * 64 + gx
                if coord_idx not in tried:
                    return coord_idx

        return None

    def clear(self) -> None:
        """Clear exploration state for a new level."""
        self.tried_actions.clear()
        self._action_queue.clear()
        self._current_state_hash = None
        self._global_tried.clear()
