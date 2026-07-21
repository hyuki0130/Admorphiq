"""Default tool set + the runtime ollama LLM callable for the UnifiedAgent."""

from __future__ import annotations

import json
import os
import urllib.request

from admorphiq.tools.base import Tool


def default_tools() -> list[Tool]:
    """Instantiate the six generic Claude-built tools in priority order."""
    from admorphiq.tools.dead_signature import DeadSignatureTool
    from admorphiq.tools.dealias import DealiasTool
    from admorphiq.tools.graph_search import GraphSearchTool
    from admorphiq.tools.llm_goal import LLMGoalTool
    from admorphiq.tools.paint_flood import PaintFloodTool
    from admorphiq.tools.toggle import ToggleTool
    from admorphiq.tools.world_model import WorldModelTool

    return [
        GraphSearchTool(),
        WorldModelTool(),
        PaintFloodTool(),
        ToggleTool(),
        LLMGoalTool(),
        DealiasTool(),
        DeadSignatureTool(),
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
            "options": {"temperature": 0.0, "num_ctx": num_ctx, "num_predict": num_predict},
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
        req = urllib.request.Request(
            f"{base_url}/chat/completions", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]

    return _call
