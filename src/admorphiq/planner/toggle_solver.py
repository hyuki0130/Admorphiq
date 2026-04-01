"""Toggle puzzle solver for click-only games like TN36.

Detects toggle groups (sets of pixels that flip together when clicked),
then brute-forces all 2^N combinations using RESET to find the winning one.
"""

from __future__ import annotations

import numpy as np
from itertools import product


class ToggleSolver:
    """Solver for toggle/lights-out style puzzles."""

    def __init__(self, max_groups: int = 15) -> None:
        self.max_groups = max_groups
        # Discovered toggle groups: list of (click_x, click_y)
        self.groups: list[tuple[int, int]] = []
        # Winning combo if found: tuple of 0/1
        self.winning_combo: tuple[int, ...] | None = None
        # Whether discovery phase is done
        self.discovered = False

    def discover_groups(
        self,
        env,
        reset_action,
        click_fn,
        get_frame_fn,
    ) -> int:
        """Discover toggle groups by clicking each position and checking for non-timer changes.

        Uses RESET between each probe so state is preserved.

        Args:
            env: Game environment
            reset_action: Action object for RESET
            click_fn: Function(env, x, y) -> obs that clicks at (x, y)
            get_frame_fn: Function(obs) -> np.ndarray (2D frame)

        Returns:
            Number of toggle groups found.
        """
        groups: dict[frozenset[tuple[int, int]], tuple[int, int]] = {}

        # Get reference frame
        obs_ref = env.step(reset_action)
        frame_ref = get_frame_fn(obs_ref)

        # Scan at 2px resolution
        for cy in range(0, 64, 2):
            for cx in range(0, 64, 2):
                obs_ref = env.step(reset_action)
                fb = get_frame_fn(obs_ref)

                obs_click = click_fn(env, cx, cy)
                fa = get_frame_fn(obs_click)

                diff_mask = fb != fa
                if not diff_mask.any():
                    continue

                dys, dxs = np.where(diff_mask)
                # Filter timer pixels: top 4 rows with x > 45
                real = frozenset(
                    (int(dxs[j]), int(dys[j]))
                    for j in range(len(dys))
                    if not (dys[j] <= 4 and dxs[j] > 40)
                )

                if real and real not in groups:
                    groups[real] = (cx, cy)

                if len(groups) >= self.max_groups:
                    break
            if len(groups) >= self.max_groups:
                break

        self.groups = list(groups.values())
        self.discovered = True
        return len(self.groups)

    def brute_force_solve(
        self,
        env,
        reset_action,
        click_fn,
        get_levels_fn,
    ) -> tuple[int, ...] | None:
        """Try all 2^N combinations to find the winning one.

        Args:
            env: Game environment
            reset_action: Action object for RESET
            click_fn: Function(env, x, y) -> obs
            get_levels_fn: Function(obs) -> int (levels_completed)

        Returns:
            Winning combo tuple, or None if not found.
        """
        if not self.groups:
            return None

        n = len(self.groups)
        if n > self.max_groups:
            return None

        # Get current level count from reset state
        obs = env.step(reset_action)
        base_levels = get_levels_fn(obs)

        for combo in product([0, 1], repeat=n):
            if sum(combo) == 0:
                continue

            obs = env.step(reset_action)

            for i, toggle in enumerate(combo):
                if toggle:
                    cx, cy = self.groups[i]
                    obs = click_fn(env, cx, cy)

            if get_levels_fn(obs) > base_levels:
                self.winning_combo = combo
                return combo

        return None

    def apply_combo(
        self,
        env,
        click_fn,
        combo: tuple[int, ...] | None = None,
    ):
        """Apply a combo (default: winning combo) without RESET.

        Returns the obs after all clicks.
        """
        if combo is None:
            combo = self.winning_combo
        if combo is None:
            return None

        obs = None
        for i, toggle in enumerate(combo):
            if toggle:
                cx, cy = self.groups[i]
                obs = click_fn(env, cx, cy)
        return obs
