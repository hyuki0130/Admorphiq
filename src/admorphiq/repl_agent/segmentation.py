"""Segmenter + tracker for the code-REPL agent (R55 module 2).

Turns a raw 64x64 grid into a set of tracked objects with STABLE ids across
frames, plus the per-turn CHANGE events (appear / disappear / move / recolor /
split / merge) and structural relations (containment / adjacency) the turn packet
needs. Built on the repo's generic segmentation primitive
(``tools/base.connected_components``) — not a rewrite; ``FrameAnalyzer`` remains
the complementary action-semantics analyzer.

Stable identity uses a translation-invariant shape hash + colour as the primary
key (so an object keeps its id when it merely moves), with spatial overlap (cell
intersection) resolving recolor / split / merge. Each object exposes one VERIFIED
interior click coordinate (an on-object cell, preferring a fully-surrounded one),
its hole count, boundary contact, containment, adjacency, and a compact
change-history string.

No model calls, no heavy deps.
"""

from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from admorphiq.tools.base import connected_components


def shape_hash(cells: list[tuple[int, int]]) -> str:
    """Translation-invariant 10-hex digest of a cell mask.

    Cells are shifted so the top-left of their bbox is (0, 0), then sorted and
    hashed — so the same shape at any position hashes identically (the property
    that keeps an object's id stable as it moves).
    """
    if not cells:
        return ""
    y0 = min(c[0] for c in cells)
    x0 = min(c[1] for c in cells)
    norm = sorted((y - y0, x - x0) for y, x in cells)
    return hashlib.md5(str(norm).encode()).hexdigest()[:10]


def _count_holes(cells: list[tuple[int, int]]) -> int:
    """Number of background regions fully enclosed by the object's mask."""
    if not cells:
        return 0
    ys = [c[0] for c in cells]
    xs = [c[1] for c in cells]
    y0, x0, y1, x1 = min(ys), min(xs), max(ys), max(xs)
    h, w = y1 - y0 + 3, x1 - x0 + 3  # 1-cell border padding
    occ = np.zeros((h, w), dtype=bool)
    for y, x in cells:
        occ[y - y0 + 1, x - x0 + 1] = True
    # Flood-fill background from the padded border; anything unreached & empty
    # is an enclosed hole.
    bg_outer = np.zeros((h, w), dtype=bool)
    q: deque[tuple[int, int]] = deque([(0, 0)])
    bg_outer[0, 0] = True
    while q:
        cy, cx = q.popleft()
        for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
            if 0 <= ny < h and 0 <= nx < w and not bg_outer[ny, nx] and not occ[ny, nx]:
                bg_outer[ny, nx] = True
                q.append((ny, nx))
    holes = 0
    seen = bg_outer | occ
    for y in range(h):
        for x in range(w):
            if not seen[y, x]:
                holes += 1
                seen[y, x] = True
                q2: deque[tuple[int, int]] = deque([(y, x)])
                while q2:
                    cy, cx = q2.popleft()
                    for ny, nx in ((cy-1, cx), (cy+1, cx), (cy, cx-1), (cy, cx+1)):
                        if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx]:
                            seen[ny, nx] = True
                            q2.append((ny, nx))
    return holes


def _safe_click(cells: list[tuple[int, int]]) -> tuple[int, int]:
    """A verified interior cell (row, col): the on-object cell with the most
    on-object 4-neighbors (falls back to the centroid-nearest cell)."""
    cellset = set(cells)
    best = cells[0]
    best_deg = -1
    for y, x in cells:
        deg = sum((y + dy, x + dx) in cellset
                  for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)))
        if deg > best_deg:
            best_deg, best = deg, (y, x)
    return best


@dataclass
class SceneObject:
    """A tracked object with a stable id and structural descriptors."""

    id: str
    color: int
    cells: list[tuple[int, int]]
    bbox: tuple[int, int, int, int]  # y0, x0, y1, x1
    centroid: tuple[float, float]    # y, x
    area: int
    shape_hash: str
    holes: int = 0
    touches_boundary: bool = False
    contained_by: str | None = None
    adjacent: list[dict[str, Any]] = field(default_factory=list)
    change_history: list[str] = field(default_factory=list)
    safe_click: tuple[int, int] = (0, 0)


@dataclass
class Scene:
    """Result of one tracker update: objects, change events, and background."""

    objects: list[SceneObject]
    events: list[dict[str, Any]] = field(default_factory=list)
    background: int = 0

    def by_id(self, oid: str) -> SceneObject | None:
        for o in self.objects:
            if o.id == oid:
                return o
        return None


