"""Stateless Python sandbox + inspection API for the code-REPL agent (R55 module 4).

The model writes Python that INSPECTS the scene (free internal computation — does
not consume environment actions) and REQUESTS actions. Each model call runs in a
fresh subprocess: stdlib-only imports (allowlist reused from ``ewm.core``),
bounded output, and a hard subprocess-level timeout+kill so a runaway loop cannot
hang the harness. Requested actions are RECORDED (explicit accounting) and
returned to the parent — the sandbox never touches the env directly; the governor
validates and applies them.

The inspection API operates on an :class:`ObservationStore` (all frames + tracked
scenes), serialized into the subprocess. :class:`Inspector` is also usable
directly (in-process) for fast unit tests; the subprocess path shares the same
class, so there is one implementation.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from admorphiq.repl_agent.segmentation import Scene

_DIGITS = "0123456789abcdef"

# Winner-validated ceiling: the Duck harness allows 30s per REPL toolcall so the
# model can run in-REPL action-sequence search (see the Duck teardown lesson).
# Env-configurable so the Kaggle bench can tune it; the output cap stays at 4000.
_DEFAULT_TIMEOUT = 30.0


def default_timeout() -> float:
    """Resolve the sandbox timeout from ``REPL_SANDBOX_TIMEOUT`` (default 30s)."""
    raw = os.environ.get("REPL_SANDBOX_TIMEOUT", "").strip()
    try:
        return float(raw) if raw else _DEFAULT_TIMEOUT
    except ValueError:
        return _DEFAULT_TIMEOUT


def _scene_payload(scene: Scene | None) -> list[dict[str, Any]]:
    if scene is None:
        return []
    return [
        {
            "id": o.id,
            "color": o.color,
            "cells": [list(c) for c in o.cells],
            "bbox": list(o.bbox),
            "centroid": [round(o.centroid[0], 2), round(o.centroid[1], 2)],
            "area": o.area,
            "shape_hash": o.shape_hash,
            "holes": o.holes,
            "contained_by": o.contained_by,
            "adjacent": o.adjacent,
            "safe_click": list(o.safe_click),
        }
        for o in scene.objects
    ]


class ObservationStore:
    """Holds every frame + tracked scene; serializes into the sandbox subprocess.

    Raw frames stay available to deterministic code here even though they are not
    dumped into the prompt (design doc module 4).
    """

    def __init__(self) -> None:
        self.frames: list[np.ndarray] = []
        self.scenes: list[Scene | None] = []

    def add(self, frame: np.ndarray, scene: Scene | None = None) -> None:
        self.frames.append(np.asarray(frame))
        self.scenes.append(scene)

    def to_payload(self) -> dict[str, Any]:
        return {
            "frames": [f.astype(int).tolist() for f in self.frames],
            "scenes": [_scene_payload(s) for s in self.scenes],
        }


class Inspector:
    """The inspection + action API bound into the sandbox namespace.

    Operates on a serialized :class:`ObservationStore` payload (frames as nested
    int lists, scenes as object-dict lists). Frame/scene indices accept negative
    values (``-1`` = latest). ``action`` records a request for the governor.
    """

    def __init__(self, payload: dict[str, Any]) -> None:
        self.frames: list[np.ndarray] = [np.array(f, dtype=int) for f in payload["frames"]]
        self.scenes: list[list[dict[str, Any]]] = payload["scenes"]
        self.actions: list[dict[str, Any]] = []

    # ----- indexing helpers ---------------------------------------------------
    def _fi(self, t: int) -> int:
        n = len(self.frames)
        idx = t if t >= 0 else n + t
        if not (0 <= idx < n):
            raise IndexError(f"frame index {t} out of range (have {n})")
        return idx

    def _find(self, oid: str, t: int) -> dict[str, Any] | None:
        for o in self.scenes[self._fi(t)]:
            if o["id"] == oid:
                return o
        return None

    # ----- inspection API -----------------------------------------------------
    def objects(self, t: int = -1) -> list[dict[str, Any]]:
        """All tracked object dicts for the scene at frame ``t``."""
        return self.scenes[self._fi(t)]

    def crop(self, region: tuple[int, int, int, int], t: int = -1) -> list[list[int]]:
        """Inclusive (y0, x0, y1, x1) sub-grid of frame ``t`` as nested lists."""
        y0, x0, y1, x1 = region
        return self.frames[self._fi(t)][y0:y1 + 1, x0:x1 + 1].tolist()

    def ascii(self, region: tuple[int, int, int, int] | None = None,
              t: int = -1) -> str:
        """Base-16 ASCII rendering of frame ``t`` (or a region of it)."""
        grid = self.frames[self._fi(t)]
        if region is not None:
            y0, x0, y1, x1 = region
            grid = grid[y0:y1 + 1, x0:x1 + 1]
        return "\n".join(
            "".join(_DIGITS[min(int(v), 15)] for v in row) for row in grid
        )

    def mask(self, oid: str, t: int = -1) -> list[list[int]]:
        """Binary (0/1) mask of the object ``oid`` over the full frame shape."""
        h, w = self.frames[self._fi(t)].shape
        out = [[0] * w for _ in range(h)]
        obj = self._find(oid, t)
        if obj is not None:
            for y, x in obj["cells"]:
                out[y][x] = 1
        return out

    def compare(self, t1: int, t2: int) -> dict[str, Any]:
        """Diff two frames: cells_changed, changed bbox, list of changed cells."""
        a, b = self.frames[self._fi(t1)], self.frames[self._fi(t2)]
        if a.shape != b.shape:
            return {"cells_changed": -1, "bbox": None, "changed": []}
        m = a != b
        ys, xs = np.where(m)
        bbox = ([int(ys.min()), int(xs.min()), int(ys.max()), int(xs.max())]
                if len(ys) else None)
        return {
            "cells_changed": int(m.sum()),
            "bbox": bbox,
            "changed": [[int(y), int(x)] for y, x in zip(ys, xs)],
        }

    def relations(self, oid: str, t: int = -1) -> dict[str, Any]:
        """Containment + adjacency of object ``oid`` at frame ``t``."""
        obj = self._find(oid, t)
        if obj is None:
            return {"contained_by": None, "adjacent": []}
        return {"contained_by": obj["contained_by"], "adjacent": obj["adjacent"]}

    def shortest_path(
        self,
        start: tuple[int, int],
        goals: Any,
        passable_mask: list[list[int]],
    ) -> list[list[int]] | None:
        """Pure 4-connected BFS from ``start`` to the nearest ``goal``.

        The LLM supplies EVERYTHING — the start cell, the goal cell(s), and the
        passability mask (1 = passable). This tool decides NOTHING about the game
        (not the player, not the goal, not the walls); it only computes a path
        over the mask it is given. Returns the path as ``[[r, c], …]`` inclusive
        of start and goal, or ``None`` if unreachable.
        """
        from collections import deque

        grid = [list(map(int, row)) for row in passable_mask]
        if not grid or not grid[0]:
            return None
        h, w = len(grid), len(grid[0])
        goal_list = [tuple(goals)] if (len(goals) == 2 and isinstance(goals[0], int)) \
            else [tuple(g) for g in goals]
        goal_set = {(int(r), int(c)) for r, c in goal_list}
        sr, sc = int(start[0]), int(start[1])
        if not (0 <= sr < h and 0 <= sc < w):
            return None
        prev: dict[tuple[int, int], tuple[int, int] | None] = {(sr, sc): None}
        q: deque[tuple[int, int]] = deque([(sr, sc)])
        while q:
            cur = q.popleft()
            if cur in goal_set:
                path: list[list[int]] = []
                node: tuple[int, int] | None = cur
                while node is not None:
                    path.append([node[0], node[1]])
                    node = prev[node]
                return path[::-1]
            cy, cx = cur
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in prev \
                        and grid[ny][nx]:
                    prev[(ny, nx)] = cur
                    q.append((ny, nx))
        return None

    def action(self, kind: str, row: int | None = None,
               col: int | None = None) -> dict[str, Any]:
        """Record an action request (explicit accounting). MOUSE needs row/col."""
        rec: dict[str, Any] = {"action": kind}
        if kind == "MOUSE":
            rec["row"] = row
            rec["col"] = col
        self.actions.append(rec)
        return rec


@dataclass
class SandboxResult:
    """Outcome of running model code in the sandbox subprocess."""

    stdout: str = ""
    error: str = ""
    timed_out: bool = False
    actions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.error and not self.timed_out


def run_code(
    code: str,
    store: ObservationStore,
    *,
    timeout: float | None = None,
    max_output: int = 4000,
) -> SandboxResult:
    """Run ``code`` in a fresh subprocess with the inspection API bound.

    The subprocess reads a JSON job on stdin and prints a JSON result. A hard
    ``timeout`` kills a runaway process (subprocess-level, robust against
    Python-level infinite loops); when unset it defaults to
    :func:`default_timeout` (30s, ``REPL_SANDBOX_TIMEOUT``-configurable) so the
    model has room for in-REPL search. ``max_output`` caps captured stdout.
    """
    if timeout is None:
        timeout = default_timeout()
    job = json.dumps({
        "code": code,
        "payload": store.to_payload(),
        "max_output": max_output,
    })
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "admorphiq.repl_agent._sandbox_worker"],
            input=job, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return SandboxResult(timed_out=True, error=f"timeout after {timeout}s")

    if proc.returncode != 0 and not proc.stdout.strip():
        return SandboxResult(error=(proc.stderr or "worker crashed").strip()[:max_output])
    try:
        data = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return SandboxResult(error=(proc.stderr or "unparseable worker output").strip()[:max_output])
    return SandboxResult(
        stdout=data.get("stdout", ""),
        error=data.get("error", ""),
        actions=data.get("actions", []),
    )
