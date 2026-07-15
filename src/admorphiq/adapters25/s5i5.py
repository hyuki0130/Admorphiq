"""script25 quarantined adapter: S5I5 (slider / goal-to-target family).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/S5I5.md`` (read for reference, not imported) records S5I5 as
a brittle 1/8 solve that read two sprite tags — ``myzmclysbl`` (rotate buttons)
and ``zylvdxoiuq`` (goals) — with every generic attempt at 0/8. Reading the game
source (dev-time only; this adapter acts frame-only) plus live probes
(``scratchpad`` traces, offline) decode the mechanic and its frame equivalents:

**Mechanic (measured — roles/hypothesis declared HERE, not in any kernel)**:
S5I5 is a slider puzzle. ``available_actions`` = ``[6]`` — ONLY ACTION6 (click).

- Each puzzle has movable GOAL markers and fixed TARGET markers, all drawn in
  the same distinct colour (measured colour 13). A goal is a small blob (size
  ~1); a target is a larger blob (size ~4). The level WINS when every target
  has a goal exactly on it (source ``vodebmynqs``: target.x==goal.x and
  target.y==goal.y for all targets).
- Each goal is attached to a resizable SLIDER whose track is a rectangular
  frame (measured colour 2). Clicking the FAR half of a track extends the
  slider, moving its goal +one unit (3 px) along the track's long axis; clicking
  the NEAR half shrinks it, moving the goal −one unit. Clicking a rotate BUTTON
  rotates the slider 90°, switching which axis the goal moves along.
- A move that would make two sliders collide is REVERTED (source
  ``ulzimrggno``), so not every click lands.

**This adapter's approach — online effect-learning greedy** (no rotation model
yet; level 1 needs none): lock the target blobs once; track the goal blobs;
generate candidate click points at the edge-midpoints of each track frame;
MEASURE each candidate's effect by clicking it and recording which goal moved,
by how much, and which target that goal serves; then repeatedly click the
measured candidate whose delta reduces its served goal's residual to its target.
Composes ``kernels.find_regions`` for all segmentation.

**Measured coverage**: on the local env (``s5i5-18d95033``) this clears **1/8**
(``game_score`` 0.028), MATCHING the brittle baseline (1/8) but WITHOUT any
sprite-tag read — the first frame-only clear of this game, proving the slider
mechanic is solvable from pixels. Level 1: two goals already axis-aligned with
their targets (7 far-half clicks on the H-track, 6 on the V-track); the greedy
learns each track's effect and drives each goal home.

**Level 2 — two reopens landed, a third structure BANKED (stop rule)**:
  1. **Movement-based goal/target discrimination — DONE.** L2's two colour-13
     blobs both start size 5 (a goal coincident with its target), so the size
     split saw only targets. Fix: defer locking until a small goal blob is
     visible; before that, probe a track click to SPLIT the merged blob — the
     piece that moves is the goal (revealed as size 1), the static one is the
     target (size 4). Verified: goal detected, target locked, goal driven.
  2. **Directional controls — DONE.** The compact colour-4 boxes are not
     rotate buttons but DIRECTIONAL slider controls (measured: one moves the
     goal +col, another −row, etc.). Added them as candidates so the
     effect-learning greedy measures and uses them. Plus **collision-revert
     handling** (``_dead``): a click that produces no goal movement (a maxed
     slider / reverted collision) is skipped until any goal moves again.
  3. **BANKED third structure — the goal cannot REACH its target by
     translation.** Measured: the goal's column control maxes/collides at col
     43 while its target sits at col 52 (9 px unreachable), and the row control
     can shave the row gap but never the column gap, so the greedy oscillates
     without converging. Reaching the target needs TRUE rotation (swap the
     slider's axis to extend past the block) — a genuinely separate control
     from the directional colour-4 boxes, not yet frame-located. Per the
     round's stop rule this is banked rather than pursued further. L1 (1/8)
     unaffected; no hardcoded coordinates/sequences added; the machinery
     (movement-split, directional-control candidates, dead-click reverts) is
     the durable value.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments the colour-13 goal/target
    blobs and the colour-2 slider tracks.
"""

from __future__ import annotations

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
from admorphiq.kernels import find_regions

GAME_ID = "s5i5"

Cell = tuple[int, int]
Region = dict[str, Any]

_GIVEUP_DEFAULT = 4000
_MARKER_COLOR = 13
_TRACK_COLOR = 2
# Rotate buttons render as compact colour-4 boxes (measured ~5x5, size ~18) —
# distinct from the full-width colour-4 HUD strip on the bottom row.
_ROTATE_COLOR = 4
_ROTATE_MIN_SIZE = 8
_ROTATE_MAX_SIZE = 32
# A colour-13 blob at or below this size is a movable goal; larger is a target.
_GOAL_MAX_SIZE = 2
# A goal within this pixel distance of its target counts as placed (one unit is
# 3 px; being inside the target blob satisfies the exact-match win).
_ON_TARGET = 2


