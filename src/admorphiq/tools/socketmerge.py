"""Vacuum-merge boards: pull like pieces together, then park them in the sockets.

RECOVERED MECHANIC (measured on a live sample board, 2026-08-27). A click inside the
playfield opens a short vacuum: every piece whose bounding box lies within a fixed reach
of the click is dragged so that its CENTRE lands exactly on the clicked cell. Pieces that
land on top of each other and are the SAME size fuse into one piece of the next size up;
pieces of DIFFERENT sizes that land together are rejected — the board flashes, the move is
undone and the step budget is docked (2, then 4, then 6...). A level is won when each
socket printed on the board holds a piece, and the boards are built so that fusing
everything down to as many pieces as there are sockets produces exactly the pieces wanted.

Three measurements shape the code and none of them were guessable from a still frame:

* One vacuum costs TWO agent actions. The click returns the pre-vacuum frame; the board
  only settles on the next action. The filler is aimed into the header, where clicks are
  measured to be inert, so it costs an action but not a step.
* The reach is not printed anywhere, so it is LEARNED: the tool aims a little further out
  each time a drag lands, and once a vacuum is ignored it halves what is left between the
  proven reach and the ignored one. Every probe that lands is also a real move, so the
  whole game pays about two wasted vacuums to know the reach exactly.
* Mixing sizes in one vacuum is punished, so every click is checked against the whole
  board first and rejected if it would sweep up a piece of another size.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, connected_components, frame_2d, has_frame
from admorphiq.tools.segment import background

__all__ = ["SocketMergeTool"]

# How far the reach estimate is allowed to run ahead of what has been proven, both when
# growing it (+_GROW per successful drag) and when guessing which pieces a click might
# sweep up before any ceiling is known (+_SLACK). Small because an over-estimate on the
# sweep test only costs a detour, while an under-estimate costs a docked budget.
_GROW = 2
_SLACK = 6
# Hazards are drawn as speckled patterns that 4-connectivity shatters into single cells;
# diagonal neighbours weld them back into one object. Kept at 1 deliberately: at 2 the
# dotted guide line on one sample board fuses into a single 43-cell "object".
_WELD = 1


@dataclass(frozen=True)
class _Piece:
    """A solid square of a playable colour: x/y are its top-left cell, side its width."""

    x: int
    y: int
    side: int
    colour: int

    @property
    def cx(self) -> int:
        # The engine's own centre convention, recovered from where a dragged piece lands.
        return self.x + self.side // 2

    @property
    def cy(self) -> int:
        return self.y + self.side // 2


def _weld(cells: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    """8-connected groups: the speckle patterns are only ever diagonally joined."""
    live = set(cells)
    out: list[set[tuple[int, int]]] = []
    while live:
        seed = live.pop()
        group = {seed}
        frontier = [seed]
        while frontier:
            cy, cx = frontier.pop()
            touch = {c for c in live if abs(c[0] - cy) <= 1 and abs(c[1] - cx) <= 1}
            live -= touch
            group |= touch
            frontier.extend(touch)
        out.append(group)
    return out


@dataclass(frozen=True)
class _Blob:
    """A hazard: an object that is not a piece and has been seen to move."""

    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def cx(self) -> int:
        return (self.x0 + self.x1) // 2

    @property
    def cy(self) -> int:
        return (self.y0 + self.y1) // 2


@dataclass(frozen=True)
class _Board:
    pieces: tuple[_Piece, ...]
    sockets: tuple[tuple[int, int], ...]  # centre of each socket
    hazards: tuple[_Blob, ...]
    top: int  # first playable row
    bottom: int  # last playable row


def _gap(px: int, py: int, x0: int, y0: int, x1: int, y1: int) -> float:
    """Distance from a clicked cell to the nearest cell of a box (0 if inside it)."""
    dx = max(x0 - px, 0, px - x1)
    dy = max(y0 - py, 0, py - y1)
    return float(dx * dx + dy * dy) ** 0.5


def _bbox_gap(px: int, py: int, p: _Piece) -> float:
    return _gap(px, py, p.x, p.y, p.x + p.side - 1, p.y + p.side - 1)


class SocketMergeTool:
    """Fuse the board down to one piece per socket, then deliver them."""

    name = "socketmerge"

    def __init__(self) -> None:
        # Reach is a property of the game, not of the level, so it survives reset().
        self._reach = 1
        self._reach_ceiling: int | None = None
        self._probing = True
        self.reset()

    def reset(self) -> None:
        self._palette: frozenset[int] | None = None
        self._sockets: tuple[tuple[int, int], ...] = ()
        self._pending: tuple[np.ndarray, int] | None = None  # (frame at click, gap aimed at)
        self._last_hash: int | None = None
        self._blocked: set[tuple[int, int]] = set()
        self._ever: set[tuple[int, int]] | None = None
        self._marks: list[tuple[int, int]] = []
        self._haz_step = 0
        self._idle = 0

    # --- perception ---------------------------------------------------------

    def _read(self, g: np.ndarray) -> _Board | None:
        """Cut the frame into playable squares and sockets, or return None if it is not one."""
        h, w = g.shape
        bg = background(g)
        top = self._header_rows(g, bg)
        if top <= 0 or top >= h - 2:
            return None
        # The board's last row carries an edge-pinned budget bar; it is never content.
        bottom = h - 2

        if self._palette is None:
            header = g[:top]
            chrome = int(np.bincount(g[0].astype(int)).argmax())
            self._palette = frozenset(int(c) for c in np.unique(header)) - {chrome} - bg
        if not self._palette:
            return None

        blank = -9
        masked = np.full_like(g, blank)
        masked[top:bottom + 1] = g[top:bottom + 1]
        for c in bg:
            masked[masked == c] = blank

        pieces: list[_Piece] = []
        sockets: list[tuple[int, int]] = []
        other: set[tuple[int, int]] = set()
        for comp in connected_components(masked, background=blank):
            y0, x0, y1, x1 = comp["bbox"]
            side = y1 - y0 + 1
            square = (x1 - x0 + 1) == side
            if square and comp["size"] == side * side and int(comp["color"]) in self._palette:
                pieces.append(_Piece(x0, y0, side, int(comp["color"])))
                continue
            # A socket is printed as a disc: a square footprint with its corners cut away.
            # Solid is what separates it from decoration — one sample board parks a solid
            # decoy square of a non-playable colour inside a socket, and without the strict
            # inequality that decoy is read as a second socket to fill.
            if (
                square
                and side >= 3
                and 0.6 * side * side <= comp["size"] < side * side
                and int(comp["color"]) not in self._palette
            ):
                sockets.append((x0 + side // 2, y0 + side // 2))
                continue
            other.update(comp["cells"])

        # Sockets are remembered from the first clean read: a delivered piece overlaps the
        # socket it fills and would erase it from the next frame's segmentation.
        if sockets:
            self._sockets = tuple(sorted(sockets))
        if not self._sockets or not pieces:
            return None
        return _Board(tuple(pieces), self._sockets, self._hazards(other), top, bottom)

    def _hazards(self, other: set[tuple[int, int]]) -> tuple[_Blob, ...]:
        """Whatever is neither piece nor socket AND has been seen to move.

        Motion is the only honest separator here: one sample board draws a dotted guide
        line straight along the route a piece must travel, and treating those dots as
        hazards refuses every useful click. The test is "has this object entered ground no
        object has ever stood on", not "did it differ from last frame" — MEASURED, because
        a piece sliding over the guide line erases and restores those dots, and a
        frame-to-frame test read the restored dots as a swarm of movers and burned a whole
        level's budget shoving scenery.
        """
        blobs = _weld(other)
        if self._ever is None:  # first read of the level: nothing has moved yet
            self._ever = set(other)
            self._marks = []
            return ()
        fresh = other - self._ever
        self._ever |= other
        out: list[_Blob] = []
        marks: list[tuple[int, int]] = []
        for cells in blobs:
            ys = [c[0] for c in cells]
            xs = [c[1] for c in cells]
            blob = _Blob(min(xs), min(ys), max(xs), max(ys))
            # Freshly covered ground identifies a mover; a remembered one stays identified
            # even on a turn it happens to retrace its own steps.
            near = any(_gap(mx, my, blob.x0, blob.y0, blob.x1, blob.y1) <= _WELD
                       for mx, my in self._marks)
            if not (cells & fresh or near):
                continue
            out.append(blob)
            marks.append((blob.cx, blob.cy))
            # How fast a hazard closes is a fact about the game, so it is measured off its
            # own tracks rather than assumed, and it is what "too close" is counted in.
            for mx, my in self._marks:
                d = max(abs(mx - blob.cx), abs(my - blob.cy))
                if d <= 2 * _WELD + self._reach:
                    self._haz_step = max(self._haz_step, d)
        self._marks = marks
        return tuple(out)

    @staticmethod
    def _header_rows(g: np.ndarray, bg: set[int]) -> int:
        """Rows of the top header, found by its own colour rather than by its height.

        The header is not simply "the rows without background" — it prints a legend on a
        background-coloured strip. What separates it is that its own colour is used
        nowhere on the board, so the header ends at the first row that colour does not touch.
        """
        chrome = int(np.bincount(g[0].astype(int)).argmax())
        if chrome in bg:
            return 0
        y = 0
        while y < g.shape[0] and bool((g[y] == chrome).any()):
            y += 1
        return y

    # --- click geometry -----------------------------------------------------

    def _sweep(self, board: _Board, px: int, py: int, radius: float) -> list[_Piece]:
        return [p for p in board.pieces if _bbox_gap(px, py, p) <= radius]

    @staticmethod
    def _corner(p: _Piece, px: int, py: int, board: _Board, w: int, h: int) -> tuple[int, int]:
        """Where a swept piece ends up: centred on the click, clamped to the playfield."""
        x = min(max(px - p.side // 2, 0), w - p.side)
        y = min(max(py - p.side // 2, board.top), min(board.bottom, h - p.side))
        return x, y

    def _land(self, p: _Piece, px: int, py: int, board: _Board, w: int, h: int) -> tuple[int, int]:
        x, y = self._corner(p, px, py, board, w, h)
        return x + p.side // 2, y + p.side // 2

    def _clicks_for(
        self, board: _Board, movers: list[_Piece], w: int, h: int, clear: bool = True
    ) -> list[tuple[int, int, tuple[int, int]]]:
        """Every legal click that sweeps up `movers` and nothing of another size.

        Returns (x, y, landing centre of movers[0]). The filters are the whole reason this
        is a search and not a formula: a vacuum that mixes sizes is docked and undone, and
        one that gathers a third equal piece silently burns it.
        With `clear`, clicks that would also drag a hazard onto the pieces are dropped —
        the hazard cannot strike during the vacuum that carries it, but it lands on top of
        its victim and strikes on the next one.
        """
        side = movers[0].side
        guess = self._reach_ceiling - 1 if self._reach_ceiling else self._reach + _SLACK
        want = {(p.x, p.y) for p in movers}
        span = self._reach + max(p.side for p in movers) + 1
        out: list[tuple[int, int, tuple[int, int]]] = []
        for px in range(max(0, movers[0].cx - span), min(w, movers[0].cx + span + 1)):
            for py in range(max(board.top, movers[0].cy - span), min(board.bottom + 1, movers[0].cy + span + 1)):
                if any(_bbox_gap(px, py, m) > self._reach for m in movers):
                    continue
                if clear and any(_gap(px, py, z.x0, z.y0, z.x1, z.y1) <= guess for z in board.hazards):
                    continue
                swept = self._sweep(board, px, py, guess)
                if any(q.side != side for q in swept):
                    continue
                # EXACTLY the intended pieces, never a superset. MEASURED: a vacuum that
                # gathers THREE equal pieces fuses the whole group into a SINGLE next-size
                # piece, so the third is swallowed for nothing and the board's total — which
                # the level's target is cut from exactly — is short by one for good.
                if want != {(q.x, q.y) for q in swept}:
                    continue
                out.append((px, py, self._land(movers[0], px, py, board, w, h)))
        return out

    def _shove(self, board: _Board, w: int, h: int) -> tuple[int, int] | None:
        """Vacuum the closest hazard away from the pieces, if one is closing in.

        A hazard walks toward the nearest piece every vacuum and knocks a step off whatever
        it reaches; the boards carry exactly enough material, so one strike loses the level
        outright. The vacuum drags a hazard the same way it drags a piece, which makes
        shoving it the only lever. How close is too close is counted in the hazard's own
        measured strides, so a faster hazard is given a wider berth without being told.
        """
        if not board.hazards:
            return None

        def spread(x: int, y: int) -> float:
            return min(((x - p.cx) ** 2 + (y - p.cy) ** 2) ** 0.5 for p in board.pieces)

        z = min(board.hazards, key=lambda b: spread(b.cx, b.cy))
        best_d = spread(z.cx, z.cy)
        if best_d > self._danger():
            return None
        best: tuple[int, int] | None = None
        for px in range(max(0, z.cx - self._reach - 3), min(w, z.cx + self._reach + 4)):
            for py in range(max(board.top, z.cy - self._reach - 3), min(board.bottom + 1, z.cy + self._reach + 4)):
                if _gap(px, py, z.x0, z.y0, z.x1, z.y1) > self._reach:
                    continue
                if self._sweep(board, px, py, self._reach):
                    continue  # never drag a piece along with the hazard
                got = spread(px, py)
                if got > best_d:
                    best_d, best = got, (px, py)
        return best

    # --- planning -----------------------------------------------------------

    def _plan(self, board: _Board, w: int, h: int) -> tuple[int, int] | None:
        pieces = sorted(board.pieces, key=lambda p: (-p.side, p.x, p.y))
        n_sock = len(board.sockets)

        work = None
        if len(pieces) > n_sock:
            work = self._fuse(board, pieces, w, h)
        if work is None:
            work = self._deliver(board, pieces, w, h)
        shove = self._shove(board, w, h)
        if shove is None or (work is not None and self._escapes(board, work, w, h)):
            return work
        return shove

    def _escapes(self, board: _Board, click: tuple[int, int], w: int, h: int) -> bool:
        """Would the useful move ITSELF carry the threatened piece out of danger?

        Without this the tool alternates shove, work, shove, work while a hazard chases a
        piece that the next fuse was going to move away anyway — half the level's budget
        spent re-establishing a gap the work would have opened for free.
        """
        moved = {(p.x, p.y) for p in self._sweep(board, click[0], click[1], self._reach)}
        after = [
            _Piece(*self._corner(p, click[0], click[1], board, w, h), p.side, p.colour)
            if (p.x, p.y) in moved else p
            for p in board.pieces
        ]
        return all(
            min(((z.cx - p.cx) ** 2 + (z.cy - p.cy) ** 2) ** 0.5 for p in after) > self._danger()
            for z in board.hazards
        )

    def _danger(self) -> float:
        """How close a hazard may come before a vacuum has to be spent on it.

        Two of its own strides: one to close the gap while the current vacuum plays out and
        one of margin. The stride is measured off the hazard's tracks, so a faster hazard
        widens its own danger zone; until one has been seen move, the reach stands in.
        """
        return 2.0 * (self._haz_step or self._reach)

    def _fuse(self, board: _Board, pieces: list[_Piece], w: int, h: int) -> tuple[int, int] | None:
        """Bring the closest matching pair together, whichever size they are.

        Order does not change the outcome — fusing two of size k always trades them for one
        of size k+1, so the board always ends on the same set of pieces however it gets
        there — which frees the choice to be about COST. Cost is vacuums, each of which is
        two actions and one step, so the closest pair wins.
        """
        by_side: dict[int, list[_Piece]] = {}
        for p in pieces:
            by_side.setdefault(p.side, []).append(p)
        pairs = [
            (a, b)
            for group in by_side.values()
            if len(group) >= 2
            for i, a in enumerate(group)
            for b in group[i + 1:]
        ]
        pairs.sort(key=lambda ab: (ab[0].cx - ab[1].cx) ** 2 + (ab[0].cy - ab[1].cy) ** 2)
        for a, b in pairs:
            if (a.x, a.y, b.x, b.y) in self._blocked:
                continue
            # A fused piece appears exactly where the vacuum pulled its parents, so of
            # all the clicks that take both, take the one nearest a socket.
            joint = self._clicks_for(board, [a, b], w, h) or self._clicks_for(board, [a, b], w, h, clear=False)
            if joint:
                sx, sy = self._nearest_socket(board, a)
                px, py, _ = min(joint, key=lambda c: (c[0] - sx) ** 2 + (c[1] - sy) ** 2)
                return px, py
            # Too far apart: walk the one further from the socket toward the other.
            sx, sy = self._nearest_socket(board, a)
            far, near = sorted((a, b), key=lambda p: -((p.cx - sx) ** 2 + (p.cy - sy) ** 2))
            step = self._walk(board, far, (near.cx, near.cy), w, h)
            if step is not None:
                return step
            step = self._walk(board, near, (far.cx, far.cy), w, h)
            if step is not None:
                return step
            self._blocked.add((a.x, a.y, b.x, b.y))
        return None

    def _deliver(self, board: _Board, pieces: list[_Piece], w: int, h: int) -> tuple[int, int] | None:
        free = list(board.sockets)
        for p in pieces:  # already sorted biggest first
            if not free:
                return None
            sx, sy = min(free, key=lambda s: (s[0] - p.cx) ** 2 + (s[1] - p.cy) ** 2)
            free.remove((sx, sy))
            if (p.cx, p.cy) == (sx, sy):
                continue  # already parked; move on to the next socket
            step = self._walk(board, p, (sx, sy), w, h)
            if step is not None:
                return step
        return None

    def _walk(
        self, board: _Board, p: _Piece, target: tuple[int, int], w: int, h: int
    ) -> tuple[int, int] | None:
        """One vacuum that drags `p` as close to `target` as the reach allows."""
        here = (p.cx - target[0]) ** 2 + (p.cy - target[1]) ** 2
        best: tuple[int, int] | None = None
        best_d = here
        options = self._clicks_for(board, [p], w, h) or self._clicks_for(board, [p], w, h, clear=False)
        for px, py, (nx, ny) in options:
            d = (nx - target[0]) ** 2 + (ny - target[1]) ** 2
            if d < best_d:
                best_d, best = d, (px, py)
        return best

    @staticmethod
    def _nearest_socket(board: _Board, p: _Piece) -> tuple[int, int]:
        return min(board.sockets, key=lambda s: (s[0] - p.cx) ** 2 + (s[1] - p.cy) ** 2)

    # --- Tool protocol ------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Non-zero only when this frame really is a vacuum-merge board with a plan.

        Every clause is a thing the board must SHOW: a header in a colour the playfield
        never uses, at least one socket printed as a corner-cut disc, at least one solid
        square in a header colour, and a legal click that advances them. A board that fails
        any of these is left to another tool rather than bid on cheaply — measured on the
        sample set, this fires on exactly one game and withdraws from the other 24.
        """
        if not has_frame(obs):
            return 0.0
        g = frame_2d(obs)
        if g.ndim != 2 or g.shape[0] != g.shape[1]:
            return 0.0
        keep = (self._palette, self._sockets, self._ever, self._marks, self._haz_step)
        self._palette, self._sockets, self._ever, self._marks = None, (), None, []
        try:
            board = self._read(g)
            if board is None or len(board.pieces) < 1:
                return 0.0
            h, w = g.shape
            if self._plan(board, w, h) is None:
                return 0.0
            # Distinct sizes on the board mean a ladder is in play, which is this family's
            # signature; a single size could be any click game and scores lower.
            sizes = {p.side for p in board.pieces}
            return 0.9 if len(board.pieces) > len(board.sockets) or len(sizes) > 1 else 0.6
        finally:
            (self._palette, self._sockets, self._ever, self._marks, self._haz_step) = keep

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Nothing is learned here: the reach test needs the SETTLED board, which arrives
        an action later than this callback, so it is done in propose against a kept frame."""

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        g = frame_2d(obs)
        digest = hash(g.tobytes())
        if digest == self._last_hash:
            # The vacuum has not resolved yet: the click returned the pre-vacuum frame.
            # Spend an action in the header, where a click is measured to be inert.
            self._idle += 1
            return [] if self._idle > 12 else [(6, (0, 0))]
        self._last_hash = digest
        self._idle = 0

        board = self._read(g)
        if board is None:
            self._pending = None
            return [(6, (0, 0))]
        h, w = g.shape

        # Reach learning, against the settled board rather than the click's own reply: a
        # drag that landed proves the gap it was aimed at, one that did nothing caps it.
        if self._pending is not None:
            before, gap = self._pending
            self._pending = None
            band = slice(board.top, board.bottom + 1)
            if bool((before[band] != g[band]).any()):
                self._reach = max(self._reach, gap)
            elif self._probing:
                self._reach_ceiling = min(self._reach_ceiling or gap, gap)

        # Reach is learned in two phases: step out by _GROW until a vacuum is ignored,
        # then halve the remaining gap until the proven value and the ignored one are
        # adjacent. Every probe but the failures is a real move, so this is nearly free.
        self._probing = self._reach_ceiling is None or self._reach < self._reach_ceiling - 1
        if self._reach_ceiling is None:
            gap = self._reach + _GROW
        elif self._probing:
            gap = (self._reach + self._reach_ceiling) // 2
        else:
            gap = self._reach
        old, self._reach = self._reach, gap
        try:
            move = self._plan(board, w, h)
        finally:
            self._reach = old
        if move is None:
            self._blocked.clear()
            return [(6, (0, 0))]
        self._pending = (g.copy(), gap)
        return [(6, move), (6, (0, 0))]
