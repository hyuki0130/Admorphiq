"""script25 quarantined adapter: TN36 (bit-panel programming puzzle).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/TN36.md`` records TN36 as a programming puzzle the legacy
`strat_tn36_puzzle` cleared 7/7 by CHEATING — calling the game-internal
``frame.zpzcmabenn(val)`` to set the bit program directly (0/7 generic).
``docs/r57_win_condition_typology_20260715.md`` mines it as a programming
puzzle whose single `ACTION6` "run" re-simulates a whole trajectory. This
adapter is the frame-only attempt; it is BANKED, with the ENCODING MAP fully
documented below (the team's explicit ask for this game).

**Encoding map — decoded from the game source (offline, dev-time only;
``environment_files/tn36/*/tn36.py``)**:

- ``available_actions = [6]`` — click only. The 64x64 frame IS the display
  (ACTION6 x/y are validated to 0..63, so display == grid, scale 1).
- **Bit panels**: a program VALUE is a binary number over a row of bit cells
  — ``yfozlxgytl.kbswvermjk == sum(1 << i for i, cell in enumerate(cells)
  if cell.on)``. ``zpzcmabenn(v)`` (the cheat) just sets each cell from a
  bit of ``v``. A level has a SEQUENCE of such panels (``thofkgziyd``), i.e.
  a multi-instruction program, not one number.
- **Opcode semantics**: running the program replays a trajectory —
  ``skgnriqpob(i)`` applies instruction ``i`` as a position + rotation +
  scale transform of the player sprite (``ahmihpsrbh`` / ``sowhkehyjk`` /
  ``oekthfoxly``). So each panel value is an opcode over movement transforms.
- **Deadline**: a colour-9 wall bar (top row) advances one cell LEFT on
  EVERY click (``yrddcregck.nmslpsqyvb`` — halved cadence at level_index>=5);
  the level LOSES when it passes the goal (``fisapprjnh`` false). Budget is
  generous on L0 (>60 clicks measured) but every bit-toggle costs deadline.
- **Run / win**: a click on the PLAY region sets ``nwjrtjcxpo`` (running);
  the trajectory animates (the huge per-run frame churn the typology saw);
  WIN when the player reaches the goal (``yxabhsirzl``).

**Measured layout (live probe, this build — corrected against the wiki's
prior refactor findings)**: the interactive controls ARE frame-reachable at
scale 1. The BIT ROW is at grid ``y=44`` (cells at cols ~21, 26, 31, 36, 41)
— clicking one toggles it (colour 5 <-> 1, a ~3-pixel change, plus the
1-pixel deadline advance). The PLAY button is at grid rows 51-59, cols 32-40
— clicking it runs the program (a ~70-pixel churn). The big colour-4 cells
at rows 9-28 are the program DISPLAY, not the toggles (an earlier sweep that
filtered for large diffs missed the tiny bit-toggle; corrected here). So a
generic agent CAN toggle bits and press play.

**Measured wall**: even with the controls reachable, blind frontier search
does not clear (0/7), matching the wiki's two prior frame-only refactor
attempts (detection worked, enumeration scored 0/7). TN36 is a STATEFUL
MULTI-FRAME interpreter: the single visible bit row is ONE program frame,
and the winning program is a SEQUENCE of frame values (v1 L0 gold is
``[3,3,3,3,3]`` — five frames of value 3), advanced by play clicks. The
space of multi-frame bit programs is combinatorial (R6's "bit-panel
combinatorial search infeasible"), the per-click deadline caps attempts, and
a blind click-frontier neither learns the bit->movement opcode nor composes
the multi-frame sequence. This is the firm wall.

**Why a generic click-frontier explorer anyway**: it is the honest,
measurable generic baseline (it will press PLAY and attempt every salient
cell), and it composes namespace-safe kernels exactly like
``admorphiq.adapters25.r11l``:

  - :func:`admorphiq.kernels.find_regions` enumerates the salient click
    candidates and masks the edge-pinned HUD.
  - :func:`admorphiq.kernels.canonical_key` hashes the masked board.
  - :func:`admorphiq.kernels.transition_shortest_path` routes over the
    incrementally-discovered transition graph to the nearest state with an
    untried click (:meth:`_nearest_untried`, the same
    ``admorphiq.adapters25.tu93`` rationale for not using
    :func:`admorphiq.kernels.reachable_frontier`).

**Measured result — BANKED at 0/7**:
- ``--max-actions 1000``: 0/7 levels, game_score 0.0 (deterministic). The
  explorer presses PLAY and clicks every salient cell, but with no reachable
  bit-toggle it can only run the all-zero program, which never reaches the
  goal. Below the cheating legacy 7/7 (which set the program via a
  game-internal call); 0/7 is the honest frame-only floor for this game.

Reopen pointer: (1) learn the bit->movement OPCODE by setting one bit at
``y=44``, pressing play, and measuring the player's displacement vector per
frame; (2) model the multi-frame program (each play advances a frame; detect
the frame count needed to reach the goal); (3) solve the target trajectory
with :func:`admorphiq.kernels.gf2_solve` / :func:`admorphiq.kernels.derive_rewrites`
over the (likely linear) opcode structure, then set + play each frame within
the deadline. The controls are reachable; the missing piece is the
game-model (opcode learning + multi-frame planning) between detection and
exploitation — exactly the "game-model phase" the wiki's prior attempts
flagged as the gap.

Composition from ``admorphiq.kernels``: find_regions, canonical_key,
transition_shortest_path (as above).
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
    most_common_color,
    reset_action,
    state_name,
)
from admorphiq.kernels import canonical_key, find_regions, transition_shortest_path

GAME_ID = "tn36"

Cell = tuple[int, int]
Region = dict[str, Any]
Grid = tuple[tuple[int, ...], ...]

_GIVEUP_DEFAULT = 4000

_HUD_SPAN_FRACTION = 0.85
_HUD_THICKNESS_FRACTION = 0.06

_MIN_CAND_SIZE = 1
_MAX_CAND_SIZE = 400


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    """A thin strip spanning most of one axis, OR pinned to a frame edge —
    catches TN36's top-row deadline bar (which advances every click) so it
    does not fragment the state key on every step."""
    r0, c0, r1, c1 = region["bbox"]
    h, w = r1 - r0 + 1, c1 - c0 + 1
    thickness = max(1, int(height * _HUD_THICKNESS_FRACTION))
    thickness_w = max(1, int(width * _HUD_THICKNESS_FRACTION))
    full_width_thin = w >= width * _HUD_SPAN_FRACTION and h <= thickness
    full_height_thin = h >= height * _HUD_SPAN_FRACTION and w <= thickness_w
    edge_pinned_thin = (h <= thickness and (r0 == 0 or r1 == height - 1)) or (
        w <= thickness_w and (c0 == 0 or c1 == width - 1)
    )
    return full_width_thin or full_height_thin or edge_pinned_thin


def _hud_cells(grid: Grid, bg: int) -> set[Cell]:
    height, width = len(grid), len(grid[0])
    cells: set[Cell] = set()
    for region in find_regions(grid, background=bg):
        if _is_hud_band(region, height, width):
            cells |= region["cells"]
    return cells


def _mask_hud(grid: Grid, hud: set[Cell]) -> Grid:
    if not hud:
        return grid
    bg = most_common_color(grid)
    return tuple(
        tuple(bg if (r, c) in hud else grid[r][c] for c in range(len(grid[0])))
        for r in range(len(grid))
    )


def _click_candidates(grid: Grid, hud: set[Cell], bg: int) -> list[Cell]:
    """Deterministic list of click-target cells: the rounded centroid of
    every salient (non-background, non-HUD) region within the size gate
    (bit cells + the play button)."""
    height, width = len(grid), len(grid[0])
    cells: list[Cell] = []
    seen: set[Cell] = set()
    for region in find_regions(grid, background=bg):
        if _is_hud_band(region, height, width):
            continue
        if not (_MIN_CAND_SIZE <= region["size"] <= _MAX_CAND_SIZE):
            continue
        cr, cc = region["centroid"]
        cell = (int(round(cr)), int(round(cc)))
        if 0 <= cell[0] < height and 0 <= cell[1] < width and cell not in seen and cell not in hud:
            seen.add(cell)
            cells.append(cell)
    return sorted(cells)


class Adapter(GameAdapter):
    """Generic click-frontier exploration over HUD-masked frame-canonical
    states (click alphabet = salient region centroids), composed from
    admorphiq.kernels. See the module docstring's BANKED encoding map."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        self._pending_click: Cell | None = None
        self._pending_key: Any | None = None

        self._transitions: list[tuple[Any, Cell, Any]] = []
        self._edges: dict[Any, dict[Cell, Any]] = {}
        self._tried_from: dict[Any, set[Cell]] = {}
        self._cands_at: dict[Any, list[Cell]] = {}

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._on_restart()
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._pending_click = None
            self._pending_key = None
            self._levels_seen = -1
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._on_level_up(levels)

        self._step += 1
        bg = most_common_color(grid)
        hud = _hud_cells(grid, bg)
        cur_key = canonical_key(_mask_hud(grid, hud), mode="exact")
        self._observe_result(cur_key)

        cands = self._cands_at.get(cur_key)
        if cands is None:
            cands = _click_candidates(grid, hud, bg)
            self._cands_at[cur_key] = cands
        if not cands:
            self._pending_click = None
            self._pending_key = None
            return reset_action()

        cell = self._decide(cur_key, cands)
        self._pending_click = cell
        self._pending_key = cur_key
        return click_action(x=cell[1], y=cell[0])

    # ── level / restart bookkeeping ─────────────────────────────────────

    def _on_level_up(self, levels: int) -> None:
        self._levels_seen = levels
        self._pending_click = None
        self._pending_key = None
        self._transitions = []
        self._edges = {}
        self._tried_from = {}
        self._cands_at = {}

    def _on_restart(self) -> None:
        self._pending_click = None
        self._pending_key = None

    # ── measurement: record the observed transition ─────────────────────

    def _observe_result(self, cur_key: Any) -> None:
        click = self._pending_click
        prev_key = self._pending_key
        self._pending_click = None
        self._pending_key = None
        if click is None or prev_key is None:
            return
        self._transitions.append((prev_key, click, cur_key))
        self._edges.setdefault(prev_key, {})[click] = cur_key
        self._tried_from.setdefault(prev_key, set()).add(click)

    # ── planning ─────────────────────────────────────────────────────────

    def _decide(self, cur_key: Any, cands: list[Cell]) -> Cell:
        tried = self._tried_from.get(cur_key, set())
        untried = [c for c in cands if c not in tried]
        if untried:
            return untried[0]

        target = self._nearest_untried(cur_key)
        if target is not None and target != cur_key:
            path = transition_shortest_path(self._transitions, cur_key, target)
            if path:
                return path[0]  # type: ignore[return-value]

        return cands[0]

    def _nearest_untried(self, start_key: Any) -> Any | None:
        """BFS over the KNOWN transition graph from ``start_key``; return the
        nearest visited state (including ``start_key``) that still has an
        untried candidate click, or None if fully explored. Hand-rolled
        rather than :func:`admorphiq.kernels.reachable_frontier` for the same
        reason ``admorphiq.adapters25.tu93`` gives (its universe is observed
        edges only, so it cannot surface a never-tried candidate)."""
        visited = {start_key}
        queue: deque[Any] = deque([start_key])
        while queue:
            state = queue.popleft()
            cands = self._cands_at.get(state)
            if cands is not None:
                tried = self._tried_from.get(state, set())
                if any(c not in tried for c in cands):
                    return state
            for _cell, nxt in self._edges.get(state, {}).items():
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        return None
