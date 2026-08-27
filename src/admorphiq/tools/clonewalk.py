"""Clone-walk tool — solve a gated maze whose only extra verb parks a REPLAY CLONE.

The board family this reads is a walled maze with one body, one marked exit, and furniture that
is wired together in plain sight. Everything below is recovered from pixels; nothing here knows
a title, an identifier, a sprite tag or a coordinate.

THE GRAMMAR, and why each piece is safe to key on:

  * BODY — a solid square block of one colour whose single centre pixel shows the floor through
    it. The hole is not decoration: the engine tests exactly ONE point, the body's centre, so the
    hole marks the cell that has to be walkable and fixes the lattice the walk is planned on.
  * EXIT — a hollow ring with a LOOSE single cell of the same colour at its middle. The ring's
    colour is the body's colour, which ties the two together and makes the pair specific enough
    to bid on.
  * WALL — the commonest colour that is not the floor. Taking the commonest colour outright
    inverts the two the moment a board's floor is larger than its surround, and then every wall
    is a road and every road a wall.
  * FURNITURE is classified by the shape of its own colour in the window centred on a lattice
    cell, never by which colour that is:
      - a filled 3x3 with little else around it    -> a BUTTON (an input, held while stood on)
      - a filled 3x3 inside an almost-filled 5x5   -> a DOOR (blocks the cell it stands on)
      - a hollow ring around a floor centre        -> a PAD (an endpoint of a swap)
    A door drawn COMPLETELY filled latches — each press flips it and it stays; one whose edge row
    is gapped is momentary and follows its button. That gap is the only difference between the
    two and it is drawn, so the distinction costs no probe.
  * A CIRCUIT is one connected region of a single colour. The wire joining a button to its door
    is drawn in the same colour and touches both ends, so connectivity IS the wiring diagram —
    no probing required, and two circuits that happen to share a colour stay separate because
    they are not connected to each other.

⛔ THE TRAP THIS FAMILY IS BUILT ON: a button is RELEASED the instant the body steps off it.
Walking to the button and then to its door is not a solution and never can be. The extra verb
rewinds the whole path just walked and leaves a CLONE behind that replays it move for move — so
the way to hold a button down is to spend a clone on it. Clones advance one step per move the
body makes, which is why WHEN a door opens is part of the answer and a plain distance map cannot
express it. The plan is therefore searched inside a full forward model of the rules.

⛔ AND: colour alone never identifies the moving body. Two blocks of the SAME colour exist here —
the body and the exit ring — and an earlier reading of this family tracked the extreme row of
that colour, which silently mixed the two together. The body is the block with the hole; the
exit is the ring with the loose dot.

⛔ WHAT IS DELIBERATELY DECLINED: a board carrying a SECOND thing drawn like the body. The
forward model has no account of it, and a plan drawn as though it were absent is a plan for a
different board. Bidding zero there costs nothing; holding on costs the level's whole budget.

Execution is one action per call, each checked against where the body actually ended up. A
disagreement retires the plan and falls back to a route drawn on the board as it is right now,
rather than continuing to steer from a fiction. The board is read off the SETTLED frame — one
command plays out as an animation and the observation carries every tick of it, so the first
tick shows a board the body has already left.
"""

from __future__ import annotations

from collections import Counter, deque
from itertools import permutations
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, has_frame, levels_completed
from admorphiq.tools.segment import components

__all__ = ["CloneWalkTool", "read_scene", "read_board", "settled_grid"]

Cell = tuple[int, int]

_SIMPLE = (1, 2, 3, 4, 5, 7)
# These boards end on their own timer at a low action count, so a route longer than this could
# not be spent even if one existed.
_MAX_ROUTE = 70
_MAX_STATES = 60_000
# Total forward-model expansions one board may cost. Planning happens once per board, but the
# tool must not stall the whole agent while it thinks.
_MAX_PLAN_STATES = 900_000
_MAX_PROBES = 30
# How many inputs a plan may consider parking a clone on, nearest to the start first — the cut
# falls on the furthest, least likely candidates.
_MAX_TARGETS = 6
# Wall pixels tolerated inside a body-sized tile before the cell counts as rock.
_TILE_SLACK = 2
_AXES: tuple[Cell, ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))


class _Door:
    """One sliding blocker: where it rests, which way it slides, and how it answers a press."""

    __slots__ = ("home", "slide", "latch", "circuit")

    def __init__(self, home: Cell, slide: Cell, latch: bool, circuit: int) -> None:
        self.home = home
        self.slide = slide
        self.latch = latch
        self.circuit = circuit


class _Board:
    """Everything static about one board, read from a single frame."""

    __slots__ = ("stride", "home", "exit", "walk", "doors", "buttons", "pads",
                 "circuit_doors", "circuit_swaps", "slots")

    def __init__(self) -> None:
        self.stride = 1
        self.home: Cell = (0, 0)
        self.exit: Cell = (0, 0)
        self.walk: set[Cell] = set()
        self.doors: list[_Door] = []
        self.buttons: dict[Cell, int] = {}
        self.pads: dict[Cell, int] = {}
        self.circuit_doors: dict[int, list[int]] = {}
        self.circuit_swaps: dict[int, list[tuple[Cell, Cell]]] = {}
        self.slots = 1


