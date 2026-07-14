"""script25 quarantined adapter: FT09 (click-toggle-parity family).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/FT09.md`` + ``.wiki/wiki/concepts/gf2_toggle_stencil.md``
+ ``.wiki/wiki/lessons/gf2_lights_out_stencil_20260423.md`` (read for
reference, not imported) record FT09 as a click-only toggle-parity puzzle:
a grid of cells, each click flips a FIXED subset of cells regardless of
their current state (a linear system over GF(2)), and repeating the same
click twice restores the prior frame (self-inverse). L1 clears once the
empirical toggle stencil is measured directly; L2+ needs reading dedicated
constraint-indicator cells as the target vector, which the wiki records as
"no plan fn yet" — out of scope here.

Also documented (``.wiki/wiki/lessons/ft09_stride_button_drop_20260423.md``):
the legacy solver's default fixed-pixel-stride probe grid lands on FT09's
cell BORDERS, not centers, and finds zero responsive cells until the stride
is narrowed. This adapter sidesteps the whole stride-alignment question —
candidate cells come from :func:`admorphiq.kernels.find_regions` segmenting
the RENDERED frame directly, never from a blind fixed-pixel sweep, so there
is no grid-alignment guess to get wrong in the first place.

Mechanic hypothesis (role assignment, declared HERE, not in the kernel
layer): every non-background, non-chrome region on the frame is a
candidate clickable cell — the SAME set serves as both the toggle
VARIABLES (what can be clicked) and the toggle EQUATIONS (what can
change). For each candidate: click it once, read every candidate's own
bounding-box dominant colour to see which flipped, then click it AGAIN
(self-inverse) to undo before probing the next — this measures the
empirical stencil ``A[i][j]`` = "does clicking cell j flip cell i's
dominant colour". MEASURED on the live env (see the wiki page recording
this run): most candidate regions found this way never toggle anything
and are never toggled by anything — the solve is therefore restricted to
the OBSERVATIONALLY ACTIVE subset (a stencil row or column with at least
one live bit), a pure measurement-driven filter, not a hardcoded cell
count. Within that active subset, several target hypotheses are tried —
"every active cell converges to the majority colour", "...to the minority
colour" (the all-off / all-on duality of a binary toggle puzzle, from
observed colour frequency, never a hardcoded palette), and a single-cell
flip for each active cell in turn (the wiki's own documented target
family for this puzzle class) — and :func:`admorphiq.kernels.gf2_solve`'s
lowest-click-count (minimum Hamming weight) solution among whichever
hypotheses are solvable is queued for execution. A measured ~200-action
attempt/move-counter revives the SAME level on GAME_OVER (not a fresh
one), so the already-measured stencil is preserved and only RE-SOLVED
(free — no new clicks) rather than re-probed from scratch on every
revival. If no target hypothesis is solvable, the adapter falls back to a
responsive-first cycling probe (mirroring ``admorphiq.adapters25.lp85``)
rather than giving up.

Composition from ``admorphiq.kernels``:
  - :func:`find_regions` segments the frame into candidate cells.
  - :func:`frame_diff` flags whether a probe click did anything at all.
  - :func:`gf2_solve` computes, over the measured empirical stencil, which
    subset of cells to click to reach each declared target state.
  - :func:`learn_point_operators` (fallback phase only) prioritizes
    re-clicking candidates that showed some effect, mirroring lp85's own
    fallback exactly.

Candidates, the stencil, and the solved plan are all re-derived (and the
click cursor reset) on every genuine level-up (``levels_completed``
actually changes), since both are properties of the level's own layout,
not something carried forward across levels.
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
from admorphiq.kernels import find_regions, frame_diff, gf2_solve, learn_point_operators

GAME_ID = "ft09"

Cell = tuple[int, int]  # (row, col)
Grid = tuple[tuple[int, ...], ...]
Bbox = tuple[int, int, int, int]

# Per-level safety cap, mirroring the sibling adapters' giveup convention.
_GIVEUP_DEFAULT = 4000

# A region spanning at least this fraction of the frame's own cell count is a
# board-spanning panel / backdrop, not a discrete clickable cell. Mirrors
# admorphiq.adapters25.lp85's identical chrome-exclusion threshold.
_MAX_CANDIDATE_FRACTION = 0.15


def _region_candidates(grid: Grid) -> list[dict[str, Any]]:
    """Non-background, non-chrome candidate cell regions, in find_regions' own
    deterministic (bbox row0, bbox col0, colour) order."""
    if not grid:
        return []
    total_cells = len(grid) * len(grid[0])
    bg = most_common_color(grid)
    regions = find_regions(grid, background=bg)
    max_size = max(1, int(total_cells * _MAX_CANDIDATE_FRACTION))
    return [r for r in regions if r["size"] <= max_size]


def _cell_point(region: dict[str, Any]) -> Cell:
    r, c = region["centroid"]
    return (int(round(r)), int(round(c)))


def _cell_class(grid: Grid, bbox: Bbox) -> int:
    """The dominant colour within ``bbox`` on ``grid`` — this candidate
    cell's current 'state', read fresh from whatever is actually rendered
    there (never a stored/assumed colour)."""
    r0, c0, r1, c1 = bbox
    sub = tuple(row[c0 : c1 + 1] for row in grid[r0 : r1 + 1])
    return most_common_color(sub)


class Adapter(GameAdapter):
    """GF(2) toggle-stencil probing + solving, composed entirely from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        # Unmeasured going in (FT09 is click-only, no movement/hazard
        # mechanic per the wiki), but lp85 — also purely click-based —
        # measured GAME_OVER anyway, so this defaults on rather than
        # risking a truncated run before the first smoke measurement.
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        self._candidates: list[dict[str, Any]] = []
        self._base_classes: list[int] = []
        self._stencil: list[list[int]] = []
        self._stencil_density: float = 0.0

        self._phase = "probe"  # "probe" -> "execute" -> "fallback"
        self._probe_j = 0
        self._probe_substep = "click"  # "click" -> "unclick"
        self._solution_queue: list[Cell] = []
        self._fallback_cursor = 0

        self._responsive: set[Cell] = set()
        self._observations: list[dict[str, Any]] = []
        self._pending_click: Cell | None = None
        self._prev_grid: Grid | None = None

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._pending_click = None
            self._prev_grid = None
            self._levels_seen = -1  # forces full re-discovery on the next real frame
            return reset_action()
        if state == "GAME_OVER":
            # A measured attempt/move-counter revives the SAME level, not a
            # fresh one (levels_completed is unchanged) -- so the expensive
            # stencil measurement stays valid and must NOT be re-probed from
            # scratch on every revival. Mid-probe interruption is the one
            # case where partial rows are unreliable, so only that case
            # forces a clean restart; once the stencil is fully measured
            # (phase is "execute"/"fallback"), _resume_after_revival() just
            # re-solves from the cached measurement (free -- no new clicks)
            # and keeps going.
            self._pending_click = None
            self._prev_grid = None
            if self._phase == "probe":
                self._levels_seen = -1
            else:
                self._resume_after_revival()
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._on_level_up(levels, grid)

        self._step += 1
        self._observe_pending(grid)

        target = self._next_target(grid)
        self._prev_grid = grid
        self._pending_click = target
        row, col = target
        return click_action(x=col, y=row)

    # ── level bookkeeping ───────────────────────────────────────────────

    def _on_level_up(self, levels: int, grid: Grid) -> None:
        self._levels_seen = levels
        self._pending_click = None
        self._prev_grid = None

        self._candidates = _region_candidates(grid)
        self._base_classes = [_cell_class(grid, c["bbox"]) for c in self._candidates]
        n = len(self._candidates)
        self._stencil = [[0] * n for _ in range(n)]
        self._stencil_density = 0.0

        self._phase = "probe" if self._candidates else "fallback"
        self._probe_j = 0
        self._probe_substep = "click"
        self._solution_queue = []
        self._fallback_cursor = 0

        self._responsive = set()
        self._observations = []

    # ── measurement: fold the result of whatever we clicked last call ───

    def _observe_pending(self, grid: Grid) -> None:
        point = self._pending_click
        before = self._prev_grid
        self._pending_click = None
        if point is None or before is None:
            return
        diff = frame_diff(before, grid)
        if diff["count"] > 0:
            self._responsive.add(point)
        self._observations.append({"point": point, "before": before, "after": grid})

        if self._phase != "probe" or not self._candidates:
            return
        if self._probe_substep == "click":
            classes_after = [_cell_class(grid, c["bbox"]) for c in self._candidates]
            for i, cls in enumerate(classes_after):
                self._stencil[i][self._probe_j] = 1 if cls != self._base_classes[i] else 0
            self._probe_substep = "unclick"
        else:
            self._probe_substep = "click"
            self._probe_j += 1
            if self._probe_j >= len(self._candidates):
                self._finish_probe()

    def _finish_probe(self) -> None:
        n = len(self._candidates)
        total_bits = sum(sum(row) for row in self._stencil)
        self._stencil_density = total_bits / (n * n) if n else 0.0
        self._solve_from_measured_stencil()
        self._phase = "execute"

    def _resume_after_revival(self) -> None:
        """Re-solve from the ALREADY-measured stencil after a same-level
        GAME_OVER revival — free (no new clicks), and necessary because any
        clicks executed toward the previous attempt's solution are erased
        by the env's own reset, so a fresh full solution must be re-queued
        from scratch rather than resuming a partially-consumed queue."""
        self._solve_from_measured_stencil()
        self._phase = "execute"

    def _solve_from_measured_stencil(self) -> None:
        """Solve the GF(2) system restricted to OBSERVATIONALLY ACTIVE
        candidates only — a candidate whose stencil row AND column are both
        entirely zero can never change and never affects anything else, so
        demanding it "flip" in the target vector would make an otherwise-
        solvable system spuriously inconsistent. This is a pure
        measurement-driven filter (which cells are active is read from the
        stencil itself), never a hardcoded assumption about which cells
        matter."""
        n = len(self._candidates)
        active = [
            i
            for i in range(n)
            if any(self._stencil[i]) or any(self._stencil[r][i] for r in range(n))
        ]
        self._solution_queue = []
        if not active:
            return

        active_classes = [self._base_classes[i] for i in active]
        color_counts: dict[int, int] = {}
        for cls in active_classes:
            color_counts[cls] = color_counts.get(cls, 0) + 1
        ranked = sorted(color_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        majority = ranked[0][0]
        minority = ranked[1][0] if len(ranked) > 1 else majority

        sub_stencil = [[self._stencil[i][j] for j in active] for i in active]
        m = len(active)
        target_major = [1 if cls != majority else 0 for cls in active_classes]
        target_minor = [1 if cls != minority else 0 for cls in active_classes]
        # Per the wiki's own documented target family for this puzzle class
        # (zero / all-flip / single-cell e_k), also try flipping each
        # active cell in isolation — a uniform majority/minority-convergence
        # target is only ONE plausible win-condition hypothesis; a
        # single-cell target is the other common shape for this class.
        single_targets = [tuple(1 if k == e else 0 for k in range(m)) for e in range(m)]

        best_solution: list[int] | None = None
        for target in (target_major, target_minor, *single_targets):
            solution = gf2_solve(sub_stencil, target)
            if solution is None:
                continue
            if best_solution is None or sum(solution) < sum(best_solution):
                best_solution = list(solution)

        if best_solution is not None:
            self._solution_queue = [
                _cell_point(self._candidates[active[k]])
                for k in range(m)
                if best_solution[k]
            ]

    # ── planning: which candidate to click next ──────────────────────────

    def _next_target(self, grid: Grid) -> Cell:
        if not self._candidates:
            h = len(grid) or 1
            w = len(grid[0]) if grid else 1
            return (h // 2, w // 2)

        if self._phase == "probe":
            return _cell_point(self._candidates[self._probe_j])

        if self._phase == "execute":
            if self._solution_queue:
                return self._solution_queue.pop(0)
            self._phase = "fallback"

        return self._fallback_target()

    def _fallback_target(self) -> Cell:
        # Every candidate has a measured effect (or lack of one) from the
        # probe phase already, exactly like lp85's post-cycle prioritization
        # — reused here as-is via the same observations list.
        operators = learn_point_operators(self._observations)
        effective_points = {p for op in operators if op["footprint"] for p in op["points"]}
        points = [_cell_point(c) for c in self._candidates]
        priority = sorted(
            range(len(points)),
            key=lambda i: 0 if points[i] in effective_points or points[i] in self._responsive else 1,
        )
        idx = priority[self._fallback_cursor % len(priority)]
        self._fallback_cursor += 1
        return points[idx]
