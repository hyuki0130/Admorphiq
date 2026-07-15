"""script25 quarantined adapter: AR25 (mirror-reflection coverage puzzle).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/AR25.md`` (read for reference, not imported) records
AR25's actual mechanic (measured offline, dev-time only; this adapter reads
only frames at runtime): the board holds one or more MOVABLE glyph pieces,
each rendered TOGETHER WITH its reflections across every mirror bar,
recursively (a kaleidoscope). A level is WON by COVERAGE — a fixed goal glyph
must be entirely covered by some piece pixel or one of its reflections. A
single ACTION1-4 press translates the active piece one cell, and every
reflected image moves by the reflection of that displacement, so one press
changes a LARGE number of pixels at once.

**Why the earlier blind explorer stalled**: the previous R56 build treated
AR25 as a generic transition-graph search over the joint piece/mirror
configuration. That reaches the legacy solver's 2/8 depth but only at a huge
budget (L0 in ~835 actions vs a 32-action human baseline), scoring ~0 on the
squared-efficiency metric — because blind search is BLIND to the reflection
coupling that makes a move so consequential.

**This build — learn the reflection model, then plan coverage**: the adapter
now composes the reflective-symmetry motion kernels
(:func:`admorphiq.kernels.learn_reflection_operators` /
:func:`admorphiq.kernels.plan_reflection_coverage`, the reflective analogue of
the ``learn_point_operators``/``plan_overwrites`` pair the R56 codex verdict
proposed, ``docs/r56_codex_toolbase_verdict_20260715.md``):

  1. **Probe** — issue each of ACTION1-4 once, each immediately followed by
     ACTION7 (UNDO), so every measured transition starts from the same level-
     start board. Each move + its reflected images translate together;
     :func:`learn_reflection_operators` recovers, purely from these frames,
     the mirror axis (from a column-move that splits the piece from its
     image), which cells are the driven piece, and the piece's per-action
     displacement.
  2. **Plan** — the goal glyph is the largest static (never-moving,
     non-HUD) cluster; :func:`plan_reflection_coverage` searches piece
     translations for one whose rendered footprint (piece + reflections)
     covers that glyph, returning a short action sequence.
  3. **Execute** — run the planned actions; the engine's own WIN fires as
     soon as coverage is achieved.

**Fallback**: when the reflection model can't be learned (no axis-splitting
observation — e.g. an axis-constrained single-direction piece, or a level
whose mechanic isn't single-piece reflective coverage) or no covering plan
exists (multi-piece joint levels), the adapter falls back to the same
generic transition-graph frontier exploration the previous build used, so
deeper levels never regress below that baseline.

**Why namespace-safe**: the adapter assigns roles (which cluster is the goal,
which is the piece) and declares the mechanic hypothesis (reflective
coverage), but every pixel algorithm and every search lives in
``admorphiq.kernels`` — no hardcoded coordinates, colours, mirror positions,
or bespoke BFS here. The reflection axis, piece footprint, per-action
displacements, and goal glyph are all learned from the live frames.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments the board (HUD masking +
    static-goal detection).
  - :func:`admorphiq.kernels.learn_reflection_operators` learns the mirror
    dynamics model from the probe transitions.
  - :func:`admorphiq.kernels.plan_reflection_coverage` plans the covering
    piece motion in that learned model.
  - :func:`admorphiq.kernels.canonical_key` /
    :func:`admorphiq.kernels.transition_shortest_path` drive the graph-
    frontier fallback exploration.
"""

from __future__ import annotations

from collections import deque
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
    canonical_key,
    find_regions,
    learn_reflection_operators,
    plan_reflection_coverage,
    transition_shortest_path,
)

GAME_ID = "ar25"

Cell = tuple[int, int]
Region = dict[str, Any]
Grid = tuple[tuple[int, ...], ...]

# Per-level safety cap, mirroring every other script25 adapter's giveup
# convention so the harness never spins forever inside this one.
_GIVEUP_DEFAULT = 4000

