"""Tests for LlamaCppBackend and registry env-driven selection.

No llama_cpp installation or model download is required — llama_cpp is fully
mocked via monkeypatching sys.modules before any import of the backend.
"""

from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_meta(family: str = "qwen3") -> Any:
    """Return a minimal CandidateMeta-like object for testing."""
    from admorphiq.llm.registry import CandidateMeta

    return CandidateMeta(
        id="qwen3_8b",
        display_name="Qwen 3 8B",
        family=family,
        ollama_tag="qwen3:8b",
        params_dense=8.0,
        params_effective=8.0,
        license="Apache 2.0",
        quantization="Q4_K_M",
        expected_vram_gb=5.0,
        context_tokens=131072,
        lora_ecosystem="mature",
        strengths=["reasoning"],
        enabled=True,
    )


def _make_llama_cpp_mock(generated_text: str = '{"result": 1}') -> types.ModuleType:
    """Build a fake llama_cpp module with the API surface we use."""
    mod = types.ModuleType("llama_cpp")

    # Mock Llama class
    llama_instance = MagicMock()
    llama_instance.return_value = {
        "choices": [{"text": generated_text}]
    }
    LlamaClass = MagicMock(return_value=llama_instance)
    mod.Llama = LlamaClass  # type: ignore[attr-defined]

    # Mock LlamaGrammar
    grammar_instance = MagicMock()
    LlamaGrammar = MagicMock()
    LlamaGrammar.from_json_schema = MagicMock(return_value=grammar_instance)
    mod.LlamaGrammar = LlamaGrammar  # type: ignore[attr-defined]

    return mod


def _build_backend(gguf_path: str = "/fake/model.gguf", family: str = "qwen3",
                   generated_text: str = '{"result": 1}'):
    """Inject a mock llama_cpp and return a LlamaCppBackend instance."""
    mock_mod = _make_llama_cpp_mock(generated_text)
    sys.modules["llama_cpp"] = mock_mod
    try:
        # Force re-import with mock in place
        if "admorphiq.llm.llamacpp_backend" in sys.modules:
            del sys.modules["admorphiq.llm.llamacpp_backend"]
        from admorphiq.llm.llamacpp_backend import LlamaCppBackend
        backend = LlamaCppBackend(_make_meta(family), gguf_path=gguf_path)
        return backend, mock_mod
    finally:
        # Leave mock in sys.modules so the backend object still works
        pass


# ---------------------------------------------------------------------------
# Test: prompt construction — qwen3 /no_think prefix
# ---------------------------------------------------------------------------

class TestPromptConstruction:
    def test_qwen3_no_think_prefix_added(self):
        """Purpose: verify qwen3 family gets /no_think prepended when absent.

        Expected feedback: PASS confirms the backend mirrors OllamaBackend's
        qwen3 prefix logic; FAIL means offline and online prompts diverge.
        """
        backend, mock_mod = _build_backend(family="qwen3")
        llama_instance = mock_mod.Llama.return_value

        backend.generate("Hello world")

        call_args = llama_instance.call_args
        used_prompt = call_args[0][0]
        assert used_prompt.startswith("/no_think\n"), (
            f"Expected /no_think prefix, got: {used_prompt[:40]!r}"
        )
        assert "Hello world" in used_prompt

    def test_qwen3_no_think_not_duplicated(self):
        """Purpose: verify /no_think is not prepended when already present.

        Expected feedback: PASS means the guard condition works and no
        double-prefix pollutes the prompt.
        """
        backend, mock_mod = _build_backend(family="qwen3")
        llama_instance = mock_mod.Llama.return_value

        backend.generate("/no_think\nAlready prefixed")

        call_args = llama_instance.call_args
        used_prompt = call_args[0][0]
        assert used_prompt.count("/no_think") == 1

    def test_non_qwen3_family_no_prefix(self):
        """Purpose: verify non-qwen3 families do NOT get /no_think prepended.

        Expected feedback: PASS means gemma4 prompts are passed verbatim,
        matching OllamaBackend's family-gated prefix logic.
        """
        backend, mock_mod = _build_backend(family="gemma4")
        llama_instance = mock_mod.Llama.return_value

        backend.generate("Hello")

        call_args = llama_instance.call_args
        used_prompt = call_args[0][0]
        assert not used_prompt.startswith("/no_think"), (
            f"gemma4 should not get /no_think prefix, got: {used_prompt!r}"
        )


# ---------------------------------------------------------------------------
# Test: json_schema triggers grammar construction
# ---------------------------------------------------------------------------

