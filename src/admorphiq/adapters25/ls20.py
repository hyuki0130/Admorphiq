"""script25 quarantined adapter: LS20 (shape/color/rotation-matching maze).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

**Mechanic model (source-read for understanding only, never imported; then
verified live).** The avatar carries a "token" with three attributes — SHAPE,
COLOR, ROTATION. The maze contains CHANGER cells that each cycle one attribute
of the carried token when stepped on, WALL cells, one or more GOAL cells (each
requires a specific (shape, color, rotation) — BLOCKING until the token matches,
level-completing the instant the avatar stands on it with a matching token), and
step-REFILL cells that top the life budget back up. A per-level STEP COUNTER
(rendered as a colour-11 band on rows 61-62) decrements by 2 per action; on
exhaustion the avatar loses one of 3 lives and repositions to the level start
(resetting position, token, AND goal progress). Losing all 3 lives is a
GAME_OVER. ``available_actions`` is ``[1,2,3,4]`` (ACTION1=up, 2=down, 3=left,
4=right); there is no interact/undo action.

**Two solution substrates, gated (this file).**

1. **OFFLINE MAZE RECONSTRUCTION + joint BFS + open-loop execution** (primary).
   The R56 investigation (four rounds — refill / open-loop / deepest-first /
   prefix, all banked in the git history of this file) proved L2 is winnable
   (a validated 45-action live plan) but NOT via online frame-keyed exploration
   under full-reset 21-action lives — the exploration economics don't close in
   budget. This adapter sidesteps exploration: it PARSES the maze from a single
   settled frame (walls / avatar+token / goal+required-token / changers-by-type
   / refills — every element frame-separable, validated byte-exact against the
   engine ground truth for L1 and L2), runs a JOINT BFS over
   ``(cell, shape, color, rotation, steps_left, refills_taken)`` toward "stand
   on a goal with a matching token" (life-budget- and refill-aware), and
   executes the found action sequence OPEN-LOOP. Open-loop is load-bearing: the
   env is deterministic under an action sequence from a settled anchor
   (measured: committed legs survive), and the R56 wall was per-step re-keying
   corrupting an aliased frame-graph — not the walk dying — so replaying a
   pre-computed plan with endpoint-only verification is exactly the fix.

   Measured (this build): L1 clears in 13 actions (human 22), L2 in 45 (123),
   L3 in 39 (73), L4 in 52 (84) — all super-human, all frame-derived (no engine
   data at runtime) and replaying to live wins. L3/L4 add PUSH-WALLS
   (``gbvqrjtaqo``): static sprites that, on contact, shove the avatar a
   deterministic distance. A push-wall is a transition RULE, not a dynamic
   hazard — it renders as a 5-pixel colour-1 edge line whose orientation gives
   the push direction (see :func:`_detect_pushwalls`), and the shove slides the
   avatar until the next wall or goal, so the joint BFS absorbs it as a
   different successor edge (measured: an L3 up-move onto (9,5) is shoved right
   to (34,5); L4 clears with all 8 push-walls).

   The parser is validated dev-time by reconstructing the engine's own sprite
   positions (walls / changer / refills / goal) and start/goal token indices
   from the rendered frame — see ``scripts/rounds/`` provenance and the LS20
   wiki page. Floor is keyed as colour-3-dominant cells (plus the changer /
   refill-capture / goal cells): this is SAFE (never routes a plan through a
   real wall — measured zero violations) and complete for the solution path.

   **Named divergences / scope.** The joint BFS handles a SINGLE goal with a
   STATIC maze + changers + refills + push-walls (L1-L4). NOT modelled: MOVING
   changers (source L5, carried by a moving hazard), MULTI-goal levels (L6), and
   a Fog flag that hides structure (L7). On multi-goal / Fog the parse returns
   ``None`` (gates to substrate 2); on a moving changer the parse succeeds but
   the open-loop plan desyncs and drains, then the adapter falls to substrate 2
   — either way the floor is preserved. The token appearance lives in a fixed
   bottom-left indicator sprite
   at pixel (3,55), NOT in the avatar's own pixels (the avatar renders a
   constant colour-12-over-9 marker); the required token lives in each goal
   cell's inner preview — both decoded by matching the 3x3 shape bitmap under
   its rotation against the six base shapes (embedded as parse constants).

2. **Frame-keyed transition-graph frontier explorer** (fallback, the R56
   substrate). Keys each observation by the multiset of live-region signatures
   excluding edge-pinned HUD bands, records observed edges, and explores by
   BFS-from-start over the discovered graph via
   :func:`admorphiq.kernels.configuration_path`. This clears L1 alone
   (~606 actions) and is the safe floor whenever the reconstruction gates out.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments each frame into regions for
    the fallback explorer's state key.
  - :func:`admorphiq.kernels.configuration_path` BFS-plans the shortest
    known-edge action sequence to the nearest unexplored frontier key.
"""

from __future__ import annotations

from collections import Counter
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

GAME_ID = "ls20"

Grid = tuple[tuple[int, ...], ...]
Cell = tuple[int, int]
Region = dict[str, Any]
StateKey = frozenset[tuple[int, int, int, int, int, int]]

_GIVEUP_DEFAULT = 4000

# ── frame-understanding constants (decoded offline from the game source for
#    UNDERSTANDING only; the adapter reads only frames at runtime) ────────────
#
# The six base token SHAPES (``ijessuuig`` order 0..5); a cell is "filled" where
# the bitmap value is not -1. The token's shape+rotation is recovered by
# matching the filled-cell SET (under 0/90/180/270 rotation) against these.
_BASE_SHAPES: tuple[tuple[tuple[int, ...], ...], ...] = (
    ((0, 0, -1), (-1, 0, 0), (0, -1, 0)),
    ((-1, 0, -1), (-1, 0, -1), (0, 0, 0)),
    ((0, -1, 0), (0, -1, 0), (0, 0, 0)),
    ((-1, 0, 0), (0, -1, 0), (-1, 0, -1)),
    ((-1, 0, -1), (0, 0, -1), (-1, 0, 0)),
    ((0, 0, 0), (-1, -1, 0), (0, -1, 0)),
)
# Token COLOUR palette in the changer's cyclic order (``tnkekoeuk``); the colour
# attribute index is this list's index of the token's fill colour.
_PALETTE: tuple[int, ...] = (12, 9, 14, 8)
_FLOOR_COLOR = 3  # BACKGROUND_COLOR — passable floor renders dominantly this
_WALL_COLOR = 4
_GOAL_BORDER = 5  # goal cell (rjlbuycveu) border colour
_REFILL_COLOR = 11  # step-refill ring (npxgalaybz); also the HUD counter band
_ROT_MARK = 1  # rotation-changer icon (rhsxkxzdjz) carries colour-1 pixels
_SHAPE_MARK = 0  # shape-changer icon (mkjdaccuuf) carries colour-0 pixels
_CELL = 5  # grid unit == avatar sprite size (gisrhqpee); moves are one unit
_STEP_FULL = 42  # StepCounter
_STEP_DECR = 2  # StepsDecrement (None in level data defaults to 2)
_PLAYABLE_MAX_ROW = 55  # arena is above the bottom HUD (token indicator / band)
_TOKEN_ICON_XY = (3, 55)  # bottom-left token indicator origin (6x6 == 3x3 x2)
_SEARCH_EXPANSIONS = 400_000
_PROBE_CAP = 2  # settle probes issued at a stale level-transition frame

# Precompute the filled-cell set -> (shape_idx, rot_idx) map (first rotation to
# produce a given set wins the tie, matching the engine's canonical rotation).
_SHAPE_ROT: dict[frozenset[Cell], tuple[int, int]] = {}
for _si, _mat in enumerate(_BASE_SHAPES):
    _cur = frozenset((r, c) for r in range(3) for c in range(3) if _mat[r][c] != -1)
    for _ri in range(4):
        _SHAPE_ROT.setdefault(_cur, (_si, _ri))
        _cur = frozenset((c, 2 - r) for (r, c) in _cur)  # rotate 90° clockwise

# action id -> (dx, dy) in grid cells (ls20 step(): 1=up 2=down 3=left 4=right)
_MOVES: dict[int, Cell] = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}

# fallback-explorer HUD-band geometry (fractions of the frame, never hardcoded
# pixel rows) — matches admorphiq.adapters25.tu93's edge-pinned-thin convention.
_THIN_FRACTION = 0.06
_SPAN_FRACTION = 0.4
_EDGE_FRACTION = 0.05
_FRONTIER_SEARCH_BUDGET = 100_000


# ════════════════════════════════════════════════════════════════════════
# Frame parser: settled 64x64 grid -> maze reconstruction, or None.
# ════════════════════════════════════════════════════════════════════════


def _cell_counts(grid: Grid, x: int, y: int, w: int = _CELL, h: int = _CELL) -> Counter:
    c: Counter = Counter()
    H, W = len(grid), len(grid[0])
    for r in range(y, min(y + h, H)):
        row = grid[r]
        for cc in range(x, min(x + w, W)):
            c[row[cc]] += 1
    return c


def _decode_shape3(cells_by_color: dict[Cell, int]) -> tuple[int, int, int] | None:
    """A 3x3 ``{(r,c): colour}`` fill map -> ``(shape_idx, color_idx, rot_idx)``.

    Returns ``None`` when the filled-cell set is not one of the six base shapes
    (under any rotation) or the fill colour is off-palette.
    """
    if not cells_by_color:
        return None
    fs = frozenset(cells_by_color)
    sr = _SHAPE_ROT.get(fs)
    if sr is None:
        return None
    col = Counter(cells_by_color.values()).most_common(1)[0][0]
    if col not in _PALETTE:
        return None
    return (sr[0], _PALETTE.index(col), sr[1])


