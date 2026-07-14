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
- :func:`admorphiq.kernels.grid_shortest_path` + :func:`admorphiq.kernels.grid_distance_field`
  (superseding an earlier ``configuration_path``-based design, see
  "Optimistic goal-directed exploration" below) plan a piece's route over
  an OPTIMISTIC passability array built from ``_known_blocked`` --
  genuinely unexplored cells are assumed passable, so routing beelines
  toward a target instead of only trusting individually-confirmed-safe
  cells.

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

**Optimistic goal-directed exploration (round 3)**: replaced the
incrementally-discovered-graph ``configuration_path`` search with
:func:`admorphiq.kernels.grid_shortest_path` over an OPTIMISTIC
passability array (:meth:`Adapter._optimistic_grid`) -- every cell is
assumed passable except ones in ``_known_blocked`` (a CONFIRMED wall, see
:meth:`Adapter._record_blocked`), so the piece beelines straight toward
its assigned target through unexplored territory instead of only
trusting cells an individually-confirmed frontier crawl has already
visited. A refuted step costs exactly one action and adds one cell to
``_known_blocked``; the next call's fresh optimistic search routes around
it. When even the optimistic search finds no route at all (the target is
sealed off by CONFIRMED walls, not merely unexplored space -- the only
way an optimistic search can fail), :func:`admorphiq.kernels.reachable_frontier`
provides candidates ranked by :func:`admorphiq.kernels.grid_distance_field`
seeded FROM the target (not from the current cell), so exploration still
trends toward the goal.

Two further bugs surfaced and were fixed while measuring this:

