"""Maze tool — walk a body to a marked exit, and recruit a replay clone when a plate gates it.

⛔ Why a model instead of a search. Measured 2026-08-27: the searching generic path opens hundreds
of states on these boards and clears nothing, because the games END on their own timer. A walk
planned on a map read from the frame costs the length of the path and nothing else.

The board grammar this tool recovers, all of it from pixels:

  * The EXIT is a hollow ring with a single loose cell of the same colour at its centre. Nothing
    else on these boards is drawn that way, which is what makes the tool safe to bid on.
  * The BODY is the other region of the exit's colour whose own centre cell shows the floor
    through it. That hole is not decoration: the engine tests ONE point, the body's centre, so
    the hole marks exactly the cell that has to be walkable, and the walk is planned on a lattice
    of centres spaced one stride apart.
  * WALLS are the background colour. Everything else is floor, or furniture standing on floor.
  * A DOOR is furniture that refuses the body. It cannot be told from a marker by looking, so it
    is learned by being refused — and remembered AS A COLOUR AT A CELL, because a door that slid
    aside slides back and must be believed again without paying for a second refusal.

⛔ THE MEASURED FACT THAT SHAPES EVERYTHING ELSE: the observation LAGS TWO PROPOSAL CALLS. The
frame handed to call k is the state before the action issued at call k-1. A tool that reads its
own position off that frame walks two steps behind itself: it re-issues moves it has already
made, then attributes a refusal to whichever cell it happened to believe it was standing on. The
first version of this tool did exactly that and learned four different controls all meaning
"down", then decided a wall existed in the middle of an empty corridor. So the position the plan
is drawn from is a BELIEF — the last observed centre carried forward through the actions still in
flight — and a refusal INVALIDATES the flight, because everything planned behind it was planned
from a place the body never reached.

⛔ And the trap that shapes the control loop: a PLATE is released the moment the body steps off
it, so walking to the plate and then to the door is not a solution and never can be. The board
hands out a rewind that returns the body to its start and leaves behind a CLONE replaying every
move just made. So a door seen to open is recorded as GATED ON the cell the body was standing on,
and stays shut in the plan until either the body is back on that cell or the rewind has been
spent — after which the clone holds it and every move the body makes advances the clone one step.
The rewind's own effect also lands a beat late, so the teleport home is blamed on the earlier
unresolved control, never on the one that merely followed it.

Frame-only: the body, the exit, the stride, the walkable map and the meaning of every control are
derived. No identifiers, no titles, no coordinates, no sizes.
"""

from __future__ import annotations

from collections import Counter, deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, frame_2d, has_frame, levels_completed
from admorphiq.tools.segment import edge_band

__all__ = ["MazeRunTool", "blobs_of"]

Cell = tuple[int, int]
_SIMPLE = (1, 2, 3, 4, 5, 7)
# How far ahead of the frame the body actually is (measured; see the module note).
_LAG = 2
# A level is abandoned rather than spun on; these boards lose on their own timer anyway.
_MAX_STEPS = 300


def blobs_of(g: Any, colour: int) -> list[list[Cell]]:
    """4-connected regions of one colour."""
    grid = np.asarray(g)
    out: list[list[Cell]] = []
    seen: set[Cell] = set()
    ys, xs = np.where(grid == colour)
    cells = set(zip(ys.tolist(), xs.tolist()))
    for cell in sorted(cells):
        if cell in seen:
            continue
        stack = [cell]
        seen.add(cell)
        group: list[Cell] = []
        while stack:
            y, x = stack.pop()
            group.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (y + dy, x + dx)
                if nxt in cells and nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        out.append(group)
    return out


def _bbox(group: list[Cell]) -> tuple[int, int, int, int]:
    ys = [c[0] for c in group]
    xs = [c[1] for c in group]
    return min(ys), min(xs), max(ys), max(xs)


def _centre(group: list[Cell]) -> Cell:
    y0, x0, y1, x1 = _bbox(group)
    return (y0 + y1) // 2, (x0 + x1) // 2


