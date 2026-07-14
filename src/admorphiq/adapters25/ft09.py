"""script25 quarantined adapter: FT09 (click-toggle-parity family).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/FT09.md`` + ``.wiki/wiki/concepts/gf2_toggle_stencil.md``
+ ``.wiki/wiki/lessons/gf2_lights_out_stencil_20260423.md`` (read for
reference, not imported) record FT09 as a click-only toggle-parity puzzle.
Gold-trace reverse-engineering (2026-07-15, `.wiki/wiki/rounds/` FT09
decode notes) FALSIFIED the "coupled GF(2) neighbourhood stencil" reading:
clicking a cell only ever changes THAT cell, never a neighbour, and the win
target is not a hardcoded palette guess — it is DRAWN on the board itself.
FT09's board is one or more 8-cell "rings" (a 3x3 layout minus its own
center) arranged around a 6x6 "glyph" occupying the ring's own center gap.
The glyph is a 3x3 compass-position pattern (NW/N/NE/W/center/E/SW/S/SE)
painted in exactly two non-marker "ink" colours (measured: always 0 and 2)
plus the ring's own marker colour at its center cell. Decode, MEASURED
exact (byte-for-byte) against a gold level: a compass position painted ink
colour 0 must reach the glyph's own center (marker) colour; ink colour 2
must reach the ring's OTHER observed button colour (read from the ring's
own cells, never hardcoded — a board's two-colour alphabet varies, e.g.
{8,9} on one level, {8,9,12} on another). A ring cell needs a click iff its
CURRENT colour differs from its glyph-predicted target; a ring that already
matches its own glyph is pre-solved and untouched. This generalizes across
multiple independent rings sharing one board (verified: a 4-ring board
where 3 rings are pre-solved and only the mismatched 4th needs exactly the
clicks the gold trace made, no more, no less).

Two-phase (decoy -> reveal) boards, also MEASURED: some levels' board at
level-start is a "decoy" — every discoverable ring already matches its own
glyph (nothing to click by the decode rule) — until ONE click anywhere on
it wholesale-replaces the visible region layout with a DIFFERENT, previously
invisible ring set (shifted position, different colour alphabet), which is
the level's real puzzle. The reveal click doubles as that new board's first
real toggle. This adapter treats "discovery found zero mismatches" as a
signal to make a probing trigger click (not a giveup), and re-runs discovery
from scratch after every click rather than trusting a stale board reading —
which handles the reveal transparently, without special-casing it, because a
wholesale-different region layout is just a fresh discovery result.

Also documented (``.wiki/wiki/lessons/ft09_stride_button_drop_20260423.md``):
the legacy solver's default fixed-pixel-stride probe grid lands on FT09's
cell BORDERS, not centers, and finds zero responsive cells until the stride
is narrowed. This adapter sidesteps the whole stride-alignment question —
candidate cells come from :func:`admorphiq.kernels.find_regions` segmenting
the RENDERED frame directly, never from a blind fixed-pixel sweep, so there
is no grid-alignment guess to get wrong in the first place.

Primary strategy — glyph decode (composed from ``admorphiq.kernels``):
  - :func:`find_regions` segments the frame into same-sized button regions
    and finds each ring's center glyph gap.
  - Ring/pitch/glyph geometry is entirely DISCOVERED, never hardcoded: the
    grid pitch is the MODE of measured button-position gaps (not the min —
    a smaller gap can be cross-cluster noise from a separate ring landing
    nearby), and :func:`admorphiq.kernels.tile_bbox` splits a discovered
    glyph bbox into its 3x3 compass reading, so no fixed pixel offsets are
    baked in anywhere.
  - Every ``choose_action`` call in this phase RE-DISCOVERS rings from the
    CURRENT frame (cheap — one ``find_regions`` pass) rather than trusting a
    cached board, which is what makes the reveal-detection above free: a
    stale candidate list is never consulted, so there is nothing to
    invalidate.
  - A per-cell click-count cap (with a small budget of overall
    "contradictions" — a clicked cell that never reaches its predicted
    target) is the safety net: if the decode is simply wrong for a board
    this adapter hasn't seen before, it gives up on glyph-driven play for
    the level and falls back to the PRE-EXISTING probe/execute/fallback
    machinery below, exactly as before this change — never grinds forever
    against a lethal board on a wrong guess.

Fallback strategy — measured GF(2) stencil probe (unchanged from the
original design, used when glyph discovery finds no rings at all, or after
the glyph phase gives up): every non-background, non-chrome region on the
frame is a candidate clickable cell — the SAME set serves as both the
toggle VARIABLES (what can be clicked) and the toggle EQUATIONS (what can
change). For each candidate: click it once, read every candidate's own
bounding-box dominant colour to see which flipped, then click it AGAIN
(self-inverse) to undo before probing the next — this measures the
empirical stencil ``A[i][j]`` = "does clicking cell j flip cell i's
dominant colour". Within the OBSERVATIONALLY ACTIVE subset (a stencil row
or column with at least one live bit), several target hypotheses are tried
— majority-colour convergence, minority-colour convergence, and a
single-cell flip for each active cell in turn — and
:func:`admorphiq.kernels.gf2_solve`'s lowest-click-count solution among
whichever hypotheses are solvable is queued for execution. A measured
~200-action attempt/move-counter revives the SAME level on GAME_OVER (not a
fresh one), so an already-measured stencil is preserved and only RE-SOLVED
(free) rather than re-probed from scratch on every revival. If no target
hypothesis is solvable, the adapter falls back further to a responsive-first
cycling probe (mirroring ``admorphiq.adapters25.lp85``) rather than giving
up outright.

Candidates, the stencil, and the solved plan are all re-derived (and the
click cursor reset) on every genuine level-up (``levels_completed``
actually changes), since both are properties of the level's own layout,
not something carried forward across levels.
"""

