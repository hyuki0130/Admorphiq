"""script25 quarantined adapter: SB26 (portal-graph sort/assignment family).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/SB26.md`` and ``docs/r57_win_condition_typology_20260715.md``
(read for reference, not imported) describe SB26 as a portal-graph traversal
puzzle disguised as a simple reference/pool colour-match sort (R57's "T3 —
Assignment/Matching" type: two designated region sets must become equal as
multisets of (colour, shape)). The board holds one or more bordered FRAMES,
each exposing N slots; a slot holds either a plain colour item or a PORTAL
that redirects traversal to a different frame (matched by that frame's
border colour). The level clears when a DFS traversal starting at the
first frame, following portals slot-by-slot, visits item slots whose
colours match a target sequence (read off a separate display band) in
TRAVERSAL order, not screen order.

``src/admorphiq/sort_match.py`` (read for MECHANIC understanding only, never
imported -- quarantine: stdlib + admorphiq.kernels + admorphiq.adapters25.base
only) already implements this correctly, but with two properties this
adapter deliberately does NOT carry over: (a) a fixed six-pixel slot grammar
(``x0+2+i*6``) for computing slot positions arithmetically from a frame's
bbox -- exactly the kind of game-specific constant the quarantine forbids;
(b) hardcoded frame/pipe structural detection duplicating what
``admorphiq.kernels.geometry`` now provides generically. This adapter
MEASURES slot positions instead (see role assignment below) and composes
``closed_frames``/``connectors`` for frame and portal detection.

**Offline verification (before any live action, per the R56 discipline of
falsifying before committing budget)**: loaded ``data/traces/sb26.npz``
(gold demonstration traces, label-generation only, never imported into this
adapter). Level 0's (wiki "L1") 8 gold click coordinates matched, to the
pixel after rounding, either a POOL-swatch region's centroid (uniform
~16px clusters in the bottom band) or a SLOT-marker region's centroid
(uniform ~4px clusters inside a ``closed_frames``-detected hollow box) --
confirming slot positions are directly measurable from small uniform-size
clusters, not arithmetic. Running :func:`_plan_sb26` itself (this module's
own function, not the reference solver) against every one of the 8 levels'
gold frames found a structurally valid plan (paired pool/slot clicks plus a
verify) for **7 of 8 levels** -- only level 1 (wiki "L2", the two-frame
portal case) failed, diagnosed below as a genuine kernel-coverage gap at
the time (since resolved -- see "Fused-frame recovery" below), not a bug
in this adapter's own logic.

Two problems were found and fixed during offline verification, both
load-bearing:

1. **Decorative single-item "frames" pollute closed_frames.** Each
   target-sequence marker in the display band is ITSELF a small hollow
   square (a colour border around one interior dot) -- ``closed_frames``
   correctly reports these as frames too, alongside the one genuine
   multi-slot placement frame. :func:`_filter_interactive_frames` and the
   ">=2 measured slots" guard in :func:`_plan_sb26` both filter these out;
   a frame with only one content region is structurally indistinguishable
   from a decorative marker and is dropped.
2. **A repeated connective chrome colour pollutes the target band.** The
   marker squares' own border colour also forms a larger connecting
   backdrop shape spanning the whole display band, which
   :func:`group_by_axis` correctly groups into the SAME row-band as the
   genuine target dots. Since that chrome colour is never suppliable from
   the pool (only genuine target colours are), filtering target-band
   regions to "colour is in the pool" cleanly removes it without assuming
   any specific chrome colour.

**Fused-frame recovery (level 1, portal case) -- formerly a kernel gap,
now resolved for BOTH of the level's two real frames**: neither of level
1's two REAL multi-slot frames is a pure rectangle border, but for two
DIFFERENT reasons, so ``closed_frames``'s exact "cells == rectangle
border" match rejects both outright (it never even reaches
``connectors``, which only separates ALREADY-distinct thin paths from
already-detected regions, not a fused/occluded shape):

- **Frame 1 (colour 14)** has a portal pipe fused onto its own edge as ONE
  connected component -- EXTRA same-colour cells.
  :func:`admorphiq.kernels.geometry.split_fused_frame` (the generic
  namespace-safe replacement for ``sort_match.py``'s game-specific
  ``_split_box_pipe``) recovers it.
- **Frame 2 (colour 8)** is missing 2 of its 72 perimeter cells --
  measured (``data/traces/sb26.npz`` level_index 1, frame 10): those 2
  cells are occupied by frame 1's own colour-14 pipe crossing frame 2's
  bottom border on its way to frame 1's ring. This is the OPPOSITE shape
  defect (too FEW cells, from a foreign-coloured occluder, not too many
  from a same-coloured appendage) --
  :func:`admorphiq.kernels.geometry.recover_occluded_frame` (R56,
  2026-07-15) recovers it, given every OTHER candidate region on the
  frame as its occluder set (never a specific colour -- the quarantine's
  "no hardcoded coordinates/palettes" rule applies to occluder selection
  too).

:func:`_recover_fused_frames` dispatches each candidate by comparing its
own cell count to its bbox's perimeter (a clean ring's cells equal that
perimeter EXACTLY -- ``closed_frames``' own test -- so an exact match is
never even tried here): MORE cells tries ``split_fused_frame``, FEWER
tries ``recover_occluded_frame``. Both kernels reject a shape that isn't
genuinely their case (``split_fused_frame`` rejects a solid block;
``recover_occluded_frame`` rejects a gap no occluder explains), so the
size-comparison dispatch is a cheap pre-filter, not a correctness guard.
Either recovered frame is reshaped into the same ``{"border_color",
"outer_bbox", "inner_bbox", "hole_cells"}`` shape ``closed_frames``
produces and unioned into the frame list BEFORE
:func:`_filter_interactive_frames` runs, so every downstream consumer
(slot detection, portal detection, DFS traversal) needs no changes at
all -- a recovered frame is indistinguishable from a clean one.

Role assignment (declared HERE, not in the kernel layer, which knows
nothing about frames, slots, portals, or targets):

  - Every :func:`admorphiq.kernels.closed_frames` hit with at least 2
    measured content slots (see below) is a portal-graph FRAME (a
    placement target), sorted by the kernel's own deterministic order
    (outer bbox top-left) -- frame 0 is the DFS traversal root, matching
    the wiki's own "frame[0]" language. A frame with only one content
    region is a decorative target-sequence marker, not a real frame (see
    "Offline verification" above).
  - A frame's CONTENT is every candidate region whose cells fall inside its
    ``hole_cells``. :func:`admorphiq.kernels.size_clusters` splits that
    content by size; the SMALLEST size class is the frame's SLOT markers
    (measured: SB26's own empty-slot markers are small, uniform, and
    smaller than any colour item on the board) -- their centroids, sorted
    left-to-right, are the slot click targets. (When a frame's content is a
    single size class, that class IS the slot set.)
  - Every OTHER candidate region (outside every frame's ``hole_cells``) is
    grouped into row-bands via :func:`admorphiq.kernels.group_by_axis`; the
    TOPMOST band is the TARGET/reference sequence (filtered to colours the
    pool can actually supply -- see "Offline verification" above -- since
    that band also contains connective marker chrome); its regions'
    colours, left-to-right, are the traversal-consumed target order for
    THIS adapter's single-frame case (multi-frame DFS order is handled
    separately below). The BOTTOMMOST band is the POOL (individual colour
    swatches, one instance per slot demand -- measured on the portal level,
    NOT a small fixed reusable set).
  - PORTALS: :func:`admorphiq.kernels.geometry.connectors` finds thin paths
    linking exactly two frames (using each frame's own border cells as a
    pseudo-region, rebuilt fresh from ``outer_bbox`` -- a RECOVERED fused
    frame's outer_bbox already excludes the appendage/pipe cells, so its
    pseudo-region is identical in shape to a clean frame's and needs no
    special-casing here). For each connector, whichever frame's slot
    markers sit closer to the connector's path is the portal's SOURCE
    (that frame's nearest slot redirects traversal to the OTHER frame).
  - Candidate regions exclude the same two RELATIVE-geometry chrome classes
    ``admorphiq.adapters25.su15`` uses (a HUD band spanning almost the full
    frame width/height while only a few cells thick -- measured: SB26 has a
    full-width 1-tall status row exactly like SU15's; and an oversized
    region above a frame-size-fraction ceiling), never absolute pixel
    coordinates.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments the frame.
  - :func:`admorphiq.kernels.closed_frames` detects clean portal-graph
    frames; :func:`admorphiq.kernels.geometry.split_fused_frame` and
    :func:`admorphiq.kernels.geometry.recover_occluded_frame` recover the
    ones closed_frames rejects because a same-colour appendage is fused
    onto the border (too many cells) or a foreign-coloured region occludes
    part of it (too few cells), respectively (see "Fused-frame recovery"
    above; together these replace sort_match's own hollow-rectangle-vs-pipe
    splitting).
  - :func:`admorphiq.kernels.connectors` detects the portal pipes linking
    frames (replacing sort_match's own endpoint-to-frame-membership scan).
  - :func:`admorphiq.kernels.group_by_axis` separates the target-sequence
    band from the pool band by row position (replacing sort_match's fixed
    ``_TOP_BAND``/``_BOT_BAND`` row-cutoff constants).
  - :func:`admorphiq.kernels.size_clusters` separates a frame's slot markers
    from any pre-filled items by size (replacing an assumed marker colour).
  - :func:`admorphiq.kernels.frame_diff` measures whether a drained click
    had any visible effect, so a plan that stops working partway through
    (a wrong guess) is abandoned rather than drained blindly to the end.

The DFS traversal itself (:func:`_dfs_traversal`) is adapter-owned policy
over a small, MEASURED graph (a handful of frames/slots) -- not a
reimplementation of a generic kernel algorithm, the same way
``admorphiq.adapters25.su15``'s pair-ranking and
``admorphiq.adapters25.m0r0``'s frontier bookkeeping are adapter policy, not
banned "own search".

Deliberately out of scope (proof of concept, not a full solver): bottom-
portal PLACEMENT (a portal itself needing to be placed from the pool rather
than being a fixed board feature) and permutation search over multiple
candidate DFS roots/orderings -- the wiki flags both as needed for L3+ and
explicitly "banked" even by the more mature reference module.

**R94 structural delegation**: the load-bearing solving ENGINE (board parse ->
faithful offline portal-DFS simulator -> placement solve -> click plan) was
DISTILLED out of this adapter into ``admorphiq.kernels.simdfs`` (the "simdfs"
family core), extraction-not-rewrite so behaviour is byte-equivalent. This
adapter's planning call now DELEGATES to :func:`admorphiq.kernels.simdfs.
simdfs_plan` (the renamed ``_plan_sb26``); the same engine is wrapped by
:func:`admorphiq.kernels.simdfs.simdfs_core` into the offline model's patchable
sandbox card (``tools.solver_core.source_card("simdfs")``). What stays here is
the per-action harness orchestration ONLY: settle-wait for a multi-layer
transient level-entry stack, bounded plan-retry, ``frame_diff`` stall-abandon,
and draining the plan one click per env step. Eligibility (verified R94): the
portal-sort board is deterministic and static between actions, so the whole
plan is derivable from ONE settled frame -- expressible through the sandbox's
per-action before/after contract (``transitions`` are unused by the planner).
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
    reset_action,
    simple_action,
    state_name,
)
from admorphiq.kernels import frame_diff
from admorphiq.kernels.simdfs import simdfs_plan

GAME_ID = "sb26"

Grid = tuple[tuple[int, ...], ...]
PlanStep = tuple[Any, ...]

_GIVEUP_DEFAULT = 4000

# Bounded settle-wait at level entry: a multi-layer transient frame stack
# mis-reads structure (measured: detect_portal_sort returns None on the
# raw level-entry frame but valid placements from the very next frame --
# see the module docstring's offline verification). Mirrors
# admorphiq.world_model_agent's own _PORTAL_SETTLE_MAX.
_SETTLE_MAX_WAIT = 6

# Bounded number of planning attempts per level. A level-entry frame can be a
# transient where the board (e.g. the pool piece colours on the pool-portal
# level) has not fully rendered; each failed attempt idles one frame to let it
# settle. Generous enough to cover the settle, small enough to bail on a
# genuinely unsupported layout rather than spin.
_PLAN_MAX_TRIES = 8

# Consecutive drained clicks producing zero visible change before the
# remaining plan is abandoned (a wrong layout guess should not be drained
# blindly to the end). Mirrors world_model_agent's own
# _MERGE_DRAG_STALL_LIMIT concept, independently measured via frame_diff.
_STALL_LIMIT = 3


class Adapter(GameAdapter):
    """Portal-graph DFS placement composed entirely from admorphiq.kernels."""

    GAME_ID = GAME_ID

    @classmethod
    def _detect_mechanic(cls, latest_frame: Any) -> bool:
        """A portal-graph sort board: the pick-place-undo control scheme AND a parse.

        1. **No avatar, pick and place with an undo.** This puzzle has nothing to walk —
           you take an item from the pool, place it in a slot, and can cancel — so it
           offers clicks plus ACTION5 and ACTION7 and no movement at all.
        2. **The board parses.** `simdfs_plan` reads the target sequence band, the
           bordered frames with their border-colour identity, the slots and the pipes
           that link frames, and returns None when the board is not one of these.

        ⛔ Condition 2 alone is NOT enough, and that is measured rather than assumed: on
        its own the parse accepts `s5i5` and `sc25` too, and a full-25 run with only it
        took s5i5 from 0.0278 to 0.0000 while gaining sb26. A detector built on "my solver
        did not refuse" inherits the solver's permissiveness — which a solver may have and
        a detector may not.
        """
        simple_ids, has_click = available_action_ids(latest_frame)
        if not has_click or sorted(simple_ids) != [5, 7]:
            return False
        return bool(simdfs_plan(canonical_layer(latest_frame)))

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1
        self._plan: list[PlanStep] = []
        self._plan_tries = 0
        self._settle_wait = 0
        self._prev_grid: Grid | None = None
        self._stall_count = 0

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state in ("NOT_PLAYED", "GAME_OVER") or not has_frame(latest_frame):
            self._reset_level_state()
            return reset_action()

        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._levels_seen = levels
            self._reset_level_state()

        self._step += 1

        # Settle-wait: a multi-layer transient frame stack at level entry
        # mis-reads structure (see the module docstring's offline
        # verification). Bounded, one-shot per level.
        raw_layers = getattr(latest_frame, "frame", None) or []
        if len(raw_layers) > 1 and self._settle_wait < _SETTLE_MAX_WAIT:
            self._settle_wait += 1
            return click_action(x=0, y=0)

        grid = canonical_layer(latest_frame)
        self._observe(grid)

        simple_ids, action6_ok = available_action_ids(latest_frame)

        # Retry planning (bounded) until a plan is found: a level-entry frame can
        # be a transient (the pool renders its piece colours a frame or two after
        # the level loads — measured on the pool-portal level), so a single
        # attempt on the first frame reads an incomplete board. Idle (a harmless
        # corner click) between tries lets the board settle. L1-L3 find their plan
        # on the first good frame, so their behaviour is unchanged.
        if not self._plan and self._plan_tries < _PLAN_MAX_TRIES:
            self._plan_tries += 1
            plan = simdfs_plan(grid)
            if plan:
                self._plan = plan

        self._prev_grid = grid
        return self._next_action(grid, simple_ids, action6_ok)

    # ── level bookkeeping ───────────────────────────────────────────────

    def _reset_level_state(self) -> None:
        self._plan = []
        self._plan_tries = 0
        self._settle_wait = 0
        self._prev_grid = None
        self._stall_count = 0

    # ── measurement: did the last drained click do anything? ────────────

    def _observe(self, grid: Grid) -> None:
        if self._prev_grid is None or not self._plan:
            self._stall_count = 0
            return
        diff = frame_diff(self._prev_grid, grid)
        if diff["count"] == 0:
            self._stall_count += 1
        else:
            self._stall_count = 0
        if self._stall_count >= _STALL_LIMIT:
            # This layout guess stopped working partway through -- abandon
            # rather than drain a plan that is no longer tracking reality.
            self._plan = []
            self._stall_count = 0

    # ── planning: drain the precomputed plan one action per call ────────

    def _next_action(self, grid: Grid, simple_ids: list[int], action6_ok: bool) -> GameAction:
        while self._plan:
            kind, *rest = self._plan.pop(0)
            if kind == "click":
                if not action6_ok:
                    continue
                row, col = rest
                return click_action(x=col, y=row)
            aid = rest[0]
            if aid not in simple_ids:
                continue
            return simple_action(aid)
        # No plan yet (settling, unsupported layout, or exhausted) -- a harmless
        # idle click at the padding corner (never a sys_click sprite) so a
        # transient board can settle without perturbing any slot or pool piece.
        return click_action(x=0, y=0)