class _Scene:
    """What one frame says: where the body is, where the exit is, what counts as floor."""

    __slots__ = ("body", "exit", "floor", "background", "reach")

    def __init__(self, body: Cell, exit_: Cell, floor: int, background: int, reach: int) -> None:
        self.body = body
        self.exit = exit_
        self.floor = floor
        self.background = background
        # How far the body's own drawing extends from its centre — the radius within which a
        # changed cell is the body redrawing itself, not a door answering it.
        self.reach = reach


class MazeRunTool:
    """Walk the body to the marked exit, spending a replay clone on any plate that gates it."""

    name = "maze"

    def __init__(self) -> None:
        # The controls never change meaning, so what they mean outlives a level.
        self._delta: dict[int, Cell] = {}
        self._rewind: int | None = None
        self._level: tuple[int, Cell] | None = None
        self.reset()

    def reset(self) -> None:
        """A new level redraws the board; only the meaning of the controls survives."""
        self._wall: dict[Cell, set[int]] = {}
        self._gates: dict[Cell, Cell] = {}
        self._seen: set[Cell] = set()
        self._tried: set[tuple[int, Cell | None]] = set()
        self._flight: deque[list[Any]] = deque()
        self._unresolved: int | None = None
        self._belief: Cell | None = None
        self._last: Cell | None = None
        self._shut: dict[Cell, int] = {}
        self._home: Cell | None = None
        self._legal: list[int] = []
        self._deployed: set[Cell] = set()
        self._latched: set[Cell] = set()
        self._flip: dict[Cell, bool] = {}
        self._plan: list[Cell] = []
        self._awaiting: Cell | None = None
        self._before: np.ndarray | None = None
        self._palette: set[int] = set()
        self._budget = 0

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Learning runs off the body's measured displacement, not off a changed-flag."""

    # -- reading the board ---------------------------------------------------

    def _scene(self, g: Any) -> _Scene | None:
        """Recover body, exit and floor colour, or nothing when the grammar is absent."""
        grid = np.asarray(g)
        if grid.ndim != 2 or grid.shape[0] != grid.shape[1] or grid.shape[0] < 16:
            return None
        band = edge_band(grid.shape)
        counts = Counter(int(v) for v in grid.ravel().tolist())
        for colour in counts:
            groups = [q for q in blobs_of(grid, colour) if not any(band[y][x] for y, x in q)]
            if len(groups) < 3:
                continue
            dots = {q[0] for q in groups if len(q) == 1}
            for ring in groups:
                if len(ring) <= 8 or not self._hollow(ring):
                    continue
                middle = _centre(ring)
                if middle not in dots:
                    continue
                bodies = [
                    q for q in groups
                    if q is not ring and len(q) > 4 and int(grid[_centre(q)]) != colour
                ]
                if not bodies:
                    continue
                blob = max(bodies, key=len)
                body = _centre(blob)
                y0, x0, y1, x1 = _bbox(blob)
                reach = max(y1 - y0, x1 - x0) // 2 + 1
                # ⛔ The floor is what shows through the body, and the WALL is whatever is
                # commonest after that. Taking the commonest colour outright inverts the two
                # the moment a board's floor is larger than its surround, and then every wall
                # is a road and every road a wall.
                floor = int(grid[body])
                wall = next(c for c, _ in counts.most_common() if c != floor)
                return _Scene(body, middle, floor, wall, reach)
        return None

    @staticmethod
    def _hollow(group: list[Cell]) -> bool:
        """A ring encloses cells it does not own — an exit marker, never a solid piece."""
        y0, x0, y1, x1 = _bbox(group)
        h, w = y1 - y0 + 1, x1 - x0 + 1
        return h >= 5 and w >= 5 and len(group) < h * w

    def _stride(self) -> int:
        for dy, dx in self._delta.values():
            if dy or dx:
                return abs(dy) + abs(dx)
        return 0

    def _open(self, grid: np.ndarray, scene: _Scene, cell: Cell, assume: bool = False) -> bool:
        """May the body's centre stand here? Background is wall; a refused colour is a door.

        A door known to be gated on a plate stays shut in the plan unless the body is on that
        plate — until the rewind is spent, after which a clone holds it and the frame is true.
        """
        y, x = cell
        n = grid.shape[0]
        if not (0 <= y < n and 0 <= x < n):
            return False
        colour = int(grid[y, x])
        if colour == scene.background:
            return False
        gate = self._gates.get(cell)
        if assume and (gate is not None or self._thick(grid, cell, scene)):
            return True
        if gate in self._latched:
            return self._flip.get(cell, False)
        if gate is not None and scene.body == gate and gate not in self._deployed:
            # ⛔ The body is what is holding this door open, so the frame showing it open is
            # not a road — it is the reason walking away closes it. Only a door held by
            # something ELSE, or one that latched, may be planned through.
            return False
        return colour not in self._wall.get(cell, ())

    def _lattice(self, grid: np.ndarray, scene: _Scene, here: Cell, assume: bool = False) -> set[Cell]:
        """Every centre the body can occupy, one stride at a time from where it believes it is."""
        step = self._stride()
        n = grid.shape[0]
        cells = {here}
        y = here[0] % step
        while y < n:
            x = here[1] % step
            while x < n:
                if self._open(grid, scene, (y, x), assume):
                    cells.add((y, x))
                x += step
            y += step
        return cells

    # -- Tool protocol -------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Bid only when the board actually shows a ring-marked exit and a body to steer."""
        if not has_frame(obs):
            return 0.0
        simple, action6 = availability(obs)
        if action6 or len({1, 2, 3, 4} & set(simple)) < 4:
            return 0.0
        if self._scene(frame_2d(obs)) is None:
            return 0.0
        return 0.7

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        grid = np.asarray(frame_2d(obs))
        scene = self._scene(grid)
        if scene is None:
            return []
        # ⛔ The level counter is not the board's identity here. It arrives on a frame that may
        # still be showing the old level, so a reset keyed on it leaves the redraw to be read as
        # a change — measured as SIXTY doors opening at once, and a clone spent walking onto one
        # of the phantom plates. The exit moves exactly when the board does; key on that.
        board = (levels_completed(obs), scene.exit)
        if board != self._level:
            self._level = board
            self.reset()
        simple, _ = availability(obs)
        self._legal = [a for a in _SIMPLE if a in simple]
        if not self._legal:
            return []
        if self._home is None:
            self._home = scene.body
        self._budget += 1
        if self._budget > _MAX_STEPS:
            return []

        self._settle(grid, scene)
        here = self._project(scene)
        if not self._open(grid, scene, here):
            here = scene.body
            self._belief = here
        self._seen.add(here)

        if not self._stride():
            probe = self._untried(None)
            return [] if probe is None else self._issue(probe, None, here)

        free = self._lattice(grid, scene, here)

        # ⛔ Follow the plan already made. Re-deriving the route on every single action looks
        # harmless and is not: the body's position is a belief two frames behind, and a route
        # that crosses a latching plate reads differently depending on which side of it the
        # belief currently sits — so the tool proposed up, then down, then up, forever, two
        # cells from the plate. A plan is dropped when the world contradicts it (a refusal, a
        # new door, a rewind), not because the frame moved on.
        if self._plan and self._plan[0] in free and self._gap(self._plan[0], here) == self._stride():
            target = self._plan.pop(0)
            plan = self._walk(target, here)
            if plan:
                return plan
        self._plan = []

        route = self._route(here, {scene.exit}, free)
        if route:
            return self._commit(route, here)

        # ⛔ A plate is released the instant the body steps off, so the exit route above is
        # computed with every undeployed door SHUT even when the frame shows it open. Standing
        # on the plate is what opened it, and walking away is what closes it again. The move
        # that is worth making here is the rewind: it puts a clone on the plate for good.
        plates = self._wanted(grid, scene) - self._deployed - self._latched
        # ⛔ Spend on contact. A plate that LATCHES needs no clone and is already excluded —
        # the evidence arrives free, because the body crosses these plates on its way past and
        # the door is then seen open with nobody on it. Going to LOOK for that evidence
        # instead cost eight moves, and a clone replays every move made since the last rewind,
        # so those eight came back as eight more moves of waiting. Stepping off the plate to
        # test it is worse still: the body left before the rewind fired, and the clone then
        # replayed a path that ended one cell short of the plate it was spent to hold.
        if here in plates:
            spend = self._rewind if self._rewind is not None else self._untried(None)
            if spend is not None:
                self._awaiting = here
                if self._rewind is not None:
                    self._deployed.add(here)
                return self._issue(spend, None, here)

        route = self._route(here, self._studs(grid, scene, free), free)
        if route:
            return self._commit(route, here)

        far = self._distances(grid, scene, scene.exit)
        coming = [d for d, p in self._gates.items() if p in self._deployed and d not in free]
        ahead = plates or coming
        aim = min(ahead, key=lambda c: far.get(c, len(far) + 1)) if ahead else scene.exit

        # ⛔ A latching plate costs no clone, but it still has to be PRESSED — and the rewind
        # puts every door back the way the level started, latches included. Only go and press
        # one whose door is ON THE ROAD being travelled, though: pressing every shut latch just
        # because it is shut sent the body back and forth across the same plate eight times,
        # and a clone replays every one of those moves.
        wanted_road = set(self._route(here, {aim}, self._lattice(grid, scene, here, assume=True)))
        relight = {
            plate for door, plate in self._gates.items()
            if plate in self._latched and not self._flip.get(door, False) and door in wanted_road
        }
        unseen = set() if self._gates else free - self._seen
        for targets in (plates, relight, unseen):
            route = self._route(here, targets, free)
            if route:
                return self._commit(route, here)

        # ⛔ Mark time TOWARD the next plate, not toward the exit. Every move made while
        # waiting is also a move appended to the path the NEXT clone will replay, so idling in
        # place buys the wait twice: measured at twelve wasted moves that then became twelve
        # extra moves of waiting after the following rewind, and the level died on its timer a
        # few actions short. Walking a road that has to be walked anyway costs nothing.
        # A door whose clone is on its way is the threshold to wait AT, not away from: the walk
        # there is the same walk the route needs once it opens.
        route = self._toward(here, self._distances(grid, scene, aim), free)
        if route:
            plan = self._walk(route[0], here)
            if plan:
                return plan
        return self._drift(here, free)

    def _commit(self, route: list[Cell], here: Cell) -> list[Step]:
        """Take the first step of a route and keep the rest as the plan to follow."""
        self._plan = route[1:]
        plan = self._walk(route[0], here)
        if not plan:
            self._plan = []
        return plan

    def _drift(self, here: Cell, free: set[Cell]) -> list[Step]:
        """Nothing plannable is reachable: take any KNOWN direction that lands on the board.

        Standing still is not an option the board offers, and a move is never wasted while a
        clone is replaying — it is the clock the clone runs on. Known directions only, so this
        can never reach for the rewind by accident.
        """
        plates = set(self._gates.values())
        for wanted in (True, False):
            for action in sorted(self._delta):
                shift = self._delta[action]
                nxt = (here[0] + shift[0], here[1] + shift[1])
                if nxt in free and ((nxt not in plates) is wanted):
                    return self._issue(action, nxt, here)
        return []

    # -- deciding where to go ------------------------------------------------

    def _wanted(self, grid: np.ndarray, scene: _Scene) -> set[Cell]:
        """Plates whose door the exit actually depends on, directly or through another door.

        ⛔ A clone is not spendable on whatever plate the body happens to cross. Measured: a
        level with two plates that gate nothing on the way out took BOTH clones and then had
        none left for the one that mattered. Chase the dependency instead: route home to the
        exit with every door imagined open, take the doors the route uses, then route home to
        THOSE doors' plates, and repeat — a door that has to be opened to reach another plate
        is just as needed as one on the final path.
        """
        if not self._gates or self._home is None:
            return set()
        free = self._lattice(grid, scene, self._home, assume=True)
        targets = [scene.exit, *self._studs(grid, scene, free)]
        wanted: set[Cell] = set()
        seen: set[Cell] = set()
        while targets:
            goal = targets.pop()
            if goal in seen:
                continue
            seen.add(goal)
            for cell in self._route(self._home, {goal}, free):
                plate = self._gates.get(cell)
                if plate is not None and plate not in wanted:
                    wanted.add(plate)
                    targets.append(plate)
        return wanted

    @staticmethod
    def _thick(grid: np.ndarray, cell: Cell, scene: _Scene) -> bool:
        """Is this cell a SOLID patch of furniture rather than a one-pixel run of wire?

        The wire joining a plate to its door is drawn in the plate's own colour, so thickness is
        the only thing separating the two ends from the run between them. Both ends are thick:
        one is the plate, the other is the door.
        """
        y, x = cell
        if y < 1 or x < 1 or y + 1 >= grid.shape[0] or x + 1 >= grid.shape[1]:
            return False
        colour = int(grid[y, x])
        if colour in (scene.floor, scene.background):
            return False
        patch = grid[y - 1:y + 2, x - 1:x + 2]
        return int(patch.min()) == colour == int(patch.max())

    def _studs(self, grid: np.ndarray, scene: _Scene, free: set[Cell]) -> set[Cell]:
        """Unvisited cells sitting on a SOLID patch of furniture — the shape a plate has.

        The wire that joins a plate to the door it drives is drawn in the same colour and is one
        pixel wide, so thickness is what separates the two ends from the run between them. Aiming
        exploration at these instead of at every non-floor cell is the difference between finding
        the plate and touring the wire.
        """
        return {c for c in free if c not in self._seen and self._thick(grid, c, scene)}

    def _steps(self) -> tuple[Cell, ...]:
        q = self._stride()
        return ((q, 0), (-q, 0), (0, q), (0, -q))

    def _route(self, start: Cell, targets: set[Cell], free: set[Cell]) -> list[Cell]:
        """Shortest walk from the body to any target, carrying the latch states with it.

        ⛔ A latching plate is not scenery to be walked over. EVERY arrival on it flips its
        door, so a route that crosses one on the way out shuts the door it is relying on.
        Measured: the tool found a perfectly good twenty-two step route to the exit, took two
        steps of it across the plate, watched the door it needed close, turned round, and did
        that for the rest of the level. So the search state is (cell, latch bits), not cell —
        one bit per latching door, flipped on entry to its plate.
        """
        if not targets:
            return []
        doors = sorted(d for d, p in self._gates.items() if p in self._latched)
        plate_of = {self._gates[d]: i for i, d in enumerate(doors)}
        shut = {d: i for i, d in enumerate(doors)}
        start_bits = tuple(self._flip.get(d, False) for d in doors)

        def step_bits(cell: Cell, bits: tuple[bool, ...]) -> tuple[bool, ...]:
            i = plate_of.get(cell)
            if i is None:
                return bits
            flipped = list(bits)
            flipped[i] = not flipped[i]
            return tuple(flipped)

        state = (start, start_bits)
        prev: dict[tuple[Cell, tuple[bool, ...]], tuple[Cell, tuple[bool, ...]] | None] = {state: None}
        queue: deque[tuple[Cell, tuple[bool, ...]]] = deque([state])
        while queue:
            here, bits = queue.popleft()
            if here in targets and (here, bits) != state:
                return self._unwind_states(prev, (here, bits))
            for dy, dx in self._steps():
                nxt = (here[0] + dy, here[1] + dx)
                i = shut.get(nxt)
                passable = bits[i] if i is not None else nxt in free
                if not passable:
                    continue
                nxt_state = (nxt, step_bits(nxt, bits))
                if nxt_state not in prev:
                    prev[nxt_state] = (here, bits)
                    queue.append(nxt_state)
        return []

    @staticmethod
    def _unwind_states(prev: dict[Any, Any], end: Any) -> list[Cell]:
        path = [end]
        while prev[path[-1]] is not None:
            path.append(prev[path[-1]])
        return [cell for cell, _bits in reversed(path)][1:]

    def _distances(self, grid: np.ndarray, scene: _Scene, source: Cell) -> dict[Cell, int]:
        """Corridor distance from a cell, with every door imagined open.

        ⛔ Straight-line distance is the wrong idea of "close" on a board made of corridors.
        Measured: the cell two steps from the exit as the crow flies was in a dead-end pocket
        whose only way out ran the length of the board, while the cell that was genuinely one
        door from the exit scored three times worse — so the body marked time in the pocket,
        on top of a latching plate, toggling the door it was waiting for.
        """
        free = self._lattice(grid, scene, source, assume=True)
        dist = {source: 0}
        queue: deque[Cell] = deque([source])
        while queue:
            here = queue.popleft()
            for dy, dx in self._steps():
                nxt = (here[0] + dy, here[1] + dx)
                if nxt in free and nxt not in dist:
                    dist[nxt] = dist[here] + 1
                    queue.append(nxt)
        return dist

    def _toward(self, start: Cell, dist: dict[Cell, int], free: set[Cell]) -> list[Cell]:
        """Get as close to the exit as the board allows; if already there, mark time.

        Marking time is not idling. Every move the body makes advances the clone one step along
        the path it is replaying, and the clone is what holds the plate down. But it must not
        walk over a latching plate to do it — that toggles the door the waiting is FOR.
        """
        far = len(dist) + 1
        plates = set(self._gates.values())
        # ⛔ Marking time must not CROSS a latching plate, not merely avoid parking on one.
        # Every crossing flips the door being waited for, and the tool spent twenty moves
        # walking to the far side of the board, finding the door shut because it had shut it
        # on the way past, and walking back to flip it again.
        latching = {p for p in plates if p in self._latched}
        if start not in latching:
            free = free - latching
        prev: dict[Cell, Cell | None] = {start: None}
        queue: deque[Cell] = deque([start])
        best = start
        while queue:
            here = queue.popleft()
            if here not in plates and dist.get(here, far) < dist.get(best, far):
                best = here
            for dy, dx in self._steps():
                nxt = (here[0] + dy, here[1] + dx)
                if nxt in free and nxt not in prev:
                    prev[nxt] = here
                    queue.append(nxt)
        if best != start:
            return self._unwind(prev, best)
        for dy, dx in self._steps():
            nxt = (start[0] + dy, start[1] + dx)
            if nxt in free and nxt not in plates:
                return [nxt]
        return []

    @staticmethod
    def _unwind(prev: dict[Cell, Cell | None], end: Cell) -> list[Cell]:
        path = [end]
        while prev[path[-1]] is not None:
            path.append(prev[path[-1]])  # type: ignore[arg-type]
        return list(reversed(path))[1:]

    @staticmethod
    def _gap(a: Cell, b: Cell) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    # -- issuing -------------------------------------------------------------

    def _untried(self, target: Cell | None) -> int | None:
        """The next control whose meaning is unknown, ASCENDING so the odd one is probed last.

        ⛔ Order is load-bearing, not tidiness. The control that is not a direction rewinds the
        level and spends one of a small pool of clones, so the directions are reached first and
        it is left until nothing else is untried.
        """
        for action in sorted(self._legal):
            if action in self._delta or action == self._rewind:
                continue
            if (action, target) in self._tried:
                continue
            return action
        return None

    def _walk(self, target: Cell, here: Cell) -> list[Step]:
        """Take one step of the route, probing an unknown control when none is known for it."""
        want = (target[0] - here[0], target[1] - here[1])
        for action in sorted(self._delta):
            if self._delta[action] == want:
                return self._issue(action, target, here)
        probe = self._untried(target)
        return [] if probe is None else self._issue(probe, target, here)

    def _issue(self, action: int, target: Cell | None, here: Cell) -> list[Step]:
        self._flight.append([action, target, True, here])
        return [(action, None)]

    def _project(self, scene: _Scene) -> Cell:
        """Where the body actually is: the last frame carried through the actions still in flight.

        ⛔ Carried by DISPLACEMENT, never by the target the plan wrote down. An absolute target
        overrides the observation, so one wrong reading is never corrected and every later target
        is written from the wrong place — measured as a body that believed itself a full stride
        ahead for the rest of the level and recorded a wall in an empty corridor.
        """
        here = scene.body
        for action, _target, live, _origin in self._flight:
            shift = self._delta.get(action)
            if live and shift is not None:
                here = (here[0] + shift[0], here[1] + shift[1])
        self._belief = here
        return here

    # -- learning ------------------------------------------------------------

    def _settle(self, grid: np.ndarray, scene: _Scene) -> None:
        """Resolve the action whose effect this frame finally shows, and read the doors."""
        # A door that changed colour did so because the body is standing on its plate NOW.
        for cell, colour in list(self._shut.items()):
            if int(grid[cell]) != colour:
                self._gates[cell] = scene.body
                self._shut.pop(cell, None)
        self._sense_gates(grid, scene)

        held = self._aliens(grid, grid, scene.reach)
        for door, plate in self._gates.items():
            if scene.body == plate:
                continue
            if held[plate] or int(grid[door]) in self._wall.get(door, ()):
                continue
            # ⛔ Open while NOBODY is standing on its plate: this door LATCHED when it was
            # pressed. Measured on a level with three plates and two clones — spending one on
            # the latching plate leaves none for the plate that has to be held, and the
            # evidence that it latched arrives free, on the way past.
            #
            # ⛔ "Nobody" has to include the CLONE. A clone parked on a hold-plate holds the
            # door open with the body far away, which is pixel-identical to a latch — and
            # reading it as one retires the very plate the clone was spent on.
            self._latched.add(plate)
            self._flip[door] = True

        previous, self._last = self._last, scene.body
        for door, plate in self._gates.items():
            if plate in self._latched and scene.body == plate and previous != plate:
                # ⛔ A latch is a BIT THIS TOOL OWNS: every arrival on the plate flips it, and
                # nothing else touches it. Re-reading it off the frame instead cost the whole
                # of one level — marking time next to the plate walked on and off it, toggling
                # the door shut on exactly the alternate frames the route needed it open.
                self._flip[door] = not self._flip.get(door, False)

        if len(self._flight) < _LAG or previous is None:
            return
        action, target, live, origin = self._flight.popleft()
        shift = (scene.body[0] - previous[0], scene.body[1] - previous[1])
        stride = self._stride()

        if shift == (0, 0):
            self._tried.add((action, target))
            # ⛔ A refusal only names a wall when the body was standing where the plan thought
            # it was. Otherwise the refusal belongs to some other cell entirely, and recording
            # it here paints walls across open floor — measured, three of them in one level.
            if target is not None and live and origin == previous and action in self._delta:
                self._wall.setdefault(target, set()).add(int(grid[target]))
                self._shut[target] = int(grid[target])
                # ⛔ Everything still in flight was planned from a cell the body never reached,
                # so it is voided in BOTH directions: it may not move the belief, and it may not
                # name a wall. Voiding only the wall left the belief a stride ahead, and the next
                # refusal was then recorded against an empty corridor two cells further on.
                self._plan = []
                for entry in self._flight:
                    entry[1], entry[2] = None, False
            elif action not in self._delta:
                self._unresolved = action
        elif not self._is_step(shift, stride) and scene.body != self._home:
            # ⛔ A jump that does not end at the start is the BOARD moving the body, not a
            # control doing it — one of these levels swaps the bodies standing on a linked pair
            # of pads. Blaming a control for it retires a working direction and strands the
            # tool. Accept the new position and drop the flight planned from the old one.
            self._flight.clear()
        elif not self._is_step(shift, stride):
            # Landing back on the start is the rewind, arriving a beat late: blame the control
            # that did nothing last turn, never the one that merely followed it.
            culprit = self._unresolved if self._unresolved is not None else action
            self._rewind = culprit
            self._delta.pop(culprit, None)
            self._unresolved = None
            self._flight.clear()
            self._plan = []
            self._flip.clear()  # the rewind puts the level back as it started, latches included
            if self._awaiting is not None:
                self._deployed.add(self._awaiting)
                self._awaiting = None
        elif scene.body == self._home and action not in self._delta:
            # ⛔ Not a step. The rewind puts the body back on its start, and from ONE stride away
            # that is pixel-identical to a move. An unknown control is never given a meaning by a
            # displacement that ends at home; it is probed again somewhere the two differ.
            self._tried.add((action, target))
            self._unresolved = action
        elif self._delta.get(action, shift) == shift:
            self._delta[action] = shift
            if action == self._unresolved:
                self._unresolved = None

    def _sense_gates(self, grid: np.ndarray, scene: _Scene) -> None:
        """A cell that cleared to floor while the body stood elsewhere is a door, and the cell
        the body is standing on is its plate.

        ⛔ Waiting to be REFUSED by a door before its plate can be recognised costs a lap of the
        whole board per plate — measured at thirty moves on a level whose whole solution is
        thirty-five. Seeing the door move is free, and it is the same evidence a person uses.

        Two exclusions keep it honest. Changes within reach of the body are the body itself
        redrawing over furniture, not a door. And any colour the level did not open with belongs
        to a clone that was not there before, so its comings and goings are never a door.
        """
        before, self._before = self._before, grid.copy()
        if not self._palette:
            self._palette = {int(v) for v in grid.ravel().tolist()}
        stride = self._stride()
        if before is None or before.shape != grid.shape or self._last is None or not stride:
            # ⛔ Not before the stride is known. Without it there is no lattice to test against
            # and no scale for "near the body", so the cells the body VACATES read as doors —
            # measured as sixteen phantom plates on the first move, one of which the tool then
            # walked onto and spent its only clone.
            return
        band = edge_band(grid.shape) | self._aliens(before, grid, scene.reach + 1)
        for y, x in zip(*np.where((before != grid) & ~band)):
            cell = (int(y), int(x))
            if int(grid[cell]) != scene.floor or int(before[cell]) not in self._palette:
                continue
            if (cell[0] - scene.body[0]) % stride or (cell[1] - scene.body[1]) % stride:
                continue
            if max(abs(cell[0] - scene.body[0]), abs(cell[1] - scene.body[1])) <= scene.reach \
                    or max(abs(cell[0] - self._last[0]), abs(cell[1] - self._last[1])) <= scene.reach:
                continue
            if cell not in self._gates:
                self._plan = []
                self._gates[cell] = scene.body
                self._wall.setdefault(cell, set()).add(int(before[cell]))

    def _aliens(self, before: np.ndarray, grid: np.ndarray, reach: int) -> np.ndarray:
        """Where a clone is, grown by its own size — evidence gathered there means nothing.

        ⛔ Measured: the clone crossing a plate reads exactly like a door opening, because the
        plate cell turns floor-coloured under the clone's own transparent middle. The tool
        recorded the cell it happened to be standing on as a second plate and spent its last
        clone walking onto it. A clone is recognisable without being understood: it is drawn in
        a colour the level did not start with.
        """
        here = np.zeros(grid.shape, dtype=bool)
        for frame in (before, grid):
            for colour in np.unique(frame):
                if int(colour) not in self._palette:
                    here |= frame == colour
        grown = here.copy()
        for dy in range(-reach, reach + 1):
            for dx in range(-reach, reach + 1):
                grown |= np.roll(np.roll(here, dy, axis=0), dx, axis=1)
        return grown

    @staticmethod
    def _is_step(shift: Cell, stride: int) -> bool:
        """One stride along one axis — the only displacement a direction may produce."""
        if shift[0] and shift[1]:
            return False
        size = abs(shift[0]) + abs(shift[1])
        return size == stride if stride else size > 0
