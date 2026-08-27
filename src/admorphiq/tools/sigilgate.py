"""Read the board's own vocabulary of spells, then route the avatar through a locked map.

The mechanic, recovered frame-only. A bordered panel holds a complete k x k lattice of equal
square cells. Clicking a cell ARMS it, and when the armed set matches one of the board's spells
that spell resolves. The spells are not guessed: every spell a level allows is displayed on its
own framed PLATE standing off the map, and asking a plate costs a turn and no allowance at all --
the panel immediately lights the cells that spell wants. So a resolution costs exactly its cell
count and no combination is ever tried.

What a resolution DOES is the board's vocabulary and has to be learned once. Three effects recur
and each is legible in a single transition: the avatar changes SIZE, the avatar is CARRIED
elsewhere, or a bolt leaves the face the avatar last turned toward. Effects are remembered by the
arrangement that produced them, so the opening levels -- which offer exactly one plate each -- pay
for the whole vocabulary and every later level gets it for nothing.

The map is a lock, and that is the part a plain reproduce-the-pattern reading misses. Solid blocks
of some colour bar the corridors, and every barred colour has a MARK somewhere else on the map: a
small framed box whose core is painted that same colour. A bolt reaching a mark opens every block
sharing its core colour. The mark normally stands where no step can reach and no bolt fired from
the avatar's own room can see, so the route to a door runs through a carry -- and the carry's
landing site is drawn too: a hollow square of accent corners, sized to the avatar's own footprint,
that MOVES to the next site each time it is used.

So this runs an agenda, not a search. Route to the exit. If no route exists, route to a stance from
which an unstruck mark stands in the bolt's line. If neither exists, take the one jump -- carry or
resize -- that DEMONSTRABLY buys one of those, judged by replanning from where it would land, and
only then a blind one. Every guard here is a measured loss: a carry taken because it was available
rather than because it helped, a bolt fired at a mark standing behind a shut door, a form changed
twice with nothing between.

Two facts make this a plan rather than a wander. A step is the avatar's own footprint, so the map
is a lattice the moment the avatar is found. And the panel that shows the spells also METERS the
level -- every cell entered and every step taken is charged against a per-level allowance and
running it out ends the game -- so exploring here is not merely slow, it loses.

Selectivity comes from the conjunction, never from one part: a COMPLETE lattice inside its own
frame AND a pair of pieces painted in the SAME two-or-more colours, one of them square. The square
one is the avatar and the other is its exit. A board that does not draw its exit in the avatar's
own colours is not this family, and ``detect`` scores 0.
"""

from __future__ import annotations

import heapq
from collections import Counter
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, has_frame

__all__ = ["SigilGateTool"]

# Conventions kept explicit because the frame reader is row-major and the click payload is not:
# a Point is (x, y); a Box is (x0, y0, x1, y1) INCLUSIVE.
Point = tuple[int, int]
Box = tuple[int, int, int, int]

# A panel below this cannot hold a 3x3 lattice and its own frame; above it, that is a board.
_MIN_PANEL = 9
_MAX_PANEL = 40
# Below 3 there is no arrangement to read; above 5 the panel IS the board.
_MIN_K = 3
_MAX_K = 5
# A framed plate is furniture. Anything larger is map.
_MAX_PLATE = 14
# Chrome: a meter pinned to an edge -- thin one way, long the other.
_METER_THIN = 3
_METER_LONG = 32
# An accent square below this is detail inside a sprite, not a landing site.
_MIN_MOTIF = 4
# The allowance forbids a wander, and it also bounds the search.
_MAX_ROUTE = 300
_MAX_STATES = 60000
# One level's worth of turns. Past this the board is not one this tool reads, and holding the turn
# costs the whole game -- measured, a stuck tool once spent 1200 actions on a board already lost.
_MAX_TURNS = 420

# up, down, left, right -- the order the simple action ids come in.
_DIRS = ((0, -1), (0, 1), (-1, 0), (1, 0))


def _settled(obs: Any) -> np.ndarray:
    """The board AFTER the action has played out, not while it is playing.

    ⛔ Read deliberately, and only inside this tool. The shared reader takes layer 0, and on this
    family a single action returns a whole ANIMATION as a stack of layers -- a resize hands back
    seventeen, of which layer 0 still shows the OLD footprint. Reading it named every spell inert
    and the tool stalled on the opening level. The last layer is where the action has finished.
    Switching the shared reader instead was measured on the full set and cost three other games,
    so the stack is read here and nowhere else.
    """
    arr = np.asarray(getattr(obs, "frame", None))
    if arr.ndim >= 3:
        arr = arr[-1]
    return arr.astype(np.int64)


