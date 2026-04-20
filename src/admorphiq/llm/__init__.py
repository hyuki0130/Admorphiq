"""LLM abstraction layer for the Phase 8 Hypothesis Engine.

Each backend implements the `LLMBackend` protocol: `generate(prompt) -> str`.
Candidates are registered in `configs/llm.yaml` and loaded via `registry.load_candidate`.
Concrete backends (Ollama for Gemma 4 / Qwen 3 families) live in sibling modules.
"""

from __future__ import annotations

from .ollama_backend import OllamaBackend
from .registry import CandidateMeta, LLMBackend, extract_game_name, load_candidate, load_registry

__all__ = [
    "CandidateMeta",
    "LLMBackend",
    "OllamaBackend",
    "extract_game_name",
    "load_candidate",
    "load_registry",
]
