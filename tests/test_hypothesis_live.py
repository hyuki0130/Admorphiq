"""R95b step (vi) tests: the live-driver's PURE helpers (no env, no LLM).

The env-driving path (LiveEnv / run_once) is exercised only under the real gate;
here we pin the cycle-discovery loop (with an offline simulator), the discovery
cell selection, and the gate verdict aggregation.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from admorphiq.hypothesis_select.grounding import UNKNOWN, GroundingService

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "probe_hypothesis_live.py"
_SPEC = importlib.util.spec_from_file_location("probe_hypothesis_live", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules["probe_hypothesis_live"] = _MOD
_SPEC.loader.exec_module(_MOD)

discover_cycle = _MOD.discover_cycle
gate_verdict = _MOD.gate_verdict


def _lattice(overrides=None):
    """A 3x3 lattice of 2x2 cells, all colour 2 unless overridden."""
    overrides = overrides or {}
    g = [[0] * 20 for _ in range(20)]
    for r0 in (4, 8, 12):
        for c0 in (6, 10, 14):
            colour = overrides.get((r0, c0), 2)
            for dr in (0, 1):
                for dc in (0, 1):
                    g[r0 + dr][c0 + dc] = colour
    return tuple(tuple(row) for row in g)


def test_discover_cycle_closes_a_two_colour_cycle_via_bidirectional_probe():
    """Purpose: the discovery loop closes a 2-colour cycle by clicking a cell
    REPEATEDLY (forward + reverse edges), the honest fix for gold's
    one-directionality — driven here by an offline flip simulator.

    Expected feedback: pass proves the live driver can acquire the cycle gold
    cannot, within budget. Fail means discovery never closes the cycle and every
    ft09 run would report GROUNDING_INCOMPLETE."""
    start = _lattice()
    gs = GroundingService()
    gs.feed(start)
    assert gs.get_ordered_cycle() is UNKNOWN  # nothing observed yet

    def probe(x, y):
        # Flip the clicked lattice cell between colours 2 and 7, return the frame.
        grid = [list(r) for r in gs._prev_grid]
        cur = grid[y][x]
        new = 7 if cur == 2 else 2
        # repaint the whole 2x2 cell the click landed in
        r0, c0 = (y // 4) * 4 + (0 if y % 4 < 2 else 2), (x // 4) * 4 + (0 if x % 4 < 2 else 2)
        for dr in (0, 1):
            for dc in (0, 1):
                grid[r0 + dr][c0 + dc] = new
        return tuple(tuple(r) for r in grid)

    closed, actions = discover_cycle(gs, probe, budget=30)
    assert closed is True
    assert 0 < actions <= 30
    cycle = gs.get_ordered_cycle()
    assert cycle is not UNKNOWN and set(cycle.value) == {2, 7}


def test_discover_cycle_gives_up_within_budget_when_it_cannot_close():
    """Purpose: when a probe never produces a reverse edge (the board is inert),
    discovery stops at the budget and reports not-closed — never loops forever.

    Expected feedback: pass proves the honest GROUNDING_INCOMPLETE path is
    budget-bounded. Fail means an unclosable cycle would hang the gate."""
    gs = GroundingService()
    gs.feed(_lattice())

    def inert(x, y):
        return gs._prev_grid  # nothing ever changes

    closed, actions = discover_cycle(gs, inert, budget=6)
    assert closed is False
    assert actions <= 6


def test_gate_verdict_pass_only_on_all_runs_clearing_the_target():
    """Purpose: the ft09 gate PASSes only when every run cleared idx0+idx1.

    Expected feedback: pass proves the 3/3 gate rule is enforced and a single
    non-clear (or a GROUNDING_INCOMPLETE) fails the gate. Fail means the verdict
    would over-report."""
    ft09_pass = [{"plan_outcome": "CLEARED", "levels_cleared": 2} for _ in range(3)]
    assert gate_verdict(ft09_pass, "ft09") == "PASS"

    one_short = ft09_pass[:2] + [{"plan_outcome": "CLEARED", "levels_cleared": 1}]
    assert gate_verdict(one_short, "ft09") == "FAIL"  # a run reached only idx0

    incomplete = ft09_pass[:2] + [{"plan_outcome": "GROUNDING_INCOMPLETE", "levels_cleared": 0}]
    assert gate_verdict(incomplete, "ft09") == "FAIL"
    assert gate_verdict([], "ft09") == "FAIL"  # no runs


def test_sc25_gate_scores_the_cast_handover_not_levels():
    """Purpose: per the FROZEN contract (sc25 idx0 pattern phase, navigation
    excluded), the sc25 gate scores ``cast_and_handover`` — NOT levels_cleared,
    which is honestly 0 for a genuine cast (the level does not clear without the
    out-of-scope exit navigation).

    Expected feedback: pass proves a 3/3 genuine-cast run PASSes with levels 0,
    while a plan-DONE that never cast (cast_and_handover False) FAILs even though
    it 'finished'. Fail means the gate reverted to a level-clear criterion the
    contract forbids for sc25."""
    cast_runs = [{"plan_outcome": "CAST_HANDOVER", "levels_cleared": 0, "cast_and_handover": True} for _ in range(3)]
    assert gate_verdict(cast_runs, "sc25") == "PASS"  # levels 0 is correct + expected

    no_cast = cast_runs[:2] + [{"plan_outcome": "DIVERGED", "levels_cleared": 0, "cast_and_handover": False}]
    assert gate_verdict(no_cast, "sc25") == "FAIL"  # a plan-DONE with no cast fails

    # A level-clear-shaped record without the cast flag must NOT pass sc25.
    level_shaped = [{"plan_outcome": "CLEARED", "levels_cleared": 1} for _ in range(3)]
    assert gate_verdict(level_shaped, "sc25") == "FAIL"
