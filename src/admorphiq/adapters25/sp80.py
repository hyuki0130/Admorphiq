"""script25 quarantined adapter: SP80 (water-routing / spill-coverage puzzle).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/SP80.md`` (read for reference, not imported) records
SP80's mechanic, read offline from the game source (dev-time only; the
adapter itself reads only frames at runtime):

**Water-routing coverage — two phases**:

- **CHANGE phase**: movable BLOCK/DEFLECTOR pieces (the selected one is
  recoloured), a fixed WATER SOURCE near the top, and two or more TARGET
  regions. ACTION1-4 move the selected piece one cell; ACTION5 COMMITS the
  layout → spill.
- **SPILL phase**: water falls from the source, flowing AROUND the placed
  pieces (spreading along a piece's leading face, resuming its fall past the
  edges). A target is satisfied only when water reaches its INTERIOR. The
  level WINS when every target is satisfied; otherwise the spill fails, the
  board resets to change, and a spill-attempt counter increments — only 4
  failed spills are allowed before GAME_OVER.

**This build — learn the flow, then plan the layout**: the adapter composes
the fluid-flow motion kernels (:func:`admorphiq.kernels.learn_flow_operators`
/ :func:`admorphiq.kernels.simulate_flow` /
:func:`admorphiq.kernels.plan_flow_coverage`, the fluid analogue of the
``learn_point_operators``/``plan_overwrites`` and reflection pairs the R56
codex verdict proposed, ``docs/r56_codex_toolbase_verdict_20260715.md``):

  1. **Learn** — commit ONE sacrificial spill. The spill exposes its whole
     animation as the observation's successive frame LAYERS (one per tick),
     so a single commit reveals the entire trajectory;
     :func:`learn_flow_operators` recovers the fall direction and the source
     emit cells from it. (A failed spill returns to the change phase in ~1
     tick, so this costs ~2 actions and 1 of the 4 spill attempts.)
  2. **Probe** — measure the selected piece's per-action displacement (the
     cluster that translates under an ACTION1-4 probe is the movable piece).
  3. **Plan** — the goal regions are the static clusters downstream of the
     source; :func:`plan_flow_coverage` searches piece placements for one
     whose simulated flow covers every target, then the layout is executed
     and committed for the winning spill.

**Fallback**: when the flow model can't be learned, no movable piece is
detected, or no covering placement exists (multi-piece levels needing
targeted ACTION6 selection, angled deflectors, etc.), the adapter falls back
to the generic transition-graph frontier exploration the previous build used,
so deeper levels never regress below that baseline.

**Why namespace-safe**: the adapter assigns roles (which cluster is the
movable piece, which are the targets, which is the source) and declares the
mechanic hypothesis (fluid coverage), but every pixel algorithm and every
search lives in ``admorphiq.kernels`` — no hardcoded coordinates, colours,
source positions, or bespoke physics here. The fall direction, source cells,
piece footprint, per-action displacements, and target regions are all learned
from the live frames.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.learn_flow_operators` learns the flow model from
    the sacrificial spill's animation layers.
  - :func:`admorphiq.kernels.plan_flow_coverage` /
    :func:`admorphiq.kernels.simulate_flow` plan the covering placement.
  - :func:`admorphiq.kernels.find_regions` segments the board (HUD masking,
    role detection).
  - :func:`admorphiq.kernels.canonical_key` /
    :func:`admorphiq.kernels.transition_shortest_path` drive the graph
    fallback.
"""

from __future__ import annotations

from collections import deque
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
    canonical_key,
    find_regions,
    learn_flow_operators,
    plan_flow_coverage,
    plan_flow_coverage_multi,
    transition_shortest_path,
)

GAME_ID = "sp80"

Cell = tuple[int, int]
Region = dict[str, Any]
Grid = tuple[tuple[int, ...], ...]