def _mk_object(comp: dict[str, Any], oid: str, grid_hw: tuple[int, int]) -> SceneObject:
    cells = [tuple(c) for c in comp["cells"]]
    h, w = grid_hw
    y0, x0, y1, x1 = comp["bbox"]
    touches = y0 == 0 or x0 == 0 or y1 == h - 1 or x1 == w - 1
    return SceneObject(
        id=oid,
        color=int(comp["color"]),
        cells=cells,
        bbox=tuple(comp["bbox"]),
        centroid=comp["centroid"],
        area=int(comp["size"]),
        shape_hash=shape_hash(cells),
        holes=_count_holes(cells),
        touches_boundary=bool(touches),
        safe_click=_safe_click(cells),
    )


def _bbox_contains(outer: tuple[int, int, int, int],
                   inner: tuple[int, int, int, int]) -> bool:
    return (outer[0] <= inner[0] and outer[1] <= inner[1]
            and outer[2] >= inner[2] and outer[3] >= inner[3]
            and outer != inner)


def _compute_relations(objects: list[SceneObject]) -> None:
    """Fill each object's ``contained_by`` and ``adjacent`` in place."""
    for a in objects:
        # containment: smallest strictly-enclosing object of a different color.
        best: SceneObject | None = None
        for b in objects:
            if b is a or b.color == a.color:
                continue
            if _bbox_contains(b.bbox, a.bbox):
                if best is None or b.area < best.area:
                    best = b
        a.contained_by = best.id if best else None
        # adjacency: any 4-neighbor cell of a belongs to b.
        acells = set(a.cells)
        adj: list[dict[str, Any]] = []
        for b in objects:
            if b is a:
                continue
            bcells = set(b.cells)
            touching = any((y + dy, x + dx) in bcells
                           for y, x in acells
                           for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)))
            if touching:
                dy = b.centroid[0] - a.centroid[0]
                dx = b.centroid[1] - a.centroid[1]
                if abs(dx) >= abs(dy):
                    direction = "right" if dx > 0 else "left"
                else:
                    direction = "down" if dy > 0 else "up"
                adj.append({"id": b.id, "direction": direction, "gap": 0})
        a.adjacent = sorted(adj, key=lambda d: d["id"])


