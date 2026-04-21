"""Unit tests for the G4 generic BFS-FrameHash strategy.

G4 (`strat_bfs_framehash`) is the universal-fallback solver introduced
in round 5 to absorb the bail-out role of the previous game-named
solvers. It must work on ANY deterministic puzzle reachable from
reset, with no game name / sprite tag / internal attribute access.

Each test carries Purpose + Expected-feedback per the Implementation
Discipline in CLAUDE.md. None are FEEDBACK-GATED — these are durable
contracts on the universal fallback.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from admorphiq.agent_ensemble import strat_bfs_framehash


class _GridEnv:
    """Minimal deterministic grid env. Player at (px, py); A1=up, A2=down,
    A3=left, A4=right; goal at fixed cell. Crossing the goal increments
    `levels_completed`. Frame is rendered as a 64x64 int32 board with the
    player as color 5 and goal as color 7.

    Just enough surface to satisfy what `strat_bfs_framehash` needs from
    an arcengine env: `step(action)` returning an obs with `frame`,
    `available_actions`, `state.name`, `levels_completed`.
    """

    def __init__(self, avail: list[int], goals: list[tuple[int, int]], start: tuple[int, int] = (32, 32)) -> None:
        self._avail = list(avail)
        self._goals = list(goals)  # one per level
        self._start = start
        self._level = 0
        self._steps = 0
        self.reset()

    def reset(self) -> Any:
        self._px, self._py = self._start
        self._level = 0
        self._steps = 0
        return self._obs()

    def _obs(self) -> Any:
        frame = np.zeros((64, 64), dtype=np.int32)
        if self._level < len(self._goals):
            gx, gy = self._goals[self._level]
            frame[gy, gx] = 7
        frame[self._py, self._px] = 5
        # Simulate a HUD on the bottom strip — values change with steps
        # so the auto-mask should learn to exclude them.
        frame[60:, :] = (self._steps & 7)

        class _Obs:
            pass

        o = _Obs()
        o.frame = [frame.tolist()]

        class _S:
            pass

        s = _S()
        if self._level >= len(self._goals):
            s.name = "WIN"
        else:
            s.name = "PLAYING"
        o.state = s
        o.levels_completed = self._level
        o.available_actions = list(self._avail)
        return o

    def step(self, action) -> Any:
        # arcengine GameAction.from_id matches the integer; for tests we
        # accept either an int-like aid or the GameAction enum value via
        # `.value`. RESET is value 0.
        aid = getattr(action, "value", None)
        if aid is None:
            aid = int(getattr(action, "name", "0").lstrip("ACTION") or "0") if hasattr(action, "name") else int(action)
        self._steps += 1
        if aid == 0:
            self.reset()
            return self._obs()
        if aid == 1 and self._py > 0:
            self._py -= 1
        elif aid == 2 and self._py < 63:
            self._py += 1
        elif aid == 3 and self._px > 0:
            self._px -= 1
        elif aid == 4 and self._px < 63:
            self._px += 1
        # Detect goal collision
        if self._level < len(self._goals):
            gx, gy = self._goals[self._level]
            if (self._px, self._py) == (gx, gy):
                self._level += 1
                # Re-spawn at start so the next level can be solved
                self._px, self._py = self._start
        return self._obs()


def test_bfs_framehash_clears_a_simple_one_level_maze():
    """Purpose: G4 must clear a trivial 1-level grid where the goal is
    a few moves from the start. Confirms the BFS + reset-replay loop
    terminates with progress, the action vocabulary discovery picks up
    A1-A4 from `available_actions`, and the HUD auto-mask doesn't
    confuse equivalent states.

    Expected feedback: failure means the universal fallback can't even
    solve the most basic case — likely a regression in the hash mask,
    BFS termination, or action-replay logic.
    """
    env = _GridEnv(avail=[1, 2, 3, 4], goals=[(34, 32)], start=(32, 32))
    best, label, used = strat_bfs_framehash(env, budget=2000)
    assert best == 1, f"expected level 1 cleared, got best={best} label={label} used={used}"
    assert label == "bfs_framehash"
    assert used < 2000


def test_bfs_framehash_chains_prefix_across_two_levels():
    """Purpose: when level 1 is solved, the cumulative prefix must be
    appended so level 2's BFS replays it before exploring. Without
    prefix-chaining the level-2 search would start from the L1-start
    state rather than the L2-start state, and the level would be
    unsolvable.

    Expected feedback: failure means the prefix-chain logic broke —
    the strategy clears L1 but not L2.
    """
    env = _GridEnv(
        avail=[1, 2, 3, 4],
        goals=[(34, 32), (32, 30)],
        start=(32, 32),
    )
    best, label, used = strat_bfs_framehash(env, budget=10000)
    assert best == 2, f"expected level 2, got best={best} used={used}"
    assert label == "bfs_framehash"


def test_bfs_framehash_returns_zero_when_no_actions_help():
    """Purpose: when no available actions can reach a goal in the
    allowed depth, G4 must return cleanly with no progress — never
    crash, never infinite-loop, never claim a label.

    Expected feedback: failure means the BFS termination logic is
    broken (no max-depth / no max-nodes guards).
    """
    # No goals at all -> already in WIN state from reset; best stays at
    # the initial levels_completed (0). Strategy should bail early.
    env = _GridEnv(avail=[1, 2, 3, 4], goals=[], start=(32, 32))
    best, label, used = strat_bfs_framehash(env, budget=500)
    assert best == 0
    assert used < 500


def test_bfs_framehash_no_op_when_only_unsupported_actions():
    """Purpose: if the env exposes no movement (no A1-A4) and no A6,
    G4 returns immediately without consuming budget. This covers the
    "this strategy doesn't fit" path so the dispatch loop can advance.

    Expected feedback: failure means G4 wastes budget on envs it can't
    progress on, starving downstream fallbacks.
    """
    env = _GridEnv(avail=[5, 7], goals=[(34, 32)], start=(32, 32))
    best, label, used = strat_bfs_framehash(env, budget=2000)
    assert best == 0
    assert label == ""
    assert used <= 2  # one reset; nothing else
