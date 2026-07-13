"""Frame-only TRANSFORM-PUZZLE capability (R28 family, sibling of rotation.py
and slider.py, RE86-class).

A sixth member of the select-and-place family. This one handles the
**multi-sprite target-coverage transform** sub-class: the board holds one or
more LARGE movable sprites (only one is "active"/controllable at a time — a
select-toggle action cycles which) plus several small, STATIC target
markers, each a ring-shaped frame around a single "required colour" dot. A
level clears once, for every required colour, some movable sprite of that
exact colour has been translated so that its own pixel footprint covers
every marker dot of that colour.

Provenance: ``.wiki/wiki/games/RE86.md`` records the mechanic ("Multiple
sprites must be moved to target positions... multi-sprite same-colour
constraints") and the legacy ``strat_re86_analytical``
(``src/admorphiq/agent_ensemble.py``) encodes a full solution: read game-
internal sprite tags for targets/movables/changers, then search offsets
covering the target's required-colour pixels. That solver's TAG READS are
NOT reused here (brittle, Kaggle-invisible); its GEOMETRIC LOGIC — find an
offset that makes a sprite's own footprint cover a scattered set of same-
coloured points, STEP=3 pixels/action, ACTION5 cycles the active sprite — is
the starting hypothesis, independently CONFIRMED by a live clean-reset probe
trace on the real RE86 board:

- The board's small (~3x3) ring+single-dot icons are exactly the "required
  point" markers described in the wiki: a colour-4 ring frame around one
  interior cell of the colour a sprite must occupy there.
- Exactly one large sprite is "active": its own centre cell is temporarily
  recoloured to a value not used by any sprite/target/background — this
  breaks 4-connectivity (the legacy code's ``pixels[centre] == 0`` read, here
  observed purely from the frame) but is DETECTED rather than assumed: a
  sprite's own colour-cluster containing a foreign-coloured cell inside its
  own bounding box is the active one (:func:`find_active_color`).
- ACTION1-4 translate the active sprite by a MEASURED, uniform per-action
  step (confirmed live: exactly 3 px/action on the measured board, matching
  the wiki/legacy STEP constant, but measured here via
  :func:`admorphiq.general_agent._step_cell_size` on a live-probed
  direction map — never assumed 3 for a different board). ACTION5 toggles
  which sprite is active with ZERO frame ambiguity cost: the "who's active"
  question is answered by :func:`find_active_color` from a single fresh
  frame read, no wasted probe click needed after cycling.
- On the measured RE86 level 1 board, both required colours already have an
  existing sprite of the exact matching colour (no colour-changer tile is
  present at all), and each sprite's own cross/plus-shaped footprint,
  translated by a single analytically-derivable offset
  (:func:`find_covering_offset`), simultaneously covers every required point
  of its colour. This module implements exactly that DIRECT-PLACEMENT case.

Scope (recorded, not solved here): the legacy solver ALSO supports routing a
sprite through a "changer" tile to recolour it when no sprite of a required
colour exists (its own hardcoded level 4-6 solutions suggest even the
changer-routing case does not generalise past a few levels). No changer
detection or routing is implemented here — there is no measured case
motivating it on the level this module was built and verified against (see
the "no speculative branches" doctrine): a colour with no existing sprite of
the exact matching colour is simply left unplaced, and the phase falls
through to normal interaction once every reachable colour is resolved.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .arrangement import _HUD_ROW_CUTOFF
from .general_agent import connected_components
from .rotation import _is_ring_component

# ── Tunables ─────────────────────────────────────────────────────────────────

# A target-marker ring frame must span at least this many cells (filters
# single-pixel speckle).
_MIN_MARKER_FRAME_SIZE = 4
# A target-marker icon's own bbox must be within this many cells on a side
# (measured RE86 markers are 3x3). Distinguishes a small marker ring from a
# much larger structural ring (e.g. a rotation-style piece frame).
_MAX_MARKER_EXTENT = 6
# A movable sprite candidate must span at least this many cells — far larger
# than a marker's single interior dot, so the two classes never collide.
_MIN_SPRITE_SIZE = 10
# Chebyshev gap (px) bridged when clustering same-colour cells into one
# sprite. Measured NECESSARY on RE86: the active sprite's own centre cell is
# recoloured to a foreign "active" marker, which would otherwise fragment
# one sprite into several disconnected same-colour components (the same
# artefact rotation.py/slider.py hit with their own tip/notch markers).
_GAP_BRIDGE = 2
# Radius (px) around a sprite's own centroid searched for the active-marker
# hole in find_active_color. Matches _GAP_BRIDGE's scale (the hole is a
# single cell right at the centre); kept as a distinct constant since it
# answers a different question (where is the active marker, not how far a
# same-colour cluster bridges).
_ACTIVE_MARKER_RADIUS = 2


# ── entity structures ───────────────────────────────────────────────────────


@dataclass
class TargetPoint:
    """A single required (x, y, colour) point read from a ring+dot marker."""

    x: int
    y: int
    color: int


@dataclass
class Sprite:
    """A movable sprite candidate: every cell of one colour, gap-bridge clustered.

    ``cells`` are CURRENT absolute (x, y) positions — re-derive fresh (via
    :func:`detect_sprite_candidates`) after every move rather than trusting a
    stale snapshot.
    """

    color: int
    cells: frozenset[tuple[int, int]]
    cx: float
    cy: float


@dataclass
class TransformPuzzle:
    """A detected transform puzzle: the target points and candidate sprites."""

    targets: list[TargetPoint]
    sprites: list[Sprite]


# ── detection ────────────────────────────────────────────────────────────────


def detect_target_points(layer: np.ndarray, background: int) -> list[TargetPoint]:
    """Ring-frame + single-interior-dot markers -> required (x, y, colour) points.

    A marker is a small (:data:`_MAX_MARKER_EXTENT`-bounded) closed ring
    (:func:`admorphiq.rotation._is_ring_component`, reused — the same
    "genuine closed border" test that disambiguates a real frame from
    incidental bbox overlap) enclosing EXACTLY one interior cell of a colour
    distinct from the frame and background — that cell's colour is the
    colour some sprite must occupy this exact point with. Pure / env-free.
    """
    out: list[TargetPoint] = []
    for c in connected_components(layer, background):
        if c["cy"] >= _HUD_ROW_CUTOFF or c["size"] < _MIN_MARKER_FRAME_SIZE:
            continue
        if not _is_ring_component(c):
            continue
        rows = [r for r, _c in c["cells"]]
        cols = [cc for _r, cc in c["cells"]]
        r0, r1, c0, c1 = min(rows), max(rows), min(cols), max(cols)
        if (r1 - r0 + 1) > _MAX_MARKER_EXTENT or (c1 - c0 + 1) > _MAX_MARKER_EXTENT:
            continue
        frame_color = c["color"]
        sub = layer[r0 : r1 + 1, c0 : c1 + 1]
        other_mask = (sub != background) & (sub != frame_color)
        if int(other_mask.sum()) != 1:
            continue
        dy, dx = np.argwhere(other_mask)[0]
        out.append(TargetPoint(x=c0 + int(dx), y=r0 + int(dy), color=int(sub[dy, dx])))
    return out


def _cluster_color_cells(
    layer: np.ndarray, color: int, gap: int = _GAP_BRIDGE
) -> list[frozenset[tuple[int, int]]]:
    """BFS-cluster all cells of ``color``, bridging up to ``gap`` Chebyshev distance.

    See the module docstring: the active sprite's own centre cell is
    recoloured to a foreign "active marker" value, which would otherwise
    split one sprite into several disconnected same-colour
    ``connected_components``. Genuinely separate sprites of the same colour
    are measured tens of pixels apart, far beyond ``gap``, so this cannot
    merge them. Returns clusters as sets of ``(y, x)`` cells. Pure / env-free.
    """
    ys, xs = np.where(layer == color)
    cells = set(zip(ys.tolist(), xs.tolist()))
    visited: set[tuple[int, int]] = set()
    clusters: list[frozenset[tuple[int, int]]] = []
    for start in sorted(cells):
        if start in visited:
            continue
        cluster: set[tuple[int, int]] = set()
        stack = [start]
        visited.add(start)
        while stack:
            cy, cx = stack.pop()
            cluster.add((cy, cx))
            for dy in range(-gap, gap + 1):
                for dx in range(-gap, gap + 1):
                    if dy == 0 and dx == 0:
                        continue
                    nb = (cy + dy, cx + dx)
                    if nb in cells and nb not in visited:
                        visited.add(nb)
                        stack.append(nb)
        clusters.append(frozenset(cluster))
    return clusters


def detect_sprite_candidates(
    layer: np.ndarray, background: int, colors: set[int]
) -> list[Sprite]:
    """Movable sprite candidates of each colour in ``colors``.

    Only colours that appear as some target's required colour are searched
    (the caller composes ``colors`` from :func:`detect_target_points`), so a
    decorative same-coloured element elsewhere is not mistaken for a movable
    sprite as long as it is smaller than :data:`_MIN_SPRITE_SIZE` — the
    marker dots themselves (1 cell) are always excluded by this floor. Pure /
    env-free.
    """
    out: list[Sprite] = []
    for color in colors:
        for cluster in _cluster_color_cells(layer, color):
            if len(cluster) < _MIN_SPRITE_SIZE:
                continue
            cells = frozenset((x, y) for y, x in cluster)
            cx = sum(x for x, _y in cells) / len(cells)
            cy = sum(y for _x, y in cells) / len(cells)
            out.append(Sprite(color=color, cells=cells, cx=cx, cy=cy))
    return out


def find_active_color(
    layer: np.ndarray, background: int, sprites: list[Sprite]
) -> int | None:
    """Which sprite (by colour) is currently active, or None.

    The active sprite has a "hole" cell exactly at its own geometric centre —
    a pixel that is neither the sprite's own colour nor the background (the
    temporarily-recoloured centre; for the measured symmetric cross/plus
    sprites, the cell mean IS the shape's true centre of symmetry even with
    that one cell missing from the average). The search window is a small
    neighbourhood around the CENTROID, not the sprite's whole bounding box —
    measured necessary: once a sprite has moved onto its target markers, its
    bbox can also enclose unrelated target-marker FRAME pixels (a different
    foreign colour, elsewhere in the box, not at the centre), which would
    otherwise cause a false "still active" read on a sprite that just moved
    away. Pure / env-free, single-frame, no probe click needed.
    """
    for s in sprites:
        cx, cy = int(round(s.cx)), int(round(s.cy))
        r0 = max(0, cy - _ACTIVE_MARKER_RADIUS)
        r1 = min(layer.shape[0] - 1, cy + _ACTIVE_MARKER_RADIUS)
        c0 = max(0, cx - _ACTIVE_MARKER_RADIUS)
        c1 = min(layer.shape[1] - 1, cx + _ACTIVE_MARKER_RADIUS)
        window = layer[r0 : r1 + 1, c0 : c1 + 1]
        foreign = window[(window != background) & (window != s.color)]
        if foreign.size > 0:
            return s.color
    return None


def detect_transform_puzzle(layer: np.ndarray, background: int) -> TransformPuzzle | None:
    """Detect a transform puzzle on ``layer``, or ``None`` when the structure is absent.

    Composes :func:`detect_target_points` + :func:`detect_sprite_candidates`.
    Returns ``None`` when there are no target markers, or no movable sprite
    of any required colour exists — so the caller only engages the transform
    phase on a genuine marker+sprite layout. Pure / env-free.
    """
    targets = detect_target_points(layer, background)
    if not targets:
        return None
    sprites = detect_sprite_candidates(layer, background, {t.color for t in targets})
    if not sprites:
        return None
    return TransformPuzzle(targets=targets, sprites=sprites)


# ── plan synthesis ──────────────────────────────────────────────────────────


def find_covering_offset(sprite: Sprite, points: list[TargetPoint]) -> tuple[int, int] | None:
    """A translation ``(dx, dy)`` of ``sprite`` that covers every point in ``points``.

    Candidates are derived from the FIRST point only: every offset that would
    place SOME cell of the sprite exactly on that point (position-agnostic —
    no blind grid search over an arbitrary range). Each candidate is then
    verified against every remaining point. Returns the first that covers
    them all, or ``None`` when no single offset does (the puzzle may need a
    colour-changer, or a different/additional sprite — out of this module's
    scope, see its docstring). Pure / env-free.
    """
    if not points or not sprite.cells:
        return None
    tx0, ty0 = points[0].x, points[0].y
    candidates = {(tx0 - sx, ty0 - sy) for sx, sy in sprite.cells}
    for dx, dy in candidates:
        translated = {(sx + dx, sy + dy) for sx, sy in sprite.cells}
        if all((p.x, p.y) in translated for p in points):
            return (dx, dy)
    return None


def build_move_actions(
    dx: int, dy: int, dir_map: dict[int, tuple[int, int]], step: int
) -> list[int]:
    """Translate a pixel offset into simple action ids, using the MEASURED ``dir_map``.

    ``dir_map`` (action id -> measured (dx, dy) per press) and ``step`` come
    from a live probe (:func:`admorphiq.general_agent._step_cell_size` on the
    probed map) — action-id-to-direction is never assumed. Returns ``[]``
    when ``dx``/``dy`` is not a clean multiple of ``step`` (an unreachable
    offset — the caller should not attempt it) or when a needed direction was
    never observed during calibration. Pure / env-free.
    """
    if step <= 0 or dx % step != 0 or dy % step != 0:
        return []
    pos_x = next((aid for aid, (sx, sy) in dir_map.items() if sx > 0 and sy == 0), None)
    neg_x = next((aid for aid, (sx, sy) in dir_map.items() if sx < 0 and sy == 0), None)
    pos_y = next((aid for aid, (sx, sy) in dir_map.items() if sy > 0 and sx == 0), None)
    neg_y = next((aid for aid, (sx, sy) in dir_map.items() if sy < 0 and sx == 0), None)
    n_x, n_y = abs(dx) // step, abs(dy) // step
    x_aid = pos_x if dx > 0 else neg_x
    y_aid = pos_y if dy > 0 else neg_y
    if n_x > 0 and x_aid is None:
        return []
    if n_y > 0 and y_aid is None:
        return []
    actions: list[int] = []
    if x_aid is not None:
        actions.extend([x_aid] * n_x)
    if y_aid is not None:
        actions.extend([y_aid] * n_y)
    return actions