def _decode_token(grid: Grid) -> tuple[int, int, int] | None:
    """The bottom-left token indicator (6x6 == 3x3 scaled 2) -> appearance."""
    ox, oy = _TOKEN_ICON_XY
    if oy + 6 > len(grid) or ox + 6 > len(grid[0]):
        return None
    cbc: dict[Cell, int] = {}
    for r in range(3):
        for c in range(3):
            sub: Counter = Counter()
            for dr in range(2):
                for dc in range(2):
                    v = grid[oy + r * 2 + dr][ox + c * 2 + dc]
                    if v in _PALETTE:
                        sub[v] += 1
            if sub:
                cbc[(r, c)] = sub.most_common(1)[0][0]
    return _decode_shape3(cbc)


def _decode_goal_preview(grid: Grid, gx: int, gy: int) -> tuple[int, int, int] | None:
    """The inner 3x3 of a goal cell (offset +1,+1) -> required appearance."""
    cbc: dict[Cell, int] = {}
    for r in range(3):
        for c in range(3):
            v = grid[gy + 1 + r][gx + 1 + c]
            if v in _PALETTE:
                cbc[(r, c)] = v
    return _decode_shape3(cbc)


def _classify_changer(hh: Counter, dom: int) -> str | None:
    """Type a lattice cell's changer icon, or ``None`` if it is not a changer.

    A changer sits on a FLOOR cell (dom == ``_FLOOR_COLOR``); requiring floor
    excludes the colour-1 decorative arena-edge / push-wall markers, which sit
    on colour-4 WALL cells. Signatures, tested in this ORDER (the colour changer
    also carries one colour-0 pixel, so the multi-palette test MUST precede the
    colour-0 shape test, or a colour changer is mis-typed "shape"):
      - rotation (``rhsxkxzdjz``): carries a colour-1 pixel;
      - colour (``soyhouuebz``): a >= 2 distinct-palette-colour icon;
      - shape (``mkjdaccuuf``): colour-0 pixels only.
    """
    if dom != _FLOOR_COLOR:
        return None
    if hh.get(_ROT_MARK, 0) > 0:
        return "rot"
    if sum(1 for c in _PALETTE if hh.get(c, 0) > 0) >= 2:
        return "color"
    if hh.get(_SHAPE_MARK, 0) > 0:
        return "shape"
    return None


def _find_avatar(grid: Grid) -> Cell | None:
    """The avatar marker: a 5x5 block, top two rows colour 12, bottom three 9."""
    H, W = len(grid), len(grid[0])
    for y in range(H - 4):
        for x in range(W - 4):
            if grid[y][x] != 12 or grid[y + 2][x] != 9:
                continue
            top = all(grid[y + i][x + c] == 12 for i in range(2) for c in range(5))
            bot = all(grid[y + i][x + c] == 9 for i in range(2, 5) for c in range(5))
            if top and bot:
                return (x, y)
    return None


def _parse(grid: Grid) -> dict[str, Any] | None:
    """Reconstruct the maze from a settled frame, or ``None`` when it cannot be
    parsed unambiguously as a single-goal level (the adapter then gates to the
    fallback explorer). Named gate-outs: no avatar / no goal / undecodable token
    or goal-preview / more than one goal."""
    if not grid or len(grid) < 64 or len(grid[0]) < 64:
        return None
    avatar = _find_avatar(grid)
    if avatar is None:
        return None
    ax, ay = avatar
    ox, oy = ax % _CELL, ay % _CELL
    xs = list(range(ox, len(grid[0]) - _CELL + 1, _CELL))
    ys = list(range(oy, len(grid) - _CELL + 1, _CELL))
    lattice = {(x, y) for x in xs for y in ys}

    goals: list[Cell] = []
    goal_req: tuple[int, int, int] | None = None
    changers: dict[Cell, str] = {}
    for x in xs:
        for y in ys:
            if y >= _PLAYABLE_MAX_ROW:  # bottom HUD zone is not playable maze
                continue
            hh = _cell_counts(grid, x, y)
            dom = hh.most_common(1)[0][0]
            if dom == _GOAL_BORDER and sum(hh.get(c, 0) for c in _PALETTE) >= 3:
                goals.append((x, y))
                if goal_req is None:
                    goal_req = _decode_goal_preview(grid, x, y)
                continue
            kind = _classify_changer(hh, dom)
            if kind is not None:
                changers[(x, y)] = kind

    if len(goals) != 1 or goal_req is None:
        return None  # multi-goal / undecodable — gate to explorer
    goal = goals[0]

    token = _decode_token(grid)
    if token is None:
        return None

    refills = _find_refills(grid, xs, ys)
    special = {goal, *changers, *refills}
    passable = {
        (x, y)
        for (x, y) in lattice
        if _cell_counts(grid, x, y).most_common(1)[0][0] == _FLOOR_COLOR or (x, y) in special
    }
    return {
        "avatar": avatar,
        "goal": goal,
        "goal_req": goal_req,
        "token": token,
        "changers": changers,
        "refills": frozenset(refills),
        "passable": passable,
        "pushwalls": _detect_pushwalls(grid, xs, ys),
    }


def _detect_pushwalls(grid: Grid, xs: list[int], ys: list[int]) -> dict[Cell, Cell]:
    """``{collision_cell: (dx, dy)}`` for each static push-wall (``gbvqrjtaqo``).

    A push-wall renders as a 5-pixel colour-1 edge LINE on one side of its cell;
    the sprite body extends past that edge into the neighbouring cell, so the
    push goes TOWARD the edge and the avatar collides one cell over (measured:
    an L3 up-move onto (9,5) is shoved right to (34,5)). The push then slides the
    avatar in ``(dx,dy)`` until the next cell is a wall OR a goal (goals are in
    the engine's push-stop set) — see ``_solve``.
    """
    out: dict[Cell, Cell] = {}
    for x in xs:
        for y in ys:
            if all(grid[y + r][x + 4] == _ROT_MARK for r in range(5)):
                out[(x + _CELL, y)] = (1, 0)
            elif all(grid[y + r][x] == _ROT_MARK for r in range(5)):
                out[(x - _CELL, y)] = (-1, 0)
            elif all(grid[y + 4][x + c] == _ROT_MARK for c in range(5)):
                out[(x, y + _CELL)] = (0, 1)
            elif all(grid[y][x + c] == _ROT_MARK for c in range(5)):
                out[(x, y - _CELL)] = (0, -1)
    return out


# ════════════════════════════════════════════════════════════════════════
# L5 pixel-faithful push-carry model + moving-changer joint BFS.
#
# L5 adds two mechanics the lattice static model can't capture:
#   (a) push-walls whose SPRITES are pixel-offset from the avatar lattice, so
#       collision is a sprite bounding-box overlap (``prpxgfxlcm``) and the carry
#       distance steps by the wall's WIDTH (``ullzqnksoj``) — NOT lattice-cell
#       equality; and
#   (b) a MOVING rotation changer that patrols a horizontal track one cell per
#       SUCCESSFUL avatar move (``dboxixicic``), bouncing at the ends.
# Both are exactly replicated below at the PIXEL level (validated by 720-action
# lockstep against the live engine, 0 divergence), so a joint BFS over
# ``(ax, ay, sh, co, ro, steps_left, refills_taken, mover_x, mover_dir)`` plans a
# death-free action sequence executed OPEN-LOOP. The mover's track + phase are
# learned at runtime from a few settled observation frames (the mover renders a
# colour-1 rot icon at its live cell), then the maze is parsed and solved. See
# the LS20 wiki page for the full derivation.
# ════════════════════════════════════════════════════════════════════════

_L5_LIFE = _STEP_FULL // _STEP_DECR  # per-life action budget (21)
_L5_OBS_CAP = 10  # settled observation frames to learn the mover cycle
_L5_SEARCH_CAP = 3_000_000  # joint-BFS expansion cap
_MOVER_WATCH_CHECKS = 4  # rot-changer frames to confirm a level is static (no mover)


def _detect_rot_cell(grid: Grid) -> Cell | None:
    """The single rotation-changer lattice cell in a settled frame, or ``None``.
    Used to watch for the L5 mover's motion while the static plan drains — it
    reads the same rot-changer the parser classifies, so a change across frames
    means the changer moved (i.e. this is the L5 moving-changer level)."""
    parsed = _parse_l5_maze(grid)
    if parsed is None:
        return None
    rots = [c for c, k in parsed["changers"].items() if k == "rot"]
    return rots[0] if len(rots) == 1 else None


def _detect_pushwalls_pixel(grid: Grid) -> list[tuple[int, int, int, int]]:
    """Push-walls as ``(sprite_x, sprite_y, dx, dy)`` from length-5 colour-1
    LINES that border a colour-4 wall. Each push-wall (``gbvqrjtaqo``) renders a
    5-pixel colour-1 edge line with the wall body on ONE side; the push goes
    AWAY from that wall. The sprite top-left is recovered from the line + edge:
      horizontal line, wall above -> push down, sprite top-left = line start;
      horizontal line, wall below -> push up, sprite top = line row - 4;
      vertical line, wall left -> push right, sprite left = line col;
      vertical line, wall right -> push left, sprite left = line col - 4.
    Pixel-exact vs engine ground truth on all 8 L5 walls. The mover's rot icon
    is 2-3 scattered pixels (never a length-5 line) so it is excluded here.
    """
    H, W = len(grid), len(grid[0])
    out: list[tuple[int, int, int, int]] = []
    consumed: set[Cell] = set()
    for y in range(H):
        x = 0
        while x <= W - _CELL:
            if all(grid[y][x + i] == _ROT_MARK for i in range(_CELL)):
                above = grid[y - 1][x] if y - 1 >= 0 else -9
                below = grid[y + 1][x] if y + 1 < H else -9
                if above == _WALL_COLOR:
                    out.append((x, y, 0, 1))
                    consumed.update((x + i, y) for i in range(_CELL))
                elif below == _WALL_COLOR:
                    out.append((x, y - 4, 0, -1))
                    consumed.update((x + i, y) for i in range(_CELL))
                x += _CELL
            else:
                x += 1
    for x in range(W):
        y = 0
        while y <= H - _CELL:
            if all(grid[y + i][x] == _ROT_MARK for i in range(_CELL)) and (x, y) not in consumed:
                left = grid[y][x - 1] if x - 1 >= 0 else -9
                right = grid[y][x + 1] if x + 1 < W else -9
                if left == _WALL_COLOR:
                    out.append((x, y, 1, 0))
                    consumed.update((x, y + i) for i in range(_CELL))
                elif right == _WALL_COLOR:
                    out.append((x - 4, y, -1, 0))
                    consumed.update((x, y + i) for i in range(_CELL))
                y += _CELL
            else:
                y += 1
    return out


