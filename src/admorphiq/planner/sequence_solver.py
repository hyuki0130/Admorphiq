"""Brute-force sequence solver for games solvable by short action sequences.

Tries all possible action sequences up to a given length, using RESET between
attempts to find the winning combination.
"""

from __future__ import annotations

import time
from itertools import product

import numpy as np


class SequenceSolver:
    """Solver that brute-forces short action sequences."""

    def __init__(self, max_length: int = 8, max_combos: int = 50000, time_limit: float = 30.0) -> None:
        self.max_length = max_length
        self.max_combos = max_combos
        self.time_limit = time_limit
        self.winning_sequence: list[tuple[str, int, int]] | None = None

    def discover_actions(
        self,
        env,
        reset_action,
        click_fn,
        get_frame_fn,
        available_actions: list[int],
    ) -> list[tuple[str, int, int]]:
        """Discover distinct actions including click regions.

        Returns list of (type, arg1, arg2) tuples:
          ('action', action_id, 0) for simple actions
          ('click', x, y) for distinct click regions
        """
        actions: list[tuple[str, int, int]] = []

        # Simple actions (excluding ACTION6)
        for a in available_actions:
            if a != 6:
                actions.append(("action", a, 0))

        # Discover distinct click regions (scan at 4px resolution)
        if 6 in available_actions:
            scan_start = time.time()
            seen_effects: set[frozenset[tuple[int, int]]] = set()
            for cy in range(0, 64, 4):
                for cx in range(0, 64, 4):
                    if time.time() - scan_start > 10.0:
                        break
                if time.time() - scan_start > 10.0:
                    break
                for cx in range(0, 64, 4):
                    obs_ref = env.step(reset_action)
                    fb = get_frame_fn(obs_ref)
                    obs_click = click_fn(env, cx, cy)
                    fa = get_frame_fn(obs_click)

                    diff = fb != fa
                    if not diff.any():
                        continue

                    dys, dxs = np.where(diff)
                    # Filter timer pixels
                    real = frozenset(
                        (int(dxs[j]), int(dys[j]))
                        for j in range(len(dys))
                        if not (dys[j] <= 4 and dxs[j] > 40)
                    )

                    if real and real not in seen_effects:
                        seen_effects.add(real)
                        actions.append(("click", cx, cy))
                        if len(actions) >= 10:
                            break
                if len(actions) >= 10:
                    break

        return actions

    def brute_force_solve(
        self,
        env,
        reset_action,
        click_fn,
        get_levels_fn,
        actions: list[tuple[str, int, int]],
    ) -> list[tuple[str, int, int]] | None:
        """Try all action sequences up to max_length.

        Returns winning sequence or None.
        """
        n = len(actions)
        if n == 0:
            return None

        # Compute max feasible length
        max_len = self.max_length
        total = 0
        for length in range(1, max_len + 1):
            combos = n ** length
            if total + combos > self.max_combos:
                max_len = length - 1
                break
            total += combos

        if max_len < 1:
            return None

        # Get base level count
        obs = env.step(reset_action)
        base_levels = get_levels_fn(obs)
        start_time = time.time()

        for length in range(1, max_len + 1):
            for seq in product(range(n), repeat=length):
                if time.time() - start_time > self.time_limit:
                    return None

                obs = env.step(reset_action)
                if obs is None:
                    continue

                for idx in seq:
                    act_type, a, b = actions[idx]
                    if act_type == "click":
                        obs = click_fn(env, a, b)
                    else:
                        from arcengine import GameAction
                        obs = env.step(GameAction.from_id(a))
                    if obs is None:
                        break

                if obs is not None and get_levels_fn(obs) > base_levels:
                    self.winning_sequence = [actions[i] for i in seq]
                    return self.winning_sequence

        return None

    def apply_sequence(
        self,
        env,
        click_fn,
        sequence: list[tuple[str, int, int]] | None = None,
    ):
        """Apply a sequence (default: winning sequence).

        Returns obs after all actions.
        """
        if sequence is None:
            sequence = self.winning_sequence
        if sequence is None:
            return None

        from arcengine import GameAction

        obs = None
        for act_type, a, b in sequence:
            if act_type == "click":
                obs = click_fn(env, a, b)
            else:
                obs = env.step(GameAction.from_id(a))
        return obs
