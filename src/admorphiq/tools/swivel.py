"""Swivel tool — jointed arms that TURN as well as telescope, driven by framed controls.

This is the same family of boards as `telescope` and deliberately disjoint from it: that tool
declines any board carrying a one-way control, this one requires at least one, so the two can
never bid on the same board. The split is not tidiness. A one-way control TURNS its bars ninety
degrees about their anchors, which re-aims every arm below them and destroys the one property
`telescope` is built on — that a carried thing translates by a fixed vector per click. Bolting
turning onto that tool would put five levels already scoring 1.0 at risk to chase three more.

The mechanic, in frame terms:

  * BARS are rectangles `U` across and `k*U - 1` along, capped at one end by an anchor stripe;
  * a two-way control lengthens or shortens every bar of its colour by one unit;
  * a ONE-WAY control turns every bar of its colour a quarter turn about its anchor, and carries
    everything hanging off that bar around with it;
  * whatever a bar carries — another bar, a RIDER, a plain blocker — is transformed with it;
  * a click that would overlap two bars is applied, tested, and UNDONE, at full budget cost;
  * the level is won when every destination ring has a rider on it.

⛔ THE TURN IS EXACT AND IT WAS MEASURED, NOT GUESSED. A bar's pivot is the top-left of its
ANCHOR unit, and the bar and every descendant map by `(rx, ry) -> (ry, -rx - (w - U))` about that
pivot with their boxes transposing, where `w` is each sprite's own pre-turn width. Checked
against the engine on a live board: predicted sprite box `(9, 48, 11, 53)`, actual
`(9, 48, 11, 53)`, and the rider landed on the predicted tip. Because the model is exact, the
whole plan is computed before the first click and refusals are predicted rather than collected.

⛔ THE PARENT-CHILD TREE CANNOT BE READ OFF THE FRAME, and assuming otherwise is the trap here.
"A child's anchor unit abuts its parent's tip unit" looks obviously right, matches the two
simplest boards, and is WRONG ON SIX OF EIGHT — it over-links a cluster of four bars into ten
links where the game declares three, finds none at all on a board that declares four, and misses
a whole family on another. The tree is therefore PROBED: one click per control, and whatever
moved with it is that control's subtree. Nesting those sets orders the tree.

⛔ DO NOT RE-READ THE BARS EVERY FRAME. Turning a bar routinely parks it against another, and a
bar with a neighbour at both ends stops satisfying the "exactly one anchor" test — measured, the
colour-11 bar vanished from the reading one click after a turn it was not even involved in. The
configuration is carried in the model and only CHECKED against the frame.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from itertools import permutations
from typing import Any

import numpy as np

# One perception grammar, shared rather than re-derived — the whole point of putting the
# readers in a module of their own.
from admorphiq.tools.base import Step, availability, has_frame, levels_completed
from admorphiq.tools.telescope import (
    _UNIT,
    _layers,
    _widget_colours,
    anchored_bars,
    marker_colour,
    read_markers,
    read_pieces,
    read_widgets,
    solid_cells,
)

__all__ = ["SwivelArmTool", "Config", "sprite_box", "anchor_pivot", "turn_box"]

Cell = tuple[int, int]
Box = tuple[int, int, int, int]

# A plan of more clicks than this is not a plan on boards whose budgets run 100 to 200.
_MAX_PLAN = 60
# Configurations to open before giving up. The reachable space is small — a handful of bars,
# four orientations each and a short length range — so this is generous, not hopeful.
_MAX_OPEN = 120_000
# Attempts to characterise one control before giving up on it for this level.
_MAX_TRIES = 2


# --- geometry ----------------------------------------------------------------


def sprite_box(body: Box, edge: int) -> Box:
    """The whole bar including its anchor stripe — what the engine actually moves.

    `read_pieces` returns the BODY, because the stripe is a different colour and comes back as
    its own region. The stripe is one line beyond the body on the anchor side.
    """
    y0, x0, y1, x1 = body
    if edge == 0:
        return (y0, x0, y1 + 1, x1)
    if edge == 2:
        return (y0 - 1, x0, y1, x1)
    if edge == 1:
        return (y0, x0, y1, x1 + 1)
    return (y0, x0 - 1, y1, x1)


def anchor_pivot(box: Box, edge: int) -> Cell:
    """The point a bar turns about: the top-left corner of its anchor unit."""
    y0, x0, y1, x1 = box
    h, w = y1 - y0 + 1, x1 - x0 + 1
    if edge == 0:
        return (x0, y0 + h - _UNIT)
    if edge == 1:
        return (x0 + w - _UNIT, y0)
    return (x0, y0)


def turn_box(box: Box, ax: int, ay: int) -> Box:
    """One quarter turn of a sprite box about (ax, ay), exactly as the engine does it."""
    y0, x0, y1, x1 = box
    h, w = y1 - y0 + 1, x1 - x0 + 1
    nx = ax + (y0 - ay)
    ny = ay - (x0 - ax) - (w - _UNIT)
    return (ny, nx, ny + w - 1, nx + h - 1)


# ⛔ MEASURED against the engine, and the obvious guess is backwards. The turn sends a bar that
# extends DOWN to one that extends RIGHT, not LEFT: a direction (dx, dy) maps to (dy, -dx), so
# the cycle runs down -> right -> up -> left. The occupancy check cannot catch this on its own —
# the boxes agree and only the next lengthening reveals which way the bar now grows.
_TURNED_EDGE = {2: 3, 3: 0, 0: 1, 1: 2}


def far_unit(box: Box, edge: int) -> Box:
    """The unit at the bar's far end — where its rider sits."""
    y0, x0, y1, x1 = box
    if edge == 0:
        return (y0, x0, y0 + _UNIT - 1, x1)
    if edge == 2:
        return (y1 - _UNIT + 1, x0, y1, x1)
    if edge == 1:
        return (y0, x0, y1, x0 + _UNIT - 1)
    return (y0, x1 - _UNIT + 1, y1, x1)


