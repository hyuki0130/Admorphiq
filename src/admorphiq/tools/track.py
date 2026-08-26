"""Track tool — bring the marked item to the marked slot on a rotating track.

The mechanic, recovered from frames: a closed loop of equal square tiles, each a flat colour; a
STATIC marker drawn beside one slot; and controls that rotate the whole loop one slot per press.
The level is won when the tile whose colour matches the marker sits in the marked slot.

⛔ Why this shape of tool rather than a search. Measured 2026-08-27 across the 25 sample games:
the generic searching path clears a first level 6x to 109x over the budget the game DECLARES, and
thirteen of the games end when that budget runs out. On the game this was built for, the search
took 924 actions for a level that allows 13. Rotating a ring to a computed offset takes as many
presses as the offset — which is what the human baseline is.

⛔ Frame-only, by construction: the tile side, the lattice pitch, the loop order, which control
turns which way, and which colour is the target are all DERIVED. Nothing about any game is
written down here.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, frame_2d, has_frame

__all__ = ["TrackAlignTool", "tiles_of", "loop_order"]

Cell = tuple[int, int]


def _uniform_blocks(g: Any, side: int) -> dict[Cell, int]:
    """Top-left corners of every `side`x`side` block that is one flat colour."""
    n = len(g)
    bg = Counter(int(v) for row in g for v in row).most_common(2)
    ignore = {c for c, _ in bg}
    found: dict[Cell, int] = {}
    for y in range(n - side + 1):
        for x in range(n - side + 1):
            first = int(g[y][x])
            if first in ignore:
                continue
            if all(int(g[y + i][x + j]) == first for i in range(side) for j in range(side)):
                found[(y, x)] = first
    corners: dict[Cell, int] = {}
    for (y, x) in sorted(found):
        if not any((y - dy, x - dx) in found for dy in range(side) for dx in range(side) if dy or dx):
            corners[(y, x)] = found[(y, x)]
    return corners


def loop_order(origins: list[Cell], pitch: int) -> list[Cell] | None:
    """Order the tiles around their closed loop, or None when they do not form one.

    Two tiles are adjacent when they sit exactly `pitch` apart along one axis and share the other.
    On a closed track every tile then has exactly two neighbours, which is what is checked: a
    scatter of blocks that happens to be equal-sized is not a track.
    """
    # ⛔ Peel, do not reject. Requiring EVERY block to have two neighbours failed on a real
    # board because the controls are blocks too and have none — the track was there and the
    # check threw it away. Drop anything that cannot be on a cycle, repeatedly, and see what
    # survives.
    pos = set(origins)
    while True:
        adj = {
            (y, x): [c for c in ((y, x + pitch), (y, x - pitch), (y + pitch, x), (y - pitch, x)) if c in pos]
            for (y, x) in pos
        }
        drop = {c for c, near in adj.items() if len(near) != 2}
        if not drop:
            break
        pos -= drop
        if len(pos) < 6:
            return None
    if not adj:
        return None
    origins = sorted(pos)
    start = min(adj)
    order = [start]
    prev, cur = None, start
    while True:
        nxt = next((c for c in adj[cur] if c != prev), None)
        if nxt is None or nxt == start:
            break
        order.append(nxt)
        prev, cur = cur, nxt
    return order if len(order) == len(origins) >= 6 else None


def _pitch(origins: list[Cell], side: int) -> int:
    gaps: list[int] = []
    for axis in (0, 1):
        vals = sorted({o[axis] for o in origins})
        gaps += [b - a for a, b in zip(vals, vals[1:]) if b - a >= side]
    return Counter(gaps).most_common(1)[0][0] if gaps else 0


def tiles_of(g: Any) -> tuple[dict[Cell, int], int]:
    """The track's tiles and their side, with the side taken from the data.

    ⛔ The side is the one whose blocks form a closed LOOP, not the one that finds the most
    blocks. Measured: "most blocks wins" chose side 2 on a board whose tiles are 4x4, because a
    4x4 tile contains four 2x2 ones and the smaller side always wins a count. Structure decides,
    not quantity.
    """
    for side in (6, 5, 4, 3, 2):
        blocks = _uniform_blocks(g, side)
        if len(blocks) < 6:
            continue
        pitch = _pitch(list(blocks), side)
        if pitch > 0 and loop_order(list(blocks), pitch) is not None:
            return blocks, side
    return {}, 0


class TrackAlignTool:
    """Rotate a closed track until the marked colour reaches the marked slot."""

    name = "track"

    def __init__(self) -> None:
        self._controls: list[Cell] = []
        self._shift: dict[Cell, int] = {}
        self._probed: Cell | None = None
        self._before: list[int] | None = None
        self._plan: list[Cell] = []

    def reset(self) -> None:
        """A new level redraws the track; what each control does is re-learned."""
        self._controls = []
        self._shift = {}
        self._probed = None
        self._before = None
        self._plan = []

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Stateless between frames: everything is recomputed from the board each turn."""

    # -- reading the board ---------------------------------------------------

    def _read(self, g: Any) -> tuple[list[Cell], list[int], int, int] | None:
        blocks, side = tiles_of(g)
        if side == 0 or len(blocks) < 6:
            return None
        pitch = _pitch(list(blocks), side)
        if pitch <= 0:
            return None
        order = loop_order(list(blocks), pitch)
        if order is None:
            return None
        return order, [blocks[o] for o in order], side, pitch

    def _marked_slot(self, g: Any, order: list[Cell], side: int) -> tuple[int, int] | None:
        """Which slot is marked, and with which colour.

        The marker is drawn OUTSIDE the tiles in a tile colour — brackets, a highlight, a frame.
        So: take the cells of each tile colour that belong to no tile, and find the slot they sit
        closest to. A colour with no such stray cells is not the marker.
        """
        n = len(g)
        owned = {(y + i, x + j) for (y, x) in order for i in range(side) for j in range(side)}
        colours = {c for c in (int(g[y][x]) for (y, x) in order)}
        stray: dict[int, list[Cell]] = {}
        for y in range(n):
            for x in range(n):
                c = int(g[y][x])
                if c in colours and (y, x) not in owned:
                    stray.setdefault(c, []).append((y, x))
        if not stray:
            return None
        colour, cells = min(stray.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        cy = sum(c[0] for c in cells) / len(cells)
        cx = sum(c[1] for c in cells) / len(cells)
        slot = min(range(len(order)), key=lambda i: (order[i][0] - cy) ** 2 + (order[i][1] - cx) ** 2)
        return slot, colour

    # -- Tool protocol -------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        if not has_frame(obs):
            return 0.0
        read = self._read(frame_2d(obs))
        if read is None:
            return 0.0
        order, colours, side, _ = read
        return 0.85 if self._marked_slot(frame_2d(obs), order, side) else 0.3

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        g = frame_2d(obs)
        read = self._read(g)
        if read is None:
            return []
        order, colours, side, pitch = read
        marked = self._marked_slot(g, order, side)
        if marked is None:
            return []
        slot, target = marked
        if colours[slot] == target:
            return []                                   # already aligned; nothing to press

        if self._probed is not None and self._before is not None:
            self._learn(colours)

        if not self._shift:
            control = self._pick_control(g, order, side)
            if control is None:
                return []
            self._probed, self._before = control, list(colours)
            return [(6, (control[1], control[0]))]

        want = [i for i, c in enumerate(colours) if c == target]
        if not want:
            return []
        best: tuple[int, Cell] | None = None
        for control, step in self._shift.items():
            if step == 0:
                continue
            for src in want:
                # after k presses the tile at `src` sits at (src + k*step) mod len
                for k in range(1, len(order) + 1):
                    if (src + k * step) % len(order) == slot:
                        if best is None or k < best[0]:
                            best = (k, control)
                        break
        if best is None:
            return []
        return [(6, (best[1][1], best[1][0]))]

    def _learn(self, colours: list[int]) -> None:
        """How far, and which way, did the press just taken rotate the track?"""
        before, control = self._before, self._probed
        self._probed, self._before = None, None
        if before is None or control is None or len(before) != len(colours):
            return
        size = len(colours)
        for step in range(1, size):
            if all(colours[(i + step) % size] == before[i] for i in range(size)):
                self._shift[control] = step
                return
        self._shift[control] = 0                        # this control does not rotate the track

    def _pick_control(self, g: Any, order: list[Cell], side: int) -> Cell | None:
        """A control is a coloured blob that is not a tile and not the marker.

        Untried ones first; a control whose effect is already known is never re-probed.
        """
        n = len(g)
        owned = {(y + i, x + j) for (y, x) in order for i in range(side) for j in range(side)}
        bg = {c for c, _ in Counter(int(v) for row in g for v in row).most_common(2)}
        seen: set[Cell] = set()
        blobs: list[list[Cell]] = []
        for y in range(n):
            for x in range(n):
                if (y, x) in owned or (y, x) in seen or int(g[y][x]) in bg:
                    continue
                stack = [(y, x)]
                seen.add((y, x))
                blob: list[Cell] = []
                while stack:
                    cy, cx = stack.pop()
                    blob.append((cy, cx))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if (0 <= ny < n and 0 <= nx < n and (ny, nx) not in seen
                                and (ny, nx) not in owned and int(g[ny][nx]) not in bg):
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                if len(blob) >= side * side:
                    blobs.append(blob)
        # ⛔ A control is COMPACT. Measured: the largest non-track blob on a real board is the
        # frame's own one-pixel border, and probing it spent an action to learn that the border
        # does nothing. Anything spanning most of the frame is chrome, not a button.
        candidates = []
        for blob in blobs:
            ys = [c[0] for c in blob]
            xs = [c[1] for c in blob]
            h = max(ys) - min(ys) + 1
            w = max(xs) - min(xs) + 1
            if h > n // 2 or w > n // 2:
                continue
            if len(blob) < 0.4 * h * w:
                continue                                # a thin outline, not a solid control
            candidates.append((len(blob), blob))
        for _, blob in sorted(candidates, key=lambda kv: -kv[0]):
            cy = sum(c[0] for c in blob) // len(blob)
            cx = sum(c[1] for c in blob) // len(blob)
            if (cy, cx) not in self._shift:
                return (cy, cx)
        return None
