"""The shared perception grammar: how a board is cut into pieces.

⛔ Why this module exists, recorded 2026-08-27 after it cost a 20x regression. Every tool was
deriving its own answer to the same four questions — what is a region, what is a tile, what is the
lattice step, what is chrome — and each answer was tuned on ONE board. Six such heuristics
accumulated inside one tool, and loosening them so a new board could be read made that tool fire
on a different game's lattice and steal the turn from the tool that could solve it:
`ft09 0.4762 -> 0.0476`, mean `0.0211 -> 0.0037`, while the loosened tool remained perfect on its
own game. Segmentation is shared machinery; it belongs in one place with its own tests, so a fix
for one board cannot silently loosen every tool at once.

Nothing here knows about any game. Everything is derived from the frame.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

__all__ = [
    "Cell",
    "background",
    "components",
    "peel_containers",
    "uniform_blocks",
    "square_regions",
    "modal_pitch",
    "candidate_pitches",
    "edge_band",
    "board_changed",
]

Cell = tuple[int, int]

# The frame's chrome sits pinned to its edge. Deliberately tiny — an earlier version of a
# related test excused real board content as overlay by taking a generous margin.
_MARGIN_DIV = 16


def background(g: Any, how_many: int = 1) -> set[int]:
    """The commonest colour(s), which is what "not a piece" means on these boards."""
    return {c for c, _ in Counter(int(v) for row in g for v in row).most_common(how_many)}


def components(g: Any, blocked: set[int]) -> list[list[Cell]]:
    """4-connected regions of cells whose colour is not blocked."""
    n = len(g)
    seen = [[False] * n for _ in range(n)]
    out: list[list[Cell]] = []
    for y in range(n):
        for x in range(n):
            if int(g[y][x]) in blocked or seen[y][x]:
                continue
            stack = [(y, x)]
            seen[y][x] = True
            cells: list[Cell] = []
            while stack:
                cy, cx = stack.pop()
                cells.append((cy, cx))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < n and 0 <= nx < n and not seen[ny][nx] and int(g[ny][nx]) not in blocked:
                        seen[ny][nx] = True
                        stack.append((ny, nx))
            out.append(cells)
    return out


def peel_containers(g: Any, comps: list[list[Cell]], blocked: set[int]) -> list[tuple[list[Cell], bool]]:
    """Split any component far larger than its siblings by dropping its own colour.

    A frame touches every tile it encloses, so plain connectivity returns the whole board as one
    blob. The flag says whether a piece came OUT of a container, which is not bookkeeping: a game
    that frames one panel is saying which panel is live, and clicking a dead panel is fatal on at
    least one sample game.
    """
    if len(comps) < 2:
        return [(c, False) for c in comps]
    sizes = sorted(len(c) for c in comps)
    typical = sizes[len(sizes) // 2]
    out: list[tuple[list[Cell], bool]] = []
    for c in comps:
        if len(c) <= 4 * typical:
            out.append((c, False))
            continue
        wall = Counter(int(g[y][x]) for y, x in c).most_common(1)[0][0]
        inner = {(y, x) for y, x in c}
        masked = [
            [int(g[y][x]) if (y, x) in inner and int(g[y][x]) != wall else -1 for x in range(len(g))]
            for y in range(len(g))
        ]
        sub = components(masked, blocked | {-1, wall})
        out.extend([(s, True) for s in sub] if sub else [(c, False)])
    return out


def uniform_blocks(g: Any, side: int, ignore: set[int] | None = None) -> dict[Cell, int]:
    """Top-left corners of every `side`x`side` block that is one flat colour."""
    n = len(g)
    skip = background(g, 2) if ignore is None else ignore
    found: dict[Cell, int] = {}
    for y in range(n - side + 1):
        for x in range(n - side + 1):
            first = int(g[y][x])
            if first in skip:
                continue
            if all(int(g[y + i][x + j]) == first for i in range(side) for j in range(side)):
                found[(y, x)] = first
    corners: dict[Cell, int] = {}
    for (y, x) in sorted(found):
        if not any((y - dy, x - dx) in found for dy in range(side) for dx in range(side) if dy or dx):
            corners[(y, x)] = found[(y, x)]
    return corners


def square_regions(g: Any, min_side: int = 4) -> dict[Cell, dict[str, Any]]:
    """Solid square regions of the SAME size, with containers peeled and flagged.

    The size kept is the commonest one: a board of tiles is many identical tiles, and anything of
    another size is furniture.
    """
    bg = background(g)
    found: dict[Cell, dict[str, Any]] = {}
    for cells, framed in peel_containers(g, components(g, bg), bg):
        y0 = min(q[0] for q in cells)
        x0 = min(q[1] for q in cells)
        h = max(q[0] for q in cells) - y0 + 1
        w = max(q[1] for q in cells) - x0 + 1
        if h != w or h < min_side or len(cells) != h * w:
            continue
        found[(y0, x0)] = {"size": h, "colours": {int(g[y][x]) for y, x in cells}, "framed": framed}
    if not found:
        return {}
    side = Counter(t["size"] for t in found.values()).most_common(1)[0][0]
    return {o: t for o, t in found.items() if t["size"] == side}


def candidate_pitches(origins: list[Cell], side: int, limit: int = 4) -> list[int]:
    """Every spacing the pieces actually exhibit, commonest first."""
    gaps: Counter[int] = Counter()
    for axis in (0, 1):
        vals = sorted({o[axis] for o in origins})
        for a, b in zip(vals, vals[1:]):
            if b - a >= side:
                gaps[b - a] += 1
    return [g for g, _ in gaps.most_common(limit)]


def modal_pitch(origins: list[Cell], side: int = 0) -> int:
    """The lattice step is the COMMONEST gap between origins, never the smallest.

    Measured: taking the minimum read the 2-pixel offset between two unrelated panels as the
    board's pitch, and every neighbour lookup then missed.
    """
    found = candidate_pitches(origins, side, limit=1)
    return found[0] if found else 0


def edge_band(shape: tuple[int, int], margin_div: int = _MARGIN_DIV) -> np.ndarray:
    """Boolean mask of the outer band, where a counter or timer lives."""
    h, w = shape
    m = max(1, min(h, w) // margin_div)
    mask = np.zeros(shape, dtype=bool)
    mask[:m, :] = mask[-m:, :] = True
    mask[:, :m] = mask[:, -m:] = True
    return mask


def board_changed(prev: np.ndarray, cur: np.ndarray, margin_div: int = _MARGIN_DIV) -> bool:
    """Did the BOARD change, ignoring an edge-pinned counter or timer?

    A frequency test cannot see these: a bar that shrinks or a counter that marches touches each
    cell once, so no cell reaches a "changes under most actions" threshold. Position identifies
    them instead.
    """
    diff = prev != cur
    if not diff.any():
        return False
    h, w = diff.shape
    m = max(1, min(h, w) // margin_div)
    return bool(diff[m:h - m, m:w - m].any())