class _Scene:
    """What one frame says right now: the body, the exit, and what floor and wall mean."""

    __slots__ = ("body", "exit", "floor", "wall", "span", "others")

    def __init__(self, body: Cell, exit_: Cell, floor: int, wall: int,
                 span: int, others: list[Cell]) -> None:
        self.body = body
        self.exit = exit_
        self.floor = floor
        self.wall = wall
        self.span = span
        self.others = others


# --- reading a frame --------------------------------------------------------


def _bbox(group: list[Cell]) -> tuple[int, int, int, int]:
    ys = [c[0] for c in group]
    xs = [c[1] for c in group]
    return min(ys), min(xs), max(ys), max(xs)


def _blobs(grid: np.ndarray, colour: int) -> list[list[Cell]]:
    """4-connected regions of exactly one colour, via the shared segmentation."""
    return components((grid != colour).astype(np.int16).tolist(), {1})


def settled_grid(obs: Any) -> np.ndarray | None:
    """The board AFTER the last command finished playing out.

    ⛔ Measured on this family: one command plays out as an animation and the observation carries
    every tick of it, oldest first. Reading the first tick steers from a board the body has
    already left — the tool then re-issues moves it has made and blames the refusal on whichever
    cell it believed it was standing on. The settled board is the LAST tick. A stack whose last
    entry does not parse as a board is not a run of ticks at all (it is a stack of overlays), so
    the reading falls back to the first entry rather than inventing one.
    """
    raw = getattr(obs, "frame", None)
    if raw is None or len(raw) == 0:
        return None
    arr = np.asarray(raw)
    if arr.ndim < 3:
        return arr.astype(np.int64)
    last = arr[-1].astype(np.int64)
    if read_scene(last) is not None:
        return last
    return arr[0].astype(np.int64)


