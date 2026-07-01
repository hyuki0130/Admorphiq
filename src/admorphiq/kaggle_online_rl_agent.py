"""Official-framework wrapper that deploys the online RL agent on Kaggle.

This is the DEPLOYED submission agent for the 110-private-game leaderboard (see
docs/submission_strategy_r7.md). It subclasses the official
``agents.agent.Agent`` interface (one instance per game, driven by the
framework's ``main()`` loop) and delegates every decision to
:class:`admorphiq.online_rl_agent.OnlineRLAgent`.

Why this one and not the world-model agent: eval = 110 PRIVATE unseen games.
The online RL agent learns FRESH per game at test time (CNN + off-policy replay
+ novelty exploration, BC warm-start as an exploration prior), so it transfers
by construction. The world-model agent scores higher on the public 25 but its
clears rest on hand-built mechanic priors tuned to those games (expected ~0%
transfer, same as the BC track) — kept as a dev-time proxy only, not shipped.

``OnlineRLAgent.choose_action`` returns an official ``arcengine.GameAction``
with ``set_data({"x","y"})`` applied for ACTION6. The agent owns its own
GAME_OVER handling (``restart_on_game_over``: it resets the attempt but KEEPS
its learned model + replay buffer — death is a learning signal), so this
wrapper only enforces a safety-net action budget.
"""

from __future__ import annotations

from typing import Any

from admorphiq._agents_shim import load_agent_class
from admorphiq.online_rl_agent import OnlineRLAgent

Agent = load_agent_class()


def _action6_data(action: Any) -> dict[str, int] | None:
    """Extract the ACTION6 ``{"x", "y"}`` dict from an official GameAction.

    Returns ``None`` for every non-ACTION6 action (the agent already attached
    the coordinates via ``set_data``; this mirrors them out for the
    ``choose_action_with_data`` contract).
    """
    if getattr(action, "value", None) != 6:
        return None
    ad = getattr(action, "action_data", None)
    if ad is None:
        return None
    return {"x": int(getattr(ad, "x", 0)), "y": int(getattr(ad, "y", 0))}


class KaggleOnlineRLAgent(Agent):  # type: ignore[misc,valid-type]
    """Official ``agents.agent.Agent`` deploying the test-time online RL agent.

    Plays one game per instance. All logic (online CNN training, off-policy
    replay, novelty exploration, per-level learning, GAME_OVER restart-and-keep)
    lives in the composed :class:`OnlineRLAgent`; this class only wires it into
    the official interface and enforces a safety-net action budget.
    """

    # Online RL needs many env steps to learn a game from scratch (the top team
    # used <100k/game). The trustworthy clear-rate baseline was measured at 1500
    # actions/game; give a generous but bounded ceiling so the learner has room
    # to reach deeper levels while a pathological no-progress game still bails
    # (the composed agent's own give-up logic fires well before this).
    MAX_ACTIONS = 8000

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._rl = OnlineRLAgent()

    # ----- official interface ------------------------------------------------

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        """Stop on WIN / agent give-up, and as a safety net at MAX_ACTIONS."""
        if self.action_counter >= self.MAX_ACTIONS:
            return True
        return self._rl.is_done(frames, latest_frame)

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        """Delegate to the online RL agent; returns an official GameAction.

        For ACTION6 the returned action already carries x/y via ``set_data``.
        The agent trains its policy online inside this call as it plays.
        """
        return self._rl.choose_action(frames, latest_frame)

    def choose_action_with_data(
        self, frames: list[Any], latest_frame: Any
    ) -> tuple[Any, dict[str, int] | None]:
        """Return ``(action, data)`` — ``data`` is the ACTION6 click dict.

        One agent step per call (mirrors ``choose_action``); the two entry
        points are never both invoked for the same step.
        """
        action = self._rl.choose_action(frames, latest_frame)
        return action, _action6_data(action)
