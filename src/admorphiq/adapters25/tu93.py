"""script25 quarantined adapter: TU93 (sliding-maze navigation family).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/TU93.md`` (read for reference, not imported) records
TU93 as a "movement" game, R57's T1 arrival typology, and flags the
LEGACY solver (``tu93_maze``) as brittle -- hardcoded L1/L2 move
sequences that happened to also work on a v2 hash rotation by
coincidence. The refactor plan on that page ("detect walls/floor via
colour, run BFS from player to exit") assumed a STANDARD fixed-step grid
maze; direct measurement below shows that assumption is WRONG for this
game and explains why a fixed-delta BFS was never actually built.

**Offline verification (before any live action)**: loaded
``data/traces/tu93.npz`` (gold trace, label-generation only, never
imported into this adapter). Level 0's gold block is 18 actions
(``min_actions_total``). ``find_regions`` on the first frame (background
colour 5) shows a SMALL set of distinguished regions among ~65 total:
colour 4 (size 1, a single pixel) sits inside colour 9 (size 8, an
8-cell ring around it) -- together these move in lockstep across every
frame (confirmed by tracking both regions' bboxes step by step AND by
:func:`admorphiq.kernels.track_objects` live, which reports BOTH as
"moved" on the very first movement probe). Colour 4 is treated as the
avatar's identifying colour for POSITION tracking (matches every other
script25 adapter's "smallest, uniquely-coloured, moves under ACTION1-4"
signature -- see :meth:`Adapter._observe_result`'s tie-break: the
SMALLEST of the moved regions is picked, a strict generalisation of
"the one moved region" that still trivially selects a single-region
avatar). Colour 9 (the ring) is NOT read for position, but its colour
IS recorded alongside colour 4 in ``_avatar_companion_colors`` -- see
"Goal-detection companion-colour bug" below for why. Colour 14 (size 9,
a single fixed cell far from the start) is the only OTHER singleton
colour -- the goal marker, matching this adapter's own
:func:`_detect_goal` rule (smallest singleton colour excluding every
avatar-associated colour). Colour 6 is a thin bar pinned to row 63 that
SHRINKS across the trace (64 cells at step 0 -> 42 cells at step 17, one
cell per elapsed action) -- an action/step counter HUD, not a game
element; see "HUD detection" below for why the usual span-fraction test
alone does not catch it.

**Mechanic model (the actual surprise): SLIDE-UNTIL-WALL, not a fixed
per-action pixel delta.** Diffing consecutive avatar positions across
the gold trace's own 18 actions showed the SAME action id producing
DIFFERENT deltas depending on where the avatar currently stood (action 4
alone: (0,1), (4,2), (-4,2), (4,2), (0,6), (4,2), (-4,2) across the one
18-step run) -- the opposite of every other script25 movement adapter so
far (dc22/ka59/m0r0 all measured a FIXED per-action pixel vector). This
was VERIFIED LIVE (not trusted from gold alone, per the su15/vc33/dc22
doctrine: offline win-condition/mechanic conclusions have been wrong
before): a live single-episode probe issuing the same action repeatedly
from repeated positions found the SAME action from the SAME cell always
producing the SAME result (a genuine cycle (23,22) -action1-> (20,22)
-action2-> (18,22) -action3-> (23,22) reproduced identically 3 times
across 2 GAME_OVER resets), and different positions producing genuinely
different deltas for the identical action id -- confirming the avatar
SLIDES in the pressed direction until something stops it, landing
wherever that happens to be, and that this is DETERMINISTIC given
(position, action), just not expressible as one fixed vector per action.
A blocked slide (already against a wall in that direction) is a
self-loop: delta (0, 0), a real and useful observation, not an error.

This rules out the fixed-vector ``grid_shortest_path``/``_optimistic_grid``
design every other script25 movement adapter uses (dc22, ka59 after its
own round-3 switch, m0r0) -- there is no single ``moves: list[(dr,dc)]``
that is valid everywhere on this board. Instead this adapter builds an
INCREMENTALLY-DISCOVERED TRANSITION GRAPH: every ``(from_cell, action,
to_cell)`` triple actually observed (self-loops included) is recorded,
and :func:`admorphiq.kernels.transition_shortest_path` finds the
shortest known action sequence to the goal once one exists in the graph.
When the goal is not yet reachable via known edges, the adapter walks to
the nearest already-visited cell that still has an untried action (a
small hand-rolled BFS over the SAME recorded edges -- see
:meth:`Adapter._nearest_untried`; :func:`admorphiq.kernels.reachable_frontier`
was evaluated and NOT used here because its ``transitions`` universe is
already-observed edges only, so it cannot surface a cell's UNTRIED
action the way this adapter's own ``_tried_from`` bookkeeping needs to)
and takes that untried action next, exactly mirroring
``admorphiq.adapters25.dc22``'s own-cell-untried-first /
broader-frontier-second tiering, just over a graph instead of a grid.

**HUD detection**: the usual span-fraction test (a region spanning most
of the frame's width/height while thin) does NOT reliably catch this
game's row-63 counter, because it SHRINKS across a run -- MEASURED to
fall from 64 cells (86% of the 64-wide frame, passes the span test) to
42 cells (65%, FAILS it) within the first 17 actions, and would keep
shrinking. Left uncaught, a long enough run would let the counter shrink
below the goal marker's 9-cell size and get misidentified as "the goal"
by :func:`_detect_goal`'s smallest-singleton-colour rule. Added a second,
measured-necessary test: a thin region PINNED TO A FRAME EDGE (its bbox
touches row 0, the last row, column 0, or the last column) is HUD
regardless of its current width/height -- a genuine game element was
never observed touching a frame edge in this trace (avatar starts at
(16,17), goal at (45,45)-(47,47), neither anywhere near an edge).

**Two bugs found and fixed during the live mechanic-probe (before trusting
this design), both from letting a real live run run all the way rather
than stopping at "it imports and doesn't crash"**:

1. **Identity-discovery stall (same bug class as
   ``admorphiq.adapters25.ka59``'s documented fix)**. The first cut's
   fallback probe picked the SAME first untried action every single call
   whenever ``_active_cell`` was still unknown (nothing populates
   ``_tried_from[None]``), and this game's own action 1 happens to be a
   self-loop from the start cell -- so the avatar never moved and
   identity-by-movement never triggered, MEASURED live: 500 actions, 9
   GAME_OVERs, ``_avatar_color`` still ``None`` throughout. Fixed by
   cycling through ``move_ids`` by ``self._step`` whenever no per-cell
   tried-set applies (:meth:`Adapter._probe`), mirroring ka59's own fix
   for the identical shape of bug.
2. **Goal-detection companion-colour bug**. Once identity discovery
   worked, ``_detect_goal`` immediately misidentified the goal as
   ``(15, 16)`` colour 9 -- the avatar's OWN cosmetic ring, which is also
   a singleton colour and SMALLER (8 cells) than the real goal marker (9
   cells), so "smallest singleton excluding the avatar's colour" picked
   the ring instead. Fixed by recording the FULL set of colours observed
   moving together at identity-discovery time
   (``_avatar_companion_colors``, both colour 4 and colour 9 here) and
   excluding all of them, not just the primary identity colour, from
   goal candidates.

**Smoke results**: 2x500 actions, deterministic: **0/9 levels,
game_score=0.0**. A longer exploratory run (3000 actions, single
sample, NOT part of the standard smoke) reached **2/9 levels,
game_score=0.0002** -- confirming the transition-graph design DOES
connect to and clear levels given enough budget, but the discovery-by-
frontier-expansion approach is inherently far less efficient than a
human's informed navigation (3000 actions for 2 levels vs a ~35-action
human baseline for the same two levels per ``baseline_actions`` in
``data/traces/tu93.npz``'s meta) -- this is the same "exhaustive-search
stumble" pattern the R53 unified-harness round log recorded for other
games under blind frontier search, not a bug. Turning frontier discovery
into an EFFICIENT solve (recognising and reusing the maze's own
structure, e.g. once the goal is connected the route is already
shortest-path-optimal via ``transition_shortest_path`` -- the
inefficiency is entirely in the EXPLORATION phase before that
connection exists) is the natural next lever if this game is revisited.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments the frame into the
    avatar, the goal marker, and (excluded) HUD.
  - :func:`admorphiq.kernels.track_objects` identifies which region
    moved after the FIRST movement probe (before the avatar's colour is
    known at all), exactly mirroring
    ``admorphiq.adapters25.dc22``/``admorphiq.adapters25.ka59``'s
    identity-by-movement technique.
  - :func:`admorphiq.kernels.transition_shortest_path` plans the
    shortest known-edge action sequence from the avatar's current cell
    to the goal over the incrementally-discovered slide graph.
"""

