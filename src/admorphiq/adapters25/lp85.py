"""script25 quarantined adapter: LP85 (rare-color click family).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/LP85.md`` (read for reference, not imported) records
LP85 as a "click" game: no movement actions, only ACTION6; the level
clears when the agent clicks the ONE pixel/region whose color is a
minority on the board, and "static non-interactive elements dominate the
frame". The legacy `click_rare` heuristic reflects exactly that.

**Divergence-first investigation (before this revision's fix, mirroring
every other script25 adapter's offline-verification discipline)**: a full
VM measurement found this adapter 0/8 at ~4000 actions despite the wiki
recording a known win pixel (`click_c8_(30,4)`). Replaying
``data/traces/lp85.npz``'s gold level-0 block against the adapter's own
candidate list found the actual bug: the winning pixel ``(30, 4)`` belongs
to a 40-pixel colour-8 region (bbox ``(29, 2, 36, 7)``), but this
adapter's OLD candidate generation collapsed that whole region down to
ONE point -- its centroid, ``(32, 5)`` -- a DIFFERENT pixel than the one
that actually wins. Frame-diffing gold's own clicks in and around that
region shows why collapsing to a centroid is wrong: clicking four
DISTINCT pixels within the SAME blob, ``(29,4)`` / ``(29,5)`` / ``(29,6)``
/ ``(29,7)``, each independently changes the frame (a HUD-visible fill bar
advances 5 rows per click, one segment at a time) but does NOT win; only
the fifth, DIFFERENT pixel ``(30,4)`` -- within the same 40-pixel blob --
triggers WIN. A single same-coloured connected region can therefore
contain SEVERAL functionally distinct pixels (here: 4 "fill" cells plus 1
"confirm" cell, the rest of the blob apparently inert), and no amount of
RANKING which region to try first fixes a strategy that only ever tries
one point per region. This matches the RETIRED (pre-quarantine)
``agent_ensemble.strat_click_rare`` exactly (read for reference, not
imported): it iterates ``np.argwhere(frame == color)`` -- literally EVERY
pixel of a rare colour, not one point per connected region -- which is how
it originally won this game. Two other candidate explanations were
checked against the SAME gold data and directly falsified: gold's 69
level-0 clicks are ALL distinct pixels (a repeated-click / vc33-style
counter mechanic is not what is happening here), and gold shows zero
GAME_OVER events (a life-ending fuse is not the primary wall either, even
though ``restart_on_game_over`` stays on as a defensive measure regardless
of which region-probing pattern this adapter's own play produces).

Mechanic hypothesis (role assignment, declared HERE, not in the kernel
layer): every PIXEL of a non-background, non-chrome-sized region is a
CANDIDATE click target (not one centroid per region — see the divergence
finding above); the correct one is more likely to belong to a color that
covers FEW pixels overall (a rare color is a plausible "this is special"
signal) than a color that dominates the frame (background/chrome). The
kernel layer knows nothing about "rare colors are targets" — it only
segments regions and reports diffs; the ranking-by-rarity heuristic, the
per-pixel enumeration, and the responsive/no-op bookkeeping live entirely
in this adapter.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments the frame into candidate
    click targets (adapter excludes only chrome-sized regions -- a
    declared size threshold, not a coordinate).
  - :func:`admorphiq.kernels.frame_diff` + :func:`admorphiq.kernels.learn_point_operators`
    answer "did this click do ANYTHING, and if so what footprint did it
    write" after each probe click -- used to prioritize re-clicking
    candidates that showed SOME effect once every candidate has been tried
    once (a click puzzle has no navigation between clicks: ACTION6 can
    reach any candidate in exactly one action, so there is no shortest-path
    kernel to compose here, unlike the movement family in ``m0r0.py``).

Candidates are re-derived (and the click cursor reset) on every level-up,
since the target set is a property of the level's own layout, not
something carried forward the way a movement game's controls are.

**Local-focus sweep (this revision, R56 2026-07-15)**: gold's own level-0
solve burns 69 actions against a human baseline of 17 because gold's
enumeration is breadth-first across the WHOLE board -- it touches dozens
of small, entirely unrelated regions (see the divergence finding above)
ONCE each before ever reaching the productive colour-8 region's own first
pixel, then only exhausts that region's pixels once it finally arrives
there. Simply grouping every region's own pixels consecutively (this
adapter's per-pixel enumeration above) does not fix that -- the wide
outer sweep still has to fully exhaust every rarer-or-tied candidate
region before the productive one is ever tried at all.

This adapter's probe QUEUE is therefore built ROUND-ROBIN across
qualifying regions (one untried pixel per region per round, rarity order
within a round, deepest rounds last) rather than one region fully before
the next -- mirroring gold's own breadth-before-depth instinct, but
cheaply: a region's FIRST pixel is reached after touching every
rarer-or-tied region's own first pixel ONCE, not after exhausting their
entire pixel counts. The moment a click shows ANY visible reaction
(``frame_diff`` count > 0 -- frame-observable, no reward-channel access
needed), the region has just proven itself special, so ALL its own
remaining untried pixels (otherwise scattered across later rounds,
interleaved with every other region's own pixels) are promoted to the
FRONT of the queue immediately -- a responsive region is finished (win,
or its own pixel budget exhausted) before the round-robin sweep resumes
elsewhere, instead of waiting for its turn in a future round.
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
from admorphiq.kernels import find_regions, frame_diff, learn_point_operators

GAME_ID = "lp85"

Cell = tuple[int, int]  # (row, col)
Bbox = tuple[int, int, int, int]

# Per-level safety cap, mirroring admorphiq.adapters25.m0r0's giveup convention.
_GIVEUP_DEFAULT = 4000

# A region spanning at least this fraction of the frame's own cell count is a
# board-spanning panel / backdrop, not a discrete clickable target. Excludes
# chrome without any fixed pixel-count constant -- the threshold scales with
# whatever the live frame's own dimensions are.
_MAX_CANDIDATE_FRACTION = 0.15


def _candidates_with_region(
    grid: tuple[tuple[int, ...], ...],
) -> tuple[list[Cell], dict[Cell, Bbox]]:
    """EVERY individual pixel of every non-background, non-chrome region,
    rarest color first, then by pixel position within a region -- NOT one
    centroid per region (see module docstring's divergence finding: a
    single connected same-coloured blob can contain several functionally
    DISTINCT pixels, and the correct one is not necessarily anywhere near
    the blob's own centroid). Mirrors the retired
    ``agent_ensemble.strat_click_rare``'s exact enumeration (every pixel of
    a rare colour, via ``np.argwhere``), reimplemented here compositionally
    from ``find_regions``' own per-region ``cells`` rather than a raw grid
    scan.

    "Rarest" = the SUM of every region's size sharing that color, ascending
    -- a color that appears in one small region is rarer than one that
    appears in several small regions adding up to more total pixels, which
    plain per-region size would miss.

    Also returns ``{pixel: owning_region_bbox}`` -- a stable per-level
    identity for "which other pixels belong to the same region as this
    one", the fact the local-focus sweep (see module docstring) reads to
    promote a responsive region's remaining pixels ahead of the outer
    sweep.
    """
    if not grid:
        return [], {}
    total_cells = len(grid) * len(grid[0])
    bg = most_common_color(grid)
    regions = find_regions(grid, background=bg)
    max_size = max(1, int(total_cells * _MAX_CANDIDATE_FRACTION))
    candidates = [r for r in regions if r["size"] <= max_size]

    color_total: dict[int, int] = {}
    for r in candidates:
        color_total[r["color"]] = color_total.get(r["color"], 0) + r["size"]

    ordered = sorted(
        candidates,
        key=lambda r: (color_total[r["color"]], r["color"], r["bbox"]),
    )
    out: list[Cell] = []
    region_of: dict[Cell, Bbox] = {}
    seen: set[Cell] = set()
    for r in ordered:
        for cell in sorted(r["cells"]):  # type: ignore[arg-type]
            if cell not in seen:
                seen.add(cell)
                out.append(cell)
                region_of[cell] = r["bbox"]
    return out, region_of


def _region_candidates(grid: tuple[tuple[int, ...], ...]) -> list[Cell]:
    """The ordered candidate list alone -- see ``_candidates_with_region``
    for the full contract (rarity/position ordering, per-pixel
    enumeration). Kept as a thin wrapper for callers that don't need the
    region-membership map."""
    candidates, _region_of = _candidates_with_region(grid)
    return candidates


def _round_robin_queue(candidates: list[Cell], region_of: dict[Cell, Bbox]) -> deque[Cell]:
    """Reorder ``candidates`` (already rarity/position ordered, one region
    fully consecutive before the next) into a ROUND-ROBIN probe queue: one
    untried pixel per region per round, region-rarity order within a
    round, deepest rounds last -- breadth across every candidate region
    before depth into any single one. See module docstring's "Local-focus
    sweep" section for why plain region-grouped order isn't enough on its
    own: a rarer-or-tied region's ENTIRE pixel count must otherwise be
    exhausted before a later region's own first pixel is ever tried, which
    is exactly gold's own measured 69-vs-17-action inefficiency. Round-
    robin instead reaches every region's first pixel after only ONE pass
    over every rarer-or-tied region, and ``Adapter._promote_region`` is
    what then lets a responsive region skip the rest of the rounds."""
    by_region: dict[Bbox, list[Cell]] = {}
    region_order: list[Bbox] = []
    for cell in candidates:
        region = region_of[cell]
        if region not in by_region:
            by_region[region] = []
            region_order.append(region)
        by_region[region].append(cell)

    queue: deque[Cell] = deque()
    round_idx = 0
    remaining = True
    while remaining:
        remaining = False
        for region in region_order:
            pixels = by_region[region]
            if round_idx < len(pixels):
                queue.append(pixels[round_idx])
                if round_idx + 1 < len(pixels):
                    remaining = True
        round_idx += 1
    return queue


class Adapter(GameAdapter):
    """Rarity-ranked click-target probing composed entirely from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        # A smoke run measured LP85 GAME_OVER-ing (not just no-op clicking)
        # partway through candidate probing, ending the run well short of
        # its action budget. Mirrors admorphiq.adapters25.m0r0's own
        # restart_on_game_over convention: consumed by
        # scripts/score_efficiency.py's run_game, which RESETs the env and
        # keeps calling this same adapter instance on GAME_OVER instead of
        # ending the run.
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1
        # The FULL rarity-ordered candidate list, fixed for the level --
        # kept for the second-pass re-cycle tier (see _next_target) and as
        # the source the first-pass queue is seeded from.
        self._candidates: list[Cell] = []
        # {pixel: owning region bbox} -- the fact the local-focus sweep
        # reads to find a responsive region's OTHER untried pixels (see
        # module docstring and _observe_result).
        self._region_of: dict[Cell, Bbox] = {}
        # The first-pass probe queue -- unlike _candidates, this is a LIVE,
        # reorderable queue: _observe_result promotes a responsive region's
        # remaining untried pixels to the FRONT, so the local-focus sweep
        # finishes that region before the outer rarity sweep resumes.
        self._queue: deque[Cell] = deque()
        self._recycle_cursor = 0
        self._responsive: set[Cell] = set()
        self._observations: list[dict[str, Any]] = []
        self._pending_click: Cell | None = None
        self._prev_grid: tuple[tuple[int, ...], ...] | None = None

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state in ("NOT_PLAYED", "GAME_OVER") or not has_frame(latest_frame):
            self._pending_click = None
            self._prev_grid = None
            self._levels_seen = -1
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._on_level_up(levels, grid)

        self._step += 1
        self._observe_result(grid)

        target = self._next_target(grid)
        self._prev_grid = grid
        self._pending_click = target
        row, col = target
        return click_action(x=col, y=row)

    # ── level bookkeeping ───────────────────────────────────────────────

    def _on_level_up(self, levels: int, grid: tuple[tuple[int, ...], ...]) -> None:
        """The candidate set is a property of THIS level's layout -- fully
        re-derived, no carry-over (unlike m0r0's persisted dir_map)."""
        self._levels_seen = levels
        self._pending_click = None
        self._prev_grid = None
        self._candidates, self._region_of = _candidates_with_region(grid)
        self._queue = _round_robin_queue(self._candidates, self._region_of)
        self._recycle_cursor = 0
        self._responsive = set()
        self._observations = []

    # ── measurement: did the pending click do anything? ─────────────────

    def _observe_result(self, grid: tuple[tuple[int, ...], ...]) -> None:
        point = self._pending_click
        before = self._prev_grid
        self._pending_click = None
        if point is None or before is None:
            return
        diff = frame_diff(before, grid)
        if diff["count"] > 0:
            self._responsive.add(point)
            self._promote_region(point)
        self._observations.append({"point": point, "before": before, "after": grid})

    def _promote_region(self, point: Cell) -> None:
        """LOCAL-FOCUS SWEEP: ``point`` just proved its own region special
        (a visible reaction, frame-observable) -- move every OTHER
        still-untried pixel of that SAME region to the FRONT of the probe
        queue, ahead of whatever the outer rarity sweep had queued next.
        A responsive region is finished (win, or its own pixels exhausted)
        before the sweep resumes elsewhere, instead of gold's own
        breadth-first pattern (measured: 69 actions against a human
        baseline of 17, because gold's sweep interleaves unrelated
        candidates between a responsive region's own pixels -- see module
        docstring)."""
        region = self._region_of.get(point)
        if region is None:
            return
        same_region = [c for c in self._queue if self._region_of.get(c) == region]
        if not same_region:
            return
        for c in same_region:
            self._queue.remove(c)
        for c in reversed(same_region):
            self._queue.appendleft(c)

    # ── planning: which candidate to click next ─────────────────────────

    def _next_target(self, grid: tuple[tuple[int, ...], ...]) -> Cell:
        if not self._candidates:
            # No candidate regions at all on this frame -- fall back to the
            # frame's own observed centre (derived from live dimensions,
            # not a hardcoded coordinate) rather than crash.
            h = len(grid) or 1
            w = len(grid[0]) if grid else 1
            return (h // 2, w // 2)

        if self._queue:
            return self._queue.popleft()

        # Every candidate has been probed at least once. Compose
        # learn_point_operators over every observation gathered so far so
        # responsive clicks (any learned operator with a non-empty
        # footprint) are prioritized on the re-cycle -- a click that
        # visibly did something is more likely to be the win condition
        # than one that was a confirmed no-op.
        operators = learn_point_operators(self._observations)
        effective_points = {
            p for op in operators if op["footprint"] for p in op["points"]
        }
        priority = sorted(
            self._candidates,
            key=lambda c: 0 if c in effective_points or c in self._responsive else 1,
        )
        idx = self._recycle_cursor % len(priority)
        self._recycle_cursor += 1
        return priority[idx]
