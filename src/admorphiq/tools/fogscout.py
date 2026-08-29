"""Proximity-fog navigation with a carried token that a target cell demands.

MECHANIC (recovered from frames only; the family, not one board).
--------------------------------------------------------------------------
Some boards hide themselves. Every pixel further than a fixed radius from the
avatar is overwritten with a single flat colour, so one observation shows a
DISC of truth inside a flat field. Four move actions step the avatar exactly one
lattice cell. Three further rules make it a puzzle rather than a maze:

* the avatar CARRIES a token, drawn in a small fixed panel outside the arena;
* some cells CYCLE one attribute of that token when the avatar enters them —
  the panel is the only place the change is visible;
* one cell is the TARGET. It displays the token it demands, as a small icon
  inside itself. Entering it with the wrong token is REFUSED (the avatar does
  not move); entering with the right token completes the level.
* a per-level ACTION BUDGET is drawn as a shrinking bar at the frame edge; on
  exhaustion the avatar is thrown back to where it started. Some cells REFILL
  that bar and are consumed.

So the state is (cell, token), not cell, and the plan is a walk in that product
space: press the right changers the right number of times, then walk in. The
tool never assumes which action is which direction, what the cell size is,
which colour is wall, or what a changer does — all six are MEASURED:

  cell size + direction map   the avatar's move leaves a changed region that is
                              exactly two cells side by side, so one probe per
                              action gives the pitch AND the direction;
  wall vs floor               a move that did not move names the target a wall;
                              a cell stood on is floor. Colours generalise from
                              those two facts, and only from those.
  changer semantics           entering cell C took token t to t'. Recorded as a
                              partial permutation and BFS'd over. Nothing is
                              assumed about WHICH attribute moved.
  target token                the icon inside the cell that refused entry.

⛔ WHY IT BIDS ON ALMOST NOTHING, AND THE TWO TESTS THAT MAKE THAT TRUE. The fog
is the whole claim, and the first version of this file tested it with a BOUNDING
BOX — compact, roughly square, corners of the box empty. That is a blob
detector, not a fog detector, and measured over the 25 boards it claimed 220
frames on SIX games it cannot play, one of them conquered at 1.0000. A box
cannot tell a disc from a cross, an L, or a rounded panel.

Two tests replace it, and the measurement says plainly that NEITHER SEPARATES
ALONE — it is the conjunction:

    board   old-hits   killed by BOTH   by CORNERS only   by CIRCLE only
    A             92               58                34                0
    B             90               90                 0                0
    C             15                2                13                0
    D             13                0                13                0
    E              9                9                 0                0
    F              1                1                 0                0
    THIS BOARD   463                0                 0                0   all survive

The CIRCLE FIT (`disc_score`) asks whether the visible island IS a disc, by
fitting one; a filled square can only reach 2/pi. The CORNER test uses the
geometry: at radius <= 32 in a square frame at most ONE frame corner can lie
inside the disc, so three of the four must be fogged. Three boards are killed
by the corners alone at circle fits of 0.79-0.86, which overlap the target's own
0.82-0.99 — so a threshold on either number by itself would have been a guess
dressed as a measurement.

`detect` returns 0.00 on all 24 other boards, and 0.00 on this game's first six
levels, which carry no fog ([[lessons/tool_selectivity_20260827]]).

⛔ WHY IT REPLANS EVERY ACTION rather than executing a plan open-loop. Under fog
the map is a belief that grows, and two of this family's rules move the avatar
where the plan did not put it: a deflector cell shoves it several cells along,
and budget exhaustion teleports it home. Reading the avatar out of every frame
and re-deriving the next single action makes both of those ordinary transitions
instead of desyncs — and the observed landing is recorded as an EDGE, so the
second encounter is planned around rather than suffered again.

⛔ WHY THE BAR IS READ AND NOT COUNTED. `[[concepts/action_budget]]`: the budget
is DRAWN. Counting actions instead would need the decrement, the refill amount
and the reset rule to be assumed; the bar states all three. Only its longest
single-colour run is used — an earlier version of a sibling tool counted a whole
edge band and overestimated every budget by fifteen times.
"""

from __future__ import annotations

from collections import Counter, deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, frame_2d, has_frame

__all__ = ["FogScoutTool"]

Cell = tuple[int, int]
Tok = tuple[frozenset[tuple[int, int]], int]

# --- fog signature bounds (frame-only; see the module docstring) -------------
_FOG_MIN_FRACTION = 0.55   # the flat field must dominate the frame
_ISLAND_MIN = 250          # smaller islands are ordinary sprites, not a view
_ISLAND_MAX = 2400         # larger means the board is simply mostly one colour
_ISLAND_MIN_COLORS = 4     # a real view of a board shows several things at once
_DISC_MIN = 0.80           # best circle-fit IoU; a filled square can only reach 2/pi
_ISLAND_SPAN = 48          # a view is bounded; a whole board is not

_MOVE_IDS = (1, 2, 3, 4)
_SIGHT_RETRY = 50          # ticks before a walked-to-and-empty sighting is retried
_PURSUIT_CAP = 30          # actions chasing one target without treading a new cell
_STALE_LOOK = 60           # ticks after which a mapped cell is worth re-seeing
_MAX_PITCH = 12
_MIN_PITCH = 3


def _dominant(g: np.ndarray) -> int:
    return int(Counter(int(v) for v in g.ravel()).most_common(1)[0][0])


def _largest_island(mask: np.ndarray) -> list[tuple[int, int]]:
    """Biggest 4-connected run of True cells (the fog leaves exactly one)."""
    h, w = mask.shape
    seen = np.zeros_like(mask)
    best: list[tuple[int, int]] = []
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or seen[y, x]:
                continue
            stack = [(y, x)]
            seen[y, x] = True
            cells: list[tuple[int, int]] = []
            while stack:
                cy, cx = stack.pop()
                cells.append((cy, cx))
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            if len(cells) > len(best):
                best = cells
    return best


def _disc_iou(mask: np.ndarray, cy: float, cx: float, r: float) -> float:
    h, w = mask.shape
    ys = (np.arange(h) - cy) ** 2
    xs = (np.arange(w) - cx) ** 2
    disc = (ys[:, None] + xs[None, :]) <= r * r
    union = int((mask | disc).sum())
    return 0.0 if union == 0 else float((mask & disc).sum()) / union


def disc_score(g: np.ndarray, flat: int, island: list[tuple[int, int]]) -> float:
    """How nearly the visible island IS a disc, in [0, 1].

    ⛔ This replaced a bounding-box shape test, and the replacement is the whole
    difference between a fog detector and a blob detector. Two boards that carry
    no fog at all — one of them CONQUERED at 1.0000 — presented a compact
    multi-colour island with empty box corners and were claimed at 0.80. A box
    cannot tell a disc from a cross, an L or a rounded panel; only fitting the
    circle can, because proximity fog is not "a blob somewhere", it is
    `distance from one point <= r` and nothing else.

    Clipping is why this is a FIT and not a formula: the disc is cut both by the
    frame edge and by anything inside it that is already the flat colour, so the
    radius is searched rather than derived from the area. A true fog view scores
    near 0.9 even when a third of it is cut away; a square scores 2/pi.
    """
    mask = np.zeros(g.shape, dtype=bool)
    ys = np.fromiter((c[0] for c in island), dtype=np.int64, count=len(island))
    xs = np.fromiter((c[1] for c in island), dtype=np.int64, count=len(island))
    mask[ys, xs] = True
    # Centre from the midpoints of spans that are not cut by the frame edge; the
    # centroid alone is dragged sideways by every clipped row.
    rows: dict[int, list[int]] = {}
    cols: dict[int, list[int]] = {}
    for y, x in island:
        a = rows.setdefault(int(y), [int(x), int(x)])
        a[0], a[1] = min(a[0], int(x)), max(a[1], int(x))
        b = cols.setdefault(int(x), [int(y), int(y)])
        b[0], b[1] = min(b[0], int(y)), max(b[1], int(y))
    h, w = g.shape
    mid_x = [(a + b) / 2 for a, b in rows.values() if a > 0 and b < w - 1]
    mid_y = [(a + b) / 2 for a, b in cols.values() if a > 0 and b < h - 1]
    cx0 = float(np.median(mid_x)) if mid_x else float(xs.mean())
    cy0 = float(np.median(mid_y)) if mid_y else float(ys.mean())
    r0 = (len(island) / np.pi) ** 0.5
    best = 0.0
    for dy in (-2.0, -1.0, 0.0, 1.0, 2.0):
        for dx in (-2.0, -1.0, 0.0, 1.0, 2.0):
            for dr in (-4.0, -2.0, 0.0, 2.0, 4.0, 6.0):
                r = r0 + dr
                if r < 8.0 or r > 32.0:
                    continue
                best = max(best, _disc_iou(mask, cy0 + dy, cx0 + dx, r))
    return best


