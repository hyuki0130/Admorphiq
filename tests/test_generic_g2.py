"""Unit tests for the G2 Sprite-Cluster-Interaction generic strategy.

G2 (`strat_sprite_cluster_interaction`) covers click-driven games
where progress comes from manipulating colored blobs (merge / vacuum
/ select-then-act). Replaces the routing role of su15_frame_only and
su15_vacuum without internal sprite-tag access.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from admorphiq.agent_ensemble import strat_sprite_cluster_interaction


def _paint(frame: np.ndarray, cx: int, cy: int, color: int, r: int = 2) -> None:
    frame[max(0, cy - r):cy + r + 1, max(0, cx - r):cx + r + 1] = color


class _ClusterEnv:
    """Minimal click env where clicking the midpoint of two same-color
    clusters merges them (size ↑, count ↓). When all same-color pairs
    are merged, the level clears.
    """

    def __init__(self, levels: list[list[tuple[int, int, int]]]) -> None:
        # Each level: list of (cx, cy, color) cluster centers.
        self._levels = levels
        self._level = 0
        self._clusters: list[tuple[int, int, int]] = []
        self.reset()

    def reset(self) -> Any:
        self._level = 0
        self._clusters = list(self._levels[0])
        return self._obs()

    def _render(self) -> np.ndarray:
        f = np.zeros((64, 64), dtype=np.int32)
        for cx, cy, color in self._clusters:
            _paint(f, cx, cy, color)
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
        o.available_actions = [6]
        return o

    def step(self, action, data: dict | None = None) -> Any:
        aid = getattr(action, "value", None)
        if aid is None:
            aid = int(action)
        if aid == 0:
            self.reset()
            return self._obs()
        if aid == 6 and data is not None and self._level < len(self._levels):
            cx, cy = int(data["x"]), int(data["y"])
            # Find any same-color pair whose midpoint is within 4 pixels
            # of the click. If found, merge them into one cluster at the
            # midpoint. If no clusters left of any duplicate color, level
            # clears.
            for i in range(len(self._clusters)):
                for j in range(i + 1, len(self._clusters)):
                    a = self._clusters[i]
                    b = self._clusters[j]
                    if a[2] != b[2]:
                        continue
                    mx, my = (a[0] + b[0]) // 2, (a[1] + b[1]) // 2
                    if abs(mx - cx) <= 4 and abs(my - cy) <= 4:
                        merged = (mx, my, a[2])
                        new_list = [
                            c for k, c in enumerate(self._clusters)
                            if k != i and k != j
                        ]
                        new_list.append(merged)
                        self._clusters = new_list
                        # Check level-clear: any duplicate-color pair left?
                        cols = [c[2] for c in self._clusters]
                        if len(cols) == len(set(cols)):
                            self._level += 1
                            if self._level < len(self._levels):
                                self._clusters = list(self._levels[self._level])
                        return self._obs()
        return self._obs()


def test_g2_merges_a_single_pair_to_clear_level():
    """Purpose: G2 must find that clicking the midpoint of two same-
    color clusters merges them and clears the level. This is the core
    mechanic of su15_frame_only / paint_game launch phase, framed as
    pure cluster manipulation.

    Expected feedback: failure means the cluster flood-fill or the
    same-color-pair midpoint click loop is broken.
    """
    levels = [[(20, 20, 4), (40, 40, 4)]]
    env = _ClusterEnv(levels)
    best, label, used = strat_sprite_cluster_interaction(env, budget=1000)
    assert best == 1, f"expected level 1, got best={best} used={used}"
    assert label == "sprite_cluster_interaction"


def test_g2_handles_multi_pair_level():
    """Purpose: when a level has multiple same-color pairs, G2 must
    iterate (re-flood after each merge, find the next pair, click
    again) until all pairs are resolved.

    Expected feedback: failure means the inner per-level loop bails
    after the first merge instead of continuing to the next pair.
    """
    levels = [[
        (16, 16, 4), (48, 16, 4),  # pair color 4
        (16, 48, 5), (48, 48, 5),  # pair color 5
    ]]
    env = _ClusterEnv(levels)
    best, label, used = strat_sprite_cluster_interaction(env, budget=2000)
    assert best == 1, f"expected level 1, got best={best} used={used}"


def test_g2_returns_zero_when_no_action6():
    """Purpose: G2 needs ACTION6. Movement-only envs must early-exit
    with no progress and trivial budget consumption.

    Expected feedback: failure means G2 wastes budget on movement
    games it cannot interact with.
    """

    class _NoClick:
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
            o.available_actions = [1, 2, 3, 4]
            return o

    env = _NoClick()
    best, label, used = strat_sprite_cluster_interaction(env, budget=2000)
    assert best == 0
    assert label == ""
    assert used <= 2
