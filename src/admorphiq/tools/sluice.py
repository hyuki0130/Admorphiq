"""Sluice — release a scripted flow into every cup, by simulating the release before committing.

THE MECHANIC, recovered from frames. The board is a lattice of cells carrying five roles, and
every role is read by SHAPE or by POSITION, never by colour, because the colours move: the piece
the player currently holds is repainted, so the same bar is one colour on one frame and another
on the next.

    emitter   a lone cell pinned against the board's rim, with its first droplet one step inside.
              The emitter/droplet PAIR is what names the flow direction; nothing else on the
              board does, and two of the six boards in this family render upside down.
    droplet   a lone cell of a second colour: flow already standing on the board.
    cup       five cells forming a 2x3 rectangle with the MIDDLE of one long side missing. That
              missing cell is the mouth and it is the only way in.
    band      a whole edge row or column in one colour. Flow that touches it loses the attempt.
    piece     a solid straight run, or a three-cell elbow. These, and only these, slide. A piece
              may carry an emitter INSIDE it, where it renders as two runs either side of a
              differently coloured cell and must be rejoined or the piece's width is wrong.

THE LEVEL IS TWO PHASES. In the first, one click selects a piece and the four direction actions
slide it a cell at a time; each of those actions spends a per-level allowance the board draws as
a bar along the frame's rim. A fifth action COMMITS, and the entire release then plays out inside
that single action — the observation comes back carrying every tick of the flow as a separate
frame layer. The level clears when the settled flow has entered EVERY cup through its mouth and
has touched the band nowhere. A losing commit restores the layout but not the attempt counter,
and the game ENDS on the fifth attempt.

THE PROPAGATION RULE is the whole tool. A droplet carries a heading; it looks one cell ahead:

    empty     it advances, keeping its heading.
    droplet   it merges into the front already standing there.
    piece     it is pushed ASIDE — a droplet appears in each of the two cells flanking its
              CURRENT position across the axis of travel, both keeping the old heading.
    cup       if BOTH flanks belong to that same cup the cup is satisfied and the droplet is
              consumed; otherwise the cup pushes aside exactly as a piece does. This is why the
              mouth is the middle of a LONG side: only there do both flanks lie in the cup.
    elbow     if exactly one flank is that same elbow and the other flank is empty, the droplet
              turns a quarter turn — and which flank it was decides both the direction AND
              whether the droplet ALSO spreads sideways (one of the two cases does both, the
              other does not; the asymmetry is measured, not assumed). Otherwise it pushes aside.
    band      the attempt is lost.
    anything else   the droplet stops.

⛔ WHERE A TOOL THAT HAS THE MECHANIC RIGHT STILL STOPS — measured, not guessed, because it is
the one thing this tool exists to fix. On this family's deepest board, three of the four pieces
must move, and the winning layout asks for two things a planner is tempted to forbid: two of those
pieces come to REST touching a piece of another colour, and the third can only reach its place by
sliding PAST pieces that have not moved yet. Both are legal — the engine refuses a slide that
would meet a cup, the band or the rim, and MOVES ANYWAY when everything it meets is another
piece — so a planner that treats pieces as obstacles to each other is searching a board the game
does not have. Measured on it: that planner reaches 63 of the 159 places the third piece can
actually stand, the winning layout is not among them, and its search returns nothing after ten
seconds — while its own propagation model, handed that layout directly, correctly reports a
clear. The mechanic was never the thing missing.

So this tool keeps exactly one separation rule, and only where it earns its keep: two pieces of
the SAME colour may not touch, because they would read back as one component on the next frame and
every plan after that would be about an object that does not exist. Different colours may touch,
and any piece may slide through any other.

⛔ WHAT MAKES THIS A PLANNING PROBLEM AND NOT A SEARCH ONE. The boards declare an allowance of
30 to 120 slides and END on overrun, while the flow itself is a pure function of the layout. So
the tool never explores: it recovers the rule, runs it as a simulator over candidate layouts, and
spends actions only on a layout its own model says wins. Measured against the engine on all six
boards of the family: the predicted droplet set is CELL-EXACT with the released flow, on the
starting layout of every one of them.

⛔ THE DIRECTION MAP IS MEASURED, NOT ASSUMED. On boards rendered upside down the CONTROLS are
rotated with the view, so the natural reading happens to hold — but that is a fact about these
six boards, not about the family. The tool starts from the natural map, watches what its own
first slide actually did, and rewrites the map from that observation before planning the rest.

⛔ AND THE MODEL IS CHECKED AGAINST THE RELEASE IT PREDICTED. The commit's own frame stack is the
whole trajectory; the tool compares the droplet cells it predicted with the ones that appeared. A
disagreement means the recovered rule is wrong for this board, and the tool then stops bidding
rather than spending three more attempts being confidently wrong.
"""

from __future__ import annotations

import heapq
import time
from collections import Counter, deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, connected_components, has_frame, levels_completed
from admorphiq.tools.segment import background as _modal_colours

__all__ = ["SluiceTool"]

