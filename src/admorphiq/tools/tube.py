"""Extendable-tube tool: nozzles on rails that must swallow tiles in a demanded order.

The mechanic, recovered from the sample boards and written here in the terms a frame can
supply. A PANEL below the board shows one or more tubes already holding a run of coloured
tiles; each such run is a demand. On the board sits a NOZZLE per demand, one cell OUTSIDE
the play rectangle, mounted on a rail, with a tube of segments running from it into the
field. Four moves, and only four:

  * along the tube's own axis, away from the nozzle -> the tube EXTENDS one cell, pushing
    whatever stands in front of it;
  * along that axis toward the nozzle -> the tube RETRACTS one cell, dragging the tiles it
    covers back with it and DEPOSITING any tile that cannot follow;
  * across that axis -> the whole assembly SLIDES one cell along the rail, carrying its
    tiles, and refusing to move at all if any tile it would push is stuck.

A tile pushed against something immovable while the tube advances onto it is swallowed:
it stays where it is and the segment covers it. Each board tube's contents, read from its
nozzle outward, must equal its panel partner's run — ALL of them at once.

Only ONE tube answers the keys at a time. A click on a nozzle hands the keys to that
tube's pair, and every other tube on the board stands still and blocks like furniture. So
the board is a rearrangement puzzle whose verbs are push, drag, deposit and hand-over, and
the planner is a search over exactly those, run on a simulator of the rule rather than on
the live game.

Everything is derived from the frame: the panel, the play rectangle, the lattice step, each
rail's reach, which tubes pair with which demand, the tiles, and the walls. No coordinate
and no colour is written down.
"""

from __future__ import annotations

import heapq
from collections import Counter
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, base_hash, has_frame, levels_completed

__all__ = ["TubeOrderTool", "Board", "Tube", "parse", "plan"]

# Search ceiling. A board of this shape reaches a few hundred thousand arrangements;
# past that the tool has no plan, and says so rather than guessing.
_NODE_CAP = 260_000
# Level-order search is kept for boards small enough to finish it, so a shallow board gets
# the shortest route; past this the search follows the arrangements that already spell most
# of the demand. Measured on four boards: at this changeover the routes are unchanged and
# the search costs a tenth of the time and memory of running level-order for longer.
_BREADTH_CAP = 12_000
# What one unspelled slot of a demand is worth in moves, once the level-order sweep gives
# out. See `plan`. Swept over 2, 4, 8, 16, 32, 64 and 200 against every board of the sample
# game, and 16 is the ONLY one of the seven that solves all of them: under it two of the
# middle boards are never found, over it the board where a single tile has to serve two
# tubes at once is never found. It is a real optimum, not a floor — a bigger number is not
# "more directed", it is a different failure. The routes it returns run 14 to 55 moves
# against a level budget of about two hundred, so the depth is not bought with the budget.
_SLOT_COST = 16
_DIRS = ((0, -1), (0, 1), (-1, 0), (1, 0))
# The family's keyboard convention. Corrected from observation if a board disagrees.
_KEYS = {(0, -1): 1, (0, 1): 2, (-1, 0): 3, (1, 0): 4}
_CLICK = 6


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

class Tube:
    """One tube on the board: where it is mounted, how far it reaches, what it owes."""

    __slots__ = ("head", "axis", "length", "group", "demand", "rail", "click")

    def __init__(self, head: tuple[int, int], axis: tuple[int, int], length: int,
                 group: frozenset[int]) -> None:
        self.head = head
        self.axis = axis
        self.length = length
        self.group = group
        self.demand: list[int] | None = None
        self.rail: tuple[int, int] = (0, -1)
        self.click: tuple[int, int] | None = None


