"""Shaft tool — a tall side-view faller planned on a WORLD map, not on the viewport.

Recovered from frames alone. The mechanic, in the order the tool has to derive it:

  * the board is a lattice of equal square cells, one glyph drawn per cell, and the camera
    shows only a window of it — roughly ten rows of a board forty rows deep;
  * control is LATERAL ONLY: exactly two of the four plain actions exist. There is no command
    for the gravity axis, which is what makes this a faller rather than a maze;
  * a lateral action moves the body one cell sideways and it then SETTLES, sliding along the
    gravity axis until a cell it cannot enter stops it. A sideways step into a cell it cannot
    enter costs the action and moves nothing;
  * a click EDITS one cell of the board. Some cells vanish, some swap to a partner, and one
    kind REVERSES GRAVITY. The reversing kind is the only one that acts from a distance: the
    others rearrange terrain, and the body moves only if the edited cell was the one holding
    it up;
  * the level ends when the body enters — or comes to rest on — the board's singular cell;
  * some cells KILL whatever comes to rest on them, and the only notice is that the board
    restarts with the level counter unmoved.

⛔ THE BOARD IS TALLER THAN THE WINDOW, and that is the whole reason this tool exists next to a
viewport-planner. Measured on the sample faller: the exit of the fourth board sits on the far
side of the gravity axis from the body, and the switch that reverses gravity is off-screen at
the moment the route has to be chosen. A planner that can only see the current window has no
route to search for, so it probes, falls, dies, and restarts — twenty-three restarts in fifteen
hundred actions, three boards deep, on the run that motivated this file. So every frame is
STITCHED into one persistent map by matching terrain across the scroll, and the route is
searched over that map.

⛔ Nothing here is written down: not the cell size, not the lattice origin, not the gravity
direction, not which colour is floor, exit, switch or hazard. Each is derived, because a
constant recovered by hand does not transfer to a board whose source we will never see.

Five derivations that are easy to get wrong, and what each costs:

  * "empty is the commonest cell" is FALSE on a board whose window is mostly rock. Measured on
    the sample faller's fourth board: rock 58 cells, air 26 — reading the mode as air puts every
    route through solid stone. Air is learned instead from the cell the body VACATES, which is
    ground truth and costs the one lateral probe the tool has to spend anyway.
  * a move is an ANIMATION and the observation ships the whole animation as layers. Layer zero
    is the board BEFORE the move; planning from it plans against a state the game has left.
    Only the LAST layer is read.
  * the camera scrolls only when the body FALLS, and it re-centres on the body, so a fall looks
    exactly like the terrain sliding. Without stitching, the tool learns the nature of whatever
    slid into the old floor's place.
  * a hazard must never be inferred from a death on a board that also runs a TIMER. The sample
    faller's first three boards drown the shaft on a schedule, and the floor the body drowned on
    is a floor it had already stood on safely. A signature that has ever held the body safely is
    therefore never marked lethal.
  * a click is addressed in SCREEN pixels, so a cell can only be edited while it is on screen.
    The search carries that restriction, or it returns routes whose middle step cannot be typed.


⛔ NOT REGISTERED, and kept deliberately rather than deleted. Measured 2026-08-27 head to head on
its board, each tool run with the other removed so the winner actually drives:

    ledge (the incumbent at the time)   3 levels at actions 15, 62, 97
    shaft                               2 levels, after a revision that took it from 1
    crag (registered now)               5 levels, 0.1648 against ledge's 0.1333

Its selectivity was perfect first time — 0.5 on this board and 0.00 on the other twenty-four —
and its central structural claim was RIGHT and is now in the wiki: the board is eleven cells wide
and up to thirty-nine tall, far taller than the viewport, which a diff of the game's own runtime
tile table confirmed. It is kept because `scripts/crag_probe.py` offers it as a head-to-head
baseline and that comparison is how `crag` earned the board; deleting it would leave a committed
script with a path that fails only when invoked, since the import sits inside a function.
"""

from __future__ import annotations

from collections import Counter, deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, has_frame, levels_completed

__all__ = ["ShaftTool", "settled_layer", "read_lattice", "fit_lattice"]

Cell = tuple[int, int]
Sig = tuple[tuple[int, int], ...]
Board = dict[Cell, Sig]
# One leg of a planned route: the action, where the body ends up, the gravity it ends under,
# how that ending was reached, and what it comes to rest on.
Leg = tuple[Step, Cell, int, str, "Sig | None"]

# A lattice below this many whole cells is furniture, not a board.
_MIN_CELLS = 24
# Cell pitch bounds. Below five the core sampled is 3x3 and a 3x3 patch of anything is flat,
# so every coarser lattice loses to the finest one on offer.
_PITCH_LO = 5
_PITCH_HI = 10
# Terrain agreement needed before a frame is accepted as the SAME board, scrolled.
_ALIGN_FIT = 0.80
# Demanded instead whenever the body's own motion cannot vouch for the shift — after a click
# that MIGHT have reversed gravity, when up and down are both admissible and the long uniform
# runs of a shaft will happily match a window eleven rows from home.
_STRICT_FIT = 0.97
_ALIGN_MIN = 12
# Cells that must disagree together under an ACCEPTED shift before their kinds are filed as
# "this moves on its own". A band of them is a hazard sweeping the shaft; one is a misread.
_VOLATILE_RUN = 3
# Clicks allowed inside one searched route. Two is enough for every board seen: throw the
# switch, then break the floor. Three multiplies the state space by the candidate count again.
_MAX_EDITS = 2
# Editable cells a single search may compose routes from. Twelve reached only the floor the
# body stands on; the way out of a pocket is often the shaft on the FAR side of the screen.
_MAX_SITES = 24
_MAX_EXPAND = 40000
# Consecutive proposals that change nothing before the tool hands the board back.
_GIVE_UP = 14
# Proposals with nothing to say before the tool stops bidding on this board altogether.
_MUTE_AFTER = 3


