"""Ledge tool — a side-view faller: two lateral controls, gravity, and a click that edits terrain.

Recovered from frames alone. The mechanic, in the order the tool has to derive it:

  * the board is a lattice of equal square cells, one sprite drawn per cell;
  * control is LATERAL ONLY — exactly two of the four movement actions exist, and that is what
    makes this a faller rather than a maze: there is no command for the gravity axis;
  * a lateral action moves the body one cell sideways and it then SETTLES, sliding along the
    gravity axis until a cell it cannot enter stops it;
  * a click EDITS one cell. Some cells vanish under a click, some swap to a partner cell, and on
    the later boards one inverts gravity. Which is which is measured, never assumed;
  * the level ends when the body enters, or comes to rest on, the board's singular cell;
  * some cells KILL what comes to rest on them, and the only notice is that the level restarts.

⛔ Nothing here is written down: not the cell size, not the lattice origin, not the gravity
direction, not which colour is floor, door, goal or hazard. Each is derived, because a constant
recovered by hand does not transfer to a game whose source we will never see.

Four derivations that are easy to get wrong, and what each cost:

  * a move is an ANIMATION and the observation ships the whole animation as LAYERS — five for a
    step, twenty-five for a long fall. Layer zero is the board BEFORE the move. Reading it plans
    against a state the game has already left; `settled` takes the last layer.
  * a cell is its ink SIGNATURE, not its dominant colour. The see-through block on the third
    board draws five pixels inside an otherwise empty cell, so by dominance it IS empty — and
    the route across that board is to click those cells solid and walk on them.
  * a door is SOLID until it is clicked. Letting a fall pass through every door below it reads
    "standing on a breakable roof" as "already at the bottom of the shaft", and the bottom of
    that shaft is a spike bed.
  * a hazard is learned from ONE death, and the inference has two branches: either the cell the
    model expected to stop on is the killer, or it let the body through onto a killer already
    known. Simulating both is what turns the second board's spike bed into knowledge instead of
    a loop of identical deaths.

Clicks are the safe probe here: a click that is not aimed at the cell underfoot cannot move the
body, so every unclassified cell can be learned for one action without risking the run.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from admorphiq.tools.base import (
    Step,
    availability,
    has_frame,
    levels_completed,
    state_name,
)

__all__ = [
    "LedgeTool",
    "fit_offsets",
    "fit_pitch",
    "floor_sig",
    "read_board",
    "settled",
]

Cell = tuple[int, int]
Sig = tuple[tuple[int, int], ...]
Board = dict[Cell, Sig]

# A faller has no command for the gravity axis. Two lateral moves is the mechanic's signature.
_LATERAL = 2
_MIN_CELLS = 24
_MIN_FIT = 0.55
_MAX_EXPAND = 4000
_GIVE_UP = 12


def settled(obs: Any) -> np.ndarray:
    """The LAST layer of the observation — the board once the move has finished playing."""
    arr = np.asarray(getattr(obs, "frame", None))
    while arr.ndim > 2:
        arr = arr[-1]
    return arr.astype(np.int64)


def _cores(g: np.ndarray, p: int, oy: int, ox: int) -> list[tuple[Cell, np.ndarray]]:
    """Every whole cell's core patch, inset by a pixel so a neighbour's bleed cannot reach it.

    The last pixel row and column are never included: an edge-pinned counter lives there on this
    family, and reading a counter as terrain invents a floor that is not there.
    """
    h, w = g.shape
    out: list[tuple[Cell, np.ndarray]] = []
    for r, y in enumerate(range(oy, h - p, p)):
        for c, x in enumerate(range(ox, w - p, p)):
            out.append(((r, c), g[y + 1 : y + p - 1, x + 1 : x + p - 1]))
    return out


def _sig(core: np.ndarray) -> Sig:
    return tuple(sorted(Counter(int(v) for v in core.ravel()).items()))


def _uniformity(g: np.ndarray, p: int, oy: int, ox: int) -> float:
    """Fraction of cell cores that are one flat colour — how tile-like this lattice looks."""
    cores = _cores(g, p, oy, ox)
    if len(cores) < _MIN_CELLS:
        return 0.0
    flat = sum(1 for _, k in cores if k.size and int(k.min()) == int(k.max()))
    return flat / len(cores)


def fit_offsets(g: np.ndarray, p: int) -> tuple[int, int, float]:
    """The lattice origin at a known step: the one that needs the FEWEST distinct tiles.

    ⛔ Not the flattest one. Flatness picked an origin two pixels off the sprite grid, where every
    cell also caught a column of its neighbour — enough to keep the walls flat, and enough to
    split the see-through block into three lookalike tiles that no learning could join up. A
    board drawn from a small alphabet is drawn from a small alphabet; a misaligned reading of it
    is not.
    """
    best: tuple[int, float, int, int] | None = None
    for oy in range(p):
        for ox in range(p):
            cores = _cores(g, p, oy, ox)
            if len(cores) < _MIN_CELLS:
                continue
            kinds = len({_sig(k) for _, k in cores})
            flat = _uniformity(g, p, oy, ox)
            if best is None or (kinds, -flat) < (best[0], -best[1]):
                best = (kinds, flat, oy, ox)
    if best is None:
        return 0, 0, 0.0
    return best[2], best[3], best[1]


def fit_pitch(g: np.ndarray, lo: int = 4, hi: int = 10) -> tuple[int, int, int, float]:
    """The lattice step, origin and quality.

    The STEP and the ORIGIN answer different questions and are scored differently. The step is
    the coarsest one whose best origin still reads the frame as flat tiles; the origin, at that
    step, is the one that needs the fewest distinct tiles.

    ⛔ The step is the COARSEST that survives, not the best-scoring one. A 4px step samples a 2x2
    core, and a 2x2 patch of anything is usually flat, so a plain argmax drifts to the finest
    step on offer and every neighbour lookup then addresses half a cell. Scoring the step by the
    origin the SECOND rule picked has the same effect by a longer route — measured, it took a
    six-pixel board and read it on a four-pixel grid.
    """
    scored = []
    for p in range(lo, hi + 1):
        flat = max((_uniformity(g, p, oy, ox) for oy in range(p) for ox in range(p)), default=0.0)
        scored.append((p, flat))
    top = max(s[1] for s in scored)
    if top <= 0.0:
        return 0, 0, 0, 0.0
    step = max(p for p, flat in scored if flat >= 0.9 * top)
    oy, ox, _ = fit_offsets(g, step)
    return step, oy, ox, dict(scored)[step]


def read_board(g: np.ndarray, p: int, oy: int, ox: int) -> tuple[Board, dict[Cell, frozenset[int]]]:
    """Cell -> its ink signature, and cell -> the bare set of inks it contains.

    The signature is the terrain's identity. The bare set is what finds the singular cells: the
    body and the goal each own an ink nothing else on the board owns.
    """
    board: Board = {}
    inks: dict[Cell, frozenset[int]] = {}
    for cell, core in _cores(g, p, oy, ox):
        if not core.size:
            continue
        board[cell] = _sig(core)
        inks[cell] = frozenset(int(v) for v in core.ravel())
    return board, inks


def floor_sig(board: Board) -> Sig:
    """What "nothing here" looks like — the commonest CELL, never the commonest pixel.

    ⛔ Measured: a pixel count answers a different question. The wall here is textured and empty
    space is flat, so the walls own more pixels while the empty cells own more of the board.
    Taking the pixel mode named the wall as free space and every route ran through solid rock.
    """
    return Counter(board.values()).most_common(1)[0][0]


class LedgeTool:
    """Harness tool wrapping the lateral-faller mechanic."""

    name = "ledge"

    def __init__(self) -> None:
        # Vocabulary learned across levels AND across deaths — the floor of the first board is
        # the floor of the eighth, and paying for the same hazard on each is paying eight times.
        self._open: set[Sig] = set()
        self._solid: set[Sig] = set()
        self._gone: set[Sig] = set()
        self._swap: dict[Sig, Sig] = {}
        self._inert: set[Sig] = set()
        self._lethal: set[Sig] = set()
        self._flip: set[Sig] = set()
        self._dud: set[Sig] = set()
        self._empty: Sig | None = None
        self._pitch = 0
        self._avatar_ink: frozenset[int] = frozenset()
        self._at: Cell | None = None
        self._gdir = 0
        self._level: int | None = None
        self._prev: dict[str, Any] | None = None
        self._first: Board | None = None
        self._seen: set[str] = set()
        self._probed: set[Sig] = set()
        self._stalls = 0
        self._idle = 0
        self._refuted = False

    # --- perception ---------------------------------------------------------

    def _lattice(self, g: np.ndarray) -> tuple[int, int, int, float]:
        if self._pitch:
            p = self._pitch
            oy, ox, _ = fit_offsets(g, p)
            flat = max((_uniformity(g, p, y, x) for y in range(p) for x in range(p)), default=0.0)
            return p, oy, ox, flat
        p, oy, ox, flat = fit_pitch(g)
        if p:
            self._pitch = p
        return p, oy, ox, flat

    def _singular(self, inks: dict[Cell, frozenset[int]]) -> dict[Cell, frozenset[int]]:
        """Cell -> the inks no other cell carries."""
        owners: dict[int, set[Cell]] = {}
        for cell, ink in inks.items():
            for col in ink:
                owners.setdefault(col, set()).add(cell)
        out: dict[Cell, set[int]] = {}
        for col, cells in owners.items():
            if len(cells) == 1:
                out.setdefault(next(iter(cells)), set()).add(col)
        return {c: frozenset(v) for c, v in out.items()}

    def _avatar(self, board: Board, inks: dict[Cell, frozenset[int]]) -> Cell | None:
        """The singular cell that moves. Tracked by its rare inks once they have been seen.

        ⛔ Membership is not identity. One of the body's two inks is shared with the hazard on
        the second board, so "any cell carrying one of my inks" matches the body AND every spike
        on screen, and the tool loses itself the moment it can see one. The body is the BEST
        match — most inks in common, and nearest to where it was, because a camera that follows
        it keeps it in nearly the same place — and it is only accepted when it is a clear best.
        """
        if self._avatar_ink:
            hits = [(len(ink & self._avatar_ink), c) for c, ink in inks.items() if ink & self._avatar_ink]
            if not hits:
                return None
            near = self._at or (0, 0)
            hits.sort(key=lambda h: (-h[0], abs(h[1][0] - near[0]) + abs(h[1][1] - near[1])))
            if len(hits) > 1 and hits[0][0] == hits[1][0] and self._at is None:
                return None
            return hits[0][1]
        cand = sorted(self._singular(inks))
        if not cand:
            return None
        if len(cand) == 1:
            return cand[0]
        # A camera that follows a body keeps it near the middle of the frame; whatever else the
        # level drew exactly once is wherever the level put it.
        rows = max(r for r, _ in board) + 1
        cols = max(c for _, c in board) + 1
        mid = ((rows - 1) / 2, (cols - 1) / 2)
        return min(cand, key=lambda c: abs(c[0] - mid[0]) + abs(c[1] - mid[1]))

    def _infer_gravity(self, board: Board, avatar: Cell, bg: Sig) -> int:
        """A resting body is occupied on exactly one side of the gravity axis."""
        r, c = avatar
        up, dn = board.get((r - 1, c)), board.get((r + 1, c))
        if up is not None and up != bg and (dn is None or dn == bg):
            return -1
        if dn is not None and dn != bg and (up is None or up == bg):
            return 1
        return 0

    # --- three-valued terrain -----------------------------------------------

    def _is_open(self, sig: Sig, bg: Sig) -> bool:
        return sig == bg or sig in self._open

    def _edit(self, sig: Sig, bg: Sig) -> Sig | None:
        """What a click turns this cell into, once that has been measured."""
        if sig in self._gone:
            return bg
        return self._swap.get(sig)

    def _door(self, sig: Sig, bg: Sig) -> bool:
        """A cell a click turns into a way through — a door, not a wall, and not free."""
        if self._is_open(sig, bg) or sig in self._flip:
            return False
        after = self._edit(sig, bg)
        return after is not None and self._is_open(after, bg)

    def _prop(self, sig: Sig, bg: Sig) -> bool:
        """A cell a click turns into FLOOR: passable now, solid after.

        This is the half of the toggle the third board is built on — the ledge you walk along is
        not there until you make it, and it looks like empty air until it is.
        """
        if not self._is_open(sig, bg) or sig in self._flip:
            return False
        after = self._edit(sig, bg)
        return after is not None and not self._is_open(after, bg)

    def _drop(self, board: Board, cell: Cell, bg: Sig, porous: bool = False) -> tuple[Cell, Sig | None]:
        """Where the body comes to rest and on what. `porous` = assume every unknown lets it by."""
        r, c = cell
        while True:
            nxt = (r + self._gdir, c)
            sig = board.get(nxt)
            if sig is None:
                return (r, c), None
            through = self._is_open(sig, bg) or (porous and sig not in self._solid)
            if not through:
                return (r, c), sig
            r = nxt[0]

    def _fatal(self, board: Board, cell: Cell, bg: Sig) -> bool:
        """Would resting here risk the level?

        Both readings have to be safe. An unknown cell underfoot is either a floor or a hole,
        and refusing only the reading the model happens to prefer is how a tool walks into the
        one it did not consider.
        """
        for porous in (False, True):
            _, support = self._drop(board, cell, bg, porous=porous)
            if support is not None and support in self._lethal:
                return True
        return False

    # --- learning from the transition just taken ----------------------------

    def _align(self, old: Board, new: Board) -> tuple[int, int] | None:
        """How far the view scrolled between the frames, in cells.

        The camera follows the body, so the body's screen cell barely moves while the WORLD
        slides under it. Without this every fall looks like the terrain changed, and the tool
        learns the nature of whatever slid into the old floor's place.
        """
        best: tuple[float, int, int] | None = None
        span = max(r for r, _ in new) + 1
        for dy in range(-span, span + 1):
            for dx in (-1, 0, 1):
                agree = tot = 0
                for (r, c), sig in new.items():
                    was = old.get((r + dy, c + dx))
                    if was is None:
                        continue
                    tot += 1
                    agree += was == sig
                if tot < 12:
                    continue
                score = agree / tot
                if best is None or (score, -abs(dy)) > (best[0], -abs(best[1])):
                    best = (score, dy, dx)
        if best is None or best[0] < 0.75:
            return None
        return best[1], best[2]

    def _learn(self, board: Board, avatar: Cell, bg: Sig) -> None:
        prev = self._prev
        if prev is None or prev["level"] != self._level:
            return
        old: Board = prev["board"]
        was: Cell = prev["avatar"]
        act: Step = prev["act"]
        shift = self._align(old, board)
        if shift is None:
            return
        dy, dx = shift
        here = (avatar[0] + dy, avatar[1] + dx)      # where the body is, in OLD coordinates
        vacated = (was[0] - dy, was[1] - dx)         # where it was, in the new frame
        if self._empty is None and here != was and vacated in board:
            # ⛔ The one class that must not be guessed. "Commonest cell" answers it while the
            # window is mostly sky and answers WALL the moment the window fills with rock — and
            # the frame it changes its mind on is the frame the planner learns that empty space
            # is solid. What the body VACATES is empty by construction: it was standing there.
            self._empty = board[vacated]
            self._solid.discard(self._empty)
            self._inert.discard(self._empty)
        if act[0] == 6:
            if here[1] == was[1] and here[0] != was[0] and (1 if here[0] > was[0] else -1) == -self._gdir:
                # ⛔ The body went UP. Nothing in this mechanic lifts a body except a change of
                # which way down is, so the tile just clicked reverses gravity — and every route
                # planned since is planned against the wrong axis. Later boards put the goal on
                # the far side of that flip, so a tool that cannot notice it stops at level four
                # with a full vocabulary and a search pointed at the ceiling.
                self._gdir = -self._gdir
                target = prev["target"]
                if target is not None and target in old:
                    self._flip.add(old[target])
                    self._gone.discard(old[target])
                return
            self._learn_click(old, board, prev["target"], shift, avatar)
            return
        dc = 1 if act[0] == prev["right"] else -1
        tgt = (was[0], was[1] + dc)
        if here == was:
            sig = old.get(tgt)
            if sig is not None and sig != bg:
                self._solid.add(sig)
                self._open.discard(sig)
            return
        sig = old.get(tgt)
        if sig is not None and sig != bg:
            self._open.add(sig)
            self._solid.discard(sig)
        if here[1] == tgt[1] and here[0] != tgt[0]:
            fell = 1 if here[0] > tgt[0] else -1
            if self._gdir == 0:
                self._gdir = fell
            r = tgt[0]
            while r != here[0]:
                through = old.get((r, tgt[1]))
                if through is not None and through != bg:
                    self._open.add(through)
                    self._solid.discard(through)
                r += fell
        under = old.get((here[0] + self._gdir, here[1])) if self._gdir else None
        if under is not None and under != bg:
            self._solid.add(under)
            self._open.discard(under)
        # Reaching the board's one-off and still being here means it was decoration. Struck off
        # by SIGNATURE, so the same ornament is not walked to again on the next board either.
        for at in (here, (here[0] + self._gdir, here[1])):
            sig = prev["goals"].get(at)
            if sig is not None:
                self._dud.add(sig)

    def _learn_click(
        self, old: Board, new: Board, target: Cell | None, shift: tuple[int, int], avatar: Cell
    ) -> None:
        """What one click did to the cell it hit — measured, never assumed."""
        if target is None:
            return
        before = old.get(target)
        if before is None:
            return
        dy, dx = shift
        at = (target[0] - dy, target[1] - dx)
        after = new.get(at)
        if after is None:
            return
        if at == avatar:
            # ⛔ The body fell INTO the cell the click was aimed at, so that cell now reads as
            # the body, not as terrain. Its standing there IS the answer: the click opened it.
            # Reading the colour instead taught that this tile becomes the body's own ground,
            # and the planner then treated floor as a door.
            self._gone.add(before)
            return
        if after == before:
            if (dy, dx) == (0, 0) and new == old:
                self._inert.add(before)
            return
        if self._empty is not None and after == self._empty:
            self._gone.add(before)
            self._swap[before] = after
            return
        self._swap[before] = after
        self._swap.setdefault(after, before)

    def _learn_death(self, bg: Sig) -> None:
        """One death, two candidates, and a simulation that tells them apart.

        The level restarted with the counter unmoved, so the last action was fatal. Either the
        cell the model expected to stop on is the killer, or it is not solid at all and let the
        body through onto a killer already known. Assuming the first without checking the second
        is what turns the third board into a loop of identical deaths.
        """
        prev = self._prev
        self._prev = None
        self._seen = set()
        self._stalls = 0
        if prev is None:
            return
        board: Board = prev["after"]
        cell: Cell | None = prev["landing"]
        if cell is None:
            return
        support = board.get((cell[0] + self._gdir, cell[1]))
        if support is None or support == bg:
            return
        _, deeper = self._drop(board, cell, bg, porous=True)
        if deeper is not None and deeper != support and deeper in self._lethal:
            self._open.add(support)
            self._solid.discard(support)
            return
        self._lethal.add(support)
        self._open.discard(support)

    def _classified(self, sig: Sig, bg: Sig) -> bool:
        return (
            sig == bg
            or sig in self._gone
            or sig in self._swap
            or sig in self._inert
            or sig in self._flip
            or sig in self._dud
        )

    def _died(self, board: Board) -> bool:
        """Did the level restart under us? The board is the opening board and we did not win."""
        if self._first is None or self._prev is None:
            return False
        return board == self._first and self._prev["board"] != self._first

    # --- planning -----------------------------------------------------------

    def _goals(self, board: Board, inks: dict[Cell, frozenset[int]], avatar: Cell) -> set[Cell]:
        """The board's other singular cells — what this level put there exactly once."""
        return {
            c
            for c in self._singular(inks)
            if c != avatar
            and not (self._avatar_ink and inks[c] & self._avatar_ink)
            and board[c] not in self._dud
        }

    def _hops(
        self, board: Board, cell: Cell, bg: Sig, goals: set[Cell]
    ) -> list[tuple[int, Cell | None, Cell, int]]:
        """Every single move from a cell: (direction, cell to click first, landing, cost)."""
        out: list[tuple[int, Cell | None, Cell, int]] = []
        for dc in (-1, 1):
            tgt = (cell[0], cell[1] + dc)
            sig = board.get(tgt)
            if sig is None:
                continue
            if tgt in goals:
                out.append((dc, None, tgt, 1))
                continue
            under = (tgt[0] + self._gdir, tgt[1])
            floor = board.get(under)
            if self._is_open(sig, bg):
                rest, _ = self._drop(board, tgt, bg)
                landed = (rest[0] + self._gdir, rest[1])
                if landed in goals:
                    out.append((dc, None, landed, 1))
                elif not self._fatal(board, tgt, bg):
                    out.append((dc, None, rest, 1))
                # The ledge is not there until it is made: click the air under the step solid,
                # then step onto it. Two actions, and on some boards the only two that exist.
                if floor is not None and self._prop(floor, bg):
                    built = dict(board)
                    built[under] = self._edit(floor, bg)          # type: ignore[index]
                    if not self._fatal(built, tgt, bg):
                        out.append((dc, under, tgt, 2))
            elif self._door(sig, bg):
                opened = dict(board)
                opened[tgt] = self._edit(sig, bg)                 # type: ignore[index]
                rest, _ = self._drop(opened, tgt, bg)
                landed = (rest[0] + self._gdir, rest[1])
                if landed in goals:
                    out.append((dc, tgt, landed, 2))
                elif not self._fatal(opened, tgt, bg):
                    out.append((dc, tgt, rest, 2))
                elif floor is not None and self._prop(floor, bg):
                    # Open the door AND build the ledge behind it. The third board stacks the
                    # two: the way through is a solid tile that must be dissolved, standing on
                    # air that must be set, over a hazard. Offering only one click per step
                    # refuses the pair and calls the board finished.
                    both = dict(opened)
                    both[under] = self._edit(floor, bg)           # type: ignore[index]
                    if not self._fatal(both, tgt, bg):
                        out.append((dc, under, tgt, 3))
        under = (cell[0] + self._gdir, cell[1])
        sig = board.get(under)
        if sig is not None and self._door(sig, bg):
            opened = dict(board)
            opened[under] = self._edit(sig, bg)                   # type: ignore[index]
            rest, _ = self._drop(opened, cell, bg)
            landed = (rest[0] + self._gdir, rest[1])
            if landed in goals:
                out.append((0, under, landed, 1))
            elif rest != cell and not self._fatal(opened, cell, bg):
                out.append((0, under, rest, 1))
        return out

    def _unknown(self, sig: Sig, bg: Sig) -> bool:
        """Neither floor nor wall yet — a tile whose behaviour has never been observed."""
        return not self._is_open(sig, bg) and sig not in self._solid

    def _search(self, board: Board, avatar: Cell, bg: Sig, goals: set[Cell]) -> tuple[int, Cell | None] | None:
        """The next hop: cheapest route to a singular cell, else the best ground gained.

        Returns (direction, cell to click) — the caller turns that into the ONE action that
        starts it and re-plans from the next frame rather than trusting a batch. The frame after
        a level-up still shows the board just finished, so a queued plan runs the finished
        level's route against the new board.
        """
        far: dict[Cell, int] = {avatar: 0}
        lead: dict[Cell, tuple[int, Cell | None]] = {}
        order = [avatar]
        best: tuple[int, int, tuple[int, Cell | None]] | None = None
        goal_hit: tuple[int, tuple[int, Cell | None]] | None = None
        curious: tuple[int, tuple[int, Cell | None]] | None = None
        while order and len(far) <= _MAX_EXPAND:
            order.sort(key=lambda c: far[c])
            cell = order.pop(0)
            # ⛔ The cheapest experiment on this family is a SIDEWAYS BUMP. Walking into a wall
            # costs one action and nothing else, and walking into a tile that turns out to be
            # air teaches exactly the fact the planner is missing. Without this the tool sits
            # in front of the see-through blocks that the third board is built from, calling
            # them wall because it has never been told otherwise, and stalls with a full
            # vocabulary and no route.
            for dc in (-1, 1):
                tgt = (cell[0], cell[1] + dc)
                sig = board.get(tgt)
                if sig is None or not self._unknown(sig, bg) or tgt in goals:
                    continue
                if self._fatal(board, tgt, bg):
                    continue
                spent = far[cell] + 1
                if curious is None or spent < curious[0]:
                    curious = (spent, lead.get(cell, (dc, None)))
            for hop, opens, rest, cost in self._hops(board, cell, bg, goals):
                start = lead.get(cell, (hop, opens))
                spent = far[cell] + cost
                if rest in goals:
                    if goal_hit is None or spent < goal_hit[0]:
                        goal_hit = (spent, start)
                    continue
                if rest in far and far[rest] <= spent:
                    continue
                far[rest] = spent
                lead[rest] = start
                order.append(rest)
                gain = (rest[0] - avatar[0]) * self._gdir
                if best is None or (gain, -spent) > (best[0], -best[1]):
                    best = (gain, spent, start)
        if goal_hit is not None:
            return goal_hit[1]
        if best is not None and best[0] > 0:
            return best[2]
        return curious[1] if curious is not None else None

    def _turn(self, board: Board, avatar: Cell, bg: Sig) -> Cell | None:
        """A gravity switch worth throwing — reachable by click, and safe to fall the other way.

        The switch is the only action on this family that opens ground the body cannot walk to,
        so it is tried when walking has run out, and only when the fall it causes lands on
        something that is not known to kill.
        """
        if not self._flip:
            return None
        self._gdir = -self._gdir
        try:
            rest, support = self._drop(board, avatar, bg)
            if rest == avatar or (support is not None and support in self._lethal):
                return None
            if self._fatal(board, avatar, bg):
                return None
        finally:
            self._gdir = -self._gdir
        best: tuple[int, Cell] | None = None
        for cell, sig in board.items():
            if sig not in self._flip:
                continue
            dist = abs(cell[0] - avatar[0]) + abs(cell[1] - avatar[1])
            if best is None or dist < best[0]:
                best = (dist, cell)
        return best[1] if best else None

    def _probe(self, board: Board, avatar: Cell) -> Cell | None:
        """One click at an unclassified cell, aimed away from the cell underfoot.

        A click anywhere else cannot move the body, so this is the free half of the vocabulary:
        what a tile DOES costs one action to measure and is never paid for twice.
        """
        bg = self._empty
        under = (avatar[0] + self._gdir, avatar[1])
        best: tuple[int, Cell] | None = None
        for cell, sig in board.items():
            if cell in (avatar, under) or sig in self._probed:
                continue
            if bg is not None and self._classified(sig, bg):
                continue
            dist = abs(cell[0] - avatar[0]) + abs(cell[1] - avatar[1])
            if best is None or dist < best[0]:
                best = (dist, cell)
        return best[1] if best else None

    # --- Tool protocol ------------------------------------------------------

    def _read(self, obs: Any) -> tuple[int, int, int, Board, dict[Cell, frozenset[int]]] | None:
        g = settled(obs)
        p, oy, ox, flat = self._lattice(g)
        if not p or flat < _MIN_FIT:
            return None
        board, inks = read_board(g, p, oy, ox)
        if len(board) < _MIN_CELLS:
            return None
        return p, oy, ox, board, inks

    def detect(self, frames: list[Any], obs: Any) -> float:
        if self._refuted or not has_frame(obs):
            return 0.0
        simple, click = availability(obs)
        if not click or len([a for a in simple if a in (1, 2, 3, 4)]) != _LATERAL:
            return 0.0
        read = self._read(obs)
        if read is None:
            return 0.0
        _, _, _, board, inks = read
        avatar = self._avatar(board, inks)
        if avatar is None:
            return 0.0
        bg = self._empty if self._empty is not None else floor_sig(board)
        if self._gdir == 0 and self._infer_gravity(board, avatar, bg) == 0:
            return 0.0
        return 0.9 if self._gdir else 0.6

    def reset(self) -> None:
        """A new board revisits nothing; the VOCABULARY survives, because the tiles do."""
        self._seen = set()
        self._prev = None
        self._first = None
        self._stalls = 0
        self._probed = set()

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Learning needs the frame AFTER the action, so it happens at the top of propose."""

    def _quit(self) -> list[Step]:
        """Hand the turn back, and stop bidding once the board has run out of ideas.

        A tool that keeps answering "nothing" while still claiming the game is a tool the
        harness has to keep asking. Withdrawing is the honest report and it is what lets
        another tool have the rest of the budget.
        """
        self._idle += 1
        if self._idle > _GIVE_UP:
            self._refuted = True
        return []

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs) or "GAME_OVER" in state_name(obs):
            return []
        level = levels_completed(obs)
        if level != self._level:
            self._level = level
            self.reset()
        simple, click = availability(obs)
        lateral = sorted(a for a in simple if a in (1, 2, 3, 4))
        if not click or len(lateral) != _LATERAL:
            return []
        read = self._read(obs)
        if read is None:
            return []
        p, oy, ox, board, inks = read
        avatar = self._avatar(board, inks)
        if avatar is None:
            self._stalls += 1
            if self._stalls > 3:
                self._refuted = True
            return []
        rare = self._singular(inks)
        if not self._avatar_ink and avatar in rare:
            self._avatar_ink = rare[avatar]
        self._at = avatar
        bg = self._empty if self._empty is not None else floor_sig(board)
        # The cell the body occupies is, by construction, one the body can occupy. Left as read
        # it is a tile like any other — an unclassified one — and the tool spends its actions
        # bumping sideways into itself to find out what it is.
        board[avatar] = bg
        if self._died(board):
            self._learn_death(bg)
        else:
            if self._first is None:
                self._first = dict(board)
            self._learn(board, avatar, bg)
        bg = self._empty if self._empty is not None else floor_sig(board)
        if self._gdir == 0:
            self._gdir = self._infer_gravity(board, avatar, bg)
        if self._gdir == 0:
            return []

        # ⛔ Stop on a REVISITED board. A faller with no move left bumps the same wall for the
        # rest of its budget, and this family ENDS a level when the budget runs out.
        stamp = f"{avatar}|{sorted(board.items())}"
        if stamp in self._seen:
            self._stalls += 1
            if self._stalls > 2:
                return self._quit()
        else:
            # A new board is progress; the count is for a tool going in circles, and letting it
            # accumulate across a whole level retires the tool for three stalls it has already
            # walked out of.
            self._seen.add(stamp)
            self._stalls = 0

        goals = self._goals(board, inks, avatar)
        hop = self._search(board, avatar, bg, goals)
        target: Cell | None = None
        if hop is not None:
            dc, opens = hop
            if opens is not None:
                target = opens
                act: Step = (6, (ox + target[1] * p + p // 2, oy + target[0] * p + p // 2))
            else:
                act = (lateral[1] if dc > 0 else lateral[0], None)
        else:
            target = self._turn(board, avatar, bg) or self._probe(board, avatar)
            if target is None:
                self._stalls += 1
                return self._quit()
            self._probed.add(board[target])
            act = (6, (ox + target[1] * p + p // 2, oy + target[0] * p + p // 2))
        after, landing = self._outcome(board, avatar, bg, act, target, lateral)
        self._prev = {
            "level": level,
            "board": board,
            "after": after,
            "avatar": avatar,
            "act": act,
            "target": target,
            "landing": landing,
            "right": lateral[1],
            "goals": {c: board[c] for c in goals},
        }
        self._idle = 0
        return [act]

    def _outcome(
        self,
        board: Board,
        avatar: Cell,
        bg: Sig,
        act: Step,
        target: Cell | None,
        lateral: list[int],
    ) -> tuple[Board, Cell]:
        """The board and the resting place this action is expected to produce.

        ⛔ Kept because the death inference reads it, and reading the PRE-action board instead
        blamed the door the click had just opened. That marked the one tile the tool knows how
        to open as a killer, on the board whose only route is through it, and the run stalled
        with a full vocabulary and nowhere to go.
        """
        after = dict(board)
        if act[0] == 6:
            if target is not None:
                edited = self._edit(board.get(target, bg), bg)
                if edited is not None:
                    after[target] = edited
            return after, self._drop(after, avatar, bg)[0]
        dc = 1 if act[0] == lateral[1] else -1
        tgt = (avatar[0], avatar[1] + dc)
        sig = after.get(tgt)
        if sig is None or not self._is_open(sig, bg):
            return after, avatar
        return after, self._drop(after, tgt, bg)[0]
