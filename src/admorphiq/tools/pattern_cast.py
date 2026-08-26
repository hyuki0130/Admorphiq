"""Reproduce a pattern the board is SHOWING you, then walk the avatar to its exit.

The mechanic, recovered frame-only: a compact panel carries a complete k x k lattice of
equal square cells. Most sit at one neutral colour; a minority are painted in a second.
That minority is not decoration — it is an INSTRUCTION. Clicking each painted cell arms
it, and when the armed set equals the painted set the board resolves the pattern in one
shot, changing the avatar (it shrinks, or it is carried elsewhere) so that a route which
was geometrically impossible becomes walkable. The lattice then goes quiet, which is also
how the tool knows there is nothing further to enter.

Two things make this a plan rather than a search. The instruction is fully visible, so no
combination is ever tried: a cast costs exactly the number of painted cells. And the panel
that shows the pattern also METERS the level — every cell entered and every step taken is
charged against a per-level allowance, and running it out ends the game — so exploring is
not merely slow here, it loses.

Selectivity comes from the instruction itself. ``detect`` scores 0 unless a complete
lattice is present AND cells are painted on it: a quiet lattice means this tool has nothing
to enter and no business taking the turn.
"""

from __future__ import annotations

from collections import Counter, deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, frame_2d, has_frame, levels_completed
from admorphiq.tools.segment import background, components, edge_band, uniform_blocks

__all__ = ["PatternCastTool"]

# Below 3x3 is not a pattern; above 5x5 is a board, not an instruction panel.
_MIN_K = 3
_MAX_K = 5
# Cell sizes worth testing, largest first: every smaller square inside a flat cell is also
# "uniform", so the biggest lattice that closes is the real one.
_SIDES = (5, 4, 3, 2)
# A click can be swallowed by an animation. Re-enter the same cell, but not forever.
_MAX_REENTRY = 3
# A path longer than this is not a plan, it is a wander — and the allowance forbids it.
_MAX_PATH = 64

Cell = tuple[int, int]
Box = tuple[int, int, int, int]


