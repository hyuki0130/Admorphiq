"""Phase tool — an avatar walked to its marker over terrain that PANEL BUTTONS re-phase.

The mechanic, recovered from frames. A board sits beside a side panel of buttons. One small
square is the avatar (the simple actions move it one lattice step), another square of the same
size is its destination, and the level clears when the avatar's cell IS the destination cell.
Most of the board is scenery; the parts that matter are drawn in two phases — SOLID, which the
avatar may stand on, and GHOSTED (the phase colour dithered pixel-by-pixel with the board's own
background), which it may not. Each button flips one group of tiles to its next phase, and the
groups are disjoint, so a board layout is the live board with one recorded overlay per group.

⛔ Why plan rather than search. The route is not a path: it needs the terrain re-phased partway
along, from a tile that survives the flip. Reaching the marker means searching (cell, phase
vector) jointly, which a frontier search over cells alone cannot express — measured, the generic
searching path clears nothing here while the declared per-level budget is about twice the human
action count, so there is no room to wander.

⛔ Standing on a tile that the flip GHOSTS drops the avatar, and the drop is charged at twenty
budget steps. Every flip is therefore checked against the avatar's own cell in the phase it is
about to enter, and rejected if that cell stops being solid.

⛔ Frame-only. The avatar and its marker are the two rarest colours, kept only when both are
single congruent squares, and which of the two is the avatar is settled by WHICH ONE MOVED, not
by position. The lattice step, the sense of each action, the buttons and each group's phase
images are all MEASURED by probing. The tool bids on the SIGNATURE, which was measured unique
across the sample set, and latches to 0.0 the moment the mechanic turns out not to be there —
pricing itself on a route it has not been given a turn to find is how it loses the board.

⛔ A button is probed only when the route needs one. Probing every button first spends an action
per button on a budget worth about two human actions per move, and most levels need one flip.
"""

from __future__ import annotations

from collections import Counter, deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, frame_2d, has_frame, levels_completed
from admorphiq.tools.segment import components, edge_band

__all__ = ["PhaseGridTool"]

Cell = tuple[int, int]
_SIMPLE = (1, 2, 3, 4)
# Rotating terrain runs to eight orientations here, so a shorter cap would model the cycle
# wrongly rather than merely incompletely.
_MAX_PHASES = 8
_MAX_BUTTONS = 12
_BFS_CAP = 200000
_MIN_SIDE_COLS = 8
# A board too shallow to hold a route is not this family's board.
_MIN_BOARD_ROWS = 8
# How far down the rarity order the two pieces may sit before the board is not this family's.
_RARE_SCAN = 6
# How many times a blocked direction probe is retried from a fresh cell.
_PROBE_PASSES = 2
# Refusals at distinct cells before a flat colour is condemned board-wide.
_REFUSALS_TO_CONDEMN = 1
# Presses a control gets to reveal its ring before it is dropped from routing.
_MAX_PRESSES = 12
# Repeats of the whole sequence required before a ring length is believed.
_WRAPS_TO_CONFIRM = 2


