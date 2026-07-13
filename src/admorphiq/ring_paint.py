"""Frame-only RING-PAINT solver (CD82-class efficiency capability).

A movement+click paint puzzle: a basket navigates an 8-position RING around a
10x10 CANVAS (ACTION1-4), selects a colour by clicking a top swatch (ACTION6),
then LAUNCHES (ACTION5) to paint one region of the canvas — the region is fixed
per ring position (0/2/4/6 = top/right/bottom/left halves; 1/3/5/7 = diagonal
triangles). A separate 10x10 TARGET panel shows the pattern the canvas must
match; the level clears when canvas == target.

The deployed frame-only path currently clears CD82 L1 only by BRUTE-FORCE
exploration (~2000+ actions, RHAE ≈ 0.0005). This module computes the exact
launch plan from the target so an L1-class board clears in ~8 actions — a ~100x
RHAE gain on an already-cleared game. Fully observation-driven on the canonical
layer: no game-id / internal reads.

Scope: half-split L1-class targets (a two-colour top/bottom or left/right split
from a uniform canvas). Diagonal targets + multi-launch deeper levels are a
future extension — the planner returns an empty plan (the caller defers) when the
target is not a clean half-split, so nothing regresses.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .general_agent import connected_components

# Ring position -> (row, col) on the 3x3 grid (centre 1,1 excluded). ACTION1-4 =
# up/down/left/right move the basket between adjacent ring cells.
POS_GRID: dict[int, tuple[int, int]] = {
    0: (0, 1), 1: (0, 2), 2: (1, 2), 3: (2, 2),
    4: (2, 1), 5: (2, 0), 6: (1, 0), 7: (0, 0),
}
_CANVAS_MIN_Y = 22  # canvas sits in the lower half; target in the top-left
_PADDING = 4        # PADDING_COLOR border, never a swatch/target/canvas colour


@dataclass
class PaintLayout:
    """A detected ring-paint layout ready for planning/execution.

    ``launches`` is the ordered list of ``(ring_position, colour)`` operations;
    ``swatch_x`` maps a colour to the x to click (at y=4) to select it;
    ``start_pos`` is the basket's starting ring position (0).
    """

    launches: list[tuple[int, int]]
    swatch_x: dict[int, int]
    start_pos: int = 0


def _detect_swatches(layer: np.ndarray, bg: int) -> dict[int, int]:
    """Top-row colour swatches: colour -> centroid x (click at (x+? ,4))."""
    sw: dict[int, int] = {}
    for c in connected_components(layer, bg):
        if c["cy"] < 9 and 6 <= c["size"] <= 40 and c["color"] not in (bg, _PADDING):
            sw.setdefault(int(c["color"]), int(round(c["cx"])))
    return sw


def _read_10x10(layer: np.ndarray, x0: int, y0: int) -> np.ndarray | None:
    h, w = layer.shape
    if x0 < 0 or y0 < 0 or x0 + 10 > w or y0 + 10 > h:
        return None
    return layer[y0 : y0 + 10, x0 : x0 + 10]


def _is_uniform(a: np.ndarray) -> bool:
    return len(set(a.flatten().tolist())) == 1


def plan_paint(target: np.ndarray, canvas_start: int) -> list[tuple[int, int]]:
    """Half-split planner: launches to paint ``target`` from a uniform canvas.

    Handles a clean two-colour horizontal (top/bottom) or vertical (left/right)
    split — the L1 class. Returns ``[]`` for anything else (diagonals, multi-band
    targets) so the caller defers to the existing path rather than mis-painting.
    """
    if target.shape != (10, 10):
        return []
    launches: list[tuple[int, int]] = []
    top, bot = target[0:5], target[5:10]
    left, right = target[:, 0:5], target[:, 5:10]
    if _is_uniform(top) and _is_uniform(bot):
        for pos, reg in ((0, top), (4, bot)):
            col = int(reg[0, 0])
            if col != canvas_start:
                launches.append((pos, col))
    elif _is_uniform(left) and _is_uniform(right):
        for pos, reg in ((6, left), (2, right)):
            col = int(reg[0, 0])
            if col != canvas_start:
                launches.append((pos, col))
    return launches


def detect_paint_layout(layer: np.ndarray, background: int) -> PaintLayout | None:
    """Detect a ring-paint layout and return the launch plan, or None.

    Signature: a ~10x10 uniform CANVAS block in the lower half + a patterned
    10x10 TARGET in the top-left + top-row swatches. Returns None when any piece
    is missing or the target is not a plannable half-split (so the caller defers).
    """
    if layer.size == 0:
        return None
    bg = int(background)
    # CANVAS: a ~10x10 solid block, lower half.
    canvas_xy: tuple[int, int] | None = None
    comps = connected_components(layer, bg)
    for c in comps:
        rows = [r for r, _ in c["cells"]]
        cols = [col for _, col in c["cells"]]
        w = max(cols) - min(cols) + 1
        h = max(rows) - min(rows) + 1
        if 8 <= w <= 12 and 8 <= h <= 12 and c["size"] >= 60 and c["cy"] > _CANVAS_MIN_Y:
            canvas_xy = (min(cols), min(rows))
            break
    if canvas_xy is None:
        return None
    # TARGET: bounding box of coloured components in the top-left quadrant.
    tcomps = [
        c for c in comps
        if c["cx"] < 20 and c["cy"] < 20 and c["size"] >= 40 and c["color"] not in (bg, _PADDING)
    ]
    if not tcomps:
        return None
    tx0 = min(min(col for _, col in c["cells"]) for c in tcomps)
    ty0 = min(min(r for r, _ in c["cells"]) for c in tcomps)
    target = _read_10x10(layer, tx0, ty0)
    canvas = _read_10x10(layer, canvas_xy[0], canvas_xy[1])
    if target is None or canvas is None or not _is_uniform(canvas):
        return None
    launches = plan_paint(target, int(canvas[0, 0]))
    if not launches:
        return None
    swatch_x = _detect_swatches(layer, bg)
    if any(col not in swatch_x for _pos, col in launches):
        return None
    return PaintLayout(launches=launches, swatch_x=swatch_x)


def nav_path(cur: int, tgt: int) -> list[int]:
    """BFS the basket from ring position ``cur`` to ``tgt`` (ACTION1-4), avoiding
    the excluded 3x3 centre. Returns the action-id path."""
    from collections import deque

    if cur == tgt:
        return []
    cr, cc = POS_GRID[cur]
    tr, tc = POS_GRID[tgt]
    q: deque[tuple[int, int, list[int]]] = deque([(cr, cc, [])])
    seen = {(cr, cc)}
    while q:
        r, c, path = q.popleft()
        if (r, c) == (tr, tc):
            return path
        for dr, dc, a in ((-1, 0, 1), (1, 0, 2), (0, -1, 3), (0, 1, 4)):
            nr, nc = r + dr, c + dc
            if 0 <= nr <= 2 and 0 <= nc <= 2 and (nr, nc) != (1, 1) and (nr, nc) not in seen:
                seen.add((nr, nc))
                q.append((nr, nc, path + [a]))
    return []
