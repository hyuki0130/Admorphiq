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

**Discriminator search (bounded, inconclusive)**: gold wins in 7 total
actions with zero wasted commitment, meaning the gold policy identified
the correct region without ever needing to test the decoy -- worth
checking whether a structural signal exists that would let this adapter
skip straight to it too. :func:`admorphiq.kernels.region_relations` shows
both colour-9 regions are symmetric in shape (``contains``/``adjacent``
to their own local colour-0 panel, ``aligned_col`` with each other,
``adjacent`` to the same colour-5 region) -- the only measured
difference is the SIZE of each one's containing panel (848 cells for
the decoy's, 368 for the winner's). This is the one candidate found in a
bounded search; it was NOT adopted as an ordering signal, because with
only ONE gold level available for this game there is no second data
point to confirm "smaller containing panel" is a real, generalizable
rule rather than a coincidence of this specific level's layout -- an
unverifiable single-level correlation is not a principled discriminator,
just a guess wearing a measurement's clothing. Left as an open lever:
if a future round gets gold coverage on additional VC33 levels, re-check
whether this panel-size relationship holds up before adopting it.

**R56 iteration 2 -- the containing-panel discriminator VERIFIED LIVE and
ADOPTED for L0 efficiency (2026-07-15).** The open lever above is now
resolved for L0 by direct live measurement, not correlation: clicking
ONLY the smaller-containing-panel colour-9 region (368 vs 848) clears L0
in exactly 3 clicks, never touching the decoy. So :func:`_region_candidates`
now orders by ascending CONTAINING-PANEL size first -- a click TARGET is a
small region NESTED inside a larger panel (both colour-9 regions are;
chrome/panel colours are not contained), and the winner's panel is the
smaller. Non-contained candidates get an unbounded panel key, so they sort
after every nested target but keep their old rarest-colour order among
themselves (byte-identical behaviour on levels with no nested target). This
makes ``_candidates[0]`` the winner, and a new LEAD-COMMIT phase in
:meth:`_next_target` clicks it exclusively (``_LEAD_ATTEMPTS``) BEFORE
probing any other candidate, so the decoy is never touched and the
requirement never inflates. **Measured: L0 in 3 actions (was 54), score 1.0
capped vs a 7-action human, game_score 0.0006 -> 0.0357 (60x).** If the lead
does not clear within its budget (a mis-ranked or deeper level), control
falls through to the original probe-all + sustain recycle, so the 1/7 floor
is preserved.

**L1 (=level index 1) BANKED -- deeper structure, no gold oracle.** L1 is
also a two-colour-9 layout, but the 3-click lead does NOT clear it (its
human baseline is 18 vs L0's 7, and the game source shows the real mechanic
is a CONNECT/ALIGN puzzle -- clicking a connector with valid before/after
aligned neighbours moves tokens; win = all tokens aligned to matching slots,
``ielczunthe``). The L0 "click the region 3x" behaviour is a surface case
of that (a single already-aligned connector). L1 needs the connector-chain
sequence decoded, and ``data/traces/vc33.npz`` covers ONLY level 0 (no L1+
gold), so there is no oracle -- banked as the reopen pointer, not chased
blind.

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
# Clicks spent committing to the top-ranked candidate (the containing-panel
# winner) BEFORE probing any other candidate. Enough to satisfy the winner's
# bare requirement (measured 3 on L0, with headroom for a slightly deeper
# level) while capping the waste if the discriminator mis-ranks.
_LEAD_ATTEMPTS = 6


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

    # Among identically-rare same-colour candidates (the module docstring's
    # two colour-9 regions — one WINNER, one DECOY whose clicks inflate the
    # winner's requirement), the winner's own CONTAINING PANEL is the smaller
    # one (measured live: 368 vs 848; clicking ONLY the smaller-panel region
    # clears L0 in 3 clicks, never touching the decoy). So break the rarity
    # tie by ascending containing-panel size, putting the winner first —
    # ``_next_target`` commits to it exclusively, so the decoy is never
    # clicked and the requirement never inflates. A candidate with no
    # containing panel sorts as if its panel were unbounded (after any that
    # have one), and the previous ``(colour, bbox)`` key remains the final,
    # fully deterministic tiebreak.
    def _panel_size(target: dict[str, Any]) -> int:
        tb = target["bbox"]
        best = None
        for r in regions:
            rb = r["bbox"]
            if (
                r["size"] > target["size"]
                and rb[0] <= tb[0]
                and rb[1] <= tb[1]
                and rb[2] >= tb[2]
                and rb[3] >= tb[3]
            ):
                if best is None or r["size"] < best:
                    best = r["size"]
        return best if best is not None else total_cells + 1

    # Order by containing-panel size FIRST: a click TARGET is a small region
    # nested inside a larger panel (both colour-9 regions on L0 are; the
    # chrome/panel colours are not contained in anything), and among nested
    # targets the WINNER's panel is the smaller (368 vs the decoy's 848).
    # Non-contained candidates get an unbounded panel key, so they sort after
    # every contained target but keep their original rarest-colour ordering
    # among themselves (preserving the old behaviour on levels with no nested
    # target). This makes ``_candidates[0]`` the winner for the L0 decoy
    # layout, which the lead-commit in ``_next_target`` then clears in ~3
    # clicks without ever touching the decoy.
    ordered = sorted(
        candidates,
        key=lambda r: (_panel_size(r), color_total[r["color"]], r["color"], r["bbox"]),
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
        # Lead-commit phase: click the top-ranked (containing-panel winner)
        # candidate exclusively before probing any other, so the decoy is
        # never touched. Reset every level.
        self._lead_clicks = 0
        self._lead_done = False

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
        self._lead_clicks = 0
        self._lead_done = False

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

        # LEAD COMMIT (efficiency): click the TOP-ranked candidate — the
        # winner picked by the containing-panel discriminator in
        # ``_region_candidates`` — exclusively FIRST, before probing any
        # other candidate. Probing every candidate once (the pass below)
        # would click the DECOY sibling and inflate the winner's own
        # requirement (module docstring), so a correct top-rank clears in its
        # bare requirement (measured: 3 clicks on L0) with the decoy never
        # touched. If the lead does not clear within its budget the
        # discriminator may have mis-ranked, so control falls through to the
        # original probe-all + sustain recycle, preserving the floor.
        if not self._lead_done:
            if self._lead_clicks < _LEAD_ATTEMPTS:
                self._lead_clicks += 1
                return self._candidates[0]
            self._lead_done = True

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
