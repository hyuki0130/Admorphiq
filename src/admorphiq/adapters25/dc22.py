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
frontier fallback BOTH report no progress does the adapter probe a
button (see "Re-click semantics" below for which one). Bounded at
``_PROBE_CLICK_CAP`` clicks per stuck episode so a board with no
reachable button (or a genuinely unsolvable local pocket) cannot spin
forever.

**Re-click semantics (added after the first live 2x500 smoke measured
0/6)**: the FIRST cut of this adapter treated every probed region as
permanently done once clicked -- a direct application of
``admorphiq.adapters25.vc33``'s lesson that a WRONG click can have a
persistent side effect, so re-probing was thought to always waste a
budgeted action for a result already known. Re-reading this adapter's
OWN "Mechanic model" measurements against the gold trace exposed a
contradiction: gold clicks the SAME board position TWICE (once early,
once later) -- the "never re-click" rule structurally forbids the gold
solution, because the measured seesaw (one block opens while a
DIFFERENT block closes, same click) means some buttons are genuine
STATE TOGGLERS whose effect must be applied, undone, and re-applied at
different points along the route, not fired once and forgotten.

Per-button click memory (``_button_memory``, keyed by the button's own
cell) now distinguishes two classes, decided from direct per-button
observation, never assumed:

- **INERT** -- the button's FIRST click showed literally zero diff
  (beyond HUD). Never re-clicked; the original vc33-derived "don't waste
  a budgeted action on an already-known result" reasoning still applies
  here, since a genuinely do-nothing region cannot start doing something
  later.
- **TOGGLER** -- the button showed ANY diff at least once. Stays
  eligible for re-click for as long as the level lasts. A second (or
  later) click of the SAME button teaches its **cosmetic signature**:
  cells that repeat on EVERY click of that specific button (the running
  intersection of all its own observed diffs) are noise -- e.g. the
  measured "indicator clusters" that flip colour on every click of one
  particular button regardless of whether that click did anything
  structural. Subtracting the cosmetic signature from a click's raw diff
  gives that click's real (non-cosmetic) effect footprint. A first click
  can't compute this yet (no second data point), so its whole diff
  counts provisionally.

``_find_toggler_reclick`` decides WHEN a re-click is worth spending a
probe budget on. The first cut gated this on a SPATIAL heuristic (a
toggler's accumulated effect footprint overlapping a cell CURRENTLY in
``_known_blocked``) -- a live 500-step probe measured ZERO reclicks
under that gate: this adapter's OWN "Offline verification" measurements
above already showed WHY it can't work -- click 1's effect is a 97-cell
REVEAL that lands far from any specific blocking cell, so a reveal-class
toggler's effect footprint has no reason to spatially coincide with
whatever cell the avatar is currently stuck against. Correlating
"where a button's effect lands" with "where the avatar happens to be
stuck" conflates two unrelated things.

Replaced with **stuck-state toggler cycling**: no spatial heuristic at
all. When genuinely stuck, try each known non-inert toggler ONCE per
distinct **stuck state** -- a key of (avatar cell, the click-parity of
every known toggler, used as a cheap proxy for "which of its ~2
observed states it is currently in" since the measured seesaw
alternates). ``_route`` itself is the effectiveness signal: the very
next ``choose_action`` call re-attempts the optimistic beeline
(``_first_step``) with whatever ``_known_blocked`` the click's raw diff
produced; if it now succeeds where it didn't before, the click helped
-- measured by the planner, not guessed by a spatial proxy
(``_route_feasible_after_toggle`` counts this for diagnostics). With a
small number of known togglers this is bounded per stuck-episode by
construction (at most one click per toggler per distinct state), on top
of the existing ``_PROBE_CLICK_CAP``.

