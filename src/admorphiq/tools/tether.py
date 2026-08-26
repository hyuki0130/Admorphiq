"""Drag tethered weights until each cluster's balance point sits on its own marker.

The mechanic this recovers, in frame terms only. A board carries three kinds of small
diamond-family glyph, all built on the same lattice: a WEIGHT (a solid diamond whose body
is one flat colour around a single differently-coloured pip), a BODY (a larger solid diamond
carrying several colours), and a MARKER (a hollow diamond ring, one size larger again, drawn
in the very colours some body carries). Clicking a weight picks it up; clicking anywhere else
drops the held weight so its pip lands on the clicked cell. Nothing else on the board responds
to a click.

The BODY is not clickable and never dragged. It is pinned to the arithmetic mean of the pips
of the weights that belong to it, floor-divided, and it re-pins the instant one of them lands.
So the whole board is a set of independent little levers: to put a body on its marker, place
its weights so their mean is the marker's centre. That relation is also how the grouping is
recovered — a body's cell IS the floored mean of its own weights and of no other set, so the
partition is read off the board rather than guessed, and a board where no partition satisfies
it is a board carrying some other mechanic and is declined.

⛔ Which marker belongs to which body is read from COLOUR, not from distance. Measured on the
sample board: markers outnumber bodies almost two to one, the surplus ones are decoys parked
closer to a body than its own marker is, and every real pairing has the marker's outer-arm
colours equal to the body's colours minus its centre pip. Nearest-marker scores that board
completely wrong; the colour identity scores it exactly.

⛔ The outer arms are the only part of a marker that may be read. A body that has arrived
covers a marker's inner ring — the four cells the two shapes share — so a colour set taken
from the whole marker changes the moment the level is won, and a plan that re-reads the board
each turn would stop recognising the thing it had just solved. Only cells the body cannot
reach are used.

⛔ Two regions are hazardous and they are not the same hazard. The BOUNDARY (the colour that
dominates the frame's outer ring) refuses a weight: a drop that would overlap it is swallowed
and the action is spent for nothing. A large interior FIELD instead punishes a BODY that comes
to rest inside it, and the sample board ends the level after five such rests, undoing each
move as it goes. So a weight may be dropped in the field freely, while every resting place a
body passes through — including the one it occupies between the first and second drop of a
two-drop plan — has to be clear of it. Planning one drop at a time cannot see that; the plan
is therefore solved for both drops at once.

Connector strokes are stripped before anything is segmented. The board draws a one-cell line
from each weight to its body over the background, and 8-connectivity happily welds a weight,
its line and its body into one blob, which is what makes a naive segmentation read this board
as three enormous objects. A colour is a stroke when no cell of it has three same-coloured
orthogonal neighbours and at least one of its runs is long and one cell thick.
"""

from __future__ import annotations

from collections import Counter, deque
from typing import Any

import numpy as np

from admorphiq.tools.base import (
    Step,
    availability,
    frame_2d,
    has_frame,
)

__all__ = ["TetherCentroidTool"]

# Glyph sizes are read off the board, not assumed; these bound the search.
_HALVES = (2, 3, 4)
# A region this large is scenery (a field or a wall), never a glyph.
_FIELD_CELLS = 60
# A stroke run must be at least this long before a colour counts as a connector.
_STROKE_RUN = 5


def _settled(obs: Any) -> np.ndarray:
    """The board once the action has finished resolving, not while it is still resolving.

    ⛔ Measured, and it cost a level: an action here renders several frames — the board as the
    click arrived, the drop in flight, and the board it settled into — and the shared reader
    returns the FIRST of them. A plan read off that frame is a plan for the position before
    the previous drop, so re-planning after a clear re-issued the drop that had just cleared
    the level and spent it on the next one. The last frame is the one the next click acts on.
    """
    frames = getattr(obs, "frame", None)
    while isinstance(frames, (list, tuple)) and frames and isinstance(frames[0], (list, tuple)) \
            and frames[0] and isinstance(frames[0][0], (list, tuple)):
        frames = frames[-1]
    arr = np.asarray(frames)
    while arr.ndim > 2:
        arr = arr[-1]
    if arr.ndim != 2 or arr.size == 0:
        return np.asarray(frame_2d(obs))
    return arr.astype(np.int64)


