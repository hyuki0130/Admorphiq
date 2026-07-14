"""script25 quarantined adapter: KA59 (multi-piece delivery/configuration-path family).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/KA59.md`` (read for reference, not imported) records
KA59 as a "multi-player cooperative Sokoban" where ACTION1-4 move and
"certain blocks push when adjacent" — the brittle `strat_ka59_sokoban`
legacy solver used hardcoded L1-L4 push sequences, which this adapter does
NOT read or reuse (see ``docs/r56_codex_toolbase_verdict_20260715.md``'s
script25 remit: compose ``admorphiq.kernels`` only).

Mechanic hypothesis, VERIFIED OFFLINE against ``data/traces/ka59.npz``
(gold traces for levels 0-3, game_id ``ka59-38d34dbb`` — the same live
hash this adapter targets) BEFORE any live action was spent, plus a
read-only (dev-time-diagnosis-only, never imported) look at
``environment_files/ka59/38d34dbb/ka59.py`` to understand what to measure:

- The board has several small ring-shaped sprites (a hollow square outline
  with a single solid-colour interior mark) — these are the movable
  PIECES. Exactly one is "active" at a time; ACTION1-4 shifts the active
  piece by a fixed pixel delta in one of four directions, or does nothing
  if blocked. ACTION6 clicks a DIFFERENT piece to make it the active one.
  Measured directly from the gold trace: level 0's frame-by-frame
  ``frame_diff`` shows every ACTION1-4 row produces an 18-19-cell diff
  bounded near one small ring (a real move), while ACTION6 rows produce a
  much smaller (as low as 2-cell) diff localized to the two rings'
  interior marker pixels — consistent with a highlight swap, not a
  position change. Level 0's gold action histogram uses ACTION6 twice
  (rows 3 and 6 of 12), confirming multi-piece control is exercised even
  on the simplest gold-covered level, not an edge case.
- The board also has larger ring-shaped sprites acting as FRAME targets. A
  level is solved when every frame's hollow interior is occupied by some
  piece's own footprint, exactly centered (measured via
  ``admorphiq.kernels.closed_frames``: a piece's ``outer_bbox`` top-left
  equals its target frame's ``inner_bbox`` top-left when correctly
  placed — a piece and its frame differ by exactly 1 cell of border on
  every side). Any piece may satisfy any frame (the win check the source
  implements is an unordered "does some piece fit this frame" search, not
  a fixed pairing), so this adapter treats piece-to-frame matching as a
  nearest-distance ASSIGNMENT problem, not a hardcoded per-level pairing.
- Offline region measurement on the level 0-3 gold start frames (via
  ``closed_frames`` + ``size_clusters`` on each ring's own outer-bbox
  area) found a clean two-class split (avatar-class outer area 9, frame-
  class outer area 25) on levels 0, 1, and 3 — every frame on those
  levels is reachable by moving/switching among the ring-class pieces
  alone. Level 2, however, ALSO exposes frame classes of outer area 40
  and 64 with NO matching ring-shaped piece anywhere on the board — those
  targets need a distinct, solid (non-ring) PUSHABLE-BOX piece class this
  adapter does not detect or move. This is a measured, honest scope
  limit, not a guess: this adapter only ever plans toward frames whose
  ``inner_bbox`` area matches some detected ring-piece's own
  ``outer_bbox`` area, so on level 2 it will correctly place whatever
  ring-class pieces exist and simply never attempt the box-class frames,
  rather than mis-planning around them.

Kernel composition (``admorphiq.kernels`` only, no game semantics inside
any kernel call):

- :func:`admorphiq.kernels.closed_frames` finds every hollow-ring shape in
  one pass (both pieces and frame targets); :func:`admorphiq.kernels.size_clusters`
  splits them into size classes by outer-bbox area — the adapter never
  hardcodes a specific pixel count for "how big is a piece".
- :func:`admorphiq.kernels.assign_pairs` computes the nearest-distance
  bipartite assignment from currently-unplaced pieces to currently-unfilled
  frames (Manhattan-distance-scored), so which piece goes to which frame
  is a measured optimization, not a fixed per-level order.
- :func:`admorphiq.kernels.track_objects` identifies, after every ACTION1-4
  attempt, WHICH ring-class region actually shifted and by how much (its
  ``matches`` entries carry a per-region ``shift``, not just an aggregate)
  — this is how the adapter learns both the currently-active piece's
  identity (never assumed) and the measured per-action pixel delta
  (``dir_map``), exactly mirroring
  ``admorphiq.adapters25.m0r0``'s frame-diff-based direction-learning, but
  generalized to a multi-piece board where "which region is the mover" is
  itself unknown ahead of time.
- :func:`admorphiq.kernels.configuration_path` plans a piece's route to its
  assigned target over the INCREMENTALLY measured ``(cell, action, cell)``
  transition graph built from real observed moves — this is the
  "heavyweight" generic state-space search kernel (unlike
  ``admorphiq.kernels.grid_shortest_path``, which needs a pre-known
  passability array; here the walls are discovered live, one probed move
  at a time, the same way ``m0r0`` discovers its maze, but expressed as an
  arbitrary caller-defined state space rather than a fixed grid).
- :func:`admorphiq.kernels.reachable_frontier` finds the nearest
  already-reached cell with an untried direction when the assigned target
  is not yet known-reachable, so exploration and goal-directed routing
  share the SAME measured transition graph instead of two separate data
  structures.

Adapter-owned policy (not a kernel concern): a cell blocked by ANOTHER
currently-unplaced piece sitting in the destination is deliberately NOT
recorded as a permanent wall (that cell may become free later, once that
other piece moves) — only a block confirmed with no other piece at the
destination is treated as a genuine, permanent wall. Pushing (walking a
piece into another piece to displace it) is NOT modeled or attempted; if
one is accidentally triggered by routing into an occupied cell the
adapter did not yet know was occupied, the resulting multi-action
animation is invisible to a single before/after diff and is simply
observed as "nothing moved" for a few actions, which is wasteful but not
unsafe (no persistent bad state is recorded from it). ``restart_on_game_over``
mirrors every other script25 adapter's convention; unlike ``m0r0`` this
game's losses (StepCounter exhaustion / enemy contact, per the read-only
source review) are not tied to a specific dangerous CELL, so no hazard
memory is kept — only the piece's own position re-anchors to "unknown"
across a restart, while the measured transition graph and dir_map (both
properties of the fixed level layout / control scheme, not of one life)
are preserved.

A target ring is also STICKY once seen (``_known_targets``): a piece
merely passing adjacent to (not yet exactly aligned with) a frame can
overlap one shared border pixel and break ``closed_frames``' exact-ring
match for that frame on that one frame only, making a real, still-unfilled
static target vanish from ``_classify_rings``' output for a call or two.
Frames never move, so a once-seen target cell is trusted as still needing
a piece until a piece is actually observed sitting exactly on it — without
this, the adapter would periodically "forget" an unsolved target and
misallocate its only free piece to the wrong (or no) goal. This was
MEASURED live (level 0's second target vanished from detection the moment
the routed piece's outer bbox came pixel-adjacent to it, one step before
reaching its exact final cell) and is a genuine, if narrow, fragility of
composing ring detection on a moving board — not a hypothetical.

Live smoke result (2x500 actions, deterministic): **0/7 levels**, but the
select-click reliability lever this was measured and fixed for now
converges immediately (see below), so the remaining wall is a DIFFERENT
one: reaching a distant target through unexplored territory (see
"Remaining bottleneck" below) can outrun even a 100-action fuse when no
push/portal is modeled.

**Select-click reliability, MEASURED and fixed (round 2)**: the first
version forced a movement probe after every select to infer success
indirectly, was frequently blocked by an unrelated wall in whatever
direction it happened to try, and clicked the piece's CENTROID first --
none of which is what the game actually needs. Two things were measured
directly from every one of the 14 ACTION6 rows in
``data/traces/ka59.npz`` (3 different levels):

1. **The verification signal**: a successful select ALWAYS swaps exactly
   two single pixels -- the piece BECOMING active (its own single hole
   cell) changes to one specific colour, and whichever piece WAS active
   changes to a different (non-fixed, sprite-dependent) colour. The
   ACTIVE colour itself is the same across every observed successful
   select, on every level -- but this adapter does not hardcode that
   value: :meth:`Adapter._observe_result` measures it once, the first time
   a movement genuinely confirms which piece is active (`_active_marker_color`),
   then :meth:`Adapter._select_confirmation` uses it as a DIRECT,
   single-pixel-read verification the very next call -- no movement probe
   needed at all when it succeeds, and a CONCLUSIVE miss (colour known,
   doesn't match) retries immediately with a different click point rather
   than wasting an action confirming failure via movement.
2. **The click point**: every one of the 14 gold ACTION6 clicks lands
   EXACTLY on the selected piece's own outer-bbox TOP-LEFT corner, never
   the centroid, to the pixel, across all 3 levels. :meth:`Adapter._select_point`
   now tries the top-left corner FIRST (centroid demoted to second
   fallback, corner-cycling kept beyond that as a safety net).

Live-measured result of both fixes together (500-action run,
``scripts/rounds`` methodology): **5/5 select clicks issued this run
confirmed the switch on the FIRST attempt** (mean 1.0 attempts/switch,
down from the earlier version's repeated multi-click cycling that could
run 10+ attempts at the same point without ever confirming).

**Remaining bottleneck (measured, not select-related)**: with switching
now near-instant, the piece that needs to reach the far frame (level 0's
target1, on the OTHER side of a wall from where both pieces spawn) still
doesn't arrive within budget across several lives -- this is unexplored-
territory frontier search taking longer than the 100-action fuse allows
when the correct detour around/through the wall isn't the Manhattan-
shortest guess (:meth:`Adapter._pick_action`'s goal-distance heuristic
only orders KNOWN directions; genuine wall-gap discovery still depends on
:func:`admorphiq.kernels.reachable_frontier`'s untried-direction BFS,
which has no shortcut for a wide, unexplored wall). This is a navigation-
budget question, not a select-reliability one -- flagged as the next
lever, not attempted here.
"""