class TestJsonSchemaGrammar:
    def test_json_schema_builds_grammar(self):
        """Purpose: verify that passing json_schema calls LlamaGrammar.from_json_schema
        and passes the resulting grammar object to the Llama call.

        Expected feedback: PASS confirms the constrained-decoding path is wired
        correctly; FAIL means structured output is not enforced at the decoder.
        """
        import json

        schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
        backend, mock_mod = _build_backend()
        llama_instance = mock_mod.Llama.return_value
        grammar_instance = mock_mod.LlamaGrammar.from_json_schema.return_value

        backend.generate("prompt", json_schema=schema)

        # Grammar was built from the serialised schema
        mock_mod.LlamaGrammar.from_json_schema.assert_called_once_with(
            json.dumps(schema)
        )
        # Grammar was passed to the Llama call
        call_kwargs = llama_instance.call_args[1]
        assert call_kwargs.get("grammar") is grammar_instance

    def test_no_json_schema_no_grammar(self):
        """Purpose: verify that when json_schema is None, no grammar is built
        and the grammar kwarg is absent from the Llama call.

        Expected feedback: PASS confirms free-form generation path is clean.
        """
        backend, mock_mod = _build_backend()
        llama_instance = mock_mod.Llama.return_value

        backend.generate("prompt")

        mock_mod.LlamaGrammar.from_json_schema.assert_not_called()
        call_kwargs = llama_instance.call_args[1]
        assert "grammar" not in call_kwargs

    def test_grammar_construction_failure_raises(self):
        """Purpose: verify RuntimeError is raised (not swallowed) when
        LlamaGrammar.from_json_schema raises — matching the contract that
        backends must raise rather than silently fall back.

        Expected feedback: PASS confirms the error-propagation contract holds.
        """
        backend, mock_mod = _build_backend()
        mock_mod.LlamaGrammar.from_json_schema.side_effect = ValueError("bad schema")

        with pytest.raises(RuntimeError, match="failed to build grammar"):
            backend.generate("prompt", json_schema={"type": "bad"})


# ---------------------------------------------------------------------------
# Test: registry env-driven selection
# ---------------------------------------------------------------------------

class TestRegistryEnvSelection:
    """Tests that load_candidate picks the right backend based on env vars."""

    def test_ollama_backend_by_default(self, monkeypatch):
        """Purpose: verify load_candidate returns OllamaBackend when no
        ADMORPHIQ_LLM_BACKEND / ADMORPHIQ_GGUF_PATH env vars are set.

        Expected feedback: PASS confirms existing OllamaBackend dev usage is
        unbroken; FAIL means the env-guard logic has a bug.
        """
        monkeypatch.delenv("ADMORPHIQ_LLM_BACKEND", raising=False)
        monkeypatch.delenv("ADMORPHIQ_GGUF_PATH", raising=False)

        import admorphiq.llm.registry as registry
        from admorphiq.llm.ollama_backend import OllamaBackend

        meta = _make_meta("qwen3")
        with patch.object(registry, "load_registry", return_value=[meta]):
            backend = registry.load_candidate("qwen3_8b")

        assert isinstance(backend, OllamaBackend)

    def test_llamacpp_backend_via_backend_env(self, monkeypatch):
        """Purpose: verify load_candidate returns LlamaCppBackend when
        ADMORPHIQ_LLM_BACKEND=llamacpp is set.

        Expected feedback: PASS confirms the Kaggle offline path is selectable
        without modifying any Python code; FAIL means the env gate is broken.
        """
        monkeypatch.setenv("ADMORPHIQ_LLM_BACKEND", "llamacpp")
        monkeypatch.setenv("ADMORPHIQ_GGUF_PATH", "/fake/model.gguf")

        mock_mod = _make_llama_cpp_mock()
        sys.modules["llama_cpp"] = mock_mod

        import admorphiq.llm.registry as registry
        from admorphiq.llm.llamacpp_backend import LlamaCppBackend

        meta = _make_meta("qwen3")
        with patch.object(registry, "load_registry", return_value=[meta]):
            backend = registry.load_candidate("qwen3_8b")

        assert isinstance(backend, LlamaCppBackend)

    def test_llamacpp_backend_via_gguf_path_env(self, monkeypatch):
        """Purpose: verify load_candidate returns LlamaCppBackend when only
        ADMORPHIQ_GGUF_PATH is set (ADMORPHIQ_LLM_BACKEND absent).

        Expected feedback: PASS confirms the convenience path where setting just
        the GGUF path is sufficient to activate offline inference.
        """
        monkeypatch.delenv("ADMORPHIQ_LLM_BACKEND", raising=False)
        monkeypatch.setenv("ADMORPHIQ_GGUF_PATH", "/fake/model.gguf")

        mock_mod = _make_llama_cpp_mock()
        sys.modules["llama_cpp"] = mock_mod

        import admorphiq.llm.registry as registry
        from admorphiq.llm.llamacpp_backend import LlamaCppBackend

        meta = _make_meta("qwen3")
        with patch.object(registry, "load_registry", return_value=[meta]):
            backend = registry.load_candidate("qwen3_8b")

        assert isinstance(backend, LlamaCppBackend)