_GIVEUP_DEFAULT = 4000
_HUD_SPAN_FRACTION = 0.85
_HUD_THICKNESS_FRACTION = 0.08


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    """A thin strip spanning most of one axis, OR pinned to a frame edge.

    SP80's top rotation strip and bottom step-counter band are edge-pinned;
    the counter band shares its colour with the in-play hazard, so only the
    EDGE-pinned test distinguishes the HUD band from a hazard inside the play
    area."""
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
    background colour, so a canonical key reflects only the play area."""
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


def _cells_of_color(grid: Grid, color: int) -> frozenset[Cell]:
    return frozenset(
        (r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v == color
    )


def _centroid(cells: frozenset[Cell]) -> tuple[float, float]:
    n = len(cells)
    return (sum(r for r, _c in cells) / n, sum(c for _r, c in cells) / n)


def _detect_translated_color(before: Grid, after: Grid, background: int) -> tuple[int | None, Cell]:
    """The colour whose cells RIGIDLY translated between two frames.

    Returns ``(color, (dr, dc))`` for the largest same-count colour cluster
    whose ``after`` cells are exactly its ``before`` cells shifted by a
    nonzero ``(dr, dc)`` — the movable piece under a move probe — or
    ``(None, (0, 0))`` when nothing translated rigidly."""
    best: tuple[int, Cell, int] | None = None
    colors = {v for row in before for v in row if v != background}
    for color in colors:
        bc = _cells_of_color(before, color)
        ac = _cells_of_color(after, color)
        if not bc or len(bc) != len(ac):
            continue
        bcen = _centroid(bc)
        acen = _centroid(ac)
        shift = (round(acen[0] - bcen[0]), round(acen[1] - bcen[1]))
        if shift == (0, 0):
            continue
        if frozenset((r + shift[0], c + shift[1]) for r, c in bc) == ac:
            if best is None or len(bc) > best[2]:
                best = (color, shift, len(bc))
    if best is not None:
        return best[0], best[1]
    return None, (0, 0)


class Adapter(GameAdapter):
    """Learn SP80's flow from a sacrificial spill, then plan a target-covering
    piece layout; fall back to generic transition-graph frontier exploration
    when the flow model is unavailable. Composed from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True
        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        # phase: "learn" (one sacrificial spill to learn the flow model),
        # "probe" (measure the movable piece's per-action deltas), "plan"
        # (execute a covering layout + commit), "graph" (fallback).
        self._phase = "learn"
        self._learned = False
        self._spill_committed = False
        self._flow_model: dict[str, Any] | None = None
        self._movable_color: int | None = None
        self._delta_map: dict[int, Cell] = {}
        self._probe_queue: list[int] = []
        self._probe_ready = False
        self._pending_probe: tuple[int, Grid] | None = None
        self._plan_queue: list[int] = []

        # multi-piece flow state ("classify" probes each candidate to split the
        # movable deflector pieces from the static targets by SELECTION response;
        # "execute" runs the joint select-and-move plan then commits the spill).
        # Only reached for levels whose single-piece plan cannot cover — L0 keeps
        # the single-piece path untouched.
        self._piece_colors: set[int] = set()
        self._classify_queue: list[tuple[Cell, int]] = []
        self._classify_pending: tuple[Cell, int] | None = None
        self._exec_plan: list[tuple[int, int]] = []
        self._exec_pieces: list[frozenset[Cell]] = []
        self._exec_pos = 0
        self._exec_pending_move: int | None = None
        self._committed = False
        self._clean_grid: Grid = ()
        self._restore_steps = 0
        self._m_source = frozenset()
        self._m_fall = (0, 0)
        self._m_flow_color = None

        # graph-fallback state.
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

        simple_ids, _action6_ok = available_action_ids(latest_frame)
        act_ids = sorted(a for a in simple_ids if a in (1, 2, 3, 4, 5))
        if not act_ids:
            return simple_action(simple_ids[0]) if simple_ids else reset_action()

        if self._phase == "learn":
            return self._learn_step(latest_frame, grid, act_ids)
        if self._phase == "probe":
            return self._probe_step(grid, act_ids)
        if self._phase == "plan":
            return self._plan_step(grid, act_ids)
        if self._phase == "restore":
            return self._restore_step(grid, act_ids)
        if self._phase == "classify":
            return self._classify_step(grid, act_ids)
        if self._phase == "execute":
            return self._execute_step(grid, act_ids)
        return self._graph_step(grid, act_ids)

    # ── level / restart bookkeeping ─────────────────────────────────────

    def _on_level_up(self, levels: int) -> None:
        self._levels_seen = levels
        self._phase = "learn"
        self._learned = False
        self._spill_committed = False
        self._flow_model = None
        self._movable_color = None
        self._delta_map = {}
        self._probe_queue = []
        self._probe_ready = False
        self._pending_probe = None
        self._plan_queue = []
        self._reset_multi()
        self._pending_action = None
        self._pending_key = None
        self._transitions = []
        self._edges = {}
        self._tried_from = {}

    def _reset_multi(self) -> None:
        self._piece_colors = set()
        self._classify_queue = []
        self._classify_pending = None
        self._exec_plan = []
        self._exec_pieces = []
        self._exec_pos = 0
        self._exec_pending_move = None
        self._committed = False
        self._clean_grid = ()
        self._restore_steps = 0
        self._m_source: frozenset[Cell] = frozenset()
        self._m_fall: Cell = (0, 0)
        self._m_flow_color: int | None = None

    def _on_restart(self) -> None:
        """GAME_OVER reset the attempt to the level start (spill counter reset
        too). Restart the flow pipeline from scratch; keep the fallback graph
        (same board)."""
        self._pending_action = None
        self._pending_key = None
        self._pending_probe = None
        if self._phase in ("learn", "probe", "plan", "classify", "execute"):
            self._phase = "learn"
            self._learned = False
            self._spill_committed = False
            self._flow_model = None
            self._movable_color = None
            self._delta_map = {}
            self._probe_queue = []
            self._probe_ready = False
            self._plan_queue = []
            self._reset_multi()

    def _reset_for_new_env(self) -> None:
        self._levels_seen = -1
        self._on_level_up(-1)

    # ── phase 1: learn the flow model from a sacrificial spill ──────────

    def _learn_step(self, latest_frame: Any, grid: Grid, act_ids: list[int]) -> GameAction:
        layers = getattr(latest_frame, "frame", None) or []
        if len(layers) > 1:
            # A spill animation exposes every tick as one layer. Only learn from
            # the spill WE committed in the change phase — on entry to a deeper
            # level the previous level's winning-spill animation is still playing
            # (a stale, opposite-direction flow), so learning from it would fit
            # the wrong fall direction. Wait for our own sacrificial spill.
            if self._spill_committed and not self._learned:
                model = learn_flow_operators(layers, background=most_common_color(grid))
                if model["fall_dir"] != (0, 0) and model["source_cells"]:
                    self._flow_model = model
                    self._learned = True
                else:
                    self._phase = "graph"
                    return self._graph_step(grid, act_ids)
            return simple_action(1 if 1 in act_ids else act_ids[0])
        # Single-layer (change) phase.
        if self._learned:
            # Snapshot the clean, post-sacrificial-spill piece arrangement before
            # the probe displaces the auto-selected piece — the multi-piece path
            # restores to this exact board so no re-arranging spill is needed.
            self._clean_grid = grid
            self._phase = "probe"
            return self._probe_step(grid, act_ids)
        if not self._spill_committed and 5 in act_ids:
            self._spill_committed = True
            return simple_action(5)  # commit the sacrificial spill
        if self._spill_committed:
            # Committed but the spill resolved without a learnable model.
            self._phase = "graph"
            return self._graph_step(grid, act_ids)
        self._phase = "graph"
        return self._graph_step(grid, act_ids)

    # ── phase 2: probe the movable piece's per-action deltas ────────────

    def _probe_step(self, grid: Grid, act_ids: list[int]) -> GameAction:
        if self._pending_probe is not None:
            action, before = self._pending_probe
            color, shift = _detect_translated_color(before, grid, most_common_color(grid))
            if color is not None:
                self._movable_color = color
                if shift != (0, 0):
                    self._delta_map[action] = shift
            self._pending_probe = None

        if not self._probe_ready:
            self._probe_queue = [a for a in (1, 2, 3, 4) if a in act_ids]
            self._probe_ready = True

        if self._probe_queue:
            a = self._probe_queue.pop(0)
            self._pending_probe = (a, grid)
            return simple_action(a)

        self._build_plan(grid)
        if self._phase == "plan":
            return self._plan_step(grid, act_ids)
        if self._phase == "restore":
            return self._restore_step(grid, act_ids)
        return self._graph_step(grid, act_ids)

    def _build_plan(self, grid: Grid) -> None:
        if self._movable_color is None or not self._delta_map or self._flow_model is None:
            self._phase = "graph"
            return
        bg = most_common_color(grid)
        movable = _cells_of_color(grid, self._movable_color)
        source = self._flow_model["source_cells"]
        fall = self._flow_model["fall_dir"]
        flow_color = self._flow_model["flow_color"]
        targets = self._detect_targets(grid, bg, {self._movable_color, flow_color}, _centroid(source), fall)
        if not movable or not targets:
            self._phase = "graph"
            return
        bounds = (len(grid), len(grid[0]))
        plan = plan_flow_coverage(movable, self._delta_map, frozenset(), source, targets, fall, bounds)
        if plan is None:
            # A single deflector cannot cover these targets. Levels past L0 place
            # SEVERAL movable pieces (each selected by an ACTION6 click); switch
            # to the multi-piece path. The probe just displaced the auto-selected
            # piece, so first walk it back to its clean pre-probe position (a spill
            # would re-arrange every piece); classify + joint plan then run on the
            # restored clean board.
            self._m_source = source
            self._m_fall = fall
            self._m_flow_color = flow_color
            self._phase = "restore"
            return
        # Append the commit (ACTION5) that spills the planned, covering layout.
        self._plan_queue = [int(a) for a in plan] + [5]
        self._phase = "plan"

    def _detect_targets(
        self,
        grid: Grid,
        background: int,
        exclude_colors: set[int],
        source_centroid: tuple[float, float],
        fall: Cell,
    ) -> list[frozenset[Cell]]:
        """Static clusters DOWNSTREAM of the source (in the fall direction),
        excluding the movable piece and the flowing substance — the regions
        the flow must cover. Downstream-filtering drops the upstream emitter
        so it is never mistaken for a target."""
        height, width = len(grid), len(grid[0])
        out: list[frozenset[Cell]] = []
        for region in find_regions(grid, background=background):
            if _is_hud_band(region, height, width):
                continue
            if region["color"] in exclude_colors:
                continue
            cen = region["centroid"]
            downstream = (cen[0] - source_centroid[0]) * fall[0] + (cen[1] - source_centroid[1]) * fall[1]
            if downstream <= 0:
                continue
            out.append(frozenset(region["cells"]))
        return out

    # ── phase 3: execute the covering layout + commit ───────────────────

    def _plan_step(self, grid: Grid, act_ids: list[int]) -> GameAction:
        if self._plan_queue:
            return simple_action(self._plan_queue.pop(0))
        self._phase = "graph"
        return self._graph_step(grid, act_ids)

    # ── multi-piece: classify pieces vs targets, then joint select+move ──

    def _downstream_regions(
        self, grid: Grid, bg: int, src_cen: tuple[float, float], fall: Cell, exclude_colors: set[int]
    ) -> list[Region]:
        """Non-HUD regions downstream of the source (in the fall direction),
        excluding ``exclude_colors`` — the pieces and targets in the play area."""
        height, width = len(grid), len(grid[0])
        out: list[Region] = []
        for region in find_regions(grid, background=bg):
            if _is_hud_band(region, height, width):
                continue
            if region["color"] in exclude_colors:
                continue
            cen = region["centroid"]
            downstream = (cen[0] - src_cen[0]) * fall[0] + (cen[1] - src_cen[1]) * fall[1]
            if downstream <= 0:
                continue
            out.append(region)
        return out

    def _restore_step(self, grid: Grid, act_ids: list[int]) -> GameAction:
        """Walk the probe-displaced (currently-selected) piece back to its clean
        pre-probe position, then classify on the restored board. Only that one
        piece moved during the probe, so restoring it makes the board identical
        to the clean snapshot the joint plan is computed from."""
        if self._movable_color is None or not self._clean_grid:
            self._phase = "graph"
            return self._graph_step(grid, act_ids)
        self._restore_steps += 1
        target = _cells_of_color(self._clean_grid, self._movable_color)
        cur = _cells_of_color(grid, self._movable_color)
        # Restored (or a move is stuck against a wall / budget spent) — classify.
        if not target or not cur or cur == target or self._restore_steps > 16:
            self._start_classify(grid, self._m_source, self._m_fall, self._m_flow_color)
            if self._phase == "classify":
                return self._classify_step(grid, act_ids)
            return self._graph_step(grid, act_ids)
        # Step the selected piece one move toward its clean centroid.
        tcen = _centroid(target)
        ccen = _centroid(cur)
        best_action: int | None = None
        best_dist = abs(ccen[0] - tcen[0]) + abs(ccen[1] - tcen[1])
        for action, (dr, dc) in self._delta_map.items():
            if action not in act_ids:
                continue
            nd = abs(ccen[0] + dr - tcen[0]) + abs(ccen[1] + dc - tcen[1])
            if nd < best_dist:
                best_dist = nd
                best_action = action
        if best_action is None:
            # Cannot get closer (blocked or already aligned enough) — proceed.
            self._start_classify(grid, self._m_source, self._m_fall, self._m_flow_color)
            if self._phase == "classify":
                return self._classify_step(grid, act_ids)
            return self._graph_step(grid, act_ids)
        return simple_action(best_action)

    def _start_classify(self, grid: Grid, source: frozenset[Cell], fall: Cell, flow_color: int | None) -> None:
        """Queue the downstream candidate regions for ACTION6 select-probing so
        the movable pieces (which turn the selected colour on click) are split
        from the static targets (which do not). Ordered source-nearest first,
        since deflector pieces sit between the source and the far targets."""
        bg = most_common_color(grid)
        self._m_source = source
        self._m_fall = fall
        self._m_flow_color = flow_color
        src_cen = _centroid(source)
        exclude = {flow_color} if flow_color is not None else set()
        cands = self._downstream_regions(grid, bg, src_cen, fall, exclude)
        self._piece_colors = {self._movable_color} if self._movable_color is not None else set()
        ranked: list[tuple[float, Cell, int]] = []
        for region in cands:
            if region["color"] == self._movable_color:
                continue
            cen = region["centroid"]
            dist = abs(cen[0] - src_cen[0]) + abs(cen[1] - src_cen[1])
            ranked.append((dist, (round(cen[0]), round(cen[1])), region["color"]))
        ranked.sort(key=lambda t: t[0])
        self._classify_queue = [(cell, color) for _d, cell, color in ranked]
        self._classify_pending = None
        if not self._classify_queue:
            self._phase = "graph"
            return
        self._phase = "classify"

    def _classify_step(self, grid: Grid, act_ids: list[int]) -> GameAction:
        if self._classify_pending is not None:
            cell, color_before = self._classify_pending
            self._classify_pending = None
            s_cells = _cells_of_color(grid, self._movable_color) if self._movable_color is not None else frozenset()
            if s_cells:
                scen = _centroid(s_cells)
                # The probed candidate is a movable piece iff the selected
                # (movable-colour) region jumped onto the clicked cell.
                if abs(scen[0] - cell[0]) <= 2 and abs(scen[1] - cell[1]) <= 2:
                    self._piece_colors.add(color_before)
                    self._build_multi_plan(grid)
                    if self._phase == "execute":
                        return self._execute_step(grid, act_ids)
                    return self._graph_step(grid, act_ids)
        if self._classify_queue:
            cell, color = self._classify_queue.pop(0)
            self._classify_pending = (cell, color)
            return click_action(cell[1], cell[0])  # x=col, y=row
        self._phase = "graph"
        return self._graph_step(grid, act_ids)

    def _build_multi_plan(self, grid: Grid) -> None:
        bg = most_common_color(grid)
        src_cen = _centroid(self._m_source)
        exclude = {self._m_flow_color} if self._m_flow_color is not None else set()
        regs = self._downstream_regions(grid, bg, src_cen, self._m_fall, exclude)
        pieces = [frozenset(r["cells"]) for r in regs if r["color"] in self._piece_colors]
        targets = [frozenset(r["cells"]) for r in regs if r["color"] not in self._piece_colors]
        if len(pieces) < 2 or not targets:
            self._phase = "graph"
            return
        bounds = (len(grid), len(grid[0]))
        plan = plan_flow_coverage_multi(
            pieces, self._delta_map, frozenset(), self._m_source, targets, self._m_fall, bounds
        )
        if plan is None:
            self._phase = "graph"
            return
        self._exec_plan = [(int(i), int(lbl)) for i, lbl in plan]
        self._exec_pieces = list(pieces)
        self._exec_pos = 0
        self._exec_pending_move = None
        self._committed = False
        self._phase = "execute"

    def _execute_step(self, grid: Grid, act_ids: list[int]) -> GameAction:
        if self._exec_pending_move is not None:
            idx = self._exec_pending_move
            self._exec_pending_move = None
            s_cells = _cells_of_color(grid, self._movable_color) if self._movable_color is not None else frozenset()
            if s_cells:
                self._exec_pieces[idx] = s_cells
            self._exec_pos += 1
        if self._exec_pos >= len(self._exec_plan):
            if 5 in act_ids and not self._committed:
                self._committed = True
                return simple_action(5)
            self._phase = "graph"
            return self._graph_step(grid, act_ids)
        idx, action_id = self._exec_plan[self._exec_pos]
        s_cells = _cells_of_color(grid, self._movable_color) if self._movable_color is not None else frozenset()
        if s_cells and s_cells == self._exec_pieces[idx]:
            if action_id in act_ids:
                self._exec_pending_move = idx
                return simple_action(action_id)
            self._phase = "graph"
            return self._graph_step(grid, act_ids)
        cen = _centroid(self._exec_pieces[idx])
        return click_action(round(cen[1]), round(cen[0]))  # x=col, y=row

    # ── phase 4: generic transition-graph frontier fallback ─────────────

    def _graph_step(self, grid: Grid, act_ids: list[int]) -> GameAction:
        cur_key = canonical_key(_mask_hud(grid), mode="exact")
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
        return act_ids[0]

    def _nearest_untried(self, start_key: Any, act_ids: list[int]) -> Any | None:
        """BFS over the KNOWN transition graph from ``start_key``; return the
        nearest state with an action in ``act_ids`` not yet recorded in
        ``_tried_from``, or None if every reachable state is fully explored.

        Hand-rolled rather than :func:`admorphiq.kernels.reachable_frontier`
        for the same reason ``admorphiq.adapters25.tu93`` gives."""
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