# A region spanning at least this fraction of the frame's own span in one
# axis while thin in the other is a HUD status bar. Independently declared
# here (each adapter's role assignments are its own) -- matches tu93/su15/
# sb26/dc22's convention.
_HUD_SPAN_FRACTION = 0.85
_HUD_THICKNESS_FRACTION = 0.06


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    """A thin strip spanning most of one axis, OR pinned to a frame edge.

    AR25's step counter (a bottom-row bar that SHRINKS one cell per action)
    and its right-column progress bar are both edge-pinned; the shrinking
    counter escapes the span-fraction test once it drops below the
    threshold, so the edge-pinned test is measured-necessary here exactly as
    in ``admorphiq.adapters25.tu93``. The full-length mirror bar is also
    caught by the full-span test — harmless, because the reflection axis is
    learned from the piece/image MOTION, not from the bar's pixels."""
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


def _mask_hud(grid: Grid) -> Grid:
    """Return ``grid`` with every edge-pinned HUD band overwritten by the
    background colour, so region detection reflects only the play area (the
    piece / image / goal configuration) and not the ticking step counter."""
    if not grid or not grid[0]:
        return grid
    height, width = len(grid), len(grid[0])
    bg = most_common_color(grid)
    hud_cells: set[Cell] = set()
    for region in find_regions(grid, background=bg):
        if _is_hud_band(region, height, width):
            hud_cells |= region["cells"]
    if not hud_cells:
        return grid
    return tuple(
        tuple(bg if (r, c) in hud_cells else grid[r][c] for c in range(width))
        for r in range(height)
    )


def _undo_available(latest_frame: Any) -> bool:
    """Whether ACTION7 (UNDO) is offered this frame.

    ``base.available_action_ids`` only surfaces ids 1-5, so the undo the
    probe schedule needs is read from the raw ``available_actions`` here."""
    for a in getattr(latest_frame, "available_actions", []) or []:
        aid = a if isinstance(a, int) else getattr(a, "value", getattr(a, "id", None))
        if aid == 7:
            return True
    return False


def _detect_goal(grid: Grid, background: int, moving_colors: frozenset[int]) -> frozenset[Cell] | None:
    """The largest static (non-moving-colour) region's cells, the goal glyph.

    ``moving_colors`` is what :func:`learn_reflection_operators` measured to
    move under the probes (the piece, its reflected image, any marker riding
    the piece); the goal is the biggest remaining coloured cluster, which the
    win condition requires the piece's rendered footprint to cover. Returns
    None when no static cluster exists."""
    best: frozenset[Cell] | None = None
    best_size = 0
    for region in find_regions(grid, background=background):
        if region["color"] in moving_colors:
            continue
        if region["size"] > best_size:
            best_size = region["size"]
            best = frozenset(region["cells"])
    return best


