"""script25 quarantined adapter: M0R0 (mirror-players merge-maze).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

**STATUS: 2/6 — L0 + L1 cleared by OFFLINE RECONSTRUCTION (R59, 2026-07-16).**
This replaces the R56 online joint-hill-climb (which cleared L0 only and
BANKED L1 as "descent doors not derivable online"). The bank's premise — "the
per-piece wall map is not cleanly frame-separable, players traverse the colour
zones" — was a LIVE-DECODE MISREAD, falsified this round by rendering the real
engine frame and comparing to ground truth: **the full wall map IS
byte-exactly frame-separable** (floor = background colour, walls = the
non-floor zone cells). With the complete maze parsed UP FRONT (not learned
reactively under optimistic passability), an offline joint BFS trivially finds
the merge path the online hill-climb structurally could not.

**Decoded mechanics (verified against environment_files/m0r0/*/m0r0.py ground
truth AND the data/traces/m0r0.npz gold oracle; dev-time only, this file never
reads either at runtime):**

- **Two mirror players** share one colour (10 in both live hashes); the SAME
  action moves BOTH on the same frame. In grid coordinates the control scheme
  is a game CONSTANT: two actions move both players the SAME way along rows
  (row-symmetric), the other two move them in OPPOSITE columns
  (column-antisymmetric). Each side is independently WALL-BLOCKED — a wall
  stops one side while the other moves, which is the ONLY way to break the
  ``left_col + right_col = const`` column invariant (the "desync" the maze
  forces to pass its single-file gaps).
- **Win = the two players MERGE onto the same cell** (engine ``next_level``
  fires when no un-merged player remains). Column parity: an even start gap
  closes exactly; an odd gap closes to adjacency and merges via the engine's
  cross-swap-to-midpoint rule (both modelled below).
- **Walls** = the maze sprite's cells, rendered as the level's zone colours
  (which VARY per level — so walls are detected as "not floor / not player /
  not hazard", never by a fixed colour). A blocked move leaves the side in
  place.
- **Hazards** (``wyiex``, colour 8, checkerboarded over floor) do NOT block —
  a player physically moves ONTO one and that triggers a full soft-reset of
  both players to the level start. So any joint action landing EITHER player
  on a hazard is FORBIDDEN in search (a skipped successor), never modelled as
  a blocked stay.
- HUD noise to ignore: colour-0/background step-counter bars live only in the
  outermost frame ring (rows/cols 0 and 63); the maze is always inset, so the
  parse excludes that ring when bounding the maze.

**Runtime pipeline (per level):**

1. **Measure** the control scheme by probing the 4 move actions once each
   (``kernels.find_regions`` + nearest-match tracking). The scheme is a game
   constant, so it PERSISTS across levels and a blocked probe (reads a
   zero delta) never clobbers a known non-zero one — the R59 bug that made
   ACTION1 look like a no-op after a settle step landed a player on the top
   wall, which silently froze the column invariant and hid every desync path.
2. **Parse** the full maze (floor / wall / hazard grid + the two player cells)
   from the settled frame via a centered-grid solve (offset can EXCEED the
   cell scale, so the offset is derived by player-pixel alignment + content
   bbox, not ``pixel % scale``).
3. **Search** the JOINT ordered state ``(player0_cell, player1_cell)`` with
   :func:`admorphiq.kernels.configuration_path` for the shortest merge path,
   using the measured per-side dynamics + parsed walls (block) + hazards
   (forbid). Identity ordering (which physical player is "player0") is carried
   from the measurement phase and re-matched each frame by nearest.
4. **Execute** the plan while tracking the joint state it PREDICTS after each
   action; a live mismatch (a wall the parse missed, or a wrong identity
   assignment) drops the rest of the plan and re-plans from the observed
   state — closed-loop robustness on top of an offline-computed plan.

If no merge plan is found (e.g. an L3+ variant that adds clickable blocks this
adapter does not model), it degrades to an untried-action explorer, preserving
the L0 floor. GAME_OVER resets the current attempt while keeping every parsed
fact.

Composition from ``admorphiq.kernels``: :func:`find_regions` (player/region
detection) and :func:`configuration_path` (the joint BFS). All pixel
classification is plain-Python iteration over the observation grid.
"""

