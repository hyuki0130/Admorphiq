"""Keyed-lock maze: walk an avatar to a lock whose KEY the avatar must first mint.

The family this tool recovers, stated only in what a frame shows:

* the board is a lattice of equal square cells; most are one flat colour (floor or
  wall), and the avatar occupies exactly one and translates one whole cell per action;
* off the board sits an INDICATOR panel — a square block of one colour holding a glyph
  drawn at an integer magnification. That glyph is the key the avatar carries;
* one or more board cells are LOCKS: a flat cell of a third colour holding a glyph of
  the SAME grammar at magnification 1, clear of the cell's border. A lock refuses entry
  — the move is simply not taken — until the indicator glyph equals the lock's glyph,
  same pattern AND same colour, and admits the avatar the instant it does, which is
  what completes the level;
* some floor cells carry a small ICON. Stepping onto one MUTATES the indicator glyph.
  Which component it mutates (turn, recolour, reshape) is not declared and is not
  guessed: the tool steps on one and reads the indicator before and after. What it
  learns is filed under the icon's own pixels, so an icon met again on a later board
  is already understood and costs nothing to re-learn;
* a one-pixel line of a foreign colour lying along a cell edge is a LAUNCHER. Entering
  either cell it separates slides the avatar along its axis. Measured on the sample
  board: the line's side of the cell it bounds gives the direction — a line on a cell's
  LAST column launches +x, on its FIRST column launches -x — and the distance is a pure
  function of the wall map, so a launcher is an ordinary BFS edge, not a hazard.

None of that names a game, a colour, a coordinate or a pitch. Every one of those is
read off a settled frame, or measured with one action.

⛔ Why the key is compared as PIXELS and never decoded into (shape, colour, turn):
decoding needs a shape alphabet, and the alphabet is precisely what another board of
this family is free to change. Pattern equality needs no alphabet. Geometry is used in
exactly one place — asking whether two glyphs are rotations of each other, to tell a
turn that is still owed from a reshape that is — and even there it rotates the bitmap
rather than reading an index.

⛔ Two false-positive traps measured while building this, both of which silently
corrupt routing rather than failing loudly:
  - a lock's own border is a `pitch`-long uniform run along a cell edge and reads as a
    launcher unless launcher colours are required to be colours no cell uses as its
    body. So does the avatar's own two-tone banding, which is why the avatar cell is
    excluded outright.
  - a decorative ring drawn around a lock bleeds one pixel into its neighbours, and a
    floor cell with a stray pixel reads as an icon. Requiring an icon to stand clear of
    its cell's border removes the bleed and keeps every real icon.
"""

from __future__ import annotations

from collections import Counter, deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, connected_components, frame_2d, has_frame
from admorphiq.tools.segment import edge_band

__all__ = ["KeyMazeTool"]

Cell = tuple[int, int]
Pattern = frozenset[tuple[int, int]]

# Lattice steps in (row, col). Which button realises each one is measured, never assumed.
_DIRS: tuple[Cell, ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))

# A lock holds its glyph at magnification 1 inside one cell, so the glyph is small.
_GLYPH_SIDES = (3, 4, 5)

# Buttons are mapped to directions before routing starts; the cap stops a maze that
# happens to wall three of them in from eating a whole life.
_CALIBRATION_CAP = 16

# Joint-search ceiling. The sample board's widest level reaches ~250k states, so this
# is headroom rather than a tuning knob.
_SEARCH_CAP = 600_000

# Actions handed over per turn. The plan is deterministic, so a longer hand-over would
# also be correct — the chunk exists so a mis-modelled icon costs six actions, not fifty.
_PLAN_CHUNK = 6


# ── glyph algebra ───────────────────────────────────────────────────────────────

def _downsample(block: np.ndarray, k: int, off: int) -> tuple[Pattern, int] | None:
    """(lit cells, lit colour) for a `k`x`k` glyph magnified across `block`.

    Every glyph pixel must be a solid s x s square holding either `off` or one single
    other colour. `off` is passed in rather than taken as the commoner colour because a
    glyph is free to light more than half its cells, and guessing there inverts it.
    """
    side = block.shape[0]
    if side != block.shape[1] or side % k or side < k:
        return None
    s = side // k
    lit: set[tuple[int, int]] = set()
    on: int | None = None
    for r in range(k):
        for c in range(k):
            sub = block[r * s:(r + 1) * s, c * s:(c + 1) * s]
            vals = np.unique(sub)
            if vals.size != 1:
                return None
            v = int(vals[0])
            if v == off:
                continue
            if on is None:
                on = v
            elif v != on:
                return None
            lit.add((r, c))
    if on is None or not lit or len(lit) == k * k:
        return None
    return frozenset(lit), on


