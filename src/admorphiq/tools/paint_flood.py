"""Paint-flood tool — perception + click proposal for click-fills-a-region games.

Mechanic (measured in su15, R53): an ACTION6 click turns a connected background
region into one fill color (su15: dominant ``0 -> 5``, ~30-50 cells/click). This
tool is game-agnostic: it DETECTS the mechanic from observed transitions and,
given a current frame, PROPOSES click points that extend the fill toward the
uncovered target region. No game ids; triggers on frame features only.

This is the perception+planning CORE of the paint tool (the runtime model calls
these); wiring it into a full agent loop that clears a level end-to-end is the
next step and is measured separately.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

BACKGROUND = 0  # colour index 0 is background across ARC-AGI-3 frames


@dataclass(frozen=True)
class FloodMechanic:
    """What a click does, inferred from observations."""

    detected: bool
    fill_color: int          # the colour clicks paint (e.g. 5 in su15)
    mean_fill_cells: float   # typical region size a click fills
    confidence: float        # fraction of click transitions matching the mechanic


def detect_flood_mechanic(
    frames: np.ndarray, actions: np.ndarray, next_frames: np.ndarray,
    click_action_min_idx: int = 5,
) -> FloodMechanic:
    """Infer whether ACTION6 clicks flood-fill a region with a single colour.

    A click transition "matches" when its changed cells are DOMINATED (>=60%) by
    a single ``old -> new`` recolouring whose ``old`` is background. The fill
    colour is the most common such ``new``; confidence is the matching fraction
    over click transitions.
    """
    from collections import Counter
    fill_votes: Counter = Counter()
    sizes: list[int] = []
    matched = clicks = 0
    for i in range(len(actions)):
        if int(actions[i]) < click_action_min_idx:
            continue
        clicks += 1
        diff = frames[i] != next_frames[i]
        n = int(diff.sum())
        if n == 0:
            continue
        olds = frames[i][diff]
        news = next_frames[i][diff]
        bg = olds == BACKGROUND
        if not bg.any():
            continue
        new_bg = news[bg]
        vals, counts = np.unique(new_bg, return_counts=True)
        top = int(vals[counts.argmax()])
        if counts.max() >= 0.6 * n:
            matched += 1
            fill_votes[top] += 1
            sizes.append(n)
    if clicks == 0 or not fill_votes:
        return FloodMechanic(False, -1, 0.0, 0.0)
    fill_color = fill_votes.most_common(1)[0][0]
    conf = matched / clicks
    return FloodMechanic(
        detected=conf >= 0.5,
        fill_color=fill_color,
        mean_fill_cells=float(np.mean(sizes)) if sizes else 0.0,
        confidence=conf,
    )


def _components(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    """4-connected components of True cells (local; no external dep)."""
    seen = np.zeros_like(mask, dtype=bool)
    out: list[list[tuple[int, int]]] = []
    h, w = mask.shape
    for r in range(h):
        for c in range(w):
            if not mask[r, c] or seen[r, c]:
                continue
            comp: list[tuple[int, int]] = []
            q = deque([(r, c)])
            seen[r, c] = True
            while q:
                y, x = q.popleft()
                comp.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
            out.append(comp)
    return out


def propose_fill_clicks(
    frame: np.ndarray, fill_color: int, max_clicks: int = 14,
) -> list[tuple[int, int]]:
    """Propose ``(x, y)`` clicks to flood the remaining background regions.

    Targets the LARGEST still-background 4-connected components first (a click in
    each floods it), returning their centroids as ``(x=col, y=row)`` — the ACTION6
    convention. Regions already the fill colour are skipped. Deterministic:
    components sorted by descending size then position.
    """
    f = np.asarray(frame, dtype=np.int16)
    comps = _components(f == BACKGROUND)
    comps.sort(key=lambda comp: (-len(comp), comp[0]))
    clicks: list[tuple[int, int]] = []
    for comp in comps[:max_clicks]:
        ys = [p[0] for p in comp]
        xs = [p[1] for p in comp]
        cy, cx = int(round(np.mean(ys))), int(round(np.mean(xs)))
        # snap the centroid onto an actual background cell of this component
        if f[cy, cx] != BACKGROUND:
            cy, cx = comp[len(comp) // 2]
        clicks.append((cx, cy))
    return clicks
