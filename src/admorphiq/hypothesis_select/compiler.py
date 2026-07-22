"""R95b STEP (v): the hypothesis compiler (schema instance -> executable plan).

Given a verified :class:`~admorphiq.hypothesis_select.schema.CellStateHypothesis`
and a live :class:`~admorphiq.hypothesis_select.grounding.GroundingService`, emit
an ``ExecutablePlan`` that a driver steps against the frame stream — the same
sandbox contract shape as the R93/R94 cards (consume the current frame, emit a
click, observe the next frame). Dispatch is on SCHEMA TAGS ONLY — never a game id,
no adapter imports (the same quarantine as grounding).

Two compiled plans (the two cell-state family members):

* **GlyphRelational x OrderedCycle -> constraint-solve plan.** For each grounded
  cell, the REQUIRED colour set is derived from its incidence (the harness-supplied
  raw ink per covering glyph) under the instance's ink->operator map and coverage
  quantifier; the click count is the distance along the ACQUIRED ordered cycle from
  the cell's current colour to the nearest satisfying colour. Clicks are resolved
  at ACTION time via ``grounding.resolve_click``, and each click's expected
  single-cell advance is CONFIRMED on the next frame — a mismatch is ``DIVERGED``,
  never a silent continue. If the cycle is UNKNOWN the plan is ``GROUNDING_INCOMPLETE``
  (the live driver's step-vi job is a bidirectional discovery probe to close it —
  the honest fix for gold's one-directional cycle). A cell with no satisfying colour
  on the cycle is ``UNSATISFIABLE``.
* **PatternReference x BinaryFlip -> XOR-diff plan.** The cells to flip are the
  symmetric difference of the current ON-set and the preview target
  (``grounding.pattern_diff``); the plan clicks exactly those, and completion is
  guard-gated (the cast = the grid matching the target). ``GROUNDING_INCOMPLETE``
  when the preview is not yet readable.

Failure surfaces are typed (``DIVERGED`` / ``GROUNDING_INCOMPLETE`` /
``UNSATISFIABLE``) — the attribution hooks for the live gate.

Scope: compilation + offline stepping only — no LLM, no live env driver (step vi).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Union

from admorphiq.hypothesis_select.grounding import UNKNOWN, GroundingService
from admorphiq.hypothesis_select.schema import (
    BinaryFlip,
    CellStateHypothesis,
    GlyphRelational,
    OrderedCycle,
    PatternReference,
)


class PlanStatus(str, Enum):
    """A plan's state: solvable/running, done, or a typed failure surface."""

    SOLVABLE = "SOLVABLE"
    DONE = "DONE"
    DIVERGED = "DIVERGED"
    GROUNDING_INCOMPLETE = "GROUNDING_INCOMPLETE"
    UNSATISFIABLE = "UNSATISFIABLE"


@dataclass(frozen=True)
class Click:
    """An emitted ACTION6 click at ``(x, y)``."""

    x: int
    y: int


@dataclass(frozen=True)
class Terminal:
    """A terminal step outcome carrying the plan's final status."""

    status: PlanStatus


StepResult = Union[Click, Terminal]


@dataclass(frozen=True)
class GlyphSolution:
    """The offline glyph-plan: per cell -> (target satisfying colour, click count
    along the cycle). ``status`` is SOLVABLE, or a typed failure."""

    status: PlanStatus
    per_cell: dict[str, tuple[int, int]]


@dataclass(frozen=True)
class PatternSolution:
    """The offline pattern-plan: the ordered flip-click coordinates to reach the
    base-XOR-preview target. ``status`` is SOLVABLE / DONE / GROUNDING_INCOMPLETE."""

    status: PlanStatus
    flip_clicks: tuple[tuple[int, int], ...]


def _cycle_distance(order: tuple[int, ...], start: int, target: int) -> Optional[int]:
    """Forward steps from ``start`` to ``target`` along the cyclic ``order``, or
    ``None`` when either colour is not on the cycle."""
    if start not in order or target not in order:
        return None
    i, j = order.index(start), order.index(target)
    return (j - i) % len(order)


def _satisfies(colour: int, constraints: list[tuple], ink_map: dict[int, str]) -> bool:
    """Whether ``colour`` satisfies every covering constraint (``(glyph_id, ink,
    marker, centroid)``) under the hypothesis's ink->operator map."""
    for _gid, ink, marker, _centroid in constraints:
        op = ink_map.get(ink)
        if op == "equal" and colour != marker:
            return False
        if op == "differ" and colour == marker:
            return False
    return True