# ── lattice helpers ─────────────────────────────────────────────────────────

def _diamond(radius: int, half: int) -> list[tuple[int, int]]:
    """Offsets of a solid diamond of L1 ``radius``, clipped to a box of ``half``."""
    return [
        (dy, dx)
        for dy in range(-half, half + 1)
        for dx in range(-half, half + 1)
        if abs(dy) + abs(dx) <= radius
    ]


def _ring(radius: int, half: int) -> list[tuple[int, int]]:
    """Offsets of a hollow diamond of L1 ``radius``, clipped to a box of ``half``."""
    return [
        (dy, dx)
        for dy in range(-half, half + 1)
        for dx in range(-half, half + 1)
        if abs(dy) + abs(dx) == radius
    ]


# ── board reading ───────────────────────────────────────────────────────────

def _chrome_colours(g: np.ndarray) -> set[int]:
    """Colours confined to a single edge row or column — a counter, not board content."""
    h, w = g.shape
    out: set[int] = set()
    for colour in {int(v) for v in np.unique(g)}:
        ys, xs = np.where(g == colour)
        if xs.size == 0:
            continue
        one_col = xs.min() == xs.max() and xs[0] in (0, w - 1)
        one_row = ys.min() == ys.max() and ys[0] in (0, h - 1)
        if one_col or one_row:
            out.add(colour)
    return out


def _boundary_colour(g: np.ndarray, bg: int, chrome: set[int]) -> int | None:
    """The colour that dominates the frame's outer ring — the wall a weight cannot enter."""
    h, w = g.shape
    ring = np.concatenate([g[0], g[h - 1], g[:, 0], g[:, w - 1]])
    counts = Counter(int(v) for v in ring if int(v) != bg and int(v) not in chrome)
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def _stroke_colours(g: np.ndarray, bg: int) -> set[int]:
    """Colours drawn as one-cell strokes — the tethers, which must not weld glyphs together."""
    h, w = g.shape
    out: set[int] = set()
    for colour in {int(v) for v in np.unique(g) if int(v) != bg}:
        mask = g == colour
        if mask.sum() < _STROKE_RUN:
            continue
        neigh = np.zeros_like(mask, dtype=np.int16)
        neigh[1:, :] += mask[:-1, :]
        neigh[:-1, :] += mask[1:, :]
        neigh[:, 1:] += mask[:, :-1]
        neigh[:, :-1] += mask[:, 1:]
        if int(neigh[mask].max()) >= 3:
            continue
        if not any(
            len(cells) >= _STROKE_RUN
            and max(
                max(c[0] for c in cells) - min(c[0] for c in cells),
                max(c[1] for c in cells) - min(c[1] for c in cells),
            ) + 1 >= _STROKE_RUN
            for cells in _blobs8(mask)
        ):
            continue
        out.add(colour)
    return out


