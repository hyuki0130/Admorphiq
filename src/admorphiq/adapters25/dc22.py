"""script25 quarantined adapter: DC22 (button-barrier navigation family).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/DC22.md`` (read for reference, not imported) records
DC22 as a "movement" game (R57's typology T1 nav + T2 elimination/door):
ACTION1-4 cardinal movement, ACTION6 toggles barriers by clicking
buttons; "the player must click-toggle the right buttons and then walk
to the exit". The wiki also flags a documented failure mode for a
DIFFERENT agent family (the generic runtime harness's HUD-vs-avatar
region-mask heuristic, ``.wiki/wiki/lessons/dc22_confined_avatar_discriminator_falsified_20260713.md``)
-- that lesson does NOT apply here: this adapter identifies the avatar
by direct movement measurement (like every other script25 adapter), never
by a generic HUD/avatar discriminator, so it never encounters that
specific failure.

**Offline verification (before any live action)**: loaded
``data/traces/dc22.npz`` (gold trace, label-generation only, never
imported into this adapter). Level 0's gold block is 20 actions
(matching ``min_actions_total``). Diffing the frame before/after each of
the gold trace's 3 ACTION6 clicks (this adapter's own read, not a
description) shows:

- Click 1 (at the FIRST board position): a large one-time diff (97
  cells) -- background->colour5 across a wide area, PLUS two 8-cell
  "indicator" clusters flip colour9<->4. Click 3 (the SAME point,
  clicked again later) diffs only 17 cells -- just the two indicator
  clusters flipping back, no repeat of the big one-time change.
- Click 2 (a DIFFERENT board position): a clean 49-cell diff -- one
  block of cells goes colour4->8 while a DIFFERENT block goes 8->4 at
  the same time. This is a genuine SEESAW gate: opening one path closes
  another, confirmed by direct measurement, not assumed.

Diffing the pure-movement rows (no clicks) isolates the avatar: a
compact, uniquely-coloured 2x2 sprite, moving a MEASURED fixed pixel
delta per cardinal action (2px here, but never hardcoded -- see
``_dir_map``). The wiki-documented "confining starting box" turned out,
on direct measurement, to be COSMETIC for this level: the avatar's own
first 1-2 plain movement actions already carry it outside the box's own
row range, with no blocked-movement diff recorded there -- so this
adapter does not special-case it at all; ordinary movement measurement
already walks straight past it.

**Goal detection**: the avatar's position at the exact WIN action
(``levels_completed_after`` first increments) coincides exactly with a
distinct 2x2, uniquely-coloured marker region present on the very first
frame (colour 11 here, but the adapter never hardcodes a colour -- see
``_detect_goal``). Checking the FULL colour histogram of the start
frame's regions: every colour used by more than one region is excluded
outright; among the remaining SINGLETON colours (used by exactly one
region), sizes range from 4 (the goal marker, and the avatar itself) up
to 1190 (a large floor panel) -- the marker and the avatar are both the
SMALLEST singleton-coloured regions on the board, several orders of
magnitude smaller than any other singleton. ``_detect_goal`` therefore
declares the goal as the smallest singleton-coloured region EXCLUDING
the avatar's own (already-measured) colour -- a structural signal
derived the same way on any board, not a hardcoded colour value.

**Mechanic model (declared here, not in the kernel layer)**: this
adapter never tries to understand WHAT a button does semantically (which
colour means "wall" vs "floor", or which specific cells a given button
controls). It only needs to know, at the pixel level, whether a
previously-confirmed-blocked cell might now be open. When a probe click
changes any cell, every changed cell is removed from ``_known_blocked``
(treated as "unknown again, optimistically passable") -- if it is STILL
blocked, the very next attempted walk through it will fail and the
existing wall-measurement path (:meth:`Adapter._record_blocked`,
identical in spirit to every other script25 movement adapter) re-adds
it. This sidesteps needing to interpret button->barrier semantics at
all, including the measured seesaw case (a button that also RE-closes a
different, previously-open cell): those cells get removed from
``_known_blocked`` too if they show up in the diff, and any that are now
genuinely blocked get correctly re-discovered and re-added the next time
routing tries to walk through them.

**Walk -> stuck -> probe -> learn -> re-plan loop**: the active piece
walks the OPTIMISTIC grid (see ``admorphiq.adapters25.ka59``'s design,
reused here for a single avatar instead of multiple pieces) toward the
goal. Only when the optimistic planner AND the broader known-cell
frontier fallback BOTH report no progress does the adapter click a
candidate button region (nearest to the avatar's current position,
excluding the avatar's and goal's own colours and any region already
probed this level -- MEASURED necessary, per
``admorphiq.adapters25.vc33``'s lesson, that a probed region should never
be re-probed even if it turned out inert, since re-probing wastes a
budgeted action for a result already known). Bounded at
``_PROBE_CLICK_CAP`` clicks per stuck episode so a board with no
reachable button (or a genuinely unsolvable local pocket) cannot spin
forever.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments the frame into the
    avatar, the goal marker, and every button/wall candidate.
  - :func:`admorphiq.kernels.track_objects` identifies which region
    moved after the FIRST movement probe (before the avatar's colour is
    known at all) -- exactly mirroring
    ``admorphiq.adapters25.ka59``'s identity-by-movement technique.
  - :func:`admorphiq.kernels.frame_diff` measures both a movement
    attempt's outcome (did the avatar's own region actually shift) and a
    button probe's outcome (did ANY cell change at all).
  - :func:`admorphiq.kernels.grid_shortest_path` + :func:`admorphiq.kernels.grid_distance_field`
    plan over the same OPTIMISTIC passability model
    ``admorphiq.adapters25.ka59`` introduced: genuinely unexplored cells
    are assumed passable, so the avatar beelines toward the goal instead
    of only trusting individually-confirmed-safe cells, and a button
    click that opens new territory is discovered by simply trying to
    walk there.
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
    grid_distance_field,
    grid_shortest_path,
    path_to_moves,
    track_objects,
)

GAME_ID = "dc22"

Cell = tuple[int, int]
Region = dict[str, Any]

# Per-level safety cap, mirroring every other script25 adapter's giveup
# convention so the harness never spins forever inside this one.
_GIVEUP_DEFAULT = 4000

# A region spanning at least this fraction of the frame's own span in one
# axis while thin in the other is a HUD status bar/strip, not a discrete
# game element. Matches su15/sb26's own convention (independently declared
# here, since each adapter's role assignments are its own).
_HUD_SPAN_FRACTION = 0.85
_HUD_THICKNESS_FRACTION = 0.06

# Bound on button probe clicks per stuck episode -- a board with no
# reachable button, or a genuinely unsolvable local pocket, must not spin
# forever clicking every remaining candidate.
_PROBE_CLICK_CAP = 8


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    r0, c0, r1, c1 = region["bbox"]
    h, w = r1 - r0 + 1, c1 - c0 + 1
    full_width_thin = w >= width * _HUD_SPAN_FRACTION and h <= max(1, int(height * _HUD_THICKNESS_FRACTION))
    full_height_thin = h >= height * _HUD_SPAN_FRACTION and w <= max(1, int(width * _HUD_THICKNESS_FRACTION))
    return full_width_thin or full_height_thin


def _live_regions(grid: tuple[tuple[int, ...], ...], background: int) -> list[Region]:
    """Non-background, non-HUD regions -- the candidate pool for avatar,
    goal marker, and clickable buttons alike."""
    if not grid:
        return []
    height, width = len(grid), len(grid[0])
    return [r for r in find_regions(grid, background=background) if not _is_hud_band(r, height, width)]


def _detect_goal(regions: list[Region], avatar_color: int | None) -> tuple[int | None, Cell | None]:
    """The SMALLEST singleton-coloured region, excluding the avatar's own
    colour -- see module docstring's "Goal detection" section for the
    offline measurement this is based on."""
    if not regions:
        return None, None
    color_counts = Counter(r["color"] for r in regions)
    singleton = [r for r in regions if color_counts[r["color"]] == 1 and r["color"] != avatar_color]
    if not singleton:
        return None, None
    goal = min(singleton, key=lambda r: r["size"])
    return goal["color"], goal["bbox"][:2]  # type: ignore[index]


class Adapter(GameAdapter):
    """Walk-stuck-probe-learn-replan navigation composed from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        # action_id -> measured pixel delta (dr, dc). Persists across
        # levels and restarts: the control scheme is a property of the
        # game, not the layout or the current life.
        self._dir_map: dict[int, Cell] = {}
        # The avatar's own colour, measured once (never hardcoded) the
        # first time a movement genuinely reveals which region moved.
        # Persists across levels and restarts -- the same convention
        # applies to every level of the same game.
        self._avatar_color: int | None = None
        self._active_cell: Cell | None = None
        self._goal_color: int | None = None
        self._goal_cell: Cell | None = None

        self._pending_action: int | None = None
        self._pending_kind: str | None = None  # "move" | "probe" | None
        self._pending_ref_cell: Cell | None = None
        self._pending_probe_cell: Cell | None = None
        self._prev_grid: tuple[tuple[int, ...], ...] | None = None

        self._tried_from: dict[Cell, set[int]] = {}
        # Cells CONFIRMED blocked. Every other cell is OPTIMISTICALLY
        # assumed passable -- see module docstring. A button click that
        # changes a cell removes it from here (see _observe_probe_result),
        # letting the optimistic planner try it again rather than trust a
        # possibly-stale "this is a wall" belief forever.
        self._known_blocked: set[Cell] = set()

        # Button regions already probed this level (by their own cell),
        # regardless of effect -- never re-probed (see module docstring's
        # vc33 cross-reference).
        self._probed_buttons: set[Cell] = set()
        self._probe_clicks_this_episode = 0

        # Diagnostic-only counters.
        self._replans = 0
        self._probes_effective = 0
        self._probes_inert = 0

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
        self._probed_buttons = set()
        self._probe_clicks_this_episode = 0

    def _on_restart(self) -> None:
        """Only the avatar's own position resets; the layout knowledge
        (dir_map, known_blocked, probed_buttons) is kept -- the walls and
        button effects didn't change, only the current attempt did."""
        self._pending_action = None
        self._pending_kind = None
        self._pending_ref_cell = None
        self._pending_probe_cell = None
        self._prev_grid = None
        self._active_cell = None
        self._probe_clicks_this_episode = 0

    # ── measurement: did the pending action do anything? ────────────────

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
            self._observe_probe_result(prev_grid, grid, probe_cell)
            return
        if kind != "move" or action is None:
            return

        bg_prev = most_common_color(prev_grid)
        prev_regions = _live_regions(prev_grid, bg_prev)

        if self._avatar_color is None:
            bg_cur = most_common_color(grid)
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
            self._tried_from.setdefault(from_cell, set()).add(action)
            self._active_cell = (from_cell[0] + shift[0], from_cell[1] + shift[1])
            return

        if ref_cell is None:
            return
        prev_avatar = next((r for r in prev_regions if r["color"] == self._avatar_color), None)
        if prev_avatar is None:
            return
        from_cell = prev_avatar["bbox"][:2]  # type: ignore[assignment]
        bg_cur = most_common_color(grid)
        cur_avatar_regions = [
            r for r in _live_regions(grid, bg_cur) if r["color"] == self._avatar_color
        ]
        if not cur_avatar_regions:
            return
        new_cell: Cell = cur_avatar_regions[0]["bbox"][:2]  # type: ignore[assignment]
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
        ``_known_blocked`` -- the fact ``_optimistic_grid`` reads to stop
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

    def _observe_probe_result(
        self,
        before: tuple[tuple[int, ...], ...],
        after: tuple[tuple[int, ...], ...],
        probe_cell: Cell | None,
    ) -> None:
        """Whether a button click changed ANYTHING -- never interpreted
        semantically (see module docstring): every changed cell is just
        removed from ``_known_blocked`` so the optimistic planner is
        willing to try walking through it again, whether it turns out
        open or (re-discovered the normal way) still blocked.

        HUD cells (e.g. the step counter, which increments every action
        regardless of the click) are excluded from ``changed`` using the
        SAME measured ``_is_hud_band`` region test every other candidate
        list in this file uses -- not a hardcoded row/column guess."""
        if probe_cell is None:
            return
        height, width = len(before), (len(before[0]) if before else 0)
        bg_before = most_common_color(before)
        hud_cells: set[Cell] = set()
        for r in find_regions(before, background=bg_before):
            if _is_hud_band(r, height, width):
                hud_cells |= r["cells"]  # type: ignore[arg-type]
        diff = frame_diff(before, after)
        changed = {c for c in diff["cells"] if c not in hud_cells}  # type: ignore[union-attr]
        if changed:
            self._known_blocked -= changed
            self._probes_effective += 1
        else:
            self._probes_inert += 1

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

        avatar_regions = [r for r in regions if r["color"] == self._avatar_color]
        if not avatar_regions:
            return self._probe(move_ids)
        self._active_cell = avatar_regions[0]["bbox"][:2]  # type: ignore[assignment]

        if self._goal_cell is None:
            self._goal_color, self._goal_cell = _detect_goal(regions, self._avatar_color)
            if self._goal_cell is None:
                return self._probe(move_ids)

        if self._active_cell == self._goal_cell:
            return self._probe(move_ids)

        return self._route(regions, move_ids, action6_ok)

    def _pick_action(self, candidates: list[int], ref_cell: Cell, goal: Cell | None) -> int:
        """Choose among untried ``candidates`` from ``ref_cell``. A
        candidate whose direction has never been measured anywhere is
        tried FIRST, unconditionally -- see admorphiq.adapters25.ka59's
        identical, measured-necessary rationale (a target reachable only
        via an unmeasured direction is invisible to the optimistic
        planner's move set otherwise). Ties among measured candidates
        break by Manhattan distance their predicted destination leaves to
        ``goal``."""
        unmeasured = [a for a in candidates if a not in self._dir_map]
        if unmeasured:
            return unmeasured[0]
        if goal is None:
            return candidates[0]

        def score(action: int) -> int:
            dr, dc = self._dir_map[action]
            dest = (ref_cell[0] + dr, ref_cell[1] + dc)
            return abs(dest[0] - goal[0]) + abs(dest[1] - goal[1])

        return min(candidates, key=score)

    def _probe(self, move_ids: list[int], cell: Cell | None = None) -> GameAction:
        ref_cell = cell if cell is not None else self._active_cell
        self._pending_ref_cell = ref_cell
        if ref_cell is not None:
            tried = self._tried_from.get(ref_cell, set())
            untried = [a for a in move_ids if a not in tried]
            if untried:
                action = self._pick_action(untried, ref_cell, self._goal_cell)
                self._pending_action = action
                self._pending_kind = "move"
                return simple_action(action)
        self._pending_action = move_ids[0]
        self._pending_kind = "move"
        return simple_action(move_ids[0])

    def _optimistic_grid(self, height: int = 64, width: int = 64) -> list[list[bool]]:
        """A ``grid_shortest_path``-shaped passability array: every cell is
        ``True`` (passable) EXCEPT the ones in ``_known_blocked``."""
        grid = [[True] * width for _ in range(height)]
        for r, c in self._known_blocked:
            if 0 <= r < height and 0 <= c < width:
                grid[r][c] = False
        return grid

    @staticmethod
    def _first_step(
        grid: list[list[bool]],
        start: Cell,
        goal: Cell,
        moves: list[Cell],
        move_labels: dict[Cell, int],
    ) -> int | None:
        path = grid_shortest_path(grid, start, goal, moves=moves)
        if not path or len(path) < 2:
            return None
        try:
            return path_to_moves(path[:2], move_labels)[0]
        except ValueError:
            return None

    def _route(self, regions: list[Region], move_ids: list[int], action6_ok: bool) -> GameAction:
        assert self._active_cell is not None and self._goal_cell is not None
        if not self._dir_map:
            return self._probe(move_ids)

        self._pending_ref_cell = self._active_cell
        moves = list(self._dir_map.values())
        move_labels = {unit: action for action, unit in self._dir_map.items()}
        optimistic = self._optimistic_grid()

        step = self._first_step(optimistic, self._active_cell, self._goal_cell, moves, move_labels)
        if step is not None:
            self._pending_action = step
            self._pending_kind = "move"
            return simple_action(step)

        # The optimistic planner found NO route -- try the current cell's
        # own untried actions before considering anything else (see
        # admorphiq.adapters25.ka59's measured ping-pong fix: skipping
        # this check first can trap the avatar switching between cells
        # that each merely "have an untried action" without ever trying
        # one).
        untried_here = [a for a in move_ids if a not in self._tried_from.get(self._active_cell, set())]
        if untried_here:
            action = self._pick_action(untried_here, self._active_cell, self._goal_cell)
            self._pending_action = action
            self._pending_kind = "move"
            return simple_action(action)

        # Broader frontier: any OTHER cell ever stood at with fewer than
        # len(move_ids) actions tried, ranked by proximity to the GOAL.
        frontier_cells = [
            c for c, tried in self._tried_from.items() if len(tried) < len(move_ids) and c != self._active_cell
        ]
        if frontier_cells:
            goal_distances = grid_distance_field(optimistic, [self._goal_cell], moves=moves)
            frontier_cells.sort(key=lambda c: goal_distances.get(c, float("inf")))
            for cell in frontier_cells:
                sub_step = self._first_step(optimistic, self._active_cell, cell, moves, move_labels)
                if sub_step is not None:
                    self._pending_action = sub_step
                    self._pending_kind = "move"
                    return simple_action(sub_step)

        # Truly stuck: every reachable cell (via the optimistic map) is
        # fully explored and none leads toward the goal. Enter the probe
        # phase (see module docstring's walk-stuck-probe-learn-replan
        # loop) rather than give up.
        if action6_ok:
            probe_action = self._probe_button(regions)
            if probe_action is not None:
                return probe_action

        return self._probe(move_ids)

    def _probe_button(self, regions: list[Region]) -> GameAction | None:
        if self._probe_clicks_this_episode >= _PROBE_CLICK_CAP:
            return None
        assert self._active_cell is not None
        candidates = [
            r
            for r in regions
            if r["color"] not in (self._avatar_color, self._goal_color)
            and r["bbox"][:2] not in self._probed_buttons
        ]
        if not candidates:
            return None
        candidates.sort(
            key=lambda r: abs(r["centroid"][0] - self._active_cell[0])  # type: ignore[index]
            + abs(r["centroid"][1] - self._active_cell[1])  # type: ignore[index]
        )
        target = candidates[0]
        cell: Cell = target["bbox"][:2]  # type: ignore[assignment]
        self._probed_buttons.add(cell)
        self._probe_clicks_this_episode += 1
        self._pending_action = None
        self._pending_kind = "probe"
        self._pending_probe_cell = cell
        row, col = (round(target["centroid"][0]), round(target["centroid"][1]))  # type: ignore[index]
        return click_action(x=col, y=row)
