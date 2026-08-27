"""Decouple the pair with the stop, then join it — one search over actors, stop and selection.

RECOVERED MECHANIC (frame-only, measured on live boards 2026-08-27). The board is a lattice of
flat cells drawn over a backdrop painted in TWO TINTS, one per half of the frame, and the walls
are painted in those same tints because they are holes in the level art that the backdrop shows
through. Two ACTORS sit on it, mirror-placed about the frame's own mid line. The four simple
actions move BOTH actors at once, one cell a press: a vertical press moves them the same way, a
horizontal press moves them OPPOSITE ways. The level ends the instant the two actors occupy one
cell — either by landing together, or by trading places from cells that were side by side, which
the board resolves by dropping both on the cell between them.

Under shared controls a mirrored pair keeps its coordinates locked together forever, so on a
symmetric board the actors can only ever meet on the mid column. Three further furnishings are
what make the deep boards solvable, and each is read from the cell's own drawing:

* a STOP — a cell drawn as a ring of floor colour around a solid centre. A click on it takes it
  under control (every actor dims to say so) and the same four actions then drive the STOP alone,
  one cell a press; a click anywhere on plain floor hands control back. An actor cannot walk
  through a stop, so a stop parked beside one actor is the ONLY way to break the coupling: press
  toward it, that actor bumps and stays while its partner walks on.
* DOORS AND KEYS, paired by COLOUR and told apart by SHAPE — a run of two or more touching cells
  of one colour is a door, a lone cell of that same colour is its key. A door is solid unless an
  actor is standing on a key of its colour AT THAT MOMENT. So a door is not opened and left open:
  somebody has to be holding it.
* HAZARDS — cells drawn as a checkerboard rather than a flat colour. What one does is not read
  off the frame and this tool never finds out: an unproven cell is one the plan is not allowed to
  walk into, and no board here needs one.

⛔ WHY ONE JOINT SEARCH, AND NOT PARK-THEN-PLAN. This is the whole difference on the last board,
and it is a difference of ORDER, not of cleverness. There, both actors start in the upper half,
the two halves are sealed by a door each, and each actor's key opens the door on the OTHER side.
The stop starts in the lower half and cannot reach the upper half, because the doors between them
are shut — until the actors are walked onto their keys, which is when both doors open at once and
stay open for exactly as long as the actors stand still. So the order is: move the actors two
presses, THEN take the stop and drive it nine cells through a door that only exists because of
where the actors are, THEN hand control back and use it. A planner that decides where the stop
goes from the board it can see now will never find that placement, because from that board the
stop cannot go there. The search here holds (actor cells, stop cell, what is selected) as ONE
state and lets the clicks fall wherever they fall — measured: the level falls in 40 actions
against a human baseline of 237, and it had never been reached at all, at any budget.

The search is run in the least powerful form that solves the board — walking, then shoving the
stops off the walking route, then the joint search — because the joint state space is a hundred
times larger and every board that does not need it should not pay for it. The middle rung is not
a nicety: one board is fenced into four chambers by THREE stops, so no single placement opens it
and the joint search over one movable stop exhausts 400,000 states without an answer, while
shoving all three off a route planned as if no stop existed takes 54 actions against a human 203.

MEASURED END TO END, 2026-08-27, on the live board and on an archived re-render of it, identical
on both to the action: SIX levels of six, 188 actions, per level 19 / 23 / 54 / 13 / 39 / 40
against human baselines of 30 / 111 / 203 / 26 / 500 / 237 — every level at or under the human
count, in 2.3 seconds.

⛔ THE LATTICE IS ANCHORED ON A DIVISION THAT REALLY EXISTS. The tint seam falls on the frame's
own mid line and cuts the cell that straddles it in two — the only division a cell of this family
ever shows. Accepting a two-part cell ANYWHERE instead makes a misaligned lattice read as
perfectly clean, because every cell straddling two flat regions is two-part; measured, that
swallowed both actors on two of six boards while reporting a flawless fit.

⛔ WHICH CONTROL DOES WHAT IS ASKED, NOT ASSUMED, AND THE ANSWER IS HALF PORTABLE. Which press is
vertical and which way it goes holds for the whole game and is learned once. Which actor is the
one that walks WITH a horizontal press does NOT: it is the left actor on some boards and the
right one on others, so each board costs one horizontal press to settle, chosen so that neither
answer walks anybody into an unproven cell.
"""

