"""Column-transfer boards: material shuttles between pillars and riders align to sockets.

The mechanic, recovered from the frame alone and named in frame terms:

* A board is cut into **lanes** by thin **channels** that run the full depth of the board.
* Each lane holds one **pillar** — a solid column that settles against one end of the depth
  axis (the *settle end*). Its other end is its **face**.
* **Riders** sit on a pillar's face and travel with it. Every rider carries a coloured mark.
* **Sockets** are coloured marks embedded in a channel. A rider is satisfied when its own
  mark lines up, along the depth axis, with the same-coloured socket on a channel that
  borders its own lane. The board is won when every rider is satisfied.
* **Steppers** are identical small squares, each pressed flush against a channel inside one
  pillar's lane. Pressing one moves ONE unit of material out of the pillar across that
  channel and into the pillar the stepper sits in — so the stepper's own pillar grows by a
  unit (its riders slide one unit away from the settle end) and the neighbour shrinks.
* **Gates** are bars parked inside a channel. While the two pillars flanking a gate both
  present their face exactly at the gate's settle-side end, clicking the gate exchanges the
  riders of those two pillars. The exchange plays as an animation during which the board
  swallows every action.

So the whole board is a small integer system: a vector of pillar heights in units, plus a
map of which pillar each rider is riding. A press moves one unit between two neighbours, a
gate swaps two riders sets, and the goal is a set of admissible heights per pillar. That is
searched exactly rather than explored, which matters because these boards END when their
own step allowance runs out.

⛔ The shrinking bar along one board edge is the step allowance, not board content — the
outer band is excluded from perception via ``segment.edge_band``.
"""

from __future__ import annotations

import heapq
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from admorphiq.tools import segment
from admorphiq.tools.base import Step, frame_2d, has_frame

__all__ = ["PillarTransferTool"]

# A stepper is a small square; anything bigger is furniture, not a control.
_MAX_STEPPER_SIDE = 8
# A channel is long in depth; this many units is the shortest one that still separates
# two lanes. Measured: the shortest real channel on these boards runs three units, and a
# rider's body runs less than that, which is what keeps the two apart.
_MIN_CHANNEL_SPAN = 3
# Hard stop on riding out a gate exchange; the real signal is the board going still.
_SETTLE_TICKS = 200
# A gate exchange plays as an animation costing tens of actions, where a press costs one.
# Weighting it keeps the planner from spending a swap it does not need.
_GATE_COST = 10
# Bound on the exact search so a misread board cannot spin.
_SEARCH_NODES = 60000


@dataclass
class _Piece:
    colour: int
    cells: list[tuple[int, int]]
    r0: int
    c0: int
    r1: int
    c1: int

    @property
    def shape(self) -> tuple[int, int]:
        return (self.r1 - self.r0 + 1, self.c1 - self.c0 + 1)


@dataclass
class _Pillar:
    lane_lo: int
    lane_hi: int
    seg_lo: int   # the depth stretch this pillar occupies; a ledge cuts a lane into several
    seg_hi: int
    height: int   # face position, measured from the settle end of its own stretch
    cap: int      # tallest it may stand and still accept another unit


@dataclass
class _Rider:
    mark: int
    pillar: int
    mark_lo: int


@dataclass
class _Socket:
    mark: int
    channel: int
    mark_lo: int


@dataclass
class _Stepper:
    dst: int
    src: int
    click: tuple[int, int]


@dataclass
class _Gate:
    low: int
    high: int
    at_low: int    # the height each flank must stand at; they differ when the two sit in
    at_high: int   # stretches with different feet
    click: tuple[int, int]


@dataclass
class _Board:
    pad: int = 0           # letterbox margin stripped before perception
    axis: int = 0          # 0 -> depth runs down rows, 1 -> depth runs across columns
    sign: int = 1          # +1 when the settle end is the high end of the depth axis
    unit: int = 0
    pillars: list[_Pillar] = field(default_factory=list)
    channels: list[tuple[int, int]] = field(default_factory=list)
    riders: list[_Rider] = field(default_factory=list)
    sockets: list[_Socket] = field(default_factory=list)
    steppers: list[_Stepper] = field(default_factory=list)
    gates: list[_Gate] = field(default_factory=list)