from __future__ import annotations

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
    assign_pairs,
    closed_frames,
    configuration_path,
    reachable_frontier,
    size_clusters,
    track_objects,
)

GAME_ID = "ka59"

Cell = tuple[int, int]
Region = dict[str, Any]

# Per-level safety cap, mirroring every other script25 adapter's giveup
# convention so the harness never spins forever inside this one.
_GIVEUP_DEFAULT = 4000

# size_clusters' ratio-jump threshold for splitting ring outer-bbox areas
# into "piece" vs "frame" size classes. 1.5 matches every other script25
# adapter's use of size_clusters (sb26, m0r0) -- no game-specific tuning.
_SIZE_CLUSTER_RATIO = 1.5


def _bbox_area(bbox: tuple[int, int, int, int]) -> int:
    r0, c0, r1, c1 = bbox
    return (r1 - r0 + 1) * (c1 - c0 + 1)


def _ring_region(ring: dict[str, Any]) -> Region:
    """A :func:`closed_frames` ring reshaped into a ``find_regions``-style dict.

    Uses the ring's own BORDER cells (outer bbox minus hole) rather than its
    interior marker pixel(s) -- the marker's colour is exactly what an
    ACTION6 select swaps (active/inactive highlight), so tracking by the
    marker would spuriously read a selected-but-not-moved piece as
    "vanished" under :func:`admorphiq.kernels.track_objects`' colour-locked
    matching. The border colour is redrawn identically every frame
    regardless of active state, so it is the stable identity signal.
    """
    r0, c0, r1, c1 = ring["outer_bbox"]
    all_cells = {(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)}
    cells = frozenset(all_cells - ring["hole_cells"])
    if not cells:
        cells = frozenset(all_cells)
    rows = [r for r, _c in cells]
    cols = [c for _r, c in cells]
    centroid = (sum(rows) / len(cells), sum(cols) / len(cells))
    return {
        "color": ring["border_color"],
        "cells": cells,
        "bbox": ring["outer_bbox"],
        "centroid": centroid,
        "size": len(cells),
    }


