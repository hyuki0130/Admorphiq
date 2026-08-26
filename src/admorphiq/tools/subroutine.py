"""Subroutine tool — assemble a program out of loose tokens, then run it once.

The mechanic, recovered from frames on one sample game: the top strip is a row of hollow boxes
whose OUTLINE colour spells a target sequence; the middle of the board holds one or more wide
rectangles, each a numbered strip of equally-spaced square slots; the bottom holds a tray of loose
square tokens. Two token shapes exist and they are the whole grammar — a SOLID square emits its
colour into the next target box, a RING square calls the rectangle whose outline is that colour.
Running the assembled program (the single non-click action) walks the first rectangle slot by slot,
recursing through calls, and the level clears when the emitted colour sequence equals the target
row. One wrong colour, one empty slot reached, or falling off the end of the first rectangle
resets the run.

⛔ Why this is a solver and not a search. Every level here is a program-synthesis puzzle whose
answer is EXACT: the tray holds precisely the tokens the solution consumes, and the target row is
longer than the slots, so the calls must be nested to replay a strip more than once. The deepest
level asks for 12 emissions out of 8 slots and needs a rectangle to call ITSELF. Nothing short of
simulating the program finds that, and nothing more than simulating it is needed — measured, the
tool places every token and runs the program ONCE per level.

⛔ Frame-only. Token kind and colour, slot lattice, rectangle identity, target sequence and which
rectangle is the entry point are all derived from the pixels. The interpreter's rules were read at
dev time from the sample game's source; the tool never reads an identifier, a tag or a coordinate.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, has_frame, levels_completed
from admorphiq.tools.segment import background

__all__ = ["SubroutineProgramTool"]

Cell = tuple[int, int]          # (y, x)
Token = tuple[str, int]         # ("emit" | "call", colour)

# The token square. Every piece on these boards — loose token, placed token, empty socket marker —
# is drawn inside a socket of this side, so it is the one length the whole grammar is built on.
_TOK = 4
# A target box is the token square plus its own outline.
_BOX = _TOK + 2
# Sockets inside one rectangle are spaced by the socket pitch: the token square plus its gap.
_PITCH = _TOK + 2
# Distance from a rectangle's outline corner to its first token square.
_INSET = 3
# A rectangle is the socket row plus the margin above and below it.
_RECT_H = _TOK + 2 * _INSET
# Simulated interpreter steps before a candidate program is called non-terminating. A solved level
# needs a few dozen; a runaway self-call would otherwise never return.
_RUN_STEPS = 400


def _grid(obs: Any) -> np.ndarray:
    """The board as it stands NOW.

    ⛔ The LAST layer, not the first. One action here can carry a whole animation — a placement
    fades, and a program run plays out entirely inside a single action and may end on a fresh
    level. Measured: the first layer of a run shows the OLD board mid-execution with most of its
    furniture hidden, which reads as a broken board and plans nonsense.
    """
    arr = np.asarray(obs.frame)
    if arr.ndim >= 3:
        arr = arr[-1]
    return arr.astype(np.int64)


# --- perception -------------------------------------------------------------

def _clear_of(g: np.ndarray, y: int, x: int, h: int, w: int, colour: int) -> bool:
    """Is the one-cell band around the (h, w) patch at (y, x) free of `colour`?

    This is what makes a reading MAXIMAL, and it is load-bearing in both directions: without it
    every 4x4 window inside a filled 6x6 target box reads as a token, and a solid token whose
    neighbour happens to share its colour would read as one wide blob.
    """
    n = len(g)
    for yy in range(y - 1, y + h + 1):
        for xx in range(x - 1, x + w + 1):
            if y <= yy < y + h and x <= xx < x + w:
                continue
            if 0 <= yy < n and 0 <= xx < n and int(g[yy][xx]) == colour:
                return False
    return True


def _tokens(g: np.ndarray, bg: set[int]) -> dict[Cell, Token]:
    """Every loose or placed token, by its square's top-left cell.

    Solid square = emit; square ring with a hollow centre = call. The two shapes are the entire
    instruction set, so reading them is reading the program.
    """
    n = len(g)
    out: dict[Cell, Token] = {}
    for y in range(n - _TOK + 1):
        for x in range(n - _TOK + 1):
            colour = int(g[y][x])
            if colour in bg:
                continue
            patch = g[y:y + _TOK, x:x + _TOK]
            if int(patch.min()) == colour and int(patch.max()) == colour:
                kind = "emit"
                # ⛔ A solid square must be MAXIMAL or every 4x4 window inside a filled target
                # box, and inside the backing strip behind the boxes, reads as a token.
                if not _clear_of(g, y, x, _TOK, _TOK, colour):
                    continue
            else:
                edge = np.ones((_TOK, _TOK), dtype=bool)
                edge[1:-1, 1:-1] = False
                if not (patch[edge] == colour).all() or (patch[~edge] == colour).any():
                    continue
                if len(set(int(v) for v in patch[~edge])) != 1:
                    continue
                # ⛔ No maximality test for a ring. Measured: one level draws a connector in the
                # callee's own colour running out of the underside of a call token, so the ring is
                # NOT isolated — demanding isolation lost that token, and with it the level's whole
                # program. A ring is already a specific enough shape to stand on its own.
                kind = "call"
            out[(y, x)] = (kind, colour)
    return out


def _sockets(g: np.ndarray, bg: set[int]) -> set[Cell]:
    """Empty sockets, reported as the top-left of the token square they would hold.

    An empty socket draws a small centred pip. Anchoring on the pip rather than on the rectangle's
    geometry means a socket is found the same way whether it sits in a rectangle or in the tray.
    """
    n = len(g)
    pip = _TOK - 2
    found: set[Cell] = set()
    for y in range(1, n - pip):
        for x in range(1, n - pip):
            colour = int(g[y][x])
            if colour in bg:
                continue
            patch = g[y:y + pip, x:x + pip]
            if int(patch.min()) != colour or int(patch.max()) != colour:
                continue
            # The pip floats in an otherwise empty square: everything around it is board colour.
            band_ok = True
            for yy in range(y - 1, y + pip + 1):
                for xx in range(x - 1, x + pip + 1):
                    if y <= yy < y + pip and x <= xx < x + pip:
                        continue
                    if not (0 <= yy < n and 0 <= xx < n) or int(g[yy][xx]) not in bg:
                        band_ok = False
                        break
                if not band_ok:
                    break
            if band_ok:
                found.add((y - 1, x - 1))
    return found


def _boxes(g: np.ndarray) -> list[tuple[int, int, int]]:
    """Every unfilled target box, as (y, x, demanded colour), in reading order.

    A box is a square outline one size up from a token whose inside is a single OTHER colour: an
    unfilled box shows its backing, a filled one is solid and is deliberately not read here —
    planning happens on a fresh board where none are filled.
    """
    n = len(g)
    boxes: list[tuple[int, int, int]] = []
    for y in range(n - _BOX + 1):
        for x in range(n - _BOX + 1):
            colour = int(g[y][x])
            patch = g[y:y + _BOX, x:x + _BOX]
            edge = np.ones((_BOX, _BOX), dtype=bool)
            edge[1:-1, 1:-1] = False
            if not (patch[edge] == colour).all() or (patch[~edge] == colour).any():
                continue
            inner = set(int(v) for v in patch[~edge])
            if len(inner) != 1:
                continue
            if _clear_of(g, y, x, _BOX, _BOX, colour):
                boxes.append((y, x, colour))
    return sorted(boxes)


def _rectangles(g: np.ndarray, slots: set[Cell], bg: set[int]) -> list[dict[str, Any]]:
    """Group sockets into the rectangles that hold them.

    Sockets of one rectangle share a row and sit exactly one pitch apart; a run that breaks the
    pitch is a different rectangle. ⛔ The gap between two ADJACENT rectangles' nearest sockets is
    never one pitch — the two outlines and their insets guarantee at least eight cells — so chaining
    on an exact pitch separates them without needing to trace the outlines. The tray is rejected by
    the last check: a loose token has no outline above it.
    """
    rects: list[dict[str, Any]] = []
    rows: dict[int, list[int]] = {}
    for y, x in sorted(slots):
        rows.setdefault(y, []).append(x)
    for y, xs in sorted(rows.items()):
        run = [xs[0]]
        for x in xs[1:]:
            if x - run[-1] == _PITCH:
                run.append(x)
            else:
                rects.append({"y": y, "xs": list(run)})
                run = [x]
        rects.append({"y": y, "xs": run})

    out: list[dict[str, Any]] = []
    for r in rects:
        y0, x0 = r["y"] - _INSET, r["xs"][0] - _INSET
        width = 2 * _INSET + _PITCH * (len(r["xs"]) - 1) + _TOK
        if y0 < 0 or x0 < 0 or x0 + width > len(g) or y0 + _RECT_H > len(g):
            continue
        colour = int(g[y0][x0])
        if colour in bg:
            continue
        if not (g[y0, x0:x0 + width] == colour).all():
            continue
        out.append({"origin": (y0, x0), "colour": colour, "slots": r["xs"], "row": r["y"]})
    # The entry point is the first rectangle in reading order — the one the run's marker starts on.
    return sorted(out, key=lambda t: t["origin"])


class Board:
    """One reading of the board: what the program is, what it must emit, what is left to place."""

    def __init__(self, g: np.ndarray) -> None:
        bg = background(g)
        boxes = _boxes(g)
        toks = _tokens(g, bg)
        # ⛔ An unfilled box's backing is a flat square of exactly a token's size, so it reads as a
        # token of the backing colour. Measured: every level handed the planner four to twelve
        # phantom tokens until the boxes' own interiors were subtracted.
        for by, bx, _ in boxes:
            toks.pop((by + 1, bx + 1), None)
        slots = _sockets(g, bg) | set(toks)
        self.rects = _rectangles(g, slots, bg)
        self.targets = [c for _, _, c in boxes]
        placed = set()
        self.content: list[list[Token | None]] = []
        for rect in self.rects:
            row: list[Token | None] = []
            for x in rect["slots"]:
                cell = (rect["row"], x)
                row.append(toks.get(cell))
                placed.add(cell)
            self.content.append(row)
        self.tray = {c: t for c, t in toks.items() if c not in placed}
        self.by_colour: dict[int, int] = {}
        for i, rect in enumerate(self.rects):
            self.by_colour.setdefault(rect["colour"], i)

    def usable(self) -> bool:
        return bool(self.rects) and bool(self.targets)


# --- the interpreter, run as a search ---------------------------------------

class _Synth:
    """Simulate the program, choosing a token whenever the run reaches an empty socket.

    Deciding the sockets lazily — in execution order, against the target the run is standing on —
    is what keeps this tiny: the emitting choice is forced to one colour, so the only real branching
    is which rectangle to call.
    """

    def __init__(self, board: Board) -> None:
        self.b = board
        self.assign: dict[tuple[int, int], Token] = {}
        self.pool: Counter[Token] = Counter(board.tray.values())

    def solve(self) -> dict[tuple[int, int], Token] | None:
        if not self.b.usable():
            return None
        entry = 0
        return dict(self.assign) if self._arrive(((entry, 0),), 0, _RUN_STEPS) else None

    def _content(self, fi: int, si: int) -> Token | None:
        return self.assign.get((fi, si)) or self.b.content[fi][si]

    def _choices(self, out: int) -> list[Token]:
        want = ("emit", self.b.targets[out])
        picks = [want] if self.pool[want] else []
        picks += sorted(
            t for t, n in self.pool.items()
            if n and t[0] == "call" and t[1] in self.b.by_colour
        )
        return picks

    def _arrive(self, stack: tuple[tuple[int, int], ...], out: int, budget: int) -> bool:
        """The run has landed on a socket."""
        if budget <= 0:
            return False
        fi, si = stack[-1]
        item = self._content(fi, si)
        if item is None:
            for tok in self._choices(out):
                self.assign[(fi, si)] = tok
                self.pool[tok] -= 1
                if self._arrive(stack, out, budget):
                    return True
                self.pool[tok] += 1
                del self.assign[(fi, si)]
            return False
        kind, colour = item
        if kind == "emit":
            # A wrong colour is fatal in the engine, so it is fatal here too.
            return colour == self.b.targets[out] and self._advance(stack, out, budget - 1)
        callee = self.b.by_colour.get(colour)
        if callee is None:
            return False
        # ⛔ The engine refuses a call that would re-enter a rectangle already open at ITS first
        # socket from a caller also at its first socket. Reproduce the refusal exactly: a plan the
        # engine rejects is not a plan.
        if si == 0 and len(stack) >= 2 and (fi, 0) in stack[:-1] and stack[-2][1] == 0:
            return False
        return self._arrive(stack + ((callee, 0),), out, budget - 1)

    def _advance(self, stack: tuple[tuple[int, int], ...], out: int, budget: int) -> bool:
        """The socket is done with; move on, returning from a call if the rectangle ran out."""
        if budget <= 0:
            return False
        if out == len(self.b.targets) - 1:
            return True
        fi, si = stack[-1]
        if si + 1 < len(self.b.content[fi]):
            return self._arrive(stack[:-1] + ((fi, si + 1),), out + 1, budget - 1)
        if len(stack) > 1:
            return self._advance(stack[:-1], out, budget - 1)
        # Off the end of the entry rectangle with targets still empty: the engine resets the run.
        return False


class SubroutineProgramTool:
    """Fill the program's empty sockets from the tray, then run it."""

    name = "subroutine"

    # The engine resets a failed run without moving the tokens back, so a second run of the same
    # program is guaranteed to fail the same way. Two is already one more than the plan needs.
    _MAX_RUNS = 2

    def __init__(self) -> None:
        self._level: int | None = None
        self._runs = 0

    def reset(self) -> None:
        self._runs = 0

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Stateless: the program is re-read from the board every turn."""

    # -- Tool protocol -------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Confidence, which is zero unless a complete program has actually been synthesised.

        ⛔ Nothing weaker is offered on purpose. A tool that bids on "this board looks like slots"
        and then cannot finish costs whichever tool could have solved the game its whole budget.
        """
        return 0.9 if self._plan(obs) is not None else 0.0

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        plan = self._plan(obs)
        if plan is None:
            return []
        board, assign = plan
        for (fi, si), tok in sorted(assign.items()):
            if board.content[fi][si] is not None:
                continue
            source = next((c for c, t in sorted(board.tray.items()) if t == tok), None)
            if source is None:
                return []
            # Aim at drawn content in both clicks — the token's own corner and the socket's pip —
            # rather than at a piece's transparent margin.
            target = (board.rects[fi]["row"] + 1, board.rects[fi]["slots"][si] + 1)
            # Pick the token up, put it down: two clicks, and the engine charges the placement once.
            return [(6, (source[1], source[0])), (6, (target[1], target[0]))]
        self._runs += 1
        return [(5, None)]

    # -- planning ------------------------------------------------------------

    def _plan(self, obs: Any) -> tuple[Board, dict[tuple[int, int], Token]] | None:
        if not has_frame(obs):
            return None
        simple, click = availability(obs)
        # The grammar needs a pointer (click) and a way to start the program (a simple action).
        if not click or not simple:
            return None
        level = levels_completed(obs)
        if level != self._level:
            self._level = level
            self.reset()
        if self._runs >= self._MAX_RUNS:
            return None
        board = Board(_grid(obs))
        assign = _Synth(board).solve()
        if assign is None:
            return None
        return board, assign