# --- perception -------------------------------------------------------------

def _dechrome(grid: np.ndarray) -> np.ndarray:
    """Erase the step-allowance bar, which is an edge LINE, not board content.

    ⛔ Masking the whole outer band instead clips a pillar and a stepper by a pixel, and a
    stepper measured 4x3 stops looking like the square it is. So only a line that reads as a
    bar — at most two colour runs, and disagreeing with the line just inside it — is
    overwritten, and every other edge pixel survives intact.
    """
    out = np.array(grid)
    h, w = out.shape
    band = segment.edge_band(out.shape, margin_div=64)
    lines = [
        (out[0], out[1], (0, slice(None))),
        (out[h - 1], out[h - 2], (h - 1, slice(None))),
        (out[:, 0], out[:, 1], (slice(None), 0)),
        (out[:, w - 1], out[:, w - 2], (slice(None), w - 1)),
    ]
    for line, inner, where in lines:
        if not band[where[0], where[1]].all():
            continue
        runs = 1 + int(np.count_nonzero(line[1:] != line[:-1]))
        if runs <= 2 and np.count_nonzero(line != inner) >= line.size // 4:
            out[where[0], where[1]] = inner
    return out


def _pieces(grid: np.ndarray, blocked: set[int]) -> list[_Piece]:
    """4-connected same-colour regions of the whole board."""
    h, w = grid.shape
    seen = np.zeros((h, w), dtype=bool)
    out: list[_Piece] = []
    for y in range(h):
        for x in range(w):
            if seen[y, x] or int(grid[y, x]) in blocked:
                continue
            colour = int(grid[y, x])
            seen[y, x] = True
            stack = [(y, x)]
            cells: list[tuple[int, int]] = []
            while stack:
                cy, cx = stack.pop()
                cells.append((cy, cx))
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] \
                            and int(grid[ny, nx]) == colour:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            ys = [q[0] for q in cells]
            xs = [q[1] for q in cells]
            out.append(_Piece(colour, cells, min(ys), min(xs), max(ys), max(xs)))
    return out


def _find_steppers(pieces: list[_Piece]) -> tuple[int, int] | None:
    """(colour, side) of the control squares: the only congruent small square family."""
    by_colour: dict[int, list[_Piece]] = {}
    for p in pieces:
        by_colour.setdefault(p.colour, []).append(p)
    best: tuple[int, int, int] | None = None
    for colour, group in by_colour.items():
        if len(group) < 2:
            continue
        shapes = {p.shape for p in group}
        if len(shapes) != 1:
            continue
        side, wide = next(iter(shapes))
        if side != wide or side > _MAX_STEPPER_SIDE:
            continue
        if best is None or len(group) > best[2]:
            best = (colour, side, len(group))
    return (best[0], best[1]) if best else None


def _span(piece: _Piece, axis: int) -> tuple[int, int]:
    """(lo, hi) of a piece along the given axis (0 = rows, 1 = columns)."""
    return (piece.r0, piece.r1) if axis == 0 else (piece.c0, piece.c1)