def _blobs8(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    """8-connected regions of a boolean mask."""
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out: list[list[tuple[int, int]]] = []
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or seen[y, x]:
                continue
            seen[y, x] = True
            cells = [(y, x)]
            q: deque[tuple[int, int]] = deque([(y, x)])
            while q:
                cy, cx = q.popleft()
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            cells.append((ny, nx))
                            q.append((ny, nx))
            out.append(cells)
    return out


class _Board:
    """Everything the plan needs, recovered from one frame."""

    def __init__(self, g: np.ndarray) -> None:
        self.g = g
        h, w = g.shape
        self.h, self.w = h, w
        counts = Counter(int(v) for v in g.ravel())
        self.bg = counts.most_common(1)[0][0]
        chrome = _chrome_colours(g)
        self.boundary = _boundary_colour(g, self.bg, chrome)
        self.strokes = _stroke_colours(g, self.bg)

        drawn = g != self.bg
        for colour in self.strokes | chrome:
            drawn &= g != colour
        self.wall = np.zeros_like(drawn)
        if self.boundary is not None:
            self.wall = g == self.boundary
            drawn &= ~self.wall

        # Scenery: an interior region far larger than any glyph. A body resting in one is
        # punished; a weight dropped in one is not.
        self.field = np.zeros_like(drawn)
        self.field_colours: set[int] = set()
        for colour in {int(v) for v in np.unique(g)}:
            if colour == self.bg or colour in self.strokes or colour == self.boundary:
                continue
            for cells in _blobs8(g == colour):
                if len(cells) >= _FIELD_CELLS:
                    self.field_colours.add(colour)
                    for cy, cx in cells:
                        self.field[cy, cx] = True
        drawn &= ~self.field
        self.piece = drawn

        self.half = 0
        self.weights: list[dict[str, Any]] = []
        self.disks: list[dict[str, Any]] = []
        self.markers: list[dict[str, Any]] = []
        for half in _HALVES:
            weights = self._weights(half)
            disks = self._disks(half)
            markers = self._markers(half)
            if len(weights) >= 2 and disks and markers:
                self.half = half
                self.weights, self.disks, self.markers = weights, disks, markers
                break

    # -- glyph scans ---------------------------------------------------------

    def _weights(self, half: int) -> list[dict[str, Any]]:
        """A solid diamond of one flat colour around a single pip, with clear shoulders."""
        body = [o for o in _diamond(half, half) if o != (0, 0)]
        shoulder = [o for o in _ring(half + 1, half)]
        out = []
        for y in range(half, self.h - half):
            for x in range(half, self.w - half):
                cols = {int(self.g[y + dy, x + dx]) for dy, dx in body}
                if len(cols) != 1:
                    continue
                colour = cols.pop()
                if colour == self.bg or not self.piece[y, x]:
                    continue
                if any(int(self.g[y + dy, x + dx]) == colour for dy, dx in shoulder):
                    continue
                if not all(self.piece[y + dy, x + dx] for dy, dx in body):
                    continue
                out.append({"at": (y, x), "colour": colour, "pip": int(self.g[y, x])})
        return out

    def _disks(self, half: int) -> list[dict[str, Any]]:
        """A solid diamond one size larger, clipped square — every cell drawn.

        Both the bodies and the loose colour tokens they pick up wear this shape; which is
        which is settled later by the tethers, not by anything a single glyph shows.
        """
        cells = _diamond(half + 1, half)
        out = []
        for y in range(half, self.h - half):
            for x in range(half, self.w - half):
                if not all(self.piece[y + dy, x + dx] for dy, dx in cells):
                    continue
                colours = Counter(int(self.g[y + dy, x + dx]) for dy, dx in cells)
                pip = int(self.g[y, x])
                out.append({
                    "at": (y, x),
                    "colours": set(colours) - ({pip} if colours[pip] == 1 else set()),
                    "cells": [(y + dy, x + dx) for dy, dx in cells],
                })
        return out

    def _markers(self, half: int) -> list[dict[str, Any]]:
        """A hollow diamond ring one size larger again — the place a body must reach."""
        ring = _ring(half + 2, half + 1)
        outer = [o for o in ring if max(abs(o[0]), abs(o[1])) == half + 1]
        pad = half + 1
        out = []
        for y in range(pad, self.h - pad):
            for x in range(pad, self.w - pad):
                if not all(self.piece[y + dy, x + dx] for dy, dx in ring):
                    continue
                out.append({
                    "at": (y, x),
                    "colours": {int(self.g[y + dy, x + dx]) for dy, dx in outer},
                    "cells": [(y + dy, x + dx) for dy, dx in ring],
                })
        return out

    # -- derived geometry ----------------------------------------------------

    def drawable(self, cell: tuple[int, int]) -> bool:
        """Whether a tether stroke would have been painted over this cell if one crossed it."""
        v = int(self.g[cell])
        return v == self.bg or v in self.field_colours

    def held(self) -> tuple[int, int] | None:
        """The weight whose body colour is the odd one out — the one a drop would move."""
        if len(self.weights) < 2:
            return None
        tally = Counter(w["colour"] for w in self.weights)
        rare = [w for w in self.weights if tally[w["colour"]] == 1]
        if len(rare) != 1 or tally[rare[0]["colour"]] == len(self.weights):
            return None
        return rare[0]["at"]


def _line(a: tuple[int, int], b: tuple[int, int]) -> list[tuple[int, int]]:
    """Every cell a straight stroke between two centres would touch."""
    y0, x0 = a
    y1, x1 = b
    dy, dx = abs(y1 - y0), abs(x1 - x0)
    sy = 1 if y0 < y1 else -1
    sx = 1 if x0 < x1 else -1
    err = dx - dy
    out = [(y0, x0)]
    while (y0, x0) != (y1, x1):
        step = err << 1
        if step > -dy:
            err -= dy
            x0 += sx
        if step < dx:
            err += dx
            y0 += sy
        out.append((y0, x0))
    return out


def _tethered(board: _Board, weight: tuple[int, int], disk: tuple[int, int]) -> bool:
    """Is this weight strung to this disk?

    The board draws the stroke only where the ground is plain, so the test is not "are there
    stroke cells along the way" but "is there anywhere along the way where a stroke SHOULD be
    showing and is not". That reads through the stretches where the stroke is hidden under
    scenery or another glyph, which a positive-evidence test cannot.
    """
    span = board.half + 1
    seen = looked = 0
    for cell in _line(weight, disk):
        near_end = (abs(cell[0] - weight[0]) <= span and abs(cell[1] - weight[1]) <= span) or (
            abs(cell[0] - disk[0]) <= span and abs(cell[1] - disk[1]) <= span)
        if near_end:
            continue
        looked += 1
        if int(board.g[cell]) in board.strokes:
            seen += 1
        elif board.drawable(cell):
            return False
    # Two glyphs sitting against each other leave no plain ground between them, so there is
    # nowhere for a stroke to show; absence of contradiction is all the evidence there is.
    return seen >= 1 or looked == 0


def _linked(board: _Board) -> dict[tuple[int, int], list[tuple[int, int]]] | None:
    """Weights grouped by the disk each is strung to, verified against the balance rule."""
    if not board.strokes:
        return None
    groups: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for weight in board.weights:
        hits = [d["at"] for d in board.disks if _tethered(board, weight["at"], d["at"])]
        if len(hits) != 1:
            return None
        groups.setdefault(hits[0], []).append(weight["at"])
    for at, members in groups.items():
        if at != _centre(members):
            return None
    return groups


def _partition(board: _Board) -> dict[tuple[int, int], list[tuple[int, int]]] | None:
    """Assign every weight to a body so each body sits on its own floored mean.

    Returns None when no assignment reproduces the board — which is the tool's own proof
    that this mechanic is not the one in front of it.
    """
    found = _linked(board)
    if found is not None:
        return found
    bodies = [b["at"] for b in board.disks]
    weights = [w["at"] for w in board.weights]
    if not bodies or len(weights) < len(bodies):
        return None
    # A weight's pip colour names its body when only one body carries that colour; that
    # collapses the search on every board measured, and a tie just widens it again.
    options: list[list[int]] = []
    for w in board.weights:
        near = [i for i, b in enumerate(board.disks) if w["pip"] in b["colours"]]
        options.append(near if near else list(range(len(bodies))))
    best: dict[tuple[int, int], list[tuple[int, int]]] | None = None
    budget = [200_000]

    def walk(i: int, groups: list[list[tuple[int, int]]]) -> bool:
        nonlocal best
        budget[0] -= 1
        if budget[0] <= 0:
            return True
        if i == len(weights):
            for bi, members in enumerate(groups):
                if not members:
                    return False
                by, bx = bodies[bi]
                if by != sum(m[0] for m in members) // len(members):
                    return False
                if bx != sum(m[1] for m in members) // len(members):
                    return False
            best = {bodies[bi]: list(members) for bi, members in enumerate(groups)}
            return True
        for bi in options[i]:
            groups[bi].append(weights[i])
            if walk(i + 1, groups):
                return True
            groups[bi].pop()
        return False

    walk(0, [[] for _ in bodies])
    return best


# ── planning ────────────────────────────────────────────────────────────────

class _Lever:
    """One body, the weights that carry it, and the places it has to come to rest.

    A board where a body already wears its marker's colours has one stop; a board where the
    colours are lying about loose has several, and the order they are picked up in is part of
    the plan, not an afterthought — every rest collects whatever it touches.
    """

    def __init__(self, board: _Board, body: dict[str, Any], members: list[tuple[int, int]],
                 marker: dict[str, Any], pickups: list[dict[str, Any]],
                 avoid: list[dict[str, Any]]) -> None:
        self.board = board
        self.body = body
        self.members = members
        self.marker = marker
        self.pickups = pickups
        self.avoid = avoid
        self.shape = _diamond(board.half + 1, board.half)

    def stops(self) -> list[dict[str, Any]]:
        """Each pickup in a nearest-first order, then the marker."""
        here = self.body["at"]
        left = list(self.pickups)
        route: list[dict[str, Any]] = []
        while left:
            nxt = min(left, key=lambda p: abs(p["at"][0] - here[0]) + abs(p["at"][1] - here[1]))
            left.remove(nxt)
            route.append(nxt)
            here = nxt["at"]
        return route + [self.marker]

    def solved(self) -> bool:
        if self.pickups:
            return False
        return bool(self._cells(self.body["at"]) & set(self.marker["cells"]))

    def _cells(self, at: tuple[int, int]) -> set[tuple[int, int]]:
        return {(at[0] + dy, at[1] + dx) for dy, dx in self.shape}

    def reach(self, stop: dict[str, Any]) -> list[tuple[int, int]]:
        """Body cells that make it touch this stop, nearest its centre first."""
        sy, sx = stop["at"]
        want = set(stop["cells"])
        span = 2 * self.board.half + 2
        out = [
            (sy + dy, sx + dx)
            for dy in range(-span, span + 1)
            for dx in range(-span, span + 1)
            if 0 <= sy + dy < self.board.h and 0 <= sx + dx < self.board.w
            and self._cells((sy + dy, sx + dx)) & want
        ]
        out.sort(key=lambda c: abs(c[0] - sy) + abs(c[1] - sx))
        return out

    def clear_of(self, forbid: list[dict[str, Any]], rest: np.ndarray) -> np.ndarray:
        """Rests that touch none of the tokens this body must not pick up.

        A rest collects whatever it touches, so a token meant for the other body — or one
        meant for a later stop of this one — is as fatal as the field: taking it adds a colour
        that cannot be given back.
        """
        if not forbid:
            return rest
        blob = np.zeros(rest.shape, dtype=bool)
        for other in forbid:
            for cy, cx in other["cells"]:
                blob[cy, cx] = True
        return rest & ~_dilate(blob, self.shape)


def _dilate(mask: np.ndarray, offsets: list[tuple[int, int]]) -> np.ndarray:
    """Grow a mask by a glyph's own footprint, so a centre cell means the whole glyph fits."""
    out = mask.copy()
    for dy, dx in offsets:
        out |= np.roll(np.roll(mask, -dy, axis=0), -dx, axis=1)
    return out


def _room(board: _Board) -> np.ndarray:
    """Cells a weight's pip may occupy at all: inside the frame, clear of the wall."""
    h, w, half = board.h, board.w, board.half
    ok = np.zeros((h, w), dtype=bool)
    ok[half + 1:h - half - 1, half + 1:w - half - 1] = True
    ok &= ~_dilate(board.wall, _diamond(half, half))
    for disk in board.disks:
        by, bx = disk["at"]
        span = half + 2
        ok[max(0, by - span):by + span + 1, max(0, bx - span):bx + span + 1] = False
    return ok


def _rest_ok(board: _Board) -> np.ndarray:
    """Cells a body may come to rest on: clear of the punishing field."""
    ok = np.ones((board.h, board.w), dtype=bool)
    if board.field.any():
        ok &= ~_dilate(board.field, _diamond(board.half + 1, board.half))
    return ok


def _centre(members: list[tuple[int, int]]) -> tuple[int, int]:
    n = len(members)
    return sum(m[0] for m in members) // n, sum(m[1] for m in members) // n


def _rest_grid(base: tuple[int, int], n: int, rest: np.ndarray) -> np.ndarray:
    """For every drop cell, whether the body's resulting rest is out of the field."""
    h, w = rest.shape
    ys = (base[0] + np.arange(h)) // n
    xs = (base[1] + np.arange(w)) // n
    good = np.zeros((h, w), dtype=bool)
    inside = (ys >= 0) & (ys < h)
    cols = (xs >= 0) & (xs < w)
    good[np.ix_(inside, cols)] = rest[np.ix_(ys[inside], xs[cols])]
    return good


def _boxes(cells: list[tuple[int, int]], span: int, shape: tuple[int, int]) -> np.ndarray:
    """Mask of every cell inside one of these glyphs' click boxes."""
    out = np.zeros(shape, dtype=bool)
    for cy, cx in cells:
        out[max(0, cy - span):cy + span + 1, max(0, cx - span):cx + span + 1] = True
    return out


def _mirror(mask: np.ndarray, total: tuple[int, int]) -> np.ndarray:
    """``out[y, x] = mask[total_y - y, total_x - x]`` — the partner of a drop that must pair to a sum."""
    h, w = mask.shape
    flip = mask[::-1, ::-1]
    pad = np.zeros((3 * h, 3 * w), dtype=bool)
    pad[h:2 * h, w:2 * w] = flip
    oy, ox = h - 1 - total[0], w - 1 - total[1]
    return pad[h + oy:h + oy + h, w + ox:w + ox + w]


def _one(board: _Board, members: list[tuple[int, int]], goals: list[tuple[int, int]],
         room: np.ndarray, rest: np.ndarray,
         busy: list[tuple[int, int]]) -> list[tuple[tuple[int, int], tuple[int, int]]] | None:
    """A single drop that lands the body on a goal cell."""
    n = len(members)
    span = board.half
    total = (sum(m[0] for m in members), sum(m[1] for m in members))
    for idx in range(n):
        base = (total[0] - members[idx][0], total[1] - members[idx][1])
        free = room & ~_boxes(busy, span, room.shape)
        for gy, gx in goals:
            for py in range(n * gy - base[0], n * gy - base[0] + n):
                if not 0 <= py < board.h:
                    continue
                for px in range(n * gx - base[1], n * gx - base[1] + n):
                    if 0 <= px < board.w and free[py, px]:
                        return [(members[idx], (py, px))]
    return None


def _two(board: _Board, members: list[tuple[int, int]], goals: list[tuple[int, int]],
         room: np.ndarray, rest: np.ndarray,
         busy: list[tuple[int, int]]) -> list[tuple[tuple[int, int], tuple[int, int]]] | None:
    """Two drops that land the body on a goal, searched over every way of splitting the sum.

    The pair is not strung out on a fixed pattern: the two destinations only have to add up,
    so the whole one-parameter family is scanned. That freedom is what gets a body around a
    field it cannot rest in — the arrangement that reaches the goal and the arrangement whose
    halfway rest is safe are usually not the same one.
    """
    n = len(members)
    span = board.half
    shape = room.shape
    total = (sum(m[0] for m in members), sum(m[1] for m in members))
    ys, xs = np.indices(shape)
    for i in range(n):
        rest_mid = rest[
            np.clip((total[0] - members[i][0] + ys) // n, 0, board.h - 1),
            np.clip((total[1] - members[i][1] + xs) // n, 0, board.w - 1),
        ]
        first = room & ~_boxes(busy, span, shape) & rest_mid
        if not first.any():
            continue
        for j in range(n):
            if i == j:
                continue
            base = (
                total[0] - members[i][0] - members[j][0],
                total[1] - members[i][1] - members[j][1],
            )
            others = [c for c in busy if c != members[i]]
            second = room & ~_boxes(others, span, shape)
            for gy, gx in goals:
                for sy in range(n * gy - base[0], n * gy - base[0] + n):
                    if not 0 <= sy <= 2 * (board.h - 1):
                        continue
                    for sx in range(n * gx - base[1], n * gx - base[1] + n):
                        if not 0 <= sx <= 2 * (board.w - 1):
                            continue
                        apart = (np.abs(2 * ys - sy) > span) | (np.abs(2 * xs - sx) > span)
                        hit = first & _mirror(second, (sy, sx)) & apart
                        if not hit.any():
                            continue
                        flat = int(np.argmax(hit))
                        py, px = flat // shape[1], flat % shape[1]
                        return [
                            (members[i], (py, px)),
                            (members[j], (sy - py, sx - px)),
                        ]
    return None


def _closer(board: _Board, members: list[tuple[int, int]], goal: tuple[int, int],
            room: np.ndarray, rest: np.ndarray,
            busy: list[tuple[int, int]]) -> tuple[int, tuple[int, int]] | None:
    """The drop that brings the body nearest its goal, for when no finish is in reach yet.

    One weight can only pull the mean a fraction of the way, so a distant marker needs a
    couple of these before the arithmetic closes.
    """
    n = len(members)
    h, w = room.shape
    span = board.half
    total = (sum(m[0] for m in members), sum(m[1] for m in members))
    here = abs(_centre(members)[0] - goal[0]) + abs(_centre(members)[1] - goal[1])
    best: tuple[int, int, tuple[int, int]] | None = None
    ys, xs = np.indices(room.shape)
    for idx in range(n):
        base = (total[0] - members[idx][0], total[1] - members[idx][1])
        landed_y = (base[0] + ys) // n
        landed_x = (base[1] + xs) // n
        free = room & ~_boxes(busy, span, room.shape)
        free &= rest[np.clip(landed_y, 0, h - 1), np.clip(landed_x, 0, w - 1)]
        if not free.any():
            continue
        cost = np.abs(landed_y - goal[0]) + np.abs(landed_x - goal[1])
        cost = np.where(free, cost, 1 << 20)
        flat = int(cost.argmin())
        value = int(cost.ravel()[flat])
        if value < here and (best is None or value < best[0]):
            best = (value, idx, (flat // w, flat % w))
    return None if best is None else (best[1], best[2])


_GOALS_TRIED = 8


def _plan_stop(board: _Board, members: list[tuple[int, int]], goals: list[tuple[int, int]],
               rest: np.ndarray, room: np.ndarray, busy: list[tuple[int, int]]
               ) -> list[tuple[tuple[int, int], tuple[int, int]]] | None:
    """(pick, drop) pairs that land this body on its marker, or None if it cannot be done.

    A finish is tried before every step, so the plan is as short as the arithmetic allows:
    each drop costs a pick-up click and a drop click, and this board ends the level on a
    fixed action count.
    """
    members = list(members)
    goals = goals[:_GOALS_TRIED]
    if not goals:
        return None
    out: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for _ in range(2 * len(members) + 2):
        for finish in (_one, _two):
            done = finish(board, members, goals, room, rest, busy)
            if done is not None:
                for pick, place in done:
                    busy[busy.index(pick)] = place
                return out + done
        step = _closer(board, members, goals[0], room, rest, busy)
        if step is None:
            return None
        out.append((members[step[0]], step[1]))
        busy[busy.index(members[step[0]])] = step[1]
        members[step[0]] = step[1]
    return None


# ── the tool ────────────────────────────────────────────────────────────────

class TetherCentroidTool:
    """Solve a board of tethered weights by planning where their balance points must land."""

    name = "tether"

    def __init__(self) -> None:
        self._plan: list[Step] = []

    # -- lifecycle -----------------------------------------------------------

    def reset(self) -> None:
        self._plan = []

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """No model is learnt: the board states its own geometry every frame."""

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Confidence, which is 0.0 unless a full plan exists for the board in front of it."""
        if not has_frame(obs):
            return 0.0
        _, action6 = availability(obs)
        if not action6:
            return 0.0
        return 0.88 if self._steps(_settled(obs)) else 0.0

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        return self._steps(_settled(obs))

    # -- the plan ------------------------------------------------------------

    def _steps(self, g: np.ndarray) -> list[Step]:
        board = _Board(g)
        if not board.half:
            return []
        groups = _partition(board)
        if not groups:
            return []
        levers = _levers(board, groups)
        if levers is None:
            return []
        rest = _rest_ok(board)
        room = _room(board)
        busy = [w["at"] for w in board.weights]
        held = board.held()
        steps: list[Step] = []
        for lever in levers:
            if lever.solved():
                continue
            members = list(lever.members)
            stops = lever.stops()
            for k, stop in enumerate(stops):
                free = lever.clear_of(lever.avoid + stops[k + 1:-1], rest)
                goals = [c for c in lever.reach(stop) if free[c]]
                drops = _plan_stop(board, members, goals, free, room, busy)
                if drops is None:
                    return []
                for pick, place in drops:
                    if pick != held:
                        steps.append((6, (pick[1], pick[0])))
                    held = place
                    steps.append((6, (place[1], place[0])))
                    members[members.index(pick)] = place
        return steps


def _levers(board: _Board,
            groups: dict[tuple[int, int], list[tuple[int, int]]]) -> list[_Lever] | None:
    """Pair every body with the marker it has to reach, and with the colours it needs first.

    Two boards, one rule. When a body already wears a marker's colours the pairing is that
    identity and nothing is collected. When no body wears any marker — they start blank — the
    colours are lying about as loose tokens, and the pairing is whichever assignment of
    markers and tokens USES THE MOST of them: a blank body can satisfy a one-colour marker by
    taking a single token, which looks like a solution and leaves a real marker unreachable.
    """
    bodies = [d for d in board.disks if d["at"] in groups]
    if not bodies:
        return None
    loose = [d for d in board.disks if d["at"] not in groups]
    direct = _direct(board, bodies, groups, loose)
    if direct is not None:
        return direct
    return _collect(board, bodies, groups, loose)


def _direct(board: _Board, bodies: list[dict[str, Any]],
            groups: dict[tuple[int, int], list[tuple[int, int]]],
            loose: list[dict[str, Any]]) -> list[_Lever] | None:
    """Every body already wears exactly one marker's colours."""
    out: list[_Lever] = []
    taken: set[tuple[int, int]] = set()
    for body in bodies:
        fits = [m for m in board.markers
                if m["at"] not in taken and m["colours"] == body["colours"]]
        if len(fits) != 1:
            return None
        taken.add(fits[0]["at"])
        out.append(_Lever(board, body, groups[body["at"]], fits[0], [], loose))
    return out or None


def _collect(board: _Board, bodies: list[dict[str, Any]],
             groups: dict[tuple[int, int], list[tuple[int, int]]],
             loose: list[dict[str, Any]]) -> list[_Lever] | None:
    """Blank bodies, loose colour tokens: choose the assignment that consumes the most tokens."""
    if not loose:
        return None
    base = set(loose[0]["colours"])
    for d in board.disks:
        base &= d["colours"]
    carried = [d["colours"] - base for d in loose]
    if any(len(c) != 1 for c in carried) or any(body["colours"] - base for body in bodies):
        return None
    best: tuple[int, list[_Lever]] | None = None
    for pairs in _assignments(len(bodies), len(board.markers)):
        used: list[list[int]] = []
        ok = True
        spent: set[int] = set()
        for bi, mi in enumerate(pairs):
            want = board.markers[mi]["colours"] - base
            take = []
            for ti, colour in enumerate(carried):
                if ti not in spent and colour <= want:
                    take.append(ti)
            got = set()
            for ti in take:
                got |= carried[ti]
            if got != want or not take:
                ok = False
                break
            spent |= set(take)
            used.append(take)
        if not ok:
            continue
        score = len(spent)
        if best is not None and score <= best[0]:
            continue
        levers = [
            _Lever(
                board, bodies[bi], groups[bodies[bi]["at"]], board.markers[pairs[bi]],
                [loose[ti] for ti in used[bi]],
                [loose[ti] for ti in range(len(loose)) if ti not in spent],
            )
            for bi in range(len(bodies))
        ]
        best = (score, levers)
    return None if best is None else best[1]


def _assignments(n: int, m: int) -> list[tuple[int, ...]]:
    """Every way of giving each of ``n`` bodies a distinct one of ``m`` markers."""
    from itertools import permutations
    return list(permutations(range(m), n))