class GlyphConstraintPlan:
    """GlyphRelational x OrderedCycle: drive each covered cell to a satisfying
    colour along the acquired cycle."""

    def __init__(
        self, objective: GlyphRelational, grounding: GroundingService, reveal_enabled: bool = False
    ) -> None:
        self._quantifier = objective.coverage_quantifier
        self._ink_map = dict(objective.ink_operator_map)
        self._g = grounding
        self._reveal_enabled = reveal_enabled  # a second (reveal) phase exists — guard label agnostic
        self._pending: Optional[tuple[str, int]] = None  # (cell_id, expected colour)
        self._trigger_pending = False  # a decoy-trigger click awaiting a wholesale reveal
        self._triggered_epochs: set[int] = set()  # epochs already probed with a trigger

    def _relevant_constraints(self, cell_centroid: tuple[float, float], covering: list[tuple]) -> list[tuple]:
        if self._quantifier == "nearest_only" and covering:
            nearest = min(covering, key=lambda e: abs(e[3][0] - cell_centroid[0]) + abs(e[3][1] - cell_centroid[1]))
            return [nearest]
        return covering

    def solve(self) -> GlyphSolution:
        """Compute per-cell (target colour, clicks) from the CURRENT grounded
        state + acquired cycle. GROUNDING_INCOMPLETE if the cycle is unknown;
        UNSATISFIABLE if a covered cell has no satisfying colour on the cycle."""
        cycle = self._g.get_ordered_cycle()
        if cycle is UNKNOWN:
            return GlyphSolution(PlanStatus.GROUNDING_INCOMPLETE, {})
        order = cycle.value
        cells = self._g.cells()
        if cells is UNKNOWN:
            return GlyphSolution(PlanStatus.GROUNDING_INCOMPLETE, {})
        per_cell: dict[str, tuple[int, int]] = {}
        for cell_id, centroid in cells.value:
            covering = self._g.incidence(cell_id)
            colour = self._g.cell_colour(cell_id)
            if covering is UNKNOWN or colour is UNKNOWN or not covering.value:
                continue  # uncovered cell — no constraint to satisfy
            constraints = self._relevant_constraints(centroid, list(covering.value))
            satisfying = [c for c in order if _satisfies(c, constraints, self._ink_map)]
            if not satisfying:
                return GlyphSolution(PlanStatus.UNSATISFIABLE, {})
            best = min(satisfying, key=lambda c: _cycle_distance(order, colour.value, c) or 0)
            clicks = _cycle_distance(order, colour.value, best) or 0
            per_cell[cell_id] = (best, clicks)
        return GlyphSolution(PlanStatus.SOLVABLE, per_cell)

    def step(self, frame: Any) -> StepResult:
        """Feed ``frame``, confirm the previous click's expected advance (DIVERGED
        on mismatch), then emit the next needed click / a decoy-reveal trigger / a
        terminal status."""
        rebind = self._g.feed(frame)
        if self._pending is not None:
            cell_id, expected = self._pending
            self._pending = None
            observed = self._g.cell_colour(cell_id)
            if observed is UNKNOWN or observed.value != expected:
                return Terminal(PlanStatus.DIVERGED)
        if self._trigger_pending:
            self._trigger_pending = False
            if rebind is None:
                # the trigger revealed nothing: the board is solved per the
                # hypothesis but the game has not advanced -> the driver decides
                # CLEARED vs DIVERGED. Otherwise a wholesale reveal happened and we
                # fall through to solve the revealed board.
                return Terminal(PlanStatus.DONE)

        solution = self.solve()
        if solution.status in (PlanStatus.GROUNDING_INCOMPLETE, PlanStatus.UNSATISFIABLE):
            return Terminal(solution.status)
        cycle = self._g.get_ordered_cycle().value
        for cell_id, (_target, clicks) in solution.per_cell.items():
            if clicks <= 0:
                continue
            coord = self._g.resolve_click(cell_id)
            if coord is UNKNOWN:
                return Terminal(PlanStatus.GROUNDING_INCOMPLETE)
            colour = self._g.cell_colour(cell_id).value
            expected = cycle[(cycle.index(colour) + 1) % len(cycle)]
            self._pending = (cell_id, expected)
            x, y = coord.value
            return Click(x, y)

        # Every covered cell is satisfied. If a decoy->reveal phase exists and this
        # board has not yet been trigger-probed, emit a trigger click and await a
        # wholesale reveal (rebind); otherwise the plan is DONE per the hypothesis.
        if self._reveal_enabled and self._g.epoch not in self._triggered_epochs:
            trigger = self._trigger_target()
            if trigger is not None:
                self._triggered_epochs.add(self._g.epoch)
                self._trigger_pending = True
                return Click(trigger[0], trigger[1])
        return Terminal(PlanStatus.DONE)

    def _trigger_target(self) -> Optional[tuple[int, int]]:
        """A ring cell to click as a decoy-reveal probe (the first covered cell
        that resolves to a live coordinate)."""
        cells = self._g.cells()
        if cells is UNKNOWN:
            return None
        for cell_id, _centroid in cells.value:
            covering = self._g.incidence(cell_id)
            coord = self._g.resolve_click(cell_id)
            if covering is not UNKNOWN and covering.value and coord is not UNKNOWN:
                return coord.value
        return None


