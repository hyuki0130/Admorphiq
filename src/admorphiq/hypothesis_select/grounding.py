"""R95b STEP (iii): the runtime grounding service (harness-owned binding layer).

Codex finding 6 made concrete: the model NEVER enumerates repeated structure
(cells, incidence) or resolves click coordinates — the harness does, over a
live-or-replayed frame stream, with stable identity across recolouring and an
honest UNKNOWN on identity loss. This is the 60%-risk component of R95b.

Contract (frozen R95b BUILD PLAN v1, step iii):

* **Stable object IDs across recolouring** — a cell's identity is its geometric
  ANCHOR (bbox position) + footprint, never its colour. A cell that recolours
  keeps its ID. IDs are namespaced by a rebind EPOCH (``e{epoch}:c{k}``) so a
  stale ID from before a layout replacement can never silently alias a new cell.
* **Roles materialized as harness_measured structures** — for the cell-state
  family: the CELL enumeration (every ring-member / lattice cell + centroid),
  the GLYPH set (ft09 marker + compass reads), and the constraint INCIDENCE
  (cell -> covering glyph IDs). Parsed via the family-generic
  :mod:`admorphiq.hypothesis_select.parse` (NOT the quarantined adapters).
* **Click resolution at ACTION time** — ``resolve_click(cell_id)`` returns the
  cell's CURRENT ``(x, y)``; UNKNOWN if the binding is stale/lost.
* **Rebind on layout replacement** — a wholesale-change detection invalidates
  every ID, re-parses, and reports a ``RebindEvent`` under a new epoch.
* **Confidence + UNKNOWN** — every query returns ``Grounded(value, "high"|"low")``
  or ``UNKNOWN``. No silent guessing.
* **Ordered-cycle acquisition** — from observed same-cell click transitions,
  build the ordered colour transition function; report UNKNOWN until >= 2
  independent confirmations per edge (the min-probe rule).

Scope: grounding ONLY — no verifier, no compiler, no LLM.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from admorphiq.hypothesis_select.parse import (
    _cell_class,
    _discover_rings,
    _is_wholesale_change,
    _read_glyph_compass,
    _sc25_lattice,
)
from admorphiq.hypothesis_select.templates import (
    _sc25_cell_colour,
    _sc25_on_set,
    _sc25_preview_mark_colour,
    _sc25_read_target,
)

Grid = tuple[tuple[int, ...], ...]
Cell = tuple[int, int]  # (row, col)


class _Unknown:
    """The explicit 'identity lost / insufficient evidence' result. A distinct
    sentinel so an UNKNOWN can never be confused with a real value (e.g. a
    resolved coordinate ``(0, 0)`` or a falsey score)."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return "UNKNOWN"


UNKNOWN = _Unknown()


@dataclass(frozen=True)
class Grounded:
    """A resolved value with the harness's confidence (``"high"`` | ``"low"``)."""

    value: Any
    confidence: str


@dataclass(frozen=True)
class RebindEvent:
    """A layout replacement: every prior ID is invalid; ``epoch`` is the new
    namespace."""

    epoch: int
    reason: str


@dataclass
class _CellRecord:
    cell_id: str
    anchor: Cell  # bbox top-left — the recolour-stable identity
    centroid: tuple[float, float]
    bbox: tuple[int, int, int, int]
    colour: int
    confidence: str


@dataclass
class _GlyphRecord:
    glyph_id: str
    anchor: Cell
    marker: int
    centroid: tuple[float, float]


@dataclass
class _Structure:
    cells: dict[Cell, dict[str, Any]] = field(default_factory=dict)  # anchor -> {centroid,bbox,region}
    glyphs: dict[Cell, dict[str, Any]] = field(default_factory=dict)  # anchor -> {marker,centroid}
    # cell anchor -> list of (glyph anchor, ink shown at this cell, glyph marker)
    incidence: dict[Cell, list[tuple[Cell, int, int]]] = field(default_factory=dict)


_MIN_CYCLE_CONFIRMATIONS = 2  # the min-probe rule: >= 2 independent edge observations