def _centroid(region: Region) -> Cell:
    r, c = region["centroid"]
    return (round(r), round(c))


def _dist(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class Adapter(GameAdapter):
    """Online effect-learning slider greedy composed from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        # Target blob centroids, locked once per level (fixed all level).
        self._targets: list[Cell] = []
        self._targets_locked = False
        # Candidate click points (row, col) still to be effect-probed, and the
        # measured effect of each probed point: which target its goal serves and
        # the (dr, dc) the goal moved.
        self._candidates: list[Cell] = []
        self._probe_idx = 0
        self._effect: dict[Cell, tuple[int, Cell]] = {}
        # Clicks that produced NO goal movement at the current configuration — a
        # slider maxed at its extent, or a collision-reverted move. Skipped so
        # the greedy abandons an exhausted control and probes another axis;
        # cleared whenever any goal actually moves (the state changed, so a
        # previously-blocked control may now be free).
        self._dead: set[Cell] = set()

        self._pending_point: Cell | None = None
        self._pending_goals: list[Cell] = []

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._pending_point = None
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._pending_point = None
            self._levels_seen = -1
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._on_level_up(levels, grid)

        self._step += 1
        bg = most_common_color(grid)
        # 8-connectivity: the target markers are diamonds of DIAGONALLY-adjacent
        # pixels, which 4-connectivity would shatter into size-1 fragments
        # (making every target look like a goal). 8-connectivity keeps each
        # diamond one blob so the goal/target size split holds.
        regions = find_regions(grid, background=bg, connectivity=8)
        goals = self._goals(regions)
        self._observe(goals)

        point = self._decide(grid, regions, goals)
        return click_action(x=point[1], y=point[0])

    # ── bookkeeping ─────────────────────────────────────────────────────

    def _on_level_up(self, levels: int, grid: tuple[tuple[int, ...], ...]) -> None:
        self._levels_seen = levels
        self._targets = []
        self._targets_locked = False
        self._candidates = []
        self._probe_idx = 0
        self._effect = {}
        self._dead = set()
        self._pending_point = None
        self._pending_goals = []

    def _lock(self, regions: list[Region], grid: tuple[tuple[int, ...], ...]) -> None:
        markers = [r for r in regions if r["color"] == _MARKER_COLOR]
        self._targets = [_centroid(r) for r in markers if r["size"] > _GOAL_MAX_SIZE]
        # Candidates = track edge-midpoints PLUS the compact colour-4 control
        # boxes. Measured (reopen #2): those boxes are the DIRECTIONAL slider
        # controls — one moves the goal +col, another -row, etc. — so a goal
        # that can only close one axis via the track edges reaches the other
        # axis through them. Which control moves which way is MEASURED by the
        # effect-learning greedy, never assumed.
        self._candidates = self._make_candidates(regions) + self._control_buttons(regions, grid)
        self._targets_locked = True

    def _control_buttons(self, regions: list[Region], grid: tuple[tuple[int, ...], ...]) -> list[Cell]:
        """Centroids of the compact colour-4 control boxes — small, roughly
        square regions (excludes the full-width colour-4 HUD strip). Each is a
        directional slider control whose actual effect is measured live."""
        h = len(grid)
        out: list[Cell] = []
        for reg in regions:
            if reg["color"] != _ROTATE_COLOR:
                continue
            if not (_ROTATE_MIN_SIZE <= reg["size"] <= _ROTATE_MAX_SIZE):
                continue
            r0, c0, r1, c1 = reg["bbox"]
            bw, bh = c1 - c0 + 1, r1 - r0 + 1
            if abs(bw - bh) > 3 or r0 <= 0 or r1 >= h - 1:
                continue
            out.append(_centroid(reg))
        return out

    def _make_candidates(self, regions: list[Region]) -> list[Cell]:
        """Edge-midpoint click points of every slider-track frame (colour 2).
        The far/near halves of a track drive its goal ±1 unit along the track's
        long axis; all four edge midpoints cover both orientations, and which
        one actually moves a goal is MEASURED, never assumed."""
        points: list[Cell] = []
        for reg in regions:
            if reg["color"] != _TRACK_COLOR:
                continue
            r0, c0, r1, c1 = reg["bbox"]
            mr, mc = (r0 + r1) // 2, (c0 + c1) // 2
            points.extend([(mr, c1), (mr, c0), (r1, mc), (r0, mc)])
        return points

    # ── perception ──────────────────────────────────────────────────────

    def _goals(self, regions: list[Region]) -> list[Cell]:
        return [_centroid(r) for r in regions if r["color"] == _MARKER_COLOR and r["size"] <= _GOAL_MAX_SIZE]

    def _observe(self, goals: list[Cell]) -> None:
        """Record the effect of the pending probe click: which goal moved (vs
        the pre-click snapshot), its delta, and which locked target it serves
        (its nearest). Stored keyed on the clicked point for the planner."""
        point = self._pending_point
        before = self._pending_goals
        self._pending_point = None
        self._pending_goals = []
        if point is None or not before or not goals:
            return
        moved = self._moved_goal(before, goals)
        if moved is None:
            # No goal moved: this control is exhausted/blocked at the current
            # configuration (a maxed slider or a collision-reverted move).
            self._dead.add(point)
            return
        # A goal moved: the configuration changed, so any control that was
        # blocked before may now be free again.
        self._dead.clear()
        old, new = moved
        delta = (new[0] - old[0], new[1] - old[1])
        if delta == (0, 0):
            return
        served = self._nearest_target(new)
        if served is not None:
            self._effect[point] = (served, delta)

    def _moved_goal(self, before: list[Cell], after: list[Cell]) -> tuple[Cell, Cell] | None:
        best: tuple[Cell, Cell] | None = None
        best_shift = 0
        for old in before:
            new = min(after, key=lambda a: _dist(a, old))
            shift = _dist(new, old)
            if shift > best_shift:
                best_shift = shift
                best = (old, new)
        return best if best_shift > 0 else None

    def _nearest_target(self, point: Cell) -> int | None:
        if not self._targets:
            return None
        return min(range(len(self._targets)), key=lambda i: _dist(self._targets[i], point))

    # ── planning ────────────────────────────────────────────────────────

    def _decide(self, grid: tuple[tuple[int, ...], ...], regions: list[Region], goals: list[Cell]) -> Cell:
        if not self._candidates:
            self._candidates = self._make_candidates(regions)
        if not self._targets_locked:
            if goals:
                # A small (movable) goal blob is now visible: lock the targets
                # from the CURRENT state and restart effect-probing with the
                # goal trackable.
                self._lock(regions, grid)
                self._probe_idx = 0
            else:
                # No small goal blob yet — on deeper levels a goal starts
                # COINCIDENT with its target (a merged size-5 blob), so the
                # size split sees only targets. Probe a track to split the
                # merged blob: the piece that MOVES is the goal (movement-based
                # discrimination), revealed as a small blob next frame.
                return self._commit(self._next_probe(), goals)

        # A measured click that strictly reduces its served goal's residual.
        improving = self._best_improving(goals)
        if improving is not None:
            return self._commit(improving, goals)

        # Otherwise probe the next un-measured candidate to learn its effect.
        if self._probe_idx < len(self._candidates):
            point = self._candidates[self._probe_idx]
            self._probe_idx += 1
            return self._commit(point, goals)

        # Everything measured and nothing improves: either solved, or a
        # collision-reverted move earlier is now free. Re-probe candidates.
        if self._candidates:
            point = self._candidates[self._step % len(self._candidates)]
            return self._commit(point, goals)
        return self._commit((len(grid) // 2, len(grid[0]) // 2), goals)

    def _best_improving(self, goals: list[Cell]) -> Cell | None:
        best_point: Cell | None = None
        best_gain = 0
        for point, (target_i, delta) in self._effect.items():
            if point in self._dead:
                continue
            target = self._targets[target_i]
            goal = self._goal_for_target(goals, target)
            if goal is None:
                continue
            before = _dist(goal, target)
            after = _dist((goal[0] + delta[0], goal[1] + delta[1]), target)
            gain = before - after
            if gain > best_gain:
                best_gain = gain
                best_point = point
        return best_point

    def _goal_for_target(self, goals: list[Cell], target: Cell) -> Cell | None:
        """The still-unplaced goal serving ``target`` — the nearest goal blob
        that has not yet reached it."""
        candidates = [g for g in goals if _dist(g, target) > _ON_TARGET]
        if not candidates:
            return None
        return min(candidates, key=lambda g: _dist(g, target))

    def _next_probe(self) -> Cell:
        """The next un-probed candidate click (then cycles) — used to bootstrap
        movement-based goal discovery before any goal is size-visible."""
        if not self._candidates:
            return (0, 0)
        if self._probe_idx < len(self._candidates):
            point = self._candidates[self._probe_idx]
            self._probe_idx += 1
            return point
        return self._candidates[self._step % len(self._candidates)]

    def _commit(self, point: Cell, goals: list[Cell]) -> Cell:
        self._pending_point = point
        self._pending_goals = list(goals)
        return point