def _overlap(a: Box, b: Box) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _shift(box: Box, dy: int, dx: int) -> Box:
    return (box[0] + dy, box[1] + dx, box[2] + dy, box[3] + dx)


def _box_cells(box: Box) -> set[Cell]:
    return {(y, x) for y in range(box[0], box[2] + 1) for x in range(box[1], box[3] + 1)}


def body_cells(box: Box, edge: int) -> set[Cell]:
    """A bar's own colour occupies everything but the one line its anchor stripe sits on."""
    y0, x0, y1, x1 = box
    if edge == 0:
        y1 -= 1
    elif edge == 2:
        y0 += 1
    elif edge == 1:
        x1 -= 1
    else:
        x0 += 1
    return _box_cells((y0, x0, y1, x1))


# --- the configuration -------------------------------------------------------


@dataclass(frozen=True)
class Config:
    """Every moving thing on the board, as it stands. Hashable, so the search can walk it."""

    bars: tuple[tuple[Box, int], ...]      # (sprite box, far edge) per bar
    freight: tuple[Box, ...]               # blockers carried by bars, in model order

    def key(self) -> tuple:
        return (self.bars, self.freight)


@dataclass
class _Model:
    colours: list[int]                      # bar colour per bar index
    kids: list[list[int]]                   # bars carried by each bar (its subtree, direct+below)
    load: list[list[int]]                   # freight indices carried by each bar
    grow_of: dict[int, int]                 # two-way control index -> colour it drives
    turn_of: dict[int, int]                 # one-way control index -> colour it drives
    parent: list[int]                       # immediate parent bar, or -1
    wall: Any = None                        # rasterised immovable furniture, padded
    static: set[Cell] = field(default_factory=set)
    places: list[Cell] = field(default_factory=list)
    riders: list[int] = field(default_factory=list)     # bar indices that carry a rider
    pairing: tuple[tuple[int, int], ...] | None = None
    refuted: set[tuple[tuple[int, int], ...]] = field(default_factory=set)

    def of_colour(self, c: int) -> list[int]:
        return [i for i, col in enumerate(self.colours) if col == c]


def _length(box: Box, edge: int) -> int:
    y0, x0, y1, x1 = box
    return (y1 - y0 + 1) if edge in (0, 2) else (x1 - x0 + 1)