Cell = tuple[int, int]          # (row, col) in DISPLAY space throughout

# The natural reading of the four direction actions. A PRIOR only — `observe` overwrites any
# entry the board contradicts.
_NATURAL: dict[Cell, int] = {(-1, 0): 1, (1, 0): 2, (0, -1): 3, (0, 1): 4}
_COMMIT = 5

_LATCH = 3          # cells of clearance the engine refuses to place a piece within, upstream
_TICKS = 600        # a release that has not settled by here is a model failure, not a win
_ATTEMPTS = 4       # the fifth commit ends the game
_PLAN_SECONDS = 20.0
_EXACT_COST = 12    # how far the cheapest-first sweep goes before the guided pass takes over
_EXACT_NODES = 60000
_GUIDED_NODES = 300000
_MISS = 4           # how hard an unsatisfied cup pulls the guided search
# The deepest plan the search will consider. MEASURED on this family: the cheapest winning layout
# per board costs 4, 7, 10, 26, 33 and 31 presses, against per-level allowances of 30, 45, 100,
# 120, 100 and 120 — so 60 admits every answer these boards have while keeping the search bounded.
# ⛔ It is NOT read off the board. The allowance is drawn as a two-tone bar along the frame's rim
# and what it shows is the FRACTION still unspent, which at the start of a level — the only moment
# the plan is made — is a single flat colour carrying no magnitude at all.
_MAX_PRESSES = 60


# --- reading the frame -------------------------------------------------------

def _stack(obs: Any) -> np.ndarray:
    """Every layer of the observation, as (layers, h, w).

    ⛔ This tool reads the STACK, deliberately, and both ends of it. The frame layers on this
    family are an animation timeline, not a z-order: a commit returns the entire release as
    successive layers, so the last layer is the settled board and the union over all of them is
    the trajectory. Reading only `arr[0]`, as the shared reader does, would plan against the
    board as it stood before the action resolved. See concepts/frame_layer_timeline.
    """
    arr = np.asarray(getattr(obs, "frame", None))
    if arr.ndim == 2:
        arr = arr[None]
    return arr.astype(int)