from __future__ import annotations

from typing import Any

from admorphiq.adapters25.base import (
    GameAction,
    GameAdapter,
    available_action_ids,
    canonical_layer,
    has_frame,
    most_common_color,
    reset_action,
    simple_action,
    state_name,
)
from admorphiq.kernels import configuration_path, find_regions

GAME_ID = "m0r0"

Cell = tuple[int, int]
JointState = tuple[Cell, Cell]

_GIVEUP_DEFAULT = 4000
# wyiex hazard colour (fixed sprite colour across both live hashes; a player
# entering one triggers a soft reset — see module docstring).
_HAZARD_COLOR = 8
# Bound on joint states expanded per merge search. A joint (self x partner)
# space is the product of two positions but each maze is small (<= ~15x15),
# so this comfortably covers a full search.
_MERGE_SEARCH_BUDGET = 200_000
_MOVE_ACTIONS = (1, 2, 3, 4)
# Consecutive decisions with NO merge plan before giving up the whole run (an
# unmodelled level variant). Generous enough that a genuinely long search or a
# transient settle frame never trips it.
_NO_PLAN_GIVEUP = 200


def _manhattan(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _player_blocks(grid: tuple[tuple[int, ...], ...], color: int) -> list[tuple[Cell, int, int]]:
    """``(top_left, height, width)`` of every region of ``color`` (kernels)."""
    out: list[tuple[Cell, int, int]] = []
    for reg in find_regions(grid, background=None):
        if reg["color"] != color:
            continue
        r0, c0, r1, c1 = reg["bbox"]
        out.append(((r0, c0), r1 - r0 + 1, c1 - c0 + 1))
    return out


def _median(vals: list[int]) -> int:
    s = sorted(vals)
    n = len(s)
    if n == 0:
        return 0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) // 2


