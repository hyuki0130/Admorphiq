"""Internal data types used across modules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GameActionRecord:
    """Lightweight record of an action taken (for memory replay)."""
    action_idx: int
