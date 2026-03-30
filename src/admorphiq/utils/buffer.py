"""Experience buffer with hash-based deduplication for ARC-AGI-3 agent."""

import hashlib
import random
from collections import deque

import torch


class ExperienceBuffer:
    """Stores (frame, action, frame_changed) tuples with MD5 deduplication.

    Uses a fixed-size deque to bound memory usage. Duplicate experiences
    (same frame + action combination) are skipped to improve sample efficiency.
    """

    def __init__(self, maxlen: int = 200_000) -> None:
        self._buffer: deque[tuple[torch.Tensor, int, bool]] = deque(maxlen=maxlen)
        self._seen_hashes: set[str] = set()

    @staticmethod
    def _hash(frame: torch.Tensor, action_idx: int) -> str:
        frame_bytes = frame.cpu().numpy().tobytes()
        action_bytes = action_idx.to_bytes(4, byteorder="little")
        return hashlib.md5(frame_bytes + action_bytes).hexdigest()

    def add(self, frame: torch.Tensor, action_idx: int, frame_changed: bool) -> bool:
        """Add an experience to the buffer. Skips duplicates.

        Args:
            frame: Frame tensor of shape (16, 64, 64).
            action_idx: Action index (0-based).
            frame_changed: Whether the frame changed after the action.

        Returns:
            True if added, False if duplicate.
        """
        h = self._hash(frame, action_idx)
        if h in self._seen_hashes:
            return False
        self._seen_hashes.add(h)
        self._buffer.append((frame, action_idx, frame_changed))
        return True

    def sample(self, batch_size: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Sample a random batch from the buffer.

        Args:
            batch_size: Number of samples to draw.

        Returns:
            Tuple of (frames, actions, labels):
                - frames: (batch_size, 16, 64, 64)
                - actions: (batch_size,) int64
                - labels: (batch_size,) bool — whether frame changed
        """
        batch = random.sample(list(self._buffer), min(batch_size, len(self._buffer)))
        frames = torch.stack([b[0] for b in batch])
        actions = torch.tensor([b[1] for b in batch], dtype=torch.long)
        labels = torch.tensor([b[2] for b in batch], dtype=torch.bool)
        return frames, actions, labels  # (B, 16, 64, 64), (B,), (B,)

    def clear(self) -> None:
        """Clear the buffer and hash set. Call on level transitions."""
        self._buffer.clear()
        self._seen_hashes.clear()

    def __len__(self) -> int:
        return len(self._buffer)
