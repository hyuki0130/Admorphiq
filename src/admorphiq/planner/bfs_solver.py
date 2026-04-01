"""BFS game-state solver for deterministic games with small state spaces.

Uses the actual game environment as the transition function, hashing rendered
frames to detect unique states. Finds shortest action sequences to complete
levels by breadth-first search.

Effective for: maze navigation (TU93), movement puzzles with limited budgets.
"""

from __future__ import annotations

import hashlib
import time
from collections import deque

import numpy as np
from arcengine import GameAction


class BFSSolver:
    """Solver that does BFS over actual game states to find winning paths."""

    def __init__(
        self,
        max_depth: int = 60,
        max_states: int = 50000,
        time_limit: float = 60.0,
    ) -> None:
        self.max_depth = max_depth
        self.max_states = max_states
        self.time_limit = time_limit
        self.winning_actions: list = []  # cumulative actions across all levels

    @staticmethod
    def _frame_hash(obs) -> str:
        f = np.array(obs.frame)
        if f.ndim == 3:
            f = f[0]
        if f.ndim < 2:
            return hashlib.md5(f.tobytes()).hexdigest()
        # Mask out timer area (top rows, right side)
        f_copy = f.copy()
        f_copy[:5, 40:] = 0
        return hashlib.md5(f_copy.tobytes()).hexdigest()

    def _replay_prefix(self, env, reset_action, prefix):
        """Replay a prefix of actions from reset. Returns obs or None."""
        obs = env.step(reset_action)
        if obs is None:
            return None
        for action in prefix:
            obs = self._do_action(env, action)
            if obs is None:
                return None
        return obs

    def solve(
        self,
        env,
        reset_action,
        simple_actions: list[int],
        get_levels_fn,
        click_coords: list[tuple[int, int]] | None = None,
        prefix: list | None = None,
        expected_base_levels: int | None = None,
    ) -> list | None:
        """BFS over game states to find shortest winning action sequence.

        Args:
            env: Game environment
            reset_action: GameAction.RESET
            simple_actions: List of simple action IDs to try (e.g. [1,2,3,4])
            get_levels_fn: Function obs -> levels_completed
            click_coords: Optional list of (x,y) click positions to include
            prefix: Actions to replay before starting BFS (for multi-level)
            expected_base_levels: Override base_levels (for mid-transition states)

        Returns:
            List of NEW actions (not including prefix) or None
        """
        start_time = time.time()
        if prefix is None:
            prefix = []

        # Get initial state (after replaying prefix)
        obs = self._replay_prefix(env, reset_action, prefix)
        if obs is None:
            return None
        base_levels = expected_base_levels if expected_base_levels is not None else get_levels_fn(obs)
        init_hash = self._frame_hash(obs)

        # Build action list
        all_actions: list = list(simple_actions)
        if click_coords:
            all_actions.extend(click_coords)

        # BFS: queue of (state_hash, new_action_path)
        visited: set[str] = {init_hash}
        queue: deque[tuple[str, list]] = deque()
        queue.append((init_hash, []))

        states_explored = 0

        while queue:
            if time.time() - start_time > self.time_limit:
                break
            if states_explored >= self.max_states:
                break

            current_hash, path = queue.popleft()

            if len(path) >= self.max_depth:
                continue

            for action in all_actions:
                # Replay prefix + path from reset
                obs = self._replay_prefix(env, reset_action, prefix)
                if obs is None:
                    continue

                # Replay BFS path
                replay_ok = True
                for prev_action in path:
                    obs = self._do_action(env, prev_action)
                    if obs is None:
                        replay_ok = False
                        break
                if not replay_ok:
                    continue

                # Take the new action
                obs = self._do_action(env, action)
                if obs is None:
                    continue

                states_explored += 1

                # Check for level completion
                if get_levels_fn(obs) > base_levels:
                    return path + [action]

                # Check if game is over
                if hasattr(obs, 'state') and obs.state.name == 'GAME_OVER':
                    continue

                new_hash = self._frame_hash(obs)
                if new_hash not in visited:
                    visited.add(new_hash)
                    queue.append((new_hash, path + [action]))

        return None

    def solve_all_levels(
        self,
        env,
        reset_action,
        simple_actions: list[int],
        get_levels_fn,
        click_coords: list[tuple[int, int]] | None = None,
        total_time_limit: float = 300.0,
    ) -> tuple[int, list]:
        """Solve as many levels as possible by chaining BFS solutions.

        Returns (levels_completed, cumulative_action_list).
        """
        start_time = time.time()
        cumulative_actions: list = []

        # Get initial level count
        obs = env.step(reset_action)
        if obs is None:
            return 0, []
        base_levels = get_levels_fn(obs)

        level = 0
        while True:
            elapsed = time.time() - start_time
            remaining = total_time_limit - elapsed
            if remaining < 5.0:
                break

            # Shrink per-level time as prefix gets longer
            per_level_limit = min(self.time_limit, remaining)

            solver_copy = BFSSolver(
                max_depth=self.max_depth,
                max_states=self.max_states,
                time_limit=per_level_limit,
            )

            result = solver_copy.solve(
                env, reset_action, simple_actions, get_levels_fn,
                click_coords=click_coords,
                prefix=cumulative_actions,
                expected_base_levels=base_levels + level,
            )

            if result is None:
                break

            cumulative_actions.extend(result)
            level += 1

            # Verify by replaying
            obs = self._replay_prefix(env, reset_action, cumulative_actions)
            if obs is None:
                break
            current_levels = get_levels_fn(obs)
            print(f"  BFS solver: level {level} solved! steps={len(result)}, total_steps={len(cumulative_actions)}, levels={current_levels}")

            if hasattr(obs, 'state') and obs.state.name == 'WIN':
                break
            if hasattr(obs, 'win_levels') and current_levels >= obs.win_levels:
                break

        # Final state — replay to get accurate level count
        # Do double replay to handle transition lag in levels_completed
        self._replay_prefix(env, reset_action, cumulative_actions)
        obs = self._replay_prefix(env, reset_action, cumulative_actions)
        final_levels = get_levels_fn(obs) if obs else base_levels
        self.winning_actions = cumulative_actions
        return final_levels, cumulative_actions

    @staticmethod
    def _do_action(env, action):
        """Execute a single action (simple int or click tuple)."""
        if isinstance(action, tuple):
            x, y = action
            ga = GameAction.from_id(6)
            ga.set_data({"x": x, "y": y})
            return env.step(ga, data={"x": x, "y": y})
        else:
            return env.step(GameAction.from_id(action))

    def apply_solution(
        self,
        env,
        actions: list | None = None,
    ):
        """Apply winning action sequence. Returns final obs."""
        if actions is None:
            actions = self.winning_actions
        if actions is None:
            return None

        obs = None
        for action in actions:
            obs = self._do_action(env, action)
            if obs is None:
                break
        return obs
