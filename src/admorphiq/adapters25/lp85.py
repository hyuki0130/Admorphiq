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

**L2 SOLVED (2026-07-15) by the ring-permutation planner below.** The
"click the rare pixel" reading is a coincidence of L1's tiny scale, not the
game's mechanic. LP85 is a ring-rotation permutation puzzle: each button
sprite carries a ``button_<id>_<L|R>`` tag; clicking it CYCLICALLY ROTATES a
numbered ring (R: pos n->n+1 wrap; L: the exact inverse), and rings OVERLAP
(Hungarian-rings-class group). Verified by DRIVING the real engine offline:
the FIXED objects are the targets (``bghvgbtwcb`` color-11 4-corner sprite,
``fdgmtkfrxl`` color-12); what RIDES the rings and rotates is the ``goal``
sprite (color-11 SOLID 2x2). Win = each moving goal lands centered inside a
fixed target's 4-corner frame (``goal`` at target ``(x+1, y+1)``). L1 = 1
target + 1 goal + 1 ring, won in 4 presses (goal rides ring A to the target);
the round-robin sweep stumbles onto the productive button in 18 presses (near
the 17-action human) -- luck of scale, no ring model. L2 = 2 targets + 2 goals
+ 3 rings (A 26 cells, B/C 10 each, B/C overlap A at 2 cells; NO fdgmtkfrxl):
a genuine Hungarian-rings coupling. It IS tractable -- offline BFS over goal
positions finds an 8-move solution (264 states) and that sequence, replayed
through the real engine, clears L2. The one FRAME-ONLY obstacle -- learning
each ring's full successor map when a few adjacent cells share a colour (ring A
3, B 2) so their swap leaves no diff -- is handled by ordering the changed cells
into their cyclic loop and voting the rotation direction by colour agreement
(``kernels.permute.learn_cyclic_successor``), which reconstructs one clean
n-cycle regardless of that local ambiguity. The planner below (``_planner_step``
/ ``_detect`` / ``_learn_button`` / ``_build_plan``) runs first on every level;
on any failure (detection, self-test, or an unreachable plan) it hands off to
the rare-colour sweep, so the L1 floor is never lost. MEASURED: 2/8 levels,
game_score 0.0803 (up from the sweep-only 1/8 @ 0.0248). See
``.wiki/wiki/games/LP85.md`` for the full write-up.
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
from admorphiq.kernels import (
    complete_cycle,
    find_regions,
    frame_diff,
    learn_cyclic_successor,
    learn_point_operators,
    plan_token_assignment,
)

GAME_ID = "lp85"

Cell = tuple[int, int]  # (row, col)
Bbox = tuple[int, int, int, int]

# Per-level safety cap, mirroring admorphiq.adapters25.m0r0's giveup convention.
_GIVEUP_DEFAULT = 4000

# ── LP85 ring-solver semantics (adapter-declared; kernels stay game-agnostic) ──
# Verified by driving the real engine (see module docstring's L2 section): each
# button sprite is a rotation control; pressing it cyclically rotates a ring of
# board cells. Buttons render in two colours by rotation direction; the MOVING
# token that rides the rings and the FIXED destination marker both render in one
# shared colour but differ in shape (a solid block vs a hollow 4-corner frame).
_BUTTON_COLORS = frozenset({8, 14})  # rotation controls (two directions)
# Marker colour classes are DISCOVERED per level (a colour appearing as both a
# solid moving token and hollow corner-frame targets), not fixed — L2 has one
# class, L3 has two (goal + goal-o) that must all be placed to win.
_SOLID_MIN_SIZE = 3  # a marker region this size or larger is a solid moving token
_DEST_CLUSTER_SPAN = 6  # corner pixels within this L∞ span form one target frame
_PLANNER_BUDGET = 40  # max rotation-sequence length the BFS may return

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


def _cint(region: dict[str, Any]) -> Cell:
    r, c = region["centroid"]
    return (round(r), round(c))


