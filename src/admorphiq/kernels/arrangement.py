"""Constrained-1D-arrangement / ring-permutation FAMILY CORE (R94 distillation).

The load-bearing solving ENGINE distilled out of the ``lp85`` script25 adapter's
full 8/8 conquest, so the SAME code drives two callers with no drifting copy:

  (a) the live adapter (``admorphiq.adapters25.lp85``) — its single-press
      ring-planner delegates ``_learn_button`` -> :func:`arrangement_learn_button`
      and every ``*_build_plan`` -> :func:`arrangement_plan` (structural
      delegation, extraction-not-rewrite: the bodies are the adapter's own, moved
      here verbatim, so live behaviour is byte-equivalent by construction), and
  (b) the offline model's patchable card — :func:`arrangement_core` composes the
      two primitives into ONE sandbox-runnable engine (frame + xy-carrying
      transition dicts + ``act``), assembled by ``tools.solver_core.source_card``.

Why this lives under ``admorphiq.kernels`` rather than ``tools/solver_core``: a
script25 adapter (quarantine zone) may only import stdlib, ``admorphiq.kernels.*``
and ``admorphiq.adapters25.base`` (enforced by ``scripts/adapters25_lint.py``), so
the delegation target the adapter imports MUST be a kernels submodule. The card is
still registered in ONE place (``tools.solver_core``); this module only supplies
the real source it bundles.

The distilled slice is the SINGLE-PRESS ring family: learn one rotation control's
``{cell: successor}`` permutation from a before/after press, then BFS a control
sequence that lands every moving goal token on its same-class fixed target. The
adapter's own ACTIVE multi-press / coupled certification driving (which button to
press K times, self-test-drop, open-chain repair) stays adapter-local engine
wiring — but it, too, plans through :func:`arrangement_plan` (its load-bearing
half), so the delegated portion is the solver, not a token slice.

Sandbox contract (see ``tools.code_agent.run_code``): the card runs with ONLY
``np``, Python builtins, ``from collections import deque``, and the helper sources
the card bundles. ``current_frame`` is a grid (list[list[int]] in the sandbox,
ndarray at adapter runtime — both normalize); ``transitions`` is a list of
``{"action", "xy": [x, y] | None, "before", "after"}`` dicts; ``act(name, x, y)``
QUEUES an action (``"CLICK"`` with x=col, y=row for ACTION6).
"""

from __future__ import annotations

from typing import Any, Callable

from admorphiq.kernels._common import normalize_frame as _normalize_frame
from admorphiq.kernels.motion import frame_diff
from admorphiq.kernels.permute import (
    complete_cycle,
    is_single_cycle,
    learn_cyclic_successor,
    learn_successor_from_series,
    plan_token_assignment,
)
from admorphiq.kernels.regions import find_regions

__all__ = [
    "arrangement_core",
    "arrangement_learn_button",
    "arrangement_learn_series",
    "arrangement_plan",
    "arrangement_scale_unit",
]

Cell = tuple[int, int]
Bbox = tuple[int, int, int, int]

# ── GAME-SPECIFIC PRIORS — RE-DERIVE from your observations ──────────────────
# These encode lp85's measured ring-puzzle semantics (see the lp85 adapter's
# module docstring, "L2 SOLVED" section, verified by driving the real engine).
# A patcher on a DIFFERENT arrangement game MUST re-derive them from the observed
# transitions: which colours are the rotation controls, how big a solid moving
# token is, how far apart a hollow target frame's corners sit, and how deep to BFS.
_BUTTON_COLORS = frozenset({8, 14})  # rotation controls (two directions)
_SOLID_MIN_SIZE = 3  # a marker region this size or larger is a solid moving token
_DEST_CLUSTER_SPAN = 6  # corner pixels within this L∞ span form one target frame
_PLANNER_BUDGET = 40  # max rotation-sequence length the BFS may return
_CERTIFY_MAX_PRESSES = 26  # adaptive-K cap: stop re-pressing a control after this
#   many presses without certifying its ring (mirrors the lp85 adapter's
#   _MP_MAX_PRESSES ring give-up — a control whose ring never fingerprints cleanly
#   is dropped rather than ground on forever).
# ── END GAME-SPECIFIC PRIORS ─────────────────────────────────────────────────


