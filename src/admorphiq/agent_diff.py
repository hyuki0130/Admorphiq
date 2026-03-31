"""Frame Diff-based agent for ARC-AGI-3.

Uses FrameAnalyzer for initial game analysis and StateGraph for
exploration planning. No neural networks — pure diff-based reasoning.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from .perception.frame_analyzer import FrameAnalyzer
from .planner.state_graph import StateGraph


def _extract_frame(obs: Any) -> np.ndarray:
    """Extract a (64, 64) uint8 frame from an observation."""
    raw = obs.frame
    if hasattr(raw, '__len__') and len(raw) > 0:
        if hasattr(raw[0], 'shape'):
            return np.array(raw[0], dtype=np.uint8)
        arr = np.array(raw, dtype=np.uint8)
        if arr.ndim == 3:
            return arr[0]
        return arr
    arr = np.array(raw, dtype=np.uint8)
    if arr.ndim == 3:
        return arr[0]
    return arr


class DiffAgent:
    """Agent that uses frame diffs to understand and play ARC-AGI-3 games."""

    def __init__(self, analysis_trials: int = 3) -> None:
        self.analyzer = FrameAnalyzer()
        self.state_graph = StateGraph()
        self.analysis_trials = analysis_trials
        self._analyzed = False
        self._step_count = 0
        self._prev_frame: np.ndarray | None = None
        self._prev_hash: str | None = None
        self._prev_action_id: int | None = None
        self._planned_path: list[int] | None = None

    def reset(self) -> None:
        """Reset for a new game."""
        self.analyzer = FrameAnalyzer()
        self.state_graph = StateGraph()
        self._analyzed = False
        self._step_count = 0
        self._prev_frame = None
        self._prev_hash = None
        self._prev_action_id = None
        self._planned_path = None

    def play_game(self, env: Any, max_actions: int = 500) -> dict:
        """Play a full game and return metrics.

        Args:
            env: ARC-AGI-3 environment (from arcade.make()).
            max_actions: Maximum actions to take.

        Returns:
            Dict with game metrics.
        """
        from arcengine import GameAction

        self.reset()
        start_time = time.time()

        obs = env.observation_space
        if obs is None:
            return {"error": "No observation after make()"}

        # Phase 1: Initial analysis
        available_action_ids = list(obs.available_actions)
        try:
            analysis_result = self.analyzer.run_initial_analysis(
                env, available_action_ids, num_trials=self.analysis_trials,
            )
        except Exception:
            analysis_result = {
                "player_color": None, "direction_map": {},
                "game_type": "unknown", "wall_colors": set(),
                "actions_analyzed": 0,
            }

        # Reset after analysis
        obs = env.step(GameAction.RESET)
        if obs is None:
            return {"error": "Reset after analysis failed"}

        analysis_actions = self.analysis_trials * len(available_action_ids) + 1
        action_count = analysis_actions

        # Phase 2: Play using analysis results
        while action_count < max_actions:
            try:
                if obs.state.name == "WIN":
                    break
                if obs.state.name in ("GAME_OVER", "NOT_PLAYED"):
                    obs = env.step(GameAction.RESET)
                    action_count += 1
                    if obs is None:
                        break
                    continue

                frame = _extract_frame(obs)
                frame_hash = self.state_graph.add_state(frame)
                available = list(obs.available_actions)

                # Record transition from previous step
                if self._prev_hash is not None and self._prev_action_id is not None:
                    self.state_graph.add_transition(self._prev_hash, self._prev_action_id, frame_hash)

                # Choose action based on game type
                if self.analyzer.game_type == "movement":
                    action_id, coords = self._movement_strategy(frame, frame_hash, available)
                elif self.analyzer.game_type == "click":
                    action_id, coords = self._click_strategy(frame, frame_hash, available)
                elif self.analyzer.game_type == "hybrid":
                    action_id, coords = self._hybrid_strategy(frame, frame_hash, available)
                else:
                    action_id, coords = self._exploration_strategy(frame_hash, available)

                # Execute action
                action = GameAction.from_id(action_id)
                if action_id == 6 and coords is not None:
                    action.set_data({"x": coords[0], "y": coords[1]})
                    obs = env.step(action, data={"x": coords[0], "y": coords[1]})
                else:
                    obs = env.step(action)

                self._prev_frame = frame
                self._prev_hash = frame_hash
                self._prev_action_id = action_id
                self._step_count += 1
                action_count += 1

                if obs is None:
                    break
            except Exception:
                # Some games raise errors mid-play; try resetting
                try:
                    obs = env.step(GameAction.RESET)
                    action_count += 1
                    if obs is None:
                        break
                except Exception:
                    break

        elapsed = time.time() - start_time

        return {
            "actions": action_count,
            "elapsed_s": round(elapsed, 2),
            "ms_per_action": round(elapsed / max(action_count, 1) * 1000, 1),
            "state": obs.state.name if obs else "UNKNOWN",
            "levels_completed": obs.levels_completed if obs else 0,
            "win_levels": obs.win_levels if obs else 0,
            "game_type": self.analyzer.game_type,
            "player_color": self.analyzer.player_color,
            "states_discovered": self.state_graph.num_states,
            "transitions_recorded": self.state_graph.num_transitions,
            "analysis": analysis_result,
        }

    def _movement_strategy(
        self, frame: np.ndarray, frame_hash: str, available: list[int],
    ) -> tuple[int, tuple[int, int] | None]:
        """Strategy for movement-type games.

        Prioritize: untried directions > least-visited direction > planned path.
        """
        # Filter to direction actions only
        direction_actions = [a for a in available if a in self.analyzer.direction_map]

        if direction_actions:
            # Prefer untried directions from this state
            untried = self.state_graph.get_unvisited_actions(frame_hash, direction_actions)
            if untried:
                return int(np.random.choice(untried)), None

            # Follow planned path if we have one
            if self._planned_path:
                next_action = self._planned_path.pop(0)
                if next_action in available:
                    return next_action, None

            # Plan a path to least-visited state
            path = self.state_graph.get_path_to_least_visited(frame_hash)
            if path:
                self._planned_path = path[1:]  # save rest for later
                if path[0] in available:
                    return path[0], None

            # Fall back to least-visited action
            return self.state_graph.get_least_visited_action(frame_hash, direction_actions), None

        # No direction actions available — fall back to exploration
        return self._exploration_strategy(frame_hash, available)

    def _click_strategy(
        self, frame: np.ndarray, frame_hash: str, available: list[int],
    ) -> tuple[int, tuple[int, int] | None]:
        """Strategy for click-type games.

        Systematically try different coordinates with ACTION6.
        """
        if 6 in available:
            # Systematic grid scan
            grid_step = 8
            step = self._step_count
            grid_x = (step * grid_step) % 64
            grid_y = ((step * grid_step) // 64 * grid_step) % 64
            # Add some noise to avoid exact repeats
            x = min(63, max(0, grid_x + np.random.randint(-2, 3)))
            y = min(63, max(0, grid_y + np.random.randint(-2, 3)))
            return 6, (int(x), int(y))

        # Fall back to any available action
        return self._exploration_strategy(frame_hash, available)

    def _hybrid_strategy(
        self, frame: np.ndarray, frame_hash: str, available: list[int],
    ) -> tuple[int, tuple[int, int] | None]:
        """Strategy for hybrid games — alternate movement and clicks."""
        # Every 5th step try a click, otherwise move
        if self._step_count % 5 == 0 and 6 in available:
            return self._click_strategy(frame, frame_hash, available)
        return self._movement_strategy(frame, frame_hash, available)

    def _exploration_strategy(
        self, frame_hash: str, available: list[int],
    ) -> tuple[int, tuple[int, int] | None]:
        """Generic exploration — try untried actions, then least-visited."""
        # Filter out RESET (8) from exploration
        usable = [a for a in available if a != 8]
        if not usable:
            return 8, None  # Only reset available

        action = self.state_graph.get_least_visited_action(frame_hash, usable)

        coords = None
        if action == 6:
            # Random coordinate
            coords = (np.random.randint(0, 64), np.random.randint(0, 64))

        return action, coords
