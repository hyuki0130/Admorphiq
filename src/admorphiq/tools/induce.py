"""T-D `induce` — recover the board's rule from probe transitions, then act on it.

Class D of the sample set (`.wiki/wiki/tool_set_spec.md`): ft09, sb26, sk48, tr87, lf52, cn04,
vc33 — seven games where the board is TRANSFORMED by a rule the agent must discover, toward a
target the board itself displays.

Why this exists, measured (`scripts/rounds/TOOLDIAG`): on ft09 the harness spends 1,610
transitions to open 24 states, 99% of its actions changing nothing — it searches 4,096 click
coordinates without noticing that only EIGHT of them do anything. Probing a stride-8 grid finds
those eight in 49 actions, and each flips exactly 38 cells, which is a GF(2) system.

This module is step 1 and 2 of that: find WHERE the board responds, and measure WHAT each
response does. Step 3, solving toward the target, composes the existing kernels.

⛔ The stride is DERIVED, never fixed. Stride 8 happens to fit ft09's lattice; a tool that
hardcodes it is a tool tuned to ft09. `discover_lattice` probes coarse and refines around the
first response, so a board on any pitch is found by the same code.
"""

from __future__ import annotations

from typing import Any, Callable

Cell = tuple[int, int]
Grid = tuple[tuple[int, ...], ...]


def changed_cells(before: Grid, after: Grid) -> list[Cell]:
    """Cells whose value differs. The unit of every measurement here."""
    return [
        (r, c)
        for r in range(len(after))
        for c in range(len(after[0]))
        if after[r][c] != before[r][c]
    ]