def _read_life(grid: Grid) -> int:
    """Life remaining in ACTIONS, read from the step-counter band. The band
    (``hbuhvkxlhc.render_interface``) starts at col 13 and fills one colour-11-
    family cell per remaining ``current_steps`` (empty cells render as floor);
    ``current_steps`` decrements by ``_STEP_DECR`` per action, so
    ``actions = filled // _STEP_DECR``. Bounded to the counter width."""
    H, W = len(grid), len(grid[0])
    row = min(61, H - 2)
    filled = sum(1 for c in range(13, min(13 + _STEP_FULL, W)) if grid[row][c] != _FLOOR_COLOR)
    return filled // _STEP_DECR


def _snap_to_lattice(sx: int, sy: int, ox: int, oy: int) -> Cell:
    """The avatar-lattice cell whose 5x5 box contains sprite top-left (sx,sy) —
    matching the engine's ``mrznumynfe`` containment trigger for pixel-offset
    refill/wall sprites."""
    return (sx - (sx - ox) % _CELL, sy - (sy - oy) % _CELL)


def _parse_l5_maze(grid: Grid) -> dict[str, Any] | None:
    """Reconstruct the L5 static maze (everything except the mover's live
    phase) from a settled frame, or ``None`` if it does not look like a
    single-goal push-wall level. The mover appears here as a ``rot`` changer at
    its current cell; the caller strips it after learning its motion."""
    avatar = _find_avatar(grid)
    if avatar is None:
        return None
    ax, ay = avatar
    ox, oy = ax % _CELL, ay % _CELL
    xs = list(range(ox, len(grid[0]) - _CELL + 1, _CELL))
    ys = list(range(oy, len(grid) - _CELL + 1, _CELL))

    pushwalls = [(sx, sy, dx, dy, _CELL, _CELL) for (sx, sy, dx, dy) in _detect_pushwalls_pixel(grid)]

    goals: list[Cell] = []
    goal_req: tuple[int, int, int] | None = None
    changers: dict[Cell, str] = {}
    hard_walls: set[Cell] = set()
    passable: set[Cell] = set()
    for x in xs:
        for y in ys:
            hh = _cell_counts(grid, x, y)
            dom = hh.most_common(1)[0][0]
            if y < _PLAYABLE_MAX_ROW and dom == _GOAL_BORDER and sum(hh.get(c, 0) for c in _PALETTE) >= 3:
                goals.append((x, y))
                if goal_req is None:
                    goal_req = _decode_goal_preview(grid, x, y)
                passable.add((x, y))
                continue
            if dom == _FLOOR_COLOR:
                passable.add((x, y))
            else:
                hard_walls.add((x, y))
            if y < _PLAYABLE_MAX_ROW:
                kind = _classify_changer(hh, dom)
                if kind is not None:
                    changers[(x, y)] = kind
    if len(goals) != 1 or goal_req is None:
        return None
    goal = goals[0]
    token = _decode_token(grid)
    if token is None:
        return None
    refills = {_snap_to_lattice(sx, sy, ox, oy) for (sx, sy) in _find_refill_sprites(grid)}
    # avatar cell is not a wall; push collision cells must be passable
    hard_walls.discard(avatar)
    passable.add(avatar)
    for (sx, sy, dx, dy, w, h) in pushwalls:
        passable.add((sx, sy))
    return {
        "avatar": avatar,
        "goal": goal,
        "goal_req": goal_req,
        "token": token,
        "changers": changers,
        "refills": frozenset(refills),
        "passable": frozenset(passable),
        "hard_walls": frozenset(hard_walls),
        "pushwalls": tuple(pushwalls),
    }


def _find_refill_sprites(grid: Grid) -> set[Cell]:
    """Raw refill-ring sprite top-left pixels (colour-11 ring with a hole),
    above the HUD band. Pixel positions (may be off-lattice; caller snaps)."""
    H, W = len(grid), len(grid[0])
    out: set[Cell] = set()
    seen: set[Cell] = set()
    for r in range(min(H - 2, 60)):
        for c in range(W - 2):
            if (r, c) in seen:
                continue
            if (
                grid[r][c] == _REFILL_COLOR
                and grid[r][c + 1] == _REFILL_COLOR
                and grid[r + 1][c] == _REFILL_COLOR
                and grid[r + 1][c + 2] == _REFILL_COLOR
                and grid[r + 1][c + 1] != _REFILL_COLOR
            ):
                out.add((c, r))
                for dr in range(3):
                    for dc in range(3):
                        seen.add((r + dr, c + dc))
    return out


def _l5_mover_advance(track: tuple[int, ...], mx: int, mdir: int) -> tuple[int, int]:
    """One mover step along a horizontal track; bounce at the ends. Advances
    ONLY on a successful avatar move (caller does not call this on a block)."""
    if not track or mx < 0 or len(track) < 2:
        return mx, mdir  # no track or a single-cell track: mover stays put
    lo, hi = min(track), max(track)
    step = _CELL if mdir == 1 else -_CELL
    cand = mx + step
    if lo <= cand <= hi:
        return cand, mdir
    mdir = 3 if mdir == 1 else 1
    step = _CELL if mdir == 1 else -_CELL
    return mx + step, mdir


def _l5_carry_dist(fjz: frozenset[Cell], sx: int, sy: int, dx: int, dy: int, w: int, h: int) -> int:
    """``ullzqnksoj``: wall-widths the avatar is carried before a blocking cell."""
    wall_cx, wall_cy = sx + dx, sy + dy
    for k in range(1, 12):
        if (wall_cx + dx * w * k, wall_cy + dy * h * k) in fjz:
            return max(0, k - 1)
    return 0


def _l5_step(maze: dict[str, Any], s: tuple, action: int) -> tuple:
    """One engine step at the pixel level. ``s`` =
    ``(ax, ay, sh, co, ro, steps, taken, mx, mdir)``."""
    ax, ay, sh, co, ro, steps, taken, mx, mdir = s
    dx, dy = _MOVES[action]
    prov_mx, prov_mdir = _l5_mover_advance(maze["mover_track"], mx, mdir)
    nx, ny = ax + dx * _CELL, ay + dy * _CELL
    matched_goal = (nx, ny) == maze["goal"] and (sh, co, ro) == maze["goal_req"]
    if (nx, ny) in maze["hard_walls"] or ((nx, ny) == maze["goal"] and not matched_goal):
        return s  # blocked: mover undoes, avatar stays
    ax, ay = nx, ny
    kind = maze["changers"].get((ax, ay))
    if maze["mover_track"] and (ax, ay) == (prov_mx, maze["mover_my"]):
        kind = "rot"
    if kind == "rot":
        ro = (ro + 1) % 4
    elif kind == "color":
        co = (co + 1) % 4
    elif kind == "shape":
        sh = (sh + 1) % 6
    nsteps = steps - 1
    if (ax, ay) in maze["refills"] and (ax, ay) not in taken:
        nsteps = maze["step_full"]
        taken = taken | {(ax, ay)}
    if nsteps >= 0:
        for (sx, sy, pdx, pdy, w, h) in maze["pushwalls"]:
            if ax < sx + w and sx < ax + _CELL and ay < sy + h and sy < ay + _CELL:
                dist = _l5_carry_dist(maze["fjzuynaokm"], sx, sy, pdx, pdy, w, h)
                if dist > 0:
                    ax += pdx * w * dist
                    ay += pdy * h * dist
                    break
    return (ax, ay, sh, co, ro, nsteps, taken, prov_mx, prov_mdir)


def _l5_bfs(maze: dict[str, Any], start: tuple) -> list[int] | None:
    """Death-free joint BFS over the pixel sim toward standing on the goal with
    a matching token, refill- and life-aware. Returns the action sequence."""
    from collections import deque

    goal, req = maze["goal"], maze["goal_req"]

    def won(st: tuple) -> bool:
        return (st[0], st[1]) == goal and (st[2], st[3], st[4]) == req

    if won(start):
        return []
    seen = {start}
    queue: deque[tuple[tuple, list[int]]] = deque([(start, [])])
    exp = 0
    while queue and exp < _L5_SEARCH_CAP:
        s, path = queue.popleft()
        exp += 1
        if s[5] <= 0:  # out of life
            continue
        for aid in (1, 2, 3, 4):
            ns = _l5_step(maze, s, aid)
            if ns[5] < 0 or ns in seen:
                continue
            if won(ns):
                return path + [aid]
            seen.add(ns)
            queue.append((ns, path + [aid]))
    return None


# ════════════════════════════════════════════════════════════════════════
# L6 pixel model: EITHER-ORDER multi-goal + THREE synchronously-phased movers.
#
# L6 (source `pbznecvnfr`/`bejndxqqzf`) needs the avatar to stand on EACH of
# several goals with THAT goal's own matching token; a satisfied goal is removed
# (stops blocking) and the level completes when all are satisfied — an either-
# order coverage, modelled as a satisfied-goals frozenset in the search state.
# It also carries THREE moving changers (rot + shape on horizontal tracks, colour
# on a 2D region) that all advance ONCE per successful avatar move and all undo on
# a block (engine steps/undoes every `wsoslqeku` together) — so they share one
# phase and the joint search stays tractable. Each mover follows `npdjlrkhsg`
# (try dir, dir-1, dir+1, dir+2 over its track cells). The tracks + current
# (pos,dir) are learned frame-only from a short observation window (each mover
# renders its kind icon at its live cell; associate BY KIND). Validated: the
# frame-only pipeline joint-BFS-plans a sequence that replays to a live L6 win.
# ════════════════════════════════════════════════════════════════════════