class SigilGateTool:
    """Learn the board's spells off its plates, then unlock a route to the exit."""

    name = "sigilgate"

    def __init__(self) -> None:
        # The board's vocabulary, keyed by the ARRANGEMENT: the same arrangement resolves the same
        # way on every level, so the one-plate opening levels teach the whole game.
        self._effects: dict[frozenset[Point], str] = {}
        # Footprints the avatar has ever worn. A resize toggles between them.
        self._forms: set[int] = set()
        self._cache: tuple[bytes, dict[str, Any] | None] | None = None
        self.reset()

    # --- lifecycle ---------------------------------------------------------

    def reset(self) -> None:
        """Drop everything learned about ONE level's map, keeping the vocabulary."""
        self._queue: list[Step] = []
        self._plates: dict[Box, frozenset[Point]] = {}
        self._asked: Box | None = None
        self._facing: int | None = None
        self._before: dict[str, Any] | None = None
        self._casting: frozenset[Point] | None = None
        self._jumped: set[tuple[str, int]] = set()
        self._exit: Box | None = None
        self._palette: frozenset[int] | None = None
        self._marks = -1
        self._turns = 0

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Record which way the avatar last turned -- a bolt leaves the face it looks at."""
        act, _ = action
        if 1 <= act <= 4:
            self._facing = act - 1

    # --- the bid -----------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Confidence this is a spell-panel board: a lattice AND an exit in the avatar's colours."""
        if not has_frame(obs):
            return 0.0
        try:
            board = self._read(_settled(obs))
        except Exception:
            return 0.0
        return 0.9 if board is not None else 0.0

    # --- perception --------------------------------------------------------

    def _read(self, g: np.ndarray) -> dict[str, Any] | None:
        """Everything the board is showing, or None if it is not showing this mechanic."""
        key = g.tobytes() + repr((self._exit, self._palette)).encode()
        if self._cache is not None and self._cache[0] == key:
            return self._cache[1]
        board = self._read_uncached(g)
        self._cache = (key, board)
        return board

    def _read_uncached(self, g: np.ndarray) -> dict[str, Any] | None:
        pad = _find_pad(g)
        if pad is None:
            return None
        rings = _find_rings(g, exclude=pad["panel"])
        plates = [b for b, inner in rings if len(inner) >= 2 and _side(b) <= _MAX_PLATE]
        skip = [pad["panel"], *plates, *_find_meters(g)]
        wall, floor = _wall_and_floor(g, skip)
        if wall is None or floor is None:
            return None
        pieces = _pieces(g, skip, {wall, floor})
        pair = _avatar_and_exit(pieces)
        if pair is None and self._exit is not None and self._palette is not None:
            # Near the exit the avatar TOUCHES it, and an accent pixel resting against the avatar
            # joins it too -- either way plain connectivity stops returning two pieces in the same
            # colours. Once the exit and the palette are known, read the avatar off the palette.
            pair = _avatar_by_palette(g, self._palette, self._exit, skip)
        if pair is None:
            return None
        avatar, exit_box = pair
        rest = [p for p in pieces if p["box"] != avatar["box"] and p["box"] != exit_box]
        marks, doors = _marks_and_doors(g, [*skip, avatar["box"], exit_box], {wall, floor})
        return {
            "grid": g,
            "pad": pad,
            "plates": plates,
            "wall": wall,
            "floor": floor,
            "avatar": avatar["box"],
            "palette": frozenset(avatar["colours"]),
            "side": _side(avatar["box"]),
            "exit": exit_box,
            "marks": marks,
            "doors": doors,
            "motifs": _find_motifs(rest),
            "lit": _lit_cells(g, pad),
        }

    # --- the turn ----------------------------------------------------------

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        """One action toward the exit, or nothing when this board is not ours to hold."""
        if not has_frame(obs):
            return []
        self._turns += 1
        if self._turns > _MAX_TURNS:
            return []
        try:
            board = self._read(_settled(obs))
        except Exception:
            return []
        if board is None:
            return []
        self._settle(board)
        if self._queue:
            return [self._queue.pop(0)]
        step = self._decide(board)
        return [step] if step is not None else []

    def _settle(self, board: dict[str, Any]) -> None:
        """Close out whatever the last turn started: a plate asked, or a spell resolved."""
        self._forms.add(board["side"])
        self._exit = board["exit"]
        self._palette = board["palette"]
        if len(board["marks"]) != self._marks:
            # The map changed shape. Every jump ruled out under the old map is open again.
            if self._marks >= 0:
                self._jumped.clear()
            self._marks = len(board["marks"])
        if self._asked is not None:
            self._plates[self._asked] = board["lit"]
            self._asked = None
        if self._casting is not None and not self._queue:
            self._effects.setdefault(self._casting, self._effect_of(board))
            self._casting = None
            self._before = None

    def _effect_of(self, now: dict[str, Any]) -> str:
        """Name what the spell just cast did, from the one transition it produced."""
        was = self._before
        if was is None:
            return "inert"
        if now["side"] != was["side"]:
            return "resize"
        reach = 2 * max(1, was["side"])
        if abs(now["avatar"][0] - was["avatar"][0]) > reach or abs(now["avatar"][1] - was["avatar"][1]) > reach:
            return "carry"
        if len(now["marks"]) < len(was["marks"]):
            return "bolt"
        return "inert"

    # --- the agenda --------------------------------------------------------

    def _decide(self, board: dict[str, Any]) -> Step | None:
        """The order of business, and it is an order: read the plates, route, unlock, jump."""
        unread = [b for b in board["plates"] if b not in self._plates]
        if unread:
            self._asked = unread[0]
            return (6, _centre(unread[0]))

        spells = self._spells()
        unknown = [r for r in self._plates.values() if r and r not in self._effects]

        route = self._route(board, spells, goal="exit")
        if route is not None:
            return self._launch(board, route, spells, unknown)
        if "bolt" in spells or unknown:
            route = self._route(board, spells, goal="stance")
            if route is not None:
                return self._launch(board, route, spells, unknown)
        return self._jump(board, spells, unknown)

    def _spells(self) -> dict[str, frozenset[Point]]:
        """Which effects THIS level offers, read off the plates it puts on the wall."""
        out: dict[str, frozenset[Point]] = {}
        for rune in self._plates.values():
            effect = self._effects.get(rune)
            if rune and effect and effect != "inert":
                out.setdefault(effect, rune)
        return out

    def _launch(self, board: dict[str, Any], route: list[tuple[str, Any]],
                spells: dict, unknown: list[frozenset[Point]]) -> Step | None:
        """Turn the first leg of a route into an action, queueing a whole cast when that is the leg."""
        kind, arg = route[0]
        if kind in ("move", "turn"):
            return (arg + 1, None)
        rune = spells.get(kind) or (unknown[0] if kind == "bolt" and unknown else None)
        return self._cast(board, rune) if rune else None

    def _cast(self, board: dict[str, Any], rune: frozenset[Point]) -> Step | None:
        """Arm every cell the spell wants, in an order that cannot spell a DIFFERENT one first."""
        order = _safe_order(rune, set(self._plates.values()))
        grid = board["pad"]["click"]
        if not order or any(not (0 <= r < board["pad"]["k"] and 0 <= c < board["pad"]["k"]) for r, c in order):
            return None
        self._before = board
        self._casting = rune
        self._queue = [(6, grid[r][c]) for r, c in order[1:]]
        return (6, grid[order[0][0]][order[0][1]])

    def _jump(self, board: dict[str, Any], spells: dict, unknown: list) -> Step | None:
        """No route: buy one. A jump that DEMONSTRABLY opens one is taken before any blind jump."""
        side = board["side"]
        if "carry" in spells and ("carry", side) not in self._jumped:
            dest = _carry_dest(board)
            if dest is not None:
                landed = dict(board, avatar=(dest[0], dest[1], dest[0] + side - 1, dest[1] + side - 1))
                if self._route(landed, spells, goal="exit") or self._route(landed, spells, goal="stance"):
                    self._jumped.add(("carry", side))
                    return self._cast(board, spells["carry"])
        for effect in ("resize", "carry"):
            if effect in spells and (effect, side) not in self._jumped:
                self._jumped.add((effect, side))
                return self._cast(board, spells[effect])
        if unknown:
            return self._cast(board, unknown[0])
        return None

    # --- the map -----------------------------------------------------------

    def _route(self, board: dict[str, Any], spells: dict, goal: str) -> list[tuple[str, Any]] | None:
        """Cheapest legs, in ALLOWANCE units, to the exit or to a firing stance.

        Cost is what the level meters, not what the agent types: one per step, and per spell its
        cell count plus the tick its resolution takes.
        """
        side = board["side"]
        free = _free_mask(board)
        stop = _ray_mask(board)
        x0, y0, _, _ = board["avatar"]
        forms = sorted(self._forms | {side}) if "resize" in spells else [side]
        anchors = _anchors(board, forms) if "carry" in spells else {}
        marks = board["marks"]
        ex = board["exit"]
        base = {(x0 + i, y0 + j) for i in range(side) for j in range(side)}

        start = (x0, y0, forms.index(side), -1 if self._facing is None else self._facing)
        dist: dict[tuple, int] = {start: 0}
        back: dict[tuple, tuple] = {}
        heap: list[tuple[int, tuple]] = [(0, start)]
        seen = 0
        while heap:
            cost, node = heapq.heappop(heap)
            if cost > dist.get(node, 1 << 30) or cost > _MAX_ROUTE:
                continue
            seen += 1
            if seen > _MAX_STATES:
                return None
            x, y, fi, face = node
            s = forms[fi]
            if goal == "stance" and face >= 0 and marks and _aims(x, y, s, face, marks, stop) is not None:
                return _unwind(back, node) + [("bolt", None)]
            for d, (dx, dy) in enumerate(_DIRS):
                nx, ny = x + dx * s, y + dy * s
                if _overlaps((nx, ny, nx + s - 1, ny + s - 1), ex):
                    if goal == "exit":
                        return _unwind(back, node) + [("move", d)]
                    continue
                legal = _fits(nx, ny, s, free, base, anchors)
                if not legal and face == d:
                    continue
                nxt = (nx, ny, fi, d) if legal else (x, y, fi, d)
                _relax(dist, back, heap, node, nxt, cost + 1, "move" if legal else "turn", d)
            if "carry" in spells:
                price = len(spells["carry"]) + 1
                for (ax, ay), near in anchors.get(s, {}).items():
                    _relax(dist, back, heap, node, (ax, ay, fi, face),
                           cost + price * (1 if near else 2), "carry", None)
            if "resize" in spells and len(forms) == 2:
                price = len(spells["resize"]) + 1
                oi = 1 - fi
                if _fits(x, y, forms[oi], free, base, anchors):
                    _relax(dist, back, heap, node, (x, y, oi, face), cost + price, "resize", None)
        return None