def _cint(region: dict[str, Any]) -> Cell:
    r, c = region["centroid"]
    return (round(r), round(c))


def _snap(cell: Cell, lattice: list[Cell]) -> Cell:
    return min(lattice, key=lambda q: (q[0] - cell[0]) ** 2 + (q[1] - cell[1]) ** 2)


def _token_regions(
    regions: list[dict[str, Any]], tile_max: int = 6
) -> list[dict[str, Any]]:
    """The small non-button regions that ride the rings (coloured tiles + goal
    tokens). The successor learner further restricts to the ones that actually
    moved, so including static corner dots here is harmless. ``tile_max`` scales
    with the board so larger-render ring tiles (LP85 L5 ~16px) are not dropped."""
    return [
        r
        for r in regions
        if int(r["color"]) not in _BUTTON_COLORS and int(r["size"]) <= tile_max
    ]


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


def _extract_frames_at(
    pts: list[Cell], ptset: set[Cell], side: int, need: int
) -> tuple[list[Cell], set[Cell]]:
    """Greedily claim disjoint axis-aligned squares of a fixed ``side`` from the
    top-left. Each square is a candidate hollow frame ``{(r,c),(r,c+s),(r+s,c),
    (r+s,c+s)}``; it is accepted when at least ``need`` of its 4 corners are
    present and unused (the top-left corner always required, so the global-minimum
    unused dot — necessarily some real frame's top-left — anchors the claim).
    Returns the accepted frame centres and the set of corners consumed."""
    used: set[Cell] = set()
    centres: list[Cell] = []
    for (r, c) in pts:
        if (r, c) in used:
            continue
        square = [(r, c), (r, c + side), (r + side, c), (r + side, c + side)]
        present = [p for p in square if p in ptset and p not in used]
        if len(present) >= need and (r, c) in present:
            used.update(present)
            rr = round(sum(p[0] for p in square) / 4)
            cc = round(sum(p[1] for p in square) / 4)
            centres.append((rr, cc))
    return centres, used


def _cluster_frame_centres(corners: list[Cell], span: int = _DEST_CLUSTER_SPAN) -> list[Cell]:
    """Group the loose corner dots of one colour into hollow target frames and
    return each frame's centre.

    A hollow 4-corner target renders 4 corner dots at the corners of a square whose
    side is the sprite footprint. Single-linkage clustering (the earlier span-group
    rule) MERGES adjacent frames when the inter-frame gap is no larger than the
    intra-frame corner span — measured on LP85 L6, where 3 targets sit corner-pitch
    apart (both gaps = 3), collapsing all 12 corners into ONE dest and stalling the
    planner. Instead DERIVE the square side from the corner geometry (a gap that
    appears as both a horizontal and a vertical frame edge) and extract DISJOINT
    squares greedily from the top-left, so each corner belongs to exactly one frame.

    ``span`` scales with the board (see :func:`_scale_unit`); it only bounds the
    largest plausible frame side here (a coarse render draws wider frames), so
    distant lone frames are never joined into one oversized square.

    A well-separated frame (LP85 L2/L3/L5) has exactly one same-row and one
    same-col edge, so it extracts as a single square unchanged; an occluded frame
    (3 corners) is recovered by the leftover pass. Preserves the prior ≥3-corner
    occlusion tolerance while separating tightly-packed frames."""
    pts = sorted(set(corners))
    if len(pts) < 3:
        return []
    ptset = set(pts)
    rows: dict[int, list[int]] = {}
    cols: dict[int, list[int]] = {}
    for (r, c) in pts:
        rows.setdefault(r, []).append(c)
        cols.setdefault(c, []).append(r)
    side_cap = max(6, 2 * span)
    hgaps = {abs(a - b) for cs in rows.values() for a in cs for b in cs if a < b}
    vgaps = {abs(a - b) for rs in cols.values() for a in rs for b in rs if a < b}
    cands = sorted(s for s in (hgaps & vgaps) if 1 <= s <= side_cap)
    if not cands:
        cands = sorted(s for s in (hgaps | vgaps) if 1 <= s <= side_cap)
    best: list[Cell] = []
    best_cover = -1
    for side in cands:
        # strict 4-corner squares first, then recover occluded (3-corner) frames
        # from the leftovers so a lone missing corner still yields its centre.
        f4, u4 = _extract_frames_at(pts, ptset, side, 4)
        leftover = [p for p in pts if p not in u4]
        f3, u3 = _extract_frames_at(leftover, ptset - u4, side, 3)
        centres = sorted(f4 + f3)
        cover = len(u4) + len(u3)
        if cover > best_cover or (cover == best_cover and len(centres) < len(best)):
            best_cover = cover
            best = centres
    return best


