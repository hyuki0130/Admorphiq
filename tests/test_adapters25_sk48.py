"""Tests for the SK48 adapter's faithful offline simulator + frame parser
(R56 dedicated session, 2026-07-15).

Background (see the module docstring + ``.wiki/wiki/games/SK48.md``): SK48 is a
snake SHAPE / pattern-matching puzzle whose win progress is frame-visible but
too sparse for any online scorer, so the adapter reconstructs a FAITHFUL
offline simulator of the grow/retract/side-push semantics from the frame and
searches it toward the EXACT internal template-match goal. The simulator was
validated in lockstep against the live engine (gold L0 13-move replay + ~900
random moves + L0-L4 solutions replayed to real wins); these tests pin the
engine-free invariants: the L0 gold sequence wins in the simulator at exactly
move 14, A* rediscovers a winning plan, and the frame-parser components decode
the sprite signatures the reconstruction depends on.
"""

from __future__ import annotations

from admorphiq.adapters25.sk48 import (
    _CellObj,
    _Head,
    _is_seg,
    _parse_budget,
    _parse_cells,
    _parse_gates,
    _parse_state,
    _Rect,
    _search,
    _Seg,
    _Sim,
)

# The exact L0 board, read from the live engine internals (dev-time) and pinned
# here as an engine-free fixture — positions in (x=col, y=row), colours as the
# elmjchdqcn pixels[1,1] / head pixels[2,2] values.
_GOLD_L0 = [1, 1, 1, 4, 4, 4, 4, 3, 2, 2, 4, 3, 1, 4]


def _l0_state() -> dict:
    ctrl = _Head(11, 36, 0, 6)
    partner = _Head(20, 56, 0, 6)
    heads = [ctrl, partner]
    bodies = [
        (ctrl, [_Seg(11, 36, 0), _Seg(17, 36, 0)]),
        (partner, [_Seg(20, 56, 0), _Seg(26, 56, 0), _Seg(32, 56, 0), _Seg(38, 56, 0)]),
    ]
    cells = [
        _CellObj(41, 30, 14), _CellObj(41, 24, 9), _CellObj(41, 18, 8),
        _CellObj(26, 56, 8), _CellObj(32, 56, 14), _CellObj(38, 56, 9),
    ]
    gates = [_Rect(13, 14, 2, 8), _Rect(13, 20, 2, 8), _Rect(13, 26, 2, 8), _Rect(13, 32, 2, 8)]
    return {
        "heads": heads, "bodies": bodies, "cells": cells,
        "partner": {id(ctrl): partner}, "check_count": {id(partner): 3},
        "active": ctrl, "arena": _Rect(17, 12, 30, 30),
        "obstacles": [], "gates": gates, "budget": 196,
    }


def test_gold_sequence_wins_at_move_14():
    """Purpose: prove the ported grow/retract/side-push physics reproduce the
    engine's win exactly — the gold L0 solution must NOT win before its final
    move and MUST win on move 14. This is the oracle that gates the whole
    simulator (a wrong push/collision rule shifts or breaks the win).
    Expected feedback: a failure means the physics port diverged from the
    engine; the search and every clear are then untrustworthy."""
    sim = _Sim(_l0_state())
    assert not sim.is_win()
    for i, a in enumerate(_GOLD_L0):
        sim.step(a)
        won = sim.is_win()
        if i < len(_GOLD_L0) - 1:
            assert not won, f"won early at move {i}"
        else:
            assert won, "did not win on the final gold move"
    assert sim.budget == 196 - 14


def test_search_finds_a_winning_plan():
    """Purpose: the A* over the simulator must rediscover a winning move
    sequence for L0 within the 196-move budget (proving the exact
    template-match goal test + heuristic are search-usable, not just the gold
    replay).
    Expected feedback: None means search cannot reach the win — the heuristic
    or goal test is broken, and the adapter would gate to the 0/8 explorer."""
    sim = _Sim(_l0_state())
    sol = _search(sim, max_expansions=400000)
    assert sol is not None and 0 < len(sol) <= 196
    replay = _Sim(_l0_state())
    for a in sol:
        replay.step(a)
    assert replay.is_win()