def grow(model: _Model, cfg: Config, colour: int, step: int) -> Config | None:
    """Lengthen or shorten every bar of one colour, carrying what each of them holds."""
    bars = list(cfg.bars)
    freight = list(cfg.freight)
    for i in model.of_colour(colour):
        box, edge = bars[i]
        if step < 0 and _length(box, edge) <= _UNIT:
            continue                       # a bar at one unit cannot be shortened further
        dy = dx = 0
        y0, x0, y1, x1 = box
        if edge == 0:
            y0 -= _UNIT * step
            dy = -_UNIT * step
        elif edge == 2:
            y1 += _UNIT * step
            dy = _UNIT * step
        elif edge == 1:
            x0 -= _UNIT * step
            dx = -_UNIT * step
        else:
            x1 += _UNIT * step
            dx = _UNIT * step
        if y1 - y0 < _UNIT - 1 or x1 - x0 < _UNIT - 1:
            return None
        bars[i] = ((y0, x0, y1, x1), edge)
        for j in model.kids[i]:
            bars[j] = (_shift(bars[j][0], dy, dx), bars[j][1])
        for f in model.load[i]:
            freight[f] = _shift(freight[f], dy, dx)
    return Config(tuple(bars), tuple(freight))


def swivel(model: _Model, cfg: Config, colour: int) -> Config | None:
    """Turn every bar of one colour a quarter turn, carrying its whole subtree round with it.

    ⛔ The DOUBLE turn is part of the mechanic, not a special case to skip: a bar whose parent
    faces the opposite way turns twice on one click. It is decided from the two orientations,
    which the model already tracks.
    """
    bars = list(cfg.bars)
    freight = list(cfg.freight)
    for i in model.of_colour(colour):
        box, edge = bars[i]
        p = model.parent[i]
        times = 2 if p >= 0 and (edge - bars[p][1]) % 4 == 2 else 1
        for _ in range(times):
            ax, ay = anchor_pivot(bars[i][0], bars[i][1])
            for j in model.kids[i]:
                bars[j] = (turn_box(bars[j][0], ax, ay), _TURNED_EDGE[bars[j][1]])
            for f in model.load[i]:
                freight[f] = turn_box(freight[f], ax, ay)
            bars[i] = (turn_box(bars[i][0], ax, ay), _TURNED_EDGE[bars[i][1]])
    return Config(tuple(bars), tuple(freight))


_PAD = 72


def legal(model: _Model, cfg: Config) -> bool:
    """No two moving boxes may overlap, and none may enter the immovable furniture."""
    boxes = [b for b, _e in cfg.bars] + list(cfg.freight)
    for n, a in enumerate(boxes):
        if a[0] > a[2] or a[1] > a[3]:
            return False
        for b in boxes[n + 1:]:
            if _overlap(a, b):
                return False
    wall = model.wall
    if wall is None:
        return True
    for y0, x0, y1, x1 in boxes:
        if y1 + _PAD < 0 or x1 + _PAD < 0 or y0 + _PAD >= wall.shape[0] or x0 + _PAD >= wall.shape[1]:
            continue
        if wall[max(0, y0 + _PAD):y1 + _PAD + 1, max(0, x0 + _PAD):x1 + _PAD + 1].any():
            return False
    return True


