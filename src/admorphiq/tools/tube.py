"""Extendable-tube tool: a nozzle on a rail that must swallow tiles in a demanded order.

The mechanic, recovered from one sample board and written here in the terms a frame can
supply. A PANEL below the board shows a second tube already holding a run of coloured
tiles; that run is the demand. On the board a NOZZLE sits one cell OUTSIDE the play
rectangle, mounted on a rail, with a tube of segments running from it into the field.
Four moves, and only four:

  * along the tube's own axis, away from the nozzle -> the tube EXTENDS one cell, pushing
    whatever stands in front of it;
  * along that axis toward the nozzle -> the tube RETRACTS one cell, dragging the tiles it
    covers back with it and DEPOSITING any tile that cannot follow;
  * across that axis -> the whole assembly SLIDES one cell along the rail, carrying its
    tiles, and refusing to move at all if any tile it would push is stuck.

A tile pushed against something immovable while the tube advances onto it is swallowed:
it stays where it is and the segment covers it. The tube's contents, read from the nozzle
outward, must equal the panel's run. So the board is a rearrangement puzzle whose only
verbs are push, drag and deposit — and the planner is a breadth-first search over exactly
those, run on a simulator of the rule rather than on the live game.

Everything is derived from the frame: the panel, the play rectangle, the lattice step, the
rail's reach, which tube is the live one (it is drawn in the same two colours as the
panel's tube), the tiles, and the walls. No coordinate and no colour is written down.
"""

from __future__ import annotations

import heapq
from collections import Counter
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, base_hash, has_frame, levels_completed

__all__ = ["TubeOrderTool", "Board", "parse", "plan"]

# Search ceiling. A board of this shape reaches a few hundred thousand arrangements;
# past that the tool has no plan, and says so rather than guessing.
_NODE_CAP = 300_000
# Level-order search is kept for boards small enough to finish it, so a shallow board gets
# the shortest route; past this the search follows the arrangements that already spell most
# of the demand. Measured on four boards: at this changeover the routes are unchanged and
# the search costs a tenth of the time and memory of running level-order for longer.
_BREADTH_CAP = 10_000
_DIRS = ((0, -1), (0, 1), (-1, 0), (1, 0))
# The family's keyboard convention. Corrected from observation if a board disagrees.
_KEYS = {(0, -1): 1, (0, 1): 2, (-1, 0): 3, (1, 0): 4}


def _neg(v: tuple[int, int]) -> tuple[int, int]:
    return (-v[0], -v[1])


def _settled(obs: Any) -> np.ndarray:
    """The LAST layer of the observation, not the first.

    Measured: one action here runs an animation, and the observation carries a layer per
    tick of it. Layer zero is the board caught mid-slide — half a cell out of position on
    a lattice whose step is a whole cell — and every reading taken from it is wrong.
    """
    arr = np.asarray(getattr(obs, "frame", None))
    if arr.ndim >= 3:
        arr = arr[-1]
    return arr.astype(np.int64)


# --- the board and its rule -------------------------------------------------

