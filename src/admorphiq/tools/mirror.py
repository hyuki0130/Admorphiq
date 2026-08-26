"""Mirror tool — two coupled actors under shared controls, brought together.

The mechanic, recovered from frames: a board is painted in TWO TINTS, one per half, and carries a
small number of identical actors. The simple actions move every actor at once, one cell per press,
and each actor answers a control with its OWN sign along each axis — a mirrored actor walks the
opposite way. The level clears when the actors meet, either by landing on one cell or by swapping
through each other from adjacent cells.

⛔ Why plan rather than search. Measured 2026-08-27 on the game this was built for: a random walk
clears its first level in 135 actions and the searching generic path in **604**, against a human
baseline of 30. Learning the transition and planning the join takes **19**.

⛔ Frame-only. The tint pair, the background, the actor colour, the lattice pitch, each actor's
sign and what every other colour DOES are all derived. Nothing here knows a board in advance.

Three readings that were WRONG first, each corrected by a board rather than by taste:

* **The background is not the commonest colour.** On a dense board the two tints together outweigh
  it, and taking the mode handed back a tint — after which the tint pair no longer existed, the
  board had no walls, and the tool bid zero on its own game. The tints are found FIRST, by their
  own signature, and the background is the commonest of what is left.
* **The actors are not the rarest piece.** A board whose markers are drawn as sub-cell glyphs has a
  rarer colour than the actors, and adopting it tracked three things that never move. Which colour
  the CONTROLS move is a question a probe answers and a still frame does not, so when more than one
  colour looks like a piece, the tool spends one action asking.
* **Not every obstruction is the same kind.** One colour STOPS an actor that walks into it — and is
  therefore the only way to break the two apart, since a shared control otherwise moves them in
  lockstep forever — while another lets the actor walk on and then throws the board back to its
  starting position. A planner that calls both "wall" routes its decoupling bump through the second
  and never arrives. So a colour's role is LEARNED, and a colour that has done nothing yet is one
  the plan is not allowed to walk into.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, frame_2d, has_frame, levels_completed
from admorphiq.tools.segment import board_changed, edge_band

__all__ = ["MirrorMergeTool", "pieces_of", "tint_pair"]

Cell = tuple[int, int]
_SIMPLE = (1, 2, 3, 4)

# A tint has to be a real share of the board, and the two shares have to look like two halves of
# the same thing. Both numbers are loose on purpose: they exist to reject a stray sprite that
# happens to live on one side, not to measure anything.
_TINT_MIN_SHARE = 0.06
_TINT_BALANCE = 0.7
_MAX_STATES = 120_000
_MAX_PROBES = 3
_MAX_LOOSE = 6
_MAX_PARKINGS = 5
_MAX_PLACINGS = 120


def _blobs(cells: set[Cell]) -> list[list[Cell]]:
    """4-connected groups of the given cells."""
    todo = set(cells)
    out: list[list[Cell]] = []
    while todo:
        stack = [todo.pop()]
        blob = []
        while stack:
            y, x = stack.pop()
            blob.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (y + dy, x + dx)
                if nxt in todo:
                    todo.discard(nxt)
                    stack.append(nxt)
        out.append(blob)
    return out


def tint_pair(g: Any) -> tuple[int, int] | None:
    """The two colours that paint one half of the board each.

    This is the mechanic announcing itself: the board says it is two mirrored halves by painting
    them differently, and that pair is what separates this family from every other board of tiles.
    """
    n = len(g)
    mid = n // 2
    left: Counter[int] = Counter()
    right: Counter[int] = Counter()
    for y in range(n):
        for x in range(n):
            (left if x < mid else right)[int(g[y][x])] += 1
    floor = _TINT_MIN_SHARE * n * n
    best: tuple[int, int] | None = None
    balance = _TINT_BALANCE
    for a in (c for c in left if not right[c] and left[c] >= floor):
        for b in (c for c in right if not left[c] and right[c] >= floor):
            lo, hi = sorted((left[a], right[b]))
            if lo / hi >= balance:
                balance = lo / hi
                best = (a, b)
    return best


def pieces_of(g: Any, skip: set[int]) -> dict[int, tuple[list[Cell], int]]:
    """Every colour that draws two to four identical solid squares — the board's loose pieces.

    Which of these the controls actually drive is not visible in a still frame, so this returns
    all of them and lets a probe decide.
    """
    hist = Counter(int(v) for row in g for v in row)
    n = len(g)
    out: dict[int, tuple[list[Cell], int]] = {}
    for colour in sorted(hist, key=lambda c: hist[c]):
        if colour in skip:
            continue
        blobs = _blobs({(y, x) for y in range(n) for x in range(n) if int(g[y][x]) == colour})
        if not 2 <= len(blobs) <= 4:
            continue
        sides = set()
        for blob in blobs:
            ys = [p[0] for p in blob]
            xs = [p[1] for p in blob]
            height = max(ys) - min(ys) + 1
            width = max(xs) - min(xs) + 1
            if height != width or height < 2 or len(blob) != height * width:
                break
            sides.add(height)
        else:
            if len(sides) == 1:
                out[colour] = (
                    sorted((min(p[0] for p in b), min(p[1] for p in b)) for b in blobs),
                    sides.pop(),
                )
    return out


class MirrorMergeTool:
    """Learn how each control moves each actor and what each colour does, then plan the join."""

    name = "mirror"

    def __init__(self) -> None:
        self._level: int | None = None
        self._stale: np.ndarray | None = None
        self._clear()

    def _clear(self) -> None:
        self._tints: set[int] = set()
        self._bg: int | None = None
        self._colour: int | None = None
        self._pitch = 0
        self._origin: Cell = (0, 0)
        self._shape: Cell = (0, 0)
        self._base: dict[int, Cell] = {}          # action -> displacement as actor 0 sees it
        self._sign: list[list[int | None]] = []   # per actor, [vertical, horizontal] in {-1, 1}
        self._block: set[int] = set()             # colours that stop an actor
        self._fatal: set[int] = set()             # colours that undo the board
        self._free: set[int] = set()              # colours an actor may stand on
        self._tries: Counter[int] = Counter()
        self._track: tuple[Cell | None, ...] | None = None
        self._ident: tuple[int, dict[int, list[Cell]]] | None = None
        self._probing: tuple[int, tuple[Cell | None, ...]] | None = None
        self._chrome: set[int] = set()
        self._fixed: set[int] = set()             # piece colours that a click does not pick up
        self._script: list[tuple[str, Any]] = []
        self._look: frozenset[int] | None = None  # how the picked-up piece reads while it is held
        self._held: Cell | None = None
        self._before: dict[Cell, frozenset[int]] = {}
        self._pend: tuple[str, Any] | None = None
        self._drop: Cell | None = None
        self._paths: dict[Cell, list[Cell]] = {}
        self._maybe: set[int] = set()             # colours stood on but not yet vouched for
        self._stuck: tuple[Any, ...] | None = None
        self._expect: tuple[int, tuple[Cell | None, ...], tuple[Cell | None, ...],
                            list[dict[Cell, frozenset[int]]]] | None = None
        self._cache: dict[Cell, frozenset[int]] = {}

    def reset(self) -> None:
        """A new board re-tints and re-mirrors, so nothing learned about the last one carries."""
        self._clear()

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Learning happens in ``propose`` against the fresh frame, which is where the actors are."""

    def beliefs(self) -> str:
        """A one-line account of what the tool currently believes, for the driver's trace."""
        live = [p for p in (self._track or ()) if p is not None]
        return (f"col={self._colour} pitch={self._pitch} pos={live} signs={self._sign} "
                f"base={self._base} block={sorted(self._block)} fatal={sorted(self._fatal)} "
                f"free={sorted(self._free)}")

    # -- reading the board ---------------------------------------------------

    def _survey(self, g: Any) -> bool:
        """The board's fixed vocabulary: the two tints, then the background, then the pieces."""
        tints = tint_pair(g)
        if tints is None:
            return False
        hist = Counter(int(v) for row in g for v in row)
        rest = [c for c in hist if c not in tints]
        if not rest:
            return False
        self._tints = set(tints)
        self._bg = max(rest, key=lambda c: hist[c])
        return True

    def _settle(self, g: Any, colour: int, pitch: int, corner: Cell) -> None:
        """Fix the lattice and everything that hangs off it, now that the actor is known."""
        n = len(g)
        oy, ox = corner[0] % pitch, corner[1] % pitch
        self._colour = colour
        self._pitch = pitch
        self._origin = (oy, ox)
        self._shape = ((n - oy) // pitch, (n - ox) // pitch)
        self._free = {self._bg, colour} if self._bg is not None else {colour}
        # ⛔ The surround is impassable by construction — the actors never leave the board — so
        # whatever paints it is a stopper, and knowing that before moving is what lets the first
        # plan use walls to break the lockstep without gambling on an untested colour.
        band = np.asarray(g)[edge_band(np.asarray(g).shape)]
        self._chrome = {int(v) for v in band}
        self._block = (self._tints | self._chrome) - self._free

    def _cells(self, g: Any) -> dict[Cell, frozenset[int]]:
        """Every whole lattice cell, described by the colours it contains."""
        pitch = self._pitch
        oy, ox = self._origin
        rows, cols = self._shape
        return {
            (r, c): frozenset(
                int(g[oy + r * pitch + i][ox + c * pitch + j])
                for i in range(pitch) for j in range(pitch)
            )
            for r in range(rows) for c in range(cols)
        }

    def _read(self, cells: dict[Cell, frozenset[int]]) -> list[Cell]:
        """Where the actors are now, read off the lattice rather than off blob shapes.

        Two actors standing side by side are ONE blob, so shape-matching loses them exactly when
        the plan is about to succeed; a cell that carries the actor colour never does.
        """
        return sorted(cell for cell, colours in cells.items() if self._colour in colours)

    # -- the transition model ------------------------------------------------

    def _delta(self, actor: int, action: int) -> list[Cell]:
        """Every displacement this actor could take, given what is known of its signs."""
        dy, dx = self._base[action]
        vertical = [self._sign[actor][0]] if self._sign[actor][0] else [-1, 1]
        horizontal = [self._sign[actor][1]] if self._sign[actor][1] else [-1, 1]
        return sorted({(dy * v, dx * h) for v in vertical for h in horizontal})

    def _apply(self, state: tuple[Cell | None, ...], action: int,
               cells: dict[Cell, frozenset[int]], strict: bool,
               extra: frozenset[Cell] = frozenset()) -> tuple[Cell | None, ...] | None:
        """One press, or None when it is a press the plan is not allowed to make.

        ``extra`` is the set of cells to read as empty — the cells a piece is about to be shifted
        out of, so a route can be planned for the board as it will be rather than as it is.
        """
        moved: list[Cell | None] = []
        for i, pos in enumerate(state):
            if pos is None:
                moved.append(None)
                continue
            targets = [(pos[0] + dy, pos[1] + dx) for dy, dx in self._delta(i, action)]
            for target in targets:
                colours = cells.get(target)
                if colours is None or target in extra:
                    continue
                if colours & self._fatal:
                    return None
                if strict and not colours <= self._free and not colours & self._block:
                    return None
            first = targets[0]
            colours = cells.get(first)
            blocked = colours is None or (first not in extra and bool(colours & (self._block | self._fatal)))
            moved.append(pos if blocked else first)
        return self._merge(state, moved)

    @staticmethod
    def _merge(prev: tuple[Cell | None, ...],
               moved: list[Cell | None]) -> tuple[Cell | None, ...]:
        """Actors that met are gone; actors that swapped through each other met."""
        for i in range(len(prev)):
            for j in range(i + 1, len(prev)):
                a, b = prev[i], prev[j]
                if a is None or b is None or a[0] != b[0] or abs(a[1] - b[1]) != 1:
                    continue
                mi, mj = moved[i], moved[j]
                if (moved[i] == b or moved[j] == a) and mi is not None and mj is not None:
                    moved[i] = moved[j] = ((mi[0] + mj[0]) // 2, (mi[1] + mj[1]) // 2)
        share: dict[Cell, list[int]] = defaultdict(list)
        for i, cell in enumerate(moved):
            if cell is not None:
                share[cell].append(i)
        for together in share.values():
            if len(together) >= 2:
                for i in together[:2]:
                    moved[i] = None
        return tuple(moved)

    # -- learning from what happened -----------------------------------------

    def _identify(self, g: Any) -> bool:
        """Whichever piece colour the last press MOVED is the actor, and its stride is the pitch."""
        ident, self._ident = self._ident, None
        if ident is None:
            return False
        action, before = ident
        now = pieces_of(g, self._skip())
        for colour, (corners, side) in now.items():
            was = before.get(colour)
            if was is None or len(was) != len(corners) or sorted(was) == sorted(corners):
                continue
            shifts = [(a[0] - b[0], a[1] - b[1]) for b, a in zip(was, sorted(corners))]
            stride = max(abs(v) for shift in shifts for v in shift)
            if not stride:
                continue
            self._settle(g, colour, stride if stride >= side else side, corners[0])
            grid = [((y - self._origin[0]) // self._pitch, (x - self._origin[1]) // self._pitch)
                    for y, x in corners]
            self._sign = [[None, None] for _ in grid]
            self._sign[0] = [1, 1]
            self._track = tuple(grid)
            self._learn_shifts(action, [(s[0] // self._pitch, s[1] // self._pitch)
                                        for s in shifts])
            return True
        return False

    def _skip(self) -> set[int]:
        return self._tints | ({self._bg} if self._bg is not None else set())

    def _learn_shifts(self, action: int, shifts: list[Cell]) -> None:
        """Read the base displacement and each actor's signs off one press."""
        lead = shifts[0]
        if lead == (0, 0):
            # ⛔ The anchor was against something and did not move, so this press says nothing
            # about which way "forward" is. Reading (0, 0) as the base — which an index-keyed
            # delta table does — freezes a control that works into one the plan believes is inert.
            return
        self._base[action] = lead
        for i, shift in enumerate(shifts):
            if i == 0 or shift == (0, 0):
                continue
            for axis in (0, 1):
                if lead[axis]:
                    self._sign[i][axis] = 1 if shift[axis] == lead[axis] else -1

    def _learn_step(self, now: list[Cell]) -> None:
        """A planned press: confirm the model, or name the colour that refuted it."""
        expect, self._expect = self._expect, None
        if expect is None:
            return
        action, before, predicted, targets = expect
        if sorted(p for p in predicted if p is not None) == now:
            # ⛔ Standing on it for ONE frame is not proof it is safe. Measured: the actors walked
            # onto the undoing class, the frame came back showing them there, and only the NEXT
            # press produced the flash and the restore — so a same-frame "it worked" promoted the
            # one colour that must never be walked into, and the board then cycled forever.
            self._free |= self._maybe
            entered = set()
            for i, pos in enumerate(predicted):
                if pos is not None and pos != before[i]:
                    entered |= set(targets[i].get(pos, frozenset())) - self._free
            self._maybe = entered
            self._track = predicted
            return
        followed = self._follow(before, now)
        if followed is None:
            # ⛔ Nothing moved by one cell, so nothing MOVED: the board undid itself, and what did
            # that is whatever the press walked into — one press ago if it was still standing
            # there. This is the only evidence the fatal class ever gives, which is why the strict
            # pass exists to make it rare.
            blame = self._maybe or {c for reach in targets for cs in reach.values() for c in cs}
            self._fatal |= blame - self._free - self._block
            self._maybe = set()
            self._track = None
            return
        for i, pos in enumerate(followed):
            if pos is None or before[i] is None:
                continue
            if pos == before[i] and predicted[i] != before[i]:
                self._block |= set(targets[i].get(predicted[i], frozenset())) - self._free
            elif pos != before[i]:
                self._free |= set(targets[i].get(pos, frozenset()))
                base = self._base.get(action, (0, 0))
                for axis in (0, 1):
                    if base[axis] and i:
                        self._sign[i][axis] = 1 if pos[axis] - before[i][axis] == base[axis] else -1
        self._track = followed

    def _follow(self, before: tuple[Cell | None, ...],
                now: list[Cell]) -> tuple[Cell | None, ...] | None:
        """Carry each actor's identity across a frame by nearest position; one press, one cell."""
        free = list(now)
        out: list[Cell | None] = []
        for pos in before:
            if pos is None:
                out.append(None)
                continue
            near = min(free, key=lambda c: abs(c[0] - pos[0]) + abs(c[1] - pos[1]),
                       default=None) if free else None
            if near is None or abs(near[0] - pos[0]) + abs(near[1] - pos[1]) > 1:
                return None
            free.remove(near)
            out.append(near)
        return tuple(out)

    # -- Tool protocol -------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        if not has_frame(obs):
            return 0.0
        simple, _ = availability(obs)
        if not set(simple) & set(_SIMPLE):
            return 0.0
        g = frame_2d(obs)
        tints = tint_pair(g)
        if tints is None:
            return 0.0
        if self._colour is not None:
            return 0.9 if self._base else 0.6
        hist = Counter(int(v) for row in g for v in row)
        rest = [c for c in hist if c not in tints]
        if not rest:
            return 0.0
        skip = set(tints) | {max(rest, key=lambda c: hist[c])}
        return 0.6 if pieces_of(g, skip) else 0.0

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        g = frame_2d(obs)
        level = levels_completed(obs)
        if level != self._level:
            # ⛔ The frame that REPORTS a level change still draws the finished board, with the
            # actors merged into one blob. Adopting from it reads the old board's furniture as
            # the new board's actors, and the whole level is then spent moving scenery. Wait for
            # the board to actually turn over.
            stale = g if self._level is not None else None
            self._level = level
            self._clear()
            self._stale = stale
        if self._stale is not None:
            if not board_changed(self._stale, g):
                return []
            self._stale = None
        simple, clickable = availability(obs)
        legal = [a for a in _SIMPLE if a in simple]
        if not legal:
            return []
        if self._colour is None:
            asked = self._begin(g, legal)
            if asked is not None:
                return asked

        self._cache = self._cells(g)
        if self._script or self._pend is not None:
            shifting = self._advance()
            if shifting:
                return shifting
        now = self._read(self._cache)
        if len(now) < 2:
            return []
        if self._probing is not None:
            self._learn_probe(now)
        elif self._expect is not None:
            self._learn_step(now)
        if self._track is None or sorted(p for p in self._track if p is not None) != now:
            self._track = tuple(now)

        known = [a for a in legal if a in self._base]
        plan = self._plan(self._track, known, strict=True)
        if plan is None:
            asked = self._ask(legal)
            if asked is not None:
                return asked
            plan = self._plan(self._track, known, strict=False)
        if plan is None:
            asked = self._ask(legal)
            if asked is not None:
                return asked
        if plan is None and clickable and self._stuck != self._mood():
            self._script = self._shift_plan(known) or self._place_plan(known)
            self._stuck = None if self._script else self._mood()
            if self._script:
                return self._advance()
        if not plan:
            return []
        return self._commit(plan[0])

    def _begin(self, g: Any, legal: list[int]) -> list[Step] | None:
        """Before the actor is known: survey the board, then adopt it or ask which piece moves."""
        if self._ident is not None and self._identify(g):
            return None
        if self._bg is None and not self._survey(g):
            return []
        pieces = pieces_of(g, self._skip())
        if not pieces:
            return []
        if len(pieces) == 1:
            colour, (corners, side) = next(iter(pieces.items()))
            self._settle(g, colour, side, corners[0])
            oy, ox = self._origin
            self._sign = [[None, None] for _ in corners]
            self._sign[0] = [1, 1]
            self._track = tuple(((y - oy) // side, (x - ox) // side) for y, x in corners)
            return None
        # ⛔ More than one colour LOOKS like a piece, and a still frame cannot say which one the
        # controls drive. One press can, and it is the same press the model needs anyway.
        action = min(legal, key=lambda a: self._tries[a])
        if self._tries[action] >= _MAX_PROBES:
            return []
        self._tries[action] += 1
        self._ident = (action, {c: v[0] for c, v in pieces.items()})
        return [(action, None)]

    def _ask(self, legal: list[int]) -> list[Step] | None:
        """No plan under what is known: spend a press on a control that has never been tried."""
        untried = [a for a in legal if a not in self._base and self._tries[a] < _MAX_PROBES]
        if not untried:
            return None
        action = min(untried, key=lambda a: self._tries[a])
        self._tries[action] += 1
        self._probing = (action, self._track or ())
        self._expect = None
        return [(action, None)]

    def _learn_probe(self, now: list[Cell]) -> None:
        """Read the base displacement and each actor's signs off the press just made."""
        probing, self._probing = self._probing, None
        if probing is None:
            return
        action, before = probing
        followed = self._follow(before, now)
        self._track = followed if followed is not None else tuple(now)
        if followed is None:
            return
        self._learn_shifts(action, [(0, 0) if a is None or b is None
                                    else (a[0] - b[0], a[1] - b[1])
                                    for b, a in zip(before, followed)])

    def _commit(self, action: int) -> list[Step]:
        predicted = self._apply(self._track, action, self._cache, strict=False)
        if predicted is None:
            return []
        targets = [
            {(pos[0] + dy, pos[1] + dx): self._cache.get((pos[0] + dy, pos[1] + dx), frozenset())
             for dy, dx in self._delta(i, action)} if pos is not None else {}
            for i, pos in enumerate(self._track)
        ]
        self._expect = (action, self._track, predicted, targets)
        return [(action, None)]

    # -- shifting the loose pieces ------------------------------------------

    def _loose(self) -> dict[int, list[Cell]]:
        """Colours that occupy only a handful of cells — the board's loose furniture.

        The board's walls are painted in the tints and its chrome sits in the surround; anything
        else that blocks and is COUNTABLE is a piece, and a piece is the kind of thing a board
        lets you pick up. Whether this one does is settled by clicking it, never by assuming.
        """
        tally: dict[int, list[Cell]] = defaultdict(list)
        drop = self._free | self._tints | self._fatal | self._chrome | self._fixed
        for cell, colours in self._cache.items():
            for colour in colours - drop:
                tally[colour].append(cell)
        return {c: v for c, v in tally.items() if len(v) <= _MAX_LOOSE}

    def _walkable(self, cells: dict[Cell, frozenset[int]], cell: Cell) -> bool:
        colours = cells.get(cell)
        return colours is not None and colours <= self._free

    def _route(self, plan: list[int], extra: frozenset[Cell]) -> set[Cell]:
        """Every cell a plan REACHES FOR — the ground it needs kept clear.

        ⛔ Not the cells the actors stand on. The cell where they finally meet is one no actor
        ever stands on afterwards, because meeting ends them; a piece parked there turns the last
        press of a 24-press plan into a bump, and the plan verified fine right up to that press.
        """
        state = self._track or ()
        seen = {p for p in state if p is not None}
        for action in plan:
            for i, pos in enumerate(state):
                if pos is not None:
                    seen |= {(pos[0] + dy, pos[1] + dx) for dy, dx in self._delta(i, action)}
            nxt = self._apply(state, action, self._cache, False, extra)
            if nxt is None:
                break
            state = nxt
            seen |= {p for p in state if p is not None}
        return seen

    def _shift_plan(self, actions: list[int]) -> list[tuple[str, Any]]:
        """The pieces are in the way: pick each one up and park it off the actors' ground.

        The parking is CHECKED, not argued: a route is planned as if the pieces were gone, each
        piece is shoved somewhere that route never reaches for, and then the route is planned
        again against the board that would result. A parking that does not survive that second
        plan is added to the ground to keep clear and the whole thing is tried again.
        """
        loose = self._loose()
        if not loose:
            return []
        marks = sorted({cell for cells in loose.values() for cell in cells})
        extra = frozenset(marks)
        route_plan = self._plan(self._track, actions, strict=False, extra=extra)
        if route_plan is None:
            return []
        keep = self._route(route_plan, extra)
        held = {p for p in (self._track or ()) if p is not None}
        for _ in range(_MAX_PARKINGS):
            where = self._parkings(marks, keep, held)
            if where is None:
                return []
            after = dict(self._cache)
            for mark, spot in where.items():
                if spot != mark:
                    after[spot] = self._cache[mark]
                    after[mark] = frozenset({self._bg}) if self._bg is not None else frozenset()
            if self._plan(self._track, actions, strict=False, cells=after) is not None:
                return self._script_for(where, after, held)
            keep |= set(where.values())
        return []

    def _parkings(self, marks: list[Cell], keep: set[Cell],
                  held: set[Cell]) -> dict[Cell, Cell] | None:
        """Where each piece ends up, shoved one at a time with the others standing still."""
        where: dict[Cell, Cell] = {}
        for mark in sorted(marks, key=lambda c: c not in keep):
            others = (set(marks) - {mark} - set(where)) | set(where.values()) | held
            path = self._park(mark, others, keep | set(where.values()))
            if path is None:
                return None
            where[mark] = path[-1]
            self._paths[mark] = path
        return where

    def _script_for(self, where: dict[Cell, Cell], after: dict[Cell, frozenset[int]],
                    held: set[Cell]) -> list[tuple[str, Any]]:
        """Turn the parkings into presses: pick up, shove, and always put down at the end."""
        script: list[tuple[str, Any]] = []
        for mark in where:
            path = self._paths[mark]
            script.append(("click", mark))
            for a, b in zip(path, path[1:]):
                step = (b[0] - a[0], b[1] - a[1])
                action = next((k for k, v in self._base.items() if v == step), None)
                if action is None:
                    return []
                script.append(("move", action))
        drop = next((c for c in sorted(after)
                     if self._walkable(after, c) and c not in held), None)
        if drop is None:
            return []
        self._drop = drop
        script.append(("click", drop))
        return script

    def _reach(self, mark: Cell, blocked: set[Cell]) -> list[list[Cell]]:
        """Every shove this piece can be given, shortest first — each entry a path of cells."""
        steps = [v for v in self._base.values() if v != (0, 0)]
        seen: dict[Cell, list[Cell]] = {mark: [mark]}
        queue: deque[Cell] = deque([mark])
        out: list[list[Cell]] = []
        while queue:
            cell = queue.popleft()
            if cell != mark:
                out.append(seen[cell])
            for dy, dx in steps:
                nxt = (cell[0] + dy, cell[1] + dx)
                if nxt in seen or nxt in blocked or not self._walkable(self._cache, nxt):
                    continue
                seen[nxt] = seen[cell] + [nxt]
                queue.append(nxt)
        return out

    def _park(self, mark: Cell, blocked: set[Cell], keep: set[Cell]) -> list[Cell] | None:
        """Shortest shove that leaves this piece somewhere the actors will never tread."""
        return next((path for path in self._reach(mark, blocked) if path[-1] not in keep), None)

    def _place_plan(self, actions: list[int]) -> list[tuple[str, Any]]:
        """No route exists even with the pieces gone — so a piece is not the obstacle, it is the TOOL.

        ⛔ Measured on the fourth board, and it inverts the previous method. Two actors under one
        control keep a fixed vertical offset forever unless something stops one of them, and that
        board's only stoppers are its own edges, which its undoing class guards. Nothing the actors
        can do alone will ever bring them level. The one piece that can be shoved IS the missing
        wall, and where to put it is found by trying: every cell the piece can reach, cheapest
        first, keeping the first that makes a safe route exist.
        """
        loose = self._loose()
        if not loose:
            return []
        marks = sorted({cell for cells in loose.values() for cell in cells})
        held = {p for p in (self._track or ()) if p is not None}
        tried = 0
        for mark in marks:
            for path in self._reach(mark, (set(marks) - {mark}) | held):
                tried += 1
                if tried > _MAX_PLACINGS:
                    return []
                spot = path[-1]
                after = dict(self._cache)
                after[spot] = self._cache[mark]
                after[mark] = frozenset({self._bg}) if self._bg is not None else frozenset()
                if self._plan(self._track, actions, strict=True, cells=after) is None:
                    continue
                self._paths = {mark: path}
                return self._script_for({mark: spot}, after, held)
        return []

    def _mood(self) -> tuple[Any, ...]:
        """What a search over piece placements depends on — re-running it unchanged is waste."""
        return (self._track, frozenset(self._block), frozenset(self._fatal), frozenset(self._free))

    def _click(self, cell: Cell) -> list[Step]:
        oy, ox = self._origin
        half = self._pitch // 2
        return [(6, (ox + cell[1] * self._pitch + half, oy + cell[0] * self._pitch + half))]

    def _advance(self) -> list[Step]:
        """Run the shifting script, checking after every step that the board agreed.

        Every exit from this mode goes through the drop click. A piece left held recolours the
        actors, and reading a dimmed actor as scenery loses the board — so the script always ends
        by putting the piece down, including when it ends early.
        """
        pend, self._pend = self._pend, None
        if pend is not None and not self._confirm(pend):
            self._script = [("click", self._drop)] if self._held is not None else []
            self._held = None
            self._look = None
        if not self._script:
            self._held = None
            self._look = None
            return []
        step = self._script.pop(0)
        self._before = dict(self._cache)
        self._pend = step
        kind, payload = step
        if kind == "click":
            return self._click(payload)
        return [(payload, None)]

    def _confirm(self, pend: tuple[str, Any]) -> bool:
        """Did the board do what the last scripted step claimed it would?"""
        kind, payload = pend
        if kind == "click":
            if payload == self._drop:
                self._held = None
                self._look = None
                return True
            look = self._cache.get(payload)
            if look is None or look == self._before.get(payload):
                # ⛔ The click picked nothing up. That is an answer, not a failure: this colour is
                # scenery, and asking again would spend the level one action at a time.
                self._fixed |= set(self._before.get(payload, frozenset())) - self._free
                return False
            self._held = payload
            self._look = look
            return True
        if self._held is None or self._look is None:
            return False
        want = (self._held[0] + self._base[payload][0], self._held[1] + self._base[payload][1])
        if self._cache.get(want) != self._look:
            return False
        self._held = want
        return True

    def _plan(self, start: tuple[Cell | None, ...], actions: list[int],
              strict: bool, extra: frozenset[Cell] = frozenset(),
              cells: dict[Cell, frozenset[int]] | None = None) -> list[int] | None:
        """Shortest press sequence that leaves no actor on the board.

        ``strict`` refuses to walk into a colour nothing is known about; it is tried first so an
        untested colour is never the thing a plan depends on. The loose pass is the admission that
        no safe route exists, and it is where a colour earns its classification.
        """
        if not actions or any(s is not None for s in start) is False:
            return None
        cells = self._cache if cells is None else cells
        seen: dict[tuple[Cell | None, ...], list[int]] = {start: []}
        queue: deque[tuple[Cell | None, ...]] = deque([start])
        while queue and len(seen) < _MAX_STATES:
            state = queue.popleft()
            if all(p is None for p in state):
                return seen[state]
            for action in actions:
                nxt = self._apply(state, action, cells, strict, extra)
                if nxt is None or nxt in seen:
                    continue
                seen[nxt] = seen[state] + [action]
                queue.append(nxt)
        return None
