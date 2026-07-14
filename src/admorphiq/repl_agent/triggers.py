"""No-progress trigger controller for PLAN / NAV interventions (R55 item B).

Decoupled from the (killed) goal-audit: these interventions fire on OBSERVED
stall signals, per the FROZEN trigger definitions in the Codex matched12 review
(`docs/r55_codex_matched12_review_20260714.md`):

- PLAN: fire after 12 consecutive environment actions without objective progress
  OR material state change; cooldown 15 actions; max 2 invocations per run.
- NAV: fire after 4 movement attempts producing no position/topology progress OR
  entering a repeated-state loop; cooldown 8 actions; max 4 invocations. Invoke
  shortest_path only when an observed traversability graph exists; else no-op.
- Combined: independent triggers, but only ONE intervention may fire on a given
  action (NAV takes precedence — it is the narrower, movement-specific signal).

The controller is a pure state machine over the executed-action stream so it can
be unit-tested against existing traces before any run. ``observe`` is called once
per executed env action; ``decide`` is called once before each model decision and
returns the intervention to inject (or None).

Signal definitions (the observable proxies the agent already computes):
- objective progress = a level advance (level_up).
- material state change = the board frame changed (board_changed).
- movement attempt = an executed action whose type is a movement (UP/DOWN/LEFT/
  RIGHT/etc.), passed as ``movement=True``.
- position/topology progress on a movement = the board changed AND the resulting
  state is novel (not recently seen). A movement that leaves the frame unchanged,
  or lands on a recently-seen state, is a stall.
- repeated-state loop = the post-action state hash is within the recent window.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class TriggerConfig:
    plan_no_progress: int = 12
    plan_cooldown: int = 15
    plan_max: int = 2
    nav_move_stall: int = 4
    nav_cooldown: int = 8
    nav_max: int = 4
    loop_window: int = 8  # recent post-action state hashes for loop detection


@dataclass
class TriggerController:
    """Frozen PLAN/NAV no-progress triggers. Pure over the executed-action stream."""

    config: TriggerConfig = field(default_factory=TriggerConfig)
    plan_enabled: bool = False
    nav_enabled: bool = False

    # counters
    _plan_streak: int = 0          # consecutive actions with no progress + no change
    _move_stall: int = 0           # consecutive stalled movement attempts
    _actions: int = 0              # executed env actions this run
    _plan_last_fire: int = -(10**9)
    _nav_last_fire: int = -(10**9)
    _plan_fires: int = 0
    _nav_fires: int = 0

    def __post_init__(self) -> None:
        self._recent: deque[str] = deque(maxlen=self.config.loop_window)

    def observe(self, *, movement: bool, board_changed: bool, level_up: bool,
                state_hash: str) -> None:
        """Update stall counters AFTER an env action executed."""
        self._actions += 1
        # PLAN: streak of actions with neither objective progress nor material change.
        if board_changed or level_up:
            self._plan_streak = 0
        else:
            self._plan_streak += 1
        # NAV: only movement attempts count. A movement makes progress iff the board
        # changed AND the new state is novel (not in the recent window).
        if movement:
            novel = state_hash not in self._recent
            progressed = board_changed and novel
            if progressed:
                self._move_stall = 0
            else:
                self._move_stall += 1
        self._recent.append(state_hash)

    def decide(self, *, has_traversability_graph: bool) -> str | None:
        """Return 'nav' | 'plan' | None for the upcoming decision. At most one.

        NAV takes precedence when both are eligible. A NAV trigger whose
        shortest_path would have no traversability graph is a NO-OP: it does not
        inject, and does not consume the cooldown/max budget.
        """
        nav_ready = (
            self.nav_enabled
            and self._move_stall >= self.config.nav_move_stall
            and self._nav_fires < self.config.nav_max
            and (self._actions - self._nav_last_fire) >= self.config.nav_cooldown
        )
        if nav_ready and has_traversability_graph:
            self._nav_last_fire = self._actions
            self._nav_fires += 1
            self._move_stall = 0
            return "nav"

        plan_ready = (
            self.plan_enabled
            and self._plan_streak >= self.config.plan_no_progress
            and self._plan_fires < self.config.plan_max
            and (self._actions - self._plan_last_fire) >= self.config.plan_cooldown
        )
        if plan_ready:
            self._plan_last_fire = self._actions
            self._plan_fires += 1
            self._plan_streak = 0
            return "plan"
        return None

    def reset_level(self) -> None:
        """A level advance is progress — clear the stall streaks (caps persist)."""
        self._plan_streak = 0
        self._move_stall = 0
        self._recent.clear()

    @property
    def stats(self) -> dict[str, int]:
        return {"plan_fires": self._plan_fires, "nav_fires": self._nav_fires,
                "actions": self._actions}