def _rotate_cw(pattern: Pattern, k: int) -> Pattern:
    """The same bitmap turned a quarter turn clockwise."""
    return frozenset((c, k - 1 - r) for r, c in pattern)


def _turns_between(src: Pattern, dst: Pattern, k: int) -> int | None:
    """How many clockwise quarter turns carry `src` onto `dst` (None if none do)."""
    cur = src
    for n in range(4):
        if cur == dst:
            return n
        cur = _rotate_cw(cur, k)
    return None


def _canonical(pattern: Pattern, k: int) -> tuple[tuple[int, int], ...]:
    """A bitmap's turn-independent identity: the smallest of its four rotations."""
    best = tuple(sorted(pattern))
    cur = pattern
    for _ in range(3):
        cur = _rotate_cw(cur, k)
        best = min(best, tuple(sorted(cur)))
    return best


def _glyph_in(window: np.ndarray, k: int) -> tuple[Pattern, int] | None:
    """The magnified glyph a panel-like block holds, or None.

    The block's commonest colour is the ground; each other colour is tried as the ink,
    and the one whose pixels fill a square whose side is a whole multiple of `k` wins.
    A highlight drawn over the panel adds a colour whose pixels span the whole block,
    which is not a multiple of `k` away from square in practice and so drops out here.
    """
    ground = Counter(int(v) for v in window.ravel()).most_common(1)[0][0]
    for ink in sorted({int(v) for v in np.unique(window)} - {ground}):
        ys, xs = np.where(window == ink)
        y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
        if (y1 - y0) != (x1 - x0) or (y1 - y0 + 1) % k:
            continue
        got = _downsample(window[y0:y1 + 1, x0:x1 + 1], k, ground)
        if got is not None and got[1] == ink:
            return got
    return None


# ── frame reading ───────────────────────────────────────────────────────────────

def _find_indicator(grid: np.ndarray) -> tuple[tuple[int, int, int, int], int] | None:
    """The off-board panel: a square block of one colour holding a magnified glyph.

    Found by its FRAME rather than its contents — a single-colour component whose
    bounding box is square and holds only that colour plus the glyph's — because the
    glyph's colour is exactly the thing the board changes and so cannot be the test.
    """
    best: tuple[tuple[int, int, int, int], int] | None = None
    best_area = 0
    for comp in connected_components(grid, background=-1):
        y0, x0, y1, x1 = comp["bbox"]
        h, w = y1 - y0 + 1, x1 - x0 + 1
        if h != w or h < 2 * _GLYPH_SIDES[0] or comp["size"] < h:
            continue
        window = grid[y0:y1 + 1, x0:x1 + 1]
        # Two colours is the panel at rest; a third appears when the game highlights it,
        # and dropping that case loses the key exactly when it starts to matter.
        if not 2 <= len({int(v) for v in np.unique(window)}) <= 3:
            continue
        for k in _GLYPH_SIDES:
            if _glyph_in(window, k) is not None and h * w > best_area:
                best, best_area = ((y0, x0, y1, x1), k), h * w
                break
    return best


def _lock_glyph(cell: np.ndarray, k: int) -> tuple[Pattern, int] | None:
    """(pattern, colour) held inside a lock cell, or None if the cell holds no glyph.

    The glyph must stand clear of the cell's own border. That one requirement is what
    separates a lock from the avatar, whose colour bands run edge to edge.
    """
    side = cell.shape[0]
    if side < k + 2:
        return None
    body = Counter(int(v) for v in cell.ravel()).most_common(1)[0][0]
    ys, xs = np.where(cell != body)
    if ys.size == 0:
        return None
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    if y0 == 0 or x0 == 0 or y1 == side - 1 or x1 == side - 1:
        return None
    if (y1 - y0) != (x1 - x0) or (y1 - y0 + 1) != k:
        return None
    return _downsample(cell[y0:y1 + 1, x0:x1 + 1], k, body)


