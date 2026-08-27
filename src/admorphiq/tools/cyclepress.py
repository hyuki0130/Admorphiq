"""Cycle-press tool — recover what each control PERMUTES, then turn the board onto its marks.

The mechanic, read off the game's own source rather than probed as a black box: a lattice of
equal square tiles; a set of controls; and, behind each control, one or more ORDERED CYCLES of
lattice slots. Pressing a control advances every slot of every cycle it owns by one place, moving
whatever tile stands there. A level is won when each STATIC marker — four corner blocks ringing a
slot — has a tile of the marker's own colour standing in it.

⛔ WHY THIS IS NOT `track` (the tool that already reads this family). `track` recovers a press by
THREADING the slots that changed into a path or a cycle through the lattice, then checking the
slide replays. That reading is true of the early boards and false of the late ones, and the
falsehood is structural, not a threshold:

  * one control owns SEVERAL cycles at once — nine eight-slot loops on one board, seven three-slot
    loops on another — because the game stacks several controls at the SAME pixel and dispatches
    every one of them;
  * the cycles are not all the same shape: orthogonal loops, DIAGONAL runs and loops whose step is
    TWO lattice cells appear together under one press, so no single adjacency rule threads them;
  * two cycles can run through neighbouring slots, so connectivity merges them into one component
    that threads as nothing.

Measured on the board where this matters: `track` probes all seven controls and recovers exactly
ONE of them, then withdraws. The level is winnable in nineteen presses.

So this tool drops geometry from the RECOVERY and keeps it only as a PREFERENCE. A press is
whatever permutation of the slots reproduces the colours; among the permutations that reproduce
them, the one that moves tiles the shortest total distance is the one kept. That is a preference
rather than a rule because a cycle's closing step is long by construction — the last slot hands
back to the first — and a hard locality limit would forbid exactly that step.

⛔ Frame-only, by construction: the tile side, the lattice pitch, which slots are marked and with
which colour, where the controls are, what each control permutes and how far the board is from
its marks are all DERIVED. Nothing about any game is written down here.

⛔ Selectivity. The bid is the same conjunction `track` measured at 0 false positives over the 25
sample games — a tile lattice at the 3:2 pitch AND a corner-annulus marker wearing a colour some
tile wears — and it drops to zero the moment no press sequence reaches the marks. A tool with no
plan must not compete for the turn.
"""

from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, frame_2d, has_frame
from admorphiq.tools.segment import background, components
from admorphiq.tools.track import markers_on, read_board

__all__ = ["CyclePressTool", "press_points", "recover_permutation"]

Cell = tuple[int, int]

# Bid: one notch above `track`'s on the same conjunction, so that where both read the mechanic
# this one takes the board. Measured over the eight boards of the game they share: `track` clears
# five and this clears eight, and the five are cleared here too.
_CONF = 0.86
# Forbidden assignment. A real cost never approaches it, so the solution is checked against it
# afterwards rather than trusting infinity arithmetic through the potentials.
_BIG = 1e9
# States the press planner may open. The board that needs the most opens ~13k.
_PLAN_STATES = 300_000
# Tiles of one wanted colour past which the plan state stops being a set worth enumerating.
_MAX_MOVERS = 6
# Presses of ONE control before its model is taken on trust. Measured against the game's own cycle
# data over all eight boards: THREE presses recover every control exactly, and one press recovers
# barely any of them.
_MAX_PRESSES = 5
# Consecutive presses a model must PREDICT before the control is left alone. ⛔ One is not enough
# and this was measured, not assumed: a permutation that is wrong in six slots still replays the
# very next press on three of these boards, so confirming on a single hit stopped the probing
# exactly where the model was still wrong and the planner then found no route at all.
_CONFIRM_STREAK = 2
# Budget kept back from probing for the press sequence itself. The longest exact solution over
# those boards is nineteen presses.
_PROBE_RESERVE = 20
# Consecutive plans that the board falsified before the tool concedes the level.
_MAX_REPLANS = 6


