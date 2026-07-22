"""R95b step (v) tests: the hypothesis compiler.

Tag-only dispatch (a grep guard), offline oracle-plan reproduction on grounded
fixtures for both games, and the typed failure surfaces (DIVERGED,
GROUNDING_INCOMPLETE, UNSATISFIABLE). No live env.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from admorphiq.hypothesis_select import schema as s
from admorphiq.hypothesis_select.compiler import (
    Click,
    GlyphConstraintPlan,
    PatternXorPlan,
    PlanStatus,
    Terminal,
    compile_hypothesis,
)
from admorphiq.hypothesis_select.grounding import UNKNOWN, Grounded, GroundingService
from admorphiq.hypothesis_select.parse import _sc25_lattice
from admorphiq.hypothesis_select.templates import _sc25_on_set, _sc25_read_target

_COMPILER_SRC = Path(__file__).resolve().parents[1] / "src" / "admorphiq" / "hypothesis_select" / "compiler.py"


def _to_grid(a) -> tuple:
    return tuple(tuple(int(x) for x in row) for row in a)


def _repaint(grid, bbox, colour):
    g = [list(r) for r in grid]
    r0, c0, r1, c1 = bbox
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            g[r][c] = colour
    return tuple(tuple(r) for r in g)


def _sc25_fixture():
    """An UNSOLVED 3x3 lattice (all cells colour 2) with a preview target at
    positions (0,0) and (2,2) — so the plan must flip exactly those two cells."""
    g = [[0] * 20 for _ in range(20)]
    for r0 in (4, 8, 12):
        for c0 in (9, 12, 15):
            for dr in (0, 1):
                for dc in (0, 1):
                    g[r0 + dr][c0 + dc] = 2
    g[4][2] = 9
    g[13][5] = 9
    return tuple(tuple(row) for row in g)


def _ft09_grounding_with_cycle():
    """Grounding primed with the ft09 L0 board AND a CLOSED 2-colour cycle. Gold
    only supplies the forward edge (9->8) — the honest one-directionality — so a
    bidirectional probe (what live discovery does) is synthesized to close it."""
    d = np.load("data/traces/ft09.npz")
    fr, nf, act, cx, cy, lvl, gold = (
        d["frames"], d["next_frames"], d["actions"], d["coords_x"], d["coords_y"],
        d["level_index"], d["is_gold"],
    )
    gs = GroundingService()
    for i in range(len(fr)):
        if gold[i] and act[i] == 6 and lvl[i] == 0:
            gs.feed_transition(fr[i], 6, (int(cx[i]), int(cy[i])), nf[i])
    start = _to_grid(fr[0])
    gs.feed(start)
    bbox = gs._cells[gs.cells().value[0][0]].bbox
    a8, a9 = _repaint(start, bbox, 8), _repaint(start, bbox, 9)
    xy = (bbox[1], bbox[0])
    for _ in range(2):  # >= 2 confirmations of the reverse edge closes the cycle
        gs.feed_transition(a9, 6, xy, a8)
        gs.feed_transition(a8, 6, xy, a9)
    gs.feed(start)
    return gs, start


def _advance(order, colour, k):
    return order[(order.index(colour) + k) % len(order)]


def test_dispatch_is_tag_only_no_game_ids_or_adapter_imports():
    """Purpose: the compiler dispatches on schema tags alone — its source contains
    no game id and no quarantined-adapter import.

    Expected feedback: pass proves the compiled plans generalise by family, not by
    hardcoded game, and honour the runtime quarantine. Fail means a game id leaked
    into the compiler and the plan would not transfer to an unseen game."""
    src = _COMPILER_SRC.read_text().lower()
    for token in ("ft09", "sc25", "adapters25"):
        assert token not in src, f"compiler.py leaked {token!r}"


def test_ft09_oracle_plan_reproduces_a_satisfying_end_state():
    """Purpose: the ft09 oracle compiles to a constraint-solve plan whose per-cell
    click counts, applied along the acquired cycle, land EVERY covered cell in a
    colour satisfying its constraints.

    Expected feedback: pass proves the compiled glyph plan is correct on the real
    L0 board (offline, via the cycle semantics) — the step-v reproduction gate.
    Fail means the plan's clicks do not solve the board."""
    gs, _start = _ft09_grounding_with_cycle()
    plan = compile_hypothesis(s.ft09_oracle_instance(), gs)
    assert isinstance(plan, GlyphConstraintPlan)
    solution = plan.solve()
    assert solution.status is PlanStatus.SOLVABLE
    order = gs.get_ordered_cycle().value
    ink_map = dict(s.ft09_oracle_instance().objective.ink_operator_map)
    n_need_clicks = 0
    for cell_id, (target, clicks) in solution.per_cell.items():
        current = gs.cell_colour(cell_id).value
        assert _advance(order, current, clicks) == target  # clicks reach the target
        constraints = list(gs.incidence(cell_id).value)
        for _gid, ink, marker, _c in constraints:  # the target satisfies every constraint
            op = ink_map.get(ink)
            assert not (op == "equal" and target != marker)
            assert not (op == "differ" and target == marker)
        n_need_clicks += clicks > 0
    assert n_need_clicks == 4  # L0's human baseline is 4 actions