from __future__ import annotations

from collections import Counter, deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, has_frame

__all__ = ["CoupledPairTool", "read_board", "lattice", "settled"]

Cell = tuple[int, int]          # (row, col) on the recovered lattice
_SIMPLE = (1, 2, 3, 4)
# Cells smaller than 3 pixels cannot draw a ring, and a board of fewer than seven cells a side is
# not one of these. Both bounds are the drawing's, not a tuning choice.
_PITCH_RANGE = range(3, 9)
_MIN_CELLS = 7
# A lattice is accepted only when essentially every cell reads as one of the four drawings; the
# slack exists for a single stray cell, not to admit a misfit.
_CLEAN = 0.995
# A tint has to be a real share of the frame and the two shares have to look like two halves of
# one backdrop. Loose on purpose: they reject a sprite that happens to live on one side.
_TINT_SHARE = 0.06
_TINT_BALANCE = 0.7
_MAX_STATES = 400_000
_MAX_PLANS = 6
_CONFIRM = 3


# --- cell reading -----------------------------------------------------------

def settled(obs: Any) -> np.ndarray:
    """The LAST layer the action handed back — the board after everything it set off resolved.

    One action of this family can span eight rendered ticks (a hazard blinks the actors and then
    throws the level back to its start), and layer 0 is the board the action STARTED from.
    """
    fr = getattr(obs, "frame", None)
    if fr is None:
        return np.zeros((0, 0), dtype=np.int64)
    arr = np.asarray(fr)
    while arr.ndim >= 3:
        arr = arr[-1]
    return arr.astype(np.int64) if arr.ndim == 2 else np.zeros((0, 0), dtype=np.int64)


def _neutralise(f: np.ndarray) -> np.ndarray:
    """Fold the frame's outermost pixel ring inward — that is where a counter is drawn."""
    g = f.copy()
    g[0, :] = g[1, :]
    g[-1, :] = g[-2, :]
    g[:, 0] = g[:, 1]
    g[:, -1] = g[:, -2]
    return g


def _kind(b: np.ndarray, y0: int, x0: int) -> tuple | None:
    """How this cell is drawn: flat, checkered, ringed, or cut by the frame's mid line."""
    vals = {int(v) for v in b.ravel()}
    if len(vals) == 1:
        return ("flat", int(b[0, 0]))
    if len(vals) != 2:
        return None
    s = b.shape[0]
    a, c = sorted(vals)
    par = ((np.arange(y0, y0 + s)[:, None] + np.arange(x0, x0 + s)[None, :]) % 2).astype(bool)
    if (b[par] == a).all() and (b[~par] == c).all():
        return ("check", a, c)
    if (b[par] == c).all() and (b[~par] == a).all():
        return ("check", c, a)
    rim = np.ones((s, s), dtype=bool)
    rim[1:-1, 1:-1] = False
    for outer, inner in ((a, c), (c, a)):
        if (b[rim] == outer).all() and (b[~rim] == inner).all():
            return ("ring", int(outer), int(inner))
    if x0 < 32 < x0 + s:
        k = 32 - x0
        if len({int(v) for v in b[:, :k].ravel()}) == 1 and len({int(v) for v in b[:, k:].ravel()}) == 1:
            return ("seam", int(b[0, 0]), int(b[0, -1]))
    if y0 < 32 < y0 + s:
        k = 32 - y0
        if len({int(v) for v in b[:k, :].ravel()}) == 1 and len({int(v) for v in b[k:, :].ravel()}) == 1:
            return ("seam", int(b[0, 0]), int(b[-1, 0]))
    return None


def lattice(f: np.ndarray) -> tuple[int, int, int] | None:
    """(pitch, row origin, column origin) of the lattice on which every cell reads cleanly.

    The lattice covers the WHOLE frame, not just the board: the letterbox is painted in the tints
    and therefore reads as wall, which is exactly what it is to anything that walks. Recovering
    the board's true extent as well would buy nothing and can only be got wrong.
    """
    best: tuple[float, int, int, int] | None = None
    for s in _PITCH_RANGE:
        for ay in range(s):
            for ax in range(s):
                ny, nx = (64 - ay) // s, (64 - ax) // s
                if ny < _MIN_CELLS or nx < _MIN_CELLS:
                    continue
                # Give up on an alignment the moment it cannot reach the bar. A misaligned
                # lattice fails within its first few cells, so this is most of the cost.
                slack = int((ny * nx) * (1.0 - _CLEAN))
                bad = 0
                for gy in range(ny):
                    y0 = ay + gy * s
                    for gx in range(nx):
                        x0 = ax + gx * s
                        if _kind(f[y0:y0 + s, x0:x0 + s], y0, x0) is None:
                            bad += 1
                            if bad > slack:
                                break
                    if bad > slack:
                        break
                if bad > slack:
                    continue
                frac = 1.0 - bad / (ny * nx)
                if best is None or (frac, s) > (best[0], best[1]):
                    best = (frac, s, ay, ax)
    return (best[1], best[2], best[3]) if best else None