class Adapter(GameAdapter):
    """Learn AR25's reflection dynamics from probe transitions, then plan a
    covering piece motion; fall back to generic transition-graph frontier
    exploration when the reflection model is unavailable. Composed entirely
    from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        # The step counter ends an attempt in GAME_OVER; restart and keep
        # the learned graph so each life compounds (the board didn't change).
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        # ── reflection probe/plan state (per level) ────────────────────────
        # phase: "probe" (measuring), "plan" (executing a covering sequence),
        # "graph" (fallback frontier exploration once reflection is spent).
        self._phase = "probe"
        self._start_grid: Grid | None = None
        self._observations: list[dict[str, Any]] = []
        self._probe_queue: list[int] = []
        self._probe_ready = False
        self._pending_probe_action: int | None = None
        self._pending_probe_before: Grid | None = None
        self._plan_queue: list[int] = []

        # ── graph-fallback state ───────────────────────────────────────────
        # The incrementally-discovered transition graph over masked board
        # states (UNDO gives cheap back-edges). ``_transitions`` is the flat
        # triple list ``transition_shortest_path`` consumes; ``_edges`` is the
        # same graph as an adjacency map maintained IN STEP so
        # :meth:`_nearest_untried`'s BFS stays linear in the graph size.
        self._pending_action: int | None = None
        self._pending_key: Any | None = None
        self._transitions: list[tuple[Any, int, Any]] = []
        self._edges: dict[Any, dict[int, Any]] = {}
        self._tried_from: dict[Any, set[int]] = {}

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._on_restart()
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._reset_for_new_env()
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._on_level_up(levels)

        self._step += 1
        masked = _mask_hud(grid)
        if self._start_grid is None:
            self._start_grid = masked

        simple_ids, _action6_ok = available_action_ids(latest_frame)
        # ACTION6 (click-select) is skipped: ACTION5 already cycles through
        # every selectable piece, and click-coordinate exploration is an
        # unbounded 64x64 space that would swamp the fallback graph. ACTION7
        # (undo) is offered for probe back-edges but read separately, since
        # base.available_action_ids only surfaces ids 1-5.
        move_ids = [a for a in simple_ids if a in (1, 2, 3, 4, 5)]
        act_ids = sorted(set(move_ids) | ({7} if _undo_available(latest_frame) else set()))
        if not act_ids:
            return simple_action(simple_ids[0]) if simple_ids else reset_action()

        if self._phase == "probe":
            return self._probe_step(masked, act_ids)
        if self._phase == "plan":
            return self._plan_step(masked, act_ids)
        return self._graph_step(masked, act_ids)

    # ── level / restart bookkeeping ─────────────────────────────────────

    def _on_level_up(self, levels: int) -> None:
        """A new level is a new board: re-probe and re-plan from scratch, and
        drop the fallback graph (its states belonged to the old board)."""
        self._levels_seen = levels
        self._phase = "probe"
        self._start_grid = None
        self._observations = []
        self._probe_queue = []
        self._probe_ready = False
        self._pending_probe_action = None
        self._pending_probe_before = None
        self._plan_queue = []
        self._pending_action = None
        self._pending_key = None
        self._transitions = []
        self._edges = {}
        self._tried_from = {}

    def _on_restart(self) -> None:
        """GAME_OVER reset the current attempt back to the level start. Drop
        the in-flight pending actions; if reflection probing/planning was
        still under way (board is back at start), restart that pipeline so it
        re-measures cleanly. The fallback graph is kept — its states are the
        same board."""
        self._pending_action = None
        self._pending_key = None
        self._pending_probe_action = None
        self._pending_probe_before = None
        if self._phase in ("probe", "plan"):
            self._phase = "probe"
            self._start_grid = None
            self._observations = []
            self._probe_queue = []
            self._probe_ready = False
            self._plan_queue = []

    def _reset_for_new_env(self) -> None:
        self._levels_seen = -1
        self._on_level_up(-1)

    # ── phase 1: probe (measure reflection transitions) ─────────────────

    def _probe_step(self, masked: Grid, act_ids: list[int]) -> GameAction:
        # Record the result of the previous probe MOVE (undo steps are not
        # recorded -- they only restore the start board for the next probe).
        if self._pending_probe_action is not None:
            if self._pending_probe_action in (1, 2, 3, 4) and self._pending_probe_before is not None:
                self._observations.append(
                    {
                        "before": self._pending_probe_before,
                        "after": masked,
                        "label": self._pending_probe_action,
                    }
                )
            self._pending_probe_action = None
            self._pending_probe_before = None

        if not self._probe_ready:
            can_undo = 7 in act_ids
            queue: list[int] = []
            for a in (1, 2, 3, 4):
                if a in act_ids:
                    queue.append(a)
                    if can_undo:
                        queue.append(7)
            self._probe_queue = queue
            self._probe_ready = True

        if self._probe_queue:
            a = self._probe_queue.pop(0)
            if a in (1, 2, 3, 4):
                # ``masked`` is the level-start board here (restored by the
                # preceding undo), so every observation's ``before`` is the
                # same reference the plan is computed from.
                self._pending_probe_action = a
                self._pending_probe_before = masked
            return simple_action(a)

        self._build_plan()
        if self._phase == "plan":
            return self._plan_step(masked, act_ids)
        return self._graph_step(masked, act_ids)

    def _build_plan(self) -> None:
        """Learn the reflection model from the probes and, if it yields a
        covering plan, arm the plan queue; otherwise fall through to graph."""
        start = self._start_grid
        if start is None:
            self._phase = "graph"
            return
        bg = most_common_color(start)
        model = learn_reflection_operators(self._observations, background=bg)
        axes = model["axes"]
        piece_cells = model["piece_cells"]
        delta_map = model["delta_map"]
        if not axes or not piece_cells or not delta_map:
            self._phase = "graph"
            return
        moving = model["moving_colors"] | model["piece_colors"]
        target = _detect_goal(start, bg, moving)
        if not target:
            self._phase = "graph"
            return
        bounds = (len(start), len(start[0]))
        plan = plan_reflection_coverage(piece_cells, axes, target, delta_map, bounds)
        if plan:
            self._plan_queue = [int(a) for a in plan]
            self._phase = "plan"
        else:
            self._phase = "graph"

    # ── phase 2: execute the covering plan ───────────────────────────────

    def _plan_step(self, masked: Grid, act_ids: list[int]) -> GameAction:
        if self._plan_queue:
            return simple_action(self._plan_queue.pop(0))
        # Plan spent without WIN -- hand off to frontier exploration for the
        # remaining budget (e.g. the model's coverage prediction diverged, or
        # the piece was blocked before reaching the planned anchor).
        self._phase = "graph"
        return self._graph_step(masked, act_ids)

    # ── phase 3: generic transition-graph frontier fallback ─────────────

    def _graph_step(self, masked: Grid, act_ids: list[int]) -> GameAction:
        cur_key = canonical_key(masked, mode="exact")
        self._observe_result(cur_key)
        action = self._decide(cur_key, act_ids)
        self._pending_action = action
        self._pending_key = cur_key
        return simple_action(action)

    def _observe_result(self, cur_key: Any) -> None:
        action = self._pending_action
        prev_key = self._pending_key
        self._pending_action = None
        self._pending_key = None
        if action is None or prev_key is None:
            return
        self._transitions.append((prev_key, action, cur_key))
        self._edges.setdefault(prev_key, {})[action] = cur_key
        self._tried_from.setdefault(prev_key, set()).add(action)

    def _decide(self, cur_key: Any, act_ids: list[int]) -> int:
        tried = self._tried_from.get(cur_key, set())
        untried = [a for a in act_ids if a not in tried]
        if untried:
            return untried[0]

        target = self._nearest_untried(cur_key, act_ids)
        if target is not None and target != cur_key:
            path = transition_shortest_path(self._transitions, cur_key, target)
            if path:
                return int(path[0])

        # Fully explored under current knowledge (or the target is
        # unroutable) -- take any action rather than stall, matching every
        # other adapter's exhausted fallback.
        return act_ids[0]

    def _nearest_untried(self, start_key: Any, act_ids: list[int]) -> Any | None:
        """BFS over the KNOWN transition graph from ``start_key``; return the
        nearest state (including ``start_key`` itself) that still has an
        action in ``act_ids`` not yet recorded in ``_tried_from``, or None if
        every reachable state has been fully explored.

        Hand-rolled rather than :func:`admorphiq.kernels.reachable_frontier`
        for the same reason ``admorphiq.adapters25.tu93`` gives: that
        kernel's universe is already-OBSERVED edges only, so it can surface a
        known edge that is untried but NOT a state's never-attempted action,
        which is what frontier exploration actually needs."""
        visited = {start_key}
        queue: deque[Any] = deque([start_key])
        while queue:
            state = queue.popleft()
            tried_here = self._tried_from.get(state, set())
            if any(a not in tried_here for a in act_ids):
                return state
            for _action, nxt in self._edges.get(state, {}).items():
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        return None
