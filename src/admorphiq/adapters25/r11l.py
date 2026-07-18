"""script25 quarantined adapter: R11L (click-driven drag-assembly puzzle).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/R11L.md`` (read for reference, not imported) records
R11L as a "sequence" game the legacy ``seq_repeat`` / ``seq_search`` cleared
1/6, and ``docs/r57_win_condition_typology_20260715.md`` flags it as an
unresolved T7/T8 case whose observable signature is "~11 consecutive
ACTION6". Reading the game source offline
(``environment_files/r11l/*/r11l.py``; dev-time only, the adapter reads only
frames at runtime) resolves it: R11L is neither a repeat-count nor a
symbol-rewrite game — it is a CLICK-DRIVEN DRAG-ASSEMBLY puzzle.

**Actual mechanic (drag-assembly) — the ONLY action is ACTION6 (click)**:

- The board has one or more CREATURES. Each creature is a BODY plus a set
  of LEGS (small clickable pieces) and a matching TARGET nest. The engine
  keeps a single SELECTED leg (auto-selected nearest the origin at level
  start).
- Clicking ON a leg SELECTS it. Clicking on empty space MOVES the selected
  leg to that point (an animated drag), UNLESS the destination collides with
  a HAZARD region (then the move is refused). Crucially, a body is
  repositioned to the CENTROID of its own legs after each move — so to bring
  a creature's body onto its target you must arrange ALL of that creature's
  legs so their average position sits on the target.
- WIN fires when EVERY creature's body overlaps its target nest (read from
  the engine's ``winning`` gate — all bodies on targets — but NEVER
  hardcoded here; the adapter reacts only to the engine's own WIN state).
- Repeated bad placements (5 collisions) or an exhausted action budget end
  the attempt in GAME_OVER. The "~11 consecutive ACTION6" the typology saw
  is simply the select/place click pairs for a few legs on level 0.

**Why a generic click-frontier explorer, not a bespoke solver**: solving
the assembly requires the CENTROID-arrangement geometry (place each
creature's legs so their mean lands on its target) AND a per-creature
leg→target grouping that the frame does not label — reconstructing both
faithfully would rebuild the game's own bookkeeping, the game-specific
"second brain" the R56 codex verdict
(``docs/r56_codex_toolbase_verdict_20260715.md``) forbids in the namespace.
Instead this adapter generalises the same transition-graph frontier
explorer the other movement adapters use, with the ACTION ALPHABET reduced
to a BOUNDED, frame-derived set of clicks — the centroid of every salient
(non-background, non-HUD) region — rather than the unbounded 64x64 click
space:

  - Every board state is canonicalised into a hashable key
    (:func:`admorphiq.kernels.canonical_key`, ``mode="exact"``) after the
    edge-pinned HUD bands are masked (:func:`admorphiq.kernels.find_regions`
    finds them).
  - The candidate clicks AT a state are that frame's salient region
    centroids (recorded per state so routing knows each state's options).
  - Every observed ``(state, click_cell, next_state)`` transition is
    recorded; the policy takes an untried click at the current state, else
    routes (:func:`admorphiq.kernels.transition_shortest_path`) to the
    nearest visited state with an untried click (a small BFS over the same
    recorded edges, :meth:`_nearest_untried`).

**L0 (single creature): centroid-assembly PLANNER** — the one-shot
select→place plan (:meth:`_build_plan`) clears L0 super-humanly (4 actions vs a
22-action human baseline, game_score 0.0476).

**L1+ (≥2 creatures): STRIKE-AWARE MOVE PLANNER** (:meth:`_build_move_plan`,
:meth:`_plan_creature`, :meth:`_frozen_step`). Per creature, a best-first search
(A*, cost = number of moves) over the joint leg configuration finds an ORDERED
sequence of single-leg moves that lands the body (its legs' centroid) inside the
target ring's bbox while EVERY intermediate body centroid avoids the body-hazard.
The body-hazard is the generic ``_hazard_cells`` set (all large non-background
regions = the arena wall PLUS the in-play ``defgjl`` obstacle), reused
colour-agnostically — the missing piece the earlier controller lacked. Creatures
are planned in sequence, each keeping every placed leg ``_LEG_SEP`` from the
others (own and other creatures'), so no two legs fuse under region detection and
each stays selectable. Legs are detected (:meth:`_detect_legs`) and grouped per
creature by NEAREST BODY (:meth:`_detect_bodies`); a move is executed as
select(exact planned from-cell)→place(dest); a move that unexpectedly does not
fire learns its predicted body centroid as a hazard (part of the obstacle renders
as other colours) and replans within the 5-strike budget.

**Measured result (R85, 2026-07-19) — r11l 3/6 @ 0.2551, deterministic ×2**
(``--max-actions`` 600 and 3000 identical; loader ``r11l/495a7899``): L0 1.0
(7 actions, byte-identical floor), L1 0.8403 (36 actions), L2 0.8920 (54
actions). The strike-aware planner generalises past the two creatures of L1 to
the 4-leg ``grhcew`` creature of L2. This SUPERSEDES the R60c "wall-edge
placement is infeasible / DISPLAY→GRID camera transform" bank, which was WRONG:
the camera is IDENTITY, both L1 creatures have 121/121 geometrically-feasible
wall-free arrangements, and the true wall was the un-modelled ``defgjl`` body
obstacle (a 70×36 band over rows ~22-58, NOT off-screen as R60c claimed) that
strikes and reverts any move whose body centroid lands on it.

The generic click-frontier explorer (below) remains the fallback for boards
neither planner recognises. On its own it never advances past L0: the assembly
is a CONTINUOUS centroid-placement problem whose winning configuration is
rarely any single salient centroid, so a frontier search over "click an
existing region" cannot construct it except by luck.

FRAME structure (measured): LEGS are colour 3 / colour 0-when-selected (fill
~0.48, NOT creature-coloured — grouping is by nearest BODY); BODIES are colour
12/15 at fill ~0.80; TARGET rings are colour 12/15 at fill ~0.24; the wall and
the ``defgjl`` obstacle are large regions (both in ``_hazard_cells``). Deeper
levels (L3+, ``dirwzt`` variants) stay for a future round.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments the board into salient
    click candidates and masks the edge-pinned HUD bands.
  - :func:`admorphiq.kernels.canonical_key` hashes the masked board into a
    stable state key.
  - :func:`admorphiq.kernels.transition_shortest_path` routes over the
    incrementally-discovered transition graph to the nearest state with an
    untried click.
"""

from __future__ import annotations

import heapq
import os
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
    canonical_key,
    find_regions,
    points_with_centroid,
    transition_shortest_path,
)

GAME_ID = "r11l"

Cell = tuple[int, int]
Region = dict[str, Any]
Grid = tuple[tuple[int, ...], ...]

# Per-level safety cap, mirroring every other script25 adapter's giveup
# convention so the harness never spins forever inside this one.
_GIVEUP_DEFAULT = 4000

_HUD_SPAN_FRACTION = 0.85
_HUD_THICKNESS_FRACTION = 0.06

# Salient click candidates: a region small enough to be an interactive piece
# (a leg / target marker), not a big background slab. Purely a "is this a
# clickable thing" size gate, no game-specific pixel count.
_MIN_CAND_SIZE = 1
_MAX_CAND_SIZE = 400

