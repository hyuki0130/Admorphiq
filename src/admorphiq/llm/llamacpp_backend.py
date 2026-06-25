"""llama-cpp-python backend for offline GGUF inference (Kaggle / air-gapped).

This backend loads the **same GGUF weights** that OllamaBackend pulls via the
Ollama server, so dev-time and Kaggle-time prompts are byte-for-byte identical.
The only difference is the serving layer:

  dev-time  →  OllamaBackend  (ollama serve + HTTP round-trip)
  Kaggle    →  LlamaCppBackend (llama_cpp.Llama in-process, CUDA layers)

Kaggle setup:
  1. Add a dataset containing the GGUF file (e.g. qwen3-8b-q4_k_m.gguf).
  2. Install the CUDA wheel BEFORE importing this module:
       pip install llama-cpp-python \
           --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121
  3. Point ADMORPHIQ_GGUF_PATH to the dataset mount path, e.g.:
       /kaggle/input/qwen3-gguf/qwen3-8b-q4_k_m.gguf

Local setup (optional, for smoke-testing without Ollama):
  pip install llama-cpp-python          # CPU build, slower
  export ADMORPHIQ_GGUF_PATH=~/.ollama/models/blobs/<sha256>
  export ADMORPHIQ_LLM_BACKEND=llamacpp

Note: llama-cpp-python is NOT a hard pyproject dependency because it requires a
native build step (cmake + BLAS / CUDA). It is imported lazily inside __init__
so that importing this module file does not fail when the package is absent.
"""

from __future__ import annotations

import json
import os
from typing import Any

from .registry import CandidateMeta


class LlamaCppBackend:
    """Generate text via an in-process llama.cpp GGUF model.

    Parameters
    ----------
    meta:
        Candidate metadata from configs/llm.yaml.
    gguf_path:
        Path to the GGUF file.  Falls back to the ADMORPHIQ_GGUF_PATH env var
        when not supplied.  Raises ValueError if neither is available.
    """

    def __init__(
        self,
        meta: CandidateMeta,
        gguf_path: str | None = None,
    ) -> None:
        self.meta = meta

        resolved = gguf_path or os.environ.get("ADMORPHIQ_GGUF_PATH")
        if not resolved:
            raise ValueError(
                "LlamaCppBackend requires a GGUF path.  Pass gguf_path= or set "
                "ADMORPHIQ_GGUF_PATH in the environment."
            )
        self._gguf_path = resolved

        # Lazy import: importing this module must NOT fail when llama_cpp is absent.
        try:
            import llama_cpp  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "llama-cpp-python is not installed.  Install it with:\n"
                "  pip install llama-cpp-python\n"
                "or (CUDA / Kaggle):\n"
                "  pip install llama-cpp-python "
                "--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121"
            ) from exc

        self._llama = llama_cpp.Llama(
            model_path=self._gguf_path,
            n_ctx=8192,
            n_gpu_layers=-1,
            verbose=False,
        )
        self._llama_cpp = llama_cpp

    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        """Return generated text, optionally constrained to json_schema.

        Mirrors OllamaBackend.generate exactly:
        - Prepends ``/no_think`` for qwen3 family models so the model emits
          the answer directly without the reasoning-chain preamble.
        - When json_schema is given, builds a LlamaGrammar from it and passes
          it as ``grammar=`` to enforce structure at the decoder level.
        - temperature 0.0 for deterministic output.

        Raises RuntimeError if json_schema is provided but LlamaGrammar
        construction fails — mirrors the OllamaBackend contract of raising
        rather than silently falling back to free-form generation.
        """
        use_prompt = prompt
        if self.meta.family == "qwen3" and not prompt.lstrip().startswith("/no_think"):
            use_prompt = "/no_think\n" + prompt

        grammar = None
        if json_schema is not None:
            try:
                grammar = self._llama_cpp.LlamaGrammar.from_json_schema(
                    json.dumps(json_schema)
                )
            except Exception as exc:
                raise RuntimeError(
                    f"LlamaCppBackend: failed to build grammar from json_schema: {exc}"
                ) from exc

        kwargs: dict[str, Any] = {
            "max_tokens": max_tokens,
            "temperature": 0.0,
        }
        if grammar is not None:
            kwargs["grammar"] = grammar

        out = self._llama(use_prompt, **kwargs)
        return out["choices"][0]["text"]
