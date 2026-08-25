"""Pins for R98's corpus validity guard — the check that stops a rule being judged on
boards that do not describe their own spills.

Purpose
-------
Four rules were adopted and reverted in one session because the corpus was wrong rather
than the rules, and one of them passed all five certification gates on the way. The guard
in `rule_bench._invalid()` is what makes that class of mistake announce itself, so a guard
that has quietly stopped biting is the same failure again with an extra step.

Expected feedback
-----------------
A failure means the guard no longer rejects the exact board shapes that cost this round
two reverts, and any bench total taken after that point is unverified.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "rounds" / "R98"))
_spec = importlib.util.spec_from_file_location(
    "r98_rule_bench", _ROOT / "scripts" / "rounds" / "R98" / "rule_bench.py"
)
rule_bench = importlib.util.module_from_spec(_spec)
sys.modules["r98_rule_bench"] = rule_bench
_spec.loader.exec_module(rule_bench)

from admorphiq.hypothesis_select.propagate_flow import Board  # noqa: E402

PIECE = frozenset({(4, 5), (4, 6), (4, 7)})


def _board(hazards: frozenset = frozenset({(9, 3)}), size: int = 10) -> Board:
    return Board(
        pieces=(PIECE,),
        sinks=(),
        hazard_cells=hazards,
        emitter_cells=frozenset(),
        standing_flow=frozenset({(1, 6)}),
        size=size,
    )


def _payload(observed: list[list[tuple[int, int]]]) -> dict:
    return {"observed": [[list(c) for c in layer] for layer in observed]}


def test_a_board_that_describes_its_own_spill_is_accepted() -> None:
    """Purpose: the guard must not reject valid boards, or it stops being usable and gets
    switched off — which is how a check dies.
    Expected feedback: a failure means the bench refuses its own corpus."""
    payload = _payload([[(1, 6)], [(2, 6)], [(3, 6)]])
    assert rule_bench._invalid(payload, _board()) == ""


def test_flow_through_a_recorded_piece_is_rejected() -> None:
    """Purpose: pins the property that condemned the old corpus — a board paired with a
    spill that ran on a DIFFERENT layout has the engine's flow occupying cells the board
    calls a piece. Valid boards score zero; the bad ones scored 1 of 1, 2 of 3 and 3 of 4.
    Expected feedback: a failure means boards frozen before the final plan step would pass
    again, and rules fitted to them would look measured."""
    payload = _payload([[(1, 6)], [(4, 6)]])
    why = rule_bench._invalid(payload, _board())
    assert "passes through 1 of 1" in why, why


def test_a_hazard_outside_the_board_is_rejected() -> None:
    """Purpose: pins the second, independent way the old boards failed to describe
    themselves — size-15 captures recording hazards at row 15, where no cell can exist.
    Expected feedback: a failure means a board can claim an entity outside its own bounds
    and still be swept."""
    payload = _payload([[(1, 6)], [(2, 6)]])
    why = rule_bench._invalid(payload, _board(hazards=frozenset({(10, 3)})))
    assert "outside the board's own bounds" in why, why
