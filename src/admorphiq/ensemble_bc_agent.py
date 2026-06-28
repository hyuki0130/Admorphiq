"""Ensemble BC agent: efficiency-first policy with a coverage fallback.

Two trained behaviour-cloning checkpoints have complementary strengths under the
efficiency-SQUARED metric:

  * ``bc_policy_v3.pt`` (D4-trained) — clears FEWER games, but where it works it
    is near-optimal (AR25 in ~15 actions → level score ~1.0, M0R0 L1+L2 perfect).
  * ``bc_policy_v2.pt`` — clears MORE games but action-BLOATED (AR25 ~441 actions
    → level score ~0.005).

Because the metric is ``min(human/agent, 1)**2`` averaged over games, each game
should be cleared by whichever policy does it MOST efficiently. This agent runs
the EFFICIENT policy (v3) first under a modest per-level probe budget. If v3
clears the level it keeps driving (it is efficient here). If v3 stalls — its
cycle detector gives up, or no level-up lands within the probe budget — the
agent switches to the COVERAGE policy (v2) for the rest of the game, emitting a
RESET first so v2 plays a clean board from its trained starting distribution.

Wasted v3 probe actions count against the eventual v2 clear's efficiency, so the
probe budget is kept small: the loss on a v2-only game is a small constant added
to an already-bloated count (negligible to its near-zero score), while the wins
(AR25/M0R0 jumping from ~0.005 to ~1.0) dominate the 25-game mean.

This composes ``BCPolicyAgent`` — it never re-implements the net, one-hot, cycle
detector, or TTT; it owns only the switch policy between two sub-agents.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .bc_agent import BCPolicyAgent, _levels_completed, _state_name

DEFAULT_EFFICIENT_WEIGHTS = (
    Path(__file__).resolve().parent.parent.parent / "models" / "bc_policy_v3.pt"
)
DEFAULT_COVERAGE_WEIGHTS = (
    Path(__file__).resolve().parent.parent.parent / "models" / "bc_policy_v2.pt"
)


class EnsembleBCAgent:
    """Run the efficient policy first, fall back to the coverage policy on stall.

    Harness contract is identical to ``BCPolicyAgent``
    (``is_done`` / ``choose_action`` over the raw arcengine observation), so the
    ``score_efficiency`` run loop is agent-agnostic.

    The active sub-agent drives every action. The ensemble only watches for a
    stall on the efficient policy and performs a one-way switch to coverage. It
    exposes ``last_hypothesis`` (read by the scorer's per-game record) describing
    which policy won the game and how many probe actions the efficient policy
    spent before any fallback.
    """

    #: Actions the efficient policy gets to clear the FIRST level before fallback,
    #: while it is still UNPROVEN on this game. v3 is near-optimal where it works
    #: (observed L1 clears in 4–15 actions), so a tight cap bails fast on the
    #: games it cannot solve at all — minimising the probe actions that get
    #: charged to the coverage policy's eventual clear under squared efficiency.
    PROBE_BUDGET_INITIAL = 18

    #: Once v3 clears any level it has PROVEN it is the right solver for this
    #: game, so later (possibly slower) levels get a wider budget before fallback
    #: (e.g. M0R0 L2 legitimately takes ~25 v3 actions; CD82 L2 ~11). Kept tight
    #: so a later v3 failure does not over-charge the coverage policy.
    PROBE_BUDGET_PROVEN = 30

    def __init__(
        self,
        efficient_path: str | Path = DEFAULT_EFFICIENT_WEIGHTS,
        coverage_path: str | Path = DEFAULT_COVERAGE_WEIGHTS,
        device: str | None = None,
        ttt: bool = True,
        probe_budget: int | None = None,
        efficient: Any = None,
        coverage: Any = None,
    ) -> None:
        # ``efficient`` / ``coverage`` injection keeps unit tests free of real
        # model loads; production builds the two sub-agents from disk weights.
        self._efficient = (
            efficient
            if efficient is not None
            else BCPolicyAgent(efficient_path, device, ttt)
        )
        self._coverage = (
            coverage
            if coverage is not None
            else BCPolicyAgent(coverage_path, device, ttt)
        )

        self._probe_budget = (
            self.PROBE_BUDGET_INITIAL if probe_budget is None else probe_budget
        )
        self._switched = False
        self._proven = False  # set once the efficient policy clears any level
        self._probe_actions = 0
        self._last_levels: int | None = None

        # Surfaced in the scorer's per-game JSON (``llm_hypothesis`` slot).
        self.last_hypothesis = "efficient(v3)"

    # ── harness contract ─────────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        if _state_name(latest_frame) == "WIN":
            return True
        # While the efficient policy is active we never report done: a stall is
        # resolved by switching to coverage (in ``choose_action``), not by ending
        # the game. Once switched, the coverage sub-agent's give-up cap governs.
        if self._switched:
            return self._coverage.is_done(frames, latest_frame)
        return False

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        levels = _levels_completed(latest_frame)
        if self._last_levels is None:
            self._last_levels = levels

        if self._switched:
            self._last_levels = levels
            return self._coverage.choose_action(frames, latest_frame)

        # Efficient policy active. A level clear means v3 is efficient here →
        # reset the per-level probe budget, mark it proven, and keep driving v3.
        if levels > self._last_levels:
            self._last_levels = levels
            self._probe_actions = 0
            self._proven = True

        budget = self.PROBE_BUDGET_PROVEN if self._proven else self._probe_budget
        self._probe_actions += 1
        stalled = self._probe_actions > budget
        gave_up = getattr(self._efficient, "_give_up", False)
        if stalled or gave_up:
            self._switched = True
            reason = "give_up" if gave_up else f"{self._probe_actions} probe actions"
            if self._proven:
                # v3 already cleared level(s) on this game: keep the board so the
                # coverage policy CONTINUES the current level. A RESET here would
                # force it to replay the already-cleared levels, charging those
                # wasted actions to the next level's efficiency score.
                self.last_hypothesis = f"coverage(v2) continuing after {reason}"
                return self._coverage.choose_action(frames, latest_frame)
            # v3 cleared nothing: RESET hands the coverage policy a clean board
            # from its trained start distribution to drive the whole game.
            self.last_hypothesis = f"coverage(v2) after {reason}"
            return self._efficient._reset_action()

        return self._efficient.choose_action(frames, latest_frame)
