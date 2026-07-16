"""Pin the tn36 opcode-column solver on a synthetic L0-shaped board.

Purpose: tn36 was the LAST zero game; the first clear (0.0357, L0 in 7 actions)
rides on (a) the move-opcode search finding a straight program that lands the
player on the goal and (b) the per-column bit-toggle encoding. These pure tests
fix both so a later parser/search change cannot silently regress the clear.

Expected feedback: green means the search still composes a straight-line move
program and the bit encoder still toggles only the bits that must change; a
failure means the program-synthesis core regressed and the tn36 clear is at
risk.
"""

from __future__ import annotations

from admorphiq.adapters25.tn36 import _column_toggle_clicks, _search_program


def _cols(n: int, values: list[int]):
    """n 2-bit columns preset to ``values`` (bit 'on' state per column)."""
    out = []
    for v in values:
        out.append({"bits": [{"row": 42, "col": 20 + 5 * len(out), "on": bool(v & 1)},
                             {"row": 45, "col": 20 + 5 * len(out), "on": bool(v & 2)}]})
    return out


def test_search_finds_straight_down_program() -> None:
    """Player 5 cells above the goal → five down opcodes (value 3 each).

    Pass = the search returns all-3 for a purely vertical +5-cell delta; fail =
    the move search or the cell-delta rounding regressed.
    """
    columns = _cols(5, [3, 0, 3, 0, 0])
    # blobs are (x, y); goal is 20px (=5 cells) below the player, same column.
    program = _search_program(columns, [(30, 13), (30, 33)])
    assert program == [3, 3, 3, 3, 3]


def test_search_resolves_player_goal_orientation() -> None:
    """The player/goal share a colour, so the search must try both orderings.

    With 2-bit columns only opcodes 1/2/3 (left/right/down) are expressible, so
    this uses a rightward pair: the goal is 12px (3 cells) right of the first
    blob. Pass = the search yields three right opcodes (2); fail = the
    orientation disambiguation or the bit-width opcode filter regressed.
    """
    columns = _cols(3, [0, 0, 0])
    program = _search_program(columns, [(28, 20), (40, 20)])  # 12px = 3 cells right
    assert program == [2, 2, 2]


def test_toggle_clicks_only_flip_mismatched_bits() -> None:
    """Setting a column already at the target must emit no clicks.

    Pass = a column at value 3 targeted to 3 yields [], while value 0→3 yields
    both bit clicks; fail = the encoder over- or under-toggles (wasting the
    deadline budget or setting the wrong opcode).
    """
    on_col = {"bits": [{"row": 42, "col": 21, "on": True}, {"row": 45, "col": 21, "on": True}]}
    off_col = {"bits": [{"row": 42, "col": 26, "on": False}, {"row": 45, "col": 26, "on": False}]}
    assert _column_toggle_clicks(on_col, 3) == []
    assert len(_column_toggle_clicks(off_col, 3)) == 2
