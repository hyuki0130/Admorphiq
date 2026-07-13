"""Official-framework wrapper deploying the LLM-FREE chained agent on Kaggle.

The measured single-artifact submission (rounds/r53, 2026-07-13): the
:class:`~admorphiq.chained_agent.ChainedAgent` runs the R28
:class:`~admorphiq.world_model_agent.WorldModelAgent` probe first — it banks
the arrangement/selection-class games EFFICIENTLY (su15 2 levels/58 actions,
ls20 88, sb26 259, ar25 2 levels; RHAE squares efficiency, so these dominate
the score) and self-terminates in ~50-260 actions elsewhere — then hands the
remaining budget to the :class:`~admorphiq.harness.loop.UnifiedAgent` graph
stack (tier gate, region mask, hash ladder, de-aliasing).

LLM-FREE by construction: the unified member gets a dead LLM callable, so its
offline-safe fallbacks route by frame signature. Measured on the full 25:
**no-LLM = 14 cleared / 1.072%** vs the gemma stack's 15 / 1.076% — the LLM
contributes +0.004%p, so v1 ships numpy-only (no model mount, no offline
ollama packaging risk); the LLM stack is a v2 upgrade path.

Both members are frame-only and game-id-free, and both self-emit RESET on
GAME_OVER, so the wrapper only wires the official interface, sets the deployed
env config, and enforces a MAX_ACTIONS safety net.
"""

from __future__ import annotations

import os
from typing import Any

from admorphiq._agents_shim import load_agent_class
from admorphiq.chained_agent import ChainedAgent
from admorphiq.harness.loop import UnifiedAgent
from admorphiq.harness.registry import default_tools
from admorphiq.world_model_agent import WorldModelAgent

Agent = load_agent_class()


def _no_llm(_messages: Any) -> str:
    """Dead LLM: raising engages the harness's offline-safe signature routing
    (the exact configuration the 1.072% full-25 measurement ran)."""
    raise RuntimeError("LLM-free deployment")


def _action6_data(action: Any) -> dict[str, int] | None:
    """Extract the ACTION6 ``{"x", "y"}`` dict from an official GameAction."""
    if getattr(action, "value", None) != 6:
        return None
    ad = getattr(action, "action_data", None)
    if ad is None:
        return None
    return {"x": int(getattr(ad, "x", 0)), "y": int(getattr(ad, "y", 0))}


def build_chained() -> ChainedAgent:
    """The deployed no-LLM chain, buildable off-Kaggle for local verification."""
    unified = UnifiedAgent(
        default_tools(),
        _no_llm,
        giveup=int(os.environ.get("GF_GIVEUP", "8000")),
        stall=int(os.environ.get("HARNESS_STALL", "80")),
        ctx_budget=int(os.environ.get("HARNESS_CTX", "6000")),
    )
    return ChainedAgent(WorldModelAgent(), unified)


class KaggleChainedAgent(Agent):  # type: ignore[misc,valid-type]
    """Official ``agents.agent.Agent`` deploying the no-LLM chained artifact."""

    # 9 h / 110 games ≈ 295 s/game at the offline engine's ~1000+ steps/s.
    # The deployed dev config (GF_GIVEUP=8000) is the MEASURED card; the
    # safety net stays far above it so per-level restarts fit comfortably.
    MAX_ACTIONS = int(os.environ.get("KAGGLE_CHAINED_MAX_ACTIONS", "100000"))

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        os.environ.setdefault("GF_GIVEUP", "8000")
        self._chain = build_chained()

    # ----- official interface ------------------------------------------------

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        """Stop on the chain's verdict, and as a safety net at MAX_ACTIONS."""
        if self.action_counter >= self.MAX_ACTIONS:
            return True
        return self._chain.is_done(frames, latest_frame)

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        """Delegate to the chain; ACTION6 already carries x/y via set_data."""
        return self._chain.choose_action(frames, latest_frame)

    def choose_action_with_data(
        self, frames: list[Any], latest_frame: Any
    ) -> tuple[Any, dict[str, int] | None]:
        """Return ``(action, data)`` — one agent step per call."""
        action = self._chain.choose_action(frames, latest_frame)
        return action, _action6_data(action)
