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
    from admorphiq.tools.world_model import WorldModelTool

    return [
        GraphSearchTool(),
        WorldModelTool(),
        PaintFloodTool(),
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