from __future__ import annotations

from collections import Counter, deque
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
from admorphiq.kernels import find_regions, track_objects, transition_shortest_path

GAME_ID = "tu93"

Cell = tuple[int, int]
Region = dict[str, Any]

# Per-level safety cap, mirroring every other script25 adapter's giveup
# convention so the harness never spins forever inside this one.
_GIVEUP_DEFAULT = 4000

# A region spanning at least this fraction of the frame's own span in one
# axis while thin in the other is a HUD status bar. Independently declared
# here (each adapter's role assignments are its own) -- matches su15/sb26/
# dc22's convention.
_HUD_SPAN_FRACTION = 0.85
_HUD_THICKNESS_FRACTION = 0.06


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    r0, c0, r1, c1 = region["bbox"]
    h, w = r1 - r0 + 1, c1 - c0 + 1
    thickness = max(1, int(height * _HUD_THICKNESS_FRACTION))
    thickness_w = max(1, int(width * _HUD_THICKNESS_FRACTION))
    full_width_thin = w >= width * _HUD_SPAN_FRACTION and h <= thickness
    full_height_thin = h >= height * _HUD_SPAN_FRACTION and w <= thickness_w
    # A thin strip PINNED TO A FRAME EDGE, at any width/height -- catches a
    # growing/shrinking counter bar the span-fraction test alone misses
    # once it shrinks past the 85% threshold (measured necessary for
    # this game's row-63 action counter; see module docstring).
    edge_pinned_thin = (h <= thickness and (r0 == 0 or r1 == height - 1)) or (
        w <= thickness_w and (c0 == 0 or c1 == width - 1)
    )
    return full_width_thin or full_height_thin or edge_pinned_thin


