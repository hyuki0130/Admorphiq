"""Default tool set + the runtime ollama LLM callable for the UnifiedAgent."""

from __future__ import annotations

import json
import os
import urllib.request

from admorphiq.tools.base import Tool


def default_tools() -> list[Tool]:
    """Instantiate the generic Claude-built tools in priority order.

The rule-recovery tools go FIRST because they are the most selective: it declines any frame without a
    board that does not carry their mechanic — `StencilTool` wants a tile lattice with an
    instruction glyph, `TrackAlignTool` a closed loop of equal tiles with a marked slot. Both
    measured at **0 false positives across the 25 sample games**, withdrawing in three actions and
    ZERO respectively. A tool that is cheap to be wrong about belongs ahead of one that will
    always propose something.
    """
    from admorphiq.tools.assemble import JigsawAssembleTool
    from admorphiq.tools.cover_targets import CoverTargetsTool
    from admorphiq.tools.clonewalk import CloneWalkTool
    from admorphiq.tools.cyclepress import CyclePressTool
    from admorphiq.tools.dead_signature import DeadSignatureTool
    from admorphiq.tools.dealias import DealiasTool
    from admorphiq.tools.graph_search import GraphSearchTool
    from admorphiq.tools.haul import HaulDeliveryTool
    from admorphiq.tools.hop import HopTool
    from admorphiq.tools.keymaze import KeyMazeTool
    from admorphiq.tools.lattice_maze import LatticeMazeTool
    from admorphiq.tools.ledge import LedgeTool
    from admorphiq.tools.linkage import LinkageReachTool
    from admorphiq.tools.llm_goal import LLMGoalTool
    from admorphiq.tools.maze import MazeRunTool
    from admorphiq.tools.mirror import MirrorMergeTool
    from admorphiq.tools.paint_flood import PaintFloodTool
    from admorphiq.tools.pattern_cast import PatternCastTool
    from admorphiq.tools.phase import PhaseGridTool
    from admorphiq.tools.pillar_transfer import PillarTransferTool
    from admorphiq.tools.progbits import ProgramBitsTool
    from admorphiq.tools.reflect_cover import ReflectCoverTool
    from admorphiq.tools.rewrite import RuleRewriteTool
    from admorphiq.tools.slotlaunch import SlotLaunchTool
    from admorphiq.tools.socketmerge import SocketMergeTool
    from admorphiq.tools.spill import SpillRouteTool
    from admorphiq.tools.stamppaint import StampPaintTool
    from admorphiq.tools.stencil import StencilTool
    from admorphiq.tools.subroutine import SubroutineProgramTool
    from admorphiq.tools.tether import TetherCentroidTool
    from admorphiq.tools.toggle import ToggleTool
    from admorphiq.tools.track import TrackAlignTool
    from admorphiq.tools.tube import TubeOrderTool
    from admorphiq.tools.world_model import WorldModelTool

    graph = GraphSearchTool()
    deadsig = DeadSignatureTool()
    # `deadsig` was registered but never consulted by anything — wire it into the searcher's
    # candidate ordering so its counters actually reach a decision.
    graph.deadsig = deadsig

    return [
        StencilTool(),
        TrackAlignTool(),
        CyclePressTool(),
        CloneWalkTool(),
        MirrorMergeTool(),
        JigsawAssembleTool(),
        CoverTargetsTool(),
        LinkageReachTool(),
        PatternCastTool(),
        ReflectCoverTool(),
        RuleRewriteTool(),
        SocketMergeTool(),
        SubroutineProgramTool(),
        HopTool(),
        LatticeMazeTool(),
        PillarTransferTool(),
        ProgramBitsTool(),
        SpillRouteTool(),
        StampPaintTool(),
        TetherCentroidTool(),
        LedgeTool(),
        MazeRunTool(),
        PhaseGridTool(),
        TubeOrderTool(),
        HaulDeliveryTool(),
        KeyMazeTool(),
        SlotLaunchTool(),
        graph,
        WorldModelTool(),
        PaintFloodTool(),
        ToggleTool(),
        LLMGoalTool(),
        DealiasTool(),
        deadsig,
    ]


def ollama_llm(
    model: str | None = None,
    host: str | None = None,
    *,
    num_ctx: int = 16384,
    num_predict: int = 1024,
):
    """Return an ``llm(messages) -> str`` callable backed by a local ollama model.

    ``num_ctx`` is the runtime context window the bench sweeps for the
    performance/​cost trade-off. Offline only — no external network.
    """
    model = model or os.environ.get("HARNESS_MODEL", "gemma4:31b-it-q8_0")
    host = host or os.environ.get("HARNESS_HOST", "http://localhost:11434")

    def _call(messages: list[dict[str, str]]) -> str:
        body = {
            "model": model, "stream": False, "think": False, "messages": messages,
            # ⛔ `num_thread` is capped from the environment because the CPU box this runs on is
            # SHARED: measured 2026-08-27, one 26B model at full tilt took 3743% CPU (~37 cores)
            # and pushed the load average to 96 alongside other tenants' workloads. Unset means
            # ollama's own default, i.e. unchanged behaviour on a machine that is ours alone.
            "options": {
                "temperature": 0.0,
                "num_ctx": num_ctx,
                "num_predict": num_predict,
                **({"num_thread": int(os.environ["OLLAMA_NUM_THREAD"])}
                   if os.environ.get("OLLAMA_NUM_THREAD") else {}),
            },
        }
        req = urllib.request.Request(
            f"{host}/api/chat", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read())["message"]["content"]

    return _call