New (never-before-clicked) candidate buttons are ranked by proximity to
the **hypothetical route** -- the shortest path from the avatar to the
goal PRETENDING every cell is passable (``_hypothetical_route_cells``)
-- rather than proximity to the avatar's current position. A live
500-step probe under the old avatar-proximity ranking spent 32 of the
run's ~128-action-per-life budget (see "Mechanic model" -- GAME_OVER
fired at steps 128/257/385, an evident per-life action fuse, not a
hazard) exhausting nearby-but-irrelevant regions before ever reaching
buttons that plausibly sit on the path to the goal; route-proximity
ranking spends that same budget on regions more likely to matter.

**Gold-replay divergence analysis (decisive finding)**: neither of the
above tunings could have worked, and a GOLD-REPLAY divergence check
against ``data/traces/dc22.npz``'s real level-0 solution (episode 1973,
20 actions, replayed by feeding this adapter gold's REAL recorded
frame-before/frame-after transitions and comparing what ``_decide``
would have picked at each step) proves why. FIRST DIVERGENCE is at
step 1: state = active_cell (38,10), goal_cell (20,24), dir_map with
only UP measured, ``known_blocked`` EMPTY. Predicted: continue the
optimistic walk (nothing looks blocked). Gold: click (48,36) -- roughly
40 cells away from the avatar. The decisive fact: ``known_blocked``
stays at EXACTLY ZERO cells for ALL 20 of gold's actions -- gold's path
never fails a single move, start to WIN. The two real buttons gold uses
(row36/col48, and row20/col44) sit far outside gold's entire walked
route (rows 20-40 / cols 10-24), confirming ACTION6 clicks are NOT
proximity-gated (a click targets a screen coordinate directly, no need
to walk the avatar there) -- so route-proximity ranking of NEW
candidates (previous paragraph) actively deprioritizes exactly the
buttons that matter, and the entire "click only when physically stuck"
trigger can categorically never fire on gold's own path, since nothing
on it is ever physically blocked. This is an ARCHITECTURAL gap, not a
tunable heuristic: the buttons gate something evaluated at the WIN
CHECK (a state/flag), not the avatar's walkable path.

**Parity-combo enumeration (replaces stuck-triggered probing for
reaching the goal)**: once >=2 known non-inert TOGGLERS exist (via the
existing ordinary walk/stuck/discovery machinery above, which still
runs to build this initial knowledge), the two with the LARGEST
measured single-click diff are locked in as ``_enum_togglers`` -- gold's
own two real buttons are exactly the two largest-footprint reveals/
seesaws measured offline (~97 and ~49 cells), so footprint size is a
reasonable, measured-consistent proxy for "the buttons that matter"
without needing to interpret what they do. Each toggler has ~2 states
(click-parity, matching the measured seesaw alternation), so the full
state space is 4 combos (``_ENUM_COMBOS``, Gray-code ordered so
consecutive combos need exactly one click each -- 3 clicks total to
cover all 4, not 2 per combo). For each untried combo in order: click
whichever toggler's current parity doesn't match the target, then WALK
to the goal cell using the existing optimistic planner (clicks are
free of any walking cost -- no need to approach a button physically).
If the avatar reaches the goal cell without WIN firing, that combo is
recorded as failed and the next one is tried. The goal region's own
appearance (colour/bbox/size, or vanishing) is also compared against
its FIRST-seen baseline right when a combo's parities are set, purely
as a diagnostic (``_enum_goal_appearance_changes``) -- per project
direction this is NOT built into a state-reading gate, since a single
level's evidence isn't enough to trust a colour-semantic interpretation
generically. If all 4 combos are tried and still fail, dc22 is banked
at 0/6: the divergence + enumeration result together are the evidence
that this level's real mechanic (a proactive win-flag requirement,
decoupled from physical navigation) sits outside what a reactive
walk-stuck-probe architecture can express, and the wall is precisely
located rather than guessed at.

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