def _piece_marker_color(grid: tuple[tuple[int, ...], ...], outer_bbox: tuple[int, int, int, int]) -> int | None:
    """The colour at a piece ring's own single interior (hole) cell.

    MEASURED (``.wiki`` was silent on this): a ring qualifies as a "piece"
    only when its hole is exactly one cell (see ``_classify_rings``), so
    the hole cell is the ring's own centre -- (r0+1, c0+1) when the ring
    is a genuine 3x3 ring. Generalised (not hardcoded to 3x3): returns
    ``None`` when the interior isn't exactly one cell or falls outside the
    grid, so a caller can fall back to a different verification instead of
    reading a wrong pixel.
    """
    r0, c0, r1, c1 = outer_bbox
    ir0, ic0, ir1, ic1 = r0 + 1, c0 + 1, r1 - 1, c1 - 1
    if ir0 != ir1 or ic0 != ic1:
        return None
    if not (0 <= ir0 < len(grid) and grid and 0 <= ic0 < len(grid[0])):
        return None
    return grid[ir0][ic0]


def _classify_rings(
    grid: tuple[tuple[int, ...], ...], background: int
) -> tuple[list[Region], list[dict[str, Any]]]:
    """Split every ring on ``grid`` into (piece regions, matching frame rings).

    Pieces are the smallest outer-bbox size class; a frame ring only
    qualifies as a usable target when its ``inner_bbox`` area matches SOME
    detected piece's own ``outer_bbox`` area (the measured "this frame
    accepts this piece class" test -- see module docstring's level-2 scope
    note). Frame rings whose interior matches no piece class are returned
    neither as pieces nor as targets: this adapter has no piece to route
    there and must not mis-plan around them.
    """
    rings = closed_frames(grid, background=background)
    if len(rings) < 2:
        return [], []
    areas = [_bbox_area(r["outer_bbox"]) for r in rings]
    clusters = size_clusters([{"size": a} for a in areas], ratio=_SIZE_CLUSTER_RATIO)
    if len(clusters) < 2:
        return [], []
    clusters_sorted = sorted(clusters, key=lambda idxs: areas[idxs[0]])
    piece_idxs = clusters_sorted[0]
    piece_areas = {areas[i] for i in piece_idxs}
    pieces = [_ring_region(rings[i]) for i in piece_idxs]
    targets: list[dict[str, Any]] = []
    for cluster in clusters_sorted[1:]:
        for i in cluster:
            ring = rings[i]
            if _bbox_area(ring["inner_bbox"]) in piece_areas:
                targets.append(ring)
    return pieces, targets


