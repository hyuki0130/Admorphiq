"""R97 build #3 tests: the AuthoredCellUpdate compiler node.

Dispatch on the authored-transition tag, causal use of the authored function in
BOTH planning and action-time confirmation (Codex trap 1), and the causal-use
proof that substituting a known-wrong authored function breaks offline parity
(Codex correction 6). A tag-only dispatch grep guard for the new path completes
the set.
"""

from __future__ import annotations

from pathlib import Path

from admorphiq.hypothesis_select import schema as s
from admorphiq.hypothesis_select.authored import AuthoredCellTransition
from admorphiq.hypothesis_select.compiler import (
    AuthoredCellUpdatePlan,
    Click,
    GlyphConstraintPlan,
    PlanStatus,
    Terminal,
    compile_hypothesis,
)
from admorphiq.hypothesis_select.grounding import Grounded

_COMPILER_SRC = Path(__file__).resolve().parents[1] / "src" / "admorphiq" / "hypothesis_select" / "compiler.py"

# A cyclic-successor authored rule (behaviourally == OrderedCycle over the palette)
# and a known-WRONG identity rule (never advances) for the parity-break proof.
_SUCC = (
    "def update(colour, click_index, palette):\n"
    "    i = palette.index(colour)\n"
    "    return palette[(i + 1) % len(palette)]\n"
)
_IDENTITY = "def update(colour, click_index, palette):\n    return colour\n"


class _StubGrounding:
    """A minimal grounding stand-in: three covered cells over palette {8, 9, 12}.
    Cell c0 starts at 8 and must equal marker 12 (needs cycling); c1/c2 already
    satisfy their equal-markers (0 clicks). Colours are static — so a plan that
    clicks and re-reads an unchanged cell must DIVERGE against the authored
    prediction. Also exposes ``get_ordered_cycle`` so the canned GlyphConstraintPlan
    can be run on the SAME board for the parity comparison."""

    _COLOUR = {"e0:c0": 8, "e0:c1": 9, "e0:c2": 12}
    _MARKER = {"e0:c0": 12, "e0:c1": 9, "e0:c2": 12}

    def feed(self, frame):
        return None

    def cells(self):
        return Grounded([("e0:c0", (10.0, 10.0)), ("e0:c1", (10.0, 20.0)), ("e0:c2", (10.0, 30.0))], "high")

    def cell_colour(self, cell_id):
        return Grounded(self._COLOUR[cell_id], "high")

    def incidence(self, cell_id):
        return Grounded(((f"g_{cell_id}", 0, self._MARKER[cell_id], (0.0, 0.0)),), "high")

    def resolve_click(self, cell_id):
        return Grounded((10, 10), "high")

    def get_ordered_cycle(self):
        return Grounded((8, 9, 12), "high")


def _authored_hypothesis(source: str, name: str) -> s.CellStateHypothesis:
    return s.CellStateHypothesis(
        objective=s.ft09_oracle_instance().objective,
        transition_model=AuthoredCellTransition(name=name, source=source),
    )


def test_dispatch_authored_tag_no_game_ids_in_the_new_path():
    """Purpose: a GlyphRelational hypothesis carrying an AuthoredCellTransition
    compiles to an AuthoredCellUpdatePlan, and the compiler source (including the
    new path) still contains no game id or adapter import.

    Expected feedback: pass proves the authored path is dispatched purely on the
    schema tag and honours the runtime quarantine. Fail means either dispatch is
    wrong or a game id leaked into the compiler."""
    plan = compile_hypothesis(_authored_hypothesis(_SUCC, "cyclic_successor"), _StubGrounding())
    assert isinstance(plan, AuthoredCellUpdatePlan)
    src = _COMPILER_SRC.read_text().lower()
    for token in ("ft09", "sc25", "adapters25"):
        assert token not in src, f"compiler.py leaked {token!r}"


def test_authored_plan_solves_by_simulating_the_authored_update():
    """Purpose: the authored plan computes each cell's (target, clicks) by pressing
    the authored update forward — c0 at 8 reaches its required 12 in 2 presses along
    the palette successor, c1/c2 need 0 — and logs the source hash + invocation
    count.

    Expected feedback: pass proves the authored function is on the PLANNING causal
    path (the click counts come from it) and is auditable. Fail means planning
    bypasses the authored rule."""
    plan = compile_hypothesis(_authored_hypothesis(_SUCC, "cyclic_successor"), _StubGrounding())
    solution = plan.solve()
    assert solution.status is PlanStatus.SOLVABLE
    assert solution.per_cell["e0:c0"] == (12, 2)
    assert solution.per_cell["e0:c1"] == (9, 0)
    assert len(plan.authored_source_hash) == 64
    assert plan.authored_invocations > 0  # solve invoked the authored update


def test_authored_plan_matches_the_canned_ordered_cycle_plan_offline():
    """Purpose: with the correct (cyclic-successor) authored rule, the authored
    plan's per-cell click counts equal those of the canned GlyphConstraintPlan +
    OrderedCycle((8,9,12)) on the SAME board — offline parity.

    Expected feedback: pass proves the authored path reproduces the proven canned
    plan when the authored rule is right (the causal-use POSITIVE control). Fail
    means the authored node computes a different plan than the equivalent canned
    rule."""
    authored = compile_hypothesis(_authored_hypothesis(_SUCC, "cyclic_successor"), _StubGrounding())
    canned = GlyphConstraintPlan(s.ft09_oracle_instance().objective, _StubGrounding())
    a_sol, c_sol = authored.solve(), canned.solve()
    assert a_sol.status is PlanStatus.SOLVABLE and c_sol.status is PlanStatus.SOLVABLE
    assert a_sol.per_cell["e0:c0"] == c_sol.per_cell["e0:c0"]  # both = (12, 2)


def test_wrong_authored_function_breaks_offline_parity():
    """Purpose: substituting a known-WRONG authored function (identity — never
    advances a colour) breaks parity — the plan can no longer reach c0's required
    colour and reports UNSATISFIABLE instead of the correct rule's SOLVABLE.

    Expected feedback: pass proves the authored code is genuinely on the causal path
    (Codex correction 6): a wrong function changes the plan, so a live success cannot
    occur without the authored code executing correctly. Fail means the plan would
    succeed regardless of the authored function — the causal-use trap is open."""
    correct = compile_hypothesis(_authored_hypothesis(_SUCC, "cyclic_successor"), _StubGrounding())
    wrong = compile_hypothesis(_authored_hypothesis(_IDENTITY, "identity"), _StubGrounding())
    assert correct.solve().status is PlanStatus.SOLVABLE
    assert wrong.solve().status is PlanStatus.UNSATISFIABLE


def test_action_time_confirmation_diverges_against_the_authored_prediction():
    """Purpose: the plan emits a click for c0 (predicted next colour = authored
    successor of 8 = 9), then — re-reading the static stub where c0 is still 8 —
    returns DIVERGED because the observed colour does not match the authored
    prediction.

    Expected feedback: pass proves the authored function is ALSO on the action-time
    confirmation path (a mismatch between its prediction and the observed frame is
    DIVERGED, never a silent continue). Fail means confirmation ignores the authored
    rule and the trap-1 causal use is incomplete."""
    plan = compile_hypothesis(_authored_hypothesis(_SUCC, "cyclic_successor"), _StubGrounding())
    first = plan.step("frame")
    assert isinstance(first, Click)
    outcome = plan.step("frame")  # c0 still reads 8, authored predicted 9 -> mismatch
    assert isinstance(outcome, Terminal) and outcome.status is PlanStatus.DIVERGED