def _merge_bands(bands: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Fuse overlapping or touching intervals — a socket splits its own channel in two."""
    out: list[tuple[int, int]] = []
    for lo, hi in sorted(bands):
        if out and lo <= out[-1][1] + 1:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out


def _letterbox(grid: np.ndarray) -> int:
    """Width of the flat border the camera pads a non-64 board with, 0 when there is none.

    Without this the settle end of the depth axis is read as the FRAME's edge rather than the
    BOARD's, and no pillar then appears to reach it — which is the whole basis for deciding
    which way is downhill.
    """
    h, w = grid.shape
    colour = int(grid[0, 0])
    margin = 0
    while margin < min(h, w) // 4:
        ring = (
            grid[margin, :],
            grid[h - 1 - margin, :],
            grid[:, margin],
            grid[:, w - 1 - margin],
        )
        if not all(bool((line == colour).all()) for line in ring):
            break
        margin += 1
    return margin


def _read(raw: np.ndarray) -> _Board | None:
    """Recover the whole board from one frame, or None when the mechanic is not present."""
    full = _dechrome(raw)
    pad = _letterbox(full)
    grid = full[pad:full.shape[0] - pad, pad:full.shape[1] - pad] if pad else full
    bg = segment.background(grid)
    pieces = _pieces(grid, bg)
    if len(pieces) < 4:
        return None
    found = _find_steppers(pieces)
    if found is None:
        return None
    step_colour, unit = found
    steppers = [p for p in pieces if p.colour == step_colour]

    # A channel is a strip exactly one unit thick across its lane and long in depth. A socket
    # embedded in a channel cuts it in two, so fragments are fused by lane band BEFORE the
    # length test — otherwise the longest fragment is mistaken for the whole channel and every
    # pillar's growth ceiling comes out short.
    strips: dict[tuple[int, int], list[_Piece]] = {}
    for p in pieces:
        if p.colour == step_colour:
            continue
        height, width = p.shape
        if height == unit and width > unit:
            strips.setdefault((p.colour, 1), []).append(p)
        elif width == unit and height > unit:
            strips.setdefault((p.colour, 0), []).append(p)
    # ⛔ Gates and even a slim pillar read as strips too, so the family has to be earned, not
    # guessed. Every stepper is pressed FLUSH against a channel, so a family no stepper touches
    # is not the channels; among what survives, the channels show the most bands, and on a tie
    # the greater reach, because a gate only ever occupies part of the channel it sits in.
    ranked: list[tuple[int, int, int, int, list[tuple[int, int]]]] = []
    for (colour, orient), group in strips.items():
        across = 1 - orient
        keep: list[tuple[int, int]] = []
        covered = 0
        for band in _merge_bands([_span(q, across) for q in group]):
            members = [q for q in group if _inside(_span(q, across), band)]
            lo = min(_span(q, orient)[0] for q in members)
            hi = max(_span(q, orient)[1] for q in members)
            if hi - lo + 1 >= _MIN_CHANNEL_SPAN * unit:
                keep.append(band)
                covered += hi - lo + 1
        if not keep:
            continue
        if not all(_adjacent_channel(_span(q, across), keep) for q in steppers):
            continue
        ranked.append((len(keep), covered, colour, orient, keep))
    if not ranked:
        return None
    _, _, chan_colour, axis, channels = max(ranked)
    # Reach is what the channel physically spans, so a gate parked inside it counts too.
    channel_pieces = [
        q for (c, o), group in strips.items() for q in group
        if o == axis and _inside_any(_span(q, 1 - axis), channels)
    ]
    lane = 1 - axis

    board = _Board(pad=pad, axis=axis, unit=unit)

    # Pillars carry the steppers, so the pillar colour is what a stepper is embedded in.
    touching: Counter[int] = Counter()
    h, w = grid.shape
    for p in steppers:
        for cy, cx in p.cells:
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < h and 0 <= nx < w:
                    v = int(grid[ny, nx])
                    if v != step_colour and v != chan_colour and v not in bg:
                        touching[v] += 1
    if not touching:
        return None
    pil_colour = touching.most_common(1)[0][0]

    # Re-component the pillar colour with the stepper cells folded in: a control sitting
    # inside a pillar must not cut that pillar into two.
    blocked = set(range(int(grid.max()) + 2)) - {pil_colour}
    pillar_pieces = [q for q in _pieces(grid, blocked) if len(q.cells) > unit]
    if not pillar_pieces:
        return None

    # Downhill is whichever end of the depth axis the pillars settle against.
    depth_end = (h if axis == 0 else w) - 1
    low = sum(1 for q in pillar_pieces if _span(q, axis)[0] == 0)
    high = sum(1 for q in pillar_pieces if _span(q, axis)[1] == depth_end)
    if low == high:
        return None
    board.sign = 1 if high > low else -1
    board.channels = channels
    settle = depth_end if board.sign > 0 else 0

    # ⛔ Lanes come from the CHANNELS, never from the visible pillars. A pillar emptied by a
    # press disappears from the frame entirely, and reading lanes off what is drawn then
    # renumbers every pillar mid-plan — measured, it broke the plan three presses in.
    # ⛔ A pillar is measured by how far a FULL-WIDTH run of it reaches from the settle end,
    # never by the bounding box of its colour. When a gate comes within reach the board draws
    # a ready-marker in the pillar's own colour, one cell wide, well up the lane — a bounding
    # box swallows it and reports a pillar twice its real height.
    solid = np.isin(grid, [pil_colour, step_colour])
    # A LEDGE is a depth at which a lane is walled across its full width by something that is
    # not pillar and not empty. It cuts the lane into stretches, each holding its own pillar
    # with its own controls, which is why a lane cannot be assumed to hold exactly one.
    barrier = ~solid & ~np.isin(grid, list(bg))
    for lo, hi in _complement(channels, depth_end):
        blocked: list[tuple[int, int]] = []
        for d in range(depth_end + 1):
            line = barrier[d, lo:hi + 1] if axis == 0 else barrier[lo:hi + 1, d]
            if line.all():
                blocked.append((d, d))
        for s0, s1 in _complement(_merge_bands(blocked), depth_end):
            foot = s1 if board.sign > 0 else s0
            height = 0
            while True:
                d = foot - board.sign * height
                if not (s0 <= d <= s1):
                    break
                line = solid[d, lo:hi + 1] if axis == 0 else solid[lo:hi + 1, d]
                if not line.all():
                    break
                height += 1
            board.pillars.append(_Pillar(lo, hi, s0, s1, height, 0))
    reach: list[int] = []
    for ch in channels:
        members = [q for q in channel_pieces if _inside(_span(q, lane), ch)]
        far = (
            min(_span(q, axis)[0] for q in members) if board.sign > 0
            else max(_span(q, axis)[1] for q in members)
        )
        reach.append(abs(settle - far) + 1)
    for i, pil in enumerate(board.pillars):
        board.pillars[i].cap = _cap(pil, channels, reach, depth_end, board.sign)

    leftovers = [
        p for p in pieces
        if p.colour not in (step_colour, chan_colour, pil_colour) and p.colour not in bg
    ]
    body = [p for p in leftovers if not _inside_any(_span(p, lane), channels)]
    if not body:
        return None

    # Riders and sockets are the leftover marks; a mark inside a channel band is a socket.
    for p in leftovers:
        if _inside_any(_span(p, lane), channels):
            band = next(i for i, ch in enumerate(channels) if _inside(_span(p, lane), ch))
            board.sockets.append(_Socket(p.colour, band, _span(p, axis)[0]))
    groups = _cluster(body)
    for group in groups:
        marks = {p.colour for p in group}
        socket_colours = {s.mark for s in board.sockets}
        shared = marks & socket_colours
        if not shared:
            continue
        mark = sorted(shared)[0]
        piece = next(p for p in group if p.colour == mark)
        lane_span = (min(_span(p, lane)[0] for p in group), max(_span(p, lane)[1] for p in group))
        depth_span = (min(_span(p, axis)[0] for p in group), max(_span(p, axis)[1] for p in group))
        idx = _pillar_index(lane_span, sum(depth_span) // 2, board.pillars)
        if idx is None:
            continue
        board.riders.append(_Rider(mark, idx, _span(piece, axis)[0]))
    if not board.riders:
        return None

    # Each stepper feeds the pillar it sits in, drawing from across the channel it hugs.
    for p in steppers:
        s_lane = _span(p, lane)
        s_depth = sum(_span(p, axis)) // 2
        dst = _pillar_index(s_lane, s_depth, board.pillars)
        if dst is None:
            continue
        ch = _adjacent_channel(s_lane, channels)
        if ch is None:
            continue
        src = _across(ch, dst, s_depth, board.pillars)
        if src is None or src == dst:
            continue
        board.steppers.append(
            _Stepper(dst, src, ((p.r0 + p.r1) // 2, (p.c0 + p.c1) // 2))
        )

    # A gate is a bar parked inside a channel — long in depth, one unit across the lane.
    for p in leftovers:
        if not _inside_any(_span(p, lane), channels):
            continue
        d0, d1 = _span(p, axis)
        if d1 - d0 + 1 < 2 * unit:
            continue
        ch = next(i for i, c in enumerate(channels) if _inside(_span(p, lane), c))
        mid = (d0 + d1) // 2
        flank = [
            i for i, pil in enumerate(board.pillars)
            if _borders(pil, channels[ch]) and pil.seg_lo <= mid <= pil.seg_hi
        ]
        if len(flank) != 2:
            continue
        # A gate opens when the flanking faces stand at the cell just past the gate's
        # settle-side end, so its height is that gap — one less than the gate's own reach.
        edge = d1 if board.sign > 0 else d0
        board.gates.append(
            _Gate(flank[0], flank[1],
                  abs(_origin(board.pillars[flank[0]], board.sign) - edge),
                  abs(_origin(board.pillars[flank[1]], board.sign) - edge),
                  ((p.r0 + p.r1) // 2, (p.c0 + p.c1) // 2))
        )
    board.sockets = [s for s in board.sockets if s.mark in {r.mark for r in board.riders}]
    return board


def _origin(pil: _Pillar, sign: int) -> int:
    """The foot of a pillar's own stretch — depths are measured from here, not from the board.

    ⛔ A stretch sitting behind a ledge has its own foot, and a rider carried onto it keeps its
    offset from the FACE, not from the board edge. Measuring both from the board made a level
    look like it needed more material than the whole board holds.
    """
    return pil.seg_hi if sign > 0 else pil.seg_lo


def _complement(bands: list[tuple[int, int]], end: int) -> list[tuple[int, int]]:
    """The lanes: whatever the channels leave behind, in order."""
    out: list[tuple[int, int]] = []
    cursor = 0
    for lo, hi in sorted(bands):
        if lo - 1 >= cursor:
            out.append((cursor, lo - 1))
        cursor = hi + 1
    if cursor <= end:
        out.append((cursor, end))
    return out


def _inside(span: tuple[int, int], band: tuple[int, int]) -> bool:
    return span[0] >= band[0] and span[1] <= band[1]


def _inside_any(span: tuple[int, int], bands: list[tuple[int, int]]) -> bool:
    return any(_inside(span, b) for b in bands)


def _pillar_index(span: tuple[int, int], depth: int, pillars: list[_Pillar]) -> int | None:
    """The pillar in this lane whose depth stretch holds the given depth.

    A lane cut by a ledge holds several pillars, so a lane alone does not name one — and
    a rider travelling through a gate straddles two lanes, so its CENTRE names its lane.
    """
    middle = (span[0] + span[1]) // 2
    fits = [
        i for i, pil in enumerate(pillars)
        if pil.lane_lo <= middle <= pil.lane_hi and pil.seg_lo <= depth <= pil.seg_hi
    ]
    if fits:
        return fits[0]
    near = [i for i, pil in enumerate(pillars) if pil.lane_lo <= middle <= pil.lane_hi]
    if not near:
        return None
    return min(near, key=lambda i: min(abs(pillars[i].seg_lo - depth),
                                       abs(pillars[i].seg_hi - depth)))


def _adjacent_channel(span: tuple[int, int], channels: list[tuple[int, int]]) -> tuple[int, int] | None:
    for ch in channels:
        if ch[1] + 1 == span[0] or ch[0] - 1 == span[1]:
            return ch
    return None


def _borders(pil: _Pillar, ch: tuple[int, int]) -> bool:
    return ch[1] + 1 == pil.lane_lo or ch[0] - 1 == pil.lane_hi


def _across(ch: tuple[int, int], dst: int, depth: int, pillars: list[_Pillar]) -> int | None:
    """The pillar on the far side of a channel, in the stretch facing the given depth."""
    far = [
        i for i, pil in enumerate(pillars)
        if _borders(pil, ch) and not (
            pillars[dst].lane_lo <= pil.lane_lo <= pillars[dst].lane_hi
        )
    ]
    if not far:
        return None
    inside = [i for i in far if pillars[i].seg_lo <= depth <= pillars[i].seg_hi]
    if inside:
        return inside[0]
    return min(far, key=lambda i: min(abs(pillars[i].seg_lo - depth),
                                      abs(pillars[i].seg_hi - depth)))


def _cap(
    pil: _Pillar,
    channels: list[tuple[int, int]],
    reach: list[int],
    depth_end: int,
    sign: int,
    clearance: int,
) -> int:
    """How tall a pillar may stand and still accept another unit.

    A ledge above the pillar binds before any channel does, and a pillar carrying a rider must
    leave the rider room under that ledge; otherwise the SHORTEST bordering channel binds.

    ⛔ Two things this got wrong, each costing a level. The binding channel is the shortest
    bordering one, not the longest — taking the longest let the planner keep feeding a pillar
    the board had already stopped accepting, and it then repeated one dead press until the
    allowance ran out. And reach is measured on the WHOLE channel, never on a fragment: a
    socket cuts a channel in two, and the stub nearest the settle end reports a ceiling less
    than half the real one.
    """
    roofed = pil.seg_lo > 0 if sign > 0 else pil.seg_hi < depth_end
    if roofed:
        return pil.seg_hi - pil.seg_lo + 1 - clearance - 1
    borders = [reach[i] for i, ch in enumerate(channels) if _borders(pil, ch)]
    return (min(borders) - 1) if borders else depth_end


def _cluster(pieces: list[_Piece]) -> list[list[_Piece]]:
    """Group touching pieces — a rider is a body plus its mark, drawn in two colours."""
    owner = list(range(len(pieces)))

    def find(i: int) -> int:
        while owner[i] != i:
            owner[i] = owner[owner[i]]
            i = owner[i]
        return i

    sets = [set(p.cells) for p in pieces]
    for i in range(len(pieces)):
        for j in range(i + 1, len(pieces)):
            a, b = pieces[i], pieces[j]
            if a.r1 + 1 < b.r0 or b.r1 + 1 < a.r0 or a.c1 + 1 < b.c0 or b.c1 + 1 < a.c0:
                continue
            if any((y + dy, x + dx) in sets[j]
                   for y, x in a.cells for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                owner[find(i)] = find(j)
    groups: dict[int, list[_Piece]] = {}
    for i, p in enumerate(pieces):
        groups.setdefault(find(i), []).append(p)
    return list(groups.values())


# --- planning ---------------------------------------------------------------

def _admissible(board: _Board) -> list[list[set[int]]]:
    """admissible[r][p] = the heights of pillar p at which rider r would be satisfied.

    A rider's mark keeps a fixed offset from the face of whatever pillar carries it, and the
    face is fixed by that pillar's height, so one observation pins the whole relation:
    a rider whose mark reads ``m`` while its pillar stands ``h`` tall needs height
    ``h + sign * (m - socket)`` to meet a socket — on ANY pillar bordering that socket's
    channel, which is what makes a gate exchange worth searching.
    """
    table: list[list[set[int]]] = []
    for rider in board.riders:
        seat = board.pillars[rider.pillar]
        # The rider's own constant: what its mark reads once its carrier's foot and height are
        # taken out. It travels with the rider, so it holds on any pillar the rider reaches.
        const = rider.mark_lo - _origin(seat, board.sign) + board.sign * seat.height
        row: list[set[int]] = []
        for pil in board.pillars:
            ok: set[int] = set()
            for socket in board.sockets:
                if socket.mark != rider.mark:
                    continue
                if not _borders(pil, board.channels[socket.channel]):
                    continue
                need = board.sign * (_origin(pil, board.sign) + const - socket.mark_lo)
                # A pillar accepts a unit while it is AT the ceiling, so it may end one unit
                # above it; the search still checks each press for itself.
                if 0 <= need <= pil.cap + board.unit and (need - pil.height) % board.unit == 0:
                    ok.add(need)
            row.append(ok)
        table.append(row)
    return table


def _solve(board: _Board) -> list[tuple[int, int]] | None:
    """Exact shortest sequence as (kind, index), kind 0 = stepper press, 1 = gate."""
    unit = board.unit
    heights = tuple(p.height for p in board.pillars)
    caps = tuple(p.cap for p in board.pillars)
    seats = tuple(r.pillar for r in board.riders)
    want = _admissible(board)
    if any(not any(row) for row in want):
        return None

    def done(hs: tuple[int, ...], st: tuple[int, ...]) -> bool:
        return all(hs[st[i]] in want[i][st[i]] for i in range(len(st)))

    def lower(hs: tuple[int, ...], st: tuple[int, ...]) -> int:
        gap = 0
        for i, seat in enumerate(st):
            opts = want[i][seat]
            gap += min((abs(hs[seat] - o) // unit for o in opts), default=1) if opts else 1
        return gap

    start = (heights, seats)
    if done(*start):
        return []
    seen = {start: 0}
    queue: list[tuple[int, int, int, tuple[Any, ...], list[tuple[int, int]]]] = [
        (lower(*start), 0, 0, start, [])
    ]
    tick = 0
    nodes = 0
    while queue and nodes < _SEARCH_NODES:
        _, cost, _, state, path = heapq.heappop(queue)
        nodes += 1
        hs, st = state
        if seen.get(state, 1 << 30) < cost:
            continue
        moves: list[tuple[tuple[Any, ...], tuple[int, int]]] = []
        for si, stepper in enumerate(board.steppers):
            if hs[stepper.src] < unit or hs[stepper.dst] > caps[stepper.dst]:
                continue
            nh = list(hs)
            nh[stepper.src] -= unit
            nh[stepper.dst] += unit
            moves.append(((tuple(nh), st), (0, si)))
        for gi, gate in enumerate(board.gates):
            if hs[gate.low] != gate.at_low or hs[gate.high] != gate.at_high:
                continue
            ns = tuple(
                gate.high if s == gate.low else gate.low if s == gate.high else s for s in st
            )
            moves.append(((hs, ns), (1, gi)))
        for nxt, move in moves:
            spend = cost + (_GATE_COST if move[0] else 1)
            if seen.get(nxt, 1 << 30) <= spend:
                continue
            seen[nxt] = spend
            if done(*nxt):
                return path + [move]
            tick += 1
            heapq.heappush(queue, (spend + lower(*nxt), spend, tick, nxt, path + [move]))
    return None


# --- tool -------------------------------------------------------------------

class PillarTransferTool:
    """Plans the exact press sequence for a column-transfer board."""

    name = "pillar_transfer"

    def __init__(self) -> None:
        self._last: np.ndarray | None = None
        self._settling = 0
        self._nudge = 0

    def reset(self) -> None:
        self._last = None
        self._settling = 0
        self._nudge = 0

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Nothing to learn here — the board states its own configuration every frame."""

    def detect(self, frames: list[Any], obs: Any) -> float:
        if not has_frame(obs):
            return 0.0
        board = _read(frame_2d(obs))
        if board is None or not board.steppers:
            return 0.0
        return 0.85 if _solve(board) is not None else 0.0

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        grid = frame_2d(obs)
        # ⛔ A gate exchange plays out over tens of frames and swallows every action it eats.
        # Replanning against a moving picture read the travelling rider as already landed,
        # planned from there, and then read it back where it started — a four-action cycle
        # that burned a whole level's allowance without moving anything. So while the board
        # is still moving, do not read it at all: click empty board and wait for it to settle.
        moving = self._last is not None and segment.board_changed(self._last, grid)
        self._last = grid
        if self._settling:
            self._settling -= 1
            if moving:
                return [(6, self._empty(grid))]
            self._settling = 0
        board = _read(grid)
        if board is None:
            return []
        plan = _solve(board)
        if plan is None:
            return []
        if not plan:
            # ⛔ The frame handed back after a level-up still renders the board just finished,
            # so "every rider already satisfied" means the next board has not been drawn yet.
            # One click on empty board pulls it into view; a bounded count stops a misread
            # board from nudging for ever.
            if self._nudge >= 2:
                return []
            self._nudge += 1
            return [(6, self._empty(grid))]  # _empty reads the FULL frame, so no pad shift
        self._nudge = 0
        kind, idx = plan[0]
        if kind == 0:
            row, col = board.steppers[idx].click
            return [(6, (col + board.pad, row + board.pad))]
        row, col = board.gates[idx].click
        self._settling = _SETTLE_TICKS
        return [(6, (col + board.pad, row + board.pad))]

    @staticmethod
    def _empty(grid: np.ndarray) -> tuple[int, int]:
        """A cell of the commonest colour — clicking it touches nothing."""
        bg = segment.background(grid)
        ys, xs = np.where(np.isin(grid, list(bg)))
        if len(ys) == 0:
            return (0, 0)
        return (int(xs[0]), int(ys[0]))
