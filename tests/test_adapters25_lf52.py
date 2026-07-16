"""Pin the lf52 peg-solitaire simulator + board parse (the first-clear path).

Purpose: LF52's R56b park called the game "unclearable" (a
position-independent side-effect animation). That was a probe artifact; the
real mechanic is peg solitaire (jump a piece over an adjacent piece into an
empty slot, capture it, win at one piece), and the L0 clear (0.0182, score
1.0) rides on ``_solve`` finding a reduce-to-one jump sequence and
``_parse_board`` separating pieces (one colour) from board slots (another) on
the 6px lattice. These pure tests fix that decode so a later parser/search
change cannot silently regress the clear.

Expected feedback: green means the simulator still reduces the L0 lattice to a
single piece and the parser still splits pieces from slots and drops the
non-board colour marker; a failure means the mechanic decode was perturbed and
the L0 clear is at risk.
"""

from __future__ import annotations

from admorphiq.adapters25.lf52 import _parse_board, _solve


def test_solve_reduces_l0_line_to_one_piece() -> None:
    """The L0 lattice (5 pieces on a bent line) must reduce to one piece.

    Pass = the DFS returns four legal jumps; fail = the jump rule or search
    regressed and L0 can no longer be planned.
    """
    pieces = {(1, 1), (2, 1), (4, 1), (5, 2), (5, 4)}
    cells = pieces | {(3, 1), (5, 1), (5, 3), (5, 5)}
    plan = _solve(pieces, cells)
    assert len(plan) == 4  # 5 pieces -> 1 piece needs exactly 4 captures
    # Replay the plan and confirm it lands on a single surviving piece.
    state = set(pieces)
    for src, dst in plan:
        mid = ((src[0] + dst[0]) // 2, (src[1] + dst[1]) // 2)
        assert src in state and mid in state and dst in cells and dst not in state
        state = (state - {src, mid}) | {dst}
    assert len(state) == 1


def test_solve_returns_empty_when_unsolvable() -> None:
    """Two isolated pieces with no shared jump line must yield no plan.

    Pass = ``_solve`` returns [] rather than a bogus sequence; fail = the
    search fabricates an illegal jump.
    """
    pieces = {(0, 0), (5, 5)}
    cells = pieces | {(1, 0), (2, 0)}
    assert _solve(pieces, cells) == []


def test_parse_board_splits_pieces_from_slots_and_drops_marker() -> None:
    """Parser must call the rarer lattice colour the pieces and ignore a marker.

    A synthetic 6px-lattice frame with many slot cells (one colour), a few
    piece cells (another), and a single off-board marker cell (a third colour)
    must parse to exactly the piece set, with the marker excluded. Pass =
    correct piece/slot split; fail = the colour-ranking heuristic regressed
    (this is the bug that made the marker a spurious 6th piece).
    """
    bg = 0
    slot, piece, marker = 1, 14, 9
    h = w = 40
    grid = [[bg] * w for _ in range(h)]

    def paint(gx: int, gy: int, color: int) -> None:
        r0, c0 = 4 + gy * 6, 4 + gx * 6
        for r in range(r0, r0 + 3):
            for c in range(c0, c0 + 3):
                grid[r][c] = color

    slots = [(x, y) for y in range(3) for x in range(3)]
    pieces = [(0, 0), (1, 0), (2, 0)]
    for gx, gy in slots:
        paint(gx, gy, slot)
    for gx, gy in pieces:
        paint(gx, gy, piece)  # a piece covers its slot
    paint(5, 5, marker)  # lone off-lattice decoration, not a board cell

    parsed = _parse_board(tuple(tuple(row) for row in grid))
    assert parsed is not None
    got_pieces, got_cells, _ = parsed
    assert got_pieces == {(0, 0), (1, 0), (2, 0)}
    assert (5, 5) not in got_cells  # marker colour dropped
