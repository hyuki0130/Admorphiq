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


def loops(origins: list[Cell], pitch: int) -> list[list[Cell]]:
    """Every closed loop among these tiles, each ordered around itself.

    ⛔ Plural, because a board can carry several. Measured: this game's second level has THREE
    concentric rings with their own control pairs, and a single-loop reader saw one ring and
    could not move the others.

    Two tiles are adjacent when they sit exactly `pitch` apart along one axis and share the
    other. Blocks that cannot lie on a cycle are PEELED first — the controls are blocks too and
    have no neighbours at all — then each remaining connected component is accepted only if every
    one of its members has exactly two neighbours, i.e. it really is a cycle.
    """
    pos = set(origins)
    while True:
        adj = {
            (y, x): [c for c in ((y, x + pitch), (y, x - pitch), (y + pitch, x), (y - pitch, x)) if c in pos]
            for (y, x) in pos
        }
        drop = {c for c, near in adj.items() if len(near) < 2}
        if not drop:
            break
        pos -= drop
        if not pos:
            return []
    out: list[list[Cell]] = []
    unseen = set(pos)
    while unseen:
        start = min(unseen)
        comp = {start}
        stack = [start]
        while stack:
            cur = stack.pop()
            for nxt in adj[cur]:
                if nxt not in comp:
                    comp.add(nxt)
                    stack.append(nxt)
        unseen -= comp
        if len(comp) < 6 or any(len(adj[c]) != 2 for c in comp):
            continue
        order = _walk(comp, adj)
        if order is not None:
            out.append(order)
    return out


def _walk(comp: set[Cell], adj: dict[Cell, list[Cell]]) -> list[Cell] | None:
    start = min(comp)
    order = [start]
    prev, cur = None, start
    while True:
        nxt = next((c for c in adj[cur] if c != prev), None)
        if nxt is None or nxt == start:
            break
        order.append(nxt)
        prev, cur = cur, nxt
    return order if len(order) == len(comp) else None


def loop_order(origins: list[Cell], pitch: int) -> list[Cell] | None:
    """The single largest loop, kept for callers that only want one."""
    found = loops(origins, pitch)
    return max(found, key=len) if found else None


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
    best: tuple[int, dict[Cell, int], int] = (0, {}, 0)
    for side in (6, 5, 4, 3, 2):
        blocks = _uniform_blocks(g, side)
        if len(blocks) < 6:
            continue
        for pitch in _candidate_pitches(list(blocks), side):
            found = loops(list(blocks), pitch)
            covered = sum(len(ring) for ring in found)
            if covered > best[0]:
                best = (covered, blocks, side)
    return best[1], best[2]


def _candidate_pitches(origins: list[Cell], side: int) -> list[int]:
    """Every gap the tiles actually exhibit, commonest first.

    ⛔ Not just the modal gap. Measured: a board with three concentric rings has its tiles at one
    spacing along each ring and a different one between rings, and taking the single commonest
    gap found no loop at all where the right gap finds two.
    """
    gaps: Counter[int] = Counter()
    for axis in (0, 1):
        vals = sorted({o[axis] for o in origins})
        for a, b in zip(vals, vals[1:]):
            if b - a >= side:
                gaps[b - a] += 1
    base = [g for g, _ in gaps.most_common(4)]
    # ⛔ Multiples too. Measured on a three-ring board whose rings sit one tile apart: adjacency
    # at the base gap links the rings to each other, every interior tile then has more than two
    # neighbours and the peel deletes the whole track. The ring's own spacing is a MULTIPLE of
    # the gap between rings, so the multiples have to be candidates.
    out: list[int] = []
    for g in base:
        for k in (1, 2, 3):
            if g * k not in out:
                out.append(g * k)
    return out