# nakogfhyus direction vectors: 0=down 1=right 2=up 3=left (engine order).
_L6_DIRVEC: dict[int, Cell] = {0: (0, 1), 1: (1, 0), 2: (0, -1), 3: (-1, 0)}
_L6_OBS_CAP = 30  # max observation moves to learn the mover cycles
_L6_STABLE_NEED = 5  # observation moves with no new mover cell => tracks complete
_L6_SEARCH_CAP = 8_000_000


def _l6_mover_step(cells: frozenset[Cell], x: int, y: int, d: int) -> tuple[int, int, int]:
    """One `dboxixicic.npdjlrkhsg` step over a mover's track cells."""
    for cand in (d, (d - 1) % 4, (d + 1) % 4, (d + 2) % 4):
        dx, dy = _L6_DIRVEC[cand]
        nx, ny = x + dx * _CELL, y + dy * _CELL
        if (nx, ny) in cells:
            return (nx, ny, cand)
    return (x, y, d)


def _l6_dir_from(prev: Cell, cur: Cell) -> int | None:
    """The `npdjlrkhsg` direction implied by a mover's step prev -> cur, or None
    if they are not one grid unit apart (mover did not advance)."""
    v = (cur[0] - prev[0], cur[1] - prev[1])
    for d, (dx, dy) in _L6_DIRVEC.items():
        if (dx * _CELL, dy * _CELL) == v:
            return d
    return None


def _l6_step(maze: dict[str, Any], s: tuple, action: int) -> tuple:
    """One engine step for L6. ``s`` =
    ``(ax, ay, sh, co, ro, steps, taken, movers, satisfied)`` where ``movers`` is
    a tuple of ``(x, y, dir)`` parallel to ``maze['mover_kinds']``/``['mover_tracks']``
    and ``satisfied`` is the frozenset of covered goal indices."""
    ax, ay, sh, co, ro, steps, taken, movers, sat = s
    dx, dy = _MOVES[action]
    prov = tuple(_l6_mover_step(maze["mover_tracks"][i], *movers[i]) for i in range(len(movers)))
    nx, ny = ax + dx * _CELL, ay + dy * _CELL
    blocked = (nx, ny) in maze["hard_walls"]
    for gi, gc in enumerate(maze["goals"]):
        if (nx, ny) == gc and gi not in sat and (sh, co, ro) != maze["reqs"][gi]:
            blocked = True
    if blocked:
        return s
    ax, ay = nx, ny
    for i, mk in enumerate(maze["mover_kinds"]):
        if (ax, ay) == (prov[i][0], prov[i][1]):
            if mk == "rot":
                ro = (ro + 1) % 4
            elif mk == "color":
                co = (co + 1) % 4
            elif mk == "shape":
                sh = (sh + 1) % 6
    nsteps = steps - 1
    if (ax, ay) in maze["refills"] and (ax, ay) not in taken:
        nsteps = maze["step_full"]
        taken = taken | {(ax, ay)}
    if nsteps >= 0:
        for (sx, sy, pdx, pdy, w, h) in maze["pushwalls"]:
            if ax < sx + w and sx < ax + _CELL and ay < sy + h and sy < ay + _CELL:
                dist = _l5_carry_dist(maze["fjzuynaokm"], sx, sy, pdx, pdy, w, h)
                if dist > 0:
                    ax += pdx * w * dist
                    ay += pdy * h * dist
                    break
    nsat = sat
    for gi, gc in enumerate(maze["goals"]):
        if gi not in sat and (ax, ay) == gc and (sh, co, ro) == maze["reqs"][gi]:
            nsat = sat | {gi}
    return (ax, ay, sh, co, ro, nsteps, taken, prov, nsat)


def _l6_bfs(maze: dict[str, Any], start: tuple) -> list[int] | None:
    """Death-free joint BFS to cover ALL goals (each with its matching token),
    refill/life-aware, over the multi-mover pixel sim."""
    from collections import deque

    ngoals = len(maze["goals"])
    if len(start[8]) == ngoals:
        return []
    seen = {start}
    queue: deque[tuple[tuple, list[int]]] = deque([(start, [])])
    exp = 0
    while queue and exp < _L6_SEARCH_CAP:
        s, path = queue.popleft()
        exp += 1
        if s[5] <= 0:
            continue
        for aid in (1, 2, 3, 4):
            ns = _l6_step(maze, s, aid)
            if ns[5] < 0 or ns == s or ns in seen:
                continue
            if len(ns[8]) == ngoals:
                return path + [aid]
            seen.add(ns)
            queue.append((ns, path + [aid]))
    return None


def _parse_l6_maze(grid: Grid) -> dict[str, Any] | None:
    """Reconstruct an L6 (multi-goal) maze from a settled frame, or ``None``.
    Like :func:`_parse_l5_maze` but keeps ALL goals + per-goal required tokens;
    the moving changers appear as rot/shape/color changer cells (the caller
    learns their tracks). Returns None if there is no avatar / undecodable token
    or goal preview."""
    avatar = _find_avatar(grid)
    if avatar is None:
        return None
    ax, ay = avatar
    ox, oy = ax % _CELL, ay % _CELL
    xs = list(range(ox, len(grid[0]) - _CELL + 1, _CELL))
    ys = list(range(oy, len(grid) - _CELL + 1, _CELL))
    pushwalls = [(sx, sy, dx, dy, _CELL, _CELL) for (sx, sy, dx, dy) in _detect_pushwalls_pixel(grid)]
    goals: list[Cell] = []
    reqs: list[tuple[int, int, int]] = []
    changers: dict[Cell, str] = {}
    hard: set[Cell] = set()
    passable: set[Cell] = set()
    for x in xs:
        for y in ys:
            hh = _cell_counts(grid, x, y)
            dom = hh.most_common(1)[0][0]
            if y < _PLAYABLE_MAX_ROW and dom == _GOAL_BORDER and sum(hh.get(c, 0) for c in _PALETTE) >= 3:
                req = _decode_goal_preview(grid, x, y)
                if req is None:
                    return None
                goals.append((x, y))
                reqs.append(req)
                passable.add((x, y))
                continue
            if dom == _FLOOR_COLOR:
                passable.add((x, y))
            else:
                hard.add((x, y))
            if y < _PLAYABLE_MAX_ROW:
                kind = _classify_changer(hh, dom)
                if kind is not None:
                    changers[(x, y)] = kind
    token = _decode_token(grid)
    if token is None or not goals:
        return None
    refills = {_snap_to_lattice(sx, sy, ox, oy) for (sx, sy) in _find_refill_sprites(grid)}
    hard.discard(avatar)
    passable.add(avatar)
    for (sx, sy, dx, dy, w, h) in pushwalls:
        passable.add((sx, sy))
    return {
        "avatar": avatar,
        "goals": goals,
        "reqs": reqs,
        "changers": changers,
        "hard_walls": frozenset(hard),
        "passable": frozenset(passable),
        "refills": frozenset(refills),
        "token": token,
        "pushwalls": tuple(pushwalls),
    }


def _band_count(grid: Grid) -> int:
    """Raw non-floor cell count in the step-counter band (== current_steps)."""
    H, W = len(grid), len(grid[0])
    row = min(61, H - 2)
    return sum(1 for c in range(13, min(13 + _STEP_FULL, W)) if grid[row][c] != _FLOOR_COLOR)


def _find_refills(grid: Grid, xs: list[int], ys: list[int]) -> set[Cell]:
    """Step-refill rings (8 colour-11 pixels around a hole) in the maze area
    (rows above the HUD counter band) -> the lattice cell whose box captures
    each. The counter band on rows 61-62 is solid colour-11 (no centre hole) so
    the ring test excludes it."""
    H, W = len(grid), len(grid[0])
    out: set[Cell] = set()
    seen: set[Cell] = set()
    for r in range(min(H - 2, 60)):
        for c in range(W - 2):
            if (r, c) in seen:
                continue
            if (
                grid[r][c] == _REFILL_COLOR
                and grid[r][c + 1] == _REFILL_COLOR
                and grid[r + 1][c] == _REFILL_COLOR
                and grid[r + 1][c + 2] == _REFILL_COLOR
                and grid[r + 1][c + 1] != _REFILL_COLOR
            ):
                cxs = [x for x in xs if x <= c]
                cys = [y for y in ys if y <= r]
                if cxs and cys:
                    out.add((max(cxs), max(cys)))
                for dr in range(3):
                    for dc in range(3):
                        seen.add((r + dr, c + dc))
    return out


# ════════════════════════════════════════════════════════════════════════
# L7 (Fog): proximity partial-observability + a MOVING rotation changer on a
# VERTICAL track. `render_interface` paints every pixel > 20px (Euclidean) from
# the avatar centre with the fog colour (== `_GOAL_BORDER`), so only a radius-20
# disc renders truthfully. The static maze is REVEALED across a push-wall-aware
# exploration sweep (accumulating memory), the single mover's full track is
# captured from a "full-view" observation post (a column-adjacent cell that sees
# the whole track) via a REFILL-CHAINED loiter, and the L5-class joint BFS then
# plans a death-free open-loop sequence. Gated on the fog signature so L1-L6 are
# byte-identical. See the LS20 wiki page (2026-07-19) for the full derivation.
# ════════════════════════════════════════════════════════════════════════

_L7_FOG_MIN = 600  # colour-5 pixel count above which the frame is fogged (L7).
_L7_FOG_RADIUS = 20.0
_L7_LIFE = _STEP_FULL // _STEP_DECR
_L7_EXPLORE_CAP = 700
_L7_SEARCH_CAP = 12_000_000
_NB4 = ((0, -1), (0, 1), (-1, 0), (1, 0))


def _l7_fog_count(grid: Grid) -> int:
    return sum(1 for row in grid for v in row if v == _GOAL_BORDER)


def _l7_cell_vis(cx: int, cy: int, ax: int, ay: int) -> bool:
    """True if lattice cell (cx,cy) is fully inside the radius-20 fog disc around
    the avatar sprite centre — all four corners within range."""
    import math

    ccx, ccy = ax + 1.5, ay + 1.5
    return all(
        math.dist((cy + dy, cx + dx), (ccy, ccx)) <= _L7_FOG_RADIUS
        for dx in (0, 4)
        for dy in (0, 4)
    )