# -- how many actions are left ----------------------------------------------


class _BudgetBar:
    """Actions remaining in the level, read off the edge-pinned indicator.

    The indicator is a line of cells at the frame's edge that goes over to a spent colour, one
    cell per action. So the fraction of the line already spent, against the presses this tool has
    actually made, gives both the level's whole budget and what is left of it — without knowing
    the game, and without needing the line's own colours to mean anything.

    ⛔ Why not the shared reader in `tools/budget.py`. That one fixes the indicator's AXIS from the
    first frame in which anything in the edge band changed. On this family that frame has exactly
    ONE cell changed, because the bar spends one cell per action, and a single cell is as much a
    row as a column — so the axis comes back as a row, the count along that row never moves again,
    and the budget reads as unknown forever. Measured on two boards here: the estimate never left
    None however many presses were taken. A bar is identified here only once at least two of its
    cells have gone, which is the first moment the axis is evidence rather than a coin toss.
    """

    def __init__(self) -> None:
        self._first: np.ndarray | None = None
        self._presses = 0
        self._high = 0

    def start(self, g: np.ndarray) -> None:
        """Pin the level's opening frame; the indicator is measured against it."""
        if self._first is None or self._first.shape != g.shape:
            self._first = g.copy()
            self._presses = 0
            self._high = 0

    def spent(self) -> None:
        """One action of the level's budget has been consumed."""
        self._presses += 1

    def remaining(self, g: np.ndarray) -> int | None:
        """Actions left, or None while the frame shows no readable indicator."""
        if self._first is None or self._presses == 0 or self._first.shape != g.shape:
            return None
        # ⛔ The four EXTREME lines only, not the whole edge band. On the boards whose play area
        # fills the frame, board content sits inside the band and moves, so a band-wide reading is
        # neither a row nor a column and comes back as no reading at all. An indicator is pinned to
        # the very edge; a board is not.
        changed = g != self._first
        lines = (changed[0, :], changed[-1, :], changed[:, 0], changed[:, -1])
        used = max(int(line.sum()) for line in lines)
        length = max(len(line) for line in lines)
        # An indicator only ever grows. A count that falls is something else being watched.
        if used < self._high:
            return None
        self._high = used
        if used < 2:
            return None
        if used >= length:
            return 0
        return int(self._presses * (length - used) / used)


# -- perception --------------------------------------------------------------


