"""Experience buffer with hash-based deduplication for ARC-AGI-3 agent."""

from __future__ import annotations

import hashlib
import random
from collections import deque

import numpy as np
import torch


class ExperienceBuffer:
    """Stores (frame, action, reward, next_frame) tuples with MD5 deduplication.

    Uses a fixed-size deque to bound memory usage. Duplicate experiences
    (same frame + action combination) are skipped to improve sample efficiency.

    Frames are stored as bool numpy arrays to save memory.
    Reward is a float in [0.0, 1.0] range.
    """

    def __init__(self, maxlen: int = 200_000) -> None:
        self._buffer: deque[tuple[np.ndarray, int, float, np.ndarray | None]] = deque(maxlen=maxlen)
        self._seen_hashes: set[str] = set()

    @staticmethod
    def _hash(frame: np.ndarray, action_idx: int) -> str:
        if hasattr(frame, 'numpy'):
            frame = frame.numpy()
        frame_bytes = frame.tobytes()
        action_bytes = int(action_idx).to_bytes(4, byteorder="little")
        return hashlib.md5(frame_bytes + action_bytes).hexdigest()

    def add(
        self,
        frame: np.ndarray,
        action_idx: int,
        reward: float | bool,
        next_frame: np.ndarray | None = None,
    ) -> bool:
        """Add an experience to the buffer. Skips duplicates.

        Args:
            frame: Bool numpy array of shape (16, 64, 64).
            action_idx: Action index (0-based).
            reward: Reward value (float 0.0-1.0, or bool for backward compat).
            next_frame: Bool numpy array of shape (16, 64, 64), or None.

        Returns:
            True if added, False if duplicate.
        """
        h = self._hash(frame, action_idx)
        if h in self._seen_hashes:
            return False
        self._seen_hashes.add(h)
        reward_f = float(reward)
        self._buffer.append((frame, action_idx, reward_f, next_frame))
        return True

    def sample(self, batch_size: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Sample a random batch from the buffer.

        Args:
            batch_size: Number of samples to draw.

        Returns:
            Tuple of (frames, actions, rewards):
                - frames: (batch_size, 16, 64, 64) float32
                - actions: (batch_size,) int64
                - rewards: (batch_size,) float32
        """
        if len(self._buffer) == 0:
            raise RuntimeError("Cannot sample from an empty buffer")
        batch = random.sample(list(self._buffer), min(batch_size, len(self._buffer)))
        frames = torch.from_numpy(np.stack([b[0] for b in batch]).astype(np.float32))
        actions = torch.tensor([b[1] for b in batch], dtype=torch.long)
        rewards = torch.tensor([b[2] for b in batch], dtype=torch.float32)
        return frames, actions, rewards  # (B, 16, 64, 64), (B,), (B,)

    def sample_with_next(
        self, batch_size: int
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor] | None:
        """Sample a batch that includes next_frame data (for World Model training).

        Only samples entries that have next_frame set. Returns None if not enough data.

        Args:
            batch_size: Number of samples to draw.

        Returns:
            Tuple of (frames, actions, rewards, next_frames) or None:
                - frames: (batch_size, 16, 64, 64) float32
                - actions: (batch_size,) int64
                - rewards: (batch_size,) float32
                - next_frames: (batch_size, 16, 64, 64) float32
        """
        candidates = [b for b in self._buffer if b[3] is not None]
        if len(candidates) < batch_size:
            return None
        batch = random.sample(candidates, batch_size)
        frames = torch.from_numpy(np.stack([b[0] for b in batch]).astype(np.float32))
        actions = torch.tensor([b[1] for b in batch], dtype=torch.long)
        rewards = torch.tensor([b[2] for b in batch], dtype=torch.float32)
        next_frames = torch.from_numpy(np.stack([b[3] for b in batch]).astype(np.float32))
        return frames, actions, rewards, next_frames

    def clear(self) -> None:
        """Clear the buffer and hash set. Call on level transitions."""
        self._buffer.clear()
        self._seen_hashes.clear()

    def __len__(self) -> int:
        return len(self._buffer)