1. **Solved-target flicker**: a piece sitting EXACTLY inside its own
   frame can itself become momentarily undetectable as a ring (same root
   cause as the sticky-target fix above, one level deeper) -- this made
   an ALREADY-SOLVED target look unfilled again for a call, misrouting
   the other piece back onto it. Fixed with a second sticky set,
   ``_solved_targets``, that only clears on a GAME_OVER restart (unlike
   ``_known_targets`` -- a solved placement genuinely reverts when the
   environment resets every piece to its level-start position, but a
   target's mere EXISTENCE does not).
2. **Action-priority trap**: :meth:`Adapter._pick_action` used to
   deprioritize any never-measured direction behind every already-known
   one, scored by distance. Once ``_route`` started depending on
   ``grid_shortest_path`` with ONLY ``self._dir_map``'s currently-known
   deltas as its move set, this became a real bug: a target reachable
   only via a direction not yet in ``dir_map`` is invisible to the
   optimistic planner (that direction isn't in its move set at all), so
   the adapter kept re-trying known-but-useless directions from
   ever-more cells instead of ever trying the one still-unmeasured
   direction that mattered. Fixed by trying any never-measured direction
   FIRST, unconditionally -- learning a new delta strictly increases what
   the planner can route through.

**Measured result**: with both fixes, all 4 directions are now learned
within the first ~8 actions of a level (previously one direction could
stay unmeasured for 25+ actions), and the optimistic planner replans
promptly on a refutation (32 replans across a full 500-action run, each
one a single wasted action, not a wasted multi-step plan). Level 0's
active piece was DEFINITIVELY measured to never reach past column 30 in
any of its explored rows, with cell (30, 33) explicitly recorded as a
CONFIRMED wall -- landing exactly inside the wall region independently
identified by the earlier gold-trace frame analysis (columns ~33-38).
This is now hard, repeatable evidence -- not merely an efficiency
shortfall -- that level 0's second target is genuinely unreachable by
pure movement: the gold solution crosses this same boundary only via a
collision-triggered push-slide (see "Push-mechanic correction" below),
which this adapter still does not model. Optimistic exploration is
therefore confirmed working exactly as designed; the remaining 0/7 is a
missing MECHANIC, not a search-budget or heuristic problem.

**Push-mechanic correction**: an earlier pass of this docstring claimed
"no pushing occurs on levels 0, 1, or 3" -- WRONG for level 0, corrected
here for the record. Tracing the full 12-action gold solution
frame-by-frame (raw ``find_regions``, not just piece-class rings) shows
one piece deliberately colliding with the other, triggering a multi-tick
push-slide that carries the second piece a long distance (column 27 to
42) past the same wall region this adapter's own exploration independently
confirmed impassable by direct movement.

**Push mechanic, IMPLEMENTED (round 4)**. Offline calibration first
(frame-by-frame trace of levels 1 and 3, the same methodology that found
level 0's push): level 1's only piece-count anomaly is the level0-to-
level1 TRANSITION tick (the "before" frame is still level 0's solved
board -- an artifact of the trace's own level-boundary labelling, not a
push), and level 3 never shows a >3px jump on any cleanly-matched piece
pair (every count mismatch there is the same detection-flicker the
sticky-target fixes above already explain). **Only level 0 (of the 4
gold-covered levels) needs a push.**

Implementation: colliding with another piece (``_record_blocked``'s
"destination occupied" branch) sets ``_push_settling``; ``choose_action``
then feeds cheap ticks -- MEASURED necessary, since the engine consumes
every submitted action as an animation tick regardless of type while a
slide resolves -- until 2 consecutive identical frames confirm it settled
(bounded at ``_PUSH_SETTLE_MAX_TICKS`` ticks), then forces full
re-identification (``_active_cell = None``) since positions may have
jumped unpredictably. Since this adapter's own assignment logic routes
each piece independently toward its OWN nearest target, it would never
naturally attempt a collision (walking into another piece is never on a
piece's direct path to ITS OWN goal) -- ``_route``'s last-resort tier
therefore deliberately walks the active piece TOWARD the nearest other
piece (colliding with it on the final step) once assigned-target routing
and frontier expansion are both exhausted, tried only there so it never
displaces the working walk-first behaviour on levels/games that don't
need a push.

**Measured live**: this genuinely works -- a push was observed carrying a
piece from (30, 27) to (30, 39), crossing the exact wall this adapter's
own optimistic search had independently confirmed at column 30-33. Three
further bugs surfaced and were fixed while getting this far, all in the
same family (a fallback silently repeating one action forever instead of
varying when it should): (1) post-push identity re-probing had no anchor
cell to key "tried" bookkeeping by, so it could repeat the SAME probe
action forever if that action happened to be blocked -- fixed with
``_identity_tried``, tracked independently of any cell. (2) the broader
frontier tier (which itself replaced ``reachable_frontier``'s narrower
walked-edges-only view, ALSO because it went fully empty once a cell's
own actions were exhausted) initially excluded the current cell from
its own candidates, so a cell with a perfectly good untried action could
still get routed away from and never actually tried -- fixed by checking
the current cell's own untried actions before considering any other
frontier cell. (3) both the select-confirmation probe and ``_probe``'s
generic last resort defaulted to the same fixed action forever once a
KNOWN cell had every action already tried (a case that did not exist
before push-triggered re-routing made revisiting an exhausted cell
common) -- fixed by cycling through actions instead of repeating one.

Despite all of this, **the 2x500 smoke result is still 0/7** -- the push
executes and crosses the wall, but the system as a whole (assignment +
select + push-settle + optimistic exploration, now interacting for the
first time) does not yet converge to a full level clear within the
100-action fuse across the available lives. The remaining gap was not
further root-caused given time spent; likely candidates are assignment
not coordinating WHICH piece should push versus walk, and the overhead
of re-identifying and re-assigning from scratch after every push and
restart. Flagged honestly as unresolved rather than claimed fixed.
"""

from __future__ import annotations

from collections.abc import Sequence
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
    grid_distance_field,
    grid_shortest_path,
    path_to_moves,
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

# A push-slide, once triggered, is MEASURED (read from the level 0 gold
# trace + a read-only source review) to consume every submitted action as
# an animation tick regardless of its nominal type, for several ticks,
# before the board re-stabilizes. This many CONSECUTIVE identical frames
# is trusted as "the slide is over" -- 1 alone risks a false-positive on
# an incidentally-static mid-slide tick.
_PUSH_SETTLE_STABLE_FRAMES = 2
# Bound on ticks spent waiting for a slide to settle, mirroring every
# other script25 adapter's settle-wait convention (sb26's _SETTLE_MAX_WAIT)
# so a slide that never stabilizes (misdetection) can't hang the adapter.
_PUSH_SETTLE_MAX_TICKS = 10


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
        # Target cells CONFIRMED solved (a piece's own cell exactly
        # matched it on some past call) -- sticky the same way, and for
        # the SAME underlying reason: a piece sitting exactly inside its
        # frame can itself become undetectable as a ring for a call or
        # two (its outer bbox now coincides with the frame's own
        # geometry), which would make _decide think that target is
        # unfilled again and re-route the WRONG piece back onto it,
        # oscillating between goals -- MEASURED live (this adapter's own
        # already-placed piece disappeared from piece_cells for single
        # calls, sending its sibling chasing an already-solved target).
        # Reset on a GAME_OVER restart too (unlike _known_targets): the
        # environment reverts every piece to its level-start position on
        # RESET, so "solved" genuinely stops being true, unlike "this
        # target exists" which remains true forever within the level.
        self._solved_targets: set[Cell] = set()

        self._tried_from: dict[Cell, set[int]] = {}
        # Cells CONFIRMED blocked (a move attempt failed with no other
        # piece at the destination -- see _record_blocked). Every other
        # cell is OPTIMISTICALLY assumed passable by _optimistic_grid, so
        # routing beelines through unexplored territory instead of only
        # trusting individually-confirmed-safe cells -- see _route.
        self._known_blocked: set[Cell] = set()

        # Diagnostic-only: how many times the optimistic straight-line
        # plan was refuted (a NEW cell entered _known_blocked, forcing a
        # different route on the next call). Never reset -- a whole-run
        # total, not a per-level state the adapter's own behaviour reads.
        self._replans = 0

        # True while a push-slide is believed to be resolving (see
        # _record_blocked: a move that collided with ANOTHER piece,
        # rather than a wall, starts a multi-tick engine animation --
        # MEASURED from the level 0 gold trace + read-only source review:
        # every submitted action is consumed as a tick, ignoring its
        # nominal type, until the board re-stabilizes). While True,
        # choose_action just feeds cheap ticks (see _settle_push) instead
        # of normal planning, since positions read mid-slide are not
        # trustworthy. Diagnostic-only: _pushes_settled counts completions.
        self._push_settling = False
        self._push_settle_stable = 0
        self._push_settle_ticks = 0
        self._pushes_settled = 0

        # Actions tried while _active_cell is None (identity unknown, no
        # anchor cell to key _tried_from by) -- see _probe. Cleared the
        # moment identity is re-established (_observe_result) or whenever
        # _active_cell is deliberately reset to None (level-up, restart,
        # post-push re-identification).
        self._identity_tried: set[int] = set()

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

        if self._push_settling:
            # A push-slide is resolving (see the field docstring): ride it
            # out with cheap ticks -- ANY submitted action is consumed as
            # an animation tick while this is in progress (measured), so
            # normal planning on a mid-slide frame would be reasoning
            # about positions that are about to change unpredictably.
            stable = self._prev_grid is not None and grid == self._prev_grid
            self._push_settle_stable = self._push_settle_stable + 1 if stable else 0
            self._push_settle_ticks += 1
            if (
                self._push_settle_stable >= _PUSH_SETTLE_STABLE_FRAMES
                or self._push_settle_ticks >= _PUSH_SETTLE_MAX_TICKS
            ):
                self._push_settling = False
                self._push_settle_stable = 0
                self._push_settle_ticks = 0
                self._pushes_settled += 1
                # Positions may have jumped unpredictably during the
                # slide -- force full re-identification via the existing
                # movement-probe pathway (self._active_cell is None)
                # rather than trust the stale pre-slide cell.
                self._active_cell = None
                self._identity_tried = set()
                self._prev_piece_regions = None
                # Fall through to normal planning this same call.
            else:
                self._pending_action = None
                self._pending_kind = None
                self._prev_grid = grid
                return simple_action(move_ids[0]) if move_ids else reset_action()

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
        self._identity_tried = set()
        self._tried_from = {}
        self._known_blocked = set()
        self._await_select_confirm = False
        self._last_select_cell = None
        self._select_attempts = {}
        self._known_targets = set()
        self._solved_targets = set()
        self._active_marker_color = None
        self._push_settling = False
        self._push_settle_stable = 0
        self._push_settle_ticks = 0

    def _on_restart(self) -> None:
        """Only the active piece's position resets; the layout knowledge
        (transitions/tried_from/dir_map) is kept -- see class docstring.
        ``_solved_targets`` is ALSO cleared here (unlike layout knowledge):
        RESET reverts every piece to its level-start position, so a target
        that was solved before this GAME_OVER genuinely stops being solved."""
        self._pending_action = None
        self._pending_kind = None
        self._prev_grid = None
        self._prev_piece_regions = None
        self._active_cell = None
        self._identity_tried = set()
        self._await_select_confirm = False
        self._last_select_cell = None
        self._select_attempts = {}
        self._solved_targets = set()
        self._push_settling = False
        self._push_settle_stable = 0
        self._push_settle_ticks = 0

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
            else:
                # Identity-probing with no anchor cell (see _probe) --
                # track this action as tried-while-blind so the next probe
                # varies instead of repeating the same refuted guess.
                self._identity_tried.add(action)
            return

        match = moved[0]
        from_cell: Cell = prev_pieces[match["before"]]["bbox"][:2]  # type: ignore[index]
        shift: Cell = tuple(match["shift"])  # type: ignore[assignment]
        self._dir_map.setdefault(action, shift)
        new_cell = (from_cell[0] + shift[0], from_cell[1] + shift[1])
        self._tried_from.setdefault(from_cell, set()).add(action)
        self._active_cell = new_cell
        self._identity_tried = set()

        if self._active_marker_color is None:
            after_bbox = cur_pieces[match["after"]]["bbox"]  # type: ignore[index]
            color = _piece_marker_color(grid, after_bbox)  # type: ignore[arg-type]
            if color is not None:
                self._active_marker_color = color

    def _record_blocked(self, cell: Cell, action: int, prev_pieces: list[Region]) -> None:
        """Mark ``action`` tried from ``cell`` -- UNLESS the destination is
        currently occupied by another piece, in which case moving into it
        is state-dependent (that piece may move away later, or may itself
        be PUSHED -- see below), not a permanent wall, so it is
        deliberately left unrecorded (see class docstring) rather than
        marked tried.

        A collision with another piece (not a wall) also starts push-slide
        settling (``_push_settling``): MEASURED from the level 0 gold
        trace -- walking the active piece into another piece's cell always
        triggers the engine's push-resolution animation, whether or not
        the push ultimately succeeds, so ``choose_action`` must ride out
        the resulting ticks and re-identify positions afterward rather
        than trust the stale pre-collision cell.

        A genuine wall (destination NOT occupied by another piece) is
        added to ``_known_blocked`` -- the fact _optimistic_grid reads to
        stop assuming that cell passable -- and counted as a replan: the
        NEXT optimistic beeline attempt will route around it instead of
        repeating the same refuted assumption.
        """
        unit = self._dir_map.get(action)
        if unit is None:
            self._tried_from.setdefault(cell, set()).add(action)
            return
        dest = (cell[0] + unit[0], cell[1] + unit[1])
        other_cells = {p["bbox"][:2] for p in prev_pieces}
        if dest in other_cells:
            self._push_settling = True
            return
        self._tried_from.setdefault(cell, set()).add(action)
        if dest not in self._known_blocked:
            self._known_blocked.add(dest)
            self._replans += 1

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
            elif self._last_select_cell is not None and len(
                self._tried_from.get(self._last_select_cell, set())
            ) >= len(move_ids):
                # Inconclusive AND the target cell's own directions are
                # ALL already known (every one is a confirmed wall, from
                # this cell's own earlier exploration under a different
                # active piece) -- MEASURED necessary: a movement probe
                # here can NEVER resolve anything new (every direction's
                # outcome is already determined, wall-vs-not, regardless
                # of which piece is standing there), so retrying one
                # forever (the naive fallback _probe would otherwise
                # repeat) can never confirm or refute the select. With no
                # better signal available, trust the click and resume
                # normal routing from here.
                self._active_cell = self._last_select_cell
            else:
                # Inconclusive (marker colour not measured yet this
                # level, or the piece isn't currently detected at all) --
                # fall back to a movement probe targeted at the piece we
                # tried to select, not the globally first move id, so a
                # direction that happens to be wall-blocked for that
                # piece isn't confused with "the click failed" (neither
                # produces a shift on its own).
                return self._probe(move_ids, cell=self._last_select_cell)

        # A target's SOLVED status is sticky too, once observed (see the
        # field docstring): a piece sitting exactly inside its frame can
        # itself become momentarily undetectable, which must not make an
        # already-placed target look unfilled again.
        self._solved_targets |= self._known_targets & piece_cell_set
        free_cells = [c for c in piece_cells if c not in self._known_targets]
        unfilled_targets = sorted(self._known_targets - self._solved_targets)

        if not free_cells or not unfilled_targets:
            return self._probe(move_ids)

        assignment = self._assign(free_cells, unfilled_targets)

        if self._active_cell in assignment:
            other_cells = [c for c in piece_cells if c != self._active_cell]
            return self._route(assignment[self._active_cell], move_ids, other_cells)

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

        A candidate whose direction has NEVER been measured anywhere
        (``not in self._dir_map``) is tried FIRST, unconditionally --
        MEASURED live to be necessary: with ``_route`` now planning via
        ``grid_shortest_path`` over ``self._dir_map.values()``, a target
        that requires a direction still absent from ``dir_map`` is
        UNREACHABLE to the optimistic planner no matter how much budget it
        gets (that direction is not even in its move set) -- learning a
        brand-new delta strictly increases what the planner can route
        through, which is worth more than any already-known direction's
        distance score. The earlier version scored an unmeasured candidate
        behind every measured one (preferring "closer, even if it's
        provably not the way there" over "unknown, but might be exactly
        what's missing") and could loop indefinitely re-trying known
        directions from ever-more cells while genuinely needing a
        direction it never once attempted.

        Once every candidate is measured, ties break by the Manhattan
        distance each candidate's predicted destination leaves to
        ``goal`` (ascending); with no ``goal`` at all (identity still
        unknown), the first candidate in ``move_ids`` order is used.
        """
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
        elif move_ids:
            # Identity genuinely unknown (no anchor cell at all -- e.g.
            # right after a push-slide, where positions jumped
            # unpredictably) -- MEASURED necessary: without this branch,
            # every call falls straight to the fixed move_ids[0] below,
            # which repeats the SAME action forever if it happens to be
            # blocked for whichever piece is secretly active, never
            # varying enough to ever reveal identity. _identity_tried
            # tracks "tried while blind" independently of any cell.
            untried = [a for a in move_ids if a not in self._identity_tried]
            if untried:
                self._pending_action = untried[0]
                self._pending_kind = "move"
                return simple_action(untried[0])
        # Truly nothing left to try (a known cell with every action
        # already tried, or blind identity-probing exhausted every
        # action too) -- every OTHER tier in _route already failed too,
        # so this is a genuine last resort. MEASURED necessary: always
        # defaulting to move_ids[0] here repeats the IDENTICAL action
        # forever with no chance of ever revealing new information (its
        # outcome from this exact cell is already fully determined);
        # cycling by self._step at least varies the probe, which can
        # matter if circumstances change from outside this cell's own
        # history (e.g. another piece that was blocking a direction
        # moves away).
        action = move_ids[self._step % len(move_ids)]
        self._pending_action = action
        self._pending_kind = "move"
        return simple_action(action)

    def _optimistic_grid(self, height: int = 64, width: int = 64) -> list[list[bool]]:
        """A ``grid_shortest_path``-shaped passability array: every cell is
        ``True`` (passable) EXCEPT the ones in ``_known_blocked``.

        This is the "optimistic" half of optimistic replanning -- genuinely
        unexplored territory is ASSUMED passable rather than excluded, so a
        shortest-path search beelines the piece straight toward its target
        instead of only trusting cells a slow, individually-confirmed
        frontier crawl has already visited. A wrong assumption costs
        exactly one refuted action (see ``_record_blocked``), after which
        the next call's grid excludes it and reroutes -- see ``_route``.
        """
        grid = [[True] * width for _ in range(height)]
        for r, c in self._known_blocked:
            if 0 <= r < height and 0 <= c < width:
                grid[r][c] = False
        return grid

    def _route(
        self, goal_target: Cell, move_ids: list[int], other_cells: Sequence[Cell] = ()
    ) -> GameAction:
        if self._active_cell == goal_target:
            return self._probe(move_ids)
        if not self._dir_map:
            # No direction measured yet at all -- nothing for grid_shortest_path
            # to plan with; fall back to a plain probe until at least one
            # action's delta is known.
            return self._probe(move_ids)

        # Every move this function issues is hypothesized to originate from
        # the currently-trusted active cell -- see _observe_result's use of
        # _pending_ref_cell to attribute a blocked outcome correctly.
        self._pending_ref_cell = self._active_cell

        moves = list(self._dir_map.values())
        move_labels = {unit: action for action, unit in self._dir_map.items()}
        optimistic = self._optimistic_grid()

        step = self._first_step(optimistic, self._active_cell, goal_target, moves, move_labels)
        if step is not None:
            self._pending_action = step
            self._pending_kind = "move"
            return simple_action(step)

        # The optimistic planner found NO route at all -- goal_target is
        # sealed off by CONFIRMED walls, not merely unexplored space (an
        # optimistic search only fails this way, since every unknown cell
        # is assumed open). Try the CURRENT cell's own untried actions
        # FIRST -- MEASURED necessary: without this check ahead of the
        # broader frontier search below, a current cell with a perfectly
        # good untried action would still get routed AWAY from (toward
        # some other frontier cell that also merely "has an untried
        # action"), and if that other cell then routes straight back
        # here, the two cells trap the piece in a permanent ping-pong
        # that never actually TRIES the untried action at either one.
        untried_here = [a for a in move_ids if a not in self._tried_from.get(self._active_cell, set())]
        if untried_here:
            action = self._pick_action(untried_here, self._active_cell, goal_target)  # type: ignore[arg-type]
            self._pending_action = action
            self._pending_kind = "move"
            return simple_action(action)

        # The current cell is fully exhausted. Fall back to frontier
        # exploration: any OTHER cell ever STOOD AT (a key in
        # _tried_from) with fewer than len(move_ids) actions tried is a
        # genuine frontier candidate, reachable or not via the
        # OPTIMISTIC grid (not reachable_frontier's narrower "walked
        # this exact edge before" view) -- MEASURED necessary:
        # reachable_frontier's graph (built only from this piece's own
        # successful moves) can be fully disconnected from every other
        # still-open cell (e.g. ones visited by a DIFFERENT piece, or
        # reached mid-push), leaving NO candidate at all even though the
        # optimistic map clearly shows a route there. Ranked by
        # proximity to the GOAL (grid_distance_field seeded FROM the
        # target) so expansion still trends toward the goal instead of
        # flooding outward blindly.
        frontier_cells = [
            c for c, tried in self._tried_from.items() if len(tried) < len(move_ids) and c != self._active_cell
        ]
        if frontier_cells:
            goal_distances = grid_distance_field(optimistic, [goal_target], moves=moves)
            frontier_cells.sort(key=lambda c: goal_distances.get(c, float("inf")))
            for cell in frontier_cells:
                sub_step = self._first_step(optimistic, self._active_cell, cell, moves, move_labels)
                if sub_step is not None:
                    self._pending_action = sub_step
                    self._pending_kind = "move"
                    return simple_action(sub_step)

        # Neither the direct optimistic beeline nor frontier expansion
        # made any progress -- as a last resort before falling back to
        # blind local probing, try walking the active piece TOWARD (and
        # so, on the final step, INTO) the nearest other piece. MEASURED
        # (level 0 gold trace): colliding with another piece triggers a
        # push-slide that can cross territory pure walking cannot (this
        # adapter's own optimistic search independently confirmed a
        # genuine wall on level 0 that ends exactly where gold's push
        # begins) -- see _record_blocked's push-settling. The optimistic
        # grid never marks a piece-occupied cell blocked, so
        # grid_shortest_path happily routes toward it; only tried once
        # assigned-target routing and frontier expansion are BOTH
        # exhausted, so this never displaces the working walk-first
        # behaviour on levels/games that don't need a push.
        for candidate in sorted(
            other_cells,
            key=lambda c: abs(c[0] - self._active_cell[0]) + abs(c[1] - self._active_cell[1]),  # type: ignore[index]
        ):
            push_step = self._first_step(optimistic, self._active_cell, candidate, moves, move_labels)
            if push_step is not None:
                self._pending_action = push_step
                self._pending_kind = "move"
                return simple_action(push_step)

        return self._probe(move_ids)

    @staticmethod
    def _first_step(
        grid: list[list[bool]],
        start: Cell,
        goal: Cell,
        moves: list[Cell],
        move_labels: dict[Cell, int],
    ) -> int | None:
        """The first action of ``grid_shortest_path(grid, start, goal)``, or
        ``None`` when unreachable on ``grid`` or the path is degenerate."""
        path = grid_shortest_path(grid, start, goal, moves=moves)
        if not path or len(path) < 2:
            return None
        try:
            return path_to_moves(path[:2], move_labels)[0]
        except ValueError:
            return None
