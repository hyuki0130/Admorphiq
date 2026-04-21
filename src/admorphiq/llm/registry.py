"""Candidate registry + backend protocol for Phase 8 LLM benchmark.

The registry reads `configs/llm.yaml` and exposes a uniform `LLMBackend`
interface. Backends dispatch by `family`:

  - gemma4 / qwen3 → OllamaBackend (requires `ollama serve`)

Adding a new candidate is a YAML edit plus (if a new family) one Python class.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
LLM_YAML = REPO_ROOT / "configs" / "llm.yaml"


@dataclass(frozen=True)
class CandidateMeta:
    """Static metadata for one LLM candidate from `configs/llm.yaml`."""

    id: str
    display_name: str
    family: str
    ollama_tag: str | None
    params_dense: float
    params_effective: float
    license: str
    quantization: str
    expected_vram_gb: float
    context_tokens: int
    lora_ecosystem: str
    strengths: list[str]
    enabled: bool


class LLMBackend(Protocol):
    """Minimal contract every candidate backend must satisfy."""

    meta: CandidateMeta

    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        """Return the generated text for a prompt.

        `json_schema` — optional JSON Schema dict; when set, the backend must
        constrain generation to match. Ollama 0.5+ supports this via the
        `format` API parameter. Backends that cannot enforce schema MUST
        raise rather than silently fall back to free-form generation.
        """
        ...


def load_registry() -> list[CandidateMeta]:
    """Read `configs/llm.yaml` and return every candidate's metadata."""
    if yaml is None:
        raise RuntimeError("pyyaml is required to read configs/llm.yaml")
    data = yaml.safe_load(LLM_YAML.read_text())
    out: list[CandidateMeta] = []
    for raw in data["candidates"]:
        out.append(
            CandidateMeta(
                id=raw["id"],
                display_name=raw["display_name"],
                family=raw["family"],
                ollama_tag=raw.get("ollama_tag"),
                params_dense=float(raw["params_dense"]),
                params_effective=float(raw["params_effective"]),
                license=raw["license"],
                quantization=raw["quantization"],
                expected_vram_gb=float(raw["expected_vram_gb"]),
                context_tokens=int(raw["context_tokens"]),
                lora_ecosystem=raw["lora_ecosystem"],
                strengths=list(raw.get("strengths", [])),
                enabled=bool(raw.get("enabled", False)),
            )
        )
    return out


def load_candidate(candidate_id: str) -> LLMBackend:
    """Return a ready-to-use backend for the named candidate."""
    for meta in load_registry():
        if meta.id != candidate_id:
            continue
        if meta.family in ("gemma4", "qwen3"):
            if not meta.ollama_tag:
                raise ValueError(
                    f"Candidate {candidate_id!r} missing ollama_tag in configs/llm.yaml"
                )
            from .ollama_backend import OllamaBackend  # lazy import
            return OllamaBackend(meta, meta.ollama_tag)
        raise NotImplementedError(
            f"Candidate '{candidate_id}' (family={meta.family}) has no backend wired."
        )
    raise KeyError(f"No candidate with id {candidate_id!r} in {LLM_YAML}")


_GAME_TITLE_MARKER = re.compile(r"Game title:\s*([A-Z0-9]{4})")


def extract_game_name(prompt: str) -> str:
    """Utility used by the bench script to identify which game a prompt refers to."""
    match = _GAME_TITLE_MARKER.search(prompt)
    return match.group(1) if match else "UNKNOWN"