class Adapter(GameAdapter):
    """Multi-piece configuration-path delivery, composed from admorphiq.kernels."""

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

        self._pending_action: int | None = None
        self._pending_kind: str | None = None  # "move" | "select" | None
        # The cell a "move" action was hypothesized to originate from when
        # it was chosen (see _probe/_route) -- used to attribute a BLOCKED
        # outcome to the right cell even right after a select, when
        # self._active_cell is still the stale pre-click value and cannot
        # be trusted as "whoever this move was issued for".
        self._pending_ref_cell: Cell | None = None
        self._prev_grid: tuple[tuple[int, ...], ...] | None = None
        self._prev_piece_regions: list[Region] | None = None

        # Current best-known active piece's cell (its outer-bbox
        # top-left), or None while identity is still unknown.
        self._active_cell: Cell | None = None

        # A select click's effect is invisible to _observe_result on its
        # own turn (see class docstring: no assumed highlight colour), so
        # the call immediately after one MUST be a movement probe -- this
        # is how the click's outcome gets measured at all. Without forcing
        # this, _decide would recompute the identical "not yet selected"
        # assignment and re-issue the same click forever.
        self._await_select_confirm = False
        # The piece cell a pending select click targeted -- the reference
        # cell for the forced post-select probe's untried-action choice.
        self._last_select_cell: Cell | None = None
        # Per-cell count of select clicks issued while that cell never
        # confirmed active -- drives _select_point's corner cycling.
        self._select_attempts: dict[Cell, int] = {}
        # The colour the ACTIVE piece's own centre pixel shows, measured
        # (never hardcoded) the first time a movement genuinely confirms
        # which piece is active -- MEASURED on the gold trace to be a
        # stable per-level constant (every observed successful select in
        # data/traces/ka59.npz showed the same colour on the newly-active
        # piece, though the INACTIVE colour varies per piece/sprite). Once
        # known, a select's success is verifiable by comparing a piece's
        # own centre pixel colour to this value -- no extra movement probe
        # needed. Property of the level's sprite assignment: persists
        # across a GAME_OVER restart (see _on_restart), reset on level-up.
        self._active_marker_color: int | None = None

        # Every target cell ever measured via closed_frames this level,
        # kept even on a call where re-detection fails -- MEASURED
        # necessary: a piece merely passing adjacent to (not yet exactly
        # aligned with) a frame can overlap one shared border pixel and
        # break closed_frames' exact-ring match for that frame on THIS
        # frame only, making it vanish from _classify_rings' targets for
        # one or more calls even though it is a real, still-unfilled,
        # static frame. Frames never move, so once seen a target cell is
        # trusted until a piece is actually observed sitting on it.
        self._known_targets: set[Cell] = set()

        # Measured (cell, action, cell) transitions -- the state-space
        # graph configuration_path / reachable_frontier search over.
        # Property of the level layout: reset on level-up, kept across a
        # GAME_OVER restart (the walls didn't move, only the active
        # piece's position did).
        self._transitions: list[tuple[Cell, int, Cell]] = []
        self._adj: dict[Cell, list[tuple[int, Cell]]] = {}
        self._tried_from: dict[Cell, set[int]] = {}
        self._action_plan: list[int] = []

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
            self._prev_piece_regions = None
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
        self._prev_grid = None
        self._prev_piece_regions = None
        self._active_cell = None
        self._transitions = []
        self._adj = {}
        self._tried_from = {}
        self._action_plan = []
        self._await_select_confirm = False
        self._last_select_cell = None
        self._select_attempts = {}
        self._known_targets = set()
        self._active_marker_color = None

    def _on_restart(self) -> None:
        """Only the active piece's position resets; the layout knowledge
        (transitions/tried_from/dir_map) is kept -- see class docstring."""
        self._pending_action = None
        self._pending_kind = None
        self._prev_grid = None
        self._prev_piece_regions = None
        self._active_cell = None
        self._action_plan = []
        self._await_select_confirm = False
        self._last_select_cell = None
        self._select_attempts = {}

    # ── measurement: did the pending action move a piece? ───────────────

    def _observe_result(self, grid: tuple[tuple[int, ...], ...]) -> None:
        action = self._pending_action
        kind = self._pending_kind
        ref_cell = self._pending_ref_cell
        prev_pieces = self._prev_piece_regions
        self._pending_action = None
        self._pending_kind = None
        self._pending_ref_cell = None
        if action is None or kind != "move" or self._prev_grid is None or not prev_pieces:
            return

        bg = most_common_color(grid)
        cur_pieces, _targets = _classify_rings(grid, bg)
        tracked = track_objects(prev_pieces, cur_pieces)
        moved = [m for m in tracked["matches"] if tuple(m["shift"]) != (0, 0)]  # type: ignore[arg-type]
        if len(moved) != 1:
            if ref_cell is not None:
                self._record_blocked(ref_cell, action, prev_pieces)
            return

        match = moved[0]
        from_cell: Cell = prev_pieces[match["before"]]["bbox"][:2]  # type: ignore[index]
        shift: Cell = tuple(match["shift"])  # type: ignore[assignment]
        self._dir_map.setdefault(action, shift)
        new_cell = (from_cell[0] + shift[0], from_cell[1] + shift[1])
        self._adj.setdefault(from_cell, []).append((action, new_cell))
        self._transitions.append((from_cell, action, new_cell))
        self._tried_from.setdefault(from_cell, set()).add(action)
        self._active_cell = new_cell

        if self._active_marker_color is None:
            after_bbox = cur_pieces[match["after"]]["bbox"]  # type: ignore[index]
            color = _piece_marker_color(grid, after_bbox)  # type: ignore[arg-type]
            if color is not None:
                self._active_marker_color = color

    def _record_blocked(self, cell: Cell, action: int, prev_pieces: list[Region]) -> None:
        """Mark ``action`` tried from ``cell`` -- UNLESS the destination is
        currently occupied by another piece, in which case the block is
        state-dependent (that piece may move away later), not a permanent
        wall, so it is deliberately left unrecorded (see class docstring)."""
        unit = self._dir_map.get(action)
        if unit is None:
            self._tried_from.setdefault(cell, set()).add(action)
            return
        dest = (cell[0] + unit[0], cell[1] + unit[1])
        other_cells = {p["bbox"][:2] for p in prev_pieces}
        if dest in other_cells:
            return
        self._tried_from.setdefault(cell, set()).add(action)

    # ── planning ─────────────────────────────────────────────────────────

    def _assign(self, free_cells: list[Cell], unfilled_targets: list[Cell]) -> dict[Cell, Cell]:
        if not free_cells or not unfilled_targets:
            return {}
        matrix = [
            [-(abs(p[0] - t[0]) + abs(p[1] - t[1])) for t in unfilled_targets] for p in free_cells
        ]
        pairs = assign_pairs(matrix)
        return {free_cells[i]: unfilled_targets[j] for i, j in pairs}

    def _decide(
        self, grid: tuple[tuple[int, ...], ...], move_ids: list[int], action6_ok: bool
    ) -> GameAction:
        if not move_ids:
            self._pending_action = None
            self._pending_kind = None
            return reset_action()

        bg = most_common_color(grid)
        pieces, targets = _classify_rings(grid, bg)
        self._prev_piece_regions = pieces
        if not pieces:
            return self._probe(move_ids)

        # Target cells are STICKY within a level (see class field docstring
        # on _known_targets): a target missing from THIS call's targets
        # (piece-overlap detection corruption) is still trusted if it was
        # ever seen before, rather than treated as satisfied or gone.
        self._known_targets |= {t["inner_bbox"][:2] for t in targets}  # type: ignore[misc]

        piece_cells = [p["bbox"][:2] for p in pieces]  # type: ignore[misc]
        piece_cell_set = set(piece_cells)

        if self._await_select_confirm:
            self._await_select_confirm = False
            confirmed = self._select_confirmation(grid, pieces, piece_cells)
            if confirmed is True:
                # The clicked piece's own centre pixel already shows the
                # measured active-marker colour -- no movement probe
                # needed at all; fall through to route/assign normally
                # with the now-known active cell, saving the action a
                # forced probe would have spent.
                self._active_cell = self._last_select_cell
            elif confirmed is False:
                # CONCLUSIVE miss (marker colour is known and does not
                # match) -- retry immediately with a different point on
                # the SAME piece rather than spending an action on a
                # movement probe first; the colour check itself is the
                # verification, no probe needed to learn this failed.
                goal_region = next(
                    p for p, c in zip(pieces, piece_cells) if c == self._last_select_cell
                )
                self._pending_action = None
                self._pending_kind = "select"
                self._await_select_confirm = True
                point = self._select_point(goal_region, self._last_select_cell)  # type: ignore[arg-type]
                return click_action(x=point[1], y=point[0])
            else:
                # Inconclusive (marker colour not measured yet this
                # level, or the piece isn't currently detected at all) --
                # fall back to a movement probe targeted at the piece we
                # tried to select, not the globally first move id, so a
                # direction that happens to be wall-blocked for that
                # piece isn't confused with "the click failed" (neither
                # produces a shift on its own).
                return self._probe(move_ids, cell=self._last_select_cell)
        free_cells = [c for c in piece_cells if c not in self._known_targets]
        unfilled_targets = sorted(c for c in self._known_targets if c not in piece_cell_set)

        if not free_cells or not unfilled_targets:
            return self._probe(move_ids)

        assignment = self._assign(free_cells, unfilled_targets)

        if self._active_cell in assignment:
            return self._route(assignment[self._active_cell], move_ids)

        if self._active_cell is None:
            # Identity unknown: probe a movement direction. _observe_result
            # will read WHICH piece actually moved from the next frame,
            # revealing the active piece without ever assuming it.
            return self._probe(move_ids)

        if not assignment:
            return self._probe(move_ids)

        if not action6_ok:
            # Can't switch control at all this frame; nothing more to do
            # for the currently-active (already-placed or unassigned)
            # piece -- probe harmlessly rather than stall.
            return self._probe(move_ids)

        goal_cell = min(
            assignment,
            key=lambda c: abs(c[0] - self._active_cell[0]) + abs(c[1] - self._active_cell[1]),  # type: ignore[index]
        )
        goal_region = next(p for p, c in zip(pieces, piece_cells) if c == goal_cell)
        self._pending_action = None
        self._pending_kind = "select"
        self._await_select_confirm = True
        self._last_select_cell = goal_cell
        point = self._select_point(goal_region, goal_cell)
        return click_action(x=point[1], y=point[0])

    def _select_confirmation(
        self, grid: tuple[tuple[int, ...], ...], pieces: list[Region], piece_cells: list[Cell]
    ) -> bool | None:
        """Whether ``self._last_select_cell``'s piece now shows the
        measured active-marker colour.

        Returns ``True``/``False`` when conclusive, ``None`` when the
        check cannot be made yet (the marker colour hasn't been measured
        this level, or the targeted cell isn't currently detected as a
        piece at all -- e.g. transient re-detection noise) -- the caller
        falls back to a movement probe only in the ``None`` case.
        """
        if self._active_marker_color is None or self._last_select_cell is None:
            return None
        if self._last_select_cell not in piece_cells:
            return None
        idx = piece_cells.index(self._last_select_cell)
        color = _piece_marker_color(grid, pieces[idx]["bbox"])  # type: ignore[arg-type]
        if color is None:
            return None
        return color == self._active_marker_color

    def _select_point(self, region: Region, cell: Cell) -> Cell:
        """The (row, col) to click for ``region``, varying across repeated
        failed attempts at the SAME cell (bounded corner cycling) rather
        than clicking the identical point forever -- a select that keeps
        not taking effect may mean that specific point lands outside the
        sprite's own click hit-test, not that clicking never works.

        The FIRST attempt is the piece's own outer-bbox TOP-LEFT corner,
        not its centroid -- MEASURED from every one of the 14 gold-trace
        ACTION6 clicks in ``data/traces/ka59.npz``: each one lands
        EXACTLY on the selected piece's outer-bbox top-left corner (to
        the pixel, across 3 different levels), never the centre. Centroid
        is kept as the second fallback rather than dropped outright, since
        it is still a valid interior point if the top-left corner ever
        turns out not to register for some board.
        """
        attempts = self._select_attempts.get(cell, 0)
        self._select_attempts[cell] = attempts + 1
        centroid = (round(region["centroid"][0]), round(region["centroid"][1]))
        r0, c0, r1, c1 = region["bbox"]
        candidates = [(r0, c0), centroid, (r1, c1), (r0, c1), (r1, c0)]
        return candidates[attempts % len(candidates)]

    def _pick_action(self, candidates: list[int], ref_cell: Cell, goal: Cell | None) -> int:
        """Choose among untried ``candidates`` from ``ref_cell``.

        With no ``goal`` (identity still unknown, or no useful hint
        available), the first candidate in ``move_ids`` order is used --
        arbitrary but deterministic. With a ``goal``, a candidate whose
        MEASURED direction (``dir_map``) is already known is scored by the
        Manhattan distance its predicted destination leaves to ``goal``
        (ascending -- prefer directions that measurably approach the goal);
        a candidate with no measured direction yet is deprioritized behind
        every measured one (tier 1 vs tier 0) since trying it can only be
        evaluated AFTER the fact, but is still tried once every measured
        direction from this cell is exhausted, so every action still gets
        learned eventually. This exists purely to spend fewer of a level's
        tightly fused action budget wandering AWAY from a known target once
        enough of the control scheme is already measured -- it never
        invents a destination the adapter hasn't actually observed.
        """
        if goal is None:
            return candidates[0]

        def score(action: int) -> tuple[int, int]:
            unit = self._dir_map.get(action)
            if unit is None:
                return (1, 0)
            dest = (ref_cell[0] + unit[0], ref_cell[1] + unit[1])
            return (0, abs(dest[0] - goal[0]) + abs(dest[1] - goal[1]))

        return min(candidates, key=score)

    def _probe(
        self, move_ids: list[int], cell: Cell | None = None, goal: Cell | None = None
    ) -> GameAction:
        ref_cell = cell if cell is not None else self._active_cell
        self._pending_ref_cell = ref_cell
        if ref_cell is not None:
            tried = self._tried_from.get(ref_cell, set())
            untried = [a for a in move_ids if a not in tried]
            if untried:
                action = self._pick_action(untried, ref_cell, goal)
                self._pending_action = action
                self._pending_kind = "move"
                return simple_action(action)
        self._pending_action = move_ids[0]
        self._pending_kind = "move"
        return simple_action(move_ids[0])

    def _route(self, goal_target: Cell, move_ids: list[int]) -> GameAction:
        if self._active_cell == goal_target:
            return self._probe(move_ids)

        # Every move this function issues is hypothesized to originate from
        # the currently-trusted active cell -- see _observe_result's use of
        # _pending_ref_cell to attribute a blocked outcome correctly.
        self._pending_ref_cell = self._active_cell

        if self._action_plan:
            action = self._action_plan.pop(0)
            self._pending_action = action
            self._pending_kind = "move"
            return simple_action(action)

        path = configuration_path(
            initial=self._active_cell,
            goal_test=lambda c: c == goal_target,
            successors=lambda c: self._adj.get(c, []),
        )
        if path:
            self._action_plan = list(path)  # type: ignore[arg-type]
            action = self._action_plan.pop(0)
            self._pending_action = action
            self._pending_kind = "move"
            return simple_action(action)

        tried_pairs = {(cell, a) for cell, acts in self._tried_from.items() for a in acts}
        frontier = reachable_frontier(self._transitions, self._active_cell, tried_pairs)
        if frontier:
            cell, action = frontier[0]
            if cell == self._active_cell:
                self._pending_action = action  # type: ignore[assignment]
                self._pending_kind = "move"
                return simple_action(action)  # type: ignore[arg-type]
            sub_path = configuration_path(
                initial=self._active_cell,
                goal_test=lambda c: c == cell,
                successors=lambda c: self._adj.get(c, []),
            )
            if sub_path:
                self._action_plan = list(sub_path)  # type: ignore[arg-type]
                action = self._action_plan.pop(0)
                self._pending_action = action
                self._pending_kind = "move"
                return simple_action(action)

        untried = [a for a in move_ids if a not in self._tried_from.get(self._active_cell, set())]
        if untried:
            action = self._pick_action(untried, self._active_cell, goal_target)  # type: ignore[arg-type]
            self._pending_action = action
            self._pending_kind = "move"
            return simple_action(action)

        return self._probe(move_ids)