def _has_lock_shaped_cell(grid: np.ndarray, k: int) -> bool:
    """Is any `k`x`k` two-colour glyph fully ringed by its own ground colour?

    The detect-time stand-in for the lattice parse, which needs a pitch this tool has
    not measured before its first action.
    """
    h, w = grid.shape
    for y in range(1, h - k):
        for x in range(1, w - k):
            ring = np.concatenate([
                grid[y - 1, x - 1:x + k + 1], grid[y + k, x - 1:x + k + 1],
                grid[y:y + k, x - 1], grid[y:y + k, x + k],
            ])
            vals = np.unique(ring)
            if vals.size != 1:
                continue
            if _downsample(grid[y:y + k, x:x + k], k, int(vals[0])) is not None:
                return True
    return False


class _Board:
    """One frame read as a lattice: who is where, what blocks, what mutates."""

    __slots__ = ("avatar", "walls", "floor_cells", "locks", "icons", "launch", "rows", "cols")

    def __init__(self) -> None:
        self.avatar: Cell | None = None
        self.walls: set[Cell] = set()
        self.floor_cells: set[Cell] = set()
        self.locks: dict[Cell, tuple[Pattern, int]] = {}
        self.icons: dict[Cell, tuple] = {}
        self.launch: dict[Cell, Cell] = {}
        self.rows = 0
        self.cols = 0