def fog_view(g: np.ndarray) -> tuple[int, list[tuple[int, int]]] | None:
    """(flat colour, island cells) when this frame is a proximity-fog view.

    Proximity fog is one specific thing: every pixel further than a fixed radius
    from the avatar is overwritten with one flat colour. So the test is that the
    visible remainder IS a disc — fitted, not approximated by its box.
    """
    total = g.size
    flat = _dominant(g)
    same = int((g == flat).sum())
    if same < _FOG_MIN_FRACTION * total:
        return None
    if not (_ISLAND_MIN <= total - same <= _ISLAND_MAX):
        return None
    h, w = g.shape
    # At radius r <= 32 in a square frame at most ONE frame corner can be inside
    # the disc, so three of the four must be fogged. Cheap, and it kills any
    # board whose content merely happens to be sparse.
    corners = [g[0, 0], g[0, w - 1], g[h - 1, 0], g[h - 1, w - 1]]
    if sum(1 for v in corners if int(v) == flat) < 3:
        return None
    island = _largest_island(g != flat)
    if not (_ISLAND_MIN <= len(island) <= _ISLAND_MAX):
        return None
    ys = [c[0] for c in island]
    xs = [c[1] for c in island]
    ih = max(ys) - min(ys) + 1
    iw = max(xs) - min(xs) + 1
    if not (12 <= ih <= _ISLAND_SPAN and 12 <= iw <= _ISLAND_SPAN):
        return None
    if len({int(g[y, x]) for y, x in island}) < _ISLAND_MIN_COLORS:
        return None
    if disc_score(g, flat, island) < _DISC_MIN:
        return None
    return flat, island


