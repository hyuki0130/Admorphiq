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
from admorphiq.kernels import (
    canonical_key,
    find_regions,
    points_with_centroid,
    transition_shortest_path,
)

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

# A non-background region at least this big is treated as a WALL/HAZARD
# (r11l's `bvzgd-*` level walls, plus the edge counter column): the planner
# must not place a leg on one (the game refuses such placements). A structural
# threshold, not a game-specific pixel count — pieces (legs) and the small
# body/target rings are all well under it.
_HAZARD_MIN_SIZE = 28
# Interactive PIECE size band (a leg / body / target marker) — excludes both
# single-pixel decoration (leg-to-body connector dots) and wall-sized slabs.
_MIN_PIECE_SIZE = 6
_MAX_PIECE_SIZE = 27
# A clickable FOOT (leg) is a compact blob; a leg-to-body LIMB line is thin
# (low bbox fill). Feet fill ~0.5 of their bbox, limbs ~0.15.
_MIN_LEG_FILL = 0.35
# A BODY marker is very compact (fills ~0.8 of its bbox); its TARGET nest is a
# low-fill ring (~0.24). This threshold separates a body from both its own
# target and from the feet (~0.5), so a creature colour = one body + one nest.
_BODY_FILL = 0.6
# Squared-distance tolerance for "a ring sits at the legs' centroid" (== the
# body). ~4 px, comfortably inside a body marker's own extent.
_BODY_CENTROID_TOL2 = 16.0
# A placed leg needs this many cells of clear background around its centre —
# roughly the leg sprite's half-extent — so legs land separated from the nest
# and each other (overlapping placements collide and burn the game's strikes).
_LEG_CLEAR_RADIUS = 2
# A drag animation settles in a handful of frames; a placement still unsettled
# after this many is stuck (the board changed under the plan) — abandon it.
_PLACE_STUCK_LIMIT = 12
# A new level's legs animate in; build the plan only once the detected creature
# signature has held for this many consecutive frames (past the animation).
_SETTLE_FRAMES = 3


def _hazard_cells(grid: Grid, bg: int) -> set[Cell]:
    """Cells belonging to a wall/hazard region — any non-background region at
    or above :data:`_HAZARD_MIN_SIZE`. The planner treats these as unplaceable
    (the game refuses a leg drop that collides with one)."""
    cells: set[Cell] = set()
    for region in find_regions(grid, background=bg):
        if region["size"] >= _HAZARD_MIN_SIZE:
            cells |= region["cells"]
    return cells


def _fill(region: Region) -> float:
    """Fraction of a region's bounding box its cells occupy — a compact foot/
    body fills ~0.5-0.8, a thin limb line ~0.15."""
    r0, c0, r1, c1 = region["bbox"]
    area = (r1 - r0 + 1) * (c1 - c0 + 1)
    return region["size"] / area if area else 0.0


