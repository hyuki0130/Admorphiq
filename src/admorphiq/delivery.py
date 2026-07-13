"""Frame-only DELIVERY (pick-up / carry / drop) capability (R28 family,
sibling of transform_route.py/rotation.py/slider.py, WA30-class).

A pick-carry-deliver sub-class: the board holds a player sprite that moves on
a fixed grid step, several small ITEM markers (each a small closed ring frame
around a solid-colour interior fill — structurally the same "ring + interior"
shape family as RE86's target markers and this module's own TARGET zone, just
at a different size), and one or more larger TARGET zones the items must be
carried into. ACTION5 is a context action: pressed while the player is
adjacent to and facing an item, it picks the item up (attaching it to the
player at the facing-direction offset); pressed again while the item's
attached position lies within a target zone's footprint, it drops the item
there.

Provenance: `.wiki/wiki/games/WA30.md` records the mechanic ("delivery" —
pick up items, deliver to target zones) and the legacy `strat_wa30_analytical`
(`src/admorphiq/agent_ensemble.py`) encodes a full solution reading game-
internal sprite tags. That solver's TAG READS are not reused here (brittle,
Kaggle-invisible); its overall shape — BFS-navigate adjacent to an item, face
it, pick up (ACTION5), BFS-navigate the carried player+item pair (item held
at a FIXED offset from the player, discovered once at pickup time and never
recomputed until the next pickup) to a free target cell, drop (ACTION5) — is
the starting hypothesis, independently CONFIRMED by a live clean-reset probe
trace on the real WA30 L1 board:

- The board's small (4x4) ring+2x2-interior icons are the item markers: a
  closed ring frame (:func:`admorphiq.rotation._is_ring_component`, reused)
  around a solid-colour interior fill. A LARGER ring+interior structure
  (measured: 12x4 vs the items' 4x4, i.e. a 3x size-class jump) is the
  target zone — :func:`_split_items_targets` separates the two classes by
  this measured size outlier, not a fixed game-specific count.
- The player is a 4x4 two-colour sprite: a stable "body" colour plus a
  1-cell-wide "leading edge" accent stripe that relocates to whichever side
  faces the direction of the LAST move — this is NOT a fixed-position marker
  (unlike RE86's active-sprite hole), so naively tracking either colour
  alone across two ARBITRARY frames gives a scrambled delta whenever the
  facing direction differs between them (measured: the existing generic
  movement-discovery phase locks onto the accent colour alone and produces
  a corrupted move_map, e.g. action2 measured (0, 7) instead of the true
  (0, 4)). :func:`detect_mover_by_motion` fixes this the same way
  transform_route.py's `detect_sprite_by_motion` fixed RE86's decoration
  contamination: track the UNION of whichever colours changed state under
  ONE known-good calibration press (excluding the known item/target ring
  and interior colours), which is immune to which sub-colour carries the
  accent in either frame because it is not colour-keyed at all.
- Items block player movement (measured: the player could not walk onto an
  item's cell) until picked up; once carried, the item's cell is simply
  wherever `player_cell + carry_offset` lands (no independent obstacle of
  its own — the offset moves with the player).
- The carried item's offset is fixed at pickup time to exactly one grid step
  in the direction the player was facing (matching the legacy solver's
  "face the item, then press 5" step) and does NOT retarget to the current
  travel direction on subsequent moves (measured: after picking up while
  facing up, the item stayed attached ABOVE the player through two DOWN
  presses and a RIGHT press, never re-anchoring to "below" or "left of").

Scope (recorded, not solved here): autonomous non-player "worker" entities
that also pick up/deliver items (mentioned in the wiki, present in the
legacy solver's tag reads) were not observed moving during the L1 probe
trace this module was built against — no detection or avoidance logic for
them is implemented (see the "no speculative branches" doctrine). A future
level that requires it is out of scope until measured.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .arrangement import _HUD_ROW_CUTOFF
from .general_agent import connected_components
from .rotation import _is_ring_component

# ── Tunables ─────────────────────────────────────────────────────────────────

# The multiplicative cell-count jump (largest / next-largest, sorted) that
# separates the TARGET size class from the ITEM size class in
# :func:`_split_items_targets`. Measured on WA30 L1: 3 items at 16 cells
# each (ring 12 + interior 4), 1 target at 48 cells (ring 28 + interior 20)
# — a 3.0x jump. 2.0 leaves comfortable margin below that measured value
# while still rejecting a board where every ring+interior marker is the
# same size (no target/item distinction the frame can express).
_SIZE_CLASS_RATIO = 2.0


# ── entity structures ───────────────────────────────────────────────────────


@dataclass
class RingMarker:
    """A ring-frame + solid-interior marker: an item or a target zone."""

    ring_color: int
    interior_color: int
    cells: frozenset[tuple[int, int]]  # (x, y), ring + interior combined
    cx: float
    cy: float


@dataclass
class Mover:
    """A moving multi-colour entity (the player, or an item mid-carry):
    every cell that changed state under one action, regardless of which of
    several colours it is — see :func:`detect_mover_by_motion`.
    """

    cells: frozenset[tuple[int, int]]
    cx: float
    cy: float


@dataclass
class DeliveryPuzzle:
    """A detected delivery puzzle: item markers and target zone(s)."""

    items: list[RingMarker]
    targets: list[RingMarker]


# ── detection ────────────────────────────────────────────────────────────────


def _ring_markers(layer: np.ndarray, background: int) -> list[RingMarker]:
    """Every ring-frame component with a solid, single-colour interior fill.

    Reuses :func:`admorphiq.rotation._is_ring_component` (the same "genuine
    closed border" test RE86's target markers use) at whatever bbox scale
    the ring happens to be — no fixed size assumption, so items (4x4) and
    target zones (measured 12x4 on WA30 L1) are found by the SAME pass; the
    size split into item/target roles happens separately in
    :func:`_split_items_targets`. Pure / env-free.
    """
    out: list[RingMarker] = []
    for c in connected_components(layer, background):
        if c["cy"] >= _HUD_ROW_CUTOFF or not _is_ring_component(c):
            continue
        rows = [r for r, _c in c["cells"]]
        cols = [cc for _r, cc in c["cells"]]
        r0, r1, c0, c1 = min(rows), max(rows), min(cols), max(cols)
        sub = layer[r0 : r1 + 1, c0 : c1 + 1]
        interior_mask = np.ones(sub.shape, dtype=bool)
        for ry, rx in c["cells"]:
            interior_mask[ry - r0, rx - c0] = False
        if not interior_mask.any():
            continue
        interior_colors = {int(v) for v in sub[interior_mask].tolist()}
        if background in interior_colors or len(interior_colors) != 1:
            continue
        interior_color = interior_colors.pop()
        all_cells = frozenset((x, y) for y, x in c["cells"]) | frozenset(
            (c0 + rx, r0 + ry)
            for ry in range(sub.shape[0])
            for rx in range(sub.shape[1])
            if interior_mask[ry, rx]
        )
        cx = sum(x for x, _y in all_cells) / len(all_cells)
        cy = sum(y for _x, y in all_cells) / len(all_cells)
        out.append(
            RingMarker(
                ring_color=c["color"],
                interior_color=interior_color,
                cells=all_cells,
                cx=cx,
                cy=cy,
            )
        )
    return out


def _split_items_targets(markers: list[RingMarker]) -> tuple[list[RingMarker], list[RingMarker]]:
    """Bipartition ring markers into (items, targets) by a measured size-class jump.

    See :data:`_SIZE_CLASS_RATIO`. When fewer than 2 markers exist, or no
    jump clears the ratio (every marker is the same size class), everything
    is treated as items and there is no detected target — the caller's
    :func:`detect_delivery_puzzle` then correctly reports no puzzle (a
    delivery mechanic needs both). Pure / env-free.
    """
    if len(markers) < 2:
        return list(markers), []
    ordered = sorted(markers, key=lambda m: len(m.cells))
    best_i, best_ratio = 0, 1.0
    for i in range(1, len(ordered)):
        prev_n = len(ordered[i - 1].cells)
        cur_n = len(ordered[i].cells)
        ratio = cur_n / prev_n if prev_n else float("inf")
        if ratio > best_ratio:
            best_ratio = ratio
            best_i = i
    if best_ratio < _SIZE_CLASS_RATIO:
        return ordered, []
    return ordered[:best_i], ordered[best_i:]


def detect_delivery_puzzle(layer: np.ndarray, background: int) -> DeliveryPuzzle | None:
    """Detect a delivery puzzle on ``layer``, or ``None`` when absent.

    Composes :func:`_ring_markers` + :func:`_split_items_targets`. Returns
    ``None`` unless there is at least one item AND at least one target zone
    — so the caller only engages the delivery phase on a genuine
    pick-carry-deliver layout. Pure / env-free.
    """
    markers = _ring_markers(layer, background)
    items, targets = _split_items_targets(markers)
    if not items or not targets:
        return None
    return DeliveryPuzzle(items=items, targets=targets)


def detect_mover_by_motion(
    before: np.ndarray,
    after: np.ndarray,
    exclude_colors: set[int],
    background: int,
    include_colors: set[int] | None = None,
) -> tuple[Mover, Mover] | None:
    """Classify the PLAYER's motion by which cells changed state, excluding
    known non-player colours (item/target ring + interior colours).

    When ``include_colors`` is given (the player's own colour set, learned on
    an earlier distractor-free level), the changed-cell scan is restricted to
    exactly those colours instead of the "everything not an item" default.
    This isolates the player from AUTONOMOUS movers — a patrol actor or an
    animated indicator that shifts on its OWN schedule during a calibration
    press and, if swept into the same before/after diff, drags the union
    centroid to a meaningless delta (measured WA30 L2: colours 12 and 5 moved
    independently of the press, producing a step-1 garbage direction map,
    while the true player is stably colour 14). The default path (no hint) is
    unchanged for the first delivery level, where the player identity is not
    yet known and no distractor was measured.

    Mirrors :func:`admorphiq.transform_route.detect_sprite_by_motion`'s
    domain-restriction technique, generalised from ONE fixed colour to
    "any colour not already accounted for" — necessary because the WA30
    player's own accent colour relocates to whichever edge faces the last
    move direction (see the module docstring), so a single fixed colour
    cannot identify it reliably; the set of cells that changed state, minus
    the colours already known to belong to items/targets, is exactly the
    player regardless of which of its own sub-colours moved where. Returns
    ``(mover_before, mover_after)`` — the vacated-cell footprint and the
    arrived-cell footprint, each its own centroid, so the delta is a clean
    before->after shift the same way the RE86 fix was. Returns ``None`` when
    nothing outside ``exclude_colors``/``background`` changed state at all.

    Rows at/past :data:`admorphiq.arrangement._HUD_ROW_CUTOFF` are excluded
    from consideration entirely (matching :func:`_ring_markers`'s own HUD
    exclusion) — measured necessary: WA30's bottom-row move/attempt counter
    (`.wiki/wiki/rounds/r53_unified-harness.md`, "move-limited... row 63")
    ticks on its own schedule, independent of which calibration press is in
    flight, and a tick landing in the SAME diff as a genuine player press
    would otherwise be swept into the "changed, not excluded" set and skew
    the centroid (measured: action2's raw delta came out (0, 3) instead of
    the true (0, 4) before this exclusion was added). Pure / env-free.
    """
    if before.shape != after.shape:
        return None
    diff = np.argwhere(before != after)
    if not len(diff):
        return None
    vacated: set[tuple[int, int]] = set()
    arrived: set[tuple[int, int]] = set()
    for y, x in diff.tolist():
        if y >= _HUD_ROW_CUTOFF:
            continue
        bv, av = int(before[y, x]), int(after[y, x])
        if include_colors is not None:
            if bv in include_colors:
                vacated.add((x, y))
            if av in include_colors:
                arrived.add((x, y))
            continue
        if bv not in exclude_colors and bv != background:
            vacated.add((x, y))
        if av not in exclude_colors and av != background:
            arrived.add((x, y))
    if not vacated or not arrived:
        return None
    mover_before = Mover(
        cells=frozenset(vacated),
        cx=sum(x for x, _y in vacated) / len(vacated),
        cy=sum(y for _x, y in vacated) / len(vacated),
    )
    mover_after = Mover(
        cells=frozenset(arrived),
        cx=sum(x for x, _y in arrived) / len(arrived),
        cy=sum(y for _x, y in arrived) / len(arrived),
    )
    return mover_before, mover_after


# ── planning ─────────────────────────────────────────────────────────────────


def locate_player_cell(
    layer: np.ndarray, body_color: int, accent_colors: set[int]
) -> tuple[int, int] | None:
    """The player's true (x, y) grid-cell corner, robust to a carried item.

    A colour-mask lookup over the FULL player colour set breaks once
    carrying: the picked-up item is ALSO rendered in the accent colour (see
    the module docstring), so the mask would include the item's own cells
    too and the resulting bbox undershoots the player's true position by
    exactly one grid step toward the carry direction (measured: this was
    the actual cause of every WA30 L1 delivery landing one cell short).

    The fix uses the BODY colour (measured stable: always the larger,
    12-of-16-cell sub-colour, never touching a carried item directly) as
    the anchor, then adds back ONLY the accent cells 4-adjacent to some
    body cell — the player's own leading-edge marker sits immediately
    against the body, while a carried item is always at least one full
    grid step further out, so this adjacency test recovers exactly the
    player's own 4th edge without ever pulling in the carried item's cells,
    regardless of which side currently holds the marker. Returns ``None``
    when no body-coloured cell is present. Pure / env-free.
    """
    body_mask = layer == body_color
    body_ys, body_xs = np.where(body_mask)
    if not len(body_xs):
        return None
    body_cells = set(zip(body_xs.tolist(), body_ys.tolist()))
    accent_mask = np.isin(layer, list(accent_colors)) if accent_colors else np.zeros_like(body_mask)
    accent_ys, accent_xs = np.where(accent_mask)
    marker_cells = {
        (x, y)
        for x, y in zip(accent_xs.tolist(), accent_ys.tolist())
        if (x - 1, y) in body_cells
        or (x + 1, y) in body_cells
        or (x, y - 1) in body_cells
        or (x, y + 1) in body_cells
    }
    return bbox_min_corner(frozenset(body_cells | marker_cells))


def bbox_min_corner(cells: frozenset[tuple[int, int]]) -> tuple[int, int]:
    """The (x, y) top-left corner of ``cells``' own bounding box.

    Used as the canonical "grid cell" coordinate for both the player and
    item/target markers — they all share the same step-sized footprint, so
    the min corner is a stable, orientation-independent position regardless
    of which side an item's accent/leading-edge colour currently occupies.
    Pure / env-free.
    """
    return min(x for x, _y in cells), min(y for _x, y in cells)


def target_slots(target: RingMarker, slot_size: int) -> list[tuple[int, int]]:
    """Enumerate ``slot_size``x``slot_size`` sub-cells tiling ``target``'s bbox.

    A target zone's own footprint can hold multiple items side by side —
    measured on WA30 L1: one 12x4 target zone tiles into exactly 3 4x4 slots
    matching the 3 items' own footprint size. Slots that don't fit evenly
    (a target whose extent is not an exact multiple of ``slot_size``) are
    dropped rather than padded — an uneven remainder was not measured
    anywhere, so no interpolation is invented for it. Pure / env-free.
    """
    xs = [x for x, _y in target.cells]
    ys = [y for _x, y in target.cells]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    width, height = x1 - x0 + 1, y1 - y0 + 1
    if slot_size <= 0 or width % slot_size or height % slot_size:
        return []
    out = []
    for sy in range(y0, y1 + 1, slot_size):
        for sx in range(x0, x1 + 1, slot_size):
            out.append((sx, sy))
    return out


def adjacent_cells(cell: tuple[int, int], step: int) -> list[tuple[int, int]]:
    """The 4 cardinal grid-step neighbours of ``cell``. Pure / env-free."""
    x, y = cell
    return [(x - step, y), (x + step, y), (x, y - step), (x, y + step)]


def bfs_path(
    blocked: set[tuple[int, int]],
    start: tuple[int, int],
    goal_set: set[tuple[int, int]],
    step: int,
    bounds: tuple[int, int],
    item_offset: tuple[int, int] | None = None,
) -> list[tuple[int, int]] | None:
    """Grid BFS from ``start`` to any cell in ``goal_set``, stepping by
    ``step`` in the 4 cardinal directions.

    ``blocked`` never includes ``start`` itself (a cell the player already
    occupies cannot be "blocked" against leaving it) — callers should not
    pre-add it. When ``item_offset`` is given (delivering a carried item,
    fixed at pickup time — see the module docstring), each candidate cell
    ``(px, py)`` is ALSO checked at ``(px+ox, py+oy)`` for blockage: mirrors
    the legacy solver's carried-item collision check, so a delivery path
    never drags the item through a wall/another undelivered item even
    though only the player's own cell is the nominal BFS state. ``bounds``
    is the layer's ``(height, width)`` — candidates outside it (including
    the offset cell, when present) are rejected. Returns the list of
    ``(x, y)`` waypoints (``start`` included) or ``None`` if unreachable.
    Pure / env-free.
    """
    h, w = bounds
    bl = set(blocked)
    bl.discard(start)
    visited = {start}
    queue: list[tuple[tuple[int, int], list[tuple[int, int]]]] = [(start, [start])]
    qi = 0
    while qi < len(queue):
        pos, path = queue[qi]
        qi += 1
        if pos in goal_set:
            return path
        for nx, ny in adjacent_cells(pos, step):
            if (nx, ny) in visited or not (0 <= nx < w and 0 <= ny < h):
                continue
            if (nx, ny) in bl:
                continue
            if item_offset is not None:
                ox, oy = nx + item_offset[0], ny + item_offset[1]
                if not (0 <= ox < w and 0 <= oy < h) or (ox, oy) in bl:
                    continue
            visited.add((nx, ny))
            queue.append(((nx, ny), path + [(nx, ny)]))
    return None


def path_to_actions(
    path: list[tuple[int, int]], dir_map: dict[int, tuple[int, int]]
) -> list[int] | None:
    """Translate consecutive waypoint deltas into action ids via the MEASURED
    ``dir_map`` (action id -> per-press (dx, dy), from
    :func:`detect_mover_by_motion` + calibration — never assumed). Returns
    ``None`` if any step's delta was never observed during calibration (a
    direction the puzzle's own step size doesn't support). Pure / env-free.
    """
    by_delta = {delta: aid for aid, delta in dir_map.items()}
    actions: list[int] = []
    for (x0, y0), (x1, y1) in zip(path, path[1:]):
        delta = (x1 - x0, y1 - y0)
        aid = by_delta.get(delta)
        if aid is None:
            return None
        actions.append(aid)
    return actions
