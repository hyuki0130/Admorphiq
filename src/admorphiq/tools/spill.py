"""Spill tool — deflect a scripted flow into every cup by placing the pieces.

The mechanic, recovered from frames. The board has three fixed things and one movable one:
emitters that release a stream, cup-shaped sinks with a one-cell mouth notch, and a lethal band
pinned along a board edge; between them sit bars and elbows the player may slide. One action
commits, and the whole spill then plays out inside that SINGLE action — the observation comes
back carrying every tick of it as a separate layer. The level clears when the settled flow has
entered EVERY cup by its mouth and has touched the lethal band nowhere.

⛔ Why plan rather than explore. Measured before this tool existed: the searching generic path
spent **3,274 actions** on the first level and scored 0.0000, against a human baseline of 39 —
and the level's own data declares a budget of 30 board-changing actions, past which the game
ends. There is no exploration budget here to spend. The tool instead recovers the propagation
rule, runs it as a SIMULATOR over candidate placements, and commits only to a placement its own
model says wins.

⛔ Nothing is assumed about which way is down. Gravity is DERIVED — a cup's mouth opens against
the flow, so the direction from a mouth into its own body is the flow direction, cross-checked
against each emitter's droplet sitting one cell downstream of it. Two of the six boards render
rotated, and a tool that assumed "down" would drive every piece the wrong way on them.

⛔ A wrong commit is not free: the board keeps its layout but the attempt counter does not reset,
and the game ENDS on the fifth. So the tool commits only on a predicted win, and a commit that
loses anyway retires that exact layout from the search rather than being retried.
"""

from __future__ import annotations

import heapq
import time
from collections import Counter, deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, connected_components, has_frame, levels_completed

__all__ = ["SpillRouteTool"]

Cell = tuple[int, int]

# Display-space deltas to the simple action that produces them. The board is rendered rotated on
# some levels AND the controls are rotated with it, so the display always reads naturally.
_MOVES: dict[Cell, int] = {(-1, 0): 1, (1, 0): 2, (0, -1): 3, (0, 1): 4}
_COMMIT = 5

# A piece may not sit closer than this to the emitter edge — measured as a hard refusal by the
# engine, and a plan that ignores it silently loses the moves it spends pushing into the wall.
_HEAD_ROOM = 3
_MAX_TICKS = 400          # a spill that has not settled by here is a model failure, not a win
_MAX_COST = 40            # deepest action cost the placement search will consider
_EXACT_COST = 12          # ... and how far the cheapest-first pass sweeps before handing over
_EXACT_BUDGET = 60000     # placements the cheapest-first pass may simulate
_SIM_BUDGET = 250000      # placements the flow-guided pass may simulate
_MAX_MOVED = 4            # pieces one plan may relocate
_MISS_WEIGHT = 3          # how hard an unfilled cup pulls the best-first search
_MAX_COMMITS = 4          # the fifth commit ends the game
# ⛔ A wall-clock stop as well as a placement count. The two are not the same guard: a board with
# more pieces makes every placement more expensive, so a budget that costs seconds on one board
# can cost minutes on another, and a plan that never returns holds up the whole measurement.
_PLAN_SECONDS = 25.0


class Piece:
    """One movable object: its cells, and which of them emit."""

    __slots__ = ("cells", "kind", "origin", "emits", "colour")

    def __init__(self, cells: list[Cell], kind: str, emits: list[Cell], colour: int) -> None:
        top = (min(c[0] for c in cells), min(c[1] for c in cells))
        self.origin = top
        self.cells = tuple(sorted((c[0] - top[0], c[1] - top[1]) for c in cells))
        self.emits = tuple(sorted((c[0] - top[0], c[1] - top[1]) for c in emits))
        self.kind = kind
        self.colour = colour

    def at(self, origin: Cell) -> list[Cell]:
        return [(origin[0] + dy, origin[1] + dx) for dy, dx in self.cells]

    def emitters(self, origin: Cell) -> list[Cell]:
        return [(origin[0] + dy, origin[1] + dx) for dy, dx in self.emits]


