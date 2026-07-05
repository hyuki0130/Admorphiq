"""Official-framework wrapper deploying the graph-frontier agent on Kaggle.

This is the DEPLOYED submission agent (decision R37b, see
.wiki/wiki/rounds/r36_graph-frontier-bfs.md). It subclasses the official
``agents.agent.Agent`` interface (one instance per game) and delegates every
decision to :class:`admorphiq.graph_frontier_agent.GraphFrontierAgent`.

Why this agent for the 110 PRIVATE games:
- TRAINING-FREE: HUD/region-masked state hashing -> exact observed transition
  graph -> frontier shortest-path BFS. Nothing is learned from the public games,
  so there is no warm-start/transfer inflation question at all (the BC-policy
  and reward-shaping levers measured ~0% transfer; this mechanism is
  transfer-honest by construction).
- Measured (transfer-honest): 9-subset mean game_score 0.0055 vs the online-RL
  from-scratch 0.0014; full-25 8/25 L1 @8000; with the give-up cap raised it
  BREAKS L2 (CD82 342+26,965 actions, VC33 954+12,389) — depth scales with
  budget, which Kaggle provides: the offline arcengine steps at ~1000+/s, so
  the ~295 s/game budget (9 h / 110 games) affords ~10^5 actions per game for
  a training-free agent.

The wrapper widens the agent's internal give-up to match the big Kaggle budget
(env-overridable) and enforces a hard MAX_ACTIONS safety net.
"""

from __future__ import annotations

import os
from typing import Any

from admorphiq._agents_shim import load_agent_class
from admorphiq.graph_frontier_agent import GraphFrontierAgent

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


class KaggleGraphFrontierAgent(Agent):  # type: ignore[misc,valid-type]
    """Official ``agents.agent.Agent`` deploying the graph-frontier agent.

    Plays one game per instance. All logic (region-masked state hashing, exact
    transition graph, frontier BFS, segment click candidates) lives in the
    composed :class:`GraphFrontierAgent`; this class wires it into the official
    interface, widens the give-up to the Kaggle action budget, and enforces a
    MAX_ACTIONS safety net.
    """

    # ~295 s/game (9 h / 110 games) at the offline engine's ~1000+ steps/s
    # affords ~10^5 actions for a training-free agent. R37b measured depth
    # (L2 clears) appearing only past the ~10^4-action mark, so the budget IS
    # the depth lever here. Env-overridable for dev experiments.
    MAX_ACTIONS = int(os.environ.get("KAGGLE_GF_MAX_ACTIONS", "100000"))

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Widen the agent's internal no-progress give-up to the big budget
        # unless the operator already pinned one explicitly.
        os.environ.setdefault("GF_GIVEUP", str(self.MAX_ACTIONS))
        self._gf = GraphFrontierAgent()

    # ----- official interface ------------------------------------------------

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        """Stop on WIN / agent give-up, and as a safety net at MAX_ACTIONS."""
        if self.action_counter >= self.MAX_ACTIONS:
            return True
        return self._gf.is_done(frames, latest_frame)

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        """Delegate to the graph-frontier agent; returns an official GameAction.

        For ACTION6 the returned action already carries x/y via ``set_data``.
        """
        return self._gf.choose_action(frames, latest_frame)

    def choose_action_with_data(
        self, frames: list[Any], latest_frame: Any
    ) -> tuple[Any, dict[str, int] | None]:
        """Return ``(action, data)`` — ``data`` is the ACTION6 click dict.

        One agent step per call (mirrors ``choose_action``); the two entry
        points are never both invoked for the same step.
        """
        action = self._gf.choose_action(frames, latest_frame)
        return action, _action6_data(action)
