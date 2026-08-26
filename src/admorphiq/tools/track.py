"""Track tool — bring the marked items to the marked slots on rotating tracks.

The mechanic, recovered from frames: a lattice of equal square tiles, each a flat colour; one or
more STATIC markers, each drawn as four corner blocks around a single slot; and controls that
rotate a track — an ordered cyclic run of slots — by one slot per press. A level is won when
every marked slot holds a tile of its marker's colour.

⛔ Why this shape of tool rather than a search. Measured 2026-08-27 across the 25 sample games:
the generic searching path clears a first level 6x to 109x over the budget the game DECLARES, and
thirteen of the games end when that budget runs out. On the game this was built for, the search
took 924 actions for a level that allows 13. Rotating a track to a computed offset takes as many
presses as the offset — which is what the human baseline is.

⛔ Frame-only, by construction: the tile side, the lattice pitch, which slots form a track, which
control turns it and which way, and which colour is wanted where are all DERIVED. Nothing about
any game is written down here.

⛔ The track is NOT a geometric loop, and reading it as one is what capped this tool at a single
level. Measured over all eight boards of its game: a track can be a straight run whose last slot
wraps to its first; it can be a serpentine path; it can step DIAGONALLY; it can be split across
four separated segments chained in an order only the colours reveal; and one press can turn two
independent tracks at once. What every one of them does obey is that a press is a cyclic shift by
one along SOME order, so the order is recovered by probe and then CHECKED — a hypothesis is kept
only when replaying the shift reproduces the observed colours cell for cell.
"""

from __future__ import annotations

from collections import Counter, deque
from itertools import permutations
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, frame_2d, has_frame
from admorphiq.tools.segment import background, candidate_pitches, components

__all__ = ["TrackAlignTool", "read_board", "markers_on", "recover_tracks"]

Cell = tuple[int, int]

# The marker is a square annulus one tile-quarter thick; the tile is 2 units of a 3-unit lattice
# step. Both numbers come from the SAME source — the drawing grammar of a board of tiles — and
# BOTH are load-bearing, measured over the 25 sample games at 60 actions each: the lattice test
# alone leaves ONE other game reading as a tile board, and requiring the annulus removes it. The
# bid is a conjunction because either half alone is not this mechanic.
_PITCH_NUM, _PITCH_DEN = 3, 2
_MIN_TILES = 6
_BFS_STATES = 200_000
# Chaining segments into one track is a permutation search; past this many segments the search is
# not worth its cost and the tool would rather have no model than a guessed one.
_MAX_SEGMENTS = 6
# How many candidate slot-sets the growth search may test before it settles for what it has.
_GROWTH_TRIES = 400


def _blobs(g: Any) -> list[tuple[int, int, int, int, int, int, list[Cell]]]:
    """Every non-background region, with its bounding box, area and colour."""
    out = []
    for cells in components(g, background(g, 2)):
        y0 = min(c[0] for c in cells)
        x0 = min(c[1] for c in cells)
        h = max(c[0] for c in cells) - y0 + 1
        w = max(c[1] for c in cells) - x0 + 1
        out.append((y0, x0, h, w, len(cells), int(g[y0][x0]), cells))
    return out


def read_board(g: Any) -> tuple[dict[Cell, int], int, int] | None:
    """The tiles, their side and the lattice pitch — or None when this is not a tile board.

    ⛔ The two commonest colours are excluded, not one. Measured: on the boards where the play
    area is smaller than the frame, the surround is the commonest colour and the play area the
    second, so blocking one colour returns the whole play area — tiles included — as a single
    square region and the board reads as one enormous tile.
    """
    blobs = _blobs(g)
    squares = [b for b in blobs if b[2] == b[3] and b[4] == b[2] * b[3]]
    if not squares:
        return None
    side = Counter(b[2] for b in squares).most_common(1)[0][0]
    if side < 2 or side % 2:
        return None
    tiles = {(b[0], b[1]): b[5] for b in squares if b[2] == side}
    if len(tiles) < _MIN_TILES:
        return None
    pitch = candidate_pitches(list(tiles), side, limit=1)
    if not pitch or pitch[0] * _PITCH_DEN != side * _PITCH_NUM:
        return None
    return tiles, side, pitch[0]