class Board:
    """Everything the simulator needs, all of it derived from one frame."""

    __slots__ = ("n", "scale", "off", "grav", "sinks", "hazard", "pieces", "emitters", "waters")

    def __init__(self, n: int, scale: int, off: int, grav: Cell) -> None:
        self.n = n
        self.scale = scale
        self.off = off
        self.grav = grav
        self.sinks: list[tuple[frozenset[Cell], Cell]] = []   # (body cells, bbox as y0,x0,y1,x1)
        self.hazard: set[Cell] = set()
        self.pieces: list[Piece] = []
        self.emitters: set[Cell] = set()
        self.waters: set[Cell] = set()


# --- reading the board -------------------------------------------------------

def _grid(obs: Any) -> np.ndarray:
    """The SETTLED frame. A commit returns the whole spill animation; its last layer is the board."""
    arr = np.asarray(getattr(obs, "frame", None))
    if arr.ndim >= 3:
        arr = arr[-1]
    return arr.astype(int)


def _blocks(px: np.ndarray, n: int, s: int, off: int) -> tuple[np.ndarray, float]:
    """The board at `n` cells of side `s`, and how flat those cells actually are.

    ⛔ A cell's value is its CENTRE pixel, never its corner: one pixel row of the frame is a
    progress bar painted over the board, so a corner read returns the bar on every cell of the
    row it crosses. For the same reason a cell counts as flat when all but one of its rows agree.
    """
    grid = px[off:off + n * s, off:off + n * s]
    blocks = grid.reshape(n, s, n, s).transpose(0, 2, 1, 3).reshape(n, n, s * s)
    mid = blocks[:, :, (s // 2) * s + s // 2]
    agree = (blocks == mid[:, :, None]).sum(-1)
    return mid, float((agree >= s * s - s).mean())


def _lattice(px: np.ndarray) -> tuple[int, int, int] | None:
    """Cell size and letterbox offset, coarsest first."""
    h = px.shape[0]
    for s in range(8, 1, -1):
        for off in (0, 1, 2, 3, 4):
            span = h - 2 * off
            if span <= 0 or span % s:
                continue
            n = span // s
            if not 8 <= n <= 32:
                continue
            if _blocks(px, n, s, off)[1] >= 0.95:
                return n, s, off
    return None


def _downsample(px: np.ndarray, n: int, s: int, off: int) -> np.ndarray:
    return _blocks(px, n, s, off)[0]


def _cup(cells: list[Cell]) -> tuple[Cell, Cell] | None:
    """(mouth, the direction a flow must be travelling to enter it), or None for other shapes.

    A cup is a solid 3x2 rectangle with exactly the middle of one long side missing — that gap is
    the only place the flow is accepted, which is why the shape and not the colour identifies it.
    """
    if len(cells) != 5:
        return None
    y0, x0 = min(c[0] for c in cells), min(c[1] for c in cells)
    y1, x1 = max(c[0] for c in cells), max(c[1] for c in cells)
    hgt, wid = y1 - y0 + 1, x1 - x0 + 1
    if {hgt, wid} != {2, 3}:
        return None
    hole = [(y, x) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1) if (y, x) not in set(cells)]
    if len(hole) != 1:
        return None
    my, mx = hole[0]
    if wid == 3 and mx == x0 + 1 and my in (y0, y1):
        return hole[0], ((1, 0) if my == y0 else (-1, 0))
    if hgt == 3 and my == y0 + 1 and mx in (x0, x1):
        return hole[0], ((0, 1) if mx == x0 else (0, -1))
    return None


def _shape_of(cells: list[Cell]) -> str:
    """`bar` for a solid straight run, `angle` for a three-cell elbow, else empty."""
    y0, x0 = min(c[0] for c in cells), min(c[1] for c in cells)
    y1, x1 = max(c[0] for c in cells), max(c[1] for c in cells)
    hgt, wid = y1 - y0 + 1, x1 - x0 + 1
    if len(cells) == hgt * wid and min(hgt, wid) == 1 and max(hgt, wid) >= 2:
        return "bar"
    if len(cells) == 3 and hgt == 2 and wid == 2:
        return "angle"
    return ""


def _read(px: np.ndarray) -> Board | None:
    """Recover the whole mechanic from one frame, or return None when it is not this one."""
    lat = _lattice(px)
    if lat is None:
        return None
    n, s, off = lat
    g = _downsample(px, n, s, off)
    bg = Counter(int(v) for v in g.ravel()).most_common(1)[0][0]

    # The lethal band is a board edge line rendered end to end in one colour. Reading it off the
    # edge rather than off a colour keeps a bar piece that happens to lie along an edge out of it.
    hazard: set[Cell] = set()
    lines = [
        [(0, c) for c in range(n)], [(n - 1, c) for c in range(n)],
        [(r, 0) for r in range(n)], [(r, n - 1) for r in range(n)],
    ]
    for line in lines:
        colours = {int(g[y][x]) for y, x in line}
        if len(colours) == 1 and colours.pop() != bg:
            hazard.update(line)

    comps = [c for c in connected_components(g, background=bg)
             if not set(c["cells"]) & hazard]
    cups = [(c, _cup(c["cells"])) for c in comps]
    cups = [(c, m[0], m[1]) for c, m in cups if m is not None]
    if not cups:
        return None
    sink_cells = {c for comp, _, _ in cups for c in comp["cells"]}
    rest = [c for c in comps if not set(c["cells"]) & sink_cells]
    singles = [c for c in rest if len(c["cells"]) == 1]
    solids = [c for c in rest if len(c["cells"]) > 1]
    lone = {c["cells"][0]: int(c["color"]) for c in singles}

    # ⛔ Gravity comes from the EMITTERS, with the cups only voting. A cup may be turned to face
    # any side — one board has cups opening up, left and right at once — so a majority of mouths
    # points the wrong way, and a tool that trusts them drives every piece across the board.
    # An emitter is a lone cell against the board's rim with its first droplet one step inside,
    # and that pair names the flow direction outright.
    votes: Counter[Cell] = Counter()
    for a, ca in lone.items():
        for step in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            b = (a[0] + step[0], a[1] + step[1])
            if lone.get(b, ca) == ca:
                continue
            rim_a = a[0] in (0, n - 1) or a[1] in (0, n - 1)
            rim_b = b[0] in (0, n - 1) or b[1] in (0, n - 1)
            votes[step] += 10 if rim_a and not rim_b else 1
    if not votes:
        return None
    for _, _, facing in cups:
        if facing in votes:
            votes[facing] += 3
    grav = votes.most_common(1)[0][0]

    board = Board(n, s, off, grav)
    board.hazard = hazard
    for comp, mouth, _ in cups:
        cells = frozenset(comp["cells"]) | {mouth}
        y0 = min(c[0] for c in cells)
        x0 = min(c[1] for c in cells)
        y1 = max(c[0] for c in cells)
        x1 = max(c[1] for c in cells)
        board.sinks.append((frozenset(comp["cells"]), (y0, x0, y1, x1)))

    # The same pair now names both colours at once: upstream cell is an emitter, downstream is
    # the flow itself.
    pair = [(a, b) for a in lone for b in lone
            if b == (a[0] + grav[0], a[1] + grav[1]) and lone[a] != lone[b]]
    if not pair:
        return None
    emit_colour = Counter(lone[a] for a, _ in pair).most_common(1)[0][0]
    water_colour = Counter(lone[b] for _, b in pair).most_common(1)[0][0]
    board.emitters = {c for c, col in lone.items() if col == emit_colour}
    board.waters = {c for c, col in lone.items() if col == water_colour}
    if not board.waters:
        return None

    # A piece with an emitter in it renders as two runs either side of the emitter cell; rejoin
    # them, or the flow model loses both the piece's true width and its source.
    owned: dict[int, list[Cell]] = {}
    inner: dict[int, list[Cell]] = {}
    colour: dict[int, int] = {}
    index = {}
    for i, comp in enumerate(solids):
        owned[i] = list(comp["cells"])
        inner[i] = []
        colour[i] = int(comp["color"])
        for c in comp["cells"]:
            index[c] = i
    merged = {i: i for i in owned}

    def _root(i: int) -> int:
        while merged[i] != i:
            i = merged[i]
        return i

    for cell in sorted(board.emitters):
        near = {_root(index[(cell[0] + dy, cell[1] + dx)])
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if (cell[0] + dy, cell[1] + dx) in index}
        if not near:
            continue
        keep = min(near)
        for other in near:
            merged[other] = keep
        owned[keep].append(cell)
        inner[keep].append(cell)
        board.emitters.discard(cell)
        index[cell] = keep

    for i in list(owned):
        r = _root(i)
        if r != i:
            owned[r].extend(owned[i])
            inner[r].extend(inner[i])
            del owned[i]
    for i, cells in owned.items():
        kind = _shape_of(cells)
        if kind:
            board.pieces.append(Piece(cells, kind, inner[i], colour[i]))
    if not board.pieces:
        return None
    return board


# --- the propagation rule ----------------------------------------------------

def _axis(grav: Cell) -> tuple[Cell, Cell]:
    """(left, right) of the flow — the two ways it is pushed aside by an obstruction."""
    return (grav[1], -grav[0]), (-grav[1], grav[0])


# Occupancy codes. `_INERT` covers the boundary and the emitter bodies alike: the engine gives a
# droplet no response there, so it simply stops.
_EMPTY, _WATER, _BAR, _ELBOW, _CUP, _LETHAL, _INERT = 0, 1, 2, 3, 4, 5, 6


def _spill(board: Board, layout: tuple[Cell, ...]) -> tuple[bool, int, int, frozenset[Cell]]:
    """Run the flow over one candidate placement.

    -> (clears, cups filled, droplets lost to the band, cells the flow reached). The last two are
    not diagnostics, they are what makes the search tractable: lost droplets give the placement
    search a gradient where "did it clear" gives it none, and a piece the flow never touches
    cannot change the outcome, so only placements standing IN the flow are worth simulating.

    Every branch mirrors one measured engine response: advance into empty space, queue behind the
    flow's own front, split sideways past a bar, satisfy a cup only from between its own two
    flanks, turn at an elbow met on one side, die on the lethal band, stop at the boundary.
    """
    n = board.n
    span = n + 2                      # a one-cell pad, so no step off the board needs a bounds test
    kind = bytearray(span * span)
    owner = [0] * (span * span)
    for i in range(span):
        kind[i] = kind[(span - 1) * span + i] = _INERT
        kind[i * span] = kind[i * span + span - 1] = _INERT

    def at(cell: Cell) -> int:
        return (cell[0] + 1) * span + cell[1] + 1

    for c in board.hazard:
        kind[at(c)] = _LETHAL
    for i, (body, _) in enumerate(board.sinks):
        for c in body:
            j = at(c)
            kind[j], owner[j] = _CUP, i
    for c in board.emitters:
        kind[at(c)] = _INERT
    sources = [at(c) for c in board.emitters]
    for i, piece in enumerate(board.pieces):
        tag = _BAR if piece.kind == "bar" else _ELBOW
        for c in piece.at(layout[i]):
            j = at(c)
            kind[j], owner[j] = tag, i
        sources.extend(at(c) for c in piece.emitters(layout[i]))

    grav = board.grav
    back = (-grav[0], -grav[1])
    left, right = _axis(grav)
    flat = {}
    for step in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        p1, p2 = (left, right) if step in (grav, back) else (back, grav)
        flat[step[0] * span + step[1]] = (
            p1[0] * span + p1[1], p2[0] * span + p2[1],
            -step[1] * span + step[0], step[1] * span - step[0],
        )
    down = grav[0] * span + grav[1]

    wet: set[int] = set()
    front: list[tuple[int, int]] = []
    for c in sorted(board.waters):
        j = at(c)
        kind[j] = _WATER
        wet.add(j)
        front.append((j, down))
    for j in sorted(sources):
        tgt = j + down
        if kind[tgt] == _EMPTY:
            kind[tgt] = _WATER
            wet.add(tgt)
            front.append((tgt, down))

    filled: set[int] = set()
    doomed = 0
    for _ in range(_MAX_TICKS):
        if not front:
            break
        nxt: list[tuple[int, int]] = []
        for pos, d in front:
            p1, p2, turn_a, turn_b = flat[d]
            step = pos + d
            k = kind[step]
            if k == _EMPTY:
                kind[step] = _WATER
                wet.add(step)
                nxt.append((step, d))
                continue
            if k == _WATER:
                nxt.append((step, d))
                continue
            if k == _LETHAL:
                doomed += 1
                continue
            if k not in (_BAR, _CUP, _ELBOW):
                continue                       # boundary or emitter body: the droplet stops
            side_a, side_b = pos + p1, pos + p2
            k1, k2 = kind[side_a], kind[side_b]
            if k == _CUP:
                if k1 == _CUP and k2 == _CUP and owner[side_a] == owner[step] \
                        and owner[side_b] == owner[step]:
                    filled.add(owner[step])
                    continue
            elif k == _ELBOW:
                flank_a = k1 == _ELBOW and owner[side_a] == owner[step]
                flank_b = k2 == _ELBOW and owner[side_b] == owner[step]
                if flank_a and k2 == _EMPTY:
                    tgt = pos + turn_a
                    kind[tgt] = _WATER
                    wet.add(tgt)
                    nxt.append((tgt, turn_a))
                if flank_b and k1 == _EMPTY:
                    tgt = pos + turn_b
                    kind[tgt] = _WATER
                    wet.add(tgt)
                    nxt.append((tgt, turn_b))
                    continue
            # ⛔ Re-read the flanks: a turn may have just filled one of them, and the engine
            # re-queries before spreading. Using the cached value doubles the droplet.
            if kind[side_a] == _EMPTY:
                kind[side_a] = _WATER
                wet.add(side_a)
                nxt.append((side_a, d))
            if kind[side_b] == _EMPTY:
                kind[side_b] = _WATER
                wet.add(side_b)
                nxt.append((side_b, d))
        front = nxt

    cells = frozenset(((j // span) - 1, (j % span) - 1) for j in wet)
    win = not front and not doomed and len(filled) == len(board.sinks)
    return win, len(filled), doomed, cells


# --- placement legality + search ---------------------------------------------

def _depth(cell: Cell, grav: Cell, n: int) -> int:
    if grav[0]:
        return cell[0] if grav[0] > 0 else n - 1 - cell[0]
    return cell[1] if grav[1] > 0 else n - 1 - cell[1]


def _blocked(board: Board) -> set[Cell]:
    """Cells no piece may occupy: the lethal band, the cups, the emitters and the standing flow."""
    out = set(board.hazard) | set(board.emitters) | set(board.waters)
    for body, _ in board.sinks:
        out |= set(body)
    return out


def _legal(board: Board, cells: list[Cell], blocked: set[Cell], others: set[Cell]) -> bool:
    n = board.n
    for y, x in cells:
        if not (0 <= y < n and 0 <= x < n) or (y, x) in blocked:
            return False
        if _depth((y, x), board.grav, n) < _HEAD_ROOM:
            return False
        # ⛔ Pieces are kept apart, not merely non-overlapping: two touching same-colour pieces
        # read back as ONE component on the next frame, and every plan after that is about an
        # object that does not exist.
        for dy, dx in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            if (y + dy, x + dx) in others:
                return False
    y0 = min(c[0] for c in cells)
    x0 = min(c[1] for c in cells)
    y1 = max(c[0] for c in cells)
    x1 = max(c[1] for c in cells)
    for _, (sy0, sx0, sy1, sx1) in board.sinks:
        if y0 <= sy1 + 1 and y1 >= sy0 - 1 and x0 <= sx1 + 1 and x1 >= sx0 - 1:
            return False
    return True


def _reach(board: Board, idx: int, layout: tuple[Cell, ...], limit: int) -> dict[Cell, int]:
    """Every origin the piece can slide to, with the number of presses it takes."""
    piece = board.pieces[idx]
    blocked = _blocked(board)
    others: set[Cell] = set()
    for j, other in enumerate(board.pieces):
        if j != idx:
            others.update(other.at(layout[j]))
    start = layout[idx]
    dist = {start: 0}
    queue: deque[Cell] = deque([start])
    while queue:
        cur = queue.popleft()
        if dist[cur] >= limit:
            continue
        for dy, dx in _MOVES:
            nxt = (cur[0] + dy, cur[1] + dx)
            if nxt in dist:
                continue
            if _legal(board, piece.at(nxt), blocked, others):
                dist[nxt] = dist[cur] + 1
                queue.append(nxt)
    return dist


def _disjoint(board: Board, layout: tuple[Cell, ...]) -> bool:
    taken: set[Cell] = set()
    for i, piece in enumerate(board.pieces):
        cells = piece.at(layout[i])
        for y, x in cells:
            for dy, dx in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                if (y + dy, x + dx) in taken:
                    return False
        taken.update(cells)
    return True


def _search(board: Board, bad: set[tuple[Cell, ...]]) -> tuple[Cell, ...] | None:
    """Cheapest placement whose simulated spill clears.

    Two passes, because the boards are two different problems. Early boards are solved by ONE
    short slide, so an exhaustive cheapest-first sweep returns the minimal action cost — which is
    what the score is made of. Later boards need three or four pieces relocated, where that sweep
    is measured to exhaust 400,000 placements without leaving cost 6; there the search follows the
    FLOW instead, considering only placements that stand in the water's own path.
    """
    base = tuple(p.origin for p in board.pieces)
    reach = [_reach(board, i, base, _MAX_COST) for i in range(len(board.pieces))]
    ranked = [sorted(r.items(), key=lambda kv: kv[1]) for r in reach]
    seen: set[tuple[Cell, ...]] = set()
    stop = time.monotonic() + _PLAN_SECONDS
    hit = _exhaustive(board, bad, base, ranked, seen, stop)
    if hit is not None:
        return hit
    return _guided(board, bad, base, ranked, seen, stop)


def _exhaustive(board: Board, bad: set[tuple[Cell, ...]], base: tuple[Cell, ...],
                ranked: list[list[tuple[Cell, int]]],
                seen: set[tuple[Cell, ...]], stop: float) -> tuple[Cell, ...] | None:
    """Cheapest-first over every combination, until the placement budget runs out."""
    order = sorted(range(len(board.pieces)), key=lambda i: len(ranked[i]))
    budget = _EXACT_BUDGET

    def walk(idx: int, layout: tuple[Cell, ...], cost: int, limit: int) -> tuple[Cell, ...] | None:
        nonlocal budget
        if budget <= 0:
            return None
        if not budget % 2048 and time.monotonic() > stop:
            budget = 0
            return None
        if idx == len(order):
            if layout in seen or layout in bad or not _disjoint(board, layout):
                return None
            seen.add(layout)
            budget -= 1
            return layout if _spill(board, layout)[0] else None
        i = order[idx]
        for tgt, dist in ranked[i]:
            spend = 0 if dist == 0 else dist + 1
            if cost + spend > limit:
                break
            found = walk(idx + 1, layout[:i] + (tgt,) + layout[i + 1:], cost + spend, limit)
            if found is not None:
                return found
        return None

    for limit in range(0, _EXACT_COST + 1):
        found = walk(0, base, 0, limit)
        if found is not None:
            return found
        if budget <= 0:
            return None
    return None


def _guided(board: Board, bad: set[tuple[Cell, ...]], base: tuple[Cell, ...],
            ranked: list[list[tuple[Cell, int]]],
            seen: set[tuple[Cell, ...]], stop: float) -> tuple[Cell, ...] | None:
    """Best-first over placements that intercept the flow, guided by how many cups fill."""
    total = len(board.sinks)
    win, filled, doomed, wet = _spill(board, base)
    if win and base not in bad:
        return base
    tick = 0
    heap: list[tuple[int, int, int, tuple[Cell, ...], frozenset[int], frozenset[Cell]]] = [
        (_MISS_WEIGHT * (total - filled) + doomed, 0, tick, base, frozenset(), wet)
    ]
    budget = _SIM_BUDGET
    while heap and budget > 0 and time.monotonic() < stop:
        _, cost, _, layout, moved, wet = heapq.heappop(heap)
        for i in range(len(board.pieces)):
            if i in moved:
                continue
            piece = board.pieces[i]
            standing = bool(set(piece.at(layout[i])) & wet)
            for tgt, dist in ranked[i]:
                if dist == 0:
                    continue
                spend = cost + dist + 1
                if spend > _MAX_COST:
                    break
                if not standing and not set(piece.at(tgt)) & wet:
                    continue
                nxt = layout[:i] + (tgt,) + layout[i + 1:]
                if nxt in seen or not _disjoint(board, nxt):
                    continue
                seen.add(nxt)
                budget -= 1
                win, filled, doomed, reached = _spill(board, nxt)
                if win and nxt not in bad:
                    return nxt
                if len(moved) + 1 < _MAX_MOVED:
                    tick += 1
                    heapq.heappush(heap, (spend + _MISS_WEIGHT * (total - filled) + doomed,
                                          spend, tick, nxt, moved | {i}, reached))
    return None


# --- the tool ----------------------------------------------------------------

class SpillRouteTool:
    """Recover the flow rule, plan a winning placement, then execute it."""

    name = "spill"

    def __init__(self) -> None:
        self._level: int | None = None
        # The selected colour is a property of the GAME, not the level, so it survives reset: once
        # one click has taught it, every later level knows which piece is live without spending an
        # action to find out.
        self._sel_colour: int | None = None
        self._goal: list[tuple[tuple[Cell, ...], Cell]] = []
        self._bad: set[tuple[Cell, ...]] = set()
        self._commits = 0
        self._pending = False
        self._stuck = False
        self._clicked: Cell | None = None

    def reset(self) -> None:
        self._goal = []
        self._bad = set()
        self._commits = 0
        self._pending = False
        self._stuck = False
        self._clicked = None

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Nothing is carried between frames: the plan is re-derived from the board each turn."""

    # -- protocol ---------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        if not has_frame(obs):
            return 0.0
        simple, six = availability(obs)
        if not six or not {1, 2, 3, 4, 5} <= set(simple):
            return 0.0
        board = _read(_grid(obs))
        if board is None:
            return 0.0
        return 0.85

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        level = levels_completed(obs)
        if level != self._level:
            self._level = level
            self.reset()
        if self._stuck or not has_frame(obs):
            return []
        board = _read(_grid(obs))
        if board is None:
            return []
        if self._clicked is not None:
            # Our own click is the only free way to learn which colour means "live"; reading it
            # off shape or position is a guess, and a wrong one moves the wrong piece.
            for piece in board.pieces:
                if piece.origin == self._clicked and self._sel_colour is None:
                    self._sel_colour = piece.colour
            self._clicked = None
        if self._pending:
            # The commit came back on the same level, so the placement lost. Retire exactly that
            # layout — retrying it would spend one of the four attempts on a known answer.
            self._pending = False
            self._bad.add(tuple(p.origin for p in board.pieces))
            self._goal = []
        if not self._goal:
            hit = _search(board, self._bad)
            if hit is None:
                self._stuck = True
                return []
            self._goal = [(board.pieces[i].cells, hit[i]) for i in range(len(board.pieces))]
        return self._advance(board)

    # -- execution --------------------------------------------------------

    def _advance(self, board: Board) -> list[Step]:
        """One action toward the planned placement, or the commit once it is reached."""
        pairs = self._match(board)
        if len(pairs) != len(board.pieces):
            self._goal = []          # the board no longer holds the pieces the plan was about
            return []
        pending = [(i, t) for i, t in pairs if board.pieces[i].origin != t]
        for idx, target in pending:
            piece = board.pieces[idx]
            move = self._route(board, idx, target)
            if move is None:
                continue
            if self._sel_colour is None or piece.colour != self._sel_colour:
                self._clicked = piece.origin
                return [self._click(board, piece)]
            return [(_MOVES[move], None)]
        if pending:
            # Every remaining piece is boxed in by another one. The layout is unreachable in the
            # order it was planned, so retire it rather than commit a placement we never built.
            self._bad.add(tuple(t for _, t in pairs))
            self._goal = []
            return []
        if self._commits >= _MAX_COMMITS:
            self._stuck = True
            return []
        self._commits += 1
        self._pending = True
        return [(_COMMIT, None)]

    def _match(self, board: Board) -> list[tuple[int, Cell]]:
        """Assign each piece its planned origin — by shape, then by nearness within a shape."""
        out: list[tuple[int, Cell]] = []
        free = list(range(len(self._goal)))
        for idx, piece in enumerate(board.pieces):
            cand = [g for g in free if self._goal[g][0] == piece.cells]
            if not cand:
                continue
            best = min(cand, key=lambda g: abs(self._goal[g][1][0] - piece.origin[0])
                       + abs(self._goal[g][1][1] - piece.origin[1]))
            free.remove(best)
            out.append((idx, self._goal[best][1]))
        return out

    @staticmethod
    def _route(board: Board, idx: int, target: Cell) -> Cell | None:
        """The first press of a shortest slide from where the piece is to where it must be."""
        layout = tuple(p.origin for p in board.pieces)
        dist = _reach(board, idx, layout, _MAX_COST)
        if target not in dist:
            return None
        cur = target
        while dist[cur] > 1:
            for dy, dx in _MOVES:
                prev = (cur[0] - dy, cur[1] - dx)
                if dist.get(prev) == dist[cur] - 1:
                    cur = prev
                    break
            else:
                return None
        start = layout[idx]
        return (cur[0] - start[0], cur[1] - start[1])

    def _click(self, board: Board, piece: Piece) -> Step:
        """Select a piece by clicking the middle of one of its cells."""
        cell = piece.at(piece.origin)[0]
        half = board.scale // 2
        return (6, (board.off + cell[1] * board.scale + half,
                    board.off + cell[0] * board.scale + half))