class PatternCastTool:
    """Enter the displayed pattern, then navigate the avatar into its exit."""

    name = "pattern_cast"

    def __init__(self) -> None:
        self._level = -1
        self.reset()

    # --- lifecycle ---------------------------------------------------------

    def reset(self) -> None:
        """Drop everything learned about one level's board and lattice."""
        self._entered: dict[Cell, int] = {}
        self._awaiting: tuple[Cell, int] | None = None
        self._reentry = 0
        self._avatar_palette: frozenset[int] | None = None
        self._avatar_box: Box | None = None
        self._goal: set[Cell] | None = None
        self._floor: int | None = None
        self._stride: int | None = None
        self._prev: np.ndarray | None = None
        self._prev_step: Step | None = None
        self._blocked: set[int] = set()
        self._faced = False
        self._heading: int | None = None
        self._aim: tuple[Cell, int] | None = None
        self._rearms = 0
        self._reads = 0
        self._seen: set[Box] = set()

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Learning happens in ``propose``, which sees both sides of a transition."""

    # --- detection ---------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Confidence that a pattern is on display for us to reproduce."""
        if not has_frame(obs):
            return 0.0
        simple, click_ok = availability(obs)
        if not click_ok or len(simple) < 4:
            return 0.0
        pad = _find_pad(frame_2d(obs))
        if pad is None or not _painted(pad[2]):
            return 0.0
        return 0.9

    # --- planning ----------------------------------------------------------

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        """One action at a time: the board is deliberately re-read every turn.

        A level-up leaves the finished board on screen for one more frame, and a cast
        rewrites the avatar mid-plan, so any queued sequence is planning against a
        position that no longer exists.
        """
        if not has_frame(obs):
            return []
        simple, click_ok = availability(obs)
        if not click_ok:
            return []
        grid = frame_2d(obs)
        level = levels_completed(obs)
        if level != self._level:
            fresh = self._level >= 0
            self._level = level
            self.reset()
            if fresh:
                # A cleared level leaves the FINISHED board on screen for one more frame,
                # avatar already merged into its exit. Planning on it is not merely wasted:
                # a lattice click aimed at the old pattern lands on the NEW one and arms a
                # cell the new pattern does not want, which no later click can undo without
                # spending the allowance twice. Spend one inert click and look again.
                again = self._read_again(grid)
                if again is not None:
                    return [again]

        pad = _find_pad(grid)
        if pad is None:
            return []
        origins, side, colours = pad
        panel = _panel_box(grid, origins)

        self._confirm_entry(colours)
        self._learn(grid, panel)
        # Walk BEFORE entering anything. A resolved pattern can be directional — it acts
        # the way the avatar faces — so entering it from wherever we happen to stand
        # spends the allowance on a shot into a wall. Walking first both closes the
        # distance and, when the last step is refused, leaves the avatar facing exactly
        # the thing that refused it.
        step = self._navigate(grid, panel, simple)
        if step is None:
            step = self._face_then_enter(origins, side, colours)
        if step is None:
            step = self._read_again(grid)
        if step is None:
            step = self._rearm(grid, panel)
        if step is None:
            return []
        self._prev = grid
        self._prev_step = step
        return [step]

    # --- phase 1: reproduce the displayed pattern --------------------------

    def _confirm_entry(self, colours: list[list[int]]) -> None:
        """A cell counts as entered only once its colour has actually moved.

        Believing the click instead of the frame is what breaks on a swallowed action:
        the pattern then stays one cell short forever and never resolves.
        """
        if self._awaiting is None:
            return
        (r, c), before = self._awaiting
        now = colours[r][c]
        if now != before:
            self._entered[(r, c)] = before
            self._awaiting = None
            self._reentry = 0
        else:
            self._reentry += 1
            if self._reentry > _MAX_REENTRY:
                self._awaiting = None
                self._reentry = 0

    def _face_then_enter(
        self, origins: list[list[Cell]], side: int, colours: list[list[int]]
    ) -> Step | None:
        """Turn to the refusing direction once, then enter the pattern.

        A refused step still turns the avatar, which costs one unit of the allowance and
        is the only way to aim a directional resolution. Done once per standstill.
        """
        facing = self._prev_step[0] if self._prev_step else None
        if not self._faced and self._heading is not None:
            self._faced = True
            if self._heading != facing:
                return (self._heading, None)
        return self._enter_pattern(origins, side, colours)

    def _rearm(self, grid: np.ndarray, panel: Box) -> Step | None:
        """The lattice has gone quiet while we are still stuck — ask for a new pattern.

        Boards of this family park their instructions in FURNITURE: framed boxes that
        stand off the walkable area entirely, one per pattern the level allows. Clicking
        one puts its pattern back on the lattice. Furniture is identified by exactly that
        property — it is a piece the avatar could never walk up to, because the ground
        inside its frame is not joined to the ground the avatar stands on. Cycled so a
        level offering several patterns eventually offers the one that helps, and capped
        so a level offering none cannot spin.
        """
        if self._avatar_box is None or self._floor is None:
            return None
        board = _board_only(grid, panel)
        ground = _ground(board, self._avatar_box, self._floor)
        shelf = [
            o for o in self._objects(grid, board)
            if not (_halo(o["cells"]) & ground) and o["cells"].isdisjoint(self._goal or set())
        ]
        if not shelf or self._rearms >= 2 * len(shelf):
            return None
        shelf.sort(key=lambda o: (-o["size"], o["box"]))
        pick = shelf[self._rearms % len(shelf)]
        self._rearms += 1
        self._seen.clear()
        y0, x0, y1, x1 = pick["box"]
        return (6, ((x0 + x1) // 2, (y0 + y1) // 2))

    def _read_again(self, grid: np.ndarray) -> Step | None:
        """Nothing is readable — spend one inert click to get a fresh frame.

        A cleared level leaves the FINISHED board on screen for one more frame, with the
        avatar already merged into its exit and nothing left to pair. Clicking bare wall is
        the least committal way to ask again: it touches no piece and no cell of the
        lattice. Once per level, so a genuinely dead board cannot loop.
        """
        if self._reads >= 2:
            return None
        wall = background(grid)
        for y, x in ((0, 0), (grid.shape[0] - 1, 0)):
            if int(grid[y][x]) in wall:
                self._reads += 1
                return (6, (x, y))
        return None

    def _enter_pattern(
        self, origins: list[list[Cell]], side: int, colours: list[list[int]]
    ) -> Step | None:
        """Click one painted cell, or nothing when the pattern is fully entered.

        "Entered" is held against the colour the cell took, so a cell toggled back off by
        a stray click returns to the pending list on its own.
        """
        painted = _painted(colours)
        if not painted:
            # The lattice has gone quiet: whatever was entered has been resolved, so the
            # board is a different board and every square is worth standing on again.
            if self._entered:
                self._seen.clear()
                self._entered.clear()
            return None
        pending = [
            cell for cell in painted
            if cell not in self._entered
            or self._entered[cell] == colours[cell[0]][cell[1]]
        ]
        if not pending:
            return None
        if self._awaiting is not None and self._reentry > _MAX_REENTRY:
            return None
        r, c = self._awaiting[0] if self._awaiting is not None else pending[0]
        self._awaiting = ((r, c), colours[r][c])
        y, x = origins[r][c]
        return (6, (x + side // 2, y + side // 2))

    # --- what the last transition taught -----------------------------------

    def _learn(self, grid: np.ndarray, panel: Box) -> None:
        """Read the effect of our own last action off the two frames."""
        prev, last = self._prev, self._prev_step
        if prev is None or last is None or last[0] == 6 or self._avatar_box is None:
            return
        box = self._track(grid, panel)
        if box is None:
            return
        if box == self._avatar_box:
            self._blocked.add(last[0])
            return
        self._blocked.clear()
        self._faced = False
        # Cells the avatar left behind are, by definition, walkable ground.
        vacated = _box_cells(self._avatar_box) - _box_cells(box)
        floors = Counter(int(grid[y][x]) for y, x in vacated)
        if floors:
            self._floor = floors.most_common(1)[0][0]
        # Only a STEP calibrates the step. A resolved pattern can carry the avatar right
        # across the board, and taking that jump for the stride makes every later plan
        # propose leaps the avatar cannot perform.
        span = max(box[2] - box[0], box[3] - box[1]) + 1
        shift = max(abs(box[0] - self._avatar_box[0]), abs(box[1] - self._avatar_box[1]))
        if 0 < shift <= span:
            self._stride = shift

    def _track(self, grid: np.ndarray, panel: Box) -> Box | None:
        """Re-find the avatar after our own move."""
        return self._avatar(_board_only(grid, panel))

    def _avatar(self, board: list[list[int]]) -> Box | None:
        """The avatar, once the exit is known: its own colours, minus the exit's cells.

        Read as CELLS, never as a component. Walking up to the exit makes the two touch,
        and touching pieces are one component — so an avatar found by matching whole
        components vanishes on the step before arrival, which is the only step that
        matters. Anything else that drifts against it merges the same way.
        """
        if self._avatar_palette is None or self._goal is None:
            return None
        mine = {
            (y, x)
            for y, row in enumerate(board)
            for x, colour in enumerate(row)
            if colour in self._avatar_palette
        } - self._goal
        if not mine:
            return None
        oy, ox = (self._avatar_box or (0, 0, 0, 0))[:2]
        return _cells_box(min(
            _split(mine), key=lambda g: min(abs(y - oy) + abs(x - ox) for y, x in g)
        ))

    # --- phase 2: walk the avatar into the exit ----------------------------

    def _navigate(self, grid: np.ndarray, panel: Box, simple: list[int]) -> Step | None:
        """Shortest lattice path to the exit, or a nudge toward it when none exists."""
        moves = [a for a in (1, 2, 3, 4) if a in simple]
        if len(moves) < 4:
            return None
        if self._floor is None:
            self._floor = _floor_colour(grid, panel)
        if self._floor is None:
            return None
        board = _board_only(grid, panel)
        avatar_box = self._avatar(board)
        if avatar_box is None or len(self._blocked) >= 4:
            # Either the piece we were following is gone, or it has refused every
            # direction — both say the pair was read off a frame that did not describe
            # this board, so read it again rather than pushing a dead avatar around.
            self._goal = None
            self._avatar_palette = None
            self._blocked.clear()
            pair = self._pair(self._objects(grid, board))
            if pair is None:
                return None
            avatar, goal = pair
            self._avatar_palette = avatar["palette"]
            self._goal = goal["cells"]
            avatar_box = avatar["box"]
        self._avatar_box = avatar_box
        goal_box = _cells_box(self._goal)

        stride = self._stride or (avatar_box[2] - avatar_box[0] + 1)
        reach = _reachable(grid, avatar_box, self._goal, self._floor, stride)
        route = min(
            (p for place, p in reach.items() if _footprint(place, avatar_box) & self._goal),
            key=len, default=None,
        )
        if route:
            self._heading = None
            self._aim = None
            return (route[0], None)

        self._aim = _aim(grid, avatar_box, self._goal, self._floor, reach,
                         self._objects(grid, board), _ground(board, avatar_box, self._floor))
        if self._aim is not None:
            place, heading = self._aim
            self._heading = heading
            if place != (avatar_box[0], avatar_box[1]):
                return (reach[place][0], None)
            return None
        return self._nudge(avatar_box, goal_box, moves)

    def _nudge(self, avatar: Box, goal: Box, moves: list[int]) -> Step | None:
        """No route yet — close the gap on the wider axis, and face that way.

        Facing is not incidental: a step the wall refuses still turns the avatar, and a
        pattern the board resolves as a projectile travels the way the avatar faces.
        """
        dy = (goal[0] + goal[2]) - (avatar[0] + avatar[2])
        dx = (goal[1] + goal[3]) - (avatar[1] + avatar[3])
        wants = []
        if dy:
            wants.append((abs(dy), 2 if dy > 0 else 1))
        if dx:
            wants.append((abs(dx), 4 if dx > 0 else 3))
        wants.sort(reverse=True)
        self._heading = next((a for _, a in wants if a in moves), None)
        if avatar in self._seen:
            # Already stood here since the last thing that changed the board, so nudging
            # on can only retrace. Two walls at right angles otherwise bounce the avatar
            # between them until the allowance runs out and the level is LOST — measured.
            return None
        self._seen.add(avatar)
        for _, action in wants:
            if action in moves and action not in self._blocked:
                return (action, None)
        return None

    # --- board reading -----------------------------------------------------

    def _objects(self, grid: np.ndarray, board: list[list[int]]) -> list[dict[str, Any]]:
        """Board pieces: neither wall, nor floor, nor the panel, nor the edge chrome.

        The wall is read off the WHOLE frame — on the blanked board the commonest value is
        the blanking itself, which would leave the maze standing as one enormous "piece".
        """
        skip = set(background(grid)) | {-1}
        if self._floor is not None:
            skip.add(self._floor)
        out: list[dict[str, Any]] = []
        for cells in components(board, skip):
            out.append({
                "cells": set(cells),
                "box": _cells_box(set(cells)),
                "size": len(cells),
                "palette": frozenset(board[y][x] for y, x in cells),
            })
        return out

    def _pair(self, objs: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """The avatar and its exit: two pieces from the SAME palette, one clearly larger.

        A door is painted in the key's colours. The size gap is what separates a real pair
        from a symmetric ornament, whose halves are the same size as each other.
        """
        by_palette: dict[frozenset[int], list[dict[str, Any]]] = {}
        for o in objs:
            by_palette.setdefault(o["palette"], []).append(o)
        best: tuple[int, dict[str, Any], dict[str, Any]] | None = None
        for group in by_palette.values():
            # Exactly two: one avatar, one exit. A palette with three or more members is
            # ornament — a scatter of identical markers reads as a pair otherwise, and a
            # tool that latches onto one steers a marker around for the rest of the level.
            if len(group) != 2:
                continue
            group.sort(key=lambda o: o["size"])
            small, large = group[0], group[-1]
            if large["size"] * 2 < small["size"] * 3:
                continue
            score = small["size"] + large["size"]
            if best is None or score > best[0]:
                best = (score, small, large)
        if best is None:
            return None
        _, small, large = best
        if self._avatar_palette is not None and small["palette"] != self._avatar_palette:
            return None
        return small, large


# --- lattice perception -----------------------------------------------------


def _find_pad(grid: np.ndarray) -> tuple[list[list[Cell]], int, list[list[int]]] | None:
    """The largest complete k x k lattice of equal flat squares, with its colours."""
    wall = background(grid)
    listed = grid.tolist()
    for side in _SIDES:
        blocks = uniform_blocks(listed, side, ignore=wall)
        if len(blocks) < _MIN_K * _MIN_K:
            continue
        lattice = _complete_lattice(sorted(blocks), side)
        if lattice is not None:
            return lattice, side, [[blocks[o] for o in row] for row in lattice]
    return None


def _complete_lattice(origins: list[Cell], side: int) -> list[list[Cell]] | None:
    """Pick k rows and k columns sharing one pitch, with every crossing filled."""
    present = set(origins)
    rows = sorted({y for y, _ in origins})
    cols = sorted({x for _, x in origins})
    pitches = {b - a for a, b in zip(rows, rows[1:])} | {b - a for a, b in zip(cols, cols[1:])}
    for k in range(_MAX_K, _MIN_K - 1, -1):
        for pitch in sorted(p for p in pitches if p >= side):
            for y0 in rows:
                ys = [y0 + i * pitch for i in range(k)]
                if not all(y in rows for y in ys):
                    continue
                for x0 in cols:
                    xs = [x0 + j * pitch for j in range(k)]
                    if not all(x in cols for x in xs):
                        continue
                    if all((y, x) in present for y in ys for x in xs):
                        return [[(y, x) for x in xs] for y in ys]
    return None


def _painted(colours: list[list[int]]) -> list[Cell]:
    """Cells carrying the instruction: a strict minority against one neutral majority."""
    counts = Counter(c for row in colours for c in row)
    if len(counts) < 2:
        return []
    neutral, hits = counts.most_common(1)[0]
    if hits * 2 <= sum(counts.values()):
        return []
    return [
        (r, c)
        for r in range(len(colours))
        for c in range(len(colours[r]))
        if colours[r][c] != neutral
    ]


# --- board geometry ---------------------------------------------------------


def _panel_box(grid: np.ndarray, origins: list[list[Cell]]) -> Box:
    """Bounding box of the component the lattice is mounted in."""
    seed = origins[0][0]
    for cells in components(grid, background(grid)):
        if seed in cells:
            ys = [y for y, _ in cells]
            xs = [x for _, x in cells]
            return (min(ys), min(xs), max(ys), max(xs))
    return (origins[0][0][0], origins[0][0][1], origins[-1][-1][0], origins[-1][-1][1])


def _board_only(grid: np.ndarray, panel: Box) -> list[list[int]]:
    """The frame with the instruction panel and the edge chrome blanked to -1."""
    chrome = edge_band(grid.shape)
    h, w = grid.shape
    return [
        [
            -1 if (chrome[y][x] or (panel[0] <= y <= panel[2] and panel[1] <= x <= panel[3]))
            else int(grid[y][x])
            for x in range(w)
        ]
        for y in range(h)
    ]


def _cells_box(cells: set[Cell]) -> Box:
    ys = [y for y, _ in cells]
    xs = [x for _, x in cells]
    return (min(ys), min(xs), max(ys), max(xs))


def _split(cells: set[Cell]) -> list[set[Cell]]:
    """4-connected groups of a cell set."""
    todo = set(cells)
    out: list[set[Cell]] = []
    while todo:
        stack = [todo.pop()]
        group = set(stack)
        while stack:
            y, x = stack.pop()
            for n in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if n in todo:
                    todo.discard(n)
                    group.add(n)
                    stack.append(n)
        out.append(group)
    return out


def _box_cells(box: Box) -> set[Cell]:
    y0, x0, y1, x1 = box
    return {(y, x) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)}


def _floor_colour(grid: np.ndarray, panel: Box) -> int | None:
    """Walkable ground: the commonest board colour once the wall is set aside.

    The wall is the commonest colour of the WHOLE frame — a maze is mostly maze — so the
    ground is what is left over, and it is still far commoner than any piece standing on it.
    """
    wall = background(grid)
    counts: Counter[int] = Counter()
    for row in _board_only(grid, panel):
        for colour in row:
            if colour >= 0 and colour not in wall:
                counts[colour] += 1
    return counts.most_common(1)[0][0] if counts else None


def _footprint(place: Cell, avatar: Box) -> set[Cell]:
    """The cells the avatar would cover standing at ``place``."""
    y, x = place
    return _box_cells((y, x, y + avatar[2] - avatar[0], x + avatar[3] - avatar[1]))


def _halo(cells: set[Cell]) -> set[Cell]:
    """The 4-neighbours just outside a cell set."""
    out: set[Cell] = set()
    for y, x in cells:
        out |= {(y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)}
    return out - cells


def _ground(board: list[list[int]], avatar: Box, floor: int) -> set[Cell]:
    """The floor region the avatar actually stands in, flood-filled from under it.

    Ground the avatar cannot walk on is not ground for our purposes: a framed panel is
    full of the same colour, and treating that as walkable makes furniture look like part
    of the board.
    """
    h, w = len(board), len(board[0])
    seed = [c for c in _halo(_box_cells(avatar)) if 0 <= c[0] < h and 0 <= c[1] < w
            and board[c[0]][c[1]] == floor]
    seen = set(seed)
    stack = list(seed)
    while stack:
        y, x = stack.pop()
        for n in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if n in seen or not (0 <= n[0] < h and 0 <= n[1] < w):
                continue
            if board[n[0]][n[1]] == floor:
                seen.add(n)
                stack.append(n)
    return seen


def _aim(
    grid: np.ndarray,
    avatar: Box,
    goal: set[Cell],
    floor: int,
    reach: dict[Cell, list[int]],
    objs: list[dict[str, Any]],
    ground: set[Cell],
) -> tuple[Cell, int] | None:
    """Where to stand and which way to face so a directional resolution hits something.

    Which something is the whole question, and it is answered by REACH, not by proximity.
    A piece the avatar can walk up against needs no projectile — it is already within
    reach and shooting it spends the pattern for nothing. The piece worth a shot is the
    one that borders the same ground yet no step can ever reach: that is what a ranged
    resolution is FOR, and on these boards it is the switch that clears the way, standing
    in an alcove behind a gap too narrow to enter.
    """
    if not reach:
        return None
    # Where the avatar can STAND is not the same as where the ground goes: the avatar is
    # several cells wide, so a gap the ground runs through can still admit no placement.
    # That difference is exactly the "out of reach" the shot is for.
    covered: set[Cell] = set()
    for place in reach:
        covered |= _footprint(place, avatar)
    marks = [
        o["cells"] for o in objs
        if not (o["cells"] & goal)
        and _halo(o["cells"]) & ground
        and not (_halo(o["cells"]) & covered)
    ]
    if not marks:
        return None

    h, w = grid.shape
    ah = avatar[2] - avatar[0] + 1
    aw = avatar[3] - avatar[1] + 1
    rays = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
    best: tuple[int, Cell, int] | None = None
    for place, path in reach.items():
        if best is not None and len(path) >= best[0]:
            continue
        cy, cx = place[0] + ah // 2, place[1] + aw // 2
        edges = {
            1: (place[0] - 1, cx), 2: (place[0] + ah, cx),
            3: (cy, place[1] - 1), 4: (cy, place[1] + aw),
        }
        for action, (dy, dx) in rays.items():
            y, x = edges[action]
            while 0 <= y < h and 0 <= x < w:
                if any((y, x) in m for m in marks):
                    best = (len(path), place, action)
                    break
                if int(grid[y][x]) != floor:
                    break
                y, x = y + dy, x + dx
    return (best[1], best[2]) if best else None


def _reachable(
    grid: np.ndarray, avatar: Box, goal: set[Cell], floor: int, stride: int
) -> dict[Cell, list[int]]:
    """Every placement the avatar can step to, with the shortest route to each."""
    h, w = grid.shape
    ah = avatar[2] - avatar[0] + 1
    aw = avatar[3] - avatar[1] + 1
    own = _box_cells(avatar)

    def free(y: int, x: int) -> bool:
        if y < 0 or x < 0 or y + ah > h or x + aw > w:
            return False
        for cy in range(y, y + ah):
            for cx in range(x, x + aw):
                if (cy, cx) in goal or (cy, cx) in own:
                    continue
                if int(grid[cy][cx]) != floor:
                    return False
        return True

    start = (avatar[0], avatar[1])
    out: dict[Cell, list[int]] = {start: []}
    queue: deque[Cell] = deque([start])
    deltas = ((1, (0, -stride)), (2, (0, stride)), (3, (-stride, 0)), (4, (stride, 0)))
    while queue:
        y, x = queue.popleft()
        path = out[(y, x)]
        if len(path) >= _MAX_PATH:
            continue
        for action, (dx, dy) in deltas:
            step = (y + dy, x + dx)
            if step in out or not free(*step):
                continue
            out[step] = path + [action]
            queue.append(step)
    return out