def settled_layer(obs: Any) -> np.ndarray:
    """The board once the move has finished playing — read from the STACK, not from `frame_2d`.

    ⛔ This tool does its own frame reading and must keep doing it. The shared reader takes
    layer ZERO, and on this family the layer stack is an ANIMATION TIMELINE: layer 0 is the
    board part-way through the move that has just been made. Checked against the engine's own
    body coordinate over a ten-action script, layer 0 reports the body's position from the
    PREVIOUS action every time and lands the lattice origin one or two pixels off the grid,
    while the last layer matches the truth on every step. For a faller that is not a detail —
    layer 0 is the board mid-fall, which is the one moment its position means nothing.

    ⛔ And this is a per-tool reading, deliberately, not a fix to the shared reader. Switching
    that to the last layer was measured on all twenty-five games and made the card WORSE
    (0.6733 -> 0.6525); the stack is not uniformly "start ... settled" across games. It is
    settled-last HERE, which is a fact about the boards this tool bids on and nothing wider.
    See `.wiki/wiki/concepts/frame_layer_timeline.md`.
    """
    arr = np.asarray(getattr(obs, "frame", None))
    while arr.ndim > 2:
        arr = arr[-1]
    return arr.astype(np.int64)


def _cores(g: np.ndarray, p: int, oy: int, ox: int) -> list[tuple[Cell, np.ndarray]]:
    """Every whole cell's core patch, inset one pixel so a neighbour's bleed cannot reach it.

    Glyphs are drawn one pixel wider than the pitch on this family, so adjacent cells share a
    boundary line and whichever was drawn last owns it. The inset makes a cell's reading its
    own.
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
    """(distinct cell kinds, fraction of cells that are one flat colour) at this lattice."""
    cs = _cores(g, p, oy, ox)
    if len(cs) < _MIN_CELLS:
        return 10**6, 0.0
    kinds = len({_sig(k) for _, k in cs})
    flat = sum(1 for _, k in cs if k.size and int(k.min()) == int(k.max())) / len(cs)
    return kinds, flat


def fit_lattice(g: np.ndarray) -> tuple[int, int, int] | None:
    """Pitch and origin of the cell grid, or None if the frame is not drawn on one.

    ⛔ The PITCH and the ORIGIN are scored differently and it matters. The pitch is the COARSEST
    step that still reads the frame as flat tiles — a plain argmax drifts to the finest step on
    offer, because a small enough core is flat whatever it samples. The origin, at that pitch,
    is the one that needs the FEWEST distinct kinds: a board drawn from a small alphabet is
    drawn from a small alphabet, and a misaligned reading of it is not.
    """
    flats = []
    for p in range(_PITCH_LO, _PITCH_HI + 1):
        best = max((_alphabet(g, p, oy, ox)[1] for oy in range(p) for ox in range(p)), default=0.0)
        flats.append((p, best))
    top = max(f for _, f in flats)
    if top <= 0.0:
        return None
    pitch = max(p for p, f in flats if f >= 0.9 * top)
    origin: tuple[int, float, int, int] | None = None
    for oy in range(pitch):
        for ox in range(pitch):
            kinds, flat = _alphabet(g, pitch, oy, ox)
            if kinds >= 10**6:
                continue
            if origin is None or (kinds, -flat) < (origin[0], -origin[1]):
                origin = (kinds, flat, oy, ox)
    if origin is None:
        return None
    return pitch, origin[2], origin[3]


def read_lattice(g: np.ndarray, p: int, oy: int, ox: int) -> tuple[Board, dict[Cell, frozenset[int]]]:
    """Screen cell -> its signature, and screen cell -> the bare set of colours it carries."""
    board: Board = {}
    inks: dict[Cell, frozenset[int]] = {}
    for cell, core in _cores(g, p, oy, ox):
        if not core.size:
            continue
        board[cell] = _sig(core)
        inks[cell] = frozenset(int(v) for v in core.ravel())
    return board, inks


def _singular(inks: dict[Cell, frozenset[int]]) -> set[Cell]:
    """Cells carrying a colour that no other cell carries — the body and the exit are two."""
    owners: dict[int, set[Cell]] = {}
    for cell, ink in inks.items():
        for col in ink:
            owners.setdefault(col, set()).add(cell)
    return {next(iter(cells)) for cells in owners.values() if len(cells) == 1}


class ShaftTool:
    """Harness tool wrapping the lateral-faller mechanic on a stitched world map."""

    name = "shaft"

    def __init__(self) -> None:
        # --- vocabulary: learned once, carried across boards AND across deaths, because the
        # rock of the first board is the rock of the eighth and paying for it twice is waste.
        self._air: Sig | None = None
        self._open: set[Sig] = set()
        self._solid: set[Sig] = set()
        self._lethal: set[Sig] = set()
        self._safe: set[Sig] = set()      # has held the body without killing it
        self._vanish: set[Sig] = set()    # a click empties this cell
        self._swap: dict[Sig, Sig] = {}   # a click turns this cell into that one
        self._flip: set[Sig] = set()      # a click reverses gravity
        self._inert: set[Sig] = set()     # a click does nothing to this cell
        self._probed: set[Sig] = set()    # a click on this kind has been paid for once
        self._deadly: set[tuple[Cell, int, int, tuple[int, int] | None]] = set()
        self._graves: set[tuple[Cell, int]] = set()
        self._exit: Sig | None = None
        self._proved = False
        self._body_ink: frozenset[int] = frozenset()
        self._pitch = 0
        self._oy = 0
        self._ox = 0
        self._left = 3
        self._right = 4

        # --- per-board state
        self._world: Board = {}
        self._volatile: set[Sig] = set()
        self._ghost: set[Cell] = set()
        self._origin = 0
        self._opening: tuple[Board, Cell] | None = None
        self._acted = 0
        self._at: Cell | None = None
        self._gdir = 0
        self._cols = 0
        self._band = (3, 3)
        self._edited: set[Cell] = set()
        self._visited: set[Cell] = set()
        self._plan: list[Leg] = []
        self._last: dict[str, Any] | None = None
        self._probe_col = 0
        self._idle = 0
        self._level: int | None = None
        self._mute = 0

    # ------------------------------------------------------------------ read

    def _lattice(self, g: np.ndarray) -> tuple[int, int, int] | None:
        if self._pitch:
            p = self._pitch
            best: tuple[int, float, int, int] | None = None
            for oy in range(p):
                for ox in range(p):
                    kinds, flat = _alphabet(g, p, oy, ox)
                    if kinds >= 10**6:
                        continue
                    if best is None or (kinds, -flat) < (best[0], -best[1]):
                        best = (kinds, flat, oy, ox)
            return (p, best[2], best[3]) if best else None
        found = fit_lattice(g)
        if found:
            self._pitch = found[0]
        return found

    def _body(self, board: Board, inks: dict[Cell, frozenset[int]]) -> Cell | None:
        """The singular cell that moves, tracked by its rare colours once they are known.

        ⛔ Membership is not identity. One of the body's colours is shared with a hazard on a
        later board, so "any cell carrying one of my colours" matches the body and every spike
        on screen at once. The body is the BEST match — most colours in common, then nearest to
        where it was, because a camera that follows it keeps it in nearly the same place.
        """
        if self._body_ink:
            hits = [(len(ink & self._body_ink), c) for c, ink in inks.items() if ink & self._body_ink]
            if not hits:
                return None
            near = self._at_screen() or (0, 0)
            hits.sort(key=lambda h: (-h[0], abs(h[1][0] - near[0]) + abs(h[1][1] - near[1])))
            return hits[0][1]
        cand = sorted(_singular(inks))
        if not cand:
            return None
        rows = max(r for r, _ in board) + 1
        cols = max(c for _, c in board) + 1
        mid = ((rows - 1) / 2, (cols - 1) / 2)
        return min(cand, key=lambda c: abs(c[0] - mid[0]) + abs(c[1] - mid[1]))

    def _at_screen(self) -> Cell | None:
        return None if self._at is None else (self._at[0] - self._origin, self._at[1])

    # --------------------------------------------------------------- stitching

    def _stitch(self, board: Board, body: Cell, anchor: tuple[int, int] | None,
                strict: bool = False) -> bool:
        """Fold this window into the world map. False when it is a DIFFERENT board.

        The camera follows the body and only moves when it falls, so a fall and a landslide are
        the same picture. The shift is recovered by matching terrain: the offset under which the
        window agrees with what the map already holds.

        ⛔ Agreement alone is NOT enough to name the shift, and that is the expensive lesson
        here. A shaft is mostly long uniform runs of rock and air, so a window laid fifteen rows
        off its true home still agrees with nine cells in ten — and once accepted, the tool
        writes a SECOND COPY of the board into the map and plans routes across a place that does
        not exist. Physics settles it instead: between two frames the body can only have moved
        ALONG the gravity axis, so a shift that claims it climbed is rejected however well the
        rock lines up. A window that no admissible shift explains is a new board — a level
        gained, or a death that restarted this one.
        """
        rows = max(r for r, _ in board) + 1
        self._cols = max(c for _, c in board) + 1
        self._band = (body[0], rows - 1 - body[0])
        if not self._world:
            self._origin = 0
            self._absorb(board, body, 0)
            return True
        lo = min(r for r, _ in self._world) - rows
        hi = max(r for r, _ in self._world) + rows
        scored: list[tuple[float, int]] = []
        for shift in range(lo, hi + 1):
            agree = total = 0
            for (r, c), sig in board.items():
                if (r, c) == body:
                    continue
                key = (r + shift, c)
                was = self._world.get(key)
                if was is None or key in self._ghost or was in self._volatile or sig in self._volatile:
                    continue
                total += 1
                if was == sig:
                    agree += 1
            if total >= _ALIGN_MIN:
                scored.append((agree / total, shift))
        if not scored:
            return False
        if anchor is not None:
            prev_row, gdir = anchor
            if gdir:
                scored = [(sc, sh) for sc, sh in scored if (body[0] + sh - prev_row) * gdir >= 0]
        if not scored:
            return False
        top = max(sc for sc, _ in scored)
        if top < (_STRICT_FIT if strict else _ALIGN_FIT):
            return False
        shift = min((sh for sc, sh in scored if sc >= top - 0.01),
                    key=lambda sh: abs(sh - self._origin))
        self._origin = shift
        self._absorb(board, body, shift)
        return True

    def _absorb(self, board: Board, body: Cell, shift: int) -> None:
        """Write the window into the map, and note any cell that changed on its own.

        A cell that changes with no click on it is something the board animates — a hazard that
        sweeps the shaft, or a timer drawn onto the terrain. A WHOLE BAND of them has to change
        together before the kinds involved are filed that way: one disagreeing cell is a misread,
        a row of them is a moving thing, and the difference decides whether the map's alignment
        can trust the terrain next frame.

        Being filed does NOT make a kind passable. An unknown cell is refused by the search,
        which is the safe reading; the only thing that makes a kind passable is the body having
        gone through it.
        """
        clashes: list[tuple[Cell, Sig, Sig]] = []
        for (r, c), sig in board.items():
            key = (r + shift, c)
            if (r, c) == body:
                if self._air is not None:
                    self._world[key] = self._air
                    self._ghost.add(key)
                continue
            was = self._world.get(key)
            if was is not None and was != sig and key not in self._edited and key not in self._ghost:
                clashes.append((key, was, sig))
            self._world[key] = sig
            self._ghost.discard(key)
        if len(clashes) >= _VOLATILE_RUN:
            for _, was, sig in clashes:
                self._volatile.add(was)
                self._volatile.add(sig)
        self._at = (body[0] + shift, body[1])

    # ------------------------------------------------------------- vocabulary

    def _is_open(self, sig: Sig | None) -> bool:
        if sig is None:
            return False
        return sig == self._air or sig in self._open

    def _known(self, sig: Sig | None) -> bool:
        return sig is not None and (self._is_open(sig) or sig in self._solid)

    def _learn_move(self, before: Cell, went: int, after: Cell) -> None:
        """What the board just admitted about itself, from one lateral step.

        The reading is exact, which is why the tool spends its first action on a step rather
        than a click: the cell stepped into was passable, every cell fallen through was
        passable, the cell that stopped the fall was not, and the cell just vacated was
        passable — and that last one is where AIR comes from, with no appeal to which
        signature happens to be commonest.
        """
        target = (before[0], before[1] + went)
        tsig = self._world.get(target)
        if after == before:
            if tsig is not None and not self._is_open(tsig):
                self._solid.add(tsig)
            elif tsig is not None and self._air is None:
                self._solid.add(tsig)
            return
        if tsig is not None:
            self._open.add(tsig)
        if self._air is None:
            vacated = self._world.get(before)
            if vacated is not None:
                self._air = vacated
                self._open.add(vacated)
        r = target[0]
        while r != after[0]:
            nxt = r + (1 if after[0] > r else -1)
            sig = self._world.get((nxt, target[1]))
            if sig is not None and nxt != after[0]:
                self._open.add(sig)
            r = nxt
    def _learn_support(self, at: Cell) -> None:
        """Whatever is holding the body up is solid, and — having held it — is not a hazard.

        ⛔ Called only once the gravity axis is known, and that ordering is load-bearing. It used
        to run inside the step-learner, which fires on the FIRST move of a board, before the axis
        has been read; with no axis there is no "underfoot", so nothing was ever filed as solid,
        every fall ran off the end of what the tool knew, and every single step looked like a
        step into unexplored ground. The tool paced back and forth for the whole budget.
        """
        if not self._gdir:
            return
        support = self._world.get((at[0] + self._gdir, at[1]))
        if support is not None and not self._is_open(support):
            self._solid.add(support)
            self._safe.add(support)

    def _learn_click(self, cell: Cell, was: Sig, now: Sig | None, flipped: bool) -> None:
        if flipped:
            self._flip.add(was)
            return
        if now is None or now == was:
            self._inert.add(was)
            return
        if self._air is not None and now == self._air:
            self._vanish.add(was)
        else:
            self._swap[was] = now
        self._open.discard(was) if not self._is_open(now) else None

    def _learn_death(self, last: dict[str, Any] | None) -> None:
        """One death, read as narrowly as the evidence allows — and never more widely.

        Three facts are on offer and the emitted action already said which one applies:

        * the body was heading onto something DRAWN and unexplained, so that signature is a
          hazard and the whole board's worth of it is refused from here on;
        * the body was heading over a BRINK with nothing drawn beyond, so nothing can be named,
          but leaving the map at that cell under that gravity is fatal however the body arrives
          there — which survives the restart, and the restart is the point;
        * failing both, only the exact (cell, gravity, action) is refused.

        ⛔ What is NOT done is inferring a hazard from an ordinary landing. The first three
        boards of this family drown the shaft on a schedule, and a body drowned on a floor it
        had stood on twice is not evidence about the floor. An earlier version marked it anyway
        and locked the tool out of the only ledge it could stand on, whereupon it went silent
        for the rest of the budget. A landing the tool predicted correctly teaches nothing about
        terrain; it only says the clock ran out.
        """
        if not last:
            return
        if last.get("key") is not None:
            self._deadly.add(last["key"])
        if last.get("brink") is not None:
            self._graves.add(last["brink"])
        blind = last.get("blind")
        if blind is None or blind in self._safe or self._is_open(blind):
            return
        self._lethal.add(blind)
        self._solid.discard(blind)

    # ---------------------------------------------------------------- physics

    def _settle(self, cells: Board, start: Cell, gdir: int) -> tuple[str, Cell, Sig | None]:
        """Slide from `start` along `gdir`. Returns (verdict, resting cell, the thing underfoot).

        Verdicts, and the distinction between the last two is the one that matters most:

        * `rest` — stopped on terrain the tool has stood on before;
        * `win`  — came to rest on the exit;
        * `dead` — came to rest over a known hazard, or over a brink already paid for;
        * `edge` — ran off the end of the map. Nothing is DRAWN down there yet; the camera
          simply has not been that far. Ordinary unexplored shaft.
        * `blind` — stopped on something that IS drawn and that the tool cannot account for.

        ⛔ Those last two were one verdict, and conflating them is what made the second board
        unwinnable. Both shafts out of the opening pocket need two clicks; the left one is three
        steps closer, so the searcher always took it, and the left one is bedded with spikes.
        The spikes were ON SCREEN the whole time — drawn, unexplained, three rows down. By the
        time a board's second level starts, rock and air and the breakable block have all been
        named by walking on them, so a cell still drawn in something else is the board saying
        "this one is different". Unseen ground is a better bet than an unexplained thing, and
        ordering the two that way is worth several restarts a board.
        """
        r, c = start
        while True:
            nxt = (r + gdir, c)
            sig = cells.get(nxt)
            if sig is None:
                if ((r, c), gdir) in self._graves:
                    return "dead", (r, c), None
                return "edge", (r, c), None
            if self._exit is not None and sig == self._exit:
                return "win", nxt, None
            if self._is_open(sig):
                r = nxt[0]
                continue
            if sig in self._lethal:
                return "dead", (r, c), sig
            if sig in self._solid:
                return "rest", (r, c), sig
            return "blind", (r, c), sig

    def _step(self, cells: Board, at: Cell, gdir: int, dc: int) -> tuple[str, Cell, Sig | None]:
        """One lateral action from `at`, resolved to a verdict, a resting cell and its support."""
        target = (at[0], at[1] + dc)
        sig = cells.get(target)
        if sig is None:
            return "edge", at, None
        if self._exit is not None and sig == self._exit:
            return "win", target, None
        if not self._is_open(sig):
            if sig in self._solid:
                return "rest", at, sig
            if sig in self._lethal:
                return "rest", at, sig
            return "rest", at, sig
        return self._settle(cells, target, gdir)

    # ----------------------------------------------------------------- search

    def _edit_sites(self, cells: Board) -> list[Cell]:
        """Cells whose click effect is known, nearest the body first.

        ⛔ The cap is wide enough to reach the OTHER shaft. At twelve it held only the blocks
        immediately under and beside the body, so the only routes the searcher could compose
        were the ones that dig straight down — into whatever the board put directly below.

        ⛔ A cell that has been clicked before is NOT excluded, and that used to be a permanent
        lock-out. One kind of block TOGGLES: a click turns it into its partner and a click on the
        partner turns it back. The prober therefore clicks such a cell twice — once to learn the
        block, once more when the partner shows up as a kind it has not seen — leaving the board
        exactly as it found it and the cell marked as already dealt with. On the third board that
        cell is the pillar between the body and the only hole in the floor. Re-clicking is kept
        honest by the rule that an edit must OPEN something: clicking a toggle back the way it
        came opens nothing, so it is refused on its own merits rather than by bookkeeping.
        """
        if self._at is None:
            return []
        out = []
        for cell, sig in cells.items():
            if sig in self._flip or sig in self._vanish or sig in self._swap:
                out.append(cell)
        out.sort(key=lambda q: abs(q[0] - self._at[0]) + abs(q[1] - self._at[1]))
        return out[:_MAX_SITES]

    def _apply(self, cells: Board, at: Cell, gdir: int,
               cell: Cell) -> tuple[Board, int, str, Cell, Sig | None]:
        """The board, gravity, body and what is underfoot after clicking `cell`."""
        sig = cells[cell]
        nxt = dict(cells)
        if sig in self._flip:
            nxt[cell] = self._air if self._air else sig
            g2 = -gdir
            ahead = nxt.get((at[0] + g2, at[1]))
            if ahead is not None and self._exit is not None and ahead == self._exit:
                return nxt, g2, "win", (at[0] + g2, at[1]), None
            if self._is_open(ahead):
                verdict, rest, under = self._settle(nxt, at, g2)
                return nxt, g2, verdict, rest, under
            return nxt, g2, "rest", at, ahead
        nxt[cell] = self._air if sig in self._vanish else self._swap[sig]
        if cell == (at[0] + gdir, at[1]):
            verdict, rest, under = self._settle(nxt, at, gdir)
            return nxt, gdir, verdict, rest, under
        return nxt, gdir, "rest", at, cells.get((at[0] + gdir, at[1]))

    def _visible(self, at: Cell, cell: Cell) -> bool:
        """A click is typed in screen pixels, so its cell must be on screen when it is typed."""
        up, dn = self._band
        return -up <= cell[0] - at[0] <= dn and 0 <= cell[1] < self._cols

    def _search(self, goal: str) -> list[Leg] | None:
        """Shortest action route: to the exit (`goal="exit"`), or to somewhere NEW (`"new"`).

        The state carries the board itself, because a click rearranges it, and gravity, because
        one kind of click reverses it. Routes are capped at `_MAX_EDITS` clicks: two is enough
        for every board seen, and a third multiplies the frontier by the candidate count again.

        The four ways of getting somewhere new are ranked, and the ranking is the whole design:

        1. a route that lands on ground the tool KNOWS and still brings unseen rows into view —
           free information, taken the moment it is found;
        2. a fall off the END of the map — unexplored shaft, the normal way down;
        3. a route that EDITS the board without revealing anything yet — the way out of a pocket
           whose exit is more blocks wide than one search can plan through;
        4. a fall onto something DRAWN that the tool cannot account for — last, because by the
           second board everything ordinary has already been named by walking on it, so what is
           left is what the board drew differently, and that is usually what kills.

        ⛔ Rank 3 above rank 2 and the tool digs straight down through the nearest floor into
        whatever is under it. Rank 3 below rank 4 and it walls itself into a pocket and goes
        silent. Rank 1 anywhere but first and it pays actions for information it was being
        offered free. Each of those three orderings was measured, in that order, on this game.
        """
        if self._at is None or self._gdir == 0:
            return None
        seen: set[tuple[Cell, int, tuple[Cell, ...]]] = {(self._at, self._gdir, ())}
        queue: deque[tuple[Cell, int, tuple[Cell, ...], Board, list[Leg]]] = deque()
        queue.append((self._at, self._gdir, (), self._world, []))
        expanded = 0
        over: list[Leg] | None = None      # rank 2 — off the end of the map
        edit: list[Leg] | None = None      # rank 3 — changes the board
        dark: list[Leg] | None = None      # rank 4 — onto the unexplained
        while queue and expanded < _MAX_EXPAND:
            at, gdir, edits, cells, path = queue.popleft()
            expanded += 1
            moves: list[tuple[Step, str, Cell, int, Sig | None, Board, tuple[Cell, ...]]] = []
            for aid, dc in ((self._left, -1), (self._right, 1)):
                if (at, gdir, aid, None) in self._deadly:
                    continue
                verdict, rest, under = self._step(cells, at, gdir, dc)
                moves.append(((aid, None), verdict, rest, gdir, under, cells, edits))
            if len(edits) < _MAX_EDITS:
                for cell in self._edit_sites(cells):
                    if cell in edits or not self._visible(at, cell):
                        continue
                    xy = self._pixel(cell)
                    if xy is None or (at, gdir, 6, xy) in self._deadly:
                        continue
                    if cell == (at[0] + gdir, at[1]) and self._digs_into_a_hazard(cells, at, gdir):
                        continue
                    nxt, g2, verdict, rest, under = self._apply(cells, at, gdir, cell)
                    moves.append(((6, xy), verdict, rest, g2, under, nxt,
                                  tuple(sorted(edits + (cell,)))))
            for step, verdict, rest, g2, under, board, marks in moves:
                move = path + [(step, rest, g2, verdict, under)]
                if verdict == "win":
                    return move
                if verdict == "dead":
                    continue
                if verdict == "edge":
                    if goal == "new" and rest != at and over is None:
                        over = move
                    continue
                if verdict == "blind":
                    if goal == "new" and dark is None:
                        dark = move
                    continue
                if self._is_a_trap(board, rest, g2):
                    continue
                if goal == "new" and self._newness(rest) > 0:
                    return move
                if (goal == "new" and marks != edits and edit is None
                        and self._opens(cells, at, gdir, board, rest, g2)):
                    edit = move
                key = (rest, g2, marks)
                if (rest == at and marks == edits) or key in seen:
                    continue
                seen.add(key)
                queue.append((rest, g2, marks, board, move))
        return over or edit or dark

    def _digs_into_a_hazard(self, cells: Board, at: Cell, gdir: int) -> bool:
        """Would digging out this column, block by block, end on a known hazard with no way off?

        ⛔ Breaking the floor is a COMMITMENT and a one-step search cannot see it. Each block
        removed drops the body a single row onto the next one, which looks safe every time — so
        the tool dug a one-cell shaft four blocks deep down a column whose bed was spikes,
        arrived in a slot with solid rock on both sides, and could then neither go on nor climb
        back. The spikes had been on screen, and named, since the board's first death.

        ⛔ But the projection stops the moment the shaft STOPS being one cell wide. Refusing
        every column whose distant bed is fatal refuses the correct dig too: two blocks down the
        same shaft a whole row of breakable opens sideways, and the route out of the board runs
        along it. A dig is only a trap while there is nothing to step onto but more of itself.
        """
        col = at[1]
        r = at[0]
        for _ in range(len(self._world) + 1):
            sig = cells.get((r + gdir, col))
            if sig is None or (self._exit is not None and sig == self._exit):
                return False
            if sig in self._lethal:
                return True
            if self._is_open(sig):
                # ⛔ "Blind" counts as fatal HERE and nowhere else. Landing on something
                # unexplained is an ordinary risk when the body can step off again; it is not one
                # when the body has just dropped itself down a one-cell shaft it cannot climb.
                # A commitment is only made onto ground the tool can account for.
                return self._settle(cells, (r, col), gdir)[0] in ("dead", "blind")
            if sig not in self._vanish:
                return False
            r += gdir
            for dc in (-1, 1):
                side = cells.get((r, col + dc))
                if side is not None and (self._is_open(side) or side in self._vanish
                                         or side in self._swap):
                    return False
        return False

    def _is_a_trap(self, cells: Board, at: Cell, gdir: int) -> bool:
        """A slot the body can enter, cannot leave sideways, and can only leave downward to die.

        ⛔ The dig projection alone is not enough, because the tool can build the trap in two
        moves that are each defensible. Measured: it broke the block below the slot from OUTSIDE
        the slot — which is not a dig, so the projection never ran — and then stepped in, which
        is an ordinary step onto ordinary floor. Two legal moves, one dead end. So the question
        is asked of the RESTING PLACE rather than of the action: rock on both sides, and nothing
        under it but a way to die.
        """
        for dc in (-1, 1):
            side = cells.get((at[0], at[1] + dc))
            if side is None:
                return False
            if (self._is_open(side) or side in self._vanish or side in self._swap
                    or side in self._flip):
                return False
        return self._digs_into_a_hazard(cells, at, gdir)

    def _reach(self, cells: Board, at: Cell, gdir: int) -> set[Cell]:
        """Every resting cell the body can walk to from `at` without editing the board."""
        seen = {at}
        stack = [at]
        while stack:
            cur = stack.pop()
            for dc in (-1, 1):
                verdict, rest, _ = self._step(cells, cur, gdir, dc)
                if verdict in ("dead", "edge", "blind") or rest in seen:
                    continue
                seen.add(rest)
                stack.append(rest)
        return seen

    def _opens(self, before: Board, at: Cell, gdir: int,
               after: Board, rest: Cell, g2: int) -> bool:
        """Did that click actually OPEN something, or merely rearrange scenery?

        ⛔ Without this test the tool clicks every breakable block on screen, one per action, and
        goes nowhere: each click changes the board, so each one qualified as "a route that edits
        the board", and the searcher took them in order of distance until the budget was gone.
        Measured on the second board — fourteen consecutive clicks from a standing start, no
        movement, no information. An edit earns its action only if the body can afterwards reach
        somewhere it could not reach before.
        """
        gained = self._reach(after, rest, g2) - self._reach(before, at, gdir)
        return any(not self._is_a_trap(after, cell, g2) for cell in gained)

    def _newness(self, rest: Cell) -> int:
        """How many rows of the board a camera centred on `rest` would show for the first time.

        This is the frontier measure, and it is deliberately blind to direction. "Go deeper" is
        the right instinct on a shaft and the wrong one on the board where the exit sits on the
        far side of a reversed gravity axis; "show me rows I have not seen" is the same instinct
        without the assumption.
        """
        up, dn = self._band
        rows = {r for r, _ in self._world}
        return sum(1 for r in range(rest[0] - up, rest[0] + dn + 1) if r not in rows)

    def _pixel(self, cell: Cell) -> tuple[int, int] | None:
        """Screen centre of a world cell, or None when it is not on screen."""
        p = self._pitch
        if not p:
            return None
        r = cell[0] - self._origin
        y = self._oy + p * r + p // 2
        x = self._ox + p * cell[1] + p // 2
        if not (0 <= y < 64 and 0 <= x < 64):
            return None
        return int(x), int(y)

    # --------------------------------------------------------------- lifecycle

    def detect(self, frames: list[Any], obs: Any) -> float:
        if self._mute >= _MUTE_AFTER or not has_frame(obs):
            return 0.0
        simple, click = availability(obs)
        lateral = [a for a in simple if a in (1, 2, 3, 4)]
        if not click or len(lateral) != 2:
            return 0.0
        g = settled_layer(obs)
        found = self._lattice(g)
        if found is None:
            return 0.0
        p, oy, ox = found
        board, inks = read_lattice(g, p, oy, ox)
        if len(board) < _MIN_CELLS:
            return 0.0
        if self._body(board, inks) is None:
            return 0.0
        # ⛔ The opening bid is deliberately BELOW the threshold at which this harness hands a
        # tool the whole game. All the tool can say before it has moved is "there is a lattice
        # and something on it that might be a body" — it has not yet measured which way gravity
        # points, and on this family that is the difference between a plan and a guess. Measured:
        # bidding above the threshold from the first frame took ownership of the board away from
        # a tool that clears three levels of it, and delivered one.
        return 0.9 if self._gdir else 0.5

    def reset(self) -> None:
        """A new board revisits nothing; the VOCABULARY survives, because the cells do.

        ⛔ Gravity does NOT survive. It is board state, not cell knowledge: a board finished with
        the switch thrown hands the next one an inverted axis, and every route on it would then
        be planned upside down.
        """
        self._world = {}
        self._volatile = set()
        self._ghost = set()
        self._origin = 0
        self._opening = None
        self._acted = 0
        self._at = None
        self._gdir = 0
        self._edited = set()
        self._visited = set()
        self._plan = []
        self._last = None
        self._idle = 0

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        if self._last is not None:
            self._last["action"] = action
            self._last["changed"] = changed

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        simple, click = availability(obs)
        lateral = sorted(a for a in simple if a in (1, 2, 3, 4))
        if not click or len(lateral) != 2:
            return []
        self._left, self._right = lateral[0], lateral[1]
        g = settled_layer(obs)
        found = self._lattice(g)
        if found is None:
            return []
        p, self._oy, self._ox = found
        board, inks = read_lattice(g, p, self._oy, self._ox)
        body = self._body(board, inks)
        if body is None:
            return []
        if not self._body_ink:
            self._body_ink = inks[body]

        level = levels_completed(obs)
        fresh = level != self._level
        pending = self._last
        self._last = None
        self._level = level
        was_at = self._at
        # The gravity axis is read off the NEW frame, in SCREEN space, before anything is
        # stitched — so it is available even when the action just taken may have reversed it.
        # ⛔ Without this the shift after a click was unconstrained, and a window eleven rows
        # from home matched the uniform rock well enough to be accepted; the map then held two
        # copies of the board and the body was tracked in the phantom one.
        axis = self._axis(board, body) or self._gdir
        anchor = None if was_at is None or axis == 0 else (was_at[0], axis)
        if fresh:
            # ⛔ The stand-down survives a RESTART and is lifted only by a new LEVEL. A board
            # that defeated the tool defeats it again the same way, and clearing the flag on
            # every restart turned "stand down" into a four-action toll charged forty-six times
            # — paid out of the budget of whichever tool was actually getting somewhere.
            self._mute = 0
        if fresh and self._exit is not None:
            # The board ended while the tool was walking at one particular signature. On this
            # family the board ends when the body ARRIVES, so that signature was the exit, and
            # it is the same signature on the next board: the guess is now a fact and stops
            # being re-argued from scratch every time the map scrolls.
            self._proved = True
        if fresh or not self._stitch(board, body, anchor, strict=anchor is None and was_at is not None):
            if not fresh:
                self._learn_death(pending)
            self.reset()
            if fresh:
                self._deadly = set()
                self._graves = set()
            self._level = level
            self._stitch(board, body, None)
            self._opening = (dict(board), body)
            was_at = None
            pending = None
        elif self._opening is None:
            self._opening = (dict(board), body)
        self._digest(board, body, was_at, pending)
        if self._at is not None:
            self._visited.add(self._at)
        if self._gdir == 0:
            return self._sidestep()

        if self._exit_seen():
            route = self._search("exit")
            if route:
                self._plan = route
                return self._emit()
        route = self._search("new")
        if route:
            self._plan = route
            return self._emit()
        probe = self._probe_click()
        if probe is not None:
            self._mute = 0
            return probe
        step = self._sidestep()
        if step:
            self._mute = 0
            return step
        # ⛔ Out of plan is out of turn. A tool holding the board with nothing to do is not
        # merely idle: on this family the harness keeps handing it every step, and thirteen of
        # the twenty-five sample games END when the budget runs out. Standing down lets a tool
        # that does have a plan have the board.
        self._mute += 1
        return []

    # ------------------------------------------------------------- internals


    def _axis(self, board: Board, body: Cell) -> int:
        """A resting body is supported on exactly ONE side of the gravity axis.

        ⛔ The support is named by what AIR is, never by which of the two neighbours is rarer on
        screen. Measured on the sample faller's fourth board: rock outnumbers air 58 cells to 26
        inside the window, so the frequency reading calls the ceiling the floor and plans every
        route upside down. Until air has been observed this returns nothing at all, and the tool
        spends one lateral step to find out — which is the same step that teaches it air.
        """
        air = self._air
        if air is None:
            return 0
        up, dn = board.get((body[0] - 1, body[1])), board.get((body[0] + 1, body[1]))
        up_air = up is not None and self._is_open(up)
        dn_air = dn is not None and self._is_open(dn)
        if up is not None and not up_air and dn_air:
            return -1
        if dn is not None and not dn_air and up_air:
            return 1
        return 0

    def _digest(self, board: Board, body: Cell, was_at: Cell | None,
                pending: dict[str, Any] | None) -> None:
        """Fold the transition just taken into the vocabulary, then re-read the gravity axis."""
        if self._gdir == 0:
            self._gdir = self._axis(board, body)
        if pending is None or was_at is None or self._at is None:
            return
        action = pending.get("action")
        if action is None:
            return
        aid, _xy = action
        if aid in (self._left, self._right):
            self._learn_move(was_at, -1 if aid == self._left else 1, self._at)
            if self._gdir == 0:
                self._gdir = self._axis(board, body)
            self._learn_support(self._at)
        elif aid == 6 and pending.get("cell") is not None:
            after = self._axis(board, body)
            flipped = after != 0 and self._gdir != 0 and after != self._gdir
            self._learn_click(pending["cell"], pending["was"],
                              self._world.get(pending["cell"]), flipped)
            if flipped:
                self._gdir = after
            self._learn_support(self._at)
        self._idle = self._idle + 1 if self._at == was_at else 0

    def _exit_seen(self) -> bool:
        """Is the exit's signature both known and on the map?

        Before a first win the exit is a GUESS: the one cell the board has drawn exactly ONCE,
        anywhere the map reaches, that is neither the body nor anything already classified as
        terrain. It is a guess worth walking toward — it is also the only thing on the board
        worth walking toward — and it REFUTES ITSELF: the moment a second cell of that signature
        scrolls into view, or the moment that signature stops a fall, the board has said it is
        furniture and the guess is dropped. A guess that survives to a win is never re-examined.
        """
        if self._exit is not None:
            hits = sum(1 for s in self._world.values() if s == self._exit)
            if self._proved:
                return hits > 0
            if (hits == 1 and self._exit not in self._solid and self._exit not in self._lethal
                    and self._exit not in self._flip and self._exit not in self._vanish
                    and self._exit not in self._swap):
                return True
            self._exit = None
        if self._at is None:
            return False
        counts = Counter(self._world.values())
        alone = [c for c, s in self._world.items()
                 if counts[s] == 1 and c != self._at
                 and s not in self._solid and s not in self._lethal and not self._is_open(s)]
        alone = [c for c in alone if self._world[c] not in self._flip
                 and self._world[c] not in self._vanish and self._world[c] not in self._swap]
        if len(alone) != 1:
            return False
        self._exit = self._world[alone[0]]
        return True

    def _probe_click(self) -> list[Step] | None:
        """Pay ONE action to find out what a click does to a kind of cell.

        ⛔ Including the kind the tool currently BELIEVES is the exit, as long as that is still a
        guess. Measured, and it deadlocked a whole board: the body reached the floor of the shaft
        with the only singular cell on the map two rows further down behind solid rock, so the
        guess was unreachable — and being the guess, it was also the one cell the prober refused
        to touch. It was the gravity switch. One click on it turns the board upside down and the
        route opens. Clicking a real exit costs nothing: a board that ends when the body ARRIVES
        does not answer a click on the destination.

        ⛔ This is the action the tool cannot plan its way out of needing. On the first board the
        only way down is through a floor that has to be broken, and "break the floor" is not a
        move a search can find until a click has been seen to do something. The support
        underfoot is probed first because its outcome is the most informative one available: it
        either opens the shaft or it does not, and either answer is a fact about the board.

        One probe per KIND, never per cell — a board of twenty identical blocks would otherwise
        spend twenty actions learning the same thing once.
        """
        if self._at is None or self._gdir == 0:
            return None
        order: list[Cell] = []
        under = (self._at[0] + self._gdir, self._at[1])
        if under in self._world:
            order.append(under)
        order.extend(sorted(self._world,
                            key=lambda q: abs(q[0] - self._at[0]) + abs(q[1] - self._at[1])))
        for cell in order:
            sig = self._world.get(cell)
            if sig is None or sig == self._air or sig in self._probed or sig in self._volatile:
                continue
            if sig in self._vanish or sig in self._swap or sig in self._flip or sig in self._inert:
                continue
            if any(sig == made for made in self._swap.values()):
                # The partner half of a toggle. Clicking it only undoes the click that revealed
                # it, and the pair is one mechanic, already paid for.
                continue
            if sig in self._lethal:
                continue
            if self._proved and sig == self._exit:
                continue
            if not self._visible(self._at, cell):
                continue
            xy = self._pixel(cell)
            if xy is None or (self._at, self._gdir, 6, xy) in self._deadly:
                continue
            self._probed.add(sig)
            self._edited.add(cell)
            self._last = {"gdir": self._gdir, "cell": cell, "was": sig, "blind": None,
                          "brink": None, "flip": True,
                          "key": (self._at, self._gdir, 6, xy)}
            self._acted += 1
            return [(6, xy)]
        return None

    def _emit(self) -> list[Step]:
        """Issue the route's first action, and record what would have to be true if it kills.

        Every emitted action carries its own post-mortem: the exact (cell, gravity, action) that
        produced it, plus whichever of the two learnable facts applies — the SIGNATURE it was
        about to come to rest on when that thing is drawn but unexplained, or the BRINK it was
        about to fall over when there is nothing drawn down there at all. If the board restarts,
        one of those is the answer, and which one is already decided.
        """
        step, rest, gdir, verdict, under = self._plan[0]
        aid, xy = step
        note: dict[str, Any] = {"gdir": self._gdir, "cell": None, "blind": None, "brink": None,
                                "key": (self._at, self._gdir, aid, xy)}
        if aid == 6 and xy is not None:
            cell = (self._origin + (xy[1] - self._oy) // self._pitch,
                    (xy[0] - self._ox) // self._pitch)
            note["cell"] = cell
            note["was"] = self._world.get(cell)
            note["flip"] = note["was"] not in self._vanish and note["was"] not in self._swap
            self._edited.add(cell)
        if verdict == "edge":
            note["brink"] = (rest, gdir)
        elif under is not None and not self._is_open(under) and under not in self._solid:
            # ⛔ The post-mortem is keyed on WHAT the body was going to stand on, not on how the
            # route classified the ending. A dig can be planned as an ordinary landing and still
            # put the body down on something the tool has never accounted for, and that is the
            # case worth learning from. Keying on the verdict instead let eleven deaths in a row
            # teach nothing at all.
            note["blind"] = under
        self._last = note
        self._acted += 1
        return [step]

    def _sidestep(self) -> list[Step]:
        """The one unplanned action, and it exists to answer exactly one question.

        A board opens with the tool knowing nothing — not which signature is air, and therefore
        not which way gravity points. One lateral step settles both: the cell the body leaves is
        air by construction, and the side it comes to rest against is the floor.

        ⛔ It is not a fallback for "no route". A tool with no plan must bid nothing and take
        nothing: alternating left and right on a board it cannot read spends a budget that
        thirteen of the twenty-five sample games END on, and takes the turn from a tool that
        might have had a plan. So this runs only while the axis is still unknown.
        """
        if self._gdir != 0 or self._idle >= _GIVE_UP:
            return []
        self._probe_col = 1 - self._probe_col
        aid = self._right if self._probe_col else self._left
        note: dict[str, Any] = {"gdir": self._gdir, "cell": None, "blind": None, "brink": None,
                                "key": (self._at, self._gdir, aid, None)}
        self._last = note
        self._acted += 1
        return [(aid, None)]
