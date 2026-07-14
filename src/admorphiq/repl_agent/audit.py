"""Counter-triggered goal-falsification audit (R55 v7-3, Codex v5 review).

A model that clicks forever, mistaking self-caused change for progress, never
revises its wrong goal because nothing forces it to. This audit does: at
12/24/48 actions WITHOUT a level clear it demands a STRUCTURED, falsifiable goal
statement + a discriminating test, and after a declared bounded-horizon milestone
is missed twice it forces the alternative hypothesis.

Design (Codex, binding):
- Trigger on ``turn_in_level`` thresholds, not every N (a high count means the
  goal-OR-plan failed, so the first audit forces an informative TEST, not a
  blind mechanic switch).
- The audit response declares GOAL_HYPOTHESIS / EXPECTED_MILESTONE (within N
  actions) / FALSIFIER / ALTERNATIVE_HYPOTHESIS + one discriminating action.
- A milestone missed twice ⇒ reject the goal-or-plan, require the alternative.

Pure/testable: the agent wires it behind a flag (default OFF) so v6-vs-v7 stays
one-variable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_AUDIT_FIELDS = {
    "GOAL_HYPOTHESIS": "hypothesis",
    "EXPECTED_MILESTONE": "milestone",
    "FALSIFIER": "falsifier",
    "ALTERNATIVE_HYPOTHESIS": "alternative",
}
_HORIZON_RE = re.compile(r"within\s+(\d+)\s+action", re.IGNORECASE)


@dataclass
class AuditState:
    """The currently-pursued goal hypothesis + its bounded-horizon milestone."""

    hypothesis: str = ""
    milestone: str = ""
    falsifier: str = ""
    alternative: str = ""
    deadline_turn: int = -1   # turn_in_level by which the milestone must be met
    misses: int = 0


class GoalAuditor:
    """Triggers audits at action thresholds and tracks milestone misses."""

    def __init__(self, thresholds: tuple[int, ...] = (12, 24, 48),
                 default_horizon: int = 8) -> None:
        self.thresholds = tuple(sorted(thresholds))
        self.default_horizon = default_horizon
        self._audited: set[int] = set()
        self.state = AuditState()

    def reset_level(self) -> None:
        self._audited.clear()
        self.state = AuditState()

    def due(self, turn_in_level: int) -> bool:
        """True when a threshold has been reached that hasn't been audited yet."""
        return self.pending_threshold(turn_in_level) is not None

    def pending_threshold(self, turn_in_level: int) -> int | None:
        """The lowest reached-but-not-yet-audited threshold (the one firing), or
        None. Used to record the ACTUAL trigger (a transcript prompt scan
        overcounts because the audit text persists across tool-loop rounds)."""
        pend = [t for t in self.thresholds
                if turn_in_level >= t and t not in self._audited]
        return min(pend) if pend else None

    def force_alternative(self) -> bool:
        """After 2 missed milestones, the current goal-or-plan is rejected."""
        return self.state.misses >= 2

    def prompt_section(self) -> str:
        """The AUDIT block appended to the decision prompt."""
        block = (
            "\n\nAUDIT — no level completed in a while; you MUST re-examine your "
            "plan. Output these labeled lines, THEN one action:\n"
            "GOAL_HYPOTHESIS: <what completes THIS level>\n"
            "EXPECTED_MILESTONE: <a concrete observable, within N actions>\n"
            "FALSIFIER: <the observation that would prove this goal WRONG>\n"
            "ALTERNATIVE_HYPOTHESIS: <a different mechanic/goal>\n"
            "Then take ONE action that DISCRIMINATES the current hypothesis from "
            "the alternative — an informative TEST, not a blind switch."
        )
        if self.force_alternative():
            block += (
                f"\nYour goal '{self.state.hypothesis}' MISSED its milestone "
                f"twice — REJECT it and pursue the ALTERNATIVE "
                f"'{self.state.alternative}'."
            )
        return block

    def parse(self, raw: str) -> dict[str, str]:
        """Extract the labeled audit fields from a model reply."""
        out: dict[str, str] = {}
        for label, key in _AUDIT_FIELDS.items():
            m = re.search(rf"{label}\s*:\s*(.+)", raw or "")
            if m:
                out[key] = m.group(1).strip()[:200]
        return out

    def on_audit(self, parsed: dict[str, str], turn_in_level: int) -> AuditState:
        """Adopt the audited goal (or the forced alternative) + set the milestone
        deadline. Returns the new state."""
        forcing = self.force_alternative()
        self._mark_audited(turn_in_level)
        horizon = self.default_horizon
        m = _HORIZON_RE.search(parsed.get("milestone", ""))
        if m:
            horizon = max(1, int(m.group(1)))
        hyp = (parsed.get("alternative") if forcing and parsed.get("alternative")
               else parsed.get("hypothesis", ""))
        self.state = AuditState(
            hypothesis=hyp,
            milestone=parsed.get("milestone", ""),
            falsifier=parsed.get("falsifier", ""),
            alternative=parsed.get("alternative", ""),
            deadline_turn=turn_in_level + horizon,
            misses=0 if forcing else self.state.misses,
        )
        return self.state

    def check_milestone(self, turn_in_level: int, level_advanced: bool) -> str:
        """Per-transition milestone check: "met" | "missed" | "pending" | "idle".

        A level advance meets it (misses reset). The deadline passing without an
        advance is a MISS (counts toward the force-alternative threshold).
        """
        if level_advanced:
            self.state.misses = 0
            self.state.deadline_turn = -1
            return "met"
        if self.state.deadline_turn >= 0 and turn_in_level >= self.state.deadline_turn:
            self.state.misses += 1
            self.state.deadline_turn = -1  # consumed until the next audit
            return "missed"
        return "pending" if self.state.deadline_turn >= 0 else "idle"

    def _mark_audited(self, turn_in_level: int) -> None:
        for t in self.thresholds:
            if turn_in_level >= t:
                self._audited.add(t)
