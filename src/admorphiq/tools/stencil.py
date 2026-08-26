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

from admorphiq.tools.base import Step, frame_2d, has_frame, levels_completed
from admorphiq.tools.segment import (
    square_regions,
)

__all__ = ["StencilTool", "tiles", "all_tiles", "read_code", "plan"]

Grid = Any
Cell = tuple[int, int]


def all_tiles(g: Grid) -> dict[Cell, dict[str, Any]]:
    """Every equal tile on screen — the worked examples live in the panels that are not live."""
    return square_regions(g)


def tiles(g: Grid) -> dict[Cell, dict[str, Any]]:
    """Only the tiles of the LIVE board, when the game frames one."""
    kept = square_regions(g)
    live = {o: t for o, t in kept.items() if t["framed"]}
    return live or kept


def pitch(origins: list[Cell], side: int = 0) -> int:
    """The lattice step is the COMMONEST gap between origins, never the smallest."""
    gaps: list[int] = []
    for axis in (0, 1):
        vals = sorted({o[axis] for o in origins})
        gaps += [b - a for a, b in zip(vals, vals[1:]) if b - a >= side]
    return Counter(gaps).most_common(1)[0][0] if gaps else 0


def _stencil(g: Grid, origin: Cell) -> tuple[int, list[list[int]]] | None:
    """The marker and the 3x3 ink, or None when this tile is decorated rather than instructing.

    The discriminator is that a stencil's CENTRE colour appears exactly once among its nine
    sample points. Measured on ft09 level 5, which carries three identical
    `[[14,6,14],[6,14,6],[14,6,14]]` checkerboard tiles: read as stencils they taught the code
    two extra inks (6 -> paint, 14 -> leave) that no real stencil uses, and the level planned
    nothing. A real marker names one cell — itself.
    """
    y0, x0 = origin
    ink = [[int(g[y0 + 2 * i][x0 + 2 * j]) for j in range(3)] for i in range(3)]
    marker = ink[1][1]
    if sum(row.count(marker) for row in ink) != 1:
        return None
    return marker, ink


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
        read = _stencil(g, origin)
        if read is None:
            continue
        marker, ink = read
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
    reads = {o: _stencil(g, o) for o in board}
    markers = {r[0] for r in reads.values() if r is not None}
    demands: dict[Cell, set[int]] = {}
    clicks: list[Cell] = []
    for origin, tile in board.items():
        if len(tile["colours"]) == 1:
            continue
        read = reads[origin]
        if read is None:
            continue
        marker, ink = read
        # "The other colour" comes from the tiles when they show two states. Only when every
        # plain tile is the SAME colour — ft09 level 5 starts all-14 while its stencils name 14
        # and 15 — do the markers supply it; reading markers first regressed level 4, which has
        # a two-colour palette that already answers the question.
        rest = sorted(palette - {marker}) or sorted(markers - {marker}) or sorted(palette)
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
                at = (y0 + (i - 1) * step, x0 + (j - 1) * step)
                nb = board.get(at)
                if nb is None or nb["colours"] == {want}:
                    continue
                if _stencil(g, at) is not None:
                    continue                           # a stencil instructs; it is not painted
                # A patterned neighbour that is not a stencil is an UNRESOLVED tile, and the
                # stencil beside it says what it must become. Measured on ft09 level 5, where
                # every stencil was already satisfied and the only work left sat in three
                # checkerboard tiles that the earlier "plain neighbours only" rule skipped.
                demands.setdefault(at, set()).add(want)
                clicks.append((at[0] + 2, at[1] + 2))
    # ⛔ Refuse to act on a model that contradicts itself. Two stencils demanding different
    # colours for one tile means the neighbourhood reading is wrong for this board, and on ft09
    # a wrong click COSTS A LEVEL — measured, 4 -> 3 on one click and 4 -> 0 over a run. Silence
    # keeps what is already won; guessing spends it.
    if any(len(v) > 1 for v in demands.values()):
        return [], code
    return sorted(set(clicks)), code


class StencilTool:
    """Harness tool wrapping the stencil mechanic."""

    name = "stencil"

    def __init__(self) -> None:
        self._code: dict[int, bool] = {}
        self._level: int | None = None
        self._seen: set[str] = set()

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
        """The ink code survives a level change — the game teaches it once and then stops.

        The visited-state set does not: a new board revisits nothing.
        """
        self._seen = set()

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Stateless: the plan is recomputed from each frame, so nothing accumulates here."""

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        level = levels_completed(obs)
        if level != self._level:
            self._level = level
            self.reset()
        g = frame_2d(obs)
        # ⛔ Stop on a REVISITED board. A demand count that fails to fall is not the signal —
        # one click can retire one stencil's demand while breaking a neighbour's, and requiring
        # a strict decrease killed level 4, which legitimately plateaus. A repeated state is
        # unambiguous: the plan is cycling. On ft09 that matters because clicking on regardless
        # burned 130 actions at level 5 and lost every level already won (4 -> 0).
        # Hash the TILE MAP, not the frame: ft09 marches an action counter one pixel per
        # action, so a whole-frame hash is unique every step and never detects anything.
        stamp = repr(sorted((o, sorted(v["colours"])) for o, v in tiles(g).items()))
        if stamp in self._seen:
            return []
        self._seen.add(stamp)
        clicks, self._code = plan(g, self._code)
        # One click at a time. The frame after a level-up still shows the board just finished,
        # so a batch computed once runs the previous level's plan against the next level's board.
        return [(6, (x, y)) for y, x in clicks[:1]]