class Board:
    """Everything the planner needs, all of it read off one frame."""

    __slots__ = ("pitch", "ay", "ax", "ny", "nx", "kinds", "floor", "tints",
                 "wall", "risky", "stops", "doors", "keys", "actors", "actor_colour", "held")

    def __init__(self) -> None:
        self.pitch = self.ay = self.ax = self.ny = self.nx = 0
        self.kinds: dict[Cell, tuple] = {}
        self.floor = -1
        self.tints: tuple[int, int] = (-1, -1)
        self.wall: set[Cell] = set()     # proven solid: walking into one is a bump
        self.risky: set[Cell] = set()    # unproven: the plan may not walk into one at all
        self.stops: list[Cell] = []
        self.doors: dict[Cell, int] = {}
        self.keys: dict[Cell, int] = {}
        self.actors: list[Cell] = []
        self.actor_colour = -1
        self.held: Cell | None = None      # the stop under control, by cell

    def centre(self, cell: Cell) -> tuple[int, int]:
        return (self.ax + cell[1] * self.pitch + self.pitch // 2,
                self.ay + cell[0] * self.pitch + self.pitch // 2)

    def inside(self, cell: Cell) -> bool:
        return 0 <= cell[0] < self.ny and 0 <= cell[1] < self.nx


def _tints(board: Board) -> tuple[int, int] | None:
    """The two backdrop colours: one per half of the frame, each a real share, roughly equal."""
    where: dict[int, list[Cell]] = {}
    for cell, k in board.kinds.items():
        if k and k[0] == "flat":
            where.setdefault(k[1], []).append(cell)
    total = len(board.kinds)
    best: tuple[int, int, int] | None = None
    colours = sorted(where)
    for i, a in enumerate(colours):
        for b in colours[i + 1:]:
            la, lb = where[a], where[b]
            if min(len(la), len(lb)) < _TINT_SHARE * total:
                continue
            if min(len(la), len(lb)) / max(len(la), len(lb)) < _TINT_BALANCE:
                continue
            xa = [board.centre(c)[0] for c in la]
            xb = [board.centre(c)[0] for c in lb]
            if max(xa) < 32 < min(xb) or max(xb) < 32 < min(xa):
                cand = (len(la) + len(lb), a, b)
                if best is None or cand > best:
                    best = cand
    return (best[1], best[2]) if best else None


def _runs(cells: list[Cell]) -> list[list[Cell]]:
    """4-connected groups of the given cells."""
    todo = set(cells)
    out: list[list[Cell]] = []
    while todo:
        stack = [todo.pop()]
        run = []
        while stack:
            y, x = stack.pop()
            run.append((y, x))
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if (ny, nx) in todo:
                    todo.discard((ny, nx))
                    stack.append((ny, nx))
        out.append(run)
    return out


def _loose_colours(board: Board) -> dict[int, list[Cell]]:
    """Non-backdrop, non-floor colours drawn only as cells that touch nothing of their own kind."""
    where: dict[int, list[Cell]] = {}
    for cell, k in board.kinds.items():
        if k and k[0] == "flat" and k[1] not in (board.floor, *board.tints):
            where.setdefault(k[1], []).append(cell)
    return {c: cells for c, cells in where.items()
            if len(cells) >= 2 and all(len(r) == 1 for r in _runs(cells))}


def _actor_candidates(board: Board, loose: dict[int, list[Cell]]) -> list[int]:
    """Loose colours that include a pair mirrored about the frame's mid line."""
    out = []
    for colour, cells in loose.items():
        xs = [board.centre(c)[0] for c in cells]
        if any(abs(xs[i] + xs[j] - 64) <= 2 for i in range(len(xs)) for j in range(i + 1, len(xs))):
            out.append(colour)
    return out


def _nearest_colour(loose: dict[int, list[Cell]], prev: list[Cell]) -> int | None:
    """The loose colour sitting where the actors were — how a recolour is followed."""
    best: tuple[int, int] | None = None
    for colour, cells in loose.items():
        if len(cells) != len(prev):
            continue
        cost = 0
        for p in prev:
            near = min(max(abs(p[0] - c[0]), abs(p[1] - c[1])) for c in cells)
            if near > 1:
                cost = -1
                break
            cost += near
        if cost >= 0 and (best is None or cost < best[0]):
            best = (cost, colour)
    return best[1] if best else None


def read_board(f: np.ndarray, actor_colours: set[int] | None = None,
               prev: list[Cell] | None = None, rest_inner: set[int] | None = None) -> Board | None:
    """The whole board — lattice, backdrop, walls, stops, doors, keys, actors — from one frame.

    ⛔ The mirrored pair identifies the actors on the FIRST frame and never again. Two presses in
    and the pair is no longer mirrored (that is the point of the exercise), and taking control of
    a stop RECOLOURS every actor to say so. Both were measured to lose the actors mid-plan. Once
    the caller knows what it is following, it says so: a colour it has seen, or failing that the
    loose colour sitting where the actors were one press ago.
    """
    raw = np.asarray(f)
    if raw.shape != (64, 64):
        return None                 # a board this tool cannot see is not a board it may plan on
    g = _neutralise(raw.astype(np.int16))
    lat = lattice(g)
    if lat is None:
        return None
    b = Board()
    b.pitch, b.ay, b.ax = lat
    b.ny, b.nx = (64 - b.ay) // b.pitch, (64 - b.ax) // b.pitch
    for gy in range(b.ny):
        y0 = b.ay + gy * b.pitch
        for gx in range(b.nx):
            x0 = b.ax + gx * b.pitch
            b.kinds[(gy, gx)] = _kind(g[y0:y0 + b.pitch, x0:x0 + b.pitch], y0, x0)
    tints = _tints(b)
    if tints is None:
        return None
    b.tints = tints
    flat = Counter(k[1] for k in b.kinds.values() if k and k[0] == "flat")
    rest = [c for c in flat if c not in tints]
    if not rest:
        return None
    b.floor = max(rest, key=lambda c: flat[c])
    loose = _loose_colours(b)
    colour = None
    if actor_colours:
        colour = next((c for c in sorted(actor_colours)
                       if c in loose and (prev is None or len(loose[c]) == len(prev))), None)
        if colour is None and prev is not None:
            colour = _nearest_colour(loose, prev)
    else:
        cands = _actor_candidates(b, loose)
        colour = cands[0] if len(cands) == 1 else None
    if colour is None:
        return None
    b.actor_colour = colour
    b.actors = sorted(loose[colour])

    # A stop is a ring of floor colour; the centre it is drawn with says whether it is held.
    rings = sorted((c, k) for c, k in b.kinds.items() if k and k[0] == "ring" and k[1] == b.floor)
    b.stops = [c for c, _ in rings]
    if rest_inner:
        odd = [c for c, k in rings if k[2] not in rest_inner]
        if len(odd) == 1:
            b.held = odd[0]

    # Doors and keys share a colour; a run of two or more cells is the door, a lone cell its key.
    for colour in {k[1] for k in b.kinds.values() if k and k[0] == "flat"} - {b.floor, b.actor_colour, *tints}:
        cells = [c for c, k in b.kinds.items() if k and k[0] == "flat" and k[1] == colour]
        runs = _runs(cells)
        doors = [c for r in runs if len(r) > 1 for c in r]
        keys = [c for r in runs if len(r) == 1 for c in r]
        if doors and keys:
            b.doors.update({c: colour for c in doors})
            b.keys.update({c: colour for c in keys})

    known = set(b.actors) | set(b.stops) | set(b.doors) | set(b.keys)
    for cell, k in b.kinds.items():
        if cell in known or (k and k[0] == "flat" and k[1] == b.floor):
            continue
        if k and (k[0] == "seam" or (k[0] == "flat" and k[1] in tints)):
            b.wall.add(cell)        # the backdrop showing through the level art: solid, and known so
        else:
            b.risky.add(cell)
    return b


# --- the model the search plans in ------------------------------------------

class _Sim:
    """The transition rule, stated once and used by both the search and the check."""

    def __init__(self, board: Board, delta: dict[int, list[Cell]],
                 raw: dict[int, Cell]) -> None:
        self.b = board
        self.delta = delta          # action id -> per-actor (dy, dx)
        # A held stop is ONE object and takes the press as given — the mirroring belongs to the
        # actors, not to the control, so a stop driven with an actor's sense goes the wrong way
        # whenever that actor happens to be the mirrored one.
        self.raw = raw

    def open_doors(self, actors: tuple[Cell | None, ...]) -> set[int]:
        """Door colours whose key has somebody standing on it RIGHT NOW."""
        return {self.b.keys[p] for p in actors if p is not None and p in self.b.keys}

    def shut(self, actors: tuple[Cell | None, ...]) -> set[Cell]:
        opened = self.open_doors(actors)
        return {c for c, colour in self.b.doors.items() if colour not in opened}

    def step(self, state: tuple, act: tuple) -> tuple | None:
        actors, stops, held = state
        if act[0] == "c":
            return (actors, stops, act[1])
        wall = self.b.wall | self.shut(actors)
        moves = self.delta.get(act[1])
        if moves is None:
            return None
        if held >= 0:
            dy, dx = self.raw[act[1]]
            # A stop is driven by the same press, without the mirroring — it is one object.
            cell = (stops[held][0] + dy, stops[held][1] + dx)
            if cell in self.b.risky:
                return None
            if (self.b.inside(cell) and cell not in wall and cell not in self.b.keys
                    and cell not in stops and cell not in actors):
                stops = tuple(cell if i == held else s for i, s in enumerate(stops))
            return (actors, stops, held)
        after: list[Cell | None] = []
        for i, pos in enumerate(actors):
            if pos is None:
                after.append(None)
                continue
            dy, dx = moves[i]
            cell = (pos[0] + dy, pos[1] + dx)
            # ⛔ An unproven cell is not a wall and must not be planned as one. Measured: the board
            # LETS an actor walk onto a hazard and then throws the whole level back to its start,
            # so a plan that counted on the bump — and the bump is exactly what breaks the pair
            # apart, so the search reaches for it — diverges from the engine on that very press.
            if cell in self.b.risky:
                return None
            if not self.b.inside(cell) or cell in wall or cell in stops:
                cell = pos
            after.append(cell)
        # Two actors that were side by side and traded places settle on the cell between them.
        for i in range(len(after)):
            for j in range(i + 1, len(after)):
                a, c = actors[i], actors[j]
                if a is None or c is None or a[0] != c[0] or abs(a[1] - c[1]) != 1:
                    continue
                if after[i] == c or after[j] == a:
                    mid = ((after[i][0] + after[j][0]) // 2, (after[i][1] + after[j][1]) // 2)
                    after[i] = after[j] = mid
        seats: dict[Cell, list[int]] = {}
        for i, pos in enumerate(after):
            if pos is not None:
                seats.setdefault(pos, []).append(i)
        for pos, who in seats.items():
            if len(who) >= 2:
                for i in who[:2]:
                    after[i] = None
        return (tuple(after), stops, held)

    def won(self, state: tuple) -> bool:
        return all(p is None for p in state[0])


def _search(sim: _Sim, start: tuple, free_cell: Cell | None,
            movable: int | None, cap: int) -> list[tuple] | None:
    """Shortest press-and-click sequence that ends the level, or None inside the cap."""
    acts: list[tuple] = [("a", a) for a in sorted(sim.delta)]
    if free_cell is not None and start[1]:
        # Handing control back is always available: a search entered while a stop is held has no
        # other way to move an actor at all, and that state is reachable whenever a plan was
        # interrupted part way through a shove.
        acts.append(("c", -1))
        if movable is not None:
            acts.append(("c", movable))
    seen: dict[tuple, tuple | None] = {start: None}
    queue: deque[tuple] = deque([start])
    while queue and len(seen) < cap:
        state = queue.popleft()
        for act in acts:
            nxt = sim.step(state, act)
            if nxt is None or nxt in seen:
                continue
            if sim.won(nxt):
                out = [act]
                cur = state
                while seen[cur] is not None:
                    pact, prev = seen[cur]
                    out.append(pact)
                    cur = prev
                return list(reversed(out))
            seen[nxt] = (act, state)
            queue.append(nxt)
    return None


def _drives(sim: _Sim, state: tuple, which: int) -> dict[Cell, list[tuple]]:
    """Every cell this stop can be shoved to while the actors stand still, and how."""
    start = state[1][which]
    seen: dict[Cell, list[tuple]] = {start: []}
    queue: deque[Cell] = deque([start])
    held = (state[0], state[1], which)
    while queue:
        cell = queue.popleft()
        here = (held[0], tuple(cell if i == which else c for i, c in enumerate(held[1])), which)
        for a in sorted(sim.raw):
            nxt = sim.step(here, ("a", a))
            if nxt is None:
                continue
            got = nxt[1][which]
            if got in seen:
                continue
            seen[got] = seen[cell] + [("a", a)]
            queue.append(got)
    del seen[start]
    return seen


def _route(sim: _Sim, state: tuple, acts: list[tuple]) -> set[Cell]:
    """Every cell a walking plan REACHES FOR — the ground a parked stop must stay off.

    Not the cells the actors stand on. The cell where they finally meet is one no actor ever
    stands on afterwards, because meeting ends them, so a stop parked there turns the last press
    of the plan into a bump and the plan verifies fine right up to it.
    """
    seen: set[Cell] = set()
    for act in acts:
        if act[0] == "a":
            for i, pos in enumerate(state[0]):
                if pos is not None:
                    dy, dx = sim.delta[act[1]][i]
                    seen.add((pos[0] + dy, pos[1] + dx))
        state = sim.step(state, act)
        if state is None:
            break
        seen |= {p for p in state[0] if p is not None}
    return seen


def _shift_then_walk(sim: _Sim, state: tuple, free: Cell | None) -> list[tuple] | None:
    """The stops are in the WAY: shove each one off the route and then walk.

    Cheap because the halves do not interact — nothing the actors do changes where a stop can go
    while they stand still. The parking is CHECKED, not argued: the route is planned as if no stop
    existed, each stop is shoved somewhere that route never reaches for, and the walk is planned
    AGAIN against the board that leaves.
    """
    if free is None or not state[1]:
        return None
    bare = _search(sim, (state[0], (), -1), free, None, _MAX_STATES)
    if bare is None:
        return None
    keep = _route(sim, (state[0], (), -1), bare) | {p for p in state[0] if p is not None}
    script: list[tuple] = []
    stops = list(state[1])
    parked: set[Cell] = set()
    for i in range(len(stops)):
        if stops[i] not in keep:
            continue
        routes = _drives(sim, (state[0], tuple(stops), -1), i)
        spot = min((c for c in routes if c not in keep and c not in parked),
                   key=lambda c: len(routes[c]), default=None)
        if spot is None:
            return None
        script += [("c", i), *routes[spot]]
        parked.add(spot)
        stops[i] = spot
    if not script:
        return None
    walk = _search(sim, (state[0], tuple(stops), -1), free, None, _MAX_STATES)
    if walk is None:
        return None
    return script + [("c", -1)] + walk


class CoupledPairTool:
    """See the module docstring — the mechanic, and why the search is joint."""

    name = "decouple"

    def __init__(self) -> None:
        # Held for the whole GAME: which press is vertical, and which way each press goes for an
        # actor whose horizontal sense is +1. Both are properties of the controls, not the board.
        self._axis: dict[int, str] = {}
        self._sense: dict[int, tuple[int, int]] = {}
        self._clear()

    def _clear(self) -> None:
        self._colours: set[int] = set()     # every colour the actors have been drawn in here
        self._rest: set[int] = set()        # the centre colour a stop rests in
        self._seen: list[Cell] = []         # where the actors were one propose() ago
        self._order: list[Cell] = []        # the stops in a FIXED order, followed as they move
        self._sign: dict[int, int] = {}     # actor index -> horizontal sense on THIS board
        self._plan: list[Step] = []
        self._expect: list[tuple] = []
        self._sim: _Sim | None = None
        self._at = 0
        self._confirmed = 0
        self._plans = 0
        self._probing: int | None = None
        self._probe_from: Board | None = None
        self._dead = False

    def reset(self) -> None:
        self._clear()

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Nothing is learned from the action alone — the board it produced is read on the next
        propose(), where both frames are available and the actors can be matched."""

    # -- learning the controls ------------------------------------------------

    def _learn(self, before: Board, after: Board, action: int) -> None:
        """What one press did, matched actor to actor by their order along the row."""
        if len(before.actors) != len(after.actors):
            return
        shifts = [(b[0] - a[0], b[1] - a[1]) for a, b in zip(before.actors, after.actors)]
        moved = [s for s in shifts if s != (0, 0)]
        if not moved:
            return
        if any(dy for dy, _ in moved):
            if any(dx for _, dx in moved):
                return          # a press that moves on both axes is not this family
            self._axis[action] = "v"
            self._sense[action] = (moved[0][0], 0)
            return
        self._axis[action] = "h"
        first = next(i for i, s in enumerate(shifts) if s != (0, 0))
        if action not in self._sense:
            self._sense[action] = (0, shifts[first][1])
        base = self._sense[action][1]
        for i, (_, dx) in enumerate(shifts):
            if dx:
                self._sign[i] = 1 if dx == base else -1
        if len(self._sign) == 1 and len(shifts) == 2:
            # A mirrored pair has one sense each; one observed actor settles both.
            self._sign[1 - next(iter(self._sign))] = -next(iter(self._sign.values()))

    def _raw(self) -> dict[int, Cell]:
        return {a: self._sense[a] for a in _SIMPLE}

    def _delta(self, n: int) -> dict[int, list[Cell]] | None:
        """Per-action, per-actor cell shift — None until every press and sense is known."""
        if len(self._axis) < len(_SIMPLE) or len(self._sign) < n:
            return None
        out: dict[int, list[Cell]] = {}
        for a in _SIMPLE:
            dy, dx = self._sense[a]
            if self._axis[a] == "v":
                out[a] = [(dy, 0)] * n
            else:
                out[a] = [(0, dx * self._sign[i]) for i in range(n)]
        return out

    # -- the harness contract -------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        # A tool with no plan bids ZERO. Once the search has come back empty on this board there
        # is nothing to hold it for, and holding it costs the board its turn with everything else.
        if self._dead or not has_frame(obs):
            return 0.0
        simple, action6 = availability(obs)
        if not action6 or not set(_SIMPLE).issubset(set(simple)):
            return 0.0
        try:
            board = read_board(settled(obs))
        except Exception:  # noqa: BLE001 — a frame this tool cannot parse is not this family
            return 0.0
        if board is None or len(board.actors) != 2:
            return 0.0
        return 0.9

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if self._dead or not has_frame(obs):
            return []
        board = self._look(obs)
        if board is None or len(board.actors) != 2:
            # A level-up hands back the board that was just SOLVED — the actors have gone and the
            # next board is not drawn until something acts on it. One press it already understands
            # is the cheapest way through, and cheaper than whatever the harness would probe.
            return [(self._known_press(), None)] if len(self._axis) == len(_SIMPLE) else []
        if self._probing is not None and self._probe_from is not None:
            self._learn(self._probe_from, board, self._probing)
            self._probing = self._probe_from = None
        gap = self._untried(board)
        if gap is not None:
            self._probing, self._probe_from = gap, board
            return [(gap, None)]
        state = self._state(board)
        if self._plan and self._at < len(self._plan) and state == self._expect[self._at]:
            self._confirmed += 1
            head = self._plan[self._at:]
            take = len(head) if self._confirmed >= _CONFIRM else 1
            self._at += take
            return head[:take]
        return self._replan(board, state)

    # -- internals ------------------------------------------------------------

    def _known_press(self) -> int:
        return next(a for a in _SIMPLE if self._axis.get(a) == "v")

    def _look(self, obs: Any) -> Board | None:
        """Read the board, telling the reader what this tool is already following."""
        board = read_board(settled(obs), self._colours or None,
                           self._seen or None, self._rest or None)
        if board is None:
            return None
        self._colours.add(board.actor_colour)
        # ⛔ Actors are followed too, and for the same reason as the stops: the reader hands them
        # back in reading order, so the moment one overtakes the other on the page they swap
        # identity — and each actor's horizontal SENSE is attached to that identity. Measured,
        # the plan diverged on its FIRST press.
        board.actors = self._follow_from(self._seen, board.actors)
        self._seen = list(board.actors)
        if not self._rest:
            self._rest = {k[2] for k in board.kinds.values()
                          if k and k[0] == "ring" and k[1] == board.floor}
        # ⛔ Stops are followed, never re-sorted. Sorting them by cell renumbers the whole set the
        # moment one of them moves past another, and a plan that says "the one I am holding" then
        # means a different object — measured, the plan diverged on its third press.
        board.stops = self._follow_from(self._order, board.stops)
        self._order = list(board.stops)
        return board

    @staticmethod
    def _follow_from(was: list[Cell], now: list[Cell]) -> list[Cell]:
        """Put `now` into the order of `was`, matching each to the nearest place it could be."""
        if len(was) != len(now):
            return list(now)
        left = list(now)
        out: list[Cell] = []
        for old in was:
            near = min(left, key=lambda c: abs(c[0] - old[0]) + abs(c[1] - old[1]))
            left.remove(near)
            out.append(near)
        return out

    def _untried(self, board: Board) -> int | None:
        """The next press worth spending an action on to finish the control model.

        The horizontal sense is the only part that has to be re-asked on every board, and the
        press chosen is one whose outcome is safe under BOTH answers — an actor walked into an
        unproven cell teaches nothing the plan can use and may cost the board.
        """
        unknown = [a for a in _SIMPLE if a not in self._axis]
        if unknown:
            return unknown[0]
        if len(self._sign) >= len(board.actors):
            return None
        horiz = [a for a in _SIMPLE if self._axis[a] == "h"]
        wall = board.wall | board.risky | {c for c, colour in board.doors.items()
                                if colour not in {board.keys[p] for p in board.actors if p in board.keys}}
        for a in horiz:
            dx = self._sense[a][1]
            if all(not board.inside((p[0], p[1] + s * dx)) or (p[0], p[1] + s * dx) not in wall
                   for p in board.actors for s in (1, -1)):
                return a
        return horiz[0] if horiz else None

    def _state(self, board: Board) -> tuple:
        held = board.stops.index(board.held) if board.held in board.stops else -1
        return (tuple(board.actors), tuple(board.stops), held)

    def _free_cell(self, board: Board, state: tuple | None = None) -> Cell | None:
        """A plain floor cell to click to hand control back.

        ⛔ Chosen from the board as it will BE, not as it is. The letterbox is not clickable at
        all — the board simply does not answer — and a cell a stop has since been parked on is
        worse than useless: clicking it picks that stop UP again. Measured: a plan that shoved
        three stops then clicked the cell one of them now occupied.
        """
        taken = set(board.actors) | set(board.stops)
        if state is not None:
            taken = {p for p in state[0] if p is not None} | set(state[1])
        return next((c for c, k in sorted(board.kinds.items())
                     if k and k[0] == "flat" and k[1] == board.floor and c not in taken), None)

    def _replan(self, board: Board, state: tuple) -> list[Step]:
        delta = self._delta(len(board.actors))
        if delta is None:
            return []
        self._plans += 1
        if self._plans > _MAX_PLANS:
            self._dead = True
            return []
        sim = _Sim(board, delta, self._raw())
        free = self._free_cell(board)
        # The least powerful search that solves the board, in order. Walking is free; shoving a
        # stop off the route costs one more walk; holding actors, stop and
        # selection in ONE state costs a space a hundred times larger and is the only thing that
        # can express "walk the actors first so the stop's road exists".
        found = _search(sim, state, free, None, _MAX_STATES)
        if found is None:
            found = _shift_then_walk(sim, state, free)
        if found is None:
            for i in range(len(board.stops)):
                found = _search(sim, state, free, i, _MAX_STATES)
                if found is not None:
                    break
        if found is None:
            self._dead = True
            return []
        self._sim = sim
        self._plan, self._expect = self._materialise(sim, state, found, free)
        self._at = 1
        self._confirmed = 0
        return self._plan[:1]

    def _materialise(self, sim: _Sim, state: tuple, acts: list[tuple],
                     free: Cell | None) -> tuple[list[Step], list[tuple]]:
        """Turn the abstract sequence into presses and clicks, and record the board each leaves."""
        steps: list[Step] = []
        expect: list[tuple] = [state]
        for act in acts:
            if act[0] == "a":
                steps.append((act[1], None))
            else:
                cell = state[1][act[1]] if act[1] >= 0 else self._free_cell(sim.b, state)
                if cell is None:
                    break
                steps.append((6, sim.b.centre(cell)))
            state = sim.step(state, act)
            expect.append(state)
        return steps, expect