def _detect_dests(
    regions: list[dict[str, Any]],
    colors: frozenset[int],
    solid_min: int = _SOLID_MIN_SIZE,
    span: int = _DEST_CLUSTER_SPAN,
) -> list[tuple[int, Cell]]:
    """Fixed destinations = the centres of the hollow 4-corner target frames,
    tagged with their colour class. The sub-``solid_min`` marker-colour regions
    are the corner dots (single sprite pixels); cluster them per colour and take
    each cluster's centre."""
    dests: list[tuple[int, Cell]] = []
    for color in colors:
        corners = [
            _cint(r)
            for r in regions
            if int(r["color"]) == color and int(r["size"]) < solid_min
        ]
        dests.extend((color, centre) for centre in _cluster_frame_centres(corners, span))
    return sorted(dests)


def _detect_movers(
    regions: list[dict[str, Any]], colors: frozenset[int], solid_min: int = _SOLID_MIN_SIZE
) -> list[tuple[int, Cell]]:
    """Moving goal tokens = SOLID regions of a marker colour, tagged with their
    colour class (so a token is only ever matched to a same-class target). A
    target's corner blocks are smaller than ``solid_min`` (they are single sprite
    pixels, the goal token is a full 2×2 block), so they are excluded here."""
    return sorted(
        (int(r["color"]), _cint(r))
        for r in regions
        if int(r["color"]) in colors and int(r["size"]) >= solid_min
    )


def _detect_marker_colors(
    regions: list[dict[str, Any]],
    solid_min: int = _SOLID_MIN_SIZE,
    span: int = _DEST_CLUSTER_SPAN,
) -> frozenset[int]:
    """The colour classes that behave as (moving solid token, fixed hollow
    target) pairs: a colour that appears BOTH as a solid block AND as a hollow
    4-corner target frame (a ≥3-dot cluster). A level may have several such
    classes (LP85 L3 has two — goal/target and goal-o/target-o — that must all
    be placed to win), so detection is not tied to a single hard-coded colour.
    Requiring a real corner *frame* (not just any stray small region) is what
    stops ordinary coloured ring tiles from being mistaken for markers.

    ``solid_min`` / ``span`` scale with the board (see the adapter's
    ``_scale_unit``); at their defaults they reproduce the original fixed L1–L4
    thresholds."""
    solids = {
        int(r["color"])
        for r in regions
        if int(r["color"]) not in _BUTTON_COLORS and int(r["size"]) >= solid_min
    }
    return frozenset(c for c in solids if _detect_dests(regions, frozenset({c}), solid_min, span))


# ── load-bearing solver primitives (the distilled ENGINE) ────────────────────


