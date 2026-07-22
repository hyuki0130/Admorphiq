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
from admorphiq.hypothesis_select.templates import _sc25_read_target

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


def _sc25_start_frame():
    """A REAL sc25 level-0 start board (from the trace), whose interactive lattice
    is a 2-colour grid with a preview target beside it. Deliberately a board where
    the current non-majority cells COINCIDE with the preview target — the live case
    that made a current-majority ON-set spuriously report 'already solved'. The
    base-XOR-preview diff (against the captured parity-0 base) must still be
    non-empty here."""
    d = np.load("data/traces/sc25.npz")
    return _to_grid(d["frames"][0])


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
    set equals the base-XOR-preview diff set — computed against the captured
    parity-0 BASE, not the current frame's majority colour.

    Expected feedback: pass proves the compiled pattern plan clicks exactly the
    cells needed to reach the cast state, AND that a start board whose non-majority
    cells coincide with the preview does NOT spuriously report 'already solved'
    (empty diff) — the live DIVERGED-at-start defect. Fail means the base snapshot
    regressed to a current-majority read."""
    frame = _sc25_start_frame()
    gs = GroundingService()
    gs.feed(frame)  # capture the parity-0 base
    gs.feed(frame)  # a second equal read locks the preview target
    plan = compile_hypothesis(s.sc25_oracle_instance(), gs)
    assert isinstance(plan, PatternXorPlan)
    solution = plan.solve()
    assert solution.status is PlanStatus.SOLVABLE
    assert solution.flip_clicks  # NON-empty: not spuriously 'already solved'

    # Ground truth: at the start (current == base), the flip set is exactly the
    # preview-target cells (base XOR preview flips precisely those), as (x, y).
    lattice = _sc25_lattice(frame)
    target = _sc25_read_target(frame, lattice)
    expected = set()
    for key in target:
        rr, rc = lattice["index"][key]["centroid"]
        expected.add((int(round(rc)), int(round(rr))))
    assert set(solution.flip_clicks) == expected


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


def _ft09_decoy_grounding():
    """Grounding on the real L3 DECOY board (fr[105], all rings satisfied) with a
    closed {8,12} cycle injected (the decoy's own colours), plus the wholesale
    REVEALED board (nf[105]) — the exact decoy->reveal transition diagnosed for
    the L3 12->8 anomaly."""
    d = np.load("data/traces/ft09.npz")
    decoy, revealed = _to_grid(d["frames"][105]), _to_grid(d["next_frames"][105])
    gs = GroundingService()
    gs.feed(decoy)
    bbox = gs._cells[gs.cells().value[0][0]].bbox
    a8, a12 = _repaint(decoy, bbox, 8), _repaint(decoy, bbox, 12)
    xy = (bbox[1], bbox[0])
    for _ in range(2):
        gs.feed_transition(a8, 6, xy, a12)
        gs.feed_transition(a12, 6, xy, a8)
    gs.feed(decoy)
    return gs, decoy, revealed


def test_glyph_plan_decoy_triggers_then_reveal_needs_rediscovery():
    """Purpose: on a DECOY board (all rings satisfied) the reveal-phase-enabled
    plan emits a TRIGGER click rather than a premature DONE; feeding the resulting
    WHOLESALE-revealed board resets the per-board cycle, so the plan reports
    GROUNDING_INCOMPLETE (the driver then re-discovers) — it does NOT falsely
    declare the level solved.

    Expected feedback: pass proves the decoy->reveal phase mechanic (schema
    LayoutReplaced guard -> compiler trigger-then-resolve) works on the real L3
    decoy transition. Fail means the plan either never triggers or falsely DONEs a
    decoy."""
    gs, decoy, revealed = _ft09_decoy_grounding()
    assert gs.get_ordered_cycle() is not UNKNOWN  # cycle primed
    plan = compile_hypothesis(s.ft09_oracle_instance(), gs)
    first = plan.step(decoy)
    assert isinstance(first, Click)  # a trigger click, not a premature Terminal(DONE)
    after_reveal = plan.step(revealed)
    assert isinstance(after_reveal, Terminal)
    assert after_reveal.status is PlanStatus.GROUNDING_INCOMPLETE  # reveal -> cycle reset -> re-discover


def test_glyph_plan_trigger_revealing_nothing_is_honest_done():
    """Purpose: if the decoy-trigger click causes NO wholesale change (the board
    is genuinely solved, no hidden reveal), the plan returns DONE — it does not
    loop clicking.

    Expected feedback: pass proves the honest-DIVERGED path is preserved: a
    plan-DONE that clears nothing is the driver's DIVERGED signal, and the plan
    itself terminates rather than thrashing. Fail means a solved-but-not-won board
    would loop or misreport."""
    gs, decoy, _revealed = _ft09_decoy_grounding()
    plan = compile_hypothesis(s.ft09_oracle_instance(), gs)
    first = plan.step(decoy)
    assert isinstance(first, Click)  # the trigger
    # Feed the SAME board again (no wholesale change) -> the trigger revealed nothing.
    outcome = plan.step(decoy)
    assert isinstance(outcome, Terminal) and outcome.status is PlanStatus.DONE