def rider_at(cfg: Config, bar: int) -> Cell:
    box, edge = cfg.bars[bar]
    unit = far_unit(box, edge)
    return ((unit[0] + unit[2]) // 2, (unit[1] + unit[3]) // 2)


def solved(model: _Model, cfg: Config) -> bool:
    if model.pairing is None:
        return False
    return all(rider_at(cfg, b) == model.places[p] for p, b in model.pairing)


def _reach(model: _Model, cfg: Config, pair: tuple[tuple[int, int], ...]) -> int:
    total = 0
    for place_i, bar in pair:
        here = rider_at(cfg, bar)
        goal = model.places[place_i]
        total += abs(goal[0] - here[0]) + abs(goal[1] - here[1])
    return total


def choose_pairing(model: _Model, cfg: Config) -> bool:
    """Pick which rider is meant for which destination — nearest first, refutable later."""
    if model.pairing is not None:
        return True
    best = None
    for pick in permutations(model.riders, len(model.places)):
        pair = tuple(zip(range(len(model.places)), pick))
        if pair in model.refuted:
            continue
        cost = _reach(model, cfg, pair)
        # ⛔ A pairing claiming the board is already finished is refuted by the board being here.
        if cost == 0:
            continue
        if best is None or cost < best[0]:
            best = (cost, pair)
    if best is None:
        return False
    model.pairing = best[1]
    return True


def plan(model: _Model, start: Config, moves: list[tuple[str, int, int]]) -> list[int] | None:
    """Shortest legal click sequence to a solved board, as indices into `moves`.

    A breadth-first walk, and deliberately so. The reachable configuration space of a handful of
    jointed bars is small — four orientations each and a short length range — so the shortest
    answer is affordable outright, and shortest is exactly what the scoring wants.
    """
    if solved(model, start):
        return []
    seen = {start.key()}
    queue: deque[tuple[Config, list[int]]] = deque([(start, [])])
    opened = 0
    while queue:
        cfg, path = queue.popleft()
        opened += 1
        if opened > _MAX_OPEN or len(path) >= _MAX_PLAN:
            continue
        for n, (kind, colour, step) in enumerate(moves):
            nxt = grow(model, cfg, colour, step) if kind == "grow" else swivel(model, cfg, colour)
            if nxt is None or nxt.key() in seen or not legal(model, nxt):
                continue
            if solved(model, nxt):
                return [*path, n]
            seen.add(nxt.key())
            queue.append((nxt, [*path, n]))
    return None


# --- building the model from the board ----------------------------------------


def _rasterise(cells: set[Cell]) -> Any:
    n = 2 * _PAD + 64
    wall = np.zeros((n, n), dtype=bool)
    for y, x in cells:
        if -_PAD <= y < n - _PAD and -_PAD <= x < n - _PAD:
            wall[y + _PAD, x + _PAD] = True
    return wall


@dataclass
class _Reading:
    """What one frame says: the bars, the freight and the destinations."""

    bars: list[tuple[Box, int]]
    colours: list[int]
    freight: list[Box]
    places: list[Cell]
    solid: set[Cell]
    fixed: set[Cell]


def read_board(g: np.ndarray, widgets: list[Any], marker: int) -> _Reading | None:
    boxes = [w.box for w in widgets]
    pieces = read_pieces(g, marker, boxes)
    found = anchored_bars(g, marker, boxes, pieces)
    if not found:
        return None
    bars = [(sprite_box(pieces[i].box, e), e) for i, e in found]
    owned = {i for i, _e in found}
    stripes = set()
    for (box, _e), (i, _ee) in zip(bars, found):
        for j, p in enumerate(pieces):
            if j in owned or j in stripes:
                continue
            if _overlap(p.box, box):
                stripes.add(j)              # the anchor stripe now lives inside the bar's box
    # ⛔ Only RECTANGLES may be carried. A wall is an L or a frame and its bounding box covers
    # most of the board — measured, one board's two wall blobs came back as boxes spanning
    # (27,3)-(41,8) and (27,18)-(41,59), which makes every configuration illegal. Anything that
    # is not a rectangle is furniture until a probe proves otherwise.
    freight: list[Box] = []
    fixed: set[Cell] = set()
    for j, p in enumerate(pieces):
        if j in owned or j in stripes:
            continue
        if p.rect:
            freight.append(p.box)
        else:
            fixed |= set(p.cells)
    marks = read_markers(g, marker)
    if marks is None:
        return None
    solid, _ = solid_cells(g, marker, boxes)
    return _Reading(bars, [pieces[i].colour for i, _e in found], freight,
                    list(marks.places), solid, fixed)


class SwivelArmTool:
    """Harness tool for jointed-arm boards that TURN as well as telescope."""

    name = "swivel"

    def __init__(self) -> None:
        self._level: int | None = None
        self.reset()

    # -- lifecycle ---------------------------------------------------------

    def reset(self) -> None:
        self._model: _Model | None = None
        self._cfg: Config | None = None
        self._widgets: list[Any] = []
        self._controls: list[tuple[str, Any]] = []     # ("grow"/"turn", widget)
        self._marker: int | None = None
        self._probe = 0
        self._fixed: set[Cell] = set()
        self._chrome: set[Cell] = set()
        self._tries: list[int] = []
        self._moved: dict[int, set[int]] = {}          # control index -> piece indices that moved
        self._driven: dict[int, int] = {}
        self._double: dict[int, bool] = {}
        self._move_ctrl: list[int] = []
        self._pending: tuple[int, int, bool] | None = None
        self._moves: list[tuple[str, int, int]] = []
        self._plan: list[int] = []
        self._dead = False

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Stateless: every transition is read off the frames inside propose()."""

    # -- bidding -----------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        """0.95 for a jointed-arm board that still has a destination to reach, else 0.0.

        ⛔ Requires at least one ONE-WAY control, which is exactly what `telescope` refuses. The
        two tools therefore partition this family instead of competing for it, and a defect in
        the turning model cannot cost the levels the other one already banks.
        """
        if self._dead or not has_frame(obs):
            return 0.0
        simple, action6 = availability(obs)
        if simple or not action6:
            return 0.0
        layers = _layers(obs)
        if not layers:
            return 0.0
        if self._model is not None:
            return 0.95
        g = layers[-1]
        widgets = read_widgets(g)
        if not any(not w.two_way for w in widgets) or not any(w.two_way for w in widgets):
            return 0.0
        colour = marker_colour(g, _widget_colours(g, widgets))
        if colour is None:
            return 0.0
        marks = read_markers(g, colour)
        if marks is None:
            return 0.0
        if len(anchored_bars(g, colour, [w.box for w in widgets])) < len(marks.places):
            return 0.0
        return 0.95

    # -- acting ------------------------------------------------------------

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if self._dead or not has_frame(obs):
            return []
        layers = _layers(obs)
        if not layers:
            return []
        g = layers[-1]
        level = levels_completed(obs)
        if level != self._level:
            self._level = level
            self.reset()
        if self._model is None:
            if not self._begin(g):
                self._dead = True
                return []
        elif self._pending is not None and not self._settle(g, len(layers) > 1):
            self._dead = True
            return []
        return self._next()

    def _begin(self, g: np.ndarray) -> bool:
        self._widgets = read_widgets(g)
        if not self._widgets:
            return False
        self._marker = marker_colour(g, _widget_colours(g, self._widgets))
        if self._marker is None:
            return False
        reading = read_board(g, self._widgets, self._marker)
        if reading is None:
            return False
        self._controls = [("grow" if w.two_way else "turn", w) for w in self._widgets]
        self._tries = [0] * len(self._controls)
        self._cfg = Config(tuple(reading.bars), tuple(reading.freight))
        self._fixed = set(reading.fixed)
        off = np.zeros(g.shape, dtype=bool)
        for y0, x0, y1, x1 in [w.box for w in self._widgets]:
            off[y0:y1 + 1, x0:x1 + 1] = True
        off[-1, :] = True
        self._chrome = {(int(y), int(x)) for y, x in zip(*np.where(off))}
        self._model = _Model(colours=reading.colours,
                             kids=[[] for _ in reading.bars],
                             load=[[] for _ in reading.bars],
                             grow_of={}, turn_of={},
                             parent=[-1] * len(reading.bars),
                             places=reading.places,
                             riders=list(range(len(reading.bars))))
        return True

    # -- probing: one click per control tells us what it carries -----------

    def _settle(self, g: np.ndarray, refused: bool) -> bool:
        """Fold the result of the click just taken into the model."""
        model, cfg = self._model, self._cfg
        assert model is not None and cfg is not None and self._pending is not None
        ctrl, step, learning = self._pending
        self._pending = None
        if refused:
            self._plan = []
            return True
        if learning:
            return self._identify(g, ctrl, step)
        # ⛔ Verify by PREDICTION, never by re-reading the bars. A turn parks bars against each
        # other and the "exactly one anchor" reading then loses them; the model is the truth and
        # the frame only has to agree with it where it can be seen.
        kind, colour, delta = self._moves[ctrl]
        nxt = grow(model, cfg, colour, delta) if kind == "grow" else swivel(model, cfg, colour)
        if nxt is None:
            return False
        self._cfg = nxt
        return self._agrees(g, nxt)

    def _identify(self, g: np.ndarray, ctrl: int, step: int) -> bool:
        """Work out what this control drives by TESTING hypotheses against the frame.

        ⛔ Not by reading the bars again. A turn parks bars against each other and a bar with a
        neighbour at both ends stops satisfying the "exactly one anchor" rule — measured, the
        first turn on this family's sixth board lost the colour-11 bar from the reading entirely
        and the model was thrown away one action in. Since the turn is exact, every candidate
        answer can be SIMULATED and checked against the pixels instead: which bar answered, and
        which of the others it carries. Exactly one hypothesis reproduces the board.
        """
        model, cfg = self._model, self._cfg
        assert model is not None and cfg is not None
        kind = self._controls[ctrl][0]
        seen, marked = solid_cells(g, self._marker or 0, [w.box for w in self._widgets])
        n = len(cfg.bars)
        others = list(range(n))
        winner: tuple[Config, int, set[int]] | None = None
        for driven in range(n):
            rest = [i for i in others if i != driven]
            for mask in range(1 << len(rest)):
              kids = [rest[k] for k in range(len(rest)) if mask >> k & 1]
              # ⛔ A turn can be a DOUBLE turn. The engine turns a bar twice on one click when
              # its parent faces the opposite way, and at probe time the parentage is exactly
              # what is not yet known — so both are offered and the frame picks.
              for times in ((1, 2) if kind == "turn" else (1,)):
                trial = self._simulate(cfg, driven, kids, kind, step, times)
                if trial is None:
                    continue
                # ⛔ Clip to the board BEFORE testing. A turn routinely swings a bar partly
                # off-screen, and comparing unclipped cells against what was rendered rejects
                # the one hypothesis that is exactly right — measured, the correct reading was
                # discarded for predicting nine cells above row zero.
                cells = {c for c in self._cells(trial, keep_freight=False)
                         if 0 <= c[0] < g.shape[0] and 0 <= c[1] < g.shape[1]}
                if not cells <= (seen | marked):
                    continue
                # ⛔ The test must be COLOUR-AWARE. Bars parked end to end make "this bar grew
                # one unit" and "the next bar grew and pushed this one along" occupy exactly the
                # same cells — measured, three different readings of one click all fit the board
                # perfectly and the tool refused rather than choose. Their colours differ, and
                # that is the whole of the evidence needed.
                if not self._colours_fit(g, trial, marked):
                    continue
                free, moved_f = self._fit_freight(cfg, trial, driven, kids, kind, step, seen, marked)
                whole = cells | free | self._fixed
                on = {c for c in whole if 0 <= c[0] < g.shape[0] and 0 <= c[1] < g.shape[1]}
                if seen <= on and (on - seen) <= marked:
                    if winner is not None and winner[1] != driven:
                        return False      # two readings fit; the board has not decided
                    if winner is None:
                        winner = (trial, driven, set(kids) | {n + f for f in moved_f}, times)
        if winner is None:
            return False
        trial, driven, moved, times = winner
        self._cfg = trial
        self._moved[ctrl] = moved | {driven}
        self._driven[ctrl] = driven
        self._double[ctrl] = times == 2
        return True

    def _simulate(self, cfg: Config, driven: int, kids: list[int],
                  kind: str, step: int, times: int = 1) -> Config | None:
        """One action under the hypothesis that `driven` answers and carries `kids`."""
        bars = list(cfg.bars)
        box, edge = bars[driven]
        if kind == "turn":
            for _ in range(times):
                ax, ay = anchor_pivot(bars[driven][0], bars[driven][1])
                for j in kids:
                    bars[j] = (turn_box(bars[j][0], ax, ay), _TURNED_EDGE[bars[j][1]])
                bars[driven] = (turn_box(bars[driven][0], ax, ay),
                                _TURNED_EDGE[bars[driven][1]])
            return Config(tuple(bars), cfg.freight)
        if step < 0 and _length(box, edge) <= _UNIT:
            return None
        y0, x0, y1, x1 = box
        dy = dx = 0
        if edge == 0:
            y0 -= _UNIT * step
            dy = -_UNIT * step
        elif edge == 2:
            y1 += _UNIT * step
            dy = _UNIT * step
        elif edge == 1:
            x0 -= _UNIT * step
            dx = -_UNIT * step
        else:
            x1 += _UNIT * step
            dx = _UNIT * step
        bars[driven] = ((y0, x0, y1, x1), edge)
        for j in kids:
            bars[j] = (_shift(bars[j][0], dy, dx), bars[j][1])
        return Config(tuple(bars), cfg.freight)

    def _fit_freight(self, cfg: Config, trial: Config, driven: int, kids: list[int],
                     kind: str, step: int, seen: set[Cell],
                     marked: set[Cell]) -> tuple[set[Cell], list[int]]:
        """Each carried blocker either came along or stayed; the frame says which, one at a time."""
        out: set[Cell] = set()
        moved: list[int] = []
        box, edge = cfg.bars[driven]
        for f, fb in enumerate(cfg.freight):
            if kind == "turn":
                ax, ay = anchor_pivot(box, edge)
                other = turn_box(fb, ax, ay)
            else:
                dy = dx = 0
                if edge in (0, 2):
                    dy = (-_UNIT if edge == 0 else _UNIT) * step
                else:
                    dx = (-_UNIT if edge == 1 else _UNIT) * step
                other = _shift(fb, dy, dx)
            here = _box_cells(fb)
            there = _box_cells(other)
            if there <= (seen | marked) and not here <= (seen | marked):
                out |= there
                moved.append(f)
                trial.freight[f] if False else None
            else:
                out |= here
        if moved:
            fresh = list(trial.freight)
            for f in moved:
                fb = cfg.freight[f]
                if kind == "turn":
                    ax, ay = anchor_pivot(box, edge)
                    fresh[f] = turn_box(fb, ax, ay)
                else:
                    dy = dx = 0
                    if edge in (0, 2):
                        dy = (-_UNIT if edge == 0 else _UNIT) * step
                    else:
                        dx = (-_UNIT if edge == 1 else _UNIT) * step
                    fresh[f] = _shift(fb, dy, dx)
            object.__setattr__(trial, "freight", tuple(fresh))
        return out, moved

    def _colours_fit(self, g: np.ndarray, cfg: Config, marked: set[Cell]) -> bool:
        """Does every bar's own colour land exactly where this reading says it does?"""
        model = self._model
        assert model is not None
        want: dict[int, set[Cell]] = {}
        for i, (box, edge) in enumerate(cfg.bars):
            cells = {c for c in body_cells(box, edge)
                     if 0 <= c[0] < g.shape[0] and 0 <= c[1] < g.shape[1]}
            want.setdefault(model.colours[i], set()).update(cells)
        for colour, cells in want.items():
            here = {(int(y), int(x)) for y, x in zip(*np.where(g == colour))}
            here -= self._chrome
            if not (cells - marked) <= here or not here <= cells:
                return False
        return True

    def _cells(self, cfg: Config, keep_freight: bool = True) -> set[Cell]:
        out: set[Cell] = set()
        for box, _e in cfg.bars:
            out |= _box_cells(box)
        if keep_freight:
            for box in cfg.freight:
                out |= _box_cells(box)
        return out

    def _agrees(self, g: np.ndarray, cfg: Config) -> bool:
        model = self._model
        assert model is not None
        want: set[Cell] = set()
        for box, _e in cfg.bars:
            want |= {(y, x) for y in range(box[0], box[2] + 1) for x in range(box[1], box[3] + 1)}
        for box in cfg.freight:
            want |= {(y, x) for y in range(box[0], box[2] + 1) for x in range(box[1], box[3] + 1)}
        if model.wall is not None:
            want |= model.static
        boxes = [w.box for w in self._widgets]
        seen, marked = solid_cells(g, self._marker or 0, boxes)
        on = {c for c in want if 0 <= c[0] < g.shape[0] and 0 <= c[1] < g.shape[1]}
        return seen <= on and (on - seen) <= marked

    # -- choosing the next click -------------------------------------------

    def _next(self) -> list[Step]:
        model, cfg = self._model, self._cfg
        assert model is not None and cfg is not None
        while self._probe < len(self._controls):
            ctrl = self._probe
            if ctrl in self._moved or self._tries[ctrl] >= _MAX_TRIES:
                self._probe += 1
                continue
            step = 1 if self._tries[ctrl] == 0 else -1
            self._tries[ctrl] += 1
            self._pending = (ctrl, step, True)
            return [self._click(ctrl, step)]
        if not self._moves and not self._assemble():
            self._dead = True
            return []
        if not self._plan and not self._replan():
            self._dead = True
            return []
        n = self._plan.pop(0)
        kind, _colour, delta = self._moves[n]
        self._pending = (n, delta if kind == "grow" else 0, False)
        return [self._click(self._move_ctrl[n], delta if kind == "grow" else 1)]

    def _click(self, ctrl: int, step: int) -> Step:
        kind, wd = self._controls[ctrl]
        if kind == "turn":
            y, x = (wd.box[0] + wd.box[2]) // 2, (wd.box[1] + wd.box[3]) // 2
        else:
            y, x = wd.plus if step > 0 else wd.minus
        return (6, (x, y))

    # -- turning the probes into a model -----------------------------------

    def _assemble(self) -> bool:
        """Work out from the probes which control drives what, and what carries what.

        ⛔ A control's colour is taken from the bars whose OWN shape answered — the ones that
        changed length, or changed which way they point. Reading it off the widget's artwork
        instead means trusting a palette; reading it off the board means trusting a measurement.
        """
        model, cfg = self._model, self._cfg
        assert model is not None and cfg is not None
        n = len(cfg.bars)
        driven: dict[int, int] = {}
        for ctrl, moved in self._moved.items():
            _ = moved
            driven[ctrl] = self._driven[ctrl]
        if len(driven) != len(self._controls):
            return False
        for ctrl, bar in driven.items():
            subtree = sorted(i for i in self._moved[ctrl] if i < n and i != bar)
            model.kids[bar] = subtree
            model.load[bar] = sorted(i - n for i in self._moved[ctrl] if i >= n)
        for bar in set(driven.values()):
            above = [b for b in set(driven.values()) if b != bar and bar in model.kids[b]]
            if above:
                model.parent[bar] = min(above, key=lambda b: len(model.kids[b]))
        carried = {f for bar in set(driven.values()) for f in model.load[bar]}
        model.static = set(self._fixed)
        for f in range(len(cfg.freight)):
            if f in carried:
                continue
            y0, x0, y1, x1 = cfg.freight[f]
            model.static |= {(y, x) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)}
        model.wall = _rasterise(model.static)
        keep = sorted(carried)
        remap = {f: k for k, f in enumerate(keep)}
        for bar in set(driven.values()):
            model.load[bar] = [remap[f] for f in model.load[bar]]
        self._cfg = Config(cfg.bars, tuple(cfg.freight[f] for f in keep))
        self._moves = []
        self._move_ctrl = []
        for ctrl, (kind, _wd) in enumerate(self._controls):
            colour = model.colours[driven[ctrl]]
            if kind == "grow":
                for step in (1, -1):
                    self._moves.append(("grow", colour, step))
                    self._move_ctrl.append(ctrl)
            else:
                self._moves.append(("turn", colour, 0))
                self._move_ctrl.append(ctrl)
        return True

    def _replan(self) -> bool:
        """Find a click sequence, retiring rider guesses the board has already refuted."""
        model, cfg = self._model, self._cfg
        assert model is not None and cfg is not None
        for _ in range(len(model.riders) + 1):
            if not choose_pairing(model, cfg):
                return False
            if not solved(model, cfg):
                found = plan(model, cfg, self._moves)
                if found:
                    self._plan = found
                    return True
            model.refuted.add(model.pairing or ())
            model.pairing = None
        return False
