"""script25 quarantined adapter: VC33 (rare-color click family).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/VC33.md`` (read for reference, not imported) records
VC33 as a "click" game (R57's typology T1, click-arrival): no movement
actions, only ACTION6; the legacy ``click_rare`` heuristic clears level 0
via a click near a colour-9 cluster, "similar shape to LP85 but with a
different target colour".

**Offline verification (before any live action)**: loaded
``data/traces/vc33.npz`` (gold trace, label-generation only, never
imported into this adapter). Level 0's gold block is 7 actions (matching
``baseline_actions[0] == 7``); the WINNING click (the row where
``levels_completed_after`` first increments) lands inside a 4x4,
16-cell, colour-9 region at grid bbox ``(32, 60, 35, 63)``.

The frame has **two** colour-9 regions of identical size (16 cells each,
at bbox ``(24, 60, 27, 63)`` and ``(32, 60, 35, 63)``) — same colour,
same size, so rarity ranking alone cannot tell them apart. Gold's own
trace clicks the FIRST one twice (rows 0-1: a visible-but-non-winning
response, +0.02 reward each) before switching to the SECOND one and
clicking it repeatedly (rows 2-6) to win.

**A first version copied LP85's exact recipe verbatim (rarity-ranked
candidates, try each once, then round-robin recycle preferring
"responsive" candidates) and it FAILED live -- 0/7 across 500 actions,
despite reaching the correct region's exact click point within the
first 9 actions.** Live probing (single-episode, direct
``arcengine`` calls, no adapter) uncovered the real mechanic, which is
NOT "one correct click wins" the way LP85 is:

- The correct region needs **3 (fresh-episode baseline) cumulative
  clicks** to win -- 1 or 2 clicks on it alone never win, MEASURED
  directly (fresh episode per candidate count, 1 through 5 clicks on
  the same point, zero prior actions of any kind).
- Those clicks do **not** need to be strictly consecutive: interleaving
  the correct click with a genuinely INERT off-target click (one that
  produces no visible effect) never raises the requirement -- MEASURED
  (``on, off, on, off, on`` still wins on the 3rd on-target click, and
  clicking 8 assorted inert candidates before ever touching the correct
  region also leaves its own requirement at exactly 3).
- But clicking the OTHER colour-9 (decoy, ALSO visibly "responsive")
  region RAISES the correct region's own click requirement, rather than
  resetting accumulated progress to zero outright -- MEASURED (0 prior
  decoy clicks: needs 3; 1 prior: needs 4; 2 prior: needs 5; 5 prior:
  needs 6 -- the increase saturates rather than climbing 1:1 forever).
  This is exactly what broke the LP85-style recycle: round-robin
  cycling visits BOTH same-colour candidates every lap, so each lap
  makes the correct target's own requirement climb again before it can
  ever be satisfied.

**Fix (this version)**: after the initial single-pass-per-candidate
probe (unchanged from LP85 -- still how the two same-colour candidates
get discovered and colour-ranked at all, though this ALSO means the
decoy already gets one "raise" click for free during that pass if it is
ever tried before the correct target is), the adapter no longer
round-robins. It COMMITS to one candidate at a time (priority order:
responsive candidates first, matching LP85's own tie-break) and clicks
it repeatedly, up to ``_SUSTAIN_ATTEMPTS`` times, before ever trying a
different candidate -- so a genuinely-correct target's own requirement
is never raised again mid-commitment by switching away and back.
``_SUSTAIN_ATTEMPTS`` (10) is set with margin over the measured worst
case observed (6, after heavy decoy interaction), not tuned to the
exact number, since the adapter has no way to know the true threshold in
advance and must discover "this didn't work" empirically per candidate.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments the frame into
    candidate click targets (excludes only chrome-sized regions -- a
    declared size threshold, not a coordinate).
  - :func:`admorphiq.kernels.frame_diff` + :func:`admorphiq.kernels.learn_point_operators`
    answer "did this click do ANYTHING, and if so what footprint did it
    write" after each probe -- used to prioritize the SUSTAINED-commit
    order toward candidates that showed some effect once every candidate
    has been tried once (a click puzzle has no navigation between
    clicks: ACTION6 reaches any candidate in exactly one action, so
    there is no shortest-path kernel to compose here).

Candidates are re-derived (and all cursor/commit state reset) on every
level-up, since the target set is a property of the level's own layout,
not something carried forward the way a movement game's controls are.
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

GAME_ID = "vc33"

Cell = tuple[int, int]  # (row, col)

# Per-level safety cap, mirroring every other script25 adapter's giveup
# convention so the harness never spins forever inside this one.
_GIVEUP_DEFAULT = 4000

# A region spanning at least this fraction of the frame's own cell count is a
# board-spanning panel / backdrop, not a discrete clickable target. Excludes
# chrome without any fixed pixel-count constant -- the threshold scales with
# whatever the live frame's own dimensions are. Matches LP85's own value;
# not re-measured separately since both games' chrome-vs-target shape was
# confirmed identical via the offline gold-frame region dump above.
_MAX_CANDIDATE_FRACTION = 0.15

# How many CONSECUTIVE clicks to commit to one candidate before trying a
# different one. MEASURED: the correct region alone needs 3 cumulative
# clicks, but clicking a DIFFERENT responsive-looking (decoy) region
# RAISES that requirement -- 1 decoy click raised it to 4, 2 to 5, 5 to 6
# (the increase saturates, does not keep climbing 1:1 with decoy click
# count). Since every candidate gets tried once during the initial pass
# before any sustained commitment begins (including a decoy, if one is
# responsive), the correct candidate's OWN threshold is already inflated
# by the time sustained commitment starts. 10 keeps comfortable margin
# over the measured worst case (6) observed after heavy decoy clicking.
_SUSTAIN_ATTEMPTS = 10


def _region_candidates(grid: tuple[tuple[int, ...], ...]) -> list[Cell]:
    """Non-background, non-chrome region centroids, rarest color first.

    "Rarest" = the SUM of every region's size sharing that color, ascending
    -- a color that appears in one small region is rarer than one that
    appears in several small regions adding up to more total pixels, which
    plain per-region size would miss. Ties (see module docstring's two
    identically-sized colour-9 regions) break by ``(color, bbox)``,
    deterministic but not semantically informed -- resolved instead by
    :meth:`Adapter._next_target` trying every candidate once before ever
    recycling.
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
        cell = (int(round(r["centroid"][0])), int(round(r["centroid"][1])))
        if cell not in seen:
            seen.add(cell)
            out.append(cell)
    return out


