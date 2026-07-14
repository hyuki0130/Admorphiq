"""script25 quarantined adapter: M0R0 (mirrored-maze navigation family).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

**Second backport (this revision, R56 2026-07-15)**: replaces the FIRST
backport's "declare the mirror partner's current position as a fixed goal
cell, then run single-agent shortest-path toward it" model (measured 0/6
at both 500 and 3000 actions -- see the round page's Open items) with a
genuine JOINT-STATE planner. The first backport's own bug: EVERY action
moves BOTH pieces simultaneously (see "Joint dynamics" below), so
"path-plan SELF toward wherever the partner currently sits" is asking the
wrong question -- the partner is not a stationary or independently-moving
obstacle, it is the OTHER HALF of a single joint action's effect. Treating
it as a fixed waypoint means the "target" moves out from under the plan
on every single step.

**Joint dynamics -- MEASURED live (this file never reads
``data/traces/m0r0.npz`` at runtime; that file was consulted OFFLINE,
dev-time only, to design this measurement, exactly as every other
adapter's offline-investigation discipline works). Confirmed by
re-deriving the same result from the gold trace across BOTH captured
levels (different measured cell sizes, 5px level 0 / 4px level 1) with
zero game-title/id branching in the code below**:

- SELF and the mirror PARTNER share one colour; the SAME action id moves
  BOTH regions on the SAME frame.
- Each side's own resulting displacement is measured independently and
  can be BLOCKED independently (a wall stops one side's movement while
  the other side moves freely under the identical action) -- gold's own
  solution deliberately exploits this to break/restore row-sync between
  the two pieces (see "Win condition" below).
- No FIXED horizontal/vertical split is assumed in the CODE (that would
  be baking one level's observed shape in as a game-wide constant) --
  ``_partner_dir_map`` is measured the same way ``_dir_map`` always was,
  action by action, independently. It happens to come out antisymmetric
  in one axis and symmetric in the other on both captured levels, but
  the planner below works from whatever is actually measured, not from
  that expectation.
- The per-axis PIXEL SCALE is a property of THIS level's own grid, not
  the game (measured directly: level 0 stepped 5px/action, level 1
  4px/action) -- both dir_maps' MAGNITUDES are reset (not carried over)
  on level-up, always replaced by a fresh clean measurement. The SIGN of
  each action's direction (which button is up/down/left/right, per side)
  DOES transfer across levels -- that part of the control scheme is a
  genuine game-wide constant -- and is kept in ``_dir_sign``/
  ``_partner_dir_sign`` to disambiguate the first re-measurement on a new
  level when more than one same-radius candidate exists.

**Win condition -- measured, NOT assumed uniform across levels (a real
finding, not a guess)**: aggregating every WIN-triggering transition
across all 5 repeated gold demonstrations of level 0 and level 1 (10
transitions total, byte-identical geometry within each level, so this is
reproducible, not noise):

- Level 0: win fires when the two regions' bboxes become COLUMN-adjacent
  (touching, closing the column gap fully to 0) -- and level 0's row gap
  is 0 throughout its entire captured trace (no asymmetric vertical block
  ever occurs), so this alone is also "both axes simultaneously at their
  own floor".
- Level 1: win fires when the ROW gap closes to exactly 0 via a
  successful (one-side-blocked) vertical action -- but the COLUMN gap at
  that exact moment is a nonzero 4px (one full measured cell), NOT
  touching. Tracing the full 40-action gold sequence shows this 4px
  column gap is itself a WALL-CAPPED FLOOR: an earlier inward-closing
  action at the identical 4px gap produces `(0, 0)` on BOTH sides
  simultaneously (neither side can close it further), and row-gap==0
  alone is reached MANY times earlier in the same trace WITHOUT winning
  (steps where column gap is still 12-36px) -- so row-gap==0 is necessary
  but not sufficient either; level 1's win is the moment row-gap==0 is
  achieved WHILE column-gap is independently already pinned at its own
  floor.
- Combined, well-evidenced hypothesis: **win = a joint state where BOTH
  axes are simultaneously at their own wall-capped minimum gap** (that
  floor is 0 when unobstructed, or a positive wall-capped value
  otherwise -- discovered by search, never hardcoded). This is NOT
  proven for a third, unseen M0R0-family level, so the planner below
  never hardcodes a specific target gap -- it greedily hill-climbs toward
  smaller total gap using the MEASURED joint dynamics and lets the live
  engine's own WIN signal (``is_done()`` / ``state_name()``) be the only
  authority on whether a given joint state actually won. A state that
  looks gap-minimal but doesn't win simply becomes the new starting point
  for another round of hill-climbing.

**Planner**: ``kernels.configuration_path`` (generic BFS over a
caller-supplied state space) searches the JOINT state ``(self_cell,
partner_cell)`` for the shortest path to any REACHABLE state with a
strictly smaller combined gap than the current one -- a greedy
hill-climbing step, re-planned every single decision (existing
``_route``-style single-step replanning), not a one-shot fixed target.
Each side's own movement in the search uses the SAME optimistic
passability convention as every other script25 adapter: a destination
cell is assumed passable unless CONFIRMED blocked by an earlier failed
attempt (``_known_blocked`` for self, ``_partner_known_blocked`` for the
partner -- two independent sets, since the two sides are independently
blockable). When no improving state is reachable within budget, the
adapter falls back to trying the current joint state's own untried
actions (to discover new walls) exactly like the pre-existing
``_probe``/frontier mechanism.

A minimal DC22-style singleton-marker fallback is kept for the
(unobserved-in-gold, but not ruled out for a private-set variant) case
where no second same-coloured region is ever seen this level at all --
i.e. a genuinely non-mirrored M0R0-family level.

Kept unchanged from the first backport (still correct, not touched by
this revision): GAME_OVER handling via ``_on_restart`` (preserves every
learned wall/hazard fact, only resets the current attempt's tracked
position -- matches DC22's own control-flow shape), hazard-memory
(``_hazards``/``_dead_cells``, dead-cell threshold), and SELF's own
identity re-acquisition after a restart via nearest-to-level-start-cell
(never an arbitrary "first same-coloured region", to avoid ever locking
onto the partner by mistake).

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` + :func:`admorphiq.kernels.track_objects`
    identify SELF (mirroring ``admorphiq.adapters25.dc22``'s
    identity-by-movement technique) and, every call thereafter, the
    CURRENT partner position.
  - :func:`admorphiq.kernels.configuration_path` searches the JOINT state
    space for a gap-improving move, using the measured per-side dynamics
    and per-side optimistic passability.

Hazard memory (kept from the first backport, unchanged in spirit -- this
game's own GAME_OVER trap is orthogonal to the goal-direction model): a
first smoke run measured GAME_OVER at 151 actions with 0 levels cleared,
so this adapter keeps ``restart_on_game_over = True`` and tracks (cell,
action) pairs that trigger a fatal reposition -- :meth:`_observe_result`
detects this two ways: (a) the harness's own explicit ``state ==
"GAME_OVER"``, handled via :meth:`_on_restart` (preserves every learned
fact, only resets the current attempt's position); (b) a SILENT
reposition (the frame snaps back to the exact start-of-level frame while
this adapter's own tracked position was mid-maze) for any engine that
never reports an explicit GAME_OVER state for this outcome. Either way, a
cell hazardous under >= ``_DEAD_CELL_HAZARD_THRESHOLD`` distinct actions
is excluded from the joint search entirely, persisted across restarts
within a level, and reset on level-up alongside the rest of the spatial
state.
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
from admorphiq.kernels import configuration_path, find_regions, track_objects

GAME_ID = "m0r0"

Cell = tuple[int, int]
Region = dict[str, Any]
JointState = tuple[Cell, Cell]

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

# Bound on how many joint states configuration_path expands per decision --
# a joint state space can be much larger than a single-agent one (product
# of two positions), so this is deliberately smaller than a single-agent
# search's typical budget; a hill-climbing step only needs to find ONE
# improving state, not exhaustively map the space.
_JOINT_SEARCH_BUDGET = 4000


def _manhattan(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _sign(v: int) -> int:
    if v > 0:
        return 1
    if v < 0:
        return -1
    return 0


def _cell_sign(shift: Cell) -> Cell:
    return (_sign(shift[0]), _sign(shift[1]))


def _magnitude(shift: Cell) -> int:
    return abs(shift[0]) + abs(shift[1])


def _rematch_radius(dir_map: dict[int, Cell]) -> int:
    """Bound for a bounded nearest-match re-measurement, from PEER
    magnitudes already confirmed for this same piece/level (never a fixed
    constant -- see ``_observe_piece``'s docstring for the bug this
    replaces).

    Once >=1 action's magnitude is confirmed this level, a fresh
    measurement is accepted only within 2x the MEDIAN confirmed magnitude
    -- an outlier candidate that far from every peer is rejected outright
    rather than stored, because a wrong move vocabulary poisons every
    joint-state plan built from it afterward (measured directly: a
    spurious match at a fixed 20px radius produced a (0, -20) magnitude
    while three peer actions all correctly measured 4, corrupting
    ``_joint_successors``' own move set for the rest of the level).

    Before any peer exists (the very first action measured this level for
    this piece), falls back to a conservative absolute cap -- both
    per-level pixel scales measured so far (4px, 5px) sit comfortably
    under it, so it constrains the very first guess without assuming a
    specific scale."""
    if not dir_map:
        return 8
    magnitudes = sorted(_magnitude(v) for v in dir_map.values())
    n = len(magnitudes)
    median = magnitudes[n // 2] if n % 2 else (magnitudes[n // 2 - 1] + magnitudes[n // 2]) / 2
    return max(1, int(2 * median))


def _gap_score(self_cell: Cell, partner_cell: Cell) -> int:
    """Combined row+column separation between the two pieces -- the
    quantity the joint planner hill-climbs downward. A plain Manhattan
    distance: no axis-specific "closing direction" is assumed here (that
    would bake in the measured-but-not-guaranteed-universal horizontal/
    vertical split from the module docstring); the planner only needs
    SOME scalar that decreases as the pieces approach whatever
    configuration the live engine considers a win, and Manhattan distance
    decreases under both observed win patterns (level 0's full column
    closure and level 1's row closure)."""
    return _manhattan(self_cell, partner_cell)


def _detect_singleton_marker(regions: list[Region], self_color: int | None) -> Cell | None:
    """DC22-style fallback goal: the smallest singleton-coloured region
    excluding SELF's own colour. Used ONLY when no second SELF-coloured
    region has EVER been observed this level -- i.e. a level that turns
    out not to use the mirror-partner mechanic both captured gold levels
    showed. Not exercised by either captured level; kept as a documented,
    narrow safety net for an unseen variant, not the primary path."""
    if not regions:
        return None
    color_counts = Counter(r["color"] for r in regions)
    singleton = [r for r in regions if color_counts[r["color"]] == 1 and r["color"] != self_color]
    if not singleton:
        return None
    goal = min(singleton, key=lambda r: r["size"])
    return goal["bbox"][:2]  # type: ignore[index]


class Adapter(GameAdapter):
    """Joint-state hill-climbing navigation composed entirely from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        # action_id -> CONFIRMED pixel delta (dr, dc) of SELF's / the
        # PARTNER's own region, for THIS level. Reset (not persisted) on
        # level-up: the per-axis pixel SCALE is a property of the level's
        # own grid, not the game (measured: 5px/action on one level,
        # 4px/action on another), so a magnitude carried over from a
        # different level is actively wrong, not just stale.
        self._dir_map: dict[int, Cell] = {}
        self._partner_dir_map: dict[int, Cell] = {}
        # action_id -> measured SIGN (-1/0/+1 per axis), one per side. This
        # DOES persist across levels/restarts (the control scheme is a
        # game-wide constant) and seeds disambiguation the first time an
        # action is re-measured on a new level (see _observe_piece).
        self._dir_sign: dict[int, Cell] = {}
        self._partner_dir_sign: dict[int, Cell] = {}
        self._self_color: int | None = None
        self._active_cell: Cell | None = None
        # The partner's current position, re-read fresh every call (never
        # cached) -- see module docstring's "Joint dynamics": the partner
        # moves on every action, so a stale position is wrong immediately.
        self._partner_cell: Cell | None = None
        # True once a second SELF-coloured region has been directly
        # observed at least once this level -- gates the DC22-style
        # singleton fallback (see _detect_singleton_marker).
        self._partner_ever_seen = False
        # Fallback-only static goal (singleton marker), used exclusively
        # when no partner has ever been seen this level.
        self._marker_cell: Cell | None = None

        self._pending_action: int | None = None
        self._pending_ref_cell: Cell | None = None
        self._pending_partner_ref_cell: Cell | None = None
        self._prev_grid: tuple[tuple[int, ...], ...] | None = None
        # A multi-hop gap-improving plan from configuration_path, drained
        # ONE action per decision instead of being recomputed from scratch
        # every step -- necessary because a genuine improving path can
        # require a temporary WORSENING hop (gold's own solution
        # deliberately desyncs row-alignment before resyncing it), and
        # re-deriving "does gap improve relative to the new, worse
        # baseline" every single step degenerates into undoing the very
        # first hop forever (measured directly via a live diagnostic: an
        # infinite gap=10<->20 oscillation, worsen then "improve" back to
        # exactly where it started). ``_pending_plan_expected`` is the
        # joint state the plan predicts AFTER each queued action, checked
        # against the ACTUAL observed state before every drain -- a
        # newly-discovered wall invalidates the rest of the plan rather
        # than blindly continuing it.
        self._pending_plan: list[int] = []
        self._pending_plan_expected: list[JointState] = []
        # The very first frame seen this level (post-reset frames snap back
        # to this exactly) -- see _observe_result's silent-reposition
        # detector.
        self._level_start_grid: tuple[tuple[int, ...], ...] | None = None
        # SELF's / the partner's own position the first time each was ever
        # measured this level (cached once). Used to re-acquire identity
        # after ANY restart (_active_cell/_partner_cell go back to None)
        # among the >= 1 same-coloured regions on the board --
        # nearest-to-start-position is a robust, measured-necessary
        # disambiguator, since picking an arbitrary same-coloured region
        # would risk swapping the two pieces' identities.
        self._level_start_cell: Cell | None = None
        self._partner_start_cell: Cell | None = None

        self._tried_from: dict[Cell, set[int]] = {}
        self._partner_tried_from: dict[Cell, set[int]] = {}
        # Cells CONFIRMED blocked, one set per side -- the two pieces are
        # independently blockable (see module docstring). Every other cell
        # is OPTIMISTICALLY assumed passable; nothing removes a cell once
        # added (no button/toggle mechanic in this game, unlike DC22).
        self._known_blocked: set[Cell] = set()
        self._partner_known_blocked: set[Cell] = set()

        # (cell, action) pairs that triggered a fatal reposition. Persists
        # across restarts WITHIN a level (a property of the layout);
        # cleared on level-up alongside every other spatial fact. Kept from
        # the first backport, unchanged in spirit.
        self._hazards: dict[Cell, set[int]] = {}
        # Cells hazardous under >= _DEAD_CELL_HAZARD_THRESHOLD distinct
        # actions -- excluded from the joint search entirely (see
        # _joint_successors). Persists like _hazards.
        self._dead_cells: set[Cell] = set()

        self._replans = 0

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            # A fatal reposition just happened, but the maze layout (walls,
            # hazards) didn't change -- only the current attempt did.
            # Matches DC22's own correct GAME_OVER handling.
            self._on_restart()
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._pending_action = None
            self._pending_ref_cell = None
            self._pending_partner_ref_cell = None
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
        """Drop every SPATIAL fact about the level just left, INCLUDING
        both dir_maps' confirmed magnitudes (a property of THIS level's
        own grid, not the game -- see module docstring). dir_sign for
        both sides survives -- the control scheme itself is a game-wide
        constant."""
        self._levels_seen = levels
        self._pending_action = None
        self._pending_ref_cell = None
        self._pending_partner_ref_cell = None
        self._pending_plan = []
        self._pending_plan_expected = []
        self._prev_grid = None
        self._level_start_grid = grid
        self._level_start_cell = None
        self._partner_start_cell = None
        self._active_cell = None
        self._partner_cell = None
        self._partner_ever_seen = False
        self._marker_cell = None
        self._tried_from = {}
        self._partner_tried_from = {}
        self._known_blocked = set()
        self._partner_known_blocked = set()
        self._hazards = {}
        self._dead_cells = set()
        self._dir_map = {}
        self._partner_dir_map = {}

    def _on_restart(self) -> None:
        """Only the two pieces' own tracked positions reset; every fact
        already learned about the layout (dir_maps, known_blocked sets,
        hazards, dead_cells, tried_from) remains true (the maze didn't
        change, only the attempt did) and is deliberately KEPT so each
        life compounds on the last instead of re-exploring from scratch
        every time. The queued multi-hop plan is dropped -- a restart
        means something just went wrong (a hazard), so re-planning fresh
        from whatever position is re-acquired is safer than blindly
        continuing a plan computed for the pre-restart position."""
        self._pending_action = None
        self._pending_ref_cell = None
        self._pending_partner_ref_cell = None
        self._pending_plan = []
        self._pending_plan_expected = []
        self._prev_grid = None
        self._active_cell = None
        self._partner_cell = None

    # ── measurement: did the pending action move SELF / the partner? ───

    def _observe_result(self, grid: tuple[tuple[int, ...], ...]) -> None:
        action = self._pending_action
        ref_cell = self._pending_ref_cell
        partner_ref_cell = self._pending_partner_ref_cell
        before = self._prev_grid
        self._pending_action = None
        self._pending_ref_cell = None
        self._pending_partner_ref_cell = None
        if action is None or before is None:
            return

        # A SILENT reposition: the frame snaps back to the exact
        # level-start frame while this adapter's own tracking still holds
        # a position DIFFERENT from where SELF started this level -- a
        # fatal reposition just happened without the harness ever
        # reporting an explicit GAME_OVER state for it.
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
            self._dir_sign[action] = _cell_sign(shift)
            self._tried_from.setdefault(from_cell, set()).add(action)
            self._active_cell = (from_cell[0] + shift[0], from_cell[1] + shift[1])
            return

        bg_cur = most_common_color(grid)
        same_colour_cur = [r for r in find_regions(grid, background=bg_cur) if r["color"] == self._self_color]

        if ref_cell is not None:
            new_self = self._observe_piece(
                ref_cell,
                action,
                same_colour_cur,
                self._dir_map,
                self._dir_sign,
                self._tried_from,
                self._known_blocked,
                exclude_cell=None,
            )
            if new_self is not None:
                self._active_cell = new_self

        if partner_ref_cell is not None:
            new_partner = self._observe_piece(
                partner_ref_cell,
                action,
                same_colour_cur,
                self._partner_dir_map,
                self._partner_dir_sign,
                self._partner_tried_from,
                self._partner_known_blocked,
                # Never let the partner-tracking match land on SELF's own
                # just-updated cell -- the two pieces share a colour, so
                # without this exclusion a frame where the partner didn't
                # move could nearest-match onto SELF instead (measured-
                # necessary the same way SELF's own ref_cell-first
                # discipline was, see _observe_piece's docstring).
                exclude_cell=self._active_cell,
            )
            if new_partner is not None:
                self._partner_cell = new_partner
                if self._partner_start_cell is None:
                    self._partner_start_cell = new_partner
                self._partner_ever_seen = True
            else:
                # No separate partner region this frame -- either merged
                # with SELF (about to win, or already did) or genuinely
                # not present. Never fabricated from an unrelated region;
                # simply left unknown for this frame.
                self._partner_cell = None

    def _observe_piece(
        self,
        ref_cell: Cell,
        action: int,
        same_colour_cur: list[Region],
        dir_map: dict[int, Cell],
        dir_sign: dict[int, Cell],
        tried_from: dict[Cell, set[int]],
        known_blocked: set[Cell],
        exclude_cell: Cell | None,
    ) -> Cell | None:
        """Generic single-piece movement measurement, used for BOTH SELF
        and the partner (same exact-match-first logic, parameterized by
        which dir_map/dir_sign/tried_from/known_blocked to update).
        ``ref_cell`` is where this piece was BEFORE the action (recorded
        by the caller before issuing it, never re-derived by fuzzy
        matching). Returns the piece's new cell, or ``None`` if it can't
        be identified this frame (e.g. it merged with the other piece, or
        genuinely vanished) -- callers must NOT overwrite their own
        tracked cell with ``None``.

        EXACT position checks first (never fuzzy nearest-match when the
        possibilities are known): either this piece is still exactly at
        ref_cell (blocked) or exactly at the PREDICTED destination
        (dir_map[action], once CONFIRMED this level -- dir_map is reset
        every level-up, so this is always a same-level confirmation, never
        a stale cross-level guess) -- a same-coloured OTHER piece can sit
        CLOSER to ref_cell than this piece's own true post-action position
        on some frames, so "nearest region to ref_cell" would silently
        lock onto the wrong piece.

        When the magnitude is unconfirmed for THIS level (never measured
        yet, or wiped at level-up because a different level's pixel scale
        doesn't transfer -- see module docstring), falls through to a
        bounded nearest-match re-measurement, preferring whichever
        candidate matches dir_sign's PRIOR direction for this action (the
        control scheme DOES transfer across levels) as a tie-break before
        plain nearest. The bound itself is PEER-relative, not a fixed
        constant -- see ``_rematch_radius``'s docstring for the exact bug
        (a spurious 20px-boundary match) this replaces: once >=1 action's
        magnitude is already confirmed for this piece/level, a candidate
        farther than 2x the median confirmed magnitude is an outlier and
        is REJECTED outright (this action stays unconfirmed for the next
        genuine attempt) rather than ever being stored -- a wrong move
        vocabulary poisons every plan built from it afterward."""
        candidates = [r for r in same_colour_cur if exclude_cell is None or r["bbox"][:2] != exclude_cell]
        cur_cells = {r["bbox"][:2] for r in candidates}

        predicted = dir_map.get(action)
        if predicted is not None:
            dest = (ref_cell[0] + predicted[0], ref_cell[1] + predicted[1])
            if dest in cur_cells:
                tried_from.setdefault(ref_cell, set()).add(action)
                return dest
            if ref_cell in cur_cells:
                self._record_blocked(ref_cell, action, dir_map, tried_from, known_blocked)
                return ref_cell
            # Neither exact position holds -- a genuine within-level
            # anomaly (e.g. a coupling side-effect) after this action's
            # magnitude was already confirmed once this level. Record
            # tried without touching dir_map from an unreliable guess.
            tried_from.setdefault(ref_cell, set()).add(action)
            return None

        radius = _rematch_radius(dir_map)
        radius_candidates = [r for r in candidates if _manhattan(r["bbox"][:2], ref_cell) <= radius]
        if not radius_candidates:
            # Every candidate is an outlier relative to this piece's own
            # peer-confirmed magnitudes (or, pre-peer, past the
            # conservative absolute cap) -- reject rather than guess; this
            # action's magnitude stays unconfirmed, never poisoned.
            tried_from.setdefault(ref_cell, set()).add(action)
            return None
        prior_sign = dir_sign.get(action)
        if prior_sign is not None:
            sign_matched = [
                r
                for r in radius_candidates
                if _cell_sign(tuple(a - b for a, b in zip(r["bbox"][:2], ref_cell))) == prior_sign  # type: ignore[arg-type]
            ]
            if sign_matched:
                radius_candidates = sign_matched
        near = min(radius_candidates, key=lambda r: _manhattan(r["bbox"][:2], ref_cell))
        new_cell: Cell = near["bbox"][:2]  # type: ignore[assignment]
        if new_cell == ref_cell:
            self._record_blocked(ref_cell, action, dir_map, tried_from, known_blocked)
            return ref_cell
        shift = (new_cell[0] - ref_cell[0], new_cell[1] - ref_cell[1])
        dir_map[action] = shift
        dir_sign[action] = _cell_sign(shift)
        tried_from.setdefault(ref_cell, set()).add(action)
        return new_cell

    def _record_blocked(
        self,
        cell: Cell,
        action: int,
        dir_map: dict[int, Cell],
        tried_from: dict[Cell, set[int]],
        known_blocked: set[Cell],
    ) -> None:
        """Mark ``action`` tried from ``cell`` for whichever piece owns
        ``dir_map``/``tried_from``/``known_blocked``, and if its measured
        direction is known, add the refuted destination to
        ``known_blocked`` -- the fact the joint search reads to stop
        assuming that destination passable for THIS side."""
        tried_from.setdefault(cell, set()).add(action)
        unit = dir_map.get(action)
        if unit is None:
            return
        dest = (cell[0] + unit[0], cell[1] + unit[1])
        if dest not in known_blocked:
            known_blocked.add(dest)
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
        # region found"), since the partner (same colour) can otherwise be
        # picked up as SELF by mistake.
        ref = self._active_cell if self._active_cell is not None else self._level_start_cell
        if ref is None:
            ref = self_regions[0]["bbox"][:2]  # type: ignore[assignment]
        self._active_cell = min(self_regions, key=lambda r: _manhattan(r["bbox"][:2], ref))["bbox"][:2]  # type: ignore[assignment]

        partner_ref = self._partner_cell if self._partner_cell is not None else self._partner_start_cell
        partner_candidates = [r for r in self_regions if r["bbox"][:2] != self._active_cell]
        if partner_candidates:
            if partner_ref is not None:
                self._partner_cell = min(
                    partner_candidates, key=lambda r: _manhattan(r["bbox"][:2], partner_ref)
                )["bbox"][:2]  # type: ignore[assignment]
            else:
                self._partner_cell = partner_candidates[0]["bbox"][:2]  # type: ignore[assignment]
            self._partner_ever_seen = True
        else:
            self._partner_cell = None

        if self._partner_cell is not None:
            self._marker_cell = None
            if self._active_cell == self._partner_cell:
                # Degenerate: exact overlap already (should be rare -- a
                # true merge usually collapses to ONE region instead --
                # but if it happens, there's nothing left to close).
                return self._probe(move_ids)
            return self._route_joint(move_ids)

        if self._partner_ever_seen:
            # The partner was seen before but isn't visible THIS frame --
            # most likely merged with SELF (i.e. very likely already won,
            # or about to be on the next is_done() check). Never fabricate
            # a goal from an unrelated region here; just idle/probe and
            # let the harness's own WIN check decide.
            return self._probe(move_ids)

        # No partner ever observed this level at all -- fall back to the
        # DC22-style singleton-marker reading for a non-mirrored variant.
        if self._marker_cell is None:
            self._marker_cell = _detect_singleton_marker(regions, self._self_color)
        if self._marker_cell is None:
            return self._probe(move_ids)
        if self._active_cell == self._marker_cell:
            return self._probe(move_ids)
        return self._route_to_marker(move_ids)

    def _joint_successors(self, move_ids: list[int]):
        """Closure over the CURRENT measured dynamics/known-blocked sets,
        shaped exactly as ``kernels.configuration_path`` requires:
        ``state -> iterable of (action, next_state)``. Only actions
        measured for BOTH sides participate -- an action unmeasured for
        either side has no predictable joint effect yet (bootstrapped
        separately via ``_probe``, matching the existing "measure unknown
        actions first" discipline)."""
        usable = [a for a in move_ids if a in self._dir_map and a in self._partner_dir_map]

        def successors(state: JointState):
            self_cell, partner_cell = state
            for action in usable:
                s_delta = self._dir_map[action]
                p_delta = self._partner_dir_map[action]
                s_dest = (self_cell[0] + s_delta[0], self_cell[1] + s_delta[1])
                p_dest = (partner_cell[0] + p_delta[0], partner_cell[1] + p_delta[1])
                s_next = self_cell if s_dest in self._known_blocked or s_dest in self._dead_cells else s_dest
                p_next = (
                    partner_cell
                    if p_dest in self._partner_known_blocked or p_dest in self._dead_cells
                    else p_dest
                )
                next_state = (s_next, p_next)
                if next_state == state:
                    continue
                yield action, next_state

        return successors

    def _route_joint(self, move_ids: list[int]) -> int:
        assert self._active_cell is not None and self._partner_cell is not None
        state: JointState = (self._active_cell, self._partner_cell)

        self._pending_ref_cell = self._active_cell
        self._pending_partner_ref_cell = self._partner_cell

        # Drain a QUEUED plan when reality still matches its prediction --
        # see __init__'s docstring for why single-step replanning breaks a
        # genuine "worsen then improve" detour (measured directly: an
        # infinite gap oscillation). A mismatch (a newly-discovered wall
        # changed what's actually reachable) drops the rest of the plan
        # and falls through to a fresh search below.
        if self._pending_plan_expected and self._pending_plan_expected[0] == state:
            action = self._pending_plan.pop(0)
            self._pending_plan_expected.pop(0)
            return action
        self._pending_plan = []
        self._pending_plan_expected = []

        current_gap = _gap_score(*state)

        if self._dir_map and self._partner_dir_map:
            successors = self._joint_successors(move_ids)

            def goal_test(s: JointState) -> bool:
                return _gap_score(*s) < current_gap

            path = configuration_path(state, goal_test, successors, max_states=_JOINT_SEARCH_BUDGET)
            if path:
                # configuration_path returns only action LABELS -- replay
                # them through the SAME successors closure to recover the
                # state EACH hop expects to find itself in BEFORE it runs
                # (its precondition), so later hops can be validated
                # against reality before executing (see __init__'s
                # docstring). expected_states[i] is the state produced by
                # path[i] -- i.e. the precondition for path[i+1] -- so
                # pending_plan (path[1:]) pairs with expected_states[:-1]
                # (drop the FINAL state, which is the goal itself and has
                # no further queued action to precede). Deterministic and
                # cheap: this is the identical closure BFS just searched
                # with.
                expected_states: list[JointState] = []
                cur = state
                for step_action in path:
                    cur = next(ns for act, ns in successors(cur) if act == step_action)
                    expected_states.append(cur)
                self._pending_plan = list(path[1:])
                self._pending_plan_expected = expected_states[:-1]
                return path[0]

        # No gap-improving joint move is currently known/reachable -- try
        # SELF's own untried actions from the current cell first (a
        # not-yet-measured action might be the one that actually helps),
        # falling back to the partner's untried actions, so newly
        # discovered dynamics keep feeding the joint search on the next
        # decision.
        untried_self = self._viable_actions(self._active_cell, move_ids, self._tried_from)
        if untried_self:
            return untried_self[0]
        untried_partner = self._viable_actions(self._partner_cell, move_ids, self._partner_tried_from)
        if untried_partner:
            return untried_partner[0]

        # Truly stuck under current knowledge: nothing untried anywhere
        # relevant, and no reachable joint state improves the gap. Retry
        # the first move (cheap) in case a state elsewhere in the
        # already-explored joint frontier was missed by the budget.
        return move_ids[0]

    def _route_to_marker(self, move_ids: list[int]) -> int:
        """Single-agent fallback routing toward ``_marker_cell`` for the
        non-mirrored-variant case -- no joint state involved, so this is
        just "try the untried action whose measured delta best reduces
        Manhattan distance to the marker"."""
        assert self._active_cell is not None and self._marker_cell is not None
        untried = self._viable_actions(self._active_cell, move_ids, self._tried_from)
        if not untried:
            return move_ids[0]

        measured = [a for a in untried if a in self._dir_map]
        if not measured:
            return untried[0]

        def score(action: int) -> int:
            dr, dc = self._dir_map[action]
            dest = (self._active_cell[0] + dr, self._active_cell[1] + dc)  # type: ignore[index]
            return _manhattan(dest, self._marker_cell)  # type: ignore[arg-type]

        return min(measured, key=score)

    def _viable_actions(self, cell: Cell, move_ids: list[int], tried_from: dict[Cell, set[int]]) -> list[int]:
        tried = tried_from.get(cell, set())
        return [a for a in move_ids if a not in tried]

    def _probe(self, move_ids: list[int]) -> int:
        self._pending_ref_cell = self._active_cell
        self._pending_partner_ref_cell = self._partner_cell
        if self._active_cell is not None:
            untried = self._viable_actions(self._active_cell, move_ids, self._tried_from)
            if untried:
                return untried[0]
        return move_ids[0]
