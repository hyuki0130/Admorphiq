"""Slide skeleton pieces until their arms cover a board's pinned target marks.

The family this reads: the board carries a handful of small MARKS, each a 3x3 ring of one
flat colour with a differently-coloured pip at its middle, and PIECES — thin skeletal shapes
(a cross, an X, a bar, a rectangle outline) drawn in the pip colours. The level is won when
every mark's pip stands on a piece cell of that pip's own colour. Nothing else about the
board matters, so the game reduces to: choose, for each piece, the rigid translation that
between them cover every pip, then walk the pieces there.

Three things are LEARNED rather than assumed, because assuming any of them was wrong on the
board this was built against:

* Which action moves which way, and by how far. The tool issues a move, watches the cells
  shift, and records the vector. A move that changes nothing is retried before the action is
  believed inert, because these boards swallow actions during animations.
* WHAT A PIECE IS. Pieces that share a colour and touch are one blob to any segmenter, and
  this board has three such. So objecthood comes from motion: the cells that vanish, plus
  the cells that appear shifted back by the move vector, are one object. That estimate is
  never an over-claim — it can miss cells a move left standing, and those are recovered by
  union as further moves are seen — so a covering translation found from it is real.
* Which piece the controls are driving. The driven piece wears a single odd-coloured cell at
  its middle, which is a frame fact but an unreliable one when that cell is hidden under a
  mark, so what actually moved always overrules it.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, frame_2d, has_frame
from admorphiq.tools.segment import background, board_changed, edge_band

__all__ = ["CoverTargetsTool"]

Cell = tuple[int, int]

# A mark is a pip ringed by its 8 neighbours: the smallest shape that can say "here".
_MARK = 3
# An action is only believed inert after it has failed to move anything this many times.
_INERT_AFTER = 3
# A remembered piece is recognised in a new view once this much of it is still on show.
_RECOGNISE = 0.5


class CoverTargetsTool:
    """Cover every target pip with a piece of that pip's colour (see module docstring)."""

    name = "cover_targets"

    def __init__(self) -> None:
        self._effect: dict[int, tuple[int, int]] = {}
        self._select: int | None = None
        self._noeffect: Counter[int] = Counter()
        self.reset()

    # --- lifecycle ---------------------------------------------------------

    def reset(self) -> None:
        """Drop the per-level board; the learned control map survives, it is the game's."""
        self._spec: tuple[int, list[tuple[int, int, int]]] | None = None
        self._parts: list[dict[str, Any]] = []
        self._blobs: dict[int, set[Cell]] = {}
        self._wheel: int | None = None
        self._acted: int | None = None
        self._grid: np.ndarray | None = None
        self._odd: list[Cell] = []
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
        spec = self._marks(grid)
        if spec is None:
            return 0.0
        blobs = self._blobs_of(grid, spec)
        pips = {p[2] for p in spec[1]}
        if not pips <= set(blobs):
            return 0.0
        for colour in pips:
            want = [(r, c) for r, c, v in spec[1] if v == colour]
            if _offsets(frozenset(blobs[colour]), want):
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
                ring = {
                    int(grid[r + dy, c + dx])
                    for dy in (-1, 0, 1)
                    for dx in (-1, 0, 1)
                    if dy or dx
                }
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

    def _blobs_of(
        self, grid: np.ndarray, spec: tuple[int, list[tuple[int, int, int]]]
    ) -> dict[int, set[Cell]]:
        """Every piece-coloured cell on the board, gathered by colour.

        Cells under a mark are dropped rather than guessed at: a piece running through one is
        invisible there, and inventing the crossing added cells an X-shaped piece never had.
        The remembered shapes fill those gaps instead.
        """
        ringc, marks = spec
        hidden = {
            (r + dy, c + dx)
            for r, c, _ in marks
            for dy in (-1, 0, 1)
            for dx in (-1, 0, 1)
        }
        chrome = edge_band(grid.shape, margin_div=min(grid.shape))
        blocked = set(background(grid.tolist())) | {ringc}
        h, w = grid.shape
        out: dict[int, set[Cell]] = {}
        for r in range(h):
            for c in range(w):
                if chrome[r, c] or (r, c) in hidden:
                    continue
                v = int(grid[r, c])
                if v not in blocked:
                    out.setdefault(v, set()).add((r, c))
        # The driven piece wears one odd cell at its middle. On a solid piece that cell is
        # part of the body and its colour flips as the controls move on, so hand it back to
        # whatever it touches — otherwise the piece's size flickers by one every turn.
        self._odd = [next(iter(c)) for v, c in out.items() if len(c) == 1]
        for spot in self._odd:
            y, x = spot
            for body in out.values():
                if len(body) < 2:
                    continue
                if any(max(abs(y - a), abs(x - b)) == 1 for a, b in body):
                    body.add(spot)
                    break
        return {v: cells for v, cells in out.items() if len(cells) > 2}

    # --- objecthood from motion --------------------------------------------

    def _learn(self, blobs: dict[int, set[Cell]], grid: np.ndarray) -> None:
        """Attribute the last action: a piece moved, the controls changed hands, or neither."""
        action, before, prev = self._acted, self._blobs, self._grid
        if action is None or prev is None:
            return
        moved = _moved(before, blobs, self._effect.get(action))
        if moved is not None:
            cells, vec = moved
            self._effect[action] = vec
            self._noeffect[action] = 0
            self._idle = 0
            self._attribute(cells, vec)
            return
        if board_changed(prev, grid):
            if action not in self._effect:
                self._select = action
            self._wheel = None
            self._noeffect[action] = 0
            self._idle = 0
            return
        self._noeffect[action] += 1

    def _attribute(self, cells: set[Cell], vec: tuple[int, int]) -> None:
        """File the cells that just moved against a known piece, or open a new one.

        Whoever held the controls still holds them — only the select action changes that — so
        a move is filed against the driven piece without asking whether it LOOKS like it.
        That matters: a move along one axis only exposes the arms crossing that axis, so two
        moves of one cross can share barely any cells, and asking for a resemblance split it
        into two pieces that then fought each other for the controls.
        """
        target = self._wheel
        if target is None:
            box = (
                min(c[0] for c in cells), min(c[1] for c in cells),
                max(c[0] for c in cells), max(c[1] for c in cells),
            )
            for i, part in enumerate(self._parts):
                mask = _mask(part)
                seat = (
                    min(c[0] for c in mask), min(c[1] for c in mask),
                    max(c[0] for c in mask), max(c[1] for c in mask),
                )
                if all(abs(a - b) <= _MARK for a, b in zip(box, seat)):
                    target = i
                    break
        if target is None:
            anchor = (min(c[0] for c in cells), min(c[1] for c in cells))
            self._parts.append({
                "colour": None,
                "shape": frozenset((y - anchor[0], x - anchor[1]) for y, x in cells),
                "anchor": (anchor[0] + vec[0], anchor[1] + vec[1]),
                "axes": {0 if vec[0] else 1},
            })
            self._wheel = len(self._parts) - 1
            return
        part = self._parts[target]
        anchor = part["anchor"]
        part["shape"] = part["shape"] | {(y - anchor[0], x - anchor[1]) for y, x in cells}
        part["anchor"] = (anchor[0] + vec[0], anchor[1] + vec[1])
        part["axes"].add(0 if vec[0] else 1)
        self._wheel = target

    def _at_the_wheel(self) -> int | None:
        """Which piece the controls are on, read off the odd cell it wears at its middle.

        Only a hint: the cell is invisible when it happens to lie under a mark. What actually
        moved always wins, and when neither can say, the next move is itself the probe.
        """
        for y, x in self._odd:
            for i, part in enumerate(self._parts):
                mask = _mask(part)
                if not mask:
                    continue
                cy = (min(c[0] for c in mask) + max(c[0] for c in mask)) / 2
                cx = (min(c[1] for c in mask) + max(c[1] for c in mask)) / 2
                if abs(y - cy) <= 1 and abs(x - cx) <= 1:
                    return i
        return None

    def _recolour(self, blobs: dict[int, set[Cell]]) -> None:
        """Say which colour each piece is now wearing, by where its cells actually are."""
        for part in self._parts:
            mask = _mask(part)
            best, score = None, 0
            for colour, cells in blobs.items():
                hit = len(mask & cells)
                if hit > score:
                    best, score = colour, hit
            part["colour"] = best

    # --- planning ----------------------------------------------------------

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        """One action toward covering the pips, learning the board as it goes."""
        if not has_frame(obs):
            return []
        grid = frame_2d(obs)
        spec = self._marks(grid)
        if spec is None:
            return []
        blobs = self._blobs_of(grid, spec)
        self._learn(blobs, grid)
        self._recolour(blobs)
        if self._wheel is None:
            self._wheel = self._at_the_wheel()
        self._blobs, self._grid, self._acted = blobs, grid, None

        pips = spec[1]
        gap = [(r, c) for r, c, v in pips if not self._covered(r, c, v)]
        if not gap:
            return []
        plan = self._assign(pips, blobs)
        if plan is None:
            plan = self._dip(pips, blobs)
        if plan is None:
            return self._discover(blobs)
        for i, vec in plan:
            if vec == (0, 0):
                continue
            if self._wheel is not None and self._wheel != i:
                return self._cycle()
            return self._drive(vec)
        return []

    def _covered(self, r: int, c: int, colour: int) -> bool:
        """Is this pip already standing on a piece of its own colour?

        Only the remembered pieces can answer: the pip's own cell is hidden under its mark,
        so the frame shows the mark there whether a piece runs through it or not.
        """
        return any(
            part["colour"] == colour and (r, c) in _mask(part) for part in self._parts
        )

    def _assign(
        self, pips: list[tuple[int, int, int]], blobs: dict[int, set[Cell]]
    ) -> list[tuple[int, tuple[int, int]]] | None:
        """One translation per piece that together cover every pip, cheapest first."""
        step = self._stride()
        if not step or not self._parts:
            return None
        chosen: list[tuple[int, tuple[int, int]]] = []
        for colour in {v for _, _, v in pips}:
            want = [(r, c) for r, c, v in pips if v == colour]
            mine = [i for i, p in enumerate(self._parts) if p["colour"] == colour]
            if not mine:
                return None
            picks = _cover(
                [(i, _mask(self._parts[i])) for i in mine], want, step, self._unmoved(blobs, colour)
            )
            if picks is None:
                return None
            chosen.extend(picks)
        chosen.sort(key=lambda iv: abs(iv[1][0]) + abs(iv[1][1]))
        return chosen

    def _dip(
        self, pips: list[tuple[int, int, int]], blobs: dict[int, set[Cell]]
    ) -> list[tuple[int, tuple[int, int]]] | None:
        """Take a piece to a patch of a colour the board asks for and no piece is wearing.

        When the marks demand a colour that is nowhere on any piece, the board is not
        unsolvable — it is telling you where to go. The only fixed thing on it wearing that
        exact colour is where a piece goes to acquire it, and the piece to send is one whose
        own colour no mark asks for, so nothing already useful is spent.
        """
        step = self._stride()
        wanted = {v for _, _, v in pips}
        short = sorted(wanted - {p["colour"] for p in self._parts})
        if not step or not short:
            return None
        spare = [i for i, p in enumerate(self._parts) if p["colour"] not in wanted]
        donors = spare or list(range(len(self._parts)))
        best: tuple[int, int, tuple[int, int]] | None = None
        for colour in short:
            patch = self._unmoved(blobs, colour)
            if not patch:
                continue
            for i in donors:
                mask = _mask(self._parts[i])
                for sy, sx in patch:
                    for my, mx in mask:
                        off = (_snap(sy - my, step), _snap(sx - mx, step))
                        cost = abs(off[0]) + abs(off[1])
                        if off == (0, 0) or (best is not None and cost >= best[0]):
                            continue
                        if any((y + off[0], x + off[1]) in patch for y, x in mask):
                            best = (cost, i, off)
        return None if best is None else [(best[1], best[2])]

    def _unmoved(self, blobs: dict[int, set[Cell]], colour: int) -> frozenset[Cell]:
        """Cells of this colour that no known piece accounts for; they stay where they are."""
        known: set[Cell] = set()
        for part in self._parts:
            if part["colour"] == colour:
                known |= _mask(part)
        return frozenset(blobs.get(colour, set()) - known)

    def _discover(self, blobs: dict[int, set[Cell]]) -> list[Step]:
        """No plan yet — finish learning the piece in hand, then take the next one.

        A piece is only fully seen once it has moved on BOTH axes: one axis exposes only the
        arms that cross it. So the piece in hand is nudged along the axis it has not moved on
        — and if no action is yet known to push that way, an untried action is spent finding
        one, rather than repeating a move that cannot teach anything new.
        """
        if self._wheel is not None:
            part = self._parts[self._wheel]
            for axis in sorted({0, 1} - part["axes"]):
                pick = self._toward(axis, _mask(part), blobs)
                if pick is not None:
                    return self._emit(pick)
            if self._seen_all():
                return []
            return self._cycle()
        blind = self._blind()
        if blind is not None:
            return self._emit(blind)
        known = [a for a in self._effect if a in self._usable()]
        return self._emit(known[0]) if known else []

    def _blind(self) -> int | None:
        """An action never yet tried, which is the only kind that can teach a new direction."""
        for a in self._usable():
            if a not in self._effect and a != self._select:
                return a
        return None

    def _toward(
        self, axis: int, mask: frozenset[Cell], blobs: dict[int, set[Cell]]
    ) -> int | None:
        """A push along this axis that keeps the piece on the board, or a way to find one."""
        board = next(iter(blobs.values()), None)
        limit = 0 if board is None else max(max(c) for c in board) + 1
        for action, vec in self._effect.items():
            if action not in self._usable() or bool(vec[0]) != (axis == 0):
                continue
            after = [(y + vec[0], x + vec[1]) for y, x in mask]
            if any(0 <= y < limit and 0 <= x < limit for y, x in after):
                return action
        return self._blind()

    def _seen_all(self) -> bool:
        """Have the controls come back round to a piece already fully learned?"""
        self._idle += 1
        return self._idle > len(self._parts) + 2

    # --- controls ----------------------------------------------------------

    def _stride(self) -> int:
        """How far one move carries a piece, once a move has actually been seen."""
        seen = [abs(v) for vec in self._effect.values() for v in vec if v]
        return min(seen) if seen else 0

    def _usable(self) -> list[int]:
        return [a for a in (1, 2, 3, 4, 5) if self._noeffect[a] < _INERT_AFTER]

    def _emit(self, action: int) -> list[Step]:
        self._acted = action
        return [(action, None)]

    def _cycle(self) -> list[Step]:
        """Hand the controls to another piece."""
        if self._select is not None and self._select in self._usable():
            return self._emit(self._select)
        blind = [a for a in self._usable() if a not in self._effect]
        return self._emit(blind[0]) if blind else []

    def _drive(self, want: tuple[int, int]) -> list[Step]:
        """The action that pushes the wanted way, or the cheapest way to find one out."""
        dy, dx = want
        for axis in ((dy, 0), (0, dx)):
            if axis == (0, 0):
                continue
            for action, vec in self._effect.items():
                if action in self._usable() and _aligned(vec, axis):
                    return self._emit(action)
        blind = [a for a in self._usable() if a not in self._effect and a != self._select]
        if blind:
            return self._emit(blind[0])
        self._idle += 1
        return [] if self._idle > 2 else self._cycle()


