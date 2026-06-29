"""Official-framework wrapper that deploys the online world-model agent on Kaggle.

This is the world-model submission agent. It subclasses the official
``agents.agent.Agent`` interface (one instance per game, driven by the
framework's ``main()`` loop) and delegates every decision to
:class:`admorphiq.world_model_agent.WorldModelAgent`.

Unlike the BC submission (:class:`admorphiq.kaggle_bc_agent.KaggleBCAgent`),
the world-model agent loads **no trained weights** — it learns each game's
dynamics ONLINE at test time (perception -> objects -> per-game effect model
-> goal inference -> search planning). That is exactly why it can transfer to
the 110 private games: nothing is fit to the public games ahead of time.

``WorldModelAgent.choose_action`` returns an official ``arcengine.GameAction``
with ``set_data({"x","y"})`` already applied for ACTION6, so the framework's
``take_action`` -> ``action.action_data.model_dump()`` path gets click
coordinates with no extra work here.
"""

from __future__ import annotations

from typing import Any

from admorphiq._agents_shim import load_agent_class
from admorphiq.world_model_agent import WorldModelAgent

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


class KaggleWorldModelAgent(Agent):  # type: ignore[misc,valid-type]
    """Official ``agents.agent.Agent`` deploying the online world-model agent.

    Plays one game per instance. All logic (discovery probing, online effect
    model, goal inference, search planning) lives in the composed
    :class:`WorldModelAgent`; this class only wires it into the official
    interface and enforces a safety-net action budget.
    """

    # Safety net only — the composed agent's own discovery/plan/give-up logic
    # governs when to stop. The efficiency metric squares the human/agent
    # action ratio, so the agent aims for short plans; this cap just bounds a
    # pathological no-progress game.
    MAX_ACTIONS = 600

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._wm = WorldModelAgent()

    # ----- official interface ------------------------------------------------

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        """Stop on WIN / agent give-up, and as a safety net at MAX_ACTIONS."""
        if self.action_counter >= self.MAX_ACTIONS:
            return True
        return self._wm.is_done(frames, latest_frame)

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        """Delegate to the world-model agent; returns an official GameAction.

        For ACTION6 the returned action already carries x/y via ``set_data``.
        """
        return self._wm.choose_action(frames, latest_frame)

    def choose_action_with_data(
        self, frames: list[Any], latest_frame: Any
    ) -> tuple[Any, dict[str, int] | None]:
        """Return ``(action, data)`` — ``data`` is the ACTION6 click dict.

        One agent step per call (mirrors ``choose_action``); the two entry
        points are never both invoked for the same step.
        """
        action = self._wm.choose_action(frames, latest_frame)
        return action, _action6_data(action)