# A non-background region at least this big is treated as a WALL/HAZARD
# (r11l's `bvzgd-*` level walls, plus the edge counter column): the planner
# must not place a leg on one (the game refuses such placements). A structural
# threshold, not a game-specific pixel count — pieces (legs) and the small
# body/target rings are all well under it.
_HAZARD_MIN_SIZE = 28
# Interactive PIECE size band (a leg / body / target marker) — excludes both
# single-pixel decoration (leg-to-body connector dots) and wall-sized slabs.
_MIN_PIECE_SIZE = 6
_MAX_PIECE_SIZE = 27
# A clickable FOOT (leg) is a compact blob; a leg-to-body LIMB line is thin
# (low bbox fill). Feet fill ~0.5 of their bbox, limbs ~0.15.
_MIN_LEG_FILL = 0.35
# A BODY marker is very compact (fills ~0.8 of its bbox); its TARGET nest is a
# low-fill ring (~0.24). This threshold separates a body from both its own
# target and from the feet (~0.5), so a creature colour = one body + one nest.
_BODY_FILL = 0.6
# Squared-distance tolerance for "a ring sits at the legs' centroid" (== the
# body). ~4 px, comfortably inside a body marker's own extent.
_BODY_CENTROID_TOL2 = 16.0
# A placed leg needs this many cells of clear background around its centre —
# roughly the leg sprite's half-extent — so legs land separated from the nest
# and each other (overlapping placements collide and burn the game's strikes).
_LEG_CLEAR_RADIUS = 2
# A drag animation settles in a handful of frames; a placement still unsettled
# after this many is stuck (the board changed under the plan) — abandon it.
_PLACE_STUCK_LIMIT = 12
# A new level's legs animate in; build the plan only once the detected creature
# signature has held for this many consecutive frames (past the animation).
_SETTLE_FRAMES = 3
# FROZEN-TARGET controller bound (multi-creature levels): total leg placements
# attempted before giving up to the explorer. A 2–3 creature assembly is 5–7
# legs; each leg needs at most a couple of select retries, so this covers the
# arrangement without spinning when a target is genuinely unreachable.
_MAX_FROZEN_MOVES = 48
# Alternate select cells to try for one leg when a placement does not fire: the
# leg's rounded centroid can fall on a background pixel of a non-convex sprite,
# so on a miss we click a different FILLED cell of the same leg before deciding
# the destination itself is refused.
_MAX_SELECT_RETRY = 3
# Best-first search bound for one creature's strike-aware move plan. A 2-3 leg
# assembly over a coarse candidate grid converges in a handful of expansions; this
# ceiling only guards against a pathological board (then the planner defers).
_ASTAR_MAX_EXPAND = 12000
# Minimum chebyshev distance between any two leg CENTRES the planner will place.
# Two leg blobs closer than this fuse under the gap-2 region detector; the merged
# blob then exceeds the piece-size gate and is dropped entirely, so the adapter can
# no longer find that leg to select/verify it — the measured L1 stall (orrqlj's 3rd
# leg landing 7 cells from pumlzd's, close enough to fuse). Keeping every placed leg
# this far from every other leg (own and other creatures', including a stationary
# leg that has not moved yet) keeps them individually detectable.
_LEG_SEP = 10
# Chebyshev radius for proximity-clustering multi-colour body fragments (and
# scattered target-ring fragments) into one piece in the colour-blind detector.
_CLUSTER_SEP = 6
# Speculative-target-trial (R87): body-centroid tolerance around a colour-blind
# candidate target centre (< engine overlap tolerance body_half+target_half), and
# the number of settled all-placed frames to wait for a win before advancing to
# the next candidate.
_TRIAL_TARGET_TOL = 4
_TRIAL_IDLE_FRAMES = 3


def near_d2(a: Cell, b: Cell) -> int:
    """Squared Euclidean distance between two cells (integer)."""
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _hazard_cells(grid: Grid, bg: int) -> set[Cell]:
    """Cells belonging to a wall/hazard region — any non-background region at
    or above :data:`_HAZARD_MIN_SIZE`. The planner treats these as unplaceable
    (the game refuses a leg drop that collides with one)."""
    cells: set[Cell] = set()
    for region in find_regions(grid, background=bg):
        if region["size"] >= _HAZARD_MIN_SIZE:
            cells |= region["cells"]
    return cells


def _fill(region: Region) -> float:
    """Fraction of a region's bounding box its cells occupy — a compact foot/
    body fills ~0.5-0.8, a thin limb line ~0.15."""
    r0, c0, r1, c1 = region["bbox"]
    area = (r1 - r0 + 1) * (c1 - c0 + 1)
    return region["size"] / area if area else 0.0


def _analyze_creatures(grid: Grid, bg: int, hazard: set[Cell]) -> list[tuple[list[Cell], Cell]] | None:
    """Detect ALL centroid-assembly creatures — one ``(leg_centres, target_centre)``
    per creature — from frame structure. Tries the per-colour detector first (the
    proven L0-L2 path); when it returns ``None`` (a board whose creature bodies are
    MULTI-COLOUR with colours shared across creatures, e.g. L3's `dirwzt` variants —
    the per-colour "one body colour = one creature" assumption is void there),
    falls back to a colour-BLIND connectivity detector. The fallback fires ONLY
    when the colour path fails, so L0-L2 detection is byte-identical."""
    by_color = _analyze_creatures_bycolor(grid, bg, hazard)
    if by_color is not None:
        return by_color
    conn = _analyze_creatures_connectivity(grid, bg, hazard)
    return conn[0] if conn is not None else None


