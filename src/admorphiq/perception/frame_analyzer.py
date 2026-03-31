"""Frame diff-based game state analyzer.

Analyzes action effects by comparing frames before/after each action,
detecting player color, movement directions, walls, and game type.
"""

from __future__ import annotations

import numpy as np


def _extract_first_layer(raw_frame: object) -> np.ndarray:
    """Extract the first (64, 64) uint8 layer from a frame."""
    if hasattr(raw_frame, '__len__') and len(raw_frame) > 0:  # type: ignore[arg-type]
        if hasattr(raw_frame[0], 'shape'):  # type: ignore[index]
            return np.array(raw_frame[0], dtype=np.uint8)  # type: ignore[index]
        arr = np.array(raw_frame, dtype=np.uint8)
        if arr.ndim == 3:
            return arr[0]
        return arr
    arr = np.array(raw_frame, dtype=np.uint8)
    if arr.ndim == 3:
        return arr[0]
    return arr


class FrameAnalyzer:
    """Analyze game mechanics by observing frame diffs from actions."""

    def __init__(self) -> None:
        self.action_effects: dict[int, list[dict]] = {}  # action_id -> [diff results]
        self.player_color: int | None = None
        self.direction_map: dict[int, tuple[int, int]] = {}  # action_id -> (dy, dx)
        self.wall_colors: set[int] = set()
        self.game_type: str = "unknown"  # movement, click, hybrid, transform

    def analyze_action(
        self,
        frame_before: np.ndarray,
        frame_after: np.ndarray,
        action_id: int,
        coords: tuple[int, int] | None = None,
    ) -> dict:
        """Analyze the effect of a single action by comparing frames.

        Args:
            frame_before: (64, 64) uint8 frame before action.
            frame_after: (64, 64) uint8 frame after action.
            action_id: The action ID (1-7).
            coords: Optional (x, y) for ACTION6.

        Returns:
            Dict with action_id, coords, changed_pixels, movements, frame_changed.
        """
        diff = frame_after.astype(int) - frame_before.astype(int)
        changed_pixels = int(np.count_nonzero(diff))

        # Detect per-color movements by comparing center of mass
        movements: dict[int, dict] = {}
        for color in range(16):
            before_mask = frame_before == color
            after_mask = frame_after == color

            before_count = int(before_mask.sum())
            after_count = int(after_mask.sum())

            if before_count > 0 and after_count > 0:
                before_center = np.array(np.where(before_mask)).mean(axis=1)
                after_center = np.array(np.where(after_mask)).mean(axis=1)
                delta = after_center - before_center

                if np.abs(delta).max() > 0.5:
                    movements[color] = {
                        "dy": float(delta[0]),
                        "dx": float(delta[1]),
                        "pixel_count": after_count,
                    }

        result = {
            "action_id": action_id,
            "coords": coords,
            "changed_pixels": changed_pixels,
            "movements": movements,
            "frame_changed": changed_pixels > 0,
        }

        # Store for later analysis
        if action_id not in self.action_effects:
            self.action_effects[action_id] = []
        self.action_effects[action_id].append(result)

        return result

    def detect_player(self) -> int | None:
        """Detect the player color — the color that moves consistently with direction actions."""
        movement_counts: dict[int, int] = {}
        for action_id, effects in self.action_effects.items():
            if action_id in (1, 2, 3, 4, 5):
                for effect in effects:
                    for color in effect["movements"]:
                        movement_counts[color] = movement_counts.get(color, 0) + 1

        if movement_counts:
            self.player_color = max(movement_counts, key=movement_counts.get)  # type: ignore[arg-type]
            return self.player_color
        return None

    def detect_directions(self) -> dict[int, tuple[int, int]]:
        """Map each action ID to a direction (dy, dx) based on player movement."""
        if self.player_color is None:
            return {}

        directions: dict[int, tuple[int, int]] = {}
        for action_id, effects in self.action_effects.items():
            if action_id not in (1, 2, 3, 4, 5):
                continue
            deltas: list[tuple[float, float]] = []
            for effect in effects:
                if self.player_color in effect["movements"]:
                    mov = effect["movements"][self.player_color]
                    deltas.append((mov["dy"], mov["dx"]))
            if deltas:
                avg_dy = sum(d[0] for d in deltas) / len(deltas)
                avg_dx = sum(d[1] for d in deltas) / len(deltas)
                # Snap to cardinal direction
                if abs(avg_dy) > abs(avg_dx):
                    directions[action_id] = (-1 if avg_dy < 0 else 1, 0)
                else:
                    directions[action_id] = (0, -1 if avg_dx < 0 else 1)

        self.direction_map = directions
        return directions

    def detect_walls(self, frame: np.ndarray) -> set[int]:
        """Detect wall/obstacle colors — colors adjacent to blocked movements.

        When a movement action didn't move the player, the color in the
        movement direction is likely a wall.
        """
        if self.player_color is None or not self.direction_map:
            return set()

        wall_candidates: dict[int, int] = {}  # color -> count

        for action_id, effects in self.action_effects.items():
            if action_id not in self.direction_map:
                continue
            dy, dx = self.direction_map[action_id]

            for effect in effects:
                # If player didn't move for this action, check what's ahead
                if self.player_color not in effect["movements"]:
                    # Use the frame to find adjacent color
                    player_mask = frame == self.player_color
                    if not player_mask.any():
                        continue
                    center_y, center_x = np.array(np.where(player_mask)).mean(axis=1)
                    check_y = int(center_y) + dy
                    check_x = int(center_x) + dx
                    if 0 <= check_y < 64 and 0 <= check_x < 64:
                        ahead_color = int(frame[check_y, check_x])
                        if ahead_color != self.player_color and ahead_color != 0:
                            wall_candidates[ahead_color] = wall_candidates.get(ahead_color, 0) + 1

        # Colors that blocked movement at least once
        self.wall_colors = {c for c, count in wall_candidates.items() if count >= 1}
        return self.wall_colors

    def classify_game(self) -> str:
        """Classify game type based on observed action effects."""
        has_movement = bool(self.direction_map)
        has_click = any(
            any(e["frame_changed"] for e in effects)
            for action_id, effects in self.action_effects.items()
            if action_id == 6
        )

        if has_movement and has_click:
            self.game_type = "hybrid"
        elif has_movement:
            self.game_type = "movement"
        elif has_click:
            self.game_type = "click"
        else:
            self.game_type = "unknown"
        return self.game_type

    def run_initial_analysis(
        self,
        env,
        available_actions: list[int],
        num_trials: int = 3,
    ) -> dict:
        """Run initial analysis by trying each action multiple times.

        Resets the game between trials. Returns a summary dict.

        Args:
            env: ARC-AGI-3 environment (with .step() and .observation_space).
            available_actions: List of available action IDs (1-7).
            num_trials: Number of trials per action.

        Returns:
            Summary dict with player_color, direction_map, game_type, wall_colors.
        """
        from arcengine import GameAction

        last_frame: np.ndarray | None = None

        for action_id in available_actions:
            self.action_effects[action_id] = []

            for _trial in range(num_trials):
                try:
                    # Reset to get a clean state
                    obs = env.step(GameAction.RESET)
                    if obs is None:
                        continue

                    frame_before = _extract_first_layer(obs.frame)

                    # Execute action
                    action = GameAction.from_id(action_id)
                    if action_id == 6:
                        action.set_data({"x": 32, "y": 32})
                        obs = env.step(action, data={"x": 32, "y": 32})
                        coords: tuple[int, int] | None = (32, 32)
                    else:
                        obs = env.step(action)
                        coords = None

                    if obs is None:
                        continue

                    frame_after = _extract_first_layer(obs.frame)
                    last_frame = frame_after

                    self.analyze_action(frame_before, frame_after, action_id, coords)
                except Exception:
                    # Some game environments may raise errors for certain actions
                    continue

        # Run detections
        self.detect_player()
        self.detect_directions()
        self.classify_game()

        # Detect walls using last observed frame
        if last_frame is not None:
            self.detect_walls(last_frame)

        return {
            "player_color": self.player_color,
            "direction_map": self.direction_map,
            "game_type": self.game_type,
            "wall_colors": self.wall_colors,
            "actions_analyzed": len(self.action_effects),
        }