def _to_grid(frame: Any) -> Grid:
    """A frame (numpy ``(H, W)`` / ``(L, H, W)``, or a nested sequence) as a plain
    ``(row, col)`` int grid. A 3-D frame keeps its LAST (canonical) layer."""
    arr = np.asarray(frame)
    if arr.ndim == 3:
        arr = arr[-1]
    return tuple(tuple(int(v) for v in row) for row in arr)


def _parse_structure(grid: Grid) -> _Structure:
    """Parse a frame into the cell-state family's roles, GENERICALLY (rings+glyphs
    for ft09, lattice for sc25), keyed by recolour-stable anchors. No game id."""
    struct = _Structure()
    # Ring discovery can read a sub-cell glyph tile off the frame edge on a
    # degenerate board (a lattice of very small cells whose spurious ring gaps
    # land on the boundary) — a latent parse edge case real button-sized boards
    # never hit. The grounding service must never crash on an arbitrary frame, so
    # a failed ring parse is treated as "no rings" and falls through to lattice.
    try:
        rings = _discover_rings(grid)
    except (IndexError, ValueError):
        rings = []
    if rings:
        for ring in sorted(rings, key=lambda r: (r["glyph_bbox"][0], r["glyph_bbox"][1])):
            gbb = ring["glyph_bbox"]
            g_anchor = (gbb[0], gbb[1])
            compass = _read_glyph_compass(grid, gbb)
            marker = compass["C"]
            struct.glyphs[g_anchor] = {
                "marker": marker,
                "centroid": ((gbb[0] + gbb[2]) / 2, (gbb[1] + gbb[3]) / 2),
            }
            for name, cell in ring["ring_cells"].items():
                anchor = (cell["bbox"][0], cell["bbox"][1])
                struct.cells[anchor] = {"centroid": cell["centroid"], "bbox": cell["bbox"]}
                # Record the ink the glyph shows at this cell's compass position,
                # so the verifier can apply a HYPOTHESIS's ink->operator map to it
                # (the harness supplies the raw ink; the model owns the mapping).
                struct.incidence.setdefault(anchor, []).append((g_anchor, compass[name], marker))
        return struct

    lattice = _sc25_lattice(grid)
    if lattice:
        for region in lattice["index"].values():
            anchor = (region["bbox"][0], region["bbox"][1])
            struct.cells[anchor] = {"centroid": region["centroid"], "bbox": region["bbox"]}
    return struct