class TrackAlignTool:
    """Rotate a closed track until the marked colour reaches the marked slot."""

    name = "track"

    def __init__(self) -> None:
        self._controls: list[Cell] = []
        self._shift: dict[Cell, tuple[int, int]] = {}   # control -> (ring index, slots per press)
        self._probed: Cell | None = None
        self._before: list[list[int]] | None = None
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

    def _read(self, g: Any) -> tuple[list[list[Cell]], list[list[int]], int, int] | None:
        """Every ring on the board, with the colours currently sitting in each of its slots."""
        blocks, side = tiles_of(g)
        if side == 0 or len(blocks) < 6:
            return None
        best: tuple[int, list[list[Cell]], int] = (0, [], 0)
        for pitch in _candidate_pitches(list(blocks), side):
            rings = loops(list(blocks), pitch)
            covered = sum(len(r) for r in rings)
            if covered > best[0]:
                best = (covered, rings, pitch)
        if not best[1]:
            return None
        return best[1], [[blocks[o] for o in ring] for ring in best[1]], side, best[2]

    def _marked_slot(self, g: Any, ring: list[Cell], owned: set[Cell], side: int) -> tuple[int, int] | None:
        """Which slot of THIS ring is marked, and with which colour.

        The marker is drawn OUTSIDE the tiles in a tile colour — brackets, a highlight, a frame.
        So: take cells of a ring colour that belong to no tile anywhere, keep those nearest this
        ring, and read off the slot they sit against.
        """
        n = len(g)
        colours = {int(g[y][x]) for (y, x) in ring}
        stray: dict[int, list[Cell]] = {}
        for y in range(n):
            for x in range(n):
                c = int(g[y][x])
                if c in colours and (y, x) not in owned:
                    stray.setdefault(c, []).append((y, x))
        best: tuple[float, int, int] | None = None
        for colour, cells in stray.items():
            cy = sum(c[0] for c in cells) / len(cells)
            cx = sum(c[1] for c in cells) / len(cells)
            slot = min(range(len(ring)), key=lambda i: (ring[i][0] - cy) ** 2 + (ring[i][1] - cx) ** 2)
            dist = (ring[slot][0] - cy) ** 2 + (ring[slot][1] - cx) ** 2
            if dist > (4 * side) ** 2:
                continue                                # this marker belongs to another ring
            if best is None or dist < best[0]:
                best = (dist, slot, colour)
        return None if best is None else (best[1], best[2])

    # -- Tool protocol -------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        if not has_frame(obs):
            return 0.0
        g = frame_2d(obs)
        read = self._read(g)
        if read is None:
            return 0.0
        rings, _, side, _ = read
        owned = self._owned(rings, side)
        # ⛔ No marker, no bid. Returning a consolation 0.3 for "there is a loop here" cost a
        # DIFFERENT game 0.0943 of its score, measured full-25: a lattice that happens to contain
        # a cycle is not this mechanic, and a tool with nothing to propose must not compete for
        # the turn.
        marked = any(self._marked_slot(g, r, owned, side) for r in rings)
        return 0.85 if marked else 0.0

    @staticmethod
    def _owned(rings: list[list[Cell]], side: int) -> set[Cell]:
        return {(y + i, x + j) for ring in rings for (y, x) in ring
                for i in range(side) for j in range(side)}

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        g = frame_2d(obs)
        read = self._read(g)
        if read is None:
            return []
        rings, palettes, side, pitch = read
        owned = self._owned(rings, side)

        if self._probed is not None and self._before is not None:
            self._learn(palettes)

        # Which rings still need turning, and by how much, under each control we know.
        wants: list[tuple[int, int, int]] = []          # (ring index, slot, target colour)
        for i, ring in enumerate(rings):
            marked = self._marked_slot(g, ring, owned, side)
            if marked is None:
                continue
            slot, target = marked
            if palettes[i][slot] != target:
                wants.append((i, slot, target))
        if not wants:
            return []

        best: tuple[int, Cell] | None = None
        for control, (ring_idx, step) in self._shift.items():
            if step == 0 or ring_idx >= len(rings):
                continue
            for want_idx, slot, target in wants:
                if want_idx != ring_idx:
                    continue
                size = len(rings[ring_idx])
                for src, colour in enumerate(palettes[ring_idx]):
                    if colour != target:
                        continue
                    for k in range(1, size + 1):
                        if (src + k * step) % size == slot:
                            if best is None or k < best[0]:
                                best = (k, control)
                            break
        if best is not None:
            return [(6, (best[1][1], best[1][0]))]

        control = self._pick_control(g, owned, side)
        if control is None:
            return []
        self._probed, self._before = control, [list(p) for p in palettes]
        return [(6, (control[1], control[0]))]

    def _learn(self, palettes: list[list[int]]) -> None:
        """Which ring did the press just taken turn, and by how many slots?"""
        before, control = self._before, self._probed
        self._probed, self._before = None, None
        if before is None or control is None or len(before) != len(palettes):
            return
        for idx, (was, now) in enumerate(zip(before, palettes)):
            if len(was) != len(now) or was == now:
                continue
            size = len(now)
            for step in range(1, size):
                if all(now[(i + step) % size] == was[i] for i in range(size)):
                    self._shift[control] = (idx, step)
                    return
        self._shift[control] = (0, 0)                   # this control turns nothing

    def _pick_control(self, g: Any, owned: set[Cell], side: int) -> Cell | None:
        """A control is a coloured blob that is not a tile and not the marker.

        Untried ones first; a control whose effect is already known is never re-probed.
        """
        n = len(g)
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
