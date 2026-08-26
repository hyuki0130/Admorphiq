"""Programmed-piece boards: write the instruction word, then press run.

The mechanic this tool claims is a *deferred* one, and that is what makes it its own tool. Clicking
the board does nothing at all. What the clicks land on is a row of INSTRUCTION CELLS — each a
vertical stack of two-state bit patches — and a run disc. Pressing the disc executes the row left to
right, one instruction per animation frame, and the piece walks the board under that program. The
level is therefore decided BEFORE any motion happens: the tool authors a word, it does not steer.

Four things follow, and each one is a measurement, not a guess.

* **The alphabet is not given.** A bit pattern means whatever the engine says it means and nothing
  in the frame declares it. Two ways in exist and the tool uses both. Where the board carries a
  second, LOCKED instruction row and a set of demo buttons, pressing a button replays that program
  on its own panel — one press buys one instruction's meaning, and the answer arrives whole because
  a single action returns the entire animation as a stack of frames. Where it does not (the first
  board carries no demo), the tool writes a word of DISTINCT patterns into its own row and reads
  the meaning of every one of them off the trajectory of that single run.
* **A run is cheap and safe.** A program that does not win puts the piece back where it started, so
  probing costs one action and never a level. What is not cheap is time: a bar across the top of
  the frame retreats a pixel per action and ends the game when it empties.
* **Walls are visible, so they are read and not walked into.** The floor is a chequer of two
  colours; anything else in the play area that is neither piece nor socket is furniture, and the
  planner routes around it before the first run rather than after a failed one.
* **Landing is not only about position.** The piece has to arrive at the socket's opening at the
  same SIZE, in the same COLOUR, and turned the right way round — the socket's inner tabs are the
  negative of the piece's own notch. So resize, recolour and rotate instructions count toward the
  answer exactly like moves do, and the goal test is the whole four-part condition.

Frame-only throughout: lattice, disc, piece, socket, walls and the alphabet itself are all
recovered from pixels.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

import numpy as np

from admorphiq.tools import segment
from admorphiq.tools.base import Step, frame_2d, has_frame

__all__ = ["ProgramBitsTool"]

# A bit patch draws as a 3-cell bar — lying down on one row, standing up on the next — so the two
# bits of a word are told apart by shape as well as by height. Three is the whole glyph.
_MARK = 3
_MIN_COLS = 3
_MIN_ROWS = 2
# A piece can be scaled up several times over; a wall band is wider than anything this bounds.
_MAX_PIECE = 20
# Probing costs a run each; two is the ceiling before the plan is worth more than the knowledge.
_MAX_PROBE_RUNS = 2
_MAX_ATTEMPTS = 8

Box = tuple[int, int, int, int]  # (x0, y0, x1, y1) inclusive
Pattern = tuple[int, ...]  # the colour of each bit of one instruction cell
Mask = tuple[tuple[bool, ...], ...]
# (dx, dy, dwidth, dheight, quarter turns, colour it leaves the piece — -1 for unchanged)
Effect = tuple[int, int, int, int, int, int]
_INERT: Effect = (0, 0, 0, 0, 0, -1)


@dataclass
class Bar:
    """One instruction row: the x centre of each cell, the y centre of each bit row."""

    cols: list[int]
    rows: list[int]

    @property
    def top(self) -> int:
        return min(self.rows) - 2

    def read(self, g: np.ndarray) -> list[Pattern]:
        return [tuple(int(g[y][x]) for y in self.rows) for x in self.cols]

    def site(self, col: int, row: int) -> tuple[int, int]:
        return (self.cols[col], self.rows[row])


@dataclass
class Board:
    """Everything the mechanic needs, recovered from one frame."""

    bar: Bar
    demo: Bar | None
    run_xy: tuple[int, int]
    selectors: list[tuple[int, int]]
    piece: Box
    piece_colour: int
    goal: Box
    socket: Box
    socket_colour: int
    base: tuple[int, int]
    shape: Mask
    keyed: Mask
    states: tuple[int, int]  # the two states a bit patch can show
    region: Box
    demo_region: Box | None
    walls: np.ndarray


# --- geometry ---------------------------------------------------------------


def _boxes(cells: list[list[tuple[int, int]]]) -> list[Box]:
    out = []
    for c in cells:
        ys = [q[0] for q in c]
        xs = [q[1] for q in c]
        out.append((min(xs), min(ys), max(xs), max(ys)))
    return out


def _colour_components(g: Any, colour: int, region: Box | None = None) -> list[list[tuple[int, int]]]:
    """Connected regions of one colour, optionally clipped to a box.

    Clipping blanks everything outside the box to a sentinel the segmenter refuses, so the one
    shared implementation of connectivity still does the walking.
    """
    n = len(g)
    if region is None:
        grid: Any = g
    else:
        x0, y0, x1, y1 = region
        grid = [
            [int(g[y][x]) if (y0 <= y <= y1 and x0 <= x <= x1) else -1 for x in range(n)]
            for y in range(n)
        ]
    return segment.components(grid, set(range(-1, 64)) - {colour})


def _span(box: Box) -> tuple[int, int]:
    return (box[2] - box[0] + 1, box[3] - box[1] + 1)


def _delta(a: Box, b: Box) -> tuple[int, int, int, int]:
    aw, ah = _span(a)
    bw, bh = _span(b)
    return (b[0] - a[0], b[1] - a[1], bw - aw, bh - ah)


def _sample(g: np.ndarray, box: Box, base: tuple[int, int], hit: int, want: bool) -> Mask:
    """The shape of a box reduced to base resolution.

    A piece keeps its outline at every scale, so the fit test has to be done at one resolution.
    Each base cell is read at the centre of the block it stands for, which is what makes the
    reading survive a piece drawn at double or quadruple size.
    """
    w, h = _span(box)
    sx = max(1, w // base[0])
    sy = max(1, h // base[1])
    out = []
    for j in range(base[1]):
        y = box[1] + j * sy + sy // 2
        row = []
        for i in range(base[0]):
            x = box[0] + i * sx + sx // 2
            if 0 <= y < len(g) and 0 <= x < len(g):
                row.append((int(g[y][x]) == hit) == want)
            else:
                row.append(False)
        out.append(tuple(row))
    return tuple(out)


def _turn(mask: Mask, quarters: int) -> Mask:
    """The mask a quarter of a turn clockwise, `quarters` times."""
    cur = mask
    for _ in range(quarters % 4):
        h = len(cur)
        w = len(cur[0])
        cur = tuple(tuple(cur[h - 1 - j][i] for j in range(h)) for i in range(w))
    return cur


# --- the instruction row ----------------------------------------------------


def _straight_triples(g: np.ndarray) -> list[tuple[int, int, int]]:
    """(cx, cy, colour) of every isolated 3-cell bar — the bit patches of an instruction row."""
    band = segment.edge_band(g.shape)
    out: list[tuple[int, int, int]] = []
    for colour in {int(v) for row in g for v in row}:
        for cells in _colour_components(g, colour):
            if len(cells) != _MARK:
                continue
            ys = sorted(q[0] for q in cells)
            xs = sorted(q[1] for q in cells)
            flat = ys[0] == ys[-1] and xs[-1] - xs[0] == _MARK - 1
            tall = xs[0] == xs[-1] and ys[-1] - ys[0] == _MARK - 1
            if not (flat or tall):
                continue
            cy, cx = ys[1], xs[1]
            if not band[cy][cx]:
                out.append((cx, cy, colour))
    return out


def _uniform_runs(values: list[int], min_len: int) -> list[list[int]]:
    """Maximal stretches of a sorted list whose consecutive gaps are all equal."""
    runs: list[list[int]] = []
    i = 0
    while i < len(values) - 1:
        step = values[i + 1] - values[i]
        j = i + 1
        while j < len(values) - 1 and values[j + 1] - values[j] == step:
            j += 1
        if j - i + 1 >= min_len:
            runs.append(values[i : j + 1])
        i = j
    return runs


def _find_bars(g: np.ndarray) -> tuple[list[Bar], tuple[int, int] | None]:
    """Every instruction row in the frame, plus the two states a bit patch takes."""
    marks = _straight_triples(g)
    if len(marks) < _MIN_COLS * _MIN_ROWS:
        return [], None
    at = {(cx, cy): colour for cx, cy, colour in marks}
    bars: list[Bar] = []
    claimed: set[tuple[int, ...]] = set()
    for cols in _uniform_runs(sorted({cx for cx, _, _ in marks}), _MIN_COLS):
        rows_all = sorted({cy for cx, cy, _ in marks if cx in cols})
        full = [cy for cy in rows_all if all((cx, cy) in at for cx in cols)]
        for rows in _uniform_runs(full, _MIN_ROWS):
            key = tuple(cols)
            if key not in claimed:
                claimed.add(key)
                bars.append(Bar(cols=list(cols), rows=list(rows)))
    if not bars:
        return [], None
    states = Counter()
    for bar in bars:
        for x in bar.cols:
            for y in bar.rows:
                states[at[(x, y)]] += 1
    if len(states) > 2:
        return [], None
    if len(states) == 1:
        # A fully written word shows one state only. That is a legal board, not a failed read — it
        # is exactly the frame one click before the answer runs, and losing the bar there stranded
        # a finished plan without ever pressing the disc.
        only = next(iter(states))
        return bars, (only, only)
    # The word is mostly blank on a board waiting to be written, so the commoner state is "off".
    (off, _), (on, _) = states.most_common()
    return bars, (on, off)


def _controls(g: np.ndarray, strip_top: int) -> list[tuple[Box, int, int]]:
    """(box, colour, cell count) of the compact shapes in the control strip under the rows.

    Bounded to the strip and not merely to "clear of the instruction rows". A piece drawn at triple
    size up on a panel is the same size as the disc and rounder than some of the buttons, and once
    it was mistaken for the disc the tool decided the demo panel was the one it could write to and
    the board stopped being legible at all.
    """
    out: list[tuple[Box, int, int]] = []
    for colour in {int(v) for row in g for v in row}:
        for cells in _colour_components(g, colour):
            if not (16 <= len(cells) <= 200):
                continue
            box = _boxes([cells])[0]
            w, h = _span(box)
            if 6 <= w <= 14 and 6 <= h <= 14 and (box[1] + box[3]) // 2 >= strip_top:
                out.append((box, colour, len(cells)))
    return out


# --- the play area ----------------------------------------------------------


def _cavity(g: np.ndarray, box: Box, colour: int) -> Box | None:
    """The opening in a socket: the extent of everything within it that is not its own wall."""
    xs = [x for y in range(box[1], box[3] + 1) for x in range(box[0], box[2] + 1)
          if int(g[y][x]) != colour]
    ys = [y for y in range(box[1], box[3] + 1) for x in range(box[0], box[2] + 1)
          if int(g[y][x]) != colour]
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _plug_and_socket(g: np.ndarray, region: Box) -> tuple[Box, int, Box, Box, int] | None:
    """(piece, its colour, the opening, the socket, the socket's colour).

    A plug and a socket, and they need NOT share a colour — one board hands the piece in one colour
    and asks for it in another, which is what the recolour instruction is for. They are told apart
    by being solid versus hollow, and the pair is confirmed by FIT: the opening's size is an exact
    scaling of the piece's, in both axes by the same factor. That last test is what keeps a solid
    wall band out of the running, since no wall is a scaled copy of the opening.
    """
    scenery = _bulk(g, region)
    x0, y0, x1, y1 = region
    seen = {int(g[y][x]) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)}
    parts: list[tuple[Box, int, float]] = []
    for colour in seen - scenery:
        for cells in _colour_components(g, colour, region):
            box = _boxes([cells])[0]
            w, h = _span(box)
            if w < 2 or h < 2 or max(w, h) > _MAX_PIECE or len(cells) < 4:
                continue
            parts.append((box, colour, len(cells) / (w * h)))
    best: tuple[float, Box, int, Box, Box, int] | None = None
    for socket, s_colour, s_fill in parts:
        hole = _cavity(g, socket, s_colour)
        if hole is None:
            continue
        hw, hh = _span(hole)
        sw, sh = _span(socket)
        if hw < 2 or hh < 2 or hw >= sw or hh >= sh:
            continue
        for piece, p_colour, p_fill in parts:
            if piece == socket:
                continue
            pw, ph = _span(piece)
            if hw * ph != hh * pw or (max(hw, pw) % min(hw, pw)) or (max(hh, ph) % min(hh, ph)):
                continue
            if p_fill - s_fill < 0.15:
                continue
            if best is None or p_fill - s_fill > best[0]:
                best = (p_fill - s_fill, piece, p_colour, hole, socket, s_colour)
    if best is None:
        return None
    return best[1], best[2], best[3], best[4], best[5]


def _paving(g: np.ndarray, region: Box) -> set[int]:
    """The two colours the play area is tiled with — the floor an obstacle map must forgive."""
    x0, y0, x1, y1 = region
    counts = Counter(int(g[y][x]) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))
    return {c for c, _ in counts.most_common(2)}


def _bulk(g: np.ndarray, region: Box) -> set[int]:
    """Colours that cannot be an object: scenery, chequer, panel frame.

    Defined by SHAPE and not by how much of the panel they cover. Two share-based versions came
    before this and each one failed on a different panel — the second commonest colour is the
    piece itself in a dimmed demo panel, and a piece drawn at quadruple size covers a third of the
    panel it is standing in. What actually separates them is that scenery is either one sprawling
    region or many repeated ones, and a piece is neither.
    """
    out: set[int] = set()
    x0, y0, x1, y1 = region
    for colour in {int(g[y][x]) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)}:
        boxes = _boxes(_colour_components(g, colour, region))
        if len(boxes) > 4 or any(max(_span(b)) > _MAX_PIECE for b in boxes):
            out.add(colour)
    return out


def _obstacles(g: np.ndarray, region: Box, spare: set[int]) -> np.ndarray:
    """A prefix-summed map of everything in the play area a piece cannot stand on.

    The floor is a chequer of two colours, so anything else that is neither the piece nor the
    socket is furniture — a wall, a barrier, the panel's own frame. Reading it off the frame is
    what lets the first run be the winning one; learning each wall by walking into it costs a run
    apiece out of a budget that empties.
    """
    x0, y0, x1, y1 = region
    floor = _paving(g, region) | spare
    mask = np.zeros((66, 66), dtype=np.int32)
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if int(g[y][x]) not in floor:
                mask[y + 1][x + 1] = 1
    return mask.cumsum(0).cumsum(1)


def _hits(prefix: np.ndarray, box: Box) -> bool:
    x0, y0, x1, y1 = box
    if x0 < 0 or y0 < 0 or x1 > 63 or y1 > 63:
        return True
    total = (prefix[y1 + 1][x1 + 1] - prefix[y0][x1 + 1]
             - prefix[y1 + 1][x0] + prefix[y0][x0])
    return bool(total)


# --- planning ---------------------------------------------------------------


def _plan_path(board: Board, vocab: dict[Pattern, Effect],
               bad: set[tuple[int, int]]) -> list[Pattern] | None:
    """The shortest word that lands the piece in the socket, or None.

    A breadth-first walk over piece states rather than a sum over instruction counts. Counting was
    the first version and it is right only while the board is empty: the moment a level puts a wall
    in, the same multiset wins or loses depending on the ORDER, and a plan that cannot be reordered
    has nothing to try after a failed run.

    A state is where the piece is, how big it is, which way round it is and what colour it is,
    because all four are in the win condition.
    """
    slots = len(board.bar.cols)
    start = (board.piece, 0, board.piece_colour)
    seen: dict[tuple[Box, int, int], list[Pattern]] = {start: []}
    queue = [start]
    head = 0
    moves = [(p, e) for p, e in vocab.items() if e != _INERT]

    def landed(state: tuple[Box, int, int]) -> bool:
        box, turns, colour = state
        return (box == board.goal and colour == board.socket_colour
                and _turn(board.shape, turns) == board.keyed)

    if landed(start):
        return []
    while head < len(queue):
        cur = queue[head]
        head += 1
        word = seen[cur]
        if len(word) >= slots:
            continue
        box, turns, colour = cur
        for pattern, (dx, dy, dw, dh, dr, newc) in moves:
            nxt_box = (box[0] + dx, box[1] + dy, box[2] + dx + dw, box[3] + dy + dh)
            state = (nxt_box, (turns + dr) % 4, newc if newc >= 0 else colour)
            if state in seen or (nxt_box[0], nxt_box[1]) in bad:
                continue
            if nxt_box[2] < nxt_box[0] or nxt_box[3] < nxt_box[1]:
                continue
            if (nxt_box[0] < board.region[0] or nxt_box[1] < board.region[1]
                    or nxt_box[2] > board.region[2] or nxt_box[3] > board.region[3]):
                continue
            if nxt_box != board.goal and _hits(board.walls, nxt_box):
                continue
            seen[state] = word + [pattern]
            if landed(state):
                return seen[state]
            queue.append(state)
    return None


class ProgramBitsTool:
    """Author the instruction word a programmed-piece board is asking for, then run it."""

    name = "progbits"

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._vocab: dict[Pattern, Effect] = {}
        self._plan: list[Step] = []
        self._run_step: Step | None = None
        self._pending: str | None = None
        self._ran_from: Board | None = None
        self._tried: set[tuple[int, int]] = set()
        self._bad: set[tuple[int, int]] = set()
        self._probe_runs = 0
        self._attempts = 0
        self._states: tuple[int, int] | None = None

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Learning happens in propose, where the whole animation stack is readable."""

    # -- perception ----------------------------------------------------------

    def _perceive(self, g: np.ndarray) -> Board | None:
        bars, states = _find_bars(g)
        if not bars or states is None:
            return None
        if states[0] == states[1]:
            if self._states is None:
                return None
            states = self._states
        else:
            self._states = states
        strip_top = max(max(b.rows) for b in bars) + 3
        blobs = _controls(g, strip_top)
        solid = [b for b in blobs if b[2] >= 0.6 * (_span(b[0])[0] * _span(b[0])[1])]
        if not solid:
            return None
        run_box = max(solid, key=lambda b: b[2])[0]
        run_xy = ((run_box[0] + run_box[2]) // 2, (run_box[1] + run_box[3]) // 2)
        # The row wired to the disc is the one it sits under; a locked demo row is the other.
        bar = min(bars, key=lambda b: abs(sum(b.cols) / len(b.cols) - run_xy[0]))
        demo = None
        if len(bars) > 1:
            demo = min((b for b in bars if b is not bar),
                       key=lambda b: abs(sum(b.cols) / len(b.cols) - run_xy[0]))
        pitch = bar.cols[1] - bar.cols[0]
        # Two rows means two panels side by side, and the play area of each stops where the other
        # begins. Reaching a fixed distance past the row instead pulls in a one-cell sliver of the
        # neighbour's chequer, which is enough to make the demo piece stop being the only object of
        # its colour and the whole alphabet unlearnable.
        lo, hi = 0, 63
        if demo is not None:
            mid = int((sum(demo.cols) / len(demo.cols) + sum(bar.cols) / len(bar.cols)) / 2)
            lo, hi = (mid + 1, 63) if sum(demo.cols) < sum(bar.cols) else (0, mid - 1)
        region = (max(lo, min(bar.cols) - 2 * pitch), 3,
                  min(hi, max(bar.cols) + 2 * pitch), bar.top - 1)
        found = _plug_and_socket(g, region)
        if found is None:
            return None
        piece, p_colour, goal, socket, s_colour = found
        base = (min(_span(piece)[0], _span(goal)[0]), min(_span(piece)[1], _span(goal)[1]))
        demo_region = None
        if demo is not None:
            dp = demo.cols[1] - demo.cols[0]
            d_lo, d_hi = (0, region[0] - 2) if region[0] > 0 else (region[2] + 2, 63)
            demo_region = (max(d_lo, min(demo.cols) - 2 * dp), 3,
                           min(d_hi, max(demo.cols) + 2 * dp), demo.top - 1)
        # A demo button reads two ways — as its own ring, and as the patch of background the ring
        # encloses — and on these boards only one of the two survives every button, because a ring
        # touching the furniture beside it is no longer a ring. Both are kept and merged by centre.
        sel: list[tuple[int, int]] = []
        for box, _, _ in blobs:
            cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
            if abs(cx - run_xy[0]) + abs(cy - run_xy[1]) < 5:
                continue
            if not any(abs(cx - a) + abs(cy - b) < 5 for a, b in sel):
                sel.append((cx, cy))
        return Board(
            bar=bar, demo=demo, run_xy=run_xy, selectors=sel,
            piece=piece, piece_colour=p_colour, goal=goal,
            socket=socket, socket_colour=s_colour, base=base,
            shape=_sample(g, piece, base, p_colour, True),
            keyed=_sample(g, goal, base, s_colour, False),
            states=states, region=region, demo_region=demo_region,
            walls=_obstacles(g, region, {p_colour, s_colour}),
        )

    # -- learning ------------------------------------------------------------

    def _track(self, layers: np.ndarray, region: Box, start: Box, colour: int,
               base: tuple[int, int], avoid: Box | None,
               floor: set[int]) -> list[tuple[Box, int, Mask]]:
        """The piece frame by frame, followed by identity rather than by colour.

        Two reasons it cannot just watch one colour. The piece and its socket often share one, so
        the extent of that colour is the pair's union and moves half as far as the piece does; and
        one instruction REPAINTS the piece, after which watching its old colour watches nothing.
        Each frame keeps whichever small object, in any colour, is nearest what the piece was.
        """
        shots = [(start, colour, _sample(layers[0], start, base, colour, True))]
        for layer in layers[1:]:
            prev_box, prev_colour, _ = shots[-1]
            best: tuple[int, Box, int] | None = None
            for c in {int(v) for row in layer for v in row} - floor:
                for cells in _colour_components(layer, c, region):
                    if len(cells) < 4:
                        continue
                    box = _boxes([cells])[0]
                    if max(_span(box)) > _MAX_PIECE or box == avoid:
                        continue
                    cost = sum(abs(a - b) for a, b in zip(box, prev_box)) + (0 if c == prev_colour else 2)
                    if best is None or cost < best[0]:
                        best = (cost, box, c)
            if best is None:
                shots.append(shots[-1])
            else:
                shots.append((best[1], best[2], _sample(layer, best[1], base, best[2], True)))
        return shots

    def _absorb(self, layers: np.ndarray, region: Box, bar: Bar, start: Box, colour: int,
                base: tuple[int, int], avoid: Box | None, own: bool) -> None:
        """Attribute each frame-to-frame change to the instruction that caused it."""
        if len(layers) < 2:
            return
        shots = self._track(layers, region, start, colour, base, avoid,
                            _bulk(layers[0], region) - {colour})
        for i, pattern in enumerate(bar.read(layers[-1])):
            if i + 1 >= len(shots):
                break
            (box_a, col_a, mask_a) = shots[i]
            (box_b, col_b, mask_b) = shots[i + 1]
            dx, dy, dw, dh = _delta(box_a, box_b)
            turns = 0
            if (dx, dy, dw, dh) == (0, 0, 0, 0) and mask_a != mask_b:
                for k in (1, 2, 3):
                    if _turn(mask_a, k) == mask_b:
                        turns = k
                        break
            effect: Effect = (dx, dy, dw, dh, turns, col_b if col_b != col_a else -1)
            known = self._vocab.get(pattern)
            if known is None or (known == _INERT and effect != _INERT):
                self._vocab[pattern] = effect
            elif own and known != _INERT and effect == _INERT:
                # The instruction is known to act and this time it did not: the square it asked for
                # is not available. That square is what the next plan routes around, and it is the
                # only thing a failed run is worth.
                self._bad.add((box_a[0] + known[0], box_a[1] + known[1]))

    # -- authoring -----------------------------------------------------------

    def _write(self, board: Board, g: np.ndarray, word: list[Pattern]) -> list[Step]:
        current = board.bar.read(g)
        steps: list[Step] = []
        for col, want in enumerate(word):
            for row, (have, wish) in enumerate(zip(current[col], want)):
                if have != wish:
                    steps.append((6, board.bar.site(col, row)))
        steps.append((6, board.run_xy))
        return steps

    def _probe_word(self, board: Board) -> list[Pattern]:
        """A word of distinct patterns — one run then tells the meaning of each of them."""
        on, off = board.states
        bits = len(board.bar.rows)
        slots = len(board.bar.cols)
        words = [tuple(on if value >> i & 1 else off for i in range(bits))
                 for value in range(min(1 << bits, slots))]
        while len(words) < slots:
            words.append(words[-1])
        return words

    def _launch(self, board: Board, g: np.ndarray, word: list[Pattern]) -> list[Step]:
        self._plan = self._write(board, g, word)
        self._run_step = self._plan[-1]
        return [self._take(board)]

    def _take(self, board: Board | None) -> Step:
        step = self._plan.pop(0)
        if step == self._run_step:
            self._pending = "run"
            self._ran_from = board
        return step

    # -- the contract --------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        if not has_frame(obs):
            return 0.0
        # A word to write, a disc to press, and a piece with a socket to be in: the mechanic is
        # present AND there is a plan. Anything short of all three is not this tool's board.
        return 0.85 if self._perceive(frame_2d(obs)) is not None else 0.0

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        layers = np.asarray(obs.frame)
        if layers.ndim < 3:
            layers = layers[None, ...]
        g = layers[-1]
        board = self._perceive(g)

        if board is not None:
            if self._pending == "demo" and board.demo is not None and board.demo_region is not None:
                seed = self._demo_seed(layers[0], board)
                if seed is not None:
                    self._absorb(layers, board.demo_region, board.demo, seed[0], seed[1],
                                 board.base, None, own=False)
            elif self._pending == "run" and self._ran_from is not None:
                was = self._ran_from
                self._absorb(layers, was.region, was.bar, was.piece, was.piece_colour,
                             was.base, was.socket, own=True)
        self._pending = None

        # A plan already authored is emitted before anything else. Re-reading the board first was
        # what stranded the very first finished word: the last click makes every bit the same
        # colour, the row stops looking like a row, and the disc never gets pressed.
        if self._plan:
            return [self._take(board)]
        if board is None:
            return []

        blank = tuple(board.states[1] for _ in board.bar.rows)
        self._vocab.setdefault(blank, _INERT)

        word = _plan_path(board, self._vocab, self._bad)
        if word is not None:
            self._attempts += 1
            if self._attempts > _MAX_ATTEMPTS:
                return []
            return self._launch(board, g, word + [blank] * (len(board.bar.cols) - len(word)))

        untried = [s for s in board.selectors if s not in self._tried]
        if board.demo is not None and untried:
            self._tried.add(untried[0])
            self._pending = "demo"
            return [(6, untried[0])]

        if board.demo is None and self._probe_runs < _MAX_PROBE_RUNS:
            self._probe_runs += 1
            return self._launch(board, g, self._probe_word(board))
        return []

    def _demo_seed(self, first: np.ndarray, board: Board) -> tuple[Box, int] | None:
        """The one small object in the demo panel, which is the piece the demo is about."""
        assert board.demo_region is not None
        scenery = _bulk(first, board.demo_region)
        best: tuple[int, Box, int] | None = None
        for colour in {int(v) for row in first for v in row} - scenery:
            comps = [c for c in _colour_components(first, colour, board.demo_region) if len(c) >= 4]
            if len(comps) != 1:
                continue
            box = _boxes(comps)[0]
            if max(_span(box)) > _MAX_PIECE:
                continue
            if best is None or len(comps[0]) > best[0]:
                best = (len(comps[0]), box, colour)
        return None if best is None else (best[1], best[2])