def _planner_background(grid: tuple[tuple[int, ...], ...]) -> frozenset[int]:
    """The two most-common colours — the board backdrop + its panel/chrome fill.
    Both must be excluded: with only the top colour excluded, the second backdrop
    survives as regions that the generic marker-colour discovery can mistake for
    a token class. Marker tokens and ring tiles are small and far rarer than
    either backdrop, so dropping the top two never removes a real token colour."""
    counts: dict[int, int] = {}
    for row in grid:
        for v in row:
            counts[v] = counts.get(v, 0) + 1
    top = sorted(counts, key=lambda c: (-counts[c], c))[:2]
    return frozenset(top)


def _detect_buttons(regions: list[dict[str, Any]]) -> list[Cell]:
    """Rotation-control click cells: every region whose colour is a declared
    button colour, sorted for determinism. Inert picks (a control whose centroid
    lands off the playable viewport) simply learn an empty rotation and are
    dropped before planning."""
    return sorted(_cint(r) for r in regions if int(r["color"]) in _BUTTON_COLORS)


def _detect_marker_colors(regions: list[dict[str, Any]]) -> frozenset[int]:
    """The colour classes that behave as (moving solid token, fixed hollow
    target) pairs: a colour that appears BOTH as a solid block AND as a hollow
    4-corner target frame (a ≥3-dot cluster). A level may have several such
    classes (LP85 L3 has two — goal/target and goal-o/target-o — that must all
    be placed to win), so detection is not tied to a single hard-coded colour.
    Requiring a real corner *frame* (not just any stray small region) is what
    stops ordinary coloured ring tiles from being mistaken for markers."""
    solids = {
        int(r["color"])
        for r in regions
        if int(r["color"]) not in _BUTTON_COLORS and int(r["size"]) >= _SOLID_MIN_SIZE
    }
    return frozenset(c for c in solids if _detect_dests(regions, frozenset({c})))


def _detect_movers(regions: list[dict[str, Any]], colors: frozenset[int]) -> list[tuple[int, Cell]]:
    """Moving goal tokens = SOLID regions of a marker colour, tagged with their
    colour class (so a token is only ever matched to a same-class target)."""
    return sorted(
        (int(r["color"]), _cint(r))
        for r in regions
        if int(r["color"]) in colors and int(r["size"]) >= _SOLID_MIN_SIZE
    )


def _cluster_frame_centres(corners: list[Cell]) -> list[Cell]:
    """Group the loose corner dots of one colour into hollow target frames and
    return each frame's centre. Dots within ``_DEST_CLUSTER_SPAN`` (L∞) form one
    group; a group of ≥3 (a 4-corner frame, tolerating one occlusion) yields its
    rounded centroid."""
    used: set[int] = set()
    centres: list[Cell] = []
    for i, a in enumerate(corners):
        if i in used:
            continue
        group = [a]
        used.add(i)
        for j, b in enumerate(corners):
            if j not in used and abs(a[0] - b[0]) <= _DEST_CLUSTER_SPAN and abs(
                a[1] - b[1]
            ) <= _DEST_CLUSTER_SPAN:
                group.append(b)
                used.add(j)
        if len(group) >= 3:
            rr = round(sum(p[0] for p in group) / len(group))
            cc = round(sum(p[1] for p in group) / len(group))
            centres.append((rr, cc))
    return centres


def _detect_dests(regions: list[dict[str, Any]], colors: frozenset[int]) -> list[tuple[int, Cell]]:
    """Fixed destinations = the centres of the hollow 4-corner target frames,
    tagged with their colour class. The non-solid marker-colour pixels are the
    corner dots; cluster them per colour and take each cluster's centre."""
    dests: list[tuple[int, Cell]] = []
    for color in colors:
        corners = [
            _cint(r)
            for r in regions
            if int(r["color"]) == color and int(r["size"]) < _SOLID_MIN_SIZE
        ]
        dests.extend((color, centre) for centre in _cluster_frame_centres(corners))
    return sorted(dests)