# --- geometry ---------------------------------------------------------------


def _mask(part: dict[str, Any]) -> frozenset[Cell]:
    """Where the piece's cells are right now."""
    ay, ax = part["anchor"]
    return frozenset((ay + y, ax + x) for y, x in part["shape"])


def _moved(
    before: dict[int, set[Cell]], after: dict[int, set[Cell]], known: tuple[int, int] | None
) -> tuple[set[Cell], tuple[int, int]] | None:
    """The cells of the one piece that moved, at their old spot, and by how far.

    Vanished cells were certainly the mover; appeared cells were certainly the mover, one
    move ago. Their union is a piece — possibly only part of one, when a move slid a piece
    along its own length and most of it stayed put, which is why shapes accumulate.
    """
    gone: set[Cell] = set()
    came: set[Cell] = set()
    for colour in set(before) | set(after):
        gone |= before.get(colour, set()) - after.get(colour, set())
        came |= after.get(colour, set()) - before.get(colour, set())
    # A cell that merely changed from one piece's colour to another's is one piece passing
    # over another, not a piece arriving or leaving. Counting those as motion grew a hollow
    # rectangle from 39 cells to 83 as it slid across its neighbours.
    gone, came = gone - came, came - gone
    if not gone or not came:
        return None
    vec = _vector(gone, came, known)
    if vec is None:
        return None
    return gone | {(y - vec[0], x - vec[1]) for y, x in came}, vec