class Board:
    """A parsed board: geometry, the live tube, the tiles, and the demanded run."""

    def __init__(
        self,
        pitch: int,
        field: tuple[int, int, int, int],
        head: tuple[int, int],
        axis: tuple[int, int],
        length: int,
        tiles: dict[tuple[int, int], int],
        walls: set[tuple[int, int]],
        foreign: dict[tuple[int, int], tuple[int, int]],
        rail: tuple[int, int],
        demand: list[int],
    ) -> None:
        self.p = pitch
        self.fx0, self.fy0, self.fx1, self.fy1 = field
        self.head = head
        self.axis = axis
        self.length = length
        self.tiles = tiles
        self.walls = walls
        self.foreign = foreign          # cell -> that segment's own axis
        self.rail = rail                # inclusive pixel span across the tube's axis
        self.demand = demand

    def cells(self, head: tuple[int, int], length: int) -> list[tuple[int, int]]:
        ax, ay = self.axis
        return [(head[0] + i * ax * self.p, head[1] + i * ay * self.p) for i in range(length)]

    def outside(self, cell: tuple[int, int]) -> bool:
        x, y = cell
        return x < self.fx0 or x + self.p > self.fx1 or y < self.fy0 or y + self.p > self.fy1

    def blocked(self, cell: tuple[int, int], move: tuple[int, int]) -> bool:
        dest = (cell[0] + move[0] * self.p, cell[1] + move[1] * self.p)
        return self.outside(dest) or dest in self.walls

    def rail_ok(self, head: tuple[int, int], move: tuple[int, int]) -> bool:
        """The rail must reach half a cell beyond the nozzle's centre in the slide's sense."""
        off = self.p // 2 - 1
        probe = (head[0] + off + move[0] * (self.p // 2), head[1] + off + move[1] * (self.p // 2))
        across = probe[1] if self.axis[0] else probe[0]
        return self.rail[0] <= across <= self.rail[1]


class Sim:
    """One transition, faithful to the push / drag / deposit rule."""

    def __init__(self, board: Board, head: tuple[int, int], length: int,
                 tiles: dict[tuple[int, int], int]) -> None:
        self.b = board
        self.head = head
        self.length = length
        self.tiles = tiles
        self.live = board.cells(head, length)
        self.livepos = set(self.live)

    def _crossing(self, cell: tuple[int, int], want_flat: bool,
                  skip: tuple[int, int] | None) -> bool:
        """Is there a segment at this cell lying along the axis asked for?

        `skip` excuses the segment doing the pushing, and ONLY that one. A cell can hold
        two segments at once — the live tube standing where a dead one already crosses —
        and excusing the whole cell was measured to make the tool believe it could drag a
        tile out of a crossing tube. It cannot, and the two plans that follow from the two
        beliefs are exact inverses, so the tool oscillated until the level's budget ran out.
        """
        if cell != skip and cell in self.livepos and bool(self.b.axis[0]) == want_flat:
            return True
        other = self.b.foreign.get(cell)
        return other is not None and bool(other[0]) == want_flat

    def _push(self, kind: str, cell: tuple[int, int], move: tuple[int, int],
              moved: set[tuple[str, tuple[int, int]]],
              parent: tuple[int, int] | None = None) -> bool:
        key = (kind, cell)
        if key in moved:
            return True
        p = self.b.p
        dest = (cell[0] + move[0] * p, cell[1] + move[1] * p)
        if self.b.blocked(cell, move):
            # A segment being drawn back toward its own nozzle, or one already standing
            # outside the rectangle, is exempt: that is how the tube retracts off the edge.
            exempt = kind == "seg" and (self.b.axis == _neg(move) or self.b.outside(cell))
            if not exempt:
                return False
        if kind == "seg":
            for off in ((0, 0), move):
                at = (cell[0] + off[0] * p, cell[1] + off[1] * p)
                if at not in self.tiles:
                    continue
                if self._push("tile", at, move, moved, parent=cell):
                    moved.add(("tile", at))
                elif (self.b.axis[0] == 0) != (move[0] == 0):
                    # Sliding sideways into a tile that cannot give way stops everything.
                    # Advancing along the axis instead SWALLOWS it, which costs no state.
                    return False
        else:
            flat_move = move[0] != 0
            for off in ((0, 0), move):
                at = (cell[0] + off[0] * p, cell[1] + off[1] * p)
                if self._crossing(at, not flat_move, parent):
                    return False
            if dest in self.tiles and not self._push("tile", dest, move, moved):
                return False
        moved.add(key)
        return True

    def apply(self, move: tuple[int, int]) -> tuple[tuple[int, int], int, dict, bool]:
        """(nozzle, length, tiles, did_anything_move) after this move."""
        b, p = self.b, self.b.p
        stay = (self.head, self.length, self.tiles, False)
        moved: set[tuple[str, tuple[int, int]]] = set()
        if move == b.axis:                                     # extend
            if b.blocked(self.live[-1], move):
                return stay
            for c in self.live:
                self._push("seg", c, move, moved)
            new_head, new_len = self.head, self.length + 1
        elif move == _neg(b.axis):                             # retract
            if self.length == 1:
                return stay
            for c in self.live[1:]:
                self._push("seg", c, move, moved)
            new_head, new_len = self.head, self.length - 1
        else:                                                  # slide along the rail
            if not b.rail_ok(self.head, move):
                return stay
            for c in self.live:
                if not self._push("seg", c, move, moved):
                    return stay
            new_head = (self.head[0] + move[0] * p, self.head[1] + move[1] * p)
            new_len = self.length
        if not moved:
            return stay
        shifted = {c for kind, c in moved if kind == "tile"}
        tiles = {}
        for cell, colour in self.tiles.items():
            if cell in shifted:
                tiles[(cell[0] + move[0] * p, cell[1] + move[1] * p)] = colour
            else:
                tiles[cell] = colour
        return (new_head, new_len, tiles, True)


def _satisfied(board: Board, head: tuple[int, int], length: int, tiles: dict) -> bool:
    got = [tiles[c] for c in board.cells(head, length) if c in tiles]
    want = board.demand
    return len(got) >= len(want) and got[: len(want)] == want


def _progress(board: Board, head: tuple[int, int], length: int, tiles: dict) -> tuple[int, int]:
    """How near this arrangement is to the demand: (matching prefix, order kept)."""
    got = [tiles[c] for c in board.cells(head, length) if c in tiles]
    want = board.demand
    pre = 0
    while pre < len(want) and pre < len(got) and got[pre] == want[pre]:
        pre += 1
    # Longest run of the demand appearing in order anywhere under the tube: it separates
    # an arrangement that has the right tiles in the right sequence but shifted along the
    # tube from one that merely has the right tiles.
    keep = 0
    for colour in got:
        if keep < len(want) and colour == want[keep]:
            keep += 1
    return pre, keep


def plan(board: Board, cap: int = _NODE_CAP) -> list[tuple[int, int]] | None:
    """Search (nozzle, length, tile arrangement) for the demanded run.

    Breadth first while that is affordable, because a shallow board deserves the shortest
    route; then best first on how much of the demand the arrangement already spells,
    because a board with four tiles on a seven-by-seven field has more arrangements than a
    level-order sweep will ever reach. States are flat tuples and the route is parent
    links: carrying a path per queue entry is what runs this out of memory rather than out
    of nodes.
    """
    if _satisfied(board, board.head, board.length, board.tiles):
        return []
    start = (board.head, board.length, tuple(sorted(board.tiles.items())))
    seen: dict[tuple, tuple[int, tuple[int, int] | None]] = {start: (-1, None)}
    order = [start]

    def route_to(node: int) -> list[tuple[int, int]]:
        out = []
        while node > 0:
            back, mv = seen[order[node]]
            out.append(mv)
            node = back
        return out[::-1]

    def expand(node: int) -> int | None:
        cur = order[node]
        tiles = dict(cur[2])
        for move in _DIRS:
            nh, nl, nt, changed = Sim(board, cur[0], cur[1], tiles).apply(move)
            if not changed:
                continue
            key = (nh, nl, tuple(sorted(nt.items())))
            if key in seen:
                continue
            seen[key] = (node, move)
            order.append(key)
            if _satisfied(board, nh, nl, nt):
                return len(order) - 1
        return None

    flat = min(cap, _BREADTH_CAP)
    i = 0
    while i < len(order) and i < flat:
        hit = expand(i)
        if hit is not None:
            return route_to(hit)
        i += 1
    if i < len(order):
        pool: list[tuple[int, int, int]] = []
        for node in range(i, len(order)):
            pre, keep = _progress(board, order[node][0], order[node][1], dict(order[node][2]))
            heapq.heappush(pool, (-pre, -keep, node))
        while pool and len(seen) < cap:
            _, _, node = heapq.heappop(pool)
            frontier = len(order)
            hit = expand(node)
            if hit is not None:
                return route_to(hit)
            for fresh in range(frontier, len(order)):
                pre, keep = _progress(board, order[fresh][0], order[fresh][1], dict(order[fresh][2]))
                heapq.heappush(pool, (-pre, -keep, fresh))
    return None


# --- perception -------------------------------------------------------------

def _strip_top(g: np.ndarray, bg: int, panel: int) -> int:
    """First row of the demand panel.

    The panel is the band at the bottom that the background never shows through. A coverage
    vote finds the wrong edge of it, because a busy panel row is mostly its own contents.
    Any single-colour rule between the band and the board is chrome, and is peeled off.
    """
    h = g.shape[0]
    y = h - 1
    while y >= 0 and not (g[y] == bg).any():
        y -= 1
    top = y + 1
    while top < h and len(set(int(v) for v in g[top])) <= 2 \
            and panel not in set(int(v) for v in g[top]):
        top += 1
    return top if h // 2 < top < h - 1 else -1


def _field_rect(g: np.ndarray, panel: int, limit: int) -> tuple[int, int, int, int] | None:
    """The play rectangle: where the panel colour is laid down thickly above the band.

    A projection, not a component: the tube can cut the rectangle's colour clean in two
    across its whole width, and a component would then report half a board.
    """
    area = g[:limit] == panel
    rows = area.sum(axis=1)
    cols = area.sum(axis=0)
    if rows.max() < 4 or cols.max() < 4:
        return None
    ys = np.where(rows >= max(4, rows.max() * 0.34))[0]
    xs = np.where(cols >= max(4, cols.max() * 0.34))[0]
    if not len(ys) or not len(xs):
        return None
    return int(xs[0]), int(ys[0]), int(xs[-1]) + 1, int(ys[-1]) + 1


def _square_components(g: np.ndarray, skip: set[int]) -> list[int]:
    """The side of every solid square block of a non-skipped colour. Used only for pitch."""
    h, w = g.shape
    seen = np.zeros((h, w), dtype=bool)
    out: list[int] = []
    for y in range(h):
        for x in range(w):
            if seen[y, x] or int(g[y, x]) in skip:
                continue
            colour = int(g[y, x])
            stack = [(y, x)]
            seen[y, x] = True
            cells = []
            while stack:
                cy, cx = stack.pop()
                cells.append((cy, cx))
                for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                    if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] \
                            and int(g[ny, nx]) == colour:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            ys = [c[0] for c in cells]
            xs = [c[1] for c in cells]
            side = max(ys) - min(ys) + 1
            if side == max(xs) - min(xs) + 1 and len(cells) == side * side:
                out.append(side)
    return out


def _seg_edges(g: np.ndarray, x: int, y: int, p: int) -> tuple[int, int] | None:
    """The two colours of a segment lying flat at this cell, or None.

    Only the segment's two end columns are read: a tile drawn on top hides everything
    between them, and those are exactly the cells that matter.
    """
    o = p // 2 - 1
    if x < 0 or y < 0 or y + o + 1 >= g.shape[0] or x + p > g.shape[1]:
        return None
    a, b = int(g[y + o, x]), int(g[y + o + 1, x])
    c, d = int(g[y + o, x + p - 1]), int(g[y + o + 1, x + p - 1])
    return (a, b) if a != b and a == d and b == c else None


def _seg_edges_v(g: np.ndarray, x: int, y: int, p: int) -> tuple[int, int] | None:
    """The same reading for a segment standing on end."""
    o = p // 2 - 1
    if x < 0 or y < 0 or y + p > g.shape[0] or x + o + 1 >= g.shape[1]:
        return None
    a, b = int(g[y, x + o]), int(g[y, x + o + 1])
    c, d = int(g[y + p - 1, x + o]), int(g[y + p - 1, x + o + 1])
    return (a, b) if a != b and a == d and b == c else None


def _is_mouth(g: np.ndarray, x: int, y: int, p: int, pair: tuple[int, int],
              axis: tuple[int, int]) -> bool:
    """Does this cell hold a nozzle whose tube runs off along `axis`?

    The nozzle's casing covers its own cell except for two pixels at the lip, where the
    tube colour shows through. That lip is the only thing that identifies it, and it is
    still there when the tube has been drawn back to nothing — which a chain search is not.
    """
    o = p // 2 - 1
    a, b = pair
    if axis[0]:
        col = x + p - 1 if axis[0] > 0 else x
        want = (b, a) if axis[0] > 0 else (a, b)
        if x < 0 or y < 0 or y + o + 1 >= g.shape[0] or col >= g.shape[1] or x + p > g.shape[1]:
            return False
        if (int(g[y + o, col]), int(g[y + o + 1, col])) != want:
            return False
        return _seg_edges(g, x, y, p) is None
    row = y + p - 1 if axis[1] > 0 else y
    want = (b, a) if axis[1] > 0 else (a, b)
    if x < 0 or y < 0 or row >= g.shape[0] or y + p > g.shape[0] or x + o + 1 >= g.shape[1]:
        return False
    if (int(g[row, x + o]), int(g[row, x + o + 1])) != want:
        return False
    return _seg_edges_v(g, x, y, p) is None


def _tile_at(g: np.ndarray, cell: tuple[int, int], p: int, bg: int, panel: int) -> int | None:
    """The colour of the tile occupying this cell, or None.

    Only the tile's own border ring is read. The panel stamps a small mark in the middle of
    a tile once that slot of the demand is satisfied, so a solid-square test loses exactly
    the tiles that are going right.
    """
    x, y = cell
    if x < 0 or y < 0 or y + p > g.shape[0] or x + p > g.shape[1]:
        return None
    inner = g[y + 1:y + p - 1, x + 1:x + p - 1]
    ring = np.concatenate([inner[0], inner[-1], inner[:, 0], inner[:, -1]])
    colour = int(ring[0])
    if colour in (bg, panel) or not np.all(ring == colour):
        return None
    lid = g[y, x:x + p]
    if int(lid[0]) not in (bg, panel) and np.all(lid == lid[0]):
        return None                      # a nozzle: its own casing reads as a ring
    return colour


def _rail_span(g: np.ndarray, head: tuple[int, int], axis: tuple[int, int], p: int,
               bg: int, rect: tuple[int, int, int, int], top: int) -> tuple[int, int]:
    """How far the nozzle's track reaches across its own lane.

    Read only inside the nozzle's lane. Another fixture parked outside the rectangle would
    otherwise be counted as track and offer a slide that does not exist. The nozzle hides
    the stretch of track it stands on, so its own centre is seeded into the span; without
    that the track reads short at whichever end the nozzle happens to be resting.
    """
    fx0, fy0, fx1, fy1 = rect
    o = p // 2 - 1
    chrome_rows = {y for y in range(top) if not (g[y] == bg).any()}
    chrome_cols = {x for x in range(g.shape[1]) if not (g[:top, x] == bg).any()}
    if axis[0]:
        lo, hi = head[1] + o, head[1] + o + 1
        for y in range(top):
            if y in chrome_rows or head[1] <= y < head[1] + p:
                continue
            for x in range(head[0], min(head[0] + p, g.shape[1])):
                if int(g[y, x]) == bg or (fx0 <= x < fx1 and fy0 <= y < fy1):
                    continue
                lo, hi = min(lo, y), max(hi, y)
    else:
        lo, hi = head[0] + o, head[0] + o + 1
        for x in range(g.shape[1]):
            if x in chrome_cols or head[0] <= x < head[0] + p:
                continue
            for y in range(head[1], min(head[1] + p, top)):
                if int(g[y, x]) == bg or (fx0 <= x < fx1 and fy0 <= y < fy1):
                    continue
                lo, hi = min(lo, x), max(hi, x)
    return lo, hi


def parse(g: np.ndarray) -> Board | None:
    """Read a board off one frame, or return None when this is not that shape of board."""
    if g.shape[0] < 16 or g.shape[0] != g.shape[1]:
        return None
    # The surround, not the commonest colour: on a large board the play surface outweighs
    # its own background, and a frequency vote hands back the board.
    bg = int(Counter(int(v) for v in g[0]).most_common(1)[0][0])
    panel = int(Counter(int(v) for v in g[g.shape[0] - 1]).most_common(1)[0][0])
    if panel == bg:
        return None
    top = _strip_top(g, bg, panel)
    if top < 0:
        return None
    rect = _field_rect(g, panel, top)
    if rect is None:
        return None
    fx0, fy0, fx1, fy1 = rect
    sides = Counter(s for s in _square_components(g, {bg, panel}) if s >= 3)
    if not sides:
        return None
    p = sides.most_common(1)[0][0] + 2
    if p < 4 or fx1 - fx0 < 2 * p or fy1 - fy0 < 2 * p:
        return None
    if (fx1 - fx0) % p or (fy1 - fy0) % p:
        return None

    # The panel's own lattice need not share the board's phase, so it is scanned at every
    # offset. Exactly ONE chain may live down there: two chains are two demands, and this
    # tool plans for one tube.
    chains: list[tuple[list[tuple[int, int]], tuple[int, int]]] = []
    for x in range(g.shape[1] - p + 1):
        for y in range(top, g.shape[0] - p + 1):
            e = _seg_edges(g, x, y, p)
            if not e or _seg_edges(g, x - p, y, p) == e:
                continue
            chain = [(x, y)]
            nxt = (x + p, y)
            while _seg_edges(g, nxt[0], nxt[1], p) == e:
                chain.append(nxt)
                nxt = (nxt[0] + p, nxt[1])
            chains.append((chain, e))
    if len(chains) != 1:
        return None
    ref, pair = chains[0]

    ref_head = None
    for cand in ((ref[0][0] - p, ref[0][1]), (ref[-1][0] + p, ref[-1][1])):
        if _is_mouth(g, cand[0], cand[1], p, pair, (1, 0)) \
                or _is_mouth(g, cand[0], cand[1], p, pair, (-1, 0)):
            if ref_head is not None:
                return None
            ref_head = cand
    if ref_head is None:
        return None
    ref_cells = sorted(set(ref) | {ref_head})
    if ref_cells[0] != ref_head:
        ref_cells = ref_cells[::-1]
    demand = [c for c in (_tile_at(g, q, p, bg, panel) for q in ref_cells) if c is not None]
    demand = demand[: len(ref_cells) - 1]
    if not demand:
        return None

    found = []
    for x in range(fx0 - p, fx1 + p, p):
        for y in range(fy0 - p, min(fy1 + p, top), p):
            cell = (x, y)
            if not (x < fx0 or x + p > fx1 or y < fy0 or y + p > fy1):
                continue
            for axis in _DIRS:
                if _is_mouth(g, x, y, p, pair, axis):
                    found.append((cell, axis))
    if len(found) != 1:
        return None
    head, axis = found[0]
    reader = _seg_edges if axis[0] else _seg_edges_v
    step = (axis[0] * p, axis[1] * p)
    cells = [head]
    nxt = (head[0] + step[0], head[1] + step[1])
    while reader(g, nxt[0], nxt[1], p) == pair:
        cells.append(nxt)
        nxt = (nxt[0] + step[0], nxt[1] + step[1])

    tiles: dict[tuple[int, int], int] = {}
    walls: set[tuple[int, int]] = set()
    foreign: dict[tuple[int, int], tuple[int, int]] = {}
    for x in range(fx0, fx1, p):
        for y in range(fy0, fy1, p):
            colour = _tile_at(g, (x, y), p, bg, panel)
            if colour is not None:
                tiles[(x, y)] = colour
            elif np.all(g[y:y + p, x:x + p] == bg):
                walls.add((x, y))
    for x in range(fx0 - p, fx1 + p, p):
        for y in range(fy0 - p, min(fy1 + p, top), p):
            if (x, y) in cells:
                continue
            if _seg_edges(g, x, y, p) is not None:
                foreign[(x, y)] = (1, 0)
            elif _seg_edges_v(g, x, y, p) is not None:
                foreign[(x, y)] = (0, 1)

    lo, hi = _rail_span(g, head, axis, p, bg, rect, top)
    if lo > hi:
        return None
    return Board(p, rect, head, axis, len(cells), tiles, walls, foreign, (lo, hi), demand)


# --- the tool ---------------------------------------------------------------

class TubeOrderTool:
    """Plan a tube board to its demanded run, or stand down.

    `detect` bids only when a board parses AND the search has found a route through it, so
    a board this tool merely resembles costs the run nothing. The route is planned once and
    then FOLLOWED: the search is seconds of work, and re-running it per frame would spend
    more time than the whole level does. Every frame is still checked against what the
    route predicted, and a surprise re-plans on the spot.
    """

    name = "tube_order"

    def __init__(self) -> None:
        self._keys = dict(_KEYS)
        self._dead: set[str] = set()
        self.reset()

    def reset(self) -> None:
        self._route: list[tuple[int, int]] = []
        self._board: Board | None = None
        self._key: str | None = None
        self._expect: tuple | None = None
        self._pending: tuple[Board, tuple[int, int], int] | None = None
        self._level = -1
        # One failed search per level is enough. The tool takes no action when it has no
        # route, so nothing it does can change the board into a solvable one, and the
        # search is seconds of work that would otherwise be repeated every single turn.
        self._surrendered = False

    @staticmethod
    def _state(board: Board) -> tuple:
        return (board.head, board.length, tuple(sorted(board.tiles.items())))

    def _rebind(self, board: Board) -> None:
        """Bind a key to the direction it actually produced.

        The four directions are read off the board, but WHICH key drives which is a
        convention, and a convention is not a measurement. One transition settles it: at
        most one direction reproduces what the frame did, so when the board disagrees with
        the convention the two keys involved trade places.
        """
        assert self._pending is not None
        before, move, aid = self._pending
        self._pending = None
        actual = self._state(board)
        matches = []
        for cand in _DIRS:
            nh, nl, nt, _ = Sim(before, before.head, before.length, before.tiles).apply(cand)
            if (nh, nl, tuple(sorted(nt.items()))) == actual:
                matches.append(cand)
        if len(matches) != 1 or matches[0] == move:
            return
        truth = matches[0]
        self._keys[move], self._keys[truth] = self._keys[truth], aid

    def _study(self, obs: Any) -> bool:
        if not has_frame(obs):
            return False
        g = _settled(obs)
        done = levels_completed(obs)
        if done != self._level:
            self._level = done
            self._route, self._board, self._key = [], None, None
            self._expect, self._pending = None, None
            self._surrendered = False
        digest = base_hash(g)
        if digest == self._key:
            return bool(self._route)
        self._key = digest
        board = parse(g)
        if board is None:
            self._route, self._board = [], None
            self._pending = None
            return False
        if self._pending is not None:
            self._rebind(board)
        state = self._state(board)
        if self._route and state == self._expect:
            self._board = board
            self._route = self._route[1:]
            self._expect = None
            if self._route:
                return True
        if self._surrendered or digest in self._dead:
            self._route, self._board = [], None
            return False
        route = plan(board)
        if route is None:
            self._dead.add(digest)
            self._surrendered = True
            self._route, self._board = [], None
            return False
        self._board, self._route = board, route
        return bool(route)

    def detect(self, frames: list[Any], obs: Any) -> float:
        return 0.95 if self._study(obs) else 0.0

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Nothing is learned here: the correction needs the frame AFTER the action."""

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not self._study(obs) or not self._route:
            return []
        board = self._board
        assert board is not None
        move = self._route[0]
        key = self._keys[move]
        nh, nl, nt, _ = Sim(board, board.head, board.length, board.tiles).apply(move)
        self._expect = (nh, nl, tuple(sorted(nt.items())))
        self._pending = (board, move, key)
        return [(key, None)]