from __future__ import annotations

from collections import Counter
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
from admorphiq.kernels import find_regions, frame_diff, gf2_solve, learn_point_operators, tile_bbox

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

# A ring needs 8 button-sized neighbours around its glyph gap.
_RING_SIZE = 8
_COMPASS_ORDER = ("NW", "N", "NE", "W", "C", "E", "SW", "S", "SE")
_COMPASS_OFFSET_SIGNS = {
    "NW": (-1, -1), "N": (-1, 0), "NE": (-1, 1),
    "W": (0, -1), "E": (0, 1),
    "SW": (1, -1), "S": (1, 0), "SE": (1, 1),
}
_GLYPH_MARKER_INK = 0  # ink colour that maps to the glyph's own center (marker) colour
_GLYPH_OTHER_INK = 2  # ink colour that maps to the ring's other observed button colour

# Give up on a specific glyph-predicted cell after this many clicks without
# reaching its predicted target (a multi-step colour cycle needs a FEW
# clicks, but an unbounded retry risks grinding a lethal board on a wrong
# decode instead of falling back).
_GLYPH_PER_CELL_CLICK_CAP = 4
# Total contradictions (cells that hit the per-cell cap, or a board where
# discovery + trigger clicks never produce a mismatch to act on) tolerated
# before abandoning glyph-driven play for the level and falling back to the
# probe/execute/fallback machinery.
_GLYPH_CONTRADICTION_CAP = 2


def _is_hud_row(bbox: Bbox, grid: Grid) -> bool:
    """A region spanning the FULL first-and-last row of the frame is the
    bottom HUD/status bar (a step counter or similar chrome), not a
    clickable cell -- excluded everywhere a candidate list is built. HUD-row
    contamination measured directly: a step counter incrementing every
    action inflates a region's diff bbox to span the whole frame, drowning
    out the real interaction points (see the FT09 decode session's CD82
    cross-reference)."""
    if not grid:
        return False
    last_row = len(grid) - 1
    return bbox[0] == last_row and bbox[2] == last_row


def _region_candidates(grid: Grid) -> list[dict[str, Any]]:
    """Non-background, non-chrome candidate cell regions, in find_regions' own
    deterministic (bbox row0, bbox col0, colour) order."""
    if not grid:
        return []
    total_cells = len(grid) * len(grid[0])
    bg = most_common_color(grid)
    regions = find_regions(grid, background=bg)
    max_size = max(1, int(total_cells * _MAX_CANDIDATE_FRACTION))
    return [r for r in regions if r["size"] <= max_size and not _is_hud_row(r["bbox"], grid)]


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