def _blocks(px: np.ndarray, n: int, s: int, off: int) -> tuple[np.ndarray, float]:
    """The board read at n cells of side s, plus how flat those cells actually are.

    A cell's value is its CENTRE pixel and never its corner: the allowance bar is painted over
    the outermost pixel row of the frame, so a corner read returns the bar on every cell of the
    row it crosses. For the same reason a cell still counts as flat when one of its pixel rows
    disagrees.
    """
    grid = px[off:off + n * s, off:off + n * s]
    cells = grid.reshape(n, s, n, s).transpose(0, 2, 1, 3).reshape(n, n, s * s)
    mid = cells[:, :, (s // 2) * s + s // 2]
    agree = (cells == mid[:, :, None]).sum(-1)
    return mid, float((agree >= s * s - s).mean())


def _lattice(px: np.ndarray) -> tuple[int, int, int] | None:
    """(cells per side, pixels per cell, letterbox offset) — coarsest reading that is flat."""
    if px.ndim != 2 or px.shape[0] != px.shape[1]:
        return None
    h = px.shape[0]
    for side in range(8, 1, -1):
        for off in range(0, 5):
            span = h - 2 * off
            if span <= 0 or span % side:
                continue
            n = span // side
            if not 8 <= n <= 32:
                continue
            if _blocks(px, n, side, off)[1] >= 0.95:
                return n, side, off
    return None


def _mouth(cells: list[Cell]) -> tuple[Cell, Cell] | None:
    """(mouth cell, the heading a droplet must carry to enter), or None if this is not a cup."""
    if len(cells) != 5:
        return None
    have = set(cells)
    r0, c0 = min(c[0] for c in cells), min(c[1] for c in cells)
    r1, c1 = max(c[0] for c in cells), max(c[1] for c in cells)
    hgt, wid = r1 - r0 + 1, c1 - c0 + 1
    if {hgt, wid} != {2, 3}:
        return None
    gap = [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1) if (r, c) not in have]
    if len(gap) != 1:
        return None
    mr, mc = gap[0]
    if wid == 3 and mc == c0 + 1 and mr in (r0, r1):
        return gap[0], ((1, 0) if mr == r0 else (-1, 0))
    if hgt == 3 and mr == r0 + 1 and mc in (c0, c1):
        return gap[0], ((0, 1) if mc == c0 else (0, -1))
    return None


def _kind(cells: list[Cell]) -> str:
    """`bar` for a solid straight run of two or more, `elbow` for a three-cell corner, else ``."""
    r0, c0 = min(c[0] for c in cells), min(c[1] for c in cells)
    r1, c1 = max(c[0] for c in cells), max(c[1] for c in cells)
    hgt, wid = r1 - r0 + 1, c1 - c0 + 1
    if len(cells) == hgt * wid and min(hgt, wid) == 1 and max(hgt, wid) >= 2:
        return "bar"
    if len(cells) == 3 and hgt == 2 and wid == 2:
        return "elbow"
    return ""


class Piece:
    """One slidable object: its shape about its own top-left, and which of its cells emit."""

    __slots__ = ("shape", "origin", "emits", "kind", "colour")

    def __init__(self, cells: list[Cell], kind: str, emits: list[Cell], colour: int) -> None:
        r0, c0 = min(c[0] for c in cells), min(c[1] for c in cells)
        self.origin: Cell = (r0, c0)
        self.shape = tuple(sorted((r - r0, c - c0) for r, c in cells))
        self.emits = tuple(sorted((r - r0, c - c0) for r, c in emits))
        self.kind = kind
        self.colour = colour

    def at(self, origin: Cell) -> list[Cell]:
        return [(origin[0] + r, origin[1] + c) for r, c in self.shape]

    def emitters(self, origin: Cell) -> list[Cell]:
        return [(origin[0] + r, origin[1] + c) for r, c in self.emits]


class Board:
    """Everything the simulator and the planner need, all of it derived from one frame."""

    __slots__ = ("n", "scale", "off", "grav", "cups", "band", "pieces",
                 "emitters", "droplets", "drop_colour")

    def __init__(self, n: int, scale: int, off: int, grav: Cell) -> None:
        self.n, self.scale, self.off, self.grav = n, scale, off, grav
        self.cups: list[tuple[frozenset[Cell], tuple[int, int, int, int]]] = []
        self.band: set[Cell] = set()
        self.pieces: list[Piece] = []
        self.emitters: set[Cell] = set()
        self.droplets: set[Cell] = set()
        self.drop_colour: int = -1

    def key(self) -> tuple:
        return (self.n, self.grav, tuple(sorted(self.band)),
                tuple(sorted((tuple(sorted(b)), bb) for b, bb in self.cups)),
                tuple(sorted(self.emitters)), tuple(sorted(self.droplets)),
                tuple(sorted((p.shape, p.origin, p.emits) for p in self.pieces)))


def _read(obs: Any) -> Board | None:
    """Recover the whole mechanic from the settled frame, or return None: this is not the family."""
    px = _stack(obs)[-1]
    lat = _lattice(px)
    if lat is None:
        return None
    n, scale, off = lat
    g = _blocks(px, n, scale, off)[0]
    bg = next(iter(_modal_colours(g)))

    # The band is an edge line rendered end to end in one colour. Taking it off the EDGE rather
    # than off a colour keeps a bar that happens to lie along an edge out of it.
    band: set[Cell] = set()
    for line in ([(0, c) for c in range(n)], [(n - 1, c) for c in range(n)],
                 [(r, 0) for r in range(n)], [(r, n - 1) for r in range(n)]):
        tones = {int(g[r][c]) for r, c in line}
        if len(tones) == 1 and tones.pop() != bg:
            band.update(line)

    comps = [c for c in connected_components(g, background=bg) if not set(c["cells"]) & band]
    cups: list[tuple[list[Cell], Cell, Cell]] = []
    for comp in comps:
        found = _mouth(list(comp["cells"]))
        if found is not None:
            cups.append((list(comp["cells"]), found[0], found[1]))
    if not cups:
        return None
    inside = {c for body, _, _ in cups for c in body}
    rest = [c for c in comps if not set(c["cells"]) & inside]
    lone: dict[Cell, int] = {c["cells"][0]: int(c["color"]) for c in rest if len(c["cells"]) == 1}
    solid = [c for c in rest if len(c["cells"]) > 1]
    if not lone or not solid:
        return None

    grav = _gravity(lone, cups, n)
    if grav is None:
        return None
    pairs = [(a, b) for a, b in ((a, (a[0] + grav[0], a[1] + grav[1])) for a in lone)
             if b in lone and lone[a] != lone[b]]
    if not pairs:
        return None
    # ⛔ ONE emitter colour and ONE droplet colour, or the pairing is coincidence rather than a
    # reading. A board where the pairs disagree is not this family and gets no bid.
    emit_tone = {lone[a] for a, _ in pairs}
    drop_tone = {lone[b] for _, b in pairs}
    if len(emit_tone) != 1 or len(drop_tone) != 1 or emit_tone == drop_tone:
        return None

    board = Board(n, scale, off, grav)
    board.band = band
    board.drop_colour = next(iter(drop_tone))
    for body, mouth, _ in cups:
        whole = set(body) | {mouth}
        board.cups.append((frozenset(body), (min(c[0] for c in whole), min(c[1] for c in whole),
                                             max(c[0] for c in whole), max(c[1] for c in whole))))
    board.emitters = {c for c, tone in lone.items() if tone in emit_tone}
    board.droplets = {c for c, tone in lone.items() if tone in drop_tone}

    # An emitter sitting inside a piece splits that piece into two runs on the frame. Rejoin them
    # through the emitter cell, or the piece's own width — the thing that decides where the flow
    # is pushed aside — is measured short by one cell on each side.
    owner: dict[Cell, int] = {}
    body: dict[int, list[Cell]] = {}
    inner: dict[int, list[Cell]] = {}
    tone: dict[int, int] = {}
    for i, comp in enumerate(solid):
        body[i] = list(comp["cells"])
        inner[i] = []
        tone[i] = int(comp["color"])
        for c in comp["cells"]:
            owner[c] = i
    link = {i: i for i in body}

    def root(i: int) -> int:
        while link[i] != i:
            i = link[i]
        return i

    for cell in sorted(board.emitters):
        touch = {root(owner[(cell[0] + dr, cell[1] + dc)])
                 for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))
                 if (cell[0] + dr, cell[1] + dc) in owner}
        if not touch:
            continue
        keep = min(touch)
        for other in touch:
            link[other] = keep
        body[keep].append(cell)
        inner[keep].append(cell)
        owner[cell] = keep
        board.emitters.discard(cell)
    for i in list(body):
        r = root(i)
        if r != i:
            body[r].extend(body[i])
            inner[r].extend(inner[i])
            del body[i]
    for i, cells in body.items():
        kind = _kind(cells)
        if kind:
            board.pieces.append(Piece(cells, kind, inner[i], tone[i]))
    if not board.pieces or not board.droplets:
        return None
    return board


