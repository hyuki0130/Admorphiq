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
        self._explorer.on_level_up()
