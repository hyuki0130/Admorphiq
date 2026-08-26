"""Stencil tool — paint a small instruction glyph onto a lattice of equal tiles.

Recovered from frames alone in round r101 and measured on ft09 (levels 1-4, 62 actions,
zero game constants). The mechanic:

  * the board is a lattice of equal square tiles, all one colour to begin with;
  * one or more tiles instead carry a 3x3 STENCIL drawn at every second pixel;
  * the stencil's centre pixel names the MARKER colour a click paints with;
  * each stencil cell says what its neighbour must be — the marker, or the other colour.

⛔ Nothing here is written down: not the tile size, not the pitch, not which ink means
"paint", not the palette. Every one of those is derived, because a constant recovered by hand
does not transfer to a private game, which is the entire point of the generic-tool track.

The three derivations that are easy to get wrong, each of which DID fail a measurement first:

  * a coloured FRAME touches every tile, so plain connected components return the whole board
    as one blob — `_peel` treats a component far larger than its siblings as a container;
  * two unrelated panels can sit 2 pixels apart, so the lattice step is the COMMONEST gap
    between origins, never the smallest;
  * the ink -> role code cannot be guessed from ink frequency (both inks appear exactly four
    times on ft09 level 1). It is read off the solved panels drawn beside the live board, and
    then CARRIED, because the next level ships no worked example at all.

Full failure ledger: `.wiki/wiki/rounds/r101_tool-development.md`.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, frame_2d, has_frame

__all__ = ["StencilTool", "tiles", "all_tiles", "read_code", "plan"]

Grid = Any
Cell = tuple[int, int]


def _components(g: Grid, blocked: set[int]) -> list[list[Cell]]:
    n = len(g)
    seen = [[False] * n for _ in range(n)]
    out: list[list[Cell]] = []
    for y in range(n):
        for x in range(n):
            if int(g[y][x]) in blocked or seen[y][x]:
                continue
            stack = [(y, x)]
            seen[y][x] = True
            cells: list[Cell] = []
            while stack:
                cy, cx = stack.pop()
                cells.append((cy, cx))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < n and 0 <= nx < n and not seen[ny][nx] and int(g[ny][nx]) not in blocked:
                        seen[ny][nx] = True
                        stack.append((ny, nx))
            out.append(cells)
    return out


def _peel(g: Grid, comps: list[list[Cell]], blocked: set[int]) -> list[tuple[list[Cell], bool]]:
    """A component far larger than its siblings is a CONTAINER; drop its colour and re-split.

    The flag says whether a piece came out of a container, and that is not bookkeeping: a game
    that frames one panel is saying which panel is live, and on ft09 a click on a dead panel is
    an out-of-board click, which resets the level.
    """
    if len(comps) < 2:
        return [(c, False) for c in comps]
    sizes = sorted(len(c) for c in comps)
    typical = sizes[len(sizes) // 2]
    out: list[tuple[list[Cell], bool]] = []
    for c in comps:
        if len(c) <= 4 * typical:
            out.append((c, False))
            continue
        wall = Counter(int(g[y][x]) for y, x in c).most_common(1)[0][0]
        inner = {(y, x) for y, x in c}
        masked = [
            [int(g[y][x]) if (y, x) in inner and int(g[y][x]) != wall else -1 for x in range(len(g))]
            for y in range(len(g))
        ]
        sub = _components(masked, blocked | {-1, wall})
        out.extend([(s, True) for s in sub] if sub else [(c, False)])
    return out


def _square_blocks(g: Grid) -> dict[Cell, dict[str, Any]]:
    bg = Counter(int(v) for row in g for v in row).most_common(1)[0][0]
    found: dict[Cell, dict[str, Any]] = {}
    for c, framed in _peel(g, _components(g, {bg}), {bg}):
        y0 = min(q[0] for q in c)
        x0 = min(q[1] for q in c)
        h = max(q[0] for q in c) - y0 + 1
        w = max(q[1] for q in c) - x0 + 1
        if h != w or h < 4 or len(c) != h * w:
            continue
        found[(y0, x0)] = {"size": h, "colours": {int(g[y][x]) for y, x in c}, "framed": framed}
    if not found:
        return {}
    side = Counter(t["size"] for t in found.values()).most_common(1)[0][0]
    return {o: t for o, t in found.items() if t["size"] == side}


def all_tiles(g: Grid) -> dict[Cell, dict[str, Any]]:
    """Every equal tile on screen — the worked examples live in the panels that are not live."""
    return _square_blocks(g)


def tiles(g: Grid) -> dict[Cell, dict[str, Any]]:
    """Only the tiles of the LIVE board, when the game frames one."""
    kept = _square_blocks(g)
    live = {o: t for o, t in kept.items() if t["framed"]}
    return live or kept


def pitch(origins: list[Cell], side: int = 0) -> int:
    """The lattice step is the COMMONEST gap between origins, never the smallest."""
    gaps: list[int] = []
    for axis in (0, 1):
        vals = sorted({o[axis] for o in origins})
        gaps += [b - a for a, b in zip(vals, vals[1:]) if b - a >= side]
    return Counter(gaps).most_common(1)[0][0] if gaps else 0


def _stencil(g: Grid, origin: Cell) -> tuple[int, list[list[int]]]:
    y0, x0 = origin
    return int(g[y0 + 2][x0 + 2]), [[int(g[y0 + 2 * i][x0 + 2 * j]) for j in range(3)] for i in range(3)]


def read_code(g: Grid, board: dict[Cell, dict[str, Any]], step: int) -> dict[int, bool]:
    """Learn ink -> ROLE (carries the marker / does not) from the solved panels on screen.

    A panel counts as worked only when its ink -> colour map is ONE-TO-ONE: an untouched board
    maps every ink to the blank colour, which is a map that carries no code. The role is stored,
    never the colour — ft09 paints in 8 on level 1 and in 12 on level 2.
    """
    votes: Counter[tuple[int, bool]] = Counter()
    for origin, tile in board.items():
        if len(tile["colours"]) == 1:
            continue
        marker, ink = _stencil(g, origin)
        y0, x0 = origin
        seen: dict[int, set[int]] = {}
        for i in range(3):
            for j in range(3):
                if (i, j) == (1, 1):
                    continue
                nb = board.get((y0 + (i - 1) * step, x0 + (j - 1) * step))
                if nb is None or len(nb["colours"]) != 1:
                    continue
                seen.setdefault(ink[i][j], set()).add(next(iter(nb["colours"])))
        if len(seen) < 2 or any(len(v) != 1 for v in seen.values()):
            continue
        if len({next(iter(v)) for v in seen.values()}) < len(seen):
            continue
        for k, v in seen.items():
            votes[(k, next(iter(v)) == marker)] += 1
    out: dict[int, bool] = {}
    for (k, role), _ in votes.most_common():
        out.setdefault(k, role)
    return out


def plan(g: Grid, code: dict[int, bool] | None = None) -> tuple[list[Cell], dict[int, bool]]:
    """Every click the live stencils call for, plus the code in force."""
    board = tiles(g)
    if not board:
        return [], code or {}
    side = next(iter(board.values()))["size"]
    step = pitch(list(board), side)
    if step <= 0:
        return [], code or {}
    every = all_tiles(g)
    code = read_code(g, every, pitch(list(every), side) or step) or (code or {})
    if not code:
        return [], code
    palette = {next(iter(t["colours"])) for t in board.values() if len(t["colours"]) == 1}
    clicks: list[Cell] = []
    for origin, tile in board.items():
        if len(tile["colours"]) == 1:
            continue
        marker, ink = _stencil(g, origin)
        rest = sorted(palette - {marker}) or sorted(palette)
        if not rest:
            continue
        other = rest[0]
        y0, x0 = origin
        for i in range(3):
            for j in range(3):
                if (i, j) == (1, 1):
                    continue
                role = code.get(ink[i][j])
                if role is None:
                    continue
                # A stencil states BOTH halves. Levels that start uniform only ever exercise
                # "paint this"; a level that starts mixed also needs "this must NOT be painted".
                want = marker if role else other
                nb = board.get((y0 + (i - 1) * step, x0 + (j - 1) * step))
                if nb is None or len(nb["colours"]) != 1 or nb["colours"] == {want}:
                    continue
                clicks.append((y0 + (i - 1) * step + 2, x0 + (j - 1) * step + 2))
    return sorted(set(clicks)), code


class StencilTool:
    """Harness tool wrapping the stencil mechanic."""

    name = "stencil"

    def __init__(self) -> None:
        self._code: dict[int, bool] = {}

    def detect(self, frames: list[Any], obs: Any) -> float:
        if not has_frame(obs):
            return 0.0
        g = frame_2d(obs)
        board = tiles(g)
        if len(board) < 4:
            return 0.0
        marked = [o for o, t in board.items() if len(t["colours"]) > 1]
        if not marked:
            return 0.0
        clicks, _ = plan(g, self._code)
        return 0.9 if clicks else 0.4

    def reset(self) -> None:
        """The ink code survives a level change — the game teaches it once and then stops."""

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Stateless: the plan is recomputed from each frame, so nothing accumulates here."""

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        clicks, self._code = plan(frame_2d(obs), self._code)
        # One click at a time. The frame after a level-up still shows the board just finished,
        # so a batch computed once runs the previous level's plan against the next level's board.
        return [(6, (x, y)) for y, x in clicks[:1]]
