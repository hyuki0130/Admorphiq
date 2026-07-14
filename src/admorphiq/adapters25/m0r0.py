"""script25 quarantined adapter: M0R0 (movement/maze family).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

Mechanic hypothesis (role assignment, declared HERE — not in the kernel
layer, which knows nothing about players, mazes, or actions): ACTION1-4 are
movement buttons; each press either shifts exactly one on-screen region by a
fixed amount (one "grid cell") or produces no visible shift at all (that
direction is blocked from the current cell). The adapter never assumes
WHICH region is the player, WHICH direction is "up", or how large a cell is
in pixels — every one of those facts is measured live from the frames via
``admorphiq.kernels``:

  - :func:`admorphiq.kernels.frame_diff` + :func:`admorphiq.kernels.find_regions`
    + :func:`admorphiq.kernels.track_objects` + :func:`admorphiq.kernels.motion_vectors`
    answer "did something move, and by how much" after each press.
  - :func:`admorphiq.kernels.grid_distance_field` + :func:`admorphiq.kernels.grid_shortest_path`
    + :func:`admorphiq.kernels.path_to_moves` answer "how do I get from here
    to the nearest cell whose neighbours I haven't tried yet" once every
    movement action has already been tried from the current cell.

This mirrors ``admorphiq.graph_frontier_agent.GraphFrontierAgent``'s
"frontier BFS to the nearest state with an untried action" ingredient (the
mechanism shared by the top ARC-AGI-3 graph agents — see that module's
docstring) but is reimplemented from scratch using ONLY the namespace-safe
kernel library: no state-hash graph, no HUD masking, no click candidates.
Those remain out of scope for this maze-navigation proof of concept (see
``docs/r56_codex_toolbase_verdict_20260715.md``'s script25 remit).

``.wiki/wiki/games/M0R0.md`` (read for reference, not imported) records
that M0R0 is a movement game with a mirror/reflection mechanic and that
frame-only BFS clears 2/6 levels — the target this adapter's own frontier
search is trying to reach purely by composing kernels.
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
from admorphiq.kernels import (
    find_regions,
    frame_diff,
    grid_distance_field,
    grid_shortest_path,
    motion_vectors,
    path_to_moves,
    track_objects,
)

GAME_ID = "m0r0"

Cell = tuple[int, int]

# Per-level safety cap: is_done() returns True after this many actions even
# if the level never clears, mirroring GraphFrontierAgent's own "giveup"
# ingredient so this adapter can never spin forever inside the harness.
_GIVEUP_DEFAULT = 4000

# Used only when no direction has been measured yet (so known_passable can
# only ever be the single start cell anyway -- the value never actually
# steers a real path, see _nearest_frontier's early-return on an empty
# frontier).
_CARDINAL_FALLBACK: tuple[Cell, ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))


def _sign(v: int) -> int:
    if v > 0:
        return 1
    if v < 0:
        return -1
    return 0


class Adapter(GameAdapter):
    """Frontier-BFS maze navigation composed entirely from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1
        # action_id -> measured UNIT cell delta (dr, dc), e.g. (0, 1). Persists
        # across levels: the control scheme is a property of the game, not the
        # layout (matching admorphiq.general_agent.GeneralAgent's documented
        # "carried control knowledge" convention).
        self._dir_map: dict[int, Cell] = {}
        self._pending_action: int | None = None
        self._prev_grid: tuple[tuple[int, ...], ...] | None = None
        self._player_cell: Cell = (0, 0)
        self._known_passable: set[Cell] = {(0, 0)}
        self._tried_from: dict[Cell, set[int]] = {}
        self._action_plan: list[int] = []

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state in ("NOT_PLAYED", "GAME_OVER") or not has_frame(latest_frame):
            self._pending_action = None
            self._prev_grid = None
            self._levels_seen = -1
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._on_level_up(levels)

        self._step += 1
        self._observe_result(grid)

        simple_ids, _action6_ok = available_action_ids(latest_frame)
        move_ids = sorted(a for a in simple_ids if a in (1, 2, 3, 4))
        if not move_ids:
            # No movement actions exposed at all -- nothing for a maze plan
            # to compose from. Degrade to whatever else is available rather
            # than crash; this adapter simply has no traction on this frame.
            self._prev_grid = grid
            self._pending_action = None
            return simple_action(simple_ids[0]) if simple_ids else reset_action()

        action = self._next_action(move_ids)
        self._prev_grid = grid
        self._pending_action = action
        return simple_action(action)

    # ── level bookkeeping ───────────────────────────────────────────────

    def _on_level_up(self, levels: int) -> None:
        """Drop every SPATIAL fact about the level just left; keep the dir_map."""
        self._levels_seen = levels
        self._pending_action = None
        self._prev_grid = None
        self._player_cell = (0, 0)
        self._known_passable = {(0, 0)}
        self._tried_from = {}
        self._action_plan = []

    # ── measurement: did the pending action move anything? ─────────────

    def _observe_result(self, grid: tuple[tuple[int, ...], ...]) -> None:
        """Fold the outcome of the just-executed action into the passability map.

        Composes frame_diff -> find_regions (before/after) -> track_objects
        -> motion_vectors to answer "did the mover shift, and in which unit
        direction" without ever assuming which region is the player or what
        color it is.
        """
        action = self._pending_action
        before = self._prev_grid
        self._pending_action = None
        if action is None or before is None:
            return
        if before == grid:
            self._tried_from.setdefault(self._player_cell, set()).add(action)
            return
        diff = frame_diff(before, grid)
        if diff["count"] == 0:
            self._tried_from.setdefault(self._player_cell, set()).add(action)
            return

        regions_before = find_regions(before, background=most_common_color(before))
        regions_after = find_regions(grid, background=most_common_color(grid))
        tracked = track_objects(regions_before, regions_after)
        dominant = motion_vectors(tracked["matches"])["dominant"]

        self._tried_from.setdefault(self._player_cell, set()).add(action)
        if not dominant or dominant == (0, 0):
            return
        unit = (_sign(dominant[0]), _sign(dominant[1]))
        self._dir_map.setdefault(action, unit)
        new_cell = (self._player_cell[0] + unit[0], self._player_cell[1] + unit[1])
        self._known_passable.add(new_cell)
        self._player_cell = new_cell

    # ── planning: what action to take next ──────────────────────────────

    def _next_action(self, move_ids: list[int]) -> int:
        tried_here = self._tried_from.get(self._player_cell, set())
        untried_here = [a for a in move_ids if a not in tried_here]
        if untried_here:
            return untried_here[0]

        if self._action_plan:
            return self._action_plan.pop(0)

        target = self._nearest_frontier(move_ids)
        if target is None or target == self._player_cell:
            # Nothing reachable left to explore (a fully-tried pocket, or no
            # direction measured yet) -- keep the harness alive with a
            # harmless re-probe rather than crash or idle forever.
            return move_ids[0]

        path = self._plan_path(self._player_cell, target)
        if len(path) < 2:
            return move_ids[0]
        move_labels = {unit: action for action, unit in self._dir_map.items()}
        moves = path_to_moves(path, move_labels)
        if not moves:
            return move_ids[0]
        self._action_plan = moves[1:]
        return moves[0]

    def _nearest_frontier(self, move_ids: list[int]) -> Cell | None:
        """The known-passable cell nearest the player with an untried direction."""
        frontier = [
            cell
            for cell in self._known_passable
            if any(a not in self._tried_from.get(cell, set()) for a in move_ids)
        ]
        if not frontier:
            return None
        array, origin = self._passable_array()
        moves = tuple(self._dir_map.values()) or _CARDINAL_FALLBACK
        source_local = self._to_local(self._player_cell, origin)
        distances = grid_distance_field(array, [source_local], moves=moves)
        best: Cell | None = None
        best_dist: int | None = None
        for cell in sorted(frontier):
            d = distances.get(self._to_local(cell, origin))
            if d is None:
                continue
            if best_dist is None or d < best_dist:
                best_dist = d
                best = cell
        return best

    def _plan_path(self, start: Cell, goal: Cell) -> list[Cell]:
        array, origin = self._passable_array()
        moves = tuple(self._dir_map.values()) or _CARDINAL_FALLBACK
        path_local = grid_shortest_path(
            array, self._to_local(start, origin), self._to_local(goal, origin), moves=moves
        )
        if path_local is None:
            return []
        return [self._to_absolute(c, origin) for c in path_local]

    def _passable_array(self) -> tuple[list[list[bool]], Cell]:
        cells = self._known_passable
        rows = [r for r, _c in cells]
        cols = [c for _r, c in cells]
        r0, r1 = min(rows), max(rows)
        c0, c1 = min(cols), max(cols)
        height, width = r1 - r0 + 1, c1 - c0 + 1
        array = [[False] * width for _ in range(height)]
        for r, c in cells:
            array[r - r0][c - c0] = True
        return array, (r0, c0)

    @staticmethod
    def _to_local(cell: Cell, origin: Cell) -> Cell:
        return (cell[0] - origin[0], cell[1] - origin[1])

    @staticmethod
    def _to_absolute(cell: Cell, origin: Cell) -> Cell:
        return (cell[0] + origin[0], cell[1] + origin[1])