class PatternXorPlan:
    """PatternReference x BinaryFlip: flip the cells whose shown colour differs
    from the base-XOR-preview target, guard-gated on the cast (grid == target)."""

    def __init__(self, objective: PatternReference, grounding: GroundingService) -> None:
        self._objective = objective
        self._g = grounding
        self._pending: Optional[tuple[int, int]] = None

    def solve(self) -> PatternSolution:
        """The flip-click set to reach the target. GROUNDING_INCOMPLETE until the
        preview is readable; DONE when the grid already matches (nothing to flip)."""
        diff = self._g.pattern_diff()
        if diff is UNKNOWN:
            return PatternSolution(PlanStatus.GROUNDING_INCOMPLETE, ())
        flips = tuple(sorted(diff.value))
        status = PlanStatus.DONE if not flips else PlanStatus.SOLVABLE
        return PatternSolution(status, flips)

    def step(self, frame: Any) -> StepResult:
        """Feed ``frame`` and emit the next flip click, or DONE once the cast fires.
        The cast = the grid reaching base-XOR-preview, detected by an EMPTY flip
        set from the base-aware ``pattern_diff`` — NOT the current-frame majority
        read, which coincides with the preview on some start boards and DONEs
        spuriously (measured live)."""
        self._g.feed(frame)
        solution = self.solve()
        if solution.status is PlanStatus.GROUNDING_INCOMPLETE:
            return Terminal(PlanStatus.GROUNDING_INCOMPLETE)
        if not solution.flip_clicks:
            return Terminal(PlanStatus.DONE)
        x, y = solution.flip_clicks[0]
        self._pending = (x, y)
        return Click(x, y)


ExecutablePlan = Union[GlyphConstraintPlan, PatternXorPlan]


def compile_hypothesis(instance: CellStateHypothesis, grounding: GroundingService) -> ExecutablePlan:
    """Compile a verified hypothesis into an executable plan, dispatching ONLY on
    the schema's objective + transition-model tags (never a game id)."""
    objective, transition = instance.objective, instance.transition_model
    if isinstance(objective, GlyphRelational) and isinstance(transition, OrderedCycle):
        # The reveal is enabled by the STRUCTURAL presence of a second phase, NOT by
        # which guard label the model chose for it. The reveal guard is epistemically
        # undeterminable pre-solve (a reasonable model picks level_advanced as
        # readily as layout_replaced), so the guard is advisory; the actual trigger
        # condition (all constraints satisfied yet no level-up) is observed at
        # runtime and is guard-name-agnostic.
        reveal = len(instance.phases) >= 2
        return GlyphConstraintPlan(objective, grounding, reveal_enabled=reveal)
    if isinstance(objective, PatternReference) and isinstance(transition, BinaryFlip):
        return PatternXorPlan(objective, grounding)
    raise ValueError(
        f"no compiled plan for objective {type(objective).__name__} x "
        f"transition {type(transition).__name__}"
    )


__all__ = [
    "PlanStatus",
    "Click",
    "Terminal",
    "StepResult",
    "GlyphSolution",
    "PatternSolution",
    "GlyphConstraintPlan",
    "PatternXorPlan",
    "ExecutablePlan",
    "compile_hypothesis",
]