def test_parse_state_gates_on_garbage():
    """Purpose: the frame parser must return None (so the adapter falls back to
    the safe explorer) when handed a board with no parseable head, never a
    half-built state that would waste budget on a bogus plan.
    Expected feedback: a non-None here means the gate leaks — a malformed frame
    could drive a wrong plan and regress the 0/8 floor."""
    blank = tuple(tuple(5 for _ in range(64)) for _ in range(64))
    assert _parse_state(blank) is None


def test_parse_budget_reads_the_progress_bar():
    """Purpose: budget is decoded from the row-53 colour-2 progress bar; a full
    bar must read as ~196 so the search budget cap is right.
    Expected feedback: a wrong reading shrinks/expands the search budget and can
    make solvable levels look unsolvable."""
    grid = [[5] * 64 for _ in range(64)]
    grid[53] = [2] * 64
    assert _parse_budget(tuple(tuple(r) for r in grid)) == 196
    grid[53] = [2] * 32 + [3] * 32
    assert abs(_parse_budget(tuple(tuple(r) for r in grid)) - 98) <= 1


def test_parse_cells_reads_4x4_colour_blocks():
    """Purpose: target cells render as 4x4 solid colour blocks (inside a 6x6
    sprite offset by 1,1); the parser must map a block back to its sprite
    origin (x=col-1, y=row-1) with the right colour — the overlap order of
    these colours IS the win condition.
    Expected feedback: a mis-located or mis-coloured cell corrupts both the
    goal test and the heuristic."""
    grid = [[5] * 64 for _ in range(64)]
    for r in range(19, 23):
        for c in range(42, 46):
            grid[r][c] = 8
    cells = _parse_cells(tuple(tuple(r) for r in grid))
    assert len(cells) == 1
    assert (cells[0].x, cells[0].y, cells[0].color) == (41, 18, 8)


def test_is_seg_detects_horizontal_and_vertical_bands():
    """Purpose: body-segment detection keys on the dashed 1/2 (active) pattern
    at the two middle rows (horizontal) or cols (vertical); the walk that
    reconstructs a snake body depends on it.
    Expected feedback: a false negative truncates the parsed snake (wrong
    length -> wrong template comparison); a false positive invents segments."""
    g = [[5] * 64 for _ in range(64)]
    # horizontal segment at (10,10): middle rows 12,13 carry the 2/1 dash edges
    g[12][10], g[13][10], g[12][15], g[13][15] = 2, 1, 1, 2
    grid = tuple(tuple(r) for r in g)
    assert _is_seg(grid, 10, 10, horiz=True)
    assert not _is_seg(grid, 10, 10, horiz=False)
    g2 = [[5] * 64 for _ in range(64)]
    g2[20][22], g2[20][23], g2[25][22], g2[25][23] = 2, 1, 1, 2
    grid2 = tuple(tuple(r) for r in g2)
    assert _is_seg(grid2, 20, 20, horiz=False)


def test_parse_gates_merges_stacked_rails():
    """Purpose: stacked side-push gates share rows and one can be head-occluded,
    so the parser detects a 2-wide colour-2/3 RAIL (>=8 long) rather than fixed
    gate boxes — the merged rail must cover the whole run.
    Expected feedback: a missed rail wrongly forbids side-pushes, so search
    cannot find solutions that slide the snake (L0 needs three side-pushes)."""
    g = [[5] * 64 for _ in range(64)]
    # a vertical rail at cols 13-14, rows 14..29 (two stacked 8-tall gates)
    pattern = [2, 2, 3, 3, 3, 3, 2, 2] * 2
    for i, v in enumerate(pattern):
        g[14 + i][13] = v
        g[14 + i][14] = v
    gates = _parse_gates(tuple(tuple(r) for r in g))
    assert any(gt.x == 13 and gt.y == 14 and gt.h >= 16 for gt in gates)
    # a check-point inside the rail is contained (enables a side-push there)
    assert any(gt.contains(13, 20) for gt in gates)