def discover_lattice(
    probe: Callable[[Cell], tuple[Grid, Grid]],
    size: int,
    coarse: int = 8,
    budget: int = 120,
) -> dict[str, Any]:
    """Find the cells the board RESPONDS to, and what each response changes.

    ``probe(cell)`` performs one action at ``cell`` and returns ``(before, after)``. The caller
    owns the environment; this function owns only the search order.

    Coarse pass first: one probe every ``coarse`` cells. If nothing responds, halve the stride and
    sweep again — a lattice on a finer pitch is found by refinement rather than by a bigger
    constant. Once a response is seen, the pitch is INFERRED from the spacing of the responders
    rather than assumed to be the probe stride.

    Returns ``{"live": {cell: footprint}, "stride": inferred pitch or None, "probes": count}``.
    ``live`` is empty when the budget runs out with no response, which is itself informative — a
    board with no responding cell is not this class.
    """
    raw: dict[Cell, list[Cell]] = {}
    probes = 0
    stride = coarse
    while stride >= 1 and probes < budget:
        for y in range(stride // 2, size, stride):
            for x in range(stride // 2, size, stride):
                if probes >= budget:
                    break
                before, after = probe((y, x))
                probes += 1
                delta = changed_cells(before, after)
                if delta:
                    raw[(y, x)] = delta
        if raw:
            break
        stride //= 2

    hud = _hud_cells(raw, probes, size)
    live = {
        cell: [c for c in delta if c not in hud]
        for cell, delta in raw.items()
    }
    live = {cell: delta for cell, delta in live.items() if delta}
    return {
        "live": live,
        "stride": _infer_pitch(sorted(live)),
        "probes": probes,
        "hud_cells": len(hud),
    }


def _hud_cells(raw: dict[Cell, list[Cell]], probes: int, size: int = 64) -> set[Cell]:
    """Cells a probe changes because a COUNTER advanced, not because the board responded.

    ⛔ Two shapes, and the obvious filter only catches one. A cell changing under nearly every
    probe is a timer — that test is here and it is worth keeping. But MEASURED on cd82: 40 of its
    64 probes each changed exactly ONE cell, and all forty were DIFFERENT cells, marching right to
    left along row 63. A progress bar filling one step per action never repeats a cell, so a
    frequency test scores it 0 and it survives as forty "responders". cd82's real response count
    is TWO (footprints 94 and 95), not forty-two.

    So the second test is positional: single-cell changes confined to an edge-pinned band, in
    aggregate across probes, are the counter. `size // 16` keeps the band to the outermost few
    rows or columns — the same "edge-pinned, deliberately TINY" reasoning sp80's own HUD test
    records, after an earlier version there excused real board content as overlay.

    ⛔ **The "never empty a board" guard this filter used to carry was built on a MISREADING and
    has been removed.** It was justified as protecting `ka59`, which "answers with a single cell
    and nothing else ... a genuine one-cell rule". Measured 2026-08-27: those single cells are
    (63, 63), (63, 62), (63, 61), (63, 60) ... one per probe, marching right to left along the
    bottom row. ka59 is INERT to clicks at those positions and the only thing moving is the action
    counter. The guard was preserving a counter and calling it a rule, and on vc33 — where every
    one of 50 probes changed row 0 alone — it reported 50 responders on a board that answers
    nothing.

    What replaces it is the counter's actual signature: it MARCHES. Its position advances
    monotonically with probe order along one edge line, which no rule of a board does.
    """
    if probes < 5 or not raw:
        return set()
    counts: dict[Cell, int] = {}
    for delta in raw.values():
        for c in set(delta):
            counts[c] = counts.get(c, 0) + 1
    hud = {c for c, n in counts.items() if n >= 0.8 * len(raw)}

    # ⛔ NOT "single-cell changes": measured on ft09, one responder changes 38 cells of which 36
    # are its 6x6 tile (colour 9 -> 8) and TWO are the row-63 counter (12 -> 11). A `len(delta)
    # == 1` test misses those two entirely. The counter is defined by WHERE it sits, not by how
    # many of its cells move at once, so the band is what gets filtered — and only the part of a
    # delta that falls in the band, never the whole response.
    margin = max(1, size // 16)

    def in_band(cell: Cell) -> bool:
        r, c = cell
        return r < margin or r >= size - margin or c < margin or c >= size - margin

    band_cells = {c for delta in raw.values() for c in delta if in_band(c)}
    # A board whose REAL rule lives at the edge would be gutted by this, so require the band to
    # look like a counter: many distinct cells, each touched by few probes.
    if len(band_cells) >= 3:
        touched = {c: sum(1 for d in raw.values() if c in d) for c in band_cells}
        if max(touched.values()) <= 0.5 * len(raw):
            hud |= band_cells

    survivors = {cell for cell, d in raw.items() if any(c not in hud for c in d)}
    if survivors:
        return hud
    # Everything responded inside the band, so the "never empty a board" guard would hand back
    # every probe as a responder. ⛔ MEASURED on vc33: all 50 of its probes changed row 0 alone —
    # a bar shrinking one cell per action — and the guard reported 50 responders on a board that
    # answers nothing. The counter's real signature is that it MARCHES: its position advances
    # monotonically with probe order, which no rule of the board does.
    walk = [sorted(c for c in d if in_band(c)) for d in raw.values()]
    heads = [w[0] for w in walk if w]
    if len(heads) >= 5 and len({h[1] for h in heads}) >= 3:
        cols = [h[1] for h in heads]
        rows = [h[0] for h in heads]
        marching = (
            all(a >= b for a, b in zip(cols, cols[1:])) or all(a <= b for a, b in zip(cols, cols[1:]))
        ) and len(set(rows)) <= margin
        if marching:
            return hud
    return set()


def _infer_pitch(cells: list[Cell]) -> int | None:
    """The spacing the responding cells actually sit on, from their own coordinates.

    Taken from the DATA rather than from the probe stride: a coarse sweep can land on a lattice
    finer than itself, and reporting the sweep's stride would then claim a pitch the board does
    not have.
    """
    if len(cells) < 2:
        return None
    gaps = sorted(
        {abs(a[i] - b[i]) for a in cells for b in cells for i in (0, 1) if a[i] != b[i]}
    )
    return gaps[0] if gaps else None


def footprint_signature(live: dict[Cell, list[Cell]]) -> dict[str, Any]:
    """What the responses have in common — the shape of the rule, before any solving.

    A class-D board whose responders all flip the SAME NUMBER of cells is a uniform operator (a
    parity toggle); one where the count varies with position is not, and needs a different
    treatment. Reporting which it is keeps the next step honest instead of assuming parity.
    """
    sizes = {len(v) for v in live.values()}
    return {
        "responders": len(live),
        "footprint_sizes": sorted(sizes),
        "uniform": len(sizes) == 1,
    }
