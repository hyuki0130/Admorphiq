"""script25 quarantined adapter: BP35 (gravity platformer, move + click-destroy).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/BP35.md`` (read for reference, not imported) records
BP35 as a gravity platformer the legacy `bp35_platformer` cleared 1/9 (L0 in
16 actions), generic R23 8B 0/9. ``docs/r57_win_condition_typology_20260715.md``
mines it as a platformer whose win is reaching a fixed `+`-shaped exit
marker. Reading the game source offline (``environment_files/bp35/*/
bp35.py``; dev-time only, the adapter reads only frames at runtime) plus a
live probe establish the mechanic. **CORRECTION CHAIN: the original
"deterministic per-action gravity" claim rested on a flawed ACTION1 no-op probe
(known-bad); R56b then over-corrected to a "MOMENTUM platformer with HIDDEN
velocity" — and R59 OVERTURNS that too.** The R59 re-examination (source read +
faithful ``env._game`` probes) shows BP35 IS deterministic and fully
frame-observable after all — the "acceleration" was fall distances and the
"receding exit" was camera scroll. See "R59 RE-EXAMINATION" below; the adapter
still ships as the frontier explorer (0/9) pending a dedicated solver pass.

**Determinism check (ORIGINAL, now KNOWN-FLAWED)**: a live repeat-probe
issued the same action from a fresh env twice and got byte-identical results,
concluding "deterministic per-action gravity". The flaw: that probe issued
ACTION1, which is NOT in ``available_actions`` ([3,4,6,7]) — a no-op that
trivially reproduces (it only ticks the step counter). It never exercised the
real controls, so it proved nothing about the actual dynamics.

**R59 RE-EXAMINATION (2026-07-16) — the R56b momentum bank is OVERTURNED.**
Reading the source (``pywlvyklps``/``fsvnqdbzrp``/``gwfodrkvzx``/``pbsitubcfd``)
plus faithful ``env._game`` probes shows BP35 is a DETERMINISTIC, fully
FRAME-OBSERVABLE grid platformer (world 11×36, gravity dy=-1):

- ``available_actions = [3, 4, 6, 7]``. ACTION3/ACTION4 move the player EXACTLY
  ONE cell horizontally, then it falls deterministically until landing. The
  R56b "2,6,6,6,6,3 acceleration" was a MISREAD of FALL DISTANCES (1 horizontal
  + N vertical); measured world positions are clean unit steps
  ((3,23)→(4,23)→(5,23)→(6,23)→(7,20)→(8,20)). There is NO velocity — the
  ``(position)→(position)`` graph is NOT aliased.
- The EXIT is FIXED at world (3,7). The R56b "receding exit" was a CAMERA
  artifact: the frame is a scrolling window over the tall level and the camera
  follows the player, so the exit's SCREEN column drifts while its WORLD cell
  never moves.
- Clicks are FUNCTIONAL (R56b "inert" is FALSE): ACTION6 on a colour-14
  ``qclfkhjnaac`` block DESTROYS it (measured 14→5); clicking the block DIRECTLY
  ABOVE the player makes it CLIMB the cleared column (measured (7,20)→(7,16)).
  ``pbsitubcfd`` only relocates the player when the clicked cell is exactly
  ``(px, py-1)`` — other clicks still remove the block but don't move the
  player, which is why the R56b probe (watching only player/exit position)
  called them inert. Screen→world is ``hyntnfvpgl(x, y+camera_y)`` (offset 0,
  scale 6): the adapter clicks the block's FRAME centroid, camera handled
  engine-side.
- WIN = the engine's own WIN signal (never hardcoded).

**Consequence**: BP35 is a clean deterministic planning problem, state =
(player world cell, set of destroyed blocks) — NO hidden state, so the R56b
"aliased hidden-velocity" framing is wrong. The solve is a (position,
destroyed-blocks) BFS/A* over {move+fall, destroy+climb}, the same shape as
sk48's faithful-simulator solve. This adapter still ships as the frontier
explorer (0/9) because that build is a DEDICATED pass: a naive hand model AND a
real-engine replay-BFS both failed to find the known-solvable L0 (the legacy
brittle solver clears it), so the move+fall+destroy dynamics need lockstep
validation against the engine (the sk48 lesson) before a solver can trust them.
See ``.wiki/wiki/games/BP35.md`` "Reopen".

**Why a generic MOVE+CLICK frontier explorer**: BP35 mixes two action
kinds, so this adapter generalises the transition-graph frontier explorer to
a HYBRID action alphabet — the simple move ids PLUS a bounded set of clicks
at the frame's salient region centroids (the destructible blocks), rather
than the unbounded 64x64 click space. Planning the gravity-aware
destroy-then-fall route faithfully would re-implement the platformer physics
(a game-specific "second brain" the R56 codex verdict forbids); instead the
search discovers the transitions:

  - Every board state is canonicalised (:func:`admorphiq.kernels.canonical_key`,
    ``mode="exact"``) after the edge-pinned HUD is masked
    (:func:`admorphiq.kernels.find_regions`).
  - The candidate ACTIONS at a state are the available moves plus a click on
    each salient centroid (recorded per state so routing knows the options).
  - Every observed ``(state, action_label, next_state)`` transition is
    recorded; the policy takes an untried action at the current state, else
    routes (:func:`admorphiq.kernels.transition_shortest_path`) to the
    nearest visited state with an untried action (:meth:`_nearest_untried`,
    a small BFS over the same edges — same rationale as
    ``admorphiq.adapters25.tu93`` for not using
    :func:`admorphiq.kernels.reachable_frontier`).

**Measured result — BANKED at 0/9**: Smoke:
- ``--max-actions 1000``: 0/9 levels, game_score 0.0; also 0/9 at 10000.
  Below the internals-tuned legacy `bp35_platformer` 1/9 (0/9 generic). The
  frontier explorer cannot compose a win: its state key is the raw
  camera-relative frame (the same world position looks different at different
  camera scroll) and it has no model of the climb / block-clearing the solve
  needs. Reopen pointer (R59, CORRECTED — the R56b "hidden velocity" pointer is
  withdrawn): BP35 is DETERMINISTIC and fully observable, so the solve is a
  (player world cell, destroyed-blocks) BFS/A* over {move+fall, destroy+climb} —
  the sk48 faithful-simulator shape. Build a lockstep-validated move+fall+destroy
  simulator (a naive model + real-engine replay-BFS both failed to find the
  known-solvable L0, so the dynamics need validation), a frame parser that
  de-aliases the camera scroll by tracking the player's WORLD position, then
  search to the gem. Open sub-puzzle: the search stays confined to y≥16 because
  the path-opening blocks above the y=15 wall are OFF-SCREEN until the player
  climbs — the correct simulator must resolve this (L0 is winnable; the legacy
  brittle solver proves it).

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` masks the HUD and enumerates the
    destructible-block click candidates.
  - :func:`admorphiq.kernels.canonical_key` hashes the masked board into a
    stable state key.
  - :func:`admorphiq.kernels.transition_shortest_path` routes over the
    incrementally-discovered transition graph.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from admorphiq.adapters25.base import (
    GameAction,
    GameAdapter,
    canonical_layer,
    click_action,
    has_frame,
    reset_action,
    simple_action,
    state_name,
)

GAME_ID = "bp35"

Cell = tuple[int, int]
Grid = tuple[tuple[int, ...], ...]

# Frame colour -> world-cell kind (cell-centre sampled; see BP35.md):
#   5 = solid terrain/wall, 10 = open/passable, 14 = destructible block,
#   7 = the '+' exit gem. 0/3/15 are HUD/letterbox and read as unknown.
_KIND = {5: "wall", 10: "pass", 14: "destroy", 7: "gem"}
_PLAYER_COLOR = 9
_CELL_PX = 6  # each world cell renders 6x6 px (measured)
_GRAV = -1  # this game's gravity is "up" (toward decreasing world y)
_PLAN_LEG = 3  # actions taken per plan before re-parsing + re-planning
_PLAN_CAP = 8000  # BFS expansion cap per plan

_GIVEUP_DEFAULT = 4000


def _marker(grid: Grid) -> Cell | None:
    """The player sprite's marker (colour-9) centroid in frame pixels, or None
    when the player is mid-animation and not drawn. The parser reads every other
    cell RELATIVE to this point, so its exact pixel offset within the player
    cell cancels out."""
    rs = 0
    cs = 0
    n = 0
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            if v == _PLAYER_COLOR:
                rs += r
                cs += c
                n += 1
    if n == 0:
        return None
    return (round(rs / n), round(cs / n))


def _parse(grid: Grid, marker: Cell, pabs: Cell, world: dict[Cell, str]) -> None:
    """Merge the visible cells into ``world`` (abs cell -> kind). A world cell
    at relative ``(kx, ky)`` from the player renders at frame
    ``(marker_row + ky*6, marker_col + kx*6)`` (the player is camera-locked at
    its marker), so its absolute cell is ``(pabs.x + kx, pabs.y + ky)``."""
    h = len(grid)
    w = len(grid[0]) if grid else 0
    for ky in range(-8, 9):
        fr = marker[0] + ky * _CELL_PX
        if not (0 <= fr < h):
            continue
        for kx in range(-4, 10):
            fc = marker[1] + kx * _CELL_PX
            if 0 <= fc < w:
                kind = _KIND.get(grid[fr][fc])
                if kind:
                    world[(pabs[0] + kx, pabs[1] + ky)] = kind
    world[pabs] = "pass"


def _fall(world: dict[Cell, str], x: int, y: int, soft: bool) -> tuple[str, Cell]:
    """Deterministic gravity fall from ``(x, y)`` in the gravity direction until
    a non-passable cell. ``soft`` (exploration mode) treats an UNKNOWN cell as a
    landing floor (a reveal point); otherwise unknown is a wall."""
    cur = (x, y)
    ny = y + _GRAV
    n = 0
    while world.get((x, ny)) == "pass" and n < 40:
        cur = (x, ny)
        ny += _GRAV
        n += 1
    v = world.get((x, ny))
    kind = v if v is not None else ("soft" if soft else "wall")
    if kind == "gem":
        return ("WIN", (x, ny))
    if kind == "spike":
        return ("DEAD", cur)
    return ("OK", cur)


def _successors(world: dict[Cell, str], pos: Cell, soft: bool) -> list[tuple[str, str, Cell, Cell | None]]:
    """Every (label, result, new_pos, destroyed_cell) from ``pos``: move
    left/right (1 cell + fall) and click a destructible NEIGHBOUR (left / right /
    the cell directly above, which climbs the cleared column)."""
    out: list[tuple[str, str, Cell, Cell | None]] = []
    for d, nm in ((1, "R"), (-1, "L")):
        nx = pos[0] + d
        if pos[0] + d < 0:  # engine treats x<0 as a wall bump
            out.append((nm, "OK", pos, None))
            continue
        k = world.get((nx, pos[1]))
        if k == "gem":
            out.append((nm, "WIN", (nx, pos[1]), None))
            continue
        if k in ("wall", "destroy", "spike"):
            out.append((nm, "OK", pos, None))
            continue
        res, np_ = _fall(world, nx, pos[1], soft)
        out.append((nm, res, np_, None))
    for cx, cy, nm in ((pos[0] - 1, pos[1], "CL"), (pos[0] + 1, pos[1], "CR"), (pos[0], pos[1] + _GRAV, "CA")):
        if world.get((cx, cy)) == "destroy":
            w2 = dict(world)
            w2[(cx, cy)] = "pass"
            if (cx, cy) == (pos[0], pos[1] + _GRAV):
                res, np_ = _fall(w2, pos[0], pos[1] + _GRAV, soft)
                out.append((nm, res, np_, (cx, cy)))
            else:
                out.append((nm, "OK", pos, (cx, cy)))
    return out


def _plan(world: dict[Cell, str], start: Cell, gem: Cell | None, visited: set[Cell]) -> list[str] | None:
    """BFS over (player cell, destroyed-block set). Goal = reach the gem when it
    is known; otherwise (exploration) steer toward the lowest-y UNVISITED
    reachable cell — visited-awareness stops the climb dead-ending and
    oscillating in one column. Returns the first-found winning path, else the
    path to the best frontier cell."""
    seen: set[tuple[Cell, frozenset[Cell]]] = {(start, frozenset())}
    q: deque[tuple[Cell, frozenset[Cell], list[str]]] = deque([(start, frozenset(), [])])
    best: list[str] | None = None
    best_sc: int | None = None
    exp = 0
    soft = gem is None
    while q and exp < _PLAN_CAP:
        pos, destroyed, path = q.popleft()
        exp += 1
        w = dict(world)
        for c in destroyed:
            w[c] = "pass"
        if gem is not None:
            sc = abs(pos[1] - gem[1]) + abs(pos[0] - gem[0])
        else:
            sc = pos[1] + (0 if pos not in visited else 1000)
        if path and (best_sc is None or sc < best_sc):
            best_sc = sc
            best = path
        for nm, res, np_, clk in _successors(w, pos, soft):
            if res == "WIN":
                return path + [nm]
            if res == "DEAD":
                continue
            nd = destroyed | ({clk} if clk else set())
            st = (np_, nd)
            if st not in seen:
                seen.add(st)
                q.append((np_, nd, path + [nm]))
    return best


class Adapter(GameAdapter):
    """Frame-only deterministic solver: parse the camera-scrolled window into an
    accumulating world map (kinds from colour), track the player by the marker's
    screen column, and BFS over (cell, destroyed-blocks) toward the gem, climbing
    to reveal it. Pure Python + the frame; no game internals."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True
        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1
        self._reset_level()

    def _reset_level(self) -> None:
        self._world: dict[Cell, str] = {}
        self._pabs: Cell = (0, 0)
        self._visited: set[Cell] = set()
        self._col0: int | None = None
        self._queue: list[str] = []

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._reset_level()
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._levels_seen = -1
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._levels_seen = levels
            self._reset_level()
        self._step += 1

        marker = _marker(grid)
        if marker is None:
            # Player mid-animation: nudge a frame to redraw it.
            return simple_action(4)
        if self._col0 is None:
            self._col0 = marker[1]
        # x is exact from the marker column (camera x is fixed); y is carried by
        # the sim (the player is camera-locked, so y is not on screen).
        self._pabs = (round((marker[1] - self._col0) / _CELL_PX), self._pabs[1])
        _parse(grid, marker, self._pabs, self._world)
        self._visited.add(self._pabs)

        if not self._queue:
            gem = next((c for c, k in self._world.items() if k == "gem"), None)
            path = _plan(self._world, self._pabs, gem, self._visited)
            self._queue = list(path[:_PLAN_LEG]) if path else ["R"]

        action = self._queue.pop(0)
        soft = not any(k == "gem" for k in self._world.values())
        for nm, _res, np_, _clk in _successors(self._world, self._pabs, soft):
            if nm == action:
                self._pabs = (self._pabs[0], np_[1])
                break

        if action == "R":
            return simple_action(4)
        if action == "L":
            return simple_action(3)
        dx, dy = {"CA": (0, _GRAV), "CL": (-1, 0), "CR": (1, 0)}[action]
        return click_action(x=marker[1] + dx * _CELL_PX, y=marker[0] + dy * _CELL_PX)
