"""Slide skeleton pieces until their arms cover a board's pinned target marks.

The family this reads: the board carries a handful of small MARKS, each a 3x3 ring of one
flat colour with a differently-coloured pip at its middle, and one or more PIECES — thin
skeletal shapes (a cross, a rectangle outline) drawn in the pip colours. The level is won
when every mark's pip is standing on a piece cell of that pip's own colour. Nothing else
about the board matters, so the whole game reduces to: for each colour, find the rigid
translation of that piece whose cells cover every pip of that colour, then walk it there.

Two things are LEARNED rather than assumed, because assuming either was wrong on the
board this was built against:

* Which action moves which way, and by how far. The tool issues a move, watches the
  piece's cells shift, and records the vector. Until it has a vector for a direction it
  spends one action finding out; a move that changes nothing is retried before the action
  is believed inert, because these boards swallow actions during animations.
* Which piece the controls are currently driving. The driven piece wears a single
  odd-coloured cell at its middle, which is a frame fact, but the tool still checks each
  observed shift against its belief and re-reads the frame if they disagree.

The marks are drawn ON TOP of the pieces, so a piece passing under one is cut into
fragments with a 3-cell hole. Both are repaired here — fragments of one colour that sit
within a mark's width of each other are one piece, and a hidden cell flanked by that
colour on both sides in a straight line is part of the piece.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, frame_2d, has_frame
from admorphiq.tools.segment import background, edge_band

__all__ = ["CoverTargetsTool"]

Cell = tuple[int, int]

# A mark is a pip ringed by its 8 neighbours: the smallest shape that can say "here".
_MARK = 3
# Fragments of one colour this close belong to the same piece — a mark can hide no more.
_BRIDGE = _MARK + 1
# An action is only believed inert after it has failed to move anything this many times.
_INERT_AFTER = 3


def _neighbours8(r: int, c: int) -> list[Cell]:
    return [(r + dy, c + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]


class CoverTargetsTool:
    """Cover every target pip with the piece of that pip's colour (see module docstring)."""

    name = "cover_targets"

    def __init__(self) -> None:
        self._spec: tuple[int, list[tuple[int, int, int]]] | None = None
        self._effect: dict[int, tuple[int, int]] = {}
        self._select: int | None = None
        self._noeffect: Counter[int] = Counter()
        self._prev: np.ndarray | None = None
        self._prev_action: int | None = None
        self._giveup: set[int] = set()
        self._idle = 0

    # --- lifecycle ---------------------------------------------------------

    def reset(self) -> None:
        """Drop the per-level goal; the learned control map survives, it is the game's."""
        self._spec = None
        self._prev = None
        self._prev_action = None
        self._giveup = set()
        self._idle = 0

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """The harness's transition hook; the tool learns from its own frames in propose."""

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Confidence, which is zero unless a covering translation actually exists."""
        if not has_frame(obs):
            return 0.0
        simple, _ = availability(obs)
        if len([a for a in simple if a in (1, 2, 3, 4, 5)]) < 4:
            return 0.0
        grid = frame_2d(obs)
        read = self._read(grid)
        if read is None:
            return 0.0
        _, pips, pieces, _ = read
        wanted = {p[2] for p in pips}
        if not wanted <= {q["colour"] for q in pieces}:
            return 0.0
        for piece in pieces:
            want = [(p[0], p[1]) for p in pips if p[2] == piece["colour"]]
            if want and _offsets(piece["mask"], want):
                return 0.85
        return 0.0

    # --- perception --------------------------------------------------------

    def _marks(self, grid: np.ndarray) -> tuple[int, list[tuple[int, int, int]]] | None:
        """The goal: the ring colour, and every (row, col, pip colour) it encircles."""
        if self._spec is not None:
            return self._spec
        h, w = grid.shape
        bg = background(grid.tolist())
        found: dict[int, list[tuple[int, int, int]]] = {}
        for r in range(1, h - 1):
            for c in range(1, w - 1):
                pip = int(grid[r, c])
                if pip in bg:
                    continue
                ring = {int(grid[y, x]) for y, x in _neighbours8(r, c)}
                if len(ring) != 1:
                    continue
                ringc = ring.pop()
                if ringc == pip or ringc in bg:
                    continue
                found.setdefault(ringc, []).append((r, c, pip))
        if not found:
            return None
        ringc, marks = max(found.items(), key=lambda kv: len(kv[1]))
        if len(marks) < 2:
            return None
        self._spec = (ringc, marks)
        return self._spec

    def _read(
        self, grid: np.ndarray
    ) -> tuple[int, list[tuple[int, int, int]], list[dict[str, Any]], int | None] | None:
        """(ring colour, marks, pieces, index of the driven piece) or None if this is not it."""
        spec = self._marks(grid)
        if spec is None:
            return None
        ringc, marks = spec
        hidden = {
            (r + dy, c + dx)
            for r, c, _ in marks
            for dy in (-1, 0, 1)
            for dx in (-1, 0, 1)
        }
        chrome = edge_band(grid.shape, margin_div=min(grid.shape))
        bg = background(grid.tolist())
        blocked = set(bg) | {ringc}

        cells: dict[int, list[Cell]] = {}
        h, w = grid.shape
        for r in range(h):
            for c in range(w):
                if chrome[r, c] or (r, c) in hidden:
                    continue
                v = int(grid[r, c])
                if v in blocked:
                    continue
                cells.setdefault(v, []).append((r, c))

        groups: list[tuple[int, list[Cell]]] = []
        for colour, pts in cells.items():
            for grp in _cluster(pts, _BRIDGE):
                groups.append((colour, grp))
        if not groups:
            return None

        big = [(col, grp) for col, grp in groups if len(grp) > 2]
        small = [(col, grp) for col, grp in groups if len(grp) <= 2]
        if not big:
            return None

        pieces: list[dict[str, Any]] = []
        for colour, grp in big:
            mask = set(grp) | _bridged(grid, colour, hidden, grp)
            pieces.append({"colour": colour, "mask": frozenset(mask), "cells": grp})

        driven = _driven(pieces, small)
        return ringc, marks, pieces, driven

    # --- planning ----------------------------------------------------------

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        """One action toward covering the pips, learning the controls as it goes."""
        if not has_frame(obs):
            return []
        grid = frame_2d(obs)
        self._learn(grid)
        read = self._read(grid)
        self._prev, self._prev_action = grid, None
        if read is None:
            return []
        _, pips, pieces, driven = read

        need: dict[int, tuple[int, int]] = {}
        for piece in pieces:
            colour = piece["colour"]
            if colour in self._giveup:
                continue
            want = [(p[0], p[1]) for p in pips if p[2] == colour]
            if not want:
                continue
            step = self._stride()
            options = _offsets(piece["mask"], want)
            if step:
                options = {o for o in options if o[0] % step == 0 and o[1] % step == 0}
            if not options:
                self._giveup.add(colour)
                continue
            best = min(options, key=lambda o: (abs(o[0]) + abs(o[1]), o))
            if best != (0, 0):
                need[colour] = best
        if not need:
            return []

        if driven is None:
            return self._explore(None)
        wheel = pieces[driven]["colour"]
        if wheel not in need:
            return self._cycle()
        dy, dx = need[wheel]
        return self._explore((dy, dx))

    # --- control learning --------------------------------------------------

    def _stride(self) -> int:
        """How far one move carries a piece, once a move has actually been seen."""
        seen = [abs(v) for vec in self._effect.values() for v in vec if v]
        return min(seen) if seen else 0

    def _learn(self, grid: np.ndarray) -> None:
        """Attribute the last action: did a piece shift, did the driven piece change, or neither."""
        if self._prev is None or self._prev_action is None:
            return
        action = self._prev_action
        before, after = self._read(self._prev), self._read(grid)
        if before is None or after is None:
            return
        shift = _shift(before[2], after[2])
        if shift is not None and shift != (0, 0):
            self._effect[action] = shift
            self._noeffect[action] = 0
            self._idle = 0
            return
        if before[3] is not None and after[3] is not None and \
                before[2][before[3]]["colour"] != after[2][after[3]]["colour"]:
            self._select = action
            self._noeffect[action] = 0
            self._idle = 0
            return
        self._noeffect[action] += 1

    def _usable(self) -> list[int]:
        return [a for a in (1, 2, 3, 4, 5) if self._noeffect[a] < _INERT_AFTER]

    def _emit(self, action: int) -> list[Step]:
        self._prev_action = action
        return [(action, None)]

    def _cycle(self) -> list[Step]:
        """Hand the controls to another piece."""
        if self._select is not None:
            return self._emit(self._select)
        return self._explore(None)

    def _explore(self, want: tuple[int, int] | None) -> list[Step]:
        """The action that moves the wanted way, or the cheapest way to find one out."""
        if want is not None:
            dy, dx = want
            axis = (dy, 0) if abs(dy) >= abs(dx) else (0, dx)
            for _ in range(2):
                for action, vec in self._effect.items():
                    if self._noeffect[action] >= _INERT_AFTER:
                        continue
                    if _aligned(vec, axis):
                        return self._emit(action)
                axis = (0, dx) if axis[0] else (dy, 0)
                if axis == (0, 0):
                    break
        unknown = [a for a in self._usable() if a not in self._effect and a != self._select]
        if unknown:
            return self._emit(unknown[0])
        self._idle += 1
        if self._idle > 2:
            return []
        retry = [a for a in self._usable() if a in self._effect]
        return self._emit(retry[0]) if retry else []


# --- geometry ---------------------------------------------------------------


def _cluster(pts: list[Cell], gap: int) -> list[list[Cell]]:
    """Split cells into groups no further apart than `gap` — a mark cannot hide more."""
    parent = list(range(len(pts)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            if max(abs(pts[i][0] - pts[j][0]), abs(pts[i][1] - pts[j][1])) <= gap:
                a, b = find(i), find(j)
                if a != b:
                    parent[a] = b
    out: dict[int, list[Cell]] = {}
    for i, p in enumerate(pts):
        out.setdefault(find(i), []).append(p)
    return list(out.values())


def _bridged(grid: np.ndarray, colour: int, hidden: set[Cell], grp: list[Cell]) -> set[Cell]:
    """Cells a mark is covering that the piece plainly runs through."""
    if not hidden:
        return set()
    own = set(grp)
    y0 = min(p[0] for p in grp) - _MARK
    y1 = max(p[0] for p in grp) + _MARK
    x0 = min(p[1] for p in grp) - _MARK
    x1 = max(p[1] for p in grp) + _MARK
    h, w = grid.shape
    out: set[Cell] = set()
    for r, c in hidden:
        if not (y0 <= r <= y1 and x0 <= c <= x1):
            continue
        for dy, dx in ((0, 1), (1, 0)):
            ends = []
            for sign in (1, -1):
                y, x = r + dy * sign, c + dx * sign
                while 0 <= y < h and 0 <= x < w and (y, x) in hidden:
                    y, x = y + dy * sign, x + dx * sign
                ends.append((y, x) in own)
            if all(ends):
                out.add((r, c))
                break
    return out


def _offsets(mask: frozenset[Cell], pips: list[Cell]) -> set[Cell]:
    """Every translation of `mask` that lands a piece cell on each of `pips`."""
    cand: set[Cell] | None = None
    for py, px in pips:
        here = {(py - my, px - mx) for my, mx in mask}
        cand = here if cand is None else (cand & here)
        if not cand:
            return set()
    return cand or set()


def _driven(pieces: list[dict[str, Any]], small: list[tuple[int, list[Cell]]]) -> int | None:
    """The piece wearing the odd cell that marks it as the one the controls drive."""
    for _, grp in small:
        y, x = grp[0]
        best, dist = None, None
        for i, piece in enumerate(pieces):
            d = min(max(abs(y - my), abs(x - mx)) for my, mx in piece["mask"])
            if dist is None or d < dist:
                best, dist = i, d
        if best is not None and dist is not None and dist <= _BRIDGE:
            return best
    return None


def _shift(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> tuple[int, int] | None:
    """The rigid translation one piece underwent, if exactly one moved rigidly."""
    found: tuple[int, int] | None = None
    by_colour = {p["colour"]: p for p in after}
    for piece in before:
        other = by_colour.get(piece["colour"])
        if other is None or len(other["mask"]) != len(piece["mask"]):
            continue
        old, new = piece["mask"], other["mask"]
        if old == new:
            continue
        dy = min(p[0] for p in new) - min(p[0] for p in old)
        dx = min(p[1] for p in new) - min(p[1] for p in old)
        if {(y + dy, x + dx) for y, x in old} != set(new):
            continue
        if found is not None:
            return None
        found = (dy, dx)
    return found


def _aligned(vec: tuple[int, int], axis: tuple[int, int]) -> bool:
    """Does `vec` push along `axis` — same sign, same axis, nothing sideways?"""
    dy, dx = vec
    ay, ax = axis
    if ay:
        return dx == 0 and dy * ay > 0
    return dy == 0 and dx * ax > 0
