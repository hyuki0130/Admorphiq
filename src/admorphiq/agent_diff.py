"""Frame Diff-based agent for ARC-AGI-3.

Uses FrameAnalyzer for initial game analysis and StateGraph for
exploration planning. No neural networks — pure diff-based reasoning.

Enhanced with:
- Systematic spiral/zigzag movement patterns
- Click effect learning (track which coords cause changes)
- Connected component player tracking
- Wall map building for movement games
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
        # Enhanced: track effective click coordinates
        self._effective_clicks: list[tuple[int, int]] = []
        self._ineffective_clicks: list[tuple[int, int]] = []
        # Enhanced: wall map for movement games
        self._wall_map: np.ndarray | None = None
        # Enhanced: player position tracking
        self._player_positions: list[tuple[int, int]] = []
        # Enhanced: spiral movement pattern
        self._spiral_actions: list[int] = []
        self._spiral_idx: int = 0
        # Enhanced: action sequence that caused level progress
        self._successful_sequences: list[list[int]] = []
        self._current_sequence: list[int] = []
        # Track levels for detecting progress
        self._last_levels_completed: int = 0
        # Last click coordinates for tracking effectiveness
        self._last_click_coords: tuple[int, int] | None = None
        # Global action counter (never resets, for coordinate generation)
        self._global_step: int = 0

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
        self._effective_clicks.clear()
        self._ineffective_clicks.clear()
        self._wall_map = None
        self._player_positions.clear()
        self._spiral_actions.clear()
        self._spiral_idx = 0
        self._successful_sequences.clear()
        self._current_sequence.clear()
        self._last_levels_completed = 0
        self._last_click_coords = None

    def play_game(self, env: Any, max_actions: int = 500, time_limit: float = 300.0) -> dict:
        """Play a full game and return metrics.

        Args:
            env: ARC-AGI-3 environment (from arcade.make()).
            max_actions: Maximum actions to take (fallback).
            time_limit: Time limit in seconds (default 5 minutes).

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

        # Build spiral pattern if movement game
        if self.analyzer.game_type == "movement" and self.analyzer.direction_map:
            self._build_spiral_pattern()

        # Initialize wall map
        self._wall_map = np.zeros((64, 64), dtype=np.uint8)

        # Phase 2: Play using analysis results
        while action_count < max_actions:
            elapsed = time.time() - start_time
            if elapsed > time_limit:
                break

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

                # Detect level transition
                levels_completed = obs.levels_completed if hasattr(obs, 'levels_completed') else 0
                if levels_completed > self._last_levels_completed:
                    self._last_levels_completed = levels_completed
                    # Save successful sequence
                    if self._current_sequence:
                        self._successful_sequences.append(self._current_sequence.copy())
                    self._current_sequence.clear()
                    self.state_graph.clear()
                    self._wall_map = np.zeros((64, 64), dtype=np.uint8)
                    self._spiral_idx = 0
                    self._prev_frame = None
                    self._prev_hash = None
                    self._prev_action_id = None
                    self._effective_clicks.clear()
                    self._ineffective_clicks.clear()
                    self._step_count = 0
                    # Re-analyze for new level
                    try:
                        re_analysis = self.analyzer.run_initial_analysis(
                            env, available, num_trials=2,
                        )
                        obs = env.step(GameAction.RESET)
                        action_count += len(available) * 2 + 1
                        if obs is None:
                            break
                        if self.analyzer.game_type == "movement" and self.analyzer.direction_map:
                            self._build_spiral_pattern()
                        frame = _extract_frame(obs)
                        frame_hash = self.state_graph.add_state(frame)
                    except Exception:
                        pass

                # Record transition from previous step
                if self._prev_hash is not None and self._prev_action_id is not None:
                    self.state_graph.add_transition(self._prev_hash, self._prev_action_id, frame_hash)
                    # Track click effectiveness
                    if self._prev_action_id == 6 and self._prev_frame is not None:
                        diff_count = int(np.count_nonzero(frame != self._prev_frame))
                        if diff_count > 5 and hasattr(self, '_last_click_coords') and self._last_click_coords is not None:
                            self._effective_clicks.append(self._last_click_coords)

                # Track player position
                if self.analyzer.player_color is not None:
                    player_mask = frame == self.analyzer.player_color
                    if player_mask.any():
                        cy, cx = np.array(np.where(player_mask)).mean(axis=1)
                        self._player_positions.append((int(cy), int(cx)))
                        # Update wall map based on blocked movements
                        if self._prev_frame is not None and self._prev_action_id in self.analyzer.direction_map:
                            dy, dx = self.analyzer.direction_map[self._prev_action_id]
                            prev_mask = self._prev_frame == self.analyzer.player_color
                            if prev_mask.any():
                                prev_cy, prev_cx = np.array(np.where(prev_mask)).mean(axis=1)
                                if abs(cy - prev_cy) < 0.5 and abs(cx - prev_cx) < 0.5:
                                    # Player didn't move -> wall ahead
                                    wall_y = int(prev_cy) + dy * 2
                                    wall_x = int(prev_cx) + dx * 2
                                    if 0 <= wall_y < 64 and 0 <= wall_x < 64:
                                        self._wall_map[wall_y, wall_x] = 1

                # Choose action based on game type
                if self.analyzer.game_type == "movement":
                    action_id, coords = self._movement_strategy(frame, frame_hash, available)
                elif self.analyzer.game_type == "click":
                    action_id, coords = self._click_strategy(frame, frame_hash, available)
                elif self.analyzer.game_type == "hybrid":
                    action_id, coords = self._hybrid_strategy(frame, frame_hash, available)
                else:
                    action_id, coords = self._exploration_strategy(frame_hash, available)

                self._current_sequence.append(action_id)

                # Execute action
                self._last_click_coords = coords if action_id == 6 else None
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
                self._global_step += 1
                action_count += 1

                if obs is None:
                    break
            except Exception:
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

    def _build_spiral_pattern(self) -> None:
        """Build a spiral movement pattern using direction map.

        Creates a sequence: go N steps right, N steps down, N steps left, N steps up,
        expanding the spiral each iteration.
        """
        dm = self.analyzer.direction_map
        if not dm:
            return

        # Find action IDs for each direction
        right_id = left_id = up_id = down_id = None
        for aid, (dy, dx) in dm.items():
            if dx > 0:
                right_id = aid
            elif dx < 0:
                left_id = aid
            elif dy > 0:
                down_id = aid
            elif dy < 0:
                up_id = aid

        if not all([right_id, down_id, left_id, up_id]):
            # Can't build full spiral, use zigzag instead
            self._build_zigzag_pattern()
            return

        # Generate expanding spiral
        pattern = []
        for size in range(1, 20):
            pattern.extend([right_id] * size)
            pattern.extend([down_id] * size)
            pattern.extend([left_id] * (size + 1))
            pattern.extend([up_id] * (size + 1))

        self._spiral_actions = pattern

    def _build_zigzag_pattern(self) -> None:
        """Build zigzag movement pattern using available directions."""
        dm = self.analyzer.direction_map
        if not dm:
            return
        aids = list(dm.keys())
        if len(aids) < 2:
            return

        # Alternate between first two directions
        pattern = []
        for size in range(3, 20):
            pattern.extend([aids[0]] * size)
            pattern.extend([aids[1]] * size)

        self._spiral_actions = pattern

    def _movement_strategy(
        self, frame: np.ndarray, frame_hash: str, available: list[int],
    ) -> tuple[int, tuple[int, int] | None]:
        """Strategy for movement-type games.

        Enhanced with spiral/zigzag exploration and wall-aware navigation.
        """
        direction_actions = [a for a in available if a in self.analyzer.direction_map]

        if direction_actions:
            # Priority 1: untried directions from this state
            untried = self.state_graph.get_unvisited_actions(frame_hash, direction_actions)
            if untried:
                # Prefer directions that don't lead to known walls
                if self.analyzer.player_color is not None and self._wall_map is not None:
                    player_mask = frame == self.analyzer.player_color
                    if player_mask.any():
                        cy, cx = np.array(np.where(player_mask)).mean(axis=1)
                        safe_untried = []
                        for aid in untried:
                            dy, dx = self.analyzer.direction_map[aid]
                            check_y, check_x = int(cy) + dy * 2, int(cx) + dx * 2
                            if 0 <= check_y < 64 and 0 <= check_x < 64:
                                if self._wall_map[check_y, check_x] == 0:
                                    safe_untried.append(aid)
                        if safe_untried:
                            return int(np.random.choice(safe_untried)), None
                return int(np.random.choice(untried)), None

            # Priority 2: Follow spiral pattern
            if self._spiral_actions and self._spiral_idx < len(self._spiral_actions):
                next_action = self._spiral_actions[self._spiral_idx]
                self._spiral_idx += 1
                if next_action in available:
                    return next_action, None

            # Priority 3: Follow planned path
            if self._planned_path:
                next_action = self._planned_path.pop(0)
                if next_action in available:
                    return next_action, None

            # Priority 4: Plan path to least-visited state
            path = self.state_graph.get_path_to_least_visited(frame_hash)
            if path:
                self._planned_path = path[1:]
                if path[0] in available:
                    return path[0], None

            # Priority 5: Least-visited action
            return self.state_graph.get_least_visited_action(frame_hash, direction_actions), None

        return self._exploration_strategy(frame_hash, available)

    def _click_strategy(
        self, frame: np.ndarray, frame_hash: str, available: list[int],
    ) -> tuple[int, tuple[int, int] | None]:
        """Strategy for click-type games.

        Systematic approach:
        1. Click every non-background pixel (most likely to be interactive)
        2. Use effective click history to focus on productive regions
        3. Fall back to fine grid scan
        """
        if 6 in available:
            # Priority 1: If we have effective clicks, exploit them with variations
            if self._effective_clicks and self._step_count > 50:
                if self._step_count % 3 == 0:
                    # Exploit: click near known effective positions
                    base = self._effective_clicks[self._step_count % len(self._effective_clicks)]
                    x = min(63, max(0, base[0] + np.random.randint(-3, 4)))
                    y = min(63, max(0, base[1] + np.random.randint(-3, 4)))
                    return 6, (int(x), int(y))

            # Priority 2: Click on non-background pixels systematically
            targets = self._get_nonbackground_pixels(frame)
            if targets:
                idx = self._step_count % len(targets)
                return 6, targets[idx]

            # Priority 3: Fine grid scan covering every 2 pixels
            grid_step = 2
            total_grid = (64 // grid_step) ** 2
            grid_idx = self._step_count % total_grid
            grid_x = (grid_idx % (64 // grid_step)) * grid_step + 1
            grid_y = (grid_idx // (64 // grid_step)) * grid_step + 1
            return 6, (int(grid_x), int(grid_y))

        return self._exploration_strategy(frame_hash, available)

    def _get_nonbackground_pixels(self, frame: np.ndarray) -> list[tuple[int, int]]:
        """Get all non-background pixel coordinates, sampled for coverage."""
        colors, counts = np.unique(frame, return_counts=True)
        if len(colors) <= 1:
            return []

        bg_color = colors[counts.argmax()]
        non_bg = frame != bg_color
        if not non_bg.any():
            return []

        ys, xs = np.where(non_bg)
        if len(ys) == 0:
            return []

        # Sample up to 500 positions evenly distributed
        n_samples = min(500, len(ys))
        indices = np.linspace(0, len(ys) - 1, n_samples, dtype=int)
        return [(int(xs[i]), int(ys[i])) for i in indices]

    def _find_interesting_click_targets(self, frame: np.ndarray) -> list[tuple[int, int]]:
        """Find interesting positions to click based on frame content."""
        # Find non-background colors
        colors, counts = np.unique(frame, return_counts=True)
        if len(colors) <= 1:
            return []

        bg_color = colors[counts.argmax()]
        targets = []

        # Click on edges of non-background regions
        for color in colors:
            if color == bg_color:
                continue
            mask = frame == color
            if not mask.any():
                continue
            ys, xs = np.where(mask)
            if len(ys) == 0:
                continue
            # Sample boundary pixels
            n_samples = min(8, len(ys))
            indices = np.linspace(0, len(ys) - 1, n_samples, dtype=int)
            for idx in indices:
                targets.append((int(xs[idx]), int(ys[idx])))

        return targets

    def _hybrid_strategy(
        self, frame: np.ndarray, frame_hash: str, available: list[int],
    ) -> tuple[int, tuple[int, int] | None]:
        """Strategy for hybrid games — smarter alternation between movement and clicks.

        Enhanced: Try movement first to explore, then click at new positions.
        """
        # First 70% of steps: prioritize movement to explore the space
        # Last 30%: try clicking at interesting positions
        if self._step_count % 3 != 0:
            result = self._movement_strategy(frame, frame_hash, available)
            if result[0] in self.analyzer.direction_map:
                return result
        if 6 in available:
            return self._click_strategy(frame, frame_hash, available)
        return self._movement_strategy(frame, frame_hash, available)

    def _exploration_strategy(
        self, frame_hash: str, available: list[int],
    ) -> tuple[int, tuple[int, int] | None]:
        """Generic exploration — try untried actions, then least-visited."""
        usable = [a for a in available if a != 8]
        if not usable:
            return 8, None

        action = self.state_graph.get_least_visited_action(frame_hash, usable)

        coords = None
        if action == 6:
            # Use global step for systematic grid coverage that doesn't reset
            grid_step = 4
            total_grid = (64 // grid_step) ** 2
            grid_idx = self._global_step % total_grid
            gx = (grid_idx % (64 // grid_step)) * grid_step + np.random.randint(0, grid_step)
            gy = (grid_idx // (64 // grid_step)) * grid_step + np.random.randint(0, grid_step)
            coords = (int(min(63, gx)), int(min(63, gy)))

        return action, coords
