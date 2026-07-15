"""Tests for VC33's containing-panel winner discriminator (R56 iteration 2).

VC33 shows two identically-sized same-colour regions — a WINNER (clicking it
~3x clears the level) and a DECOY (clicking it inflates the winner's
requirement). The winner is the one nested in the SMALLER containing panel
(measured live: 368 vs 848; clicking only the smaller-panel region clears L0
in 3 clicks). ``_region_candidates`` orders candidates so the winner leads,
and the adapter's lead-commit then clicks it exclusively.
"""

from __future__ import annotations

from admorphiq.adapters25.vc33 import _region_candidates

_BG = 1


def _grid(cells, h=64, w=64):
    g = [[_BG] * w for _ in range(h)]
    for (r, c), col in cells.items():
        g[r][c] = col
    return tuple(tuple(row) for row in g)


def _filled(r0, c0, r1, c1, color):
    return {(r, c): color for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)}


def test_winner_with_smaller_panel_leads():
    """Purpose: with two same-colour target regions — one nested in a small
    panel (WINNER), one in a large panel (DECOY) — plus an unrelated rarer
    chrome region, ``_region_candidates`` returns the winner's centroid FIRST
    (ahead of the decoy AND the rarer chrome). Expected feedback: a FAIL means
    the lead-commit would click the decoy or chrome first, inflating the
    winner's requirement, and L0 would clear inefficiently (the 60x regression
    this fix removes)."""
    cells: dict[tuple[int, int], int] = {}
    # Small panel (colour 4, 6x6=36) with a nested target (colour 9, 2x2) — WINNER.
    cells.update(_filled(4, 4, 9, 9, 4))
    cells.update(_filled(6, 6, 7, 7, 9))  # winner target, centre ~ (6.5,6.5)
    # Large panel (colour 4, 12x12=144) with a nested same-colour target — DECOY.
    cells.update(_filled(20, 20, 31, 31, 4))
    cells.update(_filled(25, 25, 26, 26, 9))  # decoy target, centre ~ (25.5,25.5)
    # A rarer, NON-nested chrome region (colour 7, single tiny blob).
    cells.update(_filled(50, 50, 51, 51, 7))
    grid = _grid(cells)
    order = _region_candidates(grid)
    assert order, "expected candidates"
    # winner target centre rounds to (7,7) or (6,6) — accept the nested-small one first
    winner = order[0]
    assert abs(winner[0] - 7) <= 1 and abs(winner[1] - 7) <= 1
    # the decoy (nested in the larger panel) comes after the winner
    decoy_idx = next(
        (i for i, c in enumerate(order) if abs(c[0] - 26) <= 1 and abs(c[1] - 26) <= 1), None
    )
    assert decoy_idx is not None and decoy_idx > 0