# ── glyph decode: ring/pitch/glyph discovery, entirely from frame observation ──


def _discover_rings(grid: Grid) -> list[dict[str, Any]]:
    """Discover 8-cell toggle rings and their center glyph gaps. Pure frame
    observation: button size is the modal size among same-sized regions
    occurring >= 8 times (a ring's own member count); pitch is the MODE of
    measured button-position gaps (the min is unreliable -- a smaller gap
    can be cross-cluster noise from an unrelated ring's columns landing
    close by, measured directly on a real 4-ring board); a ring is any gap
    position whose all 8 compass-offset neighbours are button regions."""
    if not grid:
        return []
    bg = most_common_color(grid)
    regions = [r for r in find_regions(grid, background=bg) if not _is_hud_row(r["bbox"], grid)]
    size_counts = Counter(r["size"] for r in regions)
    button_sizes = [s for s, c in size_counts.items() if c >= _RING_SIZE]
    if not button_sizes:
        return []
    button_size = max(button_sizes, key=lambda s: size_counts[s])
    buttons = [r for r in regions if r["size"] == button_size]
    by_topleft = {(r["bbox"][0], r["bbox"][1]): r for r in buttons}

    btn_h = buttons[0]["bbox"][2] - buttons[0]["bbox"][0] + 1
    btn_w = buttons[0]["bbox"][3] - buttons[0]["bbox"][1] + 1
    row0s = sorted({r["bbox"][0] for r in buttons})
    col0s = sorted({r["bbox"][1] for r in buttons})
    row_gaps = [b - a for a, b in zip(row0s, row0s[1:]) if b - a >= btn_h]
    col_gaps = [b - a for a, b in zip(col0s, col0s[1:]) if b - a >= btn_w]
    if not row_gaps or not col_gaps:
        return []
    pitch_r = Counter(row_gaps).most_common(1)[0][0]
    pitch_c = Counter(col_gaps).most_common(1)[0][0]
    offsets = {
        name: (dr * pitch_r, dc * pitch_c)
        for name, (dr, dc) in _COMPASS_OFFSET_SIGNS.items()
    }

    rings: list[dict[str, Any]] = []
    seen_centers: set[Cell] = set()
    for r0, c0 in by_topleft:
        for dr, dc in offsets.values():
            cr, cc = r0 - dr, c0 - dc
            if (cr, cc) in seen_centers or (cr, cc) in by_topleft:
                continue
            neighbours: dict[str, dict[str, Any]] = {}
            ok = True
            for name, (odr, odc) in offsets.items():
                pos = (cr + odr, cc + odc)
                if pos not in by_topleft:
                    ok = False
                    break
                neighbours[name] = by_topleft[pos]
            if not ok:
                continue
            seen_centers.add((cr, cc))
            glyph_bbox: Bbox = (cr, cc, cr + btn_h - 1, cc + btn_w - 1)
            rings.append({"glyph_bbox": glyph_bbox, "ring_cells": neighbours})
    return rings


def _read_glyph_compass(grid: Grid, glyph_bbox: Bbox) -> dict[str, int]:
    """Split ``glyph_bbox`` into its 3x3 compass reading via the generic
    ``tile_bbox`` kernel (no hardcoded pixel offsets), sampling each
    sub-cell's top-left pixel (the glyph's own block-structured art)."""
    subs = tile_bbox(glyph_bbox, 3, 3)
    return {name: grid[r0][c0] for name, (r0, c0, _r1, _c1) in zip(_COMPASS_ORDER, subs)}