def arrangement_learn_button(
    before_frame: Any, after_frame: Any, background: frozenset[int] | int | None
) -> dict[Cell, Cell]:
    """Learn ONE rotation control's ``{cell: successor}`` permutation from the
    frame pair spanning a single press of it — the "(a) learn per-click
    marker-movement effect" half of the engine.

    Extracted verbatim from ``lp85.Adapter._learn_button``'s learning body (the
    self-test-and-drop that follows it there is adapter POLICY, not the learner,
    and stays adapter-local). Segments both frames into ring-tile regions, diffs
    them, and recovers the cyclic successor map — passing every token centroid as
    a candidate so a ring cell that kept its colour (invisible in the diff) is
    recovered geometrically rather than dropped, then closing the partial map into
    a full cycle.

    Expected feedback: a ``{cell: successor}`` map over the rotated ring's cells;
    ``len < 2`` signals an inert / non-rotating press the caller must not plan on.
    """
    before = _token_regions(find_regions(before_frame, background=background))
    after = _token_regions(find_regions(after_frame, background=background))
    diff = frame_diff(before_frame, after_frame)
    candidates = [_cint(r) for r in before]
    return complete_cycle(
        learn_cyclic_successor(before, after, diff["cells"], candidate_cells=candidates)
    )


# ── press-until-certify orchestration (adaptive-K) ───────────────────────────
# Distilled from the lp85 adapter's multi-press ring learner (its ``mp_learn``
# phase + ``_mp_match`` / ``_scale_unit`` and the ``_learn_button`` self-test):
# learning a ring from ONE press under-determines it whenever adjacent ring cells
# reuse a colour (the swap is invisible), so the adapter re-presses the SAME
# control until its colour time-series fingerprints every ring cell (bounded by
# ``_MP_MIN_PRESSES`` .. ``_MP_MAX_PRESSES``). These functions carry that policy so
# the sandbox CARD — not just the adapter — presses-until-certify, driven purely
# from the growing ``transitions`` list (the core is re-invoked each refill).


def arrangement_scale_unit(
    regions: list[dict[str, Any]], background: frozenset[int]
) -> int:
    """The board's TILE UNIT — the modal size of a small non-background region.

    Extracted from ``lp85.Adapter``'s module-level ``_scale_unit`` (which now
    delegates here) so the card and the adapter derive scale from ONE
    implementation. A coarser render scales every sprite up, so the size thresholds
    the ring detectors use must scale with this unit rather than a fixed pixel
    count; the modal small region is the 2×2 tile/token block. Returns 4 (the LP85
    L1–L4 unit) when nothing small is present, reproducing the original fixed
    thresholds exactly."""
    small = [
        int(r["size"])
        for r in regions
        if int(r["color"]) not in background and 1 <= int(r["size"]) <= 32
    ]
    if not small:
        return 4
    counts: dict[int, int] = {}
    for s in small:
        counts[s] = counts.get(s, 0) + 1
    return max(counts, key=lambda s: (counts[s], -s))


