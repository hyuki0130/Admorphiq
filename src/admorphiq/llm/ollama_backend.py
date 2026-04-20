"""Ollama HTTP backend for LLM benchmark candidates.

Connects to a locally-running Ollama server (default: http://localhost:11434).
The model tag in `configs/llm.yaml` (`ollama_tag`) selects which pulled model runs.

Pull a missing model with `ollama pull <tag>` before enabling a candidate.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .registry import CandidateMeta


class OllamaBackend:
    """Generate text via the Ollama /api/generate endpoint."""

    def __init__(self, meta: CandidateMeta, ollama_tag: str, host: str = "http://localhost:11434") -> None:
        self.meta = meta
        self._tag = ollama_tag
        self._endpoint = f"{host.rstrip('/')}/api/generate"

    def generate(self, prompt: str, max_tokens: int = 512) -> str:
        # Qwen 3 (and other reasoning-tuned models) default to a "thinking" phase
        # whose tokens count against num_predict but do NOT appear in `response`.
        # Prepend `/no_think` so the model emits the answer directly; also disable
        # `think` at the API level for providers that honor it.
        use_prompt = prompt
        if self.meta.family == "qwen3" and not prompt.lstrip().startswith("/no_think"):
            use_prompt = "/no_think\n" + prompt
        body = {
            "model": self._tag,
            "prompt": use_prompt,
            "stream": False,
            "think": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.0,
                "top_p": 1.0,
            },
        }
        req = urllib.request.Request(
            self._endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                payload: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Ollama request failed for tag={self._tag!r}: {e}. "
                f"Ensure `ollama serve` is running and the model is pulled."
            )
        return payload.get("response", "")
