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

from collections import deque
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

    ops: list[tuple[str, int, int]]  # (kind "L"aunch / "A"rrow, ring_position, colour)
    swatch_x: dict[int, int]
    start_pos: int = 0


def _detect_swatches(layer: np.ndarray, bg: int) -> dict[int, int]:
    """Top-row colour swatches: colour -> centroid x (click at (x+? ,4)).

    Restricted to x>=20: the swatch strip sits top-centre/right, while the target
    reference is top-LEFT (x<20) — without this a stray target-colour pixel in
    the top-left was mis-read as that colour's swatch (measured CD82 L2).
    """
    sw: dict[int, int] = {}
    for c in connected_components(layer, bg):
        if c["cy"] < 9 and 6 <= c["size"] <= 40 and c["cx"] >= 20 and c["color"] not in (bg, _PADDING):
            sw.setdefault(int(c["color"]), int(round(c["cx"])))
    return sw


def _region_mask(pos: int) -> np.ndarray:
    """The 10x10 boolean mask a launch from ring ``pos`` paints (from the game's
    own region geometry, verification-only): 0/2/4/6 = top/right/bottom/left
    halves; 1/3/5/7 = upper-right/lower-right/lower-left/upper-left triangles."""
    m = np.zeros((10, 10), dtype=bool)
    if pos == 0:
        m[0:5, :] = True
    elif pos == 4:
        m[5:10, :] = True
    elif pos == 6:
        m[:, 0:5] = True
    elif pos == 2:
        m[:, 5:10] = True
    elif pos == 1:
        for i in range(10):
            m[i, i:10] = True
    elif pos == 3:
        for i in range(10):
            m[i, 9 - i : 10] = True
    elif pos == 5:
        for i in range(10):
            m[i, 0 : i + 1] = True
    elif pos == 7:
        for i in range(10):
            m[i, 0 : 10 - i] = True
    return m


def _arrow_mask(pos: int) -> np.ndarray:
    """The 10x10 patch an ARROW-CLICK (ACTION6) paints at half-position ``pos``
    (0/2/4/6) — a small centre-edge patch, distinct from a launch's half. From
    the game geometry (verification-only)."""
    m = np.zeros((10, 10), dtype=bool)
    if pos == 0:
        m[0:3, 3:7] = True
    elif pos == 4:
        m[7:10, 3:7] = True
    elif pos == 6:
        m[3:7, 0:3] = True
    elif pos == 2:
        m[3:7, 7:10] = True
    return m


_MASKS = {p: _region_mask(p) for p in range(8)}
_ARROW_MASKS = {p: _arrow_mask(p) for p in (0, 2, 4, 6)}
# Fixed click coords for the arrow op at each half-position (game display geometry).
ARROW_COORDS: dict[int, tuple[int, int]] = {0: (32, 20), 2: (51, 38), 4: (32, 57), 6: (14, 38)}
# The win check ignores the two main diagonals (the game compares canvas==target
# only off the anti-diagonals) — so the planner matches off-diagonal cells only.
_OFFDIAG = np.ones((10, 10), dtype=bool)
for _i in range(10):
    _OFFDIAG[_i, _i] = False
    _OFFDIAG[_i, 9 - _i] = False


def _matches(canvas: np.ndarray, target: np.ndarray) -> bool:
    return bool(np.array_equal(canvas[_OFFDIAG], target[_OFFDIAG]))


def _read_10x10(layer: np.ndarray, x0: int, y0: int) -> np.ndarray | None:
    h, w = layer.shape
    if x0 < 0 or y0 < 0 or x0 + 10 > w or y0 + 10 > h:
        return None
    return layer[y0 : y0 + 10, x0 : x0 + 10]


def _is_uniform(a: np.ndarray) -> bool:
    return len(set(a.flatten().tolist())) == 1


def plan_paint(
    target: np.ndarray, canvas_start: int, colors: list[int] | None = None, max_depth: int = 4
) -> list[tuple[str, int, int]]:
    """Shortest paint-op sequence that produces ``target`` from a uniform canvas.

    BFS over paint ops — ``("L", pos, colour)`` launches (halves 0/2/4/6, diagonal
    triangles 1/3/5/7) and ``("A", pos, colour)`` arrow-clicks (small centre-edge
    patches at 0/2/4/6). Each op overwrites its region; later ops paint over
    earlier; the result is matched against the target on the OFF-DIAGONAL cells
    only (the game's win check ignores the two main diagonals). Solves CD82 L1
    (half-split), L2 (diagonal + multi-launch), and L3 (launches + an arrow).
    ``colors`` defaults to the target's own palette. Returns ``[]`` when already
    matching or when no sequence up to ``max_depth`` matches (the caller defers).
    """
    if target.shape != (10, 10):
        return []
    if colors is None:
        colors = sorted(set(target.flatten().tolist()))
    start = np.full((10, 10), canvas_start, dtype=target.dtype)
    if _matches(start, target):
        return []
    op_masks = [("L", p, _MASKS[p]) for p in range(8)]
    op_masks += [("A", p, _ARROW_MASKS[p]) for p in (0, 2, 4, 6)]
    frontier: deque[tuple[np.ndarray, list[tuple[str, int, int]]]] = deque([(start, [])])
    seen = {start.tobytes()}
    while frontier:
        canvas, seq = frontier.popleft()
        if len(seq) >= max_depth:
            continue
        for kind, pos, mask in op_masks:
            for col in colors:
                nxt = canvas.copy()
                nxt[mask] = col
                if _matches(nxt, target):
                    return [*seq, (kind, pos, col)]
                key = nxt.tobytes()
                if key not in seen:
                    seen.add(key)
                    frontier.append((nxt, [*seq, (kind, pos, col)]))
    return []


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
    # TARGET: bounding box of coloured components in the top-left quadrant. The
    # size floor is small (8) because a deeper level's target has thin diagonal
    # colour bands (<40px) — measured CD82 L3: a 40px floor dropped them and the
    # whole target went undetected.
    tcomps = [
        c for c in comps
        if c["cx"] < 20 and c["cy"] < 20 and c["size"] >= 8 and c["color"] not in (bg, _PADDING)
    ]
    if not tcomps:
        return None
    tx0 = min(min(col for _, col in c["cells"]) for c in tcomps)
    ty0 = min(min(r for r, _ in c["cells"]) for c in tcomps)
    target = _read_10x10(layer, tx0, ty0)
    canvas = _read_10x10(layer, canvas_xy[0], canvas_xy[1])
    if target is None or canvas is None or not _is_uniform(canvas):
        return None
    swatch_x = _detect_swatches(layer, bg)
    ops = plan_paint(target, int(canvas[0, 0]), colors=sorted(swatch_x))
    if not ops:
        return None
    if any(col not in swatch_x for _kind, _pos, col in ops):
        return None
    return PaintLayout(ops=ops, swatch_x=swatch_x)


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
