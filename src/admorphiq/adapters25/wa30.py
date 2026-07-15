"""script25 quarantined adapter: WA30 (pick-carry-drop delivery puzzle).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/WA30.md`` (read for reference, not imported): a single
WORKER moves with ACTION1-4 and uses ACTION5 as a context interact — picking
up a box and delivering it to a goal zone. WIN = every box on a goal cell. The
mechanic (read offline, dev-time only; the adapter reads only frames at
runtime) is a facing-and-carry delivery: everything sits on a coarse logical
grid (the worker steps one logical cell per action), a box attaches when the
worker reaches it and follows the worker, and dropping it on a goal cell
satisfies that goal.

**This build — carry-aware delivery composition**: the mechanic (measured
offline, dev-time only) is a facing-and-carry delivery — a box picked while
the worker FACES it (ACTION5 at distance one cell in the facing direction)
attaches and then FOLLOWS the worker at a fixed offset equal to that facing
vector; dropping (ACTION5) leaves the box at its carried position; the level
wins when every box sits on a goal cell. The adapter detects the worker,
boxes, and goal-pad slots from the frame and composes
:func:`admorphiq.kernels.plan_carry_delivery` (the generic offset-routing
delivery planner: to seat a fixed-offset follower on a cell ``C`` the worker
routes to ``C - offset``, so both pickup and delivery legs are pure
translations, chained min-cost via
:func:`admorphiq.kernels.grid_shortest_path`). The only game-specific step it
adds on top is a facing nudge before each pickup interact (a blocked step into
the box that sets rotation). Measured: L0 clears in 30 actions vs a 71-action
human baseline (super-human, level score 1.0) — the first generic WA30 clear.

**Fallback**: when roles can't be detected or no delivery plan routes (deeper
levels with more boxes, angled walls, or a carry geometry the fixed
facing-up offset can't serve), the adapter falls back to the generic
transition-graph frontier exploration the previous build used, so it never
regresses below that baseline.

**L1 divergence (banked 2026-07-15, see WA30.md)**: L1 adds a second,
AUTONOMOUS agent (a ``kdweefinfi``-tagged sprite; measured colour 12) that
picks up and delivers boxes ON ITS OWN every step, independent of the player —
a live single-step probe shows it moving on every action regardless of the
command. The board is therefore non-stationary and the static precomputed
carry plan desyncs; the true worker is the colour-14 ``wbmdvjhthc`` mover but
fixing detection alone does not clear L1. Clearing it needs a reactive
cooperative (multi-agent, replan-every-step) delivery planner — a new
composition beyond this static-plan model. L1 stays on the graph fallback.

**Why namespace-safe**: the adapter assigns roles (which cluster is the
worker, which are boxes, which cells are goals) and declares the mechanic
hypothesis (delivery), but the assignment, routing, and path conversion all
live in ``admorphiq.kernels`` — no hardcoded coordinates, colours, or bespoke
search here.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments the board (role detection,
    HUD masking).
  - :func:`admorphiq.kernels.plan_delivery` plans the pick->deliver chain over
    the detected roles and a passability grid.
  - :func:`admorphiq.kernels.canonical_key` /
    :func:`admorphiq.kernels.transition_shortest_path` drive the graph
    fallback.
"""

from __future__ import annotations

from collections import deque
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
from admorphiq.kernels import (
    canonical_key,
    find_regions,
    plan_carry_delivery,
    transition_shortest_path,
)

GAME_ID = "wa30"

Cell = tuple[int, int]
Region = dict[str, Any]
Grid = tuple[tuple[int, ...], ...]

_GIVEUP_DEFAULT = 4000
_HUD_SPAN_FRACTION = 0.85
_HUD_THICKNESS_FRACTION = 0.06

# The board is rendered at 4 px per logical cell (the worker steps one logical
# cell = 4 px per action); planning runs on the downscaled logical grid.
_CELL = 4


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    """A thin strip spanning most of one axis, OR pinned to a frame edge —
    catches WA30's bottom-row step counter."""
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


def _mask_hud(grid: Grid) -> Grid:
    if not grid or not grid[0]:
        return grid
    height, width = len(grid), len(grid[0])
    bg = most_common_color(grid)
    hud: set[Cell] = set()
    for region in find_regions(grid, background=bg):
        if _is_hud_band(region, height, width):
            hud |= region["cells"]
    if not hud:
        return grid
    return tuple(
        tuple(bg if (r, c) in hud else grid[r][c] for c in range(width))
        for r in range(height)
    )


