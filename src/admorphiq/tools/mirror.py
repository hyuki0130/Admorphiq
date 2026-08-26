"""Mirror tool — two coupled actors under shared controls, brought together.

The mechanic, recovered from frames: a small number of identical actors sit in mirrored halves of
the board; the simple actions move ALL of them at once, one cell per press, with the horizontal
sense MIRRORED between halves; the level clears when they meet.

⛔ Why plan rather than search. Measured 2026-08-27 on the game this was built for: a random walk
clears its first level in 135 actions and the searching generic path in **604**, against a human
baseline of 30. Learning the transition from two probes and planning the join takes **15**.

⛔ Frame-only. The actor colour, the cell size, the walkable map and each actor's mirror sense are
all DERIVED — the sense from a probe, not from which side of the frame an actor happens to be on.
"""

from __future__ import annotations

from collections import Counter, deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, frame_2d, has_frame, levels_completed
from admorphiq.tools.segment import background

__all__ = ["MirrorMergeTool", "actors_of"]

Cell = tuple[int, int]
_SIMPLE = (1, 2, 3, 4)


def actors_of(g: Any, colour: int | None = None) -> tuple[list[Cell], int, int]:
    """The actors' top-left corners, their colour and their size.

    Actors are the RAREST colour that forms several identical square blobs: a board's scenery is
    plentiful and its pieces are few.
    """
    hist = Counter(int(v) for row in g for v in row)
    n = len(g)
    # ⛔ Once an actor colour is known, keep it. Measured: re-picking "the rarest colour" every
    # frame latched onto a different colour mid-plan and reported the actors at two opposite
    # corners of the frame, after which every plan was about the wrong objects.
    order = [colour] if colour is not None else [c for c, _ in sorted(hist.items(), key=lambda kv: kv[1])]
    for colour in order:
        cells = {(y, x) for y in range(n) for x in range(n) if int(g[y][x]) == colour}
        if not 2 <= len(cells) <= 400:
            continue
        corners = [
            (y, x) for (y, x) in sorted(cells)
            if not any((y - dy, x - dx) in cells for dy in range(6) for dx in range(6) if dy or dx)
        ]
        if len(corners) < 2 or len(cells) % len(corners):
            continue
        area = len(cells) // len(corners)
        side = int(round(area ** 0.5))
        if side * side != area or side < 2:
            continue
        return corners, colour, side
    return [], -1, 0


def _half(cell: Cell, size: int) -> int:
    """Which half of the board a cell sits in — the actor identity that survives a re-sort."""
    return 0 if cell[1] * 2 < size else 1


class MirrorMergeTool:
    """Learn how the controls move each actor, then plan the join."""

    name = "mirror"

    def __init__(self) -> None:
        self._delta: dict[int, dict[int, Cell]] = {}   # action -> {half: (dy, dx)}
        self._probe: tuple[int, list[Cell]] | None = None
        self._level: int | None = None
        self._size = 64
        self._colour: int | None = None

    def reset(self) -> None:
        """A new level re-mirrors the board, so the learned deltas do not carry."""
        self._delta = {}
        self._probe = None
        self._colour = None

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Stateless between frames: the plan is recomputed from the board each turn."""

    # -- reading -------------------------------------------------------------

    @staticmethod
    def _walkable(g: Any, side: int, actor: int) -> set[Cell]:
        """Cells an actor may stand on: those whose centre is background or another actor."""
        bg = background(g)
        n = len(g)
        free: set[Cell] = set()
        for y in range(0, n - side + 1):
            for x in range(0, n - side + 1):
                c = int(g[y + side // 2][x + side // 2])
                if c in bg or c == actor:
                    free.add((y, x))
        return free

    def _learn(self, corners: list[Cell]) -> None:
        probe = self._probe
        self._probe = None
        if probe is None:
            return
        action, before = probe
        if len(before) != len(corners):
            return
        # ⛔ Key the delta by WHICH HALF the actor is in, not by its index in a sorted list.
        # Measured: the corner list is sorted, so as soon as two actors' sort order flips, an
        # index-keyed delta is applied to the wrong actor and every plan after that is fiction.
        # Actors stay in their own half on a mirrored board, so the half is a stable identity.
        n = self._size
        self._delta[action] = {
            _half(b, n): (a[0] - b[0], a[1] - b[1])
            for b, a in zip(sorted(before, key=lambda c: c[1]), sorted(corners, key=lambda c: c[1]))
        }

    # -- Tool protocol -------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        if not has_frame(obs):
            return 0.0
        simple, _ = availability(obs)
        if not set(simple) & set(_SIMPLE):
            return 0.0
        corners, _, side = actors_of(frame_2d(obs))
        if len(corners) < 2 or side == 0:
            return 0.0
        return 0.8 if any(self._delta.values()) else 0.5

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        level = levels_completed(obs)
        if level != self._level:
            self._level = level
            self.reset()
        g = frame_2d(obs)
        self._size = len(g)
        corners, colour, side = actors_of(g, self._colour)
        if len(corners) < 2 or side == 0:
            return []
        self._colour = colour
        if self._probe is not None:
            self._learn(corners)

        simple, _ = availability(obs)
        legal = [a for a in _SIMPLE if a in simple]
        untried = [a for a in legal if a not in self._delta]
        if untried:
            # ⛔ Probe the sense, never assume it from which half an actor sits in: the mirror is
            # a property of the CONTROL, and reading it off geometry is a guess that costs the
            # level when the board is mirrored about the other axis.
            self._probe = (untried[0], list(corners))
            return [(untried[0], None)]

        moving = {a: d for a, d in self._delta.items() if any(v != (0, 0) for v in d.values())}
        if not moving:
            return []
        free = self._walkable(g, side, colour)
        plan = self._plan_join(tuple(corners), moving, free, len(g))
        return [(plan[0], None)] if plan else []

    @staticmethod
    def _plan_join(start: tuple[Cell, ...], moving: dict[int, dict[int, Cell]],
                   free: set[Cell], size: int) -> list[int]:
        """Shortest action sequence bringing every actor onto one cell."""
        def apply(state: tuple[Cell, ...], action: int) -> tuple[Cell, ...]:
            out = []
            for pos in state:
                dy, dx = moving[action].get(_half(pos, size), (0, 0))
                nxt = (pos[0] + dy, pos[1] + dx)
                out.append(nxt if nxt in free else pos)
            return tuple(out)

        seen: dict[tuple[Cell, ...], list[int]] = {start: []}
        queue: deque[tuple[Cell, ...]] = deque([start])
        while queue and len(seen) < 20000:
            state = queue.popleft()
            if len(set(state)) == 1:
                return seen[state]
            for action in moving:
                nxt = apply(state, action)
                if nxt not in seen:
                    seen[nxt] = seen[state] + [action]
                    queue.append(nxt)
        return []