def _chrome_span(g: np.ndarray) -> tuple[int, int]:
    """First and last row that is not a flat band pinned to the frame's edge.

    ⛔ Two different kinds of chrome sit at the edge and BOTH have to go. The outermost ring
    carries the budget bar, which marches one pixel per action: left in, every click appeared to
    change one more board cell than the one before and no phase cycle ever closed. The flat bands
    inside it are the letterbox. The ring is stripped FIRST, or the bar — never flat — stops the
    band scan at the very first row and the whole letterbox is read as board.
    """
    n = len(g)
    band = edge_band((n, n), n)
    inner = int(np.argmax(~band[:, n // 2])) if band.any() else 0
    limit = n // 4
    top = inner
    while top < limit and len({int(v) for v in g[top]}) == 1:
        top += 1
    bot = n - 1 - inner
    while n - 1 - bot < limit and len({int(v) for v in g[bot]}) == 1:
        bot -= 1
    return top, bot


def _split_columns(g: np.ndarray, top: int, bot: int) -> tuple[int, int] | None:
    """(board width, first panel column) from the columns' own modal colours.

    The board and the panel are two flat grounds side by side; the boundary is where the modal
    colour of a column stops being the modal colour of the frame's first column.
    """
    band = np.asarray(g)[top:bot + 1]
    modal = [Counter(int(v) for v in band[:, x]).most_common(1)[0][0] for x in range(band.shape[1])]
    ground = modal[0]
    # The panel is the band of one ground that REACHES THE FRAME'S EDGE, so it is the terminal run
    # of the column-modal profile — not the first column that differs from the board's ground.
    # ⛔ MEASURED on dc22 level 6, whose profile is
    #     4@0-8  2@9-11  4@12-19  0@20-21  4@22-39  0@40-41  5@42-63
    # The old rule took the FIRST deviation (column 9, an object standing inside the board), found
    # the modal colour to its right was the ground again, and concluded there was no panel — so the
    # tool never read that board on any of its 500 actions and the level has never cleared. The
    # panel is plainly 5@42-63.
    edge = modal[-1]
    if edge == ground:
        return None
    start = len(modal) - 1
    while start > 0 and modal[start - 1] == edge:
        start -= 1
    if start < _MIN_SIDE_COLS or len(modal) - start < _MIN_SIDE_COLS:
        return None
    return start, start


def _one_square(board: np.ndarray, colour: int) -> Cell | None:
    """Top-left corner if `colour` paints exactly one filled square, else None."""
    cells = np.argwhere(np.asarray(board) == colour)
    if not len(cells):
        return None
    y0, x0 = int(cells[:, 0].min()), int(cells[:, 1].min())
    y1, x1 = int(cells[:, 0].max()), int(cells[:, 1].max())
    if (y1 - y0) != (x1 - x0) or len(cells) != (y1 - y0 + 1) ** 2:
        return None
    return y0, x0


def _pieces(board: np.ndarray) -> tuple[int, int, int] | None:
    """(colour, colour, side) for the two rarest colours that each paint ONE congruent square.

    ⛔ Not simply the two rarest. Measured: a board carrying two-tone tokens gave four colours
    tied at the avatar's own pixel count, and taking the rarest two read the halves of a token as
    the pieces. Congruence is what keeps the rule tight — a lone terrain tile is a square too,
    but never the same size as the avatar.
    """
    hist = Counter(int(v) for row in board for v in row)
    if len(hist) < 4:
        return None
    order = [c for c, _ in sorted(hist.items(), key=lambda kv: (kv[1], kv[0]))][:_RARE_SCAN]
    squares: list[tuple[int, int]] = []
    for colour in order:
        if _one_square(board, colour) is None:
            continue
        side = int(round(hist[colour] ** 0.5))
        if side * side != hist[colour] or side < 2 or side > 6:
            continue
        squares.append((colour, side))
    for i, (c0, s0) in enumerate(squares):
        for c1, s1 in squares[i + 1:]:
            if s0 == s1:
                return c0, c1, s0
    return None


class PhaseGridTool:
    """Walk the avatar to its marker, flipping tile groups when the walk needs them."""

    name = "phase_grid"

    def __init__(self) -> None:
        self._level = -1
        self._dead = False
        self.reset()

    # --- lifecycle ---------------------------------------------------------

    def reset(self) -> None:
        self._rare: tuple[int, int] = (-1, -1)
        self._avatar = -1
        self._marker = -1
        self._side = 0
        self._deltas: dict[int, Cell] = {}
        self._to_probe: list[int] = []
        self._probed: list[int] = []
        self._probe_passes = 0
        self._probe_seen: list[tuple[int, dict[int, Cell]]] = []
        self._expect: tuple[Cell, tuple[int, ...]] | None = None
        self._warm = True
        self._settled_clicks: set[Cell] = set()
        self._warps: dict[tuple[Cell, Cell], Cell] = {}
        self._warp_tested: set[tuple[Cell, Cell]] = set()
        self._before_pos: Cell | None = None
        self._visited: set[Cell] = set()
        self._objects: set[Cell] = set()
        self._groups: list[dict[str, Any]] = []
        self._pending: Step | None = None
        self._before: np.ndarray | None = None
        self._blocked: set[tuple[Cell, tuple[int, ...]]] = set()
        self._refused: dict[int, set[Cell]] = {}
        self._not_floor: set[int] = set()
        self._retired = False
        self._plan: list[Step] = []
        self._stalls = 0

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Transitions are re-read from the live frame in propose; nothing to bank here."""

    # --- perception --------------------------------------------------------

    def _read(self, g: np.ndarray) -> dict[str, Any] | None:
        top, bot = _chrome_span(g)
        if bot - top < _MIN_BOARD_ROWS:
            return None
        split = _split_columns(g, top, bot)
        if split is None:
            return None
        right, panel = split
        board = np.asarray(g)[top:bot + 1, 0:right]
        found = _pieces(board)
        if found is None:
            return None
        c0, c1, side = found
        bg = Counter(int(v) for row in board for v in row).most_common(1)[0][0]
        return {"top": top, "bot": bot, "panel": panel, "board": board,
                "bg": bg, "side": side, "rare": (c0, c1)}

    @staticmethod
    def _at(board: np.ndarray, colour: int) -> Cell | None:
        return _one_square(board, colour)

    def _panel_buttons(self, g: np.ndarray, geom: dict[str, Any]) -> list[Cell]:
        """One click point per island in the panel, largest island first.

        ⛔ Re-read every time it is needed, never cached. A control can be UNLOCKED partway
        through a level, and a panel read once at the start cannot see the button that appears.
        """
        top, bot, panel = geom["top"], geom["bot"], geom["panel"]
        strip = np.asarray(g)[top:bot + 1, panel:]
        ground = Counter(int(v) for row in strip for v in row).most_common(1)[0][0]
        # The shared segmentation reads a square grid; seat the strip in one filled with its own
        # ground so the islands it finds are the strip's islands and the coordinates still map.
        side = max(strip.shape)
        square = np.full((side, side), ground, dtype=strip.dtype)
        square[:strip.shape[0], :strip.shape[1]] = strip
        found: list[tuple[int, Cell]] = []
        for cells in components(square.tolist(), {ground}):
            if len(cells) < 4:
                continue
            ys = [c[0] for c in cells]
            xs = [c[1] for c in cells]
            found.append((len(cells), ((min(ys) + max(ys)) // 2 + top, (min(xs) + max(xs)) // 2 + panel)))
        found.sort(key=lambda kv: -kv[0])
        return [c for _, c in found[:_MAX_BUTTONS]]

    # --- the phase model ---------------------------------------------------

    def _layout(self, board: np.ndarray, config: tuple[int, ...]) -> np.ndarray:
        """The board as it would look with every group in the phase `config` names."""
        out = np.array(board, copy=True)
        for index, group in enumerate(self._groups):
            if not group["images"]:
                continue
            for (y, x), colour in group["images"][config[index] % len(group["images"])].items():
                out[y, x] = colour
        return out

    def _signature(self, layout: np.ndarray, cell: Cell) -> tuple[int, ...]:
        """What the tile at `cell` LOOKS like — the key a refusal is remembered under."""
        y, x = cell
        s = self._side
        return tuple(int(v) for v in np.asarray(layout)[y:y + s, x:x + s].ravel())

    def _solid(self, layout: np.ndarray, cell: Cell, bg: int) -> bool:
        """A cell is standable when its whole tile carries no colour known not to be floor.

        A GHOSTED tile is its phase colour dithered with the board's OWN background, so one
        background pixel inside the tile is the whole of the test — and a tile made of two other
        colours still counts as solid, which is what a two-tone token needs.

        ⛔ The background is not the only colour that is not floor, and assuming it was cost a
        whole level. This family draws an EMPTY SLOT where a piece of terrain can sit: a flat
        strip in a colour of its own, permanently visible, that the piece then fills. The slot
        is not the background, so it read as standable, and every route ran along terrain that
        was not there. Which colours behave that way is LEARNED — see `_learn_refusal` — and a
        learned one is then treated exactly like the background, everywhere on the board at
        once, because the discovery is about the colour and not about the cell it turned up in.
        """
        y, x = cell
        s = self._side
        if y < 0 or x < 0 or y + s > layout.shape[0] or x + s > layout.shape[1]:
            return False
        tile = layout[y:y + s, x:x + s]
        if bool((tile == bg).any()):
            return False
        return not any(bool((tile == c).any()) for c in self._not_floor)

    def _items(self, board: np.ndarray, anchor: Cell, bg: int) -> set[Cell]:
        """Solid tiles that are not one flat colour — the board's objects, not its scenery.

        Terrain here is laid out on the same lattice the avatar walks, so a tile of terrain is
        one flat colour and the seam between two terrains falls on a tile edge. A tile that is
        solid and yet mixed is therefore something SITTING on the terrain, and on this family
        that is the only kind of thing worth walking to for its own sake.
        """
        step = self._step()
        s = self._side
        if step <= 0:
            return set()
        h, w = board.shape
        out: set[Cell] = set()
        for y in range(anchor[0] % step, h - s + 1, step):
            for x in range(anchor[1] % step, w - s + 1, step):
                tile = board[y:y + s, x:x + s]
                if (tile == bg).any() or len(np.unique(tile)) == 1:
                    continue
                out.add((y, x))
        return out

    def _step(self) -> int:
        moves = [max(abs(dy), abs(dx)) for dy, dx in self._deltas.values() if dy or dx]
        return min(moves) if moves else 0

    def _reachable(self, board: np.ndarray, start: Cell, bg: int) -> set[Cell]:
        """Every cell the avatar can stand on in SOME measured phase — a diagnostic."""
        out: set[Cell] = set()
        config0 = tuple(gr["phase"] for gr in self._groups)
        cache: dict[tuple[int, ...], np.ndarray] = {config0: np.asarray(board)}
        seen = {(start, config0)}
        queue = deque([(start, config0)])
        while queue and len(seen) < _BFS_CAP:
            pos, cfg = queue.popleft()
            out.add(pos)
            if cfg not in cache:
                cache[cfg] = self._layout(board, cfg)
            grid = cache[cfg]
            for dy, dx in self._deltas.values():
                nxt = (pos[0] + dy, pos[1] + dx)
                if (nxt, cfg) in seen or not self._solid(grid, nxt, bg):
                    continue
                if (nxt, self._signature(grid, nxt)) in self._blocked:
                    continue
                seen.add((nxt, cfg))
                queue.append((nxt, cfg))
            for index, group in enumerate(self._groups):
                if not group["period"]:
                    continue
                nc = list(cfg)
                nc[index] = (cfg[index] + 1) % group["period"]
                ncfg = tuple(nc)
                land = self._warps.get((group["click"], pos), pos)
                if (land, ncfg) in seen:
                    continue
                if ncfg not in cache:
                    cache[ncfg] = self._layout(board, ncfg)
                if not self._solid(cache[ncfg], land, bg):
                    continue
                seen.add((land, ncfg))
                queue.append((land, ncfg))
        return out

    def _route(self, board: np.ndarray, start: Cell, goals: set[Cell], bg: int) -> list[Step]:
        """Shortest action list over (cell, phase vector); a flip costs one action like a move."""
        if not self._deltas or self._step() <= 0 or not goals:
            return []
        config0 = tuple(gr["phase"] for gr in self._groups)
        cache: dict[tuple[int, ...], np.ndarray] = {config0: np.asarray(board)}

        def layout(cfg: tuple[int, ...]) -> np.ndarray:
            if cfg not in cache:
                cache[cfg] = self._layout(board, cfg)
            return cache[cfg]

        seen: dict[tuple[Cell, tuple[int, ...]], list[Step]] = {(start, config0): []}
        queue: deque[tuple[Cell, tuple[int, ...]]] = deque([(start, config0)])
        while queue and len(seen) < _BFS_CAP:
            pos, cfg = queue.popleft()
            trail = seen[(pos, cfg)]
            if pos in goals:
                return trail
            grid = layout(cfg)
            for action, (dy, dx) in self._deltas.items():
                nxt = (pos[0] + dy, pos[1] + dx)
                if (nxt, cfg) in seen or not self._solid(grid, nxt, bg):
                    continue
                if (nxt, self._signature(grid, nxt)) in self._blocked:
                    continue
                seen[(nxt, cfg)] = trail + [(action, None)]
                queue.append((nxt, cfg))
            for index, group in enumerate(self._groups):
                if not group["period"]:
                    continue
                nc = list(cfg)
                nc[index] = (cfg[index] + 1) % group["period"]
                ncfg = tuple(nc)
                # A control moves the avatar only where that was MEASURED; elsewhere it stands.
                land = self._warps.get((group["click"], pos), pos)
                if (land, ncfg) in seen:
                    continue
                # ⛔ A flip that ghosts the tile underfoot drops the avatar; never queue it.
                if not self._solid(layout(ncfg), land, bg):
                    continue
                seen[(land, ncfg)] = trail + [(6, (group["click"][1], group["click"][0]))]
                queue.append((land, ncfg))
        return []

    # --- settling the last action ------------------------------------------

    def _settle_move(self, geom: dict[str, Any], action: int) -> None:
        """Bank where each rare square sits after a simple action; the mover is the avatar."""
        board = geom["board"]
        now = {c: self._at(board, c) for c in self._rare}
        before = self._probe_seen[-1][1] if self._probe_seen else {}
        for colour, pos in now.items():
            was = before.get(colour)
            if was is None or pos is None or pos == was:
                continue
            if self._avatar < 0:
                self._avatar = colour
                self._marker = next(c for c in self._rare if c != colour)
            if colour == self._avatar:
                self._deltas[action] = (pos[0] - was[0], pos[1] - was[1])
        self._probe_seen.append((action, {c: p for c, p in now.items() if p is not None}))

    def _fill_by_elimination(self) -> None:
        """The one action that never moved gets the one displacement nothing else claimed."""
        step = self._step()
        if step <= 0:
            return
        known = set(self._deltas.values())
        missing = [a for a in self._probed if a not in self._deltas]
        unused = [d for d in ((-step, 0), (step, 0), (0, -step), (0, step)) if d not in known]
        if len(missing) == 1 and len(unused) == 1:
            self._deltas[missing[0]] = unused[0]

    def _settle_flip(self, geom: dict[str, Any], click: Cell) -> None:
        """Bank the board this press produced, and find the control's PERIOD.

        ⛔ A phase is a press COUNT, not a picture. Two distinct phases can render identically:
        the terrain here is a bridge that closes in from both ends, so a control with an eight
        press ring shows only five pictures — blank, two, four, six, FULL, six, four, two — and
        the sequence is a palindrome. Identifying phases by their picture merged each picture's
        two occurrences, and the merged "next" then recorded whichever transition was seen last.
        Measured: the FULL bridge became unreachable — nothing in the ring mapped to it — the
        reachable set collapsed to seven cells, and the level was unwinnable in the model while
        the picture that wins it sat in the tool's own table.

        So the ring length is measured instead, by pressing until the SEQUENCE of pictures
        repeats as a sequence, with a second wrap to confirm. After that a press is arithmetic —
        `(phase + 1) % period` — and needs no re-reading of the board at all.
        """
        board = geom["board"]
        if self._before is None or board.shape != self._before.shape:
            return
        # ⛔ Drop the avatar's own pixels. A control that MOVES the avatar redraws it in two
        # places, and folding that into a phase image paints the avatar into the terrain.
        changed = {(int(y), int(x)) for y, x in np.argwhere(board != self._before)
                   if int(board[y][x]) != self._avatar and int(self._before[y][x]) != self._avatar}
        landed = self._at(board, self._avatar)
        if self._before_pos is not None:
            self._warp_tested.add((click, self._before_pos))
            if landed is not None and landed != self._before_pos:
                self._warps[(click, self._before_pos)] = landed
        group = next((gr for gr in self._groups if gr["click"] == click), None)
        if group is None:
            if not changed:
                # An inert control: it is not terrain, so it never enters a route.
                self._settled_clicks.add(click)
                return
            group = {"click": click, "seen": [np.array(self._before, copy=True)],
                     "cells": set(), "period": 0, "phase": 0, "presses": 0,
                     "images": [], "hidden": set()}
            self._groups.append(group)
        group["presses"] += 1
        group["cells"] |= changed
        if group["period"]:
            # The ring is known; a press is arithmetic and the board need not be re-read.
            group["phase"] = (group["phase"] + 1) % group["period"]
            return
        if self._before_pos is not None:
            group["hidden"] |= {c for c in group["cells"] if self._covers(self._before_pos, c)}
        group["seen"].append(np.array(board, copy=True))
        period = self._period_of(group)
        if period:
            group["period"] = period
            group["images"] = [self._image(group, group["seen"][i]) for i in range(period)]
            group["phase"] = (len(group["seen"]) - 1) % period
            self._settled_clicks.add(click)
        elif group["presses"] >= _MAX_PRESSES:
            # No ring within the budget: keep the board honest but never route a flip through
            # a control whose next phase cannot be predicted.
            self._settled_clicks.add(click)

    def _image(self, group: dict[str, Any], snap: np.ndarray) -> dict[Cell, int]:
        """One phase's picture over the group's footprint, minus anything the avatar covered."""
        return {c: int(snap[c[0]][c[1]]) for c in group["cells"] if c not in group["hidden"]}

    def _period_of(self, group: dict[str, Any]) -> int:
        """Smallest ring length the observed sequence of pictures repeats at, twice confirmed.

        ⛔ One repeat is not a ring. A palindromic sequence returns to an earlier picture
        halfway round, so accepting the first match names a period the control does not have.
        """
        seen = [self._image(group, s) for s in group["seen"]]
        n = len(seen)
        for period in range(1, min(_MAX_PHASES, n - 1) + 1):
            pairs = [(i, i + period) for i in range(n - period)]
            if len(pairs) < _WRAPS_TO_CONFIRM:
                break
            if all(seen[i] == seen[j] for i, j in pairs):
                return period
        return 0

    def _learn_refusal(self, board: np.ndarray, cell: Cell) -> None:
        """Generalise a refused move from the cell to the COLOUR it was wearing.

        ⛔ This family draws an EMPTY SLOT where a piece of terrain can sit — a flat strip in a
        colour of its own, permanently visible, that the piece fills when it arrives. The slot
        is not the background, so "no background pixel means standable" called it floor and
        every route ran along terrain that was not there. One refusal settles it for the whole
        board, because the discovery is about the COLOUR, not the cell it turned up in.
        """
        y, x = cell
        s = self._side
        tile = np.asarray(board)[y:y + s, x:x + s]
        if tile.size == 0 or len(np.unique(tile)) != 1:
            return
        colour = int(tile.flat[0])
        if colour in (self._avatar, self._marker):
            return
        seen = self._refused.setdefault(colour, set())
        seen.add(cell)
        if len(seen) >= _REFUSALS_TO_CONDEMN:
            self._not_floor.add(colour)
            # Everything planned against the old reading of the board is now wrong.
            self._plan = []

    def _covers(self, corner: Cell, cell: Cell) -> bool:
        """Does the avatar standing at `corner` hide the pixel `cell`?"""
        return 0 <= cell[0] - corner[0] < self._side and 0 <= cell[1] - corner[1] < self._side

    # --- the harness contract ----------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Confidence this board is the phase mechanic, and that this tool can still act on it.

        ⛔ The signature is a CLAIM, not a guess, so it is bid like one. Every clause below has
        to hold at once: the four senses and a click are offered, the frame splits into a board
        and a panel of different grounds, and the board carries exactly two congruent single
        squares among its rarest colours. Measured over 200 frames of live play on each of the
        25 sample games, with a fresh tool asked on every frame so no accumulated state could
        hide an answer: that conjunction fires on ONE board and returns 0.0 on the other 24,
        first frame and deep frames alike.

        ⛔ An earlier version bid 0.35 before it had a route, which cost the tool the game
        outright: the plan only exists after the probes, the probes only run if the tool gets a
        turn, and the turn goes to whoever bids highest on the FIRST frame. A tool that must
        act to learn cannot price itself on what it has already learned.

        ⛔ The withdrawal is what makes the high bid safe. The moment the premise fails — no
        square moves under any action, the pieces stop being readable, or no route survives
        three re-plans — the tool latches dead and bids 0.0 for the rest of the game, handing
        the board back rather than owning something it cannot finish.
        """
        if self._dead or self._retired or not has_frame(obs):
            return 0.0
        simple, click = availability(obs)
        if not click or not set(_SIMPLE).issubset(set(simple)):
            return 0.0
        if self._read(frame_2d(obs)) is None:
            return 0.0
        return 0.95 if self._plan else 0.85

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if self._dead or self._retired or not has_frame(obs):
            return []
        level = levels_completed(obs)
        if level != self._level:
            self._level = level
            self.reset()
        simple, _ = availability(obs)
        legal = [a for a in _SIMPLE if a in simple]
        if not legal:
            return []
        if self._warm:
            # ⛔ The frame that reports a level cleared still draws the level just finished; one
            # action turns the page before anything on it may be read.
            self._warm = False
            return [(legal[0], None)]

        g = frame_2d(obs)
        geom = self._read(g)
        if geom is None:
            return []

        if self._rare == (-1, -1):
            self._rare, self._side = (geom["rare"][0], geom["rare"][1]), geom["side"]
            self._to_probe = list(legal)
            self._probed = list(legal)
            self._probe_seen = [(0, {c: self._at(geom["board"], c) for c in self._rare})]

        if self._pending is not None:
            pending, self._pending = self._pending, None
            if pending[0] == 6 and pending[1] is not None:
                expected = self._expect
                self._expect = None
                self._settle_flip(geom, (pending[1][1], pending[1][0]))
                landed = self._at(geom["board"], self._avatar)
                if expected is None or expected != (landed, self._config()):
                    # ⛔ The flip did not land where the route said. Re-plan against what is
                    # true — but only then: re-planning after EVERY flip re-runs a search over
                    # the whole phase space for nothing, and the space is exponential in the
                    # number of controls.
                    self._plan = []
            elif self._expect is None:
                # No prediction was attached, so this was a probe: read the sense off the result.
                self._settle_move(geom, pending[0])
            else:
                self._settle_step(geom, pending)

        if self._to_probe:
            self._pending = (self._to_probe.pop(0), None)
            return [self._pending]
        if self._avatar >= 0 and len(self._deltas) < 3 and self._probe_passes < _PROBE_PASSES:
            # ⛔ A start corner can block two of the four senses at once, and elimination needs
            # three of them. The probes that came back empty are re-run from wherever the ones
            # that worked have carried the avatar.
            missing = [a for a in self._probed if a not in self._deltas]
            if missing and self._deltas:
                self._probe_passes += 1
                self._to_probe = missing
                self._probe_seen = [(0, {c: self._at(geom["board"], c) for c in self._rare})]
                self._pending = (self._to_probe.pop(0), None)
                return [self._pending]

        if self._avatar < 0:
            # Neither square moved under any simple action: this is not the mechanic.
            self._dead = True
            return []
        self._fill_by_elimination()

        start = self._at(geom["board"], self._avatar)
        goal = self._at(geom["board"], self._marker)
        if start is None or goal is None:
            # Could be an animation drawing over a piece; give up on the level, not the game.
            self._retired = True
            return []
        if start == goal:
            # The premise says this clears the level. If the frame still says otherwise, the
            # pieces were misread — count it against the stall budget rather than owning the
            # board while proposing nothing.
            self._stalls += 1
            if self._stalls > 2:
                self._retired = True
            return []
        if start not in self._visited:
            self._visited.add(start)
            # Standing somewhere new can UNLOCK a control, so the route in hand is stale.
            self._plan = []
        # ⛔ Objects are remembered, not re-read on demand. The avatar HIDES the tile it stands
        # on, so a tile walked to stops looking like an object the moment it is reached — and
        # the press that has to happen there would never be offered.
        self._objects |= self._items(geom["board"], start, geom["bg"])

        if self._plan:
            return [self._emit(geom, start, self._plan.pop(0))]

        board, bg = geom["board"], geom["bg"]
        self._plan = self._route(board, start, {goal}, bg)
        if self._plan:
            self._stalls = 0
            return [self._emit(geom, start, self._plan.pop(0))]

        # No route to the marker in the world as measured. Enlarge it, cheapest first: a control
        # whose phases are unmeasured, then an object nobody has stood on.
        panel = self._panel_buttons(g, geom)
        for click in panel:
            if click not in self._settled_clicks:
                return [self._emit(geom, start, (6, (click[1], click[0])))]

        wanted = self._objects - self._visited
        self._plan = self._route(board, start, wanted, bg)
        if self._plan:
            self._stalls = 0
            return [self._emit(geom, start, self._plan.pop(0))]

        # ⛔ Last resort, and only while standing ON an object: press a control here and watch
        # the AVATAR, not the terrain. A control's effect on the avatar is measured, never
        # assumed — on this family one of them moves it, and no amount of terrain phasing
        # reaches the rest of the board without that. An empty tile is not a reason to press.
        if start in self._objects:
            for click in panel:
                if (click, start) not in self._warp_tested:
                    return [self._emit(geom, start, (6, (click[1], click[0])))]

        # ⛔ Running out of route RETIRES the tool for this level only. Making it permanent
        # meant that a level another tool went on to clear was handed back to a tool that had
        # already declared itself finished with the whole game.
        self._stalls += 1
        if self._stalls > 2:
            self._retired = True
        return []

    def _emit(self, geom: dict[str, Any], start: Cell, step: Step) -> Step:
        self._before = np.array(geom["board"], copy=True)
        self._before_pos = start
        self._expect = (self._advance(start, step), self._predict(step))
        self._pending = step
        return step

    def _predict(self, step: Step) -> tuple[int, ...]:
        """The phase vector this step should leave behind."""
        config = list(self._config())
        if step[0] == 6 and step[1] is not None:
            click = (step[1][1], step[1][0])
            for index, group in enumerate(self._groups):
                if group["click"] == click and group["period"]:
                    config[index] = (config[index] + 1) % group["period"]
        return tuple(config)

    def _config(self) -> tuple[int, ...]:
        return tuple(gr["phase"] for gr in self._groups)

    def _advance(self, cell: Cell, step: Step) -> Cell:
        if step[0] == 6 and step[1] is not None:
            return self._warps.get(((step[1][1], step[1][0]), cell), cell)
        dy, dx = self._deltas.get(step[0], (0, 0))
        return cell[0] + dy, cell[1] + dx

    def _settle_step(self, geom: dict[str, Any], step: Step) -> None:
        """Check the planned move landed where the model said; if not, learn the wall."""
        if self._expect is None:
            return
        target, _ = self._expect
        self._expect = None
        if step[0] == 6:
            return
        now = self._at(geom["board"], self._avatar)
        if now == target:
            return
        # ⛔ The model said standable and the engine disagreed. Remember the refusal against
        # what the tile LOOKED like, not against the phase vector it was tried under: this
        # family draws a dead copy of a piece where the piece used to be, so the same picture
        # means the same answer, while a phase vector over several many-orientation controls
        # names a state the route will never stand in twice.
        self._blocked.add((target, self._signature(geom["board"], target)))
        self._learn_refusal(geom["board"], target)
        self._plan = []
