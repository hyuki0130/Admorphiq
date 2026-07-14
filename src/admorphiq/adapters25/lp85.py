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
from admorphiq.kernels import find_regions, frame_diff, learn_point_operators

GAME_ID = "lp85"

Cell = tuple[int, int]  # (row, col)

# Per-level safety cap, mirroring admorphiq.adapters25.m0r0's giveup convention.
_GIVEUP_DEFAULT = 4000

# A region spanning at least this fraction of the frame's own cell count is a
# board-spanning panel / backdrop, not a discrete clickable target. Excludes
# chrome without any fixed pixel-count constant -- the threshold scales with
# whatever the live frame's own dimensions are.
_MAX_CANDIDATE_FRACTION = 0.15


def _region_candidates(grid: tuple[tuple[int, ...], ...]) -> list[Cell]:
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
    """
    if not grid:
        return []
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
    seen: set[Cell] = set()
    for r in ordered:
        for cell in sorted(r["cells"]):  # type: ignore[arg-type]
            if cell not in seen:
                seen.add(cell)
                out.append(cell)
    return out


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
        self._candidates: list[Cell] = []
        self._cursor = 0
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
        self._candidates = _region_candidates(grid)
        self._cursor = 0
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
        self._observations.append({"point": point, "before": before, "after": grid})

    # ── planning: which candidate to click next ─────────────────────────

    def _next_target(self, grid: tuple[tuple[int, ...], ...]) -> Cell:
        if not self._candidates:
            # No candidate regions at all on this frame -- fall back to the
            # frame's own observed centre (derived from live dimensions,
            # not a hardcoded coordinate) rather than crash.
            h = len(grid) or 1
            w = len(grid[0]) if grid else 1
            return (h // 2, w // 2)

        if self._cursor < len(self._candidates):
            target = self._candidates[self._cursor]
            self._cursor += 1
            return target

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
        idx = (self._cursor - len(self._candidates)) % len(priority)
        self._cursor += 1
        return priority[idx]