def press_points(g: Any, tiles: dict[Cell, int], side: int) -> list[Cell]:
    """One pressable point per single-colour region that is neither a tile nor chrome.

    ⛔ Take the tiles OUT of the grid before looking, rather than discarding any region that
    touches one. A control drawn against a tile is 4-connected to it, so the whole thing reads as
    board furniture and the control ceases to exist as far as the tool is concerned. Measured:
    4 controls found on a board that has 8, and the four missing ones were every control that
    turns a cycle in the losing direction.

    ⛔ Split by COLOUR as well as by connectivity. A pair of opposite controls is drawn with its
    two halves TOUCHING on some of these boards, and connectivity alone returns the pair as one
    region whose centre lands on one half.

    ⛔ ONE background colour is blocked here, not the two `read_board` blocks. The budget
    indicator is a bar the height of the frame drawn in a single colour, which makes that colour
    the SECOND commonest on the board — and every control drawn in it then reads as background and
    disappears. Measured: half the controls on one board, all of them turning cycles the same way.
    The surround that the second colour was blocking for is filtered here by size instead, since a
    surround spans the frame and a control does not.

    ⛔ The edge band is excluded because the budget indicator lives there, and a marker's corner
    block is excluded by area because it is a quarter of a tile.
    """
    n = len(g)
    margin = max(1, n // 16)
    blocked = background(g, 1)
    owned = {(y + i, x + j) for (y, x) in tiles for i in range(side) for j in range(side)}
    masked = [[-1 if (y, x) in owned else int(g[y][x]) for x in range(n)] for y in range(n)]
    out: list[Cell] = []
    for cells in components(masked, blocked | {-1}):
        by_colour: dict[int, set[Cell]] = {}
        for (y, x) in cells:
            by_colour.setdefault(int(g[y][x]), set()).add((y, x))
        for region in (r for part in by_colour.values() for r in _regions(part)):
            if len(region) < side * side:
                continue
            ys = [c[0] for c in region]
            xs = [c[1] for c in region]
            if max(ys) - min(ys) >= n // 2 or max(xs) - min(xs) >= n // 2:
                continue
            mid = (sum(ys) / len(region), sum(xs) / len(region))
            # The click must land ON the region: these controls are drawn with a notch, so the
            # bounding-box centre is not always inside them.
            cy, cx = min(region, key=lambda c: (c[0] - mid[0]) ** 2 + (c[1] - mid[1]) ** 2)
            if cy < margin or cy >= n - margin or cx < margin or cx >= n - margin:
                continue
            out.append((cy, cx))
    return sorted(out)


def _regions(cells: set[Cell]) -> list[set[Cell]]:
    """4-connected pieces of a set of cells."""
    unseen = set(cells)
    out: list[set[Cell]] = []
    while unseen:
        start = min(unseen)
        stack = [start]
        seen = {start}
        while stack:
            y, x = stack.pop()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (y + dy, x + dx)
                if nxt in unseen and nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        unseen -= seen
        out.append(seen)
    return out


# -- recovering what a press does --------------------------------------------


def _candidates(slots: list[Cell], pairs: list[tuple[dict[Cell, int], dict[Cell, int]]]) -> dict[Cell, set[Cell]]:
    """Where each slot's tile can have gone, given every press of this control seen so far.

    A press sends the tile on `s` to some `t`, so every recorded pair must show `s`'s old colour
    on `t` afterwards. Each further press of the same control intersects the candidate sets again,
    which is why re-pressing a control is evidence rather than waste.
    """
    by_colour: list[dict[int, set[Cell]]] = []
    for _before, after in pairs:
        index: dict[int, set[Cell]] = {}
        for t, colour in after.items():
            index.setdefault(colour, set()).add(t)
        by_colour.append(index)
    out: dict[Cell, set[Cell]] = {}
    for s in slots:
        keep: set[Cell] | None = None
        for (before, _after), index in zip(pairs, by_colour):
            here = index.get(before[s], set())
            keep = set(here) if keep is None else (keep & here)
            if not keep:
                break
        out[s] = keep or set()
    return out


def _assign(cost: list[list[float]]) -> list[int] | None:
    """Minimum-cost perfect assignment (Hungarian, O(n^3)); None when none exists."""
    n = len(cost)
    if n == 0:
        return []
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [_BIG * 4] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = _BIG * 4
            j1 = 0
            row = cost[i0 - 1]
            ui = u[i0]
            for j in range(1, n + 1):
                if used[j]:
                    continue
                cur = row[j - 1] - ui - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            if j1 == 0:
                return None
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    out = [0] * n
    for j in range(1, n + 1):
        if p[j]:
            out[p[j] - 1] = j - 1
    return None if any(cost[i][out[i]] >= _BIG for i in range(n)) else out


def recover_permutation(slots: list[Cell], pairs: list[tuple[dict[Cell, int], dict[Cell, int]]],
                        pitch: int) -> dict[Cell, Cell] | None:
    """The slot permutation this control applies — the shortest-moving one that replays exactly.

    ⛔ Locality is a preference and never a filter. Every cycle closes: its last slot hands its
    tile back to its first, and on these boards that closing step is up to fifteen lattice cells
    while every other step is one. Forbidding long steps forbids the closure and leaves no
    permutation at all; charging for them leaves exactly one long step per cycle, which is the
    truth.
    """
    if not pairs:
        return None
    cand = _candidates(slots, pairs)
    if any(not c for c in cand.values()):
        return None

    # Forced choices first: a slot with one candidate fixes it and removes that target from every
    # other slot, which usually collapses most of the board before any search is needed.
    fixed: dict[Cell, Cell] = {}
    open_slots = set(slots)
    changed = True
    while changed:
        changed = False
        for s in sorted(open_slots):
            free = cand[s] - set(fixed.values())
            if len(free) == 1:
                fixed[s] = next(iter(free))
                open_slots.discard(s)
                changed = True
            elif not free:
                return None
    rest = sorted(open_slots)
    if rest:
        taken = set(fixed.values())
        targets = sorted({t for s in rest for t in cand[s]} - taken)
        if len(targets) != len(rest):
            return None
        index = {t: j for j, t in enumerate(targets)}
        step = max(1, pitch)
        cost = [[_BIG] * len(targets) for _ in rest]
        for i, s in enumerate(rest):
            for t in cand[s]:
                j = index.get(t)
                if j is not None:
                    cost[i][j] = (abs(t[0] - s[0]) + abs(t[1] - s[1])) / step
        picked = _assign(cost)
        if picked is None:
            return None
        for i, s in enumerate(rest):
            fixed[s] = targets[picked[i]]
    return fixed


def _replays(perm: dict[Cell, Cell], before: dict[Cell, int], after: dict[Cell, int]) -> bool:
    """Does this permutation account for the transition cell for cell?"""
    return all(after.get(perm[s]) == colour for s, colour in before.items() if s in perm)


# -- planning ----------------------------------------------------------------


def plan_presses(tiles: dict[Cell, int], marks: list[tuple[Cell, int]],
                 moves: dict[Cell, dict[Cell, Cell]]) -> list[Cell] | None:
    """Shortest press sequence putting a tile of each marker's colour on that marker's slot.

    Only tiles some press can actually MOVE are carried in the state: a tile no cycle touches is
    scenery, and a marker such a tile already satisfies is satisfied forever. That is what keeps
    the search exact instead of greedy — the widest board here opens ~13k states, not millions.
    """
    movable = {s for mapping in moves.values() for s, t in mapping.items() if s != t}
    want: dict[int, set[Cell]] = {}
    for slot, colour in marks:
        if slot in tiles and tiles[slot] == colour and slot not in movable:
            continue                                     # settled by a tile nothing can move
        want.setdefault(colour, set()).add(slot)
    if not want:
        return []
    colours = sorted(want)
    groups = []
    for c in colours:
        movers = sorted(s for s, v in tiles.items() if v == c and s in movable)
        if not movers or len(movers) > _MAX_MOVERS:
            return None
        groups.append(tuple(movers))
    start = tuple(groups)

    def done(state: tuple[tuple[Cell, ...], ...]) -> bool:
        return all(want[c] <= set(state[i]) for i, c in enumerate(colours))

    if done(start):
        return []
    if not moves:
        return None
    # Several controls can drive the SAME cycles — a board here carries sixteen controls and only
    # four distinct permutations — and keeping the duplicates multiplies the branching for
    # nothing.
    distinct: dict[tuple, Cell] = {}
    for control, mapping in moves.items():
        distinct.setdefault(tuple(sorted(mapping.items())), control)
    generators = [(moves[c], c) for c in distinct.values()]
    seen: dict[tuple, tuple | None] = {start: None}
    queue = deque([start])
    while queue:
        state = queue.popleft()
        for mapping, control in generators:
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
            if len(seen) > _PLAN_STATES:
                return None
    return None


# -- the tool ----------------------------------------------------------------


class CyclePressTool:
    """Learn each control's permutation, then press the board onto its markers."""

    name = "cyclepress"

    def __init__(self) -> None:
        self._signature: tuple | None = None
        self._slots: list[Cell] = []
        self._pitch = 1
        self._pairs: dict[Cell, list[tuple[dict[Cell, int], dict[Cell, int]]]] = {}
        self._perm: dict[Cell, dict[Cell, Cell]] = {}
        self._inert: set[Cell] = set()
        self._streak: dict[Cell, int] = {}
        self._pending: Cell | None = None
        self._before: dict[Cell, int] | None = None
        self._plan: list[Cell] = []
        self._expect: list[dict[Cell, int]] = []
        self._replans = 0
        self._settled = 0
        self._stuck = False
        self._budget = _BudgetBar()
        self._last_frame: np.ndarray | None = None

    def reset(self) -> None:
        """A new board redraws the cycles; everything learned about the old one is void."""
        self.__init__()

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Every fact this tool uses is recomputed from the board, so a transition carries none."""

    # -- Tool protocol ---------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        # ⛔ No mark, no bid; no plan, no bid. Both halves are load-bearing — a lattice that
        # happens to carry a cycle is not this mechanic, and once the board is read and no press
        # sequence reaches the marks, holding the turn only spends another tool's budget.
        if self._stuck or not has_frame(obs):
            return 0.0
        g = frame_2d(obs)
        board = read_board(g)
        if board is None:
            return 0.0
        tiles, side, _pitch = board
        return _CONF if markers_on(g, tiles, side) else 0.0

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        g = frame_2d(obs)
        board = read_board(g)
        if board is None:
            return []
        tiles, side, pitch = board
        self._watch_budget(g)

        signature = (side, pitch, frozenset(tiles))
        if signature != self._signature:
            self.reset()
            self._signature = signature
            self._slots = sorted(tiles)
            self._pitch = pitch

        if self._pending is not None:
            self._learn(tiles)

        marks = markers_on(g, tiles, side)
        if not marks:
            return []
        controls = press_points(g, tiles, side)
        if not controls:
            return []

        if all(tiles.get(slot) == colour for slot, colour in marks):
            return self._nudge(controls)
        self._settled = 0

        probe = self._next_probe(controls)
        if probe is not None:
            self._pending = probe
            self._before = dict(tiles)
            self._plan, self._expect = [], []
            return [(6, (probe[1], probe[0]))]

        if self._plan and self._expect and self._expect[0] == tiles:
            self._expect.pop(0)
            press = self._plan.pop(0)
            self._pending = press
            self._before = dict(tiles)
            return [(6, (press[1], press[0]))]

        if self._replans >= _MAX_REPLANS:
            self._stuck = True
            return []
        found = plan_presses(tiles, marks, self._perm)
        if not found:
            self._stuck = found is None
            return []
        self._replans += 1
        self._plan = found
        self._expect = self._forecast(tiles, found)
        self._expect.pop(0)
        press = self._plan.pop(0)
        self._pending = press
        self._before = dict(tiles)
        return [(6, (press[1], press[0]))]

    # -- probing ---------------------------------------------------------

    def _next_probe(self, controls: list[Cell]) -> Cell | None:
        """The next control to press for evidence, or None when the model is worth planning on.

        Every control is pressed once first — the cheapest complete model there is. A control is
        then pressed AGAIN until its recovered permutation PREDICTS the press, which is the only
        honest test available without an oracle: a permutation that replays the presses seen so
        far always exists, and the wrong one stops replaying as soon as one more press is taken.

        ⛔ The re-presses are gated on the budget indicator, and the gate is what keeps the tool
        off the boards it cannot afford. The first board of this game allows THIRTEEN actions and
        needs five presses to solve; spending four on confirming one control loses it. With too
        few actions observed to read the indicator, no re-press is taken and the plan's own
        falsification is relied on instead.
        """
        unpressed = [c for c in controls if c not in self._pairs and c not in self._inert]
        if unpressed:
            return unpressed[0]
        self._settle()
        unconfirmed = [c for c in controls
                       if c in self._pairs and self._streak.get(c, 0) < _CONFIRM_STREAK
                       and len(self._pairs[c]) < _MAX_PRESSES]
        if not unconfirmed:
            return None
        left = self._budget.remaining(self._last_frame)
        if left is None or left < len(unconfirmed) + _PROBE_RESERVE:
            return None
        return unconfirmed[0]

    def _learn(self, tiles: dict[Cell, int]) -> None:
        """Fold the press just taken into what is known about that control."""
        before, control = self._before, self._pending
        self._pending, self._before = None, None
        if before is None or control is None or set(before) != set(tiles):
            return
        if before == tiles:
            self._inert.add(control)                     # this control turns nothing
            return
        self._pairs.setdefault(control, []).append((before, tiles))
        known = self._perm.get(control)
        if known is not None and _replays(known, before, tiles):
            self._streak[control] = self._streak.get(control, 0) + 1
            return                                       # the model predicted this press
        self._streak[control] = 0
        twin = self._twin(control)
        if twin is not None:
            # Controls come in duplicates: one board here draws SIXTEEN of them over four distinct
            # permutations. Re-deriving a permutation already confirmed elsewhere costs three
            # presses per duplicate — 80 of that board's 150 actions went on exactly that. A
            # confirmed permutation that replays every press this control has made is adopted
            # instead, which is far stronger evidence than the single-press recovery it replaces:
            # the permutation is not being CHOSEN to fit, it was fixed before this control existed.
            self._perm[control] = twin
            self._streak[control] = _CONFIRM_STREAK
            return
        found = recover_permutation(self._slots, self._pairs[control], self._pitch)
        if found is None and len(self._pairs[control]) > 1:
            # No permutation replays ALL of this control's presses, so one of them is not this
            # control's doing — the board moved between the press and the reading. Keeping the
            # contradiction would poison the control forever, since the evidence only ever
            # intersects; the latest press is kept and the rest discarded.
            self._pairs[control] = self._pairs[control][-1:]
            found = recover_permutation(self._slots, self._pairs[control], self._pitch)
        if found is not None:
            self._perm[control] = found
        else:
            self._perm.pop(control, None)

    def _settle(self) -> None:
        """Adopt, for free, every control a confirmed permutation already explains.

        Doing this only when a control is next PRESSED costs one press per duplicate, and the
        duplicates are the majority: sixteen controls over four permutations on one board. The
        evidence is the same either way — it is already on record — so it is spent here instead.
        """
        for control in sorted(self._pairs):
            if self._streak.get(control, 0) >= _CONFIRM_STREAK:
                continue
            twin = self._twin(control)
            if twin is not None:
                self._perm[control] = twin
                self._streak[control] = _CONFIRM_STREAK

    def _twin(self, control: Cell) -> dict[Cell, Cell] | None:
        """A permutation already confirmed on another control that explains this one's presses."""
        for other, perm in self._perm.items():
            if other == control or self._streak.get(other, 0) < _CONFIRM_STREAK:
                continue
            if all(_replays(perm, before, after) for before, after in self._pairs[control]):
                return perm
        return None

    def _nudge(self, controls: list[Cell]) -> list[Step]:
        """The board reads as solved. The win is only TESTED on a press, so make one.

        A frame taken mid-transition can also read as solved, so the first call spends a click off
        the board rather than a press; if the board is still here afterwards the level really did
        arrive satisfied and a press is what tests it.
        """
        self._settled += 1
        if self._settled < 2:
            return [(6, (0, 0))]
        return [(6, (controls[0][1], controls[0][0]))]

    def _watch_budget(self, g: np.ndarray) -> None:
        """Count the presses that cost budget, once per distinct frame.

        A press that costs nothing costs nothing to SEE either: this family ignores a click that
        lands on no control, and the frame — indicator included — comes back identical. So a
        changed frame while a press is outstanding is exactly one action of the budget, which is
        what the indicator has to be divided by.
        """
        if self._last_frame is None:
            self._budget.start(g)
        elif not np.array_equal(g, self._last_frame):
            if self._pending is not None:
                self._budget.spent()
        self._last_frame = g.copy()

    def _forecast(self, tiles: dict[Cell, int], presses: list[Cell]) -> list[dict[Cell, int]]:
        """The board as it should look before each press — the plan's own falsification test."""
        out = []
        state = dict(tiles)
        for press in presses:
            out.append(dict(state))
            mapping = self._perm[press]
            state = {mapping.get(s, s): v for s, v in state.items()}
        return out
