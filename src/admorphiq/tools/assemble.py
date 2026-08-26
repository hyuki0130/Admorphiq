"""Assemble tool — loose pieces carrying seam marks, moved and re-formed until the seams meet.

The mechanic, recovered from frames: the board holds a handful of rigid pieces. One is SELECTED at
a time; a click on a piece selects it, the four simple actions slide the selected piece one cell,
and the fifth RE-FORMS it. Every piece carries a few MARKER cells — lone cells of a colour the
piece's body does not use. The level clears when every marker sits on exactly one other marker,
i.e. when the pieces interlock like a jigsaw.

⛔ The load-bearing discovery is the ACCEPTANCE TEST, not the search. Markers come in two kinds and
the frame CANNOT tell them apart — the renderer paints both the same colour, matched or not. So a
purely geometric "every marker cell is covered twice" criterion admits arrangements the game
rejects, and executing a wrong one costs the level's whole budget. MEASURED on the four unstacked
levels of the game this was built for: adding "and NOTHING ELSE overlaps — two bodies never share
a cell, a body never lands on a marker" cuts 8/32/32/128 geometric arrangements to 4/4/8/16, and
every survivor is accepted by the game. The pieces are a tiling; the markers are the seams.

⛔ The turn action is NOT assumed to be a rotation — it is WATCHED. MEASURED on the same game: on
its last two levels several pieces are stacked at one spot with only the top one visible, and the
turn action steps through that stack instead of turning anything, bouncing at both ends. A tool
that computes the next form with `rot90` reads those boards as unsolvable. So the tool presses the
turn once, keeps the quarter-turn answer if that is what came back, and otherwise walks the orbit
until it returns to where it started, recording each form it is given.

⛔ Read a piece while it is SELECTED. Some boards grey every resting piece to one flat colour, so
an unselected piece shows no markers at all; selection is what reveals them.

⛔ A wrong action is charged. The board draws a countdown and the game ENDS when it runs out, so
this tool acts only from a completed plan: it reads every piece, solves the tiling offline, and
then spends actions. `detect` is 0.0 whenever that has failed or cannot be attempted.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, frame_2d, has_frame, levels_completed
from admorphiq.tools.segment import background, components

__all__ = ["JigsawAssembleTool", "lattice_of", "pieces_of", "marker_colour"]

Cell = tuple[int, int]  # (x, y) on the coarse board
_TURN = 5
_SLIDE = {(1, 0): 4, (-1, 0): 3, (0, 1): 2, (0, -1): 1}
_MAX_NODES = 400_000
_MAX_SOLUTIONS = 400
_MAX_ORBIT = 26
_MIN_CELLS = 3
_MAX_IDLE = 8


def lattice_of(g: np.ndarray) -> tuple[int, int, int] | None:
    """(cells, scale, offset): the coarse board this frame is a blow-up of, or None.

    The frame is a nearest-neighbour magnification of a small board, letter-boxed to the centre.
    The coarsest lattice on which EVERY block is one flat colour is that board — chrome pinned
    outside the letter box is excluded by construction, which is why the offset is derived rather
    than assumed.
    """
    n = int(g.shape[0])
    for cells in range(n // 2, 3, -1):
        scale = n // cells
        if scale < 2:
            continue
        off = (n - cells * scale) // 2
        blocks = g[off : off + cells * scale, off : off + cells * scale]
        blocks = blocks.reshape(cells, scale, cells, scale)
        if bool(np.all(blocks == blocks[:, :1, :, :1])):
            return cells, scale, off
    return None


def pieces_of(board: np.ndarray) -> tuple[list[set[Cell]], int]:
    """The connected non-background regions of the coarse board, and the background colour."""
    bg = background(board.tolist())
    comps = components(board.tolist(), bg)
    out = [{(x, y) for (y, x) in comp} for comp in comps if len(comp) >= _MIN_CELLS]
    return out, int(next(iter(bg)))


def marker_colour(forms: list[np.ndarray]) -> int | None:
    """The seam colour: the colour the most pieces have in common, rarest first on a tie.

    ⛔ Not "the minority colour within each piece". MEASURED on the game this was built for: one
    piece is three cells, two of which are markers, so its own majority IS the marker and a
    per-piece reading inverts it — the level then never solves. Bodies differ from piece to piece;
    the seams are what the pieces have in common, so sharing is the discriminator.
    """
    if len(forms) < 2:
        return None
    carried: Counter[int] = Counter()
    total: Counter[int] = Counter()
    for art in forms:
        carried.update({int(v) for v in art.ravel() if v >= 0})
        total.update(int(v) for v in art.ravel() if v >= 0)
    shared = [c for c in carried if carried[c] >= 2]
    if not shared:
        return None
    return min(shared, key=lambda c: (-carried[c], total[c], c))


def _crop(board: np.ndarray, cells: set[Cell]) -> tuple[np.ndarray, Cell]:
    """The piece as a rectangle of colours with -1 off the piece, plus its top-left corner."""
    xs = [x for x, _ in cells]
    ys = [y for _, y in cells]
    x0, y0 = min(xs), min(ys)
    art = np.full((max(ys) - y0 + 1, max(xs) - x0 + 1), -1, dtype=int)
    for x, y in cells:
        art[y - y0, x - x0] = int(board[y, x])
    return art, (x0, y0)


def _quarter(art: np.ndarray) -> np.ndarray:
    """The piece as it would look one clockwise quarter turn on."""
    return np.rot90(art, k=3)


def _same(a: np.ndarray, b: np.ndarray) -> bool:
    return a.shape == b.shape and bool(np.array_equal(a, b))


def _footprint(art: np.ndarray, at: Cell) -> set[Cell]:
    return {
        (at[0] + x, at[1] + y)
        for y in range(art.shape[0])
        for x in range(art.shape[1])
        if art[y, x] >= 0
    }


class JigsawAssembleTool:
    """Read every piece and every form it takes, solve the tiling, then spend actions on it."""

    name = "assemble"

    def __init__(self) -> None:
        self._level: int | None = None
        self._earned = False
        self._scale, self._off, self._cells = 1, 0, 64
        self.reset()

    def reset(self) -> None:
        """A new level is a new set of pieces; nothing about the old one carries."""
        self._forms: list[list[np.ndarray]] = []
        self._closed: list[bool] = []
        self._cur: list[int] = []
        self._at: list[Cell] = []
        self._marks: list[list[np.ndarray]] = []
        self._marker: int | None = None
        self._selected: int | None = None
        self._pending: Cell | None = None
        self._turning = False
        self._prev: np.ndarray | None = None
        self._plan: list[tuple[int, int, Cell]] = []
        self._layouts: list[dict[int, tuple[int, int, int]]] = []
        self._done: set[int] = set()
        self._sliding: tuple[int, int, Cell] | None = None
        self._idle = 0
        self._dead = False

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """The board is re-read every turn, so nothing is carried through this hook."""

    # -- reading -------------------------------------------------------------

    def _board(self, obs: Any) -> np.ndarray | None:
        g = frame_2d(obs)
        lat = lattice_of(g)
        if lat is None:
            return None
        cells, scale, off = lat
        self._scale, self._off, self._cells = scale, off, cells
        return g[off : off + cells * scale : scale, off : off + cells * scale : scale]

    def _click(self, cell: Cell) -> Step:
        """A click at the centre of a coarse cell, in frame pixels."""
        x, y = cell
        half = self._scale // 2
        return 6, (self._off + x * self._scale + half, self._off + y * self._scale + half)

    def _signature(self, board: np.ndarray) -> bool:
        """Several disjoint pieces, at least one stitched with LONE odd cells, an even seam count.

        ⛔ "Lone" is what earns the bid. MEASURED across the 24 other sample boards: a piece
        carrying a two-cell patch of a second colour is a DRAWING, and dropping the isolation test
        makes this tool bid on a board it cannot solve. A seam is a single cell by construction —
        it is the point another piece has to touch.
        """
        parts, _ = pieces_of(board)
        if len(parts) < 2:
            return False
        seams = 0
        for cells in parts:
            hist = Counter(int(board[y, x]) for x, y in cells)
            body = hist.most_common(1)[0][0]
            odd = {(x, y) for x, y in cells if int(board[y, x]) != body}
            if not odd or len(odd) > 0.4 * len(cells):
                continue
            if any((x + dx, y + dy) in odd for x, y in odd for dx, dy in ((1, 0), (0, 1))):
                continue
            seams += len(odd)
        return seams >= 2 and seams % 2 == 0

    def _cells_of(self, idx: int) -> set[Cell]:
        return _footprint(self._forms[idx][self._cur[idx]], self._at[idx])

    def _taken(self, skip: int | None = None) -> set[Cell]:
        out: set[Cell] = set()
        for i in range(len(self._forms)):
            if i != skip:
                out |= self._cells_of(i)
        return out

    def _unseen(self, board: np.ndarray) -> Cell | None:
        """A cell of some piece no form of ours accounts for."""
        seen = self._taken()
        for cells in pieces_of(board)[0]:
            spare = cells - seen
            if spare:
                return sorted(spare)[0]
        return None

    # -- discovery -----------------------------------------------------------

    def _adopt(self, board: np.ndarray, cells: set[Cell]) -> int:
        art, corner = _crop(board, cells)
        self._forms.append([art])
        self._closed.append(False)
        self._cur.append(0)
        self._at.append(corner)
        return len(self._forms) - 1

    def _region(self, board: np.ndarray, seeds: set[Cell], skip: int | None,
                keep: set[Cell] | None = None) -> set[Cell] | None:
        """The piece the seed cells belong to, minus every other piece.

        ⛔ `keep` is not optional in spirit. MEASURED: a piece that turns can come to REST AGAINST
        a piece nobody has read yet, and the two are then one region — the tool recorded both as
        a single piece, its orbit never closed, and the board went unreadable. After a turn the
        piece is exactly what CHANGED plus where it already was; a neighbour is neither.
        """
        others = self._taken(skip)
        for cells in pieces_of(board)[0]:
            if cells & seeds:
                spare = cells - others
                if keep is not None:
                    spare &= keep
                if len(spare) >= 1:
                    return spare
        return None

    def _upset(self, board: np.ndarray, changed: set[Cell], allow: int) -> bool:
        """Did the whole board move under us? Then what we just watched explains nothing.

        ⛔ MEASURED: a cleared level only turns into the next one when SOMETHING acts, so the
        action this tool spends reading the old board is eaten by the transition and answered
        with a completely different board. Adopting a piece from that answer produced an orbit
        that could never close, and the level was lost to sixteen wasted turns.
        """
        touched = [cells for cells in pieces_of(board)[0] if cells & changed]
        return len(touched) > allow or len(changed) > 0.5 * board.size

    def _restart(self) -> None:
        """Forget what was read without forgetting that this tool belongs to this game."""
        earned, level, idle = self._earned, self._level, self._idle
        self.reset()
        self._earned, self._level, self._idle = earned, level, idle

    def _absorb_click(self, board: np.ndarray) -> None:
        """The click selected a piece we had not read: record it as it now shows itself."""
        prev, self._prev = self._prev, None
        clicked, self._pending = self._pending, None
        if prev is None or clicked is None:
            return
        changed = {(int(x), int(y)) for y, x in zip(*np.where(board != prev))}
        if not changed:
            self._dead = True  # nothing answered the click; this board is not ours
            return
        if self._upset(board, changed, allow=2):
            self._restart()
            return
        region = self._region(board, {clicked}, None)
        if region is None or clicked not in region:
            self._dead = True
            return
        self._selected = self._adopt(board, region)

    def _absorb_turn(self, board: np.ndarray) -> None:
        """The turn re-formed the selected piece: record the form it came back as."""
        prev, self._prev = self._prev, None
        self._turning = False
        changed = {(int(x), int(y)) for y, x in zip(*np.where(board != prev))} if prev is not None else set()
        if not changed:
            self._dead = True  # the turn did nothing; the mechanic is not what we read
            return
        if self._upset(board, changed, allow=1):
            self._restart()
            return
        if self._selected is None:
            # The level handed the selection to a piece we have not identified. Whatever the turn
            # moved IS that piece, and the board we came in on holds its resting form.
            before = self._region(prev, changed, None) if prev is not None else None
            if before is None:
                self._dead = True
                return
            self._selected = self._adopt(prev, before)
            was = before
        else:
            was = self._cells_of(self._selected)
        idx = self._selected
        region = self._region(board, changed, idx, keep=changed | was)
        if region is None:
            self._dead = True
            return
        art, corner = _crop(board, region)
        forms = self._forms[idx]
        self._at[idx] = corner
        if len(forms) == 1 and _same(art, _quarter(forms[0])):
            # A quarter turn came back: the orbit is the four quarter turns, no more presses owed.
            self._forms[idx] = [forms[0], art, _quarter(art), _quarter(_quarter(art))]
            self._closed[idx] = True
            self._cur[idx] = 1
            return
        forms.append(art)
        self._cur[idx] = len(forms) - 1
        # ⛔ The orbit closes on the SEQUENCE repeating, never on one form coming back. MEASURED:
        # a stack walks up to its top and then walks back down, so the form after k presses does
        # not determine the form after k+1 — the direction is hidden state. Reading a single
        # repeat as the period made the tool press three times expecting the tallest form and get
        # the second-shortest, and the level was then executed against a piece that was not there.
        for period in range(1, len(forms) - 1):
            if _same(forms[period], forms[0]) and _same(forms[period + 1], forms[1]):
                self._forms[idx] = forms[:period]
                self._closed[idx] = True
                self._cur[idx] = (len(forms) - 1) % period
                return
        if len(forms) >= _MAX_ORBIT:
            self._dead = True

    def _finalise(self) -> bool:
        """Name the seam colour once every piece is read, and mark up every form it can take."""
        marker = marker_colour([forms[0] for forms in self._forms])
        if marker is None:
            return False
        self._marker = marker
        self._marks = [[(art == marker) for art in forms] for forms in self._forms]
        return all(any(m.any() for m in marks) for marks in self._marks)

    # -- solving -------------------------------------------------------------

    def _solve(self) -> list[dict[int, tuple[int, int, int]]]:
        """Every tiling with the markers paired and nothing else shared, cheapest first."""
        n = len(self._forms)
        if n < 2:
            return []
        found: list[dict[int, tuple[int, int, int]]] = []
        budget = [_MAX_NODES]
        # An orbit that bounces shows the same form twice; the search needs each shape once.
        choices = [
            [f for f in range(len(forms)) if all(not _same(forms[f], forms[g]) for g in range(f))]
            for forms in self._forms
        ]
        most = [max(int(m.sum()) for m in marks) for marks in self._marks]

        def place(idx: int, f: int, dx: int, dy: int,
                  occ: dict[Cell, bool]) -> dict[Cell, bool] | None:
            art = self._forms[idx][f]
            mark = self._marks[idx][f]
            out = dict(occ)
            for yy in range(art.shape[0]):
                for xx in range(art.shape[1]):
                    if art[yy, xx] < 0:
                        continue
                    key = (xx + dx, yy + dy)
                    is_mark = bool(mark[yy, xx])
                    if key in out:
                        # ⛔ The whole acceptance test: a shared cell is legal only when BOTH
                        # sides of it are markers, and only ever two deep.
                        if not is_mark or not out[key]:
                            return None
                        out[key] = False
                    else:
                        out[key] = is_mark
            return out

        def walk(placed: dict[int, tuple[int, int, int]], occ: dict[Cell, bool]) -> None:
            if budget[0] <= 0 or len(found) >= _MAX_SOLUTIONS:
                return
            budget[0] -= 1
            if len(placed) == n:
                if not any(occ.values()):
                    found.append(dict(placed))
                return
            if not placed:
                for f in choices[0]:
                    nxt = place(0, f, 0, 0, occ)
                    if nxt is not None:
                        walk({0: (f, 0, 0)}, nxt)
                return
            openings = [c for c, still in occ.items() if still]
            if not openings:
                return
            # ⛔ Aim every candidate at ONE open seam, not at all of them. That seam has to be
            # closed by SOMEBODY, so nothing is lost — and it collapses the n! ways of reaching
            # the same arrangement into one. MEASURED on the 13-piece level: the whole space goes
            # from 40 million nodes and ninety seconds to a fraction of a second.
            spare = sum(most[idx] for idx in range(n) if idx not in placed)
            if len(openings) > spare:
                return
            ox, oy = min(openings)
            tried: set[tuple[int, int, int, int]] = set()
            for idx in range(n):
                if idx in placed:
                    continue
                for f in choices[idx]:
                    for my, mx in zip(*np.where(self._marks[idx][f])):
                        key = (idx, f, ox - int(mx), oy - int(my))
                        if key in tried:
                            continue
                        tried.add(key)
                        nxt = place(idx, f, key[2], key[3], occ)
                        if nxt is None:
                            continue
                        placed[idx] = (f, key[2], key[3])
                        walk(placed, nxt)
                        del placed[idx]

        walk({}, {})
        scored = sorted(
            ((got[0], lay) for lay, got in ((lay, self._cost(lay)) for lay in found) if got),
            key=lambda z: z[0],
        )
        return [lay for _, lay in scored]

    def _presses(self, idx: int, form: int) -> int:
        """Fewest presses to show this shape — a bouncing orbit offers it at more than one step."""
        forms = self._forms[idx]
        orbit = len(forms)
        return min(
            (j - self._cur[idx]) % orbit
            for j in range(orbit)
            if _same(forms[j], forms[form])
        )

    def _cost(self, layout: dict[int, tuple[int, int, int]]
              ) -> tuple[int, list[tuple[int, int, Cell]]] | None:
        """Cheapest global placement of a relative layout, in actions, or None if it cannot fit."""
        n = self._cells
        spans = [
            (dx, dy, dx + self._forms[i][f].shape[1], dy + self._forms[i][f].shape[0])
            for i, (f, dx, dy) in layout.items()
        ]
        lo_x = min(s[0] for s in spans)
        lo_y = min(s[1] for s in spans)
        hi_x = max(s[2] for s in spans)
        hi_y = max(s[3] for s in spans)
        if hi_x - lo_x > n or hi_y - lo_y > n:
            return None
        best: tuple[int, list[tuple[int, int, Cell]]] | None = None
        for tx in range(-lo_x, n - hi_x + 1):
            for ty in range(-lo_y, n - hi_y + 1):
                total = 0
                steps: list[tuple[int, int, Cell]] = []
                for i in sorted(layout):
                    f, dx, dy = layout[i]
                    turns = self._presses(i, f)
                    art = self._forms[i][f]
                    sx, sy = self._at[i]
                    cx, cy = self._reseat(sx, sy, art.shape) if turns else (sx, sy)
                    tgt = (dx + tx, dy + ty)
                    moves = abs(tgt[0] - cx) + abs(tgt[1] - cy)
                    if turns == 0 and moves == 0:
                        continue
                    total += 1 + turns + moves
                    steps.append((i, f, tgt))
                if best is None or total < best[0]:
                    best = (total, steps)
        return best

    def _reseat(self, sx: int, sy: int, shape: tuple[int, ...]) -> Cell:
        """A re-formed piece keeps its corner, then the board pushes it back inside."""
        n = self._cells
        return max(0, min(sx, n - shape[1])), max(0, min(sy, n - shape[0]))

    # -- execution -----------------------------------------------------------

    def _handle(self, idx: int) -> Cell | None:
        """A cell of this piece that no other piece is sitting on — the only safe click."""
        free = sorted(self._cells_of(idx) - self._taken(idx))
        return free[len(free) // 2] if free else None

    def _reseat_from(self, board: np.ndarray, idx: int) -> bool:
        """Find the selected piece again after it changed form; markers count as wildcards."""
        art = self._forms[idx][self._cur[idx]]
        marker = self._marker
        bg = background(board.tolist())
        n = self._cells
        hits = []
        for y0 in range(n - art.shape[0] + 1):
            for x0 in range(n - art.shape[1] + 1):
                ok = True
                for yy in range(art.shape[0]):
                    for xx in range(art.shape[1]):
                        want = int(art[yy, xx])
                        if want < 0:
                            continue
                        got = int(board[y0 + yy, x0 + xx])
                        if got in bg or (want != marker and got != want):
                            ok = False
                            break
                    if not ok:
                        break
                if ok:
                    hits.append((x0, y0))
        if len(hits) != 1:
            return False
        self._at[idx] = hits[0]
        return True

    # -- Tool protocol -------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        if not has_frame(obs) or self._dead:
            return 0.0
        simple, six = availability(obs)
        if not six or not {1, 2, 3, 4, _TURN}.issubset(set(simple)):
            return 0.0
        board = self._board(obs)
        if board is None:
            return 0.0
        if self._plan:
            return 0.9
        return 0.45 if self._earned or self._signature(board) else 0.0

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs) or self._dead:
            return []
        level = levels_completed(obs)
        if level != self._level:
            if self._level is not None:
                self._earned = True
            self._level = level
            self.reset()
        board = self._board(obs)
        if board is None:
            return []
        simple, six = availability(obs)
        if not six or not {1, 2, 3, 4, _TURN}.issubset(set(simple)):
            return []

        if self._pending is not None:
            self._absorb_click(board)
        elif self._turning:
            self._absorb_turn(board)
        if self._dead:
            return []

        if not self._plan:
            step = self._discover(board)
            if step is not None or self._dead:
                return step or []
            if not self._finalise():
                self._dead = True
                return []
            self._layouts = self._solve()
            if not self._attempt():
                self._dead = True
                return []
        return self._execute(board)

    def _attempt(self) -> bool:
        """Take the next-cheapest tiling and cost it from wherever the pieces are NOW.

        ⛔ One tiling is not one answer. MEASURED on the 13-piece level: half of the tilings that
        satisfy the frame-visible test are still refused, because the two kinds of marker are
        painted the same colour and a seam can pair the wrong two. So the tool executes the
        cheapest, and on a board that does not advance it re-costs the next one from the
        arrangement it just built rather than reading the level again.
        """
        while self._layouts:
            got = self._cost(self._layouts.pop(0))
            if got is not None and got[1]:
                self._plan = got[1]
                self._done = set()
                return True
        return False

    # -- the two loops -------------------------------------------------------

    def _discover(self, board: np.ndarray) -> list[Step] | None:
        """One action of reading: walk the selected piece's orbit, else reach for a new piece."""
        if not self._forms:
            if not self._earned and not self._signature(board):
                # A finished board is one interlocked piece and the next level only appears after
                # another action, so a miss here is a wait — not a verdict.
                self._idle += 1
                if self._idle > _MAX_IDLE:
                    self._dead = True
                return []
            self._idle = 0
            # Something already holds the selection; the turn is what says which piece it is.
            self._turning = True
            self._prev = board.copy()
            return [(_TURN, None)]
        open_orbit = next((i for i, done in enumerate(self._closed) if not done), None)
        if open_orbit is not None:
            steps: list[Step] = []
            if self._selected != open_orbit:
                handle = self._handle(open_orbit)
                if handle is None:
                    self._dead = True
                    return []
                steps.append(self._click(handle))
                self._selected = open_orbit
            self._turning = True
            self._prev = board.copy()
            return [*steps, (_TURN, None)]
        spare = self._unseen(board)
        if spare is not None:
            self._pending = spare
            self._prev = board.copy()
            return [self._click(spare)]
        return None

    def _execute(self, board: np.ndarray) -> list[Step]:
        """Hand back a NON-EMPTY move list for as long as the plan still owes work.

        ⛔ An empty proposal is not free — it is DESTRUCTIVE. MEASURED in the real harness on the
        game this was built for: a piece that is already standing on its target owes no slide, so
        the per-piece call returned `[]`; the loop answers an empty proposal by substituting a
        probe action, and on this board the first simple action SLIDES the selected piece. The
        plan's own arrangement was pushed one cell off by the harness, the level then refused,
        and the tool spent the rest of the budget re-costing tilings against a board that no
        longer matched its bookkeeping — one level in the harness against six in isolation.
        So a piece that owes nothing is skipped HERE, in the same call, and the tool never hands
        the loop a turn it did not ask for.
        """
        steps: list[Step] = []
        # Each pass retires one piece from the plan, so this cannot outrun the plan's length.
        for _ in range(len(self._plan) + 2):
            steps = self._next_moves(board)
            if steps or self._dead:
                break
        if steps or self._dead:
            return steps
        # Nothing left to move and the level has not turned over: idle on a cell no piece owns,
        # which selects nothing and moves nothing, rather than letting the loop pick for us.
        return [self._click(self._vacant())]

    def _vacant(self) -> Cell:
        """A coarse cell no piece stands on — clicking it is the cheapest action that is inert."""
        taken = self._taken()
        for y in range(self._cells):
            for x in range(self._cells):
                if (x, y) not in taken:
                    return (x, y)
        return (0, 0)

    def _next_moves(self, board: np.ndarray) -> list[Step]:
        """One piece per call: first its form and its selection, then its slide."""
        if self._sliding is not None:
            idx, form, tgt = self._sliding
            self._sliding = None
            if not self._reseat_from(board, idx):
                self._dead = True
                return []
            return self._slide(idx, tgt)

        # ⛔ Order the moves by what stays CLICKABLE, not by the order the solver produced.
        # MEASURED: a piece parked on top of the next one leaves it with no cell of its own, and
        # a click there selects the wrong piece — the plan is then executed against fiction.
        best: tuple[int, int, tuple[int, int, Cell]] | None = None
        for order, (idx, form, tgt) in enumerate(self._plan):
            if idx in self._done or self._handle(idx) is None:
                continue
            art = self._forms[idx][form]
            landing = _footprint(art, tgt)
            covered = set(landing)
            for j in self._done:
                if j != idx:
                    covered |= self._cells_of(j)
            stranded = sum(
                1
                for j in range(len(self._forms))
                if j not in self._done and j != idx and not self._cells_of(j) - covered
            )
            if best is None or (stranded, order) < (best[0], best[1]):
                best = (stranded, order, (idx, form, tgt))
        if best is None:
            if all(idx in self._done for idx, _, _ in self._plan) and self._attempt():
                return self._next_moves(board)
            self._dead = True
            return []

        _, _, (idx, form, tgt) = best
        self._done.add(idx)
        steps: list[Step] = []
        if self._selected != idx:
            handle = self._handle(idx)
            if handle is None:
                self._dead = True
                return []
            steps.append(self._click(handle))
            self._selected = idx
        turns = self._presses(idx, form)
        if turns:
            steps.extend([(_TURN, None)] * turns)
            self._cur[idx] = form
            self._sliding = (idx, form, tgt)
            return steps
        self._cur[idx] = form
        return steps + self._slide(idx, tgt)

    def _slide(self, idx: int, tgt: Cell) -> list[Step]:
        cx, cy = self._at[idx]
        self._at[idx] = tgt
        return (
            [(_SLIDE[(1 if tgt[0] > cx else -1, 0)], None)] * abs(tgt[0] - cx)
            + [(_SLIDE[(0, 1 if tgt[1] > cy else -1)], None)] * abs(tgt[1] - cy)
        )
