"""Unit tests for the G1 Interactive-Grid-Toggle generic strategy.

G1 (`strat_interactive_grid_toggle`) replaces the routing role of
`paint_game`, `lights_out`, and `tn36_frame_only` by sharing one
probe-classify-search pipeline. These tests pin three game shapes
G1 is designed to handle: a self-toggle grid, a paired-toggle grid,
and a paint-and-execute (palette + executor) grid.

Each test carries Purpose + Expected-feedback per the Implementation
Discipline in CLAUDE.md.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from admorphiq.agent_ensemble import strat_interactive_grid_toggle


class _ClickGridEnv:
    """Minimal click-only env for G1 testing.

    Constructor accepts a list of "level rules". Each level rule is a
    dict with keys:
      cells:   list[(cx, cy, color)] — initial palette of clickable cells
      effect:  callable(state, click) -> new_state — toggles state on click
      goal:    callable(state) -> bool — returns True when the level is cleared
      executor: optional (cx, cy) — a click that triggers level-up check
    """

    def __init__(self, levels: list[dict]) -> None:
        self._levels = levels
        self._level = 0
        self._state: dict = {}
        self.reset()

    def reset(self) -> Any:
        self._level = 0
        self._state = {}
        for c in self._levels[self._level]["cells"]:
            self._state[(c[0], c[1])] = c[2]
        return self._obs()

    def _render(self) -> np.ndarray:
        frame = np.zeros((64, 64), dtype=np.int32)
        if self._level < len(self._levels):
            for k, color in self._state.items():
                # Only render entries keyed by (cx, cy) ints — flags
                # like 'cursor_color', 'solved', 'fired', or compound
                # ('lit', x, y) keys are state metadata, not visuals.
                if isinstance(k, tuple) and len(k) == 2 and all(isinstance(v, int) for v in k):
                    cx, cy = k
                    frame[max(0, cy - 1):cy + 2, max(0, cx - 1):cx + 2] = color
        return frame

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
            rule = self._levels[self._level]
            self._state = rule["effect"](self._state, (cx, cy))
            executor = rule.get("executor")
            cleared = False
            if executor is None:
                cleared = rule["goal"](self._state)
            elif (cx, cy) == executor and rule["goal"](self._state):
                cleared = True
            if cleared:
                self._level += 1
                if self._level < len(self._levels):
                    self._state = {}
                    for c in self._levels[self._level]["cells"]:
                        self._state[(c[0], c[1])] = c[2]
        return self._obs()


def test_g1_clears_a_paint_executor_level():
    """Purpose: G1 must clear a paint-and-execute style level — click a
    palette swatch (small diff: only the swatch tile changes) then click
    an executor cell (large diff: > 30% of frame). This is the abstract
    shape of paint_game/lights_out without any sprite tags.

    Expected feedback: failure means the executor-classification
    threshold (30% of frame) or palette+executor probing path is broken.
    """
    target_color = 4

    # Place cells exactly on the stride-6 grid scan positions so G1's
    # cell-discovery picks them up at the click coords G1 will use.
    PALETTE = (9, 9)
    EXECUTOR = (45, 45)

    def _effect(state, click):
        s = dict(state)
        if click == PALETTE:
            s["cursor_color"] = target_color
            s["palette_selected"] = True  # visual: a "selected" frame
        elif click == EXECUTOR:
            if s.get("cursor_color") == target_color:
                s["solved"] = True
            s["fired"] = True  # global render trigger
        return s

    def _goal(state):
        return state.get("solved", False)

    levels = [{
        "cells": [(PALETTE[0], PALETTE[1], 4), (EXECUTOR[0], EXECUTOR[1], 7)],
        "effect": _effect,
        "goal": _goal,
        "executor": EXECUTOR,
    }]

    env = _ClickGridEnv(levels)
    # Hijack render: palette click must produce a small but non-zero
    # diff so G1 doesn't classify it 'inert'. Executor click must paint
    # a large region so G1 classifies it 'executor' (diff > 30%).
    orig_render = env._render

    def _big_render():
        f = orig_render()
        if env._state.get("palette_selected"):
            f[2:6, 2:6] = 4  # small "selected" indicator
        if env._state.get("fired"):
            f[10:54, 10:54] = 7  # large executor-fire visualization
        return f

    env._render = _big_render
    best, label, used = strat_interactive_grid_toggle(env, budget=4000)
    assert best == 1, f"expected level 1 cleared, got best={best} used={used}"
    assert label == "interactive_grid_toggle"


def test_g1_returns_zero_when_action6_unavailable():
    """Purpose: G1 only fits click-driven puzzles. When the env does not
    expose ACTION6, G1 must return immediately with no progress and
    minimal budget consumption.

    Expected feedback: failure means G1 is wasting budget on movement
    games that don't even support clicks.
    """

    class _NoClickEnv:
        def step(self, action, data=None):
            class _Obs:
                pass

            o = _Obs()
            o.frame = [np.zeros((64, 64), dtype=np.int32).tolist()]

            class _S:
                pass

            s = _S()
            s.name = "PLAYING"
            o.state = s
            o.levels_completed = 0
            o.available_actions = [1, 2, 3, 4]
            return o

    env = _NoClickEnv()
    best, label, used = strat_interactive_grid_toggle(env, budget=2000)
    assert best == 0
    assert label == ""
    assert used <= 2  # one reset, no further work


def test_g1_finds_a_single_toggle_solution():
    """Purpose: when one specific cell click solves the level (the
    simplest non-trivial case), G1 must find it via the singleton
    toggle search (Phase 3a) without falling through to pair / triple
    search.

    Expected feedback: failure means the singleton phase doesn't
    correctly check for level-up after each candidate click. Cells are
    placed on the stride-6 grid (coords ending in 9, 15, 21, ...) so
    G1's grid scan finds them at exact click coords.
    """
    SOLUTION = (21, 21)

    def _effect(state, click):
        s = dict(state)
        # Each click toggles a "lit" flag at that cell; the solving
        # click also flips a global "solved" flag so cross-toggle has
        # observable behavior beyond a single-cell change.
        cell_key = ("lit", click[0], click[1])
        s[cell_key] = not s.get(cell_key, False)
        if click == SOLUTION:
            s["solved"] = True
        return s

    def _goal(state):
        return state.get("solved", False)

    # Place all cells on the stride-6 grid scan positions.
    levels = [{
        "cells": [(9, 9, 3), (21, 21, 4), (33, 33, 5), (45, 45, 6)],
        "effect": _effect,
        "goal": _goal,
    }]
    env = _ClickGridEnv(levels)
    # Make each lit cell render a 5x5 region so its diff is > 10 pixels
    # (the threshold above 'palette' classification).
    orig_render = env._render

    def _bigger_render():
        f = orig_render()
        for (kind, cx, cy), val in env._state.items() if False else []:
            pass
        # also paint lit-flag visualization
        for k, v in list(env._state.items()):
            if isinstance(k, tuple) and len(k) == 3 and k[0] == "lit" and v:
                cx, cy = k[1], k[2]
                f[max(0, cy - 2):cy + 3, max(0, cx - 2):cx + 3] = 9
        return f

    env._render = _bigger_render
    best, label, used = strat_interactive_grid_toggle(env, budget=2000)
    assert best == 1, f"expected level 1 cleared, got best={best} used={used}"
    assert label == "interactive_grid_toggle"
