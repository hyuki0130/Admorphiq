"""Maze tool — find the body the controls move, then walk it to the goal.

⛔ Why a model instead of a search. Measured 2026-08-27: the searching generic path opens
hundreds of states on these boards and clears nothing, because the games END when their action
budget runs out (thirteen of the twenty-five declare one, as low as 20 actions for a level). A
walk planned on a map read from the frame costs the length of the path.

⛔ And the trap this one has to survive, measured on the game it was built for: **an action
arriving while the body is mid-animation is SWALLOWED**. A tool that records "this action did
nothing" during an animation learns a false wall. So the mover is identified by what MOVES across
several probes, not by one, and a proposal is repeated when the board does not answer.

Frame-only: the body, the step size, the walkable map and the goal are derived.
"""

from __future__ import annotations

from collections import Counter, deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, frame_2d, has_frame, levels_completed
from admorphiq.tools.segment import edge_band

__all__ = ["MazeRunTool", "blobs_of"]

Cell = tuple[int, int]
_SIMPLE = (1, 2, 3, 4, 5)
# How many times an action is tried before it is believed inert.
_PROBE_TRIES = 4


def blobs_of(g: Any, colour: int) -> list[list[Cell]]:
    """4-connected regions of one colour."""
    n = len(g)
    cells = {(y, x) for y in range(n) for x in range(n) if int(g[y][x]) == colour}
    out: list[list[Cell]] = []
    seen: set[Cell] = set()
    for cell in sorted(cells):
        if cell in seen:
            continue
        stack = [cell]
        seen.add(cell)
        group: list[Cell] = []
        while stack:
            y, x = stack.pop()
            group.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (y + dy, x + dx)
                if nxt in cells and nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        out.append(group)
    return out


def _bbox(group: list[Cell]) -> tuple[int, int, int, int]:
    ys = [c[0] for c in group]
    xs = [c[1] for c in group]
    return min(ys), min(xs), max(ys), max(xs)