def _analyze_creatures(grid: Grid, bg: int, hazard: set[Cell]) -> list[tuple[list[Cell], Cell]] | None:
    """Detect ALL centroid-assembly creatures on the board — one ``(leg_centres,
    target_centre)`` per creature — purely from frame structure.

    Model (validated live, see the module docstring): each creature is a BODY
    that sits at the integer CENTROID of its own clickable LEGS, plus a
    same-colour TARGET nest the body must reach. A body is a COMPACT high-fill
    marker; its target is a low-fill ring of the same colour. Legs are the
    other compact pieces; each is assigned to the NEAREST body (the assignment
    is self-labelling because a body sits on its legs' mean), and the grouping
    is verified — a group whose centroid is not near its body is rejected.

    Returns the per-creature list (>= 1) or ``None`` when no clean creature is
    found (the caller then falls back to the generic explorer). No colour or
    coordinate constants — only sizes, bbox-fill, the same-colour body/target
    signature, and centroid-nearness.
    """
    # gap=2 so a ring-shaped nest drawn as scattered pixels fuses into one
    # piece-sized region (its outline points sit within a 3-cell bridge).
    pieces = [
        r
        for r in find_regions(grid, background=bg, gap=2)
        if _MIN_PIECE_SIZE <= r["size"] <= _MAX_PIECE_SIZE
        and not (r["cells"] & hazard)
    ]
    if len(pieces) < 3:
        return None

    by_color: dict[int, list[Region]] = {}
    for r in pieces:
        by_color.setdefault(r["color"], []).append(r)

    # A creature colour has a COMPACT body (high fill) plus at least one other
    # same-colour region (its low-fill target ring). Two thin limb lines share
    # a colour too, but neither is high-fill, so that colour is rejected.
    bodies: list[tuple[Region, Region]] = []  # (body, target)
    body_colors: set[int] = set()
    for color, regs in by_color.items():
        if len(regs) < 2:
            continue
        body = max(regs, key=_fill)
        if _fill(body) < _BODY_FILL:
            continue
        target = min((r for r in regs if r is not body), key=_fill)
        bodies.append((body, target))
        body_colors.add(color)
    if not bodies:
        return None

    # Legs = compact pieces that are NOT a body/target ring colour.
    legs = [r for r in pieces if r["color"] not in body_colors and _fill(r) >= _MIN_LEG_FILL]
    if not legs:
        return None

    def _d2(a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2

    # Assign each leg to the nearest body (self-labelling: a body sits on its
    # own legs' mean).
    groups: dict[int, list[Region]] = {i: [] for i in range(len(bodies))}
    for leg in legs:
        i = min(range(len(bodies)), key=lambda i: _d2(leg["centroid"], bodies[i][0]["centroid"]))
        groups[i].append(leg)

    creatures: list[tuple[list[Cell], Cell]] = []
    for i, (body, target) in enumerate(bodies):
        grp = groups[i]
        if not grp:
            return None  # a body with no legs -> layout not understood; defer
        centroid = (
            sum(r["centroid"][0] for r in grp) / len(grp),
            sum(r["centroid"][1] for r in grp) / len(grp),
        )
        if _d2(centroid, body["centroid"]) > _BODY_CENTROID_TOL2:
            return None  # grouping inconsistent with the body-at-centroid invariant
        leg_centres = [(int(round(r["centroid"][0])), int(round(r["centroid"][1]))) for r in grp]
        target_centre = (int(round(target["centroid"][0])), int(round(target["centroid"][1])))
        creatures.append((leg_centres, target_centre))
    return creatures


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

        # Centroid-assembly PLANNER state (tried once per level before the
        # explorer). ``_plan`` is a queue of (kind, cell) clicks — a "select"
        # (click a leg to select it) then a "place" (click the destination,
        # which animates); the place step is re-issued until the masked board
        # settles. ``_plan_attempted`` gates it to one shot per level.
        self._plan: list[tuple[str, Cell]] | None = None
        self._plan_attempted = False
        self._plan_place_issued = False
        self._plan_last_masked: Grid | None = None
        self._plan_place_count = 0
        # Creature signature (per-creature leg counts) held while waiting for a
        # new level's entry animation to settle, plus how many consecutive
        # frames it has held.
        self._settle_ref: tuple[int, ...] | None = None
        self._settle_count = 0

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
        masked = _mask_hud(grid, hud)
        cur_key = canonical_key(masked, mode="exact")
        self._observe_result(cur_key)

        # Centroid-assembly planner first (one shot per level); when it has no
        # plan or is exhausted it returns None and the generic explorer runs.
        planned = self._planner_step(grid, bg, masked)
        if planned is not None:
            self._pending_click = None  # planner clicks are not explorer edges
            self._pending_key = None
            return click_action(x=planned[1], y=planned[0])

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
        self._plan = None
        self._plan_attempted = False
        self._plan_place_issued = False
        self._plan_last_masked = None
        self._plan_place_count = 0
        self._settle_ref = None
        self._settle_count = 0

    def _on_restart(self) -> None:
        self._pending_click = None
        self._pending_key = None
        # A restart means a placement went wrong (a strike); abandon the
        # one-shot plan and let the explorer take over rather than repeat it.
        self._plan = None
        self._plan_attempted = True

    # ── centroid-assembly planner ───────────────────────────────────────

    def _build_plan(self, grid: Grid, bg: int) -> list[tuple[str, Cell]] | None:
        """Detect every creature and compute a select→place click plan that
        lands each body (its legs' centroid) on its target nest, avoiding
        hazards. Returns ``None`` when no clean creature is found (the explorer
        then runs)."""
        hazard = _hazard_cells(grid, bg)
        creatures = _analyze_creatures(grid, bg, hazard)
        if not creatures:
            return None
        height, width = len(grid), len(grid[0])

        def is_free(cell: Cell) -> bool:
            # Require a clear BACKGROUND neighbourhood, not merely non-hazard:
            # a leg sprite has extent, and a cell on a nest / another marker
            # overlaps it. Demanding empty bg pushes the legs to well-separated
            # open cells (clear of the nests and of each other), avoiding the
            # transit collisions that trigger the game's strikes.
            r, c = cell
            for dr in range(-_LEG_CLEAR_RADIUS, _LEG_CLEAR_RADIUS + 1):
                for dc in range(-_LEG_CLEAR_RADIUS, _LEG_CLEAR_RADIUS + 1):
                    rr, cc = r + dr, c + dc
                    if not (0 <= rr < height and 0 <= cc < width):
                        return False
                    if grid[rr][cc] != bg or (rr, cc) in hazard:
                        return False
            return True

        plan: list[tuple[str, Cell]] = []
        for leg_centres, target in creatures:
            dests = points_with_centroid(target, len(leg_centres), is_free, current=leg_centres)
            if dests is None:
                return None
            for leg, dest in zip(leg_centres, dests):
                if tuple(leg) == tuple(dest):
                    continue  # leg already positioned; no click needed
                plan.append(("select", leg))
                plan.append(("place", dest))
        return plan or None

    def _planner_step(self, grid: Grid, bg: int, masked: Grid) -> Cell | None:
        """Emit the next planner click, or ``None`` to defer to the explorer.

        The plan is built once per level, but only once the level's own
        entry/win animation has SETTLED (two identical masked frames) — a plan
        built on the transition frame would see the previous level's leftover
        pieces and mis-place. While waiting, a hazard cell is clicked (a
        refused no-op) so the animation can advance without disturbing the
        board. A ``select`` click is instant (issued once, advance next call);
        a ``place`` click animates, so it is re-issued until the masked board
        settles, then the plan advances."""
        if self._plan is None and not self._plan_attempted:
            # A new level's legs animate into place over many frames (the
            # detected leg count oscillates), so gate plan-building on the
            # CREATURE SIGNATURE (per-creature leg counts) being non-empty and
            # unchanged for a few consecutive frames — a raw frame-equality
            # settle stabilises on transient mid-animation frames. While
            # waiting, click a hazard cell (a refused no-op).
            sig = self._creature_signature(grid, bg)
            if sig is not None and sig == self._settle_ref:
                self._settle_count += 1
            else:
                self._settle_ref = sig
                self._settle_count = 0
            if sig is None or self._settle_count < _SETTLE_FRAMES:
                return self._safe_wait_cell(grid, bg)
            self._plan_attempted = True
            self._plan = self._build_plan(grid, bg)
            self._plan_place_issued = False
            self._plan_last_masked = None
            self._plan_place_count = 0
        if not self._plan:
            return None

        kind, cell = self._plan[0]
        if kind == "select":
            # Validate against the CURRENT board: if the leg we planned to
            # select is no longer there, the plan was built on a since-changed
            # frame (e.g. a level-entry animation that held the previous
            # level's pieces), so discard it and rebuild once settled.
            if not self._leg_present(grid, bg, cell):
                self._plan = None
                self._plan_attempted = False
                self._settle_ref = None
                return self._safe_wait_cell(grid, bg)
            self._plan.pop(0)
            self._plan_place_issued = False
            self._plan_last_masked = None
            return cell
        # place: settled when the masked board matches the previous call's.
        if self._plan_place_issued and masked == self._plan_last_masked:
            self._plan.pop(0)
            self._plan_place_issued = False
            self._plan_last_masked = None
            self._plan_place_count = 0
            return self._planner_step(grid, bg, masked)
        # A placement that never settles means the board changed under the plan
        # (a level transition, or the leg was not where the plan assumed) —
        # abandon and rebuild once settled rather than re-clicking forever.
        self._plan_place_count += 1
        if self._plan_place_count > _PLACE_STUCK_LIMIT:
            self._plan = None
            self._plan_attempted = False
            self._settle_ref = None
            self._plan_place_count = 0
            return self._safe_wait_cell(grid, bg)
        self._plan_place_issued = True
        self._plan_last_masked = masked
        return cell

    def _safe_wait_cell(self, grid: Grid, bg: int) -> Cell | None:
        """A hazard cell whose click the game refuses (a no-op) — used to burn
        a frame while a level animation settles, without disturbing the board.
        ``None`` (defer to the explorer) if the board has no hazard region."""
        hazard = _hazard_cells(grid, bg)
        return min(hazard) if hazard else None

    def _creature_signature(self, grid: Grid, bg: int) -> tuple[int, ...] | None:
        """A hashable summary of the detected creatures (sorted per-creature leg
        counts), or ``None`` when no creature is found. Used to detect when a
        new level's leg-spawn animation has settled (the signature stops
        changing) before committing to a plan."""
        creatures = _analyze_creatures(grid, bg, _hazard_cells(grid, bg))
        if not creatures:
            return None
        return tuple(sorted(len(legs) for legs, _t in creatures))

    def _leg_present(self, grid: Grid, bg: int, cell: Cell) -> bool:
        """Whether a detected leg currently sits near ``cell`` — the freshness
        check that catches a plan built on a since-changed (transition) frame."""
        hazard = _hazard_cells(grid, bg)
        creatures = _analyze_creatures(grid, bg, hazard)
        if not creatures:
            return False
        for leg_centres, _target in creatures:
            for lc in leg_centres:
                if (lc[0] - cell[0]) ** 2 + (lc[1] - cell[1]) ** 2 <= _BODY_CENTROID_TOL2:
                    return True
        return False

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