def _gravity(lone: dict[Cell, int], cups: list[tuple[list[Cell], Cell, Cell]], n: int) -> Cell | None:
    """The direction the flow travels, from the emitter/droplet pairs, with the cups only voting.

    ⛔ Cups do not decide it. A cup can be turned to face any side and one board in this family
    has cups opening up, left and right at once, so a majority of mouths points the wrong way. An
    emitter is a lone cell against the rim with its droplet one step inward, and THAT pair names
    the direction outright — which is why a rim-anchored pair outvotes everything else here.
    """
    vote: Counter[Cell] = Counter()
    for a, tone in lone.items():
        for step in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            b = (a[0] + step[0], a[1] + step[1])
            if b not in lone or lone[b] == tone:
                continue
            on_rim = a[0] in (0, n - 1) or a[1] in (0, n - 1)
            b_rim = b[0] in (0, n - 1) or b[1] in (0, n - 1)
            vote[step] += 10 if on_rim and not b_rim else 1
    if not vote:
        return None
    for _, _, facing in cups:
        if facing in vote:
            vote[facing] += 3
    return vote.most_common(1)[0][0]


# --- the propagation rule ----------------------------------------------------

_EMPTY, _WET, _BAR, _ELBOW, _CUP, _BAND, _STOP = range(7)


def _flanks(grav: Cell) -> dict[Cell, tuple[Cell, Cell, Cell, Cell]]:
    """Per heading: the two cells a droplet is pushed aside into, and the two turns an elbow can
    impose.

    ⛔ The ORDER of the two flanks is load-bearing and it is fixed by GRAVITY, not by the heading:
    the two elbow cases are not mirror images of each other — one of them also spreads sideways
    and the other does not — so a flank pair listed the other way round predicts a different
    board. Two of the six boards render rotated, and reading the flanks off the heading alone
    swaps them on exactly those two.
    """
    gr, gc = grav
    across = ((gc, -gr), (-gc, gr))
    along = ((-gr, -gc), (gr, gc))
    out: dict[Cell, tuple[Cell, Cell, Cell, Cell]] = {}
    for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        p1, p2 = across if d in (grav, (-gr, -gc)) else along
        out[d] = (p1, p2, (-d[1], d[0]), (d[1], -d[0]))
    return out


