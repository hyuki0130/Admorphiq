"""Unit tests for the G3 Push-BFS-on-Inferred-Grid generic strategy.

G3 (`strat_push_bfs_grid`) covers sokoban-style movement-and-collision
games. Replaces the routing role of ka59_sokoban and wa30_analytical
without internal sprite-tag access.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from admorphiq.agent_ensemble import strat_push_bfs_grid


class _SokobanLikeEnv:
    """Minimal sokoban env. Player (color 5) moves on a grid; walking
    onto the goal (color 7) clears the level. No items/pushes — that
    keeps the BFS state space small enough for fast unit testing.

    `_dirs` maps action ids to (dy, dx). Each move is one cell on a
    5-pixel pitch (matches the LS20-shape grid that round-3 G3
    candidates were tuned around).
    """

    PITCH = 5

    def __init__(self, levels: list[dict]) -> None:
        # levels: list of dicts {start: (gx, gy), goal: (gx, gy), w, h}
        self._levels = levels
        self._level = 0
        self._gx = 0
        self._gy = 0
        self.reset()

    def reset(self) -> Any:
        # Match arcengine semantics: reset replays the *current* level
        # from its start, but does not roll back cumulative progress.
        if self._level >= len(self._levels):
            return self._obs()
        cur = self._levels[self._level]
        self._gx, self._gy = cur["start"]
        return self._obs()

    def _render(self) -> np.ndarray:
        f = np.zeros((64, 64), dtype=np.int32)
        if self._level >= len(self._levels):
            return f
        cur = self._levels[self._level]
        gx_goal, gy_goal = cur["goal"]
        # Goal as 3x3 of color 7
        gx, gy = gx_goal * self.PITCH + 5, gy_goal * self.PITCH + 5
        f[max(0, gy - 1):gy + 2, max(0, gx - 1):gx + 2] = 7
        # Player as 3x3 of color 5
        px, py = self._gx * self.PITCH + 5, self._gy * self.PITCH + 5
        f[max(0, py - 1):py + 2, max(0, px - 1):px + 2] = 5
        return f

    def _obs(self) -> Any:
        class _Obs:
            pass

        o = _Obs()
        o.frame = [self._render().tolist()]

        class _S:
            pass

        s = _S()
        s.name = "WIN" if self._level >= len(self._levels) else "PLAYING"
        o.state = s
        o.levels_completed = self._level
        o.available_actions = [1, 2, 3, 4]
        return o

    def step(self, action, data: dict | None = None) -> Any:
        aid = getattr(action, "value", None)
        if aid is None:
            aid = int(action)
        if aid == 0:
            self.reset()
            return self._obs()
        if self._level >= len(self._levels):
            return self._obs()
        cur = self._levels[self._level]
        w, h = cur["w"], cur["h"]
        if aid == 1 and self._gy > 0:
            self._gy -= 1
        elif aid == 2 and self._gy < h - 1:
            self._gy += 1
        elif aid == 3 and self._gx > 0:
            self._gx -= 1
        elif aid == 4 and self._gx < w - 1:
            self._gx += 1
        if (self._gx, self._gy) == cur["goal"]:
            self._level += 1
            if self._level < len(self._levels):
                nxt = self._levels[self._level]
                self._gx, self._gy = nxt["start"]
        return self._obs()


def test_g3_clears_a_one_step_grid_level():
    """Purpose: G3's player-detection probe finds the moving cluster
    after one direction press, then BFS reaches the goal in ≤ depth.
    Trivial 2-cell level — pure smoke test on the detect+BFS pipeline.

    Expected feedback: failure means either player detection picked
    the wrong color or BFS replay-from-reset is broken.
    """
    levels = [{"start": (1, 1), "goal": (2, 1), "w": 4, "h": 4}]
    env = _SokobanLikeEnv(levels)
    best, label, used = strat_push_bfs_grid(env, budget=4000)
    assert best == 1, f"expected level 1, got best={best} used={used}"
    assert label == "push_bfs_grid"


def test_g3_chains_across_two_levels():
    """Purpose: after L1 clears the level state advances; G3 must keep
    going on L2 with a fresh BFS, not bail because the prior plan no
    longer applies.

    Expected feedback: failure means the per-level loop terminates on
    first success instead of attempting the next level.
    """
    levels = [
        {"start": (1, 1), "goal": (2, 1), "w": 4, "h": 4},
        {"start": (0, 0), "goal": (1, 1), "w": 3, "h": 3},
    ]
    env = _SokobanLikeEnv(levels)
    best, label, used = strat_push_bfs_grid(env, budget=8000)
    assert best == 2, f"expected level 2, got best={best} used={used}"


def test_g3_returns_zero_with_only_one_dir():
    """Purpose: G3 needs at least 2 movement directions for a useful
    BFS (otherwise it's a 1-D walk). Envs that expose only A1 (or
    just A6) must early-exit.

    Expected feedback: failure means G3 wastes budget on
    insufficiently-actuated envs.
    """

    class _OneDir:
        def step(self, action, data=None):
            class _O:
                pass

            o = _O()
            o.frame = [np.zeros((64, 64), dtype=np.int32).tolist()]

            class _S:
                pass

            s = _S()
            s.name = "PLAYING"
            o.state = s
            o.levels_completed = 0
            o.available_actions = [1]  # only one dir
            return o

    env = _OneDir()
    best, label, used = strat_push_bfs_grid(env, budget=2000)
    assert best == 0
    assert label == ""
    assert used <= 2
