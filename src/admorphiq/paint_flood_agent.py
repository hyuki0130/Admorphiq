"""PaintFloodAgent — runnable agent for click-fills-a-region (paint) games.

Wires the generic paint_flood tool (`admorphiq.tools.paint_flood`) into the
harness contract (is_done / choose_action). LLM-free (pure perception + planning),
so it benches offline with scripts/score_efficiency.py. Game-agnostic: detects
the flood mechanic from its OWN probes and clicks fill-completing points; no game
ids.

Loop: probe clicks to learn the fill mechanic (+ fill color) -> once detected,
click the largest still-background regions (propose_fill_clicks) to complete the
coloring; interleave ACTION7 (commit/advance on paint titles like su15 whose only
actions are [6,7]). Resets accumulation on level-up.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from admorphiq.graph_frontier_agent import (
    _availability,
    _frame_2d,
    _has_frame,
    _levels_completed,
    _state_name,
)
from admorphiq.tools.paint_flood import detect_flood_mechanic, propose_fill_clicks

_DETECT_EVERY = 12   # re-run detection until the mechanic is found
_MIN_PROBES = 6      # click probes before first detection attempt


class PaintFloodAgent:
    """Harness-contract agent driving the paint_flood tool."""

    def __init__(self, giveup: int = 8000) -> None:
        from admorphiq.adapter import AdmorphiqAdapter
        self._convert = AdmorphiqAdapter._convert_action
        self.giveup = giveup
        self._reset_level()

    def _reset_level(self) -> None:
        self._frames: list[np.ndarray] = []
        self._acts: list[int] = []
        self._nexts: list[np.ndarray] = []
        self._prev_frame: np.ndarray | None = None
        self._prev_action_idx: int | None = None
        self._fill_color: int = -1
        self._fill_queue: list[tuple[int, int]] = []
        self._probe_i = 0
        self._steps = 0
        self._last_levels = 0

    # ----- harness contract ---------------------------------------------------

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        if _state_name(latest_frame) == "WIN":
            return True
        return self._steps >= self.giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        from admorphiq.types import ActionType, GameAction
        obs = latest_frame
        state = _state_name(obs)

        levels = _levels_completed(obs)
        if levels > self._last_levels:
            self._reset_level()
            self._last_levels = levels

        if state in ("GAME_OVER", "NOT_PLAYED"):
            self._prev_frame = None
            self._prev_action_idx = None
            return self._convert(GameAction.reset())
        if not _has_frame(obs):
            return self._convert(GameAction.reset())

        frame = _frame_2d(obs).astype(np.int16)
        # record the transition our previous action produced
        if self._prev_frame is not None and self._prev_action_idx is not None \
                and self._prev_frame.shape == frame.shape:
            self._frames.append(self._prev_frame)
            self._acts.append(self._prev_action_idx)
            self._nexts.append(frame.copy())

        simple_ids, action6_ok = _availability(obs)
        self._steps += 1

        # (Re)detect the flood mechanic from accumulated probes.
        if self._fill_color < 0 and len(self._acts) >= _MIN_PROBES \
                and len(self._acts) % _DETECT_EVERY == 0:
            m = detect_flood_mechanic(
                np.array(self._frames), np.array(self._acts), np.array(self._nexts)
            )
            if m.detected:
                self._fill_color = m.fill_color

        action_idx, key = self._pick(frame, simple_ids, action6_ok)
        self._prev_frame = frame
        self._prev_action_idx = action_idx
        if key[0] == "click":
            internal = GameAction.coordinate(int(key[1]), int(key[2]))
        else:
            internal = GameAction.simple(ActionType(int(key[1])))
        return self._convert(internal)

    # ----- policy -------------------------------------------------------------

    def _pick(
        self, frame: np.ndarray, simple_ids: list[int], action6_ok: bool
    ) -> tuple[int, tuple]:
        """Return (combined_action_idx, key) where key is ("click",x,y) or ("simple",id)."""
        from admorphiq.ewm.core import COORD_OFFSET, GRID

        # Fill phase: mechanic known -> click the fill-completing points.
        if self._fill_color >= 0 and action6_ok:
            if not self._fill_queue:
                self._fill_queue = propose_fill_clicks(frame, self._fill_color)
            if self._fill_queue:
                x, y = self._fill_queue.pop(0)
                return COORD_OFFSET + y * GRID + x, ("click", x, y)

        # Probe phase: click BACKGROUND-REGION centroids (where a flood actually
        # triggers) rather than a blind grid — the diagnostic showed blind stride
        # probes never elicit the mechanic. Fall back to a stride grid only if no
        # background regions exist. Interleave a simple action to commit/advance.
        if action6_ok:
            if not self._fill_queue:
                self._fill_queue = propose_fill_clicks(frame, fill_color=-1)
                if not self._fill_queue:
                    self._fill_queue = [
                        (x, y) for y in range(4, GRID, 12) for x in range(4, GRID, 12)
                    ]
            self._probe_i += 1
            if self._probe_i % 4 == 0 and simple_ids:
                sid = simple_ids[0]
                return sid - 1, ("simple", sid)
            x, y = self._fill_queue.pop(0)
            return COORD_OFFSET + y * GRID + x, ("click", x, y)

        if simple_ids:
            sid = simple_ids[0]
            return sid - 1, ("simple", sid)
        return 6, ("simple", 7)  # ACTION7 fallback when only [7] remains