# Parity-combo enumeration order (see module docstring's "Parity-combo
# enumeration"): (toggler_a_parity, toggler_b_parity) pairs, Gray-code
# ordered so each successive combo needs exactly ONE click to reach from
# the previous one (starting from the natural (0, 0) both-unclicked
# state) -- 3 total transition clicks to cover all 4 combos, not 2*4.
_ENUM_COMBOS: list[tuple[int, int]] = [(0, 0), (0, 1), (1, 1), (1, 0)]


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

        # Per-button click memory, keyed by the button region's own cell
        # (bbox top-left), persisting across restarts within a level (see
        # module docstring's vc33 cross-reference: a probed region's
        # measured effect is never re-derived from scratch). Each entry:
        # {"centroid": (row, col), "clicks": int, "diffs": [frozenset, ...]
        # (one raw HUD-excluded diff per click, in order), "cosmetic":
        # frozenset (cells that repeat on EVERY click of THIS button, once
        # >=2 clicks are observed), "inert": bool (True only when the
        # FIRST click showed literally zero diff -- a genuinely inert
        # region is never re-clicked; a region that showed ANY diff at
        # least once stays eligible for a re-click, see
        # ``_find_toggler_reclick``)}.
        self._button_memory: dict[Cell, dict[str, Any]] = {}
        self._probe_clicks_this_episode = 0

        # Stuck-state toggler cycling (see module docstring's "Re-click
        # semantics"): maps a stuck-state key (see ``_stuck_state_key``)
        # to the set of toggler cells already tried AT that state, so the
        # SAME toggler is never re-clicked twice for the SAME state (a
        # click that changes the state -- flips a toggler's parity, or
        # moves the avatar -- naturally produces a NEW key and permits
        # trying again).
        self._tried_togglers_at_state: dict[tuple[Any, ...], set[Cell]] = {}
        # Diagnostic-only: which tier the last probe click came from, so
        # ``_route`` can tell whether the NEXT re-plan attempt follows a
        # toggler re-click (see ``_route_feasible_after_toggle`` below).
        self._last_probe_kind: str | None = None  # "toggler_reclick" | "new_candidate" | None

        # Diagnostic-only counters.
        self._replans = 0
        self._probes_effective = 0
        self._probes_inert = 0
        self._probes_toggler_reclick = 0
        # Times a toggler re-click was immediately followed by the
        # optimistic beeline succeeding where it previously didn't --
        # the planner's OWN measured effectiveness signal for a re-click
        # (see module docstring: replaces the falsified spatial-overlap
        # gate).
        self._route_feasible_after_toggle = 0

        # Parity-combo enumeration (see module docstring): once >=2 known
        # non-inert togglers exist, the two with the LARGEST measured
        # single-click diff are locked in as ``_enum_togglers`` and every
        # ``_ENUM_COMBOS`` entry is tried in order -- replaces the
        # stuck-triggered probe entirely for reaching the goal, since
        # gold's own solution proved clicks here are proactive/state-
        # gating, not reactive to physical blockage (see "Re-click
        # semantics").
        self._enum_togglers: list[Cell] | None = None
        self._enum_combo_idx = 0
        self._enum_tried: set[tuple[int, int]] = set()
        # The goal region's (colour, bbox, size) as first observed --
        # the baseline "closed" appearance a combo's effect is compared
        # against (diagnostic; does not gate the walk-to-confirm step).
        self._goal_baseline: tuple[Any, ...] | None = None
        self._enum_checked_appearance: set[tuple[int, int]] = set()
        # Diagnostic-only: how many combos showed the goal region's own
        # appearance change (colour/bbox/size, or vanish) once that
        # combo's parities were set, BEFORE any walk was attempted.
        self._enum_goal_appearance_changes = 0

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
        self._button_memory = {}
        self._probe_clicks_this_episode = 0
        self._tried_togglers_at_state = {}
        self._last_probe_kind = None
        self._enum_togglers = None
        self._enum_combo_idx = 0
        self._enum_tried = set()
        self._goal_baseline = None
        self._enum_checked_appearance = set()

    def _on_restart(self) -> None:
        """Only the avatar's own position resets; the layout knowledge
        (dir_map, known_blocked, button_memory, tried_togglers_at_state)
        is kept -- the walls and button effects didn't change, only the
        current attempt did."""
        self._pending_action = None
        self._pending_kind = None
        self._pending_ref_cell = None
        self._pending_probe_cell = None
        self._prev_grid = None
        self._active_cell = None
        self._probe_clicks_this_episode = 0
        self._last_probe_kind = None

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
        """Whether a button click changed ANYTHING. The RAW diff always
        drives ``_known_blocked`` (never interpreted semantically -- see
        module docstring): every changed cell is removed so the
        optimistic planner is willing to try walking through it again,
        whether it turns out open or (re-discovered the normal way)
        still blocked. This part never needs cosmetic/structural
        classification -- a freed cell that is still genuinely blocked
        self-corrects the next time routing tries to walk through it.

        HUD cells (e.g. the step counter, which increments every action
        regardless of the click) are excluded from ``changed`` using the
        SAME measured ``_is_hud_band`` region test every other candidate
        list in this file uses -- not a hardcoded row/column guess.

        Separately, this button's OWN click memory is updated (see
        ``_button_memory``'s docstring in ``__init__``) -- this is what
        decides whether the button is ever worth re-clicking, and is kept
        deliberately independent of the ``_known_blocked`` update above
        (see module docstring's "Re-click semantics" section)."""
        if probe_cell is None:
            return
        mem = self._button_memory.get(probe_cell)
        if mem is None:
            return
        height, width = len(before), (len(before[0]) if before else 0)
        bg_before = most_common_color(before)
        hud_cells: set[Cell] = set()
        for r in find_regions(before, background=bg_before):
            if _is_hud_band(r, height, width):
                hud_cells |= r["cells"]  # type: ignore[arg-type]
        diff = frame_diff(before, after)
        changed = frozenset(c for c in diff["cells"] if c not in hud_cells)  # type: ignore[union-attr]
        if changed:
            self._known_blocked -= changed

        mem["diffs"].append(changed)
        mem["clicks"] += 1
        if mem["clicks"] == 1:
            # A first click can't yet distinguish cosmetic noise from a
            # real effect (see module docstring) -- a completely empty
            # first diff is the only signal available at this point: the
            # region is genuinely inert (no visible reaction at all) and
            # is never clicked again. Anything else counts as effective
            # for now; the SECOND click (if any) teaches the cosmetic
            # signature and refines this.
            mem["inert"] = not changed
            effective = bool(changed)
        else:
            # >=2 clicks of this SAME button: cells that repeat on EVERY
            # click are its measured cosmetic signature (per-button, from
            # direct observation -- not assumed). Subtract them from THIS
            # click's diff to get the click's real (non-cosmetic) effect.
            cosmetic = mem["diffs"][0]
            for d in mem["diffs"][1:]:
                cosmetic = cosmetic & d
            mem["cosmetic"] = cosmetic
            effective = bool(changed - cosmetic)
        if effective:
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
            self._goal_baseline = self._goal_appearance(regions)

        if self._enum_togglers is None:
            self._maybe_start_enumeration()

        if self._enum_togglers is not None and self._enum_combo_idx < len(_ENUM_COMBOS):
            if self._active_cell == self._goal_cell:
                # Reached the goal cell under this combo's parities but
                # WIN didn't fire (is_done() would have stopped the loop
                # otherwise) -- this combo doesn't gate the door. Try the
                # next one; the existing defensive _probe below nudges
                # the avatar one step off the goal cell so the NEXT
                # combo's walk-to-confirm isn't a degenerate start==goal.
                self._enum_tried.add(_ENUM_COMBOS[self._enum_combo_idx])
                self._enum_combo_idx += 1
            else:
                action = self._enumeration_decide(regions, move_ids)
                if action is not None:
                    return action

        if self._active_cell == self._goal_cell:
            return self._probe(move_ids)

        return self._route(regions, move_ids, action6_ok)

    def _goal_appearance(self, regions: list[Region]) -> tuple[Any, ...] | None:
        """The goal region's (colour, bbox, size) in the CURRENT frame, or
        None if it isn't present at all (vanished) -- compared against
        ``_goal_baseline`` to see whether a combo's clicks visibly
        changed the goal marker itself (module docstring's "Reframe the
        success signal")."""
        for r in regions:
            if r["color"] == self._goal_color:
                return (r["color"], r["bbox"], r["size"])
        return None

    def _maybe_start_enumeration(self) -> None:
        """Lock in the two known non-inert TOGGLERS with the LARGEST
        measured single-click diff as ``_enum_togglers`` -- see module
        docstring's "Parity-combo enumeration". Requires at least 2 to be
        known; does nothing (falls back to ordinary walk/stuck/probe
        discovery) until then."""
        togglers = [
            (cell, max((len(d) for d in mem["diffs"]), default=0))
            for cell, mem in self._button_memory.items()
            if not mem["inert"] and mem["clicks"] > 0
        ]
        if len(togglers) < 2:
            return
        togglers.sort(key=lambda t: (-t[1], t[0]))
        self._enum_togglers = [togglers[0][0], togglers[1][0]]

    def _enumeration_decide(self, regions: list[Region], move_ids: list[int]) -> GameAction | None:
        """Drive the current combo: click whichever known toggler's
        parity doesn't yet match the target, then walk toward the goal
        once both match. Returns None only when every combo has been
        tried (falls through to ordinary routing, which by this point is
        just a dead end -- see module docstring)."""
        assert self._enum_togglers is not None and self._active_cell is not None and self._goal_cell is not None
        while self._enum_combo_idx < len(_ENUM_COMBOS):
            target = _ENUM_COMBOS[self._enum_combo_idx]
            if target in self._enum_tried:
                self._enum_combo_idx += 1
                continue
            cell_a, cell_b = self._enum_togglers
            parity_a = self._button_memory[cell_a]["clicks"] % 2
            parity_b = self._button_memory[cell_b]["clicks"] % 2
            if parity_a != target[0]:
                return self._click_button(cell_a, kind="enum_set")
            if parity_b != target[1]:
                return self._click_button(cell_b, kind="enum_set")

            if target not in self._enum_checked_appearance:
                self._enum_checked_appearance.add(target)
                if self._goal_appearance(regions) != self._goal_baseline:
                    self._enum_goal_appearance_changes += 1

            if not self._dir_map:
                return self._probe(move_ids)
            moves = list(self._dir_map.values())
            move_labels = {unit: action for action, unit in self._dir_map.items()}
            optimistic = self._optimistic_grid()
            step = self._first_step(optimistic, self._active_cell, self._goal_cell, moves, move_labels)
            if step is not None:
                self._pending_action = step
                self._pending_kind = "move"
                self._pending_ref_cell = self._active_cell
                return simple_action(step)

            # Can't even reach the goal cell under this combo's
            # passability state -- treat as a failed combo, same as
            # reaching the goal without triggering WIN.
            self._enum_tried.add(target)
            self._enum_combo_idx += 1
        return None

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
        if self._last_probe_kind == "toggler_reclick":
            # The planner's OWN re-plan is the effectiveness signal for
            # the last re-click (module docstring: replaces the
            # falsified spatial-overlap gate) -- diagnostic only, does
            # not change what action gets taken.
            if step is not None:
                self._route_feasible_after_toggle += 1
            self._last_probe_kind = None
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

        # Tier 1: stuck-state toggler cycling (module docstring's
        # "Re-click semantics" -- replaces the falsified spatial-overlap
        # gate). Re-clicking a known toggler is itself a planning move --
        # the seesaw case (one block opens while another closes) needs
        # exactly this: walk segment 1, toggle, walk segment 2, and
        # toggle again (a new stuck state, since the toggler's own parity
        # flipped) if the first segment is needed once more.
        reclick_cell = self._find_toggler_reclick()
        if reclick_cell is not None:
            self._probes_toggler_reclick += 1
            return self._click_button(reclick_cell, kind="toggler_reclick")

        # Tier 2: a brand-new, never-clicked candidate region, ranked by
        # proximity to the HYPOTHETICAL route toward the goal (module
        # docstring: a reveal-class button's effect can be far from the
        # avatar's current position but still sit near the route it
        # needs), falling back to avatar-proximity when no route/dir_map
        # exists yet to rank against.
        candidates = [
            r
            for r in regions
            if r["color"] not in (self._avatar_color, self._goal_color)
            and r["bbox"][:2] not in self._button_memory
        ]
        if not candidates:
            return None
        candidates = self._rank_candidates_by_route(candidates)
        target = candidates[0]
        cell: Cell = target["bbox"][:2]  # type: ignore[assignment]
        self._button_memory[cell] = {
            "centroid": target["centroid"],
            "clicks": 0,
            "diffs": [],
            "cosmetic": frozenset(),
            "inert": False,
        }
        return self._click_button(cell, kind="new_candidate")

    def _stuck_state_key(self) -> tuple[Any, ...]:
        """(avatar cell, sorted (toggler cell, click-parity) pairs) --
        click parity is a cheap, measured-consistent proxy for "which of
        its ~2 observed states a toggler is currently in" (the seesaw
        alternates on each click). Two calls at the SAME avatar position
        with every known toggler in the SAME parity are the SAME stuck
        state; a click that flips any toggler's parity (or moves the
        avatar) produces a genuinely new key."""
        toggler_states = tuple(
            sorted(
                (cell, mem["clicks"] % 2)
                for cell, mem in self._button_memory.items()
                if not mem["inert"] and mem["clicks"] > 0
            )
        )
        return (self._active_cell, toggler_states)

    def _find_toggler_reclick(self) -> Cell | None:
        """The first known non-inert toggler not yet tried AT the current
        stuck state (see ``_stuck_state_key``) -- no spatial heuristic;
        ``_route``'s own next re-plan attempt (``_route_feasible_after_toggle``)
        is what measures whether a given re-click actually helped."""
        key = self._stuck_state_key()
        tried = self._tried_togglers_at_state.setdefault(key, set())
        for cell, mem in self._button_memory.items():
            if mem["inert"] or mem["clicks"] == 0 or cell in tried:
                continue
            tried.add(cell)
            return cell
        return None

    def _hypothetical_route_cells(self) -> set[Cell]:
        """The shortest avatar->goal path PRETENDING every cell is
        passable -- a fixed reference line for "where the route would go
        absent any barriers", used to rank which new button candidate is
        worth probing first (module docstring's "Re-click semantics")."""
        if self._active_cell is None or self._goal_cell is None or not self._dir_map:
            return set()
        moves = list(self._dir_map.values())
        height = width = 64
        all_passable = [[True] * width for _ in range(height)]
        path = grid_shortest_path(all_passable, self._active_cell, self._goal_cell, moves=moves)
        return set(path) if path else set()

    def _rank_candidates_by_route(self, candidates: list[Region]) -> list[Region]:
        assert self._active_cell is not None
        route_cells = self._hypothetical_route_cells()
        if route_cells:
            def route_distance(r: Region) -> int:
                rr, rc = r["centroid"]  # type: ignore[misc]
                return min(abs(rr - cr) + abs(rc - cc) for cr, cc in route_cells)

            return sorted(candidates, key=route_distance)
        return sorted(
            candidates,
            key=lambda r: abs(r["centroid"][0] - self._active_cell[0])  # type: ignore[index]
            + abs(r["centroid"][1] - self._active_cell[1]),  # type: ignore[index]
        )

    def _click_button(self, cell: Cell, kind: str) -> GameAction:
        mem = self._button_memory[cell]
        self._probe_clicks_this_episode += 1
        self._pending_action = None
        self._pending_kind = "probe"
        self._pending_probe_cell = cell
        self._last_probe_kind = kind
        row, col = (round(mem["centroid"][0]), round(mem["centroid"][1]))
        return click_action(x=col, y=row)