def _rect_components(mask: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    """(y0, x0, height, width, size) for every 4-connected True region."""
    h, w = mask.shape
    seen = np.zeros_like(mask)
    out: list[tuple[int, int, int, int, int]] = []
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or seen[y, x]:
                continue
            stack = [(y, x)]
            seen[y, x] = True
            cells = []
            while stack:
                cy, cx = stack.pop()
                cells.append((cy, cx))
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            ys = [c[0] for c in cells]
            xs = [c[1] for c in cells]
            out.append((min(ys), min(xs), max(ys) - min(ys) + 1,
                        max(xs) - min(xs) + 1, len(cells)))
    return out


def _count_pattern(g: np.ndarray, pat: np.ndarray) -> int:
    """How many places in the frame carry this exact block."""
    h, w = g.shape
    ph, pw = pat.shape
    n = 0
    for y in range(h - ph + 1):
        for x in range(w - pw + 1):
            if g[y, x] == pat[0, 0] and np.array_equal(g[y:y + ph, x:x + pw], pat):
                n += 1
                if n > 1:
                    return n
    return n


def move_signature(prev: np.ndarray, cur: np.ndarray) -> tuple[int, tuple[int, int], tuple[int, int]] | None:
    """(pitch, vacated top-left, occupied top-left) read off one step.

    An avatar that steps one cell leaves a changed region that is exactly two
    cells side by side and completely filled — the cell it left and the cell it
    entered. That shape carries the lattice pitch, the avatar's position and,
    with the action that produced it, what that action means.

    ⛔ Which half is which cannot be decided by matching the two halves across
    the frames: when the vacated cell and the destination were both plain floor
    the match holds BOTH ways round, and the first version of this read every
    move backwards. The avatar is the block that occurs ONCE in the frame;
    floor occurs everywhere. That is the discriminator.
    """
    diff = prev != cur
    if not diff.any():
        return None
    best: tuple[int, tuple[int, int], tuple[int, int]] | None = None
    for y0, x0, hh, ww, size in _rect_components(diff):
        if size != hh * ww:
            continue
        if hh == 2 * ww and _MIN_PITCH <= ww <= _MAX_PITCH:
            pitch, halves = ww, ((y0, x0), (y0 + ww, x0))
        elif ww == 2 * hh and _MIN_PITCH <= hh <= _MAX_PITCH:
            pitch, halves = hh, ((y0, x0), (y0, x0 + hh))
        else:
            continue
        a, b = halves
        occupied = None
        for cand in (a, b):
            blk = _block(cur, cand, pitch)
            if _count_pattern(cur, blk) == 1:
                occupied = cand
                break
        if occupied is None:
            continue
        vacated = a if occupied == b else b
        if best is None or pitch < best[0]:
            best = (pitch, vacated, occupied)
    return best


def _block(g: np.ndarray, origin: tuple[int, int], pitch: int) -> np.ndarray:
    y, x = origin
    return g[y:y + pitch, x:x + pitch]


def _norm(mask: frozenset[tuple[int, int]]) -> frozenset[tuple[int, int]]:
    """A glyph slid to the origin, so two drawings of it compare equal."""
    if not mask:
        return mask
    y0 = min(y for y, _ in mask)
    x0 = min(x for _, x in mask)
    return frozenset((y - y0, x - x0) for y, x in mask)


def _rot90(mask: frozenset[tuple[int, int]]) -> frozenset[tuple[int, int]]:
    if not mask:
        return mask
    h = max(y for y, _ in mask) + 1
    return _norm(frozenset((x, h - 1 - y) for y, x in mask))


def _flip(mask: frozenset[tuple[int, int]]) -> frozenset[tuple[int, int]]:
    if not mask:
        return mask
    w = max(x for _, x in mask) + 1
    return _norm(frozenset((y, w - 1 - x) for y, x in mask))


def _turns(k: int) -> Any:
    def apply(m: frozenset[tuple[int, int]]) -> frozenset[tuple[int, int]]:
        for _ in range(k):
            m = _rot90(m)
        return m
    return apply


# The rigid motions of a small glyph. A mark whose every observed transition is
# explained by ONE of these is not a lookup table — it is that motion, and it
# then applies to glyphs the tool has never seen it act on.
_MOTIONS: dict[str, Any] = {
    "rot90": _turns(1),
    "rot180": _turns(2),
    "rot270": _turns(3),
    "flip": _flip,
    "flip2": lambda m: _turns(2)(_flip(m)),
}
_MOTION_MIN = 3   # observed pairs before a motion is believed


def _canon(mask: frozenset[tuple[int, int]]) -> frozenset[tuple[int, int]]:
    """A glyph reduced to unit scale, so the same token compares equal wherever
    it is drawn. The status panel draws it magnified; the cell that demands it
    draws it small. Both reduce to the same set."""
    cur = mask
    for _ in range(3):
        if not cur:
            return cur
        h = max(y for y, _ in cur) + 1
        w = max(x for _, x in cur) + 1
        shrunk = None
        for f in (2, 3):
            if h % f or w % f or len(cur) % (f * f):
                continue
            blocks = {(y // f, x // f) for y, x in cur}
            if len(blocks) * f * f != len(cur):
                continue
            if all((by * f + dy, bx * f + dx) in cur
                   for by, bx in blocks for dy in range(f) for dx in range(f)):
                shrunk = frozenset(blocks)
                break
        if shrunk is None:
            return cur
        cur = shrunk
    return cur


def icon_key(patch: np.ndarray, ground: int) -> Tok | None:
    """(unit-scale filled offsets, colour) of a one-colour glyph on ``ground``.

    A token is a sparse mark in a SINGLE colour. Two colours means a palette
    swatch, and a nearly full patch means a ring or a solid tile — neither is a
    token, and that is what keeps the tool from mistaking a changer for the
    target cell.
    """
    vals = Counter(int(v) for v in patch.ravel())
    vals.pop(ground, None)
    if len(vals) != 1:
        return None
    color, n = vals.most_common(1)[0]
    span = patch.size
    if not (0.15 * span <= n <= 0.80 * span):
        return None
    ys, xs = np.where(patch == color)
    y0, x0 = int(ys.min()), int(xs.min())
    return _canon(frozenset((int(y) - y0, int(x) - x0) for y, x in zip(ys, xs))), int(color)


def cell_mark(blk: np.ndarray, ground: int) -> frozenset[tuple[int, int, int]] | None:
    """Everything in a cell that is not its own ground, as (row, col, colour).

    This is the tool's notion of OBJECT IDENTITY, and it is deliberately cruder
    than the token reader: a refill ring, a palette swatch and a two-colour
    changer glyph all have one, while plain floor and a solid wall have none.
    Learning is stored against it rather than against a coordinate, so one visit
    teaches every cell wearing the same mark — including the one that moves.
    """
    ys, xs = np.where(blk != ground)
    if len(ys) == 0 or len(ys) == blk.size:
        return None
    return frozenset((int(y), int(x), int(blk[y, x])) for y, x in zip(ys, xs))


def _motion_of(table: dict[Any, Any]) -> str | None:
    """The rigid motion that explains EVERY observed pair, if exactly one does.

    ⛔ This is the difference between a rule that can be finished and one that
    cannot. One of this family's marks PATROLS, so each observation of it costs
    an interception and its table stays thin however long the tool runs — 4 of
    24 glyphs after 1385 actions, which left the demanded token unreachable and
    the win search firing ZERO times. But its four pairs are all one quarter
    turn, and a quarter turn is total: it applies to the twenty glyphs the tool
    never caught it acting on.

    ⛔ And it must be able to say NO. Measured on the same run, the mark that
    substitutes one glyph for another is explained by 0 of 15 pairs under every
    motion, so it keeps its lookup table and keeps being learned by observation.
    A test that accepted both would be an assumption wearing a measurement's
    clothes. Three pairs minimum, and exactly one motion may match.
    """
    if len(table) < _MOTION_MIN:
        return None
    fits = [name for name, f in _MOTIONS.items()
            if all(f(m) == _norm(mm) for m, mm in table.items())]
    return fits[0] if len(fits) == 1 else None


def _bar_runs(g: np.ndarray, flat: int) -> dict[int, int]:
    """Longest horizontal run of each colour in the frame's bottom edge band."""
    h, w = g.shape
    depth = max(2, h // 16)
    runs: dict[int, int] = {}
    for y in range(h - depth, h):
        run_c, run_n = -99, 0
        for x in range(w + 1):
            v = int(g[y, x]) if x < w else -99
            if v == run_c:
                run_n += 1
                continue
            if run_c >= 0 and run_c != flat:
                runs[run_c] = max(runs.get(run_c, 0), run_n)
            run_c, run_n = v, 1
    return runs


def _bar(g: np.ndarray, flat: int, color: int | None) -> tuple[int, int, int] | None:
    """(colour, filled length, WHOLE BAND length) of the drawn action budget.

    ⛔ The band, not just the filled part, and this decided a level. The budget
    is drawn as a fixed-length strip whose spent portion is redrawn in another
    colour, so reading only the filled run makes "full" mean "whatever it was
    when I first looked". Measured: handed the board 147 actions into the level
    — which is when the harness actually gives it up, the incumbent holding it
    across the level-up until it stalls — the tool saw a half-spent strip,
    concluded a life was a third as long as it is, and spent 206 of its 342
    actions running between refills it did not need. Handed the SAME level at
    action 0 it cleared in 206. The strip's total length is on screen from the
    first frame; there is no reason to infer it.

    ⛔ The band is read from the frame's EDGE. Reading three cell-heights deep
    put real board rows inside it, so a long run of floor beat the bar whenever
    the avatar came near the bottom — the same mistake that made a sibling tool
    overestimate every budget fifteen-fold.
    """
    h, w = g.shape
    depth = max(2, h // 16)
    best: tuple[int, int, int, int] | None = None   # (len, row, start, colour)
    for y in range(h - depth, h):
        run_c, run_n = -99, 0
        for x in range(w + 1):
            v = int(g[y, x]) if x < w else -99
            if v == run_c:
                run_n += 1
                continue
            if run_c >= 0 and run_c != flat and (color is None or run_c == color):
                if best is None or run_n > best[0]:
                    best = (run_n, y, x - run_n, run_c)
            run_c, run_n = v, 1
    if best is None:
        # ⛔ An EMPTY strip is a reading, not a failure. Returning None here left
        # the last non-zero length in place, so a bar that had just run out
        # still read as most of a life and the tool walked on until it died.
        return None if color is None else (color, 0, 0)
    if color is None and best[0] < 8:
        return None
    n, row, start, col = best
    span = n
    for step, edge in ((-1, start - 1), (1, start + n)):
        x = edge
        if not (0 <= x < w):
            continue
        other = int(g[row, x])
        if other == flat or other == col:
            continue
        while 0 <= x < w and int(g[row, x]) == other:
            span += 1
            x += step
    return col, n, span


class FogScoutTool:
    """Explore a fog-hidden board, learn what each cell does to the carried
    token, and walk into the target cell holding the token it demands."""

    name = "fogscout"

    def __init__(self) -> None:
        self.reset()

    # -- lifecycle ----------------------------------------------------------

    def reset(self) -> None:
        self.pitch: int | None = None
        self.dirs: dict[int, tuple[int, int]] = {}
        self.tpl: np.ndarray | None = None
        self.anchor: tuple[int, int] | None = None   # pixel origin of cell (0,0)
        self.pos: Cell | None = None
        self.start: Cell | None = None
        self.radius: float = 0.0

        self.floor_colors: set[int] = set()
        self.wall_colors: set[int] = set()
        self.walls: set[Cell] = set()
        self.seen: dict[Cell, int] = {}              # cell -> dominant colour
        self.stood: set[Cell] = set()
        self.edges: dict[tuple[Cell, int], Cell] = {}

        self.panel: tuple[int, int, int, int] | None = None
        self.tok: Tok | None = None
        self.mark: dict[Cell, frozenset[tuple[int, int, int]]] = {}
        self.kind: dict[frozenset[tuple[int, int, int]], dict[Tok, Tok]] = {}
        self.inert: set[frozenset[tuple[int, int, int]]] = set()
        self.refill_marks: set[frozenset[tuple[int, int, int]]] = set()
        self.sighted: dict[frozenset[tuple[int, int, int]], Cell] = {}
        self.checked: dict[frozenset[tuple[int, int, int]], int] = {}
        self.seen_at: dict[frozenset[tuple[int, int, int]], list[tuple[int, Cell]]] = {}
        self.lane: dict[frozenset[tuple[int, int, int]], set[Cell]] = {}
        self.aim: dict[Cell, frozenset[tuple[int, int, int]]] = {}
        self.home: Cell | None = None
        self.looked: dict[Cell, int] = {}
        self.tick = 0
        # Which of the plan's clauses produced the last action. Read by
        # scripts/fogscout_probe.py --solo --trace; a run that spends its budget
        # in one clause is the shape of every defect found while building this.
        self.reason = "start"
        # ⛔ A CENSUS, not a narrative. Every place this tool decides an action —
        # and every place its planner declines to — increments a key here, and
        # `scripts/fogscout_probe.py --census` prints the totals for one attempt
        # at the claimed level. Counting why beat reasoning about why three times
        # in one round on exactly this symptom: a tool that fires and then does
        # nothing.
        self.census: Counter[str] = Counter()
        self._rules_ver = -1
        self._rules_cache: dict[frozenset[tuple[int, int, int]], tuple[str, dict[Any, Any]]] = {}
        self.give_up: set[Cell] = set()
        self._pursuit: tuple[str, int] = ("", 0)
        self._trod_at = -1
        self._plan_dist: int | None = None
        # Where the current walk is headed, and how often a walk ever finishes.
        # ⛔ A tool can look busy while completing nothing: every action starts a
        # fresh walk to a fresh target and abandons the last one. Arrivals are
        # the only honest measure of that, and they are one counter.
        self._aim_cell: Cell | None = None
        self.arrived = 0
        self.abandoned = 0
        self.aimed: Counter[str] = Counter()
        self.target: Tok | None = None
        self.goal: Cell | None = None
        self.icon_cells: dict[Cell, Tok] = {}
        # Every token-like icon ever seen, by cell, and never pruned. `icon_cells`
        # is a live worklist and is emptied as marks are understood; this is the
        # record a refusal is checked against.
        self.icon_seen: dict[Cell, Tok] = {}
        self.refusals: dict[int, set[Cell]] = {}

        self.bar_color: int | None = None
        self.bar_full: int = 0
        self.bar_drop: int = 0
        self.bar_len: int = 0
        self._bar_seen = False
        self._bar_hist: dict[int, list[int]] = {}

        self._prev: np.ndarray | None = None
        self._prev_action: int | None = None
        self._prev_tok: Tok | None = None
        self._prev_pos: Cell | None = None
        self._probe_cycle = 0
        self._blind = 0
        self._lost = False
        self.flat: int | None = None
        self.fails: dict[tuple[Cell, int], int] = {}

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """The harness feeds transitions here; the frame AFTER the action only
        arrives at the next ``propose``, so the learning happens there and this
        records what produced it."""
        self._prev = prev
        self._prev_action = action[0] if action else None

    # -- detection ----------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        if not has_frame(obs):
            return 0.0
        simple, _ = availability(obs)
        if not any(a in simple for a in _MOVE_IDS):
            return 0.0
        g = frame_2d(obs).astype(np.int16)
        if fog_view(g) is None:
            return 0.0
        # A plan means a direction map. Before the probes have produced one the
        # tool has an intention, not a plan — but the probes ARE the plan's
        # first four actions and nothing else on the board can make them, so the
        # claim is real from the first fogged frame.
        return 0.86 if self.dirs else 0.80

    # -- perception ---------------------------------------------------------

    def _cell_origin(self, c: Cell) -> tuple[int, int]:
        oy, ox = self.anchor
        return oy + c[0] * self.pitch, ox + c[1] * self.pitch

    def _cell_of(self, px: tuple[int, int]) -> Cell:
        oy, ox = self.anchor
        return ((px[0] - oy) // self.pitch, (px[1] - ox) // self.pitch)

    def _locate(self, g: np.ndarray) -> Cell | None:
        """Where the avatar is now, by its own block, preferring the position
        nearest to where it was."""
        if self.tpl is None or self.anchor is None:
            return None
        p = self.pitch
        h, w = g.shape
        oy, ox = self.anchor
        best: Cell | None = None
        bestd = 1 << 30
        for cy in range((0 - oy) // p, (h - oy) // p + 1):
            for cx in range((0 - ox) // p, (w - ox) // p + 1):
                y, x = oy + cy * p, ox + cx * p
                if y < 0 or x < 0 or y + p > h or x + p > w:
                    continue
                if not np.array_equal(g[y:y + p, x:x + p], self.tpl):
                    continue
                d = 0 if self.pos is None else abs(cy - self.pos[0]) + abs(cx - self.pos[1])
                if d < bestd:
                    best, bestd = (cy, cx), d
        return best

    def _bootstrap(self, g: np.ndarray) -> None:
        """Learn pitch, lattice and the avatar's own block from one step that
        moved, and what the action that produced it means."""
        if self._prev is None or self._prev_action is None:
            return
        sig = move_signature(self._prev, g)
        if sig is None:
            return
        pitch, vac, occ = sig
        self.pitch = pitch
        self.anchor = occ
        self.tpl = g[occ[0]:occ[0] + pitch, occ[1]:occ[1] + pitch].copy()
        self.pos = (0, 0)
        self.start = (0, 0)
        dy = (occ[0] - vac[0]) // pitch
        dx = (occ[1] - vac[1]) // pitch
        self.dirs[self._prev_action] = (dy, dx)
        self.stood.add((0, 0))

    def _learn_dir(self, before: Cell, after: Cell, action: int) -> None:
        d = (after[0] - before[0], after[1] - before[1])
        if abs(d[0]) + abs(d[1]) == 1:
            self.dirs.setdefault(action, d)
        if len(self.dirs) == 3:
            missing = {(-1, 0), (1, 0), (0, -1), (0, 1)} - set(self.dirs.values())
            gap = [a for a in _MOVE_IDS if a not in self.dirs]
            if len(missing) == 1 and len(gap) == 1:
                self.dirs[gap[0]] = missing.pop()

    def _read_panel(self, g: np.ndarray, flat: int, island: set[tuple[int, int]]) -> None:
        """The status panel is the small square mark that lives OUTSIDE the
        visible disc. Its box is remembered once found, because the glyph drawn
        in it changes size and a box re-derived per frame would move with it."""
        if self.panel is not None:
            y0, x0, y1, x1 = self.panel
            key = icon_key(g[y0:y1 + 1, x0:x1 + 1], flat)
            if key is not None:
                self.tok = key
            return
        p = self.pitch or 5
        for y0, x0, hh, ww, size in _rect_components(g != flat):
            if (y0, x0) in island or abs(hh - ww) > 2 or not (3 <= hh <= 3 * p):
                continue
            if any((y, x) in island for y in range(y0, y0 + hh) for x in range(x0, x0 + ww)):
                continue
            side = max(hh, ww)
            key = icon_key(g[y0:y0 + side, x0:x0 + side], flat)
            if key is None:
                continue
            self.panel = (y0, x0, y0 + side - 1, x0 + side - 1)
            self.tok = key
            return

    def _scan(self, g: np.ndarray, flat: int) -> None:
        """Fold every cell inside the truthful disc into the accumulated map."""
        p = self.pitch
        cy, cx = self._cell_origin(self.pos)
        centre = (cy + (p - 1) / 2.0, cx + (p - 1) / 2.0)
        r = self.radius - 1.0
        h, w = g.shape
        panel = self.panel
        reach = int(r // p) + 2
        for dy in range(-reach, reach + 1):
            for dx in range(-reach, reach + 1):
                c = (self.pos[0] + dy, self.pos[1] + dx)
                y, x = self._cell_origin(c)
                if y < 0 or x < 0 or y + p > h or x + p > w:
                    continue
                far = max(abs(y - centre[0]), abs(y + p - 1 - centre[0])) ** 2 + \
                    max(abs(x - centre[1]), abs(x + p - 1 - centre[1])) ** 2
                if far > r * r:
                    continue
                if panel is not None and not (y + p - 1 < panel[0] or y > panel[2]
                                              or x + p - 1 < panel[1] or x > panel[3]):
                    continue
                blk = g[y:y + p, x:x + p]
                dom = Counter(int(v) for v in blk.ravel()).most_common(1)[0][0]
                if c == self.pos:
                    continue
                self.seen[c] = dom
                self.looked[c] = self.tick
                sig = cell_mark(blk, dom)
                if sig is None or dom in self.wall_colors:
                    self.mark.pop(c, None)
                    self.icon_cells.pop(c, None)
                    continue
                self.mark[c] = sig
                self.sighted[sig] = c
                self.lane.setdefault(sig, set()).add(c)
                trail = self.seen_at.setdefault(sig, [])
                if not trail or trail[-1] != (self.tick, c):
                    trail.append((self.tick, c))
                    del trail[:-3]
                if sig in self.kind or sig in self.inert or sig in self.refill_marks:
                    self.icon_cells.pop(c, None)
                    continue
                key = icon_key(blk[1:p - 1, 1:p - 1], dom)
                if key is not None:
                    self.icon_cells[c] = key
                    self.icon_seen[c] = key

    def _read_bar(self, g: np.ndarray, flat: int) -> None:
        """Track the drawn budget, identifying its colour by BEHAVIOUR.

        ⛔ The strip has two colours — spent and remaining — and which of them is
        the LONGER run depends entirely on how full it happens to be. Picking
        the longer one locks onto the spent half whenever the tool arrives at a
        low tank, and then every reading is INVERTED: it grows as actions are
        spent and drops when a refill tops it up. Measured on a mid-level
        handover, that one inversion filed every refill on the board as INERT —
        permanently — so the tool had no fuel model at all on the one board that
        needs one, and chased a changer for a third of its actions believing it
        was fuel.

        What identifies the budget is not its length, it is that it SHRINKS as
        actions are spent. So both colours are watched for a few frames and the
        one that falls is the one that is kept.
        """
        if self.bar_color is None:
            for colour, length in _bar_runs(g, flat).items():
                self._bar_hist.setdefault(colour, []).append(length)
            best, drop = None, 0
            for colour, hist in self._bar_hist.items():
                if len(hist) < 4:
                    continue
                fall = hist[0] - hist[-1]
                if fall > drop:
                    best, drop = colour, fall
            if best is None:
                return
            self.bar_color = best
        b = _bar(g, flat, self.bar_color)
        if b is None:
            return
        _colour, length, band = b
        self.bar_full = max(self.bar_full, band)
        if self.bar_len and length < self.bar_len:
            fall = self.bar_len - length
            self.bar_drop = fall if not self.bar_drop else min(self.bar_drop, fall)
        self.bar_len = length
        self._bar_seen = True

    def moves_left(self) -> int:
        if not self.bar_drop:
            return 1 << 20
        return max(0, self.bar_len // self.bar_drop)

    # -- map + plan ---------------------------------------------------------

    def _in_arena(self, c: Cell, shape: tuple[int, int]) -> bool:
        p = self.pitch
        y, x = self._cell_origin(c)
        if y < 0 or x < 0 or y + p > shape[0] or x + p > shape[1]:
            return False
        pn = self.panel
        if pn is not None and not (y + p - 1 < pn[0] or y > pn[2] or x + p - 1 < pn[1] or x > pn[3]):
            return False
        return True

    def _passable(self, c: Cell, shape: tuple[int, int]) -> bool:
        if not self._in_arena(c, shape):
            return False
        if c in self.walls:
            return False
        dom = self.seen.get(c)
        return not (dom is not None and dom in self.wall_colors)

    def _step_to(self, c: Cell, a: int) -> Cell:
        d = self.dirs[a]
        return self.edges.get((c, a), (c[0] + d[0], c[1] + d[1]))

    def _tok_after(self, c: Cell, t: Tok) -> Tok | None:
        """The token after entering ``c`` holding ``t`` — None when that press
        has never been observed and its result is therefore unknown.

        ⛔ Keyed by what is DRAWN in the cell, not by the cell. One of these
        boards carries a changer that PATROLS: its effect belongs to the mark,
        which travels, and a table keyed by coordinates loses it the moment it
        steps away. Identity by appearance also means the second changer of a
        kind is understood before it is ever touched."""
        sig = self.mark.get(c)
        if sig is None:
            # ⛔ A cell on a MOVING mark's beat still offers that mark's press.
            # Pinning a changer to the cell it was last drawn in makes any plan
            # needing it TWICE unfindable — it will not be in that cell the
            # second time, so the search never returns a route and the tool
            # falls back to wandering. What is true is weaker and sufficient:
            # stand on the beat and the mark comes past. Arrival timing is the
            # executor's problem, and `_hold` is how it waits.
            for msig, lane in self.lane.items():
                if len(lane) > 1 and c in lane and msig in self.kind:
                    # ⛔ Through the RULE, not the raw table. The mark whose beat
                    # this is is exactly the one whose table is thin, so reading
                    # its pairs here threw away the very generalisation that
                    # makes it usable — the win search stayed unsatisfiable with
                    # the target token fully reachable in the closure.
                    got = self._factored(msig, t) or self.kind[msig].get(t)
                    if got is not None:
                        return got
            return t
        if sig in self.inert or sig in self.refill_marks:
            return t
        table = self.kind.get(sig)
        if table is None:
            return None
        got = self._factored(sig, t)
        return table.get(t) if got is None else got

    def _factored(self, sig: frozenset[tuple[int, int, int]], t: Tok) -> Tok | None:
        """Apply a changer as a rule over ONE ATTRIBUTE rather than as a lookup."""
        rules = self._rules()
        kind = rules.get(sig)
        if kind is None:
            return None
        axis, table = kind
        if axis == "colour":
            nxt = table.get(t[1])
            return None if nxt is None else (t[0], nxt)
        if axis == "motion":
            return (_norm(_MOTIONS[table](t[0])), t[1])
        nxt = table.get(t[0])
        return None if nxt is None else (nxt, t[1])

    def _rules(self) -> dict[frozenset[tuple[int, int, int]], tuple[str, dict[Any, Any]]]:
        """Each mark as a permutation of ONE attribute, extended by commutation.

        ⛔ Two things are being recovered here and both were measured, not
        assumed.

        FIRST, that a mark moves one attribute and leaves the rest alone. A token
        is (shape-mask, colour) and the space is about a hundred wide, so storing
        transitions as (token -> token) pairs means each must be observed:
        measured, 51 pairs learned across three marks and the closure from the
        token actually held was THREE tokens in ONE colour, with the demanded
        token unreachable and the win search firing zero times in 1385 actions.
        Reading the invariant off the pairs instead took that closure to 68.

        SECOND, that marks moving DIFFERENT attributes COMMUTE — so a transition
        one of them has never been seen making can be derived from one it has:

            if  B(m) is known,  A(m) is known,  and  A(B(m)) is known,
            then  B(A(m))  =  A(B(m)).

        That matters because the three marks are not equally cheap to observe:
        one of them PATROLS, and an interception is rare, so its table stays thin
        however long the tool runs. Conjugating it through the mark that is cheap
        to press fills it in without a single extra action.

        ⛔ The inference is CHECKED before it is used. Commutation is verified on
        every case where both sides are already known, and a pair that disagrees
        even once is not conjugated — the tool would rather have a small correct
        table than a large invented one.
        """
        ver = sum(len(v) for v in self.kind.values())
        if self._rules_ver == ver:
            return self._rules_cache
        rules: dict[frozenset[tuple[int, int, int]], tuple[str, dict[Any, Any]]] = {}
        for sig, table in self.kind.items():
            pairs = list(table.items())
            if not pairs:
                continue
            if all(a[0] == b[0] for a, b in pairs):
                m = {a[1]: b[1] for a, b in pairs}
                axis = "colour"
            elif all(a[1] == b[1] for a, b in pairs):
                m = {a[0]: b[0] for a, b in pairs}
                axis = "mask"
            else:
                continue
            if len(set(m.values())) != len(m):     # a permutation, not a collapse
                continue
            motion = _motion_of(m) if axis == "mask" else None
            rules[sig] = ("motion", motion) if motion else (axis, m)
        movers = [sig for sig, (axis, _) in rules.items() if axis == "mask"]
        for _ in range(4):
            grew = False
            for a_sig in movers:
                for b_sig in movers:
                    if a_sig == b_sig:
                        continue
                    a, b = rules[a_sig][1], rules[b_sig][1]
                    if not self._commutes(a, b):
                        continue
                    for m in list(b):
                        ab = a.get(b[m])
                        if ab is None or a.get(m) is None or a[m] in b:
                            continue
                        b[a[m]] = ab
                        grew = True
            if not grew:
                break
        self._rules_ver, self._rules_cache = ver, rules
        return rules

    @staticmethod
    def _commutes(a: dict[Any, Any], b: dict[Any, Any]) -> bool:
        """A(B(x)) == B(A(x)) everywhere both sides are already known."""
        agree = 0
        for x in a:
            if x not in b:
                continue
            lhs = a.get(b[x])
            rhs = b.get(a[x])
            if lhs is None or rhs is None:
                continue
            if lhs != rhs:
                return False
            agree += 1
        return agree > 0

    def _search(self, shape: tuple[int, int], want: Any, learn: bool) -> int | None:
        """BFS in (cell, token) space; returns the first action of the route."""
        if self.pos is None or self.tok is None:
            return None
        start = (self.pos, self.tok)
        seen = {start}
        q: deque[tuple[Cell, Tok, int | None]] = deque([(self.pos, self.tok, None)])
        acts = [a for a in self.dirs if a in _MOVE_IDS]
        while q:
            c, t, first = q.popleft()
            for a in acts:
                nb = self._step_to(c, a)
                if nb == self.goal:
                    # ⛔ The target cell is decided by the token CARRIED IN, and
                    # it must be decided BEFORE asking what the cell does to the
                    # token. It displays the token it demands, so it carries a
                    # mark like a changer does — and an unlearned mark means
                    # "unknown effect", which the search skips. That skip fired
                    # on the winning move every single time: the token closure
                    # covered the demanded token, a neighbour of the cell was
                    # reachable, and the joint search still returned None
                    # because the one edge that ends the level was the one edge
                    # it refused to consider. A mark on the target can never be
                    # learned, because learning it means the level is over.
                    if t == self.target and want(nb, t):
                        return a if first is None else first
                    continue
                if not self._passable(nb, shape):
                    continue
                nt = self._tok_after(nb, t)
                head = a if first is None else first
                if nt is None:
                    # an unmeasured press: the discovery target itself
                    if learn:
                        return head
                    continue
                if want(nb, nt):
                    return head
                key = (nb, nt)
                if key in seen:
                    continue
                seen.add(key)
                q.append((nb, nt, head))
        return None

    def _reach(self, shape: tuple[int, int]) -> dict[Cell, int]:
        """Every cell the avatar can actually walk to -> the first action of the
        route. Learned edges are used, so a cell only a deflector delivers to
        appears here once that deflection has been felt."""
        if self.pos is None:
            return {}
        out: dict[Cell, int] = {}
        q: deque[tuple[Cell, int | None]] = deque([(self.pos, None)])
        seen = {self.pos}
        acts = [a for a in self.dirs if a in _MOVE_IDS]
        while q:
            c, first = q.popleft()
            for a in acts:
                nb = self._step_to(c, a)
                if nb == self.goal or not self._passable(nb, shape) or nb in seen:
                    continue
                head = a if first is None else first
                seen.add(nb)
                out[nb] = head
                q.append((nb, head))
        return out

    def _walk(self, shape: tuple[int, int], want: Any) -> int | None:
        """Walk toward the nearest wanted cell, recording how far it is so the
        caller can tell whether the tank covers it."""
        step, dist = self._walk_far(shape, want)
        self._plan_dist = dist if step is not None else None
        return step

    def _walk_far(self, shape: tuple[int, int], want: Any) -> tuple[int | None, int]:
        """Plain cell BFS: (first action, distance) to the nearest wanted cell."""
        if self.pos is None:
            return None, 0
        seen = {self.pos}
        q: deque[tuple[Cell, int | None, int]] = deque([(self.pos, None, 0)])
        acts = [a for a in self.dirs if a in _MOVE_IDS]
        while q:
            c, first, d = q.popleft()
            for a in acts:
                nb = self._step_to(c, a)
                if nb == self.goal or not self._passable(nb, shape) or nb in seen:
                    continue
                head = a if first is None else first
                if want(nb):
                    self._aim_cell = nb
                    return head, d + 1
                seen.add(nb)
                q.append((nb, head, d + 1))
        return None, 0

    def _frontier(self, shape: tuple[int, int]) -> int | None:
        def unexplored(c: Cell) -> bool:
            for d in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nb = (c[0] + d[0], c[1] + d[1])
                if nb not in self.seen and nb not in self.stood and self._in_arena(nb, shape):
                    return True
            return False
        return self._walk(shape, unexplored)

    def _plan(self, shape: tuple[int, int]) -> int | None:
        """Win if the walk exists; otherwise buy the cheapest missing fact.

        ⛔ The ORDER is the whole design and the first version had it wrong. It
        pressed changers to complete their tables before finishing the map,
        and a table over a token space of a hundred values never completes —
        the tool spent an entire budget pressing two marks it already
        understood while the third, the one the target actually demanded, sat
        in a corridor it had not walked. Mapping is FINITE and it is what makes
        the win search possible at all, so it comes first."""
        if self.goal is not None and self.target is not None:
            win = self._search(shape, lambda c, t: c == self.goal and t == self.target, False)
            if win is not None:
                self._say("win")
                return win
        edge = self._frontier(shape)
        if edge is not None:
            self._say("map")
            return edge
        # Any cell carrying a mark this tool has never stepped on. Identity is
        # the MARK, so one visit teaches every cell that carries it — which is
        # what makes a board of eight refills cost one probe instead of eight.
        def unlearned(sig: frozenset[tuple[int, int, int]]) -> bool:
            return (sig not in self.kind and sig not in self.inert
                    and sig not in self.refill_marks)

        fresh: set[Cell] = set()
        for c, sig in self.mark.items():
            if c == self.goal or not unlearned(sig):
                continue
            # ⛔ Aim where the mark WILL be, not where it is. The patrolling
            # changer moves one cell before the avatar's action is applied, so
            # chasing its current cell is a pursuit that never closes: measured,
            # a thousand actions spent in its corridor, stepping into the cell
            # it had just left, and its rule never once observed.
            target = self._intercept(c, sig, shape)
            self.aim[target] = sig
            fresh.add(target)
        # ⛔ Include the LAST PLACE each unlearned mark was seen, not only where
        # one is standing right now. The patrolling changer is visible for a
        # frame or two and then the cell it was in reads as plain floor again,
        # so a live-only list forgot it the moment it stepped away: measured,
        # the tool saw that mark once at action 601 and then walked the other
        # half of the board for six hundred more without ever going back. A
        # sighting is a place to go looking; a live mark is a place to step.
        # ⛔ But a sighting goes STALE once it has been walked to and found
        # empty. Chasing one forever is what a moving mark turns this rule into:
        # measured, the tool walked to the same cell for a thousand actions,
        # arriving after the mark had moved on every time, and pressed the two
        # changers it could actually reach exactly three times in the whole run.
        # A checked sighting is worth re-checking later, not immediately.
        fresh |= {c for sig, c in self.sighted.items()
                  if c != self.goal and unlearned(sig)
                  and self.tick - self.checked.get(sig, -_SIGHT_RETRY) >= _SIGHT_RETRY}
        if self.pos in fresh:
            hold = self._hold(shape)
            if hold is not None:
                self._say("wait")
                return hold
            fresh.discard(self.pos)
        if fresh:
            step = self._walk(shape, lambda c: c in fresh)
            if step is not None:
                self._say(f"mark{sorted(fresh)}")
                return step
            # Not an action — the walk failed and a later clause will produce
            # one. Recording it as a decision inflated it to 286 of 354, which
            # reads as the tool's dominant activity and is nothing of the kind.
            self.reason = f"mark-unreachable{sorted(fresh)}"
        # ⛔ A cell that has been SEEN is not a cell that has been WALKED. The
        # map's passability is a prediction from colour, and this family breaks
        # it in one direction: a deflector cell sends the avatar somewhere else
        # entirely, and the somewhere else can be a whole region no ordinary
        # step reaches. Measured: a third of this board — including the mark the
        # target demanded — sat behind exactly one such cell, mapped as open,
        # predicted reachable, and never once stepped on.
        # ⛔ Treading is LOAD-BEARING and gating it on "the objective is already
        # known" was measured to lose the level outright, from clearing to not
        # reaching it at every handover. It is not idle wandering: a deflector
        # cell lands the avatar somewhere the map does not predict, and one such
        # cell is the only way into a third of this board. The route in is
        # discovered by stepping on cells, not by looking at them.
        untrod = self._walk(shape, lambda c: c not in self.stood and c not in self.give_up)
        if untrod is not None:
            self._say("tread")
            return untrod
        # Nothing new is VISIBLE, which does not mean there is nothing new: one
        # of this family's changers PATROLS, so a board mapped once has a hole
        # in it that no frontier can report.
        #
        # ⛔ Re-LOOK before pressing again. Completing a changer's table is an
        # infinite sink — the token space is a hundred values wide and every
        # press teaches one entry — so a tool that ranks pressing above looking
        # spends the whole budget perfecting two marks it already understands.
        # Measured: two complete tables, twenty-four entries each, and the mark
        # the target actually demanded never once seen.
        if self.tick - self._oldest_look(shape) > _STALE_LOOK:
            look = self._patrol(shape)
            if look is not None:
                return look
        if self.kind:
            # ⛔ Nearest unmeasured press, NOT the mark that most needs learning.
            # Directing effort at the thinnest rule was measured twice and lost
            # both times — by raw pair count and again by rule domain, the closure
            # falling 68 -> 48 — because the mark that needs learning is the one
            # that MOVES, and walking across the board to miss it costs more than
            # the presses it displaces. The binding constraint is interception
            # rate, not press allocation.
            press = self._search(shape, lambda c, t: False, True)
            if press is not None:
                self._say("press")
                return press
        # Last resort is still a LOOK, never a random step: with the map
        # complete and every known table full, the only thing left that can
        # change is where the moving mark is.
        look = self._patrol(shape)
        if look is not None:
            return look
        self._say("idle")
        return None

    def _hold(self, shape: tuple[int, int]) -> int | None:
        """Spend an action WITHOUT moving, by pushing into a known wall.

        There is no wait action on these boards — every action is a step — so
        the only way to let a moving thing come to you is to step at something
        that refuses. It costs one unit of the drawn budget and nothing else.
        """
        if self.pos is None:
            return None
        for a in self.dirs:
            if a not in _MOVE_IDS:
                continue
            nb = self._step_to(self.pos, a)
            if nb == self.pos or (nb in self.walls and nb != self.goal):
                return a
        return None

    def _patrol(self, shape: tuple[int, int]) -> int | None:
        """Walk to the cell seen longest ago.

        ⛔ The OLDEST cell, not the nearest stale one. Nearest made the tool
        shuffle on the spot: the cells it had just left were the first to go
        stale again, so it refreshed its own doorstep for a thousand actions
        and never returned to the far corridor. The point of re-looking is to
        be somewhere else."""
        # ⛔ Only cells the avatar can actually WALK TO. Every visible cell is
        # logged as looked at, walls and the far side of a one-way deflector
        # included, and those are always the oldest things on the board — so a
        # minimum over "looked" picked an unreachable target every single time
        # and the patrol never once fired in a twelve-hundred-action run.
        reach = self._reach(shape)
        opts = [c for c in reach if c in self.looked]
        if not opts:
            return None
        oldest = min(opts, key=lambda c: self.looked[c])
        self._say(f"look{oldest}")
        return reach[oldest]

    def _intercept(self, c: Cell, sig: frozenset[tuple[int, int, int]],
                   shape: tuple[int, int]) -> Cell:
        """Where to stand to actually MEET a mark that is moving.

        ⛔ Walking at it does not work in either obvious form. Its cell is stale
        the moment the frame is drawn — the mark steps before the avatar's
        action is applied — and its NEXT cell only helps when the avatar is
        already in front of it; from behind, aiming one cell ahead is a chase
        that never closes, and that is what a thousand actions in its corridor
        bought. So: intercept when the next cell is already within reach, and
        otherwise AMBUSH — stand at the far end of the beat it has been seen
        walking, and let it come. A mark that patrols always comes back.
        """
        nxt = self._predict(sig)
        if nxt is None or not self._passable(nxt, shape) or self.pos is None:
            return c
        if abs(nxt[0] - self.pos[0]) + abs(nxt[1] - self.pos[1]) <= 1:
            return nxt
        lane = [q for q in self.lane.get(sig, ()) if self._passable(q, shape)]
        if not lane:
            return nxt
        near = min(lane, key=lambda q: abs(q[0] - self.pos[0]) + abs(q[1] - self.pos[1]))
        if abs(near[0] - self.pos[0]) + abs(near[1] - self.pos[1]) > 1:
            # Not on the beat yet: go stand at the far end of it and let the
            # mark walk back into reach.
            return max(lane, key=lambda q: abs(q[0] - c[0]) + abs(q[1] - c[1]))
        # ⛔ On the beat and the mark is walking AWAY: WAIT, do not follow. A
        # chase from behind never closes — both move one cell a tick — and it
        # was 72 misses out of 74 arrivals. Holding position costs one budget
        # unit and the patrol brings itself back.
        return self.pos

    def _predict(self, sig: frozenset[tuple[int, int, int]]) -> Cell | None:
        """Where a mark seen moving will be on the next frame, or None if it has
        not been seen moving."""
        trail = self.seen_at.get(sig) or []
        if len(trail) < 2:
            return None
        (t0, c0), (t1, c1) = trail[-2], trail[-1]
        if t1 != t0 + 1 or t1 != self.tick:
            return None
        dy, dx = c1[0] - c0[0], c1[1] - c0[1]
        if abs(dy) + abs(dx) != 1:
            return None
        # ⛔ Straight-line only. Predicting the TURN-AROUND at the end of the
        # beat was tried and measured WORSE on this deterministic board — the
        # learned transitions went 2 -> 1 — because a beat assembled from
        # sightings is not the true track, so "the cell ahead is one it has
        # never been in" fires in the middle of the walk as well as at its end.
        return (c1[0] + dy, c1[1] + dx)

    def _oldest_look(self, shape: tuple[int, int]) -> int:
        reach = self._reach(shape)
        return min((t for c, t in self.looked.items() if c in reach), default=self.tick)

    # -- driving ------------------------------------------------------------

    def _ingest(self, g: np.ndarray, flat: int, island: list[tuple[int, int]] | None) -> None:
        if self.pitch is None:
            self._bootstrap(g)
            if self.pitch is None:
                return
        here = self._locate(g)
        if here is None:
            # Mid-animation the avatar is between cells and cannot be found. The
            # actions spent here are SWALLOWED, and what happens next is not
            # their doing.
            self._blind += 1
            self._lost = True
            return
        lost, self._lost = self._lost, False
        self._blind = 0
        self.tick += 1
        prev_pos, prev_tok, action = self.pos, self.tok, self._prev_action
        # What was DRAWN in the cell just entered — and only if it was seen there
        # on the PREVIOUS frame.
        #
        # ⛔ A remembered mark is not a present one. The patrolling changer
        # leaves its signature in the map at the cell it was last seen in; walk
        # there two moves later and it has gone, the token does not change, and
        # the tool concludes the mark is INERT — permanently, and about the one
        # mark the level's target actually required. Measured: the mover was
        # found, chased, stepped on, written off, and never considered again.
        mark = self.mark.get(here) if self.looked.get(here) == self.tick - 1 else None
        # ⛔ And if the map has nothing there, fall back to what the tool was
        # AIMING at. Intercepting a moving mark means stepping into a cell the
        # map has never seen it in — it arrives the same tick — so the map's
        # answer is None exactly when the interception SUCCEEDS. Measured: the
        # avatar reached the interception square 74 times, the token changed,
        # and every one of those observations was thrown away because the cell
        # it happened in carried no recorded mark.
        if mark is None:
            mark = self.aim.get(here)
        # ⛔ Standing on a cell ERASES what the map remembers about it, whether
        # or not anything was learned. The avatar covers the cell, so the record
        # cannot be refreshed from here — and a stale record of a mark that has
        # since walked away reads as a live one, which sent the tool back to the
        # same empty cell for 1044 of 1200 actions.
        self.mark.pop(here, None)
        self.pos = here
        self.stood.add(here)
        for sig, c in self.sighted.items():
            if c == here:
                self.checked[sig] = self.tick
        p = self.pitch
        oy, ox = self._cell_origin(here)
        centre = (oy + (p - 1) / 2.0, ox + (p - 1) / 2.0)
        if island:
            far = max(((y - centre[0]) ** 2 + (x - centre[1]) ** 2) for y, x in island) ** 0.5
            self.radius = max(self.radius, far)

        before_bar = self.bar_len
        self._read_bar(g, flat)
        if island:
            self._read_panel(g, flat, set(island))
        elif self.panel is not None:
            self._read_panel(g, flat, set())
        if self.radius:
            self._scan(g, flat)

        if lost:
            # ⛔ Attribute NOTHING across a blind gap. A deflector slides the
            # avatar over several frames; during them the tool sends actions it
            # cannot read the results of, and the landing then gets pinned on
            # whichever action happened to be last. Worse, the frames in between
            # look like refusals, and two of those write the passage off as a
            # wall — which is how the only route into a third of this board came
            # to be marked closed. See [[concepts/swallowed_action]].
            self._prev_tok = self.tok
            self.fails.clear()
            return
        if prev_pos is None or action is None or action not in self.dirs and prev_pos == here:
            self._prev_tok = self.tok
            return
        # ⛔ NOT `> before_bar > 0`. That extra clause excluded the very case a
        # refill exists for: the tank is EMPTY. Measured on a mid-level handover
        # where the tool is chronically at zero, every refill it stood on was
        # filed INERT — permanently, since nothing re-examines that set — and it
        # then had no fuel model at all on the one board that needs one.
        # ⛔ Not `> before_bar > 0` either — that clause excluded the very case a
        # refill exists for, an EMPTY tank, and on a mid-level handover where
        # the tool is chronically at zero every refill it stood on was filed
        # INERT, permanently, since nothing re-examines that set. What the
        # clause was really guarding is the FIRST reading, where `before_bar` is
        # a sentinel rather than a measurement; guard that directly.
        refilled = self._bar_seen and self.bar_len > before_bar
        adjacent = abs(here[0] - prev_pos[0]) + abs(here[1] - prev_pos[1]) <= 1
        if refilled and not adjacent:
            # ⛔ A LIFE ENDED. The budget went back to full and the avatar is not
            # where a step could have put it: it was thrown home, the token was
            # reset with it, and every consumed refill is back. Read as an
            # ordinary move this taught the tool three lies at once — that the
            # landing cell refills, that it forces the starting token, and that
            # there is an edge from where the avatar died to where it now is.
            # All three were measured in the accumulated model before this
            # branch existed.
            self.home = here
            self._prev_tok = self.tok
            self.fails.clear()
            return
        if here != prev_pos:
            if action in self.dirs:
                self.edges[(prev_pos, action)] = here
                self.fails.pop((prev_pos, action), None)
            self._learn_dir(prev_pos, here, action)
            if mark is not None:
                # ⛔ A refill RESETS the strip; it does not nudge it. Calling any
                # upward tick a refill is how the model came to hold two kinds
                # SWAPPED — measured on a mid-level handover, the refill ring
                # filed as INERT and the colour changer filed as a REFILL. After
                # that the tool chased the changer believing it was fuel (a
                # third of every action), never refuelled, and never learned a
                # changer at all, because a mark in `refill_marks` is read as
                # leaving the token alone. One noisy frame-to-frame delta
                # mislabelled the board and every later symptom followed from it.
                jump = self.bar_len - before_bar
                if refilled and jump >= max(2, self.bar_full // 4):
                    self.refill_marks.add(mark)
                    self.inert.discard(mark)
                elif prev_tok is not None and self.tok is not None and self.tok != prev_tok:
                    self.kind.setdefault(mark, {})[prev_tok] = self.tok
                    self.inert.discard(mark)
                elif mark not in self.kind:
                    self.inert.add(mark)
                self.mark.pop(here, None)
                self.icon_cells.pop(here, None)
        elif action in self.dirs:
            d = self.dirs[action]
            blockedc = (prev_pos[0] + d[0], prev_pos[1] + d[1])
            dom = self.seen.get(blockedc)
            key = (prev_pos, action)
            self.fails[key] = self.fails.get(key, 0) + 1
            if blockedc in self.icon_seen:
                # A cell that REFUSES entry while showing a token is the target:
                # the token it shows is the one it demands.
                #
                # ⛔ Checked against every icon EVER seen there, not against the
                # live worklist. The worklist is pruned as marks are understood
                # and holds only what is visible now, so a target bumped while it
                # sat at the rim of the visible disc was absent from it — and
                # fell through to the branch below, which filed the target as a
                # WALL and its colour as a wall colour. Measured: handed the
                # level 40 actions in rather than at its first frame, the tool
                # never identified the target at all in 1545 actions, and every
                # later plan was searching for a cell it had itself sealed off.
                self.goal = blockedc
                self.target = self.icon_seen[blockedc]
            elif dom is not None and dom not in self.floor_colors:
                self.walls.add(blockedc)
                # ⛔ ONE refusal is not a colour. Generalising from a single
                # blocked cell is how the target's own colour became "wall" —
                # after which every cell drawn in it was impassable, including
                # the one the level ends on. A colour earns the label by
                # refusing at two DIFFERENT cells.
                seen_at = self.refusals.setdefault(dom, set())
                seen_at.add(blockedc)
                if len(seen_at) >= 2:
                    self.wall_colors.add(dom)
            if self.fails[key] >= 2:
                # ⛔ Twice, not once. An action that arrives mid-animation is
                # SWALLOWED ([[concepts/swallowed_action]]) and a single failure
                # would wall off a passage that is open. Two failures from the
                # same cell are a rule; the edge is recorded as a self-loop so
                # the planner routes around whatever caused it — a wall, a
                # refusal, or a deflector that puts the avatar back.
                self.edges[key] = prev_pos
        for c in self.stood:
            dom = self.seen.get(c)
            if dom is not None:
                self.floor_colors.add(dom)
                self.wall_colors.discard(dom)
        self._prev_tok = self.tok

    def _say(self, why: str) -> None:
        self.reason = why
        self.census[why.split("[")[0]] += 1

    def state_key(self, frame: np.ndarray) -> str:
        """The harness's progress measure, in the tool's OWN terms.

        ⛔ Under fog the raw frame is the wrong yardstick in BOTH directions. The
        budget bar redraws every action, so a tool pinned against a wall looks
        like it is progressing; and the visible disc is identical from any two
        cells with the same surroundings, so real exploration can look static.
        What this tool accomplishes is BELIEF — cells mapped, marks understood,
        token held, position. `harness/loop.py` asks the active tool for this key
        precisely so that "no new state" means what the tool is for; a tool that
        does not answer is judged by a frame hash instead.
        """
        return (f"{len(self.seen)}|{len(self.stood)}|{len(self.kind)}|"
                f"{sum(len(v) for v in self.kind.values())}|{self.pos}|{self.tok}")

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            self._say("no-frame")
            return []
        g = frame_2d(obs).astype(np.int16)
        simple, _ = availability(obs)
        acts = [a for a in _MOVE_IDS if a in simple]
        if not acts:
            self._say("no-moves")
            return []
        view = fog_view(g)
        if view is not None:
            self.flat, island = view[0], view[1]
        elif self.flat is None:
            # Not this tool's board yet, and nothing learned to fall back on.
            self._say("unfogged")
            return [(acts[0], None)]
        else:
            # ⛔ The disc test is for CLAIMING the board, not for reading it. A
            # refused move and a deflection both put an overlay on the frame that
            # fails the test, and returning a fixed action on those frames made
            # the tool alternate two moves for the whole budget: the plan asked
            # for one, its unreadable result asked for the other, and neither was
            # ever recorded. The flat colour is a property of the LEVEL, so once
            # it is known every frame is readable.
            island = None
        self._ingest(g, self.flat, island)
        if self.pitch is None or self.pos is None:
            self._probe_cycle += 1
            self._say("lost" if self.pitch is not None else "bootstrap")
            return [(acts[self._probe_cycle % len(acts)], None)]
        unprobed = [a for a in acts if a not in self.dirs]
        if unprobed:
            self._say("probe-dir")
            return [(unprobed[0], None)]
        before = len(self.stood)
        # ⛔ PLAN FIRST, refuel only when the plan cannot be finished on what is
        # left in the tank. Checking the tank first looks safer and is not: the
        # tool is chronically near-empty on this family, so a refill was almost
        # always "worth diverting to", and every diversion ABANDONED the walk in
        # progress. Measured on a mid-level handover — which is the only kind
        # the harness ever gives, since the incumbent keeps the board across a
        # level-up — refuelling took half the actions, the tool never once
        # completed the walk to the target cell, and so never learned what the
        # target even demands. Given the same level from its first frame it
        # cleared it in 206 actions.
        prev_aim = self._aim_cell
        self._aim_cell = None
        self._plan_dist = None
        step = self._plan(g.shape)
        if self._aim_cell is not None:
            sig = self.mark.get(self._aim_cell)
            if self._aim_cell in self.icon_seen:
                self.aimed["icon"] += 1
            elif sig is not None and sig in self.refill_marks:
                self.aimed["refill"] += 1
            elif self._aim_cell in self.seen or self._aim_cell in self.stood:
                self.aimed["mapped cell"] += 1
            else:
                self.aimed["unseen cell"] += 1
        if prev_aim is not None and prev_aim != self._aim_cell:
            if self.pos == prev_aim:
                self.arrived += 1
            else:
                self.abandoned += 1
        # Skip the tank only when the plan's target distance is KNOWN and within
        # reach; a plan whose cost is unknown gets the cautious branch.
        if step is None or self._plan_dist is None or self._plan_dist > self.moves_left():
            fuel = self._refuel(g.shape)
            if fuel is not None:
                # ⛔ One action, one census entry. The overridden plan already
                # counted itself, so leaving it in made the percentages sum past
                # 100 and overstated whichever branch refuel kept interrupting.
                self.census[self.reason.split("[")[0]] -= 1
                step = fuel
                self._say("refuel")
        # ⛔ Give up on a target that is not getting closer. Predicted
        # reachability is a belief, and when it is wrong the walk oscillates
        # between the same two cells for hundreds of actions — measured: five
        # hundred and fifteen of twelve hundred spent in one column. A pursuit
        # that has not added a single new cell in `_PURSUIT_CAP` actions is
        # abandoned and the cell it was chasing is struck off.
        tag = self.reason.split("[")[0]
        if tag == self._pursuit[0] and before == self._trod_at:
            self._pursuit = (tag, self._pursuit[1] + 1)
        else:
            self._pursuit = (tag, 0)
        self._trod_at = before
        if self._pursuit[1] > _PURSUIT_CAP:
            self._pursuit = (tag, 0)
            far = self._reach(g.shape)
            unseen = [c for c in far if c not in self.stood and c not in self.give_up]
            if unseen:
                self.give_up.add(min(unseen, key=lambda c: abs(c[0] - self.pos[0]) + abs(c[1] - self.pos[1])))
        if step is None:
            self._probe_cycle += 1
            step = acts[self._probe_cycle % len(acts)]
        return [(step, None)]

    def _refuel(self, shape: tuple[int, int]) -> int | None:
        """Divert to a refill cell when the drawn budget is about to run out.

        Running out is not fatal — it costs a life and throws the avatar back to
        the start — but it also throws away every step of the current approach,
        which under a squared-efficiency metric is the expensive part."""
        live = {c for c, sig in self.mark.items() if sig in self.refill_marks}
        if not live:
            return None
        step, dist = self._walk_far(shape, lambda c: c in live)
        if step is None:
            return None
        # ⛔ Go at the last possible moment AND only when the tank is genuinely
        # low. "Within reach of the next refill" is almost always true on a
        # board with several of them and a life of twenty-one moves, so the
        # first version diverted continuously: measured inside the harness,
        # refuelling was 206 of the 342 actions it was given and it learned
        # ZERO changers in that time — it shuttled between refills for its whole
        # tenure and was retired for making no progress, which was exactly true.
        # ⛔ GO WITH SLACK, not on the last unit. `left <= dist + 1` is a route
        # that arrives with an empty tank, and it has no margin for the walk
        # being longer than the map predicts — a deflector, a refused step, a
        # refill that turns out to be behind one. Measured over 24 deterministic
        # runs of ls20 (scripts/_ls20_fuelfan*.py): level 7 costs 303 actions at
        # slack 1 and 237 at slack 4, running dry five times instead of four,
        # and every slack from 2 to 6 lands on the same 237-239 plateau. So the
        # lever is HAVING slack; the exact number is not a tuning surface, and
        # it is written against the tank so a smaller one is not over-served.
        left = self.moves_left()
        full = self.bar_full // self.bar_drop if self.bar_drop else 0
        if full and left > max(3, full // 3):
            return None
        return step if left <= dist + max(3, full // 5) else None