class KeyMazeTool:
    """Solve a keyed-lock maze by minting the key the lock asks for, then walking in."""

    name = "keymaze"

    def __init__(self) -> None:
        # Measured once and deliberately kept across levels: re-deriving them per level
        # costs probes out of a budget the later levels do not have.
        self.pitch = 0
        self.origin: Cell = (0, 0)
        self.floor: int | None = None
        self.wall_colours: set[int] = set()
        self.dirs: dict[int, Cell] = {}
        self.panel: tuple[int, int, int, int] | None = None
        self.glyph_k = 0
        self.bar_colour: int | None = None
        self.full_units = 0
        # Icon semantics filed under the icon's own pixels, so a board that reuses one
        # is already understood: "turn" | "recolour" | "reshape" | "refill" | "inert".
        self.icon_kind: dict[tuple, str] = {}
        self.colour_map: dict[tuple[tuple, int], int] = {}
        self.shape_map: dict[tuple[tuple, Pattern], Pattern] = {}
        self.calibration_spent = 0
        self.reset()

    # -- lifecycle -------------------------------------------------------------

    def reset(self) -> None:
        self._prev: np.ndarray | None = None
        self._prev_action = 0
        self._prev_count = 0
        self._probe_order: list[int] = []
        self._idle = 0
        self._seen_icons: dict[Cell, tuple] = {}
        # Per-level, and deliberately NOT kept: the budget drains at a rate the level
        # sets, and carrying a cheaper level's rate into a dearer one plans twice the
        # budget that exists and walks the avatar to a certain death.
        self.unit_cost = 0

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """No-op: every transition this tool learns from is read in `propose`.

        Learning here would see the frame BEFORE the action and never the one after,
        and the one after is the half that carries the answer.
        """

    # -- detection -------------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        if not has_frame(obs):
            return 0.0
        simple, click = availability(obs)
        # Four directions and nothing else. Bidding on a board with a click is how a
        # tool steals a turn from the one that could actually solve it.
        if click or sorted(simple) != [1, 2, 3, 4]:
            return 0.0
        grid = frame_2d(obs)
        found = _find_indicator(grid)
        if found is None:
            return 0.0
        return 0.9 if _has_lock_shaped_cell(grid, found[1]) else 0.0

    # -- turn ------------------------------------------------------------------

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        grid = frame_2d(obs)
        self._learn(grid)
        plan = self._choose(grid)
        self._prev = grid.copy()
        self._prev_action = plan[0] if plan else 0
        self._prev_count = len(plan)
        return [(a, None) for a in plan]

    def _choose(self, grid: np.ndarray) -> list[int]:
        if self.pitch == 0 or (len(self.dirs) < 4 and self.calibration_spent < _CALIBRATION_CAP):
            probe = self._probe_button()
            if probe:
                self.calibration_spent += 1
                return [probe]
        board = self._parse(grid)
        if board is None or board.avatar is None or not board.locks:
            # Two measured stale frames: a life-loss flash blanks the board for one
            # action, and the frame handed back on a level-up still shows the board just
            # finished (its lock already consumed, hence the empty-lock test). One blind
            # step rides either out; a board that never comes back is not ours to play.
            self._idle += 1
            return [self._any_action()] if self._idle <= 2 else []
        self._idle = 0
        token = self._read_token(grid)
        if token is None:
            return []
        plan = self._plan(board, token, grid)
        # Until the drain rate has been measured the search is planning against a budget
        # it has invented, so only its first action is trusted — that action measures it.
        if self.unit_cost == 0:
            return plan[:1]
        return self._truncate(board, plan)[:_PLAN_CHUNK]

    def _truncate(self, b: _Board, plan: list[int]) -> list[int]:
        """End the hand-over on the first icon the plan steps onto.

        What an icon does is read by comparing the key across the handed-over chunk, so
        a chunk holding two icons would attribute both effects to one of them. Ending on
        the first keeps every reading exact without costing an action.
        """
        cell = b.avatar
        for i, action in enumerate(plan):
            d = self.dirs.get(action)
            if d is None or cell is None:
                return plan[:i]
            land = (cell[0] + d[0], cell[1] + d[1])
            if land in b.locks:
                return plan[:i + 1]
            slide = b.launch.get(land)
            cell = (land[0] + slide[0], land[1] + slide[1]) if slide else land
            if cell in b.icons:
                return plan[:i + 1]
        return plan

    def _probe_button(self) -> int:
        """A button whose direction is not yet known, cycling so a walled one is retried."""
        unknown = [a for a in (1, 2, 3, 4) if a not in self.dirs]
        if not unknown:
            return 0
        self._probe_order = [a for a in self._probe_order if a in unknown] or list(unknown)
        return self._probe_order.pop(0)

    def _any_action(self) -> int:
        return next(iter(self.dirs), 1)

    # -- learning --------------------------------------------------------------

    def _learn(self, grid: np.ndarray) -> None:
        """Read the transition the action proposed last turn actually produced."""
        prev, action, count = self._prev, self._prev_action, self._prev_count
        self._prev = None
        if prev is None or action == 0 or prev.shape != grid.shape:
            return
        self._learn_bar(prev, grid, count)
        if self.pitch == 0:
            self._learn_lattice(prev, grid, action)
            return
        before, after = self._parse(prev), self._parse(grid)
        if before is None or after is None or before.avatar is None or after.avatar is None:
            return
        moved = (after.avatar[0] - before.avatar[0], after.avatar[1] - before.avatar[1])
        if action not in self.dirs and moved in _DIRS:
            self.dirs[action] = moved
        icon = before.icons.get(after.avatar)
        if icon is not None and after.avatar != before.avatar:
            self._learn_icon(icon, prev, grid)

    def _learn_lattice(self, prev: np.ndarray, grid: np.ndarray, action: int) -> None:
        """One successful move declares the cell size, the floor colour and the avatar.

        The move leaves two squares changed: the one it vacated, now flat floor, and the
        one it entered, which is not flat. That asymmetry names the floor and the
        direction without either being assumed.
        """
        mask = (prev != grid) & ~edge_band(grid.shape)
        if not mask.any():
            return
        comps = connected_components(np.where(mask, 1, 0), background=0)
        if not comps:
            return
        y0, x0, y1, x1 = max(comps, key=lambda c: c["size"])["bbox"]
        h, w = y1 - y0 + 1, x1 - x0 + 1
        if h == 2 * w:
            p, halves = w, [(y0, x0), (y0 + w, x0)]
        elif w == 2 * h:
            p, halves = h, [(y0, x0), (y0, x0 + h)]
        else:
            return
        flat = [np.unique(grid[y:y + p, x:x + p]).size == 1 for y, x in halves]
        if flat.count(True) != 1:
            return
        vacated, entered = halves[flat.index(True)], halves[1 - flat.index(True)]
        self.pitch = p
        self.floor = int(grid[vacated[0], vacated[1]])
        self.origin = (entered[0] % p, entered[1] % p)
        self.dirs[action] = ((entered[0] - vacated[0]) // p, (entered[1] - vacated[1]) // p)

    def _learn_bar(self, prev: np.ndarray, grid: np.ndarray, count: int) -> None:
        """The budget bar, and what an action costs it.

        The bar is the edge-pinned colour that shrinks; floor and wall colours are
        excluded because the avatar crossing a cell that reaches into the band shrinks
        those too, and the largest survivor is taken because the bar is the band's bulk.
        """
        was, now = self._band_counts(prev), self._band_counts(grid)
        if self.bar_colour is None:
            skip = {self.floor} | self.wall_colours
            shrunk = [c for c in was if c not in skip and 0 < now.get(c, 0) < was[c]]
            if not shrunk:
                return
            self.bar_colour = max(shrunk, key=lambda c: was[c])
        self.full_units = max(self.full_units, now.get(self.bar_colour, 0))
        drop = was.get(self.bar_colour, 0) - now.get(self.bar_colour, 0)
        # A refill or a level change moves the bar the other way and says nothing about
        # the rate; an uneven drop means the chunk was not all plain moves.
        if count > 0 and drop > 0 and drop % count == 0:
            self.unit_cost = drop // count

    def _band_counts(self, grid: np.ndarray) -> Counter:
        band = edge_band(grid.shape)
        return Counter(int(v) for v in grid[band])

    def _bar(self, grid: np.ndarray) -> int:
        if self.bar_colour is None:
            return 0
        return self._band_counts(grid).get(self.bar_colour, 0)

    def _learn_icon(self, icon: tuple, prev: np.ndarray, grid: np.ndarray) -> None:
        """Name an icon by what stepping on it did to the key (or to the budget bar)."""
        # ⛔ Every sighting is recorded, not just the first. An earlier version returned
        # early once an icon had a name, which froze its recolour cycle at the single
        # step first seen; the search then believed one colour was all it could reach and
        # bounced on that icon until the budget ran out, forever.
        was, now = self._read_token(prev), self._read_token(grid)
        if was is None or now is None:
            return
        if was == now:
            # Every plain action spends the bar, so a step that did NOT spend it topped
            # it up. Testing for growth alone would miss a refill taken while full.
            refilled = self._bar(grid) >= self._bar(prev)
            self.icon_kind[icon] = "refill" if refilled else self.icon_kind.get(icon, "inert")
            return
        (was_pat, was_col), (now_pat, now_col) = was, now
        k = self.glyph_k
        if was_col != now_col and was_pat == now_pat:
            self.icon_kind[icon] = "recolour"
            self.colour_map[(icon, was_col)] = now_col
        elif was_col == now_col and _turns_between(was_pat, now_pat, k) is not None:
            self.icon_kind[icon] = "turn"
        else:
            self.icon_kind[icon] = "reshape"
            # A reshape leaves the key's ORIENTATION alone, so one sighting settles the
            # same mutation under all four turns of it. Recording them together is what
            # keeps a board with both a reshape and a turn icon from needing every
            # combination visited.
            was_r, now_r = was_pat, now_pat
            for _ in range(4):
                self.shape_map[(icon, was_r)] = now_r
                was_r, now_r = _rotate_cw(was_r, k), _rotate_cw(now_r, k)

    # -- perception ------------------------------------------------------------

    def _read_token(self, grid: np.ndarray) -> tuple[Pattern, int] | None:
        if self.panel is None:
            found = _find_indicator(grid)
            if found is None:
                return None
            self.panel, self.glyph_k = found
        y0, x0, y1, x1 = self.panel
        return _glyph_in(grid[y0:y1 + 1, x0:x1 + 1], self.glyph_k)

    def _parse(self, grid: np.ndarray) -> _Board | None:
        """Cut the frame into lattice cells and give each one a role."""
        if self.pitch == 0 or self.floor is None:
            return None
        if self.panel is None and self._read_token(grid) is None:
            return None
        p, (oy, ox) = self.pitch, self.origin
        b = _Board()
        b.rows, b.cols = (grid.shape[0] - oy) // p, (grid.shape[1] - ox) // p
        py0, px0, py1, px1 = self.panel if self.panel else (-1, -1, -2, -2)
        blocks: dict[Cell, np.ndarray] = {}
        bodies: dict[Cell, int] = {}
        for r in range(b.rows):
            for c in range(b.cols):
                y, x = oy + r * p, ox + c * p
                if not (y + p <= py0 or y > py1 or x + p <= px0 or x > px1):
                    b.walls.add((r, c))  # occluded by the panel: never route through it
                    continue
                blk = grid[y:y + p, x:x + p]
                blocks[(r, c)] = blk
                bodies[(r, c)] = Counter(int(v) for v in blk.ravel()).most_common(1)[0][0]
        self.wall_colours |= {
            bodies[cell] for cell, blk in blocks.items()
            if np.unique(blk).size == 1 and bodies[cell] != self.floor
        }
        for cell, blk in blocks.items():
            body = bodies[cell]
            flat = np.unique(blk).size == 1
            if body == self.floor:
                b.floor_cells.add(cell)
                if not flat and self._icon_stands_clear(blk):
                    b.icons[cell] = self._icon_key(blk)
                continue
            if body in self.wall_colours:
                b.walls.add(cell)
                continue
            glyph = _lock_glyph(blk, self.glyph_k)
            if glyph is not None:
                b.locks[cell] = glyph
                continue
            if b.avatar is None:
                b.avatar = cell
                b.floor_cells.add(cell)
            else:
                b.walls.add(cell)
        self._recall_icons(b, blocks)
        b.launch = self._launchers(grid, b, bodies)
        return b

    def _recall_icons(self, b: _Board, blocks: dict[Cell, np.ndarray]) -> None:
        """Put back the icon the avatar is standing on.

        ⛔ Measured: an avatar parked on an icon HIDES it, the search then sees no way to
        trigger it a second time, and a level needing three triggers of one icon stalls
        one trigger in with a plan that reads as impossible. Only the cell under the
        avatar is recalled — every other cell is trusted as seen, so a refill that has
        been spent stays gone.
        """
        for cell in blocks:
            if cell in b.icons:
                self._seen_icons[cell] = b.icons[cell]
            elif cell != b.avatar:
                self._seen_icons.pop(cell, None)
        if b.avatar in self._seen_icons:
            b.icons[b.avatar] = self._seen_icons[b.avatar]

    def _icon_stands_clear(self, block: np.ndarray) -> bool:
        """Does the decoration avoid the cell's border? Border ink is a neighbour's bleed."""
        ys, xs = np.where(block != self.floor)
        side = block.shape[0]
        return bool(ys.size) and 0 not in ys and 0 not in xs \
            and side - 1 not in ys and side - 1 not in xs

    def _icon_key(self, block: np.ndarray) -> tuple:
        """An icon's identity: its non-floor pixels, positions and colours."""
        ys, xs = np.where(block != self.floor)
        return tuple(sorted((int(y), int(x), int(block[y, x])) for y, x in zip(ys, xs)))

    def _launchers(self, grid: np.ndarray, b: _Board, bodies: dict[Cell, int]) -> dict[Cell, Cell]:
        """Trigger cell -> the displacement an entering avatar is slid by.

        A launcher is a `pitch`-long, one-pixel-thin run lying exactly along a cell edge
        in a colour NO cell uses as its body — the requirement that keeps a lock's own
        border and the avatar's colour banding from reading as launchers.
        """
        p, (oy, ox) = self.pitch, self.origin
        native = set(bodies.values()) | {self.floor} | self.wall_colours
        blocked = b.walls | set(b.locks)
        out: dict[Cell, Cell] = {}
        for cell, body in bodies.items():
            if cell == b.avatar or cell in b.locks:
                continue
            r, c = cell
            y, x = oy + r * p, ox + c * p
            edges = (
                ((-1, 0), grid[y, x:x + p]),
                ((1, 0), grid[y + p - 1, x:x + p]),
                ((0, -1), grid[y:y + p, x]),
                ((0, 1), grid[y:y + p, x + p - 1]),
            )
            for d, line in edges:
                vals = np.unique(line)
                if vals.size != 1 or int(vals[0]) in native or int(vals[0]) == body:
                    continue
                far = (r + d[0], c + d[1])
                if far in blocked or not (0 <= far[0] < b.rows and 0 <= far[1] < b.cols):
                    continue
                reach = 0
                probe = (far[0] + d[0], far[1] + d[1])
                while (0 <= probe[0] < b.rows and 0 <= probe[1] < b.cols
                       and probe not in blocked):
                    reach += 1
                    probe = (probe[0] + d[0], probe[1] + d[1])
                if reach:
                    out[cell] = out[far] = (d[0] * reach, d[1] * reach)
        return out

    # -- routing ---------------------------------------------------------------

    def _mutate(self, sig: tuple, token: tuple[Pattern, int]) -> tuple[Pattern, int] | None:
        """The key an icon of kind `sig` yields, or None if that is not yet measured."""
        pattern, colour = token
        kind = self.icon_kind.get(sig)
        if kind == "inert":
            return token
        if kind == "turn":
            # A turn is the one mutation that generalises from a single sighting: the
            # bitmap itself carries the answer, so no further visit is ever needed.
            return _rotate_cw(pattern, self.glyph_k), colour
        if kind == "recolour":
            nxt = self.colour_map.get((sig, colour))
            return None if nxt is None else (pattern, nxt)
        if kind == "reshape":
            nxt = self.shape_map.get((sig, pattern))
            return None if nxt is None else (nxt, colour)
        return None

    def _plan(self, b: _Board, token: tuple[Pattern, int], grid: np.ndarray) -> list[int]:
        """Shortest action list that opens a lock — or, failing that, that measures the
        one unmeasured icon effect standing between here and a plan.

        Search state is (cell, key, budget left, refills spent). The budget belongs in
        the state and not in a post-hoc check because the sample board's second level is
        NOT solvable inside one budget: the route has to be chained through refills, and
        a planner that only checks affordability after choosing a target strands itself
        at the far end of the maze with four units left. Every edge costs one action, so
        plain breadth-first order is optimal in the quantity the score is made of.
        """
        plan = self._search(b, token, grid, self.unit_cost)
        if plan:
            return plan
        # Nothing is reachable on what is left. Walking on anyway spends the budget and
        # costs a life — and a life restarts the board with its refills RESTORED while
        # everything measured about the icons is kept, which is exactly the trade a board
        # whose refills had to be spent on reconnaissance needs. Measured: the sample
        # board's second level is unsolvable after its first refill is spent learning
        # what a refill is, and solvable in 45 actions on the life after.
        return self._search(b, token, grid, 0)

    def _search(self, b: _Board, token: tuple[Pattern, int], grid: np.ndarray,
                cost: int) -> list[int]:
        by_dir = {d: a for a, d in self.dirs.items()}
        if len(by_dir) < len(_DIRS) or b.avatar is None:
            return []
        units = self._bar(grid)
        full = max(self.full_units, units)
        start = (b.avatar, token, units, ())
        seen = {start}
        queue: deque[tuple[tuple, list[int]]] = deque([(start, [])])
        explore: list[int] | None = None
        while queue and len(seen) < _SEARCH_CAP:
            (cell, key, left, spent), path = queue.popleft()
            for d, action in by_dir.items():
                land = (cell[0] + d[0], cell[1] + d[1])
                if not (0 <= land[0] < b.rows and 0 <= land[1] < b.cols):
                    continue
                budget = left - cost
                if cost and budget < 0:
                    continue
                if land in b.locks:
                    # A lock refuses a wrong key rather than punishing it, so a mismatch
                    # is simply not an edge.
                    if b.locks[land] == key:
                        return path + [action]
                    continue
                if land not in b.floor_cells:
                    continue
                slide = b.launch.get(land)
                if slide is not None:
                    land = (land[0] + slide[0], land[1] + slide[1])
                    if land not in b.floor_cells:
                        continue
                sig = b.icons.get(land)
                nxt_key, nxt_spent = key, spent
                if sig is not None and land not in spent:
                    if self.icon_kind.get(sig) == "refill":
                        budget, nxt_spent = full, tuple(sorted(set(spent) | {land}))
                    else:
                        nxt_key = self._mutate(sig, key)
                        if nxt_key is None:
                            if explore is None:
                                explore = path + [action]
                            continue
                state = (land, nxt_key, budget, nxt_spent)
                if state in seen:
                    continue
                seen.add(state)
                queue.append((state, path + [action]))
        return explore or []
