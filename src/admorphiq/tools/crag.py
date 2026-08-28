"""Crag tool — a lateral faller whose route is planned over a STITCHED WORLD and a GRAVITY AXIS
that the board itself can reverse.

Recovered from frames alone. The mechanic, in the order the tool has to derive it:

  * the board is a lattice of equal square cells, one glyph per cell, and the camera shows a
    WINDOW of about ten rows onto a board three to four times that deep;
  * control is LATERAL ONLY — exactly two of the four plain actions exist. There is no command
    for the gravity axis, which is what makes this a faller and not a maze;
  * a lateral action moves the body one cell sideways and it then SETTLES along the gravity axis
    until a cell it cannot enter stops it. A step into a cell it cannot enter costs the action
    and moves nothing;
  * a click EDITS one cell. Some kinds vanish, some swap to a partner, and one kind REVERSES
    GRAVITY. Which is which is measured;
  * the level ends when the body enters — or comes to rest on — the board's singular cell;
  * some cells KILL whatever comes to rest on them and the only notice is a restart.

⛔ THE THREE FACTS THIS TOOL IS BUILT ON, each of which a viewport-planner cannot use.

1. **A CLICK MOVES THE BODY ONLY WHEN IT IS AIMED AT THE BODY'S SUPPORT — except the gravity
   kind, which acts from anywhere on screen.** That asymmetry is the whole search. It says the
   click candidates worth expanding are four: the cell holding the body up, the two cells beside
   it, and every gravity switch currently on screen. Offering every editable cell instead makes
   the frontier the size of the window and the searcher never gets past two clicks deep — and
   two is not enough. Measured statically against this family's fourth board: the shortest route
   to its exit is nineteen actions and SIX of them are clicks, four of those gravity reversals.

2. **THE GRAVITY AXIS IS PART OF THE STATE, NOT A FIELD.** A route can be planned half under one
   axis and half under the other, and the exit of the fourth board sits where "descend" points
   exactly the wrong way. A search whose state is (cell) rather than (cell, axis, edits) cannot
   express the route at all, whatever budget it is given.

3. **A DEATH IS NOT A LOST BOARD.** The engine restarts the level and hands back a fresh action
   budget; the terrain is identical. So the world map and the vocabulary SURVIVE the restart and
   only the edits are rolled back. The board is learned across attempts and the route is planned
   once it is knowable, rather than being re-guessed from the opening window every time.

⛔ Nothing here is written down: not the cell size, not the lattice origin, not which way gravity
points, not which glyph is floor, exit, switch or spike. A constant recovered by hand does not
transfer to a board whose source we will never see.

Four derivations that are easy to get wrong on this family:

  * **the observation is an ANIMATION, shipped as layers, and layer zero is the board BEFORE the
    action.** Only the LAST layer is the settled board. This tool reads the stack itself and
    deliberately does not ask for the shared reader to change: switching that to the last layer
    was measured across all twenty-five games and made the card worse (0.6733 -> 0.6525). It is
    settled-last HERE. See `.wiki/wiki/concepts/frame_layer_timeline.md`.
  * **the lattice ORIGIN moves when gravity reverses.** The camera re-centres the body at a
    different screen row for each axis, and that row is not a multiple of the pitch, so the whole
    grid shifts by a few pixels. Fitting the origin once and keeping it reads every later frame
    half a cell out.
  * **"empty is the commonest cell" is false** on a window filled with rock. Air is taken from
    the cell the body VACATES, which is ground truth.
  * **a click is typed in SCREEN pixels**, so a cell can only be edited while it is on screen.
    The search carries that restriction or it returns routes whose middle step cannot be typed.
"""

from __future__ import annotations

from collections import Counter, deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, has_frame, levels_completed, state_name

__all__ = ["CragTool", "settled_layer", "fit_lattice", "read_lattice"]

Cell = tuple[int, int]
Sig = tuple[tuple[int, int], ...]
Board = dict[Cell, Sig]
# One leg of a planned route: the action to type, what the tool expects to see afterwards, and
# the reading that justified it — carried because a death is only interpretable against the
# expectation the fatal action was taken under.
Leg = tuple[Step, Cell, int, str, "Sig | None"]

# A faller has no command for its gravity axis. Exactly two lateral moves is the signature.
_LATERAL = 2
# Fewer whole cells than this is furniture, not a board.
_MIN_CELLS = 24
# Below five the sampled core is 3x3, and a 3x3 patch of anything is flat, so every coarser
# lattice loses to the finest on offer.
_PITCH_LO = 5
_PITCH_HI = 10
# Terrain agreement before a window is accepted as THIS board, scrolled.
_ALIGN_FIT = 0.82
_ALIGN_MIN = 16
# Clicks allowed inside one searched route. Six, because the shortest route to the fourth
# board's exit needs six and a cap of two cannot express it. The frontier stays small because
# the candidate sites are four plus the switches on screen, not the whole window.
_MAX_EDITS = 6
_MAX_EXPAND = 40000
# Clicks a single EXPLORING route may compose. Two, not six: exploration re-plans after every
# action, so depth buys nothing there, while the frontier it costs is the whole difference
# between a search that returns and one that does not. Three was measured and is slightly worse
# (the second board went 254 actions -> 261) with no level gained.
_EXPLORE_EDITS = 2
# Proposals that change nothing before the tool hands the board back.
_GIVE_UP = 16
# Handovers before it stops bidding on this game at all.
_MUTE_AFTER = 3


def settled_layer(obs: Any) -> np.ndarray:
    """The board once the move has finished playing — the LAST layer of the observation."""
    arr = np.asarray(getattr(obs, "frame", None))
    while arr.ndim > 2:
        arr = arr[-1]
    return arr.astype(np.int64)


def _cores(g: np.ndarray, p: int, oy: int, ox: int) -> list[tuple[Cell, np.ndarray]]:
    """Every whole cell's core, inset a pixel so a neighbour's bleed cannot reach it.

    Glyphs are drawn one pixel wider than the pitch here, so adjacent cells share a boundary
    line and whichever was drawn last owns it. The final pixel row is never reached, which also
    keeps an edge-pinned action counter out of the terrain.
    """
    h, w = g.shape
    out: list[tuple[Cell, np.ndarray]] = []
    for r, y in enumerate(range(oy, h - p, p)):
        for c, x in enumerate(range(ox, w - p, p)):
            out.append(((r, c), g[y + 1 : y + p - 1, x + 1 : x + p - 1]))
    return out


def _sig(core: np.ndarray) -> Sig:
    """A cell's identity: the colour histogram of its core, order-free."""
    return tuple(sorted(Counter(int(v) for v in core.ravel()).items()))


def _alphabet(g: np.ndarray, p: int, oy: int, ox: int) -> tuple[int, float]:
    """(distinct kinds, fraction of cells that are one flat colour) at this lattice."""
    cs = _cores(g, p, oy, ox)
    if len(cs) < _MIN_CELLS:
        return 10**6, 0.0
    kinds = len({_sig(k) for _, k in cs})
    flat = sum(1 for _, k in cs if k.size and int(k.min()) == int(k.max())) / len(cs)
    return kinds, flat


def _best_origin(g: np.ndarray, p: int) -> tuple[int, int] | None:
    """The origin at a known pitch: the one needing the FEWEST distinct kinds.

    ⛔ Not the flattest. Flatness picks an origin a pixel or two off the sprite grid, where every
    cell also catches a column of its neighbour — enough to keep rock flat, and enough to split
    one glyph into three lookalikes that no learning can join up.
    """
    best: tuple[int, float, int, int] | None = None
    for oy in range(p):
        for ox in range(p):
            kinds, flat = _alphabet(g, p, oy, ox)
            if kinds >= 10**6:
                continue
            if best is None or (kinds, -flat) < (best[0], -best[1]):
                best = (kinds, flat, oy, ox)
    return (best[2], best[3]) if best else None


