"""Semantic-eligibility trigger controller for PLAN / NAV (R55 item-B, re-ruled).

The frozen STALL predicates were shown by trace-replay to be structurally
incapable of firing on the diagnosed navigation walls (they move freely and
change the board every action — no stall). Codex re-ruling
(`docs/r55_codex_trigger_reruling_20260714.md`) replaces them with unconditional
GOAL-DECLARATION eligibility, subject only to cooldown and cap:

- NAV: eligible while the model's current declared GOAL_HYPOTHESIS matches the
  frozen nav-signature (reach / navigate / move-to / exit / target). Fires at the
  first decision boundary after declaration; cooldown 8 executed env actions;
  max 4/run. NO traversability-graph gate — the nudge exists to make the model
  build start/goals/passable_mask; noncompliance is logged treatment noise.
- PLAN: eligible while the current declared goal AND milestone are both nonempty.
  Cooldown 15 executed env actions; max 2/run.
- Combined: independent cooldowns/caps; at most one injection per decision
  boundary; NAV precedence; PLAN stays pending (no eligibility/budget loss) and
  fires at the next boundary if still eligible.

Rules (Codex): cooldowns count EXECUTED ENV ACTIONS (not LLM/tool rounds); an
injection consumes cooldown+cap even if the model ignores it; a level-up
invalidates the active goal + eligibility until a new goal is declared (caps and
cooldown history persist); repeating the same declaration does not reset
cooldown. Audit stays OFF — no extra call solicits the goal; the declaration is
parsed from the model's own turn output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Frozen nav-signature: a declared goal is navigation-shaped when it mentions
# reaching / navigating / moving-to a target, exit, or goal location.
_NAV_SIGNATURE = re.compile(
    r"\b(reach|navigate|move\s+.+?\s+to|go\s+to|head\s+to|exit|target|"
    r"destination|goal\s+(?:cell|position|location|square|tile))\b", re.IGNORECASE)
_GOAL_RE = re.compile(r"GOAL(?:_HYPOTHESIS)?\s*[:=]\s*(.+)", re.IGNORECASE)
_MILESTONE_RE = re.compile(r"(?:EXPECTED_)?MILESTONE\s*[:=]\s*(.+)", re.IGNORECASE)


def classify_declaration(text: str) -> tuple[bool, bool]:
    """Parse a model turn's text into (nav_goal, goal_and_milestone).

    nav_goal: the text declares a navigation-shaped goal (nav-signature match on
    an explicit GOAL line if present, else anywhere in the text).
    goal_and_milestone: both a nonempty goal AND a nonempty milestone are stated
    (PLAN eligibility). No audit solicits these — they are read from the model's
    natural output.
    """
    t = text or ""
    gm = _GOAL_RE.search(t)
    goal_text = gm.group(1).strip() if gm else ""
    mm = _MILESTONE_RE.search(t)
    milestone_text = mm.group(1).strip() if mm else ""
    nav_scope = goal_text if goal_text else t
    nav_goal = bool(_NAV_SIGNATURE.search(nav_scope))
    goal_and_milestone = bool(goal_text) and bool(milestone_text)
    return nav_goal, goal_and_milestone


@dataclass
class TriggerConfig:
    nav_cooldown: int = 8
    nav_max: int = 4
    plan_cooldown: int = 15
    plan_max: int = 2


@dataclass
class TriggerController:
    """Goal-declaration PLAN/NAV triggers (semantic eligibility, re-ruled spec)."""

    config: TriggerConfig = field(default_factory=TriggerConfig)
    plan_enabled: bool = False
    nav_enabled: bool = False

    _nav_eligible: bool = False
    _plan_eligible: bool = False
    _actions: int = 0
    _nav_last_fire: int = -(10**9)
    _plan_last_fire: int = -(10**9)
    _nav_fires: int = 0
    _plan_fires: int = 0

    def note_declaration(self, text: str) -> None:
        """Update eligibility from the model's latest turn output."""
        nav, plan = classify_declaration(text)
        # Eligibility latches on while a qualifying goal stands; it is cleared
        # only by a level-up (invalidate_goal). A turn that declares no qualifying
        # goal does not by itself revoke a still-standing one (the model does not
        # re-state the goal every turn), but a fresh qualifying declaration keeps
        # it eligible.
        if nav:
            self._nav_eligible = True
        if plan:
            self._plan_eligible = True

    def observe_action(self) -> None:
        """One executed env action — advances the cooldown clock."""
        self._actions += 1

    def invalidate_goal(self) -> None:
        """Level-up: the active goal + eligibility are void until re-declared.
        Caps and cooldown history persist (Codex)."""
        self._nav_eligible = False
        self._plan_eligible = False

    def decide(self) -> str | None:
        """Return 'nav' | 'plan' | None for the upcoming decision boundary.

        At most one injection; NAV precedence. An injection consumes cooldown+cap.
        """
        nav_ready = (
            self.nav_enabled and self._nav_eligible
            and self._nav_fires < self.config.nav_max
            and (self._actions - self._nav_last_fire) >= self.config.nav_cooldown
        )
        if nav_ready:
            self._nav_last_fire = self._actions
            self._nav_fires += 1
            return "nav"

        plan_ready = (
            self.plan_enabled and self._plan_eligible
            and self._plan_fires < self.config.plan_max
            and (self._actions - self._plan_last_fire) >= self.config.plan_cooldown
        )
        if plan_ready:
            self._plan_last_fire = self._actions
            self._plan_fires += 1
            return "plan"
        return None

    @property
    def stats(self) -> dict[str, int]:
        return {"nav_fires": self._nav_fires, "plan_fires": self._plan_fires,
                "actions": self._actions}