class GroundingService:
    """A runtime grounding service over a frame stream. Constructor takes nothing
    game-specific; drive it with :meth:`feed` (frame stream) and/or
    :meth:`feed_transition` (transition stream), then query cells / glyphs /
    incidence / click resolution / the acquired ordered cycle."""

    def __init__(self) -> None:
        self._epoch = -1
        self._prev_grid: Optional[Grid] = None
        self._cells: dict[str, _CellRecord] = {}
        self._glyphs: dict[str, _GlyphRecord] = {}
        # cell_id -> tuple of (glyph_id, ink, marker, glyph_centroid)
        self._incidence: dict[str, tuple[tuple[str, int, int, tuple[float, float]], ...]] = {}
        self._bound: set[str] = set()
        self._rebinds: list[RebindEvent] = []
        self._cycle_obs: dict[tuple[int, int], int] = defaultdict(int)
        self._footprint_obs: dict[int, int] = defaultdict(int)  # click footprint -> count

    # ── frame stream ─────────────────────────────────────────────────────

    def feed(self, frame: Any) -> Optional[RebindEvent]:
        """Ingest a frame. Returns a ``RebindEvent`` iff a layout replacement was
        detected (new epoch, all prior IDs invalidated); otherwise ``None``."""
        grid = _to_grid(frame)
        rebind: Optional[RebindEvent] = None
        if self._epoch == -1:
            self._open_epoch(grid)
        elif self._prev_grid is not None and _is_wholesale_change(self._prev_grid, grid):
            rebind = self._open_epoch(grid, reason="layout_replaced")
        else:
            self._rebind_same_epoch(grid)
        self._prev_grid = grid
        return rebind

    def _open_epoch(self, grid: Grid, reason: str = "initial") -> Optional[RebindEvent]:
        self._epoch += 1
        struct = _parse_structure(grid)
        cell_anchors = sorted(struct.cells)
        anchor_to_id = {a: f"e{self._epoch}:c{k}" for k, a in enumerate(cell_anchors)}
        glyph_anchors = sorted(struct.glyphs)
        glyph_to_id = {a: f"e{self._epoch}:g{k}" for k, a in enumerate(glyph_anchors)}

        self._cells = {
            anchor_to_id[a]: _CellRecord(
                cell_id=anchor_to_id[a],
                anchor=a,
                centroid=struct.cells[a]["centroid"],
                bbox=struct.cells[a]["bbox"],
                colour=_cell_class(grid, struct.cells[a]["bbox"]),
                confidence="high",
            )
            for a in cell_anchors
        }
        self._glyphs = {
            glyph_to_id[a]: _GlyphRecord(
                glyph_id=glyph_to_id[a], anchor=a, marker=struct.glyphs[a]["marker"],
                centroid=struct.glyphs[a]["centroid"],
            )
            for a in glyph_anchors
        }
        self._incidence = {
            anchor_to_id[a]: tuple(
                (glyph_to_id[g], ink, marker, struct.glyphs[g]["centroid"])
                for (g, ink, marker) in sorted(
                    struct.incidence.get(a, []), key=lambda t: glyph_to_id[t[0]]
                )
            )
            for a in cell_anchors
        }
        self._bound = set(self._cells)
        if reason == "initial":
            return None
        event = RebindEvent(epoch=self._epoch, reason=reason)
        self._rebinds.append(event)
        return event

    def _rebind_same_epoch(self, grid: Grid) -> None:
        """Same epoch, next frame: re-parse and match candidates to existing cells
        by anchor (exact = high confidence, jittered within tolerance = low),
        updating colour/position and keeping IDs. Unmatched existing cells become
        unbound (their query returns UNKNOWN)."""
        struct = _parse_structure(grid)
        tol = self._match_tolerance()
        bound: set[str] = set()
        for record in self._cells.values():
            match, exact = self._nearest_anchor(record, struct.cells, tol)
            if match is None:
                record.confidence = "low"
                continue
            info = struct.cells[match]
            record.centroid = info["centroid"]
            record.bbox = info["bbox"]
            record.colour = _cell_class(grid, info["bbox"])
            record.confidence = "high" if exact else "low"
            bound.add(record.cell_id)
        # Keep glyph marker/positions current (markers are static, but recolour-safe).
        for record in self._glyphs.values():
            match, _exact = self._nearest_anchor(record, struct.glyphs, tol)
            if match is not None:
                record.marker = struct.glyphs[match]["marker"]
                record.centroid = struct.glyphs[match]["centroid"]
        self._bound = bound

    @staticmethod
    def _nearest_anchor(
        record: Any, candidates: dict[Cell, dict[str, Any]], tol: float
    ) -> tuple[Optional[Cell], bool]:
        if record.anchor in candidates:
            return record.anchor, True
        best: Optional[tuple[float, Cell]] = None
        cr, cc = record.centroid
        for anchor, info in candidates.items():
            rr, rc = info["centroid"]
            dist = abs(rr - cr) + abs(rc - cc)
            if dist <= tol and (best is None or dist < best[0]):
                best = (dist, anchor)
        return (best[1], False) if best is not None else (None, False)

    def _match_tolerance(self) -> float:
        centroids = [rec.centroid for rec in self._cells.values()]
        if len(centroids) < 2:
            return 3.0
        gaps = [
            abs(a[0] - b[0]) + abs(a[1] - b[1])
            for i, a in enumerate(centroids)
            for b in centroids[i + 1 :]
        ]
        return max(1.0, min(gaps) / 2.0)

    # ── transition stream (drives ID tracking + cycle acquisition) ────────

    def feed_transition(self, before: Any, action: int, xy: tuple[int, int], after: Any) -> None:
        """Ingest one transition: advance the frame stream (before then after) and,
        for an ACTION6 click that hits a cell, record the observed colour edge for
        the ordered-cycle acquisition."""
        self.feed(before)
        before_grid = _to_grid(before)
        after_grid = _to_grid(after)
        # A wholesale board replacement (a decoy->reveal trigger or a level
        # boundary) is NOT a same-cell colour transition: the "cell" at the click
        # xy is a DIFFERENT physical cell before vs after, so recording its colour
        # change as a cycle edge is a mis-attribution (measured: every spurious
        # ft09 L3 12->8 edge is exactly such a wholesale trigger click). Only a
        # non-wholesale click advances a cell along its own cycle.
        if action == 6 and not _is_wholesale_change(before_grid, after_grid):
            footprint = sum(
                1
                for cid in self._bound
                if _cell_class(before_grid, self._cells[cid].bbox)
                != _cell_class(after_grid, self._cells[cid].bbox)
            )
            self._footprint_obs[footprint] += 1
            cell = self._cell_at_xy(xy)
            if cell is not None:
                cb = _cell_class(before_grid, cell.bbox)
                ca = _cell_class(after_grid, cell.bbox)
                if cb != ca:
                    self._cycle_obs[(cb, ca)] += 1
        self.feed(after)

    def _cell_at_xy(self, xy: tuple[int, int]) -> Optional[_CellRecord]:
        """The bound cell a click at ``xy = (x, y)`` lands on — by bbox
        CONTAINMENT first (a click falls inside its cell's footprint), then the
        nearest centroid within a cell-sized tolerance (a click just off a small
        cell). Nearest-centroid alone is wrong: a click on a wide cell's edge is
        several pixels from its centroid, more than the inter-cell spacing."""
        x, y = xy
        row, col = y, x
        for cid in self._bound:
            r0, c0, r1, c1 = self._cells[cid].bbox
            if r0 <= row <= r1 and c0 <= col <= c1:
                return self._cells[cid]
        tol = self._cell_span()
        best: Optional[tuple[float, _CellRecord]] = None
        for cid in self._bound:
            rec = self._cells[cid]
            dist = abs(rec.centroid[0] - row) + abs(rec.centroid[1] - col)
            if dist <= tol and (best is None or dist < best[0]):
                best = (dist, rec)
        return best[1] if best is not None else None

    def _cell_span(self) -> float:
        """A generous click-to-cell tolerance = the largest bound cell's bbox
        extent (so a click anywhere on/near a cell resolves to it)."""
        span = 3.0
        for cid in self._bound:
            r0, c0, r1, c1 = self._cells[cid].bbox
            span = max(span, float(r1 - r0 + 1), float(c1 - c0 + 1))
        return span

    # ── queries (Grounded | UNKNOWN, never a silent guess) ────────────────

    @property
    def epoch(self) -> int:
        return self._epoch

    @property
    def rebind_events(self) -> tuple[RebindEvent, ...]:
        return tuple(self._rebinds)

    def cells(self) -> Any:
        """The current cell enumeration: ``Grounded(list[(cell_id, centroid)], conf)``
        over the bound cells, or ``UNKNOWN`` when no structure is grounded. Overall
        confidence is ``low`` if any bound cell is low-confidence."""
        if not self._bound:
            return UNKNOWN
        listing = [
            (cid, self._cells[cid].centroid) for cid in sorted(self._bound)
        ]
        conf = "low" if any(self._cells[cid].confidence == "low" for cid in self._bound) else "high"
        return Grounded(listing, conf)

    def glyphs(self) -> Any:
        """The glyph set: ``Grounded(list[(glyph_id, marker, centroid)], "high")`` or
        ``UNKNOWN`` when the family has no glyphs (e.g. a lattice-only board)."""
        if not self._glyphs:
            return UNKNOWN
        listing = [
            (g.glyph_id, g.marker, g.centroid) for g in sorted(self._glyphs.values(), key=lambda r: r.glyph_id)
        ]
        return Grounded(listing, "high")

    def incidence(self, cell_id: str) -> Any:
        """The covering-glyph evidence for ``cell_id``:
        ``Grounded(tuple[(glyph_id, ink, marker, glyph_centroid)], "high")`` — the
        raw ink each covering glyph shows at this cell (the harness supplies the
        ink; a hypothesis owns the ink->operator mapping). ``UNKNOWN`` for an
        unknown/stale cell."""
        if not self._id_current(cell_id) or cell_id not in self._incidence:
            return UNKNOWN
        return Grounded(self._incidence[cell_id], "high")

    def cell_colour(self, cell_id: str) -> Any:
        """The bound cell's current colour, or ``UNKNOWN`` if stale/unbound."""
        if not self._id_current(cell_id) or cell_id not in self._cells or cell_id not in self._bound:
            return UNKNOWN
        return Grounded(self._cells[cell_id].colour, self._cells[cell_id].confidence)

    def observed_footprints(self) -> Any:
        """The distribution of click FOOTPRINTS observed so far (how many cells a
        click changed) as ``Grounded(dict[int, count], conf)``, or ``UNKNOWN`` with
        no observations. Confidence is ``low`` until >= 2 clicks are seen (the
        min-probe rule) — a transition-model footprint claim must not be judged on
        one click."""
        if not self._footprint_obs:
            return UNKNOWN
        total = sum(self._footprint_obs.values())
        return Grounded(dict(self._footprint_obs), "high" if total >= _MIN_CYCLE_CONFIRMATIONS else "low")

    def pattern_evidence(self) -> Any:
        """For a lattice/preview board (the pattern-reference family member), the
        current-frame match facts a hypothesis's preview interpretation is judged
        against: ``Grounded({"matches_xor", "matches_absolute", "cells_matching",
        "total"}, "high")`` — or ``UNKNOWN`` when there is no lattice/readable
        preview (e.g. a glyph board or an unsettled frame)."""
        grid = self._prev_grid
        if grid is None:
            return UNKNOWN
        lattice = _sc25_lattice(grid)
        if lattice is None:
            return UNKNOWN
        target = _sc25_read_target(grid, lattice)
        if target is None:
            return UNKNOWN
        on_set = _sc25_on_set(grid, lattice)
        mark = _sc25_preview_mark_colour(grid, lattice)
        absolute_on = (
            frozenset(
                k for k, region in lattice["index"].items() if _sc25_cell_colour(grid, region) == mark
            )
            if mark is not None
            else frozenset()
        )
        cells_matching = sum(1 for k in lattice["index"] if (k in on_set) == (k in target))
        return Grounded(
            {
                "matches_xor": on_set == target,
                "matches_absolute": absolute_on == target,
                "cells_matching": cells_matching,
                "total": len(lattice["index"]),
            },
            "high",
        )

    def resolve_click(self, cell_id: str) -> Any:
        """The cell's CURRENT ``(x, y)`` click coordinate as ``Grounded((x, y), conf)``,
        or ``UNKNOWN`` if the ID is from a stale epoch, unknown, or not bound in the
        latest frame (identity lost)."""
        if not self._id_current(cell_id) or cell_id not in self._cells or cell_id not in self._bound:
            return UNKNOWN
        rec = self._cells[cell_id]
        x = int(round(rec.centroid[1]))
        y = int(round(rec.centroid[0]))
        return Grounded((x, y), rec.confidence)

    def _id_current(self, cell_id: str) -> bool:
        """Whether ``cell_id`` belongs to the CURRENT epoch (a stale ID from before a
        rebind can never alias into this epoch)."""
        return cell_id.startswith(f"e{self._epoch}:")

    def get_ordered_cycle(self) -> Any:
        """The acquired ordered colour cycle as ``Grounded(tuple[int], "high")``, or
        ``UNKNOWN`` until every edge has >= 2 independent confirmations AND the
        confirmed edges form a single unambiguous cycle (the min-probe rule)."""
        confirmed = {
            edge for edge, count in self._cycle_obs.items() if count >= _MIN_CYCLE_CONFIRMATIONS
        }
        if not confirmed:
            return UNKNOWN
        successor: dict[int, int] = {}
        for cb, ca in confirmed:
            if cb in successor and successor[cb] != ca:
                return UNKNOWN  # ambiguous: a colour with two confirmed successors
            successor[cb] = ca
        colours = set(successor) | set(successor.values())
        if set(successor) != colours:  # some colour has no outgoing confirmed edge
            return UNKNOWN
        start = min(colours)
        order = [start]
        cur = successor[start]
        while cur != start:
            if cur in order:
                return UNKNOWN  # a sub-loop that doesn't cover all colours
            order.append(cur)
            cur = successor[cur]
        if len(order) != len(colours):
            return UNKNOWN
        return Grounded(tuple(order), "high")


__all__ = [
    "UNKNOWN",
    "Grounded",
    "RebindEvent",
    "GroundingService",
]