def fit_lattice(g: np.ndarray) -> tuple[int, int, int] | None:
    """Pitch and origin of the cell grid, or None when the frame is not drawn on one.

    The PITCH is the COARSEST step that still reads the frame as flat tiles — a plain argmax
    drifts to the finest step on offer, because a small enough core is flat whatever it samples.
    """
    flats = []
    for p in range(_PITCH_LO, _PITCH_HI + 1):
        best = max((_alphabet(g, p, oy, ox)[1] for oy in range(p) for ox in range(p)), default=0.0)
        flats.append((p, best))
    top = max(f for _, f in flats)
    if top <= 0.0:
        return None
    pitch = max(p for p, f in flats if f >= 0.9 * top)
    origin = _best_origin(g, pitch)
    return None if origin is None else (pitch, origin[0], origin[1])


def read_lattice(g: np.ndarray, p: int, oy: int, ox: int) -> tuple[Board, dict[Cell, frozenset[int]]]:
    """Screen cell -> signature, and screen cell -> the bare set of colours it carries."""
    board: Board = {}
    inks: dict[Cell, frozenset[int]] = {}
    for cell, core in _cores(g, p, oy, ox):
        if not core.size:
            continue
        board[cell] = _sig(core)
        inks[cell] = frozenset(int(v) for v in core.ravel())
    return board, inks


def _singular(inks: dict[Cell, frozenset[int]]) -> dict[Cell, frozenset[int]]:
    """Cell -> the colours no other cell on screen carries. The body and the exit are two."""
    owners: dict[int, set[Cell]] = {}
    for cell, ink in inks.items():
        for col in ink:
            owners.setdefault(col, set()).add(cell)
    out: dict[Cell, set[int]] = {}
    for col, cells in owners.items():
        if len(cells) == 1:
            out.setdefault(next(iter(cells)), set()).add(col)
    return {c: frozenset(v) for c, v in out.items()}