def _arr_scale(
    regions: list[dict[str, Any]], background: frozenset[int]
) -> tuple[int, int, int, int]:
    """``(unit, solid_min, span, tile_max)`` scaled to the board (see
    :func:`arrangement_scale_unit`). At unit 4 these equal the fixed LP85 L1–L4
    priors, so those levels are byte-identical; a coarse render relaxes them
    proportionally (mirrors the adapter ``_detect``'s scale-relative thresholds)."""
    unit = arrangement_scale_unit(regions, background)
    solid_min = max(_SOLID_MIN_SIZE, unit // 2)
    span = max(_DEST_CLUSTER_SPAN, 3 * int(unit ** 0.5))
    tile_max = max(6, 2 * unit)
    return unit, solid_min, span, tile_max


def arrangement_learn_series(
    frames: list[Any], background: frozenset[int] | int | None, tile_max: int
) -> tuple[dict[Cell, Cell], bool]:
    """Learn one control's ring from the colour TIME-SERIES over K presses — the
    per-button EVIDENCE ACCUMULATION half of press-until-certify.

    Extracted verbatim from ``lp85.Adapter._mp_match`` (which now delegates here):
    every ring tile's colour across the ``K+1`` frames spanning ``K`` consecutive
    presses of ONE control uniquely fingerprints its cyclic order even when tokens
    reuse colours (where a single press is ambiguous). A cell whose colour never
    changed across the window is static (off-ring) and excluded before matching.

    Expected feedback: ``(succ, all_exact)`` — ``succ`` a bijection over the moved
    cells; ``all_exact`` True iff every assigned successor matched its predecessor's
    shifted series at EVERY timestep (a perfect, trustworthy fingerprint). ``succ``
    grows to cover the whole ring only once every ring cell has been OBSERVED to
    move, which is why a colour-duplicated ring needs several presses."""
    regions0 = find_regions(frames[0], background=background)
    cells = [_cint(r) for r in regions0 if int(r["size"]) <= tile_max]
    series: dict[Cell, tuple[int, ...]] = {}
    for (rr, cc) in cells:
        s = tuple(int(frames[t][rr][cc]) for t in range(len(frames)))
        if len(set(s)) > 1:
            series[(rr, cc)] = s
    return learn_successor_from_series(series)


def _press_runs(transitions: list[dict[str, Any]]) -> list[tuple[Cell, list[Any]]]:
    """Segment the transition history into maximal CONTIGUOUS same-control press
    runs. Each run is ``(button_cell, frames)`` with ``frames = [before, after,
    after, …]`` spanning that run's presses (a click's ``xy`` is ``(x=col, y=row)``;
    a non-click or a different control breaks the run). The learning burst that
    presses one control K times in a row IS the longest run for that control, so
    reconstructing runs recovers the adaptive-K window even after a plan later
    interleaves single presses of the same control among other buttons."""
    runs: list[tuple[Cell, list[Any]]] = []
    cur_btn: Cell | None = None
    cur_frames: list[Any] = []
    for t in transitions:
        xy = t.get("xy")
        btn = None if xy is None else (int(xy[1]), int(xy[0]))
        if btn is not None and btn == cur_btn:
            cur_frames.append(t["after"])
        else:
            if cur_btn is not None and len(cur_frames) >= 2:
                runs.append((cur_btn, cur_frames))
            if btn is None:
                cur_btn = None
                cur_frames = []
            else:
                cur_btn = btn
                cur_frames = [t["before"], t["after"]]
    if cur_btn is not None and len(cur_frames) >= 2:
        runs.append((cur_btn, cur_frames))
    return runs


def _selftest_map(
    succ: dict[Cell, Cell],
    before: Any,
    after: Any,
    background: frozenset[int] | int | None,
    marker_colors: frozenset[int],
    solid_min: int,
) -> bool:
    """Whether a learned ring map is consistent with an observed mover move.

    Extracted from ``lp85.Adapter._learn_button``'s self-test-and-DROP policy
    (which now delegates here): a ring whose map predicts a goal token would move
    to a cell it did NOT occupy afterwards is a WRONG map that would corrupt the
    plan, so the caller drops it. A mover the ring does not carry (absent from
    ``succ``) is no evidence either way and passes."""
    pre = {
        cell
        for _c, cell in _detect_movers(
            find_regions(before, background=background), marker_colors, solid_min
        )
    }
    post = {
        cell
        for _c, cell in _detect_movers(
            find_regions(after, background=background), marker_colors, solid_min
        )
    }
    for g in pre:
        if g in succ and succ[g] not in post:
            return False
    return True


def _certify_button(
    frames: list[Any],
    background: frozenset[int] | int | None,
    marker_colors: frozenset[int],
    solid_min: int,
    tile_max: int,
) -> dict[Cell, Cell] | None:
    """Certify ONE control from its accumulated press window, or ``None`` if it
    needs more evidence — the core's per-button "is this ring fully learned?" gate.

    CERTIFIED requires all three: (1) the time-series map over the window is a clean
    single cycle whose every edge is exact (:func:`arrangement_learn_series`); (2)
    that map COVERS the ring's full expected cell set — the augmented single-press
    map from :func:`arrangement_learn_button` splices the loop's momentarily-invisible
    tiles back in geometrically, so this is "the map covers the expected ring cells"
    (ring size derived from marker/track geometry, the way the adapter does): a
    series that has not yet observed every ring cell move is rejected, which is what
    makes a colour-duplicated ring take several presses; and (3) it does not
    mispredict an observed mover move (:func:`_selftest_map`). Below any of these,
    the control is uncertified and the caller re-presses it."""
    if len(frames) < 2:
        return None
    succ, all_exact = arrangement_learn_series(frames, background, tile_max)
    if len(succ) < 2 or not all_exact or not is_single_cycle(succ):
        return None
    expected = set(arrangement_learn_button(frames[0], frames[1], background))
    if expected and not (set(succ) >= expected):
        return None
    if not _selftest_map(
        succ, frames[-2], frames[-1], background, marker_colors, solid_min
    ):
        return None
    return succ


def _certify_ops(
    transitions: list[dict[str, Any]],
    background: frozenset[int] | int | None,
    marker_colors: frozenset[int],
    solid_min: int,
    tile_max: int,
) -> tuple[dict[Cell, dict[Cell, Cell]], set[Cell], dict[Cell, int]]:
    """Accumulate ALL of each control's presses and certify the ones whose rings are
    fully learned. Returns ``(ops, certified, presses)``: the certified
    ``{button: succ}`` maps, the certified button set, and each control's TOTAL
    press count (drives the least-pressed-uncertified re-press choice). The learning
    burst for a control is its longest contiguous run, so a control keeps its
    certified map even after a plan later interleaves single presses of it."""
    best: dict[Cell, list[Any]] = {}
    for btn, frames in _press_runs(transitions):
        if btn not in best or len(frames) > len(best[btn]):
            best[btn] = frames
    presses: dict[Cell, int] = {}
    for t in transitions:
        xy = t.get("xy")
        if xy is None:
            continue
        b = (int(xy[1]), int(xy[0]))
        presses[b] = presses.get(b, 0) + 1
    ops: dict[Cell, dict[Cell, Cell]] = {}
    certified: set[Cell] = set()
    for btn, frames in best.items():
        succ = _certify_button(frames, background, marker_colors, solid_min, tile_max)
        if succ is not None:
            ops[btn] = succ
            certified.add(btn)
    return ops, certified, presses


def arrangement_plan(
    ops: dict[Any, dict[Cell, Cell]],
    movers: list[tuple[int, Cell]],
    dests: list[tuple[int, Cell]],
    *,
    budget: int,
) -> list[Any] | None:
    """BFS a control sequence that lands every moving token on its same-class
    target — the "(b) plan a press sequence driving markers to targets" half.

    Extracted as the shared body of ``lp85.Adapter._build_plan`` /
    ``_mp_build_plan`` / ``_cb_build_plan`` (all three now delegate here, so their
    live behaviour is byte-equivalent). Builds the ring lattice from the learned
    operators, snaps each mover/target onto it, and delegates the class-aware
    search to :func:`admorphiq.kernels.permute.plan_token_assignment`.

    ``ops`` maps an operator NAME (any hashable — the adapter uses ``"b<idx>"`` /
    ring-op names / button cells) to its learned permutation; ``movers`` / ``dests``
    are ``(colour_class, cell)`` lists. Returns the operator-name sequence
    (length ≤ ``budget``), or ``None`` when no operators, a mover/dest mismatch,
    or an unreachable assignment means the caller should fall back.
    """
    ops = {k: v for k, v in ops.items() if len(v) >= 2}
    if not ops:
        return None
    lattice: list[Cell] = []
    seen: set[Cell] = set()
    for mp in ops.values():
        for cell in (*mp.keys(), *mp.values()):
            if cell not in seen:
                seen.add(cell)
                lattice.append(cell)
    if not movers or len(movers) != len(dests):
        return None
    tokens = [_snap(cell, lattice) for _color, cell in movers]
    token_labels = [color for color, _cell in movers]
    goals = [_snap(cell, lattice) for _color, cell in dests]
    goal_labels = [color for color, _cell in dests]
    plan = plan_token_assignment(
        ops,
        tokens,
        goals,
        labels=token_labels,
        goal_labels=goal_labels,
        budget=budget,
    )
    if not plan:
        return None
    return list(plan)


def arrangement_core(
    current_frame: Any,
    transitions: list[dict[str, Any]],
    act: Callable[..., None],
    trace: list[str] | None = None,
) -> None:
    """Sandbox-runnable ring-permutation engine with PRESS-UNTIL-CERTIFY learning:
    accumulate every control's presses from ``transitions``, certify the controls
    whose rings are fully learned (:func:`_certify_ops`), and either QUEUE a solving
    press sequence from the CERTIFIED maps or QUEUE the next certification press.

    This carries the lp85 conquest's load-bearing adaptive-K orchestration, not just
    a single-press slice: a colour-duplicated ring is under-determined by one press,
    so the core RE-presses the LEAST-PRESSED uncertified control (never-pressed
    first) until its colour time-series fingerprints every ring cell — capped at
    ``_CERTIFY_MAX_PRESSES`` presses per control (a ring that never certifies is
    dropped). It plans ONLY from certified maps. Because the core is re-invoked each
    refill on the GROWING transition list, a plan that did not clear simply
    re-certifies and re-plans from the new board — no persistent state. Instrumented
    ``trace`` lines (detection counts, per-control press counts + certified flag,
    plan length, certify/probe decision) give a patcher localization evidence.
    """
    grid = _normalize_frame(current_frame)
    bg = _planner_background(grid)
    regions = find_regions(grid, background=bg)
    buttons = _detect_buttons(regions)
    _unit, solid_min, span, tile_max = _arr_scale(regions, bg)
    marker_colors = _detect_marker_colors(regions, solid_min, span)
    movers = _detect_movers(regions, marker_colors, solid_min)
    dests = _detect_dests(regions, marker_colors, solid_min, span)
    if trace is not None:
        trace.append(
            f"detect: buttons={len(buttons)} marker_classes={len(marker_colors)} "
            f"movers={len(movers)} dests={len(dests)}"
        )

    # (a) accumulate every control's presses and certify the fully-learned rings.
    ops, certified, presses = _certify_ops(
        transitions, bg, marker_colors, solid_min, tile_max
    )
    if trace is not None:
        per = (
            " ".join(
                f"({b[1]},{b[0]})={presses.get(b, 0)}p{'C' if b in certified else ''}"
                for b in buttons
            )
            or "none"
        )
        trace.append(
            f"learned {len(ops)} effect-map(s); certified {len(certified)}/{len(buttons)} "
            f"presses[{per}]"
        )

    # (b) plan from the CERTIFIED maps only, when a full same-class placement exists.
    if ops and movers and len(movers) == len(dests):
        plan = arrangement_plan(ops, movers, dests, budget=_PLANNER_BUDGET)
        if plan:
            if trace is not None:
                trace.append(f"plan={len(plan)} presses -> queue")
            for button in plan:
                act("CLICK", button[1], button[0])
            return
        if trace is not None:
            trace.append("no reachable plan from certified maps")

    # press-until-certify: re-press the LEAST-PRESSED uncertified control (never-
    # pressed first), capped at _CERTIFY_MAX_PRESSES presses (adaptive-K give-up).
    pending = [
        b
        for b in buttons
        if b not in certified and presses.get(b, 0) < _CERTIFY_MAX_PRESSES
    ]
    if pending:
        target = min(pending, key=lambda b: (presses.get(b, 0), b))
        if trace is not None:
            trace.append(
                f"certify press ({target[1]},{target[0]}) presses={presses.get(target, 0)}"
            )
        act("CLICK", target[1], target[0])
        return
    if trace is not None:
        trace.append("no uncertified control under the press cap")