class MazeRunTool:
    """Learn which body the simple actions move, then plan its walk to the goal."""

    name = "maze"

    def __init__(self) -> None:
        self._colour: int | None = None
        self._delta: dict[int, Cell] = {}
        self._probe: tuple[int, Cell] | None = None
        self._level: int | None = None
        self._plan: list[int] = []
        self._last: Cell | None = None
        self._repeats = 0
        self._tries: dict[int, int] = {}

    def reset(self) -> None:
        """A new level redraws the maze; the body's colour is re-found and the walk replanned."""
        self._colour = None
        self._delta = {}
        self._probe = None
        self._plan = []
        self._last = None
        self._repeats = 0
        self._tries = {}

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Stateless between frames: the map and the plan come from the board each turn."""

    # -- reading -------------------------------------------------------------

    def _body(self, g: Any) -> tuple[Cell, list[Cell]] | None:
        """The moving body's top-left corner and its cells, for the pinned colour."""
        if self._colour is None:
            return None
        band = edge_band(np.asarray(g).shape)
        groups = [q for q in blobs_of(g, self._colour) if not any(band[y][x] for y, x in q)]
        if not groups:
            return None
        biggest = max(groups, key=len)
        y0, x0, _, _ = _bbox(biggest)
        return (y0, x0), biggest

    def _goal(self, g: Any) -> Cell | None:
        """The other region of the body's colour — a maze marks its exit in the body's colour."""
        if self._colour is None:
            return None
        band = edge_band(np.asarray(g).shape)
        groups = [q for q in blobs_of(g, self._colour)
                  if len(q) >= 4 and not any(band[y][x] for y, x in q)]
        if len(groups) < 2:
            return None
        groups.sort(key=len, reverse=True)
        y0, x0, y1, x1 = _bbox(groups[1])
        return ((y0 + y1) // 2, (x0 + x1) // 2)

    @staticmethod
    def _free(g: Any, body: list[Cell], step: int) -> set[Cell]:
        """Cells the body may occupy: those whose footprint is background or its own colour."""
        n = len(g)
        bg = Counter(int(v) for row in g for v in row).most_common(1)[0][0]
        y0, x0, y1, x1 = _bbox(body)
        h, w = y1 - y0 + 1, x1 - x0 + 1
        own = {int(g[y][x]) for y, x in body}
        ok: set[Cell] = set()
        for y in range(0, n - h + 1, max(1, step)):
            for x in range(0, n - w + 1, max(1, step)):
                if all(int(g[y + i][x + j]) in own or int(g[y + i][x + j]) == bg
                       for i in range(h) for j in range(w)):
                    ok.add((y, x))
        return ok

    # -- Tool protocol -------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        if not has_frame(obs):
            return 0.0
        simple, _ = availability(obs)
        if len(set(simple) & set(_SIMPLE)) < 3:
            return 0.0
        return 0.6 if self._delta else 0.35

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        level = levels_completed(obs)
        if level != self._level:
            self._level = level
            self.reset()
        g = frame_2d(obs)
        simple, _ = availability(obs)
        legal = [a for a in _SIMPLE if a in simple]
        if not legal:
            return []

        if self._probe is not None:
            self._resolve(g)

        if self._colour is None or not self._delta:
            # ⛔ Probe each action SEVERAL times before believing it inert. Measured on this
            # family: the first actions after a reset are ABSORBED — one board swallows two in a
            # row — so a single-shot probe records every control as dead and the tool concludes
            # the board cannot be moved at all.
            untried = [a for a in legal if self._tries.get(a, 0) < _PROBE_TRIES and not any(self._delta.get(a, (0, 0)))]
            if not untried:
                self._delta = {a: d for a, d in self._delta.items() if any(d)}
                return []
            pick = untried[0]
            self._tries[pick] = self._tries.get(pick, 0) + 1
            self._probe = (pick, self._snapshot(g))
            return [(pick, None)]

        found = self._body(g)
        goal = self._goal(g)
        if found is None or goal is None:
            return []
        here, body = found
        step = max(abs(d[0]) or abs(d[1]) for d in self._delta.values() if any(d)) or 1
        free = self._free(g, body, step)
        plan = self._walk(here, goal, free, {a: d for a, d in self._delta.items() if any(d)})
        return [(plan[0], None)] if plan else []

    # -- learning ------------------------------------------------------------

    @staticmethod
    def _snapshot(g: Any) -> Any:
        return np.asarray(g).copy()

    def _resolve(self, g: Any) -> None:
        """Read one probe: which colour region moved, and by how much."""
        action, before = self._probe
        self._probe = None
        cur = np.asarray(g)
        if cur.shape != before.shape:
            return
        # ⛔ Ignore the edge band. Measured: without this the tool picked the HUD COUNTER as the
        # body it was steering — a small blob on the bottom row that advances every action — and
        # reported a "move" of (62, 50).
        inside = ~edge_band(cur.shape)
        moved = np.argwhere((cur != before) & inside)
        if moved.size == 0:
            self._delta.setdefault(action, (0, 0))
            return
        colours = Counter(int(before[y][x]) for y, x in moved)
        for colour, _ in colours.most_common():
            was = blobs_of(before, colour)
            now = blobs_of(cur, colour)
            if not was or not now:
                continue
            a = max(was, key=len)
            b = max(now, key=len)
            if len(a) != len(b) or len(a) < 4:
                continue
            ay, ax, _, _ = _bbox(a)
            by, bx, _, _ = _bbox(b)
            if (by - ay, bx - ax) != (0, 0):
                self._colour = colour
                self._delta[action] = (by - ay, bx - ax)
                return
        self._delta.setdefault(action, (0, 0))

    @staticmethod
    def _walk(start: Cell, goal: Cell, free: set[Cell], delta: dict[int, Cell]) -> list[int]:
        """Shortest action path from the body's corner to the cell containing the goal."""
        seen: dict[Cell, list[int]] = {start: []}
        queue: deque[Cell] = deque([start])
        best: tuple[int, Cell] | None = None
        while queue and len(seen) < 20000:
            pos = queue.popleft()
            dist = abs(pos[0] - goal[0]) + abs(pos[1] - goal[1])
            if best is None or dist < best[0]:
                best = (dist, pos)
            for action, (dy, dx) in delta.items():
                nxt = (pos[0] + dy, pos[1] + dx)
                if nxt in free and nxt not in seen:
                    seen[nxt] = seen[pos] + [action]
                    queue.append(nxt)
        return seen[best[1]] if best and seen.get(best[1]) else []