class CragTool:
    """Harness tool wrapping the reversible-gravity faller on a stitched world map."""

    name = "crag"

    def __init__(self) -> None:
        # --- vocabulary: learned once and carried across boards AND across deaths, because the
        # rock of the first board is the rock of the ninth and paying for it twice is waste.
        self._air: Sig | None = None
        self._open: set[Sig] = set()
        self._solid: set[Sig] = set()
        self._lethal: set[Sig] = set()
        self._safe: set[Sig] = set()          # has held the body without killing it
        self._vanish: set[Sig] = set()        # a click empties this cell
        self._swap: dict[Sig, Sig] = {}       # a click turns this cell into that one
        self._flip: set[Sig] = set()          # a click reverses the gravity axis
        self._inert: set[Sig] = set()         # a click does nothing here
        self._probed: set[Sig] = set()        # a click on this kind has been paid for once
        self._exit: Sig | None = None
        self._dud: set[Sig] = set()           # looked singular, was decoration
        self._aimed: Sig | None = None
        self._aim: Cell | None = None
        self._body_ink: frozenset[int] = frozenset()
        self._pitch = 0
        self._left = 0
        self._right = 0
        self._bands: dict[int, tuple[int, int]] = {}
        self._refuted = False
        self._mute = 0

        # --- per-board, surviving a death but not a level
        self._world: Board = {}
        self._origin = 0
        self._rows = 0
        self._cols = 0
        self._opening: Board | None = None
        self._home: Cell | None = None
        self._volatile: set[Sig] = set()
        self._seen_rows: set[int] = set()
        # (place, axis) -> action struck off there: it killed, or it repeatedly did something
        # other than what the model said it would.
        self._deadly: set[tuple[tuple[Cell, int], Step]] = set()
        self._missed: dict[tuple[tuple[Cell, int], Step], int] = {}
        # Resting places from which nothing at all was reachable. Survives a restart, because the
        # terrain does.
        self._pocket: set[tuple[Cell, int]] = set()
        self._known = 0
        self._grade = 0
        # This board has been seen to restart itself, so running the clock out is a way back to
        # the opening rather than a way to waste the rest of the game.
        self._clocked = False
        self._waiting = 0

        # --- per-attempt, rolled back by a death
        self._edits: dict[Cell, Sig] = {}     # cell -> what it was before we clicked it
        self._at: Cell | None = None
        self._gdir = 0
        self._visited: set[tuple[Cell, int]] = set()
        self._plan: list[Leg] = []
        self._last: dict[str, Any] | None = None
        self._expect: Cell | None = None
        self._took: tuple[tuple[Cell, int], Step] | None = None
        self._bump = 1
        self._oy = 0
        self._ox = 0
        self._idle = 0
        self._level: int | None = None
        self._note = ""

    # ------------------------------------------------------------------- read

    def _readings(self, g: np.ndarray) -> list[tuple[int, int, Board, dict[Cell, frozenset[int]], Cell]]:
        """Every plausible way to lay the cell grid over this frame, body included.

        ⛔ The lattice ORIGIN and the SCROLL are the same unknown and must be solved together.
        The camera does not move in whole cells — it re-centres the body at a different screen
        row for each gravity axis, and that row is not a multiple of the pitch — so the pixel
        origin moves under the tool's feet. Choosing it per frame by "fewest distinct kinds"
        looks principled and is not: on a window that has just filled with rock, two origins tie
        and the tie flips. Measured on the first board, the reading jumped a few pixels between
        two consecutive frames, every signature in the window changed at once, alignment then
        refused the frame as a different board, and the tool went blind eight actions into the
        level — twice, and then again on every restart.

        So every origin is offered, and the one that AGREES with the map is the one taken. The
        pitch is not re-derived: it is a property of the board's art, not of the window.
        """
        if not self._pitch:
            got = fit_lattice(g)
            if got is None:
                return []
            self._pitch, self._oy, self._ox = got
        p = self._pitch
        fitted = _best_origin(g, p)
        oxs = {self._ox} | ({fitted[1]} if fitted else set())
        out: list[tuple[int, int, Board, dict[Cell, frozenset[int]], Cell]] = []
        for ox in sorted(oxs):
            for oy in range(p):
                board, inks = read_lattice(g, p, oy, ox)
                if len(board) < _MIN_CELLS:
                    continue
                self._rows = max(r for r, _ in board) + 1
                self._cols = max(c for _, c in board) + 1
                body = self._body(board, inks)
                if body is None:
                    continue
                out.append((oy, ox, board, inks, body))
        if not out and fitted:
            board, inks = read_lattice(g, p, fitted[0], fitted[1])
            body = self._body(board, inks)
            if body is not None:
                out.append((fitted[0], fitted[1], board, inks, body))
        return out

    def _body(self, board: Board, inks: dict[Cell, frozenset[int]]) -> Cell | None:
        """The singular cell that moves, tracked by its rare colours once they are known.

        ⛔ Membership is not identity. One of the body's colours is shared with a hazard on the
        later boards, so "any cell carrying one of my colours" matches the body AND every spike
        on screen. The body is the BEST match: most colours in common, then nearest to where it
        was, because a camera that follows it keeps it in nearly the same place.
        """
        if self._body_ink:
            hits = [(len(ink & self._body_ink), c) for c, ink in inks.items() if ink & self._body_ink]
            if not hits:
                return None
            near = (0, 0) if self._at is None else (self._at[0] - self._origin, self._at[1])
            hits.sort(key=lambda h: (-h[0], abs(h[1][0] - near[0]) + abs(h[1][1] - near[1])))
            return hits[0][1]
        cand = sorted(_singular(inks))
        if not cand:
            return None
        mid = ((self._rows - 1) / 2, (self._cols - 1) / 2)
        return min(cand, key=lambda c: abs(c[0] - mid[0]) + abs(c[1] - mid[1]))

    # --------------------------------------------------------------- stitching

    def _stitch(self, readings: list[tuple[int, int, Board, dict[Cell, frozenset[int]], Cell]],
                allow: int | None) -> tuple[str, Board, dict[Cell, frozenset[int]], Cell]:
        """Fold this window into the world map. Returns 'grow', 'home' or 'lost'.

        The camera follows the body and only moves when it falls, so a fall and a landslide are
        the same picture; the shift has to be recovered by matching terrain.

        ⛔ AGREEMENT ALONE CANNOT NAME THE SHIFT, and this is the expensive lesson of the file. A
        shaft is long uniform runs of rock and air, so a window laid fifteen rows off its true
        home still agrees with nine cells in ten. Measured on the first board: one such shift was
        accepted, the body appeared to have travelled fifteen rows AGAINST gravity, the tool
        concluded the block it had just clicked reverses gravity — and carried that invention
        into every later board, where it clicked the same kind twice and died in three actions,
        forever. PHYSICS settles it instead. `allow` says which way the body may have moved, in
        gravity units: +1 with the axis, -1 against it, 0 not at all, None unknown. A lateral
        step can only settle ALONG the axis; a click that is not on the body's support cannot
        move it at all; only the gravity kind moves it the other way.

        `home` means the window is the board's opening again, which on this family means one
        thing — the body died and the engine restarted the level with a fresh action budget. That
        is not a lost board: the terrain is unchanged, so the map is kept and only OUR edits are
        rolled back.
        """
        first = readings[0]
        if not self._world:
            oy, ox, board, inks, body = first
            self._shape(board)
            self._oy, self._ox, self._origin = oy, ox, 0
            self._home = body
            self._opening = {c: sg for c, sg in board.items() if c != body}
            self._absorb(board, body, 0)
            return "grow", board, inks, body
        for oy, ox, board, inks, body in readings:
            if self._restarted(board, body):
                self._shape(board)
                self._oy, self._ox, self._origin = oy, ox, 0
                self._clocked = True
                self._waiting = 0
                self._rollback()
                self._absorb(board, body, 0)
                return "home", board, inks, body
        best: tuple[tuple[float, int, int, int, int], int, int, int] | None = None
        lo = min(r for r, _ in self._world)
        hi = max(r for r, _ in self._world)
        for idx, (oy, ox, board, inks, body) in enumerate(readings):
            for shift in range(lo - self._rows, hi + self._rows + 1):
                if not self._admissible(body[0] + shift, allow):
                    continue
                agree = total = 0
                for (r, c), sg in board.items():
                    if (r, c) == body:
                        continue
                    was = self._world.get((r + shift, c))
                    if was is None or was in self._volatile or sg in self._volatile:
                        continue
                    total += 1
                    agree += was == sg
                if total < _ALIGN_MIN:
                    continue
                score = agree / total
                # Among readings that agree equally, the one already in use wins: the pixel
                # origin only moves when the camera does, so continuity is evidence.
                stale = 0 if (oy, ox) == (self._oy, self._ox) else 1
                fits = self._expect is not None and body[0] + shift != self._expect[0]
                cand = (round(score, 3), -stale, -int(fits), -abs(shift - self._origin), -idx)
                if best is None or cand > best[0]:
                    best = (cand, shift, idx, 0)
        if best is None or best[0][0] < _ALIGN_FIT:
            return "lost", first[2], first[3], first[4]
        shift, idx = best[1], best[2]
        oy, ox, board, inks, body = readings[idx]
        self._shape(board)
        self._oy, self._ox, self._origin = oy, ox, shift
        self._absorb(board, body, shift)
        return "grow", board, inks, body

    def _allow(self) -> int | None:
        """Which way the body may have moved since the last frame, in gravity units.

        This is the physics the alignment is checked against, and every branch is a fact about
        the mechanic rather than a guess: a lateral step settles ALONG the axis or not at all; a
        click that is not aimed at the body's support cannot move it, unless it is the gravity
        kind, which can only move it the other way; and a click on the support with an unmeasured
        glyph could be either, so it constrains nothing and says so.
        """
        last = self._last
        if last is None or self._gdir == 0:
            return None
        if last["kind"] == "walk":
            return 1
        was = last.get("was")
        if was in self._flip:
            return -1
        known = was is not None and (was in self._vanish or was in self._swap or was in self._inert)
        if known:
            return 1 if last.get("on_support") else 0
        return None if last.get("on_support") else -1

    def _admissible(self, row: int, allow: int | None) -> bool:
        """Could the body have arrived at this world row, given what was just done to it?"""
        if allow is None or self._at is None or self._gdir == 0:
            return True
        delta = (row - self._at[0]) * self._gdir
        if allow == 0:
            return delta == 0
        return delta >= 0 if allow > 0 else delta <= 0

    def _restarted(self, board: Board, body: Cell) -> bool:
        """Did the body die, so the engine put the level back to its opening?

        The picture is compared exactly — a restart restores terrain, edits and body together,
        so the opening window comes back cell for cell. ⛔ But the picture ALONE is not the test,
        and that mistake cost the first board: walking one step back to where the level started
        reproduces the opening exactly, the tool read its own second action as a death, filed
        that action as fatal, and had walled itself in by the fifth. A restart is a picture the
        last action could NOT have produced — the body was somewhere else and the route did not
        say it was coming here.
        """
        if self._opening is None or self._home is None or body != self._home:
            return False
        if self._at is None or self._at == self._home or self._expect == self._home:
            return False
        return all(sig == self._opening.get(cell) for cell, sig in board.items() if cell != body)

    def _shape(self, board: Board) -> None:
        """Adopt the CHOSEN reading's own shape.

        ⛔ Not the last one tried. `_readings` offers a lattice per candidate origin and sets the
        shape as it goes so the body finder has something to work with, which leaves the shape at
        whatever the final candidate happened to be — and the candidates do not all have the same
        number of whole rows, because where the origin falls decides whether the last row fits.
        Everything downstream is measured in rows: how far the window reaches, how far a shift may
        be searched, whether a cell can be clicked. Measured on the fourth board, the reach
        AGAINST the axis came out one row short, and the reversal that opens the board sits
        exactly at that row.
        """
        self._rows = max(r for r, _ in board) + 1
        self._cols = max(c for _, c in board) + 1

    def _absorb(self, board: Board, body: Cell, shift: int) -> None:
        """Write the window into the map, and note any cell that changes on its own.

        A cell that changes with no click on it is something the board animates — a hazard that
        sweeps the shaft, a counter drawn onto the terrain. A whole BAND has to move together
        before the kinds involved are filed that way: one disagreeing cell is a misread, a row of
        them is a moving thing. Being filed does not make a kind passable; only the body having
        gone through it does that.
        """
        clashes: list[tuple[Sig, Sig]] = []
        for (r, c), sig in board.items():
            key = (r + shift, c)
            if (r, c) == body:
                if self._air is not None:
                    self._world[key] = self._air
                continue
            was = self._world.get(key)
            if was is not None and was != sig and key not in self._edits:
                clashes.append((was, sig))
            self._world[key] = sig
            self._seen_rows.add(key[0])
        if len(clashes) >= 3:
            # ⛔ Only the glyph that ARRIVED is filed, and never air. Filing both sides of every
            # clash files the background the mover moved ACROSS, and air is the commonest cell on
            # the board: once it is volatile the alignment has almost nothing left to compare, no
            # shift clears the overlap floor, and the tool declares every later frame a different
            # board. Measured on the first level, the frame the hazard band first came into view.
            for _, sig in clashes:
                if sig != self._air:
                    self._volatile.add(sig)
        self._at = (body[0] + shift, body[1])

    def _rollback(self) -> None:
        """Undo our own edits: a restart restores the terrain, so the map must too.

        ⛔ Where the body has been IS rolled back, and that is measured rather than reasoned. The
        frontier is the set of places not yet stood in, so keeping it across a restart should let
        the next attempt go straight to where the last one stopped — and it takes the tool from
        three levels to one. What the run actually needs after a death is to walk its way back
        out, learning the board again as it goes: the route to the frontier is only knowable in
        terms of ground the tool is willing to re-cross.
        """
        for cell, was in self._edits.items():
            self._world[cell] = was
        self._edits = {}
        self._visited = set()
        self._plan = []
        self._expect = None
        self._took = None
        self._gdir = 0

    # ------------------------------------------------------------- vocabulary

    def _is_open(self, sig: Sig | None) -> bool:
        return sig is not None and (sig == self._air or sig in self._open)

    def _learn_move(self, before: Cell, dc: int, after: Cell, into: Sig | None) -> None:
        """What one lateral step admitted about the board — an exact reading, not a guess.

        The cell stepped into was passable, every cell fallen through was passable, and the cell
        just VACATED was passable, which is where air comes from with no appeal to which glyph
        happens to be commonest.

        ⛔ `into` is the glyph that WAS in the target cell, carried from before the action, and it
        has to be: once the body is standing there the map holds the body's own cell as air, so
        reading the target after the fact learns "air is passable" and nothing else. That is why
        a block a click had just turned into a doorway could never be filed passable — the tool
        walked through it, learned nothing, and on the next attempt refused to walk through it
        again. Measured on the third board, whose opening pocket has exactly one such doorway.
        """
        target = (before[0], before[1] + dc)
        tsig = into if into is not None else self._world.get(target)
        if after == before:
            if tsig is not None and not self._is_open(tsig):
                self._solid.add(tsig)
            return
        if tsig is not None:
            self._open.add(tsig)
            self._solid.discard(tsig)
        if self._air is None:
            vacated = self._world.get(before)
            if vacated is not None:
                self._air = vacated
                self._open.add(vacated)
        r = target[0]
        while r != after[0]:
            nxt = r + (1 if after[0] > r else -1)
            if nxt != after[0]:
                sig = self._world.get((nxt, target[1]))
                if sig is not None:
                    self._open.add(sig)
                    self._solid.discard(sig)
            r = nxt

    def _learn_support(self) -> None:
        """Whatever holds the body up is solid and — having held it — is not a hazard.

        ⛔ Only once the axis is known. It used to run inside the step-learner, which fires on the
        FIRST move of a board, before the axis has been read; with no axis there is no underfoot,
        nothing was ever filed solid, and every fall ran off the end of what the tool knew.
        """
        if not self._gdir or self._at is None:
            return
        sig = self._world.get((self._at[0] + self._gdir, self._at[1]))
        if sig is not None and not self._is_open(sig):
            self._solid.add(sig)
            self._safe.add(sig)

    def _learn_click(self, cell: Cell, was: Sig, flipped: bool) -> None:
        now = self._world.get(cell)
        if flipped:
            self._flip.add(was)
            self._probed.add(was)
            return
        self._probed.add(was)
        if now is None or now == was:
            self._inert.add(was)
            return
        if self._air is not None and now == self._air:
            self._vanish.add(was)
        else:
            self._swap[was] = now

    def _learn_death(self, last: dict[str, Any] | None) -> None:
        """One death, read as narrowly as the evidence allows — and always narrowed to SOMETHING.

        ⛔ A hazard is never inferred from an ordinary landing. The first boards of this family
        run a hazard down the shaft on a schedule, and a body killed while standing on a floor it
        had already stood on is not evidence about the floor. Only a landing the tool could not
        account for — something DRAWN and unexplained — names a kind lethal.

        ⛔ But a death that names nothing must still cost the action that caused it, or the tool
        repeats it. Measured: the same three actions, then a restart, then the same three, for
        the whole budget. So the exact (place, axis, action) is struck off even when the reason
        cannot be pinned on a glyph — which is also the honest reading when the killer is a clock
        rather than a tile.
        """
        if not last:
            return
        if last.get("key") is not None:
            self._deadly.add(last["key"])
        blind = last.get("blind")
        if blind is None or blind in self._safe or self._is_open(blind):
            return
        self._lethal.add(blind)
        self._solid.discard(blind)

    # ------------------------------------------------------------------ physics

    def _settle(self, cells: Board, start: Cell, gdir: int,
                targets: set[Cell]) -> tuple[str, Cell, Sig | None]:
        """Slide from `start` along `gdir` -> (verdict, resting cell, what is underfoot).

        `edge` is running off the end of the MAP — ordinary unexplored shaft, nothing drawn down
        there yet. `blind` is stopping on something that IS drawn and cannot be accounted for.
        ⛔ Keeping those apart is worth several restarts a board: by the second level rock, air
        and the breakable block have all been named by walking on them, so a cell still drawn in
        something else is the board saying "this one is different", and that is usually the thing
        that kills. Unseen ground is the better bet.
        """
        r, c = start
        for _ in range(self._rows * 8 + 8):
            nxt = (r + gdir, c)
            if nxt in targets:
                return "win", nxt, None
            sig = cells.get(nxt)
            if sig is None:
                return "edge", (r, c), None
            if self._is_open(sig):
                r = nxt[0]
                continue
            if sig in self._lethal:
                return "dead", (r, c), sig
            if sig in self._solid:
                return "rest", (r, c), sig
            return "blind", (r, c), sig
        return "rest", (r, c), None

    def _walk(self, cells: Board, at: Cell, gdir: int, dc: int,
              targets: set[Cell]) -> tuple[str, Cell, Sig | None]:
        """One lateral action -> verdict, resting cell, support.

        A step into a cell the body cannot enter costs the action and moves nothing, which is why
        it is returned as a rest AT THE SAME CELL rather than dropped: the searcher has to know
        the action is legal and useless, or it plans through a wall and then believes it is
        somewhere it is not.
        """
        target = (at[0], at[1] + dc)
        if target in targets:
            return "win", target, None
        sig = cells.get(target)
        if sig is None:
            return "rest", at, None
        if not self._is_open(sig):
            # ⛔ Unexplained is not the same as solid, and the difference is the cheapest
            # experiment on this family. A sideways step into a glyph nothing is known about
            # costs one action and settles it either way — the body moves, so the glyph is
            # passable, or it does not, so the glyph is wall. Without that, a kind that a click
            # turns into ANOTHER unexplained kind can never become passable: the tool clicks the
            # block beside it, sees a glyph it has never walked through, calls it wall, and paces
            # the same three cells for the rest of the level. Measured on the third board, whose
            # opening pocket is closed by exactly such a block.
            if sig in self._solid or sig in self._lethal:
                return "rest", at, sig
            return "test", at, sig
        return self._settle(cells, target, gdir, targets)

    def _click(self, cells: Board, at: Cell, gdir: int, cell: Cell,
               targets: set[Cell]) -> tuple[Board, int, str, Cell, Sig | None]:
        """The board, the axis, the body and its support after clicking `cell`.

        ⛔ The asymmetry that shapes the whole search: a click that is NOT the gravity kind moves
        the body only when it is aimed at the cell holding it up. Anywhere else it is a pure
        terrain edit and the body stays put. The gravity kind acts from anywhere on screen and
        re-settles the body under the reversed axis.
        """
        sig = cells[cell]
        nxt = dict(cells)
        if sig in self._flip:
            nxt[cell] = self._air if self._air is not None else sig
            g2 = -gdir
            ahead = nxt.get((at[0] + g2, at[1]))
            if self._is_open(ahead):
                verdict, rest, under = self._settle(nxt, at, g2, targets)
                return nxt, g2, verdict, rest, under
            # ⛔ NOT claimed as a win even when the exit is the cell the reversed axis points at.
            # The reversal re-settles the body by a different route than a step does, and it is
            # the one path that does not test the cell it starts from. Guessing generously here
            # returns routes that end one action short of the exit.
            return nxt, g2, "rest", at, ahead
        nxt[cell] = self._air if sig in self._vanish else self._swap[sig]  # type: ignore[assignment]
        if cell == (at[0] + gdir, at[1]):
            verdict, rest, under = self._settle(nxt, at, gdir, targets)
            return nxt, gdir, verdict, rest, under
        return nxt, gdir, "rest", at, cells.get((at[0] + gdir, at[1]))

    # -------------------------------------------------------------------- sites

    def _band(self, gdir: int) -> tuple[int, int]:
        """(rows visible along the axis, rows visible against it) from a settled body.

        Measured per axis rather than assumed symmetric: the camera puts the body off-centre so
        it can see where it is falling, and reversing the axis moves it to a different screen
        row. An axis never yet seen is given the tighter of the two known bands, because a click
        planned onto a cell that turns out to be off screen is an action spent on nothing.
        """
        known = self._bands.get(gdir)
        if known:
            return known
        if self._bands:
            other = next(iter(self._bands.values()))
            tight = max(0, min(other) - 1)
            return tight, tight
        return 0, 0

    def _visible(self, at: Cell, cell: Cell, gdir: int) -> bool:
        ahead, behind = self._band(gdir)
        delta = (cell[0] - at[0]) * gdir
        return -behind <= delta <= ahead and 0 <= cell[1] < self._cols

    def _sites(self, cells: Board, at: Cell, gdir: int) -> list[Cell]:
        """The click candidates worth expanding, and no others.

        Five local cells plus every gravity switch on screen. ⛔ The local five are exactly the
        ones a click can do anything WITH: the support (breaking it drops the body), the two
        beside it (opening a wall to walk through, or closing air to walk on), and the two that
        would hold the body up one step away (building the ledge before stepping onto it). Every
        other editable cell on screen can be reached by walking next to it first, so nothing is
        lost — while offering them all makes the frontier the size of the window and no route six
        clicks deep is ever found.

        ⛔ MEASURED, and it is the reason the list is not "everything within reach": adding just
        ONE more candidate — the cell directly overhead, which a reversed axis turns into floor —
        took the tool from three levels to one. It is a defensible cell to click and it still
        multiplies the frontier by its own branching factor at every state, so the searcher runs
        out of expansions before it reaches the route that was already working.
        """
        out: list[Cell] = []
        for cell in ((at[0] + gdir, at[1]), (at[0], at[1] - 1), (at[0], at[1] + 1),
                     (at[0] + gdir, at[1] - 1), (at[0] + gdir, at[1] + 1)):
            sig = cells.get(cell)
            if sig is not None and (sig in self._vanish or sig in self._swap):
                out.append(cell)
        for cell, sig in cells.items():
            if sig in self._flip and self._visible(at, cell, gdir):
                out.append(cell)
        return out

    def _pixel(self, cell: Cell) -> tuple[int, int] | None:
        """Where to click a world cell, in screen pixels, or None when it is off screen."""
        p = self._pitch
        row = cell[0] - self._origin
        if not p or not (0 <= row < self._rows) or not (0 <= cell[1] < self._cols):
            return None
        x = self._ox + cell[1] * p + p // 2
        y = self._oy + row * p + p // 2
        if not (0 <= x < 64 and 0 <= y < 63):
            return None
        return x, y

    # ------------------------------------------------------------------ search

    def _reveals(self, at: Cell, gdir: int) -> int:
        """Rows the map has never held that standing here would bring into view."""
        ahead, behind = self._band(gdir)
        lo, hi = at[0] - behind * gdir, at[0] + ahead * gdir
        return sum(1 for r in range(min(lo, hi), max(lo, hi) + 1) if r not in self._seen_rows)

    def _search(self, targets: set[Cell], goal: str, edits_cap: int) -> list[Leg] | None:
        """The route: to a target (`goal="exit"`), or onward (`"new"`).

        The state is (cell, axis, edits) because a click rearranges the board and one kind of
        click reverses which way down is. That third component is what lets a route be planned
        half under one axis and half under the other, which the deeper boards require.

        For `"exit"` — and for `"end"`, which asks for the fastest way to DIE — the first route
        found is the answer: breadth-first, unit costs, so it is also the shortest.

        For `"new"` the frontier is EXHAUSTED and every resting place scored,
        because the cheapest way onward and the best way onward are not the same thing:

            (is it safe, does it show new rows, HOW FAR ALONG THE AXIS does it get,
             how few blocks does it spend, how few actions)

        ⛔ GROUND GAINED is the third term and cost is the last, and that ordering is the whole
        difference between exploring a board and destroying it. Ranked by cost alone, a one-click
        dig at depth one always beats a five-step walk at depth five: measured on the second
        board, the tool broke sixteen blocks in twenty-nine actions, dropped itself into a slot
        it could not climb out of, and went silent with most of the board unseen. Spending steps
        costs actions; spending blocks costs the board.

        ⛔ And the gain is measured along the axis IN FORCE AT THE LANDING, not the one the body
        set out under. A route that reverses gravity and then covers ground scores that ground as
        progress; read under the original axis it reads as going backwards, and the boards whose
        exit sits on the far side of a reversal become unreachable.
        """
        if self._at is None or self._gdir == 0 or self._air is None:
            return None
        home = self._at
        seen: set[tuple[Cell, int, tuple[Cell, ...]]] = {(home, self._gdir, ())}
        queue: deque[tuple[Cell, int, tuple[Cell, ...], Board, list[Leg]]] = deque()
        queue.append((home, self._gdir, (), self._world, []))
        expanded = 0
        self._grade = 0
        best: tuple[tuple[int, int, int, int, int], list[Leg]] | None = None
        while queue and expanded < _MAX_EXPAND:
            at, gdir, edits, cells, path = queue.popleft()
            expanded += 1
            moves: list[tuple[Step, str, Cell, int, Board, tuple[Cell, ...], Sig | None, bool]] = []
            for aid, dc in ((self._left, -1), (self._right, 1)):
                verdict, rest, under = self._walk(cells, at, gdir, dc, targets)
                moves.append(((aid, None), verdict, rest, gdir, cells, edits, under,
                              ((at, gdir), (aid, None)) in self._deadly))
            if len(edits) < edits_cap:
                for cell in self._sites(cells, at, gdir):
                    if cell in edits or not self._visible(at, cell, gdir):
                        continue
                    xy = self._pixel_from(at, gdir, cell)
                    if xy is None:
                        continue
                    # ⛔ The dig guard is suspended when the goal is to END the attempt. It exists
                    # to stop the tool committing to a shaft whose bed is fatal — which is exactly
                    # the move being looked for here, and the only one available from a one-cell
                    # pocket where the body cannot even step sideways. Left on, the search for a
                    # fast ending returns nothing on precisely the boards that need it, and the
                    # tool goes back to serving out the clock.
                    if goal != "end" and cell == (at[0] + gdir, at[1]) \
                            and self._digs_into_trouble(cells, at, gdir):
                        continue
                    board2, g2, verdict, rest, under = self._click(cells, at, gdir, cell, targets)
                    moves.append(((6, xy), verdict, rest, g2, board2,
                                  tuple(sorted(edits + (cell,))), under,
                                  ((at, gdir), (6, xy)) in self._deadly))
            for step, verdict, rest, g2, board2, marks, under, struck in moves:
                leg = path + [(step, rest, g2, verdict, under)]
                if verdict == "win":
                    return leg
                if verdict == "dead":
                    if goal == "end":
                        return leg
                    continue
                if goal == "new" and verdict == "test":
                    # An experiment: worth an action when nothing better is on offer, and never
                    # expanded, because what happens next is exactly what is not known.
                    score = (1, -1 if struck else 0, -len(marks), 0, -len(leg))
                    if best is None or score > best[0]:
                        best = (score, leg)
                    continue
                if goal == "new" and rest != home:
                    # ⛔ A struck action is DISCOURAGED, never forbidden. These boards run a
                    # clock as well as hazards, so a death often names nothing and the strike
                    # lands on whichever action happened to be in flight. Forbidding those walls
                    # the tool in by its own bookkeeping: measured on the third board, four deaths
                    # to the clock struck both ways out of the opening pocket and the tool then
                    # sat in it, with the block that opens the board one step away and legal.
                    safe = -1 if struck else (0 if verdict == "blind" else 1)
                    # An edge fall leaves the map along the axis, which is as far along as this
                    # look can see; it is scored that way rather than as a stop at the last
                    # known cell, which is where it is drawn.
                    reach = (rest[0] - home[0]) * g2 + (self._rows if verdict == "edge" else 0)
                    # "Fresh" is a place the body has not STOOD in, not merely a row it has not
                    # seen. ⛔ Scoring on unseen rows alone leaves every move on an already-mapped
                    # floor tied at zero, the tie falls to whichever the frontier reached first,
                    # and the tool paces one step back and forth across the same two cells while
                    # the way on is four steps to the side.
                    # Two grades of new, and the difference is what a faller is FOR. Standing
                    # somewhere the body has not stood is worth an action; standing somewhere the
                    # CAMERA has not been is worth several, because the board is four times as
                    # deep as the window and the only way to learn the rest of it is to travel.
                    # ⛔ With one grade the tool sweeps a fully-mapped ledge end to end before it
                    # will break a block, because every cell along it is somewhere it has not
                    # stood: measured, that is most of the first board's cost.
                    if (rest, g2) in self._pocket:
                        fresh = 0
                    elif verdict != "rest":
                        fresh = 2
                    elif self._reveals(rest, g2) > 0:
                        # ⛔ `_reveals` was a BOOLEAN here, so a resting place showing ONE new row
                        # and one showing twenty scored identically. bp35 pays its whole 2x against
                        # the human count in discovery — 51 frontier searches on level 2, 39 on
                        # level 3 — and every route it walks is already shortest (BFS, unit costs),
                        # so the magnitude of what a landing SHOWS is the only thing left to rank.
                        # MEASURED: bp35 0.1648 -> 0.2078, level 3 from 81 actions to 45
                        # (0.281 -> 0.956). ⚠️ The cap is NOT load-bearing: 3, 8, 16 and 999 all
                        # give 0.2078, so a reveal above 3 rows never decides anything here — kept
                        # small so it cannot swamp the terms ranked below it.
                        fresh = 2 + min(self._reveals(rest, g2), 3)
                    elif (rest, g2) not in self._visited:
                        fresh = 1
                    else:
                        fresh = 0
                    # ⛔ Getting SOMEWHERE outranks getting there safely, and that ordering is
                    # not recklessness — it is the only way the vocabulary ever grows. Rank
                    # safety first and a step onto anything unexplained loses to a step back
                    # onto ground already walked, so the tool paces two known cells for the whole
                    # budget while the one drop that would teach it something sits beside it.
                    # Measured on the first board at action five, every run.
                    #
                    # ⛔ Blocks spent outrank ground gained. A dig gets deeper sooner than a walk
                    # always does, so putting reach first makes every route a dig; putting the
                    # edit count first means the board is only broken when walking has run out.
                    # ⛔ A route that reaches nothing NEW is not a route, it is pacing. Recording
                    # it means the searcher always has an answer, the tool never asks the next
                    # question, and it walks a mapped ledge end to end for the whole budget with
                    # a glyph it has never clicked one step away. When nothing new is reachable,
                    # the honest report is nothing, and the caller goes and measures something.
                    if fresh:
                        # ⛔ KEEPING A REVERSAL IN REACH outranks getting further along the axis,
                        # and this one term is the whole of the fourth board. Two landings one
                        # click apart scored identically — same freshness, same cost, one click
                        # each — so the tie fell to depth and the tool took the deeper one. The
                        # deeper one is a pocket: a body under an axis it can no longer reverse
                        # cannot climb, and the switches were already spent getting there.
                        # Measured at that moment, the map was RIGHT (238 cells classified
                        # correctly, 2 wrong, none unnamed) and reached to within ONE ROW of the
                        # exit. What was missing was not knowledge of the board; it was the
                        # reading that an axis you can still turn is worth more than three rows
                        # of descent.
                        score = (fresh, safe, -len(marks), reach, -len(leg))
                        if best is None or score > best[0]:
                            best = (score, leg)
                if verdict in ("edge", "blind", "test"):
                    continue
                if self._is_a_trap(board2, rest, g2):
                    continue
                key = (rest, g2, marks)
                if key in seen or (rest == at and marks == edits and g2 == gdir):
                    continue
                seen.add(key)
                queue.append((rest, g2, marks, board2, leg))
        if best is None:
            return None
        self._grade = best[0][0]
        return best[1]

    def _digs_into_trouble(self, cells: Board, at: Cell, gdir: int) -> bool:
        """Would digging out this column, block by block, end somewhere with no way off?

        ⛔ Breaking the floor is a COMMITMENT and one move at a time cannot see it: each block
        removed drops the body a single row onto the next, which looks safe every time. Measured
        on the second board — a one-cell shaft dug the whole depth of a column, rock on both
        sides at every rung, a known hazard at the bottom, no route out and nothing left to
        measure. So the column is projected before the first block is taken.

        ⛔ The projection STOPS the moment the shaft stops being one cell wide. Refusing every
        column whose distant bed is fatal refuses the correct dig too: two blocks down the same
        shaft a whole row often opens sideways, and the route out of the board runs along it. A
        dig is only a commitment while there is nothing to step onto but more of itself.
        """
        col = at[1]
        r = at[0]
        for _ in range(self._rows * 6):
            sig = cells.get((r + gdir, col))
            if sig is None:
                return True
            if self._is_open(sig):
                verdict = self._settle(cells, (r, col), gdir, set())[0]
                return verdict in ("dead", "blind", "edge")
            if sig in self._lethal:
                return True
            if sig not in self._vanish and sig not in self._swap:
                return False
            r += gdir
            for dc in (-1, 1):
                side = cells.get((r, col + dc))
                if side is not None and (self._is_open(side) or side in self._vanish
                                         or side in self._swap or side in self._flip):
                    return False
        return False

    def _is_a_trap(self, cells: Board, at: Cell, gdir: int) -> bool:
        """A slot the body can enter and cannot leave except by digging further into itself.

        ⛔ Breaking the floor is a COMMITMENT and one move at a time cannot see it: each block
        removed drops the body a single row onto the next, which looks safe every time. Measured
        on the second board — a one-cell shaft four blocks deep, rock on both sides at the
        bottom, no route out and nothing left to measure. The question is asked of the RESTING
        PLACE rather than of the action, because the tool can build the same trap out of two
        moves that are each defensible on their own.
        """
        for dc in (-1, 1):
            side = cells.get((at[0], at[1] + dc))
            if side is None:
                return False
            if (self._is_open(side) or side in self._vanish or side in self._swap
                    or side in self._flip):
                return False
        under = cells.get((at[0] + gdir, at[1]))
        return under is None or not (under in self._vanish or under in self._swap)

    def _pixel_from(self, at: Cell, gdir: int, cell: Cell) -> tuple[int, int] | None:
        """A click typed from a body at `at` — the camera has moved, so the pixel has too.

        ⛔ Only the FIRST leg of a route is ever typed; every later leg is re-derived from the
        frame it actually reaches. So the pixel recorded here is a placeholder for the legs the
        searcher only imagines, and is exact for the one it is about to use.
        """
        p = self._pitch
        if not p:
            return None
        ahead, behind = self._band(gdir)
        row = (cell[0] - at[0]) * gdir
        if not (-behind <= row <= ahead):
            return None
        screen = (at[0] - self._origin) + (cell[0] - at[0]) if at == self._at else None
        if screen is None:
            screen = (behind + row) if gdir > 0 else (self._rows - 1 - behind - row)
        if not (0 <= screen < self._rows) or not (0 <= cell[1] < self._cols):
            return None
        x = self._ox + cell[1] * p + p // 2
        y = self._oy + screen * p + p // 2
        return (x, y) if 0 <= x < 64 and 0 <= y < 63 else None

    def _probe_click(self, targets: set[Cell]) -> Cell | None:
        """One click at a kind never clicked before, chosen so it cannot move the body.

        A click anywhere but the body's support cannot move it, so this is the free half of the
        vocabulary: what a glyph DOES costs one action to measure and is never paid for twice.
        """
        if self._at is None:
            return None
        support = (self._at[0] + self._gdir, self._at[1])
        best: tuple[int, Cell] | None = None
        for cell, sig in self._world.items():
            if cell in (self._at, support) or cell in targets or sig in self._probed:
                continue
            # ⛔ Volatile is a statement about ALIGNMENT — "this glyph moves, so do not match
            # terrain on it" — and nothing at all about whether it is worth clicking. Excluding
            # it here locked the tool out of the only block that opens the third board's opening
            # pocket, because a hazard sweeping past on an earlier frame had filed the same
            # glyph, and it paced three cells until the clock ran out.
            if sig == self._air or sig in self._lethal:
                continue
            if not self._visible(self._at, cell, self._gdir) or self._pixel(cell) is None:
                continue
            dist = abs(cell[0] - self._at[0]) + abs(cell[1] - self._at[1])
            if best is None or dist < best[0]:
                best = (dist, cell)
        return best[1] if best else None

    # ----------------------------------------------------------- Tool protocol

    def detect(self, frames: list[Any], obs: Any) -> float:
        if self._refuted or not has_frame(obs):
            return 0.0
        simple, click = availability(obs)
        if not click or len([a for a in simple if a in (1, 2, 3, 4)]) != _LATERAL:
            return 0.0
        return 0.5 if self._readings(settled_layer(obs)) else 0.0

    def reset(self) -> None:
        """A new level revisits nothing; the VOCABULARY survives, because the glyphs do."""
        self._world = {}
        self._opening = None
        self._home = None
        self._volatile = set()
        self._seen_rows = set()
        self._deadly = set()
        self._missed = {}
        self._pocket = set()
        # ⛔ Running out of ideas is a fact about a BOARD, not about a game. Carrying the count
        # across a level-up retires a tool from a game it is in the middle of solving: measured,
        # it went quiet on the sixth board of a game whose first five it had just cleared.
        self._mute = 0
        self._origin = 0
        self._rollback()
        self._at = None
        self._last = None
        self._expect = None
        self._bump = 1
        self._idle = 0

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Learning needs the frame AFTER the action, so it happens at the top of propose."""

    def trace(self) -> str:
        return (f"at={self._at} g={self._gdir} cells={len(self._world)} "
                f"air={self._air is not None} exit={self._exit is not None} "
                f"open={len(self._open)} solid={len(self._solid)} kill={len(self._lethal)} "
                f"gone={len(self._vanish)} swap={len(self._swap)} flip={len(self._flip)} "
                f"edits={len(self._edits)} | {self._note}")

    def _quit(self, why: str) -> list[Step]:
        """Hand the turn back, and stop bidding once the board has run out of ideas."""
        self._note = why
        self._idle += 1
        if self._idle > _GIVE_UP:
            self._idle = 0
            self._mute += 1
            if self._mute >= _MUTE_AFTER:
                self._refuted = True
        return []

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs) or "GAME_OVER" in state_name(obs):
            return []
        level = levels_completed(obs)
        if level != self._level:
            if self._level is not None and level > self._level and self._aimed is not None:
                # Reaching that glyph ended the level: it IS the exit, on every board from here.
                self._exit = self._aimed
            self._level = level
            self._aimed = None
            self._aim = None
            self.reset()
        simple, click = availability(obs)
        lateral = sorted(a for a in simple if a in (1, 2, 3, 4))
        if not click or len(lateral) != _LATERAL:
            return []
        self._left, self._right = lateral[0], lateral[1]
        readings = self._readings(settled_layer(obs))
        if not readings:
            return self._quit("unreadable")
        was_at, was_g = self._at, self._gdir
        outcome, board, inks, body = self._stitch(readings, self._allow())
        rare = _singular(inks)
        if not self._body_ink and body in rare:
            self._body_ink = rare[body]
        if outcome == "lost":
            self._last = None
            self._plan = []
            return self._quit("window does not belong to this board")
        if outcome == "home" and was_at is not None and was_at != self._at:
            self._learn_death(self._last)
            self._last = None
            self._aimed = None

        self._digest(was_at, was_g)
        if self._at is None:
            return self._quit("no body")
        if self._gdir == 0:
            self._gdir = self._infer_gravity()
        if self._gdir == 0:
            # Nothing on screen says which way down is, and one step both reveals it and names
            # air. The direction alternates because a step into rock teaches neither.
            self._bump = -self._bump
            self._last = {"kind": "walk", "from": self._at, "dc": self._bump,
                          "into": self._world.get((self._at[0], self._at[1] + self._bump))}
            self._note = "reading the axis"
            return [(self._right if self._bump > 0 else self._left, None)]
        self._widen_band()
        self._learn_support()
        # ⛔ A dead end is only dead GIVEN WHAT IS KNOWN. The moment a glyph is named — a block
        # that turns out to open, a floor that turns out to kill — every earlier judgement of
        # "nothing reachable from here" was made without it, so they all go. Holding them past
        # that point is how a tool talks itself out of the board it has just learned to read.
        if self._vocabulary() != self._known:
            self._known = self._vocabulary()
            self._pocket = set()
        self._visited.add((self._at, self._gdir))
        return self._act(board, inks)

    # ---------------------------------------------------------------- internals

    def _widen_band(self) -> tuple[int, int]:
        """How far the window reaches along the axis and against it, from a settled body.

        ⛔ WIDEST EVER SEEN, not first seen, and that word is worth a whole level. The window is a
        fixed height in pixels but not in CELLS: where the lattice origin happens to fall decides
        whether the last row is whole, so the same window reads as ten rows on one frame and nine
        on the next. Recorded once, an unlucky first frame understates the reach against the axis
        by one row forever — and a click one row outside the recorded band is a route the searcher
        will not even consider. Measured on the fourth board: the reversal that opens it sits
        EXACTLY three rows behind the body, the band said two, and the tool turned away from the
        one move that wins, every attempt, on every restart.
        """
        row = (self._at[0] if self._at else 0) - self._origin
        ahead = row if self._gdir < 0 else self._rows - 1 - row
        behind = self._rows - 1 - row if self._gdir < 0 else row
        was = self._bands.get(self._gdir)
        band = (max(ahead, was[0]), max(behind, was[1])) if was else (ahead, behind)
        self._bands[self._gdir] = band
        return band

    def _infer_gravity(self) -> int:
        """A resting body is blocked on exactly one side of the axis."""
        if self._at is None or self._air is None:
            return 0
        r, c = self._at
        up, dn = self._world.get((r - 1, c)), self._world.get((r + 1, c))
        if up is not None and up != self._air and (dn is None or dn == self._air):
            return -1
        if dn is not None and dn != self._air and (up is None or up == self._air):
            return 1
        return 0

    def _digest(self, was_at: Cell | None, was_g: int) -> None:
        """Fold the transition just taken into the vocabulary."""
        last, self._last = self._last, None
        if last is None or was_at is None or self._at is None:
            return
        if last["kind"] == "walk":
            self._learn_move(was_at, last["dc"], self._at, last.get("into"))
            if self._gdir == 0 and self._at[1] == was_at[1] + last["dc"] and self._at[0] != was_at[0]:
                self._gdir = 1 if self._at[0] > was_at[0] else -1
            return
        cell, was = last["cell"], last["was"]
        # ⛔ The reversal is read from the SETTLED BOARD, never from how far the body appears to
        # have travelled. A body is blocked on exactly one side of the axis it is resting under,
        # so the board states the axis directly, and that reading does not depend on the window
        # having been aligned correctly. The displacement test that used to stand here read one
        # bad alignment as a reversal and invented a gravity switch on a board that has none.
        settled = self._infer_gravity()
        flipped = (was in self._flip) or (was_g != 0 and settled == -was_g)
        if flipped and was_g:
            self._gdir = -was_g
        if was is not None:
            self._edits.setdefault(cell, was)
            self._learn_click(cell, was, flipped)
            if self._world.get(cell) == was and not flipped:
                self._edits.pop(cell, None)

    def _targets(self, board: Board, inks: dict[Cell, frozenset[int]]) -> set[Cell]:
        """Where the level might end: every cell drawn in the known exit glyph, and — while that
        glyph is still unknown — whatever this window drew exactly once beside the body.

        ⛔ Candidates are targets, never a confirmed exit. Filing the first singular cell as THE
        exit teaches the searcher that any cell drawn like it wins, and one board's ornament then
        makes the whole map look solved. A candidate is only promoted when reaching it actually
        ended the level.
        """
        out: set[Cell] = set()
        if self._exit is not None:
            out |= {c for c, s in self._world.items() if s == self._exit}
        here = None if self._at is None else (self._at[0] - self._origin, self._at[1])
        for cell, ink in _singular(inks).items():
            if cell == here or board[cell] in self._dud:
                continue
            if self._body_ink and ink & self._body_ink:
                continue
            if self._exit is not None and board[cell] != self._exit:
                continue
            out.add((cell[0] + self._origin, cell[1]))
        return out

    def _act(self, board: Board, inks: dict[Cell, frozenset[int]]) -> list[Step]:
        """Follow the plan while it holds, else re-plan: a target first, then somewhere new."""
        targets = self._targets(board, inks)
        arrived = self._took
        if self._expect is not None and self._expect != self._at:
            # The board did not do what the route said it would; the rest of the route was
            # written about a board that no longer exists.
            #
            # ⛔ And a route that keeps missing in the SAME place has to be struck off, not merely
            # re-planned. The searcher is deterministic, so re-planning from an unchanged map
            # returns the identical route, and the tool paces between two cells for the whole
            # budget. Three misses is enough to call the model wrong about that one action.
            self._plan = []
            if self._took is not None:
                self._missed[self._took] = self._missed.get(self._took, 0) + 1
                if self._missed[self._took] >= 3:
                    self._deadly.add(self._took)
        self._expect = None
        self._took = None
        if self._plan:
            return [self._take()]
        if self._aim is not None and self._at == self._aim and self._exit is None:
            # Walked onto the cell the level was supposed to end at, and it did not: whatever it
            # was drawn in is decoration, and no board is to be crossed for it again.
            sig = self._world.get(self._aim)
            if sig is not None:
                self._dud.add(sig)
            self._aim = None
        route = self._search(targets, "exit", _MAX_EDITS) if targets else None
        if route is not None:
            end = route[-1][1]
            sig = self._world.get(end)
            self._aimed = sig if sig is not None else self._aimed
            self._aim = end
        else:
            route = self._search(targets, "new", _EXPLORE_EDITS)
            if route is not None and self._grade < 2:
                # ⛔ MEASURE A GLYPH BEFORE WALKING TO ANOTHER CELL IN A ROOM ALREADY SEEN. A
                # route graded 1 reaches somewhere the body has not stood but shows no row the
                # camera has not seen — on a ledge that is every cell along it, and the searcher
                # will take them one at a time for as long as they last. Measured on the first
                # board: eleven consecutive actions walking a mapped ledge end to end and back,
                # while the block that opens the floor underneath had never been clicked. A step
                # like that buys one cell; a click buys a whole KIND, everywhere it is drawn, on
                # every board after this one.
                cell = self._probe_click(targets)
                xy = self._pixel(cell) if cell is not None else None
                if cell is not None and xy is not None:
                    self._edits.setdefault(cell, self._world[cell])
                    self._last = {"kind": "click", "cell": cell, "was": self._world[cell],
                                  "on_support": False, "blind": None,
                                  "key": ((self._at, self._gdir), (6, xy))}
                    self._took = self._last["key"]
                    self._plan = []
                    self._note = f"measure {cell} before pacing"
                    self._idle = 0
                    return [(6, xy)]
        if route is None:
            cell = self._probe_click(targets)
            if cell is None:
                return self._stranded(arrived)
            xy = self._pixel(cell)
            if xy is None:
                return self._quit("nothing clickable on screen")
            # Registered as OUR edit before the action is taken, not after it lands: `_absorb`
            # sees the next frame first, and a change it cannot attribute to a click of ours is
            # a change it files as something the board animates.
            self._edits.setdefault(cell, self._world[cell])
            self._last = {"kind": "click", "cell": cell, "was": self._world[cell],
                          "on_support": False, "blind": None,
                          "key": ((self._at, self._gdir), (6, xy))}
            self._took = self._last["key"]
            self._note = f"probe {cell}"
            self._idle = 0
            return [(6, xy)]
        self._plan = route
        self._note = f"{'exit' if targets and route[-1][1] in targets else 'explore'} route x{len(route)}"
        self._idle = 0
        return [self._take()]

    def _stranded(self, arrived: tuple[tuple[Cell, int], Step] | None) -> list[Step]:
        """No route, nothing left to measure — the body has walled itself in.

        Two things are owed here and the first is the durable one: the action that BROUGHT the
        body to this pocket is struck off, so the next attempt does not walk into it again. The
        second is getting out. There is no undo in this control scheme — the only two commands
        are lateral — so the way back to a board the tool can plan on is the board's own clock:
        these levels end after a fixed number of actions and restart with the terrain intact and
        the map already learned.

        ⛔ Running the clock is offered ONLY on a board that has ALREADY been seen to restart
        itself. On a game with no such clock the same behaviour is an infinite loop that holds
        the turn forever, so the evidence has to come first — and when it is absent the honest
        answer is to hand the board back. The count is capped anyway: a clock that has not fired
        in two hundred actions is not the clock this tool saw.
        """
        if arrived is not None:
            self._deadly.add(arrived)
        if self._at is not None and self._gdir:
            self._pocket |= self._region(self._at, self._gdir)
            # ⛔ A dead end is a PLACE, not an action. Striking only the action that arrived here
            # leaves the next attempt free to walk back in by a different last step — and it did,
            # three times running. Measured on the second board: the tool reached the same pocket
            # on three consecutive attempts, burned the level's whole action budget waiting for
            # the clock each time, and cleared on the fourth. That is two hundred actions spent
            # re-learning one fact. The place is refused as a DESTINATION and still allowed as
            # somewhere to pass through, because a pocket is often on the way to somewhere else.

        if not self._clocked or self._at is None or self._waiting > 200:
            return self._quit("walled in, and this board has no clock to wait out")
        # ⛔ The clock is the SLOWEST way to start again, and on this family it is most of the
        # cost of the levels the tool already knows how to clear. Walled in, the attempt is over
        # whatever happens next; what is left to choose is how many actions it takes to admit it.
        # Waiting spends the rest of the level's budget — forty actions of bumping a wall —
        # where a known hazard two steps away spends two. Measured: the second board takes 124
        # actions against a human 48, and the difference is almost entirely time served standing
        # in pockets. This is only ever reached once the board has been searched for a way ON and
        # has none, so nothing is being thrown away that could have been played.
        ending = self._search(set(), "end", _EXPLORE_EDITS)
        if ending is not None:
            self._plan = ending
            self._note = f"walled in; ending the attempt in {len(ending)}"
            self._idle = 0
            return [self._take()]
        self._waiting += 1
        self._note = f"walled in; waiting out the clock ({self._waiting})"
        self._idle = 0
        # The cheapest wait is a step into something solid: it costs the action the clock wants
        # and cannot move the body into anything worse.
        for aid, dc in ((self._left, -1), (self._right, 1)):
            sig = self._world.get((self._at[0], self._at[1] + dc))
            if sig is not None and not self._is_open(sig):
                self._last = None
                return [(aid, None)]
        self._last = None
        return [(self._left, None)]

    def _region(self, at: Cell, gdir: int) -> set[tuple[Cell, int]]:
        """Every resting state reachable from here by WALKING alone — the pocket, not the cell.

        ⛔ Refusing only the cell the tool was standing on when it ran out of moves is refusing one
        square of a room. Measured on the fifth board: it was stranded, came back to the cell
        beside it on the next attempt, ran the clock out there too, and did that twice more. A
        pocket is a connected region and has to be remembered as one.
        """
        seen = {(at, gdir)}
        stack = [(at, gdir)]
        while stack and len(seen) < 400:
            cur, g = stack.pop()
            for dc in (-1, 1):
                verdict, rest, _ = self._walk(self._world, cur, g, dc, set())
                if verdict != "rest" or (rest, g) in seen:
                    continue
                seen.add((rest, g))
                stack.append((rest, g))
        return seen

    def _vocabulary(self) -> int:
        """How much the tool knows about glyphs. A pocket is only a pocket given this."""
        return (len(self._open) + len(self._solid) + len(self._lethal) + len(self._vanish)
                + len(self._swap) + len(self._flip) + len(self._inert))

    def _take(self) -> Step:
        """Emit the route's next action, and record both what it should teach and where it ends.

        Only ONE leg is typed per turn. The frame after a level-up still shows the board just
        finished, so a queued batch runs the finished level's route against the new board — and
        on this family a route is invalidated by any surprise anyway, since every later leg was
        computed on a board the tool only imagined.
        """
        step, rest, gdir, verdict, under = self._plan.pop(0)
        aid, xy = step
        support = None if self._at is None else (self._at[0] + self._gdir, self._at[1])
        if aid == 6 and xy is not None:
            cell = (self._origin + (xy[1] - self._oy) // self._pitch,
                    (xy[0] - self._ox) // self._pitch)
            was = self._world.get(cell)
            if was is not None:
                self._edits.setdefault(cell, was)
            self._last = None if was is None else {"kind": "click", "cell": cell, "was": was,
                                                   "on_support": cell == support}
        else:
            dc = 1 if aid == self._right else -1
            self._last = {"kind": "walk", "from": self._at, "dc": dc,
                          "into": None if self._at is None
                          else self._world.get((self._at[0], self._at[1] + dc))}
        if self._last is not None:
            self._last["blind"] = under if verdict == "blind" else None
            self._last["key"] = ((self._at, self._gdir), step)
            self._took = self._last["key"]
        self._expect = rest
        return step