def _release(board: Board, layout: tuple[Cell, ...]) -> tuple[bool, int, int, frozenset[Cell]]:
    """Run the flow over one candidate layout.

    -> (clears, cups satisfied, droplets lost on the band, cells the flow reached). The last two
    are not diagnostics: lost droplets give the layout search a gradient where "did it clear"
    gives it none, and a piece the flow never touches cannot change the outcome, so only layouts
    standing IN the water are worth simulating at all.
    """
    n = board.n
    span = n + 2                     # one cell of pad, so no step off the board needs a bounds test
    role = bytearray(span * span)
    owner = [0] * (span * span)
    for i in range(span):
        role[i] = role[(span - 1) * span + i] = _STOP
        role[i * span] = role[i * span + span - 1] = _STOP

    def at(cell: Cell) -> int:
        return (cell[0] + 1) * span + cell[1] + 1

    for c in board.band:
        role[at(c)] = _BAND
    for i, (cup, _) in enumerate(board.cups):
        for c in cup:
            j = at(c)
            role[j], owner[j] = _CUP, i
    for c in board.emitters:
        role[at(c)] = _STOP
    taps = [at(c) for c in sorted(board.emitters)]
    for i, piece in enumerate(board.pieces):
        mark = _BAR if piece.kind == "bar" else _ELBOW
        for c in piece.at(layout[i]):
            j = at(c)
            role[j], owner[j] = mark, i
        taps.extend(at(c) for c in piece.emitters(layout[i]))

    grav = board.grav
    flat = {}
    for d, (p1, p2, t1, t2) in _flanks(grav).items():
        flat[d[0] * span + d[1]] = (p1[0] * span + p1[1], p2[0] * span + p2[1],
                                    t1[0] * span + t1[1], t2[0] * span + t2[1])
    down = grav[0] * span + grav[1]

    wet: set[int] = set()
    front: list[tuple[int, int]] = []
    for c in sorted(board.droplets):
        j = at(c)
        role[j] = _WET
        wet.add(j)
        front.append((j, down))
    for j in taps:
        ahead = j + down
        if role[ahead] == _EMPTY:
            role[ahead] = _WET
            wet.add(ahead)
            front.append((ahead, down))

    full: set[int] = set()
    lost = 0
    for _ in range(_TICKS):
        if not front:
            break
        nxt: list[tuple[int, int]] = []
        for pos, d in front:
            p1, p2, turn1, turn2 = flat[d]
            ahead = pos + d
            what = role[ahead]
            if what == _EMPTY:
                role[ahead] = _WET
                wet.add(ahead)
                nxt.append((ahead, d))
                continue
            if what == _WET:
                nxt.append((ahead, d))
                continue
            if what == _BAND:
                lost += 1
                continue
            if what not in (_BAR, _ELBOW, _CUP):
                continue                       # the rim, or an emitter's own body: it stops here
            left, right = pos + p1, pos + p2
            if what == _CUP:
                if role[left] == _CUP and role[right] == _CUP \
                        and owner[left] == owner[ahead] and owner[right] == owner[ahead]:
                    full.add(owner[ahead])
                    continue
            elif what == _ELBOW:
                same_left = role[left] == _ELBOW and owner[left] == owner[ahead]
                same_right = role[right] == _ELBOW and owner[right] == owner[ahead]
                if same_left and role[right] == _EMPTY:
                    tgt = pos + turn1
                    if role[tgt] == _EMPTY:
                        role[tgt] = _WET
                        wet.add(tgt)
                    nxt.append((tgt, turn1))
                if same_right and role[left] == _EMPTY:
                    tgt = pos + turn2
                    if role[tgt] == _EMPTY:
                        role[tgt] = _WET
                        wet.add(tgt)
                    nxt.append((tgt, turn2))
                    continue
            # ⛔ Re-read the flanks rather than reusing what was read above: a turn may just have
            # filled one of them, and the board is queried again before the spread. Trusting the
            # stale read doubles the droplet.
            for side in (left, right):
                if role[side] == _EMPTY:
                    role[side] = _WET
                    wet.add(side)
                    nxt.append((side, d))
        front = nxt

    reached = frozenset(((j // span) - 1, (j % span) - 1) for j in wet)
    return (not front and not lost and len(full) == len(board.cups)), len(full), lost, reached


# --- where a piece may stand, and how far --------------------------------------

def _upstream(cell: Cell, grav: Cell, n: int) -> int:
    """How far along the flow's own axis the cell sits, counted from the emitter end."""
    return cell[0] if grav[0] > 0 else (n - 1 - cell[0]) if grav[0] else (
        cell[1] if grav[1] > 0 else n - 1 - cell[1])


def _forbidden(board: Board) -> set[Cell]:
    out = set(board.band) | set(board.emitters) | set(board.droplets)
    for cup, _ in board.cups:
        out |= set(cup)
    return out


def _standable(board: Board, cells: list[Cell], barred: set[Cell]) -> bool:
    """Can a piece occupy these cells at all? Independent of where the OTHER pieces are, because
    the engine lets pieces pass through one another and refuses only the fixed furniture."""
    n = board.n
    for r, c in cells:
        if not (0 <= r < n and 0 <= c < n) or (r, c) in barred:
            return False
    if min(_upstream(c, board.grav, n) for c in cells) < _LATCH:
        return False
    r0, c0 = min(c[0] for c in cells), min(c[1] for c in cells)
    r1, c1 = max(c[0] for c in cells), max(c[1] for c in cells)
    for _, (br0, bc0, br1, bc1) in board.cups:
        if r0 <= br1 + 1 and r1 >= br0 - 1 and c0 <= bc1 + 1 and c1 >= bc0 - 1:
            return False
    return True


def _slides(board: Board, idx: int, limit: int) -> dict[Cell, int]:
    """Every origin the piece can reach, with the number of presses it takes to get there."""
    piece = board.pieces[idx]
    barred = _forbidden(board)
    start = piece.origin
    dist = {start: 0}
    queue: deque[Cell] = deque([start])
    while queue:
        cur = queue.popleft()
        if dist[cur] >= limit:
            continue
        for step in _NATURAL:
            nxt = (cur[0] + step[0], cur[1] + step[1])
            if nxt in dist:
                continue
            if _standable(board, piece.at(nxt), barred):
                dist[nxt] = dist[cur] + 1
                queue.append(nxt)
    return dist


def _separate(board: Board, layout: tuple[Cell, ...]) -> bool:
    """No two pieces overlap, and no two of the SAME colour touch.

    ⛔ Only same-colour touching is forbidden, and the distinction is worth its own line: two
    touching pieces of one colour read back as ONE component on the next frame, and every plan
    after that is about an object that does not exist. Two touching pieces of DIFFERENT colours
    read back correctly — and the deepest board of this family has a winning layout that stands a
    bar against an elbow, so forbidding that outright forbids the answer.
    """
    held: dict[Cell, int] = {}
    for i, piece in enumerate(board.pieces):
        cells = piece.at(layout[i])
        for r, c in cells:
            for dr, dc in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                seat = held.get((r + dr, c + dc))
                if seat is None or seat == i:
                    continue
                if (dr, dc) == (0, 0) or board.pieces[seat].colour == piece.colour:
                    return False
        for cell in cells:
            held[cell] = i
    return True


def _plan(board: Board, spent: set[tuple[Cell, ...]]) -> tuple[Cell, ...] | None:
    """The cheapest layout this tool's own model says clears, or None."""
    base = tuple(p.origin for p in board.pieces)
    ceiling = _MAX_PRESSES
    ranked = [sorted(_slides(board, i, ceiling).items(), key=lambda kv: kv[1])
              for i in range(len(board.pieces))]
    seen: set[tuple[Cell, ...]] = set()
    deadline = time.monotonic() + _PLAN_SECONDS
    hit = _cheapest(board, spent, base, ranked, seen, deadline, ceiling)
    return hit if hit is not None else _guided(board, spent, base, ranked, seen, deadline, ceiling)


def _cheapest(board: Board, spent: set[tuple[Cell, ...]], base: tuple[Cell, ...],
              ranked: list[list[tuple[Cell, int]]], seen: set[tuple[Cell, ...]],
              deadline: float, ceiling: int) -> tuple[Cell, ...] | None:
    """Exhaustive cheapest-first. Shallow boards are one short slide, and this returns the
    MINIMUM press count for them, which is what the score is actually made of."""
    order = sorted(range(len(board.pieces)), key=lambda i: len(ranked[i]))
    left = _EXACT_NODES

    def walk(k: int, layout: tuple[Cell, ...], cost: int, cap: int) -> tuple[Cell, ...] | None:
        nonlocal left
        if left <= 0:
            return None
        if not left % 1024 and time.monotonic() > deadline:
            left = 0
            return None
        if k == len(order):
            if layout in seen or layout in spent or not _separate(board, layout):
                return None
            seen.add(layout)
            left -= 1
            return layout if _release(board, layout)[0] else None
        i = order[k]
        for tgt, dist in ranked[i]:
            spend = 0 if dist == 0 else dist + 1
            if cost + spend > cap:
                break
            found = walk(k + 1, layout[:i] + (tgt,) + layout[i + 1:], cost + spend, cap)
            if found is not None:
                return found
        return None

    for cap in range(0, min(_EXACT_COST, ceiling) + 1):
        found = walk(0, base, 0, cap)
        if found is not None:
            return found
        if left <= 0:
            return None
    return None


def _guided(board: Board, spent: set[tuple[Cell, ...]], base: tuple[Cell, ...],
            ranked: list[list[tuple[Cell, int]]], seen: set[tuple[Cell, ...]],
            deadline: float, ceiling: int) -> tuple[Cell, ...] | None:
    """Best-first over layouts that stand IN the water, ranked by how many cups they satisfy.

    A deep board needs three or four pieces relocated, where the exhaustive sweep does not leave
    cost six inside its node budget. Restricting candidates to pieces the flow actually reaches
    is what makes it tractable: a piece the water never meets cannot change the outcome.
    """
    total = len(board.cups)
    clears, full, lost, wet = _release(board, base)
    if clears and base not in spent:
        return base
    tick = 0
    heap: list[tuple[int, int, int, tuple[Cell, ...], frozenset[Cell]]] = [
        (_MISS * (total - full) + lost, 0, tick, base, wet)
    ]
    left = _GUIDED_NODES
    while heap and left > 0 and time.monotonic() < deadline:
        _, cost, _, layout, wet = heapq.heappop(heap)
        for i in range(len(board.pieces)):
            piece = board.pieces[i]
            in_water = bool(set(piece.at(layout[i])) & wet)
            for tgt, dist in ranked[i]:
                if dist == 0:
                    continue
                spend = cost + dist + 1
                if spend > ceiling:
                    break
                if not in_water and not set(piece.at(tgt)) & wet:
                    continue
                nxt = layout[:i] + (tgt,) + layout[i + 1:]
                if nxt in seen or not _separate(board, nxt):
                    continue
                seen.add(nxt)
                left -= 1
                clears, full, lost, reached = _release(board, nxt)
                if clears and nxt not in spent:
                    return nxt
                tick += 1
                heapq.heappush(heap, (_MISS * (total - full) + lost, spend, tick, nxt, reached))
    return None


# --- the tool ----------------------------------------------------------------

class SluiceTool:
    """Place the pieces so the simulated release satisfies every cup, then commit once."""

    name = "sluice"

    def __init__(self) -> None:
        self._level = -1
        self._reset_level()
        # The direction map is per GAME, not per level: it is a property of the controls.
        self._map: dict[int, Cell] = {aid: step for step, aid in _NATURAL.items()}
        self._probed = False
        self._retired = False

    def _reset_level(self) -> None:
        self._goal: list[tuple[tuple[Cell, ...], Cell]] = []
        self._spent: set[tuple[Cell, ...]] = set()
        self._commits = 0
        self._awaiting = False
        self._predicted: frozenset[Cell] = frozenset()
        self._stuck = False
        self._holding: tuple[tuple[Cell, ...], Cell] | None = None
        self._pending: tuple[Cell, int] | None = None   # (step intended, action that asked for it)
        self._refused = 0
        self._plans: dict[tuple, tuple[Cell, ...] | None] = {}

    def reset(self) -> None:
        self._reset_level()

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Nothing is carried here. The board is re-read every turn, and the control map is
        rewritten inside `propose`, which is the only place the identity of the piece that just
        moved is available. This hook exists to satisfy the protocol."""

    # -- protocol ---------------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Confidence, which is ZERO unless this tool has an actual winning layout in hand.

        ⛔ A tool with no plan must bid nothing. Recognising the shapes is not a plan: the board
        may be one this tool reads and cannot solve, and a consolation bid there takes the turn
        from a tool that could.
        """
        if self._retired or self._stuck or not has_frame(obs):
            return 0.0
        simple, click = availability(obs)
        if not click or not {1, 2, 3, 4, 5} <= set(simple):
            return 0.0
        board = _read(obs)
        if board is None:
            return 0.0
        return 0.9 if self._layout(board) is not None else 0.0

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        level = levels_completed(obs)
        if level != self._level:
            self._level = level
            self._reset_level()
        if self._retired or self._stuck or not has_frame(obs):
            return []
        simple, click = availability(obs)
        if not click or not {1, 2, 3, 4, 5} <= set(simple):
            # ⛔ Checked again here, not only in `detect`. The harness silently DROPS any step of
            # a batch whose action is unavailable, and a batch with a hole in it puts a piece
            # somewhere the plan never intended — worse than proposing nothing.
            return []
        board = _read(obs)
        if board is None:
            return []
        if self._awaiting:
            self._settle(obs, board)
            if self._stuck:
                return []
        self._follow(board)
        target = self._layout(board)
        if target is None:
            self._stuck = True
            return []
        self._goal = [(board.pieces[i].shape, target[i]) for i in range(len(board.pieces))]
        return self._advance(board)

    # -- planning ---------------------------------------------------------------

    def _layout(self, board: Board) -> tuple[Cell, ...] | None:
        """The winning layout for this exact board, planned at most once per board state.

        ⛔ Cached deliberately, and the misses are remembered too. `detect` is asked on every
        stall by every tool the harness holds, and planning a deep board costs seconds; paying
        that per call would make the tool's own cost the game's cost.
        """
        key = board.key()
        if key in self._plans:
            return self._plans[key]
        found = _plan(board, self._spent)
        if len(self._plans) > 64:
            self._plans.clear()
        self._plans[key] = found
        return found

    # -- execution --------------------------------------------------------------

    def _follow(self, board: Board) -> None:
        """Track the held piece across the frame, and learn what the last slide actually did.

        ⛔ Which piece is held cannot be read off the frame when only one piece has its shape:
        the engine repaints the held piece, so "the odd colour out" needs a peer to be odd
        against, and a board with a single bar has none. It is TRACKED instead — this tool
        clicked it, so this tool knows — and a slide of one cell per action keeps the match
        unambiguous even between two pieces of identical shape.
        """
        if self._holding is None:
            self._pending = None
            return
        shape, was = self._holding
        same = [p for p in board.pieces if p.shape == shape]
        if not same:
            self._holding = None
            self._pending = None
            return
        now = min(same, key=lambda p: abs(p.origin[0] - was[0]) + abs(p.origin[1] - was[1])).origin
        self._holding = (shape, now)
        if self._pending is None:
            return
        intended, action = self._pending
        self._pending = None
        moved = (now[0] - was[0], now[1] - was[1])
        if moved == (0, 0):
            # The engine refused a slide this tool's legality model called legal. One refusal is
            # survivable — replan and route around it — but a model that keeps being wrong will
            # push into the wall for the rest of the allowance, so the second one ends it.
            self._refused += 1
            if self._refused >= 2:
                self._stuck = True
            self._plans.clear()
            return
        self._refused = 0
        self._probed = True
        if moved != intended and moved in _NATURAL:
            # ⛔ Learn a ROTATION, not one arrow. If the controls are turned relative to the view
            # they are turned as a set, and correcting a single entry would leave two actions
            # claiming the same direction and one claiming none.
            for _ in range(3):
                intended = (-intended[1], intended[0])
                if intended == moved:
                    self._map = {aid: (-d[1], d[0]) for aid, d in self._map.items()}
                    break
                self._map = {aid: (-d[1], d[0]) for aid, d in self._map.items()}
            self._plans.clear()

    def _advance(self, board: Board) -> list[Step]:
        """Queue the whole remaining plan in one go, and commit at the end of it.

        ⛔ The plan is emitted as a BATCH rather than an action at a time, and that is a
        perception decision, not an efficiency one. Two same-coloured pieces that touch read back
        as ONE component, and a piece on its way past another passes THROUGH exactly such a
        moment — the final layout is checked for it, an intermediate one cannot be. Re-reading
        the board there returned four pieces as three and abandoned a level this tool had
        already solved. Every action of the plan comes from ONE frame, so no such frame is ever
        consulted.
        """
        pairs = self._match(board)
        if len(pairs) != len(board.pieces):
            self._plans.clear()                    # the board no longer holds the planned pieces
            return []
        moves: list[tuple[int, list[Cell]]] = []
        for idx, target in pairs:
            if board.pieces[idx].origin == target:
                continue
            route = self._route(board, idx, target)
            if route is None:
                # The layout is unreachable as planned. Retire it rather than commit a placement
                # that was never built.
                self._spent.add(tuple(t for _, t in pairs))
                self._plans.clear()
                return []
            moves.append((idx, route))

        if moves and not self._probed:
            # One slide, alone, to see what the controls actually do before spending the rest of
            # the allowance on the assumption. It is the plan's own first slide, so it costs
            # nothing extra.
            idx, route = moves[0]
            piece = board.pieces[idx]
            if self._holding != (piece.shape, piece.origin):
                self._holding = (piece.shape, piece.origin)
                self._pending = None
                return [self._click(board, piece)]
            action = self._action(route[0])
            if action is None:
                return []
            self._pending = (route[0], action)
            return [(action, None)]

        out: list[Step] = []
        for idx, route in moves:
            out.append(self._click(board, board.pieces[idx]))
            for step in route:
                action = self._action(step)
                if action is None:
                    return []
                out.append((action, None))
        if self._commits >= _ATTEMPTS:
            self._stuck = True
            return []
        self._commits += 1
        self._awaiting = True
        self._holding = None
        self._predicted = _release(board, tuple(t for _, t in pairs))[3]
        out.append((_COMMIT, None))
        return out

    @staticmethod
    def _route(board: Board, idx: int, target: Cell) -> list[Cell] | None:
        """Every slide of a shortest route from where the piece is to where it must be."""
        dist = _slides(board, idx, _MAX_PRESSES)
        if target not in dist:
            return None
        back: list[Cell] = []
        cur = target
        while dist[cur] > 0:
            for step in _NATURAL:
                prev = (cur[0] - step[0], cur[1] - step[1])
                if dist.get(prev) == dist[cur] - 1:
                    back.append(step)
                    cur = prev
                    break
            else:
                return None
        return list(reversed(back))

    def _settle(self, obs: Any, board: Board) -> None:
        """Read the release that just played out, and hold the model to it."""
        self._awaiting = False
        self._holding = None
        seen = self._trajectory(obs, board)
        if seen and not (seen <= self._predicted):
            # ⛔ The flow went somewhere the model said it could not. Every layout the search
            # ranks is then wrong too, and three more attempts spent on it are three thrown away.
            # Stop bidding on this board rather than be confidently wrong four times.
            self._retired = True
            self._stuck = True
            return
        self._spent.add(tuple(p.origin for p in board.pieces))
        self._plans.clear()

    def _trajectory(self, obs: Any, board: Board) -> set[Cell]:
        """Every cell the flow occupied, unioned over the commit's own frame layers.

        Measured against the engine on all six boards of this family: this set and the simulated
        one are IDENTICAL, cell for cell, on the starting layout of every board — so the subset
        test in `_settle` is a real check and not a formality with room to hide in.
        """
        n, s, off = board.n, board.scale, board.off
        out: set[Cell] = set()
        for layer in _stack(obs):
            cells = _blocks(layer, n, s, off)[0]
            for r, c in zip(*np.where(cells == board.drop_colour)):
                out.add((int(r), int(c)))
        return out

    def _action(self, step: Cell) -> int | None:
        for aid, known in self._map.items():
            if known == step:
                return aid
        return None

    def _match(self, board: Board) -> list[tuple[int, Cell]]:
        """Give each piece its planned origin — by shape, then by nearness within that shape."""
        out: list[tuple[int, Cell]] = []
        free = list(range(len(self._goal)))
        for idx, piece in enumerate(board.pieces):
            same = [g for g in free if self._goal[g][0] == piece.shape]
            if not same:
                continue
            pick = min(same, key=lambda g: abs(self._goal[g][1][0] - piece.origin[0])
                       + abs(self._goal[g][1][1] - piece.origin[1]))
            free.remove(pick)
            out.append((idx, self._goal[pick][1]))
        return out

    @staticmethod
    def _click(board: Board, piece: Piece) -> Step:
        """Select a piece by clicking the middle pixel of one of its cells."""
        cell = piece.at(piece.origin)[0]
        half = board.scale // 2
        return (6, (board.off + cell[1] * board.scale + half,
                    board.off + cell[0] * board.scale + half))