def _token_regions(regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The small non-button regions that ride the rings (coloured tiles + goal
    tokens). The successor learner further restricts to the ones that actually
    moved, so including static corner dots here is harmless."""
    return [r for r in regions if int(r["color"]) not in _BUTTON_COLORS and int(r["size"]) <= 6]


def _snap(cell: Cell, lattice: list[Cell]) -> Cell:
    return min(lattice, key=lambda q: (q[0] - cell[0]) ** 2 + (q[1] - cell[1]) ** 2)


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

        # ── ring-permutation planner state (tried first each level; on any
        # failure the adapter falls back to the rare-colour sweep above, so the
        # L1 floor is never lost) ──
        self._planner_active = True
        self._phase = "settle"  # settle -> detect -> learn -> execute (or abort)
        self._bg: frozenset[int] = frozenset()
        self._marker_colors: frozenset[int] = frozenset()  # (mover, target) colour classes
        self._buttons: list[Cell] = []  # button click cells (row, col)
        self._dests: list[tuple[int, Cell]] = []  # (colour class, destination cell)
        self._ops: dict[str, dict[Cell, Cell]] = {}  # learned per-button rotations
        self._learn_idx = 0  # button whose press we are awaiting the result of
        self._pre_frame: tuple[tuple[int, ...], ...] | None = None
        self._pre_goals: list[Cell] = []
        self._plan: deque[str] = deque()
        self._selftest_fails = 0

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

        if self._planner_active:
            action = self._planner_step(grid)
            if action is not None:
                self._prev_grid = grid
                return action
            # Planner gave up on this level — fall through to the sweep, which
            # keeps the proven L1 floor (and GAME_OVER restarts reset cleanly).
            self._planner_active = False
            self._pending_click = None

        self._observe_result(grid)
        target = self._next_target(grid)
        self._prev_grid = grid
        self._pending_click = target
        row, col = target
        return click_action(x=col, y=row)

    # ── ring-permutation planner ────────────────────────────────────────

    def _click_button(self, idx: int) -> GameAction:
        row, col = self._buttons[idx]
        return click_action(x=col, y=row)

    def _planner_step(self, grid: tuple[tuple[int, ...], ...]) -> GameAction | None:
        """Drive the learn→plan→execute machine one step; return the action to
        take, or ``None`` to abort to the sweep. ``grid`` is the frame resulting
        from the previous action (the result of the click just issued)."""
        if self._phase == "settle":
            # One inert click lets a just-completed level transition render.
            self._phase = "detect"
            return click_action(x=0, y=0)

        if self._phase == "detect":
            if not self._detect(grid):
                return None
            self._phase = "learn"
            self._learn_idx = 0
            self._pre_frame = grid
            self._pre_goals = self._mover_cells(grid)
            return self._click_button(0)

        if self._phase == "learn":
            self._learn_button(self._learn_idx, grid)
            self._learn_idx += 1
            if self._learn_idx < len(self._buttons):
                self._pre_frame = grid
                self._pre_goals = self._mover_cells(grid)
                return self._click_button(self._learn_idx)
            # every control learned — plan from the self-test-clean rings only
            # (mislearned maps were dropped in _learn_button, so no global abort).
            if not self._build_plan(grid):
                return None
            self._phase = "execute"

        if self._phase == "execute":
            if not self._plan:
                return None  # plan ran out without a win — hand off to the sweep
            name = self._plan.popleft()
            return self._click_button(int(name[1:]))

        return None

    def _mover_cells(self, grid: tuple[tuple[int, ...], ...]) -> list[Cell]:
        """Current positions of every moving token (all colour classes)."""
        regions = find_regions(grid, background=self._bg)
        return [cell for _color, cell in _detect_movers(regions, self._marker_colors)]

    def _detect(self, grid: tuple[tuple[int, ...], ...]) -> bool:
        """Segment the frame into rotation controls, moving goal tokens, and
        fixed destinations across ALL colour classes. Returns whether the level
        looks like a solvable ring puzzle: ≥1 control, ≥1 moving token, and each
        colour class has as many movers as destinations (so a full placement
        exists)."""
        self._bg = _planner_background(grid)
        regions = find_regions(grid, background=self._bg)
        self._buttons = _detect_buttons(regions)
        self._marker_colors = _detect_marker_colors(regions)
        movers = _detect_movers(regions, self._marker_colors)
        self._dests = _detect_dests(regions, self._marker_colors)
        mover_counts: dict[int, int] = {}
        for color, _cell in movers:
            mover_counts[color] = mover_counts.get(color, 0) + 1
        dest_counts: dict[int, int] = {}
        for color, _cell in self._dests:
            dest_counts[color] = dest_counts.get(color, 0) + 1
        return len(self._buttons) >= 1 and len(movers) >= 1 and mover_counts == dest_counts

    def _learn_button(self, idx: int, grid: tuple[tuple[int, ...], ...]) -> None:
        """Learn button ``idx``'s rotation from the frame pair spanning its
        press, and self-test it against the observed goal displacement."""
        assert self._pre_frame is not None
        before = _token_regions(find_regions(self._pre_frame, background=self._bg))
        after = _token_regions(find_regions(grid, background=self._bg))
        diff = frame_diff(self._pre_frame, grid)
        # Pass every token centroid so a ring cell that stayed the same colour
        # (invisible in the diff) is recovered geometrically rather than dropped.
        candidates = [_cint(r) for r in before]
        succ = complete_cycle(
            learn_cyclic_successor(before, after, diff["cells"], candidate_cells=candidates)
        )
        if len(succ) < 2:
            return  # inert control (off-viewport / non-rotating) — skip it
        post_goals = set(self._mover_cells(grid))
        # Self-test then DROP-on-fail: a ring whose learned map mispredicts an
        # observed goal move is a WRONG map (it would corrupt the plan), so it is
        # excluded rather than counted toward a global abort. L4 is pressed by
        # ~16 buttons that rotate only 2 real rings; the correct (self-test-clean)
        # rotations are kept and the mislearned/edge presses dropped, instead of
        # the old "abort the whole plan after 2 failures" which tripped on the
        # redundant multi-button-per-ring learning even when the real rings were
        # learned correctly.
        for g in self._pre_goals:
            if g in succ and succ[g] not in post_goals:
                self._selftest_fails += 1
                return  # drop this mislearned map
        self._ops[f"b{idx}"] = succ

    def _build_plan(self, grid: tuple[tuple[int, ...], ...]) -> bool:
        ops = {k: v for k, v in self._ops.items() if len(v) >= 2}
        if not ops:
            return False
        lattice: list[Cell] = []
        seen: set[Cell] = set()
        for mp in ops.values():
            for cell in (*mp.keys(), *mp.values()):
                if cell not in seen:
                    seen.add(cell)
                    lattice.append(cell)
        movers = _detect_movers(find_regions(grid, background=self._bg), self._marker_colors)
        if not movers or len(movers) != len(self._dests):
            return False
        tokens = [_snap(cell, lattice) for _color, cell in movers]
        token_labels = [color for color, _cell in movers]
        dests = [_snap(cell, lattice) for _color, cell in self._dests]
        dest_labels = [color for color, _cell in self._dests]
        plan = plan_token_assignment(
            ops,
            tokens,
            dests,
            labels=token_labels,
            goal_labels=dest_labels,
            budget=_PLANNER_BUDGET,
        )
        if not plan:
            return False
        self._plan = deque(plan)
        return True

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
        # Re-arm the ring planner for the new level (a level's rings/targets are
        # its own; nothing carries over). Falls back to the sweep on failure.
        # The initial level's first frame is already settled, so detect it
        # immediately; a mid-game level transition renders one frame late, so
        # spend one inert click letting the new board settle before detecting.
        self._planner_active = True
        self._phase = "detect" if levels == 0 else "settle"
        self._marker_colors = frozenset()
        self._buttons = []
        self._dests = []
        self._ops = {}
        self._learn_idx = 0
        self._pre_frame = None
        self._pre_goals = []
        self._plan = deque()
        self._selftest_fails = 0

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