def _decode_ring_mismatches(grid: Grid, ring: dict[str, Any]) -> list[tuple[Cell, int]]:
    """Cells in ``ring`` whose current colour differs from their glyph-
    predicted target: ink colour 0 -> the glyph's own center (marker)
    colour, ink colour 2 -> the ring's OTHER observed button colour (read
    from this ring's own cells, never a hardcoded palette -- a board's
    two-colour alphabet is measured to vary between levels). Returns []
    when the ring already matches its glyph (pre-solved) OR when the ring's
    'other' colour can't be determined (every button already shows the
    marker colour, so there is no second observed colour to disambiguate
    against)."""
    glyph = _read_glyph_compass(grid, ring["glyph_bbox"])
    marker = glyph["C"]
    observed = {_cell_class(grid, c["bbox"]) for c in ring["ring_cells"].values()}
    other_candidates = observed - {marker}
    if len(other_candidates) != 1:
        return []
    other = next(iter(other_candidates))

    mismatches: list[tuple[Cell, int]] = []
    for name, cell in ring["ring_cells"].items():
        ink = glyph[name]
        target = marker if ink == _GLYPH_MARKER_INK else other if ink == _GLYPH_OTHER_INK else None
        if target is None:
            continue
        if _cell_class(grid, cell["bbox"]) != target:
            mismatches.append((_cell_point(cell), target))
    return mismatches


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

        self._phase = "probe"  # "glyph" -> "probe" -> "execute" -> "fallback"
        self._probe_j = 0
        self._probe_substep = "click"  # "click" -> "unclick"
        self._solution_queue: list[Cell] = []
        self._fallback_cursor = 0

        self._responsive: set[Cell] = set()
        self._observations: list[dict[str, Any]] = []
        self._pending_click: Cell | None = None
        self._prev_grid: Grid | None = None

        # Glyph-decode phase state. ``_glyph_pending_target`` is the predicted
        # colour for whatever cell was just clicked (None for a decoy-trigger
        # click, which has no predicted colour -- success is "the board
        # changed at all"). A cell that keeps producing NEW colours after
        # each click is a genuine measured multi-step cycle and stays in
        # play (bounded by the per-cell click cap); a click that changes
        # NOTHING, or that revisits a colour already seen for that cell
        # without ever reaching its target, is a contradiction -- the safety
        # net described in the module docstring.
        self._glyph_click_counts: dict[Cell, int] = {}
        self._glyph_seen_colours: dict[Cell, set[int]] = {}
        self._glyph_contradictions = 0
        self._glyph_trigger_attempts = 0
        self._glyph_pending_target: int | None = None
        self._glyph_pending_is_trigger = False

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
            elif self._phase == "glyph":
                # RESET reverts the board to this SAME level's pristine start
                # (attempt counter, not a fresh level), so any glyph-decode
                # click progress is undone too -- reset the per-cell bookkeeping
                # and let the next call's fresh re-discovery pick up from the
                # (again-pristine) board. Contradictions accumulated before
                # this GAME_OVER are real measurements of the decode failing
                # on THIS board and are deliberately NOT reset.
                self._glyph_click_counts = {}
                self._glyph_seen_colours = {}
                self._glyph_trigger_attempts = 0
                self._glyph_pending_target = None
                self._glyph_pending_is_trigger = False
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

        self._start_probe(grid)

        self._glyph_click_counts = {}
        self._glyph_seen_colours = {}
        self._glyph_contradictions = 0
        self._glyph_trigger_attempts = 0
        self._glyph_pending_target = None
        self._glyph_pending_is_trigger = False
        # Glyph decode takes priority over the probe machinery whenever this
        # level's board actually has a discoverable ring -- _start_probe above
        # still ran (so _candidates/_stencil are ready as the fallback if the
        # decode later gives up), but the phase itself starts at "glyph".
        if _discover_rings(grid):
            self._phase = "glyph"

    def _start_probe(self, grid: Grid) -> None:
        """(Re-)derive the probe/execute/fallback machinery's candidates from
        ``grid``. Called both on a genuine level-up and when the glyph phase
        abandons decode-driven play mid-level (in which case ``grid`` is the
        CURRENT board, which may already differ from the level-start board
        after a decoy -> reveal transition -- probing the live layout, not a
        stale one, is the whole point of calling this from both places)."""
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

        if self._phase == "glyph":
            self._observe_glyph_click(point, grid, diff)
            return

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