class Adapter(GameAdapter):
    """Rarity-ranked click-target probing composed entirely from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        # Mirrors every other script25 adapter's restart_on_game_over
        # convention: consumed by scripts/score_efficiency.py's run_game,
        # which RESETs the env and keeps calling this same adapter
        # instance on GAME_OVER instead of ending the run.
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

        # Sustained-commit state (see module docstring): once every
        # candidate has been probed once, the adapter commits to ONE
        # candidate at a time (priority-ordered, computed once) and
        # clicks it repeatedly rather than round-robin cycling, since
        # switching to a different responsive-looking candidate resets a
        # correct target's accumulated progress.
        self._sustain_order: list[Cell] = []
        self._sustain_idx = 0
        self._sustain_target: Cell | None = None
        self._sustain_remaining = 0

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
        re-derived, no carry-over (unlike a movement game's persisted
        control scheme)."""
        self._levels_seen = levels
        self._pending_click = None
        self._prev_grid = None
        self._candidates = _region_candidates(grid)
        self._cursor = 0
        self._responsive = set()
        self._observations = []
        self._sustain_order = []
        self._sustain_idx = 0
        self._sustain_target = None
        self._sustain_remaining = 0

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

        # Every candidate has been probed at least once. From here on,
        # COMMIT to one candidate at a time and click it repeatedly (see
        # module docstring: switching candidates resets a correct
        # target's accumulated progress, which is exactly what broke a
        # round-robin recycle here). The priority order (computed once,
        # not recomputed every call, so it stays stable while a
        # commitment is in progress) prefers whichever candidates showed
        # a visible effect during the initial pass -- a click that did
        # SOMETHING is more likely to be a genuine counter target than a
        # confirmed no-op, and this is also how the same-colour tie (see
        # module docstring) gets tried: both tied candidates were probed
        # during the initial pass regardless of rank, so the real winner
        # is never skipped, just possibly tried after its decoy sibling.
        if self._sustain_target is None or self._sustain_remaining <= 0:
            if not self._sustain_order:
                operators = learn_point_operators(self._observations)
                effective_points = {
                    p for op in operators if op["footprint"] for p in op["points"]
                }
                self._sustain_order = sorted(
                    self._candidates,
                    key=lambda c: 0 if c in effective_points or c in self._responsive else 1,
                )
            self._sustain_target = self._sustain_order[self._sustain_idx % len(self._sustain_order)]
            self._sustain_idx += 1
            self._sustain_remaining = _SUSTAIN_ATTEMPTS
        self._sustain_remaining -= 1
        return self._sustain_target