# --- perception helpers -----------------------------------------------------


def _blobs(mask: np.ndarray) -> list[list[Point]]:
    """4-connected regions of a boolean mask, as lists of (x, y)."""
    h, w = mask.shape
    seen = np.zeros_like(mask)
    out: list[list[Point]] = []
    for y in range(h):
        row = mask[y]
        for x in range(w):
            if not row[x] or seen[y, x]:
                continue
            stack = [(x, y)]
            seen[y, x] = True
            cells: list[Point] = []
            while stack:
                cx, cy = stack.pop()
                cells.append((cx, cy))
                for dx, dy in _DIRS:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((nx, ny))
            out.append(cells)
    return out


def _bbox(cells: list[Point]) -> Box:
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    return (min(xs), min(ys), max(xs), max(ys))


def _side(b: Box) -> int:
    return max(b[2] - b[0] + 1, b[3] - b[1] + 1)


def _centre(b: Box) -> Point:
    return ((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)


def _overlaps(a: Box, b: Box) -> bool:
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def _find_pad(g: np.ndarray) -> dict[str, Any] | None:
    """The instruction panel: one frame whose holes are a COMPLETE k x k of equal flat cells."""
    for colour in np.unique(g):
        mask = g == colour
        for cells in _blobs(mask):
            box = _bbox(cells)
            w, h = box[2] - box[0] + 1, box[3] - box[1] + 1
            if w != h or not (_MIN_PANEL <= w <= _MAX_PANEL):
                continue
            inner = np.zeros_like(mask)
            inner[box[1]:box[3] + 1, box[0]:box[2] + 1] = True
            inner &= ~mask
            holes = _blobs(inner)
            k = int(round(len(holes) ** 0.5))
            if not (_MIN_K <= k <= _MAX_K) or k * k != len(holes):
                continue
            boxes = [_bbox(c) for c in holes]
            sides = {b[2] - b[0] + 1 for b in boxes} | {b[3] - b[1] + 1 for b in boxes}
            if len(sides) != 1:
                continue
            cell = sides.pop()
            if any(len(c) != cell * cell for c in holes):
                continue
            xs = sorted({b[0] for b in boxes})
            ys = sorted({b[1] for b in boxes})
            if len(xs) != k or len(ys) != k:
                continue
            px = {b - a for a, b in zip(xs, xs[1:])}
            py = {b - a for a, b in zip(ys, ys[1:])}
            if len(px) != 1 or px != py:
                continue
            click = [[(xs[c] + cell // 2, ys[r] + cell // 2) for c in range(k)] for r in range(k)]
            return {"k": k, "cell": cell, "click": click, "panel": box}
    return None


def _lit_cells(g: np.ndarray, pad: dict[str, Any]) -> frozenset[Point]:
    """Which lattice cells the panel is SHOWING: the minority colour is the spell it wants."""
    k = pad["k"]
    colours = [[int(g[y][x]) for (x, y) in row] for row in pad["click"]]
    flat = [c for row in colours for c in row]
    neutral = Counter(flat).most_common(1)[0][0]
    lit = {(r, c) for r in range(k) for c in range(k) if colours[r][c] != neutral}
    return frozenset(lit) if 0 < len(lit) < k * k else frozenset()


def _find_rings(g: np.ndarray, exclude: Box) -> list[tuple[Box, set[int]]]:
    """Every single-colour frame whose whole bbox border is that colour, with its interior palette."""
    out: list[tuple[Box, set[int]]] = []
    for colour in np.unique(g):
        mask = g == colour
        for cells in _blobs(mask):
            box = _bbox(cells)
            w, h = box[2] - box[0] + 1, box[3] - box[1] + 1
            if w < 3 or h < 3 or box == exclude:
                continue
            if not (mask[box[1], box[0]:box[2] + 1].all() and mask[box[3], box[0]:box[2] + 1].all()
                    and mask[box[1]:box[3] + 1, box[0]].all() and mask[box[1]:box[3] + 1, box[2]].all()):
                continue
            interior = g[box[1] + 1:box[3], box[0] + 1:box[2]]
            if interior.size:
                out.append((box, {int(v) for v in np.unique(interior)}))
    return out


def _find_meters(g: np.ndarray) -> list[Box]:
    """Chrome pinned to an edge: thin one way, long the other. A counter, never a piece."""
    h, w = g.shape
    out: list[Box] = []
    for colour in np.unique(g):
        for cells in _blobs(g == colour):
            b = _bbox(cells)
            bw, bh = b[2] - b[0] + 1, b[3] - b[1] + 1
            if bw <= _METER_THIN and bh >= _METER_LONG and (b[0] <= _METER_THIN or b[2] >= w - 1 - _METER_THIN):
                out.append(b)
            elif bh <= _METER_THIN and bw >= _METER_LONG and (b[1] <= _METER_THIN or b[3] >= h - 1 - _METER_THIN):
                out.append(b)
    return out


def _wall_and_floor(g: np.ndarray, skip: list[Box]) -> tuple[int | None, int | None]:
    """The two colours the map is cut from: the one that runs off the edge, and the one inside it."""
    live = np.ones(g.shape, dtype=bool)
    for b in skip:
        live[b[1]:b[3] + 1, b[0]:b[2] + 1] = False
    counts = Counter(int(v) for v in g[live])
    if not counts:
        return None, None
    h, w = g.shape
    edge: set[int] = set()
    for x in range(w):
        for y in (0, h - 1):
            if live[y, x]:
                edge.add(int(g[y][x]))
    for y in range(h):
        for x in (0, w - 1):
            if live[y, x]:
                edge.add(int(g[y][x]))
    wall = next((c for c, _ in counts.most_common() if c in edge), None)
    floor = next((c for c, _ in counts.most_common() if c != wall), None)
    return wall, floor


def _pieces(g: np.ndarray, skip: list[Box], ground: set[int]) -> list[dict[str, Any]]:
    """Everything standing on the map: connected runs of whatever is neither wall nor floor."""
    live = np.ones(g.shape, dtype=bool)
    for b in skip:
        live[b[1]:b[3] + 1, b[0]:b[2] + 1] = False
    mask = live & ~np.isin(g, list(ground))
    return [{"box": _bbox(c), "cells": c, "colours": {int(g[y][x]) for x, y in c}} for c in _blobs(mask)]


def _avatar_and_exit(pieces: list[dict[str, Any]]) -> tuple[dict[str, Any], Box] | None:
    """Avatar and exit wear the SAME colours; the avatar is the square one."""
    by_palette: dict[frozenset[int], list[dict[str, Any]]] = {}
    for p in pieces:
        if len(p["colours"]) >= 2:
            by_palette.setdefault(frozenset(p["colours"]), []).append(p)
    best: tuple[dict[str, Any], Box] | None = None
    for group in by_palette.values():
        if len(group) < 2:
            continue
        squares = [p for p in group if _is_square(p)]
        if not squares:
            continue
        avatar = min(squares, key=lambda p: len(p["cells"]))
        rest = [p for p in group if p is not avatar]
        exit_piece = max(rest, key=lambda p: len(p["cells"]))
        if best is None or len(avatar["cells"]) < len(best[0]["cells"]):
            best = (avatar, exit_piece["box"])
    return best


def _avatar_by_palette(g: np.ndarray, palette: frozenset[int], exit_box: Box,
                       skip: list[Box]) -> tuple[dict[str, Any], Box] | None:
    """The avatar when its colours are already known: the square run painted only in them."""
    mask = np.isin(g, list(palette))
    for b in [*skip, exit_box]:
        mask[b[1]:b[3] + 1, b[0]:b[2] + 1] = False
    best: dict[str, Any] | None = None
    for cells in _blobs(mask):
        piece = {"box": _bbox(cells), "cells": cells, "colours": {int(g[y][x]) for x, y in cells}}
        if _is_square(piece) and (best is None or len(cells) < len(best["cells"])):
            best = piece
    return (best, exit_box) if best else None


def _is_square(p: dict[str, Any]) -> bool:
    b = p["box"]
    w, h = b[2] - b[0] + 1, b[3] - b[1] + 1
    return w == h and len(p["cells"]) == w * h


def _marks_and_doors(g: np.ndarray, skip: list[Box], ground: set[int]) -> tuple[list[dict], list[dict]]:
    """A mark is a framed core; a door is a bare block. They pair on the CORE'S OWN COLOUR.

    Read one colour at a time rather than off whole pieces: a mark standing against the scenery
    merges with it under plain connectivity, and the pair that mark unlocks then goes unseen --
    measured, exactly one of two locks on a late board was found this way.
    """
    live = np.ones(g.shape, dtype=bool)
    for b in skip:
        live[b[1]:b[3] + 1, b[0]:b[2] + 1] = False
    marks: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    for colour in np.unique(g):
        if int(colour) in ground:
            continue
        for cells in _blobs(live & (g == colour)):
            b = _bbox(cells)
            w, h = b[2] - b[0] + 1, b[3] - b[1] + 1
            if len(cells) != w * h:
                continue
            frame = _surround(g, b)
            if len(cells) >= 2 and len(frame) == 1 and not (frame & ground):
                # A bolt is stopped by the whole mark, frame included -- not by its core.
                marks.append({"box": b, "hit": (b[0] - 1, b[1] - 1, b[2] + 1, b[3] + 1),
                              "colour": int(colour)})
            else:
                blocks.append({"box": b, "colour": int(colour)})
    keyed = {m["colour"] for m in marks}
    return marks, [d for d in blocks if d["colour"] in keyed]


def _surround(g: np.ndarray, b: Box) -> set[int]:
    """The colours of the one-cell ring around a box, clipped to the frame."""
    h, w = g.shape
    out: set[int] = set()
    for x in range(b[0] - 1, b[2] + 2):
        for y in (b[1] - 1, b[3] + 1):
            if 0 <= x < w and 0 <= y < h:
                out.add(int(g[y][x]))
    for y in range(b[1], b[3] + 1):
        for x in (b[0] - 1, b[2] + 1):
            if 0 <= x < w and 0 <= y < h:
                out.add(int(g[y][x]))
    return out


def _find_motifs(pieces: list[dict[str, Any]]) -> list[Box]:
    """Accent corners: four lone pixels of one colour at the corners of an axis-aligned square."""
    lone: dict[int, set[Point]] = {}
    for p in pieces:
        if len(p["cells"]) == 1:
            lone.setdefault(next(iter(p["colours"])), set()).add(p["cells"][0])
    out: list[Box] = []
    for pts in lone.values():
        ordered = sorted(pts)
        for (x0, y0) in ordered:
            for (x1, y1) in ordered:
                d = x1 - x0
                if y1 != y0 or d < _MIN_MOTIF - 1:
                    continue
                if (x0, y0 + d) in pts and (x1, y0 + d) in pts:
                    out.append((x0, y0, x1, y0 + d))
    return out


def _carry_dest(board: dict[str, Any]) -> Point | None:
    """Where the next carry lands: the largest accent square, its interior sized to the avatar."""
    if not board["motifs"]:
        return None
    ring = max(board["motifs"], key=_side)
    inner = _side(ring) - 2
    s = board["side"]
    if inner < s:
        return None
    off = (inner - s) // 2
    return (ring[0] + 1 + off, ring[1] + 1 + off)


def _anchors(board: dict[str, Any], forms: list[int]) -> dict[int, dict[Point, bool]]:
    """Every landing site the carry cycles through, per form, flagged with which one is NEXT."""
    out: dict[int, dict[Point, bool]] = {s: {} for s in forms}
    for m in board["motifs"]:
        s = _side(m)
        if s in out:
            out[s][(m[0], m[1])] = False
    dest = _carry_dest(board)
    if dest is not None and board["side"] in out:
        out[board["side"]][dest] = True
    return out


# --- planning helpers -------------------------------------------------------


def _free_mask(board: dict[str, Any]) -> np.ndarray:
    """Where a footprint may stand: bare floor. A door still drawn is a door still shut."""
    return board["grid"] == board["floor"]


def _ray_mask(board: dict[str, Any]) -> np.ndarray:
    """What stops a bolt: the wall the map is cut from, plus shut doors. Detail does not."""
    stop = board["grid"] == board["wall"]
    for d in board["doors"]:
        b = d["box"]
        stop[b[1]:b[3] + 1, b[0]:b[2] + 1] = True
    for m in board["marks"]:
        b = m["hit"]
        stop[max(0, b[1]):b[3] + 1, max(0, b[0]):b[2] + 1] = True
    return stop


def _fits(x: int, y: int, s: int, free: np.ndarray, base: set[Point], anchors: dict) -> bool:
    """Can a footprint of this size stand here? Where it already stands always counts."""
    h, w = free.shape
    if x < 0 or y < 0 or x + s > w or y + s > h:
        return False
    for per_form in anchors.values():
        if (x, y) in per_form:
            return True
    for i in range(s):
        for j in range(s):
            if not free[y + j, x + i] and (x + i, y + j) not in base:
                return False
    return True


def _aims(x: int, y: int, s: int, face: int, marks: list[dict], stop: np.ndarray) -> dict | None:
    """The first thing a bolt fired from this stance reaches, if that thing is a mark."""
    dx, dy = _DIRS[face]
    cx = x + (s - 1 if dx > 0 else 0)
    cy = y + (s - 1 if dy > 0 else 0)
    h, w = stop.shape
    for i in range(1, max(h, w)):
        px, py = cx + dx * i, cy + dy * i
        if not (0 <= px < w and 0 <= py < h):
            return None
        for m in marks:
            if m["hit"][0] <= px <= m["hit"][2] and m["hit"][1] <= py <= m["hit"][3]:
                return m
        if stop[py, px]:
            return None
    return None


def _relax(dist, back, heap, node, nxt, cost, kind, arg) -> None:
    if cost < dist.get(nxt, 1 << 30):
        dist[nxt] = cost
        back[nxt] = (node, kind, arg)
        heapq.heappush(heap, (cost, nxt))


def _unwind(back: dict, node: tuple) -> list[tuple[str, Any]]:
    legs: list[tuple[str, Any]] = []
    while node in back:
        node, kind, arg = back[node]
        legs.append((kind, arg))
    legs.reverse()
    return legs


def _safe_order(rune: frozenset[Point], others: set[frozenset[Point]]) -> list[Point]:
    """An arming order that never spells a DIFFERENT spell halfway -- that one would fire early."""
    rivals = {r for r in others if r and r != rune}
    cells = sorted(rune)
    for _ in range(len(cells)):
        armed: set[Point] = set()
        early = False
        for c in cells[:-1]:
            armed.add(c)
            if frozenset(armed) in rivals:
                early = True
                break
        if not early:
            return cells
        cells = cells[1:] + cells[:1]
    return sorted(rune)