class Board:
    """A parsed board: geometry, every board tube, the tiles, and the walls."""

    def __init__(self, pitch: int, field: tuple[int, int, int, int],
                 tubes: list[Tube], tiles: dict[tuple[int, int], int],
                 walls: set[tuple[int, int]]) -> None:
        self.p = pitch
        self.fx0, self.fy0, self.fx1, self.fy1 = field
        self.tubes = tubes
        self.tiles = tiles
        self.walls = walls

    def outside(self, cell: tuple[int, int]) -> bool:
        x, y = cell
        return x < self.fx0 or x + self.p > self.fx1 or y < self.fy0 or y + self.p > self.fy1

    def blocked(self, cell: tuple[int, int], move: tuple[int, int]) -> bool:
        dest = (cell[0] + move[0] * self.p, cell[1] + move[1] * self.p)
        return self.outside(dest) or dest in self.walls

    def stuck(self, cell: tuple[int, int]) -> bool:
        """Is this cell itself off the field? A nozzle's own cell always is."""
        return self.outside(cell) or cell in self.walls

    def rail_ok(self, idx: int, head: tuple[int, int], move: tuple[int, int]) -> bool:
        """The rail must reach half a cell beyond the nozzle's centre in the slide's sense."""
        tube = self.tubes[idx]
        off = self.p // 2 - 1
        probe = (head[0] + off + move[0] * (self.p // 2), head[1] + off + move[1] * (self.p // 2))
        across = probe[1] if tube.axis[0] else probe[0]
        return tube.rail[0] <= across <= tube.rail[1]

    def selectable(self) -> list[int]:
        """Tubes a click can hand the keys to: the ones with a partner in the panel."""
        return [i for i, t in enumerate(self.tubes) if t.demand is not None and t.click]


def cells_of(head: tuple[int, int], axis: tuple[int, int], length: int,
             p: int) -> list[tuple[int, int]]:
    return [(head[0] + i * axis[0] * p, head[1] + i * axis[1] * p) for i in range(length)]


def _step(board: Board, heads: tuple, lengths: tuple, tiles: dict, active: int,
          move: tuple[int, int]):
    """One key press on the active tube. Returns (heads, lengths, tiles) or None.

    A faithful transcription of the rule: a segment advancing along its own axis onto a
    tile that cannot give way SWALLOWS it (the tile stays, the segment covers it), while a
    segment moving ACROSS its axis into a stuck tile refuses, and refuses for the whole
    assembly. A tile is stopped dead by any segment lying across the direction it is asked
    to go, in its own cell or the one it is aimed at — which is what makes a second tube
    furniture rather than scenery.
    """
    p = board.p
    tube = board.tubes[active]
    axis = tube.axis
    segs = cells_of(heads[active], axis, lengths[active], p)

    occupied: dict[tuple[int, int], list[tuple[int, bool]]] = {}
    for i, t in enumerate(board.tubes):
        flat = t.axis[0] != 0
        for c in cells_of(heads[i], t.axis, lengths[i], p):
            occupied.setdefault(c, []).append((i, flat))

    moved: set[tuple[str, int, tuple[int, int]]] = set()

    def crossing(cell: tuple[int, int], want_flat: bool,
                 skip: tuple[int, tuple[int, int]] | None) -> bool:
        """Is a segment lying along the asked-for axis at this cell?

        `skip` excuses the segment doing the pushing, and ONLY that one. A cell can hold
        two segments at once — one tube standing where another crosses — and excusing the
        whole cell was measured to make the tool believe it could drag a tile out of a
        crossing tube. It cannot, and the two plans that follow from the two beliefs are
        exact inverses, so the tool oscillated until the level's budget ran out.
        """
        for idx, flat in occupied.get(cell, ()):
            if flat == want_flat and (idx, cell) != skip:
                return True
        return False

    def push(kind: str, owner: int, cell: tuple[int, int],
             parent: tuple[int, tuple[int, int]] | None) -> bool:
        key = (kind, owner, cell)
        if key in moved:
            return True
        if board.blocked(cell, move):
            # A segment being drawn back toward its own nozzle, or one already standing
            # outside the rectangle, is exempt: that is how a tube retracts off the edge.
            exempt = kind == "seg" and (board.tubes[owner].axis == _neg(move)
                                        or board.stuck(cell))
            if not exempt:
                return False
        if kind == "seg":
            flat_axis = board.tubes[owner].axis[0] != 0
            for off in ((0, 0), move):
                at = (cell[0] + off[0] * p, cell[1] + off[1] * p)
                if at not in tiles:
                    continue
                if not push("tile", -1, at, (owner, cell)) and flat_axis == (move[0] == 0):
                    # Sliding across the axis into a tile that cannot give way stops
                    # everything. Advancing ALONG the axis instead swallows it. The test
                    # is whether the segment lies ACROSS the move, and it reads backwards:
                    # a flat segment asked to go up or down is the crossing case.
                    return False
        else:
            want_flat = move[0] == 0
            for off in ((0, 0), move):
                at = (cell[0] + off[0] * p, cell[1] + off[1] * p)
                if crossing(at, want_flat, parent):
                    return False
            dest = (cell[0] + move[0] * p, cell[1] + move[1] * p)
            if dest in tiles and not push("tile", -1, dest, None):
                return False
        moved.add(key)
        return True

    head, length = heads[active], lengths[active]
    if move == axis:                                       # extend
        if board.blocked(segs[-1], move):
            return None
        for c in segs:
            push("seg", active, c, None)
        length += 1
    elif move == _neg(axis):                               # retract
        if length == 1:
            return None
        for c in segs[1:]:
            push("seg", active, c, None)
        length -= 1
    else:                                                  # slide along the rail
        if not board.rail_ok(active, head, move):
            return None
        for c in segs:
            if not push("seg", active, c, None):
                return None
        head = (head[0] + move[0] * p, head[1] + move[1] * p)

    shifted = {c for kind, _, c in moved if kind == "tile"}
    fresh = {}
    for cell, colour in tiles.items():
        if cell in shifted:
            fresh[(cell[0] + move[0] * p, cell[1] + move[1] * p)] = colour
        else:
            fresh[cell] = colour
    new_heads = heads[:active] + (head,) + heads[active + 1:]
    new_lengths = lengths[:active] + (length,) + lengths[active + 1:]
    return new_heads, new_lengths, fresh


def _held(board: Board, heads: tuple, lengths: tuple, tiles: dict, idx: int) -> list[int]:
    tube = board.tubes[idx]
    run = cells_of(heads[idx], tube.axis, lengths[idx], board.p)
    return [tiles[c] for c in run if c in tiles]


def _satisfied(board: Board, heads: tuple, lengths: tuple, tiles: dict) -> bool:
    for i, tube in enumerate(board.tubes):
        want = tube.demand
        if want is None:
            continue
        got = _held(board, heads, lengths, tiles, i)
        if len(got) < len(want) or got[: len(want)] != want:
            return False
    return True


def _progress(board: Board, heads: tuple, lengths: tuple,
              tiles: dict) -> tuple[int, int, int]:
    """How near this arrangement is: (tubes done, matching prefixes, order kept)."""
    done = pre_total = keep_total = 0
    for i, tube in enumerate(board.tubes):
        want = tube.demand
        if want is None:
            continue
        got = _held(board, heads, lengths, tiles, i)
        pre = 0
        while pre < len(want) and pre < len(got) and got[pre] == want[pre]:
            pre += 1
        if pre == len(want) and len(got) >= len(want):
            done += 1
        # Longest run of the demand appearing in order anywhere under the tube: it
        # separates an arrangement that has the right tiles in the right sequence but
        # shifted along the tube from one that merely has the right tiles.
        keep = 0
        for colour in got:
            if keep < len(want) and colour == want[keep]:
                keep += 1
        pre_total += pre
        keep_total += keep
    return done, pre_total, keep_total


Move = tuple[str, Any]


def plan(board: Board, active: int, cap: int = _NODE_CAP) -> list[Move] | None:
    """Search (which tube has the keys, every nozzle, every length, every tile).

    Breadth first while that is affordable, because a shallow board deserves the shortest
    route; then a weighted A* whose cost is the route so far and whose estimate is the
    number of demanded slots still unspelled, priced at `_SLOT_COST` moves each.

    The weight is the whole game, and it was MEASURED. Ordering the frontier purely by how
    much of the demand an arrangement already spells — no route length in the score at all
    — solves the crossing board in 291,000 states, and only from one of the two readings of
    who holds the keys; the same board with the route length restored and each missing slot
    priced at eight moves solves in 76,000, from either reading, in two seconds. Pure greed
    wanders down long corridors that spell one more colour and never come back.
    """
    heads0 = tuple(t.head for t in board.tubes)
    lengths0 = tuple(t.length for t in board.tubes)
    if _satisfied(board, heads0, lengths0, board.tiles):
        return []
    hands = board.selectable()
    slots = sum(len(t.demand) for t in board.tubes if t.demand is not None)
    start = (active, heads0, lengths0, tuple(sorted(board.tiles.items())))
    seen: dict[tuple, tuple[int, Move | None, int]] = {start: (-1, None, 0)}
    order = [start]

    def route_to(node: int) -> list[Move]:
        out: list[Move] = []
        while node > 0:
            back, mv, _ = seen[order[node]]
            assert mv is not None
            out.append(mv)
            node = back
        return out[::-1]

    def expand(node: int) -> int | None:
        cur = order[node]
        who, heads, lengths = cur[0], cur[1], cur[2]
        tiles = dict(cur[3])
        depth = seen[cur][2] + 1
        options: list[Move] = [("mv", d) for d in _DIRS]
        options += [("sel", k) for k in hands if k != who]
        for mv in options:
            if mv[0] == "sel":
                key = (mv[1], heads, lengths, cur[3])
                nh, nl, nt = heads, lengths, tiles
            else:
                out = _step(board, heads, lengths, tiles, who, mv[1])
                if out is None:
                    continue
                nh, nl, nt = out
                key = (who, nh, nl, tuple(sorted(nt.items())))
            if key in seen:
                continue
            seen[key] = (node, mv, depth)
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
        pool: list[tuple[int, int]] = []

        def offer(node: int) -> None:
            st = order[node]
            _, pre, keep = _progress(board, st[1], st[2], dict(st[3]))
            cost = seen[st][2] + _SLOT_COST * (slots - pre) - keep
            heapq.heappush(pool, (cost, node))

        for node in range(i, len(order)):
            offer(node)
        while pool and len(seen) < cap:
            node = heapq.heappop(pool)[1]
            frontier = len(order)
            hit = expand(node)
            if hit is not None:
                return route_to(hit)
            for fresh in range(frontier, len(order)):
                offer(fresh)
    return None


# --- perception -------------------------------------------------------------

def _strip_top(g: np.ndarray, bg: int, panel: int) -> int:
    """First row of the demand panel.

    The band at the bottom is the run of rows the panel's own colour OWNS. Reading it as
    "the rows the background never shows through" is what an earlier version did, and it
    fails the moment a fixture down there is DRAWN in the background colour: measured on a
    board whose two panel nozzles are, which put the band's edge eight rows too low and
    lost every demand on it. Any single-colour rule between the band and the board is
    chrome, and is peeled off.
    """
    h = g.shape[0]
    y = h - 1
    while y >= 0 and Counter(int(v) for v in g[y]).most_common(1)[0][0] == panel:
        y -= 1
    top = y + 1
    while top < h and len(set(int(v) for v in g[top])) <= 2 \
            and panel not in set(int(v) for v in g[top]):
        top += 1
    return top if h // 2 < top < h - 1 else -1


def _field_rect(g: np.ndarray, panel: int, limit: int) -> tuple[int, int, int, int] | None:
    """The play rectangle: where the panel colour is laid down thickly above the band.

    A projection, not a component: a tube can cut the rectangle's colour clean in two
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


def _signature(g: np.ndarray, cell: tuple[int, int], p: int) -> tuple:
    """A rotation-blind fingerprint of a nozzle's casing.

    Which nozzle on the board owes which run in the panel is not written anywhere: the two
    are simply DRAWN as the same fixture, and one of them may be turned on its side. A
    colour census of the cell survives that quarter turn where a pixel comparison does not.
    """
    x, y = cell
    patch = g[y:y + p, x:x + p]
    return tuple(sorted(Counter(int(v) for v in patch.ravel()).items()))


def _chains(g: np.ndarray, top: int, p: int) -> list[tuple[list[tuple[int, int]], tuple[int, int]]]:
    """Every run of flat segments in the panel band, at any lattice phase.

    The panel's own lattice need not share the board's phase, so it is scanned at every
    offset; a run that has no nozzle at either end is an alias of a real one read half a
    cell over, and is dropped by the caller.
    """
    found = []
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
            found.append((chain, e))
    return found


def _chrome(g: np.ndarray, bg: int, top: int) -> tuple[set[int], set[int]]:
    """Rows and columns above the panel that the background never shows through.

    This game draws its remaining budget as a bar pinned across one whole row, and the bar
    is TWO colours with a moving boundary — which is a nozzle's lip exactly. Measured: at
    the moment the bar had drained to the right column, a phantom tube appeared in the
    corner beside the field and the route was thrown away mid-level. A counter is not board
    content, and the thing that separates it from board content is that the board's own
    background never appears in its lane.
    """
    rows = {y for y in range(top) if not (g[y] == bg).any()}
    cols = {x for x in range(g.shape[1]) if not (g[:top, x] == bg).any()}
    return rows, cols


def _rail_span(g: np.ndarray, head: tuple[int, int], axis: tuple[int, int], p: int,
               bg: int, rect: tuple[int, int, int, int], top: int,
               occupied: set[tuple[int, int]],
               chrome: tuple[set[int], set[int]]) -> tuple[int, int]:
    """How far this nozzle's track reaches across its own lane.

    Read only inside the nozzle's lane, and only for pixels no tube already explains. A
    SECOND tube parked in the same lane is otherwise counted as track and offers a slide
    that does not exist — measured on a board whose two nozzles share the top edge, where
    the tool then planned a sideways move the game refuses. The nozzle hides the stretch of
    track it stands on, so its own centre is seeded into the span; without that the track
    reads short at whichever end the nozzle happens to be resting.
    """
    fx0, fy0, fx1, fy1 = rect
    o = p // 2 - 1
    chrome_rows, chrome_cols = chrome

    def lattice(x: int, y: int) -> tuple[int, int]:
        return (fx0 + p * ((x - fx0) // p), fy0 + p * ((y - fy0) // p))

    if axis[0]:
        lo, hi = head[1] + o, head[1] + o + 1
        for y in range(top):
            if y in chrome_rows or head[1] <= y < head[1] + p:
                continue
            for x in range(head[0], min(head[0] + p, g.shape[1])):
                if int(g[y, x]) == bg or (fx0 <= x < fx1 and fy0 <= y < fy1):
                    continue
                if lattice(x, y) in occupied:
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
                if lattice(x, y) in occupied:
                    continue
                lo, hi = min(lo, x), max(hi, x)
    return lo, hi


def _walk(g: np.ndarray, head: tuple[int, int], axis: tuple[int, int], p: int,
          pair: tuple[int, int]) -> list[tuple[int, int]]:
    reader = _seg_edges if axis[0] else _seg_edges_v
    step = (axis[0] * p, axis[1] * p)
    run = [head]
    nxt = (head[0] + step[0], head[1] + step[1])
    while reader(g, nxt[0], nxt[1], p) == pair:
        run.append(nxt)
        nxt = (nxt[0] + step[0], nxt[1] + step[1])
    return run


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

    # --- the demands, one flat run per nozzle in the panel band
    demands: list[tuple[tuple, list[int], tuple[int, int], frozenset[int]]] = []
    for chain, pair in _chains(g, top, p):
        mouth = None
        for cand in ((chain[0][0] - p, chain[0][1]), (chain[-1][0] + p, chain[-1][1])):
            for axis in ((1, 0), (-1, 0)):
                if _is_mouth(g, cand[0], cand[1], p, pair, axis):
                    if mouth is not None and mouth != cand:
                        return None
                    mouth = cand
        if mouth is None:
            continue
        run = sorted(set(chain) | {mouth})
        if run[0] != mouth:
            run = run[::-1]
        want = [c for c in (_tile_at(g, q, p, bg, panel) for q in run) if c is not None]
        want = want[: len(run) - 1]
        if not want:
            return None
        centre = (mouth[0] + p // 2, mouth[1] + p // 2)
        demands.append((_signature(g, mouth, p), want, centre, frozenset(pair)))
    if not demands:
        return None
    if len({d[0] for d in demands}) != len(demands):
        return None                      # two runs owed to fixtures we cannot tell apart

    # --- the tubes on the board, whatever colours they wear
    lattice_x = list(range(fx0 - p, fx1 + p, p))
    lattice_y = list(range(fy0 - p, min(fy1 + p, top), p))
    pairs_h: set[tuple[int, int]] = set()
    pairs_v: set[tuple[int, int]] = set()
    for x in lattice_x:
        for y in lattice_y:
            e = _seg_edges(g, x, y, p)
            if e:
                pairs_h.add(e)
            e = _seg_edges_v(g, x, y, p)
            if e:
                pairs_v.add(e)
    for _, _, _, group in demands:
        for a, b in ((min(group), max(group)), (max(group), min(group))):
            pairs_h.add((a, b))
            pairs_v.add((a, b))
    if len(pairs_h) > 4 or len(pairs_v) > 4:
        return None

    chrome = _chrome(g, bg, top)
    tubes: list[Tube] = []
    for x in lattice_x:
        for y in lattice_y:
            cell = (x, y)
            if not (x < fx0 or x + p > fx1 or y < fy0 or y + p > fy1):
                continue
            if any(r in chrome[0] for r in range(y, y + p)) \
                    or any(c in chrome[1] for c in range(x, x + p)):
                continue
            hit = None
            for axis in _DIRS:
                for pair in (pairs_h if axis[0] else pairs_v):
                    if _is_mouth(g, x, y, p, pair, axis):
                        if hit is not None:
                            return None  # a cell that reads as two nozzles at once
                        hit = (axis, pair)
            if hit is None:
                continue
            axis, pair = hit
            run = _walk(g, cell, axis, p, pair)
            tube = Tube(cell, axis, len(run), frozenset(pair))
            tubes.append(tube)
    if not tubes or len(tubes) < len(demands):
        return None

    for tube in tubes:
        sig = _signature(g, tube.head, p)
        for owed_sig, want, centre, _ in demands:
            if owed_sig == sig:
                if tube.demand is not None:
                    return None
                tube.demand, tube.click = want, centre
    if sum(1 for t in tubes if t.demand is not None) != len(demands):
        return None

    # --- the field: a tile, a hole in the floor, or nothing
    tiles: dict[tuple[int, int], int] = {}
    walls: set[tuple[int, int]] = set()
    for x in range(fx0, fx1, p):
        for y in range(fy0, fy1, p):
            colour = _tile_at(g, (x, y), p, bg, panel)
            if colour is not None:
                tiles[(x, y)] = colour
            elif np.all(g[y:y + p, x:x + p] == bg):
                walls.add((x, y))
    if not tiles:
        return None

    occupied: set[tuple[int, int]] = set()
    for tube in tubes:
        occupied.update(cells_of(tube.head, tube.axis, tube.length, p))
    for tube in tubes:
        lo, hi = _rail_span(g, tube.head, tube.axis, p, bg, rect, top, occupied, chrome)
        if lo > hi:
            return None
        tube.rail = (lo, hi)
    return Board(p, rect, tubes, tiles, walls)


def _candidates(board: Board) -> list[int]:
    """Which tube might be holding the keys right now.

    Only one pair on the board answers the keys, and it is drawn in its own two colours
    while every other tube wears the shared pair. So a colour group carrying TWO board
    tubes cannot be the live one, which on the crowded boards leaves exactly one answer;
    where two groups each carry one tube the frame does not say, and both are offered. A
    route that opens with a hand-over is right under either reading, so the tool prefers
    one; when no such route exists the board itself settles it in a single action.
    """
    by_group: dict[frozenset[int], list[int]] = {}
    for i, tube in enumerate(board.tubes):
        by_group.setdefault(tube.group, []).append(i)
    out = [members[0] for members in by_group.values() if len(members) == 1]
    return out or list(range(len(board.tubes)))


# --- the tool ---------------------------------------------------------------

class TubeOrderTool:
    """Plan a tube board to its demanded runs, or stand down.

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
        self._route: list[Move] = []
        self._board: Board | None = None
        self._key: str | None = None
        self._at: tuple | None = None
        self._pending: tuple[Board, tuple[int, int], int] | None = None
        self._active = 0
        self._ruled_out: set[int] = set()
        self._issued = 0
        self._level = -1
        # One failed search per level is enough. The tool takes no action when it has no
        # route, so nothing it does can change the board into a solvable one, and the
        # search is seconds of work that would otherwise be repeated every single turn.
        self._surrendered = False

    @staticmethod
    def _state(board: Board) -> tuple:
        return (tuple(t.head for t in board.tubes),
                tuple(t.length for t in board.tubes),
                tuple(sorted(board.tiles.items())))

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
        if len(before.tubes) != len(board.tubes):
            return
        actual = self._state(board)
        heads = tuple(t.head for t in before.tubes)
        lengths = tuple(t.length for t in before.tubes)
        matches = []
        for cand in _DIRS:
            out = _step(before, heads, lengths, before.tiles, self._active, cand)
            if out is None:
                continue
            if (out[0], out[1], tuple(sorted(out[2].items()))) == actual:
                matches.append(cand)
        if len(matches) != 1 or matches[0] == move:
            return
        truth = matches[0]
        self._keys[move], self._keys[truth] = self._keys[truth], aid

    def _search(self, board: Board) -> bool:
        """Plan under every reading of who holds the keys, and keep the safest route."""
        best: tuple[int, int, list[Move], int] | None = None
        reading = _candidates(board)
        # An opening hand-over makes the route right under EVERY reading, and is worth its
        # one action only when the frame leaves more than one reading open.
        unsure = len(reading) > 1
        for guess in reading:
            if guess in self._ruled_out:
                continue
            route = plan(board, guess)
            if route is None:
                continue
            if route and route[0][0] != "sel" and board.tubes[guess].click and unsure:
                route = [("sel", guess)] + route
            blind = 0 if (route and route[0][0] == "sel") else 1
            rank = (blind, len(route), route, guess)
            if best is None or rank[:2] < best[:2]:
                best = rank
        if best is None:
            return False
        _, _, self._route, self._active = best
        self._board = board
        return True

    def _study(self, obs: Any) -> bool:
        if not has_frame(obs):
            return False
        g = _settled(obs)
        done = levels_completed(obs)
        if done != self._level:
            self._level = done
            self._route, self._board, self._key = [], None, None
            self._expect, self._pending = None, None
            self._ruled_out = set()
            self._surrendered = False
        digest = base_hash(g)
        if digest == self._key:
            # A hand-over leaves the board untouched, so an unchanged frame is exactly what
            # it looks like and the route must carry on. A MOVE that changes nothing is a
            # different animal — the rule was misread — and the only tell is that the board
            # has now ignored two actions running. Count actions issued, not frames looked
            # at: the harness studies the same frame twice per turn, and counting looks
            # made the tool throw away a good route after one free hand-over.
            if self._issued < 2:
                return bool(self._route)
            self._route, self._at = [], None
        self._issued = 0
        self._key = digest
        board = parse(g)
        if board is None:
            self._route, self._board = [], None
            self._pending = None
            return False
        if self._pending is not None:
            self._rebind(board)
        state = self._state(board)
        if self._at is not None:
            if state == self._at:
                self._board, self._at = board, None
                if self._route:
                    return True
            else:
                # The board did not do what the route said it would, so the reading of who
                # holds the keys was wrong. Drop that reading rather than the whole board.
                self._ruled_out.add(self._active)
                self._route, self._at = [], None
        if self._surrendered or digest in self._dead:
            self._route, self._board = [], None
            return False
        if not self._search(board):
            self._dead.add(digest)
            self._surrendered = True
            self._route, self._board = [], None
            return False
        return bool(self._route)

    def detect(self, frames: list[Any], obs: Any) -> float:
        return 0.95 if self._study(obs) else 0.0

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Nothing is learned here: the correction needs the frame AFTER the action."""

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not self._study(obs) or not self._route:
            return []
        board = self._board
        assert board is not None
        kind, arg = self._route[0]
        heads = tuple(t.head for t in board.tubes)
        lengths = tuple(t.length for t in board.tubes)
        if kind == "sel":
            self._active = arg
            self._at = (heads, lengths, tuple(sorted(board.tiles.items())))
            self._pending = None
            self._route = self._route[1:]
            self._issued += 1
            return [(_CLICK, board.tubes[arg].click)]
        key = self._keys[arg]
        out = _step(board, heads, lengths, board.tiles, self._active, arg)
        if out is None:
            self._route = []
            return []
        self._at = (out[0], out[1], tuple(sorted(out[2].items())))
        self._pending = (board, arg, key)
        self._route = self._route[1:]
        self._issued += 1
        return [(key, None)]