def openai_compat_llm(
    model: str | None = None,
    base_url: str | None = None,
    *,
    num_predict: int = 1024,
    timeout: float = 300.0,
):
    """Return an ``llm(messages) -> str`` callable against a vLLM OpenAI server.

    This is the Kaggle backend: Kaggle has no ollama daemon, but R55 proved a
    ``vllm.entrypoints.openai.api_server`` subprocess serving ``/chat/completions``.
    Endpoint + served model come from ``HARNESS_LLM_BASE_URL`` / ``HARNESS_LLM_MODEL``
    (the served-model-NAME the server was booted with, e.g. ``qwen`` — NOT the
    weights dir). Missing either is a hard error: a silent fallback would make
    UnifiedAgent quietly degrade to tools and read as a misleadingly green run.

    ``num_predict`` maps to ``max_tokens``. ``num_ctx`` is NOT a per-request knob
    on vLLM (the server fixes it via ``--max-model-len``), so it is intentionally
    absent here. Qwen thinking is disabled per request (it otherwise spends the
    whole token budget on reasoning — measured in R55).
    """
    model = model or os.environ.get("HARNESS_LLM_MODEL", "")
    base_url = (base_url or os.environ.get("HARNESS_LLM_BASE_URL", "")).rstrip("/")
    if not base_url or not model:
        raise RuntimeError(
            "openai_compat_llm needs HARNESS_LLM_BASE_URL and HARNESS_LLM_MODEL "
            f"(base_url={base_url!r}, model={model!r})"
        )

    def _call(messages: list[dict[str, str]]) -> str:
        body = {
            "model": model, "stream": False, "messages": messages,
            "temperature": 0.0, "max_tokens": num_predict,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        # Reasoning-model support (gpt-oss/harmony): the first A/B ran gpt-oss
        # with NO reasoning effort set (and thinking DISABLED above) — testing a
        # reasoning model with its reasoning channel off, a measured process
        # error. Env-gated so gemma4/qwen requests stay byte-identical unset.
        effort = os.environ.get("HARNESS_REASONING_EFFORT")
        if effort:
            body["reasoning_effort"] = effort
            del body["chat_template_kwargs"]
        req = urllib.request.Request(
            f"{base_url}/chat/completions", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]

    return _call


def openai_tool_client(
    model: str | None = None,
    base_url: str | None = None,
    *,
    num_predict: int = 2048,
    timeout: float = 300.0,
    enable_thinking: bool | None = None,
):
    """Return a ``chat(messages, tools=None, tool_choice=None) -> dict`` callable
    against the vLLM OpenAI server, returning the FULL assistant message
    (``content`` + ``tool_calls``) — the native function-calling contract.

    The prior string-only ``openai_compat_llm`` discarded ``tool_calls`` and forced
    the agent to regex-parse free text out of a monolithic prompt. This client does
    real tool-calling: pass ``tools`` (JSON function schemas with rich parameter
    descriptions) and ``tool_choice`` (``"auto"``, ``"required"``, or a named
    ``{"type":"function","function":{"name":...}}``); vLLM constrains decoding for
    named/required calls. ``enable_thinking`` is sent only when explicitly set (do
    NOT blanket-disable across models — that was a Qwen-specific hack)."""
    model = model or os.environ.get("HARNESS_LLM_MODEL", "")
    base_url = (base_url or os.environ.get("HARNESS_LLM_BASE_URL", "")).rstrip("/")
    if not base_url or not model:
        raise RuntimeError(
            "openai_tool_client needs HARNESS_LLM_BASE_URL and HARNESS_LLM_MODEL "
            f"(base_url={base_url!r}, model={model!r})"
        )

    def _chat(messages, tools=None, tool_choice=None) -> dict:
        body: dict = {
            "model": model, "stream": False, "messages": messages,
            "temperature": 0.0, "max_tokens": num_predict,
        }
        if tools is not None:
            body["tools"] = tools
            body["tool_choice"] = tool_choice or "auto"
        if enable_thinking is not None:
            body["chat_template_kwargs"] = {"enable_thinking": enable_thinking}
        req = urllib.request.Request(
            f"{base_url}/chat/completions", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            msg = json.loads(r.read())["choices"][0]["message"]
        return {"content": msg.get("content") or "", "tool_calls": msg.get("tool_calls") or []}

    return _chat