def _holed_squares(grid: np.ndarray, colour: int) -> list[tuple[Cell, int]]:
    """Every isolated solid square of ``colour`` with exactly one hole, at its centre.

    Written as window sums rather than a flood because ``detect`` runs on every frame of every
    game: the flood over all sixteen colours cost about seven milliseconds a call on boards this
    tool does not even claim, and this is the test that rejects them.
    """
    mask = (grid == colour).astype(np.int32)
    total = np.zeros((mask.shape[0] + 1, mask.shape[1] + 1), dtype=np.int32)
    total[1:, 1:] = mask.cumsum(0).cumsum(1)

    def block(y0: int, x0: int, side: int) -> np.ndarray:
        return (total[y0 + side:, x0 + side:][:mask.shape[0] - side - y0 + 1,
                                              :mask.shape[1] - side - x0 + 1]
                - total[y0:, x0 + side:][:mask.shape[0] - side - y0 + 1,
                                         :mask.shape[1] - side - x0 + 1]
                - total[y0 + side:, x0:][:mask.shape[0] - side - y0 + 1,
                                         :mask.shape[1] - side - x0 + 1]
                + total[y0:, x0:][:mask.shape[0] - side - y0 + 1,
                                  :mask.shape[1] - side - x0 + 1])

    out: list[tuple[Cell, int]] = []
    n = mask.shape[0]
    for side in range(5, min(n // 4, 11) + 1, 2):
        inner = block(0, 0, side)
        ys, xs = np.where(inner == side * side - 1)
        for y, x in zip(ys.tolist(), xs.tolist()):
            mid = (y + side // 2, x + side // 2)
            if int(grid[mid]) == colour:
                continue
            # A body is drawn standing alone: nothing of its colour touches it, which is what
            # separates it from a corner of some larger shape of the same colour.
            y0, x0 = y - 1, x - 1
            if y0 < 0 or x0 < 0 or y0 + side + 2 > n or x0 + side + 2 > n:
                continue
            if int(block(0, 0, side + 2)[y0, x0]) != side * side - 1:
                continue
            out.append((mid, side))
    return out


def read_scene(grid: np.ndarray) -> _Scene | None:
    """Recover the body and the exit, or nothing when this grammar is absent.

    Nothing is guessed: a board without a holed block AND a dotted ring of the same colour is
    not this family, and claiming it would take the turn from a tool that can solve it.
    """
    if grid.ndim != 2 or grid.shape[0] != grid.shape[1] or grid.shape[0] < 24:
        return None
    counts = Counter(int(v) for v in grid.ravel().tolist())
    if len(counts) < 3:
        return None
    bodies: dict[int, list[tuple[Cell, int]]] = {}
    for colour in counts:
        found = _holed_squares(grid, colour)
        if found:
            bodies[colour] = found
    for colour, found in sorted(bodies.items()):
        if len(found) != 1:
            continue
        rings = [
            mid for group in _blobs(grid, colour)
            for mid in [((min(c[0] for c in group) + max(c[0] for c in group)) // 2,
                         (min(c[1] for c in group) + max(c[1] for c in group)) // 2)]
            if _is_ring(grid, group, mid, colour)
        ]
        if len(rings) != 1:
            continue
        body, span = found[0]
        floor = int(grid[body])
        wall = next((c for c, _ in counts.most_common() if c != floor), floor)
        if wall == floor:
            return None
        # A block drawn the same way in ANOTHER colour is something else moving on this board,
        # not the thing being steered.
        others = [m for c, fs in bodies.items() if c != colour for m, _ in fs]
        return _Scene(body, rings[0], floor, wall, span, others)
    return None


def _is_ring(grid: np.ndarray, group: list[Cell], mid: Cell, colour: int) -> bool:
    """A hollow shape with a LOOSE cell of its own colour at the middle — the exit marker."""
    y0, x0, y1, x1 = _bbox(group)
    h, w = y1 - y0 + 1, x1 - x0 + 1
    if h != w or h < 7 or h % 2 == 0 or not 8 <= len(group) < h * w - 1:
        return False
    if int(grid[mid]) != colour:
        return False
    return all(int(grid[mid[0] + dy, mid[1] + dx]) != colour
               for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)))


def _circuit_map(grid: np.ndarray, floor: int, wall: int) -> dict[Cell, int]:
    """Label every non-floor, non-wall pixel with the id of its connected colour region."""
    label: dict[Cell, int] = {}
    nid = 0
    for colour in sorted({int(v) for v in grid.ravel().tolist()} - {floor, wall}):
        for group in _blobs(grid, colour):
            for cell in group:
                label[cell] = nid
            nid += 1
    return label


def tally_patch(grid: np.ndarray) -> bytes:
    """The corner strip carrying the board's clone tally, as a comparable stamp.

    ⛔ This is how the rewind is told apart from a move, and nothing else can do it: rewinding a
    ONE-move path puts the body exactly one cell from where it stood, which reads as an ordinary
    step and was measured being learned as "up". The tally is the only thing on the board that
    answers to the rewind and to nothing else.
    """
    n = grid.shape[0]
    return np.ascontiguousarray(grid[:max(4, n // 10), :max(8, n // 4)]).tobytes()


def _count_slots(grid: np.ndarray, wall: int, floor: int) -> int:
    """How many replay clones the board offers, counted off its own tally marks.

    The marks are a ROW OF EQUAL SQUARES pinned in a corner outside the play area. The count is
    load-bearing: spending one clone MORE than the board has resets every clone already parked,
    so a plan that miscounts throws away the work it just did.

    ⛔ They are NOT counted per colour. The mark for the clone currently being recorded is drawn
    differently from the rest, so counting the commonest colour's squares returns one on a board
    that offers two. What identifies a tally is that the marks are the same SIZE and sit on the
    same ROW; the row with the most such squares is the tally.
    """
    n = grid.shape[0]
    depth, width = max(4, n // 10), max(8, n // 4)
    # The shared segmentation walks a SQUARE grid, so the strip is padded out with wall — which
    # is inert here, because wall is never one of the colours counted.
    patch = np.full((width, width), wall, dtype=np.int64)
    patch[:depth, :width] = grid[:depth, :width]
    rows: Counter[tuple[int, int]] = Counter()
    for colour in sorted({int(v) for v in patch.ravel().tolist()} - {wall, floor}):
        for group in _blobs(patch, colour):
            y0, x0, y1, x1 = _bbox(group)
            side = y1 - y0 + 1
            if side != x1 - x0 + 1 or side < 3 or len(group) < side * side - 1:
                continue
            rows[(side, y0)] += 1
    return max(1, max(rows.values(), default=1))


def _pad_ring(grid: np.ndarray, cell: Cell, half: int, scene: _Scene) -> Cell | None:
    """A ring of one colour drawn around a floor centre marks a swap endpoint."""
    y, x = cell
    win = grid[y - half:y + half + 1, x - half:x + half + 1]
    if win.shape[0] != 2 * half + 1 or win.shape[1] != 2 * half + 1:
        return None
    ring = np.concatenate([win[0, :], win[-1, :], win[1:-1, 0], win[1:-1, -1]])
    colour, hits = Counter(int(v) for v in ring.tolist()).most_common(1)[0]
    if colour in (scene.floor, scene.wall) or hits < ring.size - 2:
        return None
    if int((win[1:-1, 1:-1] == colour).sum()):
        return None
    return (y - half, x - half)


def _slide(grid: np.ndarray, cell: Cell, half: int, colour: int) -> Cell | None:
    """Which way this blocker moves: toward the single tab that sticks out of its body.

    The tab is where the wire lands, so it is drawn on every one of these and reading it is
    free. Without it the blocker's destination is unknown, and a plan can route the body
    straight into the cell the blocker slid into.
    """
    y, x = cell
    for dy, dx in ((half, 0), (-half, 0), (0, half), (0, -half)):
        if int(grid[y + dy, x + dx]) == colour:
            return (dy // half, dx // half)
    return None


def read_board(grid: np.ndarray, scene: _Scene, stride: int) -> _Board | None:
    """Cut the frame into cells and name every piece of furniture standing on one."""
    n = grid.shape[0]
    if stride < 3 or stride > n // 4:
        return None
    if (scene.exit[0] - scene.body[0]) % stride or (scene.exit[1] - scene.body[1]) % stride:
        return None
    board = _Board()
    board.stride = stride
    board.home = scene.body
    board.exit = scene.exit
    circuits = _circuit_map(grid, scene.floor, scene.wall)
    half = stride // 2
    span = max(1, (scene.span - 1) // 2)
    for y in range(scene.body[0] % stride, n, stride):
        for x in range(scene.body[1] % stride, n, stride):
            if not (half <= y < n - half and half <= x < n - half):
                continue
            colour = int(grid[y, x])
            if colour == scene.wall:
                continue
            # ⛔ ONE pixel is not enough to call a cell a road. The wire joining a button to its
            # door is drawn straight ACROSS walls, so the cell under it reads as furniture and a
            # route was planned through solid rock — measured, the body simply refused to move.
            # The body's own drawing is the footprint that has to fit, so the whole tile is what
            # gets tested. Against the engine's own mask this is EXACT on every board seen.
            tile = grid[y - span:y + span + 1, x - span:x + span + 1]
            if int((tile == scene.wall).sum()) > _TILE_SLACK:
                continue
            board.walk.add((y, x))
            if colour == scene.floor:
                anchor = _pad_ring(grid, (y, x), half, scene)
                if anchor is not None:
                    board.pads[(y, x)] = circuits.get(anchor, -1)
                continue
            if not bool((grid[y - 1:y + 2, x - 1:x + 2] == colour).all()):
                continue
            win = grid[y - half + 1:y + half, x - half + 1:x + half]
            filled, area = int((win == colour).sum()), win.size
            cid = circuits.get((y, x), -1)
            if filled >= area - 4:
                slide = _slide(grid, (y, x), half, colour)
                if slide is None:
                    continue
                board.circuit_doors.setdefault(cid, []).append(len(board.doors))
                board.doors.append(_Door((y, x), slide, filled >= area, cid))
            elif filled <= area // 2:
                board.buttons[(y, x)] = cid
    _pair_pads(board)
    board.slots = _count_slots(grid, scene.wall, scene.floor)
    return board


def _pair_pads(board: _Board) -> None:
    """Join swap endpoints two by two — nearest first, inside the circuit that feeds them."""
    by_circuit: dict[int, list[Cell]] = {}
    for cell, cid in board.pads.items():
        by_circuit.setdefault(cid, []).append(cell)
    for cid, cells in by_circuit.items():
        left = sorted(cells)
        while len(left) >= 2:
            a = left.pop(0)
            b = min(left, key=lambda c: abs(c[0] - a[0]) + abs(c[1] - a[1]))
            left.remove(b)
            board.circuit_swaps.setdefault(cid, []).append((a, b))


# --- the forward model ------------------------------------------------------


class _World:
    """An exact forward model of the board's rules — the thing the plan is searched inside."""

    def __init__(self, board: _Board) -> None:
        self.b = board
        self.open = [False] * len(board.doors)
        self.ghosts: list[list[Cell]] = []
        self.expansions = 0
        self.t = 0
        self.pos = board.home
        self.gpos: list[Cell] = []
        self.path: list[Cell] = []
        self._settle(False)

    # -- state ---------------------------------------------------------------

    def key(self) -> tuple:
        return (self.t, self.pos, tuple(self.gpos), tuple(self.open))

    def snapshot(self) -> tuple:
        return (self.t, self.pos, tuple(self.gpos), tuple(self.open), tuple(self.path))

    def restore(self, snap: tuple) -> None:
        self.t, self.pos, gpos, opened, path = snap
        self.gpos = list(gpos)
        self.open = list(opened)
        self.path = list(path)

    # -- rules ---------------------------------------------------------------

    def _door_cell(self, i: int) -> Cell:
        door = self.b.doors[i]
        if not self.open[i]:
            return door.home
        return (door.home[0] + door.slide[0] * self.b.stride,
                door.home[1] + door.slide[1] * self.b.stride)

    def _passable(self, cell: Cell) -> bool:
        if cell not in self.b.walk:
            return False
        return all(self._door_cell(i) != cell for i in range(len(self.b.doors)))

    def _occupants(self) -> dict[Cell, set[str]]:
        occ: dict[Cell, set[str]] = {}
        occ.setdefault(self.pos, set()).add("P")
        for i, g in enumerate(self.gpos):
            occ.setdefault(g, set()).add(f"G{i}")
        return occ

    def _fire(self, cell: Cell, body: str, value: bool, occ: dict[Cell, set[str]],
              swaps: list[tuple[Cell, Cell]], rewinding: bool) -> None:
        """One body arriving at or leaving one cell, plus whatever edge that creates."""
        here = occ.setdefault(cell, set())
        was = bool(here)
        if value:
            here.add(body)
        else:
            here.discard(body)
        cid = self.b.buttons.get(cell)
        if cid is None or bool(here) == was:
            return
        for idx in self.b.circuit_doors.get(cid, ()):
            if self.b.doors[idx].latch:
                if value:
                    self.open[idx] = not self.open[idx]
            else:
                self.open[idx] = value
        # A swap fires on the press while playing and on the release while rewinding — the
        # board runs its wiring backwards along with everything else.
        if value != rewinding:
            swaps.extend(self.b.circuit_swaps.get(cid, ()))

    def _settle(self, rewinding: bool) -> None:
        occ: dict[Cell, set[str]] = {}
        swaps: list[tuple[Cell, Cell]] = []
        self._fire(self.pos, "P", True, occ, swaps, rewinding)
        for i, g in enumerate(self.gpos):
            self._fire(g, f"G{i}", True, occ, swaps, rewinding)
        self._apply_swaps(swaps)

    def _apply_swaps(self, swaps: list[tuple[Cell, Cell]]) -> None:
        for a, b in swaps:
            on_a, on_b = self._names_at(a), self._names_at(b)
            for name in on_a:
                self._place(name, b)
            for name in on_b:
                self._place(name, a)

    def _names_at(self, cell: Cell) -> list[str]:
        out = ["P"] if self.pos == cell else []
        return out + [f"G{i}" for i, g in enumerate(self.gpos) if g == cell]

    def _place(self, name: str, cell: Cell) -> None:
        if name == "P":
            self.pos = cell
        else:
            self.gpos[int(name[1:])] = cell

    def move(self, step: Cell) -> bool:
        """One command. False when the board refuses it — and then NOTHING advances."""
        self.expansions += 1
        dest = (self.pos[0] + step[0] * self.b.stride, self.pos[1] + step[1] * self.b.stride)
        if not self._passable(dest):
            return False
        occ = self._occupants()
        swaps: list[tuple[Cell, Cell]] = []
        self._fire(self.pos, "P", False, occ, swaps, False)
        self.pos = dest
        for i, ghost in enumerate(self.ghosts):
            if self.t >= len(ghost):
                continue
            gstep = ghost[self.t]
            gdest = (self.gpos[i][0] + gstep[0] * self.b.stride,
                     self.gpos[i][1] + gstep[1] * self.b.stride)
            if not self._passable(gdest):
                continue
            self._fire(self.gpos[i], f"G{i}", False, occ, swaps, False)
            self.gpos[i] = gdest
        self._fire(self.pos, "P", True, occ, swaps, False)
        for i, g in enumerate(self.gpos):
            self._fire(g, f"G{i}", True, occ, swaps, False)
        self._apply_swaps(swaps)
        self.path.append(step)
        self.t += 1
        return True

    def rewind(self) -> None:
        """Retrace the path backwards, leave a clone replaying it, and start the pass over.

        The retrace is simulated rather than assumed away: the body crosses every cell of the
        path a second time on the way back, and a LATCHING door counts each of those crossings.
        """
        if not self.path:
            return
        recorded = list(self.path)
        occ = self._occupants()
        while self.path:
            step = self.path.pop()
            idx = len(self.path)
            swaps: list[tuple[Cell, Cell]] = []
            for i, ghost in enumerate(self.ghosts):
                if idx >= len(ghost):
                    continue
                gstep = ghost[idx]
                gdest = (self.gpos[i][0] - gstep[0] * self.b.stride,
                         self.gpos[i][1] - gstep[1] * self.b.stride)
                if not self._passable(gdest):
                    continue
                self._fire(self.gpos[i], f"G{i}", False, occ, swaps, True)
                self.gpos[i] = gdest
            back = (self.pos[0] - step[0] * self.b.stride,
                    self.pos[1] - step[1] * self.b.stride)
            if self._passable(back):
                self._fire(self.pos, "P", False, occ, swaps, True)
                self.pos = back
            self.t -= 1
            self._fire(self.pos, "P", True, occ, swaps, True)
            for i, g in enumerate(self.gpos):
                self._fire(g, f"G{i}", True, occ, swaps, True)
            self._apply_swaps(swaps)
        self.ghosts.append(recorded)
        self.t = 0
        self.pos = self.b.home
        self.gpos = [self.b.home] * len(self.ghosts)
        self.path = []
        self._settle(False)

    # -- searching -----------------------------------------------------------

    def route(self, target: Cell, moves: list[Cell]) -> list[Cell] | None:
        """Shortest command sequence from HERE that lands the body on ``target``."""
        if self.pos == target:
            return []
        start = self.snapshot()
        seen = {self.key()}
        queue: deque[tuple[tuple, list[Cell]]] = deque([(start, [])])
        found: list[Cell] | None = None
        states = 0
        while queue and found is None:
            snap, taken = queue.popleft()
            if len(taken) >= _MAX_ROUTE:
                continue
            for step in moves:
                self.restore(snap)
                if not self.move(step):
                    continue
                states += 1
                if states > _MAX_STATES or self.expansions > _MAX_PLAN_STATES:
                    queue.clear()
                    break
                if self.pos == target:
                    found = taken + [step]
                    break
                k = self.key()
                if k in seen:
                    continue
                seen.add(k)
                queue.append((self.snapshot(), taken + [step]))
        self.restore(start)
        return found


def _reach(board: _Board, start: Cell, blocked: set[Cell],
           bridges: bool = False) -> dict[Cell, Cell | None]:
    """Plain flood over the lattice — used only to decide WHICH inputs are worth a clone.

    ⛔ With ``bridges`` the swap pads are treated as one step apart. They have to be: on several
    of these boards the exit sits in a region the walk CANNOT reach at all, joined to the rest
    only by a swap, and a flood that ignores that reports the board unsolvable and asks for no
    clone at all — so the button that opens the door on the way was never even considered.
    """
    seen: dict[Cell, Cell | None] = {start: None}
    queue = deque([start])
    partner: dict[Cell, Cell] = {}
    if bridges:
        for pairs in board.circuit_swaps.values():
            for a, b in pairs:
                partner[a] = b
                partner[b] = a
    while queue:
        cell = queue.popleft()
        nexts = [(cell[0] + dy * board.stride, cell[1] + dx * board.stride)
                 for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        if cell in partner:
            nexts.append(partner[cell])
        for nxt in nexts:
            if nxt in seen or nxt not in board.walk or nxt in blocked:
                continue
            seen[nxt] = cell
            queue.append(nxt)
    return seen


# --- the tool ---------------------------------------------------------------


class CloneWalkTool:
    """Walk the body to the marked exit, parking a replay clone on every button that gates it."""

    name = "clonewalk"

    def __init__(self) -> None:
        # What each command means outlives a board; only the board itself is redrawn.
        self._delta: dict[int, Cell] = {}
        self._rewind: int | None = None
        self._span = 0
        self._probes = 0
        self._board_key: tuple | None = None
        self._cache: tuple[bytes, float] | None = None
        self.reset()

    def reset(self) -> None:
        self._board: _Board | None = None
        self._plan: list[int] | None = None
        self._expect: list[Cell] | None = None
        self._cursor = 0
        self._pending: tuple[int, Cell, bytes] | None = None
        self._tally = b""
        self._tally0 = b""
        self._recover = 0
        self._refused: set[tuple[int, Cell]] = set()
        self._was: Cell | None = None
        self._sent: int | None = None
        self._seen_at: Cell | None = None
        self._trail = 0
        self._dead = False

    # -- protocol ------------------------------------------------------------

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Learning runs off the body's measured displacement, taken in propose()."""

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Bid only on a board showing the whole grammar, and never once this one is given up.

        ⛔ A tool with no plan must bid ZERO. A consolation bid is not free — it takes the turn
        from whichever tool could have solved the board, measured elsewhere as a 10x loss on a
        game the bidder never fitted.
        """
        if self._dead or not has_frame(obs):
            return 0.0
        simple, action6 = availability(obs)
        if action6 or len({1, 2, 3, 4} & set(simple)) < 4 or 5 not in simple:
            return 0.0
        grid = settled_grid(obs)
        if grid is None:
            return 0.0
        if self._board is not None and self._plan is not None:
            # Already holding a plan for this board — and the clones this tool parks are drawn
            # exactly like the body, so re-reading the board mid-plan would see its own work as
            # a stranger and hand the board away in the middle of a route.
            return 0.75
        stamp = grid.tobytes()
        if self._cache is not None and self._cache[0] == stamp:
            return self._cache[1]
        scene = read_scene(grid)
        score = 0.0
        if scene is not None and not scene.others:
            board = read_board(grid, scene, self._span or scene.span + 1)
            if board is not None and board.doors and board.exit in board.walk:
                score = 0.75
        self._cache = (stamp, score)
        return score

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        grid = settled_grid(obs)
        if grid is None:
            return []
        scene = read_scene(grid)
        if scene is None:
            return []
        simple, _ = availability(obs)
        legal = [a for a in _SIMPLE if a in simple]
        if len({1, 2, 3, 4} & set(simple)) < 4:
            return []
        key = (levels_completed(obs), scene.exit, scene.span)
        if key != self._board_key:
            self._board_key = key
            self.reset()
            self._tally0 = tally_patch(grid)
        self._tally = tally_patch(grid)
        self._track(scene)
        self._learn(scene)
        self._settle_controls(legal)
        if self._dead:
            return []
        if len(self._delta) < 4 or self._rewind is None:
            return self._probe_step(scene, legal)
        if self._board is None and (self._tally != self._tally0 or self._trail):
            # ⛔ Naming the commands cost a tally mark. A plan is computed for a board with all
            # its clones in hand, so the marks are wound back BEFORE planning: spending the rest
            # wraps the tally and clears every clone, which is exactly what is wanted.
            #
            # ⛔ And only before planning. Left ungated this fires on the plan's OWN rewind — the
            # tally has legitimately moved — and the extra rewind wrapped the tally, deleted the
            # clone the plan had just parked, and left the body standing at a door that never
            # opened again. Measured: the level was lost from a winning position.
            spent = self._spend_marks(grid, scene)
            if spent is not None:
                return spent
        if self._board is None:
            if scene.others:
                # ⛔ Something else is moving on this board and the forward model has no account
                # of it. A plan drawn as if it were not there is a plan for a different board;
                # declining costs nothing, and holding on costs the whole level's budget.
                self._dead = True
                return []
            if not self._build(grid, scene):
                return []
        return self._advance(grid, scene)

    def _emit(self, action: int, body: Cell) -> list[Step]:
        """Every command leaves through here, so the recorded path is never guessed at."""
        self._sent = action
        self._seen_at = body
        return [(action, None)]

    def _track(self, scene: _Scene) -> None:
        """Keep the length of the path the next rewind would replay.

        ⛔ This is not bookkeeping. A plan is computed for a body standing at the start with
        NOTHING recorded, and the commands spent naming the controls are recorded moves like any
        other — so the clone spent on a button replayed those first and arrived four moves late,
        at a door the body had already been refused by. Measured: a level lost from a plan that
        was correct for the board it assumed.
        """
        if self._sent is None:
            return
        if self._sent == self._rewind:
            self._trail = 0
        elif self._seen_at is not None and scene.body != self._seen_at:
            self._trail += 1

    # -- learning the commands ------------------------------------------------

    def _settle_controls(self, legal: list[int]) -> None:
        """Fill in whatever the probes have already made inevitable.

        ⛔ Two commands never need probing and both were measured costing real actions. The
        LAST direction is settled by elimination — four movement commands mean the four
        directions, and probing the fourth from a cell whose remaining side is a wall repeats
        forever (thirty refusals of the same command from the same cell). The REWIND is settled
        the same way, and must be: probing it while a path exists spends a clone the plan needs.
        """
        unnamed = [a for a in legal if a not in self._delta and a != self._rewind]
        fresh = [d for d in _AXES if d not in self._delta.values()]
        if len(unnamed) == 1 and len(fresh) == 1:
            self._delta[unnamed[0]] = fresh.pop()
            unnamed = []
        if self._rewind is None and len(self._delta) == 4:
            spare = [a for a in legal if a not in self._delta]
            if len(spare) != 1:
                self._dead = True
                return
            self._rewind = spare[0]

    def _probe_step(self, scene: _Scene, legal: list[int]) -> list[Step]:
        """Try an unnamed command and watch what the body does."""
        self._probes += 1
        if self._probes > _MAX_PROBES:
            self._dead = True
            return []
        unnamed = [a for a in legal if a not in self._delta and a != self._rewind]
        untried = [a for a in unnamed if (a, scene.body) not in self._refused]
        if untried:
            action = untried[0]
            self._pending = (action, scene.body, self._tally)
            return self._emit(action, scene.body)
        if not unnamed:
            self._dead = True
            return []
        # Every unnamed command has already been refused HERE, so a probe only says something
        # somewhere else: take a named step first.
        stride = self._span or scene.span + 1
        for action, step in sorted(self._delta.items()):
            dest = (scene.body[0] + step[0] * stride, scene.body[1] + step[1] * stride)
            if dest == self._was:
                continue
            self._was = scene.body
            return self._emit(action, scene.body)
        self._dead = True
        return []

    def _learn(self, scene: _Scene) -> None:
        """Name the command just issued by the displacement it produced."""
        if self._pending is None:
            return
        action, before, marks = self._pending
        self._pending = None
        if marks != self._tally:
            # Only the rewind spends a tally mark.
            self._rewind = action
            return
        dy, dx = scene.body[0] - before[0], scene.body[1] - before[1]
        if dy == 0 and dx == 0:
            self._refused.add((action, before))
            return
        if (dy and dx) or (self._span and max(abs(dy), abs(dx)) != self._span):
            self._rewind = action
            return
        span = max(abs(dy), abs(dx))
        self._span = span
        self._delta[action] = (dy // span if dy else 0, dx // span if dx else 0)

    def _spend_marks(self, grid: np.ndarray, scene: _Scene) -> list[Step] | None:
        """Burn the remaining clones so the tally wraps back to a full board."""
        self._recover += 1
        if self._recover > 4 * _MAX_PROBES:
            self._dead = True
            return []
        board = read_board(grid, scene, self._span or scene.span + 1)
        if board is None:
            self._dead = True
            return []
        if self._trail == 0:
            for action, step in sorted(self._delta.items()):
                dest = (scene.body[0] + step[0] * board.stride,
                        scene.body[1] + step[1] * board.stride)
                if dest in board.walk:
                    return self._emit(action, scene.body)
            self._dead = True
            return []
        return self._emit(self._rewind or 0, scene.body)

    # -- planning -------------------------------------------------------------

    def _moves(self) -> list[Cell]:
        return [self._delta[a] for a in sorted(self._delta)]

    def _action_of(self, step: Cell) -> int:
        return next(a for a, d in self._delta.items() if d == step)

    def _build(self, grid: np.ndarray, scene: _Scene) -> bool:
        board = read_board(grid, scene, self._span or scene.span + 1)
        if board is None or not board.doors or board.exit not in board.walk:
            self._dead = True
            return False
        self._board = board
        plan = self._solve(board)
        if plan is None:
            self._dead = True
            return False
        self._plan, self._expect = plan
        self._cursor = 0
        return True

    def _gating(self, board: _Board) -> list[Cell]:
        """The inputs a clone is worth spending on: those wired to something in the way.

        ⛔ Not simply "every input the body walks past". A board with inputs that gate nothing on
        the way out will happily take every clone and leave none for the one that matters, so the
        dependency is chased instead: route out with every door imagined open and every swap
        imagined usable, take the doors and swaps that route needs, take THEIR buttons, then
        route to those and repeat.
        """
        wanted: list[Cell] = []
        seen: set[Cell] = set()
        pending = [board.exit]
        guard = 0
        while pending and guard < 12:
            guard += 1
            goal = pending.pop()
            if goal in seen:
                continue
            seen.add(goal)
            tree = _reach(board, board.home, set(), bridges=True)
            if goal not in tree:
                continue
            cell: Cell | None = goal
            while cell is not None:
                for circuit in self._circuits_at(board, cell):
                    for button in sorted(board.buttons):
                        if board.buttons[button] == circuit and button not in wanted:
                            wanted.append(button)
                            pending.append(button)
                if cell in board.pads and cell not in wanted:
                    wanted.append(cell)
                    pending.append(cell)
                cell = tree[cell]
        # ⛔ The chase alone is not the candidate set. Measured: a board whose exit needs a door
        # whose button sits behind ANOTHER door returns only the buttons it cannot reach, and
        # every plan starts with a leg that cannot be walked. The inputs the body CAN reach are
        # always candidates too — that is where a first clone has to come from.
        rest = [c for c in list(board.buttons) + list(board.pads) if c not in wanted]
        rest.sort(key=lambda c: abs(c[0] - board.home[0]) + abs(c[1] - board.home[1]))
        return (wanted + rest)[:_MAX_TARGETS]

    @staticmethod
    def _circuits_at(board: _Board, cell: Cell) -> list[int]:
        """Which wiring a cell depends on: a door's own circuit, or a pad's swap circuit."""
        out = [door.circuit for door in board.doors if door.home == cell]
        if cell in board.pads:
            out.append(board.pads[cell])
        return out

    def _solve(self, board: _Board) -> tuple[list[int], list[Cell]] | None:
        """Shortest plan: park k clones on gating inputs, then walk out. k grows from zero."""
        moves = self._moves()
        if len(moves) < 4:
            return None
        targets = self._gating(board)
        budget = max(0, board.slots - 1)
        # A plan whose FIRST leg cannot be walked is not a plan; testing that once per target
        # rather than once per ordering is what keeps the search affordable.
        opener = {t: _World(board).route(t, moves) for t in targets}
        best: tuple[list[int], list[Cell]] | None = None
        for k in range(0, budget + 1):
            for order in permutations(targets, k):
                if order and opener[order[0]] is None:
                    continue
                got = self._attempt(board, order, moves)
                if got is not None and (best is None or len(got[0]) < len(best[0])):
                    best = got
            if best is not None:
                return best
        return best

    def _attempt(self, board: _Board, order: tuple[Cell, ...],
                 moves: list[Cell]) -> tuple[list[int], list[Cell]] | None:
        world = _World(board)
        actions: list[int] = []
        expect: list[Cell] = []
        for target in order:
            leg = world.route(target, moves)
            if leg is None:
                return None
            for step in leg:
                world.move(step)
                actions.append(self._action_of(step))
                expect.append(world.pos)
            world.rewind()
            actions.append(self._rewind or 0)
            expect.append(world.pos)
        leg = world.route(board.exit, moves)
        if leg is None:
            return None
        for step in leg:
            world.move(step)
            actions.append(self._action_of(step))
            expect.append(world.pos)
        return actions, expect

    # -- execution -------------------------------------------------------------

    def _advance(self, grid: np.ndarray, scene: _Scene) -> list[Step]:
        """Issue the next command, having checked the last one landed where it was meant to."""
        assert self._board is not None
        if self._plan is not None and self._expect is not None:
            if self._cursor and scene.body != self._expect[self._cursor - 1]:
                self._plan = None
            elif self._cursor < len(self._plan):
                action = self._plan[self._cursor]
                self._cursor += 1
                return self._emit(action, scene.body)
            else:
                self._plan = None
        return self._walk_out(grid, scene)

    def _walk_out(self, grid: np.ndarray, scene: _Scene) -> list[Step]:
        """The board is not where the plan said: route on the board as it is drawn right now."""
        board = read_board(grid, scene, self._span or scene.span + 1)
        if board is None:
            self._dead = True
            return []
        blocked = {door.home for door in board.doors}
        tree = _reach(board, scene.body, blocked)
        if board.exit not in tree:
            self._dead = True
            return []
        cell, route = board.exit, []
        while tree[cell] is not None:
            route.append(cell)
            cell = tree[cell]
        step = route[-1]
        delta = ((step[0] - scene.body[0]) // board.stride,
                 (step[1] - scene.body[1]) // board.stride)
        try:
            return self._emit(self._action_of(delta), scene.body)
        except StopIteration:
            self._dead = True
            return []