def _solve_axis(scale: int, player_px: list[int], content_lo: int, content_hi: int) -> tuple[int, int] | None:
    """Centered-grid ``(dim, offset)`` for one axis.

    The tightest centered grid (largest offset, ``offset = (64 - dim*scale)//2``)
    whose offset aligns EVERY player pixel to a cell boundary and whose span
    contains all maze content ``[content_lo, content_hi]``. Needed because the
    true offset can EXCEED ``scale`` (a 13-wide grid at scale 4 has offset 6),
    so ``pixel % scale`` is not the offset.
    """
    best: tuple[int, int] | None = None
    for dim in range(1, 64 // scale + 1):
        off = (64 - dim * scale) // 2
        if off < 0:
            continue
        if not all(0 <= (px - off) < dim * scale and (px - off) % scale == 0 for px in player_px):
            continue
        if off > content_lo or off + dim * scale < content_hi + 1:
            continue
        if best is None or off > best[1]:
            best = (dim, off)
    return best


class _Maze:
    """A parsed level: geometry + wall/hazard sets + the two player cells."""

    __slots__ = ("gh", "gw", "scale", "off_y", "off_x", "walls", "hazards", "players")

    def __init__(self, gh, gw, scale, off_y, off_x, walls, hazards, players):
        self.gh = gh
        self.gw = gw
        self.scale = scale
        self.off_y = off_y
        self.off_x = off_x
        self.walls: set[Cell] = walls
        self.hazards: set[Cell] = hazards
        self.players: list[Cell] = players

    def to_grid(self, px_cell: Cell) -> Cell:
        return ((px_cell[0] - self.off_y) // self.scale, (px_cell[1] - self.off_x) // self.scale)


def _classify_cell(grid, r0: int, c0: int, scale: int, background: int, player_color: int) -> str:
    """One grid cell -> ``"hazard"`` (any colour-8 pixel), ``"floor"`` (a
    background/player pixel and no hazard), or ``"wall"`` (neither)."""
    has_hazard = False
    has_floor = False
    h = len(grid)
    w = len(grid[0]) if h else 0
    for rr in range(r0, min(r0 + scale, h)):
        grow = grid[rr]
        for cc in range(c0, min(c0 + scale, w)):
            val = grow[cc]
            if val == _HAZARD_COLOR:
                has_hazard = True
            elif val == background or val == player_color:
                has_floor = True
    if has_hazard:
        return "hazard"
    return "floor" if has_floor else "wall"


def _parse_maze(grid: tuple[tuple[int, ...], ...], player_color: int) -> _Maze | None:
    """Frame -> ``_Maze`` (floor = background, hazard = colour-8-present cell,
    wall = anything else), or ``None`` when the two players are not resolvable."""
    if not grid:
        return None
    blocks = _player_blocks(grid, player_color)
    if len(blocks) < 2:
        return None
    scale = _median([h for _, h, _ in blocks] + [w for _, _, w in blocks])
    if scale < 1:
        return None
    background = most_common_color(grid)

    # Maze content bbox = floor/player/hazard pixels, excluding the outer HUD
    # ring (rows/cols 0 and 63 carry the step-counter bars in the background
    # colour, which would otherwise inflate the bbox to the frame edge).
    top = left = 64
    bot = right = -1
    h = len(grid)
    w = len(grid[0]) if h else 0
    for r in range(1, min(h, 63)):
        row = grid[r]
        for c in range(1, min(w, 63)):
            v = row[c]
            if v == background or v == player_color or v == _HAZARD_COLOR:
                if r < top:
                    top = r
                if r > bot:
                    bot = r
                if c < left:
                    left = c
                if c > right:
                    right = c
    if bot < 0:
        return None

    prow = [tl[0] for tl, _, _ in blocks]
    pcol = [tl[1] for tl, _, _ in blocks]
    ay = _solve_axis(scale, prow, top, bot)
    ax = _solve_axis(scale, pcol, left, right)
    if ay is None or ax is None:
        return None
    gh, off_y = ay
    gw, off_x = ax

    walls: set[Cell] = set()
    hazards: set[Cell] = set()
    for gy in range(gh):
        for gx in range(gw):
            kind = _classify_cell(grid, off_y + gy * scale, off_x + gx * scale, scale, background, player_color)
            if kind == "hazard":
                hazards.add((gy, gx))
            elif kind == "wall":
                walls.add((gy, gx))

    players = sorted(((tl[0] - off_y) // scale, (tl[1] - off_x) // scale) for tl, _, _ in blocks)
    return _Maze(gh, gw, scale, off_y, off_x, walls, hazards, players)


class Adapter(GameAdapter):
    """Offline-reconstruction merge-maze solver composed from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True
        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        # action_id -> {player_index: (dr, dc)} in GRID units. Persists across
        # levels (the control scheme is a game constant); a blocked probe
        # (zero delta) never overwrites a known non-zero one.
        self._scheme: dict[int, dict[int, Cell]] = {a: {} for a in _MOVE_ACTIONS}
        self._player_color: int | None = None
        # consecutive decisions that produced no merge plan (drives is_done's
        # unmodelled-variant bail); reset on any level-up.
        self._no_plan_streak = 0

        self._reset_level_state()

    def _reset_level_state(self) -> None:
        self._maze: _Maze | None = None
        # the current sorted joint state (index 0/1 aligned with self._scheme)
        self._p0: Cell | None = None
        self._p1: Cell | None = None
        # measurement bookkeeping for the current level
        self._measure_prev: list[Cell] | None = None
        self._measure_action: int | None = None
        self._measure_queue: list[int] = list(_MOVE_ACTIONS)
        self._prev_grid: tuple[tuple[int, ...], ...] | None = None
        self._pending_action: int | None = None
        self._settle_tries = 0
        # the action just issued, used to predict identity across a crossing
        self._last_action: int | None = None

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        # Bail once a level yields NO merge plan for a sustained stretch (an
        # unmodelled variant, e.g. one that adds clickable blocks): the search
        # is deterministic, so a long run of empty plans will not spontaneously
        # recover, and continuing only burns the shared action budget without
        # changing the score. A level that merely needs a long path always
        # returns a (non-empty) plan, so its streak stays at zero.
        return (
            state_name(latest_frame) == "WIN"
            or self._step >= self._giveup
            or self._no_plan_streak >= _NO_PLAN_GIVEUP
        )

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            # A soft reset happened (a player hit a hazard). Keep every parsed
            # fact; only the current attempt's plan/identity is stale.
            self._plan = []
            self._expected = []
            self._p0 = self._p1 = None
            self._pending_action = None
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._pending_action = None
            self._prev_grid = None
            self._levels_seen = -1
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._levels_seen = levels
            self._reset_level_state()

        self._step += 1

        simple_ids, _ = available_action_ids(latest_frame)
        move_ids = [a for a in _MOVE_ACTIONS if a in simple_ids]
        if not move_ids:
            self._prev_grid = grid
            self._pending_action = None
            return simple_action(simple_ids[0]) if simple_ids else reset_action()

        action = self._decide(grid, move_ids)
        self._prev_grid = grid
        self._pending_action = action
        return simple_action(action)

    # ── player colour discovery ─────────────────────────────────────────

    def _discover_player_color(self, before: tuple, after: tuple) -> None:
        """Player colour = the (non-background) colour whose regions shifted
        between ``before`` and ``after`` under the just-issued probe."""
        bg = most_common_color(after)
        before_by_color: dict[int, list[Cell]] = {}
        for reg in find_regions(before, background=None):
            if reg["color"] == bg:
                continue
            before_by_color.setdefault(reg["color"], []).append((reg["bbox"][0], reg["bbox"][1]))
        best: tuple[int, int] | None = None
        for reg in find_regions(after, background=None):
            color = reg["color"]
            if color == bg or color not in before_by_color:
                continue
            here = (reg["bbox"][0], reg["bbox"][1])
            if here not in before_by_color[color]:
                # a region of this colour moved
                count = len(before_by_color[color])
                if best is None or count < best[1]:
                    best = (color, count)
        if best is not None:
            self._player_color = best[0]

    # ── decision ────────────────────────────────────────────────────────

    def _decide(self, grid: tuple, move_ids: list[int]) -> int:
        # Phase A — measure the control scheme (and discover player colour on
        # the very first probe).
        if self._measure_action is not None:
            self._absorb_probe(grid)

        if self._player_color is None:
            # First ever action: issue a probe; discovery happens on absorb.
            self._measure_action = self._measure_queue.pop(0) if self._measure_queue else 1
            self._measure_prev = None
            return self._measure_action

        # (re)parse the maze once the player colour is known.
        if self._maze is None:
            maze = _parse_maze(grid, self._player_color)
            if maze is None or len(maze.players) < 2:
                # level-up transition frame (previous merged block) — settle
                self._settle_tries += 1
                if self._settle_tries > 3:
                    return move_ids[0]
                return move_ids[0]
            self._maze = maze
            self._settle_tries = 0

        # Probe every move action ONCE per level. This both (re)confirms the
        # scheme (blocked probes never clobber a known delta) and — critically
        # — establishes the two players' IDENTITY order at the level start,
        # BEFORE any crossing, by nearest-tracking across the small probes.
        # Identity matters: the mirror control scheme means applying player-0's
        # delta to the wrong physical player flips the column direction, which
        # is exactly why a position-sorted state diverges once the pair crosses.
        if self._measure_queue:
            a = self._measure_queue.pop(0)
            self._measure_prev = list(self._identity_or_sorted(grid))
            self._measure_action = a
            return a
        self._measure_action = None

        # Phase B — closed-loop merge over the ORDERED joint identity state.
        # Re-plan the shortest merge path from the OBSERVED state every
        # decision and take only its first action; BFS is cheap on these small
        # mazes and single-step transitions are exact (byte-exact wall map), so
        # this follows the shortest path with zero open-loop drift and any
        # surprise simply re-routes next frame.
        players = self._current_players(grid)
        if len(players) < 2:
            # merged (or about to win) — idle a legal move; harness WIN check
            # decides.
            self._last_action = None
            return move_ids[0]
        self._assign_identity(players)

        plan = self._search_merge(move_ids)
        if plan:
            self._no_plan_streak = 0
            self._last_action = plan[0]
            return plan[0]
        # No merge plan (unmodelled variant) — gated explorer preserving floor.
        self._no_plan_streak += 1
        self._last_action = None
        return self._explore(move_ids)

    def _identity_or_sorted(self, grid: tuple) -> list[Cell]:
        """The two players in the identity order established SO FAR this level
        (or sorted, before any is established)."""
        players = self._current_players(grid)
        if self._p0 is not None and self._p1 is not None and len(players) == 2:
            self._assign_identity(players)
            return [self._p0, self._p1]
        return players

    def _assign_identity(self, players: list[Cell]) -> None:
        """Map the two observed cells to ordered identities p0/p1. When a prior
        assignment exists, match by the ACTION-PREDICTED positions (robust to a
        column crossing that a plain position-nearest match would mis-handle);
        otherwise bootstrap from sorted order (uncrossed at the level start)."""
        a, b = players[0], players[1]
        if self._p0 is None or self._p1 is None or self._maze is None:
            self._p0, self._p1 = a, b
            return
        pred0, pred1 = self._p0, self._p1
        act = self._last_action
        if act is not None and 0 in self._scheme[act] and 1 in self._scheme[act]:
            pred0 = self._offset(self._p0, self._scheme[act][0], self._maze)
            pred1 = self._offset(self._p1, self._scheme[act][1], self._maze)
        keep = _manhattan(a, pred0) + _manhattan(b, pred1)
        swap = _manhattan(a, pred1) + _manhattan(b, pred0)
        self._p0, self._p1 = (a, b) if keep <= swap else (b, a)

    # ── measurement helpers ─────────────────────────────────────────────

    def _absorb_probe(self, grid: tuple) -> None:
        action = self._measure_action
        self._measure_action = None
        if action is None:
            return
        before = self._prev_grid
        if before is not None and self._player_color is None:
            self._discover_player_color(before, grid)
        if self._player_color is None:
            return
        # Parse the level geometry (same maze in `before` and `grid`) so the
        # very first probe — the one that also discovered the player colour —
        # still records its scheme delta cleanly, measured at the START
        # position (where a move is most likely unblocked) rather than being
        # deferred to the end of the queue.
        if self._maze is None:
            self._maze = _parse_maze(grid, self._player_color)
        prev = self._measure_prev
        if prev is None and before is not None and self._maze is not None:
            prev = self._grid_players(before)
        cur = self._current_players(grid)
        if prev is None or len(prev) < 2 or len(cur) < 2:
            return
        used: set[int] = set()
        matched: list[Cell | None] = [None, None]
        for i, p in enumerate(prev[:2]):
            best: tuple[int, int, Cell] | None = None
            for j, q in enumerate(cur):
                if j in used:
                    continue
                d = _manhattan(p, q)
                if best is None or d < best[0]:
                    best = (d, j, q)
            if best is not None:
                used.add(best[1])
                matched[i] = best[2]
                delta = (best[2][0] - p[0], best[2][1] - p[1])
                if delta != (0, 0):
                    self._scheme[action][i] = delta
        # Carry the identity order (which physical cell is player-0 / player-1)
        # forward from this probe so it is established BEFORE any crossing.
        if matched[0] is not None and matched[1] is not None:
            self._p0, self._p1 = matched[0], matched[1]

    def _grid_players(self, grid: tuple) -> list[Cell]:
        return self._current_players(grid)

    def _scheme_complete(self) -> bool:
        return all(0 in self._scheme[a] and 1 in self._scheme[a] for a in _MOVE_ACTIONS)

    def _current_players(self, grid: tuple) -> list[Cell]:
        """The occupied player GRID CELLS (not region bboxes). Enumerating by
        cell — every player pixel mapped through the maze's scale/offset —
        keeps the two players DISTINCT even when they become adjacent and
        ``find_regions`` connects them into a single region (the R59 bug that
        made an about-to-merge pair look like one player and stalled the
        final crossing move)."""
        if self._player_color is None or self._maze is None:
            return []
        maze = self._maze
        cells: set[Cell] = set()
        for reg in find_regions(grid, background=None):
            if reg["color"] != self._player_color:
                continue
            for r, c in reg["cells"]:
                cells.add(((r - maze.off_y) // maze.scale, (c - maze.off_x) // maze.scale))
        return sorted(cells)

    # ── joint search ────────────────────────────────────────────────────

    def _successors(self, move_ids: list[int]):
        maze = self._maze
        assert maze is not None
        walls = maze.walls
        hazards = maze.hazards
        gh, gw = maze.gh, maze.gw
        scheme = self._scheme
        usable = [a for a in move_ids if 0 in scheme[a] and 1 in scheme[a]]

        def _step(cell: Cell, d: Cell) -> Cell:
            nxt = (cell[0] + d[0], cell[1] + d[1])
            if 0 <= nxt[0] < gh and 0 <= nxt[1] < gw and nxt not in walls:
                return nxt
            return cell

        def successors(state: JointState):
            p0, p1 = state
            for a in usable:
                n0 = _step(p0, scheme[a][0])
                n1 = _step(p1, scheme[a][1])
                if n0 in hazards or n1 in hazards:
                    continue
                # engine cross-swap merge for an odd (adjacent) approach
                if p0[0] == p1[0] and abs(p0[1] - p1[1]) == 1 and ((n0 == p1 and n1 == p0) or n0 == n1):
                    mid = ((p0[0] + p1[0]) // 2, (p0[1] + p1[1]) // 2)
                    yield a, (mid, mid)
                    continue
                ns: JointState = (n0, n1)
                if ns == state:
                    continue
                yield a, ns

        return successors

    def _search_merge(self, move_ids: list[int]) -> list[int] | None:
        if self._maze is None or self._p0 is None or self._p1 is None:
            return None
        start: JointState = (self._p0, self._p1)
        successors = self._successors(move_ids)

        def goal(state: JointState) -> bool:
            return state[0] == state[1]

        path = configuration_path(start, goal, successors, max_states=_MERGE_SEARCH_BUDGET)
        return list(path) if path else None

    def _explore(self, move_ids: list[int]) -> int:
        """Gated fallback: an untried move that most reduces the player gap,
        else the first legal move. Preserves the cleared-level floor when no
        merge plan is available (an unmodelled variant)."""
        if self._maze is None or self._p0 is None or self._p1 is None:
            return move_ids[0]
        scheme = self._scheme
        maze = self._maze
        best_action = move_ids[0]
        best_gap = None
        for a in move_ids:
            if 0 not in scheme[a] or 1 not in scheme[a]:
                return a  # measure an unknown action first
            n0 = self._offset(self._p0, scheme[a][0], maze)
            n1 = self._offset(self._p1, scheme[a][1], maze)
            if n0 in maze.hazards or n1 in maze.hazards:
                continue
            gap = _manhattan(n0, n1)
            if best_gap is None or gap < best_gap:
                best_gap = gap
                best_action = a
        return best_action

    @staticmethod
    def _offset(cell: Cell, d: Cell, maze: _Maze) -> Cell:
        nxt = (cell[0] + d[0], cell[1] + d[1])
        if 0 <= nxt[0] < maze.gh and 0 <= nxt[1] < maze.gw and nxt not in maze.walls:
            return nxt
        return cell
