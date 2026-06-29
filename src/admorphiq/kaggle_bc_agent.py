"""Official-framework wrapper that deploys the trained BC policy on Kaggle.

This is the Kaggle submission agent. It subclasses the official
``agents.agent.Agent`` interface (one instance per game, driven by the
framework's ``main()`` loop) and delegates every decision to the trained
behaviour-cloning policy in :class:`admorphiq.bc_agent.BCPolicyAgent`.

Why a thin wrapper instead of making ``BCPolicyAgent`` itself the official
agent: ``BCPolicyAgent`` is harness-shaped but framework-agnostic — it
operates over the raw arcengine observation and owns the net load, the
masked frame->logits policy, the cycle detector and the optional TTT depth
loop. Keeping it decoupled from the official ``Agent`` base (which carries
recorder / tracing / arc_env plumbing) lets the training + scoring pipeline
reuse it without dragging in the framework. This class is the only adapter
that binds it to the official run-loop.

The composed ``BCPolicyAgent.choose_action`` already returns an official
``arcengine.GameAction`` with ``set_data({"x":..,"y":..})`` applied for
ACTION6 (via ``AdmorphiqAdapter._convert_action``), so the framework's
``take_action`` -> ``action.action_data.model_dump()`` path gets the click
coordinates with no extra work here.

Weights: loaded from ``models/bc_policy.pt`` by default — the running
training pipeline promotes its current best into that path, so the
submission auto-deploys whatever is best at submit time. ``BC_WEIGHTS``
overrides the path.
"""

from __future__ import annotations

import os
from typing import Any

from admorphiq._agents_shim import load_agent_class
from admorphiq.bc_agent import DEFAULT_WEIGHTS, BCPolicyAgent

Agent = load_agent_class()


def _action6_data(action: Any) -> dict[str, int] | None:
    """Extract the ACTION6 ``{"x", "y"}`` dict from an official GameAction.

    Returns ``None`` for every non-ACTION6 action (the BC policy already
    attached the coordinates to the action via ``set_data``; this just mirrors
    them out for the ``choose_action_with_data`` contract).
    """
    if getattr(action, "value", None) != 6:
        return None
    ad = getattr(action, "action_data", None)
    if ad is None:
        return None
    return {"x": int(getattr(ad, "x", 0)), "y": int(getattr(ad, "y", 0))}


class KaggleBCAgent(Agent):  # type: ignore[misc,valid-type]
    """Official ``agents.agent.Agent`` deploying the trained BC policy.

    Plays one game per instance. All policy logic (net, masking, cycle
    detection, TTT) lives in the composed :class:`BCPolicyAgent`; this class
    only wires it into the official interface and enforces the action budget.
    """

    # Efficiency matters (the metric squares the human/agent action ratio), so
    # keep the budget tight. The composed BCPolicyAgent's cycle detector and
    # no-progress give-up still prevent grinding within this cap.
    MAX_ACTIONS = 200

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        weights = os.environ.get("BC_WEIGHTS", "").strip() or DEFAULT_WEIGHTS
        self._bc = BCPolicyAgent(weights_path=weights)

    # ----- official interface ------------------------------------------------

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        """Stop on WIN / policy give-up, and as a safety net at MAX_ACTIONS."""
        if self.action_counter >= self.MAX_ACTIONS:
            return True
        return self._bc.is_done(frames, latest_frame)

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        """Delegate to the BC policy; returns an official GameAction.

        For ACTION6 the returned action already carries x/y via ``set_data``,
        so the framework's ``take_action`` reaches the click coordinates.
        """
        return self._bc.choose_action(frames, latest_frame)

    def choose_action_with_data(
        self, frames: list[Any], latest_frame: Any
    ) -> tuple[Any, dict[str, int] | None]:
        """Return ``(action, data)`` — ``data`` is the ACTION6 click dict.

        One BC step per call (mirrors ``choose_action``); the two entry points
        are never both invoked for the same step.
        """
        action = self._bc.choose_action(frames, latest_frame)
        return action, _action6_data(action)
