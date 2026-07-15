"""script25 quarantined adapter: R11L (click-driven drag-assembly puzzle).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/R11L.md`` (read for reference, not imported) records
R11L as a "sequence" game the legacy ``seq_repeat`` / ``seq_search`` cleared
1/6, and ``docs/r57_win_condition_typology_20260715.md`` flags it as an
unresolved T7/T8 case whose observable signature is "~11 consecutive
ACTION6". Reading the game source offline
(``environment_files/r11l/*/r11l.py``; dev-time only, the adapter reads only
frames at runtime) resolves it: R11L is neither a repeat-count nor a
symbol-rewrite game — it is a CLICK-DRIVEN DRAG-ASSEMBLY puzzle.

**Actual mechanic (drag-assembly) — the ONLY action is ACTION6 (click)**:

- The board has one or more CREATURES. Each creature is a BODY plus a set
  of LEGS (small clickable pieces) and a matching TARGET nest. The engine
  keeps a single SELECTED leg (auto-selected nearest the origin at level
  start).
- Clicking ON a leg SELECTS it. Clicking on empty space MOVES the selected
  leg to that point (an animated drag), UNLESS the destination collides with
  a HAZARD region (then the move is refused). Crucially, a body is
  repositioned to the CENTROID of its own legs after each move — so to bring
  a creature's body onto its target you must arrange ALL of that creature's
  legs so their average position sits on the target.
- WIN fires when EVERY creature's body overlaps its target nest (read from
  the engine's ``winning`` gate — all bodies on targets — but NEVER
  hardcoded here; the adapter reacts only to the engine's own WIN state).
- Repeated bad placements (5 collisions) or an exhausted action budget end
  the attempt in GAME_OVER. The "~11 consecutive ACTION6" the typology saw
  is simply the select/place click pairs for a few legs on level 0.

**Why a generic click-frontier explorer, not a bespoke solver**: solving
the assembly requires the CENTROID-arrangement geometry (place each
creature's legs so their mean lands on its target) AND a per-creature
leg→target grouping that the frame does not label — reconstructing both
faithfully would rebuild the game's own bookkeeping, the game-specific
"second brain" the R56 codex verdict
(``docs/r56_codex_toolbase_verdict_20260715.md``) forbids in the namespace.
Instead this adapter generalises the same transition-graph frontier
explorer the other movement adapters use, with the ACTION ALPHABET reduced
to a BOUNDED, frame-derived set of clicks — the centroid of every salient
(non-background, non-HUD) region — rather than the unbounded 64x64 click
space:

  - Every board state is canonicalised into a hashable key
    (:func:`admorphiq.kernels.canonical_key`, ``mode="exact"``) after the
    edge-pinned HUD bands are masked (:func:`admorphiq.kernels.find_regions`
    finds them).
  - The candidate clicks AT a state are that frame's salient region
    centroids (recorded per state so routing knows each state's options).
  - Every observed ``(state, click_cell, next_state)`` transition is
    recorded; the policy takes an untried click at the current state, else
    routes (:func:`admorphiq.kernels.transition_shortest_path`) to the
    nearest visited state with an untried click (a small BFS over the same
    recorded edges, :meth:`_nearest_untried`).

**Measured result — BANKED at 1/6 (ties the legacy card more efficiently)**:
- ``--max-actions 1000``: 1/6 levels — L0 cleared in 238 clicks vs a
  22-click human baseline, game_score 0.000407 (deterministic). The legacy
  `seq_search` needed 505 clicks for the same L0.
- ``--max-actions 30000`` (raised ``giveup``): still 1/6 — the explorer
  never advances past level 0, confirming deeper multi-creature levels are a
  hard plateau for blind click search, not merely a budget shortfall.

Even with the click alphabet bounded to region centroids, the assembly is a
CONTINUOUS centroid-placement problem: the winning leg configuration is
rarely any single salient centroid, so a frontier search over "click an
existing region" cannot construct it except by luck, and each wrong
placement risks one of the 5 collision strikes before GAME_OVER. The honest
characterisation matches the codex verdict's guidance: the lever is LEARNED
OBJECT DYNAMICS (which click drags which leg, how the body follows) +
configuration-space planning toward the target, not blind click search.
Reopen pointer: a generic "click-drag operator" motion kernel that infers,
from observed click→leg-move transitions, the drag map and the body-follows-
centroid rule, letting ``configuration_path`` plan a target-covering leg
arrangement — the same shape as the codex-proposed ``learn_point_operators``
/ ``plan_overwrites`` pair, generalised to click-drag assembly.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments the board into salient
    click candidates and masks the edge-pinned HUD bands.
  - :func:`admorphiq.kernels.canonical_key` hashes the masked board into a
    stable state key.
  - :func:`admorphiq.kernels.transition_shortest_path` routes over the
    incrementally-discovered transition graph to the nearest state with an
    untried click.
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

GAME_ID = "r11l"

Cell = tuple[int, int]
Region = dict[str, Any]
Grid = tuple[tuple[int, ...], ...]

# Per-level safety cap, mirroring every other script25 adapter's giveup
# convention so the harness never spins forever inside this one.
_GIVEUP_DEFAULT = 4000

_HUD_SPAN_FRACTION = 0.85
_HUD_THICKNESS_FRACTION = 0.06

# Salient click candidates: a region small enough to be an interactive piece
# (a leg / target marker), not a big background slab. Purely a "is this a
# clickable thing" size gate, no game-specific pixel count.
_MIN_CAND_SIZE = 1
_MAX_CAND_SIZE = 400


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    """A thin strip spanning most of one axis, OR pinned to a frame edge —
    R11L renders a step-counter column at the frame edge; masking it keeps
    the state key stable across the ticking count."""
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


def _candidates(grid: Grid, hud: set[Cell], bg: int) -> list[Cell]:
    """Deterministic list of click-target cells: the rounded centroid of
    every salient (non-background, non-HUD) region within the size gate.
    Sorted for reproducibility so the frontier search is deterministic."""
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
    states, with the action alphabet bounded to salient region centroids.
    Composed from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        # A 5th bad placement or an exhausted budget ends the attempt in
        # GAME_OVER; restart and keep the learned graph so each life
        # compounds (the board layout didn't change).
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        self._pending_click: Cell | None = None
        self._pending_key: Any | None = None

        # Incrementally-discovered transition graph over masked board states.
        # ``_transitions`` is the flat triple list transition_shortest_path
        # consumes; ``_edges`` is the same graph as an adjacency map kept in
        # step so _nearest_untried's BFS stays linear. ``_cands_at`` records
        # each visited state's own click candidates (a state's alphabet is
        # frame-derived, so routing must remember what was clickable there).
        # All reset on level-up, kept across a mid-level GAME_OVER restart.
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
            cands = _candidates(grid, hud, bg)
            self._cands_at[cur_key] = cands
        if not cands:
            # No salient click target this frame -- nothing a click policy
            # can compose from. Idle with a reset rather than crash.
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

        # Fully explored under current knowledge -- click any candidate
        # rather than stall.
        return cands[0]

    def _nearest_untried(self, start_key: Any) -> Any | None:
        """BFS over the KNOWN transition graph from ``start_key``; return the
        nearest visited state (including ``start_key``) that still has a
        candidate click not yet in ``_tried_from``, or None if every
        reachable state is fully explored. Hand-rolled rather than
        :func:`admorphiq.kernels.reachable_frontier` for the same reason
        ``admorphiq.adapters25.tu93`` gives (its universe is observed edges
        only, so it cannot surface a state's never-clicked candidate)."""
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