def _analyze_creatures_bycolor(grid: Grid, bg: int, hazard: set[Cell]) -> list[tuple[list[Cell], Cell]] | None:
    """Per-colour centroid-assembly detection (the L0-L2 path).

    Model (validated live, see the module docstring): each creature is a BODY
    that sits at the integer CENTROID of its own clickable LEGS, plus a
    same-colour TARGET nest the body must reach. A body is a COMPACT high-fill
    marker; its target is a low-fill ring of the same colour. Legs are the
    other compact pieces; each is assigned to the NEAREST body (the assignment
    is self-labelling because a body sits on its legs' mean), and the grouping
    is verified — a group whose centroid is not near its body is rejected.

    Returns the per-creature list (>= 1) or ``None`` when no clean creature is
    found (the caller then tries the connectivity fallback, else the explorer).
    No colour or coordinate constants — only sizes, bbox-fill, the same-colour
    body/target signature, and centroid-nearness.
    """
    # gap=2 so a ring-shaped nest drawn as scattered pixels fuses into one
    # piece-sized region (its outline points sit within a 3-cell bridge).
    # HUD-band regions are dropped too, not just the big hazard slabs: an
    # edge-pinned WALL FRAGMENT (e.g. a 7px sliver of the top border) is under
    # the hazard size floor yet is not a piece — left in, it is mistaken for a
    # leg, joins the nearest creature's leg group, and shifts that group's
    # centroid off its body so the consistency check fails and detection aborts
    # (measured on live L1: this alone returned None on the real 2-creature
    # frame). Masking HUD bands out of the piece set is the fix.
    height, width = len(grid), len(grid[0])
    pieces = [
        r
        for r in find_regions(grid, background=bg, gap=2)
        if _MIN_PIECE_SIZE <= r["size"] <= _MAX_PIECE_SIZE
        and not (r["cells"] & hazard)
        and not _is_hud_band(r, height, width)
    ]
    if len(pieces) < 3:
        return None

    by_color: dict[int, list[Region]] = {}
    for r in pieces:
        by_color.setdefault(r["color"], []).append(r)

    # A creature colour has a COMPACT body (high fill) plus at least one other
    # same-colour region (its low-fill target ring). Two thin limb lines share
    # a colour too, but neither is high-fill, so that colour is rejected.
    bodies: list[tuple[Region, Region]] = []  # (body, target)
    body_colors: set[int] = set()
    for color, regs in by_color.items():
        if len(regs) < 2:
            continue
        body = max(regs, key=_fill)
        if _fill(body) < _BODY_FILL:
            continue
        target = min((r for r in regs if r is not body), key=_fill)
        bodies.append((body, target))
        body_colors.add(color)
    if not bodies:
        return None

    # Legs = compact pieces that are NOT a body/target ring colour.
    legs = [r for r in pieces if r["color"] not in body_colors and _fill(r) >= _MIN_LEG_FILL]
    if not legs:
        return None

    def _d2(a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2

    # Assign each leg to the nearest body (self-labelling: a body sits on its
    # own legs' mean).
    groups: dict[int, list[Region]] = {i: [] for i in range(len(bodies))}
    for leg in legs:
        i = min(range(len(bodies)), key=lambda i: _d2(leg["centroid"], bodies[i][0]["centroid"]))
        groups[i].append(leg)

    creatures: list[tuple[list[Cell], Cell]] = []
    for i, (body, target) in enumerate(bodies):
        grp = groups[i]
        if not grp:
            return None  # a body with no legs -> layout not understood; defer
        centroid = (
            sum(r["centroid"][0] for r in grp) / len(grp),
            sum(r["centroid"][1] for r in grp) / len(grp),
        )
        if _d2(centroid, body["centroid"]) > _BODY_CENTROID_TOL2:
            return None  # grouping inconsistent with the body-at-centroid invariant
        leg_centres = [(int(round(r["centroid"][0])), int(round(r["centroid"][1]))) for r in grp]
        target_centre = (int(round(target["centroid"][0])), int(round(target["centroid"][1])))
        creatures.append((leg_centres, target_centre))
    return creatures


def _cluster_regions(regions: list[Region], sep: int) -> list[list[Region]]:
    """Union-find proximity clustering of regions by chebyshev(centroid) <= sep.
    Used to fuse a MULTI-COLOUR body (several adjacent high-fill pieces of
    different colours) into one creature body, colour-blind."""
    n = len(regions)
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i in range(n):
        ci = regions[i]["centroid"]
        for j in range(i + 1, n):
            cj = regions[j]["centroid"]
            if max(abs(ci[0] - cj[0]), abs(ci[1] - cj[1])) <= sep:
                parent[find(i)] = find(j)
    groups: dict[int, list[Region]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(regions[i])
    return list(groups.values())


def _cluster_centre(cluster: list[Region]) -> Cell:
    rs = [r["centroid"][0] for r in cluster]
    cs = [r["centroid"][1] for r in cluster]
    return (int(round(sum(rs) / len(rs))), int(round(sum(cs) / len(cs))))


def _target_score(body_cols: set[int], target_cols: set[int]) -> tuple[int, int]:
    """Rank a (body, target) colour-set match: NESTED first (the target ring's
    colours are a subset of the body's, or vice-versa — the measured signature of
    a real creature ring, since a ring shares its body's colours while a decoy
    fragment carries a foreign colour), then by raw overlap. Returns a sort key
    (higher = better); ``(0, 0)`` when the colours are disjoint (not a candidate)."""
    ov = len(body_cols & target_cols)
    if ov == 0:
        return (0, 0)
    nested = 1 if (body_cols <= target_cols or target_cols <= body_cols) else 0
    return (nested, ov)


def _greedy_target_assign(
    body_colours: list[set[int]], target_centres: list[Cell], target_colours: list[set[int]], body_centres: list[Cell]
) -> list[Cell]:
    """One-to-one body->target assignment, best match first (NESTED colour sets
    before raw overlap — see :func:`_target_score`). A body with no overlapping
    target keeps its own centre (a non-winning placeholder the trial replaces)."""
    pairs: list[tuple[tuple[int, int], int, int]] = []
    for i in range(len(body_colours)):
        for ti in range(len(target_centres)):
            score = _target_score(body_colours[i], target_colours[ti])
            if score != (0, 0):
                pairs.append((score, i, ti))
    pairs.sort(key=lambda p: (-p[0][0], -p[0][1], p[1], p[2]))
    assigned: dict[int, Cell] = {}
    used_t: set[int] = set()
    for _score, i, ti in pairs:
        if i in assigned or ti in used_t:
            continue
        assigned[i] = target_centres[ti]
        used_t.add(ti)
    return [assigned.get(i, body_centres[i]) for i in range(len(body_colours))]


def _analyze_creatures_connectivity(
    grid: Grid, bg: int, hazard: set[Cell]
) -> tuple[list[tuple[list[Cell], Cell]], list[list[Cell]]] | None:
    """Colour-BLIND multi-creature detection for boards the per-colour path fails
    on (bodies MULTI-COLOUR with shared colours). Fill bands separate the pieces:
    bodies (fill >= ``_BODY_FILL``), legs (``[_MIN_LEG_FILL, _BODY_FILL)``), target
    rings (fill < ``_MIN_LEG_FILL``). High-fill body pieces are proximity-clustered
    into N creature bodies (colour-blind); legs are assigned to the nearest body;
    targets are matched to bodies by COLOUR-SET overlap (each creature's ring shares
    its body's colours). Returns ``(creatures, candidates)`` where ``creatures[i] =
    (leg_centres, best_guess_target)`` and ``candidates[i]`` is the ordered list of
    plausible target centres (best-first) for the ambiguous-target trial, or
    ``None`` when < 2 clean body clusters (this fallback is multi-creature only)."""
    height, width = len(grid), len(grid[0])
    pieces = [
        r
        for r in find_regions(grid, background=bg, gap=2)
        if _MIN_PIECE_SIZE <= r["size"] <= _MAX_PIECE_SIZE
        and not (r["cells"] & hazard)
        and not _is_hud_band(r, height, width)
    ]
    bodies_p = [r for r in pieces if _fill(r) >= _BODY_FILL]
    legs_p = [r for r in pieces if _MIN_LEG_FILL <= _fill(r) < _BODY_FILL]
    targets_p = [r for r in pieces if _fill(r) < _MIN_LEG_FILL]
    if len(bodies_p) < 2 or not legs_p:
        return None
    body_clusters = _cluster_regions(bodies_p, _CLUSTER_SEP)
    if len(body_clusters) < 2:
        return None
    n = len(body_clusters)
    body_centres = [_cluster_centre(c) for c in body_clusters]
    body_colours = [{r["color"] for r in c} for c in body_clusters]
    target_clusters = _cluster_regions(targets_p, _CLUSTER_SEP) if targets_p else []
    target_centres = [_cluster_centre(c) for c in target_clusters]
    target_colours = [{r["color"] for r in c} for c in target_clusters]

    groups: list[list[Cell]] = [[] for _ in range(n)]
    for lp in legs_p:
        lc = (int(round(lp["centroid"][0])), int(round(lp["centroid"][1])))
        i = min(range(n), key=lambda k: (lc[0] - body_centres[k][0]) ** 2 + (lc[1] - body_centres[k][1]) ** 2)
        groups[i].append(lc)
    if any(not g for g in groups):
        return None

    best = _greedy_target_assign(body_colours, target_centres, target_colours, body_centres)
    candidates: list[list[Cell]] = []
    for i in range(n):
        scored = [
            (_target_score(body_colours[i], target_colours[ti]), target_centres[ti])
            for ti in range(len(target_clusters))
            if _target_score(body_colours[i], target_colours[ti]) != (0, 0)
        ]
        scored.sort(key=lambda s: (-s[0][0], -s[0][1], s[1]))
        cand = [tc for _score, tc in scored] or [body_centres[i]]
        if best[i] in cand:
            cand.remove(best[i])
        cand.insert(0, best[i])
        candidates.append(cand)
    creatures = [(groups[i], best[i]) for i in range(n)]
    return creatures, candidates


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    """A thin strip spanning most of one axis, OR pinned to a frame edge —
    R11L renders a step-counter column at the frame edge; masking it keeps
    the state key stable across the ticking count."""
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


def _hud_cells(grid: Grid, bg: int) -> set[Cell]:
    height, width = len(grid), len(grid[0])
    cells: set[Cell] = set()
    for region in find_regions(grid, background=bg):
        if _is_hud_band(region, height, width):
            cells |= region["cells"]
    return cells


def _mask_hud(grid: Grid, hud: set[Cell]) -> Grid:
    if not hud:
        return grid
    bg = most_common_color(grid)
    return tuple(
        tuple(bg if (r, c) in hud else grid[r][c] for c in range(len(grid[0])))
        for r in range(len(grid))
    )


def _candidates(grid: Grid, hud: set[Cell], bg: int) -> list[Cell]:
    """Deterministic list of click-target cells: the rounded centroid of
    every salient (non-background, non-HUD) region within the size gate.
    Sorted for reproducibility so the frontier search is deterministic."""
    height, width = len(grid), len(grid[0])
    cells: list[Cell] = []
    seen: set[Cell] = set()
    for region in find_regions(grid, background=bg):
        if _is_hud_band(region, height, width):
            continue
        if not (_MIN_CAND_SIZE <= region["size"] <= _MAX_CAND_SIZE):
            continue
        cr, cc = region["centroid"]
        cell = (int(round(cr)), int(round(cc)))
        if 0 <= cell[0] < height and 0 <= cell[1] < width and cell not in seen and cell not in hud:
            seen.add(cell)
            cells.append(cell)
    return sorted(cells)


class Adapter(GameAdapter):
    """Generic click-frontier exploration over HUD-masked frame-canonical
    states, with the action alphabet bounded to salient region centroids.
    Composed from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        # A 5th bad placement or an exhausted budget ends the attempt in
        # GAME_OVER; restart and keep the learned graph so each life
        # compounds (the board layout didn't change).
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        self._pending_click: Cell | None = None
        self._pending_key: Any | None = None

        # Incrementally-discovered transition graph over masked board states.
        # ``_transitions`` is the flat triple list transition_shortest_path
        # consumes; ``_edges`` is the same graph as an adjacency map kept in
        # step so _nearest_untried's BFS stays linear. ``_cands_at`` records
        # each visited state's own click candidates (a state's alphabet is
        # frame-derived, so routing must remember what was clickable there).
        # All reset on level-up, kept across a mid-level GAME_OVER restart.
        self._transitions: list[tuple[Any, Cell, Any]] = []
        self._edges: dict[Any, dict[Cell, Any]] = {}
        self._tried_from: dict[Any, set[Cell]] = {}
        self._cands_at: dict[Any, list[Cell]] = {}

        # Centroid-assembly PLANNER state (tried once per level before the
        # explorer). ``_plan`` is a queue of (kind, cell) clicks — a "select"
        # (click a leg to select it) then a "place" (click the destination,
        # which animates); the place step is re-issued until the masked board
        # settles. ``_plan_attempted`` gates it to one shot per level.
        self._plan: list[tuple[str, Cell]] | None = None
        self._plan_attempted = False
        self._plan_place_issued = False
        self._plan_last_masked: Grid | None = None
        self._plan_place_count = 0
        # FROZEN-TARGET controller for MULTI-creature levels. The one-shot plan
        # and its continuous-rebuild predecessor both chased MOVING goals:
        # ``points_with_centroid`` recomputed from CURRENT leg positions every
        # rebuild shifted each leg's destination cycle to cycle, so legs never
        # converged. Fix: when ≥2 creatures are detected, compute each creature's
        # FINAL leg configuration ONCE (the fixed-point: cells whose floor
        # centroid is the nest, all placeable) and HOLD it; re-detection then only
        # maps CURRENT legs to those FROZEN cells and drives the next unplaced leg
        # to its frozen cell, never disturbing a leg already on target. Single-
        # creature levels (L0) keep the one-shot path byte-identical.
        self._multi = False
        # Per-creature INITIAL (leg_centres, target_centre), captured once at
        # build; the strike-aware planner drives the current legs from here.
        self._frozen_creatures: list[tuple[list[Cell], Cell]] = []
        # Each creature's BODY/TARGET colour, used to match current legs to their
        # creature by NEAREST BODY (legs themselves are NOT creature-coloured —
        # measured: every leg renders as colour 3, or colour 0 while selected — so
        # a body, a same-colour high-fill piece, is the identity anchor). No colour
        # is hardcoded; it is read from the frame per level.
        self._frozen_colors: list[int] = []
        self._frozen_moves = 0
        # STRIKE-AWARE move plan (R85). Measured on the live L1: moving a leg
        # re-centres its body to the legs' new mean, and if that BODY position
        # overlaps the in-play ``defgjl`` obstacle the engine fires a STRIKE and
        # REVERTS the move (5 strikes → game over). The frozen greedy driver only
        # modelled leg-vs-wall collision, so its minimum-displacement moves drove
        # the body through the obstacle and thrashed. The obstacle is a large
        # non-background region, so it is already in the generic ``_hazard_cells``
        # set — reused here as a BODY hazard (colour-agnostic, no per-level
        # constant). Per creature we search an ORDERED sequence of single-leg
        # moves (best-first, cost = #moves) where every intermediate body centroid
        # avoids that hazard set, landing the body overlapping its target. The two
        # creatures' plans are independent (one creature's leg never moves the
        # other's body), so they concatenate. ``_moves`` is that ordered plan;
        # ``None`` means "needs (re)building". ``_learned_haz`` accumulates body
        # cells that struck despite the frame prior (part of the obstacle renders
        # as other colours), refining the model online within the 5-strike budget.
        self._moves: list[tuple[Cell, Cell, Cell]] | None = None
        self._move_idx = 0
        self._learned_haz: set[Cell] = set()
        # SPECULATIVE-TARGET-TRIAL (R87) for boards detected via the colour-blind
        # fallback, where a creature's target ring is not uniquely identifiable
        # from colour/geometry (L3: `orrqlj`'s two unique colours split across
        # clusters → ≥4 equally-plausible targets). Rather than guess, ACT: place
        # the unambiguous creatures, then drive the ambiguous creature's body to
        # each candidate target IN TURN until the engine's own win fires ("the win
        # condition is the missing sensor"). ``_target_candidates[i]`` is creature
        # i's ordered candidate target centres; ``_cand_idx[i]`` the one currently
        # in play; ``_trial_idle`` counts settled frames spent with all legs placed
        # but no level-up, before advancing to the next candidate.
        self._use_trial = False
        self._target_candidates: list[list[Cell]] | None = None
        self._cand_idx: list[int] = []
        self._trial_idle = 0
        # Geometry measured once at build from the frame: the piece (leg/body)
        # half-extent and each creature's target bbox — used by the planner's
        # placeable / body-safe / overlap tests. No hardcoded size: read from the
        # detected regions.
        self._piece_half = 2
        self._cr_target_box: list[tuple[int, int, int, int]] = []
        # In-flight move's predicted body centroid (for the learned-hazard update
        # when a placement unexpectedly does not fire).
        self._fc_pred_body: Cell | None = None
        # In-flight single-leg move: select the leg (click a filled cell of it,
        # retrying alternates on a miss) then place at its frozen cell (re-issued
        # until the drag settles, then the outcome is verified).
        self._fc_phase: str | None = None  # None | "select" | "place"
        self._fc_leg_pre: Cell | None = None
        self._fc_dest: Cell | None = None
        self._fc_select_cells: list[Cell] = []
        self._fc_retry = 0
        self._fc_place_issued = False
        self._fc_place_masked: Grid | None = None
        self._fc_place_count = 0
        # Per-placement trajectory log (intended dest vs observed move) — banked
        # for the reopen note when convergence stalls. Printed only under the
        # R11L_DEBUG env flag; never in a normal scored run.
        self._fc_trajectory: list[tuple[Cell, Cell, bool]] = []
        # Creature signature (per-creature leg counts) held while waiting for a
        # new level's entry animation to settle, plus how many consecutive
        # frames it has held.
        self._settle_ref: tuple[int, ...] | None = None
        self._settle_count = 0

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._on_restart()
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._pending_click = None
            self._pending_key = None
            self._levels_seen = -1
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._on_level_up(levels)

        self._step += 1
        bg = most_common_color(grid)
        hud = _hud_cells(grid, bg)
        masked = _mask_hud(grid, hud)
        cur_key = canonical_key(masked, mode="exact")
        self._observe_result(cur_key)

        # Centroid-assembly planner first (one shot per level); when it has no
        # plan or is exhausted it returns None and the generic explorer runs.
        planned = self._planner_step(grid, bg, masked)
        if planned is not None:
            self._pending_click = None  # planner clicks are not explorer edges
            self._pending_key = None
            return click_action(x=planned[1], y=planned[0])

        cands = self._cands_at.get(cur_key)
        if cands is None:
            cands = _candidates(grid, hud, bg)
            self._cands_at[cur_key] = cands
        if not cands:
            # No salient click target this frame -- nothing a click policy
            # can compose from. Idle with a reset rather than crash.
            self._pending_click = None
            self._pending_key = None
            return reset_action()

        cell = self._decide(cur_key, cands)
        self._pending_click = cell
        self._pending_key = cur_key
        return click_action(x=cell[1], y=cell[0])

    # ── level / restart bookkeeping ─────────────────────────────────────

    def _on_level_up(self, levels: int) -> None:
        self._levels_seen = levels
        self._pending_click = None
        self._pending_key = None
        self._transitions = []
        self._edges = {}
        self._tried_from = {}
        self._cands_at = {}
        self._plan = None
        self._plan_attempted = False
        self._plan_place_issued = False
        self._plan_last_masked = None
        self._plan_place_count = 0
        self._settle_ref = None
        self._settle_count = 0
        self._multi = False
        self._frozen_creatures = []
        self._frozen_colors = []
        self._frozen_moves = 0
        self._moves = None
        self._move_idx = 0
        self._learned_haz = set()
        self._piece_half = 2
        self._cr_target_box = []
        self._use_trial = False
        self._target_candidates = None
        self._cand_idx = []
        self._trial_idle = 0
        self._reset_move()
        self._fc_trajectory = []

    def _reset_move(self) -> None:
        self._fc_phase = None
        self._fc_leg_pre = None
        self._fc_dest = None
        self._fc_pred_body = None
        self._fc_select_cells = []
        self._fc_retry = 0
        self._fc_place_issued = False
        self._fc_place_masked = None
        self._fc_place_count = 0

    def _on_restart(self) -> None:
        self._pending_click = None
        self._pending_key = None
        # A restart on a SINGLE-creature level means a placement went wrong (a
        # strike); abandon the one-shot plan and let the explorer take over. On a
        # MULTI-creature level the frozen destinations are board-invariant, so
        # keep them and resume driving legs toward the same cells (each life
        # compounds); only the in-flight move is reset.
        if self._multi:
            # A multi-creature restart means the 5-strike budget was spent; the
            # learned body-hazard cells are kept (each life refines the model),
            # but the ordered plan is rebuilt from the revived board.
            self._moves = None
            self._move_idx = 0
            self._reset_move()
            return
        self._plan = None
        self._plan_attempted = True

    # ── centroid-assembly planner ───────────────────────────────────────

    def _build_plan(self, grid: Grid, bg: int) -> list[tuple[str, Cell]] | None:
        """Detect every creature and compute a select→place click plan that
        lands each body (its legs' centroid) on its target nest, avoiding
        hazards. Returns ``None`` when no clean creature is found (the explorer
        then runs)."""
        hazard = _hazard_cells(grid, bg)
        creatures = _analyze_creatures(grid, bg, hazard)
        if not creatures:
            return None
        self._multi = len(creatures) >= 2
        height, width = len(grid), len(grid[0])

        def is_free(cell: Cell, radius: int) -> bool:
            # Require a clear BACKGROUND neighbourhood, not merely non-hazard:
            # a leg sprite has extent, and a cell on a nest / another marker
            # overlaps it. Demanding empty bg pushes the legs to well-separated
            # open cells (clear of the nests and of each other), avoiding the
            # transit collisions that trigger the game's strikes. The clearance
            # RADIUS is relaxed per creature (below) — the full half-extent is
            # preferred, but a target wedged against a wall (a deep level's
            # 3-leg nest) admits no radius-2-clear arrangement, so a tighter
            # radius-1 fallback keeps such a creature solvable.
            r, c = cell
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    rr, cc = r + dr, c + dc
                    if not (0 <= rr < height and 0 <= cc < width):
                        return False
                    if grid[rr][cc] != bg or (rr, cc) in hazard:
                        return False
            return True

        plan: list[tuple[str, Cell]] = []
        for leg_centres, target in creatures:
            # Prefer the full clearance (radius 2); relax to radius 1 only when
            # the target's neighbourhood is too tight for it. Radius 2 first
            # keeps every already-solvable creature (e.g. L0's) byte-identical —
            # the fallback only fires where the strict radius returns nothing.
            dests = None
            for radius in (_LEG_CLEAR_RADIUS, 1):
                dests = points_with_centroid(
                    target, len(leg_centres), lambda cell, _r=radius: is_free(cell, _r), current=leg_centres
                )
                if dests is not None:
                    break
            if dests is None:
                return None
            for leg, dest in zip(leg_centres, dests):
                if tuple(leg) == tuple(dest):
                    continue  # leg already positioned; no click needed
                plan.append(("select", leg))
                plan.append(("place", dest))
        return plan or None

    def _planner_step(self, grid: Grid, bg: int, masked: Grid) -> Cell | None:
        """Emit the next planner click, or ``None`` to defer to the explorer.

        The plan is built once per level, but only once the level's own
        entry/win animation has SETTLED (two identical masked frames) — a plan
        built on the transition frame would see the previous level's leftover
        pieces and mis-place. While waiting, a hazard cell is clicked (a
        refused no-op) so the animation can advance without disturbing the
        board. A ``select`` click is instant (issued once, advance next call);
        a ``place`` click animates, so it is re-issued until the masked board
        settles, then the plan advances."""
        if self._plan is None and not self._plan_attempted:
            # A new level's legs animate into place over many frames (the
            # detected leg count oscillates), so gate plan-building on the
            # CREATURE SIGNATURE (per-creature leg counts) being non-empty and
            # unchanged for a few consecutive frames — a raw frame-equality
            # settle stabilises on transient mid-animation frames. While
            # waiting, click a hazard cell (a refused no-op).
            sig = self._creature_signature(grid, bg)
            if sig is not None and sig == self._settle_ref:
                self._settle_count += 1
            else:
                self._settle_ref = sig
                self._settle_count = 0
            if sig is None or self._settle_count < _SETTLE_FRAMES:
                return self._safe_wait_cell(grid, bg)
            self._plan_attempted = True
            # Route on creature count: ≥2 creatures use the FROZEN-TARGET
            # controller (compute-once destinations); a single creature keeps the
            # byte-identical one-shot plan (L0).
            hz = _hazard_cells(grid, bg)
            bycolor = _analyze_creatures_bycolor(grid, bg, hz)
            conn = _analyze_creatures_connectivity(grid, bg, hz) if bycolor is None else None
            if bycolor is not None and len(bycolor) >= 2:
                # The proven per-colour path (L0-L2): fixed per-creature targets,
                # no trial.
                self._multi = True
                self._use_trial = False
                self._target_candidates = None
                self._build_frozen(grid, bg, bycolor)
            elif conn is not None and len(conn[0]) >= 2:
                # Colour-blind fallback (L3+): fixed leg groups + AMBIGUOUS targets
                # resolved by the speculative trial.
                creatures, candidates = conn
                self._multi = True
                self._use_trial = True
                self._target_candidates = candidates
                self._cand_idx = [0] * len(creatures)
                self._trial_idle = 0
                self._build_frozen(grid, bg, creatures)
            else:
                self._plan = self._build_plan(grid, bg)
                self._plan_place_issued = False
                self._plan_last_masked = None
                self._plan_place_count = 0

        if self._multi:
            return self._frozen_step(grid, bg, masked)

        if not self._plan:
            return None

        kind, cell = self._plan[0]
        if kind == "select":
            # Validate against the CURRENT board: if the leg we planned to
            # select is no longer there, the plan was built on a since-changed
            # frame (e.g. a level-entry animation that held the previous
            # level's pieces), so discard it and rebuild once settled.
            if not self._leg_present(grid, bg, cell):
                self._plan = None
                self._plan_attempted = False
                self._settle_ref = None
                return self._safe_wait_cell(grid, bg)
            self._plan.pop(0)
            self._plan_place_issued = False
            self._plan_last_masked = None
            return cell
        # place: settled when the masked board matches the previous call's.
        if self._plan_place_issued and masked == self._plan_last_masked:
            self._plan.pop(0)
            self._plan_place_issued = False
            self._plan_last_masked = None
            self._plan_place_count = 0
            return self._planner_step(grid, bg, masked)
        # A placement that never settles means the board changed under the plan
        # (a level transition, or the leg was not where the plan assumed) —
        # abandon and rebuild once settled rather than re-clicking forever.
        self._plan_place_count += 1
        if self._plan_place_count > _PLACE_STUCK_LIMIT:
            self._plan = None
            self._plan_attempted = False
            self._settle_ref = None
            self._plan_place_count = 0
            return self._safe_wait_cell(grid, bg)
        self._plan_place_issued = True
        self._plan_last_masked = masked
        return cell

    def _safe_wait_cell(self, grid: Grid, bg: int) -> Cell | None:
        """A hazard cell whose click the game refuses (a no-op) — used to burn
        a frame while a level animation settles, without disturbing the board.
        ``None`` (defer to the explorer) if the board has no hazard region."""
        hazard = _hazard_cells(grid, bg)
        return min(hazard) if hazard else None

    def _creature_signature(self, grid: Grid, bg: int) -> tuple[int, ...] | None:
        """A hashable summary of the detected creatures (sorted per-creature leg
        counts), or ``None`` when no creature is found. Used to detect when a
        new level's leg-spawn animation has settled (the signature stops
        changing) before committing to a plan."""
        creatures = _analyze_creatures(grid, bg, _hazard_cells(grid, bg))
        if not creatures:
            return None
        return tuple(sorted(len(legs) for legs, _t in creatures))

    def _leg_present(self, grid: Grid, bg: int, cell: Cell) -> bool:
        """Whether a detected leg currently sits near ``cell`` — the freshness
        check that catches a plan built on a since-changed (transition) frame."""
        hazard = _hazard_cells(grid, bg)
        creatures = _analyze_creatures(grid, bg, hazard)
        if not creatures:
            return False
        for leg_centres, _target in creatures:
            for lc in leg_centres:
                if (lc[0] - cell[0]) ** 2 + (lc[1] - cell[1]) ** 2 <= _BODY_CENTROID_TOL2:
                    return True
        return False

    # ── strike-aware move planner (multi-creature) ──────────────────────

    @staticmethod
    def _box_clear(cell: Cell, half: int, blocked: set[Cell], height: int, width: int, require_inbounds: bool) -> bool:
        """Whether the ``(2*half+1)`` footprint box centred at ``cell`` touches no
        cell of ``blocked``. ``require_inbounds`` also rejects a box clipping the
        board edge — set for LEG placement (the engine refuses a leg that clips the
        arena wall, and an edge-clipped leg is unreliable) and clear for the BODY
        (the body can sit against the edge; only obstacle overlap strikes)."""
        r, c = cell
        for dr in range(-half, half + 1):
            rr = r + dr
            for dc in range(-half, half + 1):
                cc = c + dc
                if not (0 <= rr < height and 0 <= cc < width):
                    if require_inbounds:
                        return False
                    continue
                if (rr, cc) in blocked:
                    return False
        return True

    def _measure_geometry(self, grid: Grid, bg: int, hazard: set[Cell]) -> None:
        """Measure, from the frame, the piece half-extent (legs and bodies are the
        same small marker) and each creature's TARGET bbox — the planner's overlap
        and footprint sizes, read from detected regions, never hardcoded."""
        legs = self._detect_legs(grid, bg, hazard)
        half = 2
        if legs:
            spans = [max(r["bbox"][2] - r["bbox"][0], r["bbox"][3] - r["bbox"][1]) for r in legs]
            half = max(1, max(spans) // 2)
        self._piece_half = half
        # Only piece-sized, non-hazard, non-HUD regions are candidates for the
        # target ring — the giant wall / obstacle regions are large and must not
        # be matched (matching the obstacle gives a huge bbox that any body
        # trivially "overlaps", a false win goal).
        height, width = len(grid), len(grid[0])
        pieces = [
            r
            for r in find_regions(grid, background=bg, gap=2)
            if _MIN_PIECE_SIZE <= r["size"] <= _MAX_PIECE_SIZE
            and not (r["cells"] & hazard)
            and not _is_hud_band(r, height, width)
        ]
        self._cr_target_box = []
        for _legs, target in self._frozen_creatures:
            if self._use_trial:
                # Colour-blind targets are cluster CENTRES of scattered ring
                # fragments, not clean regions, so the nearest-region box would be
                # a lone fragment. Use a fixed tolerance box: a body centroid within
                # ``_TRIAL_TARGET_TOL`` of the centre overlaps the ring (engine
                # overlap tolerance ≈ body_half + target_half).
                tr, tc = target
                box = (tr - _TRIAL_TARGET_TOL, tc - _TRIAL_TARGET_TOL, tr + _TRIAL_TARGET_TOL, tc + _TRIAL_TARGET_TOL)
            else:
                box = self._region_box_near(pieces, target)
            self._cr_target_box.append(box)

    @staticmethod
    def _region_box_near(regions: list[Region], centre: Cell) -> tuple[int, int, int, int]:
        """The bbox of the region whose centroid is nearest ``centre`` — used to
        recover the TARGET nest's extent (the frozen target is stored as a centre
        only). Falls back to a unit box when no region is found."""
        best: Region | None = None
        best_d: float | None = None
        for r in regions:
            cr, cc = r["centroid"]
            d = (cr - centre[0]) ** 2 + (cc - centre[1]) ** 2
            if best_d is None or d < best_d:
                best_d = d
                best = r
        if best is None:
            return (centre[0] - 1, centre[1] - 1, centre[0] + 1, centre[1] + 1)
        r0, c0, r1, c1 = best["bbox"]
        return (int(r0), int(c0), int(r1), int(c1))

    def _build_frozen(self, grid: Grid, bg: int, creatures: list[tuple[list[Cell], Cell]]) -> None:
        """Capture the multi-creature level once: initial legs, target centre, the
        creature-identity body colour, and the frame geometry the strike-aware
        planner needs. The move plan itself is built lazily (and rebuilt on a
        learned strike) in :meth:`_frozen_step`."""
        hazard = _hazard_cells(grid, bg)
        self._frozen_creatures = [
            ([(int(r), int(c)) for r, c in legs], (int(target[0]), int(target[1])))
            for legs, target in creatures
        ]
        # Creature identity colour = the colour of the BODY nearest this
        # creature's leg centroid (a body sits at its legs' mean). Sampling the
        # target ring's centroid instead reads background — the ring is hollow —
        # so the body must be matched by position, not a centre pixel. Used to
        # re-find the creature's body each cycle for leg→creature grouping.
        bodies = self._detect_bodies(grid, bg, hazard)
        self._frozen_colors = []
        for legs, _t in self._frozen_creatures:
            cr = sum(leg[0] for leg in legs) / len(legs)
            cc = sum(leg[1] for leg in legs) / len(legs)
            if bodies:
                col = min(bodies, key=lambda c: (bodies[c][0] - cr) ** 2 + (bodies[c][1] - cc) ** 2)
            else:
                col = -1
            self._frozen_colors.append(col)
        self._measure_geometry(grid, bg, hazard)
        self._moves = None
        self._move_idx = 0
        self._frozen_moves = 0

    @staticmethod
    def _cheb(a: Cell, b: Cell) -> int:
        return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

    def _move_candidates(self, grid: Grid, hazard: set[Cell], target_centre: Cell, avoid: set[Cell]) -> list[Cell]:
        """Leg-destination candidates for the planner: a coarse wall/obstacle-free
        grid over the board plus a fine ring around the creature's target, so a
        precise final centroid is reachable. Each candidate's leg footprint is
        clear of the hazard regions and in bounds, and at least ``_LEG_SEP`` from
        every ``avoid`` cell (another creature's legs — kept separable)."""
        height, width = len(grid), len(grid[0])
        half = self._piece_half

        def ok(cell: Cell) -> bool:
            if not self._box_clear(cell, half, hazard, height, width, True):
                return False
            return all(self._cheb(cell, a) >= _LEG_SEP for a in avoid)

        out: list[Cell] = []
        seen: set[Cell] = set()
        for r in range(0, height, 2):
            for c in range(0, width, 2):
                cell = (r, c)
                if cell not in seen and ok(cell):
                    seen.add(cell)
                    out.append(cell)
        tr, tc = target_centre
        for dr in range(-8, 9):
            for dc in range(-8, 9):
                cell = (tr + dr, tc + dc)
                if cell not in seen and ok(cell):
                    seen.add(cell)
                    out.append(cell)
        return out

    def _plan_creature(
        self, grid: Grid, bg: int, body_haz: set[Cell], legs: list[Cell], ci: int, avoid: set[Cell]
    ) -> tuple[list[tuple[Cell, Cell, Cell]], tuple[Cell, ...]] | None:
        """Best-first search of an ORDERED single-leg-move sequence that lands
        creature ``ci``'s body (its legs' centroid) overlapping its target while
        EVERY intermediate body centroid stays clear of the body hazard (wall +
        obstacle) and every leg stays ``_LEG_SEP`` from its siblings and the
        ``avoid`` legs. Returns ``(ordered (from, to, body_after) moves, final leg
        config)``, or ``None`` if none is found."""
        height, width = len(grid), len(grid[0])
        half = self._piece_half
        target_centre = self._frozen_creatures[ci][1]
        target_box = self._cr_target_box[ci]
        cands = self._move_candidates(grid, _hazard_cells(grid, bg), target_centre, avoid)
        n = len(legs)
        if n == 0:
            return None
        start = tuple((int(r), int(c)) for r, c in legs)

        def centroid(cfg: tuple[Cell, ...]) -> Cell:
            return (sum(p[0] for p in cfg) // n, sum(p[1] for p in cfg) // n)

        def heuristic(cfg: tuple[Cell, ...]) -> int:
            b = centroid(cfg)
            return abs(b[0] - target_centre[0]) + abs(b[1] - target_centre[1])

        r0, c0, r1, c1 = target_box

        def is_goal(cfg: tuple[Cell, ...]) -> bool:
            # Require the body CENTROID inside the target ring's bbox (not merely a
            # bbox-touch): a boundary sliver leaves only a 1-cell corner overlap
            # that is not a reliable pixel collision, so the engine win does not
            # fire (measured on pumlzd). A centroid over the ring guarantees a
            # solid overlap. The body must also be strike-clear.
            b = centroid(cfg)
            return (
                r0 <= b[0] <= r1
                and c0 <= b[1] <= c1
                and self._box_clear(b, half, body_haz, height, width, False)
            )

        parents: dict[tuple[Cell, ...], tuple[tuple[Cell, ...], int, Cell] | None] = {start: None}
        pq: list[tuple[int, int, int, tuple[Cell, ...]]] = [(heuristic(start), 0, 0, start)]
        tie = 1
        expand = 0
        goal_cfg: tuple[Cell, ...] | None = None
        while pq and expand < _ASTAR_MAX_EXPAND:
            _, cost, _, cfg = heapq.heappop(pq)
            if is_goal(cfg):
                goal_cfg = cfg
                break
            expand += 1
            for nxt, moved_leg, dest in self._neighbours(cfg, cands, n, centroid, half, body_haz, height, width):
                if nxt not in parents:
                    parents[nxt] = (cfg, moved_leg, dest)
                    heapq.heappush(pq, (cost + 1 + heuristic(nxt), cost + 1, tie, nxt))
                    tie += 1
        if goal_cfg is None:
            return None
        path: list[tuple[Cell, Cell, Cell]] = []
        cur = goal_cfg
        while parents[cur] is not None:
            prev, moved_leg, dest = parents[cur]  # type: ignore[misc]
            path.append((prev[moved_leg], dest, centroid(cur)))
            cur = prev
        path.reverse()
        return path, goal_cfg

    def _neighbours(
        self,
        cfg: tuple[Cell, ...],
        cands: list[Cell],
        n: int,
        centroid: Any,
        half: int,
        body_haz: set[Cell],
        height: int,
        width: int,
    ):
        """Yield ``(next_cfg, moved_leg_index, dest)`` for every single-leg
        relocation to a candidate cell whose resulting body centroid is
        hazard-clear (a strike-free move) and that stays ``_LEG_SEP`` from this
        creature's other legs (so the placed legs remain individually detectable)."""
        for i in range(n):
            for dest in cands:
                if dest == cfg[i]:
                    continue
                if any(self._cheb(dest, cfg[j]) < _LEG_SEP for j in range(n) if j != i):
                    continue
                nxt = cfg[:i] + (dest,) + cfg[i + 1 :]
                if self._box_clear(centroid(nxt), half, body_haz, height, width, False):
                    yield nxt, i, dest

    def _detect_bodies(self, grid: Grid, bg: int, hazard: set[Cell]) -> dict[int, Cell]:
        """Each creature's BODY centre keyed by colour: the compact HIGH-FILL
        piece of a creature colour (measured L1: bodies fill ~0.8 at colour 12/15,
        while legs are colour 0/3 at ~0.48 and target rings ~0.24). Used to match
        current legs to their creature by nearest body, robustly through the
        body-follows-centroid motion (the body is always rendered)."""
        height, width = len(grid), len(grid[0])
        out: dict[int, Cell] = {}
        for r in find_regions(grid, background=bg, gap=2):
            if not (_MIN_PIECE_SIZE <= r["size"] <= _MAX_PIECE_SIZE):
                continue
            if (r["cells"] & hazard) or _is_hud_band(r, height, width):
                continue
            if _fill(r) >= _BODY_FILL:
                out.setdefault(r["color"], self._leg_centre(r))
        return out

    def _detect_legs(self, grid: Grid, bg: int, hazard: set[Cell]) -> list[Region]:
        """The compact clickable LEG regions on the current board — the same
        piece/body/leg discrimination :func:`_analyze_creatures` uses, but WITHOUT
        the per-creature grouping/consistency check, so it stays robust mid-
        arrangement (when a body sits momentarily off its legs' centroid)."""
        height, width = len(grid), len(grid[0])
        pieces = [
            r
            for r in find_regions(grid, background=bg, gap=2)
            if _MIN_PIECE_SIZE <= r["size"] <= _MAX_PIECE_SIZE
            and not (r["cells"] & hazard)
            and not _is_hud_band(r, height, width)
        ]
        by_color: dict[int, list[Region]] = {}
        for r in pieces:
            by_color.setdefault(r["color"], []).append(r)
        body_colors: set[int] = set()
        for color, regs in by_color.items():
            if len(regs) < 2:
                continue
            if _fill(max(regs, key=_fill)) >= _BODY_FILL:
                body_colors.add(color)
        return [r for r in pieces if r["color"] not in body_colors and _fill(r) >= _MIN_LEG_FILL]

    @staticmethod
    def _leg_centre(region: Region) -> Cell:
        return (int(round(region["centroid"][0])), int(round(region["centroid"][1])))

    def _leg_click_cells(self, region: Region) -> list[Cell]:
        """Select-click candidates for one leg: its rounded centroid first, then
        the nearest FILLED cells of the region — the alternates tried on a miss
        (a non-convex leg's centroid can land on a background pixel)."""
        cr, cc = region["centroid"]
        out: list[Cell] = [(int(round(cr)), int(round(cc)))]
        for p in sorted(region["cells"], key=lambda q: (q[0] - cr) ** 2 + (q[1] - cc) ** 2):
            if p not in out:
                out.append((int(p[0]), int(p[1])))
            if len(out) >= _MAX_SELECT_RETRY + 1:
                break
        return out

    def _log_traj(self, moved: bool) -> None:
        if self._fc_dest is None or self._fc_leg_pre is None:
            return
        self._fc_trajectory.append((self._fc_dest, self._fc_leg_pre, moved))
        if os.environ.get("R11L_DEBUG"):
            import sys

            print(
                f"[r11l] move#{self._frozen_moves} leg{self._fc_leg_pre} "
                f"-> dest{self._fc_dest} body{self._fc_pred_body} moved={moved} "
                f"learned_haz={len(self._learned_haz)} move_idx={self._move_idx}",
                file=sys.stderr,
                flush=True,
            )

    def _frozen_issue_select(self) -> Cell:
        """Emit the next select click (a filled cell of the target leg) and move
        to the place phase; a fresh place-settle window opens."""
        cell = self._fc_select_cells.pop(0)
        self._fc_phase = "place"
        self._fc_place_issued = False
        self._fc_place_masked = None
        self._fc_place_count = 0
        return cell

    def _build_move_plan(self, grid: Grid, bg: int, leg_regions: list[Region]) -> list[tuple[Cell, Cell, Cell]] | None:
        """Assemble the whole level's ordered strike-free move list: group the
        CURRENT legs to their creature by nearest body (fallback target), then
        concatenate each creature's :meth:`_plan_creature` sequence (the plans are
        independent — one creature's leg never moves another's body). ``None`` when
        detection is inconsistent or any creature has no strike-free plan."""
        hazard = _hazard_cells(grid, bg)
        body_haz = hazard | self._learned_haz
        bodies = self._detect_bodies(grid, bg, hazard)
        n_cr = len(self._frozen_creatures)
        anchors = [bodies.get(self._frozen_colors[ci], self._frozen_creatures[ci][1]) for ci in range(n_cr)]
        groups: list[list[Cell]] = [[] for _ in range(n_cr)]
        for r in leg_regions:
            lc = self._leg_centre(r)
            ci = min(range(n_cr), key=lambda i: (lc[0] - anchors[i][0]) ** 2 + (lc[1] - anchors[i][1]) ** 2)
            groups[ci].append(lc)
        # Plan creatures in sequence, each avoiding the FINAL legs of already-planned
        # creatures plus the CURRENT legs of not-yet-planned ones, so no leg lands
        # adjacent to another (which would fuse them under region detection and
        # break selection). The plans stay independent for execution.
        moves: list[tuple[Cell, Cell, Cell]] = []
        placed: list[Cell] = []
        for ci in range(n_cr):
            legs = groups[ci]
            if len(legs) != len(self._frozen_creatures[ci][0]):
                return None  # detection churn — wait a frame and rebuild
            avoid = set(placed)
            for cj in range(n_cr):
                if cj != ci:
                    avoid.update(groups[cj])
            result = self._plan_creature(grid, bg, body_haz, legs, ci, avoid)
            if result is None:
                return None
            seq, final_cfg = result
            moves.extend(seq)
            placed.extend(final_cfg)
        return moves

    def _advance_trial(self, grid: Grid, bg: int, masked: Grid) -> Cell | None:
        """Speculative-target-trial step (colour-blind path only). Called once all
        planned legs are placed but no win registered. Idles a few settled frames
        (the win may still be animating), then re-targets the first creature with an
        untried candidate to its NEXT candidate and rebuilds — driving that
        creature's body to the new target. Returns the next click, or ``None`` when
        still idling or when every candidate is exhausted (give up → the caller
        idles / the explorer takes over)."""
        self._trial_idle += 1
        if self._trial_idle < _TRIAL_IDLE_FRAMES:
            return None  # give the win a chance to register before re-targeting
        ci = None
        for i in range(len(self._frozen_creatures)):
            if self._target_candidates and self._cand_idx[i] + 1 < len(self._target_candidates[i]):
                ci = i
                break
        if ci is None:
            return None  # all candidates tried — the level is genuinely unreached
        self._cand_idx[ci] += 1
        new_target = self._target_candidates[ci][self._cand_idx[ci]]  # type: ignore[index]
        legs, _old = self._frozen_creatures[ci]
        self._frozen_creatures[ci] = (legs, new_target)
        self._cr_target_box[ci] = (
            new_target[0] - _TRIAL_TARGET_TOL,
            new_target[1] - _TRIAL_TARGET_TOL,
            new_target[0] + _TRIAL_TARGET_TOL,
            new_target[1] + _TRIAL_TARGET_TOL,
        )
        self._moves = None  # rebuild: already-placed creatures re-plan to 0 moves
        self._move_idx = 0
        self._trial_idle = 0
        self._reset_move()
        return self._frozen_step(grid, bg, masked)

    def _frozen_step(self, grid: Grid, bg: int, masked: Grid) -> Cell | None:
        """One controller click, driven by the strike-aware move plan. Builds the
        ordered plan once (rebuilds on a learned strike), then executes the next
        move as select(current leg)→place(dest). A move whose leg does not actually
        shift (a mispredicted body strike, or a wall refusal) learns its predicted
        body centroid as a hazard and forces a replan. Only detected leg pieces are
        ever selected, so a body is never dragged. Returns ``None`` to defer to the
        explorer when no strike-free plan exists or the attempt budget is spent."""
        hazard = _hazard_cells(grid, bg)
        leg_regions = self._detect_legs(grid, bg, hazard)

        def near(a: Cell, b: Cell) -> bool:
            return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 <= _BODY_CENTROID_TOL2

        if self._fc_phase == "place":
            legs = [self._leg_centre(r) for r in leg_regions]
            return self._frozen_place(grid, bg, masked, legs, near)

        if self._moves is None:
            self._moves = self._build_move_plan(grid, bg, leg_regions)
            self._move_idx = 0
            if self._moves is None:
                # Detection not settled / no plan yet — idle a frame and retry.
                return self._safe_wait_cell(grid, bg)
        if not self._moves:
            return None  # no strike-free plan at all → defer to the explorer

        # Moves are executed STRICTLY in order from the config the plan was built
        # on (each verified before advancing), so no "already-satisfied" skip is
        # needed — and a skip keyed on "any leg near this dest" would wrongly drop
        # a move whose OWN leg is elsewhere but another leg happens to sit near the
        # destination (measured: it left a creature one leg short of its target).
        if self._move_idx >= len(self._moves):
            # All planned moves done. For the per-colour path both bodies are on
            # their (known) targets → WIN is imminent; idle until it registers.
            # For the colour-blind TRIAL path, if no win registers after a few
            # settled frames, the ambiguous creature's current candidate target was
            # wrong → advance it to the next candidate and rebuild (the level does
            # not advance on a wrong target, so this idle-then-advance IS the
            # "engine win as the missing sensor" loop).
            if self._use_trial:
                trial = self._advance_trial(grid, bg, masked)
                if trial is not None:
                    return trial
            return self._safe_wait_cell(grid, bg)
        if self._frozen_moves >= _MAX_FROZEN_MOVES:
            return None  # too many attempts → defer to the explorer

        from_cell, dest, pred_body = self._moves[self._move_idx]
        if not leg_regions:
            self._moves = None
            return self._safe_wait_cell(grid, bg)
        region = min(leg_regions, key=lambda r: near_d2(self._leg_centre(r), from_cell))
        if near_d2(self._leg_centre(region), from_cell) > _BODY_CENTROID_TOL2:
            # No leg near the planned from-cell (the board drifted under the plan)
            # — rebuild from the current board.
            self._moves = None
            return self._safe_wait_cell(grid, bg)
        # SELECT by clicking the EXACT planned from-cell first: the engine selects
        # the leg whose bbox contains the click, so this grabs the intended leg even
        # when the detected region centroid drifted (e.g. two legs a hair over the
        # separation floor fuse into one region whose centroid sits between them, in
        # NEITHER leg's bbox). The region's own filled cells follow as retries.
        self._fc_leg_pre = from_cell
        self._fc_dest = dest
        self._fc_pred_body = pred_body
        self._fc_select_cells = [from_cell] + [c for c in self._leg_click_cells(region) if c != from_cell]
        self._fc_retry = 0
        return self._frozen_issue_select()

    def _frozen_place(
        self, grid: Grid, bg: int, masked: Grid, legs: list[Cell], near: Any
    ) -> Cell | None:
        """The place phase: click the destination, re-issued until the drag
        settles, then verify the intended leg reached it. On success advance the
        plan; on a persistent miss retry an alternate select cell, then learn the
        predicted body centroid as a hazard (a mispredicted strike, since part of
        the obstacle renders as other colours) and replan."""
        if self._fc_place_issued and masked == self._fc_place_masked:
            assert self._fc_dest is not None and self._fc_leg_pre is not None
            moved = any(near(self._fc_dest, leg) for leg in legs) and not any(
                near(self._fc_leg_pre, leg) for leg in legs
            )
            self._log_traj(moved)
            if moved:
                self._move_idx += 1
                self._frozen_moves += 1
                self._reset_move()
                return self._frozen_step(grid, bg, masked)
            self._fc_retry += 1
            if self._fc_select_cells and self._fc_retry <= _MAX_SELECT_RETRY:
                return self._frozen_issue_select()
            if self._fc_pred_body is not None:
                self._learned_haz.add(self._fc_pred_body)
            self._moves = None
            self._frozen_moves += 1
            self._reset_move()
            return self._frozen_step(grid, bg, masked)

        self._fc_place_count += 1
        if self._fc_place_count > _PLACE_STUCK_LIMIT:
            self._log_traj(False)
            if self._fc_pred_body is not None:
                self._learned_haz.add(self._fc_pred_body)
            self._moves = None
            self._frozen_moves += 1
            self._reset_move()
            return self._frozen_step(grid, bg, masked)
        self._fc_place_issued = True
        self._fc_place_masked = masked
        return self._fc_dest

    # ── measurement: record the observed transition ─────────────────────

    def _observe_result(self, cur_key: Any) -> None:
        click = self._pending_click
        prev_key = self._pending_key
        self._pending_click = None
        self._pending_key = None
        if click is None or prev_key is None:
            return
        self._transitions.append((prev_key, click, cur_key))
        self._edges.setdefault(prev_key, {})[click] = cur_key
        self._tried_from.setdefault(prev_key, set()).add(click)

    # ── planning ─────────────────────────────────────────────────────────

    def _decide(self, cur_key: Any, cands: list[Cell]) -> Cell:
        tried = self._tried_from.get(cur_key, set())
        untried = [c for c in cands if c not in tried]
        if untried:
            return untried[0]

        target = self._nearest_untried(cur_key)
        if target is not None and target != cur_key:
            path = transition_shortest_path(self._transitions, cur_key, target)
            if path:
                return path[0]  # type: ignore[return-value]

        # Fully explored under current knowledge -- click any candidate
        # rather than stall.
        return cands[0]

    def _nearest_untried(self, start_key: Any) -> Any | None:
        """BFS over the KNOWN transition graph from ``start_key``; return the
        nearest visited state (including ``start_key``) that still has a
        candidate click not yet in ``_tried_from``, or None if every
        reachable state is fully explored. Hand-rolled rather than
        :func:`admorphiq.kernels.reachable_frontier` for the same reason
        ``admorphiq.adapters25.tu93`` gives (its universe is observed edges
        only, so it cannot surface a state's never-clicked candidate)."""
        visited = {start_key}
        queue: deque[Any] = deque([start_key])
        while queue:
            state = queue.popleft()
            cands = self._cands_at.get(state)
            if cands is not None:
                tried = self._tried_from.get(state, set())
                if any(c not in tried for c in cands):
                    return state
            for _cell, nxt in self._edges.get(state, {}).items():
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        return None
