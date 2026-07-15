"""script25 quarantined adapter: DC22 (button-barrier gated-maze navigation).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/DC22.md`` (read for reference, not imported). DC22 L0's
gold (20 actions, verified to replay to WIN on the live env) INTERLEAVES walk
and toggle: click A (a one-time REVEAL that opens a region) → walk → click B
(a SEESAW that opens one path segment while closing another) → walk → click A
again (an 8-cell BARRIER flip) → walk → goal. Three earlier plans were
falsified (reactive stuck-probe / parity-enumeration / decoupled
set-state-then-walk) because the win is neither reachability-triggered nor a
proactive flag: it is a PRODUCT-GRAPH gated maze where certain button clicks
mutate WHICH cells are walkable, and the walk + toggles are inseparable.

**Validated model (measured, dev-time only; runtime reads only frames)**: a
cell is a WALL iff its colour is a wall colour (learned from blocked moves —
colour 0 unrevealed + colour 4 closed barrier here, never hardcoded). Each
toggle button, clicked, mutates the wall-cell set:
- a REVEAL removes a fixed cell set from the walls permanently (one-time);
- a SEESAW / BARRIER toggles a fixed cell set's wall-membership each click
  (a symmetric-difference — measured as colour 4↔8 / 4↔9 swaps).
A toggle is learned by clicking it TWICE: cells changed on BOTH clicks are the
toggled (swap) set; cells changed on only the FIRST are the one-time reveal
set. The win is simply reaching the goal cell in SOME reachable
(cell, wall-set) product state.

**This build — compose the gated-maze planner**: once the avatar, goal, wall
colours, and ≥1 toggle are known, the adapter composes
:func:`admorphiq.kernels.plan_gated_path` (BFS over the product graph
``(cell, wall_set)``: move edges gated by the current wall set, toggle edges
mutating it) to emit the full interleaved walk+click plan, then executes it.
Measured: L0 clears in 20 actions vs a 59-action human baseline. Falls back to
optimistic walk-and-learn exploration while bootstrapping the model, so it
never regresses below reactive navigation.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments avatar / goal / buttons.
  - :func:`admorphiq.kernels.track_objects` identifies the avatar by motion.
  - :func:`admorphiq.kernels.frame_diff` measures a move's outcome and a
    button's effect (which cells it changes).
  - :func:`admorphiq.kernels.grid_shortest_path` drives the bootstrap
    optimistic walk; :func:`admorphiq.kernels.plan_gated_path` plans the
    interleaved solution over the learned toggle model.
"""

from __future__ import annotations

from collections import Counter
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
from admorphiq.kernels import (
    find_regions,
    frame_diff,
    grid_shortest_path,
    path_to_moves,
    plan_gated_path,
    track_objects,
)

GAME_ID = "dc22"

Cell = tuple[int, int]
Region = dict[str, Any]

_GIVEUP_DEFAULT = 4000
_HUD_SPAN_FRACTION = 0.85
_HUD_THICKNESS_FRACTION = 0.06

# Once this many non-inert toggle buttons are known (each classified by a
# second click), the product-graph plan is attempted. DC22 L0 needs 2.
_MIN_TOGGLERS_TO_PLAN = 2


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    r0, c0, r1, c1 = region["bbox"]
    h, w = r1 - r0 + 1, c1 - c0 + 1
    full_width_thin = w >= width * _HUD_SPAN_FRACTION and h <= max(1, int(height * _HUD_THICKNESS_FRACTION))
    full_height_thin = h >= height * _HUD_SPAN_FRACTION and w <= max(1, int(width * _HUD_THICKNESS_FRACTION))
    return full_width_thin or full_height_thin


def _live_regions(grid: tuple[tuple[int, ...], ...], background: int) -> list[Region]:
    """Non-background, non-HUD regions — the candidate pool for avatar, goal,
    and clickable buttons alike."""
    if not grid:
        return []
    height, width = len(grid), len(grid[0])
    return [r for r in find_regions(grid, background=background) if not _is_hud_band(r, height, width)]


def _detect_goal(regions: list[Region], avatar_color: int | None) -> tuple[int | None, Cell | None]:
    """The SMALLEST singleton-coloured region, excluding the avatar's own colour."""
    if not regions:
        return None, None
    color_counts = Counter(r["color"] for r in regions)
    singleton = [r for r in regions if color_counts[r["color"]] == 1 and r["color"] != avatar_color]
    if not singleton:
        return None, None
    goal = min(singleton, key=lambda r: r["size"])
    return goal["color"], goal["bbox"][:2]  # type: ignore[index]


def _hud_cells(grid: tuple[tuple[int, ...], ...], background: int) -> set[Cell]:
    height, width = len(grid), (len(grid[0]) if grid else 0)
    cells: set[Cell] = set()
    for r in find_regions(grid, background=background):
        if _is_hud_band(r, height, width):
            cells |= r["cells"]  # type: ignore[arg-type]
    return cells