def _l7_parse_disc(grid: Grid, mem: dict[str, Any]) -> Cell | None:
    """Accumulate the truthful (disc-interior) cells into ``mem``: walls / floor /
    goal(+req) / static changers / refills / push-walls / token. Floor and refill
    classifications are STICKY (a fog-edge wall misread never overwrites floor; a
    collected refill stays a refill location — restored on death). Returns the
    avatar cell, or ``None`` when the frame has no parseable avatar."""
    avatar = _find_avatar(grid)
    if avatar is None:
        return None
    ax, ay = avatar
    ox, oy = ax % _CELL, ay % _CELL
    mem["ox"], mem["oy"] = ox, oy
    tok = _decode_token(grid)
    if tok is not None:
        mem["token"] = tok
    static: dict[Cell, str] = mem["static"]
    for (sx, sy, dx, dy) in _detect_pushwalls_pixel(grid):
        if _l7_cell_vis(sx, sy, ax, ay):
            mem["pushwalls"][(sx, sy)] = (dx, dy)
    for (rx, ry) in _find_refill_sprites(grid):
        c = _snap_to_lattice(rx, ry, ox, oy)
        if _l7_cell_vis(c[0], c[1], ax, ay):
            static[c] = "refill"
    xs = list(range(ox, len(grid[0]) - _CELL + 1, _CELL))
    ys = list(range(oy, len(grid) - _CELL + 1, _CELL))
    for x in xs:
        for y in ys:
            if not _l7_cell_vis(x, y, ax, ay):
                continue
            hh = _cell_counts(grid, x, y)
            dom = hh.most_common(1)[0][0]
            if y < _PLAYABLE_MAX_ROW and dom == _GOAL_BORDER and sum(hh.get(c, 0) for c in _PALETTE) >= 3:
                static[(x, y)] = "goal"
                mem["goal"] = (x, y)
                if mem["goal_req"] is None:
                    r = _decode_goal_preview(grid, x, y)
                    if r:
                        mem["goal_req"] = r
                continue
            kind = _classify_changer(hh, dom) if y < _PLAYABLE_MAX_ROW else None
            if kind is not None:
                mem["changers"][kind].add((x, y))
                if static.get((x, y)) not in ("refill", "goal"):
                    static[(x, y)] = "floor"
            elif dom == _FLOOR_COLOR:
                if static.get((x, y)) not in ("refill", "goal"):
                    static[(x, y)] = "floor"
            elif dom == _WALL_COLOR:
                if static.get((x, y)) != "floor":
                    static[(x, y)] = "wall"
    static[avatar] = "floor"
    return avatar


def _l7_fresh_rot(grid: Grid, avatar: Cell, xm: int) -> list[Cell]:
    """The mover's CURRENT rot-icon cell(s) read FRESH from this frame at column
    ``xm`` (unpolluted by accumulated memory). L7 has exactly one mover and no
    static rot-changer, so this returns its single current cell (or []/many when
    it is partly fogged — the caller records only when exactly one is seen)."""
    out: list[Cell] = []
    ax, ay = avatar
    for y in range(0, _PLAYABLE_MAX_ROW, _CELL):
        if not _l7_cell_vis(xm, y, ax, ay):
            continue
        hh = _cell_counts(grid, xm, y)
        dom = hh.most_common(1)[0][0]
        if _classify_changer(hh, dom) == "rot":
            out.append((xm, y))
    return out


def _l7_apply_push(cell: Cell, pushwalls: dict[Cell, Cell], fj: frozenset[Cell]) -> Cell:
    ax, ay = cell
    for (sx, sy), (pdx, pdy) in pushwalls.items():
        if ax < sx + _CELL and sx < ax + _CELL and ay < sy + _CELL and sy < ay + _CELL:
            dist = _l5_carry_dist(fj, sx, sy, pdx, pdy, _CELL, _CELL)
            if dist > 0:
                return (ax + pdx * _CELL * dist, ay + pdy * _CELL * dist)
            break
    return (ax, ay)


def _l7_nav(
    pss: set[Cell],
    walls: frozenset[Cell],
    pushwalls: dict[Cell, Cell],
    fj: frozenset[Cell],
    refills: set[Cell],
    goal: Cell | None,
    start: Cell,
    targets: set[Cell],
    life: int,
) -> int | None:
    """Life + push-wall + refill-aware BFS to any target; first action or None.
    Push-wall slides are applied so routing avoids the deflection zone (the naive
    shortest path deflects off the y<=30 push-walls and never reaches the column)."""
    from collections import deque

    if not targets:
        return None
    seen = {(start, life, frozenset())}
    queue: deque[tuple[Cell, int, frozenset[Cell], list[int]]] = deque([(start, life, frozenset(), [])])
    while queue:
        cell, lf, taken, path = queue.popleft()
        if cell in targets and path:
            return path[0]
        if lf <= 0:
            continue
        for aid, (dx, dy) in _MOVES.items():
            nb = (cell[0] + dx * _CELL, cell[1] + dy * _CELL)
            if nb in walls or nb == goal or nb not in pss:
                continue
            nb = _l7_apply_push(nb, pushwalls, fj)
            if nb not in pss:
                continue
            nl, nt = lf - 1, taken
            if nb in refills and nb not in taken:
                nl, nt = _L7_LIFE, taken | {nb}
            if nl < 0:
                continue
            key = (nb, nl, nt)
            if key in seen:
                continue
            seen.add(key)
            queue.append((nb, nl, nt, path + [aid]))
    return None


def _l7_step(maze: dict[str, Any], s: tuple, action: int) -> tuple:
    """One engine step for L7. ``s`` =
    ``(ax, ay, sh, co, ro, steps, taken, mstate)`` where ``mstate`` = ``(mx, my,
    mdir)`` is the vertical mover's cell + `npdjlrkhsg` direction."""
    ax, ay, sh, co, ro, steps, taken, mst = s
    dx, dy = _MOVES[action]
    prov = _l6_mover_step(maze["track"], *mst)
    nx, ny = ax + dx * _CELL, ay + dy * _CELL
    matched = (nx, ny) == maze["goal"] and (sh, co, ro) == maze["goal_req"]
    if (nx, ny) in maze["hard_walls"] or ((nx, ny) == maze["goal"] and not matched):
        return s
    ax, ay = nx, ny
    kind = maze["static_changers"].get((ax, ay))
    if (ax, ay) == (prov[0], prov[1]):
        kind = "rot"
    if kind == "rot":
        ro = (ro + 1) % 4
    elif kind == "color":
        co = (co + 1) % 4
    elif kind == "shape":
        sh = (sh + 1) % 6
    nsteps = steps - 1
    if (ax, ay) in maze["refills"] and (ax, ay) not in taken:
        nsteps = maze["step_full"]
        taken = taken | {(ax, ay)}
    if nsteps >= 0:
        for (sx, sy), (pdx, pdy) in maze["pushwalls"].items():
            if ax < sx + _CELL and sx < ax + _CELL and ay < sy + _CELL and sy < ay + _CELL:
                dist = _l5_carry_dist(maze["fjzuynaokm"], sx, sy, pdx, pdy, _CELL, _CELL)
                if dist > 0:
                    ax += pdx * _CELL * dist
                    ay += pdy * _CELL * dist
                    break
    return (ax, ay, sh, co, ro, nsteps, taken, prov)


def _l7_frontier(mem: dict[str, Any], pss: set[Cell]) -> set[Cell]:
    """Revealed floor cells with an unrevealed in-arena neighbour (the exploration
    frontier under fog)."""
    static = mem["static"]
    out: set[Cell] = set()
    for c in pss:
        for dx, dy in _NB4:
            nb = (c[0] + dx * _CELL, c[1] + dy * _CELL)
            if nb not in static and 4 <= nb[0] < 60 and 0 <= nb[1] < _PLAYABLE_MAX_ROW:
                out.add(c)
                break
    return out


def _l7_new_mem() -> dict[str, Any]:
    return {
        "static": {},
        "goal": None,
        "goal_req": None,
        "changers": {"shape": set(), "color": set(), "rot": set()},
        "pushwalls": {},
        "token": None,
        "ox": 4,
        "oy": 0,
    }


def _l7_bfs(maze: dict[str, Any], start: tuple) -> list[int] | None:
    """Death-free joint BFS to stand on the goal with a matching token, life- and
    refill-aware, over the L7 pixel sim (single goal + 2 static changers + 1
    vertical mover + push-walls)."""
    from collections import deque

    goal, req = maze["goal"], maze["goal_req"]

    def won(st: tuple) -> bool:
        return (st[0], st[1]) == goal and (st[2], st[3], st[4]) == req

    if won(start):
        return []
    seen = {start}
    queue: deque[tuple[tuple, list[int]]] = deque([(start, [])])
    exp = 0
    while queue and exp < _L7_SEARCH_CAP:
        s, path = queue.popleft()
        exp += 1
        if s[5] <= 0:
            continue
        for aid in (1, 2, 3, 4):
            ns = _l7_step(maze, s, aid)
            if ns[5] < 0 or ns == s or ns in seen:
                continue
            if won(ns):
                return path + [aid]
            seen.add(ns)
            queue.append((ns, path + [aid]))
    return None


# ════════════════════════════════════════════════════════════════════════
# Joint BFS over (cell, shape, color, rotation, steps_left, refills_taken).
# ════════════════════════════════════════════════════════════════════════