def _vector(
    gone: set[Cell], came: set[Cell], known: tuple[int, int] | None
) -> tuple[int, int] | None:
    """How far the board's content shifted, by best agreement rather than by centroid.

    An action's step is a property of the control, so once measured it is simply used. What
    changed cannot re-derive it: a bar sliding ALONG its own length leaves only its two ends
    changed, and both a 3-cell step and a 43-cell leap explain those ends equally well — the
    leap even better. A centroid is no help either; it read a cross's 3-cell move as 5,
    because the mean of what changed is dragged by whichever arm happened to move wholesale.
    """
    if known is not None and known != (0, 0):
        return known

    def fits(vec: tuple[int, int]) -> int:
        return len({(y + vec[0], x + vec[1]) for y, x in gone} & came)

    best, score = None, (0, 0)
    for g in _spread(gone):
        for c in _spread(came):
            vec = (c[0] - g[0], c[1] - g[1])
            if vec == (0, 0):
                continue
            rank = (fits(vec), -abs(vec[0]) - abs(vec[1]))
            if rank > score:
                best, score = vec, rank
    return best if score[0] else None


def _spread(cells: set[Cell], take: int = 12) -> list[Cell]:
    """A handful of cells spanning the set, enough to propose every plausible shift."""
    ordered = sorted(cells)
    if len(ordered) <= take:
        return ordered
    stride = len(ordered) / take
    return [ordered[int(i * stride)] for i in range(take)]


