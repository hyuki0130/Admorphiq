"""script25 quarantined adapter: M0R0 (mirror-players merge-maze).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

**STATUS: 5/6 — L0/L1 OFFLINE RECONSTRUCTION + L3 MOVABLE-BLOCK CLEARING + L4
CONSTRUCTIVE BLOCK PLACEMENT + L5 MOMENTARY PRESSURE-PLATE GATES (R59,
2026-07-16). All five cleared levels score 1.000 (super-human).**

L5 adds `dfnuk`/`hnutp` gate groups: each group has a 1-cell PLATE and a 3-cell
conditional WALL; the wall is passable IFF a player stands on a plate of that
group, recomputed every step (MOMENTARY). The gate state is a pure function of
the players' positions, so the joint BFS node stays ``(p0, p1)`` and
``_successors`` computes the closed gate walls per node. Gate cells are detected
as colours that are NOT floor/player/block/hazard and NOT one of the two
dominant ZONE colours — so a level whose zone colour is 12/14/15 (L1-L4) never
mis-reads its static walls as gates.

cvcer movable blocks (colour 9) are used two opposite ways, both gated on
colour-9 detection so the L0/L1 path is untouched:
- **L3 — block as OBSTACLE to clear:** parse blocks as a third cell class,
  compute the blocks-as-floor merge trajectory, ACTION6-select each block on it
  and route it (``kernels.grid_shortest_path`` + ``path_to_moves``) to an
  off-path parking cell, then run the cleared-board merge.
- **L4 — block as a CONSTRUCTIVE DESYNC TOOL:** when NO merge exists even with
  the block gone (blocks-as-floor = None), the pair spawns at ASYMMETRIC rows
  and the row-gap can only close by wall-blocking one mirror side mid-move —
  so the block is MOVED ONTO a cell where, as a wall, it enables the merge
  (``_build_place_plan``: search the block's reachable cells for one whose
  placement makes ``_search_merge`` feasible), then the closed-loop merge runs.
The live engine is the oracle (no L3+ gold trace exists). Subtle unlocks: floor
is the FIXED colour 5 (never ``most_common_colour`` — a wall-heavy zone can
out-count it); per-level scheme probes are SKIPPED once the scheme is complete
(they desync the players pre-merge); and a SELECTED block is blocked by BOTH
walls AND hazards (unlike a player, so block routing avoids both). The
placement search is position-relative, so it finds an enabling cell for
whatever settled spawn the players are at.
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
    click_action,
    has_frame,
    most_common_color,
    reset_action,
    simple_action,
    state_name,
)
from admorphiq.kernels import configuration_path, find_regions, grid_shortest_path, path_to_moves

GAME_ID = "m0r0"

Cell = tuple[int, int]
JointState = tuple[Cell, Cell]

_GIVEUP_DEFAULT = 4000
# wyiex hazard colour (fixed sprite colour across both live hashes; a player
# entering one triggers a soft reset — see module docstring). A wyiex cell
# renders as a CHECKERBOARD of colour 8 over the floor colour, which
# distinguishes it from a SOLID colour-8 zone WALL (some levels' wall zone is
# also colour 8 — see _classify_cell).
_HAZARD_COLOR = 8
# cvcer movable-block colour (a selectable obstacle that blocks players like a
# wall until relocated) and the colour it remaps to WHILE selected. See the
# "L3 movable blocks" section of the module docstring.
_BLOCK_COLOR = 9
_SELECTED_COLOR = 11
# The maze FLOOR colour — the engine's fixed Camera background (5) on every
# level and hash. NOT derived via most-common-colour: a wall-heavy level's zone
# colour can out-count the floor (e.g. L3's colour-15 zone), which would then
# be mistaken for the background and every floor cell mis-read as a wall.
_FLOOR_COLOR = 5
# Canonical block-move scheme in grid (row, col): the SELECTED block moves in
# raw grid directions (ACTION1 up / 2 down / 3 left / 4 right), verified live
# on both hashes. Unlike the mirror players, a block is a single unmirrored
# mover, so this is a fixed game constant, not a per-side measurement.
_BLOCK_MOVE_LABELS: dict[Cell, int] = {(-1, 0): 1, (1, 0): 2, (0, -1): 3, (0, 1): 4}
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
    """A parsed level: geometry + wall/hazard/block sets + the two player cells,
    plus the pressure-plate gate groups (L5)."""

    __slots__ = ("gh", "gw", "scale", "off_y", "off_x", "walls", "hazards",
                 "players", "blocks", "plates", "gate_walls")

    def __init__(self, gh, gw, scale, off_y, off_x, walls, hazards, players, blocks,
                 plates=None, gate_walls=None):
        self.gh = gh
        self.gw = gw
        self.scale = scale
        self.off_y = off_y
        self.off_x = off_x
        self.walls: set[Cell] = walls
        self.hazards: set[Cell] = hazards
        self.players: list[Cell] = players
        self.blocks: set[Cell] = blocks  # cvcer movable obstacle cells
        # Pressure-plate gates (dfnuk/hnutp), keyed by group colour: a player on
        # any plate of a group makes that group's conditional walls passable
        # (momentary — recomputed every step from the players' positions).
        self.plates: dict[int, set[Cell]] = plates or {}
        self.gate_walls: dict[int, set[Cell]] = gate_walls or {}

    def to_grid(self, px_cell: Cell) -> Cell:
        return ((px_cell[0] - self.off_y) // self.scale, (px_cell[1] - self.off_x) // self.scale)

    def pixel_center(self, cell: Cell) -> Cell:
        """Display pixel (x, y) at the centre of a grid cell — for ACTION6 clicks."""
        return (self.off_x + cell[1] * self.scale + self.scale // 2,
                self.off_y + cell[0] * self.scale + self.scale // 2)


def _classify_cell(grid, r0: int, c0: int, scale: int, background: int, player_color: int) -> str:
    """One grid cell -> ``"block"`` / ``"hazard"`` / ``"wall"`` / ``"floor"``.

    - a cvcer movable block (colour 9 present) → ``"block"`` (it obstructs like
      a wall until relocated);
    - a wyiex hazard renders as a CHECKERBOARD of colour 8 over the floor, so a
      cell with BOTH colour 8 and the floor colour → ``"hazard"``;
    - SOLID colour 8 (no floor pixel) is a zone WALL, not a hazard — some
      levels' wall zone is colour 8 (e.g. L3 ``npwxa=[15,8]``), which would be
      mass-mis-read as hazards without the checkerboard test;
    - background/player pixels (and nothing else) → ``"floor"``; everything
      else (other solid zone colours) → ``"wall"``.
    """
    has8 = has_floor = has_block = False
    h = len(grid)
    w = len(grid[0]) if h else 0
    for rr in range(r0, min(r0 + scale, h)):
        grow = grid[rr]
        for cc in range(c0, min(c0 + scale, w)):
            val = grow[cc]
            if val == _BLOCK_COLOR:
                has_block = True
            elif val == _HAZARD_COLOR:
                has8 = True
            elif val == background or val == player_color:
                has_floor = True
    if has_block:
        return "block"
    if has8 and has_floor:
        return "hazard"
    if has8:
        return "wall"
    return "floor" if has_floor else "wall"


def _detect_gates(
    grid, off_y: int, off_x: int, scale: int, gh: int, gw: int, background: int, player_color: int
) -> tuple[dict[int, set[Cell]], dict[int, set[Cell]]]:
    """Pressure-plate gate groups (L5's ``dfnuk``/``hnutp``) as
    ``(plates, gate_walls)``, each keyed by group colour.

    A gate colour is any colour that is NOT floor / player / block / hazard and
    NOT one of the two dominant ZONE colours (the maze-wall fill, which is the
    top-2 most-frequent non-floor/non-player colours). This is what stops a
    level whose zone colour happens to be 12/14/15 (L1-L4) from mis-reading its
    static walls as gates — there the gate colour IS the zone colour, so it is
    excluded. Within a gate colour, a single-cell region is a PLATE
    (``hnutp``), a multi-cell region a conditional WALL (``dfnuk``).
    """
    # Pixel counts per colour, to find the two zone (maze-wall) colours.
    counts: dict[int, int] = {}
    for r in range(off_y, min(off_y + gh * scale, len(grid))):
        row = grid[r]
        for c in range(off_x, min(off_x + gw * scale, len(row))):
            v = row[c]
            if v == background or v == player_color:
                continue
            counts[v] = counts.get(v, 0) + 1
    zone = {c for c, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:2]}
    excluded = {background, player_color, _BLOCK_COLOR, _HAZARD_COLOR} | zone

    plates: dict[int, set[Cell]] = {}
    gate_walls: dict[int, set[Cell]] = {}
    for reg in find_regions(grid, background=None):
        color = reg["color"]
        if color in excluded:
            continue
        cells = {((r - off_y) // scale, (c - off_x) // scale) for r, c in reg["cells"]}
        cells = {(gy, gx) for gy, gx in cells if 0 <= gy < gh and 0 <= gx < gw}
        if not cells:
            continue
        if len(cells) == 1:
            plates.setdefault(color, set()).update(cells)
        else:
            gate_walls.setdefault(color, set()).update(cells)
    return plates, gate_walls


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
    background = _FLOOR_COLOR

    # Maze content bbox = FLOOR (background) + player pixels ONLY, excluding the
    # outer HUD ring (rows/cols 0 and 63 carry step-counter bars). Colour 8 is
    # deliberately NOT used to bound the maze: a colour-8 wall zone bleeds into
    # the letterbox PADDING (which is zone-filled), which would inflate the bbox
    # to the frame edge and break the centered-grid solve. The floor colour only
    # ever appears INSIDE the maze, so it bounds it cleanly (hazard cells still
    # contain floor pixels under their checkerboard, so they are included too).
    top = left = 64
    bot = right = -1
    h = len(grid)
    w = len(grid[0]) if h else 0
    for r in range(1, min(h, 63)):
        row = grid[r]
        for c in range(1, min(w, 63)):
            v = row[c]
            if v == background or v == player_color:
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
    movable: set[Cell] = set()
    for gy in range(gh):
        for gx in range(gw):
            kind = _classify_cell(grid, off_y + gy * scale, off_x + gx * scale, scale, background, player_color)
            if kind == "hazard":
                hazards.add((gy, gx))
            elif kind == "wall":
                walls.add((gy, gx))
            elif kind == "block":
                movable.add((gy, gx))

    players = sorted(((tl[0] - off_y) // scale, (tl[1] - off_x) // scale) for tl, _, _ in blocks)

    # Pressure-plate gates (L5): the classify loop above marked the gate cells
    # as static walls (they are non-floor); reclassify them out of `walls` and
    # into the gate groups. Plates are walkable floor; conditional walls block
    # only while their group is closed (handled in _successors).
    plates, gate_walls = _detect_gates(grid, off_y, off_x, scale, gh, gw, background, player_color)
    for cells in plates.values():
        walls -= cells
    for cells in gate_walls.values():
        walls -= cells
    return _Maze(gh, gw, scale, off_y, off_x, walls, hazards, players, movable, plates, gate_walls)


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
        # the action just issued, used to read identity from the OBSERVED
        # motion on the next frame (which player moved by scheme[a][0] is p0).
        self._last_action: int | None = None
        # the players' positions BEFORE the last action, to measure that motion.
        self._prev_merge_players: list[Cell] | None = None
        # queued block-clearing action SPECS — ("click", x, y) or ("move", id)
        # — built once per level from the parsed board and turned into a fresh
        # GameAction at drain time (ACTION6 is a mutable singleton, so a
        # pre-built click would be clobbered by the next one). None = not built.
        self._clear_plan: list[tuple] | None = None

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
        return action

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
            return simple_action(self._measure_action)

        # (re)parse the maze once the player colour is known.
        if self._maze is None:
            maze = _parse_maze(grid, self._player_color)
            if maze is None or len(maze.players) < 2:
                # level-up transition frame (previous merged block) — settle
                self._settle_tries += 1
                return simple_action(move_ids[0])
            self._maze = maze
            self._settle_tries = 0

        # Probe the move actions to learn the control scheme — but ONLY until it
        # is complete. It is a game constant, so once L0 has measured it, later
        # levels skip probing entirely: the probes MOVE the players, and on a
        # level like L3 that desyncs them to asymmetric rows before the merge
        # even starts (the winning path starts from the clean symmetric spawn).
        # Identity no longer needs the probes — it is read from the first real
        # move's OBSERVED motion (see _assign_identity).
        if self._measure_queue and not self._scheme_complete():
            a = self._measure_queue.pop(0)
            self._measure_prev = list(self._identity_or_sorted(grid))
            self._measure_action = a
            return simple_action(a)
        self._measure_queue = []
        self._measure_action = None

        # Phase B0 — CLEAR movable blocks off the merge path (L3-class levels).
        # Built once from the parsed board (deterministic), drained one action
        # per frame (ACTION6 select/deselect clicks + block moves). A block
        # obstructs the players like a wall; relocating those on the merge
        # trajectory to off-path parking cells opens the merge. Gated: only runs
        # when cvcer blocks are actually detected.
        if self._maze.blocks and self._clear_plan is None:
            self._clear_plan = self._build_clear_plan(grid) or []
        if self._clear_plan:
            kind, *rest = self._clear_plan.pop(0)
            if kind == "click":
                return click_action(rest[0], rest[1])
            return simple_action(rest[0])

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
            self._prev_merge_players = None
            return simple_action(move_ids[0])
        # Identity from OBSERVED motion: the two players just moved by
        # {scheme[a][0], scheme[a][1]}; the one whose displacement matches
        # scheme[last_action][0] is player-0. This reads identity directly off
        # the frame (no fragile prediction/flip heuristic) and is exact whenever
        # the pair actually moved.
        self._assign_identity(players)

        blocks = self._current_blocks(grid)
        plan = self._search_merge(move_ids, blocks)
        if plan:
            self._no_plan_streak = 0
            self._prev_merge_players = players
            self._last_action = plan[0]
            return simple_action(plan[0])
        # No merge plan (unmodelled variant) — gated explorer preserving floor.
        self._no_plan_streak += 1
        self._prev_merge_players = players
        self._last_action = self._explore(move_ids)
        return simple_action(self._last_action)

    def _identity_or_sorted(self, grid: tuple) -> list[Cell]:
        """The two players in the identity order established SO FAR this level
        (or sorted, before any is established)."""
        players = self._current_players(grid)
        if self._p0 is not None and self._p1 is not None and len(players) == 2:
            self._assign_identity(players)
            return [self._p0, self._p1]
        return players

    def _assign_identity(self, players: list[Cell]) -> None:
        """Map the two observed cells to ordered identities p0/p1 from the
        OBSERVED motion of the last action. The two players just displaced by
        ``{scheme[a][0], scheme[a][1]}`` (mirror opposites in the column axis),
        so the cell whose displacement from its previous position matches
        ``scheme[a][0]`` is player-0. This reads identity straight off the frame
        and is exact whenever the pair moved; if it didn't move (both blocked)
        or there is no prior frame, identity is kept / bootstrapped by proximity.

        This replaced a prediction-then-flip heuristic that could oscillate:
        after the block-clearing phase the pair can sit at asymmetric rows with
        a mirror-ambiguous assignment, and only the actual observed motion
        disambiguates it without a self-fighting correction loop."""
        a, b = players[0], players[1]
        prev = self._prev_merge_players
        act = self._last_action
        if (
            prev is not None
            and len(prev) == 2
            and act is not None
            and 0 in self._scheme[act]
            and 1 in self._scheme[act]
        ):
            # match each current cell to its nearest previous cell, then to the
            # scheme's two expected displacements.
            target0 = self._scheme[act][0]
            best_pair: tuple[int, Cell, Cell] | None = None
            for cur0, cur1 in ((a, b), (b, a)):
                # cur0 assumed p0 (moved by target0 from some prev cell)
                cost = min(_manhattan(cur0, (p[0] + target0[0], p[1] + target0[1])) for p in prev)
                if best_pair is None or cost < best_pair[0]:
                    best_pair = (cost, cur0, cur1)
            if best_pair is not None:
                self._p0, self._p1 = best_pair[1], best_pair[2]
                return
        if self._p0 is None or self._p1 is None:
            self._p0, self._p1 = a, b
            return
        # No usable motion this frame — keep identity by proximity to the prior
        # assignment (handles a blocked no-op without dropping identity).
        keep = _manhattan(a, self._p0) + _manhattan(b, self._p1)
        swap = _manhattan(a, self._p1) + _manhattan(b, self._p0)
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

    def _successors(self, move_ids: list[int], blocks: set[Cell] | None = None):
        maze = self._maze
        assert maze is not None
        # cvcer blocks obstruct players exactly like walls (until relocated by
        # the clearing phase). Union them in so the merge search never plans
        # through a block.
        walls = maze.walls | (blocks if blocks is not None else set())
        hazards = maze.hazards
        gh, gw = maze.gh, maze.gw
        scheme = self._scheme
        usable = [a for a in move_ids if 0 in scheme[a] and 1 in scheme[a]]
        plates = maze.plates
        gate_walls = maze.gate_walls

        def _closed_gate_walls(state: JointState) -> set[Cell]:
            """The gate-wall cells that block in THIS state — a group's walls
            block unless one of the two players stands on one of its plates
            (momentary gate; the wall set is a pure function of the positions)."""
            if not gate_walls:
                return set()
            p0, p1 = state
            closed: set[Cell] = set()
            for color, ws in gate_walls.items():
                pls = plates.get(color, set())
                if p0 not in pls and p1 not in pls:
                    closed |= ws
            return closed

        def _step(cell: Cell, d: Cell, blocked: set[Cell]) -> Cell:
            nxt = (cell[0] + d[0], cell[1] + d[1])
            if 0 <= nxt[0] < gh and 0 <= nxt[1] < gw and nxt not in walls and nxt not in blocked:
                return nxt
            return cell

        def successors(state: JointState):
            p0, p1 = state
            blocked = _closed_gate_walls(state)
            for a in usable:
                n0 = _step(p0, scheme[a][0], blocked)
                n1 = _step(p1, scheme[a][1], blocked)
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

    def _search_merge(self, move_ids: list[int], blocks: set[Cell] | None = None) -> list[int] | None:
        if self._maze is None or self._p0 is None or self._p1 is None:
            return None
        start: JointState = (self._p0, self._p1)
        successors = self._successors(move_ids, blocks)

        def goal(state: JointState) -> bool:
            return state[0] == state[1]

        path = configuration_path(start, goal, successors, max_states=_MERGE_SEARCH_BUDGET)
        return list(path) if path else None

    def _current_blocks(self, grid: tuple) -> set[Cell]:
        """cvcer block cells RIGHT NOW (colour 9), re-read each frame — their
        positions change as the clearing phase relocates them."""
        if self._maze is None:
            return set()
        maze = self._maze
        cells: set[Cell] = set()
        for reg in find_regions(grid, background=None):
            if reg["color"] != _BLOCK_COLOR:
                continue
            for r, c in reg["cells"]:
                cells.add(((r - maze.off_y) // maze.scale, (c - maze.off_x) // maze.scale))
        return cells

    # ── block clearing (L3-class movable obstacles) ─────────────────────

    def _replay_occupied(self, start: JointState, plan: list[int]) -> set[Cell]:
        """Every grid cell either player occupies along ``plan`` (blocks treated
        as floor). Used to find which cvcer blocks sit ON the merge path."""
        maze = self._maze
        assert maze is not None
        scheme = self._scheme

        def _step(cell: Cell, d: Cell) -> Cell:
            nxt = (cell[0] + d[0], cell[1] + d[1])
            if 0 <= nxt[0] < maze.gh and 0 <= nxt[1] < maze.gw and nxt not in maze.walls:
                return nxt
            return cell

        occ = {start[0], start[1]}
        st = start
        for a in plan:
            p0, p1 = st
            n0 = _step(p0, scheme[a][0])
            n1 = _step(p1, scheme[a][1])
            if p0[0] == p1[0] and abs(p0[1] - p1[1]) == 1 and ((n0 == p1 and n1 == p0) or n0 == n1):
                mid = ((p0[0] + p1[0]) // 2, (p0[1] + p1[1]) // 2)
                st = (mid, mid)
            else:
                st = (n0, n1)
            occ.add(st[0])
            occ.add(st[1])
        return occ

    def _build_clear_plan(self, grid: tuple) -> list[tuple] | None:
        """Offline plan (deterministic) that relocates every cvcer block sitting
        on the merge path to an off-path parking cell, so the joint merge opens.
        Each relocation = ACTION6 select-click on the block, block-move actions
        routed by :func:`grid_shortest_path`, ACTION6 deselect-click on a floor
        cell. Returns the queued actions, or ``None`` if any block can't be
        parked (the merge phase then bails via the no-plan streak)."""
        maze = self._maze
        players = self._current_players(grid)
        if maze is None or len(players) < 2 or not maze.blocks:
            return []
        self._p0, self._p1 = players[0], players[1]
        # merge path with blocks as FLOOR — its trajectory tells us which
        # blocks obstruct.
        floor_plan = self._search_merge(list(_MOVE_ACTIONS), blocks=None)
        if not floor_plan:
            # No merge even with the blocks GONE → the block is not an obstacle
            # to clear but a TOOL to PLACE: some cell, occupied by the block-as-
            # wall, blocks one mirror player during a move so the pair can
            # desync and merge (the L4 mechanic). Search for such a placement.
            return self._build_place_plan(players)
        occ = self._replay_occupied((self._p0, self._p1), floor_plan)
        blocking = [b for b in sorted(maze.blocks) if b in occ]
        if not blocking:
            return []

        cur_blocks = set(maze.blocks)
        plan: list[tuple] = []
        for blk in blocking:
            park, route = self._route_block(blk, occ, cur_blocks)
            if park is None:
                return None
            sx, sy = maze.pixel_center(blk)
            plan.append(("click", sx, sy))               # select the block
            plan.extend(("move", a) for a in route)      # walk it to parking
            dx, dy = maze.pixel_center(self._deselect_cell(cur_blocks | {park}))
            plan.append(("click", dx, dy))               # deselect
            cur_blocks.discard(blk)
            cur_blocks.add(park)

        # Append the merge itself, computed OPEN-LOOP over the now-cleared board
        # (parked blocks as walls) from the current sorted identity. Clearing
        # never moves the players, so this start position is exact. Open-loop
        # (vs the closed-loop re-planner) is deliberate: after clearing, the pair
        # can sit at asymmetric rows where per-frame identity re-derivation
        # oscillates, whereas the one-shot ordered plan — validated to a live win
        # — applies cleanly. If it under-shoots, the closed-loop merge still runs
        # afterwards as a fallback.
        self._p0, self._p1 = players[0], players[1]
        merge = self._search_merge(list(_MOVE_ACTIONS), blocks=cur_blocks)
        if merge:
            plan.extend(("move", a) for a in merge)
        return plan

    def _build_place_plan(self, players: list[Cell]) -> list[tuple] | None:
        """The L4 mechanic: the single cvcer block is a DESYNC TOOL, not an
        obstacle. Find a cell the block can reach such that, standing there as a
        wall, it blocks one mirror player during a move so the pair can close
        its (asymmetric-row) gap and merge; route the block there. The merge
        itself is left to the closed-loop merge phase (which reads the block's
        new position as a wall and handles the asymmetric-row start via motion
        identity). Returns the block-relocation actions, or ``None`` if no
        reachable placement enables a merge."""
        maze = self._maze
        assert maze is not None
        if len(maze.blocks) != 1:
            return None  # only single-block constructive placement is modelled
        blk = next(iter(maze.blocks))
        self._p0, self._p1 = players[0], players[1]
        # cells the block can reach (it is blocked by walls AND hazards, unlike
        # a player which is only blocked by walls; players are not obstacles to
        # a block).
        passable = [[True] * maze.gw for _ in range(maze.gh)]
        for (r, c) in maze.walls | maze.hazards:
            passable[r][c] = False
        best: tuple[int, Cell, list[Cell]] | None = None
        for gy in range(maze.gh):
            for gx in range(maze.gw):
                target = (gy, gx)
                if target in maze.walls or target in maze.hazards or target in players:
                    continue
                route = grid_shortest_path(passable, blk, target)
                if route is None:
                    continue
                mp = self._search_merge(list(_MOVE_ACTIONS), blocks={target})
                if not mp:
                    continue
                cost = len(route) + len(mp)
                if best is None or cost < best[0]:
                    best = (cost, target, route)
        if best is None:
            return None
        _, target, route = best
        plan: list[tuple] = [("click", *maze.pixel_center(blk))]  # select
        plan.extend(("move", int(a)) for a in path_to_moves(route, _BLOCK_MOVE_LABELS))
        plan.append(("click", *maze.pixel_center(self._deselect_cell({target}))))  # deselect
        return plan

    def _route_block(self, blk: Cell, occ: set[Cell], cur_blocks: set[Cell]) -> tuple[Cell | None, list[int]]:
        """Nearest off-path parking cell for ``blk`` and the block-move actions
        to reach it. The block routes over cells that are not walls / hazards /
        OTHER blocks (players are not obstacles to a block)."""
        maze = self._maze
        assert maze is not None
        gh, gw = maze.gh, maze.gw
        passable = [[True] * gw for _ in range(gh)]
        for (r, c) in maze.walls | maze.hazards:
            passable[r][c] = False
        for b in cur_blocks:
            if b != blk:
                passable[b[0]][b[1]] = False
        best: tuple[Cell, list[Cell]] | None = None
        for gy in range(gh):
            for gx in range(gw):
                cell = (gy, gx)
                if cell in occ or cell in maze.walls or cell in maze.hazards or cell in cur_blocks:
                    continue
                path = grid_shortest_path(passable, blk, cell)
                if path is not None and (best is None or len(path) < len(best[1])):
                    best = (cell, path)
        if best is None:
            return None, []
        park, path = best
        return park, [int(a) for a in path_to_moves(path, _BLOCK_MOVE_LABELS)]

    def _deselect_cell(self, cur_blocks: set[Cell]) -> Cell:
        """Any non-cvcer floor cell — clicking it deselects the held block
        (clicking a cvcer would just select a DIFFERENT block)."""
        maze = self._maze
        assert maze is not None
        for gy in range(maze.gh):
            for gx in range(maze.gw):
                cell = (gy, gx)
                if cell not in maze.walls and cell not in maze.hazards and cell not in cur_blocks:
                    return cell
        return (0, 0)

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