def test_sc25_oracle_plan_emits_the_base_xor_preview_diff_set():
    """Purpose: the sc25 oracle compiles to an XOR-diff plan whose emitted click
    set equals the base-XOR-preview diff set computed independently.

    Expected feedback: pass proves the compiled pattern plan clicks exactly the
    cells needed to reach the cast state. Fail means the plan's flip set diverges
    from the target diff."""
    frame = _sc25_fixture()
    gs = GroundingService()
    gs.feed(frame)
    plan = compile_hypothesis(s.sc25_oracle_instance(), gs)
    assert isinstance(plan, PatternXorPlan)
    solution = plan.solve()
    assert solution.status is PlanStatus.SOLVABLE

    # Ground truth diff set (on_set XOR target), independently, as (x, y) coords.
    lattice = _sc25_lattice(frame)
    on_set = _sc25_on_set(frame, lattice)
    target = _sc25_read_target(frame, lattice)
    expected = set()
    for key in on_set ^ target:
        rr, rc = lattice["index"][key]["centroid"]
        expected.add((int(round(rc)), int(round(rr))))
    assert set(solution.flip_clicks) == expected
    assert len(expected) == 2  # the two mismatched cells


def test_grounding_incomplete_on_withheld_cycle_evidence():
    """Purpose: with only the one-directional gold cycle evidence (no closing
    edge), the glyph plan reports GROUNDING_INCOMPLETE rather than guessing.

    Expected feedback: pass proves the honest 60%-risk falsification surface —
    an unclosable cycle stops the plan cleanly (live discovery is step vi's job).
    Fail means the plan fabricates a solution from incomplete grounding."""
    d = np.load("data/traces/ft09.npz")
    fr, nf, act, cx, cy, lvl, gold = (
        d["frames"], d["next_frames"], d["actions"], d["coords_x"], d["coords_y"],
        d["level_index"], d["is_gold"],
    )
    gs = GroundingService()
    for i in range(len(fr)):
        if gold[i] and act[i] == 6 and lvl[i] == 0:
            gs.feed_transition(fr[i], 6, (int(cx[i]), int(cy[i])), nf[i])
    gs.feed(_to_grid(fr[0]))
    assert gs.get_ordered_cycle() is UNKNOWN  # gold is one-directional
    plan = compile_hypothesis(s.ft09_oracle_instance(), gs)
    assert plan.solve().status is PlanStatus.GROUNDING_INCOMPLETE


def test_diverged_when_the_board_contradicts_the_acquired_cycle():
    """Purpose: when a clicked cell's observed change does not match the acquired
    cycle's prediction, the stepper returns DIVERGED — never a silent continue.

    Expected feedback: pass proves execution is guarded by per-click confirmation
    (the attribution hook for the live gate). Fail means the plan would keep
    clicking against a board whose dynamics differ from what was grounded."""
    gs, start = _ft09_grounding_with_cycle()
    plan = compile_hypothesis(s.ft09_oracle_instance(), gs)
    first = plan.step(start)
    assert isinstance(first, Click)
    # Feed a next frame where the clicked cell went to an OFF-CYCLE colour (5),
    # contradicting the acquired {8,9} cycle's predicted advance.
    clicked_cell = plan._pending[0]
    bbox = gs._cells[clicked_cell].bbox
    diverged_frame = _repaint(start, bbox, 5)
    outcome = plan.step(diverged_frame)
    assert isinstance(outcome, Terminal) and outcome.status is PlanStatus.DIVERGED


class _StubGrounding:
    """A minimal grounding stand-in for the UNSATISFIABLE unit: one cell covered by
    two contradictory equal-constraints (must equal 8 AND equal 9), a 2-colour
    cycle — so no cycle colour satisfies both."""

    def get_ordered_cycle(self):
        return Grounded((8, 9), "high")

    def cells(self):
        return Grounded([("e0:c0", (10.0, 10.0))], "high")

    def cell_colour(self, cell_id):
        return Grounded(8, "high")

    def incidence(self, cell_id):
        return Grounded(((("e0:g0", 0, 8, (0.0, 0.0)), ("e0:g1", 0, 9, (20.0, 20.0)))), "high")


def test_unsatisfiable_when_no_cycle_colour_satisfies_the_constraints():
    """Purpose: a covered cell whose constraint set admits no colour on the
    acquired cycle yields UNSATISFIABLE.

    Expected feedback: pass proves the plan reports an impossible constraint set
    as its own typed surface (not DIVERGED or a wrong solve). Fail means an
    unsatisfiable board would be mislabelled."""
    objective = s.ft09_oracle_instance().objective  # all_covering, ink 0=equal
    plan = GlyphConstraintPlan(objective, _StubGrounding())
    assert plan.solve().status is PlanStatus.UNSATISFIABLE