def _live_regions(grid: tuple[tuple[int, ...], ...], background: int) -> list[Region]:
    """Non-background, non-HUD regions -- the candidate pool for avatar
    and goal detection alike."""
    if not grid:
        return []
    height, width = len(grid), len(grid[0])
    return [r for r in find_regions(grid, background=background) if not _is_hud_band(r, height, width)]


def _detect_goal(regions: list[Region], exclude_colors: set[int]) -> tuple[int | None, Cell | None]:
    """The SMALLEST singleton-coloured region, excluding every colour in
    ``exclude_colors`` -- see module docstring's "Offline verification"
    section for the offline measurement this is based on. Excludes the
    avatar's FULL colour set (not just its primary identity colour): this
    game's avatar sprite is measured to be TWO co-moving regions (a core
    plus a cosmetic ring), and the ring's colour is ALSO a singleton --
    smaller than the real goal marker -- so excluding only the primary
    identity colour would misidentify the avatar's own ring as the goal
    (measured live, see module docstring)."""
    if not regions:
        return None, None
    color_counts = Counter(r["color"] for r in regions)
    singleton = [r for r in regions if color_counts[r["color"]] == 1 and r["color"] not in exclude_colors]
    if not singleton:
        return None, None
    goal = min(singleton, key=lambda r: r["size"])
    return goal["color"], goal["bbox"][:2]  # type: ignore[index]