def _logical(cell_bbox: tuple[int, int, int, int]) -> Cell:
    """The logical-grid cell of a region's bbox centre (frame px / _CELL)."""
    r0, c0, r1, c1 = cell_bbox
    return ((r0 + r1) // 2 // _CELL, (c0 + c1) // 2 // _CELL)


class Adapter(GameAdapter):
    """Compose the delivery/subgoal planner over detected worker/box/goal
    roles; fall back to generic transition-graph frontier exploration.
    Composed from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True
        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        # phase: "plan" (compute + execute a delivery chain once), "graph".
        self._phase = "plan"
        self._plan_queue: list[int] = []
        self._planned = False

        # graph-fallback state.
        self._pending_action: int | None = None
        self._pending_key: Any | None = None
        self._transitions: list[tuple[Any, int, Any]] = []
        self._edges: dict[Any, dict[int, Any]] = {}
        self._tried_from: dict[Any, set[int]] = {}

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._on_restart()
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._reset_for_new_env()
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._on_level_up(levels)

        self._step += 1

        simple_ids, _action6_ok = available_action_ids(latest_frame)
        act_ids = sorted(a for a in simple_ids if a in (1, 2, 3, 4, 5))
        if not act_ids:
            return simple_action(simple_ids[0]) if simple_ids else reset_action()

        if self._phase == "plan":
            return self._plan_step(grid, act_ids)
        return self._graph_step(grid, act_ids)

    # ── level / restart bookkeeping ─────────────────────────────────────

    def _on_level_up(self, levels: int) -> None:
        self._levels_seen = levels
        self._phase = "plan"
        self._planned = False
        self._plan_queue = []
        self._pending_action = None
        self._pending_key = None
        self._transitions = []
        self._edges = {}
        self._tried_from = {}

    def _on_restart(self) -> None:
        self._pending_action = None
        self._pending_key = None
        if self._phase == "plan":
            self._planned = False
            self._plan_queue = []

    def _reset_for_new_env(self) -> None:
        self._levels_seen = -1
        self._on_level_up(-1)

    # ── phase 1: compute + execute the delivery chain ───────────────────

    def _plan_step(self, grid: Grid, act_ids: list[int]) -> GameAction:
        if not self._planned:
            self._planned = True
            self._build_plan(grid)
        if self._plan_queue:
            a = self._plan_queue.pop(0)
            return simple_action(a if a in act_ids else act_ids[0])
        self._phase = "graph"
        return self._graph_step(grid, act_ids)

    def _build_plan(self, grid: Grid) -> None:
        bg = most_common_color(grid)
        masked = _mask_hud(grid)
        regions = [r for r in find_regions(masked, background=bg) if not _is_hud_band(r, len(grid), len(grid[0]))]
        roles = self._detect_roles(regions)
        if roles is None:
            self._phase = "graph"
            return
        worker, boxes, goals = roles
        height = len(grid) // _CELL
        width = len(grid[0]) // _CELL
        # Passable everywhere except where a box currently sits (the worker
        # cannot stand on a box); goal cells are passable delivery spots.
        blocked = set(boxes)
        passable = [
            [(r, c) not in blocked for c in range(width)] for r in range(height)
        ]
        # Measured WA30 controls (game-specific, quarantine-legal): ACTION1-4
        # move the worker one logical cell up/down/left/right; ACTION5 is the
        # context pick/drop. The carried box FOLLOWS at a fixed offset equal to
        # the facing direction at pickup — picking while facing "up" seats the
        # box one cell ABOVE the worker (offset (-1, 0)) and it rides there.
        move_labels = {(-1, 0): 1, (1, 0): 2, (0, -1): 3, (0, 1): 4}
        carry_offset = (-1, 0)
        facing_action = move_labels[carry_offset]  # face the pickup before ACTION5
        plan = plan_carry_delivery(worker, boxes, goals, carry_offset, passable, move_labels, 5)
        if plan is None:
            self._phase = "graph"
            return
        # A pickup interact requires the worker to FACE the box first; insert a
        # facing move (a blocked step into the box that only sets rotation)
        # before every ODD interact (pickups). Deliveries (even interacts) drop
        # the carried box in place and need no facing.
        seq: list[int] = []
        interacts = 0
        for a in plan:
            if a == 5:
                interacts += 1
                if interacts % 2 == 1:
                    seq.append(facing_action)
                seq.append(5)
            else:
                seq.append(int(a))
        self._plan_queue = seq

    def _detect_roles(
        self, regions: list[Region]
    ) -> tuple[Cell, list[Cell], list[Cell]] | None:
        """Worker = the singleton marker colour (one region of a colour no
        other region shares); boxes = the small same-shape cluster class;
        goals = the logical cells of the largest remaining static region (the
        delivery pad). All in logical-grid coordinates. None when the roles
        can't be separated."""
        if not regions:
            return None
        by_color: dict[int, list[Region]] = {}
        for r in regions:
            by_color.setdefault(r["color"], []).append(r)
        # Worker: a colour owned by exactly one region (the mover).
        singletons = [regs[0] for regs in by_color.values() if len(regs) == 1]
        if not singletons:
            return None
        # Boxes: a same-colour class of 2+ regions that are all the SAME size
        # (a uniform repeated sprite), preferring the most populous such class.
        # This distinguishes the box class from an incidentally-shared colour
        # whose regions differ in size (e.g. sprite cores + a large pad border
        # both drawn in one colour).
        uniform = [
            (color, regs)
            for color, regs in by_color.items()
            if len(regs) >= 2 and len({r["size"] for r in regs}) == 1
        ]
        if not uniform:
            return None
        box_color, box_regs = max(uniform, key=lambda kv: (len(kv[1]), -kv[0]))
        boxes = [_logical(r["bbox"]) for r in box_regs]
        # Goal pad: the largest region whose colour is neither the box colour
        # nor a box-core colour, tiled into its logical cells.
        pad_candidates = [
            r for r in regions if r["color"] != box_color and _logical(r["bbox"]) not in boxes
        ]
        if not pad_candidates:
            return None
        pad = max(pad_candidates, key=lambda r: r["size"])
        goals = self._pad_cells(pad["bbox"], len(boxes))
        # Worker: the singleton nearest in size to a box (the mover, not the pad).
        worker_region = min(
            singletons, key=lambda r: (abs(r["size"] - box_regs[0]["size"]), r["bbox"])
        )
        worker = _logical(worker_region["bbox"])
        if not boxes or not goals:
            return None
        return worker, boxes, goals

    def _pad_cells(self, bbox: tuple[int, int, int, int], count: int) -> list[Cell]:
        """The distinct logical cells a delivery pad spans (its bbox sampled
        on the logical grid), capped at ``count`` (one per box)."""
        r0, c0, r1, c1 = bbox
        cells: list[Cell] = []
        seen: set[Cell] = set()
        r = r0
        while r <= r1:
            c = c0
            while c <= c1:
                lc = (r // _CELL, c // _CELL)
                if lc not in seen:
                    seen.add(lc)
                    cells.append(lc)
                c += _CELL
            r += _CELL
        return cells[:count] if count else cells

    # ── phase 2: generic transition-graph frontier fallback ─────────────

    def _graph_step(self, grid: Grid, act_ids: list[int]) -> GameAction:
        cur_key = canonical_key(_mask_hud(grid), mode="exact")
        self._observe_result(cur_key)
        action = self._decide(cur_key, act_ids)
        self._pending_action = action
        self._pending_key = cur_key
        return simple_action(action)

    def _observe_result(self, cur_key: Any) -> None:
        action = self._pending_action
        prev_key = self._pending_key
        self._pending_action = None
        self._pending_key = None
        if action is None or prev_key is None:
            return
        self._transitions.append((prev_key, action, cur_key))
        self._edges.setdefault(prev_key, {})[action] = cur_key
        self._tried_from.setdefault(prev_key, set()).add(action)

    def _decide(self, cur_key: Any, act_ids: list[int]) -> int:
        tried = self._tried_from.get(cur_key, set())
        untried = [a for a in act_ids if a not in tried]
        if untried:
            return untried[0]
        target = self._nearest_untried(cur_key, act_ids)
        if target is not None and target != cur_key:
            path = transition_shortest_path(self._transitions, cur_key, target)
            if path:
                return int(path[0])
        return act_ids[0]

    def _nearest_untried(self, start_key: Any, act_ids: list[int]) -> Any | None:
        """BFS over the KNOWN transition graph from ``start_key``; return the
        nearest state with an untried action, or None if fully explored.
        Hand-rolled rather than :func:`admorphiq.kernels.reachable_frontier`
        for the same reason ``admorphiq.adapters25.tu93`` gives."""
        visited = {start_key}
        queue: deque[Any] = deque([start_key])
        while queue:
            state = queue.popleft()
            tried_here = self._tried_from.get(state, set())
            if any(a not in tried_here for a in act_ids):
                return state
            for _action, nxt in self._edges.get(state, {}).items():
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        return None