def markers_on(g: Any, tiles: dict[Cell, int], side: int) -> list[tuple[Cell, int]]:
    """Slots ringed by four corner blocks of one colour that a tile also wears.

    The corner blocks are a quarter of the tile on a side and sit just outside it, so the whole
    mark is twice the tile across. Requiring the colour to be one a TILE wears is what makes the
    mark a demand rather than decoration: it names which tile is wanted here.
    """
    k = side // 2
    n = len(g)
    worn = set(tiles.values())
    found: list[tuple[Cell, int]] = []
    for (y, x) in tiles:
        corners = ((y - k, x - k), (y - k, x + side), (y + side, x - k), (y + side, x + side))
        seen: list[int] = []
        for (cy, cx) in corners:
            if cy < 0 or cx < 0 or cy + k > n or cx + k > n:
                break
            block = {int(g[cy + i][cx + j]) for i in range(k) for j in range(k)}
            if len(block) != 1:
                break
            seen.append(block.pop())
        if len(seen) == 4 and len(set(seen)) == 1 and seen[0] in worn:
            found.append(((y, x), seen[0]))
    return found


def controls_on(g: Any, tiles: dict[Cell, int], side: int) -> list[Cell]:
    """Compact regions that are not tiles and not chrome — the things worth pressing.

    ⛔ The edge band is excluded because the step counter lives there. Measured: on one board it
    contributes eight separate marks of exactly tile area, and probing each cost an action to
    learn that a counter does nothing.
    """
    n = len(g)
    margin = max(1, n // 16)
    owned = {(y + i, x + j) for (y, x) in tiles for i in range(side) for j in range(side)}
    out: list[Cell] = []
    for (y0, x0, h, w, area, _colour, cells) in _blobs(g):
        if area < side * side or h > n // 2 or w > n // 2:
            continue
        if any(c in owned for c in cells):
            continue
        cy, cx = y0 + h // 2, x0 + w // 2
        if cy < margin or cy >= n - margin or cx < margin or cx >= n - margin:
            continue
        out.append((cy, cx))
    return sorted(out)


# -- recovering what a press does -------------------------------------------


def _neighbours(c: Cell, live: set[Cell], pitch: int, diagonal: bool) -> list[Cell]:
    steps = [(0, pitch), (0, -pitch), (pitch, 0), (-pitch, 0)]
    if diagonal:
        steps += [(pitch, pitch), (pitch, -pitch), (-pitch, pitch), (-pitch, -pitch)]
    return [(c[0] + dy, c[1] + dx) for dy, dx in steps if (c[0] + dy, c[1] + dx) in live]


def _components(live: set[Cell], pitch: int, diagonal: bool) -> list[set[Cell]]:
    unseen = set(live)
    out: list[set[Cell]] = []
    while unseen:
        stack = [min(unseen)]
        seen = {stack[0]}
        while stack:
            cur = stack.pop()
            for nxt in _neighbours(cur, live, pitch, diagonal):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        unseen -= seen
        out.append(seen)
    return out


def _thread(live: set[Cell], pitch: int, diagonal: bool) -> list[Cell] | None:
    """Order a connected set as a simple path or cycle; None when it is neither."""
    if len(live) == 1:
        return [next(iter(live))]
    adj = {c: _neighbours(c, live, pitch, diagonal) for c in live}
    if any(len(a) > 2 or not a for a in adj.values()):
        return None
    ends = [c for c, a in adj.items() if len(a) == 1]
    if not ends:
        start = min(live)
    elif len(ends) == 2:
        start = min(ends)
    else:
        return None
    order = [start]
    prev, cur = None, start
    while True:
        nxt = next((c for c in adj[cur] if c != prev), None)
        if nxt is None or nxt == start:
            break
        order.append(nxt)
        prev, cur = cur, nxt
    return order if len(order) == len(live) else None


def _shifts_to(order: list[Cell], before: dict[Cell, int], after: dict[Cell, int], step: int) -> bool:
    """Does sliding this order by `step` reproduce the observed colours exactly?"""
    n = len(order)
    return all(after[order[(i + step) % n]] == before[order[i]] for i in range(n))


def _as_separate(parts: list[list[Cell]], before: dict[Cell, int],
                 after: dict[Cell, int]) -> list[tuple[list[Cell], int]] | None:
    """Each piece is a track of its own, turned by the same press."""
    out: list[tuple[list[Cell], int]] = []
    for order in parts:
        if len(order) < 2:
            return None
        if _shifts_to(order, before, after, 1):
            out.append((order, 1))
        elif _shifts_to(order, before, after, -1):
            out.append((order, -1))
        else:
            return None
    return out


def _as_chained(parts: list[list[Cell]], before: dict[Cell, int],
                after: dict[Cell, int]) -> list[tuple[list[Cell], int]] | None:
    """One track whose slots fall in several separated segments.

    Inside a segment the shift is visible as a slide; ACROSS segments only the colours say which
    segment feeds which, so the joining order is searched and then checked in full.
    """
    if not 2 <= len(parts) <= _MAX_SEGMENTS:
        return None
    for mask in range(1 << len(parts)):
        runs = [p if (mask >> i) & 1 else p[::-1] for i, p in enumerate(parts)]
        if not all(all(after[r[i + 1]] == before[r[i]] for i in range(len(r) - 1)) for r in runs):
            continue
        for tail in permutations(range(1, len(runs))):
            ring = [c for i in (0, *tail) for c in runs[i]]
            if _shifts_to(ring, before, after, 1):
                return [(ring, 1)]
    return None


def recover_tracks(changed: set[Cell], slots: set[Cell], pitch: int,
                   before: dict[Cell, int], after: dict[Cell, int]) -> list[tuple[list[Cell], int]] | None:
    """What this press did, as ordered tracks — the widest reading that replays exactly.

    ⛔ The slots that changed are a SUBSET of the track: two neighbouring tiles of one colour
    leave the second unchanged when they slide. So the changed set is grown by the slots that
    would close its gaps, and every reading along the way is checked; the widest one that replays
    the frame cell for cell wins. Taking the FIRST that replays instead read a sixteen-slot track
    as fifteen and cost three re-plans and forty extra actions on one board.

    ⛔ Growth branches ONE slot at a time at a loose end. Adding every loose-end neighbour at once
    is cheaper and wrong: on a three-slot track whose ends share a colour only two slots change,
    and a bulk step jumps straight from two to five, never testing the three that is the answer —
    the tool then plans against a two-slot track and every press lands somewhere else.
    """
    best: tuple[int, list[tuple[list[Cell], int]]] | None = None
    for diagonal in (False, True):
        seen: set[frozenset[Cell]] = set()
        queue: list[set[Cell]] = [set(changed)]
        while queue and len(seen) < _GROWTH_TRIES:
            grown = queue.pop(0)
            key = frozenset(grown)
            if key in seen:
                continue
            seen.add(key)
            parts = [_thread(part, pitch, diagonal) for part in _components(grown, pitch, diagonal)]
            if all(p is not None for p in parts):
                whole = [p for p in parts if p is not None]
                for reading in (_as_separate(whole, before, after), _as_chained(whole, before, after)):
                    if reading is None:
                        continue
                    size = sum(len(o) for o, _ in reading)
                    if best is None or size > best[0]:
                        best = (size, reading)
            gaps = {u for u in slots if u not in grown
                    and len(_neighbours(u, grown, pitch, diagonal)) >= 2}
            if gaps:
                queue.append(grown | gaps)
                continue
            adj = {c: _neighbours(c, grown, pitch, diagonal) for c in grown}
            loose = {c for c, a in adj.items() if len(a) <= 1}
            for u in sorted(slots):
                if u not in grown and set(_neighbours(u, grown, pitch, diagonal)) & loose:
                    queue.append(grown | {u})
    return best[1] if best else None


# -- planning ---------------------------------------------------------------


def _plan_presses(tiles: dict[Cell, int], marks: list[tuple[Cell, int]],
                  moves: dict[Cell, dict[Cell, Cell]]) -> list[Cell] | None:
    """Shortest press sequence that puts a wanted colour on every marked slot.

    A press permutes SLOTS regardless of what stands on them, so only the tiles wearing a marker's
    colour need tracking — the rest of the board is scenery. That is what keeps the search small
    enough to be exact rather than greedy.
    """
    wanted: dict[int, set[Cell]] = {}
    for slot, colour in marks:
        wanted.setdefault(colour, set()).add(slot)
    colours = sorted(wanted)
    start = tuple(tuple(sorted(s for s, v in tiles.items() if v == c)) for c in colours)

    def done(state: tuple[tuple[Cell, ...], ...]) -> bool:
        return all(wanted[c] <= set(state[i]) for i, c in enumerate(colours))

    if done(start):
        return []
    if not moves:
        return None
    seen: dict[tuple, tuple | None] = {start: None}
    queue = deque([start])
    while queue:
        state = queue.popleft()
        for control, mapping in moves.items():
            nxt = tuple(tuple(sorted(mapping.get(p, p) for p in group)) for group in state)
            if nxt in seen:
                continue
            seen[nxt] = (state, control)
            if done(nxt):
                out: list[Cell] = []
                cur: tuple = nxt
                while seen[cur] is not None:
                    prev, press = seen[cur]
                    out.append(press)
                    cur = prev
                return out[::-1]
            queue.append(nxt)
            if len(seen) > _BFS_STATES:
                return None
    return None


class TrackAlignTool:
    """Turn the tracks until every marked slot wears its marker's colour."""

    name = "track"

    def __init__(self) -> None:
        self._signature: tuple | None = None
        self._moves: dict[Cell, dict[Cell, Cell]] = {}
        self._probed: set[Cell] = set()
        self._pending: Cell | None = None
        self._before: dict[Cell, int] | None = None
        self._plan: list[Cell] = []
        self._expect: list[dict[Cell, int]] = []
        self._seen: dict[Cell, int] = {}
        self._settled = 0
        self._stuck = False

    def reset(self) -> None:
        """A new board redraws the tracks; what each control does is re-learned."""
        self._signature = None
        self._moves = {}
        self._probed = set()
        self._pending = None
        self._before = None
        self._plan = []
        self._expect = []
        self._seen = {}
        self._settled = 0
        self._stuck = False

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Everything is recomputed from the board, so a transition carries nothing extra."""

    # -- Tool protocol ---------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        # ⛔ No mark, no bid. Returning a consolation score for "there is a lattice here" cost a
        # DIFFERENT game 0.0943 of its score, measured full-25: a lattice that happens to carry a
        # cycle is not this mechanic, and a tool with nothing to propose must not compete for the
        # turn. `_stuck` is the same rule one step later — once the board is read and no press
        # sequence reaches the marks, the bid drops to zero rather than holding the board.
        if self._stuck or not has_frame(obs):
            return 0.0
        g = frame_2d(obs)
        board = read_board(g)
        if board is None:
            return 0.0
        tiles, side, _pitch = board
        return 0.85 if markers_on(g, tiles, side) else 0.0

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        g = frame_2d(obs)
        board = read_board(g)
        if board is None:
            return []
        tiles, side, pitch = board
        signature = (side, pitch, frozenset(tiles))
        if signature != self._signature:
            self.reset()
            self._signature = signature
        if self._pending is not None:
            self._learn(tiles, pitch)
        if self._seen != tiles:
            self._settled = 0
        self._seen = dict(tiles)

        marks = markers_on(g, tiles, side)
        if not marks:
            return []
        if all(tiles[slot] == colour for slot, colour in marks):
            self._settled += 1
            if self._settled < 2:
                # The frame that follows a win still shows the board just finished. One harmless
                # click — a corner is off any board — moves it on without spending a press.
                return [(6, (0, 0))]
            # ⛔ Still aligned and still here: the win is only TESTED on a press, so a board that
            # arrives already satisfied hangs forever on harmless clicks. One press breaks the
            # alignment, and the planner puts it back — which is the press that gets tested.
            spots = controls_on(g, tiles, side)
            return [(6, (spots[0][1], spots[0][0]))] if spots else []

        untried = [c for c in controls_on(g, tiles, side) if c not in self._probed]
        if untried:
            self._pending = untried[0]
            self._before = dict(tiles)
            self._plan, self._expect = [], []
            return [(6, (untried[0][1], untried[0][0]))]

        if self._plan and self._expect and self._expect[0] == tiles:
            press = self._plan.pop(0)
            self._expect.pop(0)
            return [(6, (press[1], press[0]))]

        found = _plan_presses(tiles, marks, self._moves)
        if not found:
            self._stuck = found is None
            return []
        self._plan = found
        self._expect = self._forecast(tiles, found)
        press = self._plan.pop(0)
        self._expect.pop(0)
        return [(6, (press[1], press[0]))]

    # -- learning --------------------------------------------------------

    def _learn(self, tiles: dict[Cell, int], pitch: int) -> None:
        """Read off the tracks this press turned, keeping only a reading that replays exactly."""
        before, control = self._before, self._pending
        self._pending, self._before = None, None
        if before is None or control is None or set(before) != set(tiles):
            return
        self._probed.add(control)
        changed = {s for s in before if before[s] != tiles[s]}
        if not changed:
            return                                      # this control turns nothing
        tracks = recover_tracks(changed, set(before), pitch, before, tiles)
        if not tracks:
            return
        mapping: dict[Cell, Cell] = {}
        for order, step in tracks:
            n = len(order)
            for i, slot in enumerate(order):
                mapping[slot] = order[(i + step) % n]
        self._moves[control] = mapping

    def _forecast(self, tiles: dict[Cell, int], presses: list[Cell]) -> list[dict[Cell, int]]:
        """The board as it should look before each press — the plan's own falsification test."""
        out = []
        state = dict(tiles)
        for press in presses:
            out.append(dict(state))
            mapping = self._moves[press]
            state = {mapping.get(s, s): v for s, v in state.items()}
        return out