class Adapter(GameAdapter):
    """Slide-until-wall maze navigation over an incrementally-discovered
    transition graph, composed from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        # The avatar's own colour, measured once (never hardcoded) the
        # first time a movement genuinely reveals which region moved.
        # Persists across levels and restarts -- the same convention
        # applies to every level of the same game.
        self._avatar_color: int | None = None
        # Every colour observed moving IN LOCKSTEP with the avatar at
        # identity-discovery time (the primary colour plus any cosmetic
        # companion, e.g. this game's own ring around the avatar's core
        # pixel) -- excluded wholesale from goal detection, since a
        # companion colour is also a singleton and can be SMALLER than
        # the real goal marker (measured live; see module docstring).
        self._avatar_companion_colors: set[int] = set()
        self._active_cell: Cell | None = None
        self._goal_color: int | None = None
        self._goal_cell: Cell | None = None

        self._pending_action: int | None = None
        self._pending_ref_cell: Cell | None = None
        self._prev_grid: tuple[tuple[int, ...], ...] | None = None

        # The incrementally-discovered SLIDE graph: every observed
        # (from_cell, action, to_cell) triple, self-loops (blocked
        # slides) included -- see module docstring's "Mechanic model".
        # Persists across levels and restarts: NEW LEVEL means a new
        # maze layout, so this resets on level-up (see _on_level_up) but
        # is kept across a mid-level GAME_OVER restart (the maze itself
        # didn't change, only the current attempt did).
        self._transitions: list[tuple[Cell, int, Cell]] = []
        self._tried_from: dict[Cell, set[int]] = {}

        # Diagnostic-only counters.
        self._edges_learned = 0
        self._self_loops = 0

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
            self._pending_ref_cell = None
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

        action = self._decide(grid, move_ids)
        self._prev_grid = grid
        return action

    # ── level / restart bookkeeping ─────────────────────────────────────

    def _on_level_up(self, levels: int) -> None:
        self._levels_seen = levels
        self._pending_action = None
        self._pending_ref_cell = None
        self._prev_grid = None
        self._active_cell = None
        self._goal_color = None
        self._goal_cell = None
        self._transitions = []
        self._tried_from = {}

    def _on_restart(self) -> None:
        """Only the avatar's own position resets; the learned slide graph
        (``_transitions``/``_tried_from``) is kept -- the maze layout
        didn't change, only the current attempt did."""
        self._pending_action = None
        self._pending_ref_cell = None
        self._prev_grid = None
        self._active_cell = None

    # ── measurement: did the pending action do anything? ────────────────

    def _observe_result(self, grid: tuple[tuple[int, ...], ...]) -> None:
        action = self._pending_action
        ref_cell = self._pending_ref_cell
        prev_grid = self._prev_grid
        self._pending_action = None
        self._pending_ref_cell = None
        if prev_grid is None or action is None:
            return

        bg_prev = most_common_color(prev_grid)
        prev_regions = _live_regions(prev_grid, bg_prev)

        if self._avatar_color is None:
            bg_cur = most_common_color(grid)
            cur_regions = _live_regions(grid, bg_cur)
            tracked = track_objects(prev_regions, cur_regions)
            moved = [m for m in tracked["matches"] if tuple(m["shift"]) != (0, 0)]  # type: ignore[arg-type]
            if not moved:
                return
            # This game's avatar sprite is TWO co-moving regions (a
            # single-pixel core plus a cosmetic ring around it, MEASURED
            # from the gold trace and confirmed live) -- track_objects
            # correctly reports BOTH as moved, so "exactly one moved
            # region" (dc22/ka59's identity test) never fires here. Pick
            # the SMALLEST moved region as the identity anchor: a compact
            # marker is the more precise reference point, and this is a
            # strict generalisation of "the one moved region" for a
            # single-region avatar (trivially still picks it).
            match = min(moved, key=lambda m: prev_regions[m["before"]]["size"])  # type: ignore[index]
            from_cell: Cell = prev_regions[match["before"]]["bbox"][:2]  # type: ignore[index]
            shift: Cell = tuple(match["shift"])  # type: ignore[assignment]
            self._avatar_color = prev_regions[match["before"]]["color"]  # type: ignore[assignment]
            self._avatar_companion_colors = {prev_regions[m["before"]]["color"] for m in moved}  # type: ignore[index]
            to_cell = (from_cell[0] + shift[0], from_cell[1] + shift[1])
            self._record_transition(from_cell, action, to_cell)
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
        to_cell: Cell = cur_avatar_regions[0]["bbox"][:2]  # type: ignore[assignment]
        self._record_transition(ref_cell, action, to_cell)

    def _record_transition(self, from_cell: Cell, action: int, to_cell: Cell) -> None:
        self._transitions.append((from_cell, action, to_cell))
        self._tried_from.setdefault(from_cell, set()).add(action)
        if to_cell == from_cell:
            self._self_loops += 1
        else:
            self._edges_learned += 1

    # ── planning ─────────────────────────────────────────────────────────

    def _decide(self, grid: tuple[tuple[int, ...], ...], move_ids: list[int]) -> GameAction:
        if not move_ids:
            self._pending_action = None
            self._pending_ref_cell = None
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
            self._goal_color, self._goal_cell = _detect_goal(regions, self._avatar_companion_colors)
            if self._goal_cell is None:
                return self._probe(move_ids)

        if self._active_cell == self._goal_cell:
            return self._probe(move_ids)

        return self._route(move_ids)

    def _probe(self, move_ids: list[int]) -> GameAction:
        ref_cell = self._active_cell
        self._pending_ref_cell = ref_cell
        if ref_cell is not None:
            tried = self._tried_from.get(ref_cell, set())
            untried = [a for a in move_ids if a not in tried]
            if untried:
                action = untried[0]
                self._pending_action = action
                return simple_action(action)
        # No ref_cell (avatar identity not yet known) or every action
        # already tried from this cell -- cycle by step rather than
        # repeat one fixed action forever. MEASURED necessary: this
        # game's own action 1 is a self-loop (no-op) from the start
        # cell, so a fixed first-pick probe would never move the avatar
        # and identity-by-movement would never trigger (same bug class
        # documented and fixed in admorphiq.adapters25.ka59).
        action = move_ids[self._step % len(move_ids)]
        self._pending_action = action
        return simple_action(action)

    def _nearest_untried(self, move_ids: list[int]) -> Cell | None:
        """BFS over the KNOWN slide graph from ``_active_cell``; returns
        the nearest cell (including ``_active_cell`` itself, distance 0)
        that still has an action in ``move_ids`` not yet recorded in
        ``_tried_from``, or None if every reachable cell has been fully
        explored. Hand-rolled rather than
        :func:`admorphiq.kernels.reachable_frontier` -- see module
        docstring for why that kernel's "already-observed edges only"
        universe doesn't fit "find an UNTRIED action" here."""
        assert self._active_cell is not None
        edges: dict[Cell, dict[int, Cell]] = {}
        for state, action, nxt in self._transitions:
            edges.setdefault(state, {})[action] = nxt
        visited = {self._active_cell}
        queue: deque[Cell] = deque([self._active_cell])
        while queue:
            cell = queue.popleft()
            tried_here = self._tried_from.get(cell, set())
            if any(a not in tried_here for a in move_ids):
                return cell
            for _action, nxt in edges.get(cell, {}).items():
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        return None

    def _route(self, move_ids: list[int]) -> GameAction:
        assert self._active_cell is not None and self._goal_cell is not None
        self._pending_ref_cell = self._active_cell

        path = transition_shortest_path(self._transitions, self._active_cell, self._goal_cell)
        if path:
            action = path[0]
            self._pending_action = action
            return simple_action(action)  # type: ignore[arg-type]

        # The goal isn't (yet) connected in the known graph -- expand
        # toward the nearest cell that still has an untried action.
        target_cell = self._nearest_untried(move_ids)
        if target_cell is not None:
            if target_cell == self._active_cell:
                untried = [a for a in move_ids if a not in self._tried_from.get(self._active_cell, set())]
                action = untried[0]
            else:
                sub_path = transition_shortest_path(self._transitions, self._active_cell, target_cell)
                action = sub_path[0] if sub_path else move_ids[0]  # type: ignore[assignment]
            self._pending_action = action
            return simple_action(action)

        # Every reachable cell has been fully explored and the goal is
        # still not connected -- nothing more to learn from here; take
        # any action rather than stall (mirrors every other adapter's
        # exhausted fallback).
        self._pending_action = move_ids[0]
        return simple_action(move_ids[0])