class Adapter(GameAdapter):
    """Gated-maze product-graph planner composed from admorphiq.kernels, with
    an optimistic walk-and-learn bootstrap."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True
        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        self._dir_map: dict[int, Cell] = {}
        self._avatar_color: int | None = None
        self._active_cell: Cell | None = None
        self._goal_color: int | None = None
        self._goal_cell: Cell | None = None

        self._pending_action: int | None = None
        self._pending_kind: str | None = None  # "move" | "probe"
        self._pending_ref_cell: Cell | None = None
        self._pending_probe_cell: Cell | None = None
        self._prev_grid: tuple[tuple[int, ...], ...] | None = None

        self._tried_from: dict[Cell, set[int]] = {}
        self._known_blocked: set[Cell] = set()
        # Colours a blocked move landed against — the wall colours the
        # product-graph passability test uses (never hardcoded).
        self._wall_colors: set[int] = set()

        # Per-button memory keyed by the button cell (bbox top-left):
        # {"centroid", "diffs": [frozenset,...], "clicks": int}. A button is a
        # TOGGLER once any click changed cells; classified reveal-vs-swap by
        # its 2nd click.
        self._button_memory: dict[Cell, dict[str, Any]] = {}
        self._probe_clicks = 0

        # Cached product-graph plan (action ids + ("click", cell) tuples).
        self._plan: list[Any] | None = None
        self._plan_idx = 0

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._on_restart()
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._pending_action = None
            self._pending_kind = None
            self._prev_grid = None
            self._levels_seen = -1
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._on_level_up(levels)

        self._step += 1
        self._observe_result(grid)

        simple_ids, action6_ok = available_action_ids(latest_frame)
        move_ids = sorted(a for a in simple_ids if a in (1, 2, 3, 4))
        action = self._decide(grid, move_ids, action6_ok)
        self._prev_grid = grid
        return action

    # ── level / restart bookkeeping ─────────────────────────────────────

    def _on_level_up(self, levels: int) -> None:
        self._levels_seen = levels
        self._pending_action = None
        self._pending_kind = None
        self._pending_ref_cell = None
        self._pending_probe_cell = None
        self._prev_grid = None
        self._active_cell = None
        self._goal_color = None
        self._goal_cell = None
        self._tried_from = {}
        self._known_blocked = set()
        self._wall_colors = set()
        self._button_memory = {}
        self._probe_clicks = 0
        self._plan = None
        self._plan_idx = 0

    def _on_restart(self) -> None:
        self._pending_action = None
        self._pending_kind = None
        self._pending_ref_cell = None
        self._pending_probe_cell = None
        self._prev_grid = None
        self._active_cell = None
        # The plan is state-dependent (built from the level-start layout); a
        # restart reverts every toggle, so re-plan from scratch.
        self._plan = None
        self._plan_idx = 0

    # ── measurement ─────────────────────────────────────────────────────

    def _observe_result(self, grid: tuple[tuple[int, ...], ...]) -> None:
        action = self._pending_action
        kind = self._pending_kind
        ref_cell = self._pending_ref_cell
        probe_cell = self._pending_probe_cell
        prev_grid = self._prev_grid
        self._pending_action = None
        self._pending_kind = None
        self._pending_ref_cell = None
        self._pending_probe_cell = None
        if prev_grid is None:
            return
        if kind == "probe":
            self._observe_probe(prev_grid, grid, probe_cell)
            return
        if kind != "move" or action is None:
            return

        bg_prev = most_common_color(prev_grid)
        prev_regions = _live_regions(prev_grid, bg_prev)
        bg_cur = most_common_color(grid)

        if self._avatar_color is None:
            cur_regions = _live_regions(grid, bg_cur)
            tracked = track_objects(prev_regions, cur_regions)
            moved = [m for m in tracked["matches"] if tuple(m["shift"]) != (0, 0)]  # type: ignore[arg-type]
            if len(moved) != 1:
                return
            match = moved[0]
            from_cell: Cell = prev_regions[match["before"]]["bbox"][:2]  # type: ignore[index]
            shift: Cell = tuple(match["shift"])  # type: ignore[assignment]
            self._avatar_color = prev_regions[match["before"]]["color"]  # type: ignore[assignment]
            self._dir_map.setdefault(action, shift)
            self._active_cell = (from_cell[0] + shift[0], from_cell[1] + shift[1])
            return

        if ref_cell is None:
            return
        prev_avatar = next((r for r in prev_regions if r["color"] == self._avatar_color), None)
        if prev_avatar is None:
            return
        from_cell = prev_avatar["bbox"][:2]  # type: ignore[assignment]
        cur_avatar = [r for r in _live_regions(grid, bg_cur) if r["color"] == self._avatar_color]
        if not cur_avatar:
            return
        new_cell: Cell = cur_avatar[0]["bbox"][:2]  # type: ignore[assignment]
        if new_cell == from_cell:
            self._record_blocked(prev_grid, ref_cell, action)
            return
        self._dir_map.setdefault(action, (new_cell[0] - from_cell[0], new_cell[1] - from_cell[1]))
        self._tried_from.setdefault(from_cell, set()).add(action)
        self._active_cell = new_cell

    def _record_blocked(self, before: tuple[tuple[int, ...], ...], cell: Cell, action: int) -> None:
        self._tried_from.setdefault(cell, set()).add(action)
        unit = self._dir_map.get(action)
        if unit is None:
            return
        dest = (cell[0] + unit[0], cell[1] + unit[1])
        self._known_blocked.add(dest)
        if 0 <= dest[0] < len(before) and before and 0 <= dest[1] < len(before[0]):
            self._wall_colors.add(before[dest[0]][dest[1]])

    def _observe_probe(
        self,
        before: tuple[tuple[int, ...], ...],
        after: tuple[tuple[int, ...], ...],
        probe_cell: Cell | None,
    ) -> None:
        if probe_cell is None:
            return
        mem = self._button_memory.get(probe_cell)
        if mem is None:
            return
        bg = most_common_color(before)
        hud = _hud_cells(before, bg)
        changed = frozenset(c for c in frame_diff(before, after)["cells"] if c not in hud)  # type: ignore[union-attr]
        mem["diffs"].append(changed)
        mem["clicks"] += 1
        # A click opens/closes cells: those newly a wall colour become walls,
        # the rest leave — apply to the live known_blocked so the bootstrap
        # walk stays consistent.
        if changed:
            for r, c in changed:
                if after[r][c] in self._wall_colors:
                    self._known_blocked.add((r, c))
                else:
                    self._known_blocked.discard((r, c))

    # ── planning ─────────────────────────────────────────────────────────

    def _decide(
        self, grid: tuple[tuple[int, ...], ...], move_ids: list[int], action6_ok: bool
    ) -> GameAction:
        if not move_ids:
            self._pending_action = None
            self._pending_kind = None
            return reset_action()

        bg = most_common_color(grid)
        regions = _live_regions(grid, bg)

        if self._avatar_color is None:
            return self._probe(move_ids)
        avatar = [r for r in regions if r["color"] == self._avatar_color]
        if not avatar:
            return self._probe(move_ids)
        self._active_cell = avatar[0]["bbox"][:2]  # type: ignore[assignment]

        if self._goal_cell is None:
            self._goal_color, self._goal_cell = _detect_goal(regions, self._avatar_color)
            if self._goal_cell is None:
                return self._probe(move_ids)

        # Execute a cached product-graph plan if one exists.
        if self._plan is not None:
            act = self._next_plan_action(move_ids)
            if act is not None:
                return act

        # Try to BUILD a plan once the model is bootstrapped.
        if self._can_plan():
            plan = self._build_gated_plan(grid)
            if plan:
                self._plan = plan
                self._plan_idx = 0
                act = self._next_plan_action(move_ids)
                if act is not None:
                    return act

        # Bootstrap: optimistic walk toward the goal; when stuck, discover a
        # button (each clicked twice to classify) to enrich the toggle model.
        return self._bootstrap(grid, regions, move_ids, action6_ok)

    def _can_plan(self) -> bool:
        togglers = [c for c, m in self._button_memory.items() if m["clicks"] >= 2 and any(m["diffs"])]
        return (
            self._goal_cell is not None
            and bool(self._wall_colors)
            and bool(self._dir_map)
            and len(togglers) >= _MIN_TOGGLERS_TO_PLAN
        )

    def _build_gated_plan(self, grid: tuple[tuple[int, ...], ...]) -> list[Any] | None:
        """Compose plan_gated_path over the learned wall colours + toggle
        effects. Returns a list of action ids and ("click", cell) tuples, or
        None when unreachable."""
        assert self._active_cell is not None and self._goal_cell is not None
        height, width = len(grid), len(grid[0])
        walls0 = frozenset(
            (r, c)
            for r in range(height)
            for c in range(width)
            if grid[r][c] in self._wall_colors
        )
        togglers = sorted(
            (
                (cell, mem)
                for cell, mem in self._button_memory.items()
                if mem["clicks"] >= 2 and any(mem["diffs"])
            ),
            key=lambda cm: -max((len(d) for d in cm[1]["diffs"]), default=0),
        )
        toggles: list[tuple[Any, Any]] = []
        for cell, mem in togglers:
            first, second = mem["diffs"][0], mem["diffs"][1]
            reveal = frozenset(first - second)  # changed once only -> one-time
            swap = frozenset(first & second)  # changed both clicks -> toggles
            toggles.append((("click", cell), _make_mutator(reveal, swap)))

        move_labels = {unit: action for action, unit in self._dir_map.items()}

        def passable(cell: Cell, walls: frozenset[Cell]) -> bool:
            r, c = cell
            return 0 <= r < height and 0 <= c < width and cell not in walls

        return plan_gated_path(
            self._active_cell, self._goal_cell, walls0, passable, toggles, move_labels, max_states=400_000
        )

    def _next_plan_action(self, move_ids: list[int]) -> GameAction | None:
        assert self._plan is not None
        if self._plan_idx >= len(self._plan):
            self._plan = None
            return None
        item = self._plan[self._plan_idx]
        self._plan_idx += 1
        if isinstance(item, tuple) and item and item[0] == "click":
            cell = item[1]
            mem = self._button_memory[cell]
            row, col = round(mem["centroid"][0]), round(mem["centroid"][1])
            self._pending_action = None
            self._pending_kind = "probe"
            self._pending_probe_cell = cell
            return click_action(x=col, y=row)
        action = int(item)
        self._pending_action = action
        self._pending_kind = "move"
        self._pending_ref_cell = self._active_cell
        return simple_action(action)

    def _bootstrap(
        self,
        grid: tuple[tuple[int, ...], ...],
        regions: list[Region],
        move_ids: list[int],
        action6_ok: bool,
    ) -> GameAction:
        assert self._active_cell is not None and self._goal_cell is not None
        if self._dir_map:
            step = self._optimistic_step(grid)
            if step is not None:
                self._pending_action = step
                self._pending_kind = "move"
                self._pending_ref_cell = self._active_cell
                return simple_action(step)
        # Optimistic route blocked (or no dir_map yet) — discover a button.
        if action6_ok:
            probe = self._probe_button(regions)
            if probe is not None:
                return probe
        return self._probe(move_ids)

    def _optimistic_step(self, grid: tuple[tuple[int, ...], ...]) -> int | None:
        assert self._active_cell is not None and self._goal_cell is not None
        height, width = len(grid), len(grid[0])
        passable = [[(r, c) not in self._known_blocked for c in range(width)] for r in range(height)]
        moves = list(self._dir_map.values())
        move_labels = {unit: action for action, unit in self._dir_map.items()}
        path = grid_shortest_path(passable, self._active_cell, self._goal_cell, moves=moves)
        if not path or len(path) < 2:
            return None
        try:
            return path_to_moves(path[:2], move_labels)[0]
        except ValueError:
            return None

    def _probe_button(self, regions: list[Region]) -> GameAction | None:
        # Prefer clicking a KNOWN button a second time (to classify it), then
        # the largest never-clicked candidate — the biggest-diff buttons gate
        # the route (DC22's reveal/seesaw are the two largest regions clicked).
        for cell, mem in sorted(
            self._button_memory.items(),
            key=lambda cm: -max((len(d) for d in cm[1]["diffs"]), default=0),
        ):
            if mem["clicks"] == 1 and any(mem["diffs"]):
                return self._click_button(cell)
        if self._probe_clicks >= 40:
            return None
        candidates = [
            r
            for r in regions
            if r["color"] not in (self._avatar_color, self._goal_color)
            and r["bbox"][:2] not in self._button_memory
        ]
        if not candidates:
            return None
        target = max(candidates, key=lambda r: r["size"])
        cell: Cell = target["bbox"][:2]  # type: ignore[assignment]
        self._button_memory[cell] = {"centroid": target["centroid"], "diffs": [], "clicks": 0}
        return self._click_button(cell)

    def _click_button(self, cell: Cell) -> GameAction:
        mem = self._button_memory[cell]
        self._probe_clicks += 1
        self._pending_action = None
        self._pending_kind = "probe"
        self._pending_probe_cell = cell
        row, col = round(mem["centroid"][0]), round(mem["centroid"][1])
        return click_action(x=col, y=row)

    def _probe(self, move_ids: list[int]) -> GameAction:
        ref_cell = self._active_cell
        self._pending_ref_cell = ref_cell
        if ref_cell is not None:
            tried = self._tried_from.get(ref_cell, set())
            untried = [a for a in move_ids if a not in tried]
            if untried:
                self._pending_action = untried[0]
                self._pending_kind = "move"
                return simple_action(untried[0])
        action = move_ids[self._step % len(move_ids)]
        self._pending_action = action
        self._pending_kind = "move"
        return simple_action(action)


def _make_mutator(reveal: frozenset[Cell], swap: frozenset[Cell]):
    """A toggle's wall-set mutation: remove the one-time reveal set, toggle
    the swap set's wall-membership (symmetric difference)."""
    def mutate(walls: frozenset[Cell]) -> frozenset[Cell]:
        return frozenset((walls - reveal) ^ swap)

    return mutate