class SceneTracker:
    """Segments frames and tracks objects with stable ids across updates.

    Primary match key is (shape_hash, color) — unique on both sides means the
    same object translated/static. Remaining objects are matched by cell overlap,
    which surfaces recolor (1:1, colour changed), split (1 prev : many curr), and
    merge (many prev : 1 curr). Unmatched current objects appeared; unmatched
    previous objects disappeared. Ids are ``o0, o1, …`` assigned on first sight
    and preserved thereafter.
    """

    def __init__(self, background: int | None = None) -> None:
        self._background = background
        self._objects: list[SceneObject] = []
        self._counter = 0
        self._history: dict[str, list[str]] = {}

    def _new_id(self) -> str:
        oid = f"o{self._counter}"
        self._counter += 1
        return oid

    def _note(self, oid: str, msg: str) -> None:
        hist = self._history.setdefault(oid, [])
        hist.append(msg)
        del hist[:-8]  # keep the last 8

    def update(self, frame: np.ndarray) -> Scene:
        grid = np.asarray(frame)
        comps = connected_components(grid, background=self._background)
        bg = self._resolve_background(grid)

        if not self._objects:
            objs = [_mk_object(c, self._new_id(), grid.shape) for c in comps]
            for o in objs:
                self._note(o.id, "appeared")
                o.change_history = list(self._history[o.id])
            _compute_relations(objs)
            self._objects = objs
            return Scene(objects=objs, events=[], background=bg)

        objs, events = self._match(comps, grid.shape)
        _compute_relations(objs)
        self._objects = objs
        return Scene(objects=objs, events=events, background=bg)

    def _resolve_background(self, grid: np.ndarray) -> int:
        if self._background is not None:
            return int(self._background)
        vals, counts = np.unique(grid, return_counts=True)
        return int(vals[int(counts.argmax())]) if len(vals) else 0

    def _match(self, comps: list[dict[str, Any]],
               grid_hw: tuple[int, int]) -> tuple[list[SceneObject], list[dict[str, Any]]]:
        curr = [_mk_object(c, "", grid_hw) for c in comps]
        prev = self._objects
        events: list[dict[str, Any]] = []
        matched_prev: set[int] = set()
        matched_curr: set[int] = set()

        # Step A — unique (shape_hash, color) match = translated/static object.
        def _index_by_key(objs: list[SceneObject]) -> dict[tuple[str, int], list[int]]:
            idx: dict[tuple[str, int], list[int]] = {}
            for i, o in enumerate(objs):
                idx.setdefault((o.shape_hash, o.color), []).append(i)
            return idx

        pidx, cidx = _index_by_key(prev), _index_by_key(curr)
        for key, plist in pidx.items():
            clist = cidx.get(key, [])
            if len(plist) == 1 and len(clist) == 1:
                pi, ci = plist[0], clist[0]
                self._assign(prev[pi], curr[ci])
                moved = curr[ci].centroid != prev[pi].centroid
                if moved:
                    dy = curr[ci].centroid[0] - prev[pi].centroid[0]
                    dx = curr[ci].centroid[1] - prev[pi].centroid[1]
                    self._note(curr[ci].id, f"moved ({dy:+.0f},{dx:+.0f})")
                    events.append({"type": "moved", "id": curr[ci].id,
                                   "from": _rc(prev[pi].centroid),
                                   "to": _rc(curr[ci].centroid)})
                curr[ci].change_history = list(self._history[curr[ci].id])
                matched_prev.add(pi)
                matched_curr.add(ci)

        # Step B — overlap-based for the rest (recolor / split / merge).
        overlaps = self._overlaps(prev, curr, matched_prev, matched_curr)
        # split: a prev overlapping >=2 curr.
        for pi, clist in overlaps["prev_to_curr"].items():
            if pi in matched_prev:
                continue
            targets = [ci for ci in clist if ci not in matched_curr]
            if len(targets) >= 2:
                for ci in targets:
                    curr[ci].id = self._new_id()
                    self._note(curr[ci].id, f"split from {prev[pi].id}")
                    curr[ci].change_history = list(self._history[curr[ci].id])
                    matched_curr.add(ci)
                matched_prev.add(pi)
                events.append({"type": "split", "id": prev[pi].id,
                               "into": [curr[ci].id for ci in targets]})
        # merge: a curr overlapping >=2 prev.
        for ci, plist in overlaps["curr_to_prev"].items():
            if ci in matched_curr:
                continue
            sources = [pi for pi in plist if pi not in matched_prev]
            if len(sources) >= 2:
                keep = prev[sources[0]]
                self._assign(keep, curr[ci])
                curr[ci].change_history = list(self._history.get(curr[ci].id, []))
                self._note(curr[ci].id,
                           f"merged {[prev[pi].id for pi in sources]}")
                curr[ci].change_history = list(self._history[curr[ci].id])
                for pi in sources:
                    matched_prev.add(pi)
                matched_curr.add(ci)
                events.append({"type": "merged",
                               "ids": [prev[pi].id for pi in sources],
                               "into": curr[ci].id})
        # 1:1 overlap leftover = recolor (or shape change in place).
        for pi, clist in overlaps["prev_to_curr"].items():
            if pi in matched_prev:
                continue
            targets = [ci for ci in clist if ci not in matched_curr]
            if len(targets) == 1:
                ci = targets[0]
                self._assign(prev[pi], curr[ci])
                if curr[ci].color != prev[pi].color:
                    self._note(curr[ci].id,
                               f"recolored {prev[pi].color}->{curr[ci].color}")
                    events.append({"type": "recolored", "id": curr[ci].id,
                                   "from": prev[pi].color, "to": curr[ci].color})
                curr[ci].change_history = list(self._history[curr[ci].id])
                matched_prev.add(pi)
                matched_curr.add(ci)

        # Step C — leftovers.
        for ci, o in enumerate(curr):
            if ci not in matched_curr:
                o.id = self._new_id()
                self._note(o.id, "appeared")
                o.change_history = list(self._history[o.id])
                events.append({"type": "appeared", "id": o.id})
        for pi, o in enumerate(prev):
            if pi not in matched_prev:
                events.append({"type": "disappeared", "id": o.id})

        return curr, events

    def _assign(self, prev_obj: SceneObject, curr_obj: SceneObject) -> None:
        """Carry the previous stable id + history onto the current object."""
        curr_obj.id = prev_obj.id
        self._history.setdefault(curr_obj.id, list(prev_obj.change_history))

    def _overlaps(self, prev: list[SceneObject], curr: list[SceneObject],
                  matched_prev: set[int], matched_curr: set[int]) -> dict[str, Any]:
        prev_sets = [set(o.cells) for o in prev]
        curr_sets = [set(o.cells) for o in curr]
        p2c: dict[int, list[int]] = {}
        c2p: dict[int, list[int]] = {}
        for pi in range(len(prev)):
            if pi in matched_prev:
                continue
            for ci in range(len(curr)):
                if ci in matched_curr:
                    continue
                if prev_sets[pi] & curr_sets[ci]:
                    p2c.setdefault(pi, []).append(ci)
                    c2p.setdefault(ci, []).append(pi)
        return {"prev_to_curr": p2c, "curr_to_prev": c2p}


def _rc(centroid: tuple[float, float]) -> list[int]:
    return [int(round(centroid[0])), int(round(centroid[1]))]
