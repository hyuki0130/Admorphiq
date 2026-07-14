"""script25 quarantined adapter: M0R0 (mirrored-maze navigation family).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

**Backport (this revision)**: replaces the original undirected frontier-BFS
exploration (which never reaches a declared target — it just walks toward
whichever known cell has the fewest tried actions) with the
optimistic-passability + shortest-path-to-a-declared-goal pattern
``admorphiq.adapters25.dc22``/``admorphiq.adapters25.ka59`` now use. A full
first-smoke VM measurement at ~4000 actions found undirected frontier
exploration alone insufficient (0/6, still 0 even at 8x the original
500-action budget) — the wall is DIRECTION, not exploration budget, exactly
the gap dc22/ka59's goal-directed planner closed for their own games.

**Offline goal-signal investigation (before any code changed)**, mirroring
dc22's own offline-verification discipline: loaded ``data/traces/m0r0.npz``
(gold trace, label-generation only, never imported into this adapter) and
traced BOTH captured levels' gold blocks frame-by-frame. Finding, measured
directly (not assumed from the wiki's "mirror/reflection mechanic" prose —
that prose motivated WHERE to look, this is what was actually measured):
the avatar's own colour is used by TWO regions simultaneously throughout
the level, not one. On a horizontal-axis action, the two regions move in
OPPOSITE absolute directions (a genuine mirror pair, not a static "goal
marker" the wiki's older single-avatar framing would suggest); on a
vertical-axis action, both move in the SAME absolute direction; each side
can be blocked independently by its own local walls (the two halves of the
board are NOT identical mazes, just mirrored in shape). The measured WIN
action, on both captured levels, is exactly the step that brings the two
regions into pixel-adjacency (their bboxes merge into one connected region
under ``find_regions``). **There is no separate small "exit marker"
region for this mechanic — the goal IS the mirror partner's own current
position, which is itself moving, not a one-time-computed fixed cell.**
This directly changes what "declare a goal" means for M0R0 versus DC22 (a
static marker, computed once): here the goal must be RE-READ from the live
frame every planning call, exactly like every other per-cell fact in this
adapter, so the planner is always routing toward the mirror partner's
actual current position rather than a stale offline snapshot.

``_detect_goal`` therefore tries the mirror-partner reading FIRST (the
nearest OTHER same-avatar-colour region), and falls back to DC22's own
"smallest singleton-coloured region" reading only when no second
same-colour region exists — a level using a genuinely different (single-
avatar-to-marker) mechanic is not assumed impossible, just not what the
two captured levels showed.

Mechanic hypothesis (role assignment, declared HERE — not in the kernel
layer, which knows nothing about players, mazes, or actions): ACTION1-4 are
movement buttons; each press either shifts a region by a fixed measured
pixel amount or produces no visible shift (blocked from the current cell).
Composed entirely from ``admorphiq.kernels``:

  - :func:`admorphiq.kernels.find_regions` + :func:`admorphiq.kernels.track_objects`
    identify the avatar (mirroring ``admorphiq.adapters25.dc22``'s
    identity-by-movement technique — the region that moves when only ONE
    region on the whole board shifts, tried across successive probe
    actions until a frame satisfies that condition) and, every planning
    call thereafter, the CURRENT mirror-partner position.
  - :func:`admorphiq.kernels.grid_shortest_path` + :func:`admorphiq.kernels.grid_distance_field`
    + :func:`admorphiq.kernels.path_to_moves` plan over the SAME
    optimistic passability model DC22/KA59 use: every cell is assumed
    passable except ones CONFIRMED blocked by a failed movement attempt,
    so the planner beelines toward wherever the mirror partner currently
    sits instead of only trusting individually-confirmed-safe cells.

Hazard memory (kept from the pre-backport version, unchanged in spirit —
this game's own GAME_OVER trap is orthogonal to the goal-direction
change): a first smoke run measured GAME_OVER at 151 actions with 0
levels cleared, so this adapter keeps ``restart_on_game_over = True`` and
tracks (cell, action) pairs that trigger a fatal reposition —
:meth:`_observe_result` detects this two ways: (a) the harness's own
explicit ``state == "GAME_OVER"`` (now correctly handled the same way
``dc22`` does — :meth:`_on_restart` preserves every learned fact and only
resets the current attempt's position, where the PRE-backport version
incorrectly routed this through the full level-wipe path shared with
``NOT_PLAYED``, discovered while porting dc22's control-flow shape here);
(b) a SILENT reposition (the frame snaps back to the exact start-of-level
frame while this adapter's own tracked position was mid-maze) for any
engine that never reports an explicit GAME_OVER state for this outcome.
Either way, a cell hazardous under >= ``_DEAD_CELL_HAZARD_THRESHOLD``
distinct actions is excluded from the passable array entirely (see
``_passable_array``), persisted across restarts within a level, and reset
on level-up alongside the rest of the spatial state.
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
from admorphiq.kernels import (
    find_regions,
    grid_distance_field,
    grid_shortest_path,
    path_to_moves,
    track_objects,
)

GAME_ID = "m0r0"

Cell = tuple[int, int]
Region = dict[str, Any]

# Per-level safety cap, mirroring every other script25 adapter's giveup
# convention so the harness never spins forever inside this one.
_GIVEUP_DEFAULT = 4000

# A cell hazardous under this many DISTINCT actions is declared dead outright
# (excluded from future path-planning entirely) rather than waiting to try
# every remaining direction from it too. Measured motivation (pre-backport):
# a smoke run recorded the SAME cell killing the run on 3 separate actions
# across 3 separate lives (455 of 500 actions spent re-discovering that one
# spot is fatal regardless of direction) -- 2 independent hazardous
# directions from one cell is already strong evidence the CELL itself is the
# trap, not the direction, so this stops the frontier search from ever
# returning to it. Kept unchanged by this backport.
_DEAD_CELL_HAZARD_THRESHOLD = 2


def _manhattan(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _detect_goal(
    regions: list[Region],
    self_color: int | None,
    self_cell: Cell | None,
    partner_ever_seen: bool,
) -> tuple[int | None, Cell | None]:
    """The mirror partner's current position when one exists (the NEAREST
    other region sharing the avatar's own colour — see module docstring's
    offline investigation), re-read fresh from the CURRENT frame every call
    (never cached) -- a mirror partner's position cannot be a one-time
    snapshot the way DC22's static marker is.

    When ``partner_ever_seen`` is True (this level's mirror partner has
    been directly observed on some EARLIER call) but no separate partner
    region is visible on THIS frame, the two pieces are momentarily
    touching/merged into one connected region (measured directly: both
    captured gold levels briefly show exactly this right before, and
    sometimes several actions before, the actual WIN moment -- see module
    docstring). Reporting ``self_cell`` itself as the goal in that case
    correctly reads as "already arrived" downstream (``Adapter._decide``'s
    ``active_cell == goal_cell`` check) rather than falling through to the
    singleton-colour fallback below and fabricating a goal from an
    unrelated region -- the exact bug a first live smoke measured directly
    (the goal jumped to a HUD/border region's position mid-level, sending
    the planner chasing it for dozens of wasted actions).

    DC22's own "smallest singleton-coloured region" reading is used ONLY
    when no partner has EVER been seen this level -- for any level that
    turns out not to use the mirror-partner mechanic at all."""
    if not regions:
        return None, None
    if self_color is not None and self_cell is not None:
        partners = [
            r for r in regions if r["color"] == self_color and r["bbox"][:2] != self_cell
        ]
        if partners:
            nearest = min(partners, key=lambda r: _manhattan(r["bbox"][:2], self_cell))
            return self_color, nearest["bbox"][:2]  # type: ignore[index]
        if partner_ever_seen:
            return self_color, self_cell

    color_counts = Counter(r["color"] for r in regions)
    singleton = [r for r in regions if color_counts[r["color"]] == 1 and r["color"] != self_color]
    if not singleton:
        return None, None
    goal = min(singleton, key=lambda r: r["size"])
    return goal["color"], goal["bbox"][:2]  # type: ignore[index]


class Adapter(GameAdapter):
    """Optimistic goal-directed navigation composed entirely from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        # action_id -> measured pixel delta (dr, dc) of SELF's OWN region.
        # Persists across levels and restarts: the control scheme is a
        # property of the game, not the layout.
        self._dir_map: dict[int, Cell] = {}
        self._self_color: int | None = None
        self._active_cell: Cell | None = None
        self._goal_color: int | None = None
        self._goal_cell: Cell | None = None
        # True once a mirror partner has been directly observed as a
        # SEPARATE region at least once this level -- see _detect_goal's
        # docstring for why this gates the singleton-colour fallback.
        self._partner_ever_seen = False

        self._pending_action: int | None = None
        self._pending_ref_cell: Cell | None = None
        self._prev_grid: tuple[tuple[int, ...], ...] | None = None
        # The very first frame seen this level (post-reset frames snap back
        # to this exactly) -- see _observe_result's silent-reposition
        # detector.
        self._level_start_grid: tuple[tuple[int, ...], ...] | None = None
        # SELF's own position the first time it was ever measured this
        # level (cached once, at the same moment _self_color is first
        # learned). Used to re-acquire SELF's identity after ANY restart
        # (_active_cell goes back to None) among the >= 1 same-coloured
        # regions on the board -- nearest-to-start-position is a robust,
        # measured-necessary disambiguator once a mirror partner of the
        # SAME colour exists (see module docstring's offline
        # investigation); picking an arbitrary same-coloured region would
        # risk locking onto the mirror partner instead of SELF.
        self._level_start_cell: Cell | None = None

        self._tried_from: dict[Cell, set[int]] = {}
        # Cells CONFIRMED blocked. Every other cell is OPTIMISTICALLY
        # assumed passable -- a movement attempt that fails to shift SELF
        # adds its predicted destination here; nothing removes a cell once
        # added (no button/toggle mechanic in this game, unlike DC22).
        self._known_blocked: set[Cell] = set()

        # (cell, action) pairs that triggered a fatal reposition. Persists
        # across restarts WITHIN a level (a property of the layout);
        # cleared on level-up alongside every other spatial fact. Kept from
        # the pre-backport version, unchanged in spirit.
        self._hazards: dict[Cell, set[int]] = {}
        # Cells hazardous under >= _DEAD_CELL_HAZARD_THRESHOLD distinct
        # actions -- excluded from the passable array and frontier search
        # entirely (see _passable_array). Persists like _hazards.
        self._dead_cells: set[Cell] = set()

        self._replans = 0

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            # A fatal reposition just happened, but the maze layout (walls,
            # hazards) didn't change -- only the current attempt did. This
            # branch previously shared the full-wipe path with NOT_PLAYED
            # below (a real bug found while porting DC22's control-flow
            # shape here: it silently discarded every learned wall/hazard
            # fact on every single GAME_OVER, defeating the hazard-memory
            # mechanism this file has always documented). Now matches
            # DC22's own correct GAME_OVER handling.
            self._on_restart()
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._pending_action = None
            self._pending_ref_cell = None
            self._prev_grid = None
            self._levels_seen = -1
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._on_level_up(levels, grid)

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

        action = self._decide(grid, move_ids)
        self._prev_grid = grid
        self._pending_action = action
        return simple_action(action)

    # ── level / restart bookkeeping ─────────────────────────────────────

    def _on_level_up(self, levels: int, grid: tuple[tuple[int, ...], ...]) -> None:
        """Drop every SPATIAL fact about the level just left; keep the dir_map."""
        self._levels_seen = levels
        self._pending_action = None
        self._pending_ref_cell = None
        self._prev_grid = None
        self._level_start_grid = grid
        self._level_start_cell = None
        self._active_cell = None
        self._goal_color = None
        self._goal_cell = None
        self._partner_ever_seen = False
        self._tried_from = {}
        self._known_blocked = set()
        self._hazards = {}
        self._dead_cells = set()

    def _on_restart(self) -> None:
        """Only SELF's own tracked position resets; every fact already
        learned about the layout (dir_map, known_blocked, hazards,
        dead_cells, tried_from) remains true (the maze didn't change, only
        the attempt did) and is deliberately KEPT so each life compounds
        on the last instead of re-exploring from scratch every time --
        measured necessary pre-backport: an earlier version wiped this
        knowledge on every restart and spent nearly the whole action
        budget per life re-discovering the same already-known-safe cells."""
        self._pending_action = None
        self._pending_ref_cell = None
        self._prev_grid = None
        self._active_cell = None

    # ── measurement: did the pending action move SELF? ─────────────────

    def _observe_result(self, grid: tuple[tuple[int, ...], ...]) -> None:
        action = self._pending_action
        ref_cell = self._pending_ref_cell
        before = self._prev_grid
        self._pending_action = None
        self._pending_ref_cell = None
        if action is None or before is None:
            return

        # A SILENT reposition: the frame snaps back to the exact
        # level-start frame while this adapter's own tracking still holds
        # a position DIFFERENT from where SELF started this level -- a
        # fatal reposition just happened without the harness ever
        # reporting an explicit GAME_OVER state for it (kept from the
        # pre-backport version; see module docstring). Compared against
        # the cached level-start position, never a literal (0, 0) --
        # SELF's start cell is wherever its region actually sits in raw
        # frame pixels, not an abstract coordinate-space origin.
        if (
            self._active_cell is not None
            and self._level_start_cell is not None
            and self._active_cell != self._level_start_cell
            and grid == self._level_start_grid
        ):
            self._record_hazard(ref_cell, action)
            self._on_restart()
            return

        bg_before = most_common_color(before)
        regions_before = find_regions(before, background=bg_before)

        if self._self_color is None:
            bg_cur = most_common_color(grid)
            regions_cur = find_regions(grid, background=bg_cur)
            tracked = track_objects(regions_before, regions_cur)
            moved = [m for m in tracked["matches"] if tuple(m["shift"]) != (0, 0)]  # type: ignore[arg-type]
            if len(moved) != 1:
                return
            match = moved[0]
            from_cell: Cell = regions_before[match["before"]]["bbox"][:2]  # type: ignore[index]
            shift: Cell = tuple(match["shift"])  # type: ignore[assignment]
            self._self_color = regions_before[match["before"]]["color"]  # type: ignore[assignment]
            self._level_start_cell = from_cell
            self._dir_map.setdefault(action, shift)
            self._tried_from.setdefault(from_cell, set()).add(action)
            self._active_cell = (from_cell[0] + shift[0], from_cell[1] + shift[1])
            return

        if ref_cell is None:
            return
        self_before = [r for r in regions_before if r["color"] == self._self_color]
        if not self_before:
            return
        from_cell = min(self_before, key=lambda r: _manhattan(r["bbox"][:2], ref_cell))["bbox"][:2]  # type: ignore[assignment]
        bg_cur = most_common_color(grid)
        self_cur = [r for r in find_regions(grid, background=bg_cur) if r["color"] == self._self_color]
        if not self_cur:
            return
        new_cell: Cell = min(self_cur, key=lambda r: _manhattan(r["bbox"][:2], ref_cell))["bbox"][:2]  # type: ignore[assignment]
        if new_cell == from_cell:
            self._record_blocked(ref_cell, action)
            return
        shift = (new_cell[0] - from_cell[0], new_cell[1] - from_cell[1])
        self._dir_map.setdefault(action, shift)
        self._tried_from.setdefault(from_cell, set()).add(action)
        self._active_cell = new_cell

    def _record_blocked(self, cell: Cell, action: int) -> None:
        """Mark ``action`` tried from ``cell``, and if its measured
        direction is known, add the refuted destination to
        ``_known_blocked`` -- the fact ``_passable_array`` reads to stop
        assuming that cell passable. Counted as a replan: the NEXT
        optimistic beeline attempt routes around it."""
        self._tried_from.setdefault(cell, set()).add(action)
        unit = self._dir_map.get(action)
        if unit is None:
            return
        dest = (cell[0] + unit[0], cell[1] + unit[1])
        if dest not in self._known_blocked:
            self._known_blocked.add(dest)
            self._replans += 1

    def _record_hazard(self, cell: Cell | None, action: int | None) -> None:
        if cell is None or action is None:
            return
        self._tried_from.setdefault(cell, set()).add(action)
        hazard_actions = self._hazards.setdefault(cell, set())
        hazard_actions.add(action)
        if len(hazard_actions) >= _DEAD_CELL_HAZARD_THRESHOLD:
            self._dead_cells.add(cell)

    # ── planning ─────────────────────────────────────────────────────────

    def _decide(self, grid: tuple[tuple[int, ...], ...], move_ids: list[int]) -> int:
        if self._self_color is None:
            return self._probe(move_ids)

        bg = most_common_color(grid)
        regions = find_regions(grid, background=bg)
        self_regions = [r for r in regions if r["color"] == self._self_color]
        if not self_regions:
            return self._probe(move_ids)
        # After a restart _active_cell is None -- re-acquire identity via
        # the cached level-start position (never an arbitrary "first
        # region found"), since a mirror partner of the SAME colour can
        # otherwise be picked up as SELF by mistake (see module docstring).
        ref = self._active_cell if self._active_cell is not None else self._level_start_cell
        if ref is None:
            ref = self_regions[0]["bbox"][:2]  # type: ignore[assignment]
        self._active_cell = min(self_regions, key=lambda r: _manhattan(r["bbox"][:2], ref))["bbox"][:2]  # type: ignore[assignment]

        partners_now = [
            r
            for r in regions
            if r["color"] == self._self_color and r["bbox"][:2] != self._active_cell
        ]
        if partners_now:
            self._partner_ever_seen = True
        self._goal_color, self._goal_cell = _detect_goal(
            regions, self._self_color, self._active_cell, self._partner_ever_seen
        )
        if self._goal_cell is None:
            return self._probe(move_ids)

        if self._active_cell == self._goal_cell:
            return self._probe(move_ids)

        return self._route(move_ids)

    def _pick_action(self, candidates: list[int], ref_cell: Cell, goal: Cell | None) -> int:
        """Choose among untried ``candidates`` from ``ref_cell``. A
        candidate whose direction has never been measured anywhere is
        tried FIRST, unconditionally -- a target reachable only via an
        unmeasured direction is invisible to the optimistic planner's move
        set otherwise. Ties among measured candidates break by Manhattan
        distance their predicted destination leaves to ``goal``."""
        unmeasured = [a for a in candidates if a not in self._dir_map]
        if unmeasured:
            return unmeasured[0]
        if goal is None:
            return candidates[0]

        def score(action: int) -> int:
            dr, dc = self._dir_map[action]
            dest = (ref_cell[0] + dr, ref_cell[1] + dc)
            return _manhattan(dest, goal)

        return min(candidates, key=score)

    def _viable_actions(self, cell: Cell, move_ids: list[int]) -> list[int]:
        tried = self._tried_from.get(cell, set())
        out = []
        for a in move_ids:
            if a in tried:
                continue
            unit = self._dir_map.get(a)
            if unit is not None and (cell[0] + unit[0], cell[1] + unit[1]) in self._dead_cells:
                continue
            out.append(a)
        return out

    def _probe(self, move_ids: list[int], cell: Cell | None = None) -> int:
        ref_cell = cell if cell is not None else self._active_cell
        self._pending_ref_cell = ref_cell
        if ref_cell is not None:
            untried = self._viable_actions(ref_cell, move_ids)
            if untried:
                return self._pick_action(untried, ref_cell, self._goal_cell)
        return move_ids[0]

    def _passable_array(self) -> list[list[bool]]:
        """A ``grid_shortest_path``-shaped passability array over the FULL
        64x64 frame: every cell ``True`` (optimistically passable) EXCEPT
        ones in ``_known_blocked`` or ``_dead_cells``."""
        height, width = 64, 64
        array = [[True] * width for _ in range(height)]
        for r, c in self._known_blocked | self._dead_cells:
            if 0 <= r < height and 0 <= c < width:
                array[r][c] = False
        return array

    def _route(self, move_ids: list[int]) -> int:
        assert self._active_cell is not None and self._goal_cell is not None
        if not self._dir_map:
            return self._probe(move_ids)

        self._pending_ref_cell = self._active_cell
        moves = list(self._dir_map.values())
        move_labels = {unit: action for action, unit in self._dir_map.items()}
        optimistic = self._passable_array()

        path = grid_shortest_path(optimistic, self._active_cell, self._goal_cell, moves=moves)
        if path and len(path) >= 2:
            try:
                step = path_to_moves(path[:2], move_labels)[0]
                return step
            except ValueError:
                pass

        # The optimistic planner found NO route -- try the current cell's
        # own untried actions before considering anything else (a target
        # reachable only via an unmeasured direction from HERE is
        # otherwise invisible to the planner's known move set).
        untried_here = self._viable_actions(self._active_cell, move_ids)
        if untried_here:
            return self._pick_action(untried_here, self._active_cell, self._goal_cell)

        # Broader frontier: any OTHER cell ever stood at with fewer than
        # len(move_ids) actions tried, ranked by proximity to the GOAL.
        frontier_cells = [
            c for c, tried in self._tried_from.items() if len(tried) < len(move_ids) and c != self._active_cell
        ]
        if frontier_cells:
            goal_distances = grid_distance_field(optimistic, [self._goal_cell], moves=moves)
            frontier_cells.sort(key=lambda c: goal_distances.get(c, float("inf")))
            for cell in frontier_cells:
                sub_path = grid_shortest_path(optimistic, self._active_cell, cell, moves=moves)
                if sub_path and len(sub_path) >= 2:
                    try:
                        return path_to_moves(sub_path[:2], move_labels)[0]
                    except ValueError:
                        continue

        # Truly stuck: every reachable cell (via the optimistic map) is
        # fully explored and none leads toward the goal.
        return self._probe(move_ids)