def _solve(parsed: dict[str, Any]) -> list[int] | None:
    """Shortest action sequence from the parsed start to standing on the goal
    with a matching token, life-budget- and refill-aware. Single continuous
    life-chain (deaths reset all progress, so a death-free plan is sought);
    refills top the budget back to ``_STEP_FULL // _STEP_DECR`` actions.
    Returns ``None`` when unreachable within the expansion cap."""
    from collections import deque

    full = _STEP_FULL // _STEP_DECR
    goal = parsed["goal"]
    req = parsed["goal_req"]
    changers = parsed["changers"]
    refills = parsed["refills"]
    passable = parsed["passable"]
    pushwalls = parsed.get("pushwalls", {})
    sh, co, ro = parsed["token"]
    start = (parsed["avatar"], sh, co, ro, full, frozenset())
    if start[0] == goal and (sh, co, ro) == req:
        return []

    seen = {start}
    queue: deque[tuple[tuple[Any, ...], list[int]]] = deque([(start, [])])
    expansions = 0
    while queue and expansions < _SEARCH_EXPANSIONS:
        (pos, sh, co, ro, steps, taken), path = queue.popleft()
        expansions += 1
        if steps <= 0:
            continue
        px, py = pos
        for aid, (dx, dy) in _MOVES.items():
            npos = (px + dx * _CELL, py + dy * _CELL)
            if npos not in passable:
                continue
            # Stepping onto a push-wall collision cell slides the avatar in the
            # push direction until the next cell is a wall or the goal (the
            # engine stops the push before goal cells). The destination effect
            # then applies at the landing cell.
            push = pushwalls.get(npos)
            if push is not None:
                pdx, pdy = push
                while True:
                    slid = (npos[0] + pdx * _CELL, npos[1] + pdy * _CELL)
                    if slid in passable and slid != goal:
                        npos = slid
                    else:
                        break
            nsh, nco, nro, nsteps, ntaken = sh, co, ro, steps - 1, taken
            kind = changers.get(npos)
            if kind == "rot":
                nro = (nro + 1) % 4
            elif kind == "color":
                nco = (nco + 1) % 4
            elif kind == "shape":
                nsh = (nsh + 1) % 6
            if npos in refills and npos not in taken:
                nsteps = full
                ntaken = taken | {npos}
            if nsteps < 0:
                continue
            if npos == goal and (nsh, nco, nro) != req:
                continue  # goal is blocking until the token matches
            nxt = (npos, nsh, nco, nro, nsteps, ntaken)
            if nxt in seen:
                continue
            if npos == goal and (nsh, nco, nro) == req:
                return path + [aid]
            seen.add(nxt)
            queue.append((nxt, path + [aid]))
    return None


# ════════════════════════════════════════════════════════════════════════
# Fallback: frame-keyed transition-graph frontier explorer (R56 substrate).
# ════════════════════════════════════════════════════════════════════════


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    r0, c0, r1, c1 = region["bbox"]
    h, w = r1 - r0 + 1, c1 - c0 + 1
    thin_h = max(1, int(height * _THIN_FRACTION))
    thin_w = max(1, int(width * _THIN_FRACTION))
    edge = max(1, int(height * _EDGE_FRACTION))
    edge_w = max(1, int(width * _EDGE_FRACTION))
    if h <= thin_h and (w >= width * _SPAN_FRACTION or r0 <= edge - 1 or r1 >= height - edge):
        return True
    if w <= thin_w and (h >= height * _SPAN_FRACTION or c0 <= edge_w - 1 or c1 >= width - edge_w):
        return True
    return False


class _Explorer:
    """Frame-keyed transition-graph frontier explorer, BFS-from-start over the
    discovered edges (the R56 substrate; clears L1 alone in ~606 actions)."""

    def __init__(self) -> None:
        self._transitions: list[tuple[StateKey, int, StateKey]] = []
        self._tried_from: dict[StateKey, set[int]] = {}
        self._start_key: StateKey | None = None
        self._plan: list[int] = []
        self._plan_expected: list[StateKey] = []
        self._pending_action: int | None = None
        self._pending_key: StateKey | None = None

    def on_level_up(self) -> None:
        self._transitions = []
        self._tried_from = {}
        self._start_key = None
        self._plan = []
        self._plan_expected = []
        self._pending_action = None
        self._pending_key = None

    def choose(self, grid: Grid, move_ids: list[int]) -> int:
        cur_key = self._state_key(grid)
        if self._start_key is None:
            self._start_key = cur_key
        self._observe_result(cur_key)
        action = self._decide(cur_key, move_ids)
        self._pending_action = action
        self._pending_key = cur_key
        return action

    def _state_key(self, grid: Grid) -> StateKey:
        if not grid:
            return frozenset()
        height, width = len(grid), len(grid[0])
        bg = most_common_color(grid)
        regions = find_regions(grid, background=bg)
        return frozenset(
            (r["color"], r["size"], *r["bbox"])
            for r in regions
            if not _is_hud_band(r, height, width)
        )

    def _observe_result(self, cur_key: StateKey) -> None:
        action = self._pending_action
        from_key = self._pending_key
        self._pending_action = None
        self._pending_key = None
        if action is None or from_key is None:
            return
        self._transitions.append((from_key, action, cur_key))
        self._tried_from.setdefault(from_key, set()).add(action)

    def _decide(self, cur_key: StateKey, move_ids: list[int]) -> int:
        successors = self._successors()
        if self._plan_expected and self._plan_expected[0] == cur_key:
            self._plan_expected.pop(0)
            return self._plan.pop(0)
        self._plan = []
        self._plan_expected = []
        target = self._shallowest_frontier(move_ids, successors)
        if target is not None:
            target_key, from_start = target
            if cur_key == target_key:
                return self._untried(cur_key, move_ids)[0]
            anchor = self._start_key if cur_key == self._start_key else cur_key
            route = (
                from_start
                if anchor == self._start_key
                else configuration_path(
                    cur_key, lambda k: k == target_key, successors, max_states=_FRONTIER_SEARCH_BUDGET
                )
            )
            if route:
                return self._launch(anchor, route, successors)
        untried_here = self._untried(cur_key, move_ids)
        if untried_here:
            return untried_here[0]
        return move_ids[0]

    def _shallowest_frontier(self, move_ids, successors):
        if self._start_key is None:
            return None

        def goal_test(key: StateKey) -> bool:
            return bool(self._untried(key, move_ids))

        path = configuration_path(
            self._start_key, goal_test, successors, max_states=_FRONTIER_SEARCH_BUDGET
        )
        if path is None:
            return None
        target_key = self._replay(self._start_key, path, successors)
        if target_key is None:
            return None
        return target_key, path

    def _replay(self, anchor: StateKey, actions, successors) -> StateKey | None:
        cur = anchor
        for action in actions:
            edges = dict(successors(cur))
            if action not in edges:
                return None
            cur = edges[action]
        return cur

    def _launch(self, anchor: StateKey, plan, successors) -> int:
        self._plan = list(plan)
        expected = [anchor]
        cur = anchor
        for action in plan[:-1]:
            cur = dict(successors(cur))[action]
            expected.append(cur)
        self._plan_expected = expected
        self._plan_expected.pop(0)
        return self._plan.pop(0)

    def _untried(self, key: StateKey, move_ids: list[int]) -> list[int]:
        tried = self._tried_from.get(key, set())
        return [a for a in move_ids if a not in tried]

    def _successors(self):
        edges: dict[StateKey, dict[int, StateKey]] = {}
        for from_key, action, to_key in self._transitions:
            edges.setdefault(from_key, {})[action] = to_key

        def successors(key: StateKey):
            return list(edges.get(key, {}).items())

        return successors


# ════════════════════════════════════════════════════════════════════════
# Adapter: offline reconstruction (open-loop) first, explorer fallback.
# ════════════════════════════════════════════════════════════════════════


