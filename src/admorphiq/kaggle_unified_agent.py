"""Official ``agents.agent.Agent`` deploying the GENERIC TOOLS ALONE — zero adapters.

⛔ THIS IS THE WIRING THAT WAS MISSING, and its absence is why a measured 0.31 of card was
sitting unshippable. Six Kaggle wrappers existed — BC, online-RL, chained, world-model,
detection dispatch, graph-frontier — and **none of them wrapped the generic tool harness**, so
the axis rule 7a names ("clear the sample games" with `--agent unified`) had no route to a
notebook at all. Measured on ceph-build at @4000, same tree, full 25:

    --agent kaggle_detect  (as SHIPPED: 13 adapters + generic fallback)   0.5335
    --agent unified        (generic tools alone, zero adapters)           0.8874

The adapters are worse on 23 of 25 games. They were written when the generic fallback scored
0.0566 and both routing guards were calibrated against that; neither can see that the fallback
has since overtaken them.

⚠️ Why this is the right thing to SHIP and not merely the higher number: the eval is 110 PRIVATE
games. An adapter fires on a mechanic recognised from the public 25, so a private game carrying
none of them gets the fallback anyway — which is why raising the public card 5.6x moved the hidden
score 0.20 -> 0.18. The generic tools read no game id, no title and no sprite tag, and their
measured transfer across re-rendered games is 0.9981 with 13 of 14 IDENTICAL.

⛔ Building this is NOT submitting it. Whether the submission notebook switches to this wrapper is
submission-affecting and the user's call — see
`.wiki/wiki/lessons/adapters_now_cost_the_card_20260827.md`.
"""

from __future__ import annotations

import os
from typing import Any

from admorphiq._agents_shim import load_agent_class
from admorphiq.harness.loop import UnifiedAgent
from admorphiq.harness.registry import default_tools, ollama_llm, openai_compat_llm
from admorphiq.kaggle_chained_agent import _action6_data

Agent = load_agent_class()


def build_unified() -> UnifiedAgent:
    """The generic harness, buildable off-Kaggle so the wrapper can be verified locally.

    The construction MIRRORS ``scripts/score_efficiency.py:_make_agent("unified")`` — same
    tools, same llm wiring, same giveup/stall/ctx knobs — so the notebook ships what the round
    measurements measure. ⛔ Diverging here is how a card drifts from its own scoreboard: the
    runner supplies parameters a hand-built call silently omits, and that has already cost this
    project a measurement (0.0338 where the real run gives 0.1648).

    ⛔ `no_progress` is NOT defaulted here. It belongs to ``UnifiedAgent``; duplicating it once
    created two homes and the wrong one won, so a bail that was measured, committed and written
    up never ran.

    The harness routes by frame signature whenever the llm call raises, and on Kaggle without a
    served model that is the path taken. MEASURED on a Kaggle GPU run 2026-08-27 with a real
    gemma-4-31b behind vLLM: the LLM arm and the signature arm scored **0.853963 both, ZERO games
    differing** — so on these 25 the model changes nothing and its absence costs nothing. Stage 2
    is where a model earns its place, on games no tool was tuned against.
    """
    use_openai = (
        os.environ.get("HARNESS_LLM_BACKEND", "").lower() == "openai"
        or bool(os.environ.get("HARNESS_LLM_BASE_URL"))
    )

    def _llm(num_predict: int = 1024, num_ctx: int = 16384):
        if use_openai:
            return openai_compat_llm(num_predict=num_predict)
        return ollama_llm(num_ctx=num_ctx, num_predict=num_predict)

    no_progress = os.environ.get("HARNESS_NOPROGRESS")
    return UnifiedAgent(
        default_tools(),
        _llm(),
        **({"no_progress": int(no_progress)} if no_progress else {}),
        draw_llm=_llm(num_ctx=8192, num_predict=400),
        giveup=int(os.environ.get("GF_GIVEUP", "8000")),
        stall=int(os.environ.get("HARNESS_STALL", "80")),
        ctx_budget=int(os.environ.get("HARNESS_CTX", "6000")),
    )


class KaggleUnifiedAgent(Agent):  # type: ignore[misc,valid-type]
    """The generic tool harness behind the official agent interface."""

    #: Per-game action budget, inherited from the measurement that set it for the shipped card:
    #: capping at 4,000 costs no score (identical to four decimals against no cap) and buys the
    #: run back from the 9-hour limit. ⛔ Not lower — re86 clears a FULL-SCORE level at 588
    #: cumulative actions, so a cap at 500 would destroy real score.
    MAX_ACTIONS = int(os.environ.get("KAGGLE_UNIFIED_MAX_ACTIONS", "4000"))

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._agent = build_unified()

    # ----- official interface ------------------------------------------------

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        """Stop on the harness's own verdict, and as a safety net at MAX_ACTIONS."""
        if self.action_counter >= self.MAX_ACTIONS:
            return True
        return self._agent.is_done(frames, latest_frame)

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        return self._agent.choose_action(frames, latest_frame)

    def choose_action_with_data(
        self, frames: list[Any], latest_frame: Any
    ) -> tuple[Any, dict[str, int] | None]:
        """Return ``(action, data)`` — one agent step per call."""
        action = self._agent.choose_action(frames, latest_frame)
        return action, _action6_data(action)
