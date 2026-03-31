"""Game play logging for ARC-AGI-3 agents."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


class GameLogger:
    """Structured JSONL logger for game play analysis."""

    def __init__(self, game_id: str, agent_name: str, log_dir: str = "logs") -> None:
        self.game_id = game_id
        self.agent_name = agent_name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"{game_id}_{agent_name}_{timestamp}.jsonl"

    def _write(self, entry: dict[str, Any]) -> None:
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def log_step(
        self,
        step: int,
        action: Any,
        obs: Any = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Log a single action step."""
        entry: dict[str, Any] = {
            "type": "step",
            "step": step,
            "action": str(action),
        }
        if obs is not None:
            entry["state"] = str(obs.state) if hasattr(obs, "state") else None
            entry["levels_completed"] = getattr(obs, "levels_completed", None)
            entry["win_levels"] = getattr(obs, "win_levels", None)
        if extra:
            entry.update(extra)
        self._write(entry)

    def log_frame_diff(
        self,
        step: int,
        frame_before: np.ndarray,
        frame_after: np.ndarray,
        action: Any,
    ) -> None:
        """Log frame change details including pixel count and color movements."""
        diff = frame_after.astype(int) - frame_before.astype(int)
        changed_pixels = int(np.count_nonzero(diff))

        movements: dict[str, dict[str, float]] = {}
        for color in range(16):
            before_pos = np.argwhere(frame_before == color)
            after_pos = np.argwhere(frame_after == color)
            if len(before_pos) > 0 and len(after_pos) > 0:
                b_center = before_pos.mean(axis=0)
                a_center = after_pos.mean(axis=0)
                delta = a_center - b_center
                if np.abs(delta).max() > 0.5:
                    movements[str(color)] = {
                        "dy": round(float(delta[0]), 1),
                        "dx": round(float(delta[1]), 1),
                    }

        self._write({
            "type": "frame_diff",
            "step": step,
            "action": str(action),
            "changed_pixels": changed_pixels,
            "movements": movements,
        })

    def log_event(self, event_type: str, details: dict[str, Any] | None = None) -> None:
        """Log a discrete event (level_up, reset, error, strategy_switch, etc.)."""
        entry: dict[str, Any] = {"type": "event", "event": event_type}
        if details:
            entry.update(details)
        self._write(entry)

    def log_summary(
        self,
        total_actions: int,
        levels_cleared: int,
        elapsed: float,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Log end-of-game summary."""
        entry: dict[str, Any] = {
            "type": "summary",
            "game_id": self.game_id,
            "agent": self.agent_name,
            "total_actions": total_actions,
            "levels_cleared": levels_cleared,
            "elapsed_seconds": round(elapsed, 2),
            "ms_per_action": round(elapsed / max(total_actions, 1) * 1000, 1),
        }
        if extra:
            entry.update(extra)
        self._write(entry)