class Adapter(GameAdapter):
    """Offline maze-reconstruction + joint-BFS + open-loop plan per level,
    gating to the frame-keyed explorer when the parse or search fails."""

    GAME_ID = GAME_ID

    @classmethod
    def _detect_mechanic(cls, latest_frame: Any) -> bool:
        """A token-matching maze: movement-only controls AND a parseable single-goal level.

        1. **Movement only.** The mechanic offers ACTION1-4 and nothing else — no click,
           no interact, no undo. MEASURED across the 25 public games, that alone narrows
           to three candidates (ls20, tr87, tu93).
        2. **The level parses.** `_parse` reconstructs avatar, goal, carried token and
           goal preview from a settled frame and returns None on any of its named
           gate-outs (no avatar / no goal / undecodable token or preview / more than one
           goal), so "does this board read as a token-matching maze" is exactly the
           question detection needs to ask.
        """
        simple_ids, has_click = available_action_ids(latest_frame)
        if has_click or sorted(simple_ids) != [1, 2, 3, 4]:
            return False
        return _parse(canonical_layer(latest_frame)) is not None

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True
        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1
        self._plan: list[int] = []
        self._plan_committed = False  # tried (and either planned or failed) this level
        self._plan_failed = False  # this level fell back to the explorer
        self._probes = 0  # settle probes issued at a stale transition frame
        self._explorer = _Explorer()
        # L5 moving-changer path. ``_mover_watch_cell`` watches a rot-changer for
        # motion while the static plan drains (zero L1-L4 cost); once motion is
        # seen, ``_l5_armed`` gates the pixel path, whose observation state is
        # ``_l5_state`` (None -> "observing" -> "done") + ``_l5_obs`` (mover cells).
        self._mover_watch_cell: Cell | None = None
        self._mover_checks = 0
        self._l5_armed = False
        self._l5_state: str | None = None
        self._l5_obs: list[Cell] = []
        # L6 multi-goal path: observation of the 3 phase-synced movers by KIND.
        self._l6_state: str | None = None
        self._l6_visited: dict[str, set[Cell]] = {}
        self._l6_order: dict[str, list[Cell]] = {}
        self._l6_obs_moves = 0
        self._l6_stable = 0
        self._l6_prev_av: Cell | None = None
        self._l6_band_prev: int | None = None
        self._l6_decr: int | None = None
        # L7 (Fog) path: reveal-then-loiter-then-plan, gated on the fog signature.
        self._l7_mem: dict[str, Any] = _l7_new_mem()
        self._l7_phase: str | None = None  # None -> explore -> loiter -> plan -> done/failed
        self._l7_xm: int | None = None
        self._l7_obs_y: set[int] = set()
        self._l7_rot_seq: list[Cell] = []
        self._l7_saw_rev = {"min": False, "max": False}
        self._l7_consumed: set[Cell] = set()
        self._l7_prev_band: int | None = None
        self._l7_m0: Cell | None = None
        self._l7_explore_steps = 0

    # ── harness contract ─────────────────────────────────────────────────
    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._plan = []
            self._plan_committed = False
            self._plan_failed = False
            self._probes = 0
            self._mover_watch_cell = None
            self._mover_checks = 0
            self._l5_armed = False
            self._l5_state = None
            self._l5_obs = []
            self._l6_state = None
            self._l6_visited = {}
            self._l6_order = {}
            self._l6_obs_moves = 0
            self._l7_mem = _l7_new_mem()
            self._l7_phase = None
            self._l7_xm = None
            self._l7_obs_y = set()
            self._l7_rot_seq = []
            self._l7_saw_rev = {"min": False, "max": False}
            self._l7_consumed = set()
            self._l7_prev_band = None
            self._l7_m0 = None
            self._l7_explore_steps = 0
            self._explorer._pending_action = None
            self._explorer._pending_key = None
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._reset_level(-1)
            return reset_action()

        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._reset_level(levels)

        self._step += 1
        grid = canonical_layer(latest_frame)
        simple_ids, _a6 = available_action_ids(latest_frame)
        move_ids = sorted(a for a in simple_ids if a in (1, 2, 3, 4))
        if not move_ids:
            return simple_action(simple_ids[0]) if simple_ids else reset_action()

        # 1. Drain a committed open-loop plan. While the static plan drains, WATCH
        #    the rot-changer cell (zero action cost): if it moves, this is the L5
        #    moving-changer level — abandon the (desyncing) static plan and arm the
        #    pixel path; if it stays put over a few checks it is a static level
        #    (L1-L4) and the plan drains normally, untouched.
        if self._plan:
            if self._mover_watch_cell is not None:
                cur_rot = _detect_rot_cell(grid)
                if cur_rot is not None and cur_rot != self._mover_watch_cell:
                    self._plan = []
                    self._mover_watch_cell = None
                    self._l5_armed = True
                    self._l5_state = None
                    self._l5_obs = []
                    self._plan_committed = False
                elif cur_rot is not None:
                    self._mover_checks += 1
                    if self._mover_checks >= _MOVER_WATCH_CHECKS:
                        self._mover_watch_cell = None
                    return simple_action(self._plan.pop(0))
                else:
                    return simple_action(self._plan.pop(0))
            else:
                return simple_action(self._plan.pop(0))

        # 1.25 L7 fog gate. The fog paints everything outside a radius-20 disc with
        #     colour-5 (== the goal-border colour), so a fogged frame reads as a
        #     giant goal to the L1-L6 parsers — they MUST be bypassed. The gate
        #     (colour-5 pixel count) cleanly separates L7 (~3000) from L1-L6 (<=482,
        #     measured), so this can never fire on an earlier level: L1-L6 stay
        #     byte-identical. The L7 path reveals the maze, captures the mover's
        #     vertical track from a full-view post via a refill-chained loiter, and
        #     joint-BFS plans; on any failure it returns None -> explorer floor.
        if _l7_fog_count(grid) > _L7_FOG_MIN:
            l7_action = self._try_l7(grid, move_ids)
            if l7_action is not None:
                return simple_action(l7_action)
            return simple_action(self._explorer.choose(grid, move_ids))

        # 1.5 L6 multi-goal + moving-changer path (gated on >=2 goals, which only
        #     L6 has — L1-L5 are single-goal and fall straight through). Observes
        #     the three phase-synced movers, then joint-BFS plans multi-goal
        #     coverage. On not-L6 or any failure it returns None and the existing
        #     single-goal paths run, so the 5/7 floor is untouched.
        if not self._plan_committed and not self._plan_failed:
            l6_action = self._try_l6(grid, move_ids)
            if l6_action is not None:
                return simple_action(l6_action)

        # 2. L5 pixel path — only once the moving changer has been confirmed. It
        #    observes the mover cycle, reconstructs the pixel maze and joint-BFS
        #    plans a death-free open-loop sequence.
        if self._l5_armed and not self._plan_failed:
            l5_action = self._try_l5(grid, move_ids)
            if l5_action is not None:
                return simple_action(l5_action)
            # L5 confirmed but unsolved -> drop to the explorer floor (the static
            # reconstruction can't model the mover, so re-trying it would loop).
            self._l5_armed = False
            self._plan_failed = True

        # 3. Try the offline reconstruction once per level (until it commits a
        #    plan or the settle probes run out), planning from the CURRENT
        #    (post-probe) frame so a stale transition frame is absorbed.
        if not self._plan_committed and not self._plan_failed:
            parsed = _parse(grid)
            if parsed is not None:
                plan = _solve(parsed)
                if plan:
                    self._plan = list(plan)
                    self._plan_committed = True
                    self._arm_mover_watch(grid)
                    return simple_action(self._plan.pop(0))
            if self._probes < _PROBE_CAP:
                # Stale/unsettled transition frame: probe once (any move), then
                # re-parse+plan from the resulting settled frame next turn.
                self._probes += 1
                return simple_action(move_ids[0])
            self._plan_failed = True

        # 4. Fallback: frame-keyed explorer for this level.
        return simple_action(self._explorer.choose(grid, move_ids))

    def _arm_mover_watch(self, grid: Grid) -> None:
        """Arm the rot-changer motion watch when the just-committed static level
        could be the L5 moving-changer level (push-walls present + a rot-changer).
        On any other level this leaves the watch disarmed (zero L1-L4 impact)."""
        parsed = _parse_l5_maze(grid)
        if parsed is None or not parsed["pushwalls"]:
            self._mover_watch_cell = None
            return
        rots = [c for c, k in parsed["changers"].items() if k == "rot"]
        self._mover_watch_cell = rots[0] if rots else None
        self._mover_checks = 0

    def _try_l5(self, grid: Grid, move_ids: list[int]) -> int | None:
        """The armed L5 path (called only after the moving changer is confirmed).
        Observes the mover cell over a few SETTLED frames to learn its track +
        phase, then reconstructs the pixel maze and joint-BFS plans a death-free
        open-loop sequence. Returns an observation move, the first plan action, or
        ``None`` when it gives up (caller drops to the explorer floor)."""
        if self._l5_state == "done":
            return None
        parsed = _parse_l5_maze(grid)
        if parsed is None:
            return move_ids[0]  # unsettled: settle (we know this is L5)
        if self._l5_state is None:
            self._l5_state = "observing"
            self._l5_obs = []
        rots = [c for c, k in parsed["changers"].items() if k == "rot"]
        if rots:
            self._l5_obs.append(rots[0])
        xs = [c[0] for c in self._l5_obs]
        enough = len(self._l5_obs) >= 5 and len(set(xs)) >= 3
        if enough or len(self._l5_obs) >= _L5_OBS_CAP:
            self._l5_state = "done"
            if len(set(xs)) < 2:
                return None
            plan = self._plan_l5(grid, parsed)
            if plan:
                self._plan = plan
                self._plan_committed = True
                return self._plan.pop(0)
            return None
        # issue a safe observation move (a successful move advances the mover)
        ax, ay = parsed["avatar"]
        for act in (4, 3, 2, 1):
            dx, dy = _MOVES[act]
            nb = (ax + dx * _CELL, ay + dy * _CELL)
            if nb in parsed["passable"] and nb != parsed["goal"] and nb not in parsed["hard_walls"]:
                return act
        return move_ids[0]

    def _plan_l5(self, grid: Grid, parsed: dict[str, Any]) -> list[int] | None:
        """Build the pixel maze from the observed mover cycle + the settled
        parse, then joint-BFS a death-free plan (or ``None``)."""
        obs = self._l5_obs
        xs = [c[0] for c in obs]
        my = obs[0][1]
        track = tuple(sorted(set(range(min(xs), max(xs) + 1, _CELL))))
        mx = obs[-1][0]
        mdir = 1
        for j in range(len(obs) - 1, 0, -1):
            if obs[j][0] != obs[j - 1][0]:
                mdir = 1 if obs[j][0] > obs[j - 1][0] else 3
                break
        changers = {c: k for c, k in parsed["changers"].items() if not (k == "rot" and c == (mx, my))}
        maze = {
            "hard_walls": parsed["hard_walls"],
            "goal": parsed["goal"],
            "goal_req": parsed["goal_req"],
            "changers": changers,
            "refills": parsed["refills"],
            "pushwalls": parsed["pushwalls"],
            "fjzuynaokm": frozenset(set(parsed["hard_walls"]) | {parsed["goal"]}),
            "mover_track": track,
            "mover_my": my,
            "step_full": _L5_LIFE,
        }
        sh, co, ro = parsed["token"]
        ax, ay = parsed["avatar"]
        start = (ax, ay, sh, co, ro, _read_life(grid), frozenset(), mx, mdir)
        return _l5_bfs(maze, start)

    def _try_l6(self, grid: Grid, move_ids: list[int]) -> int | None:
        """L6 multi-goal path. Gated on >=2 goals (only L6 has them). Observes
        the three phase-synced movers (rot/shape/color, one per kind icon) until
        their tracks stop growing, then joint-BFS plans multi-goal coverage.
        Returns an observation move, the first plan action, or ``None`` (not L6,
        or gave up -> single-goal paths / explorer floor run)."""
        if self._l6_state == "done":
            return None
        parsed = _parse_l6_maze(grid)
        if parsed is None:
            return move_ids[0] if self._l6_state == "observing" else None
        if self._l6_state is None:
            if len(parsed["goals"]) < 2:
                self._l6_state = "done"  # single-goal level -> not L6
                return None
            self._l6_state = "observing"
            self._l6_visited = {"rot": set(), "shape": set(), "color": set()}
            self._l6_order = {"rot": [], "shape": [], "color": []}
            self._l6_obs_moves = 0
            self._l6_stable = 0
            self._l6_prev_av = None
            self._l6_band_prev = None
            self._l6_decr = None
        av = parsed["avatar"]
        band = _band_count(grid)
        if self._l6_prev_av is None or av != self._l6_prev_av:  # last move succeeded
            grew = False
            for c, k in parsed["changers"].items():
                if k in self._l6_visited:
                    if c not in self._l6_visited[k]:
                        grew = True
                    self._l6_visited[k].add(c)
                    self._l6_order[k].append(c)
            self._l6_stable = 0 if grew else self._l6_stable + 1
            if self._l6_band_prev is not None and self._l6_decr is None:
                delta = self._l6_band_prev - band
                if delta > 0:  # a clean (non-refill) successful move reveals decr
                    self._l6_decr = delta
        self._l6_prev_av = av
        self._l6_band_prev = band
        if (self._l6_obs_moves >= 6 and self._l6_stable >= _L6_STABLE_NEED) or self._l6_obs_moves >= _L6_OBS_CAP:
            self._l6_state = "done"
            plan = self._plan_l6(grid, parsed)
            if plan:
                self._plan = plan
                self._plan_committed = True
                return self._plan.pop(0)
            return None
        # issue a safe successful move (advances all movers once)
        self._l6_obs_moves += 1
        for act in (4, 3, 2, 1):
            dx, dy = _MOVES[act]
            nb = (av[0] + dx * _CELL, av[1] + dy * _CELL)
            if nb in parsed["passable"] and nb not in parsed["hard_walls"] and nb not in parsed["goals"]:
                return act
        return move_ids[0]

    def _plan_l6(self, grid: Grid, parsed: dict[str, Any]) -> list[int] | None:
        """Build the L6 pixel maze from the observed mover tracks + the settled
        multi-goal parse, then joint-BFS a death-free coverage plan (or None)."""
        kinds = [k for k in ("rot", "shape", "color") if self._l6_visited[k]]
        if not kinds:
            return None
        tracks = [frozenset(self._l6_visited[k]) for k in kinds]
        curmov: list[tuple[int, int, int]] = []
        for k in kinds:
            seq = self._l6_order[k]
            pos = seq[-1]
            d = 1
            for j in range(len(seq) - 1, 0, -1):
                dd = _l6_dir_from(seq[j - 1], seq[j])
                if dd is not None:
                    d = dd
                    break
            curmov.append((pos[0], pos[1], d))
        decr = self._l6_decr or _STEP_DECR
        maze = {
            "goals": parsed["goals"],
            "reqs": parsed["reqs"],
            "hard_walls": parsed["hard_walls"],
            "refills": parsed["refills"],
            "pushwalls": parsed["pushwalls"],
            "fjzuynaokm": frozenset(set(parsed["hard_walls"]) | set(parsed["goals"])),
            "mover_kinds": kinds,
            "mover_tracks": tracks,
            "step_full": _STEP_FULL // decr,
        }
        ax, ay = parsed["avatar"]
        sh, co, ro = parsed["token"]
        start = (ax, ay, sh, co, ro, _band_count(grid) // decr, frozenset(),
                 tuple(curmov), frozenset())
        return _l6_bfs(maze, start)

    def _try_l7(self, grid: Grid, move_ids: list[int]) -> int | None:
        """The L7 (Fog) path: reveal the maze under proximity fog, capture the
        single vertical mover's full track from a full-view observation post via a
        refill-chained loiter, then joint-BFS a death-free plan and commit it
        open-loop. Returns an action, or ``None`` when it gives up (caller drops to
        the explorer floor). Called only on fogged frames (gate guarantees L7)."""
        mem = self._l7_mem
        av = _l7_parse_disc(grid, mem)
        if av is None:
            return move_ids[0]  # unsettled/animation frame: settle
        if self._l7_phase is None:
            self._l7_phase = "explore"
        band = _band_count(grid) // _STEP_DECR
        static = mem["static"]
        refills = {c for c, t in static.items() if t == "refill"}
        walls = frozenset(c for c, t in static.items() if t == "wall")
        goal = mem["goal"]
        fj = frozenset(walls | ({goal} if goal else set()))
        pss = {c for c, t in static.items() if t in ("floor", "goal", "refill")}
        # track consumed refills (faithful plan anchor); a death restores all
        if self._l7_prev_band is not None and band > self._l7_prev_band:
            if av in refills:
                self._l7_consumed.add(av)
            elif band >= _L7_LIFE - 1:
                self._l7_consumed.clear()
        self._l7_prev_band = band
        if mem["changers"]["rot"]:
            self._l7_xm = min(c[0] for c in mem["changers"]["rot"])
        xm = self._l7_xm

        for _ in range(4):  # allow at most a few phase transitions per turn
            if self._l7_phase == "explore":
                self._l7_explore_steps += 1
                if self._l7_explore_steps > _L7_EXPLORE_CAP:
                    return None
                if xm is not None:
                    posts = {c for c in pss if c[0] == xm - _CELL}
                    if av in posts and len(_l7_fresh_rot(grid, av, xm)) == 1:
                        self._l7_phase = "loiter"
                        continue
                    tgt = posts or _l7_frontier(mem, pss)
                else:
                    tgt = _l7_frontier(mem, pss)
                nav = _l7_nav(pss, walls, mem["pushwalls"], fj, refills, goal, av, tgt, band)
                if nav is None and band <= 3 and refills:
                    nav = _l7_nav(pss, walls, mem["pushwalls"], fj, refills, goal, av, refills, band)
                if nav is not None:
                    return nav
                for aid, (dx, dy) in _MOVES.items():
                    nb = (av[0] + dx * _CELL, av[1] + dy * _CELL)
                    if nb not in static and 4 <= nb[0] < 60 and 0 <= nb[1] < _PLAYABLE_MAX_ROW:
                        return aid
                return move_ids[0]

            if self._l7_phase == "loiter":
                posts = {c for c in pss if c[0] == xm - _CELL}
                rot = _l7_fresh_rot(grid, av, xm)
                if av in posts and band > 3:
                    if len(rot) == 1:
                        mc = rot[0]
                        self._l7_obs_y.add(mc[1])
                        if not self._l7_rot_seq or self._l7_rot_seq[-1] != mc:
                            self._l7_rot_seq.append(mc)
                        seq = self._l7_rot_seq
                        if len(seq) >= 3:
                            a, b, c = seq[-3][1], seq[-2][1], seq[-1][1]
                            if a < b > c:
                                self._l7_saw_rev["max"] = True
                            if a > b < c:
                                self._l7_saw_rev["min"] = True
                    if len(self._l7_obs_y) >= 2 and self._l7_saw_rev["min"] and self._l7_saw_rev["max"]:
                        self._l7_phase = "plan"
                        continue
                    for aid, (dx, dy) in _MOVES.items():
                        nb = (av[0] + dx * _CELL, av[1] + dy * _CELL)
                        if nb in posts and nb != goal:
                            return aid
                    return move_ids[0]
                tgt = refills if (band <= 3 and refills) else posts
                nav = _l7_nav(pss, walls, mem["pushwalls"], fj, refills, goal, av, tgt, band)
                return nav if nav is not None else move_ids[0]

            if self._l7_phase == "plan":
                if not self._l7_obs_y:
                    return None
                track = frozenset(
                    (xm, y) for y in range(min(self._l7_obs_y), max(self._l7_obs_y) + 1, _CELL)
                )
                fullview = {
                    c
                    for c in pss
                    if c[0] == xm - _CELL
                    and all(_l7_cell_vis(t[0], t[1], c[0], c[1]) for t in track)
                }
                if not fullview:
                    return None
                if av not in fullview:
                    nav = _l7_nav(pss, walls, mem["pushwalls"], fj, refills, goal, av, fullview, band)
                    return nav if nav is not None else move_ids[0]
                rot = _l7_fresh_rot(grid, av, xm)
                if len(rot) != 1:
                    for aid, (dx, dy) in _MOVES.items():
                        nb = (av[0] + dx * _CELL, av[1] + dy * _CELL)
                        if nb in fullview and nb != goal:
                            return aid
                    return move_ids[0]
                if self._l7_m0 is None:
                    self._l7_m0 = rot[0]
                    for aid, (dx, dy) in _MOVES.items():
                        nb = (av[0] + dx * _CELL, av[1] + dy * _CELL)
                        if nb in fullview and nb != goal:
                            return aid
                    return move_ids[0]
                m1 = rot[0]
                mdir = 0
                if self._l7_m0 != m1:
                    v = (m1[0] - self._l7_m0[0], m1[1] - self._l7_m0[1])
                    for d, (dx, dy) in _L6_DIRVEC.items():
                        if (dx * _CELL, dy * _CELL) == v:
                            mdir = d
                            break
                if mem["token"] is None or goal is None or mem["goal_req"] is None:
                    return None
                maze = {
                    "goal": goal,
                    "goal_req": mem["goal_req"],
                    "hard_walls": walls,
                    "refills": frozenset(refills),
                    "static_changers": {
                        **{c: "shape" for c in mem["changers"]["shape"]},
                        **{c: "color" for c in mem["changers"]["color"]},
                    },
                    "track": track,
                    "pushwalls": dict(mem["pushwalls"]),
                    "fjzuynaokm": frozenset(walls | {goal}),
                    "step_full": _L7_LIFE,
                }
                sh, co, ro = mem["token"]
                start = (av[0], av[1], sh, co, ro, band, frozenset(self._l7_consumed), (m1[0], m1[1], mdir))
                plan = _l7_bfs(maze, start)
                if plan:
                    self._plan = list(plan)
                    self._plan_committed = True
                    self._l7_phase = "done"
                    return self._plan.pop(0)
                self._l7_phase = "failed"
                return None
            return None
        return move_ids[0]

    def _reset_level(self, levels: int) -> None:
        self._levels_seen = levels
        self._plan = []
        self._plan_committed = False
        self._plan_failed = False
        self._probes = 0
        self._mover_watch_cell = None
        self._mover_checks = 0
        self._l5_armed = False
        self._l5_state = None
        self._l5_obs = []
        self._l6_state = None
        self._l6_visited = {}
        self._l6_order = {}
        self._l6_obs_moves = 0
        self._l7_mem = _l7_new_mem()
        self._l7_phase = None
        self._l7_xm = None
        self._l7_obs_y = set()
        self._l7_rot_seq = []
        self._l7_saw_rev = {"min": False, "max": False}
        self._l7_consumed = set()
        self._l7_prev_band = None
        self._l7_m0 = None
        self._l7_explore_steps = 0
        self._explorer.on_level_up()