def _offsets(mask: frozenset[Cell], pips: list[Cell]) -> set[Cell]:
    """Every translation of `mask` that lands a piece cell on each of `pips`."""
    cand: set[Cell] | None = None
    for py, px in pips:
        here = {(py - my, px - mx) for my, mx in mask}
        cand = here if cand is None else (cand & here)
        if not cand:
            return set()
    return cand or set()


def _cover(
    parts: list[tuple[int, frozenset[Cell]]],
    pips: list[Cell],
    step: int,
    fixed: frozenset[Cell],
) -> list[tuple[int, tuple[int, int]]] | None:
    """Split the pips between the pieces of one colour, minimising total moves."""
    todo = frozenset(p for p in pips if p not in fixed)
    if not todo:
        return [(i, (0, 0)) for i, _ in parts]
    choices: list[list[tuple[frozenset[Cell], tuple[int, int]]]] = []
    for _, mask in parts:
        best: dict[frozenset[Cell], tuple[int, int]] = {}
        seen: set[tuple[int, int]] = {(0, 0)}
        for py, px in todo:
            for my, mx in mask:
                seen.add((_snap(py - my, step), _snap(px - mx, step)))
        for off in seen:
            if off[0] % step or off[1] % step:
                continue
            got = frozenset(p for p in todo if (p[0] - off[0], p[1] - off[1]) in mask)
            cost = abs(off[0]) + abs(off[1])
            if got not in best or cost < abs(best[got][0]) + abs(best[got][1]):
                best[got] = off
        choices.append(sorted(best.items(), key=lambda kv: abs(kv[1][0]) + abs(kv[1][1])))

    found: list[tuple[int, tuple[int, int]]] | None = None
    cheapest = None

    def walk(k: int, left: frozenset[Cell], spent: int, picks: list[tuple[int, int]]) -> None:
        nonlocal found, cheapest
        if cheapest is not None and spent >= cheapest:
            return
        if not left:
            found, cheapest = [(parts[j][0], picks[j]) for j in range(len(picks))], spent
            return
        if k >= len(choices):
            return
        for got, off in choices[k]:
            walk(k + 1, left - got, spent + abs(off[0]) + abs(off[1]), [*picks, off])

    walk(0, todo, 0, [])
    return found


def _snap(value: int, step: int) -> int:
    """The nearest translation the controls can actually produce."""
    return int(round(value / step)) * step


def _aligned(vec: tuple[int, int], axis: tuple[int, int]) -> bool:
    """Does `vec` push along `axis` — same sign, same axis, nothing sideways?"""
    dy, dx = vec
    ay, ax = axis
    if ay:
        return dx == 0 and dy * ay > 0
    return dy == 0 and dx * ax > 0
