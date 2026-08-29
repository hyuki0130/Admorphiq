"""Shared contract + generic frame utilities for the harness tools.

A Tool is the unit the runtime model orchestrates. It is instantiated once per
game, sees ONLY the FrameData API (never game internals / sprite tags / ids),
and exposes a uniform lifecycle so the harness can run any tool the same way:

    detect(frames, obs) -> float   frame-only confidence this tool fits (0..1)
    reset()                        clear per-level state (called on level-up)
    observe(prev, action, changed) learn from the transition just taken
    propose(frames, obs) -> Steps  the next 1..N actions toward progress

Everything a tool needs to read the observation or analyse a frame lives here,
authored clean and game-agnostic, so tool modules never import the legacy
agents. The only reused pieces are the FrameData API readers (``_frame_2d`` etc.)
which are adapter-level, not game-specific.
"""

from __future__ import annotations

import hashlib
from collections import deque
from typing import Any, Protocol, runtime_checkable

import numpy as np

# API-level observation readers (game-agnostic; documented adapter contract).
from admorphiq.graph_frontier_agent import (
    _availability,
    _frame_2d,
    _has_frame,
    _levels_completed,
    _state_name,
)

__all__ = [
    "Tool",
    "Step",
    "frame_2d",
    "has_frame",
    "state_name",
    "levels_completed",
    "availability",
    "base_hash",
    "diff_cells",
    "diff_bbox",
    "color_histogram",
    "connected_components",
    "changed_mask",
]

# A queued action: (action_id 1-7, optional (x, y) for ACTION6 click).
Step = tuple[int, tuple[int, int] | None]


@runtime_checkable
class Tool(Protocol):
    """Uniform lifecycle for a harness tool (see module docstring)."""

    name: str

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Frame-only confidence in [0, 1] that this tool fits the game."""

    def reset(self) -> None:
        """Drop per-level state (harness calls this on a level transition)."""

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Record the effect of the action just taken (stateful tools learn here)."""

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        """Return the next 1..N actions to take toward progress."""


# --- observation readers (re-exported adapter API, game-agnostic) ------------

def frame_2d(obs: Any) -> np.ndarray:
    """The (64, 64) int grid of the observation's SETTLED layer.

    ⛔ An observation is not one grid. When an action has a scripted consequence the engine returns
    several layers, OLDEST FIRST, so the first layer is the state emitted BEFORE the consequence —
    never the board the next turn is played against. Measured 2026-08-29 across 21 games: the last
    layer is closer than layer 0 to the board handed back next at **100% of level transitions in
    every game**, and at 1591 of 1927 multi-layer frames away from transitions.

    Order is what that measurement proves. Whether the last layer is the board a tool WANTS is a
    separate question — on an animation-heavy board it may be caught mid-consequence — and it is
    settled only by the full-25 gate, which is why this line is a one-line change.
    """
    return _frame_2d_settled(obs)


def _frame_2d_settled(obs: Any) -> np.ndarray:
    fr = getattr(obs, "frame", None)
    arr = np.asarray(fr)
    if arr.ndim >= 3:
        arr = arr[-1]
    return arr.astype(np.int64)


def has_frame(obs: Any) -> bool:
    return _has_frame(obs)


def state_name(obs: Any) -> str:
    return _state_name(obs)


def levels_completed(obs: Any) -> int:
    return _levels_completed(obs)


def availability(obs: Any) -> tuple[list[int], bool]:
    """(simple action ids 1-5/7, action6_available) — see adapter contract."""
    return _availability(obs)


# --- generic frame analysis (authored clean; no game specifics) --------------

def base_hash(frame: np.ndarray) -> str:
    """Stable 12-hex digest of a grid's visible content (aliasing key)."""
    return hashlib.md5(np.ascontiguousarray(frame).tobytes()).hexdigest()[:12]


def changed_mask(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Boolean mask of cells that differ between two same-shape grids."""
    if a.shape != b.shape:
        return np.zeros((0, 0), dtype=bool)
    return a != b


def diff_cells(a: np.ndarray, b: np.ndarray) -> int:
    """Count of differing cells between two grids (0 if shapes mismatch)."""
    m = changed_mask(a, b)
    return int(m.sum())


def diff_bbox(a: np.ndarray, b: np.ndarray) -> tuple[int, int, int, int] | None:
    """(y0, x0, y1, x1) inclusive bounding box of the changed region, or None."""
    m = changed_mask(a, b)
    if m.size == 0 or not m.any():
        return None
    ys, xs = np.where(m)
    return int(ys.min()), int(xs.min()), int(ys.max()), int(xs.max())


def color_histogram(frame: np.ndarray, ncolors: int = 16) -> np.ndarray:
    """Count of each colour index 0..ncolors-1 in the grid."""
    flat = np.asarray(frame).ravel()
    return np.bincount(flat[(flat >= 0) & (flat < ncolors)], minlength=ncolors)


def connected_components(
    frame: np.ndarray, background: int | None = None
) -> list[dict[str, Any]]:
    """4-connected same-colour regions of the grid.

    Returns one dict per region: ``color``, ``size``, ``centroid`` (y, x),
    ``bbox`` (y0, x0, y1, x1), ``cells`` (list of (y, x)). If ``background`` is
    None the most common colour is treated as background and skipped, so the
    result is the set of foreground objects.
    """
    grid = np.asarray(frame)
    h, w = grid.shape
    if background is None:
        hist = color_histogram(grid)
        background = int(hist.argmax()) if hist.any() else -1
    seen = np.zeros((h, w), dtype=bool)
    out: list[dict[str, Any]] = []
    for y in range(h):
        for x in range(w):
            if seen[y, x]:
                continue
            color = int(grid[y, x])
            seen[y, x] = True
            if color == background:
                continue
            cells = [(y, x)]
            q: deque[tuple[int, int]] = deque([(y, x)])
            while q:
                cy, cx = q.popleft()
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] \
                            and int(grid[ny, nx]) == color:
                        seen[ny, nx] = True
                        cells.append((ny, nx))
                        q.append((ny, nx))
            ys = [c[0] for c in cells]
            xs = [c[1] for c in cells]
            out.append({
                "color": color,
                "size": len(cells),
                "centroid": (float(np.mean(ys)), float(np.mean(xs))),
                "bbox": (min(ys), min(xs), max(ys), max(xs)),
                "cells": cells,
            })
    return out
